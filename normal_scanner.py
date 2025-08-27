import pandas as pd
import yfinance as yf
import os
import requests

# Load stock list (only "symbol" column needed)
stocks = pd.read_csv("stocks.csv")

# Check if "symbol" column exists
if "symbol" not in stocks.columns:
    raise Exception("❌ stocks.csv must contain a 'symbol' column")

stock_list = stocks["symbol"].tolist()

# Telegram config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

alerts = []

# Simple scanner logic
for symbol in stock_list:
    try:
        data = yf.download(symbol, period="5d", interval="1d")
        if data.empty:
            continue
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]

        # Example: check breakout
        if latest["Close"] > prev["High"]:
            alerts.append(f"🚀 Breakout: {symbol} | Close {latest['Close']:.2f} > Prev High {prev['High']:.2f}")

    except Exception as e:
        print(f"Error scanning {symbol}: {e}")

# Send results
if alerts:
    message = "\n".join(alerts)
else:
    message = "No trades found today ✅"

print(message)
send_telegram_message(message)
