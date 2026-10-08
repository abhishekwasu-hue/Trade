"""chart_reader/areas.py — KB टप्पा 3: **सगळी 12 साधनं, प्रत्येक signal साठी** (a–l), मग active area (K6.4) आणि confluence (K7).

🎓 Abhi (2026-10-08): 7 Oct ला फक्त horizontal पाहिल्याने उतरती trendline सुटली — म्हणून प्रत्येक वेळी पूर्ण यादी.
  a horizontal swing cluster (K4) · b role flip (K4) · c supply/demand base (displacement च्या आधीचा, K4) · d range edge (K4)
  e liquidity: equal highs/lows, आधीचे swing extremes, PDH/PDL (K5) · f sloping trendline ≥ 3 touches (K6)
  g channel — impulse आणि correction चा (K6, मोजपट्टी) · h Fibonacci 38.2/50/61.8/78.6 ± band (K7, मोजपट्टी) · i C = A (K3/K7, मोजपट्टी)
  j round numbers 100/500/1000 (K8) · k PDH/PDL/PDC, आठवड्याचे H/L (K8) · l gap edge / PDC, जुने unfilled gaps (K13)
"ठोस" (solid) साधनंच active area होऊ शकतात. मोजपट्टी (g/h/i) ला गुण फक्त ठोस area शी overlap असेल तर (एकट्या Fibonacci ला 0).
Active area (K6.4): ताज्या bars नी प्रत्यक्ष शिवलेला, trade बाजूच्या role चा, MAGNET / BROKEN / DEAD नसलेला ठोस area — गुणवत्तेनुसार;
horizontal आणि sloping ≤ 0.5 MR मध्ये भेटत असतील तर तो छेदबिंदू सर्वोच्च (quality 1.0).
"""
import numpy as np
import pandas as pd

from . import measures as M

BAD = ("MAGNET", "BROKEN", "DEAD")
RULERS = ("g", "h", "i")


def _zone(mid, half):
    return float(mid - half), float(mid + half)


def _role(lo, hi, price):
    return "SUPPORT" if (lo + hi) / 2.0 < price else "RESISTANCE"


# ---------------------------------------------------------------------------------------------------------------------
# f: sloping trendline (K6.1)
# ---------------------------------------------------------------------------------------------------------------------
def _line_state(d, a_bar, a_px, slope, role, mr, s, start):
    c, h, lo = (d[k].to_numpy(float) for k in ("close", "high", "low"))
    buf = s["origin_break_buffer_mr"] * mr
    state = "ACTIVE"
    for j in range(start, len(c)):
        v = a_px + slope * (j - a_bar)
        beyond = c[j] > v + buf if role == "RESISTANCE" else c[j] < v - buf
        if beyond and j + 1 < len(c):
            v1 = a_px + slope * (j + 1 - a_bar)
            if (c[j + 1] > v1) if role == "RESISTANCE" else (c[j + 1] < v1):
                return "BROKEN"                                           # real break: buffer पलीकडे close + पुढचा bar reclaim नाही
        if (h[j] >= v if role == "RESISTANCE" else lo[j] <= v) and state == "ACTIVE":
            state = "TESTED"
    return state


