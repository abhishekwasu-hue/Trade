"""
tests/test_market_hours.py
------------------------------
config.is_market_open — unattended scripts (oi_snapshot_collector.py, credit_spread_auto_trader.py,
oi_signal_auto_trader.py) बाजार बंद असताना उगाच Option Chain fetch करू नयेत यासाठीची सुधारणा.
"""
import datetime

from config import is_market_open, is_trading_day


class TestIsMarketOpen:
    def test_weekday_during_market_hours_is_open(self):
        assert is_market_open(datetime.datetime(2026, 8, 24, 11, 0)) is True  # सोमवार, 11:00

    def test_weekday_before_market_open_is_closed(self):
        assert is_market_open(datetime.datetime(2026, 8, 24, 8, 0)) is False

    def test_weekday_after_market_close_is_closed(self):
        assert is_market_open(datetime.datetime(2026, 8, 24, 16, 0)) is False

    def test_saturday_is_closed_regardless_of_time(self):
        assert is_market_open(datetime.datetime(2026, 8, 29, 11, 0)) is False

    def test_sunday_is_closed_regardless_of_time(self):
        assert is_market_open(datetime.datetime(2026, 8, 30, 11, 0)) is False

    def test_exact_open_boundary_is_open(self):
        assert is_market_open(datetime.datetime(2026, 8, 24, 9, 15)) is True

    def test_exact_close_boundary_is_open(self):
        assert is_market_open(datetime.datetime(2026, 8, 24, 15, 30)) is True

    def test_one_minute_after_close_is_closed(self):
        assert is_market_open(datetime.datetime(2026, 8, 24, 15, 31)) is False

    def test_nse_holiday_on_weekday_is_closed(self):
        """दिवाळी-बलिप्रतिपदा (10 नोव्हे 2026, मंगळवार) — सामान्य ट्रेडिंग दिवस असता, पण NSE सुट्टी आहे."""
        assert is_market_open(datetime.datetime(2026, 11, 10, 11, 0)) is False

    def test_gandhi_jayanti_is_closed(self):
        assert is_market_open(datetime.datetime(2026, 10, 2, 11, 0)) is False

    def test_ordinary_weekday_not_in_holiday_list_is_open(self):
        assert is_market_open(datetime.datetime(2026, 11, 11, 11, 0)) is True  # बुधवार, सुट्टी यादीत नाही


class TestIsTradingDay:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — eod_market_report.py सारख्या दुपारी ४ वाजता
    (बाजार बंद झाल्यानंतर) चालणाऱ्या scripts साठी, फक्त दिवस तपासणारं स्वतंत्र function."""

    def test_weekday_evening_after_market_close_is_still_trading_day(self):
        assert is_trading_day(datetime.datetime(2026, 8, 24, 16, 0)) is True  # सोमवार, 4pm

    def test_weekend_is_not_trading_day(self):
        assert is_trading_day(datetime.datetime(2026, 8, 29, 16, 0)) is False  # शनिवार

    def test_holiday_is_not_trading_day(self):
        assert is_trading_day(datetime.datetime(2026, 11, 10, 16, 0)) is False  # दिवाळी-बलिप्रतिपदा
