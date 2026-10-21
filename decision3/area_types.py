"""decision3/area_types.py — PA standard §2C (track T2): the BASE TYPE of every area and how strongly price LEFT it. Evidence only.

Base type (C.1) — read from the area's own base candles and the legs on either side of them, by comparison only:
  • the base = the area's own candle(s) (birth a: the swing candle; b: the BOS origin base 1H candle; d: the two equal swings; Daily /
    Weekly bands: their Daily / Weekly swing candle), extended to every adjoining bar that still trades inside the band;
  • the leg IN = where the bar just before the base lies: wholly above the band ⇒ price DROPPED into it (D), wholly below ⇒ RALLIED (R);
  • the leg OUT = where the first bar after the base lies: above ⇒ rally out (R), below ⇒ drop out (D);
  • RBD / DBR = reversal bases (supply / demand), RBR / DBD = continuation bases (demand / supply). Still inside the base at t ⇒ the
    out-leg is not known yet ("RB?").
  • A FLIPPED area (KB K4 role reversal) also gets `flip_base`: its leg in = the break leg (broken upward ⇒ R), its base = the latest
    retest after the flip, its leg out = how price left that retest (old supply broken up, retested, rallied ⇒ RBR).
Departure strength (C.5) — the departure leg = from the base to the first finest-degree swing beyond it (still running ⇒ to the running
extreme, `complete` False). Compared with the APPROACH leg (the leg in, from the last finest swing beyond the band on that side) and
with the NEXT leg (from the departure's end to the next opposite swing): pace (travel per bar), mean body, body overlap (less = more
one-sided) and FUT volume (when known): `strength` "strong" = the departure beats the approach on more measures than it loses,
"weak" = the reverse, "even" = as many each (`unanimous` = one leg won every measure; the next-leg comparison is reported beside
it). Broke structure = a close beyond the last confirmed structure swing (D2 on 15M; the Daily / Weekly swing on HTF) that existed
before the departure, before price came back into the base (`internal_bos`: the same with the finest swings). An
imbalance (FVG) left by the departure is listed too (confluence_pa.scan_fvgs).
Never a gate, never a score: `read_area_types` returns facts + a one-line evidence wording per area; `draw_objects` the chart objects.
Bars ≤ t only (swings confirmed by t). `levels.Levels` is only read.
"""
import numpy as np

from . import flip as FL
from . import levels as LV
from . import pa_frames as PF

REVERSAL, CONTINUATION = "reversal", "continuation"
NAME = {"RBD": "rally-base-drop", "DBR": "drop-base-rally", "RBR": "rally-base-rally", "DBD": "drop-base-drop"}


def _same(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) < 1e-9


def _seed(V, L, t, frames):
    """(frame, s0, s1, why) — the area's own base candle(s) on its own frame; frame None ⇒ why."""
    lv = V.levels
    birth = L.births[0] if L.births else None
    kind = "H" if L.role0 == LV.RES else "L"
    if birth == "a:D2":
        ps = [p for p in lv.piv if p.confirm_bar == L.born_bar and p.kind == kind and _same(p.price, L.anchor)]
        if ps:
            return frames["15M"], ps[0].bar, ps[0].bar, None
    elif birth == "b":
        for bar, d, origin in lv.bos:
            if bar == L.born_bar and _same(origin.price, L.anchor):
                jb = lv._base(d, origin, bar)                                  # read-only: the same base candle the level was born from
                if jb is not None:
                    ix = np.flatnonzero((lv.h1_of == jb[0]) & (np.arange(lv.n) <= bar))
                    if len(ix):
                        return frames["15M"], int(ix[0]), int(ix[-1]), None
    elif birth == "d":
        ps = sorted((p for p in lv.piv if p.kind == kind), key=lambda p: p.bar)
        for a, b in zip(ps[:-1], ps[1:]):
            if max(a.confirm_bar, b.confirm_bar) == L.born_bar and _same((a.price + b.price) / 2, L.anchor):
                return frames["15M"], a.bar, b.bar, None
    elif birth in ("a:D", "a:D-prior", "a:W-prior"):
        F = frames["W" if birth == "a:W-prior" else "D"]
        if F is None:
            return None, None, None, "Daily / Weekly candles not given to the engine"
        ps = [p for p in F.ext if _same(p.price, L.anchor) and (p.kind == kind or birth != "a:D")]   # prior: role = side of price
        if ps:
            return F, ps[-1].bar, ps[-1].bar, None
    return None, None, None, f"base candle of birth {birth!r} not found"


