"""
weekly_dual_expiry_option_seller.py
-----------------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली रणनीती — NIFTY (साप्ताहिक, मंगळवार expiry) आणि SENSEX (साप्ताहिक,
गुरुवार expiry) दोन्ही एकत्र, hedge-सहित (Iron Condor / Credit Spread), मासिक १०-१५% ROI लक्ष्य.

निर्णय-तर्क (established framework, वापरकर्त्याशी चर्चा करून अंतिम केलेला):
  VIX > 20                                    -> NO_TRADE
  दिशा "खरी" (confirmed) -- ३ स्रोत जुळले        -> High Confidence -> दिशात्मक (VIX<20 पर्यंत प्राधान्य)
  दिशा "मध्यम" -- २ स्रोत जुळले, आणि VIX<16       -> दिशात्मक (fallback)
  दिशा अस्पष्ट, VIX<16                          -> Iron Condor (fallback)
  बाकी सर्व (VIX 16-20, दिशा अस्पष्ट/मध्यम)        -> NO_TRADE

३ दिशा-स्रोत (Confluence, established functions चा पुनर्वापर):
  १. Supertrend (1H) — signals.calculate_supertrend()
  २. Market Structure (HH/HL वि. LH/LL) — signals.classify_market_structure()
  ३. OI Rotation (Call/Put OI विरुद्ध दिशेने, सलग २ स्नॅपशॉट्स) — oi_analysis.rotation_confirmed_for_2_snapshots()

⚠️ महत्त्वाची मर्यादा: हा फक्त सिग्नल-निर्णय भाग आहे — प्रत्यक्ष order-execution आपल्याच established
trading_engine.py/database.py च्या functions शी जोडून पूर्ण करावं लागेल (credit_spread_auto_trader.py
सारखं). १०-१५% मासिक ROI हे लक्ष्य आहे, हमी नाही — बाजार परिस्थितीनुसार निकाल बदलू शकतात.
"""
import argparse
import datetime
import sqlite3

from config import DB_PATH, get_ist_now
from signals import calculate_supertrend, classify_market_structure
from oi_analysis import rotation_confirmed_for_2_snapshots
from strategy import select_credit_spread_fixed_strikes
from upstox_api import fetch_upstox_option_chain, fetch_india_vix, fetch_candles

# 🎓 वापरकर्त्याने स्पष्ट सांगितलेलं established expiry-वेळापत्रक (सप्टेंबर २०२५ पासूनचं SEBI फेरबदल)
SYMBOL_EXPIRY_WEEKDAY = {"NIFTY": 1, "SENSEX": 3}  # Python: सोमवार=0 ... मंगळवार=1, गुरुवार=3

VIX_NO_TRADE_THRESHOLD = 20.0
VIX_IRON_CONDOR_THRESHOLD = 16.0


def map_structure_to_direction(structure_label):
    """classify_market_structure() चा वर्णनात्मक स्ट्रिंग, साध्या BULLISH/BEARISH/None मध्ये बदलणे."""
    if structure_label.startswith("HH/HL"):
        return "BULLISH"
    elif structure_label.startswith("LH/LL"):
        return "BEARISH"
    return None


def get_supertrend_direction(df_1h, period=10, multiplier=3):
    """established calculate_supertrend() वापरून, सद्य (शेवटच्या) candle ची दिशा."""
    if df_1h is None or len(df_1h) < period + 5:
        return None
    _, direction = calculate_supertrend(df_1h, period=period, multiplier=multiplier)
    last_dir = direction.iloc[-1]
    if pd_isna(last_dir):
        return None
    return "BULLISH" if int(last_dir) == 1 else "BEARISH"


def pd_isna(x):
    """pandas import न करता, साधी NaN तपासणी (हलकं dependency)."""
    return x != x


