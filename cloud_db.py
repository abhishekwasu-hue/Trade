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
import datetime
import json
import os

import pandas as pd

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

from log_setup import get_logger

_logger = get_logger("cloud_db.py")

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
    account_id TEXT,
    received_at TIMESTAMP NOT NULL DEFAULT NOW()
);
ALTER TABLE upstox_tokens ADD COLUMN IF NOT EXISTS account_id TEXT;
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

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Nifty SRv2 Momentum-Filter Reversal" रणनीतीचं
# राज्य (One-Touch Rule + Cooldown Period) — GitHub Actions प्रत्येक वेळी नवीन (rikama) environment
# मध्ये चालत असल्याने, हे राज्य Supabase मध्येच साठवावं लागतं (स्थानिक फाईल टिकत नाही).
CREATE_SRV2_STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS srv2_strategy_state (
    symbol TEXT PRIMARY KEY,
    last_tested_level REAL,
    last_sl_hit_time TIMESTAMP
);
"""

# वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — SRv2 चे lots/hedge_width_points आता Dashboard वरून
# बदलता येतील (hardcode नाही). symbol प्रत्येकाची स्वतंत्र नोंद.
CREATE_SRV2_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS srv2_settings (
    symbol TEXT PRIMARY KEY,
    lots INTEGER NOT NULL DEFAULT 1,
    hedge_width_points REAL NOT NULL DEFAULT 100,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

# वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) — एकाच, flexible
# table मध्ये कुठल्याही strategy चे settings — नवीन field जोडायला schema-बदल (migration) लागू नये
# म्हणून JSONB. (strategy_name, symbol) प्रत्येकाची स्वतंत्र नोंद.
CREATE_STRATEGY_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strategy_settings (
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    settings JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (strategy_name, symbol)
);
"""

# वापरकर्त्याशी चर्चा करून ठरवलेले, नवीन नियम-संचातले डीफॉल्ट — Dashboard वरून बदलले नसतील तर हेच
# वापरले जातात (कधीच hardcoded राहत नाहीत — इथूनच, एकाच जागी, बदलण्याजोगे).
STRATEGY_SETTINGS_DEFAULTS = {
    "1m_instant": {
        "lots": 1,
        "itm_depth_points": 50,          # Short leg — ATM पासून किती points ITM
        "hedge_width_points": 150,       # Long hedge — short strike पासून किती दूर
        # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Gate — RSI/PCR आता on/off + adjustable) —
        # आधी RSI उंबरठे (Support<40/Resistance>60) module मध्ये hardcoded होते, PCR गेट कधीच बंद
        # करता येत नव्हता. आता दोन्ही Dashboard वरून (Entry Gate विभाग) नियंत्रित करता येतात —
        # डीफॉल्ट दोन्ही चालू, जुनेच उंबरठे, म्हणजे न बदलणाऱ्या वापरकर्त्यांसाठी वर्तन तेच राहतं.
        "entry_rsi_gate_enabled": True,
        "rsi_support_max": 40,           # Support/Bullish साठी RSI यापेक्षा कमी हवा
        "rsi_resistance_min": 60,        # Resistance/Bearish साठी RSI यापेक्षा जास्त हवा
        "entry_pcr_gate_enabled": True,
        # PCR < pcr_bullish_min -> Bullish trade नाही. PCR > pcr_bearish_max -> Bearish trade नाही.
        # डेटा गहाळ/जुना असल्यास trade थांबवणे (fail-safe) — हे PCR गेट बंद असतानाही लागू होत नाही.
        "pcr_bullish_min": 0.80,
        "pcr_bearish_max": 1.10,
        "spread_sl_spot_pct": 0.05,
        "spread_sl_premium_points": 5,
        "spread_tsl_spot_pct": 0.10,
        "spread_tsl_premium_points": 10,
        "spread_target_spot_pct": 0.20,
        "spread_target_premium_points": 15,
        "naked_enabled": True,           # "on the same signal" -- डीफॉल्ट सक्रिय, Dashboard वरून बंद करता येईल
        "naked_hedge_enabled": False,    # डीफॉल्ट: निव्वळ (naked) buy, hedge नाही
        "naked_hedge_width_points": 150,
        "naked_sl_spot_pct": 0.05,
        "naked_sl_premium_points": 10,
        "naked_tsl_spot_pct": 0.10,
        "naked_tsl_premium_points": 20,
        "naked_target_spot_pct": 0.20,
        "naked_target_premium_points": 30,
    },
    "15m_dynamic_sr": {
        "lots": 1,
        "itm_depth_points": 100,
        "hedge_width_points": 150,
        # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Gate — RSI/PCR आता on/off + adjustable) —
        # 1m_instant सारखीच सुधारणा, पण srv2_momentum_reversal_strategy.py चा RSI गेट एकाच
        # neutral_level (50) भोवती सममित आहे (Support<50/Resistance>50), दोन वेगळे उंबरठे नाहीत.
        "entry_rsi_gate_enabled": True,
        "rsi_neutral_level": 50,
        "entry_pcr_gate_enabled": True,
        "pcr_bullish_min": 0.80,
        "pcr_bearish_max": 1.10,
        "spread_sl_spot_pct": 0.15,
        "spread_sl_premium_points": 10,
        "spread_tsl_spot_pct": 0.30,
        "spread_tsl_premium_points": 25,
        "spread_target_pct_of_premium": 80,
        "carry_forward_min_profit_pct": 30,
        "naked_enabled": True,
        "naked_hedge_enabled": False,
        "naked_hedge_width_points": 150,
        "naked_sl_spot_pct": 0.05,
        "naked_sl_premium_points": 10,
        "naked_tsl_spot_pct": 0.10,
        "naked_tsl_premium_points": 20,
        "naked_target_spot_pct": 0.40,
        "naked_target_premium_points": 50,
        "naked_eod_hour": 15,            # Naked trades कधीच carry-forward नाहीत, नेहमी आजच 3:00pm ला बंद
        "naked_eod_minute": 0,
    },
}

