"""decision3/model_c.py — MODEL C: the counter-trend C leg of a correction against the Daily side (handover T-3, Appendix A; owner-orders
DECISIONS 32; design = docs/reports/model_c/COVERAGE.md). A separate, switchable entry model, default OFF (`model_c = off`: V22.decide
never calls this module and its rows stay byte-identical). It adds NO concept: every piece is an existing reader, read in the minor
direction while the Daily side is the other way (mirror everything for a Daily UP trend):

  C-1 context   the Daily DState read exactly as now (`daily.state_at`; model C needs DState.trend DOWN — Q1: step1's "trend first"
                NEUTRAL is a context line, the Weekly fallback gives no model C) + the Weekly state, recorded on every C entry.
  C-2 / C-3     wave A = the newest 1H CHoCH up (mtf_state's BOS / CHoCH by 15M close on the level_degree D2 swings — a close beyond
                the last 1H lower high) known at t. O = the lowest low between that CHoCH's protected high and the CHoCH bar (Q3: a
                known price, bars ≤ t). HA = the first D2 swing high formed from the CHoCH bar on, read only from its confirm bar. A's
                nature = legs_compare (leg_facts / compare on the 1H candles: A against the Daily-side leg before O and B so far);
                `c_a_nature = impulse` (default) needs the verdict "impulse", `any` = what-if. No CHoCH ⇒ no A ⇒ no model C.
  C-4 B         the pullback from HA; it must read "correction" (B so far against A; "mixed" / NA ⇒ the models wait, Q9). B DIES only by
                a close beyond O AND a swing of the finest structure (`Levels._known0`, the K4 degree, Q4) formed beyond O —
                `trendline._broken_at`, the K4 / K6.5 definition unchanged. One candle beyond O without a swing ⇒ alive (a sweep).
  C-5 entry     the existing entry models E1–E4 (entry_models.Reader / read, unchanged) in the minor direction, with an injected trade
                side (`side_fn`: the C window below) at the C AREAS: Levels.active(t, minor side) ∩ 1H ∩ ACTIVE / TESTED ∩ base (the
                additive Level.base_bar) between O and HA (Q5; a FLIPPED area inside A is not C-a, Q6). Refined base, traded_inside,
                once per model per visit, absorption, H2, entry hours, the data-problem rule: all as they are.
  C-6 window    `c_window = b_only` (default): while B is in progress (A complete, HA confirmed, A / B natures read, alive, no 15M close
                beyond HA). b_and_ha_retest = + the first return to HA (forced for the C-e objects when C-e is on). c_pullbacks
                (what-if) = + C's own pullbacks after the close beyond HA at areas built during C, until a 1H CHoCH back to the Daily
                side. The breakout candle of HA is never an entry (the window closes at the first close beyond HA; C-e reads only the
                RETURN after the C push left HA — never the break, H2).
  C-7 end zone  context only (never a gate, an entry or an exit): the first Daily / Weekly area beyond HA on the trade side, the Daily
                protected origin, the projections B_end + r × (HA − O) for each r in `c_projections` (display ratios, settings only).
  C-8 evidence  context lines only: B per-bar FUT volume against A's (legs_compare facts), hidden RSI divergence (rsi_hidden).
  C-10 text     one story line per entry (`story`), the label "C · E2" (family C, sub-model), `visit_id` "C:<area>@<start>" (the per-visit
                claim stays apart from the Daily side), cluster ids "MC…" / "MCB…".
  C-11 subs     C-a E1–E4 at the C areas · C-b E4 (b) on B's broken 1H line / channel parallel (anchors inside B) · C-c an E4 (a)
                whose sweep extreme lies beyond O (C-c wins over C-a, Q10) · C-d E4 (b) on a broken triangle edge whose swings lie
                inside B (patterns_pa.hook_lines) · C-e the HA area / a broken line lying on it, first return only (E4 (b) while
                BROKEN, E1–E4 once FLIPPED) · C-f a label on a Daily-side entry inside the end zone (never removes or adds one, Q6).
                Each sub-way has its own switch (`model_c_subs`; live: engine3_model_c_<x>_on, default OFF) and its own statistics.
Bars ≤ t only (pivots by confirm bar, the 1H candles when closed). No order, no broker, no AI call; no new execution setting.
"""
import logging

