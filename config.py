"""Global configuration constants — DB path and timeframe settings shared across all modules."""
import os

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_PATH = os.path.join(DATA_DIR, "historical_data.db")

TIMEFRAME_CONFIG = {
    "INTRADAY": {
        "structure": ("15minute", "15M"),
        "rsi": ("5minute", "5M"),
        "confirm": ("1minute", "1M"),
    },
    "SWING": {
        "structure": ("day", "Daily"),
        "rsi": ("1hour", "1H"),
        "confirm": ("1hour", "1H"),
    },
}
