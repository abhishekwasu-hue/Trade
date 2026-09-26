"""
tests/test_cloud_db.py
--------------------------
cloud_db.py (Supabase/PostgreSQL, OI Snapshot साठी) — graceful fallback + SQL logic. आणि
upstox_api.py चं केंद्रीकृत Symbol->Instrument Key mapping (SENSEX सहित).

⚠️ प्रामाणिक टीप: cloud_db.py चा प्रत्यक्ष खऱ्या Supabase/PostgreSQL सर्व्हरशी जोडणी होणारा भाग या
वातावरणात (network प्रतिबंधामुळे) चाचणी करता आलेला नाही — फक्त graceful-fallback आणि mocked-connection
logic इथे तपासलं आहे.
"""
import datetime
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

    def test_save_encrypts_when_key_configured(self, monkeypatch):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा (Plaintext Broker Credentials) -- TOKEN_ENCRYPTION_KEY
        सेट असेल तर DB मध्ये plaintext token कधीच जाता कामा नये."""
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)
        monkeypatch.setattr(cloud_db, "encrypt_token", lambda t: f"enc:v1:{t}-encrypted")

        cloud_db.save_upstox_token("fake_token_abc123")
        sql, params = mock_cursor.execute.call_args[0]
        assert params == ("enc:v1:fake_token_abc123-encrypted", None)

    def test_get_decrypts_stored_value(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("enc:v1:something",)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)
        monkeypatch.setattr(cloud_db, "decrypt_token", lambda t: "decrypted_plaintext_token")

        token = cloud_db.get_latest_upstox_token()
        assert token == "decrypted_plaintext_token"


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

    def test_save_market_zones_delete_covers_all_zone_types(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून मागे-घेतलेली सुधारणा — DYNAMIC_SR_*_1M/*_5M zones ला
        nightly DELETE मधून कायमचं वगळणं चुकीचं ठरलं (जुने levels कधीच refresh न होता कायमचे
        ACTIVE राहून trade घेऊ शकत होते). आता DELETE पुन्हा साधं, symbol-व्यापी (कुठलाही
        zone_type वगळत नाही) -- compute_all_zones() आता 1M/5M सुद्धा रोज ताजे generate करतं,
        त्यामुळे इथे विशेष अपवाद लागत नाही."""
        from unittest.mock import MagicMock
        import pandas as pd
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        zones_df = pd.DataFrame([
            {"zone_type": "SUPPORT", "zone_low": 24000, "zone_high": 24000, "strength": 5, "formed_date": "2024-01-01", "status": "ACTIVE"},
        ])
        cloud_db.save_market_zones(zones_df, "NIFTY")
        delete_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "_1M" not in delete_sql and "_5M" not in delete_sql
        assert "NOT IN" not in delete_sql

    def test_scoped_delete_limits_to_given_zone_types(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेला `scoped=True` -- NIFTY चे 15M/30M/60M zones intraday
        वारंवार ताजे करताना, त्याच वेळी dynamic_sr_instant_trader.py जपत असलेले 1M/5M live zones
        सुरक्षित (अबाधित) राहायला हवेत -- DELETE फक्त दिलेल्या zones_df मधल्या zone_types पुरतंच
        मर्यादित असायला हवं, symbol-व्यापी नाही."""
        from unittest.mock import MagicMock
        import pandas as pd
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        zones_df = pd.DataFrame([
            {"zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": 24000, "zone_high": 24000,
             "strength": 3, "formed_date": "2024-01-01", "status": "ACTIVE"},
        ])
        result = cloud_db.save_market_zones(zones_df, "NIFTY", scoped=True)
        assert result is True
        delete_sql, delete_params = mock_cursor.execute.call_args_list[0][0]
        assert "DELETE FROM market_zones" in delete_sql
        assert "zone_type = ANY" in delete_sql
        assert delete_params == ("NIFTY", ["DYNAMIC_SR_SUPPORT_15M"])
        # DELETE (1) + INSERT (1) = 2 एकूण calls -- 1M/5M/इतर zone_types साठी कुठलाही DELETE नाही
        assert mock_cursor.execute.call_count == 2

    def test_scoped_true_with_empty_df_skips_delete_entirely(self, monkeypatch):
        """पुरेसा candle-डेटा नसेल तर zones_df रिकामा असू शकतो -- तेव्हा scoped DELETE अजिबात
        चालवायचा नाही (जुने zones तसेच सुरक्षित राहायला हवेत, चुकून सगळंच पुसलं जाऊ नये)."""
        from unittest.mock import MagicMock
        import pandas as pd
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.save_market_zones(pd.DataFrame(columns=["zone_type", "zone_low", "zone_high", "strength", "formed_date", "status"]), "NIFTY", scoped=True)
        assert result is True
        assert mock_cursor.execute.call_count == 0


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

    def test_real_trade_attempt_never_deduped_even_if_identical(self, monkeypatch):
        """🎓 trade_status="OPENED" (खरा order attempt) असलेली नोंद -- मागची तशीच असली तरी कधीच
        dedupe होऊ नये (SELECT dedup-check अजिबात चालवलाच जाऊ नये, थेट INSERT)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        entry = {"symbol": "NIFTY", "trade_date": "2026-09-05", "signal_time": "2026-09-05 10:16",
                  "level_type": "DYNAMIC_SR_SUPPORT_5M", "level_price": 23900.0, "hit_type": "TOUCH",
                  "direction": "BULLISH", "ltp_at_signal": 23901.0, "trade_status": "OPENED", "reason": ""}
        cloud_db.save_signal_log(entry)
        assert mock_cursor.execute.call_count == 1  # फक्त INSERT, SELECT dedup-check नाही
        assert "INSERT INTO signal_log" in mock_cursor.execute.call_args_list[0][0][0]

    def test_identical_no_action_entry_skips_reinsert(self, monkeypatch):
        """🎓 वापरकर्त्याने सापडवलेली bug (Dashboard वर Signal Log "2-3 वेळा repeat") — त्याच दिवशी,
        त्याच level साठी, सर्वात अलीकडची नोंद अगदी तशीच (hit_type+trade_status) असेल, आणि
        नवीन entry मध्ये कधीच खरा trade attempt नसेल (trade_status=SKIPPED_* इ.), तर पुन्हा
        साठवली जाऊ नये."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("TOUCH", "SKIPPED_COOLDOWN_30MIN")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        entry = {"symbol": "NIFTY", "trade_date": "2026-09-05", "signal_time": "2026-09-05 10:17",
                  "level_type": "DYNAMIC_SR_SUPPORT_5M", "level_price": 23900.0, "hit_type": "TOUCH",
                  "direction": "BULLISH", "ltp_at_signal": 23902.0, "trade_status": "SKIPPED_COOLDOWN_30MIN",
                  "reason": "मागच्या hit ला फक्त 5.0 मिनिटं झालीत"}
        result = cloud_db.save_signal_log(entry)
        assert result is True
        assert mock_cursor.execute.call_count == 1  # फक्त SELECT dedup-check, INSERT नाही
        assert "SELECT" in mock_cursor.execute.call_args_list[0][0][0]

    def test_changed_reason_alone_still_deduped(self, monkeypatch):
        """🎓 code-review द्वारे सापडवलेली, पहिल्या फिक्सची त्रुटी — reason मध्ये bot script दर cycle ला
        बदलणारं जिवंत मूल्य embed करतं (उदा. cooldown चे elapsed मिनिटं, live RSI/PCR आकडा), त्यामुळे
        reason हा dedup-तुलनेचा भाग असणं चुकीचं होतं — त्यामुळे नेमकं cooldown/RSI/PCR च्या सर्वाधिक
        repeat होणाऱ्या केसेससाठीच dedup कधीच जुळायचा नाही. आता trade_status सारखाच असेल, तर reason
        वेगळा (उदा. वेगळी cooldown वेळ) असला तरी dedup व्हायलाच हवं."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("TOUCH", "SKIPPED_COOLDOWN_30MIN")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        entry = {"symbol": "NIFTY", "trade_date": "2026-09-05", "signal_time": "2026-09-05 10:18",
                  "level_type": "DYNAMIC_SR_SUPPORT_5M", "level_price": 23900.0, "hit_type": "TOUCH",
                  "direction": "BULLISH", "ltp_at_signal": 23902.0, "trade_status": "SKIPPED_COOLDOWN_30MIN",
                  "reason": "मागच्या hit ला फक्त 6.0 मिनिटं झालीत"}  # वेगळा reason, पण तोच trade_status
        cloud_db.save_signal_log(entry)
        assert mock_cursor.execute.call_count == 1  # फक्त SELECT dedup-check, INSERT नाही
        assert "SELECT" in mock_cursor.execute.call_args_list[0][0][0]

    def test_changed_trade_status_still_inserts_new_row(self, monkeypatch):
        """मागची नोंद वेगळ्या trade_status ची असेल (उदा. cooldown संपून आता RSI गेटने अडवलं), तर
        नवीन नोंद व्हायलाच हवी — हा खरा, अर्थपूर्ण state-transition आहे."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("TOUCH", "SKIPPED_COOLDOWN_30MIN")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        entry = {"symbol": "NIFTY", "trade_date": "2026-09-05", "signal_time": "2026-09-05 10:31",
                  "level_type": "DYNAMIC_SR_SUPPORT_5M", "level_price": 23900.0, "hit_type": "TOUCH",
                  "direction": "BULLISH", "ltp_at_signal": 23902.0, "trade_status": "SKIPPED_RSI_FILTER",
                  "reason": "RSI 42.0 दिशेशी जुळत नाही"}  # वेगळा trade_status
        cloud_db.save_signal_log(entry)
        assert mock_cursor.execute.call_count == 2  # SELECT + INSERT दोन्ही
        assert "INSERT INTO signal_log" in mock_cursor.execute.call_args_list[1][0][0]

    def test_no_prior_entry_inserts_normally(self, monkeypatch):
        """त्या level साठी आजची पहिलीच नोंद (fetchone -> None) -- नेहमीप्रमाणे insert व्हायला हवी."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        entry = {"symbol": "NIFTY", "trade_date": "2026-09-05", "signal_time": "2026-09-05 09:16",
                  "level_type": "DYNAMIC_SR_SUPPORT_5M", "level_price": 23900.0, "hit_type": "NO_HIT",
                  "direction": "NONE", "ltp_at_signal": None, "trade_status": None, "reason": "level ला स्पर्श आढळला नाही"}
        cloud_db.save_signal_log(entry)
        assert mock_cursor.execute.call_count == 2  # SELECT (काहीच सापडलं नाही) + INSERT
        assert "INSERT INTO signal_log" in mock_cursor.execute.call_args_list[1][0][0]

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

    def test_get_signal_log_range_returns_dataframe(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("2026-09-05 10:15", "DYNAMIC_SR_SUPPORT", 23900.0, "TOUCH", "BULLISH", 23901.0, "OPENED", ""),
            ("2026-09-03 11:20", "SUPPORT", 23800.0, "NO_HIT", "BEARISH", 23850.0, None, ""),
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        df = cloud_db.get_signal_log_range("NIFTY", "2026-09-01", "2026-09-05")
        assert len(df) == 2
        assert list(df.columns) == ["signal_time", "level_type", "level_price", "hit_type", "direction", "ltp_at_signal", "trade_status", "reason"]
        assert "BETWEEN" in mock_cursor.execute.call_args.args[0]

    def test_get_signal_log_range_no_connection_returns_none(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.get_signal_log_range("NIFTY", "2026-09-01", "2026-09-05") is None

    def test_get_signal_log_range_normalizes_date_objects_to_strings(self, monkeypatch):
        """🎓 वापरकर्त्याने सापडवलेली गंभीर bug — page_dashboard.py Signal Log tab नेहमी
        get_ist_today()/st.date_input() (datetime.date objects) पाठवतं, पण signal_log.trade_date
        column TEXT आहे. psycopg2 datetime.date ला ::date cast सकट पाठवतो -> PostgreSQL मध्ये
        "text BETWEEN date AND date" कधीच जुळायचं नाही (silently caught, None रिटर्न) -> Dashboard
        वर कायम "कुठलाही signal नाही" (चुकीचं) दिसायचं, जरी bot scripts व्यवस्थित लिहीत असले तरी.
        आता date objects आधीच "YYYY-MM-DD" string मध्ये रूपांतरित होऊनच query ला जातात."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        cloud_db.get_signal_log_range("NIFTY", datetime.date(2026, 9, 1), datetime.date(2026, 9, 18))
        bound_params = mock_cursor.execute.call_args.args[1]
        assert bound_params == ("NIFTY", "2026-09-01", "2026-09-18")
        assert all(isinstance(p, str) for p in bound_params)

    def test_get_signal_log_normalizes_date_object_to_string(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        cloud_db.get_signal_log("NIFTY", datetime.date(2026, 9, 18))
        bound_params = mock_cursor.execute.call_args.args[1]
        assert bound_params == ("NIFTY", "2026-09-18")


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
    table/column न वापरता). रिटर्न आता 3-tuple: (hit_count, last_hit_time, last_trade_time)."""

    def test_no_hits_returns_zero_and_none(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_hit_time, last_trade_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 0
        assert last_hit_time is None
        assert last_trade_time is None

    def test_two_hits_returns_count_and_latest_hit_time(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("2026-09-08 11:30:00", "SKIPPED_RSI_FILTER"), ("2026-09-08 09:20:00", "SKIPPED_RSI_FILTER"),
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_hit_time, last_trade_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 2
        assert last_hit_time == "2026-09-08 11:30:00"  # established ORDER BY ... DESC मुळे सर्वात अलीकडची पहिली
        assert last_trade_time is None  # दोन्ही touches फक्त RSI-नाकारलेले, खरा trade कधीच नाही

    def test_no_connection_returns_safe_default(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        count, last_hit_time, last_trade_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 0
        assert last_hit_time is None
        assert last_trade_time is None

    def test_query_error_returns_safe_default(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("db error")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_hit_time, last_trade_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 0
        assert last_hit_time is None
        assert last_trade_time is None

    def test_no_role_query_has_no_level_type_filter(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेला `role` पर्याय — role न दिल्यास (डीफॉल्ट) query ने
        support/resistance दोन्ही मिळून मोजायला हवं (backward compatible, जुनं वर्तन)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        sql, params = mock_cursor.execute.call_args[0]
        assert "level_type" not in sql
        assert params == ("NIFTY", "2026-09-08", 23900.0)

    def test_role_given_adds_level_type_filter(self, monkeypatch):
        """role="SUPPORT" दिलं की फक्त support-role च्या hits मोजल्या जाव्यात — तोच level नंतर
        resistance म्हणून test झाला तरी तो वेगळा (स्वतंत्र कमाल-2) counter असायला हवा."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08", role="SUPPORT")
        sql, params = mock_cursor.execute.call_args[0]
        assert "level_type LIKE" in sql
        assert params == ("NIFTY", "2026-09-08", 23900.0, "%SUPPORT%")

    def test_support_and_resistance_hits_counted_independently(self, monkeypatch):
        """एकाच किंमतीला support म्हणून 2 hits, resistance म्हणून 0 -- role="RESISTANCE" ने
        विचारल्यास अजूनही 0/2 दिसायला हवं (support चे hits resistance च्या counter मध्ये मिसळू नयेत)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def _execute(sql, params):
            if "level_type LIKE" in sql and params[-1] == "%RESISTANCE%":
                mock_cursor.fetchall.return_value = []
            else:
                mock_cursor.fetchall.return_value = [
                    ("2026-09-08 11:30:00", "OPENED"), ("2026-09-08 09:20:00", "OPENED"),
                ]

        mock_cursor.execute.side_effect = _execute
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        support_count, _, _ = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08", role="SUPPORT")
        resistance_count, _, _ = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08", role="RESISTANCE")
        assert support_count == 2
        assert resistance_count == 0

    def test_last_trade_time_ignores_rejected_touches(self, monkeypatch):
        """🎓 वापरकर्त्याने CSV export मधून सापडवलेली, गोंधळात टाकणारी वागणूक — "मागच्या hit ला
        फक्त 1 मिनिट झालं, 30 हवीत" हा cooldown message प्रत्यक्षात एका RSI-नाकारलेल्या touch वरून
        (खरा trade कधीच न होता) येत होता. आता last_trade_time साठी फक्त खरे trade attempts (उदा.
        "OPENED") मोजले जावेत -- SKIPPED_RSI_FILTER/SKIPPED_PCR_GATE/इ. कधीच नाही, जरी ते सर्वात
        अलीकडचे (rows[0]) असले तरी."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("2026-09-08 11:35:00", "SKIPPED_RSI_FILTER"),   # सर्वात अलीकडचा -- पण खरा trade नाही
            ("2026-09-08 11:20:00", "SKIPPED_PCR_GATE"),     # हाही नाही
            ("2026-09-08 10:00:00", "OPENED"),               # हाच खरा शेवटचा trade
            ("2026-09-08 09:00:00", "OPENED"),
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_hit_time, last_trade_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 4
        assert last_hit_time == "2026-09-08 11:35:00"  # touch-आधारित count/hit_time बदललेलं नाही
        assert last_trade_time == "2026-09-08 10:00:00"  # cooldown साठी मात्र फक्त खरा trade

    def test_last_trade_time_none_when_only_rejected_touches(self, monkeypatch):
        """दिवसभर फक्त RSI/PCR-नाकारलेले touches असतील (खरा trade कधीच न होता), तर last_trade_time
        None असायला हवा -- म्हणजे cooldown अजिबात लागू होणार नाही (नवीन खऱ्या trade ला अडवलं जाणार नाही)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("2026-09-08 11:35:00", "SKIPPED_RSI_FILTER"),
            ("2026-09-08 11:20:00", "SKIPPED_PCR_GATE"),
            ("2026-09-08 11:00:00", None),  # अजून प्रत्यक्ष प्रयत्नच झाला नाही
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        count, last_hit_time, last_trade_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert count == 3
        assert last_trade_time is None

    def test_last_trade_time_recognizes_partial_multi_account_status(self, monkeypatch):
        """"A1:OPENED; A2:FAILED" सारखा multi-account निकाल सुद्धा खरा trade attempt आहे (फक्त
        None/STRATEGY_SELECTION_FAILED/SKIPPED_* नाहीत) -- last_trade_time मध्ये मोजला जायला हवा."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("2026-09-08 11:00:00", "A1:OPENED; A2:FAILED")]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        _, _, last_trade_time = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-08")
        assert last_trade_time == "2026-09-08 11:00:00"


class TestZoneRoleFromType:
    def test_support_zone_type_variants(self):
        assert cloud_db.zone_role_from_type("SUPPORT") == "SUPPORT"
        assert cloud_db.zone_role_from_type("DYNAMIC_SR_SUPPORT_1M") == "SUPPORT"
        assert cloud_db.zone_role_from_type("DYNAMIC_SR_SUPPORT_30M") == "SUPPORT"

    def test_resistance_zone_type_variants(self):
        assert cloud_db.zone_role_from_type("RESISTANCE") == "RESISTANCE"
        assert cloud_db.zone_role_from_type("DYNAMIC_SR_RESISTANCE_5M") == "RESISTANCE"

    def test_unrelated_or_empty_zone_type_returns_none(self):
        assert cloud_db.zone_role_from_type("BULLISH_OB") is None
        assert cloud_db.zone_role_from_type("") is None
        assert cloud_db.zone_role_from_type(None) is None


class TestIvHistoryStorage:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Record iv of option premium daily for
    analysis") — iv_history table, strike_oi_history सारखाच upsert पॅटर्न."""

    def test_save_iv_snapshot_upserts_each_row(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        rows = [
            {"strike": 24000, "option_type": "CE", "expiry": "2026-09-25", "iv": 12.5, "ltp": 150.0, "underlying_price": 24010.0},
            {"strike": 24000, "option_type": "PE", "expiry": "2026-09-25", "iv": 13.1, "ltp": 140.0, "underlying_price": 24010.0},
        ]
        result = cloud_db.save_iv_snapshot("NIFTY", "2026-09-23", "15:25", rows)
        assert result is True
        assert mock_cursor.execute.call_count == 2
        sql, params = mock_cursor.execute.call_args_list[0][0]
        assert "INSERT INTO iv_history" in sql
        assert "ON CONFLICT" in sql
        assert params == ("NIFTY", 24000, "CE", "2026-09-23", "15:25", "2026-09-25", 12.5, 150.0, 24010.0)

    def test_save_iv_snapshot_missing_optional_fields_default_to_none(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        cloud_db.save_iv_snapshot("NIFTY", "2026-09-23", "15:25", [{"strike": 24000, "option_type": "CE"}])
        _, params = mock_cursor.execute.call_args_list[0][0]
        assert params == ("NIFTY", 24000, "CE", "2026-09-23", "15:25", None, None, None, None)

    def test_no_connection_returns_safe_defaults(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.save_iv_snapshot("NIFTY", "2026-09-23", "15:25", [{"strike": 24000, "option_type": "CE"}]) is False
        assert cloud_db.get_iv_history("NIFTY") is None

    def test_get_iv_history_no_range_reads_everything(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_iv_history("NIFTY")
        assert result is not None and result.empty
        sql, params = mock_cursor.execute.call_args[0]
        assert "trade_date >=" not in sql
        assert "trade_date <=" not in sql
        assert params == ["NIFTY"]

    def test_get_iv_history_with_date_range_filters(self, monkeypatch):
        """🎓 "काल IV काय होता, आज काय आहे" अशी तुलना यावरूनच होणार — from_date/to_date दिल्यावर तेवढाच
        range query मध्ये यायला हवा."""
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("2026-09-22", "15:25", "2026-09-25", 24000.0, "CE", 12.0, 148.0, 24000.0),
            ("2026-09-23", "15:25", "2026-09-25", 24000.0, "CE", 12.8, 152.0, 24010.0),
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_iv_history("NIFTY", from_date="2026-09-22", to_date="2026-09-23")
        sql, params = mock_cursor.execute.call_args[0]
        assert "trade_date >= %s" in sql and "trade_date <= %s" in sql
        assert params == ["NIFTY", "2026-09-22", "2026-09-23"]
        assert len(result) == 2
        assert list(result["trade_date"]) == ["2026-09-22", "2026-09-23"]

    def test_get_iv_history_strikes_filter(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        cloud_db.get_iv_history("NIFTY", strikes=[23900, 24000])
        sql, params = mock_cursor.execute.call_args[0]
        assert "strike IN (%s,%s)" in sql
        assert params == ["NIFTY", 23900, 24000]

    def test_query_error_returns_safe_default(self, monkeypatch):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("db error")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        assert cloud_db.save_iv_snapshot("NIFTY", "2026-09-23", "15:25", [{"strike": 24000, "option_type": "CE"}]) is False
        assert cloud_db.get_iv_history("NIFTY") is None


def _ohlc_row(trade_date, open_, high, low, close):
    return {"trade_date": trade_date, "open": open_, "high": high, "low": low, "close": close}


def _iv_row(trade_date, snapshot_time, strike, option_type, iv, underlying_price):
    return {
        "trade_date": trade_date, "snapshot_time": snapshot_time, "expiry": "2026-09-25",
        "strike": strike, "option_type": option_type, "iv": iv, "ltp": 100.0,
        "underlying_price": underlying_price,
    }


class FakeIvDateTime(datetime.datetime):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Average IV Breakout Gate) — get_iv_change_from_
    average() cloud_db.py च्याच established save_vix_spike_halt_status() पॅटर्नने (get_ist_today()
    import न करता) datetime.datetime.utcnow()+5:30 वापरतं — त्यामुळे इथेही तोच FakeTime-स्टाईल mock."""
    _fixed_utcnow = None

    @classmethod
    def utcnow(cls):
        return cls._fixed_utcnow


class TestComputeBodyRatio:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Simple day candle is marabozu or likely marabozu
    with short wick is trending in intraday") — |Close-Open|/(High-Low), इंडिकेटरशिवाय plain
    daily-candle आधारित trending/sideways मोजमाप."""

    def test_pure_marubozu_ratio_near_one(self):
        # Open 23900, Low 23890, High 24110, Close 24100 -- range 220, body 200
        ratio = cloud_db.compute_body_ratio(23900, 24110, 23890, 24100)
        assert round(ratio, 2) == round(200 / 220, 2)

    def test_doji_like_ratio_near_zero(self):
        # Open 24000, Low 23850, High 24150, Close 24020 -- range 300, body 20
        ratio = cloud_db.compute_body_ratio(24000, 24150, 23850, 24020)
        assert round(ratio, 2) == round(20 / 300, 2)

    def test_zero_range_day_returns_zero_not_crash(self):
        """High==Low (हालचालच नाही, अत्यंत दुर्मिळ) -- division-by-zero ऐवजी सुरक्षित 0.0."""
        assert cloud_db.compute_body_ratio(24000, 24000, 24000, 24000) == 0.0


class TestIsSidewaysDay:
    def test_below_threshold_is_sideways(self):
        assert cloud_db.is_sideways_day(24000, 24150, 23850, 24020, marubozu_threshold=0.8) is True

    def test_at_or_above_threshold_is_not_sideways(self):
        # body_ratio 200/220 ≈ 0.909 >= 0.8
        assert cloud_db.is_sideways_day(23900, 24110, 23890, 24100, marubozu_threshold=0.8) is False

    def test_custom_threshold_respected(self):
        # body_ratio 150/250 = 0.6 -- 0.8 सह sideways, 0.5 सह trending
        assert cloud_db.is_sideways_day(24000, 24200, 23950, 24150, marubozu_threshold=0.8) is True
        assert cloud_db.is_sideways_day(24000, 24200, 23950, 24150, marubozu_threshold=0.5) is False


class TestGetNiftyDailyOhlc:
    """🎓 established `nifty_1min_ohlc` (रोज अद्ययावत होणारा NIFTY 1-मिनिट डेटा) मधून resample
    करून प्रत्येक दिवसाचा daily O/H/L/C काढणे -- नवीन कुठलाही API कॉल/cron लागत नाही."""

    def test_no_data_returns_none(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_nifty_1min_range", lambda from_date=None, to_date=None: None)
        assert cloud_db.get_nifty_daily_ohlc() is None

    def test_resamples_1min_candles_to_daily_ohlc(self, monkeypatch):
        import pandas as pd
        rows = [
            {"timestamp": pd.Timestamp("2026-09-23 09:15:00"), "open": 23800.0, "high": 23810.0, "low": 23795.0, "close": 23805.0, "volume": 0},
            {"timestamp": pd.Timestamp("2026-09-23 12:00:00"), "open": 23805.0, "high": 23920.0, "low": 23690.0, "close": 23900.0, "volume": 0},
            {"timestamp": pd.Timestamp("2026-09-23 15:29:00"), "open": 23900.0, "high": 23905.0, "low": 23895.0, "close": 23898.0, "volume": 0},
            {"timestamp": pd.Timestamp("2026-09-24 09:15:00"), "open": 24000.0, "high": 24010.0, "low": 23995.0, "close": 24005.0, "volume": 0},
        ]
        monkeypatch.setattr(cloud_db, "get_nifty_1min_range", lambda from_date=None, to_date=None: pd.DataFrame(rows))
        result = cloud_db.get_nifty_daily_ohlc()
        assert result is not None
        day1 = result[result["trade_date"] == "2026-09-23"].iloc[0]
        assert day1["open"] == 23800.0   # दिवसाचा पहिला candle चा open
        assert day1["high"] == 23920.0   # दिवसातला कमाल high
        assert day1["low"] == 23690.0    # दिवसातला किमान low
        assert day1["close"] == 23898.0  # दिवसाचा शेवटचा candle चा close
        assert len(result) == 2  # दोन वेगळे trade_dates


class TestGetIvChangeFromAverage:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Average IV Breakout Gate — "5 minute instant
    dynamic sr strategy work better in sideways, low iv or average iv market, but in trending when
    Breakout happen it books loss") — आजचा ATM IV, गेल्या N दिवसांच्या सरासरी ATM IV शी तुलना."""

    def setup_method(self):
        # 5:00 UTC + 5:30 = 10:30 IST, 2026-09-24 -- सर्व टेस्ट्समध्ये "आज" हाच.
        FakeIvDateTime._fixed_utcnow = datetime.datetime(2026, 9, 24, 5, 0)

    def _patch_now(self, monkeypatch):
        monkeypatch.setattr(cloud_db.datetime, "datetime", FakeIvDateTime)

    def test_no_history_returns_none(self, monkeypatch):
        self._patch_now(monkeypatch)
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: None)
        assert cloud_db.get_iv_change_from_average("NIFTY") is None

    def test_empty_history_returns_none(self, monkeypatch):
        import pandas as pd
        self._patch_now(monkeypatch)
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(
            columns=["trade_date", "snapshot_time", "expiry", "strike", "option_type", "iv", "ltp", "underlying_price"],
        ))
        assert cloud_db.get_iv_change_from_average("NIFTY") is None

    def test_no_todays_snapshot_returns_none(self, monkeypatch):
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [_iv_row("2026-09-23", "15:25", 24000, "CE", 12.0, 24000.0)]
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        assert cloud_db.get_iv_change_from_average("NIFTY") is None

    def test_stale_todays_snapshot_returns_none(self, monkeypatch):
        """आजचा snapshot max_age_minutes पेक्षा जुना -- collector थांबलेला असू शकतो, fail-safe None."""
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            _iv_row("2026-09-22", "15:25", 24000, "CE", 10.0, 24000.0),
            _iv_row("2026-09-22", "15:25", 24000, "PE", 10.4, 24000.0),
            _iv_row("2026-09-24", "09:30", 24000, "CE", 14.0, 24000.0),  # 10:30 - 9:30 = 60 मि जुना
            _iv_row("2026-09-24", "09:30", 24000, "PE", 14.4, 24000.0),
        ]
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        assert cloud_db.get_iv_change_from_average("NIFTY", max_age_minutes=20) is None

    def test_no_prior_days_returns_none(self, monkeypatch):
        """पुरेसा इतिहास अजून जमलेला नाही (आजचाच पहिला दिवस) -- fail-safe None."""
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            _iv_row("2026-09-24", "10:25", 24000, "CE", 12.0, 24000.0),
            _iv_row("2026-09-24", "10:25", 24000, "PE", 13.0, 24000.0),
        ]
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        assert cloud_db.get_iv_change_from_average("NIFTY") is None

    def test_success_computes_change_pct_from_average(self, monkeypatch):
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            # कालच्या आधीचा दिवस (EOD) -- ATM=23800, avg IV=(10.0+10.4)/2=10.2
            _iv_row("2026-09-22", "09:20", 23700, "CE", 99.0, 23800.0),  # आधीचा, ignored (EOD नाही)
            _iv_row("2026-09-22", "15:25", 23800, "CE", 10.0, 23800.0),
            _iv_row("2026-09-22", "15:25", 23800, "PE", 10.4, 23800.0),
            # कालचा दिवस (EOD) -- ATM=23900, avg IV=(10.8+11.2)/2=11.0
            _iv_row("2026-09-23", "15:25", 23900, "CE", 10.8, 23900.0),
            _iv_row("2026-09-23", "15:25", 23900, "PE", 11.2, 23900.0),
            # आज, सर्वात अलीकडचा -- ATM=24000 (जवळचा strike), avg IV=(12.0+13.0)/2=12.5
            _iv_row("2026-09-24", "09:30", 24000, "CE", 20.0, 24000.0),  # जुना, ignored (सर्वात अलीकडचा नाही)
            _iv_row("2026-09-24", "10:25", 23900, "CE", 99.0, 24000.0),  # वेगळा strike, ATM नाही, ignored
            _iv_row("2026-09-24", "10:25", 24000, "CE", 12.0, 24000.0),
            _iv_row("2026-09-24", "10:25", 24000, "PE", 13.0, 24000.0),
        ]
        # दोन्ही prior दिवस SIDEWAYS (body_ratio < 0.8 marubozu threshold) -- बेसलाइनमध्ये मोजले जावेत.
        daily_ohlc = pd.DataFrame([
            _ohlc_row("2026-09-22", 23800.0, 23850.0, 23750.0, 23810.0),  # range 100, body 10, ratio 0.10
            _ohlc_row("2026-09-23", 23900.0, 23950.0, 23850.0, 23910.0),  # range 100, body 10, ratio 0.10
        ])
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        monkeypatch.setattr(cloud_db, "get_nifty_daily_ohlc", lambda: daily_ohlc)
        result = cloud_db.get_iv_change_from_average("NIFTY", lookback_days=10, max_age_minutes=20)
        assert result is not None
        assert result["today_iv"] == 12.5
        assert result["baseline_avg_iv"] == 10.6  # (10.2+11.0)/2
        assert result["days_in_baseline"] == 2
        assert round(result["change_pct"], 2) == round((12.5 - 10.6) / 10.6 * 100, 2)

    def test_lookback_days_limits_prior_days_used(self, monkeypatch):
        """lookback_days पेक्षा जास्त इतिहास असेल, तर फक्त सर्वात अलीकडचे N दिवसच वापरायला हवेत."""
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            # खूप जुना दिवस, वेगळाच (खूप कमी) IV -- lookback_days=1 दिल्यास वगळला जायला हवा
            _iv_row("2026-09-20", "15:25", 23000, "CE", 1.0, 23000.0),
            _iv_row("2026-09-20", "15:25", 23000, "PE", 1.0, 23000.0),
            # सर्वात अलीकडचा आधीचा दिवस
            _iv_row("2026-09-23", "15:25", 23900, "CE", 10.0, 23900.0),
            _iv_row("2026-09-23", "15:25", 23900, "PE", 10.0, 23900.0),
            _iv_row("2026-09-24", "10:25", 24000, "CE", 12.0, 24000.0),
            _iv_row("2026-09-24", "10:25", 24000, "PE", 12.0, 24000.0),
        ]
        daily_ohlc = pd.DataFrame([
            _ohlc_row("2026-09-20", 23000.0, 23050.0, 22950.0, 23010.0),  # sideways
            _ohlc_row("2026-09-23", 23900.0, 23950.0, 23850.0, 23910.0),  # sideways
        ])
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        monkeypatch.setattr(cloud_db, "get_nifty_daily_ohlc", lambda: daily_ohlc)
        result = cloud_db.get_iv_change_from_average("NIFTY", lookback_days=1)
        assert result["days_in_baseline"] == 1
        assert result["baseline_avg_iv"] == 10.0  # फक्त 23-सप्टेंबरचाच, 20-सप्टेंबरचा वगळलेला

    def test_trending_day_excluded_from_baseline(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Fakt N diwsacha average फायद्याचा नाही" +
        "Simple day candle is marabozu ... is trending") -- trending (Marubozu-सारखा) दिवस बेसलाइन
        सरासरीतून पूर्णपणे वगळला जायला हवा, जरी तो lookback window च्या आतच असला तरी."""
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            # ट्रेंडिंग दिवस (उंच IV, 20.0) -- वगळला जायला हवा
            _iv_row("2026-09-22", "15:25", 23800, "CE", 20.0, 23800.0),
            _iv_row("2026-09-22", "15:25", 23800, "PE", 20.0, 23800.0),
            # sideways दिवस -- हाच फक्त बेसलाइनमध्ये यायला हवा
            _iv_row("2026-09-23", "15:25", 23900, "CE", 10.0, 23900.0),
            _iv_row("2026-09-23", "15:25", 23900, "PE", 10.0, 23900.0),
            _iv_row("2026-09-24", "10:25", 24000, "CE", 12.0, 24000.0),
            _iv_row("2026-09-24", "10:25", 24000, "PE", 12.0, 24000.0),
        ]
        daily_ohlc = pd.DataFrame([
            _ohlc_row("2026-09-22", 23700.0, 23920.0, 23690.0, 23900.0),  # range 230, body 200, ratio 0.87 -- TRENDING
            _ohlc_row("2026-09-23", 23900.0, 23950.0, 23850.0, 23910.0),  # range 100, body 10, ratio 0.10 -- sideways
        ])
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        monkeypatch.setattr(cloud_db, "get_nifty_daily_ohlc", lambda: daily_ohlc)
        result = cloud_db.get_iv_change_from_average("NIFTY", lookback_days=10)
        assert result is not None
        assert result["days_in_baseline"] == 1
        assert result["baseline_avg_iv"] == 10.0  # trending दिवसाचा (20.0) परिणाम अजिबात नाही

    def test_day_missing_from_daily_ohlc_treated_as_unknown_excluded(self, monkeypatch):
        """iv_history मध्ये दिवस आहे, पण daily_ohlc (nifty_1min_ohlc) मध्ये गहाळ (उदा. डेटा-गॅप) --
        classification अनिश्चित असल्याने sideways गृहीत न धरता वगळलंच जायला हवं (fail-safe)."""
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            _iv_row("2026-09-23", "15:25", 23900, "CE", 10.0, 23900.0),
            _iv_row("2026-09-23", "15:25", 23900, "PE", 10.0, 23900.0),
            _iv_row("2026-09-24", "10:25", 24000, "CE", 12.0, 24000.0),
            _iv_row("2026-09-24", "10:25", 24000, "PE", 12.0, 24000.0),
        ]
        daily_ohlc = pd.DataFrame(columns=["trade_date", "open", "high", "low", "close"])  # 23-सप्टेंबरची नोंदच नाही
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        monkeypatch.setattr(cloud_db, "get_nifty_daily_ohlc", lambda: daily_ohlc)
        assert cloud_db.get_iv_change_from_average("NIFTY") is None

    def test_non_nifty_symbol_always_returns_none(self, monkeypatch):
        """day-classification फक्त NIFTY साठी शक्य (nifty_1min_ohlc फक्त NIFTY साठीच) -- इतर symbols
        साठी जुनं सरसकट-सरासरी वर्तन परत येत नाही, fail-safe None."""
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            _iv_row("2026-09-23", "15:25", 23900, "CE", 10.0, 23900.0),
            _iv_row("2026-09-23", "15:25", 23900, "PE", 10.0, 23900.0),
            _iv_row("2026-09-24", "10:25", 24000, "CE", 12.0, 24000.0),
            _iv_row("2026-09-24", "10:25", 24000, "PE", 12.0, 24000.0),
        ]

        def _boom():
            raise AssertionError("BANKNIFTY साठी get_nifty_daily_ohlc() कधीच call व्हायला नको")

        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        monkeypatch.setattr(cloud_db, "get_nifty_daily_ohlc", _boom)
        assert cloud_db.get_iv_change_from_average("BANKNIFTY") is None

    def test_zero_baseline_returns_none(self, monkeypatch):
        import pandas as pd
        self._patch_now(monkeypatch)
        rows = [
            _iv_row("2026-09-23", "15:25", 23900, "CE", 0.0, 23900.0),
            _iv_row("2026-09-23", "15:25", 23900, "PE", 0.0, 23900.0),
            _iv_row("2026-09-24", "10:25", 24000, "CE", 12.0, 24000.0),
            _iv_row("2026-09-24", "10:25", 24000, "PE", 12.0, 24000.0),
        ]
        daily_ohlc = pd.DataFrame([
            _ohlc_row("2026-09-23", 23900.0, 23950.0, 23850.0, 23910.0),  # sideways
        ])
        monkeypatch.setattr(cloud_db, "get_iv_history", lambda symbol: pd.DataFrame(rows))
        monkeypatch.setattr(cloud_db, "get_nifty_daily_ohlc", lambda: daily_ohlc)
        assert cloud_db.get_iv_change_from_average("NIFTY") is None


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

    def test_existing_level_not_in_new_candidates_is_marked_stale_not_deleted(self, monkeypatch):
        """🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("market open hotach sarv level update
        karayche, fresh support and resistance pahijet") — आता नव्या ताज्या गणनेत न सापडलेला जुना
        level DELETE होत नाही (इतिहासासाठी row टिकतो), पण status='STALE' होतो, जेणेकरून
        status='ACTIVE' फिल्टर करणाऱ्या bots ना (उदा. dynamic_sr_instant_trader.py) तो आपोआप
        दिसेनासा होतो -- चार्टवरचं (नेहमी ताजं टॉप-5) आणि bot ची ACTIVE यादी सुसंगत राहावी म्हणून."""
        existing_rows = [(1, "DYNAMIC_SR_SUPPORT_1M", 23900.0), (2, "DYNAMIC_SR_RESISTANCE_1M", 24500.0)]
        mock_conn, mock_cursor = self._mock_conn(existing_rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        # दोन्ही आता नव्या गणनेत सापडतच नाहीत -- DELETE नाही, पण STALE व्हायला हवं
        dyn_sr = {"support": [], "resistance": []}
        result = cloud_db.merge_dynamic_sr_1m_zones("NIFTY", dyn_sr)
        assert result is True

        delete_calls = [c for c in mock_cursor.execute.call_args_list if "DELETE FROM market_zones" in c[0][0]]
        assert len(delete_calls) == 0  # कधीच hard DELETE नाही

        stale_calls = [c for c in mock_cursor.execute.call_args_list if "UPDATE market_zones" in c[0][0] and "STALE" in c[0][0]]
        assert len(stale_calls) == 2  # दोन्ही zone_types साठी (support + resistance) एक-एक UPDATE
        staled_ids = {row_id for c in stale_calls for row_id in c[0][1]}
        assert staled_ids == {1, 2}

    def test_matched_existing_level_is_not_marked_stale(self, monkeypatch):
        """जुळलेला (matched) जुना level STALE होता कामा नये -- फक्त न-जुळलेलाच."""
        existing_rows = [(1, "DYNAMIC_SR_SUPPORT_1M", 23900.0)]
        mock_conn, mock_cursor = self._mock_conn(existing_rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        dyn_sr = {"support": [{"level": 23901.0, "touches": 3}], "resistance": []}
        cloud_db.merge_dynamic_sr_1m_zones("NIFTY", dyn_sr)

        stale_calls = [c for c in mock_cursor.execute.call_args_list if "UPDATE market_zones" in c[0][0] and "STALE" in c[0][0]]
        assert len(stale_calls) == 0

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


class TestStrategySettings:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) — flexible
    JSONB-आधारित strategy-wise settings, डीफॉल्ट + आंशिक override merge."""

    def test_get_settings_returns_full_defaults_when_no_row(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_strategy_settings("1m_instant", "NIFTY")
        # symbol_enabled हा STRATEGY_SETTINGS_DEFAULTS मध्ये नाही (symbol-निहाय आहे, get_strategy_settings()
        # मध्येच जोडला जातो — NIFTY साठी डीफॉल्ट True).
        expected = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        expected["symbol_enabled"] = True
        assert result == expected

    def test_get_settings_merges_partial_override_with_defaults(self, monkeypatch):
        # फक्त lots आणि itm_depth_points बदललेले (Dashboard वर वापरकर्त्याने) — बाकीचे fields
        # (उदा. hedge_width_points) डीफॉल्टच राहायला हवेत.
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ({"lots": 5, "itm_depth_points": 75},)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_strategy_settings("1m_instant", "NIFTY")
        assert result["lots"] == 5
        assert result["itm_depth_points"] == 75
        assert result["hedge_width_points"] == 150  # डीफॉल्टच, न बदललेला

    def test_get_settings_no_connection_returns_defaults(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        result = cloud_db.get_strategy_settings("15m_dynamic_sr", "NIFTY")
        expected = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        expected["symbol_enabled"] = True
        assert result == expected

    def test_save_settings_calls_upsert_with_json(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.save_strategy_settings("1m_instant", "NIFTY", {"lots": 3})
        assert result is True
        insert_calls = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO strategy_settings" in c[0][0]]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1][0] == "1m_instant"
        assert insert_calls[0][0][1][1] == "NIFTY"

    def test_save_settings_no_connection_returns_false(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        result = cloud_db.save_strategy_settings("1m_instant", "NIFTY", {"lots": 3})
        assert result is False

    def test_naked_disabled_by_default_matches_spec(self):
        """वापरकर्त्याने स्पष्ट सांगितलेलं — डीफॉल्ट hedging नसावी (निव्वळ/naked buy)."""
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["naked_hedge_enabled"] is False
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]["naked_hedge_enabled"] is False
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["naked_enabled"] is True
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]["naked_enabled"] is True

    def test_classic_sr_reversal_symbol_enabled_defaults_false_even_for_nifty(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — नवीन "classic_sr_reversal" strategy अजून
        backtest-टप्प्यातच असल्याने, इतर दोन strategies प्रमाणे NIFTY साठी डीफॉल्ट सक्रिय नसावी —
        वापरकर्त्याने Dashboard वरून स्पष्टपणे सक्रिय केल्याशिवाय कुठलाही (PAPER सुद्धा) trade नाही."""
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        result = cloud_db.get_strategy_settings("classic_sr_reversal", "NIFTY")
        assert result["symbol_enabled"] is False
        # बाकीचे इतर strategies प्रमाणेच — पूर्ण डीफॉल्ट (फक्त symbol_enabled वेगळा)
        expected = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["classic_sr_reversal"])
        expected["symbol_enabled"] = False
        assert result == expected

    def test_classic_sr_reversal_entry_refinement_gates_default_off(self):
        """तिन्ही नवीन Entry Refinement गेट्स (Swing/Demand-Supply/Trendline) डीफॉल्ट बंद —
        backtest मधल्याच डीफॉल्ट तर्काशी सुसंगत, backward-compatible."""
        defaults = cloud_db.STRATEGY_SETTINGS_DEFAULTS["classic_sr_reversal"]
        assert defaults["swing_confluence_enabled"] is False
        assert defaults["demand_supply_gate_enabled"] is False
        assert defaults["trendline_gate_enabled"] is False
        assert "entry_pcr_gate_enabled" not in defaults  # PCR गेट मुद्दाम नाही (चर्चेत ठरल्याप्रमाणे)

    def test_classic_sr_reversal_major_swings_only_defaults(self):
        """🎓 वापरकर्त्याने प्रत्यक्ष चार्ट screenshot वरून "major swings only" दाखवलं, आणि तीच कल्पना
        strategy मध्ये आणायला सांगितलं — दोन्ही एकत्र: वाढवलेला swing_order (3->5) आणि नवीन
        swing_min_move_pct (ZigZag-सारखा magnitude फिल्टर, signals.filter_major_swings())."""
        defaults = cloud_db.STRATEGY_SETTINGS_DEFAULTS["classic_sr_reversal"]
        assert defaults["swing_order"] == 5
        assert defaults["swing_min_move_pct"] == 0.5


class TestMcxFuturesStrategySettings:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली, संपूर्णपणे नवीन, स्वतंत्र strategy — MCX Futures Trader.
    NIFTY/BANKNIFTY/SENSEX च्या तिन्ही strategies पासून पूर्णपणे वेगळी — options-specific fields
    (itm_depth_points/hedge_width_points/net_credit इ.) इथे मुळीच नाहीत, सरळ futures points मध्ये
    SL/Target."""

    def test_no_mcx_symbol_enabled_by_default(self, monkeypatch):
        """नवीन/अपडाळलेली strategy — कुठल्याही MCX commodity साठी डीफॉल्ट सक्रिय नाही (classic_sr_reversal
        सारखाच safe-by-default — वापरकर्त्याने Dashboard वरून स्पष्टपणे सक्रिय केल्याशिवाय कुठलाही, PAPER
        सुद्धा, trade नाही). symbol_enabled logic (symbol == "NIFTY") MCX symbols साठी आपोआप False ठरतं."""
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        for symbol in ("CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"):
            result = cloud_db.get_strategy_settings("mcx_futures", symbol)
            assert result["symbol_enabled"] is False

    def test_rsi_dual_threshold_defaults_40_60(self):
        defaults = cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]
        assert defaults["rsi_support_max"] == 40
        assert defaults["rsi_resistance_min"] == 60
        assert defaults["entry_rsi_gate_enabled"] is True

    def test_timeframe_choice_defaults_to_30m_only(self):
        """15M हा पर्यायच नाही (कधीच नाही) — फक्त 30M/60M/ALL(दोन्ही एकत्र)."""
        defaults = cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]
        assert defaults["timeframe_choice"] == "30M"

    def test_no_options_specific_fields(self):
        """options-only concepts (strike-निवड/hedge/net_credit) इथे नकोतच — सरळ Futures."""
        defaults = cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]
        for absent_field in ("itm_depth_points", "hedge_width_points", "naked_enabled", "entry_pcr_gate_enabled"):
            assert absent_field not in defaults

    def test_sl_target_are_futures_points_not_premium(self):
        defaults = cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]
        assert defaults["sl_points"] == 20
        assert defaults["target_points"] == 40
        assert defaults["trailing_sl_enabled"] is False

    def test_defaults_to_paper_mode(self):
        defaults = cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]
        assert defaults["trading_mode"] == "PAPER"
        assert defaults["broker_account_ids"] == []


class TestGetAllStrategyTradingModes:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Bot Dynamic SR Algo — नवीन वापरकर्त्यालाही सहज वापरता
    यावं) — पानाच्या वर सर्व strategy+symbol combos पैकी कुठले LIVE आहेत हे एकाच query मध्ये दाखवण्यासाठी."""

    def test_returns_dict_keyed_by_strategy_symbol(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("1m_instant", "NIFTY", {"trading_mode": "LIVE", "broker_account_ids": ["ACC_A"]}),
            ("classic_sr_reversal", "BANKNIFTY", {"trading_mode": "PAPER"}),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_all_strategy_trading_modes()
        assert result[("1m_instant", "NIFTY")] == {"trading_mode": "LIVE", "broker_account_ids": ["ACC_A"]}
        assert result[("classic_sr_reversal", "BANKNIFTY")] == {"trading_mode": "PAPER", "broker_account_ids": []}

    def test_handles_json_string_settings(self, monkeypatch):
        """कधीकधी psycopg2 JSONB ला dict ऐवजी raw JSON string परत देऊ शकतो."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("15m_dynamic_sr", "NIFTY", '{"trading_mode": "LIVE"}')]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_all_strategy_trading_modes()
        assert result[("15m_dynamic_sr", "NIFTY")]["trading_mode"] == "LIVE"

    def test_no_connection_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.get_all_strategy_trading_modes() == {}

    def test_no_rows_returns_empty_dict(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)
        assert cloud_db.get_all_strategy_trading_modes() == {}


class TestKillSwitchSettings:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit,
    गंभीर यादीतला चौथा मुद्दा) — get/save_kill_switch_settings() हे आधीच पूर्णपणे टेस्ट केलेल्या
    get/save_strategy_settings() चेच पातळ wrapper आहेत (strategy_name="__global_kill_switch__",
    symbol="ALL" या स्थिर जोडीसह) — त्यामुळे इथे फक्त wrapping/डीफॉल्ट्स तपासले जातात."""

    def test_get_returns_defaults_when_nothing_saved(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        settings = cloud_db.get_kill_switch_settings()
        assert settings == {
            "enabled": True, "max_daily_loss_pct": 2.0, "max_daily_profit_pct": 3.0, "max_trades_per_day": 15,
            "profit_lock_enabled": False, "profit_lock_pct": 50.0,
        }

    def test_get_returns_saved_values(self, monkeypatch):
        with patch.object(
            cloud_db, "get_strategy_settings",
            return_value={
                "enabled": False, "max_daily_loss_pct": 4.0, "max_daily_profit_pct": 6.0, "max_trades_per_day": 8,
                "profit_lock_enabled": True, "profit_lock_pct": 60.0,
            },
        ) as mock_get:
            settings = cloud_db.get_kill_switch_settings()
        mock_get.assert_called_once_with(cloud_db.KILL_SWITCH_STRATEGY_KEY, cloud_db.KILL_SWITCH_SYMBOL_KEY)
        assert settings == {
            "enabled": False, "max_daily_loss_pct": 4.0, "max_daily_profit_pct": 6.0, "max_trades_per_day": 8,
            "profit_lock_enabled": True, "profit_lock_pct": 60.0,
        }

    def test_save_delegates_with_fixed_strategy_symbol_key(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.save_kill_switch_settings(True, "2.5", "5.0", "10")
        assert ok is True
        mock_save.assert_called_once_with(
            cloud_db.KILL_SWITCH_STRATEGY_KEY, cloud_db.KILL_SWITCH_SYMBOL_KEY,
            {"enabled": True, "max_daily_loss_pct": 2.5, "max_daily_profit_pct": 5.0, "max_trades_per_day": 10,
             "profit_lock_enabled": False, "profit_lock_pct": 50.0},
        )

    def test_save_with_profit_lock_args(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("1 trade profit मध्ये exit जाला, दुसरा उघडा
        असेल, तर काही नफा नेहमी लॉक व्हावा") — profit_lock_enabled/profit_lock_pct आर्ग्युमेंट्स
        बरोबर पास होतात, डीफॉल्टवर न पडता."""
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.save_kill_switch_settings(True, "2.5", "5.0", "10", True, "40")
        assert ok is True
        mock_save.assert_called_once_with(
            cloud_db.KILL_SWITCH_STRATEGY_KEY, cloud_db.KILL_SWITCH_SYMBOL_KEY,
            {"enabled": True, "max_daily_loss_pct": 2.5, "max_daily_profit_pct": 5.0, "max_trades_per_day": 10,
             "profit_lock_enabled": True, "profit_lock_pct": 40.0},
        )


class TestMcxKillSwitchSettings:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (MCX LIVE करण्याआधी — "MCX साठी वेगळा Kill Switch") +
    वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("MCX साठीही हेच लगेच जोडायचं" — Profit-Lock) —
    get/save_mcx_kill_switch_settings() हे आधीच पूर्णपणे टेस्ट केलेल्या get/save_strategy_settings()
    चेच पातळ wrapper आहेत (strategy_name="__mcx_kill_switch__", symbol="ALL" या स्थिर जोडीसह)."""

    def test_get_returns_defaults_when_nothing_saved(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        settings = cloud_db.get_mcx_kill_switch_settings()
        assert settings == {
            "enabled": True, "max_daily_loss_pct": 1.0, "max_open_positions": 2,
            "profit_lock_enabled": False, "profit_lock_pct": 50.0,
        }

    def test_get_returns_saved_values(self, monkeypatch):
        with patch.object(
            cloud_db, "get_strategy_settings",
            return_value={
                "enabled": False, "max_daily_loss_pct": 2.0, "max_open_positions": 3,
                "profit_lock_enabled": True, "profit_lock_pct": 70.0,
            },
        ) as mock_get:
            settings = cloud_db.get_mcx_kill_switch_settings()
        mock_get.assert_called_once_with(cloud_db.MCX_KILL_SWITCH_STRATEGY_KEY, cloud_db.MCX_KILL_SWITCH_SYMBOL_KEY)
        assert settings == {
            "enabled": False, "max_daily_loss_pct": 2.0, "max_open_positions": 3,
            "profit_lock_enabled": True, "profit_lock_pct": 70.0,
        }

    def test_save_delegates_with_fixed_strategy_symbol_key(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.save_mcx_kill_switch_settings(True, "1.5", "3")
        assert ok is True
        mock_save.assert_called_once_with(
            cloud_db.MCX_KILL_SWITCH_STRATEGY_KEY, cloud_db.MCX_KILL_SWITCH_SYMBOL_KEY,
            {"enabled": True, "max_daily_loss_pct": 1.5, "max_open_positions": 3,
             "profit_lock_enabled": False, "profit_lock_pct": 50.0},
        )

    def test_save_with_profit_lock_args(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.save_mcx_kill_switch_settings(True, "1.5", "3", True, "35")
        assert ok is True
        mock_save.assert_called_once_with(
            cloud_db.MCX_KILL_SWITCH_STRATEGY_KEY, cloud_db.MCX_KILL_SWITCH_SYMBOL_KEY,
            {"enabled": True, "max_daily_loss_pct": 1.5, "max_open_positions": 3,
             "profit_lock_enabled": True, "profit_lock_pct": 35.0},
        )


class TestTradingPauseSettings:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("kill switch पेक्षा वेगळा, मॅन्युअल trading stop button —
    PAPER trades लाही लागू व्हावा") — get/set_trading_pause() हे आधीच पूर्णपणे टेस्ट केलेल्या
    get/save_strategy_settings() चेच पातळ wrapper आहेत (strategy_name="__global_trading_pause__",
    symbol="ALL" या स्थिर जोडीसह) — त्यामुळे इथे फक्त wrapping/डीफॉल्ट्स तपासले जातात."""

    def test_get_returns_defaults_when_nothing_saved(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        settings = cloud_db.get_trading_pause_settings()
        assert settings == {"paused": False, "reason": "", "paused_at": None}

    def test_get_returns_saved_values(self, monkeypatch):
        with patch.object(
            cloud_db, "get_strategy_settings",
            return_value={"paused": True, "reason": "उद्याचं Union Budget", "paused_at": "2026-09-23T10:00:00"},
        ) as mock_get:
            settings = cloud_db.get_trading_pause_settings()
        mock_get.assert_called_once_with(cloud_db.TRADING_PAUSE_STRATEGY_KEY, cloud_db.TRADING_PAUSE_SYMBOL_KEY)
        assert settings == {"paused": True, "reason": "उद्याचं Union Budget", "paused_at": "2026-09-23T10:00:00"}

    def test_set_paused_true_stamps_paused_at(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.set_trading_pause(True, reason="Manual stop")
        assert ok is True
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        assert args[0] == cloud_db.TRADING_PAUSE_STRATEGY_KEY
        assert args[1] == cloud_db.TRADING_PAUSE_SYMBOL_KEY
        payload = args[2]
        assert payload["paused"] is True
        assert payload["reason"] == "Manual stop"
        assert payload["paused_at"] is not None  # वेळ नोंदवली गेली

    def test_set_paused_false_clears_paused_at(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.set_trading_pause(False)
        assert ok is True
        payload = mock_save.call_args[0][2]
        assert payload["paused"] is False
        assert payload["paused_at"] is None


class TestVixSpikeHaltSettings:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (India VIX Spike Halt — फक्त NIFTY, फक्त LIVE) —
    get/save_vix_spike_halt_settings() आणि save_vix_spike_halt_status() हे आधीच पूर्णपणे टेस्ट
    केलेल्या get/save_strategy_settings() चेच पातळ wrapper आहेत (strategy_name="__vix_spike_halt__",
    symbol="NIFTY" या स्थिर जोडीसह) — त्यामुळे इथे फक्त wrapping/डीफॉल्ट्स तपासले जातात."""

    def test_get_returns_defaults_when_nothing_saved(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        settings = cloud_db.get_vix_spike_halt_settings()
        assert settings == {
            "enabled": True, "threshold_pct": 5.0, "halted": False, "trade_date": None,
            "prev_close": None, "current_vix": None, "pct_change": None, "checked_at": None,
        }

    def test_get_returns_saved_values(self, monkeypatch):
        with patch.object(
            cloud_db, "get_strategy_settings",
            return_value={
                "enabled": False, "threshold_pct": 7.5, "halted": True, "trade_date": "2026-09-24",
                "prev_close": 13.5, "current_vix": 14.8, "pct_change": 9.6, "checked_at": "2026-09-24T09:20:00",
            },
        ) as mock_get:
            settings = cloud_db.get_vix_spike_halt_settings()
        mock_get.assert_called_once_with(cloud_db.VIX_SPIKE_HALT_STRATEGY_KEY, cloud_db.VIX_SPIKE_HALT_SYMBOL_KEY)
        assert settings == {
            "enabled": False, "threshold_pct": 7.5, "halted": True, "trade_date": "2026-09-24",
            "prev_close": 13.5, "current_vix": 14.8, "pct_change": 9.6, "checked_at": "2026-09-24T09:20:00",
        }

    def test_save_settings_delegates_with_fixed_strategy_symbol_key(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.save_vix_spike_halt_settings(True, "6.0")
        assert ok is True
        mock_save.assert_called_once_with(
            cloud_db.VIX_SPIKE_HALT_STRATEGY_KEY, cloud_db.VIX_SPIKE_HALT_SYMBOL_KEY,
            {"enabled": True, "threshold_pct": 6.0},
        )

    def test_save_settings_does_not_touch_status_fields(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            cloud_db.save_vix_spike_halt_settings(False, 5.0)
        payload = mock_save.call_args[0][2]
        assert "halted" not in payload
        assert "trade_date" not in payload

    def test_save_status_stamps_checked_at(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.save_vix_spike_halt_status("2026-09-24", True, 13.5, 14.8, 9.6)
        assert ok is True
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        assert args[0] == cloud_db.VIX_SPIKE_HALT_STRATEGY_KEY
        assert args[1] == cloud_db.VIX_SPIKE_HALT_SYMBOL_KEY
        payload = args[2]
        assert payload["halted"] is True
        assert payload["trade_date"] == "2026-09-24"
        assert payload["prev_close"] == 13.5
        assert payload["current_vix"] == 14.8
        assert payload["pct_change"] == 9.6
        assert payload["checked_at"] is not None  # वेळ नोंदवली गेली

    def test_save_status_does_not_touch_settings_fields(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            cloud_db.save_vix_spike_halt_status("2026-09-24", False, 13.5, 13.6, 0.7)
        payload = mock_save.call_args[0][2]
        assert "enabled" not in payload
        assert "threshold_pct" not in payload


class TestOtmShadowSettingsDefaults:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (OTM Shadow — "Adhi 5-Min Instant Trader var suru kara") —
    otm_shadow_enabled डीफॉल्ट बंद (backward-compatible, जुन्या वापरकर्त्यांसाठी वर्तन बदलत नाही) आणि
    सुरुवातीला फक्त "1m_instant" (5-Min Instant Trader) साठीच उपलब्ध — इतर strategies ना हे सेटिंगच नाही."""

    def test_otm_shadow_disabled_by_default(self):
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["otm_shadow_enabled"] is False

    def test_otm_shadow_strikes_count_default_is_2(self):
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["otm_shadow_strikes_count"] == 2

    def test_other_strategies_do_not_have_otm_shadow_setting(self):
        for key in ("classic_sr_reversal", "15m_dynamic_sr", "mcx_futures"):
            assert "otm_shadow_enabled" not in cloud_db.STRATEGY_SETTINGS_DEFAULTS[key]

    def test_get_strategy_settings_merges_otm_shadow_override(self, monkeypatch):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ({"otm_shadow_enabled": True, "otm_shadow_strikes_count": 4},)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: mock_conn)

        result = cloud_db.get_strategy_settings("1m_instant", "NIFTY")
        assert result["otm_shadow_enabled"] is True
        assert result["otm_shadow_strikes_count"] == 4
