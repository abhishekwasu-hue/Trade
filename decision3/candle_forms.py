"""decision3/candle_forms.py — PA standard §2G: candle forms read relative to their neighbours and ONLY at a location (area, line, level).

EVIDENCE / STATE only: nothing here blocks or triggers an entry (the entry models decide; wiring into the evidence list is a later step).

Forms, in BOTH directions (bullish = buyers won the form, bearish = sellers won) and at ANY location (not only the commitment in the trade
direction). Every form is the method's own comparative reader in `decision3/method.py`, called read-only (no new rule, no ratio):
  • rejection (a long wick)      = `method._one_candle_form` "pin": the wick on one side longer than the rest of the candle;
  • momentum                      = `method._one_candle_form` "strong_close" (the body larger than both wicks together = it closes near
                                    its extreme) AND `method.candle_read(...)["big_body"]` (the body larger than the average body of the
                                    neighbouring candles: the current leg's earlier candles — `ctx`);
  • engulfing, morning / evening star, tweezer bottom / top, inside-bar break, doji then confirmation
                                  = `method._reversal_form_compare` read in each direction (the method's own order decides when one bar
                                    fits two multi-candle forms — the same order the commitment uses);
  • inside bar (state)            = the candle's high and low inside the previous candle's (the commitment's "wait: inside" definition);
  • indecision (doji, state)      = `method.is_doji` (the body smaller than each wick).
The comparative definitions are always used here (`candle_rule = compare`, `session_windows = False`: one continuous chart), whatever the
engine's what-if switches say.

Location: a form counts only when one of its candles trades into a location known at bar t —
  • an area (1H zone) or a level (Daily / Weekly band) alive in `Levels.snapshot(t)` (lo … hi);
  • a line: the trade-degree swing line of each side (`trendline.swing_line`, d = UP ⇒ rising support line from lows, d = DOWN ⇒ falling
    resistance line from highs) — the candle's range reaches the line's value on its bars;
  • or any location the caller passes ({kind, lo, hi} or a line {kind: "line", p1: [bar, price], slope}).
Relation (evidence wording): a bullish form at support (demand / support line) = "with" the location; a bearish form there = "against"
(e.g. a bearish engulfing at demand). Mirror at resistance. Doji / inside bar = "neutral" (indecision at the location). Off-location forms
are counted (`off_location`) but never listed as evidence.

Timeframes: "15M" (the engine's bars) or "1H" (completed 1H candles built from the 15M bars by `levels.h1_frame`; the hour containing bar
t is read only once it is complete, so the last short hour of a session is read when its time has passed — never a partial candle).

No look-ahead: bars ≤ t, swings / lines / areas known at t only.

API:
  forms_on(A, j, s=None, ctx=None)                        → every form ending at candle j, both directions, no location (list of dicts)
  forms_at(A, j, locations, s=None, ctx=None, d=None)     → the forms at the given locations (dict; raw-frame core)
  read_candle_forms(V, t, d=None, tf="15M", locations=None) → the same on a V22 state at bar t (locations from areas + lines)
  draw_objects(read)                                      → [{kind, tf, t0, t1, p0, p1, label, state, evidence}] for the chart track
"""
import pandas as pd

from . import method as M
from . import settings as S3

UP, DOWN = 1, -1
SUPPORT, RESISTANCE = "support", "resistance"

# form ⇒ (name when bullish, name when bearish, number of candles in the form)
NAMES = {
    "rejection": ("bullish rejection (long lower wick)", "bearish rejection (long upper wick)", 1),
    "momentum": ("bullish momentum candle", "bearish momentum candle", 1),
    "engulf": ("bullish engulfing", "bearish engulfing", 2),
    "star": ("morning star", "evening star", 3),
    "tweezer": ("tweezer bottom", "tweezer top", 2),
    "inside_break": ("inside bar broken upward", "inside bar broken downward", 3),
    "doji_confirm": ("doji, then a bullish confirmation", "doji, then a bearish confirmation", 2),
}
STATES = {"doji": ("indecision (doji)", 1), "inside_bar": ("inside bar", 1)}
MULTI = ("engulf", "star", "tweezer", "inside_break", "doji_confirm")


def method_settings(s=None):
    """The comparative reading (method §3) whatever the caller's what-if switches: `candle_rule = compare`, `session_windows = False`."""
    return {**S3.DEFAULTS, **(s or {}), "candle_rule": "compare", "session_windows": False}


