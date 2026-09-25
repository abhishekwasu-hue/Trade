"""
tests/test_charges.py
--------------------------------
charges.py — 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Upstox brokerage calculator वापरून actual
brokerage काढा", नंतर "Stocko आणि Fyers साठी पण actual calculator लावता येईल का", नंतर "Shoonya
che pn kra update") — Upstox/Fyers/Shoonya ऑर्डर्ससाठी (symbol/quantity/price/transaction_type
उपलब्ध असल्यास) आता वास्तविक brokerage+STT/CTT+Exchange+SEBI+Stamp+GST मोजलं जातं (segment नुसार
वेगळे दर — NSE Options वि. MCX Commodity Futures; brokerage फॉर्म्युला ब्रोकरनुसार वेगळा, statutory
दर तिघांना सारखेच), तपशील अपुरा असेल तिथेच जुना ढोबळ ₹25/ऑर्डर अंदाज. Stocko चं निश्चित मासिक
brokerage आधीसारखंच वेगळं, पण आता त्याच्याही per-order STT/Exchange/SEBI/Stamp Duty वास्तविक दराने
मोजले जातात.
"""
import datetime

import pandas as pd
import pytest

import charges


def _orders_df(rows):
    """rows: list of dicts — order_id/placed_at/account_id/symbol/quantity/transaction_type/fill_price."""
    defaults = {"order_id": "O1", "placed_at": "2026-09-10 10:00:00", "account_id": None}
    return pd.DataFrame([dict(defaults, **r) for r in rows])


class TestUpstoxAccurateOptionsCharges:
    def test_options_sell_order_has_stt_exchange_sebi_gst_no_stamp(self):
        """SELL leg: STT + Exchange + SEBI + GST लागतात, Stamp Duty (फक्त BUY) लागत नाही.
        (मोठा quantity — जेणेकरून ₹10/crore सारखा अतिशय लहान SEBI fee summary च्या 2-दशांश-स्थळ
        round() मध्ये पूर्णपणे नाहीसा होणार नाही.)"""
        df = _orders_df([{
            "order_id": "O1", "symbol": "NIFTY", "quantity": 5000, "transaction_type": "SELL",
            "fill_price": 100.0,
        }])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        b = summary["breakdown"]
        turnover = 5000 * 100.0
        assert b["brokerage"] == pytest.approx(20.0)
        assert b["stt"] == pytest.approx(turnover * 0.001)
        assert b["exchange_txn"] == pytest.approx(turnover * 0.00035)
        assert b["sebi_fee"] == pytest.approx(turnover * 0.000001)
        assert b["stamp_duty"] == pytest.approx(0.0)
        assert b["gst"] == pytest.approx((20.0 + turnover * 0.00035 + turnover * 0.000001) * 0.18)

    def test_options_buy_order_has_stamp_not_stt(self):
        """BUY leg: Stamp Duty लागते, STT (फक्त SELL) लागत नाही."""
        df = _orders_df([{
            "order_id": "O1", "symbol": "BANKNIFTY", "quantity": 15, "transaction_type": "BUY",
            "fill_price": 200.0,
        }])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        b = summary["breakdown"]
        turnover = 15 * 200.0
        assert b["stt"] == pytest.approx(0.0)
        assert b["stamp_duty"] == pytest.approx(turnover * 0.00003)

    def test_options_brokerage_always_flat_20(self):
        """Options brokerage फ्लॅट ₹20/order — मोठ्या turnover वरही टक्केवारी लागू होत नाही."""
        df = _orders_df([{
            "order_id": "O1", "symbol": "NIFTY", "quantity": 5000, "transaction_type": "BUY",
            "fill_price": 500.0,
        }])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(20.0)


