"""
elliott/swings.py — E1a: causal multi-degree swings (spec §2 "Degrees", §11, §12 पायरी 1, §14 Q3)
-----------------------------------------------------------------------------------------------
🎓 "Degree" = swing threshold चा स्तर (D0 सर्वात लहान … D3 सर्वात मोठा). प्रत्येक degree चे pivots:
  • threshold (bar i वर, फक्त bars ≤ i वरून): atr ⇒ swing_atr_mult[d] × ATR(atr_len); pct ⇒ swing_pct[d]% × close;
    fractal ⇒ r = swing_fractal_r[d] bars दोन्ही बाजूंना.
  • Pivot **confirmed** तेव्हाच जेव्हा extreme पासून उलट हालचाल ≥ threshold (बंद bars च्या high/low वरून). confirmed_idx = तो bar,
    confirmed_at = त्या bar चा bar_end (knowable_at). Confirmed pivot कधीच हलत/बदलत नाही.
  • शेवटच्या confirmed pivot नंतरचा चालू extreme = **tentative** pivot (फक्त चालू wave साठी; completed-wave नियमांमध्ये कधीच नाही).
ZigZag core: price_action/legs.py::zigzag_pivots (reuse — तेच no-lookahead logic; इथे threshold array पुरवतो).

Auto TF (§14 Q3): corrective wave [start, end] सर्वात लहान TF वर tf_bars_min–tf_bars_max **बंद** candles मध्ये दिसेल तो TF.
Similarity & Balance (Neely QOW 78): शेजारच्या legs पैकी लहान ≥ min × मोठा, price **किंवा** time ⇒ एकाच degree चे.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from opportunity_engine.cas import strip_cas
from opportunity_engine.sessions import filter_regular_hours, resample_nse, resample_nse_daily
from price_action.legs import fractal_pivots, zigzag_pivots

from .settings import TF_MIN


@dataclass(frozen=True)
class Pivot:
    degree: int
    kind: str                 # "H" | "L"
    price: float
    bar_idx: int              # extreme चा bar (त्या degree च्या TF frame मध्ये)
    ts: pd.Timestamp          # extreme bar चा start
    confirmed_idx: Optional[int]
    confirmed_at: Optional[pd.Timestamp]   # knowable_at = confirm bar चा bar_end; tentative ⇒ None
    status: str               # "confirmed" | "tentative"
    tf: str = "5m"


# ---------------------------------------------------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------------------------------------------------
def build_frame(df1m, tf):
    """1m (NIFTY spot) → NSE 09:15-anchored TF bars, **फक्त पूर्ण बंद** bars (bar_closed). Columns: timestamp, bar_end, OHLC."""
    if tf == "1m":
        d = strip_cas(filter_regular_hours(df1m))[["timestamp", "open", "high", "low", "close"]].copy()     # CAS bars structure मध्ये नाहीत
        d["timestamp"] = pd.to_datetime(d["timestamp"])
        d["bar_end"] = d["timestamp"] + pd.Timedelta(minutes=1)
        return d.reset_index(drop=True)
    r = resample_nse_daily(df1m) if tf == "1d" else resample_nse(df1m, TF_MIN[tf])
    r = r[r["bar_closed"].astype(bool)]
    return r[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


def asof(frame, now):
    """`now` पर्यंत संपलेले bars (bar_end ≤ now)."""
    return frame[frame["bar_end"] <= pd.Timestamp(now)].reset_index(drop=True)


# ---------------------------------------------------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------------------------------------------------
def atr(df, n):
    """bar i वर: TR (bars ≤ i) चा n-bar सरासरी; पहिल्या n bars ला NaN (⇒ pivot नाही)."""
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    return pd.Series(tr).rolling(n, min_periods=n).mean().to_numpy(float)


def threshold(df, degree, s):
    if s["swing_mode"] == "pct":
        return df["close"].to_numpy(float) * s["swing_pct"][degree] / 100.0
    return s["swing_atr_mult"][degree] * atr(df, s["atr_len"])


# ---------------------------------------------------------------------------------------------------------------------
# Pivots
# ---------------------------------------------------------------------------------------------------------------------
def _alternating_fractals(df, r):
    """Fractal pivots आलटून-पालटून, **causal**: सलग समान प्रकार आला आणि तो अधिक टोकाचा असेल तर मधला उलट extreme (दोघांमधला)
    नवीन confirmed pivot म्हणून घालतो (confirm = आत्ताचा bar). आधीचा confirmed pivot कधीच बदलत नाही; कमी टोकाचा नवीन pivot वगळतो."""
    h, l = df["high"].to_numpy(float), df["low"].to_numpy(float)
    out = []
    for p in fractal_pivots(df, r):
        if not out:
            out.append((p.kind, p.pivot_bar, p.confirm_bar, p.price))
            continue
        k0, b0, _, px0 = out[-1]
        if p.kind != k0:
            beyond = p.price > px0 if p.kind == "H" else p.price < px0      # उलट दिशेची leg खरंच त्या दिशेने हवी
            if p.pivot_bar > b0 and beyond:
                out.append((p.kind, p.pivot_bar, p.confirm_bar, p.price))
            continue
        more = p.price > px0 if p.kind == "H" else p.price < px0
        if not more or p.pivot_bar <= b0 + 1:
            continue
        seg = slice(b0 + 1, p.pivot_bar)
        j = b0 + 1 + int(np.argmin(l[seg]) if p.kind == "H" else np.argmax(h[seg]))
        mid = "L" if p.kind == "H" else "H"
        out.append((mid, j, p.confirm_bar, float(l[j] if mid == "L" else h[j])))
        out.append((p.kind, p.pivot_bar, p.confirm_bar, p.price))
    return out


def degree_pivots(frame, degree, s, tf="5m"):
    """एका degree चे confirmed pivots (confirmed_idx क्रमाने). frame = बंद bars (timestamp, bar_end, OHLC)."""
    if len(frame) < 3:
        return []
    if s["swing_mode"] == "fractal":
        raw = _alternating_fractals(frame, s["swing_fractal_r"][degree])
    else:
        raw = [(p.kind, p.pivot_bar, p.confirm_bar, p.price) for p in zigzag_pivots(frame, k=1.0, mr=threshold(frame, degree, s))]
    ts, be = frame["timestamp"].to_numpy(), frame["bar_end"].to_numpy()
    return [Pivot(degree, k, float(px), int(b), pd.Timestamp(ts[b]), int(c), pd.Timestamp(be[c]), "confirmed", tf) for k, b, c, px in raw]


def tentative_pivot(frame, confirmed, degree, upto=None, tf="5m"):
    """शेवटच्या (upto पर्यंत माहीत असलेल्या) confirmed pivot नंतरचा चालू extreme (bars ≤ upto). समान भाव ⇒ शेवटचा bar
    (zigzag confirm करताना जो bar निवडतो तोच). Confirmed नसतील ⇒ None."""
    upto = len(frame) - 1 if upto is None else upto
    confirmed = [p for p in confirmed if p.confirmed_idx is not None and p.confirmed_idx <= upto]
    if not confirmed:
        return None
    last = confirmed[-1]
    a = last.bar_idx + 1
    if a > upto:
        return None
    if last.kind == "H":
        seg = frame["low"].to_numpy(float)[a:upto + 1]
        j, kind, px = a + len(seg) - 1 - int(np.argmin(seg[::-1])), "L", float(seg.min())
    else:
        seg = frame["high"].to_numpy(float)[a:upto + 1]
        j, kind, px = a + len(seg) - 1 - int(np.argmax(seg[::-1])), "H", float(seg.max())
    return Pivot(degree, kind, px, j, pd.Timestamp(frame["timestamp"].iloc[j]), None, None, "tentative", tf)


def degree_tf(s, degree):
    return s["structure_tf"] if s["degree_tf_mode"] == "auto_by_bars" else s["degree_tf"][degree]


def multi_degree(df1m, s, now=None):
    """सगळ्या degrees चे confirmed pivots + tentative, `now` पर्यंतच्या बंद bars वरून.
    रिटर्न {degree: {"tf", "frame", "confirmed": [Pivot], "tentative": Pivot|None}}."""
    out, frames = {}, {}
    for d in range(s["degree_levels"]):
        tf = degree_tf(s, d)
        if tf not in frames:
            f = build_frame(df1m, tf)
            frames[tf] = asof(f, now) if now is not None else f
        fr = frames[tf]
        conf = degree_pivots(fr, d, s, tf)
        out[d] = {"tf": tf, "frame": fr, "confirmed": conf, "tentative": tentative_pivot(fr, conf, d, tf=tf)}
    return out


def known_at(pivots, t):
    """`t` वेळी माहीत असलेले confirmed pivots (confirmed_at ≤ t)."""
    t = pd.Timestamp(t)
    return [p for p in pivots if p.confirmed_at is not None and p.confirmed_at <= t]


# ---------------------------------------------------------------------------------------------------------------------
# Similarity & Balance, auto TF
# ---------------------------------------------------------------------------------------------------------------------
def legs_of(pivots):
    """सलग pivots मधले legs: (start, end, price_len, bars). bars = दोन्ही टोकांचे bars धरून (auto_tf च्या मोजणीसारखेच)."""
    return [(a, b, abs(b.price - a.price), b.bar_idx - a.bar_idx + 1) for a, b in zip(pivots, pivots[1:])]


def similar_degree(leg_a, leg_b, min_ratio):
    """Neely: लहान ≥ min_ratio × मोठा, price **किंवा** time."""
    pa, ta, pb, tb = leg_a[2], max(leg_a[3], 1), leg_b[2], max(leg_b[3], 1)
    price_ok = min(pa, pb) >= min_ratio * max(pa, pb) if max(pa, pb) > 0 else True
    time_ok = min(ta, tb) >= min_ratio * max(ta, tb)
    return bool(price_ok or time_ok)


def balance_rate(pivots, min_ratio):
    """शेजारच्या legs च्या जोड्यांपैकी किती Similarity & Balance पाळतात (degree assignment ची गुणवत्ता)."""
    lg = legs_of(pivots)
    pairs = list(zip(lg, lg[1:]))
    return float(np.mean([similar_degree(a, b, min_ratio) for a, b in pairs])) if pairs else float("nan")


def closed_bars_between(frame, start_ts, end_ts):
    """[start_ts, end_ts] मध्ये **बंद** झालेले bars (bar start ≥ start च्या bar चा, bar_end ≤ end_ts)."""
    st, en = pd.Timestamp(start_ts), pd.Timestamp(end_ts)
    f = frame[(frame["bar_end"] > st) & (frame["bar_end"] <= en)]
    return int(len(f))


def auto_tf(frames, start_ts, end_ts, s):
    """§14 Q3: wave [start_ts, end_ts] (end_ts = आत्तापर्यंत; बंद bars च) साठी auto_tfs पैकी सर्वात लहान TF ज्यात bars
    tf_bars_min–tf_bars_max. कुठलाच range मध्ये नाही ⇒ ≥ min असलेल्यांपैकी सर्वात मोठा (रचना दिसते, noise कमी); कुठलाच ≥ min
    नाही ⇒ सर्वात लहान. रिटर्न (tf, {tf: bars}, in_range) — in_range False ⇒ 8–40 नियम पूर्ण नाही (E2: < min ⇒ रचना दिसत
    नाही ⇒ त्या setup वर entry नाही; caller ठरवतो). auto_tfs मधला TF frames मध्ये नसेल ⇒ ValueError (गुपचूप वगळत नाही)."""
    missing = [tf for tf in s["auto_tfs"] if tf not in frames]
    if missing:
        raise ValueError(f"auto_tf: frames मध्ये {missing} नाहीत")
    counts = {tf: closed_bars_between(frames[tf], start_ts, end_ts) for tf in s["auto_tfs"]}
    for tf in sorted(counts, key=TF_MIN.get):
        if s["tf_bars_min"] <= counts[tf] <= s["tf_bars_max"]:
            return tf, counts, True
    order = sorted(counts, key=TF_MIN.get)
    enough = [t for t in order if counts[t] >= s["tf_bars_min"]]       # रचना दिसते असे TFs (पण > max)
    return (enough[-1] if enough else order[0]), counts, False
