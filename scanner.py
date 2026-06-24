import os
import requests
import time
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# قراءة المفاتيح السرية من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FINNHUB_TOKEN = os.getenv('FINNHUB_TOKEN')

# ====================================================================
#  ⚔️ الفلاتر الصارمة المعتمدة كاملة (طريقة المحارب) ⚔️
# ====================================================================
MIN_PRICE = 0.20            
MAX_PRICE = 25.0            
MIN_GAP_PERCENT = 4.0       
MAX_FLOAT = 50000000        # فلوت أقل من 50 مليون
MIN_RVOL = 2.0              # فوليوم نسبي أعلى من 2x (سيولة حيتان)
# ====================================================================

daily_tracked_stocks = {}

def get_stock_details_finnhub(ticker):
    """جلب السعر، التغير، الهاي، اللو، الفوليوم، الفلوت، وحساب الـ RVOL"""
    try:
        # 1. جلب الأسعار والسيولة اللحظية (الهاي واللو والفوليوم)
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_TOKEN}"
        quote_res = requests.get(quote_url, timeout=10).json()
        
        current_price = quote_res.get('c', 0)
        prev_close = quote_res.get('pc', 0)
        high_price = quote_res.get('h', 0)   # أعلى سعر اليوم (High)
        low_price = quote_res.get('l', 0)    # أدنى سعر اليوم (Low)
        volume = quote_res.get('v', 0)        # الفوليوم اللحظي الحالي
        
        if prev_close == 0: return None
        change_percent = round(((current_price - prev_close) / prev_close) * 100, 2)
        
        # 2. جلب الفلوت ومتوسط الفوليوم (بيانات الشركة الأساسية)
        profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_TOKEN}"
        profile_res = requests.get(profile_url, timeout=10).json()
        shares_outstanding = profile_res.get('shareOutstanding', 0) * 1000000
        
        # جلب متوسط الفوليوم لـ 10 أيام من المؤشرات المالية لحساب الـ RVOL
        metric_url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_TOKEN}"
        metric_res = requests.get(metric_url, timeout=10).json()
        avg_volume_10d = metric_res.get('metric', {}).get('vVolume10D', 0)
        
        # حساب الفوليوم النسبي (RVOL)
        if avg_volume_10d and avg_volume_10d > 0:
            rvol = round(volume / avg_volume_10d, 2)
        else:
            rvol = 1.0 # قيمة افتراضية إذا لم تتوفر البيانات

        return {
            'price': round(current_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'change': change_percent,
            'volume': volume,
            'float': shares_outstanding,
            'rvol': rvol
        }
    except:
        return None

def send_telegram_alert(ticker, data, alert_type="إشارة جديدة"):
    """تنسيق التنبيه المتكامل بالهاي، اللو، والـ RVOL"""
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] else "غير متوفر"
    icon = "⚔️" if alert_type == "إشارة جديدة" else "🚀"

    message = (
        f"{icon} **{alert_type}!** {icon}\n\n"
        f"🎫 **السهم المستهدف:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر الحالي:** ${data['price']}\n"
        f"🔺 **أعلى سعر (High):** ${data['high']}\n"
        f"🔻 **أدنى سعر (Low):** ${data['low']}\n"
        f"🔄 **التحرك الإجمالي:** +{data['change']}%\n"
        f"🔥 **الفوليوم النسبي (RVOL):** {data['rvol']}x\n"
        f"📊 **الفوليوم الحجمي:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

def send_finnhub_summary():
    """ملخص حصاد اليوم عند الطلب بكامل تفاصيله الفنية المحدثة"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    if not daily_tracked_stocks:
        message = "📋 **ملخص الحركة اليومية:**\n\nلا توجد أسهم انطبقت عليها الشروط الصارمة اليوم حتى الآن."
    else:
        message = "📋 **ملخص حصاد اليوم الفني المتكامل (Finnhub):**\n\n"
        sorted_stocks = sorted(daily_tracked_stocks.items(), key=lambda x: x[1]['change'], reverse=True)
        
        for index, (ticker, data) in enumerate(sorted_stocks, 1):
            yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
            float_formatted = f"{round(data['float'] / 1000000, 1)}M" if data['float'] else "غير متوفر"
            message += f"{index}. [{ticker}]({yahoo_url}) 🔥\n"
            message += f"   • السعر: `${data['price']}` [H: `${data['high']}` | L: `${data['low']}`]\n"
            message += f"   • الصعود: `+{data['change']}%` | الـ RVOL: `{data['rvol']}x`\n"
            message += f"   • الفوليوم: `{int(data['volume']):,}` | الفلوت: `{float_formatted}`\n\n"
            
        message += f"⏰ تم التحديث في: {time.strftime('%H:%M:%S')} EST"

    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        user_text = update["message"]["text"].strip().lower()
        if user_text in ["ملخص", "summary", "/summary"]:
            send_finnhub_summary()
    return jsonify({"status": "success"})

@app.route('/')
def home():
    return "Finnhub Advanced Pro Scanner is Active!"

def run_scanner_loop():
    print("⚡ تم تشغيل سكانر Finnhub المطور الشامل...")
    tickers_to_watch = ['MARA', 'RIOT', 'SOUN', 'PLTR', 'TSLA', 'NVDA', 'AMD', 'BABA', 'NIO', 'AAPL']
    
    while True:
        for ticker in tickers_to_watch:
            data = get_stock_details_finnhub(ticker)
            if data:
                price = data['price']
                change = data['change']
                share_float = data['float']
                rvol = data['rvol']
                
                # تطبيق كافة الفلاتر الصارمة جداً المعتمدة لحماية رأس مالك
                if MIN_PRICE <= price <= MAX_PRICE and change >= MIN_GAP_PERCENT:
                    if share_float <= MAX_FLOAT and rvol >= MIN_RVOL:
                        
                        # حفظ وتحديث البيانات للملخص
                        if ticker not in daily_tracked_stocks or change > daily_tracked_stocks[ticker]['change']:
                            daily_tracked_stocks[ticker] = data
                            daily_tracked_stocks[ticker]['notified'] = False
                        
                        # إرسال التنبيه الفوري
                        if daily_tracked_stocks[ticker]['notified'] is False:
                            send_telegram_alert(ticker, data, alert_type="إشارة زخم Finnhub")
                            daily_tracked_stocks[ticker]['notified'] = True
                            
            time.sleep(1)
        time.sleep(60)

scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
scanner_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
