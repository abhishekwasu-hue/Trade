"""tests/test_mcx_candle_confirm.py -- MCX Candlestick Confirmation gate (Hammer/Shooting Star/Engulfing, 30M/60M) + 50/50 entry
(50% लगेच, 50% confirmation candle च्या 50% pullback वर). network/DB-free."""
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import mcx_filters as MF
import mcx_futures_trader as mft
from tests.test_mcx_futures_trader import _DEFAULT_SETTINGS, _fake_candles_df, _fake_resolved

LEVEL = 6495.0


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(mft, "get_closed_trades_on_date", lambda *a, **k: [])
    monkeypatch.setattr(mft, "MCX_NO_NEW_ENTRY_AFTER", (24, 0))
    monkeypatch.setattr(mft, "CONTRACT_STATE", "/nonexistent/mcx_contract_state.json")
    monkeypatch.setattr(mft, "check_contract_roll", lambda *a, **k: (True, None))


def _c(ts, o, h, l, c):
    return {"timestamp": pd.Timestamp(ts), "open": o, "high": h, "low": l, "close": c}


def _frame(*rows):
    return pd.DataFrame(list(rows))


# --- शुद्ध नियम ---------------------------------------------------------------------------------------------------------------------
def test_candle_patterns():
    red = _c("2026-10-05 10:00", 110, 111, 99, 100)
    green = _c("2026-10-05 10:00", 100, 111, 99, 110)
    assert MF.candle_pattern(red, _c("2026-10-05 10:30", 99, 113, 98, 112)) == "BULLISH_ENGULFING"
    assert MF.candle_pattern(green, _c("2026-10-05 10:30", 111, 112, 97, 98)) == "BEARISH_ENGULFING"
    assert MF.candle_pattern(green, _c("2026-10-05 10:30", 100, 102.5, 88, 102)) == "HAMMER"          # wick 12 ≥ 2×2, वर 0.5 ≤ 1
    assert MF.candle_pattern(red, _c("2026-10-05 10:30", 102, 115, 99.5, 100)) == "SHOOTING_STAR"
    assert MF.candle_pattern(red, _c("2026-10-05 10:30", 100, 105, 95, 104)) is None                   # साधी candle
    assert MF.candle_pattern(red, _c("2026-10-05 10:30", 100, 100, 100, 100)) is None                  # range 0


def test_split_lots_and_pullback_rules():
    assert MF.split_lots(1) is None and MF.split_lots(2) == (1, 1) and MF.split_lots(3) == (2, 1) and MF.split_lots(4) == (2, 2)
    assert MF.pullback_reached("BULLISH", 6492.0, 6492.5) and not MF.pullback_reached("BULLISH", 6493.0, 6492.5)
    assert MF.pullback_reached("BEARISH", 6510.0, 6508.0) and not MF.pullback_reached("BEARISH", 6507.0, 6508.0)


def _hammer_frame(level=LEVEL, high=6500.0, ts_end="2026-10-05 14:30"):
    """आधीची लाल candle + level ला लागून Hammer (low 6485, close 6499) — शेवटची पूर्ण candle."""
    return _frame(_c("2026-10-05 13:30", 6520, 6522, 6505, 6508), _c("2026-10-05 14:00", 6508, 6510, 6498, 6500),
                  _c(ts_end, 6497, high, 6485, 6499))


def test_find_confirmation_needs_level_contact_and_freshness():
    conf = MF.find_candle_confirmation({"30M": _hammer_frame()}, "BULLISH", LEVEL)
    assert conf["pattern"] == "HAMMER" and conf["tf"] == "30M" and conf["pullback"] == pytest.approx(6492.5)
    assert MF.find_candle_confirmation({"30M": _hammer_frame()}, "BULLISH", 6450.0) is None          # level ला लागली नाही
    assert MF.find_candle_confirmation({"30M": _hammer_frame()}, "BEARISH", LEVEL) is None            # दिशा जुळत नाही
    old = pd.concat([_hammer_frame(), _frame(_c("2026-10-05 15:00", 6499, 6503, 6497, 6502),
                                             _c("2026-10-05 15:30", 6502, 6506, 6500, 6504))], ignore_index=True)
    assert MF.find_candle_confirmation({"30M": old}, "BULLISH", LEVEL) is None                       # 3 candles जुना
    assert MF.find_candle_confirmation({"30M": old.iloc[:-1]}, "BULLISH", LEVEL) is not None         # 2 पैकी एक
    assert MF.find_candle_confirmation({"30M": _hammer_frame()}, "BULLISH", LEVEL, patterns=("ENGULFING",)) is None


