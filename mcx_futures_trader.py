"""
mcx_futures_trader.py
------------------------------------
MCX Futures Trader — CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER. Support/Resistance touch झाला की
सरळ Futures contract BUY/SELL (options नाहीत — Upstox चा Option Chain API MCX साठी उपलब्धच नाही,
resolve_mcx_futures_instruments.py च्या docstring मध्ये आधीच नोंदवलेलं). existing 3 bots
(dynamic_sr_instant_trader.py/srv2_momentum_reversal_strategy.py/classic_sr_reversal_trader.py,
NIFTY/BANKNIFTY/SENSEX) ला अजिबात हात लावलेला नाही — पूर्णपणे स्वतंत्र strategy, सेटिंग्ज
page_mcx_futures.py (Dashboard) वरून.

रचना (page_mcx_futures.py च्या Entry/Exit Gate शी तंतोतंत सुसंगत):
  - Touch Timeframe: 30M/60M/ALL (15M कधीच पर्यायच नाही) — refresh_market_zones_mcx.py ने
    Supabase मध्ये साठवलेले DYNAMIC_SR_SUPPORT_30M/DYNAMIC_SR_RESISTANCE_30M/*_60M zones वापरतो
    (cloud_db.get_market_zones — त्याच table मधून, फक्त वेगळ्या symbol साठी — NIFTY/BANKNIFTY/
    SENSEX च्या zones ला स्पर्शही होत नाही).
  - RSI(14, त्याच timeframe चा) dual-threshold gate — dynamic_sr_instant_trader.py चा
    check_instant_rsi_filter() इथेच पुन्हा-वापरलेला (import — स्वतंत्र कॉपी नाही, तोच सिद्ध झालेला
    तर्क): rsi_support_max (Bullish साठी यापेक्षा कमी हवा) / rsi_resistance_min (Bearish साठी
    यापेक्षा जास्त हवा).
  - Multi-Hit (एकाच S/R level वर दिवसातून कमाल 2 वेळाच entry) — cloud_db.get_zone_hits_today(),
    या project मधल्या इतर सर्व bots प्रमाणेच (वापरकर्त्याने स्पष्ट सांगितलेली सामायिक रचना).
  - Breakout Entry (ऐच्छिक, `entry_breakout_gate_enabled`, डीफॉल्ट बंद) — dynamic_sr_instant_trader.py
    मधलंच price-consolidation buildup लॉजिक (check_breakout_price_consolidation +
    check_breakout_candle_close — इथेही import, स्वतंत्र कॉपी नाही) — max-2-hits च्या पलीकडचा, तिसरा
    trade, त्याच candidate च्या स्वतःच्या (30M/60M) candles वर (वेगळी finer-interval fetch नाही —
    MCX ची touch-granularity आधीच तितकी coarse आहे). RSI Gate directional trade असल्याने वगळला जातो
    (MCX मध्ये cooldown/PCR/IV gate मुळातच नाहीत, त्यामुळे तेवढंच वगळायचं).
  - Instrument नेहमी resolve_mcx_futures_instruments.resolve_symbol() ने ताजा (current/continuous
    front-month contract) — प्रत्येक cycle ला पुन्हा resolve होतो, कुठलाही instrument_key/expiry
    कधीच hardcoded नाही (महिना बदलला/contract expire झाला तरी आपोआप पुढच्या contract वर roll होतो).
  - Entry — established trading_engine.open_multi_leg_trade() (existing engine, कुठलाही बदल न
    करता, options-आधारित 3 bots प्रमाणेच) — पण एकाच "futures" leg सह (strike/option_type/hedge —
    काहीच नाही). sl_points/target_points सरळ max_loss/max_profit म्हणून पास केलेले
    (sl_pct_of_max_loss=100, target_pct_of_max_profit=100) — म्हणजे SL/Target बरोबर तेच points
    (lots/lot_size ने गुणलेले रुपये) ठरतात, कुठलंही प्रीमियम/credit गणित मध्ये येत नाही.
    strategy_result["legs"] मध्ये "strike": 0 (dummy, फक्त trading_engine.py च्या strikes_summary
    display-स्ट्रिंगसाठी — trading_engine.py ला अजिबात हात न लावता) — वगळता काहीही बदल नाही.
  - Exit (SL/Target/Trailing/EOD) — established trading_engine.manage_open_trades() (existing,
    generic "else" branch — source="mcx_futures" कुठल्याही options-specific branch शी जुळत नाही,
    त्यामुळे आपोआप प्लेन रुपये P&L वर आधारित SL/Target/EOD मिळतं, कुठलाही बदल न करता).
    trade_monitor.py चं MONITORED_SYMBOLS (NIFTY/BANKNIFTY/SENSEX, engine_service.py) इथे मुद्दामच
    बदललेलं नाही — त्याऐवजी हीच script (एकाच cron cycle मध्ये) entry-तपासणीनंतर स्वतःच
    manage_open_trades() सुद्धा प्रत्येक MCX symbol साठी चालवते.
    🎓 वापरकर्त्याने सापडवलेली सुधारणा ("exit slippage") — आधी हे monitoring एका cron invocation
    मध्ये (दर मिनिटाला) फक्त एकदाच व्हायचं — trade_monitor.py (NIFTY/BANKNIFTY/SENSEX) च्या
    "दर ~15 सेकंदांनी पुन्हा तपासा" फिक्सच्या आधीच्या, जास्त slippage-प्रवण अवस्थेसारखंच. आता
    trade_monitor.py च्याच run_monitor_loop() पॅटर्नने — entry-तपासणी अजूनही एकदाच (दर मिनिटाला,
    वेगवान करायची गरज नाही), पण exit-monitoring (run_exit_monitor_loop()) आता त्याच cron
    invocation च्या आत दर ~15 सेकंदांनी (--interval-seconds, ~30 सेकंदांपर्यंत --loop-seconds —
    trade_monitor.py च्या 50 पेक्षा कमी, कारण MCX cron ओळीत आधीच `sleep 60` stagger आहे) पुन्हा-पुन्हा
    — SL/Target ओलांडल्यानंतर बॉटला कळायला आता जास्तीत जास्त ~60 सेकंदांऐवजी ~15-20 सेकंद लागतात.
  - Trailing SL — page_mcx_futures.py चा साधा "points मागे" trailing_distance_points,
    trading_engine.compute_trailing_sl_level() ला atr_multiplier=1.0 सह दिलेला (ATR गुणक नाही,
    सरळ तितकेच points मागे) — नवीन trailing-गणित लिहावं लागलं नाही.
  - SL/Target/Trailing — Points सोबतच Percentage mode (sl_target_mode="PERCENT", page_mcx_futures.py
    च्या Exit Gate वरून निवडण्याजोगं, डीफॉल्ट "POINTS" — backward-compatible). Percentage असेल तर
    entry (SL/Target) किंवा सद्य किंमतीवरून (Trailing, प्रत्येक monitor cycle ला ताजी) points-समतुल्य
    आकडा काढून तोच trading_engine ला दिला जातो — trading_engine.py ला mode बद्दल काहीच माहीत नसतं.

⚠️ PAPER mode डीफॉल्ट (page_mcx_futures.py सेटिंग्ज — trading_mode). LIVE करण्याआधी किमान काही
दिवस PAPER मध्ये चालवून निकाल बघा.

चालवणे (VPS वर, deploy/README.md मध्ये crontab तयार आहे — अजून सक्रिय नाही):
    python3 mcx_futures_trader.py
    # किंवा स्वतःचा token देऊन: python3 mcx_futures_trader.py --token <UPSTOX_TOKEN>
"""
import argparse
import time

