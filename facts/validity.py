"""facts/validity.py — the ONE trendline check (KB K6) and the ONE horizontal area / band check (KB K4 + K5) that every chart uses.

Design: docs/design/CHART_READER_AGENT.md §3 (facts layer) and §10 (TA1–TA4, Abhi). The owners call these checks:
trendlines ⇒ `trendlines2.two_touch.find_lines`, areas ⇒ `decision3.levels.find_bands`. Every function returns facts with evidence
(anchor bars / times / prices, touch lists, break bars, reasons) — never a score, vote or grade. Pure: no I/O, no AI, no broker.

No look-ahead: every function takes `t` (the decision bar, closed) and reads only bars ≤ t. A pivot counts only once it is confirmed
(pivot bar + k ≤ t); a break by acceptance needs its second close ≤ t. Truncating the data after t never changes a result.

LINE (K6.1, TA3 corrected): a line is drawn from 2 wick-anchored touches (confirmed pivots) spaced ≥ `min_spacing` bars; no close beyond
the line between the anchors by > `between_close_mr` MR; |slope| ≤ `max_slope_mr` MR / bar; not really broken after anchor 2 (K5 real break,
K6.5). ≥ `established_touches` spaced touches = "established" (evidence +, not a different rule). The projected next touch
(line value ± `touch_mr` MR at future bars) is returned as a candidate area (the trade location; entry still needs handover + commitment).
The "touch in the last 2 sessions" rule (audit K6.4 a) is NOT applied: open question TA5.

BAND (K4 horizontal S/R, TA3b + TA4): a band is low–high (never a single price) and ≤ `band_max_mr` MR wide; it needs 2 real reaction
touches (confirmed swing highs for a resistance / supply band, swing lows for a support / demand band, extreme within the band ± `band_tol_mr`
MR), spaced ≥ `min_spacing` bars, with price fully leaving the band between them. A confirmed break (K5: close beyond the far edge by
`break_buf_mr` MR + acceptance or displacement) flips the role; touches are then counted again on the new side. A band whose last event
is a break (< 2 touches on the new side) is "broken" (hidden on charts except the most recent broken one). K5 magnet (≥ `magnet_crossings`
close-crossings of the band mid in the decision session) ⇒ no-trade level ("magnet").

CONFLUENCE (K4, K6.4): a valid band and a valid line of the same role meet within `confluence_mr` MR, now or at a projected bar.

MR = median(high − low) of the last `mr_bars` closed bars up to t (KB definition).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

RES, SUP = "resistance", "support"

DEFAULTS = {
    "mr_bars": 20,                 # KB "MR" definition (last 20 closed candles)
    "pivot_k": 2,                  # K6.1 confirmed pivots, k = 2–3
    "touch_mr": 0.2,               # K6.1 touch = pivot extreme within ±0.2 MR of the line
    "between_close_mr": 0.3,       # K6.1 no close beyond the line between the anchors by > 0.3 MR
    "min_spacing": 6,              # TA2 / K6.1 / K4: touches spaced ≥ 6 bars (setting)
    "max_slope_mr": 0.5,           # K6.1 slope > 0.5 MR / bar ⇒ reject
    "established_touches": 3,      # K6.1 ≥ 3 touches = "established" (evidence +)
    "trend_direction_only": True,  # K6 definition: a trendline joins highs in a downtrend (falling) / lows in an uptrend (rising)
    "break_buf_mr": 0.25,          # K5 real break: close beyond by 0.25 MR ...
    "disp_break_mr": 1.2,          # K5 (a) displacement: break bar range ≥ 1.2 MR ...
    "disp_outer": 0.30,            # K5 (a) ... closing in the outer 30 % of its range; (b) acceptance = next close also beyond
    "band_tol_mr": 0.2,            # K4 band tolerance in MR units (same as the K6.1 touch)
    "band_max_mr": 1.5,            # K4 zone height ≤ 1.5 MR
    "magnet_crossings": 4,         # K5 magnet: ≥ 4 close-crossings in the session ⇒ no-trade level
    "magnet_invalidates": True,    # K5 says "no-trade level" ⇒ hidden from charts (kept as in the audit's 2-touch mode)
    "confluence_mr": 0.5,          # K6.4 line and horizontal meet within ≤ 0.5 MR ⇒ "confluence"
    "projection_bars": 25,         # projected 3rd-touch zone: next N bars (one 15M session = 25 bars)
    "lookback_sessions": 8,        # finders: design §5 (15M ≈ 8 trading days; callers pass 15 for 1H)
    "max_lines": 2,                # TA1 display: at most 2 valid lines per timeframe
    "max_bands_per_side": 3,       # TA4 display: at most 3 bands above and 3 below price per timeframe
}

REGISTER = {
    "mr_bars": "KB 'MR' definition: median(H − L) of the last 20 closed candles",
    "pivot_k": "K6.1 confirmed pivots (k = 2–3)",
    "touch_mr": "K6.1 touch = pivot extreme within ±0.2 MR",
    "between_close_mr": "K6.1 no close beyond the line between the anchors by > 0.3 MR",
    "min_spacing": "TA2 (Abhi, design §10) touch spacing default 6 bars; K6.1 / K4",
    "max_slope_mr": "K6.1 slope > 0.5 MR per bar ⇒ reject",
    "established_touches": "K6.1 / TA3 ≥ 3 touches = established (evidence +, not a different rule)",
    "trend_direction_only": "K6 'what': trendline = lows in an uptrend, highs in a downtrend; a rising line through highs (falling "
                            "through lows) is a channel edge (K6.2), not a trendline ⇒ reason 'against_trend_direction'",
    "break_buf_mr / disp_break_mr / disp_outer": "K5 real break (elliott/breaks.py definition): 0.25 MR + displacement (≥ 1.2 MR, outer "
                                                 "30 %) or acceptance (next close beyond)",
    "band_tol_mr": "K4 band tolerance in MR units (TA3b)",
    "band_max_mr": "K4 zone height ≤ 1.5 MR",
    "magnet_crossings / magnet_invalidates": "K5 magnet: ≥ 4 close-crossings in the day ⇒ no-trade level",
    "confluence_mr": "K6.4 horizontal and sloping meet within ≤ 0.5 MR ⇒ 'confluence' (K4)",
    "projection_bars": "TA3: projected 3rd-touch zone at future bars (one 15M session)",
    "lookback_sessions": "design §5 inputs: 15M ≈ 8 trading days, 1H ≈ 15, 5M = current + previous session, Daily ≈ 6 months "
                         "(TF_LOOKBACK_SESSIONS / lookback(tf))",
    "max_lines": "TA1: at most 2 valid lines per timeframe",
    "max_bands_per_side": "TA4: at most 3 bands above and 3 below price per timeframe",
}


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update({k: v for k, v in (overrides or {}).items() if v is not None})
    return s


# ------------------------------------------------------------------------------------------------ bars
@dataclass
class Bars:
    ts: pd.Series
    O: np.ndarray
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray
    day: pd.Series

    @property
    def R(self):
        return self.H - self.L

    def __len__(self):
        return len(self.C)


def bars_of(df):
    """DataFrame (timestamp, open, high, low, close) ⇒ Bars. A Bars is returned unchanged."""
    if isinstance(df, Bars):
        return df
    d = df.reset_index(drop=True)
    ts = pd.to_datetime(d["timestamp"]).reset_index(drop=True)
    return Bars(ts, *(d[k].to_numpy(float) for k in ("open", "high", "low", "close")), ts.dt.normalize())


def mr_at(B, t, s=None):
    s = s or DEFAULTS
    r = B.H[max(0, t - int(s["mr_bars"]) + 1):t + 1] - B.L[max(0, t - int(s["mr_bars"]) + 1):t + 1]
    return float(np.median(r)) if len(r) else float("nan")


def session_start(B, t, sessions):
    """First bar of the session `sessions − 1` sessions before t's session (0 if the data is shorter)."""
    days = B.day.iloc[:t + 1]
    uniq = days.drop_duplicates()
    if len(uniq) <= sessions:
        return 0
    return int(uniq.index[len(uniq) - sessions])


