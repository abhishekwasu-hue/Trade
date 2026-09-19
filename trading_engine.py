"""Trade execution and lifecycle management: open/close positions (LIVE + PAPER), SL/Target/EOD/OI-reversal exits, broker reconciliation."""
import datetime
import json
import sqlite3
import time
import uuid

import cloud_db

from config import DB_PATH, get_ist_now, get_ist_today
from database import (
    log_orders_batch, get_todays_live_total_pnl_and_count, get_open_trades_by_other_sources,
    get_unverified_reconciled_trades_today_count,
)
from upstox_api import (
    execute_order_leg_set, fetch_ltp_map, fetch_ltp_map_detailed, fetch_broker_positions,
    extract_order_ids, get_instrument_key, get_available_margin, fetch_required_margin,
)
from oi_analysis import get_latest_oi_signal, check_oi_diff_entry_gate, infer_direction_from_strategy

# 🎓 वापरकर्त्याशी चर्चा करून वेगळं काढलेलं — established Target (प्रत्येक strategy चा स्वतःचा
# target_pct_of_max_profit, उदा. SRv2 साठी 80%) आणि established 3:10pm Carry-Forward साठी "किमान
# इतका नफा असायलाच हवा" हा उंबरठा — या दोन वेगळ्या गोष्टी आहेत. established सर्व "new rule" strategies
# (BULL_PUT_SPREAD/BEAR_CALL_SPREAD/IRON_CONDOR/IRON_BUTTERFLY, dynamic_sr_instant वगळता) साठी सामायिक.
from log_setup import get_logger

_logger = get_logger("trading_engine.py")

CARRY_FORWARD_MIN_PROFIT_PCT = 30

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` (1-मिनिट Instant Reversal) साठी
# SL/Target आता प्रीमियमवर नाही, underlying स्पॉट किमतीच्या हालचालीवर आधारित —
# entry-वेळचा S/R level (entry_level_price) पासून favourable/adverse दिशेने
# स्पॉट किती % हलला, त्यावरून. जुना प्रीमियम-आधारित SL(20%)/
# Target(50%)/%-Trailing या source साठी पूर्णपणे बदलला — आता
# लागू established होत नाही.
DYNAMIC_SR_SPOT_SL_PCT = 0.05
DYNAMIC_SR_SPOT_TARGET_PCT = 0.20

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — स्पॉट-आधारित SL/Target सोबतच, निव्वळ प्रीमियम-आधारित
# SL/Target (Trailing सह) — दोन्ही एकत्र, जे आधी घडेल ते लागू. Trailing चे activation/lock % हे
# चर्चेत स्पष्ट सांगून ठरवलेलं गृहीतक आहे (SRv2 च्या 20%/10% पॅटर्नशी सुसंगत, पण या घट्ट 10%/25%
# च्या प्रमाणात छोटं केलेलं).
DYNAMIC_SR_PREMIUM_SL_PCT = 10
DYNAMIC_SR_PREMIUM_TARGET_PCT = 25
DYNAMIC_SR_PREMIUM_TRAILING_ACTIVATION_PCT = 10
DYNAMIC_SR_PREMIUM_TRAILING_LOCK_PCT = 5

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` साठी EOD आता 15:00 (इतर
# strategies साठीचा डीफॉल्ट 15:15 तसाच, फक्त या source साठी वेगळा, आधीचा).
DYNAMIC_SR_EOD_HOUR = 15
DYNAMIC_SR_EOD_MINUTE = 0

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Classical Support/Resistance Reversal" (नवीन,
# स्वतंत्र तिसरी strategy, 5M+15M pooled — backtest आधी, चांगले निकाल दिसल्यावर PAPER trading) —
# dynamic_sr_instant सारखाच EOD उंबरठा (15:00).
CLASSIC_SR_EOD_HOUR = 15
CLASSIC_SR_EOD_MINUTE = 0

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — SRv2 Momentum-Reversal (15M/30M/60M एकत्र) साठी
# नवीन exit-रचना — Spot SL(0.10%, entry_level_price पासून) + Premium Target (जुनाच, 80% —
# target_level column मधूनच) + Next-Level-Exit (15M/30M/60M पूल केलेले) — जे आधी घडेल ते लागू.
# जुनी %-Trailing SL आणि 3:10pm Carry-Forward — या source साठी पूर्णपणे काढलेले.
SRV2_SPOT_SL_PCT = 0.10

def reconcile_positions(access_token, symbol):
    """
    स्थानिक DB मधील OPEN (LIVE) ट्रेड्सची तुलना Upstox कडील खऱ्या पोझिशन्सशी करून विसंगती शोधणे —
    उदा. तुम्ही Upstox app मधून manually एखादी पोझिशन बंद केली, तर हा सिस्टीम अजूनही 'OPEN' समजत राहील,
    चुकीचा MTM व circuit breaker मोजत राहील. फक्त LIVE ट्रेड्ससाठी लागू (PAPER ट्रेड्स प्रत्यक्ष ब्रोकरकडे नसतातच).
    """
    broker_positions = fetch_broker_positions(access_token)
    if broker_positions is None:
        return {"status": "error", "message": "Broker positions मिळाल्या नाहीत (API त्रुटी किंवा Static IP आवश्यक असू शकतो)."}

    broker_qty_map = {}
    for pos in broker_positions:
        key = pos.get("instrument_token")
        qty = pos.get("quantity", 0)
        if key:
            broker_qty_map[key] = broker_qty_map.get(key, 0) + qty

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT trade_id, legs_json, strikes_summary FROM live_trades WHERE symbol=? AND status='OPEN' AND COALESCE(mode,'LIVE')='LIVE'",
        (symbol,),
    )
    local_open = cur.fetchall()
    conn.close()

    mismatches = []
    local_keys = set()
    for trade_id, legs_json_str, strikes_summary in local_open:
        legs = json.loads(legs_json_str) if legs_json_str else []
        for leg in legs:
            key = leg.get("instrument_key")
            local_keys.add(key)
            broker_qty = broker_qty_map.get(key, 0)
            if broker_qty == 0:
                mismatches.append({
                    "trade_id": trade_id, "strikes_summary": strikes_summary, "leg_role": leg.get("role"),
                    "instrument_key": key,
                })

    # उलट दिशा — Broker कडे उघडी पोझिशन आहे, पण त्या instrument_key शी संबंधित कोणताही स्थानिक OPEN trade नाही.
    # (instrument_token हा अनेकदा अपारदर्शक अंकी key असतो, त्यामुळे हे symbol-निहाय फिल्टर करता येत नाही —
    # खाली दिसणाऱ्या सर्व नोंदी या app शी संबंधित नसतीलही, ते युजरने स्वतः पडताळावं.)
    unexplained_broker_positions = [
        {"instrument_key": key, "quantity": qty}
        for key, qty in broker_qty_map.items() if qty != 0 and key not in local_keys
    ]

    return {
        "status": "ok", "mismatches": mismatches, "unexplained_broker_positions": unexplained_broker_positions,
        "checked_at": get_ist_now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def normalize_legs(strategy_result):
    """कोणत्याही स्ट्रॅटेजी रिझल्टला (2-leg स्प्रेड, 4-leg कंडोर/बटरफ्लाय, किंवा Naked/Naked+Hedge)
    समान legs-list स्वरूपात आणणे.
    🎓 वापरकर्त्याने Order Book वरून सापडवलेली bug — "ltp" (entry-वेळचा प्रीमियम) आधी इथेच
    गाळला जायचा (2-leg स्प्रेड साठी) — म्हणजे Order Book च्या "Price" column ला (जो
    MARKET order request चा price=0 दाखवतो, कारण MARKET order ला limit price नसतोच) दाखवायला
    प्रत्यक्ष entry किंमतच उपलब्ध नव्हती. आता "ltp" (उपलब्ध असल्यास) पुढे नेलं जातं.
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Naked Option Trade / "Long With Hedge") —
    "buy_leg" (hedge नसलेला निव्वळ खरेदी) आणि "buy_leg"+"hedge_leg" (hedge सक्रिय केलेला debit
    स्प्रेड) दोन्ही स्वरूपं ओळखली जातात.
    🎓 वापरकर्त्याने विचारलेला प्रश्न ("Order Log मध्ये strike/expiry कळतच नाही") सोडवण्यासाठी —
    प्रत्येक leg मध्ये आता "option_type" (CE/PE) आणि "expiry" सुद्धा (उपलब्ध असल्यास) पुढे नेले जातात."""
    if "legs" in strategy_result:
        return strategy_result["legs"]
    if "buy_leg" in strategy_result:
        legs = [
            {"role": "naked_buy", "strike": strategy_result["buy_leg"]["strike"],
             "instrument_key": strategy_result["buy_leg"]["instrument_key"], "transaction_type": "BUY",
             "ltp": strategy_result["buy_leg"].get("ltp"), "option_type": strategy_result["buy_leg"].get("option_type"),
             "expiry": strategy_result["buy_leg"].get("expiry")},
        ]
        if "hedge_leg" in strategy_result:
            legs.append(
                {"role": "naked_hedge", "strike": strategy_result["hedge_leg"]["strike"],
                 "instrument_key": strategy_result["hedge_leg"]["instrument_key"], "transaction_type": "SELL",
                 "ltp": strategy_result["hedge_leg"].get("ltp"), "option_type": strategy_result["hedge_leg"].get("option_type"),
                 "expiry": strategy_result["hedge_leg"].get("expiry")},
            )
        return legs
    return [
        {"role": "long_hedge", "strike": strategy_result["long_leg"]["strike"],
         "instrument_key": strategy_result["long_leg"]["instrument_key"], "transaction_type": "BUY",
         "ltp": strategy_result["long_leg"].get("ltp"), "option_type": strategy_result["long_leg"].get("option_type"),
         "expiry": strategy_result["long_leg"].get("expiry")},
        {"role": "short_leg", "strike": strategy_result["short_leg"]["strike"],
         "instrument_key": strategy_result["short_leg"]["instrument_key"], "transaction_type": "SELL",
         "ltp": strategy_result["short_leg"].get("ltp"), "option_type": strategy_result["short_leg"].get("option_type"),
         "expiry": strategy_result["short_leg"].get("expiry")},
    ]

def _auto_reverse_filled_legs(access_token, adapter, resp, trading_mode, product_type, symbol):
    """
    🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Partial-Leg Failure Handling) —
    Multi-leg ऑर्डर मधला काही legs भरले, काही अयशस्वी झाले (resp["status"]=="partial_failure",
    upstox_api.py च्या Order Fill Verification वरून) — तर उरलेला "अर्धवट" (unhedged, नुसता naked)
    भाग शक्य तितक्या लवकर, स्वयंचलितपणे, जे भरले तेच legs उलट दिशेने (SELL<->BUY, MARKET) बंद
    (square-off) करतो — आणि Telegram वर नेहमी कळवतो (यशस्वी झालं किंवा अयशस्वी, दोन्ही स्थितीत
    वापरकर्त्याला कळायलाच हवं). कुठलाही trade live_trades मध्ये साठवला जात नाही (मूळ, हेतू असलेली
    position कधीच पूर्णपणे उभी राहिलीच नाही) — फक्त order_log मध्ये (log_orders_batch द्वारे)
    reversal-प्रयत्नाची नोंद.
    """
    from notifications import send_telegram_message
    filled_legs = [
        leg for leg in resp.get("verified_legs", [])
        if leg.get("status") == "complete" and leg.get("instrument_token") and leg.get("quantity")
    ]
    if not filled_legs:
        try:
            send_telegram_message(
                f"🔴 <b>{symbol} — Multi-leg ऑर्डर पूर्णपणे अयशस्वी</b> — एकही leg भरला गेला नाही. "
                "कुठलीही उघडी position तयार झालेली नाही."
            )
        except Exception:
            _logger.exception("_auto_reverse_filled_legs() मध्ये अनपेक्षित चूक (silently handled)")
        return

    reversal_orders = [
        {
            "quantity": leg["quantity"], "product": leg.get("product") or product_type, "validity": "DAY", "price": 0,
            "tag": "AUTO_REVERSE_PARTIAL", "instrument_token": leg["instrument_token"],
            "order_type": "MARKET",
            "transaction_type": ("SELL" if leg.get("transaction_type") == "BUY" else "BUY"),
            "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False,
            "correlation_id": uuid.uuid4().hex[:20],
        }
        for leg in filled_legs
    ]
    reversal_status, reversal_resp = (adapter.execute_order_leg_set(reversal_orders, trading_mode) if adapter is not None
                                       else execute_order_leg_set(access_token, reversal_orders, trading_mode))
    reversal_ok = reversal_status == 200 and reversal_resp.get("status") == "success"
    legs_desc = ", ".join(leg["instrument_token"] for leg in filled_legs)

    try:
        reversal_order_ids = extract_order_ids(reversal_resp) if isinstance(reversal_resp, dict) else []
        log_orders_batch(
            reversal_order_ids, f"AUTO_REVERSE_{int(time.time())}", symbol, trading_mode, reversal_orders,
            status="COMPLETE" if reversal_ok else "FAILED",
        )
    except Exception:
        _logger.exception("_auto_reverse_filled_legs() मध्ये अनपेक्षित चूक (silently handled)")

    try:
        if reversal_ok:
            send_telegram_message(
                f"🟠 <b>{symbol} — Multi-leg ऑर्डर अंशतः अयशस्वी</b> — {len(filled_legs)} leg(s) भरले होते "
                f"({legs_desc}), बाकीचे अयशस्वी. आपोआप उलट ऑर्डर टाकून ते बंद (square-off) केले — ✅ यशस्वी."
            )
        else:
            send_telegram_message(
                f"🔴 <b>{symbol} — गंभीर! Multi-leg ऑर्डर अंशतः अयशस्वी, आणि आपोआप बंद करण्याचा प्रयत्नही अयशस्वी!</b>\n"
                f"उघडे legs: {legs_desc}\nकृपया तात्काळ Upstox app/website उघडून स्वतः बंद करा."
            )
    except Exception:
        _logger.exception("_auto_reverse_filled_legs() मध्ये अनपेक्षित चूक (silently handled)")


def check_kill_switch():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit,
    गंभीर यादीतला चौथा मुद्दा) — आजचा एकूण LIVE realized P&L किंवा trade-count (सर्व symbols/bots
    मिळून, cloud_db.get_kill_switch_settings() च्या मर्यादेपलीकडे) तपासतो. PAPER trades कधीच
    अडवले जात नाहीत — फक्त LIVE (खरे पैसे) साठीच हा संरक्षक. रिटर्न: (ok: bool, reason: str|None)."""
    settings = cloud_db.get_kill_switch_settings()
    if not settings.get("enabled", True):
        return True, None
    # 🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — reconciliation ने externally
    # बंद केलेल्या trades चा realized_pnl कधीच कळत नाही (NULL राहतो), त्यामुळे तो तोटा वरच्या SUM
    # मध्ये कधीच धरलाच जात नाही — "आजचा तोटा ₹0" चुकीने दिसू शकतो, ज्या दिवशी खरंच मोठा तोटा झालेला
    # असेल त्याच दिवशी. अंदाजे आकडा गृहीत धरण्यापेक्षा, अशा वेळी नवीन LIVE trading थांबवणंच सुरक्षित.
    unverified_count = get_unverified_reconciled_trades_today_count()
    if unverified_count > 0:
        return False, (
            f"KILL_SWITCH_UNVERIFIED_PNL — आज {unverified_count} LIVE trade(s) Upstox app/website "
            f"वरून थेट बंद झालेल्या दिसतात, पण त्यांचा खरा नफा/तोटा अजून नोंदवलेला नाही — आजचा एकूण "
            f"तोटा अचूक मोजता येत नसल्याने नवीन LIVE trades थांबवले. कृपया Dashboard/Upstox वरून "
            f"प्रत्यक्ष स्थिती तपासून, गरज असल्यास त्या trade(s) चा realized_pnl हाताने नोंदवा."
        )
    total_pnl, total_trades = get_todays_live_total_pnl_and_count()
    max_daily_loss = settings.get("max_daily_loss", 10000)
    max_trades_per_day = settings.get("max_trades_per_day", 15)
    if total_pnl <= -max_daily_loss:
        return False, f"KILL_SWITCH_DAILY_LOSS — आजचा एकूण LIVE तोटा ₹{-total_pnl:,.0f} (मर्यादा ₹{max_daily_loss:,.0f})"
    if total_trades >= max_trades_per_day:
        return False, f"KILL_SWITCH_MAX_TRADES — आजचे एकूण LIVE ट्रेड्स {total_trades} (मर्यादा {max_trades_per_day})"
    return True, None


def _alert_kill_switch_blocked(symbol, source, reason):
    """LIVE Kill Switch ट्रिप झाल्यावर, नवीन LIVE trade ब्लॉक केल्यावर Telegram अलर्ट — _alert_ltp_fetch_failure()
    सारखंच, cooldown नाही (गंभीर, पैशांशी संबंधित स्थिती असल्याने दर वेळी सूचना देणं चुकून दुर्लक्षित
    होण्यापेक्षा जास्त सुरक्षित)."""
    try:
        from notifications import send_telegram_message
        send_telegram_message(
            f"🛑 <b>{symbol} ({source}) — LIVE Kill Switch सक्रिय!</b>\n"
            f"{reason}\n"
            f"हा नवीन LIVE ट्रेड ब्लॉक केला गेला (PAPER trades वर परिणाम नाही). Bot Dynamic SR Algo "
            f"पानावरून Kill Switch सेटिंग्ज तपासा/रीसेट करा."
        )
    except Exception:
        _logger.exception("_alert_kill_switch_blocked() मध्ये अनपेक्षित चूक (silently handled)")


def check_margin_available(access_token, adapter, orders, strategy_result, lots, lot_size):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Margin Check in Bots, गंभीर यादीतला
    सहावा मुद्दा) — page_dashboard.py च्या Strategy Builder मध्ये आधीपासूनच असलेला हाच Pre-Trade
    Margin Check (Upstox चं अधिकृत Margin Calculator API, hedge-फायद्यासकट; अचूक API नसेल — उदा.
    Fyers — तर max_loss-आधारित सुरक्षित worst-case अंदाज) आता 3 bots + trading_engine.py च्या इतर
    सर्व LIVE कॉल्ससाठीही, या एकाच choke-point (open_multi_leg_trade()) मधून लागू. उपलब्ध मार्जिन
    तपासताच आली नाही (adapter/API कडून None), तर Dashboard प्रमाणेच सावधपणे पुढे जाऊ देतो (block
    करत नाही) — फक्त खरंच अपुरी मार्जिन स्पष्ट दिसली, तरच block. रिटर्न: (ok: bool, reason: str|None)."""
    if adapter is not None:
        required_margin = adapter.get_required_margin(orders)
        available_margin = adapter.get_funds()
    else:
        required_margin = fetch_required_margin(access_token, orders)
        available_margin = get_available_margin(access_token)

    if required_margin is None:
        required_margin = abs(strategy_result["max_loss"]) * lots * lot_size

    if available_margin is None:
        return True, None  # तपासताच आली नाही -- Dashboard प्रमाणेच सावधपणे पुढे जाऊ देतो, block नाही
    if available_margin < required_margin:
        return False, (
            f"MARGIN_INSUFFICIENT — आवश्यक ₹{required_margin:,.0f}, उपलब्ध ₹{available_margin:,.0f} "
            f"(तूट ₹{required_margin - available_margin:,.0f})"
        )
    return True, None


