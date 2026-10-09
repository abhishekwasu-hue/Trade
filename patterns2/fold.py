"""patterns2/fold.py — थर 3 §1, §5, §6: प्रत्येक बंद candle ला (K च्या सुरुवातीपासून, साठवलेल्या pivot-प्रवाहावर) hypotheses ⇒ गुण ⇒
preferred / alternate (स्थिरता) ⇒ अवस्था. State = शुद्ध fold ⇒ replay = live.

Input: थर 2 चा I (timeline) आणि legs (known_at सह), थर 1 चे D(d−1) / D(d) pivots (confirm ≤ decision bar) आणि tentative टोक.
"""
import bisect

import numpy as np
import pandas as pd

from legs2 import ik as LI
from legs2 import measure as LM
from pivots import engine as PE

from . import enum as EN
from . import rules as R
from . import score as SC
from . import settings as PS

FORMING = ("forming_A", "forming_B", "in_X", "in_triangle", "forming_Y", "forming_wedge", "impulse_K")
STATE_MR = {"forming_A": "A बनतोय", "forming_B": "B बनतोय", "in_X": "X मध्ये", "in_triangle": "triangle च्या आत",
            "forming_Y": "Y बनतोय", "forming_wedge": "wedge बनतोय", "impulse_K": "थांबा: K हा A किंवा नवी wave 1",
            "final_leg_in_progress": "शेवटचा leg चालू", "final_leg_present": "शेवटचा leg हजर",
            "complete_resuming": "pattern पूर्ण, resumption चालू", "none": "pattern ओळखता येत नाही / थांबा"}
FAMILY_MR = {"zigzag": "zigzag", "flat": "flat", "triangle": "triangle", "double_zigzag": "double zigzag", "combination": "combination",
             "wedge": "wedge", "impulse_k": "impulse-K"}


def wave_labels(h):
    fam, L = h["family"], h["L"]
    if fam in ("zigzag", "flat"):
        return ["A", "B", "C"]
    if fam == "triangle":
        return list("ABCDE")
    if fam in ("wedge", "impulse_k"):
        return list("12345")
    xl = int(str((h.get("info") or {}).get("X", "1")).split()[0])
    xs = ["X"] if xl == 1 else ["Xa", "Xb", "X"]
    ys = ["Ya", "Yb", "Y"] if L - 3 - xl == 3 else ["Ya", "Yb", "Yc", "Yd", "Y"]
    return ["Wa", "Wb", "W"] + xs + ys


def _pt(p, tent=False):
    return {"price": float(p.price), "bar": int(p.bar), "kind": p.kind, "tent": tent}


