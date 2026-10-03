"""tests/test_mcx_quantity_check.py -- MCX LIVE सुरक्षा-गेट (Upstox quantity = units की lots अजून पडताळलेलं नाही)."""
import json

import pytest

import mcx_quantity_check as mqc
import trading_engine
from tests.test_trading_engine import temp_db  # noqa: F401  (fixture)


class TestClassify:
    def test_units_when_margin_is_a_small_fraction_of_one_lot_value(self):
        # SILVER: 1 lot ≈ ₹67.7 लाख, margin ≈ ₹8.6 लाख (≈12.8%)
        assert mqc.classify_quantity_semantics(863859.38, 30 * 225545) == "UNITS"

    def test_lots_when_margin_exceeds_one_lot_value(self):
        # quantity=30 ला "30 lots" मानल्यास margin ≈ 30 × 8.6 लाख = ₹2.6 कोटी > 1 lot च्या value (₹67.7 लाख)
        assert mqc.classify_quantity_semantics(30 * 863859.38, 30 * 225545) == "LOTS"

    @pytest.mark.parametrize("margin,value", [(None, 100.0), (0, 100.0), (100.0, 0), ("x", 5), (80.0, 100.0)])
    def test_unknown_for_bad_or_ambiguous_numbers(self, margin, value):
        assert mqc.classify_quantity_semantics(margin, value) == "UNKNOWN"


class TestMarker:
    def test_not_verified_without_marker(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mqc, "MARKER_PATH", str(tmp_path / "m.json"))
        assert mqc.is_mcx_live_quantity_verified() is False

    def test_verified_after_write(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mqc, "MARKER_PATH", str(tmp_path / "m.json"))
        monkeypatch.setattr(mqc, "DATA_DIR", str(tmp_path))
        mqc.write_verified_marker([{"symbol": "SILVER"}])
        assert mqc.is_mcx_live_quantity_verified() is True
        assert json.load(open(tmp_path / "m.json"))["semantics"] == "LOTS"

    def test_corrupt_or_wrong_marker_is_not_verified(self, tmp_path, monkeypatch):
        p = tmp_path / "m.json"
        monkeypatch.setattr(mqc, "MARKER_PATH", str(p))
        p.write_text("{not json")
        assert mqc.is_mcx_live_quantity_verified() is False
        p.write_text(json.dumps({"semantics": "UNITS"}))
        assert mqc.is_mcx_live_quantity_verified() is False


class TestEngineGate:
    def _call(self, trading_mode, source):
        legs = {"legs": [{"role": "F", "strike": 0, "instrument_key": "MCX_FO|X", "transaction_type": "SELL"}],
                "net_credit": 0.0, "max_profit": 0.0, "max_loss": 0.0, "strategy": "FUTURES_SHORT", "is_credit_strategy": True}
        return trading_engine.open_multi_leg_trade(
            "tok", "SILVER", legs, 1, 30, None, None, "D", trading_mode=trading_mode, source=source,
        )

    def test_mcx_live_refused_until_verified(self, monkeypatch):
        monkeypatch.setattr(trading_engine, "is_mcx_live_quantity_verified", lambda: False)
        sent = []
        monkeypatch.setattr("notifications.send_telegram_message", lambda m, *a, **k: sent.append(m))
        ok, resp = self._call("LIVE", "mcx_futures")
        assert ok is False and "units/lots" in resp["reason"]
        assert sent and "LIVE order अडवला" in sent[0]

    def test_gate_does_not_apply_to_paper_or_other_sources(self, monkeypatch):
        monkeypatch.setattr(trading_engine, "is_mcx_live_quantity_verified", lambda: False)
        for mode, source in (("PAPER", "mcx_futures"), ("LIVE", "dynamic_sr_instant")):
            try:
                ok, resp = self._call(mode, source)
            except Exception:
                continue  # पुढच्या (असंबंधित) mock-विरहित भागात अडकलं तरी चालेल — गेटचा संदेश नसणं हेच तपासतो
            assert "units/lots" not in str((resp or {}).get("reason", ""))


