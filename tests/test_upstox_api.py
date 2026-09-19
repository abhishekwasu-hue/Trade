"""
tests/test_upstox_api.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Order Fill Verification, गंभीर यादीतला
पहिला मुद्दा) — LIVE multi-leg ऑर्डर प्लेस केल्यावर Upstox चं तात्काळ "200 success" उत्तर फक्त
"स्वीकारला गेला" इतकंच सांगतं, "प्रत्यक्ष भरला गेला" हे नाही. आता प्रत्येक leg चा order_id
GET /v2/order/details ने पोल करून खरी (terminal) स्थिती तपासली जाते.
"""
from unittest.mock import MagicMock, patch

import upstox_api


def _mock_get_response(status_code, data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"data": data}
    return resp


class TestGetOrderDetails:
    def test_returns_data_on_200(self):
        with patch.object(upstox_api, "_get_with_retry", return_value=_mock_get_response(200, {"status": "complete"})):
            result = upstox_api.get_order_details("fake_token", "ORDER1")
        assert result == {"status": "complete"}

    def test_returns_none_on_non_200(self):
        with patch.object(upstox_api, "_get_with_retry", return_value=_mock_get_response(400)):
            result = upstox_api.get_order_details("fake_token", "ORDER1")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch.object(upstox_api, "_get_with_retry", side_effect=Exception("network")):
            result = upstox_api.get_order_details("fake_token", "ORDER1")
        assert result is None


class TestPollOrderFill:
    def test_returns_immediately_on_terminal_status(self):
        with patch.object(upstox_api, "get_order_details", return_value={"status": "complete"}), \
             patch.object(upstox_api.time, "sleep") as mock_sleep:
            result = upstox_api.poll_order_fill("fake_token", "ORDER1")
        assert result == {"status": "complete"}
        assert not mock_sleep.called  # पहिल्याच प्रयत्नात मिळालं, थांबायची गरजच नाही

    def test_retries_until_terminal_status_reached(self):
        responses = [{"status": "open"}, {"status": "open"}, {"status": "complete"}]
        with patch.object(upstox_api, "get_order_details", side_effect=responses), \
             patch.object(upstox_api.time, "sleep"):
            result = upstox_api.poll_order_fill("fake_token", "ORDER1", max_attempts=6, delay_seconds=0.01)
        assert result == {"status": "complete"}

    def test_returns_last_known_status_after_exhausting_attempts(self):
        """अंतिम (terminal) स्थिती वेळेत न मिळाल्यास, शेवटची (अनिश्चित) स्थितीच जशीच्या तशी परत —
        कधीच चुकून 'यशस्वी' गृहीत धरलं जात नाही."""
        with patch.object(upstox_api, "get_order_details", return_value={"status": "open"}), \
             patch.object(upstox_api.time, "sleep"):
            result = upstox_api.poll_order_fill("fake_token", "ORDER1", max_attempts=3, delay_seconds=0.01)
        assert result == {"status": "open"}

    def test_returns_none_when_never_fetched(self):
        with patch.object(upstox_api, "get_order_details", return_value=None), \
             patch.object(upstox_api.time, "sleep"):
            result = upstox_api.poll_order_fill("fake_token", "ORDER1", max_attempts=2, delay_seconds=0.01)
        assert result is None


