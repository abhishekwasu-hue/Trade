"""
tests/test_upstox_broker_adapter.py
--------------------------------------
🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL", फक्त plumbing) —
UpstoxBrokerAdapter.place_stop_loss_order()/cancel_order() (नवीन) — upstox_api.py मधल्याच
place_stop_loss_order()/cancel_order() functions ना योग्य पद्धतीने wrap करतात याची खात्री.
"""
from unittest.mock import patch

import upstox_broker_adapter
from upstox_broker_adapter import UpstoxBrokerAdapter


class TestSupportsBrokerSideStopLoss:
    def test_returns_true(self):
        adapter = UpstoxBrokerAdapter("fake_token", "acc1")
        assert adapter.supports_broker_side_stop_loss() is True


class TestPlaceStopLossOrder:
    def test_success_returns_order_id(self):
        adapter = UpstoxBrokerAdapter("fake_token", "acc1")
        with patch.object(
            upstox_broker_adapter, "place_stop_loss_order",
            return_value=(200, {"status": "success", "data": {"order_id": "SL-O1"}}),
        ) as mock_place:
            order_id = adapter.place_stop_loss_order("NSE_FO|123", 75, "SELL", "D", 123.45)
        assert order_id == "SL-O1"
        mock_place.assert_called_once_with("fake_token", "NSE_FO|123", 75, "SELL", "D", 123.45)

    def test_failure_returns_none(self):
        adapter = UpstoxBrokerAdapter("fake_token", "acc1")
        with patch.object(
            upstox_broker_adapter, "place_stop_loss_order",
            return_value=(400, {"status": "error", "errors": [{"message": "insufficient margin"}]}),
        ):
            order_id = adapter.place_stop_loss_order("NSE_FO|123", 75, "SELL", "D", 123.45)
        assert order_id is None

    def test_network_error_returns_none_not_raise(self):
        adapter = UpstoxBrokerAdapter("fake_token", "acc1")
        with patch.object(
            upstox_broker_adapter, "place_stop_loss_order",
            return_value=(None, {"error": "connection failed"}),
        ):
            order_id = adapter.place_stop_loss_order("NSE_FO|123", 75, "SELL", "D", 123.45)
        assert order_id is None


class TestCancelOrder:
    def test_success_returns_true(self):
        adapter = UpstoxBrokerAdapter("fake_token", "acc1")
        with patch.object(upstox_broker_adapter, "cancel_order", return_value=(200, {"status": "success"})) as mock_cancel:
            result = adapter.cancel_order("SL-O1")
        assert result is True
        mock_cancel.assert_called_once_with("fake_token", "SL-O1")

    def test_failure_returns_false(self):
        adapter = UpstoxBrokerAdapter("fake_token", "acc1")
        with patch.object(upstox_broker_adapter, "cancel_order", return_value=(400, {"status": "error"})):
            result = adapter.cancel_order("SL-O1")
        assert result is False
