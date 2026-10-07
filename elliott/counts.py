"""
elliott/counts.py — E1b: count tree (spec §4 degree-aware, §7 invalidation प्रसार, §12 per-bar loop पायऱ्या 2–5)
--------------------------------------------------------------------------------------------------------------
🎓 दिलेल्या वेळी `t` (फक्त तेव्हा माहीत असलेला डेटा):
  1. प्रत्येक degree: confirmed pivots (known_at ≤ t) + tentative (चालू wave). मागच्या count_lookback_pivots पैकी प्रत्येक origin
     आणि प्रत्येक pattern साठी patterns.build (नियम R1–R10 ने छाटणी, guideline score).
  2. Validity: count च्या hard_inv पैकी कुठलाही चालू wave सुरू झाल्यापासून count_inv_basis (real break / wick) ने तुटला ⇒ count मेला
     (R11). Break confirm index ठरवायला फक्त confirm bar पर्यंतचे bars लागतात ⇒ causal.
  3. Cross-degree (वरून खाली): degree d चा count तेव्हाच कायदेशीर जेव्हा तो d+1 च्या कुठल्यातरी count च्या **चालू wave** चा
     subdivision आहे (origin = त्या wave ची सुरुवात, दिशा तीच, pattern-कुटुंब CHILD_FAMILY नुसार; उदा. triangle wave 2 नाही — R5).
     joint score = score × parent चा joint score. strict ⇒ parent नसलेला count वगळ; penalty ⇒ × penalty.
     मोठ्या degree कडे डेटा आहे पण एकही valid count नाही ⇒ strict मध्ये लहान degree ला सुद्धा count नाही (gray).
     Pattern ची शेवटची wave (5/C/E/Y) चालू ⇒ ती संपल्यावरची दिशा parent ठरवतो (spec S7: "C संपला पण parent म्हणतो W" ⇒ entry नाही).
  4. Vote (valid counts = beam वर: पुढची **motive** wave वर/खाली — joint score चा वाटा), beam (beam_k), preferred (hysteresis —
     त्याच "वंशाचा" count टिकला असेल तर), invalidation log (break confirm झाल्याच्या वेळेसह).
Higher degrees "evolve forward": count दर bar ला pivots वरून पुन्हा मांडला जातो, पण preferred फक्त hysteresis ओलांडल्यावर बदलतो.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import swings as W
from .breaks import BreakCache, frame_index_at
from .patterns import CHILD_FAMILY, LABELS, LAST_WAVE, POSITION_RESTRICTED, build

PATTERNS = ("impulse", "lead_diag", "end_diag", "zigzag", "flat", "triangle", "wxy")


@dataclass
class DegreeView:
    degree: int
    nodes: list                       # joint score क्रमाने (beam)
    preferred: object = None
    vote_up: float = float("nan")     # joint score चा वाटा: पुढची motive wave वर
    vote_down: float = float("nan")   # … खाली;  उरलेला = पुढची wave corrective (trade नाही)
    gray: bool = True
    parent_missing: bool = False


@dataclass
class Snapshot:
    t: object
    degrees: dict                     # degree → DegreeView
    invalidated: list = field(default_factory=list)


def subcounts(pts, lower, lower_ts=None):
    """प्रत्येक leg (pts[i]→pts[i+1]) मध्ये lower-degree चे किती sub-legs (आतले pivots + 1). Lower डेटा leg च्या सुरुवातीपूर्वीपासून
    नसेल ⇒ None. lower_ts = lower pivots चे ts (np.datetime64, वाढत्या क्रमाने) — दिल्यास bisect ने जलद."""
    if lower is None:
        return None
    if not lower:
        return [None] * (len(pts) - 1)
    if lower_ts is None:
        lower_ts = np.array([p.ts for p in lower], dtype="datetime64[ns]")
    first = lower_ts[0]
    out = []
    for a, b in zip(pts, pts[1:]):
        ta, tb = np.datetime64(a.ts, "ns"), np.datetime64(b.ts, "ns")
        if first >= ta:
            out.append(None)
            continue
        out.append(int(np.searchsorted(lower_ts, tb, "left") - np.searchsorted(lower_ts, ta, "right")) + 1)
    return out


def _lineage(n):
    """एकाच count चा "वंश": degree, pattern, दिशा, origin — pivot confirm झाल्यावर key बदलते पण वंश तोच."""
    return (n.degree, n.pattern, n.direction, n.points[0].ts)


class CountEngine:
    """md = swings.multi_degree(...) (पूर्ण उपलब्ध डेटा); snapshot(t) फक्त t पर्यंत माहीत असलेलं वापरतो."""

    def __init__(self, md, s, confirm=None):
        """confirm = ConfirmTF (Scanner पुरवतो) ⇒ count invalidation `break_confirm_tf` वर (trade exit सारखं); None ⇒ degree frame."""
        self.md, self.s, self.confirm = md, s, confirm
        self.degrees = sorted(md)
        self.cache = {d: BreakCache(md[d]["frame"], s) for d in self.degrees}
        self.atr = {d: W.atr(md[d]["frame"], s["atr_len"]) for d in self.degrees}
        self.prev = None
        self.log = []
        self._why = {}                  # (degree, pattern, origin ts) → पूर्ण-wave नियम (F5 log)
        # confirmed pivots confirm क्रमाने ⇒ confirmed_at वाढतं; "t ला माहीत" = prefix (bisect)
        self._conf_at = {d: np.array([p.confirmed_at for p in md[d]["confirmed"]], dtype="datetime64[ns]") for d in self.degrees}
        self._piv_ts = {d: np.array([p.ts for p in md[d]["confirmed"]], dtype="datetime64[ns]") for d in self.degrees}

    def known(self, d, t):
        """t ला माहीत असलेले confirmed pivots (confirmed_at ≤ t) — prefix."""
        k = int(np.searchsorted(self._conf_at[d], np.datetime64(pd.Timestamp(t), "ns"), "right"))
        return self.md[d]["confirmed"][:k], k

    # ------------------------------------------------------------------------------------------------------------
    def _known(self, d, t):
        fr = self.md[d]["frame"]
        t_idx = frame_index_at(fr, t)
        conf, _ = self.known(d, t)
        tent = W.tentative_pivot(fr, conf, d, upto=t_idx, tf=self.md[d]["tf"]) if t_idx >= 0 else None
        return fr, t_idx, conf, tent

    def _same_pivot(self, a, b):
        tol = self.s["cross_degree_tol_bars"]
        if a.tf == b.tf:
            return abs(a.bar_idx - b.bar_idx) <= tol
        step = max(W.TF_MIN.get(a.tf, 5), W.TF_MIN.get(b.tf, 5))
        return abs((a.ts - b.ts).total_seconds()) <= tol * step * 60

    def _completed_break(self, d, pts, fr):
        """F5: पूर्ण waves चे नियम (R1/R6/R9) count_inv_basis वर — pivot a च्या level चा खरा break pivot a नंतर ते pivot b
        confirm होईपर्यंत झाला का. ConfirmTF असेल तर count/trade सारखाच TF."""
        def broke(level, side, a, b):
            ws, pb = pts[b - 1], pts[b]                               # review H1: violating wave च्या सुरुवातीपासून — _valid सारखंच
            end_idx = pb.confirmed_idx if pb.confirmed_idx is not None else pb.bar_idx
            if self.confirm is not None:
                t_end = fr["bar_end"].iloc[min(end_idx, len(fr) - 1)]
                return self.confirm.broken(d, ws.ts, level, side, t_end)
            return self.cache[d].confirm_index(ws.bar_idx + 1, level, side, end_idx) is not None
        return broke

    def _valid(self, d, node, t_idx, t=None):
        if self.confirm is not None and t is not None:
            st = node.points[-1].ts
            return not any(self.confirm.broken(d, st, lvl, side, t) for lvl, side, _ in node.invs)
        start = node.points[-1].bar_idx + 1
        return not any(self.cache[d].broken_by(start, lvl, side, t_idx) for lvl, side, _ in node.invs)

    def degree_nodes(self, d, t, lower_conf=None, parents=None, lower_ts=None):
        s = self.s
        fr, t_idx, conf, tent = self._known(d, t)
        if t_idx < 0 or tent is None or not conf:
            return [], t_idx, False
        atr_now = float(self.atr[d][t_idx]) if np.isfinite(self.atr[d][t_idx]) else None
        origins = set(range(max(0, len(conf) - s["count_lookback_pivots"]), len(conf)))
        for p in parents or []:                       # parent च्या चालू wave ची सुरुवात lookback बाहेर असली तरी origin म्हणून
            st = p.points[-1]
            for i in range(len(conf) - 1, -1, -1):
                if self._same_pivot(conf[i], st):
                    origins.add(i)
                elif conf[i].ts < st.ts:
                    break                                                   # pivots ts क्रमाने ⇒ यापुढचे आणखी आधीचे, जुळणार नाहीत
        out = []
        for o in sorted(origins):
            pts = conf[o:]
            subs = subcounts(pts, lower_conf, lower_ts)
            for pat in PATTERNS:
                if len(pts) - 1 >= len(LABELS[pat]):
                    continue
                why = []
                n = build(d, pat, pts, tent, s, subs, atr_now, t_idx, atr_arr=self.atr[d], mr_arr=self.cache[d].mr,
                          broke=self._completed_break(d, pts, fr), why=why)
                if n is None and why:
                    if len(self._why) > 50_000:
                        self._why.clear()                                   # फक्त log साठी — मर्यादा
                    self._why[(d, pat, pts[0].ts)] = why[0]
                if n is not None and self._valid(d, n, t_idx, t):
                    out.append(n)
        return out, t_idx, True

    # ------------------------------------------------------------------------------------------------------------
    def _origin_match(self, child, parent):
        return self._same_pivot(child.points[0], parent.points[-1])

    def snapshot(self, t):
        s = self.s
        views, parents, parent_has_data = {}, None, True
        for d in sorted(self.degrees, reverse=True):
            if d - 1 in self.md:
                lower, k = self.known(d - 1, t)
                lower_ts = self._piv_ts[d - 1][:k]
            else:
                lower, lower_ts = None, None
            nodes, _, has_data = self.degree_nodes(d, t, lower, parents, lower_ts)
            parent_missing = parents is not None and not parent_has_data     # वरच्या degree कडे अजून डेटाच नाही
            keep = []
            for n in nodes:
                if parents is None or parent_missing:                       # स्थान तपासता येत नाही ⇒ स्थान-बंधित patterns ला penalty
                    n.joint_score = n.score * (s["orphan_position_penalty"] if n.pattern in POSITION_RESTRICTED else 1.0)
                    keep.append(n)
                    continue
                ok = [p for p in parents if self._origin_match(n, p) and n.direction == p.current_dir
                      and n.pattern in CHILD_FAMILY.get((p.pattern, p.current_wave), ())]
                if ok:
                    best = max(ok, key=lambda p: p.joint_score)
                    n.joint_score, n.parent_key = n.score * best.joint_score, best.key
                    if n.current_wave == LAST_WAVE[n.pattern] and n.pattern != "end_diag" and n.subtype != "tri_exp":
                        n.next_motive_dir = best.next_motive_dir                 # pattern संपल्यावरची दिशा parent ची
                        # (ending diagonal ⇒ S11: आधी उलटा leg + retrace; expanding triangle ⇒ entry नाही — म्हणून 0 टिकतो)
                    keep.append(n)
                elif s["cross_degree_mode"] == "penalty":
                    n.joint_score = n.score * s["cross_degree_penalty"]
                    keep.append(n)
            keep.sort(key=lambda n: (-n.joint_score, n.key[3], n.pattern))
            beam = keep[:s["beam_k"]]
            # spec §4 vote "सर्व valid counts" वर; §11 नुसार beam_k = "प्रति degree जास्तीत जास्त valid counts" ⇒ valid संच = beam.
            # (सगळ्या कच्च्या उमेदवारांवर vote घेतल्यास डझनभर अर्ध-counts मुळे vote विरळ होतो — D3 वर स्पष्ट vote 27% → 1.4%.)
            tot = sum(n.joint_score for n in beam)
            vu = sum(n.joint_score for n in beam if n.next_motive_dir > 0) / tot if tot > 0 else float("nan")
            vd = sum(n.joint_score for n in beam if n.next_motive_dir < 0) / tot if tot > 0 else float("nan")
            gray = not (np.isfinite(vu) and max(vu, vd) >= s["vote_min"] and max(vu, vd) > 0.5)
            views[d] = DegreeView(d, beam, beam[0] if beam else None, vu, vd, gray, parent_missing)
            parents, parent_has_data = beam, has_data
        snap = Snapshot(t, views)
        self._hysteresis_and_log(snap)
        self.prev = snap
        return snap

    def _hysteresis_and_log(self, snap):
        if self.prev is None:
            return
        for d, v in snap.degrees.items():
            pv = self.prev.degrees.get(d)
            if pv is None:
                continue
            cur_keys = {n.key: n for n in v.nodes}
            if pv.preferred is not None and v.preferred is not None:
                lin = _lineage(pv.preferred)                                # तोच count, किंवा pivot confirm होऊन पुढे सरकलेला वंशज
                same = [n for n in v.nodes if _lineage(n) == lin]
                if same:
                    kept = max(same, key=lambda n: n.joint_score)
                    if v.preferred.joint_score - kept.joint_score < self.s["hysteresis_margin"]:
                        v.preferred = kept
            fr = self.md[d]["frame"]
            t_idx = frame_index_at(fr, snap.t)
            for n in pv.nodes:
                if n.key in cur_keys:
                    continue
                if self.confirm is not None:
                    st = n.points[-1].ts
                    broken = [(lvl, rule, c[1]) for lvl, side, rule in n.invs
                              for c in [self.confirm.confirm(d, st, lvl, side, snap.t)] if c is not None]
                else:
                    start = n.points[-1].bar_idx + 1
                    broken = [(lvl, rule, fr["bar_end"].iloc[c]) for lvl, side, rule in n.invs
                              for c in [self.cache[d].confirm_index(start, lvl, side, t_idx)] if c is not None]
                if broken:
                    lvl, rule, c = min(broken, key=lambda x: x[2])
                    e = {"t": snap.t, "break_at": c, "degree": d, "pattern": n.pattern,
                         "current_wave": n.current_wave, "level": lvl, "rule": rule, "origin": n.points[0].ts, "key": n.key}
                else:                                                       # F5: पूर्ण-wave नियमाने गायब ⇒ कारणासह log
                    rule = self._why.pop((d, n.pattern, n.points[0].ts), None)
                    if rule is None:
                        continue                                            # beam/hysteresis मुळे बाहेर — invalidation नाही
                    e = {"t": snap.t, "break_at": None, "degree": d, "pattern": n.pattern, "current_wave": n.current_wave,
                         "level": None, "rule": f"{rule}_completed", "origin": n.points[0].ts, "key": n.key}
                snap.invalidated.append(e)
                self.log.append(e)
