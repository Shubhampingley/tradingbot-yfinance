# NSE Swing Scanner — loosened logic
# - Reads tickers from stocks.csv (must include column 'symbol')
# - Generates BUY and WATCH (near-breakout) signals
# - Sends results to Telegram
# - Robust against yfinance MultiIndex / 2-D column quirks
# - DIAG_MODE shows why a ticker failed

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
    TIMEZONE, SEND_EMPTY_REPORTS, MAX_PER_MSG, DIAG_MODE
)

# ------------------ IO & Utils ------------------

def load_tickers_csv(path: str = "stocks.csv"):
    df = pd.read_csv(path)
    if "symbol" not in [c.lower() for c in df.columns]:
        raise ValueError("stocks.csv must have a 'symbol' column")
    sym_col = [c for c in df.columns if c.lower() == "symbol"][0]
    df = df.rename(columns={sym_col: "symbol"})
    syms = df["symbol"].dropna().astype(str).tolist()
    return syms, df.set_index("symbol", drop=False)

def send_telegram(text: str):
    token = TELEGRAM_BOT_TOKEN
    chat  = TELEGRAM_CHAT_ID
    if not token or not chat:
        print("Telegram not configured; skipping...")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=20)
    print("Telegram status:", r.status_code, "| resp:", r.text[:200])

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def ist_timestamp(tzname=TIMEZONE):
    tzone = tz.gettz(tzname)
    return datetime.now(tzone).strftime("%Y-%m-%d %H:%M")

def meta_round(x, nd=2):
    return round(float(x), nd) if pd.notna(x) else None

# ------------------ Data Fetch (robust) ------------------

