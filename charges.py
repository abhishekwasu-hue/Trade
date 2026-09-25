"""
charges.py
------------------------------
वास्तविक ट्रेडिंग शुल्क (brokerage + सरकारी/एक्सचेंज शुल्क) मोजण्यासाठी.

🎓 वापरकर्त्याने मागितलेली सुधारणा ("Upstox brokerage calculator वापरून actual brokerage काढा",
नंतर "Stocko आणि Fyers साठी पण actual calculator लावता येईल का", नंतर "Shoonya che pn kra update") —
आधी (rough अंदाज टप्प्यात) brokerage + STT + Exchange Txn Charge + SEBI Turnover Fee + Stamp Duty +
GST हे सहा घटक असलेला अचूक हिशोब वापरकर्त्याला जास्त/अनपेक्षित वाटला आणि पडताळणं अवघड झालं होतं,
त्यामुळे तेव्हा तात्पुरता एक निश्चित ढोबळ ₹25/ऑर्डर (all-inclusive) अंदाज वापरला गेला. आता **Upstox,
Fyers, Shoonya, आणि Stocko** — म्हणजे app मध्ये असलेले सर्वच ब्रोकर — ऑर्डर्ससाठी प्रत्येक ऑर्डरचं
turnover (quantity × price) वापरून, त्या-त्या ब्रोकरच्या स्वतःच्या प्रकाशित brokerage calculator
(upstox.com/brokerage-charges, fyers.in/charges-list, shoonya.com/pricing) + सरकारी/एक्सचेंज
दरांवरून (ऑक्टोबर-2024 च्या STT/Exchange Transaction Charge फेरबदलानंतरचे, सद्यस्थितीतले सर्वात
अलीकडचे ज्ञात दर) खरं शुल्क मोजलं जातं — segment नुसार (NSE Index/Equity Options वि. MCX Commodity
Futures) वेगवेगळे दर, कारण ते खरोखरच वेगळे आहेत:
  • STT/CTT, Exchange Txn Charge, SEBI Turnover Fee, Stamp Duty (_STATUTORY_RATES) — हे सरकारी/
    एक्सचेंज-निर्धारित असल्याने **सर्व ब्रोकर्ससाठी सारखेच**:
    - Options (NIFTY/BANKNIFTY/SENSEX): STT 0.1% (फक्त SELL, premium वर); Exchange Txn Charge
      0.035% (दोन्ही बाजू); SEBI Turnover Fee 0.0001% (दोन्ही बाजू); Stamp Duty 0.003% (फक्त BUY).
    - MCX Commodity Futures (CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER): CTT 0.01% (फक्त SELL);
      Exchange Txn Charge 0.0021% (दोन्ही बाजू); SEBI Turnover Fee 0.0001% (दोन्ही बाजू); Stamp
      Duty 0.002% (फक्त BUY).
  • brokerage (_BROKERAGE_RATES) — हाच एक घटक ब्रोकरनुसार वेगळा:
    - Upstox: Options फ्लॅट ₹20/executed order; Commodity Futures ₹20 किंवा 0.05% जे कमी.
    - Fyers: Options फ्लॅट ₹20/executed order (Upstox सारखंच); Commodity Futures ₹20 किंवा 0.03%
      जे कमी (Upstox पेक्षा किंचित कमी %).
    - Shoonya: Options फ्लॅट ₹5/executed order; Commodity Futures ₹5 किंवा 0.03% जे कमी — डिसेंबर
      2024 पासून (आधी zero-brokerage होतं, SEBI च्या exchange-rebate बंदीनंतर बदललं).
    - Stocko: प्रति-ऑर्डर brokerage नाहीच — निश्चित ₹1200/महिना सबस्क्रिप्शन (आधीसारखाच, वेगळा
      हाताळलेला), पण वरचे STT/Exchange/SEBI/Stamp Duty त्यावरही (per-order) लागू होतातच — कुठलाही
      "unlimited"/flat brokerage plan सरकारी शुल्क माफ करू शकत नाही.
  • GST 18% — brokerage + exchange + SEBI वर (Stocko साठी फक्त exchange+SEBI वर, कारण brokerage
    component इथे प्रति-ऑर्डर नाहीच).
हे दर वेळोवेळी (Budget/SEBI परिपत्रकाने) बदलू शकतात — बदलले तर फक्त खालचे _STATUTORY_RATES/
_BROKERAGE_RATES dicts अद्ययावत करायचे आहेत, बाकी लॉजिकला हात लावायची गरज नाही.
आवश्यक तपशील (symbol/quantity/price/transaction_type) उपलब्ध नसतील (उदा. जुना/minimal caller)
तेव्हाच Upstox/Fyers/Shoonya च्या ऑर्डरसाठी जुना ढोबळ ₹25/ऑर्डर अंदाजावर पडलं जातं (Stocko साठी तसा
fallback नाही — brokerage आधीच मासिक सबस्क्रिप्शनमधून मोजला जातो, double-count टाळण्यासाठी); कधीही
Upstox/Fyers/Shoonya चं शुल्क शून्य दाखवलं जात नाही.

account_id → broker_type कसं ठरतं: order_log/live_trades मधला account_id सेट असेल तर cloud_db च्या
broker_accounts table (Supabase, फक्त multi-broker सेटअपमध्ये existent) मधून broker_type शोधला जातो.
account_id रिकामा (None) असेल — म्हणजे जुना/डीफॉल्ट सिंगल-अकाउंट प्रवाह (Manual Trading Panel आणि
जवळजवळ सर्व auto-trader scripts कायम adapter=None वापरतात, म्हणजे कायम फक्त Upstox token) — तेव्हा
"upstox" गृहीत धरलं जातं.
"""
import datetime

