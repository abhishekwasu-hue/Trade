"""
elliott/patterns.py — E1b: Elliott patterns — नियम (R1–R11), guidelines (score), invalidation, पुढची दिशा
------------------------------------------------------------------------------------------------------
🎓 एका degree वरचा count = origin pivot पासून चालू वेळेपर्यंतचे legs, एका pattern च्या labels सह. शेवटचा leg (शेवटच्या confirmed
pivot पासून tentative extreme पर्यंत) **चालू wave** आहे. पूर्ण झालेल्या waves चे नियम फक्त confirmed pivots वर (tentative ban);
चालू wave चा धोका `invs` (hard invalidation levels) ने — त्यांचा break count_inv_basis (real break / wick) ने तपासला जातो.

Patterns (spec §2, §5):
  impulse (1-2-3-4-5)    R1 w2 ≯ origin; R3 w4 ≯ w1 end (wave4_overlap_strict); R2 w3 not shortest (⇒ w5 ची वरची मर्यादा)
  lead_diag / end_diag   R1; w4 ≯ w2 end (R9); w4–w1 overlap = guideline (+); स्थान (1/A वि. 5/C) cross-degree मध्ये
  zigzag (A-B-C)         R6: B ≯ A origin; B band = guideline
  flat (A-B-C)           R7: B ≥ 0.9 A; B ≤ flat_b_max_ratio × A [अनुमान]; regular/expanded
  triangle (A-B-C-D-E)   R8: C आत A end, D आत B end (barrier tolerance), E आत C end; expanding = उलट (entry नाही — E2)
  wxy (W-X-Y)            X ≯ W origin [अनुमान]
Score = (Σ guideline hits + prior) / (n + 2·prior) — EWI: "preferred = सर्वात जास्त guidelines पाळणारा".
सर्व ratios फक्त score — gate कधीच नाही (spec §3).
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

LABELS = {
    "impulse": ["1", "2", "3", "4", "5"],
    "lead_diag": ["1", "2", "3", "4", "5"],
    "end_diag": ["1", "2", "3", "4", "5"],
    "zigzag": ["A", "B", "C"],
    "flat": ["A", "B", "C"],
    "triangle": ["A", "B", "C", "D", "E"],
    "wxy": ["W", "X", "Y"],
}
MOTIVE_PATTERNS = ("impulse", "lead_diag", "end_diag")
CORRECTIVE_PATTERNS = ("zigzag", "flat", "triangle", "wxy")
# प्रत्येक wave कुठल्या प्रकारात subdivide होते (fractal नियम: trend सोबत 5, विरुद्ध 3) — cross-degree व sub-count साठी
# स्थान-बंधित patterns (R5, R9): ending diagonal फक्त 5/C, leading फक्त 1/A, triangle फक्त 4/B/X/E/Y. Parent नसेल तर स्थान तपासता
# येत नाही ⇒ (counts.py) score × orphan_position_penalty.
POSITION_RESTRICTED = ("end_diag", "lead_diag", "triangle")
CHILD_FAMILY = {
    ("impulse", "1"): MOTIVE_PATTERNS[:2], ("impulse", "3"): ("impulse",), ("impulse", "5"): ("impulse", "end_diag"),
    ("impulse", "2"): ("zigzag", "flat", "wxy"), ("impulse", "4"): CORRECTIVE_PATTERNS,          # R5: triangle wave 2 नाही
    ("lead_diag", "1"): ("impulse", "lead_diag", "zigzag"), ("lead_diag", "3"): ("impulse", "zigzag"),
    ("lead_diag", "5"): ("impulse", "zigzag"), ("lead_diag", "2"): ("zigzag", "flat", "wxy"), ("lead_diag", "4"): ("zigzag", "flat", "wxy"),
    ("zigzag", "A"): ("impulse", "lead_diag"), ("zigzag", "B"): CORRECTIVE_PATTERNS, ("zigzag", "C"): ("impulse", "end_diag"),
    ("flat", "A"): ("zigzag", "flat", "wxy"), ("flat", "B"): CORRECTIVE_PATTERNS, ("flat", "C"): ("impulse", "end_diag"),
    ("wxy", "W"): ("zigzag", "flat"), ("wxy", "X"): CORRECTIVE_PATTERNS, ("wxy", "Y"): ("zigzag", "flat", "triangle"),
}
for _w in "12345":
    CHILD_FAMILY[("end_diag", _w)] = ("zigzag", "flat", "wxy")                                  # 3-3-3-3-3
for _w in "ABCDE":
    CHILD_FAMILY[("triangle", _w)] = ("zigzag", "flat", "wxy") + (("triangle",) if _w == "E" else ())


# चालू wave संपल्यावर पुढची wave motive असेल तर तिची दिशा (pattern च्या पहिल्या wave च्या दिशेच्या पटीत), नाहीतर 0.
#   motive: 2→3, 4→5 (+d); 1/3/5 नंतर correction (0).  zigzag/flat: A→B corrective (0 — R4 A-end ban); B→C (+d);
#   C संपला ⇒ correction पूर्ण ⇒ मोठा trend पुन्हा (−d, S7).  triangle: आत entry नाही (0); E→thrust (−d, S9).
#   wxy: W→X (0); X→Y (+d, S8); Y→resumption (−d).
NEXT_KEYS = ("zigzag", "flat", "triangle", "wxy", "end_diag")
NEXT_MOTIVE = {("motive", "1"): 0, ("motive", "2"): 1, ("motive", "3"): 0, ("motive", "4"): 1, ("motive", "5"): 0,
               ("zigzag", "A"): 0, ("zigzag", "B"): 1, ("zigzag", "C"): -1,
               ("flat", "A"): 0, ("flat", "B"): 1, ("flat", "C"): -1,
               ("triangle", "A"): 0, ("triangle", "B"): 0, ("triangle", "C"): 0, ("triangle", "D"): 0, ("triangle", "E"): -1,
               ("wxy", "W"): 0, ("wxy", "X"): 1, ("wxy", "Y"): -1,
               # ending diagonal: त्याच्या दिशेने pullback entry नाही (spec §5 निषिद्ध #5); waves 3/5 सुद्धा 3-wave
               ("end_diag", "1"): 0, ("end_diag", "2"): 0, ("end_diag", "3"): 0, ("end_diag", "4"): 0, ("end_diag", "5"): 0}
LAST_WAVE = {p: LABELS[p][-1] for p in LABELS}            # शेवटची wave संपली ⇒ पुढची दिशा parent ठरवतो (counts.py)


@dataclass
class CountNode:
    degree: int
    pattern: str                 # impulse | lead_diag | end_diag | zigzag | flat | triangle | wxy
    subtype: str                 # flat_reg/flat_exp, tri_contr/tri_barrier/tri_exp, किंवा pattern
    direction: int               # पहिल्या wave ची दिशा (+1 वर / −1 खाली)
    points: list                 # origin + confirmed pivots (Pivot) — completed waves चे टोक
    current_wave: str            # चालू wave चा label
    current_dir: int             # चालू wave ची दिशा
    next_expected: str           # "up" | "down" — चालू wave संपल्यावरची दिशा
    next_motive_dir: int = 0     # चालू wave संपल्यावर पुढची wave **motive** असेल तर तिची दिशा (+1/−1), नाहीतर 0 (trade नाही)
    invs: List[Tuple[float, str, str]] = field(default_factory=list)   # (level, side below/above, rule)
    guideline_hits: dict = field(default_factory=dict)
    time_flags: dict = field(default_factory=dict)
    score: float = 0.0
    joint_score: float = 0.0
    parent_key: Optional[tuple] = None
    tentative: object = None     # चालू wave चा extreme (Pivot, status tentative) — फक्त चालू wave साठी

    @property
    def key(self):
        return (self.degree, self.pattern, self.direction, self.points[0].ts, tuple(p.ts for p in self.points[1:]), self.current_wave)

    @property
    def labels(self):
        return LABELS[self.pattern][:len(self.points)]

    @property
    def hard_inv(self):
        return self.invs[0][0] if self.invs else None

    @property
    def inv_rule(self):
        return self.invs[0][2] if self.invs else None


# ---------------------------------------------------------------------------------------------------------------------
def _ratio_hit(x, targets, tol):
    return int(any(abs(x - t) <= tol * t for t in targets)) if x is not None and np.isfinite(x) else None


def _sub_hit(sub, motive):
    """Lower-degree sub-legs: motive wave ⇒ 5 (किंवा 9 extended); corrective ⇒ 3 (किंवा 7 complex). माहिती नसेल ⇒ None.
    sub = 1 (leg च्या आत lower pivot नाही) ⇒ आतली रचना दिसतच नाही ⇒ पुरावा नाही (None) — 3/5 चा पक्षपात टाळतो."""
    if sub is None or sub <= 1:
        return None
    return int(sub in (5, 9)) if motive else int(sub in (3, 7))


def _score(hits, prior):
    vals = [v for v in hits.values() if v is not None]
    return (sum(vals) + prior) / (len(vals) + 2 * prior) if (vals or prior) else 0.0


def build(degree, pattern, pts, tentative, s, subcounts=None, atr_now=None, now_idx=None, atr_arr=None, mr_arr=None,
          broke=None, why=None):
    """pts = [origin, confirmed pivots…] (len ≥ 1), tentative = चालू wave चा extreme (Pivot). नियम मोडले ⇒ None.
    subcounts[i] = leg i (pts[i]→pts[i+1]) चे lower-degree sub-legs (किंवा None). now_idx = चालू (शेवटचा बंद) bar —
    चालू wave ची वेळ (t(c) इ.) इथपर्यंत मोजतो. atr_arr / mr_arr दिल्यास tolerance संबंधित pivot च्या **confirm bar** वरचा
    (गोठवलेला) — त्यामुळे पूर्ण झालेल्या wave चा निर्णय/level bar-दर-bar बदलत नाही (R11: मेलेला count परत येत नाही).
    broke(level, side, from_pt, to_pt) ⇒ pivots from_pt → to_pt दरम्यान level चा खरा break झाला का (F5: पूर्ण waves ना सुद्धा
    count_inv_basis; None ⇒ wick). why (list) ⇒ नकाराचं कारण (invalidation log साठी)."""
    labels = LABELS[pattern]
    nc = len(pts) - 1                                     # पूर्ण legs
    if nc >= len(labels) or tentative is None:
        return None
    pr = [p.price for p in pts]
    d = 1 if (pr[1] - pr[0] if nc >= 1 else tentative.price - pr[0]) > 0 else -1
    allp = pr + [tentative.price]
    for i in range(len(allp) - 1):                        # legs आलटून-पालटून
        if (allp[i + 1] - allp[i]) * (d if i % 2 == 0 else -d) <= 0:
            return None
    L = [abs(allp[i + 1] - allp[i]) for i in range(len(allp) - 1)]           # शेवटचा = चालू (अपूर्ण) leg
    T = [max(1, (pts[i + 1].bar_idx if i + 1 < len(pts) else tentative.bar_idx) - pts[i].bar_idx) for i in range(len(allp) - 1)]
    subs = list(subcounts or []) + [None] * 10
    cur = labels[nc]
    cur_dir = d if nc % 2 == 0 else -d
    hits, flags, invs, subtype = {}, {}, [], pattern
    tol, prior = s["fib_tol"], s["guideline_prior"]
    below_if = (lambda up: "below" if up > 0 else "above")       # d=+1 असताना खालचा धोका "below"

    def P(i):
        return pr[i]

    def beyond(lv_i, at_i, rule):
        """पूर्ण wave: pivot at_i ने pivot lv_i चा level ओलांडला (R1/R6/R9). Equality (double bottom) ⇒ violation नाही.
        count_inv_basis = real_break ⇒ wick पलीकडे पण खरा break नाही ⇒ violation नाही (F5)."""
        if (P(at_i) - P(lv_i)) * d >= 0:
            return False
        if s["count_inv_basis"] != "wick" and broke is not None and not broke(P(lv_i), below_if(d), lv_i, at_i):
            return False                                                    # wick पलीकडे, close आत ⇒ count जिवंत
        if why is not None:
            why.append(rule)
        return True

    def frozen(arr, i, fallback):
        """pivot i च्या confirm bar वरचं मूल्य (नसेल ⇒ fallback; NaN — डेटाची सुरुवात — ⇒ 0, म्हणजे tolerance नाही)."""
        if arr is None or i >= len(pts) or pts[i].confirmed_idx is None:
            return fallback or 0.0
        v = arr[min(pts[i].confirmed_idx, len(arr) - 1)]
        return float(v) if np.isfinite(v) else 0.0

    # ---------------------------------------------------------------- motive patterns
    if pattern in MOTIVE_PATTERNS:
        diag = pattern != "impulse"
        if nc >= 2 and beyond(0, 2, "R1"):
            return None                                                     # R1
        if nc >= 3 and not diag and s["wave4_overlap_strict"] and (P(3) - P(1)) * d <= 0:
            return None                                                     # wave 3 wave 1 च्या टोकापलीकडे नाही ⇒ कुठलाही wave 4 R3 मोडेल
        if nc >= 4:
            if not diag:
                gap = (P(4) - P(1)) * d                                     # > 0 ⇒ wave 4 wave 1 च्या प्रदेशाबाहेर
                allow = 0.0 if s["wave4_overlap_strict"] else s["break_buffer_mr"] * frozen(mr_arr, 3, None)
                if gap <= 0 if s["wave4_overlap_strict"] else gap < -allow:
                    return None                                             # R3
            else:
                if beyond(2, 4, "R9"):
                    return None                                             # R9: w4 ≯ w2 end
                hits["g_diag_overlap"] = int((P(4) - P(1)) * d < 0)
                hits["g_diag_converge"] = int(L[3] < L[1] and L[2] < L[0]) if nc >= 4 else None
        if nc >= 3:
            hits["g_w3_beyond_w1"] = int((P(3) - P(1)) * d > 0)
            hits["g_w3_fib"] = _ratio_hit(L[2] / L[0], tuple(s["w3_fib_targets"]), tol)
            if not diag:
                hits["g_w3_not_short_so_far"] = int(L[2] >= L[0] * s["w3_not_short_ratio"])
        if nc >= 2:
            hits["g_w2_depth"] = int(s["w2_depth_band"][0] - tol <= L[1] / L[0] <= s["w2_depth_band"][1] + tol)
            hits["g_sim_12"] = int(min(L[0], L[1]) >= max(L[0], L[1]) * s["similarity_balance_min"]
                                  or min(T[0], T[1]) >= max(T[0], T[1]) * s["similarity_balance_min"])
        if nc >= 4:
            hits["g_w4_depth"] = int(L[3] / L[2] <= s["w4_depth_max"] + tol)
            hits["g_alternation"] = int(abs(L[1] / L[0] - L[3] / L[2]) >= s["alternation_min"] or (T[1] > T[0]) != (T[3] > T[2]))
            ok_time = T[1] > T[0] or T[3] > T[2]
            flags["impulse_time_ok"] = bool(ok_time)
            if not diag and s["impulse_time_rule"] == "filter" and not ok_time:
                return None
            if not diag and s["impulse_time_rule"] == "score":
                hits["g_time_neely"] = int(ok_time)
        for i in range(nc):
            if pattern == "lead_diag" and i % 2 == 0:                        # R9: 5-3-5-3-5 किंवा 3-3-3-3-3 — दोन्ही चालतात
                hits[f"g_sub_{labels[i]}"] = None if subs[i] is None or subs[i] <= 1 else int(subs[i] in (3, 5, 7, 9))
            else:
                hits[f"g_sub_{labels[i]}"] = _sub_hit(subs[i], (i % 2 == 0) and pattern == "impulse")
        # invalidation चालू wave नुसार
        if cur == "1":
            invs.append((P(0), below_if(d), "origin"))
        elif cur == "2":
            invs.append((P(0), below_if(d), "R1"))
        elif cur == "3":
            invs.append((P(2), below_if(d), "R1-lower"))
        elif cur == "4":
            # non-strict R3: चालू wave 4 ला सुद्धा तितकीच overlap सवलत (completed check सारखी, wave 3 च्या confirm वर गोठलेली)
            allow4 = 0.0 if (diag or s["wave4_overlap_strict"]) else s["break_buffer_mr"] * frozen(mr_arr, 3, None)
            invs.append(((P(2) if diag else P(1) - d * allow4), below_if(d), "R9" if diag else "R3"))
        elif cur == "5":
            invs.append((P(4), below_if(d), "start-of-5"))
            if L[2] < L[0]:                                                 # R2 / R9: w3 < w1 ⇒ w5 ≤ w3 (diagonals सुद्धा)
                invs.append((P(4) + d * L[2], below_if(-d), "R2"))
        # F5 review M1: पूर्ण wave चा wick पलीकडे गेला (खरा break नाही) ⇒ तो level पुढेही inv (नंतर खरा break ⇒ count मेला)
        if nc >= 2 and (P(2) - P(0)) * d < 0:
            invs.append((P(0), below_if(d), "R1"))
        if diag and nc >= 4 and (P(4) - P(2)) * d < 0:
            invs.append((P(2), below_if(d), "R9"))

    # ---------------------------------------------------------------- corrective patterns
    elif pattern in ("zigzag", "flat"):
        if nc >= 2:
            b = L[1] / L[0]
            if pattern == "zigzag":
                if beyond(0, 2, "R6"):
                    return None                                             # R6: B ≯ A origin
                lo, hi = s["zigzag_b_band"]
                hits["g_b_band"] = int(lo <= b <= hi)
            else:
                if b < s["flat_b_min_ratio"] or b > s["flat_b_max_ratio"]:
                    return None                                             # R7 + [अनुमान]
                subtype = "flat_exp" if b > s["flat_expanded_min"] else "flat_reg"
                hits["g_b_classic"] = int(b <= s["flat_b_classic_max"] + tol)
            hits["g_time_ab"] = int(T[1] >= T[0])                           # Neely QOW 509: t(B) ≥ t(A) ⇒ flat/zigzag
        hits["g_sub_A"] = _sub_hit(subs[0], pattern == "zigzag") if nc >= 1 else None
        hits["g_sub_B"] = _sub_hit(subs[1], False) if nc >= 2 else None
        if cur == "A":
            invs.append((P(0), below_if(d), "origin"))
        elif cur == "B":
            if pattern == "zigzag":
                invs.append((P(0), below_if(d), "R6"))
            else:
                invs.append((P(1) - d * s["flat_b_max_ratio"] * L[0], below_if(d), "flat_b_max"))
        elif cur == "C":
            invs.append((P(2), below_if(d), "start-of-C"))
            if pattern == "zigzag" and (P(2) - P(0)) * d < 0:                # F5 M1: B चा wick A origin पलीकडे ⇒ origin inv कायम
                invs.append((P(0), below_if(d), "R6"))
            tc = max(1, (now_idx if now_idx is not None else tentative.bar_idx) - pts[2].bar_idx)
            viol = tc > T[0] + T[1]
            flags["c_time_violation"] = bool(viol)
            if s["c_time_rule"] == "score":
                hits["g_c_time"] = int(not viol)

    elif pattern == "triangle":
        if nc >= 2 and L[1] > s["flat_b_max_ratio"] * L[0]:
            return None                                                     # B > flat_b_max × A — चालू B च्या invalidation सारखाच [अनुमान]
        if nc >= 3:
            exp = (P(3) - P(1)) * d > 0
            subtype = "tri_exp" if exp else "tri_contr"
            if not exp:
                if nc >= 4:
                    tol_d = s["barrier_d_tol_atr"] * frozen(atr_arr, 3, atr_now)   # चालू D च्या level इतकाच (C च्या confirm वर)
                    gap = (P(4) - P(2)) * d                                 # d=+1: D (low) B (low) च्या वर हवा
                    if gap < -tol_d:
                        return None                                         # R8: D आत B end (barrier tolerance)
                    if gap <= tol_d:
                        subtype = "tri_barrier"
            else:
                if nc >= 4 and (P(4) - P(2)) * d > 0:
                    return None                                             # expanding: D B च्या पलीकडे हवा
            hits["g_legs_shrink"] = int(L[2] < L[1] < L[0]) if not exp else int(L[2] > L[1] > L[0])
        if nc >= 2:
            hits["g_time_b_lt_a"] = int(T[1] < T[0])                         # Neely: t(B) < t(A) ⇒ triangle/diametric
        for i in range(nc):
            hits[f"g_sub_{labels[i]}"] = _sub_hit(subs[i], False)
        contracting = subtype != "tri_exp"
        if cur == "A":
            invs.append((P(0), below_if(d), "origin"))
        elif cur == "B":                                                    # expanding मध्ये B origin पलीकडे जातो ⇒ flat सारखी मर्यादा
            invs.append((P(1) - d * s["flat_b_max_ratio"] * L[0], below_if(d), "tri_b_max"))
        elif cur == "C":                                                    # contracting की expanding हे C संपल्यावरच ठरतं
            invs.append((P(2), below_if(d), "start-of-C"))
        elif cur == "D" and contracting:
            invs.append((P(2) - d * s["barrier_d_tol_atr"] * frozen(atr_arr, 3, atr_now), below_if(d), "R8"))
        elif cur == "E" and contracting:
            invs.append((P(3), below_if(-d), "R8"))
        elif cur in "DE":                                                   # expanding: फक्त चालू wave ची सुरुवात
            invs.append((P(nc), "below" if cur_dir > 0 else "above", "start"))

    elif pattern == "wxy":
        if nc >= 2 and beyond(0, 2, "X_W_origin"):
            return None                                                     # X ≯ W origin [अनुमान] (F5: count_inv_basis)
        if nc >= 2 and (P(2) - P(0)) * d < 0:
            invs.append((P(0), below_if(d), "X_W_origin"))
        hits["g_sub_W"] = _sub_hit(subs[0], False) if nc >= 1 else None
        if cur == "W":
            invs.append((P(0), below_if(d), "origin"))
        elif cur == "X":
            invs.append((P(0), below_if(d), "X_W_origin"))
        elif cur == "Y":
            invs.append((P(2), below_if(d), "start-of-Y"))
    else:
        raise ValueError(pattern)

    nm = NEXT_MOTIVE[(pattern if pattern in NEXT_KEYS else "motive", cur)] * d
    if subtype == "tri_exp":
        nm = 0                                                              # expanding triangle ⇒ entry नाही (R8/P8)
    node = CountNode(degree, pattern, subtype, d, list(pts), cur, cur_dir, "up" if cur_dir < 0 else "down", nm, invs, hits, flags)
    node.score = _score(hits, prior)
    node.tentative = tentative
    return node
