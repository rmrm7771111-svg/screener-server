import os
import requests
import time
import threading
from flask import Flask

# 1. إعداد تطبيق الويب لـ Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Test Server is Active!"

# 2. قراءة مفاتيح التليجرام فقط من Render
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

def send_test_alert():
    """دالة لإرسال رسالة تجريبية مضمونة لتليجرام"""
    print("🔄 جاري محاولة إرسال رسالة إلى تليجرام...")
    
    message = (
        f"🎯 **تنبيه تجريبي ناجح!** 🎯\n\n"
        f"✅ تم الربط بين السكريبت والتليجرام بنجاح مئة بالمئة!\n"
        f"⏰ **الوقت الحالي:** {time.strftime('%H:%M:%S')}\n\n"
        f"جاهزون للخطوة القادمة غداً إن شاء الله 🚀"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        res = requests.post(url, json=payload)
        print(f"📡 نتيجة الإرسال من تليجرام: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ فشل الاتصال بتليجرام تماماً: {e}")

def run_test_loop():
    """حلقة ترسل رسالة فورية عند التشغيل ثم كل 20 ثانية"""
    # إرسال أول رسالة فوراً عند تشغيل السيرفر
    time.sleep(5) # انتظار 5 ثوانٍ ليتأكد أن السيرفر استقر
    send_test_alert()
    
    while True:
        time.sleep(20)
        send_test_alert()

# تشغيل الحلقة في الخلفية
test_thread = threading.Thread(target=run_test_loop, daemon=True)
test_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
