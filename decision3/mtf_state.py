"""decision3/mtf_state.py — PA standard §1 (multi-timeframe frame) + §2A (market structure: external / internal, HH / HL / LH / LL,
BOS / CHoCH). EVIDENCE / STATE only: nothing here enters, blocks or grades a trade.

One vocabulary for every timeframe (W, D, 1H, 15M, 5M):
  trending up / trending down / range / correction in progress (+ "unclear" when the structure does not give one of the four — data
  too short, or no trend structure yet).

Which existing reader gives each timeframe (no new swing detector):
  • W  — `daily.fold_impulse` on Weekly candles (V.weekly; the same DState the engine's Weekly parent uses).
  • D  — `daily.fold_impulse` (V.daily, `daily.state_at`): trend + phase + counter.
  • 1H — swings2 degree `level_degree` (D2 = the 1H trend degree the areas are born from; settings) + `swings2.structure.fold` states /
         events (BOS / CHoCH by 15M close — swings2's own definition).
  • 15M — swings2 degree `tl_degree` (D1 = the pullback's legs) + `swings2.structure.fold`.
  • 5M — the LTF bars (V.ltf) with the LTF swing definition `method.ltf_choch` already uses (a high above its left neighbour and not
         below its right one; mirror for a low), alternated (`daily._add`: same kind twice ⇒ keep the more extreme).

State (comparison only):
  • range = the reader's own RANGE (Daily / Weekly RANGE band; swings2 RANGE: Rhea band or HH + LL / equal swings).
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
  that protects the trend) — swings2.structure's definition; the same comparison is run on D / W / 5M swings (`dow_events`).
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


def labels(ps):
    """HH / LH (H) and HL / LL (L) against the previous swing of the same kind; EQH / EQL when the swing carries the reader's "equal"
    flag; the first of each kind ⇒ "H" / "L" (pivots.engine.labels, for any swing object)."""
    out, last = [], {"H": None, "L": None}
    for p in ps:
        q = last[p.kind]
        if getattr(p, "eq", False):
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


def swing_state(trend, seq, C, j, events, band=None):
    """The state word from a swing structure at frame bar j (seq = alternating swings known at j, C = closes, events = BOS / CHoCH known
    at j). Returns (state, side, detail)."""
    if trend == RANGE:
        return RANGE_S, 0, "range" + (f" {band[0]:,.2f}–{band[1]:,.2f}" if band else "")
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


def _folds(V):
    """swings2.structure.fold for the 1H degree, the 15M degree and the one below it (internal of 15M)."""
    def build():
        from swings2 import candles as SC
        from swings2 import structure as ST
        rr = SC.rng_ratio(V.res)
        d1h, d15 = degrees(V)
        out = {}
        for d in sorted({d1h, d15, d15 - 1}):
            if d >= 0 and d in V.res["pivots"]:
                out[d] = ST.fold(V.res, d, rr)
        return out
    return _memo(V, "folds", build)


def _swings2_known(V, d, t):
    """Non-warm-up swings2 pivots of degree d confirmed by 15M bar t, in t's data segment (swings2.structure.fold's own filter)."""
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
    return _memo(V, "ltf_ev", lambda: dow_events(_ltf_raw(V), L["close"]) if L is not None and len(L["end"]) else [])


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
        return [SP(p.kind, float(p.price), int(p.bar), pd.Timestamp(p.ts), int(p.confirm_bar), bool(p.eq), int(p.bar)) for p in ps]
    of = h1_view(V)["h1_of"]
    return [SP(p.kind, float(p.price), int(of[p.bar]), pd.Timestamp(p.ts), int(of[p.confirm_bar]), bool(p.eq), int(p.bar))
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
        F = _folds(V).get(dg)
        if F is None:
            return []
        of = h1_view(V)["h1_of"] if tf == "1H" else None
        piv = _swings2_known(V, dg, t)
        out = []
        for e in F["events"]:
            if e["bar"] > t or e["type"] not in ("BOS", "CHoCH"):
                continue
            kind = "H" if e["dir"] > 0 else "L"                            # an up-close breaks a high (BOS up / CHoCH up); mirror
            src = next((p for p in reversed(piv) if p.bar < e["bar"] and p.kind == kind and p.price == e["level"]), None)
            if src is None:                                                # event levels are rounded to 2 dp ⇒ the nearest such swing
                cand = [p for p in piv if p.bar < e["bar"] and p.kind == kind]
                src = min(reversed(cand), key=lambda p: abs(p.price - e["level"])) if cand else None
            pb = None if src is None else int(src.bar)
            out.append({"type": e["type"], "dir": int(e["dir"]), "level": float(e["level"]),
                        "bar": int(e["bar"] if of is None else of[e["bar"]]), "bar15": int(e["bar"]),
                        "pivot_bar": None if pb is None else int(pb if of is None else of[pb]), "disp": bool(e.get("disp", False))})
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
        F = _folds(V).get(d1h if tf == "1H" else d15)
        s = F["states"][t] if F is not None else {"trend": UNKNOWN, "range": None, "protected": None}
        trend = s["trend"]
        band = (s["range"]["bottom"], s["range"]["top"]) if s.get("range") else None
        if trend == RANGE and band is None:
            hs = [p.price for p in ext if p.kind == "H"][-2:]
            ls = [p.price for p in ext if p.kind == "L"][-2:]
            band = (min(ls), max(hs)) if len(hs) == 2 and len(ls) == 2 else None
        A = _m15_arrays(V)
        ext15 = _sp_swings2(V, _swings2_known(V, d1h if tf == "1H" else d15, t), "15M")    # the close checks run on 15M closes
        ev15 = [{**e, "bar": e["bar15"]} for e in ev]
        state, side, detail = swing_state(trend, ext15, A["c"], t, ev15, band)
        prot = s.get("protected")
        src = f"swings2 {deg} + swings2.structure.fold (15M closes)"
    else:
        F = frame(V, t, tf)
        if F is None or not F["n"]:
            return {"state": UNCLEAR_S, "trend": UNKNOWN, "side": 0, "detail": "LTF data missing", "source": "V.ltf", "protected": None}
        trend = trend_of(ext)
        state, side, detail = swing_state(trend, ext, F["c"], F["n"] - 1, ev)
        prot = None
        if trend in (UP, DOWN):
            ek = "H" if trend == UP else "L"
            e = next((p for p in reversed(ext) if p.kind == ek), None)
            q = next((p for p in reversed(ext) if p.kind != ek and e is not None and p.bar < e.bar), None)
            prot = None if q is None else q.price
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
    labs = labels(ext)
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
        ilabs = labels(inn)
        if tf in ("1H", "15M"):                                            # order inside the leg by the 15M bar of each swing
            leg = [(p, lab) for p, lab in zip(inn, ilabs) if p.order > last.order]
            iev = [e for e in _events(V, t, tf, internal=True) if e["bar15"] > last.order]
        else:
            leg = [(p, lab) for p, lab in zip(inn, ilabs) if p.bar > start]
            iev = [e for e in _events(V, t, tf, internal=True) if e["bar"] > start]
        internal = {"degree": di, "pivots": _pivot_rows([p for p, _ in leg], [lab for _, lab in leg], Fi),
                    "events": _event_rows(iev, Fi), "trend": trend_of(inn), "leg_from": {"kind": last.kind, "price": round(last.price, 2),
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
