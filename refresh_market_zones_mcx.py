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
import json
import os
import sys

import pandas as pd

import cloud_db
import resolve_mcx_futures_instruments as mcx_resolver
from signals import resample_to_1h
from level_memory import merge_levels
from sr_dynamic import compute_dynamic_sr
from upstox_api import fetch_mcx_candles

MCX_FUTURES_SYMBOLS = mcx_resolver.MCX_FUTURES_SYMBOLS


# 🎓 Level memory सुरक्षितता: कोणत्या contract वरून levels साठवले ते (symbol -> trading_symbol). contract बदलला (roll) किंवा नोंदच नाही
# (पहिली run) ⇒ memory reset — जुन्या contract चे levels calendar spread मुळे नव्या contract वर चुकीच्या किंमतीवर पडतात. bot चा
# check_contract_roll symbol बंद असताना चालत नाही, म्हणून ही तपासणी refresh मध्येच.
LEVELS_CONTRACT_STATE = os.path.join("data", "mcx_levels_contract.json")


def _load_contract_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_contract_state(state, path):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


DYNAMIC_TYPES = ("DYNAMIC_SR_SUPPORT_30M", "DYNAMIC_SR_RESISTANCE_30M", "DYNAMIC_SR_SUPPORT_60M", "DYNAMIC_SR_RESISTANCE_60M")


def _memory_settings(symbol):
    try:
        st = cloud_db.get_strategy_settings("mcx_futures", symbol)
    except Exception:
        st = {}
    return bool(st.get("level_memory_enabled", True)), int(st.get("level_memory_retire_days", 30) or 30)


def _existing_levels(symbol, suffix):
    """त्या TF चे सध्याचे ACTIVE Dynamic S/R levels (support+resistance एकत्र) -- level memory साठी. वाचता आलं नाही ⇒ []."""
    try:
        zones = cloud_db.get_market_zones(symbol, status="ACTIVE")
    except Exception:
        return []
    if zones is None or getattr(zones, "empty", True):
        return []
    rows = zones[zones["zone_type"].isin([f"DYNAMIC_SR_SUPPORT_{suffix}", f"DYNAMIC_SR_RESISTANCE_{suffix}"])]
    return [{"level": float(r.zone_low), "strength": r.strength, "formed_date": r.formed_date} for r in rows.itertuples()]


def _rows_for(suffix, dyn_sr, df, symbol, now_date, use_memory, retire_days):
    """एका TF च्या zone रांगा. use_memory ⇒ level_memory.merge_levels (जुने levels त्याच किंमतीवर); नाहीतर फक्त ताजी गणना (जुनं वर्तन)."""
    fresh = [{"level": z["level"], "touches": z["touches"]} for z in dyn_sr.get("support", []) + dyn_sr.get("resistance", [])]
    price = float(df["close"].iloc[-1])
    if use_memory:
        merged = merge_levels(_existing_levels(symbol, suffix), fresh, df, price, now_date, retire_days=retire_days)
        return [{"zone_type": f"DYNAMIC_SR_{z['role']}_{suffix}", "zone_low": z["level"], "zone_high": z["level"], "strength": z["strength"],
                 "formed_date": z["formed_date"], "status": "ACTIVE"} for z in merged], sum(1 for z in merged if not z["fresh"])
    rows = []
    for role, key in (("SUPPORT", "support"), ("RESISTANCE", "resistance")):
        for z in dyn_sr.get(key, []):
            rows.append({"zone_type": f"DYNAMIC_SR_{role}_{suffix}", "zone_low": z["level"], "zone_high": z["level"],
                         "strength": z["touches"], "formed_date": now_date, "status": "ACTIVE"})
    return rows, 0


def refresh_symbol(access_token, symbol, lookback_days=180, reset=False, state_path=None):
    """एका MCX commodity साठी DYNAMIC_SR_*_30M/*_60M zones — resolve_symbol() ने current
    continuous contract शोधून, त्याचेच 30M candles (व त्यांच्याच resample वरून 60M) वापरून.
    lookback_days=180 — refresh_market_zones.py च्या df_30m_recent/df_60m_recent इतकाच (TradingView
    च्या लोड झालेल्या इतिहासाच्या जास्त जवळ जाण्यासाठी, established निर्णय).
    🎓 Level memory (`level_memory_enabled`, डीफॉल्ट चालू) — जुने levels त्याच किंमतीवर ठेवले जातात (बघा level_memory.py). `reset=True`
    (contract roll नंतर) ⇒ जुने levels विसरले जातात (जुन्या contract चे भाव calendar spread मुळे वेगळे). फक्त DYNAMIC_SR_*_30M/*_60M
    प्रकारच पुसले/लिहिले जातात (आधी symbol चे सर्व zones पुसले जायचे — SR V3 चे levels सकट)."""
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
    now_date = df_30m["timestamp"].iloc[-1]
    memory_on, retire_days = _memory_settings(symbol)
    state_path = state_path or LEVELS_CONTRACT_STATE
    contract_state = _load_contract_state(state_path)
    contract = resolved.get("trading_symbol") or instrument_key
    contract_changed = contract_state.get(symbol) != contract          # roll किंवा पहिली नोंद ⇒ memory reset
    use_memory = memory_on and not reset and not contract_changed

    rows, remembered = [], 0
    dyn_sr_30m = compute_dynamic_sr(df_30m, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
    r30, k30 = _rows_for("30M", dyn_sr_30m, df_30m, symbol, now_date, use_memory, retire_days)
    rows += r30
    remembered += k30
    if df_60m is not None and len(df_60m) >= 100:
        dyn_sr_60m = compute_dynamic_sr(df_60m, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        r60, k60 = _rows_for("60M", dyn_sr_60m, df_60m, symbol, now_date, use_memory, retire_days)
        rows += r60
        remembered += k60

    if not rows:
        return False, f"{symbol}: कुठलेही Dynamic S/R levels सापडले नाहीत (पुरेसा pivot-डेटा नाही)"

    zones_df = pd.DataFrame(rows)
    saved = cloud_db.save_market_zones(zones_df, symbol, scoped=True, zone_types=list(DYNAMIC_TYPES))
    if not saved:
        return False, f"{symbol}: Supabase मध्ये साठवता आलं नाही (जोडणी तपासा)"
    contract_state[symbol] = contract
    _save_contract_state(contract_state, state_path)
    mem = (f"; level memory: {remembered} जुने levels त्याच किंमतीवर ठेवले" if use_memory
           else ("; contract roll — जुने levels विसरले" if reset else
                 (f"; contract {contract} (नवा/पहिली नोंद) — जुने levels विसरले, memory पुढच्या refresh पासून" if contract_changed
                  else "; level memory बंद")))
    return True, f"{symbol} ({resolved['trading_symbol']}): {len(zones_df)} zones साठवले (30M+60M){mem}"


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
