"""
tests/test_upstox_api.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Order Fill Verification, गंभीर यादीतला
पहिला मुद्दा) — LIVE multi-leg ऑर्डर प्लेस केल्यावर Upstox चं तात्काळ "200 success" उत्तर फक्त
"स्वीकारला गेला" इतकंच सांगतं, "प्रत्यक्ष भरला गेला" हे नाही. आता प्रत्येक leg चा order_id
GET /v2/order/details ने पोल करून खरी (terminal) स्थिती तपासली जाते.
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest

import upstox_api


def _mock_get_response(status_code, data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"data": data}
    return resp


class TestFetchLtpMapDetailed:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Token-Expiry/LTP-Fetch Silent Failure,
    गंभीर यादीतला तिसरा मुद्दा) — fetch_ltp_map_detailed() ने अयशस्वी झाल्यास नेमकं कारण
    (उदा. "HTTP 401") caller ला कळवायला हवं, fetch_ltp_map() (जुनं, backward-compatible) ने
    कधीच न बदलता तेच behavior द्यायला हवं."""

    def test_success_returns_data_and_none_error(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"NSE_INDEX:Nifty 50": {"instrument_token": "NSE_INDEX|Nifty 50", "last_price": 24000.5}}}
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result, error = upstox_api.fetch_ltp_map_detailed("fake_token", ["NSE_INDEX|Nifty 50"])
        assert result == {"NSE_INDEX|Nifty 50": 24000.5}
        assert error is None

    def test_401_returns_empty_dict_and_error_detail(self):
        resp = MagicMock()
        resp.status_code = 401
        resp.text = "Unauthorized: token expired"
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result, error = upstox_api.fetch_ltp_map_detailed("fake_token", ["PE24400"])
        assert result == {}
        assert "401" in error

    def test_exception_returns_empty_dict_and_error_detail(self):
        with patch.object(upstox_api, "_get_with_retry", side_effect=Exception("connection reset")):
            result, error = upstox_api.fetch_ltp_map_detailed("fake_token", ["PE24400"])
        assert result == {}
        assert "connection reset" in error

    def test_empty_instrument_keys_returns_empty_no_error(self):
        result, error = upstox_api.fetch_ltp_map_detailed("fake_token", [])
        assert result == {}
        assert error is None

    def test_missing_last_price_key_is_omitted_not_zero(self):
        """🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — एखाद्या leg साठी
        response मध्ये "last_price" key च गहाळ असेल (अपुरा/चुकीचा प्रतिसाद), तर ती किंमत 0.0 म्हणून
        गृहीत धरली जाऊ नये (SELL leg साठी हे current_pnl खोटं जास्त दाखवून चुकीचा Target-exit घडवू
        शकतं) — त्याऐवजी result dict मधून ती key अजिबात गाळली जायला हवी (म्हणजे .get() कडून None
        मिळेल, आणि manage_open_trades() चा "LTP मिळाली नाही" guard योग्यरित्या कार्यान्वित होईल)."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {
            "NSE_FO:PE24400": {"instrument_token": "PE24400"},  # last_price key च नाही
            "NSE_FO:PE24300": {"instrument_token": "PE24300", "last_price": 27.5},
        }}
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result, error = upstox_api.fetch_ltp_map_detailed("fake_token", ["PE24400", "PE24300"])
        assert "PE24400" not in result  # गहाळ key -- .get() कडून None मिळेल
        assert result["PE24300"] == 27.5

    def test_genuine_zero_last_price_is_kept_as_zero(self):
        """खरोखर last_price=0 दिलेला असेल (उदा. worthless deep-OTM contract), तर तो legitimate
        शून्य म्हणूनच वापरायला हवा -- गहाळ data सारखा गाळला जाऊ नये."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"NSE_FO:PE24000": {"instrument_token": "PE24000", "last_price": 0}}}
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result, error = upstox_api.fetch_ltp_map_detailed("fake_token", ["PE24000"])
        assert result["PE24000"] == 0.0

    def test_fetch_ltp_map_backward_compatible_success(self):
        with patch.object(upstox_api, "fetch_ltp_map_detailed", return_value=({"PE24400": 20.0}, None)):
            result = upstox_api.fetch_ltp_map("fake_token", ["PE24400"])
        assert result == {"PE24400": 20.0}

    def test_fetch_ltp_map_backward_compatible_failure_returns_empty_dict_only(self):
        """जुनंच वर्तन — fetch_ltp_map() ला अयशस्वी झाल्यास फक्त रिकामा dict, error_detail कधीच दिसत नाही."""
        with patch.object(upstox_api, "fetch_ltp_map_detailed", return_value=({}, "HTTP 401: ...")):
            result = upstox_api.fetch_ltp_map("fake_token", ["PE24400"])
        assert result == {}


