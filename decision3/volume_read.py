"""decision3/volume_read.py — PA standard §2I: volume reads on the near-month FUT volume (indices), comparative only.

EVIDENCE / STATE only: nothing here blocks or triggers an entry. Volume = the engine's raw per-bar FUT volume (`V.levels.A["volume_raw"]`,
legs2.volume.bar_volume near-month join; method §3 Volume: raw bars, per-bar AVERAGES — never sums, never a time-of-day baseline). Bars
without FUT volume never count as zero: they are left out of every average and reported (`gaps`). No FUT volume at all ⇒ every read is NA.

Legs = the swings of one swings2 degree (default `tl_degree`, the pullback degree D1) CONFIRMED by bar t, in bar order (two swings of the
same kind in a row ⇒ the more extreme one). The current leg runs from the last confirmed swing to bar t.

  • pullback_vs_impulse — the pullback (the current leg, or the approach into an area visit) vs the leg it pulls back from (the impulse):
    per-bar average volume lower / higher / equal. Lower = the method's "pullback on lower volume than the impulse".
  • climax — the largest-volume candle of a leg, a large candle (range above the leg's earlier candles' average: `method.candle_read`
    big_range), on which the leg made its extreme, and after it no candle went beyond that extreme (no progress). Read on the completed
    leg (the climax that ended it, at its swing) and on the current leg (holding / forming).
  • effort_result — effort = per-bar average volume, result = progress per bar (start swing to the leg's extreme ÷ its candles). The
    current leg vs the previous leg in the same direction: more effort, less result ⇒ "effort without result"; less effort, more result
    ⇒ "result with ease"; otherwise "in harmony". Also candle t vs the current leg's earlier candles: volume above their average with a
    body not above their average ⇒ "effort without result (candle)".
  • absorption — the existing method reader, called read-only: `method.zone_study(...)["absorption"]` over the current visit to the area
    (`V.visit`, structure rule) — the opposite side keeps coming in small candles and price does not move away; plus the volume wording
    (the opposite side's per-bar volume in the later part of the visit vs the earlier part and vs the trade side's).
  • commitment_volume — the existing definition, called read-only: `method.commitment(...)` (`commit_volume_rule`, approach leg + the
    visit's opposite-side candles) — its vol_mult / vol_vs / low_volume facts at bar t.

API: read_volume(V, t, d=None, area=None, degree=None) → dict; the single reads take (A, swings, t) or (V, t, area); draw_objects(read).
No look-ahead: bars ≤ t and swings with confirm_bar ≤ t only.
"""
import numpy as np
import pandas as pd

from . import method as M

UP, DOWN = 1, -1


# ------------------------------------------------------------------------------------------------ helpers
def volume_of(A):
    """The raw per-bar FUT volume array (None ⇒ no volume). `volume_raw` (engine) first, else `volume`."""
    v = A.get("volume_raw") if hasattr(A, "get") else None
    if v is None:
        v = A.get("volume") if hasattr(A, "get") else None
    return M._vol({"volume": v}) if v is not None else None


def _avg(vol, bars):
    """Per-bar average over the bars that have volume; (avg | None, gaps)."""
    bars = [int(i) for i in bars]
    have = [float(vol[i]) for i in bars if np.isfinite(vol[i]) and vol[i] > 0]
    return (float(np.mean(have)) if have else None), len(bars) - len(have)


def swings(pivots, t):
    """Alternating swings confirmed by bar t: [(bar, kind "H"/"L", price)] in bar order; two of one kind in a row ⇒ the more extreme."""
    known = sorted((p for p in pivots if p.confirm_bar <= t and p.bar <= t), key=lambda p: (p.bar, p.confirm_bar))
    out = []
    for p in known:
        x = (int(p.bar), p.kind, float(p.price))
        if out and out[-1][1] == p.kind:
            if (x[2] > out[-1][2]) if p.kind == "H" else (x[2] < out[-1][2]):
                out[-1] = x
            continue
        if out and x[0] == out[-1][0]:
            continue
        out.append(x)
    return out


def _pivots(V, degree=None):
    deg = int(V.s.get("tl_degree", 1) if degree is None else degree)
    return list(V.res["pivots"].get(deg, []))


def _cmp_word(a, b, lower="lower", higher="higher"):
    if a is None or b is None:
        return None
    return lower if a < b else (higher if a > b else "equal")


