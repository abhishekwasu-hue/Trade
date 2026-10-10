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
    """Trendline state: real break **elliott/breaks.py::first_real_break** ने (भाग G: real break ची एकच व्याख्या) — तिरक्या रेषेसाठी
    OHLC मधून रेषेचं मूल्य वजा करून (detrend) level 0 वर. नाहीतर touch ⇒ TESTED, अन्यथा ACTIVE."""
    from elliott import breaks as BRK
    from elliott import settings as ESET
    n = len(d)
    if start >= n:
        return "ACTIVE"
    line = a_px + slope * (np.arange(n) - a_bar)
    det = pd.DataFrame({k: d[k].to_numpy(float) - line for k in ("open", "high", "low", "close")})
    side = "above" if role == "RESISTANCE" else "below"
    if BRK.first_real_break(det, int(start), 0.0, side, dict(ESET.DEFAULTS)) is not None:
        return "BROKEN"
    touch = (det["high"].to_numpy()[start:] >= 0) if role == "RESISTANCE" else (det["low"].to_numpy()[start:] <= 0)
    return "TESTED" if touch.any() else "ACTIVE"


def _line_from(d, pts, a, b, kind, role, s, mr):
    """anchors a, b (pivots) मधून रेषा: touches (सगळे pts मध्ये ± tl_touch_mr × MR), anchors-पासून-आत्तापर्यंत closes, spacing, slope."""
    ts, c = d["timestamp"], d["close"].to_numpy(float)
    slope = (b[1] - a[1]) / max(b[0] - a[0], 1)
    tol = s["tl_touch_mr"] * mr
    on = [p for p in pts if p[0] >= a[0] and abs(p[1] - (a[1] + slope * (p[0] - a[0]))) <= tol]
    last_touch = max(p[0] for p in on)
    seg = np.arange(a[0], last_touch + 1)
    line = a[1] + slope * (seg - a[0])
    beyond = (c[seg] - line) if kind == "H" else (line - c[seg])
    spaced = all(on[i + 1][0] - on[i][0] >= s["tl_min_spacing"] for i in range(len(on) - 1))
    valid = (len(on) >= 3 and not (beyond > s["tl_close_beyond_mr"] * mr).any() and spaced
             and abs(slope) <= s["tl_max_slope_mr"] * mr)
    v = a[1] + slope * (len(d) - 1 - a[0])
    lo, hi = _zone(v, tol)
    return {"id": f"TL-{'R' if role == 'RESISTANCE' else 'S'}{ts.iloc[a[0]]:%y%m%d%H%M}", "tool": "f", "kind": "solid", "role": role,
            "slope": float(slope), "touches": int(len(on)), "valid": bool(valid), "value": float(v), "low": lo, "high": hi,
            "state": _line_state(d, a[0], a[1], slope, role, mr, s, last_touch + 1),
            "anchors": [(str(ts.iloc[p[0]]), round(p[1], 2)) for p in on], "last_touch": int(last_touch),
            "touch_bars": [int(p[0]) for p in on],
            "pair": [(str(ts.iloc[a[0]]), round(a[1], 2)), (str(ts.iloc[b[0]]), round(b[1], 2))],   # रेषा आखणारी जोडी (स्थिर ओळख)
            "bar": int(sorted(p[0] for p in on)[2]) if len(on) >= 3 else int(last_touch),   # "जन्म" = 3रा touch (story no-lookahead)
            "quality": 0.8 if valid else 0.3}


def _rebuild(d, inner, kind, role, anchors, s, mr):
    """Memory मधली रेषा (पहिले दोन anchors) त्याच pivots वरून पुन्हा: touches नव्याने (नवीन touch त्याच रेषेत). Pivots सापडले नाहीत ⇒ None."""
    ts = [str(t) for t in d["timestamp"]]
    pts = [p for p in inner if p[2] == kind]
    a = next((p for p in pts if ts[p[0]] == str(anchors[0][0])), None)
    b = next((p for p in pts if ts[p[0]] == str(anchors[1][0])), None)
    if a is None or b is None or b[0] <= a[0]:
        return None
    return _line_from(d, [p for p in pts if p[0] >= a[0]], a, b, kind, role, s, mr)