import cloud_db
import resolve_mcx_futures_instruments as mcx_resolver
from config import get_ist_now
from database import init_sqlite_db, has_open_trade_from_source, run_auto_backup_if_due
from dynamic_sr_instant_trader import check_instant_rsi_filter, check_breakout_price_consolidation, check_breakout_candle_close
from notifications import send_telegram_message, write_heartbeat, notify_error
from process_lock import ProcessLock, ProcessLockHeld
from signals import resample_to_1h
from trading_engine import open_multi_leg_trade, manage_open_trades
from upstox_api import fetch_mcx_candles

MCX_FUTURES_SYMBOLS = mcx_resolver.MCX_FUTURES_SYMBOLS
STRATEGY_KEY = "mcx_futures"

# Upstox चा MCX Futures product-type — established 3 bots (options, NSE_FO/BSE_FO) established
# "D" (Delivery/Carry-Forward — जेणेकरून bot चं स्वतःचं EOD-square-off logic लागू होतं, broker चा
# स्वयंचलित MIS square-off मध्ये येत नाही) तेच इथेही — established संपूर्ण codebase मध्ये सुसंगत.
PRODUCT_TYPE = "D"

# 🎓 वापरकर्त्याने मागितलेली सुधारणा — entry-वेळचा touch-detection buffer आता सर्व commodities साठी
# 0.10% (आधी 0.05% होता) — किंमत level च्या ±0.10% च्या आत आली/candle range त्यात असेल तरच TOUCH
# मानला जातो (हे hysteresis-आधारित direction-buffer, DIRECTION_HYSTERESIS_BUFFER_PCT, पेक्षा वेगळं —
# तो कुठला touch झाल्यावर दिशा काय ठरवायची ते सांगतो, हा touch खरंच झाला का ते).
TOUCH_TOLERANCE_PCT = 0.10
TIMEFRAME_SUFFIXES = ["30M", "60M"]  # 15M कधीच नाही (वापरकर्त्याने स्पष्ट सांगितल्याप्रमाणे)

