"""SQLite database: schema init, order/trade logging, and all query/read functions."""
import datetime
import json
import os
import re
import sqlite3
import pandas as pd

from config import DATA_DIR, DB_PATH, get_ist_now, get_ist_today
from upstox_api import fetch_ltp_map, upload_to_google_drive


from log_setup import get_logger

_logger = get_logger("database.py")

# 🎓 वापरकर्त्याने मागितलेली सुधारणा (शिफारसी — SL/TSL-प्रकार वि. Target-प्रकार वर्गीकरण) — आधी हे
# page_performance.py मध्ये फक्त शिफारसींसाठी, स्थानिक पातळीवर परिभाषित होते. आता इथे, केंद्रीय
# ठिकाणी — page_performance.py इथून import करतो (duplicate व्याख्या टाळण्यासाठी). हे Trailing-SL/
# Premium-Target सकट, "व्यापक" वर्गीकरण आहे — खालच्या win-rate साठीच्या "शुद्ध" (narrow) सेट्सपेक्षा वेगळं.
SL_TYPE_EXIT_REASONS = {"SL", "TRAILING_SL", "PCT_TRAILING_SL", "TSL_SL", "SL_HIT"}
TARGET_TYPE_EXIT_REASONS = {"TARGET", "PREMIUM_TARGET", "NEXT_LEVEL_EXIT", "TARGET_HIT"}

# 🎓 वापरकर्त्याने मागितलेली सुधारणा (Winning Rate — फक्त शुद्ध SL/Target) — वापरकर्त्याशी स्पष्टपणे
# चर्चा करून ठरवलेला निर्णय: Win Rate आता **फक्त** शुद्ध SL किंवा शुद्ध TARGET या दोनच exit_reason
# प्रकारांवर आधारित असायला हवी — Trailing SL (स्वतःहून घट्ट होणारा) किंवा Breakeven-वर अडकलेला SL
# (TSL_SL) यामुळे बंद झालेले trades, तसंच EOD/Carry-Forward/Manual/OI-Reversal/Next-Level-Exit —
# हे सगळे या गणनेतून (numerator आणि denominator दोन्हीतून) पूर्णपणे वगळायचे. वरच्या "व्यापक"
# SL_TYPE_EXIT_REASONS/TARGET_TYPE_EXIT_REASONS (जे Trailing/Premium-Target सुद्धा धरतात, फक्त
# शिफारसींसाठी वापरलेले) यांच्यापेक्षा हे मुद्दामच वेगळे, अरुंद (narrow) सेट्स आहेत.
WIN_RATE_SL_REASONS = {"SL", "SL_HIT"}  # SL_HIT = जुनी (legacy) नोंद, "SL" चाच जुना समानार्थी शब्द
WIN_RATE_TARGET_REASONS = {"TARGET", "TARGET_HIT"}  # TARGET_HIT = जुनी (legacy) नोंद
WIN_RATE_COUNTED_REASONS = WIN_RATE_SL_REASONS | WIN_RATE_TARGET_REASONS


