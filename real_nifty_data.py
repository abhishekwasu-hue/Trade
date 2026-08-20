"""
real_nifty_data.py
----------------------
वापरकर्त्याने दिलेला **खरा** NIFTY50 ऐतिहासिक 1-मिनिट candle डेटा (2015-01-09 ते 2024-03-27, 852,087
bars) — data/nifty50_1min.parquet मध्ये कायमचा साठवलेला. यापुढे सर्व backtest (A1 Engine + नवीन ४
strategies दोन्ही) याच खऱ्या डेटावर चालतात — कुठलाही synthetic/random-walk डेटा वापरला जात नाही.

⚠️ महत्त्वाची मर्यादा: या डेटासेटमध्ये खरा Volume नाही (स्रोत CSV मध्येच नव्हता) — volume हा नेहमी 0
असतो. VWAP strategy त्यामुळे प्रत्यक्षात साधी सरासरी (TWAP सारखी) बनते, खरी Volume-Weighted नाही.
bb_squeeze चा volume_spike_multiplier gate या डेटावर कधीच खरा अर्थ देणार नाही (कायम volume=0).
"""
import os
import pandas as pd

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "nifty50_1min.parquet")

HAS_REAL_VOLUME = False  # स्पष्ट, तपासण्यायोग्य ध्वज — या डेटासेटमध्ये खरा volume नाही
DATA_START = pd.Timestamp("2015-01-09")
DATA_END = pd.Timestamp("2024-03-27")


def load_nifty_1min(from_date=None, to_date=None):
    """
    साठवलेला खरा NIFTY50 1-मिनिट डेटा वाचणे, ऐच्छिक तारीख-रेंज फिल्टरसह.
    from_date/to_date दिले नाहीत तर संपूर्ण डेटासेट (2015-2024) परत मिळतो.
    """
    if not os.path.exists(_DATA_PATH):
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = pd.read_parquet(_DATA_PATH)
    if from_date is not None:
        df = df[df["timestamp"] >= pd.Timestamp(from_date)]
    if to_date is not None:
        df = df[df["timestamp"] <= pd.Timestamp(to_date) + pd.Timedelta(days=1)]
    return df.reset_index(drop=True)


def resample_ohlc(df, interval_minutes):
    """1-मिनिट डेटा दिलेल्या मिनिटांच्या interval मध्ये resample करणे (उदा. 15 -> 15-मिनिट candles)."""
    if df is None or df.empty:
        return df
    df = df.set_index("timestamp")
    rule = f"{interval_minutes}min"
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    resampled = df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
    return resampled.reset_index()


def resample_daily(df):
    """
    प्रत्येक ट्रेडिंग-दिवसाचं एकच candle (कॅलेंडर तारखेनुसार गटबद्ध — साध्या 1440-मिनिट rolling window ने
    नाही, कारण NSE चे तास 9:15-15:30 आहेत, पूर्ण 24 तास नाही).
    """
    if df is None or df.empty:
        return df
    df = df.copy()
    df["date_only"] = df["timestamp"].dt.date
    daily = df.groupby("date_only").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"),
    ).reset_index()
    daily["timestamp"] = pd.to_datetime(daily["date_only"])
    return daily[["timestamp", "open", "high", "low", "close", "volume"]]


def load_nifty_resampled(interval_minutes, from_date=None, to_date=None):
    """load_nifty_1min + resample_ohlc/resample_daily एकत्र — सर्वात सामान्य वापर."""
    df_1min = load_nifty_1min(from_date, to_date)
    if interval_minutes == 1:
        return df_1min
    if interval_minutes == "day":
        return resample_daily(df_1min)
    return resample_ohlc(df_1min, interval_minutes)
