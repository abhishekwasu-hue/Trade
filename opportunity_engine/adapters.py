"""opportunity_engine/adapters.py — column नावे आणि timezone मधली तफावत (फक्त column/tz; कुठलीही गणना नाही).

जुन्या `mtf_pullback_strategy` ला `Date/High/Low/Close` (मोठी अक्षरे) हवे; आपल्याला lowercase `timestamp/open/high/low/close`;
Upstox candles tz-aware (+05:30), offline डेटा naive IST. engine आत नेहमी *naive IST, lowercase, कालानुक्रमे, duplicates शिवाय*.
"""
import pandas as pd

_RENAMES = {"Date": "timestamp", "Datetime": "timestamp", "date": "timestamp", "datetime": "timestamp", "Timestamp": "timestamp",
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
OHLC = ["open", "high", "low", "close"]


def to_engine_frame(df):
    """कुठल्याही स्वरूपाचा OHLC df -> engine चा स्वच्छ df. आवश्यक columns नसतील तर रिकामा df (exception नाही)."""
    empty = pd.DataFrame(columns=["timestamp"] + OHLC)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return empty
    out = df.rename(columns={k: v for k, v in _RENAMES.items() if k in df.columns and v not in df.columns}).copy()
    if any(c not in out.columns for c in ["timestamp"] + OHLC):
        return empty
    ts = pd.to_datetime(out["timestamp"], errors="coerce")
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    out["timestamp"] = ts.astype("datetime64[ns]")
    for c in OHLC:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["timestamp"] + OHLC).sort_values("timestamp").drop_duplicates("timestamp")
    return out.reset_index(drop=True)


def to_legacy_frame(df):
    """engine df -> `Date/Open/High/Low/Close` (जुन्या mtf_pullback_strategy functions साठी)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close"])
    return df.rename(columns={"timestamp": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
