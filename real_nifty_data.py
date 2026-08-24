"""
real_nifty_data.py
----------------------
वापरकर्त्याने दिलेला **खरा** NIFTY50 ऐतिहासिक डेटा — दोन स्रोत, कायमचे साठवलेले:
  १. data/nifty50_1min.parquet — 1-मिनिट candles (2015-01-09 ते 2024-03-27, 852,087 bars, खरा
     volume नाही — स्रोत CSV मध्येच नव्हता)
  २. data/nifty50_daily_extension.parquet — खरा दैनिक (daily) डेटा (2024-03-28 ते आजपर्यंत, NSE च्या
     रोजच्या bhav-copy स्वरूपात, **खरा Shares-Traded volume सकट**)
यापुढे सर्व backtest (A1 Engine + नवीन ४ strategies दोन्ही) याच खऱ्या डेटावर चालतात — कुठलाही
synthetic/random-walk डेटा वापरला जात नाही.

⚠️ महत्त्वाची मर्यादा: 1-मिनिट भागात (2015-2024-03-27) खरा Volume नाही (volume नेहमी 0). दैनिक
extension भागात (2024-03-28 पासून पुढे) मात्र खरा volume आहे. VWAP/bb_squeeze strategies त्यामुळे
जुन्या कालावधीत साध्या सरासरीसारख्या वागतात, नवीन कालावधीत खऱ्या Volume-आधारित पद्धतीने.

15-मिनिट/1-तास सारखे intraday timeframes फक्त 1-मिनिट भागातूनच (2024-03-27 पर्यंत) मिळतात — दैनिक
extension मध्ये फक्त एक दैनिक candle प्रति दिवस आहे, त्यातून intraday resample करता येत नाही.
"""
import os
import pandas as pd

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "nifty50_1min.parquet")
_DAILY_EXT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "nifty50_daily_extension.parquet")

HAS_REAL_VOLUME = False  # स्पष्ट, तपासण्यायोग्य ध्वज — 1-मिनिट भागात खरा volume नाही (दैनिक extension मध्ये आहे)
DATA_START = pd.Timestamp("2015-01-09")
DATA_END = pd.Timestamp("2024-03-27")          # 1-मिनिट डेटाची शेवटची तारीख (intraday साठी मर्यादा)
DAILY_DATA_END = pd.Timestamp("2026-08-20")     # दैनिक extension सकट, एकूण डेटाची शेवटची तारीख


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


def load_daily_extension(from_date=None, to_date=None):
    """खरा दैनिक extension डेटा (2024-03-28 पासून पुढे, खरा volume सकट) वाचणे."""
    if not os.path.exists(_DAILY_EXT_PATH):
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = pd.read_parquet(_DAILY_EXT_PATH)
    if from_date is not None:
        df = df[df["timestamp"] >= pd.Timestamp(from_date)]
    if to_date is not None:
        df = df[df["timestamp"] <= pd.Timestamp(to_date)]
    return df.reset_index(drop=True)


def load_nifty_daily_combined(from_date=None, to_date=None):
    """
    1-मिनिट डेटावरून resample केलेला दैनिक भाग (2015-01-09 ते 2024-03-27, volume=0) आणि खरा दैनिक
    extension डेटा (2024-03-28 पासून पुढे, खरा volume सकट) — दोन्ही सलगपणे जोडून एकच सलग दैनिक मालिका
    (2015 पासून आजपर्यंत) देणे — Swing backtest साठी सर्वात व्यापक, खरा डेटा.
    """
    df1 = pd.read_parquet(_DATA_PATH) if os.path.exists(_DATA_PATH) else pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    if from_date is not None:
        df1 = df1[df1["timestamp"] >= pd.Timestamp(from_date)]
    df1 = df1[df1["timestamp"] <= DATA_END + pd.Timedelta(days=1)]
    daily_from_1min = resample_daily(df1) if not df1.empty else pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    ext_from = max(pd.Timestamp(from_date), DATA_END + pd.Timedelta(days=1)) if from_date is not None else DATA_END + pd.Timedelta(days=1)
    daily_ext = load_daily_extension(ext_from, to_date)

    combined = pd.concat([daily_from_1min, daily_ext], ignore_index=True)
    combined = combined.sort_values("timestamp").drop_duplicates(subset="timestamp").reset_index(drop=True)
    if to_date is not None:
        combined = combined[combined["timestamp"] <= pd.Timestamp(to_date)]
    return combined.reset_index(drop=True)


def load_nifty_resampled(interval_minutes, from_date=None, to_date=None):
    """load_nifty_1min + resample_ohlc/resample_daily एकत्र — सर्वात सामान्य वापर.
    'day' साठी 1-मिनिट + दैनिक extension दोन्ही स्रोत एकत्र (load_nifty_daily_combined), 2015 ते आजपर्यंत."""
    if interval_minutes == "day":
        return load_nifty_daily_combined(from_date, to_date)
    df_1min = load_nifty_1min(from_date, to_date)
    if interval_minutes == 1:
        return df_1min
    return resample_ohlc(df_1min, interval_minutes)
