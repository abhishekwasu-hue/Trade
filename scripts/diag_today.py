#!/usr/bin/env python3
"""🩺 diag_today (read-only, VPS): "आज Telegram ला setup का आला नाही?" — docs/reports चा no-signals अहवाल भरण्यासाठी एक file.

काहीही लिहीत / बदलत नाही (फक्त --out file). Secrets नाहीत: token / key / secret सारखे शब्द व लांब tokens redacted; .env वाचत नाही.
  • code: VPS git commit, branch, deploy rollback file (/root/paper_rollback.txt), आजचे reflog (checkout केव्हा ⇒ deploy 09:15 आधी?)
  • settings: प्रत्येक bot × symbol enabled / trading_mode / entry_mode / signal_source (dashboard चेच getters), Vision, PAPER instruments
  • cron + systemd अवस्था; one_bot_status() ओळ
  • आजचा per-15M-bar निर्णय log: engine store (engine_signals) + signal_log (bots) + level-gate trend cache + Vision signals + log tails
    python3 scripts/diag_today.py --out /root/diag_today.txt [--day YYYYMMDD]
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SECRET = re.compile(r"(?i)(token|secret|password|api[_-]?key|bearer|authorization)([\"'=:\s]+)(\S+)")
LONG = re.compile(r"[A-Za-z0-9_\-\.]{40,}")
SERVICES = ("vision_worker", "vision_telegram", "position_stream_monitor", "position_stream_monitor_mcx", "streamlit_dashboard",
            "upstox_token_webhook", "engine_service.timer")
LOGS = ("engine_signal.log", "srv2.log", "dsr.log", "classic_sr.log", "monitor.log", "mcx_futures.log")


def redact(s):
    s = SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", str(s))
    return LONG.sub(lambda m: m.group(0) if "/" in m.group(0) or m.group(0).count(".") > 2 else "<redacted>", s)


def sh(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        return (r.stdout + (r.stderr if r.returncode else "")).strip()
    except Exception as exc:                                             # noqa: BLE001
        return f"<{type(exc).__name__}: {exc}>"


class Out:
    def __init__(self):
        self.lines = []

    def h(self, t):
        self.lines += ["", "=" * 100, t, "=" * 100]

    def p(self, *a):
        self.lines.append(redact(" ".join(str(x) for x in a)))


def section_code(o, day):
    o.h("1. CODE (VPS)")
    o.p("HEAD:", sh(["git", "log", "-1", "--format=%H %ci %s"]))
    o.p("branch:", sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]))
    o.p("dirty (tracked):", sh(["git", "status", "--short", "--untracked-files=no"]) or "clean")
    for f in ("/root/paper_rollback.txt",):
        o.p(f"rollback file {f}:", open(f).read().strip() if os.path.exists(f) else "absent",
            f"(mtime {dt.datetime.fromtimestamp(os.path.getmtime(f)):%H:%M %d/%m})" if os.path.exists(f) else "")
    o.p("reflog (HEAD moves; deploy time ⇒ before / after 09:15 IST?):")
    o.p(sh(["git", "reflog", "--date=iso", "-n", "25"]))
    o.p("origin/main:", sh(["git", "log", "-1", "--format=%H %ci", "origin/main"]))


def section_settings(o):
    o.h("2. SETTINGS (dashboard getters) — bot × symbol")
    try:
        import cloud_db
        from bots_common import one_bot as OB
        from bots_common import level_gate_bot as LGB
        keys = ("symbol_enabled", "trading_mode", "signal_source", "srv3_signal_source", "srv3_shadow_enabled", "otm_shadow_enabled",
                "min_hold_shadow_enabled", "active_timeframes")
        for strat in ("15m_dynamic_sr", "1m_instant", "classic_sr_reversal"):
            for sym in OB.SYMBOLS:
                s = cloud_db.get_strategy_settings(strat, sym)
                o.p(f"{strat:<20} {sym:<10}", {k: s.get(k) for k in keys if k in s}, "entry_mode(effective):", LGB.entry_mode(s),
                    "| stored:", sorted(cloud_db.get_strategy_settings_raw(strat, sym)))
        for sym in OB.mcx_symbols():
            s = cloud_db.get_strategy_settings("mcx_futures", sym)
            o.p(f"{'mcx_futures':<20} {sym:<10}", {k: s.get(k) for k in ("symbol_enabled", "trading_mode")}, "entry_mode:", LGB.entry_mode(s))
    except Exception as exc:                                             # noqa: BLE001
        o.p("settings error:", type(exc).__name__, exc)
    try:
        from vision import config as VC
        for bot in VC.BOTS:
            s = VC.load(bot)
            o.p(f"vision {bot:<24}", {k: s.get(k) for k in ("vision_mode", "approval_required", "symbols", "level_gate")})
    except Exception as exc:                                             # noqa: BLE001
        o.p("vision settings error:", exc)
    try:
        from paper import config as PC
        o.p("PAPER instruments (config.yaml + local):", PC.load().get("instruments"), "| local file:", PC.local_path(),
            "exists" if os.path.exists(PC.local_path()) else "absent")
        from paper import pause as PP
        o.p("PAPER pause:", PP.paused())
    except Exception as exc:                                             # noqa: BLE001
        o.p("paper config error:", exc)
    try:
        import cloud_db
        o.p("kill switch:", cloud_db.get_kill_switch_settings(), "| trading pause:", cloud_db.get_trading_pause_settings())
    except Exception as exc:                                             # noqa: BLE001
        o.p("kill switch error:", exc)


def section_cron(o):
    o.h("3. CRON + SYSTEMD")
    o.p(sh(["crontab", "-l"]))
    for u in SERVICES:
        o.p(f"{u}: {sh(['systemctl', 'is-active', u])} / {sh(['systemctl', 'is-enabled', u])}")
    try:
        from bots_common import one_bot as OB
        st = OB.one_bot_status()
        o.p("one_bot_status:", st["line"])
        for r in st["bots"]:
            o.p("  ", r)
    except Exception as exc:                                             # noqa: BLE001
        o.p("one_bot_status error:", exc)


def section_logs(o, day):
    d_iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    o.h("4a. ENGINE STORE — per-15M-bar decisions today (engine_signals)")
    try:
        import engine_signal as ES
        with sqlite3.connect(ES.db_path()) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("SELECT symbol, bar_ts, decision, gate, direction, level_lo, level_hi, grade, reason, payload FROM engine_signals "
                             "WHERE bar_ts LIKE ? ORDER BY symbol, bar_ts", (d_iso + "%",)).fetchall()
            cons = c.execute("SELECT * FROM engine_consumed WHERE bar_ts LIKE ?", (d_iso + "%",)).fetchall()
        o.p(f"db {ES.db_path()} · rows {len(rows)}")
        for r in rows:
            eng = ""
            try:
                eng = json.loads(r["payload"] or "{}").get("engine") or ("decision2" if r["payload"] else "")
            except ValueError:
                pass
            o.p(f"  {r['symbol']:<10} {r['bar_ts'][11:16]} [{eng or '?'}] {r['decision']:<9} gate {r['gate'] or '—':<6} dir {r['direction']} "
                f"area {r['level_lo']}–{r['level_hi']} grade {r['grade']} · {str(r['reason'] or '')[:140]}")
        for r in cons:
            o.p("  consumed:", dict(r))
    except Exception as exc:                                             # noqa: BLE001
        o.p("engine store error:", exc)
    o.h("4b. SIGNAL LOG (bots, Supabase) — today")
    try:
        import cloud_db
        for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
            df = cloud_db.get_signal_log(sym, d_iso)
            o.p(f"{sym}: {0 if df is None else len(df)} rows")
            if df is not None:
                for _, r in df.sort_values("signal_time").iterrows():
                    o.p(f"  {r['signal_time']} {r['level_type']} {r['level_price']} {r['hit_type']} {r['direction']} {r['trade_status']} · "
                        f"{str(r['reason'])[:160]}")
    except Exception as exc:                                             # noqa: BLE001
        o.p("signal log error:", exc)
    o.h("4c. LEVEL-GATE trend cache (data/level_gate) — today")
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "level_gate", f"*{d_iso}*"))):
        o.p(os.path.basename(f), open(f, encoding="utf-8").read()[:600])
    o.h("4d. VISION signals today")
    try:
        from vision import store as VS
        with VS.connect() as c:
            c.row_factory = sqlite3.Row
            for r in c.execute("SELECT * FROM vision_signals WHERE created_at LIKE ? ORDER BY created_at", (d_iso + "%",)).fetchall():
                r = dict(r)
                o.p({k: r.get(k) for k in ("created_at", "bot", "symbol", "direction", "level", "setup_tf", "status", "verdict", "exec_note")
                     if k in r})
    except Exception as exc:                                             # noqa: BLE001
        o.p("vision store error:", exc)
    o.h("4e. LOG TAILS (redacted)")
    for f in LOGS:
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            o.p(f"{f}: absent")
            continue
        try:
            tail = open(p, encoding="utf-8", errors="replace").read().splitlines()[-400:]
        except OSError as exc:
            o.p(f"{f}: {exc}")
            continue
        o.p(f"--- {f} (last {len(tail)} lines, mtime {dt.datetime.fromtimestamp(os.path.getmtime(p)):%H:%M %d/%m})")
        for ln in tail:
            o.p("  " + ln[:300])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--day", default=None, help="YYYYMMDD (default: आज, IST)")
    a = ap.parse_args(argv)
    day = a.day or (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).strftime("%Y%m%d")
    o = Out()
    o.p(f"diag_today · day {day} · generated {dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30):%H:%M} IST · read-only")
    for fn in (section_code, lambda o_, d_: section_settings(o_), lambda o_, d_: section_cron(o_), section_logs):
        try:
            fn(o, day)
        except Exception as exc:                                         # noqa: BLE001
            o.p("section error:", type(exc).__name__, exc)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(o.lines) + "\n")
    print(f"✅ {a.out} ({len(o.lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
