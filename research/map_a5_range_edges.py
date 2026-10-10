"""research/map_a5_range_edges.py — नकाशा A5 (G10 / S9): range कडांचे tests IS वर. **फक्त अहवाल; threshold नाही.**

Trade-degree RANGE = 15M वर repo ची व्याख्या (opportunity_engine/structure.StructureTracker, KB K1: N नवे swings, निर्णय नाही ⇒ RANGE;
range_high / range_low त्या bar पर्यंत confirmed swings वरून). Market_state F2 trend दिशा ठरल्यावर range मध्ये परत जात नाही, म्हणून
trade-degree साठी हा tracker. पालक (HTF) दिशा = market_state F2 trend (1H, त्या bar पर्यंत).
Test = RANGE असताना कडेला (± area_tol_mr × MR) पहिला touch; त्याचे bars कडेवर असेपर्यंत एक episode. प्रकार (episode मधल्या bars वरून):
  1. sweep + reclaim — wick / close कडेपलीकडे, मग close परत आत (real break नाही);
  2. sweep शिवाय rejection — कडेला लागला, पलीकडे गेला नाही;
  3. real break — elliott/breaks.first_real_break (KB G).
Outcome (फक्त गटांसाठी): decision bar (reclaim close / rejection touch bar) नंतर — विरुद्ध कड आधी की ही कड real-broken आधी (horizon).
R:R (spot): entry = decision bar close, SL = sweep टोक (नसेल तर कड) ∓ sl_buffer_mr × MR (सध्याचं dashboard setting 0.25 MR),
target = विरुद्ध कड. Range उंची ÷ risk सुद्धा.
S6 + S9: पालक trend असताना trend दिशेची कड (up ⇒ खालची) वि. विरुद्ध कड — वेगळे.

    python3 research/map_a5_range_edges.py --is-data data/nifty50_1min.parquet --out docs/reports/situation_map
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import breaks as BR                 # noqa: E402
from elliott import data_policy as DP            # noqa: E402
from elliott import settings as ES               # noqa: E402

TOL_MR = 0.3           # touch = simple_core area_tol_mr [A1 register]
SL_BUF_MR = 0.25       # Abhi K-10 round 2 dashboard SL buffer
HORIZON = 200          # bars [A1 register]


def parent_dir(h1, t):
    from market_state import core as C
    f = h1[(pd.to_datetime(h1["bar_end"]) <= t) & (pd.to_datetime(h1["bar_end"]) > t - pd.Timedelta(days=60))].reset_index(drop=True)
    if len(f) < 30:
        return 0
    return int(C.trend(f)["dir"])


def scan(fr, h1, log=print):
    from opportunity_engine.structure import StructureTracker
    es = dict(ES.DEFAULTS)
    mr = BR.median_range(fr, 20)
    h, lo, c = (fr[k].to_numpy(float) for k in ("high", "low", "close"))
    st = StructureTracker("15m")
    out, active = [], {}
    for j, r in enumerate(fr.itertuples(index=False)):
        st.on_bar(pd.Timestamp(r.bar_end), r.open, r.high, r.low, r.close)
        snap = st.snapshot()
        if snap["trend_state"] != "RANGE" or not np.isfinite(mr[j]):
            active = {}
            continue
        hi_, lo_ = float(snap["range_high"]), float(snap["range_low"])
        tol = TOL_MR * float(mr[j])
        for edge, lvl, touch in (("upper", hi_, h[j] >= hi_ - tol), ("lower", lo_, lo[j] <= lo_ + tol)):
            key = (edge, round(lvl, 2))
            if touch and key not in active:
                active[key] = j
                out.append({"j": j, "edge": edge, "level": lvl, "other": lo_ if edge == "upper" else hi_, "ts": str(r.timestamp)})
            elif not touch and key in active and j - active[key] > 3:
                active.pop(key, None)
        if log and j % 20000 == 0:
            log(f"  {r.timestamp}: tests {len(out)}")
    res = []
    for t in out:
        j, lvl, other = t["j"], t["level"], t["other"]
        up = t["edge"] == "upper"
        side = "above" if up else "below"
        end = min(len(fr) - 1, j + HORIZON)
        brk = BR.first_real_break(fr, j, lvl, side, es, mr=mr, end=end)
        # episode: j पासून कडेवर / पलीकडे असलेले bars; sweep = पलीकडे wick / close
        k, swept, ext, dec = j, False, (h[j] if up else lo[j]), None
        while k <= end:
            beyond = (h[k] > lvl) if up else (lo[k] < lvl)
            if beyond:
                swept = True
                ext = max(ext, h[k]) if up else min(ext, lo[k])
            inside = (c[k] <= lvl) if up else (c[k] >= lvl)
            if (swept and inside) or (not swept and inside and k > j - 1):
                dec = k
                break
            k += 1
        if brk is not None and (dec is None or brk <= dec):
            kind = "real_break"
        elif swept:
            kind = "sweep_reclaim"
        else:
            kind = "rejection"
        rec = {**t, "kind": kind, "decision": None, "rr": None, "height_risk": None, "result": None}
        if kind != "real_break" and dec is not None:
            entry = float(c[dec])
            sl = (max(ext, lvl) + SL_BUF_MR * mr[dec]) if up else (min(ext, lvl) - SL_BUF_MR * mr[dec])
            risk = abs(entry - sl)
            if risk > 0 and np.isfinite(risk):
                rec.update(decision=int(dec), rr=round(abs(other - entry) / risk, 2), height_risk=round(abs(lvl - other) / risk, 2))
            seg_h, seg_l = h[dec + 1:end + 1], lo[dec + 1:end + 1]
            reach = np.nonzero((seg_l <= other) if up else (seg_h >= other))[0]
            b2 = BR.first_real_break(fr, dec + 1, lvl, side, es, mr=mr, end=end)
            k_reach = dec + 1 + int(reach[0]) if len(reach) else None
            if k_reach is not None and (b2 is None or k_reach < b2):
                rec["result"] = "opposite_edge"
            elif b2 is not None:
                rec["result"] = "edge_broke"
            else:
                rec["result"] = "neither"
        rec["parent"] = parent_dir(h1, pd.Timestamp(fr["bar_end"].iloc[j]))
        rec["with_trend_edge"] = None if rec["parent"] == 0 else ((not up) if rec["parent"] > 0 else up)
        res.append(rec)
    return res


def report(rows):
    df = pd.DataFrame(rows)
    L = ["# नकाशा A5: range कडांचे tests (G10 / S9), IS 2015–2021", "",
         "**फक्त अहवाल; threshold नाही.** Range = 15M StructureTracker RANGE (KB K1). Outcome फक्त गटांसाठी. R:R: entry = decision close, "
         "SL = sweep टोक / कड ∓ 0.25 MR, target = विरुद्ध कड.", "", f"एकूण tests: {len(df)}", ""]
    if not len(df):
        return "\n".join(L) + "\n"
    L += ["| प्रकार | n | विरुद्ध कड आधी | कड तुटली आधी | दोन्ही नाही | R:R ≥ 3 शक्य | उंची ÷ risk (median) |", "|---|---|---|---|---|---|---|"]
    for k in ("sweep_reclaim", "rejection", "real_break"):
        g = df[df["kind"] == k]
        if not len(g):
            continue
        rv = g["result"].value_counts()
        rr3 = int((g["rr"].fillna(0) >= 3).sum())
        L.append(f"| {k} | {len(g)} | {rv.get('opposite_edge', 0)} | {rv.get('edge_broke', 0)} | {rv.get('neither', 0)} | {rr3} | "
                 f"{g['height_risk'].median() if g['height_risk'].notna().any() else '—'} |")
    L += ["", "## S6 + S9: पालक (HTF) trend असताना", "", "| कड | n | विरुद्ध कड आधी | कड तुटली आधी | R:R ≥ 3 शक्य |", "|---|---|---|---|---|"]
    for lab, g in (("trend दिशेची कड", df[df["with_trend_edge"] == True]), ("विरुद्ध कड", df[df["with_trend_edge"] == False]),   # noqa: E712
                   ("पालक trend नाही (शुद्ध S9)", df[df["parent"] == 0])):
        g = g[g["kind"] != "real_break"]
        rv = g["result"].value_counts()
        L.append(f"| {lab} | {len(g)} | {rv.get('opposite_edge', 0)} | {rv.get('edge_broke', 0)} | {int((g['rr'].fillna(0) >= 3).sum())} |")
    L += ["", "**मर्यादा:** market_state F2 trend दिशा ठरल्यावर range मध्ये जात नाही ⇒ \"पालक trend नाही\" गट जवळजवळ रिकामा राहतो.",
          "Range ओळखीचे parameters (StructureTracker pivot_n / swing_k / N=4 swings) A1 register मध्ये."]
    return "\n".join(L) + "\n"


def main(argv=None):
    import market_state as MS
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--start", default="2015-02-01")
    ap.add_argument("--end", default="2021-12-31")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    a = ap.parse_args(argv)
    raw = pd.read_parquet(a.is_data) if a.is_data.endswith(".parquet") else pd.read_csv(a.is_data, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    raw = DP.filter_allowed(raw, "golden")
    raw = raw[(raw["timestamp"] >= pd.Timestamp(a.start)) & (raw["timestamp"] < pd.Timestamp(a.end) + pd.Timedelta(days=1))]
    fr = MS.full_frames(raw)
    rows = scan(fr["15m"].reset_index(drop=True), fr["1h"].reset_index(drop=True))
    os.makedirs(a.out, exist_ok=True)
    md = report(rows)
    open(os.path.join(a.out, "A5_range_edges.md"), "w", encoding="utf-8").write(md)
    json.dump(rows, open(os.path.join(a.out, "A5_range_edges.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(md[:1800])


if __name__ == "__main__":
    main()
