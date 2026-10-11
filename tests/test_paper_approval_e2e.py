"""Abhi review (PR #281) — production default (approval_required = True) ने तिन्ही bots end-to-end:
signal ⇒ PENDING_HUMAN ⇒ (a) timeout ⇒ **कुठलीही PAPER position नाही** (shadow सुद्धा नाही, फक्त would-have नोंद), (b) ✅ ⇒ एकच position.
आणि behaviour tests: exits pause / kill-switch / PAPER pause / vision चूक असतानाही चालतात; watcher फक्त exits नंतर, stream loop मध्ये कधीच नाही."""
import datetime
from unittest.mock import patch

import pandas as pd
import pytest

import cloud_db
import dynamic_sr_instant_trader as dsr
import srv2_momentum_reversal_strategy as srv2
import srv3_instant_shadow as SH
import trade_monitor
import trading_engine
from paper import journal as PJ
from paper import pause as PP
from paper import watch as PW
from tests.test_dynamic_sr_instant_trader import _candles_with_rsi, _fake_chain, _fake_zones
from tests.test_min_hold_end_to_end import _hover, signal_db  # noqa: F401 (fixture)
from tests.test_trading_engine import FakeTime, seed_trade, temp_db  # noqa: F401 (fixture)
from tests.test_vision_v1 import KEY, ME
from vision import config as VC
from vision import decide as VD
from vision import store as VS
from vision import telegram_bot as TB

T0 = datetime.datetime(2026, 9, 11, 10, 0, 0)


@pytest.fixture(autouse=True)
def prod(monkeypatch):
    """production default: approval_required = True; Telegram बटणं (HMAC + approver) — खरा network नाही."""
    monkeypatch.setitem(VC.BOT_DEFAULTS, "approval_required", True)
    monkeypatch.setenv("VISION_CALLBACK_SECRET", KEY)
    monkeypatch.setenv("TELEGRAM_APPROVER_IDS", str(ME))
    orig = VS.now_ist
    yield
    VS.now_ist = orig


def _pending(sid, now):
    VS.transition(sid, ("QUEUED",), "PENDING_HUMAN", None, deadline=VS._iso(now + datetime.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0, median_range=1000.0)   # worker प्रमाणे (drift guard साठी)


def _approve(sid, now):
    cq = {"id": "c", "from": {"id": ME}, "message": {"chat": {"id": ME}, "message_id": 1}, "data": VD.callback_data(sid, "A")}
    ok, _ = TB.handle_callback(cq, now=now, answer=lambda *a: None, edit=lambda *a: None)
    assert ok
    assert VS.get_signal(sid)["decided_by"] == f"telegram:{ME}"


def _rows(bot):
    return [r for r in VS.list_signals() if r["bot"] == bot]


# ------------------------------------------------------------------------------------------------ 5-Min Instant
def _dsr(now, hover=1):
    VS.now_ist = lambda: now
    s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
    s.update(entry_rsi_gate_enabled=False, entry_pcr_gate_enabled=False, naked_enabled=False, entry_min_hold_gate_enabled=False, lots=2,
             trading_mode="PAPER")
    with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=s), \
         patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
         patch.object(dsr, "get_ist_now", return_value=now), \
         patch.object(dsr, "fetch_candles", return_value=_candles_with_rsi(_hover(hover), declining=True, today_ist=now)), \
         patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
         patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
         patch.object(dsr, "has_open_trade_from_source", return_value=False), \
         patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as m, \
         patch.object(dsr, "send_telegram_message", return_value=True):
        dsr.process_symbol("fake_token", "NIFTY")
    return m.call_args_list


def test_dsr_timeout_no_position_at_all(signal_db):
    assert _dsr(T0) == []                                                        # HOLD (default notify ⇒ human_confirm)
    (r,) = _rows("dynamic_sr_instant")
    assert r["mode"] == "human_confirm"
    _pending(r["signal_id"], T0)
    assert _dsr(T0 + datetime.timedelta(minutes=11)) == []                       # timeout ⇒ REJECTED ⇒ shadow position सुद्धा नाही
    assert _dsr(T0 + datetime.timedelta(minutes=12)) == []
    wh = PJ.would_have_rows()
    assert len(wh) == 1 and wh[0]["lots"] == 0 and wh[0]["status"] == "SKIPPED_VISION_REJECTED"


