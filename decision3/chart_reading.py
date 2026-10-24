"""decision3/chart_reading.py — the FACTS of the daily Chart Reading Report (Abhi's order, owner-orders DECISIONS 35).

What it is: one plain, JSON-safe dict per symbol with what the decision3 READER already read at the closed 15M bar t — grouped by the
closed concept list of the Price Action Standard (§1 MTF, §2 A–L, §3 models). Nothing here reads price on its own: every value is copied
from a reader (mtf_state, Levels.snapshot with the K4 lifecycle, liquidity_pa, the decision row's channel_lines / channels,
patterns_pa, volume_read, rsi (draw_objects.divergences) / rsi_hidden, the row's wave_context, confluence_pa, range_edges, legs_compare,
area_types, entry_models incl. the refined 15M base, model C's switch). No new reading rule, no score, no number.

Selection words only (display, comparison — no number): "nearest" = the smallest distance from the last close (the reader's own `dist`);
"current" = known in the reader's structure window (the 1H external pivots `mtf_state` reads the trend from); a concept with nothing to
say is an empty list / None and its section is left out of the message.

No look-ahead: everything is read with the reader's own bars-≤-t functions; `as_of` is the bar's close (`V.bar_end[t]`). One concept
failing never stops the rest — its error is kept in `errors` (shown on the dashboard page only).

Every fact item carries `src` = the reader fact it comes from (tests map every message line back to its fact)."""
import math

import numpy as np
import pandas as pd

CONCEPTS = ("big_picture", "structure", "areas", "liquidity", "lines", "patterns", "confluence", "volume", "rsi", "breakout_range",
            "wave", "plan")
ALIVE = ("ACTIVE", "TESTED", "FLIPPED")                                     # K4 alive + a trade location (BROKEN / DEAD are not)
SHOWN_TFS = ("1H", "D", "W")


def _f(x, nd=2):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def _kind(role):
    return {"resistance": "supply", "support": "demand"}.get(str(role), "area")


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(x))
    return x


# ------------------------------------------------------------------------------------------------------------------------ areas
def area_fact(x, conf_by_id=None, types_by_id=None):
    """One `Levels.snapshot` area ⇒ the report's area item (state words from the K4 lifecycle; confluence pieces from confluence_pa)."""
    st = str(x.get("state") or "ACTIVE").upper()
    role = str(x.get("role") or "")
    was = None
    if st == "FLIPPED" or int(x.get("flips") or 0) > 0:
        was = {"resistance": "support", "support": "resistance"}.get(role)
    out = {"id": x.get("id"), "tf": x.get("tf"), "role": role, "kind": _kind(role), "lo": _f(x.get("lo")), "hi": _f(x.get("hi")),
           "state": st, "tests": int(x.get("tests") or 0), "sweeps": int(x.get("sweeps") or 0), "flips": int(x.get("flips") or 0),
           "was": was, "dist": _f(x.get("dist")), "above": bool(x.get("above")), "below": bool(x.get("below")),
           "trade_location": bool(x.get("trade_location", True)), "born_bar": x.get("born_bar"),
           "confluence_label": x.get("confluence_label"), "src": "levels.snapshot (K4 lifecycle)"}
    c = (conf_by_id or {}).get(x.get("id"))
    if c:
        out["confluence"] = [{"what": p.get("what"), "tf": p.get("tf"), "ratio": p.get("ratio"), "lo": _f(p.get("lo")),
                              "hi": _f(p.get("hi")), "price": _f(p.get("price"))} for p in c.get("pieces") or ()]
    ty = (types_by_id or {}).get(x.get("id"))
    if ty:
        out["base_type"] = (ty.get("base") or {}).get("type")
        out["departure"] = (ty.get("departure") or {}).get("strength")
    if "line" in str(x.get("confluence_label") or ""):
        out.setdefault("confluence", []).append({"what": "line"})
    return out


def overlaps(a, b):
    return not (float(a["hi"]) < float(b["lo"]) or float(a["lo"]) > float(b["hi"]))


