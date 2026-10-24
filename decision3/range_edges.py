"""decision3/range_edges.py — PA standard §2L: the range market's two EDGES as areas (evidence / areas only).

Abhi's method: when a timeframe's state is range, the range edges ARE the areas — a bull put at the lower edge, a bear call at the upper
edge. The range (Abhi 21 Oct, `daily_range_rule = structure`): after a swing high H and a swing low L (the two edges), the later swings
fail to make a new extreme on both sides (no close beyond the edge; a wick = a sweep, inside); it ends at a close beyond an edge + a swing
beyond (`daily.range_walk`). Daily / Weekly = the RANGE state of `decision3.daily` (DState.range_pair = the edges); 1H / 15M = the same
rule on that timeframe's swings here. This module turns the edges into two areas and follows their lifecycle.

Structure: each edge = the edge swing's own candle, wick to body (`levels._band_swing`, width 0); later swings that reached it are
`members` (evidence), never widening it. The c13 what-if (two C-13 equal highs + lows) builds the edge as below:
  • the upper edge = the two (or more) "equal" swing HIGHs of the range (C-13 equal: the later extreme reaches the earlier swing candle's
    area and does not go beyond it) ⇒ a RESISTANCE area; the lower edge = the equal swing LOWs ⇒ a SUPPORT area;
  • the area = the extreme (anchor) swing candle's own area, wick to body (`levels._band_swing`, width 0) — the same construction as the
    equal-highs / lows birth "d" in `levels.py`: one base ⇒ the earlier (extreme) swing's band; the other swing candles reacting in it are
    listed as `members` ("inside" ⇒ the same zone, lineage only; "overlaps" ⇒ lineage evidence) and never widen it (Abhi Z-1u / Z-1x).
    Only when the anchor candle has no area at all (a zero-range candle) the members' wick-to-body areas together are the area ("d").
  • later swings of the same kind that are C-13 equal to the anchor (a third touch = triple top / bottom) join the members once
    confirmed (bars ≤ t).
Lifecycle (the levels' own K4 machine, `Levels._step_far_swing`, replayed bar by bar on the 15M bars after the edge is known):
  fresh (no visit since the range was read) / tested (n visits) / broken (a close beyond + a swing formed beyond, far-side swing not
  reached) / flipped (far-side swing reached ⇒ role reversed) / dead (a flipped edge broken again past its far swing). A sweep (beyond and
  back before any swing forms beyond) is counted as ★, never a break.
Trade side at each edge: lower edge ⇒ bull put, upper edge ⇒ bear call (`daily.trade_side("RANGE")`). A range BREAKOUT (the Daily close
leaves the band ⇒ the range state ends) is CONTEXT only — Abhi does not trade breakouts — reported under `breakout`, never an entry.

Output entries have every key of `Levels.snapshot` (id, tf, role, lo, hi, births, anchor, tests, sweeps, flips, fresh, score, dist, …,
trade_location, not_location_why, state, broken_at, far_swing, flipped_at …) plus `range_edge`, `trade_side`, `lifecycle`, `members`,
`range`, so the entry models arm at the edges (DECISIONS 40: `trade_edges` ⇒ `entry_models.Reader.range_edge_areas`, the current
Daily / 1H range, trade side; `range_edge_areas = off` = what-if).
Timeframes: Daily (trade-side areas), Weekly (context only, Abhi Z-1u). 1H / 15M rectangles: `edges_from_rectangle` (hook for the
rectangle reader, track T4).
No look-ahead: everything at 15M bar t reads Daily / Weekly states with known_at ≤ bar_end[t], pivots confirmed by t and bars ≤ t.
No numbers: no tolerance, no width, no distance — comparisons with the swing candles only. No settings added.
"""
import numpy as np
import pandas as pd

from . import daily as DD
from . import flip as FL
from . import levels as LV

LOWER, UPPER = "lower", "upper"
ROLE = {LOWER: LV.SUP, UPPER: LV.RES}
KIND = {LOWER: "L", UPPER: "H"}
SIDE = {LOWER: "bull_put", UPPER: "bear_call"}
WORD = {FL.ACTIVE: "fresh", FL.TESTED: "tested", FL.BROKEN: "broken", FL.FLIPPED: "flipped", FL.DEAD: "dead"}
BIRTH = "range"                                     # births tag of a range-edge area (levels use "a:D2", "a:D", "b", "c", "d")
TF_STATES = {"D": ("daily", "daily_df"), "W": ("weekly", "weekly_df")}
NO_BREAKOUT = "Abhi does not trade breakouts — a range breakout is context only"


# ------------------------------------------------------------------------------------------------ range episodes (Daily / Weekly)
def _known_states(states, ts):
    """States known at ts (known_at ≤ ts), in order (states are in known_at order)."""
    cur = DD.state_at(states, ts)
    return [] if cur.bar is None or cur.bar < 0 else states[:cur.bar + 1]


