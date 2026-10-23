"""decision3/mtf_state.py — PA standard §1 (multi-timeframe frame) + §2A (market structure: external / internal, HH / HL / LH / LL,
BOS / CHoCH). EVIDENCE / STATE only: nothing here enters, blocks or grades a trade.

One vocabulary for every timeframe (W, D, 1H, 15M, 5M):
  trending up / trending down / range / correction in progress (+ "unclear" when the structure does not give one of the four — data
  too short, or no trend structure yet).

Which existing reader gives each timeframe (no new swing detector):
  • W  — `daily.fold_impulse` on Weekly candles (V.weekly; the same DState the engine's Weekly parent uses).
  • D  — `daily.fold_impulse` (V.daily, `daily.state_at`): trend + phase + counter.
  • 1H — swings2 degree `level_degree` (D2 = the 1H trend degree the areas are born from; settings).
  • 15M — swings2 degree `tl_degree` (D1 = the pullback's legs).
    (1H / 15M: the swings only — trend = trend_of on the swings with the C-13 equal, BOS / CHoCH = `dow_events` by 15M close. The
    swings2.structure Rhea band (σ numbers) is NOT used.)
  • 5M — the LTF bars (V.ltf) with the LTF swing definition `method.ltf_choch` already uses (a high above its left neighbour and not
         below its right one; mirror for a low), alternated (`daily._add`: same kind twice ⇒ keep the more extreme).

State (comparison only):
  • range = the reader's own RANGE (Daily / Weekly RANGE band); on 1H / 15M the structural range of `range_edges` (DECISIONS 16 —
    the row's `range_state`; `_structural_range`): a swing disagreement (HH + LL / LH + HL / C-13 "equal") alone is no range there
    ("unclear"); 5M: HH + LL / LH + HL or a C-13 "equal" high / low (band = the higher of the last two highs, the lower of the last two lows).
  • trending up = UP structure and the impulse leg is running: the last confirmed swing is the higher low, or price has closed beyond
    the last high (BOS) since it.
  • correction in progress = UP structure, the last confirmed swing is the high and no close beyond it since (the counter-move is
    running, the protected low has not been broken by the swings), or the newest structure event is a CHoCH against the trend (the
    protected swing was closed through, the swings have not reversed yet). Daily / Weekly: DState phase correction / origin_broken or
    counter = pullback. Mirror for DOWN.
External vs internal (§2A): external = the timeframe's own (higher-degree) swings; internal = the next lower degree's swings inside
the current external leg (1H: D1 inside the D2 leg; 15M: D0 inside the D1 leg; D: the N − 1 Daily pivots inside the Daily leg; W: the
Daily swings inside the Weekly leg; 5M: none). Each degree gets HH / HL / LH / LL labels and its BOS / CHoCH events:
  BOS = close beyond the last trend-direction swing (continuation); CHoCH = close beyond the last counter swing before it (the swing
  that protects the trend) — swings2.structure's definition, run by `dow_events` on every timeframe's swings.
Agreement (§1): which timeframes agree with the Daily side (or the given direction d), which are in correction, which are against.
No look-ahead: everything is read from bars closed at the 15M bar t (pivots by confirm bar, Daily / Weekly by known_at ≤ bar_end[t],
LTF bars with bar_end ≤ bar_end[t], 1H candles only when closed). No dates, times or fixed numbers in the reading; no new settings.
"""
import weakref
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import daily as DD
from . import levels as LV
from . import settings as S3

TFS = ("W", "D", "1H", "15M", "5M")
UP_S, DOWN_S, RANGE_S, CORR_S, UNCLEAR_S = "trending up", "trending down", "range", "correction in progress", "unclear"
UP, DOWN, RANGE, UNKNOWN = "UP", "DOWN", "RANGE", "unknown"
AGREE, CORRECTION, AGAINST, NO_SIDE = "agrees", "correction", "against", "no side"


@dataclass(frozen=True)
class SP:
    """A swing in one timeframe's own bar index (frame bar of the extreme, frame bar whose close confirmed it)."""
    kind: str
    price: float
    bar: int
    ts: pd.Timestamp
    confirm_bar: int
    eq: bool = False
    src_bar: int = None                     # swings2 swings: the 15M bar of the extreme (orders swings inside one 1H candle)

    @property
    def order(self):
        return self.bar if self.src_bar is None else self.src_bar


# ------------------------------------------------------------------------------------------------ cache (per V22 object)
_CACHE = weakref.WeakKeyDictionary()


def _cache(V):
    try:
        c = _CACHE.get(V)
        if c is None:
            c = _CACHE[V] = {}
        return c
    except TypeError:                                                      # not weak-referenceable ⇒ no cache (still correct)
        return {}


def _memo(V, key, fn):
    c = _cache(V)
    if key not in c:
        c[key] = fn()
    return c[key]


def _s(V):
    return getattr(V, "s", None) or S3.load(None)


def degrees(V):
    """(1H degree, 15M degree) = the engine's own `level_degree` (D2) and `tl_degree` (D1)."""
    s = _s(V)
    return int(s["level_degree"]), int(s["tl_degree"])