def sloping(df, s, mr, upto=None):
    """शेवटचे 3 confirmed swing highs (resistance) / lows (support) ⇒ candidate रेषा **नेहमी** (≥ 3 pivots असताना).
    valid (गुण मिळतात) फक्त: ≥ 3 touches (± tl_touch_mr × MR), anchors मध्ये कुठलाही close रेषेपलीकडे > tl_close_beyond_mr × MR नाही,
    touches ≥ tl_min_spacing bars दूर, |slope| ≤ tl_max_slope_mr × MR प्रति bar. Anchor wicks वर, break चा निर्णय closes वर."""
    d = (df if upto is None else df.iloc[: upto + 1]).reset_index(drop=True)
    if len(d) < 10 or not mr:
        return []
    piv = M.pivots(d, s["swing_atr_mult"])
    ts, c = d["timestamp"], d["close"].to_numpy(float)
    out = []
    for kind, role in (("H", "RESISTANCE"), ("L", "SUPPORT")):
        pts = [p for p in piv if p[2] == kind][-3:]
        if len(pts) < 3:
            continue
        a, b = pts[0], pts[-1]
        slope = (b[1] - a[1]) / max(b[0] - a[0], 1)
        on = lambda p: abs(p[1] - (a[1] + slope * (p[0] - a[0]))) <= s["tl_touch_mr"] * mr       # noqa: E731
        touches = sum(on(p) for p in pts)
        seg = np.arange(a[0], b[0] + 1)
        line = a[1] + slope * (seg - a[0])
        beyond = (c[seg] - line) if kind == "H" else (line - c[seg])
        spaced = all(pts[i + 1][0] - pts[i][0] >= s["tl_min_spacing"] for i in range(len(pts) - 1))
        valid = (touches >= 3 and not (beyond > s["tl_close_beyond_mr"] * mr).any() and spaced
                 and abs(slope) <= s["tl_max_slope_mr"] * mr)
        v = a[1] + slope * (len(d) - 1 - a[0])
        lo, hi = _zone(v, s["tl_touch_mr"] * mr)
        out.append({"id": f"TL-{'R' if role == 'RESISTANCE' else 'S'}{ts.iloc[a[0]]:%y%m%d%H%M}", "tool": "f", "kind": "solid", "role": role,
                    "slope": float(slope), "touches": int(touches), "valid": bool(valid), "value": float(v), "low": lo, "high": hi,
                    "state": _line_state(d, a[0], a[1], slope, role, mr, s, b[0] + 1),
                    "anchors": [(str(ts.iloc[p[0]]), round(p[1], 2)) for p in pts], "quality": 0.8 if valid else 0.3})
    return out


# ---------------------------------------------------------------------------------------------------------------------
# c: base before displacement (K4)
# ---------------------------------------------------------------------------------------------------------------------
def base_zones(df, s, mr, lookback=120, keep=3):
    """Displacement (≥ 2 सलग candles body ≥ disp_body_frac × range आणि range ≥ disp_body_mr × MR, किंवा एक ≥ disp_single_mr × MR)
    + आधीचा swing तुटलेला (BOS) ⇒ त्याच्या आधीचा base (1–4 लहान candles, range ≤ base_max_range_mr × MR). Zone: demand = [lowest low,
    highest body-top]; supply उलट; उंची ≤ base_max_height_mr × MR."""
    d = df.tail(lookback).reset_index(drop=True)
    o, h, lo, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    rng, body = h - lo, np.abs(c - o)
    big = (rng >= s["disp_body_mr"] * mr) & (body >= s["disp_body_frac"] * np.maximum(rng, 1e-9))
    out, i = [], 1
    while i < len(d):
        dirn = 1 if c[i] > o[i] else -1
        single = rng[i] >= s["disp_single_mr"] * mr and body[i] >= s["disp_body_frac"] * rng[i]
        pair = big[i] and i + 1 < len(d) and big[i + 1] and (c[i + 1] > o[i + 1]) == (dirn > 0)
        if not (single or pair):
            i += 1
            continue
        end = i + (1 if pair else 0)
        prior = d.iloc[max(0, i - 20):i]
        bos = (c[end] > prior["high"].max()) if dirn > 0 else (c[end] < prior["low"].min())
        j, base = i - 1, []
        while j >= 0 and len(base) < 4 and rng[j] <= s["base_max_range_mr"] * mr:
            base.append(j)
            j -= 1
        if bos and base:
            if dirn > 0:
                zlo, zhi = float(lo[base].min()), float(np.maximum(o[base], c[base]).max())
            else:
                zlo, zhi = float(np.minimum(o[base], c[base]).min()), float(h[base].max())
            if zhi - zlo <= s["base_max_height_mr"] * mr:
                out.append({"id": f"BASE-{'D' if dirn > 0 else 'S'}{d['timestamp'].iloc[base[-1]]:%y%m%d%H%M}", "tool": "c", "kind": "solid",
                            "low": zlo, "high": zhi, "role": "SUPPORT" if dirn > 0 else "RESISTANCE", "state": "ACTIVE", "quality": 0.8})
        i = end + 1
    return out[-keep:]


