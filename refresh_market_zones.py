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
from upstox_api import fetch_candles


def refresh_symbol(access_token, symbol, lookback_days=365):
    """एका symbol साठी संपूर्ण विश्लेषण करून Supabase मध्ये साठवणे."""
    df_1h = fetch_candles(access_token, symbol, current_spot=0, interval="1hour", lookback_days=lookback_days)
    df_15m = fetch_candles(access_token, symbol, current_spot=0, interval="15minute", lookback_days=lookback_days)
    if df_1h is None or df_1h.empty:
        return False, f"{symbol}: 1H डेटा मिळाला नाही"

    zones_df = compute_all_zones(df_1h, df_15m if df_15m is not None else df_1h.iloc[:0], symbol=symbol)
    saved = cloud_db.save_market_zones(zones_df, symbol)
    if not saved:
        return False, f"{symbol}: Supabase मध्ये साठवता आलं नाही (जोडणी तपासा)"
    active_count = (zones_df["status"] == "ACTIVE").sum()
    return True, f"{symbol}: {len(zones_df)} zones साठवले ({active_count} अजून ACTIVE)"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    args = parser.parse_args()

    cloud_db.init_cloud_table()
    all_ok = True
    for symbol in args.symbols.split(","):
        ok, message = refresh_symbol(args.token, symbol.strip())
        print(("✅ " if ok else "❌ ") + message)
        all_ok = all_ok and ok

    sys.exit(0 if all_ok else 1)
