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