import pandas as pd

FLAT_CHARGE_PER_ORDER = 25.0  # आता फक्त _BROKERAGE_RATES मध्ये नसलेल्या ब्रोकरसाठी (व तपशील अपुरा असेल तरच) — ढोबळ अंदाज, all-inclusive
STOCKO_FLAT_MONTHLY = 1200.0
DEFAULT_BROKER = "upstox"

# resolve_mcx_futures_instruments.MCX_FUTURES_SYMBOLS शी सुसंगत (इथेच वेगळी ठेवली आहे — तो module
# cloud_db/config import करतो, जे charges.py ला नकोय, फक्त हीच यादी हवी आहे — segment ठरवण्यासाठी).
MCX_FUTURES_SYMBOLS = ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"]

_GST_RATE = 0.18

# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Stocko आणि Fyers साठी पण actual calculator लावता येईल का") —
# STT/CTT, Exchange Txn Charge, SEBI Turnover Fee, Stamp Duty हे सरकारी/एक्सचेंज-निर्धारित दर आहेत —
# ब्रोकर Upstox असो, Fyers असो वा Stocko, हे **सर्वांना सारखेच** लागू होतात (कुठलाही ब्रोकर हे माफ करू
# शकत नाही — म्हणून यांना segment नुसार (Options वि. MCX Commodity Futures) फक्त एकदाच, ब्रोकर-निरपेक्ष
# ठेवलं आहे). फक्त "brokerage" हा एकच घटक प्रत्येक ब्रोकरनुसार वेगळा असतो — तो खालच्या _BROKERAGE_RATES
# मध्ये वेगळा दिला आहे. दर स्रोत: upstox.com/brokerage-charges, fyers.in/charges-list (ऑक्टोबर-2024
# STT/Exchange Transaction Charge फेरबदलानंतरचे — सर्वात अलीकडचे ज्ञात दर).
_STATUTORY_RATES = {
    "options": {
        "stt_pct": 0.001, "stt_side": "sell",  # STT 0.1% premium वर, फक्त SELL
        "exch_pct": 0.00035, "exch_side": "both",  # NSE Exchange Txn Charge 0.035%, दोन्ही बाजू
        "sebi_pct": 0.000001, "sebi_side": "both",  # SEBI Turnover Fee 0.0001%, दोन्ही बाजू
        "stamp_pct": 0.00003, "stamp_side": "buy",  # Stamp Duty 0.003%, फक्त BUY
    },
    "commodity_futures": {
        "stt_pct": 0.0001, "stt_side": "sell",  # CTT 0.01% ट्रेड व्हॅल्यूवर, फक्त SELL
        "exch_pct": 0.000021, "exch_side": "both",  # MCX Exchange Txn Charge 0.0021%, दोन्ही बाजू
        "sebi_pct": 0.000001, "sebi_side": "both",  # SEBI Turnover Fee 0.0001%, दोन्ही बाजू
        "stamp_pct": 0.00002, "stamp_side": "buy",  # Stamp Duty 0.002%, फक्त BUY
    },
}

