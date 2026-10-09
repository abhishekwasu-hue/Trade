"""scripts/vision_blind_test.py — चार MAP CHECK केसेसवर vision ची blind चाचणी (Abhi 2026-10-09). **Trade नाही, order नाही, नियम बदल नाही.**

फक्त VPS वर (vision key, Telegram, trade-data). प्रत्येक केस: decision bar वर कापलेले स्वच्छ W / D / 1H / 15M charts + OHLC तक्ते ⇒ vision
(VISION_SIGNAL_MODEL, playbook + 12-मुद्दे checklist) ⇒ code: खुणांच्या खऱ्या किंमती, निर्णय नियम, R:R ⇒ marking केलेले charts ⇒
manifest (Telegram album, reply ⇒ backtest_review "vision_test"). एकूण खर्च ≤ --budget ($1); प्रत्येक call vision_usage मध्ये ("vision_test").
Charts / JSON फक्त --out-dir (private trade-data).

    python3 scripts/vision_blind_test.py --out-dir /root/trade-data/review/vision_test/map4 [--dry-run] [--send]
"""
import argparse
import json
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP         # noqa: E402
from vision_led import blind_test as BT       # noqa: E402

RECENT = "/root/trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz"
RUN_ID = "vision_test/map4"


def load(path, purpose):
    raw = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return DP.filter_allowed(raw, purpose)


def marks_for(r, tfs, areas_all=True):
    """chart साठी खुणा: labels / trendlines फक्त tfs च्या; areas सगळ्या (आडव्या पातळ्या) किंवा फक्त tfs च्या."""
    return {"labels": [x for x in r["labels"] if x["tf"] in tfs], "trendlines": [x for x in r["trendlines"] if x["a"]["tf"] in tfs],
            "areas": [x for x in r["areas"] if areas_all or x["tf"] in tfs]}