import numpy as np
import pandas as pd

from . import entry_models as EM
from . import flip as FL
from . import legs_compare as LC
from . import settings as S3
from . import trendline as TL

log = logging.getLogger(__name__)

SUBS = S3.MODEL_C_SUBS
WINDOWS = S3.C_WINDOWS
NATURES = ("impulse", "any")
TRIANGLES = ("sym_triangle", "asc_triangle", "desc_triangle")              # C-d: "B contracts into a triangle" (patterns track)
AREA_STATES = (FL.ACTIVE, FL.TESTED)                                       # C-5: fresh or tested only (never broken / flipped / dead)
SUB_NAME = {"C-a": "B-end at an A area", "C-b": "B channel break retest", "C-c": "B sweeps O (expanded flat)",
            "C-d": "B triangle edge retest", "C-e": "HA flip retest", "C-f": "end of C, back to the Daily side"}


# ------------------------------------------------------------------------------------------------ settings
def validate(s):
    """Fail at start (V22.__init__), never a silent switch: unknown values ⇒ ValueError with the allowed ones."""
    if str(s.get("model_c", "off")) not in ("off", "on"):
        raise ValueError(f"decision3 V22: unknown model_c {s.get('model_c')!r} (allowed: off, on)")
    subs = s.get("model_c_subs", SUBS)
    if isinstance(subs, str) or any(x not in SUBS for x in (subs or ())):
        raise ValueError(f"decision3 V22: model_c_subs accepts a list of {', '.join(SUBS)} (got {subs!r})")
    if str(s.get("c_a_nature", "impulse")) not in NATURES:
        raise ValueError(f"decision3 V22: unknown c_a_nature {s.get('c_a_nature')!r} (allowed: {', '.join(NATURES)})")
    if str(s.get("c_window", "b_only")) not in WINDOWS:
        raise ValueError(f"decision3 V22: unknown c_window {s.get('c_window')!r} (allowed: {', '.join(WINDOWS)})")
    pr = s.get("c_projections", (1.0,))
    try:
        ok = not isinstance(pr, str) and all(np.isfinite(float(r)) and float(r) > 0 for r in (pr or ()))
    except (TypeError, ValueError):
        ok = False
    if not ok:
        raise ValueError(f"decision3 V22: c_projections = a list of positive ratios (display only; got {pr!r})")


def is_on(V):
    return str(V.s.get("model_c", "off")) == "on"


def subs_on(V):
    return tuple(x for x in SUBS if x in tuple(V.s.get("model_c_subs", SUBS) or ()))


def _memo(V):
    return V.__dict__.setdefault("_mc_memo", {})


def _ts(V, i):
    return None if i is None else str(pd.Timestamp(V._ts[int(i)]))


# ------------------------------------------------------------------------------------------------ inputs (existing readers)
def dstate(V, t):
    """(Daily DState, Weekly DState) known at bar t — the Daily reader exactly as now (C-1)."""
    from . import daily as DD
    return DD.state_at(V.daily, V.bar_end[t]), DD.state_at(V.weekly, V.bar_end[t])


def structure(V):
    """The 1H structure in the 15M index: (D2 swings, BOS / CHoCH events, data segment per bar or None). The swings are the
    level_degree (D2) swings2 pivots (non warm-up, mtf_state's filter); the events are mtf_state's `_swings2_events` (dow_events by 15M
    close, per data segment). Memoised per V."""
    m = _memo(V)
    if "structure" not in m:
        from . import mtf_state as MS
        d2 = int(V.s["level_degree"])
        ps = sorted((p for p in V.res["pivots"].get(d2, []) if not p.warmup), key=lambda p: (p.confirm_bar, p.bar))
        m["structure"] = (ps, MS._swings2_events(V, d2), MS._m15_arrays(V)["seg"])
    return m["structure"]


def legs_frame(V, t):
    """The candles A / B are compared on: the 1H candles closed at t (mtf_state.frame — the 1H degree's own candles) ⇒ (F, 15M bar ⇒
    frame bar, n closed). A bare V without swings2 data (synthetic tests) ⇒ the 15M candles."""
    if isinstance(getattr(V, "res", None), dict) and "m15" in V.res:
        from . import mtf_state as MS
        F = MS.frame(V, t, "1H")
        of = MS.h1_view(V)["h1_of"]
        return F, (lambda i: int(of[int(i)])), int(F["n"])
    A = V.levels.A
    return {"o": A["open"], "h": A["high"], "l": A["low"], "c": A["close"], "v": A.get("volume_raw")}, int, int(t) + 1


