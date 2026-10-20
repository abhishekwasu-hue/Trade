"""decision3/trendline.py — थर v2.2 पायरी ⑤ (spec §1 ⑤): K ची आतली तिरकी रेघ आणि तिचा trend-दिशेने close-break ⇒ grade + (gate नाही).

रेघ (t ला माहीत तेवढ्यावरूनच):
  • बिंदू = I_end (K ची सुरुवात) + K मधले confirmed (confirm_bar ≤ t) counter-बाजूचे D`tl_degree` pivots. Bear call (d = DOWN): K वर
    चढते ⇒ खालचे बिंदू (I_end low + L pivots), रेघ चढती; bull put आरसा.
  • शेवटचे दोन बिंदू जे K च्या दिशेने सरकलेत (DOWN ⇒ दुसरा low वर) ⇒ रेघ. स्पर्श = रेघेपासून σ_1H × tl_touch_sigma च्या आत असलेले
    बिंदू (दोन anchors स्वतः = 2 स्पर्श ⇒ spec "K चे ≥ 2 स्पर्श" default ला पूर्ण; जास्त स्पर्श = माहिती; tl_min_touches > 2 ⇒ कडक).
  • Break = रेघ बनल्यानंतरच्या (दुसऱ्या बिंदूचा confirm_bar नंतर) bar चा close रेघेपलीकडे trend-दिशेने (DOWN ⇒ खाली).
रेघ नसेल (बिंदू < 2) ⇒ None (NA ⇒ conviction बेरजेत नाही). Order / broker / AI call नाही.

वरचे σ / स्पर्श-संख्या नियम = `line_rule = "sigma"` (जुनं, what-if). Default `line_rule = "logic"` (method §3 Lines, K6):
  • रेघ = दोन वेगळे reactions (मधे उलट swing — `separate`); स्पर्श = candle ची wick रेघेपर्यंत, body बाजूला (`touches`); संख्या / σ नाही.
  • दोन reactions मधे कोणताही close रेघेपलीकडे नाही; त्यानंतर रेघ तुटते फक्त close पलीकडे + पलीकडे swing ने (`broken_by`, K6.5) —
    परत आलेला close = throw-over, रेघ उभी.
  • K रेघ: trigger = bar t (commitment candle) चा close-through; आधीच गेलेली रेघ ⇒ `broken_before`, trigger नाही.
  • Confluence = रेघ area च्या पट्ट्यातून ⇒ तोच area, "tl" label (नवा / अरुंद पट्टा नाही).
"""
import numpy as np

UP, DOWN = 1, -1


def _logic(s):
    r = s.get("line_rule", "logic")
    if r not in ("logic", "sigma"):
        raise ValueError(f"line_rule {r!r} — logic / sigma पैकी")
    return r == "logic"


def touches(A, b, y, kind):
    """Method §3 Lines: candle b touches a line at price y when its wick reaches the line while its body stays on the respected side —
    swing high (kind "H", line above price): body top ≤ y ≤ high; swing low: low ≤ y ≤ body bottom. A comparison, never a tolerance."""
    o, c = float(A["open"][b]), float(A["close"][b])
    if kind == "H":
        return bool(max(o, c) <= y <= float(A["high"][b]))
    return bool(float(A["low"][b]) <= y <= min(o, c))


def broken_by(A, pivs, kind, line, side, start, end):
    """Method §3 / K6.5 (as an area): a line is broken by a close beyond it (`side` +1 = above) AND a swing of `kind` formed beyond it
    after that close (pivs = swings known at the read bar); a close that comes back before any such swing = a throw-over (noise).
    Bars start … end only. Returns the bar of the close that began that excursion (no close back on the line's side between it and the
    swing), or None."""
    def beyond(i):
        return (float(A["close"][i]) - line(i)) * side > 0
    for i in range(start, end + 1):
        if beyond(i) and any(p.kind == kind and i <= p.bar <= end and (float(p.price) - line(p.bar)) * side > 0 and
                             all(beyond(j) for j in range(i, p.bar)) for p in pivs):
            return i
    return None


