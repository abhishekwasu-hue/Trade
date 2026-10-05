"""tests/test_mcx_candle_confirm.py -- MCX bot: LOGIC-BASED candle confirmation gate (price_action/candles.py) + structure SL + chase +
50/50 entry (भाग 2 composite च्या 50% pullback वर, दोन्हींचा SL एकच). network/DB-free."""
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import mcx_filters as MF
import mcx_futures_trader as mft
from tests.test_mcx_futures_trader import _DEFAULT_SETTINGS, _fake_candles_df, _fake_resolved
from tests.test_price_action_candles import _df

LEVEL = 100.0
SWEEP1 = [(100.2, 100.8, 97.5, 100.6)]          # N=1: खोल wick, close level जवळ ⇒ score ≈ 74, SL ≈ 97.45
WEAK = [(100.3, 101.5, 99.9, 101.4)]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(mft, "get_closed_trades_on_date", lambda *a, **k: [])
    monkeypatch.setattr(mft, "MCX_NO_NEW_ENTRY_AFTER", (24, 0))
    monkeypatch.setattr(mft, "check_contract_roll", lambda *a, **k: (True, None))


def test_candle_tf_for_chart_mode():
    assert MF.candle_tf_for("chart", "30M", {}) == "30M" and MF.candle_tf_for("chart", "60M", {}) == "60M"
    assert MF.candle_tf_for("chart", "SRV3", {"timeframe_choice": "60M"}) == "60M"        # SR V3 ⇒ bot चा TF
    assert MF.candle_tf_for("chart", "SRV3", {"timeframe_choice": "ALL"}) == "30M"
    assert MF.candle_tf_for("60M", "30M", {}) == "60M" and MF.candle_tf_for("30M", "60M", {}) == "30M"


def test_split_and_pullback_helpers():
    assert MF.split_lots(1) is None and MF.split_lots(2) == (1, 1) and MF.split_lots(3) == (2, 1)
    assert MF.pullback_reached("BULLISH", 99.1, 99.15) and not MF.pullback_reached("BULLISH", 99.2, 99.15)


def _zones(level=LEVEL, suffix="30M"):
    return pd.DataFrame([{"symbol": "CRUDEOIL", "zone_type": f"DYNAMIC_SR_SUPPORT_{suffix}", "zone_low": level, "zone_high": level,
                          "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"}])


def _settings(**kw):
    return {**_DEFAULT_SETTINGS, "symbol_enabled": True, "entry_rsi_gate_enabled": False, "candle_confirm_enabled": True, **kw}


def _run(settings, frames, price=100.6, open_pos=False, suffix="30M"):
    trade = MagicMock(return_value=(True, {"trade_id": "T1"}))
    logs = MagicMock(return_value=True)
    with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
         patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
         patch.object(mft.cloud_db, "get_market_zones", return_value=_zones(suffix=suffix)), \
         patch.object(mft, "fetch_mcx_candles", return_value=_fake_candles_df(closes=[104.0] * 30 + [price])), \
         patch.object(mft, "fetch_candle_confirm_frames", return_value=frames), \
         patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
         patch.object(mft, "has_open_trade_from_source", return_value=open_pos), \
         patch.object(mft.cloud_db, "save_signal_log", logs), \
         patch.object(mft.cloud_db, "save_mcx_last_check", return_value=True), \
         patch.object(mft, "send_telegram_message"), \
         patch.object(mft, "open_multi_leg_trade", trade):
        return mft.process_symbol("tok", "CRUDEOIL"), trade, logs


def _state():
    try:
        return json.load(open(mft.CANDLE_STATE))
    except OSError:
        return {}


def _statuses(logs):
    return [c.args[0]["trade_status"] for c in logs.call_args_list]


def _reasons(logs):
    return [c.args[0]["reason"] for c in logs.call_args_list]


