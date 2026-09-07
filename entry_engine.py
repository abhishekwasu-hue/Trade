"""
entry_engine.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Phase 2a — Entry Signal Extraction) — established
"A1 Signal Engine" (Direction Engine → Market Structure/Break/Pullback/Retest → RSI → VIX Gate →
OI Confirmation Gate → Sideways Detection → Strategy Selection → Position Sizing) आधी संपूर्णपणे
`page_dashboard.py` च्या `render()` मध्येच, UI (`st.metric`/`st.markdown`) सोबत घट्ट गुंफलेलं होतं —
म्हणजे Dashboard उघडं असतानाच हे सर्व चालायचं.

ही script तेच पूर्ण pipeline (शुद्ध, कुठलाही Streamlit import न वापरता) एका फंक्शनमध्ये काढते —
`evaluate_intraday_signal()` — जे Dashboard (फक्त दाखवण्यासाठी) आणि भविष्यातली standalone
entry-execution service (Phase 2b) दोन्ही वापरू शकतील.

⚠️ **सध्याचा scope — फक्त INTRADAY.** established SWING mode ला tab2 च्या OI-snapshot local
variables शी cross-tab dependency आहे (Advanced OI Analysis), जी वेगळी, अजून काळजीपूर्वक तपासून
काढायला हवी — ती अजून `page_dashboard.py` मध्येच, न बदललेली, आहे. trading_style != "INTRADAY"
दिल्यास हे function `NotImplementedError` देतं (चुकीने SWING साठी वापरलं जाऊ नये म्हणून).

established वर्तन तंतोतंत तेच आहे — फक्त जागा बदलली आहे, गणित/निकाल एकही ओळीत बदललेला नाही
(page_dashboard.py मधल्या मूळ कोडशी ओळ-न-ओळ जुळवून काढलेलं).
"""
import pandas as pd

from config import TIMEFRAME_CONFIG
from upstox_api import fetch_timeframe_df, fetch_candles, fetch_india_vix, get_available_margin
from signals import (
    calculate_rsi, calculate_supertrend, resample_to_1h,
    find_support_resistance_levels, detect_trendline, check_trend_signal,
    classify_market_structure, classify_sideways,
    rsi_momentum_and_divergence,
    check_price_action_strategy, check_indicator_strategy,
)
from strategy import select_iron_condor, select_iron_butterfly, select_credit_spread_fixed_strikes, compute_position_size
from oi_analysis import get_latest_oi_signal, check_oi_diff_entry_gate