def bar_end(B, t):
    """End of bar t = its start + the frame's usual bar length (the most common gap between consecutive bars)."""
    d = B.ts.diff().dropna()
    d = d[d > pd.Timedelta(0)]
    step = d.mode().iloc[0] if len(d) else pd.Timedelta(microseconds=1)
    return B.ts.iloc[t] + step


TF_LOOKBACK_SESSIONS = {"5M": 2, "15M": 8, "1H": 15, "D": 126}       # design §5 inputs (5M current + previous session; Daily ≈ 6 months)


def lookback(tf, s=None):
    """Settings with the design §5 lookback for a timeframe label ("5M", "15M", "1H", "D")."""
    return load({**(s or {}), "lookback_sessions": TF_LOOKBACK_SESSIONS.get(tf, DEFAULTS["lookback_sessions"])})


def pivots(B, t, kind, s=None, start=0):
    """k-fractal pivots confirmed by t (pivot bar + k ≤ t): bars i in [start, t − k] whose high (H) / low (L) is the extreme of i ± k."""
    s = s or DEFAULTS
    k = int(s["pivot_k"])
    y = B.H if kind == "H" else B.L
    out = []
    for i in range(max(k, start), t - k + 1):
        w = y[i - k:i + k + 1]
        if (kind == "H" and y[i] == w.max()) or (kind == "L" and y[i] == w.min()):
            out.append(i)
    return out