def _approach_start(F, b0, lo, hi, s_in):
    """Start of the leg in: the latest finest swing before the base lying beyond the band on the side price came from; none ⇒ the
    extreme of the run of bars on that side just before the base."""
    kind = "H" if s_in > 0 else "L"
    xs = [p for p in F.fine if p.bar < b0 and p.kind == kind and ((p.price > hi) if s_in > 0 else (p.price < lo))]
    if xs:
        return int(max(xs, key=lambda p: p.bar).bar)
    i = b0 - 1
    while i - 1 >= 0 and PF.side(F, i - 1, lo, hi) == s_in:
        i -= 1
    seg = np.arange(i, b0)
    return int(seg[np.argmax(F.H[seg])] if s_in > 0 else seg[np.argmin(F.L[seg])])


def read_base(F, lo, hi, s0, s1):
    """Base type + departure facts of the band [lo, hi] whose own candles are s0 … s1 on frame F (bars ≤ F.last)."""
    b0, b1 = PF.span(F, s0, s1, lo, hi)
    s_in = PF.side(F, b0 - 1, lo, hi) if b0 >= 1 else 0
    s_out = PF.side(F, b1 + 1, lo, hi) if b1 + 1 <= F.last else 0
    leg_in = {1: "D", -1: "R"}.get(s_in)
    leg_out = {1: "R", -1: "D"}.get(s_out)
    base = {"tf": F.tf, "from_bar": int(b0), "to_bar": int(b1), "from_ts": F.stamp(b0), "to_ts": F.stamp(b1), "leg_in": leg_in,
            "leg_out": leg_out, "type": None, "family": None}
    if leg_in and leg_out:
        base["type"] = f"{leg_in}B{leg_out}"
        base["family"] = REVERSAL if leg_in != leg_out else CONTINUATION
        base["why"] = f"{NAME[base['type']]}: price {'dropped' if leg_in == 'D' else 'rallied'} into the base and " \
                      f"{'rallied' if leg_out == 'R' else 'dropped'} out of it"
    else:
        base["type_partial"] = f"{leg_in or '?'}B{leg_out or '?'}"
        base["why"] = "no bar before the base in the data" if not leg_in else "price is still inside the base (no leg out yet)"
    dep = {"strength": None, "vs_approach": None, "vs_next": None, "approach": None, "leg": None, "next": None, "complete": False,
           "bos": None, "internal_bos": None, "returned_at": None, "fvg": []}
    if leg_in:
        a0 = _approach_start(F, b0, lo, hi, s_in)
        dep["approach"] = PF.leg_facts(F, a0, b0 - 1)
    if not leg_out:
        return base, dep
    up = s_out > 0
    ret = next((i for i in range(b1 + 1, F.last + 1) if PF.overlaps(F, i, lo, hi)), None)
    stop = (ret - 1) if ret is not None else F.last
    dep["returned_at"] = F.stamp(ret)
    ends = [p for p in F.fine if p.kind == ("H" if up else "L") and b1 < p.bar <= stop]
    if ends:
        e = min(ends, key=lambda p: p.bar).bar
        dep["complete"] = True
    else:
        seg = np.arange(b1 + 1, stop + 1)
        e = int(seg[np.argmax(F.H[seg])] if up else seg[np.argmin(F.L[seg])])
    dep["leg"] = PF.leg_facts(F, b1 + 1, e)
    if dep["complete"]:
        nx = [p for p in F.fine if p.kind == ("L" if up else "H") and p.bar > e]
        if nx:
            dep["next"] = PF.leg_facts(F, e + 1, min(nx, key=lambda p: p.bar).bar)
    dep["vs_approach"] = PF.compare_legs(dep["leg"], dep["approach"])
    dep["vs_next"] = PF.compare_legs(dep["leg"], dep["next"]) if dep["next"] else None
    dep["strength"] = {"stronger": "strong", "weaker": "weak", "even": "even"}.get(dep["vs_approach"]["verdict"])
    dep["bos"] = PF.structure_break(F, F.ext, b1 + 1, stop, up, b1)
    dep["internal_bos"] = PF.structure_break(F, F.fine, b1 + 1, stop, up, b1)
    from . import confluence_pa as CP
    dep["fvg"] = [g for g in CP.scan_fvgs(F, b1 + 1, e + 1) if g["dir"] == (1 if up else -1)]
    return base, dep


def _flip_base(F, L, t, lo, hi, fv):
    """KB K4 role reversal: leg in = the break leg, base = the latest retest after the flip, leg out = how price left that retest."""
    tf = fv.get("flipped_at")
    if tf is None:
        return None
    leg_in = "R" if (fv.get("break_dir") or 0) > 0 else "D"
    tests = [b for b, k, _ in L.events if k == "test" and tf <= b <= t]
    if not tests:
        return {"type": None, "type_partial": f"{leg_in}B?", "leg_in": leg_in, "leg_out": None, "why": "not retested since the flip"}
    base, dep = read_base(F, lo, hi, tests[-1], tests[-1])
    out = base["leg_out"]
    res = {"leg_in": leg_in, "leg_out": out, "from_bar": base["from_bar"], "to_bar": base["to_bar"], "from_ts": base["from_ts"],
           "to_ts": base["to_ts"], "type": None, "departure": dep}
    if out:
        res["type"] = f"{leg_in}B{out}"
        res["family"] = REVERSAL if leg_in != out else CONTINUATION
        res["why"] = f"role reversal: broken by a {'rally' if leg_in == 'R' else 'drop'}, retested, then " \
                     f"{'rallied' if out == 'R' else 'dropped'} away ⇒ {NAME[res['type']]}"
    else:
        res["type_partial"] = f"{leg_in}B?"
        res["why"] = "price is still inside the retest"
    return res