# 🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py/srv2_momentum_reversal_strategy.py
# मधलाच hysteresis-आधारित direction-निर्णय (बघा determine_direction_with_hysteresis()) आता इथेही.
# सुरुवातीला srv2 सारखाच 0.015% buffer ठेवला होता (तोही फक्त 30M/60M वापरतो म्हणून), पण वापरकर्त्याने
# लगेच MCX साठी स्वतंत्रपणे 1% (commodities — CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER — साठी जास्त
# रुंद, कारण त्यांची किंमत-हालचाल NIFTY/BANKNIFTY पेक्षा वेगळ्या प्रमाणात असते) सांगितलं — स्वतंत्र
# constant, बाकी दोन्ही bots ला हात लावलेला नाही.
DIRECTION_HYSTERESIS_BUFFER_PCT = 1.0

# MCX चं trading session NSE पेक्षा खूप उशिरापर्यंत (रात्री, हंगामानुसार ~23:30/23:55 पर्यंत बदलतं,
# deploy/README.md मधली नोंद बघा) — प्रत्यक्ष exchange-close च्या थोडं आधी, established इतर
# strategies (15:15 IST, exchange-close 15:30 च्या आधी) सारखाच सुरक्षित मार्जिन ठेवणारा डीफॉल्ट.
MCX_EOD_HOUR = 23
MCX_EOD_MINUTE = 15


def determine_direction_with_hysteresis(level, closes, buffer_pct=DIRECTION_HYSTERESIS_BUFFER_PCT):
    """🎓 dynamic_sr_instant_trader.py/srv2_momentum_reversal_strategy.py मधल्याच फंक्शनची हुबेहूब
    नक्कल — किंमत level पासून ±buffer_pct% च्या आतच (borderline) असेल, तर आधीचीच "निश्चित" दिशा कायम
    ठेवायची (उगाच फ्लिप नाही). closes (त्या candidate च्या timeframe च्या आजच्या सर्व candles च्या
    close किमती, जुनं ते नवीन क्रमाने) मधून मागे जाऊन, ज्या पहिल्या candle चं close त्या बॅंडच्या
    (level±buffer) स्पष्टपणे बाहेर आहे, तीच शेवटची निश्चित दिशा मानली जाते. दिवसभर कधीच बॅंडबाहेर
    गेलं नसेल, तर सद्य किमतीची raw तुलनाच (जुनं वर्तन) safe fallback.
    रिटर्न: "BULLISH"/"BEARISH" """
    buffer = level * buffer_pct / 100
    upper, lower = level + buffer, level - buffer
    for close in reversed(closes):
        if close >= upper:
            return "BULLISH"
        if close <= lower:
            return "BEARISH"
    return "BULLISH" if closes[-1] >= level else "BEARISH"


def _collect_touch_candidates(access_token, instrument_key, all_zones, active_suffixes, now):
    """दिलेल्या timeframes (30M/60M) च्या ACTIVE levels, प्रत्येकाचे स्वतःचे candles (त्याच
    timeframe चा RSI साठी) आणि सद्य किंमत (आजच्याच दिवसाची) — एकाच यादीत एकत्र करणे.
    srv2_momentum_reversal_strategy._collect_touch_candidates() याच पॅटर्नचं MCX-futures आवृत्ती —
    फरक फक्त instrument_key (resolve_mcx_futures_instruments कडून) व fetch_mcx_candles() वापरणं.
    रिटर्न: [(level_price, timeframe_suffix, candles_df, current_price, todays_closes), ...]"""
    candidates = []
    today_date = now.date()
    for suffix in active_suffixes:
        dyn_levels = all_zones[(all_zones["zone_type"].str.endswith(f"_{suffix}")) & (all_zones["status"] == "ACTIVE")]
        if dyn_levels.empty:
            continue
        # "60minute"/"1hour" Upstox कडून थेट verified नाही (fetch_mcx_candles() च्या
        # allowed_intervals यादीत नाही) — 30-मिनिट candles मागवून resample करणे, इतर बॉट्स प्रमाणेच.
        df_30m = fetch_mcx_candles(access_token, instrument_key, interval="30minute", lookback_days=5)
        candles_df = resample_to_1h(df_30m) if suffix == "60M" and df_30m is not None and not df_30m.empty else df_30m
        if candles_df is None or candles_df.empty or len(candles_df) < 12:
            continue
        candles_df = candles_df.copy()
        candles_df["_date"] = candles_df["timestamp"].dt.date
        todays_candles_df = candles_df[candles_df["_date"] == today_date]
        if todays_candles_df.empty:
            continue
        current_price = todays_candles_df["close"].iloc[-1]
        todays_closes = todays_candles_df["close"].tolist()
        for _, zrow in dyn_levels.iterrows():
            candidates.append((zrow["zone_low"], suffix, candles_df, current_price, todays_closes))
    return candidates


