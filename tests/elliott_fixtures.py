"""Elliott corrective-pattern fixture library (Abhi: TRADE_SESSION_CORRECTION_FIXTURES) — synthetic Daily OHLC.

Every fixture = lead-in (top + LH ⇒ DOWN trend start) → 5-wave DOWN impulse → the corrective shape → continuation (5 waves down beyond
the impulse end). Mirror (UP) = prices reflected (MIRROR − p). Shapes follow the published rules / guidelines (Frost & Prechter,
docs/research/elliott_rules.md); ratios such as 1.618 are only typical shapes here, never engine thresholds.

Units: impulse length I (origin LH → impulse end E). Prices are fixture numbers (no dates — timestamps are synthetic business days).
"""
import numpy as np
import pandas as pd

E = 1000.0                                                                 # DOWN impulse end
I = 280.0                                                                  # impulse length (origin LH = E + I)
MIRROR = 2600.0                                                            # UP mirror: p ⇒ MIRROR − p
WICK = 2.0


def _bars(delta):
    return max(3, int(round(abs(delta) / 12.0)))


def ohlc(points, mirror=False):
    """[(price, bars) | price] ⇒ Daily OHLC; bars None ⇒ length-based. Turning points carry the wick extremes."""
    pts = [p if isinstance(p, tuple) else (p, None) for p in points]
    closes = [pts[0][0]]
    for px, nb in pts[1:]:
        nb = nb or _bars(px - closes[-1])
        closes += list(np.linspace(closes[-1], px, nb + 1)[1:])
    c = np.array(closes, float)
    if mirror:
        c = MIRROR - c
    o = np.r_[c[0], c[:-1]]
    from mtf.adapter import SYN_EPOCH                                      # synthetic sessions (no real calendar dates)
    ts = pd.bdate_range(SYN_EPOCH, periods=len(c))
    from decision3 import daily_swings as DS
    return DS.prepare(pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + WICK, "low": np.minimum(o, c) - WICK,
                                    "close": c}))


# lead-in: rally to a top, pullback, lower high (= impulse origin), then the 5-wave DOWN impulse to E
TOP = E + I + 60.0
LEAD = [(E + 40.0, 0), (TOP, 30), (E + I - 30.0, 8), (E + I, 5)]          # LH = origin (E + I)
IMPULSE = None                                                             # set below (needs build())


def continuation(top):
    """after the correction: 5 waves down from its end, beyond E (5-3-5-3-5)."""
    span = top - (E - 120.0)
    return build(top, [(top - 0.3 * span, "m5"), (top - 0.18 * span, "c3"), (top - 0.8 * span, "m5"), (top - 0.7 * span, "c3"),
                       (E - 120.0, "m5")]) + [E - 105.0]


def _shape(corr, cont=True):
    """corr = correction waypoints after E. Returns (points, info) — info: correction extreme ("top"), correction end ("end" = its
    last waypoint; triangle e / truncated or running c lie below the top) and the lead-in length."""
    pts = LEAD + IMPULSE + corr
    vals = [p[0] if isinstance(p, tuple) else p for p in corr]
    end = vals[-1]
    return pts + (continuation(end) if cont else []), {"top": max(vals), "end": end, "n_lead": len(LEAD) + len(IMPULSE)}


A = 0.40 * I                                                               # typical wave a of a correction


def m5(s, e):
    """motive wave s ⇒ e in 5 sub-waves (1-2-3-4-5: 2 < 100% of 1, 3 longest, 4 clear of 1)."""
    d = e - s
    return [s + 0.30 * d, s + 0.18 * d, s + 0.75 * d, s + 0.60 * d, e]


def c3(s, e):
    """corrective wave s ⇒ e in 3 sub-waves (a-b-c)."""
    d = e - s
    return [s + 0.62 * d, s + 0.38 * d, e]


def build(start, waves):
    """[(end, "m5" | "c3" | "1")] ⇒ waypoints (sub-waves drawn as Elliott subdivisions)."""
    out, cur = [], start
    for end, k in waves:
        if k == "ed":                                                      # ending diagonal: contracting wedge, 3-3-3-3-3, 4 overlaps 1
            d, w = end - cur, []
            for x in (0.45, 0.22, 0.72, 0.52, 1.0):
                w += c3(w[-1] if w else cur, cur + x * d)
            out += w
        else:
            out += m5(cur, end) if k == "m5" else (c3(cur, end) if k == "c3" else [end])
        cur = end
    return out


