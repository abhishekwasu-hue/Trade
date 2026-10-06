"""tests/test_order_safety.py — G3: market_protection setting (डीफॉल्ट: field नाही), exit-अपयश इशारा (leg-निहाय, throttle, partial धोका),
पूर्ण-अपयश retry (डीफॉल्ट OFF); manage_open_trades / open_multi_leg_trade सोबत एकत्रित. Network नाही."""
import datetime

import pytest

import notifications
import order_safety as OS
import trading_engine
from tests.test_trading_engine import FakeTime, seed_trade, temp_db  # noqa: F401  (fixture)

SL_LTPS = {"PE24400": 50.0, "PE24300": 2.0}            # pnl = (30 − 48) × 75 = −1350 < SL −1125


# ---- unit ----------------------------------------------------------------------------------------------------------------------------------
def test_market_protection_setting_defaults_to_none_and_validates():
    assert OS.market_protection_pct({}) is None
    assert OS.market_protection_pct({"order_market_protection_pct": None}) is None
    assert OS.market_protection_pct({"order_market_protection_pct": 0}) is None
    assert OS.market_protection_pct({"order_market_protection_pct": 30}) is None
    assert OS.market_protection_pct({"order_market_protection_pct": True}) is None
    assert OS.market_protection_pct({"order_market_protection_pct": "3"}) == 3


def test_apply_market_protection_returns_same_list_by_default():
    orders = [{"order_type": "MARKET"}, {"order_type": "LIMIT"}]
    assert OS.apply_market_protection(orders, {}) is orders
    out = OS.apply_market_protection(orders, {"order_market_protection_pct": 2})
    assert out[0]["market_protection"] == 2 and "market_protection" not in out[1] and "market_protection" not in orders[0]


def test_alert_throttle_and_counts():
    assert [OS.should_alert(n) for n in (1, 2, 4, 5, 6, 10)] == [True, False, False, True, False, True]
    assert OS.record_failure("T") == 1 and OS.record_failure("T") == 2
    assert OS.record_success("T") == 2 and OS.record_success("T") == 0


PARTIAL = {"status": "partial_failure", "verified_legs": [{"instrument_token": "PE24400", "status": "complete"},
                                                          {"instrument_token": "PE24300", "status": "rejected"}]}


def test_failure_message_partial_and_full():
    m = OS.failure_message("NIFTY", "T1", "SL", 1, 200, PARTIAL)
    assert "POSITION अजून उघडी आहे" in m and "PARTIAL EXIT" in m and "PE24400" in m
    full = OS.failure_message("NIFTY", "T1", "SL", 1, 400, {"status": "error", "errors": [{"message": "market order not allowed"}]})
    assert "PARTIAL" not in full and "market order not allowed" in full
    assert OS.is_full_failure({"status": "error"}) and not OS.is_full_failure(PARTIAL)


def test_retry_only_on_full_failure_and_only_when_enabled():
    calls = []
    send = lambda: (calls.append(1), (200, {"status": "success"}))[1]                              # noqa: E731
    on = {"exit_retry_on_fail": True}
    assert OS.retry_full_failure_once(send, 500, {"status": "error"}, {}, sleep=lambda s: None)[2] is False
    sc, rs, retried = OS.retry_full_failure_once(send, 500, {"status": "error"}, on, sleep=lambda s: None)
    assert retried and sc == 200 and len(calls) == 1
    assert OS.retry_full_failure_once(send, 200, PARTIAL, on, sleep=lambda s: None)[2] is False      # partial ⇒ retry नाही
    assert OS.retry_full_failure_once(send, 200, {"status": "success"}, on, sleep=lambda s: None)[2] is False


# ---- manage_open_trades सोबत ---------------------------------------------------------------------------------------------------------------
@pytest.fixture
def sl_setup(temp_db, monkeypatch):  # noqa: F811
    seed_trade(temp_db, "TX", net_credit=30, sl_level=-1125, target_level=1800)
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: dict(SL_LTPS))
    FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)          # IST 10:30
    monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
    sent = []
    monkeypatch.setattr(notifications, "send_telegram_message", lambda msg, *a, **k: sent.append(msg))
    return temp_db, sent


