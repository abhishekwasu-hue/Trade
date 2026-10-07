"""
elliott/setups.py — E2: count → setup (spec §4 tiers, §5 catalogue S1–S14, §7 invalidation hierarchy, §14 Q6)
-------------------------------------------------------------------------------------------------------------
🎓 Trade degree D वर preferred count म्हणतो "चालू wave **corrective** आहे, ती संपल्यावर पुढची wave **motive** (दिशा ±1)".
तेव्हाच setup. कुठला setup हे count चा pattern / चालू wave आणि parent (D+1) ची चालू wave ठरवते:

  impulse 2        parent 3 ⇒ S2 · parent 5 ⇒ S2 (Tier C, late) · parent C (zigzag/flat) ⇒ S13 · बाकी ⇒ S1
  lead_diag 2      S10                         (lead_diag 4 ⇒ S3, Tier C — diagonal-संशय)
  impulse 4        parent 3 ⇒ S4 · parent 5 ⇒ S5 · parent C ⇒ S14 · बाकी ⇒ S3
  zigzag B         parent impulse/lead_diag 2 किंवा 4 (म्हणजे 5-wave नंतरचा पहिला A) ⇒ S12 · बाकी ⇒ S6a
  flat B           S6b
  triangle E       parent zigzag/flat B ⇒ S6c · बाकी ⇒ S9          (expanding ⇒ next_motive 0 ⇒ setup नाही)
  zigzag/flat C, wxy Y   correction पूर्ण ⇒ parent ची पुढची motive ⇒ S7 (inv = parent चा नियम-स्तर; parent B/X मध्ये ⇒ Tier B,
                   parent flat B ⇒ inv = B टोक ∓ buffer, S6b प्रमाणे)
  wxy X; किंवा कुठलाही count जो parent wxy च्या X चा शेवटचा भाग   S8 (default बंद)
  wave 2 / B ज्याचा origin = ending diagonal चं टोक (D किंवा D+1) ⇒ S11 (spec: S7/S1 ऐवजी S11 — WORK_LOG E1b)
Block (Tier "Blocked", spec §4): count नाही / parent_missing / gray / पुढची wave corrective (A-end R4, triangle/X च्या आत) /
  parent ची चालू wave B, X किंवा triangle आणि हा count त्याचा शेवटचा भाग नाही ("B च्या आत" — Kennedy "never trade gray") /
  parent ending diagonal (§5 निषिद्ध #5: diagonal च्या दिशेने pullback नाही) /
  उलट दिशेचा count ≥ alt_block_weight / htf_gate ⇒ Tier B / setup बंद.
Hard inv (त्याच degree चा नियम-स्तर, §7): count चा invs[0]; S6b ⇒ B चं टोक ∓ buffer [अनुमान]; S7 ⇒ parent चा invs[0].
C3 (c_time_rule = delay): zigzag/flat C संपला असं वाटलं पण t(c) > t(a)+t(b) ⇒ entry नाही (Terminal C — D−1 ending diagonal — सूट).
Wick inv पलीकडे पण real break नाही (§14 Q6): recount ⇒ त्याच दिशेचा पुढचा valid count (उदा. expanded flat); skip ⇒ entry नाही.
"""
from dataclasses import dataclass, field

import numpy as np

from .breaks import frame_index_at
from .patterns import LAST_WAVE, build

BASE_TIER = {"S1": "A", "S2": "A", "S3": "A", "S4": "A", "S5": "C", "S6a": "B", "S6b": "B", "S6c": "B", "S7": "A", "S8": "B",
             "S9": "A", "S10": "A", "S11": "B", "S12": "B", "S13": "B", "S14": "C"}
# zone: (settings key, "retrace" = चालू wave च्या सुरुवातीपासून मागच्या leg चा भाग | "project" = पहिल्या leg (A/W) चा भाग)
ZONE = {"S1": ("zone_fibs_w2", "retrace"), "S2": ("zone_fibs_w2", "retrace"), "S10": ("zone_fibs_w2", "retrace"),
        "S11": ("zone_fibs_w2", "retrace"), "S13": ("zone_fibs_w2", "retrace"),
        "S3": ("zone_fibs_w4", "retrace"), "S4": ("zone_fibs_w4", "retrace"), "S5": ("zone_fibs_w4", "retrace"),
        "S14": ("zone_fibs_w4", "retrace"), "S6a": ("zone_fibs_zz_b", "retrace"), "S12": ("zone_fibs_zz_b", "retrace"),
        "S6b": ("zone_fibs_flat_b", "retrace"), "S6c": ("zone_fibs_tri_e", "retrace"), "S9": ("zone_fibs_tri_e", "retrace"),
        "S8": ("zone_fibs_x", "retrace"), "S7": ("zone_fibs_c", "project")}