# ------------------------------------------------------------------------------------------------ generic comparisons
def trend_of(ps, equal=None):
    """swings2.structure.trend_of on any alternating swing list: last two H and last two L — both higher ⇒ UP, both lower ⇒ DOWN, else
    RANGE; an "equal" later swing ⇒ RANGE; fewer than two of each ⇒ unknown."""
    hs = [p for p in ps if p.kind == "H"][-2:]
    ls = [p for p in ps if p.kind == "L"][-2:]
    if len(hs) < 2 or len(ls) < 2:
        return UNKNOWN
    if getattr(hs[1], "eq", False) or getattr(ls[1], "eq", False):
        return RANGE
    if equal is not None and (equal(hs[1], hs[0]) or equal(ls[1], ls[0])):
        return RANGE
    if hs[1].price > hs[0].price and ls[1].price > ls[0].price:
        return UP
    if hs[1].price < hs[0].price and ls[1].price < ls[0].price:
        return DOWN
    return RANGE


def labels(ps, equal=None):
    """HH / LH (H) and HL / LL (L) against the previous swing of the same kind; EQH / EQL when the later swing is "equal" to it
    (equal(later, earlier) — the C-13 comparison) or carries an "equal" flag; the first of each kind ⇒ "H" / "L"."""
    out, last = [], {"H": None, "L": None}
    for p in ps:
        q = last[p.kind]
        if getattr(p, "eq", False) or (equal is not None and q is not None and equal(p, q)):
            lab = "EQH" if p.kind == "H" else "EQL"
        elif q is None:
            lab = p.kind
        elif p.kind == "H":
            lab = "HH" if p.price > q.price else "LH"
        else:
            lab = "HL" if p.price > q.price else "LL"
        last[p.kind] = p
        out.append(lab)
    return out


def alternate(raw, upto=None):
    """Raw swings (confirm order) ⇒ alternating H / L (daily._add: the same kind twice ⇒ keep the more extreme); only confirm_bar ≤ upto."""
    seq = []
    for p in sorted(raw, key=lambda q: (q.confirm_bar, q.bar)):
        if upto is not None and p.confirm_bar > upto:
            break
        DD._add(seq, p)
    return seq


def dow_events(raw, C, equal=None):
    """BOS / CHoCH by close on any swing list (swings2.structure's definition), causal: at each bar the swings confirmed by then
    (alternated as they arrive). UP ⇒ BOS = close above the last H; CHoCH = close below the last L before that H (the protected low).
    DOWN mirror. Each swing fires once. Returns events [{type, dir, level, bar, pivot_bar}] in bar order."""
    by = {}
    for p in raw:
        by.setdefault(int(p.confirm_bar), []).append(p)
    seq, out, fired = [], [], set()
    n = len(C)
    for b in range(n):
        for p in sorted(by.get(b, []), key=lambda q: q.bar):
            DD._add(seq, p)
        if len(seq) < 4:
            continue
        tail = seq[-4:]
        tr = trend_of(tail, equal)
        if tr not in (UP, DOWN):
            continue
        up = tr == UP
        ek = "H" if up else "L"
        ext = next(p for p in reversed(seq) if p.kind == ek)
        prot = next((p for p in reversed(seq) if p.kind != ek and p.bar < ext.bar), None)
        dirn = 1 if up else -1
        c = float(C[b])
        if (c - ext.price) * dirn > 0 and ("bos", ext.bar, ext.kind) not in fired:
            fired.add(("bos", ext.bar, ext.kind))
            out.append({"type": "BOS", "dir": dirn, "level": float(ext.price), "bar": b, "pivot_bar": int(ext.bar)})
        if prot is not None and (prot.price - c) * dirn > 0 and ("choch", prot.bar, prot.kind) not in fired:
            fired.add(("choch", prot.bar, prot.kind))
            out.append({"type": "CHoCH", "dir": -dirn, "level": float(prot.price), "bar": b, "pivot_bar": int(prot.bar)})
    return out


def _range_left(seq, C, j, band):
    """Evidence wording only (§1 MTF state; DECISIONS 16 — a range = price fails to make a new extreme on BOTH sides; §2 K / T4 — a
    break is real only by a close beyond + a swing formed beyond): the state stays "range" while no swing has formed beyond the band,
    but when a close since the newest swing (bars ≤ j) went beyond a band edge the detail says so, so a reader does not see "range"
    with price already traded away from it. The newest such close decides the side. '' when none / no band. Comparison only."""
    if not band or not seq or j is None:
        return ""
    lo = int(seq[-1].bar) + 1
    if lo > j:
        return ""
    c = np.asarray(C[lo:j + 1], float)
    up, dn = np.flatnonzero(c > float(band[1])), np.flatnonzero(c < float(band[0]))
    if not len(up) and not len(dn):
        return ""
    above = len(up) and (not len(dn) or up[-1] > dn[-1])
    edge = float(band[1]) if above else float(band[0])
    return (f"; closed {'above its high' if above else 'below its low'} {edge:,.2f} since the last swing — no swing formed beyond it "
            f"yet (not a confirmed break)")


