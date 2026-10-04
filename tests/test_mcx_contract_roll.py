"""tests/test_mcx_contract_roll.py -- MCX contract roll: ट्रेडिंग दिवसांत नियम (डीफॉल्ट 6, staggered delivery period + 1 पेक्षा कमी नाही),
roll सूचना, zones refresh, trailing reference trade च्या स्वतःच्या contract वरून."""
import datetime
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

import cloud_db
import database
import mcx_futures_trader as mft
import resolve_mcx_futures_instruments as rmfi
from tests.test_resolve_mcx_futures_instruments import _contract, _mock_search_response


def _resolve(results, today, roll_days=None, setting=None):
    settings = {} if setting is None else {"roll_trading_days_before_expiry": setting}
    with patch.object(rmfi.requests, "get", return_value=_mock_search_response(results)), \
         patch.object(rmfi, "get_ist_today", return_value=today), \
         patch.object(rmfi.cloud_db, "get_strategy_settings", return_value=settings):
        return rmfi.resolve_symbol("tok", results[0]["trading_symbol"].split(" FUT")[0], roll_days=roll_days)


GOLD = [_contract("GOLD FUT 05 OCT 26", "MCX_FO|OCT", 1, 1.0, "2026-10-05"), _contract("GOLD FUT 04 DEC 26", "MCX_FO|DEC", 1, 1.0, "2026-12-04")]
D = datetime.date


def test_trading_days_left_counts_weekdays_inclusive():
    assert rmfi.trading_days_left(D(2026, 9, 28), D(2026, 10, 5)) == 6          # सोम 28 Sep ते सोम 5 Oct
    assert rmfi.trading_days_left(D(2026, 10, 3), D(2026, 10, 5)) == 1          # शनिवार ⇒ फक्त सोमवार
    assert rmfi.trading_days_left(D(2026, 10, 6), D(2026, 10, 5)) == 0


def test_defaults_and_staggered_table():
    assert rmfi.ROLL_TRADING_DAYS_BEFORE_EXPIRY == 6
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]["roll_trading_days_before_expiry"] == 6
    assert rmfi.STAGGERED_DELIVERY_TRADING_DAYS == {"GOLD": 3, "SILVER": 3, "COPPER": 3}
    assert rmfi.effective_roll_days("GOLD", 2) == 4 and rmfi.effective_roll_days("GOLD", 6) == 6      # period+1 पेक्षा कमी नाही
    assert rmfi.effective_roll_days("CRUDEOIL", 1) == 1


@pytest.mark.parametrize("today,expected,rolled", [
    (D(2026, 9, 25), "GOLD FUT 05 OCT 26", False),      # शुक्र: 7 ट्रेडिंग दिवस बाकी
    (D(2026, 9, 28), "GOLD FUT 04 DEC 26", True),       # सोम: 6 ⇒ roll
    (D(2026, 9, 27), "GOLD FUT 04 DEC 26", True),       # रविवार: पुढचे 6 (सोम–सोम) ⇒ roll
    (D(2026, 10, 5), "GOLD FUT 04 DEC 26", True),       # expiry दिवस
])
def test_resolver_rolls_on_trading_days(today, expected, rolled):
    ok, r = _resolve(GOLD, today)
    assert ok and r["trading_symbol"] == expected and r["rolled"] is rolled
    assert r["front_trading_symbol"] == "GOLD FUT 05 OCT 26" and r["roll_trading_days_before_expiry"] == 6
    assert r["staggered_delivery_trading_days"] == 3
    assert r["front_trading_days_to_expiry"] == rmfi.trading_days_left(today, D(2026, 10, 5))


def test_roll_happens_before_staggered_period_even_with_low_setting():
    # setting 1 असलं तरी GOLD साठी किमान 4: staggered period (शेवटचे 3: 1, 2, 5 Oct) सुरू होण्याआधीच्या दिवशी (30 Sep) roll
    ok, r = _resolve(GOLD, D(2026, 9, 29), setting=1)
    assert r["trading_symbol"] == "GOLD FUT 05 OCT 26" and r["roll_trading_days_before_expiry"] == 4
    ok, r = _resolve(GOLD, D(2026, 9, 30), setting=1)
    assert r["trading_symbol"] == "GOLD FUT 04 DEC 26" and r["rolled"]


