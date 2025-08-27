import pandas as pd
import yfinance as yf
import datetime as dt
import os
import requests

# --- Telegram Setup ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
            requests.post(url, data=payload)
        except Exception as e:
            print("Telegram error:", e)

# --- Load tickers from CSV ---
def load_tickers():
    try:
        df = pd.read_csv("stocks.csv", header=None)
        tickers = df[0].dropna().tolist()
        return tickers
    except Exception as e:
        send_telegram(f"❌ Error reading stocks.csv: {e}")
        return []

# --- Strategy: Swing trade filter ---
def check_strategy(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if data.empty:
            return None

        data["RSI"] = compute_rsi(data["Close"])
        latest = data.iloc[-1]

        # Example swing condition: RSI above 60 + price above 50EMA
        ema50 = data["Close"].ewm(span=50).mean().iloc[-1]
        if latest["RSI"] > 60 and latest["Close"] > ema50:
            return f"{ticker}: Close={latest['Close']:.2f}, RSI={latest['RSI']:.1f}"
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
    return None

# --- RSI function ---
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- Main run ---
def run_scanner():
    tickers = load_tickers()
    if not tickers:
        send_telegram("⚠️ No tickers found in stocks.csv")
        return

    signals = []
    for t in tickers:
        res = check_strategy(t)
        if res:
            signals.append(res)

    if signals:
        send_telegram("✅ Swing Trade Signals:\n" + "\n".join(signals))
    else:
        send_telegram("ℹ️ No signals found today.")

if __name__ == "__main__":
    run_scanner()