def _alert_margin_insufficient(symbol, source, reason):
    """अपुऱ्या मार्जिनमुळे LIVE trade ब्लॉक झाल्यावर Telegram अलर्ट — इतर गंभीर अलर्ट्स सारखंच
    (Kill Switch/LTP-fetch-failure), cooldown नाही."""
    try:
        from notifications import send_telegram_message
        send_telegram_message(
            f"🟠 <b>{symbol} ({source}) — LIVE Trade अपुऱ्या मार्जिनमुळे ब्लॉक!</b>\n"
            f"{reason}\n"
            f"Broker account मध्ये मार्जिन वाढवा, किंवा lots/strategy कमी करा."
        )
    except Exception:
        _logger.exception("_alert_margin_insufficient() मध्ये अनपेक्षित चूक (silently handled)")


def _alert_cross_strategy_conflict(symbol, source, strategy_result, other_source_trades):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Cross-Strategy Conflict Check — फक्त अलर्ट, block नाही,
    वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय) — याच symbol वर आधीच दुसऱ्या strategy(-strategies) ची
    OPEN position असताना नवीन LIVE trade उघडलं जातंय, हे कळवणं — trade अडवला जात नाही, निर्णय
    वापरकर्त्याकडेच (कदाचित मुद्दामच वेगवेगळ्या दिशेने diversify करायचं असेल)."""
    try:
        from notifications import send_telegram_message
        others_desc = "; ".join(f"{t['source']} ({t['strategy']})" for t in other_source_trades)
        send_telegram_message(
            f"⚠️ <b>{symbol} — Cross-Strategy Overlap!</b>\n"
            f"नवीन trade: {source} ({strategy_result.get('strategy', '?')})\n"
            f"आधीच उघड्या (इतर strategies): {others_desc}\n"
            f"दोन्ही एकाच underlying वर — margin/एकत्रित जोखीम स्वतः तपासा (हे फक्त सूचना आहे, trade ब्लॉक केलेलं नाही)."
        )
    except Exception:
        _logger.exception("_alert_cross_strategy_conflict() मध्ये अनपेक्षित चूक (silently handled)")


def open_multi_leg_trade(access_token, symbol, strategy_result, lots, lot_size, sl_pct_of_max_loss, target_pct_of_max_profit, product_type, trading_mode="LIVE", trading_style="INTRADAY", sl_pct_of_credit=None, source="MANUAL", adapter=None, entry_level_price=None, entry_timeframe=None):
    """कोणतीही स्ट्रॅटेजी (2-leg क्रेडिट स्प्रेड किंवा 4-leg Iron Condor/Butterfly) उघडणे (LIVE किंवा PAPER) व DB मध्ये नोंद करणे.
    sl_pct_of_credit दिलं (Price Action/Indicator साठी, वापरकर्त्याशी चर्चा करून ठरवलेलं नवीन नियम) तर SL
    net_credit च्या % वर ठरतो (max_loss च्या % ऐवजी — Iron Condor/Butterfly साठी जुनीच पद्धत कायम).
    source — हा trade नेमका कुठून आला (उदा. 'DASHBOARD', 'credit_spread_auto_trader', 'oi_signal_auto_trader',
    'oi_greeks_vix_strategy') — Positions page वर स्पष्टपणे दाखवण्यासाठी (वापरकर्त्याशी चर्चा करून जोडलेलं).
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" — adapter (BrokerAdapter
    इन्स्टन्स) दिला असेल तर त्याच broker/account द्वारे ऑर्डर जाते (access_token फक्त trade_id/स्टोरेज
    साठी वापरला जातो); न दिल्यास, जुनं (थेट Upstox) वर्तन तसंच राहतं.
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Next-Level Exit, 1-मिनिट Instant Trader) — entry_level_price
    (ऐच्छिक) — entry-वेळचा underlying S/R level (option strike नाही) — नंतर favourable दिशेने पुढचा
    level touch झाला की profit-booking exit साठी वापरला जातो (इतर strategies साठी None, वापरलं जात नाही).
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Same-Timeframe Next-Level-Exit, 15M/30M/60M) —
    entry_timeframe (ऐच्छिक, उदा. "15M"/"30M"/"60M"/"1M"/"5M") — Next-Level-Exit साठी त्याच
    timeframe चा पुढचा level शोधण्यासाठी वापरला जातो."""
    if trading_mode == "LIVE":
        kill_switch_ok, kill_switch_reason = check_kill_switch()
        if not kill_switch_ok:
            _alert_kill_switch_blocked(symbol, source, kill_switch_reason)
            return False, {"status": "error", "reason": kill_switch_reason}

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Cross-Strategy Conflict Check) — फक्त सूचना, trade
        # कधीच अडवला जात नाही (वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय).
        other_source_trades = get_open_trades_by_other_sources(symbol, source)
        if other_source_trades:
            _alert_cross_strategy_conflict(symbol, source, strategy_result, other_source_trades)

    legs = normalize_legs(strategy_result)
    qty = lots * lot_size

    orders = [
        {
            "quantity": qty, "product": product_type, "validity": "DAY", "price": 0,
            "tag": f"A1_{leg['role'].upper()[:16]}", "instrument_token": leg["instrument_key"],
            "order_type": "MARKET", "transaction_type": leg["transaction_type"],
            "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False,
            # 🎓 वापरकर्त्याने विचारलेला प्रश्न ("Order Log मध्ये strike/expiry कळत नाही") सोडवण्यासाठी
            # जोडलेलं — leg मध्येच आधीपासून उपलब्ध असलेली माहिती इथे order-dict मध्येही पुढे नेली,
            # जेणेकरून log_order() ती प्रत्यक्ष साठवू शकेल (आधी हे कधीच पास केलं जात नव्हतं).
            "strike": leg.get("strike"), "option_type": leg.get("option_type"), "expiry": leg.get("expiry"),
            # 🎓 वापरकर्त्याने Upstox कडून सापडवलेली bug — Upstox Multi Order API ला प्रत्येक order
            # साठी `correlation_id` (unique, alphanumeric, कमाल २० अक्षरं) आता सक्तीचा आहे — नसेल तर
            # "UDAPI1115: correlation_id is required" देऊन संपूर्ण ऑर्डर नाकारतो.
            "correlation_id": uuid.uuid4().hex[:20],
        }
        for leg in legs
    ]

    if trading_mode == "LIVE":
        margin_ok, margin_reason = check_margin_available(access_token, adapter, orders, strategy_result, lots, lot_size)
        if not margin_ok:
            _alert_margin_insufficient(symbol, source, margin_reason)
            return False, {"status": "error", "reason": margin_reason}

    status_code, resp = (adapter.execute_order_leg_set(orders, trading_mode) if adapter is not None
                          else execute_order_leg_set(access_token, orders, trading_mode))
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Partial-Leg Failure Handling, गंभीर
    # यादीतला दुसरा मुद्दा) — Order Fill Verification (upstox_api.py) मुळे आता कळू शकतं की multi-leg
    # ऑर्डर मधला काही भाग भरला, काही अयशस्वी झाला (उदा. मार्जिन कमी पडलं, एक strike illiquid) —
    # असा "अर्धवट, unhedged" भाग तसाच उघडा राहू देणं सर्वात धोकादायक. लगेच, स्वयंचलितपणे जे भरले
    # तेच legs उलट दिशेने बंद (square-off) करतो, आणि Telegram वर कळवतो (यशस्वी किंवा अयशस्वी दोन्ही
    # स्थितीत). PAPER mode/इतर brokers (जिथे verification अजून लागू नाही) साठी resp["status"] कधीच
    # "partial_failure" येणार नाही — त्यामुळे हे पूर्णपणे additive, फक्त Upstox LIVE साठीच सक्रिय.
    if resp.get("status") == "partial_failure":
        _auto_reverse_filled_legs(access_token, adapter, resp, trading_mode, product_type, symbol)
    if status_code != 200 or resp.get("status") != "success":
        return False, resp

    order_ids = extract_order_ids(resp)
    # 🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — इथे आधी फक्त
    # lot_size नेच गुणलं जायचं, lots ने नाही. पण manage_open_trades() मधला current_pnl
    # (exit-वेळी प्रत्यक्ष तुलना होणारा) नेहमी `* lots * lot_size` असतो (बघा वरचा
    # net_credit_total, ओळ ~741). त्यामुळे lots>1 असेल, तर SL/Target रकमेत lots गुणलाच जायचा नाही
    # — म्हणजे intended रकमेच्या फक्त 1/lots इतक्याच हालचालीवर SL/Target लगेच trigger व्हायचा
    # (उदा. lots=3 → SL तिप्पट लवकर, Target तिप्पट लवकर) — जितके lots जास्त, तितकी चूक मोठी.
    max_loss_total = strategy_result["max_loss"] * lots * lot_size
    # 🎓 Naked Option (hedge नसलेला buy) साठी max_profit=None असतो (theoretically
    # unbounded — strategy.py.select_naked_option_itm() बघा) — None * lots क्रॅश व्हायचा, आणि तो
    # क्रॅश प्रत्यक्ष order Upstox कडे गेल्यानंतर, database मध्ये trade साठवण्याआधी व्हायचा — म्हणजे
    # खरा पैसा गेलेला, पण bot ला त्या trade चं अस्तित्वच माहीत नाही (SL/Target/EOD काहीच लागू होत
    # नाही). आता None सुरक्षितपणे हाताळला जातो — max_profit_total/target_pnl_level दोन्ही None
    # राहतात (unbounded-profit trade साठी % target गणिताला अर्थच नाही — SL/Trailing-SL/EOD अजूनही
    # लागू होतातच, फक्त निश्चित profit-target नाही).
    max_profit_total = (strategy_result["max_profit"] * lots * lot_size) if strategy_result["max_profit"] is not None else None
    net_credit_total = strategy_result["net_credit"] * lots * lot_size
    if sl_pct_of_credit is not None:
        # 🎓 Naked Option साठी net_credit ऋण (debit, buy_leg["ltp"] इतका) असतो,
        # Credit Spread साठी धन (credit) — abs() शिवाय naked trades साठी sl_pnl_level
        # चुकून धन यायचा, त्यामुळे entry नंतर लगेचच (कुठलीही खरी किंमत-हालचाल
        # न होताच) SL trigger व्हायचा (current_pnl <= sl_pnl_level
        # पहिल्याच तपासणीलाच खरं ठरायचं). आता abs() मुळे दोन्ही केसेससाठी SL
        # पातळी नेहमी योग्य ऋण (तोटा) असते.
        sl_pnl_level = -(abs(net_credit_total) * (sl_pct_of_credit / 100.0))
    else:
        sl_pnl_level = -(max_loss_total * (sl_pct_of_max_loss / 100.0))
    target_pnl_level = (max_profit_total * (target_pct_of_max_profit / 100.0)) if max_profit_total is not None else None
    strikes_summary = " · ".join(f"{leg['role']}:{leg['strike']:.0f}" for leg in legs)

    trade_id = f"{'PAPER' if trading_mode == 'PAPER' else symbol}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    # 🎓 वापरकर्त्याने Order Book वरून सापडवलेली bug — established MARKET orders चा request price
    # नेहमी 0 असतो (limit price नसतोच) — established प्रत्यक्ष entry किंमत (प्रत्येक leg चं "ltp"/
    # "premium", established strategy_result मधून) इथे वेगळी पाठवली जाते.
    entry_fill_prices = {
        leg["instrument_key"]: (leg.get("ltp") if leg.get("ltp") is not None else leg.get("premium"))
        for leg in legs
    }
    log_orders_batch(order_ids, trade_id, symbol, trading_mode, orders, status="COMPLETE", fill_prices=entry_fill_prices)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO live_trades
           (trade_id, trade_date, symbol, strategy, short_strike, long_strike, short_instrument, long_instrument,
            lots, lot_size, net_credit, max_profit, max_loss, sl_pnl_level, target_pnl_level,
            entry_time, exit_time, exit_reason, realized_pnl, status, short_order_id, long_order_id,
            legs_json, strikes_summary, mode, trading_style, source, account_id, entry_level_price, entry_timeframe)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            trade_id, get_ist_today().strftime("%Y-%m-%d"), symbol, strategy_result["strategy"],
            None, None, None, None,
            # 🎓 वापरकर्त्याने Dashboard export मधून सापडवलेली bug — established net_credit column
            # नेहमीच "per-share" (lot_size/lots ने न गुणलेला) साठवला जायचा — पण max_profit/max_loss
            # चुकून आधीच lot_size ने गुणलेले (max_profit_total/max_loss_total, "एका lot चा total")
            # साठवले जायचे. established database.py चा Positions/CSV display फॉर्म्युला तिन्ही column
            # सारखेच (per-share) गृहीत धरून `* lots * lot_size` करतो — त्यामुळे max_loss/max_profit
            # प्रत्यक्षात lot_size ने **दुसऱ्यांदा** गुणले जायचे (उदा. Iron Condor चा खरा max_loss
            # ₹6,655 ऐवजी ₹367,575 सारखा भलताच मोठा दिसायचा). आता established net_credit प्रमाणेच,
            # दोन्ही per-share (strategy_result मधलं मूळ, न गुणलेलं मूल्य) साठवलं जातं.
            lots, lot_size, strategy_result["net_credit"], strategy_result["max_profit"], strategy_result["max_loss"],
            sl_pnl_level, target_pnl_level,
            get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), None, None, None, "OPEN",
            None, None,
            json.dumps(legs), strikes_summary, trading_mode, trading_style, source,
            adapter.get_account_id() if adapter is not None else None,
            entry_level_price, entry_timeframe,
        ),
    )
    inserted = cur.rowcount > 0
    conn.commit()
    conn.close()
    if not inserted:
        # अत्यंत दुर्मिळ केस — uuid suffix असूनही trade_id टक्कर झाली (जवळजवळ अशक्य, तरीही शांतपणे न सोडता कळवणे)
        return False, {"status": "error", "message": f"Trade DB मध्ये नोंदवता आला नाही (trade_id टक्कर: {trade_id}). ऑर्डर प्रत्यक्षात प्लेस झाला असेल तर Reconciliation Check चालवून तपासा."}
    return True, {"trade_id": trade_id, "order_ids": order_ids}

def compute_trailing_sl_level(current_pnl, peak_pnl, atr_points, lot_size, lots, atr_multiplier=1.5, original_sl_level=None):
    """
    ATR-आधारित Trailing SL — पोझिशन नफ्यात असताना, ATR (बाजाराच्या अस्थिरतेवर आधारित) पटीत एक अंतर
    ठेवून SL सतत नफ्याच्या दिशेने वर सरकवणे. एकदा सरकल्यावर कधीच मागे सरकत नाही (peak_pnl कधीच कमी होत
    नाही). पोझिशन कधीच नफ्यात गेलेली नसेल (peak_pnl<=0) तर ट्रेलिंग सक्रियच होत नाही — मूळ स्थिर SL तसाच
    वापरला जातो. परिणामी SL कधीच मूळ स्थिर SL पेक्षा वाईट (जास्त सैल) होणार नाही, याची खात्री केलेली आहे.
    Returns: (नवीन peak_pnl, प्रत्यक्ष वापरायचा effective_sl_level)
    """
    new_peak_pnl = max(peak_pnl, current_pnl) if peak_pnl is not None else current_pnl

    if new_peak_pnl <= 0 or atr_points is None:
        return new_peak_pnl, original_sl_level

    trailing_distance = atr_points * lot_size * lots * atr_multiplier
    trailing_sl_level = new_peak_pnl - trailing_distance

    effective_sl = trailing_sl_level if original_sl_level is None else max(original_sl_level, trailing_sl_level)
    return new_peak_pnl, effective_sl


def evaluate_point_spot_exit(
    direction_bullish, entry_spot, current_spot, premium_pnl_points,
    sl_spot_pct, sl_premium_points, tsl_spot_pct, tsl_premium_points,
    target_spot_pct, target_premium_points, tsl_already_activated,
):
    """
    वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) — Spot% आणि
    Premium-Points दोन्ही एकत्र (जे आधी घडेल ते) तपासणारं, पुनर्वापरयोग्य exit-गणित — Credit
    Spread आणि Naked Buy दोन्हींसाठी वापरता येतं.

    premium_pnl_points — आधीच योग्य चिन्हासह, प्रति-share नफा (net_credit - cost_to_close_now हेच
    सूत्र Spread आणि Naked दोन्हीसाठी बरोबर काम करतं — net_credit ऋण (debit) साठवला की Naked साठीही
    चिन्ह आपोआप बरोबर येतं, वेगळं गणित लागत नाही). धनात्मक = नफा.

    direction_bullish: True -> स्पॉट वर गेला की favourable. False -> स्पॉट खाली गेला की favourable.
    tsl_already_activated: आधीच्या cycle मध्ये TSL (Entry/Breakeven) सक्रिय झाली होती का — एकदा
    सक्रिय झाली की कायम (sticky) राहते, पुन्हा जुन्या (घट्ट नसलेल्या) SL कडे परत जात नाही.

    रिटर्न: (exit_reason: "TARGET"/"SL"/"TSL_SL"/None, tsl_now_activated: bool, detail: str|None)
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Performance Report PDF — "exact reason" मागणी) —
    तिसरा detail — Spot% विरुद्ध Premium Points यापैकी नेमकं कोणतं उंबरठा ओलांडला गेला, हे स्पष्ट
    सांगणारा वाचनीय मजकूर. exit_reason च्या पहिल्या दोन मूल्यांवर (कोड-आधारित business logic, उदा.
    `point_exit_reason != "TARGET"`) याचा **काहीही** परिणाम होत नाही — फक्त जोड आहे.
    """
    if direction_bullish:
        spot_move_pct = (current_spot - entry_spot) / entry_spot
    else:
        spot_move_pct = (entry_spot - current_spot) / entry_spot
    spot_move_display = spot_move_pct * 100

    # Target — TSL च्या स्थितीशी संबंध नाही, गाठला की केव्हाही लगेच बंद
    # 🎓 detail मुद्दाम इंग्रजीत (Marathi/Devanagari नाही) — हा stored DB मजकूर Performance Report
    # PDF मध्ये थेट दाखवला जातो, आणि PDF फॉन्ट्समध्ये (fonts/ फोल्डरमध्ये फक्त DejaVu Sans आहे,
    # Devanagari font नाही) मराठी glyphs रिकाम्या चौकोनासारखे दिसतात — म्हणून इथे इंग्रजीतच.
    target_by_spot = spot_move_pct >= target_spot_pct / 100
    target_by_premium = premium_pnl_points >= target_premium_points
    if target_by_spot or target_by_premium:
        if target_by_spot and target_by_premium:
            detail = (f"Target hit — both Spot move {spot_move_display:.2f}% (threshold {target_spot_pct}%) and "
                       f"Premium gain {premium_pnl_points:.1f} points (threshold {target_premium_points}) reached simultaneously.")
        elif target_by_spot:
            detail = (f"Target hit via Spot move — {spot_move_display:.2f}% reached/exceeded the {target_spot_pct}% threshold "
                       f"(Premium gain still at {premium_pnl_points:.1f}/{target_premium_points} points).")
        else:
            detail = (f"Target hit via Premium points — {premium_pnl_points:.1f} points reached/exceeded the {target_premium_points}-point threshold "
                       f"(Spot move still at {spot_move_display:.2f}%/{target_spot_pct}%).")
        return "TARGET", tsl_already_activated, detail

    if tsl_already_activated:
        # TSL आधीच सक्रिय — SL आता Entry/Breakeven वर घट्ट (प्रीमियम-नफा 0 किंवा त्याखाली गेला की बंद)
        if premium_pnl_points <= 0:
            detail = f"Trailing SL hit (locked to Entry/Breakeven) — Premium gain {premium_pnl_points:.1f} points dropped to/below zero."
            return "TSL_SL", True, detail
        return None, True, None

    # TSL अजून सक्रिय नाही — मूळ (सैल) SL तपासणे
    sl_by_spot = spot_move_pct <= -sl_spot_pct / 100
    sl_by_premium = premium_pnl_points <= -sl_premium_points
    if sl_by_spot or sl_by_premium:
        if sl_by_spot and sl_by_premium:
            detail = (f"Stop-Loss hit — both adverse Spot move {spot_move_display:.2f}% (threshold -{sl_spot_pct}%) and "
                       f"Premium loss {premium_pnl_points:.1f} points (threshold -{sl_premium_points}) reached simultaneously.")
        elif sl_by_spot:
            detail = (f"Stop-Loss hit via Spot move — adverse move {spot_move_display:.2f}% reached/exceeded the -{sl_spot_pct}% threshold "
                       f"(Premium loss still at {premium_pnl_points:.1f}/-{sl_premium_points} points).")
        else:
            detail = (f"Stop-Loss hit via Premium points — loss {premium_pnl_points:.1f} points reached/exceeded the -{sl_premium_points}-point threshold "
                       f"(Spot move still at {spot_move_display:.2f}%/-{sl_spot_pct}%).")
        return "SL", False, detail

    # TSL सक्रिय व्हायची अट (आता किंवा आधीपासून) पूर्ण झाली का
    tsl_now_activated = (spot_move_pct >= tsl_spot_pct / 100) or (premium_pnl_points >= tsl_premium_points)
    return None, tsl_now_activated, None


def compute_premium_trailing_floor(premium_pnl_points, peak_premium_pnl_points, trail_distance_points):
    """
    🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("user defined trailing stop loss for all
    strategies") — 3 Bot स्ट्रॅटेजींसाठी (1-Min Instant/dynamic_sr_instant, SRv2/srv2_momentum_reversal,
    Classical S/R Reversal/classic_sr_reversal) Premium-Points-आधारित *सतत* Trailing Stop.

    evaluate_point_spot_exit() मधलं मूळ TSL-to-Breakeven लॉजिक (अजूनही पूर्णपणे न बदललेलं) एकदाच
    सक्रिय झाल्यावर SL कायमचा Entry/Breakeven (0) वर अडकवतं. हे फंक्शन त्याच्या वर, पूर्णपणे स्वतंत्रपणे
    (manage_open_trades() मधून, evaluate_point_spot_exit() चं परिणाम "still open" असेल तरच) वापरलं
    जातं — TSL एकदा सक्रिय झाल्यावर, SL Breakeven ऐवजी (Peak Premium Points - trail_distance_points)
    इतका, नफा जसा वाढत जाईल तसा सतत मागे-मागे सरकत राहतो. Breakeven पेक्षा हे कधीच सैल (वाईट) होत नाही
    — कारण हे फक्त exit_reason अजून None असतानाच (म्हणजे Breakeven आधीच ओलांडला गेलेला नाही तेव्हाच)
    तपासलं जातं.

    Returns: (नवीन peak_premium_pnl_points, floor_points — याच्या खाली/बरोबर premium_pnl_points
    गेला की Trailing SL लागू व्हायला हवा)
    """
    new_peak = max(peak_premium_pnl_points or 0.0, premium_pnl_points)
    floor_points = new_peak - trail_distance_points
    return new_peak, floor_points


def compute_pct_trailing_sl_level(current_pnl, peak_pnl, net_credit_total, activation_pct=20, lock_pct=10, original_sl_level=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली, established ATR-Trailing पेक्षा वेगळी यंत्रणा — फक्त
    `dynamic_sr_instant` (1-मिनिट Instant Reversal) साठी: established ATR ऐवजी निव्वळ प्रीमियमच्या
    टक्केवारीवर आधारित —
      • MTM नफा established activation_pct (डीफॉल्ट 20%) पर्यंत पोहोचेपर्यंत काहीही होत नाही (मूळ
        स्थिर SL तसाच).
      • एकदा पोहोचला की, SL established lock_pct (डीफॉल्ट 10% credit) इतकं मागे ठेवून लगेच वर सरकतो
        (म्हणजे activation क्षणी SL = breakeven + (activation_pct - lock_pct)% इतका lock होतो).
      • पुढे नफा वाढतच राहिला, तर SL सुद्धा established lock_pct चं अंतर राखत सतत वर सरकत राहतो — कधीच
        मागे सरकत नाही (peak_pnl कधीच कमी होत नाही, established ATR आवृत्तीसारखंच).
    Returns: (नवीन peak_pnl, प्रत्यक्ष वापरायचा effective_sl_level)
    """
    new_peak_pnl = max(peak_pnl, current_pnl) if peak_pnl is not None else current_pnl

    activation_level = net_credit_total * (activation_pct / 100.0)
    if new_peak_pnl < activation_level:
        return new_peak_pnl, original_sl_level  # अजून 20% पर्यंत पोहोचलेलं नाही — मूळ स्थिर SL तसाच

    lock_amount = net_credit_total * (lock_pct / 100.0)
    trailing_sl_level = new_peak_pnl - lock_amount

    effective_sl = trailing_sl_level if original_sl_level is None else max(original_sl_level, trailing_sl_level)
    return new_peak_pnl, effective_sl


