"""decision3/trigger_frame.py — the 5M TRIGGER frame (Abhi, DECISIONS 37: the entry trigger is read on 5M for every model).

The 5M candles the entry models read their trigger on, and how each 5M candle sits against the 15M bars the reading is built from:

  • 5M spot OHLC = V22's own LTF frame (`V.ltf`, the same bars the c1 5M CHoCH reads — one 5M series, never two);
  • raw near-month FUT 5M volume per 5M bar (`legs2.volume.near_month`), joined on the exact bar start — a 5M bar without a FUT bar is
    NaN with its reason ("no FUT bar"), never 0 and never filled (method §3 Volume, RC5);
  • k(j) = the last 15M bar CLOSED at the 5M close end5[j] (bar_end ≤ end5[j]; −1 ⇒ none): the 15M / 1H / Daily state the 5M candle
    j may use (a 15M bar in progress is never read — its 5M children only as 5M candles);
  • b(j) = the 15M bar (09:15-anchored bin, as legs2.volume.to_15m) that CONTAINS the 5M candle; a bin with no closed 15M bar yet (the
    bar in progress) ⇒ k(j) + 1 (a position only — never an index into the 15M arrays) and `bin_ts` = that bin's start (visit ids);
  • pos(j) = the 5M candle's float position on the 15M bar axis (b(j) with the child's place inside its bin) — a line's value at a 5M
    candle (E4 b) is read there; no 15M data is read for it.

Bars ≤ the frame's own data only; the frame never fills a gap. Comparison facts only, no reading rule and no number."""
import numpy as np
import pandas as pd

BAR15 = pd.Timedelta(minutes=15)
OPEN = pd.Timedelta(hours=9, minutes=15)


