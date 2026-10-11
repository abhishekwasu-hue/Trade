"""🗺 MTF CHECK — W / D / 1H / 15M प्रत्येक TF च्या स्वतःच्या candles वर थर 1–7 + B1 / B2, नमुना-दिवसांचे 8 images + caption + manifest.

उदा. (BANKNIFTY, trade-data मधले TF csv):
  python3 scripts/mtf_check.py --instrument BANKNIFTY --tf-dir <trade-data>/banknifty --dates YYYY-MM-DD \
      --out-dir <trade-data>/review/mtf --run-id bn_run1
holdout instrument (NIFTY): --m1 <1m csv …> (1H / 15M थर; W / D फक्त राखाडी display — holdout sealed).
तारखा / windows फक्त CLI वरून. Shadow: order / निर्णय बदल नाही. पाठवणं: scripts/send_review_to_telegram.py --run review/mtf/<run-id>.
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from mtf import adapter as MA  # noqa: E402
from mtf import concepts as CC  # noqa: E402
from mtf import run as MR  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402


def holdout_frames(paths):
    """holdout instrument (NIFTY) 1m (holdout वगळून) ⇒ 15M / 1H (थरांसाठी) आणि D / W (फक्त display)."""
    from scripts import swing_check as SC
    m15 = PE.bars_15m(SC.load_1m(paths))
    f15 = m15[["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)
    f1h = PC.agg_1h(m15)[["timestamp", "open", "high", "low", "close"]]
    t = pd.to_datetime(f15["timestamp"])
    agg = dict(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    fd = f15.assign(timestamp=t.dt.normalize()).groupby("timestamp").agg(**agg).reset_index()
    fw = f15.assign(timestamp=(t.dt.normalize() - pd.to_timedelta(t.dt.weekday, unit="D"))).groupby("timestamp").agg(**agg).reset_index()
    return {"15M": f15, "1H": f1h}, {"D": fd, "W": fw}


def tf_frames(tf_dir, ins):
    out = {}
    for tf in MA.TFS:
        p = os.path.join(tf_dir, f"{ins}_{tf}.csv.gz")
        if os.path.exists(p):
            out[tf] = MA.load_tf(p)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default=None, choices=INS.names())
    ap.add_argument("--tf-dir", default=None, help="<INSTR>_<TF>.csv.gz असलेला folder (index_candles_fetch चा output)")
    ap.add_argument("--m1", nargs="*", default=None, help="holdout instrument (NIFTY): 1m csv (1H / 15M थर; W / D फक्त display)")
    ap.add_argument("--dates", nargs="+", required=True, help="नमुना दिवस YYYY-MM-DD (त्या दिवशी --asof-time पर्यंत बंद candles)")
    ap.add_argument("--asof-time", default="15:30")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--concepts-path", default=None, help="chart_concepts store (default data/chart_concepts.json)")
    ap.add_argument("--concepts-off", default=None, help="या run पुरत्या बंद संकल्पना: key1,key2")
    ap.add_argument("--mode", default=None, choices=CC.MODES)
    a = ap.parse_args(argv)
    ins = INS.set_current(a.instrument)
    cfg = CC.load(a.concepts_path, CC.cli_overrides(a.concepts_off, a.mode))
    display = None
    if INS.holdout(ins):
        if not a.m1:
            ap.error(f"{ins} साठी --m1 हवं (holdout ⇒ W / D थर नाहीत)")
        frames, display = holdout_frames(a.m1)
    else:
        tfd = a.tf_dir or os.path.join(os.environ.get("TRADE_DATA_DIR", os.path.join(ROOT, "..", "trade-data")), INS.get()["dir"])
        frames = tf_frames(tfd, ins)
        if not frames:
            ap.error(f"{tfd} मध्ये {ins}_<TF>.csv.gz नाहीत")
    Cs = {}
    for tf in MA.TFS:
        if tf in frames and len(frames[tf]):
            print(f"{ins} {tf}: {len(frames[tf])} candles · थर बांधतो…", flush=True)
            Cs[tf] = MA.build(frames[tf], tf, ins)
        else:
            Cs[tf] = None
    run_dir = os.path.join(a.out_dir, a.run_id)
    items = []
    for n, d in enumerate(a.dates, 1):
        asof = pd.Timestamp(f"{d} {a.asof_time}")
        r = MR.run_day(Cs, asof, cfg, os.path.join(run_dir, d), display=display)
        if not r["files"]:
            print(f"{d}: त्या वेळेपर्यंत बंद candle नाही ⇒ वगळला", flush=True)
            continue
        items.append({"n": n, "date": d, "item": f"mtf/{a.run_id}|day:{d}", "reading": r["caption"].splitlines()[0],
                      "caption": r["caption"], "files": [f"{d}/{f}" for f in r["files"]], "kind": "mtf"})
        s = r["summary"]["tf"]
        print(f"{d}: images {len(r['files'])} · " + " · ".join(f"{tf} ✅{sum(m['type'] == '✅' for m in x['marks'])} "
                                                               f"🟡{sum(m['type'] == '🟡' for m in x['marks'])}" for tf, x in s.items()), flush=True)
    man = {"run_id": a.run_id, "title": f"MTF CHECK {INS.label()}", "unit": "दिवस", "instrument": INS.label(), "concepts": cfg,
           "items": items}
    if not items:
        ap.error("एकाही दिवसाचे images नाहीत — manifest लिहिला नाही")
    for k, it in enumerate(items, 1):
        it["n"] = k
    json.dump(man, open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"manifest: {os.path.join(run_dir, 'manifest.json')}")
    return man


if __name__ == "__main__":
    main()
