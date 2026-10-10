"""research/map_a4b_gray.py — नकाशा A4 (Abhi Sep–Oct review मुद्दा 3): Elliott count किती वेळा gray, आणि **का**. फक्त अहवाल.

प्रत्येक नमुना वेळ t (1H bar close, फक्त t पर्यंतचा data): elliott.swings.multi_degree + elliott.counts.CountEngine.snapshot(t)
(market_state.elliott_vote हेच वापरतो). प्रत्येक degree साठी gray चं कारण एका गटात:
  1. data / pivots अपुरे      — त्या degree ला confirmed pivots / tentative नाही (history window मध्ये)
  2. नियमांनी सगळे counts बाद — pivots आहेत, पण patterns.build (R1–R10) / invalidation (R11) नंतर एकही valid count नाही
  3. मोठ्या degree शी जुळत नाही — valid counts आहेत, पण strict cross-degree मध्ये parent च्या चालू wave चा भाग नाहीत
  4. पुढची wave corrective    — beam मधले counts पुढची motive wave सांगत नाहीत (vote ≈ 0)
  5. vote विभागलेलं            — वर / खाली दोन्ही, कोणताही vote_min / 50% पेक्षा जास्त नाही
History window: production सारखा (`--window-days`, default 130 = K-10 / Simple Core) आणि तुलना म्हणून लांब window.

    python3 research/map_a4b_gray.py --is-data data/nifty50_1min.parquet --recent-data <csv.gz> --out docs/reports/situation_map
"""
import argparse
import collections
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP            # noqa: E402
from elliott import swings as W                  # noqa: E402

REASONS = ("data / pivots अपुरे", "नियमांनी सगळे counts बाद", "मोठ्या degree शी जुळत नाही", "पुढची wave corrective", "vote विभागलेलं")


def read(path):
    raw = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return DP.filter_allowed(raw, "golden")


def probe(m1, t, es):
    from elliott.counts import CountEngine
    md = W.multi_degree(m1, es, now=t)
    eng = CountEngine(md, es)
    rec = {}
    orig = eng.degree_nodes

    def spy(d, tt, *a, **k):
        nodes, t_idx, has = orig(d, tt, *a, **k)
        rec[d] = {"raw": len(nodes), "has_data": bool(has)}
        return nodes, t_idx, has
    eng.degree_nodes = spy
    snap = eng.snapshot(t)
    why = collections.defaultdict(collections.Counter)
    for (d, _pat, _o), w in getattr(eng, "_why", {}).items():
        why[d][str(w)[:70]] += 1
    out = {}
    for d, v in snap.degrees.items():
        r = rec.get(d, {"raw": 0, "has_data": False})
        vu, vd = v.vote_up, v.vote_down
        if not v.gray:
            reason = None
        elif not r["has_data"]:
            reason = REASONS[0]
        elif r["raw"] == 0:
            reason = REASONS[1]
        elif not v.nodes:
            reason = REASONS[2]
        elif not np.isfinite(vu) or (vu + vd) < 0.5:
            reason = REASONS[3]
        else:
            reason = REASONS[4]
        cp = md[d]["confirmed"][-11:]
        fr = md[d]["frame"]
        legs_h = []
        for a, b in zip(cp, cp[1:]):
            ta, tb = pd.Timestamp(a.ts), pd.Timestamp(b.ts)
            legs_h.append(float(((pd.to_datetime(fr["timestamp"]) > ta) & (pd.to_datetime(fr["timestamp"]) <= tb)).sum())
                          * W.TF_MIN.get(md[d]["tf"], 5) / 60.0)
        out[d] = {"tf": md[d]["tf"], "n_pivots": len(md[d]["confirmed"]), "leg_h": round(float(np.median(legs_h)), 1) if legs_h else None, "raw": r["raw"], "beam": len(v.nodes),
                  "up": None if not np.isfinite(vu) else round(float(vu), 3), "down": None if not np.isfinite(vd) else round(float(vd), 3),
                  "gray": bool(v.gray), "reason": reason, "parent_missing": bool(v.parent_missing),
                  "why_top": why[d].most_common(2)}
    return out


def scan(raw, start, end, every, part, window_days, hours=(10, 11, 12, 13, 14, 15), log=print, variant="auto", es_over=None):
    from elliott import settings as ES
    es = {**ES.DEFAULTS, **(es_over or {})}
    days = [pd.Timestamp(d) for d in sorted(pd.to_datetime(raw["timestamp"]).dt.normalize().unique())
            if pd.Timestamp(start) <= pd.Timestamp(d) <= pd.Timestamp(end)][::every]
    rows = []
    for n, d in enumerate(days):
        m1d = raw[(raw["timestamp"] >= d - pd.Timedelta(days=window_days)) & (raw["timestamp"] < d + pd.Timedelta(days=1))]
        for h in hours:
            t = d + pd.Timedelta(hours=h, minutes=15 if h < 15 else 30)                 # 1H bar close (NSE 09:15 पासून)
            m1 = m1d[m1d["timestamp"] < t]
            try:
                res = probe(m1, t, es)
            except Exception as exc:                                                  # गुपचूप नाही: error नोंद
                rows.append({"t": str(t), "part": part, "window": window_days, "variant": variant, "error": f"{type(exc).__name__}: {str(exc)[:100]}"})
                continue
            for dg, v in res.items():
                rows.append({"t": str(t), "part": part, "window": window_days, "variant": variant, "degree": dg, **v})
        if log and n % 20 == 0:
            log(f"  {part} w{window_days} {d:%Y-%m-%d}: {n + 1}/{len(days)}")
    return rows