def _leg(F, of, n, i0, i1, dirn):
    """legs_compare.leg_facts of the 15M bar range (i0, i1] on the frame (only candles closed by t)."""
    if i0 is None or i1 is None:
        return None
    j0, j1 = of(i0), min(of(i1), n - 1)
    return LC.leg_facts(F, j0, j1, dirn) if j1 > j0 else None


def known0(V, t):
    return [p for p in getattr(V.levels, "_known0", []) if p.confirm_bar <= t]


# ------------------------------------------------------------------------------------------------ the C cycle at bar t
def cycle(V, t, d):
    """The C cycle for the minor direction d (+1 = an up correction while the Daily is DOWN) read at bar t with bars ≤ t only ⇒ dict
    {id, phase, alive, why, O, choch, HA, a_nature, b_nature, b_end, ha_close, dead, windows {b, e, cp}, ha_area, context}."""
    key = ("cyc", int(t), int(d))
    m = _memo(V)
    if key in m:
        return m[key]
    m[key] = out = _cycle(V, int(t), int(d))
    return out


def _cycle(V, t, d):
    A = V.levels.A
    st, wk = dstate(V, t)
    want = "DOWN" if d > 0 else "UP"
    ctx = {"daily": {"trend": st.trend, "phase": getattr(st, "phase", None), "counter": getattr(st, "counter", None),
                     "corr_label": getattr(st, "corr_label", None), "rev": getattr(st, "rev", None) is not None,
                     "protected": None if getattr(st, "protected", None) is None else round(float(st.protected.price), 2),
                     "wave_a": None if getattr(st, "wave_a", None) is None else round(float(st.wave_a.price), 2)},
           "weekly": getattr(wk, "trend", None)}
    ctx["daily_b_leg"] = bool(ctx["daily"]["corr_label"] == "b" and ctx["daily"]["counter"] in ("candidate", "correction"))
    out = {"d": d, "t": t, "id": None, "phase": "none", "alive": False, "windows": {"b": False, "e": False, "cp": False},
           "context": ctx}
    if st.trend != want:
        out["why"] = f"Daily {st.trend}: model C needs the Daily side {want} (C-1)"
        return out
    ps, evs, seg = structure(V)
    s_t = None if seg is None else seg[t]
    same = (lambda b: True) if seg is None else (lambda b: seg[int(b)] == s_t)
    ev = [e for e in evs if e["type"] == "CHoCH" and int(e["dir"]) == d and int(e["bar"]) <= t and same(e["bar"])]
    if not ev:
        out["why"] = f"no 1H CHoCH {'up' if d > 0 else 'down'} known — wave A needs a CHoCH (C-3)"
        return out
    ch = max(ev, key=lambda e: int(e["bar"]))
    pb, cb = int(ch["pivot_bar"]), int(ch["bar"])
    X = A["low"] if d > 0 else A["high"]
    seg_x = np.asarray(X[pb:cb + 1], float)
    ob = pb + int(np.argmin(seg_x) if d > 0 else np.argmax(seg_x))
    O = float(X[ob])
    out.update(id=f"{cb}:{ob}", phase="A running", alive=True,
               O={"price": round(O, 2), "bar": ob, "ts": _ts(V, ob)},
               choch={"level": round(float(ch["level"]), 2), "bar": cb, "ts": _ts(V, cb), "protected_bar": pb})
    k0 = known0(V, t)
    C = A["close"]
    dead = TL._broken_at(C, k0, "L" if d > 0 else "H", lambda i: O, -d, ob + 1, t)   # K4 / K6.5: close beyond O + a swing beyond O
    if dead is not None:
        sw = next((p for p in k0 if p.kind == ("L" if d > 0 else "H") and p.bar >= dead and (float(p.price) - O) * d < 0), None)
        out.update(phase="dead", alive=False, dead={"close_bar": int(dead), "ts": _ts(V, dead),
                                                    "swing": None if sw is None else {"price": round(float(sw.price), 2),
                                                                                      "bar": int(sw.bar), "known_bar": int(sw.confirm_bar)}},
                   why=f"B died: a close {'below' if d > 0 else 'above'} O {O:,.2f} and a swing formed beyond it (C-4) — the "
                       f"correction idea is dead; the Daily side continues")
        return out
    kind = "H" if d > 0 else "L"
    ha = min((p for p in ps if p.kind == kind and int(p.bar) >= cb and int(p.bar) > ob and p.confirm_bar <= t and same(p.bar)),
             key=lambda p: int(p.bar), default=None)
    if ha is None:
        out["why"] = "wave A running: its 1H swing high HA is not confirmed yet (no B, no entry)" if d > 0 else \
            "wave A running: its 1H swing low HA is not confirmed yet (no B, no entry)"
        return out
    hb, HA = int(ha.bar), float(ha.price)
    out["HA"] = {"price": round(HA, 2), "bar": hb, "ts": _ts(V, hb), "known_bar": int(ha.confirm_bar)}
    beyond = np.flatnonzero((np.asarray(C[hb + 1:t + 1], float) - HA) * d > 0)
    hc = hb + 1 + int(beyond[0]) if len(beyond) else None
    last = (hc - 1) if hc is not None else t
    be = None
    if last > hb:
        xb = np.asarray(X[hb + 1:last + 1], float)
        be = hb + 1 + int(np.argmin(xb) if d > 0 else np.argmax(xb))
        out["b_end"] = {"price": round(float(X[be]), 2), "bar": be, "ts": _ts(V, be)}
    F, of, n = legs_frame(V, t)
    a_leg, p_leg, b_leg = _leg(F, of, n, ob, hb, d), _leg(F, of, n, pb, ob, -d), _leg(F, of, n, hb, be, -d)
    a_cmp, b_cmp = LC.compare(a_leg, [p_leg, b_leg]), LC.compare(b_leg, [a_leg])
    out.update(a_nature={"verdict": a_cmp["verdict"], "why": a_cmp["why"]}, b_nature={"verdict": b_cmp["verdict"], "why": b_cmp["why"]},
               legs={"A": a_leg, "B": b_leg, "before_O": p_leg})
    a_ok = str(V.s.get("c_a_nature", "impulse")) == "any" or a_cmp["verdict"] == LC.IMPULSE
    b_ok = b_cmp["verdict"] == LC.CORRECTION
    win = str(V.s.get("c_window", "b_only"))
    if hc is None:
        out["phase"] = "B in progress"
        out["windows"]["b"] = bool(a_ok and b_ok)
        out["why"] = ("B in progress: model C window open" if a_ok and b_ok else
                      f"B in progress, the models wait: A reads {a_cmp['verdict']}"
                      + ("" if a_ok else f" (c_a_nature = {V.s.get('c_a_nature', 'impulse')})")
                      + f", B reads {b_cmp['verdict']}" + ("" if b_ok else " (B must read corrective)"))
        return out
    out.update(phase="C underway", ha_close={"bar": hc, "ts": _ts(V, hc)},
               why=f"C underway: a close {'above' if d > 0 else 'below'} HA {HA:,.2f} — no new B entries (C-6)")
    if not (a_ok and b_ok):
        return out
    if win == "c_pullbacks":
        back = [e for e in evs if e["type"] == "CHoCH" and int(e["dir"]) == -d and hc < int(e["bar"]) <= t and same(e["bar"])]
        out["windows"]["cp"] = not back
    ha_area = _ha_area(V, t, hb, d)
    out["ha_area"] = ha_area
    if ha_area is not None and ("C-e" in subs_on(V) or win == "b_and_ha_retest"):
        r = _first_return(V, t, hc, ha_area, d, k0)
        out["ha_return"] = r
        out["windows"]["e"] = bool(r and r["start"] is not None and r.get("end_known") is None)
    return out


