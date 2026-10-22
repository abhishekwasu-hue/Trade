"""decision3/chart_lines.py — P8 CLEAN CHARTS (Abhi 21 Oct): which lines and areas a chart SHOWS. DISPLAY ONLY — the reader still reads
ALL lines in its reading / evidence; nothing here decides, blocks or triggers an entry.

SHOW, in this order (category a → d):
  (a) evidence lines — the line in confluence with the entry area that price touched in this visit (the visit's bars hold the line's
      value inside the entry area's band); for E4 (b) the broken line being retested (its id in ctx["evidence_ids"]). Always shown.
  (b) the channel price is in now on the setup timeframe — both boundaries (one channel object).
  (c) the next line in price's path above and below (the nearest line met between the entry and the target / the invalidation).
  (d) higher-degree lines (a higher timeframe than the setup one, or a higher swing degree) that price respects in the current move
      (touched since the current leg's start swing and not broken).
HIDE (behind "Show all lines": the HTML report reveals them in a second image, a PNG lists "hidden: N"):
  dead lines (closed through, not being retested now); lines outside the trade's path (beyond the next opposite area or beyond the
  invalidation); a lower-degree line nearly parallel and close to a higher-degree one (kept: the higher degree — "nearly parallel and
  close" = the two lines stay within one entry-area width of each other over their common span, a comparison with the area, no number);
  lines that ended before the current leg's start swing (by structure: drawn to / broken before that swing). Still crowded ⇒ keep the
  earlier category, then the higher degree, then more touches. At most `chart_max_lines` (a DISPLAY setting, decision3/settings.py
  OUTPUT) lines are shown; the legend lists only the shown lines.
AREAS: the refined base (RC2), the target area and the invalidation drawn strong; the context area faint; the other areas faded;
dead areas hidden.

Objects are decision3.draw_objects dicts (time / price geometry). Bars = the setup timeframe's bars up to the trigger (timestamp, high,
low, close) — lines are straight in that bar index, as decision3.draw_render draws them.
"""
import numpy as np
import pandas as pd

LINE_KINDS = ("line", "channel", "pattern")
TF_RANK = {"5M": 0, "15M": 1, "1H": 2, "D": 3, "W": 4}
CATEGORY = {"a": "evidence line", "b": "channel price is in", "c": "next line in the path", "d": "higher-degree line respected"}


def max_lines_default():
    from . import settings as S3
    return int(S3.OUTPUT["chart_max_lines"][0])


def key_of(o):
    """A line's identity: its id, else its first evidence id (the replay's line objects carry the reader's line id there)."""
    if o.get("id") is not None:
        return str(o["id"])
    ev = o.get("evidence") or []
    if ev:
        return str(ev[0])
    return f"{o.get('kind')}|{o.get('label')}|{o.get('t0')}"


def rank(o):
    """Degree for comparison: the timeframe the line was read on, then its swing degree."""
    return (TF_RANK.get(str(o.get("tf")), 1), int(o.get("degree") or 0))


class _Bars:
    def __init__(self, bars):
        b = bars if isinstance(bars, pd.DataFrame) else pd.DataFrame(bars or [], columns=["timestamp", "high", "low", "close"])
        ts = b["timestamp"] if "timestamp" in b.columns else b.get("start")
        self.ts = pd.to_datetime(pd.Series(ts)).to_numpy("datetime64[ns]")
        self.h = b["high"].to_numpy(float) if len(b) else np.zeros(0)
        self.l = b["low"].to_numpy(float) if len(b) else np.zeros(0)
        self.c = b["close"].to_numpy(float) if len(b) else np.zeros(0)
        self.n = len(self.ts)

    def i(self, t):
        if t is None or not self.n:
            return None
        return int(np.searchsorted(self.ts, np.datetime64(pd.Timestamp(t), "ns"), side="right")) - 1


def _segs(o):
    """The straight lines of an object: [(t0, p0, t1, p1)] — the main line, then a channel's / pattern's extra lines."""
    out = [(o["t0"], float(o["p0"]), o["t1"], float(o["p1"]))]
    for d in o.get("lines") or ():
        out.append((d["t0"], float(d["p0"]), d["t1"], float(d["p1"])))
    return out


def _value(B, seg, i):
    t0, p0, t1, p1 = seg
    i0, i1 = B.i(t0), B.i(t1)
    if i0 is None or i1 is None:
        return None
    if i1 == i0:
        return p0
    return p0 + (p1 - p0) * (i - i0) / (i1 - i0)


