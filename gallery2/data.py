"""gallery2/data.py — gallery charts चे bars (data policy सह). **Sealed NIFTY holdout चा एकही bar कधीच वाचला / दाखवला जात नाही.**

Sources (key ⇒ file). Repo मधला NIFTY 1m (IS / VAL) public repo मध्ये आहे; बाकी सगळं private `trade-data` clone मध्ये (env
`TRADE_DATA_DIR` / `TRADE_DATA`, नाहीतर repo शेजारचा `trade-data`, `/root/trade-data`, `/home/user/trade-data`). File नसेल ⇒
`DataMissing` (page कारण दाखवतो; tests skip).

Policy:
  • NIFTY ⇒ `elliott.data_policy` purpose "golden": IS / VAL / CONTAMINATED फक्त; HOLDOUT आणि ILLUSTRATION कधीच नाहीत. 1m rows
    resample च्या **आधी** गाळल्या जातात (holdout चा minute कोणत्याही bar मध्ये येत नाही). NIFTY ला अपवाद नाही.
  • BANKNIFTY / SENSEX ⇒ NIFTY holdout च्या तारखा (correlated बाजार) टाळल्या जातात; अपवाद फक्त manifest मध्ये
    `holdout_dates_exception: true` असलेले Abhi चे आधीचे marked charts (उदा. BANKNIFTY Feb → Mar 2026).
"""
import os
import re

import pandas as pd

from elliott import data_policy as DP
from opportunity_engine import sessions as SS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
TIMEFRAMES = ("D", "1H", "15M")
TF_NAME = {"D": "Daily", "1H": "1H", "15M": "15M"}
TF_MINUTES = {"1H": 60, "15M": 15}
COLS = ["timestamp", "open", "high", "low", "close", "volume"]

# where: "repo" (public repo checkout) / "trade-data" (private clone). kind: "1m" (resampled) किंवा TF (जसे आहे तसे).
SOURCES = {
    "nifty_1m_repo": {"symbol": "NIFTY", "where": "repo", "path": "data/nifty50_1min.parquet", "kind": "1m"},
    # golden window चा NIFTY 1m: `upstox/NIFTY_1m_<from>_<to>.csv.gz` — सगळ्यात नवा (शेवटची तारीख मोठी) file आपोआप
    "nifty_1m_golden": {"symbol": "NIFTY", "where": "trade-data", "dir": "upstox",
                        "pattern": r"^NIFTY_1m_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.csv\.gz$", "kind": "1m"},
    "banknifty_D": {"symbol": "BANKNIFTY", "where": "trade-data", "path": "banknifty/BANKNIFTY_D.csv.gz", "kind": "D"},
    "banknifty_1H": {"symbol": "BANKNIFTY", "where": "trade-data", "path": "banknifty/BANKNIFTY_1H.csv.gz", "kind": "1H"},
    "banknifty_15M": {"symbol": "BANKNIFTY", "where": "trade-data", "path": "banknifty/BANKNIFTY_15M.csv.gz", "kind": "15M"},
}


class DataMissing(RuntimeError):
    """Source file या machine वर नाही (sandbox / CI मध्ये trade-data नसतो)."""


def trade_data_dir():
    for env in ("TRADE_DATA_DIR", "TRADE_DATA"):
        if os.environ.get(env):
            return os.environ[env]
    for p in (os.path.join(os.path.dirname(ROOT), "trade-data"), "/root/trade-data", "/home/user/trade-data"):
        if os.path.isdir(p):
            return p
    return os.path.join(os.path.dirname(ROOT), "trade-data")


def source_path(key):
    """Source चा file. `pattern` असलेल्या sources साठी folder मधला जुळणारा: सगळ्यात उशिराची शेवटची तारीख, त्यात सगळ्यात **लवकरची**
    सुरुवात (पूर्ण coverage — incremental छोटा file जुन्या bars ना हरवत नाही); NIFTY source ची सुरुवात holdout मध्ये असलेले files
    निवडतच नाही. नाही ⇒ folder + pattern (अस्तित्वात नसलेला path ⇒ `load_source` मध्ये DataMissing)."""
    src = SOURCES[key]
    base = ROOT if src["where"] == "repo" else trade_data_dir()
    if "pattern" not in src:
        return os.path.join(base, src["path"])
    d = os.path.join(base, src["dir"])
    found = []
    if os.path.isdir(d):
        for f in os.listdir(d):
            m = re.match(src["pattern"], f)
            if not m:
                continue
            if src["symbol"] == "NIFTY" and _in_nifty_holdout_dates([m.group(1)])[0]:
                continue                                                   # holdout मध्ये सुरू होणारा file वाचतच नाही
            found.append((m.group(2), -pd.Timestamp(m.group(1)).value, f))
    return os.path.join(d, max(found)[2]) if found else os.path.join(d, src["pattern"])


# ---------------------------------------------------------------------------------------------------------------- policy
def _in_nifty_holdout_dates(ts):
    t = pd.to_datetime(pd.Series(ts))
    return ((t >= DP.HOLDOUT_START) & (t < DP.CONTAMINATED_START)).to_numpy()


