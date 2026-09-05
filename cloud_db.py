"""
cloud_db.py
---------------
OI Diff Snapshot डेटासाठी Cloud Database (Supabase/PostgreSQL) — वापरकर्त्याशी चर्चा करून
ठरवलेली सुधारणा. Local machine वरच्या unattended scripts (oi_snapshot_collector.py) आणि Streamlit
Cloud वरचं Dashboard — दोन्ही याच एका, सामायिक (shared) database शी बोलतात, त्यामुळे local script ने
साठवलेला डेटा लगेच Cloud Dashboard वरही दिसतो (आधीच्या स्वतंत्र, न-जोडलेल्या SQLite फाईल्सच्या
समस्येवर हाच खरा उपाय).

⚙️ Setup (एकदाच, वापरकर्त्याने स्वतः करायचं):
  १. https://supabase.com वर मोफत खातं तयार करा, नवीन Project बनवा.
  २. Project Settings -> Database -> Connection String (URI) कॉपी करा
     (उदा. postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres)
  ३. ही स्ट्रिंग पर्यावरण चल (environment variable) 'SUPABASE_DB_URL' मध्ये ठेवा, किंवा
     data/notification_config.json मध्ये {"supabase_db_url": "..."} असं जोडा.
  ४. Streamlit Cloud वर: App Settings -> Secrets मध्ये SUPABASE_DB_URL जोडा.

Connection string सेट केलेली नसेल तर — सर्व function शांतपणे (None, "...उपलब्ध नाही") परत देतात,
कुठेही crash होत नाही (त्या स्थितीत Dashboard जुन्याच local SQLite कडे आपोआप वळतो).

⚠️ प्रामाणिक इशारा: हा कोड psycopg2 + मानक PostgreSQL syntax वापरून लिहिला आहे, पण या विकास
वातावरणात खऱ्या Supabase/PostgreSQL सर्व्हरशी जोडून चाचणी करता आलेली नाही (network प्रतिबंधामुळे) —
फक्त तर्कशास्त्र (mocked connection सह) पडताळलं आहे. कृपया तुमच्या स्वतःच्या Supabase वर एकदा
प्रत्यक्ष चाचणी करा.
"""
import json
import os

