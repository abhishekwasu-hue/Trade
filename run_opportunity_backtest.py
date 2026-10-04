"""
run_opportunity_backtest.py
-----------------------------
Opportunity Engine चा backtest (D1–D3, तिन्ही variants V1/V2/V3) खऱ्या offline NIFTY डेटावर (2015-01-09 → 2024-03-27, index; volume नाही) चालवून निकाल CSV मध्ये साठवणे.
कुठलाही order/DB/network नाही. निकाल जसे आले तसे — ट्यूनिंग नाही. Walk-forward: IS 2015-01→2021-12, OOS 2022-01→2024-03; verdict फक्त अहवाल.

    python3 run_opportunity_backtest.py --out /tmp/oe_bt                 # पूर्ण (≈ 10–15 मिनिटं)
    python3 run_opportunity_backtest.py --start 2022-01-01 --variants V1  # जलद
    python3 run_opportunity_backtest.py --diagnostics --variants V1       # + निदान (exit/MAE-MFE/counterfactual/मोठे losses/funnel/D2), सर्व IS-OOS वेगळे
    # volume सकट वि. volume शिवाय (collect_index_futures_volume.py ने गोळा केलेला डेटा; त्याच काळाचे Upstox index 5M):
    python3 run_opportunity_backtest.py --index-5m data/oe_index_5min_NIFTY.parquet --futures-volume data/oe_futures_5min_NIFTY.parquet --variants V1
    # Dual-Eye consensus: visual backfill (run_visual_backfill.py) नंतर तिन्ही modes चा तुलना तक्ता (फक्त backfill कालावधी):
    python3 run_opportunity_backtest.py --visual-cache data/oe_visual_backfill_NIFTY.jsonl --start 2022-01-01 --variants V1
"""
import argparse
import os
import sys
import time

import pandas as pd

