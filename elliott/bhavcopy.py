"""
elliott/bhavcopy.py
-------------------
🎓 NSE F&O bhavcopy (अधिकृत, मोफत, दैनिक) — प्रत्येक NIFTY option strike चा त्या दिवसाचा OHLC/close/settlement/OI.
Intraday premium नाही; म्हणून backtest मध्ये: त्या दिवसाच्या bhavcopy close वरून strike-निहाय IV (smile) ⇒ intraday entry/exit
साठी त्या IV ने Black-Scholes (Abhi चा क्रम: Upstox expired API → bhavcopy-IV BS → शुद्ध BS शेवटचा पर्याय).
Expiry तारखा इथूनच — म्हणजे ऐतिहासिक expiry calendar अधिकृत स्रोतातून, weekday hard-code नाही. **Lot size फक्त UDiFF मध्ये**
(8 Jul 2024 नंतर; आपल्यासाठी फक्त golden काळ) — जुन्या format मध्ये lot column नाही, म्हणून IS/VAL चा lot इतिहास E3 मध्ये वेगळ्या
(स्रोतासह) तक्त्यातून. Volume: जुन्या format मध्ये contracts; UDiFF मध्ये TtlTradgVol (एकक `volume_unit` मध्ये नोंदवलं).

दोन formats (NSE ने 8 Jul 2024 पासून UDiFF सुरू केला):
  old   fo{DD}{MON}{YYYY}bhav.csv  — INSTRUMENT, SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, OPEN … SETTLE_PR, CONTRACTS, OPEN_INT
  UDiFF BhavCopy_NSE_FO_0_0_0_{YYYYMMDD}_F_0000.csv — TradDt, FinInstrmTp, TckrSymb, XpryDt, StrkPric, OptnTp, OpnPric …
        SttlmPric, OpnIntrst, TtlTradgVol, UndrlygPric, NewBrdLotQty
हा module फक्त parse/normalize करतो (network नाही) — download VPS script मध्ये (research/elliott_vps_data.py).
"""
import datetime as dt
import io
import zipfile

import numpy as np
import pandas as pd

UDIFF_START = dt.date(2024, 7, 8)
COLUMNS = ["date", "symbol", "instrument", "expiry", "strike", "opt_type", "open", "high", "low", "close", "settle",
           "volume", "volume_unit", "oi", "underlying", "lot_size"]
FLOAT_COLS = ["strike", "open", "high", "low", "close", "settle", "volume", "oi", "underlying", "lot_size"]

OLD_REQUIRED = {"INSTRUMENT", "SYMBOL", "EXPIRY_DT", "STRIKE_PR", "OPTION_TYP", "OPEN", "HIGH", "LOW", "CLOSE",
                "SETTLE_PR", "CONTRACTS", "OPEN_INT", "TIMESTAMP"}
UDIFF_REQUIRED = {"TradDt", "FinInstrmTp", "TckrSymb", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric", "LwPric",
                  "ClsPric", "SttlmPric", "OpnIntrst", "TtlTradgVol"}


class BhavcopyFormatError(ValueError):
    pass


def urls_for(day):
    """त्या दिवसाचे संभाव्य URLs (आधी अपेक्षित format, मग दुसरा) — NSE ने जुन्या फाइल्स कधी कधी नवीन मार्गावरही ठेवल्या."""
    d = pd.Timestamp(day).date()
    mon = d.strftime("%b").upper()
    path = f"content/historical/DERIVATIVES/{d.year}/{mon}/fo{d:%d}{mon}{d.year}bhav.csv.zip"
    old = [f"https://archives.nseindia.com/{path}", f"https://nsearchives.nseindia.com/{path}"]     # जुना host बंद झाला तरी
    new = [f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"]
    return new + old if d >= UDIFF_START else old + new


def read_zip_csv(payload):
    """zip (किंवा साधा csv) bytes → DataFrame."""
    if payload[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            payload = z.read(name)
    return pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False)


def _num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.strip().replace({"": np.nan, "-": np.nan}), errors="coerce")


def detect_format(df):
    cols = {c.strip() for c in df.columns}
    if OLD_REQUIRED <= cols:
        return "old"
    if UDIFF_REQUIRED <= cols:
        return "udiff"
    raise BhavcopyFormatError(f"ओळखीचा bhavcopy format नाही; columns: {sorted(cols)[:40]}")


