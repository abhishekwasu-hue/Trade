"""process_lock.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Duplicate-Order Protection, गंभीर यादीतला
पाचवा मुद्दा) — तिन्ही bots (dynamic_sr_instant_trader.py/srv2_momentum_reversal_strategy.py/
classic_sr_reversal_trader.py) VPS crontab वर दर १ मिनिटाला चालतात. एखादी invocation (नेटवर्क
मंदी/Upstox retry-backoff मुळे) १ मिनिटापेक्षा जास्त वेळ घेते, तर cron पुढची invocation त्याच
वेळी, समांतर सुरू करतो — दोन्ही प्रोसेस जवळपास एकाच क्षणी database.has_open_trade_from_source()
तपासतात (check-then-insert मध्ये आधी कुठलाही lock नव्हता), दोन्हींना "उघडी position नाही" दिसतं,
आणि दोन्हीही डुप्लिकेट (खरे, LIVE) ऑर्डर पाठवू शकतात.

OS-पातळीवरचं (fcntl) advisory file-lock — प्रत्येक bot script साठी स्वतंत्र लॉक फाईल (data/
फोल्डर मध्ये, .gitignore मध्ये आधीच वगळलेलं) — हे रोखतं: आधीचीच invocation अजून चालू असेल, तर
नवीन invocation कुठलाही trade-check/order-placement न करताच, लगेच सुरक्षितपणे थांबते.
"""
import fcntl
import os

from config import DATA_DIR


class ProcessLockHeld(Exception):
    """या नावाचा lock आधीच दुसऱ्या (अजून चालू असलेल्या) प्रोसेसकडे आहे."""


class ProcessLock:
    """with ProcessLock("bot_name"): ... — त्याच नावाची आधीची invocation अजून चालू असेल, तर
    __enter__ लगेच ProcessLockHeld देतो (ब्लॉक करत नाही — cron ने पुढची invocation लगेच,
    सुरक्षितपणे वगळावी, वाट बघत थांबू नये)."""

    def __init__(self, name):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._path = os.path.join(DATA_DIR, f"{name}.lock")
        self._fh = None

    def __enter__(self):
        self._fh = open(self._path, "w")
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._fh.close()
            self._fh = None
            raise ProcessLockHeld(f"'{self._path}' आधीच दुसऱ्या (अजून चालू असलेल्या) प्रोसेसकडे लॉक आहे")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fh is not None:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()
        return False