# ब्रोकर-निहाय brokerage दर — इथेच फक्त फरक असतो (वरचे statutory दर सर्व ब्रोकर्ससाठी सारखेच).
# "stocko" इथे नाही, कारण त्याचं brokerage प्रति-ऑर्डर नसून निश्चित मासिक सबस्क्रिप्शन आहे
# (STOCKO_FLAT_MONTHLY, compute_charges() मध्ये वेगळं हाताळलेलं). स्रोत: upstox.com/brokerage-charges,
# fyers.in/charges-list, shoonya.com/pricing (डिसेंबर-2024 पासून Shoonya चं zero-brokerage संपून
# ₹5/0.03% लागू झालं — सर्वात अलीकडचं ज्ञात).
_BROKERAGE_RATES = {
    "upstox": {
        "options": {"flat": 20.0, "pct": None},  # फ्लॅट ₹20/executed order
        "commodity_futures": {"flat": 20.0, "pct": 0.0005},  # ₹20 किंवा 0.05%, जे कमी
    },
    "fyers": {
        "options": {"flat": 20.0, "pct": None},  # फ्लॅट ₹20/executed order
        "commodity_futures": {"flat": 20.0, "pct": 0.0003},  # ₹20 किंवा 0.03%, जे कमी (Upstox पेक्षा किंचित कमी %)
    },
    "shoonya": {
        "options": {"flat": 5.0, "pct": None},  # फ्लॅट ₹5/executed order (सर्वात कमी — Shoonya चं मुख्य वैशिष्ट्य)
        "commodity_futures": {"flat": 5.0, "pct": 0.0003},  # ₹5 किंवा 0.03%, जे कमी
    },
}

_EMPTY_DAILY_CHARGES = pd.DataFrame(columns=[
    "date", "broker_type", "orders", "brokerage", "stt", "exchange_txn", "sebi_fee",
    "stamp_duty", "gst", "charge",
])
_EMPTY_BREAKDOWN = {"brokerage": 0.0, "stt": 0.0, "exchange_txn": 0.0, "sebi_fee": 0.0, "stamp_duty": 0.0, "gst": 0.0}
_EMPTY_SUMMARY = {"total_charges": 0.0, "total_orders": 0, "per_broker": {}, "breakdown": dict(_EMPTY_BREAKDOWN)}


def get_account_broker_map():
    """account_id -> broker_type — cloud_db (Supabase) configured असेल तरच काही देईल, नाहीतर रिकामा dict
    (त्या स्थितीत सर्व orders चा account_id आपोआप None असतो, त्यामुळे पुढे resolve_broker_type() ने
    "upstox" गृहीत धरलं जातं — सुसंगतच राहतं)."""
    try:
        import cloud_db
        if not cloud_db.is_cloud_db_configured():
            return {}
        accounts_df = cloud_db.get_all_broker_accounts(active_only=False)
        if accounts_df is None or accounts_df.empty:
            return {}
        return dict(zip(accounts_df["account_id"], accounts_df["broker_type"]))
    except Exception:
        return {}


def resolve_broker_type(account_id, broker_map):
    if not account_id:
        return DEFAULT_BROKER
    return broker_map.get(account_id, DEFAULT_BROKER)


