"""
Yahoo Finance (yfinance) द्वारे — कोणताही Upstox token न लागता — NIFTY/BANKNIFTY ऐतिहासिक candles
मिळवणे. Backtest/Signal Check साठी पर्यायी डेटा स्रोत — विशेषतः token उपलब्ध नसताना उपयोगी.

महत्त्वाची मर्यादा (Yahoo Finance च्या स्वतःच्याच धोरणामुळे, आपल्या कोडची चूक नाही):
- 15-मिनिटांचा (व इतर <1 दिवसाचा) डेटा फक्त गेल्या ~60 दिवसांपुरताच उपलब्ध असतो.
- Daily डेटा मात्र अनेक वर्षांचा उपलब्ध असतो (Swing साठी पूर्ण 10 वर्षांची रेंज चालेल).
"""
import datetime
import pandas as pd

YFINANCE_SYMBOL_MAP = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
YFINANCE_INTERVAL_MAP = {"15minute": "15m", "30minute": "30m", "hour": "60m", "day": "1d"}
YFINANCE_MAX_INTRADAY_DAYS = 59  # Yahoo चं स्वतःचं ~60 दिवसांचं धोरण, थोडं मार्जिन ठेवून


def get_yfinance_max_days(interval):
    """दिलेल्या interval साठी yfinance कडून जास्तीत जास्त किती दिवसांचा डेटा मागता येईल ते सांगणे."""
    if interval == "day":
        return 3650
    if interval == "hour":
        return 729  # Yahoo चं धोरण: 60m (hourly) डेटा ~730 दिवसांपर्यंत उपलब्ध, 15m/30m पेक्षा जास्त सैल
    return YFINANCE_MAX_INTRADAY_DAYS


def fetch_yfinance_candles(symbol, interval, from_date, to_date):
    """
    Yahoo Finance वरून candles मागवून आपल्या ॲपच्या नेहमीच्या candle-shape मध्ये (timestamp/open/high/
    low/close/volume/oi) बदलणे — जेणेकरून हे Upstox च्या fetch फंक्शन्ससाठी drop-in पर्याय म्हणून वापरता येईल.
    Returns (df, error_message) — यशस्वी झाल्यास error_message=None, अयशस्वी झाल्यास नेमकं कारण असलेला मजकूर
    (आधी सर्व अपयश शांतपणे रिकाम्या DataFrame मध्ये लपायचं — कारण कधीच कळायचं नाही; आता ते UI पर्यंत पोहोचतं).
    """
    empty_df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
    try:
        import yfinance as yf
    except ImportError as e:
        return empty_df, f"yfinance library उपलब्ध नाही (ImportError: {e}). requirements.txt मध्ये 'yfinance' आहे का तपासा."

    yf_symbol = YFINANCE_SYMBOL_MAP.get(symbol, symbol)
    yf_interval = YFINANCE_INTERVAL_MAP.get(interval, "1d")

    max_days = get_yfinance_max_days(interval)
    if (to_date - from_date).days > max_days:
        from_date = to_date - datetime.timedelta(days=max_days)

    try:
        ticker = yf.Ticker(yf_symbol)
        yf_df = ticker.history(
            start=from_date.strftime("%Y-%m-%d"),
            end=(to_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),  # end एक्सक्लुझिव्ह असतो
            interval=yf_interval,
        )
    except Exception as e:
        return empty_df, f"Yahoo Finance कडून डेटा मागवताना चूक ({type(e).__name__}): {e}"

    if yf_df is None or yf_df.empty:
        return empty_df, (
            f"Yahoo Finance ने रिकामा डेटा दिला (सिम्बॉल={yf_symbol}, interval={yf_interval}, "
            f"{from_date} ते {to_date}). शक्य कारणं: चुकीचा तारीख-रेंज, बाजार बंद असलेले दिवस, "
            "किंवा Yahoo Finance कडून तात्पुरती मर्यादा (rate limit)."
        )

    df = yf_df.reset_index()
    ts_col = "Datetime" if "Datetime" in df.columns else "Date"
    df = df.rename(columns={
        ts_col: "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
    })
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if df["timestamp"].dt.tz is not None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
    df["oi"] = 0
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    result_df = df[["timestamp", "open", "high", "low", "close", "volume", "oi"]].dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return result_df, None
