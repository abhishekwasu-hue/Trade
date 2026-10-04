"""
run_visual_backfill.py
------------------------
🎓 Opportunity Engine PR-V (spec §17.9): 2022-01 → 2024-03 (OOS) मधल्या प्रत्येक trading दिवसासाठी NIFTY चे Daily आणि 1H charts (फक्त D−1 पर्यंतचे) vision model
कडून एकदाच वाचून JSONL cache मध्ये साठवणे — मग `run_opportunity_backtest.py --visual-cache …` ने तिन्ही consensus modes चा तुलना तक्ता.
**आधी खर्च दाखवतो; `--run --yes` दिल्याशिवाय एकही paid call नाही.** Resumable (पूर्ण झालेले charts वगळले जातात), rate-limit-safe (SDK retries + batch).
BANKNIFTY चा offline intraday डेटा नाही, म्हणून backfill फक्त NIFTY.

    python3 run_visual_backfill.py                                         # फक्त अंदाज: charts, calls, tokens
    python3 run_visual_backfill.py --price-in 4 --price-out 20            # + $ अंदाज (model चे $/1M tokens दर)
    python3 run_visual_backfill.py --sample-exact                         # + एका नमुन्याचे अचूक input tokens (count_tokens; generation खर्च नाही)
    python3 run_visual_backfill.py --run --yes --mode batch               # Batches API (50% स्वस्त) — submit; पुन्हा चालवल्यावर निकाल गोळा
    python3 run_visual_backfill.py --run --yes --mode batch --wait        # submit + संपेपर्यंत थांबून गोळा
    python3 run_visual_backfill.py --run --yes --mode sync --max-charts 20 # छोटा नमुना (sync)
"""
import argparse
import os
import sys
import time

import real_nifty_data
from opportunity_engine import backtest as BT
from opportunity_engine import sessions
from opportunity_engine.visual_audit import auditor as A
from opportunity_engine.visual_audit import backfill as BF
from opportunity_engine.visual_audit import jobs as J

CACHE = os.path.join("data", "oe_visual_backfill_NIFTY.jsonl")


def main(argv=None, client_factory=A.make_client, frames=None):
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2024-03-27")
    p.add_argument("--tfs", default=",".join(BF.BACKFILL_TFS))
    p.add_argument("--cache", default=CACHE)
    p.add_argument("--price-in", type=float, default=None, help="$ प्रति 1M input tokens")
    p.add_argument("--price-out", type=float, default=None, help="$ प्रति 1M output tokens")
    p.add_argument("--out-tokens", type=int, default=1500, help="प्रति call अंदाजे output tokens (thinking + JSON)")
    p.add_argument("--sample-exact", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--yes", action="store_true", help="खर्च मंजूर — paid calls सुरू")
    p.add_argument("--mode", choices=("batch", "sync"), default="batch")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--max-charts", type=int, default=None)
    args = p.parse_args(argv)

    t0 = time.time()
    if frames is None:
        df = real_nifty_data.load_nifty_1min()
        if df.empty:
            print("❌ offline NIFTY डेटा सापडला नाही.")
            return 1
        frames = sessions.build_frames(df)
    tl = BT.prepare_timeline(frames, BT.BacktestConfig(start=args.start, end=args.end, variants=("V1",)),
                             progress=lambda i, n, d: print(f"  timeline {i}/{n} {d}", flush=True) if i % 500 == 0 else None)
    tfs = tuple(t.strip() for t in args.tfs.split(",") if t.strip())
    done = BF.done_keys(args.cache)
    items = BF.plan_items(tl, args.start, args.end, tfs, done)
    if args.max_charts:
        items = items[:args.max_charts]
    est = J.estimate(len(items), args.price_in, args.price_out, args.out_tokens, batch=args.mode == "batch")
    print(f"\nTimeline तयार ({time.time() - t0:.0f}s). कालावधी {args.start} → {args.end}, TFs {tfs}.")
    print(f"आधीच पूर्ण: {len(done)} charts · बाकी: {est['charts']} charts = {est['calls']} calls (overlay + स्वतंत्र)")
    print(f"अंदाजे tokens: input ≈ {est['input_tokens']:,}, output ≈ {est['output_tokens']:,} (प्रति call output {args.out_tokens} गृहीत)")
    if est["cost_usd"] is not None:
        print(f"अंदाजे खर्च: ${est['cost_usd']:,} ({'batch — 50% सवलत लावून' if est['batch'] else 'sync'})")
    else:
        print("$ अंदाजासाठी --price-in/--price-out (model चे $/1M tokens दर) द्या.")
    vcfg = A.VisualAuditConfig.from_env()
    client = None
    if args.sample_exact or args.run:
        if not vcfg.model:
            print("❌ VISUAL_AUDIT_MODEL env सेट नाही.")
            return 1
        client = client_factory()
    if args.sample_exact and items:
        day, tf = items[0]
        ch = BF.chart(tl, frames, day, tf, "NIFTY")
        if ch and ch["png_overlay"] is not None:
            exact = J.exact_input_tokens(client, A.build_request(vcfg, "overlay", ch["png_overlay"], "NIFTY", tf, ch["labels"], BF.states_for(tl, day, tf)))
            print(f"नमुना ({day.date:%Y-%m-%d} {tf}) overlay call चे अचूक input tokens: {exact} (अंदाज: {J.per_call_input_estimate(len(ch['labels']))})")
    if not args.run:
        print("\nहा फक्त अंदाज आहे — एकही paid call झाला नाही. मंजुरीनंतर: --run --yes")
        return 0
    if not args.yes:
        print("❌ --yes दिलेलं नाही — खर्च मंजूर केल्याशिवाय calls नाहीत.")
        return 1
    state = args.cache + ".batches.json"
    if args.mode == "sync":
        n = BF.run_sync(client, vcfg, tl, frames, items, args.cache)
        print(f"✅ {n} charts audit करून {args.cache} मध्ये साठवले.")
        return 0
    written, pending = BF.collect(client, tl, frames, args.cache, state, wait=False)
    if written or pending:
        print(f"आधीच्या batches मधून {written} charts गोळा; अजून चालू batches: {pending}")
    if pending == 0 and items:
        items = BF.plan_items(tl, args.start, args.end, tfs, BF.done_keys(args.cache))[:args.max_charts or None]
        reqs = BF.build_requests(vcfg, tl, frames, items)
        print(f"{len(reqs)} requests batches मध्ये सबमिट करत आहे…")
        BF.submit(client, reqs, state)
    if args.wait:
        written, pending = BF.collect(client, tl, frames, args.cache, state, wait=True)
        print(f"✅ {written} charts गोळा; बाकी batches {pending}")
    else:
        print("Batches साधारण 1 तासात संपतात — मग हीच command (--run --yes --mode batch) पुन्हा चालवा, निकाल गोळा होतील.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