# ---------------------------------------------------------------------------------------------------------------------
# सगळी साधनं
# ---------------------------------------------------------------------------------------------------------------------
def _horizontal(horiz):
    out = []
    for z in horiz:
        if z.get("flipped") or z.get("state") == "FLIPPED" or z.get("role_reversal"):
            tool, q = "b", 1.0
        elif z.get("edge"):
            tool, q = "d", 0.6
        else:
            tool, q = "a", 0.8 if z.get("quality_n", 0) >= 2 else (0.5 if z.get("degree", 0) >= 2 else 0.3)
        out.append({**z, "tool": tool, "kind": "solid", "quality": q})
    return out


def _liquidity(d, s, mr, price):
    piv = M.pivots(d, s["internal_atr_mult"])
    out = []
    for kind in ("H", "L"):
        pts = [p for p in piv if p[2] == kind][-8:]
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if abs(pts[i][1] - pts[j][1]) <= s["eq_tol_mr"] * mr and pts[j][0] - pts[i][0] >= s["eq_min_bars"]:
                    lo_, hi_ = sorted((pts[i][1], pts[j][1]))
                    lo_, hi_ = lo_ - 0.1 * mr, hi_ + 0.1 * mr
                    lvl = max(pts[i][1], pts[j][1]) if kind == "H" else min(pts[i][1], pts[j][1])
                    out.append({"id": f"EQ{kind}-{pts[j][0]}", "tool": "e", "kind": "solid", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price),
                                "state": "ACTIVE", "quality": 0.6, "pool": "equal_highs" if kind == "H" else "equal_lows",
                                "level": float(lvl), "bar": int(pts[j][3] if pts[j][3] is not None else pts[j][0])})
        if pts:                                                             # आधीचा swing extreme (stop pool)
            p = pts[-1]
            lo_, hi_ = _zone(p[1], 0.1 * mr)
            out.append({"id": f"SW{kind}-{p[0]}", "tool": "e", "kind": "solid", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price),
                        "state": "ACTIVE", "quality": 0.4, "pool": "swing_high" if kind == "H" else "swing_low", "level": float(p[1]),
                        "bar": int(p[3] if p[3] is not None else p[0])})
    return out


def _channels(d, st, s, mr, price):
    out = []
    corr = st.get("correction") or []
    imp = st.get("impulse")
    n = len(d)
    if imp and len(corr) >= 3 and st.get("correction_bars"):
        (a0b, a1b, b1b) = st["correction_bars"][:3]
        a0, a1, b1 = corr[0], corr[1], corr[2]
        slope = (b1 - a0) / max(b1b - a0b, 1)                             # K6.3: A ची सुरुवात – B चं टोक; A च्या टोकातून समांतर
        v = a1 + slope * (n - 1 - a1b)
        lo_, hi_ = _zone(v, s["fib_band_mr"] * mr)
        out.append({"id": "CH-corr", "tool": "g", "kind": "ruler", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price), "state": "ACTIVE",
                    "quality": 0.5})
    if imp:
        sb, eb = imp["start_bar"], imp["end_bar"]
        if eb > sb:
            slope = (imp["end"] - imp["origin"]) / (eb - sb)              # impulse channel: origin–end रेषा, समांतर रेषा impulse च्या सुरुवातीतून
            v = imp["origin"] + slope * (n - 1 - sb)
            lo_, hi_ = _zone(v, s["fib_band_mr"] * mr)
            out.append({"id": "CH-imp", "tool": "g", "kind": "ruler", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price), "state": "ACTIVE",
                        "quality": 0.4})
    return out


def _fib(st, s, mr, price):
    imp = st.get("impulse")
    if not imp or abs(imp["end"] - imp["origin"]) < s["fib_min_impulse_mr"] * mr:
        return []
    out = []
    for r in (0.382, 0.5, 0.618, 0.786):
        v = imp["end"] - (imp["end"] - imp["origin"]) * r
        lo_, hi_ = _zone(v, s["fib_band_mr"] * mr)
        out.append({"id": f"FIB{r:.3f}", "tool": "h", "kind": "ruler", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price),
                    "state": "ACTIVE", "quality": 0.5})
    return out


