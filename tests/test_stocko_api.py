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