def _flatten_columns(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Flatten yfinance MultiIndex columns to a simple 1-D set."""
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = df.columns.get_level_values(0)
        if symbol in lvl0:
            df = df.xs(symbol, axis=1, level=0)
        else:
            df.columns = [c[-1] if isinstance(c, tuple) else str(c) for c in df.columns]
    return df

def fetch_ohlcv(symbol: str, period=PERIOD, interval=INTERVAL) -> pd.DataFrame:
    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        group_by="column",
        threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    df = _flatten_columns(df, symbol)
    # Normalize names, drop duplicate columns
    df = df.rename(columns=lambda c: str(c).strip().title())
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Ensure 1-D numeric Series
    for col in ["Open", "High", "Low", "Close", "Volume", "Adj Close"]:
        if col in df.columns:
            s = df[col]
            if isinstance(s, pd.DataFrame):  # squeeze any 2-D leftovers
                s = s.iloc[:, 0]
            df[col] = pd.to_numeric(s, errors="coerce")

    # Drop rows missing Close
    df = df.dropna(subset=["Close"])

    return df

# ------------------ Indicators & Signals ------------------

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Guarantee required columns exist and are numeric 1-D
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = np.nan
        s = out[col]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        out[col] = pd.to_numeric(s, errors="coerce")

    close = out["Close"]
    high  = out["High"]
    low   = out["Low"]
    vol   = out["Volume"].fillna(0)

    # Technicals
    out["EMA10"] = EMAIndicator(close, window=10).ema_indicator()
    out["EMA30"] = EMAIndicator(close, window=30).ema_indicator()

    out["RSI14"] = RSIIndicator(close, window=14).rsi()

    macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    out["MACD"]     = macd.macd()
    out["MACDsig"]  = macd.macd_signal()
    out["MACDhist"] = macd.macd_diff()

    atr = AverageTrueRange(high=high, low=low, close=close, window=14)
    out["ATR14"] = atr.average_true_range()

    volma20 = vol.rolling(20, min_periods=5).mean().replace(0, np.nan)
    out["VolMA20"]  = volma20
    out["VolRatio"] = vol / volma20

    # Prior N-day high (exclude today) for breakout test
    out["High20"]     = close.rolling(BO_LOOKBACK, min_periods=BO_LOOKBACK).max().shift(1)
    # Prior 10-bar swing low (exclude today)
    out["SwingLow10"] = low.rolling(10, min_periods=10).min().shift(1)

    return out

def buy_signal_row(row_prev, row, vol_mult=VOL_MULT, rsi_min=RSI_MIN):
    """
    LOOSER BUY: 4 ways to trigger
      A) Breakout: Close > prior N-day high, vol >= 0.9*VOL_MULT (min 0.9), EMA10>EMA30, RSI>=rsi_min, MACDhist>=0
      B) EMA cross: EMA10 crossed above EMA30 today, vol >= 0.9, RSI >= max(43, rsi_min-5)
      C) Trend-pullback: EMA10>EMA30, Close > EMA30, MACDhist>0, RSI >= max(45, rsi_min-3),
                         Close within 2% of prior N-day high
      D) Continuation: EMA10>EMA30, Close/EMA30 >= 1.01, MACDhist rising (today > yday),
                       RSI >= max(50, rsi_min), VolRatio >= 0.9
    """
    reasons = []

    # Common pieces
    ema10, ema30 = row.get("EMA10", np.nan), row.get("EMA30", np.nan)
    trend_up = pd.notna(ema10) and pd.notna(ema30) and (ema10 > ema30)
    macdh, macdh_prev = row.get("MACDhist", np.nan), row_prev.get("MACDhist", np.nan)
    macd_ok  = pd.notna(macdh) and (macdh >= 0)
    macd_rising = pd.notna(macdh) and pd.notna(macdh_prev) and (macdh > macdh_prev)

    volx = row.get("VolRatio", np.nan)
    vol_ok     = pd.notna(volx) and (volx >= float(vol_mult))
    vol_ok_09  = pd.notna(volx) and (volx >= 0.9)
    vol_ok_lo  = pd.notna(volx) and (volx >= max(0.9, float(vol_mult) * 0.9))

    rsi = row.get("RSI14", np.nan)
    rsi_ok    = pd.notna(rsi) and (rsi >= float(rsi_min)) and (rsi > row_prev.get("RSI14", rsi - 1))
    rsi_lo    = pd.notna(rsi) and (rsi >= max(43.0, float(rsi_min) - 5))
    rsi_cont  = pd.notna(rsi) and (rsi >= max(50.0, float(rsi_min)))

    highN = row.get("High20", np.nan)
    breakout = pd.notna(highN) and (row["Close"] > highN)

    # (A) Breakout mode (looser volume)
    mode_A = trend_up and breakout and (vol_ok or vol_ok_lo) and rsi_ok and macd_ok

    # (B) EMA cross mode (fresh trend start)
    crossed = pd.notna(row_prev.get("EMA10")) and pd.notna(row_prev.get("EMA30")) and \
              (row_prev["EMA10"] <= row_prev["EMA30"]) and (ema10 > ema30)
    mode_B = crossed and vol_ok_09 and rsi_lo

    # (C) Trend-pullback near prior high
    near_high = pd.notna(highN) and highN > 0 and 0 < (highN - row["Close"]) / highN <= 0.02  # 2%
    above_base = trend_up and (row["Close"] > ema30 if pd.notna(ema30) else False)
    mode_C = above_base and macd_ok and vol_ok_09 and (pd.notna(rsi) and rsi >= max(45.0, float(rsi_min) - 3)) and near_high

    # (D) Continuation (no breakout yet, but strong thrust)
    ema_gap_ok = trend_up and pd.notna(ema30) and (row["Close"] / ema30 >= 1.01)
    mode_D = ema_gap_ok and macd_rising and rsi_cont and vol_ok_09

    ok = bool(mode_A or mode_B or mode_C or mode_D)
    if not ok and DIAG_MODE:
        if not trend_up: reasons.append("trend")
        if not (breakout or near_high or ema_gap_ok): reasons.append("setup")
        if not (vol_ok or vol_ok_lo or vol_ok_09): reasons.append("volume")
        if not (rsi_ok or rsi_lo or rsi_cont): reasons.append("rsi")
        if not (macd_ok or macd_rising): reasons.append("macd")
    return ok, reasons

def watch_signal_row(row_prev, row):
    """
    WATCH (near-breakout) — widened:
      - EMA10>EMA30
      - Close within 3% of prior N-day high
      - VolRatio >= 0.8
      - RSI >= max(RSI_MIN-7, 40)
      - MACDhist >= 0
    """
    ema10, ema30 = row.get("EMA10", np.nan), row.get("EMA30", np.nan)
    trend_up = pd.notna(ema10) and pd.notna(ema30) and (ema10 > ema30)
    highN    = row.get("High20", np.nan)
    near = pd.notna(highN) and highN > 0 and 0 < (highN - row["Close"]) / highN <= 0.03  # 3%
    vol_ok = pd.notna(row.get("VolRatio", np.nan)) and row["VolRatio"] >= 0.8
    rsi_ok = pd.notna(row.get("RSI14", np.nan)) and row["RSI14"] >= max(float(RSI_MIN) - 7, 40)
    macd_ok = pd.notna(row.get("MACDhist", np.nan)) and row["MACDhist"] >= 0
    return trend_up and near and vol_ok and rsi_ok and macd_ok

def build_meta(today):
    close = float(today["Close"])
    atr   = float(today["ATR14"]) if pd.notna(today["ATR14"]) else 0.0
    swing_low = today.get("SwingLow10", np.nan)

    stop_atr = close - ATR_STOP_MULT * atr if atr > 0 else np.nan
    stop_swing = float(swing_low) if pd.notna(swing_low) else np.nan
    if pd.notna(stop_atr) and pd.notna(stop_swing):
        stop = min(stop_atr, stop_swing)
    else:
        stop = stop_atr if pd.notna(stop_atr) else stop_swing

    if pd.notna(stop):
        rr = close - stop
        target = close + 2 * rr
    else:
        target = close + 3 * atr if atr > 0 else np.nan

    trail_dist = ATR_TRAIL_MULT * atr if atr > 0 else np.nan

    meta = {
        "close": meta_round(today.get("Close")),
        "ema10": meta_round(today.get("EMA10")),
        "ema30": meta_round(today.get("EMA30")),
        "rsi14": meta_round(today.get("RSI14"), 1),
        "macdh": meta_round(today.get("MACDhist"), 3),
        "volx":  meta_round(today.get("VolRatio"), 2),
        "atr":   round(float(atr), 2) if atr > 0 else None,
        "stop":  meta_round(stop),
        "target":meta_round(target),
        "trail": meta_round(trail_dist),
    }
    return meta

# ------------------ Per-symbol Analysis ------------------

def analyze_symbol(sym: str):
    df = fetch_ohlcv(sym)
    if df.empty:
        return None if not DIAG_MODE else {"diag": "no_data"}
    if len(df) < max(50, BO_LOOKBACK + 5):
        return None if not DIAG_MODE else {"diag": "insufficient_bars"}

    # If volume is zero or NaN for most rows, skip (bad data)
    vol = df.get("Volume", pd.Series(dtype=float))
    if vol.isna().mean() > 0.5 or (vol.fillna(0) == 0).mean() > 0.5:
        return None if not DIAG_MODE else {"diag": "illiquid_or_bad_volume"}

    ind = compute_indicators(df)
    today = ind.iloc[-1]
    yday  = ind.iloc[-2]

    ok_buy, reasons = buy_signal_row(yday, today, vol_mult=VOL_MULT, rsi_min=RSI_MIN)
    if ok_buy:
        meta = build_meta(today)
        meta["type"] = "BUY"
        return meta

    if watch_signal_row(yday, today):
        return {
            "type": "WATCH",
            "close": meta_round(today.get("Close")),
            "ema10": meta_round(today.get("EMA10")),
            "ema30": meta_round(today.get("EMA30")),
            "rsi14": meta_round(today.get("RSI14"), 1),
            "macdh": meta_round(today.get("MACDhist"), 3),
            "volx":  meta_round(today.get("VolRatio"), 2),
        }

    return None if not DIAG_MODE else {"diag": ";".join(reasons)}

# ------------------ Main ------------------

def main():
    syms, _ = load_tickers_csv("stocks.csv")
    buys, watch, errors, diags = [], [], [], []

    for s in syms:
        try:
            info = analyze_symbol(s)
            if info and info.get("type") == "BUY":
                buys.append(
                    f"{s} → BUY | Close {info['close']} | EMA10 {info['ema10']} | EMA30 {info['ema30']} | "
                    f"RSI {info['rsi14']} | MACDΔ {info['macdh']} | Vol× {info['volx']} | "
                    f"SL {info.get('stop')} | TGT {info.get('target')} | Trail≈{info.get('trail')}"
                )
            elif info and info.get("type") == "WATCH":
                watch.append(
                    f"{s} → WATCH | Close {info['close']} | EMA10 {info['ema10']} | EMA30 {info['ema30']} | "
                    f"RSI {info['rsi14']} | MACDΔ {info['macdh']} | Vol× {info['volx']} | Near {BO_LOOKBACK}d High"
                )
            elif DIAG_MODE and info and "diag" in info:
                diags.append(f"{s}: {info['diag']}")
        except Exception as e:
            errors.append(f"{s}: {e}")

    header = (
        f"📈 NSE Swing Scan @ {ist_timestamp()} ({TIMEZONE})\n"
        f"Interval={INTERVAL} Period={PERIOD}\n"
        f"Breakout>{BO_LOOKBACK}d | Vol≥{VOL_MULT}× | RSI≥{RSI_MIN}"
    )

    sent_any = False
    if buys:
        send_telegram(header + "\n\n✅ BUY candidates\n" + "\n".join(buys))
        sent_any = True
    if watch:
        send_telegram("👀 WATCH list (near breakout)\n" + "\n".join(watch))
        sent_any = True

    if not sent_any and SEND_EMPTY_REPORTS:
        send_telegram(header + "\n\n— No qualifying BUY/WATCH signals —")

    if DIAG_MODE and diags:
        send_telegram("🔎 Diagnostics (first 20)\n" + "\n".join(diags[:20]))

    if errors:
        send_telegram("⚠️ Scan errors\n" + "\n".join(errors[:MAX_PER_MSG]))

if __name__ == "__main__":
    main()
