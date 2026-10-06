"""
pullback_credit_spread/store.py
-------------------------------
🎓 Settings साठवण: Supabase `strategy_settings` (strategy_name = "pullback_credit_spread", symbol प्रमाणे — सध्याचा pattern) + बदलांचा
इतिहास `pcs_settings_history` (कोणी, केव्हा, key, जुनं → नवं). Supabase मिळालं नाही तर स्थानिक फाईल (data/pcs_settings.json,
data/pcs_settings_history.jsonl — gitignored) — dashboard तरीही चालतो.
प्रत्येक save पूर्ण dict (validate नंतर) **बदलतो** (merge नाही) — म्हणजे Reset खरंच डीफॉल्टवर नेतं.
"""
import datetime as dt
import json
import os
import tempfile
import threading

from . import settings as S

STRATEGY = "pullback_credit_spread"
SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_PATH = os.path.join(_ROOT, "data", "pcs_settings.json")
LOCAL_HISTORY = os.path.join(_ROOT, "data", "pcs_settings_history.jsonl")

CREATE_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS pcs_settings_history (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    key TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_by TEXT,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


_LOCK = threading.Lock()                                          # Streamlit sessions = एकाच process मधले threads
_TABLE_READY = False


def _conn():
    try:
        import cloud_db
        return cloud_db.get_connection()
    except Exception:
        return None


def _resolve(conn_fn):
    return (conn_fn or _conn)()


def _ensure_history_table(cur):
    """DDL फक्त table तयार नसल्याचं माहीत नसेल तेव्हा. flag commit यशस्वी झाल्यावरच (_table_committed) — नाहीतर rollback मध्ये
    CREATE TABLE पण मागे जातो आणि flag खोटा राहतो."""
    if not _TABLE_READY:
        cur.execute(CREATE_HISTORY_SQL)
        return True
    return False


def _table_committed(ran):
    global _TABLE_READY
    if ran:
        _TABLE_READY = True


def _now():
    return (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")


def _load_local():
    try:
        with open(LOCAL_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_local(all_):
    os.makedirs(os.path.dirname(LOCAL_PATH), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(LOCAL_PATH), prefix=".pcs_settings.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(all_, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LOCAL_PATH)


def load(symbol, conn_fn=None):
    """symbol चे settings (validate केलेले, डीफॉल्टसह पूर्ण) + स्रोत ("supabase"/"local"/"default"/"error").
    "error" ⇒ Supabase connection मिळालं पण वाचन फेल: डीफॉल्ट परत, पण पान Save बंद ठेवतं (जुन्या स्थानिक/डीफॉल्ट मूल्यांनी खरी
    Supabase नोंद overwrite होऊ नये)."""
    conn = _resolve(conn_fn)
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT settings FROM strategy_settings WHERE strategy_name=%s AND symbol=%s", (STRATEGY, symbol))
                row = cur.fetchone()
            if row and row[0]:
                raw = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                return S.validate(raw)[0], "supabase"
            return dict(S.DEFAULTS), "default"
        except Exception:
            return dict(S.DEFAULTS), "error"
        finally:
            try:
                conn.close()
            except Exception:
                pass
    raw = _load_local().get(symbol)
    return (S.validate(raw)[0], "local") if raw else (dict(S.DEFAULTS), "default")


def save(symbol, new_settings, changed_by="dashboard", conn_fn=None):
    """validate → पूर्ण dict बदल + इतिहास. रिटर्न (clean, errors, changes, स्रोत). स्रोत "error" ⇒ Supabase मिळालं पण save अयशस्वी —
    स्थानिक फाईलमध्ये **गुपचूप** साठवत नाही (नाहीतर load जुनी Supabase नोंद वाचेल). स्थानिक fallback फक्त Supabase connection नसेल तेव्हा."""
    old, old_src = load(symbol, conn_fn)
    clean, errors = S.validate(new_settings)
    if old_src == "error":
        return clean, errors + ["Supabase वाचता आलं नाही — save केलं नाही (पुन्हा प्रयत्न करा)"], [], "error"
    changes = S.diff(old, clean)
    conn = _resolve(conn_fn)
    if conn is not None:
        try:
            with conn.cursor() as cur:
                ran = _ensure_history_table(cur)
                cur.execute("""INSERT INTO strategy_settings (strategy_name, symbol, settings, updated_at) VALUES (%s, %s, %s, NOW())
                               ON CONFLICT (strategy_name, symbol) DO UPDATE SET settings = EXCLUDED.settings, updated_at = NOW()""",
                            (STRATEGY, symbol, json.dumps(clean, ensure_ascii=False)))
                for k, o, n in changes:
                    cur.execute("INSERT INTO pcs_settings_history (symbol, key, old_value, new_value, changed_by) VALUES (%s, %s, %s, %s, %s)",
                                (symbol, k, json.dumps(o, ensure_ascii=False), json.dumps(n, ensure_ascii=False), changed_by))
            conn.commit()
            _table_committed(ran)
            return clean, errors, changes, "supabase"
        except Exception as e:                                       # noqa: BLE001
            try:
                conn.rollback()
            except Exception:
                pass
            return clean, errors + [f"Supabase save अयशस्वी: {type(e).__name__}"], [], "error"
        finally:
            try:
                conn.close()
            except Exception:
                pass
    with _LOCK:
        all_ = _load_local()
        all_[symbol] = clean
        _save_local(all_)
    if changes:
        os.makedirs(os.path.dirname(LOCAL_HISTORY), exist_ok=True)
        with open(LOCAL_HISTORY, "a", encoding="utf-8") as f:
            for k, o, n in changes:
                f.write(json.dumps({"symbol": symbol, "key": k, "old": o, "new": n, "by": changed_by, "at": _now()}, ensure_ascii=False) + "\n")
    return clean, errors, changes, "local"


def reset(symbol, changed_by="dashboard", conn_fn=None):
    return save(symbol, dict(S.DEFAULTS), changed_by, conn_fn)


def history(symbol=None, limit=30, conn_fn=None):
    """शेवटचे बदल: [{symbol, key, old, new, by, at}] (नवे आधी)."""
    conn = _resolve(conn_fn)
    if conn is not None:
        try:
            with conn.cursor() as cur:
                ran = _ensure_history_table(cur)
                q = "SELECT symbol, key, old_value, new_value, changed_by, changed_at FROM pcs_settings_history"
                args = ()
                if symbol:
                    q += " WHERE symbol=%s"
                    args = (symbol,)
                cur.execute(q + " ORDER BY id DESC LIMIT %s", args + (limit,))
                rows = cur.fetchall()
            conn.commit()
            _table_committed(ran)
            return [{"symbol": r[0], "key": r[1], "old": r[2], "new": r[3], "by": r[4], "at": str(r[5])} for r in rows]
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
    try:
        with open(LOCAL_HISTORY, encoding="utf-8") as f:
            rows = [json.loads(x) for x in f if x.strip()]
    except (OSError, ValueError):
        rows = []
    rows = [r for r in rows if not symbol or r.get("symbol") == symbol]
    return list(reversed(rows))[:limit]
