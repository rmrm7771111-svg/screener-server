from flask import Flask
import threading
import time
import requests
import os

app = Flask(__name__)

# =====================
# ENV VARIABLES
# =====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

last_alert = {}

# =====================
# WEB ENDPOINT
# =====================
@app.route("/")
def home():
    return "Scanner is running"

# =====================
# TELEGRAM
# =====================
def send(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_TOKEN or CHAT_ID")
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

# =====================
# SYMBOLS
# =====================
def get_symbols():
    return ["AAPL", "TSLA", "AMC", "NVDA", "GME"]

# =====================
# MARKET DATA
# استبدلها لاحقاً بالـ API الحقيقي
# =====================
def get_quote(symbol):
    return {
        "c": 10,
        "o": 9,
        "pc": 9.5,
        "v": 2000000
    }

def get_profile(symbol):
    return {
        "shareOutstanding": 50000000
    }

# =====================
# SCANNER
# =====================
def scan():
    global last_alert

    symbols = get_symbols()

    for s in symbols:
        try:
            q = get_quote(s)
            p = get_profile(s)

            price = q.get("c", 0)
            open_price = q.get("o", 0)
            prev_close = q.get("pc", 0)
            volume = q.get("v", 0)
            float_shares = p.get("shareOutstanding", 0)

            if price < 0.30:
                continue

            if open_price == 0 or prev_close == 0:
                continue

            momentum = ((price - open_price) / open_price) * 100
            gap = ((open_price - prev_close) / prev_close) * 100
            spike = ((price - prev_close) / prev_close) * 100

            # مؤقت إلى أن تضيف API حقيقي
            vol_pressure = 2

            score = (
                momentum * 0.3 +
                vol_pressure * 10 +
                spike * 0.2
            )

            now = time.time()

            if s in last_alert and now - last_alert[s] < 300:
                continue

            # BREAKOUT
            if momentum >= 5 and score >= 15:

                last_alert[s] = now

                send(
                    f"🏦 BREAKOUT\n"
                    f"{s}\n"
                    f"Price: {price}\n"
                    f"Momentum: {round(momentum,2)}%\n"
                    f"Volume: {volume}\n"
                    f"Float: {float_shares}\n"
                    f"RVOL: {round(vol_pressure,2)}\n"
                    f"Score: {round(score,2)}"
                )

            # GAP
            elif gap >= 4:

                last_alert[s] = now

                send(
                    f"⚡ GAP\n"
                    f"{s}\n"
                    f"Gap: {round(gap,2)}%\n"
                    f"Volume: {volume}\n"
                    f"Float: {float_shares}"
                )

            # SPIKE
            elif spike >= 8:

                last_alert[s] = now

                send(
                    f"⛔ SPIKE\n"
                    f"{s}\n"
                    f"Move: {round(spike,2)}%\n"
                    f"Volume: {volume}\n"
                    f"Float: {float_shares}"
                )

        except Exception as e:
            print(e)

# =====================
# LOOP
# =====================
def scanner_loop():
    while True:
        scan()
        time.sleep(60)

# =====================
# START BACKGROUND THREAD
# =====================
threading.Thread(
    target=scanner_loop,
    daemon=True
).start()
