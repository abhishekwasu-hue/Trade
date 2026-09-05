"""
dynamic_sr_instant_trader.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली, वाढीव High-Frequency 1-मिनिट S/R रणनीती — Chart वर दाखवला
जाणारा Dynamic S/R (strength≥2, आधीच market_zones मध्ये साठवलेला) — 1-मिनिट candles च्या [low,high]
रेंज मधून, किंवा दोन candles मधल्या gap मधून, level ओलांडला गेला की, कुठलीही candle-पुष्टी न घेता
तात्काळ PAPER Option Spread trade + Telegram + संपूर्ण Signal Log.

🎓 वापरकर्त्याने विचारलेला महत्त्वाचा प्रश्न — Market Gap Up/Down झाला (level ला कुठलाच candle प्रत्यक्ष
स्पर्श न करता, "उडी मारून" पलीकडे गेला) तर काय — आधीचं (फक्त "सद्य LTP जवळ आहे का") तपासणारं तर्क अशा
gap-मध्ये level चुकवायचं (कधीच trigger व्हायचंच नाही). आता check_level_crossed() दोन्ही परिस्थिती
हाताळतं: (अ) सरळ स्पर्श (candle च्या [low,high] च्या आत level), (ब) gap-through (मागच्या candle च्या
close आणि पुढच्या candle च्या open मध्ये level सापडला, म्हणजे उडी मारून ओलांडला गेला).

तर्क:
  १. Supabase मधून साठवलेले ACTIVE DYNAMIC_SR_SUPPORT/RESISTANCE levels वाचणे (established persistence).
  २. अलीकडचे 1-मिनिट candles मिळवून, प्रत्येक ACTIVE level साठी check_level_crossed() तपासणे.
  ३. Support cross -> Bull Put Spread. Resistance cross -> Bear Call Spread.
  ४. established select_credit_spread_fixed_strikes() + open_multi_leg_trade() (PAPER) वापरून execute.
  ५. **प्रत्येक तपासलेला level** (hit झाला किंवा नाही) Signal Log मध्ये साठवणे — Dashboard वर संपूर्ण
     intraday इतिहास दिसण्यासाठी. फक्त hit झालेलेच नाही — सर्व levels, प्रत्येक cycle ला.
  ६. Hit झालेला zone Supabase मध्ये FILLED (mitigated) करणे.
  ७. established Telegram notification.

⚠️ GitHub Actions ची खरी तांत्रिक किमान मर्यादा ५ मिनिटं आहे (established) — त्यामुळे ही script
दर ५ मिनिटांनीच चालते, पण प्रत्येक वेळी **मागच्या cycle पासूनचे सर्व 1-मिनिट candles** तपासते —
त्यामुळे मधल्या कुठल्याही मिनिटातला स्पर्श/gap चुकत नाही (फक्त "आत्ताचीच" किंमत नाही).
खऱ्या-अर्थाने दर-मिनिटाला चालवायचं असल्यास, established VPS वर cron ठेवावा लागेल (GitHub Actions वर शक्य नाही).
"""
import argparse

import cloud_db
from config import get_ist_now, DB_PATH
from database import init_sqlite_db
from notifications import send_telegram_message
from strategy import select_credit_spread_fixed_strikes
from trading_engine import open_multi_leg_trade
from upstox_api import fetch_upstox_option_chain, fetch_candles


def check_level_crossed(level, candles):
    """
    🎓 वापरकर्त्याने विचारलेला Gap Up/Down प्रश्न सोडवण्यासाठी जोडलेला तर्क — अलीकडच्या 1-मिनिट
    candles च्या [low,high] रेंज मधून, आणि सलग candles मधल्या gap मधूनही (मागच्या candle चा close ते
    पुढच्या candle चा open) level ओलांडला का तपासणे.
    candles: [{"open":.., "high":.., "low":.., "close":..}, ...] (जुनं ते नवीन क्रमाने).
    रिटर्न: (hit: bool, hit_type: "TOUCH"/"GAP_THROUGH"/None, approx_price: float/None)
    """
    prev_close = None
    for c in candles:
        if c["low"] <= level <= c["high"]:
            return True, "TOUCH", level
        if prev_close is not None:
            if (prev_close < level < c["open"]) or (prev_close > level > c["open"]):
                return True, "GAP_THROUGH", c["open"]
        prev_close = c["close"]
    return False, None, None