class TestUpstoxAccurateCommodityFuturesCharges:
    def test_commodity_symbol_gets_ctt_not_options_stt(self):
        df = _orders_df([{
            "order_id": "O1", "symbol": "CRUDEOIL", "quantity": 100, "transaction_type": "SELL",
            "fill_price": 6000.0,
        }])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        b = summary["breakdown"]
        turnover = 100 * 6000.0
        assert b["stt"] == pytest.approx(turnover * 0.0001)  # CTT 0.01%, options STT (0.1%) नाही

    def test_commodity_brokerage_is_lower_of_flat_or_percent(self):
        """मोठा turnover — 0.05% हा ₹20 पेक्षा जास्त होतो, त्यामुळे फ्लॅट ₹20 लागायला हवं."""
        df = _orders_df([{
            "order_id": "O1", "symbol": "GOLD", "quantity": 100, "transaction_type": "BUY",
            "fill_price": 70000.0,
        }])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(20.0)

    def test_commodity_small_turnover_uses_percent_brokerage(self):
        """लहान turnover — 0.05% हा ₹20 पेक्षा कमी होतो, त्यामुळे percent-based brokerage लागायला हवं."""
        df = _orders_df([{
            "order_id": "O1", "symbol": "SILVER", "quantity": 1, "transaction_type": "BUY",
            "fill_price": 1000.0,
        }])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(1000.0 * 0.0005)


class TestUpstoxFallsBackToFlatWhenDataMissing:
    def test_upstox_order_without_symbol_falls_back_to_flat(self):
        df = _orders_df([{"order_id": "O1"}])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.FLAT_CHARGE_PER_ORDER)
        assert summary["breakdown"]["stt"] == 0.0
        assert summary["per_broker"]["upstox"]["orders"] == 1

    def test_upstox_order_with_zero_quantity_falls_back_to_flat(self):
        df = _orders_df([{
            "order_id": "O1", "symbol": "NIFTY", "quantity": 0, "transaction_type": "BUY",
            "fill_price": 100.0,
        }])
        _, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.FLAT_CHARGE_PER_ORDER)

    def test_multiple_orders_scale_linearly(self):
        df = _orders_df([{"order_id": "O1"}, {"order_id": "O2"}, {"order_id": "O3"}])
        daily, summary = charges.compute_charges(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert summary["breakdown"]["brokerage"] == pytest.approx(3 * charges.FLAT_CHARGE_PER_ORDER)
        assert summary["per_broker"]["upstox"]["orders"] == 3


class TestShoonyaAccurateCharges:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Shoonya che pn kra update") — Shoonya ऑर्डर्ससाठीही आता
    Upstox/Fyers सारखंच वास्तविक brokerage+statutory शुल्क मोजलं जातं — brokerage सर्वात कमी
    (फ्लॅट ₹5/order, किंवा Commodity Futures साठी ₹5 किंवा 0.03% जे कमी), statutory दर इतर
    ब्रोकर्ससारखेच."""

    def test_shoonya_options_brokerage_flat_5(self):
        df = _orders_df([{
            "order_id": "O1", "account_id": "acc1", "symbol": "NIFTY", "quantity": 50,
            "transaction_type": "SELL", "fill_price": 100.0,
        }])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "shoonya"},
        )
        turnover = 50 * 100.0
        assert summary["breakdown"]["brokerage"] == pytest.approx(5.0)
        assert summary["breakdown"]["stt"] == pytest.approx(turnover * 0.001)  # statutory दर इतर ब्रोकर्ससारखेच
        assert summary["per_broker"]["shoonya"]["orders"] == 1

    def test_shoonya_commodity_brokerage_lower_of_flat_or_percent(self):
        df = _orders_df([{
            "order_id": "O1", "account_id": "acc1", "symbol": "GOLD", "quantity": 1,
            "transaction_type": "BUY", "fill_price": 50000.0,
        }])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "shoonya"},
        )
        assert summary["breakdown"]["brokerage"] == pytest.approx(min(5.0, 50000.0 * 0.0003))

    def test_shoonya_falls_back_to_flat_when_data_missing(self):
        df = _orders_df([{"order_id": "O1", "account_id": "acc1"}])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "shoonya"},
        )
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.FLAT_CHARGE_PER_ORDER)


class TestFyersAccurateCharges:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Stocko आणि Fyers साठी पण actual calculator लावता येईल
    का") — Fyers ऑर्डर्ससाठीही आता Upstox सारखंच वास्तविक brokerage+statutory शुल्क मोजलं जातं,
    फक्त brokerage दर वेगळे (Options ₹20 फ्लॅट — Upstox सारखंच; Commodity Futures ₹20 किंवा 0.03%,
    Upstox च्या 0.05% पेक्षा कमी)."""

    def test_fyers_options_brokerage_flat_20_same_as_upstox(self):
        df = _orders_df([{
            "order_id": "O1", "account_id": "acc1", "symbol": "NIFTY", "quantity": 50,
            "transaction_type": "SELL", "fill_price": 100.0,
        }])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "fyers"},
        )
        turnover = 50 * 100.0
        assert summary["breakdown"]["brokerage"] == pytest.approx(20.0)
        assert summary["breakdown"]["stt"] == pytest.approx(turnover * 0.001)  # statutory दर Upstox सारखेच

    def test_fyers_commodity_brokerage_uses_lower_percent_than_upstox(self):
        """मोठा turnover — Fyers चं 0.03% हे Upstox च्या 0.05% पेक्षा कमी रक्कम देतं (₹20 च्या आतच)."""
        df = _orders_df([{
            "order_id": "O1", "account_id": "acc1", "symbol": "GOLD", "quantity": 1,
            "transaction_type": "BUY", "fill_price": 50000.0,
        }])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "fyers"},
        )
        assert summary["breakdown"]["brokerage"] == pytest.approx(50000.0 * 0.0003)

    def test_fyers_falls_back_to_flat_when_data_missing(self):
        df = _orders_df([{"order_id": "O1", "account_id": "acc1"}])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "fyers"},
        )
        assert summary["breakdown"]["brokerage"] == pytest.approx(charges.FLAT_CHARGE_PER_ORDER)