def process_symbol(access_token, symbol):
    """एका MCX commodity साठी — 30M/60M levels (settings-चालित), RSI dual-threshold gate,
    Multi-Hit, आणि आढळल्यास एकाच futures leg चं PAPER/LIVE trade (settings-चालित lots/SL/Target)."""
    settings = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol)
    if not settings.get("symbol_enabled", False):
        return f"{symbol}: बंद आहे (symbol_enabled=False, MCX Futures Trader सेटिंग्जमधून सक्रिय करा)"

    ok, resolved = mcx_resolver.resolve_symbol(access_token, symbol)
    if not ok:
        return f"{symbol}: सध्याचा (current/continuous) Futures contract सापडला नाही ({resolved})"
    instrument_key = resolved["instrument_key"]
    lot_size = resolved["lot_size"]

    lots = settings["lots"]
    bullish_entry_enabled = settings.get("bullish_entry_enabled", True)
    bearish_entry_enabled = settings.get("bearish_entry_enabled", True)
    entry_rsi_gate_enabled = settings.get("entry_rsi_gate_enabled", True)
    rsi_support_max = settings.get("rsi_support_max", 40)
    rsi_resistance_min = settings.get("rsi_resistance_min", 60)
    entry_breakout_gate_enabled = settings.get("entry_breakout_gate_enabled", False)
    breakout_lookback_candles = settings.get("breakout_lookback_candles", 12)
    breakout_tolerance_pct = settings.get("breakout_tolerance_pct", 0.30)
    timeframe_choice = settings.get("timeframe_choice", "30M")
    active_suffixes = TIMEFRAME_SUFFIXES if timeframe_choice == "ALL" else [timeframe_choice]

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones_mcx.py चालवा)"

    now = get_ist_now()
    trade_date = now.strftime("%Y-%m-%d")
    candidates = _collect_touch_candidates(access_token, instrument_key, all_zones, active_suffixes, now)
    if not candidates:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels ({'/'.join(active_suffixes)}) सापडले नाहीत, किंवा आजचे candles अजून तयार नाहीत"

    for level_price, timeframe_suffix, candles_df, current_price, todays_closes in candidates:
        touched = abs(current_price - level_price) <= level_price * TOUCH_TOLERANCE_PCT / 100

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा — आधी दिशा फक्त सद्य किमतीच्या raw तुलनेवरून ठरायची,
        # आता srv2_momentum_reversal_strategy.py सारखीच hysteresis logic (0.015% buffer) — किंमत
        # level पासून त्या बँडच्या आतच wobble करत असेल, तर आधीचीच निश्चित दिशा कायम राहते.
        direction = determine_direction_with_hysteresis(level_price, todays_closes)
        level_type = "SUPPORT" if direction == "BULLISH" else "RESISTANCE"

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Mcx comodity sathi suddha he feature add
        # kra, Breakout buildup waril A and C mix logic") — dynamic_sr_instant_trader.py प्रमाणे
        # role हा zone_type सारखा स्थिर database column नाही — इथे तो प्रत्येक cycle ला hysteresis-
        # दिशेवरूनच (`level_type`, वर) ताजा काढला जातो, त्यामुळे breakout घडलाच असेल तर हा आधीच
        # (नैसर्गिकपणे) नव्या दिशेकडे वळलेला असतो — वेगळी flip-logic लागत नाही (dynamic_sr_instant_
        # trader.py च्या उलट, जिथे role स्थिर असल्याने breakout_direction स्वतंत्रपणे उलटवावी लागते).
        # म्हणून buildup साठी "मूळ" (breakout-आधीची) role शोधायला — याच level वर उलट role
        # (opposite_role) कडे आधीच 2 hits झालेल्या आहेत का, हे तपासायचं (हाच "A"). झाले असतील, आणि
        # किंमत level च्या आधीच्या काही candles मध्ये जवळच consolidate होऊन (हाच "C") आता निर्णायकपणे
        # (आताच्या, ताज्या) दिशेने close झाली, तरच हा breakout trade — `touched` (सद्य किंमत level
        # च्या जवळच आहे का) ची अट breakout candle साठी खरीच ठरणार नाही (breakout म्हणजे किंमत level
        # पासून निर्णायक दूर गेलेली), म्हणून इथे त्यापासून स्वतंत्रपणे तपासलं जातं.
        role = level_type
        hit_count_so_far, _, _ = cloud_db.get_zone_hits_today(symbol, level_price, trade_date, role=role)
        is_breakout_trade = False
        if entry_breakout_gate_enabled:
            opposite_role = "RESISTANCE" if role == "SUPPORT" else "SUPPORT"
            opposite_hit_count, _, _ = cloud_db.get_zone_hits_today(symbol, level_price, trade_date, role=opposite_role)
            if opposite_hit_count >= 2:
                candles_for_breakout = [{"close": c} for c in todays_closes]
                if (check_breakout_price_consolidation(level_price, candles_for_breakout, breakout_lookback_candles, breakout_tolerance_pct)
                        and check_breakout_candle_close(level_price, direction, candles_for_breakout)):
                    is_breakout_trade = True
                    touched = True

        log_entry = {
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": level_type,
            "level_price": level_price, "hit_type": "TOUCH" if touched else "NO_HIT",
            "direction": direction if touched else "NONE", "ltp_at_signal": current_price,
            "trade_status": None,
            "reason": "" if touched else f"level ला स्पर्श (touch) आढळला नाही ({timeframe_suffix})",
        }

        if not touched:
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — अंतिम (breakout-flip नंतरच्याही) direction वरच तपासलं जातं, जेणेकरून
        # कुठल्याही उगमाची (reversal/breakout) या दिशेची trade अडवली जाईल. फक्त नवीन trades थांबतात.
        if direction == "BULLISH" and not bullish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BULLISH_ENTRY_DISABLED"
            log_entry["reason"] = f"Bullish Entry सेटिंग्जमधून बंद आहे ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            continue
        if direction == "BEARISH" and not bearish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BEARISH_ENTRY_DISABLED"
            log_entry["reason"] = f"Bearish Entry सेटिंग्जमधून बंद आहे ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            continue

        if hit_count_so_far >= 2 and not is_breakout_trade:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = f"आजच्या या zone साठी (याच role) कमाल 2 वेळा मर्यादा आधीच गाठलेली ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            continue

        rsi_value = None
        if entry_rsi_gate_enabled and not is_breakout_trade:
            rsi_ok, rsi_value = check_instant_rsi_filter(candles_df, direction, rsi_support_max, rsi_resistance_min)
            if not rsi_ok:
                log_entry["trade_status"] = "SKIPPED_RSI_FILTER"
                log_entry["reason"] = (
                    f"RSI {rsi_value} ({timeframe_suffix}) दिशेशी जुळत नाही "
                    f"(Support<{rsi_support_max} / Resistance>{rsi_resistance_min} हवं होतं)"
                )
                cloud_db.save_signal_log(log_entry)
                continue

        if has_open_trade_from_source(symbol, STRATEGY_KEY):
            log_entry["trade_status"] = "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"
            log_entry["reason"] = f"आधीची MCX Futures position (कुठल्याही level/timeframe वरची) अजून बंद झालेली नाही ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            continue

        # --- सर्व अटी पूर्ण! Entry — एकच futures leg (options concepts काहीच नाहीत) ---
        transaction_type = "BUY" if direction == "BULLISH" else "SELL"
        entry_price_estimate = float(current_price)
        # 🎓 net_credit चिन्ह-नियम (trading_engine.open_multi_leg_trade() च्या Naked Option पॅटर्नशी
        # सुसंगत) — SELL (credit) = धन, BUY (debit) = ऋण. फक्त bookkeeping साठी; प्रत्यक्ष fill
        # किंमत आल्यावर trading_engine.py स्वतःच त्याच सूत्राने पुन्हा-गणना करून delta नुसार
        # max_loss/max_profit समायोजित करतो (slippage-सुरक्षित, कुठलाही बदल न करता established वर्तन).
        net_credit_estimate = entry_price_estimate if transaction_type == "SELL" else -entry_price_estimate
        leg = {
            "role": "futures_long" if direction == "BULLISH" else "futures_short",
            "instrument_key": instrument_key, "transaction_type": transaction_type,
            "ltp": entry_price_estimate,
            # "strike": 0 — dummy, फक्त trading_engine.py च्या strikes_summary display-स्ट्रिंगसाठी
            # (f"{leg['role']}:{leg['strike']:.0f}") — trading_engine.py ला अजिबात हात न लावता,
            # पूर्णपणे futures-side workaround.
            "strike": 0, "option_type": None, "expiry": resolved.get("expiry"),
        }
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Points सोबतच Percentage mode) — sl_target_mode=="PERCENT"
        # असेल तर entry_price_estimate च्या % वरून points-समतुल्य आकडा काढला जातो — पुढे trading_engine.
        # open_multi_leg_trade() ला नेहमीच points (max_loss/max_profit) च मिळतात, mode तिथे कधीच जात
        # नाही (trading_engine.py ला अजिबात हात न लावता).
        if settings.get("sl_target_mode", "POINTS") == "PERCENT":
            sl_points_effective = entry_price_estimate * float(settings.get("sl_pct", 2.0)) / 100
            target_points_effective = entry_price_estimate * float(settings.get("target_pct", 4.0)) / 100
        else:
            sl_points_effective = float(settings["sl_points"])
            target_points_effective = float(settings["target_points"])
        strategy_result = {
            "strategy": "MCX_FUTURES_LONG" if direction == "BULLISH" else "MCX_FUTURES_SHORT",
            "legs": [leg], "net_credit": net_credit_estimate,
            "max_loss": sl_points_effective, "max_profit": target_points_effective,
        }

        trading_mode = settings.get("trading_mode", "PAPER")
        broker_account_ids = settings.get("broker_account_ids") or []
        if broker_account_ids:
            from trading_engine import execute_trade_on_all_accounts
            results, factory_errors = execute_trade_on_all_accounts(
                symbol=symbol, strategy_result=strategy_result, base_lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=100, target_pct_of_max_profit=100,
                product_type=PRODUCT_TYPE, trading_mode=trading_mode, trading_style="INTRADAY",
                sl_pct_of_credit=None, source=STRATEGY_KEY,
                entry_level_price=level_price, entry_timeframe=timeframe_suffix,
                account_ids=broker_account_ids,
            )
            trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
            if factory_errors:
                trade_status += " | वगळलेले: " + "; ".join(factory_errors)
        else:
            _, trade_status = open_multi_leg_trade(
                access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=100, target_pct_of_max_profit=100,
                product_type=PRODUCT_TYPE, trading_mode=trading_mode, trading_style="INTRADAY",
                sl_pct_of_credit=None, source=STRATEGY_KEY,
                entry_level_price=level_price, entry_timeframe=timeframe_suffix,
            )

        if is_breakout_trade:
            rsi_display = f"📈 Breakout Entry (price consolidation + candle close, {timeframe_suffix}) — RSI Gate वगळले."
        elif entry_rsi_gate_enabled:
            rsi_display = f"RSI {rsi_value} ({timeframe_suffix}), फिल्टर पास"
        else:
            rsi_display = f"RSI Gate बंद ({timeframe_suffix}, तपासलं नाही)"
        log_entry["trade_status"] = trade_status
        if is_breakout_trade:
            log_entry["reason"] = f"Directional (trend-continuation) trade — Breakout Entry (price consolidation + candle close, {timeframe_suffix}), RSI Gate वगळले"
        else:
            log_entry["reason"] = rsi_display
        cloud_db.save_signal_log(log_entry)

        hit_label_header = "🎯 Breakout Entry" if is_breakout_trade else f"🎯 Dynamic S/R Cross (आजचा {hit_count_so_far + 1}/2 वा hit)"
        message = (
            f"{hit_label_header} <b>{symbol} MCX Futures ({timeframe_suffix})</b>\n"
            f"{level_type} {level_price:.2f} — {transaction_type} {resolved['trading_symbol']} (≈{entry_price_estimate:.2f}). {rsi_display}\n"
            f"निकाल: {trade_status}\n"
            f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        return f"{symbol}: 🎯 {level_type} {level_price:.2f} ({timeframe_suffix}) -> {transaction_type} {trade_status}"

    return f"{symbol}: कुठलाही MCX level ({'/'.join(active_suffixes)}, RSI+Multi-Hit मर्यादेसह) पात्र ठरला नाही"


def monitor_symbol(access_token, symbol):
    """उघड्या MCX Futures positions चं SL/Target/Trailing/EOD — established trading_engine.
    manage_open_trades() (कुठलाही बदल न करता, generic "else" branch) — trade_monitor.py चं
    MONITORED_SYMBOLS इथे बदललेलं नाही, त्यामुळे हीच script स्वतःच monitoring करते."""
    settings = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol)
    trailing_sl_enabled = bool(settings.get("trailing_sl_enabled", False))
    trailing_distance_points = settings.get("trailing_distance_points") if trailing_sl_enabled else None
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Points सोबतच Percentage mode) — trailing_pct असेल तर
    # सद्य किंमतीवरून (प्रत्येक monitoring cycle ला ताजी, resolve_symbol()/fetch_mcx_candles()
    # कडून) points-समतुल्य अंतर काढलं जातं — compute_trailing_sl_level() ला अजिबात हात न लावता.
    if trailing_sl_enabled and settings.get("sl_target_mode", "POINTS") == "PERCENT":
        ok, resolved = mcx_resolver.resolve_symbol(access_token, symbol)
        if ok:
            df_current = fetch_mcx_candles(access_token, resolved["instrument_key"], interval="30minute", lookback_days=1)
            if df_current is not None and not df_current.empty:
                current_price = float(df_current["close"].iloc[-1])
                trailing_distance_points = current_price * float(settings.get("trailing_pct", 1.0)) / 100
            else:
                trailing_distance_points = None  # सद्य किंमत मिळाली नाही — या cycle ला trailing वगळणे (सुरक्षित)
        else:
            trailing_distance_points = None
    return manage_open_trades(
        access_token, symbol, PRODUCT_TYPE,
        eod_squareoff_hour=MCX_EOD_HOUR, eod_squareoff_minute=MCX_EOD_MINUTE,
        oi_reversal_exit_enabled=False,
        trailing_sl_enabled=trailing_sl_enabled,
        # atr_multiplier=1.0 — ATR-गुणक नाही, trailing_distance_points इतकेच सरळ points मागे
        # (compute_trailing_sl_level() ला अजिबात हात न लावता — trailing_distance = atr_points *
        # lot_size * lots * atr_multiplier, atr_multiplier=1.0 दिल्याने ते नेमकं
        # trailing_distance_points इतकंच राहतं).
        atr_points=trailing_distance_points, atr_multiplier=1.0,
    )


