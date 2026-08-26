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


def init_cloud_table():
    """oi_diff_snapshots table (नसेल तर) तयार करणे. Configured नसेल तर शांतपणे False."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        return True
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
