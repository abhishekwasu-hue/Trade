"""Trade execution and lifecycle management: open/close positions (LIVE + PAPER), SL/Target/EOD/OI-reversal exits, broker reconciliation."""
import datetime
import json
import sqlite3
import time
import uuid

from config import DB_PATH, get_ist_now, get_ist_today
from database import log_orders_batch
from upstox_api import execute_order_leg_set, fetch_ltp_map, fetch_broker_positions
from oi_analysis import get_latest_oi_signal, check_oi_diff_entry_gate, infer_direction_from_strategy

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
    """कोणत्याही स्ट्रॅटेजी रिझल्टला (2-leg स्प्रेड किंवा 4-leg कंडोर/बटरफ्लाय) समान legs-list स्वरूपात आणणे."""
    if "legs" in strategy_result:
        return strategy_result["legs"]
    return [
        {"role": "long_hedge", "strike": strategy_result["long_leg"]["strike"],
         "instrument_key": strategy_result["long_leg"]["instrument_key"], "transaction_type": "BUY"},
        {"role": "short_leg", "strike": strategy_result["short_leg"]["strike"],
         "instrument_key": strategy_result["short_leg"]["instrument_key"], "transaction_type": "SELL"},
    ]

def open_multi_leg_trade(access_token, symbol, strategy_result, lots, lot_size, sl_pct_of_max_loss, target_pct_of_max_profit, product_type, trading_mode="LIVE", trading_style="INTRADAY", sl_pct_of_credit=None, source="MANUAL"):
    """कोणतीही स्ट्रॅटेजी (2-leg क्रेडिट स्प्रेड किंवा 4-leg Iron Condor/Butterfly) उघडणे (LIVE किंवा PAPER) व DB मध्ये नोंद करणे.
    sl_pct_of_credit दिलं (Price Action/Indicator साठी, वापरकर्त्याशी चर्चा करून ठरवलेलं नवीन नियम) तर SL
    net_credit च्या % वर ठरतो (max_loss च्या % ऐवजी — Iron Condor/Butterfly साठी जुनीच पद्धत कायम).
    source — हा trade नेमका कुठून आला (उदा. 'DASHBOARD', 'credit_spread_auto_trader', 'oi_signal_auto_trader',
    'oi_greeks_vix_strategy') — Positions page वर स्पष्टपणे दाखवण्यासाठी (वापरकर्त्याशी चर्चा करून जोडलेलं)."""
    legs = normalize_legs(strategy_result)
    qty = lots * lot_size

    orders = [
        {
            "quantity": qty, "product": product_type, "validity": "DAY", "price": 0,
            "tag": f"A1_{leg['role'].upper()[:16]}", "instrument_token": leg["instrument_key"],
            "order_type": "MARKET", "transaction_type": leg["transaction_type"],
            "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False,
        }
        for leg in legs
    ]
    status_code, resp = execute_order_leg_set(access_token, orders, trading_mode)
    if status_code != 200 or resp.get("status") != "success":
        return False, resp

    order_ids = resp.get("data", {}).get("order_ids", [])
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
    log_orders_batch(order_ids, trade_id, symbol, trading_mode, orders, status="COMPLETE")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO live_trades
           (trade_id, trade_date, symbol, strategy, short_strike, long_strike, short_instrument, long_instrument,
            lots, lot_size, net_credit, max_profit, max_loss, sl_pnl_level, target_pnl_level,
            entry_time, exit_time, exit_reason, realized_pnl, status, short_order_id, long_order_id,
            legs_json, strikes_summary, mode, trading_style, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            trade_id, get_ist_today().strftime("%Y-%m-%d"), symbol, strategy_result["strategy"],
            None, None, None, None,
            lots, lot_size, strategy_result["net_credit"], max_profit_total, max_loss_total,
            sl_pnl_level, target_pnl_level,
            get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), None, None, None, "OPEN",
            None, None,
            json.dumps(legs), strikes_summary, trading_mode, trading_style, source,
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
    """
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    past_eod_cutoff = (ist_now.hour, ist_now.minute) >= (eod_squareoff_hour, eod_squareoff_minute)
    oi_signal_latest = get_latest_oi_signal(symbol) if oi_reversal_exit_enabled else None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """SELECT trade_id, legs_json, lots, lot_size, net_credit, sl_pnl_level, target_pnl_level, mode, trading_style, strategy, peak_pnl
           FROM live_trades WHERE symbol=? AND status='OPEN'""",
        (symbol,),
    )
    open_trades = cur.fetchall()
    if not open_trades:
        conn.close()
        return []

    parsed_trades = []
    all_keys = set()
    for (trade_id, legs_json_str, lots, lot_size, net_credit, sl_level, target_level, trade_mode, trade_style, strategy_name, peak_pnl) in open_trades:
        legs = json.loads(legs_json_str) if legs_json_str else []
        for leg in legs:
            all_keys.add(leg["instrument_key"])
        parsed_trades.append((trade_id, legs, lots, lot_size, net_credit, sl_level, target_level, trade_mode or "LIVE", trade_style or "INTRADAY", strategy_name or "", peak_pnl))

    ltp_map = fetch_ltp_map(access_token, list(all_keys))

    closed_summaries = []
    for (trade_id, legs, lots, lot_size, net_credit, sl_level, target_level, trade_mode, trade_style, strategy_name, peak_pnl) in parsed_trades:
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

        # ATR-आधारित Trailing SL — चालू असेल तरच, आणि मूळ स्थिर SL पेक्षा कधीच वाईट (सैल) होणार नाही याची खात्री
        effective_sl_level = sl_level
        if trailing_sl_enabled:
            new_peak_pnl, effective_sl_level = compute_trailing_sl_level(
                current_pnl, peak_pnl, atr_points, lot_size, lots, atr_multiplier=atr_multiplier, original_sl_level=sl_level,
            )
            if new_peak_pnl != peak_pnl:
                cur.execute("UPDATE live_trades SET peak_pnl=? WHERE trade_id=?", (new_peak_pnl, trade_id))

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेला नवीन नियम — Price Action/Indicator (BULL_PUT_SPREAD/
        # BEAR_CALL_SPREAD) साठी Target लगेच बंद करत नाही — फक्त दुपारी ३ वाजता तपासतो: नफा >=Target
        # (net_credit च्या 30%) असेल तर पुढच्या दिवशी चालू ठेवणे (काहीही न करणे), नाहीतर बंद करणे.
        # 🎓 वापरकर्त्याशी चर्चा करून वाढवलेली सुधारणा — नवीन OI+Greeks+VIX एकत्रित रणनीती (Iron Condor
        # सुद्धा तयार करते) साठी, तोच 30%-credit SL + 3pm carry-forward नियम आता Iron Condor/Butterfly
        # लाही लागू — सर्व unattended strategies मध्ये सुसंगत जोखीम-व्यवस्थापन.
        is_new_rule_trade = strategy_name in ("BULL_PUT_SPREAD", "BEAR_CALL_SPREAD", "IRON_CONDOR", "IRON_BUTTERFLY")
        past_carry_forward_check_time = (ist_now.hour, ist_now.minute) >= (15, 0)

        exit_reason = None
        if effective_sl_level is not None and current_pnl <= effective_sl_level:
            exit_reason = "TRAILING_SL" if (trailing_sl_enabled and effective_sl_level != sl_level) else "SL"
        elif is_new_rule_trade:
            if past_carry_forward_check_time:
                if target_level is not None and current_pnl >= target_level:
                    pass  # नफा पुरेसा (>=30% credit) -- पुढच्या दिवशी चालू ठेवणे, बंद करायचं नाही
                else:
                    exit_reason = "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT"
            # 3pm च्या आधी -- SL शिवाय काहीही तपासायचं नाही, Target लगेच बंद करत नाही
        elif target_level is not None and current_pnl >= target_level:
            exit_reason = "TARGET"
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
                }
                for leg in legs
            ]
            status_code, resp = execute_order_leg_set(access_token, close_orders, trade_mode)
            if status_code == 200 and resp.get("status") == "success":
                order_ids = resp.get("data", {}).get("order_ids", [])
                log_orders_batch(order_ids, trade_id, symbol, trade_mode, close_orders, status="COMPLETE")
                cur.execute(
                    """UPDATE live_trades SET status='CLOSED', exit_time=?, exit_reason=?, realized_pnl=?
                       WHERE trade_id=?""",
                    (get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), exit_reason, round(current_pnl, 2), trade_id),
                )
                conn.commit()
                closed_summaries.append({"trade_id": trade_id, "reason": exit_reason, "pnl": round(current_pnl, 2), "mode": trade_mode})

    # Trailing SL मुळे peak_pnl अपडेट झालेला असू शकतो, जरी या रनला कोणताही trade प्रत्यक्ष बंद झाला नसला तरी —
    # तो बदल इथे न चुकता commit करणे आवश्यक (नाहीतर वर फक्त trade बंद झाल्यावरच commit होतो).
    conn.commit()
    conn.close()
    return closed_summaries


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


def close_trade_manually(access_token, trade_id, symbol, product_type):
    """दिलेला specific trade_id मॅन्युअली बंद करणे (Positions tab मधील 'Close' बटणासाठी) — मोड (PAPER/LIVE) DB मधूनच वाचली जाते."""
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
        }
        for leg in legs
    ]
    status_code, resp = execute_order_leg_set(access_token, close_orders, trade_mode or "LIVE")
    if status_code == 200 and resp.get("status") == "success":
        order_ids = resp.get("data", {}).get("order_ids", [])
        log_orders_batch(order_ids, trade_id, symbol, trade_mode or "LIVE", close_orders, status="COMPLETE")
        cur.execute(
            "UPDATE live_trades SET status='CLOSED', exit_time=?, exit_reason='MANUAL_CLOSE', realized_pnl=? WHERE trade_id=?",
            (get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), round(current_pnl, 2), trade_id),
        )
        conn.commit()
        conn.close()
        return True, round(current_pnl, 2)

    conn.close()
    return False, f"बंद करताना त्रुटी: {resp}"
