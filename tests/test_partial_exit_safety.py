"""tests/test_partial_exit_safety.py — Partial-exit safety fix (वापरकर्त्याचा निर्णय 2026-10-06, flag शिवाय).
आधीचा exit प्रयत्न अयशस्वी ⇒ पुढचा प्रयत्न broker positions मधल्या खऱ्या उघड्या qty वरून फक्त उरलेले legs पाठवतो; स्थिती अनिश्चित ⇒
काहीही पाठवत नाही + Telegram इशारा. परिस्थिती: partial-fill, double-retry, broker-mismatch, pending/unknown, positions नाहीत,
manual close. Network नाही."""
import datetime

import pytest

import notifications
import order_safety as OS
import trading_engine
from tests.test_trading_engine import FakeTime, seed_trade, temp_db  # noqa: F401  (fixture)

SL_LTPS = {"PE24400": 50.0, "PE24300": 2.0}            # pnl = (30 − 48) × 75 = −1350 < SL −1125
# trade: PE24400 SELL (short, बंद करायला BUY), PE24300 BUY (long hedge, बंद करायला SELL); qty 75
PARTIAL = {"status": "partial_failure", "verified_legs": [
    {"order_id": "O1", "instrument_token": "PE24400", "status": "complete", "filled_quantity": 75},
    {"order_id": "O2", "instrument_token": "PE24300", "status": "rejected", "filled_quantity": 0}]}
REJECTED = (400, {"status": "error", "errors": [{"message": "rejected"}]})


def _pos(short_net, long_net, product="D"):
    return [{"instrument_token": "PE24400", "quantity": short_net, "product": product},
            {"instrument_token": "PE24300", "quantity": long_net, "product": product}]


def _close_orders(qty=75, mcx=False):
    extra = {"broker_quantity": 1} if mcx else {}
    return [{"instrument_token": "PE24400", "transaction_type": "BUY", "quantity": qty, "product": "D", **extra},
            {"instrument_token": "PE24300", "transaction_type": "SELL", "quantity": qty, "product": "D", **extra}]


# ---- unit: plan_exit_resend ----------------------------------------------------------------------------------------------------------------
def test_first_attempt_is_unchanged():
    orders = _close_orders()
    assert OS.plan_exit_resend(orders, None, None) == (orders, None)
    assert OS.plan_exit_resend(orders, None, None)[0] is orders


def test_partial_fill_sends_only_remaining_leg():
    prior = {"last_sent": _close_orders(), "nofill": False, "pending_ids": []}
    out, why = OS.plan_exit_resend(_close_orders(), _pos(0, 75), prior)
    assert why is None and [o["instrument_token"] for o in out] == ["PE24300"] and out[0]["quantity"] == 75


def test_partial_qty_within_leg_sends_only_unfilled_qty():
    prior = {"last_sent": _close_orders(), "nofill": False, "pending_ids": []}
    out, why = OS.plan_exit_resend(_close_orders(), _pos(-25, 75), prior)
    assert why is None and {o["instrument_token"]: o["quantity"] for o in out} == {"PE24400": 25, "PE24300": 75}


def test_all_flat_means_nothing_to_send():
    prior = {"last_sent": _close_orders(), "nofill": False, "pending_ids": []}
    assert OS.plan_exit_resend(_close_orders(), _pos(0, 0), prior) == ([], None)


@pytest.mark.parametrize("positions, needle", [
    (_pos(+75, 75), "उलट्या"),                                   # short leg आता long ⇒ आधीच उलटी position
    (_pos(-150, 75), "> अपेक्षित"),                              # अपेक्षेपेक्षा जास्त (दुसरा trade?)
    ([{"instrument_token": "PE24300", "quantity": 75, "product": "D"}], "गहाळ"),   # leg positions मध्येच नाही
])
def test_broker_mismatch_blocks(positions, needle):
    prior = {"last_sent": _close_orders(), "nofill": False, "pending_ids": []}
    out, why = OS.plan_exit_resend(_close_orders(), positions, prior)
    assert out is None and needle in why


def test_mcx_partial_lots_is_ambiguous_and_blocks():
    prior = {"last_sent": _close_orders(mcx=True), "nofill": False, "pending_ids": []}
    out, why = OS.plan_exit_resend(_close_orders(qty=100, mcx=True), _pos(-40, 100), prior)
    assert out is None and "MCX" in why
    out, why = OS.plan_exit_resend(_close_orders(qty=100, mcx=True), _pos(-1, 0), prior)     # lots मध्ये पूर्ण leg उघडा ⇒ ठीक
    assert why is None and [o["instrument_token"] for o in out] == ["PE24400"]


def test_product_filter_ignores_other_product_positions():
    prior = {"last_sent": _close_orders(), "nofill": False, "pending_ids": []}
    positions = _pos(0, 75) + [{"instrument_token": "PE24400", "quantity": -75, "product": "I"}]
    out, why = OS.plan_exit_resend(_close_orders(), positions, prior)
    assert why is None and [o["instrument_token"] for o in out] == ["PE24300"]