def duplicate_groups(areas):
    """Reading check (concept C / Z-1u): alive areas of the same timeframe and role whose bands overlap = one PLACE (a counter only, the
    reader never merges them). Returns [{"tf", "kind", "ids", "lo", "hi"}] (lo / hi = the lowest / highest edge of the group, for the
    WORDS only — never a band the engine uses). Comparison only."""
    out, seen = [], set()
    for i, a in enumerate(areas):
        if a["id"] in seen:
            continue
        grp = [a]
        for b in areas[i + 1:]:
            if b["id"] not in seen and b["tf"] == a["tf"] and b["role"] == a["role"] and any(overlaps(b, g) for g in grp):
                grp.append(b)
        if len(grp) > 1:
            seen.update(g["id"] for g in grp)
            out.append({"tf": a["tf"], "kind": a["kind"], "ids": [g["id"] for g in grp], "lo": min(g["lo"] for g in grp),
                        "hi": max(g["hi"] for g in grp), "src": "levels.snapshot (Z-1u counter)"})
    return out


def _nearest(items, key=lambda a: a["dist"]):
    return min(items, key=key) if items else None


def areas_facts(V, t, row, close, conf_read=None, types=None):
    snap = V.levels.snapshot(t)
    conf_by_id = {a["id"]: a for a in (conf_read or {}).get("areas") or ()}
    types_by_id = {a["id"]: a for a in (types or ())}
    alive = [area_fact(x, conf_by_id, types_by_id) for x in snap if str(x.get("state")).upper() in ALIVE and x.get("tf") in SHOWN_TFS]
    broken = [area_fact(x) for x in snap if str(x.get("state")).upper() in ("BROKEN", "BEYOND_NOT_BROKEN") and x.get("tf") in SHOWN_TFS]
    by_id = {a["id"]: a for a in alive}
    watch = [by_id[w["id"]] for w in (row.get("watch_list") or ()) if w.get("id") in by_id]   # the engine's own armed trade side
    side_roles = {w.get("role") for w in (row.get("watch_list") or ())}
    opp_role = ({"resistance", "support"} - side_roles).pop() if len(side_roles) == 1 else None
    # the next opposite area: the nearest alive 1H / Daily area of the other role on the far side of price (preopen_crux's target rule)
    opp = [a for a in alive if opp_role and a["role"] == opp_role and a["trade_location"]
           and ((opp_role == "support" and a["below"]) or (opp_role == "resistance" and a["above"]))]
    shown_ids = {a["id"] for a in watch}
    out = {"watch": watch, "next_opposite": _nearest(opp), "htf": [], "broken": broken, "alive": alive}
    if out["next_opposite"]:
        shown_ids.add(out["next_opposite"]["id"])
    for tf in ("D", "W"):                                                  # the nearest Daily / Weekly area above and below price
        for side in ("above", "below"):
            a = _nearest([x for x in alive if x["tf"] == tf and x[side] and x["id"] not in shown_ids])
            if a:
                out["htf"].append(a)
                shown_ids.add(a["id"])
        ins = [x for x in alive if x["tf"] == tf and not x["above"] and not x["below"] and x["id"] not in shown_ids]
        for a in ins:                                                      # price inside a Daily / Weekly area
            out["htf"].append(a)
            shown_ids.add(a["id"])
    near_1h = [a for a in alive if a["tf"] == "1H"]
    out["duplicates"] = duplicate_groups([a for a in near_1h if a["id"] in shown_ids or
                                          any(overlaps(a, by_id[i]) for i in shown_ids if by_id[i]["tf"] == "1H")])
    out["shown_ids"] = sorted(shown_ids)
    return out


# ------------------------------------------------------------------------------------------------------------------------ pieces
def big_picture(V, t, row, mts):
    tfs = {}
    for tf in ("W", "D", "1H", "15M", "5M"):
        x = (mts.get("tfs") or {}).get(tf) or {}
        tfs[tf] = {"state": x.get("state"), "trend": x.get("trend"), "protected": _f(x.get("protected")),
                   "band": [_f(b) for b in x["band"]] if isinstance(x.get("band"), (list, tuple)) else None,
                   "src": f"mtf_state.tfs[{tf}]"}
    p = row.get("protected") or {}
    daily = {"trend": row.get("daily_trend"), "trend_used": row.get("trend_used"), "phase": row.get("daily_phase"),
             "protected": _f(p.get("price")), "protected_kind": p.get("kind"), "weekly": row.get("weekly_trend"),
             "src": "decision row ① (daily.fold_impulse)"}
    return {"tfs": tfs, "daily": daily, "agreement": (mts.get("agreement") or {}).get("relation"),
            "side": (mts.get("agreement") or {}).get("side")}


