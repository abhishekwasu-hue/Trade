"""decision3/legs_compare.py — PA standard §2B: impulse vs correction legs, judged by COMPARISON with the neighbouring legs, and the form
of a correction (zigzag ABC / flat / triangle / channel). EVIDENCE only: no entry, no block, no wave-count prediction.

A leg = the bars from one swing to the next of the same timeframe's external degree (mtf_state.swings: W / D / 1H / 15M / 5M), bars
(start swing, end swing]. Per leg, read on that timeframe's own candles:
  • body    — the average candle body (|close − open|) per bar;
  • overlap — the average share of each candle's range that overlaps the previous candle's range (pair high-low union = the whole);
  • volume  — the average FUT volume per bar (method §3: averages per bar, never sums); NA when any bar of the leg has no volume.
Comparison (no percentile, no threshold): a leg is impulse-like on a measure when it is beyond EVERY neighbouring leg (larger bodies /
less overlap / higher volume), correction-like when it is short of every neighbour (smaller bodies / more overlap / lower volume),
"between" otherwise. Neighbours = the adjacent legs on either side known at t (the leg after it may still be running — read so far).
Verdict = the side most measures take (a strict majority of the measures read); unanimous ⇒ "clear"; no majority ⇒ "mixed".
(legs2.settings2 percentiles c_hi / c_lo / baseline_legs are deliberately not used.)

Correction form (§2B), from the counter-move's own swings (start = the trend-direction extreme, then the internal swings inside it,
then the running extreme so far), comparison only:
  • 1 leg: "one leg (A)"; 2 legs: "A–B" (B short of A's start / B back to A's start);
  • zigzag (ABC): three legs, B stays short of A's start and C goes beyond A's end;
  • flat: three legs, B comes back to A's start or beyond;
  • triangle: four or more legs, the highs keep falling and the lows keep rising (contracting) — or the mirror (expanding);
  • channel: four or more legs that step in the counter direction on both sides (each high and each low beyond the previous one);
  • otherwise "complex". The form is what the swings show so far — never a forecast of the next leg.
No look-ahead: only bars / swings closed at the 15M bar t. No dates, times or fixed numbers; no new settings.
"""
import numpy as np

from . import mtf_state as MS

IMPULSE, CORRECTION, MIXED, NA = "impulse", "correction", "mixed", "NA"
MEASURES = ("body", "overlap", "volume")


# ------------------------------------------------------------------------------------------------ one leg
def leg_facts(F, i0, i1, dirn):
    """Measures of the leg (i0, i1] on frame F ({o, h, l, c, v}); dirn = +1 up / −1 down. < 1 bar ⇒ None."""
    i0, i1 = int(i0), int(i1)
    if i1 <= i0:
        return None
    o, h, l, c = (np.asarray(F[k], float) for k in ("o", "h", "l", "c"))
    idx = np.arange(i0 + 1, i1 + 1)
    body = float(np.mean(np.abs(c[idx] - o[idx])))
    ov = []
    for j in idx:
        top, bot = min(h[j], h[j - 1]), max(l[j], l[j - 1])
        span = max(h[j], h[j - 1]) - min(l[j], l[j - 1])
        ov.append(max(0.0, top - bot) / span if span > 0 else 1.0)
    vol, vol_na = None, None
    if F.get("v") is None:
        vol_na = "no volume for this timeframe"
    else:
        v = np.asarray(F["v"], float)[idx]
        if np.all(np.isfinite(v) & (v > 0)):
            vol = float(np.mean(v))
        else:
            vol_na = "a bar of the leg has no volume"
    return {"bars": int(len(idx)), "dir": int(dirn), "body": body, "overlap": float(np.mean(ov)), "volume": vol, "volume_na": vol_na}


