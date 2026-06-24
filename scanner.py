import os
import requests
import time
import threading
from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# لضمان عدم الحظر: الفلتر للسعر فقط فوق 20 سنت لـ 5 أسهم فقط
MIN_PRICE = 0.20

def get_top_market_movers():
    """جلب قائمة سريعة ومختصرة لأعلى الأسهم حركة"""
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        params = {"scrIds": "day_gainers", "count": 5}  # طلب 5 أسهم فقط للتجربة السريعة
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, params=params, headers=headers).json()
        results = response.get('finance', {}).get('result', [{}])[0].get('quotes', [])
        return [stock['symbol'] for stock in results if 'symbol' in stock][:5]
    except:
        # قائمة احتياطية شهيرة ورخيصة في حال تعطل الرابط اللحظي
        return ['MARA', 'RIOT', 'SOUN', 'PLTR', 'NIO']

def get_stock_metrics_fast(ticker):
    """جلب سعر السهم وإغلاقه الأخير بسرعة فائقة لتجنب الحظر"""
    try:
        stock = yf.Ticker(ticker)
        # نطلب بيانات يومين فقط لتقليل حجم البيانات المستهلكة
        hist = stock.history(period='2d', interval='1d')
        if hist.empty or len(hist) < 2: return None
            
        prev_close = hist['Close'].iloc[-2]
        current_price = hist['Close'].iloc[-1]
        current_change = round(((current_price - prev_close) / prev_close) * 100, 2)

        return {
            'price': round(current_price, 2),
            'change': current_change
        }
    except:
        return None

def send_live_summary_to_user():
    """توليد ملخص سريع جداً ومضمون بـ 5 أسهم فقط"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # إشعار سريع للمتداول
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": "⏳ جاري جلب 5 أسهم خفيفة للتجربة الحالية..."})
    except: pass

    top_tickers = get_top_market_movers()
    message = "📋 **ملخص التجربة الخفيفة (أسهم فوق 0.20$):**\n\n"
    valid_stocks_count = 0
    
    for ticker in top_tickers:
        data = get_stock_metrics_fast(ticker)
        if data and data['price'] >= MIN_PRICE:
            yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
            valid_stocks_count += 1
            message += f"{valid_stocks_count}. [{ticker}]({yahoo_url}) ✅\n"
            message += f"   • السعر: `${data['price']}` | التغير: `{data['change']}%`\n\n"
            
        # تأخير نصف ثانية بين السهم والآخر لحماية السيرفر من الحظر
        time.sleep(0.5)
            
    if valid_stocks_count == 0:
        message = "📋 **الملخص:**\n\nياهو فاينانس فرض حظراً مؤقتاً على السيرفر حالياً، انتظر دقائق ثم أرسل 'ملخص' مرة أخرى."
    else:
        message += f"🚀 نجحت التجربة والاتصال مستقر الحين!"
        
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        user_text = update["message"]["text"].strip().lower()
        if user_text in ["ملخص", "summary", "/summary"]:
            send_live_summary_to_user()
    return jsonify({"status": "success"})

@app.route('/')
def home():
    return "Fast Safe Scanner is Active!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
