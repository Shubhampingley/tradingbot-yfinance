import yfinance as yf
import pandas as pd
import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

# Read stock tickers from CSV
stocks = pd.read_csv("stocks.csv", header=None, names=["symbol"])
stock_list = stocks["symbol"].tolist()

alerts = []

for symbol in stock_list:
    try:
        data = yf.download(symbol, period="6mo", interval="1d")
        if data.empty:
            continue

        rsi = compute_rsi(data["Close"])
        last_rsi = rsi.iloc[-1]

        if last_rsi > 60:
            alerts.append(f"{symbol} RSI={last_rsi:.2f}")
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")

if alerts:
    msg = "📊 Swing Trade Alerts:\n" + "\n".join(alerts)
    send_telegram(msg)
else:
    send_telegram("No trade signals today.")

# --- RSI function ---
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
