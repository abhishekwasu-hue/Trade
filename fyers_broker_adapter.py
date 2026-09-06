"""
fyers_broker_adapter.py
---------------------------
🎓 established Multi-Broker आर्किटेक्चरचा दुसरा (Fyers) Adapter — established fyers_api.py functions
ना established BrokerAdapter इंटरफेसच्या स्वरूपात wrap करणे.

⚠️ प्रामाणिक, महत्त्वाची टीप — हा Adapter code-स्तरावर तयार आहे, पण established broker_factory.py
मध्ये **जाणीवपूर्वक अजून सक्रिय केलेला नाही** ("अजून पूर्ण झालेला नाही" असा error देतो) — कारण Fyers च्या
Option-Symbol निर्मितीची (विशेषतः NIFTY इंडेक्स-options साठी नेमकं नामकरण) पडताळणी अजून prत्यक्ष Fyers
account सह झालेली नाही. established access_token इथे नेहमी "client_id:access_token" या Fyers-established
combined स्वरूपातच अपेक्षित आहे.
"""
from broker_adapter import BrokerAdapter
from fyers_api import (
    fetch_ltp_map, fetch_fyers_option_chain, fetch_candles,
    execute_order_leg_set, get_available_margin,
)


class FyersBrokerAdapter(BrokerAdapter):
    """established fyers_api.py functions चा BrokerAdapter-इंटरफेस मधला wrapper."""

    def fetch_ltp_map(self, instrument_keys):
        return fetch_ltp_map(self.access_token, instrument_keys)

    def fetch_option_chain(self, symbol):
        raw_chain, status = fetch_fyers_option_chain(self.access_token, symbol)
        return raw_chain if status == "SUCCESS" else []

    def fetch_candles(self, symbol, interval, lookback_days):
        return fetch_candles(self.access_token, symbol, interval, lookback_days)

    def execute_order_leg_set(self, orders, trading_mode):
        return execute_order_leg_set(self.access_token, orders, trading_mode)

    def get_funds(self):
        return get_available_margin(self.access_token)
