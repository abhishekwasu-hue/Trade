"""decision3/flip.py — KB K4 / G4 (Abhi's final flip rule, Z-1): BROKEN vs FLIPPED, the approach context, the in-zone read.

Rule (KB K4 "A broken zone flips [Abhi]" / "Broken, not flipped [Abhi]"; G4; Abhi final answers Z-1a … Z-1f):
  • A zone FLIPS role when price goes beyond it AND past the swing on the far side (reaching it is the proof; no candle condition).
    No swing beyond the zone (new highs / lows) ⇒ the far-side swing is the first swing FORMED after the break, and reaching it means
    that swing being CONFIRMED — it does not have to be broken (Abhi Z-1s, the corrected Z-1a wording): e.g. a confirmed swing low
    below a broken support flips it at that confirmation. A swing that existed beyond the zone before the break must still be passed.
  • Beyond the zone (acceptance) but the far-side swing not reached ⇒ BROKEN: not a trade location; wait.
  • Once flipped the old role ends: a FLIPPED zone broken again past its far-side swing (no swing beyond ⇒ the first swing after that
    break confirmed, Z-1s) is DEAD — no second flip (Z-1f).
  • FLIPPED ⇒ the return into the area is a trade location. HOW price approaches (corrective or not, lower volume or not) is CONTEXT
    only (Z-1d) — reported, never a gate. The decision is the in-zone study after price enters the zone: candle sizes by side, FUT volume
    per candle (time-of-day normalised, per-bar averages), patterns inside the zone, which side grows / shrinks, selling (buying) volume
    expanding, RSI divergence (evidence) — then the dominant commitment candle with higher volume + LTF CHoCH = entry (engine ⑥: a2 + c0
    + c1). Unclear in-zone study ⇒ wait.

Owners (no new classifier, no new volume source): far-side swing = swings2 D`level_degree` pivots (the 1H levels' own source);
approach (a) = `decision3.daily_legs.classify` (legs2 anatomy C + read_counter; reader2 not imported); volume = the engine's per-bar
FUT volume — raw bars (method §3; the legacy `volume_baseline = slot` divides by the time-of-day slot median); in-zone study = `decision3.method.zone_study` /
`zone_pattern`; RSI divergence = `rsi2.engine.Divergence` (facts only).
No look-ahead: everything at bar t reads bars ≤ t and pivots with confirm_bar ≤ t.
"""
import numpy as np
import pandas as pd

from . import daily_legs as DL

ACTIVE, TESTED, BROKEN, FLIPPED, DEAD = "ACTIVE", "TESTED", "BROKEN", "FLIPPED", "DEAD"
RULES = ("far_swing", "acceptance")


# ------------------------------------------------------------------------------------------------ far-side swing
def structural(close, lo, hi, up):
    """Abhi Z-1y: a swing beyond the band counts as a STRUCTURAL far-side swing only if its own candle closed beyond the band too. A swing
    whose candle closed back inside / on the role's side (up: close ≤ hi; down: close ≥ lo) is a sweep wick of this band (K5), not a
    structural swing — using it would flip the zone on every false break. close None (not known) ⇒ kept (old callers)."""
    if close is None or not np.isfinite(close):
        return True
    return bool(close > hi) if up else bool(close < lo)