def _ha_area(V, t, hb, d):
    """HA's own 1H area: the area born at HA's swing (base_bar = HA's bar, the role against the minor direction) ⇒ {id, lo, hi} at t."""
    want = "resistance" if d > 0 else "support"
    for L in getattr(V.levels, "L", []):
        if getattr(L, "base_bar", None) == hb and getattr(L, "role0", None) == want and getattr(L, "tf", "1H") == "1H":
            lo, hi = L.band_at(t) if hasattr(L, "band_at") else (L.lo, L.hi)
            return {"id": L.id, "lo": round(float(lo), 2), "hi": round(float(hi), 2)}
    return None


def _first_return(V, t, hc, band, d, k0):
    """C-e: the FIRST return to HA's area after C left it — never the break itself (H2). The C push away = the first finest-structure
    swing beyond the band on the trade side formed from the first close beyond HA on (confirmed by t); the return starts at the first bar
    after that swing whose range touches the band and ends when a new swing forms that does not reach the band (either side — the
    visit's structure rule, RC4), known at its confirm bar."""
    A = V.levels.A
    lo, hi = float(band["lo"]), float(band["hi"])
    away = next((p for p in sorted(k0, key=lambda q: q.bar) if p.kind == ("H" if d > 0 else "L") and p.bar >= hc
                 and ((float(p.price) > hi) if d > 0 else (float(p.price) < lo))), None)
    if away is None:
        return {"push": None, "start": None}
    s0 = next((i for i in range(int(away.bar) + 1, t + 1) if A["low"][i] <= hi and A["high"][i] >= lo), None)
    out = {"push": {"price": round(float(away.price), 2), "bar": int(away.bar), "known_bar": int(away.confirm_bar)},
           "start": s0, "start_ts": _ts(V, s0)}
    if s0 is None:
        return out
    end = next((p for p in sorted(k0, key=lambda q: q.confirm_bar) if p.bar > s0 and (float(p.price) > hi or float(p.price) < lo)), None)
    out["end_known"] = None if end is None else int(end.confirm_bar)
    return out