def swing_state(trend, seq, C, j, events, band=None):
    """The state word from a swing structure at frame bar j (seq = alternating swings known at j, C = closes, events = BOS / CHoCH known
    at j). Returns (state, side, detail)."""
    if trend == RANGE:
        return RANGE_S, 0, "range" + (f" {band[0]:,.2f}–{band[1]:,.2f}" if band else "") + _range_left(seq, C, j, band)
    if trend not in (UP, DOWN):
        return UNCLEAR_S, 0, "fewer than two confirmed highs and lows"
    dirn = 1 if trend == UP else -1
    word = UP_S if dirn > 0 else DOWN_S
    ek = "H" if dirn > 0 else "L"
    last_ev = next((e for e in reversed(events) if e["type"] in ("BOS", "CHoCH")), None)
    if last_ev is not None and last_ev["type"] == "CHoCH" and last_ev["dir"] == -dirn:
        return CORR_S, dirn, (f"CHoCH {'down' if dirn > 0 else 'up'}: close beyond the protected "
                              f"{'low' if dirn > 0 else 'high'} {last_ev['level']:,.2f} — the swings have not reversed yet")
    ext = next((p for p in reversed(seq) if p.kind == ek), None)
    last = seq[-1] if seq else None
    if ext is not None and last is ext:
        lo = int(ext.bar) + 1
        beyond = lo <= j and bool(np.any((np.asarray(C[lo:j + 1], float) - ext.price) * dirn > 0))
        if not beyond:
            return CORR_S, dirn, (f"counter-move after the {'high' if dirn > 0 else 'low'} {ext.price:,.2f}; no close beyond it yet "
                                  f"(protected swing intact)")
        return word, dirn, f"close beyond the last {'high' if dirn > 0 else 'low'} {ext.price:,.2f} (BOS) — impulse leg running"
    return word, dirn, (f"{'higher low' if dirn > 0 else 'lower high'} {last.price:,.2f} confirmed — impulse leg running"
                        if last is not None else "")


# ------------------------------------------------------------------------------------------------ timeframe sources
def _bar_end(V, t):
    return pd.Timestamp(V.bar_end[t]) if hasattr(V, "bar_end") else pd.Timestamp(pd.to_datetime(V.m15["bar_end"]).iloc[t])


def _m15_arrays(V):
    def build():
        m = V.res["m15"]
        vol = None
        lv = getattr(V, "levels", None)
        if lv is not None and lv.A.get("volume_raw") is not None:
            vol = np.asarray(lv.A["volume_raw"], float)
        return {"o": m["open"].to_numpy(float), "h": m["high"].to_numpy(float), "l": m["low"].to_numpy(float),
                "c": m["close"].to_numpy(float), "v": vol, "ts": pd.to_datetime(m["timestamp"]).reset_index(drop=True),
                "seg": np.array([V.res["segments"].get(pd.Timestamp(x)) for x in pd.to_datetime(m["timestamp"]).dt.normalize()])}
    return _memo(V, "m15", build)


def equal_fn(V, tf):
    """C-13 "equal" for the TF's swings (daily.c13_equal: the later extreme reaches the earlier swing candle's area, wick to body, and
    does not go beyond it) — on the candles the swing was found on (swings2 ⇒ 15M; 5M ⇒ LTF; D / W ⇒ their own). No σ tolerance."""
    if tf in ("1H", "15M"):
        A = _m15_arrays(V)
        O, C = A["o"], A["c"]
    elif tf == "5M":
        L = _ltf(V)
        if L is None:
            return None
        O, C = L["open"], L["close"]
    else:
        _, d = _daily_raw(V, tf)
        O, C = d["open"].to_numpy(float), d["close"].to_numpy(float)
    return lambda later, earlier: DD.c13_equal(O, C, later.price, earlier.kind, earlier.order, earlier.price)


def _swings2_events(V, d):
    """BOS / CHoCH on the swings2 degree d (non-warm-up swings, 15M closes) — `dow_events`, run per data segment (state resets where
    swings2 resets). Bars are 15M indices. No Rhea band: the trend is trend_of on the swings with the C-13 equal."""
    def build():
        A = _m15_arrays(V)
        seg = A["seg"]
        ps = [p for p in V.res["pivots"].get(d, []) if not p.warmup]
        eq = equal_fn(V, "15M")
        out, i = [], 0
        n = len(seg)
        while i < n:
            j = i
            while j + 1 < n and seg[j + 1] == seg[i]:
                j += 1
            raw = [SP(p.kind, float(p.price), int(p.bar) - i, pd.Timestamp(p.ts), int(p.confirm_bar) - i, False, int(p.bar) - i)
                   for p in ps if i <= p.bar and p.confirm_bar <= j and V.res["segments"].get(pd.Timestamp(p.ts).normalize()) == seg[i]]
            for e in dow_events(raw, A["c"][i:j + 1], eq_shift(eq, i)):
                out.append({**e, "bar": e["bar"] + i, "pivot_bar": e["pivot_bar"] + i})
            i = j + 1
        return out
    return _memo(V, f"ev_s2_{d}", build)


def eq_shift(eq, k):
    """The C-13 comparison for swings whose bars are offset by k (a segment's local index)."""
    if eq is None:
        return None
    return lambda later, earlier: eq(later, SP(earlier.kind, earlier.price, earlier.bar + k, earlier.ts, earlier.confirm_bar + k,
                                               False, earlier.order + k))