def _side(x, ns, bigger_is_impulse=True):
    """'impulse' / 'correction' / 'between' for one measure of a leg against all its neighbours (None ⇒ not read)."""
    vals = [n for n in ns if n is not None]
    if x is None or not vals:
        return None
    if all(x > n for n in vals):
        return IMPULSE if bigger_is_impulse else CORRECTION
    if all(x < n for n in vals):
        return CORRECTION if bigger_is_impulse else IMPULSE
    return "between"


def compare(leg, neighbours):
    """§2B: the leg vs its neighbouring legs (list of leg_facts). Returns {verdict, clear, per measure side + words, why}."""
    if leg is None:
        return {"verdict": NA, "clear": False, "why": "leg has no bar", "measures": {}}
    ns = [n for n in neighbours if n is not None]
    if not ns:
        return {"verdict": NA, "clear": False, "why": "no neighbouring leg to compare with", "measures": {}}
    m = {"body": _side(leg["body"], [n["body"] for n in ns]),
         "overlap": _side(leg["overlap"], [n["overlap"] for n in ns], bigger_is_impulse=False),
         "volume": _side(leg["volume"], [n["volume"] for n in ns])}
    read = {k: v for k, v in m.items() if v is not None}
    n_imp = sum(1 for v in read.values() if v == IMPULSE)
    n_cor = sum(1 for v in read.values() if v == CORRECTION)
    if read and 2 * n_imp > len(read):
        verdict = IMPULSE
    elif read and 2 * n_cor > len(read):
        verdict = CORRECTION
    else:
        verdict = MIXED if read else NA
    words = {
        "body": {IMPULSE: "larger bodies", CORRECTION: "smaller bodies", "between": "bodies between the neighbours"},
        "overlap": {IMPULSE: "little overlap", CORRECTION: "overlapping candles", "between": "overlap between the neighbours"},
        "volume": {IMPULSE: "expanding volume", CORRECTION: "lower volume", "between": "volume between the neighbours"},
    }
    why = [words[k][v] for k, v in m.items() if v is not None]
    if m["volume"] is None:
        why.append("volume NA" + (f" ({leg.get('volume_na')})" if leg.get("volume_na") else ""))
    return {"verdict": verdict, "clear": bool(read) and (n_imp == len(read) or n_cor == len(read)),
            "measures": m, "why": ", ".join(why) + f" — vs {len(ns)} neighbouring leg{'s' if len(ns) > 1 else ''}"}


# ------------------------------------------------------------------------------------------------ correction form
def correction_form(points, dirn, start_edge=None):
    """Form of a counter-move from its swing prices points = [start, A end, B end, ...] (alternating; the first leg runs in dirn,
    the counter direction: −1 = a down correction in an uptrend). start_edge = the start swing candle's body edge (C-13: B "back to
    A's start" = B reaches the start candle's area, wick to body); None ⇒ the start price itself. Comparison only; never a forecast."""
    x = [float(p) for p in points]
    n = len(x) - 1
    out = {"legs": max(n, 0), "dir": int(dirn)}
    if n < 1:
        return {**out, "form": None, "why": "no counter leg yet"}
    beyond = lambda a, b: (a - b) * dirn > 0                               # noqa: E731 — a is beyond b in the counter direction
    if n == 1:
        return {**out, "form": "one leg (A)", "why": "A running / done, no B yet"}
    edge = x[0] if start_edge is None else float(start_edge)
    b_back = (x[2] - edge) * dirn <= 0                                     # B came back to A's start (its candle's area) or past it
    if n == 2:
        return {**out, "form": "A–B", "why": "B back to A's start" if b_back else "B short of A's start"}
    if n == 3:
        if b_back:
            return {**out, "form": "flat", "why": "three legs, B back to A's start" + (", C beyond A's end" if beyond(x[3], x[1])
                                                                                        else ", C short of A's end")}
        if beyond(x[3], x[1]):
            return {**out, "form": "zigzag (ABC)", "why": "three legs, B short of A's start, C beyond A's end"}
    ext = x[0::2]                                                          # the trend-side swings (start, B, D, ...)
    cnt = x[1::2]                                                          # the counter-side swings (A, C, E, ...)
    step_cnt = all(beyond(cnt[k + 1], cnt[k]) for k in range(len(cnt) - 1))
    step_ext = all(beyond(ext[k + 1], ext[k]) for k in range(len(ext) - 1))
    shrink_cnt = all(beyond(cnt[k], cnt[k + 1]) for k in range(len(cnt) - 1))  # counter side retreating (contracting)
    if n == 3:
        if shrink_cnt and step_ext:
            return {**out, "form": "contracting (triangle-like so far)", "why": "three legs, C short of A's end, B short of A's start"}
        return {**out, "form": "complex", "why": "three legs, neither zigzag nor flat"}
    if step_ext and shrink_cnt:
        return {**out, "form": "triangle (contracting)", "why": f"{n} legs: highs falling and lows rising" if dirn < 0 else
                f"{n} legs: lows rising and highs falling"}
    expand_ext = all(beyond(ext[k], ext[k + 1]) for k in range(len(ext) - 1))
    if expand_ext and step_cnt:
        return {**out, "form": "triangle (expanding)", "why": f"{n} legs: each swing beyond the previous one on both sides"}
    if step_cnt and step_ext:
        return {**out, "form": "channel", "why": f"{n} legs stepping {'down' if dirn < 0 else 'up'} on both sides"}
    return {**out, "form": "complex", "why": f"{n} legs, no zigzag / flat / triangle / channel shape"}


