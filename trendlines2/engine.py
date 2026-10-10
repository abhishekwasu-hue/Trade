"""trendlines2/engine.py — थर 5 v2.1: trend रेघा (primary / latest / fan), K च्या आधार / टोक रेघा, break / flip, trade-योग्य वर्ग,
quality descriptors, K sloping area (shadow; निर्णय नाही).

- एकच pivot पाया (थर 1 swings2); anchors फक्त confirmed pivots, त्यांच्या `known_at` पासून. सगळी गणना 15M masked series वर, linear किंमत.
- Downtrend (seller; uptrend आरसा): origin = ज्या D2 H पासून थर 1 ची दोन-पायरी reversal DOWN सुरू झाली (`origin_known_at` = reversal);
  correction-टोक (structural top) = D1 H ज्यानंतर, भाव त्याच्या वर जाण्याआधी, आधीच्या D1 low खाली **close** (`top_known_at` = तो close).
  Provisional टोक = शेवटचा न ओलांडलेला D1 H. Provisional (K-टोक) रेघ trade-योग्य फक्त (Abhi उत्तर 10-ब): ≥ 2 आधीचे held touches +
  चालू (3रा) touch candle चा close रेघेच्या आत + त्यानंतर ≤ N (6) candles मध्ये K आधार-रेघ break (थर 7 trendline-break flavour).
  "तीव्र" (उत्तर 11) = gate नाही: तीव्र + ≥ 3 held ⇒ trade-योग्य (`steep` खूण, थर 7 grade −0.5); तीव्र + 2 ⇒ trade-योग्य नाही.
- वैधता: A1–A2 मध्ये close रेघेपलीकडे > 0.3 σ नाही; |slope| ≤ 0.5 σ/bar; A1–A2 ≥ 6 bars; |slope| < 0.02 σ/bar ⇒ सपाट. σ = जन्माचा.
- Touch = wick ने ± τ (0.2 σ), भेटीनुसार; held = भेटीनंतर break न होता θ_D0 दूर. चालू भेट मोजत नाही. ≥ 3 held ⇒ valid, 2 ⇒ उमेदवार.
- Break: `elliott/breaks.first_real_break` detrended frame (OHLC − v(t)) वर, level 0, mr = मूळ frame चा median_range, retest_fn None,
  BreakCache नाही; start = A2 bar + 1; end = decision bar (causal ⇒ पूर्ण data वरचा confirm ≤ t तसाच — truncation test). Pending wrapper
  (_beyond पुन्हा लिहिलेला; breaks._beyond शी equality test). Flip ⇒ उलट side ⇒ दुसरा break ⇒ मेली. DeMark Q1–Q3, Sperandeo 1-2-3.
"""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from elliott import settings as ES
from legs2 import features as LF

from . import settings as TS

LINE_BREAK = dict(ES.DEFAULTS)                       # थर 5 रेघ real break — गोठवलेली प्रत, नाव register मध्ये


def beyond_buf(close, level, buf, side):
    """breaks._beyond ची प्रत (import नाही; equality test)."""
    return close < level - buf if side == "below" else close > level + buf


class Line:
    __slots__ = ("id", "kind", "a1", "a2", "slope", "sigma", "birth", "origin", "shifted", "provisional", "deg", "k_line", "role0",
                 "held", "false", "sweeps", "cand", "cb", "cb2", "retest", "valid0", "why", "flat", "q", "s123", "dead_at", "dc", "bufv")

    def value(self, i):
        return self.a1[1] + self.slope * (i - self.a1[0])


def structural_tops(res, A, d, kind):
    """[(pivot, top_known_at)] — kind H (downtrend tops) / L (uptrend bottoms)."""
    ps = res["pivots"][d]
    out = []
    n = len(A["c"])
    for k, p in enumerate(ps):
        if p.kind != kind or p.warmup:
            continue
        prev = next((q for q in reversed(ps[:k]) if q.kind != kind), None)
        if prev is None:
            continue
        for j in range(p.bar + 1, n):
            if (A["h"][j] > p.price) if kind == "H" else (A["l"][j] < p.price):
                break
            if (A["c"][j] < prev.price) if kind == "H" else (A["c"][j] > prev.price):
                out.append((p, max(j, p.confirm_bar)))
                break
    return out