def separate(pivs, b1, b2, kind):
    """Method §3: two anchors are separate reactions when price left the line between them — a swing of the opposite kind lies between."""
    return any(p.kind != kind and b1 < p.bar < b2 for p in pivs)


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
    logic = _logic(s)
    known = [p for p in V.res["pivots"][deg] if p.confirm_bar <= t]
    pair = None
    for j in range(len(pts) - 1, 0, -1):                                 # शेवटची जोडी जी K च्या दिशेने सरकली (logic: दोन वेगळे reactions)
        for i in range(j - 1, -1, -1):
            (b1, y1), (b2, y2) = pts[i], pts[j]
            if b2 > b1 and (y2 - y1) * (-d) > 0 and (not logic or separate(known, b1, b2, kind)):
                pair = (pts[i], pts[j])
                break
        if pair:
            break
    if pair is None:
        return None
    (b1, y1), (b2, y2) = pair
    slope = (y2 - y1) / (b2 - b1)
    if logic:                                                              # method §3: the two anchors (separate reactions) are the line;
        n_t = sum(1 for b, y in pts if b >= b1 and (b in (b1, b2) or touches(A, b, y1 + slope * (b - b1), kind)))   # touches = facts
    else:
        sg = V.levels.sig1h[t] if np.isfinite(V.levels.sig1h[t]) else 0.0
        tol = max(float(s["tl_touch_sigma"]) * sg, 1e-6 * max(abs(y1), abs(y2)))   # σ NaN ⇒ float-त्रुटीमुळे anchor गळू नये
        n_t = sum(1 for b, y in pts if b >= b1 and abs(y - (y1 + slope * (b - b1))) <= tol)
        if n_t < int(s["tl_min_touches"]):
            return None
    conf2 = max([p.confirm_bar for p in V.res["pivots"][deg] if p.bar == b2 and p.kind == kind] or [b2])
    start = max(conf2, b2) + 1
    brk = None
    for i in range(start, t + 1):
        line_i = y1 + slope * (i - b1)
        if (A["close"][i] - line_i) * d > 0:
            brk = i
            break
    out = {"p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)], "slope": round(slope, 4), "touches": n_t,
           "value_t": round(y1 + slope * (t - b1), 2), "broken": brk is not None, "break_bar": brk}
    if logic:                                                              # method §3 trigger form: the correction's own line closed through
        def line(b):                                                       # BY the commitment candle (bar t); before it the line is gone only
            return y1 + slope * (b - b1)                                   # by a close beyond + a swing beyond (K6.5) — a close that came
        gone = broken_by(A, known, kind, line, d, start, t - 1)           # back is a throw-over and the line still stands
        beyond = (lambda i: (float(A["close"][i]) - line(i)) * d > 0)      # noqa: E731
        now = gone is None and t >= start and beyond(t) and (t == start or not beyond(t - 1))
        out.update(broken=bool(now), broken_before=gone, break_bar=t if now else gone)
    return out


# ------------------------------------------------------------------------------------------------ ② तिरकी S/R (Abhi, 12 Oct)
def swing_line(V, t, d):
    """Trade-बाजूची तिरकी रेघ (spec ② "trend-दिशेची trendline रेघ तिथे (+)"; "तीच साखळी, मृत्यू पलीकडच्या swing ने"), t ला माहीत
    trend-degree (`level_degree`, D2) swings वरून: bear call (d = DOWN) ⇒ उतरती resistance — शेवटचा confirmed swing high (p2) आणि त्याआधीचा
    त्याच्यापेक्षा उंच high (p1) ज्यांच्यामधला कोणताही high रेघेपलीकडे (वर, σ_1H × tl_touch_sigma पेक्षा जास्त) नाही; bull put आरसा (चढती
    support, lows). नवा swing रेघेपलीकडे ⇒ तोच शेवटचा swing ⇒ जुनी रेघ आपोआप मेली; p2 नंतर (t − 1 पर्यंत) एखादा close रेघेपलीकडे ⇒ रेघ
    तुटली (k_line सारखं; t चा स्वतःचा close = ③ breakout तपासणी). रिटर्न {p1, p2, slope, touches, value_t, tol} / None.
    (वरचं = line_rule "sigma". Logic: जोडी = दोन वेगळे reactions, मधे कोणताही close पलीकडे नाही; p2 नंतर रेघ फक्त close + swing
    पलीकडे ने मरते; touches = candle ने; tol = 0.)"""
    if d not in (UP, DOWN):
        return None
    lv = V.levels
    kind = "H" if d == DOWN else "L"
    known = [p for p in lv.known_pivots(t) if p.bar <= t]
    pts = sorted(((int(p.bar), float(p.price)) for p in known if p.kind == kind), key=lambda x: x[0])
    if len(pts) < 2:
        return None
    sg = lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0
    b2, y2 = pts[-1]
    logic = _logic(V.s)
    tol = 0.0 if logic else max(float(V.s["tl_touch_sigma"]) * sg, 1e-6 * abs(y2))
    for i in range(len(pts) - 2, -1, -1):
        b1, y1 = pts[i]
        if b1 >= b2 or (y2 - y1) * d <= 0:                                 # DOWN ⇒ p2 खाली (lower high); UP ⇒ p2 वर (higher low)
            continue
        slope = (y2 - y1) / (b2 - b1)

        def line(b, y1=y1, b1=b1, slope=slope):
            return y1 + slope * (b - b1)
        if logic:                                                          # method: two separate reactions, and no candle closes through the
            if not separate(known, b1, b2, kind) or \
                    any((lv.A["close"][j] - line(j)) * (-d) > 0 for j in range(b1 + 1, b2)):   # line between them (a wick = touch / sweep)
                continue
            if broken_by(lv.A, known, kind, line, -d, b2 + 1, t - 1) is not None:   # after p2: close beyond + swing beyond (K6.5);
                continue                                                   # a close that came back = throw-over, the line stands. (Guard: a
                # swing of this kind after p2 is itself the newest pivot ⇒ it becomes p2 and the line is redrawn through it — "same chain")
        else:
            if any((y - line(b)) * (-d) > tol for b, y in pts[i + 1:-1]):  # मधला swing रेघेपलीकडे ⇒ ही जोडी रेघ नाही
                continue
            C = lv.A["close"]
            if any((C[j] - line(j)) * (-d) > 0 for j in range(b2 + 1, t)):  # p2 नंतर (t − 1 पर्यंत) close रेघेपलीकडे ⇒ रेघ तुटली
                continue
        if logic:
            n_t = sum(1 for b, y in pts[i:] if b in (b1, b2) or touches(lv.A, b, line(b), kind))
        else:
            n_t = sum(1 for b, y in pts[i:] if abs(y - line(b)) <= tol)
        return {"p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)], "slope": round(slope, 4), "touches": n_t,
                "value_t": round(line(t), 2), "tol": round(tol, 2)}
    return None


