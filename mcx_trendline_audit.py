"""
mcx_trendline_audit.py
------------------------
🎓 टप्पा 1 (trendlines — फक्त चाचणी, trading नाही): MCX symbol चे 30M candles → पूर्ण 60M → प्रत्येक 60M candle ला फक्त तोपर्यंतच्या डेटावरून
(no-lookahead) उतरती resistance / चढती support रेषा; रेषेला touch झाल्यावर पुढच्या 10 तासांत भाव 1 × range उलटा फिरला (HOLD) की रेषा तुटली
(BREAK). तुलना: त्याच उताराच्या पण ±1/±2 range सरकवलेल्या (random-सारख्या) रेषा. खऱ्या रेषा control पेक्षा जास्त टिकत नसतील तर logic
उपयोगी नाही. IS/OOS तारखेनुसार वेगळे. काहीही बदलत नाही.

    python3 mcx_trendline_audit.py --symbol SILVER --days 60
"""
import argparse
import os
import sys


from price_action import trendlines as TL


def main(argv=None, fetch=None, token=None, resolve=None, now=None):
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="SILVER")
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--min-touches", type=int, default=2)
    p.add_argument("--out", default="mcx_replay_out")
    args = p.parse_args(argv)
    sym = args.symbol.upper()
    if fetch is None:
        from upstox_api import fetch_mcx_candles as fetch
    if resolve is None:
        import resolve_mcx_futures_instruments as R
        resolve = R.resolve_symbol
    if token is None:
        import cloud_db
        token = cloud_db.get_effective_upstox_token(None)
    if now is None:
        from config import get_ist_now
        now = get_ist_now()
    if not token:
        print("❌ Upstox token नाही.")
        return 1
    ok, r = resolve(token, sym)
    if not ok:
        print(f"❌ {sym}: contract सापडला नाही ({r})")
        return 1
    df30 = fetch(token, r["instrument_key"], interval="30minute", lookback_days=args.days)
    df60 = TL.completed_hours(df30, now)
    print(f"{sym} ({r['trading_symbol']}): {len(df60)} पूर्ण 60M candles"
          + (f", {df60['timestamp'].iloc[0]:%d %b} ते {df60['timestamp'].iloc[-1]:%d %b %H:%M}" if len(df60) else ""))
    lines = TL.detect_trendlines(df60, min_touches=args.min_touches)
    for ln in lines:
        print(f"  आत्ताची {ln['kind']}: {ln['a_ts']:%d %b %H:%M} ({ln['a_price']:,.2f}) → {ln['b_ts']:%d %b %H:%M} ({ln['b_price']:,.2f}), "
              f"{ln['touches']} touches, उतार {ln['slope']:+.2f}/तास, पुढच्या तासाला ≈ {ln['next_price']:,.2f}")
    if not lines:
        print("  आत्ता वैध तिरकी रेषा नाही.")
    events = TL.audit_touches(df60, min_touches=args.min_touches)
    summ = TL.summarize_audit(events)
    print("\n=== टिकण्याचा दर: खऱ्या रेषा (real) वि. समांतर सरकवलेल्या (control) — IS = पहिले 60% दिवस ===")
    print(summ.to_string(index=False) if len(summ) else "(touches सापडले नाहीत — डेटा कमी)")
    os.makedirs(args.out, exist_ok=True)
    if len(events):
        events.to_csv(os.path.join(args.out, f"trendline_audit_{sym}.csv"), index=False)
    print("\nलहान sample — फक्त दिशादर्शक. हा script काहीही बदलत नाही.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
