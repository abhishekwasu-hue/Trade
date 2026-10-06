"""
banknifty_positional.py
-----------------------
🎓 H-POS1 (docs/reports/preregistered_hypotheses.md): BANKNIFTY positional short strike — levels वि. random. G2 (a) ची daily प्रतिकृती.
Report-only. Sealed holdout बंद: 2024-03-31 नंतरचा भाग load करतानाच कापला जातो.

डेटा: niftyindices.com वरचा अधिकृत NIFTY BANK daily CSV (वापरकर्ता देणार). Engines: SR V3 (day + week) आणि sr_dynamic daily. OE 1d वगळला (intraday लागतं).

    python3 banknifty_positional.py --csv data/offline/NIFTY_BANK_daily.csv --report docs/reports/h_pos1_banknifty.md
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

import g2_followups as G
import leg_level_validation as T3

ENGINES = ("SRV3_DW", "DYN_D")                                  # OE_1D नाही (daily-only डेटा)
_ALIASES = {"date": "timestamp", "timestamp": "timestamp", "index date": "timestamp", "open": "open", "high": "high", "low": "low", "close": "close",
            "open index value": "open", "high index value": "high", "low index value": "low", "closing index value": "close"}


def parse_dates(col):
    """तारखा → IST तारीख (naive, मध्यरात्र). आधी ISO (2015-01-01, 2015-01-01T00:00:00+05:30) — 90%+ जुळल्या तर तेच; नाहीतर day-first
    (niftyindices: "01 Jan 2015", "01-01-2015"). ⚠️ ISO तारखा day-first ने वाचल्यास 2021-09-01 → 9 Jan होतो (review: synthetic run मध्ये सापडलं)."""
    s = col.astype(str).str.strip()
    has_tz = s.str.contains(r"(?:[+-]\d{2}:?\d{2}|Z)$", regex=True)
    if has_tz.mean() >= 0.9:                                            # offset सह ⇒ IST मध्ये
        iso = pd.to_datetime(s, format="ISO8601", errors="coerce", utc=True)
        if iso.notna().mean() >= 0.9:
            return iso.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None).dt.normalize()
    iso = pd.to_datetime(s, format="ISO8601", errors="coerce")           # offset नाही ⇒ आधीच IST (UTC मानत नाही)
    if iso.notna().mean() >= 0.9:
        return iso.dt.normalize()
    return pd.to_datetime(s, dayfirst=True, errors="coerce", format="mixed").dt.normalize()


def load_banknifty_daily(path, cutoff=None):
    """niftyindices CSV (स्तंभांची नावं/स्पेस/तारीख-format सहनशील) -> timestamp/open/high/low/close, तारीख-क्रमाने, duplicates काढून.
    `cutoff` (डीफॉल्ट T3.VAL_END = 2024-03-31) नंतरच्या ओळी **load करतानाच** कापल्या जातात — holdout कधीच परत येत नाही."""
    cutoff = pd.Timestamp(T3.VAL_END if cutoff is None else cutoff)
    raw = pd.read_csv(path)
    cols = {}
    for c in raw.columns:
        k = str(c).strip().lower()
        if k in _ALIASES and _ALIASES[k] not in cols.values():
            cols[c] = _ALIASES[k]
    df = raw.rename(columns=cols)
    missing = {"timestamp", "open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(f"CSV मध्ये स्तंभ नाहीत: {sorted(missing)} (मिळाले: {list(raw.columns)})")
    df = df[["timestamp", "open", "high", "low", "close"]].copy()
    df["timestamp"] = parse_dates(df["timestamp"])
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df = df.dropna().sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    df = df[df["timestamp"] <= cutoff]
    df = df[(df["high"] >= df[["open", "close"]].max(axis=1)) & (df["low"] <= df[["open", "close"]].min(axis=1)) & (df["low"] > 0)]
    return df.reset_index(drop=True)


def run(dd, log=None):
    """G2 (a) चाच positional_test (OE zones नाहीत) ⇒ (तक्ता, rows). फक्त ENGINES."""
    tab, rows = G.positional_test(dd, {}, log)
    if len(tab):
        tab = tab[tab["engine"].isin(ENGINES)].reset_index(drop=True)
    return tab, rows


def level_edge_cells(tab, min_pp=3.0, z_max=-2.0):
    """H-POS1 चा pre-registered नियम: एकाच engine × bucket मध्ये IS आणि VAL दोन्हींत touch-breach कमी, cluster z ≤ −2, फरक ≥ 3 pp."""
    if tab is None or not len(tab):
        return []
    out = []
    for (eng, bk), g in tab.groupby(["engine", "अंतर"]):
        per = {r["period"]: r for _, r in g.iterrows()}
        if {"IS", "VAL"} <= set(per) and all(
                per[p]["z_touch"] <= z_max and per[p]["touch_random%"] - per[p]["touch_level%"] >= min_pp for p in ("IS", "VAL")):
            out.append((eng, bk))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--out", default=None, help="CSV तक्ता कुठे लिहायचा (डीफॉल्ट report शेजारी)")
    a = ap.parse_args(argv)
    if not os.path.exists(a.csv):
        sys.exit(f"CSV सापडली नाही: {a.csv}")
    dd = load_banknifty_daily(a.csv)
    print(f"BANKNIFTY daily: {len(dd)} दिवस, {dd['timestamp'].min():%Y-%m-%d} → {dd['timestamp'].max():%Y-%m-%d} (holdout कापला)", flush=True)
    tab, rows = run(dd, log=lambda m: print(m, flush=True))
    edges = level_edge_cells(tab)
    verdict = ("**Level edge सापडला** (pre-registered नियमानुसार): " + ", ".join(f"{e} {b}" for e, b in edges)) if edges else \
        "**Null टिकला** — pre-registered नियमानुसार कुठल्याही engine × अंतर सेलमध्ये level edge नाही (अपेक्षित)."
    if a.report:
        out_csv = a.out or os.path.splitext(a.report)[0] + ".csv"
        tab.to_csv(out_csv, index=False)
        txt = ["# H-POS1 — BANKNIFTY positional short strike: levels वि. random (report-only)\n",
               f"डेटा: NIFTY BANK daily (niftyindices.com), {dd['timestamp'].min():%Y-%m-%d} → {dd['timestamp'].max():%Y-%m-%d}; "
               "2024-03-31 नंतरचा भाग load करतानाच कापला. व्याख्या आणि नियम: `docs/reports/preregistered_hypotheses.md` (H-POS1).\n",
               f"FAILS: {G.FAILS or 'नाहीत'}.\n", G._md(tab), "\n## निकाल\n", verdict + "\n"]
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("\n".join(txt))
        print(f"report: {a.report}")
    print(verdict)
    return tab


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
