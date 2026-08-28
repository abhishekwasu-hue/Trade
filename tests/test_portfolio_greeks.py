"""
tests/test_portfolio_greeks.py
-----------------------------------
database.compute_portfolio_greeks + upstox_api.fetch_option_greeks — Portfolio-level Delta/Gamma/
Theta/Vega monitoring (वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — जागतिक prop trading firms जसं
सतत करतात तसंच).
"""
import json
import sqlite3
import tempfile

import pytest

import database
import upstox_api


@pytest.fixture
def temp_db_with_position(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()

    legs = [
        {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL"},
        {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY"},
    ]
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, entry_time, status, legs_json, strikes_summary, mode, trading_style)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("T1", "2026-08-27", "NIFTY", "BULL_PUT_SPREAD", 1, 75, 30, 30, 70, "2026-08-27 10:00:00", "OPEN",
         json.dumps(legs), "test", "PAPER", "SWING"),
    )
    conn.commit()
    conn.close()
    yield tmpdb


class TestComputePortfolioGreeks:
    def test_bull_put_spread_gives_positive_delta_and_theta(self, temp_db_with_position, monkeypatch):
        """Bull Put Spread -- bullish bias (धन Delta) + credit spread ला वेळेचा फायदा (धन Theta)."""
        monkeypatch.setattr(upstox_api, "fetch_option_greeks", lambda t, k: {
            "PE24400": {"delta": -0.35, "gamma": 0.002, "theta": -8.5, "vega": 12.0},
            "PE24300": {"delta": -0.20, "gamma": 0.0015, "theta": -6.0, "vega": 9.0},
        })
        result = database.compute_portfolio_greeks("fake_token", "NIFTY", mode_filter="PAPER")
        assert result["positions_included"] == 1
        assert result["net_delta"] == 11.25
        assert result["net_theta"] > 0  # credit spread ला वेळेचा फायदा
        assert result["net_vega"] < 0   # short options -- IV वाढल्यास तोटा

    def test_no_open_positions_returns_safe_zeros(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()
        result = database.compute_portfolio_greeks("fake_token", "NIFTY")
        assert result == {"net_delta": 0.0, "net_gamma": 0.0, "net_theta": 0.0, "net_vega": 0.0, "positions_included": 0}

    def test_missing_greeks_data_does_not_crash(self, temp_db_with_position, monkeypatch):
        """API कडून Greeks मिळाले नाहीत (रिकामा dict) तरी crash न होता सुरक्षित शून्य."""
        monkeypatch.setattr(upstox_api, "fetch_option_greeks", lambda t, k: {})
        result = database.compute_portfolio_greeks("fake_token", "NIFTY", mode_filter="PAPER")
        assert result["net_delta"] == 0.0
        assert result["positions_included"] == 1  # position आहे, पण greeks नाहीत म्हणून योगदान शून्य


class TestFetchOptionGreeksGracefulFallback:
    def test_empty_instrument_keys_returns_empty_dict(self):
        assert upstox_api.fetch_option_greeks("fake_token", []) == {}


class TestCheckPositionDeltaHealth:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Iron Condor/Spread साठी रणनीती-आधारित Delta तपासणी."""

    def test_iron_condor_balanced_is_healthy(self):
        emoji, msg = database.check_position_delta_health("IRON_CONDOR", 5)
        assert emoji == "✅"

    def test_iron_condor_tested_side_warns(self):
        emoji, msg = database.check_position_delta_health("IRON_CONDOR", 20)
        assert emoji == "⚠️"
        assert "टेस्ट" in msg

    def test_bull_put_spread_correct_direction_is_healthy(self):
        emoji, msg = database.check_position_delta_health("BULL_PUT_SPREAD", 15)
        assert emoji == "✅"

    def test_bull_put_spread_wrong_direction_is_critical(self):
        """Bullish थीसिस असूनही Delta ऋण -- मूळ गृहीतक अपयशी, गंभीर इशारा हवा."""
        emoji, msg = database.check_position_delta_health("BULL_PUT_SPREAD", -10)
        assert emoji == "🔴"

    def test_bull_put_spread_deep_itm_warns(self):
        emoji, msg = database.check_position_delta_health("BULL_PUT_SPREAD", 45)
        assert emoji == "⚠️"

    def test_bear_call_spread_correct_direction_is_healthy(self):
        emoji, msg = database.check_position_delta_health("BEAR_CALL_SPREAD", -15)
        assert emoji == "✅"

    def test_bear_call_spread_wrong_direction_is_critical(self):
        emoji, msg = database.check_position_delta_health("BEAR_CALL_SPREAD", 10)
        assert emoji == "🔴"


class TestComputePerPositionGreeks:
    def test_iron_condor_and_spread_get_different_health_checks(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()

        legs_ic = [
            {"instrument_key": "CE24800", "transaction_type": "SELL"},
            {"instrument_key": "CE24900", "transaction_type": "BUY"},
            {"instrument_key": "PE24200", "transaction_type": "SELL"},
            {"instrument_key": "PE24100", "transaction_type": "BUY"},
        ]
        conn = sqlite3.connect(tmpdb)
        conn.execute(
            """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
               max_profit, max_loss, entry_time, status, legs_json, strikes_summary, mode, trading_style)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("IC1", "2026-08-27", "NIFTY", "IRON_CONDOR", 1, 75, 40, 40, 60, "2026-08-27 10:00:00", "OPEN",
             json.dumps(legs_ic), "test", "PAPER", "SWING"),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(upstox_api, "fetch_option_greeks", lambda t, k: {
            "CE24800": {"delta": 0.68, "gamma": 0.003, "theta": -10, "vega": 15},
            "CE24900": {"delta": 0.35, "gamma": 0.002, "theta": -7, "vega": 11},
            "PE24200": {"delta": -0.10, "gamma": 0.001, "theta": -3, "vega": 5},
            "PE24100": {"delta": -0.05, "gamma": 0.0005, "theta": -2, "vega": 3},
        })
        results = database.compute_per_position_greeks("fake_token", "NIFTY", mode_filter="PAPER")
        assert len(results) == 1
        assert results[0]["health_emoji"] == "⚠️"
        assert "Call" in results[0]["health_message"]
