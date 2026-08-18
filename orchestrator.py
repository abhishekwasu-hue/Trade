"""
orchestrator.py
------------------
Signal Orchestrator — AMW A1 च्या नवीन multi-strategy architecture चा गाभा.

काम:
  1. सगळ्या enabled strategies ला दर cycle ला MarketSnapshot पास करणं
  2. प्रत्येकाचा SignalResult गोळा करणं
  3. Conflict resolution: opposite-direction signals आल्यास काय करायचं
  4. Capital/position gates: प्रत्येक strategy च्या max_positions मर्यादेत रहायचं
  5. Final approved signals ची list existing execution layer कडे (kill switch,
     arming phrase, market hours check, daily loss halt) पास करणं — तो भाग
     तुमच्या existing execution module मध्ये आधीच आहे, इथे touch केलेला नाही

Conflict resolution modes (config: conflict_mode):
  - "highest_confidence": सगळ्यात जास्त confidence जिंकते, बाकी drop
  - "veto": कोणतीही दोन strategies opposite direction देत असतील तर दोन्ही drop (safe mode)
  - "weighted_vote": weight * confidence बेरीज करून net direction ठरवा
"""

from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict

from strategies.base import StrategyBase, SignalResult, MarketSnapshot, Direction


@dataclass
class OrchestratorConfig:
    conflict_mode: str = "veto"          # "veto" | "highest_confidence" | "weighted_vote"
    min_confidence_to_act: float = 0.5   # यापेक्षा कमी confidence signal act करणार नाही


class SignalOrchestrator:
    def __init__(self, strategies: List[StrategyBase], config: OrchestratorConfig = None):
        self.strategies = [s for s in strategies if s.enabled]
        self.config = config or OrchestratorConfig()
        # runtime position tracking — प्रत्येक strategy किती positions सध्या open आहेत
        self.open_positions: Dict[str, int] = defaultdict(int)

    def run_cycle(self, snapshot: MarketSnapshot) -> List[SignalResult]:
        """एका cycle साठी सगळ्या strategies evaluate करून final approved signals देतो."""
        raw_signals: List[SignalResult] = []

        for strategy in self.strategies:
            try:
                result = strategy.check_gates(snapshot)
            except Exception as e:
                # एका strategy मध्ये error आल्यास बाकीच्या थांबता कामा नये
                result = SignalResult(
                    strategy_id=strategy.strategy_id,
                    direction=Direction.NONE,
                    confidence=0.0,
                    instrument_type=None,
                    reason=f"ERROR: {e}",
                )
            raw_signals.append(result)

        actionable = [s for s in raw_signals if s.is_actionable() and s.confidence >= self.config.min_confidence_to_act]

        if not actionable:
            return []

        resolved = self._resolve_conflicts(actionable)
        approved = self._apply_position_gates(resolved)
        return approved

    def _resolve_conflicts(self, signals: List[SignalResult]) -> List[SignalResult]:
        longs = [s for s in signals if s.direction == Direction.LONG]
        shorts = [s for s in signals if s.direction == Direction.SHORT]

        if not (longs and shorts):
            # conflict नाहीये, सगळे pass
            return signals

        mode = self.config.conflict_mode

        if mode == "veto":
            # opposite direction आढळल्यास दोन्ही बाजू drop — safest
            return []

        if mode == "highest_confidence":
            best = max(signals, key=lambda s: s.confidence)
            return [best]

        if mode == "weighted_vote":
            strategy_weight = {s.strategy_id: self._weight_of(s.strategy_id) for s in signals}
            long_score = sum(s.confidence * strategy_weight[s.strategy_id] for s in longs)
            short_score = sum(s.confidence * strategy_weight[s.strategy_id] for s in shorts)
            if long_score == short_score:
                return []  # टाय झाल्यास कोणतीही side नाही
            winners = longs if long_score > short_score else shorts
            return winners

        # unknown mode -> safest default
        return []

    def _weight_of(self, strategy_id: str) -> float:
        for s in self.strategies:
            if s.strategy_id == strategy_id:
                return s.weight
        return 1.0

    def _apply_position_gates(self, signals: List[SignalResult]) -> List[SignalResult]:
        approved = []
        for sig in signals:
            strat = next((s for s in self.strategies if s.strategy_id == sig.strategy_id), None)
            if strat is None:
                continue
            if self.open_positions[sig.strategy_id] >= strat.max_positions:
                continue  # capital allocation cap गाठलेली आहे, नवीन position नाही
            approved.append(sig)
        return approved

    def on_position_opened(self, strategy_id: str):
        self.open_positions[strategy_id] += 1

    def on_position_closed(self, strategy_id: str):
        self.open_positions[strategy_id] = max(0, self.open_positions[strategy_id] - 1)
