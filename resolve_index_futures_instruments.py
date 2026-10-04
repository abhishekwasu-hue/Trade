"""
resolve_index_futures_instruments.py
--------------------------------------
🎓 Opportunity Engine (spec §10): `resolve_mcx_futures_instruments.py` च्या पॅटर्नवर — NIFTY/BANKNIFTY चा सध्याचा **front-month futures** contract
(अजून expire न झालेल्यांपैकी सर्वात जवळचा; हार्डकोडेड expiry नाही) Upstox Search Instruments API कडून. फक्त **वाचतो** (कुठलाही order नाही).
Resolve चा नियम (trading_symbol चा " FUT" आधीचा भाग तंतोतंत symbol; FINNIFTY/NIFTYNXT50 वगळले) PR-0 च्या `verify_opportunity_data_availability`
मधला तोच वापरला आहे — नवीन copy नाही.

    python3 resolve_index_futures_instruments.py
    python3 resolve_index_futures_instruments.py --symbols NIFTY --token <UPSTOX_TOKEN>
"""
import argparse
import sys

import cloud_db
import verify_opportunity_data_availability as V
from config import get_ist_today

INDEX_FUTURES_SYMBOLS = ("NIFTY", "BANKNIFTY")


def resolve_index_futures_instruments(token, symbols=INDEX_FUTURES_SYMBOLS, today=None):
    """रिटर्न {symbol: (info|None, error|None)} — info = {trading_symbol, instrument_key, expiry, lot_size}."""
    today = today or get_ist_today()
    return {s: V.resolve_front_future(token, s, today) for s in symbols}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=None)
    parser.add_argument("--symbols", default=",".join(INDEX_FUTURES_SYMBOLS))
    args = parser.parse_args(argv)
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ Upstox token उपलब्ध नाही.")
        return 1
    bad = 0
    for sym, (info, err) in resolve_index_futures_instruments(token, [s.strip().upper() for s in args.symbols.split(",") if s.strip()]).items():
        if info is None:
            bad += 1
            print(f"❌ {sym}: {err}")
        else:
            print(f"✅ {sym}: {info['trading_symbol']} | {info['instrument_key']} | expiry {info['expiry']} | lot {info['lot_size']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