class TestBrokerQuantityIsLotsForMcx:
    """Upstox MCX `quantity` = lots (VPS Margin API ने पडताळलेलं: SILVER quantity=30 => 30 lots)."""

    def test_broker_order_quantity_prefers_broker_quantity(self):
        import upstox_api
        assert upstox_api.broker_order_quantity({"quantity": 30, "broker_quantity": 1}) == 1
        assert upstox_api.broker_order_quantity({"quantity": 75}) == 75

    def test_upstox_json_body_sends_lots_and_drops_helper_key(self, monkeypatch):
        import upstox_api
        sent = {}

        class R:
            status_code = 200
            text = "{}"

            def json(self):
                return {"status": "success"}

        monkeypatch.setattr(upstox_api, "_post_with_retry_429_only", lambda url, **kw: sent.update(kw) or R())
        orders = [{"quantity": 30, "broker_quantity": 1, "instrument_token": "MCX_FO|S", "transaction_type": "SELL"}]
        upstox_api.place_multi_leg_order("tok", orders)
        body = sent["json"]
        assert body[0]["quantity"] == 1 and "broker_quantity" not in body[0]
        assert orders[0]["quantity"] == 30 and orders[0]["broker_quantity"] == 1  # caller चे orders (log/charges) अबाधित

    def test_margin_api_gets_lots(self, monkeypatch):
        import upstox_api
        sent = {}

        class R:
            status_code = 200

            def json(self):
                return {"data": {"required_margin": 863859.0}}

        monkeypatch.setattr(upstox_api, "_post_with_retry_429_only", lambda url, **kw: sent.update(kw) or R())
        m = upstox_api.fetch_required_margin("tok", [{"quantity": 30, "broker_quantity": 1, "instrument_token": "K", "transaction_type": "BUY"}])
        assert m == 863859.0 and sent["json"]["instruments"][0]["quantity"] == 1

    def _mcx_result(self):
        return {"strategy": "MCX_FUTURES", "max_loss": 500, "max_profit": 500, "net_credit": 0,
                "legs": [{"role": "futures_leg", "strike": 0, "instrument_key": "MCX_FUT_1", "transaction_type": "SELL",
                          "option_type": None, "expiry": "2026-12-04"}]}

    def test_mcx_entry_order_carries_lots_for_broker_and_units_for_log(self, temp_db, monkeypatch):
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        monkeypatch.setattr(trading_engine, "check_mcx_kill_switch", lambda: (True, None))
        seen = []
        monkeypatch.setattr(trading_engine, "execute_order_leg_set",
                            lambda t, o, m: seen.extend(o) or (200, {"status": "success", "data": [{"order_ids": ["LIVE-1"]}]}))
        ok, _ = trading_engine.open_multi_leg_trade(
            "tok", "SILVER", self._mcx_result(), lots=2, lot_size=30, sl_pct_of_max_loss=100, target_pct_of_max_profit=100,
            product_type="D", trading_mode="LIVE", source="mcx_futures",
        )
        assert ok is True
        assert seen[0]["quantity"] == 60 and seen[0]["broker_quantity"] == 2  # units (log/charges) vs lots (broker)

    def test_non_mcx_entry_order_has_no_broker_quantity(self, temp_db, monkeypatch):
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        seen = []
        monkeypatch.setattr(trading_engine, "execute_order_leg_set",
                            lambda t, o, m: seen.extend(o) or (200, {"status": "success", "data": [{"order_ids": ["LIVE-1"]}]}))
        from tests.test_trading_engine import TestOpenMultiLegTradeKillSwitch
        trading_engine.open_multi_leg_trade(
            "tok", "NIFTY", TestOpenMultiLegTradeKillSwitch()._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE", source="dynamic_sr_instant",
        )
        assert seen and "broker_quantity" not in seen[0] and seen[0]["quantity"] == 75

    def test_other_broker_adapter_refused_for_mcx_live(self, temp_db, monkeypatch):
        monkeypatch.setattr(trading_engine, "is_mcx_live_quantity_verified", lambda: True)

        class FyersBrokerAdapter:
            pass

        ok, resp = trading_engine.open_multi_leg_trade(
            "tok", "SILVER", self._mcx_result(), lots=1, lot_size=30, sl_pct_of_max_loss=100, target_pct_of_max_profit=100,
            product_type="D", trading_mode="LIVE", source="mcx_futures", adapter=FyersBrokerAdapter(),
        )
        assert ok is False and "दुसऱ्या broker" in resp["reason"]


