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
from unittest.mock import MagicMock, patch

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


class TestUpstoxTokenStorage:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Upstox Access Token Request + Notifier Webhook
    पद्धतीने रोज एका टॅपवर मिळणारा token, Supabase मध्ये साठवण्यासाठी. GitHub Actions आणि Streamlit
    Dashboard दोन्ही इथूनच वाचतील (मॅन्युअल paste टाळण्यासाठी).
    """

    def test_save_upstox_token_inserts_correctly(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.save_upstox_token("fake_token_abc123")
        assert result is True
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO upstox_tokens" in sql
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Multi-Broker Multi-Account फीचर आल्यावर
        # save_upstox_token(access_token, account_id=None) झालं, त्यामुळे params आता 2-tuple
        # (account_id न दिल्यास None) — जुनी 1-tuple अपेक्षा (backward-incompatible) होती.
        assert params == ("fake_token_abc123", None)
        assert mock_conn.commit.called

    def test_get_latest_upstox_token_returns_most_recent(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("latest_token_xyz",)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        token = cloud_db.get_latest_upstox_token()
        assert token == "latest_token_xyz"
        sql = mock_cursor.execute.call_args[0][0]
        assert "ORDER BY received_at DESC" in sql

    def test_no_connection_returns_safe_defaults(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.save_upstox_token("x") is False
        assert cloud_db.get_latest_upstox_token() is None

    def test_no_token_stored_returns_none(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)
        assert cloud_db.get_latest_upstox_token() is None


class TestStrikeOIHistory:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या "Multi Strike OI"/"OI Change Replay"
    सारखं, प्रत्येक strike चा OI इतिहास Supabase मध्ये साठवण्यासाठी.
    """

    def test_save_strike_oi_snapshot_inserts_both_ce_and_pe(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        strikes_data = [{"strike": 24000, "ce_oi": 10000, "pe_oi": 12000}]
        result = cloud_db.save_strike_oi_snapshot("NIFTY", "2026-09-03", "10:00", strikes_data)
        assert result is True
        assert mock_cursor.execute.call_count == 2  # CE + PE
        assert mock_conn.commit.called

    def test_save_multiple_strikes(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        strikes_data = [{"strike": 24000, "ce_oi": 10000, "pe_oi": 12000},
                         {"strike": 24050, "ce_oi": 8000, "pe_oi": 9000}]
        cloud_db.save_strike_oi_snapshot("NIFTY", "2026-09-03", "10:00", strikes_data)
        assert mock_cursor.execute.call_count == 4  # 2 strikes x (CE+PE)

    def test_get_strike_oi_history_returns_dataframe(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(24000.0, "CE", "10:00", 10000)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        df = cloud_db.get_strike_oi_history("NIFTY", "2026-09-03")
        assert len(df) == 1
        assert list(df.columns) == ["strike", "option_type", "snapshot_time", "oi"]

    def test_get_strike_oi_history_with_strike_filter(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        cloud_db.get_strike_oi_history("NIFTY", "2026-09-03", strikes=[24000, 24050])
        sql = mock_cursor.execute.call_args[0][0]
        assert "strike IN" in sql

    def test_no_connection_returns_safe_defaults(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.save_strike_oi_snapshot("NIFTY", "2026-09-03", "10:00", []) is False
        assert cloud_db.get_strike_oi_history("NIFTY", "2026-09-03") is None


class TestNifty1MinStorage:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — गेल्या ५+ वर्षांचा (संपूर्ण उपलब्ध इतिहास) NIFTY
    1-मिनिट OHLC डेटा, रोज आपोआप अद्ययावत होणारा, Supabase मध्ये साठवण्यासाठी.
    """

    def test_save_batch_calls_execute_values_with_correct_data(self, monkeypatch):
        from unittest.mock import MagicMock
        import datetime
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        rows = [{"timestamp": datetime.datetime(2026, 9, 4, 9, 15), "open": 24000, "high": 24010,
                 "low": 23990, "close": 24005, "volume": 0}]
        with patch("psycopg2.extras.execute_values") as mock_execute_values:
            result = cloud_db.save_nifty_1min_batch(rows)
            assert result is True
            assert mock_execute_values.called
            sql_arg = mock_execute_values.call_args[0][1]
            assert "ON CONFLICT (timestamp) DO NOTHING" in sql_arg
            values_arg = mock_execute_values.call_args[0][2]
            assert len(values_arg) == 1

    def test_save_batch_empty_list_is_noop_success(self, monkeypatch):
        assert cloud_db.save_nifty_1min_batch([]) is True

    def test_get_range_returns_dataframe(self, monkeypatch):
        from unittest.mock import MagicMock
        import datetime
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(datetime.datetime(2026, 9, 4, 9, 15), 24000, 24010, 23990, 24005, 0)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        df = cloud_db.get_nifty_1min_range()
        assert len(df) == 1
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]

    def test_get_latest_timestamp(self, monkeypatch):
        from unittest.mock import MagicMock
        import datetime
        ts = datetime.datetime(2026, 9, 4, 15, 29)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (ts,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_nifty_1min_latest_timestamp()
        assert result == ts

    def test_no_connection_returns_safe_defaults(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.save_nifty_1min_batch([{"timestamp": "x", "open": 1, "high": 1, "low": 1, "close": 1}]) is False
        assert cloud_db.get_nifty_1min_range() is None
        assert cloud_db.get_nifty_1min_latest_timestamp() is None


class TestMarketZonesStorage:
    """market_zones.py चं विश्लेषण Supabase मध्ये साठवण्यासाठी — DELETE (जुनं) + INSERT (नवीन) पॅटर्न."""

    def test_save_market_zones_deletes_old_then_inserts_new(self, monkeypatch):
        from unittest.mock import MagicMock
        import pandas as pd
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        zones_df = pd.DataFrame([
            {"zone_type": "SUPPORT", "zone_low": 24000, "zone_high": 24000, "strength": 5, "formed_date": "2024-01-01", "status": "ACTIVE"},
            {"zone_type": "BULLISH_OB", "zone_low": 23900, "zone_high": 23950, "strength": None, "formed_date": "2024-01-02", "status": "FILLED"},
        ])
        result = cloud_db.save_market_zones(zones_df, "NIFTY")
        assert result is True
        # DELETE (1) + प्रत्येक zone साठी INSERT (2) = 3 एकूण calls
        assert mock_cursor.execute.call_count == 3
        first_call_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "DELETE FROM market_zones" in first_call_sql

    def test_get_market_zones_filters_by_status(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("NIFTY", "SUPPORT", 24000.0, 24000.0, 5.0, "2024-01-01", "ACTIVE")]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_market_zones("NIFTY", status="ACTIVE")
        assert len(result) == 1
        assert result.iloc[0]["status"] == "ACTIVE"
        sql = mock_cursor.execute.call_args[0][0]
        assert "status = %s" in sql

    def test_no_connection_returns_safe_defaults(self, monkeypatch):
        import pandas as pd
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.save_market_zones(pd.DataFrame(), "NIFTY") is False
        assert cloud_db.get_market_zones("NIFTY") is None


class TestSignalLog:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — High-Frequency 1-मिनिट S/R रणनीतीचा संपूर्ण
    intraday Signal Log (trade झाला किंवा न झाला तरीही) Dashboard वर दाखवण्यासाठी.
    """

    def test_save_signal_log_inserts_correctly(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        entry = {"symbol": "NIFTY", "trade_date": "2026-09-05", "signal_time": "2026-09-05 10:15",
                  "level_type": "DYNAMIC_SR_SUPPORT", "level_price": 23900.0, "hit_type": "TOUCH",
                  "direction": "BULLISH", "ltp_at_signal": 23901.0, "trade_status": "OPENED", "reason": ""}
        result = cloud_db.save_signal_log(entry)
        assert result is True
        assert mock_cursor.execute.called

    def test_get_signal_log_returns_dataframe(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("2026-09-05 10:15", "DYNAMIC_SR_SUPPORT", 23900.0, "TOUCH", "BULLISH", 23901.0, "OPENED", "")]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        df = cloud_db.get_signal_log("NIFTY", "2026-09-05")
        assert len(df) == 1
        assert list(df.columns) == ["signal_time", "level_type", "level_price", "hit_type", "direction", "ltp_at_signal", "trade_status", "reason"]

    def test_no_connection_returns_safe_defaults(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.save_signal_log({"symbol": "NIFTY", "trade_date": "x", "signal_time": "x",
                                          "level_type": "x", "level_price": 1, "hit_type": "x", "direction": "x"}) is False
        assert cloud_db.get_signal_log("NIFTY", "2026-09-05") is None


class TestSRv2StrategyState:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Nifty SRv2 Momentum-Filter Reversal" रणनीतीचं
    One-Touch + Cooldown राज्य, Supabase मध्ये (GitHub Actions प्रत्येक वेळी नवीन environment असल्याने).
    """

    def test_get_state_returns_safe_defaults_when_no_row(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        state = cloud_db.get_srv2_state("NIFTY")
        assert state == {"last_tested_level": None, "last_sl_hit_time": None}

    def test_get_state_returns_existing_row(self, monkeypatch):
        import datetime
        ts = datetime.datetime(2026, 9, 5, 10, 0)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (23900.0, ts)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        state = cloud_db.get_srv2_state("NIFTY")
        assert state["last_tested_level"] == 23900.0
        assert state["last_sl_hit_time"] == ts

    def test_save_state_uses_upsert(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.save_srv2_state("NIFTY", last_tested_level=23900.0, last_sl_hit_time=None)
        assert result is True
        sql = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT (symbol) DO UPDATE" in sql

    def test_no_connection_returns_safe_defaults(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.get_srv2_state("NIFTY") == {"last_tested_level": None, "last_sl_hit_time": None}
        assert cloud_db.save_srv2_state("NIFTY") is False


class TestGetEffectiveUpstoxToken:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Upstox Token Webhook (VPS, रोज
    आपोआप Supabase मध्ये token) पूर्ण automation साठी वापरण्यायोग्य -- CLI/GitHub Secret दिलेला
    असेल तर तोच (backward-compatible), नसेल तर Supabase कडून आपोआप.
    """

    def test_cli_token_takes_priority(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_latest_upstox_token", lambda: "should_not_be_used")
        result = cloud_db.get_effective_upstox_token("manual_token_123")
        assert result == "manual_token_123"

    def test_empty_cli_token_falls_back_to_supabase(self, monkeypatch):
        """🎓 GitHub Secret undefined असताना bash मध्ये रिकामी स्ट्रिंग येते -- तीही falsy मानायला हवी."""
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Multi-Broker Multi-Account फीचरमुळे
        # get_latest_upstox_token(account_id=None) झालं; get_effective_upstox_token आता ते
        # account_id पास करूनच कॉल करतं, त्यामुळे mock ने तो parameter स्वीकारायलाच हवा.
        monkeypatch.setattr(cloud_db, "get_latest_upstox_token", lambda account_id=None: "webhook_token_789")
        result = cloud_db.get_effective_upstox_token("")
        assert result == "webhook_token_789"

    def test_none_cli_token_falls_back_to_supabase(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_latest_upstox_token", lambda account_id=None: "webhook_token_789")
        result = cloud_db.get_effective_upstox_token(None)
        assert result == "webhook_token_789"

    def test_neither_available_returns_none(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_latest_upstox_token", lambda account_id=None: None)
        result = cloud_db.get_effective_upstox_token(None)
        assert result is None

    def test_cli_token_present_never_queries_supabase(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_get_latest = MagicMock()
        monkeypatch.setattr(cloud_db, "get_latest_upstox_token", mock_get_latest)
        cloud_db.get_effective_upstox_token("manual_token_123")
        assert not mock_get_latest.called


class TestGetZoneHitsToday:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit Dynamic S/R) — established एकाच zone ला
    आजपर्यंत किती वेळा hit झालाय आणि शेवटचा hit केव्हा — established signal_log वरून (वेगळं
    table/column न वापरता)."""

    def test_no_hits_returns_zero_and_none(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 0
        assert last_time is None

    def test_two_hits_returns_count_and_latest_time(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("2026-09-08 11:30:00",), ("2026-09-08 09:20:00",)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 2
        assert last_time == "2026-09-08 11:30:00"  # established ORDER BY ... DESC मुळे सर्वात अलीकडची पहिली

    def test_no_connection_returns_safe_default(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        count, last_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 0
        assert last_time is None

    def test_query_error_returns_safe_default(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("db error")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 0
        assert last_time is None


class TestGetTokenAgeHours:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — check_token_freshness.py साठी, token किती
    जुना आहे ते तपासण्यासाठीचं helper."""

    def test_returns_age_for_single_account(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5.5,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        age = cloud_db.get_token_age_hours()
        assert age == 5.5
        call_args = mock_cursor.execute.call_args[0]
        assert "account_id IS NULL" in call_args[0]

    def test_returns_age_for_specific_account(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2.0,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        age = cloud_db.get_token_age_hours(account_id="acct1")
        assert age == 2.0
        sql, params = mock_cursor.execute.call_args[0]
        assert "account_id=%s" in sql
        assert params == ("acct1",)

    def test_no_token_returns_none(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        assert cloud_db.get_token_age_hours() is None

    def test_no_connection_returns_none(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.get_token_age_hours() is None

    def test_query_error_returns_none(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("db error")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        assert cloud_db.get_token_age_hours() is None


class TestMergeDynamicSr1mZones:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (10-मिनिट हलका 1M refresh, cron सोबत) — merge-logic:
    जुळणारे जुने levels तसेच ठेवणे (Multi-Hit history टिकावी), न जुळणारे जुने काढणे, नवीन जोडणे."""

    def _mock_conn(self, existing_rows):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = existing_rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_matching_existing_level_kept_no_insert_no_delete(self, monkeypatch):
        # जुना support level 23900.0 -- नवीन गणनेतला 23901.0 (0.02% च्या आत, जुळायला हवा)
        existing_rows = [(1, "DYNAMIC_SR_SUPPORT_1M", 23900.0)]
        mock_conn, mock_cursor = self._mock_conn(existing_rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        dyn_sr = {"support": [{"level": 23901.0, "touches": 3}], "resistance": []}
        result = cloud_db.merge_dynamic_sr_1m_zones("NIFTY", dyn_sr)
        assert result is True

        insert_calls = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO market_zones" in c[0][0]]
        delete_calls = [c for c in mock_cursor.execute.call_args_list if "DELETE FROM market_zones" in c[0][0]]
        assert len(insert_calls) == 0  # जुळलं -- नवीन insert नाही
        assert len(delete_calls) == 0  # जुळलं -- delete नाही

    def test_new_candidate_not_matching_existing_gets_inserted(self, monkeypatch):
        existing_rows = [(1, "DYNAMIC_SR_SUPPORT_1M", 23900.0)]
        mock_conn, mock_cursor = self._mock_conn(existing_rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        # जुन्यापासून खूप दूर (जुळत नाही, नवीन म्हणून जोडायला हवा)
        dyn_sr = {"support": [{"level": 24500.0, "touches": 3}], "resistance": []}
        result = cloud_db.merge_dynamic_sr_1m_zones("NIFTY", dyn_sr)
        assert result is True

        insert_calls = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO market_zones" in c[0][0]]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1][2] == 24500.0  # zone_low param

    def test_existing_level_not_in_new_candidates_is_never_deleted(self, monkeypatch):
        """🎓 वापरकर्त्याने सापडवलेला मुद्दा — मोठा gap झाल्यावर जुना पण खरा level "सर्वोत्तम ५"
        यादीतून बाहेर पडला, तरी DELETE होता कामा नये — किंमत नंतर तिथे परत आली तर उपयोगी पडावा
        म्हणून, तो तसाच ठेवायला हवा."""
        existing_rows = [(1, "DYNAMIC_SR_SUPPORT_1M", 23900.0), (2, "DYNAMIC_SR_RESISTANCE_1M", 24500.0)]
        mock_conn, mock_cursor = self._mock_conn(existing_rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        # दोन्ही आता नव्या गणनेत सापडतच नाहीत -- पण DELETE होता कामा नये
        dyn_sr = {"support": [], "resistance": []}
        result = cloud_db.merge_dynamic_sr_1m_zones("NIFTY", dyn_sr)
        assert result is True

        delete_calls = [c for c in mock_cursor.execute.call_args_list if "DELETE FROM market_zones" in c[0][0]]
        assert len(delete_calls) == 0  # कधीच DELETE नाही -- फक्त रात्रीच्या पूर्ण refresh नेच निवृत्त होणार

    def test_no_connection_returns_false(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        result = cloud_db.merge_dynamic_sr_1m_zones("NIFTY", {"support": [], "resistance": []})
        assert result is False


class TestMergeDynamicSrZonesGeneric:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — merge_dynamic_sr_1m_zones() आता generic
    merge_dynamic_sr_zones() चा फक्त "1M" साठीचा wrapper आहे — तेच function "15M" साठी (SRv2,
    5-मिनिट cron सोबत) पुनर्वापर केलं जातं."""

    def _mock_conn(self, existing_rows):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = existing_rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_15m_uses_correct_zone_type_strings(self, monkeypatch):
        existing_rows = [(1, "DYNAMIC_SR_SUPPORT_15M", 23900.0)]
        mock_conn, mock_cursor = self._mock_conn(existing_rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        dyn_sr = {"support": [{"level": 24500.0, "touches": 3}], "resistance": []}
        result = cloud_db.merge_dynamic_sr_zones("NIFTY", dyn_sr, "15M")
        assert result is True

        insert_calls = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO market_zones" in c[0][0]]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1][1] == "DYNAMIC_SR_SUPPORT_15M"  # zone_type param -- 1M नाही

    def test_1m_and_15m_do_not_interfere_with_each_other(self, monkeypatch):
        """15M साठी merge करताना, त्याच symbol चे existing 1M zones अजिबात touch होऊ नयेत."""
        existing_rows = [(1, "DYNAMIC_SR_SUPPORT_15M", 23900.0)]  # SELECT ने फक्त 15M रो दिली
        mock_conn, mock_cursor = self._mock_conn(existing_rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        dyn_sr = {"support": [{"level": 23901.0, "touches": 3}], "resistance": []}
        cloud_db.merge_dynamic_sr_zones("NIFTY", dyn_sr, "15M")

        select_calls = [c for c in mock_cursor.execute.call_args_list if "SELECT" in c[0][0]]
        assert "DYNAMIC_SR_SUPPORT_15M" in select_calls[0][0][1]
        assert "DYNAMIC_SR_SUPPORT_1M" not in select_calls[0][0][1]


class TestSrv2Settings:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — SRv2 चे lots/hedge_width_points Dashboard वरून
    बदलता येण्यासाठी (hardcode नाही)."""

    def test_get_settings_returns_default_when_no_row(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_srv2_settings("NIFTY")
        assert result == {"lots": 1, "hedge_width_points": 100.0}

    def test_get_settings_returns_saved_values(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3, 150.0)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_srv2_settings("NIFTY")
        assert result == {"lots": 3, "hedge_width_points": 150.0}

    def test_get_settings_no_connection_returns_default(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        result = cloud_db.get_srv2_settings("NIFTY")
        assert result == {"lots": 1, "hedge_width_points": 100.0}

    def test_save_settings_calls_upsert(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.save_srv2_settings("NIFTY", lots=2, hedge_width_points=75.0)
        assert result is True
        insert_calls = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO srv2_settings" in c[0][0]]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1] == ("NIFTY", 2, 75.0)

    def test_save_settings_no_connection_returns_false(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        result = cloud_db.save_srv2_settings("NIFTY", lots=2, hedge_width_points=75.0)
        assert result is False


class TestGetNextLevelInDirection:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Timeframe SRv2, Next-Level-Exit) — 15M/30M/60M
    पूल केलेल्या levels मधून, entry_level_price पासून favourable दिशेने सर्वात जवळचा शोधणे."""

    def _mock_conn(self, rows):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_bullish_returns_nearest_level_above(self, monkeypatch):
        # entry=23900, वरचे उमेदवार: 23950, 24100 -- सर्वात जवळचा (23950) यायला हवा
        rows = [(23950.0,), (24100.0,), (23800.0,)]  # 23800 खालचा, वगळायला हवा
        monkeypatch.setattr(cloud_db, "get_connection", lambda: self._mock_conn(rows))
        result = cloud_db.get_next_level_in_direction("NIFTY", 23900.0, direction_bullish=True)
        assert result == 23950.0

    def test_bearish_returns_nearest_level_below(self, monkeypatch):
        rows = [(23800.0,), (23600.0,), (24000.0,)]  # 24000 वरचा, वगळायला हवा
        monkeypatch.setattr(cloud_db, "get_connection", lambda: self._mock_conn(rows))
        result = cloud_db.get_next_level_in_direction("NIFTY", 23900.0, direction_bullish=False)
        assert result == 23800.0

    def test_no_candidate_in_direction_returns_none(self, monkeypatch):
        rows = [(23800.0,)]  # फक्त खालचाच -- bullish (वरचा हवाय) साठी काहीच नाही
        monkeypatch.setattr(cloud_db, "get_connection", lambda: self._mock_conn(rows))
        result = cloud_db.get_next_level_in_direction("NIFTY", 23900.0, direction_bullish=True)
        assert result is None

    def test_no_connection_returns_none(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        result = cloud_db.get_next_level_in_direction("NIFTY", 23900.0, direction_bullish=True)
        assert result is None
