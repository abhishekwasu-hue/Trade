"""reader2/anatomy.py — anatomy vote (spec §2b): leg च्या आतल्या candles वरून −1 (पूर्ण सुधारात्मक) ते +1 (पूर्ण आवेगी).

Candle मापं legs2/features.py मधूनच (`leg_features`: body, CLV_d, overlap, ER, displacement, FVG, wave volume); इथे फक्त जे legs2 मध्ये
नाही ते: MR units मधली range expansion / contraction, दोन्ही बाजूंच्या wicks, आधीच्या counter-move शी volume तुलना, effort vs result
(MR units), आतली pause (खोली / कालावधी). प्रत्येक feature ⇒ settings च्या (corrective, impulsive) टोकांमध्ये रेषीय score; NA ⇒ वगळला
(evidence मध्ये "NA" कारणासह). Score = वजनांची सरासरी. Points / % नाहीत.
"""
import numpy as np

from legs2 import features as LF

LEAN_IMP, LEAN_COR, LEAN_NEU = "impulsive", "corrective", "neutral"


def feature_score(x, lo, hi, side):
    """x ⇒ [−1, +1]: lo (corrective टोक) ⇒ −1, hi (impulsive टोक) ⇒ +1, मध्ये रेषीय. side "imp" / "cor" ⇒ एकाच बाजूला."""
    if x is None or not np.isfinite(x) or hi == lo:
        return None
    v = float(np.clip(-1.0 + 2.0 * (x - lo) / (hi - lo), -1.0, 1.0))
    if side == "imp":
        v = max(v, 0.0)
    elif side == "cor":
        v = min(v, 0.0)
    return v


def _mean(xs):
    xs = [x for x in xs if x is not None and np.isfinite(x)]
    return float(np.mean(xs)) if xs else None


def _vol_per_bar(ch, i0, i1, s):
    if ch.vol is None:
        return None
    v = ch.vol[i0 + 1:i1 + 1]
    v = v[np.isfinite(v)]
    return float(v.mean()) if len(v) >= int(s["v_min_reliable"]) else None


def _pause(ch, i0, i1, d):
    """सर्वात खोल आतली उलट चाल (चालू टोकापासून, wicks) आणि नवीन टोकाशिवायचा सर्वात लांब काळ (bars)."""
    A = ch.A
    ext = A["l"][i0] if d > 0 else A["h"][i0]                    # चालू leg-दिशेचं टोक (leg सुरुवातीपासून)
    deep = 0.0
    run = best = 0
    for i in range(i0 + 1, i1 + 1):
        far = A["h"][i] if d > 0 else A["l"][i]
        back = A["l"][i] if d > 0 else A["h"][i]
        if (far - ext) * d > 0:
            ext, run = far, 0
        else:
            run += 1
            best = max(best, run)
        deep = max(deep, (ext - back) * d)
    return deep, best


def raw(ch, i0, i1, d, prev=None):
    """Leg bars (i0, i1] ची मापं (MR units / unit-नसलेली). prev = आधीच्या counter-move चे (j0, j1) (volume तुलनेसाठी)."""
    s, A = ch.s, ch.A
    unit = ch.mr[i0]
    n = i1 - i0
    size = abs(A["h"][i1] - A["l"][i0]) if d > 0 else abs(A["h"][i0] - A["l"][i1])
    size_mr = size / unit if unit and np.isfinite(unit) and unit > 0 else None
    sigma = unit if size_mr is not None else None
    f = LF.leg_features(A, ch.rr, ch.vol, None, np.zeros(len(ch), bool), i0, i1, d, size, sigma, s)
    idx = range(i0 + 1, i1 + 1)
    out = {"bars": n, "size_mr": size_mr, "body": f["body"], "close_loc": f["clv_d"], "overlap": f["overlap"], "er": f["er"],
           "displacement": ((f["n_disp"] + f["n_fvg"]) / n) if n and size_mr is not None else None,
           "wick_opp": _mean([LF.wick_opp_d(A, i, d) for i in idx])}
    rng = ch.rng[i0 + 1:i1 + 1]
    out["range"] = float(rng.mean() / unit) if size_mr is not None and n else None
    half = n // 2
    out["contraction"] = (float(rng[n - half:].mean() / rng[:half].mean())) if half >= 2 and rng[:half].mean() > 0 else None
    wb = float(s["wick_both_min"])
    both = []
    for i in idx:
        r = ch.rng[i]
        if r > 0:
            o, c = A["o"][i], A["c"][i]
            both.append((A["h"][i] - max(o, c)) / r >= wb and (min(o, c) - A["l"][i]) / r >= wb)
    out["wick_both"] = float(np.mean(both)) if both else None
    deep, stall = _pause(ch, i0, i1, d)
    out["pause_depth"] = (deep / size) if size > 0 else None
    out["stall"] = stall / n if n else None
    out["volume"] = out["effort_result"] = None
    if prev is not None and ch.vol is not None:
        j0, j1 = prev
        va, vb = _vol_per_bar(ch, i0, i1, s), _vol_per_bar(ch, j0, j1, s)
        if va is not None and vb:
            out["volume"] = va / vb
            unit_p = ch.mr[j0]
            psize = float(A["h"][j0:j1 + 1].max() - A["l"][j0:j1 + 1].min())
            if unit_p and np.isfinite(unit_p) and psize > 0 and size_mr:
                speed, pspeed = size_mr / n, (psize / unit_p) / (j1 - j0)
                out["effort_result"] = out["volume"] / (speed / pspeed) if speed > 0 else None
    return out