def evaluate_intraday_signal(
    token_input, symbol, raw_chain, underlying_price, atm_strike, step, settings,
    df_structure_tf=None, df_rsi_tf=None, df_1h=None, rsi_series=None,
):
    """
    established संपूर्ण A1 Signal Engine pipeline (INTRADAY-only) — Direction Engine पासून
    Strategy Selection + Position Sizing पर्यंत. कुठलाही order place करत नाही (शुद्ध — फक्त
    तपासणी/गणना) — execute करायचं की नाही, हे caller (page_dashboard.py / भविष्यातली
    entry_signal_engine.py) ठरवतो.

    settings dict मध्ये लागणारे keys (sidebar मधून established engine_settings.json सारखं):
        trading_style ("INTRADAY" हवाच), intraday_strategy_mode, sr_window, rsi_oversold,
        rsi_overbought, sl_buffer_pct, min_rr, retest_tolerance_pct, reversal_lookback,
        vix_max_threshold, enable_oi_gate, sideways_tight_range_pct, sideways_max_range_pct,
        hedge_width_points, pop_threshold_pct, risk_pct_per_trade, lot_size

    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Review फिक्स) — df_structure_tf/df_rsi_tf/df_1h/
    rsi_series आधीच fetch केलेले असतील (established page_dashboard.py चं tab1 "Direction Engine"
    तेच आधी करतं) तर ते caller ने पास करावेत — म्हणजे इथे पुन्हा नव्याने fetch (डबल Upstox API कॉल्स,
    Issue-2 speed च्या अगदी उलट) होणार नाहीत. मूळ page_dashboard.py देखील असंच "आधीच fetch केलेला
    df_structure_tf पुन्हा वापरणे" करत होता (comment पहा). None दिल्यास (उदा. भविष्यातली standalone
    entry_signal_engine.py, जिथे आधीचा tab1 नाहीच) इथेच नव्याने fetch होईल.

    रिटर्न: dict — established सर्व diagnostic values (Dashboard display साठी) + अंतिम
    strategy_result/lots/risk_amount/available_margin (execute करायचं असल्यास caller साठी).
    """
    trading_style = settings["trading_style"]
    if trading_style != "INTRADAY":
        raise NotImplementedError(
            "evaluate_intraday_signal() सध्या फक्त INTRADAY साठी आहे — SWING अजून page_dashboard.py मध्येच आहे."
        )

    intraday_strategy_mode = settings["intraday_strategy_mode"]
    sr_window = settings["sr_window"]
    rsi_oversold = settings["rsi_oversold"]
    rsi_overbought = settings["rsi_overbought"]
    sl_buffer_pct = settings["sl_buffer_pct"]
    min_rr = settings["min_rr"]
    retest_tolerance_pct = settings["retest_tolerance_pct"]
    reversal_lookback = settings["reversal_lookback"]
    vix_max_threshold = settings["vix_max_threshold"]
    enable_oi_gate = settings["enable_oi_gate"]
    sideways_tight_range_pct = settings["sideways_tight_range_pct"]
    sideways_max_range_pct = settings["sideways_max_range_pct"]
    hedge_width_points = settings["hedge_width_points"]
    pop_threshold_pct = settings["pop_threshold_pct"]
    risk_pct_per_trade = settings["risk_pct_per_trade"]
    lot_size = settings["lot_size"]

    # --- १. Direction Engine (established page_dashboard.py रेषा १९७-२५९ शी तंतोतंत जुळणारं) ---
    tf_cfg = TIMEFRAME_CONFIG[trading_style]
    structure_interval, structure_tf_label = tf_cfg["structure"]
    rsi_interval, rsi_tf_label = tf_cfg["rsi"]
    confirm_interval, confirm_tf_label = tf_cfg["confirm"]

    if trading_style == "INTRADAY":
        rsi_interval, rsi_tf_label = "15minute", "15M"

    supertrend_tf_label = "1H" if trading_style == "INTRADAY" else structure_tf_label

    if df_structure_tf is None:
        df_structure_tf = fetch_timeframe_df(token_input, symbol, underlying_price, structure_interval)
    if df_rsi_tf is None:
        df_rsi_tf = df_structure_tf if rsi_interval == structure_interval else fetch_timeframe_df(
            token_input, symbol, underlying_price, rsi_interval
        )
    if rsi_series is None:
        rsi_series = calculate_rsi(df_rsi_tf, period=14) if not df_rsi_tf.empty else pd.Series(dtype=float)

    if df_1h is None:
        if structure_interval == "1hour":
            df_1h = df_structure_tf
        elif rsi_interval == "1hour":
            df_1h = df_rsi_tf
        else:
            df_1h = resample_to_1h(fetch_candles(token_input, symbol, underlying_price, interval="30minute"))

    supertrend_source_df = df_1h if trading_style == "INTRADAY" else df_structure_tf
    st_line, st_dir = calculate_supertrend(supertrend_source_df, period=10, multiplier=3)

    supertrend_ok = len(st_dir) > 0
    rsi_ok = len(rsi_series) > 0

    direction_final, direction_color = None, None
    last_st_dir, last_st_val, last_rsi, st_label = None, None, None, None

    if supertrend_ok and rsi_ok:
        last_st_dir = int(st_dir.iloc[-1])
        last_st_val = float(st_line.iloc[-1])
        last_rsi = float(rsi_series.iloc[-1])
        st_label = "🟢 UP" if last_st_dir == 1 else "🔴 DOWN"

        # established INTRADAY: दिशा फक्त 1H Supertrend वरून (RSI इथे दिशा-गेट नाही)
        direction_final = "BULLISH" if last_st_dir == 1 else "BEARISH"
        direction_color = "#089981" if last_st_dir == 1 else "#F23645"

    pipeline_direction = direction_final if direction_final in ("BULLISH", "BEARISH") else None

    # --- २. A1 Signal Engine (established page_dashboard.py रेषा १०७१-१२७२ शी तंतोतंत जुळणारं) ---
    pattern_rsi_ok = True
    pattern_detected = None
    pattern_rsi_value = None
    intraday_strategy_detail = None

    structure_info = classify_market_structure(df_structure_tf) if not df_structure_tf.empty else {
        "structure": "INSUFFICIENT_DATA", "last_swing_high": None, "last_swing_low": None,
    }

    broke, broken_level = False, None
    pulled_back, retested = False, False
    confirmed_5m = False
    zone = None
    sr_levels = None
    trendline_support = None
    trendline_resistance = None
    trend_signal = {"gate_ok": True, "gate_reason": "पुरेसा डेटा नाही — गेट वगळला", "caution": None}

    rsi_check = rsi_momentum_and_divergence(df_structure_tf, rsi_series, pipeline_direction or "BULLISH")

    if pipeline_direction:
        if intraday_strategy_mode == "price_action":
            entry_ok, intraday_strategy_detail = check_price_action_strategy(
                df_structure_tf, pipeline_direction, rsi_series=rsi_series,
                sr_window=sr_window, rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
                sl_buffer_pct=sl_buffer_pct, min_rr=min_rr,
                retest_tolerance_pct=retest_tolerance_pct, reversal_lookback=reversal_lookback,
                df_1h=df_1h,
            )
        else:
            entry_ok, intraday_strategy_detail = check_indicator_strategy(df_structure_tf, rsi_series, pipeline_direction)
        broke, pulled_back, retested = entry_ok, entry_ok, entry_ok
        confirmed_5m = entry_ok

        sr_levels = find_support_resistance_levels(df_structure_tf)
        trendline_support = detect_trendline(df_structure_tf, swing_type="low")
        trendline_resistance = detect_trendline(df_structure_tf, swing_type="high")
        trend_signal = check_trend_signal(pipeline_direction, trendline_support, trendline_resistance, sr_levels)

    india_vix = fetch_india_vix(token_input)
    vix_ok = (india_vix is not None) and (india_vix <= vix_max_threshold)

    # --- OI Confirmation Gate (established फक्त INTRADAY branch — SWING इथे नाही, वर बघा) ---
    oi_signal_latest = None
    oi_confirmation_ok = True
    oi_gate_note = "N/A (गेट बंद आहे)"

    if enable_oi_gate and pipeline_direction:
        oi_signal_latest = get_latest_oi_signal(symbol)
        oi_confirmation_ok = check_oi_diff_entry_gate(pipeline_direction, oi_signal_latest)
        oi_gate_note = oi_signal_latest or "OI डेटा उपलब्ध नाही"

    # --- सर्व गेट्स एकत्र (established रेषा १२४०-१२४४ शी तंतोतंत जुळणारं) ---
    all_gates_passed = bool(
        pipeline_direction and broke and pulled_back and retested
        and rsi_check["momentum_ok"] and confirmed_5m and vix_ok and oi_confirmation_ok
        and trend_signal["gate_ok"] and pattern_rsi_ok
    )

    # --- Sideways मार्ग (established Direction Engine NEUTRAL/MIXED असेल तेव्हाच) ---
    sideways_info = None
    if not pipeline_direction:
        sideways_info = classify_sideways(
            df_structure_tf, structure_info, rsi_check, india_vix, vix_max_threshold,
            tight_range_pct=sideways_tight_range_pct, max_range_pct=sideways_max_range_pct,
        )

    strategy_result = None
    lots, risk_amount = 0, 0.0
    available_margin = None

    if all_gates_passed:
        strategy_result = select_credit_spread_fixed_strikes(raw_chain, pipeline_direction, atm_strike)
    elif sideways_info and sideways_info["is_sideways"]:
        if sideways_info["strategy_type"] == "IRON_BUTTERFLY":
            strategy_result = select_iron_butterfly(raw_chain, atm_strike, hedge_width_points, pop_threshold_pct)
        else:
            strategy_result = select_iron_condor(raw_chain, atm_strike, step, hedge_width_points, pop_threshold_pct)

    if strategy_result:
        available_margin = get_available_margin(token_input)
        lots, risk_amount = compute_position_size(available_margin, risk_pct_per_trade, strategy_result["max_loss"], lot_size)

    return {
        # Direction Engine
        "structure_interval": structure_interval, "structure_tf_label": structure_tf_label,
        "rsi_interval": rsi_interval, "rsi_tf_label": rsi_tf_label,
        "confirm_interval": confirm_interval, "confirm_tf_label": confirm_tf_label,
        "supertrend_tf_label": supertrend_tf_label,
        "df_structure_tf": df_structure_tf, "df_rsi_tf": df_rsi_tf, "df_1h": df_1h,
        "rsi_series": rsi_series, "supertrend_source_df": supertrend_source_df,
        "st_line": st_line, "st_dir": st_dir,
        "supertrend_ok": supertrend_ok, "rsi_ok": rsi_ok,
        "last_st_dir": last_st_dir, "last_st_val": last_st_val, "last_rsi": last_rsi, "st_label": st_label,
        "direction_final": direction_final, "direction_color": direction_color,
        "pipeline_direction": pipeline_direction,
        # A1 Signal Engine
        "pattern_rsi_ok": pattern_rsi_ok, "pattern_detected": pattern_detected, "pattern_rsi_value": pattern_rsi_value,
        "intraday_strategy_detail": intraday_strategy_detail,
        "structure_info": structure_info,
        "broke": broke, "broken_level": broken_level,
        "pulled_back": pulled_back, "retested": retested, "confirmed_5m": confirmed_5m,
        "zone": zone, "sr_levels": sr_levels,
        "trendline_support": trendline_support, "trendline_resistance": trendline_resistance,
        "trend_signal": trend_signal, "rsi_check": rsi_check,
        "india_vix": india_vix, "vix_ok": vix_ok,
        "oi_signal_latest": oi_signal_latest, "oi_confirmation_ok": oi_confirmation_ok, "oi_gate_note": oi_gate_note,
        "all_gates_passed": all_gates_passed,
        "sideways_info": sideways_info,
        "strategy_result": strategy_result, "lots": lots, "risk_amount": risk_amount,
        "available_margin": available_margin,
    }