# वापरकर्त्याने सापडवलेली bug — वरचे itm_depth_points/hedge_width_points/naked_hedge_width_points
# डीफॉल्ट NIFTY (strike step 50) साठी ठरवलेले आहेत, पण सर्व तीनही symbols साठी तेच सपाट आकडे
# दाखवले जायचे — BANKNIFTY/SENSEX चा strike step 100 (NIFTY च्या दुप्पट) असल्याने तोच आकडा त्यांच्यासाठी
# प्रत्यक्षात निम्म्या strikes-ITM ला जातो, प्रमाणाबाहेर. खालचा STRIKE_STEP आणि _scale_strike_relative_defaults()
# हे फक्त strike-निवडीशी संबंधित (points) fields, symbol च्या स्वतःच्या strike step नुसार प्रमाणात
# मोठे/लहान करतात — फक्त वापरकर्त्याने अजून त्या symbol साठी स्वतः customize न केलेल्या डीफॉल्टवरच लागू
# होतं (एकदा जतन केलं की तोच जतन केलेला आकडा कायम वापरला जातो, इथे काही बदलत नाही).
STRIKE_STEP = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}
_STRIKE_RELATIVE_FIELDS = ("itm_depth_points", "hedge_width_points", "naked_hedge_width_points")


def _scale_strike_relative_defaults(defaults, symbol):
    step = STRIKE_STEP.get(symbol, STRIKE_STEP["NIFTY"])
    baseline_step = STRIKE_STEP["NIFTY"]
    if step == baseline_step:
        return defaults
    scaled = dict(defaults)
    for field in _STRIKE_RELATIVE_FIELDS:
        if field in scaled:
            scaled[field] = max(round(scaled[field] / baseline_step) * step, step)
    return scaled

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" — कुठले accounts
# (कुठल्या broker वर) established रणनींतींनी वापरायचे, याची नोंदणी.
CREATE_BROKER_ACCOUNTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS broker_accounts (
    account_id TEXT PRIMARY KEY,
    broker_type TEXT NOT NULL,
    nickname TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    lot_multiplier REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW()
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
        _logger.exception("get_connection() मध्ये अनपेक्षित चूक (silently handled)")
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
    """oi_diff_snapshots, upstox_tokens, market_zones, strike_oi_history, nifty_1min_ohlc,
    signal_log, srv2_strategy_state, srv2_settings आणि broker_accounts tables (नसतील तर) तयार करणे."""
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
            cur.execute(CREATE_SRV2_STATE_TABLE_SQL)
            cur.execute(CREATE_SRV2_SETTINGS_TABLE_SQL)
            cur.execute(CREATE_STRATEGY_SETTINGS_TABLE_SQL)
            cur.execute(CREATE_BROKER_ACCOUNTS_TABLE_SQL)
        conn.commit()
        return True
    finally:
        conn.close()


def add_broker_account(account_id, broker_type, nickname=None, lot_multiplier=1.0):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" रणनीतीसाठी नवीन account
    नोंदवणे. account_id (nickname, unique) आधीच असेल तर अद्ययावत (upsert) होतो.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO broker_accounts (account_id, broker_type, nickname, lot_multiplier)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (account_id) DO UPDATE SET
                       broker_type = EXCLUDED.broker_type, nickname = EXCLUDED.nickname,
                       lot_multiplier = EXCLUDED.lot_multiplier""",
                (account_id, broker_type, nickname, lot_multiplier),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("add_broker_account() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_all_broker_accounts(active_only=True):
    """established, नोंदवलेले सर्व accounts वाचणे (established रणनींतींनी loop करून प्रत्येकावर trade घेण्यासाठी)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            query = "SELECT account_id, broker_type, nickname, is_active, lot_multiplier FROM broker_accounts"
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY account_id"
            cur.execute(query)
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=["account_id", "broker_type", "nickname", "is_active", "lot_multiplier"])
    except Exception:
        _logger.exception("get_all_broker_accounts() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def set_broker_account_active(account_id, is_active):
    """established account सक्रिय/निष्क्रिय करणे (Dashboard वरच्या toggle साठी)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE broker_accounts SET is_active=%s WHERE account_id=%s", (is_active, account_id))
        conn.commit()
        return True
    except Exception:
        _logger.exception("set_broker_account_active() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def delete_broker_account(account_id):
    """established account पूर्णपणे काढून टाकणे."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM broker_accounts WHERE account_id=%s", (account_id,))
        conn.commit()
        return True
    except Exception:
        _logger.exception("delete_broker_account() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_srv2_state(symbol):
    """established srv2 रणनीतीचं राज्य वाचणे (One-Touch + Cooldown साठी) — नसेल तर सुरक्षित डीफॉल्ट."""
    conn = get_connection()
    if conn is None:
        return {"last_tested_level": None, "last_sl_hit_time": None}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT last_tested_level, last_sl_hit_time FROM srv2_strategy_state WHERE symbol=%s", (symbol,))
            row = cur.fetchone()
            if row is None:
                return {"last_tested_level": None, "last_sl_hit_time": None}
            return {"last_tested_level": row[0], "last_sl_hit_time": row[1]}
    except Exception:
        _logger.exception("get_srv2_state() मध्ये अनपेक्षित चूक (silently handled)")
        return {"last_tested_level": None, "last_sl_hit_time": None}
    finally:
        conn.close()


def save_srv2_state(symbol, last_tested_level=None, last_sl_hit_time=None):
    """srv2 रणनीतीचं राज्य साठवणे (upsert — symbol आधीच असेल तर अद्ययावत, नसेल तर नवीन)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO srv2_strategy_state (symbol, last_tested_level, last_sl_hit_time)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (symbol) DO UPDATE SET
                       last_tested_level = EXCLUDED.last_tested_level,
                       last_sl_hit_time = EXCLUDED.last_sl_hit_time""",
                (symbol, last_tested_level, last_sl_hit_time),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_srv2_state() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_srv2_settings(symbol):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — SRv2 चे lots/hedge_width_points Dashboard वरून
    बदलता येण्यासाठी. नोंद नसेल तर सुरक्षित डीफॉल्ट (lots=1, hedge_width_points=100 — जुनं hardcoded
    मूल्य)."""
    conn = get_connection()
    if conn is None:
        return {"lots": 1, "hedge_width_points": 100.0}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT lots, hedge_width_points FROM srv2_settings WHERE symbol=%s", (symbol,))
            row = cur.fetchone()
            if row is None:
                return {"lots": 1, "hedge_width_points": 100.0}
            return {"lots": int(row[0]), "hedge_width_points": float(row[1])}
    except Exception:
        _logger.exception("get_srv2_settings() मध्ये अनपेक्षित चूक (silently handled)")
        return {"lots": 1, "hedge_width_points": 100.0}
    finally:
        conn.close()


def save_srv2_settings(symbol, lots, hedge_width_points):
    """SRv2 चे lots/hedge_width_points साठवणे (upsert)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO srv2_settings (symbol, lots, hedge_width_points, updated_at)
                   VALUES (%s, %s, %s, NOW())
                   ON CONFLICT (symbol) DO UPDATE SET
                       lots = EXCLUDED.lots,
                       hedge_width_points = EXCLUDED.hedge_width_points,
                       updated_at = NOW()""",
                (symbol, lots, hedge_width_points),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_srv2_settings() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_strategy_settings(strategy_name, symbol):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) —
    strategy_name ("1m_instant" किंवा "15m_dynamic_sr") + symbol साठी settings. Supabase मध्ये
    साठवलेले (Dashboard वरून बदललेले) आणि डीफॉल्ट (STRATEGY_SETTINGS_DEFAULTS) यांचं मिश्रण —
    वापरकर्त्याने फक्त काही fields बदलले असतील, तर बाकीचे डीफॉल्ट कायम राहतात. Supabase न मिळाल्यास
    (किंवा नोंद नसल्यास) संपूर्णपणे डीफॉल्ट (itm_depth_points/hedge_width_points/naked_hedge_width_points
    symbol च्या स्वतःच्या strike step नुसार आधीच प्रमाणात मोठे/लहान केलेले — _scale_strike_relative_defaults() बघा)."""
    defaults = _scale_strike_relative_defaults(dict(STRATEGY_SETTINGS_DEFAULTS.get(strategy_name, {})), symbol)
    conn = get_connection()
    if conn is None:
        return defaults
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT settings FROM strategy_settings WHERE strategy_name=%s AND symbol=%s",
                (strategy_name, symbol),
            )
            row = cur.fetchone()
            if row is None:
                return defaults
            stored = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            merged = dict(defaults)
            merged.update(stored)
            return merged
    except Exception:
        return defaults
    finally:
        conn.close()


