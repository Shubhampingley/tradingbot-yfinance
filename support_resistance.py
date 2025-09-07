
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol, period="6mo")
        if df is None:
            continue
        support = df["Low"].rolling(20).min().iloc[-2]
        resistance = df["High"].rolling(20).max().iloc[-2]
        last = df["Close"].iloc[-1]
        if abs(last - support)/support < 0.02:
            alerts.append(f"🟢 {symbol} near Support {support:.2f}")
        elif abs(last - resistance)/resistance < 0.02:
            alerts.append(f"🔴 {symbol} near Resistance {resistance:.2f}")
    msg = "\n".join(alerts) if alerts else "✅ No S/R signals"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
