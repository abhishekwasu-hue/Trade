"""legs2/ik.py — थर 2 §3: trade degree (D1, पालक D2) आणि D2 (पालक D3) वर I (impulse) आणि K (correction).

Fold (replay = live): asof पर्यंत, confirmed legs च्या known_at क्रमाने. I एकदा सापडला की फक्त दोन कारणांनी बदलतो:
  1. I च्या दिशेने कोणताही confirmed leg I_end च्या पलीकडे (label कोणतंही) ⇒ I_end तिथे सरकतो, origin तोच;
  2. I_origin चा real break (`elliott/breaks.first_real_break`, नकाशा S4 ची व्याख्या; नवी नाही) ⇒ "I रद्द: हा pullback नाही" ⇒ पुन्हा शोध.
Correction च्या आतले legs (label "आवेग" असला तरी) I ची जागा घेत नाहीत. विरोध / बरोबरी / अज्ञात legs I होत नाहीत.
फक्त माहिती: trade / no-trade निर्णय नाही.
"""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from elliott import settings as ES
from pivots import engine as PE

from . import measure as LM

ST_IMP, ST_KSTART, ST_K = "impulse चालू", "K सुरू झाला असावा", "K चालू"


def _beyond(x, ref, dirn):
    return x > ref if dirn > 0 else x < ref


def _seg(res, p):
    return res["segments"].get(pd.Timestamp(p.ts).normalize())


def origin_of(ps, end, dirn, res):
    """§3.1.2 (वरच्या I साठी; खालच्यासाठी आरसा): I_end आधीचा, I_end पेक्षा उंच किंवा बरोबर असलेला शेवटचा high, आणि I_end यांच्यामधला
    सगळ्यात खालचा low. असा high नसेल ⇒ उपलब्ध data मधला सगळ्यात खालचा low + `origin_open`."""
    seg = _seg(res, end)
    ps = [p for p in ps if _seg(res, p) == seg and p.bar < end.bar]
    top, bot = ("H", "L") if dirn > 0 else ("L", "H")
    ref = [p for p in ps if p.kind == top and (p.price >= end.price if dirn > 0 else p.price <= end.price)]
    start = ref[-1].bar if ref else -1
    cand = [p for p in ps if p.kind == bot and p.bar > start]
    if not cand:
        return None, not ref
    o = min(cand, key=lambda p: p.price) if dirn > 0 else max(cand, key=lambda p: p.price)
    return o, not ref


