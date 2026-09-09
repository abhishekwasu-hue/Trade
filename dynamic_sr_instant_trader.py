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
  ४. established select_credit_spread_fixed_strikes(strikes_otm=0 — ATM वरच Short leg, hedge_width_points=100 दूर Long leg) + open_multi_leg_trade() (PAPER) वापरून execute.
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
from database import init_sqlite_db, has_open_trade_from_source
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
                    sl_pct_of_credit=20, target_pct_of_max_profit=50, recent_candles_count=10):
    """
    एका symbol साठी — अलीकडचे 1-मिनिट candles, साठवलेले Dynamic S/R levels, प्रत्येकासाठी
    crossing-तपासणी, Signal Log, आणि आढळल्यास trade+notification.

    🎓 वापरकर्त्याशी चर्चा करून सुधारित (आधी SL 30%/Target 30% होतं) — SL आता निव्वळ प्रीमियमच्या 20%,
    Target 50%. ही रणनीती established pure INTRADAY राहते (3:10pm carry-forward लागू होत नाही,
    established `trading_engine.manage_open_trades()` मध्ये source="dynamic_sr_instant" वरून वगळलेलं) —
    established EOD Square-off (15:15) नेहमी लागू. Trailing SL आता established ATR-आधारित नाही — नवीन,
    वेगळी %-आधारित यंत्रणा (MTM नफा 20% झाल्यावर सक्रिय, 10% credit lock) established
    manage_open_trades() मध्येच याच source साठी नेहमी सक्रिय — इथे वेगळं काही सेट करावं लागत नाही.
    """
    # established zones आता कधीच FILLED केले जात नाहीत (खाली hit_count/cooldown ने नियंत्रित) —
    # म्हणून फक्त ACTIVE Dynamic SR levels वाचणे पुरेसे आहे (पूर्ण संच वाचून परत साठवायची गरज नाही).
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
    for _, row in dyn_levels.iterrows():
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

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit Dynamic S/R) — established एकच zone
        # दिवसातून जास्तीत जास्त २ वेळा trade करू शकतो — पण दोन्ही अटी पाळून: (अ) established आधीच्या
        # hit पासून किमान ३० मिनिटांचं अंतर (cooldown — किंमत त्याच पातळीजवळ लगेच पुन्हा घुटमळत असेल
        # तर उगाच वारंवार trade नको), आणि (ब) established आधीची (या symbol साठी established याच
        # source ची) position आधीच बंद (CLOSED) झालेली असावी — दोन trades एकाच वेळी उघडे राहू नयेत.
        hit_count_so_far, last_hit_time = cloud_db.get_zone_hits_today(symbol, row["zone_low"], trade_date)

        if hit_count_so_far >= 2:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = "आजच्या या zone साठी established कमाल 2 वेळा मर्यादा आधीच गाठलेली"
            cloud_db.save_signal_log(log_entry)
            continue

        if last_hit_time is not None:
            elapsed_minutes = (now - last_hit_time).total_seconds() / 60
            if elapsed_minutes < 30:
                log_entry["trade_status"] = "SKIPPED_COOLDOWN_30MIN"
                log_entry["reason"] = f"मागच्या hit ला फक्त {elapsed_minutes:.1f} मिनिटं झालीत (established किमान 30 हवीत)"
                cloud_db.save_signal_log(log_entry)
                continue

        if hit_count_so_far >= 1 and has_open_trade_from_source(symbol, "dynamic_sr_instant"):
            log_entry["trade_status"] = "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"
            log_entry["reason"] = "established आधीची position अजून बंद झालेली नाही"
            cloud_db.save_signal_log(log_entry)
            continue

        # --- Level Crossed! तात्काळ Trade (कुठलीही पुष्टी न घेता) ---
        # 🎓 वापरकर्त्याशी चर्चा करून सुधारित — Short leg आता ATM वरच (strikes_otm=0, आधी डीफॉल्ट ATM±2
        # होतं) — हेज (Long leg) अजूनही established hedge_width_points (डीफॉल्ट 100) दूर. यामुळे
        # established SRv2 (जो ATM±1 वापरतो) शी strike-collision चा धोकाही आपोआप कमी होतो.
        strategy_result = select_credit_spread_fixed_strikes(raw_chain, direction, atm_strike, strikes_otm=0)
        if strategy_result is None:
            log_entry["trade_status"] = "STRATEGY_SELECTION_FAILED"
            cloud_db.save_signal_log(log_entry)
            continue

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
                sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_max_profit,
                product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                sl_pct_of_credit=sl_pct_of_credit, source="dynamic_sr_instant",
            )
            trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
            if factory_errors:
                trade_status += " | वगळलेले: " + "; ".join(factory_errors)
        else:
            trade_result, trade_status = open_multi_leg_trade(
                access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
                sl_pct_of_max_loss=None, target_pct_of_max_profit=target_pct_of_max_profit,
                product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                sl_pct_of_credit=sl_pct_of_credit, source="dynamic_sr_instant",
            )
        log_entry["trade_status"] = trade_status
        cloud_db.save_signal_log(log_entry)

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit Dynamic S/R) — established आता zone
        # कायमचं FILLED केलं जात नाही (आधी असंच होतं — त्यामुळे दिवसातून फक्त एकदाच trade व्हायचा,
        # आणि नंतरचे touches Signal Log मधून पूर्णपणे गायबच व्हायचे). established हा zone दिवसभर
        # ACTIVE राहतो — वरचे hit_count/cooldown/open-position चेक्सच पुढच्या trades ला नियंत्रित
        # करतात, आणि प्रत्येक तपासलेला touch (trade झाला किंवा वगळला) Signal Log मध्ये दिसत राहतो.

        level_label = "Support" if row["zone_type"] == "DYNAMIC_SR_SUPPORT" else "Resistance"
        hit_label = "थेट स्पर्श" if hit_type == "TOUCH" else "⚡ Gap ने उडी मारून ओलांडला"
        message = (
            f"🎯 <b>{symbol} Dynamic S/R Cross! (आजचा {hit_count_so_far + 1}/2 वा hit)</b>\n"
            f"{level_label} {row['zone_low']:.2f} (strength {row['strength']:.0f}) — {hit_label} (≈{approx_price:.2f}).\n"
            # 🎓 वापरकर्त्याने Dashboard export मधून सापडवलेली bug — established इतर strategies प्रमाणेच
            # strategy_result ची key "strategy" आहे, "strategy_type" नाही (ती key कधीच अस्तित्वातच
            # नव्हती) — त्यामुळे हा .get() नेहमी फक्त established fallback (direction) दाखवायचा.
            f"PAPER Trade: {strategy_result.get('strategy', direction)} — {trade_status}\n"
            f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        outcomes.append(f"{level_label} {row['zone_low']:.2f} ({hit_type}) -> PAPER trade {trade_status}")

    if not outcomes:
        return f"{symbol}: सद्य 1-मिनिट candles मध्ये कुठलाही साठवलेला Dynamic S/R level cross झाला नाही"
    return f"{symbol}: 🎯 " + "; ".join(outcomes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    args = parser.parse_args()

    init_sqlite_db()
    cloud_db.init_cloud_table()
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)
    for symbol in args.symbols.split(","):
        print(process_symbol(token, symbol.strip()))