def episodes(states, ts):
    """RANGE episodes known at ts: contiguous RANGE states with the same band, oldest first. Each = {first, last, band, after} — after =
    the first state that ended it (None ⇒ still a range at ts)."""
    known = _known_states(states, ts)
    out, cur = [], None
    for x in known:
        if x.trend == "RANGE" and x.band is not None:
            if cur is not None and cur["band"] == x.band and cur["after"] is None:
                cur["last"] = x
                continue
            if cur is not None and cur["after"] is None:
                cur["after"] = x                                           # a new band ends the old range (the new one starts here)
            cur = {"first": x, "last": x, "band": tuple(x.band), "after": None}
            out.append(cur)
        elif cur is not None and cur["after"] is None:
            cur["after"] = x
    return out


def _pair(pivots, kind, edge_px):
    """The two swings of one kind that made the band edge: as `daily.fold_impulse` reads it — the last two of that kind (Q27 and the
    NEUTRAL range both take the last two confirmed). Falls back to the latest consecutive pair whose extreme is the band edge."""
    xs = [p for p in pivots if p.kind == kind]
    if len(xs) < 2:
        return None
    ext = max if kind == "H" else min
    if ext(xs[-1].price, xs[-2].price) == edge_px:
        return [xs[-2], xs[-1]]
    for a, b in reversed(list(zip(xs[:-1], xs[1:]))):
        if ext(a.price, b.price) == edge_px:
            return [a, b]
    return None


def _extreme(ps, kind):
    """The most extreme swing (highest H / lowest L); a tie ⇒ the earlier one."""
    return sorted(ps, key=lambda p: (-p.price if kind == "H" else p.price, p.bar))[0]


def _frame_arrays(df):
    df = df.reset_index(drop=True)
    return {k: df[k].to_numpy(float) for k in ("open", "high", "low", "close")}, pd.to_datetime(df["timestamp"]).reset_index(drop=True)


def _candle_area(kind, o, h, l, c, price):
    return LV._band_swing(kind, o, h, l, c, price, 0.0)                  # wick to body, width 0 (Abhi Z-1x: never widened)


# ------------------------------------------------------------------------------------------------ edge area from its swing candles
def edge_area(members, kind, candle, anchor=None):
    """The edge area from its swing candles. members = swings (kind, price, bar, …) of one kind; candle(p) ⇒ (o, h, l, c) of p's own
    candle. Anchor = the extreme swing (the earlier one under C-13 equal); area = its wick-to-body (`_band_swing`). Returns
    (lo, hi, anchor, rows) — rows = each member's own area and its relation to the edge area (anchor / inside / overlaps / apart)."""
    anchor = _extreme(members, kind) if anchor is None else anchor        # structure: the edge swing itself (a later sweep never anchors)
    areas = {id(p): _candle_area(kind, *candle(p), p.price) for p in members}
    lo, hi = areas[id(anchor)]
    if hi <= lo:                                                            # exactly-equal extremes with no area ("d"): the members' areas
        lo, hi = min(a[0] for a in areas.values()), max(a[1] for a in areas.values())
    rows = []
    for p in sorted(members, key=lambda q: q.bar):
        plo, phi = areas[id(p)]
        rel = "anchor" if p is anchor else ("inside" if lo <= plo and phi <= hi else ("overlaps" if not (phi < lo or plo > hi) else "apart"))
        rows.append({"kind": p.kind, "price": round(float(p.price), 2), "bar": int(p.bar), "area": (round(plo, 2), round(phi, 2)),
                     "relation": rel})
    return float(lo), float(hi), anchor, rows


def _touching(pivots, anchor, candle, upto_bar=None):
    """Structure: later swings of the edge's kind that reached the edge swing candle's area (or swept beyond it) — the edge's reactions
    (evidence; they never move or widen the area)."""
    lo, hi = _candle_area(anchor.kind, *candle(anchor), anchor.price)
    return [p for p in pivots if p.kind == anchor.kind and p.bar > anchor.bar and (upto_bar is None or p.bar <= upto_bar)
            and (p.price >= lo if p.kind == "H" else p.price <= hi)]


def _later_equal(pivots, anchor, members, O, C, upto_bar=None):
    """Later swings of the anchor's kind that are C-13 equal to the anchor (reach its candle's area, not beyond it) — a third touch."""
    have = {(p.kind, p.bar) for p in members}
    out = []
    for p in pivots:
        if p.kind != anchor.kind or (p.kind, p.bar) in have or p.bar <= anchor.bar or (upto_bar is not None and p.bar > upto_bar):
            continue
        if DD.c13_equal(O, C, p.price, anchor.kind, anchor.bar, anchor.price):
            out.append(p)
    return out


