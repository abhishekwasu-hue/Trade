#!/usr/bin/env python3
"""scripts/export_banknifty_history.py — BANKNIFTY candle history the VPS already holds ⇒ CSV.gz files for the private trade-data repo.

Why: the BANKNIFTY reader replay (trade-data `review/replay_banknifty_6m/`) had spot 1m / 5M and near-month FUT 5M volume for only the last
few weeks. This copies whatever older BANKNIFTY data is already ON the VPS disk, so the replay can cover a longer window.

Safety (Abhi):
  • READ-ONLY on the bot's files: SQLite opened with `mode=ro`, parquet / cache files only read. Nothing in the bot's folder is written,
    renamed or deleted. No Upstox / Supabase / paid call, no network at all — local files only. No settings, cron or services touched.
  • BANKNIFTY only. NIFTY / SENSEX rows are never read into an output (every source is BANKNIFTY by name; a FUT row whose contract is
    not BANKNIFTY ⇒ refused).
  • Never overwrites: writes ONE new folder (`--out-dir`, must not exist yet; files opened with "x"); refuses a folder inside this
    (public) repo. Written into a hidden sibling first and renamed into place at the end ⇒ never a partial folder at the final path.
  • Refuses during market hours on a trading day (08:30–15:35 IST, config.is_market_open with a margin).
  • Exit code ≠ 0 on any error (0 = written / checked, 1 = error, 2 = refused, 3 = no BANKNIFTY data found at all).

Sources (relative to `--root`, default = this repo; all optional — a missing one is reported, not an error):
  1m spot   data/engine3_cache/hist_NSE_INDEX_Nifty_Bank_1minute_*.pkl   (engine3's daily 1m history cache, ~engine3_m15_days)
            + historical_candles in config.DB_PATH (if it has BANKNIFTY rows)
  5M spot   data/oe_index_5min_BANKNIFTY.parquet (collect_index_futures_volume.py) + historical_candles
  15M / 1H / Daily spot   historical_candles only (engine3 does not keep these on disk)
  FUT 5M    data/oe_futures_5min_BANKNIFTY.parquet (near-month) · data/oe_futures_5min_BANKNIFTY_all.parquet (front + next) + historical_candles
  (data/holdout/ is the sealed holdout cache — never read here.)

Output (`--out-dir`): BANKNIFTY_1M / _5M / _15M / _1H / _D / _FUT_5M / _FUT_5M_all `.csv.gz` (only the datasets that have rows; columns
timestamp (IST, naive), open, high, low, close, volume, oi, [contract], source) + manifest.json (per file: rows, first / last bar, days,
missing / incomplete sessions, missing FUT-volume days, sha256) + README.md. Printed: the same per dataset, and `sha256  file` lines.

    python3 scripts/export_banknifty_history.py --check                       # coverage only, writes nothing
    python3 scripts/export_banknifty_history.py --guard-only                  # market-hours check only (the VPS wrapper runs it first)
    python3 scripts/export_banknifty_history.py --out-dir /root/trade-data/banknifty/vps_history/<name>
"""
import argparse
import datetime as dt
import glob
import gzip
import hashlib
import io
import json
import os
import pickle
import sqlite3
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)                                # config (market-hours guard, holiday list) — no other bot module is imported
SYMBOL = "BANKNIFTY"
INDEX_KEY = "NSE_INDEX|Nifty Bank"                          # instruments.py BANKNIFTY key (engine3 cache file names derive from it)
GUARD_OPEN, GUARD_CLOSE = dt.time(8, 30), dt.time(15, 35)   # market-hours refusal window (IST, trading days)
SESSION_START_MIN, SESSION_END_MIN = 9 * 60 + 15, 15 * 60 + 30
COLS = ["timestamp", "open", "high", "low", "close", "volume", "oi"]

# dataset → (file, bar minutes (None = daily), FUT?)
DATASETS = {
    "1M": ("BANKNIFTY_1M.csv.gz", 1, False),
    "5M": ("BANKNIFTY_5M.csv.gz", 5, False),
    "15M": ("BANKNIFTY_15M.csv.gz", 15, False),
    "1H": ("BANKNIFTY_1H.csv.gz", 60, False),
    "D": ("BANKNIFTY_D.csv.gz", None, False),
    "FUT_5M": ("BANKNIFTY_FUT_5M.csv.gz", 5, True),
    "FUT_5M_all": ("BANKNIFTY_FUT_5M_all.csv.gz", 5, True),
}
INTERVALS = {                                               # historical_candles.interval spellings ⇒ dataset timeframe
    "1minute": "1M", "minute": "1M", "1m": "1M", "1min": "1M",
    "5minute": "5M", "5m": "5M", "5min": "5M",
    "15minute": "15M", "15m": "15M", "15min": "15M",
    "60minute": "1H", "1hour": "1H", "hour": "1H", "1h": "1H", "60m": "1H",
    "day": "D", "1day": "D", "d": "D", "1d": "D", "daily": "D",
}
SPOT_NAMES = {"BANKNIFTY", "BANK NIFTY", "NIFTY BANK", "NSE_INDEX|NIFTY BANK", "NIFTYBANK"}