def init_sqlite_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS day_baseline_oi (
            symbol TEXT,
            strike REAL,
            trade_date TEXT,
            initial_ce_oi INTEGER,
            initial_pe_oi INTEGER,
            PRIMARY KEY (symbol, strike, trade_date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_candles (
            symbol TEXT,
            interval TEXT,
            timestamp TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            oi INTEGER,
            PRIMARY KEY (symbol, interval, timestamp)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oi_diff_snapshots (
            symbol TEXT,
            trade_date TEXT,
            snapshot_time TEXT,
            total_call_oi INTEGER,
            total_put_oi INTEGER,
            diff INTEGER,
            delta_diff INTEGER,
            signal TEXT,
            PRIMARY KEY (symbol, trade_date, snapshot_time)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_trades (
            trade_id TEXT PRIMARY KEY,
            trade_date TEXT,
            symbol TEXT,
            strategy TEXT,
            short_strike REAL,
            long_strike REAL,
            short_instrument TEXT,
            long_instrument TEXT,
            lots INTEGER,
            lot_size INTEGER,
            net_credit REAL,
            max_profit REAL,
            max_loss REAL,
            sl_pnl_level REAL,
            target_pnl_level REAL,
            entry_time TEXT,
            exit_time TEXT,
            exit_reason TEXT,
            realized_pnl REAL,
            status TEXT,
            short_order_id TEXT,
            long_order_id TEXT
        )
    """)
    # legs_json / strikes_summary — Iron Condor/Butterfly सारख्या N-leg स्ट्रॅटेजीजसाठी लागणारे नवीन कॉलम्स.
    # आधीपासून अस्तित्वात असलेल्या DB फाईलवरही सुरक्षितपणे चालण्यासाठी ALTER TABLE + try/except वापरले आहे.
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — प्रत्येक trade कुठून आला (कोणत्या script/interface
    # मधून) हे ओळखण्यासाठी 'source' column — Positions page वर स्पष्टपणे दाखवण्यासाठी.
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" — प्रत्येक trade
    # कुठल्या account चा आहे हे साठवण्यासाठी 'account_id' column, established Trade Monitor ला
    # योग्य adapter निवडून तोच trade बंद करता यावा म्हणून आवश्यक.
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Next-Level Exit, 1-मिनिट Instant Trader) — established
    # entry-वेळचा S/R level (established underlying किमतीचा, option strike नाही) साठवण्यासाठी —
    # established, established नंतर established favourable दिशेने established पुढचा level touch
    # झाला की established, established position "profit-booked" म्हणून बंद करून established त्याच
    # जागी established नवीन (reversal) trade घेण्यासाठी आवश्यक.
    # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (नवीन नियम-संच, Bot Dynamic SR Algo) — TSL
    # (Entry/Breakeven वर घट्ट करणारी) एकदाच (sticky) सक्रिय झाली की कायम तशीच राहते; आणि
    # 15M/30M/60M साठी "same-timeframe Next-Level-Exit" ओळखण्यासाठी entry_timeframe.
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (ROI% साठी खरी मार्जिन) — Upstox चं Margin Calculator API
    # (v2/charges/margin) आधीपासूनच फक्त LIVE trades च्या pre-trade gate साठी वापरलं जायचं (खरा
    # आकडा मिळायचाच), पण तो नंतर कुठेच साठवला जात नव्हता — ROI% साठी परत max_loss-आधारित ढोबळ
    # अंदाजच वापरला जायचा. आता trading_engine.open_multi_leg_trade() हाच खरा आकडा (PAPER trades
    # साठीही -- सध्या बहुतांश मूल्यांकन PAPER वरच होतंय) इथे साठवतो; NULL असेल (जुन्या नोंदी, किंवा
    # API कॉल अयशस्वी) तर database._compute_margin_used() आपोआप max_loss*lots*lot_size वर पडतो.
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Break even TSL activation condition calculation respect
    # to entry price, not to level price and stop loss also respect to entry price") — entry_level_price
    # (S/R zone level, उदा. 23353.1 — Next-Level-Exit साठी अजूनही तसाच वापरला जातो) आणि प्रत्यक्ष
    # entry-वेळचा spot LTP हे दोन वेगळे आकडे असू शकतात (signal-detection आणि प्रत्यक्ष order-placement
    # यामध्ये काही सेकंदांचा फरक असू शकतो). SL/TSL/Target च्या Spot% गणितासाठी आता हाच खरा entry_spot_price
    # वापरला जातो (entry_level_price ऐवजी) — नवीन, वेगळा column.
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("सध्या उघड्या trade चा TSL तात्पुरता बदलायचाय, घट्ट आणि
    # सैल दोन्ही") — manual_sl_override_pnl (NULL=कधीच override न केलेला) — set असेल तर
    # trading_engine.manage_open_trades() established सर्व per-source SL/TSL/Target शाखा वगळून
    # फक्त हाच एक (Rs P&L) threshold तपासतो — established trailing-SL च्या "कधीच सैल होत नाही" या
    # तत्त्वाला जाणीवपूर्वक अपवाद (वापरकर्त्याने स्पष्ट मागितल्याप्रमाणे), म्हणून प्रत्येक set/clear वर
    # Telegram अलर्ट अनिवार्य (trading_engine.set_manual_sl_override()/clear_manual_sl_override()).
    for col_def in ["legs_json TEXT", "strikes_summary TEXT", "mode TEXT", "trading_style TEXT", "peak_pnl REAL", "source TEXT", "account_id TEXT", "entry_level_price REAL", "tsl_activated INTEGER DEFAULT 0", "entry_timeframe TEXT", "exit_reason_detail TEXT", "entry_margin_required REAL", "entry_spot_price REAL", "manual_sl_override_pnl REAL"]:
        try:
            cursor.execute(f"ALTER TABLE live_trades ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass  # कॉलम आधीच अस्तित्वात आहे
    try:
        cursor.execute("ALTER TABLE oi_diff_snapshots ADD COLUMN underlying_price REAL")
    except sqlite3.OperationalError:
        pass  # कॉलम आधीच अस्तित्वात आहे
    for col_def in ["total_call_premium REAL", "total_put_premium REAL"]:
        try:
            cursor.execute(f"ALTER TABLE oi_diff_snapshots ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass  # कॉलम आधीच अस्तित्वात आहे

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_log (
            order_id TEXT,
            trade_id TEXT,
            symbol TEXT,
            mode TEXT,
            instrument_key TEXT,
            strike REAL,
            option_type TEXT,
            transaction_type TEXT,
            order_type TEXT,
            quantity INTEGER,
            price REAL,
            trigger_price REAL,
            status TEXT,
            tag TEXT,
            placed_at TEXT,
            fill_price REAL
        )
    """)
    # 🎓 वापरकर्त्याने Order Book वरून सापडवलेली bug — "Price" column
    # request मधला price (MARKET orders साठी नेहमी 0, कारण limit price नसतोच) दाखवायचा, प्रत्यक्ष
    # entry/exit किंमत (LTP) नाही. नवीन fill_price column मध्ये ती खरी किंमत साठवली
    # जाईल — जुन्या (आधीपासून अस्तित्वात असलेल्या) DB फाईलवरही सुरक्षितपणे लागू होण्यासाठी ALTER TABLE.
    try:
        cursor.execute("ALTER TABLE order_log ADD COLUMN fill_price REAL")
    except sqlite3.OperationalError:
        pass  # कॉलम आधीच अस्तित्वात आहे
    # 🎓 वापरकर्त्याने विचारलेला प्रश्न ("Order Log मध्ये expiry कळत नाही") सोडवण्यासाठी जोडलेला
    # नवीन column — जुन्या (आधीपासून अस्तित्वात असलेल्या) DB फाईलवरही सुरक्षितपणे लागू होण्यासाठी.
    try:
        cursor.execute("ALTER TABLE order_log ADD COLUMN expiry TEXT")
    except sqlite3.OperationalError:
        pass  # कॉलम आधीच अस्तित्वात आहे
    conn.commit()
    conn.close()

init_sqlite_db()


def log_order(order_id, trade_id, symbol, mode, order_dict, status, fill_price=None):
    """खऱ्या ब्रोकर टर्मिनलसारखं — प्रत्येक ऑर्डर (leg) चा एक कायमचा रेकॉर्ड ठेवणे, Orders टॅबसाठी.
    fill_price — प्रत्यक्ष entry/exit वेळचा LTP (MARKET orders चा request price नेहमी 0
    असतो, तो दाखवण्याऐवजी हीच खरी किंमत Order Book वर दाखवली जाते).
    🎓 वापरकर्त्याने विचारलेला प्रश्न ("Order Log मध्ये strike/expiry कळत नाही") सोडवण्यासाठी —
    आधी strike/option_type कधीच भरले जायचे नाहीत (फक्त एक अपूर्ण placeholder होता, नेहमी None
    साठवायचा). आता trading_engine.py कडून order_dict मध्येच पुढे आलेली खरी माहिती वापरली जाते."""
    try:
        instrument_key = order_dict.get("instrument_token", "")
        strike = order_dict.get("strike")
        option_type = order_dict.get("option_type")
        expiry = order_dict.get("expiry")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO order_log
               (order_id, trade_id, symbol, mode, instrument_key, strike, option_type, expiry, transaction_type,
                order_type, quantity, price, trigger_price, status, tag, placed_at, fill_price)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order_id, trade_id, symbol, mode, instrument_key, strike, option_type, expiry,
                order_dict.get("transaction_type"), order_dict.get("order_type"),
                order_dict.get("quantity"), order_dict.get("price"), order_dict.get("trigger_price"),
                status, order_dict.get("tag"), get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), fill_price,
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        _logger.exception("log_order() मध्ये अनपेक्षित चूक (silently handled)")
        pass  # ऑर्डर लॉगिंग अयशस्वी झाली तरी मुख्य ऑर्डर-प्लेसमेंट थांबता कामा नये

def log_orders_batch(order_ids, trade_id, symbol, mode, orders, status="COMPLETE", fill_prices=None):
    """एका ऑर्डर-सेटमधील प्रत्येक leg साठी log_order() कॉल करणे.
    fill_prices — ऐच्छिक {instrument_key: price} dict (established entry/exit वेळचा LTP); न दिल्यास
    established जुनं वर्तन (fill_price=None, फक्त request चा price=0 दिसेल) तसंच राहतं."""
    for i, o in enumerate(orders):
        oid = order_ids[i] if i < len(order_ids) else f"UNKNOWN-{i}"
        fill_price = (fill_prices or {}).get(o.get("instrument_token"))
        log_order(oid, trade_id, symbol, mode, o, status, fill_price=fill_price)

def save_candles_to_db(symbol, interval, df):
    if df.empty:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        ts_str = str(row["timestamp"])
        cursor.execute("""
            INSERT OR REPLACE INTO historical_candles (symbol, interval, timestamp, open, high, low, close, volume, oi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, interval, ts_str, float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), int(row.get("volume", 0)), int(row.get("oi", 0))))
    conn.commit()
    conn.close()

def load_candles_from_db(symbol, interval):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT timestamp, open, high, low, close, volume, oi FROM historical_candles WHERE symbol=? AND interval=? ORDER BY timestamp ASC"
    df = pd.read_sql_query(query, conn, params=(symbol, interval))
    conn.close()
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def check_database_health():
    """सर्व अपेक्षित DB tables अस्तित्वात आहेत का व त्यांच्यात किती रांगा आहेत ते तपासणे."""
    expected_tables = ["historical_candles", "oi_diff_snapshots", "live_trades", "order_log"]
    result = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cur.fetchall()}
        for t in expected_tables:
            if t in existing_tables:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                result[t] = {"exists": True, "rows": cur.fetchone()[0]}
            else:
                result[t] = {"exists": False, "rows": 0}
        conn.close()
        return {"status": "ok", "tables": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_data_freshness(symbol):
    """शेवटचा OI snapshot किती वेळापूर्वीचा आहे ते तपासणे — जुना असेल तर काहीतरी थांबलंय असा इशारा."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT trade_date, snapshot_time FROM oi_diff_snapshots WHERE symbol=? ORDER BY trade_date DESC, snapshot_time DESC LIMIT 1",
            (symbol,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"has_data": False}
        trade_date, snapshot_time = row
        last_dt = datetime.datetime.strptime(f"{trade_date} {snapshot_time}", "%Y-%m-%d %H:%M")
        now_ist = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
        minutes_ago = (now_ist - last_dt).total_seconds() / 60
        return {"has_data": True, "last_snapshot": f"{trade_date} {snapshot_time}", "minutes_ago": round(minutes_ago, 1)}
    except Exception as e:
        return {"has_data": False, "error": str(e)}

def get_db_backup_bytes():
    """सद्य DB फाईल bytes स्वरूपात परत करणे — डाऊनलोड बटणासाठी (Ephemeral Streamlit Cloud storage विरुद्ध संरक्षण)."""
    try:
        with open(DB_PATH, "rb") as f:
            return f.read()
    except Exception:
        _logger.exception("get_db_backup_bytes() मध्ये अनपेक्षित चूक (silently handled)")
        return None

def restore_db_from_bytes(uploaded_bytes):
    """अपलोड केलेल्या backup वरून DB बदलणे — आधी सद्य DB चा स्वतःचा सुरक्षा-backup घेऊन मगच बदलणे."""
    try:
        if os.path.exists(DB_PATH):
            safety_backup_path = DB_PATH + ".before_restore.bak"
            with open(DB_PATH, "rb") as src, open(safety_backup_path, "wb") as dst:
                dst.write(src.read())
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_bytes)
        return True, "Restore यशस्वी झाला."
    except Exception as e:
        return False, f"Restore अयशस्वी: {e}"

_AUTO_BACKUP_MARKER = os.path.join(DATA_DIR, ".last_auto_backup")

def auto_backup_due(interval_minutes=60):
    """🎓 Production-readiness सुधारणा — मॅन्युअल "Download Backup" बटणावर भरवसा ठेवण्याऐवजी, dashboard
    उघडं असताना दर ठराविक वेळाने आपोआप backup घेतलं जावं (Streamlit Cloud च्या ephemeral storage
    विरुद्ध संरक्षण). दर rerun ला उगाच अपलोड होऊ नये म्हणून एक साधा local marker — शेवटचा backup
    कधी झाला ते तपासतो. Marker फाईल स्वतःच ephemeral असली तरी हरकत नाही: container restart
    झाल्यावर ती गायब झाली तरी पुढच्या rerun लाच लगेच एक नवा backup होईल, इतकाच परिणाम."""
    try:
        if not os.path.exists(_AUTO_BACKUP_MARKER):
            return True
        with open(_AUTO_BACKUP_MARKER, "r") as f:
            last_str = f.read().strip()
        last_dt = datetime.datetime.fromisoformat(last_str)
        return (get_ist_now() - last_dt).total_seconds() >= interval_minutes * 60
    except Exception:
        _logger.exception("auto_backup_due() मध्ये अनपेक्षित चूक (silently handled)")
        return True

def mark_auto_backup_done():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(_AUTO_BACKUP_MARKER, "w") as f:
            f.write(get_ist_now().isoformat())
    except Exception:
        _logger.exception("mark_auto_backup_done() मध्ये अनपेक्षित चूक (silently handled)")
        pass  # marker लिहिता आला नाही तरी हरकत नाही — पुढच्या rerun ला पुन्हा backup प्रयत्न होईल, जास्तीत जास्त इतकाच परिणाम

def run_auto_backup_if_due(interval_minutes=60):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Crash Recovery / DB Backup, महत्त्वाच्या
    🟠 यादीतला मुद्दा) — आधी auto_backup_due()/get_db_backup_bytes()/upload_to_google_drive()/
    mark_auto_backup_done() हे चार टप्पे फक्त shared_context.py (Dashboard उघडं असतानाच) मध्ये एकत्र
    केलेले होते. तिन्ही automated bots (VPS crontab, बिनदिक्कतपणे दिवसांदिवस Dashboard न उघडताही
    चालणारे — त्यामुळे खरा VPS-crash/disk-failure धोका इथेच जास्त) कधीच स्वतःचा backup घेत नव्हते.
    आता हाच एकच, सामायिक मार्ग — Dashboard आणि तिन्ही bots दोन्हीकडून सारख्याच वर्तनासह वापरण्याजोगा.
    Google Drive configured नसेल/अपलोड अयशस्वी झालं तरी गप्प वगळलं जातं (caller कधीच अडत नाही).
    रिटर्न: खरंच नवीन backup अपलोड झालं का (bool, फक्त निदान/लॉगिंगसाठी)."""
    try:
        if not auto_backup_due(interval_minutes=interval_minutes):
            return False
        backup_bytes = get_db_backup_bytes()
        if not backup_bytes:
            return False
        ok, _msg = upload_to_google_drive(
            backup_bytes, f"amw_a1_autobackup_{get_ist_now().strftime('%Y%m%d_%H%M')}.db",
            mime_type="application/octet-stream",
        )
        if ok:
            mark_auto_backup_done()
        return ok
    except Exception:
        _logger.exception("run_auto_backup_if_due() मध्ये अनपेक्षित चूक (silently handled)")
        return False

def get_todays_realized_pnl(symbol, trading_mode="LIVE"):
    """आजच्या दिवसात बंद झालेल्या (CLOSED) ट्रेड्सचा एकूण वास्तविक नफा/तोटा (डेली सर्किट ब्रेकरसाठी).
    PAPER आणि LIVE ट्रेड्स स्वतंत्रपणे मोजले जातात, जेणेकरून Paper टेस्टिंगमुळे Live सर्किट ब्रेकर
    (किंवा उलट) चुकीने ट्रिगर होणार नाही.

    🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — P&L बेरीज आधी `trade_date`
    (entry ची तारीख, trading_engine.py:415) वरून फिल्टर व्हायची, पण हे system मुद्दामच trades रात्रभर
    carry-forward करतं (3:10pm "अपुरा नफा" check — trading_engine.py). सोमवारी उघडलेली, मंगळवारी
    सकाळी मोठ्या तोट्यात बंद झालेली trade — मंगळवारच्या (जेव्हा खरा तोटा झाला त्याच दिवशीच्या) बेरजेत
    कधीच धरलीच जायची नाही. आता realized_pnl ची बेरीज exit_time (प्रत्यक्ष तोटा/नफा कधी *realize*
    झाला, त्या तारखेवरून) वरून — trade-count मात्र मुद्दामच अजूनही trade_date (entry) वरूनच, कारण तो
    "आज किती नवीन trades उघडले" (entry-दर मर्यादा) मोजतो, वेगळाच उद्देश."""
    today_str = get_ist_today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(realized_pnl),0) FROM live_trades WHERE symbol=? AND status='CLOSED' AND COALESCE(mode,'LIVE')=? AND substr(exit_time,1,10)=?",
        (symbol, trading_mode, today_str),
    )
    total_pnl = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM live_trades WHERE symbol=? AND trade_date=? AND COALESCE(mode,'LIVE')=?",
        (symbol, today_str, trading_mode),
    )
    total_trades_today = cur.fetchone()[0]
    conn.close()
    return total_pnl, total_trades_today

def get_todays_live_total_pnl_and_count():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit,
    गंभीर यादीतला चौथा मुद्दा) — आजचा एकूण LIVE realized P&L + trade count, सर्व symbols आणि सर्व
    strategies/sources मिळून (get_todays_realized_pnl() च्या उलट, जो एकाच symbol+mode पुरता मर्यादित
    आहे) — तिन्ही bots + Dashboard यांना समान, संपूर्ण-खात्यासाठीचं एकत्रित संरक्षण देण्यासाठी.

    🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — get_todays_realized_pnl()
    सारखीच — P&L बेरीज आता exit_time वरून (कधी तोटा/नफा *realize* झाला), trade-count (entry-दर
    मर्यादेसाठी) अजूनही trade_date (entry) वरून. याआधी carry-forward झालेली, दुसऱ्या दिवशी मोठ्या
    तोट्यात बंद झालेली trade त्या दिवशीच्या kill-switch तपासणीत कधीच दिसायचीच नाही — म्हणजे नेमक्या
    सर्वात जास्त गरज असलेल्या दिवशीच Kill Switch गप्प बसायचा."""
    today_str = get_ist_today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(realized_pnl),0) FROM live_trades WHERE status='CLOSED' AND COALESCE(mode,'LIVE')='LIVE' AND substr(exit_time,1,10)=?",
        (today_str,),
    )
    total_pnl = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM live_trades WHERE trade_date=? AND COALESCE(mode,'LIVE')='LIVE'",
        (today_str,),
    )
    total_trades_today = cur.fetchone()[0]
    conn.close()
    return total_pnl, total_trades_today


