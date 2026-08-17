"""All direct Upstox API calls: candles, option chain, orders, positions, funds, VIX, news, static IP proxy."""
import datetime
import json
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st

from config import get_ist_today

from signals import calculate_rsi, resample_to_1h


def fetch_timeframe_df(access_token, symbol, spot, interval_key):
    """
    'interval_key' नुसार योग्य पद्धतीने candles मिळवणे. '1hour' साठी थेट API कॉल न करता (तो पॅरामीटर
    Upstox कडून verified नाही) 30-मिनिटांचा डेटा resample करून तयार केला जातो — आधीच वापरलेली, सुरक्षित पद्धत.
    """
    if interval_key == "1hour":
        df_30m = fetch_candles(access_token, symbol, spot, interval="30minute")
        return resample_to_1h(df_30m)
    return fetch_candles(access_token, symbol, spot, interval=interval_key)


def fetch_candles(access_token, symbol, current_spot, interval="30minute", lookback_days=400):
    """
    किमान `lookback_days` (डीफॉल्ट ४००, म्हणजे ३६५+ दिवसांचा बफर) इतका इतिहास मिळवणारे इंजिन.
    Upstox चा प्रत्येक API कॉल ठराविक तारीख-रेंजच पुरवतो, त्यामुळे संपूर्ण कालावधी
    लहान "chunks" मध्ये विभागून, प्रत्येक chunk साठी वेगळा कॉल करून सर्व candles जोडले जातात.
    """
    try:
        allowed_intervals = ["1minute", "5minute", "15minute", "30minute", "day"]
        if interval not in allowed_intervals:
            interval = "30minute"

        instrument_key = "NSE_INDEX|Nifty 50" if symbol == "NIFTY" else "NSE_INDEX|Nifty Bank"
        encoded_key = urllib.parse.quote(instrument_key, safe="")

        interval_map = {
            "1minute": ("minutes", "1"),
            "5minute": ("minutes", "5"),
            "15minute": ("minutes", "15"),
            "30minute": ("minutes", "30"),
            "day": ("days", "1"),
        }
        unit, val = interval_map[interval]

        # प्रत्येक इंटरव्हलसाठी एका API कॉलमध्ये सुरक्षितपणे किती दिवस मागवायचे
        # (Upstox v3 अतिशय मोठ्या रेंजसाठी काहीवेळा त्रुटी देतो, म्हणून intraday इंटरव्हल्ससाठी लहान तुकडे)
        chunk_days_map = {"1minute": 30, "5minute": 45, "15minute": 60, "30minute": 90, "day": lookback_days}
        chunk_days = chunk_days_map.get(interval, 90)

        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}

        today = get_ist_today()
        overall_from = today - datetime.timedelta(days=lookback_days)

        hist_candles = []
        chunk_to = today
        while chunk_to > overall_from:
            chunk_from = max(overall_from, chunk_to - datetime.timedelta(days=chunk_days))
            to_str = chunk_to.strftime("%Y-%m-%d")
            from_str = chunk_from.strftime("%Y-%m-%d")

            hist_url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/{unit}/{val}/{to_str}/{from_str}"
            try:
                res_hist = requests.get(hist_url, headers=headers, timeout=15)
                if res_hist.status_code == 200:
                    chunk_candles = res_hist.json().get("data", {}).get("candles", [])
                    hist_candles.extend(chunk_candles)
                # रेंज-मर्यादेच्या एरर्स शांतपणे वगळल्या जातात जेणेकरून जुना डेटा
                # उपलब्ध नसला तरी बाकीचा डेटा दिसत राहील
            except requests.exceptions.RequestException:
                pass

            # पुढचा (जुना) chunk — एक दिवस मागे सरकवून overlap टाळणे
            chunk_to = chunk_from - datetime.timedelta(days=1)

        # आजचा live/intraday data (V3)
        intraday_url = f"https://api.upstox.com/v3/historical-candle/intraday/{encoded_key}/{unit}/{val}"
        intraday_candles = []
        try:
            res_intra = requests.get(intraday_url, headers=headers, timeout=10)
            if res_intra.status_code == 200:
                intraday_candles = res_intra.json().get("data", {}).get("candles", [])
            else:
                st.warning(f"Intraday API failed: {res_intra.status_code} - {res_intra.text}")
        except requests.exceptions.RequestException as e:
            st.warning(f"Intraday API अपवाद: {str(e)}")

        all_candles = hist_candles + intraday_candles

        if not all_candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "oi", "rsi"])

        df_candles = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
        df_candles["timestamp"] = pd.to_datetime(df_candles["timestamp"])

        # सर्व chunks + intraday मध्ये overlap होणारे duplicate timestamps काढून टाकणे
        df_candles = df_candles.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume", "oi"]:
            df_candles[col] = pd.to_numeric(df_candles[col], errors="coerce")

        df_candles["rsi"] = calculate_rsi(df_candles)

        return df_candles

    except Exception as e:
        st.error(f"⚠️ एरर आला: {str(e)}")
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "oi", "rsi"])