class Refused(Exception):
    """Safety refusal (exit 2)."""


# ------------------------------------------------------------------------------------------------ names (BANKNIFTY only)
def cache_tag_prefix(key=INDEX_KEY, interval="1minute"):
    """engine3_live._history_cached file tag: non-alnum ⇒ "_" over f"{key}_{interval}_{days}" ⇒ prefix before the days."""
    return "".join(ch if ch.isalnum() else "_" for ch in f"{key}_{interval}_")


def classify_symbol(sym):
    """historical_candles.symbol ⇒ "spot" / "fut" / None (not BANKNIFTY ⇒ never read)."""
    s = " ".join(str(sym or "").upper().split())
    if s in SPOT_NAMES:
        return "spot"
    if s.startswith("BANKNIFTY") and "FUT" in s:
        return "fut"
    return None


def is_banknifty_contract(c):
    return str(c or "").upper().replace(" ", "").startswith("BANKNIFTY")


# ------------------------------------------------------------------------------------------------ frames
def naive_ist(series):
    ts = pd.to_datetime(series, errors="coerce")
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return ts.astype("datetime64[ns]")


def tidy(df, source, contract=None):
    """Any candle frame ⇒ COLS (+ contract) + source; timestamp naive IST; bad timestamps dropped."""
    out = pd.DataFrame({c: (df[c] if c in df.columns else 0.0) for c in COLS})
    out["timestamp"] = naive_ist(out["timestamp"])
    for c in COLS[1:]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out[["volume", "oi"]] = out[["volume", "oi"]].fillna(0.0)
    if contract is not None or "contract" in df.columns:
        out["contract"] = df["contract"].astype(str).to_numpy() if "contract" in df.columns else contract
    out["source"] = source
    return out.dropna(subset=["timestamp"]).reset_index(drop=True)


def candles_frame(candles):
    """Upstox candles [[ts, o, h, l, c, volume, oi], …] ⇒ frame."""
    rows = [list(c[:7]) + [0] * (7 - len(c[:7])) for c in (candles or []) if isinstance(c, (list, tuple)) and len(c) >= 5]
    return pd.DataFrame(rows, columns=COLS)


class _DataOnlyUnpickler(pickle.Unpickler):
    """engine3's cache is a plain list of lists (str / float / int). Anything that needs a class / function ⇒ refused (no code runs)."""

    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"refused: {module}.{name} (only plain lists / numbers / strings are read)")


# ------------------------------------------------------------------------------------------------ sources (read-only)
def read_engine3_cache(root):
    files = sorted(f for f in glob.glob(os.path.join(root, "data", "engine3_cache", f"hist_{cache_tag_prefix()}*.pkl")))
    found = []
    for p in files:
        with open(p, "rb") as fh:
            candles = _DataOnlyUnpickler(fh).load()
        if not isinstance(candles, list):
            raise ValueError(f"{os.path.basename(p)}: not a candle list")
        found.append(("1M", tidy(candles_frame(candles), f"engine3_cache/{os.path.basename(p)}")))
    return found, files


def read_parquet_stores(root):
    found, seen = [], []
    for ds, name in (("5M", "oe_index_5min_BANKNIFTY.parquet"), ("FUT_5M", "oe_futures_5min_BANKNIFTY.parquet"),
                     ("FUT_5M_all", "oe_futures_5min_BANKNIFTY_all.parquet")):
        p = os.path.join(root, "data", name)
        if not os.path.exists(p):
            continue
        seen.append(p)
        df = pd.read_parquet(p)
        if DATASETS[ds][2]:
            if "contract" not in df.columns:
                raise ValueError(f"{name}: no contract column")
            bad = [c for c in df["contract"].astype(str).unique() if not is_banknifty_contract(c)]
            if bad:
                raise Refused(f"{name}: non-BANKNIFTY contract(s) {bad[:3]} — refusing (BANKNIFTY only)")
        found.append((ds, tidy(df, f"data/{name}")))
    return found, seen


