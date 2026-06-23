from flask import Flask
import requests
import os
import threading
import time

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

last_alert_time = {}

def send_telegram(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )

# جلب كل الأسهم من السوق (مرة واحدة)
def get_all_symbols():
    url = "https://finnhub.io/api/v1/stock/symbol"
    r = requests.get(url, params={
        "exchange": "US",
        "token": API_KEY
    })
    data = r.json()

    # ناخذ الرموز فقط
    return [x["symbol"] for x in data if "symbol" in x]

SYMBOLS = get_all_symbols()

def get_quote(symbol):
    url = "https://finnhub.io/api/v1/quote"
    r = requests.get(url, params={
        "symbol": symbol,
        "token": API_KEY
    })
    return r.json()

def scan():
    global last_alert_time

    for symbol in SYMBOLS:
        try:
            d = get_quote(symbol)

            price = d.get("c", 0)
            prev = d.get("pc", 0)

            if prev == 0:
                continue

            change = ((price - prev) / prev) * 100

            # شرط المومنتوم
            if change >= 10:

                now = time.time()

                if symbol in last_alert_time and now - last_alert_time[symbol] < 300:
                    continue

                last_alert_time[symbol] = now

                send_telegram(f"🚀 BREAKOUT\n{symbol}\n+{round(change,2)}%")

        except:
            continue

def loop():
    while True:
        scan()
        time.sleep(60)

@app.route("/")
def home():
    return {"status": "full market scanner running"}

threading.Thread(target=loop, daemon=True).start()
