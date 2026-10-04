"""opportunity_engine/context.py — Journal चा "आत्ताचा" HTF संदर्भ (bias/gate/scoring चा इनपुट). फक्त वाचन; no-lookahead (journal incremental असल्याने आत्तापर्यंतचेच bars).

🎓 `TFState` = एका TF चा सद्य state + protected level + शेवटचा structure break (BOS इ.) आणि त्यानंतरचे pullbacks (Structure context score साठी "fresh BOS नंतरचा पहिला pullback").
`Context.levels` = zones.build_levels() चे गुणांकित levels (supply/demand/S-R/KEY/GAP) — veto (c), room-to-run आणि location score साठी.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from .config import TF_ORDER
from .measures import adr as measure_adr

BREAK_EVENTS = ("BOS", "REVERSAL_CONFIRMED", "RECOVERY", "RANGE_EXIT_UP", "RANGE_EXIT_DOWN")


def trend_sign(state):
    """+1 UPTREND*, −1 DOWNTREND*, 0 इतर (RANGE/INIT/None)."""
    if not state:
        return 0
    return 1 if str(state).startswith("UPTREND") else -1 if str(state).startswith("DOWNTREND") else 0


def is_weak(state):
    return bool(state) and str(state).endswith("_WEAK")


@dataclass
class TFState:
    tf: str
    state: str
    protected: Optional[float] = None
    last_sh: Optional[float] = None
    last_sl: Optional[float] = None
    range_high: Optional[float] = None
    range_low: Optional[float] = None
    ref_range: Optional[float] = None
    last_break_time: Any = None
    pullbacks_since_break: int = 0
    updated_at: Any = None

    @property
    def sign(self):
        return trend_sign(self.state)


@dataclass
class Context:
    time: Any
    price: Optional[float]
    states: Dict[str, TFState] = field(default_factory=dict)
    levels: List[dict] = field(default_factory=list)
    adr: float = float("nan")

    def get(self, tf):
        return self.states.get(tf)

    def state_name(self, tf):
        st = self.states.get(tf)
        return st.state if st else None

    def ready(self, *tfs):
        """दिलेल्या TFs चे states INIT नाहीत (पुरेसा structure) का."""
        return all(self.states.get(tf) is not None and self.states[tf].state != "INIT" for tf in tfs)


def tf_state_from_tracker(tr):
    snap = tr.snapshot()
    last_break = None
    pullbacks = 0
    for e in tr.events:
        if e["type"] in BREAK_EVENTS:
            last_break, pullbacks = e, 0
        elif e["type"] == "PULLBACK_START" and last_break is not None:
            pullbacks += 1
    return TFState(
        tf=tr.tf, state=snap["trend_state"], protected=snap["protected_level"], last_sh=snap["last_sh"], last_sl=snap["last_sl"],
        range_high=snap["range_high"], range_low=snap["range_low"], ref_range=snap["ref_range"],
        last_break_time=None if last_break is None else last_break["time"], pullbacks_since_break=pullbacks, updated_at=snap["updated_at"])


def build_context(journal, levels=None, daily_df=None, price=None, now=None, cfg=None, flips=None):
    """journal (आत्तापर्यंत चालवलेला) + ऐच्छिक levels/daily bars -> Context. `price` न दिल्यास सर्वात बारीक TF चा शेवटचा close.
    `flips` = तुटलेले (BROKEN) zones (build_levels चे `rejected` मधले) — flip zones म्हणून pullback watch साठी; gate चे room/veto त्यांना वगळतात."""
    cfg = cfg or journal.cfg
    states, finest = {}, None
    for tf in TF_ORDER:
        tr = journal.trackers.get(tf)
        if tr is None or not tr.c:
            continue
        states[tf] = tf_state_from_tracker(tr)
        finest = finest or tr
    if price is None and finest is not None:
        price = float(finest.c[-1])
    if now is None and states:
        now = max(s.updated_at for s in states.values() if s.updated_at is not None)
    adr_value = measure_adr(daily_df, cfg.adr_days) if daily_df is not None else float("nan")
    extra = [z for z in (flips or []) if z.get("status") == "BROKEN"]
    return Context(time=now, price=price, states=states, levels=list(levels or []) + extra, adr=adr_value)


class IncrementalTFState:
    """tracker च्या events वर "शेवटचा break आणि त्यानंतरचे pullbacks" O(1) amortised ठेवणारा (backtest/live: प्रत्येक bar ला पूर्ण events scan नाही)."""

    def __init__(self, tr):
        self.tr, self._i, self._last_break, self._pullbacks = tr, 0, None, 0

    def state(self):
        tr = self.tr
        evs = tr.events
        while self._i < len(evs):
            e = evs[self._i]
            if e["type"] in BREAK_EVENTS:
                self._last_break, self._pullbacks = e["time"], 0
            elif e["type"] == "PULLBACK_START" and self._last_break is not None:
                self._pullbacks += 1
            self._i += 1
        snap = tr.snapshot()
        return TFState(tf=tr.tf, state=snap["trend_state"], protected=snap["protected_level"], last_sh=snap["last_sh"], last_sl=snap["last_sl"],
                       range_high=snap["range_high"], range_low=snap["range_low"], ref_range=snap["ref_range"], last_break_time=self._last_break,
                       pullbacks_since_break=self._pullbacks, updated_at=snap["updated_at"])
