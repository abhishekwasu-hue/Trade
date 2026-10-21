"""scripts/export_banknifty_spot_history.py — BANKNIFTY spot 1m / 5M / 15M history (Upstox v3 historical-candle, free, GET only) ⇒ ONE new
folder in the private trade-data clone, committed and pushed. Abhi runs it on the VPS after the market close (read-only on the bot: no
setting, cron, service or .env change; the token is read from the usual place and never printed).

    cd /root/Trade && set -a && . ./.env && set +a && python3 /tmp/bn_spot_export.py --days 190

Output: <trade-data>/banknifty/vps_spot_history/<IST stamp>/BANKNIFTY_{1m,5m,15m}.csv.gz + manifest.json (rows, first / last bar, sha256,
weekday sessions with no bars per interval — listed, never filled). Exit: 0 pushed · 1 error (nothing committed) · 2 refused (market
hours / folder exists) · 4 committed, push pending (the nightly push sends it; do not re-run).
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())                                            # run from /tmp with cwd = /root/Trade (the bot's modules)

KEY = "NSE_INDEX|Nifty Bank"
INTERVALS = (("1minute", "1m"), ("5minute", "5m"), ("15minute", "15m"))
CHUNK_DAYS = 28                                                            # Upstox v3: minute intervals ≤ 1 month per request


def ist_now():
    return dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)


def in_market_hours(now):
    t = now.time()
    return now.weekday() < 5 and dt.time(8, 30) <= t <= dt.time(15, 35)


def fetch(token, interval, start, end):
    import verify_opportunity_data_availability as V
    out, to = [], end
    while to >= start:
        frm = max(start, to - dt.timedelta(days=CHUNK_DAYS))
        r = V.fetch_candles_window(token, KEY, interval, frm, to)
        if r["status"] != 200:
            raise RuntimeError(f"{interval} {frm}…{to}: HTTP {r['status']}")
        out.extend(r["candles"])
        to = frm - dt.timedelta(days=1)
    rows = sorted({c[0]: c for c in out}.values(), key=lambda c: c[0])
    return rows


def write_csv(path, rows):
    with gzip.open(path, "xt", encoding="utf-8") as f:
        f.write("timestamp,open,high,low,close,volume\n")
        for c in rows:
            f.write(f"{c[0]},{c[1]},{c[2]},{c[3]},{c[4]},{c[5] if len(c) > 5 else ''}\n")
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def missing_sessions(rows, start, end):
    have = {str(c[0])[:10] for c in rows}
    d, miss = start, []
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in have:
            miss.append(d.isoformat())                                     # holiday or gap — listed, never filled
        d += dt.timedelta(days=1)
    return miss


def git(td, *a):
    return subprocess.run(["git", "-C", td, *a], capture_output=True, text=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=190)
    ap.add_argument("--trade-data", default="/root/trade-data")
    a = ap.parse_args(argv)
    now = ist_now()
    if in_market_hours(now):
        print("❌ market hours (08:30–15:35 IST) — refused, nothing done"); return 2
    import cloud_db
    token = cloud_db.get_effective_upstox_token(None)
    if not token:
        print("❌ Upstox token नाही — nothing done"); return 1
    end = now.date() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=a.days)
    folder = os.path.join(a.trade_data, "banknifty", "vps_spot_history", now.strftime("%Y-%m-%d_%H%M"))
    if os.path.exists(folder):
        print(f"❌ {folder} exists — refused"); return 2
    git(a.trade_data, "pull", "-q", "--ff-only")
    tmp = os.path.join(a.trade_data, ".git", "bn_spot_tmp_" + now.strftime("%H%M%S"))
    os.makedirs(tmp)
    man = {"symbol": "BANKNIFTY", "instrument": KEY, "source": "Upstox v3 historical-candle (GET)", "from": start.isoformat(),
           "to": end.isoformat(), "files": {}}
    try:
        for interval, tag in INTERVALS:
            rows = fetch(token, interval, start, end)
            fn = f"BANKNIFTY_{tag}.csv.gz"
            sha = write_csv(os.path.join(tmp, fn), rows)
            miss = missing_sessions(rows, start, end)
            man["files"][fn] = {"rows": len(rows), "first": str(rows[0][0]) if rows else None, "last": str(rows[-1][0]) if rows else None,
                                "sha256": sha, "weekday_sessions_without_bars": miss}
            print(f"✅ {fn}: {len(rows)} rows · {man['files'][fn]['first']} → {man['files'][fn]['last']} · sha256 {sha[:16]} · "
                  f"weekdays without bars {len(miss)}")
        with open(os.path.join(tmp, "manifest.json"), "x", encoding="utf-8") as f:
            json.dump(man, f, indent=1)
        os.makedirs(os.path.dirname(folder), exist_ok=True)
        os.rename(tmp, folder)
    except Exception as exc:                                               # noqa: BLE001 — nothing committed
        subprocess.run(["rm", "-rf", tmp])
        print(f"❌ export failed: {type(exc).__name__}: {str(exc)[:200]} — nothing committed"); return 1
    rel = os.path.relpath(folder, a.trade_data)
    git(a.trade_data, "add", "--ignore-removal", rel)
    c = git(a.trade_data, "commit", "-q", "-m", f"BANKNIFTY spot history {start}…{end} (1m / 5m / 15m, VPS export)")
    if c.returncode != 0:
        print("❌ commit failed: " + (c.stderr or c.stdout)[:200]); return 1
    for attempt in range(2):
        p = git(a.trade_data, "push", "-q", "origin", "HEAD:main")
        if p.returncode == 0:
            print(f"✅ trade-data pushed · commit {git(a.trade_data, 'rev-parse', '--short', 'HEAD').stdout.strip()} · {rel}")
            return 0
        git(a.trade_data, "pull", "-q", "--rebase", "--autostash")
    print("⚠️ committed in the clone, push pending (nightly push sends it) — do not re-run"); return 4


if __name__ == "__main__":
    sys.exit(main())