def test_dsr_approve_one_position(signal_db):
    _dsr(T0)
    (r,) = _rows("dynamic_sr_instant")
    _pending(r["signal_id"], T0)
    _approve(r["signal_id"], T0 + datetime.timedelta(minutes=1))
    calls = _dsr(T0 + datetime.timedelta(minutes=1), hover=0)                   # touch नसला तरी approved level (forced)
    assert len(calls) == 1 and calls[0].kwargs["source"] == "dynamic_sr_instant" and calls[0].kwargs["trading_mode"] == "PAPER"
    assert _dsr(T0 + datetime.timedelta(minutes=2), hover=0) == []               # पुन्हा entry नाही


# ------------------------------------------------------------------------------------------------ 15M Dynamic SR
def _srv2_candles(now, n=20, last_close=23905):
    """tests/test_srv2_momentum_reversal_strategy._fake_candles_df सारखेच, पण `now` च्या आधी बंद झालेल्या 15M bars पर्यंत."""
    end_ts = pd.Timestamp(now).floor("15min") - pd.Timedelta(minutes=15)
    closes = [24100 - i * 10 for i in range(n - 1)] + [last_close]
    return pd.DataFrame({"timestamp": pd.date_range(end=end_ts, periods=n, freq="15min"), "open": closes, "high": [c + 15 for c in closes],
                         "low": [c - 15 for c in closes], "close": closes, "volume": 0, "oi": 0})


def _srv2(now):
    VS.now_ist = lambda: now
    s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
    s.update(entry_rsi_gate_enabled=False, naked_enabled=False, trading_mode="PAPER", symbol_enabled=True)
    from tests.test_srv2_momentum_reversal_strategy import _fake_dyn_zones
    candles = _srv2_candles(now)
    with patch.object(srv2, "get_ist_now", return_value=now), \
         patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
         patch.object(srv2.cloud_db, "get_strategy_settings", return_value=s), \
         patch.object(srv2, "fetch_candles", return_value=candles), \
         patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
         patch.object(srv2, "fetch_option_expiries", return_value=[]), \
         patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23930.0), "SUCCESS")), \
         patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
         patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
         patch.object(srv2, "has_open_trade_from_source", return_value=False), \
         patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as m, \
         patch.object(srv2, "send_telegram_message", return_value=True), \
         patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
        srv2.process_symbol("fake_token", "NIFTY")
    return m.call_args_list


def test_srv2_timeout_no_position_then_approve_one(signal_db):
    assert _srv2(T0) == []
    (r,) = _rows("srv2_momentum_reversal")
    _pending(r["signal_id"], T0)
    assert _srv2(T0 + datetime.timedelta(minutes=11)) == []                      # (a) timeout ⇒ position नाही
    VS.now_ist = lambda: T0 + datetime.timedelta(minutes=50)
    assert _srv2(T0 + datetime.timedelta(minutes=50)) == []                      # नवा signal (cooldown नंतर) ⇒ HOLD
    r2 = [x for x in _rows("srv2_momentum_reversal") if x["status"] == "QUEUED"][0]
    _pending(r2["signal_id"], T0 + datetime.timedelta(minutes=50))
    _approve(r2["signal_id"], T0 + datetime.timedelta(minutes=51))
    calls = _srv2(T0 + datetime.timedelta(minutes=51))                           # (b) ✅ ⇒ एकच
    assert len(calls) == 1 and calls[0].kwargs["source"] == "srv2_momentum_reversal"
    assert _srv2(T0 + datetime.timedelta(minutes=52)) == []


# ------------------------------------------------------------------------------------------------ SR V3
NOW3 = datetime.datetime(2025, 3, 5, 11, 0)