class TestStockoStatutoryCharges:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा — Stocko चं brokerage निश्चित मासिक असलं तरी STT/Exchange/
    SEBI/Stamp Duty हे सरकारी शुल्क त्यावरही (per-order) लागू होतातच."""

    def test_stocko_order_gets_real_statutory_charges_not_zero(self):
        df = _orders_df([{
            "order_id": "O1", "account_id": "acc1", "symbol": "NIFTY", "quantity": 5000,
            "transaction_type": "SELL", "fill_price": 100.0,
        }])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "stocko"},
        )
        turnover = 5000 * 100.0
        b = summary["breakdown"]
        assert b["stt"] == pytest.approx(turnover * 0.001)
        assert b["exchange_txn"] == pytest.approx(turnover * 0.00035)
        expected_gst = (turnover * 0.00035 + turnover * 0.000001) * 0.18  # brokerage component नाही, फक्त exchange+SEBI वर
        assert b["gst"] == pytest.approx(expected_gst, abs=0.01)

    def test_stocko_order_without_trade_detail_gets_zero_statutory(self):
        """तपशील नसेल तर statutory 0 राहतं — brokerage साठी जुना ढोबळ अंदाज इथे लागू होत नाही
        (double-count टाळण्यासाठी, कारण brokerage आधीच मासिक सबस्क्रिप्शनमधून मोजला जातो)."""
        df = _orders_df([{"order_id": "O1", "account_id": "acc1"}])
        _, summary = charges.compute_charges(
            df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30), broker_map={"acc1": "stocko"},
        )
        assert summary["breakdown"]["stt"] == 0.0
        assert summary["breakdown"]["exchange_txn"] == 0.0


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
        # प्रति-ऑर्डर ₹25 नाही — फक्त निश्चित मासिक शुल्क (वरच्या टेस्टमध्ये पडताळलेलं)
        stocko_daily = daily[daily["broker_type"] == "stocko"]
        assert (stocko_daily.loc[stocko_daily["orders"] > 0, "brokerage"] == 0.0).all()


class TestHypotheticalChargesByBroker:
    """🎓 वापरकर्त्याने निदर्शनास आणलेली त्रुटी ("सर्व ब्रोकरचा तुलनात्मक तक्ता आपण दिलेला नाही, फक्त
    Upstox चा दिलेला आहे") — compute_charges()चं per_broker प्रत्यक्ष *वापरलेल्या* ब्रोकरनुसारच
    गटवारी करतं (खातं फक्त Upstox चंच असेल तर तिथेही फक्त Upstoxच दिसतो). नवीन
    compute_hypothetical_charges_by_broker() त्याऐवजी, प्रत्यक्ष कुठला ब्रोकर वापरला याकडे दुर्लक्ष
    करून, त्याच orders साठी सर्व चार ब्रोकर्सचं hypothetical शुल्क मोजतं."""

    def test_returns_all_four_brokers_even_when_all_orders_are_upstox(self):
        df = _orders_df([
            {"order_id": "O1", "account_id": "acc_upstox", "symbol": "NIFTY", "quantity": 50,
             "transaction_type": "SELL", "fill_price": 100.0},
        ])
        result = charges.compute_hypothetical_charges_by_broker(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert set(result.keys()) == {"upstox", "fyers", "shoonya", "stocko"}
        assert all(v["orders"] == 1 for v in result.values())

    def test_shoonya_is_cheapest_for_options_orders(self):
        """Shoonya चं flat brokerage (₹5) Upstox/Fyers (₹20) पेक्षा कमी आहे -- statutory शुल्क सर्वांना
        सारखेच असल्याने, Options ऑर्डर्ससाठी Shoonya चा एकूण charge सर्वात कमी यायला हवा."""
        df = _orders_df([
            {"order_id": "O1", "symbol": "NIFTY", "quantity": 5000, "transaction_type": "SELL", "fill_price": 100.0},
        ])
        result = charges.compute_hypothetical_charges_by_broker(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert result["shoonya"]["charge"] < result["upstox"]["charge"]
        assert result["shoonya"]["charge"] < result["fyers"]["charge"]

    def test_stocko_includes_prorated_monthly_fee(self):
        df = _orders_df([
            {"order_id": "O1", "symbol": "NIFTY", "quantity": 50, "transaction_type": "BUY", "fill_price": 100.0},
        ])
        result = charges.compute_hypothetical_charges_by_broker(df, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        # सप्टेंबर 2026 पूर्ण महिना (30 दिवस) रेंजमध्ये असल्याने, संपूर्ण STOCKO_FLAT_MONTHLY यायला हवं
        assert result["stocko"]["charge"] > charges.STOCKO_FLAT_MONTHLY * 0.9

    def test_empty_orders_df_returns_empty_dict(self):
        assert charges.compute_hypothetical_charges_by_broker(pd.DataFrame(), datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)) == {}

    def test_ignores_actual_broker_used(self):
        """account_id/broker_type काहीही असो (इथे नाहीच) -- सर्व चार ब्रोकर्ससाठी hypothetical गणित
        सारखंच व्हायला हवं, प्रत्यक्ष वापरलेल्या ब्रोकरशी काही संबंध नाही."""
        df_no_account = _orders_df([
            {"order_id": "O1", "symbol": "NIFTY", "quantity": 50, "transaction_type": "SELL", "fill_price": 100.0},
        ])
        df_with_account = _orders_df([
            {"order_id": "O1", "account_id": "acc_shoonya", "symbol": "NIFTY", "quantity": 50,
             "transaction_type": "SELL", "fill_price": 100.0},
        ])
        r1 = charges.compute_hypothetical_charges_by_broker(df_no_account, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        r2 = charges.compute_hypothetical_charges_by_broker(df_with_account, datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        assert r1["upstox"]["charge"] == pytest.approx(r2["upstox"]["charge"])
        assert r1["shoonya"]["charge"] == pytest.approx(r2["shoonya"]["charge"])


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
