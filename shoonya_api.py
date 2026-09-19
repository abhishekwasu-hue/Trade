"""
shoonya_api.py
------------------
Shoonya (Finvasia) साठीचा REST-wrapper — upstox_api.py/fyers_api.py सारखाच पॅटर्न, पण Shoonya चं
Login/Order API ("NorenApi" — अनेक brokers नी white-label केलेलं एक सामायिक trading-API framework)
दोन मूलभूत बाबतीत वेगळं आहे:

  १. OAuth-redirect (Upstox/Fyers सारखं "ब्राउझरमध्ये लॉगिन करून auth_code कॉपी करा") नाही — थेट
     credential-based login: userid + password + factor2 (TOTP/जन्मतारीख) + vendor_code +
     api_secret + imei, एकाच API कॉलमध्ये (`/QuickAuth`).
  २. प्रत्येक API कॉल JSON body नाही — form-urlencoded `jData=<json-string>&jKey=<session_token>`
     (login-कॉललाच jKey नसतो, तो अजून मिळालेलाच नसतो).

⚠️ अत्यंत महत्त्वाची, प्रामाणिक टीप (fyers_api.py च्याच इशाऱ्याप्रमाणे) — हा सार्वजनिकरीत्या उपलब्ध
Shoonya/NorenApi दस्तऐवजीकरणावरून बांधलेला आहे, पण प्रत्यक्ष, खऱ्या Shoonya account/order सह अजून
टेस्ट झालेला **नाही**. LIVE trading साठी वापरण्याआधी हे स्वतः पडताळा (Upstox/Fyers दोघांच्याही
बाबतीत नेमकं हेच — response field-names — प्रत्यक्ष खात्यासह टेस्ट केल्यावरच बरोबर सापडलं होतं):
  - `login()` च्या response मधली exact field-names (`susertoken` वगैरे)
  - `fetch_shoonya_option_chain()` च्या response ची shape
  - `execute_order_leg_set()` चं LIVE ऑर्डर placement (आधी अत्यंत लहान, टाकाऊ रकमेने स्वतः एकदा
    प्रत्यक्ष टेस्ट करा — बाकी सर्व brokers प्रमाणेच सर्व रणनींती डीफॉल्टने PAPER mode वापरतात,
    त्यामुळे हा धोका PAPER साठी लागू होत नाही)

Option trading-symbol/token Shoonya च्याच `/SearchScrip` API कडूनच मिळवला जातो — स्वतः अंदाजाने
(date-format गृहीत धरून) बांधलेला नाही, सर्वात जास्त चुकण्याची शक्यता असलेली जागा टाळण्यासाठी मुद्दाम.
"""
import datetime
import hashlib
import json as _json

import pandas as pd
import requests

BASE_URL = "https://api.shoonya.com/NorenWClientTP"

# Shoonya/NorenApi resolution-codes (मिनिटांत, "DAY" वगळता) — दस्तऐवजीकरणानुसार TPSeries असंच घेतं.
INTERVAL_TO_MINUTES = {
    "1minute": "1", "5minute": "5", "15minute": "15", "30minute": "30", "1hour": "60", "day": "DAY",
}


def _post(endpoint, jdata, jkey=None, timeout=10):
    """सर्व Shoonya API कॉल्सचं सामायिक स्वरूप — `jData=<json>&jKey=<token>` (form-urlencoded,
    JSON content-type नाही)."""
    payload = f"jData={_json.dumps(jdata)}"
    if jkey:
        payload += f"&jKey={jkey}"
    try:
        res = requests.post(f"{BASE_URL}/{endpoint}", data=payload, timeout=timeout)
        return res.json()
    except Exception as e:
        return {"stat": "Not_Ok", "emsg": str(e)}


def login(userid, password, factor2, vendor_code, api_secret, imei="abc1234"):
    """
    Shoonya/NorenApi login (`/QuickAuth`) — session token (susertoken) मिळवणे. रोज नव्याने करावं
    लागतं (इतर brokers प्रमाणेच token expire होतो).

    factor2 — सद्य ६-अंकी TOTP कोड, किंवा (Shoonya account सेटअप वेळी तसं ठरवलेलं असेल तर) जन्मतारीख
    (DD-MM-YYYY स्वरूपात).

    यशस्वी झाल्यास (combined_token, None) — combined token "userid:susertoken" स्वरूपात (Fyers च्या
    "app_id:access_token" पॅटर्नप्रमाणेच एकत्र साठवलेले — प्रत्येक पुढच्या API कॉलला दोन्हीही लागतात).
    """
    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    app_key_hash = hashlib.sha256(f"{userid}|{api_secret}".encode("utf-8")).hexdigest()
    jdata = {
        "apkversion": "1.0.0", "uid": userid, "pwd": pwd_hash, "factor2": factor2,
        "vc": vendor_code, "appkey": app_key_hash, "imei": imei, "source": "API",
    }
    resp = _post("QuickAuth", jdata)
    if resp.get("stat") != "Ok":
        return None, resp.get("emsg", f"अज्ञात एरर (response): {resp}")
    susertoken = resp.get("susertoken")
    if not susertoken:
        return None, f"susertoken response मध्ये सापडला नाही: {resp}"
    return f"{userid}:{susertoken}", None


