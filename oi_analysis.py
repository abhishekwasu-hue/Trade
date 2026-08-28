"""Professional OI analysis: OI-Price Matrix, PCR, Max Pain, Rollover, and the OI Confirmation Gates."""
import math
import sqlite3

from config import DB_PATH, get_ist_today


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


def compute_oi_signal_with_hysteresis(current_diff, current_put_oi, current_call_oi, recent_snapshots,
                                        lookback_for_strength=3, confirm_count=3):
    """
    OI Diff सिग्नल — दिशा (level, Diff चं चिन्ह) आणि Strong/Weak, आणि छोट्या नॉइझमुळे उगाच सिग्नल
    भिरभिरू (flip-flop) नये म्हणून दोन सुधारणा (वापरकर्त्याशी चर्चा करून ठरवलेल्या):

    A) Strong/Weak — Total Put/Call OI आता मागच्या lookback_for_strength (डीफॉल्ट ३, म्हणजे ~३०
       मिनिटं) स्नॅपशॉट्सपूर्वीच्या तुलनेत खरंच वाढला आहे का ते बघतो — आधी फक्त मागच्या १च स्नॅपशॉट
       (१० मिनिटांपूर्वी) शी तुलना व्हायची, जी खूप नॉइझी होती.
    B) दिशा (BULLISH<->BEARISH) बदलण्यासाठी आता सलग confirm_count (डीफॉल्ट ३) स्नॅपशॉट्समध्ये तीच
       नवीन दिशा (Diff चं तेच नवीन चिन्ह) सलग दिसायलाच हवी — नुसती एकदाच उलट दिशा दिसली तर जुनाच
       सिग्नल कायम राहतो (आधीचा १०%-threshold आधारित hysteresis याहून कमी स्थिर होता).

    recent_snapshots: pandas DataFrame (जुनं->नवीन क्रमाने), columns: diff, total_put_oi,
    total_call_oi, signal — किमान शेवटचे max(lookback_for_strength, confirm_count-1) rows हवेत.
    """
    if len(recent_snapshots) >= lookback_for_strength:
        baseline = recent_snapshots.iloc[-lookback_for_strength]
        baseline_put_oi, baseline_call_oi = baseline["total_put_oi"], baseline["total_call_oi"]
    elif len(recent_snapshots) > 0:
        baseline_put_oi, baseline_call_oi = recent_snapshots.iloc[0]["total_put_oi"], recent_snapshots.iloc[0]["total_call_oi"]
    else:
        baseline_put_oi = baseline_call_oi = None

    if current_diff > 0:
        put_growing = baseline_put_oi is not None and current_put_oi > baseline_put_oi
        raw_signal = "🟢 BULLISH (Strong)" if put_growing else "🟡 BULLISH (Weakening)"
        raw_direction = "BULLISH"
    elif current_diff < 0:
        call_growing = baseline_call_oi is not None and current_call_oi > baseline_call_oi
        raw_signal = "🔴 BEARISH (Strong)" if call_growing else "🟠 BEARISH (Weakening)"
        raw_direction = "BEARISH"
    else:
        raw_signal, raw_direction = "⚪ NEUTRAL", "NEUTRAL"

    if len(recent_snapshots) == 0:
        return raw_signal

    prev_signal = recent_snapshots.iloc[-1]["signal"]
    prev_direction = "BULLISH" if "BULLISH" in prev_signal else ("BEARISH" if "BEARISH" in prev_signal else "NEUTRAL")

    if raw_direction == prev_direction:
        return raw_signal  # दिशा तीच आहे -- Strong/Weak लगेच अद्ययावत होऊ शकतो

    # 🎓 वापरकर्त्याने screenshot दाखवून निदर्शनास आणलेला खरा bug — आधी इथे prev_signal (जुना संपूर्ण
    # string, "Strong" सहित) जसाच्या तसा परत यायचा, जरी current_diff आता खूप खोलवर उलट दिशेत गेलेला
    # असला तरी (उदा. Diff=-50L असतानाही "BULLISH (Strong)" दिसायचं — दिशाभूल करणारं). आता held
    # स्थितीत (पुष्टी अजून झालेली नाही) जुन्या दिशेचंच "Weakening" (कमी आत्मविश्वास) रूप दाखवतो —
    # दिशा अजूनही स्थिर राहते (flip-flop टाळलं जातं), पण कधीच खोट्या "Strong" आत्मविश्वासाने नाही.
    prev_direction_weakening = {
        "BULLISH": "🟡 BULLISH (Weakening)", "BEARISH": "🟠 BEARISH (Weakening)",
    }.get(prev_direction, prev_signal)

    if len(recent_snapshots) < confirm_count - 1:
        return prev_direction_weakening  # अजून पुरेसा इतिहास नाही -- जुनीच दिशा, पण Weakening

    recent_diffs = recent_snapshots["diff"].tail(confirm_count - 1).tolist() + [current_diff]
    same_new_direction = all((d > 0 if raw_direction == "BULLISH" else d < 0) for d in recent_diffs)
    return raw_signal if same_new_direction else prev_direction_weakening


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

    today_str = get_ist_today().strftime("%Y-%m-%d")
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
    today_str = get_ist_today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT signal FROM oi_diff_snapshots WHERE symbol=? AND trade_date=? ORDER BY snapshot_time DESC LIMIT 1",
        (symbol, today_str),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def check_oi_diff_entry_gate(direction, oi_signal):
    """
    OI Diff Tracker वरून Entry/Exit साठी हार्ड गेट — Price Action आणि Indicator दोन्ही रणनीतींसाठी सामायिक.
    BULLISH: 'BULLISH' (ठाम) किंवा 'BEARISH (Weakening)' (उलटफेराचं आधीचं संकेत) — दोन्ही वैध.
    BEARISH: 'BEARISH' (ठाम) किंवा 'BULLISH (Weakening)' — दोन्ही वैध.
    स्वतःच्याच दिशेचं 'X (Weakening)' (उदा. BULLISH entry ला 'BULLISH (Weakening)') अवैध — कमकुवत होणाऱ्या
    जोमावर नवीन entry घेणं चुकीचं. NEUTRAL किंवा डेटा नसल्यास अवैध (हार्ड गेट — माहिती नसेल तर सुरक्षित नकार).
    हेच फंक्शन Exit साठीही वापरलं जातं — उघड्या ट्रेडच्या दिशेला हा गेट False देऊ लागला की OI_REVERSAL exit होतो.
    """
    if oi_signal is None:
        return False
    is_weakening = "Weakening" in oi_signal
    if direction == "BULLISH":
        if "BULLISH" in oi_signal:
            return not is_weakening
        if "BEARISH" in oi_signal:
            return is_weakening
        return False
    elif direction == "BEARISH":
        if "BEARISH" in oi_signal:
            return not is_weakening
        if "BULLISH" in oi_signal:
            return is_weakening
        return False
    return False