def side_fn(V, d, cid, which):
    """The injected trade side for entry_models.Reader: u ⇒ d while the SAME cycle's window `which` (b / e / cp) is open at u (read with
    bars ≤ u), else 0 (the models re-arm from the window's first bar)."""
    def f(u):
        c = cycle(V, int(u), d)
        return d if c.get("id") == cid and c["windows"].get(which) else 0
    return f


# ------------------------------------------------------------------------------------------------ C areas and C objects
def areas(V, t, cyc, b0, b1):
    """C-5 (Q5): the minor-side areas at t (Levels.active), 1H only, ACTIVE / TESTED, whose base (Level.base_bar) lies in [b0, b1]."""
    trend = "UP" if cyc["d"] > 0 else "DOWN"
    out = []
    for x in V.levels.active(t, trend):
        if x.get("tf") != "1H" or x.get("state") not in AREA_STATES:
            continue
        L = V.levels.L[x["id"]] if isinstance(x.get("id"), (int, np.integer)) and 0 <= int(x["id"]) < len(V.levels.L) else None
        bb = getattr(L, "base_bar", None)
        if bb is not None and b0 <= int(bb) <= b1:
            out.append(x)
    return out


def _anchors(V, t, obj):
    if obj.get("parallel_of"):
        base = next((ln for ln in TL.channel_lines(V, t) if ln["id"] == obj["parallel_of"]), None)
        obj = base or obj
    return int(obj["p1"][0]), int((obj.get("p2") or obj["p1"])[0])


def keep_b(V, t, cyc):
    """C-b: a broken 1H line / channel parallel (entry_models' broken-line objects) whose anchors (a parallel: its base line's) lie
    inside B (from HA's bar to t)."""
    hb = cyc["HA"]["bar"]

    def f(kind, obj):
        if kind != "line" or str(obj.get("id", "")).startswith("pat:"):
            return False
        a1, a2 = _anchors(V, t, obj)
        return hb <= a1 and a2 <= t
    return f


def keep_d(cyc):
    """C-d: a broken triangle edge (patterns_pa.hook_lines) whose pattern swings all lie inside B."""
    hb = cyc["HA"]["bar"]
    return lambda kind, obj: kind == "line" and str(obj.get("id", "")).startswith("pat:") and \
        all(int(b) >= hb for b in obj.get("swing_bars") or [-1])


