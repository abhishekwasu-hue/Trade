"""opportunity_engine/validation.py — Breakout & Trigger Validation (spec §5, indicator-मुक्त). Output: `validation_score 0–100` + पास/फेल कारणं.

🎓 वजन (plan v2 §2 #3, सुरुवातीचे; backtest नंतर सुधारू): body 20 · close-location 15 · range-expansion 15 · level-पलीकडे close 10 · volume 20 · room 10 · exhaustion 10.
Hard fail: wick-only breakout, room < 1.5R. Pass ≥ 60 आणि hard fail नाही. Volume (raw) उपलब्ध नसेल तर "N/A" आणि त्याचे गुण range expansion ला.
सर्व आकारमान तुलना `k × ref_range(tf)` (मोजपट्टी) — `rr` scalar caller देतो. Follow-through (entry नंतर) तपासणी `risk.py` मध्ये.
Reversal triggers (D2/D3/D4/D6/D10): wick-rejection · body-confirm · trigger-break · zone मध्ये स्पर्श.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class Validation:
    score: float = 0.0
    passed: bool = False
    hard_fail: List[str] = field(default_factory=list)
    checks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    volume_na: bool = False
    kind: str = "BREAKOUT"


def _num(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def validate_breakout(trigger, direction, level, rr, cfg, vol_median=None, room_r=None):
    """trigger = {open, high, low, close, volume?}; direction "LONG"/"SHORT"; level = तोडलेला level; rr = trigger TF ची ref_range (scalar);
    vol_median = मागच्या 20 bars च्या volume चा median (किंवा None => N/A); room_r = HTF opposing zone पर्यंत R (None => zone नाही)."""
    out = Validation(kind="BREAKOUT")
    o, h, l, c = (_num(trigger.get(k)) for k in ("open", "high", "low", "close"))
    rr = _num(rr)
    if None in (o, h, l, c) or rr is None or rr <= 0 or _num(level) is None:
        out.hard_fail.append("DATA")
        out.reasons.append("trigger bar / ref_range / level उपलब्ध नाही")
        return out
    long = direction == "LONG"
    rng = h - l
    w = dict(cfg.val_weights)
    vol = _num(trigger.get("volume"))
    med = _num(vol_median)
    out.volume_na = vol is None or vol <= 0 or med is None or med <= 0
    if out.volume_na:
        w["expansion"] += w.pop("volume")
        w["volume"] = 0
    checks = {}
    body_ratio = abs(c - o) / rng if rng > 0 else 0.0
    checks["body"] = {"pass": body_ratio >= cfg.val_body_min, "value": round(body_ratio, 3), "need": cfg.val_body_min}
    loc = ((c - l) / rng if long else (h - c) / rng) if rng > 0 else 0.0
    checks["close_loc"] = {"pass": loc >= 1 - cfg.val_close_loc, "value": round(loc, 3), "need": 1 - cfg.val_close_loc}
    checks["expansion"] = {"pass": rng >= cfg.val_expansion_k * rr, "value": round(rng / rr, 3), "need": cfg.val_expansion_k}
    beyond = (c - level) if long else (level - c)
    checks["beyond"] = {"pass": beyond >= cfg.val_beyond_k * rr, "value": round(beyond / rr, 3), "need": cfg.val_beyond_k}
    wick_only = (h > level and c <= level) if long else (l < level and c >= level)
    checks["volume"] = ({"pass": None, "value": None, "need": cfg.val_volume_mult} if out.volume_na else
                        {"pass": vol >= cfg.val_volume_mult * med, "value": round(vol / med, 3), "need": cfg.val_volume_mult})
    room_ok = room_r is None or room_r >= cfg.room_min_r
    checks["room"] = {"pass": room_ok, "value": None if room_r is None else round(room_r, 2), "need": cfg.room_min_r}
    checks["exhaustion"] = {"pass": rng <= cfg.val_exhaustion_k * rr, "value": round(rng / rr, 3), "need": cfg.val_exhaustion_k}
    total = 0.0
    for name, ch in checks.items():
        if ch["pass"]:
            total += w.get(name, 0)
    out.checks, out.score = checks, round(total, 1)
    if wick_only:
        out.hard_fail.append("WICK_ONLY")
        out.reasons.append("Wick-only breakout (level पलीकडे close नाही) — नाकारला")
    if not room_ok:
        out.hard_fail.append("NO_ROOM")
        out.reasons.append(f"HTF opposing zone पर्यंत जागा {room_r:.2f}R < {cfg.room_min_r}R")
    for name, ch in checks.items():
        if ch["pass"] is False and name != "room":
            out.reasons.append(f"{name} अपुरा ({ch['value']} < {ch['need']})" if name != "exhaustion" else f"exhaustion: candle खूप मोठी ({ch['value']} > {ch['need']})")
    if out.volume_na:
        out.reasons.append("Volume N/A — त्याचे गुण range expansion ला")
    out.passed = not out.hard_fail and out.score >= cfg.val_pass
    return out


def validate_reversal(trigger, direction, prev, zone, rr, cfg):
    """Reversal trigger (pattern/wick-rejection/trigger-break): wick 30 · body-confirm 25 · trigger-break 25 · zone मध्ये स्पर्श 20. Pass ≥ 60.
    `prev` = आधीचा bar {high, low} (trigger-break साठी), `zone` = {low, high} किंवा None."""
    out = Validation(kind="REVERSAL")
    o, h, l, c = (_num(trigger.get(k)) for k in ("open", "high", "low", "close"))
    rr = _num(rr)
    if None in (o, h, l, c) or rr is None or rr <= 0:
        out.hard_fail.append("DATA")
        out.reasons.append("trigger bar / ref_range उपलब्ध नाही")
        return out
    long = direction == "LONG"
    rng = h - l
    body_hi, body_lo = max(o, c), min(o, c)
    wick = (body_lo - l) if long else (h - body_hi)
    wick_ratio = wick / rng if rng > 0 else 0.0
    confirm = (c > o and (c - l) / rng >= 0.5) if long and rng > 0 else (c < o and (h - c) / rng >= 0.5) if rng > 0 else False
    prev_h, prev_l = _num((prev or {}).get("high")), _num((prev or {}).get("low"))
    broke = (prev_h is not None and c > prev_h) if long else (prev_l is not None and c < prev_l)
    touched = None
    if zone and _num(zone.get("low")) is not None:
        touched = (l <= zone["high"]) if long else (h >= zone["low"])
    pts = {"wick_rejection": 30.0, "body_confirm": 25.0, "trigger_break": 25.0, "at_zone": 20.0}
    if touched is None:                                   # zone लागू नाही (उदा. D2 gap-fade) => N/A; त्याचे गुण उरलेल्यांना प्रमाणात (volume N/A प्रमाणेच)
        scale = 100.0 / (100.0 - pts["at_zone"])
        pts = {k: (v * scale if k != "at_zone" else 0.0) for k, v in pts.items()}
    checks = {
        "wick_rejection": {"pass": wick_ratio >= 0.4 and wick >= 0.3 * rr, "value": round(wick_ratio, 3), "need": 0.4, "points": pts["wick_rejection"]},
        "body_confirm": {"pass": bool(confirm), "value": None, "need": None, "points": pts["body_confirm"]},
        "trigger_break": {"pass": bool(broke), "value": None, "need": None, "points": pts["trigger_break"]},
        "at_zone": {"pass": None if touched is None else bool(touched), "value": touched, "need": True, "points": pts["at_zone"]},
    }
    out.checks = checks
    out.score = float(sum(ch["points"] for ch in checks.values() if ch["pass"]))
    for name, ch in checks.items():
        if ch["pass"] is False:
            out.reasons.append(f"{name} नाही")
    if touched is None:
        out.reasons.append("zone लागू नाही — त्याचे गुण उरलेल्या तपासण्यांना")
    out.passed = out.score >= cfg.val_pass
    return out
