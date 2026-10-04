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
import os
import time

import pandas as pd

import cloud_db
import resolve_mcx_futures_instruments as mcx_resolver
from config import get_ist_now
import database
from database import (init_sqlite_db, has_open_trade_from_source, run_auto_backup_if_due, count_entries_at_level_today,
                      get_closed_trades_on_date, get_open_trade_contracts)
from dynamic_sr_instant_trader import (
    check_instant_rsi_filter, check_breakout_price_consolidation, check_breakout_candle_close,
    get_supertrend_direction, _completed_bars_only, count_consecutive_touch_minutes,
)
from notifications import send_telegram_message, write_heartbeat, notify_error, notify_exit
from process_lock import ProcessLock, ProcessLockHeld
from signals import resample_to_1h, resample_to_4h
from trading_engine import open_multi_leg_trade, manage_open_trades, format_trade_result
from upstox_api import fetch_mcx_candles, fetch_broker_positions
import srv3_instant_shadow as SRV3
import mcx_filters as MF
from sr_levels_v3 import SRConfig

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
# 🎓 bug-review -- MCX बॉटला "नवीन entry बंद" वेळ नव्हती (NSE चे 3 bots EOD च्या ३० मिनिटं आधी, 14:45 ला बंद करतात). EOD square-off (वर)
# 23:15 ला असल्याने त्यानंतरच्या touch वर उघडलेली position पुढच्याच exit-cycle ला (~५ सेकंदांत) EOD_SQUAREOFF ने लगेच बंद व्हायची --
# फुकट brokerage/slippage (LIVE मध्ये खरे orders). वापरकर्त्याने ठरवलेलं: EOD च्या ३० मिनिटं आधी, 22:45 पासून नवीन entry नाही.
MCX_NO_NEW_ENTRY_AFTER = (22, 45)

# 🎓 वापरकर्त्याचा निर्णय ("MCX bot मध्ये सुद्धा SR V3 levels — Setting ने निवड") — `level_engine` (MCX पान, symbol-निहाय):
#   "DYNAMIC"     — जुनेच 30M/60M Dynamic S/R levels (डीफॉल्ट, वर्तन अपरिवर्तित)
#   "SRV3_SHADOW" — मूळ bot जुन्याच levels वर; शेजारी SR V3 levels वर तेच नियम, निव्वळ PAPER, वेगळा source (तुलनेसाठी)
#   "SRV3"        — मूळ bot च SR V3 levels वर (settings चा trading_mode जसा आहे तसा — PAPER/LIVE तुमच्या निवडीने)
# SR V3 (MCX): 15M + 30M + 1H pivots, PDH/PDL/PDC/PWH/PWL (सत्र-अंत 23:30), gaps, फक्त grade A/B, किंमतीपासून ≤ 3%, फक्त पूर्ण
# झालेले candles; दर 5 मिनिटांनी market_zones मध्ये `SRV3_SUPPORT`/`SRV3_RESISTANCE` (शेवटी "_30M"/"_60M" नाही ⇒ जुन्या
# Dynamic candidates मध्ये कधीच मिसळत नाहीत). MCX चा historical backtest शक्य नाही (ऐतिहासिक MCX डेटा नाही) — म्हणून
# आधी SRV3_SHADOW ने forward PAPER तुलना करण्याची शिफारस.
LEVEL_ENGINES = ("DYNAMIC", "SRV3_SHADOW", "SRV3")
SRV3_SHADOW_SOURCE = "mcx_futures_srv3_shadow"
MCX_TRADE_SOURCES = (STRATEGY_KEY, SRV3_SHADOW_SOURCE)   # trading_engine.MCX_SOURCES सारखेच
SRV3_TIMEFRAME_LABEL = "SRV3"
SRV3_CFG = SRConfig(session_end="23:30")
SRV3_REFRESH_STATE = os.path.join("data", "mcx_srv3_refresh.json")

# 🎓 Contract roll (वापरकर्त्याचा निर्णय, सर्व commodities) — नियम resolver मध्ये: front-month चे उरलेले **ट्रेडिंग** दिवस ≤
# roll_trading_days_before_expiry (डीफॉल्ट 6, आणि staggered delivery period + 1 पेक्षा कधीच कमी नाही — बघा resolve_mcx_futures_instruments.
# effective_roll_days) झाले की पुढचा contract. इथे फक्त: contract बदलल्याचं ओळखून Telegram सूचना, आणि त्या symbol चे zones नव्या contract
# च्या candles वरून लगेच पुन्हा मोजणे (जुन्या contract चे levels calendar-spread मुळे चुकीच्या भावावर असतात) — zones नव्या contract चे
# होईपर्यंत त्या symbol वर नवीन entry नाही. उघड्या positions चे exits (आणि trailing चा reference भाव) त्यांच्या स्वतःच्या (trade मध्ये
# साठवलेल्या) instrument वरच.
CONTRACT_STATE = os.path.join("data", "mcx_contract_state.json")


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


def fetch_mcx_trend_filter_directions(access_token, instrument_key, now, st1h_period=10, st1h_multiplier=3.0,
                                      st4h_period=10, st4h_multiplier=3.0):
    """🎓 "add Supertrend entry gate for MCX futures" -- (1H दिशा, 4H दिशा), दोन्ही शेवटच्या **पूर्ण झालेल्या** candle ची. दोन्ही 30-मिनिट
    candles (MCX साठी Upstox ने verified) वरून resample (1H, आणि ९:००-आधारित 4H). डेटा मिळाला नाही/चूक झाली तर त्या टाईमफ्रेमसाठी None
    (gate fail-open, trade अडवत नाही)."""
    dir_1h = dir_4h = None
    try:
        df30 = fetch_mcx_candles(access_token, instrument_key, interval="30minute", lookback_days=20)
    except Exception:
        return dir_1h, dir_4h
    if df30 is None or df30.empty:
        return dir_1h, dir_4h
    df30 = df30.copy()
    for col in ("volume", "oi"):
        if col not in df30.columns:
            df30[col] = 0
    try:
        dir_1h = get_supertrend_direction(_completed_bars_only(resample_to_1h(df30), 60, now), st1h_period, st1h_multiplier)
    except Exception:
        dir_1h = None
    try:
        dir_4h = get_supertrend_direction(_completed_bars_only(resample_to_4h(df30), 240, now), st4h_period, st4h_multiplier)
    except Exception:
        dir_4h = None
    return dir_1h, dir_4h


