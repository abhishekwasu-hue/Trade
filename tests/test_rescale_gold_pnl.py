"""tests/test_rescale_gold_pnl.py -- जुन्या (गुणकाशिवाय साठवलेल्या) GOLD trades ची एकदाच ×100 दुरुस्ती."""
import sqlite3

import pytest

import rescale_gold_pnl as rg


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(str(tmp_path / "t.db"))
    c.execute(
        """CREATE TABLE live_trades (trade_id TEXT, trade_date TEXT, symbol TEXT, source TEXT, status TEXT, mode TEXT,
           lots INTEGER, lot_size REAL, realized_pnl REAL, peak_pnl REAL, sl_pnl_level REAL, target_pnl_level REAL,
           manual_sl_override_pnl REAL, pnl_multiplier REAL, entry_time TEXT)"""
    )
    rows = [
        # जुना GOLD (गुणक नाही), बंद
        ("OLD1", "2026-09-30", "GOLD", "mcx_futures", "CLOSED", "PAPER", 1, 1, 38.0, 50.0, -500.0, 900.0, None, 1, "t1"),
        # जुना GOLD, NULL multiplier, OPEN
        ("OLD2", "2026-10-02", "GOLD", "mcx_futures", "OPEN", "PAPER", 1, 1, None, 10.0, -400.0, 800.0, -300.0, None, "t2"),
        # आधीच दुरुस्त GOLD (multiplier 100)
        ("NEW", "2026-10-02", "GOLD", "mcx_futures", "CLOSED", "PAPER", 1, 100, 8000.0, 9000.0, -1.0, 1.0, None, 100, "t3"),
        # SILVER आणि दुसरा source — हात लावायचा नाही
        ("SIL", "2026-10-01", "SILVER", "mcx_futures", "CLOSED", "PAPER", 1, 30, 8910.0, 9000.0, 1.0, 1.0, None, 1, "t4"),
        ("OTH", "2026-10-01", "GOLD", "dynamic_sr_instant", "CLOSED", "PAPER", 1, 1, 5.0, 5.0, 1.0, 1.0, None, 1, "t5"),
    ]
    c.executemany("INSERT INTO live_trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    yield c
    c.close()


def _row(conn, tid):
    return conn.execute("SELECT lot_size, realized_pnl, peak_pnl, sl_pnl_level, target_pnl_level, manual_sl_override_pnl, pnl_multiplier "
                        "FROM live_trades WHERE trade_id=?", (tid,)).fetchone()


def test_finds_only_unscaled_gold_mcx_rows(conn):
    assert {r[0] for r in rg.find_unscaled_gold_trades(conn)} == {"OLD1", "OLD2"}


def test_rescale_multiplies_pnl_fields_by_100_and_marks_multiplier(conn):
    assert rg.rescale_gold_trades(conn) == 2
    assert _row(conn, "OLD1") == (100, 3800.0, 5000.0, -50000.0, 90000.0, None, 100)
    lot_size, realized, peak, sl, tgt, manual, mult = _row(conn, "OLD2")
    assert (lot_size, realized, peak, sl, tgt, manual, mult) == (100, None, 1000.0, -40000.0, 80000.0, -30000.0, 100)


def test_untouched_rows_stay_untouched(conn):
    before = {t: _row(conn, t) for t in ("NEW", "SIL", "OTH")}
    rg.rescale_gold_trades(conn)
    assert {t: _row(conn, t) for t in ("NEW", "SIL", "OTH")} == before


def test_idempotent(conn):
    rg.rescale_gold_trades(conn)
    snapshot = conn.execute("SELECT * FROM live_trades ORDER BY trade_id").fetchall()
    assert rg.rescale_gold_trades(conn) == 0
    assert conn.execute("SELECT * FROM live_trades ORDER BY trade_id").fetchall() == snapshot
