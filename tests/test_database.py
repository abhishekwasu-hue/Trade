"""
tests/test_database.py
--------------------------------
Performance टॅबवरच्या नवीन "Entry+Exit कारण" Trade Log आणि rule-based शिफारशींचा आधार असलेल्या
database.py च्या query helpers साठी — खऱ्या तात्पुरत्या SQLite DB वर.
"""
import datetime
import json
import sqlite3
import tempfile

import pandas as pd
import pytest

import database


@pytest.fixture
def temp_db(monkeypatch):
    """प्रत्येक test साठी नवीन, स्वतंत्र तात्पुरता SQLite DB."""
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    yield tmpdb


def seed_closed_trade(tmpdb, trade_id, realized_pnl, exit_reason, exit_date, symbol="NIFTY",
                       source="dynamic_sr_instant", entry_timeframe="15M", entry_level_price=23900.0,
                       strategy="BULL_PUT_SPREAD", mode="LIVE", exit_reason_detail=None):
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, exit_time, exit_reason,
           exit_reason_detail, realized_pnl, status, legs_json, mode, trading_style, source,
           entry_level_price, entry_timeframe) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, exit_date, symbol, strategy, 1, 75, 1000, 1000, 500, 250, 500,
         f"{exit_date} 10:00:00", f"{exit_date} 14:00:00", exit_reason, exit_reason_detail, realized_pnl,
         "CLOSED", json.dumps([]), mode, "INTRADAY", source, entry_level_price, entry_timeframe),
    )
    conn.commit()
    conn.close()


class TestGetClosedTradesDetail:
    def test_returns_entry_and_exit_columns(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-10")
        df = database.get_closed_trades_detail("NIFTY")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["source"] == "dynamic_sr_instant"
        assert row["entry_timeframe"] == "15M"
        assert row["exit_reason"] == "TARGET"
        assert row["Realized P&L"] == 500.0

    def test_date_range_filters_by_exit_date(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-01")
        seed_closed_trade(temp_db, "T2", -200.0, "SL", "2026-09-15")
        df = database.get_closed_trades_detail(
            "NIFTY", start_date=datetime.date(2026, 9, 10), end_date=datetime.date(2026, 9, 20),
        )
        assert len(df) == 1
        assert df.iloc[0]["Trade ID"] == "T2"

    def test_mode_filter(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-10", mode="LIVE")
        seed_closed_trade(temp_db, "T2", 300.0, "TARGET", "2026-09-10", mode="PAPER")
        df = database.get_closed_trades_detail("NIFTY", mode_filter="PAPER")
        assert len(df) == 1
        assert df.iloc[0]["Trade ID"] == "T2"

    def test_includes_exit_reason_detail(self, temp_db):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Performance Report PDF) — SL/Target नेमकं
        Spot% की Premium Points मुळे लागला, हे स्पष्ट करणारा exit_reason_detail column."""
        seed_closed_trade(
            temp_db, "T1", -200.0, "SL", "2026-09-10",
            exit_reason_detail="Stop-Loss hit via Premium points - loss -6.0 points reached/exceeded the -5-point threshold.",
        )
        seed_closed_trade(temp_db, "T2", 300.0, "EOD_SQUAREOFF", "2026-09-10")
        df = database.get_closed_trades_detail("NIFTY").sort_values("Trade ID").reset_index(drop=True)
        assert df.iloc[0]["exit_reason_detail"] == "Stop-Loss hit via Premium points - loss -6.0 points reached/exceeded the -5-point threshold."
        assert pd.isna(df.iloc[1]["exit_reason_detail"])


class TestGetExitReasonBreakdown:
    def test_groups_by_source_and_exit_reason(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-10", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T2", -200.0, "SL", "2026-09-11", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T3", 300.0, "TARGET", "2026-09-12", source="srv2_momentum_reversal")

        df = database.get_exit_reason_breakdown("NIFTY", "source")
        assert len(df) == 3
        instant_sl_row = df[(df["Group"] == "dynamic_sr_instant") & (df["Exit Reason"] == "SL")].iloc[0]
        assert instant_sl_row["Trades"] == 1
        assert instant_sl_row["Total P&L"] == -200.0

    def test_empty_when_no_trades(self, temp_db):
        df = database.get_exit_reason_breakdown("NIFTY", "source")
        assert df.empty
