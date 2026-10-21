#!/usr/bin/env python3
"""🩺 diagnose_day_export (VPS, READ-ONLY): how did the live reader (engine decision3) read one day? Exports everything needed to
reproduce the day in the sandbox, to the private trade-data repo (review/diagnosis_today/<DAY>/vps/).

Run it from a copy OUTSIDE the deployed tree (the deployed code is NOT changed; it runs against whatever /root/Trade HEAD is):
  git -C /root/Trade fetch origin claude/diagnose-day
  git -C /root/Trade show origin/claude/diagnose-day:scripts/diagnose_day_export.py > /tmp/diagnose_day_export.py
  cd /root/Trade && set -a && . ./.env && set +a && python3 /tmp/diagnose_day_export.py --symbol NIFTY --day 2026-10-21

Read-only everywhere: SQLite opened `mode=ro`; never writes the bot's DBs / caches / settings / cron (engine3 caches go to a private temp
dir via ENGINE3_CACHE_DIR); no order / broker call; Upstox = free candle GETs only (one fetch; the replay re-uses it). No secret is
printed or written (env NAMES only; tokens / JWTs / long hex-base64 strings / text after token|Bearer are redacted). nice + ionice.
`--now` (default: current IST, capped at 15:30 of --day): only bars closed by then. Each section is independent (✅ / ❌).
Sections: 1 code · 2 settings · 3 live outputs (engine rows, vision, paper journal, PAPER live_trades, logs) · 4 inputs (CSV.gz) ·
push (must-haves) · 5 bar-by-bar replay at the deployed commit (`--no-replay` to skip) · push again. Exit 0 iff live outputs exported.
Code मध्ये तारीख नाही (दिवस CLI ने).
"""
import argparse
import dataclasses
import datetime as dt
import gc
import gzip
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback

IST = dt.timedelta(hours=5, minutes=30)
STRATEGY_KEY = "15m_dynamic_sr"
VISION_BOT = "srv2_momentum_reversal"
SECRET_WORDS = ("token", "secret", "key", "password", "passwd", "auth")
LOG_FILES = ("engine_signal.log", "srv2.log", "vision_worker.log", "vision_telegram.log", "level_gate_preopen.log", "monitor.log",
             "trade_monitor.log", "dsr.log", "classic_sr.log")
LOG_MAX_LINES = 40000
LOG_TAIL_BYTES = 12_000_000                                                # bounded memory on a 1 GB VPS
UNITS = ("vision_worker", "vision_telegram")


# ------------------------------------------------------------------------------------------------ redaction
_SECRET_AFTER = re.compile(r"(?i)\b(token|bearer|authorization|api[_-]?key|access[_-]?key|secret|password|passwd|apikey)"
                           r"([\"']?\s*[=:]\s*[\"']?|\s+)([^\s\"',;&]+)")
_TG_BOT = re.compile(r"bot\d{5,}:[A-Za-z0-9_\-]{20,}")
_LONG = re.compile(r"[A-Za-z0-9+_\-=.]{40,}")
_ENV_SECRETS = []


def load_env_secrets(environ=None):
    """Values of env vars whose NAME looks secret (≥ 8 chars) ⇒ literal redaction everywhere (values never printed)."""
    env = os.environ if environ is None else environ
    _ENV_SECRETS[:] = sorted({v for k, v in env.items() if v and len(v) >= 8 and any(w in k.lower() for w in SECRET_WORDS)},
                             key=len, reverse=True)


def redact(s):
    s = str(s)
    for v in _ENV_SECRETS:
        if v in s:
            s = s.replace(v, "<redacted-env>")
    s = _TG_BOT.sub("bot<redacted>", s)
    s = _SECRET_AFTER.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", s)
    return _LONG.sub("<redacted-long>", s)


def secret_name(k):
    k = str(k).lower()
    return any(w in k for w in ("token", "secret", "key", "password"))


# ------------------------------------------------------------------------------------------------ JSON / files
def clean(o, depth=0):
    """Anything (numpy / pandas / dataclass / objects) ⇒ JSON-safe (NaN ⇒ None). Never raises."""
    try:
        import numpy as np
        import pandas as pd
    except ImportError:                                                  # pragma: no cover
        np = pd = None
    if depth > 30:
        return str(o)[:300]
    if o is None or isinstance(o, (bool, str, int)):
        return o
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {str(k): clean(v, depth + 1) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [clean(v, depth + 1) for v in o]
    if np is not None:
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o) if math.isfinite(float(o)) else None
        if isinstance(o, np.ndarray):
            return [clean(v, depth + 1) for v in (o.tolist() if o.size <= 5000 else o[:5000].tolist())]
        if isinstance(o, (pd.Timestamp, dt.datetime, dt.date, pd.Timedelta)):
            return None if pd.isna(o) else str(o)
        if isinstance(o, pd.DataFrame):
            return {"_frame_rows": len(o), "columns": [str(c) for c in o.columns],
                    "records": clean(o.head(300).to_dict("records"), depth + 1)}
        if isinstance(o, pd.Series):
            return clean(o.head(2000).tolist(), depth + 1)
    if isinstance(o, (dt.datetime, dt.date)):
        return str(o)
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {"_type": type(o).__name__, **{f.name: clean(getattr(o, f.name, None), depth + 1) for f in dataclasses.fields(o)}}
    if hasattr(o, "__dict__") and not callable(o):
        return {"_type": type(o).__name__, **{k: clean(v, depth + 1) for k, v in list(vars(o).items())[:60] if not k.startswith("__")}}
    return str(o)[:500]


def dumps(o):
    return json.dumps(clean(o), ensure_ascii=False, indent=1, allow_nan=False)


class Out:
    """Writes only under `root` (a NEW folder); refuses to overwrite a file."""

    def __init__(self, root):
        self.root = root
        self.files = []

    def path(self, rel):
        p = os.path.join(self.root, rel)
        if os.path.exists(p):
            raise FileExistsError(f"refusing to overwrite {p}")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        self.files.append(rel)
        return p

    def json(self, rel, obj, gz=False):
        txt = dumps(obj)
        if gz:
            with gzip.open(self.path(rel + ".gz"), "wt", encoding="utf-8") as f:
                f.write(txt)
        else:
            with open(self.path(rel), "w", encoding="utf-8") as f:
                f.write(txt)

    def text(self, rel, txt, do_redact=True):
        with open(self.path(rel), "w", encoding="utf-8") as f:
            f.write(redact(txt) if do_redact else txt)

    def csv(self, rel, df):
        df.to_csv(self.path(rel + ".csv.gz"), index=False, compression="gzip")


def sh(cmd, cwd=None, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode, (r.stdout or "") + (("\n" + r.stderr) if r.returncode and r.stderr else "")
    except Exception as exc:                                             # noqa: BLE001
        return 99, f"<{type(exc).__name__}: {exc}>"


def ro_connect(path):
    """SQLite read-only (never creates / migrates / writes). Missing file ⇒ FileNotFoundError."""
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"db not found: {path}")
    c = sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def table_cols(c, table):
    return [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]


def rows_like(c, table, day, cols_any, extra_where=""):
    """Rows of `table` where any of `cols_any` (that exist) starts with `day`."""
    have = table_cols(c, table)
    if not have:
        return [], have
    use = [x for x in cols_any if x in have]
    if not use:
        return [], have
    where = " OR ".join(f"CAST({x} AS TEXT) LIKE ?" for x in use)
    q = f"SELECT * FROM {table} WHERE ({where}){extra_where}"
    return [dict(r) for r in c.execute(q, [day + "%"] * len(use)).fetchall()], have


