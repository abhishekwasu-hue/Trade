"""
tests/test_trade_monitor.py
--------------------------------
🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — याच नावाचा ("position_exit_monitor")
ProcessLock इथेही + engine_service.py दोन्हीकडे जोडलेला — बघा tests/test_engine_service.py चीच
टिप्पणी. दोन्हींपैकी कुठलीही (किंवा चुकून दोन्ही) प्रत्यक्ष VPS वर चालू असो, एकाच वेळी फक्त एकच
manage_open_trades() चालवेल.
"""
import inspect
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


class TestRunMonitorLoop:
    """🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("SL slippage कमी करा") — एका cron invocation च्या
    आत, run_monitor_cycle() पुन्हा-पुन्हा (interval_seconds च्या अंतराने) चालवणे — fake clock/sleep
    वापरून वेळ न घालवता चाचणी."""

    def _fake_clock(self, start=0.0):
        state = {"now": start}

        def now_fn():
            return state["now"]

        def sleep_fn(seconds):
            state["now"] += seconds

        return now_fn, sleep_fn, state

    def test_runs_multiple_cycles_within_loop_budget(self):
        now_fn, sleep_fn, _ = self._fake_clock()
        cycle_calls = []
        cycle_fn = MagicMock(side_effect=lambda t, p: cycle_calls.append((t, p)) or "ok")

        cycles = trade_monitor.run_monitor_loop(
            "tok", "D", interval_seconds=20, loop_seconds=50,
            cycle_fn=cycle_fn, sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
        )

        # instant fake-cycle (0 सेकंद घेतो) -> 0, 20, 40, 50 सेकंदांना cycle चालतो (शेवटचा तंतोतंत
        # loop_seconds च्या सीमेवर -- cycle आधी चालतो, budget-check नंतर, म्हणून सीमेवरचाही मोजला जातो),
        # 70 वर बजेट संपलेलं दिसून थांबतं.
        assert cycles == 4
        assert cycle_fn.call_count == 4
        assert all(c == ("tok", "D") for c in cycle_calls)

    def test_single_cycle_when_it_alone_exceeds_loop_budget(self):
        """cycle_fn ला स्वतःलाच loop_seconds पेक्षा जास्त वेळ लागला, तरी दुसरा cycle सुरू होता कामा नये."""
        now_fn, sleep_fn, state = self._fake_clock()

        def slow_cycle(t, p):
            state["now"] += 100  # loop_seconds (50) पेक्षा जास्त
            return "slow"

        cycles = trade_monitor.run_monitor_loop(
            "tok", "D", interval_seconds=20, loop_seconds=50,
            cycle_fn=slow_cycle, sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
        )
        assert cycles == 1

    def test_never_sleeps_past_loop_budget(self):
        """sleep_fn ला दिलेला वेळ, उरलेल्या budget पेक्षा जास्त कधीच नसावा."""
        now_fn, _, state = self._fake_clock()
        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            state["now"] += seconds

        trade_monitor.run_monitor_loop(
            "tok", "D", interval_seconds=20, loop_seconds=45,
            cycle_fn=lambda t, p: "ok", sleep_fn=tracking_sleep, now_fn=now_fn, print_fn=lambda x: None,
        )
        assert sum(sleep_calls) <= 45
        assert all(s >= 0 for s in sleep_calls)

    def test_default_interval_seconds_is_15(self):
        """🎓 वापरकर्त्याशी चर्चा करून पुढे आणखी घट्ट केलेलं (आधी 20 होतं, सुरुवातीच्या SL-slippage
        फिक्समध्ये) — run_monitor_loop() चा डीफॉल्ट आणि `--interval-seconds` चा argparse डीफॉल्ट
        दोन्ही 15 असायला हवेत (cron/crontab explicit flag न देताच रिलाय करतो यावर)."""
        sig = inspect.signature(trade_monitor.run_monitor_loop)
        assert sig.parameters["interval_seconds"].default == 15

    def test_cli_default_interval_seconds_is_15(self):
        """__main__ मधला argparse डीफॉल्ट सुद्धा 15 च असायला हवा (function-signature डीफॉल्टशी
        सुसंगत) -- प्रत्यक्ष trade_monitor.py च्या source मधूनच पडताळणी (tautological मॉक टाळून)."""
        source = inspect.getsource(trade_monitor)
        assert '"--interval-seconds", type=float, default=15' in source


