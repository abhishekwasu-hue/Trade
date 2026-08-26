"""
tests/test_cloud_db.py
--------------------------
cloud_db.py (Supabase/PostgreSQL, OI Snapshot साठी) — graceful fallback + SQL logic. आणि
upstox_api.py चं केंद्रीकृत Symbol->Instrument Key mapping (SENSEX सहित).

⚠️ प्रामाणिक टीप: cloud_db.py चा प्रत्यक्ष खऱ्या Supabase/PostgreSQL सर्व्हरशी जोडणी होणारा भाग या
वातावरणात (network प्रतिबंधामुळे) चाचणी करता आलेला नाही — फक्त graceful-fallback आणि mocked-connection
logic इथे तपासलं आहे.
"""
import os
from unittest.mock import MagicMock

import cloud_db
from upstox_api import get_instrument_key


class TestGracefulFallback:
    def test_not_configured_returns_false(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
        monkeypatch.setattr(cloud_db, "CONFIG_PATH", str(tmp_path / "cfg.json"))
        assert cloud_db.is_cloud_db_configured() is False

    def test_get_connection_returns_none_when_unconfigured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
        monkeypatch.setattr(cloud_db, "CONFIG_PATH", str(tmp_path / "cfg.json"))
        assert cloud_db.get_connection() is None

    def test_save_snapshot_returns_false_without_crashing(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
        monkeypatch.setattr(cloud_db, "CONFIG_PATH", str(tmp_path / "cfg.json"))
        result = cloud_db.save_oi_snapshot_cloud("NIFTY", "2026-08-25", "10:00", 100, 120, 20, 0, "BULLISH", 24500, 50, 45)
        assert result is False

    def test_history_returns_empty_list_without_crashing(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
        monkeypatch.setattr(cloud_db, "CONFIG_PATH", str(tmp_path / "cfg.json"))
        assert cloud_db.get_oi_history_cloud("NIFTY", "2026-08-25") == []


class TestSQLLogicWithMockedConnection:
    def test_save_uses_on_conflict_do_nothing(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.save_oi_snapshot_cloud("NIFTY", "2026-08-25", "10:00", 100, 120, 20, 5, "BULLISH", 24500, 50, 45)
        assert result is True

        sql, params = mock_cursor.execute.call_args[0]
        assert "ON CONFLICT" in sql
        assert params == ("NIFTY", "2026-08-25", "10:00", 100, 120, 20, 5, "BULLISH", 24500, 50, 45)
        assert mock_conn.commit.called


class TestInstrumentKeyMapping:
    def test_nifty_unchanged(self):
        assert get_instrument_key("NIFTY") == "NSE_INDEX|Nifty 50"

    def test_banknifty_unchanged(self):
        assert get_instrument_key("BANKNIFTY") == "NSE_INDEX|Nifty Bank"

    def test_sensex_new(self):
        assert get_instrument_key("SENSEX") == "BSE_INDEX|SENSEX"

    def test_unknown_symbol_falls_back_to_nifty(self):
        assert get_instrument_key("UNKNOWN") == "NSE_INDEX|Nifty 50"