def _swings2_known(V, d, t):
    """Non-warm-up swings2 pivots of degree d confirmed by 15M bar t, in t's data segment (the same filter swings2.structure uses)."""
    A = _m15_arrays(V)
    seg = A["seg"][t]
    ps = [p for p in V.res["pivots"].get(d, []) if not p.warmup and p.confirm_bar <= t
          and V.res["segments"].get(pd.Timestamp(p.ts).normalize()) == seg]
    return sorted(ps, key=lambda p: (p.confirm_bar, p.bar))


def _daily_raw(V, which):
    """Raw Daily / Weekly swings at the trend degree (`daily._raw_pivots`, the fold's own input) and the Daily N − 1 swings."""
    def build():
        s = _s(V)
        d = (V.daily_df if which in ("D", "Dlow") else V.weekly_df).reset_index(drop=True)
        kat = DD.known_at_of(d)
        if which == "Dlow":
            n = int(s["daily_pivot_n"]) - 1
            if s["daily_swing_method"] != "pivot" or n < 1:
                return [], d
            return DD.pivots_pivot(d, n, kat), d
        sig = DD.sigma_d(d, int(s["daily_sigma_sessions"]))
        return DD._raw_pivots(d, s, kat, sig), d
    return _memo(V, f"raw_{which}", build)


def _daily_equal(d):
    O, C = d["open"].to_numpy(float), d["close"].to_numpy(float)
    return lambda later, earlier: DD.c13_equal(O, C, later.price, earlier.kind, earlier.bar, earlier.price)


def _ltf_equal(V):
    L = _ltf(V)
    return None if L is None else (lambda later, earlier: DD.c13_equal(L["open"], L["close"], later.price, earlier.kind, earlier.bar,
                                                                         earlier.price))


def _daily_events(V, which):
    def build():
        raw, d = _daily_raw(V, which)
        return dow_events(raw, d["close"].to_numpy(float), _daily_equal(d))
    return _memo(V, f"ev_{which}", build)


def _ltf(V):
    return getattr(V, "ltf", None)


def _ltf_raw(V):
    """5M swings: method.ltf_choch's LTF swing (high above the left neighbour, not below the right; mirror), confirmed by the right
    neighbour's close."""
    def build():
        L = _ltf(V)
        if L is None or not len(L["end"]):
            return []
        H, Lo = L["high"], L["low"]
        ts = pd.to_datetime(pd.Series(L["start"]))
        out = []
        for i in range(1, len(H) - 1):
            if H[i] > H[i - 1] and H[i] >= H[i + 1]:
                out.append(SP("H", float(H[i]), i, pd.Timestamp(ts.iloc[i]), i + 1))
            if Lo[i] < Lo[i - 1] and Lo[i] <= Lo[i + 1]:
                out.append(SP("L", float(Lo[i]), i, pd.Timestamp(ts.iloc[i]), i + 1))
        return sorted(out, key=lambda p: (p.confirm_bar, p.bar))
    return _memo(V, "ltf_raw", build)


def _ltf_events(V):
    L = _ltf(V)
    return _memo(V, "ltf_ev", lambda: dow_events(_ltf_raw(V), L["close"], _ltf_equal(V)) if L is not None and len(L["end"]) else [])


def ltf_known(V, t):
    """Number of LTF bars closed at 15M bar t (bar_end ≤ bar_end[t])."""
    L = _ltf(V)
    if L is None or not len(L["end"]):
        return 0
    return int(np.searchsorted(L["end"], np.datetime64(_bar_end(V, t)), side="right"))


def daily_known(V, t, which="D"):
    st = DD.state_at(V.daily if which == "D" else V.weekly, _bar_end(V, t))
    return st, int(st.bar)


def h1_view(V):
    def build():
        h1, h1_of = LV.h1_frame(V.res["m15"])
        m15 = V.res["m15"]
        vr = _m15_arrays(V)["v"]
        vol = None
        if vr is not None:
            s = pd.Series(np.where(np.isfinite(vr) & (vr > 0), vr, np.nan)).groupby(h1_of)
            vol = s.sum(min_count=1).to_numpy(float).copy()
            vol[s.apply(lambda x: x.isna().any()).to_numpy()] = np.nan    # a 1H bar with a missing FUT child ⇒ NA (never under-counted)
        t1 = pd.to_datetime(h1["timestamp"])
        need = np.minimum((t1 + pd.Timedelta(hours=1)).to_numpy(), (t1.dt.normalize() + pd.Timedelta(hours=15, minutes=30)).to_numpy())
        return {"h1": h1, "h1_of": np.asarray(h1_of), "need": need, "v": vol,
                "bar_end": pd.to_datetime(m15["bar_end"]).to_numpy() if "bar_end" in m15.columns else
                (pd.to_datetime(m15["timestamp"]) + pd.Timedelta(minutes=15)).to_numpy()}
    return _memo(V, "h1", build)


def h1_closed(V, t):
    """Number of 1H candles closed at 15M bar t (a 1H candle counts only when its hour — or the session — has ended)."""
    H = h1_view(V)
    j = int(H["h1_of"][t])
    return j + 1 if H["bar_end"][t] >= H["need"][j] else j