def origins(res, st, d, kind):
    """[(origin pivot, origin_known_at bar)] — kind H ⇒ reversal DOWN चे origin (त्याआधीच्या CHoCH पूर्वीचा शेवटचा D-degree H)."""
    ev = st.get(d, {"events": []})["events"]
    want = -1 if kind == "H" else 1
    out = []
    for i, e in enumerate(ev):
        if e["type"] != "reversal" or e["dir"] != want:
            continue
        ch = next((x for x in reversed(ev[:i]) if x["type"] == "CHoCH" and x["dir"] == want), None)
        if ch is None:
            continue
        ps = [p for p in res["pivots"][d] if p.kind == kind and p.bar < ch["bar"] and p.confirm_bar <= ch["bar"]]
        if ps:
            out.append((ps[-1], e["bar"], False))
    # reversal शिवाय सुरू झालेला trend (data / segment सुरुवात): त्या दिशेचा trend पहिल्यांदा दिसतो तेव्हा, segment मधलं सगळ्यात टोकाचं
    # D-degree pivot = origin (`origin_fallback` — log मध्ये Abhi साठी प्रश्न)
    states = st.get(d, {"states": []})["states"]
    want_tr = "DOWN" if kind == "H" else "UP"
    segs = [res["segments"].get(pd.Timestamp(x).normalize()) for x in pd.to_datetime(res["m15"]["timestamp"])]
    done = set()
    for t, x in enumerate(states):
        sg = segs[t]
        if x["trend"] != want_tr or sg in done:
            continue
        done.add(sg)
        if any(segs[ok] == sg and ok <= t for _, ok, _ in out):
            continue
        ps = [p for p in res["pivots"][d] if p.kind == kind and p.confirm_bar <= t and segs[p.bar] == sg and not p.warmup]
        if ps:
            o = (max if kind == "H" else min)(ps, key=lambda p: p.price)
            out.append((o, t, True))
    return sorted(out, key=lambda x: x[1])