class Tracker:
    def __init__(self, lg, d, asof, es=None):
        self.lg, self.d, self.res = lg, d, lg["res"]
        m15 = self.res["m15"]
        self.asof = pd.Timestamp(asof)
        self.end = int((pd.to_datetime(m15["bar_end"]) <= self.asof).sum()) - 1
        self.F = m15.iloc[:self.end + 1]
        self.es = {**ES.DEFAULTS, **(es or {})}
        self.mr = BR.median_range(self.F, int(self.es["median_range_n"]))
        seg = self.res["segments"].get(pd.Timestamp(m15["timestamp"].iloc[self.end]).normalize()) if self.end >= 0 else None
        self.legs = [L for L in LM.known(lg, d, asof) if L["seg"] == seg]              # holdout ओलांडत नाही (त्याच segment मधले)
        self.ps = [p for p in PE.known(self.res, d, asof) if _seg(self.res, p) == seg]
        self.log = []

    def _break_at(self, origin, dirn):
        """origin चा पहिला real break (confirm bar; फक्त asof पर्यंतच्या bars वर) ⇒ index किंवा None."""
        side = "below" if dirn > 0 else "above"
        return BR.first_real_break(self.F, origin.bar + 1, origin.price, side, self.es, mr=self.mr)

    def _discover(self, now, i):
        """§3.1: मागे जाताना पहिला confirmed 'आवेग' / 'आवेग (कमकुवत)' leg; origin आधीच तुटलेला असेल तर तो पुढे नाही."""
        known = [L for L in self.legs if L["b"].confirm_bar <= now]          # त्याच bar ला confirm झालेला leg सुद्धा
        ps = [p for p in self.ps if p.confirm_bar <= now]
        for L in reversed(known):
            if L["label"] not in LM.IMPULSE_LABELS:
                continue
            o, open_ = origin_of(ps, L["b"], L["dir"], self.res)
            if o is None:
                continue
            c = self._break_at(o, L["dir"])
            if c is not None and c <= now:
                continue
            alt = [M for M in known if M["b"].bar > L["b"].bar and M["label"] in LM.CONFLICT_LABELS]
            I = {"dir": L["dir"], "origin": o, "end": L["b"], "ends": [L["b"]], "leg": L, "origin_open": open_, "cancel": c,
                 "since": now, "alt": alt}
            for M in known:                                                    # आधीच पलीकडे गेलेले I-दिशेचे legs ⇒ I_end सरकतो
                if M["b"].bar > I["end"].bar and M["dir"] == I["dir"] and _beyond(M["b"].price, I["end"].price, I["dir"]):
                    I["end"] = M["b"]
                    I["ends"].append(M["b"])
            return I
        return None

    def run(self):
        I, i, n = None, 0, len(self.legs)
        self.timeline = [(-1, None)]                                       # (bar, त्या bar पासूनचा I) — थर 3 साठी (replay = live)

        def snap(bar, cur):
            self.timeline.append((bar, None if cur is None else {**cur, "ends": list(cur["ends"])}))
        while True:
            nxt = self.legs[i]["b"].confirm_bar if i < n else None
            if I is not None and I["cancel"] is not None and I["cancel"] <= self.end and (nxt is None or I["cancel"] <= nxt):
                now = I["cancel"]
                self.log.append({"bar": now, "event": "I रद्द: हा pullback नाही", "origin": I["origin"].price})
                I = self._discover(now, i)
                if I is not None:
                    self.log.append({"bar": now, "event": "नवा I", "end": I["end"].price})
                snap(now, I)
                continue
            if nxt is None:
                break
            L = self.legs[i]
            i += 1
            if I is None:
                I = self._discover(nxt, i)
                if I is not None:
                    self.log.append({"bar": nxt, "event": "I सापडला", "end": I["end"].price})
                    snap(nxt, I)
            elif L["dir"] == I["dir"] and _beyond(L["b"].price, I["end"].price, I["dir"]):
                I["end"] = L["b"]
                I["ends"].append(L["b"])
                note = "I_end सरकला" + (" (expanded flat चा B हा पर्याय थर 3 ठरवेल)" if L["label"] not in LM.IMPULSE_LABELS else "")
                self.log.append({"bar": nxt, "event": note, "end": L["b"].price})
                snap(nxt, I)
        self.I = I
        return I

    def I_at(self, bar):
        """timeline वरून bar ला लागू असलेला I (त्या bar पर्यंतच्या घटनांनंतर)."""
        cur = None
        for b, I in self.timeline:
            if b > bar:
                break
            cur = I
        return cur

    def state(self):
        """§3.3 asof ची अवस्था."""
        I = self.run()
        out = {"degree": self.d, "I": None, "state": None, "alt_I": [], "log": self._log_json()}
        if I is None:
            out["state"] = "I नाही"                                                  # शोधात भेटलेले सगळे विरोध-legs (शेवटचे 3)
            out["alt_I"] = [LM.leg_json(x) for x in self.legs if x["label"] in LM.CONFLICT_LABELS][-3:]
            return out
        out["alt_I"] = [LM.leg_json(x) for x in I.get("alt", [])]                  # I शोधताना भेटलेले विरोध-legs (पर्यायी I)
        m = self.F
        h, lo, cl = m["high"].to_numpy(float), m["low"].to_numpy(float), m["close"].to_numpy(float)
        o, e, dirn = I["origin"], I["end"], I["dir"]
        size = abs(e.price - o.price)
        Ib = max(e.bar - o.bar, 1)
        after = slice(e.bar + 1, self.end + 1)
        ext, eb = e.price, e.bar
        if self.end > e.bar:
            seg = h[after] if dirn > 0 else lo[after]
            k = int(np.argmax(seg)) if dirn > 0 else int(np.argmin(seg))
            if _beyond(float(seg[k]), e.price, dirn):
                ext, eb = float(seg[k]), e.bar + 1 + k
        sig = e.sigma or np.nan
        I_legs = [L for L in self.legs if L["a"].bar >= o.bar and L["b"].bar <= e.bar]
        out["I"] = {"dir": dirn, "origin": {"price": round(o.price, 2), "ts": str(o.ts)}, "end": {"price": round(e.price, 2), "ts": str(e.ts)},
                    "ends": [round(x.price, 2) for x in I["ends"]], "size": round(size, 2), "size_sigma": round(size / sig, 2) if sig else None,
                    "bars": Ib, "legs": len(I_legs), "origin_open": I["origin_open"], "found_from": I["leg"]["label"]}
        if _beyond(ext, e.price, dirn):
            # I_end च्या पलीकडे tentative टोक (D(d) ने अजून confirm केलेलं नाही): एक degree खालचा उलट pivot नाही ⇒ impulse चालू
            low = PE.known(self.res, self.d - 1, self.asof)
            opp = "L" if dirn > 0 else "H"
            if not [p for p in low if p.kind == opp and p.bar > eb]:
                out["state"] = ST_IMP
            else:
                tail = slice(eb + 1, self.end + 1)
                cx = float(lo[tail].min()) if dirn > 0 else float(h[tail].max())
                out["state"] = ST_KSTART
                rng = abs(ext - o.price)
                out["retrace_pct"] = round(100.0 * abs(ext - cx) / rng, 1) if rng else None
                out["retrace_now_pct"] = round(100.0 * abs(ext - cl[self.end]) / rng, 1) if rng else None
            out["extreme"] = round(ext, 2)
            return out
        # I_end D(d) ने confirm केलेला ⇒ K नक्की सुरू झाला (K चे confirmed legs अजून नसले तरी)
        K_legs = [L for L in self.legs if L["a"].bar >= e.bar]
        cx = float(lo[after].min()) if dirn > 0 else float(h[after].max()) if self.end > e.bar else e.price
        cI = [L["C"] for L in I_legs if L.get("C") is not None]
        cK = [L["C"] for L in K_legs if L.get("C") is not None]
        out.update(state=ST_K, K={"legs": [LM.leg_json(L) for L in K_legs], "depth_pct": round(100.0 * abs(e.price - cx) / size, 1) if size else None,
                                  "time_ratio": round((self.end - e.bar) / Ib, 2), "C_K": round(float(np.mean(cK)), 2) if cK else None,
                                  "C_I": round(float(np.mean(cI)), 2) if cI else None,
                                  "counter_impulse": [LM.leg_json(L) for L in K_legs if L["dir"] != dirn and L["label"] in LM.IMPULSE_LABELS]})
        if out["K"]["counter_impulse"]:
            out["note"] = "विरुद्ध दिशेचा आवेग (zigzag चा A / C, किंवा reversal) — पुरावा, gate नाही"
        return out

    def _log_json(self):
        ts = pd.to_datetime(self.F["timestamp"])
        return [{**x, "ts": str(ts.iloc[x["bar"]]) if 0 <= x["bar"] < len(ts) else None} for x in self.log]


def state_at(lg, d, asof, es=None):
    return Tracker(lg, d, asof, es).state()
