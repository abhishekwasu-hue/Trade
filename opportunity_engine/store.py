"""opportunity_engine/store.py — Structure Journal चा Supabase स्तर (spec §2.5). **फक्त स्वतःचे तीन tables**; `market_zones` ला कधीच हात नाही.

🎓 मंजूर केलेली रचना (plan v2): `market_structure_state` (प्रति symbol+tf एक row, upsert) · `market_structure_events` (फक्त append; `event_key` ने dedupe) ·
`opportunity_zones` (वेगळा table — `save_market_zones()` चं symbol-व्यापी DELETE live bots च्या zones पुसतं म्हणून `market_zones` वापरलेला नाही).
सर्व मूल्यं DB ला जाण्याआधी `float()/int()`/python datetime (numpy/pandas प्रकार नाहीत). Connection `cloud_db.get_connection` (lazy import) किंवा चाचणीसाठी injected `conn_factory`.
अपयश शांतपणे False/None (कधीच raise नाही) — refresh script ने कारण दाखवावं.
"""
import hashlib
import json
import logging
import math

import pandas as pd

_logger = logging.getLogger(__name__)

STATE_TABLE, EVENTS_TABLE, ZONES_TABLE = "market_structure_state", "market_structure_events", "opportunity_zones"

CREATE_STATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    trend_state TEXT NOT NULL,
    protected_level DOUBLE PRECISION,
    last_sh DOUBLE PRECISION,
    last_sl DOUBLE PRECISION,
    range_high DOUBLE PRECISION,
    range_low DOUBLE PRECISION,
    ref_range DOUBLE PRECISION,
    updated_at TIMESTAMP,
    PRIMARY KEY (symbol, tf)
);
"""
CREATE_EVENTS_SQL = f"""
CREATE TABLE IF NOT EXISTS {EVENTS_TABLE} (
    id SERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    event_time TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    price DOUBLE PRECISION,
    details_json TEXT,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""
CREATE_ZONES_SQL = f"""
CREATE TABLE IF NOT EXISTS {ZONES_TABLE} (
    symbol TEXT NOT NULL,
    level_id TEXT NOT NULL,
    tf TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT,
    zone_low DOUBLE PRECISION NOT NULL,
    zone_high DOUBLE PRECISION NOT NULL,
    core_low DOUBLE PRECISION,
    core_high DOUBLE PRECISION,
    freshness TEXT,
    status TEXT,
    role TEXT,
    quality_grade TEXT,
    quality_score DOUBLE PRECISION,
    origin_type TEXT,
    mtf_count INTEGER,
    touches INTEGER,
    gap_status TEXT,
    reject_reason TEXT,
    formed_at TIMESTAMP,
    computed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, level_id)
);
"""
STATE_COLS = ["symbol", "tf", "trend_state", "protected_level", "last_sh", "last_sl", "range_high", "range_low", "ref_range", "updated_at"]
ZONE_COLS = ["symbol", "level_id", "tf", "kind", "source", "zone_low", "zone_high", "core_low", "core_high", "freshness", "status", "role", "quality_grade",
             "quality_score", "origin_type", "mtf_count", "touches", "gap_status", "reject_reason", "formed_at"]
EVENT_TYPES_STORED = ("INIT_TREND", "INIT_RANGE", "CHOCH", "BOS", "SWEEP", "RECOVERY", "REVERSAL_CONFIRMED", "RANGE_START", "RANGE_EXIT_UP", "RANGE_EXIT_DOWN",
                       "ZONE_FORMED", "ZONE_MITIGATED", "ZONE_BROKEN", "GAP_FILLED")


# ---------------------------------------------------------------------------------------------------------------------
# मूल्य-रूपांतरण (numpy/pandas -> python)
# ---------------------------------------------------------------------------------------------------------------------
def f(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def i(x):
    v = f(x)
    return None if v is None else int(v)


def ts(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata").tz_localize(None)
    return t.to_pydatetime()


def _json_default(o):
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    try:
        return float(o)
    except (TypeError, ValueError):
        return str(o)


def event_key(symbol, tf, time, etype, price, extra=""):
    raw = f"{symbol}|{tf}|{ts(time)}|{etype}|{'' if f(price) is None else round(f(price), 2)}|{extra}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _connect(conn_factory=None):
    if conn_factory is not None:
        return conn_factory()
    import cloud_db                                   # lazy: package import वर DB नाही
    return cloud_db.get_connection()


def _run(conn_factory, work):
    """conn उघडून `work(cursor)` चालवणं; commit/rollback/close. अपयशात (False/None, कारण) — कधीच raise नाही."""
    conn = _connect(conn_factory)
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            result = work(cur)
        conn.commit()
        return True if result is None else result
    except Exception:
        _logger.exception("opportunity_engine.store मध्ये अनपेक्षित चूक (silently handled)")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------------------------------
def ensure_tables(conn_factory=None):
    def work(cur):
        for sql in (CREATE_STATE_SQL, CREATE_EVENTS_SQL, CREATE_ZONES_SQL):
            cur.execute(sql)
    return _run(conn_factory, work)


def save_structure_state(symbol, snapshots, conn_factory=None):
    """snapshots = Journal.snapshot(tf) dicts (tf, trend_state, protected_level, last_sh, last_sl, range_high, range_low, ref_range, updated_at). upsert."""
    rows = [(symbol, s["tf"], s["trend_state"], f(s.get("protected_level")), f(s.get("last_sh")), f(s.get("last_sl")), f(s.get("range_high")),
             f(s.get("range_low")), f(s.get("ref_range")), ts(s.get("updated_at"))) for s in snapshots]
    if not rows:
        return False

    def work(cur):
        for row in rows:
            cur.execute(
                f"""INSERT INTO {STATE_TABLE} ({', '.join(STATE_COLS)}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, tf) DO UPDATE SET trend_state = EXCLUDED.trend_state, protected_level = EXCLUDED.protected_level,
                    last_sh = EXCLUDED.last_sh, last_sl = EXCLUDED.last_sl, range_high = EXCLUDED.range_high, range_low = EXCLUDED.range_low,
                    ref_range = EXCLUDED.ref_range, updated_at = EXCLUDED.updated_at""", row)
    return _run(conn_factory, work)


def event_rows(symbol, events):
    """tracker/zone events -> (event_key, symbol, tf, time, type, price, details_json) — फक्त EVENT_TYPES_STORED."""
    rows = []
    for e in events:
        if e.get("type") not in EVENT_TYPES_STORED:
            continue
        details = {k: v for k, v in e.items() if k not in ("tf", "time", "type", "price", "bar_idx", "state")}
        extra = str(e.get("level_id", e.get("swing_idx", "")))
        rows.append((event_key(symbol, e["tf"], e["time"], e["type"], e.get("price"), extra), symbol, e["tf"], ts(e["time"]), e["type"], f(e.get("price")),
                     json.dumps(details, default=_json_default, ensure_ascii=False)))
    return rows


def append_events(symbol, events, conn_factory=None):
    """फक्त append; `event_key` UNIQUE + ON CONFLICT DO NOTHING (वारंवार refresh केल्यास duplicates नाहीत)."""
    rows = event_rows(symbol, events)
    if not rows:
        return 0

    def work(cur):
        n = 0
        for row in rows:
            cur.execute(
                f"""INSERT INTO {EVENTS_TABLE} (event_key, symbol, tf, event_time, event_type, price, details_json) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_key) DO NOTHING""", row)
            n += max(int(cur.rowcount or 0), 0)
        return n
    result = _run(conn_factory, work)
    return 0 if result is False else int(result)


def zone_rows(symbol, levels):
    rows = []
    for z in levels:
        if not z.get("level_id"):
            continue
        rows.append((symbol, z["level_id"], z["tf"], z["kind"], z.get("source"), f(z["low"]), f(z["high"]), f(z.get("core_low")), f(z.get("core_high")),
                     z.get("freshness"), z.get("status"), z.get("role"), z.get("quality_grade"), f(z.get("quality_score")), z.get("origin_type"),
                     i(z.get("mtf_count")), i(z.get("touches")), z.get("gap_status"), z.get("reject_reason"), ts(z.get("formed_at"))))
    return rows


def save_zones(symbol, levels, conn_factory=None):
    """symbol चे zones upsert (level_id नुसार) आणि **आपल्याच table मधले** गेलेले (आता नसलेले) level_id काढणे. `levels` रिकामी असेल तर काहीच बदल नाही (अर्धवट/चुकीच्या
    गणनेतून जुना योग्य निकाल पुसू नये)."""
    rows = zone_rows(symbol, levels)
    if not rows:
        return False

    def work(cur):
        for row in rows:
            cur.execute(
                f"""INSERT INTO {ZONES_TABLE} ({', '.join(ZONE_COLS)}) VALUES ({', '.join(['%s'] * len(ZONE_COLS))})
                    ON CONFLICT (symbol, level_id) DO UPDATE SET tf = EXCLUDED.tf, kind = EXCLUDED.kind, source = EXCLUDED.source, zone_low = EXCLUDED.zone_low,
                    zone_high = EXCLUDED.zone_high, reject_reason = EXCLUDED.reject_reason, core_low = EXCLUDED.core_low, core_high = EXCLUDED.core_high, freshness = EXCLUDED.freshness,
                    status = EXCLUDED.status, role = EXCLUDED.role, quality_grade = EXCLUDED.quality_grade, quality_score = EXCLUDED.quality_score,
                    origin_type = EXCLUDED.origin_type, mtf_count = EXCLUDED.mtf_count, touches = EXCLUDED.touches, gap_status = EXCLUDED.gap_status,
                    formed_at = EXCLUDED.formed_at, computed_at = NOW()""", row)
        cur.execute(f"DELETE FROM {ZONES_TABLE} WHERE symbol = %s AND level_id <> ALL(%s)", (symbol, [r[1] for r in rows]))
    return _run(conn_factory, work)


def _read(conn_factory, sql, params, cols):
    conn = _connect(conn_factory)
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception:
        _logger.exception("opportunity_engine.store वाचताना चूक (silently handled)")
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def load_state(symbol, conn_factory=None):
    return _read(conn_factory, f"SELECT {', '.join(STATE_COLS)} FROM {STATE_TABLE} WHERE symbol = %s ORDER BY tf", (symbol,), STATE_COLS)


def load_zones(symbol, conn_factory=None):
    return _read(conn_factory, f"SELECT {', '.join(ZONE_COLS)} FROM {ZONES_TABLE} WHERE symbol = %s ORDER BY quality_score DESC", (symbol,), ZONE_COLS)


def load_events(symbol, limit=200, conn_factory=None):
    cols = ["symbol", "tf", "event_time", "event_type", "price", "details_json"]
    return _read(conn_factory, f"SELECT {', '.join(cols)} FROM {EVENTS_TABLE} WHERE symbol = %s ORDER BY event_time DESC LIMIT %s", (symbol, int(limit)), cols)


def zone_transition_events(symbol, old_df, new_levels, now):
    """मागच्या साठवलेल्या zones (old_df) आणि नवीन levels तुलना करून ZONE_FORMED/ZONE_MITIGATED/ZONE_BROKEN/GAP_FILLED events (event time = `now`)."""
    if old_df is None or len(old_df) == 0:
        return []                                      # आधारभूत (baseline) नाही => events नाहीत (पहिल्या run ला शेकडो ZONE_FORMED टाळण्यासाठी)
    old = {r["level_id"]: r for _, r in old_df.iterrows()}
    events = []
    for z in new_levels:
        lid, prev = z.get("level_id"), old.get(z.get("level_id"))
        base = {"tf": z["tf"], "time": now, "price": (z["core_low"] + z["core_high"]) / 2.0, "level_id": lid, "kind": z["kind"], "grade": z.get("quality_grade")}
        if z["kind"] == "GAP" and z.get("gap_status") == "FILLED" and (prev is None or prev.get("gap_status") != "FILLED"):
            events.append({**base, "type": "GAP_FILLED"})
        if prev is None:
            if z["kind"] != "GAP" or z.get("gap_status") != "FILLED":
                events.append({**base, "type": "ZONE_FORMED"})
        elif prev.get("status") != z.get("status"):
            if z.get("status") == "MITIGATED":
                events.append({**base, "type": "ZONE_MITIGATED"})
            elif z.get("status") == "BROKEN":
                events.append({**base, "type": "ZONE_BROKEN"})
    return events
