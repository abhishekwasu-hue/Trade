"""rsi2/engine.py — the reader's RSI divergence is `Divergence` (bottom of this file; method §3, layer 5: consecutive swings of one degree,
a new price extreme vs an RSI that does not exceed its previous extreme, equal counts; no bar windows or numeric thresholds). The `RSI`
class and helpers above are the OLD numeric detector (gaps, σ / RSI differences, Cardwell zones) — used only by the facts dossier and the
MTF display; rebuilt with the output (layer 6). Old description:

थर 6: RSI divergence (pivot-based; थर 1 pivots, RSI त्याच candle च्या close ला) आणि Cardwell rsi_range.

- RSI: masked 15M closes (थर 1 series), Wilder (`chart_reader.evidence.rsi` — शुद्ध, import + equality test), segment-निहाय (holdout मधून
  warm-up नाही), पहिल्या warmup_bars ला `rsi_warmup`. 1H RSI फक्त बंद 1H candles वर (त्या candle च्या 15M शेवटच्या bar ला उपलब्ध).
- Detector (A): D0 pivots वर; degree tag = nesting (D1 / D2 असेल तर); same (L1, L2) जोडी दोन degrees मध्ये ⇒ एकदाच (सगळ्यात मोठी).
  लागोपाठचे same-type pivots (त्याच degree चे), gap minGap–maxGap (D2: 1H bars), |Δp| ≥ 0.25 σ, |Δrsi| ≥ 3; line_clear (मधली RSI
  जोडरेघ ओलांडत नाही) आणि price_clear (मधली candle price जोडरेघेपलीकडे close नाही). Emit `known_at(L2)` (D2: max(pivot known_at, L2 च्या
  1H candle चा close)).
- on_K (Cardwell positive / negative reversal): hidden ज्यात L1 ∈ {I_origin, I_strict_HL} आणि L2 = K चा शेवटचा low (I खाली ⇒ highs).
  regular_in_K = K च्या A-low → C-low regular (momentum thinning, वेगळी खूण). at_impulse_end = regular ज्याचं H2 = I_end. cascade = एकाच
  दिशेच्या ≥ 2 लागोपाठ regular ज्या price ने नाकारल्या.
- rsi_range (B): RSI pivots (k left / right; known_at = pivot + k), window 40 (15M) / 20 (1H): bull / bear / neutral; range_shift warn /
  confirmed (थर 1 CHoCH); rsi_disagree (1H vs थर 1 D2).
"""
import numpy as np
import pandas as pd

from chart_reader import evidence as EV
from swings2 import structure as SST

from . import settings as RS

REG_BULL, HID_BULL, REG_BEAR, HID_BEAR = "regular_bull", "hidden_bull", "regular_bear", "hidden_bear"
BULL, BEAR, NEUTRAL = "bull_range", "bear_range", "neutral"


def rsi_segmented(close, segs, n):
    out = np.full(len(close), np.nan)
    start = 0
    for i in range(1, len(close) + 1):
        if i == len(close) or segs[i] != segs[i - 1]:
            out[start:i] = EV.rsi(close[start:i], n)
            start = i
    return out