def keep_e(t, cyc):
    """C-e: HA's own BROKEN area, or a BROKEN line lying on it (its value at t inside the HA band) — one place (DECISIONS 28)."""
    ha = cyc.get("ha_area") or {}

    def f(kind, obj):
        if kind == "area":
            return obj.get("id") == ha.get("id")
        v = TL.line_value(obj, t)
        return ha.get("lo") is not None and float(ha["lo"]) <= v <= float(ha["hi"])
    return f


# ------------------------------------------------------------------------------------------------ the C entries at bar t
def entries_at(V, t, cyc):
    """Model C entries fired at bar t for the cycle (the existing entry models, unchanged) ⇒ (entries, armed)."""
    d = cyc["d"]
    trend = "UP" if d > 0 else "DOWN"
    sub = subs_on(V)
    cid = cyc["id"]
    got, armed = [], []

    def run(which, act, keep, extra, broken_on, label_fn):
        r = EM.read(V, t, trend, act, side_fn=side_fn(V, d, cid, which), keep=keep, extra=extra, prefix="M", broken_on=broken_on)
        armed.extend(r["armed"])
        for e in r["entries"]:
            s = label_fn(e)
            if s in sub:
                got.append((e, s, which))
    if cyc["windows"]["b"]:
        hb, ob = cyc["HA"]["bar"], cyc["O"]["bar"]
        act = areas(V, t, cyc, ob, hb) if ("C-a" in sub or "C-c" in sub) else []
        bo = "C-b" in sub or "C-d" in sub
        extra = None
        if "C-d" in sub:
            from . import patterns_pa as PA
            extra = PA.hook_lines(V, t, d, families=TRIANGLES)
        kb, kd = keep_b(V, t, cyc), keep_d(cyc)
        keep = (lambda k, o: ("C-b" in sub and kb(k, o)) or ("C-d" in sub and kd(k, o)))
        if act or bo:
            run("b", act, keep, extra, bo, lambda e: _sub_of(e, cyc))
    if cyc["windows"]["e"] and "C-e" in sub:
        ha = cyc["ha_area"]
        act = [x for x in V.levels.active(t, trend) if x.get("id") == ha["id"] and x.get("state") == FL.FLIPPED]
        run("e", act, keep_e(t, cyc), None, True, lambda e: "C-e")
    if cyc["windows"]["cp"] and ("C-a" in sub or "C-c" in sub):
        b0 = (cyc.get("b_end") or {}).get("bar", cyc["HA"]["bar"])
        run("cp", areas(V, t, cyc, b0, t), None, None, False, lambda e: _sub_of(e, cyc))
    out = [label(V, t, e, cyc, s, which) for e, s, which in got]
    return out, armed


def _sub_of(e, cyc):
    """The firing sub-model of one entry (Q10: an E4 (a) whose sweep extreme lies beyond O at a C area = C-c, wins over C-a)."""
    if e["object"] == "area":
        if e["model"] == "E4" and (e.get("facts") or {}).get("sweep_extreme") is not None:
            if (float(e["facts"]["sweep_extreme"]) - float(cyc["O"]["price"])) * cyc["d"] < 0:
                return "C-c"
        return "C-a"
    return "C-d" if str(e["area"].get("id", "")).startswith("line:pat:") else "C-b"


def _px(x):
    return "NA" if x is None else f"{float(x):,.2f}"


def end_zone(V, t, cyc):
    """C-7 — CONTEXT ONLY (never a gate, an entry or an exit): the first Daily / Weekly area beyond HA on the trade side (snapshot, Z-1u:
    Weekly = context), the Daily protected origin, and the C-vs-A projections B_end + r × |HA − O| (r in `c_projections`, display
    ratios from the settings). Bars ≤ t."""
    d = cyc["d"]
    HA, O = float(cyc["HA"]["price"]), float(cyc["O"]["price"])
    role = "resistance" if d > 0 else "support"
    htf = [x for x in V.levels.snapshot(t) if x.get("tf") in ("D", "W") and x.get("role") == role and x.get("state") != FL.DEAD
           and ((float(x["lo"]) > HA) if d > 0 else (float(x["hi"]) < HA))]
    first = min(htf, key=lambda x: (float(x["lo"]) - HA) * d, default=None)
    be = (cyc.get("b_end") or {}).get("price")
    proj = [] if be is None else [{"ratio": float(r), "price": round(float(be) + d * float(r) * abs(HA - O), 2)}
                                  for r in (V.s.get("c_projections") or ())]
    return {"first_htf_area": None if first is None else {k: first.get(k) for k in ("id", "tf", "role", "lo", "hi", "state")},
            "protected_origin": cyc["context"]["daily"].get("protected"), "projections": proj,
            "use": "context only — never a gate, an entry or an exit (C-7)"}


