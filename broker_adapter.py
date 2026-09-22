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

    def supports_broker_side_stop_loss(self):
        """🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL", सध्या फक्त Upstox
        साठी) — caller ने (trading_engine.py) हे आधी तपासूनच place_stop_loss_order()/cancel_order()
        वापरावं; न-सपोर्ट करणाऱ्या brokers (Shoonya/Stocko/Fyers) साठी डीफॉल्ट False — polling-based
        (trade_monitor.py) exit हाच त्यांचा एकमेव मार्ग तसाच राहतो, काहीही न बदलता."""
        return False

    def place_stop_loss_order(self, instrument_token, quantity, transaction_type, product, trigger_price):
        """established leg साठी resting SL-M (Stop-Loss Market) order ठेवणे — फक्त
        supports_broker_side_stop_loss()==True असणाऱ्या brokers नीच override करावं.
        रिटर्न: order_id (str) यशस्वी झाल्यास, नाहीतर None."""
        raise NotImplementedError(f"{type(self).__name__} broker-side SL orders support करत नाही")

    def cancel_order(self, order_id):
        """established आधीच ठेवलेला order (उदा. वरचा resting SL-M) रद्द करणे — established polling-based
        exit (Target/TSL/इ.) ने trade आधीच बंद केला की, हा उरलेला pending order रद्द करण्यासाठी वापरायचा.
        रिटर्न: True/False (यशस्वी झालं की नाही)."""
        raise NotImplementedError(f"{type(self).__name__} broker-side SL orders support करत नाही")
