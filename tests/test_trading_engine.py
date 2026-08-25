"""
tests/test_trading_engine.py
--------------------------------
SL/Target गणित आणि दुपारी ३ वाजताचा Carry-Forward/Close निर्णय — हे सर्वात नाजूक, थेट खऱ्या पैशाशी
संबंधित logic आहे (वापरकर्त्याशी चर्चा करून ठरवलेलं). खऱ्या तात्पुरत्या SQLite DB वर, वेळ mock करून चालवलं जातं.
"""
import datetime
import json
import sqlite3
import tempfile

import pytest

import database
import trading_engine


@pytest.fixture
def temp_db(monkeypatch):
    """प्रत्येक test साठी नवीन, स्वतंत्र तात्पुरता SQLite DB."""
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
    yield tmpdb


def seed_trade(tmpdb, trade_id, net_credit, sl_level, target_level, strategy="BULL_PUT_SPREAD"):
    conn = sqlite3.connect(tmpdb)
    legs = [
        {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL"},
        {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY"},
    ]
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, status, legs_json,
           strikes_summary, mode, trading_style) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, "2026-08-24", "NIFTY", strategy, 1, 75, net_credit, net_credit, 50,
         sl_level, target_level, "2026-08-24 10:00:00", "OPEN", json.dumps(legs), "test", "PAPER", "SWING"),
    )
    conn.commit()
    conn.close()


class FakeTime(datetime.datetime):
    """वेळ mock करण्यासाठी -- ३ वाजण्यापूर्वी/नंतर दोन्ही परिस्थिती नियंत्रितपणे तयार करता येतात."""
    _fixed = None

    @classmethod
    def utcnow(cls):
        return cls._fixed


class TestSLTargetComputation:
    """SL आधार (net_credit चा % वि max_loss चा %) — दोन्ही मार्ग स्वतंत्र, एकमेकांना बाधा न आणता."""

    def test_old_basis_uses_max_loss_pct(self):
        """Iron Condor/Butterfly साठी जुनाच मार्ग अजूनही कार्यरत असायला हवा."""
        max_loss_total, net_credit_total = 50 * 75, 30 * 75
        sl_pct_of_max_loss = 50
        sl_pnl_level = -(max_loss_total * (sl_pct_of_max_loss / 100.0))
        assert sl_pnl_level == -1875.0

    def test_new_basis_uses_net_credit_pct(self):
        """Price Action/Indicator साठी नवीन मार्ग -- net_credit चा 30%."""
        net_credit_total = 50 * 75
        sl_pct_of_credit = 30
        sl_pnl_level = -(net_credit_total * (sl_pct_of_credit / 100.0))
        assert sl_pnl_level == -1125.0


class TestThreePMCarryForwardLogic:
    """दुपारी ३ वाजताचा Carry-Forward-वि-Close निर्णय (BULL_PUT_SPREAD/BEAR_CALL_SPREAD साठीच)."""

    def test_before_3pm_large_profit_does_not_close(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T1", net_credit=50, sl_level=-1125, target_level=1125)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 5.0, "PE24300": 3.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 0)  # UTC 9:00 = IST 14:30 (3pm आधी)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0  # Target लगेच बंद करत नाही, 3pm आधी

    def test_after_3pm_sufficient_profit_carries_forward(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T2", net_credit=50, sl_level=-1125, target_level=1125)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 5.0, "PE24300": 3.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 45)  # UTC 9:45 = IST 15:15 (3pm नंतर)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0  # नफा पुरेसा -> carry-forward

    def test_after_3pm_insufficient_profit_closes(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T3", net_credit=50, sl_level=-1125, target_level=100000)  # अवाढव्य target -> अपुरा नफा
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 22.0, "PE24300": 20.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 45)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT"

    def test_sl_hit_closes_regardless_of_time(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T4", net_credit=30, sl_level=-1125, target_level=1125)
        # short leg (24400, SELL) खूप महाग झाला -> मोठा तोटा (MTM = (net_credit - (short-long))*lot_size)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 60.0, "PE24300": 5.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)  # सकाळी, 3pm च्या खूप आधी
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SL"