MOTIVE = ("impulse", "lead_diag")
ZZFLAT = ("zigzag", "flat")


@dataclass
class Setup:
    code: str
    degree: int
    tier: str
    trade_dir: int                    # +1 ⇒ bull put (पुढची motive वर), −1 ⇒ bear call
    node: object                      # count (CountNode)
    parent: object
    levels: list                      # zone चे Fib/structure levels (किंमत)
    hard_inv: float
    inv_rule: str
    wave_start: object                # चालू corrective wave ची सुरुवात (Pivot)
    extreme: object                   # चालू corrective wave चं टोक (tentative Pivot)
    vote: float
    opp_max: float
    alt_invs: list = field(default_factory=list)      # same-direction counts (≥ alt_weight_min) चे hard_inv — strike (E3)
    parent_invs: list = field(default_factory=list)   # D+1 चे invs — cascade exit (§7 प्रसार 4)
    recount: bool = False             # §14 Q6: preferred चा inv wick ने ओलांडला ⇒ दुसरा count
    inv_degree: int = None            # F4: hard_inv कोणत्या count चा (degree, त्या wave ची सुरुवात) — count engine तिथेच तपासतो
    inv_start_ts: object = None
    parent_start_ts: object = None    # parent (D+1) च्या चालू wave ची सुरुवात — parent cascade त्याच confirmation TF वर

    @property
    def direction(self):
        return "bull_put" if self.trade_dir > 0 else "bear_call"

    @property
    def inv_side(self):
        return "below" if self.trade_dir > 0 else "above"


def _find(view, key):
    if view is None or key is None:
        return None
    return next((n for n in view.nodes if n.key == key), None)


def _ends_diagonal(eng, d, t, pivot):
    """`pivot` हा degree d किंवा d+1 वरच्या (contracting) ending diagonal चा शेवट आहे का? (S11 ओळख)"""
    s = eng.s
    for dd in (d, d + 1):
        if dd not in eng.md:
            continue
        conf, _ = eng.known(dd, t)
        for i in range(len(conf) - 1, 4, -1):                                      # pivots ts क्रमाने ⇒ मागे जाताना
            if eng._same_pivot(conf[i], pivot):
                n = build(dd, "end_diag", conf[i - 5:i], conf[i], s)
                if n is None:
                    break
                p = [x.price for x in conf[i - 5:i + 1]]
                L = [abs(b - a) for a, b in zip(p, p[1:])]
                if n.guideline_hits.get("g_diag_overlap") == 1 and L[3] < L[1] and L[2] < L[0] and L[4] < L[2]:
                    return True
                break
            if conf[i].ts < pivot.ts:
                break
    return False


def _terminal_c(eng, snap, d, node):
    """Neely Terminal C सूट: **हाच** C स्वतः ending diagonal — D−1 चा preferred count end_diag आणि त्याचा origin = C ची सुरुवात.
    (D0 खाली degree नाही ⇒ सूट नाही.)"""
    lo = snap.degrees.get(d - 1)
    return (lo is not None and lo.preferred is not None and lo.preferred.pattern == "end_diag"
            and eng._same_pivot(lo.preferred.points[0], node.points[-1]))


def classify(node, parent, grandparent):
    """(code, tier) — पुढची motive दिशा node.next_motive_dir ≠ 0 असं गृहीत."""
    pat, cw = node.pattern, node.current_wave
    pp, pw = (parent.pattern, parent.current_wave) if parent is not None else (None, None)
    last = cw == LAST_WAVE.get(pat)
    if last and pp == "wxy" and pw == "X":
        code = "S8"                                                                  # X संपला ⇒ Y साठी (S7 नव्हे — §5 S7 नोंद)
    elif last and pat in ZZFLAT + ("wxy",):
        code = "S7"
    elif pat == "impulse" and cw == "2":
        code = "S13" if pp in ZZFLAT and pw == "C" else ("S2" if pp in MOTIVE and pw in ("3", "5") else "S1")
    elif pat == "lead_diag" and cw == "2":
        code = "S10"
    elif pat in MOTIVE and cw == "4":
        if pat == "lead_diag":
            code = "S3"
        elif pp in MOTIVE and pw == "3":
            code = "S4"
        elif pp in MOTIVE and pw == "5":
            code = "S5"
        elif pp in ZZFLAT and pw == "C":
            code = "S14"
        else:
            code = "S3"
    elif pat == "zigzag" and cw == "B":
        code = "S12" if pp in MOTIVE and pw in ("2", "4") else "S6a"
    elif pat == "flat" and cw == "B":
        code = "S6b"
    elif pat == "triangle" and cw == "E":
        code = "S6c" if pp in ZZFLAT and pw == "B" else "S9"
    elif pat == "wxy" and cw == "X":
        code = "S8"
    else:
        return None, None
    tier = BASE_TIER[code]
    if code == "S7" and pw == "B":
        tier = "B"                                                                   # parent चा C trade (bounded) — S6a सारखा
    if tier == "A":
        late = (pp in MOTIVE and pw == "5") if code not in ("S7", "S9") else \
            (grandparent is not None and grandparent.pattern in MOTIVE and grandparent.current_wave == "5")
        if late or pat == "lead_diag" and cw == "4":
            tier = "C"
        elif code not in ("S7", "S9") and pp in ZZFLAT + ("wxy",):
            tier = "B"                                                               # parent च्या corrective wave ची दिशा
        elif grandparent is not None and grandparent.current_dir != node.next_motive_dir:
            tier = "B"                                                               # D+2 विरुद्ध
    return code, tier


