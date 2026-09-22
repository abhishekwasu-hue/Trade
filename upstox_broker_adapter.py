"""
upstox_broker_adapter.py
------------------------------
🎓 established Multi-Broker आर्किटेक्चरचा पहिला (Upstox) Adapter — established, आधीच अस्तित्वात
असलेल्या upstox_api.py functions ना, established BrokerAdapter इंटरफेसच्या स्वरूपात wrap करणे
(established, प्रत्यक्ष तर्कात कुठलाही बदल नाही — फक्त एकसंध, multi-account-सक्षम interface मागे लपवणे).
"""
from broker_adapter import BrokerAdapter
from upstox_api import (
    fetch_ltp_map, fetch_upstox_option_chain, fetch_candles,
    execute_order_leg_set, get_available_margin, fetch_required_margin,
    place_stop_loss_order, cancel_order,
)


class UpstoxBrokerAdapter(BrokerAdapter):
    """established upstox_api.py functions चा BrokerAdapter-इंटरफेस मधला wrapper."""

    def fetch_ltp_map(self, instrument_keys):
        return fetch_ltp_map(self.access_token, instrument_keys)

    def fetch_option_chain(self, symbol):
        raw_chain, status = fetch_upstox_option_chain(self.access_token, symbol, 0)
        return raw_chain if status == "SUCCESS" else []

    def fetch_candles(self, symbol, interval, lookback_days):
        return fetch_candles(self.access_token, symbol, current_spot=0, interval=interval, lookback_days=lookback_days)

    def execute_order_leg_set(self, orders, trading_mode):
        return execute_order_leg_set(self.access_token, orders, trading_mode)

    def get_funds(self):
        return get_available_margin(self.access_token)

    def get_required_margin(self, orders):
        # 🎓 established Upstox चं अधिकृत Margin Calculator API (v2/charges/margin) — established
        # संपूर्ण strategy साठी नेमकी मार्जिन (hedge-फायद्यासकट), ढोबळ अंदाज नाही.
        return fetch_required_margin(self.access_token, orders)

    def supports_broker_side_stop_loss(self):
        # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL", फक्त Upstox पासून सुरुवात)
        return True

    def place_stop_loss_order(self, instrument_token, quantity, transaction_type, product, trigger_price):
        status_code, resp = place_stop_loss_order(
            self.access_token, instrument_token, quantity, transaction_type, product, trigger_price,
        )
        if status_code == 200 and isinstance(resp, dict) and resp.get("status") == "success":
            return resp.get("data", {}).get("order_id")
        return None

    def cancel_order(self, order_id):
        status_code, resp = cancel_order(self.access_token, order_id)
        return status_code == 200 and isinstance(resp, dict) and resp.get("status") == "success"
