"""tests/test_mcx_phase1_filters.py -- MCX टप्पा 1: SL cooldown, same-level/direction block, supertrend_filter_mode, cascade (network/DB-मुक्त)."""
import datetime
import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest

import cloud_db
import database
import mcx_futures_trader as mft
from tests.test_mcx_futures_trader import _DEFAULT_SETTINGS, _fake_candles_df, _fake_resolved, _fake_zones


@pytest.fixture(autouse=True)
def _no_entry_cutoff(monkeypatch, tmp_path):
    monkeypatch.setattr(mft, "MCX_NO_NEW_ENTRY_AFTER", (24, 0))
    monkeypatch.setattr(mft, "CONTRACT_STATE", str(tmp_path / "mcx_contract_state.json"))     # repo च्या data/ मध्ये state नको


def _run(prior=(), bullish=True, directions=("BULLISH", "BULLISH"), cascade=None, **kw):
    settings = {**_DEFAULT_SETTINGS, "symbol_enabled": True, "entry_rsi_gate_enabled": False, **kw}
    if bullish:
        candles_df, zones = _fake_candles_df(last_close=6500.0), _fake_zones(support_level=6500.0)
    else:
        candles_df, zones = _fake_candles_df(closes=[6300.0] * 19 + [6400.0]), _fake_zones(support_level=6402.0)
    with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
         patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
         patch.object(mft.cloud_db, "get_market_zones", return_value=zones), \
         patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
         patch.object(mft, "fetch_mcx_trend_filter_directions", return_value=directions) as dirs, \
         patch.object(mft, "fetch_completed_30m_bars", return_value=None) as bars, \
         patch.object(mft.MF, "cascade_block", return_value=cascade or (False, None, {})) as casc, \
         patch.object(mft, "get_closed_trades_on_date", return_value=list(prior)) as closed, \
         patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
         patch.object(mft, "has_open_trade_from_source", return_value=False), \
         patch.object(mft, "open_multi_leg_trade", return_value=(True, {"trade_id": "T1"})) as trade, \
         patch.object(mft, "send_telegram_message", return_value=True), \
         patch.object(mft.cloud_db, "save_mcx_last_check", return_value=True), \
         patch.object(mft.cloud_db, "save_signal_log", return_value=True) as log:
        mft.process_symbol("tok", "CRUDEOIL")
    logs = [c.args[0] for c in log.call_args_list]
    return trade, logs, {"dirs": dirs, "bars": bars, "cascade": casc, "closed": closed}


def _closed(minutes_ago, pnl=-20000.0, reason="SL", level=6500.0, direction="BULLISH"):
    now = mft.get_ist_now()
    t = max(now - datetime.timedelta(minutes=minutes_ago), now.replace(hour=0, minute=0, second=0, microsecond=0))
    return {"exit_time": t.strftime("%Y-%m-%d %H:%M:%S"), "exit_reason": reason, "realized_pnl": pnl, "entry_level_price": level,
            "direction": direction}


def _statuses(logs):
    return [e["trade_status"] for e in logs]


def test_defaults():
    d = cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]
    assert d["sl_cooldown_minutes"] == 60 and d["sl_level_direction_block_enabled"] is True
    assert d["supertrend_filter_mode"] == "htf_against" and d["cascade_filter_enabled"] is False     # वापरकर्त्याचा निर्णय: सर्व MCX
    for st in ("SKIPPED_SL_COOLDOWN", "SKIPPED_SL_LEVEL_SAME_DIRECTION", "SKIPPED_CASCADE_NO_CHOCH", "SKIPPED_MCX_TREND_FILTER"):
        assert cloud_db._is_no_action_trade_status(st)                   # max-hits मध्ये मोजले जात नाहीत


def test_sl_cooldown_blocks_after_sl_loss():
    trade, logs, _ = _run([_closed(20, level=7000.0)])
    assert not trade.called and "SKIPPED_SL_COOLDOWN" in _statuses(logs)
    reason = next(e["reason"] for e in logs if e["trade_status"] == "SKIPPED_SL_COOLDOWN")
    assert "cooldown" in reason and "60" in reason


def test_cooldown_ignores_profit_exit_and_can_be_disabled():
    trade, _, _ = _run([_closed(20, pnl=15000.0, reason="TRAILING_SL", level=7000.0)])
    assert trade.called                                                  # फायद्यातला trailing SL ⇒ cooldown नाही
    trade, logs, _ = _run([_closed(20, level=7000.0)], sl_cooldown_minutes=0)
    assert trade.called and "SKIPPED_SL_COOLDOWN" not in _statuses(logs)


def test_same_level_same_direction_blocked_for_the_day():
    trade, logs, _ = _run([_closed(0, level=6500.0)], sl_cooldown_minutes=0)
    assert not trade.called and "SKIPPED_SL_LEVEL_SAME_DIRECTION" in _statuses(logs)
    trade, _, _ = _run([_closed(0, level=6500.0, direction="BEARISH")], sl_cooldown_minutes=0)
    assert trade.called                                                  # दुसरी दिशा ⇒ चालेल
    trade, _, _ = _run([_closed(0, level=6500.0)], sl_cooldown_minutes=0, sl_level_direction_block_enabled=False)
    assert trade.called


