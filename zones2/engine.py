"""zones2/engine.py — थर 4: buyer / seller areas, liquidity, sweep / accept, ★ (shadow; निर्णय नाही).

जन्म (§2): D1+ confirmed pivot ⇒ zone (जन्म = D1 `known_at`; degree वाढ त्या degree च्या `known_at` पासून). पट्टा H ⇒ [max(O, C), high],
L ⇒ [low, min(O, C)], रुंदी जन्माच्या σ ने 0.2–1 σ. भूमिका H seller / L buyer. स्वतंत्र स्रोत k: PDH / PDL / PDC, PWH / PWL (पूर्ण sessions).
Flags: c origin / base (आवेग leg + departure + BOS; `known_at` max-नियम), d range कड (थर 1 RANGE), e liquidity (EQ जोडी / त्या degree चं
शेवटचं टोक; नवं टोक / accept / real break ⇒ काढलं; sweep ⇒ `swept_at`).
एकत्र (§3): फक्त a + k; linkage overlap किंवा मध्यबिंदू ≤ 0.5 σ (सध्याचा σ; क्रम-स्वतंत्र single-linkage); union > 1.5 σ ⇒ सगळ्यात मोठ्या
अंतरावर तोड, प्रत्येक भाग ≤ 1.5 σ होईपर्यंत. Id = सगळ्यात जुना pivot (k-फक्त ⇒ k-id); merge ⇒ जुना id चं state; नवा id ⇒ नवं state.
Id वंश (Abhi निर्णय, 04 §3): id कधीच बदलत नाही — pruning ने मूळ pivot गेला तरी तोच id (आधीच्या सदस्यांवरून); merge ⇒ जुना id;
split ⇒ मूळ pivot चा भाग id ठेवतो, बाकीचे भाग नवे id; प्रत्येक बदल `lineage` नोंद.
अवस्था (§4; प्रत्येक बंद candle): भेट (जन्माची चाल नाही), reaction (≥ 1 σ, पुढच्या भेटीपर्यंत / 12 bars), touch_score, zone_sweep /
deep_sweep, reclaim, accept, spring test, pending ⇒ real break (`elliott/breaks.first_real_break`, settings `ZONE_BREAK`, retest_fn None,
end = decision bar) ⇒ flip ⇒ दुसरा real break ⇒ मेला; breaker (break आधीच्या 20 bars मध्ये sweep + displacement).
"""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from elliott import settings as ES
from legs2 import features as LF
from legs2 import measure as LM
from pivots import engine as PE

from . import settings as ZS

ZONE_BREAK = dict(ES.DEFAULTS)                     # zone real break (MASTER पातळी 2) — गोठवलेली प्रत, नाव register मध्ये
SELLER, BUYER = "seller", "buyer"


def _band(A, p, sig, s):
    """H ⇒ [max(O, C), high]; L ⇒ [low, min(O, C)]; रुंदी < min ⇒ टोकापासून body कडे वाढव; > max ⇒ टोकापासून कापा."""
    i = p.bar
    o, c = A["o"][i], A["c"][i]
    lo_w, hi_w = float(s["width_min"]) * sig, float(s["width_max"]) * sig
    if p.kind == "H":
        top, bot = p.price, max(o, c)
        w = top - bot
        if w < lo_w:
            bot = top - lo_w
        elif w > hi_w:
            bot = top - hi_w
    else:
        bot, top = p.price, min(o, c)
        w = top - bot
        if w < lo_w:
            top = bot + lo_w
        elif w > hi_w:
            top = bot + hi_w
    return float(top), float(bot)