# ------------------------------------------------------------------------------------------------ lifecycle (the levels' K4 machine)
def _first_bar(LVS, known_at):
    """The first 15M bar whose close knows `known_at` (0 if known before the window — lifecycle then runs from the window start)."""
    js = np.flatnonzero(LVS.bar_end.to_numpy() >= np.datetime64(pd.Timestamp(known_at)))
    return int(js[0]) if len(js) else None


def lifecycle(LVS, edge, lo, hi, born, t, anchor_px, tf, key):
    """Replay one edge area through `Levels`' own per-bar lifecycle (test counting + K4 `_step_far_swing`) on 15M bars born+1 … t.
    Returns the `Level` (events ≤ t). The `Levels` object is not changed (the edge is not added to it)."""
    L = LV.Level(key, ROLE[edge], float(lo), float(hi), int(born), [BIRTH], anchor_px, tf=tf)
    L.bands.append((int(born), L.lo, L.hi))
    H, Lo, C = LVS.A["high"], LVS.A["low"], LVS.A["close"]
    acc = int(LVS.s["accept_closes"])                                   # read by _step_far_swing only under break_rule = closes (legacy)
    touching, excursion, st = False, {}, {"brk": False, "start": None, "rc": 0, "back": None}
    for b in range(int(born) + 1, int(t) + 1):
        if not L.alive(b):
            break
        role = L.role_at(b - 1)
        inside = Lo[b] <= L.hi and H[b] >= L.lo
        if role == LV.SUP:
            beyond_wick, beyond_close = Lo[b] < L.lo, C[b] < L.lo
        else:
            beyond_wick, beyond_close = H[b] > L.hi, C[b] > L.hi
        if inside and not touching:
            L.events.append((b, "test", ""))
        touching = inside
        LVS._step_far_swing(L, b, role, LVS.known_pivots(b), beyond_wick, beyond_close, excursion, st, acc)
    return L


# ------------------------------------------------------------------------------------------------ snapshot-shaped entry
def _entry(V, L, t, snap, edge, members, rng, current):
    """One edge as a `Levels.snapshot` entry (+ range keys)."""
    LVS = V.levels
    c = float(LVS.A["close"][t])
    sg = LVS.sig1h[t]
    lo, hi = L.lo, L.hi
    dist = 0.0 if lo <= c <= hi else (lo - c if c < lo else c - hi)
    ov = [x for x in snap if not (hi < x["lo"] or lo > x["hi"])]
    conf = [{"tf": x["tf"], "id": x["id"], "lo": x["lo"], "hi": x["hi"]} for x in ov if L.tf in ("1H", "15M") and x["tf"] in ("D", "W")]
    inside_1h = [x["id"] for x in ov if L.tf in ("D", "W") and x["tf"] == "1H" and x.get("state") not in (FL.BROKEN, FL.DEAD)]
    same = [x["id"] for x in ov if x["tf"] == L.tf and x["role"] == L.role_at(t) and x["lo"] == round(lo, 2) and x["hi"] == round(hi, 2)]
    fv = LVS.flip_view(L, t)
    state = fv["state"]
    flipped = L.count("flip", t) > 0
    side = SIDE[edge] if not flipped else None
    loc, why = True, None
    if not current:
        loc, why = False, "range over — " + NO_BREAKOUT
    elif L.tf == "W":
        loc, why = False, "Weekly range edge: context only (Abhi Z-1u)"
    elif state in (FL.BROKEN, FL.DEAD):
        loc, why = False, f"edge {WORD[state]} (K4): not a trade location"
    elif flipped:
        loc, why = False, "edge flipped (role reversed) — no longer this range's edge"
    elif inside_1h:
        loc, why = False, (f"{LV.TF_WORD.get(L.tf, L.tf)} range edge overlapped by 1H zone(s) {inside_1h}: the 1H band is the location "
                           f"(Abhi Z-1u)")
    w = hi - lo
    births = [BIRTH] + (["c"] if flipped else [])
    tests = L.count("test", t)
    ev = [f"range {edge} edge = {len(members)} equal swing {'high' if edge == UPPER else 'low'}s "
          f"({', '.join(format(m['price'], ',.2f') for m in members)}) — area = swing candle {lo:,.2f}–{hi:,.2f} (wick to body)",
          f"{WORD[state]}" + (f" ×{tests}" if state == FL.TESTED else "") + (f", ★{L.count('sweep', t)}" if L.count("sweep", t) else ""),
          (f"{SIDE[edge].replace('_', ' ')} at the {edge} edge" if side else "flipped edge — no range trade side")]
    return {"id": L.id, "uid": getattr(L, "uid", None) or str(L.id), "tf": L.tf, "role": L.role_at(t), "lo": round(lo, 2), "hi": round(hi, 2), "births": births,
            "anchor": L.anchor, "tests": tests, "sweeps": L.count("sweep", t), "flips": L.count("flip", t),
            "fresh": tests == 0, "score": LVS.score(L, t, births, conf), "dist": round(dist, 2),
            "dist_sigma": round(dist / sg, 2) if np.isfinite(sg) and sg > 0 else None,
            "above": lo > c, "below": hi < c, "born_bar": L.born_bar, "provisional_width": False, "width_note": None,
            "width": round(w, 2), "width_sigma": round(w / sg, 2) if np.isfinite(sg) and sg > 0 else None,
            "confluence": conf, "confluence_label": LV.confluence_label(conf), "trade_location": loc, "not_location_why": why,
            "too_wide": False, "lineage": [{"bar": int(L.born_bar), "same_as": i} for i in same], **fv,
            # range keys
            "range_edge": edge, "trade_side": side, "lifecycle": WORD[state], "members": members, "range": rng, "current": current,
            "inside_1h": inside_1h, "same_level": same[0] if same else None, "evidence": ev}