def _real_break(B, t, i, level, up, mr, s):
    """K5 real break at bar i through `level` (up ⇒ close above level + buf). `level` = a price (horizontal band edge) or a function
    bar ⇒ price (a sloped line: the acceptance close i + 1 is compared with the line's value at i + 1). Uses bars ≤ t only."""
    lv = level if callable(level) else (lambda _i: level)
    buf = float(s["break_buf_mr"]) * mr
    sg = 1 if up else -1
    if sg * (B.C[i] - lv(i)) <= buf:
        return False
    if i + 1 <= t and sg * (B.C[i + 1] - lv(i + 1)) > buf:
        return True                                                         # (b) acceptance
    rng = B.H[i] - B.L[i]
    pos = (B.C[i] - B.L[i]) / rng if rng > 0 else 0.5
    return bool(rng >= float(s["disp_break_mr"]) * mr and (pos >= 1 - float(s["disp_outer"]) if up else pos <= float(s["disp_outer"])))


def _pt(B, i, price):
    return {"bar": int(i), "ts": str(B.ts.iloc[i]), "price": round(float(price), 2)}


def spaced_count(bars, gap):
    n, last = 0, None
    for b in sorted(bars):
        if last is None or b - last >= gap:
            n, last = n + 1, b
    return n


# ------------------------------------------------------------------------------------------------ LINE (K6)
def line_value(line, bar):
    return line["anchor1"]["price"] + line["slope_per_bar"] * (bar - line["anchor1"]["bar"])


