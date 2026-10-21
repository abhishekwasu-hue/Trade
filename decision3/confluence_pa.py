"""decision3/confluence_pa.py — PA standard §2F (track T2): confluence levels. Evidence only.

F.1 HTF horizontal levels — the earlier swing extremes of the higher timeframes, as the engine already builds them (`levels.Levels`
    births a:D / a:D-prior / a:W-prior: each its own Daily / Weekly band, Abhi Z-1u) plus the Daily swing extremes still resting
    (liquidity_pa). Read only; nothing is re-built.
F.2 Imbalance (fair value gap) — three candles where the third does not trade back to the first: bullish = low[i] > high[i−2] with a
    bullish middle candle (gap = high[i−2] … low[i]); bearish = the mirror. State at t, from the later bars only: open (no later bar
    traded into the gap), partly (traded into it, not through it — `remaining` = the part still untraded), filled (a later bar traded
    through it). Read on the 15M bars ≤ t and the 1H candles completed by t. "Left by an impulse": `middle_largest` = the middle
    candle's body is larger than both neighbours' (comparison), `leg_broke_structure` (15M) = the finest-degree leg holding it closed
    beyond the last confirmed D2 swing.
F.3 Fibonacci retracement — ONLY as a confluence label (Abhi's rule, KB K7): the last impulse that broke structure (the newest D2 BOS:
    from its origin swing to the extreme confirmed swing after it, both confirmed pivots). Its retracement levels (`pa_fib_ratios`, the
    declared exception — the ratios ARE the definition) are reported only where a level lands INSIDE an alive area's band (a trade
    location of `levels.snapshot`: not BROKEN / DEAD, not a Weekly context band, not a Daily band under a 1H zone) or inside a resting liquidity extreme's own swing-candle band. A level landing on nothing is never output; no Fib when the
    impulse's end is not confirmed yet, when price has made a new extreme beyond it since, or when price has gone back beyond its origin.
F.4 Confluence — per area one list of the pieces at the same place (HTF band overlap from `levels.snapshot`, imbalance, Fib level,
    resting liquidity) and the label "confluence: …" (no score, no count gate). The existing `levels.confluence_label` is unchanged.
Bars ≤ t only (swings confirmed by t). Never a gate.
"""
import numpy as np

from . import flip as FL
from . import levels as LV
from . import liquidity_pa as LP
from . import pa_frames as PF
from . import settings as S3


def scan_fvgs(F, i_from=2, i_to=None):
    """Imbalances whose third candle is in i_from … i_to (≤ F.last), with their state at F.last."""
    i_to = F.last if i_to is None else min(i_to, F.last)
    out = []
    for i in range(max(2, int(i_from)), i_to + 1):
        m = i - 1
        if F.L[i] > F.H[i - 2] and F.C[m] > F.O[m]:
            d, lo, hi = 1, float(F.H[i - 2]), float(F.L[i])
        elif F.H[i] < F.L[i - 2] and F.C[m] < F.O[m]:
            d, lo, hi = -1, float(F.H[i]), float(F.L[i - 2])
        else:
            continue
        g = {"tf": F.tf, "dir": d, "lo": round(lo, 2), "hi": round(hi, 2), "bar": int(m), "ts": F.stamp(m), "third_ts": F.stamp(i),
             "state": "open", "remaining": (round(lo, 2), round(hi, 2)), "touched_at": None, "filled_at": None}
        body = np.abs(F.C[i - 2:i + 1] - F.O[i - 2:i + 1])
        g["middle_largest"] = bool(body[1] > body[0] and body[1] > body[2])
        if i < F.last:
            seg = F.L[i + 1:F.last + 1] if d > 0 else F.H[i + 1:F.last + 1]
            into = np.flatnonzero(seg < hi) if d > 0 else np.flatnonzero(seg > lo)
            if len(into):
                g["touched_at"] = F.stamp(i + 1 + into[0])
                through = np.flatnonzero(seg <= lo) if d > 0 else np.flatnonzero(seg >= hi)
                if len(through):
                    g["state"], g["filled_at"], g["remaining"] = "filled", F.stamp(i + 1 + through[0]), None
                else:
                    g["state"] = "partly"
                    g["remaining"] = (round(lo, 2), round(float(seg.min()), 2)) if d > 0 else (round(float(seg.max()), 2), round(hi, 2))
        out.append(g)
    return out