def test_setting_and_explicit_roll_days():
    ok, r = _resolve(GOLD, D(2026, 9, 24), setting=8)                              # 8 ट्रेडिंग दिवस बाकी ⇒ roll
    assert r["rolled"] and r["roll_trading_days_before_expiry"] == 8
    ok, r = _resolve(GOLD, D(2026, 9, 24), roll_days=5, setting=8)                 # explicit argument ला प्राधान्य
    assert not r["rolled"]


def test_resolver_roll_applies_to_all_commodities_and_pending_when_no_next():
    crude = [_contract("CRUDEOIL FUT 19 OCT 26", "MCX_FO|C1", 100, 1.0, "2026-10-19"), _contract("CRUDEOIL FUT 18 NOV 26", "MCX_FO|C2", 100, 1.0, "2026-11-18")]
    ok, r = _resolve(crude, D(2026, 10, 12))                                        # सोम 12 ते सोम 19 = 6
    assert r["trading_symbol"] == "CRUDEOIL FUT 18 NOV 26" and r["rolled"] and r["staggered_delivery_trading_days"] == 0
    ok, r = _resolve(crude[:1], D(2026, 10, 12))                                    # पुढचा यादीत नाही
    assert ok and r["trading_symbol"] == "CRUDEOIL FUT 19 OCT 26" and not r["rolled"] and r["roll_pending"]
    ok, r = _resolve(GOLD, D(2026, 9, 1))
    assert r["trading_symbol"] == "GOLD FUT 05 OCT 26" and not r["roll_pending"]


def _res(ts, rolled=False, front=None, pending=False):
    return {"trading_symbol": ts, "instrument_key": "K", "lot_size": 1, "expiry": "2026-12-04", "rolled": rolled, "front_trading_symbol": front or ts,
            "roll_trading_days_before_expiry": 6, "staggered_delivery_trading_days": 3, "roll_pending": pending}


def test_check_contract_roll_first_run_no_roll_is_silent(tmp_path):
    notify, refresh = MagicMock(), MagicMock(return_value=(True, "ok"))
    ok, msg = mft.check_contract_roll("t", "CRUDEOIL", _res("CRUDEOIL FUT 18 NOV 26"), notify=notify, refresh=refresh, state_path=str(tmp_path / "s.json"))
    assert ok and msg is None and not notify.called and not refresh.called


def test_check_contract_roll_notifies_once_and_refreshes_zones(tmp_path):
    state = str(tmp_path / "s.json")
    notify, refresh = MagicMock(), MagicMock(return_value=(True, "GOLD: 12 zones साठवले"))
    mft.check_contract_roll("t", "GOLD", _res("GOLD FUT 05 OCT 26"), notify=notify, refresh=refresh, state_path=state)
    ok, msg = mft.check_contract_roll("t", "GOLD", _res("GOLD FUT 04 DEC 26", rolled=True, front="GOLD FUT 05 OCT 26"),
                                      notify=notify, refresh=refresh, state_path=state)
    assert ok and notify.call_count == 1 and refresh.call_count == 1
    text = notify.call_args.args[0]
    assert "GOLD FUT 05 OCT 26 → GOLD FUT 04 DEC 26" in text and "ट्रेडिंग दिवस ≤ 6" in text and "शेवटचे 3" in text and "12 zones" in msg
    ok2, msg2 = mft.check_contract_roll("t", "GOLD", _res("GOLD FUT 04 DEC 26", rolled=True, front="GOLD FUT 05 OCT 26"),
                                        notify=notify, refresh=refresh, state_path=state)
    assert ok2 and msg2 is None and notify.call_count == 1 and refresh.call_count == 1          # पुन्हा नाही


def test_check_contract_roll_first_run_already_rolled_refreshes(tmp_path):
    notify, refresh = MagicMock(), MagicMock(return_value=(True, "ok"))
    ok, _ = mft.check_contract_roll("t", "GOLD", _res("GOLD FUT 04 DEC 26", rolled=True, front="GOLD FUT 05 OCT 26"),
                                    notify=notify, refresh=refresh, state_path=str(tmp_path / "s.json"))
    assert ok and notify.call_count == 1 and refresh.call_count == 1