def _c_eq_a(st, s, mr, price):
    corr = st.get("correction") or []
    if len(corr) < 3:
        return []
    a = corr[1] - corr[0]
    out = []
    for r in (0.618, 1.0, 1.618):
        v = corr[2] + a * r
        lo_, hi_ = _zone(v, s["fib_band_mr"] * mr)
        out.append({"id": f"C={r:g}A", "tool": "i", "kind": "ruler", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price), "state": "ACTIVE",
                    "quality": 0.5})
    return out


def _rounds(price, s, mr):
    out = []
    base = int(price // 100) * 100
    for v in range(base - 300, base + 400, 100):
        nearest = v in (base, base + 100)                                   # जवळचे खालचा / वरचा 100 नेहमी candidate
        if abs(v - price) > s["round_max_dist_mr"] * mr and not nearest:
            continue
        w = 3 if v % 1000 == 0 else 2 if v % 500 == 0 else 1
        lo_, hi_ = _zone(v, s["level_band_mr"] * mr)
        out.append({"id": f"RN{v}", "tool": "j", "kind": "solid", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price), "state": "ACTIVE",
                    "quality": {1: 0.2, 2: 0.3, 3: 0.4}[w]})
    return out


def _pd_levels(ctx, s, mr, price):
    out = []
    for key, name, q in (("pdh", "PDH", 0.5), ("pdl", "PDL", 0.5), ("pdc", "PDC", 0.4), ("week_high", "PWH", 0.5), ("week_low", "PWL", 0.5)):
        v = (ctx or {}).get(key)
        if v is None:
            continue
        lo_, hi_ = _zone(float(v), s["level_band_mr"] * mr)
        out.append({"id": name, "tool": "k", "kind": "solid", "low": lo_, "high": hi_, "role": _role(lo_, hi_, price), "state": "ACTIVE",
                    "quality": q, "pool": name.lower() if name in ("PDH", "PDL") else None})
    return out


def _gaps(ctx, price):
    out = []
    for i, (lo_, hi_) in enumerate((ctx or {}).get("gap_edges") or []):
        out.append({"id": f"GAP{i}", "tool": "l", "kind": "solid", "low": float(lo_), "high": float(hi_), "role": _role(lo_, hi_, price),
                    "state": "ACTIVE", "quality": 0.3})
    return out


def tools(df, horiz, st, ctx, s, mr):
    """सगळी साधनं (a–l) ⇒ candidates [{id, tool, kind, low, high, role, state, quality, …}]. df = trigger TF बंद bars."""
    price = float(df["close"].iloc[-1])
    cands = _horizontal(horiz)
    cands += base_zones(df, s, mr)
    cands += _liquidity(df, s, mr, price)
    cands += sloping(df, s, mr)
    cands += _channels(df, st or {}, s, mr, price)
    cands += _fib(st or {}, s, mr, price)
    cands += _c_eq_a(st or {}, s, mr, price)
    cands += _rounds(price, s, mr)
    cands += _pd_levels(ctx, s, mr, price)
    cands += _gaps(ctx, price)
    return cands


# ---------------------------------------------------------------------------------------------------------------------
# active area (K6.4) + confluence (K7)
# ---------------------------------------------------------------------------------------------------------------------
def _overlap(a, b, gap=0.0):
    return a["low"] - gap <= b["high"] and b["low"] - gap <= a["high"]