def _touch_runs(B, seg, a, b):
    """Reactions at the line between bars a … b: runs of consecutive bars whose range holds the line's value (one run = one touch)."""
    n, prev = 0, False
    bars = []
    for i in range(max(a, 0), min(b, B.n - 1) + 1):
        v = _value(B, seg, i)
        hit = v is not None and B.l[i] <= v <= B.h[i]
        if hit:
            bars.append(i)
            if not prev:
                n += 1
        prev = hit
    return n, bars


def _width(ctx, objects, B):
    """'Close' for the parallel test: the entry area's width; no band (a line entry) ⇒ the median width of the drawn areas; none ⇒ the
    median bar range of the window. A comparison with the chart's own objects — no number."""
    a = ctx.get("area")
    if a and float(a[1]) > float(a[0]):
        return float(a[1]) - float(a[0])
    ws = [float(o["p1"]) - float(o["p0"]) for o in objects if o.get("kind") == "area" and float(o["p1"]) > float(o["p0"])]
    if ws:
        return float(np.median(ws))
    if B.n:
        return float(np.median(B.h - B.l))
    return 0.0


def _leg_start(ctx, objects, B, t_i, d):
    """The current leg's start swing (by structure): ctx["leg_start"] if given, else the newest swing object on the side opposite to the
    trade before the visit (bear call: the swing low price rallied from), else the window's extreme on that side before the visit."""
    if ctx.get("leg_start") is not None:
        return B.i(ctx["leg_start"])
    vs = B.i(ctx.get("visit_start")) if ctx.get("visit_start") is not None else t_i
    vs = t_i if vs is None else vs
    want_high = d > 0                                                      # bull put: the leg down started at a swing high
    sw = []
    for o in objects:
        if o.get("kind") != "swing":
            continue
        hi = o.get("src") == "H" if o.get("src") in ("H", "L") else str(o.get("label", "")).upper() in ("HH", "LH", "EQH", "H")
        if hi == want_high:
            k = B.i(o["t0"])
            if k is not None and k <= vs:
                sw.append(k)
    if sw:
        return max(sw)
    if not B.n or vs is None or vs <= 0:
        return 0
    seg = B.h[:vs + 1] if want_high else B.l[:vs + 1]
    return int(np.argmax(seg) if want_high else np.argmin(seg))