def hyp_state(h, P, I, s):
    """§6 (एका hypothesis ची अवस्था). क्रम: impulse_K ⇒ forming ⇒ final_leg_in_progress ⇒ complete_resuming ⇒ final_leg_present.
    (complete_resuming हा final_leg_present चाच खास प्रकार ⇒ त्याआधी तपासला.)"""
    fam, b, x = h["family"], h["bounds"], h["x"]
    n, L, t = len(b) - 1, h["L"], h["t"]
    d = 1 if x[1] > x[0] else -1
    flags = []
    if fam == "impulse_k":
        return "impulse_K", flags
    if fam == "wedge" and not s["wedge_as_ending"]:
        return "forming_A", ["wedge (leading A) ⇒ थांबा"]
    if n < L:
        if fam in ("zigzag", "flat"):
            return ("forming_A" if n == 1 else "forming_B"), flags
        if fam == "triangle":
            return ("forming_A" if n == 1 else "in_triangle"), flags
        if fam == "wedge":
            return "forming_wedge", flags
        lab = wave_labels(h)[n - 1]
        return ("forming_A" if lab.startswith("W") else ("in_X" if lab.startswith("X") else "forming_Y")), flags

    def c_rule(a0, a1, c0, c1, j0, j1):
        """C (5 अपेक्षित): A चं टोक गाठलं नाही; किंवा पहिले तीन sub-legs confirmed आणि भाव चौथ्यात."""
        if (x[c1] - x[a1]) * d < 0:
            return True, (["C_short_possible"] if t == 1 else [])
        if b[j1] - b[j0] == 3 and t == 1:
            return True, ["C चा चौथा sub-leg"]
        return False, []

    inprog = False
    if fam in ("zigzag", "flat"):
        inprog, flags = c_rule(0, 1, 2, 3, 2, 3)
    elif fam == "triangle":
        inprog = b[5] - b[4] == 1 and t == 1
        flags = ["E चा दुसरा sub-leg"] if inprog else []
    elif fam == "wedge":
        inprog = not R.beyond(x[5], x[3], d)
    else:                                                                  # W-X-Y: Y चा शेवटचा भाग
        xl = int(str((h.get("info") or {}).get("X", "1")).split()[0])
        ys = 3 + xl
        if L - ys == 3:
            if (x[ys + 3] - x[ys + 1]) * d < 0:
                inprog, flags = True, (["C_short_possible"] if t == 1 else [])
            elif b[ys + 3] - b[ys + 2] == 3 and t == 1:
                inprog, flags = True, ["Y च्या C चा चौथा sub-leg"]
        else:
            inprog = b[L] - b[L - 1] == 1 and t == 1
            flags = ["Y च्या E चा दुसरा sub-leg"] if inprog else []
    if inprog:
        return "final_leg_in_progress", flags
    if t == 1 and I is not None and not R.beyond(P[-1]["price"], I["end"].price, I["dir"]):
        return "complete_resuming", flags
    return "final_leg_present", flags


