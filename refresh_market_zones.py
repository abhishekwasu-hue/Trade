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
from notifications import notify_error
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

    🎓 established SRv2 Momentum-Filter Reversal (established, 15-मिनिट candles) साठी वेगळा,
    अलीकडचा डेटासेट — df_15m_recent (DYNAMIC_SR_*_15M नावाने साठवलं जातं). Dynamic S/R Instant
    Reversal Trader (established, 1-मिनिट + 5-मिनिट candles, तात्काळ) साठी df_1m_recent/
    df_5m_recent — दोन्ही रोज रात्री इथेच ताजी पुन्हा-गणना होतात (DYNAMIC_SR_*_1M/*_5M), जेणेकरून
    refresh_dynamic_sr_1m.py/refresh_dynamic_sr_5m.py च्या दर-५-मिनिटांच्या merge-cron ने दिवसभर
    जपलेले, पण आता जुने झालेले levels रोज योग्यरित्या ताजे होतात — कायमचे गोठलेले राहत नाहीत.

    🎓 वापरकर्त्याने सापडवलेली bug — SRv2 Momentum-Filter Reversal प्रत्यक्षात 15M/30M/60M
    तिन्ही timeframes तपासतो (srv2_momentum_reversal_strategy.TIMEFRAME_TO_SUFFIX), पण df_30m_recent/
    df_60m_recent आधी इथे कधीच मागवले जायचेच नाहीत — त्यामुळे DYNAMIC_SR_*_30M/*_60M zones कधीच
    तयार व्हायचे नाहीत, आणि त्या दोन timeframes साठी Signal Log कायमचा रिकामा राहायचा. आता
    df_15m_recent सारखाच, df_30m_recent थेट मागवला जातो; df_60m_recent त्याच्याच resample वरून
    (Upstox कडून "1hour" interval verified नसल्याने — fetch_timeframe_df() मध्ये आधीच वापरलेला पॅटर्न).
    """
    df_30m = fetch_candles(access_token, symbol, current_spot=0, interval="30minute", lookback_days=lookback_days)
    # 🎓 वापरकर्त्याने Market Zones export मधून सापडवलेली, गंभीर bug — एखादा historical chunk
    # (Upstox API कडून, नेटवर्क/rate-limit मुळे) अयशस्वी झाला तरी fetch_candles() आधी शांतपणे
    # (Streamlit-only st.warning() मार्फत, जे headless cron मध्ये no-op होतं) फक्त तेवढाच भाग गाळून
    # पुढे जायचं — म्हणजे df_30m/df_15m मध्ये काही महिन्यांचं अंतर (gap) राहायचं, आणि नेमकं त्याच
    # काळात किंमत एखाद्या जुन्या zone मधून प्रत्यक्ष गेली असली तरी mitigation-तपासणीला (is_zone_mitigated())
    # ते कधीच दिसायचं नाही — जुनी Bullish Order Block/Demand Zone (किंमत आता खूप खाली गेल्यावरही)
    # कायमची चुकीने ACTIVE दाखवत राहायची. आता असा gap आढळला की त्या symbol साठी आजचं साठवणंच
    # वगळतो (जुनाच, शक्यतो बरोबर असलेला डेटा तसाच ठेवून) — अर्धवट/चुकीच्या डेटावरून पुन्हा-गणना
    # करून जुना योग्य निकाल खराब करण्यापेक्षा हे सुरक्षित.
    if df_30m is not None and df_30m.attrs.get("failed_chunks", 0) > 0:
        msg = f"{symbol}: 30-मिनिट इतिहासाचे {df_30m.attrs['failed_chunks']} chunk(s) मिळाले नाहीत — आजचे zones साठवले नाहीत (जुनेच कायम राहतील)."
        notify_error("refresh_market_zones", msg)
        return False, msg
    df_1h = resample_to_1h(df_30m) if df_30m is not None and not df_30m.empty else df_30m
    df_15m = fetch_candles(access_token, symbol, current_spot=0, interval="15minute", lookback_days=lookback_days)
    if df_15m is not None and df_15m.attrs.get("failed_chunks", 0) > 0:
        msg = f"{symbol}: 15-मिनिट इतिहासाचे {df_15m.attrs['failed_chunks']} chunk(s) मिळाले नाहीत — आजचे zones साठवले नाहीत (जुनेच कायम राहतील)."
        notify_error("refresh_market_zones", msg)
        return False, msg

    # 🎓 वापरकर्त्याने चार्ट वि. प्रत्यक्ष trading मधल्या विसंगतीवरून सापडवलेली bug — established
    # Dynamic S/R (established, 1-मिनिट Instant Trader साठी वापरला जाणारा) साठी established df_15m
    # (संपूर्ण lookback_days, established डीफॉल्ट ३६५ दिवस) ऐवजी established वेगळा, established
    # Dashboard चार्टच्याच डीफॉल्ट इतका (established 15-मिनिटसाठी established Upstox चा स्वतःचा
    # डीफॉल्ट — established उदा. २० दिवस) **अलीकडचा** डेटा — established संपूर्ण वर्षभरातून
    # established सर्वात टोकाचे (जुने, सद्य किमतीपासून दूर) points निवडले जाऊ नयेत म्हणून.
    df_15m_recent = fetch_candles(access_token, symbol, current_spot=0, interval="15minute")  # established डीफॉल्ट lookback (chart-सारखाच)
    df_1m_recent = fetch_candles(access_token, symbol, current_spot=0, interval="1minute")  # Upstox चा स्वतःचा डीफॉल्ट lookback (1-मिनिटसाठी ~5 दिवस)
    df_5m_recent = fetch_candles(access_token, symbol, current_spot=0, interval="5minute")  # Upstox चा स्वतःचा डीफॉल्ट lookback (5-मिनिटसाठी ~10 दिवस)
    df_30m_recent = fetch_candles(access_token, symbol, current_spot=0, interval="30minute")  # डीफॉल्ट lookback (chart-सारखाच, ~60 दिवस)
    # "1hour" Upstox कडून थेट verified नाही (fetch_timeframe_df() प्रमाणेच) — 30-मिनिट resample करून.
    df_60m_recent = resample_to_1h(df_30m_recent) if df_30m_recent is not None and not df_30m_recent.empty else df_30m_recent

    if df_1h is None or df_1h.empty:
        return False, f"{symbol}: 1H डेटा मिळाला नाही"

    zones_df = compute_all_zones(
        df_1h, df_15m if df_15m is not None else df_1h.iloc[:0], symbol=symbol,
        df_15m_recent=df_15m_recent if df_15m_recent is not None and not df_15m_recent.empty else None,
        df_1m_recent=df_1m_recent if df_1m_recent is not None and not df_1m_recent.empty else None,
        df_5m_recent=df_5m_recent if df_5m_recent is not None and not df_5m_recent.empty else None,
        df_30m_recent=df_30m_recent if df_30m_recent is not None and not df_30m_recent.empty else None,
        df_60m_recent=df_60m_recent if df_60m_recent is not None and not df_60m_recent.empty else None,
    )
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
