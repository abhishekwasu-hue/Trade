"""
oi_signal_auto_trader.py
----------------------------
पूर्णपणे स्वयंचलित (unattended), local machine वर cron/scheduler द्वारे वारंवार चालवायची script:

  Entry: A1 Signal Engine (1H Supertrend + Price Action/Indicator, 15M) तांत्रिक पुष्टी
         + OI Signal सलग ३ स्नॅपशॉट्समध्ये (~३० मिनिटं) तीच दिशा टिकून (स्थिर) — दोन्ही एकत्र जुळल्यावरच entry
  Strikes: ATM+2 Short, ATM+4 (100pt) Hedge — hedge आधी execute (आधीच्याच established पद्धतीने)
  Risk: SL = net_credit च्या 30%, दुपारी ३ ला नफा>=30% असल्यास carry-forward नाहीतर बंद
        (manage_open_trades मध्ये आधीच बांधलेली — इथे फक्त तीच पुनर्वापर केली आहे)
  सुरक्षा: फक्त Kill-Switch फाईल (credit_spread_auto_trader.py सारखीच)

⚠️ वापरण्याआधी अनेक दिवस PAPER mode मध्ये चालवून निकाल तपासा.
"""
import datetime
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, get_ist_now, get_ist_today, is_market_open
from signals import calculate_supertrend, calculate_rsi, resample_to_1h, check_price_action_strategy, check_indicator_strategy
from upstox_api import fetch_candles, fetch_timeframe_df, fetch_upstox_option_chain
from strategy import select_credit_spread_fixed_strikes
from database import get_live_positions_with_mtm
from trading_engine import open_multi_leg_trade, manage_open_trades
from notifications import notify_entry, notify_error, write_heartbeat

KILL_SWITCH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "KILL_SWITCH")
LOT_SIZE = 75
OI_PERSISTENCE_COUNT = 3  # ~३० मिनिटं (दर १० मिनिटांचे snapshots)


def is_kill_switch_active():
    return os.path.exists(KILL_SWITCH_PATH)


def get_current_a1_direction(access_token, symbol, strategy_choice="price_action"):
    """1H Supertrend + 15M Price Action/Indicator — आपल्याच page_dashboard.py च्या INTRADAY मार्गासारखीच, तंतोतंत तीच पद्धत."""
    df_30m = fetch_candles(access_token, symbol, None, interval="30minute")
    if df_30m is None or df_30m.empty:
        return None, "30-मिनिट डेटा मिळाला नाही"
    df_1h = resample_to_1h(df_30m)
    if df_1h.empty:
        return None, "1H resample अपयशी"
    _, st_dir = calculate_supertrend(df_1h, period=10, multiplier=3)
    if st_dir.empty or pd.isna(st_dir.iloc[-1]):
        return None, "1H Supertrend दिशा अस्पष्ट"
    direction_1h = "BULLISH" if int(st_dir.iloc[-1]) == 1 else "BEARISH"

    df_15m = fetch_timeframe_df(access_token, symbol, None, "15minute")
    if df_15m is None or df_15m.empty:
        return None, "15M डेटा मिळाला नाही"
    rsi_series = calculate_rsi(df_15m, period=14)

    if strategy_choice == "price_action":
        entry_ok, detail = check_price_action_strategy(df_15m, direction_1h, rsi_series=rsi_series, df_1h=df_1h)
    else:
        entry_ok, detail = check_indicator_strategy(df_15m, rsi_series, direction_1h)

    if not entry_ok:
        return None, f"1H दिशा={direction_1h}, पण {strategy_choice} entry-तपासणी अपुरी: {detail}"
    return direction_1h, f"A1 तांत्रिक पुष्टी OK ({strategy_choice}): {direction_1h}"


def get_oi_signal_persistence(symbol, min_consistent=OI_PERSISTENCE_COUNT):
    """oi_diff_snapshots मधले शेवटचे min_consistent स्नॅपशॉट्स — तीच दिशा (BULLISH/BEARISH) सलग टिकून आहे का."""
    import sqlite3
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
        return None, f"अपुरा इतिहास ({len(rows)}/{min_consistent} स्नॅपशॉट्स)"
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
        return None, "काही स्नॅपशॉट्समध्ये स्पष्ट दिशा नाही"
    if all(d == directions[0] for d in directions):
        return directions[0], f"OI Signal सलग {min_consistent} स्नॅपशॉट्समध्ये स्थिर: {directions[0]}"
    return None, f"OI Signal स्थिर नाही (गेली {min_consistent}: {directions})"