def report(rows):
    df = pd.DataFrame([r for r in rows if "degree" in r])
    err = sum(1 for r in rows if "error" in r)
    L = ["# नकाशा A4b: Elliott count किती वेळा gray, आणि का (Abhi Sep–Oct review मुद्दा 3)", "",
         "**फक्त अहवाल.** नमुना = 1H bar close (10:15 … 15:30), फक्त त्या वेळेपर्यंतचा data. Count engine = market_state.elliott_vote "
         "वापरतो तोच (elliott.counts, default settings). **सध्याच्या `degree_tf_mode = auto_by_bars` मध्ये D0–D3 सगळे 5m pivots वर** "
         "(degree = swing चा आकार; 'leg median' = त्या degree च्या शेवटच्या 10 legs चा median कालावधी, तासांत) ⇒ वेगळा 1H / Daily count नाही. "
         "तुलनेसाठी fixed (D0 5m · D1 15m · D2 1h · D3 1d) — फक्त research, settings बदल नाही.",
         f"Engine error: {err}.", ""]
    if not len(df):
        return "\n".join(L) + "\n"
    for (part, var, w), g in df.groupby(["part", "variant", "window"], sort=False):
        L += [f"## {part} · {var} · history window {w} दिवस", "",
              "| degree | TF | leg median (तास) | नमुने | gray % | " + " | ".join(REASONS) + " | parent नाही % |",
              "|---|---|---|---|---|" + "---|" * len(REASONS) + "---|"]
        for dg, h in g.groupby("degree"):
            gr = h[h["gray"]]
            rc = gr["reason"].value_counts()
            tf = h["tf"].value_counts()
            tf_s = ", ".join(f"{k} {v * 100 / len(h):.0f}%" for k, v in tf.head(2).items())
            L.append(f"| D{dg} | {tf_s} | {h['leg_h'].median() if h['leg_h'].notna().any() else '—'} | {len(h)} | **{len(gr) * 100 / len(h):.0f}%** | "
                     + " | ".join(f"{rc.get(r, 0) * 100 / max(len(gr), 1):.0f}%" for r in REASONS)
                     + f" | {h['parent_missing'].mean() * 100:.0f}% |")
        L += ["", "Gray कारणांचे % = gray नमुन्यांपैकी. 'नियमांनी बाद' मध्ये सर्वाधिक वारंवार नियम (patterns.build चं पहिलं कारण):", ""]
        for dg, h in g.groupby("degree"):
            c = collections.Counter()
            for wl in h.loc[h["reason"] == REASONS[1], "why_top"]:
                for w, k in wl or []:
                    c[w] += k
            if c:
                L.append(f"- D{dg}: " + " · ".join(f"{w} ({k})" for w, k in c.most_common(3)))
        L.append("")
    L += ["**नकाशा P1 / P2 साठी वाचन:** पालक दिशा counts वरून घ्यायची असेल तर gray चं प्रमाण आणि त्याचं कारण आधी सुटायला हवं "
          "(उदा. history window अपुरी ⇒ pivots नाहीत; strict cross-degree ⇒ मोठ्या degree शी जुळत नाही). Threshold / नियम बदल इथे नाही — G-MAP1."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--recent-data", default=None)
    ap.add_argument("--every", type=int, default=15)
    ap.add_argument("--windows", default="130,400")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    a = ap.parse_args(argv)
    wins = [int(x) for x in a.windows.split(",")]
    FIXED = ("fixed 5m/15m/1h/1d (तुलना; settings बदल नाही)", {"degree_tf_mode": "fixed"})
    rows = []
    isd = read(a.is_data)
    for w in wins:                                                                     # production: auto_by_bars
        rows += scan(isd, "2015-12-01", "2021-12-31", a.every, "IS 2015–2021", w, variant="auto_by_bars (सध्याचं)")
    rows += scan(isd, "2015-12-01", "2021-12-31", a.every, "IS 2015–2021", max(wins), variant=FIXED[0], es_over=FIXED[1])
    if a.recent_data:
        rec = read(a.recent_data)                                                      # history 2026-07-01 पासूनच ⇒ window = उपलब्ध सगळा
        part = "Jul–Oct 2026 (contaminated, illustration; history 1 Jul पासूनच)"
        rows += scan(rec, "2026-07-15", "2026-10-08", 3, part, 130, variant="auto_by_bars (सध्याचं)")
        rows += scan(rec, "2026-07-15", "2026-10-08", 3, part, 130, variant=FIXED[0], es_over=FIXED[1])
    os.makedirs(a.out, exist_ok=True)
    md = report(rows)
    open(os.path.join(a.out, "A4b_gray.md"), "w", encoding="utf-8").write(md)
    json.dump(rows, open(os.path.join(a.out, "A4b_gray.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(md)


if __name__ == "__main__":
    main()
