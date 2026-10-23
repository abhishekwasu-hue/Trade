#!/usr/bin/env python3
"""scripts/reading_gallery_today.py — the DAILY "Today's reading gallery" (owner-orders DECISIONS 49, the daily loop; DECISIONS 46 style).

After the close, on the VPS (where the live data and the engine store are): for the session (today, IST) and each symbol that has
engine rows in the store, ONE gallery in the private trade-data repo — review/reading_gallery/<YYYY-MM-DD>/index.html + PNGs:
  • EVERY engine entry of the session (engine_signals rows with `entries`, stored; consumed or still pending per bot), and
  • EVERY place an armed area / broken line was visited without an entry (the rows' `armed` list: visit ids + models status),
each with the 1H + 15M + 5M charts (decision3/reading_gallery.py: the object with its lifecycle events known at the decision, the
approach-side arrow, the trigger candle, the invalidation, the next area, the decision line with the later bars faded "after the
decision"), English chart text and ONE plain Marathi line of the reader's own reason (from the row's reason / models status only), a
header summary and a numbered list (Abhi replies "#3: …").

Data = the live engine's own inputs (engine3_live.UpstoxFeed / build_inputs / load_m1 / v22_settings — the history cache is reused),
the engine store read-only (sqlite mode=ro), V22 rebuilt ONCE for the session and drawn from (decide reads bars ≤ its bar only; the
charts draw only bars closed at the decision as known, the rest faded). Nothing here is a reading rule, a gate or an order; PAPER /
LIVE untouched; no paid call (Upstox GETs only, as the engine; no Vision).
OFF when the market was closed (config.is_trading_day) or when the dashboard setting `reading_gallery` = off; --force runs it anyway.
Display caps (dashboard, chart-reading settings): `reading_gallery_max_visit_charts` (visits drawn; the rest are listed with their
Marathi line, never hidden) — a display setting, never a reading rule.

Output: --trade-data (default $TRADE_DATA_DIR or /root/trade-data) must be the private trade-data checkout (research/elliott_vps_data
.check_repo — never this public repo); the folder is written, `git add --ignore-removal`, committed and pushed (rejected ⇒ pull
--rebase --autostash, once more), then every file's remote blob is compared. Push impossible ⇒ a tarball (path + sha256 printed).
Telegram: ONE silent line with the gallery path when done (notifications.send_telegram_message, silent).

    python3 scripts/reading_gallery_today.py                                   # VPS (cron after the close)
    python3 scripts/reading_gallery_today.py --day 2026-10-16 --inputs DIR --store es.db --out DIR --no-push --no-telegram --force
Offline (--inputs DIR): engine_<SYM>_{m15,ltf5,m1,daily,fut5}.csv.gz read through the same build_inputs as live (a file feed).
"""
import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import time
import warnings

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(1, os.path.join(ROOT, "research"))

REL_BASE = os.path.join("review", "reading_gallery")
SESSION_END = (15, 31)                                                    # operational: the data cut = the session's last close (+1 min)


# ------------------------------------------------------------------------------------------------------------------------ feeds
class FileFeed:
    """Offline feed with the UpstoxFeed surface (index / futures) over engine_<SYM>_{m15,ltf5,m1,daily,fut5}.csv.gz — so the offline
    run goes through the SAME engine3_live.build_inputs / load_m1 cuts as live (review / sample / tests)."""
    KEYS = {"15minute": "m15", "5minute": "ltf5", "1minute": "m1", "day": "daily"}

    def __init__(self, folder, today):
        self.folder, self.today = folder, pd.Timestamp(today).normalize()

    def _read(self, sym, key, days):
        p = os.path.join(self.folder, f"engine_{str(sym).upper()}_{key}.csv.gz")
        if not os.path.exists(p):
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        d = pd.read_csv(p)
        t = pd.to_datetime(d["timestamp"])
        if getattr(t.dt, "tz", None) is not None:
            t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        d["timestamp"] = t
        if "expiry" in d.columns:
            d["expiry"] = pd.to_datetime(d["expiry"])
        if "volume" not in d.columns:
            d["volume"] = 0.0
        d = d[(d["timestamp"] < self.today + pd.Timedelta(days=1)) & (d["timestamp"] >= self.today - pd.Timedelta(days=int(days)))]
        return d.reset_index(drop=True)

    def index(self, symbol, interval, days):
        return self._read(symbol, self.KEYS[interval], days)

    def futures(self, symbol, interval, days):
        return self._read(symbol, "fut5", days)


