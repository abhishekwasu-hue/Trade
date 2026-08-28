"""
tests/test_dte.py
---------------------
compute_dte — OI Diff Tracker वर Expiry पर्यंत किती दिवस उरले (DTE) ते दाखवण्यासाठी.
"""
import datetime

from oi_analysis import compute_dte


class TestComputeDTE:
    def test_normal_case(self):
        today = datetime.date(2026, 8, 25)
        chain = [{"strike_price": 24500, "expiry": "2026-09-01"}]
        expiry, dte = compute_dte(chain, today)
        assert expiry == datetime.date(2026, 9, 1)
        assert dte == 7

    def test_expiry_today(self):
        today = datetime.date(2026, 8, 25)
        chain = [{"strike_price": 24500, "expiry": "2026-08-25"}]
        _, dte = compute_dte(chain, today)
        assert dte == 0

    def test_missing_expiry_field_returns_none_safely(self):
        today = datetime.date(2026, 8, 25)
        chain = [{"strike_price": 24500}]
        expiry, dte = compute_dte(chain, today)
        assert expiry is None and dte is None

    def test_empty_chain_returns_none_safely(self):
        expiry, dte = compute_dte([], datetime.date(2026, 8, 25))
        assert expiry is None and dte is None

    def test_invalid_date_format_returns_none_safely(self):
        today = datetime.date(2026, 8, 25)
        chain = [{"strike_price": 24500, "expiry": "invalid-date"}]
        expiry, dte = compute_dte(chain, today)
        assert expiry is None and dte is None
