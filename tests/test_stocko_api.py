"""
tests/test_stocko_api.py
--------------------------------
🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — शूनya साठीच्याच कारणाने —
बॉट्स नेहमी fetch_upstox_option_chain() वापरतात, त्यामुळे Stocko कडे पोहोचणारा instrument_token
नेहमी Upstox च्याच स्वरूपात ("NSE_FO|<upstox numeric token>") असतो, Stocko चा स्वतःचा
instrument_token/exchange-code नाही. आधी हे तसंच थेट Stocko कडे पाठवलं जायचं; आता वैध Stocko
exchange-code नसेल तर LIVE order स्पष्टपणे अडवला जायला हवा."""
from unittest.mock import patch

import stocko_api


class TestExecuteOrderLegSetLiveGuard:
    def test_live_order_with_upstox_shaped_exchange_is_blocked(self):
        orders = [{
            "instrument_token": "NSE_FO|12345678", "quantity": 75, "transaction_type": "SELL",
            "order_type": "MARKET", "price": 0, "product": "D",
        }]
        with patch.object(stocko_api, "place_order") as mock_place:
            status, resp = stocko_api.execute_order_leg_set("client:token", orders, trading_mode="LIVE")
        assert status == 500
        assert resp["status"] == "error"
        assert not mock_place.called  # खरा API कॉलच होता कामा नये

    def test_live_order_with_valid_stocko_exchange_proceeds(self):
        orders = [{
            "instrument_token": "NFO|987654", "quantity": 75, "transaction_type": "SELL",
            "order_type": "MARKET", "price": 0, "product": "D",
        }]
        with patch.object(stocko_api, "place_order", return_value=(200, {"status": "success", "data": {"oms_order_id": "ORD1"}})) as mock_place:
            status, resp = stocko_api.execute_order_leg_set("client:token", orders, trading_mode="LIVE")
        assert status == 200
        assert resp["data"]["order_ids"] == ["ORD1"]
        assert mock_place.call_args.kwargs["exchange"] == "NFO"
        assert mock_place.call_args.kwargs["instrument_token"] == "987654"

    def test_multi_leg_batch_gets_distinct_user_order_ids(self):
        """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — place_order() चा डीफॉल्ट user_order_id
        (int(time.time()) % 100000, सेकंद-रिझोल्यूशन) एकाच batch मधल्या सलग legs साठी सहज
        एकसारखाच येऊ शकतो — Stocko कडून दुसरा leg duplicate order id म्हणून नाकारला जाण्याचा धोका.
        आता प्रत्येक legला वेगळा (batch base + leg index) id मिळायलाच हवा."""
        orders = [
            {"instrument_token": "NFO|111", "quantity": 75, "transaction_type": "SELL", "order_type": "MARKET", "price": 0, "product": "D"},
            {"instrument_token": "NFO|222", "quantity": 75, "transaction_type": "BUY", "order_type": "MARKET", "price": 0, "product": "D"},
        ]
        with patch.object(stocko_api, "place_order", return_value=(200, {"status": "success", "data": {"oms_order_id": "ORD1"}})) as mock_place:
            stocko_api.execute_order_leg_set("client:token", orders, trading_mode="LIVE")
        user_order_ids = [c.kwargs["user_order_id"] for c in mock_place.call_args_list]
        assert len(user_order_ids) == 2
        assert len(set(user_order_ids)) == 2  # दोन्ही legs साठी वेगवेगळे id

    def test_missing_base_url_error_string_does_not_crash_with_attributeerror(self):
        """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — STOCKO_BASE_URL सेट नसेल, तर place_order()
        dict ऐवजी (None, error-string) परत देतो — खालचा resp.get(...) तेव्हा AttributeError ने
        क्रॅश व्हायचं (अनियंत्रित exception), स्पष्ट error dict ऐवजी."""
        orders = [{
            "instrument_token": "NFO|987654", "quantity": 75, "transaction_type": "SELL",
            "order_type": "MARKET", "price": 0, "product": "D",
        }]
        with patch.object(stocko_api, "place_order", return_value=(None, "STOCKO_BASE_URL environment variable सेट नाही")):
            status, resp = stocko_api.execute_order_leg_set("client:token", orders, trading_mode="LIVE")
        assert status == 500
        assert resp["status"] == "error"
        assert "STOCKO_BASE_URL" in resp["message"]