class TestGetTotalCapital:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Kill Switch — Loss/Profit % एकूण capital च्या सापेक्ष) —
    get_total_capital() = available_margin + used_margin (Upstox Funds & Margin API, equity
    segment) — नुसता available_margin नाही, कारण तो उघड्या positions मुळे दिवसभर कमी-जास्त होतो."""

    def setup_method(self):
        upstox_api.get_total_capital.clear()

    def test_sums_available_and_used_margin(self):
        resp = _mock_get_response(200, {"equity": {"available_margin": 150000.0, "used_margin": 850000.0}})
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result = upstox_api.get_total_capital("fake_token")
        assert result == 1000000.0

    def test_missing_used_margin_defaults_to_zero(self):
        resp = _mock_get_response(200, {"equity": {"available_margin": 150000.0}})
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result = upstox_api.get_total_capital("fake_token")
        assert result == 150000.0

    def test_non_200_returns_none(self):
        resp = _mock_get_response(401)
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result = upstox_api.get_total_capital("fake_token")
        assert result is None

    def test_exception_returns_none_not_raised(self):
        with patch.object(upstox_api, "_get_with_retry", side_effect=Exception("connection reset")):
            result = upstox_api.get_total_capital("fake_token")
        assert result is None


class TestVerifyTokenLive:
    """🎓 वापरकर्त्याने रागाने, पण अगदी बरोबर दुरुस्त केलेला मुद्दा — "मोबाईलवर Approve करूनही 401
    चालूच" या तक्रारीचं मूळ localize करण्यासाठी जोडलेलं फंक्शन — Supabase मधली वेळ (freshness) नाही,
    तर प्रत्यक्ष Upstox कडून token स्वीकारला जातो का हे थेट तपासतं."""

    def test_empty_token_returns_false_without_network_call(self):
        with patch.object(upstox_api.requests, "get") as mock_get:
            is_valid, detail = upstox_api.verify_token_live("")
        assert is_valid is False
        assert "रिकामा" in detail
        mock_get.assert_not_called()

    def test_valid_token_returns_true_on_200(self):
        with patch.object(upstox_api.requests, "get", return_value=_mock_get_response(200, {})):
            is_valid, detail = upstox_api.verify_token_live("fake_token")
        assert is_valid is True
        assert "वैध" in detail

    def test_expired_token_returns_false_on_401(self):
        with patch.object(upstox_api.requests, "get", return_value=_mock_get_response(401, {})):
            is_valid, detail = upstox_api.verify_token_live("stale_token")
        assert is_valid is False
        assert "401" in detail

    def test_unexpected_status_returns_false_with_code(self):
        with patch.object(upstox_api.requests, "get", return_value=_mock_get_response(500, {})):
            is_valid, detail = upstox_api.verify_token_live("fake_token")
        assert is_valid is False
        assert "500" in detail

    def test_connection_exception_returns_false_not_raised(self):
        with patch.object(upstox_api.requests, "get", side_effect=ConnectionError("boom")):
            is_valid, detail = upstox_api.verify_token_live("fake_token")
        assert is_valid is False
        assert "जोडणी" in detail


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

    def test_still_pending_leg_after_timeout_fires_urgent_alert(self):
        """🎓 पूर्व-live रिव्ह्यूत सापडवलेली, गंभीर bug — poll_order_fill() ने terminal status
        मिळण्याआधीच वेळ संपली (status="open", कधीच rejected/cancelled/complete नाही) तर तो leg
        "भरलाच नाही" (rejected सारखाच) समजला जायचा -- पण खरा order अजूनही pending असून क्षणभरात
        भरला जाऊ शकतो, म्हणजे एक untracked (कधीच live_trades मध्ये न नोंदवलेली) real position उरू
        शकते. आता अशा genuinely-uncertain (confirmed rejected/cancelled पेक्षा वेगळ्या) स्थितीसाठी
        वेगळा, तातडीचा अलर्ट यायलाच हवा."""
        resp = {"status": "success", "data": [
            {"order_id": "O1", "correlation_id": "C1"},
            {"order_id": "O2", "correlation_id": "C2"},
        ]}

        def side_effect(token, order_id):
            return {"status": "complete"} if order_id == "O1" else {"status": "open"}  # O2 कधीच terminal झाला नाही

        with patch.object(upstox_api, "poll_order_fill", side_effect=side_effect), \
             patch("notifications.send_telegram_message") as mock_telegram:
            result = upstox_api._verify_and_annotate_fills("fake_token", self._orders(), resp)
        assert mock_telegram.called
        alert_text = mock_telegram.call_args.args[0]
        assert "O2" in alert_text
        assert "तातडीचं" in alert_text
        assert "O1" not in alert_text  # confirmed complete leg अलर्टमध्ये नसावा
        # business-logic classification अबाधित (partial_failure, जुनंच वर्तन) -- फक्त जोडलेला अलर्ट
        assert result["status"] == "partial_failure"

    def test_all_legs_confirmed_terminal_does_not_fire_urgent_alert(self):
        """दोन्ही legs confirmed terminal (complete/rejected) असतील -- खरंच अनिश्चित काहीच नाही --
        तर तातडीचा अलर्ट यायलाच नको (false-positive टाळण्यासाठी)."""
        resp = {"status": "success", "data": [
            {"order_id": "O1", "correlation_id": "C1"},
            {"order_id": "O2", "correlation_id": "C2"},
        ]}

        def side_effect(token, order_id):
            return {"status": "complete"} if order_id == "O1" else {"status": "rejected"}

        with patch.object(upstox_api, "poll_order_fill", side_effect=side_effect), \
             patch("notifications.send_telegram_message") as mock_telegram:
            upstox_api._verify_and_annotate_fills("fake_token", self._orders(), resp)
        assert not mock_telegram.called


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


def _mock_post_response(status_code, retry_after=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"Retry-After": retry_after} if retry_after else {}
    return resp


class TestPostWithRetry429Only:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Rate Limiting on Order Placement, दुय्यम
    🟡 यादीतला मुद्दा) — वापरकर्त्याशी चर्चा करून ठरवलेला, जाणीवपूर्वक अरुंद निर्णय: **फक्त** HTTP 429
    वर retry (order कधीच place झालाच नाही, त्यामुळे सुरक्षित) — 502/503/504 किंवा network exception
    वर कधीच नाही (order प्रत्यक्ष place झाला की नाही याबद्दल संदिग्धता, duplicate-order धोका)."""

    def test_200_returns_immediately_no_retry(self):
        with patch.object(upstox_api.time, "sleep") as mock_sleep, \
             patch.object(upstox_api.requests, "post", return_value=_mock_post_response(200)) as mock_post:
            res = upstox_api._post_with_retry_429_only("https://fake.url")
        assert res.status_code == 200
        assert mock_post.call_count == 1
        assert not mock_sleep.called

    def test_429_retries_then_succeeds(self):
        responses = [_mock_post_response(429), _mock_post_response(429), _mock_post_response(200)]
        with patch.object(upstox_api.time, "sleep"), \
             patch.object(upstox_api.requests, "post", side_effect=responses) as mock_post:
            res = upstox_api._post_with_retry_429_only("https://fake.url", max_retries=3)
        assert res.status_code == 200
        assert mock_post.call_count == 3

    def test_429_exhausts_retries_returns_last_429(self):
        with patch.object(upstox_api.time, "sleep"), \
             patch.object(upstox_api.requests, "post", return_value=_mock_post_response(429)) as mock_post:
            res = upstox_api._post_with_retry_429_only("https://fake.url", max_retries=2)
        assert res.status_code == 429
        assert mock_post.call_count == 3  # पहिला प्रयत्न + 2 retries

    def test_502_never_retried(self):
        """order प्रत्यक्ष place झाला की नाही अस्पष्ट राहू शकतं (Upstox च्या सर्व्हरपर्यंत पोहोचलं) —
        त्यामुळे 502/503/504 वर कधीच retry नाही (duplicate-order धोका टाळण्यासाठी)."""
        with patch.object(upstox_api.time, "sleep") as mock_sleep, \
             patch.object(upstox_api.requests, "post", return_value=_mock_post_response(502)) as mock_post:
            res = upstox_api._post_with_retry_429_only("https://fake.url")
        assert res.status_code == 502
        assert mock_post.call_count == 1
        assert not mock_sleep.called

    def test_network_exception_propagates_immediately_no_retry(self):
        """network timeout/connection error -- order खरंच पोहोचला की नाही अस्पष्ट, त्यामुळे कधीच
        retry नाही -- exception जशीच्या तशी caller कडे जायलाच हवी."""
        import requests as _requests
        with patch.object(upstox_api.time, "sleep") as mock_sleep, \
             patch.object(upstox_api.requests, "post", side_effect=_requests.exceptions.Timeout("timed out")) as mock_post:
            with pytest.raises(_requests.exceptions.Timeout):
                upstox_api._post_with_retry_429_only("https://fake.url")
        assert mock_post.call_count == 1
        assert not mock_sleep.called

    def test_retry_after_header_used_when_present(self):
        responses = [_mock_post_response(429, retry_after="7"), _mock_post_response(200)]
        with patch.object(upstox_api.time, "sleep") as mock_sleep, \
             patch.object(upstox_api.requests, "post", side_effect=responses):
            upstox_api._post_with_retry_429_only("https://fake.url")
        mock_sleep.assert_called_once_with(7.0)


