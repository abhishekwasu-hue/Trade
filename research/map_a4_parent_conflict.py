"""research/map_a4_parent_conflict.py — नकाशा A4: PARENT_CONFLICT चं मोजमाप. **फक्त नोंद / अहवाल; gate नाही.**

दोन वाचनं, दिवसाच्या close ला (no-lookahead, market_state.read):
  (1) market_state ची HTF trend दिशा (F2, 1H) — Simple Core आज हीच वापरतो;
  (2) counts ची sequence दिशा — Elliott count engine चा vote (elliott.counts, market_state.elliott_vote), पालक degree = D2
      (gray ⇒ 0). [नकाशा P1: पालक = primary count मधल्या motive sequence ची दिशा — vote हा त्याचा आजचा code-proxy.]
Conflict = दोन्ही ≠ 0 आणि वेगळे. IS (दर `--every` वा दिवस) आणि Jul–Oct 2026 (contaminated, फक्त illustration) वेगवेगळे.

    python3 research/map_a4_parent_conflict.py --is-data data/nifty50_1min.parquet --recent-data <csv.gz> --out docs/reports/situation_map
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP            # noqa: E402

PARENT_DEGREE = 2


def read(path):
    raw = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return DP.filter_allowed(raw, "golden")


def scan(raw, start, end, every, part, log=print):
    import market_state as MS
    days = [pd.Timestamp(d) for d in sorted(pd.to_datetime(raw["timestamp"]).dt.normalize().unique())
            if pd.Timestamp(start) <= pd.Timestamp(d) <= pd.Timestamp(end)][::every]
    out = []
    for n, d in enumerate(days):
        asof = d + pd.Timedelta(hours=15, minutes=30)
        m1 = raw[(raw["timestamp"] >= d - pd.Timedelta(days=70)) & (raw["timestamp"] < asof)]
        ms = MS.read(m1, asof, run_elliott=True)
        ew = ms.get("elliott") or {}
        v = ew.get(PARENT_DEGREE) or ew.get(str(PARENT_DEGREE)) or {}
        tr = ms["trend"]
        ms_dir = int(tr.get("dir") or 0)
        ew_dir = int(v.get("dir") or 0) if not ew.get("error") else None
        out.append({"date": f"{d:%Y-%m-%d}", "part": part, "ms_dir": ms_dir, "ms_state": tr.get("state"), "ew_dir": ew_dir,
                    "ew_gray": v.get("gray"), "ew_error": ew.get("error"),
                    "conflict": bool(ms_dir and ew_dir and ms_dir != ew_dir)})
        if log and n % 25 == 0:
            log(f"  {part} {d:%Y-%m-%d}: {n + 1}/{len(days)}")
    return out


def report(rows):
    df = pd.DataFrame(rows)
    L = ["# नकाशा A4: PARENT_CONFLICT (market_state HTF trend वि. counts ची sequence दिशा)", "",
         "**फक्त नोंद — gate नाही.** तोपर्यंत पालक दिशा = market_state. Counts दिशा = Elliott count engine vote, पालक degree D2 (gray ⇒ 0).", ""]
    for part, g in df.groupby("part"):
        both = g[(g["ms_dir"] != 0) & (g["ew_dir"].fillna(0) != 0)]
        L += [f"## {part}", "", f"- दिवस: {len(g)} · counts gray / मत नाही: {int((g['ew_dir'].fillna(0) == 0).sum())} · count engine error: "
              f"{int(g['ew_error'].notna().sum())}",
              f"- दोन्हींचं मत असलेले दिवस: {len(both)} · **conflict: {int(both['conflict'].sum())}** "
              f"({(both['conflict'].mean() * 100 if len(both) else 0):.0f}%)",
              f"- market_state testing दिवशी conflict: {int(g[(g['ms_state'] == 'testing') & g['conflict']].shape[0])}", ""]
        ex = g[g["conflict"]].head(8)
        if len(ex):
            L += ["उदाहरणं (charts trade-data मध्ये):", "", "| दिवस | market_state | counts (D2) |", "|---|---|---|"]
            L += [f"| {r.date} | {'up' if r.ms_dir > 0 else 'down'} ({r.ms_state}) | {'up' if r.ew_dir > 0 else 'down'} |" for r in ex.itertuples()]
            L.append("")
    L += ["**Abhi साठी प्रश्न (G-MAP1):** PARENT_CONFLICT वर gate हवा का, की फक्त नोंद / size?"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--recent-data", default=None)
    ap.add_argument("--every", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    a = ap.parse_args(argv)
    rows = scan(read(a.is_data), "2015-04-01", "2021-12-31", a.every, "IS 2015–2021")
    if a.recent_data:
        rows += scan(read(a.recent_data), "2026-07-15", "2026-10-08", 1, "Jul–Oct 2026 (contaminated, illustration)")
    os.makedirs(a.out, exist_ok=True)
    md = report(rows)
    open(os.path.join(a.out, "A4_parent_conflict.md"), "w", encoding="utf-8").write(md)
    json.dump(rows, open(os.path.join(a.out, "A4_parent_conflict.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(md)


if __name__ == "__main__":
    main()
