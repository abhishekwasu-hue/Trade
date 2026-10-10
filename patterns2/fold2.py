"""patterns2/fold2.py — थर 3 v2.1 §1, §5, §6, §7: थर 2 v2 (ik2) च्या I / K वर, प्रत्येक बंद candle ला hypotheses ⇒ गुण ⇒
preferred / alternate (स्थिरता) ⇒ अवस्था ⇒ momentum. State = शुद्ध fold (replay = live). निर्णय नाही.

v1 (fold.py) पासून बदल:
- I, K अवस्था, flags थर 2 v2 (`legs2.ik2.Tracker`) मधून; "impulse चालू" ⇒ pattern नाही; "K सुरू झाला असावा" ⇒ फक्त forming_A.
- नियम rules2 / enum2 / score2 (invalid फक्त I_origin real break; प्रकार ⇒ दुसरा प्रकार; मजबूत पुरावा m 0.2).
- Wedge = संपूर्ण K (ending) — इतर templates सारख्या अवस्था.
- complete_resuming = शेवटचा wave confirmed pivot वर संपला + एक उलट leg + थर 2 `cisd` **किंवा** `last_leg_start_broken`;
  शेवटचा wave लहान ⇒ `final_leg_short` (पूर्णता 0.6). Resuming नंतर भाव शेवटच्या wave पलीकडे ⇒ final_leg_in_progress ("resuming failed").
- position_ban (D2 preferred मधली जागा), final_flag_risk, partial_rise, C = A projection, pattern रेघा, momentum (§7).
"""
import numpy as np
import pandas as pd

from legs2 import ik2 as LI
from legs2 import measure as LM

from . import enum2 as EN
from . import fold as F1
from . import momentum as MO
from . import rules as R
from . import score as SC1
from . import score2 as SC
from . import settings2 as PS

FORMING = F1.FORMING
STATE_MR = {**F1.STATE_MR, "complete_resuming": "pattern पूर्ण, resumption सुरू", "impulse": "impulse चालू (pattern नाही)"}
FAMILY_MR = F1.FAMILY_MR
wave_labels = F1.wave_labels
BAN_STATES = ("forming_A", "forming_B", "in_X", "in_triangle")


def _pt(p, tent=False):
    return {"price": float(p.price), "bar": int(p.bar), "kind": p.kind, "tent": tent}


def hyp_state(h, P, I, fl, s):
    """§6 (एका hypothesis ची अवस्था) आणि खुणा."""
    fam, b, x = h["family"], h["bounds"], h["x"]
    n, L, t = len(b) - 1, h["L"], h["t"]
    d = 1 if x[1] > x[0] else -1
    flags = []
    if fam == "impulse_k":
        return "impulse_K", flags
    if n < L:
        if fam in ("zigzag", "flat"):
            return ("forming_A" if n == 1 else "forming_B"), flags
        if fam == "triangle":
            return ("forming_A" if n == 1 else "in_triangle"), flags
        if fam == "wedge":
            return ("forming_A" if n == 1 else "forming_wedge"), flags
        lab = wave_labels(h)[n - 1]
        return ("forming_A" if lab.startswith("W") else ("in_X" if lab.startswith("X") else "forming_Y")), flags
    short = False
    inprog = False
    if fam in ("zigzag", "flat"):
        if (x[3] - x[1]) * d < 0:
            short = True
            if t == 0:
                inprog = True
            flags.append("C_short_possible")
        elif b[3] - b[2] == 3 and t == 1:
            inprog, flags = True, ["C चा चौथा sub-leg"]
    elif fam == "triangle":
        inprog = b[5] - b[4] == 1 and t == 1
        flags = ["E चा दुसरा sub-leg"] if inprog else []
    elif fam == "wedge":
        if not R.beyond(x[5], x[3], d):
            short = True
            flags.append("अपूर्ण wedge (5 ने 3 गाठलं नाही)")
            if t == 0:
                inprog = True
    else:
        xl = int(str((h.get("info") or {}).get("X", "1")).split()[0])
        ys = 3 + xl
        if L - ys == 3:
            if (x[ys + 3] - x[ys + 1]) * d < 0:
                short = True
                flags.append("C_short_possible")
                inprog = t == 0
            elif b[ys + 3] - b[ys + 2] == 3 and t == 1:
                inprog, flags = True, ["Y च्या C चा चौथा sub-leg"]
        else:
            inprog = b[L] - b[L - 1] == 1 and t == 1
    if inprog or t == 0:
        return "final_leg_in_progress", flags
    if short:
        flags.append("final_leg_short")
    if I is not None and not R.beyond(P[-1]["price"], I["end"]["price"], I["dir"]) and \
            (fl.get("cisd") is not None or fl.get("last_leg_start_broken") is not None):
        return "complete_resuming", flags
    return "final_leg_present", flags


