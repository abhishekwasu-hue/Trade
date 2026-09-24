"""
tests/test_check_vix_spike_halt.py
--------------------------------
check_vix_spike_halt.py — 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("India VIX ने पहिल्या पाच
मिनिटांत ठराविक% (आदल्या दिवसाच्या close च्या तुलनेत, threshold 5%) क्रॉस केली तर NIFTY साठी bot ने
automatic trading थांबवावी") — run_vix_spike_check() % बदल बरोबर मोजतं, cloud_db मध्ये साठवतं, आणि
(enabled/fetch-failure/threshold नुसार) योग्य निर्णय + Telegram अलर्ट देतं का, याची पडताळणी. सर्व
external कॉल्स (fetch_india_vix/fetch_india_vix_prev_close/save_vix_spike_halt_status/
send_telegram_message) mock केलेले.
"""
import cloud_db
import check_vix_spike_halt as script


class TestRunVixSpikeCheck:
    def _mock_settings(self, monkeypatch, enabled=True, threshold_pct=5.0):
        monkeypatch.setattr(cloud_db, "get_vix_spike_halt_settings", lambda: {"enabled": enabled, "threshold_pct": threshold_pct})

    def _mock_save(self, monkeypatch):
        calls = []
        monkeypatch.setattr(cloud_db, "save_vix_spike_halt_status", lambda *a, **k: calls.append((a, k)))
        return calls

    def test_disabled_skips_entirely(self, monkeypatch):
        self._mock_settings(monkeypatch, enabled=False)

        def _boom(tok):
            raise AssertionError("enabled=False असताना VIX fetch व्हायला नको होता")
        monkeypatch.setattr(script, "fetch_india_vix", _boom)
        halted = script.run_vix_spike_check("tok", print_fn=lambda x: None)
        assert halted is False

    def test_below_threshold_not_halted(self, monkeypatch):
        self._mock_settings(monkeypatch, threshold_pct=5.0)
        monkeypatch.setattr(script, "fetch_india_vix", lambda tok: 13.0)
        monkeypatch.setattr(script, "fetch_india_vix_prev_close", lambda tok: 12.7)  # +2.4%
        save_calls = self._mock_save(monkeypatch)
        telegram_calls = []
        monkeypatch.setattr(script, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        halted = script.run_vix_spike_check("tok", print_fn=lambda x: None)
        assert halted is False
        assert len(save_calls) == 1
        args, _ = save_calls[0]
        assert args[1] is False  # halted
        assert len(telegram_calls) == 1
        assert "🟢" in telegram_calls[0]

    def test_above_threshold_halted(self, monkeypatch):
        self._mock_settings(monkeypatch, threshold_pct=5.0)
        monkeypatch.setattr(script, "fetch_india_vix", lambda tok: 14.0)
        monkeypatch.setattr(script, "fetch_india_vix_prev_close", lambda tok: 13.0)  # +7.7%
        save_calls = self._mock_save(monkeypatch)
        telegram_calls = []
        monkeypatch.setattr(script, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        halted = script.run_vix_spike_check("tok", print_fn=lambda x: None)
        assert halted is True
        args, _ = save_calls[0]
        assert args[1] is True  # halted
        assert "🔴" in telegram_calls[0]

    def test_exactly_at_threshold_is_halted(self, monkeypatch):
        """>= threshold (नुसतं > नाही) — सीमा-केस."""
        self._mock_settings(monkeypatch, threshold_pct=5.0)
        monkeypatch.setattr(script, "fetch_india_vix", lambda tok: 10.5)
        monkeypatch.setattr(script, "fetch_india_vix_prev_close", lambda tok: 10.0)  # +5.0%
        save_calls = self._mock_save(monkeypatch)
        monkeypatch.setattr(script, "send_telegram_message", lambda msg: None)
        halted = script.run_vix_spike_check("tok", print_fn=lambda x: None)
        assert halted is True

    def test_fetch_failure_fails_safe_halted(self, monkeypatch):
        self._mock_settings(monkeypatch)
        monkeypatch.setattr(script, "fetch_india_vix", lambda tok: None)
        monkeypatch.setattr(script, "fetch_india_vix_prev_close", lambda tok: 13.0)
        save_calls = self._mock_save(monkeypatch)
        telegram_calls = []
        monkeypatch.setattr(script, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        halted = script.run_vix_spike_check("tok", print_fn=lambda x: None)
        assert halted is True
        args, _ = save_calls[0]
        assert args[1] is True
        assert "⚠️" in telegram_calls[0]

    def test_prev_close_zero_fails_safe_halted(self, monkeypatch):
        self._mock_settings(monkeypatch)
        monkeypatch.setattr(script, "fetch_india_vix", lambda tok: 13.0)
        monkeypatch.setattr(script, "fetch_india_vix_prev_close", lambda tok: 0)
        self._mock_save(monkeypatch)
        monkeypatch.setattr(script, "send_telegram_message", lambda msg: None)
        halted = script.run_vix_spike_check("tok", print_fn=lambda x: None)
        assert halted is True

    def test_no_alert_when_send_alert_false(self, monkeypatch):
        self._mock_settings(monkeypatch)
        monkeypatch.setattr(script, "fetch_india_vix", lambda tok: 13.0)
        monkeypatch.setattr(script, "fetch_india_vix_prev_close", lambda tok: 12.7)
        self._mock_save(monkeypatch)
        telegram_calls = []
        monkeypatch.setattr(script, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        script.run_vix_spike_check("tok", print_fn=lambda x: None, send_alert=False)
        assert telegram_calls == []

    def test_telegram_failure_does_not_crash(self, monkeypatch):
        self._mock_settings(monkeypatch)
        monkeypatch.setattr(script, "fetch_india_vix", lambda tok: 13.0)
        monkeypatch.setattr(script, "fetch_india_vix_prev_close", lambda tok: 12.7)
        self._mock_save(monkeypatch)

        def _boom(msg):
            raise ConnectionError("telegram down")
        monkeypatch.setattr(script, "send_telegram_message", _boom)
        printed = []
        halted = script.run_vix_spike_check("tok", print_fn=printed.append)
        assert halted is False
        assert any("Telegram" in p for p in printed)
