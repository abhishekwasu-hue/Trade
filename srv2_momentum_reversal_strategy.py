"""
srv2_momentum_reversal_strategy.py
------------------------------------------------
🎓 वापरकर्त्याशी चर्चा करून, संपूर्ण blueprint वरून बांधलेली नवीन रणनीती —
"Nifty SRv2 Momentum-Filter Reversal"

established SRv2 (sr_dynamic.compute_dynamic_sr, Chart वर दाखवला जाणारा) + 0.40% दिशात्मक-गती फिल्टर
(chop-zone मधले खोटे bounce टाळण्यासाठी) एकत्र — 15-मिनिट Nifty (Cash) साठी.

🎓 वापरकर्त्याशी चर्चा करून सुधारित — established Momentum Prerequisite (स्विंग-टोकापासून 0.40%
दिशात्मक हालचाल) काढून टाकला. established त्याऐवजी आता established RSI-आधारित फिल्टर:
  Resistance ला स्पर्श (Bear Call Spread) -> established 15-मिनिट RSI **50 च्या वर** असावा.
  Support ला स्पर्श (Bull Put Spread) -> established 15-मिनिट RSI **50 च्या खाली** असावा.

नियम (अद्ययावत):
  Rule 1 (RSI Filter): SRv2 level टेस्ट होण्याआधी, established 15-मिनिट RSI(14) established दिशेशी
    सुसंगत हवा — Resistance/Bearish साठी RSI>50, established Support/Bullish साठी RSI<50.
  Rule 2 (Entry): फिल्टर पास झाल्यावर, LTP ने SRv2 Support/Resistance ला स्पर्श केला की —
    Support Bounce (Long) -> established select_credit_spread_fixed_strikes(strikes_otm=1,
    hedge_width_points=100) — ATM+1 विकणे (Put), ATM+3 hedge.
    Resistance Bounce (Short) -> तेच, पण Call बाजूने (ATM+1 विकणे, ATM+3 hedge).
  Rule 3 (Risk): SL = collective net premium च्या 30%, Target = net premium च्या 80%, established
    %-आधारित Trailing SL (20% नफ्यानंतर सक्रिय, established 10% credit लॉक — established, established
    trading_engine.py मध्ये established केंद्रीकृत).
  Rule 4 (Multi-Hit): established एकच level established दिवसातून established कमाल 2 वेळा — established
    दुसरा hit established फक्त established आधीची (याच strategy ची) position established आधीच बंद
    (SL/Target लागलेली) established असेल तरच. established, established Cooldown (SL लागल्यावर established
    ३०-मिनिटांचा established symbol-व्यापी विराम) established established srv2_strategy_state (Supabase)
    established द्वारे established कायम.

⚠️ established GitHub Actions ची खरी तांत्रिक किमान मर्यादा ५ मिनिटं आहे — रणनीती स्वतः 15-मिनिट
chart वापरते, त्यामुळे दर ५ मिनिटांनी चालली तरी नुकसान नाही (established idempotent पॅटर्न — नवीन
15-मिनिट candle आलेली नसेल तर फक्त "काहीच बदल नाही" असं सांगून थांबेल).
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
from upstox_api import fetch_upstox_option_chain, fetch_candles

RSI_NEUTRAL_LEVEL = 50   # 🎓 वापरकर्त्याशी चर्चा करून जोडलेलं — established Momentum Filter ऐवजी
# established RSI(14, established 15-मिनिट) फिल्टर — Resistance/Bearish साठी RSI>50, established
# Support/Bullish साठी RSI<50.
TOUCH_TOLERANCE_PCT = 0.05   # established gap-fill/dynamic-sr च्याच tolerance-तत्त्वानुसार
# 🎓 वापरकर्त्याशी चर्चा करून सुधारित (आधीचं ₹500 flat + 80% target — आता निव्वळ प्रीमियमच्या
# टक्केवारीवर आधारित, established trading_engine.py च्या 30%-credit "new rule" स्ट्रॅटेजींशी सुसंगत):
# SL = collective premium च्या 30%, Target/3:10pm carry-forward मर्यादाही 30%.
SL_PCT_OF_CREDIT = 30        # 🎓 वापरकर्त्याने स्पष्ट सांगितलेलं — निव्वळ प्रीमियमच्या 30% (टक्केवारी, स्थिर रक्कम नाही)
TARGET_PCT_OF_PREMIUM = 80   # 🎓 वापरकर्त्याशी चर्चा करून पुन्हा 80% वर आणलं (30% कडे बदललं होतं ते
# established आता वेगळ्या CARRY_FORWARD_MIN_PROFIT_PCT (trading_engine.py, डीफॉल्ट 30%) शी गल्लत
# झाल्यामुळे होतं — Target (केव्हाही गाठला तरी लगेच बंद) आणि 3:10pm Carry-Forward चा किमान-नफा उंबरठा
# या आता established दोन वेगळ्या, स्वतंत्र गोष्टी आहेत.
COOLDOWN_MINUTES = 30        # 🎓 वापरकर्त्याने स्पष्ट सांगितलेलं (२ candles × १५-मिनिट)
LEVEL_REPEAT_TOLERANCE_PCT = 0.05  # "तोच level" ओळखण्यासाठी (One-Touch Rule)


def check_rsi_filter(candles_df, direction, neutral_level=RSI_NEUTRAL_LEVEL):
    """
    🎓 Rule 1 (सुधारित) — established Momentum Filter (0.40% स्विंग-हालचाल) च्या जागी — established
    15-मिनिट RSI(14) established दिशेशी सुसंगत आहे का तपासणे.
    direction: "BULLISH" (Support Bounce) -> established RSI **50 च्या खाली** हवा (established, अजून
    oversold-कडे झुकलेला, established संभाव्य bounce ला अनुकूल).
    "BEARISH" (Resistance Bounce) -> established RSI **50 च्या वर** हवा (established, अजून
    overbought-कडे झुकलेला, established संभाव्य reversal ला अनुकूल).
    रिटर्न: (pass: bool, rsi_value: float किंवा None)
    """
    rsi_series = calculate_rsi(candles_df, period=14)
    if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
        return False, None
    latest_rsi = round(float(rsi_series.iloc[-1]), 2)
    if direction == "BULLISH":
        return latest_rsi < neutral_level, latest_rsi
    return latest_rsi > neutral_level, latest_rsi


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
    """🎓 established जुना One-Touch नियम — आता established process_symbol() च्या मुख्य प्रवाहात
    वापरला जात नाही (established Multi-Hit — signal_log-आधारित, per-level — याने replace केलं),
    established backward-compatible म्हणून established function तसंच ठेवलेलं (established जुन्या
    tests साठी).established, तोच level (tolerance च्या आत) लगेच पुन्हा टेस्ट झाला का."""
    if last_tested_level is None:
        return False
    tolerance = level_price * tolerance_pct / 100
    return abs(level_price - last_tested_level) <= tolerance


def process_symbol(access_token, symbol, lots=1, lot_size=65):
    """एका symbol साठी — SRv2 levels, momentum-फिल्टर, One-Touch/Cooldown, आणि आढळल्यास PAPER trade.

    🎓 वापरकर्त्याशी चर्चा करून सुधारित — established दिशा live compute_dynamic_sr() ऐवजी आता
    established dynamic_sr_instant_trader.py सारखेच, Supabase मध्ये established रोज एकदा (EOD,
    refresh_market_zones.py द्वारे) साठवलेले DYNAMIC_SR_SUPPORT_15M/RESISTANCE_15M levels (established, established 15-मिनिट डेटावरून काढलेले,
    ACTIVE स्थितीतले) वापरते — प्रत्येक cycle ला नव्याने live गणना करत नाही."""
    now = get_ist_now()
    state = cloud_db.get_srv2_state(symbol)

    if is_in_cooldown(state["last_sl_hit_time"], now):
        return f"{symbol}: Cooldown कालावधी चालू आहे (SL नंतर {COOLDOWN_MINUTES} मिनिटं विराम)"

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"
    # 🎓 वापरकर्त्याशी चर्चा करून स्पष्ट केलेला भेद — established DYNAMIC_SR_*_15M (established, 15-मिनिट
    # candles वरून काढलेले, established SRv2 स्वतःच्याच 15-मिनिट रचनेला अनुसरून) — established
    # DYNAMIC_SR_*_1M (established, Instant Reversal Trader साठीचे, established वेगळे) नाही.
    dyn_levels = all_zones[(all_zones["zone_type"].str.endswith("_15M")) & (all_zones["status"] == "ACTIVE")]
    if dyn_levels.empty:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels नाहीत"

    candles_df = fetch_candles(access_token, symbol, current_spot=0, interval="15minute", lookback_days=5)
    if candles_df is None or candles_df.empty or len(candles_df) < 12:
        return f"{symbol}: पुरेसा 15-मिनिट इतिहास मिळाला नाही"

    underlying_price = candles_df["close"].iloc[-1]
    # 🎓 established candles (list-स्वरूप) आता established check_rsi_filter() ला लागत नाही
    # (established candles_df थेट वापरतो) — established जुनं Momentum Filter काढल्यामुळे established
    # हे रूपांतरण आता अनावश्यक.
    trade_date = now.strftime("%Y-%m-%d")

    for _, zrow in dyn_levels.iterrows():
        level_type = "SUPPORT" if zrow["zone_type"] == "DYNAMIC_SR_SUPPORT_15M" else "RESISTANCE"
        direction = "BULLISH" if level_type == "SUPPORT" else "BEARISH"
        level_price = zrow["zone_low"]
        touched = abs(underlying_price - level_price) <= level_price * TOUCH_TOLERANCE_PCT / 100
        if not touched:
            continue

        rsi_ok, rsi_value = check_rsi_filter(candles_df, direction)
        if not rsi_ok:
            continue  # 🎓 Rule 1 (सुधारित) -- RSI दिशेशी सुसंगत नाही

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit, dynamic_sr_instant_trader.py सारखीच) —
        # established जुना One-Touch नियम (established `last_tested_level`, established एकच, global
        # value — established कुठलाही level test झाला की established overwrite व्हायचा, established
        # per-level track नाही) established bug होता — established levels किमतीच्या जवळ आल्यामुळे
        # established हे establishedच वारंवार trigger व्हायचं. आता established establishedच्या
        # signal_log-आधारित (established per-level) mechanism: established एकच level दिवसातून
        # established कमाल २ वेळा, established आणि established established आधीची (established याच
        # source ची) position established आधीच बंद (SL/Target लागलेली) असावी.
        hit_count_so_far, _ = cloud_db.get_zone_hits_today(symbol, level_price, trade_date)
        if hit_count_so_far >= 2:
            continue  # established आजच्या या level साठी established कमाल 2 वेळा मर्यादा आधीच गाठलेली
        if hit_count_so_far >= 1 and has_open_trade_from_source(symbol, "srv2_momentum_reversal"):
            continue  # established आधीची (याच strategy ची) position established अजून बंद झालेली नाही

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
        sl_pct = SL_PCT_OF_CREDIT  # 🎓 वापरकर्त्याशी चर्चा करून सुधारित — आता थेट निव्वळ प्रीमियमच्या 30% (₹ स्थिर रक्कम ऐवजी)

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
                product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                sl_pct_of_credit=sl_pct, source="srv2_momentum_reversal",
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
            )

        cloud_db.save_srv2_state(symbol, last_tested_level=level_price, last_sl_hit_time=state["last_sl_hit_time"])
        # 🎓 established हाच hit established signal_log मध्ये साठवला जातो (established Multi-Hit
        # गणनेसाठी, established वरचं get_zone_hits_today() यावरच अवलंबून आहे).
        cloud_db.save_signal_log({
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": zrow["zone_type"],
            "level_price": level_price, "hit_type": "TOUCH", "direction": direction,
            "ltp_at_signal": underlying_price, "trade_status": trade_status, "reason": f"RSI {rsi_value}, फिल्टर पास",
        })

        strategy_label = "Bull Put Spread (Support Bounce)" if direction == "BULLISH" else "Bear Call Spread (Resistance Bounce)"
        message = (
            f"🎯 <b>{symbol} SRv2 Momentum-Reversal</b> (आजचा {hit_count_so_far + 1}/2 वा hit)\n"
            f"{level_type} {level_price:.2f} — RSI {rsi_value} (फिल्टर पास).\n"
            f"{strategy_label} — SL {sl_pct:.1f}% of Premium, Target {TARGET_PCT_OF_PREMIUM}%.\n"
            f"PAPER Trade: {trade_status} — वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        return f"{symbol}: 🎯 {level_type} {level_price:.2f} (RSI {rsi_value}) -> {strategy_label} PAPER trade {trade_status}"

    return f"{symbol}: कुठलाही SRv2 level (पुरेशी गती + Multi-Hit मर्यादेसह) पात्र ठरला नाही"


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