def _leg_bos(F, bar, up):
    """15M: the finest-degree leg holding `bar` (from the last opposite finest swing at / before it to the next same-side finest swing,
    or t) closed beyond the last confirmed structure swing formed before the leg."""
    st = [p for p in F.fine if p.kind == ("L" if up else "H") and p.bar <= bar]
    if not st:
        return None
    s0 = max(st, key=lambda p: p.bar).bar
    en = [p for p in F.fine if p.kind == ("H" if up else "L") and p.bar >= bar]
    e = min(en, key=lambda p: p.bar).bar if en else F.last
    return PF.structure_break(F, F.ext, s0 + 1, e, up, s0) is not None


def fvgs(V, t, include_filled=False):
    """F.2 at t: imbalances on 15M (bars ≤ t) and 1H (completed candles), open / partly (and filled when include_filled)."""
    lv = V.levels
    F15 = PF.frame_15m(lv, t)
    out = []
    for F in (F15, PF.frame_1h(lv, t)):
        for g in scan_fvgs(F):
            if g["state"] == "filled" and not include_filled:
                continue
            if F.tf == "15M":
                g["leg_broke_structure"] = _leg_bos(F, g["bar"], g["dir"] > 0)
            out.append(g)
    return out


def _pool_band(V, t, x):
    """The resting extreme's own swing-candle band (wick-to-body, levels._band_swing) on its own timeframe."""
    lv = V.levels
    if x["tf"] == "15M":
        i = x["bar"]
        o, h, lo, c = (float(lv.A[k][i]) for k in ("open", "high", "low", "close"))
    else:
        D = PF.frame_htf(V, t, "D")
        if D is None:
            return None
        i = x["bar"]
        o, h, lo, c = float(D.O[i]), float(D.H[i]), float(D.L[i]), float(D.C[i])
    return LV._band_swing(x["kind"], o, h, lo, c, x["price"], 0.0)


