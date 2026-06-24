import os
import requests
import time
import threading
from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# ====================================================================
#  🧪 شروط فلاتر مفتوحة وموسعة جداً للتجربة والاختبار فقط 🧪
# ====================================================================
MIN_PRICE = 0.20            # الحد الأدنى 20 سنت (شرطك الأساسي)
MAX_PRICE = 9999.0          # تم إلغاء الحد الأعلى لتمرير أي سهم
MIN_GAP_PERCENT = 0.0       # تم إلغاء شرط الجاب (حتى لو صفر يمر)
MIN_VOLUME = 0              # تم إلغاء شرط الفوليوم اللحظي الأدنى
MAX_FLOAT = 999999999999    # تم إلغاء شرط الفلوت المنخفض تماماً
MIN_RVOL = 0.0              # تم إلغاء شرط الفوليوم النسبي
# ====================================================================

sent_alerts_prices = {}

def get_top_market_movers():
    """جلب قائمة أعلى 30 سهم حركة وصعوداً في كامل السوق الأمريكي لحظياً"""
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        params = {"scrIds": "day_gainers", "count": 30}
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, params=params, headers=headers).json()
        results = response.get('finance', {}).get('result', [{}])[0].get('quotes', [])
        return [stock['symbol'] for stock in results if 'symbol' in stock][:30]
    except:
        return []

def get_stock_metrics(ticker):
    """الفحص اللحظي المفتوح للتجربة خارج/أثناء أوقات السوق"""
    try:
        stock = yf.Ticker(ticker)
        # نطلب بيانات يومية لضمان جلب إغلاق أمس واليوم السابق حتى لو السوق مغلق
        hist = stock.history(period='5d', interval='1d
