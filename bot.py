import yfinance as yf
import pandas as pd
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

# ---------- SUPPLY DEMAND FUNCTIONS ----------
def get_candle_body(o, c, h, l):
    # Convert pandas Series to single values
    open_val = o.iloc[0] if hasattr(o, 'iloc') else o
    close_val = c.iloc[0] if hasattr(c, 'iloc') else c
    high_val = h.iloc[0] if hasattr(h, 'iloc') else h
    low_val = l.iloc[0] if hasattr(l, 'iloc') else l
    
    body = abs(close_val - open_val)
    total_range = high_val - low_val
    if total_range <= 0:
        total_range = 1
    
    body_percent = (body / total_range) * 100
    is_bullish = close_val > open_val
    
    return {
        'body': body,
        'body_percent': body_percent,
        'is_bullish': is_bullish
    }

def is_explosive(c):
    return c['body_percent'] >= 60

def is_base(c, legin):
    return c['body'] <= (legin['body'] * 0.5)

def detect_zones(df, tf):
    zones = []
    for i in range(2, len(df)-5):
        legin = get_candle_body(
            df['Open'].iloc[i], df['Close'].iloc[i],
            df['High'].iloc[i], df['Low'].iloc[i]
        )
        if not is_explosive(legin):
            continue
        for be in range(i+1, min(i+4, len(df)-2)):
            ok = True
            for k in range(i+1, be+1):
                base_cdl = get_candle_body(
                    df['Open'].iloc[k], df['Close'].iloc[k],
                    df['High'].iloc[k], df['Low'].iloc[k]
                )
                if not is_base(base_cdl, legin):
                    ok = False
                    break
            if not ok:
                continue
            lo_start = be+1
            lo_candles = []
            for k in range(lo_start, min(lo_start+5, len(df))):
                lo = get_candle_body(
                    df['Open'].iloc[k], df['Close'].iloc[k],
                    df['High'].iloc[k], df['Low'].iloc[k]
                )
                if lo['body'] < legin['body']:
                    break
                lo_candles.append(lo)
            if len(lo_candles) >= 1:
                legin_color = "GREEN" if legin['is_bullish'] else "RED"
                lo_color = "GREEN" if lo_candles[-1]['is_bullish'] else "RED"
                if legin_color == "GREEN" and lo_color == "GREEN":
                    trade = "BUY"
                    pattern = "RISE-BASE-RISE"
                elif legin_color == "GREEN" and lo_color == "RED":
                    trade = "SELL"
                    pattern = "RISE-BASE-DROP"
                elif legin_color == "RED" and lo_color == "RED":
                    trade = "SELL"
                    pattern = "DROP-BASE-DROP"
                else:
                    trade = "BUY"
                    pattern = "DROP-BASE-RISE"
                zones.append({
                    'symbol': 'test',
                    'tf': tf,
                    'trade': trade,
                    'pattern': pattern,
                    'low': min(df['Low'].iloc[i:be+1]),
                    'high': max(df['High'].iloc[i:be+1]),
                    'price': df['Close'].iloc[-1],
                    'strength': round(lo_candles[-1]['body']/legin['body'], 2)
                })
    return zones

def fetch(sym, tf):
    try:
        int_map = {"5m": "5m", "15m": "15m", "1h": "60m"}
        per_map = {"5m": "2d", "15m": "5d", "1h": "10d"}
        df = yf.download(sym, period=per_map[tf], interval=int_map[tf], progress=False)
        return df if not df.empty and len(df) > 10 else None
    except:
        return None

# ---------- MAIN SCANNER ----------
def scan():
    print("=" * 50)
    print("🤖 SUPPLY-DEMAND BOT STARTED")
    print("=" * 50)
    print(f"📊 Symbols: {len(ALL_SYMBOLS)}")
    print(f"⏰ Timeframes: {TIMEFRAMES}")
    print("=" * 50)
    
    sent = {}
    cycle = 0
    
    while True:
        cycle += 1
        print(f"\n🔄 CYCLE #{cycle} - {datetime.now().strftime('%H:%M:%S')}")
        
        for sym in ALL_SYMBOLS:
            for tf in TIMEFRAMES:
                print(f"  📍 {sym} [{tf}]")
                df = fetch(sym, tf)
                if df is None:
                    print(f"     ❌ No data")
                    continue
                print(f"     ✅ {len(df)} candles")
                zones = detect_zones(df, tf)
                for z in zones:
                    key = f"{sym}_{tf}_{z['low']}_{z['high']}"
                    if key not in sent:
                        # Convert to float values
                        try:
                            price_val = float(z['price'])
                        except:
                            price_val = float(z['price'].iloc[0]) if hasattr(z['price'], 'iloc') else 0
                        try:
                            low_val = float(z['low'])
                        except:
                            low_val = float(z['low'].iloc[0]) if hasattr(z['low'], 'iloc') else 0
                        try:
                            high_val = float(z['high'])
                        except:
                            high_val = float(z['high'].iloc[0]) if hasattr(z['high'], 'iloc') else 0
                        
                        msg = f"""🚨 ALERT 🚨

{sym} | {tf}
💰 ₹{price_val:.2f}
📐 {z['pattern']}
🎯 {z['trade']}
📈 Zone: ₹{low_val:.2f} - ₹{high_val:.2f}
⚡ Strength: {z['strength']}x"""
                        try:
                            bot.send_message(CHAT_ID, msg)
                            print(f"     ✅ ALERT SENT! {sym} {tf}")
                            sent[key] = True
                            time.sleep(1)
                        except Exception as e:
                            print(f"     ❌ Telegram error: {e}")
                time.sleep(0.5)
            time.sleep(0.5)
        
        print(f"\n⏳ Cycle #{cycle} complete. Waiting 60 sec...")
        time.sleep(60)

# ---------- START ----------
if __name__ == "__main__":
    print("🚀 STARTING...")
    
    # Flask thread
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    time.sleep(2)
    
    # Main scan
    print("🔁 CALLING SCAN FUNCTION...")
    scan()