def fib_on_areas(V, t, snap=None, obvious=None):
    """F.3 at t: the retracement levels of the last structure-breaking impulse that land on an area / resting liquidity — nothing
    else. Returns {"impulse": {...} | None, "levels": [{ratio, price, on: [...]}], "why"}."""
    lv = V.levels
    ratios = tuple(V.s.get("pa_fib_ratios", S3.DEFAULTS["pa_fib_ratios"]))
    out = {"impulse": None, "levels": [], "why": None}
    bos = [b for b in lv.bos if b[0] <= t]
    if not bos:
        out["why"] = "no structure break yet"
        return out
    bbar, d, origin = bos[-1]
    up = d > 0
    ends = [p for p in lv.known_pivots(t) if p.kind == ("H" if up else "L") and p.bar > origin.bar]
    if not ends:
        out["why"] = "the impulse's end swing is not confirmed yet"
        return out
    end = max(ends, key=lambda p: p.price) if up else min(ends, key=lambda p: p.price)
    A = lv.A
    after = np.arange(end.bar + 1, t + 1)
    if len(after) and ((A["high"][after].max() > end.price) if up else (A["low"][after].min() < end.price)):
        out["why"] = "price made a new extreme beyond the impulse's end (its swing not confirmed yet)"
        return out
    if len(after) and ((A["low"][after].min() < origin.price) if up else (A["high"][after].max() > origin.price)):
        out["why"] = "price went back beyond the impulse's origin (retracement beyond 100%)"
        return out
    rng = float(end.price - origin.price)
    out["impulse"] = {"dir": int(d), "from_price": round(float(origin.price), 2), "from_ts": str(lv.ts.iloc[int(origin.bar)]),
                      "to_price": round(float(end.price), 2), "to_ts": str(lv.ts.iloc[int(end.bar)]), "bos_ts": str(lv.ts.iloc[int(bbar)])}
    snap = lv.snapshot(t) if snap is None else snap
    obvious = LP.obvious_extremes(V, t) if obvious is None else obvious
    areas = [x for x in snap if x["state"] not in (FL.BROKEN, FL.DEAD) and x.get("trade_location", True)]   # an AREA = a location
    # (Abhi Z-1u: a Weekly band is context only, a Daily band under a 1H zone is that zone's label — a wide context band is no landing)
    pools = []
    for x in obvious:
        if x["state"] == "resting":
            b = _pool_band(V, t, x)
            if b is not None:
                pools.append((x, b))
    for r in ratios:
        px = float(end.price) - float(r) * rng
        on = [{"what": "area", "id": a["id"], "tf": a["tf"], "role": a["role"], "lo": a["lo"], "hi": a["hi"]}
              for a in areas if a["lo"] <= px <= a["hi"]]
        on += [{"what": "liquidity", "tf": x["tf"], "side": x["side"], "price": x["price"], "lo": round(b[0], 2), "hi": round(b[1], 2)}
               for x, b in pools if b[0] <= px <= b[1]]
        if on:
            out["levels"].append({"ratio": float(r), "price": round(px, 2), "on": on})
    if not out["levels"]:
        out["why"] = "no retracement level lands on an area or resting liquidity (Fib is never read alone)"
    return out


def htf_levels(V, t, snap=None, obvious=None):
    """F.1 at t: the engine's own Daily / Weekly bands alive at t + the Daily swing extremes still resting."""
    snap = V.levels.snapshot(t) if snap is None else snap
    obvious = LP.obvious_extremes(V, t) if obvious is None else obvious
    out = []
    for x in snap:
        if x["tf"] in ("D", "W"):
            out.append({"kind": "band", "tf": x["tf"], "id": x["id"], "role": x["role"], "lo": x["lo"], "hi": x["hi"], "state": x["state"],
                        "births": x["births"], "trade_location": x.get("trade_location"),
                        "evidence": f"{LV.TF_WORD[x['tf']]} {'supply' if x['role'] == LV.RES else 'demand'} band "
                                    f"{x['lo']:,.0f}–{x['hi']:,.0f} ({x['state']})"})
    for x in obvious:
        if x["tf"] == "D" and x["state"] == "resting":
            out.append({"kind": "extreme", "tf": "D", "price": x["price"], "side": x["side"], "ts": x["ts"],
                        "evidence": f"Daily swing {'high' if x['kind'] == 'H' else 'low'} {x['price']:,.2f} (not taken)"})
    return out


def _fvg_words(g):
    lo, hi = g["remaining"] or (g["lo"], g["hi"])
    return f"imbalance {g['tf']} {'bullish' if g['dir'] > 0 else 'bearish'} {g['state']} {lo:,.0f}–{hi:,.0f}"


