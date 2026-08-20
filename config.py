"""Global configuration constants — DB path and timeframe settings shared across all modules."""
import datetime
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


def get_ist_now():
    """
    सद्य IST वेळ (datetime object) — सर्व्हरची local वेळ (datetime.datetime.now(), जी Streamlit Cloud
    सारख्या UTC सर्व्हरवर चुकीची ठरते) वापरण्याऐवजी, नेहमी UTC पासून योग्य +5:30 करून काढलेली खरी IST वेळ.
    """
    return datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)


def get_ist_today():
    """सद्य IST तारीख (date object) — datetime.date.today() ऐवजी, तीच वरची अडचण तारखेसाठीही."""
    return get_ist_now().date()