def c_equals_a(h, P):
    """C = A projection (B-end पासून), A, B हजर असतील तर (zigzag / flat; W-X-Y चा Y साठी Y.A)."""
    x = h["x"]
    if h["family"] in ("zigzag", "flat") and len(x) >= 3:
        return round(x[2] + (x[1] - x[0]), 2)
    return None


def pattern_lines(h, P, ts):
    """Pattern रेघांची टोकं (थर 5 / chart साठी): zigzag channel (0–B, समांतर A), triangle A–C / B–D, wedge 1–3 / 2–4."""
    b, x = h["bounds"], h["x"]
    bx = [P[k]["bar"] for k in b]
    n = len(b) - 1
    out = []

    def seg(i, j, name):
        if j <= n and bx[j] != bx[i]:
            out.append({"name": name, "from": {"ts": str(ts.iloc[bx[i]]), "price": round(x[i], 2)},
                        "to": {"ts": str(ts.iloc[bx[j]]), "price": round(x[j], 2)}})
    if h["family"] in ("zigzag", "flat"):
        seg(0, 2, "0–B")
    elif h["family"] == "triangle":
        seg(1, 3, "A–C")
        seg(2, 4, "B–D")
    elif h["family"] == "wedge":
        seg(1, 3, "1–3")
        seg(2, 4, "2–4")
    return out