class TestPlaceMultiLegOrderUsesRetry429Only:
    def test_place_multi_leg_order_recovers_from_transient_429(self):
        orders = [{"instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D"}]
        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {"status": "success", "data": [{"order_id": "O1"}]}
        with patch.object(upstox_api.time, "sleep"), \
             patch.object(upstox_api.requests, "post", side_effect=[_mock_post_response(429), success_resp]):
            status_code, body = upstox_api.place_multi_leg_order("fake_token", orders)
        assert status_code == 200
        assert body["status"] == "success"


class TestPlaceStopLossOrder:
    """🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL", फक्त plumbing — अजून
    कुठल्याही live entry/exit flow मधून कॉल होत नाही)."""

    def test_success_sends_sl_m_order_type_and_returns_order_id(self):
        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {"status": "success", "data": {"order_id": "SL-O1"}}
        with patch.object(upstox_api, "_post_with_retry_429_only", return_value=success_resp) as mock_post:
            status_code, body = upstox_api.place_stop_loss_order(
                "fake_token", "NSE_FO|12345", 75, "SELL", "D", trigger_price=123.45,
            )
        assert status_code == 200
        assert body["data"]["order_id"] == "SL-O1"
        sent_body = mock_post.call_args.kwargs["json"]
        assert sent_body["order_type"] == "SL-M"
        assert sent_body["trigger_price"] == 123.45
        assert sent_body["transaction_type"] == "SELL"
        assert sent_body["quantity"] == 75
        assert sent_body["instrument_token"] == "NSE_FO|12345"

    def test_network_exception_returns_error_dict_not_raise(self):
        import requests as _requests
        with patch.object(upstox_api, "_post_with_retry_429_only", side_effect=_requests.exceptions.ConnectionError("boom")):
            status_code, body = upstox_api.place_stop_loss_order("fake_token", "NSE_FO|12345", 75, "SELL", "D", 123.45)
        assert status_code is None
        assert "error" in body

    def test_correlation_id_defaults_to_generated_when_not_given(self):
        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {"status": "success", "data": {"order_id": "SL-O1"}}
        with patch.object(upstox_api, "_post_with_retry_429_only", return_value=success_resp) as mock_post:
            upstox_api.place_stop_loss_order("fake_token", "NSE_FO|12345", 75, "SELL", "D", 123.45)
        sent_body = mock_post.call_args.kwargs["json"]
        assert sent_body["correlation_id"]  # रिकामं नाही


