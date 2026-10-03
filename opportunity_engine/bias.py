"""opportunity_engine/bias.py — HTF Bias Resolver + Alignment Gate + Pullback Watch (spec §3, plan v2 §0.2/§8).

🎓 वापरकर्त्याने मंजूर केलेले नियम:
  • Primary HTF: **4H = bias**, **Daily = veto**, **1H = पुष्टी** (config: `primary_htf: 4h|1d`, `daily_veto: true|false`).
  • Bias (primary = 4H): UP/UP_PB आणि 1H == UPTREND ⇒ `LONG_ONLY`; 1H ≠ UPTREND ⇒ `LONG_ONLY_WAIT_PULLBACK_END` (breakouts नाहीत; फक्त D2/D3/D4/D6/D10);
    4H WEAK ⇒ `NO_TRADE` (config: अर्धी साइज); 4H RANGE ⇒ `RANGE_EDGES_ONLY`; DOWN बाजू आरशातली.
  • Daily veto (long साठी; short आरशातलं) — खालीलपैकी काहीही असेल तर नवीन long नाही:
      (a) Daily DOWNTREND / DOWNTREND_PULLBACK (विरोधी trend);  (b) Daily UPTREND_WEAK (त्याच दिशेचा WEAK);
      (c) entry Daily FRESH supply किंवा grade A/B resistance च्या `1.5R` आत (R = |entry − SL|; अंतर zone च्या जवळच्या किनाऱ्यापर्यंत).
    Daily RANGE ⇒ 4H bias चालेल, पण range edge पासून किमान `2.5R` (long: range high पासून).
    ⚠️ literal वाचन: long साठी Daily `DOWNTREND_WEAK` हा veto नाही — तो "early reversal" म्हणून ध्वजांकित (scoring मध्ये Daily-aligned गुण अर्धे).
  • Gate (hard): `HTF_MISALIGNED`, `HTF_WAIT_PULLBACK`, `DAILY_VETO_A/B/C`, `DAILY_RANGE_LOCATION`, `NO_ROOM` (<1.5R), `PROTECTED_LEVEL` (SL primary-HTF protected level पलीकडे),
    `RANGE_LOCATION` (RANGE bias मध्ये मधोमध entry), `NO_TRADE`.
  • Counter-trend breakout = pullback: trade नाही; `PULLBACK_IN_PROGRESS` + watch zone (जवळचा HTF demand/support/flip किंवा उलट बाजूचा supply).
कुठलाही indicator नाही; `R` आणि zone अंतर किंमतीत; ref_range इथे वापरलेला नाही.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .context import is_weak, trend_sign

LONG_ONLY, LONG_WAIT = "LONG_ONLY", "LONG_ONLY_WAIT_PULLBACK_END"
SHORT_ONLY, SHORT_WAIT = "SHORT_ONLY", "SHORT_ONLY_WAIT_PULLBACK_END"
RANGE_EDGES, NO_TRADE = "RANGE_EDGES_ONLY", "NO_TRADE"

HTF_ZONE_TFS = ("1h", "4h", "1d")
GATE_TEXT = {
    "NO_TRADE": "Bias NO_TRADE",
    "HTF_MISALIGNED": "दिशा HTF bias शी जुळत नाही",
    "HTF_WAIT_PULLBACK": "HTF मध्ये pullback संपण्याची वाट — breakout setups नाहीत",
    "DAILY_VETO_A": "Daily विरोधी trend (veto a)",
    "DAILY_VETO_B": "Daily त्याच दिशेचा WEAK (veto b)",
    "DAILY_VETO_C": "Daily FRESH supply/A-B resistance जवळ (veto c)",
    "DAILY_RANGE_LOCATION": "Daily RANGE: range edge खूप जवळ",
    "NO_ROOM": "HTF opposing zone पर्यंत 1.5R पेक्षा कमी जागा",
    "PROTECTED_LEVEL": "SL primary-HTF protected level पलीकडे (HTF structure धोक्यात)",
    "RANGE_LOCATION": "RANGE bias: entry range च्या कडेजवळ नाही (मधोमध)",
}


@dataclass
class Bias:
    label: str
    direction: int = 0                  # +1 long, −1 short, 0 (दोन्ही कडा / नाही)
    mode: str = "NONE"                  # FULL | PULLBACK_END | RANGE | NONE
    size_factor: float = 1.0
    primary_tf: str = "4h"
    primary_state: Optional[str] = None
    one_h_state: Optional[str] = None
    daily_state: Optional[str] = None
    daily_early_reversal_long: bool = False
    daily_early_reversal_short: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class GateResult:
    passed: bool
    codes: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    watch: Optional[Dict[str, Any]] = None          # PULLBACK_IN_PROGRESS चा watch zone
    pullback_in_progress: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def primary_code(self):
        return self.codes[0] if self.codes else None


def _label(sign, wait):
    return (LONG_WAIT if wait else LONG_ONLY) if sign > 0 else (SHORT_WAIT if wait else SHORT_ONLY)


def resolve_bias(ctx, cfg):
    """Context -> Bias (प्रत्येक closed 15M bar ला)."""
    primary = cfg.primary_htf
    st_p = ctx.state_name(primary)
    st_1h, st_d = ctx.state_name("1h"), ctx.state_name("1d")
    bias = Bias(label=NO_TRADE, primary_tf=primary, primary_state=st_p, one_h_state=st_1h, daily_state=st_d,
                daily_early_reversal_long=st_d == "DOWNTREND_WEAK", daily_early_reversal_short=st_d == "UPTREND_WEAK")
    if not ctx.ready(primary):
        bias.reasons.append(f"{primary} चा structure अजून तयार नाही (INIT) — trade नाही")
        return bias
    sign = trend_sign(st_p)
    if st_p == "RANGE":
        bias.label, bias.mode = RANGE_EDGES, "RANGE"
        bias.reasons.append(f"{primary} RANGE — range च्या कडेवरच reversal setups")
        return bias
    if is_weak(st_p):
        if cfg.weak_half_size:
            bias.label, bias.direction, bias.mode, bias.size_factor = _label(sign, True), sign, "PULLBACK_END", 0.5
            bias.reasons.append(f"{primary} {st_p} — config नुसार trend-दिशेचे pullback-end setups अर्ध्या साइजने")
        else:
            bias.reasons.append(f"{primary} {st_p} (CHoCH) — trend धोक्यात; नवीन trade नाही")
        return bias
    wait = st_1h != ("UPTREND" if sign > 0 else "DOWNTREND")
    bias.label, bias.direction = _label(sign, wait), sign
    bias.mode = "PULLBACK_END" if wait else "FULL"
    bias.reasons.append(f"{primary} {st_p}" + (f"; 1H {st_1h} ≠ trend-दिशेचा — pullback संपण्याची वाट (breakouts नाहीत)" if wait else "; 1H पुष्टी"))
    return bias


# ---------------------------------------------------------------------------------------------------------------------
# zones मदतनीस
# ---------------------------------------------------------------------------------------------------------------------
def _opposing(level, sign):
    """long (sign=+1) साठी वरचे supply/resistance (PDH/PWH सकट), short साठी खालचे demand/support (PDL/PWL सकट)."""
    kind, src = level.get("kind"), str(level.get("source", ""))
    if sign > 0:
        return kind in ("SUPPLY", "RESISTANCE") or (kind == "KEY" and src in ("PDH", "PWH"))
    return kind in ("DEMAND", "SUPPORT") or (kind == "KEY" and src in ("PDL", "PWL"))


def _strong(level):
    return level.get("quality_grade") in ("A", "B") or (level.get("kind") == "SUPPLY" and level.get("freshness") == "FRESH") or \
        (level.get("kind") == "DEMAND" and level.get("freshness") == "FRESH")


def nearest_opposing(ctx, entry, sign, tfs=HTF_ZONE_TFS, strong_only=True):
    """entry च्या पलीकडचा (long: वर; short: खाली) सर्वात जवळचा opposing HTF zone; (level, distance_pts) किंवा (None, None)."""
    best, best_d = None, None
    for lv in ctx.levels:
        if lv.get("tf") not in tfs or not _opposing(lv, sign) or lv.get("status") == "BROKEN" or lv.get("reject_reason"):
            continue
        if strong_only and not _strong(lv):
            continue
        d = (lv["low"] - entry) if sign > 0 else (entry - lv["high"])
        if d < 0:
            continue
        if best_d is None or d < best_d:
            best, best_d = lv, d
    return best, best_d


def pullback_watch_zone(ctx, sign, tfs=HTF_ZONE_TFS):
    """trend-दिशेच्या pullback चं संभाव्य अंतिम स्थान: जवळचा HTF demand/support/flip/unfilled gap (long) किंवा supply/resistance/flip (short) — किंमतीच्या
    खाली/वर, सर्वात जवळचा. Flip = तुटलेला (BROKEN) विरुद्ध zone, जो आता भूमिका बदलून आधार/अडथळा झाला."""
    price = ctx.price
    if price is None:
        return None
    best, best_d = None, None
    for lv in ctx.levels:
        if lv.get("tf") not in tfs:
            continue
        flipped = lv.get("status") == "BROKEN"
        if lv.get("reject_reason") and not flipped:
            continue
        kind, src = lv.get("kind"), str(lv.get("source", ""))
        support_like = (kind in ("DEMAND", "SUPPORT") and not flipped) or (kind in ("SUPPLY", "RESISTANCE") and flipped) or \
            (kind == "KEY" and src in ("PDL", "PWL")) or (kind == "GAP" and lv.get("gap_status") != "FILLED")
        resist_like = (kind in ("SUPPLY", "RESISTANCE") and not flipped) or (kind in ("DEMAND", "SUPPORT") and flipped) or \
            (kind == "KEY" and src in ("PDH", "PWH"))
        if sign > 0 and support_like and lv["high"] <= price:
            d = price - lv["high"]
        elif sign < 0 and resist_like and lv["low"] >= price:
            d = lv["low"] - price
        else:
            continue
        if best_d is None or d < best_d:
            best, best_d = lv, d
    if best is None:
        return None
    flip = best.get("status") == "BROKEN"
    return {"zone_low": best["low"], "zone_high": best["high"], "kind": best["kind"], "tf": best["tf"], "level_id": best.get("level_id"),
            "distance": best_d, "flip": flip, "reason": f"{best['tf']} {best['kind']}" + (" (flip)" if flip else f" ({best.get('freshness', '')})")}


# ---------------------------------------------------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------------------------------------------------
def risk_distance(cand):
    return abs(float(cand.entry) - float(cand.sl_ref))


def apply_gate(cand, bias, ctx, cfg):
    """Candidate वर hard gate. रिटर्न GateResult (सर्व अपयशी कारणं, पहिलं = primary)."""
    codes, details = [], {}
    sign, R = cand.sign, risk_distance(cand)
    entry = float(cand.entry)

    def fail(code, **extra):
        if code not in codes:
            codes.append(code)
        details.update(extra)

    if bias.label == NO_TRADE:
        fail("NO_TRADE")
    elif bias.direction != 0 and sign != bias.direction:
        fail("HTF_MISALIGNED")
    elif bias.mode == "PULLBACK_END" and (cand.setup_id in cfg.breakout_setups or cand.kind == "BREAKOUT") and cand.setup_id not in cfg.pullback_end_setups:
        fail("HTF_WAIT_PULLBACK")

    primary_state = ctx.state_name(cfg.primary_htf)
    if bias.label == RANGE_EDGES:
        st = ctx.get(cfg.primary_htf)
        if st is not None and st.range_high is not None and st.range_low is not None and st.range_high > st.range_low:
            height = st.range_high - st.range_low
            pos = (entry - st.range_low) / height
            ok = pos <= cfg.range_edge_frac if sign > 0 else pos >= 1 - cfg.range_edge_frac
            if not ok:
                fail("RANGE_LOCATION", range_position=round(pos, 3))

    if cfg.daily_veto and cfg.primary_htf != "1d" and ctx.get("1d") is not None:
        d = ctx.get("1d")
        if d.sign == -sign and not is_weak(d.state):
            fail("DAILY_VETO_A", daily_state=d.state)
        elif d.sign == sign and is_weak(d.state):
            fail("DAILY_VETO_B", daily_state=d.state)
        if R > 0:
            z, dist = nearest_opposing(ctx, entry, sign, tfs=("1d",))
            if z is not None and dist < cfg.veto_zone_r * R:
                fail("DAILY_VETO_C", zone=z.get("level_id"), distance_r=round(dist / R, 2))
            if d.state == "RANGE" and d.range_high is not None and d.range_low is not None:
                edge = (d.range_high - entry) if sign > 0 else (entry - d.range_low)
                if edge < cfg.daily_range_location_r * R:
                    fail("DAILY_RANGE_LOCATION", distance_r=round(edge / R, 2) if R else None)

    if R > 0:
        z, dist = nearest_opposing(ctx, entry, sign)
        details["room_r"] = None if z is None else round(dist / R, 2)
        if z is not None and dist < cfg.room_min_r * R:
            fail("NO_ROOM", zone=z.get("level_id"), distance_r=round(dist / R, 2))

    prot = ctx.get(cfg.primary_htf).protected if ctx.get(cfg.primary_htf) is not None else None
    if prot is not None and primary_state and trend_sign(primary_state) == sign:
        beyond = cand.sl_ref < prot if sign > 0 else cand.sl_ref > prot
        if beyond:
            fail("PROTECTED_LEVEL", protected=prot)

    result = GateResult(passed=not codes, codes=codes, reasons=[GATE_TEXT.get(c, c) for c in codes], details=details)
    if "HTF_MISALIGNED" in codes and cand.kind == "BREAKOUT" and bias.direction != 0:
        result.pullback_in_progress = True
        result.watch = pullback_watch_zone(ctx, bias.direction)
    return result
