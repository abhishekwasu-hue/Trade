"""
tests/test_database.py
--------------------------
DB Migrations — नवीन columns (total_call_premium इ.) जुन्या (migration-आधीच्या) DB वरही सुरक्षितपणे
लागू होतात याची खात्री. हे विशेषतः महत्त्वाचं आहे कारण वापरकर्त्याचा deployed DB जुना असू शकतो.
"""
import sqlite3
import tempfile

import database


def test_migration_adds_new_columns_to_old_db(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)

    # जुनी (migration आधीची) स्कीमा सिम्युलेट करणे
    conn = sqlite3.connect(tmpdb)
    conn.execute("""CREATE TABLE oi_diff_snapshots (
        symbol TEXT, trade_date TEXT, snapshot_time TEXT, total_call_oi INTEGER, total_put_oi INTEGER,
        diff INTEGER, delta_diff INTEGER, signal TEXT, underlying_price REAL,
        PRIMARY KEY (symbol, trade_date, snapshot_time)
    )""")
    conn.execute("CREATE TABLE live_trades (trade_id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

    database.init_sqlite_db()

    conn = sqlite3.connect(tmpdb)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(oi_diff_snapshots)")
    cols = [row[1] for row in cur.fetchall()]
    conn.close()

    assert "total_call_premium" in cols
    assert "total_put_premium" in cols
    assert "underlying_price" in cols  # आधीचं migration सुद्धा अजूनही कार्यरत


def test_fresh_db_has_all_expected_tables(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()

    conn = sqlite3.connect(tmpdb)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()

    for expected in ["historical_candles", "oi_diff_snapshots", "live_trades", "order_log"]:
        assert expected in tables