def check_line(df, t, a1, a2, side, s=None):
    """The shared K6 line check. a1 / a2 = (bar, price) wick anchors, a1 < a2; side RES (anchors on highs) or SUP (lows).
    Returns facts: anchors, slope, MR, touches (bar, time, price, distance in MR), spaced touch count, established, break,
    valid + reasons, the bar from which the line exists (anchor 2 confirmed) and the projected next-touch zone."""
    s = load(s)
    B = bars_of(df)
    b1, y1 = int(a1[0]), float(a1[1])
    b2, y2 = int(a2[0]), float(a2[1])
    mr = mr_at(B, t, s)
    m = (y2 - y1) / (b2 - b1) if b2 != b1 else 0.0
    sg = 1 if side == RES else -1                                           # +1 ⇒ "beyond" = above
    wick = B.H if side == RES else B.L
    k = int(s["pivot_k"])
    tol = float(s["touch_mr"]) * mr
    reasons = []

    def v(i):
        return y1 + m * (i - b1)
    if b2 - b1 < int(s["min_spacing"]):
        reasons.append("anchors_spacing_lt_min")
    if b2 + k > t:
        reasons.append("anchor2_not_confirmed")
    anc_dev = max(abs(y1 - wick[b1]), abs(y2 - wick[b2])) / mr
    if anc_dev > float(s["touch_mr"]):
        reasons.append("anchor_not_on_wick")
    between = [sg * (B.C[i] - v(i)) / mr for i in range(b1 + 1, b2)]
    mx_between = max(between) if between else 0.0
    if mx_between > float(s["between_close_mr"]):
        reasons.append("close_through_between_anchors")
    slope_mr = abs(m) / mr
    if slope_mr > float(s["max_slope_mr"]):
        reasons.append("too_steep")
    if s["trend_direction_only"] and sg * m > 0:
        reasons.append("against_trend_direction")
    brk = None
    for i in range(b2 + 1, t + 1):
        if _real_break(B, t, i, v, sg > 0, mr, s):
            brk = i
            break
    if brk is not None:
        reasons.append("broken")
    kind = "H" if side == RES else "L"
    touch = {i for i in pivots(B, t, kind, s, start=b1) if abs(wick[i] - v(i)) <= tol}
    if anc_dev <= float(s["touch_mr"]):
        touch |= {b1, b2}
    touch = sorted(i for i in touch if brk is None or i < brk)
    n_sp = spaced_count(touch, int(s["min_spacing"]))
    if n_sp < 2 and "anchors_spacing_lt_min" not in reasons:
        reasons.append("touches_lt2_spaced")
    valid = not reasons
    line = {"kind": "line", "side": side, "anchor1": _pt(B, b1, y1), "anchor2": _pt(B, b2, y2), "slope_per_bar": round(m, 4),
            "slope_mr_per_bar": round(slope_mr, 3), "mr": round(mr, 2), "asof": _pt(B, t, B.C[t]),
            "valid_from": str(B.ts.iloc[b2 + k]) if b2 + k <= t else None,
            "touches": [{**_pt(B, i, wick[i]), "dev_mr": round(float((wick[i] - v(i)) / mr), 3)} for i in touch],
            "touch_count": n_sp, "established": bool(valid and n_sp >= int(s["established_touches"])),
            "anchor_dev_mr": round(anc_dev, 3), "max_close_beyond_between_mr": round(mx_between, 3),
            "broken": brk is not None, "break": _pt(B, brk, B.C[brk]) if brk is not None else None,
            "value_at_t": round(v(t), 2), "valid": valid, "reasons": reasons}
    line["projected_zone"] = projected_zone(line, t, s) if valid else None
    return line


def projected_zone(line, t, s=None, bars=None):
    """TA3: the projected next (3rd) touch = line value ± touch_mr MR at the next `bars` bars after t — a candidate area (trade
    location), not an entry. Offsets are bar counts after t on the same timeframe (the caller maps them to times)."""
    s = load(s)
    n = int(bars or s["projection_bars"])
    tol = float(s["touch_mr"]) * line["mr"]
    path = []
    for o in range(1, n + 1):
        y = line_value(line, t + o)
        path.append({"offset": o, "mid": round(y, 2), "lo": round(y - tol, 2), "hi": round(y + tol, 2)})
    return {"kind": "projected_touch", "role": line["side"], "from_bar": int(t), "tol": round(tol, 2), "next": path[0] if path else None,
            "path": path, "touch_number": line["touch_count"] + 1}


def candidate_lines(df, t, side, s=None, start=None):
    """All 2-touch lines from pairs of confirmed wick pivots in [start, t] (anchors = the first two spaced touches of the line: a pair
    whose line has an earlier spaced touch between its anchors is the same line drawn later, so it is skipped). Each entry =
    check_line facts (valid or not)."""
    s = load(s)
    B = bars_of(df)
    st = session_start(B, t, int(s["lookback_sessions"])) if start is None else start
    kind = "H" if side == RES else "L"
    y = B.H if side == RES else B.L
    piv = pivots(B, t, kind, s, start=st)
    mr = mr_at(B, t, s)
    tol = float(s["touch_mr"]) * mr
    gap = int(s["min_spacing"])
    anchors = reaction_extremes(piv, y, gap, kind)
    out = []
    for a, i in enumerate(anchors):
        for j in anchors[a + 1:]:
            if j - i < gap:
                continue
            m = (y[j] - y[i]) / (j - i)
            if any(abs(y[p] - (y[i] + m * (p - i))) <= tol and p - i >= gap and j - p >= gap for p in anchors if i < p < j):
                continue                                                    # an earlier spaced 2nd touch exists ⇒ same line, drawn from it
            out.append(check_line(B, t, (i, y[i]), (j, y[j]), side, s))
    return out