def _alert_ltp_fetch_failure(symbol, context_label, error_detail, has_live_trades):
    """
    🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Token-Expiry/LTP-Fetch Silent Failure,
    गंभीर यादीतला तिसरा मुद्दा) — आधी LTP मिळाली नाही (उदा. token expire झाला, HTTP 401) की
    manage_open_trades() फक्त शांतपणे त्या cycle साठी exit-तपासणी वगळायचं (continue) — कुठलाही
    alert नाही. उघडी LIVE position मग SL/TSL/Target शिवाय, कुणालाच न कळता, अनिश्चित काळ तशीच राहू
    शकायची. आता — फक्त LIVE trades साठीच (PAPER मध्ये खरे पैसे नाहीत, कमी तातडीचं) — नेहमी Telegram
    अलर्ट (cron दर मिनिटाला चालतो, त्यामुळे समस्या राहिली तर पुढच्याही cycle ला पुन्हा अलर्ट येईल —
    इथे मुद्दामच cooldown नाही, हीच codebase मधली established पद्धत — उदा. CLOSE ORDER FAILED अलर्ट).
    401/403 दिसल्यास टोकन-समस्या असल्याचं स्पष्टपणे सांगणारा वेगळा संदेश.
    """
    if not has_live_trades:
        return
    try:
        from notifications import send_telegram_message
        is_auth_issue = bool(error_detail) and ("401" in error_detail or "403" in error_detail)
        if is_auth_issue:
            send_telegram_message(
                f"🔴 <b>{symbol} — Upstox टोकन समस्या (Authentication अयशस्वी)!</b>\n"
                f"{context_label} साठी LTP मिळाली नाही ({error_detail}) — टोकन expire/अवैध झाला असण्याची "
                f"दाट शक्यता. LIVE positions चं SL/TSL/Target या cycle ला तपासलंच गेलं नाही. "
                f"कृपया लगेच Dashboard उघडून नवीन token approve करा."
            )
        else:
            send_telegram_message(
                f"🟠 <b>{symbol} — {context_label} LTP मिळाली नाही</b> ({error_detail or 'रिकामा प्रतिसाद'}) — "
                f"LIVE positions चं SL/TSL/Target या cycle ला तपासलंच गेलं नाही. समस्या कायम राहिल्यास लगेच तपासा."
            )
    except Exception:
        _logger.exception("_alert_ltp_fetch_failure() मध्ये अनपेक्षित चूक (silently handled)")