class RSI:
    def __init__(self, lg, st, s=None):
        self.lg, self.st, self.res = lg, st, lg["res"]
        self.s = RS.load(s)
        m15 = self.res["m15"]
        self.n = len(m15)
        self.A = lg["A"]
        self.ts = pd.to_datetime(m15["timestamp"]).reset_index(drop=True)
        day = self.ts.dt.normalize()
        self.segs = np.array([self.res["segments"].get(pd.Timestamp(d)) for d in day])
        self.sig = np.array([self.res["sigma"].get(pd.Timestamp(d), np.nan) for d in day], float)
        p = int(self.s["period"])
        self.r15 = rsi_segmented(self.A["c"], self.segs, p)
        self.warm = np.zeros(self.n, bool)
        start = 0
        for i in range(self.n):
            if i == 0 or self.segs[i] != self.segs[i - 1]:
                start = i
            self.warm[i] = i - start < int(self.s["warmup_bars"])
        from pivots import charts as PC
        h1 = PC.agg_1h(m15)
        H, L, E, S1, G1, F1 = SST._h1(self.res)
        self.h1_close = h1["close"].to_numpy(float)
        self.h1_end = E                                                        # 1H index ⇒ 15M bar जिथे बंद (−1 ⇒ अपूर्ण)
        self.h1_first = F1
        ok = E >= 0
        self.r1h = np.full(len(E), np.nan)
        idx = np.flatnonzero(ok)
        if len(idx):
            self.r1h[idx] = rsi_segmented(self.h1_close[idx], np.asarray(G1)[idx], p)
        self.bar_to_h1 = np.full(self.n, -1)
        for k, (a, b) in enumerate(zip(F1, np.where(E >= 0, E, F1))):
            self.bar_to_h1[a:max(a, b) + 1] = k
        self.divs = self._detect()
        self.rpiv15 = self._rsi_pivots(self.r15, None)
        self.rpiv1h = self._rsi_pivots(self.r1h, self.h1_end)

    # ------------------------------------------------------------------------------------------------ detector
    def _tag(self, p):
        tag = 0
        for d in (1, 2):
            if any(q.bar == p.bar and q.kind == p.kind for q in self.res["pivots"][d]):
                tag = d
        return tag

    def _rsi_at(self, p, d):
        if d == 2:
            k = self.bar_to_h1[p.bar]
            if k < 0 or self.h1_end[k] < 0:
                return None, None
            return self.r1h[k], int(self.h1_end[k])
        return self.r15[p.bar], None

    def _clear(self, a, b, kind, d=0, skip=None):
        """line_clear (RSI; L1 / L2 शेजारचे line_skip bars वगळून; D2 ⇒ 1H RSI) आणि price_clear (closes). skip = 0 ⇒ strict."""
        lo, hi = a.bar, b.bar
        if hi - lo < 2:
            return True, True
        seg = np.arange(lo + 1, hi)
        pl = a.price + (b.price - a.price) * (seg - lo) / (hi - lo)
        cc = self.A["c"][seg]
        pc = bool(np.all(cc >= pl - 1e-9)) if kind == "L" else bool(np.all(cc <= pl + 1e-9))
        k = int(self.s["line_skip"] if skip is None else skip)
        if d == 2:
            i0, i1 = int(self.bar_to_h1[lo]), int(self.bar_to_h1[hi])
            r, x0, x1 = self.r1h, i0, i1
        else:
            r, x0, x1 = self.r15, lo, hi
        xs = np.arange(x0 + 1 + k, x1 - k)
        if not len(xs):
            return True, pc
        rl = r[x0] + (r[x1] - r[x0]) * (xs - x0) / (x1 - x0)
        rr = r[xs]
        if kind == "L":
            return bool(np.all(np.nan_to_num(rr, nan=np.inf) >= rl - 1e-9)), pc
        return bool(np.all(np.nan_to_num(rr, nan=-np.inf) <= rl + 1e-9)), pc

    def pair(self, a, b, d, kind):
        """दोन same-type pivots ⇒ divergence dict किंवा None."""
        s = self.s
        r1, k1 = self._rsi_at(a, d)
        r2, k2 = self._rsi_at(b, d)
        if r1 is None or r2 is None or not (np.isfinite(r1) and np.isfinite(r2)) or self.warm[a.bar]:
            return None
        sig = self.sig[b.bar]
        dp, dr = float(s["min_price_sigma"]) * sig, float(s["min_rsi"])
        typ = None
        if kind == "L":
            if b.price < a.price - dp and r2 > r1 + dr:
                typ = REG_BULL
            elif b.price > a.price + dp and r2 < r1 - dr:
                typ = HID_BULL
        else:
            if b.price > a.price + dp and r2 < r1 - dr:
                typ = REG_BEAR
            elif b.price < a.price - dp and r2 > r1 + dr:
                typ = HID_BEAR
        if typ is None:
            return None
        lc, pc = self._clear(a, b, kind, d)
        strict = self._clear(a, b, kind, d, skip=0)[0]                          # Abhi उत्तर 12: line_skip 2 ग्राह्य, strict खूण
        known = b.confirm_bar if d != 2 else max(b.confirm_bar, k2)
        gap_between = any(a.bar < g <= b.bar for g in self.res["gap_bar_2s"])
        grade = None
        if typ in (REG_BULL, REG_BEAR):
            grade = "मजबूत" if (r1 <= s["grade_os"] if typ == REG_BULL else r1 >= s["grade_ob"]) else "कमकुवत"
        return {"type": typ, "degree": d, "L1": {"bar": a.bar, "price": round(a.price, 2), "ts": str(self.ts.iloc[a.bar])},
                "L2": {"bar": b.bar, "price": round(b.price, 2), "ts": str(self.ts.iloc[b.bar])}, "rsi1": round(float(r1), 2),
                "rsi2": round(float(r2), 2), "gap": b.bar - a.bar, "known_bar": int(known), "line_clear": lc, "line_clear_strict": strict,
                "price_clear": pc,
                "strength": round(abs(r2 - r1) / (abs(b.price - a.price) / sig), 3) if sig else None, "gap_between": gap_between,
                "grade": grade}

    def _detect(self):
        out = {}
        for d in (0, 1, 2):
            ps = [p for p in self.res["pivots"][d] if not p.warmup]
            lo, hi = self.s["gaps"][d]
            for kind in ("H", "L"):
                kk = [p for p in ps if p.kind == kind]
                for a, b in zip(kk, kk[1:]):
                    if self.res["segments"].get(pd.Timestamp(a.ts).normalize()) != self.res["segments"].get(pd.Timestamp(b.ts).normalize()):
                        continue
                    g = b.bar - a.bar
                    if d == 2:
                        g = self.bar_to_h1[b.bar] - self.bar_to_h1[a.bar]
                    if not lo <= g <= hi:
                        continue
                    x = self.pair(a, b, d, kind)
                    if x is not None and x["line_clear"] and x["price_clear"]:
                        key = (a.bar, b.bar, kind)
                        if key not in out or out[key]["degree"] < d:
                            out[key] = x
        return sorted(out.values(), key=lambda x: (x["known_bar"], x["L2"]["bar"]))

    # ------------------------------------------------------------------------------------------------ rsi_range
    def _rsi_pivots(self, r, end_map):
        """RSI वर k left / right pivots ⇒ [(idx, kind, value, known_15m_bar)]."""
        k = int(self.s["pivot_k"])
        out = []
        for i in range(k, len(r) - k):
            w = r[i - k:i + k + 1]
            if not np.isfinite(w).all():
                continue
            if r[i] == w.max() and np.argmax(w) == k:
                kind = "H"
            elif r[i] == w.min() and np.argmin(w) == k:
                kind = "L"
            else:
                continue
            kb = i + k if end_map is None else int(end_map[i + k])
            if kb < 0:
                continue
            out.append((i, kind, float(r[i]), kb))
        return out

    def classify(self, t, tf="15M"):
        s = self.s
        if tf == "15M":
            r, piv, w = self.r15, self.rpiv15, int(s["window_15m"])
            i1 = t
        else:
            k = self.bar_to_h1[t]
            while k >= 0 and (self.h1_end[k] < 0 or self.h1_end[k] > t):
                k -= 1
            if k < 0:
                return {"range": None}
            r, piv, w = self.r1h, self.rpiv1h, int(s["window_1h"])
            i1 = k
        i0 = max(i1 - w + 1, 0)
        win = r[i0:i1 + 1]
        win = win[np.isfinite(win)]
        if len(win) < w // 2:
            return {"range": None}
        kn = [p for p in piv if p[3] <= t and i0 <= p[0] <= i1]
        tr = [p[2] for p in kn if p[1] == "L"]
        pk = [p[2] for p in kn if p[1] == "H"]
        mn, mx = float(win.min()), float(win.max())
        bull = mn >= s["bull_min"] and mx >= s["bull_max"] and sum(x < s["bull_trough"] for x in tr) <= 1 and \
            all(x >= s["bull_min"] for x in tr)
        bear = mx <= s["bear_max"] and mn <= s["bear_min"] and sum(x > s["bear_peak"] for x in pk) <= 1 and \
            all(x <= s["bear_max"] for x in pk)
        rng = BULL if bull else (BEAR if bear else NEUTRAL)
        warn = None
        seq = [p for p in piv if p[3] <= t]
        for a, b in zip(seq, seq[1:]):
            if a[1] == "L" and b[1] == "H" and a[2] < s["shift_trough"] and b[2] < s["shift_peak"]:
                warn = ("bull→bear", b[3])
            if a[1] == "H" and b[1] == "L" and a[2] > s["shift_peak"] and b[2] > s["shift_trough"]:
                warn = ("bear→bull", b[3])
        out = {"range": rng, "min": round(mn, 1), "max": round(mx, 1), "warn": None, "confirmed": False}
        dd = np.diff(self.h1_end[self.h1_end >= 0])
        w15 = w if tf == "15M" else w * (int(round(float(np.median(dd)))) if len(dd) else 1)       # 1H window ⇒ 15M bars
        if warn is not None and t - warn[1] <= w15:
            out["warn"] = warn[0]
            want = -1 if warn[0] == "bull→bear" else 1
            ev = self.st.get(1, {"events": []})["events"]
            out["confirmed"] = any(e["type"] == "CHoCH" and e["dir"] == want and warn[1] - w15 <= e["bar"] <= t for e in ev)
        return out

    def known(self, t):
        return [x for x in self.divs if x["known_bar"] <= t]


