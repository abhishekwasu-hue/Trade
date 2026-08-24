"""
credit_spread_auto_trader.py
--------------------------------
पूर्णपणे स्वयंचलित (unattended), local machine वर cron/scheduler द्वारे वारंवार (उदा. दर ५-१०
मिनिटांनी, बाजार-वेळेत) चालवायची script — Credit Spread (Bull Put / Bear Call) साठी:

  दिशा: A1 Signal Engine (1H Supertrend) — सलग ३ तपासण्यांत तीच दिशा दिसली तरच 'स्थिर' मानून entry
  Strikes: ATM पासून 2 strikes OTM (short leg), 100-पॉइंट hedge (long leg) — निश्चित, PoP-आधारित नाही
  Expiry: Weekly (सर्वात जवळची)
  Exit: 30% SL (net credit च्या), 3pm ला — जर नफा >=30% असेल तर पुढे चालू ठेवणे, नाहीतर बंद
  सुरक्षा: फक्त Kill-Switch फाईल (रोज arming phrase नाही, कारण unattended)

⚠️⚠️⚠️ अत्यंत महत्त्वाचं — वापरण्याआधी वाचा ⚠️⚠️⚠️
१. हे प्रथम अनेक दिवस PAPER mode मध्ये चालवून, निकाल तपासूनच LIVE करा.
२. हे CRON/Task Scheduler ने दर काही मिनिटांनी (बाजार तास 9:15-15:30 मध्येच) चालवायचं आहे — एकदाच
   चालवून विसरायचं नाही (state file द्वारे मागचा संदर्भ राखलं जातं).
३. Kill-Switch फाईल (KILL_SWITCH_PATH) तयार केल्यास script लगेच सर्व नवीन entries थांबवेल — पण
   आधीच उघडी position स्वतःहून बंद करत नाही (ती manually किंवा Dashboard वरून बंद करावी लागेल).
४. Upstox Access Token दर काही तासांनी expire होतो — तो वैध आहे याची खात्री ठेवावी लागेल
   (हे स्वतः token refresh करत नाही).
"""
import datetime
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, get_ist_now
from signals import calculate_supertrend, resample_to_1h
from upstox_api import fetch_candles, fetch_upstox_option_chain
from database import get_live_positions_with_mtm
from trading_engine import open_multi_leg_trade, close_trade_manually

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "credit_spread_state.json")
KILL_SWITCH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "KILL_SWITCH")

# --- रणनीतीचे नियम (चर्चा करून ठरवलेले) ---
STRIKES_OTM = 2
HEDGE_WIDTH_POINTS = 100
SL_PCT_OF_CREDIT = 30
PROFIT_CARRY_PCT = 30
CLOSE_TIME = datetime.time(15, 0)
DIRECTION_STABILITY_CHECKS = 3
LOT_SIZE = 75


# ============================================================
# राज्य (State) — cron प्रत्येक वेळी नव्याने चालतो, म्हणून मागचा संदर्भ फाईलमध्ये साठवणे
# ============================================================
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"recent_directions": [], "open_position": None, "last_entry_date": None}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def is_kill_switch_active():
    return os.path.exists(KILL_SWITCH_PATH)


# ============================================================
# दिशा — 1H Supertrend (आपल्याच A1 Engine सारखीच, tested पद्धत) + स्थिरता तपासणी
# ============================================================
def get_current_direction(access_token, symbol):
    df_30m = fetch_candles(access_token, symbol, None, interval="30minute")
    if df_30m is None or df_30m.empty:
        return None
    df_1h = resample_to_1h(df_30m)
    if df_1h.empty:
        return None
    _, st_dir = calculate_supertrend(df_1h, period=10, multiplier=3)
    if st_dir.empty or st_dir.isna().iloc[-1]:
        return None
    return "BULLISH" if int(st_dir.iloc[-1]) == 1 else "BEARISH"


def check_direction_stable(recent_directions, min_consistent=DIRECTION_STABILITY_CHECKS):
    """गेल्या min_consistent तपासण्यांत सलग तीच दिशा (BULLISH/BEARISH) दिसली तरच 'स्थिर' — flip-flop नको."""
    if len(recent_directions) < min_consistent:
        return None
    last_n = recent_directions[-min_consistent:]
    if last_n[0] not in ("BULLISH", "BEARISH"):
        return None
    return last_n[0] if all(d == last_n[0] for d in last_n) else None


