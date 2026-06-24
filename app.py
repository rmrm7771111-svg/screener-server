from flask import Flask
import requests
import threading
import time
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

last_alert = {}
symbols_cache = []
last_symbols_update = 0


@app.route("/")
def home():
    return "Scanner Running"


def send(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": msg
            },
            timeout=10
        )
    except Exception as e:
        print(e)


def get_symbols():
    global symbols_cache, last_symbols_update

    # تحديث القائمة مرة كل 24 ساعة فقط
    if time.time() - last_symbols_update < 86400 and symbols_cache:
        return symbols_cache

    try:
        url = (
            "https://finnhub.io/api/v1/stock/symbol"
            f"?exchange=US&token={FINNHUB_API_KEY}"
        )

        data = requests.get(url, timeout=30).json()

        symbols = []

        for stock in data:
            symbol = stock.get("symbol", "")

            if (
                symbol
                and "." not in symbol
                and "^" not in symbol
                and len(symbol) <= 5
            ):
                symbols.append(symbol)

        symbols_cache = symbols
        last_symbols_update = time.time()

        print(f"Loaded {len(symbols)} symbols")

        return symbols

    except Exception as e:
        print(e)
        return symbols_cache


def get_quote(symbol):
    try:
        url = (
            f"https://finnhub.io/api/v1/quote"
            f"?symbol={symbol}&token={FINNHUB_API_KEY}"
        )

        return requests.get(url, timeout=10).json()

    except:
        return {}


def get_profile(symbol):
    try:
        url = (
            f"https://finnhub.io/api/v1/stock/profile2"
            f"?symbol={symbol}&token={FINNHUB_API_KEY}"
        )

        return requests.get(url, timeout=10).json()

    except:
        return {}


def scan():
    global last_alert

    symbols = get_symbols()

    # الخطة المجانية لا تتحمل كل السوق دفعة واحدة
    # نفحص أول 300 سهم كل دورة
    for s in symbols[:300]:

        try:
            q = get_quote(s)

            price = q.get("c", 0)
            open_price = q.get("o", 0)
            prev_close = q.get("pc", 0)

            if price < 0.30:
                continue

            if open_price == 0 or prev_close == 0:
                continue

            momentum = ((price - open_price) / open_price) * 100
            spike = ((price - prev_close) / prev_close) * 100

            now = time.time()

            if s in last_alert and now - last_alert[s] < 300:
                continue

            if momentum >= 10:

                profile = get_profile(s)

                volume = q.get("v", 0)
                float_shares = profile.get("shareOutstanding", "N/A")

                last_alert[s] = now

                send(
                    f"🏦 BREAKOUT\n\n"
                    f"{s}\n"
                    f"Price: ${price}\n"
                    f"Momentum: {round(momentum,2)}%\n"
                    f"Spike: {round(spike,2)}%\n"
                    f"Volume: {volume}\n"
                    f"Float: {float_shares}"
                )

            time.sleep(1)  # لتخفيف ضغط API

        except Exception as e:
            print(e)


def scanner_loop():
    while True:
        scan()
        time.sleep(60)


threading.Thread(
    target=scanner_loop,
    daemon=True
).start()