# ------------------------------------------------------------------------------------------------ per-timeframe swing lists
def _sp_swings2(V, ps, frame):
    """swings2 pivots ⇒ SP in the 15M index (frame "15M") or the 1H index (frame "1H")."""
    if frame == "15M":
        return [SP(p.kind, float(p.price), int(p.bar), pd.Timestamp(p.ts), int(p.confirm_bar), False, int(p.bar)) for p in ps]
    of = h1_view(V)["h1_of"]                                               # "equal" = C-13 (equal_fn), not swings2's σ flag
    return [SP(p.kind, float(p.price), int(of[p.bar]), pd.Timestamp(p.ts), int(of[p.confirm_bar]), False, int(p.bar))
            for p in ps]


def swings(V, t, tf):
    """(external, internal, ext_degree, int_degree) for timeframe tf at 15M bar t — alternating SP lists in that TF's own bar index
    (W: weekly bars, D: daily bars, 1H: 1H candles, 15M: 15M bars, 5M: LTF bars; the W internal swings are in Daily bars). Only swings
    confirmed by t."""
    d1h, d15 = degrees(V)
    if tf in ("1H", "15M"):
        de, di = (d1h, d1h - 1) if tf == "1H" else (d15, d15 - 1)
        ext = _sp_swings2(V, _swings2_known(V, de, t), tf)
        inn = _sp_swings2(V, _swings2_known(V, di, t), tf) if di >= 0 else []
        return ext, inn, f"D{de}", (f"D{di}" if di >= 0 else None)
    if tf == "5M":
        n = ltf_known(V, t)
        return alternate([p for p in _ltf_raw(V) if p.confirm_bar < n]), [], "5M swing", None
    _, jd = daily_known(V, t, "D")
    if tf == "D":
        raw, d = _daily_raw(V, "D")
        low, _ = _daily_raw(V, "Dlow")
        n = int(_s(V)["daily_pivot_n"])
        return [_sp_d(p, d) for p in alternate(raw, jd)], [_sp_d(p, d) for p in alternate(low, jd)], \
            f"Daily N={n}", (f"Daily N={n - 1}" if low else None)
    _, jw = daily_known(V, t, "W")
    raw, w = _daily_raw(V, "W")
    rawd, d = _daily_raw(V, "D")
    return [_sp_d(p, w) for p in alternate(raw, jw)], [_sp_d(p, d) for p in alternate(rawd, jd)], "Weekly", "Daily"


def _sp_d(p, d):
    return SP(p.kind, float(p.price), int(p.bar), pd.Timestamp(d["timestamp"].iloc[p.bar]), int(p.confirm_bar))


def frame(V, t, tf):
    """Bars of timeframe tf closed at 15M bar t: {o, h, l, c, v (or None), ts, n} — arrays are the full series; use [: n]."""
    if tf == "15M":
        A = _m15_arrays(V)
        return {**{k: A[k] for k in ("o", "h", "l", "c", "v", "ts")}, "n": t + 1}
    if tf == "1H":
        H = h1_view(V)
        h1 = H["h1"]
        return {"o": h1["open"].to_numpy(float), "h": h1["high"].to_numpy(float), "l": h1["low"].to_numpy(float),
                "c": h1["close"].to_numpy(float), "v": H["v"], "ts": pd.to_datetime(h1["timestamp"]).reset_index(drop=True),
                "n": h1_closed(V, t)}
    if tf == "5M":
        L = _ltf(V)
        if L is None:
            return None
        return {"o": L["open"], "h": L["high"], "l": L["low"], "c": L["close"], "v": None,
                "ts": pd.to_datetime(pd.Series(L["start"])).reset_index(drop=True), "n": ltf_known(V, t)}
    st, j = daily_known(V, t, tf)
    _, d = _daily_raw(V, tf)
    v = None
    if "volume" in d.columns:
        v = pd.to_numeric(d["volume"], errors="coerce").to_numpy(float)
        v = v if np.isfinite(v).any() and (v > 0).any() else None
    return {"o": d["open"].to_numpy(float), "h": d["high"].to_numpy(float), "l": d["low"].to_numpy(float),
            "c": d["close"].to_numpy(float), "v": v, "ts": pd.to_datetime(d["timestamp"]).reset_index(drop=True), "n": j + 1}


def _events(V, t, tf, internal=False):
    """BOS / CHoCH known at t for the TF's external (or internal) degree, in the TF's bar index (W internal: Daily bars)."""
    d1h, d15 = degrees(V)
    if tf in ("1H", "15M"):
        de = d1h if tf == "1H" else d15
        dg = de - 1 if internal else de
        if dg < 0 or dg not in V.res["pivots"]:
            return []
        of = h1_view(V)["h1_of"] if tf == "1H" else None
        seg = _m15_arrays(V)["seg"][t]
        out = []
        for e in _swings2_events(V, dg):
            if e["bar"] > t or _m15_arrays(V)["seg"][e["bar"]] != seg:
                continue
            pb = int(e["pivot_bar"])
            out.append({"type": e["type"], "dir": int(e["dir"]), "level": float(e["level"]),
                        "bar": int(e["bar"] if of is None else of[e["bar"]]), "bar15": int(e["bar"]),
                        "pivot_bar": int(pb if of is None else of[pb])})
        return out
    if tf == "5M":
        if internal:
            return []
        n = ltf_known(V, t)
        return [e for e in _ltf_events(V) if e["bar"] < n]
    _, jd = daily_known(V, t, "D")
    if tf == "D":
        return [e for e in _daily_events(V, "Dlow" if internal else "D") if e["bar"] <= jd]
    if internal:
        return [e for e in _daily_events(V, "D") if e["bar"] <= jd]
    _, jw = daily_known(V, t, "W")
    return [e for e in _daily_events(V, "W") if e["bar"] <= jw]