# ------------------------------------------------------------------------------------------------------------------------ inputs ⇒ V
def session_now(day):
    return pd.Timestamp(day).normalize() + pd.Timedelta(hours=SESSION_END[0], minutes=SESSION_END[1])


def build_v(sym, feed, now, s=None, log=print):
    """The session's V22, built ONCE exactly as engine3_live.compute builds it (build_inputs + load_m1 + v22_settings + the fold
    cache); FUT volume missing ⇒ the levels-only inputs (the gallery still shows the reading; the rows said "data problem")."""
    import instruments as INS
    import engine3_live as L3
    from decision3 import engine as E3
    from decision3 import history as HI
    s3 = L3.v22_settings(s)
    note = None
    try:
        m15, daily, ltf, fut, note = L3.build_inputs(feed, sym, now, s)
    except L3.FutVolumeMissing as exc:
        note = f"FUT volume missing: {exc}"
        m15, daily, _l, _f, _n = L3.build_inputs(feed, sym, now, s, levels_only=True)
        ss = {**L3.DEFAULTS, **(s or {})}
        ltf = L3.closed_session_bars(feed.index(sym, "5minute", ss["engine3_ltf_days"]), 5, now)
        fut = None
    m1, _info = L3.load_m1(feed, sym, m15, pd.Timestamp(now), s)
    m15 = m15.drop(columns=[c for c in ("volume",) if c in m15.columns])
    kw = {"sealed": HI.sealed_fn(sym)}
    if s3:
        kw["s"] = s3
    if ltf is not None and len(ltf):
        kw["ltf"] = ltf
    if fut is not None:
        kw["futures"] = fut
    prev = INS._current["name"]
    INS.set_current(sym)
    try:
        with L3.fold_cache(sym.upper()), warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            try:
                V = E3.V22(m15, m1, daily, **kw)
            except Exception as exc:                                          # noqa: BLE001 — as the live engine: once without 1m
                if m1 is None:
                    raise
                log(f"⚠️ {sym}: V22 with 1m failed ({type(exc).__name__}) ⇒ without 1m")
                V = E3.V22(m15, None, daily, **kw)
    finally:
        INS._current["name"] = prev
    return V, note


# ------------------------------------------------------------------------------------------------------------------------ store
def store_rows(path, day, symbols=None):
    """{SYM: [row dicts of the session, by bar_ts]} + {SYM: [engine_entry_consumed rows]} — the engine store opened READ-ONLY."""
    import engine_signal as ES
    p = ES.db_path(path)
    if not os.path.exists(p):
        return {}, {}
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        d0, d1 = str(pd.Timestamp(day).normalize()), str(pd.Timestamp(day).normalize() + pd.Timedelta(days=1))
        rows = [dict(x) for x in c.execute("SELECT * FROM engine_signals WHERE bar_ts>=? AND bar_ts<? ORDER BY symbol, bar_ts", (d0, d1))]
        try:
            cons = [dict(x) for x in c.execute("SELECT * FROM engine_entry_consumed")]
        except sqlite3.Error:
            cons = []
    finally:
        c.close()
    out, used = {}, {}
    for r in rows:
        if symbols and r["symbol"] not in symbols:
            continue
        out.setdefault(r["symbol"], []).append(r)
    for x in cons:
        used.setdefault(x["symbol"], []).append(x)
    return out, used


