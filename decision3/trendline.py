"""decision3/trendline.py — थर v2.2 पायरी ⑤ (spec §1 ⑤): K ची आतली तिरकी रेघ आणि तिचा trend-दिशेने close-break ⇒ grade + (gate नाही).

रेघ (t ला माहीत तेवढ्यावरूनच):
  • बिंदू = I_end (K ची सुरुवात) + K मधले confirmed (confirm_bar ≤ t) counter-बाजूचे D`tl_degree` pivots. Bear call (d = DOWN): K वर
    चढते ⇒ खालचे बिंदू (I_end low + L pivots), रेघ चढती; bull put आरसा.
  • शेवटचे दोन बिंदू जे K च्या दिशेने सरकलेत (DOWN ⇒ दुसरा low वर) ⇒ रेघ. स्पर्श = रेघेपासून σ_1H × tl_touch_sigma च्या आत असलेले
    बिंदू (दोन anchors स्वतः = 2 स्पर्श ⇒ spec "K चे ≥ 2 स्पर्श" default ला पूर्ण; जास्त स्पर्श = माहिती; tl_min_touches > 2 ⇒ कडक).
  • Break = रेघ बनल्यानंतरच्या (दुसऱ्या बिंदूचा confirm_bar नंतर) bar चा close रेघेपलीकडे trend-दिशेने (DOWN ⇒ खाली).
रेघ नसेल (बिंदू < 2) ⇒ None (NA ⇒ conviction बेरजेत नाही). Order / broker / AI call नाही.
"""
import numpy as np

UP, DOWN = 1, -1


def k_line(V, t, d, k):
    """K (dict, Pullbacks.at) साठी t ला रेघ: {p1, p2, slope, touches, value_t, broken, break_bar} किंवा None."""
    if not k or not k.get("open") or d not in (UP, DOWN):
        return None
    s = V.s
    A = V.levels.A
    deg = int(s["tl_degree"])
    kind = "L" if d == DOWN else "H"                                     # K चा counter-move: DOWN ⇒ K वर (lows ची रेघ)
    pts = [(int(k["i_end_bar"]), float(k["i_end"]))]
    for p in sorted(V.res["pivots"][deg], key=lambda p: p.bar):
        if p.kind == kind and p.bar > k["i_end_bar"] and p.confirm_bar <= t:
            pts.append((int(p.bar), float(p.price)))
    if len(pts) < 2:
        return None
    pair = None
    for j in range(len(pts) - 1, 0, -1):                                 # शेवटची जोडी जी K च्या दिशेने सरकली
        for i in range(j - 1, -1, -1):
            (b1, y1), (b2, y2) = pts[i], pts[j]
            if b2 > b1 and (y2 - y1) * (-d) > 0:
                pair = (pts[i], pts[j])
                break
        if pair:
            break
    if pair is None:
        return None
    (b1, y1), (b2, y2) = pair
    slope = (y2 - y1) / (b2 - b1)
    sg = V.levels.sig1h[t] if np.isfinite(V.levels.sig1h[t]) else 0.0
    tol = max(float(s["tl_touch_sigma"]) * sg, 1e-6 * max(abs(y1), abs(y2)))   # σ NaN ⇒ float-त्रुटीमुळे anchor गळू नये
    touches = sum(1 for b, y in pts if b >= b1 and abs(y - (y1 + slope * (b - b1))) <= tol)
    if touches < int(s["tl_min_touches"]):
        return None
    conf2 = max([p.confirm_bar for p in V.res["pivots"][deg] if p.bar == b2 and p.kind == kind] or [b2])
    start = max(conf2, b2) + 1
    brk = None
    for i in range(start, t + 1):
        line_i = y1 + slope * (i - b1)
        if (A["close"][i] - line_i) * d > 0:
            brk = i
            break
    return {"p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)], "slope": round(slope, 4), "touches": touches,
            "value_t": round(y1 + slope * (t - b1), 2), "broken": brk is not None, "break_bar": brk}