# ------------------------------------------------------------------------------------------------ state per timeframe
def _daily_word(st):
    """DState ⇒ (state, side, detail)."""
    if st.trend == "UNKNOWN" or st.bar < 0:
        return UNCLEAR_S, 0, "data too short (or no candle yet)"
    if st.trend == "NEUTRAL":
        return UNCLEAR_S, 0, "no trend structure (neutral)"
    if st.trend == "RANGE":
        b = st.band
        return RANGE_S, 0, "range" + (f" {b[0]:,.2f}–{b[1]:,.2f}" if b else "")
    dirn = 1 if st.trend == "UP" else -1
    word = UP_S if dirn > 0 else DOWN_S
    prot = f" · protected {st.protected.price:,.2f}" if st.protected is not None else ""
    rev = " · structure after the impulse extreme is against the trend" if getattr(st, "rev", None) is not None else ""
    if st.phase == "origin_broken":
        return CORR_S, dirn, f"protected origin closed through — no opposite impulse yet (correction leg {st.corr_label or '—'})" + rev
    if st.phase == "correction":
        what = "same-degree correction" if st.counter == "correction" else "same-degree correction candidate"
        return CORR_S, dirn, f"{what} (leg {st.corr_label or '—'}){prot}{rev}"
    if st.counter == "pullback":
        return CORR_S, dirn, f"lower-degree pullback after the impulse extreme{prot}{rev}"
    return word, dirn, f"impulse leg running{prot}{rev}"


def _band(ext):
    """The pivot range (HH + LL / equal swings): the higher of the last two highs, the lower of the last two lows."""
    hs = [p.price for p in ext if p.kind == "H"][-2:]
    ls = [p.price for p in ext if p.kind == "L"][-2:]
    return (min(ls), max(hs)) if len(hs) == 2 and len(ls) == 2 else None


def _protected(ext, trend):
    """The swing that protects the trend: the last counter swing before the trend extreme (swings2's strict swing)."""
    if trend not in (UP, DOWN):
        return None
    ek = "H" if trend == UP else "L"
    e = next((p for p in reversed(ext) if p.kind == ek), None)
    q = next((p for p in reversed(ext) if p.kind != ek and e is not None and p.bar < e.bar), None)
    return None if q is None else q.price


def _structural_range(V, t, tf, state, side, detail):
    """§1 market state, concept L (DECISIONS 16: a range = from structure — between two edges, the later swings fail to make a new
    extreme on both sides; not C-13 equal). On 1H / 15M the word "range" comes from the ONE structural range reader
    (`range_edges` — the row's `range_state`, the same swings and closes), so the two readers never disagree on the same bars:
      • a structural range in force at t ⇒ "range" with its edges; the swings' own trend inside it (HH / HL …, a counter-move) is kept
        in the detail ("inside it: …") — the inner swings of a range are not the timeframe's trend;
      • the last two highs / lows disagreeing (or C-13 equal) with no structural range in force ⇒ no trend structure and no range
        ⇒ "unclear" (the detail says why).
    Comparison only; no new setting. A V without the area engine (a stub) ⇒ unchanged. The `daily_range_rule = c13` what-if switches
    `range_state` to the C-13 reader while this word stays structural (DECISIONS 16), so under that what-if only they may differ."""
    if getattr(V, "levels", None) is None:
        return state, side, detail
    from . import range_edges as RE
    try:
        cur = DD.range_at(RE._pairs(V, tf), t)
    except Exception:                                                     # evidence only: never raised into a read
        return state, side, detail
    if cur is not None:
        lo, hi = float(cur["L"].price), float(cur["H"].price)
        inner = "" if state in (RANGE_S, UNCLEAR_S) else f"; inside it the swings read {state}" + (f" — {detail}" if detail else "")
        return RANGE_S, 0, (f"range {lo:,.2f}–{hi:,.2f} (from structure: later swings failed to make a new extreme on both sides)"
                            + inner)
    if state == RANGE_S:
        return UNCLEAR_S, 0, ("the last two highs / lows disagree (or are equal) — no trend structure, and no range from structure "
                              "(no swing pair whose later swings failed on both sides)")
    return state, side, detail


