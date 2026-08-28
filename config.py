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


# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — NSE च्या अधिकृत 2026 Equity/Derivatives Segment
# सुट्टी-यादीवरून (स्रोत: NSE India, groww.in/p/nse-holidays, ऑगस्ट 2026 मध्ये पडताळलेलं). वीकेंडला
# येणाऱ्या सुट्ट्या (उदा. महाशिवरात्री-रविवार) इथे नाहीत — त्या weekday-check मुळे आपोआप वगळल्या जातातच.
# ⚠️ ही यादी दरवर्षी NSE कडून नव्याने जाहीर होते — पुढच्या वर्षी अद्ययावत करावी लागेल.
NSE_HOLIDAYS_2026 = {
    datetime.date(2026, 1, 15),   # महानगरपालिका निवडणूक - महाराष्ट्र
    datetime.date(2026, 1, 26),   # प्रजासत्ताक दिन
    datetime.date(2026, 3, 3),    # होळी
    datetime.date(2026, 3, 26),   # श्री राम नवमी
    datetime.date(2026, 3, 31),   # श्री महावीर जयंती
    datetime.date(2026, 4, 3),    # गुड फ्रायडे
    datetime.date(2026, 4, 14),   # डॉ. बाबासाहेब आंबेडकर जयंती
    datetime.date(2026, 5, 1),    # महाराष्ट्र दिन
    datetime.date(2026, 5, 28),   # बकरी ईद
    datetime.date(2026, 6, 26),   # मुहर्रम
    datetime.date(2026, 9, 14),   # गणेश चतुर्थी
    datetime.date(2026, 10, 2),   # गांधी जयंती
    datetime.date(2026, 10, 20),  # दसरा
    datetime.date(2026, 11, 10),  # दिवाळी-बलिप्रतिपदा
    datetime.date(2026, 11, 24),  # गुरु नानक जयंती
    datetime.date(2026, 12, 25),  # ख्रिसमस
}


def is_trading_day(now_dt=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — आज व्यापार-दिवस आहे का (सोमवार-शुक्रवार, NSE सुट्टी
    नाही) — फक्त दिवस तपासतो, वेळ नाही. eod_market_report.py सारख्या दुपारी ४ वाजता (बाजार बंद
    झाल्यानंतर) चालणाऱ्या scripts साठी उपयुक्त — is_market_open() तिथे नेहमी False देईल (वेळ जुळत
    नाही म्हणून), पण आजचा दिवस स्वतः व्यापार-दिवस होता की नाही हे वेगळंच, इथे तपासलं जातं.
    """
    now_dt = now_dt or get_ist_now()
    if now_dt.weekday() >= 5:  # 5=शनिवार, 6=रविवार
        return False
    if now_dt.date() in NSE_HOLIDAYS_2026:
        return False
    return True


def is_market_open(now_dt=None, open_time=datetime.time(9, 15), close_time=datetime.time(15, 30)):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — NSE बाजार वेळेत आहे का (सोमवार ते शुक्रवार, डीफॉल्ट
    9:15 ते 15:30 IST, आणि आता NSE च्या अधिकृत सुट्टी-यादीनुसार सुट्टीचे दिवसही वगळले जातात).
    unattended scripts (oi_snapshot_collector.py, credit_spread_auto_trader.py,
    oi_signal_auto_trader.py) बाजार बंद असताना उगाच Option Chain fetch करू नयेत म्हणून.
    """
    now_dt = now_dt or get_ist_now()
    if not is_trading_day(now_dt):
        return False
    return open_time <= now_dt.time() <= close_time
