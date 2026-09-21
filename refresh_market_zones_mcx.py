"""
refresh_market_zones_mcx.py
------------------------------------
MCX Futures साठी Dynamic S/R (30M/60M) — refresh_market_zones.py (NIFTY/BANKNIFTY/SENSEX, पूर्ण
Order Block/Demand-Supply/Gap विश्लेषणासह) पासून पूर्णपणे स्वतंत्र, नवीन, लहान script — MCX ला फक्त
mcx_futures_trader.py च्या Entry Gate ला हवे तेवढेच (30M/60M Dynamic S/R) लागतं, Order Block/
Demand-Supply/Gap संकल्पना MCX strategy मध्ये मुळातच वापरल्या जात नाहीत.

resolve_mcx_futures_instruments.resolve_symbol() ने मिळालेल्या current/continuous front-month
contract वरून upstox_api.fetch_mcx_candles() ने 30-मिनिट candles मागवून (60-मिनिट त्याच्याच
resample वरून — Upstox कडून "1hour" थेट verified नसल्याने, established पॅटर्न), sr_dynamic.
compute_dynamic_sr() नेच (market_zones.compute_all_zones() मध्ये DYNAMIC_SR_*_30M/*_60M साठी
established वापरलेल्याच parameters सह) DYNAMIC_SR_SUPPORT_30M/DYNAMIC_SR_RESISTANCE_30M/
DYNAMIC_SR_SUPPORT_60M/DYNAMIC_SR_RESISTANCE_60M zone_types साठवतो.

cloud_db.save_market_zones()/get_market_zones() दोन्ही symbol-scoped (WHERE symbol=%s) आहेत —
त्यामुळे हे NIFTY/BANKNIFTY/SENSEX च्या zones ला अजिबात स्पर्श करत नाही.

चालवणे (VPS वर, रोज बाजार बंद झाल्यावर — deploy/README.md मध्ये crontab तयार आहे, अजून सक्रिय नाही):
    python3 refresh_market_zones_mcx.py --token <UPSTOX_TOKEN>
"""
import argparse
import sys

import pandas as pd

import cloud_db
import resolve_mcx_futures_instruments as mcx_resolver
from signals import resample_to_1h
from sr_dynamic import compute_dynamic_sr
from upstox_api import fetch_mcx_candles

MCX_FUTURES_SYMBOLS = mcx_resolver.MCX_FUTURES_SYMBOLS


def refresh_symbol(access_token, symbol, lookback_days=180):
    """एका MCX commodity साठी DYNAMIC_SR_*_30M/*_60M zones — resolve_symbol() ने current
    continuous contract शोधून, त्याचेच 30M candles (व त्यांच्याच resample वरून 60M) वापरून.
    lookback_days=180 — refresh_market_zones.py च्या df_30m_recent/df_60m_recent इतकाच (TradingView
    च्या लोड झालेल्या इतिहासाच्या जास्त जवळ जाण्यासाठी, established निर्णय)."""
    ok, resolved = mcx_resolver.resolve_symbol(access_token, symbol)
    if not ok:
        return False, f"{symbol}: सध्याचा (current/continuous) Futures contract सापडला नाही ({resolved})"

    instrument_key = resolved["instrument_key"]
    df_30m = fetch_mcx_candles(access_token, instrument_key, interval="30minute", lookback_days=lookback_days)
    if df_30m is not None and df_30m.attrs.get("failed_chunks", 0) > 0:
        msg = f"{symbol}: 30-मिनिट इतिहासाचे {df_30m.attrs['failed_chunks']} chunk(s) मिळाले नाहीत — आजचे zones साठवले नाहीत (जुनेच कायम राहतील)."
        return False, msg
    if df_30m is None or len(df_30m) < 100:
        return False, f"{symbol}: पुरेसा 30-मिनिट इतिहास नाही (किमान 100 candles हवेत) — zones साठवले नाहीत"

    df_60m = resample_to_1h(df_30m)

    rows = []
    now_date = df_30m["timestamp"].iloc[-1]

    dyn_sr_30m = compute_dynamic_sr(df_30m, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
    for s in dyn_sr_30m.get("support", []):
        rows.append({"zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": s["level"], "zone_high": s["level"],
                     "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
    for r in dyn_sr_30m.get("resistance", []):
        rows.append({"zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": r["level"], "zone_high": r["level"],
                     "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    if df_60m is not None and len(df_60m) >= 100:
        dyn_sr_60m = compute_dynamic_sr(df_60m, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr_60m.get("support", []):
            rows.append({"zone_type": "DYNAMIC_SR_SUPPORT_60M", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr_60m.get("resistance", []):
            rows.append({"zone_type": "DYNAMIC_SR_RESISTANCE_60M", "zone_low": r["level"], "zone_high": r["level"],
                         "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    if not rows:
        return False, f"{symbol}: कुठलेही Dynamic S/R levels सापडले नाहीत (पुरेसा pivot-डेटा नाही)"

    zones_df = pd.DataFrame(rows)
    saved = cloud_db.save_market_zones(zones_df, symbol)
    if not saved:
        return False, f"{symbol}: Supabase मध्ये साठवता आलं नाही (जोडणी तपासा)"
    return True, f"{symbol} ({resolved['trading_symbol']}): {len(zones_df)} zones साठवले (30M+60M)"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(MCX_FUTURES_SYMBOLS))
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
