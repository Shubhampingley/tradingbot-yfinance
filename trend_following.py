
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol)
        if df is None or len(df) < 60:
            continue
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        if df["EMA20"].iloc[-1] > df["EMA50"].iloc[-1] and df["EMA20"].iloc[-2] <= df["EMA50"].iloc[-2]:
            alerts.append(f"📈 {symbol} BUY (EMA20>EMA50)")
        elif df["EMA20"].iloc[-1] < df["EMA50"].iloc[-1] and df["EMA20"].iloc[-2] >= df["EMA50"].iloc[-2]:
            alerts.append(f"📉 {symbol} SELL (EMA20<EMA50)")
    msg = "\n".join(alerts) if alerts else "✅ No EMA signals"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