def forms_on(A, j, s=None, ctx=None):
    """Every candle form that ends at candle j, in both directions, read only from candles ≤ j. ctx = the first candle of the neighbours
    the momentum candle is compared with (the current leg); None or ctx ≥ j ⇒ momentum not read (no neighbours — reported as `na`).
    Returns a list of {form, dir (+1 bullish / −1 bearish / 0 state), name, bars: [first, j], n}."""
    sm = method_settings(s)
    j = int(j)
    out = []
    if j < 0:
        return out
    o, h, lo, c = M._ohlc(A, j)
    for d in (UP, DOWN):
        one = M._one_candle_form(A, j, d)
        if one == "pin":
            out.append(_f("rejection", d, j))
        elif one == "strong_close":
            big = None
            if ctx is not None and int(ctx) < j:
                big = M.candle_read(A, j, sm, int(ctx))["big_body"]
            if big:
                out.append(_f("momentum", d, j))
            elif big is None:
                out.append({**_f("momentum", d, j), "na": "no neighbouring candles to compare the body with"})
        fm = M._reversal_form_compare(A, j, d, sm)
        if fm is not None and fm[0] in MULTI and j - NAMES[fm[0]][2] + 1 >= 0:
            out.append(_f(fm[0], d, j))
    if M.is_doji(o, h, lo, c, sm):
        out.append(_state("doji", j))
    if j >= 1 and h <= float(A["high"][j - 1]) and lo >= float(A["low"][j - 1]):
        out.append(_state("inside_bar", j))
    return [x for x in out if not x.get("na")] + [x for x in out if x.get("na")]


def _f(form, d, j):
    n = NAMES[form][2]
    return {"form": form, "dir": d, "name": NAMES[form][0 if d == UP else 1], "bars": [j - n + 1, j], "n": n}


def _state(form, j):
    return {"form": form, "dir": 0, "name": STATES[form][0], "bars": [j, j], "n": 1}


# ------------------------------------------------------------------------------------------------ locations
def _line_at(loc, b):
    b1, y1 = loc["p1"]
    return float(y1) + float(loc["slope"]) * (float(b) - float(b1))


def touches(loc, lo, hi, a, b):
    """Does a candle (low lo, high hi; spanning base bars a … b) trade into the location? Area / level: the ranges overlap. Line: the
    candle's range reaches the line's value on its bars (a 1H candle spans four 15M bars)."""
    if loc.get("kind") == "line":
        ya, yb = _line_at(loc, a), _line_at(loc, b)
        return bool(lo <= max(ya, yb) and hi >= min(ya, yb))
    return bool(lo <= float(loc["hi"]) and hi >= float(loc["lo"]))


def relation(form_dir, role):
    """with / against / neutral: a bullish form at support (demand) is with it, a bearish one against; mirror at resistance."""
    if form_dir == 0 or role not in (SUPPORT, RESISTANCE):
        return "neutral"
    return "with" if (form_dir == UP) == (role == SUPPORT) else "against"


def _loc_word(loc):
    role = loc.get("role")
    if loc.get("kind") == "line":
        slope = loc.get("slope")
        tilt = "" if slope is None else ("rising " if slope > 0 else "falling " if slope < 0 else "flat ")
        return f"{tilt}{role or ''} line".strip()
    word = {SUPPORT: "demand", RESISTANCE: "supply"}.get(role, "location")
    tf = loc.get("tf")
    band = f"{float(loc['lo']):,.0f}–{float(loc['hi']):,.0f}"
    if loc.get("kind") == "level":
        return f"{TF_WORD.get(tf, tf or '')} {word} level {band}".strip()
    return f"{word} {band}" + (f" ({tf})" if tf else "")


TF_WORD = {"D": "Daily", "W": "Weekly", "1H": "1H"}


def forms_at(A, j, locations, s=None, ctx=None, d=None, span=None):
    """Raw-frame core: the forms ending at candle j that touch a location. span(i) ⇒ (first, last) base bar of candle i (line values are
    on base bars; default = the candle's own index). d = the trade direction (optional) ⇒ each form also says if it is for / against it.
    Returns {forms: [...], states: [...], off_location: [names], evidence: [str]}."""
    span = span or (lambda i: (int(i), int(i)))
    found = forms_on(A, j, s, ctx)
    out = {"forms": [], "states": [], "off_location": [], "na": [], "evidence": []}
    for f in found:
        if f.get("na"):
            out["na"].append(f"{f['name']}: {f['na']}")
            continue
        at = []
        for loc in locations or []:
            hit = [i for i in range(f["bars"][0], f["bars"][1] + 1)
                   if touches(loc, float(A["low"][i]), float(A["high"][i]), *span(i))]
            if hit:
                at.append({"kind": loc.get("kind"), "id": loc.get("id"), "tf": loc.get("tf"), "role": loc.get("role"),
                           "where": _loc_word(loc), "relation": relation(f["dir"], loc.get("role")), "candles": hit})
        if not at:
            out["off_location"].append(f["name"])
            continue
        g = {**f, "at": at}
        if d in (UP, DOWN) and f["dir"] != 0:
            g["trade"] = "for" if f["dir"] == d else "against"
        (out["states"] if f["dir"] == 0 else out["forms"]).append(g)
        parts = []
        for rel, word in (("with", "with"), ("against", "against"), ("neutral", "indecision")):
            w = [x["where"] for x in at if x["relation"] == rel]
            if w:
                parts.append(f"{word}: {', '.join(w)}")
        out["evidence"].append(f"{f['name']} at a location — {'; '.join(parts)}" + (f" ({g['trade']} the trade)" if "trade" in g else ""))
    return out