def _split_token(access_token):
    """combined token ("userid:susertoken") दोन भागांत वेगळं करणे."""
    userid, _, susertoken = access_token.partition(":")
    return userid, susertoken


def search_scrip(access_token, exchange, search_text):
    """
    Shoonya `/SearchScrip` API — दिलेल्या शोध-मजकुरावरून जुळणारे trading-symbols/tokens ची यादी.
    Option Chain/candles साठी आवश्यक (exact strike/expiry चा symbol Shoonya कडूनच मिळवण्यासाठी,
    स्वतः date-format गृहीत धरून नाही).
    """
    userid, susertoken = _split_token(access_token)
    resp = _post("SearchScrip", {"uid": userid, "exch": exchange, "stext": search_text}, jkey=susertoken)
    if resp.get("stat") != "Ok":
        return []
    return resp.get("values", [])


def fetch_ltp_map(access_token, instrument_keys):
    """
    GetQuotes एकावेळी एकाच token साठी काम करतं (Upstox/Fyers च्या batch API सारखं नाही) — प्रत्येक
    key साठी वेगळा कॉल. instrument_keys "<exchange>|<token>" स्वरूपात अपेक्षित (उदा. "NFO|12345",
    search_scrip() कडून मिळालेले).
    """
    userid, susertoken = _split_token(access_token)
    result = {}
    for key in instrument_keys:
        exch, _, token = key.partition("|")
        resp = _post("GetQuotes", {"uid": userid, "exch": exch or "NFO", "token": token}, jkey=susertoken)
        result[key] = float(resp["lp"]) if resp.get("stat") == "Ok" and resp.get("lp") else None
    return result


def fetch_shoonya_option_chain(access_token, symbol, strike_count=20):
    """
    Shoonya `/GetOptionChain` API — raw_chain (Upstox/Fyers सारखंच nested, प्रति-strike एक dict)
    स्वरूपात रूपांतरित करून परत करणे.

    ⚠️ हा भाग विशेषतः Shoonya च्या स्वतःच्या API दस्तऐवजीकरण/Postman collection शी ताडून पडताळावा —
    response मधली exact field-names (`tsym`/`optt`/`strprc` वगैरे) गृहीत धरलेली आहेत, प्रत्यक्ष
    खात्यासह अजून पडताळलेली नाहीत.
    """
    userid, susertoken = _split_token(access_token)
    exch = "NFO"
    resp = _post(
        "GetOptionChain",
        {"uid": userid, "exch": exch, "tsym": symbol, "strprc": "", "cnt": str(strike_count)},
        jkey=susertoken,
    )
    values = resp.get("values", []) if isinstance(resp, dict) and resp.get("stat") == "Ok" else []

    strikes = {}
    for entry in values:
        try:
            strike = float(entry.get("strprc"))
        except (TypeError, ValueError):
            continue
        option_type = entry.get("optt")  # अपेक्षित: "CE" / "PE"
        if option_type not in ("CE", "PE"):
            continue
        if strike not in strikes:
            strikes[strike] = {"strike_price": strike, "call_options": None, "put_options": None}
        leg_data = {
            "instrument_key": f"{exch}|{entry.get('token')}",
            "market_data": {
                "ltp": float(entry.get("lp") or 0),
                "oi": int(float(entry.get("oi") or 0)),
                "volume": int(float(entry.get("v") or 0)),
            },
            "option_greeks": {},
        }
        if option_type == "CE":
            strikes[strike]["call_options"] = leg_data
        else:
            strikes[strike]["put_options"] = leg_data
    return [strikes[k] for k in sorted(strikes.keys())]