# ------------------------------------------------------------------------------------------------ I.1 pullback vs impulse
def pullback_vs_impulse(A, sw, t, start=None, start_kind=None):
    """The pullback = the candles after the swing it starts from up to t; the impulse = the leg into that swing, from the opposite swing
    before it. Default start = the last confirmed swing of `sw`; an area visit passes its approach swing (`start` bar, `start_kind` "H" /
    "L"). Per-bar average volume of each. A pullback that has gone beyond the impulse's start is no pullback (state "beyond"). Returns
    {state lower / higher / equal / beyond / na, why, pullback, impulse, evidence}."""
    vol = volume_of(A)
    out = {"state": "na", "why": None, "pullback": None, "impulse": None, "evidence": None}
    if vol is None:
        out["why"] = "no FUT volume"
        return out
    if start is not None:
        b1, k1 = int(start), start_kind
        p1 = float(A["high"][b1] if k1 == "H" else A["low"][b1])
        prior = [x for x in sw if x[0] < b1 and x[1] != k1]
        if not prior:
            out["why"] = "no swing known before the approach swing (no impulse leg)"
            return out
        b0, _, p0 = prior[-1]
    else:
        pts = [x for x in sw if x[0] < t]
        if len(pts) < 2:
            out["why"] = "no impulse leg known (fewer than two confirmed swings)"
            return out
        (b0, _, p0), (b1, k1, p1) = pts[-2], pts[-1]
    imp_dir = UP if k1 == "H" else DOWN                                    # the impulse ran into the swing at b1
    ib, pb = list(range(b0 + 1, b1 + 1)), list(range(b1 + 1, int(t) + 1))
    if not pb:
        out["why"] = "no pullback candle yet"
        return out
    ia, ig = _avg(vol, ib)
    pa, pg = _avg(vol, pb)
    beyond = (min(A["low"][i] for i in pb) < p0) if imp_dir == UP else (max(A["high"][i] for i in pb) > p0)
    out["impulse"] = {"from_bar": int(b0), "to_bar": int(b1), "dir": imp_dir, "from_price": float(p0), "to_price": float(p1),
                      "avg_volume": _r(ia), "gaps": ig, "bars": len(ib)}
    out["pullback"] = {"from_bar": int(b1), "to_bar": int(t), "avg_volume": _r(pa), "gaps": pg, "bars": len(pb)}
    if beyond:
        out.update(state="beyond", why="price went beyond the impulse's start — not a pullback of that leg")
        return out
    w = _cmp_word(pa, ia)
    if w is None:
        out["why"] = "FUT volume missing on the " + ("pullback" if pa is None else "impulse") + " candles"
        return out
    side = "up" if imp_dir == UP else "down"
    out["state"] = w
    out["evidence"] = (f"pullback on {w} volume than the impulse {side} (per-bar average {pa:,.0f} vs {ia:,.0f})" if w != "equal" else
                       f"pullback on the same per-bar volume as the impulse {side}")
    return out


def _r(x):
    return None if x is None else round(float(x), 1)


# ------------------------------------------------------------------------------------------------ I.2 climax
def _climax_in(A, vol, a, e, d, t, s=None):
    """Leg a … e (direction d) read at bar t: the largest-volume candle c of the leg, large (range above the leg's earlier candles'
    average), the leg's extreme on it, and no later candle (≤ t) beyond that extreme."""
    bars = [i for i in range(a, e + 1) if np.isfinite(vol[i]) and vol[i] > 0]
    if len(bars) < 2:
        return None
    c = max(bars, key=lambda i: vol[i])
    ext = (lambda i: A["high"][i]) if d == UP else (lambda i: A["low"][i])
    leg_ext = max(ext(i) for i in range(a, e + 1)) if d == UP else min(ext(i) for i in range(a, e + 1))
    big = M.candle_read(A, c, _cs(s), a)["big_range"] if c > a else None
    on_ext = ext(c) == leg_ext
    later = range(c + 1, t + 1)
    progress = any((ext(i) > ext(c)) if d == UP else (ext(i) < ext(c)) for i in later)
    return {"bar": int(c), "volume": float(vol[c]), "big_range": big, "at_extreme": bool(on_ext), "after": len(later),
            "progress_after": bool(progress), "found": bool(big and on_ext and not progress and len(later) > 0),
            "forming": bool(big and on_ext and len(later) == 0)}


def _cs(s=None):
    """The comparative candle reading (method §3) whatever the what-if switches say."""
    from . import settings as S3
    return {**S3.DEFAULTS, **(s or {}), "candle_rule": "compare", "session_windows": False}


