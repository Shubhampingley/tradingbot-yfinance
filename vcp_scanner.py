import os
import time
import math
import pandas as pd
import numpy as np
import yfinance as yf

CSV_INPUT = "nifty500.csv"          # must contain a column named SYMBOL
CSV_OUTPUT = "vcp_candidates.csv"   # results written here

# ---------------------------
# Helpers
# ---------------------------
def load_symbols(path: str) -> list[str]:
    df = pd.read_csv(path)
    # Accept a few common header variants, default to SYMBOL
    for col in ["SYMBOL", "Symbol", "symbol", "Ticker", "ticker"]:
        if col in df.columns:
            syms = df[col].dropna().astype(str).str.strip().tolist()
            return [s for s in syms if s]
    raise SystemExit(f"No SYMBOL/Ticker column found in {path}. Columns={list(df.columns)}")

def true_range(h, l, c_prev):
    return np.maximum(h - l, np.maximum(np.abs(h - c_prev), np.abs(l - c_prev)))

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    df: daily OHLCV with index as datetime and columns: Open,High,Low,Close,Volume
    Returns df with added columns:
      - ATR20, ATRPCT20 (ATR as % of Close)
      - R10PCT (10-day range as % of Close)
      - VOL10, VOL50 (SMA)
      - HIGH50 (rolling 50d high)
    """
    df = df.copy()
    df["Close_shift"] = df["Close"].shift(1)
    tr = true_range(df["High"].values, df["Low"].values, df["Close_shift"].values)
    df["TR"] = tr
    df["ATR20"] = pd.Series(tr, index=df.index).rolling(20).mean()
    df["ATRPCT20"] = (df["ATR20"] / df["Close"]) * 100.0

    # 10-day range percent
    rolling_high_10 = df["High"].rolling(10).max()
    rolling_low_10 = df["Low"].rolling(10).min()
    df["R10"] = rolling_high_10 - rolling_low_10
    df["R10PCT"] = (df["R10"] / df["Close"]) * 100.0

    # Volume SMAs
    df["VOL10"] = df["Volume"].rolling(10).mean()
    df["VOL50"] = df["Volume"].rolling(50).mean()

    # 50-day high (pivot zone)
    df["HIGH50"] = df["High"].rolling(50).max()

    return df

def is_vcp_row(row_now, row_then, tight_range_pct=6.0, near_high_pct=3.0, vol_rel_threshold=0.9):
    """
    VCP heuristic:
      1) ATR% now < ATR% 20 trading days ago (contraction)
      2) 10d range% now < tight_range_pct (tight base)
      3) Close within near_high_pct of 50d high (near pivot)
      4) Optional: 10d vol < 50d vol * vol_rel_threshold (volume dry-up)
    """
    if any(pd.isna(v) for v in [row_now.ATRPCT20, row_then.ATRPCT20, row_now.R10PCT, row_now.HIGH50, row_now.Close]):
        return False

    contraction = row_now.ATRPCT20 < row_then.ATRPCT20
    tight = row_now.R10PCT <= tight_range_pct

    # near 50d high
    if row_now.HIGH50 <= 0:
        return False
    near_high = (row_now.HIGH50 - row_now.Close) / row_now.HIGH50 * 100.0 <= near_high_pct

    # volume dry-up (optional, not strict — we’ll treat as soft condition)
    vol_ok = True
    if not math.isnan(row_now.VOL10) and not math.isnan(row_now.VOL50) and row_now.VOL50 > 0:
        vol_ok = (row_now.VOL10 / row_now.VOL50) <= vol_rel_threshold

    # We prioritize quantity; require the 3 structural checks, make volume optional
    return contraction and tight and near_high and vol_ok

def scan_ticker(ticker: str) -> dict | None:
    """
    Returns dict with metrics if ticker matches VCP today, else None.
    """
    try:
        # ~8 months to ensure we have 50d windows with buffer
        df = yf.download(ticker, period="8mo", interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None

        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if df.shape[0] < 60:
            return None

        df = compute_indicators(df)
        # Compare today vs ~1 month ago (20 trading days)
        if df.shape[0] < 70:
            idx_then = -30  # fallback if shorter history
        else:
            idx_then = -20

        row_now = df.iloc[-1]
        row_then = df.iloc[idx_then]

        if is_vcp_row(row_now, row_then):
            # Prepare a compact result row
            close = float(row_now.Close)
            high50 = float(row_now.HIGH50)
            pivot_gap_pct = (high50 - close) / high50 * 100.0 if high50 > 0 else np.nan
            return {
                "Ticker": ticker,
                "Close": round(close, 2),
                "R10%": round(float(row_now.R10PCT), 2),
                "ATR%20": round(float(row_now.ATRPCT20), 2),
                "Near50H%": round(pivot_gap_pct, 2),          # how far below 50d high
                "Vol10/Vol50": round(float(row_now.VOL10 / row_now.VOL50), 2) if row_now.VOL50 and not math.isnan(row_now.VOL50) else np.nan,
            }
        return None
    except Exception as e:
        print(f"[WARN] {ticker} error: {e}")
        return None

# ---------------------------
# Main
# ---------------------------
def main():
    symbols = load_symbols(CSV_INPUT)
    print(f"Loaded {len(symbols)} symbols from {CSV_INPUT}")

    results = []
    for i, sym in enumerate(symbols, start=1):
        print(f"[{i}/{len(symbols)}] Scanning {sym} ...")
        hit = scan_ticker(sym)
        if hit:
            results.append(hit)
        # polite pacing to avoid throttling
        time.sleep(0.25)

    if results:
        out = pd.DataFrame(results).sort_values(["Near50H%","R10%","ATR%20"])
        out.to_csv(CSV_OUTPUT, index=False)
        print(f"\n✅ Found {len(out)} VCP candidates. Saved -> {CSV_OUTPUT}")
        print(out.head(25).to_string(index=False))
    else:
        # Still create an empty file for downstream steps
        pd.DataFrame(columns=["Ticker","Close","R10%","ATR%20","Near50H%","Vol10/Vol50"]).to_csv(CSV_OUTPUT, index=False)
        print("\nℹ️ No VCP candidates today with current heuristic. File created:", CSV_OUTPUT)

if __name__ == "__main__":
    main()
