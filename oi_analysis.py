"""Professional OI analysis: OI-Price Matrix, PCR, Max Pain, Rollover, and the OI Confirmation Gates."""
import datetime
import math
import sqlite3

from config import DB_PATH


def find_psychological_level(price, direction, round_to=500):
    """
    दिलेल्या किमतीपासून पुढच्या (त्या दिशेला अपेक्षित) round-number psychological level काढणे —
    BEARISH: वर (ceiling) — जिथे resistance अपेक्षित. BULLISH: खाली (floor) — जिथे support अपेक्षित.
    डीफॉल्ट 500 च्या पटीत (24000/24500/25000 सारखे) — 100 च्या पटीपेक्षा जास्त लक्षणीय मानले जातात.
    """
    if direction == "BEARISH":
        level = math.ceil(price / round_to) * round_to
        if level == price:
            level += round_to
    else:
        level = math.floor(price / round_to) * round_to
        if level == price:
            level -= round_to
    return level


def compute_oi_signal_with_hysteresis(current_diff, delta_diff, prev_delta_diff, prev_signal, hysteresis_threshold_pct=20):
    """
    OI Diff सिग्नल — प्रथम पातळी (level) + गती (momentum) वरून कच्चा (raw) सिग्नल ठरवणे, मग तो मागच्या
    प्रत्यक्ष दाखवलेल्या सिग्नलपेक्षा वेगळा असेल तरच लागू करणे — पण केवळ delta_diff मागच्या delta_diff
    पेक्षा किमान hysteresis_threshold_pct% बदलला असेल तरच (नाहीतर आधीचाच सिग्नल कायम — छोट्या,
    noise-सदृश बदलांमुळे उगाच सिग्नल भिरभिरणं (flip-flop) टाळण्यासाठी).
    मागचा delta_diff बरोबर 0 असेल तर % काढताच येत नाही — त्यावेळी सुरक्षित बाजूने सिग्नल बदलला जात नाही.
    """
    if current_diff > 0 and delta_diff > 0:
        raw_signal = "🟢 BULLISH"
    elif current_diff < 0 and delta_diff < 0:
        raw_signal = "🔴 BEARISH"
    elif current_diff > 0 and delta_diff <= 0:
        raw_signal = "🟡 BULLISH (Weakening)"
    elif current_diff < 0 and delta_diff >= 0:
        raw_signal = "🟠 BEARISH (Weakening)"
    else:
        raw_signal = "⚪ NEUTRAL"

    if prev_signal is None or prev_delta_diff is None:
        return raw_signal
    if prev_delta_diff == 0:
        return prev_signal
    pct_change = abs(delta_diff - prev_delta_diff) / abs(prev_delta_diff) * 100
    if pct_change >= hysteresis_threshold_pct:
        return raw_signal
    return prev_signal


def check_oi_wall_confirmation(raw_chain, symbol, psychological_level, direction, step=50):
    """
    दिलेल्या psychological level च्या जवळच्या strike वर OI Wall (Short Buildup) आहे का ते तपासणे —
    Price Action रणनीतीसाठी हार्ड गेट (Order Block + Retest + Pattern सोबतच, हेही खरं असेल तरच एंट्री).
    BEARISH: त्या strike च्या Call (CE) मध्ये आजचा Chg OI सकारात्मक (नवीन विक्री, resistance building) हवी.
    BULLISH: त्या strike च्या Put (PE) मध्ये आजचा Chg OI सकारात्मक (नवीन विक्री, support building) हवी.
    Baseline OI साठी day_baseline_oi हेच table वापरलं जातं — Option Chain टेबलमधल्या Chg OI शी सुसंगत.
    """
    target_strike = round(psychological_level / step) * step
    item = next((it for it in raw_chain if it.get("strike_price") == target_strike), None)
    if item is None:
        return False, {"target_strike": target_strike, "reason": "strike सापडला नाही"}

    side = "call_options" if direction == "BEARISH" else "put_options"
    opt = item.get(side, {}) or {}
    mkt = opt.get("market_data", {}) or {}
    current_oi = int(mkt.get("oi") or 0)

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    col = "initial_ce_oi" if direction == "BEARISH" else "initial_pe_oi"
    cur.execute(f"SELECT {col} FROM day_baseline_oi WHERE symbol=? AND strike=? AND trade_date=?", (symbol, target_strike, today_str))
    row = cur.fetchone()
    conn.close()
    baseline_oi = row[0] if row else current_oi

    chg_oi = current_oi - baseline_oi
    confirmed = chg_oi > 0
    return confirmed, {
        "target_strike": target_strike, "current_oi": current_oi, "baseline_oi": baseline_oi,
        "chg_oi": chg_oi, "side": "CE" if direction == "BEARISH" else "PE",
    }

