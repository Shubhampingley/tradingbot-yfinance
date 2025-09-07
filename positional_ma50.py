
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol, period="1y")
        if df is None or len(df) < 60:
            continue
        df["MA50"] = df["Close"].rolling(50).mean()
        if df["Close"].iloc[-1] > df["MA50"].iloc[-1]:
            alerts.append(f"📈 {symbol} Above MA50 (trend intact)")
        elif df["Close"].iloc[-1] < df["MA50"].iloc[-1]:
            alerts.append(f"📉 {symbol} Below MA50 (weak)")
    msg = "\n".join(alerts) if alerts else "✅ No MA50 signals"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