def _evidence(x):
    b, d = x["base"], x["departure"]
    born = "supply" if x.get("role0", x["role"]) == LV.RES else "demand"
    now = "supply" if x["role"] == LV.RES else "demand"
    s = born if born == now else f"{now} (born as {born}, flipped)"
    if b.get("type"):
        s += f" · base {b['type']} ({b['family']}: {NAME[b['type']]})"
    else:
        s += f" · base {b.get('type_partial') or '?'} ({b.get('why')})"
    va = d.get("vs_approach") or {}
    if d.get("strength") in ("strong", "weak"):
        s += f" · left {d['strength']}ly ({va['verdict']} than the approach" + (" on every measure" if va.get("unanimous") else "") + ")"
    elif d.get("strength") == "even":
        s += " · left about as strongly as it came in"
    vn = d.get("vs_next") or {}
    if vn.get("verdict") in ("stronger", "weaker"):
        s += f", {vn['verdict']} than the next leg"
    if d.get("bos"):
        s += f" · broke structure (close beyond swing {d['bos']['swing']:,.2f})"
    elif b.get("leg_out"):
        s += " · did not break structure" + (" (internal structure only)" if d.get("internal_bos") else "")
    if d.get("fvg"):
        s += f" · left {len(d['fvg'])} imbalance(s)"
    fb = x.get("flip_base")
    if fb and fb.get("type"):
        s += f" · after the flip: {fb['type']} ({fb['family']})"
    elif fb:
        s += f" · after the flip: {fb.get('type_partial')} ({fb.get('why')})"
    return s


def read_area_types(V, t, d=None):
    """Every area alive at t (`levels.snapshot`): base type (C.1), departure strength + broke structure (C.5), flip base for FLIPPED
    areas. d (trade side, ±1) only marks `trade_side`; nothing is filtered or decided. Bars ≤ t only."""
    lv = V.levels
    frames = {"15M": PF.frame_15m(lv, t), "D": PF.frame_htf(V, t, "D"), "W": PF.frame_htf(V, t, "W")}
    out = []
    for x in lv.snapshot(t):
        L = lv.L[x["id"]]
        F, s0, s1, why = _seed(V, L, t, frames)
        item = {"id": x["id"], "tf": x["tf"], "role": x["role"], "role0": L.role0, "lo": x["lo"], "hi": x["hi"], "state": x["state"],
                "births": x["births"], "trade_location": x.get("trade_location"),
                "trade_side": None if d is None else ((x["role"] == LV.SUP) == (d > 0))}
        if F is None or F.last < 0 or s0 > F.last:
            item["base"] = {"type": None, "why": why or "base candle not known at t"}
            item["departure"] = {"strength": None}
        else:
            base, dep = read_base(F, x["lo"], x["hi"], s0, s1)
            if base.get("leg_out"):
                base["consistent_with_role"] = (base["leg_out"] == "D") == (L.role0 == LV.RES)
            item["base"], item["departure"] = base, dep
        if x.get("flipped_at") is not None and x.get("state") != FL.DEAD:   # retests are 15M events ⇒ read on the 15M frame
            item["flip_base"] = _flip_base(frames["15M"], L, t, x["lo"], x["hi"], x)
        item["evidence"] = _evidence(item)
        out.append(item)
    return out


def draw_objects(V, t, items=None):
    """Chart objects (track T8 schema): one box per area from its base to t, labelled with base type, departure and structure break."""
    items = read_area_types(V, t) if items is None else items
    end = str(V.levels.ts.iloc[int(t)])
    objs = []
    for x in items:
        b = x["base"]
        label = b.get("type") or b.get("type_partial") or "base ?"
        if x["departure"].get("strength"):
            label += f" · {x['departure']['strength']}"
        if x["departure"].get("bos"):
            label += " · BOS"
        fb = x.get("flip_base")
        if fb and fb.get("type"):
            label += f" · flip {fb['type']}"
        objs.append({"kind": "area_base", "tf": x["tf"], "t0": b.get("from_ts") or end, "t1": end, "p0": x["lo"], "p1": x["hi"],
                     "label": label, "state": x["state"], "evidence": x["evidence"]})
    return objs