def far_swing(known, lo, hi, up, start=None, closes=None):
    """The far-side swing for a break of [lo, hi]: up (a resistance broken upward) ⇒ swing HIGHs above hi; down ⇒ swing LOWs below lo,
    of the level's own structural degree (`known` = the caller's pivots of that degree, confirmed by the bar being judged). closes (the
    15M closes by bar) ⇒ sweep wicks of this band are not structural swings (Abhi Z-1y, `structural`).
      1. the nearest such swing that formed before the excursion began (pivot bar < start; start None ⇒ any bar);
      2. none (the zone is at new highs / lows) ⇒ the FIRST CONFIRMED such swing that formed after the break began (Abhi, Z-1a).
    Returns the pivot or None. Whether it is reached: `reached` (Abhi Z-1s — source 2 is reached by its confirmation)."""
    kind = "H" if up else "L"
    beyond = [p for p in known if p.kind == kind and (p.price > hi if up else p.price < lo)
              and (closes is None or structural(float(closes[int(p.bar)]), lo, hi, up))]
    pre = [p for p in beyond if start is None or p.bar < start]
    if pre:
        return min(pre, key=lambda p: p.price) if up else max(pre, key=lambda p: p.price)
    if start is None:
        return None
    post = [p for p in beyond if p.bar >= start]
    return min(post, key=lambda p: (p.confirm_bar, p.bar)) if post else None


def swing_source(p, start):
    return None if p is None else ("before_break" if start is None or p.bar < start else "first_confirmed_after_break")


def reached(src, price, extreme, up):
    """Abhi Z-1s: is the far-side swing reached at this bar? A swing that existed beyond the zone before the break ("before_break") ⇒
    only when price trades past it (extreme = the bar's high for an up break / low for a down break). The first swing formed after the
    break ("first_confirmed_after_break", no swing beyond the zone — new highs / lows) ⇒ reached by its CONFIRMATION (the caller only
    passes swings confirmed by the bar being judged); it does not have to be broken."""
    if src == "first_confirmed_after_break":
        return True
    return bool(extreme > price) if up else bool(extreme < price)


# ------------------------------------------------------------------------------------------------ approach context (G4, facts only)
def legs_arrays(A, ts):
    """decision3 15M arrays ⇒ the legs2 candle-metrics layout (o, h, l, c, first = first bar of a session; legs2 drops the overnight gap)."""
    day = pd.to_datetime(pd.Series(ts)).dt.normalize().to_numpy()
    first = np.r_[True, day[1:] != day[:-1]] if len(day) else np.zeros(0, bool)
    return {"o": A["open"], "h": A["high"], "l": A["low"], "c": A["close"], "first": first}


def _ts(ts, i):
    return str(pd.Timestamp(ts[int(i)]))