class Fold:
    """एका degree (d = 1 किंवा 2) साठी, शेवटच्या asof पर्यंत bar-दर-bar."""

    def __init__(self, lg, d, asof, s=None, parent=None):
        self.lg, self.res, self.d, self.s = lg, lg["res"], d, PS.load(s)
        self.tr = LI.Tracker(lg, d, asof)
        self.tr.run()
        m15 = self.res["m15"]
        self.end = self.tr.end
        self.ts = pd.to_datetime(m15["timestamp"]).iloc[:self.end + 1].reset_index(drop=True)
        self.h, self.lo = m15["high"].to_numpy(float), m15["low"].to_numpy(float)
        self.inner = sorted(self.res["pivots"][d - 1], key=lambda p: p.bar)
        self.same = sorted(self.res["pivots"][d], key=lambda p: p.bar)
        self.d0 = self.res["pivots"][0]
        self.legs = self.lg["legs"][d]
        self.parent = parent
        self._enum, self._st = {}, {}
        self.coarse, self.closed = set(), set()
        self.out = {}
        self.log = []

    # ------------------------------------------------------------------------------------------------ input
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

    def _inner_pts(self, t):
        return [_pt(p) for p in self.inner if p.confirm_bar <= t]

    def phase(self, I, t):
        """थर 2 §3.3 ची अवस्था bar t ला (legs2.ik.Tracker.state सारखीच): I_end पलीकडे tentative टोक ⇒ एक degree खालचा उलट pivot
        नाही ⇒ impulse; आहे ⇒ kstart. नाहीतर (I_end D(d) ने confirm) ⇒ k."""
        e, dirn = I["end"], I["dir"]
        if t <= e.bar:
            return "k"
        seg = self.h[e.bar + 1:t + 1] if dirn > 0 else self.lo[e.bar + 1:t + 1]
        k = int(np.argmax(seg)) if dirn > 0 else int(np.argmin(seg))
        if not R.beyond(float(seg[k]), e.price, dirn):
            return "k"
        eb = e.bar + 1 + k
        opp = "L" if dirn > 0 else "H"
        if not any(p.kind == opp and p.bar > eb and p.confirm_bar <= t for p in self.inner):
            return "impulse"
        return "kstart"

    def _wave2(self, I, t):
        asof = self.ts.iloc[t] + pd.Timedelta(minutes=15)
        tr = PE.trend(PE.known(self.res, self.d + 1, asof))
        ones = [L for L in self.legs if L["a"].bar >= I["origin"].bar and L["b"].bar <= I["end"].bar
                and L["b"].confirm_bar <= t and L["label"] in LM.IMPULSE_LABELS]
        return tr["dir"] == -I["dir"] and len(ones) == 1

    # ------------------------------------------------------------------------------------------------ एका bar ला
    def hyps_at(self, I, t):
        groups = [I["end"]]
        if len(I["ends"]) >= 2:
            groups.append(I["ends"][-2])                                           # expanded flat: जुन्या I_end पासूनसुद्धा
        out, meta = [], []
        inner_t = self._inner_pts(t)
        legs_t = [L for L in self.legs if L["b"].confirm_bar <= t]
        w2 = self._wave2(I, t)
        for gi, S in enumerate(groups):
            gkey = (I["origin"].bar, S.bar)
            if gi and gkey in self.closed:
                continue
            coarse = gkey in self.coarse
            P = self._P(S, t, coarse)
            if not coarse and len(P) > int(self.s["max_points"]):
                self.coarse.add(gkey)                                              # एकदाच, pivot-संख्येवरून (घड्याळ नाही)
                coarse = True
                P = self._P(S, t, True)
                self.log.append({"bar": t, "event": "coarse (एक degree वरचे pivots)", "group": S.bar})
            key = (S.bar, coarse, tuple((p["bar"], p["price"], p["tent"]) for p in P))
            if key not in self._enum:
                self._enum[key] = EN.enumerate_hyps(P, self.s, sigma=S.sigma)
            hs, hit = self._enum[key]
            ctx = SC.Ctx(P, inner_t, self.h, self.lo, legs_t, t, S.sigma, self.s)
            ctx._st = self._st.setdefault((S.bar, coarse, tuple(p["bar"] for p in inner_t[-40:]), P[-1]["bar"], P[-1]["price"]), {})
            ctx.wave2_evidence = w2
            gh = []
            for h0 in hs:
                h = dict(h0)
                SC.score(h, ctx)
                h["group"], h["gi"], h["coarse"] = S.bar, gi, coarse
                h["id"] = EN.identity(h, P)
                h["state"], h["flags"] = hyp_state(h, P, I, self.s)
                nb = len(h["bounds"]) - 1
                h["structs"] = [ctx.structure(h["bounds"][k], h["bounds"][k + 1]) for k in range(nb) if k < nb - 1 or h["done"]]
                h["P"] = P
                gh.append(h)
            if gi and not gh:
                self.closed.add(gkey)                                              # जुन्या गटात एकही valid नाही ⇒ गट बंद
            out += gh
            meta.append({"start": round(S.price, 2), "start_ts": str(S.ts), "coarse": coarse, "points": len(P), "budget_hit": hit,
                         "n": len(gh)})
        order = {f: i for i, f in enumerate(PS.ORDER)}
        # क्रम: गुण ⇒ बरोबरीत थर 2 चा नवा I आधी ⇒ निश्चित pattern-क्रम ⇒ (शेवटचा, फक्त निश्चिततेसाठी) सीमा — Abhi च्या §3.7 यादीत नोंद
        out.sort(key=lambda h: (-h["score"], h["gi"], order[h["family"]], tuple(h["bounds"]), h["t"]))
        return out, meta

    @staticmethod
    def _match(pid, hs):
        """त्याच family / प्रकार / गटाचा hypothesis, ज्याच्या confirmed टोकांत जुन्या टोकांचा prefix आहे (tentative ⇒ confirmed,
        अपूर्ण ⇒ पूर्ण). coarse ⇒ जुनी टोकं coarse P च्या bars वर projected (nested pivots). शेवटच्या wave चं confirmed टोक पुढे सरकलं
        (त्याच wave चा नवा टोक) ⇒ "extension" (तोच hypothesis). रिटर्न (hypothesis, "same" / "extension") किंवा (None, None)."""
        best, how_b = None, None
        for h in hs:
            f, k, g, ends = h["id"]
            if (f, k, g) != pid[:3]:
                continue
            pe = pid[3]
            if h.get("coarse") and h.get("P"):
                allowed = {p["bar"] for p in h["P"]}
                pe = tuple(b for b in pe if b in allowed)
            how = None
            if ends[:len(pe)] == pe:
                how = "same"
            elif pe and len(ends) >= len(pe) and ends[:len(pe) - 1] == pe[:-1] and ends[len(pe) - 1] > pe[-1]:
                how = "extension"
            if how and (best is None or (how == "same", h["score"]) > (how_b == "same", best["score"])):
                best, how_b = h, how
        return best, how_b

    def run(self):
        st = {"pref": None, "chal": None, "n": 0, "origin": None}
        for t in range(self.end + 1):
            I = self.tr.I_at(t)
            rec = {"bar": t, "ts": str(self.ts.iloc[t]), "I": None, "phase": None, "pref": None, "alt": None, "agg": "none",
                   "n_valid": 0, "ratio": None, "groups": [], "change": None}
            if I is None:
                st.update(pref=None, chal=None, n=0, origin=None)
                self.out[t] = rec
                continue
            if st["origin"] != I["origin"].bar:
                st.update(pref=None, chal=None, n=0, origin=I["origin"].bar)
                self.coarse, self.closed = set(), set()
            rec["I"] = {"dir": I["dir"], "origin": I["origin"].price, "end": I["end"].price, "end_bar": I["end"].bar}
            ph = self.phase(I, t)
            rec["phase"] = ph
            if ph == "impulse":                                                   # K चा इतिहास (preferred) हरवत नाही
                self.out[t] = rec
                continue
            if ph == "kstart":
                rec["agg"] = "forming_A"
                self.out[t] = rec
                continue
            hs, meta = self.hyps_at(I, t)
            rec["groups"], rec["n_valid"] = meta, len(hs)
            pref, change = self._choose(st, hs, t)
            rec["change"] = change
            if pref is not None:
                rec["pref"] = pref
                alt = next((h for h in hs if h["family"] != pref["family"] or h["bounds"][-1] != pref["bounds"][-1]
                            or h["group"] != pref["group"]), None)
                rec["alt"] = alt
                if len(hs) >= 2 and hs[1]["score"] > 0:
                    rec["ratio"] = round(hs[0]["score"] / hs[1]["score"], 3)
                rec["agg"] = "none" if all(h["state"] in FORMING for h in hs) else pref["state"]
            rec["hyps"] = hs
            self.out[t] = rec
        return self.out

    def _choose(self, st, hs, t):
        """§5.4: preferred valid असेपर्यंत राहतो; तोच challenger ≥ hysteresis × गुण, लागोपाठ hysteresis_bars candles ⇒ बदल;
        preferred invalid ⇒ लगेच बदल. प्रत्येक बदलाची नोंद (extension = बदल नाही, फक्त नोंद)."""
        if not hs:
            if st["pref"] is not None:
                self.log.append({"bar": t, "event": "सगळे hypotheses invalid", "from": st["pref"][0]})
            st.update(pref=None, chal=None, n=0)
            return None, None
        top = hs[0]
        if st["pref"] is None:
            st.update(pref=top["id"], chal=None, n=0)
            return top, {"why": "पहिला preferred", "to": top["family"]}
        cur, how = self._match(st["pref"], hs)
        if cur is None:
            old = st["pref"][0]
            self.log.append({"bar": t, "event": "preferred invalid ⇒ बदल", "from": old, "to": top["family"]})
            st.update(pref=top["id"], chal=None, n=0)
            return top, {"why": "preferred invalid", "from": old, "to": top["family"]}
        if how == "extension":
            self.log.append({"bar": t, "event": "extension", "family": cur["family"]})
        st["pref"] = cur["id"]
        others = [h for h in hs if h is not cur and h["id"] != cur["id"]]
        ch = others[0] if others else None
        if ch is not None and ch["score"] >= float(self.s["hysteresis"]) * cur["score"]:
            same = st["chal"] is not None and self._match(st["chal"], [ch])[0] is not None
            st["n"] = st["n"] + 1 if same else 1
            st["chal"] = ch["id"]
            if st["n"] >= int(self.s["hysteresis_bars"]):
                self.log.append({"bar": t, "event": "challenger ⇒ बदल", "from": cur["family"], "to": ch["family"],
                                 "score": (cur["score"], ch["score"])})
                st.update(pref=ch["id"], chal=None, n=0)
                return ch, {"why": "challenger", "from": cur["family"], "to": ch["family"]}
        else:
            st.update(chal=None, n=0)
        return cur, None


