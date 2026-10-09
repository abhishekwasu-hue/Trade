"""research/review_report.py — Abhi च्या review नंतरचे अहवाल (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §4, TRADE_GOLDEN_GALLERY_PROMPT §5).

  docs/reports/backtest_visual_review.md  ✔ / ✘ / ? % (trades आणि दिवस वेगळे), ✘ चे प्रकार (कारणातील keywords वरून गट), सुटलेले trades,
                                           प्रत्येक प्रकारासाठी code मधली जागा (file:function) आणि दुरुस्तीचा प्रस्ताव.
  docs/reports/golden_gallery.md          प्रत्येक G: सापडलेले, ⭐ / ✔ / ✘, "वेगळा G", hindsight (फक्त माहिती — n लहान).
Reviews Supabase मधून (backtest_review, golden_gallery); index JSON trade-data मधून. Images नाहीत (public repo).

    python3 research/review_report.py --review-dir /root/trade-data/backtest_review --gallery-dir /root/trade-data/golden_gallery
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backtest_review import gallery as GL      # noqa: E402
from backtest_review import store as BS        # noqa: E402

# ✘ प्रकार ⇒ (कारणातील keywords, code मधली जागा, प्रस्तावाची दिशा)
ERROR_TYPES = {
    "trend चुकला": (("trend", "protected", "htf"), "market_state/core.py:trend", "protected swing / real break / HL-LH पुष्टी तपासा"),
    "impulse चुकला": (("impulse", "bos", "displacement"), "market_state/core.py:impulse, leg_metrics", "F3 निकष (ER / overlap / BOS) तपासा"),
    "correction / ABC चुकला": (("abc", "correction", "wave", "zigzag", "flat", "triangle", "diagonal"),
                               "market_state/core.py:correction; chart_reader/structure.py:_abc_type", "labels / प्रकार नियम"),
    "area चुकला": (("area", "zone", "base", "flip", "level"), "chart_reader/areas.py:tools, active", "साधनं / active निवड"),
    "trendline सुटली": (("trendline", "tl", "रेषा"), "chart_reader/areas.py:sloping", "anchors शोध / touches"),
    "reversal चुकला": (("reversal", "candle", "hammer", "engulfing"), "chart_reader/reversal.py:evaluate", "composite / CL"),
    "R:R / SL चुकला": (("r:r", "rr", "sl", "target", "invalidation"), "chart_reader/risk.py:compute; areas.trade_targets", "SL / target व्याख्या"),
    "side चुकली": (("side", "bear", "bull"), "market_state/core.py:decide_side", "F4 सुसंगतता"),
}


def classify(reason):
    r = str(reason or "").lower()
    hits = [k for k, (kw, _, _) in ERROR_TYPES.items() if any(w in r for w in kw)]
    return hits or ["इतर"]


def _pct(n, d):
    return f"{100.0 * n / d:.0f}%" if d else "—"


def review_md(indexes, reviews):
    reviews = BS.measurable(reviews)                                          # test / vision_test नोंदी मोजमापात नाहीत
    days = [d for ix in indexes for d in ix.get("days", [])]
    trades = [t for d in days for t in d.get("trades", [])]
    L = ["# Backtest visual review — निकाल (C-V1)", "",
         "> Abhi चे ✔ / ✘ / ? (Supabase `backtest_review`). Contaminated / VAL काळ ⇒ फक्त logic पडताळणी, tuning नाही. Settings hash: "
         + ", ".join(sorted({ix.get("settings_hash", "—") for ix in indexes})), ""]
    for name, items in (("Trades", [t["item_id"] for t in trades]), ("दिवस", [d["item_id"] for d in days])):
        got = [reviews[i]["verdict"] for i in items if i in reviews]
        L.append(f"- **{name}:** तपासले {len(got)}/{len(items)} · ✔ {_pct(got.count('OK'), len(got))} · ✘ {_pct(got.count('WRONG'), len(got))}"
                 f" · ? {_pct(got.count('UNCLEAR'), len(got))}")
    ok_tr = [reviews[t["item_id"]]["verdict"] for t in trades if t["item_id"] in reviews]
    L += [f"- **लक्ष्य:** trades मध्ये बरोबर ≥ 85% — सध्या {_pct(ok_tr.count('OK'), len(ok_tr))} (निर्णय Abhi चा).", "", "## ✘ चे प्रकार", "",
          "| प्रकार | संख्या | code मधली जागा | प्रस्ताव |", "|---|---|---|---|"]
    wrong = [(i, r) for i, r in reviews.items() if r["verdict"] == "WRONG"]
    groups = {}
    for i, r in wrong:
        for g in classify(r.get("reason")):
            groups.setdefault(g, []).append(i)
    for g, ids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        _, where, fix = ERROR_TYPES.get(g, ((), "—", "Abhi चं कारण वाचून ठरवा"))
        L.append(f"| {g} | {len(ids)} | `{where}` | {fix} |")
    missed = [(i, r["missed_trade"]) for i, r in reviews.items() if r.get("missed_trade")]
    L += ["", "## सुटलेले trades", ""] + ([f"- {i[4:]} · {m['time']} {m['side']} — {reviews[i].get('reason') or ''}" for i, m in missed]
                                         or ["- अजून नाही"])
    L += ["", "## पुढे", "", "- प्रत्येक ✘ आणि सुटलेला trade ⇒ `tests/golden_chart_cases/` मध्ये नवीन case (Abhi च्या कारणावरून अपेक्षा); दुरुस्ती PR मध्ये pass."]
    return "\n".join(L) + "\n"


def gallery_md(index, reviews):
    ex = index.get("examples", [])
    L = ["# Golden Gallery G1–G6 — निकाल", "",
         "> IS 2015–2021 + Jul–Oct 2026 (VAL / holdout नाही). Ranking = code grade + confluence (hindsight नाही). Hindsight फक्त माहिती (n लहान).", "",
         "| G | setup | सापडलेले | दाखवलेले | ⭐ | ✔ | ✘ | वेगळा G | hindsight (target / SL / time) |", "|---|---|---|---|---|---|---|---|---|"]
    for g, name in GL.SETUPS.items():
        items = [e for e in ex if e["setup"] == g]
        v = [(reviews.get(e["id"]) or {}) for e in items]
        h = pd.Series([(e.get("hindsight") or {}).get("result") for e in items]).value_counts().to_dict() if items else {}
        L.append(f"| {g} | {name} | {(index.get('counts') or {}).get(g, 0)} | {len(items)} | {sum(x.get('verdict') == 'GOLDEN' for x in v)} | "
                 f"{sum(x.get('verdict') == 'OK' for x in v)} | {sum(x.get('verdict') == 'WRONG' for x in v)} | "
                 f"{', '.join(x['corrected_setup'] for x in v if x.get('corrected_setup')) or '—'} | "
                 f"{h.get('TARGET', 0)} / {h.get('SL', 0)} / {h.get('TIME', 0)} |")
    L += ["", "## Detector च्या चुका (✘)", ""]
    for e in ex:
        r = reviews.get(e["id"]) or {}
        if r.get("verdict") == "WRONG":
            L.append(f"- {e['setup']} {e['bar_start'][:16]}: {r.get('reason') or '—'}" + (f" ⇒ {r['corrected_setup']}" if r.get("corrected_setup") else "")
                     + " · `backtest_review/gallery.py:detect`")
    L += ["", "## ⭐ ⇒ golden cases", "", "- प्रत्येक ⭐ ⇒ `tests/golden_chart_cases/` (trend, impulse, correction प्रकार, setup, area, side)."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--review-dir", default="/root/trade-data/backtest_review")
    ap.add_argument("--gallery-dir", default="/root/trade-data/golden_gallery")
    a = ap.parse_args(argv)
    idx = []
    if os.path.isdir(a.review_dir):
        for run in sorted(os.listdir(a.review_dir)):
            p = os.path.join(a.review_dir, run, "run_index.json")
            if os.path.exists(p):
                idx.append(json.load(open(p, encoding="utf-8")))
    if idx:
        open(os.path.join(ROOT, "docs", "reports", "backtest_visual_review.md"), "w", encoding="utf-8").write(review_md(idx, BS.load_reviews()))
    gp = os.path.join(a.gallery_dir, "gallery_index.json")
    if os.path.exists(gp):
        open(os.path.join(ROOT, "docs", "reports", "golden_gallery.md"), "w", encoding="utf-8").write(
            gallery_md(json.load(open(gp, encoding="utf-8")), BS.load_gallery()))
    print("ok")


if __name__ == "__main__":
    main()
