"""tests/test_mcx_margin.py — "Commodity nusar Required Margin pn dakhwa": mcx_margin.compute_margin_rows()."""
import mcx_margin


def _resolve(token, sym):
    if sym == "BAD":
        return False, "not found"
    return True, {"instrument_key": f"MCX_FO|{sym}", "lot_size": 100, "trading_symbol": f"{sym} FUT 30 OCT 26"}


class TestComputeMarginRows:
    def test_rows_have_buy_sell_total_and_per_lot(self):
        calls = []

        def margin(token, orders):
            calls.append((orders[0]["transaction_type"], orders[0]["quantity"], orders[0]["product"]))
            return 300000.0 if orders[0]["transaction_type"] == "BUY" else 320000.0

        rows = mcx_margin.compute_margin_rows(
            "tok", ["CRUDEOIL"], {"CRUDEOIL": 2}, product="D",
            resolve_fn=_resolve, ltp_fn=lambda t, k: {k[0]: 9000.0}, margin_fn=margin,
        )
        r = rows[0]
        assert r["Lot Size"] == 100 and r["Lots"] == 2 and r["LTP"] == 9000.0
        assert r["Contract Value (Rs)"] == 9000.0 * 200
        assert r["BUY Margin (Rs)"] == 300000.0 and r["SELL Margin (Rs)"] == 320000.0
        assert r["BUY / lot (Rs)"] == 150000.0 and r["SELL / lot (Rs)"] == 160000.0
        assert r["स्थिती"] == "OK"
        assert calls == [("BUY", 200, "D"), ("SELL", 200, "D")]  # qty = lots × lot_size

    def test_missing_margin_stays_none_not_estimated(self):
        rows = mcx_margin.compute_margin_rows(
            "tok", ["GOLD"], {}, resolve_fn=_resolve, ltp_fn=lambda t, k: {k[0]: 150000.0}, margin_fn=lambda t, o: None,
        )
        r = rows[0]
        assert r["Lots"] == 1
        assert r["BUY Margin (Rs)"] is None and r["SELL Margin (Rs)"] is None
        assert "आकडा दिला नाही" in r["स्थिती"]

    def test_unresolved_commodity_reported_and_others_continue(self):
        rows = mcx_margin.compute_margin_rows(
            "tok", ["BAD", "SILVER"], {}, resolve_fn=_resolve, ltp_fn=lambda t, k: {k[0]: 236000.0}, margin_fn=lambda t, o: 100000.0,
        )
        assert "सापडला नाही" in rows[0]["स्थिती"] and rows[0]["BUY Margin (Rs)"] is None
        assert rows[1]["BUY Margin (Rs)"] == 100000.0

    def test_resolver_exception_does_not_stop_others(self):
        def boom(token, sym):
            if sym == "GOLD":
                raise RuntimeError("network")
            return _resolve(token, sym)
        rows = mcx_margin.compute_margin_rows(
            "tok", ["GOLD", "COPPER"], {}, resolve_fn=boom, ltp_fn=lambda t, k: {}, margin_fn=lambda t, o: 5000.0,
        )
        assert "network" in rows[0]["स्थिती"]
        assert rows[1]["BUY Margin (Rs)"] == 5000.0 and rows[1]["LTP"] is None


class TestTotalWorstCaseMargin:
    def test_sums_larger_side_per_commodity(self):
        rows = [
            {"BUY Margin (Rs)": 100.0, "SELL Margin (Rs)": 120.0},
            {"BUY Margin (Rs)": 300.0, "SELL Margin (Rs)": 250.0},
            {"BUY Margin (Rs)": None, "SELL Margin (Rs)": None},
        ]
        assert mcx_margin.total_worst_case_margin(rows) == 420.0

    def test_none_when_no_numbers(self):
        assert mcx_margin.total_worst_case_margin([{"BUY Margin (Rs)": None, "SELL Margin (Rs)": None}]) is None