class Engine:
    def __init__(self, lg, st, s=None, es=None, view=(2, 1)):
        self.lg, self.st, self.res = lg, st, lg["res"]
        self.s = TS.load(s)
        self.es = dict(LINE_BREAK if es is None else es)
        self.m15 = self.res["m15"]
        self.n = len(self.m15)
        self.A = lg["A"]
        self.ts = pd.to_datetime(self.m15["timestamp"]).reset_index(drop=True)
        self.sig = np.array([self.res["sigma"].get(pd.Timestamp(d), np.nan) for d in self.ts.dt.normalize()], float)
        self.k0 = float(self.res["settings"]["k"][0])
        self.mr = BR.median_range(self.m15, int(self.es["median_range_n"]))
        self.od, self.td = view
        self.tops = {k: structural_tops(self.res, self.A, self.td, k) for k in ("H", "L")}
        self.orig = {k: origins(self.res, st, self.od, k) for k in ("H", "L")}
        self.lines = {}
        self.steep = {}                                                              # (line id, t) ⇒ तीव्र trade-योग्य
        self._build()

    # ------------------------------------------------------------------------------------------------ रेघा बांधणं
    def _sigma_at(self, b):
        b = min(max(b, 0), self.n - 1)
        return self.sig[b]

    def make(self, a1, a2, kind, birth, origin=False, shifted=False, provisional=False, k_line=False):
        """a1, a2 = (bar, price). अवैध ⇒ Line सह why."""
        key = (a1[0], kind, a2[0], provisional, k_line)
        if key in self.lines:
            L = self.lines[key]
            L.shifted = L.shifted or shifted                                         # cache मधून आली तरी origin_shifted खूण
            L.origin = L.origin or origin
            return L
        L = Line()
        L.id = f"{'K' if k_line else ''}{kind}{a1[0]}-{a2[0]}{'p' if provisional else ''}"
        L.kind, L.a1, L.a2 = kind, a1, a2
        L.slope = (a2[1] - a1[1]) / (a2[0] - a1[0]) if a2[0] != a1[0] else 0.0
        L.birth = birth
        L.sigma = self._sigma_at(birth)
        L.origin, L.shifted, L.provisional, L.k_line = origin, shifted, provisional, k_line
        L.deg = None
        L.role0 = "resistance" if kind == "H" else "support"
        L.why = self._validity(L)
        L.valid0 = L.why is None
        L.flat = bool(np.isfinite(L.sigma) and abs(L.slope) < float(self.s["flat_slope"]) * L.sigma)
        self._scan(L)
        self.lines[key] = L
        return L

    def _validity(self, L):
        s, A = self.s, self.A
        sg = L.sigma
        if not np.isfinite(sg) or sg <= 0:
            return "σ नाही"
        spacing = int(s["k_spacing"] if L.k_line else s["min_spacing"])
        if L.a2[0] - L.a1[0] < spacing:
            return "spacing"
        if abs(L.slope) > float(s["max_slope"]) * sg:
            return "तीव्र (slope)"
        lim = float(s["close_beyond"]) * sg
        for i in range(L.a1[0] + 1, L.a2[0]):
            v = L.value(i)
            if (A["c"][i] - v > lim) if L.kind == "H" else (v - A["c"][i] > lim):
                return "anchors मध्ये close पलीकडे"
        return None

    def detrended(self, L):
        idx = np.arange(self.n)
        v = L.a1[1] + L.slope * (idx - L.a1[0])
        return pd.DataFrame({"open": self.A["o"] - v, "high": self.A["h"] - v, "low": self.A["l"] - v, "close": self.A["c"] - v})

    def _scan(self, L):
        """पूर्ण series वर (causal) touches / break / flip / मेली; प्रत्येक घटनेचा bar ⇒ t ला फक्त ≤ t वाचायचं."""
        A, s = self.A, self.s
        L.held, L.false, L.sweeps, L.cand, L.cb, L.cb2, L.retest, L.q, L.s123, L.dead_at = [], [], [], None, None, None, None, None, None, None
        L.dc, L.bufv = None, None
        if not L.valid0:
            return
        sg = L.sigma
        tau, th0 = float(s["tau"]) * sg, self.k0 * sg
        F = self.detrended(L)
        side = "above" if L.kind == "H" else "below"
        st = L.a2[0] + 1
        L.cb = BR.first_real_break(F, st, 0.0, side, self.es, mr=self.mr, end=None, retest_fn=None)
        buf = float(self.es["break_buffer_mr"])
        L.dc = F["close"].to_numpy(float) * (1 if side == "above" else -1)            # रेघेपलीकडे (+)
        L.bufv = buf * self.mr
        for i in range(st, self.n if L.cb is None else L.cb + 1):
            if np.isfinite(self.mr[i]) and beyond_buf(F["close"].iat[i], 0.0, buf * self.mr[i], side):
                L.cand = i
                break
        if L.cb is not None:
            L.cb2 = BR.first_real_break(F, L.cb + 1, 0.0, "below" if side == "above" else "above", self.es, mr=self.mr, end=None,
                                        retest_fn=None)
            L.dead_at = L.cb2
            L.q = demark(A, break_candle(L, st), L, 1 if side == "above" else -1)   # audit #41: confirm झालेल्या break चीच candle
        # touches (भेटीनुसार): flip आधी भूमिका role0, नंतर उलट
        sgn = 1 if L.kind == "H" else -1                                            # +1: रेघ वर (resistance)
        in_v, vs, fb, sw = False, None, False, False
        end = self.n if L.cb2 is None else L.cb2 + 1
        for i in range(L.a1[0], end):
            v = L.value(i)
            if L.cb is not None and i == L.cb:
                in_v = False
                sgn = -sgn                                                         # flip
                continue
            near = (A["h"][i] >= v - tau) if sgn > 0 else (A["l"][i] <= v + tau)
            if near and not in_v:
                in_v, vs, fb, sw = True, i, False, False
            if in_v:
                if (A["c"][i] - v) * sgn > 0:
                    fb = True
                elif (A["h"][i] - v if sgn > 0 else v - A["l"][i]) > 0:
                    sw = True
                away = (v - A["l"][i]) if sgn > 0 else (A["h"][i] - v)
                if away >= th0:
                    rec = {"start": vs, "held": i, "false_break": fb, "sweep": sw, "after_flip": bool(L.cb is not None and i > L.cb)}
                    L.held.append(rec)
                    if rec["after_flip"] and L.retest is None:
                        L.retest = rec
                    in_v = False

    # ------------------------------------------------------------------------------------------------ सगळ्या रेघा
    def _build(self):
        for kind in ("H", "L"):
            for o, ok, _ in self.orig[kind]:
                tops = [(p, tk) for p, tk in self.tops[kind] if p.bar > o.bar]
                pts = [((o.bar, o.price), ok, True)] + [((p.bar, p.price), tk, False) for p, tk in tops]
                for i, (a1, k1, is_o) in enumerate(pts):
                    for a2, k2, _ in pts[i + 1:]:
                        if (a2[1] < a1[1]) if kind == "H" else (a2[1] > a1[1]):
                            self.make(a1, a2, kind, max(k1, k2), origin=is_o)

    def all_lines(self):
        return [L for L in self.lines.values() if not L.k_line]

    # ------------------------------------------------------------------------------------------------ t ला
    def held_at(self, L, t):
        return [h for h in L.held if h["held"] <= t]

    def status(self, L, t):
        if L.cb2 is not None and L.cb2 <= t:
            return "मेली"
        if L.cb is not None and L.cb <= t:
            return "flip"
        if L.dc is not None and t > L.a2[0]:                                         # pending = आत्ता पलीकडे, reclaim नाही, real break नाही
            i = t
            while i > L.a2[0] and L.dc[i] > 0:
                i -= 1
            run = range(i + 1, t + 1)
            if any(np.isfinite(L.bufv[j]) and L.dc[j] > L.bufv[j] for j in run):
                return "pending"
        return "अखंड"

    def segment(self, t, kind):
        """t ला चालू trend segment चा origin (त्या दिशेचा शेवटचा reversal ≤ t) आणि त्या segment चे known tops."""
        os_ = [(o, ok) for o, ok, _ in self.orig[kind] if ok <= t]
        if not os_:
            return None, []
        o, ok = os_[-1]
        other = [ok2 for _, ok2, _ in self.orig["L" if kind == "H" else "H"] if ok < ok2 <= t]
        if other:
            return None, []                                                        # उलट reversal नंतर हा trend संपला
        tops = [(p, tk) for p, tk in self.tops[kind] if p.bar > o.bar and tk <= t]
        return (o, ok), tops

    def named(self, t, kind):
        """primary (Sperandeo), latest (DeMark), fan (त्याच A1 वरून)."""
        seg, tops = self.segment(t, kind)
        if seg is None:
            return {}
        (o, ok) = seg
        A = self.A
        rng = slice(o.bar, t + 1)
        ll = (o.bar + int(np.argmin(A["l"][rng]))) if kind == "H" else (o.bar + int(np.argmax(A["h"][rng])))
        out = {}
        cands = [(p, tk) for p, tk in tops if p.bar < ll]
        a1s = [((o.bar, o.price), ok, True)] + [((p.bar, p.price), tk, False) for p, tk in tops]
        prim = None
        for j, (a1, k1, is_o) in enumerate(a1s):
            pool = [(p, tk) for p, tk in cands if p.bar > a1[0] and ((p.price < a1[1]) if kind == "H" else (p.price > a1[1]))]
            for p, tk in reversed(pool):
                L = self.make(a1, (p.bar, p.price), kind, max(k1, tk), origin=is_o, shifted=not is_o)
                if L.valid0:
                    prim = L
                    break
            if prim is not None:
                break
        if prim is not None:
            out["primary"] = prim
        tk_sorted = sorted(tops, key=lambda x: x[0].bar)
        prov = self.provisional(t, kind, o)
        pts = [((p.bar, p.price), tk, False) for p, tk in tk_sorted] + ([((prov.bar, prov.price), t, True)] if prov is not None else [])
        if len(pts) >= 2:
            (a1, k1, _), (a2, k2, pv) = pts[-2], pts[-1]
            if (a2[1] < a1[1]) if kind == "H" else (a2[1] > a1[1]):
                out["latest"] = self.make(a1, a2, kind, max(k1, k2), provisional=pv)
        fans = []
        if prim is not None:
            for p, tk in tk_sorted:
                L = self.make(prim.a1, (p.bar, p.price), kind, max(prim.birth if prim.origin else tk, tk), origin=prim.origin)
                if L is not prim and L.valid0 and p.bar > prim.a1[0] and ((p.price < prim.a1[1]) if kind == "H" else (p.price > prim.a1[1])):
                    fans.append(L)
        out["fans"] = fans
        out["origin"] = o
        out["origin_fallback"] = any(fb for oo, _, fb in self.orig[kind] if oo is o)
        return out

    def provisional(self, t, kind, o):
        ps = [p for p in self.res["pivots"][self.td] if p.kind == kind and p.confirm_bar <= t and p.bar > o.bar]
        if not ps:
            return None
        p = ps[-1]
        seg = self.A["h"][p.bar + 1:t + 1] if kind == "H" else self.A["l"][p.bar + 1:t + 1]
        if len(seg) and ((seg.max() > p.price) if kind == "H" else (seg.min() < p.price)):
            return None
        return p

    def descriptors(self, L, t, i_slope=None):
        hs = self.held_at(L, t)
        sp = [b["held"] - a["held"] for a, b in zip(hs, hs[1:])]
        ib = int(self.s["inbound_bars"])
        a0 = max(L.a1[0] - ib, 0)
        inb = (self.A["c"][L.a1[0]] - self.A["c"][a0]) / max(L.a1[0] - a0, 1) / L.sigma if L.sigma else None
        cls = None
        if i_slope:
            r = abs(L.slope) / abs(i_slope)
            lo, hi = self.s["slope_cls"]
            cls = "सपाट" if r < lo else ("मध्यम" if r <= hi else "तीव्र")
        stale = False
        if len(sp) >= 1 and hs:
            stale = t - hs[-1]["held"] > float(self.s["stale_x"]) * float(np.median(sp))
        return {"held": len(hs), "spacing": round(float(np.mean(sp)), 1) if sp else None, "life": t - L.a1[0],
                "inbound": None if inb is None else round(float(inb), 4), "slope_cls": cls, "stale": stale,
                "false_break": sum(h["false_break"] for h in hs), "sweep": sum(h["sweep"] for h in hs),
                "slope_sigma": round(L.slope / L.sigma, 4) if L.sigma else None}

    def line_json(self, L, t, name=None, cls=None, i_slope=None):
        return {"id": L.id, "name": name, "kind": L.kind, "class": cls, "a1": {"ts": str(self.ts.iloc[L.a1[0]]), "price": round(L.a1[1], 2)},
                "a2": {"ts": str(self.ts.iloc[L.a2[0]]), "price": round(L.a2[1], 2)}, "value_now": round(L.value(t), 2),
                "status": self.status(L, t), "flat": L.flat, "steep": bool(self.steep.get((L.id, t))), "origin": L.origin,
                "origin_shifted": L.shifted, "provisional": L.provisional,
                "valid": L.valid0, "why": L.why, "touches": self.descriptors(L, t, i_slope),
                "break": None if L.cb is None or L.cb > t else {"ts": str(self.ts.iloc[L.cb]), "Q": L.q},
                "retest": None if L.retest is None or L.retest["held"] > t else str(self.ts.iloc[L.retest["held"]])}