def get_latest_oi_signal(symbol):
    """आजच्या दिवसातील Put-Call OI Diff Tracker चा सर्वात अलीकडचा सिग्नल मिळवणे (OI Confirmation Gate साठी)."""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT signal FROM oi_diff_snapshots WHERE symbol=? AND trade_date=? ORDER BY snapshot_time DESC LIMIT 1",
        (symbol, today_str),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def infer_direction_from_strategy(strategy_name):
    """स्ट्रॅटेजीच्या नावावरून तिची दिशा ठरवणे — Iron Condor/Butterfly साठी None (त्या non-directional असतात)."""
    if "BULL" in strategy_name:
        return "BULLISH"
    if "BEAR" in strategy_name:
        return "BEARISH"
    return None

def check_oi_confirmation(direction, oi_signal, strictness="A"):
    """
    Direction Engine च्या दिशेशी OI Diff Tracker सिग्नल जुळतो का तपासणे — Intraday एंट्रीसाठी अतिरिक्त गेट.
    Option A (Conflict Filter, डीफॉल्ट): फक्त सक्रिय विरोध (उलट दिशेचा OI सिग्नल) असेल तरच ब्लॉक —
    Weakening किंवा Neutral पास होतात (OI किंमतीच्या मागे असू शकतो, हे सामान्य आहे).
    Option B (Strict Confirmation): फक्त पूर्ण जुळणी (Weakening सुद्धा नाही) असेल तरच पास.
    OI डेटा उपलब्ध नसल्यास गेट वगळला जातो (ब्लॉक होत नाही).
    """
    if oi_signal is None:
        return True, "OI data unavailable — gate skipped"
    if direction == "BULLISH":
        ok = ("BEARISH" not in oi_signal) if strictness == "A" else (oi_signal == "🟢 BULLISH")
    elif direction == "BEARISH":
        ok = ("BULLISH" not in oi_signal) if strictness == "A" else (oi_signal == "🔴 BEARISH")
    else:
        ok = True
    return ok, oi_signal

def _extract_oi_ltp(item, side):
    """raw_chain मधील एका strike-item मधून दिलेल्या side (call_options/put_options) ची OI व LTP काढणे."""
    opt = item.get(side, {}) or {}
    mkt = opt.get("market_data", {}) or {}
    oi = mkt.get("oi")
    ltp = mkt.get("ltp")
    return (int(oi) if oi is not None else 0), (float(ltp) if ltp is not None else None)

def get_previous_day_total_oi(symbol):
    """आजच्या आधीच्या शेवटच्या ट्रेडिंग दिवसाचा शेवटचा एकूण (Call+Put) OI मिळवणे — oi_diff_snapshots मधून."""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """SELECT total_call_oi, total_put_oi FROM oi_diff_snapshots
           WHERE symbol=? AND trade_date < ? ORDER BY trade_date DESC, snapshot_time DESC LIMIT 1""",
        (symbol, today_str),
    )
    row = cur.fetchone()
    conn.close()
    return (row[0] + row[1]) if row else None

