
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol, period="1mo")
        if df is None or len(df) < 2:
            continue
        latest, prev = df.iloc[-1], df.iloc[-2]
        if latest["Close"] > prev["High"]:
            alerts.append(f"🚀 Breakout {symbol}: Close {latest['Close']:.2f} > Prev High {prev['High']:.2f}")
    msg = "\n".join(alerts) if alerts else "✅ No breakouts"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
