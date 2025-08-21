# config.py
import os

# --- Telegram (supports multiple secret names) ---
TELEGRAM_BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")

# --- Data settings ---
INTERVAL = os.getenv("INTERVAL", "1d")   # "1d", "1h", etc.
PERIOD   = os.getenv("PERIOD", "1y")     # history length

# --- Strategy dials (loosened defaults for testing) ---
VOL_MULT       = float(os.getenv("VOL_MULT", "1.15"))   # volume vs 20d avg
RSI_MIN        = float(os.getenv("RSI_MIN", "45"))      # momentum floor
ATR_STOP_MULT  = float(os.getenv("ATR_STOP_MULT", "1.5"))
ATR_TRAIL_MULT = float(os.getenv("ATR_TRAIL_MULT", "3.0"))
BO_LOOKBACK    = int(os.getenv("BO_LOOKBACK", "12"))    # prior N-day high (excluding today)

# --- Messaging & behavior ---
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
SEND_EMPTY_REPORTS = os.getenv("SEND_EMPTY_REPORTS", "true").lower() == "true"
MAX_PER_MSG = int(os.getenv("MAX_PER_MSG", "30"))

# --- Diagnostics (optional) ---
DIAG_MODE = os.getenv("DIAG_MODE", "false").lower() == "true"