import real_nifty_data
from opportunity_engine import sessions
from opportunity_engine import diagnostics as DG
from opportunity_engine import volume as VOL
from opportunity_engine.visual_audit import compare as VCMP
from opportunity_engine.visual_audit import store as VSTORE
from opportunity_engine.backtest import PERIODS, BacktestConfig, VARIANT_TEXT, run_backtest, split_is_oos, summarize


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=None, help="trading सुरू तारीख (warm-up आधीपासूनच)")
    parser.add_argument("--end", default=None)
    parser.add_argument("--variants", default="V1,V2,V3")
    parser.add_argument("--detectors", default="D1,D2,D3,D6,D7,D8,D10")
    parser.add_argument("--out", default="oe_backtest_out")
    parser.add_argument("--diagnostics", action="store_true", help="निदान तक्ते पण (फक्त अहवाल; नियम/parameters बदलत नाही)")
    parser.add_argument("--index-5m", default=None, help="offline 1M ऐवजी हा index 5M parquet (collector चा) वापरा; Daily इतिहास offline/extension मधून")
    parser.add_argument("--futures-volume", default=None, help="futures 5M parquet — volume जोडून आणि volume शिवाय असे दोन्ही backtest")
    parser.add_argument("--visual-cache", default=None, help="visual audit JSONL (backfill) — consensus modes off/score/gate तुलना")
    parser.add_argument("--consensus-modes", default="off,score,gate")
    args = parser.parse_args(argv)

    t0 = time.time()
    if args.index_5m:
        idx = pd.read_parquet(args.index_5m)
        frames = VOL.frames_from_index_5m(idx, daily=real_nifty_data.load_nifty_daily_combined())
    else:
        df = real_nifty_data.load_nifty_1min()
        if df.empty:
            print("❌ offline NIFTY डेटा सापडला नाही (data/nifty50_1min.parquet).")
            return 1
        frames = sessions.build_frames(df)
    bcfg = BacktestConfig(start=args.start, end=args.end, variants=tuple(v.strip() for v in args.variants.split(",")), detectors=tuple(d.strip() for d in args.detectors.split(",")))
    progress = lambda i, n, d: print(f"  {i}/{n} {d}", flush=True) if i % 500 == 0 else None          # noqa: E731
    novol = None
    if args.futures_volume:
        frames, cov = VOL.attach_futures_volume(frames, pd.read_parquet(args.futures_volume))
        print(f"Futures volume जोडला: {cov['with_volume']}/{cov['bars']} 5M bars ({cov['pct']}%), {cov['from']} → {cov['to']}", flush=True)
        if cov["with_volume"] == 0:
            print("⚠️ index डेटा आणि futures volume यांचा काळ एकमेकांवर येत नाही — volume-सकट निकाल volume-शिवायच्या निकालासारखेच असतील.")
    print(f"डेटा तयार ({time.time() - t0:.0f}s); timeline आणि replay चालू…", flush=True)
    res = run_backtest(frames, bcfg, progress=progress)
    os.makedirs(args.out, exist_ok=True)
    if args.futures_volume:
        print("\nvolume शिवाय (तुलनेसाठी) replay चालू…", flush=True)
        novol = run_backtest(VOL.without_volume(frames), bcfg, progress=progress)
        rows = []
        for v in res.results:
            for mode, rr in (("volume सकट", res), ("volume शिवाय", novol)):
                for label, part in zip(PERIODS, split_is_oos(rr.results[v]["trades"])):
                    rows.append({"variant": v, "mode": mode, "period": label, **summarize(part, "r")})
        vc = pd.DataFrame(rows)
        vc.to_csv(os.path.join(args.out, "volume_comparison.csv"), index=False)
        print("\n=== Volume सकट वि. शिवाय (R साइज-विना) ===")
        print(vc.to_string(index=False))
    res.comparison.to_csv(os.path.join(args.out, "variants_comparison.csv"), index=False)
    for name, table in res.variant_tables().items():
        table.to_csv(os.path.join(args.out, f"{name}.csv"), index=False)
    for v, r in res.results.items():
        for name in ("trades", "virtual", "decisions"):
            r[name].to_csv(os.path.join(args.out, f"{v}_{name}.csv"), index=False)
        for name, table in res.tables(v).items():
            table.to_csv(os.path.join(args.out, f"{v}_{name}.csv"), index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    print("\n=== Variants तुलना ===")
    print(res.comparison.to_string(index=False))
    vt = res.variant_tables()
    print("\n=== §3.4: variants IS / OOS वेगळे (R) ===")
    print(vt["variants_is_oos"].to_string(index=False))
    print("\n=== वर्षनिहाय expectancy R (trades) ===")
    print(vt["variants_yearwise"].to_string(index=False))
    for v in res.results:
        t = res.tables(v)
        print(f"\n=== {v}: {VARIANT_TEXT.get(v, '')} ===")
        print(t["summary"].to_string(index=False))
        print(t["verdicts"].to_string(index=False))
        print(t["aligned_vs_counter"].to_string(index=False))
        if len(t["wait_pullback"]):
            print("--- WAIT_PULLBACK_END bias मध्ये ---")
            print(t["wait_pullback"].to_string(index=False))
    if args.diagnostics:
        for v in res.results:
            print(f"\n=== {v}: निदान (shadow detection चालू…) ===", flush=True)
            diag = DG.run_diagnostics(res.timeline, res.results[v], v, bcfg, progress=lambda i, n, d: print(f"  {i}/{n} {d}", flush=True) if i % 500 == 0 else None)
            for name, table in diag.items():
                table.to_csv(os.path.join(args.out, f"{v}_diag_{name}.csv"), index=False)
            for name in ("check_resim", "A_exit_breakdown", "A_win_composition", "B_counterfactual", "C_loss_size", "D_funnel"):
                if name in diag and len(diag[name]):
                    print(f"\n--- {name} ---")
                    print(diag[name].to_string(index=False))
    if args.visual_cache:
        recs = VSTORE.records_by_date(VSTORE.read_jsonl(args.visual_cache))
        if not recs:
            print(f"⚠️ {args.visual_cache} मध्ये visual records नाहीत — consensus तुलना वगळली.")
        else:
            modes = tuple(m.strip() for m in args.consensus_modes.split(",") if m.strip())
            for v in res.results:
                table, _ = VCMP.modes_table(res.timeline, bcfg, recs, modes, v)
                table.to_csv(os.path.join(args.out, f"{v}_consensus_modes.csv"), index=False)
                print(f"\n=== {v}: Dual-Eye consensus modes ({min(recs):%Y-%m-%d} → {max(recs):%Y-%m-%d}; R साइज-विना) ===")
                print(table.to_string(index=False))
            rt, rx = VCMP.reaction_by_class(res.timeline, frames, recs)
            rt.to_csv(os.path.join(args.out, "consensus_level_reaction.csv"), index=False)
            rx.to_csv(os.path.join(args.out, "consensus_level_reaction_rows.csv"), index=False)
            print("\n=== Level reaction (पुढच्या 10 sessions, 1H) — consensus वर्गानुसार ===")
            print(rt.to_string(index=False))
    print(f"\nनिकाल CSV: {os.path.abspath(args.out)}  (एकूण {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
