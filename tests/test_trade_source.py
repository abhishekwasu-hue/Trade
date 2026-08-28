"""
tests/test_trade_source.py
------------------------------
प्रत्येक trade कुठून आला (कोणत्या script/interface) — 'source' column, वापरकर्त्याशी चर्चा करून
जोडलेली सुधारणा. सर्व scripts+Dashboard एकाच Positions table मध्ये लिहितात, त्यामुळे source शिवाय
कुठला trade कुठून आला हे ओळखताच येत नव्हतं.
"""
import sqlite3
import tempfile

import database
import trading_engine


def test_source_stored_and_retrieved_correctly(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": {"order_ids": ["T1", "T2"]}}))
    monkeypatch.setattr(database, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})

    strategy_result = {
        "strategy": "BULL_PUT_SPREAD",
        "short_leg": {"strike": 24400, "instrument_key": "PE24400", "ltp": 50},
        "long_leg": {"strike": 24300, "instrument_key": "PE24300", "ltp": 25},
        "net_credit": 25, "max_profit": 25, "max_loss": 75,
    }
    success, result = trading_engine.open_multi_leg_trade(
        "fake_token", "NIFTY", strategy_result, lots=1, lot_size=75,
        sl_pct_of_max_loss=999, target_pct_of_max_profit=30, product_type="D",
        trading_mode="PAPER", trading_style="SWING", sl_pct_of_credit=30,
        source="oi_greeks_vix_strategy",
    )
    assert success is True

    positions_df = database.get_live_positions_with_mtm("fake_token", "NIFTY", mode_filter="PAPER")
    assert positions_df["Source"].iloc[0] == "oi_greeks_vix_strategy"


def test_missing_source_defaults_to_dashboard(monkeypatch):
    """source न दिल्यास ('MANUAL' डीफॉल्ट पॅरामीटर) — जुनं वर्तन तुटू नये (backward compat)."""
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": {"order_ids": ["T1", "T2"]}}))

    strategy_result = {
        "strategy": "BULL_PUT_SPREAD",
        "short_leg": {"strike": 24400, "instrument_key": "PE24400", "ltp": 50},
        "long_leg": {"strike": 24300, "instrument_key": "PE24300", "ltp": 25},
        "net_credit": 25, "max_profit": 25, "max_loss": 75,
    }
    success, result = trading_engine.open_multi_leg_trade(
        "fake_token", "NIFTY", strategy_result, lots=1, lot_size=75,
        sl_pct_of_max_loss=50, target_pct_of_max_profit=80, product_type="D",
        trading_mode="PAPER", trading_style="SWING",
        # source दिलेला नाही -- डीफॉल्ट "MANUAL"
    )
    assert success is True

    conn = sqlite3.connect(tmpdb)
    row = conn.execute("SELECT source FROM live_trades WHERE trade_id=?", (result["trade_id"],)).fetchone()
    conn.close()
    assert row[0] == "MANUAL"


def test_old_trades_without_source_show_dashboard_fallback(monkeypatch):
    """migration आधीचे trades (source=NULL) -- Positions page वर 'DASHBOARD' दाखवायला हवं, रिकामं नाही."""
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(database, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})

    import json
    legs = [
        {"instrument_key": "PE24400", "transaction_type": "SELL"},
        {"instrument_key": "PE24300", "transaction_type": "BUY"},
    ]
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, entry_time, status, legs_json, strikes_summary, mode, trading_style)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("OLD1", "2026-08-01", "NIFTY", "BULL_PUT_SPREAD", 1, 75, 25, 25, 75, "2026-08-01 10:00:00", "OPEN",
         json.dumps(legs), "test", "PAPER", "SWING"),  # source स्तंभ मुद्दाम दिलेलाच नाही (NULL राहील)
    )
    conn.commit()
    conn.close()

    positions_df = database.get_live_positions_with_mtm("fake_token", "NIFTY", mode_filter="PAPER")
    assert positions_df["Source"].iloc[0] == "DASHBOARD"