def climax(A, sw, t, s=None):
    """Climax on the completed leg (the one into the last confirmed swing) and on the current leg (from that swing to t). Returns
    {state found / forming / none / na, buying / selling, completed, current, evidence}."""
    vol = volume_of(A)
    out = {"state": "na", "completed": None, "current": None, "evidence": [], "why": None}
    if vol is None:
        out["why"] = "no FUT volume"
        return out
    pts = [x for x in sw if x[0] < t]
    if not pts:
        out["why"] = "no confirmed swing yet"
        return out
    out["state"] = "none"
    if len(pts) >= 2:
        (b0, _, _), (b1, k1, _) = pts[-2], pts[-1]
        d = UP if k1 == "H" else DOWN
        r = _climax_in(A, vol, b0 + 1, b1, d, t, s)
        if r:
            r["dir"] = d
            out["completed"] = r
            if r["found"]:
                out["state"] = "found"
                out["evidence"].append(f"{'buying' if d == UP else 'selling'} climax ended the leg {'up' if d == UP else 'down'} "
                                       f"(its largest-volume, large candle made the extreme; nothing went beyond it)")
    b1, k1, _ = pts[-1]
    d = DOWN if k1 == "H" else UP
    r = _climax_in(A, vol, b1 + 1, int(t), d, t, s)
    if r:
        r["dir"] = d
        out["current"] = r
        if r["found"]:
            out["state"] = "found"
            out["evidence"].append(f"{'buying' if d == UP else 'selling'} climax in the current leg {'up' if d == UP else 'down'}: "
                                   f"no progress beyond it for {r['after']} candle(s)")
        elif r["forming"] and out["state"] != "found":
            out["state"] = "forming"
            out["evidence"].append(f"possible {'buying' if d == UP else 'selling'} climax on the last candle (largest volume of the leg, "
                                   f"large, at the extreme) — progress after it not known yet")
    return out


# ------------------------------------------------------------------------------------------------ I.4 effort vs result
def _leg_er(A, vol, a, e, d, t):
    bars = list(range(a + 1, e + 1))
    if not bars:
        return None
    va, gaps = _avg(vol, bars)
    start = A["low"][a] if d == UP else A["high"][a]
    ext = max(A["high"][i] for i in bars) if d == UP else min(A["low"][i] for i in bars)
    prog = float((ext - start) * d)
    return {"from_bar": int(a), "to_bar": int(e), "dir": d, "effort": _r(va), "gaps": gaps, "result": round(prog / len(bars), 2),
            "progress": round(prog, 2), "bars": len(bars)}


def effort_result(A, sw, t, s=None):
    """Leg: the current leg (last confirmed swing … t) vs the previous leg in the same direction (two swings back). Candle: bar t vs the
    current leg's earlier candles. Returns {state, leg {...}, candle {...}, evidence}."""
    vol = volume_of(A)
    out = {"state": "na", "leg": None, "candle": None, "evidence": [], "why": None}
    if vol is None:
        out["why"] = "no FUT volume"
        return out
    pts = [x for x in sw if x[0] < t]
    if not pts:
        out["why"] = "no confirmed swing yet"
        return out
    b1, k1, _ = pts[-1]
    d = DOWN if k1 == "H" else UP
    cur = _leg_er(A, vol, b1, int(t), d, t)
    prev = _leg_er(A, vol, pts[-3][0], pts[-2][0], d, t) if len(pts) >= 3 else None
    if cur and prev and cur["effort"] is not None and prev["effort"] is not None:
        e = _cmp_word(cur["effort"], prev["effort"], "less", "more")
        r = _cmp_word(cur["result"], prev["result"], "less", "more")
        if e == "more" and r != "more":
            st = "effort without result"
        elif e == "less" and r == "more":
            st = "result with ease"
        else:
            st = "in harmony"
        out["leg"] = {"current": cur, "previous": prev, "effort": e, "result": r, "state": st}
        out["state"] = st
        side = "up" if d == UP else "down"
        out["evidence"].append(f"leg {side}: {st} — {e} volume per bar than the previous leg {side}, {r} progress per bar")
    elif cur:
        out["leg"] = {"current": cur, "previous": prev, "state": None,
                      "why": "no previous leg in the same direction" if not prev else "FUT volume missing on a leg"}
    a = b1 + 1
    if t > a and np.isfinite(vol[t]) and vol[t] > 0:
        va, _ = _avg(vol, range(a, int(t)))
        cr = M.candle_read(A, int(t), _cs(s), a)
        if va is not None:
            hv = float(vol[t]) > va
            ewr = bool(hv and not cr["big_body"])
            out["candle"] = {"bar": int(t), "volume": float(vol[t]), "leg_avg_volume": _r(va), "high_volume": hv, "big_body": cr["big_body"],
                             "effort_without_result": ewr}
            if ewr:
                out["evidence"].append("candle: volume above the leg's average with a body not above the leg's average — effort without "
                                       "result (candle)")
                if out["state"] in ("na", None):
                    out["state"] = "effort without result (candle)"
    return out


