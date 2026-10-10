"""rsi2/engine.py — थर 6: RSI divergence (pivot-based; थर 1 pivots, RSI त्याच candle च्या close ला) आणि Cardwell rsi_range.

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

    def _clear(self, a, b, kind, d=0):
        """line_clear (RSI; L1 / L2 शेजारचे line_skip bars वगळून; D2 ⇒ 1H RSI) आणि price_clear (closes)."""
        lo, hi = a.bar, b.bar
        if hi - lo < 2:
            return True, True
        seg = np.arange(lo + 1, hi)
        pl = a.price + (b.price - a.price) * (seg - lo) / (hi - lo)
        cc = self.A["c"][seg]
        pc = bool(np.all(cc >= pl - 1e-9)) if kind == "L" else bool(np.all(cc <= pl + 1e-9))
        k = int(self.s["line_skip"])
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
        known = b.confirm_bar if d != 2 else max(b.confirm_bar, k2)
        gap_between = any(a.bar < g <= b.bar for g in self.res["gap_bar_2s"])
        grade = None
        if typ in (REG_BULL, REG_BEAR):
            grade = "मजबूत" if (r1 <= s["grade_os"] if typ == REG_BULL else r1 >= s["grade_ob"]) else "कमकुवत"
        return {"type": typ, "degree": d, "L1": {"bar": a.bar, "price": round(a.price, 2), "ts": str(self.ts.iloc[a.bar])},
                "L2": {"bar": b.bar, "price": round(b.price, 2), "ts": str(self.ts.iloc[b.bar])}, "rsi1": round(float(r1), 2),
                "rsi2": round(float(r2), 2), "gap": b.bar - a.bar, "known_bar": int(known), "line_clear": lc, "price_clear": pc,
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
    """एकाच दिशेच्या लागोपाठ ≥ 2 regular divergences ज्या price ने नाकारल्या (नंतरचा same-type confirmed pivot L2 पलीकडे trend-दिशेने)."""
    regs = [x for x in R.known(t) if x["type"] in (REG_BULL, REG_BEAR)]
    out = []
    for typ in (REG_BULL, REG_BEAR):
        kind = "L" if typ == REG_BULL else "H"
        rej = []
        for x in [y for y in regs if y["type"] == typ]:
            ps = [p for p in R.res["pivots"][0] if p.kind == kind and p.bar > x["L2"]["bar"] and p.confirm_bar <= t]
            nxt = ps[0] if ps else None
            if nxt is not None and ((nxt.price < x["L2"]["price"]) if kind == "L" else (nxt.price > x["L2"]["price"])):
                rej.append((x, nxt.confirm_bar))
            else:
                rej = []
        if len(rej) >= 2:
            out.append({"type": typ, "n": len(rej), "known_bar": rej[-1][1]})
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
