"""
srv2_momentum_reversal_strategy.py
------------------------------------------------
Nifty SRv2 Momentum-Filter Reversal — आता Multi-Timeframe (15-मिनिट + 30-मिनिट + 60-मिनिट एकत्र).

वापरकर्त्याशी चर्चा करून ठरवलेली रचना:
  - तिन्ही timeframes (15M/30M/60M) चे ACTIVE Dynamic S/R levels एकाच यादीत एकत्र तपासले जातात.
  - "First come, first touch" — कुठलाही एक (कुठल्याही timeframe चा) पात्र ठरला, की तोच घेतला जातो.
    कुठल्याही timeframe ला प्राधान्य नाही.
  - Position-मर्यादा एकत्रित — तिन्ही timeframes मिळून एकाच वेळी फक्त एकच उघडी position.
  - SL लागल्यावर, पुढचा (कुठल्याही timeframe चा) touch पुन्हा trade करू शकतो.
  - Support/Resistance ही सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून ठरते (साठवलेल्या ऐतिहासिक
    label वरून नाही) — एक level Support/Resistance मध्ये "रूपांतरित" होऊ शकतो.
  - RSI(14, त्याच timeframe चा) फिल्टर — Resistance/Bearish साठी RSI>50, Support/Bullish साठी RSI<50.
  - Lots आणि Hedge Width Points आता Dashboard वरून बदलता येतात (cloud_db.srv2_settings, hardcode नाही).
  - Expiry Day ला (आजची तारीख == चालू साप्ताहिक expiry) पुढच्या आठवड्याच्या expiry चे strikes वापरले
    जातात (expiry_index=1) — जास्त जोखीम टाळण्यासाठी.
  - Exit-रचना (trading_engine.py मध्ये केंद्रीकृत) — Spot SL(0.10%, entry_level_price पासून) +
    Premium Target(80%) + Next-Level-Exit (15M/30M/60M पूल केलेले) — जे आधी घडेल ते.

Multi-Hit (per-level, दिवसातून कमाल 2 वेळा) आणि Cooldown (SL नंतर 30 मिनिटं, symbol-व्यापी) — आधीचेच.
"""
import argparse

import pandas as pd

import cloud_db
from config import get_ist_now
from database import init_sqlite_db, has_open_trade_from_source, run_auto_backup_if_due
from notifications import send_telegram_message, write_heartbeat, notify_error
from process_lock import ProcessLock, ProcessLockHeld
from signals import calculate_rsi, resample_to_1h
from strategy import select_credit_spread_itm, select_naked_option_itm
from oi_analysis import check_pcr_gate
from trading_engine import open_multi_leg_trade
from upstox_api import fetch_upstox_option_chain, fetch_candles, fetch_option_expiries

RSI_NEUTRAL_LEVEL = 50
TOUCH_TOLERANCE_PCT = 0.05
SL_PCT_OF_CREDIT = 30
TARGET_PCT_OF_PREMIUM = 80
COOLDOWN_MINUTES = 30
LEVEL_REPEAT_TOLERANCE_PCT = 0.05

# वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Multi-Timeframe. Upstox interval-नाव -> zone_type suffix.
TIMEFRAME_TO_SUFFIX = {"15minute": "15M", "30minute": "30M", "60minute": "60M"}


def check_rsi_filter(candles_df, direction, neutral_level=RSI_NEUTRAL_LEVEL):
    """Rule 1 — 15/30/60-मिनिट (candles_df ज्या timeframe चा असेल त्याचा) RSI(14) दिशेशी सुसंगत आहे का.
    direction: "BULLISH" (Support Bounce) -> RSI 50 च्या खाली हवा.
    "BEARISH" (Resistance Bounce) -> RSI 50 च्या वर हवा.
    रिटर्न: (pass: bool, rsi_value: float किंवा None)"""
    rsi_series = calculate_rsi(candles_df, period=14)
    if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
        return False, None
    latest_rsi = round(float(rsi_series.iloc[-1]), 2)
    if direction == "BULLISH":
        return latest_rsi < neutral_level, latest_rsi
    return latest_rsi > neutral_level, latest_rsi


