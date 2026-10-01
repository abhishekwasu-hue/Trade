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
from database import init_sqlite_db, has_open_trade_from_source, get_last_sl_tsl_exit_time, run_auto_backup_if_due
# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("RSI setting 60/40 अशी करा") — established single, सममित
# rsi_neutral_level (50) ऐवजी आता dynamic_sr_instant_trader.py/mcx_futures_trader.py सारखाच
# dual-threshold RSI गेट (Support<40 / Resistance>60, established, सिद्ध तर्क — नवीन कॉपी नाही).
from dynamic_sr_instant_trader import check_instant_rsi_filter, check_level_crossed, close_open_5m_positions, count_consecutive_touch_minutes
from notifications import send_telegram_message, write_heartbeat, notify_error
from process_lock import ProcessLock, ProcessLockHeld
from signals import resample_to_1h
from strategy import select_credit_spread_itm, select_naked_option_itm
from oi_analysis import check_pcr_gate
from trading_engine import open_multi_leg_trade, format_trade_result
from upstox_api import fetch_upstox_option_chain, fetch_candles, fetch_option_expiries

# 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("15 मिनिट लेवल हिट बफर remove करा", 1-मिनिट candles) —
# आधी touch = शेवटच्या 15M candle च्या close किमतीचं level पासूनचं अंतर <= 0.05% (सुमारे 11 पॉइंट) होतं,
# म्हणजे किंमत level ला प्रत्यक्ष न पोहोचताही "touch" मानला जायचा. आता buffer 0: शेवटच्या 2 (1-मिनिट)
# candles ची [low,high] रेंज level ला प्रत्यक्ष स्पर्श करते (किंवा दोन candles मधल्या gap मधून level ओलांडला
# जातो) तेव्हाच touch — dynamic_sr_instant_trader.check_level_crossed(). (साधं 0 tolerance वर आधीचं
# 'सद्य किंमत == level' तपासणं कधीच पूर्ण झालं नसतं, म्हणून candle-रेंज पद्धत.)
TOUCH_TOLERANCE_PCT = 0.0
SL_PCT_OF_CREDIT = 30
TARGET_PCT_OF_PREMIUM = 80
COOLDOWN_MINUTES = 30
# 🎓 entry-gate review मध्ये सापडलेली bug — 5M Instant Trader व Classic SR मध्ये 14:45 नंतर नवीन entry
# नाही (EOD exit जवळ आल्यावर उघडलेला trade लगेचच बंद व्हायचा), पण या 15M SRv2 मध्ये हा कट-ऑफ नव्हताच
# (cron 15:59 IST पर्यंत चालतो) — त्यामुळे 15:00 EOD च्या काही मिनिटं आधीही नवीन trade उघडू शकायचा.
NO_NEW_ENTRY_AFTER_HOUR = 14
NO_NEW_ENTRY_AFTER_MINUTE = 45
LEVEL_REPEAT_TOLERANCE_PCT = 0.05
# 🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py मधलाच hysteresis-आधारित
# direction-निर्णय (बघा determine_direction_with_hysteresis()) आता इथेही, पण 15M/30M/60M चे
# candles वापरत असल्याने (1M/5M पेक्षा साहजिकच कमी noisy) वेगळा, अरुंद buffer — 0.015% (त्या
# फाईलमधल्या 0.10% पेक्षा वेगळा, स्वतंत्र constant — दोन्ही bots एकमेकांपासून स्वतंत्र राहतात).
DIRECTION_HYSTERESIS_BUFFER_PCT = 0.015

# वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Multi-Timeframe. Upstox interval-नाव -> zone_type suffix.
TIMEFRAME_TO_SUFFIX = {"15minute": "15M", "30minute": "30M", "60minute": "60M"}


