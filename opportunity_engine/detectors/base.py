"""opportunity_engine/detectors/base.py — Detector interface आणि Candidate dataclass (spec §4).

प्रत्येक detector: स्वतंत्र class, `detect(journal, bars_by_tf, bias, now) -> list[Candidate]`; `enabled`, `min_score`, `allowed_bias`; स्वतःचा `setup_quality`
(0–100) आणि कारणं (`notes`). कुठलाही indicator नाही. Candidate ची दिशा bias शी जुळते का ते `bias.apply_gate()` ठरवतो — detector फक्त *काय दिसलं* ते सांगतो.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

KIND_BREAKOUT, KIND_PULLBACK_END, KIND_REVERSAL = "BREAKOUT", "PULLBACK_END", "REVERSAL"


@dataclass
class Candidate:
    setup_id: str                       # "D1" … "D10"
    direction: str                      # "LONG" | "SHORT"
    time: Any                           # trigger bar चा bar_end (निर्णयाची वेळ)
    entry: float                        # entry किंमत (trigger bar चा close)
    sl_ref: float                       # structural invalidation level (SL याच्या पलीकडे buffer सह)
    kind: str = KIND_BREAKOUT           # BREAKOUT | PULLBACK_END | REVERSAL
    tf: str = "15m"                     # setup TF
    trigger_tf: str = "5m"
    setup_quality: float = 50.0         # 0–100 (detector चा)
    trigger: Dict[str, Any] = field(default_factory=dict)       # {open, high, low, close, volume?, level?, prev_high?, prev_low?, ref_range?}
    zone: Optional[Dict[str, Any]] = None                       # location (zones.build_levels चा एक level) किंवा None
    targets_hint: List[float] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def sign(self):
        return 1 if self.direction == "LONG" else -1


class Detector:
    """आधारभूत class. subclass `detect()` implement करतो."""
    setup_id = "D?"
    default_kind = KIND_BREAKOUT

    def __init__(self, enabled=True, min_score=None, allowed_bias=None):
        self.enabled = enabled
        self.min_score = min_score
        self.allowed_bias = allowed_bias

    def detect(self, journal, bars_by_tf, bias, now):
        raise NotImplementedError
