"""verify_mcx_order_quantity_units.py
--------------------------------------
फक्त वाचणारा (कुठलाही order/trade नाही) — Upstox Margin API ला MCX contracts साठी `quantity = lot_size` आणि
`quantity = 1` देऊन विचारतो, आणि लागणारी margin 1 lot च्या contract value शी ताडतो:
  • quantity=lot_size ची margin ≈ contract value च्या 1.2 पट किंवा जास्त (आणि quantity=1 ची 2–60%) => Upstox API ची
    quantity = LOTS ✅ (bot आता broker ला lots पाठवतो — हेच बरोबर)
  • quantity=lot_size ची margin ≈ contract value च्या काही % => quantity = UNITS ❌ (bot चं सध्याचं lots पाठवणं चुकीचं!)
फक्त lot_size > 1 असलेल्या commodities (SILVER/CRUDEOIL...) भेद करू शकतात; GOLD चा lot_size 1 आहे, त्यामुळे तो वगळला जातो.
सर्व भेद-करणारे commodities 'LOTS' दाखवत असतील तरच data/mcx_quantity_units_verified.json लिहिली जाते —
ती असल्याशिवाय MCX चा LIVE order bot कडून नाकारला जातो (mcx_quantity_check.py).

चालवणे (VPS वर, बाजार चालू असताना — LTP साठी):
    python3 verify_mcx_order_quantity_units.py
    python3 verify_mcx_order_quantity_units.py --token <UPSTOX_TOKEN>
"""
import argparse

import cloud_db
import resolve_mcx_futures_instruments as resolver
from mcx_contract_specs import get_price_multiplier
from mcx_quantity_check import (
    MARKER_PATH, ONE_LOT_MARGIN_MAX_RATIO, ONE_LOT_MARGIN_MIN_RATIO, classify_quantity_semantics, write_verified_marker,
)
from upstox_api import fetch_ltp_map, fetch_required_margin

CHECK_SYMBOLS = ["SILVER", "GOLD", "CRUDEOIL"]


def check_symbol(token, symbol):
    ok, info = resolver.resolve_symbol(token, symbol)
    if not ok:
        return {"symbol": symbol, "verdict": "UNKNOWN", "reason": str(info)}
    lot_size = info.get("lot_size")
    key = info.get("instrument_key")
    ltp = fetch_ltp_map(token, [key]).get(key)
    if not lot_size or not ltp:
        return {"symbol": symbol, "verdict": "UNKNOWN", "reason": f"lot_size={lot_size}, LTP={ltp} — आकडे मिळाले नाहीत"}
    margin = fetch_required_margin(token, [{
        "instrument_token": key, "quantity": int(lot_size), "transaction_type": "BUY", "product": "D",
    }])
    one_lot_value = float(lot_size) * float(ltp) * get_price_multiplier(symbol)
    result = {
        "symbol": symbol, "instrument_key": key, "lot_size": lot_size, "ltp": ltp,
        "margin_for_quantity_eq_lot_size": margin, "one_lot_contract_value": one_lot_value,
        "ratio": (margin / one_lot_value) if margin and one_lot_value else None,
    }
    if int(lot_size) <= 1:
        result["verdict"] = "N/A"  # lot_size = 1 => units आणि lots सारखेच, भेद करता येत नाही
        return result
    verdict = classify_quantity_semantics(margin, one_lot_value)
    margin_one = fetch_required_margin(token, [{
        "instrument_token": key, "quantity": 1, "transaction_type": "BUY", "product": "D",
    }])
    ratio_one = (margin_one / one_lot_value) if margin_one and one_lot_value else None
    result["margin_for_quantity_1"], result["ratio_one"] = margin_one, ratio_one
    if verdict == "LOTS" and not (ratio_one is not None and ONE_LOT_MARGIN_MIN_RATIO <= ratio_one <= ONE_LOT_MARGIN_MAX_RATIO):
        verdict = "UNKNOWN"  # quantity=1 ची margin 1 पूर्ण lot सारखी दिसत नाही — खात्री नाही
    result["verdict"] = verdict
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    args = parser.parse_args()
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही.")
        raise SystemExit(1)

    results = [check_symbol(token, s) for s in CHECK_SYMBOLS]
    for r in results:
        if r["verdict"] == "UNKNOWN" and "reason" in r:
            print(f"⚠️ {r['symbol']}: {r['reason']}")
            continue
        ratio = f"{r['ratio']:.3f}" if r.get("ratio") is not None else "—"
        ratio_one = f" | quantity=1 गुणोत्तर {r['ratio_one']:.3f}" if r.get("ratio_one") is not None else ""
        icon = {"LOTS": "✅", "UNITS": "❌", "N/A": "➖"}.get(r["verdict"], "⚠️")
        print(
            f"{icon} {r['symbol']}: quantity={r['lot_size']} → margin ₹{(r.get('margin_for_quantity_eq_lot_size') or 0):,.0f} | "
            f"1 lot contract value ₹{r['one_lot_contract_value']:,.0f} | गुणोत्तर {ratio}{ratio_one} => {r['verdict']}"
        )

    deciding = [r["verdict"] for r in results if r["verdict"] != "N/A"]
    if deciding and set(deciding) == {"LOTS"}:
        write_verified_marker([{k: v for k, v in r.items()} for r in results])
        print(f"\n✅ Upstox MCX quantity = LOTS (पडताळलं). bot broker ला lots पाठवतो — हेच बरोबर. मार्कर लिहिला: {MARKER_PATH}")
        print("   MCX LIVE गेट उघडला (फक्त Upstox वर, आणि फक्त तुम्ही Mode LIVE निवडल्यास).")
    elif "UNITS" in deciding:
        print("\n❌ Upstox MCX quantity 'UNITS' दिसते — bot चं lots पाठवणं चुकीचं! MCX LIVE करू नका; हा output मला कळवा. "
              "मार्कर लिहिला नाही; MCX LIVE गेट बंदच राहील.")
        raise SystemExit(2)
    else:
        print("\n⚠️ निकाल अस्पष्ट/अपुरा (बाजार बंद असेल तर LTP नसतो) — मार्कर लिहिला नाही; MCX LIVE गेट बंदच राहील. "
              "बाजार चालू असताना पुन्हा चालवा, किंवा हा output मला कळवा.")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