def break_candle(L, start):
    """confirm (cb) पासून मागे: रेघेपलीकडे (buffer सह) सलग closes चा run — त्याची पहिली candle = break candle. आधीचा reclaim झालेला
    (false) break वेगळा run ⇒ तो Q साठी वापरत नाही (audit #41)."""
    i = L.cb
    while i - 1 >= start and np.isfinite(L.bufv[i - 1]) and L.dc[i - 1] > L.bufv[i - 1]:
        i -= 1
    return i


def demark(A, i, L, dirn):
    """DeMark: Q1 आधीची candle break च्या उलट बंद; Q2 break candle चा open रेघेपलीकडे; Q3 आधीचा close ± (range भाग) रेघेपलीकडे."""
    if i is None or i < 1:
        return None
    p = i - 1
    v = L.value(i)
    q1 = (A["c"][p] - A["o"][p]) * dirn < 0
    q2 = (A["o"][i] - v) * dirn > 0
    proj = A["c"][p] + (A["c"][p] - A["l"][p]) if dirn > 0 else A["c"][p] - (A["h"][p] - A["c"][p])
    q3 = (proj - v) * dirn > 0
    return {"Q1": bool(q1), "Q2": bool(q2), "Q3": bool(q3)}


# ---------------------------------------------------------------------------------------------------- trade-योग्य + K
def trend_slope_of(E, t, o, kind):
    """§2.7.5: trend slope = §2.2 चा trend origin ⇒ सध्याचं टोक (downtrend ⇒ सगळ्यात खालचा low)."""
    A = E.A
    seg = slice(o.bar, t + 1)
    j = o.bar + (int(np.argmin(A["l"][seg])) if kind == "H" else int(np.argmax(A["h"][seg])))
    v = A["l"][j] if kind == "H" else A["h"][j]
    return (v - o.price) / max(j - o.bar, 1)


