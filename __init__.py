"""
strategies/__init__.py
-------------------------
strategies पॅकेजचा entry point — loader.py इथूनच STRATEGY_REGISTRY import करतो
(config.yaml मधल्या strategy_id कडून प्रत्यक्ष class कडे जाणारा नकाशा).

नवीन strategy जोडताना: इथेच import करून STRATEGY_REGISTRY मध्ये तिचा strategy_id
(config.yaml मधल्या key शीच जुळणारा) घालायचा — बाकी कुठेही बदल लागत नाही.
"""

from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType
from .oi_pcr import OIPCRStrategy
from .ict_fvg import ICTFVGStrategy
from .bb_squeeze import BBSqueezeStrategy
from .vwap import VWAPStrategy

STRATEGY_REGISTRY = {
    OIPCRStrategy.strategy_id: OIPCRStrategy,
    ICTFVGStrategy.strategy_id: ICTFVGStrategy,
    BBSqueezeStrategy.strategy_id: BBSqueezeStrategy,
    VWAPStrategy.strategy_id: VWAPStrategy,
}

__all__ = [
    "StrategyBase", "SignalResult", "MarketSnapshot", "Direction", "InstrumentType",
    "OIPCRStrategy", "ICTFVGStrategy", "BBSqueezeStrategy", "VWAPStrategy",
    "STRATEGY_REGISTRY",
]
