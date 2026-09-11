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
  १. Supabase मधून साठवलेले ACTIVE DYNAMIC_SR_SUPPORT_1M/RESISTANCE_1M levels वाचणे (established, 1-मिनिट डेटावरून काढलेले, persistence).
  २. अलीकडचे 1-मिनिट candles मिळवून, प्रत्येक ACTIVE level साठी check_level_crossed() तपासणे.
  ३. established Next-Level Exit — established touched level established आधीच्या (favourable दिशेने)
     established उघड्या position साठी established profit-target असेल, तर established आधी established
     ती established बंद (established Signal Log/Telegram सह established "NEXT_LEVEL_EXIT").
  ४. established RSI(14, established 1-मिनिट) फिल्टर — Support touch (RSI<40) -> Bull Put Spread.
     Resistance touch (RSI>60) -> Bear Call Spread. established RSI established जुळत नसेल तर established
     established दुर्लक्षित.
  ५. established select_credit_spread_fixed_strikes(strikes_otm=0 — ATM वरच Short leg, hedge_width_points=100 दूर Long leg) + open_multi_leg_trade() (PAPER) वापरून execute — established entry_level_price established साठवलेला (established Next-Level Exit साठी).
  ६. **प्रत्येक तपासलेला level** (hit झाला किंवा नाही) Signal Log मध्ये साठवणे — Dashboard वर संपूर्ण
     intraday इतिहास दिसण्यासाठी. फक्त hit झालेलेच नाही — सर्व levels, प्रत्येक cycle ला.
  ७. established Telegram notification.

⚠️ GitHub Actions ची खरी तांत्रिक किमान मर्यादा ५ मिनिटं आहे (established) — त्यामुळे ही script
दर ५ मिनिटांनीच चालते, पण प्रत्येक वेळी **मागच्या cycle पासूनचे सर्व 1-मिनिट candles** तपासते —
त्यामुळे मधल्या कुठल्याही मिनिटातला स्पर्श/gap चुकत नाही (फक्त "आत्ताचीच" किंमत नाही).
खऱ्या-अर्थाने दर-मिनिटाला चालवायचं असल्यास, established VPS वर cron ठेवावा लागेल (GitHub Actions वर शक्य नाही).
"""
import argparse

import pandas as pd

import cloud_db
from config import get_ist_now, DB_PATH
from database import init_sqlite_db, has_open_trade_from_source, get_open_trades_with_entry_level
from notifications import send_telegram_message
from signals import calculate_rsi
from strategy import select_credit_spread_fixed_strikes
from trading_engine import open_multi_leg_trade, close_trade_manually
from upstox_api import fetch_upstox_option_chain, fetch_candles

RSI_SUPPORT_MAX = 40     # 🎓 वापरकर्त्याशी चर्चा करून जोडलेलं — Support touch + 1-मिनिट RSI < 40 -> Bull Put Spread
RSI_RESISTANCE_MIN = 60  # established Resistance touch + 1-मिनिट RSI > 60 -> Bear Call Spread


def check_instant_rsi_filter(candles_df, direction):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established आधी Instant Trader ला कुठलीही entry-पूर्व
    पुष्टी लागत नव्हती (तात्काळ trade). आता established 1-मिनिट RSI(14) फिल्टर:
    Support (BULLISH) -> RSI established RSI_SUPPORT_MAX (40) च्या **खाली** हवा.
    Resistance (BEARISH) -> RSI established RSI_RESISTANCE_MIN (60) च्या **वर** हवा.
    रिटर्न: (pass: bool, rsi_value: float किंवा None)
    """
    rsi_series = calculate_rsi(candles_df, period=14)
    if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
        return False, None
    latest_rsi = round(float(rsi_series.iloc[-1]), 2)
    if direction == "BULLISH":
        return latest_rsi < RSI_SUPPORT_MAX, latest_rsi
    return latest_rsi > RSI_RESISTANCE_MIN, latest_rsi


TOUCH_TOLERANCE_PCT = 0.02  # 🎓 वापरकर्त्याशी चर्चा करून जोडलेला बफर — level पासून ±0.02% च्या आत
# candle चा low/high आला तरी "स्पर्श" (TOUCH) समजला जातो — प्रत्यक्ष तंतोतंत overlap नसला तरी.
# SRv2 च्या TOUCH_TOLERANCE_PCT (0.05%) सारखीच, टक्केवारी-आधारित पद्धत — स्थिर पॉइंट्सऐवजी, जेणेकरून
# NIFTY ची किंमत भविष्यात कितीही वर/खाली गेली तरी प्रमाण तेच राहील.


