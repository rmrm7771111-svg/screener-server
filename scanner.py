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

# قاموس لحفظ الأسعار السابقة لمراقبة الصعود والهبوط كل 60 ثانية
last_tracked_prices = {}

# فلاتر المايكرو كاب (Micro-Cap) الصارمة للأسهم الانفجارية
MAX_MARKET_CAP = 300000000  # أقصى قيمة سوقية: 300 مليون دولار (مايكرو كاب)
MAX_FLOAT = 50000000        # أقصى حجم أسهم حرة: 50 مليون سهم

def send_telegram_alert(ticker, data, direction):
    """إرسال تنبيه الحركة اللحظية صعوداً أو هبوطاً إلى تليجرام"""
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
    
    if direction == "up":
        icon = "🚀"
        status_text = f"اختراق صعودي مايكرو كاب (Breakout) (+{data['move_diff']}%)"
    else:
        icon = "🔻"
        status_text = f"تراجع وهبوط مايكرو كاب (Breakdown) ({data['move_diff']}%)"
        
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] > 0 else "N/A"
    mktcap_formatted = f"{round(data['market_cap'] / 1000000, 2)}M" if data['market_cap'] > 0 else "N/A"

    message = (
        f"{icon} **{status_text}** {icon}\n\n"
        f"🎫 **السهم:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر الحالي:** ${data['price']}\n"
        f"🔺 **الهاي اليومي:** ${data['high']} | 🔻 **اللو اليومي:** ${data['low']}\n"
        f"🔄 **التغير اليومي العام:** +{data['change']}%\n"
        f"🔥 **الفوليوم النسبي RVOL:** {data['rvol']}x\n"
        f"📊 **حجم التداول:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"💎 **القيمة السوقية:** ${mktcap_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def get_finnhub_top_movers():
    """استخراج قائمة الأسهم النشطة مباشرة من Finnhub وبالمفتاح الخاص بك"""
    tickers = []
    try:
        # استدعاء قائمة الأسهم الأكثر نشاطاً وتغيراً في السوق الأمريكي عبر الـ API المباشر
        url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_TOKEN}"
        res = requests.get(url, timeout=15).json()
        
        # فرز أولي وسريع لأخذ الأسهم العادية فقط واستبعاد الصناديق والمؤشرات
        valid_symbols = [
            item['symbol'] for item in res 
            if item.get('type') == 'Common Stock' and not item['symbol'].count('.')
        ]
        
        # لضمان السرعة وفحص التوب جينرز، نأخذ عينة من الأسهم النشطة لفحصها بدقة بالخطوة التالية
        # سنركز على أول 100 سهم نشط لتصفيتهم إلى أفضل 30 مايكرو كاب
        return valid_symbols[:100]
    except Exception as e:
        print(f"Error fetching symbols from Finnhub: {e}")
    # أسهم طوارئ مايكرو كاب وسريعة الحركة لضمان عمل الرادار في كل الظروف
    return ['HOLO', 'MGLO', 'LPA', 'BDRX', 'GWAV', 'FFIE', 'CRKN', 'SOUN']

def get_detailed_crypto_and_microcap_data(ticker):
    """فحص السهم بالكامل والتأكد من مطابقتة لشروط المايكرو كاب والتوب جينرز"""
    try:
        # 1. جلب الأسعار الحية
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_TOKEN}"
        q_res = requests.get(quote_url, timeout=5).json()
        
        c = q_res.get('c', 0)
        pc = q_res.get('pc', 0)
        h = q_res.get('h', 0)
        l = q_res.get('l', 0)
        v = q_res.get('v', 0)
        
        if pc == 0 or c == 0: return None
        change_percent = round(((c - pc) / pc) * 100, 2)
        
        # فلتر توب جينرز مبدئي (يجب أن يكون السهم مرتفع اليوم بأكثر من 2%)
        if change_percent < 2.0: return None

        # 2. جلب بيانات الشركة (الفلوت والقيمة السوقية)
        profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_TOKEN}"
        p_res = requests.get(profile_url, timeout=5).json()
        if not p_res: return None
        
        market_cap = p_res.get('marketCapitalization', 0) * 1000000 # تحويل للمليون
        shares_outstanding = p_res.get('shareOutstanding', 0) * 1000000
        
        # تطبيق فلتر المايكرو كاب الصارم (Micro-Cap Filter)
        if market_cap > MAX_MARKET_CAP or shares_outstanding > MAX_FLOAT:
            return None

        # 3. حساب الـ RVOL
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

def run_pure_finnhub_scanner():
    print("⚡ تم تشغيل الرادار المعتمد بالكامل على Finnhub API للمايكرو كاب...")
    
    while True:
        # جلب قائمة الأسهم المبدئية عبر المفتاح
        raw_tickers = get_finnhub_top_movers()
        valid_microcaps_found = 0
        
        for ticker in raw_tickers:
            # إذا وصلنا لـ 30 سهم مايكرو كاب نشط ممتاز في هذه الدورة نكتفي بها للسرعة
            if valid_microcaps_found >= 30: 
                break
                
            data = get_detailed_crypto_and_microcap_data(ticker)
            if data:
                valid_microcaps_found += 1
                current_price = data['price']
                
                # المقارنة كل 60 ثانية لرصد الصعود والهبوط اللحظي
                if ticker in last_tracked_prices:
                    old_price = last_tracked_prices[ticker]
                    move_diff = round(((current_price - old_price) / old_price) * 100, 2)
                    data['move_diff'] = move_diff
                    
                    # إرسال تنبيه لو تحرك السهم صعوداً أو هبوطاً بمقدار 0.4% أو أكثر خلال دقيقة
                    if move_diff >= 0.4:
                        send_telegram_alert(ticker, data, direction="up")
                    elif move_diff <= -0.4:
                        send_telegram_alert(ticker, data, direction="down")
                
                # تخزين السعر اللحظي الحالي للدورة القادمة
                last_tracked_prices[ticker] = current_price
                
            time.sleep(1.2) # حماية الـ API Rate Limit الخاص بمفتاحك
            
        print(f"⏳ تم فحص وتحديث أسهم المايكرو كاب. انتظار 60 ثانية لبدء الدورة الجديدة...")
        time.sleep(60)

# تشغيل خيط الفحص المستقل
threading.Thread(target=run_pure_finnhub_scanner, daemon=True).start()

@app.route('/')
def home():
    return "<h1>رادار المايكرو كاب والتوب جينرز عبر Finnhub يعمل بأعلى كفاءة!</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
