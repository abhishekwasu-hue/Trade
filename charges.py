"""
charges.py
------------------------------
वास्तविक ट्रेडिंग शुल्क (brokerage + सरकारी/एक्सचेंज शुल्क) मोजण्यासाठी.

🎓 वापरकर्त्याने मागितलेली सुधारणा ("Upstox brokerage calculator वापरून actual brokerage काढा") —
आधी (rough अंदाज टप्प्यात) brokerage + STT + Exchange Txn Charge + SEBI Turnover Fee + Stamp Duty +
GST हे सहा घटक असलेला अचूक हिशोब वापरकर्त्याला जास्त/अनपेक्षित वाटला आणि पडताळणं अवघड झालं होतं,
त्यामुळे तेव्हा तात्पुरता एक निश्चित ढोबळ ₹25/ऑर्डर (all-inclusive) अंदाज वापरला गेला. आता वापरकर्त्याने
स्पष्टपणे "Upstox चा brokerage calculator वापरून actual brokerage काढा" असं मागितलं आहे — त्यामुळे
**Upstox** ऑर्डर्ससाठी (हाच DEFAULT_BROKER, आणि जवळजवळ सर्व ऑर्डर्स याच ब्रोकरचे असतात) आता Upstox च्या
स्वतःच्या प्रकाशित brokerage calculator (upstox.com/brokerage-charges) + सरकारी/एक्सचेंज दरांवरून
(ऑक्टोबर-2024 च्या STT/Exchange Transaction Charge फेरबदलानंतरचे, सद्यस्थितीतले सर्वात अलीकडचे ज्ञात
दर) प्रत्येक ऑर्डरचं turnover (quantity × price) वापरून खरं शुल्क मोजलं जातं — segment नुसार (NSE
Index/Equity Options वि. MCX Commodity Futures) वेगवेगळे दर, कारण ते खरोखरच वेगळे आहेत:
  • Options (NIFTY/BANKNIFTY/SENSEX): brokerage फ्लॅट ₹20/executed order; STT 0.1% (फक्त SELL,
    premium वर); Exchange Txn Charge 0.035% (दोन्ही बाजू, premium वर); SEBI Turnover Fee 0.0001%
    (दोन्ही बाजू); Stamp Duty 0.003% (फक्त BUY); GST 18% (brokerage + exchange + SEBI वर).
  • MCX Commodity Futures (CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER): brokerage ₹20 किंवा ट्रेड
    व्हॅल्यूच्या 0.05%, जे कमी असेल ते; CTT 0.01% (फक्त SELL); Exchange Txn Charge 0.0021% (दोन्ही
    बाजू); SEBI Turnover Fee 0.0001% (दोन्ही बाजू); Stamp Duty 0.002% (फक्त BUY); GST 18%.
हे दर वेळोवेळी (Budget/SEBI परिपत्रकाने) बदलू शकतात — बदलले तर फक्त खालचा _UPSTOX_RATES dict अद्ययावत
करायचा आहे, बाकी लॉजिकला हात लावायची गरज नाही.
आवश्यक तपशील (symbol/quantity/price/transaction_type) उपलब्ध नसतील (उदा. जुना/minimal caller) तेव्हाच
त्या विशिष्ट ऑर्डरसाठी जुना ढोबळ ₹25/ऑर्डर अंदाजावर पडलं जातं — कधीही शुल्क शून्य दाखवलं जात नाही.
Fyers/Shoonya (इतर per-order ब्रोकर) — अजूनही जुनाच ढोबळ ₹25/ऑर्डर (all-inclusive) अंदाज, कारण
वापरकर्त्याने फक्त Upstox साठी अचूक आकडे मागितले — या इतर ब्रोकर्सचे प्रत्यक्ष दर अजून पडताळलेले नाहीत.
Stocko — निश्चित ₹1200/महिना (per-order नाही, फिक्स्ड सबस्क्रिप्शन प्लॅन, आधीसारखाच) कायम.

account_id → broker_type कसं ठरतं: order_log/live_trades मधला account_id सेट असेल तर cloud_db च्या
broker_accounts table (Supabase, फक्त multi-broker सेटअपमध्ये existent) मधून broker_type शोधला जातो.
account_id रिकामा (None) असेल — म्हणजे जुना/डीफॉल्ट सिंगल-अकाउंट प्रवाह (Manual Trading Panel आणि
जवळजवळ सर्व auto-trader scripts कायम adapter=None वापरतात, म्हणजे कायम फक्त Upstox token) — तेव्हा
"upstox" गृहीत धरलं जातं.
"""
import datetime

import pandas as pd

FLAT_CHARGE_PER_ORDER = 25.0  # आता फक्त Fyers/Shoonya साठी (व Upstox रांगांना पुरेसा तपशील नसेल तरच) — ढोबळ अंदाज, all-inclusive
STOCKO_FLAT_MONTHLY = 1200.0
DEFAULT_BROKER = "upstox"

