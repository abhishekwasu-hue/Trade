"""
tests/test_broker_adapter.py
--------------------------------
🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL", फक्त Upstox पासून सुरुवात) —
BrokerAdapter base class चे नवीन डीफॉल्ट्स (supports_broker_side_stop_loss()==False,
place_stop_loss_order()/cancel_order() raise NotImplementedError) — Shoonya/Stocko/Fyers सारख्या
अजून-सपोर्ट-न-करणाऱ्या brokers साठी काहीही न बदलता, सुरक्षितपणे "unsupported" राहतात याची खात्री.
"""
import pytest

from broker_adapter import BrokerAdapter


class _MinimalAdapter(BrokerAdapter):
    """फक्त abstract methods इम्प्लिमेंट करणारा, established supports_broker_side_stop_loss() override न
    करणारा — डीफॉल्ट वर्तन तपासण्यासाठी."""

    def fetch_ltp_map(self, instrument_keys):
        return {}

    def fetch_option_chain(self, symbol):
        return []

    def fetch_candles(self, symbol, interval, lookback_days):
        return None

    def execute_order_leg_set(self, orders, trading_mode):
        return 200, {"status": "success"}

    def get_funds(self):
        return 100000.0


class TestDefaultBrokerSideStopLossSupport:
    def test_supports_broker_side_stop_loss_defaults_false(self):
        adapter = _MinimalAdapter("fake_token", "acc1")
        assert adapter.supports_broker_side_stop_loss() is False

    def test_place_stop_loss_order_raises_not_implemented(self):
        adapter = _MinimalAdapter("fake_token", "acc1")
        with pytest.raises(NotImplementedError):
            adapter.place_stop_loss_order("NSE_FO|123", 75, "SELL", "D", 123.45)

    def test_cancel_order_raises_not_implemented(self):
        adapter = _MinimalAdapter("fake_token", "acc1")
        with pytest.raises(NotImplementedError):
            adapter.cancel_order("SL-O1")
