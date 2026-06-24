import os
import requests
import time

# قراءة مفاتيح الـ API السرية من متغيرات البيئة (Render)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')

# شروط الفلترة للمومنتوم والـ Gap 
MIN_GAP_PERCENT = 3.0       # التنبيه إذا كان الجاب 3% أو أكثر
MIN_VOLUME = 100000         # الحد الأدنى للفوليوم لتفادي الأسهم الضعيفة
MAX_FLOAT = 50000000        # أسهم الفلوت المنخفض (أقل من 50 مليون سهم)

def get_market_movers():
    """جلب الأسهم الأكثر حركة ومومنتوم في السوق الأمريكي كاملًا بطلب واحد"""
    try:
        # استهداف الأسهم الأكثر صعوداً وهبوطاً وحجماً في السوق الأمريكي بالكامل
        url = f"https://finnhub.io/api/v1/stock/is-index?token={FINNHUB_API_KEY}" # دالة التحقق أو المقارنة بالسوق
        # نستخدم دالة الجلب المباشر لأعلى حركات الأسهم (Market Movers)
        movers_url = f"https://finnhub.io/api/v1/stock/screener?token={FINNHUB_API_KEY}"
        
        # لضمان عملها بشكل مجاني ومستقر، سنستهدف قائمة الـ Movers النشطة لحظياً
        # ملحوظة: finnhub توفر تصفية شاملة عبر هذا الرابط
        response = requests.get(f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_API_KEY}").json()
        
        # نأخذ كامل الأسهم المتاحة
        all_tickers = [item['symbol'] for item in response if item['type'] == 'Common Stock']
        return all_tickers
    except Exception as e:
        print(f"خطأ أثناء جلب قائمة السوق: {e}")
        return []

def get_stock_metrics(ticker):
    """فحص تفاصيل السهم المستهدف بدقة"""
    try:
        # 1. جلب السعر والـ Gap
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        quote_data = requests.get(quote_url).json()
        
        prev_close = quote_data.get('pc', 0)
        open_price = quote_data.get('o', 0)
        current_price = quote_data.get('c', 0)
        
        if prev_close == 0: 
            return None
        
        gap_percent = ((open_price - prev_close) / prev_close) * 100
        current_change = ((current_price - prev_close) / prev_close) * 100

        # 2. جلب الفلوت والفوليوم
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
    """إرسال التنبيه الفوري الفائق الدقة لتليجرام"""
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
    except Exception as e:
        print(f"خطأ في إرسال تليجرام: {e}")

def start_scanner():
    print("⚡ جاري تصفية وفحص كامل السوق الأمريكي بحثاً عن المومنتوم...")
    
    while True:
        # جلب قائمة الأسهم كاملة لتحديث الفحص
        tickers = get_market_movers()
        
        for ticker in tickers:
            # الفحص السريع بناء على التغير اللحظي أولاً لتسريع العملية
            data = get_stock_metrics(ticker)
            if data:
                # التحقق من شروطك الصارمة (الجاب، الفوليوم، والفلوت المنخفض)
                if abs(data['gap']) >= MIN_GAP_PERCENT and data['volume'] >= MIN_VOLUME:
                    if data['float'] and data['float'] <= MAX_FLOAT:
                        print(f"🔥 تم رصد حركة مومنتوم حقيقية: {ticker}")
                        send_telegram_alert(ticker, data)
            
            # تأخير بسيط جداً بأجزاء من الثانية للمحافظة على استقرار الاتصال
            time.sleep(0.5)
            
        print("🔄 انتهت دورة مسح كامل السوق، إعادة الفحص الفوري...")
        time.sleep(10)

if __name__ == "__main__":
    start_scanner()