def test_pending_orders_block_until_terminal():
    prior = {"last_sent": _close_orders(), "nofill": False, "pending_ids": ["O1"]}
    assert OS.plan_exit_resend(_close_orders(), _pos(0, 75), prior)[0] is None                       # status तपासता येत नाही
    assert OS.plan_exit_resend(_close_orders(), _pos(0, 75), prior, order_status=lambda oid: {"status": "open"})[0] is None
    assert OS.plan_exit_resend(_close_orders(), _pos(0, 75), prior, order_status=lambda oid: None)[0] is None
    out, why = OS.plan_exit_resend(_close_orders(), _pos(0, 75), prior, order_status=lambda oid: {"status": "complete"})
    assert why is None and [o["instrument_token"] for o in out] == ["PE24300"]


def test_no_positions_resends_last_sent_only_after_definite_nofill():
    last = [_close_orders()[1]]                                                                      # मागच्या वेळी फक्त PE24300 पाठवला
    out, why = OS.plan_exit_resend(_close_orders(), None, {"last_sent": last, "nofill": True, "pending_ids": []})
    assert why is None and [o["instrument_token"] for o in out] == ["PE24300"]
    out, why = OS.plan_exit_resend(_close_orders(), None, {"last_sent": last, "nofill": False, "pending_ids": []})
    assert out is None and "positions" in why


def test_exit_state_roundtrip_and_clear():
    OS.save_exit_state("T1", _close_orders(), 200, PARTIAL)
    st = OS.load_exit_state("T1")
    assert st["nofill"] is False and st["pending_ids"] == [] and len(st["last_sent"]) == 2
    OS.save_exit_state("T1", _close_orders(), 200, {"status": "error", "verified_legs": [{"order_id": "X", "status": "open"}]})
    assert OS.load_exit_state("T1")["pending_ids"] == ["X"]
    OS.save_exit_state("T1", _close_orders(), 200, {"status": "error", "data": {"order_ids": ["A", "B"]}})   # fill अज्ञात ⇒ pending
    assert OS.load_exit_state("T1")["pending_ids"] == ["A", "B"]
    OS.record_success("T1")
    assert OS.load_exit_state("T1") is None


# ---- manage_open_trades (LIVE) सोबत --------------------------------------------------------------------------------------------------------
@pytest.fixture
def live_sl(temp_db, monkeypatch):  # noqa: F811
    seed_trade(temp_db, "TX", net_credit=30, sl_level=-1125, target_level=1800, mode="LIVE")
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: dict(SL_LTPS))
    FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)          # IST 10:30
    monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
    monkeypatch.setattr(trading_engine, "_maybe_cancel_broker_side_sl", lambda *a, **k: None)
    sent_msgs = []
    monkeypatch.setattr(notifications, "send_telegram_message", lambda msg, *a, **k: sent_msgs.append(msg))
    state = {"positions": _pos(-75, 75), "calls": [], "replies": [], "order_status": {}}
    monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: state["positions"])
    monkeypatch.setattr(trading_engine, "upstox_get_order_details", lambda t, oid: state["order_status"].get(oid))

    def send(t, orders, m):
        state["calls"].append([(o["instrument_token"], o["transaction_type"], o["quantity"]) for o in orders])
        return state["replies"].pop(0) if state["replies"] else (200, {"status": "success"})
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", send)
    return temp_db, state, sent_msgs


def _status(db, tid="TX"):
    import sqlite3
    c = sqlite3.connect(db)
    r = c.execute("SELECT status FROM live_trades WHERE trade_id=?", (tid,)).fetchone()
    c.close()
    return r[0]


def test_partial_fill_then_next_cycle_sends_only_remaining_leg(live_sl):
    db, st, msgs = live_sl
    st["replies"] = [(200, dict(PARTIAL))]
    assert trading_engine.manage_open_trades("tok", "NIFTY", "D") == []
    assert st["calls"] == [[("PE24400", "BUY", 75), ("PE24300", "SELL", 75)]]
    st["positions"] = _pos(0, 75)                                      # short leg बंद झाला, hedge अजून उघडा
    closed = trading_engine.manage_open_trades("tok", "NIFTY", "D")
    assert st["calls"][1] == [("PE24300", "SELL", 75)]                 # PE24400 पुन्हा पाठवला नाही ⇒ उलटी position नाही
    assert len(closed) == 1 and _status(db) == "CLOSED" and OS.load_exit_state("TX") is None


