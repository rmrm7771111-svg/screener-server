import os
import requests
import time
import threading
from flask import Flask

app = Flask(__name__)

# المفاتيح السرية من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FINNHUB_TOKEN = os.getenv('FINNHUB_TOKEN')

# قاموس لحفظ الأسعار السابقة لمراقبة الحركة دقيقة بدقيقة
last_tracked_prices = {}

# فلاتر المايكرو كاب الصارمة
MAX_MARKET_CAP = 300000000  # 300 مليون دولار
MAX_FLOAT = 50000000        # 50 مليون سهم

def send_telegram_alert(ticker, data, direction):
    """إرسال التنبيه اللحظي المنظم إلى تليجرام"""
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
    
    if direction == "up":
        icon = "🚀"
        status_text = f"اختراق صعودي مايكرو كاب (+{data['move_diff']}%)"
    else:
        icon = "🔻"
        status_text = f"تراجع وهبوط مايكرو كاب ({data['move_diff']}%)"
        
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] > 0 else "N/A"
    mktcap_formatted = f"{round(data['market_cap'] / 1000000, 2)}M" if data['market_cap'] > 0 else "N/A"

    message = (
        f"{icon} **{status_text}** {icon}\n\n"
        f"🎫 **السهم:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر الحالي:** ${data['price']}\n"
        f"🔺 **الهاي اليومي:** ${data['high']} | 🔻 **اللو اليومي:** ${data['low']}\n"
        f"🔄 **التغير اليومي العام:** +{data['change']}%\n"
        f"🔥 **الفوليوم النسبي RVOL:** {data['rvol']}x\n"
        f"📊 **حجم التداول اليومي:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"💎 **القيمة السوقية:** ${mktcap_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_live_top_gainers():
    """جلب قائمة الـ 30 سهم الأكثر ارتفاعاً في السوق الأمريكي من مصدر مفتوح ومستقر"""
    tickers = []
    try:
        # استخدام واجهة عامة ومستقرة جداً لجلب التوب جينرز لحظياً بدون حظر الـ IP
        url = "https://financialmodelingprep.com/api/v3/stock_market/gainers"
        res = requests.get(url, timeout=10).json()
        
        for item in res:
            symbol = item.get('symbol', '')
            # استبعاد الأسهم التي تحتوي على نقاط (المؤشرات وصناديق الـ ETF)
            if symbol and not symbol.count('.'):
                tickers.append(symbol)
    except Exception as e:
        print(f"Error fetching top gainers: {e}")
        
    # قائمة طوارئ احتياطية سريعة الحركة إذا حدث أي انقطاع في الشبكة
    if not tickers:
        tickers = ['HOLO', 'GWAV', 'FFIE', 'CRKN', 'SOUN', 'MULN', 'GME', 'AMC', 'LCID']
        
    return tickers[:30] # نأخذ أكبر 30 سهم توب جينر بالضبط كما طلبت

def get_finnhub_microcap_details(ticker):
    """تحليل السهم عبر Finnhub للتأكد من مطابقة شروط المايكرو كاب"""
    try:
        # 1. الأسعار الحية من مفتاحك
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_TOKEN}"
        q_res = requests.get(quote_url, timeout=5).json()
        
        c = q_res.get('c', 0)
        pc = q_res.get('pc', 0)
        h = q_res.get('h', 0)
        l = q_res.get('l', 0)
        v = q_res.get('v', 0)
        
        if pc == 0 or c == 0: return None
        change_percent = round(((c - pc) / pc) * 100, 2)

        # 2. جلب بيانات الفلوت والقيمة السوقية للتأكد أنه سهم مايكرو كاب
        profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_TOKEN}"
        p_res = requests.get(profile_url, timeout=5).json()
        
        market_cap = 0
        shares_outstanding = 0
        if p_res:
            market_cap = p_res.get('marketCapitalization', 0) * 1000000 
            shares_outstanding = p_res.get('shareOutstanding', 0) * 1000000
            
        # تطبيق الفلترة الصارمة: إذا لم تتوفر البيانات نمررها، وإذا توفرت يجب ألا تتجاوز شروط المايكرو كاب
        if market_cap > MAX_MARKET_CAP or shares_outstanding > MAX_FLOAT:
            return None

        # 3. حساب الـ RVOL الفعلي لسيولة حقيقية
        rvol = 1.0
        try:
            metric_url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_TOKEN}"
            m_res = requests.get(metric_url, timeout=5).json()
            avg_v = m_res.get('metric', {}).get('vVolume10D', 0)
            if avg_v > 0:
                actual_avg = avg_v * 1000000 if avg_v < 1000 else avg_v
                rvol = round(v / actual_avg, 2)
        except: pass

        return {
            'price': round(c, 2),
            'high': round(h, 2),
            'low': round(l, 2),
            'change': change_percent,
            'volume': v,
            'float': shares_outstanding,
            'market_cap': market_cap,
            'rvol': rvol
        }
    except:
        return None

def run_ultimate_scanner():
    print("🚀 رادار التوب جينرز والمايكرو كاب الاحترافي انطلق الآن...")
    
    while True:
        # خطوة 1: جلب التوب جينرز الـ 30 الفعليين في كامل الماركت بلحظتها
        current_top_30 = get_live_top_gainers()
        
        for ticker in current_top_30:
            # خطوة 2: فحص السهم عبر مفتاح Finnhub الخاص بك وتطبيق فلتر المايكرو كاب
            data = get_finnhub_microcap_details(ticker)
            if data:
                current_price = data['price']
                
                # خطوة 3: المقارنة كل 60 ثانية ورصد الصعود أو الهبوط
                if ticker in last_tracked_prices:
                    old_price = last_tracked_prices[ticker]
                    move_diff = round(((current_price - old_price) / old_price) * 100, 2)
                    data['move_diff'] = move_diff
                    
                    # إرسال تنبيه فوري إذا صعد أو هبط السهم بـ 0.4% أو أكثر خلال دقيقة واحدة
                    if move_diff >= 0.4:
                        send_telegram_alert(ticker, data, direction="up")
                    elif move_diff <= -0.4:
                        send_telegram_alert(ticker, data, direction="down")
                
                # حفظ السعر الحالي للدورة القادمة
                last_tracked_prices[ticker] = current_price
                
            time.sleep(1.5) # حماية وحفاظ على الـ Rate Limit الخاص بمفتاحك
            
        print("⏳ اكتملت دورة فحص الـ 30 سهم. انتظار 60 ثانية لبدء المسح اللحظي الجديد...")
        time.sleep(60)

# تشغيل خيط الفحص التلقائي المستقر
threading.Thread(target=run_ultimate_scanner, daemon=True).start()

@app.route('/')
def home():
    return "<h1>رادار الـ 30 توب جينرز المايكرو كاب الديناميكي يعمل الآن بأعلى استقرار!</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
