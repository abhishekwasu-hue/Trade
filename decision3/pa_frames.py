"""decision3/pa_frames.py — shared read-only frames for the PA-standard track T2 readers (area_types, liquidity_pa, confluence_pa).

One `Frame` = one timeframe's bars KNOWN at the 15M bar t (bars ≤ t only) + its swings known at t:
  • 15M: the engine's own 15M bars (`levels.Levels.A`), structure swings = the area degree (D`level_degree` = D2) known at t, fine
    swings = the finest structure degree the levels read (`Levels._known0`, D1) confirmed by t.
  • Daily / Weekly: the engine's Daily / Weekly candles whose close is known at t, swings = the Daily / Weekly fold's pivots known at t.
Nothing here changes `levels.Levels` or a decision; it only reads them. Every helper is a comparison of bars / swings (no fixed numbers,
no time / day framing).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Frame:
    tf: str                 # "15M" / "D" / "W"
    O: np.ndarray
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray
    V: object               # per-bar volume (np.ndarray) or None
    ts: list                # bar timestamps (pd.Timestamp)
    last: int               # last bar index known at t (-1 ⇒ none)
    ext: list               # structure swings known at t (kind, price, bar, confirm_bar)
    fine: list              # finest structure swings known at t

    def stamp(self, i):
        return None if i is None or i < 0 or i >= len(self.ts) else str(self.ts[int(i)])


def frame_15m(lv, t):
    """The engine's 15M bars ≤ t with its D2 (area-degree) swings and finest structure swings, both confirmed by t."""
    A = lv.A
    vol = A.get("volume")
    ext = [p for p in lv.known_pivots(t)]
    fine = sorted((p for p in getattr(lv, "_known0", []) if p.confirm_bar <= t), key=lambda p: p.confirm_bar)
    return Frame("15M", A["open"], A["high"], A["low"], A["close"], None if vol is None else np.asarray(vol, float),
                 list(lv.ts), int(t), ext, fine or ext)


def frame_1h(lv, t):
    """The engine's 1H candles COMPLETED before the hour of the 15M bar t (the running hour is not a candle yet). No swings."""
    h = lv.h1
    return Frame("1H", h["open"].to_numpy(float), h["high"].to_numpy(float), h["low"].to_numpy(float), h["close"].to_numpy(float),
                 None, [x for x in h["timestamp"]], int(lv.h1_of[int(t)]) - 1, [], [])


_PIV_CACHE = {}


def _htf_pivots(states, now):
    """Every Daily / Weekly swing the fold has used up to `now` (its pivots + protected / impulse-end / parent swings), one per
    (kind, bar), in confirm order — the swings `levels` builds its Daily / Weekly bands from."""
    import bisect
    key = id(states)
    hit = _PIV_CACHE.get(key)
    if hit is None or hit[0] is not states:
        if len(_PIV_CACHE) > 8:
            _PIV_CACHE.clear()
        seen, rows = {}, []
        for st in states:
            for p in list(getattr(st, "pivots", None) or []) + [getattr(st, k, None) for k in ("protected", "imp_end", "parent")]:
                if p is not None and (p.kind, p.bar) not in seen:
                    seen[(p.kind, p.bar)] = p
                    rows.append((pd.Timestamp(p.known_at), p))
        rows.sort(key=lambda r: r[0])
        hit = _PIV_CACHE[key] = (states, [r[0] for r in rows], [r[1] for r in rows])
    j = bisect.bisect_right(hit[1], pd.Timestamp(now))
    return sorted(hit[2][:j], key=lambda p: p.confirm_bar)


def frame_htf(V, t, tf):
    """Daily ("D") / Weekly ("W") candles whose close is known at the 15M bar t, with the fold's pivots known at t. None when the
    engine was built without them."""
    df = getattr(V, "daily_df" if tf == "D" else "weekly_df", None)
    states = getattr(V, "daily" if tf == "D" else "weekly", None)
    if df is None or not len(df) or not states:
        return None
    from . import daily as DD
    lv = V.levels
    now = pd.Timestamp(lv.bar_end.iloc[int(t)])
    kat = DD.known_at_of(df.reset_index(drop=True))
    last = int(np.searchsorted(np.array(kat, dtype="datetime64[ns]"), np.datetime64(now), side="right")) - 1
    piv = [p for p in _htf_pivots(states, now) if p.confirm_bar <= last]
    d = df.reset_index(drop=True)
    return Frame(tf, d["open"].to_numpy(float), d["high"].to_numpy(float), d["low"].to_numpy(float), d["close"].to_numpy(float), None,
                 [pd.Timestamp(x) for x in d["timestamp"]], last, piv, piv)