# ------------------------------------------------------------------------------------------------ Daily / Weekly
def _episode_edges(V, t, tf, ep, states, df, snap, current):
    LVS = V.levels
    A, tsx = _frame_arrays(df)
    O, Hh, Ll, C = A["open"], A["high"], A["low"], A["close"]
    first, band = ep["first"], ep["band"]
    born = _first_bar(LVS, first.known_at)
    if born is None or born > t:
        return [], None
    view = ep["last"] if not current else DD.state_at(states, LVS.bar_end.iloc[t])
    pivots_now = [p for p in view.pivots if p.known_at <= LVS.bar_end.iloc[t]]
    rng = {"tf": tf, "band_from": round(float(band[0]), 2), "band_to": round(float(band[1]), 2),
           "since": str(first.day.date()) if first.day is not None else None, "known_bar": int(born),
           "why": first.why, "current": current}
    out = []
    rp = getattr(first, "range_pair", None)                               # structure (daily_range_rule): the two edge swings

    def candle(p):
        return O[p.bar], Hh[p.bar], Ll[p.bar], C[p.bar]
    for edge, edge_px in ((LOWER, band[0]), (UPPER, band[1])):
        kind = KIND[edge]
        end_bar = ep["after"].bar if ep["after"] is not None else None
        if rp is not None:
            anchor0 = rp[0] if kind == "H" else rp[1]
            mem = [anchor0] + _touching(pivots_now, anchor0, candle, end_bar)
        else:                                                              # c13 (what-if): the two equal swings (+ a third touch)
            pair = _pair(first.pivots, kind, float(edge_px))
            if pair is None:
                continue
            anchor0 = None
            mem = pair + _later_equal(pivots_now, _extreme(pair, kind), pair, O, C, upto_bar=end_bar)
        lo, hi, anchor, rows = edge_area(mem, kind, candle, anchor0)
        for r, p in zip(rows, sorted(mem, key=lambda q: q.bar)):
            r["ts"] = str(tsx.iloc[p.bar].date())
            r["known_at"] = str(p.known_at)
        key = f"range:{tf}:{edge}:{int(anchor.bar)}"
        L = lifecycle(LVS, edge, lo, hi, born, t, float(anchor.price), tf, key)
        e = _entry(V, L, t, snap, edge, rows, rng, current)
        e["anchor_ts"] = str(tsx.iloc[anchor.bar].date())
        out.append(e)
    return out, rng


def _breakout(V, ep, df):
    """Context only: how the range ended (the first non-range state)."""
    after = ep["after"]
    if after is None:
        return None
    c = float(df.reset_index(drop=True)["close"].iloc[after.bar])
    lo, hi = ep["band"]
    w = str(after.why or "")
    d = "up" if (w.startswith("range broken up") or (not w.startswith("range broken") and c > hi)) else \
        ("down" if (w.startswith("range broken down") or (not w.startswith("range broken") and c < lo)) else None)
    how = (w if w.startswith("range broken") else f"Daily close {c:,.2f} {'above' if d == 'up' else 'below'} the range") if d else \
        f"structure: {after.trend} ({after.why})"
    return {"dir": d, "day": str(after.day.date()) if after.day is not None else None, "known_at": str(after.known_at),
            "close": round(c, 2), "state_after": after.trend, "why": how, "context_only": True, "note": NO_BREAKOUT}