def _last_event(st, tf):
    ext = (((st.get("tfs") or {}).get(tf) or {}).get("structure") or {}).get("external") or {}
    ev = ext.get("events") or []
    if not ev:
        return None
    e = ev[-1]
    return {"tf": tf, "type": e.get("type"), "dir": e.get("dir"), "level": _f(e.get("level")), "src": f"mtf_state.{tf}.external.events"}


def structure_facts(V, t, mts, legs):
    out = {"events": [e for e in (_last_event(mts, tf) for tf in ("1H", "15M", "D")) if e], "legs": [], "legs_htf": []}
    for tf in ("D", "W"):                                                  # chart geometry of the Daily / Weekly legs (display)
        for lg in (((legs or {}).get("tfs") or {}).get(tf) or {}).get("legs") or []:
            out["legs_htf"].append({"tf": tf, "dir": lg.get("dir"), "verdict": lg.get("verdict"), "complete": bool(lg.get("complete")),
                                    "t0": lg.get("t0") or lg.get("from_ts"), "t1": lg.get("t1") or lg.get("to_ts"),
                                    "p0": _f(lg.get("p0")), "p1": _f(lg.get("p1")), "src": f"legs_compare.tfs[{tf}].legs"})
    for tf in ("1H",):
        L = (((legs or {}).get("tfs") or {}).get(tf) or {}).get("legs") or []
        for lg in L[-2:]:
            out["legs"].append({"tf": tf, "dir": lg.get("dir"), "verdict": lg.get("verdict"), "complete": bool(lg.get("complete")),
                                "measures": lg.get("measures") or {}, "p0": _f(lg.get("p0")), "p1": _f(lg.get("p1")),
                                "src": f"legs_compare.tfs[{tf}].legs"})
    return out


def liquidity_facts(V, t, liq, close):
    obv = [x for x in (liq or {}).get("obvious") or () if x.get("tf") == "15M" and x.get("degree") == "structure"]
    out = {"above": None, "below": None, "sweep": None, "inducement": None}
    up = [x for x in obv if x.get("state") == "resting" and x["kind"] == "H" and float(x["price"]) > close]
    dn = [x for x in obv if x.get("state") == "resting" and x["kind"] == "L" and float(x["price"]) < close]
    if up:
        x = min(up, key=lambda x: float(x["price"]) - close)
        out["above"] = {"price": _f(x["price"]), "equal": x.get("src") == "equal", "state": "resting", "src": "liquidity_pa.obvious"}
    if dn:
        x = min(dn, key=lambda x: close - float(x["price"]))
        out["below"] = {"price": _f(x["price"]), "equal": x.get("src") == "equal", "state": "resting", "src": "liquidity_pa.obvious"}
    try:
        from . import draw_objects as DO
        sw = DO.sweeps(V, t, DO.window_start(V, t))
        if sw:
            s = sw[-1]
            out["sweep"] = {"state": s.get("state"), "pool": _f(s.get("p0")), "extreme": _f(s.get("p1")),
                            "beyond": "above" if float(s["p1"]) > float(s["p0"]) else "below", "src": "liquidity.sweeps_and_traps"}
    except Exception:                                                      # noqa: BLE001 — evidence only
        pass
    return out


def _bar_of(V, i):
    return int(i[0]) if isinstance(i, (list, tuple)) else int(i)


def _geom(x):
    """A reader line's own geometry (15M bar index + price + slope per 15M bar) — for the chart only."""
    p1 = (x or {}).get("p1")
    if not p1 or x.get("slope") is None:
        return None
    p2 = x.get("p2")
    return {"bar": int(p1[0]), "price": _f(p1[1]), "slope": _f(x["slope"], 6), "last": int(p2[0]) if p2 else int(p1[0])}