# ------------------------------------------------------------------------------------------------------------------------ trade-data
def git(td, *args, check=True):
    r = subprocess.run(["git", "-C", td, "-c", "user.name=reading-gallery", "-c", "user.email=reading-gallery@users.noreply.github.com",
                        *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {r.stderr.strip()[:200]}")
    return r


def check_trade_data(td):
    """The destination must be the private trade-data checkout on `main` (never this public repo)."""
    from elliott_vps_data import check_repo
    check_repo(td)
    br = git(td, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    if br != "main":
        raise RuntimeError(f"trade-data clone is not on main ({br or 'detached'})")
    git(td, "pull", "-q", "--ff-only", "origin", "main")


class PushPending(RuntimeError):
    """Committed in the trade-data clone but not on the remote (the commit is kept; a hand fix is printed)."""


def deletions_staged(td):
    return [x for x in git(td, "diff", "--cached", "--name-only", "--diff-filter=D").stdout.splitlines() if x.strip()]


def push_and_verify(td, rel, msg):
    """add --ignore-removal of THAT folder; commit ONLY what is staged (no pathspec: a pathspec commit would record working-tree
    deletions too) and never when a deletion is staged (trade-data never loses a file ⇒ RuntimeError ⇒ tarball); push (rejected ⇒
    pull --rebase --autostash — a failed rebase is aborted, the clone is never left mid-rebase — then push once more); every file's
    remote blob = the local one. ⇒ the remote commit id. A git lock (.git/index.lock) ⇒ RuntimeError (never deleted here)."""
    if os.path.exists(os.path.join(td, ".git", "index.lock")):
        raise RuntimeError("trade-data .git/index.lock exists (another git process, or a stale lock) — not touched")
    git(td, "add", "--ignore-removal", "--", rel)
    dels = deletions_staged(td)
    if dels:
        git(td, "reset", "-q", "--", rel, check=False)                     # unstage our folder only; nothing else touched
        raise RuntimeError(f"a deletion is staged in trade-data ({dels[:3]}) — no commit (trade-data never loses a file)")
    other = [x for x in git(td, "diff", "--cached", "--name-only").stdout.splitlines()
             if x.strip() and not (x + "/").startswith(rel.rstrip("/") + "/")]
    if other:                                                              # someone else's staged change: never committed by us
        git(td, "reset", "-q", "--", rel, check=False)
        raise RuntimeError(f"other staged changes in trade-data ({other[:3]}) — no commit")
    if git(td, "diff", "--cached", "--quiet", check=False).returncode != 0:
        git(td, "commit", "-q", "-m", msg)
    if git(td, "push", "-q", "origin", "HEAD:main", check=False).returncode != 0:
        r = git(td, "pull", "-q", "--rebase", "--autostash", "origin", "main", check=False)
        if r.returncode != 0:
            git(td, "rebase", "--abort", check=False)
            raise PushPending(f"rebase failed (aborted, clone back on its commit): {r.stderr.strip()[:160]}")
        if git(td, "push", "-q", "origin", "HEAD:main", check=False).returncode != 0:
            raise PushPending("the second push was rejected too")
    git(td, "fetch", "-q", "origin", "main")
    bad = []
    for base, _dirs, files in os.walk(os.path.join(td, rel)):
        for f in files:
            p = os.path.relpath(os.path.join(base, f), td)
            loc = git(td, "hash-object", "--", p).stdout.strip()
            rem = git(td, "rev-parse", "-q", "--verify", f"FETCH_HEAD:{p}", check=False).stdout.strip()
            if not loc or loc != rem:
                bad.append(p)
    if bad:
        raise RuntimeError(f"not on the remote / different after the push: {bad[:5]}")
    return git(td, "rev-parse", "--short", "FETCH_HEAD").stdout.strip()


def tarball(folder, tardir):
    os.makedirs(tardir, exist_ok=True)
    t = os.path.join(tardir, f"reading_gallery_{os.path.basename(folder.rstrip('/'))}.tgz")
    with tarfile.open(t, "w:gz") as tf:
        tf.add(folder, arcname=os.path.basename(folder.rstrip("/")))
    with open(t, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    return t, sha


# ------------------------------------------------------------------------------------------------------------------------ main
def settings_of(get=None):
    try:
        import cloud_db
        return (get or cloud_db.get_chart_reading_settings)()
    except Exception:                                                       # noqa: BLE001 — defaults
        import cloud_db
        return dict(cloud_db.CHART_READING_DEFAULTS)


def market_was_open(day):
    import config
    return bool(config.is_trading_day(dt.datetime.combine(pd.Timestamp(day).date(), dt.time(12, 0))))


def run(day, out_dir, feed_fn, store=None, symbols=None, settings=None, log=print, build=build_v, eng_settings=None):
    """Build the gallery of `day` into out_dir (index.html + PNGs). feed_fn(sym) ⇒ a feed. ⇒ summary dict (no git, no Telegram)."""
    from decision3 import reading_gallery as RG
    settings = settings or {}
    rows, used = store_rows(store, day, symbols)
    now = session_now(day)
    os.makedirs(out_dir, exist_ok=True)
    groups = []
    for sym in sorted(rows):
        cases = RG.collect(rows[sym], used.get(sym), day)
        g = {"symbol": sym, "cases": cases, "errors": [], "note": None}
        if cases["entries"] or cases["visits"]:
            try:
                t0 = time.time()
                V, note = build(sym, feed_fn(sym), now, (eng_settings or (lambda s: None))(sym), log=log)
                g["note"] = note
                log(f"   {sym}: V22 built in {time.time() - t0:.0f}s")
                RG.render_all(V, sym, cases, out_dir, settings, errors=g["errors"], log=log)
                del V
            except Exception as exc:                                        # noqa: BLE001 — one symbol never stops the others
                g["errors"].append(f"{sym}: V22 / charts: {type(exc).__name__}: {exc}")
                log(f"❌ {sym}: {type(exc).__name__}: {exc}")
                if "list" not in cases:
                    RG.plan_only(sym, cases, settings)
        else:
            RG.plan_only(sym, cases, settings)
        groups.append(g)
    html_path = RG.write_html(out_dir, day, groups, settings)
    summary = RG.summary(groups)
    summary["html"] = html_path
    with open(os.path.join(out_dir, "cases.json"), "w", encoding="utf-8") as fh:
        json.dump({"day": str(pd.Timestamp(day).date()), "summary": summary, "groups": RG.jsafe(groups)}, fh, ensure_ascii=False, indent=1)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--day", default=None, help="session day YYYY-MM-DD (default: today IST)")
    ap.add_argument("--symbols", default=None)
    ap.add_argument("--store", default=None, help="engine store sqlite (default: engine_signal.db_path())")
    ap.add_argument("--inputs", default=None, help="offline inputs dir (engine_<SYM>_{m15,ltf5,m1,daily,fut5}.csv.gz)")
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA_DIR", "/root/trade-data"))
    ap.add_argument("--out", default=None, help="write here instead of trade-data/review/reading_gallery/<day> (implies --no-push)")
    ap.add_argument("--tardir", default=os.environ.get("TARDIR", "/root"))
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--force", action="store_true", help="run even when the market was closed / reading_gallery = off")
    a = ap.parse_args(argv)
    import engine_signal as ES
    day = pd.Timestamp(a.day).normalize() if a.day else pd.Timestamp(ES._naive(ES.now_ist())).normalize()
    dstr = str(day.date())
    settings = settings_of()
    if not a.force and str(settings.get("reading_gallery", "on")) != "on":
        print("ℹ️ reading_gallery = off (dashboard) — no gallery.")
        return 0
    if not a.force and not market_was_open(day):
        print(f"ℹ️ {dstr}: market closed (weekend / NSE holiday) — no gallery.")
        return 0
    syms = [s.strip().upper() for s in a.symbols.split(",")] if a.symbols else None
    if a.inputs:
        feed_fn = lambda sym: FileFeed(a.inputs, day)                       # noqa: E731
        eng = None
    else:
        import cloud_db
        import engine3_live as L3
        token = cloud_db.get_effective_upstox_token(None)
        if not token:
            print("❌ Upstox login missing — no reading gallery.")
            return 1
        feed = L3.UpstoxFeed(token, day.date())
        feed_fn = lambda sym: feed                                          # noqa: E731
        eng = ES.engine3_settings
    push = not (a.no_push or a.out)
    rel = os.path.join(REL_BASE, dstr)
    if push:
        try:
            check_trade_data(a.trade_data)
        except Exception as exc:                                            # noqa: BLE001 — tarball instead
            print(f"⚠️ trade-data not usable ({exc}) ⇒ tarball")
            push = False
    out = a.out or (os.path.join(a.trade_data, rel) if push else os.path.join(a.tardir, "reading_gallery", dstr))
    print(f"📚 reading gallery {dstr} ⇒ {out}")
    summary = run(day, out, feed_fn, a.store, syms, settings, eng_settings=eng)
    if not summary["symbols"]:
        print(f"ℹ️ {dstr}: no engine rows in the store for this session — empty gallery written ({summary['html']}).")
    where = out
    if push:
        try:
            commit = push_and_verify(a.trade_data, rel, f"{rel}: today's reading gallery ({summary['line_en']})")
            where = f"trade-data {rel}/index.html (commit {commit})"
            print(f"✅ trade-data push verified: {where}")
        except PushPending as exc:                                          # committed, not pushed: kept, hand fix printed
            print(f"⏳ {rel} committed in {a.trade_data} but not pushed ({exc}). Hand fix: git -C {a.trade_data} pull --rebase "
                  f"origin main && git -C {a.trade_data} push origin HEAD:main")
            push = False
        except Exception as exc:                                            # noqa: BLE001 — tarball fallback
            print(f"⚠️ push failed ({exc}) ⇒ tarball")
            push = False
    if not push and not a.out:
        t, sha = tarball(out, a.tardir)
        where = f"tarball {t} (sha256 {sha})"
        print(f"📦 {where}")
    print(f"   {summary['line_en']}")
    if not a.no_telegram:
        try:
            from notifications import send_telegram_message
            send_telegram_message(f"📚 आजची reading gallery तयार ({dstr}): {summary['line_mr']} — {where} · फक्त माहिती", silent=True)
        except Exception as exc:                                            # noqa: BLE001 — information only
            print(f"⚠️ Telegram line not sent: {type(exc).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
