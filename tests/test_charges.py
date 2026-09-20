"""
tests/test_charges.py
--------------------------------
charges.py — Brokerage + STT/Exchange Txn Charge/SEBI Fee/Stamp Duty/GST मोजणी अचूक आहे का,
आणि Stocko चं निश्चित मासिक शुल्क आधीसारखंच वेगळं राहतं का, याची पडताळणी.
"""
import datetime

import pandas as pd
import pytest

import charges


def _orders_df(rows):
    """rows: list of dicts — order_id/placed_at/account_id/quantity/fill_price/price/transaction_type."""
    defaults = {
        "order_id": "O1", "placed_at": "2026-09-10 10:00:00", "account_id": None,
        "quantity": 75, "fill_price": 100.0, "price": 0.0, "transaction_type": "SELL",
    }
    return pd.DataFrame([dict(defaults, **r) for r in rows])


class TestBrokeragePerOrder:
    def test_single_upstox_sell_order_brokerage(self):
        df = _orders_df([{"order_id": "O1"}])
        daily, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(20.0)
        assert summary["per_broker"]["upstox"]["orders"] == 1

    def test_shoonya_brokerage_via_broker_map(self):
        df = _orders_df([{"order_id": "O1", "account_id": "acc1"}])
        daily, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "shoonya"},
        )
        assert summary["breakdown"]["brokerage"] == pytest.approx(5.0)
        assert summary["per_broker"]["shoonya"]["orders"] == 1


class TestStatutoryCharges:
    def test_stt_only_on_sell_orders(self):
        # quantity=75, fill_price=100 -> turnover = 7500
        sell = _orders_df([{"order_id": "O1", "transaction_type": "SELL"}])
        buy = _orders_df([{"order_id": "O1", "transaction_type": "BUY"}])
        _, sell_summary = charges.compute_charges(sell, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        _, buy_summary = charges.compute_charges(buy, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert sell_summary["breakdown"]["stt"] == pytest.approx(7500 * charges.STT_SELL_PCT, abs=0.01)
        assert buy_summary["breakdown"]["stt"] == pytest.approx(0.0)

    def test_stamp_duty_only_on_buy_orders(self):
        sell = _orders_df([{"order_id": "O1", "transaction_type": "SELL"}])
        buy = _orders_df([{"order_id": "O1", "transaction_type": "BUY"}])
        _, sell_summary = charges.compute_charges(sell, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        _, buy_summary = charges.compute_charges(buy, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert sell_summary["breakdown"]["stamp_duty"] == pytest.approx(0.0)
        assert buy_summary["breakdown"]["stamp_duty"] == pytest.approx(7500 * charges.STAMP_DUTY_BUY_PCT, abs=0.01)

    def test_exchange_txn_and_sebi_fee_apply_both_sides(self):
        for txn in ("BUY", "SELL"):
            df = _orders_df([{"order_id": "O1", "transaction_type": txn}])
            _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
            assert summary["breakdown"]["exchange_txn"] == pytest.approx(7500 * charges.EXCHANGE_TXN_PCT, abs=0.01)
            assert summary["breakdown"]["sebi_fee"] == pytest.approx(7500 * charges.SEBI_TURNOVER_PCT, abs=0.001)

    def test_gst_applies_only_to_brokerage_exchange_and_sebi(self):
        df = _orders_df([{"order_id": "O1", "transaction_type": "SELL"}])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        b = summary["breakdown"]
        expected_gst = (b["brokerage"] + b["exchange_txn"] + b["sebi_fee"]) * charges.GST_PCT
        assert b["gst"] == pytest.approx(expected_gst, abs=0.01)

    def test_uses_fill_price_over_request_price_when_available(self):
        df = _orders_df([{"order_id": "O1", "fill_price": 100.0, "price": 999.0}])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        # turnover 75*100=7500, नाही तर 75*999 असतं
        assert summary["breakdown"]["exchange_txn"] == pytest.approx(7500 * charges.EXCHANGE_TXN_PCT, abs=0.01)

    def test_falls_back_to_request_price_when_fill_price_missing(self):
        df = _orders_df([{"order_id": "O1", "fill_price": 0.0, "price": 100.0}])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["exchange_txn"] == pytest.approx(7500 * charges.EXCHANGE_TXN_PCT, abs=0.01)

    def test_total_charge_is_sum_of_all_components(self):
        df = _orders_df([{"order_id": "O1", "transaction_type": "SELL"}])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        b = summary["breakdown"]
        expected_total = sum(b.values())
        assert summary["total_charges"] == pytest.approx(expected_total, abs=0.05)


class TestStockoFlatMonthly:
    def test_stocko_brokerage_is_flat_monthly_not_per_order(self):
        df = _orders_df([
            {"order_id": "O1", "account_id": "acc1", "placed_at": "2026-09-05 10:00:00"},
            {"order_id": "O2", "account_id": "acc1", "placed_at": "2026-09-06 10:00:00"},
        ])
        daily, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "stocko"},
        )
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.STOCKO_FLAT_MONTHLY, rel=0.01)
        assert summary["per_broker"]["stocko"]["orders"] == 2

    def test_stocko_orders_still_get_statutory_charges(self):
        df = _orders_df([{"order_id": "O1", "account_id": "acc1", "transaction_type": "SELL"}])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "stocko"},
        )
        assert summary["breakdown"]["stt"] == pytest.approx(7500 * charges.STT_SELL_PCT)


class TestEmptyAndMissingColumns:
    def test_empty_orders_df_returns_zero_summary(self):
        daily, summary = charges.compute_charges(pd.DataFrame(), datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["total_charges"] == 0.0
        assert summary["breakdown"] == {"brokerage": 0.0, "stt": 0.0, "exchange_txn": 0.0, "sebi_fee": 0.0, "stamp_duty": 0.0, "gst": 0.0}

    def test_missing_turnover_columns_falls_back_to_brokerage_only(self):
        df = pd.DataFrame([{"order_id": "O1", "placed_at": "2026-09-10 10:00:00", "account_id": None}])
        daily, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(20.0)
        assert summary["breakdown"]["stt"] == 0.0
        assert summary["breakdown"]["exchange_txn"] == 0.0