def trade_inv(node, parent, code, s, mr_now, grandparent=None):
    """(level, side, rule) — त्या setup चा hard invalidation (§5 स्तंभ, §7)."""
    nm = node.next_motive_dir
    side = "below" if nm > 0 else "above"
    if code == "S6b" or code == "S7" and parent is not None and parent.pattern == "flat" and parent.current_wave == "B":
        x = node.tentative.price                                                     # (S7 चा parent flat B ⇒ हाच B-end, S6b नियम)
        return x - nm * s["break_buffer_mr"] * mr_now, side, "B_extreme"
    if code == "S11":
        return node.points[0].price, side, "diag_end"                               # §5 S11: diagonal चं टोक
    if code == "S7":
        if parent is not None and parent.current_wave == LAST_WAVE.get(parent.pattern):
            parent = grandparent                                                     # parent सुद्धा संपतोय (उदा. wxy Y) ⇒ त्याचा parent
        return parent.invs[0] if parent is not None and parent.invs else None
    return node.invs[0] if node.invs else None


def zone_levels(node, code, s):
    key, kind = ZONE[code]
    pr = [p.price for p in node.points]
    nc = len(pr) - 1
    ref = abs(pr[1] - pr[0]) if kind == "project" else abs(pr[nc] - pr[nc - 1])
    return [pr[nc] + node.current_dir * r * ref for r in s[key]]


def _blocked_position(node, parent):
    """§5 निषिद्ध #2/#5: parent च्या B/X/triangle आत (आणि हा count त्याचा शेवटचा भाग नाही), किंवा ending diagonal च्या आत."""
    if parent is None:
        return None
    if parent.pattern == "end_diag":
        return "inside_end_diag"
    if node.current_wave != LAST_WAVE[node.pattern] and (
            parent.pattern in ZZFLAT and parent.current_wave == "B" or parent.pattern == "wxy" and parent.current_wave == "X"
            or parent.pattern == "triangle"):
        return "inside_B_X_triangle"
    return None


def _make(eng, snap, d, t, node, up, mr_now, lows, highs, t_idx):
    """एका count वरून setup: (Setup-अर्धवट tuple) किंवा कारण. pierced ⇒ "wick_beyond_inv"."""
    s = eng.s
    nm = node.next_motive_dir
    parent = _find(up, node.parent_key)
    gp = _find(snap.degrees.get(d + 2), parent.parent_key) if parent is not None else None
    why = _blocked_position(node, parent)
    if why:
        return why
    code, tier = classify(node, parent, gp)
    if code is None:
        return "no_setup_pattern"
    if node.current_wave in ("2", "B") and _ends_diagonal(eng, d, t, node.points[0]):
        code, tier = "S11", BASE_TIER["S11"]
    inv = trade_inv(node, parent, code, s, mr_now, gp)
    if inv is None or inv[1] != ("below" if nm > 0 else "above"):
        return "no_inv"
    a = node.points[-1].bar_idx + 1
    seg = lows[a:t_idx + 1] if nm > 0 else highs[a:t_idx + 1]
    if len(seg) > 0 and ((seg.min() < inv[0]) if nm > 0 else (seg.max() > inv[0])):
        return "wick_beyond_inv"                                                     # wick पलीकडे, real break नाही (count जिवंत)
    if (code == "S7" and node.pattern in ZZFLAT and s["c_time_rule"] == "delay" and node.time_flags.get("c_time_violation")
            and not _terminal_c(eng, snap, d, node)):
        return "C3_c_time"                                                           # Neely: t(c) > t(a)+t(b) ⇒ C अजून संपला नाही
    return code, tier, inv, parent