def lines_facts(V, t, row, close):
    chans = [c for c in row.get("channels") or () if str(c.get("state")) == "inside"]
    lines = [x for x in row.get("channel_lines") or () if not x.get("broken")]
    out = {"channels": [], "above": None, "below": None}
    by_id = {x.get("id"): x for x in row.get("channel_lines") or ()}
    for c in chans:
        base = by_id.get(c.get("base")) or {}
        par = c.get("parallel") or {}
        out["channels"].append({"tf": c.get("tf"), "degree": c.get("degree"), "slope": c.get("slope_dir"), "upper": _f(c.get("upper_t")),
                                "lower": _f(c.get("lower_t")), "touches": int(base.get("touches") or 0), "id": c.get("id"),
                                "geom": [g for g in (_geom(base), _geom(par)) if g],
                                "src": "decision row channels (trendline.channels)"})
    up = [x for x in lines if _f(x.get("value_t")) is not None and float(x["value_t"]) > close]
    dn = [x for x in lines if _f(x.get("value_t")) is not None and float(x["value_t"]) < close]
    for k, arr, key in (("above", up, lambda x: float(x["value_t"]) - close), ("below", dn, lambda x: close - float(x["value_t"]))):
        if arr:
            x = min(arr, key=key)
            out[k] = {"tf": x.get("tf"), "family": x.get("family"), "slope": x.get("slope_dir"), "value": _f(x.get("value_t")),
                      "touches": int(x.get("touches") or 0), "id": x.get("id"), "geom": _geom(x), "degree": x.get("degree"),
                      "src": "decision row channel_lines (trendline)"}
    return out


def current_patterns(pat, start_bar):
    """Patterns known in the current 1H structure window (their last swing at or after the window's first pivot)."""
    out = []
    for p in (pat or {}).get("patterns") or ():
        if start_bar is not None and int(p.get("end_bar") or -1) < int(start_bar):
            continue
        out.append({"name": p.get("name"), "family": p.get("family"), "state": p.get("state"), "named": bool(p.get("named")),
                    "boundaries": {k: v.get("state") for k, v in (p.get("boundaries") or {}).items()},
                    "lines": [{"name": ln.get("name"), "value": _f(ln.get("value_t")), "geom": _geom(ln),
                               "from_bar": int((ln.get("p0") or [0])[0])} for ln in p.get("lines") or ()],
                    "tf": p.get("tf"), "end_bar": p.get("end_bar"), "src": "patterns_pa.read_patterns"})
    out.sort(key=lambda p: -int(p.get("end_bar") or -1))                  # the latest pattern first
    return out


def _window_start_bar(mts, tf="1H"):
    pv = (((mts.get("tfs") or {}).get(tf) or {}).get("structure") or {}).get("external", {}).get("pivots") or []
    bars = [int(p["bar"]) for p in pv if p.get("bar") is not None]
    return min(bars) if bars else None


def volume_facts(V, vol):
    if not vol or vol.get("volume") != "FUT":
        return {"missing": True, "src": "volume_read (FUT volume)"}
    pv = vol.get("pullback_vs_impulse") or {}
    er = vol.get("effort_result") or {}
    cl = vol.get("climax") or {}
    return {"missing": False, "pullback": {"state": pv.get("state"), "impulse_dir": (pv.get("impulse") or {}).get("dir"),
                                           "pullback_avg": _f((pv.get("pullback") or {}).get("avg_volume"), 0),
                                           "impulse_avg": _f((pv.get("impulse") or {}).get("avg_volume"), 0)},
            "effort_result": er.get("state"), "climax": cl.get("state"), "src": "volume_read.read_volume"}


def rsi_facts(V, t, row, start_bar):
    from . import draw_objects as DO
    out = {"regular": [], "hidden": None}
    since = 0 if start_bar is None else int(start_bar)
    for o in DO.divergences(V, t, since):
        out["regular"].append({"side": "bear" if "bear" in o["label"] else "bull", "degree": o.get("degree"), "p0": _f(o["p0"]),
                               "p1": _f(o["p1"]), "state": o.get("state"), "t0": o["t0"], "t1": o["t1"],
                               "src": "rsi2 regular divergence (draw_objects.divergences)"})
    try:
        from . import rsi_hidden as RH
        d = {"DOWN": -1, "UP": 1}.get(str(row.get("trend_used")))
        if d is not None:
            h = RH.read_hidden_divergence(V, t, d)
            out["hidden"] = {"side": "bull" if d > 0 else "bear", "found": h.get("found"), "src": "rsi_hidden.read_hidden_divergence"}
    except Exception:                                                      # noqa: BLE001
        pass
    return out