def line_class(flat, side_ok, before_k, held, near, steep, prov, valid_touches=3):
    """वर्ग: सपाट / trade-योग्य / तीव्र / लागू नाही. तीव्र = gate नाही — ≥ valid_touches held ⇒ trade-योग्य (उत्तर 11); provisional ⇒
    फक्त prov (उत्तर 10-ब)."""
    if flat:
        return "सपाट"
    need = int(valid_touches) if steep else 2
    if side_ok and near and held >= need and (before_k or prov):                 # तीव्र ⇒ provisional ला सुद्धा ≥ 3 held
        return "trade-योग्य"
    return "तीव्र" if steep else "लागू नाही"


def prov_ok(E, L, t, k_break):
    """Provisional रेघ (उत्तर 10-ब): A2 नंतरचा touch candle j (wick रेघेच्या ± τ, close रेघेच्या आत), j पर्यंत ≥ 2 held, आणि K आधार-रेघ
    break kb ∈ [j, j + N], kb ≤ t. रिटर्न touch bar किंवा None."""
    if k_break is None or k_break["bar"] > t or not np.isfinite(L.sigma):
        return None
    A = E.A
    kb = k_break["bar"]
    tau = float(E.s["tau"]) * L.sigma
    sgn = 1 if L.kind == "H" else -1
    for j in range(kb, max(L.a2[0], kb - int(E.s["prov_break_n"]) - 1), -1):   # j ∈ [kb − N, kb]
        v = L.value(j)
        touch = (A["h"][j] >= v - tau) if sgn > 0 else (A["l"][j] <= v + tau)
        inside = (A["c"][j] - v) * sgn <= 0
        if touch and inside and len([h for h in L.held if h["held"] < j]) >= 2:
            return j
    return None


