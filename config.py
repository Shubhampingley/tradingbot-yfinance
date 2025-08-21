import os

# Telegram (already set as GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# Data
INTERVAL = os.getenv("INTERVAL", "1d")     # daily bars
PERIOD   = os.getenv("PERIOD", "1y")       # lookback window for indicators

# Strategy dials (aggressive defaults)
VOL_MULT      = float(os.getenv("VOL_MULT", "1.5"))   # volume spike threshold vs 20d avg
RSI_MIN       = float(os.getenv("RSI_MIN", "50"))     # momentum floor
ATR_STOP_MULT = float(os.getenv("ATR_STOP_MULT", "1.5"))  # initial stop = Close - 1.5*ATR
ATR_TRAIL_MULT= float(os.getenv("ATR_TRAIL_MULT", "3.0")) # trailing stop distance

# Breakout window
BO_LOOKBACK   = int(os.getenv("BO_LOOKBACK", "20"))   # 20-day high breakout

TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
SEND_EMPTY_REPORTS = os.getenv("SEND_EMPTY_REPORTS", "true").lower() == "true"
MAX_PER_MSG = int(os.getenv("MAX_PER_MSG", "30"))