def breakout_range_facts(V, t, row, pats, areas):
    rs = row.get("range_state") or {}
    out = {"in_range": bool(rs.get("in_range")), "tfs": list(rs.get("tfs_in_range") or ()), "edges": [], "breakouts": [],
           "sweeps": []}
    for e in rs.get("edges") or ():
        out["edges"].append({"tf": e.get("tf"), "edge": e.get("range_edge"), "lo": _f(e.get("lo")), "hi": _f(e.get("hi")),
                             "lifecycle": e.get("lifecycle"), "src": "range_edges.range_state"})
    for p in pats or ():
        for k, st in (p.get("boundaries") or {}).items():
            if st in ("accepted", "fakeout", "failed", "sweep") and p.get("named"):
                out["breakouts"].append({"pattern": p["name"], "boundary": k, "state": st, "src": "patterns_pa boundaries"})
    for a in (areas or {}).get("watch") or ():
        if a.get("sweeps"):
            out["sweeps"].append({"id": a["id"], "kind": a["kind"], "lo": a["lo"], "hi": a["hi"], "sweeps": a["sweeps"],
                                  "src": "levels.snapshot sweeps (K4)"})
    return out


def wave_facts(V, row, mts):
    wc = row.get("wave_context") or {}
    w = ((mts.get("tfs") or {}).get("W") or {})
    detail = str(w.get("detail") or "").split(" · protected")[0].strip() or None
    out = {"weekly_detail": detail, "daily_leg": row.get("daily_leg"), "corr_label": row.get("corr_label") or wc.get("corr_label"),
           "daily_phase": row.get("daily_phase"), "weekly_state": w.get("state"), "weekly_counter": w.get("counter"),
           "src": "decision row wave_context (daily)"}
    try:
        from . import model_c as MC
        out["model_c"] = "on" if MC.is_on(V) else "off"
        if out["model_c"] == "on" and row.get("model_c"):
            out["model_c_brief"] = str((row.get("model_c") or {}).get("brief") or "")[:160]
    except Exception:                                                      # noqa: BLE001
        out["model_c"] = None
    return out


def plan_facts(V, t, row, areas):
    """What the engine waits for at the nearest trade-side area: the method's sequence, the entry models' state there, the refined 15M
    base (RC2), the area's BROKEN rule (K4), the next area of the same side; the other side's words (model C)."""
    from . import entry_models as EM
    trend = str(row.get("trend_used") or "")
    sides = list(row.get("trade_side") or ())
    out = {"trend": trend, "sides": sides, "nearest": None, "next_same_side": None, "models": {}, "refined": None,
           "entries": [{"model": e.get("model"), "area": (e.get("area") or {}).get("id")} for e in row.get("entries") or ()],
           "models_on": list(row.get("entry_models_on") or ()), "src": "entry_models.read (decision row armed)"}
    watch = sorted(areas.get("watch") or (), key=lambda a: a["dist"])
    if not watch:
        return out
    n = watch[0]
    out["nearest"] = n
    far_same = [a for a in watch[1:] if (a["role"] == "resistance" and a["hi"] > n["hi"]) or (a["role"] == "support" and a["lo"] < n["lo"])]
    out["next_same_side"] = far_same[0] if far_same else None
    for a in row.get("armed") or ():
        if a.get("area_id") == n["id"]:
            out["models"] = {m: {"status": (x or {}).get("status")} for m, x in (a.get("models") or {}).items()}
            out["visit"] = True
            out["visit_start_bar"] = a.get("visit_start_bar")
            why = str(a.get("disarmed") or "")
            out["disarmed"] = ("trade_side" if "from the trade side" in why else "broken" if "broke" in why else
                               "other" if why else None)
            break
    d = -1 if n["role"] == "resistance" else 1
    try:
        lvl = next((x for x in V.levels.snapshot(t) if x["id"] == n["id"]), None)
        rb = EM.Reader(V).refined(t, lvl, d) if lvl else None
        if rb:
            out["refined"] = {"lo": _f(rb["lo"]), "hi": _f(rb["hi"]), "far": _f(rb["hi"] if d < 0 else rb["lo"]), "ts": rb.get("ts"),
                              "src": "entry_models.Reader.refined (RC2)"}
    except Exception:                                                      # noqa: BLE001 — evidence only
        out["refined"] = None
    out["far_edge"] = n["hi"] if d < 0 else n["lo"]
    out["d"] = d
    return out