@pytest.fixture
def srv3_env(monkeypatch):
    opened = []
    monkeypatch.setattr(SH, "refresh_levels_if_due", lambda *a, **k: None)
    monkeypatch.setattr(SH, "has_open_trade_from_source", lambda sym, src: False)
    monkeypatch.setattr(SH, "active_levels", lambda sym: [22000.0])
    monkeypatch.setattr(SH, "evaluate_touch", lambda *a, **k: ("BULLISH", "TOUCH"))
    monkeypatch.setattr(SH, "is_todays_expiry_day", lambda t, s: False)
    monkeypatch.setattr(SH, "fetch_upstox_option_chain", lambda t, s, expiry_index=0: ([{"underlying_spot_price": 22006.0}], "ok"))
    monkeypatch.setattr(SH, "select_credit_spread_itm", lambda *a, **k: {"strategy": "BULL_PUT_SPREAD"})
    monkeypatch.setattr(SH, "select_naked_option_itm", lambda *a, **k: {"strategy": "NAKED_CALL"})
    monkeypatch.setattr(SH, "open_multi_leg_trade", lambda *a, **k: opened.append(k) or (True, {"trade_id": "x"}))
    monkeypatch.setattr(SH, "format_trade_result", lambda ok, r: "OPENED")
    monkeypatch.setattr(SH, "send_telegram_message", lambda m: None)
    return opened


def _srv3(now):
    VS.now_ist = lambda: now
    today = pd.DataFrame([{"timestamp": pd.Timestamp(now) - pd.Timedelta(minutes=2), "open": 22010.0, "high": 22012.0, "low": 22004.0,
                           "close": 22008.0},
                          {"timestamp": pd.Timestamp(now) - pd.Timedelta(minutes=1), "open": 22008.0, "high": 22009.0, "low": 21999.5,
                           "close": 22006.0}])
    s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
    s.update({"srv3_shadow_enabled": True, "symbol_enabled": True, "naked_enabled": False})
    return SH.run_shadow("t", "NIFTY", now=now, settings=s, fetch=lambda *a, **k: today)


def test_srv3_timeout_no_position_then_approve_one(srv3_env):
    _srv3(NOW3)
    (r,) = _rows("srv3_instant")
    assert not srv3_env
    _pending(r["signal_id"], NOW3)
    _srv3(NOW3 + datetime.timedelta(minutes=11))                                 # (a) timeout
    assert not srv3_env
    later = NOW3 + datetime.timedelta(minutes=45)
    _srv3(later)                                                                 # नवा signal ⇒ HOLD
    r2 = [x for x in _rows("srv3_instant") if x["status"] == "QUEUED"][0]
    _pending(r2["signal_id"], later)
    _approve(r2["signal_id"], later + datetime.timedelta(minutes=1))
    _srv3(later + datetime.timedelta(minutes=1))                                 # (b) ✅ ⇒ एकच
    assert len(srv3_env) == 1 and srv3_env[0]["source"] == SH.SOURCE and srv3_env[0]["trading_mode"] == "PAPER"
    _srv3(later + datetime.timedelta(minutes=2))
    assert len(srv3_env) == 1


def test_paper_pause_blocks_approved_entry(srv3_env):
    _srv3(NOW3)
    (r,) = _rows("srv3_instant")
    _pending(r["signal_id"], NOW3)
    _approve(r["signal_id"], NOW3 + datetime.timedelta(minutes=1))
    PP.set_pause(True, "telegram:1", "test")
    _srv3(NOW3 + datetime.timedelta(minutes=1))
    assert not srv3_env                                                          # ✅ असलं तरी PAPER pause ⇒ entry नाही
    PP.set_pause(False, "telegram:1")


