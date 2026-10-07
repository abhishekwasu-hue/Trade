"""
elliott/exits.py — E3: trade management (spec §9 exit priority, §14 Q4/Q5, §7 hierarchy)
-------------------------------------------------------------------------------------
🎓 दर TTF bar close ला (आणि क्रम 0 साठी त्या bar च्या आतल्या spot टोकावर) — **पहिला लागू झालेला exit जिंकतो**:
  0 emergency     spot ने short strike स्वतः ओलांडला (intrabar)                      re-entry नाही
  1 hard          trade-degree hard inv (किंवा D+1 parent — cascade) वर real break     re-entry नाही
  2 premium stop  spread debit ≥ hard_stop_mult × credit (bar close; intrabar पर्याय)
  3 soft          reversal composite टोक ± buffer वर real break ⇒ soft_stop_action     re-entry (max_reentries)
  4 target        Tier B: C zone मध्ये उलट logical reversal (opposite_reversal) / fixed_mult;
                  Tier A: T1 = (ii) end + 1.0 × (i) ⇒ निम्मे lots बंद, उरलेले progressive inv ने (किंवा exit_all)
  5 profit        captured ≥ tp_pct_credit[tier] % of credit
  6 progress      progress_bars (= mult × bars_last_subleg) TTF bars मध्ये spot close ने sub-leg origin (H) ओलांडला नाही
  7 expiry        expiry दिवशी ≥ expiry_exit_time: spot short strike पासून < hold SD किंवा short ITM ⇒ exit
  8 thesis        उलट setup चा trigger / पुढची motive पूर्ण
False break (wick / reclaim) ⇒ 1 आणि 3 लागत नाहीत (ते real break वरच — breaks.py). **Exits कधीच block होत नाहीत:** entry
window, vote, daily loss, max spreads, live_approved — कुठल्याही entry setting चा इथे संदर्भ नाही.
Progressive inv: (S1/S2/S10/S13) spot ने (i) चं टोक ओलांडलं ⇒ hard inv = correction end (wave 2 end).
Lower degree inv break ⇒ lower_inv_action (alert / reduce / exit).
इथे फक्त निर्णय (pure); bars, real-break, reversal आणि premium मोजणी E4 backtest/E6 paper loop करतो (ctx).
"""
import math
from dataclasses import dataclass, field

TIER_IDX = {"A": 0, "B": 1, "C": 2}
PROGRESSIVE = ("S1", "S2", "S10", "S13")
C_ZONE_SELF = ("S6a", "S6b", "S12", "S11")         # B end = extreme, A = count चा पहिला leg
C_ZONE_PARENT_FROM_EXTREME = ("S6c", "S7", "S8")    # base = extreme, A = parent चा पहिला leg (parent B/X/E संपला)
C_ZONE_PARENT_B = ("S13", "S14")                    # C च्या आत: base = parent B end, A = parent पहिला leg


@dataclass
class TradeState:
    sig: object
    plan: dict
    entry_ts: object
    entry_credit: float                  # slippage नंतरचा प्रत्यक्ष credit (points)
    lots_open: int
    hard_inv: float
    bars: int = 0                        # entry नंतर बंद झालेले TTF bars
    crossed_h: bool = False              # spot close ने sub-leg origin ओलांडला
    partial_done: bool = False
    inv_moved: bool = False
    soft_reduced: bool = False           # reduce एकदाच (ctx flags "या bar पर्यंत" — cumulative)
    lower_reduced: bool = False
    reentries: int = 0
    log: list = field(default_factory=list)


def _len0(pts):
    return abs(pts[1] - pts[0]) if len(pts) >= 2 else None


def tier_a_targets(sig, s):
    """Tier A: (ii)/correction end पासून tierA_target_fibs × (i). S7 ⇒ parent चा पहिला leg (उपलब्ध असेल तर)."""
    ref = _len0(sig.parent_points) if sig.setup == "S7" and sig.parent_pattern in ("impulse", "lead_diag") else None
    ref = ref or _len0(sig.points)
    if not ref:
        return []
    return [sig.extreme + sig.trade_dir * f * ref for f in s["tierA_target_fibs"]]


