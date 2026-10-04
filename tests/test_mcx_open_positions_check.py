"""tests/test_mcx_open_positions_check.py -- read-only MCX उघड्या positions + contract expiry तपासणी (network/DB-free)."""
import datetime
import json
import sqlite3

import mcx_open_positions_check as C

TODAY = datetime.date(2026, 10, 4)                      # रविवार


def test_trading_days_left_weekdays_only():
    assert C.trading_days_left(TODAY, datetime.date(2026, 10, 5)) == 1                   # सोमवार expiry
    assert C.trading_days_left(datetime.date(2026, 9, 28), datetime.date(2026, 10, 5)) == 6
    assert C.trading_days_left(TODAY, datetime.date(2026, 10, 3)) == 0 and C.trading_days_left(TODAY, None) == 0


def _db(tmp_path, rows):
    path = str(tmp_path / "t.db")
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE live_trades (trade_id TEXT, symbol TEXT, mode TEXT, account_id TEXT, source TEXT, legs_json TEXT, entry_time TEXT, "
              "strategy TEXT, lots INTEGER, status TEXT)")
    c.executemany("INSERT INTO live_trades VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()
    return path


def test_db_open_positions_flags_expiry_near(tmp_path):
    legs = json.dumps([{"instrument_key": "MCX_FO|OCT", "expiry": "2026-10-05"}])
    path = _db(tmp_path, [("T1", "GOLD", "PAPER", None, "mcx_futures", legs, "2026-10-01 20:00:00", "MCX_FUTURES_LONG", 1, "OPEN"),
                          ("T2", "GOLD", "PAPER", None, "mcx_futures", legs, "2026-10-01 10:00:00", "MCX_FUTURES_LONG", 1, "CLOSED"),
                          ("T3", "NIFTY", "PAPER", None, "dynamic_sr_instant", "[]", "2026-10-01", "X", 1, "OPEN")])
    rows, err = C.db_open_positions(path, ["GOLD", "SILVER"], TODAY, 6)
    assert err is None and [r["trade_id"] for r in rows] == ["T1"] and rows[0]["warn"] and rows[0]["trading_days_left"] == 1
    assert rows[0]["account_id"] == "Upstox (डीफॉल्ट)"


def test_broker_mcx_positions_filters_exchange_and_zero_qty():
    pos = [{"exchange": "MCX", "trading_symbol": "GOLD FUT 05 OCT 26", "instrument_token": "MCX_FO|1", "quantity": 1},
           {"exchange": "MCX", "trading_symbol": "SILVER FUT", "instrument_token": "MCX_FO|2", "quantity": 0},
           {"exchange": "NFO", "trading_symbol": "NIFTY", "instrument_token": "NSE_FO|3", "quantity": 75}]
    out = C.broker_mcx_positions(pos)
    assert [r["trading_symbol"] for r in out] == ["GOLD FUT 05 OCT 26"] and C.broker_mcx_positions(None) is None


def test_main_end_to_end(tmp_path, capsys):
    path = _db(tmp_path, [])

    def resolve(tok, sym):
        exp = "2026-10-05" if sym == "GOLD" else "2026-11-18"
        return True, {"trading_symbol": f"{sym} FUT", "expiry": exp, "all_upcoming_expiries": [exp, "2026-12-04"]}
    assert C.main([], resolve=resolve, positions_fn=lambda t: [], token_fn=lambda t: "tok", db_path=path, today=TODAY) == 0
    out = capsys.readouterr().out
    assert "⚠️ GOLD" in out and "उरलेले ट्रेडिंग दिवस: 1" in out and "✅ कुठलीही उघडी MCX position नाही" in out and "1 मुद्दे" in out