def test_double_retry_never_resends_closed_leg(live_sl, monkeypatch):
    db, st, msgs = live_sl
    monkeypatch.setattr(OS, "_settings", lambda: {"exit_retry_on_fail": True})
    monkeypatch.setattr(OS.time, "sleep", lambda s: None)
    st["replies"] = [(200, dict(PARTIAL)), REJECTED, REJECTED, REJECTED]
    trading_engine.manage_open_trades("tok", "NIFTY", "D")              # cycle 1: partial (in-cycle retry नाही)
    st["positions"] = _pos(0, 75)
    trading_engine.manage_open_trades("tok", "NIFTY", "D")              # cycle 2: hedge rejected ⇒ निश्चित no-fill ⇒ in-cycle retry
    trading_engine.manage_open_trades("tok", "NIFTY", "D")              # cycle 3: पुन्हा फक्त hedge
    # cycle 2: hedge (rejected) + retry hedge (rejected); cycle 3: hedge (rejected) + retry hedge (डीफॉल्ट success)
    assert len(st["calls"]) == 5
    assert all(c == [("PE24300", "SELL", 75)] for c in st["calls"][1:])
    assert _status(db) == "CLOSED"


def test_broker_mismatch_blocks_and_alerts(live_sl):
    db, st, msgs = live_sl
    st["replies"] = [(200, dict(PARTIAL))]
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    st["positions"] = _pos(+75, 75)                                     # short leg उलटा झाला (बाहेरून?) ⇒ mismatch
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    assert len(st["calls"]) == 1 and _status(db) == "OPEN"
    assert any("EXIT थांबवला" in m and "उलट्या" in m for m in msgs)


def test_unknown_pending_state_blocks_then_resumes(live_sl):
    db, st, msgs = live_sl
    st["replies"] = [(200, {"status": "error", "verified_legs": [
        {"order_id": "O1", "instrument_token": "PE24400", "status": "open"},
        {"order_id": "O2", "instrument_token": "PE24300", "status": "rejected", "filled_quantity": 0}]})]
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    st["order_status"] = {"O1": {"status": "open"}}
    st["positions"] = _pos(-75, 75)
    trading_engine.manage_open_trades("tok", "NIFTY", "D")              # O1 अजून pending ⇒ थांबा
    assert len(st["calls"]) == 1 and any("EXIT थांबवला" in m and "O1" in m for m in msgs)
    st["order_status"] = {"O1": {"status": "complete"}}
    st["positions"] = _pos(0, 75)
    closed = trading_engine.manage_open_trades("tok", "NIFTY", "D")
    assert st["calls"][1] == [("PE24300", "SELL", 75)] and len(closed) == 1


def test_positions_unavailable_after_partial_blocks(live_sl):
    db, st, msgs = live_sl
    st["replies"] = [(200, dict(PARTIAL))]
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    st["positions"] = None
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    assert len(st["calls"]) == 1 and any("EXIT थांबवला" in m for m in msgs) and _status(db) == "OPEN"


def test_blocked_alert_is_throttled(live_sl):
    db, st, msgs = live_sl
    st["replies"] = [(200, dict(PARTIAL))]
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    st["positions"] = None
    for _ in range(5):
        trading_engine.manage_open_trades("tok", "NIFTY", "D")
    blocked = [m for m in msgs if "EXIT थांबवला" in m]
    assert len(blocked) == 2 and "#1" in blocked[0] and "#5" in blocked[1]       # पहिला blocked प्रसंग लगेच, मग दर 5वा


def test_paper_repeated_failures_still_send_all_legs(temp_db, monkeypatch):  # noqa: F811
    seed_trade(temp_db, "TP", net_credit=30, sl_level=-1125, target_level=1800, mode="PAPER")
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: dict(SL_LTPS))
    FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
    monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
    monkeypatch.setattr(notifications, "send_telegram_message", lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (calls.append(len(o)), (500, {"status": "error"}))[1])
    for _ in range(2):
        trading_engine.manage_open_trades("tok", "NIFTY", "D")
    assert calls == [2, 2] and OS.load_exit_state("TP") is None


def test_manual_close_after_partial_sends_only_remaining(live_sl):
    db, st, msgs = live_sl
    st["replies"] = [(200, dict(PARTIAL))]
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    st["positions"] = _pos(0, 75)
    ok, _ = trading_engine.close_trade_manually("tok", "TX", "NIFTY", "D")
    assert ok and st["calls"][1] == [("PE24300", "SELL", 75)] and _status(db) == "CLOSED"
    assert OS.load_exit_state("TX") is None


def test_manual_close_blocked_on_mismatch(live_sl):
    db, st, msgs = live_sl
    st["replies"] = [(200, dict(PARTIAL))]
    trading_engine.manage_open_trades("tok", "NIFTY", "D")
    st["positions"] = _pos(-150, 75)
    ok, msg = trading_engine.close_trade_manually("tok", "TX", "NIFTY", "D")
    assert not ok and "थांबवला" in msg and len(st["calls"]) == 1 and _status(db) == "OPEN"