def tradeable(E, t, kind, k_start, k_ext, i_dir, trend_slope=None, k_break=None):
    """§2.7: [(Line, नाव, वर्ग)] — trade-योग्य / उमेदवार / लागू नाही / तुटलेली fan / तीव्र. §5: उलट प्रकारची flip केलेली रेघ (support ⇒
    resistance) सुद्धा trade-बाजूची उमेदवार."""
    nm = E.named(t, kind)
    other = "L" if kind == "H" else "H"
    nm2 = E.named(t, other)
    if not nm and not nm2:
        return []
    out = []
    items = []
    if nm:
        trend_slope = trend_slope_of(E, t, nm["origin"], kind)
        items = ([("primary", nm["primary"])] if "primary" in nm else []) + ([("latest", nm["latest"])] if "latest" in nm else []) + \
            [(f"fan {k + 1}", L) for k, L in enumerate(nm["fans"])]
    if nm2:
        cand2 = ([nm2["primary"]] if "primary" in nm2 else []) + ([nm2["latest"]] if "latest" in nm2 else []) + nm2["fans"]
        items += [(f"flip {k + 1}", L) for k, L in enumerate(cand2) if E.status(L, t) == "flip"]
    seen, picked_fans = set(), {"valid": 0, "cand": 0}
    for name, L in items:
        if L.id in seen:
            continue
        seen.add(L.id)
        st = E.status(L, t)
        held = len(E.held_at(L, t))
        flipped_in = name.startswith("flip")
        if (st in ("flip", "मेली") and not flipped_in) or st == "मेली":
            out.append((L, name, "तुटलेली"))
            continue
        cls = None
        side_ok = ((kind == "H" and i_dir is not None and i_dir < 0) or (kind == "L" and i_dir is not None and i_dir > 0)) and \
            (flipped_in or L.kind == kind)
        before_k = L.birth < k_start and L.a2[0] < k_start and not L.provisional
        near = k_ext is not None and np.isfinite(L.sigma) and abs(k_ext - L.value(t)) <= float(E.s["k_near"]) * L.sigma
        steep = trend_slope is not None and not flipped_in and abs(L.slope) > abs(trend_slope)
        prov = L.provisional and side_ok and near and prov_ok(E, L, t, k_break) is not None
        cls = line_class(L.flat, side_ok, before_k, held, near, steep, prov, int(E.s["valid_touches"]))
        if cls == "trade-योग्य" and steep:
            E.steep[(L.id, t)] = True                                              # नोंद + grade (थर 7 w_steep), gate नाही
        if name.startswith("fan"):
            key = "valid" if held >= int(E.s["valid_touches"]) else "cand"
            cap = int(E.s["fan_valid"] if key == "valid" else E.s["fan_cand"])
            if picked_fans[key] >= cap:
                continue
            picked_fans[key] += 1
        out.append((L, name, cls))
    return dedupe(E, out, t)