BANS = {"forming_A": "A-end ⇒ entry नाही", "forming_B": "B च्या आत ⇒ entry नाही (B-end ⇒ C trade default OFF)",
        "in_X": "X च्या आत / X-end ⇒ Y: entry नाही", "in_triangle": "triangle च्या आत (B–D) ⇒ entry नाही",
        "forming_Y": "Y बनतोय (X-end ⇒ Y entry नाही)", "impulse_K": "K स्वतः 5-wave ⇒ थांबा", "forming_wedge": "wedge बनतोय"}


def bans(h):
    """Correction Reader §2.3.3 च्या position बंदी — फक्त नोंद (निर्णय थर 7)."""
    if not h:
        return None
    return BANS.get(h["state"])


def hyp_json(h, ts):
    lab = wave_labels(h)
    P = h["P"]
    pts = [{"label": "0", "price": round(P[0]["price"], 2), "ts": str(ts.iloc[P[0]["bar"]])}]
    for k, bi in enumerate(h["bounds"][1:]):
        pts.append({"label": lab[k], "price": round(P[bi]["price"], 2), "ts": str(ts.iloc[P[bi]["bar"]]), "tentative": P[bi]["tent"]})
    return {"family": h["family"], "kind": h["kind"], "sub": (h.get("info") or {}).get("sub"), "barrier": (h.get("info") or {}).get("barrier"),
            "waves": len(h["bounds"]) - 1, "of": h["L"], "points": pts, "after_leg": h["t"] == 1, "score": h["score"],
            "state": h["state"], "flags": h["flags"], "lines": h["lines"], "completion": h["completion"], "coarse": h["coarse"],
            "from_old_I_end": bool(h["gi"]), "variants": h.get("variants")}