def read_tf(V, t, tf="D", snap=None):
    """One timeframe's range read at 15M bar t: {tf, state ("range" / "no_range"), edges (current range), last_range (the most recent
    ended range, with its edges' lifecycle — context), breakout (how it ended — context only), evidence}."""
    sk, dk = TF_STATES[tf]
    states, df = getattr(V, sk, None), getattr(V, dk, None)
    out = {"tf": tf, "state": "no_range", "edges": [], "range": None, "last_range": None, "breakout": None, "evidence": []}
    if not states or df is None:
        out["evidence"].append(f"{tf}: no states")
        return out
    ts = V.levels.bar_end.iloc[t]
    eps = episodes(states, ts)
    if not eps:
        return out
    snap = V.levels.snapshot(t) if snap is None else snap
    ep = eps[-1]
    current = ep["after"] is None
    edges, rng = _episode_edges(V, t, tf, ep, states, df, snap, current)
    if current:
        out.update(state="range", edges=edges, range=rng)
        out["evidence"].append(f"{LV.TF_WORD.get(tf, tf)} RANGE {ep['band'][0]:,.2f}–{ep['band'][1]:,.2f}: edges are the areas — "
                               f"bull put at the lower edge, bear call at the upper edge")
    else:
        out["last_range"] = {"range": rng, "edges": edges}
        out["breakout"] = _breakout(V, ep, df)
        if out["breakout"]:
            out["evidence"].append(f"last {LV.TF_WORD.get(tf, tf)} range ended: {out['breakout']['why']} — {NO_BREAKOUT}")
    return out


def read_range_edges(V, t, d=None, tfs=("D", "W")):
    """§2L at 15M bar t. V = a decision3 `V22` (or any object with levels, daily / daily_df, weekly / weekly_df). d = +1 (bull put) ⇒
    the lower edges only, −1 (bear call) ⇒ the upper edges, None ⇒ both. Returns {by_tf: {tf: read_tf}, edges: current-range edges of
    every tf (Daily first), evidence}."""
    by = {tf: read_tf(V, t, tf) for tf in tfs}
    edges = [e for tf in tfs for e in by[tf]["edges"] if d is None or (d > 0 and e["range_edge"] == LOWER) or
             (d < 0 and e["range_edge"] == UPPER)]
    return {"by_tf": by, "edges": edges, "evidence": [x for tf in tfs for x in by[tf]["evidence"]]}


def armable(V, t, d=None):
    """Hook for the entry models (wiring = T9): the current range edges that are trade locations at t (fresh / tested, not broken /
    flipped / dead, not Weekly, no overlapping 1H zone — Z-1u), nearest first. Same dict shape as `Levels.active` entries."""
    xs = [e for e in read_range_edges(V, t, d)["edges"] if e["trade_location"]]
    return sorted(xs, key=lambda e: e["dist"])


# ------------------------------------------------------------------------------------------------ 1H / 15M rectangles (hook for T4)
def edges_from_rectangle(V, t, rect, snap=None, current=True):
    """Hook for the 1H / 15M rectangle reader (T4 `patterns.rectangle`): rect = {"tf": "1H" | "15M", "highs": [swing], "lows": [swing]}
    — swings2-shaped pivots: kind, price, bar (the 15M bar of the extreme) and confirm_bar (the 15M bar whose close confirms it). The
    swing candle is the 15M bar (tf "15M") or its 1H candle as known at the confirmation (tf "1H" — as the levels' (a) birth). The last
    two highs and the last two lows must be C-13 equal (else None — not a rectangle by the method). Returns the two edge entries (same
    shape as the Daily ones) with their lifecycle from the 15M bar the fourth swing is confirmed."""
    tf = rect.get("tf", "1H")
    LVS = V.levels
    hs = sorted([p for p in rect.get("highs", []) if p.confirm_bar <= t], key=lambda p: p.bar)
    ls = sorted([p for p in rect.get("lows", []) if p.confirm_bar <= t], key=lambda p: p.bar)
    if len(hs) < 2 or len(ls) < 2:
        return None

    def candle(p):
        if tf == "1H":
            return LVS._h1_upto(LVS.h1_of[p.bar], p.confirm_bar)   # the 1H candle as known at its confirmation (levels (a))
        return tuple(float(LVS.A[k][p.bar]) for k in ("open", "high", "low", "close"))

    def equal(later, earlier):
        o, h, l, c = candle(earlier)
        return DD.c13_equal([o], [c], later.price, earlier.kind, 0, earlier.price)
    if not (equal(hs[-1], hs[-2]) and equal(ls[-1], ls[-2])):
        return None
    born = max(p.confirm_bar for p in hs[-2:] + ls[-2:])
    snap = LVS.snapshot(t) if snap is None else snap
    rng = {"tf": tf, "band_from": round(min(p.price for p in ls[-2:]), 2), "band_to": round(max(p.price for p in hs[-2:]), 2),
           "since": str(LVS.ts.iloc[born]), "known_bar": int(born), "why": "rectangle: two equal highs + two equal lows (C-13)",
           "current": bool(current)}
    out = []
    for edge, mem in ((LOWER, ls[-2:]), (UPPER, hs[-2:])):
        lo, hi, anchor, rows = edge_area(mem, KIND[edge], candle)
        for r, p in zip(rows, sorted(mem, key=lambda q: q.bar)):
            r["ts"] = str(LVS.ts.iloc[int(p.bar)])
        L = lifecycle(LVS, edge, lo, hi, born, t, float(anchor.price), tf, f"range:{tf}:{edge}:{int(anchor.bar)}")
        e = _entry(V, L, t, snap, edge, rows, rng, bool(current))
        e["anchor_ts"] = str(LVS.ts.iloc[int(anchor.bar)])
        out.append(e)
    return out


