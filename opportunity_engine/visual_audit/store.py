"""opportunity_engine/visual_audit/store.py — Visual audit चे Supabase tables (spec §17.4) + स्थानिक JSONL cache (backfill/backtest साठी).

🎓 फक्त स्वतःचे tables: `level_audit`, `level_audit_suggestions`, `visual_levels`, `level_feedback`, `visual_audit_runs` (call/token log).
सर्व writes merge-safe: `level_audit` (audit_date, symbol, tf, level_id) वर upsert; suggestions/visual_levels त्या (date, symbol, tf) साठी delete+insert
(पुन्हा चालवलं तरी duplicates नाहीत); feedback फक्त append (शेवटचा निर्णय ग्राह्य). सर्व मूल्यं `float()`/python datetime (bug #16). अपयश शांतपणे False/None.
JSONL cache: प्रत्येक ओळ = एक chart चा audit record (auditor.audit_chart) — resumable backfill आणि offline backtest (DB शिवाय).
"""
import json
import os

import pandas as pd

from .. import store as S

AUDIT, SUGG, VISUAL, FEEDBACK, RUNS = "level_audit", "level_audit_suggestions", "visual_levels", "level_feedback", "visual_audit_runs"
FEEDBACK_VERDICTS = ("CORRECT", "WRONG", "SHIFT")

CREATE_SQL = [
    f"""CREATE TABLE IF NOT EXISTS {AUDIT} (
        audit_date DATE NOT NULL, symbol TEXT NOT NULL, tf TEXT NOT NULL, level_id TEXT NOT NULL, label TEXT, kind TEXT,
        zone_low DOUBLE PRECISION, zone_high DOUBLE PRECISION, engine_grade TEXT, model_verdict TEXT, model_reason TEXT, consensus_class TEXT,
        model_name TEXT, run_id TEXT, created_at TIMESTAMP NOT NULL DEFAULT NOW(), PRIMARY KEY (audit_date, symbol, tf, level_id));""",
    f"""CREATE TABLE IF NOT EXISTS {SUGG} (
        id SERIAL PRIMARY KEY, audit_date DATE NOT NULL, symbol TEXT NOT NULL, tf TEXT NOT NULL, approx_low DOUBLE PRECISION, approx_high DOUBLE PRECISION,
        kind TEXT, reason TEXT, snapped_level_id TEXT, run_id TEXT, created_at TIMESTAMP NOT NULL DEFAULT NOW());""",
    f"""CREATE TABLE IF NOT EXISTS {VISUAL} (
        id SERIAL PRIMARY KEY, audit_date DATE NOT NULL, symbol TEXT NOT NULL, tf TEXT NOT NULL, approx_low DOUBLE PRECISION, approx_high DOUBLE PRECISION,
        kind TEXT, reason TEXT, matched_level_id TEXT, consensus_class TEXT, run_id TEXT, created_at TIMESTAMP NOT NULL DEFAULT NOW());""",
    f"""CREATE TABLE IF NOT EXISTS {FEEDBACK} (
        id SERIAL PRIMARY KEY, level_id TEXT NOT NULL, symbol TEXT NOT NULL, tf TEXT, user_verdict TEXT NOT NULL, note TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW());""",
    f"""CREATE TABLE IF NOT EXISTS {RUNS} (
        run_id TEXT PRIMARY KEY, audit_date DATE NOT NULL, symbol TEXT NOT NULL, tf TEXT NOT NULL, model_name TEXT, overlay_status TEXT, independent_status TEXT,
        error TEXT, engine_state TEXT, model_trend_state TEXT, agrees BOOLEAN, agreement_pct DOUBLE PRECISION, input_tokens INTEGER, output_tokens INTEGER,
        calls INTEGER, created_at TIMESTAMP NOT NULL DEFAULT NOW());""",
]


def _date(x):
    return pd.Timestamp(x).date()


def ensure_tables(conn_factory=None):
    def work(cur):
        for sql in CREATE_SQL:
            cur.execute(sql)
    return S._run(conn_factory, work)


