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
import datetime

import requests

import cloud_db
from config import get_ist_today

# 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुरुवातीची ५ — सर्वात जास्त liquidity/volume असलेली MCX
# commodities, options trading साठी सर्वात व्यवहार्य.
MCX_FUTURES_SYMBOLS = ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"]

# 🎓 Contract roll (वापरकर्त्याचा निर्णय, सर्व commodities) — नियम **ट्रेडिंग दिवसांत**: front-month contract चे उरलेले ट्रेडिंग दिवस
# (आज ते expiry, दोन्ही धरून; बघा trading_days_left) ≤ roll दिवस झाले की पुढचा contract. डीफॉल्ट 6 (MCX Futures सेटिंग
# `roll_trading_days_before_expiry`). हा नियम इथेच (एकाच ठिकाणी) — trader, zones refresh, margin, MCX पान, readiness check — सगळे
# हाच resolver वापरतात, त्यामुळे सर्व ठिकाणी तोच contract.
ROLL_TRADING_DAYS_BEFORE_EXPIRY = 6

# 🎓 MCX staggered delivery (tender) period — compulsory-delivery contracts मध्ये expiry धरून शेवटचे इतके ट्रेडिंग दिवस. या काळात MCX
# "delivery period margin" लावतो (higher of 25% किंवा 3% + 5-day 99% VaR — सामान्य margin च्या जवळपास दुप्पट) आणि broker (Upstox सकट)
# period सुरू होण्याआधी positions square-off करतात. स्रोत: MCX circular MCX/TRD/383/2025 (4 Aug 2025) — Precious Metals 5 ⇒ 3 दिवस
# (GOLD Aug-2026 expiry पासून, SILVER Sep-2026 पासून); Base Metals 5 ⇒ 3 दिवस (COPPER Jan-2025 पासून). CRUDEOIL/NATURALGAS cash-settled
# (delivery नाही) ⇒ 0. नवीन circular आल्यास हा तक्ता बदलायचा.
STAGGERED_DELIVERY_TRADING_DAYS = {"GOLD": 3, "SILVER": 3, "COPPER": 3}


def trading_days_left(today, expiry):
    """[today, expiry] मधले सोम–शुक्र दिवस (दोन्ही टोकं धरून; आज weekend असेल तर तो मोजला जात नाही). expiry गेलेली ⇒ 0.
    MCX सुट्ट्यांची यादी repo मध्ये नाही — त्या मोजल्या जातात (म्हणून roll दिवसांत 1-2 दिवसांची सवलत ठेवली आहे)."""
    if expiry is None or expiry < today:
        return 0
    n, d = 0, today
    while d <= expiry:
        if d.weekday() < 5:
            n += 1
        d += datetime.timedelta(days=1)
    return n


def effective_roll_days(symbol, roll_days):
    """roll दिवस कधीच staggered delivery period (+1 ट्रेडिंग दिवस) पेक्षा कमी नाहीत — period सुरू होण्याआधी किमान 1 ट्रेडिंग दिवस roll."""
    return max(int(roll_days), STAGGERED_DELIVERY_TRADING_DAYS.get(symbol.upper(), 0) + 1)


def _roll_days_setting(symbol):
    """MCX Futures सेटिंग `roll_trading_days_before_expiry` (Supabase); मिळाली नाही ⇒ डीफॉल्ट."""
    try:
        return int(cloud_db.get_strategy_settings("mcx_futures", symbol).get("roll_trading_days_before_expiry", ROLL_TRADING_DAYS_BEFORE_EXPIRY))
    except Exception:
        return ROLL_TRADING_DAYS_BEFORE_EXPIRY


