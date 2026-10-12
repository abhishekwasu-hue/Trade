"""scripts/fetch_sensex_history.py — SENSEX index Daily / 1H / 15M (Reader v2 gallery साठी) Abhi च्या Upstox historical API वरून,
private trade-data मध्ये. **फक्त VPS वर** (token VPS `.env` / webhook मधून — कधीच छापत नाही, repo / chat मध्ये नाही).

🎓 मार्ग BANKNIFTY सारखाच (`research/index_candles_fetch.py`: Upstox v3 historical-candle, GET फक्त, chunks, 0.4 s विराम):
  • Daily  = v3 `days/1` (10 वर्षांचे chunks).
  • 15M    = v3 `minutes/15` (28 दिवसांचे chunks) — gallery ला लागणारा सगळ्यात बारीक TF; Upstox चा minutes data 2022 पासूनच.
  • 1H     = 15M चा NSE / BSE 09:15-anchored resample (`opportunity_engine.sessions.resample_nse`, 60 min) ⇒ 09:15, 10:15 … 15:15 —
             BANKNIFTY_1H (v3 `hours/1`) सारखेच bins, आणि 15M शी तंतोतंत सुसंगत (वेगळा call नाही).
  • Volume = index candles मध्ये volume नसतो. BSE F&O मध्ये SENSEX futures (near-month) Upstox वर सापडले ⇒ त्याचा 15M volume त्याच
             timestamp च्या bars ला (1H / D = पूर्ण झाकलेल्या bins चीच बेरीज), बाकी NA. Expired futures चा जुना इतिहास Upstox Plus
             शिवाय मिळत नाही (probe 401) ⇒ volume फक्त चालू near-month च्या काळापुरता; सापडले नाहीत ⇒ volume = NA आणि
             manifest मध्ये "grade cap B" (spec). Futures 15M candles `SENSEX_FUT_15M.csv.gz` मध्ये साठतात (आधीचा row जिंकतो ⇒
             rollover नंतर near-month चा data बदलत नाही), पुन्हा चालवल्यावर coverage वाढते.
  • Holdout: SENSEX ला NIFTY चा sealed holdout लागू नाही (instruments.py); gallery स्वतः NIFTY-holdout तारखा load वेळी वगळते.

Output (BANKNIFTY सारखा schema: timestamp IST naive, open, high, low, close; futures volume असेल तर `volume` column, NA रिकामा):
    <trade-data>/sensex/SENSEX_D.csv.gz, SENSEX_1H.csv.gz, SENSEX_15M.csv.gz, SENSEX_FUT_15M.csv.gz, manifest.json

Resume / append: असलेले files वाचून फक्त उरलेले भाग मागवतो (शेवटचा दिवस पुन्हा — अपूर्ण दिवस भरतो; आधीचा भाग फक्त मागितलेला काळ
आधी तपासलेल्यापेक्षा जुना असेल तर). Merge = timestamp वर, नवा row जिंकतो. फक्त आकडे / तारखा छापतो (किंमती, token नाही).
Code मध्ये तारीख नाही — काळ = आजपासून मागे (CLI).

    python3 scripts/fetch_sensex_history.py --repo /root/trade-data [--daily-years 15] [--intraday-years 4.5] [--futures-days 90] [--dry-run]
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from opportunity_engine import sessions as SS  # noqa: E402
from research import elliott_vps_data as EV  # noqa: E402
from research import index_candles_fetch as IF  # noqa: E402

NAME, DIR = "SENSEX", "sensex"
KEY = "BSE_INDEX|SENSEX"                     # upstox_api.SYMBOL_INSTRUMENT_KEYS["SENSEX"] (test तपासतो)
FUT_SEARCH = {"query": NAME, "exchanges": "BSE", "segments": "FO", "instrument_types": "FUT", "page_number": 1, "records": 30}
NATIVE = {"D": IF.TF["D"], "15M": IF.TF["15M"]}  # (unit, interval, chunk दिवस) — BANKNIFTY fetcher चेच
COLS = ["timestamp", "open", "high", "low", "close"]
FUT_COLS = ["timestamp", "open", "high", "low", "close", "volume", "oi", "contract"]
DEFAULT_GAP_DAYS = 28                       # पुढचा contract सापडला नाही तर near-month काळाचा अंदाज (मासिक expiry)


# ---------------------------------------------------------------------------------------------------------------- pure parts
def candles_df(candles, with_volume=False):
    """Upstox candles [[ts, o, h, l, c, volume, oi], …] ⇒ DataFrame (timestamp naive IST, क्रमाने, duplicate नाहीत)."""
    cols = COLS + (["volume", "oi"] if with_volume else [])
    rows = [list(c[:len(cols)]) + [None] * (len(cols) - len(c[:len(cols)])) for c in candles or []]
    df = pd.DataFrame(rows, columns=cols)
    if not len(df):
        return df
    df = EV._naive_ist(df)
    df["timestamp"] = df["timestamp"].astype("datetime64[ns]")
    for c in cols[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)


def merge(old, new, keep="last"):
    """असलेले + नवे rows (timestamp वर). keep="last" ⇒ नवा row जिंकतो (index: अपूर्ण शेवटचा दिवस दुरुस्त); "first" ⇒ आधीचा
    (futures: rollover नंतर near-month चा साठवलेला volume बदलत नाही)."""
    parts = [d for d in (old, new) if d is not None and len(d)]
    if not parts:
        return (old if old is not None else new).iloc[0:0].copy()
    out = pd.concat(parts, ignore_index=True)
    out["timestamp"] = pd.to_datetime(out["timestamp"]).astype("datetime64[ns]")
    return out.drop_duplicates("timestamp", keep=keep).sort_values("timestamp").reset_index(drop=True)


def plan_ranges(start, end, existing=None, checked_from=None, pending=()):
    """मागायचे [(from, to)] (तारखा, दोन्ही सामील). File नाही ⇒ पूर्ण काळ. आहे ⇒ (१) मागितलेली सुरुवात आधी तपासलेल्या सुरुवातीपेक्षा
    जुनी असेल तर तो भाग, (२) आधीच्या run मध्ये अयशस्वी झालेले chunks (`pending` — file च्या मधली भोकं), (३) file च्या शेवटच्या
    दिवसापासून आजपर्यंत (शेवटचा दिवस पुन्हा)."""
    if existing is None or not len(existing):
        return [(start, end)] if start <= end else []
    ts = pd.to_datetime(existing["timestamp"])
    first, last = ts.min().date(), ts.max().date()
    floor = min(first, checked_from) if checked_from else first
    out = []
    if start < floor:
        out.append((start, floor - dt.timedelta(days=1)))
    for s, e in sorted(pending or []):
        r = (max(s, start), min(e, end))
        if r[0] <= r[1] and r not in out:
            out.append(r)
    if last <= end:
        out.append((max(last, start), end))
    return out


def merge_futures(old, new):
    """Futures store + नवे candles: आधीच्या दिवसांचा साठवलेला row जिंकतो (rollover नंतर near-month चा volume बदलत नाही), पण
    साठवलेल्या **शेवटच्या दिवसाचे** (आणि पुढचे) rows नव्याने बदलतात — तो दिवस मागच्या run वेळी अपूर्ण असू शकतो (चालू 15M bar)."""
    if old is not None and len(old) and new is not None and len(new):
        cut = pd.to_datetime(old["timestamp"]).max().normalize()
        if pd.to_datetime(new["timestamp"]).max() >= cut:
            old = old[pd.to_datetime(old["timestamp"]) < cut]
    return merge(old, new, keep="first")


def to_1h(m15):
    """15M ⇒ 1H (09:15-anchored, दिवस ओलांडत नाही) — OHLC फक्त."""
    if m15 is None or not len(m15):
        return pd.DataFrame(columns=COLS)
    r = SS.resample_nse(m15[COLS], 60, cas=False).dropna(subset=["open", "high", "low", "close"])
    return r[COLS].reset_index(drop=True)


def _expiry(v):
    """Upstox expiry — 'YYYY-MM-DD' किंवा epoch-ms ⇒ date."""
    if v in (None, ""):
        return None
    try:
        x = float(v)
        if x > 1e11:
            x /= 1000.0
        return (dt.datetime(1970, 1, 1) + dt.timedelta(seconds=x, hours=5, minutes=30)).date()
    except (TypeError, ValueError):
        return pd.Timestamp(str(v)[:10]).date()


def resolve_futures(rows, name, today):
    """Instrument यादी (Upstox search / master rows) ⇒ (front, next) — trading_symbol चा ' FUT' आधीचा भाग **तंतोतंत** `name`, BSE F&O,
    expiry ≥ today, expiry क्रमाने. नाही ⇒ (None, None). (SENSEX50 / BANKEX वगैरे वगळले जातात.)"""
    ok = []
    for r in rows or []:
        sym = str(r.get("trading_symbol") or r.get("tradingsymbol") or "").upper()
        seg = str(r.get("segment") or r.get("exchange") or "").upper()
        typ = str(r.get("instrument_type") or "").upper()
        if sym.split(" FUT")[0].strip() != name.upper() or " FUT" not in f" {sym}" or (seg and not seg.startswith("BSE")):
            continue
        if typ and typ not in ("FUT", "FUTIDX"):
            continue
        e = _expiry(r.get("expiry"))
        if e is not None and e >= today and r.get("instrument_key"):
            ok.append({"trading_symbol": r.get("trading_symbol") or r.get("tradingsymbol"), "instrument_key": r["instrument_key"],
                       "expiry": e})
    ok.sort(key=lambda r: r["expiry"])
    return (ok[0] if ok else None), (ok[1] if len(ok) > 1 else None)


def near_month_from(front, nxt):
    """Front contract कोणत्या तारखेनंतर near-month: मागच्या expiry चा अंदाज = front expiry − (next − front) (मासिक cadence);
    next नाही ⇒ DEFAULT_GAP_DAYS. रिटर्न: या तारखेच्या **नंतरचे** दिवस near-month."""
    gap = (nxt["expiry"] - front["expiry"]).days if nxt else DEFAULT_GAP_DAYS
    return front["expiry"] - dt.timedelta(days=max(gap, 1))


def bin_volume(m15_vol, tf):
    """15M bars + `volume` (NA = futures नाही) ⇒ tf (15M / 1H / D) bins चा volume; bin मधला एकही 15M bar NA ⇒ त्या bin चा NA
    (अर्धवट बेरीज नाही). रिटर्न Series (index = bin timestamp: 15M / 1H bar_start, D = तारीख)."""
    d = m15_vol[["timestamp", "volume"]].copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    if tf == "15M":
        return d.set_index("timestamp")["volume"]
    day = d["timestamp"].dt.normalize()
    if tf == "D":
        key = day
    else:
        mins = (d["timestamp"] - day) / pd.Timedelta(minutes=1) - (9 * 60 + 15)
        key = day + pd.Timedelta(minutes=9 * 60 + 15) + pd.to_timedelta((mins // 60) * 60, unit="min")
    g = d.assign(key=key).groupby("key")["volume"]
    return g.sum(min_count=1).where(g.count() == g.size())


def attach_volume(bars, tf, m15_vol):
    """bars ला `volume` (futures, NA जिथे नाही). m15_vol None / रिकामा ⇒ bars तसेच (volume column नाही — BANKNIFTY schema)."""
    if m15_vol is None or not len(m15_vol) or m15_vol["volume"].notna().sum() == 0:
        return bars[COLS].copy()
    v = bin_volume(m15_vol, tf)
    key = pd.to_datetime(bars["timestamp"])
    key = key.dt.normalize() if tf == "D" else key
    out = bars[COLS].copy()
    out["volume"] = key.map(v).astype("float64").to_numpy()
    return out


def index_15m_with_fut_volume(m15, fut15):
    """Index 15M + futures 15M (त्याच timestamp) ⇒ volume column (NA जिथे futures नाही)."""
    if fut15 is None or not len(fut15):
        return None
    vol = fut15.groupby(pd.to_datetime(fut15["timestamp"]))["volume"].sum()
    out = m15[["timestamp"]].copy()
    out["volume"] = pd.to_datetime(out["timestamp"]).map(vol)
    return out


# ---------------------------------------------------------------------------------------------------------------- I/O
def _read(path, cols):
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path)
    d["timestamp"] = pd.to_datetime(d["timestamp"]).astype("datetime64[ns]")
    return d[[c for c in cols if c in d.columns]]


def _write(path, df):
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False, compression="gzip")
    os.replace(tmp, path)


def _fetch_raw(session, token, key, unit, val, days, ranges, sleep, with_volume=False):
    enc = urllib.parse.quote(key, safe="")
    h = {"Accept": "application/json", "Authorization": f"Bearer {token.strip()}"}
    rows, ok, bad = [], 0, []
    for s, e in ranges:
        for cs, ce in IF.chunks(s, e, days):
            code, r = EV._get(session, f"{IF.API3}/{enc}/{unit}/{val}/{ce:%Y-%m-%d}/{cs:%Y-%m-%d}", h, timeout=30)
            if code == 200:
                rows += (r.json().get("data") or {}).get("candles") or []
                ok += 1
            else:
                bad.append((cs, ce, code))
            sleep(0.4)
    return candles_df(rows, with_volume), ok, bad


def _bad_txt(bad):
    return [f"{s}→{e}: HTTP {c}" for s, e, c in bad]


def _span(today, years):
    return today - dt.timedelta(days=int(math.ceil(365.25 * years))), today


def _rng(df):
    if df is None or not len(df):
        return "—"
    return f"{df['timestamp'].min()} → {df['timestamp'].max()}"


def main(argv=None, session=None, token=None, today=None, sleep=time.sleep):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="private trade-data checkout")
    ap.add_argument("--daily-years", type=float, default=15)
    ap.add_argument("--intraday-years", type=float, default=4.5, help="15M इतिहास (Upstox minutes data जानेवारी 2022 पासूनच)")
    ap.add_argument("--futures-days", type=int, default=90, help="near-month futures चे 15M candles इतके दिवस मागे")
    ap.add_argument("--no-futures", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="काय मागवलं जाईल ते दाखवा — token / network नाही, काहीही लिहीत नाही")
    a = ap.parse_args(argv)
    EV.check_repo(a.repo)
    today = today or IF.ist_today()
    out_dir = os.path.join(a.repo, DIR)
    mpath = os.path.join(out_dir, "manifest.json")
    man = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}
    files = man.get("files", {})
    old = {tf: _read(os.path.join(out_dir, f"{NAME}_{tf}.csv.gz"), COLS) for tf in NATIVE}
    spans = {"D": _span(today, a.daily_years), "15M": _span(today, a.intraday_years)}
    plans = {}
    for tf in NATIVE:
        cf = (files.get(tf) or {}).get("checked_from")
        pend = [(pd.Timestamp(s).date(), pd.Timestamp(e).date()) for s, e in (files.get(tf) or {}).get("pending", [])]
        plans[tf] = plan_ranges(*spans[tf], old[tf], pd.Timestamp(cf).date() if cf else None, pend)
    if a.dry_run:
        print(f"DRY RUN — {NAME} ({KEY}) ⇒ {out_dir} (token / network नाही; काहीही लिहिलं नाही)")
        for tf in NATIVE:
            unit, val, days = NATIVE[tf]
            n = sum(len(IF.chunks(s, e, days)) for s, e in plans[tf])
            print(f"  {tf}: आत्ता {0 if old[tf] is None else len(old[tf])} rows ({_rng(old[tf])}); मागवणार {unit}/{val}: "
                  + (", ".join(f"{s} → {e}" for s, e in plans[tf]) or "काही नाही") + f" · {n} calls")
        print("  1H: 15M वरून 09:15-anchored resample (call नाही)")
        print("  futures: " + ("बंद (--no-futures)" if a.no_futures else
                               f"BSE F&O मध्ये '{NAME} FUT' near-month शोधणार (1 call) ⇒ minutes/15, मागचे {a.futures_days} दिवस "
                               f"({len(IF.chunks(today - dt.timedelta(days=a.futures_days), today, 28))} calls)"))
        return 0
    tok = token or os.environ.get("UPSTOX_ACCESS_TOKEN") or EV._token(None)
    if not tok:
        print("❌ Upstox token नाही (VPS .env / webhook) — काहीच मागवलं नाही")
        return 3
    if session is None:
        import requests
        session = requests.Session()
    os.makedirs(out_dir, exist_ok=True)
    now_ist = str(dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=5, minutes=30))[:19]
    rc, merged = 0, {}
    for tf in NATIVE:
        unit, val, days = NATIVE[tf]
        new, ok, bad = _fetch_raw(session, tok, KEY, unit, val, days, plans[tf], sleep)
        if tf == "D" and len(new):
            new["timestamp"] = new["timestamp"].dt.normalize()
        merged[tf] = merge(old[tf], new) if (old[tf] is not None or len(new)) else None
        prev_cf = (files.get(tf) or {}).get("checked_from")         # अयशस्वी chunks `pending` मध्ये ⇒ पुढच्या run ला पुन्हा
        checked = min(x for x in (prev_cf, str(spans[tf][0])) if x) if merged[tf] is not None and len(merged[tf]) else prev_cf
        pending = [[str(s), str(e)] for s, e, _ in bad]
        files[tf] = {"file": f"{NAME}_{tf}.csv.gz", "rows": 0 if merged[tf] is None else int(len(merged[tf])),
                     "requested": [str(s) for s in spans[tf]], "checked_from": checked, "pending": pending,
                     "first": None if merged[tf] is None or not len(merged[tf]) else str(merged[tf]["timestamp"].min()),
                     "last": None if merged[tf] is None or not len(merged[tf]) else str(merged[tf]["timestamp"].max()),
                     "new_rows": int(len(new)), "chunks_ok": ok, "chunks_failed": _bad_txt(bad), "fetched_at_ist": now_ist,
                     "source": f"Upstox v3 {unit}/{val}"}
        if pending:
            rc = 1
            print(f"⚠️ {NAME} {tf}: {len(pending)} chunks अयशस्वी ⇒ pending (भोक) — पुन्हा चालवा, ते पुन्हा मागवले जातील")
    merged["1H"] = to_1h(merged.get("15M"))
    files["1H"] = {"file": f"{NAME}_1H.csv.gz", "rows": int(len(merged["1H"])), "source": "15M ⇒ 09:15-anchored 60 min resample",
                   "first": str(merged["1H"]["timestamp"].min()) if len(merged["1H"]) else None,
                   "last": str(merged["1H"]["timestamp"].max()) if len(merged["1H"]) else None, "fetched_at_ist": now_ist}
    # ---- futures volume (near-month, BSE F&O)
    fut_path = os.path.join(out_dir, f"{NAME}_FUT_15M.csv.gz")
    fut = _read(fut_path, FUT_COLS)
    finfo = {"store": os.path.basename(fut_path), "status": "off" if a.no_futures else "not_found"}
    if not a.no_futures:
        h = {"Accept": "application/json", "Authorization": f"Bearer {tok.strip()}"}
        code, r = EV._get(session, f"{EV.API}/instruments/search", h, params=FUT_SEARCH, timeout=30)
        sleep(0.4)
        rows = (r.json().get("data") or []) if code == 200 else []
        front, nxt = resolve_futures(rows, NAME, today)
        if code != 200:
            finfo.update(status="search_failed", http=code)
        elif front:
            since = near_month_from(front, nxt)
            s = max(since + dt.timedelta(days=1), today - dt.timedelta(days=a.futures_days))
            fnew, ok, bad = _fetch_raw(session, tok, front["instrument_key"], "minutes", "15", 28, [(s, today)], sleep, with_volume=True)
            if len(fnew):
                fnew = fnew[fnew["timestamp"].dt.date > since].assign(contract=front["trading_symbol"])
            fut = merge_futures(fut, fnew) if (fut is not None or len(fnew)) else None
            finfo.update(status="ok" if not bad else "partial", contract=front["trading_symbol"], expiry=str(front["expiry"]),
                         near_month_after=str(since), new_rows=int(len(fnew)), chunks_failed=_bad_txt(bad))
            if bad:
                rc = 1
        if fut is not None and len(fut):
            _write(fut_path, fut[FUT_COLS])
    m15v = index_15m_with_fut_volume(merged["15M"], fut) if merged.get("15M") is not None and fut is not None else None
    cover = {}
    for tf in ("D", "1H", "15M"):
        b = merged.get(tf)
        if b is None or not len(b):
            continue
        out = attach_volume(b, tf, m15v)
        _write(os.path.join(out_dir, f"{NAME}_{tf}.csv.gz"), out)
        cover[tf] = int(out["volume"].notna().sum()) if "volume" in out.columns else 0
        print(f"{'✅' if files[tf].get('rows') else '⚠️'} {NAME} {tf}: {len(out)} rows · {_rng(out)}"
              + (f" · +{files[tf]['new_rows']} मागवलेले" if "new_rows" in files[tf] else "") + f" · volume असलेले bars {cover[tf]}"
              + (f" · अयशस्वी chunks {len(files[tf]['chunks_failed'])}" if files[tf].get("chunks_failed") else ""))
    has_vol = any(cover.values())
    finfo["rows_total"] = 0 if fut is None else int(len(fut))
    man.update({"instrument": NAME, "key": KEY, "files": files, "futures": finfo, "bars_with_volume": cover,
                "volume": "SENSEX near-month futures (BSE F&O), फक्त झाकलेल्या bars ना; बाकी NA" if has_vol else "NA",
                "grade_cap": ("B जिथे volume NA (spec: futures volume नाही ⇒ grade cap B)" if has_vol else
                              "B — SENSEX futures volume नाही (spec: volume = NA ⇒ grade cap B)")})
    with open(mpath + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=1)
    os.replace(mpath + ".tmp", mpath)
    print(f"futures: {finfo.get('status')} {finfo.get('contract', '')} · store rows {finfo['rows_total']} · manifest: {mpath}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
