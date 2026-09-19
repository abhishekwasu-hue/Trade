"""
tests/test_trade_monitor.py
--------------------------------
🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — याच नावाचा ("position_exit_monitor")
ProcessLock इथेही + engine_service.py दोन्हीकडे जोडलेला — बघा tests/test_engine_service.py चीच
टिप्पणी. दोन्हींपैकी कुठलीही (किंवा चुकून दोन्ही) प्रत्यक्ष VPS वर चालू असो, एकाच वेळी फक्त एकच
manage_open_trades() चालवेल.
"""
from unittest.mock import MagicMock

import pytest

import trade_monitor
from process_lock import ProcessLockHeld


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(trade_monitor, "load_settings", lambda: {
        "product_type": "D", "eod_squareoff_hour": 15, "eod_squareoff_minute": 15,
        "oi_reversal_exit_enabled": False, "trailing_sl_enabled": False, "atr_multiplier": 1.5,
    })
    monkeypatch.setattr(trade_monitor, "compute_atr_points", lambda t, s, settings: None)
    monkeypatch.setattr(trade_monitor, "notify_exit", lambda *a, **k: None)
    monkeypatch.setattr(trade_monitor, "notify_error", lambda *a, **k: None)
    monkeypatch.setattr(trade_monitor, "write_heartbeat", lambda *a, **k: None)


class TestRunMonitorCycleProcessLock:
    def test_acquires_lock_and_calls_manage_open_trades(self, monkeypatch):
        mock_manage = MagicMock(return_value=[])
        monkeypatch.setattr(trade_monitor, "manage_open_trades", mock_manage)
        trade_monitor.run_monitor_cycle("fake_token")
        assert mock_manage.called

    def test_lock_already_held_skips_without_calling_manage_open_trades(self, monkeypatch):
        """🎓 दुसरी exit-monitor invocation (हीच script किंवा engine_service.py) अजून चालू असेल, तर
        manage_open_trades() अजिबात चालवला जाऊ नये — क्रॅशही होता कामा नये, फक्त स्पष्ट संदेश यावा."""
        mock_manage = MagicMock(return_value=[])
        monkeypatch.setattr(trade_monitor, "manage_open_trades", mock_manage)

        class _FakeLock:
            def __init__(self, name):
                pass

            def __enter__(self):
                raise ProcessLockHeld("test")

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(trade_monitor, "ProcessLock", _FakeLock)
        result = trade_monitor.run_monitor_cycle("fake_token")
        assert not mock_manage.called
        assert "वगळलं" in result
