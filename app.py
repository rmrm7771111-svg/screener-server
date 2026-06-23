from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY")

@app.route("/")
def home():
    return {"status": "online"}

@app.route("/quote/<symbol>")
def quote(symbol):

    url = "https://finnhub.io/api/v1/quote"

    r = requests.get(
        url,
        params={
            "symbol": symbol.upper(),
            "token": API_KEY
        }
    )

    return jsonify(r.json())
