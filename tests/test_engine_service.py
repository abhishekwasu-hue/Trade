"""
tests/test_engine_service.py
--------------------------------
🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — trade_monitor.py चा docstring
म्हणतो की duplicate-exit bug (हीच script + trade_monitor.py दोघेही एकाच वेळी manage_open_trades()
चालवत) consolidation ने आधीच सुटलेली आहे, पण deploy/README.md आणि deploy/engine_service.timer/.service
अजूनही फक्त engine_service.py साठीच आहेत — म्हणजे प्रत्यक्ष VPS वर कोणती script चालू आहे हे
खात्रीने सांगता येत नाही. म्हणून engine_service.py + trade_monitor.py दोन्हीकडे एकाच नावाचा
ProcessLock ("position_exit_monitor") जोडला — या टेस्ट्स तेच तपासतात.
"""
from unittest.mock import MagicMock

import pytest

import engine_service
from process_lock import ProcessLockHeld


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(engine_service, "is_market_open", lambda: True)
    monkeypatch.setattr(engine_service, "load_settings", lambda: dict(engine_service.DEFAULT_SETTINGS, monitoring_enabled=True))
    monkeypatch.setattr(engine_service.cloud_db, "get_effective_upstox_token", lambda t: "fake_token")
    monkeypatch.setattr(engine_service, "compute_atr_points", lambda t, s, settings: None)
    monkeypatch.setattr(engine_service, "notify_error", lambda *a, **k: None)
    monkeypatch.setattr(engine_service, "notify_exit", lambda *a, **k: None)
    monkeypatch.setattr(engine_service, "write_heartbeat", lambda *a, **k: None)


class TestRunOnceProcessLock:
    def test_acquires_lock_and_calls_manage_open_trades(self, monkeypatch):
        mock_manage = MagicMock(return_value=[])
        monkeypatch.setattr(engine_service, "manage_open_trades", mock_manage)
        engine_service.run_once()
        assert mock_manage.called

    def test_lock_already_held_skips_without_calling_manage_open_trades(self, monkeypatch):
        """🎓 दुसरी exit-monitor invocation (हीच script किंवा trade_monitor.py) अजून चालू असेल, तर
        manage_open_trades() अजिबात चालवला जाऊ नये — क्रॅशही होता कामा नये."""
        mock_manage = MagicMock(return_value=[])
        monkeypatch.setattr(engine_service, "manage_open_trades", mock_manage)

        class _FakeLock:
            def __init__(self, name):
                pass

            def __enter__(self):
                raise ProcessLockHeld("test")

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(engine_service, "ProcessLock", _FakeLock)
        engine_service.run_once()  # क्रॅश न होता शांतपणे थांबायला हवं
        assert not mock_manage.called
