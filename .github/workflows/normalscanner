# 📈 Swing Trading Scanner (EMA + RSI + Volume + Breakout)

Below are two files you can copy into your repo:

---

## `scanner.py`

````python
#!/usr/bin/env python3
"""
Swing Trading Scanner
Filters: Price > 200EMA, RSI>60, Breakout above 20-day high, Volume > 1.5x 20-day avg.
Sends Telegram alert if matches found.

Env Vars (set in GitHub Secrets or locally):
- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID
- TICKERS (optional, comma-separated, e.g. "RELIANCE.NS,TCS.NS,INFY.NS")

Optional file: tickers.csv (one symbol per line). If both TICKERS and tickers.csv are missing,
uses a small default list of liquid NSE names.
"""
import os
import sys
import time
import math
import json
import traceback
from datetime import datetime, timedelta, timezone

import pandas as pd
import numpy as np
import requests
import yfinance as yf

# --------- Config ---------
MIN_RSI = float(os.getenv("MIN_RSI", 60))
VOLUME_MULTIPLIER = float(os.getenv("VOLUME_MULTIPLIER", 1.5))
BREAKOUT_LOOKBACK = int(os.getenv("BREAKOUT_LOOKBACK", 20))  # days
EMA_FAST = int(os.getenv("EMA_FAST", 50))
EMA_SLOW = int(os.getenv("EMA_SLOW", 200))
PERIOD = os.getenv("PERIOD", "6mo")
INTERVAL = os.getenv("INTERVAL", "1d")
TIMEOUT = int(os.getenv("TIMEOUT", 30))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --------- Utilities ---------

def read_tickers() -> list[str]:
    # Priority: env TICKERS > tickers.csv > defaults
    env_tickers = os.getenv("TICKERS")
    if env_tickers:
        symbols = [s.strip() for s in env_tickers.split(",") if s.strip()]
        if symbols:
            return symbols
    # tickers.csv (one per line)
    if os.path.exists("tickers.csv"):
        try:
            df = pd.read_csv("tickers.csv", header=None)
            symbols = df[0].astype(str).str.strip().tolist()
            symbols = [s for s in symbols if s and not s.startswith("#")]  # allow comments
            if symbols:
                return symbols
        except Exception:
            print("[WARN] Failed to read tickers.csv; falling back to defaults.")
    # Default: a handful of liquid Indian names (NSE)
    return [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
        "LT.NS","KOTAKBANK.NS","SBIN.NS","AXISBANK.NS","BAJFINANCE.NS"
    ]


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    gain_ema = pd.Series(gain, index=series.index).ewm(alpha=1/length, adjust=False).mean()
    loss_ema = pd.Series(loss, index=series.index).ewm(alpha=1/length, adjust=False).mean()
    rs = gain_ema / (loss_ema.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)


def breakout_high(series: pd.Series, lookback: int) -> pd.Series:
    # True when today's close > max(high of previous lookback days)
    prev_high = series.shift(1).rolling(lookback).max()
    return series > prev_high


def pct(a, b):
    try:
        return (a / b - 1) * 100
    except Exception:
        return np.nan


def fetch_history(symbol: str) -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False, timeout=TIMEOUT)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df = df.rename(columns=str.title)  # ensure 'Close','High','Low','Open','Volume'
                return df
        except Exception as e:
            if attempt == 2:
                print(f"[ERROR] {symbol} download failed: {e}")
            time.sleep(1 + attempt)
    return pd.DataFrame()


def analyze_symbol(symbol: str):
    df = fetch_history(symbol)
    if df.empty or len(df) < max(EMA_SLOW + 5, BREAKOUT_LOOKBACK + 5):
        return None

    df["EMA_FAST"] = ema(df["Close"], EMA_FAST)
    df["EMA_SLOW"] = ema(df["Close"], EMA_SLOW)
    df["RSI14"] = rsi(df["Close"], 14)
    df["VOL20"] = df["Volume"].rolling(20).mean()
    df["Breakout"] = breakout_high(df["Close"], BREAKOUT_LOOKBACK)

    last = df.iloc[-1]

    cond_price_trend = (last["Close"] > last["EMA_SLOW"]) and (last["EMA_FAST"] >= last["EMA_SLOW"])  # strong trend
    cond_rsi = last["RSI14"] >= MIN_RSI
    cond_breakout = bool(last["Breakout"])  # closing breakout vs previous N days
    cond_volume = last["Volume"] >= VOLUME_MULTIPLIER * (last["VOL20"] if not math.isnan(last["VOL20"]) else 0)

    passed = cond_price_trend and cond_rsi and cond_breakout and cond_volume

    result = {
        "symbol": symbol,
        "close": float(last["Close"]),
        "ema50": float(last["EMA_FAST"]),
        "ema200": float(last["EMA_SLOW"]),
        "rsi14": float(last["RSI14"]),
        "vol": int(last["Volume"]),
        "vol20": float(last["VOL20"]) if not math.isnan(last["VOL20"]) else np.nan,
        "volx": (float(last["Volume"]) / float(last["VOL20"])) if not math.isnan(last["VOL20"]) and last["VOL20"]>0 else np.nan,
        "breakout": bool(cond_breakout),
        "price_vs_200ema_%": pct(last["Close"], last["EMA_SLOW"]),
        "passed": bool(passed),
    }
    return result