def _fmt(x):
    return "NA" if x is None else f"{x:.2f}"


def vote(ch, i0, i1, d, prev=None):
    """रिटर्न {"score" (None = NA), "cls" (impulsive / corrective / neutral / NA), "evidence": [...], "raw": {...}}."""
    s = ch.s
    n = i1 - i0
    if n <= int(s["short_leg_bars"]):
        return {"score": None, "cls": "NA", "evidence": [{"feature": "bars", "value": n, "score": None, "lean": LEAN_NEU,
                                                           "text": f"{n} bars ≤ {s['short_leg_bars']}: too short to read candles"}],
                "raw": {"bars": n}}
    m = raw(ch, i0, i1, d, prev)
    if m["size_mr"] is None:
        return {"score": None, "cls": "NA", "raw": m,
                "evidence": [{"feature": "mr", "value": None, "score": None, "lean": LEAN_NEU, "text": "median range warm-up: NA"}]}
    ev, num, den = [], 0.0, 0.0
    for k, (lo, hi, side) in s["features"].items():
        x = m.get(k)
        sc = feature_score(x, lo, hi, side)
        lean = LEAN_NEU if sc is None or abs(sc) < 1e-9 else (LEAN_IMP if sc > 0 else LEAN_COR)
        why = "NA (no volume)" if x is None and k in ("volume", "effort_result") else ("NA" if x is None else f"{_fmt(x)}")
        ev.append({"feature": k, "value": x, "score": sc, "lean": lean,
                   "text": f"{k} {why} (corrective {lo}, impulsive {hi}) ⇒ {lean}" if sc is not None else f"{k} {why}"})
        if sc is not None:
            w = float(s["weights"].get(k, 1.0))
            num, den = num + w * sc, den + w
    used = sum(1 for e in ev if e["score"] is not None)
    if used < int(s["min_features"]) or den <= 0:
        return {"score": None, "cls": "NA", "evidence": ev, "raw": m}
    score = num / den
    return {"score": score, "cls": classify(score, s), "evidence": ev, "raw": m}


def classify(score, s):
    if score is None:
        return "NA"
    return LEAN_IMP if score >= float(s["a_hi"]) else (LEAN_COR if score <= float(s["a_lo"]) else LEAN_NEU)


def lower_bars(ch, i0, i1, low):
    """Leg (i0, i1] च्या वेळेतले खालच्या TF चे bars ⇒ (j0, j1) त्या frame मध्ये (j0 = आधीचा bar). नाहीत ⇒ None."""
    ts = ch.d["timestamp"]
    t0 = ts.iloc[i0 + 1] if i0 + 1 < len(ts) else None
    t1 = ts.iloc[i1 + 1] if i1 + 1 < len(ts) else ch.kat[i1]
    if t0 is None:
        return None
    lt = low.d["timestamp"]
    sel = np.flatnonzero((lt >= t0).to_numpy() & (lt < t1).to_numpy())
    if len(sel) < 2 or sel[0] < 1:
        return None
    return int(sel[0] - 1), int(sel[-1])


def leg_vote(ch, leg, prev=None, low=None):
    """Leg चा anatomy vote; low = खालच्या TF चा Chart (उदा. Daily leg साठी 1H) ⇒ दोघांची वजनी सरासरी (spec §2d)."""
    own = vote(ch, leg.i0, leg.i1, leg.dirn, (prev.i0, prev.i1) if prev is not None else None)
    if low is None:
        return own
    jj = lower_bars(ch, leg.i0, leg.i1, low)
    if jj is None:
        return own
    sub = vote(low, jj[0], jj[1], leg.dirn)
    if sub["score"] is None:
        return own
    if own["score"] is None:
        score = sub["score"]
    else:
        w = float(ch.s["lower_weight"])
        score = (1 - w) * own["score"] + w * sub["score"]
    ev = own["evidence"] + [dict(e, feature="lower:" + e["feature"], text="lower TF " + e["text"]) for e in sub["evidence"]]
    return {"score": score, "cls": classify(score, ch.s), "evidence": ev, "raw": own["raw"], "lower": sub}