def special(R, I, st_ik, pref, t):
    """on_K आणि regular_in_K (t ला). I = ik2 internal I; st_ik = ik2 state; pref = थर 3 preferred (किंवा None)."""
    out = {"on_K": None, "regular_in_K": None, "at_impulse_end": None}
    if I is None or not st_ik.get("K"):
        return out
    up = I["dir"] > 0
    kind = "L" if up else "H"
    ps0 = [p for p in R.res["pivots"][0] if p.confirm_bar <= t and p.kind == kind and p.bar > I["end"].bar]
    a_low = None
    if pref is not None:
        P0, b0 = pref["P"], pref["bounds"]
        if len(b0) >= 2 and not P0[b0[1]]["tent"] and P0[b0[1]]["kind"] == kind:
            a_low = next((p for p in ps0 if p.bar == P0[b0[1]]["bar"]), None)          # preferred चा A-end
        P, b = pref["P"], pref["bounds"]
        ends = [P[k] for k in b[1:] if not P[k]["tent"] and P[k]["kind"] == kind]
        if ends:
            last = ends[-1]
            m = [p for p in ps0 if p.bar == last["bar"]]
            if m:
                ps0 = [p for p in ps0 if p.bar <= m[0].bar]
    if ps0:
        L2 = ps0[-1]
        refs = []
        hs = None
        for p in R.res["pivots"][1]:
            if p.kind == kind and I["origin"].bar <= p.bar < I["end"].bar and p.confirm_bar <= t:
                hs = p
        refs.append(("I_origin", I["origin"]))
        if hs is not None:
            refs.append(("I_strict_HL", hs))
        for nm, L1 in refs:
            x = R.pair(L1, L2, 0, kind)
            if x is not None and x["type"] in (HID_BULL, HID_BEAR) and x["line_clear"] and x["price_clear"]:
                x["ref"] = nm
                x["on_K_known_bar"] = max(x["known_bar"], L2.confirm_bar)
                out["on_K"] = x
                break
        a = a_low if a_low is not None else (ps0[0] if len(ps0) >= 2 else None)
        if a is not None and a.bar < L2.bar:
            x = R.pair(a, L2, 0, kind)
            if x is not None and x["type"] in (REG_BULL, REG_BEAR) and x["line_clear"] and x["price_clear"]:
                out["regular_in_K"] = x
    want = REG_BEAR if up else REG_BULL
    for x in R.known(t):
        if x["type"] == want and x["L2"]["bar"] == I["end"].bar:
            out["at_impulse_end"] = x
    return out