def overlaps(F, i, lo, hi):
    return F.L[i] <= hi and F.H[i] >= lo


def span(F, b0, b1, lo, hi):
    """The base: the seed bars b0 … b1 extended to every adjoining bar (≤ F.last) that still trades inside the band [lo, hi]."""
    b1 = min(b1, F.last)
    while b0 - 1 >= 0 and overlaps(F, b0 - 1, lo, hi):
        b0 -= 1
    while b1 + 1 <= F.last and overlaps(F, b1 + 1, lo, hi):
        b1 += 1
    return b0, b1


def side(F, i, lo, hi):
    """Where bar i lies vs the band: +1 wholly above, -1 wholly below, 0 trades inside."""
    if F.L[i] > hi:
        return 1
    if F.H[i] < lo:
        return -1
    return 0


def leg_facts(F, i0, i1):
    """Facts of one leg (bars i0 … i1): bars, travel (its own high − low), pace (travel per bar), mean body, body overlap (share of bars
    whose body overlaps the previous bar's body) and mean volume (None when any bar has no volume)."""
    if i0 is None or i1 is None or i1 < i0:
        return None
    ix = np.arange(int(i0), int(i1) + 1)
    travel = float(F.H[ix].max() - F.L[ix].min())
    body = np.abs(F.C[ix] - F.O[ix])
    ov = None
    if len(ix) > 1:
        top, bot = np.maximum(F.O[ix], F.C[ix]), np.minimum(F.O[ix], F.C[ix])
        ov = float(np.mean(np.minimum(top[1:], top[:-1]) > np.maximum(bot[1:], bot[:-1])))
    vol = None
    if F.V is not None:
        v = F.V[ix]
        if np.all(np.isfinite(v)) and np.all(v > 0):
            vol = float(v.mean())
    return {"from_bar": int(i0), "to_bar": int(i1), "from_ts": F.stamp(i0), "to_ts": F.stamp(i1), "bars": int(len(ix)),
            "travel": round(travel, 2), "pace": round(travel / len(ix), 2), "body": round(float(body.mean()), 2), "overlap": ov,
            "volume": vol}


def compare_legs(a, b):
    """Leg a vs leg b, measure by measure (comparison only): who has the larger pace, the larger mean body, the LESS body overlap and
    the larger volume ("a" / "b" / "equal"; None when a measure is missing on either leg). Verdict: "stronger" = a wins more measures
    than it loses, "weaker" = it loses more than it wins, "even" otherwise; `unanimous` = one leg won every measure present."""
    if a is None or b is None:
        return {"verdict": None, "measures": {}, "unanimous": False}
    m = {}
    for k, more in (("pace", True), ("body", True), ("overlap", False), ("volume", True)):
        x, y = a.get(k), b.get(k)
        if x is None or y is None:
            m[k] = None
            continue
        m[k] = "equal" if x == y else ("a" if (x > y) == more else "b")
    got = [v for v in m.values() if v is not None]
    wa, wb = got.count("a"), got.count("b")
    verdict = None if not got else ("stronger" if wa > wb else ("weaker" if wb > wa else "even"))
    return {"verdict": verdict, "measures": m, "unanimous": bool(got) and (wa == len(got) or wb == len(got))}


def first_beyond(F, i0, i1, price, up, by_close=False):
    """First bar in i0 … i1 (≤ F.last) trading beyond price (up ⇒ above): high / low, or the close when by_close. None if none."""
    i1 = min(i1, F.last)
    if i1 < i0:
        return None
    seg = (F.C if by_close else (F.H if up else F.L))[i0:i1 + 1]
    hit = np.flatnonzero(seg > price) if up else np.flatnonzero(seg < price)
    return int(i0 + hit[0]) if len(hit) else None


def structure_break(F, swings, i0, i1, up, before):
    """First close in i0 … i1 beyond the last confirmed swing (H for up) that formed at or before `before` and was confirmed before
    that bar. Returns {bar, ts, swing} or None."""
    ks = sorted((p for p in swings if p.kind == ("H" if up else "L") and p.bar <= before), key=lambda p: p.confirm_bar)
    if not ks or i1 < i0:
        return None
    k = -1
    for i in range(i0, min(i1, F.last) + 1):
        while k + 1 < len(ks) and ks[k + 1].confirm_bar < i:
            k += 1
        if k >= 0 and ((F.C[i] > ks[k].price) if up else (F.C[i] < ks[k].price)):
            return {"bar": int(i), "ts": F.stamp(i), "swing": round(float(ks[k].price), 2)}
    return None
