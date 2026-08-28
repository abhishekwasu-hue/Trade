"""
oi_greeks_vix_strategy.py
------------------------------
OI Analysis + Greeks + India VIX एकत्रित रणनीती — वापरकर्त्याशी चर्चा करून ठरवलेली, पूर्णपणे स्वतंत्र
unattended script.

Decision Tree (वापरकर्त्याशी चर्चा करून अंतिम ठरवलेली — VIX-दिशा उलट-पालट केलेली):
  VIX > 20         -> NO TRADE (खूप धोकादायक)
  VIX < 16         -> IRON CONDOR (नेहमी, OI काहीही असो — शांत बाजारात range-bound राहण्याची शक्यता
                      जास्त, त्यामुळे इथेच Iron Condor चं गृहीतक सर्वात जास्त खरं ठरतं)
  VIX 16-20:
    OI सलग ३ स्नॅपशॉट्समध्ये स्थिर BULLISH  -> BULL PUT SPREAD (ATM+2/Hedge+100)
    OI सलग ३ स्नॅपशॉट्समध्ये स्थिर BEARISH  -> BEAR CALL SPREAD (ATM+2/Hedge+100)
    OI अस्पष्ट/भिरभिरत                    -> NO TRADE (Iron Condor सुरक्षित डीफॉल्ट म्हणून वापरत नाही)

Entry नंतर: manage_open_trades (30% credit-SL + 3pm carry-forward — आता Iron Condor साठीही लागू) +
प्रत्येक open position साठी रणनीती-आधारित Delta Health Check (Iron Condor/Spread दोन्हीसाठी).

⚠️ वापरण्याआधी अनेक दिवस PAPER mode मध्ये चालवून निकाल तपासा.
"""
import datetime
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, get_ist_now, get_ist_today, is_market_open
from upstox_api import fetch_upstox_option_chain, fetch_india_vix
from database import get_live_positions_with_mtm, compute_per_position_greeks
from strategy import select_credit_spread_fixed_strikes, select_iron_condor
from trading_engine import open_multi_leg_trade, manage_open_trades
from notifications import notify_entry, notify_error, write_heartbeat

KILL_SWITCH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "KILL_SWITCH")
LOT_SIZE = 75
OI_PERSISTENCE_COUNT = 3        # ~३० मिनिटं
VIX_NO_TRADE_THRESHOLD = 20
VIX_IRON_CONDOR_THRESHOLD = 16
IC_POP_THRESHOLD = 70


def is_kill_switch_active():
    return os.path.exists(KILL_SWITCH_PATH)


