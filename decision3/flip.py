"""decision3/flip.py — KB K4 / G4 (Abhi's final flip rule): BROKEN vs FLIPPED, and the flip-retest checks.

Rule (KB K4 "A broken zone flips [Abhi]" / "Broken, not flipped [Abhi]" / "Flip retest (G4 / S4) [Abhi]"):
  • A zone FLIPS role when price goes beyond it AND past the swing on the far side. Reaching that swing is the proof; there is no extra
    candle condition. Until then the zone keeps its old role (sweep).
  • Beyond the zone (real break, decision3's `accept_closes` acceptance) but the far-side swing not reached ⇒ BROKEN. Its retest is NOT
    a trade location; wait.
  • FLIPPED ⇒ the reversal from that swing back into the flipped area is a PULLBACK and the area is a trade location, but entry needs
    (a) the pullback is corrective (zigzag / flat / triangle, by anatomy + structure), not impulsive against the flip;
    (b) the pullback as a whole has LOWER FUT volume than the impulse leg that made the flip (judged as a whole);
    (c) the zone criteria at the area (handover a2, dominant commitment with higher FUT volume c0, LTF CHoCH c1) — engine ⑥, unchanged.
    An impulsive or high-volume return ⇒ no trade.

Owners (no new classifier, no new volume source):
  • far-side swing = the swing source the 1H levels already use (swings2 D`level_degree` pivots, confirmed by t).
  • (a) = `decision3.daily_legs.classify` (legs2 anatomy C + patterns2 / read_counter structure, elliott=True) — the classifier decision3
    already calls; reader2 is not imported (boundary).
  • (b) = near-month FUT 5M volume summed onto the 15M spot bars by `opportunity_engine.volume` (near_month_rows + attach_futures_volume).
No look-ahead: everything at bar t reads bars ≤ t and pivots with confirm_bar ≤ t; the pullback volume window stops at t − 1 (bar t is
the commitment candle, judged by ⑥ c0).
"""
import numpy as np
import pandas as pd

from . import daily_legs as DL

ACTIVE, TESTED, BROKEN, FLIPPED, DEAD = "ACTIVE", "TESTED", "BROKEN", "FLIPPED", "DEAD"
RULES = ("far_swing", "acceptance")


# ------------------------------------------------------------------------------------------------ far-side swing
def far_swing(known, lo, hi, up, start=None):
    """The nearest confirmed swing beyond [lo, hi] on the break side: up (a resistance broken upward) ⇒ the lowest known swing HIGH above
    hi; down ⇒ the highest known swing LOW below lo. `known` = pivots confirmed by the bar being judged (caller's list). Only swings that
    formed before the excursion began (pivot bar < start) count — a swing made by the break move itself is not "the swing on the far side".
    Returns the pivot or None."""
    if up:
        c = [p for p in known if p.kind == "H" and p.price > hi and (start is None or p.bar < start)]
        return min(c, key=lambda p: p.price) if c else None
    c = [p for p in known if p.kind == "L" and p.price < lo and (start is None or p.bar < start)]
    return max(c, key=lambda p: p.price) if c else None