def test_rejection_passes_half_now_with_structure_sl_and_queues_pullback():
    _, trade, logs = _run(_settings(lots=2), {"30M": _df(SWEEP1)})
    assert trade.call_count == 1
    kw, sr = trade.call_args.kwargs, trade.call_args.args[2]
    sl = 97.5 * 0.9995
    assert kw["lots"] == 1 and kw["entry_reason_tag"] == "CANDLE_CONFIRM"
    assert sr["max_loss"] == pytest.approx(100.6 - sl, abs=1e-3)                # structure SL, settings SL नव्हे
    p = _state()["pending"]["CRUDEOIL|mcx_futures"]
    assert p["lots"] == 1 and p["sl"] == pytest.approx(sl, abs=1e-3) and p["pullback"] == pytest.approx((100.8 + 97.5) / 2) and p["tf"] == "30M"
    reason = [r for r, st in zip(_reasons(logs), _statuses(logs)) if st and st.startswith("OPENED")][-1]
    assert "N=1 score=" in reason and "wick=" in reason and "SL 97.45" in reason and "30M" in reason


def test_no_rejection_logs_specific_skip_reason():
    _, trade, logs = _run(_settings(lots=2), {"30M": _df(WEAK)}, price=100.05)
    assert not trade.called and "SKIPPED_REJECTION_WEAK_CANDLE" in _statuses(logs)
    assert any("N=" in r and "30M" in r for r in _reasons(logs))


def test_chase_rule_one_lot_skips_two_lots_waits_for_pullback():
    _, t1, l1 = _run(_settings(lots=1), {"30M": _df(SWEEP1)}, price=103.0)
    assert not t1.called and "SKIPPED_CANDLE_CHASE" in _statuses(l1)
    mft._candle_state_save({})
    _, t2, l2 = _run(_settings(lots=2), {"30M": _df(SWEEP1)}, price=103.0)
    assert not t2.called and "PENDING_PULLBACK_50" in _statuses(l2) and _state()["pending"]["CRUDEOIL|mcx_futures"]["part1_opened"] is False


def test_sl_wider_than_settings_is_skipped():
    _, trade, logs = _run(_settings(lots=1, sl_points=2), {"30M": _df(SWEEP1)})
    assert not trade.called and "SKIPPED_CANDLE_SL_TOO_WIDE" in _statuses(logs)


def test_same_rejection_never_traded_twice_even_as_longer_window():
    _run(_settings(lots=1), {"30M": _df(SWEEP1)}, price=100.05)
    more = _df(SWEEP1 + [(100.6, 101.4, 100.4, 101.2)])                         # पुढच्या candle सह N=2 window — तोच rejection
    _, trade2, logs2 = _run(_settings(lots=1), {"30M": more}, price=100.05)
    assert not trade2.called and "SKIPPED_CANDLE_ALREADY_TRADED" in _statuses(logs2)


def test_chart_mode_uses_level_timeframe_and_override():
    frames = {"30M": _df(WEAK), "60M": _df(SWEEP1)}
    _, t60, _ = _run(_settings(lots=1, timeframe_choice="60M"), frames, suffix="60M")
    assert t60.call_count == 1                                                   # 60M level ⇒ 60M candles
    mft._candle_state_save({})
    _, t30, l30 = _run(_settings(lots=1, timeframe_choice="60M", candle_tf_mode="30M"), frames, suffix="60M", price=100.05)
    assert not t30.called and "SKIPPED_REJECTION_WEAK_CANDLE" in _statuses(l30)


def test_min_hold_gate_does_not_block_confirmed_entry():
    with patch.object(mft, "fetch_mcx_todays_1m_candles", return_value=[{"close": 101.0}]), \
         patch.object(mft, "count_consecutive_touch_minutes", return_value=0):
        _, trade, _ = _run(_settings(lots=1, entry_min_hold_gate_enabled=True), {"30M": _df(SWEEP1)})
    assert trade.call_count == 1


def test_gate_off_is_unchanged_behaviour():
    _, trade, _ = _run(_settings(lots=2, candle_confirm_enabled=False), {}, price=100.05)
    assert trade.call_count == 1 and trade.call_args.kwargs["lots"] == 2 and trade.call_args.kwargs["entry_reason_tag"] is None
    assert trade.call_args.args[2]["max_loss"] == float(_settings()["sl_points"])


