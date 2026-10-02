"""
tests/test_eod_trade_summary.py
--------------------------------
EOD Telegram सारांश (eod_trade_summary.py) -- संदेशाचा मजकूर, LIVE/PAPER वेगळेपणा, shadow वगळणं, सुट्टीच्या दिवशी न पाठवणं,
आणि खऱ्या तात्पुरत्या SQLite DB वर end-to-end (charges सकट).
"""
import datetime
import json
import sqlite3
import tempfile

import pandas as pd
import pytest

import database
import eod_trade_summary as eod

DAY = datetime.date(2026, 10, 1)  # गुरुवार


@pytest.fixture
def temp_db(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    yield tmpdb


def _insert(tmpdb, trade_id, symbol, mode, status, pnl, source=None, exit_time="2026-10-01 11:30:00"):
    legs = [{"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL"}]
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit, max_profit, max_loss,
           sl_pnl_level, target_pnl_level, entry_time, status, legs_json, strikes_summary, mode, trading_style, source,
           exit_time, realized_pnl) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, "2026-10-01", symbol, "BULL_PUT_SPREAD", 1, 75, 30, 30, 50, -1000, 1000, "2026-10-01 10:00:00",
         status, json.dumps(legs), "t", mode, "INTRADAY", source, exit_time if status == "CLOSED" else None, pnl),
    )
    conn.commit()
    conn.close()


class TestBuildMessage:
    def test_live_and_paper_lines_with_counts_and_net(self):
        msg = eod.build_message("nse", DAY, {
            "LIVE": {"trades": 4, "wins": 3, "losses": 1, "gross": 1250.0, "charges": 210.0, "net": 1040.0},
            "PAPER": {"trades": 2, "wins": 0, "losses": 2, "gross": -800.0, "charges": 90.0, "net": -890.0},
        })
        assert "NSE" in msg and "2026-10-01" in msg
        assert "LIVE" in msg and "4 trade" in msg and "जिंक 3 / हर 1" in msg
        assert "+₹1,250" in msg and "₹210" in msg and "+₹1,040" in msg
        assert "PAPER" in msg and "-₹800" in msg and "-₹890" in msg

    def test_no_trades_says_so(self):
        msg = eod.build_message("mcx", DAY, {"LIVE": None, "PAPER": None})
        assert "MCX" in msg and "कुठलाही trade बंद झाला नाही" in msg

    def test_open_positions_warning(self):
        msg = eod.build_message("mcx", DAY, {"LIVE": None, "PAPER": None}, open_count=2)
        assert "2 trade OPEN" in msg

    def test_mode_without_trades_is_omitted(self):
        msg = eod.build_message("nse", DAY, {"LIVE": None, "PAPER": {"trades": 1, "wins": 1, "losses": 0, "gross": 100.0, "charges": 10.0, "net": 90.0}})
        assert "LIVE" not in msg and "PAPER" in msg


class TestRunSummary:
    def test_nse_skipped_on_weekend(self):
        sent = []
        assert eod.run_summary("nse", datetime.date(2026, 10, 3), send_fn=sent.append) is None  # शनिवार
        assert sent == []

    def test_end_to_end_with_real_db(self, temp_db):
        _insert(temp_db, "A", "NIFTY", "LIVE", "CLOSED", 1500.0)
        _insert(temp_db, "B", "NIFTY", "LIVE", "CLOSED", -400.0)
        _insert(temp_db, "C", "BANKNIFTY", "PAPER", "CLOSED", 200.0)
        _insert(temp_db, "D", "NIFTY", "PAPER", "CLOSED", 9999.0, source="dynamic_sr_instant_otm_shadow")  # shadow -- वगळला पाहिजे
        _insert(temp_db, "E", "NIFTY", "LIVE", "OPEN", None)
        _insert(temp_db, "F", "GOLD", "PAPER", "CLOSED", 777.0)  # MCX -- NSE सारांशात नको
        sent = []
        msg = eod.run_summary("nse", DAY, send_fn=sent.append)
        assert sent == [msg]
        assert "LIVE" in msg and "2 trade (जिंक 1 / हर 1)" in msg and "+₹1,100" in msg
        assert "PAPER" in msg and "1 trade" in msg and "+₹200" in msg
        assert "9,999" not in msg and "777" not in msg
        assert "1 trade OPEN" in msg

    def test_mcx_market_uses_only_mcx_symbols(self, temp_db):
        _insert(temp_db, "G", "GOLD", "PAPER", "CLOSED", 777.0)
        _insert(temp_db, "H", "NIFTY", "PAPER", "CLOSED", 500.0)
        msg = eod.run_summary("mcx", DAY, send_fn=lambda m: None)
        assert "+₹777" in msg and "500" not in msg

    def test_day_with_no_trades(self, temp_db):
        msg = eod.run_summary("nse", DAY, send_fn=lambda m: None)
        assert "कुठलाही trade बंद झाला नाही" in msg
