import yfinance as yf
import telebot
import time
import os
from datetime import datetime
from flask import Flask
import threading

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "apna_token_daal")
CHAT_ID = os.environ.get("CHAT_ID", "apna_chat_id_daal")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def scan():
    print("Bot started scanning...")
    count = 0
    while True:
        count += 1
        msg = f"✅ Bot is alive! Cycle #{count} at {datetime.now()}"
        print(msg)
        try:
            bot.send_message(CHAT_ID, msg)
        except:
            pass
        time.sleep(60)

if __name__ == "__main__":
    print("Starting...")
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    time.sleep(2)
    print("Calling scan...")
    scan()
