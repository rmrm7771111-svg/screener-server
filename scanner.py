import os
import requests
import time
import threading
from flask import Flask
import yfinance as yf

# 1. إعداد تطبيق الويب لـ Render لتشغيل الخدمة مجاناً
app = Flask(__name__)

@app.route('/')
def home():
    return "Warrior Trading Strategy Scanner (Customized) is Active!"

# 2. قراءة مفاتيح التليجرام السرية من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# ====================================================================
#  ⚔️ شروط الفلترة المعدلة (طريقة المحارب + تعديلاتك الخاصة) ⚔️
# ====================================================================
MIN_PRICE = 0.20            # الحد الأدنى للسعر (20 سنت) لاصطياد الأسهم الرخيصة جداً
MAX_PRICE = 25.0            # الحد الأقصى للسعر ($25) لضمان خفة الحركة
MIN_GAP_PERCENT = 4.0       # جاب افتتاح قوي بنسبة 4% فما فوق
MIN_VOLUME = 150000         # الحد الأدنى للفوليوم اللحظي لضمان وجود سيولة كافية
MAX_FLOAT = 50000000        # فلوت أقل من 50 مليون سهم (نطاق الزخم الطبيعي والممتاز)
MIN_RVOL = 2.0              # فوليوم نسبي قوي (ضعف المعدل الطبيعي على الأقل 2x)
# ====================================================================

# قاموس لحفظ التنبيهات المرسلة: يحفظ { اسم_السهم: آخر_سعر_أرسلناه }
sent_alerts_prices = {}

def get_top_market_movers():
    """جلب قائمة أعلى الأسهم حركة وصعوداً في كامل السوق الأمريكي"""
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        params = {"scrIds": "day_gainers", "count": 30}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, params=params, headers=headers).json()
        results = response.get('finance', {}).get('result', [{}])[0].get('quotes', [])
        
        tickers = [stock['symbol'] for stock in results if 'symbol' in stock]
        return tickers[:30]
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
        
        # جلب متوسط الفوليوم لآخر 10 أيام لحساب الـ RVOL
        avg_volume_10d = info.get('averageVolume10days', info.get('averageVolume', 0))
        
        if prev_close == 0 or open_price == 0:
            return None
            
        gap_percent = round(((open_price - prev_close) / prev_close) * 100, 2)
        current_change = round(((current_price - prev_close) / prev_close) * 100, 2)

        # حساب الفوليوم النسبي (RVOL)
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
    except Exception as e:
        print(f"خطأ في فحص تفاصيل السهم {ticker}: {e}")
        return None

def send_telegram_alert(ticker, data, alert_type="إشارة جديدة"):
    """تنسيق التنبيه وإرساله فوراً إلى تليجرام"""
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] else "غير متوفر"
    
    if alert_type == "إشارة جديدة":
        icon = "⚔️"
        title_text = f"إشارة زَخَم مطوّرة"
    else:
        icon = "🚀"
        title_text = f"متابعة الانفجار ({alert_type})"
    
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"

    message = (
        f"{icon} **{title_text}!** {icon}\n\n"
        f"🎫 **السهم المستهدف:** [{ticker}]({yahoo_url})  *(اضغط للتشارت اللحظي 📈)*\n"
        f"💵 **السعر الحالي:** ${data['price']}  *(نطاق التعديل: $0.20-$25)*\n"
        f"📈 **الفجوة (Gap):** {data['gap']}%\n"
        f"🔄 **التحرك الإجمالي:** {data['change']}%\n"
        f"🔥 **الفوليوم النسبي (RVOL):** {data['rvol']}x\n"
        f"📊 **الفوليوم اللحظي:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}  *(نطاق التعديل: < 50M)*\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True  
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"خطأ في إرسال تليجرام: {e}")

def run_scanner_loop():
    """الحلقة المستمرة لفحص أعلى 30 سهم مع تطبيق الشروط المعدلة"""
    print("⚡ تم تشغيل سكانر الزخم المعدل بنجاح...")
    
    while True:
        top_movers = get_top_market_movers()
        print(f"🔍 تم تحديث قائمة التوب 30. بدء الفحص...")
        
        for ticker in top_movers:
            data = get_stock_metrics(ticker)
            if data:
                current_price = data['price']
                
                # تطبيق الفلترة المحدثة بحسب طلبك:
                if MIN_PRICE <= current_price <= MAX_PRICE:
                    if abs(data['gap']) >= MIN_GAP_PERCENT and data['volume'] >= MIN_VOLUME:
                        if data['float'] and data['float'] <= MAX_FLOAT:
                            if data['rvol'] >= MIN_RVOL:
                                
                                if ticker not in sent_alerts_prices:
                                    print(f"🎯 سهم يطابق الفلتر المعدل تماماً: {ticker}")
                                    send_telegram_alert(ticker, data, alert_type="إشارة جديدة")
                                    sent_alerts_prices[ticker] = current_price
                                else:
                                    # مراقبة الانفجارات المتتالية بنسبة 5% فما فوق
                                    last_sent_price = sent_alerts_prices[ticker]
                                    price_increase_percent = ((current_price - last_sent_price) / last_sent_price) * 100
                                    
                                    if price_increase_percent >= 5.0:
                                        print(f"🚀 {ticker} يواصل الانفجار!")
                                        alert_msg = f"صعود +{round(price_increase_percent, 1)}%"
                                        send_telegram_alert(ticker, data, alert_type=alert_msg)
                                        sent_alerts_prices[ticker] = current_price
            
            time.sleep(1)
            
        print("🔄 انتهت الدورة، انتظر دقيقة للتحديث القادم...")
        time.sleep(60)

# تشغيل السكانر في الخلفية
scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
scanner_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