def select(objects, ctx=None, max_lines=None):
    """objects (validated draw objects) ⇒ {"shown": objects to draw (all non-line objects + the selected lines, areas restyled),
    "hidden": [{"key", "label", "reason"}], "lines": [{"key", "label", "category"}] (the shown lines, in legend order),
    "evidence": [keys], "max_lines": n}. ctx = {t, d, area (lo, hi), refined (lo, hi) | None, target (lo, hi) | None, invalidation,
    entry_ref, bars, visit_start, evidence_ids, leg_start, setup_tf}. Never raises on a missing context field (it only shows less)."""
    ctx = dict(ctx or {})
    n_max = int(max_lines if max_lines is not None else max_lines_default())
    d = int(ctx.get("d") or 0)
    B = _Bars(ctx.get("bars") if ctx.get("bars") is not None else [])
    t_i = B.i(ctx.get("t")) if ctx.get("t") is not None else (B.n - 1 if B.n else None)
    t_i = (B.n - 1) if (t_i is None and B.n) else t_i
    close = float(ctx["entry_ref"]) if ctx.get("entry_ref") is not None else (float(B.c[t_i]) if t_i is not None and B.n else None)
    setup_rank = TF_RANK.get(str(ctx.get("setup_tf") or "15M"), 1)
    vs = B.i(ctx.get("visit_start")) if ctx.get("visit_start") is not None else t_i
    leg = _leg_start(ctx, objects, B, t_i, d) if t_i is not None else None
    band = ctx.get("refined") or ctx.get("area")
    inv = ctx.get("invalidation")
    tg = ctx.get("target")
    lo_b, hi_b = -np.inf, np.inf                                           # the trade's path: target far edge … invalidation
    if d < 0:
        hi_b = float(inv) if inv is not None else np.inf
        lo_b = float(tg[0]) if tg else -np.inf
    elif d > 0:
        lo_b = float(inv) if inv is not None else -np.inf
        hi_b = float(tg[1]) if tg else np.inf
    ev_ids = {str(x) for x in ctx.get("evidence_ids") or ()}
    width = _width(ctx, objects, B)

    lines, others = [], []
    for o in objects:
        (lines if o.get("kind") in LINE_KINDS else others).append(o)
    info = {}
    for o in lines:
        k = key_of(o)
        segs = _segs(o)
        now = [_value(B, s, t_i) for s in segs] if t_i is not None else [None]
        now = [v for v in now if v is not None]
        tv, tb = (_touch_runs(B, segs[0], vs, t_i) if (vs is not None and t_i is not None) else (0, []))
        lt, lb = (_touch_runs(B, segs[0], leg, t_i) if (leg is not None and t_i is not None) else (0, []))
        if len(segs) > 1 and vs is not None and t_i is not None:
            for s in segs[1:]:
                n2, b2 = _touch_runs(B, s, vs, t_i)
                tv, tb = tv + n2, tb + b2
                n3, _b3 = _touch_runs(B, s, leg if leg is not None else vs, t_i)
                lt += n3
        info[k] = {"o": o, "segs": segs, "now": now, "visit_touch": tb, "leg_touches": lt,
                   "broken": str(o.get("state")) in ("broken", "failed"), "end": B.i(o["t1"])}

    def evidence(k):
        x = info[k]
        if k in ev_ids or any(e in ev_ids for e in (x["o"].get("evidence") or [])):
            return True
        if not band or not x["visit_touch"]:
            return False
        for i in x["visit_touch"]:
            v = _value(B, x["segs"][0], i)
            if v is not None and float(band[0]) <= v <= float(band[1]):
                return True
        return False

    hidden, cat = {}, {}
    for k, x in info.items():
        if evidence(k):
            cat[k] = "a"
            continue
        if x["broken"] and not x["visit_touch"]:
            hidden[k] = "dead (closed through, not being retested)"
        elif leg is not None and x["end"] is not None and x["end"] < leg:
            hidden[k] = "ended before the current leg's start swing"
        elif x["now"] and all(v > hi_b or v < lo_b for v in x["now"]) and not (
                x["o"]["kind"] == "channel" and close is not None and min(x["now"]) <= close <= max(x["now"])):
            hidden[k] = "outside the trade's path (beyond the next opposite area / the invalidation)"
    # parallel duplicates: a lower-degree line close to a higher-degree one over their common span
    alive = [k for k in info if k not in hidden]
    for k in alive:
        if cat.get(k) == "a":
            continue
        x = info[k]
        for k2 in alive:
            if k2 == k or k2 in hidden or rank(info[k2]["o"]) <= rank(x["o"]):
                continue
            a0 = max(B.i(x["o"]["t0"]) or 0, B.i(info[k2]["o"]["t0"]) or 0)
            ends = [a0, t_i] if t_i is not None else [a0]
            gaps = []
            for i in ends:
                v1, v2 = _value(B, x["segs"][0], i), _value(B, info[k2]["segs"][0], i)
                if v1 is not None and v2 is not None:
                    gaps.append(abs(v1 - v2))
            if gaps and width > 0 and max(gaps) <= width:
                hidden[k] = f"nearly parallel and close to the higher-degree line {info[k2]['o'].get('label')}"
                break
    alive = [k for k in info if k not in hidden]
    # (b) the channel price is in now (setup timeframe first, then the tightest)
    inside = []
    for k in alive:
        x = info[k]
        if x["o"]["kind"] == "channel" and not x["broken"] and len(x["now"]) >= 2 and close is not None and \
                min(x["now"]) <= close <= max(x["now"]):
            inside.append((0 if TF_RANK.get(str(x["o"].get("tf")), 1) == setup_rank else 1, max(x["now"]) - min(x["now"]), k))
    if inside:
        k = sorted(inside)[0][2]
        cat.setdefault(k, "b")
    # (c) the next line above and below in the path
    if close is not None:
        above = [(min(v for v in info[k]["now"] if v >= close), k) for k in alive if k not in cat and not info[k]["broken"]
                 and any(close <= v <= hi_b for v in info[k]["now"])]
        below = [(max(v for v in info[k]["now"] if v <= close), k) for k in alive if k not in cat and not info[k]["broken"]
                 and any(lo_b <= v <= close for v in info[k]["now"])]
        if above:
            cat.setdefault(min(above)[1], "c")
        if below:
            cat.setdefault(max(below)[1], "c")
    # (d) higher-degree lines respected in the current move
    for k in alive:
        x = info[k]
        if k not in cat and not x["broken"] and TF_RANK.get(str(x["o"].get("tf")), 1) > setup_rank and x["leg_touches"] > 0:
            cat[k] = "d"
    for k in alive:
        if k not in cat and k not in hidden:
            hidden[k] = "not evidence / current channel / next line in path / respected higher-degree line"
    order = sorted(cat, key=lambda k: (cat[k], -rank(info[k]["o"])[0], -rank(info[k]["o"])[1], -info[k]["leg_touches"], k))
    keep = order[:max(n_max, 0)]
    for k in order[max(n_max, 0):]:
        hidden[k] = f"over the cap (chart_max_lines = {n_max})"
    shown_lines = [info[k]["o"] for k in keep]
    return {"shown": style_areas(others, ctx) + shown_lines,
            "hidden": [{"key": k, "label": info[k]["o"].get("label"), "reason": r} for k, r in hidden.items()],
            "lines": [{"key": k, "label": info[k]["o"].get("label"), "category": CATEGORY[cat[k]]} for k in keep],
            "evidence": [k for k in order if cat[k] == "a"], "max_lines": n_max}


