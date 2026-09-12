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
from database import init_sqlite_db, has_open_trade_from_source
from notifications import send_telegram_message
from signals import calculate_rsi
from strategy import select_credit_spread_fixed_strikes
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
    now = get_ist_now()
    state = cloud_db.get_srv2_state(symbol)

    if is_in_cooldown(state["last_sl_hit_time"], now):
        return f"{symbol}: Cooldown कालावधी चालू आहे (SL नंतर {COOLDOWN_MINUTES} मिनिटं विराम)"

    settings = cloud_db.get_srv2_settings(symbol)
    lots = settings["lots"]
    hedge_width_points = settings["hedge_width_points"]

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    trade_date = now.strftime("%Y-%m-%d")
    candidates = _collect_touch_candidates(access_token, symbol, all_zones, now)
    if not candidates:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels (15M/30M/60M) सापडले नाहीत, किंवा आजचे candles अजून तयार नाहीत"

    for level_price, timeframe_suffix, candles_df, underlying_price in candidates:
        touched = abs(underlying_price - level_price) <= level_price * TOUCH_TOLERANCE_PCT / 100
        if not touched:
            continue

        # वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — दिशा सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून.
        if underlying_price >= level_price:
            level_type, direction = "SUPPORT", "BULLISH"
        else:
            level_type, direction = "RESISTANCE", "BEARISH"

        rsi_ok, rsi_value = check_rsi_filter(candles_df, direction)
        if not rsi_ok:
            continue

        # Multi-Hit — बिनशर्त position-check (कुठल्याही level/timeframe साठी).
        hit_count_so_far, _ = cloud_db.get_zone_hits_today(symbol, level_price, trade_date)
        if hit_count_so_far >= 2:
            continue
        if has_open_trade_from_source(symbol, "srv2_momentum_reversal"):
            continue

        # --- सर्व अटी पूर्ण! Entry ---
        # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Expiry-Day Logic) — आज expiry day असेल, तर
        # पुढच्या आठवड्याचे strikes (expiry_index=1) — आजच्या expiry वर trade नाही (जास्त जोखीम).
        expiry_index = 1 if is_todays_expiry_day(access_token, symbol) else 0
        raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol, expiry_index=expiry_index)
        if not raw_chain:
            return f"{symbol}: Option chain मिळाली नाही ({chain_status})"
        atm_strike = round(underlying_price / 50) * 50

        strategy_result = select_credit_spread_fixed_strikes(
            raw_chain, direction, atm_strike, strikes_otm=1, hedge_width_points=hedge_width_points,
        )
        if strategy_result is None:
            cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
            return f"{symbol}: {level_type} {level_price:.2f} ({timeframe_suffix}) टेस्ट झाला, पण strike-निवड अयशस्वी"

        net_credit_total = strategy_result["net_credit"] * lot_size
        sl_pct = SL_PCT_OF_CREDIT

        accounts_df = cloud_db.get_all_broker_accounts(active_only=False)
        if accounts_df is not None and not accounts_df.empty:
            from trading_engine import execute_trade_on_all_accounts
            results, factory_errors = execute_trade_on_all_accounts(
                symbol=symbol, strategy_result=strategy_result, base_lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=None, target_pct_of_max_profit=TARGET_PCT_OF_PREMIUM,
                product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                sl_pct_of_credit=sl_pct, source="srv2_momentum_reversal",
                entry_level_price=level_price,
            )
            trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
            if factory_errors:
                trade_status += " | वगळलेले: " + "; ".join(factory_errors)
        else:
            trade_result, trade_status = open_multi_leg_trade(
                access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=None, target_pct_of_max_profit=TARGET_PCT_OF_PREMIUM,
                product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                sl_pct_of_credit=sl_pct, source="srv2_momentum_reversal",
                entry_level_price=level_price,
            )

        cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
        cloud_db.save_signal_log({
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": level_type,
            "level_price": level_price, "hit_type": "TOUCH", "direction": direction,
            "ltp_at_signal": underlying_price, "trade_status": trade_status,
            "reason": f"RSI {rsi_value} ({timeframe_suffix}), फिल्टर पास",
        })

        strategy_label = "Bull Put Spread (Support Bounce)" if direction == "BULLISH" else "Bear Call Spread (Resistance Bounce)"
        message = (
            f"🎯 <b>{symbol} SRv2 Momentum-Reversal ({timeframe_suffix})</b> (आजचा {hit_count_so_far + 1}/2 वा hit)\n"
            f"{level_type} {level_price:.2f} — RSI {rsi_value} (फिल्टर पास).\n"
            f"{strategy_label} — SL {sl_pct:.1f}% of Premium, Target {TARGET_PCT_OF_PREMIUM}%.\n"
            f"PAPER Trade: {trade_status} — वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        return f"{symbol}: 🎯 {level_type} {level_price:.2f} ({timeframe_suffix}, RSI {rsi_value}) -> {strategy_label} PAPER trade {trade_status}"

    return f"{symbol}: कुठलाही SRv2 level (15M/30M/60M, RSI+Multi-Hit मर्यादेसह) पात्र ठरला नाही"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default="NIFTY")
    args = parser.parse_args()

    init_sqlite_db()
    cloud_db.init_cloud_table()
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)
    for symbol in args.symbols.split(","):
        print(process_symbol(token, symbol.strip()))
