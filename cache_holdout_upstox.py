"""
cache_holdout_upstox.py
-----------------------
🎓 Sealed holdout (T1/§0.2 नियम 6): Upstox वरून NIFTY index 5-min candles 2024-04-01 → आज, `data/holdout/` मध्ये साठवणे — **फक्त cache**.
हा डेटा G4 पर्यंत कुठल्याही संशोधनात/tuning मध्ये वापरायचा नाही (एकदाच, अंतिम तपासणीला उघडायचा). म्हणून ही script किंमती/निकाल छापत नाही —
फक्त bars आणि दिवसांची संख्या (आणि फाईलचा sha256, नंतर फाईल बदलली नाही ना हे तपासायला).

  • फक्त वाचतो (Upstox GET); कुठलाही order, DB write नाही. Token: --token किंवा Supabase (`cloud_db.get_effective_upstox_token`) — token कधीही छापला जात नाही.
  • Upstox V3 मिनिट-candles एका request मध्ये ~1 महिना ⇒ 28-दिवसांचे तुकडे.
  • `data/holdout/` .gitignore मध्ये आहे (repo मध्ये कधीही commit होत नाही).

चालवणे (VPS वर; sandbox मधून Upstox पोहोचत नाही):
    python3 cache_holdout_upstox.py
    python3 cache_holdout_upstox.py --symbols NIFTY,BANKNIFTY
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

import pandas as pd

HOLDOUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "holdout")     # repo च्या gitignored folder मध्येच, कुठूनही चालवलं तरी
HOLDOUT_START = datetime.date(2024, 4, 1)
CHUNK_DAYS = 28


def holdout_path(symbol, data_dir=HOLDOUT_DIR):
    return os.path.join(data_dir, f"{symbol.upper()}_5min.parquet")


def chunks(start, end, days=CHUNK_DAYS):
    """[start, end] -> [(from, to), …] (दोन्ही टोके समाविष्ट, ओव्हरलॅप नाही)."""
    out, s = [], start
    while s <= end:
        e = min(s + datetime.timedelta(days=days - 1), end)
        out.append((s, e))
        s = e + datetime.timedelta(days=1)
    return out


def fetch_symbol(fetch, token, instrument_key, start, end):
    """`fetch(token, key, interval, from, to)` -> {"status", "candles", "error"}. रिटर्न (DataFrame, errors list)."""
    from opportunity_engine.volume import candles_to_df
    parts, errors = [], []
    for a, b in chunks(start, end):
        r = fetch(token, instrument_key, "5minute", a, b)
        if r.get("status") != 200:
            errors.append(f"{a}→{b}: HTTP {r.get('status')} {r.get('error') or ''}".strip())
            continue
        if r.get("candles"):
            parts.append(candles_to_df(r["candles"]))
    if not parts:
        return pd.DataFrame(), errors
    df = pd.concat(parts, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    return df[df["timestamp"] >= pd.Timestamp(start)].reset_index(drop=True), errors


def counts_only(df):
    """फक्त संख्या — किंमत/निकाल नाही (holdout sealed)."""
    if df is None or not len(df):
        return {"bars": 0, "days": 0}
    return {"bars": int(len(df)), "days": int(pd.to_datetime(df["timestamp"]).dt.normalize().nunique())}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def cache(symbols, token, today, fetch, keys, data_dir=HOLDOUT_DIR, log=print):
    os.makedirs(data_dir, exist_ok=True)
    manifest = {"created": str(today), "start": str(HOLDOUT_START), "end": str(today), "sealed_until": "G4", "symbols": {}}
    bad = 0
    for sym in symbols:
        key = keys.get(sym.upper())
        if not key:
            log(f"  ❌ {sym}: instrument key सापडला नाही")
            bad += 1
            continue
        df, errors = fetch_symbol(fetch, token, key, HOLDOUT_START, today)
        info = counts_only(df)
        if len(df):
            path = holdout_path(sym, data_dir)
            df.to_parquet(path, index=False)
            info["sha256"] = sha256_of(path)
        info["errors"] = len(errors)
        manifest["symbols"][sym.upper()] = info
        if errors or not len(df):
            bad += 1
        log(f"  {sym}: {info['bars']} bars, {info['days']} दिवस" + (f" · ⚠️ {len(errors)} तुकडे अयशस्वी" if errors else ""))
    with open(os.path.join(data_dir, "MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    return manifest, bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=None, help="Upstox Access Token (न दिल्यास Supabase मधून)")
    ap.add_argument("--symbols", default="NIFTY")
    ap.add_argument("--data-dir", default=HOLDOUT_DIR)
    a = ap.parse_args(argv)
    import cloud_db
    import verify_opportunity_data_availability as V
    from config import get_ist_today
    from upstox_api import SYMBOL_INSTRUMENT_KEYS
    token = cloud_db.get_effective_upstox_token(a.token)
    if not token:
        print("❌ Upstox token उपलब्ध नाही (--token नाही, Supabase मध्येही नाही).")
        return 1
    today = get_ist_today() - datetime.timedelta(days=1)          # चालू (अपूर्ण) दिवस नको — फक्त पूर्ण सत्रे
    print(f"Sealed holdout cache — {HOLDOUT_START} → {today} (फक्त संख्या; डेटा G4 पर्यंत वापरायचा नाही)")
    _, bad = cache([s.strip().upper() for s in a.symbols.split(",") if s.strip()], token, today, V.fetch_candles_window, SYMBOL_INSTRUMENT_KEYS, a.data_dir)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