def compute_sl_pct_from_absolute(sl_rupees, net_credit_total):
    """sl_pct_of_credit (%) मध्ये रूपांतरित, वापरकर्त्याने दिलेल्या रुपये रकमेवरून."""
    if net_credit_total <= 0:
        return None
    return min((sl_rupees / net_credit_total) * 100, 100)


def is_in_cooldown(last_sl_hit_time, now):
    """Rule (Cooldown) — SL लागल्यावर COOLDOWN_MINUTES पर्यंत नवीन entry नाही."""
    if last_sl_hit_time is None:
        return False
    elapsed_minutes = (now - last_sl_hit_time).total_seconds() / 60
    return elapsed_minutes < COOLDOWN_MINUTES


def is_repeated_level(level_price, last_tested_level, tolerance_pct=LEVEL_REPEAT_TOLERANCE_PCT):
    """जुना One-Touch नियम — आता मुख्य प्रवाहात वापरला जात नाही (Multi-Hit ने replace केलं),
    backward-compatible म्हणून तसंच ठेवलेलं. तोच level (tolerance च्या आत) लगेच पुन्हा टेस्ट झाला का."""
    if last_tested_level is None:
        return False
    tolerance = level_price * tolerance_pct / 100
    return abs(level_price - last_tested_level) <= tolerance


def is_todays_expiry_day(access_token, symbol):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Expiry-Day Logic) — आज चालू (सर्वात जवळची)
    साप्ताहिक expiry आहे का, हे प्रत्यक्ष option-chain expiry-यादीवरून तपासणे (गृहीत धरलेला वार नाही)."""
    expiries = fetch_option_expiries(access_token, symbol)
    if not expiries:
        return False
    today_str = get_ist_now().strftime("%Y-%m-%d")
    return expiries[0] == today_str


def _collect_touch_candidates(access_token, symbol, all_zones, now):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Timeframe) — 15M/30M/60M तिन्हींचे ACTIVE
    levels, प्रत्येकाचे स्वतःचे candles (त्याच timeframe चा RSI साठी) आणि सद्य किंमत (आजच्याच
    दिवसाची, कालचे candles मिसळू नयेत म्हणून) — एकाच यादीत एकत्र करणे.
    रिटर्न: [(level_price, timeframe_suffix, candles_df, underlying_price), ...]"""
    candidates = []
    today_date = now.date()
    for interval, suffix in TIMEFRAME_TO_SUFFIX.items():
        dyn_levels = all_zones[(all_zones["zone_type"].str.endswith(f"_{suffix}")) & (all_zones["status"] == "ACTIVE")]
        if dyn_levels.empty:
            continue
        if interval == "60minute":
            # 🎓 वापरकर्त्याने सापडवलेली bug — "60minute"/"1hour" Upstox कडून थेट verified नाही
            # (fetch_candles() मध्ये allowed_intervals यादीत नाही, त्यामुळे आधी शांतपणे "30minute"
            # कडे पडायचं, पण RSI(14) "60M" चाच आहे असं भासवत राहायचं). आता fetch_timeframe_df()
            # मध्ये आधीच वापरलेला पॅटर्न — 30-मिनिट candles मागवून resample करणे.
            df_30m = fetch_candles(access_token, symbol, current_spot=0, interval="30minute", lookback_days=5)
            candles_df = resample_to_1h(df_30m) if df_30m is not None and not df_30m.empty else df_30m
        else:
            candles_df = fetch_candles(access_token, symbol, current_spot=0, interval=interval, lookback_days=5)
        if candles_df is None or candles_df.empty or len(candles_df) < 12:
            continue
        candles_df = candles_df.copy()
        candles_df["_date"] = candles_df["timestamp"].dt.date
        todays_candles_df = candles_df[candles_df["_date"] == today_date]
        if todays_candles_df.empty:
            continue
        underlying_price = todays_candles_df["close"].iloc[-1]
        for _, zrow in dyn_levels.iterrows():
            candidates.append((zrow["zone_low"], suffix, candles_df, underlying_price))
    return candidates