def run_cycle(access_token, symbol="NIFTY", trading_mode="PAPER", strategy_choice="price_action"):
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — बाजार बंद असताना उगाच Option Chain fetch करू नये
    if not is_market_open():
        write_heartbeat("oi_signal_auto_trader")
        return ["⏸️ बाजार बंद आहे (वेळेबाहेर/सुट्टी) — कुठलीही कृती केली जाणार नाही."]
    if is_kill_switch_active():
        write_heartbeat("oi_signal_auto_trader")
        return ["🛑 KILL SWITCH सक्रिय — कुठलीही कृती नाही."]
    try:
        result_log = _run_cycle_inner(access_token, symbol, trading_mode, strategy_choice)
        write_heartbeat("oi_signal_auto_trader")
        return result_log
    except Exception as exc:
        notify_error("oi_signal_auto_trader", f"चक्रादरम्यान अनपेक्षित चूक: {exc}")
        raise


def _run_cycle_inner(access_token, symbol, trading_mode, strategy_choice):
    log = []

    # --- सद्य open position असल्यास, फक्त तिचं व्यवस्थापन (SL/3pm-carry-forward — आधीच manage_open_trades मध्ये आहे) ---
    positions_df = get_live_positions_with_mtm(access_token, symbol, mode_filter=trading_mode)
    has_open = positions_df is not None and not positions_df.empty and (
        positions_df["Strategy"].isin(["BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"]).any() if "Strategy" in positions_df.columns else not positions_df.empty
    )
    if has_open:
        closed = manage_open_trades(access_token, symbol, "D", eod_squareoff_hour=15, eod_squareoff_minute=0)
        log.append(f"सद्य position व्यवस्थापन चालवलं — बंद झालेले: {[c['trade_id'] for c in closed]}" if closed else "सद्य position — काहीही बंद झालं नाही (अजून सर्व अटी आत).")
        return log

    # --- नवीन Entry — दोन्ही अटी एकत्र हव्यात ---
    a1_direction, a1_reason = get_current_a1_direction(access_token, symbol, strategy_choice)
    log.append(f"A1 तपासणी: {a1_reason}")
    if a1_direction is None:
        return log

    oi_direction, oi_reason = get_oi_signal_persistence(symbol)
    log.append(f"OI तपासणी: {oi_reason}")
    if oi_direction is None:
        return log

    if a1_direction != oi_direction:
        log.append(f"⚠️ दिशा जुळत नाही (A1={a1_direction}, OI={oi_direction}) — Entry नाही.")
        return log

    raw_chain, expiry = fetch_upstox_option_chain(access_token, symbol)
    if not raw_chain:
        log.append("Option chain मिळाला नाही.")
        return log
    atm_strike = round(raw_chain[len(raw_chain) // 2].get("underlying_spot_price", 0) / 50) * 50

    strategy_result = select_credit_spread_fixed_strikes(raw_chain, a1_direction, atm_strike)
    if strategy_result is None:
        log.append(f"दोन्ही अटी जुळल्या (दिशा={a1_direction}), पण योग्य Credit Spread तयार करता आला नाही.")
        return log

    success, result = open_multi_leg_trade(
        access_token, symbol, strategy_result, lots=1, lot_size=LOT_SIZE,
        sl_pct_of_max_loss=999, target_pct_of_max_profit=30, product_type="D",
        trading_mode=trading_mode, trading_style="SWING", sl_pct_of_credit=30,
        source="oi_signal_auto_trader",
    )
    if not success:
        log.append(f"❌ Order अयशस्वी: {result}")
        return log
    strikes_summary = f"Short {strategy_result['short_leg']['strike']}, Long {strategy_result['long_leg']['strike']}"
    notify_entry("oi_signal_auto_trader", symbol, strategy_result["strategy"], a1_direction, strikes_summary, strategy_result["net_credit"], result["trade_id"])
    log.append(f"✅ नवीन Entry (A1+OI दोन्ही जुळले): {strategy_result['strategy']} — "
               f"Short {strategy_result['short_leg']['strike']}, Long {strategy_result['long_leg']['strike']}, "
               f"Net Credit={strategy_result['net_credit']}, Trade ID={result['trade_id']}")
    return log


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--mode", default="PAPER", choices=["PAPER", "LIVE"])
    parser.add_argument("--strategy", default="price_action", choices=["price_action", "indicator"])
    args = parser.parse_args()

    result_log = run_cycle(args.token, args.symbol, args.mode, args.strategy)
    for line in result_log:
        print(f"[{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}] {line}")