def check_contract_roll(access_token, symbol, resolved, notify=None, refresh=None, state_path=None):
    """contract बदलला का ते तपासणे (state: data/mcx_contract_state.json). बदलला ⇒ Telegram सूचना (एकदाच) आणि zones refresh.
    रिटर्न (entries_ok, संदेश किंवा None) — zones नव्या contract चे होईपर्यंत entries_ok=False."""
    notify = notify or send_telegram_message
    state_path = state_path or CONTRACT_STATE
    if refresh is None:
        import refresh_market_zones_mcx
        def refresh(token, sym):                         # नवा contract ⇒ जुन्या contract चे levels विसरायचे (level memory reset)
            return refresh_market_zones_mcx.refresh_symbol(token, sym, reset=True)
    state = SRV3._load_state(state_path)
    rec = dict(state.get(symbol) or {})
    cur = resolved.get("trading_symbol") or resolved.get("instrument_key")
    prev = rec.get("contract")
    msg = None
    if prev != cur:
        if prev is not None or resolved.get("rolled"):
            old_name = prev or resolved.get("front_trading_symbol")
            msg = (f"🔄 <b>{symbol} MCX contract roll</b>: {old_name} → {cur} (expiry {resolved.get('expiry')}). "
                   f"नियम: जुन्या contract चे उरलेले ट्रेडिंग दिवस ≤ {resolved.get('roll_trading_days_before_expiry')} "
                   f"(MCX staggered delivery period: शेवटचे {resolved.get('staggered_delivery_trading_days', 0)} ट्रेडिंग दिवस). "
                   "नव्या contract चे levels पुन्हा मोजले जात आहेत; ते तयार होईपर्यंत नवीन entry नाही.")
            try:
                notify(msg)
            except Exception:
                pass
        rec["contract"] = cur
    if rec.get("levels_contract") != cur:
        if prev is None and not resolved.get("rolled"):
            rec["levels_contract"] = cur          # पहिलीच नोंद आणि roll नाही — रात्रीचा refresh याच resolver ने ⇒ zones याच contract चे
        else:
            try:
                ok, refresh_msg = refresh(access_token, symbol)
            except Exception as exc:
                ok, refresh_msg = False, str(exc)
            if not ok:
                state[symbol] = rec
                SRV3._save_state(state, state_path)
                return False, f"{symbol}: contract roll ({cur}) — नव्या contract चे zones अजून तयार नाहीत ({refresh_msg}); नवीन entry नाही"
            rec["levels_contract"] = cur
            msg = (msg + " | " if msg else "") + f"zones: {refresh_msg}"
    state[symbol] = rec
    SRV3._save_state(state, state_path)
    if resolved.get("roll_pending"):
        msg = (msg + " | " if msg else "") + (f"⚠️ {symbol}: {resolved.get('front_trading_symbol')} ची expiry जवळ आहे पण पुढचा contract Upstox "
                                              "यादीत मिळाला नाही — जवळचाच वापरला")
    return True, msg


def _drop_today_and_later(daily, now):
    """Daily candles मधून आजचा (अपूर्ण) आणि पुढचे दिवस वगळणे — PDH/PDL फक्त पूर्ण झालेल्या दिवसांवरून."""
    if daily is None or daily.empty:
        return daily
    return daily[(SRV3._naive(daily["timestamp"]).dt.normalize() < pd.Timestamp(now).normalize()).to_numpy()]


def refresh_mcx_srv3_levels_if_due(access_token, symbol, instrument_key, now, fetch=fetch_mcx_candles, state_path=SRV3_REFRESH_STATE):
    """शेवटच्या यशस्वी गणनेला ≥ 5 मिनिटं झाली असतील तर MCX साठी SR V3 पुन्हा मोजून merge. रिटर्न: संदेश किंवा None (गरज नव्हती)."""
    state = SRV3._load_state(state_path)
    last = state.get(symbol)
    if last is not None and (pd.Timestamp(now) - pd.Timestamp(last)).total_seconds() < SRV3.REFRESH_MINUTES * 60:
        return None
    df15 = fetch(access_token, instrument_key, interval="15minute", lookback_days=10)
    df30 = fetch(access_token, instrument_key, interval="30minute", lookback_days=20)
    daily = fetch(access_token, instrument_key, interval="day", lookback_days=60)
    if df30 is None or df30.empty:
        return f"{symbol}: SR V3 — 30-मिनिट डेटा मिळाला नाही (जुने SR V3 levels कायम)"
    df30 = _completed_bars_only(df30, 30, now)
    df15 = _completed_bars_only(df15, 15, now) if df15 is not None and not df15.empty else df15
    df60 = _completed_bars_only(resample_to_1h(df30), 60, now) if len(df30) else None
    price = float(df30["close"].iloc[-1])
    levels = SRV3.v3_levels_from_frames({"15minute": df15, "30minute": df30, "1hour": df60}, _drop_today_and_later(daily, now), price, SRV3_CFG)
    ok = cloud_db.merge_dynamic_sr_zones(symbol, levels, "", formed_date=now, type_prefix=SRV3.ZONE_PREFIX)
    if ok:
        state[symbol] = pd.Timestamp(now).isoformat()
        SRV3._save_state(state, state_path)
    n = len(levels["support"]) + len(levels["resistance"])
    return f"{symbol}: SR V3 levels {'merge झाले' if ok else 'नाहीत / merge अयशस्वी — जुने कायम'} ({n} A/B)"


