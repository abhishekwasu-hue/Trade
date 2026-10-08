"""research/chart_reader_examples.py — G-E1a उदाहरणं (report-only): प्रत्येकासाठी evidence हिशोब, grade, R:R, story + chart.

  1. Golden story 7 Oct 2026 (C-end bear call) — trade-data `upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz` (contaminated, purpose="golden",
     फक्त illustration, tuning नाही). File नसेल तर "data नाही" नोंद.
  2. IS (2015–2021) मधून code ने शोधलेले: एक flat C-end आणि एक triangle E-end (pullback, impulse दिशेने).
Charts: data/research/chart_reader_examples/ (gitignored — public repo मध्ये candles / charts नाहीत).

    python3 research/chart_reader_examples.py [--trade-data /home/user/trade-data] [--max-eval 80]
"""
import argparse
import json
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chart_reader import chart as CH          # noqa: E402
from chart_reader import evaluate as EV       # noqa: E402
from chart_reader import settings as CS       # noqa: E402
from chart_reader import structure as ST      # noqa: E402
from elliott import data_policy as DP         # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "research", "chart_reader_examples")
REPORT = os.path.join(ROOT, "docs", "reports", "chart_reader_examples.md")


def _window(m1, asof, days=90):
    t = pd.Timestamp(asof)
    return m1[(m1["timestamp"] >= t - pd.Timedelta(days=days)) & (m1["timestamp"] < t)].reset_index(drop=True)


def scan_is(m1, s, types=("flat", "triangle"), step=1):
    """Stage 1 (स्वस्त): 15m structure प्रत्येक bar वर (शेवटचे 300 bars) ⇒ pullback-end उमेदवार."""
    trig = EV.frame(m1, "15m", m1["timestamp"].iloc[-1] + pd.Timedelta(minutes=1))
    found = {t: [] for t in types}
    for j in range(300, len(trig), step):
        w = trig.iloc[j - 300:j + 1].reset_index(drop=True)
        r = ST.read(w, s)
        if r["entry_point"] and r["pullback"] == "pullback" and r["correction_type"] in found:
            found[r["correction_type"]].append(trig["bar_end"].iloc[j])
    return found


def evaluate_at(m1, asof, s):
    w = _window(m1, asof)
    r = EV.evaluate(w, "srv2", asof, s=s)
    trig = EV.frame(w, "15m", asof)
    return r, trig


def _md(name, r, png_name):
    L = [f"### {name}", "", f"- वेळ (bar close): **{r['asof']}** · बाजू: **{'bull put' if r['side'] > 0 else 'bear call'}** · "
         f"grade **{r['grade']}** ({r.get('total')}) · entry: **{'हो' if r['entry'] else 'नाही'}**"
         + (f" — {'; '.join(r['why_no_entry'])}" if r["why_no_entry"] else ""),
         f"- correction: {r['structure']['correction_type']} · entry point: {r['structure']['entry_point']} · pullback: "
         f"{r['structure']['pullback']}",
         f"- R:R: {('1:%.1f' % r['rr']) if r.get('rr') else '—'} · invalidation: {r.get('invalidation')} · targets: "
         f"{', '.join(str(t['price']) + ' (' + t['id'] + ')' for t in (r.get('targets') or [])) or '—'}", "",
         "| पुरावा | गुण | ओळ |", "|---|---|---|"]
    for line in r["lines"]:                                              # KB भाग D क्रमाने (16) + व्हेटो
        k = line.split()[0]
        L.append(f"| {k} | {r['points'].get(k, '—')} | {line.split(':', 1)[-1].strip()} |")
    L += ["", "Story (code narrative):", ""] + [f"- {x}" for x in r["story"]] + ["", f"Chart: `{png_name}` (gitignored)", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA", "/home/user/trade-data"))
    ap.add_argument("--max-eval", type=int, default=80)
    a = ap.parse_args(argv)
    s = CS.load()
    os.makedirs(OUT_DIR, exist_ok=True)
    sections, summary = [], {}
    # 1. golden story
    gp = os.path.join(a.trade_data, "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz")
    if os.path.exists(gp):
        g = DP.filter_allowed(pd.read_csv(gp, parse_dates=["timestamp"]), "golden")
        best = None
        for t in pd.date_range("2026-10-07 09:45", "2026-10-07 15:15", freq="15min"):
            r, trig = evaluate_at(g, t, s)
            key = (r["entry"], r["side"] == -1, r.get("total") or 0)
            if best is None or key > best[0]:
                best = (key, r, trig)
        _, r, trig = best
        p = os.path.join(OUT_DIR, "golden_2026-10-07.png")
        img = CH.png(trig, r)
        if img:
            open(p, "wb").write(img)
        sections.append(_md("7 Oct 2026 — golden story (contaminated, illustration only)", r, os.path.basename(p)))
        summary["golden_7oct"] = {k: r[k] for k in ("asof", "side", "grade", "total", "entry", "rr")}
    else:
        sections.append("### 7 Oct 2026 — golden story\n\n**Data नाही:** `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz` "
                        "(VPS export block चालायचा आहे).\n")
    # 2. IS flat / triangle
    m1 = DP.load_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"), "research")
    m1 = m1[m1["timestamp"] < DP._IS_END_X].reset_index(drop=True)
    t0 = time.time()
    found = scan_is(m1, s)
    summary["scan"] = {k: len(v) for k, v in found.items()}
    summary["scan_sec"] = round(time.time() - t0, 1)
    for typ, ts_list in found.items():
        if not ts_list:
            sections.append(f"### IS {typ}\n\nIS मध्ये उमेदवार सापडला नाही.\n")
            continue
        stride = max(len(ts_list) // a.max_eval, 1)
        best = None
        for t in ts_list[::stride][: a.max_eval]:
            r, trig = evaluate_at(m1, t, s)
            if r["structure"]["correction_type"] != typ:
                continue
            key = (r["entry"], r.get("total") or 0)
            if best is None or key > best[0]:
                best = (key, r, trig)
        if best is None:
            sections.append(f"### IS {typ}\n\nपूर्ण evaluate मध्ये {typ} टिकला नाही.\n")
            continue
        _, r, trig = best
        p = os.path.join(OUT_DIR, f"is_{typ}.png")
        img = CH.png(trig, r)
        if img:
            open(p, "wb").write(img)
        sections.append(_md(f"IS {typ} {'C-end' if typ == 'flat' else 'E-end'}", r, os.path.basename(p)))
        summary[f"is_{typ}"] = {k: r[k] for k in ("asof", "side", "grade", "total", "entry", "rr")}
    head = ["# Chart Reader G-E1a — उदाहरणं (report-only)", "",
            "> Code pre-grade (vision शिवाय), KB भाग D चा तक्ता (16 पुरावे) + A3 व्हेटो. Weights / A ≥ 60 · B 45–59 · C < 45 — Abhi ने मंजूर, "
            "tuning नाही. IS मध्ये futures volume / VIX नाही ⇒ VL, VX = 0. Charts gitignored.", "",
            f"IS scan: {summary['scan']} उमेदवार ({summary['scan_sec']} s).", ""]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, "w").write("\n".join(head + sections))
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
