import yfinance as yf
import pandas as pd
import os
import telegram

# Load Telegram secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in GitHub Secrets")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Load stock symbols from CSV
stocks = pd.read_csv("stocks.csv")

if "symbol" not in stocks.columns:
    raise ValueError("CSV must contain a column named 'symbol'")

stock_list = stocks["symbol"].tolist()

messages = []

for symbol in stock_list:
    try:
        data = yf.download(symbol, period="6mo", interval="1d", progress=False)

        if data.empty:
            continue

        # Simple swing filter: price above 50 EMA and RSI > 60
        data["EMA50"] = data["Close"].ewm(span=50).mean()
        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        data["RSI"] = 100 - (100 / (1 + rs))

        last_row = data.iloc[-1]
        if last_row["Close"] > last_row["EMA50"] and last_row["RSI"] > 60:
            messages.append(f"{symbol} looks bullish (Close={last_row['Close']:.2f}, RSI={last_row['RSI']:.1f})")

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")

# Send alerts to Telegram
if messages:
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="\n".join(messages))
else:
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="No swing trade setups found today 🚫")