def fetch_candles(access_token, symbol_token, interval, lookback_days):
    """
    Shoonya `/TPSeries` (historical candles) API — DataFrame स्वरूपात (timestamp, open, high, low,
    close, volume). symbol_token "<exchange>|<token>" स्वरूपात (search_scrip() कडून मिळालेला).
    """
    userid, susertoken = _split_token(access_token)
    exch, _, token = symbol_token.partition("|")
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=lookback_days)
    jdata = {
        "uid": userid, "exch": exch or "NFO", "token": token,
        "st": str(int(start_time.timestamp())), "et": str(int(end_time.timestamp())),
        "intrv": INTERVAL_TO_MINUTES.get(interval, "5"),
    }
    resp = _post("TPSeries", jdata, jkey=susertoken)
    if not isinstance(resp, list) or not resp:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(resp)
        df = df.rename(columns={
            "time": "timestamp", "into": "open", "inth": "high", "intl": "low", "intc": "close", "intv": "volume",
        })
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def execute_order_leg_set(access_token, orders, trading_mode="LIVE"):
    """
    upstox_api.execute_order_leg_set()/fyers_api.execute_order_leg_set() च्याच PAPER/LIVE
    पॅटर्नने — वर्तन (SL/Target, Position Sizing) सर्व brokers वर एकसारखंच राहावं म्हणून.

    trading_mode == "LIVE": खरा Shoonya `/PlaceOrder` API कॉल — प्रत्येक leg साठी वेगळा (Upstox/
    Fyers च्या "Multi-Leg" endpoint सारखं एका कॉलमध्ये अनेक legs एकत्र स्वीकारणारं समर्पित API
    Shoonya कडे सार्वजनिक दस्तऐवजीकरणात आढळलं नाही — प्रत्येक leg स्वतंत्रपणे प्लेस केला जातो; एक
    leg अयशस्वी झाल्यास आधीच्या यशस्वी legs चे order_ids error सोबत परत दिले जातात, जेणेकरून
    कॉलिंग कोडला आंशिक-भरलेली (partially filled) स्थिती लगेच कळेल).

    trading_mode == "PAPER": कोणताही खरा API कॉल न करता, प्रत्येक leg ची सध्याची मार्केट LTP आणून,
    त्यावरच तात्काळ भरलेली (filled) सिम्युलेटेड ऑर्डर तयार करणे.
    """
    if trading_mode == "LIVE":
        userid, susertoken = _split_token(access_token)
        order_ids = []
        for o in orders:
            exch, _, token = o["instrument_token"].partition("|")
            # 🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — बॉट्स (dynamic_sr_instant_trader.py
            # इ.) निवडलेला broker कुठलाही असो, strike-निवडीसाठी नेहमी fetch_upstox_option_chain()
            # वापरतात — त्यामुळे इथे पोहोचणारा instrument_token नेहमी Upstox च्याच स्वरूपात असतो
            # ("NSE_FO|<upstox numeric token>"), आणि "trading_symbol" कधीच कुठूनच पाठवलं जात नाही.
            # आधी असं असूनही आपण exch="NSE_FO" (Shoonya ला "NFO" हवं) आणि tsym=<upstox token>
            # (Shoonya साठी निरर्थक संख्या, खरा trading symbol नाही) पाठवत राहायचो — प्रत्येक ऑर्डर
            # reject होण्याची शक्यता, किंवा त्याहून वाईट, चुकीच्या contract वर जाण्याचीही शक्यता होती.
            # Shoonya साठी स्वतःचा, वेगळा option-chain/strike-resolution मार्ग (search_scrip()/
            # fetch_shoonya_option_chain() वापरून) अजून bot-स्तरावर जोडलेला नाही — तोपर्यंत असा
            # स्पष्टपणे-चुकीचा instrument असेल, तर शांतपणे चुकीचा/अंदाजे order पाठवण्यापेक्षा, इथेच
            # स्पष्ट error देऊन थांबणं जास्त सुरक्षित.
            if not o.get("trading_symbol"):
                return 500, {
                    "status": "error",
                    "message": (
                        f"Shoonya LIVE order अडवला — instrument_token ('{o['instrument_token']}') Upstox च्या "
                        "स्वरूपात आहे, Shoonya चा स्वतःचा trading_symbol नाही (अजून जोडलेलं नाही). चुकीच्या/भलत्याच "
                        "contract वर order जाण्यापेक्षा हे थांबवणं सुरक्षित."
                    ),
                    "partial_order_ids": order_ids,
                }
            jdata = {
                "uid": userid, "actid": userid,
                "exch": exch or "NFO", "tsym": o["trading_symbol"],
                "qty": str(o["quantity"]), "prc": str(o.get("price", 0)),
                "prd": "M",  # NRML/Carry-Forward — codebase इतरत्र वापरत असलेल्या "D"/Delivery शी समतुल्य
                "trantype": "B" if o["transaction_type"] == "BUY" else "S",
                "prctyp": "MKT" if o.get("order_type", "MARKET") == "MARKET" else "LMT",
                "ret": "DAY",
            }
            resp = _post("PlaceOrder", jdata, jkey=susertoken)
            if resp.get("stat") == "Ok":
                order_ids.append(resp.get("norenordno"))
            else:
                return 500, {"status": "error", "message": resp.get("emsg", str(resp)), "partial_order_ids": order_ids}
        return 200, {"status": "success", "data": {"order_ids": order_ids}}

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
    """Shoonya `/Limits` API — उपलब्ध मार्जिन (float), किंवा मिळालं नाही तर None.
    ⚠️ response मधलं नेमकं field (`cash` गृहीत धरलेलं) प्रत्यक्ष खात्यासह पडताळून घ्या —
    Noren-आधारित brokers मध्ये margin-breakdown चं exact field कधी वेगळं असतं."""
    userid, susertoken = _split_token(access_token)
    resp = _post("Limits", {"uid": userid, "actid": userid}, jkey=susertoken)
    if resp.get("stat") != "Ok":
        return None
    try:
        return float(resp.get("cash", 0))
    except (TypeError, ValueError):
        return None