def dedupe(E, items, t):
    """greedy (key क्रम): आधी निवडलेल्या रेघेशी ≥ 2 held touches समान आणि decision bar ला किंमत ± τ ⇒ काढा. Named रेघा (primary /
    latest) नेहमी ठेवल्या (cap बाहेर)."""
    def key(x):
        L = x[0]
        hs = E.held_at(L, t)
        return (-len(hs), -(L.deg or 0), -(t - L.a1[0]), -(hs[-1]["held"] if hs else -1), abs(L.slope), -L.a2[0], -L.a1[0])
    keep = []
    for x in sorted(items, key=key):
        L = x[0]
        hs = {h["start"] for h in E.held_at(L, t)}
        dup = any(len(hs & {h["start"] for h in E.held_at(y[0], t)}) >= 2 and np.isfinite(L.sigma)
                  and abs(L.value(t) - y[0].value(t)) <= float(E.s["tau"]) * L.sigma for y in keep)
        if dup and not x[1] in ("primary", "latest"):
            continue
        keep.append(x)
    return keep


def k_lines(E, rec, I, t):
    """§4: K च्या आधार / टोक रेघा. preferred pattern ची रेघ असेल तर ती; नाहीतर K मधले शेवटचे दोन same-type confirmed pivots (I_end सह)."""
    if I is None:
        return None
    kd = -I["dir"]
    base_kind = "L" if kd > 0 else "H"                                           # K वर ⇒ lows ची आधार रेघ
    h = rec.get("pref") if rec else None
    pts = None
    tip = None
    if h is not None and rec.get("agg") != "none":
        P, b = h["P"], h["bounds"]
        conf = [k for k in range(len(b)) if not P[b[k]]["tent"]]
        sel = {"wedge": ((2, 4), (1, 3)), "triangle": ((2, 4), (1, 3)), "zigzag": ((0, 2), None), "flat": ((0, 2), None)}.get(h["family"])
        if sel is not None and all(k in conf for k in sel[0]) and max(sel[0]) < len(b):
            pts = [(P[b[k]]["bar"], P[b[k]]["price"]) for k in sel[0]]
            if sel[1] is not None and all(k in conf and k < len(b) for k in sel[1]):
                tip = [(P[b[k]]["bar"], P[b[k]]["price"]) for k in sel[1]]
    if pts is None:
        ps = [p for p in E.res["pivots"][0] if p.kind == base_kind and p.confirm_bar <= t and p.bar >= I["end"].bar]
        ps = [(I["end"].bar, I["end"].price)] * (I["end"].kind == base_kind) + [(p.bar, p.price) for p in ps if p.bar > I["end"].bar]
        if len(ps) < 2:
            return None
        pts = ps[-2:]
    cb = {p.bar: p.confirm_bar for p in E.res["pivots"][0]}
    cb[I["end"].bar] = I["end"].confirm_bar

    def born(pp):
        return max(cb.get(b, t) for b, _ in pp)                                    # anchors चा known_at (t वर अवलंबून नाही)
    base = E.make(pts[0], pts[1], base_kind, born(pts), k_line=True)
    tipL = E.make(tip[0], tip[1], "H" if base_kind == "L" else "L", born(tip), k_line=True) if tip else None
    return {"base": base, "tip": tipL}