# ------------------------------------------------------------------------------------------------ range state from structure (per TF)
# Abhi (21 Oct): the row's `range_state` is read FROM STRUCTURE per timeframe (setting `range_state_rule` = "structure", default):
# `daily_range_rule`'s definition — Daily / Weekly = the RANGE state of `decision3.daily`; 1H = the level-degree (D2) swings on their 1H
# candles / closes; 15M = the finest structure-degree swings (D1) on 15M candles / closes. The breakout is context only. No overlap
# ratio, no candle count, no σ (the legacy §5.3 overlap + doji measure stays only under `range_state_rule` = "overlap"). Not swings2's
# Rhea range.
STATE_TFS = ("D", "1H", "15M")                       # trade-side timeframes, highest first; Weekly = context only
COMPACT = ("id", "range_edge", "tf", "role", "lo", "hi", "lifecycle", "tests", "sweeps", "trade_side", "trade_location",
           "not_location_why")


def _degree_pivots(V, tf):
    """1H ⇒ the levels' degree (D2); 15M ⇒ the finest structure degree with pivots (D1), as `Levels._run` reads "a swing"."""
    res = V.levels.res
    if tf == "1H":
        return list(res["pivots"].get(int(V.levels.s["level_degree"]), []))
    from swings2 import settings as S2
    low = min((res.get("settings") or S2.DEFAULTS).get("structure_degrees", S2.DEFAULTS["structure_degrees"]))
    fin = next((d for d in sorted(res["pivots"]) if d >= low and res["pivots"].get(d)), None)
    return list(res["pivots"].get(fin, [])) if fin is not None else []


def _tf_closes(V, tf):
    """The timeframe's closes on the 15M bar index: 15M = every bar; 1H = only the bar that closes its hour (NaN elsewhere — a 15M close
    beyond an edge that is back inside by the hour's close is a sweep on 1H)."""
    C = np.asarray(V.levels.A["close"], float)
    if tf != "1H":
        return C
    h = np.asarray(V.levels.h1_of)
    last = np.r_[h[1:] != h[:-1], True]
    return np.where(last, C, np.nan)


def _pairs(V, tf):
    """Every adjacent swing pair of the timeframe walked as range edges (structure; cached per V)."""
    cache = V.__dict__.setdefault("_range_pairs_cache", {})
    if tf not in cache:
        cache[tf] = DD.range_pairs(_degree_pivots(V, tf), _tf_closes(V, tf))
    return cache[tf]


def _intraday_candle(V, tf):
    LVS = V.levels
    if tf == "1H":
        return lambda p: LVS._h1_upto(LVS.h1_of[p.bar], p.confirm_bar)   # the 1H candle as known at its confirmation (levels (a))
    return lambda p: tuple(float(LVS.A[k][p.bar]) for k in ("open", "high", "low", "close"))


def _pair_edges(V, t, tf, r, snap, current):
    """The two edge areas of a structural range r (range_walk) at bar t."""
    LVS = V.levels
    candle = _intraday_candle(V, tf)
    known = [p for p in _degree_pivots(V, tf) if p.confirm_bar <= t]
    end_bar = r["broken"].bar if (r["broken"] is not None and r["broken_known"] <= t) else None
    rng = {"tf": tf, "band_from": round(float(r["L"].price), 2), "band_to": round(float(r["H"].price), 2),
           "since": str(LVS.ts.iloc[int(r["known"])]), "known_bar": int(r["known"]),
           "why": "range from structure: after the swing high and the swing low, later swings failed to make a new extreme on both sides",
           "current": bool(current)}
    out = []
    for edge, anchor0 in ((LOWER, r["L"]), (UPPER, r["H"])):
        mem = [anchor0] + _touching(known, anchor0, candle, end_bar)
        lo, hi, anchor, rows = edge_area(mem, KIND[edge], candle, anchor0)
        for row, p in zip(rows, sorted(mem, key=lambda q: q.bar)):
            row["ts"] = str(LVS.ts.iloc[int(p.bar)])
        L = lifecycle(LVS, edge, lo, hi, int(r["known"]), t, float(anchor.price), tf, f"range:{tf}:{edge}:{int(anchor.bar)}")
        e = _entry(V, L, t, snap, edge, rows, rng, bool(current))
        e["anchor_ts"] = str(LVS.ts.iloc[int(anchor.bar)])
        out.append(e)
    return out


