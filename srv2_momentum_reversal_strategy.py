"""
srv2_momentum_reversal_strategy.py
------------------------------------------------
🎓 वापरकर्त्याशी चर्चा करून, संपूर्ण blueprint वरून बांधलेली नवीन रणनीती —
"Nifty SRv2 Momentum-Filter Reversal"

established SRv2 (sr_dynamic.compute_dynamic_sr, Chart वर दाखवला जाणारा) + 0.40% दिशात्मक-गती फिल्टर
(chop-zone मधले खोटे bounce टाळण्यासाठी) एकत्र — 15-मिनिट Nifty (Cash) साठी.

नियम (वापरकर्त्याने दिलेला संपूर्ण blueprint):
  Rule 1 (Momentum Prerequisite): SRv2 level टेस्ट होण्याआधी, अलीकडच्या candles मधल्या स्विंग-टोकापासून
    सद्य किमतीपर्यंत किमान ०.४०% हालचाल झालेली हवी (Bullish: स्विंग High पासून खाली, Bearish: स्विंग
    Low पासून वर) — अन्यथा choppy/sideways बाजारातले खोटे bounce नाकारले जातात.
  Rule 2 (Entry): फिल्टर पास झाल्यावर, LTP ने SRv2 Support/Resistance ला स्पर्श केला की —
    Support Bounce (Long) -> established select_credit_spread_fixed_strikes(strikes_otm=1,
    hedge_width_points=100) — ATM+1 विकणे (Put), ATM+3 hedge.
    Resistance Bounce (Short) -> तेच, पण Call बाजूने (ATM+1 विकणे, ATM+3 hedge).
  Rule 3 (Risk): SL = ₹500 (collective net premium वर, established sl_pct_of_credit मध्ये रूपांतरित),
    Target = net premium च्या 80%.
  Rule 4 (Filtering): One-Touch (त्याच level ची लगेचची पुन्हा-चाचणी दुर्लक्षित) + Cooldown (SL लागल्यावर
    २-candle म्हणजे ३०-मिनिटांचा अनिवार्य विराम) — established srv2_strategy_state (Supabase) द्वारे.

⚠️ established GitHub Actions ची खरी तांत्रिक किमान मर्यादा ५ मिनिटं आहे — रणनीती स्वतः 15-मिनिट
chart वापरते, त्यामुळे दर ५ मिनिटांनी चालली तरी नुकसान नाही (established idempotent पॅटर्न — नवीन
15-मिनिट candle आलेली नसेल तर फक्त "काहीच बदल नाही" असं सांगून थांबेल).
"""
import argparse

import cloud_db
from config import get_ist_now
from database import init_sqlite_db
from notifications import send_telegram_message
from sr_dynamic import compute_dynamic_sr
from strategy import select_credit_spread_fixed_strikes
from trading_engine import open_multi_leg_trade
from upstox_api import fetch_upstox_option_chain, fetch_candles

MOMENTUM_MIN_PCT = 0.40      # 🎓 वापरकर्त्याने स्पष्ट सांगितलेलं थ्रेशहोल्ड
TOUCH_TOLERANCE_PCT = 0.05   # established gap-fill/dynamic-sr च्याच tolerance-तत्त्वानुसार
SL_RUPEES = 500              # 🎓 वापरकर्त्याने स्पष्ट सांगितलेलं, प्रति lot-pair निव्वळ प्रीमियमवर
TARGET_PCT_OF_PREMIUM = 80   # 🎓 वापरकर्त्याने स्पष्ट सांगितलेलं
COOLDOWN_MINUTES = 30        # 🎓 वापरकर्त्याने स्पष्ट सांगितलेलं (२ candles × १५-मिनिट)
LEVEL_REPEAT_TOLERANCE_PCT = 0.05  # "तोच level" ओळखण्यासाठी (One-Touch Rule)


def check_momentum_filter(candles, direction, min_move_pct=MOMENTUM_MIN_PCT, lookback=10):
    """
    🎓 Rule 1 — SRv2 test च्याही आधी, अलीकडच्या (लुकबॅक) candles मधल्या स्विंग-टोकापासून सद्य
    किमतीपर्यंत, किमान min_move_pct% हालचाल झाली आहे का तपासणे.
    direction: "BULLISH" (Support Bounce) किंवा "BEARISH" (Resistance Bounce).
    candles: [{"high":.., "low":.., "close":..}, ...] (जुनं ते नवीन क्रमाने)
    """
    if len(candles) < 2:
        return False, 0.0
    recent = candles[-lookback:]
    current_price = recent[-1]["close"]
    if direction == "BULLISH":
        swing_extreme = max(c["high"] for c in recent[:-1])
        move_pct = (swing_extreme - current_price) / swing_extreme * 100
    else:
        swing_extreme = min(c["low"] for c in recent[:-1])
        move_pct = (current_price - swing_extreme) / swing_extreme * 100
    return move_pct >= min_move_pct, round(move_pct, 3)


def compute_sl_pct_from_absolute(sl_rupees, net_credit_total):
    """🎓 Rule 3 — established sl_pct_of_credit (%) मध्ये रूपांतरित, वापरकर्त्याने दिलेल्या ₹ रकमेवरून."""
    if net_credit_total <= 0:
        return None
    return min((sl_rupees / net_credit_total) * 100, 100)


