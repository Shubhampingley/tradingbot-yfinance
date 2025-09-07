
# Simple hybrid: strong trend + above MA50 = bullish fundamental alignment (placeholder)
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol, period="1y")
        if df is None or len(df) < 200:
            continue
        df["MA50"] = df["Close"].rolling(50).mean()
        df["MA200"] = df["Close"].rolling(200).mean()
        last = df["Close"].iloc[-1]
        if last > df["MA50"].iloc[-1] > df["MA200"].iloc[-1]:
            alerts.append(f"🏆 {symbol} Strong fundamental+technical alignment (Above MA50 & MA200)")
    msg = "\n".join(alerts) if alerts else "✅ No hybrid signals"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
