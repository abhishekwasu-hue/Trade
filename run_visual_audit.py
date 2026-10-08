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
खर्च: प्रति symbol × TF × 2 calls (overlay + स्वतंत्र) — डीफॉल्ट फक्त NIFTY × Daily + 1H = 4 calls/दिवस.
Symbols: vision `_global` setting `visual_audit_symbols` (dashboard; default ["NIFTY"] — Abhi 2026-10-08: vision फक्त NIFTY, खर्च कमी), env
`VISUAL_AUDIT_SYMBOLS` किंवा `--symbols` ने बदलता येतो.
Budget (signals ला प्राधान्य, Abhi 2026-10-08): खर्च `vision_usage` (task = visual_audit) मध्ये; प्रत्येक chart आधी तपासणी —
audit आज + अंदाज ≤ min(`visual_audit_daily_cap` $0.10, दैनिक budget − `signals_daily_reserve_usd` $0.20), आणि एकूण दैनिक / मासिक ($5) मर्यादा.
ओलांडत असेल तर तो chart वगळला (अपयश नाही; Telegram वर कारण). Dashboard वर signals आणि visual audit वेगवेगळे + एकत्र.
Render: एकच kaleido Chrome server सगळ्या charts साठी (`KaleidoSession`, शेवटी cleanup); अपयश ⇒ server restart + एकदा पुन्हा.
अपयश: कोणता chart (symbol, TF, overlay / स्वतंत्र / Supabase) आणि कारण — log, Telegram सारांश आणि error संदेशात.
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
from opportunity_engine.visual_audit import render as R
from opportunity_engine.visual_audit import store as VS
from upstox_api import fetch_candles

DEFAULT_SYMBOLS = ("NIFTY",)
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


def symbols_setting(cli=None):
    """--symbols > env VISUAL_AUDIT_SYMBOLS > vision `_global` visual_audit_symbols > DEFAULT_SYMBOLS."""
    raw = cli or os.environ.get("VISUAL_AUDIT_SYMBOLS")
    if not raw:
        try:
            from vision import config as VC
            raw = VC.load("_global").get("visual_audit_symbols")
        except Exception:
            raw = None
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raw = DEFAULT_SYMBOLS                                           # setting नाही ⇒ default; [] (dashboard वर सगळे काढले) ⇒ बंद
    items = raw.split(",") if isinstance(raw, str) else raw
    return [str(s).strip().upper() for s in items if str(s).strip()]


def call_cost(model, usage):
    from vision import signal_audit as SA
    return SA.cost_usd(model, usage)


EST_OUT_TOKENS = 1500        # पहिल्या run चा अंदाज (खरी नोंद नसताना): प्रति call output tokens (actual सहसा ~700)


def chart_estimate(model, by_task_rows=None):
    """एका chart (overlay + स्वतंत्र) चा अंदाज $: मागच्या (≤ 20) खऱ्या visual_audit नोंदींची सरासरी, नसतील तर jobs.estimate (1,500 output/call).
    प्रत्येक chart नंतर खरा खर्च **लगेच** नोंदला जातो (review PR #274) ⇒ अंदाज कमी पडला तरी ओलांडणं जास्तीत जास्त एका chart चं."""
    rows = by_task_rows
    if rows is None:
        try:
            from vision import store as VUS
            with VUS.connect() as c:
                rows = [r[0] for r in c.execute("SELECT cost_usd FROM vision_usage WHERE task='visual_audit' ORDER BY ts DESC LIMIT 20")]
        except Exception:
            rows = []
    rows = [float(x) for x in rows if x]
    return sum(rows) / len(rows) if rows else call_cost(model, J.estimate(1, out_tokens=EST_OUT_TOKENS))


def remaining_weekdays(today):
    """आजनंतर महिन्यात उरलेले सोम–शुक्र (signals चा मासिक राखीव भाग)."""
    t = pd.Timestamp(today).normalize()
    end = t + pd.offsets.MonthEnd(0)
    return int(len(pd.bdate_range(t + pd.Timedelta(days=1), end))) if end > t else 0


