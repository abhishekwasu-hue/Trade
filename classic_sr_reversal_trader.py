"""
classic_sr_reversal_trader.py
------------------------------------
Classical Support/Resistance Reversal Trader — वापरकर्त्याशी चर्चा करून ठरवलेली, पूर्णपणे नवीन,
स्वतंत्र तिसरी strategy (dynamic_sr_instant_trader.py — 1M+5M, आणि srv2_momentum_reversal_strategy.py
— 15M+30M+60M — या दोन्हींपासून स्वतंत्र, समांतर):

  - Signal: 5-मिनिट + 15-मिनिट Dynamic S/R levels एकत्र (पूल केलेले, first-touch-wins, कुठल्याही
    timeframe ला प्राधान्य नाही) — dynamic_sr_instant_trader.py सारखंच, तोच classical Pivot-clustering
    अल्गोरिदम (sr_dynamic.compute_dynamic_sr, Market Zones nightly refresh कडून आधीच साठवलेला).
  - Touch-detection + RSI + Entry Refinement गेट्स — सर्व 5-मिनिट candles वरून (दोन्ही टाईमफ्रेमच्या
    levels साठी सामायिक, सर्वात बारीक/जलद उपलब्ध डेटा — dynamic_sr_instant_trader.py 1-मिनिट कसा
    सामायिकपणे वापरतो, त्याच तत्त्वाने).
  - RSI(14, 5-मिनिट) फिल्टर — symmetric neutral level (डीफॉल्ट 50; Support<neutral/Resistance>neutral)
    — srv2_momentum_reversal_strategy.py सारखंच, वापरकर्त्याशी चर्चा करून ठरवलेलं ("शुद्ध classical
    S/R" कल्पना — PCR गेट मुद्दाम नाही).
  - Entry Refinement — तीन ऐच्छिक, स्वतंत्र confluence गेट्स (सर्व डीफॉल्ट बंद — Bot Dynamic SR Algo
    वरून चालू करता येतात): Swing High/Low Confluence, Demand/Supply Zone, Trendline (BROKEN असेल तरच
    अडवतो) — backtest.run_classic_sr_reversal_backtest() मध्ये आधीच तपासलेलाच तर्क (signals.py चीच
    find_swings/analyze_chart_zones/detect_trendline फंक्शन्स).
  - Multi-Hit (कमाल 2/level/दिवस) + 30-मिनिट Cooldown + बिनशर्त position-open check — इतर दोन्ही
    strategies सारखंच.
  - Strike Selection — Credit Spread: Short ITM (settings-चालित depth), Long hedge (settings-चालित
    रुंदी) — dynamic_sr_instant_trader.py सारखंच.
  - Naked Option Trade — त्याच सिग्नलवर, समांतर, ऐच्छिक (डीफॉल्ट सक्रिय, hedge डीफॉल्ट बंद).
  - Expiry Day हाताळणी + Lots/ITM-depth/Hedge-width/Gates — cloud_db.get_strategy_settings
    ("classic_sr_reversal", symbol) वरून, Dashboard (Bot Dynamic SR Algo) वरून बदलण्याजोगे.
  - Exit (SL/TSL/Target, स्पॉट%+प्रीमियम-पॉइंट्स एकत्र, TSL-to-Breakeven) — trading_engine.py मध्ये
    केंद्रीकृत (evaluate_point_spot_exit, source="classic_sr_reversal" branch) — इथे फक्त
    entry_level_price/entry_timeframe साठवला जातो.

🎓 वापरकर्त्याशी चर्चा करून ठरवलेला सुरक्षिततेचा नियम — ही strategy अजूनही सुरुवातीच्याच (backtest-
verified, पण अजून प्रत्यक्ष PAPER track-record नसलेल्या) टप्प्यात आहे, त्यामुळे cloud_db.py मध्ये
symbol_enabled डीफॉल्ट **सर्व** symbols साठी (NIFTY सकट) False आहे — इतर दोन strategies (जिथे NIFTY
डीफॉल्ट सक्रिय असते) च्या उलट. वापरकर्त्याने Bot Dynamic SR Algo वरून स्पष्टपणे सक्रिय केल्याशिवाय
कुठलाही (PAPER सुद्धा) trade घेतला जात नाही.
"""
import argparse

