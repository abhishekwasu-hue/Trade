"""
collect_index_futures_volume.py
---------------------------------
🎓 Opportunity Engine (PR-2): NIFTY/BANKNIFTY च्या **front-month futures** चे 5M candles (volume + OI) आणि त्याच काळाचे index 5M candles दररोज
साठवणे — फक्त **वाचतो** (Upstox GET; कुठलाही order नाही, कुठलाही DB write नाही). कारण: PR-0 नुसार expired futures चा जुना volume Upstox Plus शिवाय
मिळत नाही (HTTP 401), म्हणून volume-सकट backtest साठी डेटा आजपासून पुढे गोळा करायचा (वापरकर्त्याने निवडलेला मोफत पर्याय).

साठवण (repo मध्ये commit होत नाही — .gitignore):
    data/oe_futures_5min_<SYMBOL>.parquet   (timestamp, open, high, low, close, volume, oi, contract)
    data/oe_index_5min_<SYMBOL>.parquet     (timestamp, open, high, low, close, volume, oi)
    data/oe_futures_5min_<SYMBOL>_all.parquet  (front + पुढचा contract, key = timestamp + contract — Chart Reader K10.3 चा volume roll)
एकाच timestamp चा आधी साठवलेला row ठेवला जातो (rollover नंतर पुढच्या contract चे जुने दिवस front-month चा डेटा बदलत नाहीत).

चालवणे (VPS वर, रोज बाजार बंद झाल्यावर; मागचे 5 दिवस पुन्हा मागवले जातात म्हणून एखादा दिवस चुकला तरी भरून निघतो):
    python3 collect_index_futures_volume.py
    python3 collect_index_futures_volume.py --symbols NIFTY --days 10
"""
import argparse
import datetime
import os
import sys

import pandas as pd

import cloud_db
import verify_opportunity_data_availability as V
from config import get_ist_today
from opportunity_engine.volume import candles_to_df, merge_store, merge_store_by_contract
from upstox_api import SYMBOL_INSTRUMENT_KEYS

DATA_DIR = "data"


def store_path(kind, symbol, data_dir=DATA_DIR):
    return os.path.join(data_dir, f"oe_{kind}_5min_{symbol.upper()}.parquet")


def _merge_into(path, new):
    old = pd.read_parquet(path) if os.path.exists(path) else None
    merged = merge_store(old, new)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    merged.to_parquet(path, index=False)
    return len(merged) - (0 if old is None else len(old)), len(merged)


def _merge_all(path, new):
    old = pd.read_parquet(path) if os.path.exists(path) else None
    merged = merge_store_by_contract(old, new)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    merged.to_parquet(path, index=False)
    return len(merged) - (0 if old is None else len(old)), len(merged)


def collect_symbol(token, symbol, days, today, data_dir=DATA_DIR, log=print):
    """एका symbol चे futures + index 5M candles. रिटर्न dict (rows, नवीन rows, volume>0 %, contract) किंवा error."""
    info, err = V.resolve_front_future(token, symbol, today)
    if info is None:
        return {"symbol": symbol, "error": f"futures contract सापडला नाही: {err}"}
    start = today - datetime.timedelta(days=days)
    out = {"symbol": symbol, "contract": info["trading_symbol"], "instrument_key": info["instrument_key"], "expiry": info["expiry"]}
    fut = V.fetch_candles_window(token, info["instrument_key"], "5minute", start, today)
    if fut["status"] != 200:
        out["error"] = f"futures candles: HTTP {fut['status']} {fut['error']}"
        return out
    fdf = candles_to_df(fut["candles"], contract=info["trading_symbol"])
    added, total = _merge_into(store_path("futures", symbol, data_dir), fdf)
    out.update({"futures_rows": len(fdf), "futures_added": added, "futures_total": total,
                "volume_nonzero_pct": round(100.0 * (fdf["volume"] > 0).mean(), 1) if len(fdf) else 0.0})
    # पुढचा contract सुद्धा (K10.3 roll) — `_all` store मध्ये, front सोबत. अपयश ⇒ फक्त नोंद (front data वर परिणाम नाही).
    try:
        parts = [fdf]
        chain, cerr = V.resolve_futures_chain(token, symbol, today, n=2)
        for nxt in [c for c in chain if c["instrument_key"] != info["instrument_key"]]:
            nf = V.fetch_candles_window(token, nxt["instrument_key"], "5minute", start, today)
            if nf["status"] == 200:
                parts.append(candles_to_df(nf["candles"], contract=nxt["trading_symbol"]))
                out["next_contract"] = nxt["trading_symbol"]
            else:
                out["next_error"] = f"HTTP {nf['status']} {nf['error']}"
        if cerr:
            out["next_error"] = cerr
        added_all, total_all = _merge_all(os.path.join(data_dir, f"oe_futures_5min_{symbol.upper()}_all.parquet"),
                                          pd.concat([p for p in parts if len(p)], ignore_index=True) if any(len(p) for p in parts) else fdf)
        out.update({"all_added": added_all, "all_total": total_all})
    except Exception as exc:                                             # नवीन पायरीचं अपयश ⇒ फक्त नोंद; front / index collection चालू राहते
        out["next_error"] = f"{type(exc).__name__}: {exc}"
    idx_key = SYMBOL_INSTRUMENT_KEYS.get(symbol.upper())
    if idx_key:
        ix = V.fetch_candles_window(token, idx_key, "5minute", start, today)
        if ix["status"] == 200:
            idf = candles_to_df(ix["candles"])
            added_i, total_i = _merge_into(store_path("index", symbol, data_dir), idf)
            out.update({"index_rows": len(idf), "index_added": added_i, "index_total": total_i})
        else:
            out["index_error"] = f"HTTP {ix['status']} {ix['error']}"
    log(f"  {symbol}: {out.get('contract')} | futures +{out.get('futures_added', 0)} (एकूण {out.get('futures_total', 0)}, volume>0 {out.get('volume_nonzero_pct')}%)"
        f" | index +{out.get('index_added', 0)} (एकूण {out.get('index_total', 0)})")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=None, help="Upstox Access Token (न दिल्यास Supabase मधून)")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY")
    parser.add_argument("--days", type=int, default=5, help="इतके मागचे दिवस पुन्हा मागवा (overlap; डीफॉल्ट 5)")
    parser.add_argument("--data-dir", default=DATA_DIR)
    args = parser.parse_args(argv)
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ Upstox token उपलब्ध नाही (--token नाही, Supabase मध्येही नाही).")
        return 1
    today = get_ist_today()
    print(f"Index futures volume collector — {today} (मागचे {args.days} दिवस)")
    bad = 0
    for sym in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        r = collect_symbol(token, sym, args.days, today, args.data_dir)
        if r.get("error"):
            bad += 1
            print(f"  ❌ {sym}: {r['error']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
