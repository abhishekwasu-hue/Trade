"""verify_mcx_order_quantity_units.py
--------------------------------------
फक्त वाचणारा (कुठलाही order/trade नाही) — Upstox Margin API ला MCX contracts साठी `quantity = lot_size`
देऊन विचारतो, आणि लागणारी margin 1 lot च्या contract value शी ताडतो:
  • margin ≈ contract value च्या काही % (साधारण 3–30%)  => Upstox API ची quantity = UNITS (lot_size = 1 lot) ✅
  • margin ≈ contract value च्या 1.2 पट किंवा जास्त     => quantity = LOTS (lot_size पाठवल्यास lot_size lots जातील!) ❌
सर्व तपासलेल्या commodities 'UNITS' दाखवत असतील तरच data/mcx_quantity_units_verified.json लिहिली जाते —
ती असल्याशिवाय MCX चा LIVE order bot कडून नाकारला जातो (mcx_quantity_check.py).

चालवणे (VPS वर, बाजार चालू असताना — LTP साठी):
    python3 verify_mcx_order_quantity_units.py
    python3 verify_mcx_order_quantity_units.py --token <UPSTOX_TOKEN>
"""
import argparse

import cloud_db
import resolve_mcx_futures_instruments as resolver
from mcx_contract_specs import get_price_multiplier
from mcx_quantity_check import MARKER_PATH, classify_quantity_semantics, write_verified_marker
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
    verdict = classify_quantity_semantics(margin, one_lot_value)
    return {
        "symbol": symbol, "verdict": verdict, "instrument_key": key, "lot_size": lot_size, "ltp": ltp,
        "margin_for_quantity_eq_lot_size": margin, "one_lot_contract_value": one_lot_value,
        "ratio": (margin / one_lot_value) if margin and one_lot_value else None,
    }


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
        print(
            f"{'✅' if r['verdict'] == 'UNITS' else '❌' if r['verdict'] == 'LOTS' else '⚠️'} {r['symbol']}: quantity={r['lot_size']} → "
            f"margin ₹{(r.get('margin_for_quantity_eq_lot_size') or 0):,.0f} | 1 lot contract value ₹{r['one_lot_contract_value']:,.0f} | "
            f"गुणोत्तर {ratio} => {r['verdict']}"
        )

    verdicts = {r["verdict"] for r in results}
    if verdicts == {"UNITS"}:
        write_verified_marker([{k: v for k, v in r.items()} for r in results])
        print(f"\n✅ सर्व 'UNITS' — Upstox quantity = units (lot_size = 1 lot). मार्कर लिहिला: {MARKER_PATH}")
        print("   आता MCX LIVE order (lots × lot_size) चा आकार बरोबर आहे; गेट उघडला.")
    elif "LOTS" in verdicts:
        print("\n❌ Upstox MCX quantity 'LOTS' मध्ये दिसते — bot चा quantity (lots × lot_size) चुकीचा, MCX LIVE करू नका! "
              "मला (Claude ला) हा output कळवा — quantity = lots करणं लागेल. मार्कर लिहिला नाही; MCX LIVE गेट बंदच राहील.")
        raise SystemExit(2)
    else:
        print("\n⚠️ निकाल अस्पष्ट/अपुरा (बाजार बंद असेल तर LTP नसतो) — मार्कर लिहिला नाही; MCX LIVE गेट बंदच राहील. "
              "बाजार चालू असताना पुन्हा चालवा, किंवा हा output मला कळवा.")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