def audit_rows(rec, levels_by_id, classes):
    """record -> level_audit rows (प्रत्येक label)."""
    d = _date(rec["audit_date"])
    verdicts = {v["label"]: v for v in ((rec.get("overlay") or {}).get("data") or {}).get("verdicts", [])}
    rows = []
    for lab in rec.get("labels") or []:
        lv = levels_by_id.get(lab["level_id"], {})
        v = verdicts.get(lab["label"], {})
        rows.append((d, rec["symbol"], rec["tf"], lab["level_id"], lab["label"], lab.get("kind"), S.f(lab.get("outer_low")), S.f(lab.get("outer_high")),
                     lab.get("grade") or lv.get("quality_grade"), v.get("verdict"), v.get("reason"), (classes.get(lab["level_id"]) or {}).get("class"),
                     rec.get("model"), rec.get("run_id")))
    return rows


def save_record(rec, levels_by_id=None, classes=None, visual_rows=None, conn_factory=None):
    """एका chart चा audit (merge-safe). visual_rows = consensus.classify चे त्या TF चे rows."""
    levels_by_id, classes = levels_by_id or {}, classes or {}
    d, sym, tf, rid = _date(rec["audit_date"]), rec["symbol"], rec["tf"], rec.get("run_id")
    a_rows = audit_rows(rec, levels_by_id, classes)
    s_rows = [(d, sym, tf, S.f(m.get("approx_low")), S.f(m.get("approx_high")), m.get("kind"), m.get("reason"), m.get("snapped_level_id"), rid)
              for m in rec.get("suggestions") or []]
    v_rows = [(d, sym, tf, S.f(z.get("approx_low")), S.f(z.get("approx_high")), z.get("kind"), z.get("reason"), z.get("matched_level_id"), z.get("consensus_class"), rid)
              for z in visual_rows or [] if z.get("tf", tf) == tf]
    ov, ind, u = rec.get("overlay") or {}, rec.get("independent") or {}, rec.get("usage") or {}
    od = ov.get("data") or {}
    run_row = (rid, d, sym, tf, rec.get("model"), ov.get("status"), ind.get("status"), (ov.get("error") or ind.get("error") or None), rec.get("engine_state"),
               od.get("trend_state"), od.get("agrees_with_engine_state"), S.f(rec.get("agreement_pct")), S.i(u.get("input_tokens")), S.i(u.get("output_tokens")),
               S.i(u.get("calls")))

    def work(cur):
        for row in a_rows:
            cur.execute(f"""INSERT INTO {AUDIT} (audit_date, symbol, tf, level_id, label, kind, zone_low, zone_high, engine_grade, model_verdict, model_reason,
                            consensus_class, model_name, run_id) VALUES ({', '.join(['%s'] * 14)})
                            ON CONFLICT (audit_date, symbol, tf, level_id) DO UPDATE SET label = EXCLUDED.label, kind = EXCLUDED.kind, zone_low = EXCLUDED.zone_low,
                            zone_high = EXCLUDED.zone_high, engine_grade = EXCLUDED.engine_grade, model_verdict = EXCLUDED.model_verdict,
                            model_reason = EXCLUDED.model_reason, consensus_class = EXCLUDED.consensus_class, model_name = EXCLUDED.model_name,
                            run_id = EXCLUDED.run_id, created_at = NOW()""", row)
        cur.execute(f"DELETE FROM {SUGG} WHERE audit_date = %s AND symbol = %s AND tf = %s", (d, sym, tf))
        for row in s_rows:
            cur.execute(f"""INSERT INTO {SUGG} (audit_date, symbol, tf, approx_low, approx_high, kind, reason, snapped_level_id, run_id)
                            VALUES ({', '.join(['%s'] * 9)})""", row)
        cur.execute(f"DELETE FROM {VISUAL} WHERE audit_date = %s AND symbol = %s AND tf = %s", (d, sym, tf))
        for row in v_rows:
            cur.execute(f"""INSERT INTO {VISUAL} (audit_date, symbol, tf, approx_low, approx_high, kind, reason, matched_level_id, consensus_class, run_id)
                            VALUES ({', '.join(['%s'] * 10)})""", row)
        cur.execute(f"""INSERT INTO {RUNS} (run_id, audit_date, symbol, tf, model_name, overlay_status, independent_status, error, engine_state, model_trend_state,
                        agrees, agreement_pct, input_tokens, output_tokens, calls) VALUES ({', '.join(['%s'] * 15)}) ON CONFLICT (run_id) DO NOTHING""", run_row)
    return S._run(conn_factory, work)


