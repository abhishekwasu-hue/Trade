"""legs2/features.py — थर 2 v2.1 §1: candle आणि leg features (MASTER §3 व्याख्या; overnight gap नेहमी वगळून).

Candle (d = leg ची दिशा, +1 / −1):
  body%, CLV, CLV_d (up ⇒ CLV, down ⇒ 1 − CLV), wick_opp_d (d-दिशेच्या टोकाकडची wick ÷ range), overlap (आधीच्या candle शी; session
  ओलांडणारी जोडी नाही), overlap3 (आधीच्या 3 candles च्या union शी; session ओलांडत नाही), rng_ratio (swings2.candles), trend_candle(d),
  displacement(d), climax_candle(d) (rng_ratio ≥ 2 आणि d-दिशेने बंद), FVG(d) (3-candle gap: up ⇒ low[i] > high[i−2]; session आत).
Leg (bars (P_(j−1), P_j]): size σ, bars, speed, ER (close-to-close, overnight पद वजा, clamp [0, 1], denominator 0 ⇒ NA, सुरुवात =
P_(j−1) candle चा close), trend_candle%, max_run, avg_overlap, avg CLV_d, n_FVG, n_disp, wave_vol, wave_RVOL, effort_result.
High = low candle: range-आधारित मापं NA (त्या candle ला वगळायचं).
"""
import numpy as np


def _r(A, i):
    return A["h"][i] - A["l"][i]


def body_pct(A, i):
    r = _r(A, i)
    return abs(A["c"][i] - A["o"][i]) / r if r > 0 else None


def clv(A, i):
    r = _r(A, i)
    return (A["c"][i] - A["l"][i]) / r if r > 0 else None


def clv_d(A, i, d):
    x = clv(A, i)
    return None if x is None else (x if d > 0 else 1.0 - x)


def wick_opp_d(A, i, d):
    """d-दिशेच्या टोकाकडची wick (up ⇒ high − max(o, c)) ÷ range."""
    r = _r(A, i)
    if r <= 0:
        return None
    o, c = A["o"][i], A["c"][i]
    return (A["h"][i] - max(o, c)) / r if d > 0 else (min(o, c) - A["l"][i]) / r


def overlap(A, i):
    """आधीच्या candle शी overlap ÷ या candle ची range. Session ओलांडणारी जोडी / H = L ⇒ None."""
    if i < 1 or A["first"][i]:
        return None
    r = _r(A, i)
    if r <= 0:
        return None
    return max(0.0, min(A["h"][i - 1], A["h"][i]) - max(A["l"][i - 1], A["l"][i])) / r


def overlap3(A, i):
    """आधीच्या (त्याच session मधल्या) 3 candles च्या union [min low, max high] शी overlap ÷ range. < 1 आधीची ⇒ None."""
    r = _r(A, i)
    if r <= 0:
        return None
    js = []
    j = i
    while len(js) < 3 and j >= 1 and not A["first"][j]:
        j -= 1
        js.append(j)
    if not js:
        return None
    hi, lo = max(A["h"][k] for k in js), min(A["l"][k] for k in js)
    return max(0.0, min(hi, A["h"][i]) - max(lo, A["l"][i])) / r


def trend_candle(A, i, d, s):
    b, x = body_pct(A, i), clv_d(A, i, d)
    return bool(b is not None and (A["c"][i] - A["o"][i]) * d > 0 and b >= float(s["trend_body"]) and x >= float(s["trend_clv"]))


def displacement(A, rr, i, d, s):
    r = _r(A, i)
    if r <= 0 or not np.isfinite(rr[i]) or (A["c"][i] - A["o"][i]) * d <= 0:
        return False
    w = wick_opp_d(A, i, d)
    return bool(rr[i] >= float(s["disp_rng_ratio"]) and body_pct(A, i) >= float(s["disp_body"]) and w <= float(s["disp_wick_opp"]))


def climax_candle(A, rr, i, d, s):
    return bool(np.isfinite(rr[i]) and rr[i] >= float(s["climax_rng_ratio"]) and (A["c"][i] - A["o"][i]) * d > 0)


def fvg(A, i, d):
    """i = तिसरी candle; तिन्ही एकाच session मध्ये."""
    if i < 2 or A["first"][i] or A["first"][i - 1]:
        return False
    return bool(A["l"][i] > A["h"][i - 2]) if d > 0 else bool(A["h"][i] < A["l"][i - 2])


def er(A, i0, i1):
    """Close-to-close efficiency (i0 चा close ⇒ i1 चा close), overnight पद (09:15 open − आदला close) वजा. 0 path ⇒ None."""
    o, c, first = A["o"], A["c"], A["first"]
    idx = np.arange(i0 + 1, i1 + 1)
    if not len(idx):
        return None
    step = c[idx] - c[idx - 1]
    gap = np.where(first[idx], o[idx] - c[idx - 1], 0.0)
    adj = step - gap
    path = float(np.abs(adj).sum())
    if path <= 0:
        return None
    return min(max(abs(float(adj.sum())) / path, 0.0), 1.0)


def gaps(A, i0, i1):
    idx = np.arange(i0 + 1, i1 + 1)
    g = np.where(A["first"][idx], A["o"][idx] - A["c"][idx - 1], 0.0)
    return {int(b): float(x) for b, x in zip(idx, g) if x != 0.0}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def leg_features(A, rr, vol, rv, bad, i0, i1, d, size, sigma, s):
    """Leg bars (i0, i1] चे features; size = pivot ते pivot (wicks). vol / rv / bad = 15M bars शी जुळणारे arrays (None ⇒ volume नाही)."""
    idx = list(range(i0 + 1, i1 + 1))
    n = len(idx)
    tc = [trend_candle(A, i, d, s) for i in idx]
    run = best = 0
    for x in tc:
        run = run + 1 if x else 0
        best = max(best, run)
    f = {
        "bars": n,
        "er": er(A, i0, i1),
        "body": _mean([body_pct(A, i) for i in idx]),
        "dirc": float(np.mean([(A["c"][i] - A["o"][i]) * d > 0 for i in idx])) if n else None,
        "overlap": _mean([overlap(A, i) for i in idx]),
        "overlap3": _mean([overlap3(A, i) for i in idx]),
        "clv_d": _mean([clv_d(A, i, d) for i in idx]),
        "trend_pct": float(np.mean(tc)) if n else None,
        "max_run": int(best),
        "n_fvg": int(sum(fvg(A, i, d) for i in idx)),
        "n_disp": int(sum(displacement(A, rr, i, d, s) for i in idx)),
        "n_climax": int(sum(climax_candle(A, rr, i, d, s) for i in idx)),
    }
    f["speed"] = (size / sigma / n) if (sigma and n) else None
    good = [i for i in idx if vol is not None and np.isfinite(vol[i]) and not bad[i]]
    f["wave_vol"] = float(sum(vol[i] for i in good)) if good else None
    rvg = [rv[i] for i in idx if rv is not None and np.isfinite(rv[i]) and not bad[i]]
    f["wave_rvol"] = float(np.mean(rvg)) if rvg else None
    f["n_reliable"] = len(rvg)
    f["effort_result"] = (f["wave_vol"] / size) if (f["wave_vol"] is not None and size > 0) else None
    return f