# ------------------------------------------------------------------------------------------------------------------------ collect
def collect(V, t=None, symbol="", row=None):
    """The report facts at closed 15M bar t (default: the last bar). row = V.decide(t) when the caller has it. Never raises for one
    concept: its error goes to `errors`."""
    t = len(V.m15) - 1 if t is None else int(t)
    row = row if row is not None else V.decide(t)
    close = float(V.levels.A["close"][t])
    facts = {"symbol": str(symbol).upper(), "t": t, "as_of": str(pd.Timestamp(V.bar_end[t])), "bar": str(pd.Timestamp(V._ts[t])),
             "last_close": round(close, 2), "fut_volume": bool(getattr(V, "vol_src", None)), "errors": {}}
    reads = {}

    def read(name, fn):
        try:
            reads[name] = fn()
        except Exception as exc:                                           # noqa: BLE001 — one reader failing never stops the rest
            reads[name] = None
            facts["errors"][name] = f"{type(exc).__name__}: {str(exc)[:160]}"

    from . import area_types as AT
    from . import confluence_pa as CP
    from . import legs_compare as LC
    from . import liquidity_pa as LP
    from . import mtf_state as MS
    from . import patterns_pa as PP
    from . import volume_read as VR
    read("mtf", lambda: MS.read_mtf_state(V, t))
    read("legs", lambda: LC.read_legs_compare(V, t))
    read("liq", lambda: LP.read_liquidity(V, t))
    read("conf", lambda: CP.read_confluence(V, t))
    read("types", lambda: AT.read_area_types(V, t))
    read("patterns", lambda: PP.read_patterns(V, t))
    read("volume", lambda: VR.read_volume(V, t))
    mts = reads.get("mtf") or {}
    start = _window_start_bar(mts)

    def put(name, fn):
        try:
            facts[name] = _jsonable(fn())
        except Exception as exc:                                           # noqa: BLE001
            facts[name] = None
            facts["errors"][name] = f"{type(exc).__name__}: {str(exc)[:160]}"

    put("big_picture", lambda: big_picture(V, t, row, mts))
    put("structure", lambda: structure_facts(V, t, mts, reads.get("legs")))
    put("areas", lambda: areas_facts(V, t, row, close, reads.get("conf"), reads.get("types")))
    put("liquidity", lambda: liquidity_facts(V, t, reads.get("liq"), close))
    put("lines", lambda: lines_facts(V, t, row, close))
    put("patterns", lambda: current_patterns(reads.get("patterns"), start))
    put("volume", lambda: volume_facts(V, reads.get("volume")))
    put("rsi", lambda: rsi_facts(V, t, row, start))
    put("breakout_range", lambda: breakout_range_facts(V, t, row, facts.get("patterns"), facts.get("areas")))
    put("wave", lambda: wave_facts(V, row, mts))
    put("plan", lambda: plan_facts(V, t, row, facts.get("areas") or {}))
    facts["confluence"] = _jsonable(confluence_of(facts.get("areas")))
    facts["structure_window_bar"] = start
    return facts


def confluence_of(areas):
    """Concept F: the confluence pieces that land ON the shown areas (confluence_pa / the snapshot's label) — labels, never a location."""
    out = []
    if not areas:
        return out
    seen = set()
    for a in list(areas.get("watch") or ()) + [areas.get("next_opposite")] + list(areas.get("htf") or ()):
        if not a or a["id"] in seen or not a.get("confluence"):
            continue
        seen.add(a["id"])
        out.append({"id": a["id"], "tf": a["tf"], "kind": a["kind"], "lo": a["lo"], "hi": a["hi"], "pieces": a["confluence"],
                    "src": "confluence_pa.read_confluence areas"})
    return out


def area_by_id(facts, aid):
    a = (facts.get("areas") or {}).get("alive") or ()
    return next((x for x in a if x["id"] == aid), None)