def read_intraday(V, t, tf, snap=None):
    """1H / 15M range from that timeframe's own swings at bar t (same output shape as `read_tf`). `daily_range_rule` (shared with the
    Daily / Weekly fold): "structure" (default, Abhi 21 Oct — `daily.range_walk`) / "c13" (two equal highs + two equal lows, what-if)."""
    if V.levels.s.get("daily_range_rule", "structure") == "c13":
        return _read_intraday_c13(V, t, tf, snap)
    out = {"tf": tf, "state": "no_range", "edges": [], "range": None, "last_range": None, "breakout": None, "evidence": []}
    pairs = _pairs(V, tf)
    cur = DD.range_at(pairs, t)
    snap = V.levels.snapshot(t) if snap is None else snap
    if cur is not None:
        edges = _pair_edges(V, t, tf, cur, snap, True)
        out.update(state="range", edges=edges, range=edges[0]["range"])
        out["evidence"].append(f"{tf} RANGE {cur['L'].price:,.2f}–{cur['H'].price:,.2f} (later swings failed to make a new extreme on "
                               f"both sides): edges are the areas — bull put at the lower edge, bear call at the upper edge")
        return out
    last = DD.range_last_broken(pairs, t)
    if last is None:
        return out
    edges = _pair_edges(V, t, tf, last, snap, False)
    b = last["broken"]
    out["last_range"] = {"range": edges[0]["range"], "edges": edges}
    out["breakout"] = {"dir": last["dir"], "day": str(V.levels.ts.iloc[int(last["broken_known"])]), "bar": int(last["broken_known"]),
                       "close": round(float(V.levels.A["close"][int(last["broken_known"])]), 2),
                       "why": f"{tf} range broken {last['dir']}: a close beyond the {'upper' if last['dir'] == 'up' else 'lower'} edge and "
                              f"a swing beyond it ({b.price:,.2f})", "context_only": True, "note": NO_BREAKOUT}
    out["evidence"].append(f"last {tf} range ended: {out['breakout']['why']} — {NO_BREAKOUT}")
    return out


def _read_intraday_c13(V, t, tf, snap=None):
    """c13 what-if: the last two swing highs and lows C-13 equal; ends at a close beyond the band."""
    out = {"tf": tf, "state": "no_range", "edges": [], "range": None, "last_range": None, "breakout": None, "evidence": []}
    known = sorted([p for p in _degree_pivots(V, tf) if p.confirm_bar <= t], key=lambda p: (p.confirm_bar, p.bar))
    hs = [p for p in known if p.kind == "H"][-2:]
    ls = [p for p in known if p.kind == "L"][-2:]
    if len(hs) < 2 or len(ls) < 2:
        return out
    band = (min(p.price for p in ls), max(p.price for p in hs))
    born = max(p.confirm_bar for p in hs + ls)
    C = V.levels.A["close"]
    out_of = [b for b in range(born, t + 1) if C[b] > band[1] or C[b] < band[0]]   # a close beyond the band ends the range (and, at
    # the bar the fourth swing is confirmed, means it never was one — the Daily RANGE too is read only with the close inside its band)
    snap = V.levels.snapshot(t) if snap is None else snap
    edges = edges_from_rectangle(V, t, {"tf": tf, "highs": hs, "lows": ls}, snap=snap, current=not out_of)
    if not edges:
        return out
    rng = edges[0]["range"]
    if not out_of:
        out.update(state="range", edges=edges, range=rng)
        out["evidence"].append(f"{tf} RANGE {band[0]:,.2f}–{band[1]:,.2f} (two equal swing highs + two equal swing lows, C-13): edges "
                               f"are the areas — bull put at the lower edge, bear call at the upper edge")
        return out
    b = out_of[0]
    d = "up" if C[b] > band[1] else "down"
    out["last_range"] = {"range": rng, "edges": edges}
    out["breakout"] = {"dir": d, "day": str(V.levels.ts.iloc[b]), "bar": int(b), "close": round(float(C[b]), 2),
                       "why": f"{tf} close {C[b]:,.2f} {'above' if d == 'up' else 'below'} the range", "context_only": True,
                       "note": NO_BREAKOUT}
    out["evidence"].append(f"last {tf} range ended: {out['breakout']['why']} — {NO_BREAKOUT}")
    return out


def _compact(x):
    br = x.get("breakout")
    rg = x.get("range") or (x.get("last_range") or {}).get("range") or {}
    return {"state": x["state"], "band": [rg.get("band_from"), rg.get("band_to")] if rg else None, "since": rg.get("since"),
            "edges": [{k: e.get(k) for k in COMPACT} for e in (x["edges"] or (x.get("last_range") or {}).get("edges") or [])],
            "breakout": None if not br else {k: br.get(k) for k in ("dir", "day", "close", "why", "context_only")}}


