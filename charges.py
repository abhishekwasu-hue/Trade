"""
charges.py
------------------------------
वास्तविक ट्रेडिंग ब्रोकरेज शुल्क (charges) मोजण्यासाठी — प्रत्येक ब्रोकरची शुल्क-रचना वेगळी आहे:
Upstox/Fyers — प्रति ऑर्डर ₹20, Shoonya — प्रति ऑर्डर ₹5, Stocko — निश्चित ₹1200/महिना (per-order
नाही, फिक्स्ड सबस्क्रिप्शन प्लॅन). हे दर वापरकर्त्याने दिलेले आहेत — प्रत्यक्ष प्लॅन बदलल्यास इथेच अपडेट करा.

account_id → broker_type कसं ठरतं: order_log/live_trades मधला account_id सेट असेल तर cloud_db च्या
broker_accounts table (Supabase, फक्त multi-broker सेटअपमध्ये existent) मधून broker_type शोधला जातो.
account_id रिकामा (None) असेल — म्हणजे जुना/डीफॉल्ट सिंगल-अकाउंट प्रवाह (Manual Trading Panel आणि
जवळजवळ सर्व auto-trader scripts कायम adapter=None वापरतात, म्हणजे कायम फक्त Upstox token) — तेव्हा
"upstox" गृहीत धरलं जातं.
"""
import datetime

import pandas as pd

BROKERAGE_PER_ORDER = {
    "upstox": 20.0,
    "fyers": 20.0,
    "shoonya": 5.0,
}
STOCKO_FLAT_MONTHLY = 1200.0
DEFAULT_BROKER = "upstox"

_EMPTY_DAILY_CHARGES = pd.DataFrame(columns=["date", "broker_type", "orders", "charge"])
_EMPTY_SUMMARY = {"total_charges": 0.0, "total_orders": 0, "per_broker": {}}


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


def compute_charges(orders_df, start_date, end_date, broker_map=None):
    """
    orders_df: columns 'placed_at' (str/datetime-parseable), 'account_id' (nullable).
    start_date/end_date: datetime.date — रिपोर्टची तारीख-रेंज (Stocko चं प्रोरेशन याच रेंजपुरतं मर्यादित).

    रिटर्न: (daily_charges_df, summary)
      daily_charges_df: columns date, broker_type, orders, charge — दिवसागणिक (Daily/Weekly/Monthly
      report बनवताना pnl_reports.py याच्यावर resample करतो).
      summary: {"total_charges", "total_orders", "per_broker": {broker: {"orders", "charge"}}}
    """
    if orders_df is None or orders_df.empty:
        return _EMPTY_DAILY_CHARGES.copy(), dict(_EMPTY_SUMMARY, per_broker={})

    broker_map = broker_map if broker_map is not None else get_account_broker_map()
    df = orders_df.copy()
    df["placed_at"] = pd.to_datetime(df["placed_at"])
    df["date"] = df["placed_at"].dt.date
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    if df.empty:
        return _EMPTY_DAILY_CHARGES.copy(), dict(_EMPTY_SUMMARY, per_broker={})

    df["broker_type"] = df["account_id"].apply(lambda a: resolve_broker_type(a, broker_map))

    pieces = []

    # --- प्रति-ऑर्डर ब्रोकर्स (Upstox/Fyers/Shoonya) ---
    per_order_df = df[df["broker_type"].isin(BROKERAGE_PER_ORDER.keys())]
    if not per_order_df.empty:
        grouped = per_order_df.groupby(["date", "broker_type"]).size().reset_index(name="orders")
        grouped["charge"] = grouped.apply(
            lambda r: round(r["orders"] * BROKERAGE_PER_ORDER[r["broker_type"]], 2), axis=1
        )
        pieces.append(grouped[["date", "broker_type", "orders", "charge"]])

    # --- Stocko: निश्चित मासिक शुल्क — ज्या कॅलेंडर महिन्यात किमान एक Stocko order झाला, त्या
    # महिन्याच्या (रिपोर्ट-रेंजमध्ये बसणाऱ्या भागाच्या) प्रत्येक दिवसाला सम-भाग (₹1200/त्या महिन्यातले
    # एकूण दिवस) वाटलेला. वास्तविक subscription नेमकं किती दिवस सक्रिय होतं हे आपल्याला माहीत नाही —
    # "वापरलेला महिना = तो संपूर्ण महिना सक्रिय गृहीत धरणे" हा एक स्पष्ट, इथेच दस्तऐवजीकरण केलेला अंदाज
    # आहे — प्रत्यक्ष Stocko बिलाशी तंतोतंत जुळेलच असं नाही.
    stocko_df = df[df["broker_type"] == "stocko"]
    stocko_order_count = len(stocko_df)
    if not stocko_df.empty:
        stocko_rows = []
        for period in stocko_df["placed_at"].dt.to_period("M").unique():
            days_in_month = period.days_in_month
            daily_amount = round(STOCKO_FLAT_MONTHLY / days_in_month, 2)
            range_start = max(period.start_time.date(), start_date)
            range_end = min(period.end_time.date(), end_date)
            d = range_start
            while d <= range_end:
                stocko_rows.append({"date": d, "broker_type": "stocko", "orders": 0, "charge": daily_amount})
                d += datetime.timedelta(days=1)
        if stocko_rows:
            pieces.append(pd.DataFrame(stocko_rows))

    if not pieces:
        return _EMPTY_DAILY_CHARGES.copy(), dict(_EMPTY_SUMMARY, per_broker={})

    daily_charges_df = pd.concat(pieces, ignore_index=True)

    per_broker = {}
    for broker_type, sub in daily_charges_df.groupby("broker_type"):
        order_count = stocko_order_count if broker_type == "stocko" else int(sub["orders"].sum())
        per_broker[broker_type] = {"orders": order_count, "charge": round(sub["charge"].sum(), 2)}

    total_orders = len(per_order_df) + stocko_order_count

    summary = {
        "total_charges": round(daily_charges_df["charge"].sum(), 2),
        "total_orders": total_orders,
        "per_broker": per_broker,
    }
    return daily_charges_df, summary
