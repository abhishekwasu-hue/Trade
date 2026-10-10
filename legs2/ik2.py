"""legs2/ik2.py — थर 2 v2.1 §5: I (impulse, sticky) आणि K (correction) — D1 (पालक D2) आणि D2 (पालक D3).

Fold (replay = live): 15M bars वर पुढे, प्रत्येक bar ला फक्त तोपर्यंत माहीत असलेलं (confirmed legs `confirm_bar` ≤ t, थर 1 घटना / states
त्या bar पर्यंत). Timeline = (bar, I) बदल; `state(t)` = त्या bar ची K अवस्था.

§5.1 I शोधणं: मागे जाताना पहिला confirmed leg, दिशा = पालक trend (थर 1) आणि (label आवेग / आवेग (कमकुवत) **किंवा** त्या leg मध्ये
  त्याच degree चा plain-close BOS). C NA leg ⇒ `I_weak_basis`. पालक RANGE ⇒ `range_alt` (I = range च्या जवळच्या कडेपासून दूर जाणारा
  शेवटचा leg). पालक unknown ⇒ I नाही.
  I_origin: I_end आधीचा, I_end ≥ असलेला शेवटचा high आणि I_end यांच्यामधला सगळ्यात खालचा low; असा high नसेल ⇒ पालक strong low
  (थर 1 protected) + `origin_bounded`.
§5.2 sticky: I-दिशेचा confirmed leg ज्याचा pivot I_end पलीकडे **आणि** leg मध्ये close I_end पलीकडे ⇒ I_end सरकतो; फक्त wick ⇒
  `sweep_of_I_end`. रद्द: (a) I_origin real break (`elliott/breaks.first_real_break`, settings `I_ORIGIN_BREAK`, retest_fn=None, cache
  नाही, `end = decision_bar`), (b) थर 1 दोन-पायरी reversal (त्याच degree, I-विरुद्ध). रद्द नंतर नवा I फक्त रद्द झालेल्या I_end नंतर
  संपणाऱ्या legs मधून (तोच I पुन्हा नाही).
§5.3 K अवस्था; I_strict_HL; खोली (मुख्य / दुय्यम); वेळ; C_K vs C_I; quiet / heavy; counter-impulse; CHoCH strict (+ displacement);
  flags `cisd`, `last_leg_start_broken`. निर्णय नाही.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from elliott import breaks as BR
from swings2 import structure as SST

from . import features as LF
from . import measure as LM
from . import settings2 as LS

ST_NONE, ST_IMP, ST_KSTART, ST_K = "I नाही", "impulse चालू", "K सुरू झाला असावा", "K चालू"
MODE_TREND, MODE_RANGE = "trend", "range_alt"


def _beyond(x, ref, dirn):
    return x > ref if dirn > 0 else x < ref


class Tracker:
    def __init__(self, lg, st, d, es=None):
        """lg = measure2.build; st = swings2.structure.all_structure(res)[0] (degree ⇒ {states, events})."""
        self.lg, self.st, self.d = lg, st, d
        self.res = lg["res"]
        self.s = lg["settings"]
        self.es = dict(LS.I_ORIGIN_BREAK if es is None else es)
        m15 = self.res["m15"]
        self.F = m15
        self.n = len(m15)
        self.A = lg["A"]
        self.mr = BR.median_range(m15, int(self.es["median_range_n"]))
        ts = pd.to_datetime(m15["timestamp"])
        self.ts = ts
        self.segs = np.array([self.res["segments"].get(pd.Timestamp(x)) for x in ts.dt.normalize()])
        self.legs = sorted(lg["legs"][d], key=lambda L: (L["b"].confirm_bar, L["b"].bar))
        self.lower = [p for p in self.res["pivots"][d - 1]]
        self.piv = self.res["pivots"][d]
        self._brk = {}
        ev = st.get(d, {"events": []})["events"]
        self.bos = [e for e in ev if e["type"] == "BOS"]
        self.revs = {}
        for e in ev:
            if e["type"] == "reversal":
                self.revs.setdefault(e["bar"], []).append(e)
        self.timeline, self.log = [], []
        self._run()

    # ------------------------------------------------------------------------------------------------ पालक
    def parent(self, t):
        """(trend, range पट्टा (top, bottom) किंवा None, protected) — पालक degree चा थर 1 state, bar t ला."""
        pd_ = self.d + 1
        if pd_ in self.st:
            x = self.st[pd_]["states"][t]
            band = None
            if x["trend"] == SST.RNG:
                if x["range"] is not None:
                    band = (x["range"]["top"], x["range"]["bottom"])
                else:
                    band = self._pivot_band(pd_, t)
            return x["trend"], band, x["protected"]
        ps = [p for p in self.res["pivots"][pd_] if p.confirm_bar <= t and not p.warmup and self._seg_p(p) == self.segs[t]]
        tr = SST.trend_of(ps)
        return tr, (self._pivot_band(pd_, t) if tr == SST.RNG else None), None

    def _pivot_band(self, dd, t):
        ps = [p for p in self.res["pivots"][dd] if p.confirm_bar <= t and not p.warmup and self._seg_p(p) == self.segs[t]]
        hs, ls = [p for p in ps if p.kind == "H"][-2:], [p for p in ps if p.kind == "L"][-2:]
        if len(hs) < 2 or len(ls) < 2:
            return None
        return max(p.price for p in hs), min(p.price for p in ls)

    def _seg_p(self, p):
        return self.res["segments"].get(pd.Timestamp(p.ts).normalize())

    # ------------------------------------------------------------------------------------------------ origin + break
    def origin_break(self, o, dirn, start=None, end=None):
        """I_origin चा पहिला real break (confirm index) — [start = I_end bar, end]. end = decision bar (None ⇒ सगळा data; causal म्हणून
        confirm ≤ t असेल तर end = t सारखाच — truncation test). Snapshot मध्ये भविष्यातला index दिसत नाही (I_at)."""
        st = o.bar + 1 if start is None else start
        key = (o.bar, o.price, dirn, st, end)
        if key not in self._brk:
            side = "below" if dirn > 0 else "above"
            self._brk[key] = BR.first_real_break(self.F, st, o.price, side, self.es, mr=self.mr, end=end, retest_fn=None)
        return self._brk[key]

    def origin_of(self, ps, end, dirn, t, protected):
        seg = self._seg_p(end)
        ps = [p for p in ps if self._seg_p(p) == seg and p.bar < end.bar]
        top, bot = ("H", "L") if dirn > 0 else ("L", "H")
        ref = [p for p in ps if p.kind == top and (p.price >= end.price if dirn > 0 else p.price <= end.price)]
        if ref:
            cand = [p for p in ps if p.kind == bot and p.bar > ref[-1].bar]
            if cand:
                return (min(cand, key=lambda p: p.price) if dirn > 0 else max(cand, key=lambda p: p.price)), False
            return None, False
        # origin_bounded: पालक strong low (थर 1 protected); bar = त्या segment मध्ये I_end आधी तो भाव असलेली शेवटची candle
        if protected is None:
            return None, True
        lo, hi = self.A["l"], self.A["h"]
        arr = lo if dirn > 0 else hi
        js = [j for j in range(end.bar - 1, -1, -1) if self.segs[j] == seg and abs(arr[j] - protected) <= 1e-9]
        if not js:
            return None, True
        return SimpleNamespace(price=float(protected), bar=js[0], kind=bot, ts=self.ts.iloc[js[0]], confirm_bar=t, sigma=end.sigma), True

    # ------------------------------------------------------------------------------------------------ शोध
    def _made_bos(self, L):
        return any(L["a"].bar < e["bar"] <= L["b"].bar and e["dir"] == L["dir"] for e in self.bos)

    def _discover(self, t, floor):
        tr, band, prot = self.parent(t)
        legs = [L for L in self.legs if L["b"].confirm_bar <= t and L["b"].bar > floor and L["seg"] == self.segs[t]]
        ps = [p for p in self.piv if p.confirm_bar <= t]
        if tr in (SST.UPT, SST.DNT):
            want = 1 if tr == SST.UPT else -1
            for L in reversed(legs):
                if L["dir"] != want:
                    continue
                if L["label"] not in LM.IMPULSE_LABELS and not self._made_bos(L):
                    continue
                o, bounded = self.origin_of(ps, L["b"], L["dir"], t, prot)
                if o is None:
                    continue
                c = self.origin_break(o, L["dir"], start=L["b"].bar)
                if c is not None and c <= t:
                    continue
                return self._new_I(L, o, bounded, c, t, MODE_TREND, legs)
            return None
        if tr == SST.RNG and band is not None:
            top, bot = band
            for L in reversed(legs):
                near_bot = abs(L["a"].price - bot) <= abs(L["a"].price - top)
                if (near_bot and L["dir"] > 0) or (not near_bot and L["dir"] < 0):
                    o = L["a"]
                    c = self.origin_break(o, L["dir"], start=L["b"].bar)
                    if c is not None and c <= t:
                        continue
                    I = self._new_I(L, o, False, c, t, MODE_RANGE, legs)
                    I["band"] = band
                    return I
        return None

    def _new_I(self, L, o, bounded, c, t, mode, legs):
        I = {"dir": L["dir"], "origin": o, "end": L["b"], "ends": [L["b"]], "leg": L, "origin_bounded": bounded, "cancel": c,
             "since": t, "mode": mode, "weak_basis": bool(L.get("C_na")), "sweeps": []}
        for M in legs:                                                           # आधीच माहीत, I_end पलीकडे गेलेले I-दिशेचे legs
            if M["b"].bar > I["end"].bar and M["dir"] == I["dir"]:
                self._extend(I, M, t, quiet=True)
        return I

    def _extend(self, I, M, t, quiet=False):
        if not _beyond(M["b"].price, I["end"].price, I["dir"]):
            return
        cl = self.A["c"][M["a"].bar + 1:M["b"].bar + 1]
        if np.any(cl > I["end"].price) if I["dir"] > 0 else np.any(cl < I["end"].price):
            I["end"] = M["b"]
            I["ends"].append(M["b"])
            if not quiet:
                self.log.append({"bar": t, "event": "I_end सरकला", "price": M["b"].price})
        else:
            I["sweeps"].append(M["b"])
            if not quiet:
                self.log.append({"bar": t, "event": "sweep_of_I_end", "price": M["b"].price})

    # ------------------------------------------------------------------------------------------------ fold
    def _snap(self, t, I):
        self.timeline.append((t, None if I is None else {**I, "ends": list(I["ends"]), "sweeps": list(I["sweeps"])}))

    def _run(self):
        I, floor = None, -1
        prev_par = None
        self._snap(-1, None)
        li = 0
        for t in range(self.n):
            if t and self.segs[t] != self.segs[t - 1]:
                if I is not None:
                    self.log.append({"bar": t, "event": "segment बदल ⇒ I नाही"})
                I, floor = None, -1
                self._snap(t, I)
            new = []
            while li < len(self.legs) and self.legs[li]["b"].confirm_bar <= t:
                if self.legs[li]["seg"] == self.segs[t]:
                    new.append(self.legs[li])
                li += 1
            changed = False
            if I is not None:
                why = None
                if I["cancel"] is not None and I["cancel"] <= t:
                    why = "I रद्द: I_origin real break"
                elif any(e["dir"] == -I["dir"] for e in self.revs.get(t, [])):
                    why = "I रद्द: थर 1 reversal (I-विरुद्ध)"
                elif I["mode"] == MODE_RANGE and self.parent(t)[0] in (SST.UPT, SST.DNT):
                    why = "range_alt संपला (पालक trend)"
                if why is not None:
                    self.log.append({"bar": t, "event": why, "origin": I["origin"].price})
                    floor = I["end"].bar if why.startswith("I रद्द") else -1
                    I, changed = None, True
            if I is not None:
                for M in new:
                    if M["dir"] == I["dir"] and M["b"].bar > I["end"].bar:
                        before = (I["end"], len(I["sweeps"]))
                        self._extend(I, M, t)
                        changed = changed or before != (I["end"], len(I["sweeps"]))
            par = self.parent(t)[:2]
            par_changed = par != prev_par
            prev_par = par
            if I is None and (new or changed or par_changed):
                I = self._discover(t, floor)
                if I is not None:
                    self.log.append({"bar": t, "event": "I सापडला" + (" (range_alt)" if I["mode"] == MODE_RANGE else ""),
                                     "price": I["end"].price})
                changed = True
            if changed:
                self._snap(t, I)

    def I_at(self, t):
        cur = None
        for b, I in self.timeline:
            if b > t:
                break
            cur = I
        if cur is not None and cur["cancel"] is not None and cur["cancel"] > t:
            cur = {**cur, "cancel": None}                                         # भविष्यातला break index t ला दिसत नाही
        return cur

    # ------------------------------------------------------------------------------------------------ अवस्था
    def quality(self, I):
        A, s, lg = self.A, self.s, self.lg
        o, e, dirn = I["origin"], I["end"], I["dir"]
        f = LF.leg_features(A, lg["rr"], lg["vol"], lg["rv"], lg["bad"], o.bar, e.bar, dirn, abs(e.price - o.price), e.sigma, s)
        spike = bool(f["trend_pct"] is not None and f["trend_pct"] >= float(s["spike_trend_pct"]) and f["max_run"] >= int(s["spike_max_run"])
                     and f["overlap"] is not None and f["overlap"] <= float(s["spike_overlap"])
                     and f["er"] is not None and f["er"] >= float(s["spike_er"]) and f["n_fvg"] >= int(s["spike_fvg"]))
        k = int(s["climax_last_candles"])
        climax = any(LF.climax_candle(A, lg["rr"], i, dirn, s) for i in range(max(e.bar - k + 1, o.bar + 1), e.bar + 1))
        pushes = [L for L in self.legs if L["dir"] == dirn and L["a"].bar >= o.bar and L["b"].bar <= e.bar
                  and L["b"].confirm_bar <= self._now]
        m = int(s["sot_pushes"])
        sot = None
        if len(pushes) >= m:
            g = [L["size"] for L in pushes[-m:]]
            sot = all(g[i + 1] < g[i] for i in range(m - 1))
        return {"kind": "spike" if spike else "channel", "climax": climax, "SOT_trend": sot, "features": f}

    def strict_hl(self, I, t):
        """I_strict_HL: I_end आधीचा (I_end देणारा) त्याच degree चा HL / LH, origin नंतर."""
        kind = "L" if I["dir"] > 0 else "H"
        ps = [p for p in self.piv if p.confirm_bar <= t and p.kind == kind and I["origin"].bar <= p.bar < I["end"].bar]
        return ps[-1] if ps else None

    def state(self, t):
        self._now = t
        I = self.I_at(t)
        out = {"degree": self.d, "bar": t, "ts": str(self.ts.iloc[t]), "I": None, "state": ST_NONE, "flags": {}}
        if I is None:
            tr = self.parent(t)[0]
            out["why"] = "पालक trend unknown" if tr == SST.UNK else "पात्र leg नाही"
            return out
        A, lg, s = self.A, self.lg, self.s
        o, e, dirn = I["origin"], I["end"], I["dir"]
        size = abs(e.price - o.price)
        q = self.quality(I)
        I_legs = [L for L in self.legs if L["a"].bar >= o.bar and L["b"].bar <= e.bar and L["b"].confirm_bar <= t]
        out["I"] = {"dir": dirn, "mode": I["mode"], "origin": {"price": round(o.price, 2), "ts": str(o.ts)},
                    "end": {"price": round(e.price, 2), "ts": str(e.ts)}, "ends": [round(x.price, 2) for x in I["ends"]],
                    "sweeps": [round(x.price, 2) for x in I["sweeps"]], "size": round(size, 2),
                    "size_sigma": round(size / e.sigma, 2) if e.sigma else None, "bars": e.bar - o.bar, "legs": len(I_legs),
                    "origin_bounded": I["origin_bounded"], "I_weak_basis": I["weak_basis"], "found_from": I["leg"]["label"],
                    "quality": q["kind"], "climax": q["climax"], "SOT_trend": q["SOT_trend"],
                    "band": I.get("band")}
        hs = self.strict_hl(I, t)
        out["I"]["I_strict_HL"] = None if hs is None else {"price": round(hs.price, 2), "ts": str(hs.ts)}
        h, lo, cl = A["h"], A["l"], A["c"]
        after = range(e.bar + 1, t + 1)
        ext, eb = e.price, e.bar
        for j in after:                                                        # I_end पलीकडचं tentative टोक
            x = h[j] if dirn > 0 else lo[j]
            if _beyond(x, ext, dirn):
                ext, eb = x, j
        if eb != e.bar:
            opp = "L" if dirn > 0 else "H"
            if not [p for p in self.lower if p.kind == opp and p.bar > eb and p.confirm_bar <= t]:
                out["state"] = ST_IMP
                out["extreme"] = round(float(ext), 2)
                return out
            ref = ext
        else:
            ref = e.price
        K_legs = [L for L in self.legs if L["a"].bar >= e.bar and L["b"].confirm_bar <= t]
        tail = range(eb + 1, t + 1) if eb != e.bar else after
        cx = (min((lo[j] for j in tail), default=ref) if dirn > 0 else max((h[j] for j in tail), default=ref))
        out["state"] = ST_K if (eb == e.bar and K_legs) else ST_KSTART
        out["extreme"] = round(float(ref), 2)
        out["retrace_pct"] = round(100.0 * abs(ref - cx) / abs(ref - o.price), 1) if ref != o.price else None
        K = {"legs": [LM_json(L) for L in K_legs], "extreme": round(float(cx), 2)}
        if hs is not None and ref != hs.price:                                   # ref / eb = I_end किंवा त्यापलीकडचं tentative टोक
            K["depth_main"] = round(abs(ref - cx) / abs(ref - hs.price), 3)
            K["time_main"] = round((t - eb) / max(eb - hs.bar, 1), 2)
        K["depth_secondary"] = round(abs(ref - cx) / abs(ref - o.price), 3) if ref != o.price else None
        K["time_secondary"] = round((t - eb) / max(eb - o.bar, 1), 2)
        cI = [L["C"] for L in I_legs if L.get("C") is not None]
        cK = [L["C"] for L in K_legs if L.get("C") is not None]
        K["C_I"] = round(float(np.mean(cI)), 3) if cI else None
        K["C_K"] = round(float(np.mean(cK)), 3) if cK else None
        rv, bad = lg["rv"], lg["bad"]

        def mrv(i0, i1):
            xs = [rv[j] for j in range(i0 + 1, i1 + 1) if np.isfinite(rv[j]) and not bad[j]]
            return float(np.mean(xs)) if xs else None
        kr, ir = mrv(e.bar, t), mrv(o.bar, e.bar)
        K["rvol_K"], K["rvol_I"] = (None if kr is None else round(kr, 3)), (None if ir is None else round(ir, 3))
        fl = out["flags"]
        fl["pullback_quiet"] = bool(kr is not None and ir is not None and kr <= float(s["quiet_rvol"]) and kr < ir)
        fl["pullback_heavy"] = bool(kr is not None and kr >= float(s["heavy_rvol"]))
        K["counter_impulse"] = [LM_json(L) for L in K_legs if L["dir"] != dirn and L.get("label") in LM.IMPULSE_LABELS]
        # CHoCH strict
        fl["choch_strict"] = None
        if hs is not None:
            for j in after:
                if _beyond(hs.price, cl[j], dirn):                               # close I_strict_HL च्या पलीकडे (I-विरुद्ध)
                    disp = LF.displacement(A, lg["rr"], j, -dirn, s)
                    fl["choch_strict"] = {"bar": j, "ts": str(self.ts.iloc[j]), "disp": disp,
                                          "read": "reversal candidate" if disp else "deep pullback"}
                    break
        fl["choch_disp"] = bool(fl["choch_strict"] and fl["choch_strict"]["disp"])
        fl["cisd"] = cisd(A, e.bar, t, dirn)
        fl["last_leg_start_broken"] = last_leg_start_broken(A, self.lower, e.bar, t, dirn)
        out["K"] = K
        if K["counter_impulse"]:
            out["note"] = "K मध्ये I-विरुद्ध आवेग leg (पुरावा, निर्णय नाही)"
        return out


def LM_json(L):
    from . import measure2 as M2
    return M2.leg_json(L)


def cisd(A, e_bar, t, dirn):
    """ICT CISD: K (I_end नंतर) मधल्या शेवटच्या counter-close run (I-विरुद्ध बंद candles) च्या पहिल्या candle चा open; त्या run नंतर
    I-दिशेची candle त्या open पलीकडे **body** close (open आणि close दोन्ही I-दिशेने) ⇒ ✓ (bar). नवा counter run ⇒ पुन्हा तपास."""
    o, c = A["o"], A["c"]
    ref, hit, run = None, None, False
    for j in range(e_bar + 1, t + 1):
        counter = (c[j] - o[j]) * dirn < 0
        if counter:
            if not run:
                ref, hit = o[j], None
            run = True
            continue
        run = False
        if ref is not None and hit is None and (c[j] - o[j]) * dirn > 0 and _beyond(c[j], ref, dirn):
            hit = j
    return hit


def last_leg_start_broken(A, lower, e_bar, t, dirn):
    """K चा शेवटचा counter-दिशेचा lower-degree leg (confirmed किंवा चालू) ज्या pivot पासून सुरू झाला, त्या भावापलीकडे (I-दिशेने)
    t चा close ⇒ ✓ (त्या pivot चा भाव). (I वर ⇒ K खाली ⇒ leg एका H पासून; close त्या H वर.)"""
    start_kind = "H" if dirn > 0 else "L"
    ps = [p for p in lower if p.confirm_bar <= t and p.bar >= e_bar]
    starts = [p for p in ps if p.kind == start_kind]
    if not starts:
        return None
    p = starts[-1]
    return round(p.price, 2) if _beyond(A["c"][t], p.price, dirn) else None