def fetch_long_history(access_token, symbol="NIFTY", years=20, chunk_years=3, progress_callback=None):
    """
    Upstox च्या V3 Historical Candle API नुसार Daily डेटा जानेवारी 2000 पासून उपलब्ध आहे — त्यामुळे
    जास्तीत जास्त 'years' वर्षांचा (किंवा जानेवारी 2000 पर्यंत, जे आधी येईल ते) Daily डेटा मागवता येतो.
    एका मोठ्या रिक्वेस्टऐवजी (जी response-size मर्यादेवर आदळू शकते) chunk_years च्या छोट्या तुकड्यांत मागवलं जातं.
    """
    instrument_key = "NSE_INDEX|Nifty 50" if symbol == "NIFTY" else "NSE_INDEX|Nifty Bank"
    encoded_key = urllib.parse.quote(instrument_key, safe="")
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}

    today = get_ist_today()
    earliest_available = datetime.date(2000, 1, 1)
    target_start = max(earliest_available, today - datetime.timedelta(days=years * 365))

    all_candles = []
    chunk_end = today
    total_span_days = (today - target_start).days or 1
    while chunk_end > target_start:
        chunk_start = max(target_start, chunk_end - datetime.timedelta(days=chunk_years * 365))
        url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/days/1/{chunk_end.strftime('%Y-%m-%d')}/{chunk_start.strftime('%Y-%m-%d')}"
        try:
            res = requests.get(url, headers=headers, timeout=25)
            if res.status_code == 200:
                candles = res.json().get("data", {}).get("candles", [])
                all_candles.extend(candles)
        except requests.exceptions.RequestException:
            pass  # हा chunk अयशस्वी झाला तरी बाकीचे चालू ठेवणे

        if progress_callback:
            done_days = (today - chunk_start).days
            progress_callback(min(done_days / total_span_days, 1.0), chunk_start, chunk_end)

        chunk_end = chunk_start - datetime.timedelta(days=1)

    if not all_candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume", "oi"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def fetch_candles_date_range(access_token, symbol, interval, from_date, to_date):
    """
    दिलेल्या अचूक (from_date ते to_date) कालावधीसाठी candles मागवणे — fetch_candles() नेहमी 'आजपर्यंत'
    मागे मोजतं, पण इथे भूतकाळातील कोणताही निश्चित कालावधी (आजपासून सुरू न होणाराही) निवडता येतो —
    Backtest मध्ये युजरने दिलेल्या date range साठी आवश्यक.
    """
    instrument_key = "NSE_INDEX|Nifty 50" if symbol == "NIFTY" else "NSE_INDEX|Nifty Bank"
    encoded_key = urllib.parse.quote(instrument_key, safe="")
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}

    interval_map = {
        "1minute": ("minutes", "1"), "5minute": ("minutes", "5"), "15minute": ("minutes", "15"),
        "30minute": ("minutes", "30"), "day": ("days", "1"),
    }
    unit, val = interval_map.get(interval, ("days", "1"))
    chunk_days_map = {"1minute": 30, "5minute": 45, "15minute": 60, "30minute": 90, "day": 1095}
    chunk_days = chunk_days_map.get(interval, 90)

    all_candles = []
    chunk_end = to_date
    while chunk_end > from_date:
        chunk_start = max(from_date, chunk_end - datetime.timedelta(days=chunk_days))
        url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/{unit}/{val}/{chunk_end.strftime('%Y-%m-%d')}/{chunk_start.strftime('%Y-%m-%d')}"
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                candles = res.json().get("data", {}).get("candles", [])
                all_candles.extend(candles)
        except requests.exceptions.RequestException:
            pass  # हा chunk अयशस्वी झाला तरी बाकीचे चालू ठेवणे
        chunk_end = chunk_start - datetime.timedelta(days=1)

    if not all_candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume", "oi"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def upload_to_google_drive(file_bytes, filename, mime_type="text/csv"):
    """
    Google Drive Service Account वापरून फाईल अपलोड करणे.
    सेटअप (.streamlit/secrets.toml):
        [gdrive]
        service_account_json = '''<संपूर्ण service account JSON की इथे>'''
        folder_id = "<target Drive फोल्डरचा ID>"   # ऐच्छिक — नसेल तर Drive च्या root मध्ये अपलोड होईल
    हा फोल्डर आधी त्या service account च्या ईमेल आयडीसोबत (Editor अ‍ॅक्सेससह) शेअर केलेला असणे आवश्यक आहे,
    अन्यथा अपलोड अयशस्वी होईल (service account कडे स्वतःची कोणतीही Drive जागा नसते).
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload

        gdrive_cfg = st.secrets.get("gdrive", {})
        sa_json_str = gdrive_cfg.get("service_account_json")
        if not sa_json_str:
            return False, "Streamlit secrets मध्ये [gdrive] service_account_json सापडला नाही."
        sa_info = json.loads(sa_json_str)
        folder_id = gdrive_cfg.get("folder_id")

        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        service = build("drive", "v3", credentials=creds)
        file_metadata = {"name": filename}
        if folder_id:
            file_metadata["parents"] = [folder_id]
        media = MediaInMemoryUpload(file_bytes, mimetype=mime_type, resumable=True)
        uploaded = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()
        return True, uploaded.get("webViewLink") or uploaded.get("id")
    except ImportError:
        return False, "Google Drive लायब्ररी उपलब्ध नाहीत — requirements.txt मध्ये 'google-api-python-client', 'google-auth' जोडा."
    except Exception as e:
        return False, f"अपलोड अयशस्वी: {e}"

def fetch_upstox_option_chain(access_token, symbol, expiry_index=0):
    instrument_key = "NSE_INDEX|Nifty 50" if symbol == "NIFTY" else "NSE_INDEX|Nifty Bank"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
    
    try:
        expiry_url = f"https://api.upstox.com/v2/option/contract?instrument_key={requests.utils.quote(instrument_key)}"
        exp_res = requests.get(expiry_url, headers=headers, timeout=8)
        
        target_expiry = None
        if exp_res.status_code == 200:
            exp_data = exp_res.json().get("data", [])
            if exp_data:
                expiries = sorted(list(set([item.get("expiry") for item in exp_data if item.get("expiry")])))
                if expiries:
                    idx = expiry_index if expiry_index < len(expiries) else len(expiries) - 1
                    target_expiry = expiries[idx]
                    
        if not target_expiry:
            target_expiry = get_ist_today().strftime("%Y-%m-%d")
            
        url = f"https://api.upstox.com/v2/option/chain?instrument_key={requests.utils.quote(instrument_key)}&expiry_date={target_expiry}"
        res = requests.get(url, headers=headers, timeout=8)
        
        if res.status_code == 200:
            res_json = res.json()
            data = res_json.get("data", [])
            if isinstance(data, dict):
                data = list(data.values())
            if data:
                return data, "SUCCESS"
            else:
                return None, f"API रेस्पॉन्स रिकामा आहे (Expiry: {target_expiry})"
        elif res.status_code == 401:
            return None, "Unauthorized (401): टोकन एक्सपायर किंवा चुकीचे आहे"
        else:
            return None, f"API Error Code: {res.status_code} - {res.text}"
    except Exception as e:
        return None, f"Exception: {str(e)}"

def fetch_market_news(max_items_per_feed=5):
    """
    राष्ट्रीय (भारत) व आंतरराष्ट्रीय मार्केट/बिझनेस न्यूज RSS फीड्समधून मिळवणे.
    कोणताही API key लागत नाही. एखादा फीड अयशस्वी झाला तरी बाकीचे दाखवले जातात (graceful degradation).
    """
    feeds = [
        {"name": "Economic Times Markets (भारत)", "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
        {"name": "BBC Business (आंतरराष्ट्रीय)", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    ]
    results = []
    for feed in feeds:
        try:
            res = requests.get(feed["url"], timeout=6, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code != 200:
                continue
            root = ET.fromstring(res.content)
            headlines = []
            for item in root.findall(".//item")[:max_items_per_feed]:
                title_el = item.find("title")
                pubdate_el = item.find("pubDate")
                title = title_el.text.strip() if title_el is not None and title_el.text else None
                pubdate = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else ""
                if title:
                    headlines.append({"title": title, "pubdate": pubdate})
            if headlines:
                results.append({"source": feed["name"], "headlines": headlines})
        except Exception:
            continue  # हा फीड अयशस्वी — पुढच्या फीडकडे जाणे, संपूर्ण रिपोर्ट थांबवायचे नाही
    return results

def fetch_india_vix(access_token):
    """India VIX (instrument key: NSE_INDEX|India VIX) चा सध्याचा LTP मिळवणे."""
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
        key = urllib.parse.quote("NSE_INDEX|India VIX", safe="")
        url = f"https://api.upstox.com/v3/market-quote/ltp?instrument_key={key}"
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("data", {})
            for v in data.values():
                if "last_price" in v:
                    return float(v["last_price"])
        return None
    except Exception:
        return None

def get_available_margin(access_token):
    """Equity segment मधील उपलब्ध ट्रेडिंग मार्जिन (v2 Get Funds and Margin API)."""
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
        url = "https://api.upstox.com/v2/user/get-funds-and-margin?segment=SEC"
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            eq = res.json().get("data", {}).get("equity", {})
            return float(eq.get("available_margin", 0))
        return None
    except Exception:
        return None

def fetch_ltp_map(access_token, instrument_keys):
    """दिलेल्या instrument keys ची सद्य LTP्स एका डिक्शनरीमध्ये (v3 LTP API)."""
    if not instrument_keys:
        return {}
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
        keys_param = urllib.parse.quote(",".join(instrument_keys), safe=",|")
        url = f"https://api.upstox.com/v3/market-quote/ltp?instrument_key={keys_param}"
        res = requests.get(url, headers=headers, timeout=8)
        result = {}
        if res.status_code == 200:
            data = res.json().get("data", {})
            for v in data.values():
                tok = v.get("instrument_token")
                if tok:
                    result[tok] = float(v.get("last_price", 0))
        return result
    except Exception:
        return {}

def get_static_ip_proxy_url():
    """
    Streamlit secrets मधून Static IP Proxy URL वाचणे (उदा. QuotaGuard Static, Fixie, इ.).
    .streamlit/secrets.toml मध्ये असं ठेवा:
        [proxy]
        url = "http://username:password@static.quotaguard.com:9293"
    Upstox च्या Static IP नियमामुळे फक्त ऑर्डर-प्लेसमेंट कॉल्ससाठीच हा प्रॉक्सी वापरला जातो —
    funds/candles/option chain सारख्या इतर API ना Static IP लागत नाही.
    """
    try:
        return st.secrets.get("proxy", {}).get("url", "").strip() or None
    except Exception:
        return None

def check_proxy_egress_ip(proxy_url, timeout=8):
    """प्रॉक्सीमधून सध्या कोणता public IP बाहेर पडतोय ते तपासणे (सेटअप डीबग करण्यासाठी)."""
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        res = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=timeout)
        if res.status_code == 200:
            return res.json().get("ip")
        return None
    except Exception:
        return None

def get_registered_static_ips(access_token):
    """Upstox कडे सध्या नोंदवलेले Static IPs (primary/secondary) मिळवणे."""
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
        res = requests.get("https://api.upstox.com/v2/user/ip", headers=headers, timeout=8)
        if res.status_code == 200:
            return res.json().get("data", {})
        return None
    except Exception:
        return None

def fetch_broker_positions(access_token):
    """Upstox कडून सद्य (आजच्या) पोझिशन्स आणणे — Portfolio API सुद्धा काही केसेसमध्ये Static IP मागू शकतो,
    त्यामुळे इथेही (उपलब्ध असल्यास) तोच Static IP Proxy वापरला जातो."""
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
        proxy_url = get_static_ip_proxy_url()
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        res = requests.get(
            "https://api.upstox.com/v2/portfolio/short-term-positions",
            headers=headers, timeout=10, proxies=proxies,
        )
        if res.status_code == 200:
            return res.json().get("data", [])
        return None
    except Exception:
        return None

def execute_order_leg_set(access_token, orders, trading_mode):
    """
    सर्व ऑर्डर-प्लेसमेंट याच एका फंक्शनमधून जाते, जेणेकरून LIVE आणि PAPER मध्ये वर्तन (SL/Target,
    Circuit Breaker, Position Sizing सगळं) एकसारखंच राहील — फक्त ऑर्डर प्रत्यक्षात Upstox कडे
    जाते की नाही, इतकाच फरक असतो.

    trading_mode == "LIVE": खरा Upstox Multi Order API कॉल (Static IP Proxy मार्गे).
    trading_mode == "PAPER": कोणताही खरा API कॉल न करता, प्रत्येक leg ची सध्याची मार्केट LTP आणून
    त्यावरच तात्काळ भरलेली (filled) सिम्युलेटेड ऑर्डर तयार करणे — त्यामुळे किंमती खऱ्याच बाजारातल्या
    असतात, फक्त पैसे हलत नाहीत.
    """
    if trading_mode == "LIVE":
        return place_multi_leg_order(access_token, orders)

    instrument_keys = [o["instrument_token"] for o in orders]
    ltp_map = fetch_ltp_map(access_token, instrument_keys)
    if any(ltp_map.get(k) is None for k in instrument_keys):
        return None, {"status": "error", "errors": [{"message": "Paper fill साठी एका किंवा अधिक legs ची LTP मिळाली नाही."}]}

    batch_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    order_ids = [f"PAPER-{batch_id}-{i}" for i in range(len(orders))]
    return 200, {"status": "success", "data": {"order_ids": order_ids}, "paper_fills": ltp_map}

def place_multi_leg_order(access_token, orders):
    """
    Upstox v2 Multi Order API — सर्व BUY (हेज) आधी, नंतर सर्व SELL एक्झिक्यूट होतात.
    Upstox च्या Static IP नियमामुळे (UDAPI1154) हा कॉल — Proxy कॉन्फिगर केलेला असल्यास — त्या
    Static IP Proxy मधूनच पाठवला जातो, कारण ऑर्डर-प्लेसमेंट API साठी नोंदणीकृत Static IP सक्तीचा आहे.
    """
    try:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token.strip()}",
        }
        proxy_url = get_static_ip_proxy_url()
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        url = "https://api.upstox.com/v2/order/multi/place"
        res = requests.post(url, headers=headers, json=orders, timeout=15, proxies=proxies)
        try:
            body = res.json()
        except Exception:
            body = {"raw": res.text}
        return res.status_code, body
    except Exception as e:
        return None, {"error": str(e)}

def fetch_next_expiry_option_chain(access_token, symbol):
    """
    दुसऱ्या (पुढच्या) expiry चा option chain मिळवणे — Rollover Analysis साठी.
    fetch_upstox_option_chain मध्ये आधीच वापरलेला, verified expiry-listing + chain-fetch पॅटर्नच पुन्हा वापरला आहे,
    फक्त expiries[0] ऐवजी expiries[1] निवडला जातो.
    """
    instrument_key = "NSE_INDEX|Nifty 50" if symbol == "NIFTY" else "NSE_INDEX|Nifty Bank"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
    try:
        expiry_url = f"https://api.upstox.com/v2/option/contract?instrument_key={requests.utils.quote(instrument_key)}"
        exp_res = requests.get(expiry_url, headers=headers, timeout=8)
        if exp_res.status_code != 200:
            return None, None
        exp_data = exp_res.json().get("data", [])
        expiries = sorted({item.get("expiry") for item in exp_data if item.get("expiry")})
        if len(expiries) < 2:
            return None, None  # पुढची expiry उपलब्ध नाही (उदा. महिन्याची शेवटची expiry सिरीज)
        next_expiry = expiries[1]
        url = f"https://api.upstox.com/v2/option/chain?instrument_key={requests.utils.quote(instrument_key)}&expiry_date={next_expiry}"
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if isinstance(data, dict):
                data = list(data.values())
            return data, next_expiry
        return None, None
    except Exception:
        return None, None
