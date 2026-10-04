"""
refresh_dynamic_sr_5m.py
-------------------------
वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (नवीन नियम-संच, Word document) — 1M Instant Trader आता
1-मिनिट **आणि** 5-मिनिट, दोन्ही Dynamic S/R levels एकत्र वापरतो. हे त्याच 5-मिनिट levels साठीची
हलकी, merge-आधारित (refresh_dynamic_sr_1m.py/refresh_dynamic_sr_15m.py सारखीच) refresh script.

फक्त DYNAMIC_SR_*_5M प्रकारचे zones — merge-आधारित (पूर्ण replace नाही, जुने कधीच DELETE होत नाहीत)
— "Merge the both levels with the historical levels. Do not remove historical levels." या स्पष्ट
सांगितलेल्या नियमाप्रमाणे.

वापर (cron मध्ये, refresh_dynamic_sr_1m.py सोबतच, दर 5 मिनिटांनी):
    python3 refresh_dynamic_sr_5m.py --symbols NIFTY,BANKNIFTY,SENSEX
"""
import argparse

import cloud_db
import level_memory as LM
from config import get_ist_now
from sr_dynamic import compute_dynamic_sr
from upstox_api import fetch_candles


def refresh_symbol_5m(access_token, symbol):
    """एका symbol साठी — अलीकडचा 5-मिनिट डेटा, Dynamic S/R गणना, आणि merge-आधारित साठवणी."""
    df_5m = fetch_candles(access_token, symbol, current_spot=0, interval="5minute")  # Upstox चा स्वतःचा डीफॉल्ट lookback (5-मिनिटसाठी ~10 दिवस)
    if df_5m is None or len(df_5m) < 100:
        return False, f"{symbol}: पुरेसा 5-मिनिट डेटा नाही"
    if df_5m.attrs.get("failed_chunks", 0) > 0:
        # अर्धवट डेटावरून गणना केलेले levels जुन्या चांगल्या levels ला STALE करू नयेत — या वेळी काहीच साठवत नाही.
        return False, f"{symbol}: 5-मिनिट इतिहासाचे {df_5m.attrs['failed_chunks']} chunk(s) मिळाले नाहीत — या वेळी levels अद्ययावत केले नाहीत (जुनेच कायम)"

    dyn_sr = compute_dynamic_sr(df_5m, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
    # 🎓 Level memory (डीफॉल्ट चालू) -- जुने levels त्याच किंमतीवर, अलीकडे टेकलेले top-5 बाहेरचेही ठेवले (बघा level_memory.py)
    if LM.memory_enabled(symbol, "5M", cloud_db.get_strategy_settings):
        dyn_sr = LM.remember_dyn_sr(dyn_sr, cloud_db.get_market_zones(symbol, status="ACTIVE"), "5M", df_5m, get_ist_now())
    ok = cloud_db.merge_dynamic_sr_zones(symbol, dyn_sr, "5M", formed_date=get_ist_now())
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
        ok, message = refresh_symbol_5m(access_token, sym)
        print(("✅ " if ok else "⚠️ ") + message)