def scrub_row(r):
    """DB row ⇒ drop secret-named columns; redact text values."""
    return {k: (redact(v) if isinstance(v, str) else v) for k, v in r.items() if not secret_name(k)}


# ------------------------------------------------------------------------------------------------ context
class Ctx:
    def __init__(self, a, repo, out):
        self.a, self.repo, self.out = a, repo, out
        self.day = a.day
        self.symbol = a.symbol.upper()
        self.status = {}                                                 # section ⇒ (ok, note)
        self.summary = {}
        self.live_rows = []
        self.raw = {}                                                    # (kind, symbol, interval, days) ⇒ raw frame (fetched once)
        self.settings = {}
        self.engine3_s = {}
        self.now = None
        self.fut_search = None                                           # probe: engine FUT search {status, info}
        self.fut_source = None                                           # which FUT 5M source the inputs used

    def ok(self, name, note=""):
        self.status[name] = (True, note)
        print(f"✅ {name}: {note}")

    def fail(self, name, exc):
        note = f"{type(exc).__name__}: {redact(str(exc))[:300]}"
        self.status[name] = (False, note)
        print(f"❌ {name}: {note}")
        try:
            self.out.text(f"errors/{name}.txt", traceback.format_exc())
        except Exception:                                                # noqa: BLE001
            pass


def ist_now():
    return dt.datetime.utcnow() + IST


def effective_now(day, now_arg=None, clock=None):
    """--now HH:MM (on --day) or the current IST time; capped at 15:30 of --day (a past day ⇒ 15:30)."""
    d = dt.date.fromisoformat(day)
    close = dt.datetime.combine(d, dt.time(15, 30))
    if now_arg:
        h, m = (int(x) for x in now_arg.split(":"))
        return min(dt.datetime.combine(d, dt.time(h, m)), close)
    cur = (clock or ist_now)()
    if cur.date() > d:
        return close
    if cur.date() < d:
        raise ValueError(f"--day {day} is in the future (IST now {cur:%Y-%m-%d %H:%M})")
    return min(cur.replace(second=0, microsecond=0), close)


# ------------------------------------------------------------------------------------------------ 1 code
def section_code(cx):
    g = lambda *a: sh(["git", *a], cwd=cx.repo)[1].strip()               # noqa: E731
    head = g("rev-parse", "HEAD")
    reflog = g("reflog", "--date=iso", "-n", "200")
    day_lines = [ln for ln in reflog.splitlines() if cx.day in ln]
    rc, cron = sh(["crontab", "-l"])
    cron_lines = [ln for ln in cron.splitlines() if re.search(r"engine_signal_run|srv2_momentum|level_gate_preopen|vision|trade_monitor", ln)]
    rb = {}
    for f in ("/root/one_bot_rollback.txt", "/root/paper_rollback.txt"):
        if os.path.exists(f):
            rb[f] = open(f, encoding="utf-8").read().strip()
    info = {"head": head, "head_short": head[:7], "log_1": g("log", "-1", "--format=%H%n%an%n%ci%n%s"),
            "branch": g("rev-parse", "--abbrev-ref", "HEAD"), "status_tracked": g("status", "--short", "--untracked-files=no"),
            "reflog_day": day_lines, "reflog_last_25": reflog.splitlines()[:25], "cron_rc": rc, "cron_lines": cron_lines,
            "rollback_files": rb, "python": sys.version, "script_sha256": hashlib.sha256(open(__file__, "rb").read()).hexdigest()}
    for mod in ("pandas", "numpy"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception:                                                # noqa: BLE001
            pass
    cx.out.text("meta/code.json", dumps(info))
    cx.summary["commit"] = head[:7]
    cx.ok("1_code", f"HEAD {head[:7]} · reflog lines today {len(day_lines)} · cron lines {len(cron_lines)}")


# ------------------------------------------------------------------------------------------------ 2 settings
def section_settings(cx):
    import cloud_db
    out, errs = {}, {}
    for sym in dict.fromkeys([cx.symbol, "NIFTY", "BANKNIFTY"]):
        try:
            st = dict(cloud_db.get_strategy_settings(STRATEGY_KEY, sym) or {})
            out[f"{STRATEGY_KEY}/{sym}"] = {k: v for k, v in st.items() if not secret_name(k)}
            if sym == cx.symbol:
                cx.settings = out[f"{STRATEGY_KEY}/{sym}"]
                cx.engine3_s = {k: v for k, v in st.items() if str(k).startswith("engine3_")}
        except Exception as exc:                                         # noqa: BLE001
            errs[sym] = f"{type(exc).__name__}: {exc}"
    try:
        import engine_signal as ES
        fn = getattr(ES, "engine3_settings", None)
        if fn is not None:                                               # exactly what the live run passes as `s`
            cx.engine3_s = fn(cx.symbol)
        out["engine_signal.DEFAULTS"] = getattr(ES, "DEFAULTS", None)
    except Exception as exc:                                             # noqa: BLE001
        errs["engine3_settings"] = f"{type(exc).__name__}: {exc}"
    out["engine3_s_used"] = cx.engine3_s
    try:
        import engine3_live as L
        out["engine3_live.DEFAULTS"] = getattr(L, "DEFAULTS", None)
        s3 = L.swing_scale(cx.engine3_s) if hasattr(L, "swing_scale") else None
        from decision3 import settings as S3
        out["v22_effective_settings"] = S3.load(s3)
        out["v22_s3_override"] = s3
    except Exception as exc:                                             # noqa: BLE001
        errs["v22_settings"] = f"{type(exc).__name__}: {exc}"
    try:
        out["signal_symbols"] = list(cloud_db.get_signal_symbols()) if hasattr(cloud_db, "get_signal_symbols") else None
    except Exception as exc:                                             # noqa: BLE001
        errs["signal_symbols"] = f"{type(exc).__name__}: {exc}"
    try:                                                                 # vision settings: read-only (VC.load would migrate the db)
        from vision import config as VC
        from vision import store as VS
        with ro_connect(VS.db_path()) as c:
            stored = {r["bot"]: r["json"] for r in c.execute("SELECT bot, json FROM vision_settings").fetchall()}
            hist = [dict(r) for r in c.execute("SELECT * FROM vision_settings_history WHERE ts LIKE ? ORDER BY ts",
                                               (cx.day + "%",)).fetchall()]
        vs = {}
        for bot in (VISION_BOT, "_global"):
            raw = json.loads(stored[bot]) if bot in stored else {}
            try:
                eff = VC.validate(bot, raw)
            except Exception as exc:                                     # noqa: BLE001
                eff = {"_validate_error": str(exc), **VC.defaults(bot)} if bot != "_global" else {"_validate_error": str(exc)}
            vs[bot] = {"stored": {k: v for k, v in raw.items() if not secret_name(k)},
                       "effective": {k: v for k, v in (eff or {}).items() if not secret_name(k)}}
        out["vision"] = vs
        out["vision_settings_history_today"] = [scrub_row(r) for r in hist]
    except Exception as exc:                                             # noqa: BLE001
        errs["vision"] = f"{type(exc).__name__}: {exc}"
    out["env_names"] = sorted(k for k in os.environ if re.match(r"^(ENGINE|VISION|PAPER|UPSTOX|SUPABASE|TELEGRAM|ANTHROPIC|TRADE)", k))
    out["errors"] = errs
    cx.out.text("meta/settings.json", dumps(out))
    if f"{STRATEGY_KEY}/{cx.symbol}" not in out:
        raise RuntimeError(f"strategy settings not readable: {errs}")
    cx.ok("2_settings", f"engine3 keys {sorted(cx.engine3_s)} · vision mode "
                        f"{((out.get('vision') or {}).get(VISION_BOT) or {}).get('effective', {}).get('vision_mode')} · errors {len(errs)}")


# ------------------------------------------------------------------------------------------------ 3 live outputs
def section_engine_rows(cx):
    import engine_signal as ES
    with ro_connect(ES.db_path()) as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM engine_signals WHERE bar_ts LIKE ? ORDER BY symbol, bar_ts",
                                           (cx.day + "%",)).fetchall()]
        try:
            cons = [dict(r) for r in c.execute("SELECT * FROM engine_consumed WHERE bar_ts LIKE ? OR at LIKE ?",
                                               (cx.day + "%", cx.day + "%")).fetchall()]
        except sqlite3.Error:
            cons = []
    for r in rows:
        try:
            r["payload_json"] = json.loads(r.get("payload") or "null")
        except ValueError:
            r["payload_json"] = None
    cx.live_rows = rows
    alerts = None
    try:                                                                 # the engine's Telegram alert state (data problem / failing)
        ap_ = ES._alert_path(None) if hasattr(ES, "_alert_path") else os.path.join(cx.repo, "data", "engine_signal_alerts.json")
        alerts = {"path": ap_, "content": json.load(open(ap_, encoding="utf-8")) if os.path.exists(ap_) else None}
    except Exception as exc:                                             # noqa: BLE001
        alerts = {"error": f"{type(exc).__name__}: {exc}"}
    errs = {}
    for r in rows:
        if r.get("decision") == getattr(ES, "ERROR", "error"):
            k = f"{r['symbol']}: {str(r.get('reason') or '')[:160]}"
            errs[k] = errs.get(k, 0) + 1
    cx.out.json("live/engine_signals.json", {"db": ES.db_path(), "rows": rows, "consumed": cons, "alert_state": alerts,
                                             "error_rows_by_reason": errs})
    cx.summary["engine_error_rows"] = errs
    lines = ["symbol,bar_ts,computed_at,decision,gate,direction,level_lo,level_hi,grade,reason"]
    for r in rows:
        lines.append(",".join(json.dumps(r.get(k), ensure_ascii=False, default=str) for k in
                              ("symbol", "bar_ts", "computed_at", "decision", "gate", "direction", "level_lo", "level_hi", "grade", "reason")))
    cx.out.text("live/engine_signals_summary.csv", "\n".join(lines) + "\n", do_redact=False)
    n = {s: sum(1 for r in rows if r["symbol"] == s) for s in sorted({r["symbol"] for r in rows})}
    cx.summary["engine_rows"] = n
    cx.ok("3a_engine_rows", f"{n} · error rows {sum(errs.values())} · consumed {len(cons)}")


