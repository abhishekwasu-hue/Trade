"""decision3/levels.py — ② Level (1H, trade-बाजूचा significant area), थर v2.2.

जन्म (known_at = त्या घटनेचा 15M close; त्याआधी level अस्तित्वात नाही):
  (a) 1H trend-degree swing = थर 1 D2 pivot (swings2) किंवा Daily swing. पट्टा = त्या swing candle (1H / Daily) चा wick-to-body
      (H ⇒ [body वरची कडा, high], L ⇒ [low, body खालची कडा]); किमान रुंदी σ_1H × level_min_width_sigma (टोकापासून body कडे वाढवून).
  (b) BOS: 15M close शेवटच्या confirmed D2 H वर (↑) / L खाली (↓) ⇒ त्या impulse चा origin = BOS आधीचा उलट D2 pivot; base = origin नंतरची
      पहिली trend-दिशेची 1H candle — तिचा पट्टा ↑ [low, open] / ↓ [open, high] (base चा उगम-भाग; किमान रुंदी). Role: ↑ support, ↓ resistance.
  (c) S/R flip (spec §5.4): पट्ट्यापलीकडे सलग `accept_closes` 15M closes (acceptance) ⇒ भूमिका उलट (support ⇄ resistance) — मृत्यू नाही.
      त्यापेक्षा कमी closes पलीकडे आणि परत आत ⇒ sweep (§7.2). Flip नंतर closes पुन्हा जुन्या बाजूला टिकले ⇒ flip अयशस्वी ⇒ जुनी भूमिका.
  (d) liquidity: दोन D2 pivots (त्याच प्रकारचे) σ_1H × liquidity_eq_sigma मध्ये ⇒ equal highs / lows पट्टा.
  लहान pivot (D0 / D1, 15M) पासून level नाही. Merge: नवा पट्टा जिवंत level ला overlap ⇒ एकच (पट्टा एकत्र, जन्म-कारणं एकत्र).
जीवनक्रम (प्रत्येक बंद 15M bar, जन्मानंतरच्या bars): चाचणी (किंमत पट्ट्यात / पलीकडे — एका भेटीला एकदा), sweep (wick पलीकडे, close परत
trade-बाजूला / पट्ट्यात; किंवा acceptance शिवाय 1–2 closes पलीकडे आणि परत) ⇒ ★ +1, flip (acceptance ⇒ भूमिका उलट), मृत्यू फक्त: level पलीकडचा (मूळ भूमिकेच्या बाजूचा) structural swing
(confirmed D2 pivot) close ने तुटला. जिवंत level snapshot मधून कधीच prune नाही (फक्त chart वर दूरची लपवा). `self` नियम नाही (K च्या टोकाचा level दुसऱ्या चाचणीला वैध).
गुण: Daily confluence (+1), fresh (+1), अनेक चाचण्या (−0.5 प्रत्येक दुसऱ्या पासून), sweep ★; impulse retracement / trendline (C पायरी).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import settings as S3

SUP, RES = "support", "resistance"


@dataclass
class Level:
    id: int
    role0: str
    lo: float
    hi: float
    born_bar: int                       # 15M bar ज्याच्या close ला level माहीत झाला
    births: list = field(default_factory=list)      # ["a:D2", "a:D", "b", "d"] (+ "c" flip नंतर)
    anchor: float = None                # swing टोक (chart / लेबल)
    events: list = field(default_factory=list)      # [(bar, "test" | "sweep" | "flip" | "dead", तपशील)]
    dead_bar: int = None
    merged_from: list = field(default_factory=list)
    bands: list = field(default_factory=list)       # [(bar, lo, hi)] — merge ने पट्टा बदलला तर इतिहास (truncation-safe snapshot)

    def band_at(self, t):
        lo, hi = self.lo, self.hi
        for b, l0, h0 in self.bands:
            if b <= t:
                lo, hi = l0, h0
        return lo, hi

    def role_at(self, t):
        r = self.role0
        for b, kind, _ in self.events:
            if b <= t and kind == "flip":
                r = RES if r == SUP else SUP
        return r

    def count(self, kind, t):
        return sum(1 for b, k, _ in self.events if k == kind and b <= t)

    def alive(self, t):
        return self.born_bar <= t and (self.dead_bar is None or self.dead_bar > t)


def h1_frame(m15):
    """15M ⇒ 1H (09:15-anchored) आणि प्रत्येक 15M bar चा 1H index."""
    t = pd.to_datetime(m15["timestamp"])
    day = t.dt.normalize()
    k = ((t - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(hours=1)).astype(int)
    key = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(hours=1)
    g = m15.assign(_k=key).groupby("_k", sort=True).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                       close=("close", "last"))
    idx = {ts: i for i, ts in enumerate(g.index)}
    return g.reset_index().rename(columns={"_k": "timestamp"}), np.array([idx[x] for x in key])


def _band_swing(kind, o, h, l, c, price, w):
    """wick-to-body; किमान रुंदी w (टोकापासून body कडे)."""
    if kind == "H":
        hi = float(price)
        lo = min(hi, float(max(o, c)))
        if hi - lo < w:
            lo = hi - w
    else:
        lo = float(price)
        hi = max(lo, float(min(o, c)))
        if hi - lo < w:
            hi = lo + w
    return lo, hi


class Levels:
    """सगळ्या levels चा जीवनक्रम (एकदा, bar क्रमाने). snapshot(t) फक्त t पर्यंतची माहिती वापरतो."""

    def __init__(self, res, daily_states=None, daily_df=None, s=None):
        self.s = S3.load(s)
        self.res = res
        m15 = res["m15"]
        self.m15 = m15
        self.n = len(m15)
        self.A = {k: m15[k].to_numpy(float) for k in ("open", "high", "low", "close")}
        self.ts = pd.to_datetime(m15["timestamp"]).reset_index(drop=True)
        self.bar_end = pd.to_datetime(m15["bar_end"]).reset_index(drop=True) if "bar_end" in m15.columns else \
            self.ts + pd.Timedelta(minutes=15)
        self.h1, self.h1_of = h1_frame(m15)
        self.sig1h = np.array([res["sigma_1h"].get(pd.Timestamp(d), np.nan) for d in self.ts.dt.normalize()], float)
        deg = int(self.s["level_degree"])
        self.piv = [p for p in res["pivots"][deg]]
        self.daily_df = daily_df
        self.daily_states = daily_states or []
        self.L = []
        self.bos = []                       # [(bar, dir, origin pivot)] — ③ impulse साठी (known_at = bar चा close)
        self.known_by = []                  # प्रत्येक bar ला माहीत D2 pivots ची संख्या (confirm क्रमाने)
        self._broken = set()                # BOS झालेले D2 pivots — retest + reclaim ला नवा BOS नाही (K जपला जातो)
        self._pv_sorted = sorted(self.piv, key=lambda p: p.confirm_bar)
        self._run()

    # ------------------------------------------------------------------------------------------ जन्म
    def _h1_upto(self, j, t):
        """1H candle j चे (open, high, low, close) — फक्त 15M bar t पर्यंतचे bars (अपूर्ण तासात पुढचे bars नाहीत ⇒ lookahead नाही)."""
        ix = np.flatnonzero((self.h1_of == j) & (np.arange(self.n) <= t))
        if not len(ix):
            return None
        return (float(self.A["open"][ix[0]]), float(self.A["high"][ix].max()), float(self.A["low"][ix].min()), float(self.A["close"][ix[-1]]))

    def _w(self, t):
        sg = self.sig1h[min(t, self.n - 1)]
        return float(self.s["level_min_width_sigma"]) * (sg if np.isfinite(sg) else 0.0)

    def _born(self, t, role, lo, hi, birth, anchor):
        for L in self.L:                                                  # merge: overlap असलेला जिवंत level
            if L.alive(t) and not (hi < L.lo or lo > L.hi):
                L.lo, L.hi = min(L.lo, lo), max(L.hi, hi)
                L.bands.append((t, L.lo, L.hi))
                if birth not in L.births:
                    L.births.append(birth)
                L.merged_from.append((t, birth))
                return L
        L = Level(len(self.L), role, float(lo), float(hi), int(t), [birth], anchor)
        L.bands.append((t, L.lo, L.hi))
        self.L.append(L)
        return L

    def _births_at(self):
        """{15M bar: [(role, lo, hi, birth, anchor)]} — known_at क्रमाने."""
        out = {}
        h1_of = self.h1_of
        for p in self.piv:
            o, hh, ll, cc = self._h1_upto(h1_of[p.bar], p.confirm_bar)
            lo, hi = _band_swing(p.kind, o, hh, ll, cc, p.price, self._w(p.confirm_bar))
            out.setdefault(p.confirm_bar, []).append((RES if p.kind == "H" else SUP, lo, hi, "a:D2", p.price))
        # Daily swings (known_at = त्या दिवसाचा close ⇒ त्या दिवसाचा शेवटचा 15M bar)
        if self.daily_states and self.daily_df is not None:
            seen = set()
            dd = self.daily_df.reset_index(drop=True)
            for st in self.daily_states:
                for p in st.pivots:
                    key = (p.kind, p.bar)
                    if key in seen:
                        continue
                    seen.add(key)
                    js = np.flatnonzero(self.bar_end.to_numpy() >= np.datetime64(p.known_at))
                    if not len(js):
                        continue
                    t = int(js[0])
                    lo, hi = _band_swing(p.kind, dd["open"].iloc[p.bar], dd["high"].iloc[p.bar], dd["low"].iloc[p.bar], dd["close"].iloc[p.bar],
                                         p.price, self._w(t))
                    out.setdefault(t, []).append((RES if p.kind == "H" else SUP, lo, hi, "a:D", p.price))
        # (d) liquidity: equal highs / lows (D2)
        eqs = float(self.s["liquidity_eq_sigma"])
        for kind in ("H", "L"):
            ps = [p for p in self.piv if p.kind == kind]
            for i in range(1, len(ps)):
                a, b = ps[i - 1], ps[i]
                t = max(a.confirm_bar, b.confirm_bar)
                sg = self.sig1h[t]
                if np.isfinite(sg) and abs(a.price - b.price) <= eqs * sg:
                    lo, hi = min(a.price, b.price), max(a.price, b.price)
                    w = self._w(t)
                    if hi - lo < w:
                        lo, hi = (hi - w, hi) if kind == "H" else (lo, lo + w)
                    out.setdefault(t, []).append((RES if kind == "H" else SUP, lo, hi, "d", (a.price + b.price) / 2))
        return out

    def _bos(self, t, known):
        """15M bar t चा close शेवटच्या confirmed D2 H / L पलीकडे (आधीच्या bar चा close अजून आत) ⇒ (dir, origin pivot) किंवा None."""
        if t == 0:
            return None
        C = self.A["close"]
        Hs = [p for p in known if p.kind == "H"]
        Ls = [p for p in known if p.kind == "L"]
        if Hs and C[t] > Hs[-1].price >= C[t - 1] and (Hs[-1].kind, Hs[-1].bar) not in self._broken:
            orig = [p for p in Ls if p.bar < t]
            if orig:
                self._broken.add((Hs[-1].kind, Hs[-1].bar))
                return 1, orig[-1]
        if Ls and C[t] < Ls[-1].price <= C[t - 1] and (Ls[-1].kind, Ls[-1].bar) not in self._broken:
            orig = [p for p in Hs if p.bar < t]
            if orig:
                self._broken.add((Ls[-1].kind, Ls[-1].bar))
                return -1, orig[-1]
        return None

    def _base(self, d, origin, t):
        """origin नंतरची पहिली trend-दिशेची 1H candle (BOS bar पर्यंत; t पर्यंतचाच भाग). Origin ची स्वतःची 1H candle वगळली (spec ② (b)
        "origin नंतरची"); BOS त्याच तासात झाला तर ती candle (दुसरी नाही)."""
        h1_of = self.h1_of
        j0, j1 = h1_of[origin.bar], h1_of[t]
        for j in range(min(j0 + 1, j1), j1 + 1):
            c4 = self._h1_upto(j, t)                                     # t पर्यंतचाच भाग (अपूर्ण तास ⇒ पुढचे bars नाहीत)
            if c4 is not None and (c4[3] - c4[0]) * d > 0:
                return j, c4
        return None

    # ------------------------------------------------------------------------------------------ जीवनक्रम
    def _run(self):
        births = self._births_at()
        H, Lo, C = self.A["high"], self.A["low"], self.A["close"]
        touching, excursion = {}, {}
        acc = int(self.s["accept_closes"])
        pv = self._pv_sorted
        k = 0
        known = []
        for t in range(self.n):
            # t च्या close पर्यंत माहीत pivots
            while k < len(pv) and pv[k].confirm_bar <= t:
                known.append(pv[k])
                k += 1
            # आधीचे levels: चाचणी / sweep / flip / मृत्यू (जन्म bar नंतरच)
            for L in self.L:
                if not L.alive(t) or L.born_bar >= t:
                    continue
                role = L.role_at(t - 1)
                inside = Lo[t] <= L.hi and H[t] >= L.lo
                if role == SUP:
                    beyond_wick, beyond_close = Lo[t] < L.lo, C[t] < L.lo
                else:
                    beyond_wick, beyond_close = H[t] > L.hi, C[t] > L.hi
                # मृत्यू: मूळ भूमिकेच्या (role0) पलीकडचा structural swing close ने तुटला — support ⇒ खालचा जवळचा D2 L, resistance ⇒ वरचा D2 H
                # (flip झालेला level सुद्धा: तुटलेला support ⇒ resistance, पण खालचा swing close ने तुटला ⇒ मेला). OPEN_QUESTIONS Q2.
                if L.role0 == SUP:
                    sw = [p.price for p in known if p.kind == "L" and p.price < L.lo]
                    dead = bool(sw) and C[t] < max(sw)
                else:
                    sw = [p.price for p in known if p.kind == "H" and p.price > L.hi]
                    dead = bool(sw) and C[t] > min(sw)
                if inside and not touching.get(L.id):
                    L.events.append((t, "test", ""))
                touching[L.id] = inside
                if dead:
                    L.events.append((t, "dead", f"पलीकडचा swing {max(sw) if L.role0 == SUP else min(sw):,.2f} close ने तुटला"))
                    L.dead_bar = t
                    continue
                exc = excursion.get(L.id, 0)
                if beyond_close:
                    exc += 1
                    if exc >= acc:                                         # acceptance: पलीकडे closes टिकले ⇒ flip (पक्का)
                        old = "flip" if L.count("flip", t - 1) % 2 == 0 else "flip_failed"
                        L.events.append((t, "flip", f"{acc} closes पट्ट्यापलीकडे ⇒ {'resistance' if role == SUP else 'support'}"
                                                    + (" (flip अयशस्वी ⇒ जुनी भूमिका)" if old == "flip_failed" else "")))
                        if "c" not in L.births:
                            L.births.append("c")
                        exc = 0
                elif exc > 0 or beyond_wick:                               # पलीकडे गेली पण acceptance शिवाय परत ⇒ sweep ★
                    L.events.append((t, "sweep", "wick पलीकडे, close परत" if exc == 0 else f"{exc} close(s) पलीकडे, परत आत"))
                    exc = 0
                excursion[L.id] = exc
            # BOS ⇒ (b) origin base
            self.known_by.append(len(known))
            b = self._bos(t, known)
            if b is not None:
                d, origin = b
                self.bos.append((t, d, origin))
                jb = self._base(d, origin, t)
                if jb is not None:
                    _j, (o, hh, ll, _c) = jb
                    lo, hi = (ll, o) if d > 0 else (o, hh)
                    w = self._w(t)
                    if hi - lo < w:
                        if d > 0:
                            hi = lo + w
                        else:
                            lo = hi - w
                    births.setdefault(t, []).append((SUP if d > 0 else RES, lo, hi, "b", origin.price))
            for role, lo, hi, why, anchor in births.get(t, []):
                self._born(t, role, lo, hi, why, anchor)

    # ------------------------------------------------------------------------------------------ snapshot
    def score(self, L, t, births):
        """फक्त माहिती (निर्णयात नाही): births = t ला माहीत जन्म-कारणं (snapshot मधून ⇒ नंतरचा merge / flip नाही)."""
        tests = L.count("test", t)
        sc = 0.0
        if "a:D" in births:
            sc += float(self.s["score_daily_bonus"])
        if tests == 0:
            sc += float(self.s["score_fresh_bonus"])
        sc -= float(self.s["score_test_penalty"]) * max(0, tests - 1)
        return sc

    def snapshot(self, t):
        """t च्या close ला जिवंत levels (dict), किंमतीपासूनच्या अंतरासह."""
        c = float(self.A["close"][t])
        sg = self.sig1h[t]
        out = []
        for L in self.L:
            if not L.alive(t):
                continue
            lo, hi = L.band_at(t)
            dist = 0.0 if lo <= c <= hi else (lo - c if c < lo else c - hi)
            births = [L.births[0]] + [b for tm, b in L.merged_from if tm <= t and b != L.births[0]]
            births = list(dict.fromkeys(births)) + (["c"] if L.count("flip", t) else [])
            out.append({"id": L.id, "role": L.role_at(t), "lo": round(lo, 2), "hi": round(hi, 2), "births": births,
                        "anchor": L.anchor, "tests": L.count("test", t), "sweeps": L.count("sweep", t), "flips": L.count("flip", t),
                        "fresh": L.count("test", t) == 0, "score": self.score(L, t, births), "dist": round(dist, 2),
                        "dist_sigma": round(dist / sg, 2) if np.isfinite(sg) and sg > 0 else None,
                        "above": lo > c, "below": hi < c})
        return out

    def active(self, t, trend):
        """trade-बाजूची जवळची levels (≤ active_levels_max). DOWN ⇒ किंमतीवरचे / किंमत ज्यात आहे ते resistance; UP ⇒ खालचे support;
        RANGE ⇒ खालचा support + वरचा resistance (प्रत्येकी जवळचा)."""
        snap = self.snapshot(t)
        m = int(self.s["active_levels_max"])
        sup = sorted([x for x in snap if x["role"] == SUP and not x["above"]], key=lambda x: x["dist"])
        res = sorted([x for x in snap if x["role"] == RES and not x["below"]], key=lambda x: x["dist"])
        if trend == "DOWN":
            return res[:m]
        if trend == "UP":
            return sup[:m]
        if trend == "RANGE":
            return (sup[:1] + res[:1])[:m]
        return []

    def known_pivots(self, t):
        """t च्या close ला माहीत D2 pivots (confirm क्रमाने)."""
        return self._pv_sorted[:self.known_by[t]] if t < len(self.known_by) else list(self._pv_sorted)
