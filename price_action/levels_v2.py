"""
price_action/levels_v2.py
-------------------------
🎓 Levels v2 — "Trader's Eye" engine (TRADE_LEVEL_ENGINE_V2_PROMPT §2, L1–L8). Chart Reader च्या horizontal areas चा पाया.
Abhi (2026-10-08): PAPER bots नव्या levels वर चालतील; G-L1 (eye-match) / G-L2 (edge) अहवाल समांतर, report-only. LIVE ⇒ G-L2 PASS अनिवार्य.

  L1 pivots      `pivot_source`: "elliott" (default) — elliott/swings.py चे causal degree pivots (D1–D3, ATR × swing_atr_mult) area TF वर;
                 level ची degree = pivot ची degree. "htf_fractal" — major_levels v1 चे 240m fractal pivots (तुलनेसाठी).
  L2 lookback    degree नुसार (`lookback_weeks_by_degree`: D1 2, D2 6, D3 26 आठवडे). Recency decay नाही.
  L3 lifecycle   ACTIVE → TESTED(n) (wick / buffer आत close / पुढच्या bar ने reclaim) → BROKEN (buffer पलीकडे close आणि पुढच्या bar ने
                 reclaim नाही, **किंवा** far edge पलीकडे सलग accept_closes closes — buffer आत असले तरी (time acceptance) ⇒ role उलटा) → FLIPPED (उलट बाजूने retest वर नकार) / DEAD (परत उलट break). MAGNET = शेवटच्या chop_window
                 bars मध्ये zone-mid आरपार closes > chop_max_crossings. Transitions फक्त bar close वर.
  L4 quality     प्रत्येक reaction (pivot bar) चा rejection: wick share (H ⇒ upper, L ⇒ lower) आणि close परत zone आत/मागे.
                 score = Σ quality × w_quality + role reversal / flipped bonus + range edge bonus + degree weight (+ origin bonus); MAGNET ⇒ 0.
  L5 zone        [min, max] wick extremes ± zone_pad_mr × MR, किमान zone_min_mr × MR.
  L6 selection   प्रत्येक बाजूला ≤ max_per_side (2), एकूण ≤ max_total (4); प्राधान्य FLIPPED > ≥ 2 quality rejections > range edge;
                 एकमेकांपासून ≥ 2 × tol; MAGNET / BROKEN / DEAD वगळून; प्रत्येकाची `reason` ओळ.
  L7 origin      STRONG_IMPULSE leg (price_action/legs.py) जिथून सुरू झाला तो base zone आत ⇒ origin bonus (setting).
  L8 no-lookahead फक्त दिलेले (बंद) bars; pivot confirmation lag (confirmed_idx ≤ शेवटचा bar); `upto` ⇒ तिथपर्यंतच. Stable `id`
                 = TF + पहिल्या pivot चा प्रकार + वेळ.
"""
import numpy as np
import pandas as pd

DEFAULTS = {
    "pivot_source": "elliott",
    "degrees": [1, 2, 3],
    "swing_atr_mult_by_degree": {1: 3.0, 2: 6.0, 3: 12.0},
    "atr_len": 14,
    "lookback_weeks_by_degree": {1: 2, 2: 6, 3: 26},
    "cluster_tol_mr": 0.75,
    "zone_pad_mr": 0.25,
    "zone_min_mr": 0.5,
    "break_buffer_mr": 0.25,
    "accept_closes": 3,              # time acceptance: far edge पलीकडे सलग इतके closes (buffer आत) ⇒ BROKEN (elliott/breaks.time_accepted)
    "chop_window": 20,
    "chop_max_crossings": 4,
    "max_per_side": 2,
    "max_total": 4,
    "min_quality": 0.3,
    "w_quality": 1.0,
    "w_role_reversal": 2.0,
    "w_edge": 1.0,
    "w_degree": {1: 0.5, 2: 1.0, 3: 1.5},
    "origin_bonus": 1.0,
}


