"""market_state — एकच market state module (TRADE_CODE_FIX_CROSSVERIFY_PROMPT §2, F1–F4).

Candidates (vision_led), chart_reader आणि vision facts सगळे हेच वापरतात; ad-hoc impulse finders नाहीत.
  frames   CAS-clean, फक्त बंद bars (bar_end ≤ asof) — opportunity_engine/sessions + cas
  swings   elliott/swings.py (degree सह; ATR × mult)
  trend    F2: trade-degree trend = HTF (1H / 75m) protected LH/HL; counter चाल protected swing च्या real break (elliott/breaks.py)
           आणि नंतर HL/LH पुष्टी होईपर्यंत correction
  legs     F3: impulse = displacement आणि कमी overlap आणि BOS; origin न तोडता 38.2–100% retrace करणारी overlapping चाल = correction
  side     F4: trend / HTF structure state (opportunity_engine/structure.py) / Elliott vote जुळले तरच side, नाहीतर "unclear" + कारण
"""
from .core import DEFAULTS, frame, full_frames, read

__all__ = ["DEFAULTS", "frame", "full_frames", "read"]
