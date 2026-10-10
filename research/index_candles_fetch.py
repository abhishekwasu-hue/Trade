"""
research/index_candles_fetch.py — index candles (कुठलाही instrument) VPS वरून trade-data मध्ये. Read-only (GET); order / DB write नाही;
token कधीच छापत नाही (VPS .env ⇒ cloud_db / UPSTOX_ACCESS_TOKEN). Destination फक्त trade-data checkout (remote तपासून). Push हे script
करत नाही. Code मध्ये तारीख नाही — काळ = आजपासून मागे (CLI).

  python3 research/index_candles_fetch.py --repo /root/trade-data --instrument BANKNIFTY \
      [--weekly-years 5] [--daily-years 2] [--intraday-months 3] [--tf W D 1H 15M]

Output: <repo>/<instrument dir>/<INSTR>_<tf>.csv.gz (timestamp IST naive, open, high, low, close; volume नाही) + manifest.json
(प्रत्येक tf: rows, पहिली / शेवटची वेळ, मागितलेला काळ, fetched_at, chunks ok / failed). NIFTY ⇒ sealed holdout rows लिहीत नाही.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.parse

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from elliott import data_policy as DP  # noqa: E402
from research import elliott_vps_data as EV  # noqa: E402

API3 = "https://api.upstox.com/v3/historical-candle"
# tf ⇒ (unit, interval, एका call ची कमाल दिवस — Upstox v3 मर्यादा)
TF = {"W": ("weeks", "1", 3650), "D": ("days", "1", 3650), "1H": ("hours", "1", 90), "15M": ("minutes", "15", 28)}


def ist_today():
    return (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=5, minutes=30)).date()


def span(tf, today, weekly_years, daily_years, intraday_months):
    if tf == "W":
        return today - dt.timedelta(days=int(365.25 * weekly_years)), today
    if tf == "D":
        return today - dt.timedelta(days=int(365.25 * daily_years)), today
    return today - dt.timedelta(days=int(30.5 * intraday_months)), today


def chunks(start, end, days):
    out, e = [], end
    while e >= start:
        s = max(start, e - dt.timedelta(days=days))
        out.append((s, e))
        e = s - dt.timedelta(days=1)
    return out


def fetch_tf(session, token, key, tf, start, end, sleep=time.sleep):
    unit, val, days = TF[tf]
    enc = urllib.parse.quote(key, safe="")
    h = {"Accept": "application/json", "Authorization": f"Bearer {token.strip()}"}
    rows, ok, bad = [], 0, []
    for s, e in chunks(start, end, days):
        code, r = EV._get(session, f"{API3}/{enc}/{unit}/{val}/{e:%Y-%m-%d}/{s:%Y-%m-%d}", h, timeout=30)
        if code == 200:
            rows += (r.json().get("data") or {}).get("candles") or []
            ok += 1
        else:
            bad.append(f"{s}→{e}: HTTP {code}")
        sleep(0.4)
    df = pd.DataFrame([c[:5] for c in rows], columns=["timestamp", "open", "high", "low", "close"])
    if len(df):
        df = EV._naive_ist(df).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df, ok, bad


def main(argv=None, session=None, token=None, today=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--instrument", required=True, choices=INS.names())
    ap.add_argument("--weekly-years", type=float, default=5)
    ap.add_argument("--daily-years", type=float, default=2)
    ap.add_argument("--intraday-months", type=float, default=3)
    ap.add_argument("--tf", nargs="+", default=["W", "D", "1H", "15M"], choices=list(TF))
    a = ap.parse_args(argv)
    EV.check_repo(a.repo)
    ins = INS.get(a.instrument)
    tok = token or os.environ.get("UPSTOX_ACCESS_TOKEN") or EV._token(None)
    if not tok:
        print("❌ Upstox token नाही (VPS .env / webhook) — काहीच मागवलं नाही")
        return 3
    if session is None:
        import requests
        session = requests.Session()
    today = today or ist_today()
    out_dir = os.path.join(a.repo, ins["dir"])
    os.makedirs(out_dir, exist_ok=True)
    mpath = os.path.join(out_dir, "manifest.json")
    man = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}
    man.update({"instrument": ins["name"], "key": ins["key"], "volume": "NA", "files": man.get("files", {})})
    rc = 0
    for tf in a.tf:
        s, e = span(tf, today, a.weekly_years, a.daily_years, a.intraday_months)
        df, ok, bad = fetch_tf(session, tok, ins["key"], tf, s, e)
        dropped = 0
        if ins["holdout"] and len(df):                                       # NIFTY: sealed holdout rows कधीच लिहायचे नाहीत
            keep = [DP.period(x) != "HOLDOUT" for x in df["timestamp"]]
            dropped = len(df) - sum(keep)
            df = df[keep].reset_index(drop=True)
        fn = f"{ins['name']}_{tf}.csv.gz"
        if len(df):
            df.to_csv(os.path.join(out_dir, fn), index=False, compression="gzip")
        man["files"][tf] = {"file": fn if len(df) else None, "rows": int(len(df)), "requested": [str(s), str(e)],
                            "first": str(df["timestamp"].iloc[0]) if len(df) else None, "last": str(df["timestamp"].iloc[-1]) if len(df) else None,
                            "chunks_ok": ok, "chunks_failed": bad, "holdout_rows_dropped": dropped,
                            "fetched_at_ist": str(dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=5, minutes=30))[:19]}
        flag = "✅" if (len(df) and not bad) else "⚠️"
        print(f"{flag} {ins['name']} {tf}: {len(df)} rows · {man['files'][tf]['first']} → {man['files'][tf]['last']}"
              + (f" · अयशस्वी chunks {len(bad)}" if bad else ""))
        if bad or not len(df):
            rc = 1
    json.dump(man, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"manifest: {mpath}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