def section_vision(cx):
    from vision import store as VS
    with ro_connect(VS.db_path()) as c:
        sig, _ = rows_like(c, "vision_signals", cx.day, ("created_at", "signal_ts", "finished_at", "decided_at", "executed_at"))
        ids = {r["signal_id"] for r in sig}
        ev, _ = rows_like(c, "vision_events", cx.day, ("ts",))
        ev_ids = {r["signal_id"] for r in ev}
        extra = []
        for sid in sorted(ev_ids - ids):                                 # events today for a signal created earlier
            extra += [dict(r) for r in c.execute("SELECT * FROM vision_signals WHERE signal_id=?", (sid,)).fetchall()]
        usage, _ = rows_like(c, "vision_usage", cx.day, ("day", "ts"))
        corr, _ = rows_like(c, "corrections", cx.day, ("ts",))
        try:
            kv = [dict(r) for r in c.execute("SELECT * FROM vision_kv").fetchall()]
        except sqlite3.Error:
            kv = []
    cx.out.json("live/vision.json", {"db": VS.db_path(), "signals": [scrub_row(r) for r in sig + extra],
                                     "events": [scrub_row(r) for r in ev], "usage": [scrub_row(r) for r in usage],
                                     "corrections": [scrub_row(r) for r in corr], "kv": [scrub_row(r) for r in kv]})
    cx.summary["vision_signals"] = len(sig) + len(extra)
    cx.ok("3b_vision", f"signals {len(sig)} (+{len(extra)} earlier) · events {len(ev)} · usage {len(usage)}")


def section_paper(cx):
    from paper import journal as PJ
    with ro_connect(PJ.db_path()) as c:
        pj, _ = rows_like(c, "paper_journal", cx.day, ("entry_time", "exit_time", "last_update_at"))
        wh, _ = rows_like(c, "paper_would_have", cx.day, ("ts",))
    cx.out.json("live/paper_journal.json", {"db": PJ.db_path(), "paper_journal": [scrub_row(r) for r in pj],
                                            "paper_would_have": [scrub_row(r) for r in wh]})
    cx.summary["paper_journal"] = len(pj)
    cx.ok("3c_paper_journal", f"journal {len(pj)} · would_have {len(wh)}")


def section_live_trades(cx):
    import config
    with ro_connect(config.DB_PATH) as c:
        rows, cols = rows_like(c, "live_trades", cx.day, ("trade_date", "entry_time", "exit_time"))
    mcol = next((x for x in ("mode", "trading_mode") if x in cols), None)
    if mcol is None:
        raise RuntimeError("live_trades has no mode column ⇒ cannot tell PAPER from LIVE ⇒ nothing exported")
    paper = [scrub_row({k: v for k, v in r.items() if not k.endswith("order_id")}) for r in rows if str(r.get(mcol) or "").upper() == "PAPER"]
    cx.out.json("live/live_trades_paper.json", {"db": config.DB_PATH, "mode_column": mcol, "rows": paper,
                                                "non_paper_rows_skipped": len(rows) - len(paper)})
    cx.summary["paper_trades"] = len(paper)
    cx.ok("3d_live_trades", f"PAPER rows {len(paper)} (non-PAPER skipped {len(rows) - len(paper)})")


def _day_markers(day):
    d = dt.date.fromisoformat(day)
    return (day, d.strftime("%Y%m%d"), d.strftime("%d-%m-%Y"), d.strftime("%d/%m/%Y"), d.strftime("%d %b %Y"), d.strftime("%b %d"))