class TestCancelOrder:
    def test_success_returns_200_and_success_status(self):
        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {"status": "success"}
        with patch.object(upstox_api.requests, "delete", return_value=success_resp) as mock_delete:
            status_code, body = upstox_api.cancel_order("fake_token", "SL-O1")
        assert status_code == 200
        assert body["status"] == "success"
        assert "order_id=SL-O1" in mock_delete.call_args.args[0]

    def test_retries_on_429_then_succeeds(self):
        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {"status": "success"}
        with patch.object(upstox_api.time, "sleep"), \
             patch.object(upstox_api.requests, "delete", side_effect=[_mock_post_response(429), success_resp]):
            status_code, body = upstox_api.cancel_order("fake_token", "SL-O1")
        assert status_code == 200
        assert body["status"] == "success"

    def test_network_exception_returns_error_dict_not_raise(self):
        import requests as _requests
        with patch.object(upstox_api.requests, "delete", side_effect=_requests.exceptions.ConnectionError("boom")):
            status_code, body = upstox_api.cancel_order("fake_token", "SL-O1")
        assert status_code is None
        assert "error" in body


class TestFetchIndiaVix:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (India VIX Spike Halt) — fetch_india_vix() सध्याचा
    LTP मिळवतं (established v3/market-quote/ltp, established 30-सेकंद cache)."""

    def setup_method(self):
        upstox_api.fetch_india_vix.clear()

    def test_success_returns_last_price(self):
        resp = _mock_get_response(200, {"NSE_INDEX:India VIX": {"instrument_token": "NSE_INDEX|India VIX", "last_price": 13.45}})
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result = upstox_api.fetch_india_vix("fake_token")
        assert result == 13.45

    def test_non_200_returns_none(self):
        resp = _mock_get_response(401)
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result = upstox_api.fetch_india_vix("fake_token")
        assert result is None

    def test_exception_returns_none_not_raised(self):
        with patch.object(upstox_api, "_get_with_retry", side_effect=Exception("connection reset")):
            result = upstox_api.fetch_india_vix("fake_token")
        assert result is None


class TestFetchIndiaVixPrevClose:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("आदल्या दिवसाचा close vs 9:20 चा VIX, threshold
    5%") — fetch_india_vix_prev_close() आदल्या ट्रेडिंग दिवसाचा close historical-candle API ने
    मिळवतं (weekend/सुट्टी ओलांडण्यासाठी 7-दिवसांची विंडो, Upstox सर्वात अलीकडचा candle आधी देतो)."""

    def test_success_returns_most_recent_candle_close(self):
        candles = [
            [ "2026-09-23T00:00:00+05:30", 13.0, 13.8, 12.9, 13.45, 0, 0],  # सर्वात अलीकडचा (आधी)
            [ "2026-09-22T00:00:00+05:30", 12.5, 13.1, 12.3, 12.9, 0, 0],
        ]
        resp = _mock_get_response(200, {"candles": candles})
        with patch.object(upstox_api, "_get_with_retry", return_value=resp) as mock_get:
            result = upstox_api.fetch_india_vix_prev_close("fake_token")
        assert result == 13.45
        url = mock_get.call_args.args[0]
        assert "historical-candle" in url
        assert "NSE_INDEX%7CIndia%20VIX" in url or "NSE_INDEX|India VIX" in url

    def test_empty_candles_returns_none(self):
        resp = _mock_get_response(200, {"candles": []})
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result = upstox_api.fetch_india_vix_prev_close("fake_token")
        assert result is None

    def test_non_200_returns_none(self):
        resp = _mock_get_response(401)
        with patch.object(upstox_api, "_get_with_retry", return_value=resp):
            result = upstox_api.fetch_india_vix_prev_close("fake_token")
        assert result is None

    def test_exception_returns_none_not_raised(self):
        with patch.object(upstox_api, "_get_with_retry", side_effect=Exception("connection reset")):
            result = upstox_api.fetch_india_vix_prev_close("fake_token")
        assert result is None