def rec_json(rec, ts, top=12):
    r = {k: v for k, v in rec.items() if k not in ("pref", "alt", "hyps")}
    r["pref"] = hyp_json(rec["pref"], ts) if rec.get("pref") else None
    r["alt"] = hyp_json(rec["alt"], ts) if rec.get("alt") else None
    r["hyps"] = [hyp_json(h, ts) for h in (rec.get("hyps") or [])[:top]]
    r["agg_mr"] = STATE_MR.get(rec["agg"], rec["agg"])
    r["bans_note"] = bans(rec.get("pref"))
    return r


def position(child, parent, t):
    """D1 चा I / K हा D2 च्या चालू K च्या आत आहे का; असेल तर D2 preferred मधली जागा (फक्त नोंद; निर्णय थर 7)."""
    if parent is None:
        return None
    pc, pp = child.out.get(t), parent.out.get(t)
    if not pc or not pp or not pc["I"] or not pp["I"] or pp["phase"] != "k":
        return None
    if pc["I"]["end_bar"] <= pp["I"]["end_bar"]:
        return {"inside": False}
    h = pp.get("pref")
    if not h:
        return {"inside": True, "where": None}
    lab = wave_labels(h)
    n = len(h["bounds"]) - 1
    where = "pattern नंतर" if h["t"] == 1 else lab[n - 1]
    return {"inside": True, "where": where, "parent": h["family"]}
