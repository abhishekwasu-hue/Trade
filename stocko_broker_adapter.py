"""
stocko_broker_adapter.py
------------------------------
Multi-Broker आर्किटेक्चरचा चौथा (Stocko) Adapter — stocko_api.py functions ना BrokerAdapter
इंटरफेसच्या स्वरूपात wrap करणे.

⚠️ प्रामाणिक, महत्त्वाची टीप — stocko_api.py वरच्या इशाऱ्यांप्रमाणे: Order placement (LIVE),
Funds, Positions/Holdings — हे वापरकर्त्याने दिलेल्या अधिकृत Stocko API PDF वरून अचूक बांधलेले
आहेत. पण fetch_ltp_map/fetch_option_chain/fetch_candles इथे रिकामं/None परत देतात — Stocko च्या
PDF मध्ये Market Data endpoints सापडले नाहीत (वेगळा दस्तऐवज लागेल). त्यामुळे Stocko अजून
Strategy Builder/A1 Signal Engine साठी वापरता येणार नाही (त्यांना option chain/LTP लागतं) —
फक्त मॅन्युअली तयार केलेले (strike/instrument_token माहीत असलेले) orders place करण्यासाठी उपयोगी.
access_token इथे नेहमी "api_client_id:access_token" या combined स्वरूपातच
अपेक्षित आहे.
"""
from broker_adapter import BrokerAdapter
from stocko_api import (
    fetch_ltp_map, fetch_stocko_option_chain, fetch_candles,
    execute_order_leg_set, get_available_margin,
)


class StockoBrokerAdapter(BrokerAdapter):
    """stocko_api.py functions चा BrokerAdapter-इंटरफेस मधला wrapper."""

    def fetch_ltp_map(self, instrument_keys):
        return fetch_ltp_map(self.access_token, instrument_keys)

    def fetch_option_chain(self, symbol):
        raw_chain, _status = fetch_stocko_option_chain(self.access_token, symbol)
        return raw_chain

    def fetch_candles(self, symbol, interval, lookback_days):
        return fetch_candles(self.access_token, symbol, interval, lookback_days)

    def execute_order_leg_set(self, orders, trading_mode):
        return execute_order_leg_set(self.access_token, orders, trading_mode)

    def get_funds(self):
        return get_available_margin(self.access_token)
