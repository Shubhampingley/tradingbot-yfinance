
# Placeholder: In practice link to earnings calendar API. Here use big gaps as proxy.
from utils import load_stocks, get_data, send_telegram_message
def run():
    alerts = []
    for symbol in load_stocks():
        df = get_data(symbol, period="1mo")
        if df is None or len(df) < 2:
            continue
        gap = (df["Open"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]
        if abs(gap) > 0.05:
            alerts.append(f"⚡ {symbol} Gap {gap*100:.1f}% (possible earnings/news)")
    msg = "\n".join(alerts) if alerts else "✅ No earnings/news gaps"
    print(msg)
    send_telegram_message(msg)
if __name__ == "__main__":
    run()
