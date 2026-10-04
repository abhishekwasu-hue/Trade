"""
run_sr_bot_level_backtest.py
------------------------------
🎓 5-Min Instant Trader आणि 15M Dynamic SR Reversal — जुने Dynamic S/R levels वि. SR V3 (grade A/B) levels, तेच entry/exit नियम
(`sr_bot_level_backtest.py` चा docstring बघा). Offline NIFTY 1-मिनिट डेटा (2015 → 2024-03), IS (2015–2021) आणि OOS (2022→) वेगळे.
कुठलाही order/DB/network नाही.

    python3 run_sr_bot_level_backtest.py --out /root/sr_bot_bt
    python3 run_sr_bot_level_backtest.py --start 2022-01-01 --bots 5m_instant      # जलद
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

import real_nifty_data
import sr_bot_level_backtest as SB

_PREP = None


def _job(args):
    bot, source, start, end = args
    return SB.simulate(_PREP, SB.BOTS[bot], source, start=start, end=end,
                       progress=lambda b, s, i, n, d: print(f"  {b}/{s}: {i}/{n} {d:%Y-%m-%d}", flush=True))


def main(argv=None, df1=None):
    global _PREP
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--bots", default="5m_instant,15m_reversal")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default="sr_bot_bt_out")
    args = p.parse_args(argv)
    t0 = time.time()
    df1 = real_nifty_data.load_nifty_1min() if df1 is None else df1
    if df1 is None or df1.empty:
        print("❌ offline NIFTY 1-मिनिट डेटा सापडला नाही.")
        return 1
    _PREP = SB.prepare(df1)
    print(f"डेटा तयार ({time.time() - t0:.0f}s): {len(_PREP.days)} दिवस", flush=True)
    jobs = [(b.strip(), s, args.start, args.end) for b in args.bots.split(",") if b.strip() in SB.BOTS for s in SB.SOURCES]
    if args.workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=min(args.workers, len(jobs))) as ex:
            results = list(ex.map(_job, jobs))
    else:
        results = [_job(j) for j in jobs]
    trades = pd.concat([r for r in results if len(r)], ignore_index=True) if any(len(r) for r in results) else pd.DataFrame()
    os.makedirs(args.out, exist_ok=True)
    trades.to_csv(os.path.join(args.out, "sr_bot_trades.csv"), index=False)
    cmp_ = SB.comparison(trades)
    yw = SB.yearwise(trades)
    cmp_.to_csv(os.path.join(args.out, "sr_bot_comparison.csv"), index=False)
    yw.to_csv(os.path.join(args.out, "sr_bot_yearwise.csv"), index=False)
    pd.set_option("display.width", 200)
    print("\n=== जुने Dynamic वि. SR V3 (A/B) — IS / OOS वेगळे (spot points; option P&L नाही) ===")
    print(cmp_.to_string(index=False) if len(cmp_) else "(trades नाहीत)")
    if len(yw):
        print("\n=== वर्षनिहाय ===")
        print(yw.pivot_table(index=["bot", "year"], columns="source", values=["trades", "avg_pts"]).to_string())
    print(f"\nCSV: {os.path.abspath(args.out)} (एकूण {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
