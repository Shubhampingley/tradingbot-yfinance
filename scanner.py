import pandas as pd
import yfinance as yf
import numpy as np

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_rsi(symbol, interval, lookback="5y"):
    data = yf.download(symbol, period=lookback, interval=interval, progress=False)
    if data.empty:
        return None
    rsi = compute_rsi(data["Close"], 14)
    return rsi.iloc[-1]  # latest RSI

def scan_stocks(stock_list):
    results = []
    for sym, name in stock_list:
        try:
            weekly_rsi = get_rsi(sym, "1wk")
            monthly_rsi = get_rsi(sym, "1mo")

            if weekly_rsi is None or monthly_rsi is None:
                continue

            if weekly_rsi > 60 and monthly_rsi > 60:
                results.append({
                    "Symbol": sym,
                    "Name": name,
                    "Weekly RSI": round(weekly_rsi, 2),
                    "Monthly RSI": round(monthly_rsi, 2)
                })
        except Exception as e:
            print(f"Error scanning {sym}: {e}")
    return pd.DataFrame(results)

if __name__ == "__main__":
    # load stock list
    stocks = pd.read_csv("stocks.csv")
    stock_list = list(zip(stocks["symbol"], stocks["name"]))

    df = scan_stocks(stock_list)
    print("\n📊 Stocks with Weekly & Monthly RSI > 60\n")
    print(df.to_string(index=False))

    # save results
    df.to_csv("scanner_results.csv", index=False)
    print("\n✅ Results saved to scanner_results.csv")
