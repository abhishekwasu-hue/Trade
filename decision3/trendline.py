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
