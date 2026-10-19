"""decision3/levels.py — ② Level (1H, trade-बाजूचा significant area), थर v2.2.

जन्म (known_at = त्या घटनेचा 15M close; त्याआधी level अस्तित्वात नाही):
  (a) 1H trend-degree swing = थर 1 D2 pivot (swings2) किंवा Daily swing. पट्टा = त्या swing candle (1H / Daily) चा wick-to-body
      (H ⇒ [body वरची कडा, high], L ⇒ [low, body खालची कडा]) — त्या candle चा स्वतःचा पट्टा (Abhi Z-1x: आकड्याने रुंद नाही;
      `level_min_width_sigma` > 0 = जुनी किमान रुंदी, फक्त what-if).
  (b) BOS: 15M close शेवटच्या confirmed D2 H वर (↑) / L खाली (↓) ⇒ त्या impulse चा origin = BOS आधीचा उलट D2 pivot; base = origin नंतरची
      पहिली trend-दिशेची 1H candle — तिचा पट्टा ↑ [low, open] / ↓ [open, high] (base चा उगम-भाग; किमान रुंदी). Role: ↑ support, ↓ resistance.
  (c) S/R flip (spec §5.4): पट्ट्यापलीकडे सलग `accept_closes` 15M closes (acceptance) ⇒ भूमिका उलट (support ⇄ resistance) — मृत्यू नाही.
      त्यापेक्षा कमी closes पलीकडे आणि परत आत ⇒ sweep (§7.2). Flip नंतर closes पुन्हा जुन्या बाजूला टिकले ⇒ flip अयशस्वी ⇒ जुनी भूमिका.
  (d) liquidity: दोन D2 pivots (त्याच प्रकारचे) σ_1H × liquidity_eq_sigma मध्ये ⇒ equal highs / lows पट्टा.
  लहान pivot (D0 / D1, 15M) पासून level नाही. Merge: नवा पट्टा जिवंत level ला overlap ⇒ एकच (पट्टा एकत्र, जन्म-कारणं एकत्र).
जीवनक्रम (प्रत्येक बंद 15M bar, जन्मानंतरच्या bars): चाचणी (किंमत पट्ट्यात / पलीकडे — एका भेटीला एकदा), sweep (wick पलीकडे, close परत
trade-बाजूला / पट्ट्यात; किंवा acceptance शिवाय 1–2 closes पलीकडे आणि परत) ⇒ ★ +1, flip (acceptance ⇒ भूमिका उलट), मृत्यू फक्त: level पलीकडचा (चालू भूमिकेच्या बाजूचा, TL1) structural swing
(confirmed D2 pivot) close ने तुटला. जिवंत level snapshot मधून कधीच prune नाही (फक्त chart वर दूरची लपवा). `self` नियम नाही (K च्या टोकाचा level दुसऱ्या चाचणीला वैध).
गुण: Daily confluence (+1), fresh (+1), अनेक चाचण्या (−0.5 प्रत्येक दुसऱ्या पासून), sweep ★; impulse retracement / trendline (C पायरी).

KB K4 flip rule (Abhi, final — `level_flip_rule` = "far_swing", default; decision3/flip.py). State per level, bar by bar (bars ≤ t only):
  ACTIVE / TESTED (tests ≥ 1) ──acceptance (accept_closes closes beyond)──▶ BROKEN  (old role kept; NOT a trade location — `active` skips it)
  ACTIVE / TESTED / BROKEN ──far-side swing reached during the excursion (≥ 1 close beyond)──▶ FLIPPED (role reversed, "c")
  BROKEN ──accept_closes closes back on the role's own side──▶ previous state ("reclaim" = the break failed, role kept; logged as a sweep ★)
  fewer than accept_closes closes beyond and back, far swing not reached ⇒ sweep ★ (old role).
  FLIPPED ──broken again and ITS far-side swing reached──▶ DEAD (Abhi Z-1f: once flipped the old role is over; no second flip, logged).
  Far-side swing (`flip.far_swing`): the nearest confirmed D`level_degree` pivot beyond the band on the break side that formed before the
  excursion began — reached when price trades past it; none (new highs / lows) ⇒ the first swing formed after the break, reached when it
  is CONFIRMED (Abhi Z-1s, the corrected Z-1a wording; it need not be broken — `flip.reached`). Known = confirm_bar ≤ t. Only STRUCTURAL
  swings count (Abhi Z-1y, `flip.structural`): a sweep wick just beyond the band (its candle closed back inside) is never the far swing.
  A new swing never merges into a DEAD level (it is born as its own level); `level_death_side` (TL1) is legacy only.
  Facts per level (snapshot): state, broken_at, break_dir, exc_start, far_swing {price, bar, ts, source}, flipped_at (DEAD: dead_at).
  "acceptance" = the old spec §5.4 (acceptance ⇒ flip at once; flip_failed back), kept only for old tests / what-if.
"""
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import flip as FL
from . import settings as S3

