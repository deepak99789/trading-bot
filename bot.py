import yfinance as yf
import pandas as pd
import telebot
import time
import os
from datetime import datetime
from flask import Flask
import threading

# ---------- TELEGRAM SETUP ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "अपना_टोकन_यहाँ_डालो")
CHAT_ID = os.environ.get("CHAT_ID", "अपना_chat_id_यहाँ_डालो")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ---------- FLASK APP (UptimeRobot ke liye) ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Trading Bot is Alive! Scanning for Supply-Demand zones..."

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ---------- ASSETS TO SCAN ----------
STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "AXISBANK.NS", "MARUTI.NS", "TITAN.NS", "WIPRO.NS",
    "SUNPHARMA.NS", "ASIANPAINT.NS", "HCLTECH.NS", "ONGC.NS", "NTPC.NS",
    "POWERGRID.NS", "M&M.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "JSWSTEEL.NS",
    "TATAMOTORS.NS", "TECHM.NS", "BAJAJFINSV.NS", "COALINDIA.NS", "GRASIM.NS",
    "DIVISLAB.NS", "DRREDDY.NS", "ADANIPORTS.NS", "ADANIENT.NS", "BRITANNIA.NS",
    "EICHERMOT.NS", "HINDALCO.NS", "INDUSINDBK.NS", "UPL.NS", "BAJAJ-AUTO.NS",
    "HEROMOTOCO.NS", "SBILIFE.NS", "ICICIPRULI.NS", "TATASTEEL.NS", "BPCL.NS",
    "SHREECEM.NS", "CIPLA.NS", "LT.NS", "DMART.NS", "HDFCLIFE.NS"
]

FOREX = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCAD=X", "USDCHF=X",
    "AUDUSD=X", "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X"
]

COMMODITIES = [
    "GC=F", "SI=F", "CL=F", "NG=F"  # Gold, Silver, Oil, Natural Gas
]

CRYPTO = [
    "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "XRP-USD"
]

ALL_SYMBOLS = STOCKS + FOREX + COMMODITIES + CRYPTO

# ---------- TIMEFRAMES ----------
TIMEFRAMES = ["5m", "15m", "30m", "1h", "2h", "4h", "1d", "1wk"]

# ---------- SUPPLY-DEMAND DETECTION LOGIC ----------
def get_candle_body(o, c, h, l):
    body = abs(c - o)
    total_range = h - l if h - l > 0 else 1
    body_percent = (body / total_range) * 100
    return {
        'body': body,
        'body_percent': body_percent,
        'is_bullish': c > o,
        'is_bearish': c < o,
        'open': o, 'close': c, 'high': h, 'low': l
    }

def is_explosive(candle, min_body_percent=60):
    return candle['body_percent'] >= min_body_percent

def is_base_candle(candle, legin_candle, max_body_ratio=0.5):
    return candle['body'] <= (legin_candle['body'] * max_body_ratio)

def detect_supply_demand_zones(df, timeframe_name):
    zones = []
    if len(df) < 10:
        return zones
    
    for i in range(2, len(df) - 3):
        legin = get_candle_body(
            df['Open'].iloc[i], df['Close'].iloc[i],
            df['High'].iloc[i], df['Low'].iloc[i]
        )
        
        if not is_explosive(legin):
            continue
        
        for base_end in range(i+1, min(i+4, len(df)-2)):
            valid_base = True
            for k in range(i+1, base_end+1):
                base_cdl = get_candle_body(
                    df['Open'].iloc[k], df['Close'].iloc[k],
                    df['High'].iloc[k], df['Low'].iloc[k]
                )
                if not is_base_candle(base_cdl, legin):
                    valid_base = False
                    break
            
            if not valid_base:
                continue
            
            legout_start = base_end + 1
            legout_candles = []
            
            for k in range(legout_start, min(legout_start+5, len(df))):
                legout_cdl = get_candle_body(
                    df['Open'].iloc[k], df['Close'].iloc[k],
                    df['High'].iloc[k], df['Low'].iloc[k]
                )
                if legout_cdl['body'] < legin['body']:
                    break
                legout_candles.append(legout_cdl)
            
            if len(legout_candles) >= 1:
                legin_color = "RED" if legin['is_bearish'] else "GREEN"
                legout_color = "RED" if legout_candles[-1]['is_bearish'] else "GREEN"
                
                if legin_color == "GREEN" and legout_color == "GREEN":
                    pattern, trade = "📗 RISE-BASE-RISE (GBG)", "BUY ✅"
                elif legin_color == "GREEN" and legout_color == "RED":
                    pattern, trade = "📕 RISE-BASE-DROP (GBR)", "SELL 🔻"
                elif legin_color == "RED" and legout_color == "RED":
                    pattern, trade = "📕 DROP-BASE-DROP (RBR)", "SELL 🔻"
                else:
                    pattern, trade = "📗 DROP-BASE-RISE (RBG)", "BUY ✅"
                
                zones.append({
                    'timeframe': timeframe_name,
                    'pattern': pattern,
                    'trade': trade,
                    'zone_low': min(df['Low'].iloc[i:base_end+1]),
                    'zone_high': max(df['High'].iloc[i:base_end+1]),
                    'legin_body_pct': round(legin['body_percent'], 1),
                    'strength': round(legout_candles[-1]['body'] / legin['body'], 2)
                })
    
    return zones

