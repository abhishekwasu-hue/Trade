"""tests/test_mcx_trade_replay.py -- read-only MCX replay: mcx_filters नियम, no-lookahead bars, forensics, margin तुलना (network/DB-मुक्त)."""
import json
import sqlite3

import numpy as np
import pandas as pd

import mcx_filters as F
import mcx_trade_replay as R


def _df30(closes, start="2026-09-28 09:00"):
    t = pd.date_range(start, periods=len(closes), freq="30min")
    c = np.asarray(closes, float)
    return pd.DataFrame({"timestamp": t, "open": c, "high": c + 2, "low": c - 2, "close": c, "volume": 0, "oi": 0})


# ---- mcx_filters ------------------------------------------------------------------------------------------------------
def test_supertrend_modes():
    assert F.supertrend_block("both_against", "BULLISH", "BEARISH", "BEARISH")[0]
    assert not F.supertrend_block("both_against", "BULLISH", "BULLISH", "BEARISH")[0]
    assert F.supertrend_block("htf_against", "BULLISH", "BULLISH", "BEARISH")[0]
    assert F.supertrend_block("htf_against", "BEARISH", None, "BULLISH")[0]
    assert not F.supertrend_block("htf_against", "BULLISH", "BEARISH", None)[0]          # डेटा नाही ⇒ fail-open
    assert not F.supertrend_block("off", "BULLISH", "BEARISH", "BEARISH")[0]


def test_sl_cooldown_and_level_direction():
    prior = [{"exit_time": "2026-09-30 10:30:00", "exit_reason": "SL", "realized_pnl": -25000, "entry_level_price": 150000.0,
              "direction": "BULLISH"},
             {"exit_time": "2026-09-30 09:40:00", "exit_reason": "TARGET", "realized_pnl": 30000, "entry_level_price": 151000.0,
              "direction": "BEARISH"}]
    blocked, why = F.sl_cooldown_block(prior, "2026-09-30 11:00:00", 60)
    assert blocked and "30 मिनिटं" in why
    assert not F.sl_cooldown_block(prior, "2026-09-30 11:31:00", 60)[0]
    assert F.sl_level_direction_block(prior, "2026-09-30 15:00:00", 150050.0, "BULLISH")[0]            # 0.033% अंतर
    assert not F.sl_level_direction_block(prior, "2026-09-30 15:00:00", 150050.0, "BEARISH")[0]        # दुसरी दिशा
    assert not F.sl_level_direction_block(prior, "2026-10-01 10:00:00", 150050.0, "BULLISH")[0]        # दुसरा दिवस
    assert not F.sl_level_direction_block(prior, "2026-09-30 15:00:00", 151000.0, "BEARISH")[0]        # target, SL नाही


def _cascade_frame(recover):
    # दिवस 1: 100 च्या आसपास swing low (95) तयार; दिवस 2: 95 खाली close (break), lower-high 92, मग (recover) 92 वर close
    d1 = [100, 98, 96, 95, 96, 98, 100, 101, 100, 99]
    d2 = [97, 94, 91, 89, 88, 90, 92, 90, 88, 87, 86, 87]
    d2 += [90, 93, 96, 97] if recover else [88, 87, 86]
    a = _df30(d1, "2026-09-29 09:00")
    b = _df30(d2, "2026-09-30 09:00")
    return pd.concat([a, b], ignore_index=True)


def test_cascade_blocks_long_below_broken_support_until_choch():
    blocked, why, info = F.cascade_block(_cascade_frame(False), "BULLISH", 85.0)
    assert blocked and info["cascade"] and info["broken_level"] == 93.0 and "CHoCH" in why
    blocked2, _, info2 = F.cascade_block(_cascade_frame(True), "BULLISH", 85.0)
    assert info2["cascade"] and info2["choch"] and not blocked2


def test_cascade_no_break_no_block():
    up = _df30(list(range(100, 130)), "2026-09-29 09:00")
    assert not F.cascade_block(up, "BULLISH", 99.0)[0]


