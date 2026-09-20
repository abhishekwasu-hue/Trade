"""
tests/test_upstox_api.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Order Fill Verification, गंभीर यादीतला
पहिला मुद्दा) — LIVE multi-leg ऑर्डर प्लेस केल्यावर Upstox चं तात्काळ "200 success" उत्तर फक्त
"स्वीकारला गेला" इतकंच सांगतं, "प्रत्यक्ष भरला गेला" हे नाही. आता प्रत्येक leg चा order_id
GET /v2/order/details ने पोल करून खरी (terminal) स्थिती तपासली जाते.
"""
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
