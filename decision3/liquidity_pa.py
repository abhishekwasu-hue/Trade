"""decision3/liquidity_pa.py — PA standard §2D (track T2): obvious swing extremes (D.2) and inducement (D.5). Evidence only.

Obvious swing extremes (resting liquidity) — every confirmed structure swing (D2 on 15M; Daily swings) whose own extreme has NOT been
traded beyond since it formed: stops rest beyond it (buy-side above an untaken high, sell-side below an untaken low). Once a later bar
trades beyond it, it is `taken` (by a wick that closed back = "wick", or by a close beyond = "close"); a taken extreme is no longer
resting. Equal highs / lows (liquidity.pools, method §3 "equal") are tagged. On each side the outermost resting extreme is `outer`
(the external liquidity of the visible structure) and the one closest to price `nearest`.
Inducement — for every area ahead of price (a supply not below price / a demand not above it, not BROKEN): the finest-degree
(D1) extreme formed on the APPROACH to the area — after the extreme of the move away from it (since its base or its last visit) —
lying between that extreme and the area (a minor high below a supply, a minor low above a demand), the one closest to the area.
State: none (no minor extreme on the approach yet) / resting (not taken) / taken (price traded beyond it; `area_reached` = price reached the area at or after that; a
taken inducement followed by the area visit = "inducement taken first"). Minor = not also a D2 swing (else `degree` "structure").
Nothing here gates, scores or changes `liquidity.pools` / `sweeps_and_traps`; bars ≤ t only (swings confirmed by t).
"""
import numpy as np

from . import flip as FL
from . import levels as LV
from . import liquidity as LQ
from . import pa_frames as PF


def _taken(F, p, upto):
    """First bar after the swing (≤ upto) trading beyond its extreme ⇒ (bar, "wick" | "close") or (None, None)."""
    up = p.kind == "H"
    j = PF.first_beyond(F, int(p.bar) + 1, upto, float(p.price), up)
    if j is None:
        return None, None
    closed_beyond = (F.C[j] > p.price) if up else (F.C[j] < p.price)
    return j, ("close" if closed_beyond else "wick")


def obvious_extremes(V, t, include_taken=False):
    """Structure swing extremes known at t (15M D2 + Daily swings): resting ones (and taken ones when include_taken)."""
    lv = V.levels
    F = PF.frame_15m(lv, t)
    c = float(lv.A["close"][t])
    eq = set()
    for kind in ("H", "L"):
        ps = sorted((p for p in F.ext if p.kind == kind), key=lambda p: p.bar)
        for p1, p2 in zip(ps[:-1], ps[1:]):
            if LQ._equal(lv.A, p1, p2):
                eq |= {id(p1), id(p2)}
    out = []
    for p in F.ext:
        j, how = _taken(F, p, t)
        if j is not None and not include_taken:
            continue
        out.append({"tf": "15M", "src": "equal" if id(p) in eq else "swing", "degree": "structure", "kind": p.kind,
                    "side": "buy" if p.kind == "H" else "sell", "price": round(float(p.price), 2), "bar": int(p.bar), "ts": F.stamp(p.bar),
                    "state": "resting" if j is None else "taken", "taken_at": F.stamp(j), "taken_bar": j, "taken_by": how})
    D = PF.frame_htf(V, t, "D")
    if D is not None and D.last >= 0:
        today = np.flatnonzero((lv.ts.dt.normalize() > D.ts[D.last].normalize()).to_numpy() & (np.arange(lv.n) <= t))
        for p in D.ext:
            j, how = _taken(D, p, D.last)
            src = "Daily"
            if j is None and len(today):                                    # the session not yet a Daily candle: its 15M bars ≤ t
                seg = lv.A["high"][today] if p.kind == "H" else lv.A["low"][today]
                hit = np.flatnonzero(seg > p.price) if p.kind == "H" else np.flatnonzero(seg < p.price)
                if len(hit):
                    k = int(today[hit[0]])
                    cb = (lv.A["close"][k] > p.price) if p.kind == "H" else (lv.A["close"][k] < p.price)
                    j, how, src = k, ("close" if cb else "wick"), "Daily (taken intraday)"
            if j is not None and not include_taken:
                continue
            out.append({"tf": "D", "src": src, "degree": "Daily", "kind": p.kind, "side": "buy" if p.kind == "H" else "sell",
                        "price": round(float(p.price), 2), "bar": int(p.bar), "ts": D.stamp(p.bar),
                        "state": "resting" if j is None else "taken", "taken_at": None if j is None else
                        (str(lv.ts.iloc[j]) if src.endswith("intraday)") else D.stamp(j)), "taken_by": how})
    for side, better in (("buy", max), ("sell", min)):
        for tf in ("15M", "D"):
            rs = [x for x in out if x["side"] == side and x["tf"] == tf and x["state"] == "resting"]
            if not rs:
                continue
            o = better(rs, key=lambda x: x["price"])
            o["outer"] = True
            ahead = [x for x in rs if (x["price"] >= c if side == "buy" else x["price"] <= c)]
            if ahead:
                n = min(ahead, key=lambda x: abs(x["price"] - c))
                n["nearest"] = True
    for x in out:
        x.setdefault("outer", False)
        x.setdefault("nearest", False)
    return out