def zz(a_end, b_end, c_end):
    return [(a_end, "m5"), (b_end, "c3"), (c_end, "m5")]                   # zigzag 5-3-5


def fl(a_end, b_end, c_end):
    return [(a_end, "c3"), (b_end, "c3"), (c_end, "m5")]                   # flat 3-3-5


def tri(pts):
    return [(p, "c3") for p in pts]                                        # triangle 3-3-3-3-3


SHAPES = {
    "zigzag_c_eq_a": zz(E + A, E + 0.45 * A, E + 1.45 * A),
    "zigzag_c_extended": zz(E + A, E + 0.5 * A, E + 0.5 * A + 1.618 * A),
    "zigzag_c_truncated": zz(E + A, E + 0.45 * A, E + 0.92 * A),
    "double_zigzag": zz(E + 0.8 * A, E + 0.5 * A, E + 1.3 * A) + [(E + 0.95 * A, "c3")] + zz(E + 1.45 * A, E + 1.2 * A, E + 1.75 * A),
    "flat_regular": fl(E + A, E + 0.03 * A, E + 1.02 * A),
    "flat_expanded": fl(E + A, E - 0.15 * A, E - 0.15 * A + 1.618 * A),   # b below E (new low), c ≈ 1.618 a
    "flat_running": fl(E + A, E - 0.1 * A, E + 0.8 * A),
    "triangle_contracting": tri([E + A, E + 0.3 * A, E + 0.85 * A, E + 0.42 * A, E + 0.74 * A]),
    "triangle_expanding": tri([E + 0.45 * A, E + 0.2 * A, E + 0.7 * A, E - 0.05 * A, E + 0.95 * A]),
    "triangle_barrier": tri([E + A, E + 0.35 * A, E + 0.88 * A, E + 0.35 * A, E + 0.76 * A]),
    "zigzag_b_triangle": [(E + A, "m5")] + tri([E + 0.6 * A, E + 0.9 * A, E + 0.66 * A, E + 0.84 * A, E + 0.7 * A]) + [(E + 1.7 * A, "m5")],
    "double_three": fl(E + A, E + 0.05 * A, E + A) + [(E + 0.7 * A, "c3")] + zz(E + 1.1 * A, E + 0.9 * A, E + 1.4 * A),
    "triple_three": zz(E + 0.6 * A, E + 0.35 * A, E + A) + [(E + 0.6 * A, "c3")]                      # W zigzag, X
                    + fl(E + 0.95 * A, E + 0.6 * A, E + 1.02 * A) + [(E + 0.7 * A, "c3")]                # Y flat, X
                    + tri([E + 0.98 * A, E + 0.55 * A, E + 0.9 * A, E + 0.62 * A, E + 0.82 * A]),       # Z triangle (last) — sideways
    "b_looks_impulsive": [(E + A, "m5"), (E + 0.1 * A, "m5"), (E + 1.15 * A, "m5")],                    # b in 5 waves, holds E
    "long_in_time": zz(E + A, E + 0.4 * A, E + 1.4 * A),
    "very_deep_holds_origin": zz(E + 0.55 * I, E + 0.3 * I, E + 0.88 * I),
}
SLOW = {"long_in_time": 3}                                                  # bars multiplier (correction longer in time than the impulse)
CORRECTIONS = {k: build(E, v) for k, v in SHAPES.items()}
FAMILY = {"zigzag_c_eq_a": "zigzag", "zigzag_c_extended": "zigzag", "zigzag_c_truncated": "zigzag", "double_zigzag": "combination",
          "flat_regular": "flat", "flat_expanded": "flat", "flat_running": "flat", "triangle_contracting": "triangle",
          "triangle_expanding": "triangle", "triangle_barrier": "triangle", "zigzag_b_triangle": "zigzag",
          "double_three": "combination", "triple_three": "combination", "b_looks_impulsive": "zigzag", "long_in_time": "zigzag",
          "very_deep_holds_origin": "zigzag"}


IMPULSE = build(E + I, [(E + I - 70, "m5"), (E + I - 40, "c3"), (E + 90, "m5"), (E + 130, "c3"), (E, "m5")])   # 5-3-5-3-5 DOWN