# ---- replay ----------------------------------------------------------------------------------------------------------
def _db(tmp_path, trades):
    path = str(tmp_path / "t.db")
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE live_trades (trade_id TEXT, symbol TEXT, mode TEXT, source TEXT, strategy TEXT, legs_json TEXT, lots INT,
                    lot_size INT, net_credit REAL, entry_time TEXT, exit_time TEXT, exit_reason TEXT, exit_reason_detail TEXT,
                    realized_pnl REAL, entry_level_price REAL, peak_pnl REAL, status TEXT, entry_margin_required REAL)""")
    for t in trades:
        conn.execute("INSERT INTO live_trades (trade_id,symbol,mode,source,strategy,legs_json,lots,lot_size,net_credit,entry_time,exit_time,"
                     "exit_reason,exit_reason_detail,realized_pnl,entry_level_price,peak_pnl,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", t)
    conn.commit()
    conn.close()
    return path


def _trade(tid, strat, entry, exit_, reason, pnl, level, detail=None, source="mcx_futures"):
    legs = json.dumps([{"instrument_key": "MCX_FO|GOLDOCT", "expiry": "2026-10-05"}])
    return (tid, "GOLD", "PAPER", source, strat, legs, 1, 100, -level, entry, exit_, reason, detail, pnl, level, 5000, "CLOSED")


def test_load_trades_read_only_and_filters(tmp_path):
    path = _db(tmp_path, [_trade("A", "MCX_FUTURES_LONG", "2026-09-30 10:00:00", "2026-09-30 10:30:00", "SL", -100, 100.0),
                          _trade("B", "MCX_FUTURES_SHORT", "2026-10-01 10:00:00", "2026-10-01 11:00:00", "TRAILING_SL", 50, 101.0,
                                 source="mcx_futures_srv3_shadow"),
                          _trade("C", "MCX_FUTURES_LONG", "2026-10-01 10:00:00", None, None, None, 99.0, source="other")])
    rows = R.load_trades(path, "GOLD", "2026-09-30", "2026-10-01")
    assert [r["trade_id"] for r in rows] == ["A", "B"]
    assert rows[0]["direction"] == "BULLISH" and rows[1]["direction"] == "BEARISH" and rows[0]["instrument_key"] == "MCX_FO|GOLDOCT"
    assert [r["trade_id"] for r in R.load_trades(path, "GOLD", trade_ids=["B"])] == ["B"]


def test_closed_bars_no_lookahead():
    df30 = _df30(np.linspace(100, 120, 40), "2026-09-30 09:00")
    d30, h1, h4, _ = R.closed_bars_at(df30, None, pd.Timestamp("2026-09-30 13:10"))
    assert d30["timestamp"].iloc[-1] == pd.Timestamp("2026-09-30 12:30")                 # 12:30–13:00 पूर्ण, 13:00 चा नाही
    assert pd.Timestamp(h1["bar_end"].iloc[-1]) <= pd.Timestamp("2026-09-30 13:10")
    assert list(h4["timestamp"]) == [pd.Timestamp("2026-09-30 09:00")]                    # 09–13 चा 4H पूर्ण, 13–17 नाही


def test_evaluate_and_summary():
    df30 = _df30(np.linspace(200, 100, 120), "2026-09-25 09:00")                        # सतत पडता बाजार
    tr = {"trade_id": "L1", "entry_time": "2026-09-28 12:00:00", "direction": "BULLISH", "entry_level_price": 110.0,
          "exit_reason": "SL", "realized_pnl": -100.0}
    prior = [{"exit_time": "2026-09-28 11:30:00", "exit_reason": "SL", "realized_pnl": -50.0, "entry_level_price": 110.0, "direction": "BULLISH"}]
    row = R.evaluate_trade(tr, df30, None, prior)
    assert row["st_4h"] == "BEARISH" and row["b_htf_against"] and row["d_cooldown"]
    summ = R.summarize([row])
    assert int(summ.loc[summ["नियम"] == "(d) cooldown", "तोट्यातले अडले"].iloc[0]) == 1


def test_forensics_finds_first_cross():
    detail = ("Trailing SL — futures price Rs 147,693.00 hit/crossed the (profit-adjusted) trailing SL price Rs 147,250.00 "
              "(Short entry Rs 147,911.00, 661.00 pts below entry); total P&L Rs 21,800.")
    tr = {"trade_id": "S1", "direction": "BEARISH", "entry_time": "2026-10-01 10:00:00", "exit_time": "2026-10-01 10:20:00",
          "exit_reason": "TRAILING_SL", "exit_reason_detail": detail, "peak_pnl": 66100}
    assert R.parse_exit_prices(detail) == (147693.0, 147250.0)
    t = pd.date_range("2026-10-01 10:00", periods=25, freq="1min")
    hi = np.full(25, 147100.0)
    hi[12:] = 147700.0                                                                     # 10:12 ला level ओलांडला
    df1m = pd.DataFrame({"timestamp": t, "open": hi - 50, "high": hi, "low": hi - 100, "close": hi - 20})
    fz = R.forensics(tr, df1m)
    assert fz["first_cross_time"] == "2026-10-01 10:12:00" and fz["minutes_cross_to_exit"] == 8.0 and len(fz["candles"])


def test_margin_compare_uses_lots_and_value():
    contracts = [{"trading_symbol": "GOLD FUT 05 OCT 26", "expiry": "2026-10-05", "instrument_key": "K1", "lot_size": 1},
                 {"trading_symbol": "GOLD FUT 04 DEC 26", "expiry": "2026-12-04", "instrument_key": "K2", "lot_size": 1}]
    seen = []

    def margin_fn(tok, orders):
        seen.append(orders[0])
        return 2_500_000 if orders[0]["instrument_token"] == "K1" else 1_400_000
    out = R.margin_compare("tok", "GOLD", contracts, margin_fn=margin_fn, ltp_fn=lambda tok, keys: {keys[0]: 150000.0})
    assert list(out["BUY margin ₹"]) == [2_500_000, 1_400_000] and all(o["quantity"] == 1 for o in seen)
    assert out["contract value ₹"].iloc[0] == 150000.0 * 100                               # GOLD: भाव प्रति 10g, lot 1kg ⇒ ×100


def test_main_end_to_end_offline(tmp_path, capsys):
    path = _db(tmp_path, [_trade("A", "MCX_FUTURES_LONG", "2026-09-30 12:00:00", "2026-09-30 12:30:00", "SL", -100, 100.0),
                          _trade("B", "MCX_FUTURES_LONG", "2026-09-30 13:00:00", "2026-09-30 13:30:00", "SL", -100, 100.0)])
    df30 = _df30(np.linspace(130, 100, 120), "2026-09-27 09:00")

    def fetch(tok, key, interval="30minute", lookback_days=None):
        return df30 if interval != "1minute" else None
    rc = R.main(["--symbol", "GOLD", "--from", "2026-09-30", "--to", "2026-09-30", "--out", str(tmp_path / "o")], fetch=fetch, token="tok",
                db_path=path, settings={}, today=pd.Timestamp("2026-10-04").date())
    out = capsys.readouterr().out
    assert rc == 0 and "सारांश" in out and (tmp_path / "o" / "replay_GOLD.csv").exists()
    tbl = pd.read_csv(tmp_path / "o" / "replay_GOLD.csv")
    assert bool(tbl.loc[tbl["trade_id"] == "B", "d_cooldown"].iloc[0]) and not bool(tbl.loc[tbl["trade_id"] == "A", "d_cooldown"].iloc[0])


def test_forensics_trailing_searches_after_peak_and_reports_gap():
    # 1 Oct GOLD SHORT प्रमाणे: entry 147,911 (level 147,250 च्या वर — जुना कोड लगेच 'ओलांडला' म्हणायचा), भाव 146,950 पर्यंत खाली,
    # मग एकाच minute मध्ये 147,693 वर उडी.
    detail = ("Trailing SL — futures price Rs 147,693.00 hit/crossed the (profit-adjusted) trailing SL price Rs 147,250.00 "
              "(Short entry Rs 147,911.00, 661.00 pts below entry); total P&L Rs 21,800.")
    tr = {"trade_id": "S2", "direction": "BEARISH", "entry_time": "2026-10-01 11:24:40", "exit_time": "2026-10-01 16:37:03",
          "exit_reason": "TRAILING_SL", "exit_reason_detail": detail, "peak_pnl": 96100}
    t = pd.date_range("2026-10-01 11:24", "2026-10-01 16:39", freq="1min")
    px = np.where(t < pd.Timestamp("2026-10-01 16:26"), 147800.0, 146950.0)
    px = np.where(t >= pd.Timestamp("2026-10-01 16:35"), 147693.0, px)
    df1m = pd.DataFrame({"timestamp": t, "open": px, "high": px, "low": px, "close": px})
    fz = R.forensics(tr, df1m)
    assert fz["peak_price"] == 146950.0 and fz["peak_time"] == "2026-10-01 16:26:00"
    assert fz["first_cross_time"] == "2026-10-01 16:35:00" and abs(fz["minutes_cross_to_exit"] - 2.05) <= 0.06
    assert fz["price_before_cross"] == 146950.0 and fz["cross_open"] == 147693.0 and fz["gap_points"] == 743.0


def test_candle_confirmation_column_uses_only_bars_before_entry():
    df30 = _df30([105.0] * 10, start="2026-10-05 09:00")
    # 12:30 लाल candle + 13:00 Hammer (low 94, close 101) — support 100 ला लागून
    df30.loc[7, ["open", "high", "low", "close"]] = [104.0, 105.0, 100.5, 101.0]
    df30.loc[8, ["open", "high", "low", "close"]] = [100.0, 101.5, 94.0, 101.0]
    tr = {"trade_id": "X", "entry_time": "2026-10-05 13:40:00", "direction": "BULLISH", "entry_level_price": 100.0,
          "exit_reason": "SL", "realized_pnl": -10}
    row = R.evaluate_trade(tr, df30, None, [], {"candle_confirm_tf": "30M"})
    assert row["e_candle"] is False and row["e_pattern"].startswith("HAMMER 30M 13:00")
    early = R.evaluate_trade({**tr, "entry_time": "2026-10-05 13:20:00"}, df30, None, [], {"candle_confirm_tf": "30M"})
    assert early["e_candle"] is True and "(e)" in early["reasons"]          # 13:00 ची candle 13:30 ला पूर्ण -- आधी दिसू नये
    assert "(e) candle confirmation" in set(R.summarize([row, early])["नियम"])