SUP, RES = "support", "resistance"
# Abhi Z-1u: every band has ONE timeframe and is built only from its own base / reaction candles (TA4) — never merged with another level,
# never widened. 1H = the trade-location timeframe; Daily = a location only where no 1H zone overlaps it; Weekly (whole weekly candles) =
# context only. A Daily / Weekly band overlapping a 1H band is a confluence label on the 1H band (evidence).
TF_OF = {"a:D2": "1H", "b": "1H", "d": "1H", "a:D": "D", "a:D-prior": "D", "a:W-prior": "W"}
TF_WORD = {"1H": "1H", "D": "Daily", "W": "Weekly"}
PROV_WIDTH = "provisional width"            # Abhi PF-2: σ_1H missing ⇒ min width from the median 1H range (bars ≤ t) — labelled
log = logging.getLogger(__name__)


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
    flip_facts: list = field(default_factory=list)  # [(bar, dict)] — K4 BROKEN / FLIPPED facts (broken_at, far_swing, flipped_at …)
    prov: list = field(default_factory=list)        # Abhi PF-2: [(from bar, to bar | None)] — band min width provisional (σ_1H missing)
    tf: str = "1H"                                  # Abhi Z-1u: the band's own timeframe (1H / D / W) — never mixed
    lineage: list = field(default_factory=list)     # Abhi Z-1u: [{"bar", "overlaps": level id, "band": (lo, hi)}] — "born from" evidence

    def provisional(self, t):
        """PF-2: the band's min width at t is the provisional one (born / merged while σ_1H was missing, σ_1H not known yet)."""
        return any(a <= t and (b is None or t < b) for a, b in self.prov)

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

    def facts_at(self, t):
        """शेवटची K4 flip facts नोंद (bar ≤ t) — नाही ⇒ {}."""
        f = {}
        for b, x in self.flip_facts:
            if b <= t:
                f = x
        return f

    def state_at(self, t):
        """K4 state at bar t: DEAD / BROKEN / FLIPPED / TESTED / ACTIVE (events ≤ t only)."""
        if not self.alive(t):
            return FL.DEAD
        base, st = FL.ACTIVE, FL.ACTIVE
        for b, kind, _ in self.events:
            if b > t:
                continue
            if kind == "flip":
                base = st = FL.FLIPPED
            elif kind == "broken":
                st = FL.BROKEN
            elif kind == "reclaim":
                st = base
        if st == FL.ACTIVE and self.count("test", t):
            return FL.TESTED
        return st

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
    """wick-to-body of the swing candle. Abhi (TA4 / Z-1x): an area is always a band from the candle where buyers / sellers acted, never a
    single price — no wick on that side (closed at its extreme) ⇒ the candle's body; no body either ⇒ its whole range. w > 0 = the
    legacy minimum width (what-if only)."""
    if kind == "H":
        hi = float(price)
        lo = min(hi, float(max(o, c)))
        if lo >= hi and float(h) > lo:                                     # the candle's own upper wick
            hi = float(h)
        if lo >= hi:
            lo = min(hi, float(min(o, c)))
        if lo >= hi:
            lo = min(hi, float(l))
        if hi - lo < w:
            lo = hi - w
    else:
        lo = float(price)
        hi = max(lo, float(min(o, c)))
        if hi <= lo and float(l) < hi:                                     # the candle's own lower wick
            lo = float(l)
        if hi <= lo:
            hi = max(lo, float(max(o, c)))
        if hi <= lo:
            hi = max(lo, float(h))
        if hi - lo < w:
            hi = lo + w
    return lo, hi


