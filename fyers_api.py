"""
fyers_api.py
--------------
🎓 वापरकर्त्याशी चर्चा करून, संशोधन केलेल्या (अधिकृत Fyers API v3 दस्तऐवजीकरण/established SDK-स्रोत)
माहितीवरून बांधलेला, established upstox_api.py सारखाच, Fyers साठीचा REST-wrapper.

⚠️ महत्त्वाची, प्रामाणिक टीप — हे established, अधिकृत माहितीवर आधारित बांधलेलं आहे, पण **प्रत्यक्ष,
खऱ्या Fyers account/order सह अजून टेस्ट झालेलं नाही** (केवळ established दस्तऐवजीकरण/established SDK
स्रोत-कोड वरून). पहिला वापर करताना PAPER-सदृश (उदा. एक अगदी लहान, टाकाऊ ऑर्डर) चाचणी आधी करा.

established authorization पॅटर्न: access_token नेहमी "client_id:access_token" या combined स्वरूपातच
साठवला/पाठवला जातो (established Fyers चाच अधिकृत नियम — Bearer नाही).
"""
import hashlib

import pandas as pd
import requests

BASE_URL = "https://api-t1.fyers.in/api/v3"
DATA_URL = "https://api-t1.fyers.in/data"

# established Fyers resolution-codes (established दस्तऐवजीकरणानुसार)
INTERVAL_TO_RESOLUTION = {"1minute": "1", "5minute": "5", "15minute": "15", "30minute": "30", "1hour": "60", "day": "D"}


def build_app_id_hash(app_id, app_secret):
    """
    🎓 वापरकर्त्याशी चर्चा करून, संशोधन केलेल्या माहितीवरून जोडलेलं — established Fyers token-exchange
    ला आवश्यक appIdHash. established, अत्यंत सामान्य चूक: app_id आणि app_secret मध्ये **कोलन (":")**
    असायलाच हवा — नसेल तर established, पूर्णपणे वेगळा (चुकीचा) hash तयार होतो, आणि established Fyers
    "Error -371: Please provide SHA-256 hash of appId and app secret" असा error देतो.
    """
    return hashlib.sha256(f"{app_id}:{app_secret}".encode("utf-8")).hexdigest()


def exchange_auth_code_for_token(app_id, app_secret, auth_code):
    """established Fyers OAuth v3 -- established validate-authcode API वापरून, auth_code चं
    access_token मध्ये रूपांतर. यशस्वी झाल्यास (combined_token, None), अयशस्वी झाल्यास (None, error)."""
    app_id_hash = build_app_id_hash(app_id, app_secret)
    try:
        res = requests.post(
            f"{BASE_URL}/validate-authcode",
            headers={"Content-Type": "application/json"},
            json={"grant_type": "authorization_code", "appIdHash": app_id_hash, "code": auth_code},
            timeout=10,
        )
        if res.status_code != 200:
            return None, f"HTTP {res.status_code}: {res.text}"
        data = res.json()
        access_token = data.get("access_token")
        if not access_token:
            return None, f"access_token मिळाला नाही: {data}"
        # 🎓 established Fyers चा नियम -- Authorization header ला नेहमी "app_id:access_token" हेच
        # combined स्वरूप लागतं (established Bearer नाही) -- इथेच जोडून, वापरण्यास तयार token देणे.
        return f"{app_id}:{access_token}", None
    except Exception as e:
        return None, str(e)


def _headers(access_token):
    """established Fyers चा नियम -- Authorization: <client_id>:<access_token> (Bearer नाही)."""
    return {"Authorization": access_token}


def fetch_ltp_map(access_token, instrument_keys):
    """established Fyers Quotes API -- {instrument_key: ltp} स्वरूपात."""
    try:
        res = requests.get(
            f"{DATA_URL}/quotes",
            headers=_headers(access_token),
            params={"symbols": ",".join(instrument_keys)},
            timeout=8,
        )
        if res.status_code != 200:
            return {k: None for k in instrument_keys}
        data = res.json().get("d", [])
        return {item["n"]: item.get("v", {}).get("lp") for item in data}
    except Exception:
        return {k: None for k in instrument_keys}


