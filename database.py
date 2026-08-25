"""SQLite database: schema init, order/trade logging, and all query/read functions."""
import datetime
import json
import os
import sqlite3
import pandas as pd

from config import DATA_DIR, DB_PATH, get_ist_now, get_ist_today
from upstox_api import fetch_ltp_map


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
    for col_def in ["legs_json TEXT", "strikes_summary TEXT", "mode TEXT", "trading_style TEXT", "peak_pnl REAL"]:
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
            placed_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_sqlite_db()


def log_order(order_id, trade_id, symbol, mode, order_dict, status):
    """खऱ्या ब्रोकर टर्मिनलसारखं — प्रत्येक ऑर्डर (leg) चा एक कायमचा रेकॉर्ड ठेवणे, Orders टॅबसाठी."""
    try:
        instrument_key = order_dict.get("instrument_token", "")
        strike = None
        option_type = None
        if "|" in instrument_key:
            # instrument key मधून काही उपयुक्त माहिती काढता आली तर काढणे (अनिवार्य नाही, फक्त प्रदर्शनासाठी)
            pass
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO order_log
               (order_id, trade_id, symbol, mode, instrument_key, strike, option_type, transaction_type,
                order_type, quantity, price, trigger_price, status, tag, placed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order_id, trade_id, symbol, mode, instrument_key, strike, option_type,
                order_dict.get("transaction_type"), order_dict.get("order_type"),
                order_dict.get("quantity"), order_dict.get("price"), order_dict.get("trigger_price"),
                status, order_dict.get("tag"), get_ist_now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # ऑर्डर लॉगिंग अयशस्वी झाली तरी मुख्य ऑर्डर-प्लेसमेंट थांबता कामा नये

def log_orders_batch(order_ids, trade_id, symbol, mode, orders, status="COMPLETE"):
    """एका ऑर्डर-सेटमधील प्रत्येक leg साठी log_order() कॉल करणे."""
    for i, o in enumerate(orders):
        oid = order_ids[i] if i < len(order_ids) else f"UNKNOWN-{i}"
        log_order(oid, trade_id, symbol, mode, o, status)

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

def get_todays_realized_pnl(symbol, trading_mode="LIVE"):
    """आजच्या दिवसात बंद झालेल्या (CLOSED) ट्रेड्सचा एकूण वास्तविक नफा/तोटा (डेली सर्किट ब्रेकरसाठी).
    PAPER आणि LIVE ट्रेड्स स्वतंत्रपणे मोजले जातात, जेणेकरून Paper टेस्टिंगमुळे Live सर्किट ब्रेकर
    (किंवा उलट) चुकीने ट्रिगर होणार नाही."""
    today_str = get_ist_today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(realized_pnl),0) FROM live_trades WHERE symbol=? AND trade_date=? AND status='CLOSED' AND COALESCE(mode,'LIVE')=?",
        (symbol, today_str, trading_mode),
    )
    total_pnl = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM live_trades WHERE symbol=? AND trade_date=? AND COALESCE(mode,'LIVE')=?",
        (symbol, today_str, trading_mode),
    )
    total_trades_today = cur.fetchone()[0]
    conn.close()
    return total_pnl, total_trades_today

def get_live_positions_with_mtm(access_token, symbol, mode_filter=None):
    """
    सर्व OPEN पोझिशन्ससाठी सद्य LTP आणून खरा (real) MTM P&L काढणे — Positions टॅबसाठी,
    अगदी ब्रोकर टर्मिनलसारखं (Entry, LTP, Qty, MTM ₹, MTM %).
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = """SELECT trade_id, mode, trading_style, strategy, legs_json, lots, lot_size, net_credit,
                      max_profit, max_loss, entry_time, strikes_summary, peak_pnl
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
    for (trade_id, mode, style, strategy, legs_json, lots, lot_size, net_credit, max_profit, max_loss, entry_time, strikes_summary, peak_pnl), legs in parsed:
        mtm, mtm_pct = None, None
        if legs:
            current_ltps = {leg["instrument_key"]: ltp_map.get(leg["instrument_key"]) for leg in legs}
            if all(v is not None for v in current_ltps.values()):
                cost_to_close_now = sum(
                    current_ltps[leg["instrument_key"]] * (1 if leg["transaction_type"] == "SELL" else -1)
                    for leg in legs
                )
                mtm = round((net_credit - cost_to_close_now) * lots * lot_size, 2)
                if max_loss:
                    mtm_pct = round((mtm / (max_loss)) * 100, 1) if mtm < 0 else round((mtm / max_profit) * 100, 1) if max_profit else None
        # 🎓 Portfolio-level Risk Dashboard साठी — max_loss/net_credit/Direction आधीच query मध्ये
        # fetch होत होते, पण output मध्ये नव्हते. जोडलं (backward-compatible, फक्त नवीन columns).
        direction = "BULLISH" if strategy == "BULL_PUT_SPREAD" else ("BEARISH" if strategy == "BEAR_CALL_SPREAD" else "NEUTRAL")
        records.append({
            "Trade ID": trade_id, "Mode": mode or "LIVE", "Style": style or "INTRADAY",
            "Strategy": strategy, "Direction": direction, "Legs": strikes_summary, "Lots": lots,
            "Entry Time": entry_time, "MTM (Rs)": mtm, "MTM (%)": mtm_pct,
            "Max Loss (Rs)": round(max_loss * lots * lot_size, 2) if max_loss else None,
            "Net Credit (Rs)": round(net_credit * lots * lot_size, 2) if net_credit else None,
            "Peak P&L (Rs)": round(peak_pnl, 2) if peak_pnl is not None else None,
        })
    return pd.DataFrame(records)


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

