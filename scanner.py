import os
import requests
import time
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# قراءة المفاتيح السرية من Render لـ Finnhub والتليجرام
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FINNHUB_TOKEN = os.getenv('FINNHUB_TOKEN') # تأكد من وجود هذا المتغير في Render

# ====================================================================
#  ⚔️ الفلاتر الصارمة المعتمدة (طريقة المحارب + تعديلاتك) ⚔️
# ====================================================================
MIN_PRICE = 0.20            # الحد الأدنى 20 سنت
MAX_PRICE = 25.0            # الحد الأعلى 25 دولار
MIN_GAP_PERCENT = 4.0       # صعود قوي أعلى من 4%
# ====================================================================

# قاموس لحفظ الأسهم التي طابقت الشروط ورصدها البوت اليوم للملخص
daily_tracked_stocks = {}

def get_finnhub_quote(ticker):
    """جلب الأسعار والنسب اللحظية للسهم عبر Finnhub"""
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_TOKEN}"
        response = requests.get(url, timeout=10).json()
        
        current_price = response.get('c', 0)  # السعر الحالي
        prev_close = response.get('pc', 0)   # الإغلاق السابق
        
        if prev_close == 0: return None
        
        # حساب نسبة التغير الحالية
        change_percent = round(((current_price - prev_close) / prev_close) * 100, 2)
        
        return {
            'price': round(current_price, 2),
            'change': change_percent
        }
    except:
        return None

def send_telegram_alert(ticker, price, change, alert_type="إشارة جديدة"):
    """تنسيق التنبيه وإرساله إلى تليجرام"""
    icon = "⚔️" if alert_type == "إشارة جديدة" else "🚀"
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"

    message = (
        f"{icon} **{alert_type}!** {icon}\n\n"
        f"🎫 **السهم المستهدف:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر الحالي:** ${price}\n"
        f"🔄 **التحرك الإجمالي:** +{change}%\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

def send_finnhub_summary():
    """إرسال ملخص بالأسهم التي رصدها البوت وانطلقت اليوم عند طلبك"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    if not daily_tracked_stocks:
        message = "📋 **ملخص الحركة اليومية:**\n\nلا توجد أسهم انطبقت عليها الشروط الصارمة وتحركت حركات كبيرة اليوم حتى الآن."
    else:
        message = "📋 **ملخص حصاد اليوم للأسهم المشتعلة المكتشفة (Finnhub):**\n\n"
        # ترتيب الأسهم من الأعلى صعوداً
        sorted_stocks = sorted(daily_tracked_stocks.items(), key=lambda x: x[1]['change'], reverse=True)
        
        for index, (ticker, data) in enumerate(sorted_stocks, 1):
            yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
            message += f"{index}. [{ticker}]({yahoo_url}) 🔥\n"
            message += f"   • آخر سعر: `${data['price']}` | صعود محقق: `+{data['change']}%`\n\n"
            
        message += f"⏰ تم التحديث في: {time.strftime('%H:%M:%S')} EST"

    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        user_text = update["message"]["text"].strip().lower()
        
        # الاستماع لأمر الملخص بالعربي أو الإنجليزي
        if user_text in ["ملخص", "summary", "/summary"]:
            send_finnhub_summary()
            
    return jsonify({"status": "success"})

@app.route('/')
def home():
    return "Finnhub Interactive Scanner is Active and Running!"

def run_scanner_loop():
    """الحلقة المستمرة للفحص عبر قائمة أسهم المومنتوم النشطة باستخدام Finnhub"""
    print("⚡ تم تشغيل سكانر Finnhub التلقائي المعتمد...")
    
    # قائمة بأسهم الزخم السريعة المعتمدة للمراقبة المستمرة
    tickers_to_watch = ['MARA', 'RIOT', 'SOUN', 'PLTR', 'TSLA', 'NVDA', 'AMD', 'BABA', 'NIO', 'AAPL']
    
    while True:
        for ticker in tickers_to_watch:
            data = get_finnhub_quote(ticker)
            if data:
                price = data['price']
                change = data['change']
                
                # تطبيق الفلاتر الصارمة الخاصة بك
                if MIN_PRICE <= price <= MAX_PRICE and change >= MIN_GAP_PERCENT:
                    
                    # حفظ وتحديث بيانات السهم في الملخص اليومي بأعلى نسبة صعود
                    if ticker not in daily_tracked_stocks or change > daily_tracked_stocks[ticker]['change']:
                        daily_tracked_stocks[ticker] = {'price': price, 'change': change}
                    
                    # إرسال تنبيه فوري إذا كان السهم يرتد لأول مرة
                    if ticker not in daily_tracked_stocks or daily_tracked_stocks[ticker]['notified'] is False:
                        send_telegram_alert(ticker, price, change, alert_type="إشارة زَخَم Finnhub")
                        daily_tracked_stocks[ticker]['notified'] = True
                        
            time.sleep(1) # تأخير ثانية واحدة بين فحص كل سهم لتجنب الضغط
        time.sleep(60) # إعادة الفحص بالكامل كل دقيقة

# تشغيل السكانر في الخلفية
scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
scanner_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
