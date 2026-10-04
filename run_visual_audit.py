"""
run_visual_audit.py
---------------------
🎓 Opportunity Engine PR-V (spec §17.5): EOD (किंवा pre-market 08:45) — Daily / 1H / 15M charts वर engine चे levels vision model कडून तपासणे,
त्याच charts चं levels-शिवाय स्वतंत्र वाचन, Dual-Eye consensus, Supabase (`level_audit`, `level_audit_suggestions`, `visual_levels`, `visual_audit_runs`) मध्ये
साठवणं, आणि Telegram वर छोटा सारांश. कुठलाही order नाही. Live intraday loop मध्ये API call नाही — इथले निकाल पुढच्या session भर वापरले जातात.

आवश्यक env: `VISUAL_AUDIT_ENABLED=1`, `VISUAL_AUDIT_MODEL=<vision-capable model id>`, `ANTHROPIC_API_KEY`. ऐच्छिक: `VISUAL_AUDIT_EFFORT`, `VISUAL_AUDIT_REPEAT=2`
(दोनदा audit करून सहमती %), `VISUAL_AUDIT_FEWSHOT=<n>` (data/visual_fewshot/ मधली उदाहरणं).

    python3 run_visual_audit.py                       # EOD (बाजार बंद झाल्यावर): audit_date = पुढचा trading दिवस
    python3 run_visual_audit.py --pre-market          # 08:45: audit_date = आज (आदल्या दिवसापर्यंतच्या डेटावर)
    python3 run_visual_audit.py --dry-run             # फक्त charts + खर्चाचा अंदाज (API call नाही)
खर्च: प्रति symbol × TF × 2 calls (overlay + स्वतंत्र) — डीफॉल्ट NIFTY + BANKNIFTY × Daily + 1H = 8 calls/दिवस (`--tfs 1d,1h,15m` ⇒ 12).
"""
import argparse
import datetime
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

import cloud_db
from config import get_ist_now
from notifications import notify_error, send_telegram_message
from opportunity_engine.config import EngineConfig
from opportunity_engine.refresh import compute_snapshot
from opportunity_engine.visual_audit import auditor as A
from opportunity_engine.visual_audit import consensus as CONS
from opportunity_engine.visual_audit import jobs as J
from opportunity_engine.visual_audit import store as VS
from upstox_api import fetch_candles

DEFAULT_SYMBOLS = ("NIFTY", "BANKNIFTY")
PNG_ROOT = os.path.join("data", "visual_audit")
CACHE = os.path.join("data", "oe_visual_audit.jsonl")
FEWSHOT_DIR = os.path.join("data", "visual_fewshot")


def audit_date_for(now, pre_market):
    """pre-market (09:15 आधी) ⇒ आज; EOD ⇒ पुढचा weekday (सुट्ट्या: त्या दिवशी bars नसतील, पुढच्या run ला नवीन date)."""
    d = pd.Timestamp(now).normalize()
    if pre_market or pd.Timestamp(now).time() < datetime.time(9, 15):
        return d.date()
    return pd.Timestamp(np.busday_offset(d.date(), 1, roll="forward")).date()


def load_fewshot(n, directory=FEWSHOT_DIR):
    if n <= 0 or not os.path.isdir(directory):
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json")))[-n:]:
        try:
            with open(path, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError):
            continue
    return out


def fetch(token, symbol, interval, lookback_days):
    return fetch_candles(token, symbol, current_spot=0, interval=interval, lookback_days=lookback_days)