# ------------------------------------------------------------------------------------------------ I.3 absorption · I.5 commitment volume
def _area_dir(area):
    return UP if area.get("role") == "support" else DOWN


def absorption(V, t, area):
    """The method's absorption (`method.zone_study`, `absorption_rule`) over the current visit to `area` (V.visit, bars ≤ t), plus the
    volume wording. d = the area's trade side (support ⇒ buyers' side UP). Returns {state absorbing / not / na, why, visit_start,
    volume {...}, evidence}."""
    t = int(t)
    d = _area_dir(area)
    out = {"state": "na", "why": None, "visit_start": None, "volume": None, "evidence": None, "dir": d}
    vi = V.visit(t, area, d)
    if vi.get("start") is None:
        out["why"] = vi.get("why") or "no visit in progress"
        return out
    a = int(vi["start"])
    out["visit_start"] = a
    if t - a + 1 < 2:
        out["why"] = "one candle in the visit — nothing to compare yet"
        return out
    Av, label = V.vol_view(a, t)
    zs = M.zone_study(Av, a, t, d, V.s)
    out["state"] = "absorbing" if zs.get("absorption") else "not absorbing"
    out["study_line"] = zs.get("line")
    vol = volume_of(V.levels.A)
    if vol is not None:
        w = list(range(a, t + 1))
        m = len(w) // 2
        side = lambda ii, sgn: [i for i in ii if (V.levels.A["close"][i] - V.levels.A["open"][i]) * d * sgn > 0]   # noqa: E731
        o0, _ = _avg(vol, side(w[:m], -1))
        o1, _ = _avg(vol, side(w[m:], -1))
        t1, _ = _avg(vol, side(w[m:], 1))
        out["volume"] = {"opposite_earlier": _r(o0), "opposite_later": _r(o1), "trade_later": _r(t1), "measure": label,
                         "opposite_keeps_coming": None if o1 is None else bool(o0 is None or o1 >= o0)}
    who = "sellers" if d == UP else "buyers"
    if zs.get("absorption"):
        vw = ""
        v = out["volume"] or {}
        if v.get("opposite_later") is not None:
            vw = f"; {who}' volume per candle {'keeps coming' if v.get('opposite_keeps_coming') else 'fades'} " \
                 f"({v['opposite_later']:,.0f} later vs {v['opposite_earlier'] or 0:,.0f} earlier)"
        out["evidence"] = f"absorption at the {'demand' if d == UP else 'supply'}: {who} keep coming in small candles and price does " \
                          f"not move away{vw}"
    return out


def commitment_volume(V, t, area):
    """The existing commitment volume (`method.commitment`, `commit_volume_rule`) at bar t for `area`'s trade side over the current visit
    (approach leg = `V.visit` approach_from … visit start − 1). Facts only: {state above / not_above / na / no_commitment, vol_mult,
    vol_vs, why}."""
    t = int(t)
    d = _area_dir(area)
    out = {"state": "na", "why": None, "vol_mult": None, "vol_vs": None, "form": None, "dir": d}
    vi = V.visit(t, area, d)
    if vi.get("start") is None:
        out["why"] = vi.get("why") or "no visit in progress"
        return out
    a = int(vi["start"])
    appr = range(int(vi["approach_from"]), a) if vi.get("approach_from") is not None else None
    Av, _ = V.vol_view(a, t)
    ok, why, cm = M.commitment(Av, t, d, area, V.s, V._ts, win=a, approach=appr)
    out.update(why=why, vol_mult=cm.get("vol_mult"), vol_vs=cm.get("vol_vs"), form=cm.get("form"))
    if cm.get("vol_na"):
        out["state"] = "na"
    elif cm.get("wait") == "low_volume":
        out["state"] = "not_above"
    elif ok and cm.get("vol_mult") is not None:
        out["state"] = "above"
    elif not cm.get("form"):
        out["state"] = "no_commitment"
    else:
        out["state"] = "not_read"
    return out