# ------------------------------------------------------------------------------------------------ behaviour: exits / watcher
def test_exit_runs_under_pause_killswitch_paper_pause_and_vision_error(temp_db, monkeypatch):
    seed_trade(temp_db, "TX", net_credit=30, sl_level=-1125, target_level=1125, source="manual_paper")
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 60.0, "PE24300": 5.0})
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
    monkeypatch.setattr(cloud_db, "get_trading_pause_settings", lambda: {"paused": True, "reason": "dashboard"})
    monkeypatch.setattr(trading_engine, "check_kill_switch", lambda *a, **k: (False, "KILL"))
    import vision.gate as VG
    monkeypatch.setattr(VG, "entry_gate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("vision down")))
    PP.set_pause(True, "telegram:1", "test")
    FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
    monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
    closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
    assert [c["reason"] for c in closed] == ["SL"]                               # exit अडत नाही
    PP.set_pause(False, "telegram:1")


@pytest.fixture
def monitor_env(monkeypatch):
    order = []
    monkeypatch.setattr(trade_monitor, "load_settings", lambda: {"product_type": "D"})
    monkeypatch.setattr(trade_monitor.database, "get_open_trade_modes_by_symbol", lambda syms: {"NIFTY": {"PAPER"}})
    monkeypatch.setattr(trade_monitor, "compute_atr_points", lambda *a: 0.0)
    monkeypatch.setattr(trade_monitor, "manage_open_trades", lambda *a, **k: order.append("exit") or [])
    monkeypatch.setattr(trade_monitor, "write_heartbeat", lambda *a: None)
    monkeypatch.setattr(PW, "run_locked", lambda tok, **k: order.append("watch"))
    return order


def test_watcher_runs_after_exits_in_cron_cycle_and_failure_is_isolated(monitor_env, monkeypatch):
    trade_monitor.run_monitor_cycle("tok", "D")
    assert monitor_env == ["exit", "watch"]
    monkeypatch.setattr(PW, "run_locked", lambda tok, **k: (_ for _ in ()).throw(RuntimeError("watch boom")))
    out = trade_monitor.run_monitor_cycle("tok", "D")                            # watcher चूक ⇒ cycle चा निकाल तसाच
    assert isinstance(out, str) and monitor_env[-1] == "exit"


def test_stream_cycle_never_runs_watcher_or_network(monitor_env, monkeypatch):
    import upstox_api
    monkeypatch.setattr(upstox_api, "fetch_ltp_map", lambda *a, **k: pytest.fail("stream cycle मध्ये watcher network नको"))
    for _ in range(5):                                                           # position_stream_monitor प्रमाणेच (heartbeat=False)
        trade_monitor.run_monitor_cycle("tok", "D", live_prices={"K": 1.0}, live_price_age={"K": 0.1}, heartbeat=False)
    assert monitor_env == ["exit"] * 5


def test_watcher_throttle(tmp_path):
    cfg = {"watch_min_interval_sec": 15}
    p = str(tmp_path / "last.json")
    assert PW._due(cfg, p, now=1000.0) and not PW._due(cfg, p, now=1010.0) and PW._due(cfg, p, now=1016.0)


def test_cron_cycle_runs_watcher_even_when_stream_holds_exit_lock(monitor_env):
    from process_lock import ProcessLock
    with ProcessLock("position_exit_monitor"):                                   # stream monitor lock धरून
        out = trade_monitor.run_monitor_cycle("tok", "D")
    assert "वगळलं" in out and monitor_env == ["watch"]                           # exit नाही, पण watcher (स्वतःचा lock) चालला


def test_live_gate_enters_and_writes_no_would_have():
    import vision.gate as VG
    g = VG.entry_gate("dynamic_sr_instant", "NIFTY", "LIVE", "BULLISH", 25000.0, "SUPPORT", "5M", T0, 25010.0, 2, 1)
    assert g.action == "ENTER" and g.lots == 2 and not PJ.would_have_rows()


def test_entry_cutoff_unquoted_yaml_and_bad_value(tmp_path):
    from paper import config as PC
    p = tmp_path / "c.yaml"
    p.write_text("paper:\n  entry_cutoff: 14:45\n", encoding="utf-8")         # YAML ⇒ 885 (sexagesimal)
    assert PC.load(str(p))["entry_cutoff"] == "14:45"
    p.write_text("paper:\n  entry_cutoff: soon\n", encoding="utf-8")
    assert PC.load(str(p))["entry_cutoff"] == PC.DEFAULTS["entry_cutoff"]


def test_pause_file_not_object_is_paused(tmp_path):
    p = tmp_path / "pp.json"
    p.write_text("null", encoding="utf-8")
    assert PP.get(str(p))["paused"] is True
