"""
charges.py
------------------------------
वास्तविक ट्रेडिंग शुल्क (brokerage + सरकारी/एक्सचेंज शुल्क) मोजण्यासाठी.

दोन प्रकारचे शुल्क:
1) Brokerage — प्रत्येक ब्रोकरची शुल्क-रचना वेगळी: Upstox/Fyers — प्रति ऑर्डर ₹20, Shoonya — प्रति
   ऑर्डर ₹5, Stocko — निश्चित ₹1200/महिना (per-order नाही, फिक्स्ड सबस्क्रिप्शन प्लॅन). हे दर
   वापरकर्त्याने दिलेले आहेत — प्रत्यक्ष प्लॅन बदलल्यास इथेच अपडेट करा.
2) सरकारी/एक्सचेंज शुल्क (STT, Exchange Transaction Charge, SEBI Turnover Fee, Stamp Duty, त्यावरचा
   GST) — हे ब्रोकर कुठलाही असो, प्रत्येक NSE Index Options ऑर्डरवर सारखेच लागू होतात, आणि प्रत्यक्षात
   options साठी हे brokerage पेक्षाही मोठे असू शकतात (उदा. STT एकट्याचा 0.1% प्रीमियमवर). आधी हे
   शुल्क अजिबात मोजलेच जात नव्हते — त्यामुळे "Net P&L (charges नंतर)" प्रत्यक्षापेक्षा जास्त (overstated)
   दिसत होता. आता quantity/fill_price/transaction_type (order_log मधूनच उपलब्ध) वापरून प्रत्येक
   ऑर्डरचा turnover काढून हे शुल्क मोजले जातात.
   ⚠️ हे दर SEBI/NSE/सरकारकडून वेळोवेळी बदलतात (शेवटचा मोठा बदल — ऑक्टोबर 2024 मध्ये options STT
   0.0625% वरून 0.1% झालं). इथले दर 2024 अखेरच्या नियमांनुसार आहेत — प्रत्यक्ष broker च्या Contract
   Note/Ledger शी अधूनमधून पडताळून पाहा, आणि बदल झाल्यास इथेच अपडेट करा.

account_id → broker_type कसं ठरतं: order_log/live_trades मधला account_id सेट असेल तर cloud_db च्या
broker_accounts table (Supabase, फक्त multi-broker सेटअपमध्ये existent) मधून broker_type शोधला जातो.
account_id रिकामा (None) असेल — म्हणजे जुना/डीफॉल्ट सिंगल-अकाउंट प्रवाह (Manual Trading Panel आणि
जवळजवळ सर्व auto-trader scripts कायम adapter=None वापरतात, म्हणजे कायम फक्त Upstox token) — तेव्हा
"upstox" गृहीत धरलं जातं.
"""
import datetime

import numpy as np
import pandas as pd

BROKERAGE_PER_ORDER = {
    "upstox": 20.0,
    "fyers": 20.0,
    "shoonya": 5.0,
}
STOCKO_FLAT_MONTHLY = 1200.0
DEFAULT_BROKER = "upstox"

# --- सरकारी/एक्सचेंज शुल्क दर (NSE Index Options, प्रीमियम turnover वर) ---
STT_SELL_PCT = 0.001            # Securities Transaction Tax — फक्त SELL ऑर्डरवर (0.1%, ऑक्टो-2024 पासून)
EXCHANGE_TXN_PCT = 0.00035      # NSE Exchange Transaction Charge — BUY व SELL दोन्हीवर (अंदाजे 0.035%)
SEBI_TURNOVER_PCT = 0.0000001   # SEBI Turnover Fee — ₹10/कोटी — BUY व SELL दोन्हीवर
STAMP_DUTY_BUY_PCT = 0.00003    # Stamp Duty (राज्य सरकार) — फक्त BUY ऑर्डरवर (0.003%)
GST_PCT = 0.18                  # Brokerage + Exchange Txn Charge + SEBI Fee यावर 18% GST (STT/Stamp Duty वर GST नाही)

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


def _add_statutory_and_brokerage_charges(df):
    """प्रत्येक ऑर्डर-रांगेला brokerage + STT + Exchange Txn + SEBI Fee + Stamp Duty + त्यावरचा GST
    जोडते. turnover = quantity × (fill_price असेल तर तो, नाहीतर request price). Stocko साठी प्रति-ऑर्डर
    brokerage 0 (कारण ते निश्चित मासिक शुल्क आहे, खाली वेगळं जोडलं जातं) — पण STT/Exchange/SEBI/Stamp
    Duty Stocko वरही (कोणत्याही ब्रोकरवर) लागू होतातच, ते ब्रोकरच्या प्लॅनवर अवलंबून नसतात."""
    df = df.copy()

    def _numeric_col(name):
        if name not in df.columns:
            return pd.Series(float("nan"), index=df.index)
        return pd.to_numeric(df[name], errors="coerce")

    fill_price = _numeric_col("fill_price")
    req_price = _numeric_col("price")
    effective_price = fill_price.where(fill_price.notna() & (fill_price > 0), req_price).fillna(0.0).abs()
    quantity = _numeric_col("quantity").fillna(0.0).abs()
    df["turnover"] = quantity * effective_price

    if "transaction_type" in df.columns:
        txn_type = df["transaction_type"].fillna("").astype(str).str.upper()
    else:
        txn_type = pd.Series("", index=df.index)
    is_sell = txn_type == "SELL"
    is_buy = txn_type == "BUY"

    df["brokerage"] = df["broker_type"].map(BROKERAGE_PER_ORDER).fillna(0.0)
    df["stt"] = np.where(is_sell, df["turnover"] * STT_SELL_PCT, 0.0)
    df["exchange_txn"] = df["turnover"] * EXCHANGE_TXN_PCT
    df["sebi_fee"] = df["turnover"] * SEBI_TURNOVER_PCT
    df["stamp_duty"] = np.where(is_buy, df["turnover"] * STAMP_DUTY_BUY_PCT, 0.0)
    df["gst"] = (df["brokerage"] + df["exchange_txn"] + df["sebi_fee"]) * GST_PCT
    df["charge"] = df["brokerage"] + df["stt"] + df["exchange_txn"] + df["sebi_fee"] + df["stamp_duty"] + df["gst"]
    return df


def compute_charges(orders_df, start_date, end_date, broker_map=None):
    """
    orders_df: columns 'placed_at' (str/datetime-parseable), 'account_id' (nullable), आणि
      'quantity'/'fill_price'/'price'/'transaction_type' (STT/Exchange/SEBI/Stamp Duty साठी — नसतील
      तर ते शुल्क 0 धरले जातात, फक्त brokerage मोजला जातो).
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
    df = _add_statutory_and_brokerage_charges(df)

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
