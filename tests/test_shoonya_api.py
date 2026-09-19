"""
tests/test_shoonya_api.py
--------------------------------
🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — बॉट्स strike-निवडीसाठी नेहमी
fetch_upstox_option_chain() वापरतात, त्यामुळे Shoonya कडे पोहोचणारा instrument_token नेहमी Upstox
च्याच स्वरूपात असतो ("NSE_FO|<upstox numeric token>") — trading_symbol कधीच सेट केलेलं नसतं. आधी
असं असूनही चुकीचा exch/tsym पाठवला जायचा; आता trading_symbol नसेल तर LIVE order स्पष्टपणे अडवला
जायला हवा (शांतपणे चुकीचा/भलताच order पाठवण्याऐवजी)."""
from unittest.mock import patch

import shoonya_api


class TestExecuteOrderLegSetLiveGuard:
    def test_live_order_without_trading_symbol_is_blocked(self):
        orders = [{
            "instrument_token": "NSE_FO|12345678", "quantity": 75, "transaction_type": "SELL",
            "order_type": "MARKET", "price": 0,
        }]
        with patch.object(shoonya_api, "_post") as mock_post:
            status, resp = shoonya_api.execute_order_leg_set("USER123:susertoken", orders, trading_mode="LIVE")
        assert status == 500
        assert resp["status"] == "error"
        assert not mock_post.called  # खरा API कॉलच होता कामा नये

    def test_live_order_with_trading_symbol_proceeds(self):
        orders = [{
            "instrument_token": "NFO|12345678", "quantity": 75, "transaction_type": "SELL",
            "order_type": "MARKET", "price": 0, "trading_symbol": "NIFTY28AUG25P24000",
        }]
        with patch.object(shoonya_api, "_post", return_value={"stat": "Ok", "norenordno": "ORD1"}) as mock_post:
            status, resp = shoonya_api.execute_order_leg_set("USER123:susertoken", orders, trading_mode="LIVE")
        assert status == 200
        assert resp["data"]["order_ids"] == ["ORD1"]
        called_jdata = mock_post.call_args[0][1]
        assert called_jdata["tsym"] == "NIFTY28AUG25P24000"
        assert called_jdata["exch"] == "NFO"