def inducement(V, t, area, F=None):
    """D.5 for one area (a `levels.snapshot` item) at t. Returns facts + evidence wording (see the module docstring)."""
    lv = V.levels
    F = F or PF.frame_15m(lv, t)
    lo, hi = float(area["lo"]), float(area["hi"])
    sup = area["role"] == LV.SUP
    res = {"area_id": area["id"], "role": area["role"], "state": "none", "minor": None, "area_reached": False, "taken_first": None}
    born = int(area.get("born_bar") or 0)
    ins = [i for i in range(born, t + 1) if PF.overlaps(F, i, lo, hi)]
    if ins and ins[-1] == t:                                                # inside now: the current visit started at its run's start
        v = t
        while v - 1 >= born and PF.overlaps(F, v - 1, lo, hi):
            v -= 1
        before = [i for i in ins if i < v]
        a0, end, reached = (before[-1] if before else born), v - 1, v
    else:
        a0, end, reached = (ins[-1] if ins else born), t, None
    if end <= a0:
        res["why"] = "no approach yet"
        return res
    seg = np.arange(a0 + 1, end + 1)
    away = int(seg[np.argmin(F.L[seg])] if not sup else seg[np.argmax(F.H[seg])])   # the extreme of the move away from the area
    kind = "L" if sup else "H"                                              # supply ⇒ a minor HIGH below it; demand ⇒ a minor LOW above
    cand = [p for p in F.fine if p.kind == kind and away < p.bar <= end and (p.price < lo if kind == "H" else p.price > hi)]
    if not cand:
        res["why"] = "no minor extreme on the approach yet"
        return res
    p = max(cand, key=lambda q: q.price) if kind == "H" else min(cand, key=lambda q: q.price)   # the one just before the area
    ext = {(q.kind, q.bar) for q in F.ext}
    j, how = _taken(F, p, t)
    res["minor"] = {"kind": p.kind, "price": round(float(p.price), 2), "bar": int(p.bar), "ts": F.stamp(p.bar),
                    "degree": "structure" if (p.kind, p.bar) in ext else "minor", "candidates": len(cand)}
    if j is None:
        res["state"] = "resting"
    else:
        res.update(state="taken", taken_at=F.stamp(j), taken_bar=int(j), taken_by=how)
        later = reached if reached is not None else next((i for i in range(j, t + 1) if PF.overlaps(F, i, lo, hi)), None)
        res["area_reached"] = later is not None and later >= j
        res["taken_first"] = res["area_reached"]
        res["reached_at"] = F.stamp(later) if res["area_reached"] else None
    return res


def _induce_words(x, area):
    role = "supply" if area["role"] == LV.RES else "demand"
    if x["state"] == "none":
        return f"inducement before the {role} {area['lo']:,.0f}–{area['hi']:,.0f}: none ({x.get('why')})"
    m = x["minor"]
    what = f"{m['degree']} {'high' if m['kind'] == 'H' else 'low'} {m['price']:,.2f}"
    if x["state"] == "resting":
        return f"inducement before the {role} {area['lo']:,.0f}–{area['hi']:,.0f}: {what} still resting"
    tail = " ⇒ then the area was reached (inducement taken first)" if x["taken_first"] else " (area not reached yet)"
    return f"inducement before the {role} {area['lo']:,.0f}–{area['hi']:,.0f}: {what} taken by a {x['taken_by']}{tail}"


def read_liquidity(V, t, d=None):
    """D.2 + D.5 at t: {"obvious": [...], "inducement": [...]}. d (trade side ±1) only marks `trade_side`. Bars ≤ t only."""
    lv = V.levels
    F = PF.frame_15m(lv, t)
    obv = obvious_extremes(V, t)
    for x in obv:
        x["evidence"] = (f"{'buy' if x['side'] == 'buy' else 'sell'}-side liquidity resting {'above' if x['kind'] == 'H' else 'below'} "
                         f"the {x['degree']} swing {'high' if x['kind'] == 'H' else 'low'} {x['price']:,.2f}"
                         + (" (equal)" if x["src"] == "equal" else "") + (" — outer" if x["outer"] else "")
                         + (" — nearest" if x["nearest"] else ""))
    ind = []
    for a in lv.snapshot(t):
        if a["state"] in FL.NOT_PLACE or (a["role"] == LV.RES and a["below"]) or (a["role"] == LV.SUP and a["above"]):
            continue
        x = inducement(V, t, a, F)
        x.update(lo=a["lo"], hi=a["hi"], tf=a["tf"], trade_side=None if d is None else ((a["role"] == LV.SUP) == (d > 0)))
        x["evidence"] = _induce_words(x, a)
        ind.append(x)
    return {"obvious": obv, "inducement": ind}


def draw_objects(V, t, read=None):
    """Chart objects (track T8 schema): resting obvious extremes (a line from the swing to t) and each inducement (a line from the
    minor extreme to its taking bar / t)."""
    r = read_liquidity(V, t) if read is None else read
    end = str(V.levels.ts.iloc[int(t)])
    objs = []
    for x in r["obvious"]:
        lab = f"{'BSL' if x['side'] == 'buy' else 'SSL'} {x['degree']}" + (" EQ" if x["src"] == "equal" else "") + \
              (" outer" if x["outer"] else "")
        objs.append({"kind": "liquidity_extreme", "tf": x["tf"], "t0": x["ts"], "t1": end, "p0": x["price"], "p1": x["price"],
                     "label": lab, "state": x["state"], "evidence": x["evidence"]})
    for x in r["inducement"]:
        if not x.get("minor"):
            continue
        m = x["minor"]
        objs.append({"kind": "inducement", "tf": "15M", "t0": m["ts"], "t1": x.get("taken_at") or end, "p0": m["price"],
                     "p1": m["price"], "label": "IDM " + ("taken" if x["state"] == "taken" else "resting"), "state": x["state"],
                     "evidence": x["evidence"]})
    return objs
