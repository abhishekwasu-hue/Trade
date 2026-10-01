"""
read_cache.py
------------------------------
🎓 Slippage -- manage_open_trades() प्रत्येक OPEN trade साठी प्रत्येक cycle ला `cloud_db.get_strategy_settings()` आणि
`get_next_level_in_direction()` (दोन्ही प्रत्येक वेळी नवा Supabase connection उघडतात, ~१००-४०० ms) बोलावतं. ५ सेकंदांच्या (आणि
सेकंदाच्या आतल्या) cycle मध्ये हाच वेळ खरा उशीर बनतो. हा लहान TTL-cache फक्त monitor प्रोसेसमध्ये (त्यांच्या `main` मध्ये
स्पष्टपणे install केल्यावर) चालतो -- import करताच काहीही बदलत नाही, म्हणून बाकीचे bots/Dashboard/tests अबाधित.
Dashboard मधून exit-सेटिंग बदलल्यास ती `ttl` सेकंदांच्या आत monitor ला लागू होते.
"""
import functools
import threading
import time


def ttl_cached(fn, ttl, clock=time.monotonic):
    lock = threading.Lock()
    store = {}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        now = clock()
        with lock:
            hit = store.get(key)
            if hit is not None and now - hit[0] < ttl:
                return hit[1]
        value = fn(*args, **kwargs)
        with lock:
            store[key] = (now, value)
        return value

    wrapper.cache_clear = store.clear
    wrapper.__wrapped__ = fn
    return wrapper


def install_monitor_read_cache(cloud_db_module, settings_ttl=10.0, level_ttl=30.0, clock=time.monotonic):
    """cloud_db चे दोन वाचन-function TTL-cached आवृत्त्यांनी बदलतो. आधीच install केलेलं असेल तर पुन्हा wrap करत नाही."""
    for name, ttl in (("get_strategy_settings", settings_ttl), ("get_next_level_in_direction", level_ttl)):
        current = getattr(cloud_db_module, name)
        if hasattr(current, "cache_clear"):
            continue
        setattr(cloud_db_module, name, ttl_cached(current, ttl, clock))