def k_base_break(E, base, t, k_from):
    """आधार-रेघेचा break घटना: पहिला close पलीकडे (मागचा close अलीकडे), एकदाच. रिटर्न dict किंवा None."""
    if base is None or not base.valid0:
        return None
    A = E.A
    dirn = -1 if base.kind == "L" else 1
    for i in range(max(base.a2[0] + 1, k_from + 1), t + 1):
        v, vp = base.value(i), base.value(i - 1)
        if (A["c"][i] - v) * dirn > 0 and (A["c"][i - 1] - vp) * dirn <= 0:
            sg = base.sigma
            rng = A["h"][i] - A["l"][i]
            return {"bar": i, "ts": str(E.ts.iloc[i]), "beyond_sigma": round(abs(A["c"][i] - v) / sg, 2) if sg else None,
                    "body": None if LF.body_pct(A, i) is None else round(LF.body_pct(A, i), 2),
                    "range_sigma": round(rng / sg, 2) if sg else None, "dir": dirn, "Q": demark(A, i, base, dirn),
                    "pending": E.status(base, t) == "pending", "confirm": base.cb is not None and base.cb <= t}
    return None


def tip_touch(E, tip, t, k_from):
    if tip is None or not tip.valid0:
        return None
    A = E.A
    tau = float(E.s["tau"]) * tip.sigma
    for i in range(max(tip.a2[0] + 1, k_from + 1), t + 1):
        v = tip.value(i)
        if (A["h"][i] >= v - tau) if tip.kind == "H" else (A["l"][i] <= v + tau):
            thr = (A["h"][i] > v and A["c"][i] <= v) if tip.kind == "H" else (A["l"][i] < v and A["c"][i] >= v)
            return {"bar": i, "throw_over": bool(thr)}
    return None


def k_sloping_area(E, lines, t, k_start, zones=None):
    """§5: K च्या शेवटच्या leg ची candle trade-योग्य रेघेच्या ± τ मध्ये ⇒ हो; wick पलीकडे + close आत ⇒ हो (sweep); close पलीकडे पण
    accept (detrended) / real break नाही ⇒ हो (pending); accept ⇒ नाही. ∩ = त्याच candle ला रेघ त्या candle आधी जन्मलेल्या trade-बाजूच्या
    zone च्या पट्ट्यात."""
    A = E.A
    best = None
    for L, name, cls in lines:
        if cls != "trade-योग्य":
            continue
        sgn = 1 if L.kind == "H" else -1
        tau = float(E.s["tau"]) * L.sigma
        acc_n, ans, hit = 0, None, None
        for i in range(k_start, t + 1):
            v = L.value(i)
            bey = (A["c"][i] - v) * sgn
            acc_n = acc_n + 1 if bey >= float(E.s["accept_sigma"]) * L.sigma else 0
            if acc_n >= int(E.s["accept_closes"]):
                ans, hit = "नाही", i
                break
            wick = ((A["h"][i] - v) if sgn > 0 else (v - A["l"][i]))
            if bey > 0 and (L.cb is None or L.cb > t):
                ans, hit = "हो (pending)", i
            elif wick > 0 and bey <= 0:
                ans, hit = "हो (sweep)", i
            elif wick >= -tau and ans is None:
                ans, hit = "हो", i
        if ans is None:
            continue
        inter = None
        if zones and hit is not None:
            v = L.value(hit)
            z = [zz for zz in zones if zz["bottom"] - 1e-9 <= v <= zz["top"] + 1e-9]
            inter = z[0]["id"] if z else None
        r = {"ans": ans, "line": L.id, "name": name, "touches": len(E.held_at(L, t)) + 1, "bar": hit, "intersection": inter,
             "value": round(L.value(t), 2), "steep": bool(E.steep.get((L.id, t))), "provisional": bool(L.provisional)}
        rank = {"हो (sweep)": 3, "हो": 2, "हो (pending)": 1, "नाही": 0}[ans]
        if best is None or (rank, inter is not None) > best[0]:
            best = ((rank, inter is not None), r)
    return best[1] if best else {"ans": "नाही"}