def _segment_for_symbol(symbol):
    """symbol वरून Upstox rate-segment ठरवते — NSE Index/Equity Options वि. MCX Commodity Futures
    (हे दोन्ही या app मध्ये प्रत्यक्ष ट्रेड होणारे एकमेव segments आहेत — कुठलाही equity delivery/
    intraday किंवा equity/currency futures नाही)."""
    return "commodity_futures" if symbol in MCX_FUTURES_SYMBOLS else "options"


def _row_turnover_details(row):
    """quantity/price/symbol/side वाचून (quantity, price, symbol, side, turnover) परत देते, किंवा
    तपशील अपुरा/अवैध असेल तर None — _accurate_row_charges() आणि _stocko_statutory_row_charges()
    दोन्हीसाठी समान पडताळणी."""
    quantity = row.get("quantity")
    price = row.get("fill_price")
    if price is None or pd.isna(price) or price == 0:
        price = row.get("price")
    symbol = row.get("symbol")
    side = row.get("transaction_type")
    if (
        quantity is None or pd.isna(quantity)
        or price is None or pd.isna(price)
        or not symbol or pd.isna(symbol)
        or side not in ("BUY", "SELL")
    ):
        return None
    turnover = float(quantity) * float(price)
    if turnover <= 0:
        return None
    return symbol, side, turnover


def _accurate_row_charges(row, broker_type):
    """एका order-row साठी ब्रोकरचं वास्तविक brokerage (_BROKERAGE_RATES[broker_type]) + सर्वांसाठी
    सारखे असलेले STT/CTT + Exchange Txn + SEBI + Stamp Duty + GST (_STATUTORY_RATES) मोजते.
    broker_type साठी दर माहीत नसतील (उदा. Shoonya) किंवा आवश्यक तपशील अपुरे/अवैध असतील तर None परत
    देते — कॉलर (_add_order_charges) मग त्या रांगेसाठी जुन्या ढोबळ ₹25/ऑर्डर अंदाजावर पडतो."""
    brokerage_rates = _BROKERAGE_RATES.get(broker_type)
    if brokerage_rates is None:
        return None
    details = _row_turnover_details(row)
    if details is None:
        return None
    symbol, side, turnover = details

    segment = _segment_for_symbol(symbol)
    seg_brokerage_rates = brokerage_rates[segment]
    statutory = _STATUTORY_RATES[segment]
    brokerage = seg_brokerage_rates["flat"]
    if seg_brokerage_rates["pct"] is not None:
        brokerage = min(brokerage, turnover * seg_brokerage_rates["pct"])
    stt = turnover * statutory["stt_pct"] if side == "SELL" else 0.0
    exchange_txn = turnover * statutory["exch_pct"]
    sebi_fee = turnover * statutory["sebi_pct"]
    stamp_duty = turnover * statutory["stamp_pct"] if side == "BUY" else 0.0
    gst = (brokerage + exchange_txn + sebi_fee) * _GST_RATE
    charge = brokerage + stt + exchange_txn + sebi_fee + stamp_duty + gst
    return {
        "brokerage": brokerage, "stt": stt, "exchange_txn": exchange_txn, "sebi_fee": sebi_fee,
        "stamp_duty": stamp_duty, "gst": gst, "charge": charge,
    }


