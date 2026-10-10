"""swings2/candles.py — MASTER §3 candle व्याख्या: rng_ratio (slot-normalised, session-गोठलेला), displacement, trend candle, CLV."""
import numpy as np
import pandas as pd

from pivots import engine as PE


def rng_ratio(res):
    """(H − L) ÷ त्याच 15M slot चा मागच्या n पात्र (पूर्ण, त्याच segment) sessions चा median. पुरेसे नाहीत ⇒ NaN."""
    m15, s = res["m15"], res["settings"]
    n = int(s["rng_sessions"])
    ts = pd.to_datetime(m15["timestamp"])
    day = ts.dt.normalize()
    slot = (ts - day).to_numpy()
    rng = (m15["high"] - m15["low"]).to_numpy(float)
    full = PE.complete_sessions(m15)
    seg = res["segments"]
    days = res["sessions"]
    by = {}
    for i, (d, sl) in enumerate(zip(day, slot)):
        by.setdefault((pd.Timestamp(d), sl), rng[i])
    out = np.full(len(m15), np.nan)
    for i, (d, sl) in enumerate(zip(day, slot)):
        d = pd.Timestamp(d)
        k = days.index(d)
        prev = [x for x in days[:k] if seg[x] == seg[d] and full[x] and (x, sl) in by][-n:]
        if len(prev) >= n:
            med = float(np.median([by[(x, sl)] for x in prev]))
            if med > 0:
                out[i] = rng[i] / med
    return out


def _parts(A, i):
    o, h, l, c = A["o"][i], A["h"][i], A["l"][i], A["c"][i]
    r = h - l
    return o, h, l, c, r


def clv(A, i, d):
    o, h, l, c, r = _parts(A, i)
    if r <= 0:
        return 0.0
    return (c - l) / r if d > 0 else (h - c) / r


def body_pct(A, i):
    o, h, l, c, r = _parts(A, i)
    return abs(c - o) / r if r > 0 else 0.0


def is_trend_candle(A, i, d, s):
    o, h, l, c, r = _parts(A, i)
    return bool((c - o) * d > 0 and body_pct(A, i) >= float(s["trend_body"]) and clv(A, i, d) >= float(s["trend_clv"]))


def is_displacement(A, rr, i, d, s):
    """rng_ratio ≥ 1.5, body% ≥ 0.6, उलट (close बाजूची) wick ≤ 0.2, d दिशेने बंद."""
    o, h, l, c, r = _parts(A, i)
    if r <= 0 or not np.isfinite(rr[i]) or (c - o) * d <= 0:
        return False
    wick = (h - c) / r if d > 0 else (c - l) / r
    return bool(rr[i] >= float(s["disp_rng_ratio"]) and body_pct(A, i) >= float(s["disp_body"]) and wick <= float(s["disp_wick_opp"]))