def evidence(V, t, cyc):
    """C-8 — context lines only (never a gate): B's per-bar FUT volume against A's, and the hidden RSI divergence at the B low."""
    lg = cyc.get("legs") or {}
    va, vb = (lg.get("A") or {}).get("volume"), (lg.get("B") or {}).get("volume")
    out = {"b_volume_vs_a": "NA (FUT volume missing on a bar of A or B)" if va is None or vb is None else
           ("lower" if vb < va else "not lower")}
    try:
        from . import rsi_hidden as RH
        h = RH.read_hidden_divergence(V, t, cyc["d"])
        out["hidden_divergence"] = {"found": h.get("found"), "reading": h.get("reading")}
    except Exception as exc:                                               # noqa: BLE001 — evidence only, never a block
        out["hidden_divergence"] = {"found": None, "reading": f"NA ({type(exc).__name__})"}
    return out


def story(e, cyc, sub, ez):
    """C-10: one plain line for the card — the context, where the entry is, the model, the end zone and what invalidates the idea."""
    d = cyc["d"]
    dn = "DOWN" if d > 0 else "UP"
    O, HA = cyc["O"]["price"], cyc["HA"]["price"]
    a = e.get("area") or {}
    side = "demand" if d > 0 else "supply"
    where = {"C-a": f"B pullback into the 1H {side} area {_px(a.get('lo'))}–{_px(a.get('hi'))}",
             "C-c": f"B swept O {_px(O)} at the 1H {side} area {_px(a.get('lo'))}–{_px(a.get('hi'))} and the next push failed",
             "C-b": f"B's broken channel line retested at {_px(a.get('lo'))}",
             "C-d": f"B's broken triangle edge retested at {_px(a.get('lo'))}",
             "C-e": f"C underway: the first return to HA's area {_px((cyc.get('ha_area') or {}).get('lo'))}–"
                    f"{_px((cyc.get('ha_area') or {}).get('hi'))}"}[sub]
    if cyc.get("windows", {}).get("cp") and sub in ("C-a", "C-c") and cyc.get("ha_close"):
        where = f"C's own pullback (c_pullbacks what-if) into the 1H {side} area {_px(a.get('lo'))}–{_px(a.get('hi'))}"
    z = ez.get("first_htf_area")
    zone = ("end zone: " + (f"{z['tf']} {z['role']} {_px(z['lo'])}–{_px(z['hi'])}" if z else "no Daily / Weekly area beyond HA known")
            + "".join(f", C = {p['ratio']:g}×A at {_px(p['price'])}" for p in ez.get("projections") or []))
    return (f"Counter C leg — Daily {dn}, 1H correction: A complete (O {_px(O)} → HA {_px(HA)}), {where}, model C · {e['model']} "
            f"({sub}) · {zone} · invalidated if B closes {'below' if d > 0 else 'above'} O {_px(O)} and a swing forms "
            f"{'below' if d > 0 else 'above'} O.")


def label(V, t, e, cyc, sub, which):
    """One model C entry: the existing entry dict + family / sub_model / story / context; ids prefixed "C:" (the per-visit claim and
    the statistics stay apart from the Daily side). The payload `model` stays E1–E4 (engine_signal.entry_ok unchanged)."""
    e = {k: v for k, v in e.items() if not k.startswith("_")}
    for k in ("visit_id", "area_visit_id", "key"):
        if e.get(k) is not None:
            e[k] = "C:" + str(e[k])
    ez = end_zone(V, t, cyc)
    ctx = {"family": "C", "sub_model": sub, "sub_name": SUB_NAME[sub], "window": {"b": str(V.s.get("c_window", "b_only")),
                                                                                  "e": "first return to HA", "cp": "c_pullbacks"}[which],
           "cycle": cyc["id"], "daily": cyc["context"]["daily"], "weekly": cyc["context"]["weekly"],
           "daily_b_leg": cyc["context"]["daily_b_leg"], "O": cyc["O"], "choch": cyc["choch"], "HA": cyc["HA"],
           "B": cyc.get("b_end"), "a_nature": cyc["a_nature"], "b_nature": cyc["b_nature"], "end_zone": ez,
           "evidence": evidence(V, t, cyc),
           "invalidated_if": f"B closes {'below' if cyc['d'] > 0 else 'above'} O {_px(cyc['O']['price'])} and a swing forms beyond O"}
    e.update(family="C", sub_model=sub, c_label=f"C · {e['model']}", story=story(e, cyc, sub, ez), model_c=ctx)
    return e


