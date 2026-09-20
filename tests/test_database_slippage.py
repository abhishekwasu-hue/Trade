"""
tests/test_database_slippage.py
--------------------------------
database.get_live_vs_shadow_paper_pairs() — LIVE+PAPER शॅडो मोडमध्ये उघडलेल्या जोड्या शोधून
(same source/strategy/entry_level_price/entry_timeframe, entry_time जवळपास एकसारखा) प्रत्यक्ष LIVE
execution आणि शुद्ध PAPER सिम्युलेशन मधला फरक (slippage) अचूक मोजतो का, याची पडताळणी.
"""
import datetime
import json
import sqlite3
import tempfile

import pytest

import database


@pytest.fixture
def temp_db(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    yield tmpdb


def seed(tmpdb, trade_id, entry_time, net_credit, realized_pnl, mode, symbol="NIFTY",
          source="dynamic_sr_instant", strategy="BULL_PUT_SPREAD", entry_level_price=23900.0,
          entry_timeframe="15M", exit_time=None):
    exit_time = exit_time or entry_time
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, exit_time, exit_reason,
           realized_pnl, status, legs_json, mode, trading_style, source, entry_level_price,
           entry_timeframe) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, entry_time[:10], symbol, strategy, 1, 75, net_credit, net_credit, 500, 250, 500,
         entry_time, exit_time, "TARGET", realized_pnl, "CLOSED", json.dumps([]), mode, "INTRADAY",
         source, entry_level_price, entry_timeframe),
    )
    conn.commit()
    conn.close()


class TestGetLiveVsShadowPaperPairs:
    def test_pairs_matching_live_and_paper_trade(self, temp_db):
        seed(temp_db, "L1", "2026-09-10 10:00:05", net_credit=20.0, realized_pnl=500.0, mode="LIVE")
        seed(temp_db, "P1", "2026-09-10 10:00:07", net_credit=25.0, realized_pnl=600.0, mode="PAPER")

        df = database.get_live_vs_shadow_paper_pairs("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert len(df) == 1
        row = df.iloc[0]
        assert row["LIVE Net Credit"] == 20.0
        assert row["PAPER Net Credit"] == 25.0
        assert row["Entry Slippage (Rs)"] == -5.0  # LIVE(20) - PAPER(25)
        assert row["LIVE P&L"] == 500.0
        assert row["PAPER P&L"] == 600.0
        assert row["P&L Slippage (Rs)"] == -100.0

    def test_no_pair_when_only_live_exists(self, temp_db):
        seed(temp_db, "L1", "2026-09-10 10:00:05", net_credit=20.0, realized_pnl=500.0, mode="LIVE")
        df = database.get_live_vs_shadow_paper_pairs("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert df.empty

    def test_no_pair_when_entry_time_too_far_apart(self, temp_db):
        seed(temp_db, "L1", "2026-09-10 10:00:00", net_credit=20.0, realized_pnl=500.0, mode="LIVE")
        seed(temp_db, "P1", "2026-09-10 10:30:00", net_credit=25.0, realized_pnl=600.0, mode="PAPER")  # 30 मिनिटं दूर
        df = database.get_live_vs_shadow_paper_pairs("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert df.empty

    def test_no_pair_when_different_entry_level(self, temp_db):
        seed(temp_db, "L1", "2026-09-10 10:00:00", net_credit=20.0, realized_pnl=500.0, mode="LIVE", entry_level_price=23900.0)
        seed(temp_db, "P1", "2026-09-10 10:00:05", net_credit=25.0, realized_pnl=600.0, mode="PAPER", entry_level_price=24000.0)
        df = database.get_live_vs_shadow_paper_pairs("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert df.empty

    def test_each_paper_trade_used_at_most_once(self, temp_db):
        # दोन LIVE trades, पण फक्त एकच जुळणारा PAPER trade — फक्त एकच जोडी तयार व्हायला हवी.
        seed(temp_db, "L1", "2026-09-10 10:00:00", net_credit=20.0, realized_pnl=500.0, mode="LIVE")
        seed(temp_db, "L2", "2026-09-10 10:00:02", net_credit=21.0, realized_pnl=520.0, mode="LIVE")
        seed(temp_db, "P1", "2026-09-10 10:00:01", net_credit=25.0, realized_pnl=600.0, mode="PAPER")
        df = database.get_live_vs_shadow_paper_pairs("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert len(df) == 1
        # सर्वात जवळचा (L1, 1 सेकंद दूर) जिंकतो, L2 (2 सेकंद दूर) नाही
        assert df.iloc[0]["LIVE P&L"] == 500.0

    def test_pure_live_mode_never_pairs_with_unrelated_paper_trade(self, temp_db):
        """शुद्ध PAPER मोडमध्ये चालणाऱ्या दुसऱ्या strategy/symbol चा trade चुकून जोडला जाऊ नये."""
        seed(temp_db, "L1", "2026-09-10 10:00:00", net_credit=20.0, realized_pnl=500.0, mode="LIVE", source="dynamic_sr_instant")
        seed(temp_db, "P1", "2026-09-10 10:00:05", net_credit=25.0, realized_pnl=600.0, mode="PAPER", source="srv2_momentum_reversal")
        df = database.get_live_vs_shadow_paper_pairs("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert df.empty

    def test_empty_when_no_trades(self, temp_db):
        df = database.get_live_vs_shadow_paper_pairs("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert df.empty
        assert list(df.columns) == [
            "Entry Date", "Strategy", "Entry Level", "Timeframe", "LIVE Net Credit", "PAPER Net Credit",
            "Entry Slippage (Rs)", "LIVE P&L", "PAPER P&L", "P&L Slippage (Rs)",
        ]