def test_fetch_frames_60m_only_completed_hours(monkeypatch):
    rows = [_c(f"2026-10-05 {h}", 100, 101, 99, 100) for h in ("09:00", "09:30", "10:00", "10:30", "11:00")]
    monkeypatch.setattr(mft, "fetch_completed_30m_bars", lambda *a, **k: _frame(*rows))
    frames = mft.fetch_candle_confirm_frames("t", "k", pd.Timestamp("2026-10-05 11:35"), "ANY")
    assert len(frames["30M"]) == 5
    assert list(frames["60M"]["timestamp"].dt.strftime("%H:%M")) == ["09:00", "10:00"]   # 11:00 चा तास अजून पूर्ण नाही
    assert set(mft.fetch_candle_confirm_frames("t", "k", pd.Timestamp("2026-10-05 11:35"), "60M")) == {"60M"}


# --- bot मध्ये --------------------------------------------------------------------------------------------------------------------------
def _zones(level=LEVEL):
    return pd.DataFrame([{"symbol": "CRUDEOIL", "zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": level, "zone_high": level,
                          "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"}])


def _settings(**kw):
    return {**_DEFAULT_SETTINGS, "symbol_enabled": True, "entry_rsi_gate_enabled": False, "candle_confirm_enabled": True,
            "candle_confirm_tf": "30M", **kw}


def _run(settings, frames, price=6500.0, open_pos=False):
    trade = MagicMock(return_value=(True, {"trade_id": "T1"}))
    logs = MagicMock(return_value=True)
    with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
         patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
         patch.object(mft.cloud_db, "get_market_zones", return_value=_zones()), \
         patch.object(mft, "fetch_mcx_candles", return_value=_fake_candles_df(last_close=price)), \
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


def test_no_pattern_skips_with_reason():
    result, trade, logs = _run(_settings(lots=2), {"30M": _frame(_c("2026-10-05 14:00", 6500, 6505, 6495, 6503),
                                                                 _c("2026-10-05 14:30", 6503, 6506, 6498, 6501))})
    assert not trade.called and "SKIPPED_CANDLE_CONFIRMATION" in _statuses(logs)


def test_lots_two_takes_half_now_and_queues_pullback():
    result, trade, logs = _run(_settings(lots=2), {"30M": _hammer_frame()})
    assert trade.call_count == 1
    kw = trade.call_args.kwargs
    assert kw["lots"] == 1 and kw["entry_reason_tag"] == "CANDLE_CONFIRM" and kw["entry_level_price"] == LEVEL
    p = _state()["pending"]["CRUDEOIL|mcx_futures"]
    assert p["lots"] == 1 and p["pullback"] == pytest.approx(6492.5) and p["direction"] == "BULLISH" and p["part1_opened"]
    assert p["expires"].startswith("2026-10-05T16:00")                       # candle 14:30–15:00 + 2 × 30M
    reason = [c.args[0]["reason"] for c in logs.call_args_list if c.args[0]["trade_status"] not in (None,)][-1]
    assert "HAMMER 30M" in reason and "भाग 2: 1 lot @ 6492.50" in reason


def test_lots_one_full_quantity_now_no_pending():
    _, trade, _ = _run(_settings(lots=1), {"30M": _hammer_frame()})
    assert trade.call_args.kwargs["lots"] == 1 and not _state().get("pending")


def test_price_outside_candle_waits_for_pullback_or_skips_for_one_lot():
    frames = {"30M": _hammer_frame(high=6499.5)}                            # भाव 6500 > high ⇒ भाग 1 नाही
    _, trade, logs = _run(_settings(lots=2), frames)
    assert not trade.called and "PENDING_PULLBACK_50" in _statuses(logs)
    assert _state()["pending"]["CRUDEOIL|mcx_futures"]["part1_opened"] is False
    mft._candle_state_save({})
    _, trade1, logs1 = _run(_settings(lots=1), frames)
    assert not trade1.called and "SKIPPED_CANDLE_PRICE_MOVED_AWAY" in _statuses(logs1)