# ------------------------------------------------------------------------------------------------ ② तिरकी S/R (Abhi, 12 Oct)
def swing_line(V, t, d):
    """Trade-बाजूची तिरकी रेघ (spec ② "trend-दिशेची trendline रेघ तिथे (+)"; "तीच साखळी, मृत्यू पलीकडच्या swing ने"), t ला माहीत
    trend-degree (`level_degree`, D2) swings वरून: bear call (d = DOWN) ⇒ उतरती resistance — शेवटचा confirmed swing high (p2) आणि त्याआधीचा
    त्याच्यापेक्षा उंच high (p1) ज्यांच्यामधला कोणताही high रेघेपलीकडे (वर, σ_1H × tl_touch_sigma पेक्षा जास्त) नाही; bull put आरसा (चढती
    support, lows). नवा swing रेघेपलीकडे ⇒ तोच शेवटचा swing ⇒ जुनी रेघ आपोआप मेली. रिटर्न {p1, p2, slope, touches, value_t, tol} / None."""
    if d not in (UP, DOWN):
        return None
    lv = V.levels
    kind = "H" if d == DOWN else "L"
    pts = sorted(((int(p.bar), float(p.price)) for p in lv.known_pivots(t) if p.kind == kind and p.bar <= t), key=lambda x: x[0])
    if len(pts) < 2:
        return None
    sg = lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0
    b2, y2 = pts[-1]
    tol = max(float(V.s["tl_touch_sigma"]) * sg, 1e-6 * abs(y2))
    for i in range(len(pts) - 2, -1, -1):
        b1, y1 = pts[i]
        if b1 >= b2 or (y2 - y1) * d <= 0:                                 # DOWN ⇒ p2 खाली (lower high); UP ⇒ p2 वर (higher low)
            continue
        slope = (y2 - y1) / (b2 - b1)

        def line(b, y1=y1, b1=b1, slope=slope):
            return y1 + slope * (b - b1)
        if any((y - line(b)) * (-d) > tol for b, y in pts[i + 1:-1]):     # मधला swing रेघेपलीकडे ⇒ ही जोडी रेघ नाही
            continue
        touches = sum(1 for b, y in pts[i:] if abs(y - line(b)) <= tol)
        return {"p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)], "slope": round(slope, 4), "touches": touches,
                "value_t": round(line(t), 2), "tol": round(tol, 2)}
    return None


def confluence_areas(V, t, d, cands):
    """Abhi (12 Oct): तिरकी रेघ + horizontal trade-बाजूचा level ⇒ confluence area = दोघांच्या पट्ट्यांचा overlap (रेघेचा पट्टा = t ला
    रेघेची किंमत ± max(σ_1H × tl_touch_sigma, अर्धी किमान level रुंदी); overlap किमान level रुंदीपेक्षा अरुंद ⇒ मध्याभोवती किमान रुंदी).
    cands = t ला trade-बाजूचे जिवंत levels (snapshot dicts). रेघ फक्त t ला माहीत swings वरून (lookahead नाही); स्पर्श < tl_min_touches ⇒
    काहीच नाही. रेघ एकटी area नाही (spec ②: level जन्म a–d; OPEN_QUESTIONS). रिटर्न [area dict] (births + "tl", `tl` = रेघ)."""
    ln = swing_line(V, t, d)
    if ln is None or ln["touches"] < int(V.s["tl_min_touches"]):
        return []
    lv = V.levels
    sg = lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0
    wmin = float(V.s["level_min_width_sigma"]) * sg
    hw = max(ln["tol"], wmin / 2.0)
    v = ln["value_t"]
    c = float(lv.A["close"][t])
    out = []
    for x in cands:
        lo, hi = max(float(x["lo"]), v - hw), min(float(x["hi"]), v + hw)
        if lo > hi:
            continue
        if hi - lo < wmin:
            m = (lo + hi) / 2.0
            lo, hi = m - wmin / 2.0, m + wmin / 2.0
        dist = 0.0 if lo <= c <= hi else (lo - c if c < lo else c - hi)
        out.append({**x, "id": f"{x['id']}+TL", "lo": round(lo, 2), "hi": round(hi, 2), "births": list(x["births"]) + ["tl"],
                    "dist": round(dist, 2), "above": lo > c, "below": hi < c, "tl": ln, "parent_level": x["id"]})
    return sorted(out, key=lambda a: a["dist"])[:int(V.s["active_levels_max"])]
