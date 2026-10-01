"""
tests/test_min_hold_end_to_end.py
---------------------------------
"3 मिनिट level hold" चा minute-by-minute end-to-end पडताळा — असली `cloud_db.save_signal_log` /
`get_zone_hits_today` (sqlite shim वर, Postgres ऐवजी) वापरून, फक्त network/broker mock करून. unit tests मध्ये
हे हरवत होतं: max-2-hits counter signal_log च्या **सर्व** touch rows मोजतो, गेटने 'थांबवलेला' touch सुद्धा.
"""
import datetime
import sqlite3
from unittest.mock import patch

import pytest

import cloud_db
import dynamic_sr_instant_trader as dsr
from tests.test_dynamic_sr_instant_trader import _candles_with_rsi, _fake_chain, _fake_zones

sqlite3.register_converter("TIMESTAMP", lambda b: datetime.datetime.fromisoformat(b.decode()))
sqlite3.register_adapter(datetime.datetime, lambda d: d.isoformat(sep=" "))


class _Cur:
    def __init__(self, conn):
        self._c = conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        self._c.execute(sql.replace("%s", "?"), params)

    def fetchone(self):
        return self._c.fetchone()

    def fetchall(self):
        return self._c.fetchall()


class _Conn:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _Cur(self._conn)

    def commit(self):
        self._conn.commit()

    def close(self):  # shared in-memory DB — बंद करायचं नाही
        pass


@pytest.fixture
def signal_db():
    raw = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    raw.execute(
        "CREATE TABLE signal_log (symbol TEXT, trade_date TEXT, signal_time TIMESTAMP, level_type TEXT, "
        "level_price REAL, hit_type TEXT, direction TEXT, ltp_at_signal REAL, trade_status TEXT, reason TEXT)"
    )
    conn = _Conn(raw)
    with patch.object(cloud_db, "get_connection", lambda: conn):
        yield raw


def _hover(n):
    """n सलग 1-मिनिट candles जे 23900 (level) च्या रेंजमध्ये राहतात."""
    return [{"open": 23900.0, "high": 23901.0, "low": 23899.0, "close": 23900.0} for _ in range(n)]


def _run_5m(now, hover_candles, **overrides):
    settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
    settings.update(entry_rsi_gate_enabled=False, entry_pcr_gate_enabled=False, naked_enabled=False,
                    entry_min_hold_gate_enabled=True, entry_min_hold_minutes=3)
    settings.update(overrides)
    candles = _candles_with_rsi(_hover(hover_candles), declining=True, today_ist=now)
    with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
         patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
         patch.object(dsr, "get_ist_now", return_value=now), \
         patch.object(dsr, "fetch_candles", return_value=candles), \
         patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
         patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
         patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
         patch.object(dsr, "send_telegram_message", return_value=True):
        dsr.process_symbol("fake_token", "NIFTY")
    return mock_trade.called


def _statuses(raw):
    return [r[0] for r in raw.execute("SELECT trade_status FROM signal_log ORDER BY rowid").fetchall()]


class TestFiveMinuteMinHoldEndToEnd:
    T0 = datetime.datetime(2026, 9, 11, 10, 0, 0)

    def test_three_minute_hold_then_entry(self, signal_db):
        # मिनिट 1 आणि 2: level वर फक्त 1-2 मिनिटं -> थांब; मिनिट 3: 3 मिनिटं -> entry
        assert _run_5m(self.T0, 1) is False
        assert _run_5m(self.T0 + datetime.timedelta(minutes=1), 2) is False
        assert _run_5m(self.T0 + datetime.timedelta(minutes=2), 3) is True
        assert _statuses(signal_db)[0] == "SKIPPED_MIN_HOLD_DURATION"

    def test_second_trade_on_same_level_not_blocked_by_gate_waiting_touches(self, signal_db):
        # पहिला trade (3 मिनिटांच्या प्रतीक्षेनंतर) ...
        _run_5m(self.T0, 1)
        assert _run_5m(self.T0 + datetime.timedelta(minutes=2), 3) is True
        # ... तासाभराने त्याच level वर पुन्हा ताजा touch (held=1): 2रा trade गेटशिवाय व्हायला हवा.
        # गेटच्या 'प्रतीक्षा' touch ने max-2-hits counter खाऊ नये.
        assert _run_5m(self.T0 + datetime.timedelta(hours=1), 1) is True

    def test_waiting_touch_and_naked_diagnostic_rows_are_not_hits(self, signal_db):
        now = self.T0
        for status in ("SKIPPED_MIN_HOLD_DURATION", "SKIPPED_NAKED_DISABLED", "SKIPPED_NAKED_STRIKE_NOT_FOUND", "OPENED"):
            signal_db.execute(
                "INSERT INTO signal_log VALUES ('NIFTY','2026-09-11',?,'DYNAMIC_SR_SUPPORT_5M',23900.0,'TOUCH','BULLISH',23900,?,'')",
                (now, status),
            )
        hits, _last_hit, last_trade = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-11", role="SUPPORT")
        assert hits == 1  # फक्त OPENED
        assert last_trade == now

    def test_price_leaving_the_level_before_three_minutes_never_enters(self, signal_db):
        # मिनिट 1: touch (held=1) -> थांब; मिनिट 2: किंमत level सोडून गेली -> touch नाहीच; entry नाही
        assert _run_5m(self.T0, 1) is False
        assert _run_5m(self.T0 + datetime.timedelta(minutes=1), 0) is False
        assert "OPENED" not in _statuses(signal_db)

    def test_gate_keeps_applying_after_rejected_touch_until_a_real_trade(self, signal_db):
        _run_5m(self.T0, 1)
        # 20 मिनिटांनी पुन्हा ताजा touch (held=1) -> अजूनही कुठलाच खरा trade झालेला नाही -> गेट लागू
        assert _run_5m(self.T0 + datetime.timedelta(minutes=20), 1) is False