def section_logs(cx):
    n_files, notes = 0, []
    d0 = dt.datetime.combine(dt.date.fromisoformat(cx.day), dt.time(0, 0)) - IST     # IST midnight in UTC (mtime check)
    markers = _day_markers(cx.day)
    names = list(LOG_FILES)
    try:
        names += [f for f in sorted(os.listdir(cx.repo)) if f.endswith(".log") and f not in names]
    except OSError:
        pass
    for f in names:
        p = os.path.join(cx.repo, f)
        if not os.path.isfile(p):
            continue
        if dt.datetime.utcfromtimestamp(os.path.getmtime(p)) < d0:
            notes.append(f"{f}: not modified today ⇒ skipped")
            continue
        try:
            size = os.path.getsize(p)
            with open(p, "rb") as fh:                                    # tail only (bounded memory)
                fh.seek(max(0, size - LOG_TAIL_BYTES))
                lines = fh.read().decode("utf-8", "replace").splitlines()
        except OSError as exc:
            notes.append(f"{f}: {exc}")
            continue
        first = next((i for i, ln in enumerate(lines) if any(m in ln for m in markers)), None)
        sel = lines[first:] if first is not None else lines[-5000:]
        how = "from the first line carrying today's date" if first is not None else "no date marker ⇒ last 5000 lines"
        if len(sel) > LOG_MAX_LINES:
            sel, how = sel[-LOG_MAX_LINES:], how + f" · capped to last {LOG_MAX_LINES}"
        cx.out.text(f"logs/{f}.txt", f"# {f} · {how} · size {size} · mtime(UTC) "
                                     f"{dt.datetime.utcfromtimestamp(os.path.getmtime(p)):%Y-%m-%d %H:%M}\n" + "\n".join(sel) + "\n")
        n_files += 1
    if shutil.which("journalctl"):
        since = f"{cx.day} 00:00"
        for u in UNITS:
            rc, txt = sh(["journalctl", "-u", u, "--since", since, "--no-pager", "-o", "short-iso"], timeout=60)
            lines = txt.splitlines()[-LOG_MAX_LINES:]
            cx.out.text(f"logs/journal_{u}.txt", f"# journalctl -u {u} --since '{since}' (host tz) rc {rc}\n" + "\n".join(lines) + "\n")
            n_files += 1
    else:
        notes.append("journalctl not available")
    cx.out.text("logs/_notes.txt", "\n".join(notes) + "\n")
    cx.summary["log_files"] = n_files
    cx.ok("3e_logs", f"{n_files} files (redacted) · {len(notes)} notes")


# ------------------------------------------------------------------------------------------------ 4 inputs
class RecordingFeed:
    """Wraps the live UpstoxFeed: every (symbol, interval, days) series is fetched ONCE (raw, before any cut) and kept in cx.raw.
    Spot series = the feed's own index() (instruments.py key ⇒ history + intraday; never the FUT search). FUT 5M (the live
    feed.futures = instruments/search ⇒ candles) comes from `fut_fn` (source chain, recorded in cx.fut_source)."""

    def __init__(self, feed, raw, fut_fn=None):
        self.feed, self.raw, self.fut_fn = feed, raw, fut_fn

    def __getattr__(self, k):
        return getattr(self.feed, k)

    def index(self, symbol, interval, days):
        key = ("index", str(symbol).upper(), interval, int(days))
        if key not in self.raw:
            self.raw[key] = self.feed.index(symbol, interval, days)
        return self.raw[key].copy()

    def futures(self, symbol, interval, days):
        key = ("futures", str(symbol).upper(), interval, int(days))
        if key not in self.raw:
            self.raw[key] = (self.fut_fn or self.feed.futures)(symbol, interval, days)
        return self.raw[key].copy()


class CutFeed:
    """Replay feed: serves the recorded raw series, only bars CLOSED by `now` (no look-ahead; Daily: up to that date — the engine's
    prepare_daily drops the day's own bar). A series never recorded ⇒ KeyError (no network in the replay)."""
    MIN = {"1minute": 1, "5minute": 5, "15minute": 15}

    def __init__(self, raw, now):
        import pandas as pd
        self.raw, self.now = raw, pd.Timestamp(now)
        self.today = self.now.date()
        self.last_session = None

    def _cut(self, df, interval):
        import pandas as pd
        if df is None or not len(df):
            return df
        ts = pd.to_datetime(df["timestamp"])
        if interval in self.MIN:
            keep = ts + pd.Timedelta(minutes=self.MIN[interval]) <= self.now
        else:
            keep = ts.dt.normalize() <= self.now.normalize()
        return df[keep.to_numpy()].reset_index(drop=True).copy()

    def index(self, symbol, interval, days):
        return self._cut(self.raw[("index", str(symbol).upper(), interval, int(days))], interval)

    def futures(self, symbol, interval, days):
        return self._cut(self.raw[("futures", str(symbol).upper(), interval, int(days))], interval)


def _token():
    import cloud_db
    tok = cloud_db.get_effective_upstox_token(None)
    if not tok:
        raise RuntimeError("Upstox token not available (cloud_db.get_effective_upstox_token) — value never printed")
    return tok


def _fut_from_search_body(body, symbol, day):
    """Same filter as engine3_live.resolve_future (exact name before ' FUT', expiry ≥ day, nearest)."""
    import verify_opportunity_data_availability as V
    rows = [r for r in ((body or {}).get("data") or []) if V._name_before_fut(r.get("trading_symbol")) == symbol.upper()
            and V._expiry_str(r.get("expiry")) >= day]
    if not rows:
        return None
    rows.sort(key=lambda r: V._expiry_str(r.get("expiry")))
    r = rows[0]
    return {"trading_symbol": r.get("trading_symbol"), "instrument_key": r.get("instrument_key"), "expiry": V._expiry_str(r.get("expiry"))}


def section_probe(cx):
    """Which Upstox calls work today: the engine's exact FUT search (once) + one spot historical + one spot intraday call.
    Status + error JSON body only (no token, no headers)."""
    import urllib.parse
    import engine3_live as L
    import verify_opportunity_data_availability as V
    tok = _token()
    day = dt.date.fromisoformat(cx.day)
    exch = getattr(L, "FUT_EXCHANGE", {}).get(cx.symbol, "NSE")
    params = {"query": cx.symbol, "exchanges": exch, "segments": "FO", "instrument_types": "FUT", "page_number": 1, "records": 30}
    out = {"at_ist": str(ist_now())[:19]}
    st, body, err = V._get(f"{V.BASE_V2}/instruments/search", tok, params=params)
    info = _fut_from_search_body(body, cx.symbol, cx.day) if st == 200 else None
    out["fut_search"] = {"url": f"{V.BASE_V2}/instruments/search", "params": params, "status": st, "error_text": err,
                         "body": body if st != 200 else {"rows": len((body or {}).get("data") or []), "front": info}}
    cx.fut_search = {"status": st, "info": info}
    key = L.index_key(cx.symbol)
    r = V.fetch_candles_window(tok, key, "day", day - dt.timedelta(days=7), day)
    out["spot_history_day"] = {"instrument_key": key, "interval": "day", "status": r["status"], "candles": len(r["candles"]),
                               "error_text": r["error"]}
    st2, body2, err2 = V._get(f"{V.BASE_V3}/intraday/{urllib.parse.quote(key, safe='')}/minutes/15", tok)
    out["spot_intraday_15m"] = {"status": st2, "candles": len((((body2 or {}).get("data") or {}).get("candles") or [])),
                                "error_text": err2, "body": body2 if st2 != 200 else None}
    cx.out.text("live/upstox_probe.json", dumps(out))
    cx.summary["probe"] = {"fut_search": st, "spot_history": r["status"], "spot_intraday": st2}
    cx.ok("3f_upstox_probe", f"FUT search HTTP {st} · spot history HTTP {r['status']} · spot intraday HTTP {st2}")