def test_no_db_read_when_both_disabled():
    trade, _, m = _run([], sl_cooldown_minutes=0, sl_level_direction_block_enabled=False)
    assert trade.called and not m["closed"].called


def test_supertrend_mode_htf_against():
    trade, logs, _ = _run(directions=("BULLISH", "BEARISH"), supertrend_filter_mode="htf_against")
    assert not trade.called and "SKIPPED_MCX_TREND_FILTER" in _statuses(logs)
    assert "4H" in next(e["reason"] for e in logs if e["trade_status"] == "SKIPPED_MCX_TREND_FILTER")
    trade, _, _ = _run(directions=("BULLISH", "BEARISH"), supertrend_filter_mode="both_against")
    assert trade.called                                                  # जुना नियम: एकच विरुद्ध ⇒ चालेल
    trade, _, m = _run(directions=("BEARISH", "BEARISH"))
    assert trade.called and not m["dirs"].called                         # tests चा _DEFAULT_SETTINGS = off
    raw = {**cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"], "entry_min_hold_gate_enabled": False}
    trade, logs, m = _run(directions=("BULLISH", "BEARISH"), **raw)       # खरा डीफॉल्ट: 4H BEARISH ⇒ LONG नाही
    assert not trade.called and m["dirs"].called and "SKIPPED_MCX_TREND_FILTER" in _statuses(logs)


def test_effective_supertrend_mode_backward_compat():
    assert mft.effective_supertrend_mode({}) == "off"
    assert mft.effective_supertrend_mode({"entry_supertrend_filter_enabled": True}) == "both_against"
    assert mft.effective_supertrend_mode({"entry_supertrend_filter_enabled": True, "supertrend_filter_mode": "htf_against"}) == "htf_against"
    assert mft.effective_supertrend_mode({"supertrend_filter_mode": "weird"}) == "off"


def test_cascade_filter_off_by_default_and_blocks_when_on():
    trade, _, m = _run()
    assert trade.called and not m["bars"].called and not m["cascade"].called
    trade, logs, m = _run(cascade=(True, "Support 6,600.00 30M close ने तुटला — CHoCH नाही ⇒ LONG थांबवला", {}), cascade_filter_enabled=True)
    assert not trade.called and "SKIPPED_CASCADE_NO_CHOCH" in _statuses(logs) and m["bars"].call_count == 1
    trade, _, _ = _run(cascade=(False, None, {"cascade": True, "choch": True}), cascade_filter_enabled=True)
    assert trade.called


def test_fetch_completed_30m_bars_drops_running_bar():
    t = pd.date_range("2026-10-01 09:00", periods=6, freq="30min")
    df = pd.DataFrame({"timestamp": t, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    with patch.object(mft, "fetch_mcx_candles", return_value=df):
        out = mft.fetch_completed_30m_bars("tok", "K", datetime.datetime(2026, 10, 1, 11, 10))
    assert out["timestamp"].iloc[-1] == pd.Timestamp("2026-10-01 10:30")
    with patch.object(mft, "fetch_mcx_candles", side_effect=RuntimeError("x")):
        assert mft.fetch_completed_30m_bars("tok", "K", datetime.datetime(2026, 10, 1, 11, 10)) is None


def test_get_closed_trades_on_date(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE live_trades (symbol TEXT, source TEXT, status TEXT, exit_time TEXT, exit_reason TEXT, realized_pnl REAL, "
                 "entry_level_price REAL, strategy TEXT)")
    conn.executemany("INSERT INTO live_trades VALUES (?,?,?,?,?,?,?,?)", [
        ("GOLD", "mcx_futures", "CLOSED", "2026-10-01 10:00:00", "SL", -100.0, 150000.0, "MCX_FUTURES_LONG"),
        ("GOLD", "mcx_futures", "CLOSED", "2026-09-30 10:00:00", "SL", -100.0, 150000.0, "MCX_FUTURES_LONG"),
        ("GOLD", "mcx_futures_srv3_shadow", "CLOSED", "2026-10-01 10:00:00", "SL", -100.0, 150000.0, "MCX_FUTURES_LONG"),
        ("GOLD", "mcx_futures", "OPEN", None, None, None, 150000.0, "MCX_FUTURES_SHORT"),
        ("GOLD", "mcx_futures", "CLOSED", "2026-10-01 12:00:00", "TARGET", 300.0, 151000.0, "MCX_FUTURES_SHORT")])
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", path)
    rows = database.get_closed_trades_on_date("GOLD", "mcx_futures", "2026-10-01")
    assert [(r["exit_reason"], r["direction"]) for r in rows] == [("SL", "BULLISH"), ("TARGET", "BEARISH")]
