"""
research/elliott_golden_report.py — golden-file regression (NIFTY, 25 Sep – 6 Oct 2026) → docs/reports/elliott_golden.md
-----------------------------------------------------------------------------------------------------------------
🎓 `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-06.csv.gz` (contaminated काळ — फक्त purpose="golden"; 1 Jul → 24 Sep warm-up).
E4 default settings आणि C3 चे सगळे candle variants — प्रत्येकावर T1–T9 + rejections (docs/reports/elliott_golden_expectations.json).
T5 (`check: sized`): Tier C चा नकार sizing स्तरावर ⇒ sized(sig) = default sizing (tier_of_A) वर lots > 0; प्रति-lot तोटा
= width × lot (credit 0 धरून — सर्वात मोठा तोटा ⇒ lots सर्वात कमी; Tier C ला A = 1 असताना 0).
फक्त test pass करण्यासाठी logic बदलायचं नाही — FAIL असेल तर कारण (bot ची चूक की screenshot वाचन) report.

    python3 research/elliott_golden_report.py [--workers 3]
"""
import argparse
import collections
import multiprocessing as mp
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research"))

from elliott import contracts as CT  # noqa: E402
from elliott import data_policy as DP  # noqa: E402
from elliott import golden as GD  # noqa: E402
from elliott import settings as S  # noqa: E402
from elliott import strikes as SK  # noqa: E402
from elliott.trigger import Scanner  # noqa: E402

OUT = os.path.join(ROOT, "docs", "reports", "elliott_golden.md")
TIER_IDX = {"A": 0, "B": 1, "C": 2}


def variants():
    import elliott_candle_merge_report as CM
    return {"E4_default": {}, **{k: v for k, v in CM.VARIANTS.items() if k != "a_generic"}}


def sized_fn(s):
    def sized(sig):
        lot = CT.lot_size(pd.Timestamp(sig.t).date() + pd.Timedelta(days=7))
        mult = s["tier_mult"][TIER_IDX.get(sig.tier, 2)]
        base = s["capital"] * s["risk_per_trade_pct"] / 100.0
        return SK.size_lots(sig.tier, mult, base, s["width_pts"] * lot, s, context="backtest") > 0
    return sized