def _master_fut(symbol, day, url=None, max_bytes=400_000_000):
    """Upstox public BOD instrument master (no token): streamed, flat objects regex-matched ⇒ the same front-month rule. Low memory."""
    import urllib.request
    import zlib
    import verify_opportunity_data_availability as V
    url = url or "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
    pat = re.compile(r"\{[^{}]*\}")
    best, buf, seen = None, "", 0
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    with urllib.request.urlopen(url, timeout=60) as resp:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            buf += d.decompress(chunk).decode("utf-8", "replace")
            seen += len(chunk)
            if seen > max_bytes:
                break
            last = 0
            for m in pat.finditer(buf):
                last = m.end()
                txt = m.group(0)
                if '"FUT"' not in txt or symbol.upper() not in txt:
                    continue
                try:
                    o = json.loads(txt)
                except ValueError:
                    continue
                if o.get("instrument_type") != "FUT" or V._name_before_fut(o.get("trading_symbol")) != symbol.upper():
                    continue
                e = V._expiry_str(o.get("expiry"))
                if e >= day and (best is None or e < best["expiry"]):
                    best = {"trading_symbol": o.get("trading_symbol"), "instrument_key": o.get("instrument_key"), "expiry": e}
            buf = buf[last:] if last else buf[-200_000:]
    return best


