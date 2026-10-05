"""opportunity_engine/risk.py — Risk & Exit Manager (spec §8). सर्व pure functions (live आणि backtest साठी एकच code path); कुठलाही indicator नाही.

🎓 नियम:
  • SL = structural level पलीकडे `0.25 × ref_range` buffer. SL अंतर `< 0.1×ADR` किंवा `> 0.6×ADR` ⇒ reject.
  • T1 = 1R (50% बुक, SL BE ला). T2 = setup target / HTF opposing zone / 2R — जे आधी येईल.
  • Structure trailing: उरलेल्या भागासाठी नवीन 5M/15M HL/LH तयार झाला की SL त्याच्या पलीकडे (indicator-आधारित नाही) — फक्त अनुकूल दिशेने सरकतो.
  • Time stop: breakout नंतर 6 bars मध्ये +0.5R गाठलं नाही तर exit. Failed-breakout: पुढचे 2 bars level च्या आत close ⇒ exit.
  • Backtest fill: एकाच bar मध्ये SL आणि target दोन्ही ⇒ **SL आधी**. Slippage NIFTY 1 pt/side, BANKNIFTY 3 pt/side. EOD 15:15 ला exit.
"""
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from .bias import nearest_opposing


D1_EXIT_RULES = ("default", "none", "bars", "or_reentry")


@dataclass
class TradePlan:
    direction: str
    entry: float
    sl: float
    t1: float
    t2: float
    risk: float
    rr_to_opposing: Optional[float] = None
    rejects: List[str] = field(default_factory=list)
    slippage: float = 0.0
    adr_ratio: Optional[float] = None

    @property
    def ok(self):
        return not self.rejects

    @property
    def sign(self):
        return 1 if self.direction == "LONG" else -1


def plan_trade(cand, ctx, cfg, rr, adr=None, symbol="NIFTY"):
    """Candidate -> TradePlan. `rr` = trigger TF ची ref_range (scalar, SL buffer साठी), `adr` = ADR (scalar) किंवा None."""
    sign = cand.sign
    entry = float(cand.entry)
    buffer = cfg.sl_buffer_k * float(rr) if rr is not None and np.isfinite(rr) else 0.0
    sl = float(cand.sl_ref) - sign * buffer
    risk = abs(entry - sl)
    plan = TradePlan(direction=cand.direction, entry=entry, sl=sl, t1=entry, t2=entry, risk=risk, slippage=cfg.slippage_pts.get(symbol, 1.0))
    if risk <= 0 or (sl - entry) * sign >= 0:
        plan.rejects.append("SL_INVALID")
        return plan
    if adr is not None and np.isfinite(adr) and adr > 0:
        plan.adr_ratio = risk / adr
        if risk < cfg.adr_min_frac * adr:
            plan.rejects.append("SL_TOO_TIGHT")
        elif risk > cfg.adr_max_frac * adr:
            plan.rejects.append("SL_TOO_WIDE")
    plan.t1 = entry + sign * cfg.t1_r * risk
    t1_hint = (cand.meta or {}).get("t1_hint")                     # setup-विशिष्ट T1 (उदा. D7: 1 × box उंची) — entry च्या पुढे असेल तरच
    if t1_hint is not None and np.isfinite(float(t1_hint)) and (float(t1_hint) - entry) * sign > 0:
        plan.t1 = float(t1_hint)
    base_t2 = entry + sign * cfg.t2_default_r * risk
    hints = [t for t in cand.targets_hint if (t - plan.t1) * sign > 0]
    t2 = min(hints, key=lambda t: abs(t - entry)) if hints else base_t2
    zone, dist = nearest_opposing(ctx, entry, sign)
    if zone is not None:
        plan.rr_to_opposing = dist / risk
        zone_edge = entry + sign * dist
        if (zone_edge - plan.t1) * sign > 0 and abs(zone_edge - entry) < abs(t2 - entry):
            t2 = zone_edge
    plan.t2 = t2 if (t2 - plan.t1) * sign > 0 else plan.t1
    return plan


# ---------------------------------------------------------------------------------------------------------------------
# Exit simulation (bar-by-bar; live आणि backtest साठी एकच)
# ---------------------------------------------------------------------------------------------------------------------
@dataclass
class Position:
    plan: TradePlan
    kind: str = "BREAKOUT"
    level: Optional[float] = None                # breakout चा level (failed-breakout साठी)
    setup: Optional[str] = None                  # setup_id (T1/H4: D1-विशिष्ट exit नियम); None ⇒ जुनं वर्तन
    sl: float = 0.0
    remaining: float = 1.0
    t1_done: bool = False
    bars: int = 0
    mfe_r: float = 0.0
    inside_closes: int = 0
    closed: bool = False
    exit_reason: Optional[str] = None
    pnl_pts: float = 0.0                         # भारित (size-weighted) pts, slippage सह
    events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.sl = self.plan.sl

    @property
    def r_multiple(self):
        return self.pnl_pts / self.plan.risk if self.plan.risk else 0.0


def open_position(plan, kind="BREAKOUT", level=None, setup=None):
    return Position(plan=plan, kind=kind, level=level, setup=setup)


