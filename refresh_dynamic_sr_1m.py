"""
refresh_dynamic_sr_1m.py
-------------------------
वापरकर्त्याशी चर्चा करून बांधलेली — Dynamic S/R Instant Reversal Trader (1-मिनिट) साठीचे levels
आता फक्त EOD ला (रात्री एकदा) नाही, तर existing 5-मिनिट cron सोबतच (वेगळं crontab entry न वाढवता)
दर वेळी ताजे केले जातात — 1-मिनिट स्ट्रॅटेजीला दिवसभर जुनेच (कालच्या रात्रीचे) levels मिळू नयेत म्हणून.

फक्त DYNAMIC_SR_*_1M प्रकारचे zones — हलका (फक्त ~5 दिवसांचा 1-मिनिट डेटा) आणि **merge**-आधारित
(पूर्ण replace नाही) — जेणेकरून Multi-Hit hit-count history (level_price वरच आधारित) टिकून राहील.
साधे SUPPORT/RESISTANCE, Order Block, Demand/Supply, आणि DYNAMIC_SR_*_15M (SRv2 साठी) — या सर्वांना
हात लावला जात नाही, ते अजूनही फक्त रात्रीच्या refresh_market_zones.py द्वारेच अपडेट होतात.

वापर (cron मध्ये, existing dynamic_sr_instant_trader.py च्याच entry च्या आधी, दर 5 मिनिटांनी):
    python3 refresh_dynamic_sr_1m.py --symbols NIFTY,BANKNIFTY,SENSEX
"""
import argparse

import cloud_db
from config import get_ist_now
from sr_dynamic import compute_dynamic_sr
from upstox_api import fetch_candles


def refresh_symbol_1m(access_token, symbol):
    """एका symbol साठी — अलीकडचा 1-मिनिट डेटा, Dynamic S/R गणना, आणि merge-आधारित साठवणी."""
    df_1m = fetch_candles(access_token, symbol, current_spot=0, interval="1minute")  # Upstox चा स्वतःचा डीफॉल्ट lookback (1-मिनिटसाठी ~5 दिवस)
    if df_1m is None or len(df_1m) < 100:
        return False, f"{symbol}: पुरेसा 1-मिनिट डेटा नाही"

    dyn_sr = compute_dynamic_sr(df_1m, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
    ok = cloud_db.merge_dynamic_sr_1m_zones(symbol, dyn_sr, formed_date=get_ist_now())
    if not ok:
        return False, f"{symbol}: Supabase मध्ये merge अयशस्वी (जोडणी तपासा)"

    support_count = len(dyn_sr.get("support", []))
    resistance_count = len(dyn_sr.get("resistance", []))
    return True, f"{symbol}: merge यशस्वी ({support_count} support, {resistance_count} resistance उमेदवार तपासले)"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    parser.add_argument("--token", default=None, help="न दिल्यास Supabase मधून आपोआप")
    args = parser.parse_args()

    access_token = cloud_db.get_effective_upstox_token(args.token)
    if not access_token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही.")
        raise SystemExit(1)

    for sym in args.symbols.split(","):
        sym = sym.strip()
        if not sym:
            continue
        ok, message = refresh_symbol_1m(access_token, sym)
        print(("✅ " if ok else "⚠️ ") + message)
