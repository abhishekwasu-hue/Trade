"""Trade execution and lifecycle management: open/close positions (LIVE + PAPER), SL/Target/EOD/OI-reversal exits, broker reconciliation."""
import datetime
import json
import sqlite3
import time
import uuid

from config import DB_PATH, get_ist_now, get_ist_today
from database import log_orders_batch
from upstox_api import execute_order_leg_set, fetch_ltp_map, fetch_broker_positions, extract_order_ids, get_instrument_key
from oi_analysis import get_latest_oi_signal, check_oi_diff_entry_gate, infer_direction_from_strategy

# 🎓 वापरकर्त्याशी चर्चा करून वेगळं काढलेलं — established Target (प्रत्येक strategy चा स्वतःचा
# target_pct_of_max_profit, उदा. SRv2 साठी 80%) आणि established 3:10pm Carry-Forward साठी "किमान
# इतका नफा असायलाच हवा" हा उंबरठा — या दोन वेगळ्या गोष्टी आहेत. established सर्व "new rule" strategies
# (BULL_PUT_SPREAD/BEAR_CALL_SPREAD/IRON_CONDOR/IRON_BUTTERFLY, dynamic_sr_instant वगळता) साठी सामायिक.
CARRY_FORWARD_MIN_PROFIT_PCT = 30

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` (1-मिनिट Instant Reversal) साठी
# SL/Target आता प्रीमियमवर नाही, underlying स्पॉट किमतीच्या हालचालीवर आधारित —
# entry-वेळचा S/R level (entry_level_price) पासून favourable/adverse दिशेने
# स्पॉट किती % हलला, त्यावरून. जुना प्रीमियम-आधारित SL(20%)/
# Target(50%)/%-Trailing या source साठी पूर्णपणे बदलला — आता
# लागू established होत नाही.
DYNAMIC_SR_SPOT_SL_PCT = 0.05
DYNAMIC_SR_SPOT_TARGET_PCT = 0.20

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
    """कोणत्याही स्ट्रॅटेजी रिझल्टला (2-leg स्प्रेड किंवा 4-leg कंडोर/बटरफ्लाय) समान legs-list स्वरूपात आणणे.
    🎓 वापरकर्त्याने Order Book वरून सापडवलेली bug — established "ltp" (entry-वेळचा प्रीमियम) आधी इथेच
    गाळला जायचा (2-leg स्प्रेड साठी) — म्हणजे Order Book च्या "Price" column ला (जो established
    MARKET order request चा price=0 दाखवतो, कारण MARKET order ला limit price नसतोच) दाखवायला
    प्रत्यक्ष entry किंमतच उपलब्ध नव्हती. आता established "ltp" (उपलब्ध असल्यास) पुढे नेलं जातं."""
    if "legs" in strategy_result:
        return strategy_result["legs"]
    return [
        {"role": "long_hedge", "strike": strategy_result["long_leg"]["strike"],
         "instrument_key": strategy_result["long_leg"]["instrument_key"], "transaction_type": "BUY",
         "ltp": strategy_result["long_leg"].get("ltp")},
        {"role": "short_leg", "strike": strategy_result["short_leg"]["strike"],
         "instrument_key": strategy_result["short_leg"]["instrument_key"], "transaction_type": "SELL",
         "ltp": strategy_result["short_leg"].get("ltp")},
    ]

def open_multi_leg_trade(access_token, symbol, strategy_result, lots, lot_size, sl_pct_of_max_loss, target_pct_of_max_profit, product_type, trading_mode="LIVE", trading_style="INTRADAY", sl_pct_of_credit=None, source="MANUAL", adapter=None, entry_level_price=None):
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
    level touch झाला की profit-booking exit साठी वापरला जातो (इतर strategies साठी None, वापरलं जात नाही)."""
    legs = normalize_legs(strategy_result)
    qty = lots * lot_size

    orders = [
        {
            "quantity": qty, "product": product_type, "validity": "DAY", "price": 0,
            "tag": f"A1_{leg['role'].upper()[:16]}", "instrument_token": leg["instrument_key"],
            "order_type": "MARKET", "transaction_type": leg["transaction_type"],
            "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False,
            # 🎓 वापरकर्त्याने Upstox कडून सापडवलेली bug — Upstox Multi Order API ला प्रत्येक order
            # साठी `correlation_id` (unique, alphanumeric, कमाल २० अक्षरं) आता सक्तीचा आहे — नसेल तर
            # "UDAPI1115: correlation_id is required" देऊन संपूर्ण ऑर्डर नाकारतो.
            "correlation_id": uuid.uuid4().hex[:20],
        }
        for leg in legs
    ]
    status_code, resp = (adapter.execute_order_leg_set(orders, trading_mode) if adapter is not None
                          else execute_order_leg_set(access_token, orders, trading_mode))
    if status_code != 200 or resp.get("status") != "success":
        return False, resp

    order_ids = extract_order_ids(resp)
    max_loss_total = strategy_result["max_loss"] * lot_size
    max_profit_total = strategy_result["max_profit"] * lot_size
    net_credit_total = strategy_result["net_credit"] * lot_size
    if sl_pct_of_credit is not None:
        sl_pnl_level = -(net_credit_total * (sl_pct_of_credit / 100.0))
    else:
        sl_pnl_level = -(max_loss_total * (sl_pct_of_max_loss / 100.0))
    target_pnl_level = max_profit_total * (target_pct_of_max_profit / 100.0)
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
            legs_json, strikes_summary, mode, trading_style, source, account_id, entry_level_price)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            entry_level_price,
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
        """SELECT trade_id, legs_json, lots, lot_size, net_credit, sl_pnl_level, target_pnl_level, mode, trading_style, strategy, peak_pnl, source, entry_level_price
           FROM live_trades WHERE symbol=? AND status='OPEN'""",
        (symbol,),
    )
    open_trades = cur.fetchall()
    if not open_trades:
        conn.close()
        return []

    parsed_trades = []
    all_keys = set()
    for (trade_id, legs_json_str, lots, lot_size, net_credit, sl_level, target_level, trade_mode, trade_style, strategy_name, peak_pnl, source, entry_level_price) in open_trades:
        legs = json.loads(legs_json_str) if legs_json_str else []
        for leg in legs:
            all_keys.add(leg["instrument_key"])
        parsed_trades.append((trade_id, legs, lots, lot_size, net_credit, sl_level, target_level, trade_mode or "LIVE", trade_style or "INTRADAY", strategy_name or "", peak_pnl, source or "", entry_level_price))

    ltp_map = fetch_ltp_map(access_token, list(all_keys))

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` trades साठी underlying
    # स्पॉटची सद्य LTP लागते (option-leg LTPs पुरेसे नाहीत, SL/Target आता स्पॉट-आधारित). कमीत कमी
    # एक असा trade असेल तरच हा जादा fetch करणे.
    underlying_spot = None
    if any(t[11] == "dynamic_sr_instant" for t in parsed_trades):
        spot_key = get_instrument_key(symbol)
        spot_ltp_map = fetch_ltp_map(access_token, [spot_key])
        underlying_spot = spot_ltp_map.get(spot_key)

    closed_summaries = []
    for (trade_id, legs, lots, lot_size, net_credit, sl_level, target_level, trade_mode, trade_style, strategy_name, peak_pnl, source, entry_level_price) in parsed_trades:
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

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` साठी SL/Target आता
        # प्रीमियमवर नाही, underlying स्पॉटच्या हालचालीवर आधारित (entry_level_price पासून). जुना
        # प्रीमियम-आधारित SL/Target/%-Trailing/Carry-Forward — या source साठी पूर्णपणे बदलला.
        if source == "dynamic_sr_instant" and entry_level_price is not None and underlying_spot is not None:
            direction_bullish = (strategy_name == "BULL_PUT_SPREAD")
            spot_pct_move = (underlying_spot - entry_level_price) / entry_level_price

            exit_reason = None
            if direction_bullish:
                if spot_pct_move >= DYNAMIC_SR_SPOT_TARGET_PCT / 100:
                    exit_reason = "SPOT_TARGET"
                elif spot_pct_move <= -DYNAMIC_SR_SPOT_SL_PCT / 100:
                    exit_reason = "SPOT_SL"
            else:
                if spot_pct_move <= -DYNAMIC_SR_SPOT_TARGET_PCT / 100:
                    exit_reason = "SPOT_TARGET"
                elif spot_pct_move >= DYNAMIC_SR_SPOT_SL_PCT / 100:
                    exit_reason = "SPOT_SL"

            if exit_reason is None and trade_style == "INTRADAY" and past_eod_cutoff:
                exit_reason = "EOD_SQUAREOFF"
        else:
            # 🎓 वापरकर्त्याशी चर्चा करून वाढवलेली सुधारणा — %-आधारित Trailing SL आता
            # `srv2_momentum_reversal` लाही लागू — 20% नफ्यानंतर सक्रिय, breakeven+10% credit लॉक.
            PCT_TRAILING_SOURCES = ("srv2_momentum_reversal",)
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
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` ला हा carry-forward
            # नियम कधीच लागू होत नाही (सामान्यतः वरच्या वेगळ्या शाखेतच जातो — पण entry_level_price/
            # underlying_spot काही कारणाने गहाळ असेल तरीही, सुरक्षिततेसाठी इथेही स्पष्ट वगळलेला).
            is_new_rule_trade = (
                strategy_name in ("BULL_PUT_SPREAD", "BEAR_CALL_SPREAD", "IRON_CONDOR", "IRON_BUTTERFLY")
                and source != "dynamic_sr_instant"
            )
            past_carry_forward_check_time = (ist_now.hour, ist_now.minute) >= (15, 10)
            carry_forward_min_profit_level = net_credit_total * (CARRY_FORWARD_MIN_PROFIT_PCT / 100.0)

            exit_reason = None
            if effective_sl_level is not None and current_pnl <= effective_sl_level:
                if is_trailing_active:
                    exit_reason = "PCT_TRAILING_SL" if is_pct_trailing_trade else "TRAILING_SL"
                else:
                    exit_reason = "SL"
            elif target_level is not None and current_pnl >= target_level:
                exit_reason = "TARGET"  # Target गाठला की केव्हाही (वेळेची वाट न बघता) लगेच बंद
            elif is_new_rule_trade and past_carry_forward_check_time:
                # Target (वर तपासलेला) अजून गाठलेला नाही, आणि आता दुपारी ३:१० झालेली आहे --
                # वेगळ्या, कमी उंबरठ्याशी (डीफॉल्ट 30% credit) पुरेसा नफा आहे का तपासणे -- असेल तर
                # पुढच्या दिवशी चालू ठेवणे, नाहीतर आजच बंद करणे.
                if current_pnl < carry_forward_min_profit_level:
                    exit_reason = "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT"
                # पुरेसा नफा असेल तर काहीही करायचं नाही -- पुढच्या दिवशी चालू ठेवणे
            elif trade_style == "INTRADAY" and past_eod_cutoff:
                exit_reason = "EOD_SQUAREOFF"
            elif oi_reversal_exit_enabled and trade_style == "INTRADAY" and oi_signal_latest:
                trade_direction = infer_direction_from_strategy(strategy_name)
                if trade_direction and not check_oi_diff_entry_gate(trade_direction, oi_signal_latest):
                    exit_reason = "OI_REVERSAL"

        if exit_reason:
            qty = lots * lot_size
            close_orders = [
                {
                    "quantity": qty, "product": product_type, "validity": "DAY", "price": 0,
                    "tag": f"A1_CLOSE_{leg['role'].upper()[:12]}", "instrument_token": leg["instrument_key"],
                    "order_type": "MARKET",
                    "transaction_type": ("SELL" if leg["transaction_type"] == "BUY" else "BUY"),
                    "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False,
                    "correlation_id": uuid.uuid4().hex[:20],  # 🎓 UDAPI1115 फिक्स — वर बघा
                }
                for leg in legs
            ]
            status_code, resp = execute_order_leg_set(access_token, close_orders, trade_mode)
            if status_code == 200 and resp.get("status") == "success":
                order_ids = extract_order_ids(resp)
                log_orders_batch(order_ids, trade_id, symbol, trade_mode, close_orders, status="COMPLETE", fill_prices=current_ltps)
                cur.execute(
                    """UPDATE live_trades SET status='CLOSED', exit_time=?, exit_reason=?, realized_pnl=?
                       WHERE trade_id=?""",
                    (get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), exit_reason, round(current_pnl, 2), trade_id),
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

    रिटर्न: (reconciled_list, error_message). यशस्वी झालं की error_message रिकामं.
    """
    positions = fetch_broker_positions(access_token)
    if positions is None:
        return [], "Upstox कडून Positions मिळाल्या नाहीत (token/नेटवर्क तपासा) — reconciliation करता आलं नाही."

    broker_open_keys = {p.get("instrument_token") for p in positions if p.get("quantity", 0) != 0}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT trade_id, legs_json FROM live_trades WHERE symbol=? AND status='OPEN' AND mode='LIVE'", (symbol,))
    open_trades = cur.fetchall()

    reconciled = []
    for trade_id, legs_json_str in open_trades:
        legs = json.loads(legs_json_str) if legs_json_str else []
        if not legs:
            continue
        still_open_at_broker = any(leg["instrument_key"] in broker_open_keys for leg in legs)
        if not still_open_at_broker:
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
        "SELECT legs_json, lots, lot_size, net_credit, mode FROM live_trades WHERE trade_id=? AND status='OPEN'",
        (trade_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Trade सापडला नाही किंवा आधीच बंद आहे."

    legs_json_str, lots, lot_size, net_credit, trade_mode = row
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
            "correlation_id": uuid.uuid4().hex[:20],  # 🎓 UDAPI1115 फिक्स — वर बघा
        }
        for leg in legs
    ]
    status_code, resp = execute_order_leg_set(access_token, close_orders, trade_mode or "LIVE")
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
                                   entry_level_price=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून बांधलेली — "Multi-Broker Multi-Account" रणनीती: established
    established broker_factory.get_all_active_adapters() कडून सर्व सक्रिय accounts मिळवून, established
    सर्व strategies, सर्व accounts वर एकसारख्या (replicated) चालवणे -- प्रत्येक account साठी established
    lot_multiplier नुसार वेगळे lots, पण established एकच strategy_result (एकाच broker-type गृहीत धरून,
    established, आत्ता फक्त Upstox सक्रिय असल्याने सुरक्षित).

    रिटर्न: (results, factory_errors) -- results: [{"account_id":.., "ok":.., "result":..}, ...],
    factory_errors: कुठला account (token/broker-type समस्येमुळे) पूर्णपणे वगळला गेला त्याची यादी.
    """
    import broker_factory
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
            source=source, adapter=adapter, entry_level_price=entry_level_price,
        )
        results.append({"account_id": adapter.get_account_id(), "ok": ok, "result": result})
    return results, factory_errors
