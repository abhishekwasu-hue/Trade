"""research/sepoct_run_compare.py — 1 Sep – 8 Oct 2026 review: run2 (PAPER settings, Abhi 2026-10-08 23:48: target_mode impulse_end,
g9_tier full) वि. run1 settings (next_opposite_area, g9_tier रिकामा). दोन्ही एकाच run2 day.json मधून: main = run2, alts["run1"] = run1
settings तोच signal. फक्त अहवाल (data contaminated ⇒ illustration, tuning नाही).

    python3 research/sepoct_run_compare.py --run-dir /root/trade-data/review/sept2026/run2 --out docs/reports/situation_map
"""
import argparse
import glob
import json
import os


def r_mult(p, s):
    if not p or not p.get("ok") or not s or s.get("exit") is None or p.get("sl") is None:
        return None
    risk = abs(float(p["entry"]) - float(p["sl"]))
    return round((float(s["exit"]) - float(p["entry"])) * int(p["side"]) / risk, 2) if risk > 0 else None


def rows_of(run_dir):
    out = []
    for f in sorted(glob.glob(os.path.join(run_dir, "*", "day.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for s in d.get("signals") or []:
            old = (s.get("alts") or {}).get("run1") or {}
            out.append({"date": d["date"], "time": s["time"], "setup": s.get("setup") or "—", "entry": s.get("trigger_price"),
                        "new": {"plan": s.get("plan") or {}, "sim": s.get("sim") or {}},
                        "old": {"plan": old.get("plan") or {}, "sim": old.get("sim") or {}}})
    return out


def report(rows):
    def cell(x):
        p, s = x["plan"], x["sim"]
        if p.get("ok"):
            R = r_mult(p, s)
            return f"trade · R:R {p.get('rr')} · {s.get('result')} {'' if R is None else f'{R:+.2f}R'}"
        return f"नाही · {(p.get('reason') or '—')[:45]}"

    L = ["# 1 Sep – 8 Oct 2026: run2 (PAPER settings, Abhi 23:48) वि. run1", "",
         "**run2:** SL structural invalidation + 0.25 MR · rr_filter on, min_rr 3 · **target_mode impulse_end** · **g9_tier full**. "
         "**run1:** तेच, पण target_mode next_opposite_area, g9_tier रिकामा. Signals दोन्हीकडे तेच (engine बदललं नाही). "
         "Hindsight निकाल spot वर ≤ 3 sessions (SL / target आधी; एकाच bar मध्ये दोन्ही ⇒ SL). Data contaminated ⇒ फक्त illustration.", "",
         "| दिवस | वेळ | setup | entry | run1 | run2 |", "|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['date']} | {r['time']} | {r['setup']} | {r['entry']:,.1f} | {cell(r['old'])} | {cell(r['new'])} |")
    L += ["", "| | signals | trade झाले | target | SL | TIME | एकूण R | सरासरी R:R (trades) |", "|---|---|---|---|---|---|---|---|"]
    for k, lab in (("old", "run1 (next_opposite_area, g9 रिकामा)"), ("new", "run2 (impulse_end, g9 full)")):
        tr = [r[k] for r in rows if r[k]["plan"].get("ok")]
        res = [x["sim"].get("result") for x in tr]
        Rs = [v for v in (r_mult(x["plan"], x["sim"]) for x in tr) if v is not None]
        rr = [x["plan"].get("rr") for x in tr if x["plan"].get("rr") is not None]
        L.append(f"| {lab} | {len(rows)} | {len(tr)} | {res.count('TARGET')} | {res.count('SL')} | {res.count('TIME')} | "
                 f"{sum(Rs):+.2f} | {(sum(rr) / len(rr)) if rr else 0:.2f} |")
    L += ["", "**मर्यादा:** n लहान, contaminated काळ ⇒ निष्कर्ष नाही. impulse_end सुद्धा कधी कधी लहान degree चा impulse निवडतो "
          "(25 / 28 Sep) — degree-सुसंगत target ची व्याख्या टप्पा B मध्ये (next_opposite_area पर्याय म्हणून राहतो)."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "reports",
                                                  "situation_map"))
    a = ap.parse_args(argv)
    rows = rows_of(a.run_dir)
    md = report(rows)
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, "SepOct_run2_vs_run1.md"), "w", encoding="utf-8").write(md)
    print(md)


if __name__ == "__main__":
    main()