def bin_start(ts):
    """5M (or any) bar starts ⇒ their 09:15-anchored 15M bin starts (the same bins as legs2.volume.to_15m / V22's FUT join)."""
    t = pd.to_datetime(pd.Series(ts)).reset_index(drop=True)
    day = t.dt.normalize()
    return day + OPEN + ((t - day - OPEN) // BAR15) * BAR15


class TriggerFrame:
    """The 5M trigger candles for a V22 instance. Attributes: n, ts (5M starts), end, A (open / high / low / close / volume / volume_raw
    arrays — the 5M "A" every method.* candle reader takes), k_of, b_of, virtual (b_of is the bar in progress), bin_ts, pos, kids
    (15M index ⇒ its 5M children), has_fut, vol_reason (5M index ⇒ why its FUT volume is NaN)."""

    def __init__(self, V, futures=None):
        L = V.ltf
        if L is None or not len(L["end"]):
            self.n = 0
            self.ts = np.array([], dtype="datetime64[ns]")
            self.end = np.array([], dtype="datetime64[ns]")
            self.A = {k: np.array([], float) for k in ("open", "high", "low", "close", "volume", "volume_raw")}
            self.k_of = self.b_of = np.array([], int)
            self.virtual = np.array([], bool)
            self.bin_ts = np.array([], dtype="datetime64[ns]")
            self.pos = np.array([], float)
            self.kids, self.has_fut, self.vol_reason = {}, futures is not None, {}
            return
        self.ts = np.asarray(L["start"], dtype="datetime64[ns]")
        self.end = np.asarray(L["end"], dtype="datetime64[ns]")
        self.n = len(self.ts)
        self.A = {k: np.asarray(L[k], float) for k in ("open", "high", "low", "close")}
        be15 = pd.to_datetime(V.bar_end).to_numpy(dtype="datetime64[ns]")
        st15 = np.asarray(V._ts, dtype="datetime64[ns]")
        self.k_of = np.searchsorted(be15, self.end, side="right").astype(int) - 1      # last 15M bar closed at the 5M close
        bins = bin_start(self.ts).to_numpy(dtype="datetime64[ns]")
        self.bin_ts = bins
        at = np.searchsorted(st15, bins, side="left")
        hit = (at < len(st15)) & (st15[np.minimum(at, len(st15) - 1)] == bins) if len(st15) else np.zeros(self.n, bool)
        self.b_of = np.where(hit, at, self.k_of + 1).astype(int)
        self.virtual = ~hit
        child = ((self.ts - bins) // np.timedelta64(5, "m")).astype(float)              # 0, 1, 2 inside a 15M bin
        self.pos = self.b_of + (child - 1.0) / 3.0
        self.kids = {}
        for j, b in enumerate(self.b_of):
            self.kids.setdefault(int(b), []).append(j)
        self.has_fut = futures is not None
        vol = np.full(self.n, np.nan)
        self.vol_reason = {}
        if futures is not None:
            from legs2 import volume as LVOL
            nm = LVOL.near_month(futures)
            got = dict(zip(pd.to_datetime(nm["timestamp"]).to_numpy(dtype="datetime64[ns]"), nm["volume"].to_numpy(float)))
            for j, t in enumerate(self.ts):
                x = got.get(t)
                if x is None:
                    self.vol_reason[j] = "no FUT bar"
                else:
                    vol[j] = float(x)
        self.A["volume"] = vol.copy()
        self.A["volume_raw"] = vol

    # ------------------------------------------------------------------------------------------ small facts
    def T(self, j):
        return None if j is None else str(pd.Timestamp(self.ts[int(j)]))

    def E(self, j):
        return None if j is None else str(pd.Timestamp(self.end[int(j)]))

    def bin_T(self, j):
        return str(pd.Timestamp(self.bin_ts[int(j)]))

    def children(self, b, upto=None):
        """The 5M candles of the 15M bar b (≤ upto)."""
        ks = self.kids.get(int(b), [])
        return [j for j in ks if upto is None or j <= int(upto)]

    def last_child_closing(self, bar_end15):
        """The 5M candle whose close is the 15M close bar_end15 (the candle at which that 15M bar became known), else None."""
        e = np.datetime64(pd.Timestamp(bar_end15), "ns")
        j = int(np.searchsorted(self.end, e, side="right")) - 1
        return j if j >= 0 and self.end[j] == e else None

    def first_at_or_after(self, ts):
        """The first 5M candle starting at / after ts (the first one that can know a fact known at ts)."""
        return int(np.searchsorted(self.ts, np.datetime64(pd.Timestamp(ts), "ns"), side="left"))

    def index_of_end(self, t_end):
        """The last 5M candle closed at t_end (−1 ⇒ none)."""
        return int(np.searchsorted(self.end, np.datetime64(pd.Timestamp(t_end), "ns"), side="right")) - 1

    def line_value(self, ln, j):
        """A line dict's price at the 5M candle j — its float position on the 15M axis (`pos`); reads no 15M data."""
        (b1, y1) = ln["p1"]
        return float(y1) + float(ln["slope"]) * (float(self.pos[int(j)]) - int(b1))

    def vol_gaps(self, a, t, limit):
        """RF-2 (b) on 5M: FUT volume gaps among the 5M candles a … t ⇒ {n, m, frac, limit, over}; FUT not given ⇒ None."""
        if not self.has_fut:
            return None
        raw = self.A["volume_raw"]
        w = np.arange(int(a), int(t) + 1)
        n = int((~(np.isfinite(raw[w]) & (raw[w] > 0))).sum())
        return {"n": n, "m": len(w), "frac": round(n / len(w), 3), "limit": float(limit), "over": bool(n / len(w) > float(limit))}

    def vol_na_reason(self, j):
        if not self.has_fut:
            return "FUT volume missing (no FUT bars given)"
        v = self.A["volume_raw"][int(j)]
        if not (np.isfinite(v) and v > 0):
            return "FUT 5M volume missing on this 5M bar" + (f" ({self.vol_reason[int(j)]})" if self.vol_reason.get(int(j)) else "")
        return None


def of(V):
    """The V22's trigger frame (built once, lazily)."""
    F = getattr(V, "_tf5", None)
    if F is None:
        F = V._tf5 = TriggerFrame(V, getattr(V, "_futures", None))
    return F


def handover5(A, arm, t, d, s, broken=None, sharp=None, memo=None, key=None):
    """`method.handover_episode` (Abhi Z-1q) read on the 5M candles arm … t — the SAME loop, resumable: the state after the windows
    arm … e (e < t) depends on those bars only, so a later t continues from the stored state (the prefix memo) instead of re-reading
    every window. tests/test_trigger_5m.py pins handover5 == method.handover_episode on every prefix. memo = a dict, key = the episode
    (area, visit start, direction); None ⇒ no memo (one full read)."""
    from . import method as M
    s = s or {}
    arm, t = int(arm), int(t)
    st0 = None if memo is None else memo.get(key)
    if st0 is not None and st0["e"] <= t:
        st = {k: (list(v) if k == "events" else v) for k, v in st0["st"].items()}
        a0, e0 = st0["a0"], st0["e"]
    else:
        st = {"present": False, "seen_at": None, "form": None, "cancelled": None, "cancelled_at": None, "sharp": None, "events": []}
        a0, e0 = arm, arm

    def cancel(u, why):
        st.update(present=False, form=None, cancelled=why, cancelled_at=int(u))
        st["events"].append((int(u), "cancelled: " + why))

    def seen(e, form):
        st.update(present=True, seen_at=int(e), form=form, cancelled=None, cancelled_at=None)
        st["events"].append((int(e), "handover seen" + (" (two-candle sharp reversal)" if form == "sharp_reversal" else "")))

    def read_sharp(e):
        if sharp is None or st["present"] or e - 1 < a0:
            return False
        sr = sharp(e, a0)
        st["sharp"] = sr
        if sr.get("found"):
            seen(e, "sharp_reversal")
            return True
        return False
    for e in range(e0, t):
        if broken is not None and broken(e):
            if st["present"]:
                cancel(e, "zone broken")
            a0 = e + 1
            continue
        if read_sharp(e):
            continue
        if e - a0 + 1 < 2:
            continue
        zs = M.zone_study(A, a0, e, d, s)
        if st["present"] and zs.get("absorption"):
            cancel(e, "absorption")
        elif not st["present"] and zs.get("handover"):
            seen(e, "study")
    if memo is not None and (memo.get(key) is None or memo[key]["e"] < t):   # keep the furthest checkpoint (calls come in time order)
        memo[key] = {"e": t, "a0": a0, "st": {k: (list(v) if k == "events" else v) for k, v in st.items()}}
    if broken is not None and broken(t):
        if st["present"]:
            cancel(t, "zone broken")
        a0 = t + 1
    else:
        read_sharp(t)
    st["window_start"] = int(a0)
    return st