# ------------------------------------------------------------------------------------------------ legs of one timeframe
def legs_of(ext, n):
    """Legs between consecutive swings (complete) + the leg running from the last swing to the last closed bar n − 1."""
    out = []
    for a, b in zip(ext, ext[1:]):
        out.append({"i0": int(a.bar), "i1": int(b.bar), "dir": 1 if b.kind == "H" else -1, "p0": float(a.price), "p1": float(b.price),
                    "from": a, "to": b, "complete": True})
    if ext and n - 1 > ext[-1].bar:
        last = ext[-1]
        out.append({"i0": int(last.bar), "i1": int(n - 1), "dir": -1 if last.kind == "H" else 1, "p0": float(last.price), "p1": None,
                    "from": last, "to": None, "complete": False})
    return out


def _running_extreme(F, i0, n, dirn):
    lo = i0 + 1
    if n - 1 < lo:
        return None, None
    arr = np.asarray(F["l" if dirn < 0 else "h"], float)[lo:n]
    k = int(np.argmin(arr) if dirn < 0 else np.argmax(arr))
    return float(arr[k]), lo + k


def read_tf(V, t, tf):
    """§2B for one timeframe at 15M bar t: the legs of the structure window (from the older of the last two highs / lows on) with their
    comparison verdicts, the running correction's form (if the TF state is "correction in progress") and the last completed counter
    leg's form."""
    F = MS.frame(V, t, tf)
    if F is None or not F["n"]:
        return {"tf": tf, "na": "no bars for this timeframe"}
    ext, inn, de, di = MS.swings(V, t, tf)
    n = int(F["n"])
    ext = [p for p in ext if p.bar < n]
    legs = legs_of(ext, n)
    facts = []
    for g in legs:
        f = leg_facts(F, g["i0"], g["i1"], g["dir"])
        if f is not None and not g["complete"]:
            g["p1"], _ = _running_extreme(F, g["i0"], n, g["dir"])
        facts.append(f)
    hs = [p for p in ext if p.kind == "H"][-2:]
    ls = [p for p in ext if p.kind == "L"][-2:]
    w0 = min(p.bar for p in hs[:1] + ls[:1]) if hs and ls else (ext[0].bar if ext else 0)
    rows = []
    for k, g in enumerate(legs):
        if g["i0"] < w0:
            continue
        nb = [facts[k - 1] if k > 0 else None, facts[k + 1] if k + 1 < len(facts) else None]
        cmp_ = compare(facts[k], nb)
        rows.append({"from_ts": str(g["from"].ts), "to_ts": None if g["to"] is None else str(g["to"].ts),
                     "t0": MS._ts_of(F, g["i0"]), "t1": MS._ts_of(F, g["i1"]), "p0": round(g["p0"], 2),
                     "p1": None if g["p1"] is None else round(float(g["p1"]), 2), "dir": "up" if g["dir"] > 0 else "down",
                     "complete": g["complete"], "facts": None if facts[k] is None else {
                         kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in facts[k].items()},
                     **cmp_, "next_so_far": bool(k + 1 < len(legs) and not legs[k + 1]["complete"])})
    st = MS._tf_state(V, t, tf)
    trend_dir = st["side"]
    cur = last = None
    if trend_dir and ext:
        cur = _current_correction(F, ext, inn, n, trend_dir, tf, V, t) if st["state"] == MS.CORR_S else None
        last = _last_correction(F, ext, inn, trend_dir, tf, V, t)
    return {"tf": tf, "degree": de, "internal_degree": di, "state": st["state"], "legs": rows, "correction": cur, "last_correction": last,
            "volume": "FUT volume per bar" if F.get("v") is not None else "NA (no volume for this timeframe)"}