def approach_context(A, ts, t, lvl, pivots, s, legs_A=None):
    """G4 CONTEXT (Abhi Z-1d: never a gate) for a FLIPPED level at bar t: how price came back into the flipped area.
    (a) pullback shape by `daily_legs.classify` (corrective / impulse / unclear); (b) the pullback's average time-of-day-normalised FUT
    volume per bar vs the flip impulse's (A["volume"] = the engine's normalised volume). Returns facts: a, b (True / False / None),
    a_why, b_why, why, pullback, impulse, a_read, b_read. Nothing here changes a decision."""
    H, L = A["high"], A["low"]
    up = int(lvl.get("break_dir") or 0) > 0
    tf, x0 = lvl.get("flipped_at"), lvl.get("exc_start")
    out = {"context_only": True, "a": None, "b": None, "a_why": "", "b_why": "", "pullback": None, "impulse": None, "a_read": None,
           "b_read": None}
    if tf is None or x0 is None or tf > t:
        out["why"] = out["a_why"] = out["b_why"] = "flip facts missing"
        return out
    tf, x0 = int(tf), int(x0)
    deg = int(s["level_degree"])
    seq = sorted(pivots.get(deg, []), key=lambda p: p.confirm_bar)
    inner = list(pivots.get(int(s["flip_pullback_inner_degree"]), []))
    seg = np.arange(tf, t + 1)
    ext_bar = int(seg[np.argmax(H[seg])] if up else seg[np.argmin(L[seg])])
    ext_px = float(H[ext_bar] if up else L[ext_bar])
    opp = [p for p in seq if p.confirm_bar <= t and p.kind == ("L" if up else "H") and p.bar < x0]
    s0 = min(int(opp[-1].bar) if opp else int(lvl.get("born_bar") or 0), x0)
    iseg = np.arange(s0, x0 + 1)
    imp_bar = int(iseg[np.argmin(L[iseg])] if up else iseg[np.argmax(H[iseg])])
    imp_px = float(L[imp_bar] if up else H[imp_bar])
    out["impulse"] = {"from_bar": imp_bar, "from_ts": _ts(ts, imp_bar), "from_price": round(imp_px, 2), "to_bar": ext_bar,
                      "to_ts": _ts(ts, ext_bar), "to_price": round(ext_px, 2)}
    if ext_bar >= t:
        out["a_why"] = out["b_why"] = "no pullback yet (the flip extreme is the decision bar)"
        out["why"] = "G4 context: " + out["a_why"]
        return out
    pseg = np.arange(ext_bar + 1, t + 1)
    pb_bar = int(pseg[np.argmin(L[pseg])] if up else pseg[np.argmax(H[pseg])])
    pb_px = float(L[pb_bar] if up else H[pb_bar])
    out["pullback"] = {"from_bar": ext_bar, "from_ts": _ts(ts, ext_bar), "from_price": round(ext_px, 2), "to_bar": pb_bar,
                       "to_ts": _ts(ts, pb_bar), "to_price": round(pb_px, 2)}
    LA = legs_A if legs_A is not None else legs_arrays(A, ts)
    c = DL.classify(LA, seq, ext_bar, ext_px, pb_bar, pb_px, t, inner_seq=inner, elliott=True)
    out["a_read"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items()}
    out["a"] = True if c["kind"] == "corrective" else (False if c["kind"] == "impulse" else None)
    word = {True: "corrective", False: "impulsive against the flip", None: "unclear"}[out["a"]]
    out["a_why"] = f"(a) approach {word}: {DL.tag(c)}, {c['n']} inner waves"
    ib = list(range(imp_bar + 1, ext_bar + 1))
    pb = list(range(ext_bar + 1, t))
    v = A.get("volume")
    if v is None:
        out["b_why"] = "(b) NA: no FUT volume"
    elif not pb or not ib:
        out["b_why"] = "(b) NA: " + ("pullback has no closed bar before the decision bar" if not pb else "impulse leg has no bar")
    else:
        v = np.asarray(v, float)
        ok_i = [i for i in ib if np.isfinite(v[i]) and v[i] > 0]
        ok_p = [i for i in pb if np.isfinite(v[i]) and v[i] > 0]
        cov = min(len(ok_i) / len(ib), len(ok_p) / len(pb))
        need = float(s["flip_vol_min_coverage"])
        if cov < need or not ok_i or not ok_p:
            out["b_why"] = (f"(b) NA: normalised FUT volume missing on {len(ib) - len(ok_i)}/{len(ib)} impulse and "
                            f"{len(pb) - len(ok_p)}/{len(pb)} pullback bars (coverage {cov:.2f} < {need:g})")
        else:
            pa, ia = float(np.mean(v[ok_p])), float(np.mean(v[ok_i]))
            r = pa / ia if ia > 0 else float("inf")
            lim = float(s["flip_pullback_vol_ratio"])
            out["b"] = bool(r < lim)
            out["b_read"] = {"pullback_avg_rel": round(pa, 3), "impulse_avg_rel": round(ia, 3), "ratio": round(r, 3), "limit": lim,
                             "pullback_bars": len(pb), "impulse_bars": len(ib), "measure": "per-bar average of slot-normalised FUT volume"}
            out["b_why"] = (f"(b) approach volume {'lower' if out['b'] else 'not lower'} than the flip impulse: {pa:.2f}× vs {ia:.2f}× "
                            f"slot median per bar (ratio {r:.2f})")
    out["why"] = "G4 context (not a gate): " + " · ".join(x for x in (out["a_why"], out["b_why"]) if x)
    return out


