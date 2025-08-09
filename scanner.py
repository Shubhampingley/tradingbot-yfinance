# scanner.py
import os
import math
import time
import requests
import yfinance as yf
from itertools import islice

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Alert threshold (percentage). Positive OR negative moves will be captured by absolute value.
PCT_THRESHOLD = float(os.getenv("PCT_THRESHOLD", "2.0"))

# Batch size for yfinance downloads (keeps fetches reliable)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))

# Top 500 tickers (NSE format expected by yfinance). You can update/replace this list.
TOP500 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","HINDUNILVR.NS","ICICIBANK.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","SBIN.NS","BHARTIARTL.NS","ITC.NS","HDFC.NS","BAJFINANCE.NS","MARUTI.NS",
    "ASIANPAINT.NS","SBILIFE.NS","NESTLEIND.NS","HCLTECH.NS","SUNPHARMA.NS","ULTRACEMCO.NS",
    # ... truncated for brevity — replace with full 500 list
]
# If you want full 500, upload or paste full list. For now assume list contains up to 500.

# === Helpers ===
def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=20)
        print("Telegram status:", r.status_code)
        if not r.ok:
            print("Telegram error:", r.text)
    except Exception as e:
        print("Telegram exception:", e)

def chunked_iterable(iterable, size):
    it = iter(iterable)
    for first in it:
        yield [first] + list(islice(it, size-1))

# === Core scanning ===
def scan_top_n(tickers, pct_threshold=PCT_THRESHOLD, batch_size=BATCH_SIZE):
    matches = []  # list of tuples: (symbol, last, prev_close, pct_change, volume)
    total = len(tickers)
    print(f"Scanning {total} tickers in batches of {batch_size}...")

    for batch in chunked_iterable(tickers, batch_size):
        tickers_str = " ".join(batch)
        try:
            # fetch 2 days to compute previous close and last close
            df = yf.download(tickers=batch, period="2d", interval="1d", progress=False, threads=True)
        except Exception as e:
            print("yfinance download error for batch:", e)
            time.sleep(2)
            continue

        # If single ticker, df has single-column structure; normalize to same shape
        # df may be a multiindex columns if multiple tickers
        if df.empty:
            print("No data returned for batch, skipping")
            continue

        # yfinance returns columns like ('Close', 'RELIANCE.NS') or if group_by='column' different shapes
        # We'll try to handle both common shapes
        try:
            # MultiTicker: columns are multiindex (Open/High/Low/Close/Volume) x ticker
            if isinstance(df.columns, pd.MultiIndex):
                for ticker in batch:
                    try:
                        close_series = df['Close'][ticker].dropna()
                    except Exception:
                        # different shape: maybe single-ticker, handle later
                        continue
                    if len(close_series) < 1:
                        continue
                    last = float(close_series.iloc[-1])
                    prev = float(close_series.iloc[-2]) if len(close_series) > 1 else last
                    # volume
                    vol = int(df['Volume'][ticker].iloc[-1]) if 'Volume' in df.columns.get_level_values(0) else 0
                    pct = (last - prev) / prev * 100 if prev else 0.0
                    if abs(pct) >= pct_threshold:
                        matches.append((ticker, last, prev, pct, vol))
            else:
                # Single ticker or single-index columns: fallback
                # For batch with multiple tickers, yfinance sometimes returns single-level columns with ticker in index
                for ticker in batch:
                    sub = df.xs(ticker, axis=1, level=1) if 'level' in dir(df.columns) else None
                    # Fallback simpler: use yf.Ticker per ticker
                    data = yf.Ticker(ticker).history(period="2d")
                    if data.empty:
                        continue
                    last = float(data["Close"].iloc[-1])
                    prev = float(data["Close"].iloc[-2]) if len(data) > 1 else last
                    vol = int(data["Volume"].iloc[-1]) if "Volume" in data else 0
                    pct = (last - prev) / prev * 100 if prev else 0.0
                    if abs(pct) >= pct_threshold:
                        matches.append((ticker, last, prev, pct, vol))
        except Exception as e:
            print("Error processing batch:", e)
            # As a robust fallback process tickers one by one
            for ticker in batch:
                try:
                    data = yf.Ticker(ticker).history(period="2d")
                    if data.empty:
                        continue
                    last = float(data["Close"].iloc[-1])
                    prev = float(data["Close"].iloc[-2]) if len(data) > 1 else last
                    vol = int(data["Volume"].iloc[-1]) if "Volume" in data else 0
                    pct = (last - prev) / prev * 100 if prev else 0.0
                    if abs(pct) >= pct_threshold:
                        matches.append((ticker, last, prev, pct, vol))
                except Exception as e2:
                    print("Ticker-level fetch error for", ticker, e2)

        # small throttle to be polite
        time.sleep(0.5)

    return matches

# === Entrypoint ===
def main():
    # Quick dependency guard
    try:
        import pandas as pd
    except Exception:
        print("pandas required. Please install pandas.")
        return

    tickers = TOP500  # replace or load dynamically if you like

    matches = scan_top_n(tickers)

    if not matches:
        send_telegram("✅ Scan complete — No movers above threshold.")
        return

    # Format message
    lines = [f"🚨 Movers (|chg| ≥ {PCT_THRESHOLD}%): {len(matches)}"]
    for s, last, prev, pct, vol in sorted(matches, key=lambda x: -abs(x[3]))[:200]:
        lines.append(f"{s}: ₹{last:.2f} ({pct:+.2f}%), vol: {vol}")
    message = "\n".join(lines[:400])  # telegram message size guard
    send_telegram(message)

if __name__ == "__main__":
    main()
