"""
iv_snapshot_collector.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली, नवीन script ("Record iv of option premium daily for analysis") —
NIFTY च्या ATM ± 5 strikes (CE+PE) चा Implied Volatility (व सोबतच LTP, underlying_price) साठवणे —
जेणेकरून "काल IV काय होता, आज काय आहे" अशी तुलना Dashboard/analysis मधून लगेच करता येईल, दर वेळी
हाताने PDF/live fetch वरून काढण्याऐवजी.

fetch_option_greeks() (आधीच अस्तित्वात, Strategy Builder च्या "Combined Greeks" साठी वापरलेला —
Upstox च्या v3/market-quote/option-greek endpoint वरून थेट IV) हाच पुनर्वापर केला आहे — वेगळी
गणना/नवीन endpoint लागत नाही. cloud_db.STRIKE_STEP (established, इतर bots मध्येही वापरलेला) वरून
प्रत्येक symbol चा योग्य strike-अंतर.

🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Average IV Breakout Gate — dynamic_sr_instant_trader.py
चा नवीन entry_iv_gate_enabled) — आधी हे script रोज **एकदाच** (EOD आधी) चालायचं (फक्त "काल" चा record
साठी पुरेसं). आता Gate ला "आजचा ताजा IV" (oi_snapshot_collector.py च्या PCR सारखाच) intraday सुद्धा
हवा असल्याने, बाजार-तासांत **दर ~15-20 मिनिटांनी सुद्धा** चालवायला हवं (खाली crontab बघा,
deploy/README.md मध्ये नोंदवलेलं) — collection-logic (ATM±5 strikes) बदललेलं नाही, फक्त वारंवारता.

चालवणे (VPS वर crontab — deploy/README.md मध्ये तयार आहे — दिवसातून अनेकदा + EOD, दोन्हीसाठी एकच):
    python3 iv_snapshot_collector.py --token <UPSTOX_TOKEN>
"""
import argparse
import sys

import cloud_db
from config import get_ist_now
from upstox_api import fetch_option_greeks, fetch_upstox_option_chain

IV_SYMBOLS = ["NIFTY"]
STRIKE_RANGE = 5  # ATM च्या दोन्ही बाजूंनी किती strikes


def collect_symbol(access_token, symbol, strike_range=STRIKE_RANGE):
    """एका symbol साठी ATM ± strike_range strikes (CE+PE) चा IV काढून साठवणे."""
    raw_chain, status = fetch_upstox_option_chain(access_token, symbol)
    if not raw_chain:
        return False, f"{symbol}: option chain मिळाला नाही ({status})"

    underlying_price = raw_chain[len(raw_chain) // 2].get("underlying_spot_price", 0)
    if not underlying_price:
        return False, f"{symbol}: underlying price मिळाली नाही"

    step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
    atm_strike = round(underlying_price / step) * step

    legs = []  # (strike, option_type, instrument_key, expiry)
    ltp_map = {}
    for item in raw_chain:
        strike = item.get("strike_price")
        expiry = item.get("expiry")
        for side_key, option_type in (("call_options", "CE"), ("put_options", "PE")):
            leg = item.get(side_key, {}) or {}
            instrument_key = leg.get("instrument_key")
            if instrument_key:
                ltp_map[instrument_key] = (leg.get("market_data", {}) or {}).get("ltp")
            if strike is not None and abs(strike - atm_strike) <= strike_range * step and instrument_key:
                legs.append((strike, option_type, instrument_key, expiry))

    if not legs:
        return False, f"{symbol}: ATM ± {strike_range} strikes च्या आत कुठलेही legs सापडले नाहीत (ATM={atm_strike})"

    instrument_keys = [leg[2] for leg in legs]
    greeks_map = fetch_option_greeks(access_token, instrument_keys)

    now_dt = get_ist_now()
    trade_date = now_dt.strftime("%Y-%m-%d")
    snapshot_time = now_dt.strftime("%H:%M")

    rows = [
        {
            "strike": strike, "option_type": option_type, "expiry": expiry,
            "iv": greeks_map.get(instrument_key, {}).get("iv"), "ltp": ltp_map.get(instrument_key),
            "underlying_price": underlying_price,
        }
        for strike, option_type, instrument_key, expiry in legs
    ]

    saved = cloud_db.save_iv_snapshot(symbol, trade_date, snapshot_time, rows)
    if not saved:
        return False, f"{symbol}: Supabase मध्ये साठवता आलं नाही (जोडणी तपासा)"
    return True, f"{symbol}: {len(rows)} legs (ATM±{strike_range} strikes, ATM={atm_strike}) IV साठवला"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(IV_SYMBOLS))
    args = parser.parse_args()

    cloud_db.init_cloud_table()
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)
    all_ok = True
    for symbol in args.symbols.split(","):
        ok, message = collect_symbol(token, symbol.strip())
        print(("✅ " if ok else "❌ ") + message)
        all_ok = all_ok and ok

    sys.exit(0 if all_ok else 1)
