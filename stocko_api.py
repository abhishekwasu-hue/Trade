"""
stocko_api.py
----------------
Stocko (SAS Online) साठीचा REST-wrapper — वापरकर्त्याने दिलेल्या अधिकृत Stocko API PDF दस्तऐवजावरून
(Api_Doc-1-1.pdf, १९ पानं) थेट बांधलेला.

Authentication — OAuth2 (Upstox/Fyers सारखं Authorization-Code ढाचा), दोन महत्त्वाचे फरक:
  १. Access token endpoint (`/oauth2/token`) ला client_id/secret request-body मध्ये नाही, तर
     **HTTP Basic Auth header** म्हणून पाठवायचे (PDF मध्ये स्पष्ट: "Credentials: As Basic Auth
     Header (default)").
  २. दोन वेगवेगळ्या "client_id" संकल्पना आहेत, गल्लत होऊ नये म्हणून वेगळी नावं वापरली आहेत:
       - `oauth_client_id`/`oauth_client_secret` — Stocko Developer Console कडून मिळणारा OAuth2
         client ID/secret (PDF मध्ये "<oauthID>").
       - `api_client_id` — तुमचा ट्रेडिंग Login ID (PDF च्या उदाहरणांमध्ये "XYZ") — जवळजवळ प्रत्येक
         API कॉलला query-param म्हणून लागतो.

⚠️ प्रामाणिक टीप — दोन गोष्टी PDF मध्ये नव्हत्या, त्यामुळे इथे स्पष्टपणे वेगळ्या हाताळल्या आहेत:
  १. **base_url** — PDF मध्ये फक्त `<base_url>` असा placeholder आहे ("SAS Online will Provide").
     त्यामुळे हा कोड `STOCKO_BASE_URL` environment variable वरून वाचतो — तो सेट नसेल तर स्पष्ट
     एरर देतो, चुकीचं/अंदाजित URL कधीच वापरत नाही.
  २. **LTP/Option Chain/Historical Candles** — या तिन्हीसाठी PDF मध्ये कुठलाही endpoint सापडला
     नाही (PDF फक्त Profile/Orders/Positions/Holdings/Funds/Scripinfo/Search इतकंच कव्हर करतो —
     बहुतेक brokers कडे "Market Data API" हा वेगळा दस्तऐवज असतो). त्यामुळे fetch_ltp_map()/
     fetch_option_chain()/fetch_candles() इथे रिकामं/None परत देतात, स्पष्ट कारणासह — अंदाजाने
     कुठलाही endpoint बांधलेला नाही. हे तीन मिळाले (वेगळा Market Data API PDF/लिंक) की भरता येतील.

PDF मध्ये स्पष्टपणे दिलेले (आणि म्हणून इथे अचूक, पडताळणी न लागणारे) भाग: login flow, Place/Modify/
Cancel Order, Orderbook/TradeBook/OrderHistory, PositionBook, Demat Holdings, Cash Positions
(Funds), Scripinfo, Search Script.
"""
import os
import time
import urllib.parse

import pandas as pd
import requests

BASE_URL = os.environ.get("STOCKO_BASE_URL", "").rstrip("/")


def _check_base_url():
    if not BASE_URL:
        return "STOCKO_BASE_URL environment variable सेट नाही (PDF मध्ये फक्त <base_url> placeholder आहे — तुमच्या Stocko खात्याकडून/Developer Console कडून खरं मूल्य मिळवून सेट करा)."
    return None


def build_login_url(oauth_client_id, redirect_uri, scope="orders holdings", state=None):
    """PDF च्या "Sample GET request" प्रमाणे — /oauth2/auth login-dialog URL."""
    params = {
        "scope": scope, "redirect_uri": redirect_uri,
        "response_type": "code", "client_id": oauth_client_id,
    }
    if state:
        params["state"] = state
    return f"{BASE_URL}/oauth2/auth?{urllib.parse.urlencode(params)}"


