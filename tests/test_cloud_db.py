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
        assert settings == {"enabled": True, "max_daily_loss": 10000, "max_trades_per_day": 15}

    def test_get_returns_saved_values(self, monkeypatch):
        with patch.object(
            cloud_db, "get_strategy_settings",
            return_value={"enabled": False, "max_daily_loss": 25000, "max_trades_per_day": 8},
        ) as mock_get:
            settings = cloud_db.get_kill_switch_settings()
        mock_get.assert_called_once_with(cloud_db.KILL_SWITCH_STRATEGY_KEY, cloud_db.KILL_SWITCH_SYMBOL_KEY)
        assert settings == {"enabled": False, "max_daily_loss": 25000, "max_trades_per_day": 8}

    def test_save_delegates_with_fixed_strategy_symbol_key(self, monkeypatch):
        with patch.object(cloud_db, "save_strategy_settings", return_value=True) as mock_save:
            ok = cloud_db.save_kill_switch_settings(True, "15000", "10")
        assert ok is True
        mock_save.assert_called_once_with(
            cloud_db.KILL_SWITCH_STRATEGY_KEY, cloud_db.KILL_SWITCH_SYMBOL_KEY,
            {"enabled": True, "max_daily_loss": 15000.0, "max_trades_per_day": 10},
        )