def process_symbol(access_token, symbol, lots=1, lot_size=65,
                    sl_pct_of_credit=30, target_pct_of_max_profit=30, recent_candles_count=10):
    """
    एका symbol साठी — अलीकडचे 1-मिनिट candles, साठवलेले Dynamic S/R levels, प्रत्येकासाठी
    crossing-तपासणी, Signal Log, आणि आढळल्यास trade+notification.
    """
    # 🎓 save_market_zones() संपूर्ण symbol चे zones "replace" करतो (फक्त Dynamic SR नाही) —
    # म्हणून एक zone FILLED करायचं असेल तरी, आधी *सर्व* zones (सर्व प्रकार, ACTIVE+FILLED दोन्ही)
    # वाचावे लागतात, मगच योग्य तो एकच row अद्ययावत करून, पूर्ण संच परत साठवायचा.
    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    dyn_levels = all_zones[(all_zones["zone_type"].str.startswith("DYNAMIC_SR")) & (all_zones["status"] == "ACTIVE")]
    if dyn_levels.empty:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels नाहीत"

    candles_df = fetch_candles(access_token, symbol, current_spot=0, interval="1minute", lookback_days=1)
    if candles_df is None or candles_df.empty:
        return f"{symbol}: 1-मिनिट candles मिळाले नाहीत"
    recent_candles = candles_df.tail(recent_candles_count).to_dict("records")

    raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol)
    if not raw_chain:
        return f"{symbol}: Option chain मिळाली नाही ({chain_status})"
    underlying_price = raw_chain[0].get("underlying_spot_price")
    atm_strike = round(underlying_price / 50) * 50
    now = get_ist_now()
    trade_date = now.strftime("%Y-%m-%d")

    outcomes = []
    zones_changed = False
    for idx, row in dyn_levels.iterrows():
        hit, hit_type, approx_price = check_level_crossed(row["zone_low"], recent_candles)

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — hit झाला किंवा नाही, प्रत्येक तपासलेला level
        # Signal Log मध्ये साठवणे (Dashboard वर संपूर्ण intraday इतिहास दिसण्यासाठी).
        direction = "BULLISH" if row["zone_type"] == "DYNAMIC_SR_SUPPORT" else "BEARISH"
        log_entry = {
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": row["zone_type"],
            "level_price": row["zone_low"], "hit_type": hit_type or "NO_HIT", "direction": direction if hit else "NONE",
            "ltp_at_signal": underlying_price, "trade_status": None, "reason": "level cross आढळला नाही" if not hit else "",
        }

        if not hit:
            cloud_db.save_signal_log(log_entry)
            continue

        # --- Level Crossed! तात्काळ Trade (कुठलीही पुष्टी न घेता) ---
        strategy_result = select_credit_spread_fixed_strikes(raw_chain, direction, atm_strike)
        if strategy_result is None:
            log_entry["trade_status"] = "STRATEGY_SELECTION_FAILED"
            cloud_db.save_signal_log(log_entry)
            continue

        trade_result, trade_status = open_multi_leg_trade(
            access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_max_profit,
            product_type="NRML", trading_mode="PAPER", trading_style="INTRADAY",
            sl_pct_of_credit=sl_pct_of_credit, source="dynamic_sr_instant",
        )
        log_entry["trade_status"] = trade_status
        cloud_db.save_signal_log(log_entry)

        # --- हाच zone आता "mitigated" (FILLED) -- बाकी सर्व zones जसेच्या तसे ठेवून ---
        all_zones.loc[idx, "status"] = "FILLED"
        zones_changed = True

        level_label = "Support" if row["zone_type"] == "DYNAMIC_SR_SUPPORT" else "Resistance"
        hit_label = "थेट स्पर्श" if hit_type == "TOUCH" else "⚡ Gap ने उडी मारून ओलांडला"
        message = (
            f"🎯 <b>{symbol} Dynamic S/R Cross!</b>\n"
            f"{level_label} {row['zone_low']:.2f} (strength {row['strength']:.0f}) — {hit_label} (≈{approx_price:.2f}).\n"
            f"PAPER Trade: {strategy_result.get('strategy_type', direction)} — {trade_status}\n"
            f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        outcomes.append(f"{level_label} {row['zone_low']:.2f} ({hit_type}) -> PAPER trade {trade_status}")

    if zones_changed:
        cloud_db.save_market_zones(all_zones, symbol)

    if not outcomes:
        return f"{symbol}: सद्य 1-मिनिट candles मध्ये कुठलाही साठवलेला Dynamic S/R level cross झाला नाही"
    return f"{symbol}: 🎯 " + "; ".join(outcomes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    args = parser.parse_args()

    init_sqlite_db()
    cloud_db.init_cloud_table()
    for symbol in args.symbols.split(","):
        print(process_symbol(args.token, symbol.strip()))