def reaction_extremes(piv, y, gap, kind):
    """One anchor per reaction: pivots closer than `gap` bars are the same touch (K6.1 spacing), and its anchor is the extreme wick
    (highest high / lowest low) — so the line is drawn over the wicks, not through them."""
    sg = 1 if kind == "H" else -1
    return [p for p in piv if not any(abs(q - p) < gap and (sg * (y[q] - y[p]) > 0 or (y[q] == y[p] and q < p)) for q in piv if q != p)]


def same_line(a, b, mr, tol_mr):
    """Two lines (same side) are one line if both anchors of one lie within the touch tolerance of the other."""
    tol = tol_mr * mr

    def on(x, y):
        return all(abs(line_value(x, p["bar"]) - p["price"]) <= tol for p in (y["anchor1"], y["anchor2"]))
    return a["side"] == b["side"] and (on(a, b) or on(b, a))


def rank_line(x):
    """TA1 display order (documented choice): more spaced touches first; then the more recent last touch; then the longer line."""
    last = x["touches"][-1]["bar"] if x["touches"] else x["anchor2"]["bar"]
    return (-x["touch_count"], -last, x["anchor1"]["bar"])


def dedupe_lines(lines, s=None):
    s = load(s)
    keep = []
    for x in sorted(lines, key=rank_line):
        if not any(same_line(x, k, x["mr"], float(s["touch_mr"])) for k in keep):
            keep.append(x)
    return keep


def select_lines(lines, s=None, debug=False):
    """TA1: the lines a chart shows — valid only (invalid ones only when debug), at most `max_lines`, ranked by `rank_line`."""
    s = load(s)
    ok = dedupe_lines([x for x in lines if x["valid"]], s)
    shown = ok[:int(s["max_lines"])]
    if debug:
        return shown + [x for x in lines if not x["valid"]]
    return shown