def test_same_pattern_never_traded_twice():
    _run(_settings(lots=1), {"30M": _hammer_frame()})
    _, trade2, logs2 = _run(_settings(lots=1), {"30M": _hammer_frame()})
    assert not trade2.called and "SKIPPED_CANDLE_CONFIRMATION" in _statuses(logs2)


def test_gate_off_is_unchanged_behaviour():
    _, trade, _ = _run(_settings(lots=2, candle_confirm_enabled=False), {})
    assert trade.call_count == 1 and trade.call_args.kwargs["lots"] == 2 and trade.call_args.kwargs["entry_reason_tag"] is None


# --- भाग 2 (pullback) --------------------------------------------------------------------------------------------------------------
def _pending(**kw):
    p = {"direction": "BULLISH", "level": LEVEL, "lots": 1, "pullback": 6492.5, "pattern": "HAMMER", "tf": "30M",
         "candle_ts": "2026-10-05T14:30:00", "expires": "2026-10-05T16:00:00", "part1_opened": True, "timeframe_suffix": "30M", **kw}
    mft._candle_state_save({"pending": {"CRUDEOIL|mcx_futures": p}})


def _pend(now="2026-10-05 15:10", price=6492.0, last_done_close=6496.0, part1_open=True):
    trade = MagicMock(return_value=(True, {"trade_id": "T2"}))
    done = _frame(_c("2026-10-05 14:30", 6497, 6500, 6485, 6499), _c("2026-10-05 15:00", 6499, 6500, 6490, last_done_close))
    with patch.object(mft, "fetch_mcx_candles", return_value=_frame(_c("2026-10-05 15:00", 6499, 6500, 6490, price))), \
         patch.object(mft, "fetch_completed_30m_bars", return_value=done), \
         patch.object(mft, "has_open_trade_from_source", return_value=part1_open), \
         patch.object(mft, "send_telegram_message"), patch.object(mft, "open_multi_leg_trade", trade):
        res = mft.process_candle_pending("tok", "CRUDEOIL", "mcx_futures", _settings(lots=2), _fake_resolved()[1],
                                         pd.Timestamp(now).to_pydatetime())
    return res, trade


def test_pullback_fills_part_two_with_own_sl_target():
    _pending()
    (still, msg), trade = _pend(price=6492.0)
    assert not still and trade.call_count == 1
    kw = trade.call_args.kwargs
    assert kw["lots"] == 1 and kw["entry_reason_tag"] == "CANDLE_PULLBACK_50" and kw["entry_level_price"] == LEVEL
    assert trade.call_args.args[2]["legs"][0]["ltp"] == 6492.0 and trade.call_args.args[2]["max_loss"] == float(_settings()["sl_points"])
    assert not _state().get("pending")


def test_pullback_waits_then_cancels():
    _pending()
    (still, msg), trade = _pend(price=6496.0)
    assert still and not trade.called and "प्रतीक्षेत" in msg
    (still, msg), _ = _pend(now="2026-10-05 16:00", price=6496.0)
    assert not still and "मुदत संपली" in msg and not _state().get("pending")
    _pending()
    (still, msg), _ = _pend(part1_open=False)
    assert not still and "भाग 1" in msg
    _pending()
    (still, msg), trade = _pend(price=6480.0, last_done_close=6480.0)            # 30M close ने level तोडला ⇒ भरायचं नाही
    assert not still and "तोडला" in msg and not trade.called


def test_pending_blocks_new_signals_for_symbol():
    _pending(expires="2099-01-01T00:00:00", part1_opened=False)                  # खऱ्या घड्याळावर अवलंबून नको
    result, trade, _ = _run(_settings(lots=2), {"30M": _hammer_frame()}, price=6500.0)
    assert "भाग 2 प्रतीक्षेत" in result and not trade.called


def test_min_hold_gate_does_not_block_confirmed_entry():
    with patch.object(mft, "fetch_mcx_todays_1m_candles", return_value=[{"close": 6520.0}]), \
         patch.object(mft, "count_consecutive_touch_minutes", return_value=0):
        _, trade, _ = _run(_settings(lots=1, entry_min_hold_gate_enabled=True), {"30M": _hammer_frame()})
    assert trade.call_count == 1