import pandas as pd

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, "data", "notification_config.json")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS oi_diff_snapshots (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    total_call_oi BIGINT,
    total_put_oi BIGINT,
    diff BIGINT,
    delta_diff BIGINT,
    signal TEXT,
    underlying_price REAL,
    total_call_premium REAL,
    total_put_premium REAL,
    PRIMARY KEY (symbol, trade_date, snapshot_time)
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Upstox Access Token Request + Notifier Webhook
# पद्धतीने रोज एका टॅपवर मिळणारा नवीन token, इथे साठवला जातो — GitHub Actions आणि Streamlit Dashboard
# दोन्ही इथूनच वाचतील, त्यामुळे कुठेही मॅन्युअल paste लागणार नाही.
CREATE_TOKEN_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS upstox_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT NOT NULL,
    received_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — S/R, Order Block, Demand/Supply Zone, Unfilled Gap
# या सर्व विश्लेषणाचा निकाल इथेच साठवला जातो — प्रत्येक वेळी पुन्हा गणना न करता, Dashboard/रणनीती
# थेट इथूनच वाचू शकतील (भविष्यातलं trade-planning जलद व्हावं म्हणून).
CREATE_ZONES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS market_zones (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    zone_type TEXT NOT NULL,
    zone_low REAL NOT NULL,
    zone_high REAL NOT NULL,
    strength REAL,
    formed_date TIMESTAMP,
    status TEXT NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या "Multi Strike OI" सारखं, प्रत्येक strike
# चा OI इतिहास (वेळेनुसार) साठवण्यासाठी — आधी फक्त एकूण (Total) Call/Put OI साठवला जायचा.
# oi_snapshot_collector.py आधीच प्रत्येक strike चा डेटा वाचतो (aggregate करण्यासाठी) — तोच पुनर्वापर.
CREATE_STRIKE_OI_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strike_oi_history (
    symbol TEXT NOT NULL,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    oi BIGINT,
    PRIMARY KEY (symbol, strike, option_type, trade_date, snapshot_time)
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — गेल्या ५+ वर्षांचा (प्रत्यक्षात संपूर्ण उपलब्ध इतिहास,
# 2015 पासून) NIFTY 1-मिनिट OHLC डेटा, रोज आपोआप अद्ययावत होणारा — जेणेकरून Backtest/Demand-Supply/
# S-R गणना प्रत्येक वेळी थेट Upstox वरून (मर्यादित lookback सह) डेटा न मागवता, इथूनच वाचू शकतील.
CREATE_NIFTY_1MIN_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nifty_1min_ohlc (
    timestamp TIMESTAMP PRIMARY KEY,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume BIGINT DEFAULT 0
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — High-Frequency 1-मिनिट S/R रणनीतीचा प्रत्येक शोधलेला
# सिग्नल (trade झाला किंवा न झाला तरीही) — Dashboard वर संपूर्ण intraday Signal Log दाखवण्यासाठी.
CREATE_SIGNAL_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS signal_log (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    signal_time TIMESTAMP NOT NULL,
    level_type TEXT NOT NULL,
    level_price REAL NOT NULL,
    hit_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    ltp_at_signal REAL,
    trade_status TEXT,
    reason TEXT
);
"""


def get_supabase_url():
    """पर्यावरण चल आधी तपासणे, नंतर config फाईल — दोन्हीपैकी काहीच नसेल तर None."""
    url = os.environ.get("SUPABASE_DB_URL")
    if url:
        return url
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            return cfg.get("supabase_db_url")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def is_cloud_db_configured():
    return psycopg2 is not None and get_supabase_url() is not None


def get_connection():
    """Cloud DB शी जोडणी करणे. Configured नसेल किंवा जोडणी अयशस्वी झाली तर None (कधीही raise होत नाही)."""
    if psycopg2 is None:
        return None
    url = get_supabase_url()
    if not url:
        return None
    try:
        return psycopg2.connect(url, connect_timeout=10)
    except Exception:
        return None


def get_connection_with_error():
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — फक्त निदान/टेस्टिंगसाठी (test_supabase_connection.py).
    get_connection() प्रमाणेच, पण अयशस्वी झाल्यास खरा, तपशीलवार error संदेश सुद्धा परत देतं — जेणेकरून
    "जोडणी झाली नाही" इतकंच नाही, तर *नेमकं का* (उदा. password चुकीचा, project paused, DNS सापडला
    नाही) हे स्पष्टपणे कळेल. get_connection() चं मूळ वर्तन (production साठी शांतपणे None) अबाधित आहे.
    रिटर्न: (connection_किंवा_None, error_message_किंवा_None)
    """
    if psycopg2 is None:
        return None, "psycopg2 library स्थापित नाही (pip install psycopg2-binary)"
    url = get_supabase_url()
    if not url:
        return None, "SUPABASE_DB_URL सापडली नाही (environment variable रिकामी आहे)"
    try:
        return psycopg2.connect(url, connect_timeout=10), None
    except Exception as exc:
        return None, str(exc)


def init_cloud_table():
    """oi_diff_snapshots, upstox_tokens, market_zones, strike_oi_history, nifty_1min_ohlc आणि
    signal_log tables (नसतील तर) तयार करणे."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.execute(CREATE_TOKEN_TABLE_SQL)
            cur.execute(CREATE_ZONES_TABLE_SQL)
            cur.execute(CREATE_STRIKE_OI_TABLE_SQL)
            cur.execute(CREATE_NIFTY_1MIN_TABLE_SQL)
            cur.execute(CREATE_SIGNAL_LOG_TABLE_SQL)
        conn.commit()
        return True
    finally:
        conn.close()


def save_signal_log(entry):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — High-Frequency 1-मिनिट S/R रणनीतीचा प्रत्येक शोधलेला
    सिग्नल साठवणे (trade झाला किंवा न झाला तरीही) — Dashboard वरच्या संपूर्ण Signal Log साठी.
    entry: {"symbol":.., "trade_date":.., "signal_time":.., "level_type":.., "level_price":..,
            "hit_type":.., "direction":.., "ltp_at_signal":.., "trade_status":.., "reason":..}
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO signal_log (symbol, trade_date, signal_time, level_type, level_price,
                                            hit_type, direction, ltp_at_signal, trade_status, reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (entry["symbol"], entry["trade_date"], entry["signal_time"], entry["level_type"],
                 entry["level_price"], entry["hit_type"], entry["direction"], entry.get("ltp_at_signal"),
                 entry.get("trade_status"), entry.get("reason")),
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_signal_log(symbol, trade_date):
    """त्या दिवसाचा संपूर्ण Signal Log वाचणे (अलीकडचा वेळ सर्वात वर)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT signal_time, level_type, level_price, hit_type, direction, ltp_at_signal,
                          trade_status, reason
                   FROM signal_log WHERE symbol=%s AND trade_date=%s ORDER BY signal_time DESC""",
                (symbol, trade_date),
            )
            rows = cur.fetchall()
            cols = ["signal_time", "level_type", "level_price", "hit_type", "direction", "ltp_at_signal", "trade_status", "reason"]
            return pd.DataFrame(rows, columns=cols)
    except Exception:
        return None
    finally:
        conn.close()


def save_nifty_1min_batch(rows):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — मोठ्या प्रमाणात (लाखो) 1-मिनिट candles efficiently
    साठवण्यासाठी — psycopg2.extras.execute_values() वापरून एकाच वेळी batch-insert (एक-एक row करत
    नाही, जे ८,५०,०००+ रांगांसाठी अत्यंत संथ ठरलं असतं). ON CONFLICT DO NOTHING -- आधीच असलेल्या
    timestamps पुन्हा दिले तरी सुरक्षितपणे वगळले जातात (idempotent -- पुन्हा चालवलं तरी डुप्लिकेट नाही).
    rows: [{"timestamp":.., "open":.., "high":.., "low":.., "close":.., "volume":..}, ...]
    """
    if not rows:
        return True
    conn = get_connection()
    if conn is None:
        return False
    try:
        import psycopg2.extras
        with conn.cursor() as cur:
            values = [(r["timestamp"], r["open"], r["high"], r["low"], r["close"], r.get("volume", 0)) for r in rows]
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO nifty_1min_ohlc (timestamp, open, high, low, close, volume) VALUES %s "
                "ON CONFLICT (timestamp) DO NOTHING",
                values,
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_nifty_1min_range(from_date=None, to_date=None):
    """साठवलेला NIFTY 1-मिनिट डेटा, ऐच्छिक तारीख-रेंज फिल्टरसह वाचणे (established load_nifty_1min()
    च्याच interface शी जुळणारं — columns: timestamp, open, high, low, close, volume)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            query = "SELECT timestamp, open, high, low, close, volume FROM nifty_1min_ohlc WHERE 1=1"
            params = []
            if from_date is not None:
                query += " AND timestamp >= %s"
                params.append(from_date)
            if to_date is not None:
                query += " AND timestamp <= %s"
                params.append(to_date)
            query += " ORDER BY timestamp ASC"
            cur.execute(query, params)
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    except Exception:
        return None
    finally:
        conn.close()


def get_nifty_1min_latest_timestamp():
    """साठवलेल्या डेटातली सर्वात अलीकडची timestamp (gap-fill/daily-update स्क्रिप्टसाठी -- कुठून पुढे भरायचं ते ठरवण्यासाठी)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(timestamp) FROM nifty_1min_ohlc")
            result = cur.fetchone()
            return result[0] if result else None
    except Exception:
        return None
    finally:
        conn.close()


def save_strike_oi_snapshot(symbol, trade_date, snapshot_time, strikes_data):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — प्रत्येक strike चा CE/PE OI, त्याच snapshot_time
    साठी, एकत्रित साठवणे. strikes_data: [{"strike":x, "ce_oi":n, "pe_oi":n}, ...] (oi_snapshot_collector
    कडे आधीच उपलब्ध, aggregate करण्यासाठी वापरलेलाच डेटा -- नवीन API कॉल्स लागत नाहीत).
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            for d in strikes_data:
                for option_type, oi_val in [("CE", d["ce_oi"]), ("PE", d["pe_oi"])]:
                    cur.execute(
                        """INSERT INTO strike_oi_history (symbol, strike, option_type, trade_date, snapshot_time, oi)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (symbol, strike, option_type, trade_date, snapshot_time)
                           DO UPDATE SET oi = EXCLUDED.oi""",
                        (symbol, d["strike"], option_type, trade_date, snapshot_time, oi_val),
                    )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_strike_oi_history(symbol, trade_date, strikes=None):
    """दिलेल्या दिवसाचा, प्रत्येक strike चा (हवं तर विशिष्ट strikes फिल्टर करून) OI इतिहास वाचणे."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if strikes:
                placeholders = ",".join(["%s"] * len(strikes))
                cur.execute(
                    f"""SELECT strike, option_type, snapshot_time, oi FROM strike_oi_history
                        WHERE symbol=%s AND trade_date=%s AND strike IN ({placeholders})
                        ORDER BY snapshot_time ASC""",
                    (symbol, trade_date, *strikes),
                )
            else:
                cur.execute(
                    """SELECT strike, option_type, snapshot_time, oi FROM strike_oi_history
                       WHERE symbol=%s AND trade_date=%s ORDER BY snapshot_time ASC""",
                    (symbol, trade_date),
                )
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=["strike", "option_type", "snapshot_time", "oi"])
    except Exception:
        return None
    finally:
        conn.close()


def save_market_zones(zones_df, symbol):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — दिलेल्या symbol चे जुने zones काढून, नवीन गणना केलेले
    zones साठवणे (replace-on-refresh — market_zones हे "सद्य स्थिती" दाखवतं, वाढत जाणारा इतिहास नाही).
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM market_zones WHERE symbol = %s", (symbol,))
            for _, row in zones_df.iterrows():
                cur.execute(
                    """INSERT INTO market_zones (symbol, zone_type, zone_low, zone_high, strength, formed_date, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (symbol, row["zone_type"], float(row["zone_low"]), float(row["zone_high"]),
                     float(row["strength"]) if pd.notna(row.get("strength")) else None,
                     row["formed_date"], row["status"]),
                )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_market_zones(symbol, status=None):
    """साठवलेले zones वाचणे — status दिलं (उदा. 'ACTIVE') तर फक्त तेवढेच, नाहीतर सर्व."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT symbol, zone_type, zone_low, zone_high, strength, formed_date, status FROM market_zones "
                    "WHERE symbol = %s AND status = %s ORDER BY zone_type",
                    (symbol, status),
                )
            else:
                cur.execute(
                    "SELECT symbol, zone_type, zone_low, zone_high, strength, formed_date, status FROM market_zones "
                    "WHERE symbol = %s ORDER BY zone_type",
                    (symbol,),
                )
            rows = cur.fetchall()
            cols = ["symbol", "zone_type", "zone_low", "zone_high", "strength", "formed_date", "status"]
            return pd.DataFrame(rows, columns=cols)
    except Exception:
        return None
    finally:
        conn.close()


def save_upstox_token(access_token):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — नवीन Upstox token (webhook कडून मिळालेला)
    Supabase मध्ये साठवणे. जुने token (इतिहास ठेवण्यासाठी) राहतात, फक्त नवीन ओळ (row) जोडली जाते —
    वाचताना नेहमी सर्वात नवीनच (get_latest_upstox_token) वापरला जातो.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO upstox_tokens (access_token) VALUES (%s)", (access_token,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_latest_upstox_token():
    """सर्वात अलीकडे साठवलेला Upstox token परत करणे, किंवा काहीच नसेल/जोडणी अयशस्वी झाली तर None."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT access_token FROM upstox_tokens ORDER BY received_at DESC LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()


def save_oi_snapshot_cloud(symbol, trade_date, snapshot_time, total_call_oi, total_put_oi,
                             diff, delta_diff, signal, underlying_price, total_call_premium, total_put_premium):
    """
    एक OI snapshot cloud DB मध्ये साठवणे — त्याच (symbol, trade_date, snapshot_time) साठी आधीच
    नोंद असेल तर काहीही न करता (ON CONFLICT DO NOTHING) शांतपणे वगळणे — डुप्लिकेट टाळण्यासाठी
    (SQLite च्या INSERT OR IGNORE सारखंच).
    रिटर्न: True (यशस्वी) / False (जोडणी उपलब्ध नाही किंवा अयशस्वी).
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO oi_diff_snapshots
                   (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff,
                    signal, underlying_price, total_call_premium, total_put_premium)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (symbol, trade_date, snapshot_time) DO NOTHING""",
                (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff,
                 signal, underlying_price, total_call_premium, total_put_premium),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_recent_oi_snapshots_cloud(symbol, trade_date, before_time=None, limit=5):
    """Signal Engine (स्थिरता तपासणी) साठी — दिलेल्या वेळेपूर्वीचे शेवटचे N snapshots (जुनं->नवीन क्रमाने)."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if before_time:
                cur.execute(
                    """SELECT diff, total_put_oi, total_call_oi, signal FROM oi_diff_snapshots
                       WHERE symbol=%s AND trade_date=%s AND snapshot_time < %s
                       ORDER BY snapshot_time DESC LIMIT %s""",
                    (symbol, trade_date, before_time, limit),
                )
            else:
                cur.execute(
                    """SELECT diff, total_put_oi, total_call_oi, signal FROM oi_diff_snapshots
                       WHERE symbol=%s AND trade_date=%s
                       ORDER BY snapshot_time DESC LIMIT %s""",
                    (symbol, trade_date, limit),
                )
            rows = cur.fetchall()
        return list(reversed(rows))  # जुनं->नवीन
    finally:
        conn.close()


def get_oi_price_history_cloud(symbol, trade_date):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — PCR + NIFTY किंमत, वेळेनुसार Chart (Sensibull-सारखं)
    साठी. established get_oi_history_cloud() पेक्षा वेगळं (त्यात बदल टाळला, सुरक्षिततेसाठी) —
    इथे underlying_price सुद्धा वाचला जातो (जो table मध्ये आधीच साठवलेला आहे, पण जुनं function वाचत
    नव्हतं). अलीकडचा वेळ शेवटी (ASC) -- chart plotting साठी योग्य क्रम.
    """
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT snapshot_time, total_call_oi, total_put_oi, underlying_price
                   FROM oi_diff_snapshots WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time ASC""",
                (symbol, trade_date),
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_oi_history_cloud(symbol, trade_date):
    """Dashboard च्या टेबलसाठी — त्या दिवसाचा संपूर्ण इतिहास (अलीकडचा वेळ सर्वात वर), premium सहित."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal,
                          total_call_premium, total_put_premium
                   FROM oi_diff_snapshots WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time DESC""",
                (symbol, trade_date),
            )
            return cur.fetchall()
    finally:
        conn.close()