def range_state(V, t):
    """The row's `range_state` from structure (setting `range_state_rule` = "structure"), per timeframe — plain dict:
    {rule, in_range, tf (the highest trade-side timeframe in range: D > 1H > 15M, or None), tfs_in_range, edges (that timeframe's edge
    areas, compact), by_tf {W, D, 1H, 15M: {state, band, since, edges, breakout}}, note}. Weekly = context only. Cached per bar on V."""
    if getattr(V, "levels", None) is None:                                 # no area engine (a stub / partial V) ⇒ not read
        return None
    cache = V.__dict__.setdefault("_range_state_cache", {})
    if t in cache:
        return cache[t]
    snap = V.levels.snapshot(t)
    by = {"W": read_tf(V, t, "W", snap), "D": read_tf(V, t, "D", snap)}
    for tf in ("1H", "15M"):
        by[tf] = read_intraday(V, t, tf, snap)
    V.__dict__.setdefault("_range_edges_full", {})[t] = {k: list(by[k]["edges"]) for k in by}   # trade_edges (DECISIONS 40)
    in_r = [tf for tf in STATE_TFS if by[tf]["state"] == "range"]
    tf = in_r[0] if in_r else None
    out = {"rule": "structure", "in_range": bool(in_r), "tf": tf, "tfs_in_range": in_r,
           "edges": [{k: e.get(k) for k in COMPACT} for e in by[tf]["edges"]] if tf else [],
           "by_tf": {k: _compact(by[k]) for k in ("W", "D", "1H", "15M")},
           "note": "range from structure: after a swing high and a swing low, later swings fail to make a new extreme on both "
                   "sides; edges = areas (range_edges); a breakout is context only"}
    cache[t] = out
    return out


def trade_edges(V, t, tfs=("D", "1H")):
    """DECISIONS 40 (concept L): the edges of the CURRENT range of each timeframe in `tfs`, read from structure exactly as the row's
    `range_state` reads them (same cache), that are trade locations at t (fresh / tested; not broken / flipped / dead; not Weekly; a
    Daily edge overlapped by an alive 1H zone gives the 1H zone — Z-1u). Full `Levels.snapshot`-shaped dicts (+ range keys) for the
    entry models. Bars ≤ t only."""
    range_state(V, t)
    full = (V.__dict__.get("_range_edges_full") or {}).get(t) or {}
    return [e for tf in tfs for e in full.get(tf, []) if e.get("current") and e.get("trade_location")]


# ------------------------------------------------------------------------------------------------ chart objects (T8)
AREA_STATE = {"fresh": "active", "tested": "tested", "broken": "broken", "flipped": "flipped", "dead": "dead"}   # T8 area vocabulary


def _ts(x):
    return None if x is None else str(pd.Timestamp(x))


def draw_objects(V, t, tfs=("D", "W")):
    """Chart objects at 15M bar t (T8 schema {kind, tf, t0, t1, p0, p1, label, state, style_key, evidence}): each edge area of the
    current (or the last ended) range per tf — kind "area", style "area.range_edge", t0 = the anchor swing candle, p0 / p1 = the area —
    and the breakout (context only) as kind "pattern" / "pattern.range_breakout", the broken edge's price from the range's start to the
    breakout day."""
    r = read_range_edges(V, t, None, tfs)
    t1 = _ts(V.levels.ts.iloc[t])
    out = []
    for tf in tfs:
        x = r["by_tf"][tf]
        edges = x["edges"] or ((x["last_range"] or {}).get("edges") or [])
        for e in edges:
            word = "support" if e["range_edge"] == LOWER else "resistance"
            side = e["trade_side"].replace("_", " ") if e["trade_side"] else "no trade side"
            lab = (f"{LV.TF_WORD.get(tf, tf)} range {e['range_edge']} edge ({word}) {e['lo']:,.0f}-{e['hi']:,.0f}, {e['lifecycle']}"
                   + (f" x{e['tests']}" if e["lifecycle"] == "tested" else "") + f" - {side}" + ("" if e["current"] else " (range over)"))
            out.append({"kind": "area", "tf": tf, "t0": _ts(e.get("anchor_ts")), "t1": t1, "p0": e["lo"], "p1": e["hi"], "label": lab,
                        "state": AREA_STATE[e["lifecycle"]], "style_key": "area.range_edge", "evidence": e["evidence"]})
        b = x.get("breakout")
        if b:
            rng = (x["last_range"] or {}).get("range") or {}
            px = rng.get("band_to") if b["dir"] == "up" else rng.get("band_from")
            px = b["close"] if px is None or b["dir"] is None else px
            out.append({"kind": "pattern", "tf": tf, "t0": _ts(rng.get("since") or b["day"]), "t1": _ts(b["day"]), "p0": px, "p1": px,
                        "label": f"{LV.TF_WORD.get(tf, tf)} range broken {b['dir'] or ''} - context only (no breakout trade)".replace("  ", " "),
                        "state": "broken", "style_key": "pattern.range_breakout", "evidence": [b["why"], b["note"]]})
    return out
