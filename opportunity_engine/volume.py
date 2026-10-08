"""opportunity_engine/volume.py — near-month index futures चा raw 5M volume index bars ला जोडणे (spec §10). कुठलाही indicator नाही.

🎓 का: NIFTY/BANKNIFTY index candles मध्ये volume नसतो (0). Breakout validation (spec §5) चा volume नियम (≥ 1.5 × मागच्या 20 bars चा median)
near-month **futures** चा volume वापरतो. PR-0 (VPS) नुसार: front-month futures चा 5M volume/OI 100% मिळतो, पण expired futures (जुना इतिहास)
Upstox Plus शिवाय मिळत नाही (HTTP 401) ⇒ `collect_index_futures_volume.py` दररोज front-month चे 5M candles साठवतो; तो डेटा इथे जोडला जातो.
जोडणी: futures 5M candle चा timestamp (= bar_start, IST) == index 5M `bar_start` (तंतोतंत); 15M = त्याच 09:15-anchored bins चा बेरीज.
ज्या bars ला futures volume नाही तिथे 0 ⇒ validation मध्ये "N/A" (गुण range expansion ला) — अंदाजाने भरलेलं काहीही नाही.
"""
import pandas as pd

from . import sessions

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "oi"]


def candles_to_df(candles, contract=None):
    """Upstox candles [[ts, o, h, l, c, volume, oi], …] -> DataFrame (timestamp = naive IST, क्रमाने, duplicate नाहीत)."""
    if not candles:
        return pd.DataFrame(columns=COLUMNS + (["contract"] if contract else []))
    rows = [list(c[:7]) + [None] * (7 - len(c[:7])) for c in candles]
    df = pd.DataFrame(rows, columns=COLUMNS)
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    df["timestamp"] = ts.astype("datetime64[ns]")
    for c in COLUMNS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    if contract:
        df["contract"] = contract
    return df.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)


def merge_store(existing, new):
    """आधी साठवलेले + नवीन candles. एकाच timestamp चा आधी साठवलेला row ठेवतो (rollover नंतरच्या पुढच्या contract चे जुने दिवस front-month ला बदलू नयेत)."""
    if existing is None or not len(existing):
        return new.reset_index(drop=True)
    if new is None or not len(new):
        return existing.reset_index(drop=True)
    out = pd.concat([existing, new], ignore_index=True)
    return out.drop_duplicates("timestamp", keep="first").sort_values("timestamp").reset_index(drop=True)


def merge_store_by_contract(existing, new):
    """सगळ्या contracts चा store (Chart Reader K10.3 roll): key = (timestamp, contract); आधी साठवलेला row ठेवतो."""
    if existing is None or not len(existing):
        return new.reset_index(drop=True)
    if new is None or not len(new):
        return existing.reset_index(drop=True)
    out = pd.concat([existing, new], ignore_index=True)
    return out.drop_duplicates(["timestamp", "contract"], keep="first").sort_values(["timestamp", "contract"]).reset_index(drop=True)


def attach_futures_volume(frames, fut5):
    """frames (engine frames) च्या 5m आणि 15m `volume` ला futures volume ने बदलतो (नवीन dict; मूळ frames बदलत नाहीत). रिटर्न (frames, coverage dict)."""
    out = dict(frames)
    f5 = frames["5m"].copy()
    if fut5 is None or not len(fut5):
        f5["volume"] = 0.0
        out["5m"] = f5
        return out, {"bars": len(f5), "with_volume": 0, "pct": 0.0, "from": None, "to": None}
    fut = fut5[["timestamp", "volume"]].copy()
    fut["timestamp"] = pd.to_datetime(fut["timestamp"]).astype("datetime64[ns]")
    vol5 = fut.groupby("timestamp")["volume"].sum()
    f5["volume"] = f5["bar_start"].map(vol5).fillna(0.0).astype(float)
    out["5m"] = f5
    if "15m" in frames:
        fut15 = sessions.resample_nse(fut.assign(open=0.0, high=0.0, low=0.0, close=0.0), 15)          # फक्त volume बेरीज हवी
        vol15 = fut15.set_index("bar_start")["volume"]
        f15 = frames["15m"].copy()
        f15["volume"] = f15["bar_start"].map(vol15).fillna(0.0).astype(float)
        out["15m"] = f15
    has = f5["volume"] > 0
    cov = {"bars": int(len(f5)), "with_volume": int(has.sum()), "pct": round(100.0 * has.mean(), 2) if len(f5) else 0.0,
           "from": None if not has.any() else f5.loc[has, "bar_start"].min(), "to": None if not has.any() else f5.loc[has, "bar_start"].max()}
    return out, cov


def without_volume(frames):
    """तुलनेसाठी: तेच frames पण volume = 0 (validation मध्ये volume N/A)."""
    out = dict(frames)
    for tf in ("5m", "15m"):
        if tf in frames:
            f = frames[tf].copy()
            f["volume"] = 0.0
            out[tf] = f
    return out


def frames_from_index_5m(index5, daily=None):
    """Upstox index 5M (collector ने साठवलेला) -> engine frames; Daily इतिहास (structure warm-up साठी) `daily` (उदा. load_nifty_daily_combined) मधून,
    5M सुरू होण्याआधीचे दिवस जोडून."""
    frames = sessions.build_frames(index5)
    if daily is not None and len(daily) and len(frames["1d"]):
        first = frames["1d"]["timestamp"].min()
        pre = sessions.daily_from_daily_bars(daily)
        pre = pre[pre["timestamp"] < first]
        frames["1d"] = pd.concat([pre, frames["1d"]], ignore_index=True)
    return frames