class Levels:
    """सगळ्या levels चा जीवनक्रम (एकदा, bar क्रमाने). snapshot(t) फक्त t पर्यंतची माहिती वापरतो."""

    def __init__(self, res, daily_states=None, daily_df=None, s=None, weekly_states=None, weekly_df=None):
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
        self.weekly_states = weekly_states or []
        self.weekly_df = weekly_df
        self.prior = []                     # Q40: 15M window आधीचे trend-degree Daily + Weekly swings (debug / count)
        self.prior_note = None              # Abhi Z-1t: why Q40 prior levels were skipped (logged, never silent)
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
        t = min(t, self.n - 1)
        sg = self.sig1h[t]
        if not np.isfinite(sg):          # TA4: σ_1H अजून नाही (window चे पहिले sigma_sessions, Q40 prior levels bar 0) ⇒ आधी रुंदी 0 ⇒ एकच-किंमत
            hl = pd.DataFrame({"h": self.A["high"][:t + 1], "l": self.A["low"][:t + 1], "j": self.h1_of[:t + 1]}).groupby("j")
            sg = float(np.median(hl["h"].max() - hl["l"].min()))        # तात्पुरता: bars ≤ t चे 1H ranges चा median (lookahead नाही)
        return float(self.s["level_min_width_sigma"]) * (sg if np.isfinite(sg) else 0.0)

    def _born(self, t, role, lo, hi, birth, anchor):
        """Abhi Z-1u: a birth always BUILDS its own band (its own candles, its own timeframe) — never merged into another band, never
        widening one. A birth lying wholly inside an alive same-timeframe, same-role band is that zone (lineage only, band unchanged); one
        that overlaps it partly is its own level with the overlap recorded as lineage ("born from" evidence); other timeframes are related
        only as confluence labels (`snapshot`)."""
        tf = TF_OF.get(birth, "1H")
        if self.s.get("level_merge", False):                              # legacy only (old tests / what-if): merge + widen, any timeframe
            for o in self.L:
                if o.alive(t) and not (hi < o.lo or lo > o.hi):
                    o.lo, o.hi = min(o.lo, lo), max(o.hi, hi)
                    o.bands.append((t, o.lo, o.hi))
                    if birth not in o.births:
                        o.births.append(birth)
                    o.merged_from.append((t, birth))
                    return o
        for o in self.L:                                                   # inside an alive same-timeframe, same-role band ⇒ the same zone:
            if o.tf == tf and o.alive(t) and o.role_at(t) == role:          # lineage only ("born from" evidence), the band is unchanged
                olo, ohi = o.band_at(t)
                if olo <= lo and hi <= ohi:
                    o.merged_from.append((t, birth))                       # births by time (snapshot reads merged_from ≤ t)
                    if birth not in o.births:
                        o.births.append(birth)
                    o.lineage.append({"bar": int(t), "inside": birth, "band": (round(float(lo), 2), round(float(hi), 2))})
                    return o
        L = Level(len(self.L), role, float(lo), float(hi), int(t), [birth], anchor, tf=tf)
        for o in self.L:
            if o.tf == tf and o.alive(t):
                olo, ohi = o.band_at(t)
                if not (hi < olo or lo > ohi):
                    L.lineage.append({"bar": int(t), "overlaps": o.id, "band": (round(olo, 2), round(ohi, 2))})
        L.bands.append((t, L.lo, L.hi))
        self.L.append(L)
        return L

    def _prior_levels(self):
        """Q40 (Abhi): 15M window आधीचे महत्त्वाचे Daily levels — फक्त trend-degree swings (degree-aware Dow चे impulse origin / टोक =
        correction टोकं) + Weekly swings, window सुरुवातीच्या किंमतीपासून `prior_level_atr_mult` × ATR_D आत. bar 0 ला जन्म; भूमिका
        तेव्हाच्या किंमतीनुसार (वर ⇒ resistance, खाली ⇒ support). तारीख output मध्ये नाही (NIFTY holdout swing ⇒ फक्त किंमत, Q39)."""
        self.prior_note = None
        if not self.n:
            return []
        dd = None if self.daily_df is None else self.daily_df.reset_index(drop=True)
        day0 = self.ts.iloc[0].normalize()
        t0_end = self.bar_end.iloc[0]
        before = dd[pd.to_datetime(dd["timestamp"]) < day0] if dd is not None and len(dd) else []
        if not len(before):                                                # Abhi Z-1t: never silent
            self.prior_note = "0 Daily bars before window ⇒ Q40 prior levels skipped"
            log.warning("decision3 levels: %s (15M window starts %s)", self.prior_note, day0.date())
            return []
        nA = int(self.s["prior_level_atr_n"])                              # (ATR only for the legacy "atr" rule)
        b = before.tail(nA + 1)
        pc = b["close"].shift(1)
        tr = np.maximum(b["high"] - b["low"], np.maximum((b["high"] - pc).abs(), (b["low"] - pc).abs())).iloc[1:]
        atr = float(tr.mean()) if len(tr) else float((b["high"] - b["low"]).mean())
        px0 = float(self.A["open"][0])
        lim = float(self.s["prior_level_atr_mult"]) * atr
        cand = {}
        self.prior = []

        def add(p):
            if p is not None and p.known_at <= t0_end:
                cand[("D", p.kind, p.bar)] = (p, "a:D-prior", dd)
        pre = [st for st in self.daily_states if st.known_at is not None and st.known_at <= t0_end]
        leg, end = None, None
        for st in pre:                                                     # degree-aware Dow ने वापरलेले swings (known ≤ window सुरुवात)
            add(st.protected)                                              # impulse origin / correction टोक
            key = (st.trend, None if st.protected is None else (st.protected.kind, st.protected.bar))
            if key != leg:                                                 # impulse leg संपला ⇒ त्याचं शेवटचं टोक (चालू running low नाही)
                add(end)
                leg = key
            end = getattr(st, "imp_end", None)
        add(end)
        if pre and pre[-1].phase in ("correction", "origin_broken") and pre[-1].imp_end is not None:
            last = pre[-1]                                                 # window सुरुवातीला चालू correction चं confirmed टोक
            ok = "H" if last.imp_end.kind == "L" else "L"
            xs = [p for p in last.pivots if p.kind == ok and p.bar > last.imp_end.bar and p.known_at <= t0_end]
            if xs:
                add(max(xs, key=lambda p: p.price) if ok == "H" else min(xs, key=lambda p: p.price))
        if self.weekly_states and self.weekly_df is not None:
            wk = [x for x in self.weekly_states if x.known_at is not None and x.known_at <= t0_end]
            if wk:
                wdf = self.weekly_df.reset_index(drop=True)
                for p in wk[-1].pivots:
                    if p.known_at <= t0_end:
                        cand[("W", p.kind, p.bar)] = (p, "a:W-prior", wdf)
        out = []
        prule = self.s.get("prior_level_rule", "all")
        if prule not in ("all", "atr"):
            raise ValueError(f"prior_level_rule {prule!r} — all / atr पैकी")
        for (_, kind, bar), (p, birth, src) in sorted(cand.items(), key=lambda kv: kv[0]):
            if prule == "atr" and abs(p.price - px0) > lim:                # legacy what-if: within prior_level_atr_mult × ATR_D of price
                continue                                                   # (method: every trend-degree prior swing is an area; its role
                                                                           # at the window start = which side of price it is on)
            r = src.iloc[p.bar]
            lo, hi = _band_swing(p.kind, r["open"], r["high"], r["low"], r["close"], p.price, self._w(0))
            role = RES if lo > px0 else (SUP if hi < px0 else (RES if p.kind == "H" else SUP))
            out.append((role, lo, hi, birth, p.price))
            self.prior.append({"src": birth, "kind": p.kind, "price": float(p.price), "role": role})
        return out

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
            day0 = self.ts.iloc[0].normalize() if self.n else None
            # Q33: Daily पूर्ण history (warm-up) — पण level जीवनक्रमाला 15M इतिहास लागतो ⇒ 15M window आधी बनलेले Daily pivots level म्हणून
            # जन्मत नाहीत (आधीचे breaks / flips माहीत नाहीत; आणि NIFTY holdout काळातले level output मध्ये नाहीत)
            for st in self.daily_states:
                if day0 is not None and st.day is not None and st.day < day0:
                    continue
                for p in st.pivots:
                    key = (p.kind, p.bar)
                    if key in seen or p.known_at <= self.bar_end.iloc[0]:
                        continue                                           # window सुरुवातीला आधीच माहीत ⇒ फक्त Q40 prior मार्गाने
                    seen.add(key)
                    js = np.flatnonzero(self.bar_end.to_numpy() >= np.datetime64(p.known_at))
                    if not len(js):
                        continue
                    t = int(js[0])
                    lo, hi = _band_swing(p.kind, dd["open"].iloc[p.bar], dd["high"].iloc[p.bar], dd["low"].iloc[p.bar], dd["close"].iloc[p.bar],
                                         p.price, self._w(t))
                    out.setdefault(t, []).append((RES if p.kind == "H" else SUP, lo, hi, "a:D", p.price))
        for item in self._prior_levels():
            out.setdefault(0, []).append(item)
        # (d) liquidity: equal highs / lows (D2) — Abhi's method §3 "equal": the later extreme reaches the earlier swing's own band
        # (its wick-to-body) and does not go beyond it ⇒ the same area reacted twice (double top / bottom). One base ⇒ the earlier
        # swing's band; it is born as a lineage of that level ("d"). `liquidity_rule` "sigma" = the legacy σ_1H tolerance (what-if).
        lrule = self.s.get("liquidity_rule", "equal")
        if lrule not in ("equal", "sigma"):
            raise ValueError(f"liquidity_rule {lrule!r} — equal / sigma पैकी")
        eqs = float(self.s["liquidity_eq_sigma"])
        for kind in ("H", "L"):
            ps = [p for p in self.piv if p.kind == kind]
            for i in range(1, len(ps)):
                a, b = ps[i - 1], ps[i]
                t = max(a.confirm_bar, b.confirm_bar)
                if lrule == "sigma":
                    sg = self.sig1h[t]
                    if not (np.isfinite(sg) and abs(a.price - b.price) <= eqs * sg):
                        continue
                    lo, hi = min(a.price, b.price), max(a.price, b.price)
                else:
                    o, hh, ll, cc = self._h1_upto(self.h1_of[a.bar], a.confirm_bar)
                    alo, ahi = _band_swing(kind, o, hh, ll, cc, a.price, 0.0)
                    if not ((alo <= b.price <= a.price) if kind == "H" else (a.price <= b.price <= ahi)):
                        continue
                    lo, hi = alo, ahi
                if hi <= lo:                                           # exactly equal extremes ⇒ the two swing candles' wick-to-body
                    lo, hi = min(_band_swing(kind, *(float(self.A[k][q.bar]) for k in ("open", "high", "low", "close")), q.price, 0.0)[0]
                                 for q in (a, b)), max(_band_swing(kind, *(float(self.A[k][q.bar]) for k in ("open", "high", "low", "close")),
                                                                   q.price, 0.0)[1] for q in (a, b))
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
        death_side = self.s.get("level_death_side", "role")
        if death_side not in ("role0", "role"):
            raise ValueError(f"level_death_side {death_side!r} — role0 / role पैकी")
        rule = self.s.get("level_flip_rule", "far_swing")
        if rule not in FL.RULES:
            raise ValueError(f"level_flip_rule {rule!r} — {' / '.join(FL.RULES)} पैकी")
        fstate = {}                                                        # K4: {level id: {"brk": bool, "start": bar, "rc": n}}
        pv = self._pv_sorted
        k = 0
        known = []
        fin = next((d for d in sorted(self.res["pivots"]) if self.res["pivots"].get(d)), None)   # the finest degree that has swings
        pv0 = sorted(self.res["pivots"].get(fin, []) if fin is not None else [], key=lambda p: p.confirm_bar)   # method §3: "any swing"
        k0 = 0
        self._known0 = []
        prov = set()                            # σ_1H नसताना जन्मलेले levels (तात्पुरती किमान रुंदी)
        for t in range(self.n):
            # t च्या close पर्यंत माहीत pivots
            while k < len(pv) and pv[k].confirm_bar <= t:
                known.append(pv[k])
                k += 1
            while k0 < len(pv0) and pv0[k0].confirm_bar <= t:
                self._known0.append(pv0[k0])
                k0 += 1
            if prov and np.isfinite(self.sig1h[t]):                        # σ_1H आता माहीत ⇒ त्यांना खरी किमान रुंदी (TA4; टोकापासून आत)
                w = self._w(t)
                for L in self.L:
                    if L.id in prov and L.alive(t) and L.hi - L.lo < w:
                        L.lo, L.hi = (L.hi - w, L.hi) if L.role0 == RES else (L.lo, L.lo + w)
                        L.bands.append((t, L.lo, L.hi))
                    if L.id in prov and L.prov and L.prov[-1][1] is None:
                        L.prov[-1] = (L.prov[-1][0], t)                    # PF-2: provisional width ends (σ_1H known)
                prov.clear()
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
                # मृत्यू: level पलीकडचा structural swing close ने तुटला — support ⇒ खालचा जवळचा D2 L, resistance ⇒ वरचा D2 H. बाजू = चालू
                # भूमिका (level_death_side = "role", Q2 / TL1 Abhi मंजूर): flipped support (= supply) फक्त वरचा D2 H तुटला तरच मेला — खालचा
                # swing तुटणं = break ची पुढची धाव. "role0" = जुना Q2 default (मूळ भूमिकेची बाजू, flip नंतरही), फक्त revert / what-if.
                if (role if death_side == "role" else L.role0) == SUP:
                    sw = [p.price for p in known if p.kind == "L" and p.price < L.lo]
                    dead = bool(sw) and C[t] < max(sw)
                    beyond_sw = max(sw) if sw else None
                else:
                    sw = [p.price for p in known if p.kind == "H" and p.price > L.hi]
                    dead = bool(sw) and C[t] > min(sw)
                    beyond_sw = min(sw) if sw else None
                if inside and not touching.get(L.id):
                    L.events.append((t, "test", ""))
                touching[L.id] = inside
                if rule == "far_swing":
                    self._step_far_swing(L, t, role, known, beyond_wick, beyond_close, excursion,
                                         fstate.setdefault(L.id, {"brk": False, "start": None, "rc": 0, "back": None}), acc)
                    continue
                if dead:
                    L.events.append((t, "dead", f"पलीकडचा swing {beyond_sw:,.2f} close ने तुटला"))
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
                    if hi <= lo:                                           # opened at its extreme ⇒ the base candle's whole range (never one price)
                        lo, hi = ll, hh
                    w = self._w(t)
                    if hi - lo < w:
                        if d > 0:
                            hi = lo + w
                        else:
                            lo = hi - w
                    births.setdefault(t, []).append((SUP if d > 0 else RES, lo, hi, "b", origin.price))
            for role, lo, hi, why, anchor in births.get(t, []):
                L = self._born(t, role, lo, hi, why, anchor)
                if not np.isfinite(self.sig1h[t]) and float(self.s["level_min_width_sigma"]) > 0:   # PF-2 only with the legacy min width
                    prov.add(L.id)
                    if not (L.prov and L.prov[-1][1] is None):
                        L.prov.append((t, None))                           # PF-2: min width from the median 1H range (σ_1H missing)
        npv = sum(1 for L in self.L if L.prov)
        if npv:
            log.info("decision3 levels: %d level(s) born with a %s (σ_1H missing; median 1H range × level_min_width_sigma)", npv, PROV_WIDTH)

    def _step_far_swing(self, L, t, role, known, beyond_wick, beyond_close, excursion, st, acc):
        """KB K4 (Abhi): one bar of one level — sweep / BROKEN / FLIPPED / reclaim / DEAD (module docstring). A never-flipped zone whose
        far-side swing is reached flips; a FLIPPED zone broken again with its far-side swing reached is DEAD — no second flip (Abhi,
        Z-1f). Reached (Z-1s, `flip.reached`): a swing beyond the band from before the break ⇒ price trades past it; none ⇒ the first
        swing formed after the break is CONFIRMED."""
        H, Lo, C = self.A["high"], self.A["low"], self.A["close"]
        exc = excursion.get(L.id, 0)
        up = role == RES                                                   # break direction: resistance ⇒ up, support ⇒ down
        if beyond_close and not st["brk"] and exc == 0:
            st["start"] = t                                                # excursion सुरू (पहिला close पलीकडे)
        prev = L.facts_at(t)
        hist = {"flipped_at": prev.get("flipped_at")} if prev.get("flipped_at") is not None else {}
        if st["brk"] or exc > 0 or beyond_close:                           # पलीकडे (≥ 1 close) ⇒ far swing पार? ⇒ FLIPPED
            fs = FL.far_swing(known, L.lo, L.hi, up, st["start"], C)
            src = FL.swing_source(fs, st["start"])
            if fs is not None and FL.reached(src, fs.price, H[t] if up else Lo[t], up):   # Z-1s: post-break swing ⇒ its confirmation
                how = "past the far-side swing" if src == "before_break" else "the first swing after the break confirmed at"
                if L.count("flip", t - 1) > 0:                             # Z-1f: flip नंतर जुनी भूमिका संपली ⇒ दुसरा flip नाही ⇒ DEAD
                    if not st["brk"]:
                        L.events.append((t, "broken", f"beyond the band and {how} {fs.price:,.2f} on one excursion"))
                    L.events.append((t, "dead", f"flipped zone broken again, {how} {fs.price:,.2f} ({src}) ⇒ dead "
                                                f"(no second flip)"))
                    L.flip_facts.append((t, {**L.facts_at(t), "dead_at": t, "dead_far_swing": self._swing_fact(fs)}))
                    L.dead_bar = t
                    excursion[L.id] = 0
                    return
                new_role = SUP if up else RES
                brk_at = self._last_broken(L, t) if st["brk"] else t
                if not st["brk"]:
                    L.events.append((t, "broken", f"beyond the band and {how} {fs.price:,.2f} on one excursion"))
                L.events.append((t, "flip", f"{how} {fs.price:,.2f} ⇒ {new_role}"))
                if "c" not in L.births:
                    L.births.append("c")
                L.flip_facts.append((t, {"broken_at": brk_at, "break_dir": 1 if up else -1, "exc_start": st["start"],
                                         "far_swing": {**self._swing_fact(fs), "source": src}, "flipped_at": t}))
                st.update(brk=False, start=None, rc=0, back=None)
                excursion[L.id] = 0
                return
        if st["brk"]:
            back = (C[t] > L.hi) if role == SUP else (C[t] < L.lo)         # close परत भूमिकेच्या बाजूला, पट्ट्याबाहेर
            st["rc"] = st["rc"] + 1 if back else 0
            if self._structural_break():                                   # method §3 (mirror): back + a swing built on the role side
                st["back"] = (st.get("back") if st.get("back") is not None else t) if back else None
                done = back and self._swing_beyond(L, st["back"], not up, t) is not None
                why = f"closed back on the {role} side and built a swing there ⇒ break failed, role kept (sweep)"
            else:
                done = st["rc"] >= acc
                why = f"{acc} closes back on the {role} side ⇒ break failed, role kept (sweep)"
            if done:
                L.events.append((t, "reclaim", why))
                L.events.append((t, "sweep", "broken then reclaimed (far-side swing not reached) ⇒ sweep ★"))   # ★ / trap_sweep पुरावा
                last_flip = [x for b, x in L.flip_facts if b <= t and x.get("flipped_at") == b]   # the flip entry itself
                L.flip_facts.append((t, {**(dict(last_flip[-1]) if last_flip else {}), "reclaimed_at": t}))
                st.update(brk=False, start=None, rc=0, back=None)
            excursion[L.id] = 0
            return
        structural = self._structural_break()
        if structural and exc > 0 and st["start"] is not None:            # method §3: a swing formed beyond during the excursion ⇒ BROKEN
            sw = self._swing_beyond(L, st["start"], up, t)
            if sw is not None:
                fs = FL.far_swing(known, L.lo, L.hi, up, st["start"], C)
                L.events.append((t, "broken", f"closed beyond the band and a swing formed beyond it ({sw.price:,.2f}); " +
                                 (f"far-side swing {fs.price:,.2f} not reached" if fs is not None else "no far-side swing known")))
                L.flip_facts.append((t, {**hist, "broken_at": t, "break_dir": 1 if up else -1, "exc_start": st["start"],
                                         "far_swing": self._swing_fact(fs)}))
                st.update(brk=True, rc=0, back=None)
                excursion[L.id] = 0
                return
        if beyond_close:
            exc += 1
            if not structural and exc >= acc:                              # legacy what-if: acceptance ⇒ BROKEN (flip फक्त far swing ने)
                fs = FL.far_swing(known, L.lo, L.hi, up, st["start"], C)
                L.events.append((t, "broken", f"{acc} closes beyond the band; " +
                                 (f"far-side swing {fs.price:,.2f} not reached" if fs is not None else "no far-side swing known")))
                L.flip_facts.append((t, {**hist, "broken_at": t, "break_dir": 1 if up else -1, "exc_start": st["start"],
                                         "far_swing": self._swing_fact(fs)}))
                st.update(brk=True, rc=0)
                exc = 0
        elif exc > 0 or beyond_wick:                                       # पलीकडे गेली, पलीकडे swing बनण्याआधी परत ⇒ sweep ★
            L.events.append((t, "sweep", "wick पलीकडे, close परत" if exc == 0 else f"{exc} close(s) पलीकडे, परत आत"))
            exc = 0
            st["start"] = None
        excursion[L.id] = exc

    def _structural_break(self):
        """Abhi's method §3: broken = a close beyond AND a swing formed beyond (default). "closes" = the legacy `accept_closes` count."""
        rule = self.s.get("break_rule", "structure")
        if rule not in ("structure", "closes"):
            raise ValueError(f"break_rule {rule!r} — structure / closes पैकी")
        return rule == "structure"

    def _swing_beyond(self, L, start, up, t):
        """A swing (the finest structure, confirmed by bar t) formed at or after `start` whose extreme lies beyond the band on the given
        side (up ⇒ above hi, else below lo). None if no such swing yet. Bars ≤ t only."""
        for p in reversed(getattr(self, "_known0", [])):
            if p.confirm_bar > t:
                continue
            if p.bar < start:
                break
            if (p.price > L.hi) if up else (p.price < L.lo):
                return p
        return None

    @staticmethod
    def _last_broken(L, t):
        b = [x for x, k, _ in L.events if k == "broken" and x <= t]
        return b[-1] if b else t

    def _swing_fact(self, p):
        if p is None:
            return None
        return {"price": round(float(p.price), 2), "bar": int(p.bar), "ts": str(self.ts.iloc[int(p.bar)]), "known_bar": int(p.confirm_bar)}

    def flip_view(self, L, t):
        """K4 facts at bar t (truncation-safe): state + broken_at / far_swing / flipped_at (+ ts). BROKEN ⇒ far_swing = the swing price
        must still pass, from pivots known at t; FLIPPED ⇒ the swing that was passed (flipped_at = the last flip)."""
        state = L.state_at(t)
        f = dict(L.facts_at(t))
        flipped = L.count("flip", t) > 0
        if state == FL.BROKEN and f.get("exc_start") is not None:
            lo, hi = L.band_at(t)
            fs = FL.far_swing(self.known_pivots(t), lo, hi, (f.get("break_dir") or 0) > 0, f["exc_start"], self.A["close"])
            f["far_swing"] = None if fs is None else {**self._swing_fact(fs), "source": FL.swing_source(fs, f["exc_start"])}
        ts = lambda b: None if b is None else str(self.ts.iloc[int(b)])  # noqa: E731
        brk = f.get("broken_at") if (state == FL.BROKEN or flipped) else None
        if state == FL.DEAD:
            return {"state": state, "dead_at": f.get("dead_at"), "dead_far_swing": f.get("dead_far_swing")}
        return {"state": state, "broken_at": brk, "broken_ts": ts(brk), "break_dir": f.get("break_dir"), "exc_start": f.get("exc_start"),
                "far_swing": f.get("far_swing"), "flipped_at": f.get("flipped_at") if flipped else None,
                "flipped_ts": ts(f.get("flipped_at")) if flipped else None}

    # ------------------------------------------------------------------------------------------ snapshot
    def score(self, L, t, births, confluence=()):
        """फक्त माहिती (निर्णयात नाही): births = t ला माहीत जन्म-कारणं; Daily (स्वतःचा Daily पट्टा किंवा Daily / Weekly confluence) ⇒ bonus."""
        tests = L.count("test", t)
        sc = 0.0
        if "a:D" in births or L.tf == "D" or confluence:
            sc += float(self.s["score_daily_bonus"])
        if tests == 0:
            sc += float(self.s["score_fresh_bonus"])
        sc -= float(self.s["score_test_penalty"]) * max(0, tests - 1)
        return sc

    def snapshot(self, t):
        """t च्या close ला जिवंत levels (dict), किंमतीपासूनच्या अंतरासह. Abhi Z-1u: each with its own `tf`; a 1H level lists the
        overlapping alive Daily / Weekly bands as `confluence` (+ `confluence_label`, evidence); `trade_location` = 1H, or Daily with no
        overlapping 1H zone (not BROKEN / DEAD), never Weekly (context only) — `trade_band_max_sigma` × σ_1H (Abhi Z-1x,
        default None = no cap — a zone that looks too wide is fixed in its construction; a cap is a what-if only).
        `width` (points) / `width_sigma` are facts for the width report (Abhi: max width — the setting stays None until he decides)."""
        c = float(self.A["close"][t])
        sg = self.sig1h[t]
        alive = [(L, *L.band_at(t)) for L in self.L if L.alive(t)]
        st = {L.id: L.state_at(t) for L, _, _ in alive}
        mx = self.s.get("trade_band_max_sigma")
        out = []
        for L, lo, hi in alive:
            dist = 0.0 if lo <= c <= hi else (lo - c if c < lo else c - hi)
            births = [L.births[0]] + [b for tm, b in L.merged_from if tm <= t and b != L.births[0]]   # (merged_from: legacy only)
            births = [b for b in dict.fromkeys(births) if b != "c"] + (["c"] if L.count("flip", t) else [])   # "c" once flipped by t
            ov = [(o, olo, ohi) for o, olo, ohi in alive if o.id != L.id and not (hi < olo or lo > ohi)]
            conf = [{"tf": o.tf, "id": o.id, "lo": round(olo, 2), "hi": round(ohi, 2)} for o, olo, ohi in ov
                    if L.tf == "1H" and o.tf in ("D", "W")]
            inside_1h = [o.id for o, _, _ in ov if L.tf != "1H" and o.tf == "1H" and st[o.id] not in (FL.BROKEN, FL.DEAD)]
            w = hi - lo
            wsg = round(w / sg, 2) if np.isfinite(sg) and sg > 0 else None
            loc, why, wide = True, None, False
            if L.tf == "W":
                loc, why = False, "Weekly band: context only (Abhi Z-1u)"
            elif inside_1h:
                loc, why = False, f"{TF_WORD[L.tf]} band overlapped by 1H zone(s) {inside_1h}: the 1H band is the location (Abhi Z-1u)"
            elif mx is not None and wsg is not None and wsg > float(mx):   # Abhi Z-1x: no trade, flagged "check" — never re-cut / widened
                loc, why, wide = False, f"too wide {w:,.0f} pts = {wsg}σ_1H > {float(mx):g}σ (trade_band_max_sigma) — check, no trade", True
            out.append({"id": L.id, "tf": L.tf, "role": L.role_at(t), "lo": round(lo, 2), "hi": round(hi, 2), "births": births,
                        "anchor": L.anchor, "tests": L.count("test", t), "sweeps": L.count("sweep", t), "flips": L.count("flip", t),
                        "fresh": L.count("test", t) == 0, "score": self.score(L, t, births, conf), "dist": round(dist, 2),
                        "dist_sigma": round(dist / sg, 2) if np.isfinite(sg) and sg > 0 else None,
                        "above": lo > c, "below": hi < c, "born_bar": L.born_bar, "provisional_width": L.provisional(t),
                        "width_note": PROV_WIDTH if L.provisional(t) else None, "width": round(w, 2), "width_sigma": wsg,
                        "confluence": conf, "confluence_label": confluence_label(conf), "trade_location": loc, "not_location_why": why,
                        "too_wide": wide,
                        "lineage": [dict(x) for x in L.lineage if x["bar"] <= t], **self.flip_view(L, t)})
        return out

    def active(self, t, trend, band=None):
        """Abhi B2 watch-list / method §4: trade-बाजूचे सगळे पुढचे valid zones, जवळचे पहिले (no count cap; RANGE ⇒ each side's nearest);
        BROKEN / DEAD नाहीत ⇒ zone तुटला की पुढचा आधीच यादीत (reset नाही). जुनी व्याख्या: trade-बाजूची जवळची levels. DOWN ⇒ किंमतीवरचे / किंमत ज्यात आहे ते resistance; UP ⇒ खालचे support;
        RANGE ⇒ खालचा support + वरचा resistance (प्रत्येकी जवळचा). Daily पट्टा (Q27) दिला असेल ⇒ फक्त कडांची बाजू: support पट्ट्याच्या
        खालच्या अर्ध्यात, resistance वरच्या अर्ध्यात (मध्य = पट्ट्याचा मध्य; Abhi: bull put खालच्या कडेला, bear call वरच्या)."""
        snap = [x for x in self.snapshot(t) if x.get("state") != FL.BROKEN   # K4 (Abhi): BROKEN (far swing पार नाही) ⇒ trade location नाही
                and x.get("trade_location", True)]                          # Abhi Z-1u: per-timeframe bands; the 1H band is the location
        sup = sorted([x for x in snap if x["role"] == SUP and not x["above"]], key=lambda x: x["dist"])
        res = sorted([x for x in snap if x["role"] == RES and not x["below"]], key=lambda x: x["dist"])
        if trend == "DOWN":                                                # Abhi's method §4: every valid area ahead armed, nearest first
            return res
        if trend == "UP":
            return sup
        if trend == "RANGE":
            if band:
                mid = (float(band[0]) + float(band[1])) / 2.0
                sup = [x for x in sup if (x["lo"] + x["hi"]) / 2.0 <= mid]
                res = [x for x in res if (x["lo"] + x["hi"]) / 2.0 >= mid]
            return sup[:1] + res[:1]                                       # RANGE: the nearest edge area on each side
        return []

    def known_pivots(self, t):
        """t च्या close ला माहीत D2 pivots (confirm क्रमाने)."""
        return self._pv_sorted[:self.known_by[t]] if t < len(self.known_by) else list(self._pv_sorted)


