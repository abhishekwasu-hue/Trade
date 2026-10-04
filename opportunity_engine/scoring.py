"""opportunity_engine/scoring.py — Opportunity Score 0–100 (spec §6, plan v2). HTF alignment हा gate आहे (score मध्ये नाही); score फक्त gate पास झालेल्या candidates साठी.

| घटक | गुण | तपशील |
| Structure context | 30 | Daily/4H/1H trend-दिशेने (15; प्रत्येकी 5; Daily "early reversal" = 2.5) · primary HTF मधला fresh-BOS नंतरचा *पहिला* pullback (10) · primary आणि 1H WEAK/RANGE नाहीत (5) |
| Location | 25 | Level Quality grade (A10/B7/C4) · freshness (FRESH 6/T1 4/T2+ 2) · MTF confluence (5) · flip/gap/trendline overlap (4) |
| Setup quality | 20 | detector चा `setup_quality` × 0.2 |
| Trigger | 15 | validation score × 0.15 |
| Reward:Risk | 10 | HTF opposing zone पर्यंत RR: 1.5 ⇒ 0, ≥3 ⇒ 10 (रेषीय; zone नसेल तर 10) |
निर्णय: < 60 ट्रेड नाही (log मध्ये नोंद) · 60–74 अर्धी साइज · ≥ 75 पूर्ण साइज. Setup-निहाय threshold override (`cfg.setup_thresholds`). `confidence = score / 100`.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .context import is_weak, trend_sign

GRADE_PTS = {"A": 10.0, "B": 7.0, "C": 4.0}
FRESH_PTS = {"FRESH": 6.0, "TESTED_1": 4.0, "TESTED_2+": 2.0}


@dataclass
class Score:
    total: float = 0.0
    components: Dict[str, float] = field(default_factory=dict)
    detail: Dict[str, Any] = field(default_factory=dict)
    decision: str = "NO_TRADE"           # NO_TRADE | HALF | FULL
    size_factor: float = 0.0
    notes: List[str] = field(default_factory=list)

    @property
    def confidence(self):
        return round(self.total / 100.0, 4)


def structure_context(cand, bias, ctx, cfg):
    sign = cand.sign
    pts, detail = 0.0, {}
    aligned = 0.0
    for tf in ("1d", "4h", "1h"):
        st = ctx.get(tf)
        if st is None:
            continue
        if st.sign == sign and not is_weak(st.state):
            aligned += 5.0
        elif tf == "1d" and ((sign > 0 and st.state == "DOWNTREND_WEAK") or (sign < 0 and st.state == "UPTREND_WEAK")):
            aligned += 2.5                                   # Daily early reversal: अर्धे गुण (वापरकर्त्याचा नियम)
            detail["daily_early_reversal"] = True
    pts += aligned
    detail["aligned"] = aligned
    p = ctx.get(cfg.primary_htf)
    fresh = 0.0
    if p is not None and p.sign == sign:
        if "PULLBACK" in p.state:
            fresh = 10.0 if p.pullbacks_since_break <= 1 else 5.0
        elif not is_weak(p.state):
            fresh = 5.0
    pts += fresh
    detail["fresh_bos_pullback"] = fresh
    one_h = ctx.get("1h")
    clean = 0.0
    if p is not None and one_h is not None and not is_weak(p.state) and p.state != "RANGE" and not is_weak(one_h.state) and one_h.state != "RANGE":
        clean = 5.0
    pts += clean
    detail["not_weak_range"] = clean
    return pts, detail


def location_score(cand, cfg=None):
    """Location (कमाल 25). `cfg.consensus_mode == "score"` असेल तर Dual-Eye consensus: CONSENSUS zone +bonus, MATH_ONLY −penalty (0..25 मध्येच) — डीफॉल्ट off ⇒ बदल नाही."""
    z = cand.zone
    if not z:
        return 0.0, {"zone": None}
    grade = GRADE_PTS.get(z.get("quality_grade"), 0.0)
    fresh = FRESH_PTS.get(z.get("freshness"), 0.0)
    mtf = z.get("mtf_count", 1)
    confluence = 5.0 if mtf >= 3 else 3.0 if mtf == 2 else 0.0
    overlap = 4.0 if (z.get("status") == "BROKEN" or z.get("flipped") or cand.meta.get("gap_overlap") or cand.meta.get("trendline_overlap")) else 0.0
    detail = {"grade": grade, "freshness": fresh, "confluence": confluence, "overlap": overlap}
    total = grade + fresh + confluence + overlap
    if cfg is not None and getattr(cfg, "consensus_mode", "off") == "score" and z.get("consensus"):
        adj = cfg.consensus_bonus if z["consensus"] == "CONSENSUS" else -cfg.consensus_penalty if z["consensus"] == "MATH_ONLY" else 0.0
        detail["consensus"] = adj
        total = max(0.0, min(25.0, total + adj))
    return total, detail


def rr_score(rr_value, cfg):
    if rr_value is None:
        return 10.0
    span = cfg.rr_full - cfg.rr_zero
    return round(10.0 * max(0.0, min(1.0, (rr_value - cfg.rr_zero) / span)), 3)


def thresholds(setup_id, cfg):
    t = cfg.setup_thresholds.get(setup_id, {})
    return float(t.get("full", cfg.score_full)), float(t.get("half", cfg.score_half))


def score_candidate(cand, validation, plan, bias, ctx, cfg):
    sc = Score()
    ctx_pts, ctx_detail = structure_context(cand, bias, ctx, cfg)
    loc_pts, loc_detail = location_score(cand, cfg)
    sc.components = {
        "structure": round(ctx_pts, 2), "location": round(loc_pts, 2),
        "setup": round(0.2 * max(0.0, min(100.0, cand.setup_quality)), 2),
        "trigger": round(0.15 * max(0.0, min(100.0, validation.score)), 2),
        "rr": rr_score(plan.rr_to_opposing if plan is not None else None, cfg),
    }
    sc.detail = {"structure": ctx_detail, "location": loc_detail}
    sc.total = round(min(100.0, sum(sc.components.values())), 2)
    full, half = thresholds(cand.setup_id, cfg)
    if sc.total >= full:
        sc.decision, sc.size_factor = "FULL", 1.0 * bias.size_factor
    elif sc.total >= half:
        sc.decision, sc.size_factor = "HALF", 0.5 * bias.size_factor
    else:
        sc.decision, sc.size_factor = "NO_TRADE", 0.0
        sc.notes.append(f"Score {sc.total:.0f} < {half:.0f} — trade नाही (log मध्ये नोंद)")
    return sc