def correction_fixture(name, mirror=False):
    corr = CORRECTIONS[name]
    k = SLOW.get(name)
    vals = list(corr)
    if k:
        prev = E
        corr = []
        for v in vals:
            corr.append((v, _bars(v - prev) * k))
            prev = v
    pts, info = _shape(corr)
    d = ohlc(pts, mirror)
    info.update(name=name, family=FAMILY[name], dir=1 if mirror else -1)
    return d, info


# negative controls: the counter-move is itself a 5-wave impulse (must flip)
J = 0.9 * I                                                                 # impulse up length (stays below the parent) unless noted


def _imp(ends, kinds=("m5", "c3", "m5", "c3", "m5")):
    return build(E, list(zip(ends, kinds)))


IMPULSES = {
    "impulse_below_origin": _imp([E + 0.25 * J, E + 0.12 * J, E + 0.7 * J, E + 0.55 * J, E + J]),
    "impulse_beyond_origin": _imp([E + 0.3 * I, E + 0.15 * I, E + 0.9 * I, E + 0.7 * I, E + 1.3 * I]),
    "impulse_extended_third": _imp([E + 0.18 * J, E + 0.1 * J, E + 0.8 * J, E + 0.7 * J, E + J]),
    "impulse_extended_fifth": _imp([E + 0.22 * J, E + 0.12 * J, E + 0.45 * J, E + 0.36 * J, E + J]),
    # contracting wedges (3 < 1, 4 < 2, 5 < 3; 4 overlaps 1): leading diagonal = the counter-move's wave 1 (5-3-5-3-5); ending
    # diagonal only in wave 5 / C position ⇒ an impulse whose wave 5 is a 3-3-3-3-3 wedge
    "leading_diagonal": _imp([E + 0.40 * J, E + 0.18 * J, E + 0.53 * J, E + 0.33 * J, E + 0.63 * J]),
    "ending_diagonal": _imp([E + 0.25 * J, E + 0.12 * J, E + 0.7 * J, E + 0.55 * J, E + J], ("m5", "c3", "m5", "c3", "ed")),   # wave 5
}


def impulse_control(name, mirror=False):
    up = IMPULSES[name]
    top = max(up)
    span = top - E                                                         # after the 5 waves: (2) pullback, then (3) starts —
    end = top + 0.15 * span if top > E + I else min(top + 0.15 * span, E + I - 20.0)   # below-origin controls never close beyond
    pts = LEAD + IMPULSE + up + c3(top, top - 0.4 * span) + [end]          # the origin ⇒ only the 5-wave rule can flip them
    d = ohlc(pts, mirror)
    return d, {"name": name, "dir": 1 if mirror else -1, "top": top, "beyond_origin": top > E + I}


# Q49 (Abhi): 5-wave पहिला पाय — wave A की wave 1? `very_deep_holds_origin` (A 5-wave, B, C 5-wave पलीकडे, मग DOWN continuation;
# A wave (4) high = leg origin ओलांडतो पण impulse पूर्ण 5-wave ⇒ (a) चा origin = impulse सुरुवात, टिकलेली)
# हाच डीप zigzag. त्याचा जोडीदार: तसाच "1" / "2" / "3", पण पुढे "4" ("1" च्या टोकाला न ओलांडता) आणि "5" — counter-move स्वतःची
# same-degree 5-wave रचना पूर्ण करते ("1" 5, "2" 3, "3" पलीकडे 5) ⇒ (b) ⇒ flip. Parent origin (E + I) वर कधीच close नाही ⇒ (a) नाही.
Q49_123 = build(E, [(E + 0.55 * I, "m5"), (E + 0.3 * I, "c3"), (E + 0.88 * I, "m5"), (E + 0.7 * I, "c3"), (E + 0.98 * I, "m5")])