def _collect_srv3_candidates(access_token, instrument_key, all_zones, active_suffixes, now):
    """SR V3 levels (ACTIVE `SRV3_*`) — touch/RSI साठी candles जुन्या मार्गाप्रमाणेच निवडलेल्या पहिल्या TF चे (30M डीफॉल्ट; 60M निवडल्यास 1H).
    रिटर्न `_collect_touch_candidates` सारखाच फॉरमॅट, timeframe label "SRV3"."""
    rows = all_zones[(all_zones["zone_type"].isin(SRV3.ZONE_TYPES)) & (all_zones["status"] == "ACTIVE")]
    if rows.empty:
        return []
    df_30m = fetch_mcx_candles(access_token, instrument_key, interval="30minute", lookback_days=5)
    candles_df = resample_to_1h(df_30m) if active_suffixes and active_suffixes[0] == "60M" and df_30m is not None and not df_30m.empty else df_30m
    if candles_df is None or candles_df.empty or len(candles_df) < 12:
        return []
    candles_df = candles_df.copy()
    candles_df["_date"] = candles_df["timestamp"].dt.date
    todays = candles_df[candles_df["_date"] == now.date()]
    if todays.empty:
        return []
    current_price, closes = todays["close"].iloc[-1], todays["close"].tolist()
    return [(float(lv), SRV3_TIMEFRAME_LABEL, candles_df, current_price, closes) for lv in sorted(set(rows["zone_low"]))]


def fetch_mcx_todays_1m_candles(access_token, instrument_key, now):
    """🎓 "level hold Minimum period" गेटसाठी -- आजचे 1-मिनिट candles ([{"low","high"}, ...], जुनं ते नवीन) किंवा None (डेटा मिळाला नाही /
    त्रुटी -- गेट fail-open, trade अडवत नाही). MCX बॉट बाकी सगळीकडे 30-मिनिट candles वापरतो; हा 1-मिनिटाचा fetch फक्त गेट तपासायची वेळ
    आली (बाकी सर्व गेट्स पार) तेव्हाच, प्रति-symbol प्रति-cycle एकदाच केला जातो."""
    try:
        df = fetch_mcx_candles(access_token, instrument_key, interval="1minute", lookback_days=1)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    todays = df[df["timestamp"].dt.date == now.date()]
    if todays.empty:
        return None
    return todays[["low", "high"]].to_dict("records")