def save_strategy_settings(strategy_name, symbol, settings_dict):
    """strategy_name + symbol साठी settings साठवणे (upsert, आंशिक अपडेट — फक्त दिलेले fields
    बदलतात, बाकीचे आधीचेच राहतात — PostgreSQL JSONB `||` merge-operator वापरून)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO strategy_settings (strategy_name, symbol, settings, updated_at)
                   VALUES (%s, %s, %s, NOW())
                   ON CONFLICT (strategy_name, symbol) DO UPDATE SET
                       settings = strategy_settings.settings || EXCLUDED.settings,
                       updated_at = NOW()""",
                (strategy_name, symbol, json.dumps(settings_dict)),
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_next_level_in_direction(symbol, entry_level_price, direction_bullish, timeframe_suffixes=("15M", "30M", "60M")):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Timeframe SRv2, Next-Level-Exit) —
    entry_level_price पासून favourable दिशेने, दिलेल्या timeframe_suffixes (डीफॉल्ट तिन्ही पूल
    केलेले — पण caller ने विशिष्ट एकच timeframe दिल्यास, उदा. ("15M",), "same-timeframe exit"
    हेही याच function ने साध्य होतं) मधला सर्वात जवळचा ACTIVE level शोधणे.
    direction_bullish=True -> entry_level_price पेक्षा वर, सर्वात जवळचा (favourable = वर जाणं).
    direction_bullish=False -> entry_level_price पेक्षा खाली, सर्वात जवळचा (favourable = खाली जाणं).
    रिटर्न: level_price (float) किंवा None (सापडला नाही तर)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        zone_types = []
        for tf in timeframe_suffixes:
            zone_types.append(f"DYNAMIC_SR_SUPPORT_{tf}")
            zone_types.append(f"DYNAMIC_SR_RESISTANCE_{tf}")
        placeholders = ",".join(["%s"] * len(zone_types))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT zone_low FROM market_zones WHERE symbol=%s AND zone_type IN ({placeholders}) AND status='ACTIVE'",
                (symbol, *zone_types),
            )
            rows = cur.fetchall()
        candidates = [float(r[0]) for r in rows]
        if direction_bullish:
            above = [c for c in candidates if c > entry_level_price]
            return min(above) if above else None
        below = [c for c in candidates if c < entry_level_price]
        return max(below) if below else None
    except Exception:
        _logger.exception("get_next_level_in_direction() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def get_zone_hits_today(symbol, level_price, trade_date):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit Dynamic S/R) — established एकाच zone ला
    दिवसातून जास्तीत जास्त किती वेळा (आणि केव्हा शेवटचं) hit झालाय, हे established signal_log वरूनच
    काढणे (वेगळं table/column लागत नाही — प्रत्येक hit आधीच इथे साठवलेला असतो).
    रिटर्न: (hit_count: int, last_hit_time: datetime किंवा None)
    """
    conn = get_connection()
    if conn is None:
        return 0, None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT signal_time FROM signal_log
                   WHERE symbol=%s AND trade_date=%s AND level_price=%s AND hit_type != 'NO_HIT'
                   ORDER BY signal_time DESC""",
                (symbol, trade_date, level_price),
            )
            rows = cur.fetchall()
            if not rows:
                return 0, None
            return len(rows), rows[0][0]
    except Exception:
        _logger.exception("get_zone_hits_today() मध्ये अनपेक्षित चूक (silently handled)")
        return 0, None
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
        _logger.exception("save_signal_log() मध्ये अनपेक्षित चूक (silently handled)")
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
        _logger.exception("get_signal_log() मध्ये अनपेक्षित चूक (silently handled)")
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
        _logger.exception("save_nifty_1min_batch() मध्ये अनपेक्षित चूक (silently handled)")
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
        _logger.exception("get_nifty_1min_range() मध्ये अनपेक्षित चूक (silently handled)")
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
        _logger.exception("get_nifty_1min_latest_timestamp() मध्ये अनपेक्षित चूक (silently handled)")
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
        _logger.exception("save_strike_oi_snapshot() मध्ये अनपेक्षित चूक (silently handled)")
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
        _logger.exception("get_strike_oi_history() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def merge_dynamic_sr_zones(symbol, dyn_sr_result, timeframe_suffix, tolerance_pct=0.02, formed_date=None):
    """
    हलका (5-मिनिट/10-मिनिट) Dynamic S/R refresh — save_market_zones() (पूर्ण replace) च्या उलट, इथे
    फक्त DYNAMIC_SR_*_{timeframe_suffix} (उदा. "1M" किंवा "15M") प्रकारचे zones merge केले जातात:
      - नवीन गणना केलेला level जुन्या ACTIVE level च्या ±tolerance_pct% च्या आत असेल, तर जुनाच
        level_price कायम ठेवला जातो (Multi-Hit hit-count history टिकून राहावी म्हणून).
      - नवीन, न जुळणारा उमेदवार असेल, तो नव्याने जोडला जातो.
      - जुना, नव्या गणनेत न सापडलेला level DELETE केला जात नाही (मोठा gap झाल्यावर जुना पण खरा
        level "सर्वोत्तम ५" यादीतून बाहेर पडला तरी हरवू नये, किंमत नंतर तिथे परत आली तर उपयोगी
        पडावा म्हणून). त्यामुळे दिवसभरात यादी ५ पेक्षा जास्त वाढू शकते — रोजची स्वच्छता फक्त
        रात्रीच्या पूर्ण refresh_market_zones.py द्वारेच होते.
    रिटर्न: True/False (यशस्वी झालं की नाही).
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        formed_date = formed_date or datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
        support_type = f"DYNAMIC_SR_SUPPORT_{timeframe_suffix}"
        resistance_type = f"DYNAMIC_SR_RESISTANCE_{timeframe_suffix}"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, zone_type, zone_low FROM market_zones WHERE symbol = %s "
                "AND zone_type IN (%s, %s) AND status = 'ACTIVE'",
                (symbol, support_type, resistance_type),
            )
            existing = cur.fetchall()  # [(id, zone_type, zone_low), ...]

            for zone_type, candidates in [
                (support_type, dyn_sr_result.get("support", [])),
                (resistance_type, dyn_sr_result.get("resistance", [])),
            ]:
                existing_of_type = [(row_id, zone_low) for (row_id, zt, zone_low) in existing if zt == zone_type]
                matched_existing_ids = set()

                for cand in candidates:
                    cand_level = float(cand["level"])
                    buffer = cand_level * tolerance_pct / 100
                    matched = next(
                        (row_id for (row_id, zone_low) in existing_of_type
                         if abs(float(zone_low) - cand_level) <= buffer and row_id not in matched_existing_ids),
                        None,
                    )
                    if matched is not None:
                        matched_existing_ids.add(matched)  # जुनाच level_price कायम -- काहीही न बदलता
                    else:
                        cur.execute(
                            """INSERT INTO market_zones (symbol, zone_type, zone_low, zone_high, strength, formed_date, status)
                               VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')""",
                            (symbol, zone_type, cand_level, cand_level, float(cand["touches"]), formed_date),
                        )

        conn.commit()
        return True
    except Exception:
        _logger.exception("merge_dynamic_sr_zones() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def merge_dynamic_sr_1m_zones(symbol, dyn_sr_result, tolerance_pct=0.02, formed_date=None):
    """Backward-compatible wrapper — merge_dynamic_sr_zones() ला "1M" सह कॉल करते."""
    return merge_dynamic_sr_zones(symbol, dyn_sr_result, "1M", tolerance_pct, formed_date)


def save_market_zones(zones_df, symbol):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — दिलेल्या symbol चे जुने zones काढून, नवीन गणना केलेले
    zones साठवणे (replace-on-refresh — market_zones हे "सद्य स्थिती" दाखवतं, वाढत जाणारा इतिहास नाही).

    🎓 वापरकर्त्याशी चर्चा करून मागे-घेतलेली सुधारणा — DYNAMIC_SR_*_1M/*_5M ला या nightly DELETE
    मधून वगळून, ते कायमचे फक्त त्यांच्याच दर-५-मिनिटांच्या merge-cron कडे सोपवण्याचा आधीचा प्रयत्न
    चुकीचा ठरला — त्या merge-cron चं "जुने levels कधीच न काढणे" फक्त त्याच दिवसापुरतं योग्य आहे,
    कायमचं नाही: nightly वगळल्यामुळे आठवडाभर जुना, आता पूर्णपणे अप्रस्तुत 1-मिनिट pivot अजूनही ACTIVE
    राहून खरा trade घेऊ शकत होता (वापरकर्त्याने विचारून सापडवलेली, वेगळी bug). योग्य उपाय: nightly
    refresh आताही **सर्वच** zone_types (1M/5M सकट) रोज साफ करून, ताज्या (अलीकडच्या काही दिवसांच्या)
    डेटावरून पुन्हा गणना करतो — बघा market_zones.compute_all_zones() मधली df_1m_recent/df_5m_recent
    टिप्पणी.
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
        _logger.exception("save_market_zones() मध्ये अनपेक्षित चूक (silently handled)")
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
        _logger.exception("get_market_zones() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def save_upstox_token(access_token, account_id=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — नवीन Upstox token (webhook कडून मिळालेला)
    Supabase मध्ये साठवणे. जुने token (इतिहास ठेवण्यासाठी) राहतात, फक्त नवीन ओळ (row) जोडली जाते —
    वाचताना नेहमी सर्वात नवीनच (get_latest_upstox_token) वापरला जातो.
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" — account_id दिला
    (established broker_accounts मधलं nickname) तर तो त्याच account साठी वेगळा साठवला जातो;
    न दिल्यास established, एकमेव (single) खात्यासाठीचं जुनं वर्तन तसंच (backward-compatible) राहतं.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO upstox_tokens (access_token, account_id) VALUES (%s, %s)", (access_token, account_id))
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_upstox_token() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_latest_upstox_token(account_id=None):
    """सर्वात अलीकडे साठवलेला Upstox token परत करणे, किंवा काहीच नसेल/जोडणी अयशस्वी झाली तर None.
    🎓 account_id दिला तर फक्त त्याच account चा token; न दिल्यास established, जुना (account_id
    नसलेला/single-account) token वाचला जातो — backward-compatible."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if account_id is not None:
                cur.execute(
                    "SELECT access_token FROM upstox_tokens WHERE account_id=%s ORDER BY received_at DESC LIMIT 1",
                    (account_id,),
                )
            else:
                cur.execute(
                    "SELECT access_token FROM upstox_tokens WHERE account_id IS NULL ORDER BY received_at DESC LIMIT 1"
                )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        _logger.exception("get_latest_upstox_token() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def get_token_age_hours(account_id=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — रोजचा manual OAuth login (get_upstox_token_manual.py)
    चुकल्यास सर्व cron jobs शांतपणे token न मिळाल्याने थांबतात, कुणालाच कळत नाही — यासाठी सर्वात
    अलीकडचा token किती तासांपूर्वी साठवला गेला, ते तपासण्यासाठी (check_token_freshness.py वापरतं).
    रिटर्न: तासांमधलं वय (float), किंवा token च नसेल/जोडणी अयशस्वी झाली तर None.
    """
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if account_id is not None:
                cur.execute(
                    "SELECT EXTRACT(EPOCH FROM (NOW() - received_at)) / 3600.0 FROM upstox_tokens "
                    "WHERE account_id=%s ORDER BY received_at DESC LIMIT 1",
                    (account_id,),
                )
            else:
                cur.execute(
                    "SELECT EXTRACT(EPOCH FROM (NOW() - received_at)) / 3600.0 FROM upstox_tokens "
                    "WHERE account_id IS NULL ORDER BY received_at DESC LIMIT 1"
                )
            row = cur.fetchone()
            return float(row[0]) if row else None
    except Exception:
        _logger.exception("get_token_age_hours() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def get_effective_upstox_token(cli_token, account_id=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Upstox Token Webhook (VPS वर, एका
    मोबाईल-टॅपवर रोज नवीन token) पूर्ण automation साठी वापरण्यायोग्य करणे. established --token
    (GitHub Secret) दिलेला असेल तर तोच वापरणे (backward-compatible, जुनी पद्धत अजूनही चालते) —
    नाहीतर established get_latest_upstox_token() (Supabase, Webhook ने साठवलेला) आपोआप वापरणे.
    account_id दिला तर established multi-account token वाचला जातो (backward-compatible, डीफॉल्ट None).
    """
    if cli_token:
        return cli_token
    return get_latest_upstox_token(account_id)


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
        _logger.exception("save_oi_snapshot_cloud() मध्ये अनपेक्षित चूक (silently handled)")
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


def get_latest_oi_snapshot_cloud(symbol, trade_date):
    """वापरकर्त्याने VPS वरून प्रत्यक्ष तपासून सापडवलेली bug (PCR Gate) — त्या दिवसाचा सर्वात
    अलीकडचा snapshot, फक्त एकच रांग (oi_analysis.get_latest_pcr() साठी). आधी हे function
    अस्तित्वातच नव्हतं — get_latest_pcr() नेहमी फक्त local SQLite कडेच बघायचं, Cloud DB configured
    असतानाही. पण oi_snapshot_collector.py Cloud DB configured असेल तर तिथेच लिहितो (local SQLite
    मध्ये काहीच लिहीत नाही) — त्यामुळे PCR Gate ला कायम "डेटा उपलब्ध नाही" दिसायचं आणि प्रत्येक
    trade अडवला जायचा, जरी collector स्वतः दर ५ मिनिटांनी व्यवस्थित (Supabase मध्ये) डेटा साठवत असला तरी."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT snapshot_time, total_call_oi, total_put_oi FROM oi_diff_snapshots
                   WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time DESC LIMIT 1""",
                (symbol, trade_date),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_latest_oi_signal_cloud(symbol, trade_date):
    """त्या दिवसाचा सर्वात अलीकडचा 'signal' — oi_analysis.get_latest_oi_signal() साठी (A1 Engine
    च्या OI Confirmation Gate मध्ये वापरलं जातं — get_latest_pcr() सारखीच, Cloud DB configured
    असताना local SQLite कडे बघण्याची चूक इथेही होती)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT signal FROM oi_diff_snapshots WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time DESC LIMIT 1""",
                (symbol, trade_date),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def get_previous_day_oi_cloud(symbol, today_str):
    """आजच्या आधीच्या शेवटच्या ट्रेडिंग दिवसाचा शेवटचा एकूण (Call+Put) OI — oi_analysis.
    get_previous_day_total_oi() साठी (Swing मोडचं OI-Price Matrix — तीच local-SQLite-only चूक)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT total_call_oi, total_put_oi FROM oi_diff_snapshots
                   WHERE symbol=%s AND trade_date < %s ORDER BY trade_date DESC, snapshot_time DESC LIMIT 1""",
                (symbol, today_str),
            )
            row = cur.fetchone()
            return (row[0] + row[1]) if row else None
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