def audit_allowed(est, g, by_task, today=None):
    """Signals ला प्राधान्य (Abhi 2026-10-08): visual audit ला परवानगी फक्त जर
      audit आज + est ≤ min(visual_audit_daily_cap, दैनिक budget − signals_daily_reserve_usd) · आजचा एकूण + est ≤ दैनिक ·
      महिना + est ≤ मासिक − signals_daily_reserve_usd × (महिन्यात उरलेले weekdays) (review PR #274: महिन्याच्या शेवटी signals उपाशी नकोत).
    by_task = vision store spent_by_task(). रिटर्न (ok, कारण)."""
    audit_day = (by_task.get("visual_audit") or (0.0, 0.0, 0))[0]
    day = sum(v[0] for v in by_task.values())
    month = sum(v[1] for v in by_task.values())
    allow = min(float(g["visual_audit_daily_cap"]), float(g["vision_daily_budget_usd"]) - float(g["signals_daily_reserve_usd"]))
    if audit_day + est > allow + 1e-12:
        return False, (f"visual audit उप-मर्यादा: आज ${audit_day:.3f} + अंदाज ${est:.3f} > ${allow:.2f} "
                       f"(cap ${g['visual_audit_daily_cap']}, signals राखीव ${g['signals_daily_reserve_usd']})")
    if day + est > float(g["vision_daily_budget_usd"]) + 1e-12:
        return False, f"vision दैनिक budget: आज ${day:.3f} + अंदाज ${est:.3f} > ${g['vision_daily_budget_usd']}"
    if today is None:
        today = pd.Timestamp(get_ist_now())
        today = today.tz_convert("Asia/Kolkata").tz_localize(None) if today.tzinfo is not None else today
    rest = remaining_weekdays(today)
    m_allow = float(g["vision_monthly_budget_usd"]) - float(g["signals_daily_reserve_usd"]) * rest
    if month + est > m_allow + 1e-12:
        return False, (f"vision मासिक budget: ${month:.2f} + अंदाज ${est:.3f} > ${m_allow:.2f} (${g['vision_monthly_budget_usd']} − signals राखीव "
                       f"${g['signals_daily_reserve_usd']} × {rest} उरलेले दिवस)")
    return True, ""


def make_allow(model, g=None, by_task_fn=None, today=None):
    """प्रत्येक chart आधी ताजी तपासणी — आधीच्या chart चा खर्च `audit_day(on_chart=…)` मधून लगेच नोंदलेला असतो.
    Vision DB / settings वाचता आलं नाही ⇒ **fail closed** (chart वगळा, कारणासह; raise नाही)."""
    try:
        from vision import config as VC
        from vision import store as VUS
        g = g or VC.load("_global")
        est = chart_estimate(model)
        fn = by_task_fn or VUS.spent_by_task
    except Exception as exc:
        why = f"vision budget वाचता आलं नाही ({type(exc).__name__}: {exc}) ⇒ audit नाही"
        return lambda tf: (False, why)

    def allow(tf):
        try:
            return audit_allowed(est, g, fn(), today)
        except Exception as exc:
            return False, f"vision budget वाचता आलं नाही ({type(exc).__name__}: {exc}) ⇒ chart वगळला"
    return allow


def record_usage(model, rec, add_fn=None):
    """एका chart चा खर्च vision_usage मध्ये (task = visual_audit) — vision budget मध्ये मोजला जातो. रिटर्न $."""
    from vision import store as VUS
    u = rec.get("usage") or {}
    cost = call_cost(model, u)
    if int(u.get("calls", 0) or 0) > 0:
        (add_fn or VUS.add_usage)("visual_audit", model, u, cost, signal_id=f"va:{rec.get('symbol')}:{rec.get('tf')}:{rec.get('run_id')}")
    return cost


def failures_of(rec, saved=True):
    """एका chart चे अपयश (ओळी): overlay / स्वतंत्र status आणि कारण, Supabase save."""
    out = []
    for kind, name, ok_set in (("overlay", "overlay", ("OK", "SKIPPED")), ("independent", "स्वतंत्र", ("OK",))):
        r = rec.get(kind) or {}
        if r.get("status") not in ok_set:
            out.append(f"{rec.get('symbol')} {rec.get('tf')} {name}: {r.get('status')} — {r.get('error') or 'कारण नाही'}")
    if not saved:
        out.append(f"{rec.get('symbol')} {rec.get('tf')}: Supabase मध्ये साठवणं अयशस्वी (log मध्ये traceback)")
    return out