def get_todays_mcx_live_pnl_and_count():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (MCX LIVE करण्याआधी — "MCX साठी वेगळा Kill Switch/capital
    cap") — आजचा MCX (source='mcx_futures', 5 commodities मिळून) LIVE realized P&L आणि सध्या उघडी
    असलेल्या LIVE positions ची संख्या — वरच्या get_todays_live_total_pnl_and_count() सारखंच (exit_time
    वरून P&L बेरीज), पण फक्त MCX पुरतं मर्यादित — check_mcx_kill_switch() साठी."""
    today_str = get_ist_today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(realized_pnl),0) FROM live_trades WHERE status='CLOSED' AND COALESCE(mode,'LIVE')='LIVE' "
        "AND source='mcx_futures' AND substr(exit_time,1,10)=?",
        (today_str,),
    )
    total_pnl = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM live_trades WHERE status='OPEN' AND COALESCE(mode,'LIVE')='LIVE' AND source='mcx_futures'",
    )
    open_positions = cur.fetchone()[0]
    conn.close()
    return total_pnl, open_positions


def get_unverified_reconciled_trades_today_count():
    """🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — reconcile_open_trades_with_broker()
    ने (trading_engine.py) externally बंद झालेली LIVE position CLOSED मार्क करताना realized_pnl कधीच
    साठवत नाही (ते function फक्त वाचतं, कुठलाही LTP मागवत नाही — त्यामुळे नेमका नफा/तोटा तिथे कळणंच
    शक्य नाही). त्यामुळे COALESCE(SUM(realized_pnl),0) मध्ये असे NULL रो कायमच वगळले जातात — म्हणजे
    वापरकर्त्याने स्वतः Upstox app मधून एखादी मोठ्या तोट्यातली position बंद केली (किंवा reconciliation
    च्या आधीच्या bug मुळे चुकून बंद मार्क झालेली position), तरी kill-switch ला तो तोटा कधीच दिसायचा
    नाही — "आजचा तोटा ₹0" असं चुकीने वाटून bots नवीन LIVE trades घेतच राहायचे. आता असे unverified
    (realized_pnl अजून माहीत नसलेले) trades असल्यास kill-switch ने वेगळ्या, स्पष्ट कारणासह नवीन LIVE
    trades थांबवावेत (fail-safe — अंदाजे आकडा गृहीत धरण्यापेक्षा नवीन trading थांबवणं सुरक्षित)."""
    today_str = get_ist_today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM live_trades WHERE status='CLOSED' AND COALESCE(mode,'LIVE')='LIVE' "
        "AND exit_reason='RECONCILED_EXTERNAL_CLOSE' AND realized_pnl IS NULL AND substr(exit_time,1,10)=?",
        (today_str,),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_open_trades_with_entry_level(symbol, source):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Next-Level Exit) — established त्याच symbol+source
    साठी established OPEN असलेले trades, established त्यांच्या entry_level_price सकट — established
    "favourable दिशेने established पुढचा level touch झाला का" established तपासण्यासाठी.
    रिटर्न: [{"trade_id":.., "strategy":.., "entry_level_price":..}, ...] (established entry_level_price
    established None असलेले established वगळलेले).
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """SELECT trade_id, strategy, entry_level_price FROM live_trades
           WHERE symbol=? AND source=? AND status='OPEN' AND entry_level_price IS NOT NULL""",
        (symbol, source),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"trade_id": r[0], "strategy": r[1], "entry_level_price": r[2]} for r in rows]


def has_open_trade_from_source(symbol, source):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit Dynamic S/R) — established त्याच source
    (उदा. 'dynamic_sr_instant') कडून established symbol साठी सध्या कुठलाही OPEN trade आहे का —
    established zone ला दुसऱ्यांदा hit होऊनही, आधीची position बंद होईपर्यंत नवीन trade न घेण्यासाठी.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM live_trades WHERE symbol=? AND source=? AND status='OPEN'",
        (symbol, source),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count > 0


def get_open_trades_by_other_sources(symbol, exclude_source):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Cross-Strategy Conflict Check — फक्त अलर्ट, block नाही) —
    दिलेल्या symbol वर सध्या OPEN असलेले, exclude_source (सध्या नवीन trade घेणारी strategy) व्यतिरिक्त
    इतर कुठल्याही strategy/source कडून आलेले trades — जेणेकरून दोन वेगवेगळ्या bots नकळत एकाच underlying
    वर (कदाचित विरुद्ध दिशेने) एकाच वेळी trade घेत असतील, तर कळवता येईल.
    रिटर्न: [{"source":.., "strategy":.., "trade_id":..}, ...]"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT source, strategy, trade_id FROM live_trades WHERE symbol=? AND status='OPEN' AND COALESCE(source,'')!=?",
        (symbol, exclude_source or ""),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"source": r[0], "strategy": r[1], "trade_id": r[2]} for r in rows]


def get_live_positions_with_mtm(access_token, symbol, mode_filter=None):
    """
    सर्व OPEN पोझिशन्ससाठी सद्य LTP आणून खरा (real) MTM P&L काढणे — Positions टॅबसाठी,
    अगदी ब्रोकर टर्मिनलसारखं (Entry, LTP, Qty, MTM ₹, MTM %).
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = """SELECT trade_id, mode, trading_style, strategy, legs_json, lots, lot_size, net_credit,
                      max_profit, max_loss, entry_time, strikes_summary, peak_pnl, source, manual_sl_override_pnl
               FROM live_trades WHERE symbol=? AND status='OPEN'"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    query += " ORDER BY entry_time DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()

    all_keys = set()
    parsed = []
    for r in rows:
        legs = json.loads(r[4]) if r[4] else []
        for leg in legs:
            all_keys.add(leg["instrument_key"])
        parsed.append((r, legs))

    ltp_map = fetch_ltp_map(access_token, list(all_keys)) if all_keys else {}

    records = []
    for (trade_id, mode, style, strategy, legs_json, lots, lot_size, net_credit, max_profit, max_loss, entry_time, strikes_summary, peak_pnl, source, manual_sl_override_pnl), legs in parsed:
        mtm, mtm_pct = None, None
        if legs:
            current_ltps = {leg["instrument_key"]: ltp_map.get(leg["instrument_key"]) for leg in legs}
            if all(v is not None for v in current_ltps.values()):
                cost_to_close_now = sum(
                    current_ltps[leg["instrument_key"]] * (1 if leg["transaction_type"] == "SELL" else -1)
                    for leg in legs
                )
                mtm = round((net_credit - cost_to_close_now) * lots * lot_size, 2)
                # 🎓 वापरकर्त्याने Positions tab वरून सापडवलेली bug (Regression) — मागच्या फिक्समध्ये
                # established max_loss/max_profit column आता per-share (net_credit प्रमाणेच) साठवले
                # जातात — पण इथे mtm (established TOTAL, lots*lot_size ने आधीच गुणलेला) त्या
                # per-share max_loss/max_profit शीच थेट भागला जायचा — scale जुळत नव्हती, त्यामुळे
                # MTM% भलताच चुकीचा (फुगलेला) यायचा. आता established दोन्ही बाजू सुसंगत (TOTAL/TOTAL).
                if max_loss:
                    mtm_pct = (
                        round((mtm / (max_loss * lots * lot_size)) * 100, 1) if mtm < 0
                        else round((mtm / (max_profit * lots * lot_size)) * 100, 1) if max_profit else None
                    )
        # 🎓 Portfolio-level Risk Dashboard साठी — max_loss/net_credit/Direction आधीच query मध्ये
        # fetch होत होते, पण output मध्ये नव्हते. जोडलं (backward-compatible, फक्त नवीन columns).
        direction = "BULLISH" if strategy == "BULL_PUT_SPREAD" else ("BEARISH" if strategy == "BEAR_CALL_SPREAD" else "NEUTRAL")
        records.append({
            "Trade ID": trade_id, "Mode": mode or "LIVE", "Style": style or "INTRADAY",
            "Strategy": strategy, "Direction": direction, "Legs": strikes_summary, "Lots": lots,
            "Source": source or "DASHBOARD",  # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — trade
            # नेमका कुठून आला (कोणत्या script/interface) — जुन्या नोंदींना source नसतो, त्यांना
            # "DASHBOARD" (interactive) असं मानणे — कारण unattended scripts येण्याआधीचे सर्व trades
            # Dashboard मधूनच यायचे.
            "Entry Time": entry_time, "MTM (Rs)": mtm, "MTM (%)": mtm_pct,
            "Max Loss (Rs)": round(max_loss * lots * lot_size, 2) if max_loss else None,
            "Net Credit (Rs)": round(net_credit * lots * lot_size, 2) if net_credit else None,
            "Peak P&L (Rs)": round(peak_pnl, 2) if peak_pnl is not None else None,
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("TSL तात्पुरता बदलायचाय") — सेट असेल तरच दिसतो,
            # जेणेकरून override सक्रिय असलेली trade Positions टेबलमध्येच लगेच वेगळी दिसेल (विसरता
            # कामा नये — विशेषतः सैल केलेली असेल तर).
            "Manual SL Override (Rs)": round(manual_sl_override_pnl, 2) if manual_sl_override_pnl is not None else None,
        })
    return pd.DataFrame(records)


def check_position_delta_health(strategy, net_delta, iron_condor_threshold=15, spread_danger_threshold=35):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Delta चा अर्थ रणनीतीनुसार वेगळा लावला जातो:
    - Iron Condor/Butterfly (दिशाहीन): |Delta| मोठा -> एक बाजू "टेस्ट" झालीय, Adjustment/Roll विचार करा
    - Credit Spread (दिशात्मक): Delta उलट दिशेने -> मूळ थीसिस अपयशी (गंभीर); बरोबर दिशेतच पण खूप मोठा ->
      Short leg खोलवर ITM जातोय, जोखीम वाढतेय (सौम्य इशारा)
    रिटर्न: (emoji, संदेश)
    """
    if strategy in ("IRON_CONDOR", "IRON_BUTTERFLY"):
        if abs(net_delta) > iron_condor_threshold:
            side = "वरची (Call)" if net_delta < 0 else "खालची (Put)"
            return "⚠️", f"Delta={net_delta:.1f} (मर्यादा ±{iron_condor_threshold}) — {side} बाजू टेस्ट झालीय, Adjustment/Roll विचार करा"
        return "✅", f"Delta={net_delta:.1f} — संतुलित (neutral), ठीक आहे"

    if strategy == "BULL_PUT_SPREAD":
        if net_delta < 0:
            return "🔴", f"Delta={net_delta:.1f} — उलट दिशेने! मूळ Bullish थीसिस अपयशी होतोय"
        if net_delta > spread_danger_threshold:
            return "⚠️", f"Delta={net_delta:.1f} (मर्यादा {spread_danger_threshold}) — Short leg खोलवर ITM जातोय, जोखीम वाढतेय"
        return "✅", f"Delta={net_delta:.1f} — अपेक्षित दिशेतच, ठीक आहे"

    if strategy == "BEAR_CALL_SPREAD":
        if net_delta > 0:
            return "🔴", f"Delta={net_delta:.1f} — उलट दिशेने! मूळ Bearish थीसिस अपयशी होतोय"
        if abs(net_delta) > spread_danger_threshold:
            return "⚠️", f"Delta={net_delta:.1f} (मर्यादा -{spread_danger_threshold}) — Short leg खोलवर ITM जातोय, जोखीम वाढतेय"
        return "✅", f"Delta={net_delta:.1f} — अपेक्षित दिशेतच, ठीक आहे"

    return "ℹ️", f"Delta={net_delta:.1f} — या रणनीतीसाठी विशिष्ट तपासणी नाही"


def compute_per_position_greeks(access_token, symbol, mode_filter=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — प्रत्येक उघड्या position साठी स्वतंत्रपणे Greeks +
    रणनीती-आधारित Delta Health Check (compute_portfolio_greeks च्या एकत्रित/aggregate आकड्यांऐवजी,
    इथे प्रत्येक Trade ID साठी वेगळे परिणाम मिळतात — Iron Condor/Spread दोन्हीसाठी उपयुक्त).
    रिटर्न: [{"trade_id":.., "strategy":.., "net_delta":.., "net_theta":.., "health_emoji":.., "health_message":..}, ...]
    """
    import upstox_api
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = "SELECT trade_id, strategy, legs_json, lots, lot_size FROM live_trades WHERE symbol=? AND status='OPEN'"
    params = [symbol]
    if mode_filter:
        query += " AND mode=?"
        params.append(mode_filter)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return []

    all_keys = set()
    parsed = []
    for trade_id, strategy, legs_json, lots, lot_size in rows:
        try:
            legs = json.loads(legs_json)
        except (json.JSONDecodeError, TypeError):
            continue
        parsed.append((trade_id, strategy, legs, lots, lot_size))
        for leg in legs:
            if leg.get("instrument_key"):
                all_keys.add(leg["instrument_key"])

    greeks_map = upstox_api.fetch_option_greeks(access_token, list(all_keys))

    results = []
    for trade_id, strategy, legs, lots, lot_size in parsed:
        qty = lots * lot_size
        net_delta = net_gamma = net_theta = net_vega = 0.0
        for leg in legs:
            g = greeks_map.get(leg.get("instrument_key"))
            if not g:
                continue
            sign = -1 if leg.get("transaction_type") == "SELL" else 1
            net_delta += sign * g.get("delta", 0.0) * qty
            net_gamma += sign * g.get("gamma", 0.0) * qty
            net_theta += sign * g.get("theta", 0.0) * qty
            net_vega += sign * g.get("vega", 0.0) * qty
        health_emoji, health_message = check_position_delta_health(strategy, net_delta)
        results.append({
            "trade_id": trade_id, "strategy": strategy,
            "net_delta": round(net_delta, 2), "net_gamma": round(net_gamma, 4),
            "net_theta": round(net_theta, 2), "net_vega": round(net_vega, 2),
            "health_emoji": health_emoji, "health_message": health_message,
        })
    return results


def compute_portfolio_greeks(access_token, symbol, mode_filter=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — सर्व उघड्या positions च्या legs साठी ताजे
    Delta/Gamma/Theta/Vega मिळवून, संपूर्ण Portfolio ची निव्वळ (net) जोखीम काढणे — प्रत्येक leg
    SELL (शॉर्ट) असेल तर उलट चिन्हाने (negative), BUY (लाँग) असेल तर तशाच चिन्हाने (positive) मोजली
    जाते — जागतिक prop trading firms जसं सतत करतात तसंच.
    रिटर्न: {"net_delta":.., "net_gamma":.., "net_theta":.., "net_vega":.., "positions_included":N}
    Greeks मिळाल्या नाहीत (API अपयशी, किंवा उघडी position नाही) तर सर्व शून्य (क्रॅश होत नाही).
    """
    import upstox_api
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = "SELECT legs_json, lots, lot_size FROM live_trades WHERE symbol=? AND status='OPEN'"
    params = [symbol]
    if mode_filter:
        query += " AND mode=?"
        params.append(mode_filter)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {"net_delta": 0.0, "net_gamma": 0.0, "net_theta": 0.0, "net_vega": 0.0, "positions_included": 0}

    all_positions = []
    all_instrument_keys = set()
    for legs_json, lots, lot_size in rows:
        try:
            legs = json.loads(legs_json)
        except (json.JSONDecodeError, TypeError):
            continue
        all_positions.append({"legs": legs, "lots": lots, "lot_size": lot_size})
        for leg in legs:
            if leg.get("instrument_key"):
                all_instrument_keys.add(leg["instrument_key"])

    greeks_map = upstox_api.fetch_option_greeks(access_token, list(all_instrument_keys))

    net_delta = net_gamma = net_theta = net_vega = 0.0
    for pos in all_positions:
        qty = pos["lots"] * pos["lot_size"]
        for leg in pos["legs"]:
            g = greeks_map.get(leg.get("instrument_key"))
            if not g:
                continue
            sign = -1 if leg.get("transaction_type") == "SELL" else 1
            net_delta += sign * g.get("delta", 0.0) * qty
            net_gamma += sign * g.get("gamma", 0.0) * qty
            net_theta += sign * g.get("theta", 0.0) * qty
            net_vega += sign * g.get("vega", 0.0) * qty

    return {
        "net_delta": round(net_delta, 2), "net_gamma": round(net_gamma, 4),
        "net_theta": round(net_theta, 2), "net_vega": round(net_vega, 2),
        "positions_included": len(all_positions),
    }


def compute_portfolio_risk_summary(positions_df):
    """
    सर्व उघड्या positions एकत्र घेऊन — एकूण जोखीम (worst-case), दिशा-केंद्रीकरण (सर्व एकाच दिशेने असतील
    तर एकत्रित जोखीम जास्त), आणि एकूण collected credit काढणे. Portfolio Risk Dashboard साठी.
    """
    if positions_df is None or positions_df.empty:
        return {"total_positions": 0, "total_max_loss": 0, "total_net_credit": 0, "total_mtm": 0,
                "bullish_count": 0, "bearish_count": 0, "neutral_count": 0, "concentration_warning": None}

    total_max_loss = positions_df["Max Loss (Rs)"].dropna().sum() if "Max Loss (Rs)" in positions_df else 0
    total_net_credit = positions_df["Net Credit (Rs)"].dropna().sum() if "Net Credit (Rs)" in positions_df else 0
    total_mtm = positions_df["MTM (Rs)"].dropna().sum()

    direction_counts = positions_df["Direction"].value_counts().to_dict() if "Direction" in positions_df else {}
    bullish_count = direction_counts.get("BULLISH", 0)
    bearish_count = direction_counts.get("BEARISH", 0)
    neutral_count = direction_counts.get("NEUTRAL", 0)
    total_directional = bullish_count + bearish_count

    concentration_warning = None
    if total_directional >= 2 and (bullish_count == total_directional or bearish_count == total_directional):
        one_sided = "BULLISH" if bullish_count == total_directional else "BEARISH"
        concentration_warning = (
            f"⚠️ सर्व {total_directional} दिशात्मक positions {one_sided} आहेत — एकाच मोठ्या उलट हालचालीने "
            f"सर्व एकत्र तोट्यात जाऊ शकतात (correlated risk, विविधता नाही)."
        )

    return {
        "total_positions": len(positions_df), "total_max_loss": round(total_max_loss, 2),
        "total_net_credit": round(total_net_credit, 2), "total_mtm": round(total_mtm, 2),
        "bullish_count": bullish_count, "bearish_count": bearish_count, "neutral_count": neutral_count,
        "concentration_warning": concentration_warning,
    }

def _compute_margin_used(df):
    """ROI% साठी "वापरलेली मार्जिन" — प्रत्यक्ष *एकाच वेळी उघडे* असलेल्या trades च्या
    (max_loss*lots*lot_size) बेरजेचा सर्वात मोठा (peak concurrent) आकडा — साधी सर्व trades ची बेरीज
    नाही.

    🎓 वापरकर्त्याने निदर्शनास आणलेली, बरोबर तक्रार — आधी सर्व trades चा margin (max_loss*lots*
    lot_size) निव्वळ बेरीज व्हायचा, जणू सर्व एकाच वेळी उघडे होते. पण established bots (1m_instant,
    dynamic_sr_instant_trader इ.) एका वेळी फक्त एकच trade उघडतात (नवीन entry आधीचा बंद झाल्याशिवाय
    घेतच नाहीत) — त्यामुळे तेच भांडवल वारंवार पुन्हा-पुन्हा वापरलं जातं, सर्व वेगळं-वेगळं भांडवल नाही.
    साधी बेरीज त्यामुळे "वापरलेली मार्जिन" प्रत्यक्षापेक्षा कितीतरी पट जास्त दाखवायची (उदा. २० trades
    → वीसपट भांडवल दाखवायचं), आणि ROI% खोटाच खूप लहान (जवळपास शून्य) दिसायचा.

    आता entry_time/exit_time वरून sweep-line (classic "meeting rooms") पद्धतीने — प्रत्येक क्षणी
    प्रत्यक्ष उघडे असलेल्या trades चीच बेरीज करून, त्यातला सर्वात मोठा (peak) आकडा "margin_used"
    मानला जातो. निव्वळ sequential (कधीच overlap न होणाऱ्या) trades साठी हे आपोआप फक्त सर्वात मोठ्या
    एका trade इतकंच येतं (बरोबर, कारण तेच भांडवल पुन्हा-पुन्हा वापरलं गेलं). वेगवेगळ्या strategies/
    accounts वर खरंच एकाच वेळी अनेक trades उघडे असतील, तर ते इथे बरोबर एकत्र मोजले जातात (overlap
    प्रत्यक्ष असेल तरच).

    entry_time/exit_time उपलब्ध नसलेल्या (जुन्या/अपूर्ण) नोंदी — त्यांचा margin peak मध्ये netting
    न करता वेगळा जोडला जातो (सुरक्षित, worst-case गृहीतक — जुनं वर्तनच त्यांच्यापुरतं कायम).

    🎓 वापरकर्त्याने मागितलेली सुधारणा (खरी मार्जिन, अंदाज नाही) — प्रत्येक trade वर आता
    entry_margin_required (Upstox च्या Margin Calculator API कडून, trading_engine.
    open_multi_leg_trade() ने trade उघडतानाच साठवलेला खरा आकडा — SPAN+Exposure, hedge-फायद्यासकट)
    उपलब्ध असल्यास तोच वापरला जातो — max_loss*lots*lot_size (ढोबळ worst-case अंदाज, हेज्ड
    credit spread साठी प्रत्यक्ष लागणाऱ्या मार्जिनपेक्षा बरंच जास्त असू शकतो) फक्त जुन्या नोंदींसाठी
    (entry_margin_required NULL — त्या वेळी हे column नव्हतंच, किंवा API कॉल अयशस्वी झाला होता)
    fallback म्हणून.
    """
    max_loss = pd.to_numeric(df["max_loss"], errors="coerce").abs()
    lots = pd.to_numeric(df["lots"], errors="coerce")
    lot_size = pd.to_numeric(df["lot_size"], errors="coerce")
    estimated_margin = max_loss * lots * lot_size
    if "entry_margin_required" in df.columns:
        real_margin = pd.to_numeric(df["entry_margin_required"], errors="coerce")
        trade_margin = real_margin.where(real_margin.notna() & (real_margin > 0), estimated_margin)
    else:
        trade_margin = estimated_margin

    entry_time = pd.to_datetime(df["entry_time"], errors="coerce") if "entry_time" in df.columns else pd.Series(pd.NaT, index=df.index)
    exit_time = pd.to_datetime(df["exit_time"], errors="coerce") if "exit_time" in df.columns else pd.Series(pd.NaT, index=df.index)

    has_margin = trade_margin.notna() & (trade_margin > 0)
    timed = has_margin & entry_time.notna() & exit_time.notna() & (exit_time >= entry_time)
    untimed_margin = trade_margin[has_margin & ~timed].sum()

    if not timed.any():
        return untimed_margin

    # sweep-line: प्रत्येक trade चे दोन events -- entry ला +margin, exit ला -margin. वेळेनुसार
    # क्रमवारी लावून cumulative sum चा कमाल आकडा हाच "कधीही एकाचवेळी जास्तीत जास्त किती भांडवल
    # वापरलं गेलं". बरोब्बर त्याच क्षणी एक trade बंद व दुसरा सुरू झाला, तर आधी "बंद" मोजून (order=0),
    # मग "सुरू" (order=1) -- खरंच sequential trades ला उगाच overlap समजलं जाऊ नये म्हणून.
    events = pd.concat([
        pd.DataFrame({"time": exit_time[timed], "delta": -trade_margin[timed], "order": 0}),
        pd.DataFrame({"time": entry_time[timed], "delta": trade_margin[timed], "order": 1}),
    ], ignore_index=True).sort_values(["time", "order"])
    peak = events["delta"].cumsum().max()
    return float(peak) + untimed_margin


def get_performance_summary(symbol, mode_filter=None, style_filter=None, start_date=None, end_date=None):
    """
    बंद झालेल्या (CLOSED) ट्रेड्सवरून Win Rate, Avg P&L, Profit Factor, ROI% वगैरे मूळ कामगिरी आकडे
    काढणे. start_date/end_date दिले (उदा. आजची तारीख दोन्हीसाठी) तर फक्त त्या exit_time रेंजमधले
    trades मोजले जातात.

    🎓 वापरकर्त्याने मागितलेली सुधारणा (Winning Rate — फक्त शुद्ध SL/Target) — "win_rate" आता फक्त
    शुद्ध SL किंवा शुद्ध TARGET exit_reason असलेल्या trades वरून (दोन्ही numerator आणि denominator) —
    Trailing SL/Breakeven/EOD/Manual/इ. सर्व वगळून. जुनं (सर्व closed trades, P&L-चिन्ह आधारित) win
    rate "win_rate_all_exits" म्हणून संदर्भासाठी अजूनही उपलब्ध.
    🎓 वापरकर्त्याने मागितलेली सुधारणा (ROI — मार्जिन-आधारित) — प्रत्यक्ष broker margin प्रत्येक trade
    सोबत साठवलेला नाही, त्यामुळे max_loss * lots * lot_size (Dashboard च्या Pre-Trade Margin
    Check मध्ये आधीपासूनच वापरलेला, सुरक्षित worst-case अंदाज) हीच "वापरलेली
    मार्जिन" मानून roi_pct = एकूण realized P&L / एकूण मार्जिन.
    """
    conn = sqlite3.connect(DB_PATH)
    query = ("SELECT realized_pnl, exit_reason, max_loss, lots, lot_size, entry_time, exit_time, entry_margin_required FROM live_trades "
             "WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL")
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if style_filter:
        query += " AND COALESCE(trading_style,'INTRADAY')=?"
        params.append(style_filter)
    if start_date:
        query += " AND date(exit_time) >= ?"
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        query += " AND date(exit_time) <= ?"
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return {"total_trades": 0}

    pnls = df["realized_pnl"]
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    sl_target_df = df[df["exit_reason"].isin(WIN_RATE_COUNTED_REASONS)]
    sl_target_wins = sl_target_df[sl_target_df["exit_reason"].isin(WIN_RATE_TARGET_REASONS)]
    sl_target_count = len(sl_target_df)

    margin_used = _compute_margin_used(df)

    return {
        "total_trades": len(pnls),
        "win_count": len(wins), "loss_count": len(losses),
        "win_rate": round(len(sl_target_wins) / sl_target_count * 100, 1) if sl_target_count else None,
        "sl_target_trade_count": sl_target_count,
        "win_rate_all_exits": round(len(wins) / len(pnls) * 100, 1) if len(pnls) else None,
        "total_pnl": round(pnls.sum(), 2),
        "avg_pnl": round(pnls.mean(), 2),
        "avg_win": round(wins.mean(), 2) if len(wins) else None,
        "avg_loss": round(losses.mean(), 2) if len(losses) else None,
        "best_trade": round(pnls.max(), 2),
        "worst_trade": round(pnls.min(), 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "margin_used": round(margin_used, 2),
        "roi_pct": round(pnls.sum() / margin_used * 100, 2) if margin_used > 0 else None,
    }

def get_equity_curve_data(symbol, mode_filter=None, style_filter=None, start_date=None, end_date=None):
    """वेळेनुसार संचयी (cumulative) वास्तविक P&L — Equity Curve चार्टसाठी. start_date दिली तर
    त्याच्याआधीचे trades curve मध्ये मोजले जात नाहीत (cumulative sum त्याच तारखेपासूनच सुरू होतो)."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT exit_time, realized_pnl FROM live_trades
               WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL AND exit_time IS NOT NULL"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if style_filter:
        query += " AND COALESCE(trading_style,'INTRADAY')=?"
        params.append(style_filter)
    if start_date:
        query += " AND date(exit_time) >= ?"
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        query += " AND date(exit_time) <= ?"
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    query += " ORDER BY exit_time ASC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return df
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df["cumulative_pnl"] = df["realized_pnl"].cumsum()
    return df

def _group_win_rate_and_roi(sub):
    """एका group च्या (DataFrame) उप-संचावरून — नवीन (SL/Target-फक्त) Win Rate, जुना (सर्व exits,
    संदर्भासाठी) Win Rate, आणि margin-आधारित ROI% — get_performance_by_group()/
    get_performance_by_two_groups() दोन्हीत सामायिक वापरण्यासाठी (duplicate टाळण्यासाठी)."""
    wins = sub[sub["realized_pnl"] > 0]
    sl_target_sub = sub[sub["exit_reason"].isin(WIN_RATE_COUNTED_REASONS)]
    sl_target_wins = sl_target_sub[sl_target_sub["exit_reason"].isin(WIN_RATE_TARGET_REASONS)]
    sl_target_count = len(sl_target_sub)
    margin_used = _compute_margin_used(sub)
    total_pnl = sub["realized_pnl"].sum()
    return {
        "Win Rate %": round(len(sl_target_wins) / sl_target_count * 100, 1) if sl_target_count else None,
        "SL/Target Trades": sl_target_count,
        "Win Rate % (All Exits)": round(len(wins) / len(sub) * 100, 1),
        "ROI %": round(total_pnl / margin_used * 100, 2) if margin_used > 0 else None,
    }


# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("credit spread आणि naked option buy चं विश्लेषण/निष्कर्ष वेगळे
# हवेत, एकत्र मिसळू नका") — प्रत्येक Dynamic SR bot (1m_instant/classic_sr_reversal/15m_dynamic_sr)
# credit spread ट्रेड्स (BULL_PUT_SPREAD/BEAR_CALL_SPREAD -- फक्त दिशा वेगळी, रचना एकच) आणि naked
# option ट्रेड्स (NAKED_CALL/NAKED_PUT) दोन्ही, एकाच `source` खाली, `strategy` स्तंभातल्या वेगळ्या
# कोडने साठवतो. get_performance_by_group()/get_exit_reason_breakdown() ला थेट "strategy" column
# नाव दिलं, तर हे ६ कच्चे कोड वेगळे-वेगळे दिसतात (राजकीय गोंधळ) -- ही SQL अभिव्यक्ती त्याऐवजी दिली,
# तर नेमके हे २ अर्थपूर्ण गट (Iron Condor/Iron Butterfly जसेच्या तसे) मिळतात. दोन्ही फंक्शन्स
# group_col ला थेट SQL अभिव्यक्ती म्हणून वापरतात (COALESCE(...) च्या आत टाकतात) -- म्हणूनच हे शक्य
# आहे, कुठलाही स्कीमा बदल न करता (हार्डकोडेड, कधीच वापरकर्ता-इनपुट नाही -- SQL injection चा प्रश्नच नाही).
OPTION_STRUCTURE_GROUP_SQL = (
    "CASE WHEN strategy IN ('BULL_PUT_SPREAD', 'BEAR_CALL_SPREAD') THEN 'CREDIT_SPREAD' "
    "WHEN strategy IN ('NAKED_CALL', 'NAKED_PUT') THEN 'NAKED_OPTION' "
    "ELSE strategy END"
)


def get_live_vs_shadow_paper_pairs(symbol, start_date, end_date):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (LIVE+PAPER शॅडो मोड — Performance Report मध्ये slippage
    दिसावं) — LIVE+PAPER trading mode मध्ये प्रत्येक खऱ्या LIVE trade सोबत trading_engine.
    open_multi_leg_trade() कडूनच, त्याच सिग्नलवर (same source/strategy/entry_level_price/
    entry_timeframe), जवळपास त्याच क्षणी एक शॅडो PAPER trade उघडला जातो. इथे असे जोडे (LIVE trade
    ला, त्याच group मधल्या, entry_time 5 मिनिटांच्या आत असलेल्या सर्वात जवळच्या PAPER trade शी,
    greedy nearest-match — प्रत्येक PAPER trade फक्त एकदाच वापरला जातो) शोधून, प्रत्यक्ष LIVE
    execution आणि शुद्ध PAPER सिम्युलेशन मधला फरक (entry premium व P&L, दोन्हीतला "slippage") मोजते.
    केवळ LIVE mode मध्ये (शॅडो PAPER शिवाय) घेतलेल्या trades साठी कधीच जोडी सापडणार नाही — रिकामा
    DataFrame, म्हणजे हे फीचर आपोआप फक्त LIVE+PAPER मोड प्रत्यक्ष वापरला तरच काही दाखवतं.

    रिटर्न: DataFrame — Entry Date/Strategy/Entry Level/Timeframe/LIVE Net Credit/PAPER Net Credit/
    Entry Slippage (Rs)/LIVE P&L/PAPER P&L/P&L Slippage (Rs) (जोडी न सापडल्यास रिकामा, हेच स्तंभ)."""
    cols = [
        "Entry Date", "Strategy", "Entry Level", "Timeframe", "LIVE Net Credit", "PAPER Net Credit",
        "Entry Slippage (Rs)", "LIVE P&L", "PAPER P&L", "P&L Slippage (Rs)",
    ]
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT trade_id, source, strategy, entry_level_price, entry_timeframe, entry_time,
                      net_credit, realized_pnl, mode
               FROM live_trades
               WHERE symbol=? AND status='CLOSED' AND mode IN ('LIVE','PAPER')
                     AND entry_level_price IS NOT NULL AND entry_time IS NOT NULL
                     AND date(entry_time) >= ? AND date(entry_time) <= ?"""
    params = [
        symbol, start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date,
        end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date,
    ]
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=cols)

    df["entry_time"] = pd.to_datetime(df["entry_time"])
    live_df = df[df["mode"] == "LIVE"].sort_values("entry_time")
    paper_df = df[df["mode"] == "PAPER"]

    rows = []
    used_paper_ids = set()
    for _, live_row in live_df.iterrows():
        candidates = paper_df[
            (paper_df["source"] == live_row["source"])
            & (paper_df["strategy"] == live_row["strategy"])
            & (paper_df["entry_level_price"] == live_row["entry_level_price"])
            & (paper_df["entry_timeframe"] == live_row["entry_timeframe"])
            & (~paper_df["trade_id"].isin(used_paper_ids))
        ]
        if candidates.empty:
            continue
        time_diff = (candidates["entry_time"] - live_row["entry_time"]).abs()
        candidates = candidates[time_diff <= pd.Timedelta(minutes=5)]
        if candidates.empty:
            continue
        best = candidates.loc[(candidates["entry_time"] - live_row["entry_time"]).abs().idxmin()]
        used_paper_ids.add(best["trade_id"])

        entry_slippage = None
        if pd.notna(live_row["net_credit"]) and pd.notna(best["net_credit"]):
            entry_slippage = round(live_row["net_credit"] - best["net_credit"], 2)
        pnl_slippage = None
        if pd.notna(live_row["realized_pnl"]) and pd.notna(best["realized_pnl"]):
            pnl_slippage = round(live_row["realized_pnl"] - best["realized_pnl"], 2)

        rows.append({
            "Entry Date": live_row["entry_time"].strftime("%Y-%m-%d"),
            "Strategy": live_row["strategy"],
            "Entry Level": live_row["entry_level_price"],
            "Timeframe": live_row["entry_timeframe"] or "N/A",
            "LIVE Net Credit": live_row["net_credit"],
            "PAPER Net Credit": best["net_credit"],
            "Entry Slippage (Rs)": entry_slippage,
            "LIVE P&L": live_row["realized_pnl"],
            "PAPER P&L": best["realized_pnl"],
            "P&L Slippage (Rs)": pnl_slippage,
        })
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def get_performance_by_group(symbol, group_col, mode_filter=None, start_date=None, end_date=None):
    """strategy (source)/entry_timeframe/trading_style नुसार कामगिरीची विभागणी (Win Rate, Total P&L,
    Trade Count, ROI%) — कोणती रणनीती/टाईमफ्रेम जास्त फायदेशीर आहे हे ठरवण्यासाठी. start_date/end_date
    दिले तर फक्त त्या exit_time रेंजमधलेच trades मोजले जातात (न दिल्यास संपूर्ण इतिहास).
    🎓 वापरकर्त्याने मागितलेली सुधारणा (Winning Rate — फक्त शुद्ध SL/Target, ROI — मार्जिन-आधारित) —
    get_performance_summary() मध्ये वापरलेलीच पद्धत, इथे प्रत्येक group साठी स्वतंत्रपणे."""
    conn = sqlite3.connect(DB_PATH)
    col_expr = f"COALESCE({group_col}, 'UNKNOWN')"
    query = f"""SELECT {col_expr} AS grp, realized_pnl, exit_reason, max_loss, lots, lot_size, entry_time, exit_time, entry_margin_required FROM live_trades
                WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if start_date:
        query += " AND date(exit_time) >= ?"
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        query += " AND date(exit_time) <= ?"
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return pd.DataFrame()

    rows = []
    for grp, sub in df.groupby("grp"):
        rows.append({
            "Group": grp, "Trades": len(sub),
            **_group_win_rate_and_roi(sub),
            "Total P&L": round(sub["realized_pnl"].sum(), 2),
            "Avg P&L": round(sub["realized_pnl"].mean(), 2),
        })
    return pd.DataFrame(rows).sort_values("Total P&L", ascending=False)


def get_performance_by_two_groups(symbol, group_col1, group_col2, mode_filter=None, start_date=None, end_date=None):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("strategy आणि timeframe दोन्ही एकत्र दाखवणारं वेगळं
    टेबल") — group_col1 + group_col2 दोन्हींच्या प्रत्येक जोडीसाठी स्वतंत्र ओळ (उदा. "1-Min Instant
    Trader" + "5M" ही specific जोडी किती फायदेशीर आहे, वेगळ्या-वेगळ्या single-column breakdown
    टेबलांमध्ये हे लगेच दिसत नाही). get_performance_by_group() सारखीच गणना (Win Rate/ROI%), फक्त
    group_col1×group_col2 च्या cross-tab वर."""
    conn = sqlite3.connect(DB_PATH)
    col_expr1 = f"COALESCE({group_col1}, 'UNKNOWN')"
    col_expr2 = f"COALESCE({group_col2}, 'UNKNOWN')"
    query = f"""SELECT {col_expr1} AS grp1, {col_expr2} AS grp2, realized_pnl, exit_reason, max_loss, lots, lot_size, entry_time, exit_time, entry_margin_required
                FROM live_trades WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if start_date:
        query += " AND date(exit_time) >= ?"
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        query += " AND date(exit_time) <= ?"
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return pd.DataFrame()

    rows = []
    for (g1, g2), sub in df.groupby(["grp1", "grp2"]):
        rows.append({
            "Strategy": g1, "Timeframe": g2, "Trades": len(sub),
            **_group_win_rate_and_roi(sub),
            "Total P&L": round(sub["realized_pnl"].sum(), 2),
            "Avg P&L": round(sub["realized_pnl"].mean(), 2),
        })
    return pd.DataFrame(rows).sort_values("Total P&L", ascending=False)


def get_closed_trades_detail(symbol, mode_filter=None, start_date=None, end_date=None):
    """प्रत्येक बंद (CLOSED) trade चा तपशील — Entry (source/timeframe/level/option-structure) आणि
    Exit (exit_reason) या दोन्हींसकट — Performance टॅबवरच्या 'Entry+Exit कारण' Trade Log साठी."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT trade_id AS "Trade ID", entry_time AS "Entry Time", exit_time AS "Exit Time",
                      COALESCE(source, 'UNKNOWN') AS source, COALESCE(entry_timeframe, 'UNKNOWN') AS entry_timeframe,
                      entry_level_price, COALESCE(strategy, 'UNKNOWN') AS strategy,
                      COALESCE(exit_reason, 'UNKNOWN') AS exit_reason, exit_reason_detail,
                      realized_pnl AS "Realized P&L", COALESCE(mode, 'LIVE') AS mode
               FROM live_trades WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL AND exit_time IS NOT NULL"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if start_date:
        query += " AND date(exit_time) >= ?"
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        query += " AND date(exit_time) <= ?"
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    query += " ORDER BY exit_time DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("review slippages after trade monitor update") — trading_engine.py
# च्या evaluate_point_spot_exit()/manage_open_trades() ने आधीच exit_reason_detail मध्ये लिहिलेल्या
# वाचनीय मजकुरातून (regex ने), प्रत्येक SL/TSL exit प्रत्यक्ष threshold च्या किती "पुढे जाऊन" (overshoot)
# पकडला गेला हे काढणे — polling-based monitoring (trade_monitor.py/mcx_futures_trader.py) च्या
# interval-सुधारणांनंतर स्लिपेज खरंच कमी झालं का, हे रोज (दरवेळी manual SQL query न चालवता) तपासता यावं.
_SL_TSL_OVERSHOOT_PATTERNS = [
    # TSL locked to Entry/Breakeven — threshold नेहमी 0, म्हणून overshoot = |प्रत्यक्ष आकडा|
    (re.compile(r"Premium gain (-?[\d.]+) points dropped to/below zero"),
     lambda m: {"basis": "TSL Breakeven (Premium pts)", "overshoot_points": abs(float(m.group(1)))}),
    # निरंतर Premium-Points Trailing SL — floor ओलांडून प्रत्यक्ष कुठे पकडलं गेलं
    (re.compile(r"floor (-?[\d.]+) pts, now at (-?[\d.]+) pts"),
     lambda m: {"basis": "TSL Trail (Premium pts)", "overshoot_points": float(m.group(1)) - float(m.group(2))}),
    # SL — दोन्ही (Spot% + Premium pts) एकाच वेळी
    (re.compile(
        r"Stop-Loss hit — both adverse Spot move (-?[\d.]+)% \(threshold -([\d.]+)%\) and "
        r"Premium loss (-?[\d.]+) points \(threshold -([\d.]+)\) reached simultaneously"
    ), lambda m: {
        "basis": "SL (Spot %+Premium pts)",
        "overshoot_pct": abs(float(m.group(1))) - float(m.group(2)),
        "overshoot_points": abs(float(m.group(3))) - float(m.group(4)),
    }),
    # SL — फक्त Premium points मुळे
    (re.compile(r"Stop-Loss hit via Premium points — loss (-?[\d.]+) points reached/exceeded the -([\d.]+)-point threshold"),
     lambda m: {"basis": "SL (Premium pts)", "overshoot_points": abs(float(m.group(1))) - float(m.group(2))}),
    # SL — फक्त Spot% मुळे
    (re.compile(r"Stop-Loss hit via Spot move — adverse move (-?[\d.]+)% reached/exceeded the -([\d.]+)% threshold"),
     lambda m: {"basis": "SL (Spot %)", "overshoot_pct": abs(float(m.group(1))) - float(m.group(2))}),
    # जुनी/इतर रणनीतींची निव्वळ ₹ P&L-आधारित SL/Trailing-SL (Rs मध्ये negative असू शकतं, त्यामुळे optional "-")
    (re.compile(
        r"(?:Trailing SL|Stop-Loss) — total P&L Rs (-?[\d,]+) hit/crossed the (?:\(profit-adjusted\) )?"
        r"(?:trailing SL|fixed SL) level Rs (-?[\d,]+)"
    ), lambda m: {
        "basis": "SL/TSL (Fixed Rs)",
        "overshoot_rs": abs(float(m.group(2).replace(",", "")) - float(m.group(1).replace(",", ""))),
    }),
]


def _parse_sl_tsl_overshoot_detail(detail):
    """वरच्या पॅटर्न्सपैकी पहिला जुळणारा वापरून overshoot काढणे — काहीच जुळलं नाही (उदा. जुनं, आताच्या
    detail-format आधीचं trade) तर None — असे trades overshoot टेबलमधून वगळले जातात, चुकीचा आकडा
    दाखवण्यापेक्षा."""
    if not detail or not isinstance(detail, str):
        return None
    for pattern, extractor in _SL_TSL_OVERSHOOT_PATTERNS:
        m = pattern.search(detail)
        if m:
            result = {"overshoot_points": None, "overshoot_pct": None, "overshoot_rs": None}
            result.update(extractor(m))
            return result
    return None


def get_sl_tsl_overshoot(symbol, mode_filter=None, start_date=None, end_date=None):
    """प्रत्येक SL/TSL exit साठी — threshold च्या किती "पुढे जाऊन" (overshoot) bot ला किंमत सापडली,
    तेच trading_engine.py ने आधीच exit_reason_detail मध्ये साठवलेल्या मजकुरातून काढून — Performance
    टॅबवर SL/TSL Overshoot (Slippage) Tracker साठी."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT trade_id AS "Trade ID", exit_time AS "Exit Time", exit_reason,
                      exit_reason_detail, realized_pnl AS "Realized P&L", COALESCE(mode, 'LIVE') AS "Mode"
               FROM live_trades
               WHERE symbol=? AND status='CLOSED' AND exit_reason_detail IS NOT NULL
                     AND exit_reason IN ('SL', 'TSL_SL', 'TRAILING_SL', 'PCT_TRAILING_SL')"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if start_date:
        query += " AND date(exit_time) >= ?"
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        query += " AND date(exit_time) <= ?"
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    query += " ORDER BY exit_time DESC"
    raw_df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    cols = ["Trade ID", "Exit Time", "Exit Reason", "Basis", "Overshoot (pts)", "Overshoot (%)", "Overshoot (Rs)", "Realized P&L", "Mode"]
    if raw_df.empty:
        return pd.DataFrame(columns=cols)

    rows = []
    for _, r in raw_df.iterrows():
        parsed = _parse_sl_tsl_overshoot_detail(r["exit_reason_detail"])
        if parsed is None:
            continue
        rows.append({
            "Trade ID": r["Trade ID"], "Exit Time": r["Exit Time"], "Exit Reason": r["exit_reason"],
            "Basis": parsed["basis"],
            "Overshoot (pts)": round(parsed["overshoot_points"], 2) if parsed["overshoot_points"] is not None else None,
            "Overshoot (%)": round(parsed["overshoot_pct"], 3) if parsed["overshoot_pct"] is not None else None,
            "Overshoot (Rs)": round(parsed["overshoot_rs"], 0) if parsed["overshoot_rs"] is not None else None,
            "Realized P&L": r["Realized P&L"], "Mode": r["Mode"],
        })
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def get_exit_reason_breakdown(symbol, group_col, mode_filter=None, start_date=None, end_date=None):
    """group_col (source/entry_timeframe) आणि exit_reason नुसार एकत्रित आकडे — कोणत्या कारणाने
    (SL/Target/Trailing SL/EOD वगैरे) सर्वात जास्त वेळा बाहेर पडलं जातं हे strategy/timeframe-निहाय
    तपासण्यासाठी — SL/Target/Trailing-SL सेटिंग्ज optimize करण्याच्या शिफारशींचा आधार."""
    conn = sqlite3.connect(DB_PATH)
    col_expr = f"COALESCE({group_col}, 'UNKNOWN')"
    query = f"""SELECT {col_expr} AS grp, COALESCE(exit_reason, 'UNKNOWN') AS exit_reason, realized_pnl
                FROM live_trades WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if start_date:
        query += " AND date(exit_time) >= ?"
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        query += " AND date(exit_time) <= ?"
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return pd.DataFrame()

    rows = []
    for (grp, reason), sub in df.groupby(["grp", "exit_reason"]):
        rows.append({
            "Group": grp, "Exit Reason": reason, "Trades": len(sub),
            "Total P&L": round(sub["realized_pnl"].sum(), 2),
            "Avg P&L": round(sub["realized_pnl"].mean(), 2),
        })
    return pd.DataFrame(rows)

def get_order_log_full(symbol, start_date=None, end_date=None, mode_filter=None):
    """Order Log — दिलेल्या तारीख-रेंजमध्ये (start_date/end_date न दिल्यास सर्व), मर्यादा-विरहित —
    Orders टॅबवरच्या तारीख-रेंज फिल्टर व CSV डाऊनलोडसाठी."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT placed_at AS "Time", order_id AS "Order ID", trade_id AS "Trade ID", mode AS "Mode",
                      transaction_type AS "Action", strike AS "Strike", option_type AS "Option Type",
                      expiry AS "Expiry", order_type AS "Type", quantity AS "Qty",
                      COALESCE(fill_price, price) AS "Price", trigger_price AS "Trigger", status AS "Status", tag AS "Tag"
               FROM order_log WHERE symbol=?"""
    params = [symbol]
    if start_date:
        query += " AND date(placed_at) >= ?"
        params.append(start_date.strftime("%Y-%m-%d"))
    if end_date:
        query += " AND date(placed_at) <= ?"
        params.append(end_date.strftime("%Y-%m-%d"))
    if mode_filter:
        query += " AND mode=?"
        params.append(mode_filter)
    query += " ORDER BY placed_at DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_orders_with_account(symbol, start_date, end_date, mode_filter=None):
    """दिलेल्या तारीख-रेंजमधले सर्व orders, account_id सकट (charges.py ला ब्रोकर ओळखण्यासाठी लागतो) —
    order_log.trade_id → live_trades.account_id असा LEFT JOIN. trade_id जुळला नाही (उदा. Manual
    Trading Panel चे MANUAL_UNTRACKED/BASKET_UNTRACKED, जे कायम फक्त Upstox वापरतात) तर account_id
    NULL राहतो — charges.py मध्ये त्याचा अर्थ आपोआप "upstox" असा घेतला जातो.
    quantity/fill_price/price/transaction_type — charges.py ला STT/Exchange/SEBI/Stamp Duty सारखे
    turnover-आधारित सरकारी/एक्सचेंज शुल्क अचूक मोजण्यासाठी लागतात (फक्त flat brokerage पुरेसं नाही)."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT o.order_id, o.trade_id, o.placed_at, o.mode, o.quantity, o.fill_price, o.price,
                      o.transaction_type, lt.account_id
               FROM order_log o LEFT JOIN live_trades lt ON o.trade_id = lt.trade_id
               WHERE o.symbol=? AND date(o.placed_at) >= ? AND date(o.placed_at) <= ?"""
    params = [symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
    if mode_filter:
        query += " AND o.mode=?"
        params.append(mode_filter)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_closed_trades_for_report(symbol, start_date, end_date, mode_filter=None):
    """दिलेल्या तारीख-रेंजमध्ये बंद (CLOSED) झालेले trades — exit_time नुसार (P&L exit च्याच दिवशी
    'realized' मानला जातो, entry दिवशी नाही) — Daily/Weekly/Monthly P&L Report साठी."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT trade_id, exit_time, realized_pnl FROM live_trades
               WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL AND exit_time IS NOT NULL
               AND date(exit_time) >= ? AND date(exit_time) <= ?"""
    params = [symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty:
        df["exit_time"] = pd.to_datetime(df["exit_time"])
    return df
