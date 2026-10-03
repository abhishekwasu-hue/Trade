"""opportunity_engine/engine.py — पूर्ण निर्णय-साखळी (live आणि backtest साठी एकच code path):

Context → Bias → (प्रत्येक candidate) Gate → Validation → Risk plan → Score → Selector → Commentary.
detectors (PR-1c) `Candidate` देतात; इथे त्यांचा निर्णय होतो. कुठलाही order/DB/network नाही.
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np

from . import commentary as cm
from .bias import Bias, GateResult, apply_gate, resolve_bias
from .risk import TradePlan, plan_trade
from .scoring import Score, score_candidate
from .selector import DayState, Selection, select
from .validation import Validation, validate_breakout, validate_reversal


@dataclass
class Decision:
    candidate: Any
    bias: Bias
    gate: Optional[GateResult] = None
    validation: Optional[Validation] = None
    plan: Optional[TradePlan] = None
    score: Optional[Score] = None
    status: str = "PENDING"        # REJECTED_GATE | REJECTED_VALIDATION | REJECTED_RISK | REJECTED_SCORE | PASS | TAKEN | DROPPED
    reasons: List[str] = field(default_factory=list)
    commentary: str = ""
    size_factor: float = 0.0
    drop_reason: Optional[str] = None

    @property
    def confidence(self):
        return 0.0 if self.score is None else self.score.confidence


@dataclass
class EvalResult:
    bias: Bias
    decisions: List[Decision]
    selection: Selection


def _rr_of(cand):
    v = cand.trigger.get("ref_range")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) and v > 0 else None


def _validate(cand, plan_rr_room, cfg):
    t = cand.trigger
    rr = _rr_of(cand)
    if cand.kind == "BREAKOUT":
        return validate_breakout(t, cand.direction, t.get("level"), rr, cfg, vol_median=t.get("volume_median"), room_r=plan_rr_room)
    prev = {"high": t.get("prev_high"), "low": t.get("prev_low")}
    return validate_reversal(t, cand.direction, prev, cand.zone, rr, cfg)


def evaluate(candidates, ctx, cfg, now=None, day=None, symbol="NIFTY"):
    """candidates (यादी) -> EvalResult. `day` = DayState (मर्यादा/cooldown); नसेल तर रिकामा दिवस."""
    now = now if now is not None else ctx.time
    day = day or DayState()
    bias = resolve_bias(ctx, cfg)
    decisions, passing = [], []
    for cand in candidates:
        d = Decision(candidate=cand, bias=bias)
        decisions.append(d)
        d.gate = apply_gate(cand, bias, ctx, cfg)
        if not d.gate.passed:
            d.status, d.reasons = "REJECTED_GATE", list(d.gate.reasons)
            d.commentary = cm.gate_rejected(cand, d.gate, bias, ctx)
            continue
        rr = _rr_of(cand)
        d.plan = plan_trade(cand, ctx, cfg, rr, adr=ctx.adr, symbol=symbol)
        if not d.plan.ok:
            d.status, d.reasons = "REJECTED_RISK", [f"Risk: {r}" for r in d.plan.rejects]
            d.commentary = cm.rejected(cand, "Risk नियमात बसत नाही", d.reasons, ctx)
            continue
        d.validation = _validate(cand, d.plan.rr_to_opposing, cfg)
        if not d.validation.passed:
            d.status, d.reasons = "REJECTED_VALIDATION", d.validation.reasons or ["validation अपुरं"]
            d.commentary = cm.rejected(cand, f"Trigger validation अपयशी (score {d.validation.score:.0f})", d.reasons, ctx)
            continue
        d.score = score_candidate(cand, d.validation, d.plan, bias, ctx, cfg)
        d.size_factor = d.score.size_factor
        if d.score.decision == "NO_TRADE":
            d.status, d.reasons = "REJECTED_SCORE", d.score.notes
            d.commentary = cm.rejected(cand, f"Score {d.score.total:.0f} < threshold", d.reasons, ctx)
            continue
        d.status = "PASS"
        passing.append(d)
    selection = select(passing, now, day, cfg)
    for d, reason in selection.dropped:
        d.status, d.drop_reason = "DROPPED", reason
        d.reasons = [f"Selector: {reason}"]
        d.commentary = cm.rejected(d.candidate, f"Selector ने वगळला ({reason})", d.reasons, ctx)
    if selection.chosen is not None:
        c = selection.chosen
        c.status = "TAKEN"
        c.commentary = cm.taken(c.candidate, c.plan, c.score, c.validation, ctx, bias)
    return EvalResult(bias=bias, decisions=decisions, selection=selection)
