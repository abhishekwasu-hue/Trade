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

import cloud_db
import resolve_mcx_futures_instruments as mcx_resolver
from config import get_ist_now
from database import init_sqlite_db, has_open_trade_from_source, run_auto_backup_if_due
from dynamic_sr_instant_trader import check_instant_rsi_filter
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

TOUCH_TOLERANCE_PCT = 0.05
TIMEFRAME_SUFFIXES = ["30M", "60M"]  # 15M कधीच नाही (वापरकर्त्याने स्पष्ट सांगितल्याप्रमाणे)

# MCX चं trading session NSE पेक्षा खूप उशिरापर्यंत (रात्री, हंगामानुसार ~23:30/23:55 पर्यंत बदलतं,
# deploy/README.md मधली नोंद बघा) — प्रत्यक्ष exchange-close च्या थोडं आधी, established इतर
# strategies (15:15 IST, exchange-close 15:30 च्या आधी) सारखाच सुरक्षित मार्जिन ठेवणारा डीफॉल्ट.
MCX_EOD_HOUR = 23
MCX_EOD_MINUTE = 15


def _collect_touch_candidates(access_token, instrument_key, all_zones, active_suffixes, now):
    """दिलेल्या timeframes (30M/60M) च्या ACTIVE levels, प्रत्येकाचे स्वतःचे candles (त्याच
    timeframe चा RSI साठी) आणि सद्य किंमत (आजच्याच दिवसाची) — एकाच यादीत एकत्र करणे.
    srv2_momentum_reversal_strategy._collect_touch_candidates() याच पॅटर्नचं MCX-futures आवृत्ती —
    फरक फक्त instrument_key (resolve_mcx_futures_instruments कडून) व fetch_mcx_candles() वापरणं.
    रिटर्न: [(level_price, timeframe_suffix, candles_df, current_price), ...]"""
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
        for _, zrow in dyn_levels.iterrows():
            candidates.append((zrow["zone_low"], suffix, candles_df, current_price))
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
    entry_rsi_gate_enabled = settings.get("entry_rsi_gate_enabled", True)
    rsi_support_max = settings.get("rsi_support_max", 40)
    rsi_resistance_min = settings.get("rsi_resistance_min", 60)
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

    for level_price, timeframe_suffix, candles_df, current_price in candidates:
        touched = abs(current_price - level_price) <= level_price * TOUCH_TOLERANCE_PCT / 100

        # दिशा सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून (साठवलेल्या ऐतिहासिक label वरून नाही) —
        # srv2_momentum_reversal_strategy.py/dynamic_sr_instant_trader.py सारखाच established नियम.
        if current_price >= level_price:
            level_type, direction = "SUPPORT", "BULLISH"
        else:
            level_type, direction = "RESISTANCE", "BEARISH"

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

        rsi_value = None
        if entry_rsi_gate_enabled:
            rsi_ok, rsi_value = check_instant_rsi_filter(candles_df, direction, rsi_support_max, rsi_resistance_min)
            if not rsi_ok:
                log_entry["trade_status"] = "SKIPPED_RSI_FILTER"
                log_entry["reason"] = (
                    f"RSI {rsi_value} ({timeframe_suffix}) दिशेशी जुळत नाही "
                    f"(Support<{rsi_support_max} / Resistance>{rsi_resistance_min} हवं होतं)"
                )
                cloud_db.save_signal_log(log_entry)
                continue

        hit_count_so_far, last_hit_time = cloud_db.get_zone_hits_today(symbol, level_price, trade_date, role=level_type)
        if hit_count_so_far >= 2:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = f"आजच्या या zone साठी (याच role) कमाल 2 वेळा मर्यादा आधीच गाठलेली ({timeframe_suffix})"
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

        rsi_display = f"RSI {rsi_value} ({timeframe_suffix}), फिल्टर पास" if entry_rsi_gate_enabled else f"RSI Gate बंद ({timeframe_suffix}, तपासलं नाही)"
        log_entry["trade_status"] = trade_status
        log_entry["reason"] = rsi_display
        cloud_db.save_signal_log(log_entry)

        message = (
            f"🎯 <b>{symbol} MCX Futures ({timeframe_suffix})</b> (आजचा {hit_count_so_far + 1}/2 वा hit)\n"
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
    """🎓 established 3 bots प्रमाणेच — प्रत्येक symbol चं entry-तपासणी व exit-monitoring स्वतंत्र
    try/except मध्ये, एकाच्या अपयशाने बाकीच्यांना/heartbeat ला अडवू नये म्हणून."""
    any_symbol_succeeded = False
    for symbol in symbols:
        symbol = symbol.strip()
        try:
            print(process_symbol(token, symbol))
            any_symbol_succeeded = True
        except Exception as e:
            notify_error("mcx_futures_trader", f"{symbol}: entry-तपासणी त्रुटी — {e}")
            print(f"⚠️ {symbol}: entry-तपासणी अनपेक्षित त्रुटी — {e}")

        try:
            closed = monitor_symbol(token, symbol)
            if closed:
                print(f"{symbol}: 🔔 {len(closed)} position(s) बंद झाल्या — {closed}")
            any_symbol_succeeded = True
        except Exception as e:
            notify_error("mcx_futures_trader", f"{symbol}: monitor त्रुटी — {e}")
            print(f"⚠️ {symbol}: monitor अनपेक्षित त्रुटी — {e}")
    return any_symbol_succeeded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(MCX_FUTURES_SYMBOLS))
    args = parser.parse_args()

    # 🎓 established 3 bots प्रमाणेच — Duplicate-Order Protection (VPS crontab वर मंद network/retry
    # मुळे मागची invocation अजून चालू असू शकते; अशा वेळी नवीन invocation डुप्लिकेट ऑर्डर टाळण्यासाठी थांबते).
    try:
        with ProcessLock("mcx_futures_trader"):
            init_sqlite_db()
            cloud_db.init_cloud_table()
            token = cloud_db.get_effective_upstox_token(args.token)
            if not token:
                print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
                exit(1)
            any_symbol_succeeded = run_all_symbols(token, args.symbols.split(","))
            if any_symbol_succeeded:
                write_heartbeat("mcx_futures_trader")
            run_auto_backup_if_due(interval_minutes=60)
    except ProcessLockHeld as e:
        print(f"⏭️ मागची invocation अजून चालू आहे, ही वगळली — डुप्लिकेट ऑर्डर टाळण्यासाठी ({e})")