def confluence_areas(V, t, d, cands):
    """Abhi (12 Oct): तिरकी रेघ + horizontal trade-बाजूचा level ⇒ confluence area = दोघांच्या पट्ट्यांचा overlap (रेघेचा पट्टा = t ला
    रेघेची किंमत ± max(σ_1H × tl_touch_sigma, अर्धी किमान level रुंदी); overlap किमान level रुंदीपेक्षा अरुंद ⇒ मध्याभोवती किमान रुंदी).
    cands = ② चे active levels (`Levels.active`, तोच जवळचा-N संच — वेगळी अंतर-मर्यादा नाही); area किंमतीच्या चुकीच्या बाजूला ⇒ नाही. रेघ फक्त t ला माहीत swings वरून (lookahead नाही); स्पर्श < tl_min_touches ⇒
    काहीच नाही. रेघ एकटी area नाही (spec ②: level जन्म a–d; OPEN_QUESTIONS). रिटर्न [area dict] (births + "tl", `tl` = रेघ;
    "tl" grade वाढवत नाही — parent level चा ★ तसाच, confluence फक्त पुरावा-नोंद, OPEN_QUESTIONS D12-6).
    (वरचं = line_rule "sigma". Logic: रेघ t ला area च्या पट्ट्यातून जाते ⇒ तोच area, births + "tl", confluence_line — overlap / नवा
    पट्टा नाही; engine.step2 तो area जागीच बदलतो.)"""
    ln = swing_line(V, t, d)
    if ln is not None and _logic(V.s):                                     # method §3: where a line and an area meet = the strongest
        v = ln["value_t"]                                                  # location — the area itself, labelled (never a new or
        out = []                                                           # narrowed band)
        for x in cands:
            if float(x["lo"]) <= v <= float(x["hi"]):
                out.append({**x, "births": list(x["births"]) + ["tl"], "tl": ln, "confluence_line": True})
        return out
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
        if (d == DOWN and hi < c) or (d == UP and lo > c):                 # चुकीच्या बाजूला (resistance close खाली / support वर) ⇒ नाही
            continue
        dist = 0.0 if lo <= c <= hi else (lo - c if c < lo else c - hi)
        out.append({**x, "id": f"{x['id']}+TL", "lo": round(lo, 2), "hi": round(hi, 2), "births": list(x["births"]) + ["tl"],
                    "dist": round(dist, 2), "above": lo > c, "below": hi < c, "tl": ln, "parent_level": x["id"]})
    return sorted(out, key=lambda a: a["dist"])                           # Abhi's method §4: every area ahead, nearest first