def determine_direction_with_hysteresis(level, closes, buffer_pct=DIRECTION_HYSTERESIS_BUFFER_PCT):
    """🎓 dynamic_sr_instant_trader.py मधल्याच फंक्शनची हुबेहूब नक्कल (वापरकर्त्याने तिथेही, इथेही
    hysteresis लावायला सांगितलं) — किंमत level पासून ±buffer_pct% च्या आतच (borderline) असेल, तर
    आधीचीच "निश्चित" दिशा कायम ठेवायची (उगाच फ्लिप नाही). closes (त्या candidate च्या timeframe
    च्या आजच्या सर्व candles च्या close किमती, जुनं ते नवीन क्रमाने) मधून मागे जाऊन, ज्या पहिल्या
    candle चं close त्या बॅंडच्या (level±buffer) स्पष्टपणे बाहेर आहे, तीच शेवटची निश्चित दिशा मानली
    जाते. दिवसभर कधीच बॅंडबाहेर गेलं नसेल, तर सद्य किमतीची raw तुलनाच (जुनं वर्तन) safe fallback.
    रिटर्न: "BULLISH"/"BEARISH" """
    buffer = level * buffer_pct / 100
    upper, lower = level + buffer, level - buffer
    for close in reversed(closes):
        if close >= upper:
            return "BULLISH"
        if close <= lower:
            return "BEARISH"
    return "BULLISH" if closes[-1] >= level else "BEARISH"


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


