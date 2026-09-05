"""
refresh_market_zones.py
--------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — शेवटच्या १ वर्षाच्या OHLC डेटावरून S/R, Order Block,
Demand/Supply Zone, Unfilled Gap यांचं संपूर्ण विश्लेषण करून Supabase मध्ये साठवणे — जेणेकरून
Dashboard/रणनीती प्रत्येक वेळी पुन्हा गणना न करता, थेट वाचू शकतील.

GitHub Actions द्वारे रोज (बाजार बंद झाल्यावर) आपोआप चालवण्यासाठी डिझाईन केलेलं — किंवा हातानेही:
    python3 refresh_market_zones.py --token <UPSTOX_TOKEN>
"""
import argparse
import sys

import cloud_db
from market_zones import compute_all_zones
from real_nifty_data import resample_ohlc
from signals import resample_to_1h
from upstox_api import fetch_candles


def refresh_symbol(access_token, symbol, lookback_days=365):
    """एका symbol साठी संपूर्ण विश्लेषण करून Supabase मध्ये साठवणे."""
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — NIFTY साठी आता established, रोज-अद्ययावत होणारा
    # nifty_1min_ohlc (Supabase) वापरतो — प्रत्येक वेळी थेट Upstox कडून (मर्यादित lookback सह) डेटा
    # मागवून calculations अस्थिर होऊ नयेत म्हणून. इतर symbols (BANKNIFTY/SENSEX) साठी अजूनही established
    # थेट Upstox-fetch मार्गच (त्यांच्यासाठी अजून 1-मिनिट Supabase इतिहास साठवलेला नाही).
    if symbol == "NIFTY":
        df_1min = cloud_db.get_nifty_1min_range()
        if df_1min is None or df_1min.empty:
            return False, f"{symbol}: Supabase मध्ये 1-मिनिट डेटा नाही -- आधी migrate_nifty_1min_to_supabase.py चालवा."
        df_1h = resample_ohlc(df_1min, 60)
        df_15m = resample_ohlc(df_1min, 15)
    else:
        # 🎓 वापरकर्त्याने प्रत्यक्ष Dashboard वर दाखवलेला खरा bug — इथे आधी थेट
        # fetch_candles(interval="1hour", ...) कॉल केलं जायचं, पण established fetch_candles() मध्ये
        # "1hour" हा allowed_intervals यादीतच नाही — त्यामुळे तो शांतपणे "30minute" कडे fallback व्हायचा,
        # आणि resample न होताच "1H zones" प्रत्यक्षात 30-मिनिटांच्या candles वरूनच मोजले जायचे. आता
        # established fetch_timeframe_df()/resample_to_1h() च्याच पॅटर्नने, स्पष्टपणे 30मिनिट->1H resample.
        df_30m = fetch_candles(access_token, symbol, current_spot=0, interval="30minute", lookback_days=lookback_days)
        df_1h = resample_to_1h(df_30m) if df_30m is not None and not df_30m.empty else df_30m
        df_15m = fetch_candles(access_token, symbol, current_spot=0, interval="15minute", lookback_days=lookback_days)

    if df_1h is None or df_1h.empty:
        return False, f"{symbol}: 1H डेटा मिळाला नाही"

    zones_df = compute_all_zones(df_1h, df_15m if df_15m is not None else df_1h.iloc[:0], symbol=symbol)
    if zones_df.empty:
        return False, f"{symbol}: पुरेसा इतिहास नाही (किमान २० candles प्रति timeframe हवेत) -- कुठलेही zones सापडले नाहीत."
    saved = cloud_db.save_market_zones(zones_df, symbol)
    if not saved:
        return False, f"{symbol}: Supabase मध्ये साठवता आलं नाही (जोडणी तपासा)"
    active_count = (zones_df["status"] == "ACTIVE").sum()
    return True, f"{symbol}: {len(zones_df)} zones साठवले ({active_count} अजून ACTIVE)"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    args = parser.parse_args()

    cloud_db.init_cloud_table()
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)
    all_ok = True
    for symbol in args.symbols.split(","):
        ok, message = refresh_symbol(token, symbol.strip())
        print(("✅ " if ok else "❌ ") + message)
        all_ok = all_ok and ok

    sys.exit(0 if all_ok else 1)
