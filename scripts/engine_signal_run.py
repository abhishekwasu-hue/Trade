#!/usr/bin/env python3
"""🧭 Engine signal service (Abhi, Monday PAPER): शेवटच्या **बंद** 15M candle वर common analysis engine (decision2, थर 1–7) ⇒
`engine_signal` store (VPS local SQLite). Bots हा store adapter ने वाचतात (signal_source own / engine / both); own असताना फक्त
shadow मत (Vision caption). Order / broker call नाही. Code मध्ये तारीख नाही. Holdout rows कधीच नाहीत (data_policy).

VPS cron (VPS ची वेळ UTC — deploy/README.md; बाजार 03:45–10:00 UTC; प्रत्येक 15M candle बंद झाल्यावर ~1 मिनिटाने; बाजार बंद ⇒ script स्वतः थांबतो):
  1,16,31,46 3-10 * * 1-5  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/engine_signal_run.py >> engine_signal.log 2>&1
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import engine_signal as ES  # noqa: E402


def main(argv=None, token_fn=None, run_fn=None, market_fn=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NIFTY")
    ap.add_argument("--force", action="store_true", help="बाजार बंद असला तरी (dry-run / तपासणी)")
    a = ap.parse_args(argv)
    if market_fn is None:
        from config import is_market_open as market_fn
    if not a.force and not market_fn():
        print("बाजार बंद ⇒ engine signal नाही")
        return 0
    if token_fn is None:
        import cloud_db
        token_fn = lambda: cloud_db.get_effective_upstox_token(None)  # noqa: E731
    tok = token_fn()
    if not tok:
        print("❌ Upstox token नाही — engine signal मोजता येत नाही (आधी daily login)")
        return 2
    run_fn = run_fn or ES.run
    rc = 0
    for sym in [x.strip().upper() for x in a.symbols.split(",") if x.strip()]:
        try:
            r = run_fn(sym, tok)
            print(f"✅ {sym} {r['bar_ts']}: {r['decision']} {r.get('gate') or ''} dir {r.get('direction')} · {ES.opinion(sym, r['bar_ts'])}")
        except Exception as exc:
            print(f"⚠️ {sym}: {type(exc).__name__}: {exc}")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