def exchange_auth_code_for_token(oauth_client_id, oauth_client_secret, auth_code, redirect_uri, api_client_id):
    """
    /oauth2/token — Basic Auth (oauth_client_id:oauth_client_secret) header सह, standard OAuth2
    Authorization-Code grant (grant_type/code/redirect_uri — PDF token-exchange च्या request-body
    चं exact स्वरूप दाखवत नाही, हे RFC 6749 च्या मानक फॉरमॅटनुसार आहे — PDF मधल्या
    "Grant type: Authorization Code" या वाक्यावरून पडताळलेलं).

    यशस्वी झाल्यास (combined_token, None) — combined token "api_client_id:access_token" स्वरूपात
    (Fyers/Shoonya च्याच पॅटर्नप्रमाणे — प्रत्येक पुढच्या API कॉलला दोन्हीही लागतात).
    """
    base_url_error = _check_base_url()
    if base_url_error:
        return None, base_url_error
    try:
        res = requests.post(
            f"{BASE_URL}/oauth2/token",
            auth=(oauth_client_id, oauth_client_secret),
            data={"grant_type": "authorization_code", "code": auth_code, "redirect_uri": redirect_uri},
            timeout=10,
        )
        if res.status_code != 200:
            return None, f"HTTP {res.status_code}: {res.text}"
        data = res.json()
        access_token = data.get("access_token")
        if not access_token:
            return None, f"access_token response मध्ये सापडला नाही: {data}"
        return f"{api_client_id}:{access_token}", None
    except Exception as e:
        return None, str(e)


def _split_token(access_token):
    """combined token ("api_client_id:access_token") दोन भागांत वेगळं करणे."""
    client_id, _, token = access_token.partition(":")
    return client_id, token


def _headers(access_token):
    _, token = _split_token(access_token)
    return {"Authorization": f"Bearer {token}"}


def _get(path, access_token, params=None, timeout=8):
    base_url_error = _check_base_url()
    if base_url_error:
        return None, base_url_error
    try:
        res = requests.get(f"{BASE_URL}{path}", headers=_headers(access_token), params=params, timeout=timeout)
        return res, None
    except Exception as e:
        return None, str(e)


def get_profile(access_token):
    """PDF #1 (Profile) — GET /api/v1/user/profile?client_id=<clientID>."""
    client_id, _ = _split_token(access_token)
    res, error = _get("/api/v1/user/profile", access_token, params={"client_id": client_id})
    if error:
        return None, error
    if res.status_code != 200:
        return None, f"HTTP {res.status_code}: {res.text}"
    return res.json().get("data"), None


def place_order(access_token, exchange, instrument_token, order_type, quantity, order_side, product,
                 price=0, trigger_price=0, validity="DAY", disclosed_quantity=0, user_order_id=None):
    """
    PDF #2 (Place Normal Order) — POST /api/v1/orders. पॅरामीटर्स PDF च्याच नावांनी, अचूक:
    exchange: NSE/NFO/CDS/BSE/MCX · order_type: LIMIT/MARKET/SL/SLM · order_side: BUY/SELL ·
    product: MIS (Intraday) / NRML (Carryforward) / CNC.
    """
    base_url_error = _check_base_url()
    if base_url_error:
        return None, base_url_error
    client_id, token = _split_token(access_token)
    body = {
        "exchange": exchange, "order_type": order_type, "instrument_token": instrument_token,
        "quantity": quantity, "disclosed_quantity": disclosed_quantity, "price": price,
        "order_side": order_side, "trigger_price": trigger_price, "validity": validity,
        "product": product, "client_id": client_id,
        "user_order_id": user_order_id or int(time.time()) % 100000,
        "market_protection_percentage": 0, "device": "WEB",
    }
    try:
        res = requests.post(f"{BASE_URL}/api/v1/orders", headers={"Authorization": f"Bearer {token}"}, json=body, timeout=10)
        return res.status_code, res.json()
    except Exception as e:
        return 500, {"status": "error", "message": str(e)}


def cancel_order(access_token, oms_order_id):
    """PDF #4 (Cancel Normal Order) — DELETE /api/v1/orders/<omsOrderNum>?client_id=<clientID>."""
    base_url_error = _check_base_url()
    if base_url_error:
        return False, base_url_error
    client_id, token = _split_token(access_token)
    try:
        res = requests.delete(
            f"{BASE_URL}/api/v1/orders/{oms_order_id}",
            headers={"Authorization": f"Bearer {token}"}, params={"client_id": client_id}, timeout=10,
        )
        return res.status_code == 200, res.json()
    except Exception as e:
        return False, {"status": "error", "message": str(e)}


def get_orderbook(access_token, order_type="pending"):
    """PDF #7 (Orderbook) — order_type: 'pending' किंवा 'completed'."""
    client_id, _ = _split_token(access_token)
    res, error = _get("/api/v1/orders", access_token, params={"type": order_type, "client_id": client_id})
    if error or res.status_code != 200:
        return []
    return res.json().get("data", {}).get("orders", [])


def get_positions(access_token, position_type="live"):
    """PDF #10 (PositionBook) — position_type: 'live' (आजचं) किंवा 'historical' (सर्व)."""
    client_id, _ = _split_token(access_token)
    res, error = _get("/api/v1/positions", access_token, params={"type": position_type, "client_id": client_id})
    if error or res.status_code != 200:
        return []
    return res.json().get("data", [])