# ------------------------------------------------------------------------------------------------ BAND (K4 + K5)
def check_band(df, t, lo, hi, s=None, start=None, magnet_df=None):
    """The shared K4 band check for [lo, hi] at decision bar t (bars [start, t] only; start None ⇒ the same `lookback_sessions` window
    as the finders). magnet_df: optional finer frame (e.g. 15M) whose closes in t's session, up to the end of bar t, are used for the K5
    magnet count (default: this frame); later rows are ignored. Returns facts (touches, breaks, role, flags, reasons)."""
    s = load(s)
    B = bars_of(df)
    if start is None:
        start = session_start(B, t, int(s["lookback_sessions"]))
    lo, hi = float(lo), float(hi)
    mr = mr_at(B, t, s)
    tol = float(s["band_tol_mr"]) * mr
    buf = float(s["break_buf_mr"]) * mr
    gap = int(s["min_spacing"])
    reasons = []
    w = hi - lo
    if w <= 0:
        reasons.append("not_a_band")
    elif w > float(s["band_max_mr"]) * mr:
        reasons.append("too_wide")
    ph = set(pivots(B, t, "H", s, start=start))
    pl = set(pivots(B, t, "L", s, start=start))
    role, cur, older, breaks = None, [], [], []

    def left_between(a, b):
        return any(B.L[x] > hi or B.H[x] < lo for x in range(a + 1, b))

    def add(i, price, kind):
        if not cur or (i - cur[-1]["bar"] >= gap and left_between(cur[-1]["bar"], i)):
            cur.append({**_pt(B, i, price), "kind": kind})
    for i in range(start, t + 1):
        if i in ph and lo - tol <= B.H[i] <= hi + tol and role in (None, RES) and B.C[i] <= hi + buf:
            role = RES
            add(i, B.H[i], "swing high")
        elif i in pl and lo - tol <= B.L[i] <= hi + tol and role in (None, SUP) and B.C[i] >= lo - buf:
            role = SUP
            add(i, B.L[i], "swing low")
        if role == RES and _real_break(B, t, i, hi, True, mr, s):
            breaks.append({**_pt(B, i, B.C[i]), "dir": "up", "new_role": SUP})
            older.append(cur)
            role, cur = SUP, []
        elif role == SUP and _real_break(B, t, i, lo, False, mr, s):
            breaks.append({**_pt(B, i, B.C[i]), "dir": "down", "new_role": RES})
            older.append(cur)
            role, cur = RES, []
    broken = bool(breaks) and len(cur) < 2
    if broken:
        reasons.append("broken")
    elif len(cur) < 2:
        reasons.append("lt2_reaction_touches")
    M = bars_of(magnet_df) if magnet_df is not None else B
    if magnet_df is None:
        tm = t
    else:                                                                   # finer bars that end by the end of bar t (no look-ahead)
        tm = int(np.searchsorted(M.ts.to_numpy(), bar_end(B, t).to_datetime64(), side="left")) - 1
    tm = max(tm, 0)
    sess = np.flatnonzero((M.day == M.day.iloc[tm]).to_numpy())
    sess = sess[sess <= tm]
    sgn = np.sign(M.C[sess] - (lo + hi) / 2)
    cross = int(np.sum(sgn[1:] * sgn[:-1] < 0)) if len(sgn) > 1 else 0
    if cross >= int(s["magnet_crossings"]) and s["magnet_invalidates"]:
        reasons.append("magnet")
    c = B.C[t]
    n = len(cur)
    return {"kind": "band", "lo": round(lo, 2), "hi": round(hi, 2), "mr": round(mr, 2), "width_mr": round(w / mr, 3) if mr else None,
            "role": role, "touches": cur, "touch_count": n, "earlier_side_touches": [x for g in older for x in g],
            "established": bool(not reasons and n >= int(s["established_touches"])), "breaks": breaks,
            "flipped": bool(breaks) and not broken, "broken": broken, "last_break_bar": breaks[-1]["bar"] if breaks else None,
            "price_side": "above" if c > hi else ("below" if c < lo else "inside"), "crossings_session": cross,
            "asof": _pt(B, t, c), "valid": not reasons, "reasons": reasons}


def band_from_reactions(B, i, j, kind):
    """K4 / TA4: the band low–high from the two reaction candles (never a single price). Swing highs ⇒ [higher body top (capped at the
    lower high), higher high]; swing lows ⇒ [lower low, lower body bottom (capped at the higher low)]."""
    if kind == "H":
        hi = max(B.H[i], B.H[j])
        tops = (max(B.O[i], B.C[i]), max(B.O[j], B.C[j]))
        lo = min(min(B.H[i], B.H[j]), max(tops))
        if lo >= hi:
            lo = min(tops)
    else:
        lo = min(B.L[i], B.L[j])
        bots = (min(B.O[i], B.C[i]), min(B.O[j], B.C[j]))
        hi = max(max(B.L[i], B.L[j]), min(bots))
        if hi <= lo:
            hi = max(bots)
    return float(lo), float(hi)


def candidate_bands(df, t, s=None, start=None, magnet_df=None):
    """Bands from every pair of same-kind confirmed pivots in [start, t] spaced ≥ min_spacing whose extremes lie within band_max_mr MR,
    each checked by check_band (valid, broken or invalid)."""
    s = load(s)
    B = bars_of(df)
    st = session_start(B, t, int(s["lookback_sessions"])) if start is None else start
    mr = mr_at(B, t, s)
    gap = int(s["min_spacing"])
    out, seen = [], set()
    for kind in ("H", "L"):
        y = B.H if kind == "H" else B.L
        piv = pivots(B, t, kind, s, start=st)
        for a, i in enumerate(piv):
            for j in piv[a + 1:]:
                if j - i < gap or abs(y[i] - y[j]) > float(s["band_max_mr"]) * mr:
                    continue
                lo, hi = band_from_reactions(B, i, j, kind)
                key = (round(lo, 2), round(hi, 2))
                if key in seen:
                    continue
                seen.add(key)
                f = check_band(B, t, lo, hi, s, start=st, magnet_df=magnet_df)
                f["defined_by"] = [_pt(B, i, y[i]), _pt(B, j, y[j])]
                out.append(f)
    return out


