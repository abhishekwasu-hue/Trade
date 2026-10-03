"""tests/test_mcx_quantity_check.py -- MCX LIVE सुरक्षा-गेट (Upstox quantity = units की lots अजून पडताळलेलं नाही)."""
import json

import pytest

import mcx_quantity_check as mqc
import trading_engine


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
        assert json.load(open(tmp_path / "m.json"))["semantics"] == "UNITS"

    def test_corrupt_or_wrong_marker_is_not_verified(self, tmp_path, monkeypatch):
        p = tmp_path / "m.json"
        monkeypatch.setattr(mqc, "MARKER_PATH", str(p))
        p.write_text("{not json")
        assert mqc.is_mcx_live_quantity_verified() is False
        p.write_text(json.dumps({"semantics": "LOTS"}))
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
