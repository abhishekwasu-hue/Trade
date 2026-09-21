"""
resolve_mcx_futures_instruments.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — MCX Futures trading (CRUDEOIL/NATURALGAS/GOLD/SILVER/
COPPER) जोडण्याआधीचं पहिलं, सुरक्षित पाऊल. lot_size/tick_size/instrument_key/expiry स्वतः अंदाजाने
(training data वरून, कधीही न बदलणारे गृहीत धरून) कोडमध्ये हार्डकोड करणं धोकादायक आहे — हे आकडे प्रत्यक्ष
contract प्रमाणे बदलतात आणि चुकलं तर थेट खऱ्या पैशावर परिणाम होतो (established Shoonya integration मध्ये
आधीच वापरलेला हाच नियम — "स्वतः अंदाजाने बांधलेला नाही, brokerच्याच API कडूनच मिळवलेला").

हा script फक्त **वाचतो** (कुठलाही order/trade नाही) — Upstox च्या अधिकृत Search Instruments API
(https://api.upstox.com/v2/instruments/search) कडून, प्रत्येक commodity चा सध्याचा **"continuous"**
Futures contract (अजून expire न झालेल्यांपैकी सर्वात जवळचा, front-month — हार्डकोडेड expiry नाही,
कधीही चालवलं तरी आपोआप योग्य/चालू contract) — खरा instrument_key/trading_symbol/lot_size/tick_size/
expiry — मिळवून दाखवतो. पुढच्या टप्प्यात (MCX Futures Trader strategy बांधताना) हीच पद्धत (प्रत्येक
cron-run ला स्वतः पुन्हा resolve करणे) वापरली जाईल, जेणेकरून महिना बदलला/contract expire झाला तरी
bot आपोआप पुढच्या contract वर roll होईल — कुठलाही मॅन्युअल बदल न करता.

चालवणे (VPS वर, जिथे रोजचा वैध Upstox token Supabase मध्ये आधीच साठवलेला आहे):
    python3 resolve_mcx_futures_instruments.py
    # किंवा स्वतःचा token देऊन:
    python3 resolve_mcx_futures_instruments.py --token <UPSTOX_TOKEN>
"""
import argparse

import requests

import cloud_db
from config import get_ist_today

# 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुरुवातीची ५ — सर्वात जास्त liquidity/volume असलेली MCX
# commodities, options trading साठी सर्वात व्यवहार्य.
MCX_FUTURES_SYMBOLS = ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"]


def resolve_symbol(access_token, symbol):
    """एका commodity साठी सध्याचं ("continuous" — कायम आपोआप रोल होणारं, हार्डकोडेड expiry नाही)
    Futures contract — अजून expire न झालेल्या सर्व contracts पैकी सर्वात जवळचा (front-month) — मिळवणे.
    🎓 Upstox च्या `expiry=current_month` keyword-filter ऐवजी मुद्दाम client-side (expiry >= आज,
    क्रमवारीत पहिला) फिल्टर वापरला आहे — महिन्याच्या शेवटी "current_month" contract आधीच expire
    झालेला/जवळजवळ झालेला असू शकतो, तेव्हा keyword-filter चुकीचा (आधीच्याच महिन्याचा) contract देऊ शकतो;
    हे कधीही चालवलं तरी नेहमी खराखुरा, ट्रेड करण्यायोग्य पुढचा contract देतं, तारखेची पर्वा न करता.
    रिटर्न: (यशस्वी_का, तपशील_dict_किंवा_error_संदेश)."""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}
    params = {
        "query": symbol, "exchanges": "MCX", "instrument_types": "FUT",
        "page_number": 1, "records": 30,
    }
    try:
        res = requests.get("https://api.upstox.com/v2/instruments/search", headers=headers, params=params, timeout=10)
    except Exception as exc:
        return False, f"विनंती पाठवताना चूक: {exc}"
    if res.status_code != 200:
        return False, f"HTTP {res.status_code}: {res.text[:300]}"

    results = res.json().get("data", [])
    today_str = get_ist_today().isoformat()
    # exact symbol-नाव जुळणारे, आणि अजून expire न झालेलेच (आजच्या तारखेच्या आधीचे कधीच नाहीत) निवडणे.
    matches = [
        r for r in results
        if r.get("trading_symbol", "").upper().startswith(symbol.upper())
        and (r.get("expiry") or "") >= today_str
    ]
    if not matches:
        return False, f"'{symbol}' साठी अजून expire न झालेला कुठलाही MCX Futures contract सापडला नाही (raw results: {len(results)})"

    # expiry नुसार क्रमवारी — सर्वात जवळचा (सध्याचा, "continuous") contract निवडणे.
    matches.sort(key=lambda r: r.get("expiry", ""))
    nearest = matches[0]
    return True, {
        "symbol": symbol,
        "trading_symbol": nearest.get("trading_symbol"),
        "instrument_key": nearest.get("instrument_key"),
        "lot_size": nearest.get("lot_size"),
        "tick_size": nearest.get("tick_size"),
        "expiry": nearest.get("expiry"),
        "freeze_quantity": nearest.get("freeze_quantity"),
        "all_upcoming_expiries": [m.get("expiry") for m in matches],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    args = parser.parse_args()

    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        raise SystemExit(1)

    print("MCX Futures — सध्याचे continuous (front-month) contracts (Upstox Search Instruments API कडून थेट):\n")
    any_failed = False
    for sym in MCX_FUTURES_SYMBOLS:
        ok, result = resolve_symbol(token, sym)
        if not ok:
            print(f"❌ {sym}: {result}")
            any_failed = True
            continue
        print(f"✅ {sym}")
        print(f"   trading_symbol   : {result['trading_symbol']}")
        print(f"   instrument_key   : {result['instrument_key']}")
        print(f"   lot_size         : {result['lot_size']}")
        print(f"   tick_size        : {result['tick_size']}")
        print(f"   expiry           : {result['expiry']}")
        print(f"   freeze_quantity  : {result['freeze_quantity']}")
        print(f"   पुढच्या expiries : {result['all_upcoming_expiries']}")
        print()

    if any_failed:
        raise SystemExit(1)