# ------------------------------------------------------------------------------------------------ all reads
def read_volume(V, t, d=None, area=None, degree=None):
    """All §2I reads at bar t on a V22 state. area (optional, a `Levels.snapshot` band) ⇒ the pullback is the approach into that visit,
    plus absorption and the commitment volume there. d (optional) = trade direction (wording only). Returns a plain dict."""
    t = int(t)
    A = V.levels.A
    sw = swings(_pivots(V, degree), t)
    out = {"t": t, "ts": str(pd.Timestamp(V._ts[t])), "volume": "FUT" if volume_of(A) is not None else None,
           "volume_source": getattr(V, "vol_src", None), "evidence": []}
    pv = None
    if area is not None:                                                   # the approach leg into this visit (engine's structure visit):
        dd = _area_dir(area)                                               # it starts at the finest-structure swing built away from the
        vi = V.visit(t, area, dd)                                          # area (demand ⇒ a swing high above it; supply ⇒ a swing low)
        if vi.get("approach_from") is not None:
            fine = swings(getattr(V.levels, "_known0", []), t)
            pv = pullback_vs_impulse(A, fine, t, int(vi["approach_from"]) - 1, "H" if dd == UP else "L")
            pv["into_area"] = True
    out["pullback_vs_impulse"] = pv if pv is not None else pullback_vs_impulse(A, sw, t)
    out["climax"] = climax(A, sw, t, V.s)
    out["effort_result"] = effort_result(A, sw, t, V.s)
    if area is not None:
        out["absorption"] = absorption(V, t, area)
        out["commitment_volume"] = commitment_volume(V, t, area)
    for k in ("pullback_vs_impulse", "climax", "effort_result", "absorption"):
        ev = (out.get(k) or {}).get("evidence")
        out["evidence"] += ev if isinstance(ev, list) else ([ev] if ev else [])
    if d in (UP, DOWN):
        out["dir"] = d
    out["_ts"] = [str(pd.Timestamp(x)) for x in V._ts[:t + 1]]
    out["_A"] = A
    return out


def draw_objects(read, tf="15M"):
    """Chart objects: the pullback and impulse legs (with their per-bar average volume), climax candles, the effort-vs-result leg."""
    ts, A = read.get("_ts"), read.get("_A")
    if not ts or A is None:
        return []
    objs = []
    pv = read.get("pullback_vs_impulse") or {}
    if pv.get("impulse") and pv.get("pullback"):
        im, pb = pv["impulse"], pv["pullback"]
        objs.append({"kind": "volume_leg", "tf": tf, "t0": ts[im["from_bar"]], "t1": ts[im["to_bar"]], "p0": im["from_price"],
                     "p1": im["to_price"], "label": f"impulse vol/bar {im['avg_volume'] or 'NA'}", "state": "impulse", "evidence": []})
        y1 = float(A["close"][pb["to_bar"]])
        objs.append({"kind": "volume_leg", "tf": tf, "t0": ts[pb["from_bar"]], "t1": ts[pb["to_bar"]], "p0": im["to_price"], "p1": y1,
                     "label": f"pullback vol/bar {pb['avg_volume'] or 'NA'}", "state": pv.get("state"),
                     "evidence": [pv["evidence"]] if pv.get("evidence") else []})
    cl = read.get("climax") or {}
    for key in ("completed", "current"):
        r = cl.get(key)
        if r and (r.get("found") or r.get("forming")):
            b = r["bar"]
            objs.append({"kind": "volume_climax", "tf": tf, "t0": ts[b], "t1": ts[b], "p0": float(A["low"][b]), "p1": float(A["high"][b]),
                         "label": ("buying" if r["dir"] == UP else "selling") + " climax", "state": "found" if r["found"] else "forming",
                         "evidence": list(cl.get("evidence") or [])})
    er = (read.get("effort_result") or {}).get("leg") or {}
    cur = er.get("current")
    if cur and er.get("state"):
        a, e = cur["from_bar"], cur["to_bar"]
        objs.append({"kind": "effort_result", "tf": tf, "t0": ts[a], "t1": ts[e], "p0": float(A["low"][a] if cur["dir"] == UP else A["high"][a]),
                     "p1": float(A["close"][e]), "label": er["state"], "state": er["state"],
                     "evidence": list((read.get("effort_result") or {}).get("evidence") or [])})
    ab = read.get("absorption") or {}
    if ab.get("state") == "absorbing" and ab.get("visit_start") is not None:
        a = ab["visit_start"]
        objs.append({"kind": "absorption", "tf": tf, "t0": ts[a], "t1": ts[read["t"]], "p0": float(min(A["low"][a:read["t"] + 1])),
                     "p1": float(max(A["high"][a:read["t"] + 1])), "label": "absorption", "state": "absorbing",
                     "evidence": [ab.get("evidence")] if ab.get("evidence") else []})
    return objs


def public(read):
    """The read without the private arrays (JSON-safe)."""
    return {k: v for k, v in read.items() if not k.startswith("_")}