def telegram_send(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[INFO] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing; skipping Telegram.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code != 200:
            print(f"[WARN] Telegram send failed: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[WARN] Telegram exception: {e}")


def format_telegram_table(df: pd.DataFrame, max_rows: int = 10) -> str:
    if df.empty:
        return "No matches today."
    cols = ["symbol","close","rsi14","price_vs_200ema_%","volx"]
    view = df[cols].copy()
    view = view.sort_values(["rsi14","volx","price_vs_200ema_%"], ascending=False).head(max_rows)
    # Simple monospaced table
    lines = ["*Swing Scanner — Matches*", "```", f"{ 'SYMBOL':<16}{'CLOSE':>10}{'RSI':>8}{'>200EMA%':>10}{'VOLx':>8}"]
    for _, row in view.iterrows():
        lines.append(f"{row['symbol']:<16}{row['close']:>10.2f}{row['rsi14']:>8.1f}{row['price_vs_200ema_%']:>10.1f}{row['volx']:>8.2f}")
    lines.append("```")
    lines.append("_Filters: Price>200EMA, EMA50>=EMA200, RSI≥60, 20D Breakout, Vol ≥1.5×20D avg._")
    return "\n".join(lines)


def main():
    started = datetime.now(timezone.utc)
    print(f"[INFO] Swing Scanner start: {started.isoformat()}")

    symbols = read_tickers()
    print(f"[INFO] Symbols: {len(symbols)}")

    results = []
    for i, sym in enumerate(symbols, 1):
        try:
            res = analyze_symbol(sym)
            if res:
                results.append(res)
            else:
                print(f"[SKIP] {sym}: insufficient data")
        except Exception:
            print(f"[ERROR] {sym}:\n{traceback.format_exc()}")
        if i % 25 == 0:
            print(f"[INFO] Processed {i}/{len(symbols)}...")

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values(["passed","rsi14","volx"], ascending=[False, False, False], inplace=True)
    else:
        df = pd.DataFrame(columns=["symbol","close","rsi14","ema50","ema200","vol","vol20","volx","breakout","price_vs_200ema_%","passed"])

    out_csv = "scan_results.csv"
    df.to_csv(out_csv, index=False)
    print(f"[INFO] Saved {out_csv} with {len(df)} rows; {df['passed'].sum() if 'passed' in df else 0} matches.")

    # Telegram alert
    try:
        winners = df[df["passed"]] if not df.empty and "passed" in df.columns else pd.DataFrame()
        message = format_telegram_table(winners)
        telegram_send(message)
    except Exception:
        print("[WARN] Failed to send Telegram summary:")
        traceback.print_exc()

    print("[INFO] Done.")


if __name__ == "__main__":
    main()
````

---

## `.github/workflows/scan.yml`

```yaml
name: Swing Scanner

on:
  workflow_dispatch:
  schedule:
    - cron: "*/15 * * * *"  # every 15 minutes

jobs:
  run-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install yfinance pandas numpy requests

      - name: Run scanner
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          TICKERS: ${{ secrets.TICKERS }}  # optional, e.g., "RELIANCE.NS,TCS.NS,INFY.NS"
          MIN_RSI: "60"
          VOLUME_MULTIPLIER: "1.5"
          BREAKOUT_LOOKBACK: "20"
          EMA_FAST: "50"
          EMA_SLOW: "200"
          PERIOD: "6mo"
          INTERVAL: "1d"
        run: |
          python scanner.py

      - name: Upload scan results
        uses: actions/upload-artifact@v4
        with:
          name: scan_results
          path: scan_results.csv
```

---

### ✅ Setup Steps (quick)

1. Create a **private repo** (recommended). Add the two files above.
2. In **Repo → Settings → Secrets and variables → Actions → New repository secret**, add:

   * `TELEGRAM_TOKEN` → your bot token
   * `TELEGRAM_CHAT_ID` → your chat ID (e.g., `665594180`)
   * *(Optional)* `TICKERS` → comma-separated list, e.g., `RELIANCE.NS,TCS.NS,INFY.NS,...`
3. Commit & push. Run the workflow from **Actions → Swing Scanner → Run workflow** or wait for the schedule.
4. (Optional) Add a `tickers.csv` file to the repo root with one symbol per line if you don’t use `TICKERS`.

### Notes

* Uses **Yahoo Finance** for simplicity. For **Angel One** or **Fyers** real-time, we can swap the data source next.
* The filter logic is easy to tweak via environment variables in the workflow.
* Output CSV is uploaded as an artifact each run.