def _inner(inn, a, b, tf, V, t):
    """Internal swings strictly after swing a and before swing b (b None ⇒ up to t). Swings2 swings are ordered by their 15M bar; the
    W internal swings are Daily bars ⇒ ordered by date (after a's week, up to b's week)."""
    if tf != "W":
        return [p for p in inn if p.order > a.order and (b is None or p.order < b.order)]
    import pandas as pd
    wk0 = pd.Timestamp(a.ts).to_period("W-FRI")
    wk1 = None if b is None else pd.Timestamp(b.ts).to_period("W-FRI")
    return [p for p in inn if wk0 < pd.Timestamp(p.ts).to_period("W-FRI") and (wk1 is None or pd.Timestamp(p.ts).to_period("W-FRI") <= wk1)]


def _points(start, inner, cdir):
    """Alternating counter-move points from start: drop internal swings until the first one in the counter direction, then keep
    alternation (the more extreme of a repeated kind). Returns (prices, kinds, the swing object behind each point)."""
    first = "L" if cdir < 0 else "H"
    pts, kinds, objs = [float(start.price)], [start.kind], [start]
    for p in inner:
        if len(pts) == 1 and p.kind != first:
            continue
        if kinds[-1] == p.kind:
            if (p.price - pts[-1]) * (1 if p.kind == "H" else -1) > 0:
                pts[-1], objs[-1] = float(p.price), p
            continue
        pts.append(float(p.price))
        kinds.append(p.kind)
        objs.append(p)
    return pts, kinds, objs


def _edge(F, bar, kind):
    """C-13: the far edge of a swing candle's body (a high's body top / a low's body bottom) — "reached its area"."""
    o, c = float(F["o"][bar]), float(F["c"][bar])
    return max(o, c) if kind == "H" else min(o, c)


def _current_correction(F, ext, inn, n, trend_dir, tf, V, t):
    """The running counter-move: from the trend-direction extreme (the last external swing of that kind), its internal swings, then the
    running extreme after the last swing (bars closed at t)."""
    ek = "H" if trend_dir > 0 else "L"
    start = next((p for p in reversed(ext) if p.kind == ek), None)
    if start is None:
        return None
    cdir = -trend_dir
    inner = _inner(inn, start, None, tf, V, t)
    pts, kinds, objs = _points(start, inner, cdir)
    run_dir = -1 if kinds[-1] == "H" else 1                                # the move after the last swing
    if len(objs) > 1 and tf == "W":                                        # W internal swings are Daily bars
        Fd = MS.frame(V, t, "D")
        px, _ = _running_extreme(Fd, objs[-1].bar, Fd["n"], run_dir)
    else:
        px, _ = _running_extreme(F, objs[-1].bar, n, run_dir)
    if px is not None and px != pts[-1]:                                   # the leg after the last swing, so far
        pts.append(px)
    form = correction_form(pts, cdir, start_edge=_edge(F, start.bar, start.kind))
    return {**form, "from_ts": str(start.ts), "from": round(float(start.price), 2), "points": [round(p, 2) for p in pts],
            "running": True}


