from flask import Flask
import requests
import os
import threading
import time

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SYMBOLS = ["AMC","GME","PLTR","SOFI","RIVN","HOOD","AI","BBAI","IONQ","MARA"]

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

def scan():
    global last_alert

    for s in SYMBOLS:
        try:
            d = get(s)

            price = d["c"]
            prev = d["pc"]

            if prev == 0:
                continue

            change = ((price - prev) / prev) * 100

            if change >= 10:

                now = time.time()

                if s in last_alert and now - last_alert[s] < 300:
                    continue

                last_alert[s] = now

                send(f"🚀 BREAKOUT\n{s}\n+{round(change,2)}%")

        except:
            continue

def loop():
    while True:
        scan()
        time.sleep(60)

@app.route("/")
def home():
    return {"status": "running"}

threading.Thread(target=loop, daemon=True).start()
