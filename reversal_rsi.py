
import pandas as pd
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol, period="3mo")
        if df is None:
            continue
        delta = df["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))
        if df["RSI"].iloc[-1] < 30:
            alerts.append(f"🟢 {symbol} Oversold (RSI {df['RSI'].iloc[-1]:.1f})")
        elif df["RSI"].iloc[-1] > 70:
            alerts.append(f"🔴 {symbol} Overbought (RSI {df['RSI'].iloc[-1]:.1f})")
    msg = "\n".join(alerts) if alerts else "✅ No RSI signals"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