def _tf_state(V, t, tf):
    """{state, trend, side, detail, protected} for one timeframe."""
    if tf in ("D", "W"):
        st, _ = daily_known(V, t, tf)
        state, side, detail = _daily_word(st)
        trend = st.trend if st.trend in (UP, DOWN, RANGE) else UNKNOWN
        return {"state": state, "trend": trend, "side": side, "detail": detail, "source": "daily.fold_impulse (DState)",
                "protected": None if st.protected is None else round(float(st.protected.price), 2),
                "phase": st.phase, "counter": st.counter}
    ext, _, deg, _ = swings(V, t, tf)
    ev = _events(V, t, tf)
    if tf in ("1H", "15M"):
        d1h, d15 = degrees(V)
        A = _m15_arrays(V)
        ext15 = _sp_swings2(V, _swings2_known(V, d1h if tf == "1H" else d15, t), "15M")    # the close checks run on 15M closes
        trend = trend_of(ext15, equal_fn(V, tf))
        band = _band(ext15) if trend == RANGE else None
        ev15 = [{**e, "bar": e["bar15"]} for e in ev]
        state, side, detail = swing_state(trend, ext15, A["c"], t, ev15, band)
        state, side, detail = _structural_range(V, t, tf, state, side, detail)
        prot = _protected(ext15, trend)
        src = f"swings2 {deg} swings, trend_of + C-13 equal, BOS / CHoCH by 15M close; range = range_edges (structure, DECISIONS 16)"
    else:
        F = frame(V, t, tf)
        if F is None or not F["n"]:
            return {"state": UNCLEAR_S, "trend": UNKNOWN, "side": 0, "detail": "LTF data missing", "source": "V.ltf", "protected": None}
        trend = trend_of(ext, equal_fn(V, tf))
        state, side, detail = swing_state(trend, ext, F["c"], F["n"] - 1, ev, _band(ext) if trend == RANGE else None)
        prot = _protected(ext, trend)
        src = "LTF swings (method.ltf_choch definition), alternated"
    return {"state": state, "trend": trend, "side": side, "detail": detail, "source": src,
            "protected": None if prot is None else round(float(prot), 2)}


def _ts_of(F, i):
    try:
        return str(pd.Timestamp(F["ts"].iloc[int(i)]))
    except Exception:                                                      # noqa: BLE001 — index outside the frame
        return None


def _pivot_rows(ps, labs, F):
    return [{"kind": p.kind, "label": lab, "price": round(float(p.price), 2), "bar": int(p.bar), "ts": str(p.ts),
             "confirmed_at": _ts_of(F, p.confirm_bar) if F is not None else None} for p, lab in zip(ps, labs)]


def _event_rows(evs, F, ps=None):
    out = []
    for e in evs:
        out.append({"type": e["type"], "dir": "up" if e["dir"] > 0 else "down", "level": round(float(e["level"]), 2),
                    "bar": int(e["bar"]), "ts": _ts_of(F, e["bar"]) if F is not None else None,
                    "swing_ts": _ts_of(F, e["pivot_bar"]) if (F is not None and e.get("pivot_bar") is not None) else None})
    return out


def structure(V, t, tf):
    """§2A for one timeframe: external swings (labelled) of the structure window (from the older of the last two highs / lows on —
    the swings trend_of reads), its BOS / CHoCH events in that window, and the internal swings + events inside the current external
    leg (after the last external swing)."""
    ext, inn, de, di = swings(V, t, tf)
    F = frame(V, t, tf)
    eq = equal_fn(V, tf)
    labs = labels(ext, eq)
    hs = [p for p in ext if p.kind == "H"][-2:]
    ls = [p for p in ext if p.kind == "L"][-2:]
    w0 = min([p.bar for p in hs[:1] + ls[:1]]) if hs and ls else (ext[0].bar if ext else 0)
    win = [(p, lab) for p, lab in zip(ext, labs) if p.bar >= w0]
    evs = [e for e in _events(V, t, tf) if e["bar"] >= w0]
    out = {"degree": de, "pivots": _pivot_rows([p for p, _ in win], [lab for _, lab in win], F), "events": _event_rows(evs, F)}
    last = ext[-1] if ext else None
    internal = {"degree": di, "pivots": [], "events": [], "trend": UNKNOWN, "leg_from": None}
    if di is not None and last is not None:
        Fi = F
        start = last.bar
        if tf == "W":                                                      # the Weekly leg starts at the Daily extreme of that week
            _, d = _daily_raw(V, "D")
            Fi = frame(V, t, "D")
            wk = pd.to_datetime(d["timestamp"]).dt.to_period("W-FRI")
            wts = pd.Timestamp(F["ts"].iloc[last.bar]).to_period("W-FRI")
            ix = np.flatnonzero((wk == wts).to_numpy())
            if len(ix):
                col = d["high"] if last.kind == "H" else d["low"]
                sub = col.to_numpy(float)[ix]
                start = int(ix[int(np.argmax(sub) if last.kind == "H" else np.argmin(sub))])
        ieq = equal_fn(V, "D" if tf == "W" else tf)
        ilabs = labels(inn, ieq)
        if tf in ("1H", "15M"):                                            # order inside the leg by the 15M bar of each swing
            leg = [(p, lab) for p, lab in zip(inn, ilabs) if p.order > last.order]
            iev = [e for e in _events(V, t, tf, internal=True) if e["bar15"] > last.order]
        else:
            leg = [(p, lab) for p, lab in zip(inn, ilabs) if p.bar > start]
            iev = [e for e in _events(V, t, tf, internal=True) if e["bar"] > start]
        internal = {"degree": di, "pivots": _pivot_rows([p for p, _ in leg], [lab for _, lab in leg], Fi),
                    "events": _event_rows(iev, Fi), "trend": trend_of(inn, ieq), "leg_from": {"kind": last.kind, "price": round(last.price, 2),
                                                                                         "ts": str(last.ts)}}
    return {"external": out, "internal": internal}