def _last_correction(F, ext, inn, trend_dir, tf, V, t):
    """The last COMPLETED counter leg: from the trend-direction swing before the newest counter swing to that counter swing."""
    ek = "H" if trend_dir > 0 else "L"
    end = next((p for p in reversed(ext) if p.kind != ek), None)
    if end is None:
        return None
    start = next((p for p in reversed(ext) if p.kind == ek and p.bar < end.bar), None)
    if start is None:
        return None
    inner = _inner(inn, start, end, tf, V, t)
    pts, kinds, _ = _points(start, inner, -trend_dir)
    if kinds[-1] == end.kind:
        if (end.price - pts[-1]) * (1 if end.kind == "H" else -1) >= 0:
            pts[-1] = float(end.price)
    else:
        pts.append(float(end.price))
    form = correction_form(pts, -trend_dir, start_edge=_edge(F, start.bar, start.kind))
    return {**form, "from_ts": str(start.ts), "to_ts": str(end.ts), "from": round(float(start.price), 2),
            "to": round(float(end.price), 2), "points": [round(p, 2) for p in pts], "running": False}


# ------------------------------------------------------------------------------------------------ public API
def read_legs_compare(V, t, d=None, tfs=MS.TFS):
    """§2B for every timeframe at 15M bar t. d is accepted for the common API shape (the reading itself has no side). Evidence only."""
    out = {}
    for tf in tfs:
        try:
            out[tf] = read_tf(V, int(t), tf)
        except Exception as exc:                                           # noqa: BLE001 — a missing source ⇒ NA, never a silent pass
            out[tf] = {"tf": tf, "na": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return {"t": int(t), "tfs": out, "evidence_only": True}


def evidence(read):
    """Short evidence lines: the running leg's verdict and the running / last correction form per timeframe."""
    lines = []
    for tf, x in read["tfs"].items():
        if x.get("na") or not x.get("legs"):
            continue
        g = x["legs"][-1]
        lines.append(f"{tf} {'running' if not g['complete'] else 'last'} {g['dir']} leg: {g['verdict']}"
                     + (f" ({g['why']})" if g.get("why") else ""))
        c = x.get("correction") or x.get("last_correction")
        if c and c.get("form"):
            lines.append(f"{tf} {'correction so far' if c.get('running') else 'last correction'}: {c['form']} ({c['why']})")
    return lines


def draw_objects(V, t, d=None, read=None, tfs=MS.TFS):
    """Chart objects (T8): one per leg (label impulse / correction / mixed) and one per correction form."""
    read = read or read_legs_compare(V, t, d, tfs)
    out = []
    for tf, x in read["tfs"].items():
        if x.get("na"):
            continue
        for g in x.get("legs", []):
            out.append({"kind": "leg", "tf": tf, "t0": g["t0"], "t1": g["t1"], "p0": g["p0"], "p1": g["p1"],
                        "label": g["verdict"] + ("" if g["complete"] else " (so far)"), "state": "complete" if g["complete"] else "running",
                        "evidence": g.get("why")})
        for key in ("correction", "last_correction"):
            c = x.get(key)
            if c and c.get("form"):
                out.append({"kind": "correction_form", "tf": tf, "t0": c.get("from_ts"), "t1": c.get("to_ts"),
                            "p0": c.get("from"), "p1": c.get("to", c["points"][-1] if c.get("points") else None),
                            "label": c["form"], "state": "running" if c.get("running") else "complete", "evidence": c["why"]})
    return out