def compute_oi_price_matrix(current_total_oi, prev_total_oi, current_price, prev_price):
    """
    Long Buildup / Short Buildup / Short Covering / Long Unwinding — किंमत आणि एकूण OI दोन्हीच्या
    दिशेवरून पोझिशनिंगचा खरा प्रकार ठरवणे. फक्त 'OI वाढला' इतकंच बघण्यापेक्षा जास्त माहितीपूर्ण —
    कारण OI वाढ नवीन पोझिशनमुळे (मजबूत) की जुनी बंद होण्यामुळे (तात्पुरती) हे वेगळं करतं.
    """
    if None in (current_total_oi, prev_total_oi, current_price, prev_price):
        return {"category": "INSUFFICIENT_DATA", "bias": "NEUTRAL", "strength": "-"}
    price_up = current_price > prev_price
    oi_up = current_total_oi > prev_total_oi
    if price_up and oi_up:
        return {"category": "LONG_BUILDUP", "bias": "BULLISH", "strength": "Strong"}
    if (not price_up) and oi_up:
        return {"category": "SHORT_BUILDUP", "bias": "BEARISH", "strength": "Strong"}
    if price_up and (not oi_up):
        return {"category": "SHORT_COVERING", "bias": "BULLISH", "strength": "Weak/Temporary"}
    return {"category": "LONG_UNWINDING", "bias": "BEARISH", "strength": "Weak/Temporary"}

def compute_pcr_signal(total_put_oi, total_call_oi, high_threshold=1.5, low_threshold=0.5):
    """
    PCR (Put-Call Ratio) कधीकधी Contrarian वाचला जातो: टोकाच्या पातळीवर उलट दिशेचा इशारा देतो —
    खूप जास्त PCR = भरपूर Puts विकले गेलेत = मजबूत सपोर्ट = अनेकदा उलट तेजीचा (bullish) संकेत.
    खूप कमी PCR = भरपूर Calls विकले गेलेत = मजबूत रेझिस्टन्स = अनेकदा उलट मंदीचा (bearish) संकेत.
    """
    if not total_call_oi:
        return None, "NEUTRAL"
    pcr = round(total_put_oi / total_call_oi, 2)
    if pcr >= high_threshold:
        return pcr, "BULLISH"
    if pcr <= low_threshold:
        return pcr, "BEARISH"
    return pcr, "NEUTRAL"

def compute_max_pain(raw_chain):
    """
    प्रत्येक संभाव्य expiry-settlement strike साठी Option Writers चं एकूण नुकसान काढून,
    सगळ्यात कमी नुकसान असलेला strike (Max Pain) शोधणे — theory नुसार किंमत expiry जवळ या
    strike कडे झुकते, कारण मोठे option writers ती तिकडे ढकलण्याचा प्रयत्न करतात असं मानलं जातं.
    """
    strikes_data = []
    for item in raw_chain:
        strike = item.get("strike_price")
        if strike is None:
            continue
        ce_oi, _ = _extract_oi_ltp(item, "call_options")
        pe_oi, _ = _extract_oi_ltp(item, "put_options")
        strikes_data.append({"strike": strike, "ce_oi": ce_oi, "pe_oi": pe_oi})

    if not strikes_data:
        return None

    candidate_strikes = sorted({d["strike"] for d in strikes_data})
    min_pain, max_pain_strike = None, None
    for settlement in candidate_strikes:
        total_pain = 0
        for d in strikes_data:
            k = d["strike"]
            if settlement > k:
                total_pain += (settlement - k) * d["ce_oi"]
            elif settlement < k:
                total_pain += (k - settlement) * d["pe_oi"]
        if min_pain is None or total_pain < min_pain:
            min_pain, max_pain_strike = total_pain, settlement
    return max_pain_strike