# resolve_mcx_futures_instruments.MCX_FUTURES_SYMBOLS शी सुसंगत (इथेच वेगळी ठेवली आहे — तो module
# cloud_db/config import करतो, जे charges.py ला नकोय, फक्त हीच यादी हवी आहे — segment ठरवण्यासाठी).
MCX_FUTURES_SYMBOLS = ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"]

_GST_RATE = 0.18

# स्रोत: upstox.com/brokerage-charges (Upstox स्वतःचा brokerage calculator) + सरकारी/एक्सचेंज दर
# (ऑक्टोबर-2024 STT/Exchange Transaction Charge फेरबदलानंतरचे — सर्वात अलीकडचे ज्ञात दर).
_UPSTOX_RATES = {
    "options": {
        "brokerage_flat": 20.0, "brokerage_pct": None,  # फ्लॅट ₹20/executed order
        "stt_pct": 0.001, "stt_side": "sell",  # STT 0.1% premium वर, फक्त SELL
        "exch_pct": 0.00035, "exch_side": "both",  # NSE Exchange Txn Charge 0.035%, दोन्ही बाजू
        "sebi_pct": 0.000001, "sebi_side": "both",  # SEBI Turnover Fee 0.0001%, दोन्ही बाजू
        "stamp_pct": 0.00003, "stamp_side": "buy",  # Stamp Duty 0.003%, फक्त BUY
    },
    "commodity_futures": {
        "brokerage_flat": 20.0, "brokerage_pct": 0.0005,  # ₹20 किंवा 0.05%, जे कमी
        "stt_pct": 0.0001, "stt_side": "sell",  # CTT 0.01% ट्रेड व्हॅल्यूवर, फक्त SELL
        "exch_pct": 0.000021, "exch_side": "both",  # MCX Exchange Txn Charge 0.0021%, दोन्ही बाजू
        "sebi_pct": 0.000001, "sebi_side": "both",  # SEBI Turnover Fee 0.0001%, दोन्ही बाजू
        "stamp_pct": 0.00002, "stamp_side": "buy",  # Stamp Duty 0.002%, फक्त BUY
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


def _upstox_row_charges(row):
    """एका order-row साठी Upstox चं वास्तविक brokerage + STT/CTT + Exchange Txn + SEBI + Stamp Duty +
    GST (_UPSTOX_RATES, वरच्या module docstring मध्ये स्रोत/तारखेसह दस्तऐवजीकरण केलेले दर) मोजते.
    आवश्यक तपशील (symbol/quantity/price/transaction_type) अपुरे/अवैध असतील तर None परत देते — कॉलर
    (_add_order_charges) मग त्या रांगेसाठी जुन्या ढोबळ ₹25/ऑर्डर अंदाजावर पडतो."""
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

    rates = _UPSTOX_RATES[_segment_for_symbol(symbol)]
    brokerage = rates["brokerage_flat"]
    if rates["brokerage_pct"] is not None:
        brokerage = min(brokerage, turnover * rates["brokerage_pct"])
    stt = turnover * rates["stt_pct"] if side == "SELL" else 0.0
    exchange_txn = turnover * rates["exch_pct"]
    sebi_fee = turnover * rates["sebi_pct"]
    stamp_duty = turnover * rates["stamp_pct"] if side == "BUY" else 0.0
    gst = (brokerage + exchange_txn + sebi_fee) * _GST_RATE
    charge = brokerage + stt + exchange_txn + sebi_fee + stamp_duty + gst
    return {
        "brokerage": brokerage, "stt": stt, "exchange_txn": exchange_txn, "sebi_fee": sebi_fee,
        "stamp_duty": stamp_duty, "gst": gst, "charge": charge,
    }


_FLAT_ROW_CHARGE = {
    "brokerage": FLAT_CHARGE_PER_ORDER, "stt": 0.0, "exchange_txn": 0.0,
    "sebi_fee": 0.0, "stamp_duty": 0.0, "gst": 0.0, "charge": FLAT_CHARGE_PER_ORDER,
}
_CHARGE_COLS = ["brokerage", "stt", "exchange_txn", "sebi_fee", "stamp_duty", "gst", "charge"]


def _add_order_charges(df):
    """प्रत्येक ऑर्डर-रांगेला योग्य शुल्क जोडते:
    - Upstox (DEFAULT_BROKER, जवळजवळ सर्व ऑर्डर्स) — शक्य असेल तिथे _upstox_row_charges() वरून
      वास्तविक Upstox brokerage calculator दर; तपशील अपुरा असेल तिथेच जुना ढोबळ ₹25/ऑर्डर अंदाज.
    - Fyers/Shoonya — अजूनही जुनाच ढोबळ ₹25/ऑर्डर अंदाज (वापरकर्त्याने फक्त Upstox साठी अचूक आकडे
      मागितले होते).
    - Stocko — प्रति-ऑर्डर शुल्क 0 (निश्चित मासिक शुल्क compute_charges() मध्ये वेगळं जोडलं जातं)."""
    df = df.copy()
    for c in _CHARGE_COLS:
        df[c] = 0.0
    for idx, row in df.iterrows():
        broker_type = row["broker_type"]
        if broker_type == "stocko":
            continue
        result = _upstox_row_charges(row) if broker_type == "upstox" else None
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