class TestVerifyAndAnnotateFills:
    def _orders(self):
        return [
            {"instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D", "correlation_id": "C1"},
            {"instrument_token": "PE24300", "transaction_type": "BUY", "quantity": 75, "product": "D", "correlation_id": "C2"},
        ]

    def test_all_complete_marks_success(self):
        resp = {"status": "success", "data": [
            {"order_id": "O1", "correlation_id": "C1"},
            {"order_id": "O2", "correlation_id": "C2"},
        ]}
        with patch.object(upstox_api, "poll_order_fill", return_value={"status": "complete", "filled_quantity": 75, "average_price": 20.0}):
            result = upstox_api._verify_and_annotate_fills("fake_token", self._orders(), resp)
        assert result["status"] == "success"
        assert len(result["verified_legs"]) == 2
        assert all(leg["status"] == "complete" for leg in result["verified_legs"])

    def test_partial_fill_marks_partial_failure(self):
        resp = {"status": "success", "data": [
            {"order_id": "O1", "correlation_id": "C1"},
            {"order_id": "O2", "correlation_id": "C2"},
        ]}

        def side_effect(token, order_id):
            return {"status": "complete"} if order_id == "O1" else {"status": "rejected"}

        with patch.object(upstox_api, "poll_order_fill", side_effect=side_effect):
            result = upstox_api._verify_and_annotate_fills("fake_token", self._orders(), resp)
        assert result["status"] == "partial_failure"
        assert result["errors"]

    def test_none_filled_marks_error(self):
        resp = {"status": "success", "data": [
            {"order_id": "O1", "correlation_id": "C1"},
            {"order_id": "O2", "correlation_id": "C2"},
        ]}
        with patch.object(upstox_api, "poll_order_fill", return_value={"status": "rejected"}):
            result = upstox_api._verify_and_annotate_fills("fake_token", self._orders(), resp)
        assert result["status"] == "error"

    def test_verified_legs_carry_instrument_details_for_reversal(self):
        """auto-reversal (trading_engine.py) साठी लागणारी माहिती — correlation_id वरून जोडलेली,
        response च्या positional क्रमावर विसंबून नाही (Upstox अंतर्गत BUY-आधी-SELL क्रम बदलतो)."""
        resp = {"status": "success", "data": [{"order_id": "O1", "correlation_id": "C1"}]}
        with patch.object(upstox_api, "poll_order_fill", return_value={"status": "complete", "filled_quantity": 75, "average_price": 20.0}):
            result = upstox_api._verify_and_annotate_fills("fake_token", self._orders(), resp)
        leg = result["verified_legs"][0]
        assert leg["instrument_token"] == "PE24400"
        assert leg["transaction_type"] == "SELL"
        assert leg["quantity"] == 75

    def test_non_list_data_left_unchanged(self):
        """PAPER mode चं dict-स्वरूप (verification इथे कधीच येतच नाही, पण सुरक्षिततेसाठी no-op)."""
        resp = {"status": "success", "data": {"order_ids": ["PAPER-1"]}}
        result = upstox_api._verify_and_annotate_fills("fake_token", self._orders(), resp)
        assert result == resp


class TestExecuteOrderLegSetLiveVerification:
    def test_live_success_calls_verification_and_keeps_success(self):
        place_resp = {"status": "success", "data": [{"order_id": "O1", "correlation_id": "C1"}]}
        orders = [{"instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D", "correlation_id": "C1"}]
        with patch.object(upstox_api, "place_multi_leg_order", return_value=(200, place_resp)), \
             patch.object(upstox_api, "poll_order_fill", return_value={"status": "complete"}):
            status_code, resp = upstox_api.execute_order_leg_set("fake_token", orders, "LIVE")
        assert status_code == 200
        assert resp["status"] == "success"
        assert "verified_legs" in resp

    def test_live_partial_fill_downgrades_status(self):
        place_resp = {"status": "success", "data": [
            {"order_id": "O1", "correlation_id": "C1"}, {"order_id": "O2", "correlation_id": "C2"},
        ]}
        orders = [
            {"instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D", "correlation_id": "C1"},
            {"instrument_token": "PE24300", "transaction_type": "BUY", "quantity": 75, "product": "D", "correlation_id": "C2"},
        ]

        def poll_side_effect(token, order_id):
            return {"status": "complete"} if order_id == "O1" else {"status": "rejected"}

        with patch.object(upstox_api, "place_multi_leg_order", return_value=(200, place_resp)), \
             patch.object(upstox_api, "poll_order_fill", side_effect=poll_side_effect):
            status_code, resp = upstox_api.execute_order_leg_set("fake_token", orders, "LIVE")
        assert resp["status"] == "partial_failure"

    def test_live_immediate_failure_skips_verification(self):
        """place_multi_leg_order स्वतःच अयशस्वी (उदा. 400) झाला, तर verification चा प्रश्नच नाही."""
        with patch.object(upstox_api, "place_multi_leg_order", return_value=(400, {"status": "error"})), \
             patch.object(upstox_api, "poll_order_fill") as mock_poll:
            status_code, resp = upstox_api.execute_order_leg_set("fake_token", [{"instrument_token": "X"}], "LIVE")
        assert status_code == 400
        assert not mock_poll.called

    def test_paper_mode_skips_verification_entirely(self):
        with patch.object(upstox_api, "fetch_ltp_map", return_value={"PE24400": 20.0}), \
             patch.object(upstox_api, "poll_order_fill") as mock_poll:
            status_code, resp = upstox_api.execute_order_leg_set(
                "fake_token", [{"instrument_token": "PE24400", "transaction_type": "SELL"}], "PAPER",
            )
        assert status_code == 200
        assert not mock_poll.called