class Zones:
    """सगळ्या bars वर fold. lg = legs2.measure2 build; st = swings2 structure; trk = ik2 trackers {1, 2}."""

    def __init__(self, lg, st, trk, s=None, es=None):
        self.lg, self.st, self.trk = lg, st, trk
        self.res = lg["res"]
        self.s = ZS.load(s)
        self.es = dict(ZONE_BREAK if es is None else es)
        m15 = self.res["m15"]
        self.m15 = m15
        self.n = len(m15)
        self.A = lg["A"]
        self.rr = lg["rr"]
        self.ts = pd.to_datetime(m15["timestamp"]).reset_index(drop=True)
        self.day = self.ts.dt.normalize()
        self.sig = np.array([self.res["sigma"].get(pd.Timestamp(d), np.nan) for d in self.day], float)
        self.segs = np.array([self.res["segments"].get(pd.Timestamp(d)) for d in self.day])
        self.mr = BR.median_range(m15, int(self.es["median_range_n"]))
        self.sess = {d: i for i, d in enumerate(self.res["sessions"])}
        self.atoms = self._atoms()
        self.state = {}                     # id ⇒ zone state
        self.owner = {}                     # atom id ⇒ zone id (वंश)
        self.events = []
        self.snap = {}
        self.groups_at = {}

    # ------------------------------------------------------------------------------------------------ atoms
    def _atoms(self):
        out = []
        piv = self.res["pivots"]
        hi_deg = {}
        for d in (2, 3):
            for p in piv.get(d, []):
                hi_deg.setdefault((p.bar, p.kind), []).append((d, p.confirm_bar))
        for p in piv[1]:
            if p.warmup or not np.isfinite(p.sigma):
                continue
            top, bot = _band(self.A, p, p.sigma, self.s)
            ups = sorted(hi_deg.get((p.bar, p.kind), []))
            out.append({"id": f"p{p.bar}{p.kind}", "src": "a", "pivot": p, "born": p.confirm_bar, "top": top, "bottom": bot,
                        "sigma": p.sigma, "role": SELLER if p.kind == "H" else BUYER, "ups": ups, "seg": self.res["segments"].get(
                            pd.Timestamp(p.ts).normalize())})
        out += self._k_atoms()
        out = sorted(out, key=lambda a: (a["born"], a["id"]))
        nxt = {}
        for a in reversed(out):                                                    # k: त्याच नावाचा नवा आला ⇒ जुना संपला
            if a["src"] == "k":
                a["until"] = nxt.get(a["kname"], 10 ** 12)
                nxt[a["kname"]] = a["born"]
        return out

    def _k_atoms(self):
        """PDH / PDL / PDC (आदला पूर्ण session) आणि PWH / PWL (आदला पूर्ण आठवडा). जन्म = नव्या session चा पहिला bar."""
        out = []
        full = PE.complete_sessions(self.m15)
        days = self.res["sessions"]
        first = {}
        for i, d in enumerate(self.day):
            first.setdefault(pd.Timestamp(d), i)
        A = self.A
        for k in range(1, len(days)):
            d, prev = days[k], days[k - 1]
            if not full.get(prev) or self.res["segments"].get(d) != self.res["segments"].get(prev) or d not in first:
                continue
            b0 = first[d]
            sig = self.sig[b0]
            if not np.isfinite(sig):
                continue
            idx = np.flatnonzero((self.day == prev).to_numpy())
            tol = float(self.s["k_tol"]) * sig
            lv = {"PDH": float(A["h"][idx].max()), "PDL": float(A["l"][idx].min()), "PDC": float(A["c"][idx[-1]])}
            wk = [x for x in days[:k] if pd.Timestamp(x).to_period("W") == pd.Timestamp(prev).to_period("W")]
            if pd.Timestamp(d).to_period("W") != pd.Timestamp(prev).to_period("W") and all(full.get(x) for x in wk):
                wi = np.flatnonzero(self.day.isin(wk).to_numpy())
                lv["PWH"], lv["PWL"] = float(A["h"][wi].max()), float(A["l"][wi].min())
            for name, v in lv.items():
                out.append({"id": f"k{name}{b0}", "src": "k", "kname": name, "pivot": None, "born": b0, "top": v + tol, "bottom": v - tol,
                            "sigma": sig, "role": SELLER if v >= A["o"][b0] else BUYER, "ups": [], "seg": self.res["segments"].get(d),
                            "weekly": name.startswith("PW")})
        return out

    def degree(self, a, t):
        d = 1
        for dd, cb in a["ups"]:
            if cb <= t:
                d = max(d, dd)
        return d

    # ------------------------------------------------------------------------------------------------ flags (atom)
    def flag_c(self, a, t):
        """origin / base: त्या pivot पासूनचा थर-2 D1 leg आवेग (कमकुवत सह) + departure + जवळचा swing plain-close BOS."""
        p = a["pivot"]
        if p is None:
            return None
        L = next((x for x in self.lg["legs"][1] if x["a"].bar == p.bar and x["a"].kind == p.kind), None)
        if L is None or L["b"].confirm_bar > t or L.get("label") not in LM.IMPULSE_LABELS:
            return None
        A, s = self.A, self.s
        dd = L["dir"]
        nb = int(s["departure_bars"])
        js = [j for j in range(p.bar + 1, min(p.bar + nb, self.n - 1) + 1)]
        if len(js) < nb or js[-1] > t:
            return None
        ndisp = sum(LF.displacement(A, self.rr, j, dd, self.lg["settings"]) for j in js)
        net = (A["c"][js[-1]] - p.price) * dd
        if not (ndisp >= int(s["departure_disp"]) or net >= float(s["departure_net"]) * a["sigma"]):
            return None
        bos = [e for e in self.st.get(1, {"events": []})["events"] if e["type"] == "BOS" and e["dir"] == dd
               and p.bar < e["bar"] <= L["b"].bar]
        if not bos or bos[0]["bar"] > t:
            return None
        k_at = max(L["b"].confirm_bar, js[-1], bos[0]["bar"])
        if k_at > t:
            return None
        fvg = any(LF.fvg(A, j, dd) for j in js)
        base = None
        if s["band_convention"] == "base":
            r = A["h"][max(p.bar - 1, 0):p.bar + 1].max() - A["l"][max(p.bar - 1, 0):p.bar + 1].min()
            base = bool(r <= float(s["base_range"]) * a["sigma"])
        weak = L["label"] != "आवेग"
        q = 0.5 if weak else (1.0 if (fvg and ndisp >= 1) else 0.7)
        return {"known_at": k_at, "fvg": fvg, "disp": ndisp, "base": base, "q": q, "label": L["label"]}

    def flag_d(self, a, t):
        tol = float(self.s["range_edge_tol"]) * a["sigma"]
        for d in (1, 2):
            if d not in self.st:
                continue
            r = self.st[d]["states"][t]["range"]
            if r is None:
                continue
            edge = r["top"] if a["role"] == SELLER else r["bottom"]
            if a["bottom"] - tol <= edge <= a["top"] + tol:
                return {"degree": d, "edge": edge, "range_known_at": r["known_at"]}
        return None

    def flag_e(self, a, t):
        """liquidity: EQ जोडी किंवा त्या degree चं शेवटचं (confirmed) टोक; नवं टोक पलीकडे ⇒ नाही."""
        p = a["pivot"]
        if p is None:
            return None
        d = self.degree(a, t)
        ps = [q for q in self.res["pivots"][d] if q.confirm_bar <= t and q.kind == p.kind and q.bar >= p.bar]
        if not ps:
            return None
        later = [q for q in ps if q.bar > p.bar]
        beyond = [q for q in later if (q.price > p.price if p.kind == "H" else q.price < p.price)]
        if beyond:
            return None
        nxt = later[0] if later else None
        if nxt is not None and nxt.eq:
            return {"why": "EQ", "known_at": nxt.confirm_bar}
        if not later:
            return {"why": "शेवटचं टोक", "known_at": a["born"]}
        return None

    # ------------------------------------------------------------------------------------------------ एकत्र
    def cluster(self, atoms, sig):
        """single-linkage (क्रम-स्वतंत्र): overlap किंवा मध्यबिंदू ≤ linkage σ; मग union > split σ ⇒ सगळ्यात मोठ्या अंतरावर तोड."""
        n = len(atoms)
        par = list(range(n))

        def f(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        lk = float(self.s["linkage"]) * sig
        for i in range(n):
            for j in range(i + 1, n):
                a, b = atoms[i], atoms[j]
                ov = min(a["top"], b["top"]) >= max(a["bottom"], b["bottom"])
                mid = abs((a["top"] + a["bottom"]) / 2 - (b["top"] + b["bottom"]) / 2) <= lk
                if ov or mid:
                    par[f(i)] = f(j)
        groups = {}
        for i in range(n):
            groups.setdefault(f(i), []).append(atoms[i])
        out = []
        for g in groups.values():
            out += self._split(sorted(g, key=lambda a: ((a["top"] + a["bottom"]) / 2, a["id"])), sig)
        return out

    def _split(self, g, sig):
        lim = float(self.s["split"]) * sig
        top, bot = max(a["top"] for a in g), min(a["bottom"] for a in g)
        if top - bot <= lim or len(g) == 1:
            return [g]
        mids = [(a["top"] + a["bottom"]) / 2 for a in g]
        k = int(np.argmax(np.diff(mids)))
        return self._split(g[:k + 1], sig) + self._split(g[k + 1:], sig)

    @staticmethod
    def gid(g):
        ps = [a for a in g if a["src"] == "a"]
        src = ps if ps else g
        return min(src, key=lambda a: (a["born"], a["id"]))["id"]

    # ------------------------------------------------------------------------------------------------ fold
    def active(self, t):
        sig = self.sig[t]
        c = self.A["c"][t]
        out = []
        cur_sess = self.sess.get(pd.Timestamp(self.day[t]), 0)
        for a in self.atoms:
            if a["born"] > t or a["seg"] != self.segs[t]:
                continue
            if a["src"] == "k":
                if a["until"] <= t:
                    continue                                                       # फक्त सगळ्यात नवा PD* / PW*
            else:
                d = self.degree(a, t)
                st = self.state.get(a["id"])
                age = cur_sess - self.sess.get(pd.Timestamp(self.day[a["born"]]), 0)
                if d == 1 and age > int(self.s["prune_d1_sessions"]):
                    continue
                if d >= 2 and ((st is not None and st["status"] == "dead") or
                               (np.isfinite(sig) and min(abs(c - a["top"]), abs(c - a["bottom"])) > float(self.s["prune_far"]) * sig)):
                    continue
            out.append(a)
        return out

    def run(self, snap_bars=()):
        snap_bars = set(snap_bars)
        key = None
        groups = []
        for t in range(self.n):
            sig = self.sig[t]
            if not np.isfinite(sig):
                continue
            act = self.active(t)
            k2 = (tuple(a["id"] for a in act), round(float(sig), 6))
            if k2 != key:
                key = k2
                new = self.cluster(act, sig)
                ids = self.assign_ids(new, t)
                for g, i in zip(new, ids):
                    if i not in self.state:
                        self.state[i] = self._new_state(g, t)
                        self.state[i]["id"] = i
                        self.events.append({"bar": t, "type": "जन्म", "id": i})
                    for a in g:
                        self.owner[a["id"]] = i
                groups = list(zip(ids, new))
            for i, g in groups:
                self._step(self.state[i], g, t)
            if t in snap_bars:
                self.snap[t] = self.snapshot(groups, t)
        return self

    def assign_ids(self, groups, t):
        """Id वंश: प्रत्येक जुन्या zone चं "घर" = ज्या गटात त्याचा मूळ atom (atom id = zone id) आहे; मूळ atom pruning ने गेला ⇒ त्याचे
        सगळ्यात जास्त जुने सदस्य असलेला गट. गटाला त्याच्या घरातल्या zones पैकी सगळ्यात जुना id (merge ⇒ जुना id; split ⇒ मूळ pivot चा
        भाग); बाकी ⇒ merge नोंद. घर नसलेला गट ⇒ नवा id (सगळ्यात जुना pivot). प्रत्येक बदल lineage मध्ये."""
        def age(z):
            return (self.state[z]["born"], z)
        mem = [{a["id"] for a in g} for g in groups]
        parts = {}
        for k, g in enumerate(groups):
            for a in g:
                z = self.owner.get(a["id"])
                if z in self.state:
                    parts.setdefault(z, {}).setdefault(k, []).append(a)
        home = {}
        for z, by in parts.items():
            f = [k for k in by if z in mem[k]]
            home[z] = f[0] if f else min(by, key=lambda k: (-len(by[k]), min(x["born"] for x in by[k]), k))
        ids, taken = [None] * len(groups), set()
        for k in range(len(groups)):
            hs = sorted([z for z in home if home[z] == k], key=age)
            if hs:
                ids[k] = hs[0]
                taken.add(hs[0])
                if hs[0] not in mem[k] and not self.state[hs[0]].get("inherited"):
                    self.state[hs[0]]["inherited"] = True                         # एकदाच नोंद (प्रत्येक recluster ला नाही)
                    self._lin(hs[0], t, "वारसा (मूळ pivot pruning)", members=sorted(mem[k]))
                for z in hs[1:]:
                    self.events.append({"bar": t, "type": "merge", "id": hs[0], "from": z})
                    self._lin(hs[0], t, "merge", src=z)
        for k, g in enumerate(groups):
            if ids[k] is None:
                i = self.gid(g)
                if i in taken or i in self.state:
                    i = f"{i}~{t}"
                ids[k] = i
                taken.add(i)
        for z, by in parts.items():
            into = sorted({ids[k] for k in by})
            if len(into) > 1:
                self.events.append({"bar": t, "type": "split", "id": z, "into": into})
                self._lin(z, t, "split", into=into)
        return ids

    def _lin(self, z, t, what, **kw):
        if z in self.state:
            self.state[z].setdefault("lineage", []).append({"bar": t, "what": what, **kw})

    def _new_state(self, g, t):
        a = min((x for x in g if x["src"] == "a"), key=lambda x: x["born"], default=g[0])
        return {"id": self.gid(g), "role": a["role"], "born": t, "left": False, "in_visit": False, "visits": 0, "visit_bar": None,
                "react": [], "pending_react": None, "status": "active", "pend": None, "flip_bar": None, "breaks": [],
                "sweeps": [], "pend_sweep": None, "accept_at": None, "acc_n": 0, "retest": None, "breaker": False,
                "last_reaction": None, "spring": None, "deep": [], "visit_ext": None}

    def band(self, g):
        return max(a["top"] for a in g), min(a["bottom"] for a in g)

    def _step(self, z, g, t):
        A, s = self.A, self.s
        h, l, c = A["h"][t], A["l"][t], A["c"][t]
        sig = self.sig[t]
        top, bot = self.band(g)
        out = 1 if z["role"] == SELLER else -1                                   # भूमिकेविरुद्ध (break) दिशा
        edge = top if out > 0 else bot
        if z["status"] == "dead":
            return
        touch = h >= bot and l <= top
        # pending react: 12 bars / पुढची भेट
        pr = z["pending_react"]
        if pr is not None:
            far = (bot - l) if out > 0 else (h - top)
            if far >= float(s["reaction"]) * sig:
                z["react"].append(1)
                z["last_reaction"] = t
                z["pending_react"] = None
                if z["flip_bar"] is not None and z["retest"] is None:
                    z["retest"] = {"bar": pr, "shallow": bool(z.get("visit_shallow"))}
            elif t - pr > int(s["reaction_bars"]):
                z["react"].append(-1)
                z["pending_react"] = None
        if not z["left"]:
            if not touch:
                z["left"] = True
        elif touch and not z["in_visit"]:
            if z["pending_react"] is not None:
                z["react"].append(-1)
                z["pending_react"] = None
            z["in_visit"], z["visits"], z["visit_bar"] = True, z["visits"] + 1, t
            z["visit_ext"] = h if out > 0 else l
            z["visit_shallow"] = (h <= (top + bot) / 2) if out > 0 else (l >= (top + bot) / 2)
        elif touch and z["in_visit"]:
            z["visit_ext"] = max(z["visit_ext"], h) if out > 0 else min(z["visit_ext"], l)
        elif not touch and z["in_visit"]:
            z["in_visit"] = False
            z["pending_react"] = z["visit_bar"]
            self._spring(z, t)
        # sweep (wick पलीकडे, close आत)
        wick = (h - top) if out > 0 else (bot - l)
        inside = (c <= top) if out > 0 else (c >= bot)
        if wick > 0 and z["left"]:
            if inside:
                self._sweep(z, t, wick, sig, t)
            else:
                z["pend_sweep"] = (t, wick)
        elif z["pend_sweep"] is not None:
            t0, w0 = z["pend_sweep"]
            if inside and t - t0 <= int(s["sweep_close_bars"]):
                self._sweep(z, t0, w0, sig, t)
                z["pend_sweep"] = None
            elif t - t0 > int(s["sweep_close_bars"]):
                z["pend_sweep"] = None
        for sw in z["sweeps"]:
            if sw["reclaim"] is None and t - sw["seen"] <= int(s["reclaim_bars"]) and t > sw["bar"]:
                if (c < sw["mid"]) if out > 0 else (c > sw["mid"]):
                    sw["reclaim"] = t
        # accept
        if (c - edge) * out >= float(s["accept_sigma"]) * sig:
            z["acc_n"] += 1
            if z["acc_n"] >= int(s["accept_closes"]) and z["accept_at"] is None:
                z["accept_at"] = t
                self.events.append({"bar": t, "type": "accept", "id": z["id"]})
        else:
            z["acc_n"] = 0
        # pending ⇒ real break ⇒ flip ⇒ मेला
        beyond = (c - edge) * out > 0
        if beyond and z["pend"] is None:
            z["pend"] = t
        side = "above" if out > 0 else "below"
        if z["pend"] is not None:
            rb = BR.first_real_break(self.m15, z["pend"], edge, side, self.es, mr=self.mr, end=t, retest_fn=None)
            if rb is not None and rb <= t:
                self._broken(z, t, rb)
            elif not beyond and (c - edge) * out <= 0 and t > z["pend"] + int(self.es["break_no_reclaim_bars"]):
                z["pend"] = None

    def _sweep(self, z, bar, wick, sig, seen):
        s = self.s
        A = self.A
        deep = wick > float(s["sweep_hi"]) * sig
        if wick < float(s["sweep_lo"]) * sig:
            return
        rec = {"bar": bar, "seen": seen, "deep": deep, "mid": (A["h"][bar] + A["l"][bar]) / 2, "ext": A["h"][bar] if z["role"] == SELLER
               else A["l"][bar], "vol": self.lg["vol"][bar], "reclaim": None}
        if any(x["bar"] == bar for x in z["sweeps"]):
            return
        z["sweeps"].append(rec)
        self.events.append({"bar": bar, "type": "deep_sweep" if deep else "zone_sweep", "id": z["id"]})

    def _spring(self, z, t):
        """sweep नंतरच्या भेटीचं टोक sweep टोकापलीकडे नाही आणि volume कमी ⇒ spring test."""
        if not z["sweeps"]:
            return
        sw = z["sweeps"][-1]
        if z["visit_bar"] is None or z["visit_bar"] <= sw["bar"] or z["spring"] is not None:
            return
        out = 1 if z["role"] == SELLER else -1
        vol = self.lg["vol"]
        vv = np.nanmax(vol[z["visit_bar"]:t]) if np.isfinite(vol[z["visit_bar"]:t]).any() else np.nan
        held = (z["visit_ext"] - sw["ext"]) * out <= 0
        z["spring"] = {"bar": t, "ok": bool(held and np.isfinite(vv) and np.isfinite(sw["vol"]) and vv < sw["vol"]),
                       "vol_na": not (np.isfinite(vv) and np.isfinite(sw["vol"]))}

    def _broken(self, z, t, rb):
        out = 1 if z["role"] == SELLER else -1
        z["breaks"].append(rb)
        if z["flip_bar"] is None:
            lo = max(rb - int(self.s["breaker_bars"]), 0)
            sw = any(lo <= x["bar"] <= rb for x in z["sweeps"])
            disp = any(LF.displacement(self.A, self.rr, j, out, self.lg["settings"]) for j in range(lo, rb + 1))
            z.update(status="flipped", flip_bar=t, role=BUYER if z["role"] == SELLER else SELLER, pend=None, acc_n=0,
                     breaker=bool(sw and disp), left=False, in_visit=False, pending_react=None, accept_at=None)
            self.events.append({"bar": t, "type": "flip", "id": z["id"], "breaker": z["breaker"]})
        else:
            z.update(status="dead", pend=None)
            self.events.append({"bar": t, "type": "मेला", "id": z["id"]})

    # ------------------------------------------------------------------------------------------------ snapshot + गुण
    def snapshot(self, groups, t):
        out = []
        for i, g in groups:
            z = self.state[i]
            top, bot = self.band(g)
            fl = self.flags(g, t, i)
            out.append({"id": i, "top": round(top, 2), "bottom": round(bot, 2), "role": z["role"], "status": z["status"],
                        "pending": z["pend"] is not None, "accept": z["accept_at"] is not None, "flags": fl,
                        "degree": max((self.degree(a, t) for a in g if a["src"] == "a"), default=0),
                        "members": [a["id"] for a in g], "pivot_bar": min((a["pivot"].bar for a in g if a["src"] == "a"), default=None),
                        "k": [a["kname"] for a in g if a["src"] == "k"], "visits": z["visits"],
                        "touch_score": self.touch_score(z), "sweeps": [{"bar": x["bar"], "deep": x["deep"], "reclaim": x["reclaim"]}
                                                                         for x in z["sweeps"]][-3:],
                        "breaker": z["breaker"], "flip_bar": z["flip_bar"], "retest": z["retest"],
                        "spring": None if z["spring"] is None else dict(z["spring"]),
                        "sweeps_all": [{"bar": x["bar"], "seen": x["seen"], "deep": x["deep"], "reclaim": x["reclaim"]} for x in z["sweeps"]],
                        "age": self.age(z, g, t),                            # t ची गोठलेली प्रत (k_area नंतरचं state वाचत नाही)
                        "lineage": list(z.get("lineage", []))[-3:]})
        for zj in out:
            zj["score"], zj["parts"] = self.score(zj, t)
            zj["stars"] = 1 if zj["score"] < float(self.s["star2"]) else (2 if zj["score"] < float(self.s["star3"]) else 3)
        return out

    def flags(self, g, t, i=None):
        c = [x for x in (self.flag_c(a, t) for a in g if a["src"] == "a") if x]
        d = [x for x in (self.flag_d(a, t) for a in g if a["src"] == "a") if x]
        e = [x for x in (self.flag_e(a, t) for a in g if a["src"] == "a") if x]
        z = self.state[self.gid(g) if i is None else i]
        if z["accept_at"] is not None or z["breaks"]:
            e = []
        return {"c": max(c, key=lambda x: x["q"]) if c else None, "d": d[0] if d else None, "e": e[0] if e else None}

    @staticmethod
    def touch_score(z):
        return int(sum(z["react"]) + (1 if z["visits"] == 0 else 0))

    def age(self, z, g, t):
        ref = z["last_reaction"] if z["last_reaction"] is not None else z["born"]
        return self.sess.get(pd.Timestamp(self.day[t]), 0) - self.sess.get(pd.Timestamp(self.day[ref]), 0)

    def score(self, zj, t):
        s = self.s
        z = self.state[zj["id"]]
        fl = zj["flags"]
        last_sw = z["sweeps"][-1] if z["sweeps"] else None
        recent = last_sw is not None and z["visit_bar"] is not None and last_sw["bar"] >= z["visit_bar"] and last_sw["reclaim"]
        parts = {"liq": 1.0 if (fl["e"] and recent) else (0.5 if fl["e"] else 0.0),
                 "origin": fl["c"]["q"] if fl["c"] else 0.0,
                 "degree": {0: None, 1: 0.33, 2: 0.67}.get(zj["degree"], 1.0),
                 "react": 0.0 if zj["touch_score"] < 0 else min(sum(1 for r in z["react"] if r > 0), 3) / 3.0,
                 "flip": (1.0 if z["breaker"] else 0.7) if z["flip_bar"] is not None else None,
                 "k": 1.0 if zj["k"] else None,
                 "age": float(np.interp(zj["age"], [s["age_full"], s["age_half"]], [1.0, 0.5]))}
        w = {"liq": s["w_liq"], "origin": s["w_origin"], "degree": s["w_degree"], "react": s["w_react"], "flip": s["w_flip"],
             "k": s["w_k"], "age": s["w_age"]}
        num = sum(w[k] * v for k, v in parts.items() if v is not None)
        den = sum(w[k] for k, v in parts.items() if v is not None)
        return (round(num / den, 3) if den else 0.0), parts


# ---------------------------------------------------------------------------------------------------- trade बाजू + K area
def trade_side(zs, st_ik, st1, st2):
    """I खाली ⇒ seller (वर); I वर ⇒ buyer (खाली); D1 / D2 RANGE ⇒ range_mode (दोन्ही कडा, d flag). I नाही ⇒ NA."""
    rng = (st1 and st1["trend"] == "RANGE") or (st2 and st2["trend"] == "RANGE")
    I = st_ik.get("I")
    if I is None:
        return ("range_mode" if rng else None)
    return SELLER if I["dir"] < 0 else BUYER


def k_area(Z, zones, ik_state, t, k_last_start, htf_trend=None, ruler=()):
    """थर 4 §7: K च्या शेवटच्या leg ची candle (k_last_start..t) `self` नसलेल्या trade-बाजूच्या zone ला ⇒ हो / हो (sweep) / हो (pending);
    accept ⇒ नाही. रिटर्न dict (ans, zone, कारण)."""
    I = ik_state.get("I")
    if I is None or not ik_state.get("K"):
        return {"ans": "NA", "why": "I / K नाही"}
    side = SELLER if I["dir"] < 0 else BUYER
    i_end_bar = ik_state.get("i_end_bar")
    A = Z.A
    best = None
    for zj in zones:
        if zj["role"] != side or zj["status"] == "dead":
            continue
        if zj["pivot_bar"] is not None and i_end_bar is not None and zj["pivot_bar"] > i_end_bar:
            continue                                                               # self (K च्या आत जन्मलेला)
        if zj["accept"]:
            cand = ("नाही", "accept")
        else:
            hit = [j for j in range(k_last_start, t + 1) if A["h"][j] >= zj["bottom"] and A["l"][j] <= zj["top"]]
            sw = [x for x in zj["sweeps_all"] if k_last_start <= x["bar"] and x["seen"] <= t]
            if zj["pending"]:
                cand = ("हो (pending)", "close पलीकडे, accept / real break नाही")
            elif sw:
                cand = ("हो (sweep)", "zone_sweep" + (" + reclaim" if sw[-1]["reclaim"] else ""))
            elif hit:
                cand = ("हो", "स्पर्श")
            else:
                continue
        r = {"ans": cand[0], "why": cand[1], "zone": zj["id"], "stars": zj["stars"], "band": (zj["bottom"], zj["top"]),
             "spring": (zj["spring"] or {}).get("ok"), "htf_against": bool(htf_trend and ((htf_trend == "UP" and side == SELLER) or
                                                                                       (htf_trend == "DOWN" and side == BUYER)))}
        rank = {"हो (sweep)": 3, "हो": 2, "हो (pending)": 1, "नाही": 0}[cand[0]]
        if best is None or (rank, zj["stars"]) > best[0]:
            best = ((rank, zj["stars"]), r)
    if best is None:
        return {"ans": "नाही", "why": "trade-बाजूच्या zone ला स्पर्श नाही"}
    return best[1]


def confluence(price, sigma, s, extras):
    """± 0.25 σ: round, gap, Fib, C = A, pattern रेघ, दुसरा zone, POC / VA. extras = [(नाव, भाव)]."""
    tol = float(s["confluence"]) * sigma
    out = []
    for r in s["rounds"]:
        q = round(price / r) * r
        if abs(price - q) <= tol:
            out.append(f"round {int(q)}")
    out += [nm for nm, v in extras if v is not None and abs(price - v) <= tol]
    return out


def fib_levels(I, s):
    o, e = I["origin"]["price"], I["end"]["price"]
    return [(f"Fib {int(f * 1000) / 10}", e - (e - o) * f) for f in s["fibs"]]


def sessions_profile(A, vol, day, sess_of, t, sigma, s):
    """शेवटची `profile_sessions` **पूर्ण** sessions (आजच्या आधीची; known_at = त्या session चा close) — प्रत्येक session मध्ये futures
    volume हवा; कमी sessions / volume नाही ⇒ None (NA; कमी sessions वर profile नाही). रिटर्न (POC, VAL, VAH)."""
    n = int(s["profile_sessions"])
    cur = pd.Timestamp(day[t])
    days = sorted({d for d in sess_of if d < cur})[-n:]
    if len(days) < n:
        return None
    bars = []
    for d in days:
        b = sess_of[d]
        if not any(np.isfinite(vol[j]) and vol[j] > 0 for j in b):
            return None
        bars += b
    return profile(A, vol, bars, sigma, s)


def profile(A, vol, bars, sigma, s):
    """Spot candle range वर futures volume समान वाटून, 0.1 σ निश्चित grid (0 पासून). रिटर्न (POC, VAL, VAH) किंवा None."""
    if sigma is None or not np.isfinite(sigma) or sigma <= 0:
        return None
    w = float(s["bin"]) * sigma
    hist = {}
    for j in bars:
        v = vol[j]
        if not np.isfinite(v) or v <= 0:
            continue
        b0, b1 = int(np.floor(A["l"][j] / w)), int(np.floor(A["h"][j] / w))
        k = b1 - b0 + 1
        for b in range(b0, b1 + 1):
            hist[b] = hist.get(b, 0.0) + v / k
    if not hist:
        return None
    ks = sorted(hist)
    poc = max(ks, key=lambda b: (hist[b], -b))
    tot, acc = sum(hist.values()), hist[poc]
    lo = hi = poc
    while acc < float(s["va"]) * tot:
        up, dn = hist.get(hi + 1, -1), hist.get(lo - 1, -1)
        if up < 0 and dn < 0:
            break
        if up >= dn:
            hi += 1
            acc += max(up, 0)
        else:
            lo -= 1
            acc += max(dn, 0)
    return (poc + 0.5) * w, lo * w, (hi + 1) * w
