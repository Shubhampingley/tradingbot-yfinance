import os
import yfinance as yf
import requests

# Get secrets from GitHub Actions
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Stocks to scan
STOCKS = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, json=payload)

def fetch_stock_data():
    message = "📊 Stock Prices:\n"
    for ticker in STOCKS:
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period="1d")
            last_price = data["Close"].iloc[-1]
            message += f"• {ticker}: ₹{last_price:.2f}\n"
        except Exception as e:
            message += f"• {ticker}: Error: {e}\n"
    return message

if __name__ == "__main__":
    msg = fetch_stock_data()
    send_telegram_message(msg)