def _exit_alerts(sent):
    return [m for m in sent if "EXIT ORDER अयशस्वी" in m]


def test_exit_failure_alerts_first_then_every_fifth_then_recovery(sl_setup, monkeypatch):
    _, sent = sl_setup
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (500, {"status": "error"}))
    for _ in range(5):
        assert trading_engine.manage_open_trades("fake_token", "NIFTY", "D") == []
    alerts = _exit_alerts(sent)
    assert len(alerts) == 2 and "#1" in alerts[0] and "#5" in alerts[1] and "POSITION अजून उघडी आहे" in alerts[0]
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
    closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
    assert len(closed) == 1 and any("अखेर बंद झाली" in m and "5 वेळा" in m for m in sent)


def test_partial_exit_alert_warns_about_reverse_position(sl_setup, monkeypatch):
    _, sent = sl_setup
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, dict(PARTIAL)))
    trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
    assert any("PARTIAL EXIT" in m for m in _exit_alerts(sent))


def test_alert_can_be_disabled(sl_setup, monkeypatch):
    _, sent = sl_setup
    monkeypatch.setattr(OS, "_settings", lambda: {"exit_fail_alert": False})
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (500, {"status": "error"}))
    trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
    assert _exit_alerts(sent) == []


def test_default_no_retry_and_no_market_protection_on_exit(sl_setup, monkeypatch):
    calls = []

    def send(t, orders, m):
        calls.append(orders)
        return 500, {"status": "error"}
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", send)
    monkeypatch.setattr(trading_engine.time, "sleep", lambda s: None)
    trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
    assert len(calls) == 1 and all("market_protection" not in o for o in calls[0])


def test_retry_and_market_protection_when_enabled(sl_setup, monkeypatch):
    monkeypatch.setattr(OS, "_settings", lambda: {"exit_retry_on_fail": True, "order_market_protection_pct": 3})
    monkeypatch.setattr(OS.time, "sleep", lambda s: None)
    calls = []

    def send(t, orders, m):
        calls.append(orders)
        return (500, {"status": "error"}) if len(calls) == 1 else (200, {"status": "success"})
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", send)
    closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
    assert len(calls) == 2 and len(closed) == 1 and all(o["market_protection"] == 3 for o in calls[1])


def test_partial_failure_is_never_retried_in_cycle(sl_setup, monkeypatch):
    monkeypatch.setattr(OS, "_settings", lambda: {"exit_retry_on_fail": True})
    calls = []
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (calls.append(o), (200, dict(PARTIAL)))[1])
    trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
    assert len(calls) == 1


# ---- entry (open_multi_leg_trade) ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("settings, expect", [({}, None), ({"order_market_protection_pct": 4}, 4)])
def test_entry_orders_market_protection_only_when_set(temp_db, monkeypatch, settings, expect):  # noqa: F811
    monkeypatch.setattr(OS, "_settings", lambda: settings)
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})
    captured = {}

    def fake_execute(token, orders, mode):
        captured["orders"] = orders
        return 200, {"status": "success", "data": {"order_ids": ["A", "B"]}}
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)
    sr = {"strategy": "BULL_PUT_SPREAD", "short_leg": {"strike": 24400, "instrument_key": "PE24400", "ltp": 50},
          "long_leg": {"strike": 24300, "instrument_key": "PE24300", "ltp": 25}, "net_credit": 25, "max_profit": 25, "max_loss": 75}
    trading_engine.open_multi_leg_trade("fake_token", "NIFTY", sr, lots=1, lot_size=75, sl_pct_of_max_loss=999, target_pct_of_max_profit=30,
                                        product_type="D", trading_mode="PAPER", trading_style="SWING", sl_pct_of_credit=30)
    got = [o.get("market_protection") for o in captured["orders"]]
    assert got == [expect, expect] and all(("market_protection" in o) == (expect is not None) for o in captured["orders"])