class TestVerifyScript:
    def _run(self, monkeypatch, tmp_path, margins, ltp=100000.0):
        import verify_mcx_order_quantity_units as v
        monkeypatch.setattr(mqc, "MARKER_PATH", str(tmp_path / "m.json"))
        monkeypatch.setattr(mqc, "DATA_DIR", str(tmp_path))
        monkeypatch.setattr(v, "MARKER_PATH", str(tmp_path / "m.json"))
        monkeypatch.setattr(v.cloud_db, "get_effective_upstox_token", lambda t: "tok")
        lots = {"SILVER": 30, "GOLD": 1, "CRUDEOIL": 100}
        monkeypatch.setattr(v.resolver, "resolve_symbol", lambda tok, s: (True, {"instrument_key": f"K_{s}", "lot_size": lots[s]}))
        monkeypatch.setattr(v, "fetch_ltp_map", lambda tok, keys: {keys[0]: ltp})
        monkeypatch.setattr(v, "fetch_required_margin", lambda tok, orders: margins(orders[0]["instrument_token"][2:], orders[0]["quantity"], ltp))
        monkeypatch.setattr("sys.argv", ["x"])
        try:
            v.main()
            return 0
        except SystemExit as e:
            return e.code

    def test_lots_semantics_writes_marker(self, tmp_path, monkeypatch):
        def lots_margin(sym, qty, ltp):  # quantity = lots: 1 lot ≈ 12% of (lot_size × भाव)
            size = {"SILVER": 30, "GOLD": 1, "CRUDEOIL": 100}[sym]
            return qty * size * ltp * 0.12
        assert self._run(monkeypatch, tmp_path, lots_margin) == 0
        assert mqc.is_mcx_live_quantity_verified() is True

    def test_units_semantics_refuses_and_writes_nothing(self, tmp_path, monkeypatch):
        def units_margin(sym, qty, ltp):  # quantity = units: margin ∝ qty × भाव × 12%
            return qty * ltp * 0.12
        assert self._run(monkeypatch, tmp_path, units_margin) == 2
        assert mqc.is_mcx_live_quantity_verified() is False

    def test_unknown_when_margin_missing(self, tmp_path, monkeypatch):
        assert self._run(monkeypatch, tmp_path, lambda s, q, p: None) == 3
        assert mqc.is_mcx_live_quantity_verified() is False


def test_manual_close_of_mcx_trade_sends_lots_to_broker(temp_db, monkeypatch):
    from tests.test_trading_engine import seed_trade
    legs = [{"role": "futures_short", "strike": 0, "instrument_key": "FUT1", "transaction_type": "SELL"}]
    seed_trade(temp_db, "MC1", net_credit=226697.0, sl_level=-1e9, target_level=1e9, strategy="MCX_FUTURES_SHORT",
               source="mcx_futures", legs=legs, mode="LIVE")
    sent = []
    monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"FUT1": 226400.0})
    monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (sent.extend(o) or 200, {"status": "success"}))
    trading_engine.close_trade_manually("tok", "MC1", "SILVER", "D")
    assert sent and sent[0]["broker_quantity"] == 1 and sent[0]["quantity"] == 75  # seed lots=1, lot_size=75