def q49_complete_five(mirror=False):
    """Q49 negative control (review 🟡3: नाव "complete five" — flip "3" च्या शेवटी नाही, counter-move चा स्वतःचा "5" चालू असताना):
    counter-move = "1"(5) – "2"(3) – "3"(5, "1" पलीकडे) – "4"(3) – "5"(5), parent origin खालीच. "3" पर्यंत हा deep zigzag सारखाच
    (A-B-C) ⇒ तिथे wave A; (b) फक्त "4" + "5" ने संपूर्ण counter-move 5-wave वाचल्यावर."""
    d = ohlc(LEAD + IMPULSE + Q49_123 + c3(E + 0.98 * I, E + 0.8 * I) + [E + 0.95 * I], mirror)
    return d, {"name": "q49_complete_five", "dir": 1 if mirror else -1, "a_end": E + 0.55 * I, "parent": E + I,
               "end3": E + 0.88 * I, "end4": E + 0.7 * I}


def q49_lower_degree_a(mirror=False):
    """Review 🟡4: impulse (1)-(2)-(3), (4) = contracting triangle (Rule 4: origin = e), (5) = continuation; मग खालच्या degree चा
    (Q22) 5-wave A impulse origin (e) पलीकडे close करतो, parent टिकतो ⇒ wave A (why मध्ये "origin टिकला" असं नाही)."""
    e2 = E - 120.0
    w4 = CORRECTIONS["triangle_contracting"]
    pts = LEAD + build(E + I, [(E + I - 70, "m5"), (E + I - 40, "c3"), (E, "m5")]) + w4 + continuation(w4[-1])[:-1] \
        + build(e2, zz(E + 100, E + 10, E + 190)) + build(E + 190, [(e2 - 60, "m5")]) + [e2 - 45]
    return ohlc(pts, mirror), {"name": "q49_lower_degree_a", "dir": 1 if mirror else -1, "end5": e2, "e": w4[-1]}


def q49_beyond_impulse_origin(mirror=False):
    """Q49 (a) — ABC_FIX आकार (Abhi: BANKNIFTY Feb top ⇒ Mar low = DOWN impulse): trend चा चालू leg एखाद्या पूर्ण 5-wave चा wave 5
    नाही (फक्त (1) – (2) – (3)); counter-move 5-wave (सरळ उप-पाय ⇒ (b) नाही) त्या impulse leg च्या origin पलीकडे close करतो, trend
    सुरुवात (parent) टिकते ⇒ wave 1 ⇒ flip. मग 3-wave pullback आणि नवा टोक."""
    org = E + 0.6 * I                                                      # चालू impulse leg चा origin ((2) टोक)
    trend = build(E + I, [(E + 0.45 * I, "m5"), (org, "c3"), (E, "m5")])
    up = build(E, [(E + 0.75 * I, "m5")])                                  # 5-wave, origin पलीकडे, parent (E + I) खाली
    pts = LEAD + trend + up + c3(E + 0.75 * I, E + 0.5 * I) + [E + 0.9 * I]
    return ohlc(pts, mirror), {"name": "q49_beyond_impulse_origin", "dir": 1 if mirror else -1, "origin": org, "parent": E + I,
                               "top": E + 0.75 * I}


# acceptance set (Abhi's marked counts, structural)
def acceptance_banknifty(mirror=False):
    """window top → sharp fall (slow start, then wide directional bars) → a up, b down holding above the low, c up beyond a ending
    inside the sharp-fall zone (the last swing before the run of wide-range bars, i.e. the slow-start swing just above sharp_point
    from which the fall accelerated — ABC_FIX rule 2) → new decline. Engine: DOWN throughout; a-b-c labelled; sharp-fall band; origin at c (after confirm)."""
    top = 1600.0
    slow = [(1580.0, 3), (1590.0, 2), (1560.0, 3), (1570.0, 2), (1545.0, 3)]               # slow start (narrow bars)
    sharp_point = 1545.0
    fall = [(1300.0, 5), (1360.0, 4), (1150.0, 5), (1220.0, 4), (1080.0, 5)]                # wide-range directional run (its 2 / 4
                                                                                           # are one degree above a's sub-waves)
    a, b = 1380.0, 1220.0
    c = 1567.0                                                                             # c > a, ends inside the sharp-fall zone
    corr = build(1080.0, zz(a, b, c))                                              # 5-3-5
    after = [(1420.0, 6), (1460.0, 3), (1250.0, 7), (1290.0, 3), (1150.0, 6), (1170.0, 3)]
    lead = [(1350.0, 0), (top, 30), (1520.0, 8), (1585.0, 5)]
    d = ohlc(lead + slow + fall + corr + after, mirror)
    return d, {"top": top, "sharp_point": sharp_point, "a": a, "b": b, "c": c, "dir": 1 if mirror else -1}