def brief(cyc):
    """The cycle for the row (display / replay): no leg facts dicts."""
    return {k: v for k, v in cyc.items() if k not in ("legs",)}


def tag_cf(V, t, row, cyc):
    """C-f (a label only, Q6): a Daily-side entry (direction against the minor side) after C left HA, while the cycle lives, whose
    area overlaps the end zone's first Daily / Weekly area — or an E4 (b) on a broken line anchored inside C — gets `model_c_context`
    {sub_model C-f}. Never removes, adds or changes an entry's model, side, trigger or invalidation."""
    if not cyc.get("alive") or not cyc.get("ha_close"):
        return
    ez = end_zone(V, t, cyc)
    z = ez.get("first_htf_area")
    b0 = (cyc.get("b_end") or {}).get("bar", cyc["HA"]["bar"])
    for e in row.get("entries") or []:
        if e.get("family") == "C" or int(e.get("direction") or 0) != -cyc["d"]:
            continue
        a = e.get("area") or {}
        hit = z is not None and a.get("lo") is not None and float(a["lo"]) <= float(z["hi"]) and float(a["hi"]) >= float(z["lo"])
        ln = a.get("line") or {}
        if not hit and e.get("object") == "broken_line" and ln.get("p1"):
            hit = int(ln["p1"][0]) >= int(b0)
        if hit:
            e["model_c_context"] = {"sub_model": "C-f", "sub_name": SUB_NAME["C-f"], "cycle": cyc["id"], "end_zone": ez,
                                    "use": "label / statistics only — the Daily-side entry is unchanged"}


# ------------------------------------------------------------------------------------------------ the V22.decide hook
def attach(V, t, row):
    """V22.decide (only when `model_c = on`): row["model_c"] = the cycle read at t + the C armed objects; the C entries are appended to
    row["entries"] (the Daily-side entries and every other row key unchanged; C-f only labels). A model C reading error is logged and
    reported in row["model_c"]["error"] and gives no C entry (fail closed) — it never touches the Daily side."""
    try:
        st, _wk = dstate(V, t)
        d = {"DOWN": 1, "UP": -1}.get(st.trend)
        sub = subs_on(V)
        info = {"on": True, "subs": list(sub), "window": str(V.s.get("c_window", "b_only")),
                "a_nature_rule": str(V.s.get("c_a_nature", "impulse"))}
        if d is None:
            row["model_c"] = {**info, "cycle": None, "why": f"Daily {st.trend}: model C needs a Daily DOWN / UP side (C-1, Q1)"}
            return row
        cyc = cycle(V, t, d)
        ents, armed = entries_at(V, t, cyc) if cyc.get("alive") and any(cyc["windows"].values()) else ([], [])
        info.update(direction=d, cycle=brief(cyc), entries=len(ents),
                    armed=[{k: a.get(k) for k in ("object", "area_id", "lo", "hi", "visit_id", "disarmed")} |
                           {"models": {m: (x or {}).get("status") for m, x in (a.get("models") or {}).items()}} for a in armed])
        row["model_c"] = info
        if ents:
            row["entries"] = list(row.get("entries") or []) + ents
        if "C-f" in sub:
            tag_cf(V, t, row, cyc)
    except Exception as exc:                                               # noqa: BLE001 — model C never breaks the Daily side
        log.warning("decision3 model C failed at bar %s: %s", t, exc, exc_info=True)
        row["model_c"] = {"on": True, "error": f"{type(exc).__name__}: {exc}"[:200], "entries": 0}
    return row