def run_all_symbols(token, symbols):
    """🎓 established 3 bots प्रमाणेच — प्रत्येक symbol ची entry-तपासणी स्वतंत्र try/except मध्ये,
    एकाच्या अपयशाने बाकीच्यांना/heartbeat ला अडवू नये म्हणून. exit-monitoring आता वेगळ्या
    run_exit_monitor_loop() मधून (खाली बघा — cron slippage कमी करण्यासाठी वेगवान)."""
    any_symbol_succeeded = False
    for symbol in symbols:
        symbol = symbol.strip()
        try:
            print(process_symbol(token, symbol))
            any_symbol_succeeded = True
        except Exception as e:
            notify_error("mcx_futures_trader", f"{symbol}: entry-तपासणी त्रुटी — {e}")
            print(f"⚠️ {symbol}: entry-तपासणी अनपेक्षित त्रुटी — {e}")
    return any_symbol_succeeded


def run_exit_monitor_cycle(token, symbols):
    """प्रत्येक symbol साठी monitor_symbol() (SL/Target/Trailing/EOD) — एकाच cycle मध्ये सर्व
    commodities, एकाच्या अपयशाने बाकीच्यांना न अडवता (established 3 bots च्या पॅटर्नप्रमाणेच)."""
    results = []
    any_symbol_succeeded = False
    for symbol in symbols:
        symbol = symbol.strip()
        try:
            closed = monitor_symbol(token, symbol)
            any_symbol_succeeded = True
            if closed:
                results.append(f"{symbol}: 🔔 {len(closed)} position(s) बंद झाल्या — {closed}")
        except Exception as e:
            notify_error("mcx_futures_trader", f"{symbol}: monitor त्रुटी — {e}")
            results.append(f"⚠️ {symbol}: monitor अनपेक्षित त्रुटी — {e}")
    return results, any_symbol_succeeded


