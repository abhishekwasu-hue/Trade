"""
strategies/base.py
--------------------
सगळ्या intraday strategies साठी common interface.
प्रत्येक strategy ने हा base class extend करायचा आणि check_gates() implement करायचं.

Design goal:
- प्रत्येक strategy स्वतंत्र (independent), दुसऱ्या strategy वर dependent नाही
- प्रत्येकाचा output uniform SignalResult format मध्ये, जेणेकरून
  Orchestrator ला सगळ्यांना equally treat करता येईल
- IST timezone-aware timestamps सक्तीचे (तुमच्या आधीच्या timezone bug नुसार)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import pytz

IST = pytz.timezone("Asia/Kolkata")


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


class InstrumentType(str, Enum):
    FUTURES = "FUTURES"          # NIFTY 50 Futures (VWAP / BB / Structure strategies)
    OPTIONS = "OPTIONS"          # Options selling (OI/PCR strategy)


@dataclass
class SignalResult:
    """प्रत्येक strategy चा standard output. Orchestrator फक्त हाच format वाचतो."""
    strategy_id: str
    direction: Direction
    confidence: float                     # 0.0 - 1.0
    instrument_type: InstrumentType
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(IST))
    reason: str = ""                      # human-readable — कोणत्या gates pass झाल्या
    meta: Dict[str, Any] = field(default_factory=dict)   # extra debug info

    def is_actionable(self) -> bool:
        return self.direction != Direction.NONE and self.confidence > 0


@dataclass
class MarketSnapshot:
    """
    एका cycle साठी सगळा required data इथे pack होतो.
    Orchestrator हा snapshot बनवतो आणि प्रत्येक strategy ला पास करतो.
    प्रत्येक strategy फक्त तिला लागणारा भाग वापरते.
    """
    timestamp: datetime
    futures_ohlcv: Any = None      # DataFrame: NIFTY futures candles (with VWAP/BB precomputed columns)
    options_chain: Any = None      # DataFrame: strike-wise OI/ΔOI/PCR snapshot
    structure_data: Any = None     # dict/DataFrame: swing highs/lows, BOS/CHoCH flags (futures वरून)
    extra: Dict[str, Any] = field(default_factory=dict)


class StrategyBase:
    """
    सगळ्या strategies साठी common contract.
    प्रत्येक subclass ने:
      1. required_data() — कोणता data लागतो हे declare करायचं
      2. check_gates() — actual signal logic implement करायचं
    """

    strategy_id: str = "base"
    default_weight: float = 1.0
    max_concurrent_positions: int = 1

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.weight = self.config.get("weight", self.default_weight)
        self.max_positions = self.config.get("max_positions", self.max_concurrent_positions)

    def required_data(self) -> List[str]:
        """कोणते snapshot fields लागतात — Orchestrator validation साठी वापरतो."""
        raise NotImplementedError

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        """Core signal logic. प्रत्येक strategy ने override करायचं."""
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.strategy_id} enabled={self.enabled} weight={self.weight}>"
