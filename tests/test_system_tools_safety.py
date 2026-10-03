"""tests/test_system_tools_safety.py -- DB Restore ची तपासणी आणि Broker Reconciliation (अनेक symbols + MCX)."""
import json
import sqlite3

import pytest

import database
import trading_engine


def _make_db(path, with_trades=True):
    conn = sqlite3.connect(path)
    if with_trades:
        conn.execute("CREATE TABLE live_trades (trade_id TEXT)")
        conn.execute("INSERT INTO live_trades VALUES ('T1')")
    else:
        conn.execute("CREATE TABLE other (x INTEGER)")
    conn.commit()
    conn.close()
    with open(path, "rb") as f:
        return f.read()


class TestRestoreValidation:
    @pytest.fixture
    def live(self, tmp_path, monkeypatch):
        live_path = str(tmp_path / "live.db")
        original = _make_db(live_path)
        monkeypatch.setattr(database, "DB_PATH", live_path)
        return live_path, original

    @pytest.mark.parametrize("bad", [b"", b"hello world, not a database", b"SQLite format 3\x00" + b"\x00" * 10])
    def test_garbage_is_rejected_and_live_db_untouched(self, live, bad):
        live_path, original = live
        ok, msg = database.restore_db_from_bytes(bad)
        assert ok is False and "अबाधित" in msg
        assert open(live_path, "rb").read() == original

    def test_valid_sqlite_without_live_trades_is_rejected(self, live, tmp_path):
        live_path, original = live
        other = _make_db(str(tmp_path / "other.db"), with_trades=False)
        ok, msg = database.restore_db_from_bytes(other)
        assert ok is False and "live_trades" in msg
        assert open(live_path, "rb").read() == original

    def test_valid_backup_replaces_live_db_and_keeps_safety_copy(self, live, tmp_path):
        live_path, original = live
        c = sqlite3.connect(str(tmp_path / "new.db"))
        c.execute("CREATE TABLE live_trades (trade_id TEXT)")
        c.execute("INSERT INTO live_trades VALUES ('NEW1')")
        c.commit(); c.close()
        new_bytes = open(tmp_path / "new.db", "rb").read()
        ok, _ = database.restore_db_from_bytes(new_bytes)
        assert ok is True
        assert sqlite3.connect(live_path).execute("SELECT trade_id FROM live_trades").fetchall() == [("NEW1",)]
        assert open(live_path + ".before_restore.bak", "rb").read() == original


class TestReconcileMultiSymbol:
    @pytest.fixture
    def db(self, tmp_path, monkeypatch):
        path = str(tmp_path / "r.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE live_trades (trade_id TEXT, symbol TEXT, legs_json TEXT, strikes_summary TEXT, status TEXT, mode TEXT)")
        rows = [
            ("N1", "NIFTY", json.dumps([{"instrument_key": "NSE_FO|A", "role": "short"}]), "A", "OPEN", "LIVE"),
            ("S1", "SILVER", json.dumps([{"instrument_key": "MCX_FO|S", "role": "fut"}]), "S", "OPEN", "LIVE"),
            ("P1", "SILVER", json.dumps([{"instrument_key": "MCX_FO|P", "role": "fut"}]), "P", "OPEN", "PAPER"),
        ]
        conn.executemany("INSERT INTO live_trades VALUES (?,?,?,?,?,?)", rows)
        conn.commit(); conn.close()
        monkeypatch.setattr(trading_engine, "DB_PATH", path)
        return path

    def _run(self, monkeypatch, positions, symbol):
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda tok: positions)
        return trading_engine.reconcile_positions("tok", symbol)

    def test_single_symbol_string_still_works(self, db, monkeypatch):
        r = self._run(monkeypatch, [{"instrument_token": "NSE_FO|A", "quantity": 75}], "NIFTY")
        assert r["status"] == "ok" and r["mismatches"] == []

    def test_mcx_trade_missing_at_broker_is_reported_with_symbol(self, db, monkeypatch):
        r = self._run(monkeypatch, [{"instrument_token": "NSE_FO|A", "quantity": 75}], ["NIFTY", "SILVER"])
        assert [(m["trade_id"], m["symbol"]) for m in r["mismatches"]] == [("S1", "SILVER")]  # PAPER trade वगळला

    def test_other_symbols_positions_are_not_called_unexplained(self, db, monkeypatch):
        positions = [{"instrument_token": "NSE_FO|A", "quantity": 75}, {"instrument_token": "MCX_FO|S", "quantity": 1}]
        r = self._run(monkeypatch, positions, "NIFTY")  # MCX position दुसऱ्या symbol चा tracked trade आहे
        assert r["unexplained_broker_positions"] == []
        r2 = self._run(monkeypatch, positions + [{"instrument_token": "MCX_FO|ZZ", "quantity": 2}], "NIFTY")
        assert [p["instrument_key"] for p in r2["unexplained_broker_positions"]] == ["MCX_FO|ZZ"]