def process_symbol(access_token, symbol):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Crude oil hit log not working") — _process_symbol_core() चा wrapper: प्रत्येक
    cycle ला निकाल-स्थितीसह "अखेरची तपासणी" (वेळ/भाव/जवळचा level) cloud_db.save_mcx_last_check() मध्ये साठवतो, जेणेकरून
    Hit Log वर (NO_HIT dedup मुळे शांत काळातही) trader जिवंत असल्याचा पुरावा दिसेल. ही नोंद अयशस्वी झाली तरी
    trading वर परिणाम नाही (सर्व अपवाद गिळले जातात)."""
    check_info = {}
    engine = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol).get("level_engine", "DYNAMIC")
    result = _process_symbol_core(access_token, symbol, check_info, level_source="SRV3" if engine == "SRV3" else "DYNAMIC")
    if engine == "SRV3_SHADOW":
        # 🎓 SR V3 PAPER shadow — मूळ cycle नंतर, स्वतंत्र try/except: इथली कुठलीही चूक मूळ bot ला अडवत नाही.
        try:
            result += " | 🧪 " + _process_symbol_core(access_token, symbol, {}, level_source="SRV3", shadow=True)
        except Exception as e:
            result += f" | 🧪 SR V3 shadow त्रुटी (मूळ bot वर परिणाम नाही) — {e}"
    try:
        cloud_db.save_mcx_last_check(
            symbol, get_ist_now(), result, price=check_info.get("price"), nearest_level=check_info.get("nearest_level"),
            nearest_level_type=check_info.get("nearest_level_type"), nearest_timeframe=check_info.get("nearest_timeframe"),
        )
    except Exception:
        pass
    return result


effective_supertrend_mode = MF.effective_supertrend_mode


def fetch_completed_30m_bars(access_token, instrument_key, now, lookback_days=15):
    """cascade filter साठी -- `now` पर्यंत **पूर्ण** झालेले 30M bars (timestamp + 30 मि ≤ now, IST tz-शिवाय). चूक/डेटा नाही ⇒ None (fail-open)."""
    try:
        df = fetch_mcx_candles(access_token, instrument_key, interval="30minute", lookback_days=lookback_days)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = df.copy()
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    df["timestamp"] = ts
    now_ts = pd.Timestamp(now).tz_localize(None) if pd.Timestamp(now).tzinfo else pd.Timestamp(now)
    return df[df["timestamp"] + pd.Timedelta(minutes=30) <= now_ts].reset_index(drop=True)


def _process_symbol_core(access_token, symbol, check_info, level_source="DYNAMIC", shadow=False):
    """एका MCX commodity साठी — 30M/60M levels (settings-चालित), RSI dual-threshold gate,
    Multi-Hit, आणि आढळल्यास एकाच futures leg चं PAPER/LIVE trade (settings-चालित lots/SL/Target).
    `level_source="SRV3"` ⇒ levels SR V3 (बघा LEVEL_ENGINES). `shadow=True` ⇒ निव्वळ PAPER, source SRV3_SHADOW_SOURCE, signal_log मध्ये
    नोंद नाही (मूळ bot च्या hit-count/Hit Log मध्ये मिसळू नये — म्हणून "एका level वर कमाल N" live_trades वरून), Breakout Entry नाही
    (तो signal_log च्या उलट-role hits वर अवलंबून)."""
    source = SRV3_SHADOW_SOURCE if shadow else STRATEGY_KEY

    def _log(entry):
        if not shadow:
            cloud_db.save_signal_log(entry)

    settings = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol)
    if not settings.get("symbol_enabled", False):
        return f"{symbol}: बंद आहे (symbol_enabled=False, MCX Futures Trader सेटिंग्जमधून सक्रिय करा)"

    ok, resolved = mcx_resolver.resolve_symbol(access_token, symbol)
    if not ok:
        return f"{symbol}: सध्याचा (current/continuous) Futures contract सापडला नाही ({resolved})"
    instrument_key = resolved["instrument_key"]
    lot_size = resolved["lot_size"]
    roll_ok, roll_msg = check_contract_roll(access_token, symbol, resolved)
    if roll_msg:
        print(roll_msg)
    if not roll_ok:
        return roll_msg

    lots = settings["lots"]
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Max trade on same level yachi setting sidhha द्या, default
    # 2") — बघा dynamic_sr_instant_trader.py मधली टिप्पणी.
    max_hits_per_zone = int(settings.get("max_hits_per_zone", 2))
    bullish_entry_enabled = settings.get("bullish_entry_enabled", True)
    bearish_entry_enabled = settings.get("bearish_entry_enabled", True)
    entry_rsi_gate_enabled = settings.get("entry_rsi_gate_enabled", True)
    rsi_support_max = settings.get("rsi_support_max", 40)
    rsi_resistance_min = settings.get("rsi_resistance_min", 60)
    entry_breakout_gate_enabled = settings.get("entry_breakout_gate_enabled", False) and not shadow
    breakout_lookback_candles = settings.get("breakout_lookback_candles", 12)
    breakout_tolerance_pct = settings.get("breakout_tolerance_pct", 0.30)
    supertrend_1h_period = settings.get("supertrend_1h_period", 10)
    supertrend_1h_multiplier = settings.get("supertrend_1h_multiplier", 3.0)
    supertrend_4h_period = settings.get("supertrend_4h_period", 10)
    supertrend_4h_multiplier = settings.get("supertrend_4h_multiplier", 3.0)
    supertrend_directions_cache = []  # प्रति-symbol, प्रति-cycle एकदाच (सर्व levels साठी सारखं) -- lazily
    supertrend_filter_mode = effective_supertrend_mode(settings)
    sl_cooldown_minutes = int(settings.get("sl_cooldown_minutes", 60) or 0)
    sl_level_direction_block_enabled = settings.get("sl_level_direction_block_enabled", True)
    cascade_filter_enabled = settings.get("cascade_filter_enabled", False)
    closed_today_cache = []           # आजचे बंद trades (cooldown/level-direction) -- lazily, प्रति-cycle एकदाच
    completed_30m_cache = []          # cascade साठी entry आधीचे पूर्ण 30M bars -- lazily
    entry_min_hold_gate_enabled = settings.get("entry_min_hold_gate_enabled", True)
    entry_min_hold_minutes = settings.get("entry_min_hold_minutes", 5)
    entry_min_hold_first_trade_only = settings.get("entry_min_hold_first_trade_only", True)
    todays_1m_cache = []  # प्रति-symbol, प्रति-cycle एकदाच -- lazily
    timeframe_choice = settings.get("timeframe_choice", "30M")
    active_suffixes = TIMEFRAME_SUFFIXES if timeframe_choice == "ALL" else [timeframe_choice]

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones_mcx.py चालवा)"

    now = get_ist_now()
    trade_date = now.strftime("%Y-%m-%d")
    if level_source == "SRV3":
        refresh_msg = refresh_mcx_srv3_levels_if_due(access_token, symbol, instrument_key, now)
        if refresh_msg:
            print(refresh_msg)
            all_zones = cloud_db.get_market_zones(symbol)
            if all_zones is None or all_zones.empty:
                return f"{symbol}: SR V3 — zones वाचता आले नाहीत"
        candidates = _collect_srv3_candidates(access_token, instrument_key, all_zones, active_suffixes, now)
        if not candidates:
            return f"{symbol}: कुठलेही ACTIVE SR V3 (A/B) levels सापडले नाहीत, किंवा आजचे candles अजून तयार नाहीत"
    else:
        candidates = _collect_touch_candidates(access_token, instrument_key, all_zones, active_suffixes, now)
    if not candidates:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels ({'/'.join(active_suffixes)}) सापडले नाहीत, किंवा आजचे candles अजून तयार नाहीत"

    # heartbeat साठी — सद्य भाव आणि त्याच्या सर्वात जवळचा level (सर्व candidates चा भाव सारखाच असतो)
    _nearest = min(candidates, key=lambda c: abs(c[3] - c[0]))
    check_info.update({
        "price": _nearest[3], "nearest_level": _nearest[0], "nearest_timeframe": _nearest[1],
        "nearest_level_type": "RESISTANCE" if _nearest[0] >= _nearest[3] else "SUPPORT",
    })

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
        if shadow:
            hit_count_so_far = count_entries_at_level_today(symbol, level_price, source, trade_date)
            last_trade_time = None if hit_count_so_far == 0 else now
        else:
            hit_count_so_far, _, last_trade_time = cloud_db.get_zone_hits_today(symbol, level_price, trade_date, role=role)
        is_breakout_trade = False
        if entry_breakout_gate_enabled:
            opposite_role = "RESISTANCE" if role == "SUPPORT" else "SUPPORT"
            opposite_hit_count, _, _ = cloud_db.get_zone_hits_today(symbol, level_price, trade_date, role=opposite_role)
            if opposite_hit_count >= 2:
                candles_for_breakout = [{"close": c} for c in todays_closes]
                # 🎓 code-review द्वारे सापडवलेली bug — dynamic_sr_instant_trader.py मध्ये NIFTY-विशिष्ट
                # "5 minute candle close Breakout beyond 0.010%" सुधारणेसाठी check_breakout_candle_close()
                # ला नवीन buffer_pct पॅरामीटर (डीफॉल्ट 0.010%) जोडला गेला — तो इथे (MCX, वेगळ्याच,
                # कधीच न बदललेल्या मागणीसाठी) कधीच मागितला/तपासला गेला नव्हता, तरीही डीफॉल्ट मूल्यामुळे
                # शांतपणे लागू झाला असता (आधीचा strict >/< नाही). इथे buffer_pct=0.0 स्पष्टपणे देऊन
                # MCX चं established (या सुधारणेआधीचं) वर्तन जसंच्या तसं ठेवलं.
                if (check_breakout_price_consolidation(level_price, candles_for_breakout, breakout_lookback_candles, breakout_tolerance_pct)
                        and check_breakout_candle_close(level_price, direction, candles_for_breakout, buffer_pct=0.0)):
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
            _log(log_entry)
            continue

        if (now.hour, now.minute) >= MCX_NO_NEW_ENTRY_AFTER:
            log_entry["trade_status"] = "SKIPPED_TOO_LATE_FOR_NEW_ENTRY"
            log_entry["reason"] = f"{MCX_NO_NEW_ENTRY_AFTER[0]}:{MCX_NO_NEW_ENTRY_AFTER[1]:02d} नंतर नवीन entry नाही (EOD square-off आधीची मार्जिन) ({timeframe_suffix})"
            _log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — अंतिम (breakout-flip नंतरच्याही) direction वरच तपासलं जातं, जेणेकरून
        # कुठल्याही उगमाची (reversal/breakout) या दिशेची trade अडवली जाईल. फक्त नवीन trades थांबतात.
        if direction == "BULLISH" and not bullish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BULLISH_ENTRY_DISABLED"
            log_entry["reason"] = f"Bullish Entry सेटिंग्जमधून बंद आहे ({timeframe_suffix})"
            _log(log_entry)
            continue
        if direction == "BEARISH" and not bearish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BEARISH_ENTRY_DISABLED"
            log_entry["reason"] = f"Bearish Entry सेटिंग्जमधून बंद आहे ({timeframe_suffix})"
            _log(log_entry)
            continue

        # 🎓 MCX टप्पा 1 (mcx_filters.py, replay सारखेच नियम) -- SL/Trailing-SL **तोट्याने** बंद झाल्यावर sl_cooldown_minutes नवीन entry नाही;
        # आणि आज ज्या level वर ज्या दिशेने SL लागला त्या level वर त्याच दिशेने आज पुन्हा नाही. दोन्ही SKIPPED_* (max-hits मोजत नाहीत).
        # Breakout सकट सर्व entries ना लागू. DB वाचता आलं नाही तर fail-open (जुन्या gates प्रमाणे).
        if sl_cooldown_minutes > 0 or sl_level_direction_block_enabled:
            if not closed_today_cache:
                try:
                    closed_today_cache.append(get_closed_trades_on_date(symbol, source, trade_date))
                except Exception as exc:
                    print(f"{symbol}: आजचे बंद trades वाचता आले नाहीत ({exc}) — cooldown/level-direction तपासणी वगळली")
                    closed_today_cache.append([])
            prior = closed_today_cache[0]
            now_naive = now.replace(tzinfo=None)
            if sl_cooldown_minutes > 0:
                blocked, why = MF.sl_cooldown_block(prior, now_naive, sl_cooldown_minutes)
                if blocked:
                    log_entry["trade_status"] = "SKIPPED_SL_COOLDOWN"
                    log_entry["reason"] = f"{why} ({timeframe_suffix})"
                    _log(log_entry)
                    continue
            if sl_level_direction_block_enabled:
                blocked, why = MF.sl_level_direction_block(prior, now_naive, level_price, direction)
                if blocked:
                    log_entry["trade_status"] = "SKIPPED_SL_LEVEL_SAME_DIRECTION"
                    log_entry["reason"] = f"{why} ({timeframe_suffix})"
                    _log(log_entry)
                    continue

        if hit_count_so_far >= max_hits_per_zone and not is_breakout_trade:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = f"आजच्या या zone साठी (याच role) कमाल {max_hits_per_zone} वेळा मर्यादा आधीच गाठलेली ({timeframe_suffix})"
            _log(log_entry)
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
                _log(log_entry)
                continue

        # 🎓 "First time level hit, level hold Minimum period for 1st trade" (5M/15M सारखाच, 1-मिनिट candles वरून, MCX च्या 0.10% touch
        # buffer सकट) -- level ला किंमत टेकल्यावर किमान entry_min_hold_minutes सलग टिकली तरच entry. first_trade_only असल्यास फक्त त्या
        # level+role वरच्या आजच्या पहिल्या **खऱ्या** trade ला (last_trade_time -- नाकारलेला touch "पहिला" मोजला जात नाही). Breakout ला
        # लागू नाही (किंमत level पासून दूर गेलेली असते, टिकण्याचा प्रश्नच नाही; त्याचं स्वतःचं confirmation आधीच आहे). 1-मिनिट डेटा
        # नसेल/त्रुटी आली तर fail-open. SKIPPED_MIN_HOLD_DURATION no-hit status (max-hits मोजत नाही).
        if (entry_min_hold_gate_enabled and not is_breakout_trade
                and not (entry_min_hold_first_trade_only and last_trade_time is not None)):
            if not todays_1m_cache:
                todays_1m_cache.append(fetch_mcx_todays_1m_candles(access_token, instrument_key, now))
            candles_1m = todays_1m_cache[0]
            if candles_1m:
                held_minutes = count_consecutive_touch_minutes(level_price, candles_1m, tolerance_pct=TOUCH_TOLERANCE_PCT)
                if held_minutes < entry_min_hold_minutes:
                    log_entry["trade_status"] = "SKIPPED_MIN_HOLD_DURATION"
                    log_entry["reason"] = (
                        f"Level फक्त {held_minutes} मिनिटं टिकून आहे (किमान {entry_min_hold_minutes} हवीत) — ताजा/अस्थिर touch ({timeframe_suffix})"
                    )
                    _log(log_entry)
                    continue

        # 🎓 "add Supertrend entry gate for MCX futures" -- supertrend_filter_mode (बघा effective_supertrend_mode): "both_against" = किंमत 1H
        # **आणि** 4H दोन्ही Supertrend च्या खाली => Bullish नाही, दोन्हींच्या वर => Bearish नाही (जुना नियम); "htf_against" = 4H विरुद्ध असला
        # तरी नाही (MCX टप्पा 1). Breakout सकट सर्व entries ला लागू. SKIPPED_MCX_TREND_FILTER no-hit status (max-hits मोजत नाही).
        if supertrend_filter_mode != "off":
            if not supertrend_directions_cache:
                supertrend_directions_cache.append(fetch_mcx_trend_filter_directions(
                    access_token, instrument_key, now, supertrend_1h_period, supertrend_1h_multiplier,
                    supertrend_4h_period, supertrend_4h_multiplier,
                ))
            st_dir_1h, st_dir_4h = supertrend_directions_cache[0]
            blocked, why = MF.supertrend_block(supertrend_filter_mode, direction, st_dir_1h, st_dir_4h)
            if blocked:
                log_entry["trade_status"] = "SKIPPED_MCX_TREND_FILTER"
                log_entry["reason"] = f"{why} [mode {supertrend_filter_mode}; 1H: {st_dir_1h}, 4H: {st_dir_4h}] ({timeframe_suffix})"
                _log(log_entry)
                continue

        # 🎓 MCX टप्पा 1 -- "broken-support cascade" (mcx_filters.cascade_block, pure price action, 30M): मागच्या 2 sessions मध्ये 30M close ने
        # तुटलेल्या support खालच्या level वर LONG फक्त 30M bullish CHoCH नंतर (resistance साठी उलट). फक्त पूर्ण 30M bars. Breakout ला लागू नाही
        # (तो reversal नाही, trend-continuation). डेटा नसेल तर fail-open. डीफॉल्ट बंद.
        if cascade_filter_enabled and not is_breakout_trade:
            if not completed_30m_cache:
                completed_30m_cache.append(fetch_completed_30m_bars(access_token, instrument_key, now))
            blocked, why, _info = MF.cascade_block(completed_30m_cache[0], direction, level_price)
            if blocked:
                log_entry["trade_status"] = "SKIPPED_CASCADE_NO_CHOCH"
                log_entry["reason"] = f"{why} ({timeframe_suffix})"
                _log(log_entry)
                continue

        if has_open_trade_from_source(symbol, source):
            log_entry["trade_status"] = "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"
            log_entry["reason"] = f"आधीची MCX Futures position (कुठल्याही level/timeframe वरची) अजून बंद झालेली नाही ({timeframe_suffix})"
            _log(log_entry)
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

        trading_mode = "PAPER" if shadow else settings.get("trading_mode", "PAPER")
        broker_account_ids = [] if shadow else (settings.get("broker_account_ids") or [])
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
            trade_ok, trade_response = open_multi_leg_trade(
                access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=100, target_pct_of_max_profit=100,
                product_type=PRODUCT_TYPE, trading_mode=trading_mode, trading_style="INTRADAY",
                sl_pct_of_credit=None, source=source,
                entry_level_price=level_price, entry_timeframe=timeframe_suffix,
            )
            # 🎓 code-review द्वारे सापडवलेली bug (बघा trading_engine.format_trade_result() ची
            # टिप्पणी) — open_multi_leg_trade() चं दुसरं मूल्य dict असतं, raw dict signal_log.
            # trade_status (TEXT column) मध्ये साठवायचा प्रयत्न केला की DB insert चुपचाप अपयशी
            # ठरायचा, आणि नेमकी entry-क्षणाचीच signal_log रांग हरवायची.
            trade_status = format_trade_result(trade_ok, trade_response)

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
        _log(log_entry)

        hit_label_header = "🎯 Breakout Entry" if is_breakout_trade else f"🎯 Dynamic S/R Cross (आजचा {hit_count_so_far + 1}/{max_hits_per_zone} वा trade)"
        if shadow:
            hit_label_header = f"🧪 [SR V3 PAPER shadow] (आजचा {hit_count_so_far + 1}/{max_hits_per_zone} वा trade)"
        elif level_source == "SRV3":
            hit_label_header += " — SR V3 levels"
        message = (
            f"{hit_label_header} <b>{symbol} MCX Futures ({timeframe_suffix})</b>\n"
            f"{level_type} {level_price:.2f} — {transaction_type} {resolved['trading_symbol']} (≈{entry_price_estimate:.2f}). {rsi_display}\n"
            f"निकाल: {trade_status}\n"
            f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        return f"{symbol}: 🎯 {level_type} {level_price:.2f} ({timeframe_suffix}) -> {transaction_type} {trade_status}"

    return f"{symbol}: कुठलाही MCX level ({'/'.join(active_suffixes)}, RSI+Multi-Hit मर्यादेसह) पात्र ठरला नाही"


# 🎓 Slippage -- trailing %-mode मध्ये प्रत्येक cycle ला resolve_symbol() + 30-मिनिट candles (२ Upstox कॉल्स) लागतात.
# ५ सेकंदांच्या cadence वर हेच खरा उशीर ठरतं. trailing distance = किंमत × pct असल्याने २० सेकंदांत किंमत
# थोडीच बदलते, म्हणून ती "points-समतुल्य" संख्या थोडा वेळ पुन्हा वापरतो (ताजी किंमत बहुतेक वेळा आधी
# मागवलेलीच असते). exit-निर्णयाचं logic बदलत नाही.
TRAILING_PRICE_CACHE_TTL_SECONDS = 20.0
_trailing_price_cache = {}


def _get_trailing_reference_price(access_token, symbol, instrument_key=None, now_fn=time.monotonic):
    """सद्य किंमत (30M candle close) -- TTL-cached; मिळाली नाही तर None (त्या cycle ला trailing वगळणे, सुरक्षित).
    `instrument_key` = उघड्या trade चा स्वतःचा contract (roll नंतर resolver पुढचा contract देतो, पण जुन्या contract वरच्या trade चं
    trailing अंतर त्याच्याच भावावरून हवं). न दिल्यास resolver चा सध्याचा contract (जुनं वर्तन)."""
    now = now_fn()
    cache_key = (symbol, instrument_key)
    hit = _trailing_price_cache.get(cache_key)
    if hit is not None and now - hit[0] < TRAILING_PRICE_CACHE_TTL_SECONDS:
        return hit[1]
    if instrument_key is None:
        ok, resolved = mcx_resolver.resolve_symbol(access_token, symbol)
        if not ok:
            return None
        instrument_key = resolved["instrument_key"]
    df_current = fetch_mcx_candles(access_token, instrument_key, interval="30minute", lookback_days=1)
    if df_current is None or df_current.empty:
        return None
    price = float(df_current["close"].iloc[-1])
    _trailing_price_cache[cache_key] = (now, price)
    return price


def monitor_symbol(access_token, symbol, broker_positions=None, record_timing=False, live_prices=None, live_price_age=None):
    """उघड्या MCX Futures positions चं SL/Target/Trailing/EOD — established trading_engine.
    manage_open_trades() (कुठलाही बदल न करता, generic "else" branch) — trade_monitor.py चं
    MONITORED_SYMBOLS इथे बदललेलं नाही, त्यामुळे हीच script स्वतःच monitoring करते.

    `broker_positions` (असेल तर) -- run_exit_monitor_cycle() ने एकदाच आणलेले positions सर्व symbols ना शेअर केलेले
    (नाहीतर manage_open_trades() स्वतः प्रत्येक symbol साठी fetch करतं -- जुनं वर्तन). `record_timing=True` ->
    exit होताना '[Monitor lag: ...]' तुकडा."""
    settings = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol)
    trailing_sl_enabled = bool(settings.get("trailing_sl_enabled", False))
    trailing_distance_points = settings.get("trailing_distance_points") if trailing_sl_enabled else None
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Points सोबतच Percentage mode) — trailing_pct असेल तर
    # सद्य किंमतीवरून points-समतुल्य अंतर काढलं जातं — compute_trailing_sl_level() ला अजिबात हात न लावता.
    if trailing_sl_enabled and settings.get("sl_target_mode", "POINTS") == "PERCENT":
        open_keys = get_open_trade_contracts(symbol, MCX_TRADE_SOURCES)
        # उघडा trade नसेल तर trailing ची गरजच नाही (API call वाचतो). एकापेक्षा जास्त contracts (roll च्या आसपास मूळ + shadow) असतील तर
        # सर्वात जवळच्या expiry चा -- अंतर हे किमतीच्या % मध्ये असल्याने दोन contracts मधला फरक (calendar spread) नगण्य.
        current_price = (_get_trailing_reference_price(access_token, symbol, instrument_key=open_keys[0]) if open_keys else None)
        if current_price is not None:
            trailing_distance_points = current_price * float(settings.get("trailing_pct", 1.0)) / 100
        else:
            trailing_distance_points = None  # सद्य किंमत मिळाली नाही — या cycle ला trailing वगळणे (सुरक्षित)
    extra = {}
    if broker_positions is not None:
        extra["broker_positions"] = broker_positions
    if record_timing:
        extra["record_timing"] = True
    if live_prices is not None:
        extra["live_prices"] = live_prices
        extra["live_price_age"] = live_price_age
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
        **extra,
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


EXIT_MONITOR_LOCK_NAME = "mcx_exit_monitor"


def run_exit_monitor_cycle(token, symbols, heartbeat=False, live_prices=None, live_price_age=None):
    """प्रत्येक symbol साठी monitor_symbol() (SL/Target/Trailing/EOD) — एकाच cycle मध्ये सर्व
    commodities, एकाच्या अपयशाने बाकीच्यांना न अडवता (established 3 bots च्या पॅटर्नप्रमाणेच).

    🎓 Slippage -- cycle हलकी (trade_monitor.py प्रमाणेच): (१) OPEN trade नसलेल्या symbols साठी कुठलेही Upstox/Supabase
    कॉल्स नाहीत (आधी पाचही commodities साठी प्रत्येक cycle ला); (२) positions एकदाच आणून सर्व symbols ना दिले, आणि तेही
    फक्त LIVE trade असेल तरच. (३) प्रत्येक cycle फक्त `mcx_exit_monitor` lock धरतो -- दोन invocations overlap झाल्या
    तरी एका वेळी एकच cycle चालतो (डुप्लिकेट-exit टाळतो). symbol-नुसार OPEN यादी मिळाली नाही (DB त्रुटी) तर सगळे
    symbols तपासले जातात (सुरक्षित, जुनं वर्तन)."""
    try:
        with ProcessLock(EXIT_MONITOR_LOCK_NAME):
            return _run_exit_monitor_cycle_locked(token, symbols, heartbeat, live_prices, live_price_age)
    except ProcessLockHeld:
        return ["⏭️ दुसरी MCX exit-monitor cycle अजून चालू आहे — डुप्लिकेट-exit टाळण्यासाठी वगळली."], False


def _run_exit_monitor_cycle_locked(token, symbols, heartbeat, live_prices=None, live_price_age=None):
    symbols = [s.strip() for s in symbols]
    modes_by_symbol = None
    try:
        modes_by_symbol = database.get_open_trade_modes_by_symbol(symbols)
    except Exception:
        modes_by_symbol = None  # DB त्रुटी -- खाली सगळे symbols तपासले जातील
    symbols_to_check = symbols if modes_by_symbol is None else [s for s in symbols if s in modes_by_symbol]

    shared_positions = None
    if live_prices is not None:
        # 🎓 WebSocket feed (position_stream_monitor.py --market mcx) -- किमती आधीच live_prices मध्ये; positions REST ने आणत नाही
        # ([] -> reconciliation/broker-MTM फक्त cron चा REST monitor करतो; [] मुळे कुठलीही trade चुकून CLOSED होत नाही).
        shared_positions = []
    elif modes_by_symbol is not None and any("LIVE" in modes for modes in modes_by_symbol.values()):
        shared_positions = fetch_broker_positions(token)

    results = []
    any_symbol_succeeded = False
    for symbol in symbols_to_check:
        try:
            stream_kwargs = {"live_prices": live_prices, "live_price_age": live_price_age} if live_prices is not None else {}
            closed = monitor_symbol(token, symbol, broker_positions=shared_positions, record_timing=True, **stream_kwargs)
            any_symbol_succeeded = True
            if closed:
                results.append(f"{symbol}: 🔔 {len(closed)} position(s) बंद झाल्या — {closed}")
                # 🎓 "Roj entri exit che sandesh aale pahije" -- NSE चा trade_monitor.py exit वर Telegram पाठवतो, पण MCX exit loop
                # फक्त print करायचा, Telegram कधीच नाही. Telegram अपयशी झालं तरी exit-loop थांबता कामा नये.
                for c in closed:
                    try:
                        notify_exit("mcx_futures_trader", symbol, c.get("trade_id"), c.get("reason"), c.get("pnl"))
                    except Exception:
                        pass
        except Exception as e:
            notify_error("mcx_futures_trader", f"{symbol}: monitor त्रुटी — {e}")
            results.append(f"⚠️ {symbol}: monitor अनपेक्षित त्रुटी — {e}")
    # OPEN trade नसतानाही monitor जिवंत आहे (heartbeat कायम)
    return results, (any_symbol_succeeded or not symbols_to_check)


def _any_open_mcx_trades(symbols):
    try:
        return bool(database.get_open_trade_modes_by_symbol([s.strip() for s in symbols]))
    except Exception:
        return False  # DB त्रुटीने loop थांबू नये -- नेहमीचा interval वापरला जाईल


def run_exit_monitor_loop(token, symbols, interval_seconds=15, loop_seconds=30,
                           sleep_fn=time.sleep, now_fn=time.monotonic, print_fn=print,
                           open_interval_seconds=5, has_open_trades_fn=None):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("exit slippage") — trade_monitor.py च्याच
    run_monitor_loop() पॅटर्नची MCX आवृत्ती — एका invocation च्या आत, interval_seconds च्या
    अंतराने loop_seconds पर्यंत run_exit_monitor_cycle() पुन्हा-पुन्हा चालवणे, जेणेकरून SL/Target
    ओलांडल्यानंतर बॉटला कळायला आधीच्या (दर मिनिटाला फक्त एकदा) ऐवजी कमी वेळ लागेल. प्रत्येक cycle चा वेळ
    वजा करूनच पुढचा sleep काढला जातो, जेणेकरून एकूण वेळ loop_seconds च्या आसपासच राहील.

    कुठलाही MCX trade OPEN असेल तर पुढचा sleep `open_interval_seconds` (डीफॉल्ट 5) इतका घट्ट, नाहीतर
    `interval_seconds` (15) -- trade_monitor.py प्रमाणेच.

    ⚠️ जुन्या एकत्रित मोडमध्ये (`--mode both`: entry + exit एकाच प्रोसेसमध्ये, crontab ओळीत `sleep 60`) loop_seconds
    डीफॉल्ट 30 मुद्दामच कमी -- entry-तपासणी + हा loop मिळून उरलेल्या ~60-सेकंद budget पेक्षा जास्त वेळ घेतला तर पुढची
    invocation ProcessLockHeld मुळे वगळली जाते. पूर्ण मिनिट (62 s) अखंड तपासणीसाठी `--mode exit` वेगळ्या cron ओळीत
    (sleep शिवाय) वापरा -- deploy/README.md बघा."""
    if has_open_trades_fn is None:
        def has_open_trades_fn():
            return _any_open_mcx_trades(symbols)
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
        effective_interval = open_interval_seconds if has_open_trades_fn() else interval_seconds
        sleep_time = min(effective_interval - cycle_duration, remaining_in_budget)
        if sleep_time > 0:
            sleep_fn(sleep_time)
    return any_succeeded_overall


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(MCX_FUTURES_SYMBOLS))
    parser.add_argument("--mode", choices=["both", "entry", "exit"], default="both",
                         help="both (डीफॉल्ट, जुनं वर्तन: entry-तपासणी + exit-monitoring एकाच प्रोसेसमध्ये), entry (फक्त नवीन "
                              "trade शोधणे), exit (फक्त SL/Target/Trailing/EOD -- वेगळ्या cron ओळीत, sleep शिवाय, पूर्ण मिनिट)")
    parser.add_argument("--interval-seconds", type=float, default=15,
                         help="कुठलाही trade OPEN नसताना exit-monitoring किती सेकंदांच्या अंतराने तपासायचं (डीफॉल्ट 15)")
    parser.add_argument("--open-interval-seconds", type=float, default=5,
                         help="कुठलाही MCX trade OPEN असताना किती सेकंदांच्या अंतराने तपासायचं (डीफॉल्ट 5)")
    parser.add_argument("--loop-seconds", type=float, default=None,
                         help="एका invocation मध्ये exit-monitoring किती सेकंद पुन्हा-पुन्हा तपासत राहायचं (डीफॉल्ट: --mode both "
                              "मध्ये 30 -- crontab च्या आधीच्या sleep 60 stagger नंतरच्या उरलेल्या budget मध्ये सुरक्षित बसावं म्हणून; "
                              "--mode exit मध्ये 62 -- cron दर 60 सेकंदांनी नवी प्रोसेस सुरू करतो, मध्ये अंतर पडू नये म्हणून)")
    args = parser.parse_args()
    loop_seconds = args.loop_seconds if args.loop_seconds is not None else (62 if args.mode == "exit" else 30)

    # 🎓 Slippage -- exit loop असलेल्या मोड्समध्ये प्रत्येक cycle ला settings साठी नवा Supabase connection उघडू नये म्हणून
    # या प्रोसेसपुरता छोटा TTL-cache (Dashboard बदल १० सेकंदांत लागू). entry मोडमध्ये गरज नाही.
    if args.mode in ("both", "exit"):
        from read_cache import install_monitor_read_cache
        install_monitor_read_cache(cloud_db)

    # 🎓 established 3 bots प्रमाणेच — Duplicate-Order Protection (VPS crontab वर मंद network/retry
    # मुळे मागची invocation अजून चालू असू शकते; अशा वेळी नवीन invocation डुप्लिकेट ऑर्डर टाळण्यासाठी थांबते).
    # `--mode exit` मध्ये हा process-lock वापरत नाही -- तिथे प्रत्येक cycle भोवतीचा `mcx_exit_monitor` lock आहे, त्यामुळे
    # entry प्रोसेसशी टक्कर होत नाही आणि दोन exit invocations overlap झाल्या तरी सुरक्षित.
    try:
        init_sqlite_db()
        if args.mode == "exit":
            token = cloud_db.get_effective_upstox_token(args.token)
            if not token:
                msg = "कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही)."
                print(f"❌ {msg}")
                notify_error("mcx_futures_trader", msg)
                exit(1)
            symbols_list = args.symbols.split(",")
            exit_succeeded = run_exit_monitor_loop(
                token, symbols_list, args.interval_seconds, loop_seconds,
                open_interval_seconds=args.open_interval_seconds,
            )
            if exit_succeeded:
                write_heartbeat("mcx_exit_monitor")
        else:
            with ProcessLock("mcx_futures_trader"):
                cloud_db.init_cloud_table()
                token = cloud_db.get_effective_upstox_token(args.token)
                if not token:
                    msg = "कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही)."
                    print(f"❌ {msg}")
                    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (LIVE readiness — "token-missing वर Telegram
                    # अलर्ट") — सकाळी token expire झालेला असेल तर बॉट शांतपणे थांबू नये.
                    notify_error("mcx_futures_trader", msg)
                    exit(1)
                symbols_list = args.symbols.split(",")
                entry_succeeded = run_all_symbols(token, symbols_list)
                exit_succeeded = False
                if args.mode == "both":
                    exit_succeeded = run_exit_monitor_loop(
                        token, symbols_list, args.interval_seconds, loop_seconds,
                        open_interval_seconds=args.open_interval_seconds,
                    )
                if entry_succeeded or exit_succeeded:
                    write_heartbeat("mcx_futures_trader")
                run_auto_backup_if_due(interval_minutes=60)
    except ProcessLockHeld as e:
        print(f"⏭️ मागची invocation अजून चालू आहे, ही वगळली — डुप्लिकेट ऑर्डर टाळण्यासाठी ({e})")