def transform_fyers_option_chain(fyers_options_chain, underlying_price=None):
    """
    🎓 established Fyers च्या FLAT list स्वरूपाला, established आपल्या अंतर्गत raw_chain (Upstox-सारखं
    nested, प्रति-strike एक dict) स्वरूपात रूपांतरित करणे -- जेणेकरून established
    select_credit_spread_fixed_strikes() सारखी functions कुठलाही बदल न करता वापरता येतील.
    """
    strikes = {}
    for entry in fyers_options_chain:
        strike = entry["strike_price"]
        if strike not in strikes:
            strikes[strike] = {"strike_price": strike, "underlying_spot_price": underlying_price,
                                "call_options": None, "put_options": None}
        leg_data = {
            "instrument_key": entry["symbol"],
            "market_data": {"ltp": entry["ltp"], "oi": entry.get("oi", 0), "volume": entry.get("volume", 0)},
            "option_greeks": {},
        }
        if entry["option_type"] == "CE":
            strikes[strike]["call_options"] = leg_data
        else:
            strikes[strike]["put_options"] = leg_data
    return [strikes[k] for k in sorted(strikes.keys())]


def fetch_fyers_option_chain(access_token, symbol):
    """established Fyers Option Chain API -- established raw_chain स्वरूपात रूपांतरित करून परत करणे."""
    try:
        res = requests.get(
            f"{BASE_URL}/options-chain-v3",
            headers=_headers(access_token),
            params={"symbol": symbol, "strikecount": 20},
            timeout=8,
        )
        if res.status_code != 200:
            return [], "FAILED"
        data = res.json().get("data", {})
        options_chain = data.get("optionsChain", [])
        underlying_price = None
        raw_chain = transform_fyers_option_chain(options_chain, underlying_price)
        return raw_chain, "SUCCESS"
    except Exception:
        return [], "FAILED"


def fetch_candles(access_token, symbol, interval, lookback_days):
    """established Fyers History API -- established DataFrame स्वरूपात (timestamp,open,high,low,close,volume)."""
    import datetime
    resolution = INTERVAL_TO_RESOLUTION.get(interval, "5")
    range_to = datetime.datetime.now()
    range_from = range_to - datetime.timedelta(days=lookback_days)
    try:
        res = requests.get(
            f"{DATA_URL}/history",
            headers=_headers(access_token),
            params={
                "symbol": symbol, "resolution": resolution, "date_format": "1",
                "range_from": range_from.strftime("%Y-%m-%d"), "range_to": range_to.strftime("%Y-%m-%d"),
                "cont_flag": "1",
            },
            timeout=10,
        )
        if res.status_code != 200:
            return pd.DataFrame()
        candles = res.json().get("candles", [])
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        return df
    except Exception:
        return pd.DataFrame()


def execute_order_leg_set(access_token, orders, trading_mode="LIVE"):
    """
    🎓 established upstox_api.execute_order_leg_set() च्याच PAPER/LIVE पॅटर्नने — established वर्तन
    (SL/Target, Position Sizing) सर्व brokers वर एकसारखंच राहावं म्हणून.
    trading_mode == "LIVE": खरा Fyers Multi-Leg Order API कॉल.
    trading_mode == "PAPER": कोणताही खरा API कॉल न करता, प्रत्येक leg ची सध्याची मार्केट LTP आणून,
    त्यावरच तात्काळ भरलेली (filled) सिम्युलेटेड ऑर्डर तयार करणे.
    """
    if trading_mode == "LIVE":
        try:
            res = requests.post(f"{BASE_URL}/multi-order/sync", headers=_headers(access_token), json=orders, timeout=10)
            return res.status_code, res.json()
        except Exception as e:
            return 500, {"s": "error", "message": str(e)}

    instrument_keys = [o["instrument_token"] for o in orders]
    ltp_map = fetch_ltp_map(access_token, instrument_keys)
    if any(ltp_map.get(k) is None for k in instrument_keys):
        return None, {"status": "error", "errors": [{"message": "Paper fill साठी एका किंवा अधिक legs ची LTP मिळाली नाही."}]}

    import time
    import uuid
    batch_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    order_ids = [f"PAPER-{batch_id}-{i}" for i in range(len(orders))]
    return 200, {"status": "success", "data": {"order_ids": order_ids}, "paper_fills": ltp_map}


def get_available_margin(access_token):
    """established Fyers Funds API -- उपलब्ध मार्जिन (float), किंवा मिळालं नाही तर None."""
    try:
        res = requests.get(f"{BASE_URL}/funds", headers=_headers(access_token), timeout=8)
        if res.status_code != 200:
            return None
        fund_limits = res.json().get("fund_limit", [])
        for item in fund_limits:
            if item.get("title") == "Available Balance":
                return item.get("equityAmount")
        return None
    except Exception:
        return None