def normalize(df, symbol="NIFTY"):
    """कुठलाही format → COLUMNS (फक्त symbol चे index options + index futures). strike float, expiry/date = date."""
    df = df.rename(columns=lambda c: c.strip())
    fmt = detect_format(df)
    if fmt == "old":
        sym = df["SYMBOL"].str.strip()
        ins = df["INSTRUMENT"].str.strip()
        m = (sym == symbol) & ins.isin(["OPTIDX", "FUTIDX"])
        d = df[m.to_numpy()]
        out = pd.DataFrame({
            "date": pd.to_datetime(d["TIMESTAMP"].str.strip(), format="%d-%b-%Y").dt.date,
            "symbol": symbol,
            "instrument": np.where(d["INSTRUMENT"].str.strip() == "OPTIDX", "OPT", "FUT"),
            "expiry": pd.to_datetime(d["EXPIRY_DT"].str.strip(), format="%d-%b-%Y").dt.date,
            "strike": _num(d["STRIKE_PR"]).to_numpy(),
            "opt_type": d["OPTION_TYP"].str.strip().replace({"XX": ""}).to_numpy(),
            "open": _num(d["OPEN"]).to_numpy(), "high": _num(d["HIGH"]).to_numpy(), "low": _num(d["LOW"]).to_numpy(),
            "close": _num(d["CLOSE"]).to_numpy(), "settle": _num(d["SETTLE_PR"]).to_numpy(),
            "volume": _num(d["CONTRACTS"]).to_numpy(), "volume_unit": "contracts", "oi": _num(d["OPEN_INT"]).to_numpy(),
            "underlying": np.nan, "lot_size": np.nan,
        })
    else:
        sym = df["TckrSymb"].str.strip()
        tp = df["FinInstrmTp"].str.strip()
        m = (sym == symbol) & tp.isin(["IDO", "IDF"])
        d = df[m.to_numpy()]
        out = pd.DataFrame({
            "date": pd.to_datetime(d["TradDt"].str.strip()).dt.date,
            "symbol": symbol,
            "instrument": np.where(d["FinInstrmTp"].str.strip() == "IDO", "OPT", "FUT"),
            "expiry": _udiff_expiry(d),
            "strike": _num(d["StrkPric"]).to_numpy(),
            "opt_type": d["OptnTp"].str.strip().to_numpy(),
            "open": _num(d["OpnPric"]).to_numpy(), "high": _num(d["HghPric"]).to_numpy(), "low": _num(d["LwPric"]).to_numpy(),
            "close": _num(d["ClsPric"]).to_numpy(), "settle": _num(d["SttlmPric"]).to_numpy(),
            "volume": _num(d["TtlTradgVol"]).to_numpy(), "volume_unit": "udiff_TtlTradgVol", "oi": _num(d["OpnIntrst"]).to_numpy(),
            "underlying": _num(d["UndrlygPric"]).to_numpy() if "UndrlygPric" in d else np.nan,
            "lot_size": _num(d["NewBrdLotQty"]).to_numpy() if "NewBrdLotQty" in d else np.nan,
        })
    out.loc[out["instrument"] == "FUT", ["strike", "opt_type"]] = [np.nan, ""]
    out[FLOAT_COLS] = out[FLOAT_COLS].astype("float64")           # प्रत्येक महिन्याचा parquet schema एकच राहतो
    return out[COLUMNS].reset_index(drop=True)


def _udiff_expiry(d):
    """प्रत्यक्ष expiry (FininstrmActlXpryDt — सुट्टीमुळे सरकलेली) असेल तर ती, नाहीतर XpryDt."""
    xp = pd.to_datetime(d["XpryDt"].str.strip())
    if "FininstrmActlXpryDt" in d:
        act = pd.to_datetime(d["FininstrmActlXpryDt"].str.strip().replace("", None), errors="coerce")
        xp = act.fillna(xp)
    return xp.dt.date


def expiry_calendar(norm):
    """bhavcopy वरून expiry calendar: प्रत्येक options expiry, तिचा weekday, monthly (त्या महिन्यातली शेवटची) की weekly,
    आणि ती पहिल्यांदा कधी दिसली (= त्या contract चा listing पुरावा)."""
    o = norm[norm["instrument"] == "OPT"]
    if o.empty:
        return pd.DataFrame(columns=["expiry", "weekday", "kind", "first_seen", "last_seen"])
    g = o.groupby("expiry")["date"].agg(first_seen="min", last_seen="max").reset_index()
    g["weekday"] = pd.to_datetime(g["expiry"]).dt.day_name()
    ym = pd.to_datetime(g["expiry"]).dt.to_period("M")
    last_in_month = g.groupby(ym)["expiry"].transform("max")
    g["kind"] = np.where(g["expiry"] == last_in_month, "monthly", "weekly")
    return g[["expiry", "weekday", "kind", "first_seen", "last_seen"]].sort_values("expiry").reset_index(drop=True)


def first_weekly_listing(norm):
    """पहिल्या weekly (non-monthly) expiry चा listing दिवस — NIFTY weekly options कधी सुरू झाले याचा data-पुरावा."""
    cal = expiry_calendar(norm)
    w = cal[cal["kind"] == "weekly"]
    return None if w.empty else w["first_seen"].min()