# ============================================================
# Strike निवड — निश्चित (fixed): 2 strikes OTM + 100-पॉइंट hedge
# ============================================================
def select_credit_spread_fixed(raw_chain, direction, atm_strike, strikes_otm=STRIKES_OTM,
                                 hedge_width_points=HEDGE_WIDTH_POINTS, step=50):
    if direction not in ("BULLISH", "BEARISH"):
        return None
    side = "put_options" if direction == "BULLISH" else "call_options"

    if direction == "BULLISH":
        short_strike = atm_strike - strikes_otm * step
        long_strike = short_strike - hedge_width_points
    else:
        short_strike = atm_strike + strikes_otm * step
        long_strike = short_strike + hedge_width_points

    def find_leg(strike):
        for item in raw_chain:
            if item.get("strike_price") == strike:
                opt = item.get(side, {}) or {}
                ltp = (opt.get("market_data", {}) or {}).get("ltp")
                instrument_key = opt.get("instrument_key")
                if ltp and instrument_key and ltp > 0:
                    return {"strike": strike, "instrument_key": instrument_key, "ltp": ltp}
        return None

    short_leg, long_leg = find_leg(short_strike), find_leg(long_strike)
    if short_leg is None or long_leg is None:
        return None
    net_credit = short_leg["ltp"] - long_leg["ltp"]
    if net_credit <= 0:
        return None
    return {
        "strategy": "BULL_PUT_SPREAD" if direction == "BULLISH" else "BEAR_CALL_SPREAD",
        "short_leg": short_leg, "long_leg": long_leg,
        "net_credit": round(net_credit, 2), "spread_width": hedge_width_points,
        "max_profit": round(net_credit, 2), "max_loss": round(hedge_width_points - net_credit, 2),
    }


# ============================================================
# Position Management — 30% SL + 3pm carry-forward/close निर्णय
# ============================================================
def check_position_management(net_credit, current_mtm_pnl, current_time,
                                sl_pct=SL_PCT_OF_CREDIT, profit_carry_pct=PROFIT_CARRY_PCT, close_time=CLOSE_TIME):
    sl_threshold = -1 * net_credit * (sl_pct / 100)
    if current_mtm_pnl <= sl_threshold:
        return "CLOSE_SL", f"तोटा {abs(current_mtm_pnl):.2f} >= SL मर्यादा {abs(sl_threshold):.2f} ({sl_pct}% of credit)"
    if current_time >= close_time:
        profit_threshold = net_credit * (profit_carry_pct / 100)
        if current_mtm_pnl >= profit_threshold:
            return "CARRY_FORWARD", f"नफा {current_mtm_pnl:.2f} >= {profit_carry_pct}% मर्यादा -> पुढे चालू"
        return "CLOSE_EOD", f"नफा {current_mtm_pnl:.2f} < {profit_carry_pct}% मर्यादा -> 3pm बंद"
    return "HOLD", "अजून कुठलीच exit-अट पूर्ण नाही"


