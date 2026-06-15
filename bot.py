import yfinance as yf
import telebot
import time
import os
from datetime import datetime
from flask import Flask
import threading

# ---------- TELEGRAM ----------
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
bot = telebot.TeleBot(TOKEN)

# ---------- FLASK ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Alive"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ---------- SYMBOLS ----------
STOCKS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
ALL_SYMBOLS = STOCKS
TIMEFRAMES = ["5m", "15m", "1h"]

# ---------- SUPPLY DEMAND FUNCTION ----------
def check_supply_demand(df, symbol, timeframe):
    if len(df) < 20:
        return None
    
    last_high = df['High'].iloc[-1]
    last_low = df['Low'].iloc[-1]
    last_close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    
    recent_lows = df['Low'].tail(5).min()
    recent_highs = df['High'].tail(5).max()
    
    if last_close > prev_close * 1.01 and last_low <= recent_lows * 1.002:
        return {
            'type': 'DEMAND (BUY ZONE)',
            'action': 'BUY',
            'zone_low': recent_lows,
            'zone_high': recent_lows * 1.01,
            'price': last_close
        }
    
    if last_close < prev_close * 0.99 and last_high >= recent_highs * 0.998:
        return {
            'type': 'SUPPLY (SELL ZONE)',
            'action': 'SELL',
            'zone_low': recent_highs * 0.99,
            'zone_high': recent_highs,
            'price': last_close
        }
    
    return None

def fetch_data(symbol, timeframe):
    try:
        int_map = {"5m": "5m", "15m": "15m", "1h": "60m"}
        per_map = {"5m": "5d", "15m": "10d", "1h": "20d"}
        df = yf.download(symbol, period=per_map[timeframe], interval=int_map[timeframe], progress=False)
        if not df.empty and len(df) > 20:
            return df
    except Exception as e:
        print(f"  Error: {e}")
    return None

# ---------- MAIN SCANNER ----------
def scan():
    print("=" * 50)
    print("🤖 SUPPLY-DEMAND BOT STARTED")
    print("=" * 50)
    print(f"📊 Symbols: {len(ALL_SYMBOLS)}")
    print(f"⏰ Timeframes: {TIMEFRAMES}")
    print("=" * 50)
    
    sent_alerts = {}
    cycle = 0
    
    while True:
        cycle += 1
        print(f"\n🔄 CYCLE #{cycle} - {datetime.now().strftime('%H:%M:%S')}")
        
        for symbol in ALL_SYMBOLS:
            for tf in TIMEFRAMES:
                print(f"  📍 {symbol} [{tf}]")
                df = fetch_data(symbol, tf)
                if df is None:
                    print(f"     ❌ No data")
                    continue
                
                # FIX: Convert to float
                current_price = float(df['Close'].iloc[-1])
                print(f"     ✅ {len(df)} candles | Price: {current_price:.2f}")
                
                zone = check_supply_demand(df, symbol, tf)
                
                if zone:
                    alert_key = f"{symbol}_{tf}_{zone['zone_low']:.2f}"
                    if alert_key not in sent_alerts:
                        # Convert zone values to float
                        zone_low = float(zone['zone_low'])
                        zone_high = float(zone['zone_high'])
                        zone_price = float(zone['price'])
                        
                        msg = f"""🚨 ALERT 🚨

{symbol} | {tf}
💰 ₹{zone_price:.2f}
📍 {zone['type']}
🎯 {zone['action']}
📈 Zone: ₹{zone_low:.2f} - ₹{zone_high:.2f}"""
                        try:
                            bot.send_message(CHAT_ID, msg)
                            print(f"     ✅ ALERT SENT!")
                            sent_alerts[alert_key] = True
                            time.sleep(2)
                        except Exception as e:
                            print(f"     ❌ Telegram error: {e}")
                else:
                    print(f"     ℹ️ No zone")
                
                time.sleep(1)
            time.sleep(1)
        
        print(f"\n⏳ Cycle #{cycle} complete. Waiting 60 sec...")
        time.sleep(60)

# ---------- START ----------
if __name__ == "__main__":
    print("🚀 STARTING...")
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    time.sleep(2)
    print("🔁 STARTING SCAN...")
    scan()