def active(df, cands, side, s, mr, n_recent=3):
    """रिटर्न {area | None, quality 0–1, confluence [साधन letters], confluence_extra, touched_ids, intersection}."""
    want = "SUPPORT" if side > 0 else "RESISTANCE"
    recent = df.tail(int(n_recent))
    lo, hi = recent["low"].to_numpy(float), recent["high"].to_numpy(float)
    out = {"area": None, "quality": 0.0, "confluence": [], "confluence_extra": 0, "touched_ids": [], "intersection": False}
    touched = []
    for z in cands:
        if z.get("kind") != "solid" or z.get("state") in BAD or z.get("role") != want:
            continue
        if z.get("tool") == "f" and not z.get("valid"):
            continue
        if ((lo <= z["high"]) & (hi >= z["low"])).any():
            touched.append(z)
    out["touched_ids"] = [z["id"] for z in touched]
    if not touched:
        return out
    near = 0.5 * mr
    best = max(touched, key=lambda z: (z.get("quality", 0.0), z.get("tool") in ("b", "a", "f")))
    q = float(best.get("quality", 0.0))
    inter = any(z["tool"] == "f" for z in touched if _overlap(z, best, near)) and any(z["tool"] in ("a", "b", "c", "d") for z in touched
                                                                                      if _overlap(z, best, near))
    if inter:
        q = 1.0                                                             # horizontal ∩ sloping (K6.4)
    conf = sorted({z["tool"] for z in cands if z is not best and z.get("state") not in BAD and z["tool"] != best["tool"]
                   and _overlap(z, best, near) and not (z["tool"] == "f" and not z.get("valid"))})
    out.update(area=dict(best), quality=q, confluence=conf, confluence_extra=len(conf), intersection=bool(inter))
    return out


def targets(cands, side, entry):
    """trade दिशेने पुढचे **ठोस** opposite areas [(price, id)] (जवळचा आधी). मोजपट्टी target नाही."""
    want = "RESISTANCE" if side > 0 else "SUPPORT"
    out = []
    for z in cands:
        if z.get("kind") != "solid" or z.get("state") == "MAGNET" or (z.get("tool") == "f" and not z.get("valid")):
            continue
        if z.get("role") != want:
            continue
        p = z["low"] if side > 0 else z["high"]
        if (p > entry) if side > 0 else (p < entry):
            out.append((float(p), z["id"]))
    return sorted(out, key=lambda x: x[0] if side > 0 else -x[0])


TARGET_TOOLS = ("a", "b", "c", "d", "k")


def trade_targets(cands, side, entry, impulse_end=None):
    """KB टप्पा 7: target = impulse चं टोक (असेल तर), मग त्यापलीकडचे ठोस HTF areas (a/b/c/d/k). Entry आणि impulse टोक यांच्यामधले
    areas (correction चे आतले swing / equal pools, round numbers, gap edges, PDC …) target नाहीत ⇒ obstacles (गोष्टीत नोंद).
    रिटर्न (targets [(price, id)], obstacles [(price, id)]), जवळचा आधी."""
    allt = targets(cands, side, entry)
    beyond = (lambda p: p >= impulse_end) if side > 0 else (lambda p: p <= impulse_end)
    if impulse_end is None or not ((impulse_end > entry) if side > 0 else (impulse_end < entry)):
        tg = [x for x in allt if next(z for z in cands if z["id"] == x[1]).get("tool") in TARGET_TOOLS]
        return tg, [x for x in allt if x not in tg]
    tools = {z["id"]: z.get("tool") for z in cands}
    tg = [(float(impulse_end), "IMPULSE-END")] + [x for x in allt if beyond(x[0]) and tools.get(x[1]) in TARGET_TOOLS]
    obst = [x for x in allt if not beyond(x[0])]
    return tg, obst


def prior_levels(df1m, asof):
    """PDH / PDL / PDC (आधीचा पूर्ण दिवस) आणि आधीच्या आठवड्याचा H / L — फक्त पूर्ण झालेल्या sessions वरून (no-lookahead)."""
    t = pd.Timestamp(asof)
    d = df1m[pd.to_datetime(df1m["timestamp"]) < t.normalize()]
    if d.empty:
        return {}
    g = d.groupby(pd.to_datetime(d["timestamp"]).dt.normalize()).agg(high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                                                     n=("close", "size"))
    g = g[g["n"] >= 200]
    if g.empty:
        return {}
    out = {"pdh": float(g["high"].iloc[-1]), "pdl": float(g["low"].iloc[-1]), "pdc": float(g["close"].iloc[-1])}
    wk = t.normalize() - pd.Timedelta(days=t.weekday())
    prev = g[(g.index < wk) & (g.index >= wk - pd.Timedelta(days=7))]
    if len(prev):
        out.update(week_high=float(prev["high"].max()), week_low=float(prev["low"].min()))
    return out
