"""scripts/vision_trail_report.py (handover T-1 point 6 / T-5 point 1): read-only trail of a V1 signal; databases never written."""
import importlib.util
import json
import os
import sqlite3

from vision import store as VS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _script():
    spec = importlib.util.spec_from_file_location("vtr", os.path.join(ROOT, "scripts", "vision_trail_report.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_trail_and_audit_read_only(tmp_path, monkeypatch):
    vdb, tdb, jdb, edb = (str(tmp_path / n) for n in ("vision.db", "t.db", "j.db", "e.db"))
    monkeypatch.setenv("VISION_DB_PATH", vdb)
    monkeypatch.setenv("PAPER_JOURNAL_DB", jdb)
    monkeypatch.setenv("ENGINE_SIGNAL_DB", edb)
    sid = VS.insert_signal({"bot": "srv2_momentum_reversal", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "approve",
                            "signal_ts": "2026-10-22 10:15:00", "direction": "BEARISH", "level": 22761.2, "setup_tf": "15M",
                            "setup": {"tags": {"engine": True}}}, path=vdb)
    vj = {"audits": [{"verdict": "agree", "reason": "ok"}], "verdicts": ["disagree"], "rule_hits": [{"disagree": ["opening"]}],
          "context": {"l_line": {"approach": "from_below"}, "gap_ctx": {"class": "G2"}}}
    with sqlite3.connect(vdb) as c:
        c.execute("UPDATE vision_signals SET status='SHADOWED', decided_by='timeout', deadline='2026-10-22 10:25:00', tg_message_id=77, "
                  "executed_at='2026-10-22 10:30:00', exec_note='shadow (rejected)', vision_json=? WHERE signal_id=?", (json.dumps(vj), sid))
        c.execute("INSERT INTO vision_events VALUES ('2026-10-22 10:25:00', ?, 'PENDING_HUMAN→REJECTED', '{}')", (sid,))
    with sqlite3.connect(tdb) as c:
        c.execute("CREATE TABLE live_trades (trade_id TEXT, source TEXT, entry_time TEXT, exit_time TEXT, status TEXT, realized_pnl REAL, "
                  "exit_reason TEXT, mode TEXT)")
        c.execute("INSERT INTO live_trades VALUES ('S1','srv2_momentum_reversal_vision_shadow','2026-10-22 10:31:00',NULL,'OPEN',NULL,NULL,"
                  "'PAPER')")
    S = _script()
    monkeypatch.setattr(S, "_paths", lambda: {"vision": vdb, "trades": tdb, "journal": jdb, "engine": edb})
    before = {p: os.path.getmtime(p) for p in (vdb, tdb)}
    out = str(tmp_path / "r.json")
    assert S.main(["--day", "2026-10-22", "--symbol", "NIFTY", "--direction", "BEARISH", "--level", "22761", "--audit",
                   "--out", out]) == 0
    assert {p: os.path.getmtime(p) for p in (vdb, tdb)} == before                       # read-only
    r = json.load(open(out, encoding="utf-8"))["signals"][0]
    assert r["signal_id"] == sid and r["status"] == "SHADOWED" and r["buttons_attached"] and r["tg_message_id"] == 77
    assert [t["trade_id"] for t in r["shadow_trades"]] == ["S1"] and r["events"][0]["event"] == "PENDING_HUMAN→REJECTED"
    a = r["audit"]
    assert a["vision_own_verdict"] == "agree" and a["verdicts_after_floor"] == ["disagree"] and a["rule_hits"][0]["disagree"] == ["opening"]
    assert a["gap_ctx"] == {"class": "G2"}
    assert S.main(["--day", "2026-10-22", "--timeouts", "--out", out]) == 0
    assert len(json.load(open(out, encoding="utf-8"))["signals"]) == 1