def _wave_start_ts(n):
    """Count च्या चालू wave ची सुरुवात (शेवटचा confirmed point); नसेल ⇒ None."""
    pts = getattr(n, "points", None) if n is not None else None
    return pts[-1].ts if pts else None


def degree_setup(eng, snap, d, t):
    """Degree d वर t ला setup (Setup) किंवा कारण (str). Preferred count वरूनच (C0); फक्त §14 Q6 (wick inv पलीकडे, close आत)
    मध्ये त्याच चालू wave चा दुसरा valid count (उदा. expanded flat) — recount."""
    s = eng.s
    v = snap.degrees.get(d)
    if v is None or v.preferred is None:
        return "no_count"
    if v.parent_missing:
        return "parent_missing"
    if v.gray:
        return "gray"
    pref = v.preferred
    nm = pref.next_motive_dir
    if nm == 0:
        return "next_not_motive"
    vote = v.vote_up if nm > 0 else v.vote_down
    if not vote >= s["vote_min"]:
        return "vote"
    tot = sum(n.joint_score for n in v.nodes)
    share = {id(n): (n.joint_score / tot if tot > 0 else 0.0) for n in v.nodes}
    opp_max = max([share[id(n)] for n in v.nodes if n.next_motive_dir == -nm] or [0.0])
    if opp_max >= s["alt_block_weight"]:
        return "alt_block"
    up = snap.degrees.get(d + 1)
    fr = eng.md[d]["frame"]
    t_idx = frame_index_at(fr, t)
    mr_now = float(eng.cache[d].mr[t_idx]) if t_idx >= 0 and np.isfinite(eng.cache[d].mr[t_idx]) else 0.0
    lows, highs = fr["low"].to_numpy(float), fr["high"].to_numpy(float)
    node, res = pref, _make(eng, snap, d, t, pref, up, mr_now, lows, highs, t_idx)
    if res == "wick_beyond_inv":
        if s["wick_beyond_inv_action"] == "skip":
            return res
        same_wave = [n for n in v.nodes if n is not pref and n.next_motive_dir == nm and n.points[-1].ts == pref.points[-1].ts]
        for alt_node in sorted(same_wave, key=lambda n: -n.joint_score):
            r2 = _make(eng, snap, d, t, alt_node, up, mr_now, lows, highs, t_idx)
            if not isinstance(r2, str):
                node, res = alt_node, r2
                break
    if isinstance(res, str):
        return res
    code, tier, inv, parent = res
    if code not in s["setups_enabled"]:
        return f"disabled_{code}"
    if s["htf_gate_enabled"] and tier == "B":
        return "htf_gate"
    alt = []
    for n in v.nodes:
        if n.next_motive_dir == nm and share[id(n)] >= s["alt_weight_min"]:
            np_ = _find(up, n.parent_key)
            gp2 = _find(snap.degrees.get(d + 2), np_.parent_key) if np_ is not None else None
            c2, _ = classify(n, np_, gp2)
            iv2 = trade_inv(n, np_, c2, s, mr_now, gp2) if c2 else None
            if iv2 is not None and iv2[1] == inv[1]:
                alt.append(iv2[0])
    # S7 (correction पूर्ण): §14 Q3 — TF आणि sub-legs पूर्ण correction वरून (origin पासून); बाकी चालू wave वरून
    start = node.points[0] if code == "S7" else node.points[-1]
    inv_deg, inv_start = d, _wave_start_ts(node)                                     # hard inv चा मालक count (F4)
    if code == "S7" and inv[2] != "B_extreme" and parent is not None:
        inv_deg, owner = d + 1, parent
        if parent.current_wave == LAST_WAVE.get(parent.pattern):
            gp = _find(snap.degrees.get(d + 2), parent.parent_key)
            if gp is not None:
                inv_deg, owner = d + 2, gp
        if _wave_start_ts(owner) is not None:
            inv_start = _wave_start_ts(owner)
        else:
            inv_deg = d
    return Setup(code, d, tier, nm, node, parent, zone_levels(node, code, s), float(inv[0]), inv[2], start, node.tentative,
                 float(vote), float(opp_max), alt, list(parent.invs) if parent is not None else [], node is not pref,
                 inv_degree=inv_deg, inv_start_ts=inv_start,
                 parent_start_ts=_wave_start_ts(parent))