def classify_oi_price_action(current_oi, prev_oi, current_premium, prev_premium, oi_threshold_pct=2.0, premium_threshold_pct=1.0):
    """
    OI + Premium बदलावरून Writing(Selling)/Buying/Short-Covering/Long-Unwinding ठरवणे — standard
    OI-Price Matrix (options trading मधली प्रचलित पद्धत):
      OI ↑ + Premium ↓ -> Writing (नवीन विक्री/लेखन वाढतंय)
      OI ↑ + Premium ↑ -> Buying (नवीन खरेदी वाढतंय)
      OI ↓ + Premium ↑ -> Short Covering (आधीची विक्री मागे घेतायत)
      OI ↓ + Premium ↓ -> Long Unwinding (आधीची खरेदी मागे घेतायत)
    छोटे, noise-सदृश बदल टाळण्यासाठी दोन्हीकडे किमान threshold% लागतो — अन्यथा "स्थिर/अस्पष्ट".
    """
    if prev_oi is None or prev_oi == 0 or prev_premium is None or prev_premium == 0:
        return "अपुरा डेटा"
    oi_change_pct = (current_oi - prev_oi) / prev_oi * 100
    premium_change_pct = (current_premium - prev_premium) / prev_premium * 100

    oi_up = oi_change_pct >= oi_threshold_pct
    oi_down = oi_change_pct <= -oi_threshold_pct
    premium_up = premium_change_pct >= premium_threshold_pct
    premium_down = premium_change_pct <= -premium_threshold_pct

    if oi_up and premium_down:
        return "Writing ↑ (नवीन विक्री वाढतेय)"
    elif oi_up and premium_up:
        return "Buying ↑ (नवीन खरेदी वाढतेय)"
    elif oi_down and premium_up:
        return "Short Covering (विक्री मागे घेतायत)"
    elif oi_down and premium_down:
        return "Long Unwinding (खरेदी मागे घेतायत)"
    else:
        return "स्थिर/अस्पष्ट"


