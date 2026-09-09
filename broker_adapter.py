"""
broker_adapter.py
--------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली, Multi-Broker Multi-Account आर्किटेक्चरची पायाभूत रचना —
established प्रत्येक broker (Upstox, Fyers, भविष्यातले इतर) समान, standardised पद्धतीने वापरता यावा
म्हणून, हे एक अमूर्त (abstract) इंटरफेस — प्रत्येक broker-specific "Adapter" यालाच लागू (implement)
करतो, जेणेकरून established strategy-scripts (SRv2, Dynamic S/R, Trade Monitor इ.) कुठल्या broker/
account शी बोलतायत याची पर्वा न करता, एकाच, समान पद्धतीने काम करू शकतील.

प्रत्येक BrokerAdapter उपवर्गाने (subclass) हे methods अंमलात आणायलाच हवेत:
  - fetch_ltp(instrument_keys) -> {key: price}
  - fetch_option_chain(symbol) -> established raw_chain स्वरूप (strike_price, call_options, put_options)
  - fetch_candles(symbol, interval, lookback_days) -> established DataFrame
  - execute_order_leg_set(orders, trading_mode) -> established (status_code, response_dict)
  - get_funds() -> उपलब्ध मार्जिन (float)
  - get_required_margin(orders) -> established strategy साठी लागणारी मार्जिन (float), ऐच्छिक (डीफॉल्ट None)
"""
from abc import ABC, abstractmethod


class BrokerAdapter(ABC):
    """established सर्व brokers साठी समान, अमूर्त इंटरफेस -- प्रत्येक account (account_id सह) चा एक इन्स्टन्स."""

    def __init__(self, access_token, account_id):
        self.access_token = access_token
        self.account_id = account_id

    def get_account_id(self):
        return self.account_id

    @abstractmethod
    def fetch_ltp_map(self, instrument_keys):
        """दिलेल्या instrument keys साठी सद्य LTP -- {key: price} स्वरूपात."""
        ...

    @abstractmethod
    def fetch_option_chain(self, symbol):
        """established raw_chain स्वरूप -- [{"strike_price":.., "call_options": {...}, "put_options": {...}}, ...]."""
        ...

    @abstractmethod
    def fetch_candles(self, symbol, interval, lookback_days):
        """established DataFrame स्वरूप -- columns: timestamp, open, high, low, close, volume."""
        ...

    @abstractmethod
    def execute_order_leg_set(self, orders, trading_mode):
        """established orders-list प्लेस करून, (status_code, response_dict) परत करणे."""
        ...

    @abstractmethod
    def get_funds(self):
        """उपलब्ध मार्जिन (float), किंवा मिळाली नाही तर None."""
        ...

    def get_required_margin(self, orders):
        """
        🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Pre-Trade Margin Check) — establishedया strategy
        साठी established broker कडे नेमकी किती मार्जिन लागेल — established `orders` (established
        instrument_token/quantity/transaction_type/product सह). Non-abstract, डीफॉल्ट None (established
        subclass कडे अचूक margin-calculator API नसेल तर) — caller ने established तेव्हा max_loss-आधारित
        सुरक्षित अंदाज वापरावा.
        """
        return None
