"""
run_opportunity_backtest.py
-----------------------------
Opportunity Engine चा backtest (D1–D3, तिन्ही variants V1/V2/V3) खऱ्या offline NIFTY डेटावर (2015-01-09 → 2024-03-27, index; volume नाही) चालवून निकाल CSV मध्ये साठवणे.
कुठलाही order/DB/network नाही. निकाल जसे आले तसे — ट्यूनिंग नाही. Walk-forward: IS 2015-01→2021-12, OOS 2022-01→2024-03; verdict फक्त अहवाल.

    python3 run_opportunity_backtest.py --out /tmp/oe_bt                 # पूर्ण (≈ 10–15 मिनिटं)
    python3 run_opportunity_backtest.py --start 2022-01-01 --variants V1  # जलद
"""
import argparse
import os
import sys
import time

import pandas as pd

import real_nifty_data
from opportunity_engine import sessions
from opportunity_engine.backtest import BacktestConfig, VARIANT_TEXT, run_backtest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=None, help="trading सुरू तारीख (warm-up आधीपासूनच)")
    parser.add_argument("--end", default=None)
    parser.add_argument("--variants", default="V1,V2,V3")
    parser.add_argument("--detectors", default="D1,D2,D3")
    parser.add_argument("--out", default="oe_backtest_out")
    args = parser.parse_args(argv)

    t0 = time.time()
    df = real_nifty_data.load_nifty_1min()
    if df.empty:
        print("❌ offline NIFTY डेटा सापडला नाही (data/nifty50_1min.parquet).")
        return 1
    frames = sessions.build_frames(df)
    bcfg = BacktestConfig(start=args.start, end=args.end, variants=tuple(v.strip() for v in args.variants.split(",")), detectors=tuple(d.strip() for d in args.detectors.split(",")))
    print(f"डेटा तयार ({time.time() - t0:.0f}s); timeline आणि replay चालू…", flush=True)
    res = run_backtest(frames, bcfg, progress=lambda i, n, d: print(f"  {i}/{n} {d}", flush=True) if i % 500 == 0 else None)
    os.makedirs(args.out, exist_ok=True)
    res.comparison.to_csv(os.path.join(args.out, "variants_comparison.csv"), index=False)
    for v, r in res.results.items():
        for name in ("trades", "virtual", "decisions"):
            r[name].to_csv(os.path.join(args.out, f"{v}_{name}.csv"), index=False)
        for name, table in res.tables(v).items():
            table.to_csv(os.path.join(args.out, f"{v}_{name}.csv"), index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    print("\n=== Variants तुलना ===")
    print(res.comparison.to_string(index=False))
    for v in res.results:
        t = res.tables(v)
        print(f"\n=== {v}: {VARIANT_TEXT.get(v, '')} ===")
        print(t["summary"].to_string(index=False))
        print(t["verdicts"].to_string(index=False))
        print(t["aligned_vs_counter"].to_string(index=False))
    print(f"\nनिकाल CSV: {os.path.abspath(args.out)}  (एकूण {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
