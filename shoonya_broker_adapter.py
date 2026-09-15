"""
shoonya_broker_adapter.py
------------------------------
Multi-Broker आर्किटेक्चरचा तिसरा (Shoonya) Adapter — shoonya_api.py functions ना BrokerAdapter
इंटरफेसच्या स्वरूपात wrap करणे.

⚠️ प्रामाणिक, महत्त्वाची टीप (fyers_broker_adapter.py च्याच इशाऱ्याप्रमाणे) — हा Adapter
code-स्तरावर तयार आहे, पण प्रत्यक्ष, खऱ्या Shoonya account सह अजून पडताळलेला नाही — विशेषतः
Option Chain च्या response-field-names आणि LIVE order-placement. LIVE करण्याआधी shoonya_api.py
वरच्या इशाऱ्यांप्रमाणे स्वतः पडताळा. access_token इथे नेहमी "userid:susertoken" या Shoonya-established
combined स्वरूपातच अपेक्षित आहे.
"""
from broker_adapter import BrokerAdapter
from shoonya_api import (
    fetch_ltp_map, fetch_shoonya_option_chain, fetch_candles,
    execute_order_leg_set, get_available_margin,
)


class ShoonyaBrokerAdapter(BrokerAdapter):
    """shoonya_api.py functions चा BrokerAdapter-इंटरफेस मधला wrapper."""

    def fetch_ltp_map(self, instrument_keys):
        return fetch_ltp_map(self.access_token, instrument_keys)

    def fetch_option_chain(self, symbol):
        return fetch_shoonya_option_chain(self.access_token, symbol)

    def fetch_candles(self, symbol, interval, lookback_days):
        return fetch_candles(self.access_token, symbol, interval, lookback_days)

    def execute_order_leg_set(self, orders, trading_mode):
        return execute_order_leg_set(self.access_token, orders, trading_mode)

    def get_funds(self):
        return get_available_margin(self.access_token)