import pandas as pd

import cloud_db
from config import get_ist_now, DB_PATH
from database import init_sqlite_db, has_open_trade_from_source, run_auto_backup_if_due
from notifications import send_telegram_message, write_heartbeat, notify_error
from process_lock import ProcessLock, ProcessLockHeld
from signals import calculate_rsi, find_swings, filter_major_swings, analyze_chart_zones, detect_trendline
from strategy import select_credit_spread_itm, select_naked_option_itm
from trading_engine import open_multi_leg_trade
from upstox_api import fetch_upstox_option_chain, fetch_candles, fetch_option_expiries

RSI_NEUTRAL_LEVEL = 50  # Support touch + RSI < neutral -> Bull Put Spread. Resistance touch + RSI > neutral -> Bear Call Spread

# 14:45 नंतर नवीन entry नाही (आधीच्या उघड्या positions वर याचा परिणाम नाही, त्या EOD ला बंद होतील) — इतर दोन्ही strategies सारखंच.
NO_NEW_ENTRY_AFTER_HOUR = 14
NO_NEW_ENTRY_AFTER_MINUTE = 45

TOUCH_TOLERANCE_PCT = 0.05  # level पासून ±0.05% च्या आत candle चा low/high आला तरी "स्पर्श" (TOUCH)

POOLED_TIMEFRAMES = ["5M", "15M"]


def check_classic_sr_rsi_filter(candles_df, direction, neutral_level=RSI_NEUTRAL_LEVEL):
    """5-मिनिट RSI(14) फिल्टर — Support(BULLISH) -> RSI neutral_level च्या खाली.
    Resistance(BEARISH) -> RSI neutral_level च्या वर. रिटर्न: (pass: bool, rsi_value: float|None)."""
    rsi_series = calculate_rsi(candles_df, period=14)
    if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
        return False, None
    latest_rsi = round(float(rsi_series.iloc[-1]), 2)
    if direction == "BULLISH":
        return latest_rsi < neutral_level, latest_rsi
    return latest_rsi > neutral_level, latest_rsi


def check_swing_confluence(candles_df, level, direction, swing_order=3, swing_tolerance_pct=0.15, swing_min_move_pct=0.0):
    """Entry Refinement — touch झालेला level हा नुकत्याच झालेल्या खऱ्या (confirmed) Swing Low
    (Support) / Swing High (Resistance) च्या जवळ आहे का (backtest.py च्या याच गेटशी सुसंगत तर्क).
    🎓 वापरकर्त्याने प्रत्यक्ष चार्टवरून दाखवलेली "major swings only" कल्पना — swing_min_move_pct > 0
    असेल तर, raw fractal स्विंग्सवर आधी filter_major_swings() (ZigZag-सारखा magnitude फिल्टर) लावला
    जातो, जेणेकरून किरकोळ (noise) स्विंग्स confluence म्हणून मोजले जात नाहीत."""
    sh_idx, sl_idx = find_swings(candles_df, order=swing_order)
    if swing_min_move_pct > 0:
        sh_idx, sl_idx = filter_major_swings(candles_df, sh_idx, sl_idx, min_move_pct=swing_min_move_pct)
    ref_idx = sl_idx if direction == "BULLISH" else sh_idx
    if not ref_idx:
        return False, None
    nearest_swing_price = float(candles_df["low" if direction == "BULLISH" else "high"].iloc[ref_idx[-1]])
    return abs(nearest_swing_price - level) <= level * swing_tolerance_pct / 100, nearest_swing_price