def is_in_cooldown(last_sl_hit_time, now):
    """🎓 Rule 4 (Cooldown) — SL लागल्यावर established COOLDOWN_MINUTES पर्यंत नवीन entry नाही."""
    if last_sl_hit_time is None:
        return False
    elapsed_minutes = (now - last_sl_hit_time).total_seconds() / 60
    return elapsed_minutes < COOLDOWN_MINUTES


def is_repeated_level(level_price, last_tested_level, tolerance_pct=LEVEL_REPEAT_TOLERANCE_PCT):
    """🎓 Rule 4 (One-Touch) — established, तोच level (tolerance च्या आत) लगेच पुन्हा टेस्ट झाला का."""
    if last_tested_level is None:
        return False
    tolerance = level_price * tolerance_pct / 100
    return abs(level_price - last_tested_level) <= tolerance


def process_symbol(access_token, symbol, lots=1, lot_size=65):
    """एका symbol साठी — SRv2 levels, momentum-फिल्टर, One-Touch/Cooldown, आणि आढळल्यास PAPER trade."""
    now = get_ist_now()
    state = cloud_db.get_srv2_state(symbol)

    if is_in_cooldown(state["last_sl_hit_time"], now):
        return f"{symbol}: Cooldown कालावधी चालू आहे (SL नंतर {COOLDOWN_MINUTES} मिनिटं विराम)"

    candles_df = fetch_candles(access_token, symbol, current_spot=0, interval="15minute", lookback_days=5)
    if candles_df is None or candles_df.empty or len(candles_df) < 12:
        return f"{symbol}: पुरेसा 15-मिनिट इतिहास मिळाला नाही"

    underlying_price = candles_df["close"].iloc[-1]
    dyn_sr = compute_dynamic_sr(candles_df, current_price=underlying_price)
    candles = candles_df.tail(11).to_dict("records")

    for level_type, levels in [("SUPPORT", dyn_sr.get("support", [])), ("RESISTANCE", dyn_sr.get("resistance", []))]:
        direction = "BULLISH" if level_type == "SUPPORT" else "BEARISH"
        for lvl in levels:
            level_price = lvl["level"]
            touched = abs(underlying_price - level_price) <= level_price * TOUCH_TOLERANCE_PCT / 100
            if not touched:
                continue

            if is_repeated_level(level_price, state["last_tested_level"]):
                continue  # 🎓 One-Touch Rule -- तोच level लगेच पुन्हा, दुर्लक्षित

            momentum_ok, move_pct = check_momentum_filter(candles, direction)
            if not momentum_ok:
                continue  # 🎓 Rule 1 -- पुरेशी दिशात्मक गती नाही, choppy बाजार

            # --- सर्व अटी पूर्ण! Entry ---
            raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol)
            if not raw_chain:
                return f"{symbol}: Option chain मिळाली नाही ({chain_status})"
            atm_strike = round(underlying_price / 50) * 50

            strategy_result = select_credit_spread_fixed_strikes(raw_chain, direction, atm_strike, strikes_otm=1, hedge_width_points=100)
            if strategy_result is None:
                cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
                return f"{symbol}: {level_type} {level_price:.2f} टेस्ट झाला, पण strike-निवड अयशस्वी"

            net_credit_total = strategy_result["net_credit"] * lot_size
            sl_pct = compute_sl_pct_from_absolute(SL_RUPEES, net_credit_total)

            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" — established
            # broker_accounts (Supabase) मध्ये किमान एक account नोंदवलेला असेल, तर established
            # execute_trade_on_all_accounts() (सर्व सक्रिय accounts वर replicated) वापरणे; अजून
            # कुठलाही account नोंदवलेला नसेल (established, आत्ताची स्थिती), तर established, जुना
            # (single --token, backward-compatible) मार्गच कायम.
            accounts_df = cloud_db.get_all_broker_accounts(active_only=False)
            if accounts_df is not None and not accounts_df.empty:
                from trading_engine import execute_trade_on_all_accounts
                results, factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=strategy_result, base_lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=TARGET_PCT_OF_PREMIUM,
                    product_type="NRML", trading_mode="PAPER", trading_style="INTRADAY",
                    sl_pct_of_credit=sl_pct, source="srv2_momentum_reversal",
                )
                trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
                if factory_errors:
                    trade_status += " | वगळलेले: " + "; ".join(factory_errors)
            else:
                trade_result, trade_status = open_multi_leg_trade(
                    access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=TARGET_PCT_OF_PREMIUM,
                    product_type="NRML", trading_mode="PAPER", trading_style="INTRADAY",
                    sl_pct_of_credit=sl_pct, source="srv2_momentum_reversal",
                )

            cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])

            strategy_label = "Bull Put Spread (Support Bounce)" if direction == "BULLISH" else "Bear Call Spread (Resistance Bounce)"
            message = (
                f"🎯 <b>{symbol} SRv2 Momentum-Reversal</b>\n"
                f"{level_type} {level_price:.2f} — {move_pct}% दिशात्मक गती (फिल्टर पास).\n"
                f"{strategy_label} — SL ₹{SL_RUPEES} ({sl_pct:.1f}%), Target {TARGET_PCT_OF_PREMIUM}%.\n"
                f"PAPER Trade: {trade_status} — वेळ: {now.strftime('%H:%M:%S')}"
            )
            send_telegram_message(message)
            return f"{symbol}: 🎯 {level_type} {level_price:.2f} ({move_pct}% गती) -> {strategy_label} PAPER trade {trade_status}"

    return f"{symbol}: कुठलाही SRv2 level (पुरेशी गती + One-Touch सह) पात्र ठरला नाही"


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