def c_zone_base(sig):
    """Tier B: (B end, A) — C zone चा आधार; लागू नसेल ⇒ (None, None)."""
    if sig.setup == "S8" and sig.pattern == "wxy":
        base, a = sig.extreme, _len0(sig.points)                    # wxy X संपला ⇒ Y ≈ स्वतःचा W
    elif sig.setup in C_ZONE_SELF:
        base, a = sig.extreme, _len0(sig.points)
    elif sig.setup in C_ZONE_PARENT_FROM_EXTREME:
        base, a = sig.extreme, _len0(sig.parent_points)
    elif sig.setup in C_ZONE_PARENT_B and len(sig.parent_points) >= 3:
        base, a = sig.parent_points[2], _len0(sig.parent_points)
    else:
        return None, None
    return (base, a) if a else (None, None)


def c_zone(sig, s):
    """Tier B C zone (zone_fibs_c × A, B end पासून) — [levels] किंवा []."""
    base, a = c_zone_base(sig)
    return [] if base is None else [base + sig.trade_dir * f * a for f in s["zone_fibs_c"]]


def progressive_trigger(sig):
    """(i) चं टोक — spot ने ओलांडल्यावर hard inv = correction end. लागू नसेल ⇒ None."""
    if sig.setup in PROGRESSIVE and len(sig.points) >= 2:
        return sig.points[1]
    return None


def emergency_check(st, spot_extreme):
    """क्रम 0 — दर tick/poll वर (state बदलत नाही): spot ने short strike **ओलांडला** (touch नव्हे) ⇒ True."""
    k = st.plan["short_k"]
    return (spot_extreme < k) if st.sig.trade_dir > 0 else (spot_extreme > k)


def sd_remaining(spot, iv, minutes_left):
    return spot * iv * math.sqrt(max(minutes_left, 0.0) / 375.0 / 252.0) if iv else 0.0