def _collect_touch_candidates(access_token, symbol, all_zones, now, active_timeframes=None):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Timeframe) — 15M/30M/60M पैकी established
    active_timeframes मध्ये असलेल्यांचेच ACTIVE levels, प्रत्येकाचे स्वतःचे candles (त्याच timeframe
    चा RSI साठी) आणि सद्य किंमत (आजच्याच दिवसाची, कालचे candles मिसळू नयेत म्हणून) — एकाच यादीत
    एकत्र करणे.
    🎓 वापरकर्त्याने मागितलेली सुधारणा ("15 minute डीफॉल्ट, 30/60 optional") — active_timeframes
    (उदा. ["15M"] किंवा ["15M","30M"]) दिलं नाही (None, established जुने कॉलर्स/tests) तर established
    जुनंच वर्तन — तिन्ही (15M/30M/60M) एकत्र.
    रिटर्न: [(level_price, timeframe_suffix, candles_df, underlying_price, todays_closes), ...]"""
    if active_timeframes is None:
        active_timeframes = list(TIMEFRAME_TO_SUFFIX.values())
    candidates = []
    today_date = now.date()
    for interval, suffix in TIMEFRAME_TO_SUFFIX.items():
        if suffix not in active_timeframes:
            continue
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
        todays_closes = todays_candles_df["close"].tolist()
        for _, zrow in dyn_levels.iterrows():
            candidates.append((zrow["zone_low"], suffix, candles_df, underlying_price, todays_closes))
    return candidates


def _fetch_todays_1m_candles(access_token, symbol, now):
    """आजचे सर्व 1-मिनिट candles (जुनं ते नवीन) [{"open","high","low","close",...}, ...]. मिळाले नाहीत /
    चूक झाली तर रिकामी यादी (त्या cycle ला कुठलाच touch मानला जात नाही — सुरक्षित)."""
    try:
        df = fetch_candles(access_token, symbol, current_spot=0, interval="1minute", lookback_days=1)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    df = df.copy()
    df = df[df["timestamp"].dt.date == now.date()]
    return df.to_dict("records")


def _fetch_recent_1m_candles(access_token, symbol, now, count=2):
    """आजचे शेवटचे `count` 1-मिनिट candles (जुनं ते नवीन) — touch तपासण्यासाठी (buffer शिवाय,
    candle-रेंजवरून). मिळाले नाहीत / चूक झाली तर रिकामी यादी."""
    return _fetch_todays_1m_candles(access_token, symbol, now)[-count:]


def _yield_open_5m_positions(access_token, symbol, trading_mode):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (5M+15M "एका वेळी एकच position"; 15M ला प्राधान्य) — 15M नवीन
    entry घेण्याआधी, याच symbol चे उघडे 5M-कुटुंबातले trades लगेच बंद (भांडवल मोकळं). फक्त 5M चा
    `defer_to_15m_enabled` चालू असेल आणि 5M चा trading_mode याच (15M च्या) mode शी जुळत असेल तरच; नाहीतर काहीच नाही.
    रिटर्न: (पुढे entry घेता येईल: bool, बंद केलेले_ids: list). काहीही बंद होऊ शकलं नाही तर (False, ...) —
    त्या cycle ला 15M entry घेत नाही (सुरक्षित)."""
    try:
        s5 = cloud_db.get_strategy_settings("1m_instant", symbol)
        if not s5.get("defer_to_15m_enabled", False) or s5.get("trading_mode", "PAPER") != trading_mode:
            return True, []
        all_closed, closed_ids, _failed = close_open_5m_positions(
            access_token, symbol,
            "The 15M strategy is entering; its open 5M trades were closed first so only one position is held at a time.",
        )
    except Exception:
        return False, []
    return all_closed, closed_ids


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
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Max trade on same level yachi setting sidhha द्या, default
    # 2") — बघा dynamic_sr_instant_trader.py मधली टिप्पणी.
    max_hits_per_zone = int(settings.get("max_hits_per_zone", 2))
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py प्रमाणेच — Naked Option
    # Trade आता Credit Spread पासून स्वतंत्र lots सेटिंग वापरतो.
    naked_lots = settings.get("naked_lots", lots)
    bullish_entry_enabled = settings.get("bullish_entry_enabled", True)
    bearish_entry_enabled = settings.get("bearish_entry_enabled", True)
    entry_rsi_gate_enabled = settings.get("entry_rsi_gate_enabled", True)
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("RSI setting 60/40 अशी करा") — dynamic_sr_instant_trader.py/
    # mcx_futures_trader.py सारखेच dual-threshold defaults (established single rsi_neutral_level=50
    # ऐवजी).
    rsi_support_max = settings.get("rsi_support_max", 40)
    rsi_resistance_min = settings.get("rsi_resistance_min", 60)
    entry_pcr_gate_enabled = settings.get("entry_pcr_gate_enabled", True)
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("15 minute डीफॉल्ट ठेवा, 30 आणि 60 minute optional राहील") —
    # आधी तिन्ही (15M/30M/60M) नेहमीच एकत्र तपासले जायचे, निवडीची सोयच नव्हती. आता Dashboard वरून
    # (Entry Gate) निवडलेले टाईमफ्रेम्स — डीफॉल्ट फक्त 15M.
    active_timeframes = settings.get("active_timeframes", ["15M"])
    if not active_timeframes:
        active_timeframes = ["15M"]  # सुरक्षा-कवच — चुकून सर्व अनचेक झाले तरी bot पूर्णपणे बधिर होऊ नये
    # 🎓 वापरकर्त्याने पडताळणीत सापडवलेली bug (live trading आधी) — Dashboard वरचं "Target — % of Net
    # Premium" setting (spread_target_pct_of_premium, page_bot_dynamic_sr_algo.py) आधी इथे कधीच
    # वाचलंच जायचं नाही — नेहमी हार्डकोडेड TARGET_PCT_OF_PREMIUM (80%) वापरला जायचा. वापरकर्त्याने
    # 40% सेट केलं तरी bot शांतपणे 80% वरच थांबत राहायचा.
    target_pct_of_premium = settings.get("spread_target_pct_of_premium", TARGET_PCT_OF_PREMIUM)
    entry_min_hold_gate_enabled = settings.get("entry_min_hold_gate_enabled", False)
    entry_min_hold_minutes = settings.get("entry_min_hold_minutes", 3)
    entry_min_hold_first_trade_only = settings.get("entry_min_hold_first_trade_only", True)

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    trade_date = now.strftime("%Y-%m-%d")
    candidates = _collect_touch_candidates(access_token, symbol, all_zones, now, active_timeframes=active_timeframes)
    if not candidates:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels (15M/30M/60M) सापडले नाहीत, किंवा आजचे candles अजून तयार नाहीत"

    todays_1m_candles = _fetch_todays_1m_candles(access_token, symbol, now)
    recent_1m_candles = todays_1m_candles[-2:]
    for level_price, timeframe_suffix, candles_df, underlying_price, todays_closes in candidates:
        touched, touch_type, _approx = (
            check_level_crossed(level_price, recent_1m_candles, tolerance_pct=TOUCH_TOLERANCE_PCT)
            if recent_1m_candles else (False, None, None)
        )

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा — आधी दिशा फक्त सद्य किमतीच्या raw तुलनेवरून ठरायची
        # (dynamic_sr_instant_trader.py मध्ये आधी होतं तसंच) — आता तिथल्याच hysteresis logic ने,
        # पण इथे 0.015% (अरुंद) buffer सह — किंमत level पासून त्या बँडच्या आतच wobble करत असेल,
        # तर आधीचीच निश्चित दिशा कायम राहते.
        direction = determine_direction_with_hysteresis(level_price, todays_closes)
        level_type = "SUPPORT" if direction == "BULLISH" else "RESISTANCE"

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Market Zones tab वर 1-मिनिट Instant Trader
        # सारखाच संपूर्ण Signal Log, SRv2 साठीही) — याआधी इथे फक्त प्रत्यक्ष trade झाला तरच
        # save_signal_log() व्हायचं; touch न झालेले किंवा कुठल्याही gate ने अडवलेले candidates
        # कधीच साठवले जात नव्हते, त्यामुळे entry/exit cross-verify करायला काहीच data नव्हतं. आता
        # प्रत्येक तपासलेला candidate (NO_HIT सकट) इथे लगेच साठवला जातो.
        log_entry = {
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": level_type,
            "level_price": level_price, "hit_type": (touch_type or "TOUCH") if touched else "NO_HIT",
            "direction": direction if touched else "NONE", "ltp_at_signal": underlying_price,
            "trade_status": None,
            "reason": "" if touched else (
                f"level ला स्पर्श (touch) आढळला नाही ({timeframe_suffix})" if recent_1m_candles
                else f"आजचे 1-मिनिट candles उपलब्ध नाहीत, touch तपासता आला नाही ({timeframe_suffix})"
            ),
        }

        if not touched:
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — इतर सर्व gates च्याही आधी (उगाच RSI/PCR API कॉल होऊ नयेत) — फक्त नवीन
        # trades थांबतात, आधीच उघडलेले चालूच राहतात.
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

        if (now.hour, now.minute) >= (NO_NEW_ENTRY_AFTER_HOUR, NO_NEW_ENTRY_AFTER_MINUTE):
            log_entry["trade_status"] = "SKIPPED_TOO_LATE_FOR_NEW_ENTRY"
            log_entry["reason"] = f"{NO_NEW_ENTRY_AFTER_HOUR}:{NO_NEW_ENTRY_AFTER_MINUTE:02d} नंतर नवीन entry नाही"
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
            rsi_ok, rsi_value = check_instant_rsi_filter(candles_df, direction, rsi_support_max, rsi_resistance_min)
            if not rsi_ok:
                log_entry["trade_status"] = "SKIPPED_RSI_FILTER"
                log_entry["reason"] = f"RSI {rsi_value} ({timeframe_suffix}) दिशेशी जुळत नाही (Support<{rsi_support_max} / Resistance>{rsi_resistance_min} हवं होतं)"
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
        hit_count_so_far, _, last_trade_time = cloud_db.get_zone_hits_today(symbol, level_price, trade_date, role=level_type)
        if hit_count_so_far >= max_hits_per_zone:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = f"आजच्या या zone साठी (याच role) कमाल {max_hits_per_zone} वेळा मर्यादा आधीच गाठलेली ({timeframe_suffix})"
            cloud_db.save_signal_log(log_entry)
            continue
        # 🎓 "Fix bug if any ... all exit condition" audit — Dashboard चा "SL/TSL Cooldown (त्याच level वर)"
        # सेटिंग तिन्ही strategies साठी दाखवला जातो, पण इथे तो कधीच वाचला जात नव्हता (जुना
        # COOLDOWN_MINUTES state कधीच लिहिला जात नाही, म्हणून निष्क्रिय) — 15M वर SL/TSL लागल्यावर लगेच
        # त्याच level वर पुन्हा entry शक्य होती. आता dynamic_sr_instant_trader.py प्रमाणेच exit-वेळेवर
        # आधारित, त्याच exact level वर (0 = बंद). TARGET/इतर profitable exits ला लागू नाही.
        sl_tsl_cooldown_minutes = settings.get("sl_tsl_cooldown_minutes", 15)
        if sl_tsl_cooldown_minutes > 0:
            last_sl_tsl_exit = get_last_sl_tsl_exit_time(symbol, level_price, "srv2_momentum_reversal", trade_date)
            if last_sl_tsl_exit is not None:
                elapsed_since_sl = (now - last_sl_tsl_exit).total_seconds() / 60
                if elapsed_since_sl < sl_tsl_cooldown_minutes:
                    log_entry["trade_status"] = "SKIPPED_SL_TSL_COOLDOWN"
                    log_entry["reason"] = f"याच level वर मागचा SL/TSL फक्त {elapsed_since_sl:.1f} मिनिटांपूर्वी लागला (किमान {sl_tsl_cooldown_minutes} हवीत, {timeframe_suffix})"
                    cloud_db.save_signal_log(log_entry)
                    continue
        # 🎓 "Minimum Level-Hold Duration" (5M सारखाच, 1-मिनिट candles वरून, बफर शिवाय) — level ला touch होऊन
        # किमान entry_min_hold_minutes सलग टिकलेला असेल तरच entry; `first_trade_only` असल्यास फक्त त्या level
        # (+role) वर आज पहिला खरा trade होईपर्यंत (last_trade_time — नाकारलेला touch मोजला जात नाही).
        if entry_min_hold_gate_enabled and not (entry_min_hold_first_trade_only and last_trade_time is not None):
            held_minutes = count_consecutive_touch_minutes(level_price, todays_1m_candles, tolerance_pct=TOUCH_TOLERANCE_PCT)
            if held_minutes < entry_min_hold_minutes:
                log_entry["trade_status"] = "SKIPPED_MIN_HOLD_DURATION"
                log_entry["reason"] = f"Level फक्त {held_minutes} मिनिटं टिकून आहे (किमान {entry_min_hold_minutes} हवीत) — ताजा/अस्थिर touch ({timeframe_suffix})"
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
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("entry साठी touch-detection च्याच जुन्या किंमतीवर
        # अवलंबून आहे, ताजी किंमत परत घ्या") — dynamic_sr_instant_trader.py/classic_sr_reversal_trader.py
        # प्रमाणेच — आतापर्यंत इथे touch-detection वेळचा (काही मिनिटं जुना असू शकणारा candle-close)
        # underlying_price हाच ATM strike + entry_spot_price (SL/TSL च्या Spot% आधारासाठी) दोन्हींसाठी
        # वापरला जायचा. आता याच क्षणी ताज्या मागवलेल्या option chain मधली सद्य spot किंमत वापरली जाते —
        # ATM strike आणि SL/TSL चा आधार दोन्ही प्रत्यक्ष entry-क्षणाच्या जवळ.
        underlying_price = raw_chain[0].get("underlying_spot_price") or underlying_price
        log_entry["ltp_at_signal"] = underlying_price
        strike_step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
        atm_strike = round(underlying_price / strike_step) * strike_step

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Naked Option Buy आणि Credit Spread दोन्ही independently
        # optional असायला पाहिजेत — कमी कॅपिटल असलेला user फक्त naked करणं पसंत करतो") — आधी credit
        # spread नेहमीच (toggle शिवाय) चालायचा, फक्त naked ऐच्छिक होता (naked_enabled). आता दोन्ही
        # स्वतंत्रपणे on/off करता येतात — हा नवीन credit_spread_enabled (डीफॉल्ट True, backward-compatible).
        credit_spread_enabled = settings.get("credit_spread_enabled", True)
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (PAPER/LIVE टॉगल + per-strategy Broker Selection) —
        # dynamic_sr_instant_trader.py प्रमाणेच — settings मधल्याच trading_mode/broker_account_ids
        # वरून, "कुठलेही broker_accounts नोंदवलेले असतील तर सर्व सक्रिय accounts" ऐवजी.
        # credit_spread_enabled=False असतानाही naked trade ला हेच लागतात, म्हणून आधीच वाचलेले.
        trading_mode = settings.get("trading_mode", "PAPER")
        broker_account_ids = settings.get("broker_account_ids") or []

        # 🎓 "एका वेळी एकच position (5M किंवा 15M)" — 15M ला प्राधान्य: उघडे 5M trades बंद करणे entry order च्या
        # अगदी आधी (option chain मिळाल्यावर आणि strike-निवड यशस्वी झाल्यावरच) — आधी हे chain मिळण्याआधीच व्हायचं,
        # त्यामुळे chain/strike अयशस्वी झाल्यास 5M trade बंद झाला पण 15M ने काहीच घेतलं नाही. एका cycle मध्ये
        # फक्त एकदाच (spread आणि naked दोन्हीसाठी सामायिक), बंद न झाल्यास 15M entry (दोन्ही) थांबतात.
        yield_state = {}

        def _ensure_5m_yielded():
            if "ok" not in yield_state:
                yield_ok, yielded_ids = _yield_open_5m_positions(access_token, symbol, trading_mode)
                yield_state["ok"] = yield_ok
                if yield_ok and yielded_ids:
                    send_telegram_message(
                        f"🔀 <b>{symbol}: 15M ने पदभार घेतला</b>\n15M entry आधी उघडे {len(yielded_ids)} 5M trade(s) बंद केले (एका वेळी एकच position)."
                    )
            return yield_state["ok"]

        spread_result = None
        defer_spread_disabled_log = False
        trade_status = ""
        if credit_spread_enabled:
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

            if not _ensure_5m_yielded():
                trade_status = "SKIPPED_5M_POSITION_NOT_CLOSED"
            elif broker_account_ids:
                from trading_engine import execute_trade_on_all_accounts
                results, factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=spread_result, base_lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_premium,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="srv2_momentum_reversal",
                    entry_level_price=level_price, entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    account_ids=broker_account_ids, direction=direction,
                )
                trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
                if factory_errors:
                    trade_status += " | वगळलेले: " + "; ".join(factory_errors)
            else:
                trade_ok, trade_response = open_multi_leg_trade(
                    access_token, symbol, spread_result, lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_premium,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="srv2_momentum_reversal",
                    entry_level_price=level_price, entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    direction=direction,
                )
                # 🎓 code-review द्वारे सापडवलेली bug (बघा trading_engine.format_trade_result() ची
                # टिप्पणी) — open_multi_leg_trade() चं दुसरं मूल्य dict असतं, raw dict signal_log.
                # trade_status (TEXT column) मध्ये साठवायचा प्रयत्न केला की DB insert चुपचाप अपयशी
                # ठरायचा, आणि नेमकी entry-क्षणाचीच signal_log रांग हरवायची.
                trade_status = format_trade_result(trade_ok, trade_response)

            rsi_reason = f"RSI {rsi_value} ({timeframe_suffix}), फिल्टर पास" if entry_rsi_gate_enabled else f"RSI Gate बंद ({timeframe_suffix}, तपासलं नाही)"
            cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
            log_entry["trade_status"] = trade_status
            log_entry["reason"] = rsi_reason
            cloud_db.save_signal_log(log_entry)
        else:
            cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
            log_entry["trade_status"] = "SKIPPED_CREDIT_SPREAD_DISABLED"
            log_entry["reason"] = "credit_spread_enabled=False (Bot Dynamic SR Algo सेटिंग्जमध्ये बंद)"
            # 🎓 entry-gate review मध्ये सापडलेली bug — naked-only मोडमध्ये (credit_spread_enabled=False)
            # naked trade चा निकाल कधीच signal_log मध्ये जायचा नाही, फक्त हा SKIPPED_* 'no-action' शिक्का
            # जायचा — त्यामुळे 30-मिनिट cooldown / "पहिला trade" गेट / max-hits ला खरा trade दिसायचाच
            # नाही. naked चालणार असेल तर ही नोंद खाली naked निकालासह (खरा trade_status घेऊन) साठवली जाते.
            defer_spread_disabled_log = bool(settings.get("naked_enabled", True))
            if not defer_spread_disabled_log:
                cloud_db.save_signal_log(log_entry)
            print(f"ℹ️ Credit Spread trade बंद आहे (credit_spread_enabled=False, settings — symbol={symbol}, strategy=15m_dynamic_sr)")

        naked_status = ""
        naked_result = None
        # 🎓 वापरकर्त्याने विचारलेला प्रश्न ("naked trade execute झाला नाही") सोडवण्यासाठी जोडलेली
        # सुधारणा — आधी हे फक्त print() (फक्त GitHub Actions/VPS logs मध्ये दिसायचं) होतं, आता
        # signal_log मध्येही नोंदवलं जातं — त्यामुळे Dashboard वरच्या Market Zones → Signal Log
        # मध्ये (कुठल्याही log-access शिवाय) नेमकं कारण दिसेल.
        naked_diag_entry = dict(log_entry)
        if settings.get("naked_enabled", True):
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Credit Spread वि. Naked Option — स्वतंत्र
            # Strike Offset) — बघा dynamic_sr_instant_trader.py ची तीच टिप्पणी.
            naked_itm_depth_points = settings.get("naked_itm_depth_points", settings["itm_depth_points"])
            naked_result = select_naked_option_itm(
                raw_chain, direction, atm_strike, itm_depth_points=naked_itm_depth_points, step=strike_step,
                hedge_enabled=settings.get("naked_hedge_enabled", False),
                hedge_width_points=settings.get("naked_hedge_width_points", 150),
            )
            if naked_result is None:
                naked_diag_entry["trade_status"] = "SKIPPED_NAKED_STRIKE_NOT_FOUND"
                naked_diag_entry["reason"] = (
                    f"Naked trade साठी आवश्यक ITM strike (atm={atm_strike}, डेप्थ "
                    f"{naked_itm_depth_points}) raw_chain मध्ये सापडला नाही"
                )
                cloud_db.save_signal_log(naked_diag_entry)
                print(f"⚠️ {naked_diag_entry['reason']} — symbol={symbol}, direction={direction}")
        else:
            naked_diag_entry["trade_status"] = "SKIPPED_NAKED_DISABLED"
            naked_diag_entry["reason"] = "naked_enabled=False (Bot Dynamic SR Algo सेटिंग्जमध्ये बंद)"
            cloud_db.save_signal_log(naked_diag_entry)
            print(f"ℹ️ Naked trade बंद आहे (naked_enabled=False, settings — symbol={symbol}, strategy=15m_dynamic_sr)")
        if naked_result is not None:
            if not _ensure_5m_yielded():
                naked_status = "SKIPPED_5M_POSITION_NOT_CLOSED"
            elif broker_account_ids:
                from trading_engine import execute_trade_on_all_accounts
                naked_results, naked_factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=naked_result, base_lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="srv2_momentum_reversal",
                    entry_level_price=level_price, entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    account_ids=broker_account_ids, direction=direction,
                )
                naked_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in naked_results) or "कुठलाही account उपलब्ध नाही"
            else:
                naked_ok, naked_response = open_multi_leg_trade(
                    access_token, symbol, naked_result, lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="srv2_momentum_reversal",
                    entry_level_price=level_price, entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    direction=direction,
                )
                naked_status = format_trade_result(naked_ok, naked_response)

        strategy_label = "Bull Put Spread (Support Bounce)" if direction == "BULLISH" else "Bear Call Spread (Resistance Bounce)"
        # 🎓 naked-only मोड (बघा वरची टिप्पणी) — naked trade ने प्रत्यक्ष order प्रयत्न केला असेल तर तोच
        # निकाल (उदा. "OPENED") खरा trade_status म्हणून signal_log मध्ये; नाहीतर (strike सापडला नाही / naked
        # बंद) पूर्वीचाच SKIPPED_CREDIT_SPREAD_DISABLED शिक्का, पण naked निदान-नोंदीनंतर.
        if defer_spread_disabled_log:
            if naked_result is not None and naked_status:
                log_entry["trade_status"] = naked_status
                log_entry["reason"] = "credit_spread_enabled=False — फक्त Naked Option trade (निकाल trade_status मध्ये)"
            cloud_db.save_signal_log(log_entry)

        naked_line = f"Naked Option: {naked_result.get('strategy', direction)} — {naked_status}\n" if naked_result is not None else ""
        credit_spread_line = f"Credit Spread: {strategy_label} — {trade_status}\n" if spread_result is not None else ""
        rsi_display = f"RSI {rsi_value} (फिल्टर पास)" if entry_rsi_gate_enabled else "RSI Gate बंद (तपासलं नाही)"
        message = (
            f"🎯 <b>{symbol} SRv2 Momentum-Reversal ({timeframe_suffix})</b> (आजचा {hit_count_so_far + 1}/2 वा hit)\n"
            f"{level_type} {level_price:.2f} — {rsi_display}.\n"
            + credit_spread_line
            + naked_line
            + f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        combined_status = trade_status or naked_status or "कुठलाही trade प्रकार सक्रिय नाही (credit_spread_enabled व naked_enabled दोन्ही बंद)"
        return f"{symbol}: 🎯 {level_type} {level_price:.2f} ({timeframe_suffix}, {rsi_display}) -> {strategy_label} PAPER trade {combined_status}"

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