def run_symbol(symbol, token, vcfg, client, now, audit_date, tfs, fetch_fn=fetch, store_mod=VS, dry_run=False, cache=CACHE, png_root=PNG_ROOT, log=print):
    """रिटर्न (ok, सारांश ओळी, usage dict)."""
    df5 = fetch_fn(token, symbol, "5minute", 120)
    daily = fetch_fn(token, symbol, "day", 900)
    if df5 is None or df5.empty:
        return False, [f"{symbol}: 5M डेटा मिळाला नाही"], {}
    snap = compute_snapshot(df5, daily, symbol, EngineConfig(), now=now)
    levels = snap.levels + [z for z in snap.rejected if z.get("status") == "BROKEN"]
    pool = [z for z in snap.rejected if z.get("status") != "BROKEN" and z.get("kind") in ("DEMAND", "SUPPLY", "SUPPORT", "RESISTANCE")]
    states = {tf: snap.context.state_name(tf) for tf in tfs}
    png_dir = os.path.join(png_root, str(audit_date))
    if dry_run:
        n = 0
        for tf in tfs:
            ch = J.prepare_chart(snap.frames, snap.journal, levels, tf, symbol, now)
            if ch is None:
                continue
            n += 1
            os.makedirs(png_dir, exist_ok=True)
            for kind in ("overlay", "plain"):
                if ch[f"png_{kind}"] is not None:
                    with open(os.path.join(png_dir, f"{symbol}_{tf}_{kind}.png"), "wb") as fh:
                        fh.write(ch[f"png_{kind}"])
            log(f"  {symbol} {tf}: {len(ch['labels'])} labels, image {'✅' if ch['png_overlay'] or ch['png_plain'] else '❌ (kaleido/Chrome?)'}")
        est = J.estimate(n)
        return True, [f"{symbol}: dry-run — {n} charts, {est['calls']} calls, ≈ {est['input_tokens']:,} input + {est['output_tokens']:,} output tokens"], est
    feedback, _ = store_mod.load_feedback(symbol)
    records = J.audit_day(client, vcfg, symbol, audit_date, snap.frames, snap.journal, levels, pool, states, now, tfs,
                          load_fewshot(vcfg.fewshot), png_dir, log)
    res = CONS.classify(levels, pool, records, feedback)
    by_id = {z["level_id"]: z for z in levels if z.get("level_id")}
    store_mod.ensure_tables()
    lines, usage = [], {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    ok = True
    for rec in records:
        VS.append_jsonl(cache, rec)
        saved = store_mod.save_record(rec, by_id, res["classes"], [v for v in res["visual_rows"] if v.get("tf") == rec["tf"]])
        ok = ok and bool(saved)
        for k in usage:
            usage[k] += int(rec["usage"].get(k, 0))
        lines.append(CONS.summary_text(symbol, rec, res["classes"]))
    failed = [r for r in records if (r["overlay"]["status"] not in ("OK", "SKIPPED")) or r["independent"]["status"] != "OK"]
    if failed:
        ok = False
    return ok, lines, usage


def main(argv=None, fetch_fn=fetch, store_mod=VS, client_factory=A.make_client):
    p = argparse.ArgumentParser()
    p.add_argument("--token", default=None)
    p.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    p.add_argument("--tfs", default="1d,1h", help="खर्च कमी ठेवण्यासाठी डीफॉल्ट Daily + 1H (15M हवा असेल तर 1d,1h,15m)")
    p.add_argument("--pre-market", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="फक्त charts + खर्चाचा अंदाज; API call नाही")
    p.add_argument("--no-telegram", action="store_true")
    args = p.parse_args(argv)
    if not args.dry_run and os.environ.get("VISUAL_AUDIT_ENABLED", "").strip() not in ("1", "true", "yes"):
        print("ℹ️ VISUAL_AUDIT_ENABLED=1 नाही — visual audit बंद आहे (खर्च टाळण्यासाठी डीफॉल्ट बंद). --dry-run ने charts/अंदाज पाहता येतो.")
        return 0
    vcfg = A.VisualAuditConfig.from_env()
    if not args.dry_run and not vcfg.model:
        print("❌ VISUAL_AUDIT_MODEL env सेट नाही.")
        return 1
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही.")
        return 1
    client = None if args.dry_run else client_factory()
    now = pd.Timestamp(get_ist_now())
    now = now.tz_localize(None) if now.tzinfo is None else now.tz_convert("Asia/Kolkata").tz_localize(None)
    audit_date = audit_date_for(now, args.pre_market)
    tfs = tuple(t.strip() for t in args.tfs.split(",") if t.strip())
    print(f"Visual audit — audit_date {audit_date} ({'pre-market' if args.pre_market else 'EOD'}), TFs {tfs}")
    all_ok, summary, total = True, [], {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    for sym in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        try:
            ok, lines, usage = run_symbol(sym, token, vcfg, client, now, audit_date, tfs, fetch_fn, store_mod, args.dry_run)
        except Exception as exc:                                        # एका symbol चं अपयश बाकीच्यांना थांबवू नये
            ok, lines, usage = False, [f"{sym}: अयशस्वी ({type(exc).__name__}: {exc})"], {}
        for line in lines:
            print(("✅ " if ok else "⚠️ ") + line)
        summary += lines
        for k in total:
            total[k] += int(usage.get(k, 0) or 0)
        all_ok = all_ok and ok
    print(f"एकूण: {total['calls']} calls, {total['input_tokens']:,} input + {total['output_tokens']:,} output tokens")
    if not args.dry_run:
        if not args.no_telegram:
            send_telegram_message("👁️ Visual audit (" + str(audit_date) + ")\n" + "\n".join(summary) +
                                  f"\nCalls {total['calls']}, tokens {total['input_tokens']:,}/{total['output_tokens']:,}")
        if not all_ok:
            notify_error("run_visual_audit", "काही charts चा audit अयशस्वी — log बघा")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