def evaluate(st: TradeState, ctx, s):
    """**TTF bar close वरच** (state: bars, H, partial, inv बदलतो) — tick/poll वर फक्त emergency_check.
    ctx keys (E4/E6 loop मोजतो; नसलेली key ⇒ ती अट लागू नाही):
      bar (o,h,l,c) — TTF bar spot · mark (bar close ला spread debit) · mark_worst (intrabar सर्वात वाईट debit)
      hard_broken, parent_broken, soft_broken, lower_broken (real break, या bar पर्यंत) · opposite_reversal (C zone मध्ये)
      opposite_signal, next_motive_complete · expiry_day (bool), minutes_left (expiry दिवशी close पर्यंत), past_exit_time (bool), iv
      c_zone_accepted (C ने zone real break ने ओलांडला) · trail_level (entry नंतरचा शेवटचा confirmed D−1 sub-wave टोक)
    रिटर्न {"exit": कारण|None, "priority": n, "partial_lots": n, "move_inv": level|None, "alerts": [...]}"""
    sig, d = st.sig, st.sig.trade_dir
    o, h, l, c = ctx["bar"]
    out = {"exit": None, "priority": None, "partial_lots": 0, "move_inv": None, "alerts": []}
    tier = sig.tier

    def done(reason, prio):
        out.update(exit=reason, priority=prio)
        return out

    st.bars += 1
    if (c > sig.sub_origin) if d > 0 else (c < sig.sub_origin):
        st.crossed_h = True
    short_k = st.plan["short_k"]
    # 0 — emergency (intrabar)
    if s["emergency_spot_cross_short"] and emergency_check(st, l if d > 0 else h):
        return done("emergency_short_strike", 0)
    # 1 — hard invalidation (own degree) / parent cascade
    if ctx.get("hard_broken"):
        return done("hard_inv", 1)
    if ctx.get("parent_broken"):
        return done("parent_inv_cascade", 1)
    # 2 — premium stop
    mark = ctx.get("mark")
    worst = ctx.get("mark_worst", mark) if s["hard_stop_eval"] == "intrabar" else mark
    if worst is not None and worst >= s["hard_stop_mult"] * st.entry_credit:
        return done("premium_stop", 2)
    # 3 — soft timing stop
    if ctx.get("soft_broken"):
        act = s["soft_stop_action"]
        if act == "exit":
            return done("soft_stop", 3)
        if act == "reduce" and st.lots_open > 1 and not st.soft_reduced:
            st.soft_reduced = True
            out["partial_lots"] = st.lots_open // 2
        out["alerts"].append("soft_stop")
    # lower degree warning
    if ctx.get("lower_broken"):
        act = s["lower_inv_action"]
        if act == "exit":
            return done("lower_inv", 3)
        if act == "reduce" and st.lots_open > 1 and not out["partial_lots"] and not st.lower_reduced:
            st.lower_reduced = True
            out["partial_lots"] = st.lots_open // 2
        out["alerts"].append("lower_inv")
    # progressive inv (नियम क्रमाने: (i) टोक ओलांडलं ⇒ (i)-(ii) count चा inv = (ii) end)
    pt = progressive_trigger(sig)
    if s["progressive_inv"] and pt is not None and not st.inv_moved and ((h >= pt) if d > 0 else (l <= pt)):
        st.inv_moved = True
        st.hard_inv = sig.extreme
        out["move_inv"] = sig.extreme
    # trailing (§9 क्रम 4 / §14 Q4): Tier A T1 नंतर उरलेले lots, किंवा Tier B चा C zone acceptance ने ओलांडला ⇒ hold +
    # शेवटच्या confirmed sub-wave च्या टोकावर inv (फक्त trade च्या बाजूने सरकतो)
    tr = ctx.get("trail_level")
    if tr is not None and ((tier == "A" and st.partial_done) or (tier == "B" and ctx.get("c_zone_accepted"))):
        if (tr > st.hard_inv) if d > 0 else (tr < st.hard_inv):
            st.hard_inv = tr
            out["move_inv"] = tr
    # 4 — target
    base, a = c_zone_base(sig) if tier == "B" else (None, None)
    if tier == "B" and base is not None:
        if ctx.get("c_zone_accepted"):
            pass                                                                # C zone ओलांडला ⇒ target नाही, फक्त trailing
        elif s["tierB_exit_mode"] == "opposite_reversal" and ctx.get("opposite_reversal"):
            return done("c_zone_opposite_reversal", 4)
        elif s["tierB_exit_mode"] == "fixed_mult":
            tgt = base + d * s["tierB_target_mult"] * a
            if (h >= tgt) if d > 0 else (l <= tgt):
                return done("c_zone_fixed_target", 4)
    elif tier in ("A", "B") and not st.partial_done:
        # Tier A; आणि C zone नसलेले Tier B (D+2 विरुद्ध / corrective parent मुळे A→B झालेले S1–S4/S9/S10) ⇒ T1 वर पूर्ण exit (bounded)
        tg = tier_a_targets(sig, s)
        tol = s["target_tol_atr"] * ctx.get("atr", 0.0)
        if tg and ((h >= tg[0] - tol) if d > 0 else (l <= tg[0] + tol)):
            if tier == "B" or s["tierA_target_action"] == "exit_all" or st.lots_open <= 1:
                return done("tierA_target" if tier == "A" else "t1_target_bounded", 4)
            st.partial_done = True
            out["partial_lots"] = max(out["partial_lots"], st.lots_open // 2)
    # 5 — profit % credit
    if mark is not None and st.entry_credit > 0:
        captured = (st.entry_credit - mark) / st.entry_credit * 100.0
        if captured >= s["tp_pct_credit"][TIER_IDX[tier]]:
            return done("profit_pct", 5)
    # 6 — progress time
    pb = s["progress_bars_mult"] * sig.bars_last_subleg
    if pb > 0 and st.bars >= math.ceil(pb) and not st.crossed_h:
        return done("progress_time", 6)
    # 7 — expiry day
    if ctx.get("expiry_day") and ctx.get("past_exit_time"):
        itm = (c < short_k) if d > 0 else (c > short_k)
        if not ctx.get("iv") or ctx.get("minutes_left") is None:
            return done("expiry_day_no_iv", 7)                                  # SD मोजता येत नाही ⇒ सुरक्षित बाजू: exit
        sd = sd_remaining(c, ctx["iv"], ctx["minutes_left"])
        if itm or abs(c - short_k) < s["expiry_hold_min_dist_sd"] * sd:
            return done("expiry_day_risk", 7)
    # 8 — thesis complete
    if ctx.get("opposite_signal") or ctx.get("next_motive_complete"):
        return done("thesis_complete", 8)
    return out


def c_zone_reversal(bars, j, sig, s, tol, min_start=0):
    """Tier B exit चा पुरावा: C zone मध्ये **उलट** दिशेचा logical reversal (entry सारखेच नियम, mirror) — bar j वर."""
    from .reversal import evaluate as rev
    from .settings import core_candle
    zone = c_zone(sig, s)
    if not zone:
        return False
    return bool(rev(bars, j, -sig.trade_dir, zone, tol, core_candle(s), min_start=min_start)["ok"])   # C1 candle प्रयोग exit बदलत नाहीत
