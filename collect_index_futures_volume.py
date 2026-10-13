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
Upstox v3 historical minute candles दिवस D चे फक्त D+1 सकाळी (~07:00 IST) येतात ⇒ history (start … काल) + आजचे bars intraday
endpoint मधून (engine3_live सारखे). Intraday अपयश ⇒ history तरीही साठवली जाते, अपयश log मध्ये. SENSEX (BSE FUT) सापडला नाही ⇒ skip.
एकाच timestamp चा आधी साठवलेला row ठेवला जातो (rollover नंतर पुढच्या contract चे जुने दिवस front-month चा डेटा बदलत नाहीत).

चालवणे (VPS वर, रोज बाजार बंद झाल्यावर; मागचे 5 दिवस पुन्हा मागवले जातात म्हणून एखादा दिवस चुकला तरी भरून निघतो):
    python3 collect_index_futures_volume.py
    python3 collect_index_futures_volume.py --symbols NIFTY --days 10
"""
import argparse
import datetime
import os
import sys
import urllib.parse

import pandas as pd

import cloud_db
import verify_opportunity_data_availability as V
from config import get_ist_today
from engine3_live import FUT_EXCHANGE
from opportunity_engine.volume import candles_to_df, merge_store, merge_store_by_contract
from upstox_api import SYMBOL_INSTRUMENT_KEYS

DATA_DIR = "data"
OPTIONAL_SYMBOLS = {"SENSEX"}          # BSE front-month FUT सापडला नाही ⇒ log + skip (बाकी symbols चालू; exit code वर परिणाम नाही)


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


def fetch_intraday(token, instrument_key, interval="5minute"):
    """आजचे (चालू दिवसाचे) candles — Upstox v3 intraday endpoint (engine3_live.UpstoxFeed._series प्रमाणेच). Historical minute candles
    दिवस D चे फक्त D+1 सकाळी (~07:00 IST) येतात, म्हणून 16:10 च्या run ला आजचे bars इथूनच. रिटर्न {"status", "candles", "error"}."""
    unit, val = V._V3_UNITS[interval]
    enc = urllib.parse.quote(instrument_key, safe="")
    status, body, error = V._get(f"{V.BASE_V3}/intraday/{enc}/{unit}/{val}", token)
    candles = (((body or {}).get("data") or {}).get("candles") or []) if status == 200 else []
    return {"status": status, "candles": candles, "error": error}


def _history_plus_today(token, key, start, today, out, tag):
    """History (start … काल) + आजचे intraday. History अपयश ⇒ (None, error). Intraday अपयश ⇒ फक्त नोंद (`out[tag + "_intraday_error"]`),
    history तरीही परत. to_date = काल: to_date = आज दिल्यास Upstox कालचा पूर्ण दिवस वगळतो (engine3_live, 13 Oct)."""
    hist = V.fetch_candles_window(token, key, "5minute", start, today - datetime.timedelta(days=1))
    if hist["status"] != 200:
        return None, f"HTTP {hist['status']} {hist['error']}"
    candles = list(hist["candles"])
    try:
        intra = fetch_intraday(token, key)
    except Exception as exc:                                             # noqa: BLE001 — intraday अपयश ⇒ history तरीही साठवायची
        intra = {"status": None, "candles": [], "error": f"{type(exc).__name__}: {exc}"}
    if intra["status"] == 200:
        candles.extend(intra["candles"])
    else:
        out[f"{tag}_intraday_error"] = f"HTTP {intra['status']} {str(intra['error'])[:120]}"
    return candles, None


def collect_symbol(token, symbol, days, today, data_dir=DATA_DIR, log=print):
    """एका symbol चे futures + index 5M candles (history + आजचे intraday). रिटर्न dict (rows, नवीन rows, volume>0 %, contract) किंवा error.
    OPTIONAL_SYMBOLS (SENSEX) चा front-month FUT सापडला नाही ⇒ `skipped` (error नाही; बाकी symbols वर परिणाम नाही)."""
    symbol = symbol.upper()
    exch = FUT_EXCHANGE.get(symbol, "NSE")
    kw = {"exchange": exch} if exch != "NSE" else {}
    info, err = V.resolve_front_future(token, symbol, today, **kw)
    if info is None:
        if symbol in OPTIONAL_SYMBOLS:
            log(f"  ℹ️ {symbol}: {exch} front-month futures सापडला नाही — skip ({err})")
            return {"symbol": symbol, "skipped": f"{exch} futures contract सापडला नाही: {err}"}
        return {"symbol": symbol, "error": f"futures contract सापडला नाही: {err}"}
    start = today - datetime.timedelta(days=days)
    out = {"symbol": symbol, "contract": info["trading_symbol"], "instrument_key": info["instrument_key"], "expiry": info["expiry"]}
    fut, ferr = _history_plus_today(token, info["instrument_key"], start, today, out, "futures")
    if ferr:
        out["error"] = f"futures candles: {ferr}"
        return out
    fdf = candles_to_df(fut, contract=info["trading_symbol"])
    added, total = _merge_into(store_path("futures", symbol, data_dir), fdf)
    out.update({"futures_rows": len(fdf), "futures_added": added, "futures_total": total,
                "futures_today": int((fdf["timestamp"].dt.date == today).sum()) if len(fdf) else 0,
                "volume_nonzero_pct": round(100.0 * (fdf["volume"] > 0).mean(), 1) if len(fdf) else 0.0})
    # पुढचा contract सुद्धा (K10.3 roll) — `_all` store मध्ये, front सोबत. अपयश ⇒ फक्त नोंद (front data वर परिणाम नाही).
    try:
        parts = [fdf]
        chain, cerr = V.resolve_futures_chain(token, symbol, today, n=2, **kw)
        for nxt in [c for c in chain if c["instrument_key"] != info["instrument_key"]]:
            nf, nerr = _history_plus_today(token, nxt["instrument_key"], start, today, out, "next")
            if nerr is None:
                parts.append(candles_to_df(nf, contract=nxt["trading_symbol"]))
                out["next_contract"] = nxt["trading_symbol"]
            else:
                out["next_error"] = nerr
        if cerr:
            out["next_error"] = cerr
        added_all, total_all = _merge_all(os.path.join(data_dir, f"oe_futures_5min_{symbol}_all.parquet"),
                                          pd.concat([p for p in parts if len(p)], ignore_index=True) if any(len(p) for p in parts) else fdf)
        out.update({"all_added": added_all, "all_total": total_all})
    except Exception as exc:                                             # नवीन पायरीचं अपयश ⇒ फक्त नोंद; front / index collection चालू राहते
        out["next_error"] = f"{type(exc).__name__}: {exc}"
    idx_key = SYMBOL_INSTRUMENT_KEYS.get(symbol)
    if idx_key:
        ix, ierr = _history_plus_today(token, idx_key, start, today, out, "index")
        if ierr is None:
            idf = candles_to_df(ix)
            added_i, total_i = _merge_into(store_path("index", symbol, data_dir), idf)
            out.update({"index_rows": len(idf), "index_added": added_i, "index_total": total_i})
        else:
            out["index_error"] = ierr
    log(f"  {symbol}: {out.get('contract')} | futures +{out.get('futures_added', 0)} (एकूण {out.get('futures_total', 0)}, आजचे bars "
        f"{out.get('futures_today', 0)}, volume>0 {out.get('volume_nonzero_pct')}%) | index +{out.get('index_added', 0)} (एकूण {out.get('index_total', 0)})")
    for k in sorted(k for k in out if k.endswith("_error")):
        log(f"  ⚠️ {symbol} {k}: {out[k]}")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=None, help="Upstox Access Token (न दिल्यास Supabase मधून)")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
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
