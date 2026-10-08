"""
research/elliott_vps_data.py — Elliott E0: VPS वर चालवायचा **read-only** data script
------------------------------------------------------------------------------------
🎓 Sandbox मधून Upstox/NSE पोहोचत नाहीत, म्हणून हे VPS वर चालतं. फक्त डेटा **वाचतो** (GET) आणि private `trade-data` repo च्या
checkout मध्ये फाइल्स लिहितो. Order नाही, DB write नाही, token कधीच छापत नाही. Public Trade repo मध्ये candles नाहीत (Abhi:
Upstox डेटा public repo मध्ये push करायचा नाही) — destination चे git remote (fetch आणि push) "trade-data" नसतील तर script थांबतो.

  python3 research/elliott_vps_data.py --repo /root/trade-data all
  उप-commands:
    probe-expired   Upstox expired-options API (Upstox Plus) तुमच्या account वर चालतो का + किती जुना डेटा
    golden          NIFTY 1m, 2026-07-01 → 2026-10-08 (golden-file; हा काळ "contaminated", अंतिम holdout मधूनही वगळला; 7–8 Oct = Chart Reader golden story).
                    बाजार बंद (15:30 IST) झाल्यानंतरच चालवा; अपूर्ण/गहाळ दिवस असतील तर ⚠️ आणि non-zero.
    major-levels    Major Level engine चे candles (research/major_levels_eval.py export) — public repo ऐवजी इथे; NSE index
                    candles मधून sealed holdout आपोआप काढतो (फक्त golden काळ + IS/VAL राहतो)
    bhavcopy        NSE F&O bhavcopy (NIFTY options + futures). IS/VAL → nse_fo_bhavcopy/NIFTY/, golden काळ →
                    nse_fo_bhavcopy/NIFTY_golden/ (वेगळा — research loader चुकून contaminated डेटा उचलू नये). Resume होतो.
    all             वरचे सगळे (bhavcopy शेवटी — सर्वात लांब)
कुठलीही पायरी फेल किंवा अपूर्ण असेल तर exit code ≠ 0 आणि ⚠️ (जे मिळालं ते फाइल्समध्ये असतं; पुढच्या run ला resume). Push हे script करत नाही.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.parse

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import bhavcopy as BC  # noqa: E402
from elliott import data_policy as DP  # noqa: E402

NIFTY_KEY = "NSE_INDEX|Nifty 50"
API = "https://api.upstox.com/v2"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
DONE = ("ok", "missing")                       # resume मध्ये पुन्हा न मागवायचे; बाकी सगळे (error/pending/missing_weekday) पुन्हा


def ist_now():
    return dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)


# ---------------------------------------------------------------------------------------------------------------------
def _is_trade_data(url):
    u = url.strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u.lower().endswith("/trade-data") or u.lower().endswith(":trade-data")


def check_repo(path, remote_urls=None):
    """destination हा private trade-data repo चा checkout आहे याची खात्री (fetch आणि सगळे push URLs); नाहीतर ValueError.
    remote_urls (str किंवा list) test साठी."""
    if not os.path.isdir(os.path.join(path, ".git")):
        raise ValueError(f"{path}: git checkout नाही — आधी trade-data clone करा")
    if remote_urls is None:
        def git(*a):
            return subprocess.run(["git", "-C", path, "remote", *a], capture_output=True, text=True).stdout.split()
        remote_urls = git("get-url", "origin") + git("get-url", "--push", "--all", "origin")
    if isinstance(remote_urls, str):
        remote_urls = remote_urls.split()
    if not remote_urls:
        raise ValueError(f"{path}: origin remote नाही")
    bad = [u for u in remote_urls if not _is_trade_data(u)]
    if bad:
        raise ValueError(f"destination remote {bad[0]!r} हा trade-data नाही — public repo मध्ये डेटा लिहिणार नाही")
    return True


def _token(token=None):
    if token:
        return token
    import cloud_db
    return cloud_db.get_effective_upstox_token(None)


def _get(session, url, headers=None, params=None, timeout=30):
    try:
        r = session.get(url, headers=headers, params=params, timeout=timeout)
        return r.status_code, r
    except Exception as e:                                   # noqa: BLE001 — अपयश नोंदवायचं, थांबायचं नाही
        return None, e


def _naive_ist(df, col="timestamp"):
    d = df.copy()
    d[col] = pd.to_datetime(d[col])
    if getattr(d[col].dt, "tz", None) is not None:
        d[col] = d[col].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return d


# ---------------------------------------------------------------------------------------------------------------------
def probe_expired(repo, token=None, session=None):
    """Upstox expired-instruments API: expiries यादी → एका परवानगीतल्या expiry चे contracts → एका contract चा 1m candle sample.
    Sample expiry: ≤ 2024-03-31 असेल ती (IS/VAL), नसेल तर golden काळातली; candle window सुद्धा data_policy ने तपासतो."""
    import requests
    s = session or requests.Session()
    tok = _token(token)
    if not tok:
        print("❌ probe: Upstox token नाही")
        return {"ok": False, "reason": "no token"}
    h = {"Accept": "application/json", "Authorization": f"Bearer {tok.strip()}"}
    out = {"run_at": ist_now().isoformat(timespec="seconds")}
    code, r = _get(s, f"{API}/expired-instruments/expiries", h, {"instrument_key": NIFTY_KEY})
    out["expiries_status"] = code
    exp = []
    if code == 200:
        exp = sorted(r.json().get("data") or [])
    else:
        out["expiries_error"] = (getattr(r, "text", str(r)) or "")[:200]
    out["n_expiries"], out["earliest"], out["latest"] = len(exp), (exp[0] if exp else None), (exp[-1] if exp else None)
    research = [e for e in exp if DP.allowed(e, "research")]
    purpose, pool = ("research", research) if research else ("golden", [e for e in exp if DP.allowed(e, "golden")])
    if pool:
        e = pool[-1]
        out["sample_expiry"] = e
        code, r = _get(s, f"{API}/expired-instruments/option/contract", h, {"instrument_key": NIFTY_KEY, "expiry_date": e})
        out["contracts_status"] = code
        cons = (r.json().get("data") or []) if code == 200 else []
        out["n_contracts"] = len(cons)
        key = next((c.get("instrument_key") for c in cons[len(cons) // 2:] + cons if c.get("instrument_key")), None)
        if key:
            frm = (pd.Timestamp(e) - pd.Timedelta(days=3)).date()
            frm = max(frm, DP.CONTAMINATED_START.date()) if purpose == "golden" else frm
            DP.check_range(frm, e, purpose)
            url = f"{API}/expired-instruments/historical-candle/{urllib.parse.quote(key, safe='')}/1minute/{e}/{frm}"
            code, r = _get(s, url, h)
            out["candle_status"] = code
            out["sample_contract"] = key
            out["sample_candles"] = len((r.json().get("data") or {}).get("candles") or []) if code == 200 else 0
    os.makedirs(os.path.join(repo, "probes"), exist_ok=True)
    with open(os.path.join(repo, "probes", "upstox_expired_probe.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    ok = out.get("sample_candles", 0) > 0
    print(f"{'✅' if ok else '❌'} Upstox expired API: status {out['expiries_status']}, expiries {out['n_expiries']} "
          f"({out['earliest']} → {out['latest']}), sample {out.get('sample_expiry')}: contracts {out.get('n_contracts', 0)}, "
          f"1m candles {out.get('sample_candles', 0)}")
    out["ok"] = ok
    return out


# ---------------------------------------------------------------------------------------------------------------------
def expected_golden_days():
    import config
    hol = getattr(config, "NSE_HOLIDAYS_2026", set())
    return [d.date() for d in pd.bdate_range(DP.CONTAMINATED_START, DP.CONTAMINATED_END.normalize()) if d.date() not in hol]


def golden(repo, token=None, fetch=None, now=None):
    """NIFTY index 1m — golden-file काळ. फक्त purpose='golden'. अपेक्षित trading दिवस (weekday − NSE 2026 सुट्ट्या) गहाळ किंवा
    अपूर्ण (< 370 bars) असतील तर ⚠️ आणि False परत (✅ नाही). बाजार बंद होण्याआधी चालवलं तर नकार."""
    start, end = DP.CONTAMINATED_START.date(), DP.CONTAMINATED_END.date()
    DP.check_range(start, end, "golden")
    now = now or ist_now()
    if now < dt.datetime.combine(end, dt.time(15, 35)):
        print(f"❌ golden: {end} चा बाजार अजून बंद नाही — 15:35 IST नंतर चालवा")
        return None
    if fetch is None:
        from upstox_api import fetch_candles_date_range_by_instrument_key as fetch
    tok = _token(token)
    if not tok:
        print("❌ golden: Upstox token नाही")
        return None
    df = fetch(tok, NIFTY_KEY, "1minute", start, end)
    if df is None or len(df) == 0:
        print("❌ golden: candles मिळाले नाहीत")
        return None
    d = _naive_ist(df[["timestamp", "open", "high", "low", "close"]])
    d = DP.filter_allowed(d.sort_values("timestamp").drop_duplicates("timestamp"), "golden")
    os.makedirs(os.path.join(repo, "upstox"), exist_ok=True)
    p = os.path.join(repo, "upstox", f"NIFTY_1m_{start}_{end}.csv.gz")
    d.to_csv(p, index=False)
    per_day = d.groupby(d["timestamp"].dt.date).size()
    missing = [x for x in expected_golden_days() if x not in per_day.index]
    short = list(per_day[per_day < 370].index)
    complete = not missing and not short
    print(f"{'✅' if complete else '⚠️'} golden: {len(d)} 1m candles, {len(per_day)} दिवस, {d['timestamp'].min()} → "
          f"{d['timestamp'].max()}" + (f"; गहाळ दिवस {len(missing)}: {', '.join(map(str, missing[:6]))}" if missing else "")
          + (f"; अपूर्ण दिवस {len(short)}: {', '.join(map(str, short[:6]))}" if short else ""))
    return p if complete else False


# ---------------------------------------------------------------------------------------------------------------------
def golden_filtered_fetch(fetch):
    """Index candles मधून sealed holdout काढणारा wrapper (फक्त IS/VAL + golden काळ राहतो)."""
    def f(*a, **k):
        df = fetch(*a, **k)
        if df is None or len(df) == 0:
            return df
        return DP.filter_allowed(_naive_ist(df), "golden")
    return f


def major_levels(repo):
    """MCX candles (GOLD/COPPER/SILVER) sealed holdout नियमाखाली नाहीत (तो NIFTY साठी); NSE index candles मात्र filter होतात."""
    sys.path.insert(0, os.path.join(ROOT, "research"))
    import major_levels_eval as ML
    from upstox_api import fetch_candles
    out = os.path.join(repo, "major_levels_candles")
    rc = ML.export(ML.load_gt(), out_dir=out, fetch_index=golden_filtered_fetch(fetch_candles))
    print(f"{'✅' if not rc else '❌'} major-levels candles → {out}")
    return not rc


# ---------------------------------------------------------------------------------------------------------------------
def trading_days(start, end):
    """सगळे calendar दिवस — weekend ला सुद्धा प्रयत्न (Budget/Muhurat/DR special sessions चुकू नयेत)."""
    return [d.date() for d in pd.date_range(start, end, freq="D")]


def known_sessions(path=os.path.join(ROOT, "data", "nifty50_1min.parquet")):
    """सुट्टी ओळखण्यासाठी: offline NIFTY 1m मधले trading दिवस (+ त्याची श्रेणी) आणि NSE 2026 सुट्ट्या."""
    days, lo, hi = set(), None, None
    try:
        ts = pd.to_datetime(pd.read_parquet(path, columns=["timestamp"])["timestamp"])
        days = set(ts.dt.date)
        lo, hi = min(days), max(days)
    except Exception:                                               # noqa: BLE001
        pass
    try:
        import config
        hol = set(getattr(config, "NSE_HOLIDAYS_2026", set()))
    except Exception:                                               # noqa: BLE001
        hol = set()
    return {"days": days, "lo": lo, "hi": hi, "hol2026": hol}


def classify_404(day, today, sess):
    """सगळ्या URLs वर 404 आलं तर status:
      pending          — कालचा/आजचा/भविष्यातला दिवस (NSE ने अजून प्रकाशित केलं नसेल) ⇒ पुन्हा प्रयत्न
      missing          — weekend, किंवा offline डेटा/2026 यादीनुसार सुट्टी ⇒ पुन्हा नाही
      error_404_session — offline डेटानुसार त्या दिवशी बाजार चालू होता ⇒ फाईल हवीच, पुन्हा प्रयत्न
      missing_weekday  — weekday, पण सुट्टी आहे का माहीत नाही ⇒ पुन्हा प्रयत्न (holiday म्हणून कायमचं लपवत नाही)"""
    if day >= today - dt.timedelta(days=1):
        return "pending"
    if day.weekday() >= 5:
        return "missing"
    if day in sess["hol2026"]:
        return "missing"
    if sess["lo"] and sess["lo"] <= day <= sess["hi"]:
        return "error_404_session" if day in sess["days"] else "missing"
    return "missing_weekday"


def bhavcopy(repo, ranges=None, session=None, sleep=0.6, max_days=None, log=print, today=None, sess=None):
    """प्रत्येक दिवसासाठी bhavcopy (सगळे URL प्रयत्न), NIFTY ओळी normalize, महिन्यानुसार parquet. manifest.csv मुळे resume.
    Research (IS/VAL) आणि golden काळ वेगळ्या folders मध्ये. Sealed holdout ची एकही तारीख मागवत नाही."""
    import requests
    s = session or requests.Session()
    s.headers.update(UA)
    try:
        s.get("https://www.nseindia.com", timeout=15)               # cookie (archives साठी सहसा लागत नाही, पण निरुपद्रवी)
    except Exception:                                               # noqa: BLE001
        pass
    today = today or ist_now().date()
    sess = sess if sess is not None else known_sessions()
    totals = {"ok": 0, "missing": 0, "error": 0, "pending": 0}
    for a, b, purpose in (ranges or DP.default_download_ranges()):
        DP.check_range(a, b, purpose)
        base = os.path.join(repo, "nse_fo_bhavcopy", "NIFTY" if purpose == "research" else "NIFTY_golden")
        r = _bhav_range(s, base, trading_days(a, b), sleep, max_days, log, today, sess)
        for k in totals:
            totals[k] += r[k]
    print(f"{'✅' if totals['error'] == 0 else '⚠️'} bhavcopy: ok {totals['ok']}, सुट्टी/नाही {totals['missing']}, "
          f"नंतर पुन्हा {totals['pending']}, चूक {totals['error']}")
    return totals


def _bhav_range(s, base, all_days, sleep, max_days, log, today, sess):
    os.makedirs(base, exist_ok=True)
    man_p = os.path.join(base, "manifest.csv")
    man = pd.read_csv(man_p, dtype=str) if os.path.exists(man_p) else pd.DataFrame(columns=["date", "status", "rows", "url"])
    done = set(man.loc[man["status"].isin(DONE), "date"])
    days = [d for d in all_days if d.isoformat() not in done]
    if max_days:
        days = days[:max_days]
    by_month, rows_log = {}, []
    cnt = {"ok": 0, "missing": 0, "error": 0, "pending": 0}
    for i, d in enumerate(days):
        status, rows, used, codes = None, 0, "", []
        for url in BC.urls_for(d):
            code, r = _get(s, url, timeout=30)
            codes.append(code)
            if code == 200 and r.content:
                try:
                    norm = BC.normalize(BC.read_zip_csv(r.content))
                except Exception as e:                             # noqa: BLE001 — HTML block-page इ.: पुढचा URL प्रयत्न
                    status, used = f"error_parse:{type(e).__name__}:{str(e)[:60]}", url
                    time.sleep(sleep)
                    continue
                if len(norm) == 0:
                    status, used = "error_empty", url
                    time.sleep(sleep)
                    continue
                by_month.setdefault(d.strftime("%Y-%m"), []).append(norm)
                status, rows, used = "ok", len(norm), url
                break
            time.sleep(sleep)
        if status is None:
            status = classify_404(d, today, sess) if all(c == 404 for c in codes) else "error_http_" + "/".join(map(str, codes))
        key = "ok" if status == "ok" else "missing" if status == "missing" else "pending" if status in ("pending", "missing_weekday") else "error"
        cnt[key] += 1
        rows_log.append({"date": d.isoformat(), "status": status, "rows": rows, "url": used})
        if (i + 1) % 50 == 0 or i == len(days) - 1:
            _flush(base, by_month)
            by_month = {}
            man = pd.concat([man, pd.DataFrame(rows_log)], ignore_index=True).drop_duplicates("date", keep="last")
            man.sort_values("date").to_csv(man_p, index=False)
            rows_log = []
            log(f"  {os.path.basename(base)} {i + 1}/{len(days)}: ok {cnt['ok']}, सुट्टी {cnt['missing']}, "
                f"पुन्हा {cnt['pending']}, चूक {cnt['error']}")
        time.sleep(sleep)
    return cnt


def _flush(base, by_month):
    for ym, parts in by_month.items():
        p = os.path.join(base, f"{ym}.parquet")
        new = pd.concat(parts, ignore_index=True)
        if os.path.exists(p):
            new = pd.concat([pd.read_parquet(p), new], ignore_index=True)
        new = new.drop_duplicates(["date", "instrument", "expiry", "strike", "opt_type"], keep="last")
        new[BC.FLOAT_COLS] = new[BC.FLOAT_COLS].astype("float64")
        new.sort_values(["date", "expiry", "strike", "opt_type"]).to_parquet(p, index=False)


# ---------------------------------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="private trade-data repo चा checkout (उदा. /root/trade-data)")
    ap.add_argument("cmd", choices=["probe-expired", "golden", "major-levels", "bhavcopy", "all"])
    ap.add_argument("--max-days", type=int, default=None, help="bhavcopy: प्रत्येक श्रेणीत फक्त इतके दिवस (चाचणीसाठी)")
    a = ap.parse_args(argv)
    try:
        check_repo(a.repo)
    except ValueError as e:
        print(f"❌ {e}")
        return 2
    steps = ["probe-expired", "golden", "major-levels", "bhavcopy"] if a.cmd == "all" else [a.cmd]
    failed = []
    for st in steps:
        print(f"── {st}")
        try:
            if st == "probe-expired":
                ok = probe_expired(a.repo).get("expiries_status") is not None      # API "नाही" हा सुद्धा वैध निकाल
            elif st == "golden":
                ok = bool(golden(a.repo))
            elif st == "major-levels":
                ok = major_levels(a.repo)
            else:
                ok = bhavcopy(a.repo, max_days=a.max_days)["error"] == 0
        except Exception as e:                                     # noqa: BLE001 — एक पायरी फेल झाली तरी बाकीच्या चालू
            print(f"❌ {st}: {type(e).__name__}: {str(e)[:200]}")
            ok = False
        if not ok:
            failed.append(st)
    if failed:
        print(f"⚠️ अपूर्ण पायऱ्या: {', '.join(failed)} — जे मिळालं ते साठवलं आहे; पुन्हा चालवल्यास resume होतं")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