def _book(pos, price, frac, reason, time):
    p = pos.plan
    fill = price - p.sign * p.slippage                      # exit वर slippage विरुद्ध
    entry_fill = p.entry + p.sign * p.slippage              # entry वर slippage विरुद्ध
    pos.pnl_pts += (fill - entry_fill) * p.sign * frac
    pos.remaining = round(pos.remaining - frac, 10)
    pos.events.append({"time": time, "reason": reason, "price": float(price), "frac": float(frac)})


def _close_all(pos, price, reason, time):
    _book(pos, price, pos.remaining, reason, time)
    pos.closed, pos.exit_reason = True, reason


def _hhmm(s):
    h, m = str(s).split(":")
    return datetime.time(int(h), int(m))


def on_bar(pos, bar, cfg, time=None, trail_stop=None):
    """entry नंतरच्या प्रत्येक closed bar वर. `bar` = {open, high, low, close}; `time` = bar_end; `trail_stop` = नवीन structure stop (HL खालचा/LH वरचा) किंवा None.
    क्रम: SL (आधी) → T1 → T2 → structure trail → time stop → failed breakout → EOD. रिटर्न: या bar वर झालेले events."""
    if pos.closed:
        return []
    p = pos.plan
    s = p.sign
    n0 = len(pos.events)
    pos.bars += 1
    h, l, c = float(bar["high"]), float(bar["low"]), float(bar["close"])
    # 1. SL आधी (एकाच bar मध्ये SL आणि target दोन्ही असतील तरी)
    if (l <= pos.sl) if s > 0 else (h >= pos.sl):
        reason = "SL" if not pos.t1_done else ("BE" if abs(pos.sl - p.entry) < 1e-9 else "TRAIL_SL")       # T1 नंतरचा stop: BE किंवा trailing (नफ्यात)
        _close_all(pos, pos.sl, reason, time)
        return pos.events[n0:]
    # 2. T1: 50% बुक, SL BE ला
    if not pos.t1_done and ((h >= p.t1) if s > 0 else (l <= p.t1)):
        _book(pos, p.t1, cfg.t1_book_frac, "T1", time)
        pos.t1_done, pos.sl = True, p.entry
    # 3. T2 (T1 झाल्यानंतरच, आणि त्याच bar मध्ये चालेल)
    if pos.t1_done and ((h >= p.t2) if s > 0 else (l <= p.t2)):
        _close_all(pos, p.t2, "T2", time)
        return pos.events[n0:]
    favourable = (h - p.entry) if s > 0 else (p.entry - l)
    pos.mfe_r = max(pos.mfe_r, favourable / p.risk if p.risk else 0.0)
    # 4. structure trailing (फक्त T1 नंतर, फक्त अनुकूल दिशेने)
    if pos.t1_done and trail_stop is not None and (trail_stop - pos.sl) * s > 0 and (trail_stop - c) * s < 0:
        pos.sl = float(trail_stop)
        pos.events.append({"time": time, "reason": "TRAIL", "price": float(trail_stop), "frac": 0.0})
    # 5. time stop — spec: "breakout नंतर 6 bars मध्ये +0.5R गाठलं नाही तर exit" => फक्त breakout setups (reversal setups ना target पर्यंत वेळ लागतो)
    # 🎓 T1/H4: D1 साठी पर्यायी नियम (cfg.d1_exit_rule; डीफॉल्ट "default" ⇒ जुनंच)
    d1_rule = getattr(cfg, "d1_exit_rule", "default") if pos.setup == "D1" else "default"
    if d1_rule not in D1_EXIT_RULES:
        raise ValueError(f"अज्ञात d1_exit_rule: {d1_rule!r} (वैध: {D1_EXIT_RULES})")
    if d1_rule == "or_reentry":
        if not pos.t1_done and pos.level is not None and ((c < pos.level) if s > 0 else (c > pos.level)):
            _close_all(pos, c, "OR_REENTRY", time)
            return pos.events[n0:]
    elif d1_rule != "none":
        stop_bars = cfg.d1_time_stop_bars if d1_rule == "bars" else cfg.time_stop_bars
        if pos.kind in cfg.time_stop_kinds and not pos.t1_done and pos.bars >= stop_bars and pos.mfe_r < cfg.time_stop_r:
            _close_all(pos, c, "TIME_STOP", time)
            return pos.events[n0:]
    # 6. failed breakout: पुढचे `followthrough_bars` bars level च्या आत close
    if pos.kind == "BREAKOUT" and pos.level is not None and pos.bars <= cfg.followthrough_bars:
        inside = (c < pos.level) if s > 0 else (c > pos.level)
        pos.inside_closes = pos.inside_closes + 1 if inside else 0
        if pos.inside_closes >= cfg.followthrough_bars:
            _close_all(pos, c, "FAILED_BREAKOUT", time)
            return pos.events[n0:]
    # 7. EOD
    if time is not None and _time_of(time) >= _hhmm(cfg.eod_exit):
        _close_all(pos, c, "EOD", time)
    return pos.events[n0:]


def _time_of(ts):
    try:
        return ts.time()
    except AttributeError:
        return _hhmm(str(ts)[-5:])
