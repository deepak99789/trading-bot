import yfinance as yf
import telebot
import time
import os
from datetime import datetime
from flask import Flask
import threading

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Alive"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

STOCKS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
ALL_SYMBOLS = STOCKS
TIMEFRAMES = ["5m", "15m", "1h"]

def get_price(df):
    """Safely extract price as float"""
    val = df['Close'].iloc[-1]
    if hasattr(val, 'iloc'):
        val = val.iloc[0]
    return float(val)

def get_low(df):
    val = df['Low'].iloc[-1]
    if hasattr(val, 'iloc'):
        val = val.iloc[0]
    return float(val)

def get_high(df):
    val = df['High'].iloc[-1]
    if hasattr(val, 'iloc'):
        val = val.iloc[0]
    return float(val)

def check_supply_demand(df):
    if len(df) < 20:
        return None
    
    try:
        last_close = get_price(df)
        prev_close = get_price(df.iloc[:-1])
        last_low = get_low(df)
        last_high = get_high(df)
        
        recent_lows = df['Low'].tail(5).min()
        recent_highs = df['High'].tail(5).max()
        
        if hasattr(recent_lows, 'iloc'):
            recent_lows = float(recent_lows.iloc[0])
        if hasattr(recent_highs, 'iloc'):
            recent_highs = float(recent_highs.iloc[0])
        
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
    except:
        pass
    
    return None

def fetch_data(symbol, timeframe):
    try:
        int_map = {"5m": "5m", "15m": "15m", "1h": "60m"}
        per_map = {"5m": "5d", "15m": "10d", "1h": "20d"}
        df = yf.download(symbol, period=per_map[timeframe], interval=int_map[timeframe], progress=False)
        if df is not None and not df.empty and len(df) > 20:
            return df
    except:
        pass
    return None

def scan():
    print("=" * 50)
    print("🤖 SUPPLY-DEMAND BOT STARTED")
    print("=" * 50)
    print(f"Symbols: {len(ALL_SYMBOLS)}")
    print(f"Timeframes: {TIMEFRAMES}")
    print("=" * 50)
    
    sent = {}
    cycle = 0
    
    while True:
        cycle += 1
        print(f"\n[CYCLE {cycle}] {datetime.now().strftime('%H:%M:%S')}")
        
        for sym in ALL_SYMBOLS:
            for tf in TIMEFRAMES:
                print(f"  {sym} [{tf}]")
                df = fetch_data(sym, tf)
                if df is None:
                    print("    No data")
                    continue
                
                try:
                    price = get_price(df)
                    print(f"    Candles: {len(df)} | Price: {price:.2f}")
                except:
                    print("    Price error")
                    continue
                
                zone = check_supply_demand(df)
                
                if zone:
                    key = f"{sym}_{tf}_{zone['zone_low']:.2f}"
                    if key not in sent:
                        msg = f"""🚨 ALERT 🚨

{sym} | {tf}
Price: {zone['price']:.2f}
{zone['type']}
Action: {zone['action']}
Zone: {zone['zone_low']:.2f} - {zone['zone_high']:.2f}"""
                        try:
                            bot.send_message(CHAT_ID, msg)
                            print(f"    >>> ALERT SENT! <<<")
                            sent[key] = True
                        except Exception as e:
                            print(f"    Telegram error: {e}")
                else:
                    print("    No zone")
                
                time.sleep(1)
            time.sleep(1)
        
        print(f"\nCycle {cycle} complete. Waiting 60 sec...")
        time.sleep(60)

if __name__ == "__main__":
    print("STARTING...")
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    time.sleep(2)
    print("SCANNING STARTED...")
    scan()
