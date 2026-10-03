"""opportunity_engine/selector.py — Selector (spec §7).

1. gate/validation/risk/score ने नाकारलेले candidates काढणे (log मध्ये ठेवा).  2. वेळेचे नियम: 09:15–09:30 फक्त D1/D2; 14:45 नंतर नवीन entry नाही; 15:15 EOD.
3. मर्यादा: प्रति underlying 1 उघडी position · दिवसाला कमाल 2 trades · 2 SL लागल्यावर त्या दिवशी थांबा · SL नंतर 30 मिनिट cooldown · trade चालू असताना HTF WEAK ⇒ नवीन entry बंद.
4. Dedupe: एकाच दिशेचे, एकाच भागातले (entry ±`dedupe_frac × risk`) candidates एकत्र — सर्वोच्च score ठेवून, प्रत्येक *वेगळ्या* setup_id साठी confluence bonus +5 (कमाल 100).
5. विरुद्ध दिशेचे candidates एकाच वेळी शिल्लक असतील तर दोन्ही drop.  6. सर्वोच्च score निवडा (बरोबरीत setup_quality).
"""
import datetime
from dataclasses import dataclass, field
from typing import Any, List, Optional

import pandas as pd

from .scoring import thresholds


@dataclass
class DayState:
    trades_today: int = 0
    sl_today: int = 0
    last_sl_time: Any = None
    open_positions: int = 0
    htf_weak: bool = False


@dataclass
class Selection:
    chosen: Any = None                                  # Decision किंवा None
    dropped: List[Any] = field(default_factory=list)    # [(Decision, कारण)]
    day_block: Optional[str] = None


def _t(s):
    h, m = str(s).split(":")
    return datetime.time(int(h), int(m))


def day_block_reason(now, day, cfg):
    """दिवसाच्या/वेळेच्या मर्यादांमुळे *कुठलाच* नवीन entry नको असेल तर कारण; नाहीतर None."""
    now = pd.Timestamp(now)
    if now.time() >= _t(cfg.no_entry_after):
        return "TIME_LATE"
    if day.open_positions >= 1:
        return "POSITION_OPEN"
    if day.trades_today >= cfg.max_trades_per_day:
        return "MAX_TRADES"
    if day.sl_today >= cfg.max_sl_per_day:
        return "MAX_SL_HIT"
    if day.last_sl_time is not None and (now - pd.Timestamp(day.last_sl_time)) < pd.Timedelta(minutes=cfg.cooldown_minutes):
        return "SL_COOLDOWN"
    if day.htf_weak:
        return "HTF_WEAK"
    return None


def select(decisions, now, day, cfg):
    """decisions = ज्यांनी gate+validation+risk+score पास केलं (status 'PASS') ते Decision objects. रिटर्न Selection."""
    sel = Selection()
    block = day_block_reason(now, day, cfg)
    if block:
        sel.day_block = block
        sel.dropped = [(d, block) for d in decisions]
        return sel
    now_t = pd.Timestamp(now).time()
    pool = []
    for d in decisions:
        if now_t < _t(cfg.opening_window_end) and d.candidate.setup_id not in cfg.opening_setups:
            sel.dropped.append((d, "OPENING_WINDOW"))
        else:
            pool.append(d)
    # dedupe (दिशा + entry जवळ) आणि confluence bonus
    groups = []
    for d in sorted(pool, key=lambda x: (-x.score.total, -x.candidate.setup_quality)):
        placed = False
        for g in groups:
            lead = g[0]
            near = abs(d.candidate.entry - lead.candidate.entry) <= max(0.5 * lead.plan.risk, 1e-9)
            if d.candidate.direction == lead.candidate.direction and near:
                g.append(d)
                placed = True
                break
        if not placed:
            groups.append([d])
    leads = []
    for g in groups:
        lead = g[0]
        extra = {x.candidate.setup_id for x in g[1:]} - {lead.candidate.setup_id}
        if extra:
            lead.score.total = round(min(100.0, lead.score.total + cfg.confluence_bonus * len(extra)), 2)
            lead.score.notes.append(f"Confluence bonus +{cfg.confluence_bonus * len(extra):.0f} ({', '.join(sorted(extra))})")
            full, half = thresholds(lead.candidate.setup_id, cfg)                       # bonus नंतर साइज पुन्हा ठरवा
            scale = getattr(getattr(lead, "bias", None), "size_factor", 1.0)
            lead.score.decision, lead.score.size_factor = (("FULL", 1.0 * scale) if lead.score.total >= full else ("HALF", 0.5 * scale) if lead.score.total >= half else ("NO_TRADE", 0.0))
        for x in g[1:]:
            sel.dropped.append((x, "DEDUPED"))
        leads.append(lead)
    dirs = {l.candidate.direction for l in leads}
    if len(dirs) > 1:
        sel.dropped += [(l, "OPPOSITE_SIGNALS") for l in leads]
        return sel
    if leads:
        best = max(leads, key=lambda x: (x.score.total, x.candidate.setup_quality))
        sel.chosen = best
        sel.dropped += [(l, "LOWER_SCORE") for l in leads if l is not best]
    return sel