def read_sqlite(db_path):
    """historical_candles (database.py schema), BANKNIFTY rows only, opened read-only (mode=ro: never creates / writes the DB)."""
    if not db_path or not os.path.exists(db_path):
        return [], []
    uri = "file:" + os.path.abspath(db_path) + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        has = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='historical_candles'").fetchone()
        if not has:
            return [], [db_path]
        pairs = con.execute("SELECT DISTINCT symbol, interval FROM historical_candles").fetchall()
        found = []
        for sym, iv in pairs:
            kind, tf = classify_symbol(sym), INTERVALS.get(str(iv or "").strip().lower())
            if kind is None or tf is None:
                continue                                                   # not BANKNIFTY (or unknown interval) ⇒ never read
            if kind == "fut" and tf != "5M":
                continue
            df = pd.read_sql_query("SELECT timestamp, open, high, low, close, volume, oi FROM historical_candles "
                                   "WHERE symbol=? AND interval=? ORDER BY timestamp", con, params=(sym, iv))
            src = f"sqlite:historical_candles[{sym}|{iv}]"
            if kind == "fut":
                found.append(("FUT_5M_all", tidy(df, src, contract=str(sym))))
            else:
                found.append((tf, tidy(df, src)))
        return found, [db_path]
    finally:
        con.close()


# ------------------------------------------------------------------------------------------------ merge + coverage
def merge(parts, fut_all=False):
    """Sources in priority order ⇒ one frame; same key (timestamp [+ contract]) ⇒ first source kept; OHLC disagreements counted."""
    df = pd.concat(parts, ignore_index=True)
    key = ["timestamp", "contract"] if fut_all else ["timestamp"]
    dup = df[df.duplicated(key, keep=False)]
    conflicts = 0
    if len(dup):
        g = dup.groupby(key)[["open", "high", "low", "close"]].agg(lambda s: s.round(4).nunique())
        conflicts = int((g > 1).any(axis=1).sum())
    out = df.drop_duplicates(key, keep="first").sort_values(key).reset_index(drop=True)
    return out, conflicts


def expected_sessions(first, last):
    """Weekdays minus config.NSE_HOLIDAYS_2026 (the only holiday list in the repo ⇒ other years: weekdays only, noted)."""
    from config import NSE_HOLIDAYS_2026
    days = pd.bdate_range(first, last).date
    return [d for d in days if d not in NSE_HOLIDAYS_2026]


def session_starts(df, minutes):
    """Bars whose start is inside the session (09:15 ≤ start < 15:30) — 1m 375 · 5M 75 · 15M 25 · 1H 7 per full session."""
    tod = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    return df[((tod >= SESSION_START_MIN) & (tod < SESSION_END_MIN)).to_numpy()]