def resolve_symbol(access_token, symbol, roll_days=None):
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
    symbol_upper = symbol.upper()

    # 🎓 वापरकर्त्याने प्रत्यक्ष VPS वर चालवून सापडवलेली गंभीर bug — आधीचा `startswith()` फिल्टर
    # "GOLD" शोधताना "GOLDTEN"/"GOLDM"/"GOLDGUINEA"/"GOLDPETAL" सारखे पूर्णपणे वेगळे (वेगळा
    # lot_size/tick_size असलेले) commodity contracts सुद्धा जुळवायचा — trading_symbol नुसतं त्याच
    # अक्षरांनी सुरू होतो इतकंच पुरेसं मानलं जायचं. नंतर फक्त expiry नुसार क्रमवारी लावून सर्वात
    # जवळचा निवडायचा — म्हणजे नेमका कोणता contract निवडला जाईल हे कुठल्या variant चा expiry आधी
    # येतो या (कधीही बदलू शकणाऱ्या) योगायोगावर अवलंबून होतं. प्रत्यक्ष चाचणीत GOLD साठी GOLDTEN
    # (weekly, वेगळा lot_size) निवडला गेला — वापरकर्त्याला अपेक्षित plain GOLD नाही.
    # आता trading_symbol चा " FUT" च्या आधीचा भाग query symbol शी **तंतोतंत** (फक्त prefix नाही)
    # जुळायलाच हवा — Upstox चं MCX trading_symbol स्वरूप कायम "<NAME> FUT <DD> <MON> <YY>" असंच आहे.
    def _exact_name(trading_symbol):
        return (trading_symbol or "").upper().split(" FUT")[0].strip()

    matches = [
        r for r in results
        if _exact_name(r.get("trading_symbol")) == symbol_upper
        and (r.get("expiry") or "") >= today_str
    ]
    if not matches:
        # डीबग-सुसंगत इशारा — loose (नुसत्या prefix-जुळणाऱ्या) नावांपैकी काय सापडलं ते दाखवणे,
        # जेणेकरून खरंच plain "GOLD" सारखा exact contract अस्तित्वातच नसेल (उदा. Upstox/MCX ने नाव
        # बदललं असेल), तर पुढचं पाऊल (कुठलं exact नाव वापरायचं) लगेच ठरवता येईल.
        loose_names = sorted(set(
            r.get("trading_symbol", "") for r in results
            if r.get("trading_symbol", "").upper().startswith(symbol_upper)
        ))
        loose_hint = f" — जवळची (prefix-जुळणारी) नावं सापडली: {', '.join(loose_names[:10])}" if loose_names else ""
        return False, f"'{symbol}' साठी अजून expire न झालेला कुठलाही exact MCX Futures contract सापडला नाही (raw results: {len(results)}){loose_hint}"

    # expiry नुसार क्रमवारी — सर्वात जवळचा (सध्याचा, "continuous") contract; पण त्याचे उरलेले ट्रेडिंग दिवस ≤ roll दिवस असतील तर पुढचा
    # (बघा ROLL_TRADING_DAYS_BEFORE_EXPIRY / effective_roll_days). पुढचा यादीत नसेल तर नाईलाजाने जवळचाच (rolled=False, roll_pending=True).
    matches.sort(key=lambda r: r.get("expiry", ""))
    today = get_ist_today()
    roll_days = effective_roll_days(symbol, _roll_days_setting(symbol) if roll_days is None else roll_days)

    def _tdl(r):
        try:
            return trading_days_left(today, datetime.date.fromisoformat(str(r.get("expiry"))[:10]))
        except ValueError:
            return None

    front = matches[0]
    chosen = next((r for r in matches if (_tdl(r) is not None and _tdl(r) > roll_days)), None)
    rolled = chosen is not None and chosen is not front
    nearest = chosen or front
    return True, {
        "symbol": symbol,
        "trading_symbol": nearest.get("trading_symbol"),
        "instrument_key": nearest.get("instrument_key"),
        "lot_size": nearest.get("lot_size"),
        "tick_size": nearest.get("tick_size"),
        "expiry": nearest.get("expiry"),
        "freeze_quantity": nearest.get("freeze_quantity"),
        "all_upcoming_expiries": [m.get("expiry") for m in matches],
        "trading_days_to_expiry": _tdl(nearest),
        "rolled": rolled,                                         # जवळचा (front-month) contract roll-नियमामुळे वगळला
        "roll_pending": chosen is None and (_tdl(front) or 0) <= roll_days,
        "front_trading_symbol": front.get("trading_symbol"),
        "front_expiry": front.get("expiry"),
        "front_trading_days_to_expiry": _tdl(front),
        "roll_trading_days_before_expiry": roll_days,
        "staggered_delivery_trading_days": STAGGERED_DELIVERY_TRADING_DAYS.get(symbol.upper(), 0),
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
        if result.get("rolled"):
            print(f"   🔄 roll          : {result['front_trading_symbol']} (expiry {result['front_expiry']}, उरलेले ट्रेडिंग दिवस "
                  f"{result['front_trading_days_to_expiry']} ≤ {result['roll_trading_days_before_expiry']}) — पुढचा contract निवडला")
        print()

    if any_failed:
        raise SystemExit(1)