def test_check_contract_roll_blocks_entries_until_zones_ready(tmp_path):
    state = str(tmp_path / "s.json")
    notify = MagicMock()
    fail = MagicMock(return_value=(False, "पुरेसा 30-मिनिट इतिहास नाही"))
    ok, msg = mft.check_contract_roll("t", "GOLD", _res("GOLD FUT 04 DEC 26", rolled=True, front="GOLD FUT 05 OCT 26"),
                                      notify=notify, refresh=fail, state_path=state)
    assert not ok and "नवीन entry नाही" in msg and notify.call_count == 1
    good = MagicMock(return_value=(True, "ok"))
    ok2, _ = mft.check_contract_roll("t", "GOLD", _res("GOLD FUT 04 DEC 26", rolled=True, front="GOLD FUT 05 OCT 26"),
                                     notify=notify, refresh=good, state_path=state)
    assert ok2 and notify.call_count == 1 and good.call_count == 1                                # सूचना पुन्हा नाही, refresh पुन्हा प्रयत्न


def test_process_symbol_stops_when_roll_zones_not_ready(monkeypatch):
    from tests.test_mcx_futures_trader import _DEFAULT_SETTINGS
    monkeypatch.setattr(mft, "check_contract_roll", lambda *a, **k: (False, "GOLD: zones अजून तयार नाहीत; नवीन entry नाही"))
    trade = MagicMock()
    with patch.object(mft.cloud_db, "get_strategy_settings", return_value={**_DEFAULT_SETTINGS, "symbol_enabled": True}), \
         patch.object(mft.mcx_resolver, "resolve_symbol", return_value=(True, _res("GOLD FUT 04 DEC 26", rolled=True))), \
         patch.object(mft.cloud_db, "save_mcx_last_check", return_value=True), \
         patch.object(mft, "open_multi_leg_trade", trade):
        out = mft.process_symbol("t", "GOLD")
    assert "नवीन entry नाही" in out and not trade.called


def test_trailing_reference_price_uses_given_instrument_and_caches_per_contract():
    mft._trailing_price_cache.clear()
    fetched = []

    def fetch(tok, key, interval="30minute", lookback_days=None):
        import pandas as pd
        fetched.append(key)
        return pd.DataFrame({"close": [150000.0 if key == "OLD" else 151000.0]})
    try:
        with patch.object(mft, "fetch_mcx_candles", side_effect=fetch), patch.object(mft.mcx_resolver, "resolve_symbol") as res:
            assert mft._get_trailing_reference_price("t", "GOLD", instrument_key="OLD", now_fn=lambda: 1.0) == 150000.0
            assert mft._get_trailing_reference_price("t", "GOLD", instrument_key="NEW", now_fn=lambda: 1.0) == 151000.0
            assert fetched == ["OLD", "NEW"] and not res.called
    finally:
        mft._trailing_price_cache.clear()


def test_get_open_trade_contracts(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE live_trades (symbol TEXT, source TEXT, status TEXT, legs_json TEXT)")
    leg = lambda k, e: json.dumps([{"instrument_key": k, "expiry": e}])          # noqa: E731
    conn.executemany("INSERT INTO live_trades VALUES (?,?,?,?)", [
        ("GOLD", "mcx_futures_srv3_shadow", "OPEN", leg("DEC", "2026-12-04")),
        ("GOLD", "mcx_futures", "OPEN", leg("OCT", "2026-10-05")),
        ("GOLD", "mcx_futures", "OPEN", leg("OCT", "2026-10-05")),
        ("GOLD", "mcx_futures", "CLOSED", leg("AUG", "2026-08-05")),
        ("GOLD", "other", "OPEN", leg("X", "2026-01-01")),
        ("GOLD", "mcx_futures", "OPEN", "not json")])
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", path)
    assert database.get_open_trade_contracts("GOLD", ("mcx_futures", "mcx_futures_srv3_shadow")) == ["OCT", "DEC"]
