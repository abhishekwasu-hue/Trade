"""Vision V1 — 5-Min Instant bot सोबत end-to-end (network / broker mock, signal_log sqlite shim): HOLD ⇒ trade नाही आणि hit मोजणीत नाही;
approve (½) ⇒ पुढच्या cycle ला touch नसला तरी अर्ध्या lots ने entry; reject ⇒ मूळ lots ने PAPER shadow (वेगळा source); LIVE ⇒ vision नाही."""
import datetime
from unittest.mock import patch

import pytest

import cloud_db
import dynamic_sr_instant_trader as dsr
from tests.test_dynamic_sr_instant_trader import _candles_with_rsi, _fake_chain, _fake_zones
from tests.test_min_hold_end_to_end import _hover, _statuses, signal_db  # noqa: F401  (fixture)
from vision import config as VC
from vision import store as VS

T0 = datetime.datetime(2026, 9, 11, 10, 0, 0)


@pytest.fixture(autouse=True)
def _restore_clock():
    orig = VS.now_ist
    yield
    VS.now_ist = orig


def _run(now, hover, **overrides):
    VS.now_ist = lambda: now                                                      # vision चं IST घड्याळ = bot चं (fixture परत ठेवतो)
    settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
    settings.update(entry_rsi_gate_enabled=False, entry_pcr_gate_enabled=False, naked_enabled=False, entry_min_hold_gate_enabled=False,
                    lots=2, trading_mode="PAPER")
    settings.update(overrides)
    candles = _candles_with_rsi(_hover(hover), declining=True, today_ist=now)
    with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
         patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
         patch.object(dsr, "get_ist_now", return_value=now), \
         patch.object(dsr, "fetch_candles", return_value=candles), \
         patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
         patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
         patch.object(dsr, "has_open_trade_from_source", return_value=False), \
         patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
         patch.object(dsr, "send_telegram_message", return_value=True):
        dsr.process_symbol("fake_token", "NIFTY")
    return mock_trade.call_args_list


def _vtc():
    VC.save("dynamic_sr_instant", {"vision_mode": "veto_then_confirm"}, "t", trading_mode_fn=lambda b, s: "PAPER")


def _only_row():
    rows = [r for r in VS.list_signals() if r["bot"] == "dynamic_sr_instant"]
    assert len(rows) == 1
    return rows[0]


def test_hold_then_half_size_entry_after_approve_even_without_touch(signal_db):
    _vtc()
    assert _run(T0, 1) == []                                                      # HOLD — trade नाही
    assert "SKIPPED_VISION_PENDING" in _statuses(signal_db)
    hits, _, last_trade = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-11", role="SUPPORT")
    assert hits == 0 and last_trade is None                                       # hit / cooldown मोजणीत नाही
    r = _only_row()
    VS.update(r["signal_id"], status="APPROVED", factor=0.5, decided_at=VS._iso(T0), median_range=1000.0)
    calls = _run(T0 + datetime.timedelta(minutes=1), 0)                           # price level सोडून गेली (touch नाही) ⇒ forced
    assert len(calls) == 1
    kw = calls[0].kwargs
    assert kw["lots"] == 1 and kw["source"] == "dynamic_sr_instant" and kw["trading_mode"] == "PAPER"   # ½ × 2 lots
    r = VS.get_signal(r["signal_id"])
    assert r["status"] == "EXECUTED" and "OPENED" in (r["exec_note"] or "")


def test_rejected_signal_opens_paper_shadow_with_original_lots(signal_db):
    _vtc()
    _run(T0, 1)
    r = _only_row()
    VS.update(r["signal_id"], status="REJECTED", factor=0.0, decided_at=VS._iso(T0))
    calls = _run(T0 + datetime.timedelta(minutes=1), 1)
    assert len(calls) == 1
    kw = calls[0].kwargs
    assert kw["source"] == "dynamic_sr_instant_vision_shadow" and kw["trading_mode"] == "PAPER" and kw["lots"] == 2
    assert "SKIPPED_VISION_REJECTED" in _statuses(signal_db)
    assert VS.get_signal(r["signal_id"])["status"] == "SHADOWED"
    hits, _, _ = cloud_db.get_zone_hits_today("NIFTY", 23900.0, "2026-09-11", role="SUPPORT")
    assert hits == 0                                                              # shadow खरा entry नाही


def test_live_bot_unaffected_by_v1_mode(signal_db):
    _vtc()
    calls = _run(T0, 1, trading_mode="LIVE")
    assert len(calls) == 1 and calls[0].kwargs["lots"] == 2 and calls[0].kwargs["source"] == "dynamic_sr_instant"
    assert not [r for r in VS.list_signals() if r["bot"] == "dynamic_sr_instant"]


def test_notify_mode_trades_immediately_full_size(signal_db):
    VC.save("dynamic_sr_instant", {"approval_required": False}, "t", trading_mode_fn=lambda b, s: "PAPER")   # जुनं V0 वर्तन (approval बंद)
    calls = _run(T0, 1)                                                           # default notify (V0)
    assert len(calls) == 1 and calls[0].kwargs["lots"] == 2
    assert _only_row()["status"] == "QUEUED" and _only_row()["mode"] == "notify"


def test_rejected_level_then_notify_mode_no_forced_entry(signal_db):
    """Review B1: नाकारलेला level, मग तुम्ही notify केलं ⇒ पुढच्या cycle ला touch नसताना algorithm चा पूर्ण-size entry होऊ नये."""
    _vtc()
    _run(T0, 1)
    r = _only_row()
    VS.update(r["signal_id"], status="REJECTED", factor=0.0, decided_at=VS._iso(T0))
    VC.save("dynamic_sr_instant", {"vision_mode": "notify", "approval_required": False}, "t", trading_mode_fn=lambda b, s: "PAPER")
    assert _run(T0 + datetime.timedelta(minutes=1), 0) == []


def test_half_size_zero_lot_leg_goes_to_shadow_not_zero_order(signal_db):
    """Review B2: lots 1 × ½ = 0 ⇒ 0-lot order नाही, shadow."""
    _vtc()
    _run(T0, 1, lots=1)
    r = _only_row()
    VS.update(r["signal_id"], status="APPROVED", factor=0.5, decided_at=VS._iso(T0), median_range=1000.0)
    calls = _run(T0 + datetime.timedelta(minutes=1), 1, lots=1)
    assert len(calls) == 1 and calls[0].kwargs["source"] == "dynamic_sr_instant_vision_shadow" and calls[0].kwargs["lots"] == 1
    assert "SKIPPED_VISION_HALF_ZERO" in _statuses(signal_db)


def test_control_no_touch_no_trade_without_vision_decision(signal_db):
    """Control: approve test मधला entry forced level मुळेच — touch नसताना (hover 0) साधारणपणे trade होत नाही."""
    assert _run(T0 + datetime.timedelta(minutes=1), 0) == []
