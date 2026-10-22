"""scripts/vision_trail_report.py — READ-ONLY trail of Vision V1 signals (Abhi handover T-1 point 6, T-5 point 1).

Abhi runs it on the VPS (a session never does). Every database is opened read-only (sqlite `mode=ro`); nothing is written anywhere
except the JSON file named by --out. No token / secret is read or printed.

  python3 scripts/vision_trail_report.py --day 2026-10-22 --symbol NIFTY --direction BEARISH --level 22761          # T-1 card trail
  python3 scripts/vision_trail_report.py --day 2026-10-22 --timeouts                                                  # every V1 timeout
  python3 scripts/vision_trail_report.py --day 2026-10-22 --symbol NIFTY --direction BEARISH --level 22747 --audit     # T-5 audit

Per signal: signal_id, card time + Telegram message id, buttons attached or not (and why), deadline, the decision (who / when /
why), what followed (SHADOWED / EXPIRED / … and the note), the linked shadow trade and its P&L, the would-have note, the events.
--audit adds Vision's own verdict vs the verdict after the code floor, the rule ids that fired, the checklist, the l_line / gap
context, prompt_version / model, the image Vision received (path + sha256) and the engine's reading (setup tags + engine store).
"""
import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _ro(path):
    if not path or not os.path.exists(path):
        return None
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _rows(c, q, args=()):
    if c is None:
        return []
    try:
        return [dict(r) for r in c.execute(q, args).fetchall()]
    except sqlite3.Error as exc:
        return [{"error": f"{exc}"}]


def _json(x):
    try:
        return json.loads(x) if isinstance(x, str) and x else (x or {})
    except ValueError:
        return {"raw": x}


def _paths():
    from paper import journal as PJ
    from vision import store as VS
    import engine_signal as ES
    try:
        from config import DB_PATH
    except Exception:                                                    # noqa: BLE001
        DB_PATH = os.path.join(ROOT, "data", "historical_data.db")
    return {"vision": VS.db_path(), "trades": DB_PATH, "journal": PJ.db_path(), "engine": ES.db_path() if hasattr(ES, "db_path") else
            os.environ.get("ENGINE_SIGNAL_DB") or os.path.join(ROOT, "data", "engine_signals.db")}


def trail(sig, dbs):
    sid = sig["signal_id"]
    reason = sig.get("decision_reason") or ""
    out = {k: sig.get(k) for k in ("signal_id", "bot", "symbol", "direction", "level", "signal_ts", "created_at", "finished_at", "mode",
                                   "verdict", "tg_message_id", "notified", "deadline", "timeout_status", "decided_at", "decided_by",
                                   "decision_reason", "human_decision", "human_ts", "reject_reason", "status", "executed_at",
                                   "exec_note", "drift_result", "trade_id")}
    out["buttons_attached"] = not ("approver नाही" in reason or sig.get("deadline") is None)
    out["events"] = _rows(dbs["vision"], "SELECT ts, event, detail FROM vision_events WHERE signal_id=? ORDER BY ts", (sid,))
    src = f"{sig.get('bot')}_vision_shadow"
    q = ("SELECT trade_id, source, entry_time, exit_time, status, realized_pnl, exit_reason FROM live_trades WHERE mode='PAPER' "
         "AND source=? AND (trade_id=? OR (entry_time>=? AND entry_time<=datetime(?, '+10 minutes')))")
    ex = sig.get("executed_at") or ""
    out["shadow_trades"] = _rows(dbs["trades"], q, (src, sig.get("trade_id") or "", ex, ex)) if ex or sig.get("trade_id") else []
    out["would_have"] = _rows(dbs["journal"], "SELECT * FROM paper_would_have WHERE signal_id=?", (sid,))
    out["outcome"] = _json(sig.get("outcome_json"))
    return out


def audit(sig, dbs):
    vj = _json(sig.get("vision_json"))
    a0 = (vj.get("audits") or [{}])[0]
    ctx = vj.get("context") or {}
    tags = (_json(sig.get("setup_json")) or {}).get("tags") or {}
    eng = []
    if tags.get("entry_trigger_ts"):
        eng = _rows(dbs["engine"], "SELECT * FROM engine_signals WHERE symbol=? AND bar_ts=?", (sig.get("symbol"), tags["entry_trigger_ts"]))
    return {"vision_own_verdict": a0.get("verdict"), "vision_reason": a0.get("reason"), "verdicts_after_floor": vj.get("verdicts"),
            "rule_hits": vj.get("rule_hits"), "code_overrides": a0.get("code_overrides"), "checklist": a0,
            "l_line": ctx.get("l_line"), "gap_ctx": ctx.get("gap_ctx"), "time_flag": ctx.get("time_flag"),
            "prompt_version": sig.get("prompt_version"), "model": sig.get("model"), "image_path": sig.get("image_path"),
            "image_sha256": sig.get("image_sha256"), "v4_json": _json(sig.get("v4_json")), "engine_tags": tags,
            "engine_store": [{**r, "payload": _json(r.get("payload"))} for r in eng]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--symbol")
    ap.add_argument("--direction")
    ap.add_argument("--level", type=float)
    ap.add_argument("--bot")
    ap.add_argument("--timeouts", action="store_true", help="every V1 signal of the day decided by timeout")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    p = _paths()
    dbs = {k: _ro(v) for k, v in p.items()}
    if dbs["vision"] is None:
        print(f"❌ vision.db not found ({p['vision']})")
        return 2
    q, args = "SELECT * FROM vision_signals WHERE substr(signal_ts,1,10)=?", [a.day]
    if a.timeouts:
        q += " AND decided_by='timeout'"
    for col, v in (("symbol", a.symbol), ("direction", a.direction), ("bot", a.bot)):
        if v:
            q += f" AND {col}=?"
            args.append(v)
    if a.level is not None:
        q += " AND round(level)=?"
        args.append(round(a.level))
    sigs = _rows(dbs["vision"], q + " ORDER BY signal_ts", args)
    rep = []
    for s in sigs:
        r = trail(s, dbs)
        if a.audit:
            r["audit"] = audit(s, dbs)
        rep.append(r)
        print(f"· {r['signal_id']} {r['bot']} {r['symbol']} {r['direction']} L{r['level']} · card {r['finished_at']} msg "
              f"{r['tg_message_id']} · buttons {'yes' if r['buttons_attached'] else 'NO'} · deadline {r['deadline']} · decided "
              f"{r['decided_by']} {r['decided_at']} · {r['status']} · {r['exec_note'] or ''} · shadow trades {len(r['shadow_trades'])}")
    out = a.out or os.path.join(os.path.expanduser("~"), f"vision_trail_{a.day}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"day": a.day, "dbs": {k: bool(v) for k, v in dbs.items()}, "signals": rep}, f, ensure_ascii=False, indent=1, default=str)
    print(f"✅ {len(rep)} signal(s) · full trail: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