def run_exit_monitor_loop(token, symbols, interval_seconds=15, loop_seconds=30,
                           sleep_fn=time.sleep, now_fn=time.monotonic, print_fn=print):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("exit slippage") — trade_monitor.py च्याच
    run_monitor_loop() पॅटर्नची MCX आवृत्ती — एका cron invocation च्या आत, interval_seconds च्या
    अंतराने loop_seconds पर्यंत run_exit_monitor_cycle() पुन्हा-पुन्हा चालवणे, जेणेकरून SL/Target
    ओलांडल्यानंतर बॉटला कळायला आधीच्या (दर मिनिटाला फक्त एकदा) ऐवजी जास्तीत जास्त
    interval_seconds इतकाच वेळ लागेल. प्रत्येक cycle चा वेळ वजा करूनच पुढचा sleep काढला जातो,
    जेणेकरून एकूण वेळ loop_seconds च्या आसपासच राहील.
    ⚠️ loop_seconds डीफॉल्ट trade_monitor.py च्या 50 पेक्षा मुद्दामच कमी (30) ठेवला — VPS crontab
    मधली MCX ची ओळ स्वतःच आधी `sleep 60` (stampede टाळण्यासाठीचा stagger) करते, म्हणजे प्रत्यक्ष
    काम सुरू व्हायलाच cron-tick नंतर जवळपास पूर्ण मिनिट जातं. entry-तपासणी + हा loop मिळून जर
    उरलेल्या ~60-सेकंद budget पेक्षा जास्त वेळ घेतला, तर पुढची invocation ProcessLockHeld मुळे
    सरळ वगळली जाईल (उलट परिणाम — cycles आणखी विरळ). 30 सेकंद यात सुरक्षित बसतो."""
    start = now_fn()
    any_succeeded_overall = False
    while True:
        cycle_start = now_fn()
        results, any_succeeded = run_exit_monitor_cycle(token, symbols)
        any_succeeded_overall = any_succeeded_overall or any_succeeded
        for r in results:
            print_fn(r)
        elapsed = now_fn() - start
        remaining_in_budget = loop_seconds - elapsed
        if remaining_in_budget <= 0:
            break
        cycle_duration = now_fn() - cycle_start
        sleep_time = min(interval_seconds - cycle_duration, remaining_in_budget)
        if sleep_time > 0:
            sleep_fn(sleep_time)
    return any_succeeded_overall


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(MCX_FUTURES_SYMBOLS))
    parser.add_argument("--interval-seconds", type=float, default=15,
                         help="exit-monitoring किती सेकंदांच्या अंतराने पुन्हा तपासायचं (डीफॉल्ट 15, trade_monitor.py सारखंच)")
    parser.add_argument("--loop-seconds", type=float, default=30,
                         help="एका cron invocation मध्ये exit-monitoring किती सेकंद पुन्हा-पुन्हा तपासत राहायचं (डीफॉल्ट 30 — MCX crontab च्या आधीच्या sleep 60 stagger नंतरच्या उरलेल्या budget मध्ये सुरक्षित बसावं म्हणून, trade_monitor.py च्या 50 पेक्षा कमी)")
    args = parser.parse_args()

    # 🎓 established 3 bots प्रमाणेच — Duplicate-Order Protection (VPS crontab वर मंद network/retry
    # मुळे मागची invocation अजून चालू असू शकते; अशा वेळी नवीन invocation डुप्लिकेट ऑर्डर टाळण्यासाठी थांबते).
    try:
        with ProcessLock("mcx_futures_trader"):
            init_sqlite_db()
            cloud_db.init_cloud_table()
            token = cloud_db.get_effective_upstox_token(args.token)
            if not token:
                msg = "कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही)."
                print(f"❌ {msg}")
                # 🎓 वापरकर्त्याने मागितलेली सुधारणा (LIVE readiness — "token-missing वर Telegram
                # अलर्ट") — याआधी हा path पूर्णपणे गप्प राहायचा (फक्त cron log मध्ये print, कुठलाही
                # अलर्ट नाही) — बाकी सर्व failure-paths (kill switch/margin/order-failure) आधीच
                # Telegram अलर्ट पाठवतात, पण नेमकं इथेच (सकाळी token expire झालेला असेल तर) गप्प राहणं
                # सर्वात धोकादायक होतं — संपूर्ण दिवसभर बॉट काहीच न करता शांतपणे थांबून राहू शकायचा,
                # कुणालाच न कळता.
                notify_error("mcx_futures_trader", msg)
                exit(1)
            symbols_list = args.symbols.split(",")
            entry_succeeded = run_all_symbols(token, symbols_list)
            exit_succeeded = run_exit_monitor_loop(token, symbols_list, args.interval_seconds, args.loop_seconds)
            if entry_succeeded or exit_succeeded:
                write_heartbeat("mcx_futures_trader")
            run_auto_backup_if_due(interval_minutes=60)
    except ProcessLockHeld as e:
        print(f"⏭️ मागची invocation अजून चालू आहे, ही वगळली — डुप्लिकेट ऑर्डर टाळण्यासाठी ({e})")