def cascade(R, t):
    """Degree-निहाय (Abhi निर्णय): एकाच degree tag च्या, एकाच दिशेच्या लागोपाठ ≥ 2 regular divergences ज्या price ने नाकारल्या (नंतरचा
    त्याच degree चा same-type confirmed pivot L2 पलीकडे trend-दिशेने). Degrees मिसळत नाहीत."""
    regs = [x for x in R.known(t) if x["type"] in (REG_BULL, REG_BEAR)]
    out = []
    for d in sorted({x["degree"] for x in regs}):
        for typ in (REG_BULL, REG_BEAR):
            kind = "L" if typ == REG_BULL else "H"
            rej = []
            for x in [y for y in regs if y["type"] == typ and y["degree"] == d]:
                ps = [p for p in R.res["pivots"][d] if p.kind == kind and p.bar > x["L2"]["bar"] and p.confirm_bar <= t]
                nxt = ps[0] if ps else None
                if nxt is not None and ((nxt.price < x["L2"]["price"]) if kind == "L" else (nxt.price > x["L2"]["price"])):
                    rej.append((x, nxt.confirm_bar))
                else:
                    rej = []
            if len(rej) >= 2:
                out.append({"type": typ, "degree": d, "n": len(rej), "known_bar": rej[-1][1]})
    return out


def mapping(r15, r1h, sp, casc, rng1, range_edge_hit, s):
    """§4 labels (निर्णय नाही). रिटर्न (labels list, final). दोन्ही (regular + reversal) ⇒ reversal प्राधान्य; 1H > 15M."""
    lo, hi = float(s["onk_trough_lo"]), float(s["onk_trough_hi"])
    labels = []
    for nm, rr in (("1H", r1h), ("15M", r15)):
        rg = (rr or {}).get("range")
        x = sp.get("on_K")
        if x is not None:
            v = x["rsi2"]
            if (rg == BULL and x["type"] == HID_BULL and lo <= v <= hi) or (rg == BEAR and x["type"] == HID_BEAR and 100 - hi <= v <= 100 - lo):
                labels.append((nm, "K संपतोय", "reversal"))
        ai = sp.get("at_impulse_end")
        if ai is not None and ((rg == BULL and ai["type"] == REG_BEAR) or (rg == BEAR and ai["type"] == REG_BULL)):
            labels.append((nm, "continuation trap / risk", "regular"))
        if rg == NEUTRAL and rng1 and range_edge_hit:
            labels.append((nm, "range-fade पुरावा", "regular"))
    if casc:
        labels.append(("15M", "trend मजबूत", "regular"))
    if sp.get("regular_in_K") is not None:
        labels.append(("15M", "K thinning", "regular"))
    rev = [x for x in labels if x[2] == "reversal"]
    pool = sorted(rev if rev else labels, key=lambda x: 0 if x[0] == "1H" else 1)
    return labels, (pool[0][1] if pool else None)