# ------------------------------------------------------------------------------------------------ shared band facts (R1, TA3b / TA4)
# The area owner's horizontal-band finder on the shared K4 check (facts/validity.py; Abhi, design §10). Facts + evidence only; it is
# NOT used by the V22 decision (`Levels` above is unchanged) — charts call `display_bands` / `check_bands` to draw only valid bands.
def find_bands(df, t, s=None, start=None, magnet_df=None):
    """Horizontal S/R bands at decision bar t from pairs of reaction touches (facts.validity.candidate_bands): one per distinct area
    (overlapping candidates merged), valid ones first, then broken ones, then the rest. Bars ≤ t only."""
    from facts import validity as FV
    cands = FV.candidate_bands(df, t, s, start=start, magnet_df=magnet_df)
    valid = FV.dedupe_bands([x for x in cands if x["valid"]])
    broken = FV.dedupe_bands([x for x in cands if x["broken"] and x["reasons"] == ["broken"]])
    rest = [x for x in cands if not x["valid"] and not (x["broken"] and x["reasons"] == ["broken"])]
    out = valid + broken + rest
    B = FV.bars_of(df)
    for x in out:
        x.update(band_flip_facts(B, t, x, s, start))
    return out


def band_flip_facts(df, t, x, s=None, start=None):
    """KB K4 (Abhi) facts on a checked band x (facts.validity.check_band output): flip_state ACTIVE / BROKEN / FLIPPED / DEAD by Abhi's
    rule — the same state machine as the engine (Levels._step_far_swing), driven by the band check's own real breaks (in order, ≤ t):
      • a break AGAINST the band's current role (the first break sets it) ⇒ BROKEN; its segment runs to the next break (or t);
      • while BROKEN, the break's far-side swing reached ⇒ FLIPPED (role changes; a break the other way is now "against"); the far
        swing = the nearest confirmed swing beyond the band on the break side formed before the break (`facts.validity.pivots`, confirmed
        by the bar it is used on; a sweep wick — its candle closed back inside — is not structural, Abhi Z-1y) — reached when price
        trades past it; none (new highs / lows) ⇒ the FIRST swing formed after the break,
        reached when it is CONFIRMED (Abhi Z-1s, as flip.far_swing / flip.reached — the chart label mirrors the engine);
      • while BROKEN, a break back the other way before the far swing is passed = reclaim ⇒ sweep ★, the prior state and role are kept
        (ACTIVE, or FLIPPED with its flipped_at) — never a new break / flip;
      • a FLIPPED band broken against its new role and that break's far swing reached ⇒ DEAD, no second flip (Abhi Z-1f / Z-1k / Z-1s).
    Additive facts only: `valid` / `flipped` / `broken` of the shared check are not changed (open question Z-1b).
    Returns {flip_state, broken_at, far_swing (+ source), flipped_at, dead_at, sweeps} (bars + ts; bars ≤ t only)."""
    from facts import validity as FV
    s = FV.load(s)
    B = FV.bars_of(df)
    brs = sorted((br for br in (x.get("breaks") or []) if int(br["bar"]) <= t), key=lambda br: int(br["bar"]))
    out = {"flip_state": FL.ACTIVE, "broken_at": None, "far_swing": None, "flipped_at": None, "dead_at": None, "sweeps": []}
    if not brs:
        return out
    st = FV.session_start(B, t, int(s["lookback_sessions"])) if start is None else int(start)
    k = int(s["pivot_k"])
    bar = lambda i: {"bar": int(i), "ts": str(B.ts.iloc[int(i)])}  # noqa: E731
    state, against, brk_dir, prior, flip_ctx = FL.ACTIVE, None, None, None, {}
    for n, br in enumerate(brs):
        b, d = int(br["bar"]), br["dir"]
        # scan incl. the next break's bar: the engine checks the far swing before a reclaim on every bar (that bar's pass wins)
        end = min(t, int(brs[n + 1]["bar"])) if n + 1 < len(brs) else t
        if state == FL.BROKEN and d != brk_dir:                             # reclaim before the far swing ⇒ sweep, role / state kept
            state = prior
            out["sweeps"].append(bar(b))
            out.update(flip_state=state, **(flip_ctx if state == FL.FLIPPED else {"broken_at": None, "far_swing": None}))
            continue
        if state == FL.BROKEN or (against is not None and d != against):   # same-side repeat / a break in the role's favour ⇒ nothing
            continue
        against = d if against is None else against
        prior, state, brk_dir = state, FL.BROKEN, d
        up = d == "up"
        out.update(flip_state=FL.BROKEN, broken_at=bar(b), far_swing=None)
        tol = float(s["band_tol_mr"]) * FV.mr_at(B, b, s)                  # a swing within the band's touch tolerance is its own touch
        beyond = [i for i in FV.pivots(B, end, "H" if up else "L", s, start=min(st, b))
                  if ((B.H[i] > x["hi"] + tol) if up else (B.L[i] < x["lo"] - tol))
                  and FL.structural(float(B.C[i]), x["lo"], x["hi"], up)]    # Abhi Z-1y: a sweep wick is not the far swing
        piv, post = [i for i in beyond if i < b], sorted(i for i in beyond if i >= b)
        flip_bar = (out["flipped_at"] or {}).get("bar")
        for i in range(b + (prior == FL.FLIPPED and flip_bar == b), end + 1):   # the flip bar was used for the flip (engine: no DEAD on it)
            known = [p for p in piv if p + k <= i]                          # confirmed by bar i (no look-ahead)
            if known:
                p, src = (min(known, key=lambda j: B.H[j]) if up else max(known, key=lambda j: B.L[j])), "before_break"
            else:                                                           # Z-1a: first confirmed swing after the break
                first = [q for q in post if q + k <= i]
                if not first:
                    continue
                p, src = first[0], "first_confirmed_after_break"
            px = float(B.H[p] if up else B.L[p])
            out["far_swing"] = {"price": round(px, 2), "bar": int(p), "ts": str(B.ts.iloc[p]), "source": src}
            if FL.reached(src, px, B.H[i] if up else B.L[i], up):          # Z-1s: a post-break swing is reached by its confirmation
                if prior == FL.FLIPPED:                                     # Z-1f / Z-1k: flipped once ⇒ passed again = DEAD
                    out.update(flip_state=FL.DEAD, dead_at=bar(i))
                    return out
                state, against = FL.FLIPPED, ("down" if up else "up")       # role changed ⇒ the other way is now "against"
                out.update(flip_state=FL.FLIPPED, flipped_at=bar(i))
                flip_ctx = {"broken_at": out["broken_at"], "far_swing": out["far_swing"]}   # reclaim to FLIPPED restores these
                break
    return out


