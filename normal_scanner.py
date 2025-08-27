import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

# Telegram setup
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        except Exception as e:
            print("Telegram error:", e)

def check_swing_signals(ticker: str):
    try:
        df = yf.download(ticker, period="6mo", interval="1d")
        if df.empty:
            return None

        df["20EMA"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["200EMA"] = df["Close"].ewm(span=200, adjust=False).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        signal = None
        if latest["Close"] > latest["20EMA"] > latest["200EMA"]:
            if latest["Close"] > prev["Close"] * 1.02:  # breakout >2%
                signal = f"📈 {ticker} breakout above 20EMA & 200EMA"
        elif latest["Close"] < latest["20EMA"] < latest["200EMA"]:
            if latest["Close"] < prev["Close"] * 0.98:  # breakdown >2%
                signal = f"📉 {ticker} breakdown below 20EMA & 200EMA"

        return signal
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None

def main():
    tickers = os.getenv("TICKERS", "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS").split(",")

    messages = []
    for t in tickers:
        signal = check_swing_signals(t.strip())
        if signal:
            messages.append(signal)

    if messages:
        final_msg = "🚀 Swing Trade Alerts:\n" + "\n".join(messages)
        print(final_msg)
        send_telegram(final_msg)
    else:
        print("No signals today.")

if __name__ == "__main__":
    main()
