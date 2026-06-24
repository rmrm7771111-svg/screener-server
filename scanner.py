import os
import requests
import time
import threading
from flask import Flask

# إعداد تطبيق الويب الوهمي لـ Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Scanner is running successfully!"

# قراءة مفاتيح الـ API السرية من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')

MIN_GAP_PERCENT = 3.0       
MIN_VOLUME = 100000         
MAX_FLOAT = 50000000        

def get_market_movers():
    try:
        response = requests.get(f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_API_KEY}").json()
        all_tickers = [item['symbol'] for item in response if item['type'] == 'Common Stock']
        return all_tickers
    except Exception as e:
        print(f"خطأ أثناء جلب قائمة السوق: {e}")
        return []

def get_stock_metrics(ticker):
    try:
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        quote_data = requests.get(quote_url).json()
        
        prev_close = quote_data.get('pc', 0)
        open_price = quote_data.get('o', 0)
        current_price = quote_data.get('c', 0)
        
        if prev_close == 0: return None
        
        gap_percent = ((open_price - prev_close) / prev_close) * 100
        current_change = ((current_price - prev_close) / prev_close) * 100

        basic_url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_API_KEY}"
        metric_data = requests.get(basic_url).json()
        
        metrics = metric_data.get('metric', {})
        share_float = metrics.get('shareOutstanding', 0) 
        volume = metrics.get('vAvg10D', 0) 

        return {
            'price': current_price,
            'gap': round(gap_percent, 2),
            'change': round(current_change, 2),
            'float': share_float,
            'volume': volume
        }
    except:
        return None

def send_telegram_alert(ticker, data):
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] else "غير متوفر"
    
    message = (
        f"🚨 **إشارة مومنتوم من كامل السوق!** 🚨\n\n"
        f"🎫 **السهم:** `{ticker}`\n"
        f"💵 **السعر الحالي:** ${data['price']}\n"
        f"📈 **الفجوة (Gap):** {data['gap']}%\n"
        f"🔄 **التغير الحالي:** {data['change']}%\n"
        f"📊 **متوسط الفوليوم:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except:
        pass

# دالة السكانر التي ستعمل في الخلفية بشكل مستقل
def run_scanner_loop():
    print("⚡ بدء الفحص المستمر للسوق في الخلفية...")
    while True:
        tickers = get_market_movers()
        for ticker in tickers:
            data = get_stock_metrics(ticker)
            if data:
                if abs(data['gap']) >= MIN_GAP_PERCENT and data['volume'] >= MIN_VOLUME:
                    if data['float'] and data['float'] <= MAX_FLOAT:
                        send_telegram_alert(ticker, data)
            time.sleep(0.5)
        time.sleep(10)

# تشغيل السكانر في خيط (Thread) منفصل حتى لا يعطل خادم الويب
scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
scanner_thread.start()

if __name__ == "__main__":
    # تشغيل السيرفر المحلي
    app.run(host="0.0.0.0", port=10000)