def generate_oi_price_signal(put_class, call_class):
    """
    Put आणि Call च्या OI-Price classification वरून एकत्रित, actionable संदेश तयार करणे — Put Writing
    किंवा Call Short Covering (दोन्ही बुलिश) आणि Call Writing किंवा Put Short Covering (दोन्ही बेअरिश)
    यांचा मेळ घालून दिशा ठरवणे. दोन्ही बाजूंनी विरोधाभासी संकेत आले तर "मिश्र", काहीच स्पष्ट नसेल तर "तटस्थ".
    """
    bullish_signals, bearish_signals = [], []

    if "Writing" in put_class:
        bullish_signals.append("Put Writing वाढतंय")
    elif "Buying" in put_class:
        bearish_signals.append("Put Buying वाढतंय")
    elif "Short Covering" in put_class:
        bearish_signals.append("Put Short Covering (आधार कमकुवत)")
    elif "Long Unwinding" in put_class:
        bullish_signals.append("Put Unwinding (bears मागे)")

    if "Writing" in call_class:
        bearish_signals.append("Call Writing वाढतंय")
    elif "Buying" in call_class:
        bullish_signals.append("Call Buying वाढतंय")
    elif "Short Covering" in call_class:
        bullish_signals.append("Call Short Covering (रोध कमकुवत)")
    elif "Long Unwinding" in call_class:
        bearish_signals.append("Call Unwinding (bulls मागे)")

    if bullish_signals and not bearish_signals:
        return "BULLISH", "🟢 " + " + ".join(bullish_signals) + " → Don't Short Call, Nifty is Bullish"
    elif bearish_signals and not bullish_signals:
        return "BEARISH", "🔴 " + " + ".join(bearish_signals) + " → Don't Short Put, Nifty is Bearish"
    elif bullish_signals and bearish_signals:
        return "MIXED", "🟡 संमिश्र संकेत — स्पष्ट दिशा नाही, सावध रहा"
    else:
        return "NEUTRAL", "⚪ कुठलीही स्पष्ट हालचाल नाही"


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
    today_str = get_ist_today().strftime("%Y-%m-%d")
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


def compute_dte(raw_chain, today_date):
    """
    🎓 वापरकर्त्याच्या विनंतीनुसार — raw_chain मधल्या पहिल्या item मधून expiry date काढून, आजपासून
    किती दिवस उरले (DTE, Days To Expiry) ते काढणे. raw_chain मधल्या प्रत्येक strike-item मध्ये स्वतःच
    'expiry' field असते (Upstox चं standard response) — त्यामुळे fetch_upstox_option_chain चं
    signature बदलावं लागत नाही. expiry सापडली नाही, किंवा चुकीच्या format मध्ये असेल, तर सुरक्षितपणे
    (None, None) — कधीही crash होत नाही.
    """
    import datetime
    if not raw_chain:
        return None, None
    expiry_str = raw_chain[0].get("expiry")
    if not expiry_str:
        return None, None
    try:
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None, None
    dte = (expiry_date - today_date).days
    return expiry_date, dte


