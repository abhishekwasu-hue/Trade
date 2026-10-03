"""
strategies/opportunity_engine.py
----------------------------------
Opportunity Engine चा StrategyBase adapter (strategy_id: `opportunity_engine`, InstrumentType.FUTURES).

🎓 पातळ adapter — सगळं गणित `opportunity_engine/` मध्ये. Snapshot मधून `snapshot.extra["oe_journal"]` येतो; तो खालीलपैकी एक असू शकतो:
  • dict: {"context": Context, "candidates": [Candidate...], "day": DayState (ऐच्छिक), "symbol": "NIFTY" (ऐच्छिक)}
  • `Context` थेट (candidates नसतील)
आवश्यक डेटा नसेल तर `Direction.NONE` + मराठी कारण (कधीच exception नाही). PR-1b मध्ये detectors नाहीत (D1–D3 PR-1c), म्हणून candidates बाहेरून दिले जातात; दिले नाहीत तर
फक्त bias/structure माहिती `meta` मध्ये. `config.yaml` मध्ये डीफॉल्ट `enabled: false` — Orchestrator फक्त दाखवतो, कुठलाही order नाही; Phase 2 मध्ये (paper bot) वेगळा निर्णय.
"""
from dataclasses import replace

from opportunity_engine.config import EngineConfig
from opportunity_engine.context import Context
from opportunity_engine.engine import evaluate

from .base import Direction, InstrumentType, MarketSnapshot, SignalResult, StrategyBase


class OpportunityEngineStrategy(StrategyBase):
    strategy_id = "opportunity_engine"
    default_weight = 1.0
    max_concurrent_positions = 1

    def __init__(self, config=None):
        super().__init__(config)
        overrides = {k: v for k, v in self.config.items() if k in EngineConfig.__dataclass_fields__}
        self.engine_cfg = replace(EngineConfig(), **overrides) if overrides else EngineConfig()

    def required_data(self):
        return ["extra.oe_journal"]

    def _none(self, reason, snapshot=None, **meta):
        kw = {"timestamp": snapshot.timestamp} if snapshot is not None and snapshot.timestamp is not None else {}
        return SignalResult(strategy_id=self.strategy_id, direction=Direction.NONE, confidence=0.0, instrument_type=InstrumentType.FUTURES,
                            reason=reason, meta=meta, **kw)

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        payload = (snapshot.extra or {}).get("oe_journal")
        if payload is None:
            return self._none("Opportunity Engine: structure journal उपलब्ध नाही (snapshot.extra['oe_journal'] रिकामं)", snapshot)
        if isinstance(payload, Context):
            ctx, cands, day, symbol = payload, [], None, "NIFTY"
        elif isinstance(payload, dict) and isinstance(payload.get("context"), Context):
            ctx, cands, day, symbol = payload["context"], list(payload.get("candidates") or []), payload.get("day"), payload.get("symbol", "NIFTY")
        else:
            return self._none("Opportunity Engine: oe_journal चा प्रकार अवैध (Context किंवा {'context': Context, ...} हवा)", snapshot)
        if not ctx.ready(self.engine_cfg.primary_htf):
            return self._none(f"Opportunity Engine: {self.engine_cfg.primary_htf} चा structure अजून तयार नाही — पुरेसा इतिहास नाही", snapshot)
        result = evaluate(cands, ctx, self.engine_cfg, now=snapshot.timestamp if snapshot.timestamp is not None else ctx.time, day=day, symbol=symbol)
        meta = {"bias": result.bias.label, "states": {tf: s.state for tf, s in ctx.states.items()},
                "decisions": [{"setup": d.candidate.setup_id, "dir": d.candidate.direction, "status": d.status, "reasons": d.reasons,
                               "score": None if d.score is None else d.score.total, "commentary": d.commentary} for d in result.decisions]}
        chosen = result.selection.chosen
        if chosen is None:
            why = result.selection.day_block or ("candidates नाहीत" if not cands else "कुठलाही candidate gate/validation/score पास झाला नाही")
            return self._none(f"Opportunity Engine: {result.bias.label} — {why}", snapshot, **meta)
        plan = chosen.plan
        meta.update({"setup_id": chosen.candidate.setup_id, "components": chosen.score.components, "size_factor": chosen.size_factor,
                     "t1": plan.t1, "validation": chosen.validation.checks})
        return SignalResult(strategy_id=self.strategy_id, direction=Direction.LONG if chosen.candidate.direction == "LONG" else Direction.SHORT,
                            confidence=chosen.score.confidence, instrument_type=InstrumentType.FUTURES, entry_price=plan.entry, stop_loss=plan.sl, target=plan.t2,
                            timestamp=snapshot.timestamp, reason=chosen.commentary, meta=meta)