class TestFetchCandlesDateRange:
    """🎓 वापरकर्त्याने सापडवलेली bug (Performance Report PDF च्या Trade Charts मध्ये सर्वच trades
    साठी "candle data unavailable" — token बरोबर असूनही) — मूळ कारण `while chunk_end > from_date`
    होता: intraday trade (entry+exit एकाच दिवशी, म्हणजे from_date == to_date) साठी हा पहिलाच check
    False ठरून loop कधीच चालायचाच नाही, कुठलाही API कॉल न होता रिकामा DataFrame मिळायचा."""

    def _candle_row(self, ts="2026-09-24T09:20:00+05:30"):
        return [ts, 100.0, 105.0, 98.0, 102.0, 1000, 0]

    def test_same_day_range_still_fetches_one_chunk(self):
        """entry_dt.date() == exit_dt.date() (सर्वसामान्य intraday trade) — आधी इथेच रिकामा DataFrame
        मिळायचा, आता किमान एक chunk मागवला जातो."""
        same_day = datetime.date(2026, 9, 24)
        resp = _mock_get_response(200, {"candles": [self._candle_row()]})
        with patch.object(upstox_api.requests, "get", return_value=resp) as mock_get:
            df = upstox_api.fetch_candles_date_range("fake_token", "NIFTY", "5minute", same_day, same_day)
        mock_get.assert_called_once()
        assert not df.empty
        assert len(df) == 1

    def test_multi_day_range_unaffected(self):
        """आधीपासूनच बरोबर काम करणारा multi-day case — fix मुळे मोडलेला नाही, अजूनही एकाच
        iteration मध्ये संपूर्ण रेंज मागवली जाते."""
        from_date = datetime.date(2026, 9, 20)
        to_date = datetime.date(2026, 9, 24)
        resp = _mock_get_response(200, {"candles": [self._candle_row(), self._candle_row("2026-09-23T09:20:00+05:30")]})
        with patch.object(upstox_api.requests, "get", return_value=resp) as mock_get:
            df = upstox_api.fetch_candles_date_range("fake_token", "NIFTY", "5minute", from_date, to_date)
        mock_get.assert_called_once()
        assert len(df) == 2

    def test_no_candles_returns_empty_df_with_expected_columns(self):
        same_day = datetime.date(2026, 9, 24)
        resp = _mock_get_response(200, {"candles": []})
        with patch.object(upstox_api.requests, "get", return_value=resp):
            df = upstox_api.fetch_candles_date_range("fake_token", "NIFTY", "5minute", same_day, same_day)
        assert df.empty
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume", "oi"]