# ------------------------------------------------------------------------------------------------ in-zone read (facts)
def zone_read(A, ts, arm, t, d, lvl, s, rsi=None, handover=None):
    """The in-zone study as facts, bar by bar, from zone entry (`arm`) to the decision bar t (bars ≤ t): per candle — time, side
    (trade side / counter side / doji), body vs the window's average body, raw and time-of-day-normalised FUT volume, in the zone or
    not; plus the zone_study summary (which side grows / shrinks, handover / absorption, volume rising on which side), the pattern, and
    the counter-side volume first half → second half. rsi = an rsi2 Divergence read summary (optional). handover = the sticky per-episode
    handover (Abhi Z-1q, `method.handover_episode`) — reported as `handover_sticky`; `handover` stays the read of window arm … t − 1. Facts
    only."""
    from . import method as M
    o, h, lo_, c = A["open"], A["high"], A["low"], A["close"]
    V = A.get("volume")                                                    # what the comparisons use (normalised, or raw fallback)
    R = A.get("volume_raw")
    Rel = A["volume_rel"] if "volume_rel" in A else V
    arm, t = int(arm), int(t)
    w = list(range(arm, t + 1))
    bodies = [abs(c[i] - o[i]) for i in w]
    mb = float(np.mean(bodies)) if bodies else 0.0
    rows = []
    for i in w:
        side = "doji" if M.candle_read(A, i, s)["doji"] else ("trade side" if (c[i] - o[i]) * d > 0 else "counter side")
        rows.append({"bar": i, "time": _ts(ts, i), "side": side, "body_vs_window": round(abs(c[i] - o[i]) / mb, 2) if mb > 0 else None,
                     "vol_raw": None if R is None or not np.isfinite(R[i]) else round(float(R[i]), 0),
                     "vol_rel": None if Rel is None or not np.isfinite(Rel[i]) else round(float(Rel[i]), 2),
                     "vol_used": None if V is None or not np.isfinite(V[i]) else round(float(V[i]), 2),
                     "in_zone": bool(lo_[i] <= lvl["hi"] and h[i] >= lvl["lo"])})
    zs = M.zone_study(A, arm, t - 1, d, s) if t - 1 >= arm else {}

    def half(sel):
        x = [r["vol_used"] for r in sel if r["vol_used"] is not None]
        return round(float(np.mean(x)), 2) if x else None
    pre = rows[:-1]
    m = len(pre) // 2
    cs = [r for r in pre if r["side"] == "counter side"]
    ts_ = [r for r in pre if r["side"] == "trade side"]
    cs1, cs2 = [r for r in pre[:m] if r["side"] == "counter side"], [r for r in pre[m:] if r["side"] == "counter side"]
    summary = {"bars": len(rows), "trade_side_bars": len(ts_), "counter_side_bars": len(cs),
               "trade_side_vol_avg": half(ts_), "counter_side_vol_avg": half(cs),
               "counter_vol_first_half": half(cs1), "counter_vol_second_half": half(cs2),
               "counter_volume_expanding": None if half(cs1) is None or half(cs2) is None else bool(half(cs2) > half(cs1)),
               "trade_side_growing": zs.get("trade_growing", zs.get("trend_growing")), "counter_side_weakening": zs.get("counter_weakening"),
               "counter_side_gone": zs.get("counter_gone"), "handover": zs.get("handover"),
               "handover_sticky": handover, "absorption": zs.get("absorption"), "vol_rising_trade_side": zs.get("vol_trend_rising"),
               "pattern": zs.get("pattern") or M.zone_pattern(A, arm, t, d, s), "line": zs.get("line"),
               "commit_bar": rows[-1] if rows else None, "rsi_divergence": rsi}
    return {"from": _ts(ts, arm), "to": _ts(ts, t), "candles": rows, "summary": summary,
            "volume_measure": "raw FUT volume per bar" if (s or {}).get("volume_baseline", "raw") == "raw" else
            "bar FUT volume ÷ median of the same 15M slot over the previous sessions (vol_slot_sessions)"}