def get_performance_summary(symbol, mode_filter=None, style_filter=None):
    """
    बंद झालेल्या (CLOSED) ट्रेड्सवरून Win Rate, Avg P&L, Profit Factor वगैरे मूळ कामगिरी आकडे काढणे.
    """
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT realized_pnl FROM live_trades WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL"
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    if style_filter:
        query += " AND COALESCE(trading_style,'INTRADAY')=?"
        params.append(style_filter)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return {"total_trades": 0}

    pnls = df["realized_pnl"]
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    return {
        "total_trades": len(pnls),
        "win_count": len(wins), "loss_count": len(losses),
        "win_rate": round(len(wins) / len(pnls) * 100, 1) if len(pnls) else None,
        "total_pnl": round(pnls.sum(), 2),
        "avg_pnl": round(pnls.mean(), 2),
        "avg_win": round(wins.mean(), 2) if len(wins) else None,
        "avg_loss": round(losses.mean(), 2) if len(losses) else None,
        "best_trade": round(pnls.max(), 2),
        "worst_trade": round(pnls.min(), 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
    }

def get_equity_curve_data(symbol, mode_filter=None, style_filter=None):
    """वेळेनुसार संचयी (cumulative) वास्तविक P&L — Equity Curve चार्टसाठी."""
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
    query += " ORDER BY exit_time ASC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return df
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df["cumulative_pnl"] = df["realized_pnl"].cumsum()
    return df

def get_performance_by_group(symbol, group_col, mode_filter=None):
    """strategy किंवा trading_style नुसार कामगिरीची विभागणी (Win Rate, Total P&L, Trade Count)."""
    conn = sqlite3.connect(DB_PATH)
    col_expr = f"COALESCE({group_col}, 'UNKNOWN')"
    query = f"""SELECT {col_expr} AS grp, realized_pnl FROM live_trades
                WHERE symbol=? AND status='CLOSED' AND realized_pnl IS NOT NULL"""
    params = [symbol]
    if mode_filter:
        query += " AND COALESCE(mode,'LIVE')=?"
        params.append(mode_filter)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return pd.DataFrame()

    rows = []
    for grp, sub in df.groupby("grp"):
        wins = sub[sub["realized_pnl"] > 0]
        rows.append({
            "Group": grp, "Trades": len(sub),
            "Win Rate %": round(len(wins) / len(sub) * 100, 1),
            "Total P&L": round(sub["realized_pnl"].sum(), 2),
            "Avg P&L": round(sub["realized_pnl"].mean(), 2),
        })
    return pd.DataFrame(rows).sort_values("Total P&L", ascending=False)

def get_order_log(symbol, mode_filter=None, limit=100):
    """आजच्या (व अलीकडच्या) सर्व ऑर्डर्सची यादी — Orders टॅबसाठी (खऱ्या ब्रोकर Order Book सारखं)."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT placed_at AS "Time", order_id AS "Order ID", trade_id AS "Trade ID", mode AS "Mode",
                      transaction_type AS "Action", order_type AS "Type", quantity AS "Qty",
                      price AS "Price", trigger_price AS "Trigger", status AS "Status", tag AS "Tag"
               FROM order_log WHERE symbol=?"""
    params = [symbol]
    if mode_filter:
        query += " AND mode=?"
        params.append(mode_filter)
    query += " ORDER BY placed_at DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df
