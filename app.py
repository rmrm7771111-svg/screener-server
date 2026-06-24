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

# Telegram sender
def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )

# Market data
def get(symbol):
    return requests.get(
        "https://finnhub.io/api/v1/quote",
        params={"symbol": symbol, "token": API_KEY}
    ).json()

# Market time (4AM - 8PM EST simplified)
def market_open():
    hour = (datetime.utcnow().hour - 5) % 24
    return 4 <= hour <= 20

# Full scanner
def scan():
    global last_alert

    if not market_open():
        return

    symbols_url = "https://finnhub.io/api/v1/stock/symbol"
    r = requests.get(symbols_url, params={
        "exchange": "US",
        "token": API_KEY
    })

    symbols = [x["symbol"] for x in r.json()]

    for s in symbols:
        try:
            d = get(s)

            price = d.get("c", 0)
            open_price = d.get("o", 0)
            volume = d.get("v", 0)
            avg_volume = d.get("v", 1)

            # ===== Filters =====
            if price < 0.30:
                continue

            if open_price == 0:
                continue

            # Momentum (from open)
            momentum = ((price - open_price) / open_price) * 100

            # Relative Volume
            rvol = volume / avg_volume if avg_volume > 0 else 0

            # Score
            score = momentum * rvol

            # Entry conditions
            if rvol < 2:
                continue

            if momentum < 5:
                continue

            if score < 10:
                continue

            now = time.time()

            if s in last_alert and now - last_alert[s] < 300:
                continue

            last_alert[s] = now

            send(
                f"🚀 MOMENTUM BREAKOUT\n"
                f"{s}\n"
                f"Price: {price}\n"
                f"Momentum: {round(momentum,2)}%\n"
                f"RVOL: {round(rvol,2)}\n"
                f"Score: {round(score,2)}"
            )

        except:
            continue

# Loop
def loop():
    while True:
        scan()
        time.sleep(60)

@app.route("/")
def home():
    return {"status": "quant scanner running"}

threading.Thread(target=loop, daemon=True).start()