def check_demand_supply_confluence(candles_df, level, direction, swing_order=3):
    """Entry Refinement — level हा Demand Zone (Support) / Supply Zone (Resistance) च्या आत आहे का
    (signals.analyze_chart_zones — Swing High/Low वरून, ±0.3% पट्टा)."""
    zones = analyze_chart_zones(candles_df, order=swing_order)
    zone = zones.get("demand_zone") if direction == "BULLISH" else zones.get("supply_zone")
    return (zone is not None and zone[0] <= level <= zone[1]), zone


def check_trendline_not_broken(candles_df, direction, swing_order=3, lookback_swings=4):
    """Entry Refinement — त्याच दिशेची trendline (Support->Ascending, Resistance->Descending)
    अस्तित्वात असून BROKEN असेल, तरच False (अडवतो). पुरेसा डेटा नसेल/trendline सापडली नसेल तर
    True (गेट आपोआप पास — check_trend_signal() च्या फॉलबॅक-तत्त्वासारखंच)."""
    tl = detect_trendline(
        candles_df, swing_type=("low" if direction == "BULLISH" else "high"),
        lookback_swings=lookback_swings, order=swing_order,
    )
    broken = tl is not None and tl.get("valid") and tl["status"] == "BROKEN"
    return not broken, tl


def check_level_crossed(level, candles, tolerance_pct=TOUCH_TOLERANCE_PCT):
    """अलीकडच्या candles च्या [low,high] रेंज मधून (±tolerance_pct% बफरसह), आणि सलग candles मधल्या
    gap मधूनही (मागच्या candle चा close ते पुढच्या candle चा open) level ओलांडला का तपासणे.
    candles: [{"open":.., "high":.., "low":.., "close":..}, ...] (जुनं ते नवीन क्रमाने).
    रिटर्न: (hit: bool, hit_type: "TOUCH"/"GAP_THROUGH"/None, approx_price: float/None)"""
    buffer = level * tolerance_pct / 100
    level_low, level_high = level - buffer, level + buffer

    prev_close = None
    for c in candles:
        if c["low"] <= level_high and c["high"] >= level_low:
            return True, "TOUCH", level
        if prev_close is not None:
            if (prev_close < level < c["open"]) or (prev_close > level > c["open"]):
                return True, "GAP_THROUGH", c["open"]
        prev_close = c["close"]
    return False, None, None


def is_todays_expiry_day(access_token, symbol):
    """आज चालू (सर्वात जवळची) साप्ताहिक expiry आहे का, प्रत्यक्ष option-chain expiry-यादीवरून."""
    expiries = fetch_option_expiries(access_token, symbol)
    if not expiries:
        return False
    return expiries[0] == get_ist_now().strftime("%Y-%m-%d")


def _collect_pooled_levels(all_zones, timeframes=None):
    """दिलेल्या timeframes (डीफॉल्ट दोन्ही — 5M व 15M) च्या ACTIVE levels एकाच यादीत —
    [(zone_row, timeframe_suffix), ...]."""
    pooled = []
    for suffix in (timeframes or POOLED_TIMEFRAMES):
        dyn_levels = all_zones[(all_zones["zone_type"].str.endswith(f"_{suffix}")) & (all_zones["status"] == "ACTIVE")]
        for _, row in dyn_levels.iterrows():
            pooled.append((row, suffix))
    return pooled


