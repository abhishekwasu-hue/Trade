"""
tests/test_charges.py
--------------------------------
charges.py — प्रति-ऑर्डर ब्रोकर्सना (Upstox/Fyers/Shoonya) ढोबळ ₹35/ऑर्डर (FLAT_CHARGE_PER_ORDER)
brokerage म्हणून लागतो का, Stocko चं निश्चित मासिक शुल्क आधीसारखंच वेगळं राहतं का, आणि stt/exchange_txn/
sebi_fee/stamp_duty/gst हे breakdown-सुसंगततेसाठी नेहमी 0 राहतात का, याची पडताळणी.
"""
import datetime

import pandas as pd
import pytest

import charges


def _orders_df(rows):
    """rows: list of dicts — order_id/placed_at/account_id."""
    defaults = {"order_id": "O1", "placed_at": "2026-09-10 10:00:00", "account_id": None}
    return pd.DataFrame([dict(defaults, **r) for r in rows])


class TestFlatChargePerOrder:
    def test_single_upstox_order_flat_charge(self):
        df = _orders_df([{"order_id": "O1"}])
        daily, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.FLAT_CHARGE_PER_ORDER)
        assert summary["per_broker"]["upstox"]["orders"] == 1

    def test_flat_charge_applies_regardless_of_broker_map_for_non_stocko(self):
        df = _orders_df([{"order_id": "O1", "account_id": "acc1"}])
        daily, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "shoonya"},
        )
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.FLAT_CHARGE_PER_ORDER)
        assert summary["per_broker"]["shoonya"]["orders"] == 1

    def test_multiple_orders_scale_linearly(self):
        df = _orders_df([{"order_id": "O1"}, {"order_id": "O2"}, {"order_id": "O3"}])
        daily, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(3 * charges.FLAT_CHARGE_PER_ORDER)
        assert summary["per_broker"]["upstox"]["orders"] == 3


class TestStatutoryChargesAreZero:
    def test_stt_exchange_sebi_stamp_gst_always_zero(self):
        df = _orders_df([{"order_id": "O1"}])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        b = summary["breakdown"]
        assert b["stt"] == 0.0
        assert b["exchange_txn"] == 0.0
        assert b["sebi_fee"] == 0.0
        assert b["stamp_duty"] == 0.0
        assert b["gst"] == 0.0

    def test_total_charge_equals_brokerage_only(self):
        df = _orders_df([{"order_id": "O1"}])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["total_charges"] == pytest.approx(summary["breakdown"]["brokerage"])


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

    def test_stocko_orders_get_no_per_order_flat_charge(self):
        df = _orders_df([{"order_id": "O1", "account_id": "acc1"}])
        daily, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "stocko"},
        )
        # प्रति-ऑर्डर ₹35 नाही — फक्त निश्चित मासिक शुल्क (वरच्या टेस्टमध्ये पडताळलेलं)
        stocko_daily = daily[daily["broker_type"] == "stocko"]
        assert (stocko_daily.loc[stocko_daily["orders"] > 0, "brokerage"] == 0.0).all()


class TestEmptyAndMissingColumns:
    def test_empty_orders_df_returns_zero_summary(self):
        daily, summary = charges.compute_charges(pd.DataFrame(), datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["total_charges"] == 0.0
        assert summary["breakdown"] == {"brokerage": 0.0, "stt": 0.0, "exchange_txn": 0.0, "sebi_fee": 0.0, "stamp_duty": 0.0, "gst": 0.0}

    def test_minimal_columns_still_produce_flat_charge(self):
        df = pd.DataFrame([{"order_id": "O1", "placed_at": "2026-09-10 10:00:00", "account_id": None}])
        daily, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.FLAT_CHARGE_PER_ORDER)
        assert summary["breakdown"]["stt"] == 0.0
        assert summary["breakdown"]["exchange_txn"] == 0.0