def run_case(n, decision, m1, out_dir, model, client, state, dry_run=False, log=print, history_note=None):
    tag = pd.Timestamp(decision).strftime("%Y-%m-%d_%H%M")
    cdir = os.path.join(out_dir, tag)
    os.makedirs(cdir, exist_ok=True)
    fr, asof = BT.frames(m1, decision)
    rec = {"n": n, "decision": str(decision), "asof": str(asof), "model": model, "status": None,
           "bars": {tf: [str(fr[tf]["timestamp"].iloc[0]), str(fr[tf]["timestamp"].iloc[-1]), len(fr[tf])] for tf in BT.TFS if len(fr[tf])}}
    clean = {}
    for tf in BT.TFS:
        clean[tf] = BT.png(BT.figure(fr[tf], tf, f"NIFTY · {tf} · cut at {asof:%Y-%m-%d %H:%M} (closed bars only)"))
        open(os.path.join(cdir, f"input_{tf}.png"), "wb").write(clean[tf])
    text = BT.user_text(decision, fr, history_note)
    open(os.path.join(cdir, "request_text.txt"), "w", encoding="utf-8").write(text)
    if dry_run:
        rec["status"] = "DRY_RUN"
        rec["estimate_usd"] = round(BT.estimate_usd(model or "opus", text_chars=len(text)), 4)
        return rec
    est = BT.estimate_usd(model, text_chars=len(text))
    if state["spent"] + est > state["budget"]:
        rec.update(status="NOT_RUN_BUDGET", note=f"खर्च ${state['spent']:.3f} + अंदाज ${est:.3f} > ${state['budget']}")
        return rec
    params = BT.build_request([clean[tf] for tf in BT.TFS], text, model, effort=os.environ.get("VISION_SIGNAL_EFFORT") or None,
                              thinking=os.environ.get("VISION_SIGNAL_THINKING") or None)
    t0 = time.monotonic()
    try:
        msg = client.messages.create(**params)
    except Exception as exc:                                                # noqa: BLE001 — एक call; नोंद आणि पुढे
        if "temperature" in str(exc).lower() and "temperature" in params:
            params.pop("temperature")
            msg = client.messages.create(**params)
        else:
            rec.update(status="API_ERROR", error=f"{type(exc).__name__}: {str(exc)[:200]}")
            return rec
    data, err, usage = BT.parse(msg)
    from vision import store as VS
    from vision.signal_audit import cost_usd
    c = cost_usd(model, usage)
    state["spent"] += c
    VS.add_usage("vision_test", model, usage, c)
    rec.update(latency_ms=int((time.monotonic() - t0) * 1000), usage=usage, cost_usd=round(c, 5))
    if err:
        rec.update(status="PARSE_ERROR", error=err)
        return rec
    r = BT.resolve(data, fr)
    rec.update(status="OK", vision=data, code=r)
    intra = marks_for(r, ("1H", "15M"))
    htf = marks_for(r, ("W", "D"), areas_all=False)
    title = f"NIFTY · {{tf}} · {pd.Timestamp(decision):%d %b %Y} decision bar {pd.Timestamp(decision):%H:%M} · vision खुणा (किंमती OHLC वरून)"
    files = []
    for tf, mk in (("1H", intra), ("15M", intra), ("W", htf), ("D", htf)):
        p = BT.png(BT.figure(fr[tf], tf, title.format(tf=tf), mk))
        fn = f"marked_{tf}.png"
        open(os.path.join(cdir, fn), "wb").write(p)
        files.append(f"{tag}/{fn}")
    rec["files"] = files
    rec["caption"] = BT.caption(n, len(BT.CASES), decision, data, r)
    log(f"  {decision}: {r['side']} · trade {r['trade']} · {r['n_ok']}/12 ✔ · ${c:.4f}")
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--recent-data", default=RECENT)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--budget", type=float, default=1.0, help="या चाचणीची एकूण खर्च मर्यादा ($)")
    ap.add_argument("--dry-run", action="store_true", help="फक्त charts + request text (API call नाही)")
    ap.add_argument("--send", action="store_true", help="Telegram albums (VPS)")
    a = ap.parse_args(argv)
    model = os.environ.get("VISION_SIGNAL_MODEL") or None
    if not a.dry_run and not model:
        print("⛔ VISION_SIGNAL_MODEL env नाही")
        return 1
    client = None
    if not a.dry_run:
        from vision import config as VC
        from vision import store as VS
        month = VS.spent()[1]
        cap = float(VC.load("_global")["vision_monthly_budget_usd"])
        if month + a.budget > cap:
            print(f"⛔ महिन्याचा vision खर्च ${month:.2f} + या चाचणीची मर्यादा ${a.budget} > ${cap} — थांबलो (Abhi ला विचारा)")
            return 1
        from vision.signal_audit import make_client
        client = make_client(timeout_sec=120)
    os.makedirs(a.out_dir, exist_ok=True)
    is_raw, recent = load(a.is_data, "research"), None
    state = {"spent": 0.0, "budget": float(a.budget)}
    recs = []
    for n, dec in enumerate(BT.CASES, 1):
        d = pd.Timestamp(dec)
        if d >= DP.CONTAMINATED_START:
            recent = recent if recent is not None else load(a.recent_data, "golden")
            m1 = recent[recent["timestamp"] < d + pd.Timedelta(days=1)]
            note = ("History note: data before 2026-07-01 is not provided (policy), so the Weekly / Daily history is short; "
                    "use what is shown.")
        else:
            m1 = is_raw[(is_raw["timestamp"] >= d - pd.Timedelta(days=640)) & (is_raw["timestamp"] < d + pd.Timedelta(days=1))]
            note = None
        recs.append(run_case(n, d, m1, a.out_dir, model, client, state, dry_run=a.dry_run, history_note=note))
        json.dump(recs[-1], open(os.path.join(a.out_dir, f"{d:%Y-%m-%d_%H%M}", "result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, default=str)
    summary = {"run_id": RUN_ID, "model": model, "budget_usd": a.budget, "spent_usd": round(state["spent"], 5),
               "cases": [{k: r.get(k) for k in ("n", "decision", "status", "cost_usd", "error", "note")} for r in recs]}
    json.dump(summary, open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    ok = [r for r in recs if r.get("status") == "OK"]
    if ok:
        items = [{"n": r["n"], "date": r["decision"][:10], "item": f"{RUN_ID}|case:{r['decision'][:16]}", "kind": "vision_test",
                  "reading": r["caption"], "caption": r["caption"], "files": r["files"]} for r in ok]
        json.dump({"run_id": RUN_ID, "title": "VISION TEST", "unit": "केस", "items": items},
                  open(os.path.join(a.out_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"खर्च: ${state['spent']:.4f} (मर्यादा ${a.budget}) · OK {len(ok)}/{len(recs)}")
    if a.send and ok:
        from backtest_review import telegram as RT
        out = RT.send_run(a.out_dir, run_key=RUN_ID)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