def _stocko_statutory_row_charges(row):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Stocko साठी पण actual calculator लावता येईल का") — Stocko चं
    स्वतःचं brokerage प्रति-ऑर्डर नसून निश्चित मासिक सबस्क्रिप्शन आहे (STOCKO_FLAT_MONTHLY,
    compute_charges() मध्ये वेगळं जोडलं जातं — म्हणून इथे brokerage नेहमी 0), पण STT/CTT/Exchange
    Txn/SEBI Fee/Stamp Duty हे सरकारी/एक्सचेंज शुल्क आहेत — ते Stocko चं "unlimited"/flat plan
    असूनही प्रत्येक प्रत्यक्ष order वर लागतातच (कुठलाही ब्रोकर हे माफ करू शकत नाही) — त्यामुळे तेवढेच
    इथे मोजले जातात. GST फक्त exchange_txn+sebi_fee वर (ब्रोकरेज हा component इथे नसल्याने, त्यावरचा
    GST subscription बिलात वेगळा येतो, इथे मोजलेला नाही). तपशील अपुरा असेल तर None (त्या रांगेसाठी
    statutory शुल्क 0 राहतं — brokerage साठी जुना ढोबळ अंदाज इथे लागू नाही, कारण तो आधीच मासिक
    सबस्क्रिप्शनमधून मोजला जातो, त्यामुळे double-count टाळण्यासाठी fallback दिलेला नाही)."""
    details = _row_turnover_details(row)
    if details is None:
        return None
    symbol, side, turnover = details
    statutory = _STATUTORY_RATES[_segment_for_symbol(symbol)]
    stt = turnover * statutory["stt_pct"] if side == "SELL" else 0.0
    exchange_txn = turnover * statutory["exch_pct"]
    sebi_fee = turnover * statutory["sebi_pct"]
    stamp_duty = turnover * statutory["stamp_pct"] if side == "BUY" else 0.0
    gst = (exchange_txn + sebi_fee) * _GST_RATE
    charge = stt + exchange_txn + sebi_fee + stamp_duty + gst
    return {
        "brokerage": 0.0, "stt": stt, "exchange_txn": exchange_txn, "sebi_fee": sebi_fee,
        "stamp_duty": stamp_duty, "gst": gst, "charge": charge,
    }


_FLAT_ROW_CHARGE = {
    "brokerage": FLAT_CHARGE_PER_ORDER, "stt": 0.0, "exchange_txn": 0.0,
    "sebi_fee": 0.0, "stamp_duty": 0.0, "gst": 0.0, "charge": FLAT_CHARGE_PER_ORDER,
}
_CHARGE_COLS = ["brokerage", "stt", "exchange_txn", "sebi_fee", "stamp_duty", "gst", "charge"]


def _add_order_charges(df):
    """प्रत्येक ऑर्डर-रांगेला योग्य शुल्क जोडते:
    - Upstox/Fyers/Shoonya (_BROKERAGE_RATES मध्ये असलेले ब्रोकर) — शक्य असेल तिथे
      _accurate_row_charges() वरून वास्तविक brokerage+STT/Exchange/SEBI/Stamp/GST; तपशील अपुरा
      असेल तिथेच जुना ढोबळ ₹25/ऑर्डर अंदाज.
    - Stocko — brokerage 0 (निश्चित मासिक शुल्क compute_charges() मध्ये वेगळं जोडलं जातं), पण
      _stocko_statutory_row_charges() वरून वास्तविक STT/Exchange/SEBI/Stamp/GST (शक्य असेल तिथे)."""
    df = df.copy()
    for c in _CHARGE_COLS:
        df[c] = 0.0
    for idx, row in df.iterrows():
        broker_type = row["broker_type"]
        if broker_type == "stocko":
            result = _stocko_statutory_row_charges(row)
            if result is None:
                continue
        else:
            result = _accurate_row_charges(row, broker_type)
            if result is None:
                result = _FLAT_ROW_CHARGE
        for c in _CHARGE_COLS:
            df.at[idx, c] = result[c]
    return df


def compute_charges(orders_df, start_date, end_date, broker_map=None):
    """
    orders_df: columns 'placed_at' (str/datetime-parseable), 'account_id' (nullable), 'order_id',
    आणि (Upstox अचूक शुल्कासाठी, ऐच्छिक — नसेल तर त्या रांगेला जुना ढोबळ ₹25/ऑर्डर अंदाज लागतो)
    'symbol', 'quantity', 'transaction_type' ("BUY"/"SELL"), 'fill_price'/'price'.
    start_date/end_date: datetime.date — रिपोर्टची तारीख-रेंज (Stocko चं प्रोरेशन याच रेंजपुरतं मर्यादित).

    रिटर्न: (daily_charges_df, summary)
      daily_charges_df: columns date, broker_type, orders, brokerage, stt, exchange_txn, sebi_fee,
      stamp_duty, gst, charge (charge = सर्व घटकांची बेरीज, दिवसागणिक — pnl_reports.py याच्यावर
      resample करतो).
      summary: {"total_charges", "total_orders", "per_broker": {broker: {"orders", "charge"}},
                "breakdown": {"brokerage", "stt", "exchange_txn", "sebi_fee", "stamp_duty", "gst"}}
    """
    if orders_df is None or orders_df.empty:
        return _EMPTY_DAILY_CHARGES.copy(), dict(_EMPTY_SUMMARY, per_broker={}, breakdown=dict(_EMPTY_BREAKDOWN))

    broker_map = broker_map if broker_map is not None else get_account_broker_map()
    df = orders_df.copy()
    df["placed_at"] = pd.to_datetime(df["placed_at"])
    df["date"] = df["placed_at"].dt.date
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    if df.empty:
        return _EMPTY_DAILY_CHARGES.copy(), dict(_EMPTY_SUMMARY, per_broker={}, breakdown=dict(_EMPTY_BREAKDOWN))

    df["broker_type"] = df["account_id"].apply(lambda a: resolve_broker_type(a, broker_map))
    df = _add_order_charges(df)

    charge_cols = _CHARGE_COLS
    grouped = (
        df.groupby(["date", "broker_type"])
        .agg(orders=("order_id", "count"), **{c: (c, "sum") for c in charge_cols})
        .reset_index()
    )
    pieces = [grouped[["date", "broker_type", "orders"] + charge_cols]]
    stocko_order_count = int((df["broker_type"] == "stocko").sum())

    # --- Stocko: निश्चित मासिक brokerage शुल्क (वर मोजलेलं STT/Exchange/SEBI/Stamp Duty याशिवाय) —
    # ज्या कॅलेंडर महिन्यात किमान एक Stocko order झाला, त्या महिन्याच्या (रिपोर्ट-रेंजमध्ये बसणाऱ्या
    # भागाच्या) प्रत्येक दिवसाला सम-भाग (₹1200/त्या महिन्यातले एकूण दिवस) वाटलेला. वास्तविक subscription
    # नेमकं किती दिवस सक्रिय होतं हे आपल्याला माहीत नाही — "वापरलेला महिना = तो संपूर्ण महिना सक्रिय
    # गृहीत धरणे" हा एक स्पष्ट, इथेच दस्तऐवजीकरण केलेला अंदाज आहे — प्रत्यक्ष Stocko बिलाशी तंतोतंत
    # जुळेलच असं नाही.
    stocko_df = df[df["broker_type"] == "stocko"]
    if not stocko_df.empty:
        stocko_rows = []
        for period in stocko_df["placed_at"].dt.to_period("M").unique():
            days_in_month = period.days_in_month
            daily_amount = round(STOCKO_FLAT_MONTHLY / days_in_month, 2)
            range_start = max(period.start_time.date(), start_date)
            range_end = min(period.end_time.date(), end_date)
            d = range_start
            while d <= range_end:
                stocko_rows.append({
                    "date": d, "broker_type": "stocko", "orders": 0, "brokerage": daily_amount,
                    "stt": 0.0, "exchange_txn": 0.0, "sebi_fee": 0.0, "stamp_duty": 0.0, "gst": 0.0,
                    "charge": daily_amount,
                })
                d += datetime.timedelta(days=1)
        if stocko_rows:
            pieces.append(pd.DataFrame(stocko_rows))

    daily_charges_df = pd.concat(pieces, ignore_index=True)

    per_broker = {}
    for broker_type, sub in daily_charges_df.groupby("broker_type"):
        order_count = stocko_order_count if broker_type == "stocko" else int(sub["orders"].sum())
        per_broker[broker_type] = {"orders": order_count, "charge": round(sub["charge"].sum(), 2)}

    total_orders = len(df)

    summary = {
        "total_charges": round(daily_charges_df["charge"].sum(), 2),
        "total_orders": total_orders,
        "per_broker": per_broker,
        "breakdown": {c: round(daily_charges_df[c].sum(), 2) for c in charge_cols[:-1]},
    }
    return daily_charges_df, summary
