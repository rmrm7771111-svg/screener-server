import os
import requests
import time
import threading
from flask import Flask, jsonify

app = Flask(__name__)

# المفاتيح السرية من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FINNHUB_TOKEN = os.getenv('FINNHUB_TOKEN')

# قاموس لحفظ آخر أسعار مسجلة للأسهم لمقارنتها في الدورة القادمة
last_tracked_prices = {}

def send_telegram_alert(ticker, data, direction):
    """صياغة وإرسال التنبيه اللحظي بناءً على الحركة (صعود أو هبوط)"""
    yahoo_url = f"https://finance.yahoo.com/chart/{ticker}"
    
    # تحديد الإيقونة والنوع
    if direction == "up":
        icon = "🚀"
        status_text = f"اختراق صعودي لأعلى (Breakout) (+{data['move_diff']}%)"
    else:
        icon = "🔻"
        status_text = f"تراجع وهبوط لأسفل (Breakdown) ({data['move_diff']}%)"
        
    float_formatted = f"{round(data['float'] / 1000000, 2)}M" if data['float'] > 0 else "N/A"
    rvol_formatted = f"{data['rvol']}x" if data['rvol'] > 0 else "قيد الحساب"

    message = (
        f"{icon} **تنبيه حركة حية: {status_text}** {icon}\n\n"
        f"🎫 **السهم:** [{ticker}]({yahoo_url})\n"
        f"💵 **السعر اللحظي:** ${data['price']}\n"
        f"🔺 **الهاي اليومي:** ${data['high']} | 🔻 **اللو اليومي:** ${data['low']}\n"
        f"🔄 **التغير اليومي الإجمالي:** +{data['change']}%\n"
        f"🔥 **الفوليوم النسبي (RVOL):** {rvol_formatted}\n"
        f"📊 **حجم الفوليوم:** {int(data['volume']):,}\n"
        f"🌊 **الأسهم الحرة (Float):** {float_formatted}\n"
        f"⏰ **الوقت:** {time.strftime('%H:%M:%S')} EST"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_top_30_gainers():
    """جلب قائمة أكبر 30 سهم توب جينر في السوق حالياً"""
    tickers = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # طلب أعلى 30 سهم رابح في السوق الأمريكي بالثانية
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&lang=en-US&region=US&scrIds=day_gainers&count=30"
        res = requests.get(url, headers=headers, timeout=10).json()
        quotes = res['finance']['result'][0]['quotes']
        for q in quotes:
            symbol = q.get('symbol', '')
            if symbol and not symbol.count('.'): # استبعاد المؤشرات والأسهم المجزأة
                tickers.append(symbol)
    except Exception as e:
        print(f"Error fetching top gainers: {e}")
    return tickers[:30]

def get_finnhub_data(ticker):
    """سحب البيانات الفنية والعميقة للسهم عبر Finnhub"""
    try:
        # 1. الأسعار والسيولة اللحظية
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_TOKEN}"
        quote_res = requests.get(quote_url, timeout=5).json()
        
        current_price = quote_res.get('c', 0)
        prev_close = quote_res.get('pc', 0)
        high_price = quote_res.get('h', 0)   
        low_price = quote_res.get('l', 0)    
        volume = quote_res.get('v', 0)        
        
        if prev_close == 0 or current_price == 0: return None
        change_percent = round(((current_price - prev_close) / prev_close) * 100, 2)
        
        # 2. جلب الفلوت
        shares_outstanding = 0
        try:
            profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_TOKEN}"
            profile_res = requests.get(profile_url, timeout=5).json()
            shares_outstanding = profile_res.get('shareOutstanding', 0) * 1000000
        except: pass 
        
        # 3. حساب RVOL
        rvol = 0.0
        try:
            metric_url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_TOKEN}"
            metric_res = requests.get(metric_url, timeout=5).json()
            avg_volume_10d = metric_res.get('metric', {}).get('vVolume10D', 0)
            if avg_volume_10d:
                actual_avg_vol = avg_volume_10d * 1000000 if avg_volume_10d < 1000 else avg_volume_10d
                if actual_avg_vol > 0:
                    rvol = round(volume / actual_avg_vol, 2)
        except: pass

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

def run_gainers_tracker():
    print("⚡ رادار التوب جينرز اللحظي تم تشغيله ومراقبته كل 60 ثانية...")
    
    while True:
        # خطوة 1: سحب أكبر 30 توب جينر في هذه اللحظة
        top_gainers = get_top_30_gainers()
        
        for ticker in top_gainers:
            data = get_finnhub_data(ticker)
            if data:
                current_price = data['price']
                
                # خطوة 2: المقارنة مع السعر القديم المخزن في الدورة السابقة
                if ticker in last_tracked_prices:
                    old_price = last_tracked_prices[ticker]
                    
                    # حساب نسبة الحركة الفورية خلال الـ 60 ثانية الماضية
                    move_diff = round(((current_price - old_price) / old_price) * 100, 2)
                    data['move_diff'] = move_diff
                    
                    # إذا ارتفع السهم بأكثر من 0.5% خلال الدقيقة الماضية يرسل (🚀 اختراق)
                    if move_diff >= 0.5:
                        send_telegram_alert(ticker, data, direction="up")
                        
                    # إذا هبط السهم بأكثر من 0.5% خلال الدقيقة الماضية يرسل (🔻 هبوط)
                    elif move_diff <= -0.5:
                        send_telegram_alert(ticker, data, direction="down")
                
                # تحديث السعر الحالي في الذاكرة للدورة القادمة
                last_tracked_prices[ticker] = current_price
                
            time.sleep(1.2) # توزيع الطلبات لحماية الحساب من الحظر
            
        print("⏳ انتهت دورة فحص الـ 30 توب جينر. انتظار 60 ثانية للدورة القادمة...")
        time.sleep(60)

# تفعيل خيط الفحص التلقائي
threading.Thread(target=run_gainers_tracker, daemon=True).start()

@app.route('/')
def home():
    return "Top 30 Gainers Live Tracker is Running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
