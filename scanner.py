import os
import requests
import time
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# المفاتيح السرية من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FINNHUB_TOKEN = os.getenv('FINNHUB_TOKEN')

# ====================================================================
#  ⚔️ الفلاتر الصارمة (لتصفية أسهم السوق المشتعلة) ⚔️
# ====================================================================
MIN_PRICE = 0.20            
MAX_PRICE = 25.0            
MIN_GAP_PERCENT = 4.0       
MAX_FLOAT = 50000000        # فلوت أقل من 50 مليون سهم
MIN_RVOL = 2.0              # فوليوم نسبي أعلى من 2x (دخول سيولة غير طبيعية)
# ====================================================================

daily_tracked_stocks = {}

def get_market_movers():
    """الطبقة الأولى: سحب قائمة ديناميكية بالأسهم الأكثر حراكاً وارتفاعاً في كامل السوق"""
    tickers = set()
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # سحب الأسهم الأكثر ارتفاعاً (Day Gainers) من واجهة البيانات العامة لتغطية السوق
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&lang=en-US&region=US&scrIds=day_gainers&count=50"
        res = requests.get(url, headers=headers, timeout=10).json()
        quotes = res['finance']['result'][0]['quotes']
        
        for q in quotes:
            symbol = q.get('symbol', '')
            price = q.get('regularMarketPrice', 0)
            # تصفية مبدئية سريعة قبل إرسال السهم لفحص Finnhub العميق
            if symbol and (MIN_PRICE <= price <= (MAX_PRICE + 5)) and not symbol.count('.'):
                tickers.add(symbol)
    except Exception as e:
        print(f"Error fetching market movers: {e}")
        # قائمة طوارئ أساسية في حال حدوث أي انقطاع مؤقت في السحب
        tickers.update(['MARA', 'RIOT', 'SOUN', 'PLTR', 'MULN', 'GME', 'AMC', 'FFIE', 'LCID']) 
    return list(tickers)

def get_stock_details_finnhub(ticker):
    """الطبقة الثانية: استخراج الهاي واللو والفلوت وحساب الـ RVOL الفعلي عبر Finnhub"""
    try:
        # 1. جلب الأسعار والسيولة اللحظية
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_TOKEN}"
        quote_res = requests.get(quote_url, timeout=5).json()
        
        current_price = quote_res.get('c', 0)
        prev_close = quote_res.get('pc', 0)
        high_price = quote_res.get('h', 0)   
        low_price = quote_res.get('l', 0)    
        volume = quote_res.get('v', 0)        
        
        if prev_close == 0 or current_price == 0: 
            return None
            
        change_percent = round(((current_price - prev_close) / prev_close) * 100, 2)
        
        # 2. جلب حجم الفلوت (بشكل آمن يحمي من توقف الكود)
        shares_outstanding = 0
        try:
            profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_TOKEN}"
            profile_res = requests.get(profile_url, timeout=5).json()
            if profile_res and 'shareOutstanding' in profile_res:
                shares_outstanding = profile_res.get('shareOutstanding', 0) * 1000000
        except:
            pass 
        
        # 3. جلب متوسط فوليوم 10 أيام وحساب الفوليوم النسبي RVOL
        rvol = 0.0
        try:
            metric_url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_TOKEN}"
            metric_res = requests.get(metric_url, timeout=5).json()
            avg_volume_10d = metric_res.get('metric', {}).get('vVolume10D', 0)
            
            if avg_volume_10d:
                # موازنة الحساب: إذا كان المتوسط راجعاً بالملايين نقوم بضربه لمساواته بالفوليوم الحالي
                actual_avg_vol = avg_volume_10d * 1000000 if avg_volume_10d < 1000 else avg_volume_10d
                if actual_avg_vol > 0:
                    rvol = round(volume / actual_avg_vol, 2)
        except:
            pass

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