# ------------------------------------------------------------------------------------------------ FUT volume (opportunity_engine.volume)
def fut_volume_15m(m15, fut5, ltf_minutes=5):
    """Near-month FUT 5M volume on the 15M spot bars through the volume owner (opportunity_engine.volume: near_month_rows, then
    attach_futures_volume = 09:15-anchored 15M sums). 0 / no FUT row ⇒ NaN; a 15M bar with fewer FUT 5M children than its 5M slots ⇒ NaN
    (under-counted, never a guess). fut5 None / empty ⇒ None."""
    if fut5 is None or not len(fut5):
        return None
    from opportunity_engine import volume as OV
    st = pd.to_datetime(m15["timestamp"]).reset_index(drop=True)
    en = pd.to_datetime(m15["bar_end"]).reset_index(drop=True) if "bar_end" in m15.columns else st + pd.Timedelta(minutes=15)
    fut = OV.near_month_rows(fut5)
    if fut is None or not len(fut):
        return None
    ft = pd.to_datetime(fut["timestamp"])
    f5 = pd.DataFrame({"bar_start": ft.drop_duplicates().sort_values().reset_index(drop=True)})
    f15 = pd.DataFrame({"timestamp": st, "bar_start": st})
    frames, _cov = OV.attach_futures_volume({"5m": f5, "15m": f15}, fut)
    v = np.array(frames["15m"]["volume"].to_numpy(float), dtype=float)
    v[~(v > 0)] = np.nan
    ftv = ft.to_numpy()
    pos = np.searchsorted(st.to_numpy(), ftv, side="right") - 1
    ok = (pos >= 0) & (ftv < en.to_numpy()[np.clip(pos, 0, len(st) - 1)])
    kids = pd.Series(ftv[ok]).groupby(pos[ok]).nunique()
    slot = pd.Timedelta(minutes=int(ltf_minutes))
    for i in range(len(st)):
        need = int((en.iloc[i] - st.iloc[i]) / slot)
        got = int(kids.get(i, 0))
        if 0 < got < need:
            v[i] = np.nan
    return v


# ------------------------------------------------------------------------------------------------ G4 flip retest (a) + (b)
def legs_arrays(A, ts):
    """decision3 15M arrays ⇒ the legs2 candle-metrics layout (o, h, l, c, first = first bar of a session; legs2 drops the overnight gap)."""
    day = pd.to_datetime(pd.Series(ts)).dt.normalize().to_numpy()
    first = np.r_[True, day[1:] != day[:-1]] if len(day) else np.zeros(0, bool)
    return {"o": A["open"], "h": A["high"], "l": A["low"], "c": A["close"], "first": first}


def _ts(ts, i):
    return str(pd.Timestamp(ts[int(i)]))


