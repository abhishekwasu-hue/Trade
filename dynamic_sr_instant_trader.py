"""
dynamic_sr_instant_trader.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली रणनीती — Chart वर दाखवला जाणारा Dynamic S/R (strength≥2,
आधीच market_zones मध्ये साठवलेला) — LTP ने त्या level ला स्पर्श केला की, कुठलीही candle-पुष्टी न
घेता (आपल्याच Gap-Fill "Instant" logic सारखं), तात्काळ PAPER Option Spread trade.

तर्क:
  १. Supabase मधून साठवलेले ACTIVE DYNAMIC_SR_SUPPORT/RESISTANCE levels वाचणे (refresh_market_zones.py
     ने आधीच साठवलेले — इथे पुन्हा गणना होत नाही, established persistence पॅटर्न).
  २. सद्य LTP त्यातल्या कुठल्या level च्या tolerance_pct% च्या आत आहे का तपासणे.
  ३. Support hit -> Bull Put Spread (bounce अपेक्षा). Resistance hit -> Bear Call Spread (rejection अपेक्षा).
  ४. established select_credit_spread_fixed_strikes() + open_multi_leg_trade() (source="dynamic_sr_instant",
     trading_mode="PAPER") वापरून execute.
  ५. तो zone Supabase मध्ये FILLED (mitigated) करणे — पुन्हा त्याच levels वर वारंवार trade होऊ नये.
  ६. established Telegram (notifications.py) + trades-log द्वारे Dashboard वर दिसणारी सूचना.
"""
import argparse

import cloud_db
from config import get_ist_now, DB_PATH
from database import init_sqlite_db
from notifications import send_telegram_message
from strategy import select_credit_spread_fixed_strikes
from trading_engine import open_multi_leg_trade
from upstox_api import fetch_upstox_option_chain


def check_level_hit(ltp, level, level_type, tolerance_pct=0.1):
    """
    🎓 established gap-fill च्याच tolerance-तत्त्वानुसार — LTP ने Dynamic S/R level ला स्पर्श केला का.
    Support -> BUY दिशा (bounce), Resistance -> SELL दिशा (rejection).
    """
    tolerance = level * tolerance_pct / 100
    if abs(ltp - level) > tolerance:
        return None
    return "BULLISH" if level_type == "DYNAMIC_SR_SUPPORT" else "BEARISH"


def process_symbol(access_token, symbol, tolerance_pct=0.1, lots=1, lot_size=65,
                    sl_pct_of_credit=30, target_pct_of_max_profit=30):
    """एका symbol साठी — सद्य LTP, साठवलेले Dynamic S/R levels, hit-तपासणी, आणि आढळल्यास trade+notification."""
    # 🎓 save_market_zones() संपूर्ण symbol चे zones "replace" करतो (फक्त Dynamic SR नाही) —
    # म्हणून एक zone FILLED करायचं असेल तरी, आधी *सर्व* zones (सर्व प्रकार, ACTIVE+FILLED दोन्ही)
    # वाचावे लागतात, मगच योग्य तो एकच row अद्ययावत करून, पूर्ण संच परत साठवायचा.
    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    dyn_levels = all_zones[(all_zones["zone_type"].str.startswith("DYNAMIC_SR")) & (all_zones["status"] == "ACTIVE")]
    if dyn_levels.empty:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels नाहीत"

    raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol)
    if not raw_chain:
        return f"{symbol}: Option chain मिळाली नाही ({chain_status})"
    underlying_price = raw_chain[0].get("underlying_spot_price")
    atm_strike = round(underlying_price / 50) * 50

    for idx, row in dyn_levels.iterrows():
        direction = check_level_hit(underlying_price, row["zone_low"], row["zone_type"], tolerance_pct)
        if direction is None:
            continue

        # --- Level Hit! तात्काळ Trade (कुठलीही पुष्टी न घेता) ---
        strategy_result = select_credit_spread_fixed_strikes(raw_chain, direction, atm_strike)
        if strategy_result is None:
            continue

        trade_result, trade_status = open_multi_leg_trade(
            access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_max_profit,
            product_type="NRML", trading_mode="PAPER", trading_style="INTRADAY",
            sl_pct_of_credit=sl_pct_of_credit, source="dynamic_sr_instant",
        )

        # --- हाच zone आता "mitigated" (FILLED) -- बाकी सर्व zones जसेच्या तसे ठेवून, संपूर्ण संच परत साठवणे ---
        all_zones.loc[idx, "status"] = "FILLED"
        cloud_db.save_market_zones(all_zones, symbol)

        level_label = "Support" if row["zone_type"] == "DYNAMIC_SR_SUPPORT" else "Resistance"
        message = (
            f"🎯 <b>{symbol} Dynamic S/R Hit!</b>\n"
            f"{level_label} {row['zone_low']:.2f} (strength {row['strength']:.0f}) ला LTP={underlying_price:.2f} ने स्पर्श केला.\n"
            f"PAPER Trade: {strategy_result.get('strategy_type', direction)} — {trade_status}\n"
            f"वेळ: {get_ist_now().strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        return f"{symbol}: 🎯 {level_label} {row['zone_low']:.2f} hit -> PAPER trade {trade_status}"

    return f"{symbol}: सद्य LTP ({underlying_price}) कुठल्याही साठवलेल्या Dynamic S/R level च्या जवळ नाही"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    parser.add_argument("--tolerance-pct", type=float, default=0.1)
    args = parser.parse_args()

    init_sqlite_db()
    for symbol in args.symbols.split(","):
        print(process_symbol(args.token, symbol.strip(), tolerance_pct=args.tolerance_pct))