def test_fetch_frames_60m_only_completed_hours(monkeypatch):
    rows = [{"timestamp": pd.Timestamp(f"2026-10-05 {h}"), "open": 100, "high": 101, "low": 99, "close": 100}
            for h in ("09:00", "09:30", "10:00", "10:30", "11:00")]
    monkeypatch.setattr(mft, "fetch_completed_30m_bars", lambda *a, **k: pd.DataFrame(rows))
    frames = mft.fetch_candle_confirm_frames("t", "k", pd.Timestamp("2026-10-05 11:35"), "ANY")
    assert len(frames["30M"]) == 5 and list(frames["60M"]["timestamp"].dt.strftime("%H:%M")) == ["09:00", "10:00"]


# --- भाग 2 (pullback) --------------------------------------------------------------------------------------------------------------
def _pending(**kw):
    p = {"direction": "BULLISH", "level": LEVEL, "lots": 1, "pullback": 99.15, "sl": 97.45, "label": "≈ Hammer", "tf": "30M",
         "candle_ts": "2026-10-05T14:30:00", "expires": "2026-10-05T16:00:00", "part1_opened": True, "timeframe_suffix": "30M", **kw}
    mft._candle_state_save({"pending": {"CRUDEOIL|mcx_futures": p}})


def _pend(now="2026-10-05 15:10", price=99.1, last_done_close=100.4, part1_open=True):
    trade = MagicMock(return_value=(True, {"trade_id": "T2"}))
    row = lambda ts, c: {"timestamp": pd.Timestamp(ts), "open": 100.5, "high": 101.0, "low": 99.0, "close": c}
    done = pd.DataFrame([row("2026-10-05 14:30", 100.6), row("2026-10-05 15:00", last_done_close)])
    with patch.object(mft, "fetch_mcx_candles", return_value=pd.DataFrame([row("2026-10-05 15:00", price)])), \
         patch.object(mft, "fetch_completed_30m_bars", return_value=done), \
         patch.object(mft, "has_open_trade_from_source", return_value=part1_open), \
         patch.object(mft, "send_telegram_message"), patch.object(mft, "open_multi_leg_trade", trade):
        res = mft.process_candle_pending("tok", "CRUDEOIL", "mcx_futures", _settings(lots=2), _fake_resolved()[1],
                                         pd.Timestamp(now).to_pydatetime())
    return res, trade


def test_pullback_fills_with_same_sl_price():
    _pending()
    (still, msg), trade = _pend(price=99.1)
    assert not still and trade.call_count == 1
    kw, sr = trade.call_args.kwargs, trade.call_args.args[2]
    assert kw["lots"] == 1 and kw["entry_reason_tag"] == "CANDLE_PULLBACK_50"
    assert sr["legs"][0]["ltp"] == 99.1 and sr["max_loss"] == pytest.approx(99.1 - 97.45)      # एकच SL भाव
    assert not _state().get("pending")


def test_pullback_waits_then_cancels():
    _pending()
    (still, msg), trade = _pend(price=99.6)
    assert still and not trade.called and "प्रतीक्षेत" in msg
    (still, msg), _ = _pend(now="2026-10-05 16:00", price=99.6)
    assert not still and "मुदत संपली" in msg and not _state().get("pending")
    _pending()
    (still, msg), _ = _pend(part1_open=False)
    assert not still and "भाग 1" in msg
    _pending()
    (still, msg), trade = _pend(price=97.4)                                        # भाव SL च्या पलीकडे
    assert not still and "SL" in msg and not trade.called
    _pending()
    (still, msg), trade = _pend(price=99.1, last_done_close=99.5)                  # 30M close ने level तोडला
    assert not still and "तोडला" in msg and not trade.called


def test_pending_blocks_new_signals_for_symbol():
    _pending(expires="2099-01-01T00:00:00", part1_opened=False)
    result, trade, _ = _run(_settings(lots=2), {"30M": _df(SWEEP1)}, price=100.6)
    assert "भाग 2 प्रतीक्षेत" in result and not trade.called


def test_old_pattern_gate_pending_is_dropped_safely():
    mft._candle_state_save({"pending": {"CRUDEOIL|mcx_futures": {"direction": "BULLISH", "level": LEVEL, "lots": 1, "pullback": 99.0,
                                                                  "pattern": "HAMMER", "tf": "30M", "expires": "2099-01-01T00:00:00"}}})
    (still, msg), trade = _pend()
    assert not still and "जुन्या" in msg and not trade.called and not _state().get("pending")
