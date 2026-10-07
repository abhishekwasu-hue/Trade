"""vision/store.py — Vision ची स्थानिक SQLite (VPS वर `data/vision.db`, gitignored). Bots (cron), worker आणि dashboard एकाच machine वर.

Tables:
  vision_signals         प्रत्येक signal ची एक row (bot, symbol, signal_ts, algo निर्णय, vision JSON/verdict, latency, cost, notify, …).
                         V1 साठी human_decision / drift_result / status कॉलम आधीच — decision update नेहमी conditional (`WHERE status=…`).
  vision_usage           प्रत्येक API call चा खर्च (tokens, cache, $) — दैनिक / मासिक budget इथूनच.
  vision_settings        bot-निहाय settings (JSON) + `_global` (budget).
  vision_settings_history बदल-इतिहास (कोणी, कधी, काय).
  vision_kv              छोटे flags (उदा. आजचा budget इशारा पाठवला का).
Audit record (§11): `_sent.png` path + sha256 (vision ला गेलेले bytes), prompt_version, model, vision JSON (tokens सह), cost, algo निर्णय,
(V1) माझा निर्णय + वेळ, drift guard, अंतिम निर्णय; trade बंद झाल्यावर `_outcome.png` path + sha256 आणि निकाल.
"""
import contextlib
import datetime
import json
import os
import sqlite3
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS vision_signals (
    signal_id TEXT PRIMARY KEY,
    bot TEXT NOT NULL, symbol TEXT NOT NULL, trading_mode TEXT NOT NULL, mode TEXT NOT NULL,
    signal_ts TEXT NOT NULL, created_at TEXT NOT NULL,
    direction TEXT, level REAL, role TEXT, setup_tf TEXT, spot REAL,
    setup_json TEXT, algo_decision TEXT,
    status TEXT NOT NULL,                 -- QUEUED | RUNNING | DONE | EXPIRED | FAILED
    verdict TEXT,                         -- agree | gray | disagree | unavailable
    vision_json TEXT, audits INTEGER DEFAULT 0, confidence REAL,
    latency_ms INTEGER, cost_usd REAL DEFAULT 0, model TEXT, reused_from TEXT,
    image_path TEXT, notified INTEGER DEFAULT 0, error TEXT, finished_at TEXT,
    human_decision TEXT, human_ts TEXT, drift_result TEXT,
    image_sha256 TEXT, prompt_version TEXT, final_decision TEXT,
    trade_id TEXT, outcome_path TEXT, outcome_sha256 TEXT, outcome_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_vs_status ON vision_signals(status, created_at);
CREATE INDEX IF NOT EXISTS ix_vs_reuse ON vision_signals(symbol, direction, setup_tf, signal_ts);
CREATE TABLE IF NOT EXISTS vision_usage (
    ts TEXT NOT NULL, day TEXT NOT NULL, month TEXT NOT NULL, task TEXT, model TEXT, signal_id TEXT,
    input_tokens INTEGER, output_tokens INTEGER, cache_read INTEGER, cache_write INTEGER, cost_usd REAL
);
CREATE TABLE IF NOT EXISTS vision_settings (bot TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at TEXT, updated_by TEXT);
CREATE TABLE IF NOT EXISTS vision_settings_history (ts TEXT, bot TEXT, by TEXT, old_json TEXT, new_json TEXT);
CREATE TABLE IF NOT EXISTS vision_kv (k TEXT PRIMARY KEY, v TEXT);
"""


def db_path():
    if os.environ.get("VISION_DB_PATH"):
        return os.environ["VISION_DB_PATH"]
    from config import DATA_DIR
    return os.path.join(DATA_DIR, "vision.db")


@contextlib.contextmanager
def connect(path=None, timeout=10):
    p = path or db_path()
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    conn = sqlite3.connect(p, timeout=timeout)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _iso(ts):
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    return ts.replace(microsecond=0).isoformat() if hasattr(ts, "replace") else str(ts)


def now_ist():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)


# --------------------------------------------------------------------------------------------------------- signals
def insert_signal(row, path=None, timeout=10):
    """row: bot, symbol, trading_mode, mode, signal_ts, direction, level, role, setup_tf, spot, setup (dict), algo_decision. रिटर्न signal_id."""
    sid = row.get("signal_id") or uuid.uuid4().hex[:16]
    with connect(path, timeout) as c:
        c.execute(
            "INSERT INTO vision_signals (signal_id, bot, symbol, trading_mode, mode, signal_ts, created_at, direction, level, role, setup_tf, spot, "
            "setup_json, algo_decision, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'QUEUED')",
            (sid, row["bot"], row["symbol"], row["trading_mode"], row["mode"], _iso(row["signal_ts"]), _iso(now_ist()), row.get("direction"),
             row.get("level"), row.get("role"), row.get("setup_tf"), row.get("spot"),
             json.dumps(row.get("setup") or {}, ensure_ascii=False, default=str), row.get("algo_decision")))
    return sid


def claim_queued(limit=5, path=None):
    """QUEUED → RUNNING (conditional — दोन workers एकच row घेऊ शकत नाहीत). रिटर्न dict rows."""
    out = []
    with connect(path) as c:
        ids = [r["signal_id"] for r in c.execute("SELECT signal_id FROM vision_signals WHERE status='QUEUED' ORDER BY created_at LIMIT ?", (limit,))]
        for sid in ids:
            cur = c.execute("UPDATE vision_signals SET status='RUNNING' WHERE signal_id=? AND status='QUEUED'", (sid,))
            if cur.rowcount == 1:
                out.append(dict(c.execute("SELECT * FROM vision_signals WHERE signal_id=?", (sid,)).fetchone()))
    return out


def claim_one(signal_id, path=None):
    """फक्त हीच row QUEUED → RUNNING (smoke script — इतर bots च्या rows ला हात नाही). रिटर्न dict | None."""
    with connect(path) as c:
        cur = c.execute("UPDATE vision_signals SET status='RUNNING' WHERE signal_id=? AND status='QUEUED'", (signal_id,))
        if cur.rowcount != 1:
            return None
        return dict(c.execute("SELECT * FROM vision_signals WHERE signal_id=?", (signal_id,)).fetchone())


def finish(signal_id, status, path=None, **fields):
    cols = dict(fields)
    cols["status"] = status
    cols["finished_at"] = _iso(now_ist())
    if "vision_json" in cols and not isinstance(cols["vision_json"], (str, type(None))):
        cols["vision_json"] = json.dumps(cols["vision_json"], ensure_ascii=False)
    sets = ", ".join(f"{k}=?" for k in cols)
    with connect(path) as c:
        c.execute(f"UPDATE vision_signals SET {sets} WHERE signal_id=?", (*cols.values(), signal_id))


def set_outcome(signal_id, path=None, **fields):
    if "outcome_json" in fields and not isinstance(fields["outcome_json"], (str, type(None))):
        fields["outcome_json"] = json.dumps(fields["outcome_json"], ensure_ascii=False, default=str)
    sets = ", ".join(f"{k}=?" for k in fields)
    with connect(path) as c:
        c.execute(f"UPDATE vision_signals SET {sets} WHERE signal_id=?", (*fields.values(), signal_id))


def pending_outcomes(since_day, path=None):
    """DONE signals (since_day पासून) ज्यांचा outcome अजून नाही."""
    with connect(path) as c:
        rows = c.execute("SELECT * FROM vision_signals WHERE status='DONE' AND outcome_json IS NULL AND substr(signal_ts,1,10) >= ? "
                         "ORDER BY signal_ts", (str(since_day),)).fetchall()
    return [dict(r) for r in rows]


def set_notified(signal_id, ok, path=None):
    with connect(path) as c:
        c.execute("UPDATE vision_signals SET notified=? WHERE signal_id=?", (1 if ok else 0, signal_id))


def expire_stale(max_age_min, path=None):
    """RUNNING / QUEUED rows जुन्या (worker crash / restart) ⇒ EXPIRED. V1 मध्ये PENDING सुद्धा (stale approve नाही)."""
    cutoff = _iso(now_ist() - datetime.timedelta(minutes=max_age_min))
    with connect(path) as c:
        cur = c.execute("UPDATE vision_signals SET status='EXPIRED', error=COALESCE(error, 'stale (worker उशीर / restart)'), finished_at=? "
                        "WHERE status IN ('QUEUED','RUNNING') AND created_at < ?", (_iso(now_ist()), cutoff))
        return cur.rowcount


def get_signal(signal_id, path=None):
    with connect(path) as c:
        r = c.execute("SELECT * FROM vision_signals WHERE signal_id=?", (signal_id,)).fetchone()
        return dict(r) if r else None


REUSE_TAGS = ("breakout_entry", "directional")


def _reuse_tags(setup_json):
    try:
        t = (json.loads(setup_json or "{}").get("tags") or {})
    except ValueError:
        t = {}
    return tuple(bool(t.get(k)) for k in REUSE_TAGS)


def find_reusable(row, window_min, tol_pct=0.05, path=None):
    """तोच bot / symbol / दिशा / role / TF / setup प्रकार (breakout / directional tags), level ±tol_pct %, आधीच्या `window_min` मिनिटांत DONE
    (unavailable नाही, स्वतः reuse नाही) ⇒ ती row. Role किंवा breakout प्रकार वेगळा ⇒ नवा audit (verdict नियम वेगळे लागतात)."""
    level = row.get("level")
    t1 = _iso(row["signal_ts"])
    t0 = _iso(datetime.datetime.fromisoformat(t1) - datetime.timedelta(minutes=window_min))
    with connect(path) as c:
        rows = c.execute("SELECT * FROM vision_signals WHERE bot=? AND symbol=? AND direction IS ? AND role IS ? AND setup_tf IS ? "
                         "AND status='DONE' AND verdict IS NOT NULL AND verdict != 'unavailable' AND reused_from IS NULL "
                         "AND signal_ts >= ? AND signal_ts <= ? AND signal_id != ? ORDER BY signal_ts DESC",
                         (row["bot"], row["symbol"], row.get("direction"), row.get("role"), row.get("setup_tf"), t0, t1,
                          row.get("signal_id") or "")).fetchall()
    want = _reuse_tags(row.get("setup_json"))
    for r in rows:
        if _reuse_tags(r["setup_json"]) != want:
            continue
        if r["level"] is not None and level is not None and abs(float(r["level"]) - float(level)) <= abs(float(level)) * tol_pct / 100.0:
            return dict(r)
    return None


def list_signals(day=None, path=None):
    with connect(path) as c:
        if day:
            rows = c.execute("SELECT * FROM vision_signals WHERE substr(signal_ts,1,10)=? ORDER BY signal_ts", (str(day),)).fetchall()
        else:
            rows = c.execute("SELECT * FROM vision_signals ORDER BY signal_ts").fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------------------------------------- usage / budget
def add_usage(task, model, usage, cost_usd, signal_id=None, path=None, ts=None):
    t = ts or now_ist()
    with connect(path) as c:
        c.execute("INSERT INTO vision_usage VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (_iso(t), t.strftime("%Y-%m-%d"), t.strftime("%Y-%m"), task, model, signal_id, int(usage.get("input_tokens", 0)),
                   int(usage.get("output_tokens", 0)), int(usage.get("cache_read", 0)), int(usage.get("cache_write", 0)), float(cost_usd)))


def spent(path=None, ts=None):
    """(आजचा $, या महिन्याचा $) — IST."""
    t = ts or now_ist()
    with connect(path) as c:
        d = c.execute("SELECT COALESCE(SUM(cost_usd),0) FROM vision_usage WHERE day=?", (t.strftime("%Y-%m-%d"),)).fetchone()[0]
        m = c.execute("SELECT COALESCE(SUM(cost_usd),0) FROM vision_usage WHERE month=?", (t.strftime("%Y-%m"),)).fetchone()[0]
    return float(d), float(m)


def usage_summary(day, path=None):
    with connect(path) as c:
        r = c.execute("SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(cache_read),0), "
                      "COALESCE(SUM(cache_write),0), COALESCE(SUM(cost_usd),0) FROM vision_usage WHERE day=?", (str(day),)).fetchone()
    return {"calls": r[0], "input_tokens": r[1], "output_tokens": r[2], "cache_read": r[3], "cache_write": r[4], "cost_usd": round(float(r[5]), 4)}


# --------------------------------------------------------------------------------------------------------- kv
def kv_get(k, path=None):
    with connect(path) as c:
        r = c.execute("SELECT v FROM vision_kv WHERE k=?", (k,)).fetchone()
    return r[0] if r else None


def kv_set(k, v, path=None):
    with connect(path) as c:
        c.execute("INSERT INTO vision_kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
