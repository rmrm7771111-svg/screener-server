import time
import requests

# =====================
# CONFIG
# =====================
TELEGRAM_TOKEN = "PUT_YOUR_TOKEN_HERE"
CHAT_ID = "PUT_YOUR_CHAT_ID_HERE"

last_alert = {}

# =====================
# TELEGRAM
# =====================
def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# =====================
# MARKET CHECK (placeholder)
# =====================
def market_open():
    return True

# =====================
# SYMBOLS
# =====================
def get_symbols():
    return ["AAPL", "TSLA", "AMC", "NVDA", "GME"]

# =====================
# QUOTE DATA (replace with real API)
# =====================
def get_quote(symbol):
    return {
        "c": 10,
        "o": 9,
        "pc": 9.5,
        "v": 2000000
    }

# =====================
# PROFILE DATA (FLOAT)
# =====================
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

            # =====================
            # MOVES
            # =====================
            momentum = ((price - open_price) / open_price) * 100
            gap = ((open_price - prev_close) / prev_close) * 100
            spike = ((price - prev_close) / prev_close) * 100

            # =====================
            # VOLUME PRESSURE
            # =====================
            vol_pressure = volume / (volume if volume > 0 else 1)

            # =====================
            # SCORE
            # =====================
            score = (
                momentum * 0.3 +
                vol_pressure * 10 +
                spike * 0.2
            )

            now = time.time()

            if s in last_alert and now - last_alert[s] < 300:
                continue

            # =====================
            # BREAKOUT
            # =====================
            if momentum >= 5 and vol_pressure >= 2 and score >= 15:

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

            # =====================
            # GAP
            # =====================
            elif gap >= 4:

                last_alert[s] = now

                send(
                    f"⚡ GAP\n"
                    f"{s}\n"
                    f"Gap: {round(gap,2)}%\n"
                    f"Volume: {volume}\n"
                    f"Float: {float_shares}\n"
                    f"RVOL: {round(vol_pressure,2)}"
                )

            # =====================
            # SPIKE
            # =====================
            elif spike >= 8:

                last_alert[s] = now

                send(
                    f"⛔ SPIKE\n"
                    f"{s}\n"
                    f"Move: {round(spike,2)}%\n"
                    f"Volume: {volume}\n"
                    f"Float: {float_shares}\n"
                    f"RVOL: {round(vol_pressure,2)}"
                )

        except:
            continue

# =====================
# LOOP
# =====================
def loop():
    print("Scanner running...")
    while True:
        scan()
        time.sleep(60)

# =====================
# START
# =====================
if __name__ == "__main__":
    loop()
