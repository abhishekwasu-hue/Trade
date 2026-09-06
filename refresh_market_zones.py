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
from signals import resample_to_1h
from upstox_api import fetch_candles


def refresh_symbol(access_token, symbol, lookback_days=365):
    """
    एका symbol साठी संपूर्ण विश्लेषण करून Supabase मध्ये साठवणे.

    🎓 वापरकर्त्याने प्रत्यक्ष Dashboard वर दाखवलेला खरा शोध — अधिकृत Upstox दस्तऐवजीकरणानुसार
    ("1minute: last 1 month candles till endDate"), Upstox कडून 1-मिनिट डेटा कधीच एका रोलिंग
    १-महिन्यापेक्षा जास्त मागे जाऊच शकत नाही — म्हणजे established parquet (2015-2024-03-27) आणि
    established रोजचा नवीन डेटा यांच्यामधला संपूर्ण ऐतिहासिक गॅप (2024-03-27 ते ~१ महिन्यापूर्वी)
    कधीच पूर्णपणे भरता येणार नाही. यामुळे NIFTY साठी established nifty_1min_ohlc (Supabase) वरून
    Market Zones काढल्यास ते जुन्याच (2024-03-27 पूर्वीच्या) किमतींवर आधारित राहायचे, सद्य किमतीशी
    (established उदा. NIFTY 23897) पूर्णपणे विसंगत.

    दुरुस्ती — Market Zones साठी (established backtest/1-मिनिट रणनींतींसाठी nifty_1min_ohlc कायम
    असला तरी) आता सर्व symbols (established NIFTY सकट) established इतर symbols (BANKNIFTY/SENSEX)
    सारखाच, थेट Upstox 30-मिनिट (established १ वर्षाचा lookback, resample करून 1H) मार्ग वापरतो —
    established जेणेकरून zones सद्य किमतीशी सुसंगत, अद्ययावत राहतील.
    """
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