class TestFetchCandlesDateRangeByInstrumentKey:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("ट्रेड घेण्यात आलेल्या option strike चाही चार्ट, एन्ट्री/एक्झिट
    सकट, PDF Report मध्ये हवा") — get_instrument_key(symbol) फक्त ठराविक index/commodity नावांसाठीच
    काम करतं (option instrument_key दिला तर चुकून NIFTY कडे परत जातं), त्यामुळे हे वेगळं फंक्शन आधीच
    resolved raw instrument_key थेट वापरतं -- कुठलाही चुकीचा silent fallback नाही."""

    def _candle_row(self, ts="2026-09-24T09:20:00+05:30"):
        return [ts, 38.0, 40.0, 14.0, 15.0, 500, 0]

    def test_uses_given_instrument_key_directly_not_symbol_lookup(self):
        same_day = datetime.date(2026, 9, 24)
        resp = _mock_get_response(200, {"candles": [self._candle_row()]})
        with patch.object(upstox_api.requests, "get", return_value=resp) as mock_get:
            df = upstox_api.fetch_candles_date_range_by_instrument_key(
                "fake_token", "NSE_FO|44444", "5minute", same_day, same_day,
            )
        called_url = mock_get.call_args.args[0]
        assert "NSE_FO%7C44444" in called_url  # instrument_key जसाच्या तसा (URL-encoded), NIFTY कडे fallback नाही
        assert len(df) == 1

    def test_failure_does_not_call_streamlit_warning(self):
        """🎓 PDF मध्ये अनेक trades च्या अनेक legs साठी वेगळे-वेगळे प्रयत्न होतात -- fetch_candles_date_range()
        प्रमाणे प्रत्येक अयशस्वी fetch साठी st.warning() दाखवणं गोंधळाचं ठरेल, म्हणून हे फंक्शन शांत
        (warn_on_failure=False) आहे."""
        same_day = datetime.date(2026, 9, 24)
        resp = _mock_get_response(404, None)
        resp.status_code = 404
        with patch.object(upstox_api.requests, "get", return_value=resp), \
             patch.object(upstox_api, "st") as mock_st:
            df = upstox_api.fetch_candles_date_range_by_instrument_key(
                "fake_token", "NSE_FO|99999", "5minute", same_day, same_day,
            )
        assert df.empty
        assert not mock_st.warning.called

    def test_expired_contract_no_data_returns_empty_df_gracefully(self):
        """एखादा (आधीच expire झालेला) option contract -- Upstox कडे इतिहास नसेल तर रिकामा DataFrame,
        अपवाद नाही -- caller (page_performance.py/pdf_reports.py) याला "data unavailable" म्हणून
        व्यवस्थित हाताळतो."""
        same_day = datetime.date(2026, 9, 20)
        resp = _mock_get_response(200, {"candles": []})
        with patch.object(upstox_api.requests, "get", return_value=resp):
            df = upstox_api.fetch_candles_date_range_by_instrument_key(
                "fake_token", "NSE_FO|12345", "5minute", same_day, same_day,
            )
        assert df.empty
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume", "oi"]
