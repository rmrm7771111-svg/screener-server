from flask import Flask
import requests
import os
import threading
import time
from datetime import datetime, time as dtime
import pytz

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

def get_all_symbols():
    url = "https://finnhub.io/api/v1/stock/symbol"
    r = requests.get(url, params={
        "exchange": "US",
        "token": API_KEY
    })
    data = r.json()

    return [x["symbol"] for x in data if "symbol" in x]

SYMBOLS = get_all_symbols()

def get_quote(symbol):
    url = "https://finnhub.io/api/v1/quote"
    return requests.get(url, params={
        "symbol": symbol,
        "token": API_KEY
    }).json()

def market_open():
    tz = pytz.timezone("US/Eastern")
    now = datetime.now(tz).time()
    return dtime(4, 0) <= now <= dtime(20, 0)

def scan():
    global last_alert

    if not market_open():
        return

    for s in SYMBOLS:
        try:
            d = get_quote(s)

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
    return {"status": "FULL MARKET SCANNER ACTIVE"}

threading.Thread(target=loop, daemon=True).start()