def get_holdings(access_token):
    """PDF #11 (Demat Holdings)."""
    client_id, _ = _split_token(access_token)
    res, error = _get("/api/v1/holdings", access_token, params={"client_id": client_id})
    if error or res.status_code != 200:
        return []
    return res.json().get("data", {}).get("holdings", [])


def search_scrip(access_token, keyword):
    """PDF #6 (Search Script) — GET /api/v1/search?key=<keyword>."""
    res, error = _get("/api/v1/search", access_token, params={"key": keyword})
    if error or res.status_code != 200:
        return []
    return res.json().get("result", [])


def get_scrip_info(access_token, exchange, instrument_token):
    """PDF #5 (Scripinfo) — static contract info (lot size, tick size, इ.) — LTP/price नाही."""
    res, error = _get(f"/api/v1/contract/{exchange}", access_token, params={"info": "scrip", "token": instrument_token})
    if error or res.status_code != 200:
        return None
    return res.json().get("result")


def get_available_margin(access_token):
    """
    PDF #12 (Cash Positions) — GET /api/v1/funds/view?client_id=<clientID>&type=all.
    Response ची "values" ही key-value जोड्यांची list असते (प्रत्येक dict मध्ये एकच key) —
    त्यातून "Available" शोधून काढतो.
    """
    client_id, _ = _split_token(access_token)
    res, error = _get("/api/v1/funds/view", access_token, params={"client_id": client_id, "type": "all"})
    if error or res.status_code != 200:
        return None
    values = res.json().get("data", {}).get("values", [])
    for item in values:
        if "Available" in item:
            try:
                return float(item["Available"])
            except (TypeError, ValueError):
                return None
    return None


# ---------------------------------------------------------------------------
# ⚠️ खालचे तिन्ही — LTP, Option Chain, Historical Candles — PDF मध्ये कुठलाही endpoint सापडला
# नाही (वर मॉड्यूल-docstring मध्ये स्पष्ट केल्याप्रमाणे). अंदाजाने कुठलाही URL बांधलेला नाही —
# रिकामं/None परत देतात, जेणेकरून कॉलिंग कोड सुरक्षितपणे "डेटा उपलब्ध नाही" असं वागेल, चुकीचा
# डेटा दाखवणार नाही. वेगळा Market Data API दस्तऐवज मिळाला की हे भरता येतील.
# ---------------------------------------------------------------------------

def fetch_ltp_map(access_token, instrument_keys):
    """⚠️ Stocko च्या PDF मध्ये LTP/Quotes endpoint सापडला नाही — रिकामी dict परत देतो."""
    return {k: None for k in instrument_keys}


def fetch_stocko_option_chain(access_token, symbol):
    """⚠️ Stocko च्या PDF मध्ये Option Chain endpoint सापडला नाही — रिकामी यादी परत देतो."""
    return [], "NOT_IMPLEMENTED: Stocko Market Data API दस्तऐवज उपलब्ध नाही (फक्त Orders/Funds/Positions API मिळालेला आहे)."


def fetch_candles(access_token, symbol_token, interval, lookback_days):
    """⚠️ Stocko च्या PDF मध्ये Historical Candle endpoint सापडला नाही — रिकामा DataFrame परत देतो."""
    return pd.DataFrame()