# ================================================================================================ K-RSI: regular divergence facts
# KB K10.4 (K-RSI, pending Abhi). Owner = rsi2 (design §3). Facts only — no score / grade / vote; evidence inside the zone study, never a
# trigger or a gate. Wilder RSI on the SPOT close of the frame's timeframe (15M primary, 1H context, 5M optional). Pivots = swings2
# (the facts swing owner): two CONSECUTIVE same-kind pivots of one degree (no higher high / lower low between them); price on wicks; the
# RSI value = the RSI extreme within ± `div_rsi_window` bars of the price pivot, inside the pivot's own swing (between the neighbouring
# opposite pivots of that degree) and using only bars closed by the bar that confirms that pivot (or by the read bar while it is still
# forming) ⇒ no look-ahead, and a confirmed value never changes later.
# Status: "forming" = the current push's running extreme vs the previous pivot; "confirmed" = the extreme is confirmed by the right-side
# bars (swings2 confirmation) OR by a dominant commitment candle (decision3.method.commitment) closing away from it.
# Bar window per TF (`div_bars`) is only a safety cap: pairs rejected ONLY by it are logged (`cap_rejected`).
BEAR_SIDE, BULL_SIDE = "bear", "bull"
SIDE_KIND = {BEAR_SIDE: "H", BULL_SIDE: "L"}