def run(args):
    name, ov = args
    s, e = S.validate(dict(ov))
    assert not e, e
    d = DP.filter_allowed(GD.load_golden(GD.golden_csv()), "golden")
    sc = Scanner(d, s)
    sigs = []
    for t in sc.times():
        out = sc.step(t)
        if t.date() >= GD.GOLDEN_FROM:
            sigs += out
    rows = GD.evaluate(sigs, reasons=sc.reasons, sized=sized_fn(s))
    near = [(str(t), dg, code, why) for t, dg, code, why in sc.reasons
            if pd.Timestamp(t).date() == pd.Timestamp("2026-10-05").date()
            and pd.Timestamp("2026-10-05 09:45") <= pd.Timestamp(t) <= pd.Timestamp("2026-10-05 10:20")]
    diag = None
    if name == "E4_default":                                              # निदान: must वेळांना degree views + pivot confirm वेळा
        exp = GD.load_expectations()
        must_t = {}
        for e in exp["trades"]:
            if e["level"] == "must":
                w = GD._windows(e["date"], e.get("time"))
                must_t[e["id"]] = max(b for _, b in w)
        diag = {"views": {}, "pivots": []}
        sc2 = Scanner(d, s)
        want = sorted(set(must_t.values()))
        for t in sc2.times():
            if t > want[-1]:
                break
            snap = sc2.eng.snapshot(t)
            for k, tt in must_t.items():
                if tt is not None and t <= tt:
                    diag["views"][k] = (str(t), {dg: (v.gray, round(v.vote_up, 2) if v.vote_up == v.vote_up else None,
                                                      round(v.vote_down, 2) if v.vote_down == v.vote_down else None,
                                                      (v.preferred.pattern, v.preferred.current_wave, v.preferred.direction)
                                                      if v.preferred is not None else None)
                                                 for dg, v in sorted(snap.degrees.items())})
        for dg in sorted(sc.md):
            for p in sc.md[dg]["confirmed"]:
                if dg >= 1 and pd.Timestamp("2026-09-28") <= p.ts <= pd.Timestamp("2026-10-07"):
                    diag["pivots"].append((dg, p.kind, round(p.price), str(p.ts)[5:16], str(p.confirmed_at)[5:16]))
    lite = [{"t": str(x.t), "deg": x.degree, "setup": x.setup, "tier": x.tier, "dir": x.direction, "ttf": x.ttf,
             "extreme": round(x.extreme, 1), "hard_inv": round(x.hard_inv, 1), "score": round(x.score, 3),
             "label": x.candle_ctx.get("label"), "sized": sized_fn(s)(x)} for x in sigs]
    return name, rows, lite, near, diag


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    assert GD.golden_csv() is not None, "trade-data मध्ये golden 1m data नाही"
    vs = variants()
    with mp.get_context("fork").Pool(a.workers) as pool:
        out = pool.map(run, list(vs.items()))
    res = {n: (rows, lite, near) for n, rows, lite, near, _ in out}
    diag = next(dg for n, *_, dg in out if n == "E4_default")
    exp = GD.load_expectations()
    ids = [e["id"] for e in exp["trades"]] + [r["id"] for r in exp.get("rejections", [])]
    lvl = {e["id"]: e["level"] for e in exp["trades"] + exp.get("rejections", [])}
    L = ["# Golden-file regression — NIFTY 25 Sep – 6 Oct 2026", "",
         "> Data: `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-06.csv.gz` (contaminated काळ, फक्त golden; 1 Jul – 24 Sep warm-up). "
         "अपेक्षा: `docs/reports/elliott_golden_expectations.json` (Master §4). Signal + plan स्तर; premiums नाहीत. "
         "T5 sizing स्तरावर (default tier_of_A, प्रति-lot तोटा = width × lot).", "",
         "## 1. सारांश — प्रत्येक variant", ""]
    head = ["अपेक्षा", "level"] + list(res)
    L += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for i in ids:
        cells = []
        for n in res:
            st = next((r["status"] for r in res[n][0] if r["id"] == i), "—")
            cells.append({"PASS": "✅", "FAIL": "❌", "REPORT": "ℹ️"}.get(st, st))
        L.append(f"| {i} | {lvl[i]} | " + " | ".join(cells) + " |")
    fails = {n: [r["id"] for r in rows if r["status"] == "FAIL"] for n, (rows, _, _) in res.items()}
    L += ["", "✅ PASS · ❌ FAIL · ℹ️ REPORT (verify/report स्तर). FAIL संख्या: " +
          ", ".join(f"{n} {len(f)}" for n, f in fails.items()), "", "## 2. E4 default — तपशील", ""]
    rows, lite, near = res["E4_default"]
    L += ["| अपेक्षा | level | निकाल | तपशील |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} | {r['level']} | {r['status']} | {r['detail'].replace('|', '/')} |")
    L += ["", f"### Golden काळातले सगळे signals (E4 default, {len(lite)})", "",
          "| वेळ | D | setup | tier | दिशा | TTF | extreme | hard inv | score | label | sized |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in lite:
        L.append(f"| {x['t'][5:16]} | {x['deg']} | {x['setup']} | {x['tier']} | {x['dir']} | {x['ttf']} | {x['extreme']} | "
                 f"{x['hard_inv']} | {x['score']} | {x['label']} | {'हो' if x['sized'] else 'नाही'} |")
    L += ["", "### 5 Oct 09:45–10:20 (A-end, T6) — scanner ची कारणं (E4 default)", ""]
    cnt = collections.Counter((dg, code, why) for _, dg, code, why in near)
    L += [f"- D{dg} {code or '—'}: {why} × {n}" for (dg, code, why), n in sorted(cnt.items(), key=lambda x: (x[0][0], str(x[0][1])))] or \
         ["- कारणं नाहीत"]
    if diag:
        L += ["", "## 3. निदान — must वेळांना degrees काय पाहत होते (E4 default)", "",
              "प्रत्येक must च्या वेळ-खिडकीच्या शेवटी (किंवा आधीचा शेवटचा scan): degree → gray?, vote वर/खाली, preferred count "
              "(pattern, चालू wave, pattern दिशा). Setup ला त्या degree चा non-gray count, parent शी जुळणारी दिशा आणि पुढची motive "
              "trade दिशेने हवी.", "", "| must | scan | D0 | D1 | D2 | D3 |", "|---|---|---|---|---|---|"]
        for k, (t, v) in sorted(diag["views"].items()):
            cell = lambda x: ("gray" if x[0] else "ok") + f" ↑{x[1]} ↓{x[2]}" + (f" {x[3][0]}/{x[3][1]}/{x[3][2]:+d}" if x[3] else "")  # noqa: E731
            L.append(f"| {k} | {t[5:16]} | " + " | ".join(cell(v[dg]) if dg in v else "—" for dg in range(4)) + " |")
        L += ["", "**D1–D3 pivots व confirm वेळ** (pivot चा bar → confirmed_at):", "",
              "| D | प्रकार | किंमत | pivot | confirmed |", "|---|---|---|---|---|"]
        L += [f"| D{dg} | {k} | {px} | {ts} | {ca} |" for dg, k, px, ts, ca in diag["pivots"]]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main()