def _local_fut(repo, symbol, day, days):
    """VPS collector store (collect_index_futures_volume.py): data/oe_futures_5min_<SYM>.parquet (front month, `contract` column ⇒
    legs2 derives the expiry). Read-only. Window = the engine's FUT history window."""
    import pandas as pd
    p = os.path.join(repo, "data", f"oe_futures_5min_{symbol.upper()}.parquet")
    if not os.path.exists(p):
        return None, f"{p} not found"
    f = pd.read_parquet(p)
    f["timestamp"] = pd.to_datetime(f["timestamp"])
    if getattr(f["timestamp"].dt, "tz", None) is not None:
        f["timestamp"] = f["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d = pd.Timestamp(day)
    f = f[(f["timestamp"] >= d - pd.Timedelta(days=int(days))) & (f["timestamp"] < d + pd.Timedelta(days=1))].reset_index(drop=True)
    n_day = int((f["timestamp"].dt.normalize() == d).sum())
    return f, f"{p} · rows {len(f)} · rows on {day}: {n_day} · mtime(UTC) {dt.datetime.utcfromtimestamp(os.path.getmtime(p)):%Y-%m-%d %H:%M}"


def section_inputs(cx):
    import pandas as pd
    import engine3_live as L
    tok = _token()
    day = dt.date.fromisoformat(cx.day)
    run_day = ist_now().date()
    note = None
    if run_day == day:
        feed = L.UpstoxFeed(tok, day)
    else:                                                                # later run: the day's bars come from the history API
        feed = L.UpstoxFeed(tok, day + dt.timedelta(days=1))
        note = f"run on {run_day} ≠ {day}: feed today = {day + dt.timedelta(days=1)} (history to {day})"
    tried = []

    def fut_fn(symbol, interval, days):
        """FUT 5M source chain (recorded): 1 engine search result (probe) ⇒ live feed series · 2 public instrument master ⇒ same
        series · 3 local collector parquet · 4 --fut-key. None ⇒ no FUT (engine: FutVolumeMissing, as live)."""
        info = (getattr(cx, "fut_search", None) or {}).get("info")
        srcs = []
        if info:
            srcs.append(("upstox_search (engine path)", info))
        if cx.a.fut_key:
            srcs.append(("--fut-key", {"trading_symbol": cx.a.fut_contract or f"{symbol} FUT", "instrument_key": cx.a.fut_key,
                                       "expiry": cx.a.fut_expiry}))
        if not info and not cx.a.no_master:
            try:
                m = _master_fut(symbol, cx.day)
                tried.append(f"instrument master ⇒ {m}")
                if m:
                    srcs.append(("upstox_instrument_master (BOD file, no token)", m))
            except Exception as exc:                                     # noqa: BLE001
                tried.append(f"instrument master: {type(exc).__name__}: {str(exc)[:160]}")
        for name, inf in srcs:
            try:
                f = feed._series(inf["instrument_key"], interval, days, contract=inf["trading_symbol"])
                if inf.get("expiry") and len(f):
                    f = f.assign(expiry=pd.Timestamp(inf["expiry"]))
                today_rows = int((pd.to_datetime(f["timestamp"]).dt.normalize() == pd.Timestamp(day)).sum()) if len(f) else 0
                tried.append(f"{name}: {inf} ⇒ rows {len(f)}, on {day}: {today_rows}")
                if len(f) and today_rows:
                    cx.fut_source = {"source": name, "contract": inf}
                    return f
            except Exception as exc:                                     # noqa: BLE001
                tried.append(f"{name}: {type(exc).__name__}: {str(exc)[:160]}")
        try:
            f, why = _local_fut(cx.repo, symbol, cx.day, days)
            tried.append(f"local collector: {why}")
            if f is not None and len(f) and (pd.to_datetime(f["timestamp"]).dt.normalize() == pd.Timestamp(day)).any():
                cx.fut_source = {"source": "local collector parquet", "detail": why}
                return f
        except Exception as exc:                                         # noqa: BLE001
            tried.append(f"local collector: {type(exc).__name__}: {str(exc)[:160]}")
        cx.fut_source = {"source": None, "why": "no FUT 5M with rows on the day from any source"}
        raise L.EngineDataError(f"{symbol}: no FUT 5M source for {cx.day} (see inputs/meta.json fut_tried)")

    rf = RecordingFeed(feed, cx.raw, fut_fn)
    s = cx.engine3_s
    now = pd.Timestamp(cx.now)
    built, errs = {}, {}
    vnote, m1_info = None, None
    try:
        m15, daily, ltf, fut, vnote = L.build_inputs(rf, cx.symbol, now, s)
        built.update(m15=m15, daily=daily, ltf5=ltf, fut5=fut)
    except Exception as exc:                                             # noqa: BLE001 — spot series are still saved / rebuilt below
        errs["build_inputs"] = f"{type(exc).__name__}: {exc}"
        try:                                                             # spot-only engine view (same cuts as build_inputs)
            m15, daily, _l, _f, _n = L.build_inputs(rf, cx.symbol, now, s, levels_only=True)
            built.update(m15=m15, daily=daily)
            built["ltf5"] = spot_ltf(L, rf, cx.symbol, now, s)
        except Exception as exc2:                                        # noqa: BLE001
            errs["spot_only"] = f"{type(exc2).__name__}: {exc2}"
    if "m15" in built and hasattr(L, "load_m1"):
        try:
            built["m1"], m1_info = L.load_m1(rf, cx.symbol, built["m15"], now, s)
        except Exception as exc:                                         # noqa: BLE001
            errs["load_m1"] = f"{type(exc).__name__}: {exc}"
    if "m15" in built:
        try:
            from decision3 import levels as LV
            built["h1"], _ = LV.h1_frame(built["m15"])
        except Exception as exc:                                         # noqa: BLE001
            errs["h1"] = f"{type(exc).__name__}: {exc}"
    files = {}
    for (kind, sym, interval, days), df in cx.raw.items():
        if df is not None:
            cx.out.csv(f"inputs/raw_{kind}_{sym}_{interval}_{days}d", df)
            files[f"inputs/raw_{kind}_{sym}_{interval}_{days}d"] = len(df)
    for k, df in built.items():
        if df is not None:
            cx.out.csv(f"inputs/engine_{cx.symbol}_{k}", df)
            files[f"inputs/engine_{cx.symbol}_{k}"] = len(df)
    sources = {"spot (15M / 5M / 1m / day)": "UpstoxFeed.index (instruments.py index key ⇒ v3 history + intraday) — the live spot path",
               "fut5": getattr(cx, "fut_source", None)}
    meta = {"now": str(now), "symbol": cx.symbol, "settings_s": s, "files_rows": files, "volume_note": vnote, "m1_info": m1_info,
            "sources": sources, "fut_tried": tried, "feed_today": str(feed.today), "feed_note": note, "errors": errs,
            "explain": "raw_* = series exactly as fetched (naive IST, before cuts); engine_* = build_inputs / load_m1 outputs at `now` "
                       "(m15 / daily / ltf5 / fut5 / m1 / h1). Replay cuts raw_* per bar (CutFeed)."}
    cx.out.text("inputs/meta.json", dumps(meta))
    cx.summary["inputs"] = files
    cx.summary["fut_source"] = (getattr(cx, "fut_source", None) or {}).get("source")
    if not any(k[0] == "index" for k in cx.raw):
        raise RuntimeError(f"no spot series fetched: {errs}")
    cx.ok("4_inputs", f"{len(files)} CSV.gz · FUT source {cx.summary['fut_source']} · errors {list(errs)}")


# ------------------------------------------------------------------------------------------------ 5 replay
def _bar_ts(V, i):
    import pandas as pd
    try:
        return str(pd.Timestamp(V._ts[int(i)]))
    except Exception:                                                    # noqa: BLE001
        return None


def v22_extras(V, r, full_levels=False):
    """Diagnosis facts from the V22 object at the decision bar (whatever this commit exposes; each part independent)."""
    from decision3 import method as M
    t = len(V.m15) - 1
    ex, errs = {"t": t}, {}

    def part(name, fn):
        try:
            ex[name] = fn()
        except Exception as exc:                                         # noqa: BLE001
            errs[name] = f"{type(exc).__name__}: {str(exc)[:200]}"
    part("levels_snapshot", lambda: V.levels.snapshot(t))
    if full_levels:
        def all_levels():
            out = []
            for Lv in V.levels.L:
                lo, hi = Lv.band_at(t)
                out.append({"id": Lv.id, "tf": getattr(Lv, "tf", None), "role0": Lv.role0, "role_t": Lv.role_at(t), "lo": lo, "hi": hi,
                            "births": Lv.births, "anchor": Lv.anchor, "born_bar": Lv.born_bar, "born_ts": _bar_ts(V, Lv.born_bar),
                            "state_t": Lv.state_at(t), "dead_bar": Lv.dead_bar,
                            "dead_ts": _bar_ts(V, Lv.dead_bar) if Lv.dead_bar is not None and Lv.dead_bar < len(V.m15) else None,
                            "events": [[b, _bar_ts(V, b), k, d] for b, k, d in Lv.events if b <= t],
                            "bands": [[b, _bar_ts(V, b), l0, h0] for b, l0, h0 in getattr(Lv, "bands", []) if b <= t],
                            "flip_facts": [[b, x] for b, x in getattr(Lv, "flip_facts", []) if b <= t],
                            "lineage": [x for x in getattr(Lv, "lineage", []) if x.get("bar", 0) <= t]})
            return out
        part("levels_all", all_levels)
        part("prior_note", lambda: getattr(V.levels, "prior_note", None))
    trend = r.get("trend_used")
    try:
        from decision3 import trendline as TL
        if hasattr(TL, "swing_line"):
            def lines():
                out = {}
                for nm, d in (("up", M.UP), ("down", M.DOWN)):
                    ln = TL.swing_line(V, t, d)
                    out[nm] = {"line": ln}
                    if ln is not None and hasattr(TL, "reaction_touch"):
                        try:
                            out[nm]["reaction_touch"] = TL.reaction_touch(V, t, d, ln)
                        except Exception as exc:                         # noqa: BLE001
                            out[nm]["reaction_touch_error"] = f"{type(exc).__name__}: {exc}"
                return out
            part("trendlines", lines)
    except Exception as exc:                                             # noqa: BLE001
        errs["trendline_import"] = str(exc)
    act = list(r.get("active_levels") or [])[:8]

    def visits():
        out = []
        for lvl in act:
            d = M._dir(trend, lvl.get("role"))
            vi = dict(V.visit(t, lvl, d))
            for k in list(vi):
                if k in ("start", "prev_end", "approach_from") and vi[k] is not None:
                    vi[k + "_ts"] = _bar_ts(V, vi[k])
            out.append({"id": lvl.get("id"), "tf": lvl.get("tf"), "role": lvl.get("role"), "lo": lvl.get("lo"), "hi": lvl.get("hi"),
                        "state": lvl.get("state"), "dir": d, "visit": vi})
        return out
    if act and hasattr(V, "visit"):
        part("visits", visits)

    def studies():                                                       # decide() keeps only the best area in full: every armed area here
        ok1, why1, st, ctx = V.step1(t)
        out = []
        for lvl in act[:6]:
            dd, chk, extra = V._level_eval(t, ctx["trend"], lvl, ctx.get("cap"), ctx.get("notes"), step_down=bool(ctx.get("step_down")))
            ff = next(((k, str(v[1])) for k, v in chk.items() if v and v[0] is False), (None, None))
            out.append({"id": lvl.get("id"), "tf": lvl.get("tf"), "role": lvl.get("role"), "lo": lvl.get("lo"), "hi": lvl.get("hi"),
                        "verdict": dd, "first_fail": ff, "checklist": chk,
                        **{k: extra.get(k) for k in ("why", "K", "commit", "zone_read", "trendline", "confirming", "missing", "evidence",
                                                     "evidence_list", "flip_retest", "liquidity", "conviction")}})
        return out
    if act and hasattr(V, "_level_eval") and hasattr(V, "step1"):
        part("area_studies", studies)
    ex["errors"] = errs
    return ex


class Capture:
    """Temporarily wraps decision3.engine.V22 so the live compute() path runs unchanged and the built V22 object is kept."""

    def __init__(self):
        self.objs = []

    def __enter__(self):
        from decision3 import engine as E3
        self.E3, self.orig = E3, E3.V22
        objs = self.objs

        class V22Cap(self.orig):
            def __init__(s_, *a, **k):
                super().__init__(*a, **k)
                objs.append(s_)
        V22Cap.__name__ = "V22"
        # engine3_live.v22_kwargs() inspects V22.__init__ (ltf / futures kwargs) ⇒ keep the original signature, same live path
        V22Cap.__init__.__signature__ = inspect.signature(self.orig.__init__)
        E3.V22 = V22Cap
        return self

    def __exit__(self, *exc):
        self.E3.V22 = self.orig
        return False


def spot_ltf(L, feed, symbol, now, s):
    """5M spot LTF exactly as build_inputs cuts it (closed session bars; NIFTY ⇒ data_policy annotation filter)."""
    ltf = L.closed_session_bars(feed.index(symbol, "5minute", {**L.DEFAULTS, **(s or {})}["engine3_ltf_days"]), 5, now)
    from decision3 import history as HI
    if HI.is_nifty(symbol):
        from elliott import data_policy as DP
        ltf = DP.filter_allowed(ltf, "annotation")
    return ltf


def replay_compute(cx, feed, now_b):
    """The live compute() path. If it stops on FutVolumeMissing (no FUT 5M — as the live engine did when the FUT search failed), a
    second, clearly labelled reading WITHOUT FUT (fut=None ⇒ V22's own c0 'volume NA' data problem) shows everything before it."""
    import engine3_live as L
    try:
        return L.compute(cx.symbol, feed, now_b, cx.engine3_s), "live_path"
    except getattr(L, "FutVolumeMissing", ()) as exc:
        s = cx.engine3_s
        m15, daily, _l, _f, _n = L.build_inputs(feed, cx.symbol, now_b, s, levels_only=True)
        ltf = spot_ltf(L, feed, cx.symbol, now_b, s)
        m1, info = L.load_m1(feed, cx.symbol, m15, now_b, s)
        r = L.evaluate(cx.symbol, m15, daily, ltf, None, s3=L.swing_scale(s), m1=m1, m1_info=info)
        r["volume_note"] = f"REPLAY WITHOUT FUT (live path stopped: {str(exc)[:200]})"
        r["m1"] = info
        return r, "no_fut_reading (live path = FutVolumeMissing ⇒ no reading; this is the reading without FUT volume)"


def replay_bars(day, now):
    """15M bar ends 09:30 … min(now floor 15, 15:30) of the day."""
    d = dt.date.fromisoformat(day)
    t = dt.datetime.combine(d, dt.time(9, 30))
    last = min(now.replace(minute=now.minute - now.minute % 15, second=0, microsecond=0), dt.datetime.combine(d, dt.time(15, 30)))
    out = []
    while t <= last:
        out.append(t)
        t += dt.timedelta(minutes=15)
    return out


def section_replay(cx):
    import pandas as pd
    import engine3_live as L
    if not any(k[0] == "index" and k[1] == cx.symbol for k in cx.raw):
        raise RuntimeError("no recorded inputs (section 4 failed) ⇒ replay skipped")
    live = {r["bar_ts"]: r for r in cx.live_rows if r["symbol"] == cx.symbol}
    bars = replay_bars(cx.day, cx.now)
    if cx.a.bars:
        want = {x.strip() for x in cx.a.bars.split(",")}
        bars = [b for b in bars if b.strftime("%H:%M") in want]
    t0, n_ok, n_err, mism, comp = time.time(), 0, 0, 0, []
    try:
        import engine_signal as ES
        in_window = ES.in_window
    except Exception:                                                    # noqa: BLE001
        in_window = lambda b, s=None: None                               # noqa: E731
    for i, be in enumerate(bars):
        if (time.time() - t0) / 60 > cx.a.replay_max_min:
            print(f"⏹️ replay budget {cx.a.replay_max_min} min reached at {be:%H:%M} ⇒ stop")
            cx.summary["replay_stopped_at"] = f"{be:%H:%M}"
            break
        now_b = pd.Timestamp(be) + pd.Timedelta(minutes=1)                # cron minute (:01 / :16 / :31 / :46)
        rec = {"bar_end": str(pd.Timestamp(be)), "now": str(now_b), "in_live_window": in_window(str(pd.Timestamp(be)))}
        tb = time.time()
        try:
            feed = CutFeed(cx.raw, now_b)
            with Capture() as cap:
                r, mode = replay_compute(cx, feed, now_b)
            rec["mode"] = mode
            V = cap.objs[-1] if cap.objs else None
            row = L.row_from_v22(cx.symbol, r, lambda: str(now_b))
            orig = L.fit_payload
            try:                                                         # same payload, un-trimmed
                L.fit_payload = lambda p, limit=None: json.dumps(p, ensure_ascii=False, default=str)
                full = L.row_from_v22(cx.symbol, r, lambda: str(now_b))["payload"]
            finally:
                L.fit_payload = orig
            rec.update(row=row, payload_full=json.loads(full), decide=r, v22_objects_built=len(cap.objs))
            if V is not None:
                rec["extras"] = v22_extras(V, r, full_levels=(i == len(bars) - 1))
                if i == len(bars) - 1:
                    try:
                        cx.out.csv(f"replay/v22_m15_index_{cx.symbol}", V.m15[["timestamp", "bar_end"]].reset_index().rename(columns={"index": "bar"}))
                    except Exception as exc:                             # noqa: BLE001
                        rec["m15_index_error"] = str(exc)
            lv = live.get(row["bar_ts"])
            keys = ("decision", "gate", "direction", "level_lo", "level_hi", "grade")
            diff = None if lv is None else {k: [lv.get(k), row.get(k)] for k in keys if str(lv.get(k)) != str(row.get(k))}
            if diff:
                mism += 1 if "decision" in diff else 0
            comp.append({"bar_ts": row["bar_ts"], "live": None if lv is None else {k: lv.get(k) for k in keys + ("reason",)},
                         "replay": {k: row.get(k) for k in keys + ("reason",)}, "diff": diff, "mode": mode, "secs": round(time.time() - tb, 1)})
            n_ok += 1
            print(f"   {be:%H:%M} [{mode[:10]}] {row['decision']:<9} gate {row.get('gate') or '—':<4} dir {row.get('direction')} · live "
                  f"{(lv or {}).get('decision', '—')} {'≠' if diff and 'decision' in diff else ''} ({time.time() - tb:.0f}s)")
        except Exception as exc:                                         # noqa: BLE001 — one bar never stops the rest
            n_err += 1
            rec["error"] = f"{type(exc).__name__}: {exc}"
            rec["traceback"] = traceback.format_exc()[-4000:]
            lv = live.get(str(pd.Timestamp(be)))
            comp.append({"bar_ts": str(pd.Timestamp(be)), "live": None if lv is None else {k: lv.get(k) for k in ("decision", "gate", "reason")},
                         "replay": {"error": rec["error"]}})
            print(f"   {be:%H:%M} ❌ {type(exc).__name__}: {redact(str(exc))[:160]}")
        rec["secs"] = round(time.time() - tb, 1)
        cx.out.json(f"replay/bars/{cx.symbol}_{be:%H%M}.json", rec, gz=True)
        del rec
        gc.collect()
    cx.out.json("replay/compare.json", {"symbol": cx.symbol, "commit": cx.summary.get("commit"), "bars": comp})
    modes = {}
    for b in comp:
        modes[b.get("mode")] = modes.get(b.get("mode"), 0) + 1
    cx.summary["replay"] = {"modes": modes, "bars": n_ok, "errors": n_err, "decision_mismatches": mism, "minutes": round((time.time() - t0) / 60, 1)}
    if n_ok == 0 and bars:
        raise RuntimeError(f"no bar replayed ({n_err} errors)")
    cx.ok("5_replay", f"bars {n_ok} · errors {n_err} · live≠replay decisions {mism}")


# ------------------------------------------------------------------------------------------------ 6 push
def git_td(td, *a, timeout=120):
    return sh(["git", "-C", td, *a], timeout=timeout)


def pick_out_dir(td, day, sub="vps"):
    base = os.path.join(td, "review", "diagnosis_today", day)
    p, n = os.path.join(base, sub), 2
    while os.path.exists(p):                                             # never overwrite an earlier export
        p, n = os.path.join(base, f"{sub}_run{n}"), n + 1
    return p


def push(cx, td, folder, msg):
    rel = os.path.relpath(folder, td)
    rc, out = git_td(td, "add", "--ignore-removal", "--", rel)
    if rc:
        raise RuntimeError(f"git add: {out[-300:]}")
    rc, out = git_td(td, "-c", "user.name=vps-data-export", "-c", "user.email=vps-data-export@localhost", "commit", "-q", "-m", msg,
                     "--", rel)
    if rc and "nothing to commit" not in out:
        raise RuntimeError(f"git commit: {out[-300:]}")
    rc, out = git_td(td, "push", "-q", "origin", "HEAD:main", timeout=300)
    if rc:
        git_td(td, "pull", "-q", "--rebase", "--autostash", "origin", "main", timeout=300)
        rc, out = git_td(td, "push", "-q", "origin", "HEAD:main", timeout=300)
    if rc:
        raise RuntimeError(f"git push failed: {redact(out)[-300:]}")
    return git_td(td, "rev-parse", "--short", "HEAD")[1].strip()


def tarball(cx, folder):
    p = f"/root/diagnosis_{cx.day}.tgz" if os.path.isdir("/root") and os.access("/root", os.W_OK) else \
        os.path.join(tempfile.gettempdir(), f"diagnosis_{cx.day}.tgz")
    base, n = p[:-4], 2
    while os.path.exists(p):
        p, n = f"{base}_{n}.tgz", n + 1
    import tarfile
    with tarfile.open(p, "w:gz") as tf:
        tf.add(folder, arcname=os.path.basename(os.path.dirname(folder)) + "/" + os.path.basename(folder))
    return p, hashlib.sha256(open(p, "rb").read()).hexdigest()


def section_push(cx, td, folder, tag):
    name = f"6_push_{tag}"
    try:
        sha = push(cx, td, folder, f"diagnosis: {cx.symbol} {cx.day} VPS export ({tag}) — Trade {cx.summary.get('commit')}")
        cx.summary[f"pushed_{tag}"] = sha
        cx.ok(name, f"trade-data {sha} · {os.path.relpath(folder, td)}")
    except Exception as exc:                                             # noqa: BLE001
        cx.fail(name, exc)
        try:
            p, h = tarball(cx, folder)
            cx.summary[f"tarball_{tag}"] = {"path": p, "sha256": h}
            print(f"📦 tarball {p} sha256 {h}")
        except Exception as exc2:                                        # noqa: BLE001
            print(f"❌ tarball: {exc2}")


# ------------------------------------------------------------------------------------------------ main
def lower_priority():
    try:
        os.nice(10)
    except OSError:
        pass
    if shutil.which("ionice"):
        sh(["ionice", "-c3", "-p", str(os.getpid())])


def main(argv=None, clock=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--day", required=True, help="YYYY-MM-DD (IST)")
    ap.add_argument("--now", default=None, help="HH:MM IST on --day (default: current IST, capped at 15:30)")
    ap.add_argument("--repo", default=os.getcwd(), help="deployed Trade tree (default: cwd = /root/Trade)")
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA_DIR") or "/root/trade-data")
    ap.add_argument("--out-dir", default=None, help="write here instead of trade-data (tests); implies --no-push")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--replay", dest="replay", action="store_true", default=True)
    ap.add_argument("--no-replay", dest="replay", action="store_false")
    ap.add_argument("--bars", default=None, help="replay only these bar ends, e.g. 10:15,11:00")
    ap.add_argument("--replay-max-min", type=float, default=60.0, help="replay time budget (minutes)")
    ap.add_argument("--fut-key", default=None, help="FUT instrument key (e.g. NSE_FO|12345) if the search API fails")
    ap.add_argument("--fut-contract", default=None, help="its trading symbol (for the expiry, e.g. 'NIFTY FUT 27 OCT 26')")
    ap.add_argument("--fut-expiry", default=None, help="its expiry YYYY-MM-DD")
    ap.add_argument("--no-master", action="store_true", help="do not try the public Upstox instrument master for the FUT key")
    ap.add_argument("--skip", default="", help="comma list of sections to skip: code,settings,engine,vision,paper,trades,logs,inputs")
    a = ap.parse_args(argv)
    dt.date.fromisoformat(a.day)
    repo = os.path.abspath(a.repo)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    load_env_secrets()
    lower_priority()
    tmp_cache = tempfile.mkdtemp(prefix="diag_engine3_cache_")
    os.environ["ENGINE3_CACHE_DIR"] = tmp_cache                          # engine3 hist_ / fold_ caches ⇒ private (never the bot's)
    td = os.path.abspath(a.trade_data)
    push_ok = not a.no_push and a.out_dir is None
    if push_ok:
        rc, out = git_td(td, "pull", "--ff-only", "-q", timeout=300)
        print(("✅" if rc == 0 else "⚠️") + f" trade-data pull --ff-only: {'ok' if rc == 0 else redact(out)[-200:]}")
    folder = os.path.abspath(a.out_dir) if a.out_dir else pick_out_dir(td, a.day)
    if os.path.exists(folder) and os.listdir(folder):
        print(f"❌ {folder} exists and is not empty — refusing to overwrite")
        return 2
    os.makedirs(folder, exist_ok=True)
    cx = Ctx(a, repo, Out(folder))
    cx.now = effective_now(a.day, a.now, clock)
    skip = {x.strip() for x in a.skip.split(",") if x.strip()}
    print(f"🩺 diagnose_day_export · {cx.symbol} {a.day} · now {cx.now:%H:%M} IST · repo {repo} · out {folder}")
    plan = [("code", "1_code", section_code), ("settings", "2_settings", section_settings),
            ("engine", "3a_engine_rows", section_engine_rows), ("vision", "3b_vision", section_vision),
            ("paper", "3c_paper_journal", section_paper), ("trades", "3d_live_trades", section_live_trades),
            ("logs", "3e_logs", section_logs), ("probe", "3f_upstox_probe", section_probe), ("inputs", "4_inputs", section_inputs)]
    for key, name, fn in plan:
        if key in skip:
            print(f"⏭️ {name}: skipped (--skip)")
            continue
        try:
            fn(cx)
        except Exception as exc:                                         # noqa: BLE001 — one section never stops the others
            cx.fail(name, exc)

    def write_summary(tag):
        s = {"tag": tag, "symbol": cx.symbol, "day": a.day, "now": str(cx.now), "generated_ist": str(ist_now())[:19],
             "sections": {k: {"ok": v[0], "note": v[1]} for k, v in cx.status.items()}, **cx.summary}
        cx.out.text(f"SUMMARY_{tag}.json", dumps(s))
    write_summary("export")
    if push_ok:
        section_push(cx, td, folder, "export")
    if a.replay:
        try:
            section_replay(cx)
        except Exception as exc:                                         # noqa: BLE001
            cx.fail("5_replay", exc)
        write_summary("replay")
        if push_ok:
            section_push(cx, td, folder, "replay")
    shutil.rmtree(tmp_cache, ignore_errors=True)
    live_ok = bool(cx.status.get("3a_engine_rows", (False,))[0])
    print("\n======== PASTE BACK FROM HERE ========")
    print(f"diagnose_day_export {cx.symbol} {a.day} now {cx.now:%H:%M} · Trade HEAD {cx.summary.get('commit')} · out {folder}")
    for k, (ok, note) in cx.status.items():
        print(f"{'✅' if ok else '❌'} {k}: {note}")
    for k in ("engine_rows", "engine_error_rows", "probe", "fut_source", "vision_signals", "paper_journal", "paper_trades", "log_files", "replay", "replay_stopped_at",
              "pushed_export", "pushed_replay", "tarball_export", "tarball_replay"):
        if k in cx.summary:
            print(f"   {k}: {json.dumps(clean(cx.summary[k]), ensure_ascii=False)}")
    print("======== END ========")
    return 0 if live_ok else 1


if __name__ == "__main__":
    sys.exit(main())