def window_allowed(symbol, start, end, exception=False):
    """[start, end] gallery साठी चालतो का; नाही ⇒ `DP.HoldoutError` (कारणासह). NIFTY ⇒ data_policy "golden" (अपवाद नाही)."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if symbol == "NIFTY":
        return DP.check_range(s, e, purpose="golden")
    if e < s:
        raise ValueError("end < start")
    if not exception and s < DP.CONTAMINATED_START and e >= DP.HOLDOUT_START:
        raise DP.HoldoutError(f"{symbol} {s.date()}→{e.date()} NIFTY holdout च्या तारखांना छेदतो ({DP.HOLDOUT_START.date()} → "
                              f"{(DP.CONTAMINATED_START - pd.Timedelta(days=1)).date()}) — फक्त Abhi च्या आधीच्या marked charts ना अपवाद")
    return True


def policy_filter(symbol, df, exception=False):
    """परवानगी नसलेल्या rows काढतो (वापरापूर्वीचा शेवटचा पहारा)."""
    if df is None or not len(df):
        return df
    if symbol == "NIFTY":
        return DP.filter_allowed(df, "golden")
    if exception:
        return df.reset_index(drop=True)
    return df[~_in_nifty_holdout_dates(df["timestamp"])].reset_index(drop=True)


# ---------------------------------------------------------------------------------------------------------------- loading
_RAW = {}


def _read(path):
    if path.endswith(".parquet"):
        if os.path.basename(path) in DP.HOLDOUT_FILES:
            raise DP.HoldoutError(f"{os.path.basename(path)} sealed holdout file — gallery मध्ये नाही")
        d = pd.read_parquet(path)
    else:
        d = pd.read_csv(path)
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    if "volume" not in d.columns:
        d["volume"] = 0.0
    return d[COLS].sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)


def load_source(key, exception=False):
    """एका source चे सगळे (policy-filtered) rows. Cache: (key, exception)."""
    ck = (key, bool(exception), source_path(key))
    if ck not in _RAW:
        path = source_path(key)
        if not os.path.exists(path):
            raise DataMissing(f"{key}: {path} नाही")
        d = _read(path)
        if SOURCES[key]["kind"] == "D":
            d["timestamp"] = d["timestamp"].dt.normalize()
            d = d.drop_duplicates("timestamp", keep="last").reset_index(drop=True)
        _RAW[ck] = policy_filter(SOURCES[key]["symbol"], d, exception)
    return _RAW[ck]


def to_tf(m1, tf):
    """NSE 09:15-anchored bars (opportunity_engine.sessions; CAS masking नाही — chart वर खरे OHLC)."""
    if tf == "D":
        r = SS.resample_nse_daily(m1, cas=False)
    else:
        r = SS.resample_nse(m1, TF_MINUTES[tf], cas=False)
    r = r.dropna(subset=["open", "high", "low", "close"])
    return r[COLS].reset_index(drop=True)


def tf_frame(key, tf, start=None, end=None, exception=False):
    """Source ⇒ `tf` bars (1m sources resample; TF sources जसे आहेत तसे). start / end (ऐच्छिक) ⇒ 1m rows आधीच कापतो (वेग)."""
    src = SOURCES[key]
    d = load_source(key, exception)
    if src["kind"] == "1m":
        if start is not None:
            d = d[d["timestamp"] >= pd.Timestamp(start).normalize()]
        if end is not None:
            d = d[d["timestamp"] < pd.Timestamp(end).normalize() + pd.Timedelta(days=1)]
        return to_tf(d.reset_index(drop=True), tf)
    if src["kind"] != tf:
        raise ValueError(f"{key} हा {src['kind']} source — {tf} नाही")
    return d.copy()


def warmup_days(tf, bars):
    """`bars` bars मागे जायला लागणारे calendar दिवस (सुट्ट्या धरून ढोबळ, जास्तच)."""
    per_day = {"D": 1, "1H": 7, "15M": 25}[tf]
    return int(bars / per_day * 1.6) + 10


def load_window(cand, warmup_bars=0):
    """Manifest मधल्या chart चे bars: [start, end] (bar timestamps, दोन्ही सामील) + हवे असल्यास आधीचे ≤ `warmup_bars` bars
    (policy नुसार परवानगी असलेलेच — NIFTY golden window चा warm-up 2026-07-01 आधी जात नाही)."""
    exc = bool(cand.get("holdout_dates_exception"))
    window_allowed(cand["symbol"], cand["start"], cand["end"], exception=exc)
    s, e = pd.Timestamp(cand["start"]), pd.Timestamp(cand["end"])
    lo = s - pd.Timedelta(days=warmup_days(cand["timeframe"], warmup_bars)) if warmup_bars else s
    fr = tf_frame(cand["source"], cand["timeframe"], lo, e, exception=exc)
    ts = fr["timestamp"]
    win = fr[(ts >= s) & (ts <= e)]
    if warmup_bars:
        pre = fr[ts < s].tail(int(warmup_bars))
        win = pd.concat([pre, win])
    out = policy_filter(cand["symbol"], win.reset_index(drop=True), exc)
    return out.reset_index(drop=True)
