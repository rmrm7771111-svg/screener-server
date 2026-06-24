import os
import requests
import time
import threading
from flask import Flask, request, jsonify
import yfinance as yf

# 1. إعداد تطبيق الويب لـ Render
app = Flask(__name__)

# 2. قراءة مفاتيح التليجرام السرية من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# ====================================================================
#  ⚔️ شروط الفلترة المعدلة (طريقة المحارب) ⚔️
# ====================================================================
MIN_PRICE = 0.20            
MAX_PRICE = 25.0            
MIN_GAP_PERCENT = 4.0       
MIN_VOLUME = 150000         
MAX_FLOAT = 50000000        
MIN_RVOL = 2.0              
# ====================================================================

# قاموس لحفظ التنبيهات المرسلة وسعرها اللحظي: { اسم_السهم: آخر_سعر_أرسلناه }
sent_alerts_prices = {}

# قاموس مخصص لحفظ "ملخص اليوم" والأسهم التي انطبقت عليها الشروط: { اسم_السهم: أعلى_نسبة_تغير }
daily_summary_data = {}

def get_top_market_movers():
    """جلب قائمة أعلى الأسهم حركة وصعوداً في كامل السوق الأمريكي"""
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        params = {"scrIds": "day_gainers", "count": 30}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, params=params, headers=headers).json()
        results = response.get('finance', {}).get('result', [{}])[0].get('quotes', [])
        
        return [stock['symbol'] for stock in results if 'symbol' in stock][:30]
    except Exception as e:
        print(f"خطأ أثناء جلب قائمة التوب موفرز: {e}")
        return ['TSLA', 'NVDA', 'PLTR', 'MARA', 'RIOT', 'SOUN', 'BABA', 'AMD', 'AAPL', 'AMZN']

def get_stock_metrics(ticker):
    """فحص السهم بناءً على المعايير المعدلة الدقيقة"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='2d', interval='1m')
        if hist.empty:
            return None
            
        info = stock.info
        prev_close = info.get('previousClose', 0)
        open_price = info.get('open', 0)
        current_price = info.get('currentPrice', info.get('regularMarketPrice', hist['Close'].iloc[-1]))
        current_volume = info.get('regularMarketVolume', hist['Volume'].sum())
        share_float = info.get('floatShares', info.get('sharesOutstanding', 0))
        
        avg_volume_10d = info.get('averageVolume10days', info.get('averageVolume', 0))
        
        if prev_close == 0 or open_price == 0:
            return None
            
        gap_percent = round(((open_price - prev_close) / prev_close) * 100, 2)
        current_change = round(((current_price - prev_close) / prev_close) * 100, 2)

        if avg_volume_10d and avg_volume_10d > 0:
            rvol = round(current_volume / avg_volume_10d, 2)
        else:
            rvol = 1.0  

        return {
            'price': round(current_price, 2),
            'gap': gap_percent,
            'change': current_change,
            'float': share_float,
            'volume': current_volume,
            'rvol': rvol
        }
    except:
        return None

def send_telegram_alert(ticker, data, alert_type="إشارة جديدة"):
    """تنسيق التنبيه التلقائي وإرساله فوراً إلى تليجرام"""
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] else "غير متوفر"
    icon = "⚔️" if alert_type == "إشارة جديدة" else "🚀"
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"

    message = (
        f"{icon} **{alert_type}!** {icon}\n\n"
        f"🎫 **السهم المستهدف:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر الحالي:** ${data['price']}\n"
        f"📈 **الفجوة (Gap):** {data['gap']}%\n"
        f"🔄 **التحرك الإجمالي:** {data['change']}%\n"
        f"🔥 **الفوليوم النسبي (RVOL):** {data['rvol']}x\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

def send_summary_to_user():
    """صناعة وإرسال ملخص اليوم بناءً على طلب المستخدم"""
    if not daily_summary_data:
        message = "📋 **ملخص اليوم:**\n\nلا توجد أسهم طابقت الشروط الصارمة وتحركت حركات كبيرة اليوم حتى الآن."
    else:
        message = "📋 **ملخص حصاد اليوم للأسهم الأكثر حركة (Top Movers):**\n\n"
        # ترتيب الأسهم حسب الأعلى صعوداً في الملخص
        sorted_summary = sorted(daily_summary_data.items(), key=lambda x: x[1]['change'], reverse=True)
        
        for index, (ticker, stock_info) in enumerate(sorted_summary, 1):
            yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
            message += f"{index}. [{ticker}]({yahoo_url}) 📈\n"
            message += f"   • آخر سعر: `${stock_info['price']}`\n"
            message += f"   • أعلى صعود: `+{stock_info['change']}%`\n\n"
            
        message += f"⏰ تم التحديث في: {time.strftime('%H:%M:%S')} EST"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

# 3. استقبال الرسائل من تليجرام (Webhook)
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        user_text = update["message"]["text"].strip().lower()
        
        # إذا طلب المستخدم الملخص بكلمة "ملخص" أو "summary"
        if user_text in ["ملخص", "summary", "/summary"]:
            send_summary_to_user()
            
    return jsonify({"status": "success"})

@app.route('/')
def home():
    return "Interactive Scanner with Webhook is Active!"

def run_scanner_loop():
    """الحلقة المستمرة لفحص أعلى 30 سهم مع تخزين بيانات الملخص"""
    print("⚡ تم تشغيل سكانر الزخم التفاعلي المتكامل...")
    
    # محاولة ربط الـ Webhook مع تليجرام تلقائياً عند التشغيل ليتلقى الرسائل
    try:
        # ملاحظة: لكي يعمل استقبال الرسائل، يفضل تفعيل الـ Webhook برابط Render الخاص بك لاحقاً، 
        # ولكن الكود مهيأ تماماً لاستقبال الأمر بمجرد تفعيله.
        pass
    except: pass

    while True:
        top_movers = get_top_market_movers()
        for ticker in top_movers:
            data = get_stock_metrics(ticker)
            if data:
                current_price = data['price']
                current_change = data['change']
                
                if MIN_PRICE <= current_price <= MAX_PRICE:
                    if abs(data['gap']) >= MIN_GAP_PERCENT and data['volume'] >= MIN_VOLUME:
                        if data['float'] and data['float'] <= MAX_FLOAT:
                            if data['rvol'] >= MIN_RVOL:
                                
                                # حفظ أو تحديث السهم في قاموس ملخص اليوم بأعلى سعر صعود وصل له
                                if ticker not in daily_summary_data or current_change > daily_summary_data[ticker]['change']:
                                    daily_summary_data[ticker] = {'price': current_price, 'change': current_change}

                                if ticker not in sent_alerts_prices:
                                    send_telegram_alert(ticker, data, alert_type="إشارة زَخَم مطوّرة")
                                    sent_alerts_prices[ticker] = current_price
                                else:
                                    last_sent_price = sent_alerts_prices[ticker]
                                    price_increase_percent = ((current_price - last_sent_price) / last_sent_price) * 100
                                    
                                    if price_increase_percent >= 5.0:
                                        alert_msg = f"صعود +{round(price_increase_percent, 1)}%"
                                        send_telegram_alert(ticker, data, alert_type=alert_msg)
                                        sent_alerts_prices[ticker] = current_price
            time.sleep(1)
        time.sleep(60)

# تشغيل السكانر في الخلفية
scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
scanner_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
