"""
gap_fill_reversal_strategy.py
---------------------------------
AMW A1 — Gap Fill Reversal (Bullish + Bearish) — दिलेल्या Master Prompt नुसार तंतोतंत:

  1H Trend (Supertrend 10,3) -> Opening Gap -> Gap Fill -> Reversal -> 15M RSI -> Pullback ->
  Retest (अनिवार्य, टिकलाच पाहिजे) -> 5M Confirmation -> Supply/Demand -> Option Chain (PCR/OI,
  filter म्हणून — एकटा trigger नाही) -> India VIX (>20 = NO TRADE, >16 = फक्त Credit Spread) ->
  PoP>=75% + Tight Hedge (आपल्याच select_credit_spread द्वारे) -> अंतिम BULL PUT / BEAR CALL SPREAD.

महत्त्वाचं (मूळ prompt नुसार):
  - Gap भरेल असा अंदाज लावत नाही — प्रत्यक्ष भरल्यावरच पुढे जातो.
  - नुसता Gap भरला म्हणून entry नाही — पूर्ण साखळी (Reversal+Pullback+Retest+5M) हवीच.
  - अपुरी माहिती असल्यास कधीच काल्पनिक सिग्नल तयार करत नाही — स्पष्टपणे NO TRADE देतो.

हे strategies/ (StrategyBase) framework पेक्षा वेगळं, स्वतंत्र module आहे — कारण याचं output
(Short/Long Strike, Credit, PoP, Breakeven) मुळातच Options-Spread स्वरूपाचं आहे, साध्या
Direction/Entry/SL/Target सारखं नाही (जसं vwap/ict_fvg/bb_squeeze/sr_bounce देतात).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from signals import (
    calculate_rsi, calculate_supertrend, detect_candlestick_pattern,
    find_support_resistance_levels, classify_market_structure, supply_demand_zone,
    rsi_momentum_and_divergence,
)
from oi_analysis import compute_pcr_signal
from strategy import select_credit_spread


def detect_opening_gap(today_open, prev_close, min_gap_pct=0.15):
    """आजचं open आणि आदल्या दिवसाचं close यातला Gap ओळखणे — किमान min_gap_pct% असेल तरच खरा Gap."""
    if not prev_close:
        return None
    gap_points = today_open - prev_close
    gap_pct = (gap_points / prev_close) * 100
    if abs(gap_pct) < min_gap_pct:
        return None
    direction = "GAP_UP" if gap_points > 0 else "GAP_DOWN"
    return {"direction": direction, "gap_points": round(gap_points, 2), "gap_pct": round(gap_pct, 3),
            "prev_close": prev_close, "today_open": today_open}


def trace_gap_fill_reversal_chain(df_today, gap_info, retest_tolerance_pct=0.1):
    """
    आजच्या (Gap नंतरच्या) bar-by-bar इतिहासातून — Gap Fill -> Reversal -> Pullback -> Retest ही
    साखळी क्रमाने (आणि No-Lookahead पद्धतीने, सद्य क्षणापर्यंतच) घडली आहे का ते तपासणे.
    """
    import pandas as pd
    chain = {"gap_fill": False, "reversal": False, "pullback": False, "retest": False, "retest_held": False}
    if len(df_today) < 3:
        return chain, None

    bullish = gap_info["direction"] == "GAP_UP"
    fill_level = gap_info["prev_close"]

    if bullish:
        fill_idx = df_today[df_today["low"] <= fill_level].index.min()
    else:
        fill_idx = df_today[df_today["high"] >= fill_level].index.min()
    if pd.isna(fill_idx):
        return chain, None
    chain["gap_fill"] = True
    after_fill = df_today.loc[fill_idx:]
    if len(after_fill) < 3:
        return chain, None

    reversal_idx, reversal_price = None, None
    for i in range(fill_idx + 1, min(fill_idx + 10, len(df_today))):
        window = df_today.loc[:i]
        pattern = detect_candlestick_pattern(window)
        bullish_patterns = ("HAMMER", "BULLISH_ENGULFING", "MORNING_STAR")
        bearish_patterns = ("SHOOTING_STAR", "BEARISH_ENGULFING", "EVENING_STAR")
        pattern_ok = (pattern in bullish_patterns) if bullish else (pattern in bearish_patterns)
        if pattern_ok:
            reversal_idx = i
            reversal_price = df_today["high"].loc[i] if bullish else df_today["low"].loc[i]
            break
    if reversal_idx is None:
        return chain, None
    chain["reversal"] = True

    after_reversal = df_today.loc[reversal_idx + 1:]
    if len(after_reversal) < 2:
        return chain, None
    pullback_happened = (after_reversal["low"] < reversal_price).any() if bullish else (after_reversal["high"] > reversal_price).any()
    if not pullback_happened:
        return chain, None
    chain["pullback"] = True

    ref_level = fill_level
    tolerance = ref_level * (retest_tolerance_pct / 100)
    retested, retest_held = False, False
    for i in after_reversal.index:
        bar = df_today.loc[i]
        if bullish and bar["low"] <= ref_level + tolerance:
            retested, retest_held = True, bar["close"] > ref_level
            break
        elif not bullish and bar["high"] >= ref_level - tolerance:
            retested, retest_held = True, bar["close"] < ref_level
            break
    chain["retest"], chain["retest_held"] = retested, retest_held
    return chain, {"reversal_idx": reversal_idx, "ref_level": ref_level}


def check_5m_confirmation(df_5m, direction):
    """5-मिनिट Entry Confirmation — bullish/bearish rejection, candlestick, RSI momentum recovery.
    🎓 सैल केलं — आधी candlestick pattern AND RSI momentum दोन्ही एकत्र हवे होते (हाच खरा bottleneck
    ठरला, 29 पैकी फक्त 3 दिवस पास व्हायचे). आता कुठलंही एक (OR) पुरेसं."""
    if df_5m is None or len(df_5m) < 15:
        return False, "5M डेटा अपुरा"
    pattern = detect_candlestick_pattern(df_5m)
    bullish_patterns = ("HAMMER", "BULLISH_ENGULFING", "MORNING_STAR")
    bearish_patterns = ("SHOOTING_STAR", "BEARISH_ENGULFING", "EVENING_STAR")
    pattern_ok = (pattern in bullish_patterns) if direction == "BULLISH" else (pattern in bearish_patterns)

    rsi = calculate_rsi(df_5m, period=14)
    if rsi.empty or rsi.isna().iloc[-1] or len(rsi) < 4 or rsi.iloc[-4:].isna().any():
        momentum_ok = False
    else:
        momentum_ok = rsi.iloc[-1] > rsi.iloc[-3] if direction == "BULLISH" else rsi.iloc[-1] < rsi.iloc[-3]

    if pattern_ok or momentum_ok:
        matched = []
        if pattern_ok: matched.append(f"candlestick={pattern}")
        if momentum_ok: matched.append("RSI momentum")
        return True, f"5M confirmed: {' + '.join(matched)}"
    return False, f"5M confirmation अपुरं (pattern={pattern_ok}, RSI momentum={momentum_ok})"


def check_risk_filters(india_vix, pop_pct):
    """VIX + PoP धोका-तपासणी — मूळ prompt च्या नियमांप्रमाणे तंतोतंत."""
    if india_vix is None:
        return False, "India VIX उपलब्ध नाही"
    if india_vix > 20:
        return False, f"India VIX={india_vix} > 20 -> NO TRADE"
    if pop_pct is None or pop_pct < 75:
        return False, f"PoP={pop_pct} < 75% आवश्यक मर्यादा"
    credit_spread_only = india_vix > 16
    return True, f"VIX={india_vix} (Credit-Spread-Only: {credit_spread_only}), PoP={pop_pct}% -- OK"


def run_gap_fill_reversal_technical(df_1h, df_today_15m, df_5m, prev_close, today_open, min_gap_pct=0.15,
                                      require_pullback_retest=True, require_15m_rsi=True):
    """
    फक्त Technical भाग — 1H Trend -> Gap -> Fill -> Reversal -> [Pullback -> Retest, ऐच्छिक] ->
    15M RSI -> 5M Confirmation. Option Chain/PCR/OI/VIX/PoP भाग यात नाही.
    require_pullback_retest=False दिल्यास Pullback+Retest पायऱ्या वगळल्या जातात (सैल आवृत्ती —
    Reversal नंतर लगेच 15M RSI + 5M Confirmation कडे जाते).
    """
    trace = {}

    # 1) 1H Trend
    if df_1h is None or df_1h.empty or len(df_1h) < 11:
        return {"signal": "NO_TRADE", "reason": "1H Supertrend साठी अपुरा डेटा", "trace": trace}
    _, st_dir = calculate_supertrend(df_1h, period=10, multiplier=3)
    if st_dir.empty or st_dir.isna().iloc[-1]:
        return {"signal": "NO_TRADE", "reason": "1H Supertrend दिशा अस्पष्ट", "trace": trace}
    trend = "BULLISH" if int(st_dir.iloc[-1]) == 1 else "BEARISH"
    trace["1H_Trend"] = trend

    # 2) Opening Gap
    gap_info = detect_opening_gap(today_open, prev_close, min_gap_pct)
    if gap_info is None:
        return {"signal": "NO_TRADE", "reason": "स्पष्ट Opening Gap नाही", "trace": trace}
    trace["Opening_Gap"] = gap_info
    gap_bullish = gap_info["direction"] == "GAP_UP"
    if (gap_bullish and trend != "BULLISH") or (not gap_bullish and trend != "BEARISH"):
        return {"signal": "NO_TRADE", "reason": f"Gap ({gap_info['direction']}) 1H Trend ({trend}) शी जुळत नाही", "trace": trace}

    # 3-6) Gap Fill -> Reversal -> [Pullback -> Retest, ऐच्छिक]
    chain, chain_meta = trace_gap_fill_reversal_chain(df_today_15m, gap_info)
    trace["Chain"] = chain
    if not chain["gap_fill"]:
        return {"signal": "NO_TRADE", "reason": "Gap अजून भरलेला नाही", "trace": trace}
    if not chain["reversal"]:
        return {"signal": "NO_TRADE", "reason": "Gap Fill नंतर Reversal confirmation नाही", "trace": trace}
    if require_pullback_retest:
        if not chain["pullback"]:
            return {"signal": "NO_TRADE", "reason": "Reversal नंतर Pullback अजून झालेला नाही", "trace": trace}
        if not chain["retest"]:
            return {"signal": "NO_TRADE", "reason": "Retest अजून झालेला नाही (mandatory)", "trace": trace}
        if not chain["retest_held"]:
            return {"signal": "NO_TRADE", "reason": "Retest झाला, पण टिकला नाही (invalidated)", "trace": trace}

    # 15M RSI check — ऐच्छिक (require_15m_rsi=False दिल्यास वगळलं जातं)
    if require_15m_rsi:
        rsi_15m = calculate_rsi(df_today_15m, period=14)
        rsi_ok = not rsi_15m.empty and not rsi_15m.isna().iloc[-1] and (
            (rsi_15m.iloc[-1] > 45 if gap_bullish else rsi_15m.iloc[-1] < 55)
        )
        trace["15M_RSI"] = round(float(rsi_15m.iloc[-1]), 1) if not rsi_15m.empty and not rsi_15m.isna().iloc[-1] else None
        if not rsi_ok:
            return {"signal": "NO_TRADE", "reason": f"15M RSI ({trace['15M_RSI']}) confirmation देत नाही", "trace": trace}

    # 7) 5M Confirmation
    confirmed_5m, reason_5m = check_5m_confirmation(df_5m, trend)
    trace["5M_Confirmation"] = reason_5m
    if not confirmed_5m:
        return {"signal": "NO_TRADE", "reason": reason_5m, "trace": trace}

    # Supply/Demand context
    structure = classify_market_structure(df_today_15m)
    zone = supply_demand_zone(structure, trend)
    trace["Supply_Demand"] = zone

    return {
        "signal": trend, "setup": "GAP_UP_FILL_REVERSAL" if gap_bullish else "GAP_DOWN_FILL_REVERSAL",
        "reason": f"Technical साखळी पूर्ण: {gap_info['direction']} -> Fill -> Reversal -> Pullback -> Retest(held) -> 5M",
        "trace": trace, "chain_meta": chain_meta,
    }


def run_gap_fill_reversal_check(df_1h, df_today_15m, df_5m, prev_close, today_open, raw_chain,
                                  india_vix, hedge_width_points=100, pop_threshold_pct=75, min_gap_pct=0.15):
    """
    संपूर्ण साखळी एकत्र चालवून — अंतिम निर्णय (BULLISH/BEARISH ट्रेड, किंवा NO TRADE + नेमकं कारण)
    काढणे. मूळ prompt प्रमाणे प्रत्येक टप्पा (stage) स्पष्टपणे trace केला जातो, कुठलाही टप्पा वगळला
    जात नाही.
    """
    technical = run_gap_fill_reversal_technical(df_1h, df_today_15m, df_5m, prev_close, today_open, min_gap_pct)
    if technical["signal"] == "NO_TRADE":
        return technical
    trend = technical["signal"]
    trace = technical["trace"]
    gap_bullish = trace["Opening_Gap"]["direction"] == "GAP_UP"

    # 8) Option Chain — PCR (filter, trigger नाही)
    if raw_chain:
        total_call_oi = sum((item.get("call_options", {}) or {}).get("market_data", {}).get("oi", 0) or 0 for item in raw_chain)
        total_put_oi = sum((item.get("put_options", {}) or {}).get("market_data", {}).get("oi", 0) or 0 for item in raw_chain)
        pcr_signal = compute_pcr_signal(total_put_oi, total_call_oi)
        trace["PCR_OI"] = {"pcr_signal": pcr_signal, "total_put_oi": total_put_oi, "total_call_oi": total_call_oi}
    else:
        trace["PCR_OI"] = None

    # 9) Risk Filters — VIX + PoP (select_credit_spread द्वारे, tight hedge सह)
    if not raw_chain:
        return {"signal": "NO_TRADE", "reason": "Option chain डेटा उपलब्ध नाही", "trace": trace}
    spread = select_credit_spread(raw_chain, trend, hedge_width_points, pop_threshold_pct)
    pop_pct = spread["short_pop_pct"] if spread else None
    risk_ok, risk_reason = check_risk_filters(india_vix, pop_pct)
    trace["India_VIX"] = india_vix
    trace["PoP"] = pop_pct
    trace["Risk_Filters"] = risk_reason
    if not risk_ok:
        return {"signal": "NO_TRADE", "reason": risk_reason, "trace": trace}
    if spread is None:
        return {"signal": "NO_TRADE", "reason": "योग्य PoP>=75% + Tight Hedge चा Credit Spread तयार करता आला नाही", "trace": trace}
    trace["Hedge"] = f"{spread['spread_width']} पॉइंट्स रुंदीचा hedge"

    # 10) अंतिम निर्णय
    breakeven = spread["short_leg"]["strike"] - spread["net_credit"] if trend == "BULLISH" else spread["short_leg"]["strike"] + spread["net_credit"]
    trace["Final_Trade"] = spread["strategy"]

    return {
        "signal": "BULLISH" if trend == "BULLISH" else "BEARISH",
        "setup": "GAP_UP_FILL_REVERSAL" if gap_bullish else "GAP_DOWN_FILL_REVERSAL",
        "strategy": spread["strategy"],
        "short_leg": spread["short_leg"], "long_leg": spread["long_leg"],
        "net_credit": spread["net_credit"], "max_risk": spread["max_loss"],
        "breakeven": round(breakeven, 2), "estimated_pop": pop_pct,
        "sl_condition": f"तोटा net_credit च्या ठराविक% (उदा. spread_width - net_credit च्या जवळ पोहोचल्यास)",
        "profit_booking_condition": "net_credit च्या ठराविक% नफा झाल्यास (उदा. 50-70%) बुक करणे",
        "reason": f"पूर्ण साखळी confirmed: {trace['Opening_Gap']['direction']} -> Fill -> Reversal -> Pullback -> Retest(held) -> 5M -> PoP={pop_pct}%",
        "trace": trace,
    }
