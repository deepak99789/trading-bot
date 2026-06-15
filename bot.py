import yfinance as yf
import pandas as pd
import telebot
import time
import os
from datetime import datetime
from flask import Flask
import threading

# ---------- TELEGRAM SETUP ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ---------- FLASK APP ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Trading Bot is Alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ---------- ASSETS ----------
STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "MARUTI.NS", "TITAN.NS", "WIPRO.NS", "SUNPHARMA.NS",
    "ASIANPAINT.NS", "HCLTECH.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
    "M&M.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "JSWSTEEL.NS", "TECHM.NS",
    "COALINDIA.NS", "GRASIM.NS", "DIVISLAB.NS", "DRREDDY.NS", "ADANIPORTS.NS",
    "ADANIENT.NS", "BRITANNIA.NS", "EICHERMOT.NS", "HINDALCO.NS", "INDUSINDBK.NS",
    "UPL.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "SBILIFE.NS", "TATASTEEL.NS",
    "BPCL.NS", "LT.NS", "CIPLA.NS", "HDFCLIFE.NS"
]

FOREX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCAD=X"]
COMMODITIES = ["GC=F", "SI=F", "CL=F"]
CRYPTO = ["BTC-USD", "ETH-USD"]

ALL_SYMBOLS = STOCKS + FOREX + COMMODITIES + CRYPTO
TIMEFRAMES = ["5m", "15m", "30m", "1h", "2h", "4h", "1d"]

# ---------- SUPPLY-DEMAND FUNCTIONS ----------
def get_candle_body(o, c, h, l):
    body = abs(c - o)
    total_range = h - l if h - l > 0 else 1
    body_percent = (body / total_range) * 100
    return {
        'body': body, 'body_percent': body_percent,
        'is_bullish': c > o, 'is_bearish': c < o,
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
                    pattern, trade = "📗 RISE-BASE-RISE", "BUY ✅"
                elif legin_color == "GREEN" and legout_color == "RED":
                    pattern, trade = "📕 RISE-BASE-DROP", "SELL 🔻"
                elif legin_color == "RED" and legout_color == "RED":
                    pattern, trade = "📕 DROP-BASE-DROP", "SELL 🔻"
                else:
                    pattern, trade = "📗 DROP-BASE-RISE", "BUY ✅"
                
                zones.append({
                    'timeframe': timeframe_name, 'pattern': pattern, 'trade': trade,
                    'zone_low': min(df['Low'].iloc[i:base_end+1]),
                    'zone_high': max(df['High'].iloc[i:base_end+1]),
                    'strength': round(legout_candles[-1]['body'] / legin['body'], 2)
                })
    
    return zones

def fetch_data(symbol, timeframe):
    try:
        interval_map = {
            "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "60m", "2h": "60m", "4h": "60m", "1d": "1d"
        }
        period_map = {
            "5m": "2d", "15m": "5d", "30m": "5d",
            "1h": "10d", "2h": "10d", "4h": "20d", "1d": "3mo"
        }
        interval = interval_map.get(timeframe, "1d")
        period = period_map.get(timeframe, "5d")
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if not df.empty and len(df) > 10:
            return df
    except:
        pass
    return None

def scan_and_alert():
    print("🤖 Supply-Demand Bot Started at", datetime.now())
    print("📊 Total Symbols:", len(ALL_SYMBOLS))
    print("⏰ Timeframes:", TIMEFRAMES)
    
    alert_history = {}
    cycle = 0
    
    while True:
        cycle += 1
        print(f"\n🔄 Cycle #{cycle} at {datetime.now()}")
        
        for symbol in ALL_SYMBOLS:
            for tf in TIMEFRAMES:
                try:
                    df = fetch_data(symbol, tf)
                    if df is None:
                        continue
                    
                    zones = detect_supply_demand_zones(df, tf)
                    price = df['Close'].iloc[-1]
                    
                    for z in zones:
                        key = f"{symbol}_{tf}_{z['zone_low']}_{z['zone_high']}"
                        if key not in alert_history:
                            msg = f"""🚨 SUPPLY-DEMAND ALERT 🚨

📊 {symbol} | {tf}
💰 ₹{price:.2f}
📐 {z['pattern']}
🎯 {z['trade']}
📈 Zone: ₹{z['zone_low']:.2f} - ₹{z['zone_high']:.2f}
⚡ Strength: {z['strength']}x"""
                            bot.send_message(CHAT_ID, msg)
                            print(f"  ✅ Alert: {symbol} {tf}")
                            alert_history[key] = datetime.now()
                            time.sleep(1)
                except Exception as e:
                    print(f"  Error {symbol}: {e}")
                time.sleep(0.3)
            time.sleep(0.5)
        
        print(f"⏳ Cycle done. Waiting 60 sec...")
        time.sleep(60)

# ---------- START ----------
if __name__ == "__main__":
    print("🚀 Starting Trading Bot...")
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    time.sleep(2)
    print("🔁 Starting scan_and_alert...")
    scan_and_alert()
