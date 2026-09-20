"""
charges.py
------------------------------
वास्तविक ट्रेडिंग शुल्क (brokerage + सरकारी/एक्सचेंज शुल्क) मोजण्यासाठी.

🎓 वापरकर्त्याने मागितलेली सुधारणा (rough, सोपा अंदाज) — आधी brokerage + STT + Exchange Txn Charge +
SEBI Turnover Fee + Stamp Duty + त्यावरचा GST असे सहा वेगवेगळे घटक, प्रत्येक ऑर्डरच्या प्रीमियम
turnover वरून टक्केवारीने मोजले जायचे — पण वापरकर्त्याला हे जास्त/अनपेक्षित वाटलं आणि पडताळणं अवघड
झालं. आता प्रत्येक per-order ब्रोकरसाठी (Upstox/Fyers/Shoonya) एक निश्चित, ढोबळ ₹35/ऑर्डर (brokerage
+ सर्व सरकारी/एक्सचेंज शुल्क मिळून, एकत्र) — तंतोतंत नाही, पण साधा आणि अंदाज बांधता येण्याजोगा.
Stocko — निश्चित ₹1200/महिना (per-order नाही, फिक्स्ड सबस्क्रिप्शन प्लॅन, आधीसारखाच) कायम.

account_id → broker_type कसं ठरतं: order_log/live_trades मधला account_id सेट असेल तर cloud_db च्या
broker_accounts table (Supabase, फक्त multi-broker सेटअपमध्ये existent) मधून broker_type शोधला जातो.
account_id रिकामा (None) असेल — म्हणजे जुना/डीफॉल्ट सिंगल-अकाउंट प्रवाह (Manual Trading Panel आणि
जवळजवळ सर्व auto-trader scripts कायम adapter=None वापरतात, म्हणजे कायम फक्त Upstox token) — तेव्हा
"upstox" गृहीत धरलं जातं.
"""
import datetime

import pandas as pd

FLAT_CHARGE_PER_ORDER = 35.0  # ढोबळ अंदाज — brokerage + STT/Exchange/SEBI/Stamp/GST सर्व मिळून, प्रति ऑर्डर
STOCKO_FLAT_MONTHLY = 1200.0
DEFAULT_BROKER = "upstox"

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


def _add_flat_order_charge(df):
    """प्रत्येक ऑर्डर-रांगेला ढोबळ ₹35 (FLAT_CHARGE_PER_ORDER, brokerage + सर्व सरकारी/एक्सचेंज शुल्क
    मिळून) जोडते — Stocko साठी प्रति-ऑर्डर शुल्क 0 (कारण ते निश्चित मासिक शुल्क आहे, compute_charges()
    मध्ये वेगळं जोडलं जातं). breakdown मधले stt/exchange_txn/sebi_fee/stamp_duty/gst स्तंभ established
    UI/PDF code शी सुसंगत राहण्यासाठी अजूनही आहेत, पण आता नेहमी 0 — संपूर्ण ढोबळ रक्कम फक्त "brokerage"
    मध्ये दाखवली जाते."""
    df = df.copy()
    df["brokerage"] = df["broker_type"].apply(lambda b: 0.0 if b == "stocko" else FLAT_CHARGE_PER_ORDER)
    df["stt"] = 0.0
    df["exchange_txn"] = 0.0
    df["sebi_fee"] = 0.0
    df["stamp_duty"] = 0.0
    df["gst"] = 0.0
    df["charge"] = df["brokerage"]
    return df


def compute_charges(orders_df, start_date, end_date, broker_map=None):
    """
    orders_df: columns 'placed_at' (str/datetime-parseable), 'account_id' (nullable), 'order_id'.
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
    df = _add_flat_order_charge(df)

    charge_cols = ["brokerage", "stt", "exchange_txn", "sebi_fee", "stamp_duty", "gst", "charge"]
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
