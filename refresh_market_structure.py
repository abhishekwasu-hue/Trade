"""
refresh_market_structure.py
--------------------------------
Opportunity Engine चा Structure Journal (Daily/4H/1H/15M trend state, events, zones+Level Quality) रोज (EOD) पुन्हा-गणना करून Supabase च्या *स्वतःच्या* तीन tables मध्ये
(market_structure_state / market_structure_events / opportunity_zones) साठवणे. `market_zones` ला कधीच हात लागत नाही — live bots अबाधित.

    python3 refresh_market_structure.py --token <UPSTOX_TOKEN>            # token न दिल्यास Supabase मधून
    python3 refresh_market_structure.py --brief                            # + Telegram वर मराठी "structure वही" (09:00 साठी)
    python3 refresh_market_structure.py --dry-run                          # फक्त गणना/सारांश, साठवत नाही
VPS crontab आणि GitHub Actions (workflow_dispatch backup) — deploy/README.md बघा. कुठलाही order होत नाही.
"""
import argparse
import sys

import cloud_db
from notifications import notify_error, send_telegram_message
from opportunity_engine import store
from opportunity_engine.refresh import SYMBOLS, refresh_symbol
from upstox_api import fetch_candles


def fetch(token, symbol, interval, lookback_days):
    return fetch_candles(token, symbol, current_spot=0, interval=interval, lookback_days=lookback_days)


def main(argv=None, mode="eod", fetch_fn=fetch, store_mod=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--brief", action="store_true", help="Telegram वर मराठी structure वही पाठवा")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.dry_run:
        cloud_db.init_cloud_table()
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        return 1
    all_ok = True
    for symbol in [s.strip() for s in args.symbols.split(",") if s.strip()]:
        ok, message = refresh_symbol(symbol, token, fetch_fn, store_mod=store_mod or store, mode=mode, notify=send_telegram_message, send_brief=args.brief, dry_run=args.dry_run)
        print(("✅ " if ok else "❌ ") + message)
        if not ok:
            notify_error(f"refresh_market_structure[{mode}]", message)
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
