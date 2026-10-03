"""mcx_quantity_check.py
--------------------------------
🎓 MCX LIVE सुरक्षा-गेट — Upstox चा MCX `quantity` **lots** मध्ये आहे (VPS वर Margin API ने पडताळलेलं: SILVER
quantity=30 => 30 lots, margin ₹2.59 कोटी = 30 × ₹8.64 लाख). म्हणून आपला bot MCX orders साठी broker ला lots पाठवतो
(`broker_quantity`, बघा upstox_api.broker_order_quantity); `quantity` (units) फक्त Order Log / charges साठी.
`verify_mcx_order_quantity_units.py` (फक्त वाचणारा, कुठलाही order न टाकणारा) हेच पुन्हा खात्री करून मार्कर फाईल
लिहीत नाही तोपर्यंत MCX चा LIVE order trading_engine.open_multi_leg_trade() मध्ये नाकारला जातो. PAPER वर परिणाम नाही.
"""
import json
import os

from config import DATA_DIR, get_ist_now

MARKER_PATH = os.path.join(DATA_DIR, "mcx_quantity_units_verified.json")

# margin(quantity=lot_size) ÷ (lot_size × भाव × price-multiplier = 1 lot चं contract value):
#   quantity ला "units" मानल्यास हे गुणोत्तर 1 lot च्या margin% इतकं (साधारण 0.03–0.30) येतं;
#   "lots" मानल्यास quantity=lot_size म्हणजे lot_size lots => गुणोत्तर साधारण lot_size × margin% (>= 1).
# (फक्त lot_size > 1 असलेल्या commodities साठी भेद करता येतो — GOLD चा lot_size 1 आहे, तिथे दोन्ही सारखंच.)
ONE_LOT_MARGIN_MIN_RATIO = 0.02   # margin(quantity=1) ÷ 1 lot चं contract value — "1 = 1 पूर्ण lot" ची पुष्टी
ONE_LOT_MARGIN_MAX_RATIO = 0.60
UNITS_MAX_RATIO = 0.5
LOTS_MIN_RATIO = 1.2


def classify_quantity_semantics(margin_for_lot_size_qty, one_lot_contract_value):
    """'UNITS' | 'LOTS' | 'UNKNOWN' (आकडे अवैध किंवा निकाल अस्पष्ट असल्यास)."""
    try:
        margin = float(margin_for_lot_size_qty)
        value = float(one_lot_contract_value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if margin <= 0 or value <= 0:
        return "UNKNOWN"
    ratio = margin / value
    if ratio <= UNITS_MAX_RATIO:
        return "UNITS"
    if ratio >= LOTS_MIN_RATIO:
        return "LOTS"
    return "UNKNOWN"


def write_verified_marker(details):
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {"verified_at": get_ist_now().isoformat(timespec="seconds"), "semantics": "LOTS", "details": details}
    with open(MARKER_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def is_mcx_live_quantity_verified():
    """मार्कर फाईल आहे आणि त्यात semantics == 'LOTS' (Upstox MCX quantity = lots) असेल तरच True."""
    try:
        with open(MARKER_PATH, encoding="utf-8") as f:
            return json.load(f).get("semantics") == "LOTS"
    except (OSError, ValueError):
        return False