def execute_order_leg_set(access_token, orders, trading_mode="LIVE"):
    """
    upstox_api.execute_order_leg_set()/fyers_api.execute_order_leg_set() च्याच PAPER/LIVE
    पॅटर्नने. सर्व codebase-wide product_type "D"/"I" इथे Stocko च्या NRML/MIS मध्ये रूपांतरित.

    ⚠️ trading_mode == "PAPER": इतर brokers प्रमाणे सध्याची LTP वापरून सिम्युलेट करायचं असतं, पण
    fetch_ltp_map() इथे अजून काम करत नाही (वरचा इशारा बघा) — त्यामुळे PAPER mode स्पष्ट एरर देतो,
    चुकीच्या (fake) किमतीने सिम्युलेटेड फिल दाखवत नाही — Market Data API मिळेपर्यंत Stocko वर PAPER
    टेस्टिंग करता येणार नाही.
    """
    if trading_mode != "LIVE":
        return None, {
            "status": "error",
            "errors": [{"message": "Stocko साठी PAPER mode अजून उपलब्ध नाही — LTP/Market Data API अजून जोडलेला नाही (fetch_ltp_map खाली बघा)."}],
        }

    order_type_map = {"MARKET": "MARKET", "LIMIT": "LIMIT", "SL": "SL", "SL-M": "SLM"}
    product_map = {"D": "NRML", "I": "MIS"}
    # PDF #2 प्रमाणे Stocko चे स्वतःचे वैध exchange codes — "NSE_FO" (Upstox चं स्वरूप) यात नाही.
    VALID_STOCKO_EXCHANGES = {"NSE", "NFO", "CDS", "BSE", "MCX"}
    order_ids = []
    # 🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — place_order() चा डीफॉल्ट user_order_id
    # (int(time.time()) % 100000, सेकंद-रिझोल्यूशन) एकाच multi-leg ऑर्डरमधल्या सलग legs साठी
    # सहज एकसारखाच येऊ शकतो (जलद, sequential HTTP कॉल्स बहुतेकदा एकाच सेकंदात पूर्ण होतात) —
    # Stocko कडून दुसरा leg duplicate order id म्हणून नाकारला जाण्याचा धोका. आता batch-निहाय
    # एकच base (मिलिसेकंद-रिझोल्यूशन) + leg-index, त्यामुळे एकाच batch मधल्या legs ना हमखास
    # वेगवेगळे id मिळतात.
    batch_order_id_base = int(time.time() * 1000) % 90000
    for i, o in enumerate(orders):
        exch, _, token = o["instrument_token"].partition("|")
        # 🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — Shoonya साठीच्याच
        # टीपेप्रमाणे — बॉट्स strike-निवडीसाठी नेहमी fetch_upstox_option_chain() वापरतात, त्यामुळे
        # इथे पोहोचणारा instrument_token नेहमी Upstox च्याच स्वरूपात असतो ("NSE_FO|<upstox numeric
        # token>"). आधी हा exchange="NSE_FO" (Stocko ला "NSE"/"NFO"/... हवं) आणि Upstox चाच numeric
        # token (Stocko साठी निरर्थक, त्यांचा स्वतःचा instrument_token वेगळाच असतो) म्हणून थेट
        # Stocko कडे पाठवला जायचा. Stocko साठी स्वतःचा option-chain/strike-resolution मार्ग अजून
        # bot-स्तरावर जोडलेला नाही (fetch_shoonya_option_chain() सारखं काहीच Stocko साठी अस्तित्वात
        # नाही) — तोपर्यंत असा स्पष्टपणे-चुकीचा instrument असेल, तर शांतपणे चुकीचा/अंदाजे order
        # पाठवण्यापेक्षा, इथेच स्पष्ट error देऊन थांबणं जास्त सुरक्षित.
        if exch not in VALID_STOCKO_EXCHANGES:
            return 500, {
                "status": "error",
                "message": (
                    f"Stocko LIVE order अडवला — instrument_token ('{o['instrument_token']}') Upstox च्या "
                    "स्वरूपात आहे, Stocko चा स्वतःचा instrument_token नाही (अजून जोडलेलं नाही). चुकीच्या/भलत्याच "
                    "contract वर order जाण्यापेक्षा हे थांबवणं सुरक्षित."
                ),
                "partial_order_ids": order_ids,
            }
        status_code, resp = place_order(
            access_token,
            exchange=exch or "NFO",
            instrument_token=token,
            order_type=order_type_map.get(o.get("order_type", "MARKET"), "MARKET"),
            quantity=o["quantity"],
            order_side="BUY" if o["transaction_type"] == "BUY" else "SELL",
            product=product_map.get(o.get("product"), "NRML"),
            price=o.get("price", 0),
            trigger_price=o.get("trigger_price", 0),
            user_order_id=batch_order_id_base + i,
        )
        # 🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — STOCKO_BASE_URL सेट नसेल, तर place_order()
        # (_check_base_url() मुळे) resp म्हणून dict ऐवजी थेट error-string परत देतो (status_code=None) —
        # खालचा resp.get(...) तेव्हा dict नसलेल्या string वर कॉल होऊन AttributeError ने संपूर्ण
        # LIVE order-placement अनपेक्षितपणे क्रॅश व्हायचं, ऐवजी स्पष्ट error हवा होता.
        if status_code is None:
            return 500, {"status": "error", "message": resp, "partial_order_ids": order_ids}
        if resp.get("status") == "success":
            order_ids.append(resp.get("data", {}).get("oms_order_id"))
        else:
            return 500, {"status": "error", "message": resp.get("message", str(resp)), "partial_order_ids": order_ids}
    return 200, {"status": "success", "data": {"order_ids": order_ids}}