def get_oi_rotation_direction(db_path, symbol, min_change_pct=2.0):
    """established rotation_confirmed_for_2_snapshots() वापरून, अलीकडच्या ३ snapshots वरून OI-आधारित दिशा."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    today_str = get_ist_now().strftime("%Y-%m-%d")
    cur.execute(
        """SELECT total_call_oi, total_put_oi FROM oi_diff_snapshots
           WHERE symbol=? AND trade_date=? ORDER BY snapshot_time ASC""",
        (symbol, today_str),
    )
    rows = cur.fetchall()
    conn.close()
    if len(rows) < 3:
        return None
    history_rows = [(r[0], r[1]) for r in rows[-3:]]
    return rotation_confirmed_for_2_snapshots(history_rows, min_change_pct)


def confluence_direction(supertrend_dir, structure_dir, oi_rotation_dir):
    """
    🎓 वापरकर्त्याशी चर्चा करून ठरवलेली — ३ स्वतंत्र स्रोत एकत्र करून दिशा आणि आत्मविश्वास-पातळी.
    रिटर्न: (दिशा, level) — level: ३=सर्व जुळले, २=दोन जुळले, ०=अस्पष्ट/परस्परविरोधी.
    """
    sources = [supertrend_dir, structure_dir, oi_rotation_dir]
    valid = [s for s in sources if s is not None]
    bullish = valid.count("BULLISH")
    bearish = valid.count("BEARISH")
    if bullish >= 2 and bullish > bearish:
        return "BULLISH", bullish
    elif bearish >= 2 and bearish > bullish:
        return "BEARISH", bearish
    return "UNCLEAR", 0


def decide_strategy(vix, confluence_dir, confluence_level):
    """
    🎓 वापरकर्त्याशी चर्चा करून अंतिम ठरवलेली निर्णय-तर्क (पूर्ण docstring वर, फाईलच्या सुरुवातीला).
    """
    if vix is None or vix > VIX_NO_TRADE_THRESHOLD:
        return "NO_TRADE"
    direction_confirmed = (confluence_level == 3) or (confluence_level == 2 and vix < VIX_IRON_CONDOR_THRESHOLD)
    if direction_confirmed:
        return "BULL_PUT_SPREAD" if confluence_dir == "BULLISH" else "BEAR_CALL_SPREAD"
    elif vix < VIX_IRON_CONDOR_THRESHOLD:
        return "IRON_CONDOR"
    return "NO_TRADE"


def is_expiry_week_entry_day(symbol, now=None):
    """
    🎓 सोमवार (NIFTY, मंगळवार expiry आधी) किंवा मंगळवार/बुधवार (SENSEX, गुरुवार expiry आधी) —
    entry साठी योग्य दिवस आहे का. आत्ताच expiry दिवशीच entry घेणं टाळण्यासाठी (0-1 DTE खूप जोखमीचं).
    """
    now = now or get_ist_now()
    expiry_weekday = SYMBOL_EXPIRY_WEEKDAY[symbol]
    days_to_expiry = (expiry_weekday - now.weekday()) % 7
    return 1 <= days_to_expiry <= 2  # expiry च्या १-२ दिवस आधी


def evaluate_symbol(access_token, symbol, atm_strike):
    """एका symbol साठी संपूर्ण निर्णय-प्रक्रिया — दिशा, VIX, strategy निवड."""
    raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol)
    india_vix = fetch_india_vix(access_token)
    df_1h = fetch_candles(access_token, symbol, atm_strike, interval="1hour", lookback_days=60)

    supertrend_dir = get_supertrend_direction(df_1h)
    structure_info = classify_market_structure(df_1h) if df_1h is not None and not df_1h.empty else {"structure": "INSUFFICIENT_DATA"}
    structure_dir = map_structure_to_direction(structure_info["structure"])
    oi_rotation_dir = get_oi_rotation_direction(DB_PATH, symbol)

    conf_dir, conf_level = confluence_direction(supertrend_dir, structure_dir, oi_rotation_dir)
    strategy_type = decide_strategy(india_vix, conf_dir, conf_level)

    return {
        "symbol": symbol, "vix": india_vix, "supertrend": supertrend_dir, "structure": structure_dir,
        "oi_rotation": oi_rotation_dir, "confluence_direction": conf_dir, "confluence_level": conf_level,
        "strategy": strategy_type, "raw_chain": raw_chain, "atm_strike": atm_strike,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--mode", default="PAPER", choices=["PAPER", "LIVE"])
    args = parser.parse_args()

    for symbol in ["NIFTY", "SENSEX"]:
        if not is_expiry_week_entry_day(symbol):
            print(f"{symbol}: आजचा दिवस entry साठी योग्य नाही (expiry {['सोम','मंगळ','बुध','गुरु','शुक्र'][SYMBOL_EXPIRY_WEEKDAY[symbol]]}वारी)")
            continue
        # ⚠️ ATM strike प्रत्यक्ष LTP वरून काढावं लागेल — इथे उदाहरणादाखल placeholder
        result = evaluate_symbol(args.token, symbol, atm_strike=0)
        print(f"\n{symbol}: VIX={result['vix']}, Confluence={result['confluence_direction']}"
              f"(level={result['confluence_level']}) -> Strategy: {result['strategy']}")
        if result["strategy"] not in ("NO_TRADE",):
            print(f"  -> इथे select_credit_spread_fixed_strikes() ने strikes निवडून, {args.mode} mode मध्ये execute करावं")