class TestRunMonitorLoopTslFastCheck:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (TSL-only fast check) — Performance Report च्या
    SL/TSL Overshoot Tracker मध्ये TSL (Entry/Breakeven-locked) exits मध्येच खरी slippage आढळली,
    सामान्य Spot%-SL exits मध्ये नाही. त्यामुळे blanket interval घट्ट करण्याऐवजी, कुठलाही
    TSL-locked trade सक्रिय असेल तेव्हाच sleep interval घट्ट (tsl_interval_seconds) होतो."""

    def _fake_clock(self, start=0.0):
        state = {"now": start}

        def now_fn():
            return state["now"]

        def sleep_fn(seconds):
            state["now"] += seconds

        return now_fn, sleep_fn, state

    def test_uses_normal_interval_when_no_tsl_active(self):
        now_fn, sleep_fn, _ = self._fake_clock()
        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            sleep_fn(seconds)

        trade_monitor.run_monitor_loop(
            "tok", "D", interval_seconds=20, tsl_interval_seconds=5, loop_seconds=50,
            cycle_fn=lambda t, p: "ok", sleep_fn=tracking_sleep, now_fn=now_fn, print_fn=lambda x: None,
            has_active_tsl_fn=lambda: False,
        )
        # 0 -> 20 -> 40 (पूर्ण 20-sec sleeps), नंतर उरलेल्या 10-sec budget पुरताच शेवटचा sleep (ओलांडत नाही)
        assert sleep_calls == [20.0, 20.0, 10.0]

    def test_uses_tsl_interval_when_tsl_active(self):
        now_fn, sleep_fn, _ = self._fake_clock()
        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            sleep_fn(seconds)

        trade_monitor.run_monitor_loop(
            "tok", "D", interval_seconds=20, tsl_interval_seconds=5, loop_seconds=50,
            cycle_fn=lambda t, p: "ok", sleep_fn=tracking_sleep, now_fn=now_fn, print_fn=lambda x: None,
            has_active_tsl_fn=lambda: True,
        )
        assert all(s == 5.0 for s in sleep_calls)
        assert len(sleep_calls) > 2  # 20-sec ऐवजी 5-sec interval मुळे जास्त cycles व्हायला हवेत

    def test_switches_interval_mid_loop_as_tsl_state_changes(self):
        """पहिल्या cycle नंतर TSL सक्रिय होतो (उदा. price move मुळे) -- लगेच पुढच्या sleep पासूनच
        घट्ट interval वापरला जायला हवा, संपूर्ण loop साठी आधीच ठरवलेला नाही."""
        now_fn, sleep_fn, _ = self._fake_clock()
        state = {"tsl_active": False}
        cycle_calls = []

        def cycle_fn(t, p):
            cycle_calls.append(1)
            if len(cycle_calls) == 1:
                state["tsl_active"] = True  # पहिल्याच cycle नंतर TSL सक्रिय झाला
            return "ok"

        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            sleep_fn(seconds)

        trade_monitor.run_monitor_loop(
            "tok", "D", interval_seconds=20, tsl_interval_seconds=5, loop_seconds=50,
            cycle_fn=cycle_fn, sleep_fn=tracking_sleep, now_fn=now_fn, print_fn=lambda x: None,
            has_active_tsl_fn=lambda: state["tsl_active"],
        )
        assert sleep_calls[0] == 5.0  # पहिल्या cycle नंतर लगेच घट्ट interval

    def test_default_tsl_interval_seconds_is_5(self):
        sig = inspect.signature(trade_monitor.run_monitor_loop)
        assert sig.parameters["tsl_interval_seconds"].default == 5

    def test_default_has_active_tsl_fn_calls_database_helper(self, monkeypatch):
        """has_active_tsl_fn दिलेला नसेल तर database.has_active_tsl_trades(MONITORED_SYMBOLS) वर
        डीफॉल्ट पडायला हवं (हलकी स्थानिक SQLite तपासणी, इथे mock करून खरी DB टाळलेली)."""
        now_fn, sleep_fn, _ = self._fake_clock()
        calls = []
        monkeypatch.setattr(trade_monitor.database, "has_active_tsl_trades", lambda symbols: calls.append(symbols) or False)
        trade_monitor.run_monitor_loop(
            "tok", "D", interval_seconds=20, loop_seconds=20,
            cycle_fn=lambda t, p: "ok", sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
        )
        assert calls == [trade_monitor.MONITORED_SYMBOLS]

    def test_cli_default_tsl_interval_seconds_is_5(self):
        source = inspect.getsource(trade_monitor)
        assert '"--tsl-interval-seconds", type=float, default=5' in source
