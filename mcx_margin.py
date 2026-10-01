"""
mcx_margin.py
------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा ("Commodity nusar Required Margin pn dakhwa") — MCX Futures च्या प्रत्येक
commodity साठी, Upstox च्या अधिकृत Margin Calculator API (upstox_api.fetch_required_margin — तेच जे bot
trade उघडण्याआधी margin check साठी वापरतो) वरून BUY आणि SELL दोन्ही बाजूंची आवश्यक margin.

Streamlit-मुक्त (page_mcx_futures.py कॅश/UI सांभाळतो) — त्यामुळे नेटवर्क कॉल्स injectable आणि टेस्ट करता येतात.
कुठलाही अंदाज दाखवला जात नाही: Margin API ने आकडा दिला नाही तर स्तंभ रिकामा (None) राहतो.
"""
import resolve_mcx_futures_instruments as mcx_resolver
from mcx_contract_specs import get_price_multiplier
from upstox_api import fetch_ltp_map, fetch_required_margin

MARGIN_COLUMNS = [
    "Commodity", "Contract", "Lot Size", "Lots", "LTP", "Contract Value (Rs)",
    "BUY Margin (Rs)", "SELL Margin (Rs)", "BUY / lot (Rs)", "SELL / lot (Rs)", "स्थिती",
]


def _one_order(instrument_key, quantity, side, product):
    return [{"instrument_token": instrument_key, "quantity": quantity, "transaction_type": side, "product": product}]


def compute_margin_rows(access_token, symbols, lots_by_symbol, product="D",
                        resolve_fn=None, ltp_fn=None, margin_fn=None):
    """symbols की प्रत्येक commodity साठी एक dict-रांग (MARGIN_COLUMNS ह्या keys). lots_by_symbol —
    {symbol: सेव्ह केलेले lots}; न मिळाल्यास 1. resolve_fn/ltp_fn/margin_fn — फक्त टेस्टसाठी (डीफॉल्ट: खरे)."""
    resolve_fn = resolve_fn or mcx_resolver.resolve_symbol
    ltp_fn = ltp_fn or fetch_ltp_map
    margin_fn = margin_fn or fetch_required_margin
    rows = []
    for sym in symbols:
        lots = int(lots_by_symbol.get(sym, 1) or 1)
        row = {c: None for c in MARGIN_COLUMNS}
        row.update({"Commodity": sym, "Lots": lots})
        try:
            ok, resolved = resolve_fn(access_token, sym)
        except Exception as exc:  # एका commodity चा नेटवर्क अडथळा बाकीच्यांना थांबवू नये
            ok, resolved = False, str(exc)
        if not ok:
            row["स्थिती"] = f"Contract सापडला नाही: {resolved}"
            rows.append(row)
            continue
        key, lot_size = resolved["instrument_key"], int(resolved["lot_size"])
        qty = lot_size * lots
        row["Contract"] = resolved.get("trading_symbol") or key
        row["Lot Size"] = lot_size
        try:
            ltp = (ltp_fn(access_token, [key]) or {}).get(key)
        except Exception:
            ltp = None
        row["LTP"] = ltp
        # 🎓 GOLD: भाव प्रति 10g, lot 1kg => Contract Value = भाव × qty × 100 (बघा mcx_contract_specs)
        row["Contract Value (Rs)"] = round(ltp * qty * get_price_multiplier(sym), 2) if ltp else None
        buy = margin_fn(access_token, _one_order(key, qty, "BUY", product))
        sell = margin_fn(access_token, _one_order(key, qty, "SELL", product))
        row["BUY Margin (Rs)"] = round(buy, 2) if buy is not None else None
        row["SELL Margin (Rs)"] = round(sell, 2) if sell is not None else None
        row["BUY / lot (Rs)"] = round(buy / lots, 2) if buy is not None else None
        row["SELL / lot (Rs)"] = round(sell / lots, 2) if sell is not None else None
        row["स्थिती"] = "OK" if buy is not None and sell is not None else "Margin API ने आकडा दिला नाही"
        rows.append(row)
    return rows


def total_worst_case_margin(rows):
    """सर्व commodities एकाच वेळी उघडल्यास (प्रत्येकाची BUY/SELL पैकी मोठी) margin ची बेरीज; एकही आकडा
    नसेल तर None."""
    vals = [
        max(v for v in (r.get("BUY Margin (Rs)"), r.get("SELL Margin (Rs)")) if v is not None)
        for r in rows if r.get("BUY Margin (Rs)") is not None or r.get("SELL Margin (Rs)") is not None
    ]
    return sum(vals) if vals else None