def display_bands(df, t, s=None, start=None, magnet_df=None, debug=False):
    """TA4: the bands a chart draws at t — ≤ 3 valid above and ≤ 3 below the close at t, plus the most recently broken one."""
    from facts import validity as FV
    B = FV.bars_of(df)
    return FV.select_bands(find_bands(B, t, s, start, magnet_df), float(B.C[t]), s, debug=debug)


def check_bands(df, t, items, s=None, start=None, magnet_df=None):
    """Run the shared band check on areas another engine drew (items with lo / hi): returns [(item, facts)], TA4 latest-broken applied.
    start None ⇒ the finders' lookback window (`lookback_sessions`; pass facts.validity.lookback(tf) for 1H / Daily)."""
    from facts import validity as FV
    B = FV.bars_of(df)
    out = [(x, FV.check_band(B, t, x["lo"], x["hi"], s, start=start, magnet_df=magnet_df)) for x in items]
    FV.latest_broken_only([f for _, f in out])
    return out


def tf_word(x):
    """Chart / text word of a level's timeframe ("1H" / "Daily" / "Weekly"); none ⇒ "1H"."""
    return TF_WORD.get(x.get("tf", "1H"), "1H")


def confluence_label(conf):
    """Abhi Z-1u: "confluence: Daily <low–high>" (and / or Weekly) for a 1H zone overlapped by higher-timeframe bands — evidence."""
    if not conf:
        return None
    return "confluence: " + "; ".join(f"{TF_WORD.get(x['tf'], x['tf'])} {x['lo']:,.0f}–{x['hi']:,.0f}" for x in conf)