def _same(o, band):
    return band is not None and round(float(o["p0"]), 2) == round(float(band[0]), 2) and \
        round(float(o["p1"]), 2) == round(float(band[1]), 2)


def style_areas(objects, ctx):
    """AREAS (P8): the refined base and the target area strong, the context area faint, other areas faded, dead areas hidden. A refined
    base not in the list is added (tf 15M, label "refined base")."""
    ctx = ctx or {}
    out, have_rb = [], False
    for o in objects:
        if o.get("kind") != "area":
            out.append(o)
            continue
        if str(o.get("state")) == "dead":
            continue
        side = "supply" if ".supply" in str(o.get("style_key")) else ("demand" if ".demand" in str(o.get("style_key")) else
                                                                      ("supply" if int(ctx.get("d") or 0) < 0 else "demand"))
        o = dict(o)
        if _same(o, ctx.get("refined")):
            o["style_key"], have_rb = f"area.{side}.refined", True
        elif _same(o, ctx.get("target")):
            o["style_key"] = f"area.{'demand' if side == 'supply' else 'supply'}.target" if ".target" not in o["style_key"] else o["style_key"]
        elif _same(o, ctx.get("area")):
            o["style_key"] = f"area.{side}.context"
        elif str(o.get("state")) != "broken":
            o["style_key"] = f"area.{side}.faded"
        out.append(o)
    rb = ctx.get("refined")
    if rb and not have_rb and ctx.get("t") is not None:
        side = "supply" if int(ctx.get("d") or 0) < 0 else "demand"
        out.append({"kind": "area", "tf": "15M", "t0": str(ctx.get("refined_t") or ctx["t"]), "t1": str(ctx["t"]), "p0": float(rb[0]),
                    "p1": float(rb[1]), "label": f"refined base 15M {float(rb[0]):,.0f}–{float(rb[1]):,.0f}", "state": "active",
                    "style_key": f"area.{side}.refined", "evidence": []})
    return out


def evidence_ids_of(e):
    """The evidence line ids of an entry: E4 (b) on a broken line ⇒ that line's id (draw objects carry the reader's line id)."""
    a = (e or {}).get("area") or {}
    out = []
    if str(a.get("id", "")).startswith("line:"):
        out.append(str(a["id"])[len("line:"):])
    ln = a.get("line") or {}
    if ln.get("id") is not None:
        out.append(str(ln["id"]))
    return out


def ctx_of_row(r, setup_tf="15M"):
    """A decision row ⇒ the selection context (its first entry if any, else its traded area). Display only."""
    r = r or {}
    e = (r.get("entries") or [None])[0]
    if e:
        a = e.get("area") or {}
        rb = e.get("refined_base") or {}
        inv = e.get("invalidation")
        inv = inv.get("price") if isinstance(inv, dict) else inv
        return {"t": e.get("trigger_ts"), "d": int(e.get("direction") or 0), "setup_tf": setup_tf,
                "area": (float(a["lo"]), float(a["hi"])) if a.get("lo") is not None and a.get("hi") is not None else None,
                "refined": (float(rb["lo"]), float(rb["hi"])) if rb.get("lo") is not None else None, "refined_t": rb.get("ts"),
                "invalidation": None if inv is None else float(inv), "entry_ref": e.get("entry_ref"),
                "visit_start": e.get("area_visit_start") or e.get("visit_start"), "evidence_ids": evidence_ids_of(e)}
    lv = r.get("level") or {}
    return {"setup_tf": setup_tf, "area": (float(lv["lo"]), float(lv["hi"])) if lv.get("lo") is not None else None}


def legend_count(prims):
    """Legend entries of LINE kinds in a draw_render primitive list (right-margin labels)."""
    return sum(1 for p in prims if p.get("type") == "text" and p.get("margin") and p.get("src_kind") in LINE_KINDS)


def assert_legend(prims, max_lines):
    """CI / renderer guard: a chart legend never lists more lines than the display setting."""
    n = legend_count(prims)
    if max_lines is not None and n > int(max_lines):
        raise AssertionError(f"chart legend lists {n} lines > chart_max_lines {int(max_lines)} (P8 clean charts)")
    return n