def coverage(df, minutes, fut=False):
    ts = df["timestamp"]
    first, last = ts.min(), ts.max()
    days = sorted(set(ts.dt.date))
    exp = expected_sessions(first.date(), last.date())
    missing = [str(d) for d in exp if d not in set(days)]
    info = {"rows": int(len(df)), "first": str(first), "last": str(last), "days": len(days), "expected_sessions": len(exp),
            "missing_sessions": missing}
    if first.year != 2026 or last.year != 2026:
        info["note"] = "holiday list is 2026-only: a 'missing' weekday outside 2026 may be an NSE holiday"
    if minutes:
        want = -(-(SESSION_END_MIN - SESSION_START_MIN) // minutes)
        s = session_starts(df.drop_duplicates("timestamp"), minutes)
        per = s.groupby(s["timestamp"].dt.date).size()
        info["bars_per_full_session"] = want
        info["incomplete_sessions"] = {str(d): int(n) for d, n in per.items() if n < want}
    if fut:
        s = session_starts(df, 5)
        vol = s[s["volume"] > 0].groupby(s["timestamp"].dt.date).size()
        info["days_with_volume"] = int(len(vol))
        info["contracts"] = sorted(df["contract"].astype(str).unique().tolist()) if "contract" in df.columns else []
    return info


def fut_volume_missing(fut, spot_days):
    """Spot sessions (from the spot datasets) where the near-month FUT file has no session bar with volume > 0."""
    if fut is None or not len(fut):
        return [str(d) for d in spot_days]
    s = session_starts(fut, 5)
    have = set(s[s["volume"] > 0]["timestamp"].dt.date)
    return [str(d) for d in spot_days if d not in have]


# ------------------------------------------------------------------------------------------------ write
def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_csv_gz(df, path):
    """New file only ("xb" ⇒ an existing file is never overwritten); gzip mtime 0 ⇒ same rows, same sha256."""
    out = df.copy()
    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    text = out.to_csv(index=False)
    with open(path, "xb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        gz.write(text.encode("utf-8"))


def _inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def guard_time(now):
    import config
    if config.is_market_open(now, open_time=GUARD_OPEN, close_time=GUARD_CLOSE):
        raise Refused(f"market hours on a trading day ({GUARD_OPEN:%H:%M}–{GUARD_CLOSE:%H:%M} IST) — run after the close")


def guard_out_dir(out_dir, root):
    if _inside(out_dir, root):
        raise Refused(f"--out-dir is inside the public code repo ({root}) — data goes to trade-data only")
    if os.path.exists(out_dir):
        raise Refused(f"--out-dir already exists ({out_dir}) — never overwritten; pick a new folder name")


def collect(root, db_path, log=print):
    parts, read = {}, []
    for fn, arg in ((read_engine3_cache, root), (read_parquet_stores, root), (read_sqlite, db_path)):
        found, files = fn(arg)
        read += files
        for ds, df in found:
            if len(df):
                parts.setdefault(ds, []).append(df)
    log("sources read (read-only):" + ("" if read else " none found"))
    for p in read:
        log(f"  · {os.path.relpath(p, root) if _inside(p, root) else p}")
    return parts


def build(parts):
    """dataset ⇒ (frame, coverage)."""
    out = {}
    for ds, (_, minutes, fut) in DATASETS.items():
        if ds not in parts:
            continue
        df, conflicts = merge(parts[ds], fut_all=(ds == "FUT_5M_all"))
        cols = COLS + (["contract"] if fut else []) + ["source"]
        if fut and "contract" not in df.columns:
            df["contract"] = ""
        df = df[cols]
        info = coverage(df, minutes, fut=fut)
        info["sources"] = {k: int(v) for k, v in df["source"].value_counts().sort_index().items()}
        info["duplicate_key_conflicts"] = conflicts
        out[ds] = (df, info)
    spot = [out[k][0] for k in ("1M", "5M", "15M") if k in out]
    if spot:
        alld = pd.concat([d["timestamp"] for d in spot])
        spot_days = expected_sessions(alld.min().date(), alld.max().date())
        near = out["FUT_5M"][0] if "FUT_5M" in out else None
        miss = fut_volume_missing(near, spot_days)
        for ds in ("FUT_5M",):
            if ds in out:
                out[ds][1]["missing_fut_volume_days_vs_spot"] = miss
        out["_fut_missing"] = miss
    return out


def report(built, log=print):
    for ds in DATASETS:
        if ds not in built:
            log(f"── {ds}: no BANKNIFTY rows on this machine")
            continue
        i = built[ds][1]
        log(f"── {ds}: {i['rows']} rows · {i['first']} → {i['last']} · {i['days']} days / {i['expected_sessions']} expected sessions")
        log(f"   sources: {i['sources']} · key conflicts between sources: {i['duplicate_key_conflicts']}")
        miss = i["missing_sessions"]
        log(f"   missing sessions: {len(miss)}" + (f" ({', '.join(miss[:12])}{' …' if len(miss) > 12 else ''})" if miss else ""))
        inc = i.get("incomplete_sessions") or {}
        if "bars_per_full_session" in i:
            items = [f"{d}:{n}" for d, n in list(inc.items())[:12]]
            log(f"   incomplete sessions (< {i['bars_per_full_session']} session bars): {len(inc)}"
                + (f" ({', '.join(items)}{' …' if len(inc) > 12 else ''})" if inc else ""))
        if "contracts" in i:
            log(f"   contracts: {i['contracts']} · sessions with FUT volume > 0: {i['days_with_volume']}")
        if i.get("note"):
            log(f"   note: {i['note']}")
    if "_fut_missing" in built:
        m = built["_fut_missing"]
        log(f"── missing near-month FUT-volume days (vs the spot sessions): {len(m)}"
            + (f" (first {m[0]}, last {m[-1]})" if m else ""))


def partial_dir(out_dir):
    """Hidden sibling the export is written into first (renamed into place only when every file is written)."""
    out_dir = os.path.abspath(out_dir)
    return os.path.join(os.path.dirname(out_dir), f".{os.path.basename(out_dir)}.partial-{os.getpid()}")


def write_all(built, out_dir, meta, log=print):
    """All files into a hidden sibling, then ONE rename into `out_dir` ⇒ never a half-written folder at the final path (a later
    `git add` elsewhere cannot push a partial export). Any error ⇒ the sibling is removed (only this run's own folder)."""
    import shutil
    out_dir = os.path.abspath(out_dir)
    os.makedirs(os.path.dirname(out_dir), exist_ok=True)
    tmp = partial_dir(out_dir)
    os.makedirs(tmp, exist_ok=False)
    try:
        manifest = _write_files(built, tmp, meta)
        if os.path.exists(out_dir):
            raise Refused(f"--out-dir appeared while writing ({out_dir}) — not overwritten")
        os.rename(tmp, out_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log("sha256 (sha256sum format):")
    for f in sorted(manifest["files"]):
        log(f"{manifest['files'][f]['sha256']}  {f}")
    for f in ("manifest.json", "README.md"):
        log(f"{sha256_file(os.path.join(out_dir, f))}  {f}")
    return manifest


def _write_files(built, out_dir, meta):
    files = {}
    for ds, (fname, _, _) in DATASETS.items():
        if ds not in built:
            continue
        p = os.path.join(out_dir, fname)
        write_csv_gz(built[ds][0], p)
        files[fname] = {"dataset": ds, "sha256": sha256_file(p), "bytes": os.path.getsize(p), **built[ds][1]}
    manifest = {**meta, "files": files, "missing_fut_volume_days_vs_spot": built.get("_fut_missing", [])}
    with open(os.path.join(out_dir, "manifest.json"), "x", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
    lines = ["# BANKNIFTY history exported from the VPS (read-only)", "",
             f"Exported {meta['exported_at_ist']} IST by `scripts/export_banknifty_history.py` (Trade repo `{meta['code_commit']}`).",
             "Local files only (no Upstox / paid call). BANKNIFTY only. Timestamps = bar start, IST, naive. `source` = where each row came from.",
             "Coverage, gaps and sha256 per file: `manifest.json`.", "", "| file | rows | first | last | days |", "|---|---|---|---|---|"]
    lines += [f"| {f} | {v['rows']} | {v['first']} | {v['last']} | {v['days']} |" for f, v in files.items()]
    with open(os.path.join(out_dir, "README.md"), "x", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return manifest


def code_commit(root):
    import subprocess
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "unknown"
    except Exception:                                                     # noqa: BLE001
        return "unknown"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=ROOT, help="bot repo root (data/ lives here); default = this repo")
    ap.add_argument("--db", default=None, help="SQLite path (default <root>/config.DB_PATH)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--out-dir", help="NEW folder for the export (must not exist; outside this repo)")
    g.add_argument("--check", action="store_true", help="print coverage only, write nothing")
    g.add_argument("--guard-only", action="store_true", help="only the market-hours check (exit 0 = allowed, 2 = refused); reads nothing")
    ap.add_argument("--now", default=None, help="IST time for the market-hours guard (tests); default = now")
    a = ap.parse_args(argv)
    try:
        import config
        now = pd.Timestamp(a.now).to_pydatetime() if a.now else config.get_ist_now()
        guard_time(now)
        if a.guard_only:
            print(f"✅ {now:%Y-%m-%d %H:%M} IST: outside market hours — export allowed")
            return 0
        root = os.path.abspath(a.root)
        db = a.db or os.path.join(root, config.DB_PATH)
        if a.out_dir:
            guard_out_dir(a.out_dir, ROOT)
            guard_out_dir(a.out_dir, root)
        print(f"BANKNIFTY history export — {now:%Y-%m-%d %H:%M} IST · root {root} · read-only")
        built = build(collect(root, db))
        report(built)
        if not any(ds in built for ds in DATASETS):
            print("❌ no BANKNIFTY candles found in any local source — nothing written")
            return 3
        if a.check:
            print("✅ check only — nothing written")
            return 0
        meta = {"symbol": SYMBOL, "exported_at_ist": f"{now:%Y-%m-%d %H:%M}", "code_commit": code_commit(ROOT),
                "read_only": True, "network": False}
        write_all(built, a.out_dir, meta)
        print(f"✅ written: {a.out_dir}")
        return 0
    except Refused as exc:
        print(f"⛔ refused: {exc}")
        return 2
    except Exception as exc:                                              # noqa: BLE001
        print(f"❌ error: {type(exc).__name__}: {str(exc)[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
