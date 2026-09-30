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
फक्त 15M/30M/60M साठी compute_dynamic_sr() चालवतं, आणि cloud_db.merge_dynamic_sr_zones() ने (जुने
level_price जपून, गेलेले STALE, कधीच DELETE नाही) फक्त तेच zone_types merge करतं — 1M/5M, स्थिर
SUPPORT/RESISTANCE, Order Block/Demand-Supply/Gap यांना अजिबात हात लागत नाही.

चालवणे (VPS वर, बाजार सत्रादरम्यान दिवसातून काही वेळा — deploy/README.md मध्ये crontab तयार आहे):
    python3 refresh_market_zones_intraday.py --token <UPSTOX_TOKEN>
"""
import argparse
import sys

import cloud_db
from config import get_ist_now
from sr_dynamic import compute_dynamic_sr
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

    # 🎓 "levels calculation by updating levels in database repeatedly" audit — आधी इथे
    # save_market_zones(scoped=True) (delete+insert) वापरलं जायचं: प्रत्येक run ला level_price थोडे बदलायचे
    # → Multi-Hit counter (signal_log मधला exact level_price match) आणि SL/TSL cooldown आपोआप reset
    # (त्याच level वर पुन्हा entry शक्य). आता 5M/1M प्रमाणेच merge — जुळणारा (±0.02%) जुना level_price
    # कायम, नवीन जोडले जातात, गेलेले STALE होतात (कधीच DELETE नाही) — म्हणून दर 15 मिनिटांनीही सुरक्षित.
    merged, skipped = [], []
    for tf_label, df_tf in (("15M", df_15m), ("30M", df_30m), ("60M", df_60m)):
        if df_tf is None or len(df_tf) < 100:
            skipped.append(tf_label)
            continue
        dyn_sr = compute_dynamic_sr(df_tf, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        if not cloud_db.merge_dynamic_sr_zones(symbol, dyn_sr, tf_label, formed_date=get_ist_now()):
            return False, f"{symbol}: {tf_label} levels merge अयशस्वी (रिकामा निकाल किंवा Supabase जोडणी) — जुने levels कायम"
        merged.append(tf_label)

    if not merged:
        return False, f"{symbol}: पुरेसा 15M/30M/60M इतिहास नाही (किमान 100 candles प्रति timeframe हवेत) — zones साठवले नाहीत"
    return True, f"{symbol}: {'+'.join(merged)} levels merge यशस्वी (इतर zone_types अबाधित" + (f"; अपुऱ्या डेटामुळे वगळले: {', '.join(skipped)}" if skipped else "") + ")"


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
