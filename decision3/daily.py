"""decision3/daily.py — ① Daily trend (Dow), थर v2.2.

Input: Daily candles (timestamp = session तारीख, `bar_end` = त्या दिवसाचा close वेळ = known_at). NIFTY: 1m ⇒ 15M ⇒ Daily (फक्त पूर्ण
sessions, `pivots.charts.daily_from_15m`); BANKNIFTY: fetched D (bar_end = तारीख + session close).

Daily swings — `daily_swing_method`:
  • pivot (default): high[i] > डावीकडचे N highs आणि ≥ उजवीकडचे N highs (low आरसा). Confirm = i+N दिवसाचा close (known_at).
  • dc: directional change, θ_D = k_D × σ_D (σ_D = शेवटच्या `daily_sigma_sessions` Daily ranges चा median; warm-up फक्त σ साठी).
  Confirm-क्रमाने H / L आलटून पालटून; सलग तोच प्रकार ⇒ जास्त टोकाचा ठेवा (replace, त्याच confirm वेळी).

Dow (प्रत्येक बंद Daily candle नंतर; आधी त्या दिवशी confirm झालेले pivots, मग close तपासणी):
  • UP = नवा HL + HH (शेवटच्या दोन L मध्ये L2 > L1 + tol, शेवटच्या दोन H मध्ये H2 > H1 + tol; L2 आणि H2 दोन्ही शेवटच्या break नंतरचे).
    DOWN आरसा. protected = तो HL (UP) / LH (DOWN); trend मध्ये नवा HL (L > मागचा L) ⇒ protected पुढे.
  • Trend संपतो (NEUTRAL) जेव्हा protected Daily close ने तुटतो (wick नाही).
  • RANGE = NEUTRAL + दोन H जवळपास समान (|H2 − H1| ≤ tol) आणि दोन L जवळपास समान; पट्टा [min L, max H]; close पट्ट्याबाहेर ⇒ NEUTRAL.
  • tol = range_eq_sigma_d × σ_D. UNKNOWN फक्त data अपुरा (≤ daily_min_sessions Daily candles).
Pullback मध्ये trend बदलत नाही: trend फक्त protected च्या close-break ने संपतो (v2.1 चं net/H regime नाही).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import settings as S3


@dataclass(frozen=True)
class DPivot:
    kind: str           # "H" / "L"
    price: float
    bar: int            # Daily candle index
    day: pd.Timestamp
    confirm_bar: int
    known_at: pd.Timestamp


@dataclass
class DState:
    bar: int
    day: pd.Timestamp
    known_at: pd.Timestamp
    trend: str
    protected: DPivot = None
    band: tuple = None
    why: str = ""
    pivots: list = field(default_factory=list)


def _arr(d):
    return {k: d[k].to_numpy(float) for k in ("open", "high", "low", "close")}


def known_at_of(d):
    if "bar_end" in d.columns:
        return [pd.Timestamp(x) for x in d["bar_end"]]
    return [pd.Timestamp(x).normalize() + pd.Timedelta(hours=15, minutes=30) for x in d["timestamp"]]


def sigma_d(d, n):
    """σ_D[i] = Daily range चा median, शेवटच्या n candles (i सकट) — कमी असतील तर NaN (warm-up)."""
    rng = (d["high"] - d["low"]).to_numpy(float)
    out = np.full(len(d), np.nan)
    for i in range(len(d)):
        if i + 1 >= n:
            out[i] = float(np.median(rng[i + 1 - n:i + 1]))
    return out


def pivots_pivot(d, n, kat):
    """(confirm_bar क्रमाने) raw pivots — tie: डावीकडे strict, उजवीकडे ≥ (नंतरचं बरोबरीचं टोक pivot मारत नाही)."""
    A = _arr(d)
    H, L = A["high"], A["low"]
    out = []
    for i in range(n, len(d) - n):
        if H[i] > H[i - n:i].max() and H[i] >= H[i + 1:i + n + 1].max():
            out.append(DPivot("H", float(H[i]), i, pd.Timestamp(d["timestamp"].iloc[i]), i + n, kat[i + n]))
        if L[i] < L[i - n:i].min() and L[i] <= L[i + 1:i + n + 1].min():
            out.append(DPivot("L", float(L[i]), i, pd.Timestamp(d["timestamp"].iloc[i]), i + n, kat[i + n]))
    return sorted(out, key=lambda p: (p.confirm_bar, p.bar))


def pivots_dc(d, k, sig, kat):
    """Directional change: टोकापासून θ_D = k × σ_D उलट चाल (raw high / low) ⇒ टोक confirm (त्या दिवसाच्या close ला)."""
    A = _arr(d)
    H, L = A["high"], A["low"]
    out, mode = [], 0
    hi_i = lo_i = None
    for i in range(len(d)):
        if not np.isfinite(sig[i]):
            continue
        th = k * sig[i]
        if hi_i is None:
            hi_i = lo_i = i
            continue
        if mode >= 0 and H[i] > H[hi_i]:
            hi_i = i
        if mode <= 0 and L[i] < L[lo_i]:
            lo_i = i
        if mode >= 0 and hi_i < i and H[hi_i] - L[i] >= th:
            out.append(DPivot("H", float(H[hi_i]), hi_i, pd.Timestamp(d["timestamp"].iloc[hi_i]), i, kat[i]))
            mode, lo_i = -1, i
        elif mode <= 0 and lo_i < i and H[i] - L[lo_i] >= th:
            out.append(DPivot("L", float(L[lo_i]), lo_i, pd.Timestamp(d["timestamp"].iloc[lo_i]), i, kat[i]))
            mode, hi_i = 1, i
    return out


def _add(seq, p):
    """आलटून पालटून: सलग तोच प्रकार ⇒ जास्त टोकाचा ठेवा."""
    if seq and seq[-1].kind == p.kind:
        better = p.price > seq[-1].price if p.kind == "H" else p.price < seq[-1].price
        if better:
            seq[-1] = p
        return
    seq.append(p)


def _last2(seq, kind):
    xs = [p for p in seq if p.kind == kind]
    return (xs[-2], xs[-1]) if len(xs) >= 2 else (None, xs[-1] if xs else None)


def fold(d, s=None):
    """प्रत्येक Daily candle नंतरची DState यादी (index = Daily candle)."""
    s = S3.load(s)
    d = d.reset_index(drop=True)
    kat = known_at_of(d)
    sig = sigma_d(d, int(s["daily_sigma_sessions"]))
    if s["daily_swing_method"] == "dc":
        raw = pivots_dc(d, float(s["daily_dc_k"]), sig, kat)
    else:
        raw = pivots_pivot(d, int(s["daily_pivot_n"]), kat)
    C = d["close"].to_numpy(float)
    by_conf = {}
    for p in raw:
        by_conf.setdefault(p.confirm_bar, []).append(p)
    seq, out = [], []
    trend, prot, band, brk = "NEUTRAL", None, None, -1
    eq = float(s["range_eq_sigma_d"])
    for i in range(len(d)):
        why = ""
        for p in by_conf.get(i, []):
            before = seq[-1] if seq else None
            _add(seq, p)
            if not seq or seq[-1] is not p:
                continue                                                 # कमी टोकाचा सलग pivot टाकला ⇒ protected ला हात नाही
            if before is not None and before.kind == p.kind and before is prot:
                prot, why = p, "protected swing अधिक टोकाच्या सलग pivot ने बदलला"
                continue                                                 # (सलग L / H: खरा HL / LH हा नवा)
            if trend == "UP" and p.kind == "L":
                prev = [q for q in seq[:-1] if q.kind == "L"]
                if prev and p.price > prev[-1].price and (prot is None or p.price > prot.price):
                    prot, why = p, "नवा HL ⇒ protected पुढे"
            if trend == "DOWN" and p.kind == "H":
                prev = [q for q in seq[:-1] if q.kind == "H"]
                if prev and p.price < prev[-1].price and (prot is None or p.price < prot.price):
                    prot, why = p, "नवा LH ⇒ protected पुढे"
        tol = eq * sig[i] if np.isfinite(sig[i]) else 0.0
        h1, h2 = _last2(seq, "H")
        l1, l2 = _last2(seq, "L")
        if trend in ("NEUTRAL", "RANGE") and h1 and l1:
            new = h2.bar > brk and l2.bar > brk
            if new and h2.price > h1.price + tol and l2.price > l1.price + tol:
                trend, prot, band, why = "UP", l2, None, "नवा HL + HH"
            elif new and h2.price < h1.price - tol and l2.price < l1.price - tol:
                trend, prot, band, why = "DOWN", h2, None, "नवा LH + LL"
            elif trend == "NEUTRAL" and abs(h2.price - h1.price) <= tol and abs(l2.price - l1.price) <= tol and new:
                trend, band, why = "RANGE", (min(l1.price, l2.price), max(h1.price, h2.price)), "दोन H आणि दोन L जवळपास समान"
        if trend == "UP" and prot is not None and C[i] < prot.price:
            trend, why, brk, prot = "NEUTRAL", f"protected HL {prot.price:,.2f} Daily close ने तुटला", i, prot
        elif trend == "DOWN" and prot is not None and C[i] > prot.price:
            trend, why, brk, prot = "NEUTRAL", f"protected LH {prot.price:,.2f} Daily close ने तुटला", i, prot
        elif trend == "RANGE" and band and (C[i] > band[1] or C[i] < band[0]):
            trend, why, brk, band = "NEUTRAL", "close range पट्ट्याबाहेर", i, None
        shown = trend if i + 1 > int(s["daily_min_sessions"]) else "UNKNOWN"
        out.append(DState(i, pd.Timestamp(d["timestamp"].iloc[i]), kat[i], shown,
                          prot if trend in ("UP", "DOWN", "NEUTRAL") else None, band if trend == "RANGE" else None,
                          why if shown != "UNKNOWN" else "Daily data अपुरा", list(seq)))
    return out


def state_at(states, ts):
    """ts ला माहीत असलेली (known_at ≤ ts) शेवटची Daily state; नसेल ⇒ UNKNOWN."""
    ts = pd.Timestamp(ts)
    best = None
    for x in states:
        if x.known_at <= ts:
            best = x
        else:
            break
    return best if best is not None else DState(-1, None, None, "UNKNOWN", why="Daily candle अजून नाही")


def trade_side(trend):
    """trend ⇒ trade (spec ①): UP ⇒ bull put; DOWN ⇒ bear call; RANGE ⇒ कडेनुसार दोन्ही; NEUTRAL / UNKNOWN ⇒ नाही."""
    return {"UP": ("bull_put",), "DOWN": ("bear_call",), "RANGE": ("bull_put", "bear_call")}.get(trend, ())