def locations(V, t, weekly=False):
    """Locations known at bar t: every alive band in `Levels.snapshot(t)` (1H ⇒ area; Daily ⇒ level; Weekly only with weekly=True — Abhi
    Z-1u: a Weekly band is context only, and one wide band would put every candle "at a location") and the two swing lines
    (`trendline.swing_line`, up = rising support from lows, down = falling resistance from highs). Bars ≤ t only."""
    from . import trendline as TL
    out = []
    for x in V.levels.snapshot(int(t)):
        if x["tf"] == "W" and not weekly:
            continue
        out.append({"kind": "area" if x["tf"] == "1H" else "level", "id": x["id"], "tf": x["tf"], "role": x["role"],
                    "lo": float(x["lo"]), "hi": float(x["hi"]), "state": x.get("state")})
    for d, role in ((UP, SUPPORT), (DOWN, RESISTANCE)):
        ln = TL.swing_line(V, int(t), d)
        if ln is not None:
            out.append({"kind": "line", "id": f"swing_line_{'up' if d == UP else 'down'}", "tf": "15M", "role": role,
                        "p1": list(ln["p1"]), "p2": list(ln["p2"]), "slope": float(ln["slope"]), "value_t": ln["value_t"]})
    return out


def leg_start(V, t, degree=None):
    """The first candle of the current leg at bar t: the bar after the last swing (swings2 degree `tl_degree`, the pullback degree D1)
    confirmed by t. None ⇒ no swing known yet."""
    deg = int(V.s.get("tl_degree", 1) if degree is None else degree)
    piv = [p for p in V.res["pivots"].get(deg, []) if p.confirm_bar <= t and p.bar < t]
    return (max(int(p.bar) for p in piv) + 1) if piv else None


def h1_view(V, t):
    """Completed 1H candles known at 15M bar t (`levels.h1_frame`, 09:15-anchored like the engine's 1H): (A1 dict, span(j), j_last,
    ts list). The hour holding bar t counts only once its hour has ended at bar t's close."""
    lv = V.levels
    h1, of = lv.h1, lv.h1_of
    j = int(of[int(t)])
    start = pd.Timestamp(h1["timestamp"].iloc[j])
    if pd.Timestamp(V.bar_end[int(t)]) < start + pd.Timedelta(hours=1):
        j -= 1                                                             # the hour is still forming at t
    A1 = {k: h1[k].to_numpy(float)[:j + 1] for k in ("open", "high", "low", "close")}
    first = {}
    last = {}
    for i, x in enumerate(of[:int(t) + 1]):
        first.setdefault(int(x), i)
        last[int(x)] = i
    span = lambda i: (first.get(int(i), 0), last.get(int(i), int(t)))     # noqa: E731
    return A1, span, j, [pd.Timestamp(x) for x in h1["timestamp"].iloc[:j + 1]]


def read_candle_forms(V, t, d=None, tf="15M", locations_=None):
    """PA §2G on a V22 state at 15M bar t: the forms on the last candle known at t (15M bar t, or the last completed 1H candle), listed
    only where they touch a location. d = trade direction (optional, for the for / against wording). Returns a plain dict:
    {t, tf, candle, ts, forms, states, off_location, na, evidence, locations_n}."""
    t = int(t)
    locs = locations(V, t) if locations_ is None else list(locations_)
    ls = leg_start(V, t)
    if tf == "15M":
        A, span, j, ts = V.levels.A, None, t, [pd.Timestamp(x) for x in V._ts[:t + 1]]
        ctx = ls
    elif tf == "1H":
        A, span, j, ts = h1_view(V, t)
        ctx = None
        if ls is not None:
            ctx = next((i for i in range(j + 1) if span(i)[0] >= ls), None)
    else:
        raise ValueError(f"candle_forms: tf {tf!r} — 15M / 1H")
    out = {"t": t, "tf": tf, "candle": j, "ts": None if j < 0 else str(ts[j]), "forms": [], "states": [], "off_location": [], "na": [],
           "evidence": [], "locations_n": len(locs), "leg_start": ctx}
    if j < 0:
        out["na"].append("no completed candle yet")
        return out
    r = forms_at(A, j, locs, V.s, ctx, d, span)
    out.update(r)
    out["_frame"] = {"ts": [str(ts[i]) for i in range(len(ts))], "A": A}  # for draw_objects (prices of the form's candles)
    return out


def draw_objects(read):
    """Chart objects for each form / state at a location: a box over the form's candles (t0 … t1, low … high)."""
    fr = read.get("_frame")
    if not fr:
        return []
    A, ts = fr["A"], fr["ts"]
    objs = []
    for f in read.get("forms", []) + read.get("states", []):
        a, b = f["bars"]
        lo = float(min(A["low"][i] for i in range(a, b + 1)))
        hi = float(max(A["high"][i] for i in range(a, b + 1)))
        rel = sorted({x["relation"] for x in f["at"]})
        objs.append({"kind": "candle_form", "tf": read["tf"], "t0": ts[a], "t1": ts[b], "p0": lo, "p1": hi, "label": f["name"],
                     "state": "/".join(rel), "evidence": [f"{f['name']} at {x['where']} — {x['relation']}" for x in f["at"]]})
    return objs


def public(read):
    """The read without the private frame (JSON-safe)."""
    return {k: v for k, v in read.items() if not k.startswith("_")}