def process_symbol(access_token, symbol, lot_size=65):
    """एका symbol साठी — 5M+15M levels एकत्र, RSI-फिल्टर, Entry Refinement गेट्स, Multi-Hit/Cooldown,
    Expiry-Day Logic, आणि आढळल्यास Credit-Spread (ITM) + (सक्रिय असल्यास) समांतर Naked Option PAPER trade."""
    settings = cloud_db.get_strategy_settings("classic_sr_reversal", symbol)
    if not settings.get("symbol_enabled", False):
        return f"{symbol}: बंद आहे (symbol_enabled=False, Bot Dynamic SR Algo सेटिंग्जमधून सक्रिय करा — नवीन strategy असल्याने डीफॉल्ट निष्क्रिय)"
    lots = settings["lots"]
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py प्रमाणेच — Naked Option
    # Trade आता Credit Spread पासून स्वतंत्र lots सेटिंग वापरतो.
    naked_lots = settings.get("naked_lots", lots)
    bullish_entry_enabled = settings.get("bullish_entry_enabled", True)
    bearish_entry_enabled = settings.get("bearish_entry_enabled", True)
    entry_rsi_gate_enabled = settings.get("entry_rsi_gate_enabled", True)
    rsi_neutral_level = settings.get("rsi_neutral_level", RSI_NEUTRAL_LEVEL)
    swing_confluence_enabled = settings.get("swing_confluence_enabled", False)
    swing_tolerance_pct = settings.get("swing_tolerance_pct", 0.15)
    swing_order = settings.get("swing_order", 3)
    swing_min_move_pct = settings.get("swing_min_move_pct", 0.0)
    demand_supply_gate_enabled = settings.get("demand_supply_gate_enabled", False)
    trendline_gate_enabled = settings.get("trendline_gate_enabled", False)
    trendline_lookback_swings = settings.get("trendline_lookback_swings", 4)
    timeframe_choice = settings.get("timeframe_choice", "BOTH")
    active_timeframes = POOLED_TIMEFRAMES if timeframe_choice == "BOTH" else [timeframe_choice]

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    pooled_levels = _collect_pooled_levels(all_zones, active_timeframes)
    if not pooled_levels:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels ({'/'.join(active_timeframes)}) नाहीत"

    # 🎓 Touch-detection + RSI + Entry Refinement गेट्स — सर्व 5-मिनिट candles वरून (दोन्ही
    # टाईमफ्रेमच्या levels साठी सामायिक, सर्वात बारीक/जलद उपलब्ध डेटा) — dynamic_sr_instant_trader.py
    # 1-मिनिट कसा सामायिकपणे वापरतो, त्याच तत्त्वाने.
    candles_df = fetch_candles(access_token, symbol, current_spot=0, interval="5minute")
    if candles_df is None or candles_df.empty:
        return f"{symbol}: 5-मिनिट candles मिळाले नाहीत"

    today_date = get_ist_now().date()
    candles_df["_date"] = candles_df["timestamp"].dt.date
    todays_candles_df = candles_df[candles_df["_date"] == today_date]
    if todays_candles_df.empty:
        return f"{symbol}: आजचे 5-मिनिट candles अजून तयार झालेले नाहीत"

    recent_candles = todays_candles_df.tail(2).to_dict("records")  # फक्त शेवटचे 2 (सद्य किंमत + gap-check)
    current_price = recent_candles[-1]["close"]

    now = get_ist_now()
    trade_date = now.strftime("%Y-%m-%d")

    outcomes = []
    for row, timeframe_suffix in pooled_levels:
        hit, hit_type, approx_price = check_level_crossed(row["zone_low"], recent_candles)

        # दिशा सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून ठरते (साठवलेल्या ऐतिहासिक label वरून
        # नाही) — इतर दोन्ही strategies प्रमाणेच.
        direction = "BULLISH" if current_price >= row["zone_low"] else "BEARISH"
        rsi_value = None
        log_entry = {
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": row["zone_type"],
            "level_price": row["zone_low"], "hit_type": hit_type or "NO_HIT", "direction": direction if hit else "NONE",
            "ltp_at_signal": None, "trade_status": None, "reason": "level ला स्पर्श (touch) आढळला नाही (शेवटच्या candles मध्ये)" if not hit else "",
        }

        if not hit:
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — इतर सर्व gates च्याही आधी — फक्त नवीन trades थांबतात, आधीच उघडलेले चालूच
        # राहतात.
        if direction == "BULLISH" and not bullish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BULLISH_ENTRY_DISABLED"
            log_entry["reason"] = "Bullish Entry सेटिंग्जमधून बंद आहे"
            cloud_db.save_signal_log(log_entry)
            continue
        if direction == "BEARISH" and not bearish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BEARISH_ENTRY_DISABLED"
            log_entry["reason"] = "Bearish Entry सेटिंग्जमधून बंद आहे"
            cloud_db.save_signal_log(log_entry)
            continue

        if (now.hour, now.minute) >= (NO_NEW_ENTRY_AFTER_HOUR, NO_NEW_ENTRY_AFTER_MINUTE):
            log_entry["trade_status"] = "SKIPPED_TOO_LATE_FOR_NEW_ENTRY"
            log_entry["reason"] = f"{NO_NEW_ENTRY_AFTER_HOUR}:{NO_NEW_ENTRY_AFTER_MINUTE:02d} नंतर नवीन entry नाही"
            cloud_db.save_signal_log(log_entry)
            continue

        if entry_rsi_gate_enabled:
            rsi_ok, rsi_value = check_classic_sr_rsi_filter(candles_df, direction, rsi_neutral_level)
            if not rsi_ok:
                log_entry["trade_status"] = "SKIPPED_RSI_FILTER"
                log_entry["reason"] = f"RSI {rsi_value} दिशेशी जुळत नाही (Support<{rsi_neutral_level} / Resistance>{rsi_neutral_level} हवं होतं)"
                cloud_db.save_signal_log(log_entry)
                continue

        # 🎓 Entry Refinement — तीन ऐच्छिक, स्वतंत्र confluence गेट्स (सर्व डीफॉल्ट बंद).
        if swing_confluence_enabled:
            swing_ok, nearest_swing = check_swing_confluence(candles_df, row["zone_low"], direction, swing_order, swing_tolerance_pct, swing_min_move_pct)
            if not swing_ok:
                log_entry["trade_status"] = "SKIPPED_SWING_CONFLUENCE_GATE"
                log_entry["reason"] = (
                    f"level {row['zone_low']:.2f} जवळ कुठलाही खरा (confirmed) Swing "
                    f"{'Low' if direction == 'BULLISH' else 'High'} सापडला नाही (सर्वात जवळचा: {nearest_swing})"
                )
                cloud_db.save_signal_log(log_entry)
                continue

        if demand_supply_gate_enabled:
            ds_ok, zone = check_demand_supply_confluence(candles_df, row["zone_low"], direction, swing_order)
            if not ds_ok:
                log_entry["trade_status"] = "SKIPPED_DEMAND_SUPPLY_GATE"
                log_entry["reason"] = f"level {row['zone_low']:.2f} हा {'Demand' if direction == 'BULLISH' else 'Supply'} zone च्या आत नाही (zone: {zone})"
                cloud_db.save_signal_log(log_entry)
                continue

        if trendline_gate_enabled:
            tl_ok, tl = check_trendline_not_broken(candles_df, direction, swing_order, trendline_lookback_swings)
            if not tl_ok:
                log_entry["trade_status"] = "SKIPPED_TRENDLINE_BROKEN"
                log_entry["reason"] = f"त्याच दिशेची trendline BROKEN आहे (status: {tl.get('status') if tl else None})"
                cloud_db.save_signal_log(log_entry)
                continue

        hit_count_so_far, _, last_trade_time = cloud_db.get_zone_hits_today(
            symbol, row["zone_low"], trade_date, role=cloud_db.zone_role_from_type(row["zone_type"]),
        )
        if hit_count_so_far >= 2:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = "आजच्या या zone साठी (याच role — support/resistance) कमाल 2 वेळा मर्यादा आधीच गाठलेली"
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — cooldown आता फक्त खऱ्या trade नंतरच सुरू होतो
        # (last_trade_time), नुसत्या नाकारलेल्या (RSI/PCR gate ने) touch मुळे नाही.
        if last_trade_time is not None:
            elapsed_minutes = (now - last_trade_time).total_seconds() / 60
            if elapsed_minutes < 30:
                log_entry["trade_status"] = "SKIPPED_COOLDOWN_30MIN"
                log_entry["reason"] = f"मागच्या trade ला फक्त {elapsed_minutes:.1f} मिनिटं झालीत (किमान 30 हवीत)"
                cloud_db.save_signal_log(log_entry)
                continue

        if has_open_trade_from_source(symbol, "classic_sr_reversal"):
            log_entry["trade_status"] = "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"
            log_entry["reason"] = "आधीची position (या strategy ची, कुठल्याही level वरची) अजून बंद झालेली नाही"
            cloud_db.save_signal_log(log_entry)
            continue

        # --- सर्व अटी पूर्ण! Entry ---
        expiry_index = 1 if is_todays_expiry_day(access_token, symbol) else 0
        raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol, expiry_index=expiry_index)
        if not raw_chain:
            return f"{symbol}: Option chain मिळाली नाही ({chain_status})"
        underlying_price = raw_chain[0].get("underlying_spot_price")
        strike_step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
        atm_strike = round(underlying_price / strike_step) * strike_step
        log_entry["ltp_at_signal"] = underlying_price

        spread_result = select_credit_spread_itm(
            raw_chain, direction, atm_strike, step=strike_step,
            itm_depth_points=settings["itm_depth_points"], hedge_width_points=settings["hedge_width_points"],
        )
        if spread_result is None:
            log_entry["trade_status"] = "STRATEGY_SELECTION_FAILED"
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (PAPER/LIVE टॉगल + per-strategy Broker Selection) —
        # dynamic_sr_instant_trader.py प्रमाणेच — settings मधल्याच trading_mode/broker_account_ids
        # वरून, "कुठलेही broker_accounts नोंदवलेले असतील तर सर्व सक्रिय accounts" ऐवजी.
        trading_mode = settings.get("trading_mode", "PAPER")
        broker_account_ids = settings.get("broker_account_ids") or []
        if broker_account_ids:
            from trading_engine import execute_trade_on_all_accounts
            results, factory_errors = execute_trade_on_all_accounts(
                symbol=symbol, strategy_result=spread_result, base_lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=None, target_pct_of_max_profit=100,  # Target trading_engine.py च्या evaluate_point_spot_exit मध्येच ठरतं
                product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                sl_pct_of_credit=100, source="classic_sr_reversal",
                entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                account_ids=broker_account_ids,
            )
            trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
            if factory_errors:
                trade_status += " | वगळलेले: " + "; ".join(factory_errors)
        else:
            trade_result, trade_status = open_multi_leg_trade(
                access_token, symbol, spread_result, lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                sl_pct_of_credit=100, source="classic_sr_reversal",
                entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
            )
        log_entry["trade_status"] = trade_status
        cloud_db.save_signal_log(log_entry)

        naked_status = ""
        naked_result = None
        naked_diag_entry = dict(log_entry)
        if settings.get("naked_enabled", True):
            naked_result = select_naked_option_itm(
                raw_chain, direction, atm_strike, itm_depth_points=settings["itm_depth_points"], step=strike_step,
                hedge_enabled=settings.get("naked_hedge_enabled", False),
                hedge_width_points=settings.get("naked_hedge_width_points", 150),
            )
            if naked_result is None:
                naked_diag_entry["trade_status"] = "SKIPPED_NAKED_STRIKE_NOT_FOUND"
                naked_diag_entry["reason"] = (
                    f"Naked trade साठी आवश्यक ITM strike (atm={atm_strike}, डेप्थ "
                    f"{settings['itm_depth_points']}) raw_chain मध्ये सापडला नाही"
                )
                cloud_db.save_signal_log(naked_diag_entry)
        else:
            naked_diag_entry["trade_status"] = "SKIPPED_NAKED_DISABLED"
            naked_diag_entry["reason"] = "naked_enabled=False (Bot Dynamic SR Algo सेटिंग्जमध्ये बंद)"
            cloud_db.save_signal_log(naked_diag_entry)
        if naked_result is not None:
            if broker_account_ids:
                from trading_engine import execute_trade_on_all_accounts
                naked_results, naked_factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=naked_result, base_lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="classic_sr_reversal",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    account_ids=broker_account_ids,
                )
                naked_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in naked_results) or "कुठलाही account उपलब्ध नाही"
            else:
                _, naked_status = open_multi_leg_trade(
                    access_token, symbol, naked_result, lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="classic_sr_reversal",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                )

        level_label = "Support" if direction == "BULLISH" else "Resistance"
        hit_label = "थेट स्पर्श" if hit_type == "TOUCH" else "⚡ Gap ने उडी मारून ओलांडला"
        rsi_display = f"RSI {rsi_value}." if entry_rsi_gate_enabled else "RSI Gate बंद (तपासलं नाही)."
        naked_line = f"Naked Option: {naked_result.get('strategy', direction)} — {naked_status}\n" if naked_result is not None else ""
        message = (
            f"🎯 <b>{symbol} Classical S/R Reversal Cross ({timeframe_suffix})! (आजचा {hit_count_so_far + 1}/2 वा hit)</b>\n"
            f"{level_label} {row['zone_low']:.2f} (strength {row['strength']:.0f}) — {hit_label} (≈{approx_price:.2f}). {rsi_display}\n"
            f"Credit Spread: {spread_result.get('strategy', direction)} — {trade_status}\n"
            + naked_line
            + f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        outcomes.append(f"{level_label} {row['zone_low']:.2f} ({timeframe_suffix}, {hit_type}) -> {trade_status}")

    if not outcomes:
        return f"{symbol}: सद्य 5-मिनिट candles मध्ये कुठलाही साठवलेला Dynamic S/R level (5M/15M) cross झाला नाही"
    return f"{symbol}: 🎯 " + "; ".join(outcomes)


def run_all_symbols(token, symbols):
    """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — dynamic_sr_instant_trader.py प्रमाणेच इथेही — एका
    symbol मधल्या अनपेक्षित exception मुळे उरलेले symbols त्याच cycle मध्ये कधीच तपासलेच जायचे
    नाहीत, आणि heartbeat/अलर्टही कधीच पोहोचायचा नाही. आता स्वतंत्र, प्रत्येक symbol वेगळा."""
    any_symbol_succeeded = False
    for symbol in symbols:
        try:
            print(process_symbol(token, symbol.strip()))
            any_symbol_succeeded = True
        except Exception as e:
            notify_error("classic_sr_reversal_trader", f"{symbol.strip()}: {e}")
            print(f"⚠️ {symbol.strip()}: अनपेक्षित त्रुटी — {e}")
    return any_symbol_succeeded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    args = parser.parse_args()

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Duplicate-Order Protection, गंभीर
    # यादीतला पाचवा मुद्दा) — dynamic_sr_instant_trader.py सारखीच सुधारणा (VPS crontab वर दर १
    # मिनिटाला चालणारी script मंद network मुळे जास्त वेळ घेतली, तर overlapping invocation
    # डुप्लिकेट ऑर्डर पाठवू शकते — आधीचीच invocation अजून चालू असेल, तर इथेच थांबतो).
    try:
        with ProcessLock("classic_sr_reversal_trader"):
            init_sqlite_db()
            cloud_db.init_cloud_table()
            token = cloud_db.get_effective_upstox_token(args.token)
            if not token:
                print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
                exit(1)
            any_symbol_succeeded = run_all_symbols(token, args.symbols.split(","))
            if any_symbol_succeeded:
                write_heartbeat("classic_sr_reversal_trader")
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Crash Recovery / DB Backup) —
            # dynamic_sr_instant_trader.py सारखीच सुधारणा.
            run_auto_backup_if_due(interval_minutes=60)
    except ProcessLockHeld as e:
        print(f"⏭️ मागची invocation अजून चालू आहे, ही वगळली — डुप्लिकेट ऑर्डर टाळण्यासाठी ({e})")