def run_symbol(symbol, token, vcfg, client, now, audit_date, tfs, fetch_fn=fetch, store_mod=VS, dry_run=False, cache=CACHE, png_root=PNG_ROOT, log=print,
               on_record=None, allow=None):
    """रिटर्न (ok, सारांश ओळी, usage dict — `failures` [ओळी], `skipped` [(tf, कारण)] आणि `cost_usd` सह). on_record(rec) ⇒ $ (vision budget
    मध्ये नोंद); allow(tf) ⇒ (ok, कारण) प्रत्येक chart आधी (budget — वगळलेला chart अपयश नाही)."""
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
    skipped = []
    lines, usage = [], {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": 0.0, "failures": [], "skipped": skipped}

    def on_chart(rec):                                                  # खर्च **लगेच** (पुढच्या chart चा allow हा खर्च पाहतो)
        if on_record is None:
            return
        try:
            usage["cost_usd"] += float(on_record(rec) or 0.0)
        except Exception as exc:                                        # खर्च नोंद अयशस्वी ⇒ audit थांबत नाही, पण अपयश म्हणून सांगतो
            usage["failures"].append(f"{symbol} {rec['tf']}: खर्च नोंद (vision_usage) अयशस्वी — {type(exc).__name__}: {exc}")
    records = J.audit_day(client, vcfg, symbol, audit_date, snap.frames, snap.journal, levels, pool, states, now, tfs,
                          load_fewshot(vcfg.fewshot), png_dir, log, allow=allow, skipped=skipped, on_chart=on_chart)
    res = CONS.classify(levels, pool, records, feedback)
    by_id = {z["level_id"]: z for z in levels if z.get("level_id")}
    store_mod.ensure_tables()
    for rec in records:
        VS.append_jsonl(cache, rec)
        saved = store_mod.save_record(rec, by_id, res["classes"], [v for v in res["visual_rows"] if v.get("tf") == rec["tf"]])
        for k in ("input_tokens", "output_tokens", "calls"):
            usage[k] += int(rec["usage"].get(k, 0))
        usage["failures"] += failures_of(rec, bool(saved))
        lines.append(CONS.summary_text(symbol, rec, res["classes"]))
    have = {r["tf"] for r in records} | {tf for tf, _ in skipped}
    lines += [f"{symbol} {tf}: chart तयार झाला नाही (डेटा अपुरा — अपयश नाही)" for tf in tfs if tf not in have]
    lines += [f"{symbol} {tf}: वगळलं — {why}" for tf, why in skipped]
    for f in usage["failures"]:
        log(f"  ❌ {f}")
    return not usage["failures"], lines, usage


def main(argv=None, fetch_fn=fetch, store_mod=VS, client_factory=A.make_client):
    p = argparse.ArgumentParser()
    p.add_argument("--token", default=None)
    p.add_argument("--symbols", default=None, help="डीफॉल्ट: vision _global visual_audit_symbols (default NIFTY)")
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
    if not args.dry_run and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("ℹ️ ANTHROPIC_API_KEY अजून .env मध्ये नाही — आजचा visual audit वगळला (खर्च नाही, error नाही). Key जोडल्यावर आपोआप चालेल.")
        return 0
    client = None if args.dry_run else client_factory()
    now = pd.Timestamp(get_ist_now())
    now = now.tz_localize(None) if now.tzinfo is None else now.tz_convert("Asia/Kolkata").tz_localize(None)
    audit_date = audit_date_for(now, args.pre_market)
    tfs = tuple(t.strip() for t in args.tfs.split(",") if t.strip())
    print(f"Visual audit — audit_date {audit_date} ({'pre-market' if args.pre_market else 'EOD'}), TFs {tfs}")
    all_ok, summary, total, failures = True, [], {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": 0.0}, []
    symbols = symbols_setting(args.symbols)
    if not symbols:
        print("ℹ️ Visual audit symbols रिकामे (dashboard वर बंद) — आज audit नाही.")
        return 0
    print(f"Symbols: {', '.join(symbols)}")
    allow = None if args.dry_run else make_allow(vcfg.model)
    with R.KaleidoSession():                                            # एकच Chrome सगळ्या charts साठी, शेवटी cleanup
        for sym in symbols:
            try:
                ok, lines, usage = run_symbol(sym, token, vcfg, client, now, audit_date, tfs, fetch_fn, store_mod, args.dry_run,
                                              on_record=None if args.dry_run else (lambda rec: record_usage(vcfg.model, rec)), allow=allow)
            except Exception as exc:                                    # एका symbol चं अपयश बाकीच्यांना थांबवू नये
                ok, lines, usage = False, [f"{sym}: अयशस्वी ({type(exc).__name__}: {exc})"], {"failures": [f"{sym}: {type(exc).__name__}: {exc}"]}
            for line in lines:
                print(("✅ " if ok else "⚠️ ") + line)
            summary += lines
            failures += usage.get("failures") or []
            for k in ("input_tokens", "output_tokens", "calls"):
                total[k] += int(usage.get(k, 0) or 0)
            total["cost_usd"] += float(usage.get("cost_usd") or 0.0)
            all_ok = all_ok and ok
    print(f"एकूण: {total['calls']} calls, {total['input_tokens']:,} input + {total['output_tokens']:,} output tokens, ${total['cost_usd']:.4f}")
    if not args.dry_run:
        spent_line = ""
        try:
            from vision import config as VC
            from vision import store as VUS
            g, by = VC.load("_global"), VUS.spent_by_task()
            day, month = sum(v[0] for v in by.values()), sum(v[1] for v in by.values())
            va = (by.get("visual_audit") or (0.0, 0.0, 0))[0]
            spent_line = (f"\nVisual audit आज ${va:.3f} / cap ${g['visual_audit_daily_cap']} · signals राखीव ${g['signals_daily_reserve_usd']}"
                          f"\nVision एकूण: आज ${day:.3f} / ${g['vision_daily_budget_usd']}, महिना ${month:.2f} / ${g['vision_monthly_budget_usd']}")
        except Exception:
            pass
        if not args.no_telegram:
            send_telegram_message("👁️ Visual audit (" + str(audit_date) + ")\n" + "\n".join(summary) +
                                  f"\nCalls {total['calls']}, tokens {total['input_tokens']:,}/{total['output_tokens']:,}, ${total['cost_usd']:.3f}" + spent_line
                                  + ("\n❌ अयशस्वी:\n" + "\n".join(failures) if failures else ""))
        if not all_ok:
            notify_error("run_visual_audit", "अयशस्वी charts:\n" + "\n".join(failures[:8]))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
