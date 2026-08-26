"""
tests/test_oi_snapshot_collector.py
----------------------------------------
oi_analysis.fetch_and_save_oi_snapshot (Dashboard + oi_snapshot_collector.py दोन्ही वापरतात) —
browser बंद असतानाही OI Diff Snapshot साठवला जावा यासाठीची सुधारणा.
"""
import datetime
import sqlite3
import tempfile

import pytz
import pytest

import database
from oi_analysis import fetch_and_save_oi_snapshot

IST = pytz.timezone("Asia/Kolkata")


def _fake_fetch(call_ltp=50.0, put_ltp=45.0, call_oi=10000, put_oi=12000):
    def _fetch(token, symbol):
        strikes = list(range(24200, 24800, 50))
        chain = []
        for k in strikes:
            chain.append({
                "strike_price": k, "underlying_spot_price": 24500,
                "call_options": {"instrument_key": f"CE{k}", "market_data": {"ltp": call_ltp, "oi": call_oi}},
                "put_options": {"instrument_key": f"PE{k}", "market_data": {"ltp": put_ltp, "oi": put_oi}},
            })
        return chain, "OK"
    return _fetch


@pytest.fixture
def temp_db(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    yield tmpdb


class TestFetchAndSaveOISnapshot:
    def test_first_snapshot_saves_correctly(self, temp_db):
        t1 = datetime.datetime(2026, 8, 25, 10, 5, tzinfo=IST)
        result, status = fetch_and_save_oi_snapshot("tok", "NIFTY", _fake_fetch(), lambda: t1, temp_db)
        assert status == "OK"
        assert result["snapshot_time"] == "10:00"
        assert result["atm_strike"] == 24500

    def test_duplicate_slot_does_not_create_new_row(self, temp_db):
        t1 = datetime.datetime(2026, 8, 25, 10, 5, tzinfo=IST)
        fetch_and_save_oi_snapshot("tok", "NIFTY", _fake_fetch(), lambda: t1, temp_db)
        _, status2 = fetch_and_save_oi_snapshot("tok", "NIFTY", _fake_fetch(), lambda: t1, temp_db)
        assert status2 == "ALREADY_EXISTS"

        conn = sqlite3.connect(temp_db)
        count = conn.execute("SELECT COUNT(*) FROM oi_diff_snapshots").fetchone()[0]
        conn.close()
        assert count == 1

    def test_first_snapshot_direction_is_neutral_not_none(self, temp_db):
        """पहिल्याच snapshot ला prev data नसतं -- direction None ऐवजी सुरक्षित 'NEUTRAL' असायला हवं
        (Dashboard चं banner-रंग-निवड dict-lookup None वर क्रॅश होईल, म्हणून हे महत्त्वाचं)."""
        t1 = datetime.datetime(2026, 8, 25, 10, 5, tzinfo=IST)
        result, _ = fetch_and_save_oi_snapshot("tok", "NIFTY", _fake_fetch(), lambda: t1, temp_db)
        assert result["oi_price_direction"] == "NEUTRAL"
        assert result["oi_price_direction"] is not None

    def test_put_writing_detected_across_two_snapshots(self, temp_db):
        t1 = datetime.datetime(2026, 8, 25, 10, 5, tzinfo=IST)
        fetch_and_save_oi_snapshot("tok", "NIFTY", _fake_fetch(), lambda: t1, temp_db)

        t2 = datetime.datetime(2026, 8, 25, 10, 15, tzinfo=IST)
        result2, _ = fetch_and_save_oi_snapshot("tok", "NIFTY", _fake_fetch(put_oi=15000, put_ltp=40.0), lambda: t2, temp_db)
        assert "Writing" in result2["put_oi_price_class"]
        assert result2["oi_price_direction"] == "BULLISH"

    def test_missing_option_chain_returns_none_gracefully(self, temp_db):
        def _empty_fetch(token, symbol):
            return None, "API डाऊन"
        t1 = datetime.datetime(2026, 8, 25, 10, 5, tzinfo=IST)
        result, status = fetch_and_save_oi_snapshot("tok", "NIFTY", _empty_fetch, lambda: t1, temp_db)
        assert result is None
        assert "API डाऊन" in status
