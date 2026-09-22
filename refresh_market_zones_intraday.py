"""
refresh_market_zones_intraday.py
------------------------------------
NIFTY/BANKNIFTY/SENSEX चे DYNAMIC_SR_*_15M/30M/60M zones — बाजार चालू असताना (intraday) वारंवार
ताजे करण्यासाठी, refresh_market_zones.py (रोज एकदाच, बाजार बंद झाल्यावर चालणारा, संपूर्ण
विश्लेषण — SUPPORT/RESISTANCE/Order Block/Demand-Supply/Gap/1M/5M/15M/30M/60M सगळंच) पासून
**मुद्दाम पूर्णपणे स्वतंत्र** नवीन, लहान script.

🎓 वापरकर्त्याशी चर्चा करून ठरलेला डिझाईन निर्णय — refresh_market_zones.py ला थेट intraday चालवणं
धोकादायक ठरलं असतं: तो त्याच वेळी DYNAMIC_SR_*_1M/*_5M zones सुद्धा नव्याने काढून जुने सगळे
zone_types (cloud_db.save_market_zones() चं symbol-व्यापी DELETE) पुसून टाकतो — आणि तेच 1M/5M
zones dynamic_sr_instant_trader.py बाजार चालू असताना दर मिनिटाला, जुने कधीच न काढता फक्त STALE
करणाऱ्या पद्धतीने live जपत असतो, त्यावरच प्रत्यक्ष trade चालू असू शकतो. त्यामुळे हे script फक्त
market_zones.compute_intraday_sr_zones() (15M/30M/60M पुरतंच मर्यादित) वापरतं, आणि
cloud_db.save_market_zones(..., scoped=True) ने फक्त तेच सहा zone_types replace करतं — 1M/5M,
स्थिर SUPPORT/RESISTANCE, Order Block/Demand-Supply/Gap यांना अजिबात हात लागत नाही.

चालवणे (VPS वर, बाजार सत्रादरम्यान दिवसातून काही वेळा — deploy/README.md मध्ये crontab तयार आहे):
    python3 refresh_market_zones_intraday.py --token <UPSTOX_TOKEN>
"""
import argparse
import sys

import cloud_db
from market_zones import compute_intraday_sr_zones
from signals import resample_to_1h
from upstox_api import fetch_candles

INTRADAY_SR_SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]


def refresh_symbol(access_token, symbol, lookback_days=180):
    """एका symbol साठी DYNAMIC_SR_*_15M/30M/60M zones — refresh_market_zones.py मधल्याच
    df_15m_recent/df_30m_recent/df_60m_recent इतकाच lookback_days=180 (established निर्णय,
    TradingView च्या लोड झालेल्या इतिहासाच्या जास्त जवळ जाण्यासाठी)."""
    df_15m = fetch_candles(access_token, symbol, current_spot=0, interval="15minute", lookback_days=lookback_days)
    if df_15m is not None and df_15m.attrs.get("failed_chunks", 0) > 0:
        return False, f"{symbol}: 15-मिनिट इतिहासाचे {df_15m.attrs['failed_chunks']} chunk(s) मिळाले नाहीत — या वेळचे zones साठवले नाहीत (जुनेच कायम राहतील)."

    df_30m = fetch_candles(access_token, symbol, current_spot=0, interval="30minute", lookback_days=lookback_days)
    if df_30m is not None and df_30m.attrs.get("failed_chunks", 0) > 0:
        return False, f"{symbol}: 30-मिनिट इतिहासाचे {df_30m.attrs['failed_chunks']} chunk(s) मिळाले नाहीत — या वेळचे zones साठवले नाहीत (जुनेच कायम राहतील)."

    df_60m = resample_to_1h(df_30m) if df_30m is not None and not df_30m.empty else df_30m

    zones_df = compute_intraday_sr_zones(
        symbol,
        df_15m_recent=df_15m if df_15m is not None and not df_15m.empty else None,
        df_30m_recent=df_30m if df_30m is not None and not df_30m.empty else None,
        df_60m_recent=df_60m if df_60m is not None and not df_60m.empty else None,
    )
    if zones_df.empty:
        return False, f"{symbol}: पुरेसा 15M/30M/60M इतिहास नाही (किमान 100 candles प्रति timeframe हवेत) — zones साठवले नाहीत"

    saved = cloud_db.save_market_zones(zones_df, symbol, scoped=True)
    if not saved:
        return False, f"{symbol}: Supabase मध्ये साठवता आलं नाही (जोडणी तपासा)"
    return True, f"{symbol}: {len(zones_df)} zones साठवले (15M+30M+60M, इतर zone_types अबाधित)"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(INTRADAY_SR_SYMBOLS))
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