def get_oi_signal_persistence(symbol, min_consistent=OI_PERSISTENCE_COUNT):
    """oi_signal_auto_trader.py सारखीच established पद्धत — सलग स्नॅपशॉट्समध्ये तीच दिशा टिकून आहे का."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    today_str = get_ist_today().strftime("%Y-%m-%d")
    cur.execute(
        "SELECT signal FROM oi_diff_snapshots WHERE symbol=? AND trade_date=? ORDER BY snapshot_time DESC LIMIT ?",
        (symbol, today_str, min_consistent),
    )
    rows = cur.fetchall()
    conn.close()
    if len(rows) < min_consistent:
        return None
    directions = []
    for r in rows:
        sig = r[0] or ""
        if "BULLISH" in sig:
            directions.append("BULLISH")
        elif "BEARISH" in sig:
            directions.append("BEARISH")
        else:
            directions.append(None)
    if None in directions:
        return None
    return directions[0] if all(d == directions[0] for d in directions) else None


def run_cycle(access_token, symbol="NIFTY", trading_mode="PAPER"):
    if not is_market_open():
        write_heartbeat("oi_greeks_vix_strategy")
        return ["⏸️ बाजार बंद आहे (वेळेबाहेर/सुट्टी) — कुठलीही कृती नाही."]
    if is_kill_switch_active():
        write_heartbeat("oi_greeks_vix_strategy")
        return ["🛑 KILL SWITCH सक्रिय — कुठलीही कृती नाही."]
    try:
        result_log = _run_cycle_inner(access_token, symbol, trading_mode)
        write_heartbeat("oi_greeks_vix_strategy")
        return result_log
    except Exception as exc:
        notify_error("oi_greeks_vix_strategy", f"चक्रादरम्यान अनपेक्षित चूक: {exc}")
        raise


def _run_cycle_inner(access_token, symbol, trading_mode):
    log = []

    # --- सद्य open position(s) असल्यास, व्यवस्थापन + Delta Health Check ---
    positions_df = get_live_positions_with_mtm(access_token, symbol, mode_filter=trading_mode)
    has_open = positions_df is not None and not positions_df.empty and (
        positions_df["Strategy"].isin(["BULL_PUT_SPREAD", "BEAR_CALL_SPREAD", "IRON_CONDOR", "IRON_BUTTERFLY"]).any()
        if "Strategy" in positions_df.columns else not positions_df.empty
    )
    if has_open:
        closed = manage_open_trades(access_token, symbol, "D", eod_squareoff_hour=15, eod_squareoff_minute=0)
        log.append(f"सद्य positions व्यवस्थापन — बंद झालेले: {[c['trade_id'] for c in closed]}" if closed else "काहीही बंद झालं नाही (अजून सर्व अटी आत).")
        try:
            for p in compute_per_position_greeks(access_token, symbol, mode_filter=trading_mode):
                log.append(f"🩺 {p['trade_id']} ({p['strategy']}): {p['health_emoji']} {p['health_message']}")
        except Exception:
            log.append("⚠️ Delta Health Check मिळवता आला नाही (Greeks API अनुपलब्ध असू शकतं).")
        return log

    # --- नवीन Entry — आधी VIX (धोका-गेट) ---
    india_vix = fetch_india_vix(access_token)
    if india_vix is None:
        log.append("India VIX मिळाला नाही — Entry नाही.")
        return log
    log.append(f"India VIX: {india_vix}")

    if india_vix > VIX_NO_TRADE_THRESHOLD:
        log.append(f"⚠️ VIX={india_vix} > {VIX_NO_TRADE_THRESHOLD} → NO TRADE (खूप धोकादायक)")
        return log

    raw_chain, expiry = fetch_upstox_option_chain(access_token, symbol)
    if not raw_chain:
        log.append("Option chain मिळाला नाही.")
        return log
    atm_strike = round(raw_chain[len(raw_chain) // 2].get("underlying_spot_price", 0) / 50) * 50

    direction_label = "NEUTRAL"
    if india_vix < VIX_IRON_CONDOR_THRESHOLD:
        # 🎓 वापरकर्त्याशी चर्चा करून पूर्णपणे उलट-पालट केलेली सुधारणा — कमी VIX (शांत बाजार) मध्ये
        # किंमत range मध्येच राहण्याची शक्यता जास्त असते, त्यामुळे Iron Condor चं गृहीतक (defined
        # range) इथेच सर्वात जास्त खरं ठरतं — OI दिशा काहीही असो, नेहमीच Iron Condor.
        log.append(f"VIX={india_vix} (<{VIX_IRON_CONDOR_THRESHOLD}, शांत बाजार) → Iron Condor (नेहमी, OI काहीही असो)")
        strategy_result = select_iron_condor(raw_chain, atm_strike, step=50, hedge_width_points=100, pop_threshold_pct=IC_POP_THRESHOLD)
    else:
        # VIX 16-20 (अधिक प्रीमियम उपलब्ध) -- OI ची स्पष्ट, स्थिर दिशा असेल तरच दिशात्मक Spread,
        # नाहीतर स्पष्टपणे Entry नाकारणे (Iron Condor सुरक्षित डीफॉल्ट म्हणून वापरायचं नाही, हवं तसं).
        oi_direction = get_oi_signal_persistence(symbol)
        if oi_direction:
            log.append(f"VIX={india_vix} ({VIX_IRON_CONDOR_THRESHOLD}-{VIX_NO_TRADE_THRESHOLD} दरम्यान), OI स्थिर दिशा: {oi_direction}")
            direction_label = oi_direction
            strategy_result = select_credit_spread_fixed_strikes(raw_chain, oi_direction, atm_strike)
        else:
            log.append(f"VIX={india_vix} ({VIX_IRON_CONDOR_THRESHOLD}-{VIX_NO_TRADE_THRESHOLD} दरम्यान), पण OI दिशा अस्पष्ट → NO TRADE")
            return log

    if strategy_result is None:
        log.append("योग्य Strike combination सापडलं नाही — Entry नाही.")
        return log

    success, result = open_multi_leg_trade(
        access_token, symbol, strategy_result, lots=1, lot_size=LOT_SIZE,
        sl_pct_of_max_loss=999, target_pct_of_max_profit=30, product_type="D",
        trading_mode=trading_mode, trading_style="SWING", sl_pct_of_credit=30,
        source="oi_greeks_vix_strategy",
    )
    if not success:
        log.append(f"❌ Order अयशस्वी: {result}")
        return log

    net_credit = strategy_result.get("net_credit")
    notify_entry("oi_greeks_vix_strategy", symbol, strategy_result["strategy"], direction_label,
                 f"ATM={atm_strike}", net_credit, result["trade_id"])
    log.append(f"✅ नवीन Entry: {strategy_result['strategy']} ({direction_label}), Net Credit={net_credit}, Trade ID={result['trade_id']}")
    return log


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--mode", default="PAPER", choices=["PAPER", "LIVE"])
    args = parser.parse_args()

    result_log = run_cycle(args.token, args.symbol, args.mode)
    for line in result_log:
        print(f"[{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}] {line}")