def manage_open_trades(access_token, symbol, product_type, eod_squareoff_hour=15, eod_squareoff_minute=15, oi_reversal_exit_enabled=False, trailing_sl_enabled=False, atr_points=None, atr_multiplier=1.5):
    """
    उघड्या (OPEN) ट्रेड्सचे (कोणत्याही leg-संख्येचे) सद्य P&L तपासून SL / Target वर आपोआप बंद करणे.
    Intraday ट्रेड्ससाठी EOD Square-off (डीफॉल्ट 15:15 IST) आपोआप लागू होतो — ब्रोकरचा MIS
    ऑटो-स्क्वेअर-ऑफ जसा असतो तसाच, जेणेकरून Intraday पोझिशन रात्रभर उघडी राहणार नाही.
    oi_reversal_exit_enabled=True असल्यास, Directional स्प्रेड्स (Bull Put / Bear Call) साठी OI Diff
    Tracker चा सिग्नल पोझिशनच्या विरोधात सक्रियपणे फिरला तर SL/Target च्या आधीच लवकर एक्झिट होतो
    (Iron Condor/Butterfly सारख्या non-directional स्ट्रॅटेजींना हे लागू होत नाही).
    trailing_sl_enabled=True असल्यास, ATR-आधारित Trailing SL सर्व स्ट्रॅटेजींना (Price Action, Indicator,
    व मूळ Credit Spreads सकट) लागू होतो — पोझिशन नफ्यात गेल्यावर SL सतत नफ्याच्या दिशेने सरकतो, कधीच
    मूळ स्थिर SL पेक्षा वाईट होत नाही. atr_points कॉलरने (caller ने) आधीच काढून द्यायचा असतो.

    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` (1-मिनिट Instant Reversal) साठी
    दोन विशेष नियम, `source` column वरून ओळखले जातात (sidebar-आधारित trailing_sl_enabled/carry-forward
    टॉगल्सपासून पूर्णपणे स्वतंत्र, कारण ही रणनीती नेहमी pure intraday राहायला हवी, इतर
    स्ट्रॅटेजींप्रमाणे carry-forward नाही):
      • 3:10pm Carry-Forward नियम या source ला लागू होत नाही (जरी strategy_name
        BULL_PUT_SPREAD/BEAR_CALL_SPREAD शी जुळत असला तरी) — नेहमी प्लेन 15:15 EOD Square-off.
      • ATR-Trailing ऐवजी नवीन %-आधारित Trailing (compute_pct_trailing_sl_level, वर) —
        MTM नफा 20% झाल्यावर सक्रिय, 10% credit lock सह — नेहमी सक्रिय (sidebar टॉगलची गरज नाही).


    🎓 वापरकर्त्याशी चर्चा करून जोडलेली, महत्त्वाची सुरक्षा-सुधारणा (Auto-Reconciliation) — दर
    cycle ला (दर मिनिटाला, cron मार्फत) प्रत्यक्ष SL/Target तपासण्याआधीच, आधी
    reconcile_open_trades_with_broker() चालवून, Upstox app/website वरून थेट बंद केलेली (पण आपल्या
    database मध्ये अजूनही "OPEN" दिसणारी) position आधीच शोधून बंद केली जाते — जेणेकरून तिच्यावर
    चुकून पुन्हा नवीन order जाऊ नये.
    """
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    past_eod_cutoff = (ist_now.hour, ist_now.minute) >= (eod_squareoff_hour, eod_squareoff_minute)
    oi_signal_latest = get_latest_oi_signal(symbol) if oi_reversal_exit_enabled else None

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुरक्षा-सुधारणा — दर cycle ला आधी Broker Reconciliation
    # (फक्त वाचतं, कुठलाही order पाठवत नाही) — Upstox app/website वरून थेट बंद केलेली position
    # आपल्या database मध्ये अजूनही "OPEN" दिसत राहू नये, आणि चुकून तिच्यावर पुन्हा नवीन order जाऊ नये.
    reconcile_open_trades_with_broker(access_token, symbol)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """SELECT trade_id, legs_json, lots, lot_size, net_credit, sl_pnl_level, target_pnl_level, mode, trading_style, strategy, peak_pnl, source, entry_level_price, tsl_activated, entry_timeframe, account_id
           FROM live_trades WHERE symbol=? AND status='OPEN'""",
        (symbol,),
    )
    open_trades = cur.fetchall()
    if not open_trades:
        conn.close()
        return []

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection) — account_id दिलेला
    # (म्हणजे हा trade निवडलेल्या broker account वर उघडलेला) असेल, तर बंद करतानाही तोच account/broker
    # वापरायला हवा (नाहीतर बंद-ऑर्डर चुकीने Upstox कडे जाईल, आणि प्रत्यक्ष position दुसऱ्याच
    # broker वर उघडीच राहील — गंभीर, खऱ्या-पैशाशी संबंधित धोका). इथेच एकदा accounts वाचून, प्रत्येक
    # distinct account_id साठी adapter cache करतो (प्रत्येक trade साठी पुन:पुन्हा resolve न करता).
    _adapter_cache = {}

    def _resolve_close_adapter(account_id):
        if account_id is None:
            return None
        if account_id not in _adapter_cache:
            import broker_factory
            adapters, _errors = broker_factory.get_adapters_for_accounts([account_id])
            _adapter_cache[account_id] = adapters[0][0] if adapters else None
        return _adapter_cache[account_id]

    parsed_trades = []
    all_keys = set()
    for (trade_id, legs_json_str, lots, lot_size, net_credit, sl_level, target_level, trade_mode, trade_style, strategy_name, peak_pnl, source, entry_level_price, tsl_activated, entry_timeframe, account_id) in open_trades:
        legs = json.loads(legs_json_str) if legs_json_str else []
        for leg in legs:
            all_keys.add(leg["instrument_key"])
        parsed_trades.append((trade_id, legs, lots, lot_size, net_credit, sl_level, target_level, trade_mode or "LIVE", trade_style or "INTRADAY", strategy_name or "", peak_pnl, source or "", entry_level_price, bool(tsl_activated), entry_timeframe, account_id))

    ltp_map = fetch_ltp_map(access_token, list(all_keys))
    if not ltp_map and all_keys:
        # 🎓 फक्त अपयशाच्या (रिकाम्या निकालाच्याच) मार्गावरच fetch_ltp_map_detailed() ला वेगळा कॉल —
        # जेणेकरून वरचा मुख्य fetch_ltp_map() कॉल (आणि त्याला monkeypatch करणाऱ्या established टेस्ट्स)
        # पूर्णपणे अबाधित राहतात, आणि यशस्वी (सामान्य) मार्गावर जादा नेटवर्क कॉलही होत नाही.
        _, ltp_error_detail = fetch_ltp_map_detailed(access_token, list(all_keys))
        has_live_trades = any(t[7] == "LIVE" for t in parsed_trades)
        _alert_ltp_fetch_failure(symbol, "Option-leg", ltp_error_detail, has_live_trades)

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` trades साठी underlying
    # स्पॉटची सद्य LTP लागते (option-leg LTPs पुरेसे नाहीत, SL/Target आता स्पॉट-आधारित). कमीत कमी
    # एक असा trade असेल तरच हा जादा fetch करणे.
    # 🎓 Trailing SL feature टेस्ट करताना सापडलेली, आधीपासूनची गंभीर bug — इथे "classic_sr_reversal"
    # गहाळ होता, म्हणजे त्या strategy चे trades कधीच त्यांच्या स्वतःच्या (Spot%+Premium-Points+TSL)
    # exit branch मध्ये पोहोचायचेच नाहीत (entry_level_price असूनही underlying_spot नेहमी None) —
    # शांतपणे चुकीच्या generic (A1/manual) exit-लॉजिककडे पडायचे. आता जोडला.
    underlying_spot = None
    if any(t[11] in ("dynamic_sr_instant", "srv2_momentum_reversal", "classic_sr_reversal") for t in parsed_trades):
        spot_key = get_instrument_key(symbol)
        spot_ltp_map = fetch_ltp_map(access_token, [spot_key])
        # 🎓 वापरकर्त्याने विचारलेला प्रश्न ("exit condition match झाली तरी exit झाला नाही") सोडवण्यासाठी
        # जोडलेली, तात्पुरती diagnostic नोंद — underlying_spot None आलं (म्हणजे संपूर्ण स्पॉट-आधारित
        # SL/Target branch वगळला जाऊन जुन्या प्रीमियम-आधारित मार्गाकडे पडेल) तर, नेमकं काय मिळालं ते
        # स्पष्ट दिसावं (उदा. Upstox च्या response मधला key आपण पाठवलेल्या "NSE_INDEX|Nifty 50" शी
        # जुळलाच नसेल, तर हेच कारण असू शकतं — पण याची अजून खात्रीशीर पडताळणी झालेली नाही).
        if not spot_ltp_map or spot_key not in spot_ltp_map:
            print(f"⚠️ underlying_spot मिळाला नाही — spot_key='{spot_key}', मिळालेला raw response: {spot_ltp_map}")
            # 🎓 इथेही फक्त अपयशाच्याच मार्गावर fetch_ltp_map_detailed() ला वेगळा कॉल (वर बघा — मुख्य
            # fetch_ltp_map() कॉल established टेस्ट्ससाठी अबाधित ठेवण्यासाठी).
            _, spot_error_detail = fetch_ltp_map_detailed(access_token, [spot_key])
            has_live_spot_trades = any(
                t[7] == "LIVE" and t[11] in ("dynamic_sr_instant", "srv2_momentum_reversal", "classic_sr_reversal")
                for t in parsed_trades
            )
            _alert_ltp_fetch_failure(symbol, "Underlying Spot", spot_error_detail, has_live_spot_trades)
        underlying_spot = spot_ltp_map.get(spot_key)

    closed_summaries = []
    for (trade_id, legs, lots, lot_size, net_credit, sl_level, target_level, trade_mode, trade_style, strategy_name, peak_pnl, source, entry_level_price, tsl_activated, entry_timeframe, account_id) in parsed_trades:
        if not legs:
            continue
        current_ltps = {leg["instrument_key"]: ltp_map.get(leg["instrument_key"]) for leg in legs}
        if any(v is None for v in current_ltps.values()):
            continue  # काही leg ची सद्य LTP मिळाली नाही — ही तपासणी पुढच्या रनला पुन्हा होईल

        # सामान्य सूत्र: मूळ SELL leg → +sign, मूळ BUY leg → -sign (entry credit आणि आताचा close-cost सुसंगत ठेवण्यासाठी)
        cost_to_close_now = sum(
            current_ltps[leg["instrument_key"]] * (1 if leg["transaction_type"] == "SELL" else -1)
            for leg in legs
        )
        current_pnl = (net_credit - cost_to_close_now) * lots * lot_size
        net_credit_total = net_credit * lots * lot_size
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Performance Report PDF) — प्रत्येक trade चं
        # Exit नेमकं कशामुळे झालं (Spot% विरुद्ध Premium Points, कोणता next level, इ.) — exit_reason
        # कोड (business logic साठी, बदलेला नाही) सोबतच, वाचनीय detail वेगळ्या column मध्ये.
        exit_reason_detail = None

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` साठी आता स्पॉट-आधारित
        # (entry_level_price पासून) आणि निव्वळ प्रीमियम-आधारित (Trailing सह) — दोन्ही एकत्र, जे आधी
        # घडेल ते लागू. (🎓 Next-Level-Exit आधी इथून पूर्णपणे काढला होता, पण वापरकर्त्याने पुन्हा
        # मागितल्यावर — फक्त 5M-touch entries साठी, Credit Spread + Naked दोन्हींसाठी — खाली परत जोडला.)
        if source == "dynamic_sr_instant" and entry_level_price is not None and underlying_spot is not None:
            # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) —
            # जुना %-आधारित SL/Target/Trailing पूर्णपणे बदलला — आता Spot% + Premium-Points combined
            # (settings-चालित, hardcode-मुक्त) — Credit Spread आणि Naked (समांतर trade-प्रकार)
            # दोन्हींसाठी, TSL-to-Entry/Breakeven (sticky) सह.
            settings_1m = cloud_db.get_strategy_settings("1m_instant", symbol)
            is_naked = strategy_name in ("NAKED_CALL", "NAKED_PUT")
            direction_bullish = strategy_name in ("BULL_PUT_SPREAD", "NAKED_CALL")
            premium_pnl_points = net_credit - cost_to_close_now

            if is_naked:
                sl_spot_pct = settings_1m["naked_sl_spot_pct"]
                sl_premium_points = settings_1m["naked_sl_premium_points"]
                tsl_spot_pct = settings_1m["naked_tsl_spot_pct"]
                tsl_premium_points = settings_1m["naked_tsl_premium_points"]
                target_spot_pct = settings_1m["naked_target_spot_pct"]
                target_premium_points = settings_1m["naked_target_premium_points"]
            else:
                sl_spot_pct = settings_1m["spread_sl_spot_pct"]
                sl_premium_points = settings_1m["spread_sl_premium_points"]
                tsl_spot_pct = settings_1m["spread_tsl_spot_pct"]
                tsl_premium_points = settings_1m["spread_tsl_premium_points"]
                target_spot_pct = settings_1m["spread_target_spot_pct"]
                target_premium_points = settings_1m["spread_target_premium_points"]

            point_exit_reason, tsl_now_activated, point_exit_detail = evaluate_point_spot_exit(
                direction_bullish, entry_level_price, underlying_spot, premium_pnl_points,
                sl_spot_pct, sl_premium_points, tsl_spot_pct, tsl_premium_points,
                target_spot_pct, target_premium_points, tsl_activated,
            )
            if tsl_now_activated != tsl_activated:
                cur.execute("UPDATE live_trades SET tsl_activated=? WHERE trade_id=?", (1 if tsl_now_activated else 0, trade_id))

            exit_reason = point_exit_reason
            exit_reason_detail = point_exit_detail

            # 🎓 वापरकर्त्याने मागितलेली सुधारणा — user-defined Premium-Points Trailing Stop
            # (settings-चालित, डीफॉल्ट बंद). TSL आधीच सक्रिय झाली असेल आणि अजून SL/Target लागलेला
            # नसेल तरच लागू — Breakeven (evaluate_point_spot_exit वरचाच) कधीच सैल केला जात नाही.
            if exit_reason is None and tsl_now_activated:
                trail_enabled = settings_1m["naked_trailing_sl_enabled"] if is_naked else settings_1m["spread_trailing_sl_enabled"]
                if trail_enabled:
                    trail_distance = settings_1m["naked_trailing_distance_points"] if is_naked else settings_1m["spread_trailing_distance_points"]
                    new_peak_premium, floor_points = compute_premium_trailing_floor(premium_pnl_points, peak_pnl, trail_distance)
                    if new_peak_premium != peak_pnl:
                        cur.execute("UPDATE live_trades SET peak_pnl=? WHERE trade_id=?", (new_peak_premium, trade_id))
                        peak_pnl = new_peak_premium
                    if premium_pnl_points <= floor_points:
                        exit_reason = "TSL_SL"
                        exit_reason_detail = (
                            f"Trailing SL hit (Premium Points trail) — Peak premium gain {new_peak_premium:.1f} pts, "
                            f"trailing distance {trail_distance:.1f} pts -> floor {floor_points:.1f} pts, now at {premium_pnl_points:.1f} pts."
                        )

            # 🎓 वापरकर्त्याने मागितलेली सुधारणा — 5M-touch एंटर झालेल्या trades साठी Next-Level-Exit
            # परत आणला (आधी पूर्णपणे काढून टाकलेला होता) — फक्त entry_timeframe=="5M" असेल तरच
            # (वापरकर्त्याने स्पष्टपणे 1M entries ला हे लागू न करण्याचं ठरवलं), Credit Spread आणि
            # Naked दोन्हींना (SRv2 च्या फक्त-Spread पद्धतीपेक्षा वेगळं), आणि SL/TSL/Target सोबतच
            # "जे आधी घडेल ते" — त्यांना पूर्णपणे बदलत नाही.
            if exit_reason is None and entry_timeframe == "5M":
                next_level = cloud_db.get_next_level_in_direction(symbol, entry_level_price, direction_bullish, timeframe_suffixes=("5M",))
                if next_level is not None:
                    reached = (underlying_spot >= next_level) if direction_bullish else (underlying_spot <= next_level)
                    if reached:
                        exit_reason = "NEXT_LEVEL_EXIT"
                        exit_reason_detail = (
                            f"Reached the next 5M S/R level (Rs {next_level:,.1f}) — profit-booked at this next level "
                            f"instead of waiting for SL/TSL/Target."
                        )

            if exit_reason is None and trade_style == "INTRADAY":
                dynamic_sr_past_eod_cutoff = (ist_now.hour, ist_now.minute) >= (DYNAMIC_SR_EOD_HOUR, DYNAMIC_SR_EOD_MINUTE)
                if dynamic_sr_past_eod_cutoff:
                    exit_reason = "EOD_SQUAREOFF"
                    exit_reason_detail = f"Auto-closed at EOD Square-off ({DYNAMIC_SR_EOD_HOUR}:{DYNAMIC_SR_EOD_MINUTE:02d}) — neither SL nor Target was hit."
        elif source == "classic_sr_reversal" and entry_level_price is not None and underlying_spot is not None:
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Classical Support/Resistance Reversal"
            # (नवीन, स्वतंत्र तिसरी strategy, 5M+15M pooled) — dynamic_sr_instant सारखीच रचना
            # (Spot%+Premium-Points+TSL-to-Breakeven, केंद्रीकृत evaluate_point_spot_exit()) — फक्त
            # वेगळ्या settings-namespace ("classic_sr_reversal") मधून, वेगळा EOD उंबरठा.
            settings_csr = cloud_db.get_strategy_settings("classic_sr_reversal", symbol)
            is_naked = strategy_name in ("NAKED_CALL", "NAKED_PUT")
            direction_bullish = strategy_name in ("BULL_PUT_SPREAD", "NAKED_CALL")
            premium_pnl_points = net_credit - cost_to_close_now

            if is_naked:
                sl_spot_pct = settings_csr["naked_sl_spot_pct"]
                sl_premium_points = settings_csr["naked_sl_premium_points"]
                tsl_spot_pct = settings_csr["naked_tsl_spot_pct"]
                tsl_premium_points = settings_csr["naked_tsl_premium_points"]
                target_spot_pct = settings_csr["naked_target_spot_pct"]
                target_premium_points = settings_csr["naked_target_premium_points"]
            else:
                sl_spot_pct = settings_csr["spread_sl_spot_pct"]
                sl_premium_points = settings_csr["spread_sl_premium_points"]
                tsl_spot_pct = settings_csr["spread_tsl_spot_pct"]
                tsl_premium_points = settings_csr["spread_tsl_premium_points"]
                target_spot_pct = settings_csr["spread_target_spot_pct"]
                target_premium_points = settings_csr["spread_target_premium_points"]

            point_exit_reason, tsl_now_activated, point_exit_detail = evaluate_point_spot_exit(
                direction_bullish, entry_level_price, underlying_spot, premium_pnl_points,
                sl_spot_pct, sl_premium_points, tsl_spot_pct, tsl_premium_points,
                target_spot_pct, target_premium_points, tsl_activated,
            )
            if tsl_now_activated != tsl_activated:
                cur.execute("UPDATE live_trades SET tsl_activated=? WHERE trade_id=?", (1 if tsl_now_activated else 0, trade_id))

            exit_reason = point_exit_reason
            exit_reason_detail = point_exit_detail

            # 🎓 वापरकर्त्याने मागितलेली सुधारणा — user-defined Premium-Points Trailing Stop
            # (settings-चालित, डीफॉल्ट बंद). 1m_instant प्रमाणेच.
            if exit_reason is None and tsl_now_activated:
                trail_enabled = settings_csr["naked_trailing_sl_enabled"] if is_naked else settings_csr["spread_trailing_sl_enabled"]
                if trail_enabled:
                    trail_distance = settings_csr["naked_trailing_distance_points"] if is_naked else settings_csr["spread_trailing_distance_points"]
                    new_peak_premium, floor_points = compute_premium_trailing_floor(premium_pnl_points, peak_pnl, trail_distance)
                    if new_peak_premium != peak_pnl:
                        cur.execute("UPDATE live_trades SET peak_pnl=? WHERE trade_id=?", (new_peak_premium, trade_id))
                        peak_pnl = new_peak_premium
                    if premium_pnl_points <= floor_points:
                        exit_reason = "TSL_SL"
                        exit_reason_detail = (
                            f"Trailing SL hit (Premium Points trail) — Peak premium gain {new_peak_premium:.1f} pts, "
                            f"trailing distance {trail_distance:.1f} pts -> floor {floor_points:.1f} pts, now at {premium_pnl_points:.1f} pts."
                        )

            if exit_reason is None and trade_style == "INTRADAY":
                classic_sr_past_eod_cutoff = (ist_now.hour, ist_now.minute) >= (CLASSIC_SR_EOD_HOUR, CLASSIC_SR_EOD_MINUTE)
                if classic_sr_past_eod_cutoff:
                    exit_reason = "EOD_SQUAREOFF"
                    exit_reason_detail = f"Auto-closed at EOD Square-off ({CLASSIC_SR_EOD_HOUR}:{CLASSIC_SR_EOD_MINUTE:02d}) — neither SL nor Target was hit."
        elif source == "srv2_momentum_reversal" and entry_level_price is not None and underlying_spot is not None:
            settings_15m = cloud_db.get_strategy_settings("15m_dynamic_sr", symbol)
            is_naked = strategy_name in ("NAKED_CALL", "NAKED_PUT")
            direction_bullish = strategy_name in ("BULL_PUT_SPREAD", "NAKED_CALL")
            premium_pnl_points = net_credit - cost_to_close_now

            if is_naked:
                # वापरकर्त्याशी चर्चा करून ठरवलेला नियम — Naked trade "pure intraday" — कधीच
                # carry-forward नाही, नेहमी आजच (डीफॉल्ट 3:00pm) बंद. Spot%+Premium-Points एकत्र,
                # TSL-to-Breakeven सह (dynamic_sr_instant सारखीच, वेगळ्या उंबरठ्यांसह).
                point_exit_reason, tsl_now_activated, point_exit_detail = evaluate_point_spot_exit(
                    direction_bullish, entry_level_price, underlying_spot, premium_pnl_points,
                    settings_15m["naked_sl_spot_pct"], settings_15m["naked_sl_premium_points"],
                    settings_15m["naked_tsl_spot_pct"], settings_15m["naked_tsl_premium_points"],
                    settings_15m["naked_target_spot_pct"], settings_15m["naked_target_premium_points"],
                    tsl_activated,
                )
                if tsl_now_activated != tsl_activated:
                    cur.execute("UPDATE live_trades SET tsl_activated=? WHERE trade_id=?", (1 if tsl_now_activated else 0, trade_id))
                exit_reason = point_exit_reason
                exit_reason_detail = point_exit_detail

                # 🎓 वापरकर्त्याने मागितलेली सुधारणा — user-defined Premium-Points Trailing Stop
                # (settings-चालित, डीफॉल्ट बंद). 1m_instant प्रमाणेच.
                if exit_reason is None and tsl_now_activated and settings_15m["naked_trailing_sl_enabled"]:
                    trail_distance = settings_15m["naked_trailing_distance_points"]
                    new_peak_premium, floor_points = compute_premium_trailing_floor(premium_pnl_points, peak_pnl, trail_distance)
                    if new_peak_premium != peak_pnl:
                        cur.execute("UPDATE live_trades SET peak_pnl=? WHERE trade_id=?", (new_peak_premium, trade_id))
                        peak_pnl = new_peak_premium
                    if premium_pnl_points <= floor_points:
                        exit_reason = "TSL_SL"
                        exit_reason_detail = (
                            f"Trailing SL hit (Premium Points trail) — Peak premium gain {new_peak_premium:.1f} pts, "
                            f"trailing distance {trail_distance:.1f} pts -> floor {floor_points:.1f} pts, now at {premium_pnl_points:.1f} pts."
                        )

                if exit_reason is None and trade_style == "INTRADAY":
                    naked_past_eod = (ist_now.hour, ist_now.minute) >= (settings_15m["naked_eod_hour"], settings_15m["naked_eod_minute"])
                    if naked_past_eod:
                        exit_reason = "EOD_SQUAREOFF"
                        exit_reason_detail = f"Auto-closed at EOD Square-off ({settings_15m['naked_eod_hour']}:{settings_15m['naked_eod_minute']:02d}) — neither SL nor Target was hit."
            else:
                # वापरकर्त्याशी चर्चा करून ठरवलेला नियम — Credit Spread साठी SL/TSL स्पॉट%+प्रीमियम-
                # पॉइंट्स एकत्र (Target मात्र वेगळाच — निव्वळ प्रीमियमच्या 80%, existing target_level
                # column मार्फतच, म्हणून इथे target-उंबरठे प्रचंड मोठे देऊन evaluate_point_spot_exit
                # चा स्वतःचा built-in target-मार्ग निष्क्रिय केलेला).
                point_exit_reason, tsl_now_activated, point_exit_detail = evaluate_point_spot_exit(
                    direction_bullish, entry_level_price, underlying_spot, premium_pnl_points,
                    settings_15m["spread_sl_spot_pct"], settings_15m["spread_sl_premium_points"],
                    settings_15m["spread_tsl_spot_pct"], settings_15m["spread_tsl_premium_points"],
                    target_spot_pct=1e9, target_premium_points=1e9,
                    tsl_already_activated=tsl_activated,
                )
                if tsl_now_activated != tsl_activated:
                    cur.execute("UPDATE live_trades SET tsl_activated=? WHERE trade_id=?", (1 if tsl_now_activated else 0, trade_id))
                exit_reason = point_exit_reason if point_exit_reason != "TARGET" else None
                exit_reason_detail = point_exit_detail if exit_reason is not None else None

                # 🎓 वापरकर्त्याने मागितलेली सुधारणा — user-defined Premium-Points Trailing Stop
                # (settings-चालित, डीफॉल्ट बंद). PREMIUM_TARGET/NEXT_LEVEL_EXIT/Carry-Forward
                # तपासण्यांच्या आधी (existing TSL-to-Breakeven प्रमाणेच priority).
                if exit_reason is None and tsl_now_activated and settings_15m["spread_trailing_sl_enabled"]:
                    trail_distance = settings_15m["spread_trailing_distance_points"]
                    new_peak_premium, floor_points = compute_premium_trailing_floor(premium_pnl_points, peak_pnl, trail_distance)
                    if new_peak_premium != peak_pnl:
                        cur.execute("UPDATE live_trades SET peak_pnl=? WHERE trade_id=?", (new_peak_premium, trade_id))
                        peak_pnl = new_peak_premium
                    if premium_pnl_points <= floor_points:
                        exit_reason = "TSL_SL"
                        exit_reason_detail = (
                            f"Trailing SL hit (Premium Points trail) — Peak premium gain {new_peak_premium:.1f} pts, "
                            f"trailing distance {trail_distance:.1f} pts -> floor {floor_points:.1f} pts, now at {premium_pnl_points:.1f} pts."
                        )

                if exit_reason is None and target_level is not None and current_pnl >= target_level:
                    exit_reason = "PREMIUM_TARGET"
                    exit_reason_detail = (
                        f"Hit {settings_15m['spread_target_pct_of_premium']}% of Net Premium as Target "
                        f"(P&L Rs {current_pnl:,.0f} >= Target level Rs {target_level:,.0f})."
                    )

                # वापरकर्त्याशी चर्चा करून ठरवलेला नियम ("Use the same SR timeframe for exit") —
                # Next-Level-Exit आता फक्त entry_timeframe च्याच levels मधून शोधतो, तिन्ही पूल
                # केलेले नाहीत (entry_timeframe गहाळ असल्यास, सुरक्षिततेसाठी तिन्हीतूनच शोधणे —
                # जुनं, established वर्तन).
                if exit_reason is None:
                    search_timeframes = (entry_timeframe,) if entry_timeframe else ("15M", "30M", "60M")
                    next_level = cloud_db.get_next_level_in_direction(symbol, entry_level_price, direction_bullish, timeframe_suffixes=search_timeframes)
                    if next_level is not None:
                        reached = (underlying_spot >= next_level) if direction_bullish else (underlying_spot <= next_level)
                        if reached:
                            exit_reason = "NEXT_LEVEL_EXIT"
                            exit_reason_detail = (
                                f"Reached the next S/R level (Rs {next_level:,.1f}, {entry_timeframe or '15M/30M/60M'}) — "
                                "profit-booked at this next level instead of the original entry level."
                            )

                # 🎓 वापरकर्त्याने सापडवलेली, महत्त्वाची दुरुस्ती — नवीन Spot/Premium exit-रचना जोडताना
                # ही आधीचीच 3:10pm Carry-Forward तपासणी चुकून काढली गेली होती — ती परत जोडली. Target
                # (वर तपासलेला) अजून गाठलेला नसेल, आणि 3:10pm झालेली असेल — नफा किमान (settings मधला)
                # carry_forward_min_profit_pct इतका असेल तर पुढच्या दिवशी चालू ठेवणे, नाहीतर आजच बंद.
                if exit_reason is None:
                    past_carry_forward_check_time = (ist_now.hour, ist_now.minute) >= (15, 10)
                    if past_carry_forward_check_time:
                        carry_forward_min_profit_level = net_credit_total * (settings_15m["carry_forward_min_profit_pct"] / 100.0)
                        if current_pnl < carry_forward_min_profit_level:
                            exit_reason = "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT"
                            exit_reason_detail = (
                                f"Insufficient profit at 3:10pm (P&L Rs {current_pnl:,.0f} < minimum Rs {carry_forward_min_profit_level:,.0f}, "
                                f"{settings_15m['carry_forward_min_profit_pct']}% of credit) — closed today instead of carrying forward."
                            )
                        # पुरेसा नफा असेल तर काहीही करायचं नाही -- पुढच्या दिवशी चालू ठेवणे
                    elif trade_style == "INTRADAY" and past_eod_cutoff:
                        exit_reason = "EOD_SQUAREOFF"
                        exit_reason_detail = "Auto-closed at EOD Square-off — Target/Carry-Forward conditions were not met."
        else:
            # 🎓 वापरकर्त्याशी चर्चा करून वाढवलेली सुधारणा — %-आधारित Trailing SL आता कुठल्याही
            # source ला लागू होत नाही (dynamic_sr_instant/srv2_momentum_reversal दोन्ही आता स्वतंत्र,
            # वरच्या branches मध्ये हाताळले जातात).
            PCT_TRAILING_SOURCES = ()
            is_pct_trailing_trade = (source in PCT_TRAILING_SOURCES)

            effective_sl_level = sl_level
            is_trailing_active = False
            if is_pct_trailing_trade:
                # ATR-Trailing ऐवजी — नेहमी सक्रिय (sidebar टॉगलची गरज नाही), 20% नफ्यानंतर सक्रिय
                new_peak_pnl, effective_sl_level = compute_pct_trailing_sl_level(
                    current_pnl, peak_pnl, net_credit_total, activation_pct=20, lock_pct=10, original_sl_level=sl_level,
                )
                if new_peak_pnl != peak_pnl:
                    cur.execute("UPDATE live_trades SET peak_pnl=? WHERE trade_id=?", (new_peak_pnl, trade_id))
                is_trailing_active = effective_sl_level != sl_level
            elif trailing_sl_enabled:
                # ATR-आधारित Trailing SL — चालू असेल तरच, आणि मूळ स्थिर SL पेक्षा कधीच वाईट (सैल) होणार नाही याची खात्री
                new_peak_pnl, effective_sl_level = compute_trailing_sl_level(
                    current_pnl, peak_pnl, atr_points, lot_size, lots, atr_multiplier=atr_multiplier, original_sl_level=sl_level,
                )
                if new_peak_pnl != peak_pnl:
                    cur.execute("UPDATE live_trades SET peak_pnl=? WHERE trade_id=?", (new_peak_pnl, trade_id))
                is_trailing_active = effective_sl_level != sl_level

            # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेला नवीन नियम — Price Action/Indicator (BULL_PUT_SPREAD/
            # BEAR_CALL_SPREAD) साठी Target (net_credit च्या स्वतःच्या target_pct_of_max_profit %,
            # उदा. 80%) आधी दुपारी ३:१० लाच बंद व्हायचा नियम होता — पण Target गाठला की तो लगेच
            # (कधीही) बंद व्हायला हवा, वेळेची वाट न बघता. ३:१०चा नियम आता वेगळ्या, कमी उंबरठ्याशी
            # (CARRY_FORWARD_MIN_PROFIT_PCT) जोडलेला — Target (80%) अजून गाठलेला नसेल, तरच "किमान
            # इतका (३०%) नफा आहे का, नाहीतर आजच बंद करा" ही सुरक्षा-तपासणी.
            # 🎓 वापरकर्त्याशी चर्चा करून वाढवलेली सुधारणा — नवीन OI+Greeks+VIX एकत्रित रणनीती (Iron Condor
            # सुद्धा तयार करते) साठी, तोच SL + 3:10pm carry-forward नियम आता Iron Condor/Butterfly
            # लाही लागू — सर्व unattended strategies मध्ये सुसंगत जोखीम-व्यवस्थापन.
            # 🎓 वापरकर्त्याशी चर्चा करून सुधारित — तपासण्याची वेळ 3:00 वरून 3:10 केली (सर्व वरील स्ट्रॅटेजींसाठी
            # सामायिक — फक्त SRv2 साठी वेगळी नाही).
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant`/`srv2_momentum_reversal`
            # ला हा carry-forward नियम कधीच लागू होत नाही (सामान्यतः वरच्या वेगळ्या शाखांमध्येच जातात
            # — पण entry_level_price/underlying_spot काही कारणाने गहाळ असेल तरीही, सुरक्षिततेसाठी
            # इथेही स्पष्ट वगळलेले).
            is_new_rule_trade = (
                strategy_name in ("BULL_PUT_SPREAD", "BEAR_CALL_SPREAD", "IRON_CONDOR", "IRON_BUTTERFLY")
                and source not in ("dynamic_sr_instant", "srv2_momentum_reversal")
            )
            past_carry_forward_check_time = (ist_now.hour, ist_now.minute) >= (15, 10)
            carry_forward_min_profit_level = net_credit_total * (CARRY_FORWARD_MIN_PROFIT_PCT / 100.0)

            exit_reason = None
            exit_reason_detail = None
            if effective_sl_level is not None and current_pnl <= effective_sl_level:
                if is_trailing_active:
                    exit_reason = "PCT_TRAILING_SL" if is_pct_trailing_trade else "TRAILING_SL"
                    exit_reason_detail = f"Trailing SL — total P&L Rs {current_pnl:,.0f} hit/crossed the (profit-adjusted) trailing SL level Rs {effective_sl_level:,.0f}."
                else:
                    exit_reason = "SL"
                    exit_reason_detail = f"Stop-Loss — total P&L Rs {current_pnl:,.0f} hit/crossed the fixed SL level Rs {effective_sl_level:,.0f}."
            elif target_level is not None and current_pnl >= target_level:
                exit_reason = "TARGET"  # Target गाठला की केव्हाही (वेळेची वाट न बघता) लगेच बंद
                exit_reason_detail = f"Target — total P&L Rs {current_pnl:,.0f} reached/exceeded the Target level Rs {target_level:,.0f}."
            elif is_new_rule_trade and past_carry_forward_check_time:
                # Target (वर तपासलेला) अजून गाठलेला नाही, आणि आता दुपारी ३:१० झालेली आहे --
                # वेगळ्या, कमी उंबरठ्याशी (डीफॉल्ट 30% credit) पुरेसा नफा आहे का तपासणे -- असेल तर
                # पुढच्या दिवशी चालू ठेवणे, नाहीतर आजच बंद करणे.
                if current_pnl < carry_forward_min_profit_level:
                    exit_reason = "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT"
                    exit_reason_detail = (
                        f"Insufficient profit at 3:10pm (P&L Rs {current_pnl:,.0f} < minimum Rs {carry_forward_min_profit_level:,.0f}, "
                        f"{CARRY_FORWARD_MIN_PROFIT_PCT}% of credit) — closed today instead of carrying forward."
                    )
                # पुरेसा नफा असेल तर काहीही करायचं नाही -- पुढच्या दिवशी चालू ठेवणे
            elif trade_style == "INTRADAY" and past_eod_cutoff:
                exit_reason = "EOD_SQUAREOFF"
                exit_reason_detail = "Auto-closed at EOD Square-off — none of SL/Target/Carry-Forward conditions applied."
            elif oi_reversal_exit_enabled and trade_style == "INTRADAY" and oi_signal_latest:
                trade_direction = infer_direction_from_strategy(strategy_name)
                if trade_direction and not check_oi_diff_entry_gate(trade_direction, oi_signal_latest):
                    exit_reason = "OI_REVERSAL"
                    exit_reason_detail = "OI Diff Tracker signal reversed against the position — exited early for safety, ahead of SL/Target."

        if exit_reason:
            qty = lots * lot_size
            close_orders = [
                {
                    "quantity": qty, "product": product_type, "validity": "DAY", "price": 0,
                    "tag": f"A1_CLOSE_{leg['role'].upper()[:12]}", "instrument_token": leg["instrument_key"],
                    "order_type": "MARKET",
                    "transaction_type": ("SELL" if leg["transaction_type"] == "BUY" else "BUY"),
                    "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False,
                    "strike": leg.get("strike"), "option_type": leg.get("option_type"), "expiry": leg.get("expiry"),
                    "correlation_id": uuid.uuid4().hex[:20],  # 🎓 UDAPI1115 फिक्स — वर बघा
                }
                for leg in legs
            ]
            close_adapter = _resolve_close_adapter(account_id)
            status_code, resp = (close_adapter.execute_order_leg_set(close_orders, trade_mode) if close_adapter is not None
                                  else execute_order_leg_set(access_token, close_orders, trade_mode))
            if status_code == 200 and resp.get("status") == "success":
                order_ids = extract_order_ids(resp)
                log_orders_batch(order_ids, trade_id, symbol, trade_mode, close_orders, status="COMPLETE", fill_prices=current_ltps)
                cur.execute(
                    """UPDATE live_trades SET status='CLOSED', exit_time=?, exit_reason=?, exit_reason_detail=?, realized_pnl=?
                       WHERE trade_id=?""",
                    (get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), exit_reason, exit_reason_detail, round(current_pnl, 2), trade_id),
                )
                conn.commit()
                closed_summaries.append({"trade_id": trade_id, "reason": exit_reason, "pnl": round(current_pnl, 2), "mode": trade_mode})
            else:
                # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली, महत्त्वाची सुरक्षा-सुधारणा — आधी close-order
                # अयशस्वी झाल्यास कुठलीही नोंद (log/notification) होतच नव्हती — trade OPEN च
                # राहायचा, आणि दर मिनिटाला तेच शांतपणे (गुपचूप) परत अयशस्वी व्हायचं, कधीच कळायचं नाही.
                # आता print (monitor.log मध्ये दिसेल) आणि Telegram notification दोन्ही.
                print(
                    f"⚠️ CLOSE ORDER FAILED — trade_id={trade_id}, symbol={symbol}, reason={exit_reason}, "
                    f"status_code={status_code}, response={resp}"
                )
                try:
                    from notifications import send_telegram_message
                    send_telegram_message(
                        f"🔴 <b>{symbol} — Position बंद करण्याचा प्रयत्न अयशस्वी!</b>\n"
                        f"Trade {trade_id} (कारण: {exit_reason}) — broker कडून अयशस्वी उत्तर.\n"
                        f"कृपया Dashboard/Upstox app उघडून प्रत्यक्ष स्थिती तपासा."
                    )
                except Exception:
                    _logger.exception("manage_open_trades() मध्ये अनपेक्षित चूक (silently handled)")
                    pass  # Telegram पाठवताना चूक झाली तरी मुख्य loop थांबता कामा नये

    # Trailing SL मुळे peak_pnl अपडेट झालेला असू शकतो, जरी या रनला कोणताही trade प्रत्यक्ष बंद झाला नसला तरी —
    # तो बदल इथे न चुकता commit करणे आवश्यक (नाहीतर वर फक्त trade बंद झाल्यावरच commit होतो).
    conn.commit()
    conn.close()
    return closed_summaries


def reconcile_open_trades_with_broker(access_token, symbol):
    """
    वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Broker Reconciliation) — कधीकधी position आपल्या
    Dashboard बाहेर जाऊन, थेट Upstox app/website वरून बंद केली जाते. अशा वेळी आपल्या database ला
    ते कळतच नाही, आणि Positions tab वर ती खोटी "उघडी" दिसत राहते — मग तिथून चुकून पुन्हा "बंद करा"
    दाबलं, तर एक नवा, चुकीचा order Upstox कडे जाऊ शकतो.

    हे function फक्त वाचतं (Upstox कडे कुठलाही order पाठवत नाही) — प्रत्यक्ष भरतल्या Upstox
    Positions शी आपल्या OPEN trades ताडून बघतं. एखाद्या trade च्या सर्व legs ची quantity broker
    कडे शून्य असेल (म्हणजे ती position आता तिथे अस्तित्वातच नाही), तर आपल्या database मध्येच
    "CLOSED" म्हणून नोंदवतो.

    🎓 वापरकर्त्याशी चर्चा करून जोडलेली, महत्त्वाची सुरक्षा-सुधारणा — फक्त mode='LIVE' trades साठीच
    (PAPER trades ला खरी Upstox position कधीच नसते — त्यामुळे आधी PAPER trades सुद्धा चुकून
    "बाहेरून बंद झालेले" समजून बंद केले जायचे, जे साफ चुकीचं होतं).

    🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection) टेस्ट करताना सापडलेली, महत्त्वाची
    व्याप्ती-मर्यादा — हे फक्त Upstox च्या स्वतःच्या Positions शी ताडून बघतं, त्यामुळे फक्त शुद्ध Upstox
    trades (account_id IS NULL — कुठलाही विशिष्ट broker account निवडलेला नाही) साठीच सुरक्षित आहे.
    वापरकर्त्याने निवडलेल्या इतर broker (Fyers/Shoonya/Stocko) accounts वरचे trades इथे मुद्दामच
    वगळलेले — कारण BrokerAdapter इंटरफेसला अजून "fetch_positions()" नाहीये (फक्त execute_order_leg_set
    आहे), त्यामुळे त्यांची reconciliation शक्यच नाही. असे trades अजूनही SL/TSL/Target/EOD वर बरोबर
    (त्याच निवडलेल्या broker वर) बंद होतात — फक्त "वापरकर्त्याने broker च्या स्वतःच्या app/website वरून
    थेट बंद केलं तर आपोआप कळणं" ही सुरक्षा-जाळी त्यांना लागू नाही.

    रिटर्न: (reconciled_list, error_message). यशस्वी झालं की error_message रिकामं.
    """
    positions = fetch_broker_positions(access_token)
    if positions is None:
        return [], "Upstox कडून Positions मिळाल्या नाहीत (token/नेटवर्क तपासा) — reconciliation करता आलं नाही."

    # 🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — आधी `broker_open_keys` मध्ये
    # फक्त धन quantity असलेले instruments असायचे, आणि कुठलाही leg त्या यादीत *नसेल* (मग तो broker कडे
    # खरंच बंद असो, किंवा response मध्ये नुसताच गहाळ/अपूर्ण असो — दोन्ही सारखेच दिसायचे) तर trade
    # CLOSED मार्क व्हायचा. एकच रिकामा/अर्धवट response (क्षणिक network glitch, किंवा carry-forward
    # झालेली position "short-term-positions" API मध्ये त्या दिवशी दिसलीच नाही तरीही) — आणि सर्वच्या
    # सर्व OPEN LIVE trades एकाच वेळी CLOSED होऊन जायच्या, पुढे SL/Target/EOD काहीच लागू न होता
    # unmanaged राहायच्या. आता फक्त तीच position CLOSED मार्क होते, जिच्या **सर्व** legs broker कडून
    # स्पष्टपणे quantity=0 सह कळवलेल्या असतात (नुसतं यादीत नसणं पुरेसं नाही) — एखादा leg response मध्ये
    # गहाळ असेल, तर ती trade सुरक्षिततेसाठी OPEN च राहते (manage_open_trades चं SL/Target/EOD अजूनही
    # लागू राहतं) — जास्तीत जास्त एखादी खरोखर जुनी बंद झालेली trade DB मध्ये चुकून "OPEN" दिसत राहणं
    # (manual साफसफाई लागेल), पण कधीच खरी उघडी position "बंद" समजून अनियंत्रित सोडली जाणार नाही.
    broker_flat_keys = {p.get("instrument_token") for p in positions if p.get("quantity", 0) == 0}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT trade_id, legs_json FROM live_trades WHERE symbol=? AND status='OPEN' AND mode='LIVE' AND account_id IS NULL",
        (symbol,),
    )
    open_trades = cur.fetchall()

    reconciled = []
    for trade_id, legs_json_str in open_trades:
        legs = json.loads(legs_json_str) if legs_json_str else []
        if not legs:
            continue
        all_legs_confirmed_flat = all(leg["instrument_key"] in broker_flat_keys for leg in legs)
        if all_legs_confirmed_flat:
            cur.execute(
                """UPDATE live_trades SET status='CLOSED', exit_time=?, exit_reason='RECONCILED_EXTERNAL_CLOSE'
                   WHERE trade_id=?""",
                (get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), trade_id),
            )
            reconciled.append(trade_id)
    conn.commit()
    conn.close()
    return reconciled, ""


def track_manual_trade(symbol, legs, lots, lot_size, entry_ltps, trading_mode, trading_style, sl_amount=None, target_amount=None, tag_prefix="MANUAL"):
    """
    Manually प्लेस केलेले (Single किंवा Basket) ऑर्डर्स live_trades मध्ये नोंदवणे — जेणेकरून Positions
    tab मध्ये MTM दिसेल. sl_amount/target_amount ऐच्छिक (₹ रकमेत, संपूर्ण पोझिशनसाठी) — दिलं नाही तर
    manage_open_trades कडून आपोआप SL/Target बंद होणार नाही (फक्त EOD किंवा मॅन्युअल Close होईल) —
    कारण अनियंत्रित leg-संयोजनासाठी max_loss/max_profit आपोआप काढणं दिशाभूल करणारं ठरू शकतं
    (उदा. hedge नसलेली नग्न SELL पोझिशन).
    entry_ltps: {instrument_key: ltp} — प्लेसमेंटच्या क्षणी (PAPER साठी paper_fills, LIVE साठी fresh LTP).
    """
    valid_legs = [leg for leg in legs if entry_ltps.get(leg["instrument_key"]) is not None]
    if len(valid_legs) != len(legs):
        return False, None, "काही legs ची entry किंमत मिळाली नाही — DB मध्ये नोंदवता आलं नाही (ऑर्डर प्रत्यक्षात प्लेस झाला असेल, फक्त tracking चुकलं — Reconciliation Check वापरा)."

    net_credit = sum(
        entry_ltps[leg["instrument_key"]] * (1 if leg["transaction_type"] == "SELL" else -1)
        for leg in legs
    )
    strikes_summary = " · ".join(f"{leg.get('role', leg['transaction_type'])}:{leg.get('strike', '?')}" for leg in legs)
    trade_id = f"{tag_prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    sl_pnl_level = -abs(sl_amount) if sl_amount is not None else None
    target_pnl_level = abs(target_amount) if target_amount is not None else None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO live_trades
           (trade_id, trade_date, symbol, strategy, short_strike, long_strike, short_instrument, long_instrument,
            lots, lot_size, net_credit, max_profit, max_loss, sl_pnl_level, target_pnl_level,
            entry_time, exit_time, exit_reason, realized_pnl, status, short_order_id, long_order_id,
            legs_json, strikes_summary, mode, trading_style)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            trade_id, get_ist_today().strftime("%Y-%m-%d"), symbol, "MANUAL",
            None, None, None, None,
            lots, lot_size, net_credit, None, None,
            sl_pnl_level, target_pnl_level,
            get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), None, None, None, "OPEN",
            None, None,
            json.dumps(legs), strikes_summary, trading_mode, trading_style,
        ),
    )
    inserted = cur.rowcount > 0
    conn.commit()
    conn.close()
    if not inserted:
        return False, None, f"Trade DB मध्ये नोंदवता आला नाही (trade_id टक्कर: {trade_id})."
    return True, trade_id, None


def close_trade_manually(access_token, trade_id, symbol, product_type, exit_reason="MANUAL_CLOSE"):
    """दिलेला specific trade_id बंद करणे — मोड (PAPER/LIVE) DB मधूनच वाचली जाते.
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — exit_reason आता parameter (डीफॉल्ट established
    'MANUAL_CLOSE', backward-compatible) — नवीन established trade_monitor.py यालाच पुनर्वापर करून
    'SL_HIT'/'TARGET_HIT' कारणांसह स्वयंचलितपणे बंद करू शकतं."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT legs_json, lots, lot_size, net_credit, mode, account_id FROM live_trades WHERE trade_id=? AND status='OPEN'",
        (trade_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Trade सापडला नाही किंवा आधीच बंद आहे."

    legs_json_str, lots, lot_size, net_credit, trade_mode, account_id = row
    legs = json.loads(legs_json_str) if legs_json_str else []
    if not legs:
        conn.close()
        return False, "Trade चे legs सापडले नाहीत (जुनी नोंद असू शकते)."

    all_keys = [leg["instrument_key"] for leg in legs]
    ltp_map = fetch_ltp_map(access_token, all_keys)
    if any(ltp_map.get(k) is None for k in all_keys):
        conn.close()
        return False, "सद्य LTP मिळाली नाही — पुन्हा प्रयत्न करा."

    cost_to_close_now = sum(
        ltp_map[leg["instrument_key"]] * (1 if leg["transaction_type"] == "SELL" else -1)
        for leg in legs
    )
    current_pnl = (net_credit - cost_to_close_now) * lots * lot_size

    close_orders = [
        {
            "quantity": lots * lot_size, "product": product_type, "validity": "DAY",
            "tag": f"MANUAL_CLOSE_{str(leg.get('role', 'LEG'))[:12]}", "instrument_token": leg["instrument_key"],
            "order_type": "MARKET", "transaction_type": ("SELL" if leg["transaction_type"] == "BUY" else "BUY"),
            "disclosed_quantity": 0, "trigger_price": 0, "price": 0, "is_amo": False,
            "strike": leg.get("strike"), "option_type": leg.get("option_type"), "expiry": leg.get("expiry"),
            "correlation_id": uuid.uuid4().hex[:20],  # 🎓 UDAPI1115 फिक्स — वर बघा
        }
        for leg in legs
    ]
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection) — trade निवडलेल्या broker
    # account वर उघडलेला असेल (account_id), तर मॅन्युअली बंद करतानाही तोच broker वापरायला हवा —
    # manage_open_trades() मधल्याच _resolve_close_adapter() पॅटर्नप्रमाणे.
    close_adapter = None
    if account_id is not None:
        import broker_factory
        adapters, _errors = broker_factory.get_adapters_for_accounts([account_id])
        close_adapter = adapters[0][0] if adapters else None
    status_code, resp = (close_adapter.execute_order_leg_set(close_orders, trade_mode or "LIVE") if close_adapter is not None
                          else execute_order_leg_set(access_token, close_orders, trade_mode or "LIVE"))
    if status_code == 200 and resp.get("status") == "success":
        order_ids = extract_order_ids(resp)
        log_orders_batch(order_ids, trade_id, symbol, trade_mode or "LIVE", close_orders, status="COMPLETE", fill_prices=ltp_map)
        cur.execute(
            "UPDATE live_trades SET status='CLOSED', exit_time=?, exit_reason=?, realized_pnl=? WHERE trade_id=?",
            (get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), exit_reason, round(current_pnl, 2), trade_id),
        )
        conn.commit()
        conn.close()
        return True, round(current_pnl, 2)

    conn.close()
    return False, f"बंद करताना त्रुटी: {resp}"


def execute_trade_on_all_accounts(symbol, strategy_result, base_lots, lot_size, sl_pct_of_max_loss,
                                   target_pct_of_max_profit, product_type, trading_mode="PAPER",
                                   trading_style="INTRADAY", sl_pct_of_credit=None, source="MULTI_ACCOUNT",
                                   entry_level_price=None, entry_timeframe=None, account_ids=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून बांधलेली — "Multi-Broker Multi-Account" रणनीती: established
    established broker_factory.get_all_active_adapters() कडून सर्व सक्रिय accounts मिळवून, established
    सर्व strategies, सर्व accounts वर एकसारख्या (replicated) चालवणे -- प्रत्येक account साठी established
    lot_multiplier नुसार वेगळे lots, पण established एकच strategy_result (एकाच broker-type गृहीत धरून,
    established, आत्ता फक्त Upstox सक्रिय असल्याने सुरक्षित).

    🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection — "user can choose multiple
    account or single, as per capital available") — account_ids (ऐच्छिक यादी) दिली असेल, तर "सर्व
    सक्रिय accounts" ऐवजी फक्त त्याच, वापरकर्त्याने त्या strategy+symbol साठी Bot Dynamic SR Algo
    वरून स्पष्ट निवडलेल्या account(s) वर चालवलं जातं. न दिल्यास (None, जुनं वर्तन) — सर्व सक्रिय
    accounts वर replicate (backward-compatible).

    रिटर्न: (results, factory_errors) -- results: [{"account_id":.., "ok":.., "result":..}, ...],
    factory_errors: कुठला account (token/broker-type समस्येमुळे) पूर्णपणे वगळला गेला त्याची यादी.
    """
    import broker_factory
    if account_ids:
        adapters, factory_errors = broker_factory.get_adapters_for_accounts(account_ids)
    else:
        adapters, factory_errors = broker_factory.get_all_active_adapters()
    if not adapters:
        return [], factory_errors

    results = []
    for adapter, lot_multiplier in adapters:
        effective_lots = max(1, round(base_lots * lot_multiplier))
        ok, result = open_multi_leg_trade(
            access_token=adapter.access_token, symbol=symbol, strategy_result=strategy_result,
            lots=effective_lots, lot_size=lot_size, sl_pct_of_max_loss=sl_pct_of_max_loss,
            target_pct_of_max_profit=target_pct_of_max_profit, product_type=product_type,
            trading_mode=trading_mode, trading_style=trading_style, sl_pct_of_credit=sl_pct_of_credit,
            source=source, adapter=adapter, entry_level_price=entry_level_price, entry_timeframe=entry_timeframe,
        )
        results.append({"account_id": adapter.get_account_id(), "ok": ok, "result": result})
    return results, factory_errors