# ---------------------------------------------------------------------------------------------------------------------
# L3 lifecycle
# ---------------------------------------------------------------------------------------------------------------------
def lifecycle(f, zone, role, start, mr, s):
    """zone (lo, hi) ची state, bar `start` पासून शेवटच्या बंद bar पर्यंत. रिटर्न {state, role, tests, broken_at, flipped_at, crossings}."""
    lo, hi = float(zone[0]), float(zone[1])
    o, h, l, c = (f[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(c)
    buf = float(s["break_buffer_mr"]) * mr
    state, cur_role, tests, touching = "ACTIVE", role, 0, False
    broken_at = flipped_at = None
    j = max(int(start), 0)
    from elliott.breaks import time_accepted
    acc = int(s.get("accept_closes", 0) or 0)
    while j < n:
        sup = cur_role == "SUPPORT"
        if acc and state in ("ACTIVE", "TESTED", "FLIPPED") and time_accepted(c, j, lo if sup else hi, "below" if sup else "above", acc,
                                                                                max(int(start), 0) if state != "FLIPPED" else (flipped_at or 0)):
            state, broken_at = "BROKEN", j                                # time acceptance (buffer आत closes) ⇒ role उलटा
            cur_role = "RESISTANCE" if sup else "SUPPORT"
            touching = False
            j += 1
            continue
        beyond = c[j] < lo - buf if sup else c[j] > hi + buf
        if beyond and state in ("ACTIVE", "TESTED", "FLIPPED"):
            if j + 1 >= n:                                            # पुढचा bar अजून नाही ⇒ break अपुष्ट (no-lookahead)
                if not touching:
                    tests += 1
                state = "TESTED" if state == "ACTIVE" else state
                break
            reclaimed = c[j + 1] >= lo if sup else c[j + 1] <= hi
            if reclaimed:                                             # false break ⇒ फक्त test
                if not touching:
                    tests += 1
                touching = True
                state = "TESTED" if state == "ACTIVE" else state
                j += 2
                continue
            state, broken_at = "BROKEN", j + 1
            cur_role = "RESISTANCE" if sup else "SUPPORT"
            touching = False
            j += 2
            continue
        if state == "BROKEN":
            # तुटल्यानंतर: उलट बाजूने retest आणि नकार ⇒ FLIPPED; परत उलट real break (buffer + पुढचा bar, किंवा time acceptance) ⇒ DEAD
            if acc and time_accepted(c, j, hi if cur_role == "RESISTANCE" else lo, "above" if cur_role == "RESISTANCE" else "below", acc,
                                     (broken_at or 0) + 1):
                state = "DEAD"
                j += 1
                continue
            if cur_role == "RESISTANCE":
                if h[j] >= lo and c[j] < lo:
                    state, flipped_at = "FLIPPED", j
                elif c[j] > hi + buf and j + 1 < n and c[j + 1] > hi:
                    state = "DEAD"
            else:
                if l[j] <= hi and c[j] > hi:
                    state, flipped_at = "FLIPPED", j
                elif c[j] < lo - buf and j + 1 < n and c[j + 1] < lo:
                    state = "DEAD"
            j += 1
            continue
        touch = l[j] <= hi and h[j] >= lo
        if touch and not touching and state in ("ACTIVE", "TESTED"):
            tests += 1
            state = "TESTED"
        touching = touch
        j += 1
    mid = (lo + hi) / 2.0
    w = c[max(int(start), n - int(s["chop_window"])):]
    sides = np.sign(w - mid)
    sides = sides[sides != 0]
    crossings = int((np.diff(sides) != 0).sum()) if len(sides) > 1 else 0
    if crossings > int(s["chop_max_crossings"]):
        state = "MAGNET"
    return {"state": state, "role": cur_role, "tests": tests, "broken_at": broken_at, "flipped_at": flipped_at, "crossings": crossings}


# ---------------------------------------------------------------------------------------------------------------------
# L6 selection
# ---------------------------------------------------------------------------------------------------------------------
def _tier(z):
    if z.get("flipped") or z["state"] == "FLIPPED":
        return 0
    if z.get("quality_n", 0) >= 2:
        return 1
    if z.get("edge"):
        return 2
    return 3


_TIER_TEXT = {0: "role flip (FLIPPED)", 1: "≥ 2 quality rejections", 2: "range edge", 3: "major swing"}


def select(cands, price, tol, s):
    """रिटर्न निवडलेले zones (side "below" / "above", reason सह). MAGNET / BROKEN / DEAD वगळले."""
    ok = [dict(z) for z in cands if z["state"] not in ("MAGNET", "BROKEN", "DEAD")]
    for z in ok:
        z["side"] = "below" if (z["low"] + z["high"]) / 2.0 < price else "above"
        z["dist"] = min(abs(price - z["low"]), abs(price - z["high"]))
    out = []
    for side in ("below", "above"):
        pool = sorted([z for z in ok if z["side"] == side], key=lambda z: (_tier(z), z["dist"], -z.get("score", 0)))
        k = 0
        for z in pool:
            if k >= int(s["max_per_side"]) or len(out) >= int(s["max_total"]):
                break
            if any(abs((z["low"] + z["high"]) / 2 - (x["low"] + x["high"]) / 2) < 2 * tol for x in out):
                continue
            z["reason"] = (f"{z['id']}: {_TIER_TEXT[_tier(z)]} · {z['state']}"
                           + (f" ({z.get('tests', 0)} tests)" if z.get("tests") else "")
                           + (f" · D{z['degree']}" if z.get("degree") else "") + f" · score {z.get('score', 0):.1f}")
            out.append(z)
            k += 1
    return out


# ---------------------------------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------------------------------
def _tf_minutes(d):
    diffs = pd.to_datetime(d["timestamp"]).diff().dropna()
    return int(diffs.dt.total_seconds().min() // 60) if len(diffs) else 60


def _pivots(d, s, tf):
    """[(idx, kind, price, degree, ts)] — फक्त confirmed (confirmed_idx ≤ शेवटचा bar) आणि degree lookback आत."""
    last_ts = pd.Timestamp(d["timestamp"].iloc[-1])
    out = []
    if s["pivot_source"] == "htf_fractal":
        from .major_levels import confirmed_pivots, htf_bars
        h = htf_bars(d, 240, ltf_minutes=_tf_minutes(d))
        pos = {t: i for i, t in enumerate(pd.to_datetime(d["timestamp"]))}
        since = last_ts - pd.Timedelta(weeks=int(s["lookback_weeks_by_degree"][2]))
        for i, kind, px in confirmed_pivots(h, 2):
            ts = h["high_ts" if kind == "H" else "low_ts"].iloc[i]
            if ts >= since and ts in pos:
                out.append((pos[ts], kind, float(px), 2, ts))
        return out
    from elliott import swings as W
    fr = d[["timestamp", "open", "high", "low", "close"]].copy()
    fr["bar_end"] = pd.to_datetime(fr["timestamp"]) + pd.Timedelta(minutes=_tf_minutes(d))
    seen = {}
    for deg in s["degrees"]:
        es = {"swing_mode": "atr", "atr_len": int(s["atr_len"]),
              "swing_atr_mult": {deg: float(s["swing_atr_mult_by_degree"][deg])}}
        since = last_ts - pd.Timedelta(weeks=int(s["lookback_weeks_by_degree"][deg]))
        for p in W.degree_pivots(fr, deg, es, tf):
            if p.confirmed_idx is not None and p.confirmed_idx <= len(fr) - 1 and p.ts >= since:
                key = (p.bar_idx, p.kind)
                seen[key] = max(seen.get(key, (0, None))[0], deg), p           # एकच pivot अनेक degrees ⇒ सर्वात मोठी degree
    for (idx, kind), (deg, p) in seen.items():
        out.append((idx, kind, float(p.price), deg, p.ts))
    return out


def _clusters(points, tol):
    pts = sorted(points, key=lambda x: x[2])
    out, cur = [], []
    for p in pts:
        if cur and (p[2] - cur[-1][2] > tol or p[2] - cur[0][2] > 2 * tol):
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def _origins(d, mr):
    try:
        from . import legs as LG
        legs, _, _ = LG.build_legs(d)
        return [lg.start_price for lg in legs if lg.label == LG.STRONG_IMPULSE]
    except Exception:
        return []


def build(df, s=None, tf="1h", upto=None):
    """Area-TF बंद bars → {levels (निवडलेले ≤ 4), candidates (सगळे, state सह), mr, tol}. कुठल्याही bot gate शिवाय."""
    s = {**DEFAULTS, **(s or {})}
    d = (df if upto is None else df.iloc[: upto + 1]).reset_index(drop=True)
    out = {"levels": [], "candidates": [], "mr": None, "tol": None}
    if len(d) < 30:
        return out
    rng = (d["high"] - d["low"]).to_numpy(float)
    mr = float(np.median(rng[-20:]))                                     # KB भाग G: MR = 20 बंद bars (चालू bar वगळून; d मध्ये फक्त बंद bars)
    tol = float(s["cluster_tol_mr"]) * mr
    out.update(mr=mr, tol=tol)
    piv = _pivots(d, s, tf)
    if not piv:
        return out
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    top = max((p for p in piv if p[1] == "H"), key=lambda x: x[2], default=None)
    bot = min((p for p in piv if p[1] == "L"), key=lambda x: x[2], default=None)
    origins = _origins(d, mr) if s.get("origin_bonus") else []
    price = float(c[-1])
    cands = []
    for cl in _clusters(piv, tol):
        kinds = {p[1] for p in cl}
        deg = max(p[3] for p in cl)
        edge = any(p is top or p is bot for p in cl)
        if not (len(cl) >= 2 or deg >= 2 or edge):
            continue
        prices = [p[2] for p in cl]
        lo_, hi_ = min(prices) - s["zone_pad_mr"] * mr, max(prices) + s["zone_pad_mr"] * mr
        if hi_ - lo_ < s["zone_min_mr"] * mr:
            m = (lo_ + hi_) / 2.0
            lo_, hi_ = m - s["zone_min_mr"] * mr / 2.0, m + s["zone_min_mr"] * mr / 2.0
        first = min(cl, key=lambda p: p[0])
        role0 = "RESISTANCE" if first[1] == "H" else "SUPPORT"
        q = []
        for idx, kind, _, _, _ in cl:
            r = max(h[idx] - l[idx], 1e-9)
            wick = (h[idx] - max(o[idx], c[idx])) / r if kind == "H" else (min(o[idx], c[idx]) - l[idx]) / r
            back = (c[idx] <= hi_) if kind == "H" else (c[idx] >= lo_)
            q.append(0.5 * wick + 0.5 * float(back))
        st = lifecycle(d, (lo_, hi_), role0, first[0] + 1, mr, s)
        rr = len(kinds) == 2
        origin = any(lo_ <= x <= hi_ for x in origins)
        score = (sum(q) * s["w_quality"] + s["w_role_reversal"] * (rr or st["state"] == "FLIPPED") + s["w_edge"] * edge
                 + s["w_degree"].get(deg, 0.0) + (s["origin_bonus"] if origin else 0.0))
        if st["state"] == "MAGNET":
            score = 0.0
        cands.append({"id": f"{tf}-{first[1]}{pd.Timestamp(first[4]):%y%m%d%H%M}", "low": round(lo_, 2), "high": round(hi_, 2),
                      "state": st["state"], "role": st["role"], "tests": st["tests"], "degree": int(deg), "n_react": len(cl),
                      "quality_n": int(sum(x >= s["min_quality"] for x in q)), "role_reversal": rr, "flipped": st["state"] == "FLIPPED",
                      "edge": edge, "origin": origin, "score": round(float(score), 2), "crossings": st["crossings"]})
    cands.sort(key=lambda z: -z["score"])
    out["candidates"] = cands
    out["levels"] = select(cands, price, tol, s)
    return out
