from flask import Flask
import requests
import os
import threading
import time
from datetime import datetime

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

last_alert = {}

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )

def get(symbol):
    return requests.get(
        "https://finnhub.io/api/v1/quote",
        params={"symbol": symbol, "token": API_KEY}
    ).json()

# تشغيل 4AM - 8PM (يشمل pre + market + after)
def market_open():
    hour = (datetime.utcnow().hour - 4) % 24
    return 4 <= hour <= 20

def scan():
    global last_alert

    if not market_open():
        return

    symbols_url = "https://finnhub.io/api/v1/stock/symbol"
    r = requests.get(symbols_url, params={
        "exchange": "US",
        "token": API_KEY
    })

    symbols = [x["symbol"] for x in r.json() if "symbol" in x]

    for s in symbols:
        try:
            d = get(s)

            price = d.get("c", 0)
            prev = d.get("pc", 0)

            if price < 0.30:
                continue

            if prev == 0:
                continue

            change = ((price - prev) / prev) * 100

            if change >= 10:

                now = time.time()

                if s in last_alert and now - last_alert[s] < 300:
                    continue

                last_alert[s] = now

                send(f"🚀 BREAKOUT\n{s}\nPrice: {price}\n+{round(change,2)}%")

        except:
            continue

def loop():
    while True:
        scan()
        time.sleep(60)

@app.route("/")
def home():
    return {"status": "FULL MARKET SCANNER RUNNING"}

threading.Thread(target=loop, daemon=True).start()