def compute_rollover_proxy(near_chain, next_chain, atm_strike):
    """
    खरा Futures Rollover % नाही (हे सिस्टीम Futures नाही तर फक्त Options डेटा वापरते) — पण दोन प्रॉक्सींवरून
    रोलओव्हर-सदृश कल काढणे:
    1. OI Distribution: पुढच्या expiry मध्ये आधीच किती OI जमा झालंय (एकूणच्या तुलनेत %)
    2. Cost-of-Carry: ATM वर Put-Call Parity ने काढलेली Synthetic Future किंमत — जवळची expiry वि पुढची expiry
       (पुढची expiry प्रीमियमवर ट्रेड होत असेल तर बाजाराचा कल तेजीकडे मानला जातो, आणि उलट)
    """
    def total_oi(chain):
        total = 0
        for item in chain:
            ce_oi, _ = _extract_oi_ltp(item, "call_options")
            pe_oi, _ = _extract_oi_ltp(item, "put_options")
            total += ce_oi + pe_oi
        return total

    def synthetic_future(chain, strike):
        for item in chain:
            if item.get("strike_price") == strike:
                _, ce_ltp = _extract_oi_ltp(item, "call_options")
                _, pe_ltp = _extract_oi_ltp(item, "put_options")
                if ce_ltp is not None and pe_ltp is not None:
                    return strike + ce_ltp - pe_ltp
        return None

    if not near_chain or not next_chain:
        return None

    near_total = total_oi(near_chain)
    next_total = total_oi(next_chain)
    rollover_pct = round((next_total / (near_total + next_total)) * 100, 1) if (near_total + next_total) > 0 else None

    near_synthetic = synthetic_future(near_chain, atm_strike)
    next_synthetic = synthetic_future(next_chain, atm_strike)
    cost_of_carry = round(next_synthetic - near_synthetic, 2) if (near_synthetic is not None and next_synthetic is not None) else None

    bias = "NEUTRAL"
    if cost_of_carry is not None:
        if cost_of_carry > 0:
            bias = "BULLISH"
        elif cost_of_carry < 0:
            bias = "BEARISH"

    return {
        "rollover_pct": rollover_pct, "cost_of_carry": cost_of_carry, "bias": bias,
        "near_expiry_total_oi": near_total, "next_expiry_total_oi": next_total,
    }

def swing_oi_gate(pipeline_direction, oi_price_matrix, pcr_bias, max_pain_strike, current_price, rollover_info, max_opposing=1):
    """
    Swing साठी OI-Price Matrix + PCR Contrarian + Max Pain + Rollover एकत्र करून एक गेट तयार करणे.
    तत्त्व Intraday च्या Option A (Conflict Filter) सारखंच — सक्रिय विरोधी सिग्नल्सची संख्या max_opposing
    पेक्षा जास्त असेल तरच ब्लॉक; कमजोर/तटस्थ सिग्नल्स ब्लॉक करत नाहीत.
    """
    signals = []
    if oi_price_matrix and oi_price_matrix["bias"] != "NEUTRAL":
        signals.append(("OI-Price Matrix", oi_price_matrix["bias"]))
    if pcr_bias and pcr_bias != "NEUTRAL":
        signals.append(("PCR Contrarian", pcr_bias))
    if max_pain_strike is not None and current_price:
        mp_bias = "BEARISH" if max_pain_strike < current_price else ("BULLISH" if max_pain_strike > current_price else "NEUTRAL")
        if mp_bias != "NEUTRAL":
            signals.append(("Max Pain", mp_bias))
    if rollover_info and rollover_info.get("bias") != "NEUTRAL":
        signals.append(("Rollover", rollover_info["bias"]))

    opposing = [s for s in signals if s[1] != pipeline_direction]
    supporting = [s for s in signals if s[1] == pipeline_direction]
    ok = len(opposing) <= max_opposing
    return ok, {"supporting": supporting, "opposing": opposing, "total_signals": len(signals)}