def div_frame(df):
    """OHLC frame ⇒ timestamp (tz-naive), bar_end, open / high / low / close; index reset. bar_end missing ⇒ timestamp + the frame's
    usual bar step (most common gap)."""
    d = df.reset_index(drop=True).copy()
    ts = pd.to_datetime(d["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_localize(None)
    d["timestamp"] = ts
    if "bar_end" in d.columns:
        be = pd.to_datetime(d["bar_end"])
        d["bar_end"] = be.dt.tz_localize(None) if getattr(be.dt, "tz", None) is not None else be
    else:
        gaps = ts.diff().dropna()
        gaps = gaps[gaps > pd.Timedelta(0)]
        step = gaps.mode().iloc[0] if len(gaps) else pd.Timedelta(0)
        d["bar_end"] = ts + step
    for k in ("open", "high", "low", "close"):
        d[k] = d[k].astype(float)
    return d[["timestamp", "bar_end", "open", "high", "low", "close"]]


def _r2(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 2)


def div_label(x):
    """Chart / caption label (English): 'bear div · confirmed · 12 bars · RSI 68.21 → 64.10' ('=' when the RSI values are equal)."""
    pre = ("hidden " if x["type"] == "hidden" else "") + x["side"] + " div"
    a, b = x["L1"]["rsi"], x["L2"]["rsi"]
    rs = f"RSI {a:.2f} = {b:.2f}" if x["rsi_diff"] == 0 else f"RSI {a:.2f} → {b:.2f}"
    return f"{pre} · {x['status']} · {x['bars']} bars · {rs}"


class Divergence:
    """K-RSI facts on one timeframe frame. `read(t)` = facts at closed bar t (bars ≤ t only); `history(t)` = every divergence confirmed
    by t (+ the forming ones at t); `cap_log(t)` = pairs rejected only by the bar cap.

    df   : SPOT OHLC of the timeframe (timestamp [, bar_end], open, high, low, close).
    tf   : "15M" / "1H" / "5M" (selects the bar window in `div_bars`).
    res  : a swings2.engine.build result for this frame (built here if None; pass 1m order data only with a 15M frame).
    rsi  : optional precomputed RSI array (tests); default Wilder(`period`) per data segment (chart_reader.evidence.rsi).
    areas: True ⇒ at / in a valid area via decision3.levels.find_bands (facts.validity); errors ⇒ NA with the reason."""

    def __init__(self, df, tf="15M", s=None, res=None, df1m=None, rsi=None, areas=True, s_swings=None):
        from facts import validity as FV
        self.s = RS.load(s)
        self.tf = tf
        self.df = div_frame(df)
        if res is None:
            from swings2 import engine as SE
            res = SE.build(self.df, df1m, s=s_swings)
        self.res = res
        self.n = len(self.df)
        self.B = FV.bars_of(self.df)
        self.FV = FV
        self.fv = FV.lookback(tf)
        self.seg = np.array([res["segments"].get(pd.Timestamp(d), -1) for d in self.B.day])
        self.seg_start = np.zeros(self.n, int)
        for i in range(1, self.n):
            self.seg_start[i] = i if self.seg[i] != self.seg[i - 1] else self.seg_start[i - 1]
        self.rsi = np.asarray(rsi, float) if rsi is not None else rsi_segmented(self.B.C, self.seg, int(self.s["period"]))
        self.warm = (np.arange(self.n) - self.seg_start) < int(self.s["warmup_bars"])
        lo, hi = self.s["div_bars"][tf]
        self.win = (int(lo), int(hi))
        self.N = int(self.s["div_rsi_window"])
        self.degrees = tuple(int(d) for d in self.s["div_degrees"])
        self.piv = {d: sorted([p for p in res["pivots"].get(d, []) if not p.warmup], key=lambda p: (p.confirm_bar, p.bar))
                    for d in self.degrees}
        self.with_areas = areas
        self._areas = {}
        self._s3 = None
        self._scan()

    # -------------------------------------------------------------------------------------------- pieces
    def _rsi_ext(self, bar, side, lo, hi):
        """RSI extreme (max for bear, min for bull) over bars [lo, hi] ∩ the pivot's segment ⇒ (value, rsi bar) or None."""
        i0 = max(lo, int(self.seg_start[bar]))
        i1 = min(hi, self.n - 1)
        idx = np.array([i for i in range(i0, i1 + 1) if self.seg[i] == self.seg[bar]], int)
        if not len(idx):
            return None
        w = self.rsi[idx]
        if not np.isfinite(w).all() or self.warm[idx].any():
            return None
        k = int(np.argmax(w)) if side == BEAR_SIDE else int(np.argmin(w))
        return float(w[k]), int(idx[k])

    def _commit(self, j, side, price):
        """decision3.method.commitment at bar j, away from the extreme `price` (bear ⇒ DOWN) ⇒ (ok, facts)."""
        from decision3 import method as M
        from decision3 import settings as S3
        if self._s3 is None:
            self._s3 = S3.load()
            self._A = {"open": self.B.O, "high": self.B.H, "low": self.B.L, "close": self.B.C}
        d = M.DOWN if side == BEAR_SIDE else M.UP
        ok, _, cm = M.commitment(self._A, j, d, {"lo": price, "hi": price}, self._s3)
        return bool(ok), ({"form": cm.get("form"), "grade": cm.get("grade")} if ok else None)

    def area_at(self, k, price, side):
        """At / in a valid area at bar k (decision3.levels.find_bands, facts.validity checks): 'in' (inside the band), 'at' (within the
        band tolerance), 'away'; NA with the reason when the area owner fails or finds no valid band."""
        if not self.with_areas:
            return {"status": "NA", "reason": "areas not computed (areas=False)"}
        if k not in self._areas:
            try:
                from decision3 import levels as LV
                bands = [b for b in LV.find_bands(self.B, k, self.fv) if b["valid"]]
                self._areas[k] = (bands, self.FV.mr_at(self.B, k, self.fv), None)
            except Exception as exc:                                    # noqa: BLE001 — NA with the reason (evidence only)
                self._areas[k] = (None, None, f"{type(exc).__name__}: {exc}")
        bands, mr, err = self._areas[k]
        if err is not None:
            return {"status": "NA", "reason": "area owner failed — " + err}
        if not bands:
            return {"status": "NA", "reason": "no valid band (decision3.levels.find_bands) at this bar"}
        tol = float(self.fv["band_tol_mr"]) * mr

        def dist(b):
            return 0.0 if b["lo"] <= price <= b["hi"] else min(abs(price - b["lo"]), abs(price - b["hi"]))
        b = min(bands, key=dist)
        st = "in" if dist(b) == 0 else ("at" if dist(b) <= tol else "away")
        return {"status": st, "band": {"lo": b["lo"], "hi": b["hi"], "role": b["role"], "touch_count": int(b["touch_count"])},
                "distance": round(float(dist(b)), 2), "tolerance": round(float(tol), 2)}

    def _pt(self, bar, price, rv):
        return {"bar": int(bar), "time": str(self.B.ts.iloc[bar]), "price": round(float(price), 2),
                "rsi": _r2(rv[0]) if rv else None, "rsi_bar": int(rv[1]) if rv else None,
                "rsi_time": str(self.B.ts.iloc[rv[1]]) if rv else None}

    def _eval(self, d, side, a, b_bar, b_price, cap_b, known_bar, status, status_by, known):
        """One pair (a = confirmed swings2 pivot, b = the next pivot / running extreme) ⇒ record (divergence or not, with the reason).
        known = the degree's pivots known at known_bar: each RSI window stays inside its own swing (between the neighbouring opposite
        pivots), so the two windows never share a bar and a pivot's RSI value is the same in every pair."""
        kind = SIDE_KIND[side]
        rec = {"tf": self.tf, "degree": int(d), "side": side, "status": status, "status_by": status_by, "known_bar": int(known_bar),
               "known_time": str(self.B.ts.iloc[known_bar]), "bars": int(b_bar - a.bar), "window": list(self.win)}
        opp = [p.bar for p in known if p.kind != kind]
        before = [x for x in opp if x < a.bar]
        mid = [x for x in opp if a.bar < x < b_bar]
        # Abhi (final): RSI AT each swing — its extreme inside the swing's own span (between the neighbouring opposite swings; the swing
        # candle itself when there is no opposite swing on that side), never a bar count
        a_lo = before[-1] + 1 if before else a.bar
        a_hi = mid[-1] - 1 if mid else a.bar
        b_lo = mid[-1] + 1 if mid else b_bar
        ra = self._rsi_ext(a.bar, side, a_lo, min(a.confirm_bar, a_hi))
        rb = self._rsi_ext(b_bar, side, b_lo, cap_b)
        rec["L1"], rec["L2"] = self._pt(a.bar, a.price, ra), self._pt(b_bar, b_price, rb)
        rec.update(type=None, is_div=False, cap=None, price_rel=None, price_diff=round(float(b_price - a.price), 2), rsi_diff=None)
        if self.seg[a.bar] != self.seg[b_bar]:
            rec["reason"] = "pivots in different data segments"
            return rec
        if ra is None or rb is None:
            rec["reason"] = "RSI not available at a pivot (warm-up)"
            return rec
        dp = float(b_price - a.price)                                      # Abhi: a NEW extreme — strictly beyond, no tolerance band
        if kind == "H":
            rel = "equal high" if dp == 0 else ("higher high" if dp > 0 else "lower high")
            between = self.B.H[a.bar + 1:b_bar]
            clear = not len(between) or float(between.max()) <= max(a.price, b_price) + 1e-9
        else:
            rel = "equal low" if dp == 0 else ("lower low" if dp < 0 else "higher low")
            between = self.B.L[a.bar + 1:b_bar]
            clear = not len(between) or float(between.min()) >= min(a.price, b_price) - 1e-9
        r1, r2 = float(ra[0]), float(rb[0])                                # compared unrounded (no hidden tolerance); rounded only for display
        rec.update(price_rel=rel, tolerance=0.0, rsi_diff=round(r2 - r1, 2), consecutive=bool(clear))
        if not clear:
            rec["reason"] = "not consecutive pushes (a more extreme price between the pivots)"
            return rec
        extend = rel in ("higher high", "lower low")                         # Abhi: price makes a new extreme …
        if kind == "H":
            typ = "regular" if extend and r2 <= r1 else ("hidden" if not extend and r2 >= r1 else None)
        else:
            typ = "regular" if extend and r2 >= r1 else ("hidden" if not extend and r2 <= r1 else None)
        if typ == "hidden" and not self.s["div_hidden"]:
            typ = None
        if typ is None:
            if extend:
                word, op = ("high", ">") if kind == "H" else ("low", "<")
                rec["reason"] = f"RSI made a new {word} with price ({r2:.2f} {op} {r1:.2f})"
            else:
                rec["reason"] = f"price made a {rel} ({b_price:,.2f} vs {a.price:,.2f}); RSI {r1:.2f} → {r2:.2f}"
            return rec
        rec["type"] = typ
        if bool(self.s.get("div_bar_window", False)):                      # legacy what-if only — Abhi: no bar counts / minimum gaps
            lo, hi = self.win
            if not lo <= rec["bars"] <= hi:
                rec["cap"] = "max" if rec["bars"] > hi else "min"
                rec["reason"] = f"rejected only by the bar window: {rec['bars']} bars apart (window {lo}–{hi})"
                return rec
        rec["is_div"] = True
        rec["reason"] = None
        return rec

    def _count(self, rec, a_bar):
        """Multiple divergence: 1 + the count of the same-degree, same-side, same-type divergence that ended at L1 (consecutive)."""
        return 1 + self._chain.get((rec["degree"], rec["side"], rec["type"], a_bar), 0)

    def _finish(self, rec, a_bar, t):
        if rec["is_div"]:
            rec["count"] = self._count(rec, a_bar)
            self._chain[(rec["degree"], rec["side"], rec["type"], rec["L2"]["bar"])] = rec["count"]
            self.events.append(rec)
        elif rec["cap"]:
            self.rejects.append(rec)

    # -------------------------------------------------------------------------------------------- scan (bar by bar, bars ≤ t)
    def _scan(self):
        self.events, self.rejects = [], []
        self.latest = {}                                                # t ⇒ {(degree, side): record at t}
        self._chain = {}
        done = {}
        ptr = {d: 0 for d in self.degrees}
        known = {d: [] for d in self.degrees}
        cur = {}
        for t in range(self.n):
            for d in self.degrees:
                ps = self.piv[d]
                while ptr[d] < len(ps) and ps[ptr[d]].confirm_bar <= t:
                    b = ps[ptr[d]]
                    ptr[d] += 1
                    same = [p for p in known[d] if p.kind == b.kind and p.bar < b.bar]
                    known[d].append(b)
                    if not same:
                        continue
                    a = same[-1]
                    side = BEAR_SIDE if b.kind == "H" else BULL_SIDE
                    key = (d, side, a.bar, b.bar)
                    if key not in done:                                 # else: already confirmed earlier by a commitment candle
                        rec = self._eval(d, side, a, b.bar, b.price, b.confirm_bar, t, "confirmed", "right_side_bars", known[d])
                        self._finish(rec, a.bar, t)
                        done[key] = rec
                    cur[(d, side)] = done[key]
                if not known[d]:
                    continue
                last = known[d][-1]
                side = BEAR_SIDE if last.kind == "L" else BULL_SIDE      # the push in progress after the last confirmed pivot
                kind = SIDE_KIND[side]
                prev = [p for p in known[d] if p.kind == kind and p.bar < last.bar]
                if not prev or t <= last.bar or self.seg[t] != self.seg[last.bar]:
                    continue
                a = prev[-1]
                seg = np.arange(last.bar + 1, t + 1)
                y = self.B.H[seg] if kind == "H" else self.B.L[seg]
                ext = float(y.max()) if kind == "H" else float(y.min())
                m = int(seg[np.flatnonzero(y == ext)[-1]])               # later bar on a tie (swings2 rule)
                key = (d, side, a.bar, m)
                if key not in done:
                    ok, cm = (False, None) if t <= m else self._commit(t, side, ext)
                    if ok:
                        rec = self._eval(d, side, a, m, ext, t, t, "confirmed", "commitment_candle", known[d])
                        rec["commitment"] = cm
                        self._finish(rec, a.bar, t)
                        done[key] = rec
                    else:
                        rec = self._eval(d, side, a, m, ext, t, t, "forming", None, known[d])
                        if rec["is_div"]:
                            rec["count"] = self._count(rec, a.bar)
                    cur[(d, side)] = rec
                else:
                    cur[(d, side)] = done[key]
            self.latest[t] = dict(cur)

    # -------------------------------------------------------------------------------------------- public reads
    def with_area(self, rec):
        """A COPY of the record with the at / in area fact (at the record's known bar — the confirmation bar, or the read bar while
        forming); lazy because the area owner is costly. Stored records are never mutated (outputs never depend on earlier calls)."""
        out = dict(rec)
        if out.get("is_div") and "area" not in out:
            out["area"] = self.area_at(out["known_bar"], out["L2"]["price"], out["side"])
        return out

    def history(self, t=None, areas=False):
        """Every divergence confirmed by bar t (in known order) + the forming ones at t. areas ⇒ each with its area fact."""
        t = self.n - 1 if t is None else int(t)
        out = [x for x in self.events if x["known_bar"] <= t]
        out += [x for x in (self.latest.get(t) or {}).values() if x["status"] == "forming" and x["is_div"]]
        return [self.with_area(x) for x in out] if areas else out

    def cap_log(self, t=None):
        """Pairs rejected ONLY by the bar window (confirmed by t, plus the forming ones at t) — for Abhi's review of the cap."""
        t = self.n - 1 if t is None else int(t)
        out = [x for x in self.rejects if x["known_bar"] <= t]
        return out + [x for x in (self.latest.get(t) or {}).values() if x["status"] == "forming" and x["cap"]]

    def read(self, t=None):
        """Facts at closed bar t: per degree and side, the latest pair (the push in progress, or the last confirmed pair) with its
        divergence facts or the explicit absence statement; which status was used is logged. Never a score."""
        t = self.n - 1 if t is None else int(t)
        cur = self.latest.get(t) or {}
        latest, divs, caps, log = [], [], [], []
        for d in self.degrees:
            for side in (BEAR_SIDE, BULL_SIDE):
                x = cur.get((d, side))
                if x is None:
                    latest.append({"degree": d, "side": side, "statement": f"no {side} divergence (D{d}): fewer than two swing "
                                   f"{'highs' if side == BEAR_SIDE else 'lows'} of this degree known"})
                    continue
                x = self.with_area(x) if x["is_div"] else dict(x)
                st = (f"{div_label(x)} (D{d}, {x['price_rel']})" if x["is_div"]
                      else f"no {side} divergence (D{d}, {x['status']}): {x['reason']}")
                latest.append({"degree": d, "side": side, "statement": st, "pair": x})
                log.append({"degree": d, "side": side, "status": x["status"], "status_by": x["status_by"]})
                if x["is_div"]:
                    divs.append(x)
                elif x["cap"]:
                    caps.append(x)
        return {"owner": "rsi2.engine.Divergence", "kb": "method §3 RSI divergence (KB K10.4)", "tf": self.tf, "bar": t,
                "asof": str(self.B.ts.iloc[t]), "rsi": _r2(self.rsi[t]), "rsi_warmup": bool(self.warm[t]),
                "rsi_period": int(self.s["period"]), "rsi_window_bars": self.N, "bar_window": list(self.win),
                "hidden_enabled": bool(self.s["div_hidden"]), "degrees": list(self.degrees), "divergences": divs, "cap_rejected": caps,
                "latest": latest, "status_log": log,
                "note": "facts only — evidence inside the zone study; never a trigger alone, never a gate"}
