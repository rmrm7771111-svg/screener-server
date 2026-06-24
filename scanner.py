import os
import requests
import time
import threading
from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# ====================================================================
#  🧪 شروط فلاتر مفتوحة وموسعة جداً للتجربة والاختبار فقط 🧪
# ====================================================================
MIN_PRICE = 0.20            # الحد الأدنى 20 سنت (شرطك الأساسي)
MAX_PRICE = 9999.0          # تم إلغاء الحد الأعلى لتمرير أي سهم
MIN_GAP_PERCENT = 0.0       # تم إلغاء شرط الجاب (حتى لو صفر يمر)
MIN_VOLUME = 0              # تم إلغاء شرط الفوليوم اللحظي الأدنى
MAX_FLOAT = 999999999999    # تم إلغاء شرط الفلوت المنخفض تماماً
MIN_RVOL = 0.0              # تم إلغاء شرط الفوليوم النسبي
# ====================================================================

sent_alerts_prices = {}

def get_top_market_movers():
    """جلب قائمة أعلى 30 سهم حركة وصعوداً في كامل السوق الأمريكي لحظياً"""
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        params = {"scrIds": "day_gainers", "count": 30}
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, params=params, headers=headers).json()
        results = response.get('finance', {}).get('result', [{}])[0].get('quotes', [])
        return [stock['symbol'] for stock in results if 'symbol' in stock][:30]
    except:
        return []

def get_stock_metrics(ticker):
    """الفحص اللحظي المفتوح للتجربة خارج/أثناء أوقات السوق"""
    try:
        stock = yf.Ticker(ticker)
        # نطلب بيانات يومية لضمان جلب إغلاق أمس واليوم السابق حتى لو السوق مغلق
        hist = stock.history(period='5d', interval='1d')
        if len(hist) < 2: return None
            
        prev_close = hist['Close'].iloc[-2]
        current_price = hist['Close'].iloc[-1]
        current_volume = hist['Volume'].iloc[-1]
        
        info = stock.info
        share_float = info.get('floatShares', info.get('sharesOutstanding', 0))
        avg_volume_10d = info.get('averageVolume10days', info.get('averageVolume', 1))
        
        current_change = round(((current_price - prev_close) / prev_close) * 100, 2)
        rvol = round(current_volume / avg_volume_10d, 2) if avg_volume_10d else 1.0

        return {
            'price': round(current_price, 2),
            'gap': current_change, 
            'change': current_change,
            'float': share_float,
            'volume': current_volume,
            'rvol': rvol
        }
    except:
        return None

def send_telegram_alert(ticker, data, alert_type="إشارة جديدة"):
    """تنسيق التنبيه وإرساله فوراً إلى تليجرام"""
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] else "غير متوفر"
    icon = "🧪"
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"

    message = (
        f"{icon} **{alert_type} (وضع التجربة)!** {icon}\n\n"
        f"🎫 **السهم المستهدف:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر الحالي:** ${data['price']}\n"
        f"📈 **التغير:** {data['change']}%\n"
        f"🔥 **الفوليوم النسبي (RVOL):** {data['rvol']}x\n"
        f"📊 **الفوليوم الحجمي:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

def send_live_summary_to_user():
    """توليد ملخص لحظي موسع وشامل لأي سهم فوق 20 سنت للتأكد من ياهو فاينانس"""
    top_tickers = get_top_market_movers()
    message = "📋 **حصاد تجريبي لكافة الأسهم النشطة حالياً فوق 20 سنت:**\n\n"
    valid_stocks_count = 0
    
    for ticker in top_tickers:
        data = get_stock_metrics(ticker)
        if data:
            # فلتر السعر فقط بناءً على طلبك للتجربة
            if data['price'] >= MIN_PRICE:
                yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
                float_formatted = f"{round(data['float'] / 1000000, 1)}M" if data['float'] else "غير متوفر"
                valid_stocks_count += 1
                message += f"{valid_stocks_count}. [{ticker}]({yahoo_url}) ✅\n"
                message += f"   • السعر: `${data['price']}` | التغير: `{data['change']}%`\n"
                message += f"   • الـ RVOL: `{data['rvol']}x` | الفلوت: `{float_formatted}`\n\n"
            
    if valid_stocks_count == 0:
        message = "📋 **ملخص الحركة الحالية:**\n\nلم يتم العثور على أي أسهم نشطة فوق 20 سنت حالياً."
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
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
    return "Test Mode (Price > 0.20 Only) is Active!"

def run_scanner_loop():
    """الحلقة المستمرة للفحص التلقائي اللحظي"""
    print("⚡ تم تشغيل خيط الفحص التلقائي التجريبي...")
    while True:
        time.sleep(60)

scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
scanner_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
