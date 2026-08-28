"""
tests/test_market_report.py
--------------------------------
market_report.py — दररोज दुपारी ४ वाजताचा EOD Market Report साठी core data-gathering (वापरकर्त्याशी
चर्चा करून बांधलेली सुधारणा). PDF/Telegram रेंडरिंगपासून स्वतंत्र, फक्त डेटा-गोळा करण्याचं तर्कशास्त्र.
"""
import sqlite3
import tempfile

import numpy as np
import pandas as pd

import database
import market_report


def _make_df(walk, n=80):
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-08-27 09:15", periods=n, freq="15min"),
        "open": walk, "close": walk + 2, "high": walk + 8, "low": walk - 8, "volume": 1000,
    })


class TestComputeMultiTFOutlook:
    def test_all_three_bullish_gives_clear_bullish_outlook(self):
        np.random.seed(5)
        walk = 24000 + np.cumsum(abs(np.random.randn(60)) * 15)
        df = _make_df(walk, n=60)
        result = market_report.compute_multi_tf_outlook(df, df, df)
        assert result["outlook"] == "BULLISH"

    def test_mixed_directions_gives_mixed_outlook(self):
        np.random.seed(5)
        walk_up = 24000 + np.cumsum(abs(np.random.randn(60)) * 15)
        walk_down = 24000 - np.cumsum(abs(np.random.randn(60)) * 15)
        df_up, df_down = _make_df(walk_up, 60), _make_df(walk_down, 60)
        result = market_report.compute_multi_tf_outlook(df_up, df_down, df_up)
        assert result["outlook"] == "MIXED"

    def test_insufficient_data_returns_safe_default(self):
        result = market_report.compute_multi_tf_outlook(None, None, None)
        assert result["outlook"] == "INSUFFICIENT DATA"


class TestRecommendStrategy:
    def test_high_vix_warns_no_trade(self):
        assert "risky" in market_report.recommend_strategy(22, None)

    def test_low_vix_recommends_iron_condor(self):
        assert "Iron Condor" in market_report.recommend_strategy(13, None)

    def test_mid_vix_bullish_oi_recommends_bull_put(self):
        assert "Bull Put" in market_report.recommend_strategy(18, "BULLISH")

    def test_mid_vix_unclear_oi_recommends_caution(self):
        rec = market_report.recommend_strategy(18, None)
        assert "cautiously" in rec

    def test_no_vix_data_handled_gracefully(self):
        assert "unavailable" in market_report.recommend_strategy(None, None)


class TestGetTodayOIBuildupSummary:
    def test_bullish_buildup_detected_correctly(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()
        monkeypatch.setattr(market_report, "DB_PATH", tmpdb)

        from config import get_ist_today
        today_str = get_ist_today().strftime("%Y-%m-%d")
        conn = sqlite3.connect(tmpdb)
        conn.execute(
            "INSERT INTO oi_diff_snapshots (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal, total_call_premium, total_put_premium) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("NIFTY", today_str, "09:20", 100000, 100000, 0, 0, "NEUTRAL", 50.0, 50.0),
        )
        conn.execute(
            "INSERT INTO oi_diff_snapshots (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal, total_call_premium, total_put_premium) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("NIFTY", today_str, "15:20", 90000, 130000, 40000, 5000, "🟢 BULLISH (Strong)", 55.0, 40.0),
        )
        conn.commit()
        conn.close()

        summary = market_report.get_today_oi_buildup_summary("NIFTY")
        assert summary["day_direction"] == "BULLISH"
        assert "Writing" in summary["day_put_trend"]

    def test_no_data_returns_none_safely(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()
        monkeypatch.setattr(market_report, "DB_PATH", tmpdb)
        assert market_report.get_today_oi_buildup_summary("SENSEX") is None


class TestGenerateSymbolOutlook:
    def test_full_outlook_assembles_correctly(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()
        monkeypatch.setattr(market_report, "DB_PATH", tmpdb)

        np.random.seed(7)
        walk = 24000 + np.cumsum(np.random.randn(80) * 15)
        df = _make_df(walk)

        result = market_report.generate_symbol_outlook(
            "fake_token", "NIFTY", df_15m=df, df_1h=df, df_1d=df, india_vix=14.5, trading_mode="PAPER",
        )
        assert result["symbol"] == "NIFTY"
        assert "outlook" in result["multi_tf_outlook"]
        assert "Iron Condor" in result["recommendation"]
        assert result["open_positions_greeks"] == []


class TestFormatTelegramSummary:
    def test_multiple_symbols_included_in_summary(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()
        monkeypatch.setattr(market_report, "DB_PATH", tmpdb)

        np.random.seed(7)
        walk = 24000 + np.cumsum(np.random.randn(80) * 15)
        df = _make_df(walk)
        outlooks = [
            market_report.generate_symbol_outlook("fake_token", sym, df_15m=df, df_1h=df, df_1d=df, india_vix=13.5, trading_mode="PAPER")
            for sym in ["NIFTY", "BANKNIFTY"]
        ]
        summary = market_report.format_telegram_summary(outlooks)
        assert "NIFTY" in summary
        assert "BANKNIFTY" in summary
        assert "VIX" in summary
        assert "<b>" in summary  # Telegram HTML parse_mode शी सुसंगत