def process_symbol(access_token, symbol, lot_size=65):
    """एका symbol साठी — 15M/30M/60M levels एकत्र, RSI-फिल्टर, Multi-Hit/Cooldown, Expiry-Day
    Logic, आणि आढळल्यास PAPER trade (settings-चालित lots/hedge_width_points सह)."""
    settings = cloud_db.get_strategy_settings("15m_dynamic_sr", symbol)
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (symbol_enabled) — उपलब्ध भांडवलानुसार वापरकर्ता
    # Bot Dynamic SR Algo पानावरून प्रत्येक symbol स्वतंत्रपणे चालू/बंद करू शकतो — बंद असलेल्या
    # symbol वर इथेच थांबतो, पुढचं काहीही (cooldown/state check, candles fetch, trade) होत नाही.
    if not settings.get("symbol_enabled", symbol == "NIFTY"):
        return f"{symbol}: बंद आहे (symbol_enabled=False, Bot Dynamic SR Algo सेटिंग्जमधून सक्रिय करा)"

    now = get_ist_now()
    state = cloud_db.get_srv2_state(symbol)

    if is_in_cooldown(state["last_sl_hit_time"], now):
        return f"{symbol}: Cooldown कालावधी चालू आहे (SL नंतर {COOLDOWN_MINUTES} मिनिटं विराम)"

    lots = settings["lots"]
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py प्रमाणेच — Naked Option
    # Trade आता Credit Spread पासून स्वतंत्र lots सेटिंग वापरतो.
    naked_lots = settings.get("naked_lots", lots)
    entry_rsi_gate_enabled = settings.get("entry_rsi_gate_enabled", True)
    rsi_neutral_level = settings.get("rsi_neutral_level", RSI_NEUTRAL_LEVEL)
    entry_pcr_gate_enabled = settings.get("entry_pcr_gate_enabled", True)
    # 🎓 वापरकर्त्याने पडताळणीत सापडवलेली bug (live trading आधी) — Dashboard वरचं "Target — % of Net
    # Premium" setting (spread_target_pct_of_premium, page_bot_dynamic_sr_algo.py) आधी इथे कधीच
    # वाचलंच जायचं नाही — नेहमी हार्डकोडेड TARGET_PCT_OF_PREMIUM (80%) वापरला जायचा. वापरकर्त्याने
    # 40% सेट केलं तरी bot शांतपणे 80% वरच थांबत राहायचा.
    target_pct_of_premium = settings.get("spread_target_pct_of_premium", TARGET_PCT_OF_PREMIUM)

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    trade_date = now.strftime("%Y-%m-%d")
    candidates = _collect_touch_candidates(access_token, symbol, all_zones, now)
    if not candidates:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels (15M/30M/60M) सापडले नाहीत, किंवा आजचे candles अजून तयार नाहीत"

    for level_price, timeframe_suffix, candles_df, underlying_price in candidates:
        touched = abs(underlying_price - level_price) <= level_price * TOUCH_TOLERANCE_PCT / 100

        # वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — दिशा सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून.
        if underlying_price >= level_price:
            level_type, direction = "SUPPORT", "BULLISH"
        else:
            level_type, direction = "RESISTANCE", "BEARISH"

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Market Zones tab वर 1-मिनिट Instant Trader
        # सारखाच संपूर्ण Signal Log, SRv2 साठीही) — याआधी इथे फक्त प्रत्यक्ष trade झाला तरच
        # save_signal_log() व्हायचं; touch न झालेले किंवा कुठल्याही gate ने अडवलेले candidates
        # कधीच साठवले जात नव्हते, त्यामुळे entry/exit cross-verify करायला काहीच data नव्हतं. आता
        # प्रत्येक तपासलेला candidate (NO_HIT सकट) इथे लगेच साठवला जातो.
        log_entry = {
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": level_type,
            "level_price": level_price, "hit_type": "TOUCH" if touched else "NO_HIT",
            "direction": direction if touched else "NONE", "ltp_at_signal": underlying_price,
            "trade_status": None,
            "reason": "" if touched else f"level ला स्पर्श (touch) आढळला नाही ({timeframe_suffix})",
        }

        if not touched:
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 Execution-testing मध्ये सापडवलेली गंभीर bug — rsi_value आधी फक्त "if entry_rsi_gate_enabled:"
        # च्या आतच ठरायचा, पण खाली (save_signal_log आणि Telegram संदेशात, यशस्वी trade नंतर लगेचच)
        # कायम वापरला जायचा — RSI Gate बंद केला की इथे NameError येऊन order प्लेस झाल्यानंतरही
        # entire script क्रॅश व्हायचा (Naked leg, Telegram, दोन्हीही कधीच पोहोचायचेच नाहीत). आता आधीच
        # None ने सुरुवात.
        rsi_value = None
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Gate — on/off) — RSI Gate आता Dashboard
        # वरून पूर्णपणे बंद करता येतो.
        if entry_rsi_gate_enabled:
            rsi_ok, rsi_value = check_rsi_filter(candles_df, direction, rsi_neutral_level)
            if not rsi_ok:
                log_entry["trade_status"] = "SKIPPED_RSI_FILTER"
                log_entry["reason"] = f"RSI {rsi_value} ({timeframe_suffix}) दिशेशी जुळत नाही (Bullish<{rsi_neutral_level} / Bearish>{rsi_neutral_level} हवं होतं)"
                cloud_db.save_signal_log(log_entry)
                continue

        # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (PCR Gate — on/off) — दोन्ही trade-प्रकारांना
        # (Credit Spread + Naked) एकत्र लागू, पण आता Dashboard वरून पूर्णपणे बंदही करता येतो. बंद
        # नसेल तरच — डेटा गहाळ/जुना असल्यास सुरक्षिततेसाठी trade थांबवणे (fail-safe).
        if entry_pcr_gate_enabled:
            pcr_ok, pcr_value, pcr_reason = check_pcr_gate(symbol, direction, settings["pcr_bullish_min"], settings["pcr_bearish_max"])
            if not pcr_ok:
                log_entry["trade_status"] = "SKIPPED_PCR_GATE"
                log_entry["reason"] = f"{pcr_reason} ({timeframe_suffix})"
                cloud_db.save_signal_log(log_entry)
                continue

        # Multi-Hit — बिनशर्त position-check (कुठल्याही level/timeframe साठी). support/resistance
        # साठी स्वतंत्र कमाल-2 counter (role= दिलं) — तोच level भूमिका बदलून (support->resistance
        # किंवा उलट) दुसऱ्या दिशेने test झाला तर तो एक वेगळाच candidate मानला जातो.
        hit_count_so_far, _, _ = cloud_db.get_zone_hits_today(symbol, level_price, trade_date, role=level_type)
        if hit_count_so_far >= 2:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = f"आजच्या या zone साठी (याच role) कमाल 2 वेळा मर्यादा आधीच गाठलेली ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            continue
        if has_open_trade_from_source(symbol, "srv2_momentum_reversal"):
            log_entry["trade_status"] = "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"
            log_entry["reason"] = f"आधीची position (या strategy ची, कुठल्याही level/timeframe वरची) अजून बंद झालेली नाही ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            continue

        # --- सर्व अटी पूर्ण! Entry ---
        # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Expiry-Day Logic) — आज expiry day असेल, तर
        # पुढच्या आठवड्याचे strikes (expiry_index=1) — आजच्या expiry वर trade नाही (जास्त जोखीम).
        expiry_index = 1 if is_todays_expiry_day(access_token, symbol) else 0
        raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol, expiry_index=expiry_index)
        if not raw_chain:
            return f"{symbol}: Option chain मिळाली नाही ({chain_status})"
        strike_step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
        atm_strike = round(underlying_price / strike_step) * strike_step

        spread_result = select_credit_spread_itm(
            raw_chain, direction, atm_strike, step=strike_step,
            itm_depth_points=settings["itm_depth_points"], hedge_width_points=settings["hedge_width_points"],
        )
        if spread_result is None:
            log_entry["trade_status"] = "STRATEGY_SELECTION_FAILED"
            log_entry["reason"] = f"strike-निवड अयशस्वी ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
            return f"{symbol}: {level_type} {level_price:.2f} ({timeframe_suffix}) टेस्ट झाला, पण strike-निवड अयशस्वी"

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (PAPER/LIVE टॉगल + per-strategy Broker Selection) —
        # dynamic_sr_instant_trader.py प्रमाणेच — settings मधल्याच trading_mode/broker_account_ids
        # वरून, "कुठलेही broker_accounts नोंदवलेले असतील तर सर्व सक्रिय accounts" ऐवजी.
        trading_mode = settings.get("trading_mode", "PAPER")
        broker_account_ids = settings.get("broker_account_ids") or []
        if broker_account_ids:
            from trading_engine import execute_trade_on_all_accounts
            results, factory_errors = execute_trade_on_all_accounts(
                symbol=symbol, strategy_result=spread_result, base_lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_premium,
                product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                sl_pct_of_credit=100, source="srv2_momentum_reversal",
                entry_level_price=level_price, entry_timeframe=timeframe_suffix,
                account_ids=broker_account_ids,
            )
            trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
            if factory_errors:
                trade_status += " | वगळलेले: " + "; ".join(factory_errors)
        else:
            trade_result, trade_status = open_multi_leg_trade(
                access_token, symbol, spread_result, lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_premium,
                product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                sl_pct_of_credit=100, source="srv2_momentum_reversal",
                entry_level_price=level_price, entry_timeframe=timeframe_suffix,
            )

        rsi_reason = f"RSI {rsi_value} ({timeframe_suffix}), फिल्टर पास" if entry_rsi_gate_enabled else f"RSI Gate बंद ({timeframe_suffix}, तपासलं नाही)"
        cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
        log_entry["trade_status"] = trade_status
        log_entry["reason"] = rsi_reason
        cloud_db.save_signal_log(log_entry)

        naked_status = ""
        naked_result = None
        # 🎓 वापरकर्त्याने विचारलेला प्रश्न ("naked trade execute झाला नाही") सोडवण्यासाठी जोडलेली
        # सुधारणा — आधी हे फक्त print() (फक्त GitHub Actions/VPS logs मध्ये दिसायचं) होतं, आता
        # signal_log मध्येही नोंदवलं जातं — त्यामुळे Dashboard वरच्या Market Zones → Signal Log
        # मध्ये (कुठल्याही log-access शिवाय) नेमकं कारण दिसेल.
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
                print(f"⚠️ {naked_diag_entry['reason']} — symbol={symbol}, direction={direction}")
        else:
            naked_diag_entry["trade_status"] = "SKIPPED_NAKED_DISABLED"
            naked_diag_entry["reason"] = "naked_enabled=False (Bot Dynamic SR Algo सेटिंग्जमध्ये बंद)"
            cloud_db.save_signal_log(naked_diag_entry)
            print(f"ℹ️ Naked trade बंद आहे (naked_enabled=False, settings — symbol={symbol}, strategy=15m_dynamic_sr)")
        if naked_result is not None:
            if broker_account_ids:
                from trading_engine import execute_trade_on_all_accounts
                naked_results, naked_factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=naked_result, base_lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="srv2_momentum_reversal",
                    entry_level_price=level_price, entry_timeframe=timeframe_suffix,
                    account_ids=broker_account_ids,
                )
                naked_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in naked_results) or "कुठलाही account उपलब्ध नाही"
            else:
                _, naked_status = open_multi_leg_trade(
                    access_token, symbol, naked_result, lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="srv2_momentum_reversal",
                    entry_level_price=level_price, entry_timeframe=timeframe_suffix,
                )

        strategy_label = "Bull Put Spread (Support Bounce)" if direction == "BULLISH" else "Bear Call Spread (Resistance Bounce)"
        naked_line = f"Naked Option: {naked_result.get('strategy', direction)} — {naked_status}\n" if naked_result is not None else ""
        rsi_display = f"RSI {rsi_value} (फिल्टर पास)" if entry_rsi_gate_enabled else "RSI Gate बंद (तपासलं नाही)"
        message = (
            f"🎯 <b>{symbol} SRv2 Momentum-Reversal ({timeframe_suffix})</b> (आजचा {hit_count_so_far + 1}/2 वा hit)\n"
            f"{level_type} {level_price:.2f} — {rsi_display}.\n"
            f"Credit Spread: {strategy_label} — {trade_status}\n"
            + naked_line
            + f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        return f"{symbol}: 🎯 {level_type} {level_price:.2f} ({timeframe_suffix}, {rsi_display}) -> {strategy_label} PAPER trade {trade_status}"

    return f"{symbol}: कुठलाही SRv2 level (15M/30M/60M, RSI+Multi-Hit मर्यादेसह) पात्र ठरला नाही"


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
            notify_error("srv2_momentum_reversal", f"{symbol.strip()}: {e}")
            print(f"⚠️ {symbol.strip()}: अनपेक्षित त्रुटी — {e}")
    return any_symbol_succeeded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — इथला डीफॉल्ट आता refresh_market_zones.py सारखाच
    # तिन्ही symbols — प्रत्यक्ष कोणत्या symbol वर trade घ्यायचा हे आता process_symbol() च्या आतल्या
    # symbol_enabled सेटिंगवरून ठरतं (Bot Dynamic SR Algo पानावरून, उपलब्ध भांडवलानुसार), या CLI
    # यादीवरून नाही — त्यामुळे VPS crontab मध्ये --symbols बदलावं लागत नाही.
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    args = parser.parse_args()

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Duplicate-Order Protection, गंभीर
    # यादीतला पाचवा मुद्दा) — dynamic_sr_instant_trader.py सारखीच सुधारणा (VPS crontab वर दर १
    # मिनिटाला चालणारी script मंद network मुळे जास्त वेळ घेतली, तर overlapping invocation
    # डुप्लिकेट ऑर्डर पाठवू शकते — आधीचीच invocation अजून चालू असेल, तर इथेच थांबतो).
    try:
        with ProcessLock("srv2_momentum_reversal_strategy"):
            init_sqlite_db()
            cloud_db.init_cloud_table()
            token = cloud_db.get_effective_upstox_token(args.token)
            if not token:
                print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
                exit(1)
            any_symbol_succeeded = run_all_symbols(token, args.symbols.split(","))
            if any_symbol_succeeded:
                write_heartbeat("srv2_momentum_reversal")  # 🎓 Production-readiness सुधारणा — याआधी हे script कधीच heartbeat नोंदवत नव्हतं
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Crash Recovery / DB Backup) —
            # dynamic_sr_instant_trader.py सारखीच सुधारणा.
            run_auto_backup_if_due(interval_minutes=60)
    except ProcessLockHeld as e:
        print(f"⏭️ मागची invocation अजून चालू आहे, ही वगळली — डुप्लिकेट ऑर्डर टाळण्यासाठी ({e})")