def rank_band(x):
    """Band order (documented): more reaction touches first; then the more recent last touch; then the narrower band."""
    last = x["touches"][-1]["bar"] if x["touches"] else -1
    return (-x["touch_count"], -last, x["hi"] - x["lo"])


def dedupe_bands(bands):
    """Overlapping bands are one area: keep the best by `rank_band`."""
    keep = []
    for x in sorted(bands, key=rank_band):
        if not any(x["lo"] <= k["hi"] and k["lo"] <= x["hi"] for k in keep):
            keep.append(x)
    return keep


def select_bands(bands, price, s=None, debug=False):
    """TA4 display: valid bands, at most `max_bands_per_side` above and below `price` (nearest first; a band containing price counts on
    its role's side), plus the most recently broken band (flag "broken", drawn dashed). Invalid ones only when debug."""
    s = load(s)
    n = int(s["max_bands_per_side"])
    ok = dedupe_bands([x for x in bands if x["valid"]])

    def above(x):
        return x["lo"] > price or (x["lo"] <= price <= x["hi"] and x["role"] == RES)

    def dist(x):
        return 0.0 if x["lo"] <= price <= x["hi"] else min(abs(x["lo"] - price), abs(x["hi"] - price))
    up = sorted([x for x in ok if above(x)], key=dist)[:n]
    dn = sorted([x for x in ok if not above(x)], key=dist)[:n]
    shown = up + dn
    br = [x for x in bands if x["broken"] and set(x["reasons"]) == {"broken"}
          and not any(x["lo"] <= k["hi"] and k["lo"] <= x["hi"] for k in shown)]
    if br:
        shown.append(max(br, key=lambda x: (x["last_break_bar"], -(x["hi"] - x["lo"]))))
    if debug:
        ids = {id(x) for x in shown}
        shown += [x for x in bands if id(x) not in ids]
    return shown


def latest_broken_only(bands):
    """TA4 on a list of checked bands of one chart: every broken band except the most recently broken one gets reason
    "broken_not_latest" (valid stays False for all broken bands; the latest broken one is the one a chart may show dashed)."""
    br = [x for x in bands if x["broken"]]
    if len(br) < 2:
        return bands
    keep = max(br, key=lambda x: x["last_break_bar"])
    for x in br:
        if x is not keep and "broken_not_latest" not in x["reasons"]:
            x["reasons"] = x["reasons"] + ["broken_not_latest"]
    return bands


# ------------------------------------------------------------------------------------------------ CONFLUENCE (K4 + K6.4)
def confluence(band, line, s=None):
    """A valid band and a valid line of the same role meet within confluence_mr MR — at the decision bar (offset 0) or at a projected
    bar of the line's next-touch zone. Returns facts (offset, line value, band, distance in MR) or None."""
    s = load(s)
    if not (band["valid"] and line["valid"]) or band["role"] != line["side"]:
        return None
    if {line["anchor1"]["bar"], line["anchor2"]["bar"]} & {p["bar"] for p in band["touches"]}:
        return None                                                         # not independent tools (KB part B step 3 "confluence")
    mr = line["mr"]
    t = line["asof"]["bar"]
    lim = float(s["confluence_mr"]) * mr
    offs = [0] + [p["offset"] for p in ((line.get("projected_zone") or {}).get("path") or [])]
    for o in offs:
        y = line_value(line, t + o)
        d = max(band["lo"] - y, y - band["hi"], 0.0)
        if d <= lim:
            return {"kind": "confluence", "role": band["role"], "offset": int(o), "line_value": round(y, 2), "band": [band["lo"], band["hi"]],
                    "distance_mr": round(d / mr, 3) if mr else None, "zone": [round(min(band["lo"], y), 2), round(max(band["hi"], y), 2)],
                    "line_anchors": [line["anchor1"], line["anchor2"]], "band_touches": band["touches"]}
    return None


def confluences(bands, lines, s=None):
    out = []
    for b in bands:
        for ln in lines:
            c = confluence(b, ln, s)
            if c:
                out.append(c)
    return out