def fetch_and_save_oi_snapshot(access_token, symbol, fetch_chain_fn, get_ist_now_fn, db_path, atm_range=6, step=50):
    """
    🎓 वापरकर्त्याशी चर्चा करून काढलेली सुधारणा — OI Diff Snapshot (दर १० मिनिटांचा) पूर्वी फक्त
    Dashboard उघडं असतानाच (browser मध्ये) साठवला जायचा. आता हे पूर्ण, स्वतंत्र function आहे — Dashboard
    आणि नवीन unattended script (oi_snapshot_collector.py) दोन्ही हेच वापरतात, त्यामुळे browser बंद
    असतानाही (cron ने चालवल्यास) snapshots साठवले जातील, आणि Dashboard उघडल्यावर तेही टेबलमध्ये दिसतील.

    🎓 पुढची सुधारणा — Cloud DB (Supabase/PostgreSQL) configured असेल (cloud_db.py, environment variable
    SUPABASE_DB_URL किंवा config फाईल द्वारे) तर तिथेच वाचन-लेखन होतं — जेणेकरून local machine वरचा
    unattended collector आणि Streamlit Cloud वरचं Dashboard दोन्ही त्याच, सामायिक डेटाशी बोलतात
    (आधीची समस्या: दोन वेगळ्या मशीन्सवरच्या वेगळ्या, न-जोडलेल्या SQLite फाईल्स). Cloud DB configured
    नसेल तर आपोआप जुन्याच local SQLite कडे वळतं — कुठलंही जुनं वर्तन तुटत नाही.

    fetch_chain_fn/get_ist_now_fn dependency-injection सारखे pass केले आहेत — testing सोपं करण्यासाठी.

    रिटर्न: (snapshot_dict किंवा None, स्थिती-संदेश). त्याच १०-मिनिट स्लॉटसाठी snapshot आधीच असेल तर
    शांतपणे वगळलं जातं (डुप्लिकेट होत नाही) — तरीही (snapshot_dict, "ALREADY_EXISTS") परत येतं.
    """
    import cloud_db
    use_cloud = cloud_db.is_cloud_db_configured()

    raw_chain, status = fetch_chain_fn(access_token, symbol)
    if not raw_chain:
        return None, f"Option chain मिळाला नाही: {status}"

    underlying_price = raw_chain[len(raw_chain) // 2].get("underlying_spot_price", 0)
    atm_strike = round(underlying_price / step) * step

    total_call_oi = total_put_oi = 0
    total_call_premium = total_put_premium = 0.0
    for item in raw_chain:
        strike = item.get("strike_price")
        if strike is None or abs(strike - atm_strike) > atm_range * step:
            continue
        ce = item.get("call_options", {}) or {}
        pe = item.get("put_options", {}) or {}
        total_call_oi += (ce.get("market_data", {}) or {}).get("oi", 0) or 0
        total_put_oi += (pe.get("market_data", {}) or {}).get("oi", 0) or 0
        total_call_premium += (ce.get("market_data", {}) or {}).get("ltp", 0) or 0
        total_put_premium += (pe.get("market_data", {}) or {}).get("ltp", 0) or 0

    current_diff = total_put_oi - total_call_oi
    now_dt = get_ist_now_fn()
    snapshot_minute = (now_dt.minute // 10) * 10
    snapshot_time = now_dt.replace(minute=snapshot_minute, second=0, microsecond=0).strftime("%H:%M")
    today_str = now_dt.strftime("%Y-%m-%d")

    import pandas as pd
    if use_cloud:
        recent_rows_raw = cloud_db.get_recent_oi_snapshots_cloud(symbol, today_str, before_time=snapshot_time, limit=5)
        recent_rows = [(r["diff"], r["total_put_oi"], r["total_call_oi"], r["signal"]) for r in recent_rows_raw]
    else:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            """SELECT diff, total_put_oi, total_call_oi, signal FROM oi_diff_snapshots
               WHERE symbol=? AND trade_date=? AND snapshot_time < ? ORDER BY snapshot_time DESC LIMIT 5""",
            (symbol, today_str, snapshot_time),
        )
        recent_rows = list(reversed(cur.fetchall()))

    recent_snapshots_df = pd.DataFrame(
        [{"diff": r[0], "total_put_oi": r[1], "total_call_oi": r[2], "signal": r[3]} for r in recent_rows]
    )
    oi_signal = compute_oi_signal_with_hysteresis(current_diff, total_put_oi, total_call_oi, recent_snapshots_df)
    delta_diff = (current_diff - recent_rows[-1][0]) if recent_rows else 0

    # 🎓 OI-Price Banner (Writing/Buying/Covering) साठी — मागच्या (सर्वात अलीकडच्या) एकाच snapshot शी
    # तुलना. prev_single नसेल (दिवसाचा पहिलाच snapshot) तरी classify_oi_price_action ला None दिलं जातं —
    # तेच "अपुरा डेटा" परत करतं, आणि generate_oi_price_signal त्यावरून सुरक्षितपणे "NEUTRAL" ठरवतं
    # (कधीही थेट क्रॅश होणार नाही).
    if use_cloud:
        all_today = cloud_db.get_oi_history_cloud(symbol, today_str)  # अलीकडचा->जुना क्रमाने
        already_exists = any(r["snapshot_time"] == snapshot_time for r in all_today)
        earlier_today = [r for r in all_today if r["snapshot_time"] < snapshot_time]
        prev_single = earlier_today[0] if earlier_today else None
        if prev_single:
            prev_put_oi_s, prev_call_oi_s = prev_single["total_put_oi"], prev_single["total_call_oi"]
            prev_call_prem_s, prev_put_prem_s = prev_single["total_call_premium"], prev_single["total_put_premium"]
        else:
            prev_put_oi_s = prev_call_oi_s = prev_call_prem_s = prev_put_prem_s = None
        cloud_db.save_oi_snapshot_cloud(
            symbol, today_str, snapshot_time, total_call_oi, total_put_oi, current_diff, delta_diff, oi_signal,
            underlying_price, total_call_premium, total_put_premium,
        )
    else:
        import sqlite3
        conn2 = sqlite3.connect(db_path)
        cur2 = conn2.cursor()
        cur2.execute(
            """SELECT total_put_oi, total_call_oi, total_call_premium, total_put_premium FROM oi_diff_snapshots
               WHERE symbol=? AND trade_date=? AND snapshot_time < ? ORDER BY snapshot_time DESC LIMIT 1""",
            (symbol, today_str, snapshot_time),
        )
        prev_single = cur2.fetchone()
        prev_put_oi_s, prev_call_oi_s, prev_call_prem_s, prev_put_prem_s = prev_single if prev_single else (None, None, None, None)

        cur2.execute(
            """SELECT COUNT(*) FROM oi_diff_snapshots WHERE symbol=? AND trade_date=? AND snapshot_time=?""",
            (symbol, today_str, snapshot_time),
        )
        already_exists = cur2.fetchone()[0] > 0
        cur2.execute(
            """INSERT OR IGNORE INTO oi_diff_snapshots
               (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal,
                underlying_price, total_call_premium, total_put_premium)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, today_str, snapshot_time, total_call_oi, total_put_oi, current_diff, delta_diff, oi_signal,
             underlying_price, total_call_premium, total_put_premium),
        )
        conn2.commit()
        conn2.close()

    put_oi_price_class = classify_oi_price_action(total_put_oi, prev_put_oi_s, total_put_premium, prev_put_prem_s)
    call_oi_price_class = classify_oi_price_action(total_call_oi, prev_call_oi_s, total_call_premium, prev_call_prem_s)
    oi_price_direction, oi_price_message = generate_oi_price_signal(put_oi_price_class, call_oi_price_class)

    snapshot = {
        "snapshot_time": snapshot_time, "trade_date": today_str, "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi, "diff": current_diff, "delta_diff": delta_diff, "signal": oi_signal,
        "underlying_price": underlying_price, "atm_strike": atm_strike,
        "put_oi_price_class": put_oi_price_class, "call_oi_price_class": call_oi_price_class,
        "oi_price_direction": oi_price_direction, "oi_price_message": oi_price_message,
    }
    return snapshot, ("ALREADY_EXISTS" if already_exists else "OK")