def sloping(df, s, mr, upto=None, keep=None):
    """K6.1 sloping trendlines. (1) शेवटचे 3 confirmed swing highs / lows ⇒ candidate रेषा **नेहमी** (≥ 3 pivots असताना).
    (2) शोध (C-V1, 7 Oct उतरती रेषा 28 Sep / 30 Sep / 7 Oct सुटली होती): शेवटच्या tl_search_pivots swings (आतले pivots, ATR ×
        internal_atr_mult) मधल्या प्रत्येक जोडीतून रेषा; valid ⇒ सर्वाधिक touches, मग trade-degree swings वरचे touches जास्त, मग
        सर्वात ताजा touch — प्रति role एक.
    valid (गुण मिळतात) फक्त: ≥ 3 touches (± tl_touch_mr × MR), पहिल्या anchor पासून शेवटच्या touch पर्यंत कुठलाही close रेषेपलीकडे >
    tl_close_beyond_mr × MR नाही, touches ≥ tl_min_spacing bars दूर, |slope| ≤ tl_max_slope_mr × MR प्रति bar. Anchor wicks वर, break closes वर.
    keep (Abhi 2026-10-08 (b), स्थिर ओळख): {role: [anchor0, anchor1]} — memory मधली रेषा कायम (नवीन touches त्याच रेषेत); बदल फक्त
        (1) real break (breaks.py) किंवा (2) दुसरी रेषा स्पष्ट जास्त महत्त्वाची: touches ≥ जुनी + tl_switch_touches आणि ताजा touch.
        प्रति role एकच रेषा, कारण `tl_reason` मध्ये. keep = None ⇒ memory नाही (stateless): सर्वोत्तम tl_max_lines रेषा."""
    d = (df if upto is None else df.iloc[: upto + 1]).reset_index(drop=True)
    if len(d) < 10 or not mr:
        return []
    piv = M.pivots(d, s["swing_atr_mult"])
    inner = M.pivots(d, s["internal_atr_mult"])
    out = []
    for kind, role in (("H", "RESISTANCE"), ("L", "SUPPORT")):
        pts = [p for p in piv if p[2] == kind][-3:]
        if len(pts) >= 3:
            out.append(_line_from(d, pts, pts[0], pts[-1], kind, role, s, mr))
        cand = [p for p in inner if p[2] == kind and p[0] >= len(d) - int(s["tl_search_bars"])][-int(s["tl_search_pivots"]):]
        major_pts = {(str(d["timestamp"].iloc[p[0]]), round(p[1], 2)) for p in piv if p[2] == kind}
        best = []
        for i in range(len(cand)):
            for k in range(i + 1, len(cand)):
                ln = _line_from(d, cand, cand[i], cand[k], kind, role, s, mr)
                if not ln["valid"] or ln["state"] == "BROKEN":
                    continue
                major = sum(1 for an in ln["anchors"] if an in major_pts)      # trade-degree swings वरचे touches जास्त वजनाचे (K1)
                key = (ln["touches"], major, ln["last_touch"], -abs(ln["slope"]))
                best.append((key, ln))
        if keep is not None:                                               # memory mode: प्रति role एकच, स्थिर रेषा
            top = max(best, key=lambda kv: kv[0])[1] if best else None
            old = _rebuild(d, inner, kind, role, keep[role], s, mr) if keep.get(role) else None
            if old is not None and old["valid"] and old["state"] != "BROKEN":
                if (top is not None and top["pair"] != old["pair"]
                        and top["touches"] >= old["touches"] + int(s.get("tl_switch_touches", 2)) and top["last_touch"] > old["last_touch"]):
                    out.append({**top, "tl_reason": f"बदल: {top['id']} स्पष्ट जास्त महत्त्वाची ({top['touches']} वि. {old['touches']} touches, "
                                                    f"ताजा touch) — {old['id']} सोडली"})
                else:
                    out.append({**old, "tl_reason": f"कायम: {old['id']} ({old['touches']} touches)"})
            elif top is not None:
                why = ("real break ⇒ " if old is not None and old["state"] == "BROKEN" else
                       "जुनी रेषा अवैध / सापडली नाही ⇒ " if keep.get(role) else "पहिली निवड: ")
                out.append({**top, "tl_reason": why + top["id"]})
            continue
        # stateless: फक्त एक "सर्वोत्तम" रेषा दर bar ला बदलू शकते ⇒ सर्वोत्तम tl_max_lines valid रेषा (anchors नुसार वेगळ्या) zones म्हणून;
        # प्रत्येक रेषेची ओळख (anchors) स्थिर; बाजार ज्याला react करतोय ती active (areas.active).
        seen = [x["anchors"][:2] for x in out]
        for _, ln in sorted(best, key=lambda kv: kv[0], reverse=True):
            if sum(1 for x in out if x.get("role") == role) >= int(s.get("tl_max_lines", 3)) + 1:
                break
            if ln["anchors"][:2] in seen or any(set(ln["anchors"]) <= set(x["anchors"]) for x in out):
                continue
            seen.append(ln["anchors"][:2])
            out.append(ln)
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
                            "low": zlo, "high": zhi, "role": "SUPPORT" if dirn > 0 else "RESISTANCE", "state": "ACTIVE", "quality": 0.8,
                            "bar": int(end)})                       # जन्म = displacement चा शेवट (zones.py lifecycle इथून)
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
    old = set(map(tuple, (ctx or {}).get("old_gap_edges") or []))
    for i, (lo_, hi_) in enumerate((ctx or {}).get("gap_edges") or []):
        out.append({"id": f"GAP{i}", "tool": "l", "kind": "solid", "low": float(lo_), "high": float(hi_), "role": _role(lo_, hi_, price),
                    "state": "ACTIVE", "quality": 0.3, "old": (float(lo_), float(hi_)) in old})
    return out