class Fold:
    """एका degree (1 किंवा 2) साठी bar-दर-bar. trk = legs2.ik2.Tracker (त्याच degree चा)."""

    def __init__(self, lg, trk, s=None, parent=None):
        self.lg, self.trk, self.res, self.d, self.s = lg, trk, lg["res"], trk.d, PS.load(s)
        m15 = self.res["m15"]
        self.n = len(m15)
        self.ts = pd.to_datetime(m15["timestamp"]).reset_index(drop=True)
        self.h, self.lo = m15["high"].to_numpy(float), m15["low"].to_numpy(float)
        self.inner = sorted(self.res["pivots"][self.d - 1], key=lambda p: p.bar)
        self.same = sorted(self.res["pivots"][self.d], key=lambda p: p.bar)
        self.legs = lg["legs"][self.d]
        self.parent = parent
        self._enum, self._st = {}, {}
        self.coarse, self.closed = set(), set()
        self.out, self.log = {}, []
        self.hyst = MO.Hysteresis(self.s["hysteresis_bars"])

    def _P(self, S, t, coarse):
        src = self.same if coarse else self.inner
        pts = [_pt(S)] + [_pt(p) for p in src if p.bar > S.bar and p.confirm_bar <= t]
        last = pts[-1]
        if t > last["bar"]:
            seg = slice(last["bar"] + 1, t + 1)
            if last["kind"] == "H":
                i = last["bar"] + 1 + int(np.argmin(self.lo[seg]))
                pts.append({"price": float(self.lo[i]), "bar": i, "kind": "L", "tent": True})
            else:
                i = last["bar"] + 1 + int(np.argmax(self.h[seg]))
                pts.append({"price": float(self.h[i]), "bar": i, "kind": "H", "tent": True})
        return pts

    def _wave2(self, I, t):
        tr = self.trk.parent(t)[0]
        ones = [L for L in self.legs if L["a"].bar >= I["origin"].bar and L["b"].bar <= I["end"].bar
                and L["b"].confirm_bar <= t and L.get("label") in LM.IMPULSE_LABELS]
        return tr == ("DOWN" if I["dir"] > 0 else "UP") and len(ones) == 1

    def hyps_at(self, I, t, st):
        groups = [I["end"]]
        if len(I["ends"]) >= 2:
            groups.append(I["ends"][-2])                                       # expanded flat: जुन्या I_end पासूनसुद्धा
        out, meta = [], []
        inner_t = [_pt(p) for p in self.inner if p.confirm_bar <= t]
        legs_t = [L for L in self.legs if L["b"].confirm_bar <= t]
        w2 = self._wave2(I, t)
        hs_ = self.trk.strict_hl(I, t)
        il_bars = (I["end"].bar - (hs_.bar if hs_ is not None else I["origin"].bar)) or None
        extra = {"rv": self.lg["rv"], "bad": self.lg["bad"], "i_leg_bars": il_bars}
        fl = st.get("flags") or {}
        Ij = {"end": {"price": I["end"].price}, "dir": I["dir"]}
        for gi, S in enumerate(groups):
            gkey = (I["origin"].bar, S.bar)
            if gi and gkey in self.closed:
                continue
            coarse = gkey in self.coarse
            P = self._P(S, t, coarse)
            if not coarse and len(P) > int(self.s["max_points"]):
                self.coarse.add(gkey)
                coarse = True
                P = self._P(S, t, True)
                self.log.append({"bar": t, "event": "coarse (एक degree वरचे pivots)", "group": S.bar})
            key = (S.bar, coarse, tuple((p["bar"], p["price"], p["tent"]) for p in P))
            if key not in self._enum:
                self._enum[key] = EN.enumerate_hyps(P, self.s, sigma=S.sigma)
            hs, hit = self._enum[key]
            ctx = SC1.Ctx(P, inner_t, self.h, self.lo, legs_t, t, S.sigma, self.s)
            ctx._st = self._st.setdefault((S.bar, coarse, tuple(p["bar"] for p in inner_t[-40:]), P[-1]["bar"], P[-1]["price"]), {})
            ctx.wave2_evidence = w2
            ctx.extra = extra
            gh = []
            for h0 in hs:
                h = dict(h0)
                SC.score(h, ctx)
                h["group"], h["gi"], h["coarse"] = S.bar, gi, coarse
                h["id"] = EN.identity(h, P)
                h["state"], h["flags"] = hyp_state(h, P, Ij, fl, self.s)
                if "final_leg_short" in h["flags"]:
                    h["completion"] = h["completion"] + [("final_leg_short", float(self.s["short_final_m"]))]
                nb = len(h["bounds"]) - 1
                h["structs"] = [ctx.structure(h["bounds"][k], h["bounds"][k + 1]) for k in range(nb) if k < nb - 1 or h["done"]]
                h["P"] = P
                gh.append(h)
            if gi and not gh:
                self.closed.add(gkey)
            out += gh
            meta.append({"start": round(S.price, 2), "start_ts": str(S.ts), "coarse": coarse, "points": len(P), "budget_hit": hit,
                         "n": len(gh)})
        order = {f: i for i, f in enumerate(PS.ORDER)}
        out.sort(key=lambda h: (-h["score"], h["gi"], order[h["family"]], tuple(h["bounds"]), h["t"]))
        return out, meta

    def run(self, upto=None):
        st_ = {"pref": None, "chal": None, "n": 0, "origin": None, "last_state": None}
        end = self.n - 1 if upto is None else upto
        for t in range(end + 1):
            st = self.trk.state(t)
            I = self.trk.I_at(t)
            rec = {"bar": t, "ts": str(self.ts.iloc[t]), "I": None, "phase": st["state"], "pref": None, "alt": None, "agg": "none",
                   "n_valid": 0, "ratio": None, "groups": [], "change": None, "l2": st, "momentum": None, "notes": []}
            if I is None:
                st_.update(pref=None, chal=None, n=0, origin=None, last_state=None)
                self.hyst = MO.Hysteresis(self.s["hysteresis_bars"])
                self.out[t] = rec
                continue
            if st_["origin"] != (I["origin"].bar, I["ends"][0].bar):
                st_.update(pref=None, chal=None, n=0, origin=(I["origin"].bar, I["ends"][0].bar), last_state=None)
                self.coarse, self.closed = set(), set()
                self.hyst = MO.Hysteresis(self.s["hysteresis_bars"])                 # नवा I ⇒ जुन्या K चा verdict पुढे नाही
            rec["I"] = {"dir": I["dir"], "origin": I["origin"].price, "end": I["end"].price, "end_bar": I["end"].bar, "mode": I["mode"]}
            if st["state"] in (LI.ST_IMP, LI.ST_KSTART):
                self.hyst = MO.Hysteresis(self.s["hysteresis_bars"])               # momentum नसलेली candle ⇒ hysteresis पुन्हा
            if st["state"] == LI.ST_IMP:
                rec["agg"] = "impulse"
                self.out[t] = rec
                continue
            if st["state"] == LI.ST_KSTART:
                rec["agg"] = "forming_A"
                self.out[t] = rec
                continue
            hs, meta = self.hyps_at(I, t, st)
            rec["groups"], rec["n_valid"] = meta, len(hs)
            pref, change = self._choose(st_, hs, t)
            rec["change"] = change
            if pref is not None:
                rec["pref"] = pref
                rec["alt"] = next((h for h in hs if h["family"] != pref["family"] or h["bounds"][-1] != pref["bounds"][-1]
                                   or h["group"] != pref["group"]), None)
                if len(hs) >= 2 and hs[1]["score"] > 0:
                    rec["ratio"] = round(hs[0]["score"] / hs[1]["score"], 3)
                rec["agg"] = "none" if all(h["state"] in FORMING for h in hs) else pref["state"]
                if st_["last_state"] == "complete_resuming" and pref["state"] == "final_leg_in_progress":
                    self.log.append({"bar": t, "event": "resuming failed", "family": pref["family"]})
                    rec["notes"].append("resuming failed")
                st_["last_state"] = pref["state"]
            rec["hyps"] = hs
            rec["momentum"] = self.momentum(rec, st, I, t)
            rec.update(self.extras(rec, st, I, t))
            self.out[t] = rec
        return self.out

    def momentum(self, rec, st, I, t, zone_fn=None, hyst=True):
        """§7 — थर 4 नंतर zone_fn देऊन हेच पुन्हा (re-emit)."""
        h = rec.get("pref")
        P = h["P"] if h is not None else self._P(I["end"], t, False)
        if rec["agg"] == "none":
            h = None
        hs = self.trk.strict_hl(I, t)
        a = hs if hs is not None else I["origin"]
        il = (a.bar, I["end"].bar, a.price, I["end"].price)
        kd = -I["dir"]
        kx = (max if kd > 0 else min)(P, key=lambda p: p["price"])
        st_k = SC1.Ctx(P, [_pt(p) for p in self.inner if p.confirm_bar <= t], self.h, self.lo, [], t, I["end"].sigma, self.s)
        kstruct = st_k.structure(0, P.index(kx))["struct"] if P.index(kx) > 0 else SC1.UNK
        ctx = {"A": self.lg["A"], "rr": self.lg["rr"], "lg": self.lg, "s": self.s, "t": t, "state": st, "P": P, "h": h,
               "sigma": float(I["end"].sigma or 0.0), "i_leg": il, "pref_family": None if h is None else h["family"],
               "k_struct": kstruct, "d0": self.d - 1,
               "k_legs": [L for L in self.legs if L["a"].bar >= I["end"].bar and L["b"].confirm_bar <= t]}
        m = MO.evaluate(ctx, zone_fn)
        if hyst:
            m["raw_verdict"] = m["verdict"]
            m["verdict"] = self.hyst.step(m["verdict"], bool(m["danger"]))
        return m

    def extras(self, rec, st, I, t):
        """final_flag_risk, partial_rise, C = A, रेघा, position_ban (पालक)."""
        out = {"final_flag_risk": None, "partial_rise": None, "c_eq_a": None, "lines": [], "range_like": None, "position": None}
        h = rec.get("pref")
        K = st.get("K") or {}
        sig = float(I["end"].sigma or 0.0)
        kb = max(t - I["end"].bar, 1)
        if sig and K.get("extreme") is not None:
            slope = abs(K["extreme"] - I["end"].price) / kb / sig
            pushes = [L for L in self.legs if L["dir"] == I["dir"] and L["a"].bar >= I["origin"].bar and L["b"].bar <= I["end"].bar
                      and L["b"].confirm_bar <= t]
            sot = (st.get("I") or {}).get("SOT_trend")
            mm = measured_move(I, {"h": self.h, "l": self.lo}, K["extreme"], sig, float(self.s["final_flag_mm_sigma"]))
            a_ok = slope < float(self.s["final_flag_slope"])
            b_ok = len(pushes) >= int(self.s["final_flag_pushes"]) or bool(sot)
            if a_ok and b_ok and mm["ok"]:                                       # Abhi उत्तर 7: (a) आणि (b) आणि (c) — नोंद + grade, gate नाही
                out["final_flag_risk"] = {"slope_sigma_bar": round(slope, 4), "pushes": len(pushes), "SOT_trend": bool(sot),
                                          "measured_move": mm["target"]}
        if h is not None:
            P = h["P"]
            out["c_eq_a"] = c_equals_a(h, P)
            out["lines"] = pattern_lines(h, P, self.ts)
            out["range_like"] = h.get("range_like")
            x = h["x"]
            if h["family"] == "flat" and len(x) >= 4 and x[1] != x[2]:
                frac = abs(x[3] - x[2]) / abs(x[1] - x[2])
                if float(self.s["partial_lo"]) <= frac < 1.0 and h["t"] == 1:
                    out["partial_rise"] = {"frac": round(frac, 3), "note": "उलट कडेचा break 75–79% (Bulkowski)"}
        if self.parent is not None:
            out["position"] = position(self, self.parent, t)
        return out

    _match = staticmethod(F1.Fold._match)

    def _choose(self, st, hs, t):
        return F1.Fold._choose(self, st, hs, t)