def save_feedback(level_id, symbol, tf, verdict, note="", conn_factory=None):
    if verdict not in FEEDBACK_VERDICTS or not level_id:
        return False

    def work(cur):
        cur.execute(f"INSERT INTO {FEEDBACK} (level_id, symbol, tf, user_verdict, note) VALUES (%s, %s, %s, %s, %s)", (level_id, symbol, tf, verdict, note or None))
    return S._run(conn_factory, work)


AUDIT_COLS = ["audit_date", "symbol", "tf", "level_id", "label", "kind", "zone_low", "zone_high", "engine_grade", "model_verdict", "model_reason", "consensus_class",
              "model_name", "run_id"]


def load_audit(symbol, audit_date=None, conn_factory=None):
    if audit_date is None:
        return S._read(conn_factory, f"SELECT {', '.join(AUDIT_COLS)} FROM {AUDIT} WHERE symbol = %s ORDER BY audit_date, tf, label", (symbol,), AUDIT_COLS)
    return S._read(conn_factory, f"SELECT {', '.join(AUDIT_COLS)} FROM {AUDIT} WHERE symbol = %s AND audit_date = %s ORDER BY tf, label",
                   (symbol, _date(audit_date)), AUDIT_COLS)


def load_dates(symbol, conn_factory=None):
    df = S._read(conn_factory, f"SELECT DISTINCT audit_date FROM {AUDIT} WHERE symbol = %s ORDER BY audit_date DESC", (symbol,), ["audit_date"])
    return [] if df is None else list(df["audit_date"])


def load_feedback(symbol, conn_factory=None):
    """{level_id: शेवटचा user_verdict} (+ पूर्ण DataFrame)."""
    cols = ["level_id", "symbol", "tf", "user_verdict", "note", "created_at"]
    df = S._read(conn_factory, f"SELECT {', '.join(cols)} FROM {FEEDBACK} WHERE symbol = %s ORDER BY created_at", (symbol,), cols)
    if df is None or not len(df):
        return {}, df
    return dict(zip(df["level_id"], df["user_verdict"])), df


def load_runs(symbol, limit=200, conn_factory=None):
    cols = ["run_id", "audit_date", "symbol", "tf", "model_name", "overlay_status", "independent_status", "error", "engine_state", "model_trend_state", "agrees",
            "agreement_pct", "input_tokens", "output_tokens", "calls"]
    return S._read(conn_factory, f"SELECT {', '.join(cols)} FROM {RUNS} WHERE symbol = %s ORDER BY audit_date DESC LIMIT %s", (symbol, int(limit)), cols)


# ---------------------------------------------------------------------------------------------------------------------
# स्थानिक JSONL cache
# ---------------------------------------------------------------------------------------------------------------------
def cache_key(rec):
    return f"{rec['audit_date']}|{rec['symbol']}|{rec['tf']}"


def append_jsonl(path, rec):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path):
    """सर्व records (एकाच key चा शेवटचा ग्राह्य). फाइल नाही ⇒ []. तुटलेली ओळ (अर्धवट लिहिलेली) वगळली."""
    if not path or not os.path.exists(path):
        return []
    latest = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            latest[cache_key(rec)] = rec
    return list(latest.values())


def records_by_date(records):
    """{pd.Timestamp(date): [records]}"""
    out = {}
    for r in records:
        out.setdefault(pd.Timestamp(r["audit_date"]).normalize(), []).append(r)
    return out