def acceptance_banknifty_two_lows(mirror=False):
    """Q55 (Abhi): ABC_FIX §6 fixture चा भाऊ — window top → slow topping (a swing low at sharp_point) → sharp fall: a run of wide-range directional bars breaks that swing
    low first (the sharp-fall point, Q55) and later the lead-in's swing low (two lows broken — the first one is the point) → a up,
    b down holding above the low, c up beyond a ending inside the sharp-fall zone → new decline. Engine: DOWN throughout; a-b-c
    labelled; sharp-fall band at sharp_point; origin at c (after confirm)."""
    top = 1600.0
    slow = [(1580.0, 3), (1590.0, 2), (1562.0, 3), (1572.0, 2)]                            # slow topping, narrow bars
    sharp_point = 1562.0                                                                   # swing low the run breaks first
    fall = [(1300.0, 5), (1360.0, 4), (1150.0, 5), (1220.0, 4), (1080.0, 5)]                # wide-range directional run (its 2 / 4
                                                                                           # are one degree above a's sub-waves)
    a, b = 1380.0, 1220.0
    c = 1567.0                                                                             # c > a, ends inside the sharp-fall zone
    corr = build(1080.0, zz(a, b, c))                                                      # 5-3-5
    after = [(1420.0, 6), (1460.0, 3), (1250.0, 7), (1290.0, 3), (1150.0, 6), (1170.0, 3)]
    lead = [(1350.0, 0), (top, 30), (1520.0, 8), (1585.0, 5)]                              # 1520: second swing low the run breaks
    d = ohlc(lead + slow + fall + corr + after, mirror)
    return d, {"top": top, "sharp_point": sharp_point, "second_low": 1520.0, "a": a, "b": b, "c": c, "dir": 1 if mirror else -1}


def acceptance_nifty():
    """(B) top → C decline: (1)-(3) with minor bounces, a large (4) rally (breaks the minor origin, not the C start), (5) with three
    small bounces into the (A) low zone (same as tests/test_decision3_daily_review.py)."""
    pts = [(1000, 0), (1400, 20), (1000, 20), (1350, 20), (1250, 6), (1300, 4), (1150, 8), (1170, 3), (1120, 4), (1160, 4), (1080, 6),
           (1250, 12), (1215, 4), (1235, 3), (1190, 5), (1200, 3), (1120, 6), (1135, 3), (1060, 6), (1075, 3), (996, 7), (1004, 2)]
    return ohlc(pts), {"top4": 1250.0, "parent": 1300.0}


# Trend first (Abhi, setups audit — docs/reports/setups_prA_v1_audit.md): a same-degree counter-move that climbs in a staircase of
# higher lows + higher highs (each step 5 up / 3 down) but stays below the protected origin — the trend label stays DOWN (Q15: no close
# beyond the origin), yet the Daily structure since the impulse end is UP ⇒ no bear call. `breakdown` adds the DOWN continuation
# (5 waves to a new low) ⇒ the counter structure is undone and bear calls are allowed again.
STAIR = build(E, [(E + 40, "m5"), (E + 22, "c3"), (E + 70, "m5"), (E + 52, "c3"), (E + 100, "m5"), (E + 82, "c3"), (E + 122, "m5")])


def staircase_dip_back(mirror=False):
    """PR #305 review: the counter structure turned UP (HL + close above the swing high before it), then price dips back BELOW that
    swing high while the HL stays intact (no wick through it) ⇒ the Daily structure is still UP (Dow: until the HL breaks)."""
    up = build(E, [(E + 40, "m5"), (E + 22, "c3"), (E + 70, "m5"), (E + 52, "c3"), (E + 100, "m5")])
    return ohlc(LEAD + IMPULSE + up + c3(E + 100, E + 12), mirror), {"name": "staircase_dip_back", "dir": 1 if mirror else -1}


def staircase_below_origin(mirror=False, breakdown=False):
    pts = LEAD + IMPULSE + STAIR + (continuation(STAIR[-1]) if breakdown else [])
    return ohlc(pts, mirror), {"name": "staircase_below_origin", "dir": 1 if mirror else -1, "top": max(STAIR), "origin4": E + 130.0,
                               "parent": E + I}