def flip_retest(A, ts, t, lvl, pivots, s, vol=None, vol_src=None, legs_A=None):
    """G4 facts for a FLIPPED level at decision bar t (price at the area). lvl = Levels.snapshot row (break_dir, flipped_at, exc_start,
    born_bar). pivots = swings2 pivots dict {degree: [pivot]}. vol = FUT volume per 15M bar (NaN = missing) or None.
    Returns {"a": True / False / None, "b": True / False / None, "why", "a_why", "b_why", "pullback", "impulse", "a_read", "b_read"}.
    (a) None = structure not readable yet (wait); (b) None = NA (FUT volume missing; engine applies `flip_volume_na`)."""
    H, L = A["high"], A["low"]
    up = int(lvl.get("break_dir") or 0) > 0
    tf, x0 = lvl.get("flipped_at"), lvl.get("exc_start")
    out = {"a": None, "b": None, "a_why": "", "b_why": "", "pullback": None, "impulse": None, "a_read": None, "b_read": None}
    if tf is None or x0 is None or tf > t:
        out["why"] = out["a_why"] = out["b_why"] = "flip facts missing"
        return out
    tf, x0 = int(tf), int(x0)
    deg = int(s["level_degree"])
    seq = sorted(pivots.get(deg, []), key=lambda p: p.confirm_bar)
    inner = list(pivots.get(int(s["flip_pullback_inner_degree"]) if s.get("flip_pullback_inner_degree") is not None else deg - 1, []))
    # pullback start = the flip extreme (the far-swing side extreme from the flip bar up to t)
    seg = np.arange(tf, t + 1)
    ext_bar = int(seg[np.argmax(H[seg])] if up else seg[np.argmin(L[seg])])
    ext_px = float(H[ext_bar] if up else L[ext_bar])
    # impulse that made the flip: from the opposite extreme before the excursion (from the last known opposite swing, else the level's
    # birth bar) to the flip extreme
    opp = [p for p in seq if p.confirm_bar <= t and p.kind == ("L" if up else "H") and p.bar < x0]
    s0 = int(opp[-1].bar) if opp else int(lvl.get("born_bar") or 0)
    s0 = min(s0, x0)
    iseg = np.arange(s0, x0 + 1)
    imp_bar = int(iseg[np.argmin(L[iseg])] if up else iseg[np.argmax(H[iseg])])
    imp_px = float(L[imp_bar] if up else H[imp_bar])
    out["impulse"] = {"from_bar": imp_bar, "from_ts": _ts(ts, imp_bar), "from_price": round(imp_px, 2), "to_bar": ext_bar,
                      "to_ts": _ts(ts, ext_bar), "to_price": round(ext_px, 2)}
    if ext_bar >= t:
        out["a_why"] = out["b_why"] = "no pullback yet (the flip extreme is the decision bar)"
        out["why"] = "G4: " + out["a_why"]
        return out
    pseg = np.arange(ext_bar + 1, t + 1)
    pb_bar = int(pseg[np.argmin(L[pseg])] if up else pseg[np.argmax(H[pseg])])
    pb_px = float(L[pb_bar] if up else H[pb_bar])
    out["pullback"] = {"from_bar": ext_bar, "from_ts": _ts(ts, ext_bar), "from_price": round(ext_px, 2), "to_bar": pb_bar,
                       "to_ts": _ts(ts, pb_bar), "to_price": round(pb_px, 2)}
    # (a) anatomy + structure — decision3.daily_legs.classify (legs2 C + read_counter), pivots confirmed by t only
    LA = legs_A if legs_A is not None else legs_arrays(A, ts)
    if pb_bar <= ext_bar:
        out["a_why"] = "pullback has no bar yet"
    else:
        c = DL.classify(LA, seq, ext_bar, ext_px, pb_bar, pb_px, t, inner_seq=inner, elliott=True)
        out["a_read"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items()}
        out["a"] = True if c["kind"] == "corrective" else (False if c["kind"] == "impulse" else None)
        word = {True: "corrective", False: "IMPULSIVE against the flip", None: "not readable yet (unclear)"}[out["a"]]
        out["a_why"] = f"(a) pullback {word}: {DL.tag(c)}, {c['n']} inner waves"
    # (b) FUT volume: pullback bars (ext, t − 1] as a whole vs impulse bars (impulse start, ext]
    ib = list(range(imp_bar + 1, ext_bar + 1))
    pb = list(range(ext_bar + 1, t))
    if vol is None:
        out["b_why"] = "(b) NA: FUT volume missing (no near-month FUT 5M bars given)"
    elif not pb or not ib:
        out["b_why"] = "(b) NA: " + ("pullback has no closed bar before the decision bar" if not pb else "impulse leg has no bar")
    else:
        v = np.asarray(vol, float)
        ok_i = [i for i in ib if np.isfinite(v[i]) and v[i] > 0]
        ok_p = [i for i in pb if np.isfinite(v[i]) and v[i] > 0]
        cov = min(len(ok_i) / len(ib), len(ok_p) / len(pb))
        need = float(s["flip_vol_min_coverage"])
        if cov < need or not ok_i or not ok_p:
            out["b_why"] = (f"(b) NA: FUT volume missing on {len(ib) - len(ok_i)}/{len(ib)} impulse and {len(pb) - len(ok_p)}/{len(pb)} "
                            f"pullback bars (coverage {cov:.2f} < {need:g})")
        else:
            pa, ia = float(np.mean(v[ok_p])), float(np.mean(v[ok_i]))
            r = pa / ia if ia > 0 else float("inf")
            lim = float(s["flip_pullback_vol_ratio"])
            out["b"] = bool(r < lim)
            out["b_read"] = {"pullback_avg": round(pa, 1), "impulse_avg": round(ia, 1), "ratio": round(r, 3), "limit": lim,
                             "pullback_bars": len(pb), "impulse_bars": len(ib), "source": vol_src}
            out["b_why"] = (f"(b) pullback FUT volume {'LOWER' if out['b'] else 'NOT lower'} than the flip impulse: avg {pa:,.0f} vs "
                            f"{ia:,.0f} (ratio {r:.2f}, needs < {lim:g})")
    out["why"] = "G4 flip retest: " + " · ".join(x for x in (out["a_why"], out["b_why"]) if x)
    return out