def measured_move(I, A, k_extreme, sig, tol):
    """final_flag_risk (c): target_MM = |I_end − I_origin| (पहिला I_end) चं, I_end नंतरच्या पहिल्या K च्या टोकापासून trend-दिशेने
    projection; चालू K चा पट्टा (K टोक ↔ आत्ताचा I_end) target_MM च्या ±tol·σ मध्ये ⇒ ✓ (trend आधीच परिपक्व). पहिला K अजून चालू
    (I_end एकदाच) ⇒ ✗."""
    ends = I["ends"]
    if len(ends) < 2 or not sig:
        return {"ok": False, "target": None}
    e0, e1, d = ends[0], ends[1], I["dir"]
    seg = A["l"][e0.bar + 1:e1.bar + 1] if d > 0 else A["h"][e0.bar + 1:e1.bar + 1]
    if not len(seg):
        return {"ok": False, "target": None}
    tip = float(seg.min() if d > 0 else seg.max())
    target = tip + d * abs(e0.price - I["origin"].price)
    lo, hi = sorted((float(k_extreme), float(I["end"].price)))
    ok = lo - tol * sig <= target <= hi + tol * sig
    return {"ok": bool(ok), "target": round(target, 2)}


def position(child, parent, t):
    """D1 चा K हा D2 च्या preferred मधली जागा ⇒ position_ban (A-end / B च्या आत / X च्या आत / triangle च्या आत). नोंद + थर 7 gate."""
    pc, pp = child.out.get(t), parent.out.get(t)
    if not pc or not pp or not pc["I"] or not pp["I"] or pp["phase"] not in (LI.ST_K, LI.ST_KSTART):
        return {"inside": False, "ban": False}
    h = pp.get("pref")
    stt = pp["agg"] if h is None else h["state"]
    where = None
    if h is not None:
        n = len(h["bounds"]) - 1
        where = "pattern नंतर" if h["t"] == 1 else wave_labels(h)[n - 1]
    return {"inside": True, "where": where, "parent": None if h is None else h["family"], "parent_state": stt,
            "ban": stt in BAN_STATES}


def hyp_json(h, ts):
    j = F1.hyp_json(h, ts)
    j["strong"] = (h.get("info") or {}).get("strong") or []
    j["c_eq_a"] = c_equals_a(h, h["P"])
    j["lines_geom"] = pattern_lines(h, h["P"], ts)
    j["range_like"] = h.get("range_like")
    return j


def rec_json(rec, ts, top=12):
    r = {k: v for k, v in rec.items() if k not in ("pref", "alt", "hyps", "l2")}
    r["pref"] = hyp_json(rec["pref"], ts) if rec.get("pref") else None
    r["alt"] = hyp_json(rec["alt"], ts) if rec.get("alt") else None
    r["hyps"] = [hyp_json(h, ts) for h in (rec.get("hyps") or [])[:top]]
    r["agg_mr"] = STATE_MR.get(rec["agg"], rec["agg"])
    r["l2_state"] = rec["l2"]["state"]
    return r
