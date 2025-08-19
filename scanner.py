import os
import csv
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Set in GitHub Secrets
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Set in GitHub Secrets
CSV_FILE = "nifty500.csv"  # Stock list file
TOP_N = 10  # Fetch Top 10 gainers and losers (for testing)
BATCH_SIZE = 100  # Batch size for yfinance requests

# ---------------- HELPERS ----------------
def send_telegram(message: str):
    """Send message to Telegram bot."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured. Skipping send.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=30)
        print("Telegram status:", r.status_code)
        if not r.ok:
            print("Telegram error:", r.text)
    except Exception as e:
        print("Failed sending telegram:", e)

def load_tickers(csv_path: str):
    """Read stock symbols from CSV."""
    tickers = []
    try:
        with open(csv_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get('SYMBOL')  # Ensure correct column name
                if sym:
                    tickers.append(sym.strip())
    except FileNotFoundError:
        print(f"Error: {csv_path} not found.")
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
    return tickers

def chunked(iterable, size):
    """Yield fixed-size chunks from iterable."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

# ---------------- CORE LOGIC ----------------
def compute_changes(tickers):
    """Return list of tuples: (ticker, prev_close, last_price, pct_change)."""
    results = []
    for batch in chunked(tickers, BATCH_SIZE):
        try:
            df = yf.download(batch, period="2d", interval="1d", progress=False, threads=True)
        except Exception as e:
            print("yfinance batch download error:", e)
            continue

        if df.empty:
            print("Empty dataframe for batch", batch)
            continue

        if isinstance(df.columns, pd.MultiIndex):
            for t in batch:
                try:
                    close_series = df['Close'][t].dropna()
                    if close_series.empty:
                        continue
                    last = float(close_series.iloc[-1])
                    prev = float(close_series.iloc[-2]) if len(close_series) > 1 else last
                    pct = ((last - prev) / prev) * 100 if prev else 0.0
                    results.append((t, prev, last, pct))
                except Exception as e:
                    print(f"Error processing {t}:", e)
        else:
            for t in batch:
                try:
                    hist = yf.Ticker(t).history(period="2d")
                    if hist.empty:
                        continue
                    last = float(hist['Close'].iloc[-1])
                    prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else last
                    pct = ((last - prev) / prev) * 100 if prev else 0.0
                    results.append((t, prev, last, pct))
                except Exception as e:
                    print(f"Error per-ticker {t}:", e)

        time.sleep(0.5)  # Avoid API rate limits

    return results

def format_message(changes):
    """Format top gainers and losers into Telegram message."""
    df = pd.DataFrame(changes, columns=['Ticker','Prev','Last','Pct'])
    df = df.dropna(subset=['Prev','Last'])
    df = df.sort_values('Pct', ascending=False)

    top_gainers = df.head(TOP_N)
    top_losers = df.tail(TOP_N).sort_values('Pct')

    now = datetime.now().strftime('%Y-%m-%d')
    lines = [f"📊 NSE Top {TOP_N} Gainers & Losers — {now}\n"]

    lines.append("📈 Top Gainers:")
    for i, row in enumerate(top_gainers.itertuples(), start=1):
        lines.append(f"{i}. {row.Ticker}: ₹{row.Last:.2f} ({row.Pct:+.2f}%)")

    lines.append("\n📉 Top Losers:")
    for i, row in enumerate(top_losers.itertuples(), start=1):
        lines.append(f"{i}. {row.Ticker}: ₹{row.Last:.2f} ({row.Pct:+.2f}%)")

    return "\n".join(lines)

# ---------------- ENTRYPOINT ----------------
if __name__ == '__main__':
    try:
        tickers = load_tickers(CSV_FILE)
        if not tickers:
            raise SystemExit(f"{CSV_FILE} is empty or missing.")
        print(f"Loaded {len(tickers)} tickers. Starting scan...")

        changes = compute_changes(tickers)
        if not changes:
            send_telegram("No data or error fetching prices today.")
        else:
            msg = format_message(changes)
            send_telegram(msg)

    except Exception as e:
        print("Fatal error:", e)
        send_telegram(f"❌ Scanner fatal error: {e}")