def level_tags(x):
    """Chart label tail: provisional width (PF-2) + confluence (Z-1u)."""
    return width_tag(x) + (f", {x['confluence_label']}" if x.get("confluence_label") else "")


def width_tag(x):
    """Abhi PF-2: ", provisional width" for a level whose min band width is still the provisional one (σ_1H missing) — chart labels."""
    return f", {PROV_WIDTH}" if x.get("provisional_width") else ""


def band_label(x):
    """Chart label (English): role, low–high, touch count, flags."""
    role = {"resistance": "supply", "support": "demand"}.get(x.get("role"), "area")
    flipped = x.get("flipped") if "flip_state" not in x else x["flip_state"] == FL.FLIPPED   # K4 (Abhi): far-side swing पार
    flags = [f for f, on in (("established", x.get("established")), ("flipped", flipped), ("broken", x.get("broken")),
                             ("far swing not reached", x.get("flip_state") == FL.BROKEN and not x.get("broken")),
                             ("dead", x.get("flip_state") == FL.DEAD),
                             ("swept", bool(x.get("sweeps")) and x.get("flip_state") in (FL.ACTIVE, FL.FLIPPED))) if on]   # swept = reclaim; dead = Z-1f / Z-1k
    lab = f"{role} {x['lo']:,.0f}-{x['hi']:,.0f}, {x['touch_count']} touches" + (f" ({', '.join(flags)})" if flags else "")
    if not x["valid"] and not x.get("broken"):
        lab += " [invalid: " + ", ".join(x["reasons"]) + "]"
    return lab