class TestFifteenMinuteMinHoldEndToEnd:
    def _run(self, now, hover_minutes, **overrides):
        import pandas as pd
        import srv2_momentum_reversal_strategy as srv2
        from tests.test_srv2_momentum_reversal_strategy import _fake_candles_df, _fake_dyn_zones, _one_min_df
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        settings.update(symbol_enabled=True, naked_enabled=False, entry_rsi_gate_enabled=False,
                        entry_pcr_gate_enabled=False, entry_min_hold_gate_enabled=True, entry_min_hold_minutes=3)
        settings.update(overrides)
        with patch.object(srv2, "get_ist_now", return_value=now):
            candles_15m = _fake_candles_df(last_close=23902)
            rows = [(23930, 23935, 23925, 23928)] + [(23902, 23906, 23898, 23901)] * hover_minutes
            one_min = _one_min_df(rows, day=now)

        def _fetch(token, symbol, current_spot=0, interval="15minute", lookback_days=5):
            return one_min if interval == "1minute" else candles_15m

        with patch.object(srv2, "get_ist_now", return_value=now), \
             patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(srv2, "fetch_candles", side_effect=_fetch), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones(support_level=23900.0)), \
             patch.object(srv2, "get_last_sl_tsl_exit_time", return_value=None), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
        return mock_trade.called

    T0 = datetime.datetime(2026, 9, 11, 12, 0, 0)

    def test_three_minute_hold_then_entry_then_second_trade_without_wait(self, signal_db):
        # candles 12:00 पासून; शेवटचा candle = now. hover_minutes = level वर सलग टिकलेले candles.
        assert self._run(self.T0 + datetime.timedelta(minutes=1), 1) is False
        assert self._run(self.T0 + datetime.timedelta(minutes=2), 2) is False
        assert self._run(self.T0 + datetime.timedelta(minutes=3), 3) is True
        # तासाभराने पुन्हा ताजा touch (held=1): 2रा trade गेटशिवाय, आणि प्रतीक्षा-नोंदीने max-hits भरला नाही
        assert self._run(self.T0 + datetime.timedelta(hours=1), 1) is True


class TestNakedOnlyModeIsLoggedAsRealTrade:
    """entry-gate review मध्ये सापडलेली bug — credit_spread_enabled=False (naked-only) मोडमध्ये naked trade चा
    निकाल signal_log मध्ये कधीच जायचा नाही; फक्त 'SKIPPED_CREDIT_SPREAD_DISABLED' (no-action) जायचा, त्यामुळे
    30-मिनिट cooldown ला खरा trade दिसायचाच नाही आणि त्याच level वर पुन्हा पुन्हा entry व्हायची."""
    T0 = datetime.datetime(2026, 9, 11, 10, 0, 0)
    NAKED = {"strategy": "LONG_PUT", "legs": []}

    def _run(self, now, naked_result=NAKED, **overrides):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings.update(entry_rsi_gate_enabled=False, entry_pcr_gate_enabled=False, naked_enabled=True,
                        credit_spread_enabled=False, entry_min_hold_gate_enabled=False)
        settings.update(overrides)
        candles = _candles_with_rsi(_hover(1), declining=True, today_ist=now)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=now), \
             patch.object(dsr, "fetch_candles", return_value=candles), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_naked_option_itm", return_value=naked_result), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True):
            dsr.process_symbol("fake_token", "NIFTY")
        return mock_trade.call_count

    def test_naked_result_is_saved_as_the_trade_status(self, signal_db):
        assert self._run(self.T0) == 1
        statuses = _statuses(signal_db)
        assert any(s and not s.startswith("SKIPPED_") for s in statuses), statuses
        assert "SKIPPED_CREDIT_SPREAD_DISABLED" not in statuses

    def test_cooldown_applies_after_a_naked_only_trade(self, signal_db):
        assert self._run(self.T0) == 1
        # 10 मिनिटांनी त्याच level वर पुन्हा touch — 30-मिनिट cooldown ने थांबवायला हवं
        assert self._run(self.T0 + datetime.timedelta(minutes=10)) == 0
        assert "SKIPPED_COOLDOWN_30MIN" in _statuses(signal_db)

    def test_naked_strike_not_found_leaves_no_hit(self, signal_db):
        assert self._run(self.T0, naked_result=None) == 0
        hits, _h, last_trade = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-11", role="SUPPORT")
        assert hits == 0 and last_trade is None

    def test_both_disabled_still_logs_a_skip_row_that_is_not_a_hit(self, signal_db):
        assert self._run(self.T0, naked_enabled=False) == 0
        assert "SKIPPED_CREDIT_SPREAD_DISABLED" in _statuses(signal_db)
        hits, _h, last_trade = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-11", role="SUPPORT")
        assert hits == 0 and last_trade is None