# ============================================================
# मुख्य Entry Point — cron ने दर काही मिनिटांनी हेच चालवायचं
# ============================================================
def run_cycle(access_token, symbol="NIFTY", trading_mode="PAPER"):
    """
    एक चक्र (cycle) — कोणतीही existing position असल्यास तिचं व्यवस्थापन (SL/3pm तपासणी), नसल्यास
    दिशा-स्थिरता तपासून नवीन entry. trading_mode='PAPER' डीफॉल्ट — LIVE साठी स्पष्टपणे बदलावं लागतं.
    """
    log = []
    if is_kill_switch_active():
        log.append("🛑 KILL SWITCH सक्रिय आहे — कुठलीही नवीन कृती केली जाणार नाही.")
        return log

    state = load_state()
    now = get_ist_now()

    # --- सद्य position असल्यास, तिचं व्यवस्थापन ---
    if state["open_position"] is not None:
        pos = state["open_position"]
        positions_df = get_live_positions_with_mtm(access_token, symbol, mode_filter=trading_mode)
        pos_row = positions_df[positions_df["Trade ID"] == pos["trade_id"]] if positions_df is not None and not positions_df.empty else None
        if pos_row is None or pos_row.empty:
            log.append(f"⚠️ Trade ID {pos.get('trade_id')} DB मध्ये सापडला नाही — मॅन्युअली तपासा.")
            return log

        mtm_raw = pos_row["MTM (Rs)"].iloc[0]
        if pd.isna(mtm_raw):
            log.append("⚠️ सद्य LTP मिळाली नाही (MTM काढता आला नाही) — पुढच्या चक्रात पुन्हा प्रयत्न.")
            return log
        current_mtm = float(mtm_raw) / LOT_SIZE  # पॉइंट्समध्ये आणण्यासाठी
        action, reason = check_position_management(pos["net_credit"], current_mtm, now.time())
        log.append(f"सद्य position: {pos['strategy']}, MTM={current_mtm:.2f} पॉइंट्स | निर्णय: {action} | {reason}")

        if action in ("CLOSE_SL", "CLOSE_EOD"):
            success, result_msg = close_trade_manually(access_token, pos["trade_id"], symbol, product_type="D")
            log.append(f"Position बंद करण्याचा प्रयत्न ({action}): यशस्वी={success}, {result_msg}")
            if success:
                state["open_position"] = None
            # अयशस्वी झाल्यास state तसंच ठेवणे -- पुढच्या चक्रात पुन्हा प्रयत्न होईल
        # CARRY_FORWARD आणि HOLD -> काहीच बदल नाही
        save_state(state)
        return log

    # --- कुठलीही position उघडी नाही -> दिशा तपासून नवीन entry विचार ---
    direction = get_current_direction(access_token, symbol)
    state["recent_directions"] = (state["recent_directions"] + [direction])[-10:]  # फक्त शेवटच्या १० ठेवणे
    save_state(state)

    stable_direction = check_direction_stable(state["recent_directions"])
    if stable_direction is None:
        log.append(f"दिशा स्थिर नाही (सद्य: {direction}, गेल्या तपासण्या: {state['recent_directions'][-3:]}) — प्रतीक्षा")
        return log

    today_str = now.date().isoformat()
    if state.get("last_entry_date") == today_str:
        log.append("आज आधीच एक entry घेतलेली आहे — पुन्हा घेणार नाही.")
        return log

    raw_chain, expiry = fetch_upstox_option_chain(access_token, symbol)
    if not raw_chain:
        log.append("Option chain मिळाला नाही.")
        return log
    atm_strike = round(raw_chain[len(raw_chain)//2].get("underlying_spot_price", 0) / 50) * 50

    spread = select_credit_spread_fixed(raw_chain, stable_direction, atm_strike)
    if spread is None:
        log.append(f"स्थिर दिशा ({stable_direction}) सापडली, पण योग्य credit spread तयार करता आला नाही.")
        return log

    entry_success, entry_result = open_multi_leg_trade(
        access_token, symbol, spread, lots=1, lot_size=LOT_SIZE,
        # 🎓 खाली दिलेले sl_pct_of_max_loss/target_pct_of_max_profit हे DB मध्ये संदर्भासाठी साठवले
        # जातात, पण आपली स्वतःची exit-logic (30% of credit + 3pm carry-forward) याच script मध्ये,
        # वेगळी, स्वतंत्रपणे चालते — हे आकडे फक्त DB-नोंदीसाठी, प्रत्यक्ष निर्णयासाठी वापरले जात नाहीत.
        # ⚠️ जर आपलंच मुख्य Dashboard (manage_open_trades, Live/Intraday auto-refresh सह) त्याच
        # वेळी उघडं असेल, तर तेही या trade ला त्याच्याच (वेगळ्या) SL/Target/EOD नियमांनी व्यवस्थापित
        # करण्याचा प्रयत्न करू शकतं — दोन्ही एकाच वेळी चालवू नका, किंवा सावध रहा.
        sl_pct_of_max_loss=100, target_pct_of_max_profit=100,
        product_type="D", trading_mode=trading_mode, trading_style="SWING",
    )
    if not entry_success:
        log.append(f"❌ Order अयशस्वी: {entry_result}")
        return log
    trade_id = entry_result["trade_id"]

    state["open_position"] = {
        "trade_id": trade_id, "strategy": spread["strategy"], "direction": stable_direction,
        "short_leg": spread["short_leg"], "long_leg": spread["long_leg"],
        "net_credit": spread["net_credit"], "entry_time": now.isoformat(),
    }
    state["last_entry_date"] = today_str
    save_state(state)
    log.append(f"✅ नवीन Entry: {spread['strategy']} — Short {spread['short_leg']['strike']}, "
               f"Long {spread['long_leg']['strike']}, Net Credit={spread['net_credit']}, Trade ID={trade_id}")
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