# ------------------------------------------------------------------------------------------------ agreement
def agreement(states, d=None):
    """§1: which timeframes agree with the Daily side (or the direction d = ±1), which are in correction, which are against.
    agrees = trending in that direction; correction = same trend, its counter-move running; against = the opposite trend (a counter-move
    to the side, whether or not it is itself correcting); range / unclear listed apart. Daily RANGE / unclear and no d ⇒ no side."""
    D = states.get("D", {})
    side = int(d) if d in (1, -1) else int(D.get("side") or 0)
    ref = "direction given" if d in (1, -1) else "Daily side"
    out = {"side": {1: "UP", -1: "DOWN"}.get(side, None), "reference": ref, AGREE: [], CORRECTION: [], AGAINST: [], "range": [],
           "unclear": [], "relation": {}}
    for tf in TFS:
        x = states.get(tf)
        if x is None:
            continue
        if tf == "D" and d not in (1, -1):
            out["relation"][tf] = "reference"
            continue
        if x["state"] == RANGE_S:
            rel = "range"
        elif x["state"] == UNCLEAR_S or not x["side"]:
            rel = "unclear"
        elif side == 0:
            rel = NO_SIDE
        elif x["side"] == side:
            rel = CORRECTION if x["state"] == CORR_S else AGREE
        else:
            rel = AGAINST
        out["relation"][tf] = rel
        if rel in out:
            out[rel].append(tf)
    others = [tf for tf in TFS if tf in states and out["relation"].get(tf) not in ("reference",)]
    out["all_agree"] = bool(side and others and all(out["relation"][tf] == AGREE for tf in others))
    if not side:
        out["line"] = f"no side ({'Daily ' + D.get('state', '—') if d not in (1, -1) else 'd'}) — states only"
    else:
        parts = [f"{k}: {', '.join(out[k])}" for k in (AGREE, CORRECTION, AGAINST, "range", "unclear") if out[k]]
        out["line"] = f"{ref} {out['side']} — " + " · ".join(parts)
    return out


# ------------------------------------------------------------------------------------------------ public API
def read_mtf_state(V, t, d=None, with_structure=True):
    """The market state of every timeframe at 15M bar t (bars closed by bar_end[t] only) + agreement + §2A structure. Plain dicts.
    d = ±1 compares the timeframes with that direction instead of the Daily side. Evidence only — never a gate."""
    t = int(t)
    states = {}
    for tf in TFS:
        x = _tf_state(V, t, tf)
        if with_structure:
            try:
                x["structure"] = structure(V, t, tf)
            except Exception as exc:                                       # noqa: BLE001 — a missing source ⇒ NA, never a silent pass
                x["structure"] = {"na": f"{type(exc).__name__}: {str(exc)[:160]}"}
        states[tf] = x
    ag = agreement(states, d)
    story = [f"{tf}: {states[tf]['state']}" + (f" ({states[tf]['detail']})" if states[tf]["detail"] else "") for tf in TFS]
    story.append("agreement: " + ag["line"])
    return {"t": t, "as_of": str(_bar_end(V, t)), "tfs": states, "agreement": ag, "story": story, "evidence_only": True}


def evidence(state):
    """Short evidence lines for the signal's evidence list (T9 wires them): one per timeframe + the agreement line."""
    return [f"{tf} {state['tfs'][tf]['state']}" for tf in TFS if tf in state["tfs"]] + [state["agreement"]["line"]]


def draw_objects(V, t, d=None, state=None, tfs=TFS):
    """Chart objects (T8): swing labels (external + internal), BOS / CHoCH lines (from the broken swing to the closing candle), one state
    text per timeframe. Each {kind, tf, t0, t1, p0, p1, label, state, evidence}."""
    state = state or read_mtf_state(V, t, d)
    out = []
    for tf in tfs:
        x = state["tfs"].get(tf)
        if x is None:
            continue
        out.append({"kind": "tf_state", "tf": tf, "t0": state["as_of"], "t1": state["as_of"], "p0": None, "p1": None,
                    "label": f"{tf}: {x['state']}", "state": x["state"], "evidence": x["detail"]})
        st = x.get("structure") or {}
        for part, sub in (("external", st.get("external") or {}), ("internal", st.get("internal") or {})):
            for p in sub.get("pivots", []):
                out.append({"kind": "swing", "tf": tf, "t0": p["ts"], "t1": p["ts"], "p0": p["price"], "p1": p["price"],
                            "label": p["label"], "state": part, "evidence": f"{part} {sub.get('degree')} {p['label']}"})
            for e in sub.get("events", []):
                out.append({"kind": e["type"].lower(), "tf": tf, "t0": e["swing_ts"] or e["ts"], "t1": e["ts"], "p0": e["level"],
                            "p1": e["level"], "label": e["type"] + (" (int)" if part == "internal" else ""), "state": part,
                            "evidence": f"{part} {sub.get('degree')} {e['type']} {e['dir']}: close beyond {e['level']:,.2f}"})
    return out
