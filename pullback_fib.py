
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol, period="6mo")
        if df is None or len(df) < 30:
            continue
        high = df["Close"].max()
        low = df["Close"].min()
        level_38 = high - 0.382*(high-low)
        level_61 = high - 0.618*(high-low)
        last = df["Close"].iloc[-1]
        if level_61 <= last <= level_38:
            alerts.append(f"🔄 {symbol} in Fib pullback zone (38%-61%) | Close {last:.2f}")
    msg = "\n".join(alerts) if alerts else "✅ No Fib pullback signals"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