def send_telegram_alert(ticker, data, alert_type="إشارة اختراق السوق"):
    """صياغة وإرسال التنبيه الفني الشامل إلى تليجرام"""
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
    
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] > 0 else "غير متوفر بحسابك"
    rvol_formatted = f"{data['rvol']}x" if data['rvol'] > 0 else "قيد الحساب"

    message = (
        f"🚨 **{alert_type}!** 🚨\n\n"
        f"🎫 **السهم المستهدف:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر الحالي:** ${data['price']}\n"
        f"🔺 **أعلى سعر (High):** ${data['high']}\n"
        f"🔻 **أدنى سعر (Low):** ${data['low']}\n"
        f"🔄 **التحرك الإجمالي:** +{data['change']}%\n"
        f"🔥 **الفوليوم النسبي (RVOL):** {rvol_formatted}\n"
        f"📊 **الفوليوم الحجمي:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload)
    except: pass

def send_finnhub_summary():
    """تجهيز وإرسال تقرير حصاد اليوم لأعلى 15 سهم حققوا حركة صعوداً"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if not daily_tracked_stocks:
        message = "📋 **ملخص السوق:**\n\nالسوق هادئ، لا توجد أسهم انطبقت عليها الشروط اليوم بعد."
    else:
        message = "📋 **ملخص أسهم السوق المشتعلة اليوم:**\n\n"
        sorted_stocks = sorted(daily_tracked_stocks.items(), key=lambda x: x[1]['change'], reverse=True)
        for index, (ticker, data) in enumerate(sorted_stocks[:15], 1): 
            yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
            float_formatted = f"{round(data['float'] / 1000000, 1)}M" if data['float'] > 0 else "-"
            rvol_formatted = f"{data['rvol']}x" if data['rvol'] > 0 else "-"
            message += f"{index}. [{ticker}]({yahoo_url}) | `${data['price']}` | `+{data['change']}%` | RVOL: `{rvol_formatted}`\n"
        message += f"\n⏰ تم التحديث في: {time.strftime('%H:%M:%S')} EST"

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
    return "Market-Wide Intelligent Scanner is Active!"

def run_scanner_loop():
    print("⚡ تم تشغيل مساح السوق الشامل والذكي بنجاح...")
    
    while True:
        # خطوة 1: جلب الأسهم الأكثر حركة في الماركت كله الآن لتحديث الرادار
        dynamic_tickers = get_market_movers()
        print(f"🔍 جاري فحص وعمل فلترة لـ {len(dynamic_tickers)} سهم نشط عبر Finnhub...")
        
        # خطوة 2: الفحص الفني الدقيق لكل سهم ديناميكي
        for ticker in dynamic_tickers:
            data = get_stock_details_finnhub(ticker)
            if data:
                price = data['price']
                change = data['change']
                share_float = data['float']
                rvol = data['rvol']
                
                # إخضاع السهم لـ الفلاتر الصارمة لضمان الجودة
                if MIN_PRICE <= price <= MAX_PRICE and change >= MIN_GAP_PERCENT:
                    # تصفية الفلوت والـ RVOL (أو تمرير الإشارة بشكل آمن إذا كانت البيانات ناقصة في السيرفر)
                    pass_float = (share_float <= MAX_FLOAT) if share_float > 0 else True
                    pass_rvol = (rvol >= MIN_RVOL) if rvol > 0 else True
                    
                    if pass_float and pass_rvol:
                        if ticker not in daily_tracked_stocks or change > daily_tracked_stocks[ticker]['change']:
                            daily_tracked_stocks[ticker] = data
                            daily_tracked_stocks[ticker]['notified'] = False
                        
                        if daily_tracked_stocks[ticker]['notified'] is False:
                            send_telegram_alert(ticker, data)
                            daily_tracked_stocks[ticker]['notified'] = True
                            
            time.sleep(1.5) # حماية للحساب من حظر الطلبات (Rate Limit Protection)
            
        print("⏳ اكتملت دورة مسح الماركت كاملة. راحة دقيقة قبل الفحص التالي...")
        time.sleep(60)

scanner_thread = threading.Thread(target=run_scanner_loop, daemon=True)
scanner_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