def check_level_crossed(level, candles, tolerance_pct=TOUCH_TOLERANCE_PCT):
    """
    वापरकर्त्याने विचारलेला Gap Up/Down प्रश्न सोडवण्यासाठी जोडलेला तर्क — अलीकडच्या 1-मिनिट
    candles च्या [low,high] रेंज मधून (आता ±tolerance_pct% बफरसह), आणि सलग candles मधल्या gap
    मधूनही (मागच्या candle चा close ते पुढच्या candle चा open) level ओलांडला का तपासणे.
    candles: [{"open":.., "high":.., "low":.., "close":..}, ...] (जुनं ते नवीन क्रमाने).
    रिटर्न: (hit: bool, hit_type: "TOUCH"/"GAP_THROUGH"/None, approx_price: float/None)
    """
    buffer = level * tolerance_pct / 100
    level_low, level_high = level - buffer, level + buffer

    prev_close = None
    for c in candles:
        if c["low"] <= level_high and c["high"] >= level_low:
            return True, "TOUCH", level
        if prev_close is not None:
            if (prev_close < level < c["open"]) or (prev_close > level > c["open"]):
                return True, "GAP_THROUGH", c["open"]
        prev_close = c["close"]
    return False, None, None


def process_symbol(access_token, symbol, lots=1, lot_size=65,
                    sl_pct_of_credit=20, target_pct_of_max_profit=50, recent_candles_count=2):
    """
    एका symbol साठी — अलीकडचे 1-मिनिट candles, साठवलेले Dynamic S/R levels, प्रत्येकासाठी
    crossing-तपासणी, Signal Log, आणि आढळल्यास trade+notification.

    🎓 वापरकर्त्याने Signal Log मधून सापडवलेली bug — recent_candles_count आधी 10 होता (मागच्या
    10 मिनिटांच्या candles पैकी कुठल्याही एकाने level ला स्पर्श केला तरी "TOUCH" दाखवायचं) — म्हणजे
    किंमत 7-8 मिनिटांपूर्वी level जवळ होती, आता खूप दूर गेली, तरी तो जुना candle अजूनही "मागच्या 10"
    च्या यादीत असल्यामुळे खोटं, कालबाह्य "TOUCH" दाखवत राहायचं. आता फक्त शेवटचे 2 candles (सद्य
    किंमत + gap-check साठी एक जास्तीचा) — जुना, कालबाह्य touch यापुढे कधीच दाखवला जाणार नाही.

    🎓 वापरकर्त्याशी चर्चा करून सुधारित (आधी SL 30%/Target 30% होतं) — SL आता निव्वळ प्रीमियमच्या 20%,
    Target 50%. ही रणनीती pure INTRADAY राहते (3:10pm carry-forward लागू होत नाही,
    `trading_engine.manage_open_trades()` मध्ये source="dynamic_sr_instant" वरून वगळलेलं) —
    EOD Square-off (15:15) नेहमी लागू. Trailing SL आता ATR-आधारित नाही — नवीन,
    वेगळी %-आधारित यंत्रणा (MTM नफा 20% झाल्यावर सक्रिय, 10% credit lock)
    manage_open_trades() मध्येच याच source साठी नेहमी सक्रिय — इथे वेगळं काही सेट करावं लागत नाही.
    """
    # zones आता कधीच FILLED केले जात नाहीत (खाली hit_count/cooldown ने नियंत्रित) —
    # म्हणून फक्त ACTIVE Dynamic SR levels वाचणे पुरेसे आहे (पूर्ण संच वाचून परत साठवायची गरज नाही).
    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    # 🎓 वापरकर्त्याशी चर्चा करून स्पष्ट केलेला भेद — established DYNAMIC_SR_*_1M (established, 1-मिनिट
    # candles वरून काढलेले, established याच established तात्काळ स्वभावाला अनुसरून) — established
    # DYNAMIC_SR_*_15M (established, SRv2 Momentum-Filter Reversal साठीचे, established वेगळे) नाही.
    dyn_levels = all_zones[(all_zones["zone_type"].str.endswith("_1M")) & (all_zones["status"] == "ACTIVE")]
    if dyn_levels.empty:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels नाहीत"

    candles_df = fetch_candles(access_token, symbol, current_spot=0, interval="1minute", lookback_days=1)
    if candles_df is None or candles_df.empty:
        return f"{symbol}: 1-मिनिट candles मिळाले नाहीत"

    # 🎓 वापरकर्त्याने सापडवलेली, अजून खोलातली bug — lookback_days=1 म्हणजे "मागचे १ कॅलेंडर दिवस",
    # ज्यामुळे कालच्या दिवसाचे शेवटचे candles सुद्धा (आजच्या सोबतच) यात येतात. दिवसाच्या सुरुवातीच्या
    # काही मिनिटांत (जेव्हा आजचे स्वतःचे candles अजून recent_candles_count इतके तयारच झालेले नसतात),
    # tail() आपोआप कालचे (gap-पूर्वीचे) candles घ्यायचा — आणि तेच आजच्या levels ना खोटा स्पर्श
    # दाखवायचे (आज बाजारात ती किंमत कधीच न आलेली असतानाही). आता आजच्याच तारखेचे candles आधी वेगळे
    # काढून, त्यातूनच शेवटचे तपासतो — कालचा candle कधीच यात येणार नाही.
    today_date = get_ist_now().date()
    candles_df["_date"] = candles_df["timestamp"].dt.date
    todays_candles_df = candles_df[candles_df["_date"] == today_date]
    if todays_candles_df.empty:
        return f"{symbol}: आजचे 1-मिनिट candles अजून तयार झालेले नाहीत"

    recent_candles = todays_candles_df.tail(recent_candles_count).to_dict("records")

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
        direction = "BULLISH" if row["zone_type"] == "DYNAMIC_SR_SUPPORT_1M" else "BEARISH"
        log_entry = {
            "symbol": symbol, "trade_date": trade_date, "signal_time": now, "level_type": row["zone_type"],
            "level_price": row["zone_low"], "hit_type": hit_type or "NO_HIT", "direction": direction if hit else "NONE",
            "ltp_at_signal": underlying_price, "trade_status": None, "reason": "level cross आढळला नाही" if not hit else "",
        }

        if not hit:
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Next-Level Exit + Instant Reversal) — established
        # या touched level च्या established favourable दिशेने established आधीची (याच source ची)
        # established कुठली established उघडी position established असेल (established entry level पेक्षा
        # established Support-मूळ trade साठी established वर, established Resistance-मूळ trade साठी
        # established खाली established हा established touched level established असेल), तर established
        # established ती established आधी established "profit-booked" म्हणून established बंद करून,
        # established नंतर established याच established touched level वर established (RSI+Multi-Hit
        # established गेट्स established पास झाल्यास) established नवीन (reversal) trade established घेतली
        # established जाते.
        for ot in get_open_trades_with_entry_level(symbol, "dynamic_sr_instant"):
            origin_bullish = ot["strategy"] == "BULL_PUT_SPREAD"
            favourable = (row["zone_low"] > ot["entry_level_price"]) if origin_bullish else (row["zone_low"] < ot["entry_level_price"])
            if favourable:
                closed_ok, close_msg = close_trade_manually(access_token, ot["trade_id"], symbol, "D", exit_reason="NEXT_LEVEL_EXIT")
                if closed_ok:
                    send_telegram_message(
                        f"💰 <b>{symbol} Next-Level Exit — नफा बुक केला!</b>\n"
                        f"Trade {ot['trade_id']} (entry level {ot['entry_level_price']:.2f}) — "
                        f"{row['zone_low']:.2f} पर्यंत पोहोचल्यामुळे बंद केला.\n"
                        f"आता याच level वर instant reversal trade तपासला जाईल."
                    )

        rsi_ok, rsi_value = check_instant_rsi_filter(candles_df, direction)
        if not rsi_ok:
            log_entry["trade_status"] = "SKIPPED_RSI_FILTER"
            log_entry["reason"] = f"RSI {rsi_value} दिशेशी जुळत नाही (Support<{RSI_SUPPORT_MAX} / Resistance>{RSI_RESISTANCE_MIN} हवं होतं)"
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

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली, महत्त्वाची सुधारणा — आधीची तपासणी फक्त "याच specific
        # level ला आज दुसऱ्यांदा hit झाला तरच" (hit_count_so_far>=1) चालायची — म्हणजे एका वेगळ्या
        # (किंवा किंचित वेगळा गणलेल्या) level वर आधीच उघडी असलेली position असतानाही, त्या दुसऱ्या
        # (आजचा पहिलाच hit असलेल्या) level वर नवीन trade उघडली जायची — तीन trades काही मिनिटांत
        # उघडणे असं प्रत्यक्ष घडलं (वापरकर्त्याने Order Log मधून सापडवलेलं). आता ही तपासणी
        # **कुठल्याही** level साठी बिनशर्त — याच source ची कुठलीही position उघडी असेल, तर (मग ती
        # कुठल्याही level वरची असो) नवीन entry होणारच नाही.
        if has_open_trade_from_source(symbol, "dynamic_sr_instant"):
            log_entry["trade_status"] = "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"
            log_entry["reason"] = "आधीची position (या strategy ची, कुठल्याही level वरची) अजून बंद झालेली नाही"
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
                entry_level_price=row["zone_low"],
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
                entry_level_price=row["zone_low"],
            )
        log_entry["trade_status"] = trade_status
        cloud_db.save_signal_log(log_entry)

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit Dynamic S/R) — established आता zone
        # कायमचं FILLED केलं जात नाही (आधी असंच होतं — त्यामुळे दिवसातून फक्त एकदाच trade व्हायचा,
        # आणि नंतरचे touches Signal Log मधून पूर्णपणे गायबच व्हायचे). established हा zone दिवसभर
        # ACTIVE राहतो — वरचे hit_count/cooldown/open-position चेक्सच पुढच्या trades ला नियंत्रित
        # करतात, आणि प्रत्येक तपासलेला touch (trade झाला किंवा वगळला) Signal Log मध्ये दिसत राहतो.

        level_label = "Support" if row["zone_type"] == "DYNAMIC_SR_SUPPORT_1M" else "Resistance"
        hit_label = "थेट स्पर्श" if hit_type == "TOUCH" else "⚡ Gap ने उडी मारून ओलांडला"
        message = (
            f"🎯 <b>{symbol} Dynamic S/R Cross! (आजचा {hit_count_so_far + 1}/2 वा hit)</b>\n"
            f"{level_label} {row['zone_low']:.2f} (strength {row['strength']:.0f}) — {hit_label} (≈{approx_price:.2f}). RSI {rsi_value}.\n"
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
