import os
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from dateutil import tz

import yfinance as yf
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    INTERVAL, PERIOD, VOL_MULT, RSI_MIN,
    ATR_STOP_MULT, ATR_TRAIL_MULT, BO_LOOKBACK,
    TIMEZONE, SEND_EMPTY_REPORTS, MAX_PER_MSG
)

# ----- IO helpers -----
def load_tickers_csv(path="stocks.csv"):
    df = pd.read_csv(path)
    if "symbol" not in df.columns:
        raise ValueError("stocks.csv must have a 'symbol' column")
    syms = df["symbol"].dropna().astype(str).tolist()
    return syms, df.set_index("symbol", drop=False)

def fetch_ohlcv(symbol: str, period=PERIOD, interval=INTERVAL) -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    # Normalize column names
    df = df.rename(columns=lambda c: c.title())
    return df

def send_telegram(text: str):
    token = TELEGRAM_BOT_TOKEN
    chat  = TELEGRAM_CHAT_ID
    if not token or not chat:
        print("Telegram not configured; skipping...")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=15)
    if r.status_code != 200:
        print("Telegram error:", r.text)

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

# ----- Indicators & Signals -----
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]
    low   = out["Low"]
    high  = out["High"]
    vol   = out["Volume"]

    out["EMA10"] = EMAIndicator(close, window=10).ema_indicator()
    out["EMA30"] = EMAIndicator(close, window=30).ema_indicator()

    rsi = RSIIndicator(close, window=14)
    out["RSI14"] = rsi.rsi()

    macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    out["MACD"] = macd.macd()
    out["MACDsig"] = macd.macd_signal()
    out["MACDhist"] = macd.macd_diff()

    atr = AverageTrueRange(high=high, low=low, close=close, window=14)
    out["ATR14"] = atr.average_true_range()

    out["VolMA20"] = vol.rolling(20).mean()
    out["VolRatio"] = vol / out["VolMA20"]

    # 20-day high excluding today (shifted) for breakout test
    out["High20"] = close.rolling(BO_LOOKBACK).max().shift(1)
    # recent swing low (10 bars) excluding today
    out["SwingLow10"] = low.rolling(10).min().shift(1)

    return out

def buy_signal_row(row_prev, row):
    # Rules:
    # 1) Trend: EMA10 > EMA30
    # 2) Breakout: Close > prior 20d high
    # 3) Volume: VolRatio >= VOL_MULT
    # 4) Momentum: RSI >= RSI_MIN and rising (today > yesterday)
    # 5) MACD confirmation: histogram > 0
    cond_trend = (row["EMA10"] > row["EMA30"])
    cond_break = (row["Close"] > row["High20"]) if pd.notna(row["High20"]) else False
    cond_vol   = (row["VolRatio"] >= VOL_MULT)
    cond_rsi   = (row["RSI14"] >= RSI_MIN) and (row["RSI14"] > row_prev.get("RSI14", row["RSI14"] - 1))
    cond_macd  = (row["MACDhist"] > 0)

    return all([cond_trend, cond_break, cond_vol, cond_rsi, cond_macd])

def analyze_symbol(sym: str):
    df = fetch_ohlcv(sym)
    if df.empty or len(df) < max(50, BO_LOOKBACK + 5):
        return None

    ind = compute_indicators(df)
    today = ind.iloc[-1]
    yday  = ind.iloc[-2]

    if buy_signal_row(yday, today):
        close = float(today["Close"])
        atr   = float(today["ATR14"]) if not np.isnan(today["ATR14"]) else 0.0
        swing_low = today.get("SwingLow10", np.nan)
        # Initial stop as max of: ATR-based or recent swing low (slightly conservative)
        stop_atr = close - ATR_STOP_MULT * atr if atr > 0 else np.nan
        stop_swing = float(swing_low) if not np.isnan(swing_low) else np.nan
        if not np.isnan(stop_atr) and not np.isnan(stop_swing):
            stop = min(stop_atr, stop_swing)  # tighter of the two
        else:
            stop = stop_atr if not np.isnan(stop_atr) else stop_swing

        # Suggest target using 2R from stop if available, else 3*ATR
        if stop and not np.isnan(stop):
            rr = close - stop
            target = close + 2 * rr
        else:
            target = close + 3 * atr if atr > 0 else np.nan

        trail_dist = ATR_TRAIL_MULT * atr if atr > 0 else np.nan

        meta = {
            "close": round(close, 2),
            "ema10": round(float(today["EMA10"]), 2),
            "ema30": round(float(today["EMA30"]), 2),
            "rsi14": round(float(today["RSI14"]), 1),
            "macdh": round(float(today["MACDhist"]), 3),
            "volx":  round(float(today["VolRatio"]), 2),
            "atr":   round(float(atr), 2) if atr > 0 else None,
            "stop":  round(float(stop), 2) if stop and not np.isnan(stop) else None,
            "target":round(float(target), 2) if target and not np.isnan(target) else None,
            "trail": round(float(trail_dist), 2) if trail_dist and not np.isnan(trail_dist) else None,
        }
        return meta
    return None

def ist_timestamp(tzname=TIMEZONE):
    tzone = tz.gettz(tzname)
    return datetime.now(tzone).strftime("%Y-%m-%d %H:%M")

def main():
    syms, meta = load_tickers_csv("stocks.csv")
    buys = []
    errors = []

    for s in syms:
        try:
            info = analyze_symbol(s)
            if info:
                line = (
                    f"{s} → BUY | Close {info['close']} | EMA10 {info['ema10']} | EMA30 {info['ema30']} | "
                    f"RSI {info['rsi14']} | MACDΔ {info['macdh']} | Vol× {info['volx']} | "
                    f"SL {info['stop']} | TGT {info['target']} | Trail≈{info['trail']}"
                )
                buys.append(line)
        except Exception as e:
            errors.append(f"{s}: {e}")

    header = f"📈 NSE Swing Scan @ {ist_timestamp()} ({TIMEZONE})\nInterval={INTERVAL} Period={PERIOD}\nBreakout>{BO_LOOKBACK}d | Vol≥{VOL_MULT}× | RSI≥{RSI_MIN}"

    if buys:
        blocks = [header + "\n\n✅ BUY candidates"] + buys
        for chunk in chunk(blocks, MAX_PER_MSG):
            send_telegram("\n".join(chunk))
    elif SEND_EMPTY_REPORTS:
        send_telegram(header + "\n\n— No qualifying BUY signals —")

    if errors:
        send_telegram("⚠️ Scan errors\n" + "\n".join(errors[:MAX_PER_MSG]))

if __name__ == "__main__":
    main()