def tools(df, horiz, st, ctx, s, mr, keep=None):
    """सगळी साधनं (a–l) ⇒ candidates [{id, tool, kind, low, high, role, state, quality, …}]. df = trigger TF बंद bars."""
    price = float(df["close"].iloc[-1])
    cands = _horizontal(horiz)
    cands += base_zones(df, s, mr)
    cands += _liquidity(df, s, mr, price)
    cands += sloping(df, s, mr, keep=keep)
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
    # K6.4: बाजार ज्या area ला react करतोय = ताजे bars **आणि** correction चं ताजं टोक (शेवटच्या active_extreme_bars मधलं
    # trade-विरुद्ध टोक; 7 Oct: 12:00 चा 22,717.65 rejection, entry 14:30 ला) — त्या bar ने शिवलेला area सुद्धा
    n = len(df)
    win = df.tail(int(s.get("active_extreme_bars", n_recent)))
    k = int(win["high"].to_numpy(float).argmax() if side < 0 else win["low"].to_numpy(float).argmin()) if len(win) else 0
    ext = win.iloc[[k]] if len(win) else recent.iloc[:0]
    both = pd.concat([recent, ext])
    lo, hi = both["low"].to_numpy(float), both["high"].to_numpy(float)
    back = (n - 1 - np.concatenate([np.arange(n - len(recent), n), [n - len(win) + k] if len(win) else []])).astype(float)
    out = {"area": None, "quality": 0.0, "confluence": [], "confluence_extra": 0, "touched_ids": [], "intersection": False}
    touched = []
    for z in cands:
        if z.get("kind") != "solid" or z.get("state") in BAD or z.get("role") != want:
            continue
        if z.get("tool") == "f" and not z.get("valid"):
            continue
        # trendline चं मूल्य त्या bar वर (शेवटच्या bar चं नाही — V3 review): band − slope × (मागे किती bars)
        shift = float(z.get("slope") or 0.0) * back if z.get("tool") == "f" else 0.0
        if ((lo <= z["high"] - shift) & (hi >= z["low"] - shift)).any():
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
    from opportunity_engine.cas import daily_levels
    g = daily_levels(d)                                                  # CAS: PDH/PDL CAS bars वगळून; PDC = official close
    g = g[g["n"] >= 200]
    if g.empty:
        return {}
    out = {"pdh": float(g["high"].iloc[-1]), "pdl": float(g["low"].iloc[-1]), "pdc": float(g["close"].iloc[-1])}
    wk = t.normalize() - pd.Timedelta(days=t.weekday())
    prev = g[(g.index < wk) & (g.index >= wk - pd.Timedelta(days=7))]
    if len(prev):
        out.update(week_high=float(prev["high"].max()), week_low=float(prev["low"].min()))
    return out