def fetch_data(symbol, timeframe):
    try:
        interval_map = {
            "5m": "5m",
            "15m": "15m", 
            "30m": "30m",
            "1h": "60m",
            "2h": "60m",
            "4h": "60m",
            "1d": "1d",
            "1wk": "1wk"
        }
        period_map = {
            "5m": "5d",
            "15m": "10d",
            "30m": "10d",
            "1h": "20d",
            "2h": "20d",
            "4h": "30d",
            "1d": "3mo",
            "1wk": "6mo"
        }
        
        interval = interval_map.get(timeframe, "1d")
        period = period_map.get(timeframe, "5d")
        
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if not df.empty and len(df) > 10:
            return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None

def scan_and_alert():
    print("🤖 Supply-Demand Bot Started at", datetime.now())
    print("📊 Total Symbols:", len(ALL_SYMBOLS))
    print("⏰ Timeframes:", TIMEFRAMES)
    
    alert_history = {}
    cycle_count = 0
    
    while True:
        cycle_count += 1
        print(f"\n🔄 Scan Cycle #{cycle_count} at {datetime.now()}")
        
        for symbol in ALL_SYMBOLS:
            for timeframe in TIMEFRAMES:
                try:
                    print(f"  Scanning {symbol} on {timeframe}...")
                    
                    df = fetch_data(symbol, timeframe)
                    if df is None or df.empty:
                        print(f"    ❌ No data for {symbol}")
                        continue
                    
                    zones = detect_supply_demand_zones(df, timeframe)
                    current_price = df['Close'].iloc[-1]
                    
                    for zone in zones:
                        alert_key = f"{symbol}_{timeframe}_{zone['zone_low']}_{zone['zone_high']}"
                        
                        if alert_key not in alert_history:
                            msg = f"""
🚨 *SUPPLY-DEMAND ZONE ALERT* 🚨

📊 *Symbol:* `{symbol}`
⏰ *Timeframe:* `{timeframe}`
💰 *Price:* ₹{current_price:.2f}

📐 *Pattern:* {zone['pattern']}
🎯 *Action:* {zone['trade']}

📈 *Zone:* ₹{zone['zone_low']:.2f} - ₹{zone['zone_high']:.2f}
⚡ *Strength:* {zone['strength']}x

⏰ *Time:* {datetime.now().strftime('%H:%M:%S')}
"""
                            try:
                                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                                print(f"    ✅ Alert sent for {symbol} on {timeframe}")
                                alert_history[alert_key] = datetime.now()
                            except Exception as e:
                                print(f"    ❌ Telegram error: {e}")
                    
                except Exception as e:
                    print(f"    ❌ Error: {e}")
                
                time.sleep(0.5)  # Rate limit avoid karne ke liye
            
            time.sleep(1)  # Symbol ke beech mein gap
        
        print(f"\n⏳ Cycle complete. Waiting 60 seconds...")
        time.sleep(60)

# ---------- START ----------
if __name__ == "__main__":
    print("🚀 Starting Trading Bot...")
    
    # Start Flask server in background
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Wait a bit for Flask to start
    time.sleep(2)
    
    # Start trading bot
    print("🔁 Calling scan_and_alert() function...")
    try:
        scan_and_alert()
    except Exception as e:
        print(f"❌ Error in scan_and_alert: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait a bit for Flask to start
    time.sleep(2)
    
    # Start trading bot
    scan_and_alert()