def read_confluence(V, t, d=None):
    """§2F at t: {"htf_levels", "fvg", "fib", "areas": [{id, pieces, label}]}. d only marks `trade_side`. Bars ≤ t only."""
    lv = V.levels
    snap = lv.snapshot(t)
    obvious = LP.obvious_extremes(V, t)
    gaps = fvgs(V, t)
    fib = fib_on_areas(V, t, snap, obvious)
    areas = []
    for a in snap:
        if a["state"] == FL.DEAD:
            continue
        pieces = [{"what": "htf_band", "tf": c["tf"], "lo": c["lo"], "hi": c["hi"],
                   "words": f"{LV.TF_WORD.get(c['tf'], c['tf'])} band {c['lo']:,.0f}–{c['hi']:,.0f}"} for c in a.get("confluence") or []]
        for g in gaps:
            lo, hi = g["remaining"] or (g["lo"], g["hi"])
            if not (hi < a["lo"] or lo > a["hi"]):
                pieces.append({"what": "imbalance", "tf": g["tf"], "lo": lo, "hi": hi, "state": g["state"], "words": _fvg_words(g)})
        for lvl in fib["levels"]:
            if any(o["what"] == "area" and o["id"] == a["id"] for o in lvl["on"]):
                pieces.append({"what": "fib", "ratio": lvl["ratio"], "price": lvl["price"],
                               "words": f"Fib {lvl['ratio'] * 100:g}% {lvl['price']:,.0f} of the last impulse"})
        for x in obvious:                                                   # the area's own swing is not a second piece
            if x["state"] == "resting" and a["lo"] <= x["price"] <= a["hi"] and not (a.get("anchor") is not None
                                                                                  and abs(float(a["anchor"]) - x["price"]) < 0.01):
                pieces.append({"what": "liquidity", "tf": x["tf"], "price": x["price"],
                               "words": f"resting {x['side']}-side liquidity ({x['degree']} swing {x['price']:,.0f})"})
        areas.append({"id": a["id"], "tf": a["tf"], "role": a["role"], "lo": a["lo"], "hi": a["hi"], "state": a["state"],
                      "trade_side": None if d is None else ((a["role"] == LV.SUP) == (d > 0)), "pieces": pieces,
                      "label": ("confluence: " + "; ".join(p["words"] for p in pieces)) if pieces else None})
    return {"htf_levels": htf_levels(V, t, snap, obvious), "fvg": gaps, "fib": fib, "areas": areas}


def draw_objects(V, t, read=None):
    """Chart objects (track T8 schema): imbalance boxes (to their fill / t), Fib levels that land (across the impulse), HTF bands."""
    r = read_confluence(V, t) if read is None else read
    end = str(V.levels.ts.iloc[int(t)])
    objs = []
    for g in r["fvg"]:
        lo, hi = g["remaining"] or (g["lo"], g["hi"])
        objs.append({"kind": "fvg", "tf": g["tf"], "t0": g["ts"], "t1": g["filled_at"] or end, "p0": lo, "p1": hi,
                     "label": f"FVG {g['tf']} {g['state']}", "state": g["state"], "evidence": _fvg_words(g)})
    imp = r["fib"]["impulse"]
    for lvl in r["fib"]["levels"]:
        on = ", ".join(("area " + ("supply" if o["role"] == LV.RES else "demand")) if o["what"] == "area" else f"{o['side']}-side liquidity"
                       for o in lvl["on"])
        objs.append({"kind": "fib_level", "tf": "15M", "t0": imp["from_ts"], "t1": end, "p0": lvl["price"], "p1": lvl["price"],
                     "label": f"Fib {lvl['ratio'] * 100:g}% on {on}", "state": "confluence",
                     "evidence": f"Fib {lvl['ratio'] * 100:g}% of the impulse {imp['from_price']:,.0f}→{imp['to_price']:,.0f} lands on {on}"})
    for x in r["htf_levels"]:
        if x["kind"] == "band":
            objs.append({"kind": "htf_level", "tf": x["tf"], "t0": None, "t1": end, "p0": x["lo"], "p1": x["hi"],
                         "label": f"{LV.TF_WORD[x['tf']]} {'supply' if x['role'] == LV.RES else 'demand'}", "state": x["state"],
                         "evidence": x["evidence"]})
        else:
            objs.append({"kind": "htf_level", "tf": "D", "t0": x["ts"], "t1": end, "p0": x["price"], "p1": x["price"],
                         "label": f"Daily swing {'H' if x['side'] == 'buy' else 'L'}", "state": "resting", "evidence": x["evidence"]})
    return objs
