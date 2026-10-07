"""
research/elliott_data_check.py — Elliott E0: data उपलब्धता तपासणी (फक्त वाचन, network नाही, ≤ 40 ओळींचा अहवाल)
-----------------------------------------------------------------------------------------------------------
🎓 Master prompt §5: structure (NIFTY spot), options P&L चा स्रोत, splits, आणि त्या काळाचं expiry calendar/lot. हे script
सांगतं की प्रत्यक्ष काय आहे — गृहीत नाही:
  • offline NIFTY 1m (repo parquet): कव्हरेज IS/VAL मध्ये (holdout कधीच वाचत नाही — data_policy filter)
  • trade-data checkout (दिल्यास): golden 1m candles, Upstox expired-API probe, NSE bhavcopy कव्हरेज, पहिली NIFTY weekly
    expiry (weekly options सुरू झाल्याचा data-पुरावा), वर्षानुसार expiry weekday, lot sizes (UDiFF मध्येच)

    python3 research/elliott_data_check.py [--data /root/trade-data]
"""
import argparse
import glob
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import bhavcopy as BC  # noqa: E402
from elliott import data_policy as DP  # noqa: E402


def offline_spot(lines, path=os.path.join(ROOT, "data", "nifty50_1min.parquet")):
    if not os.path.exists(path):
        lines.append("❌ offline NIFTY 1m parquet नाही")
        return
    d = DP.filter_allowed(pd.read_parquet(path, columns=["timestamp"]), "research")
    ts = pd.to_datetime(d["timestamp"])
    per = ts.map(DP.period)
    days = ts.dt.date
    lines.append(f"NIFTY spot 1m (offline): {ts.min():%Y-%m-%d} → {ts.max():%Y-%m-%d}, {len(d):,} bars")
    for p in ("IS", "VAL"):
        m = (per == p).to_numpy()
        lines.append(f"  {p}: {days[m].nunique()} दिवस, सरासरी {m.sum() / max(days[m].nunique(), 1):.0f} bars/दिवस")


def golden(lines, data):
    ps = glob.glob(os.path.join(data, "upstox", "NIFTY_1m_*.csv.gz"))
    if not ps:
        lines.append("golden 1m: ❌ नाही (VPS: elliott_vps_data.py golden)")
        return
    d = pd.read_csv(ps[0], parse_dates=["timestamp"])
    g = d.groupby(d["timestamp"].dt.date).size()
    short = g[g < 370]
    lines.append(f"golden 1m: {len(d):,} bars, {len(g)} दिवस ({g.index.min()} → {g.index.max()}); अपूर्ण दिवस {len(short)}"
                 + (f" ({', '.join(map(str, short.index[:4]))})" if len(short) else ""))


def probe(lines, data):
    p = os.path.join(data, "probes", "upstox_expired_probe.json")
    if not os.path.exists(p):
        lines.append("Upstox expired API probe: ❌ अजून चाललं नाही")
        return
    j = json.load(open(p, encoding="utf-8"))
    lines.append(f"Upstox expired API: expiries status {j.get('expiries_status')}, {j.get('n_expiries')} expiries "
                 f"({j.get('earliest')} → {j.get('latest')}); sample {j.get('sample_expiry')}: 1m candles {j.get('sample_candles', 0)}"
                 f" ⇒ {'✅ intraday premium मिळू शकतो' if j.get('sample_candles') else '❌ intraday premium नाही'}")


def bhav(lines, data):
    for sub, label in (("NIFTY", "IS/VAL"), ("NIFTY_golden", "golden")):
        base = os.path.join(data, "nse_fo_bhavcopy", sub)
        files = sorted(glob.glob(os.path.join(base, "*.parquet")))
        if not files:
            lines.append(f"NSE bhavcopy {label}: ❌ नाही (VPS: elliott_vps_data.py bhavcopy)")
            continue
        man_p = os.path.join(base, "manifest.csv")
        man = pd.read_csv(man_p, dtype=str) if os.path.exists(man_p) else pd.DataFrame(columns=["date", "status"])
        kind = man["status"].map(lambda s: s if s in ("ok", "missing") else "retry" if s in ("pending", "missing_weekday") else "error")
        vc = kind.value_counts()
        d = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        lines.append(f"NSE bhavcopy {label}: {len(files)} महिने, ओळी {len(d):,}; दिवस ok {vc.get('ok', 0)}, सुट्टी {vc.get('missing', 0)}, "
                     f"पुन्हा {vc.get('retry', 0)}, चूक {vc.get('error', 0)}")
        md = pd.to_datetime(man.loc[man["status"] == "missing", "date"])
        wk = md[md.dt.weekday < 5].dt.year.value_counts()
        for y, n in wk[wk > 16].items():
            lines.append(f"  ⚠️ {y}: {n} weekday 'सुट्टी' — NSE सुट्ट्यांपेक्षा जास्त; archive host/URL तपासा")
        if label != "IS/VAL":
            continue
        cal = BC.expiry_calendar(d)
        lines.append(f"  पहिली NIFTY weekly expiry listing (data-पुरावा): {BC.first_weekly_listing(d)}")
        cal["year"] = pd.to_datetime(cal["expiry"]).dt.year
        t = cal.groupby(["year", "weekday"]).size().unstack(fill_value=0)
        for y, r in t.iterrows():
            lines.append(f"  {y}: " + ", ".join(f"{k[:3]} {v}" for k, v in r.items() if v))
        per_day = d[d["instrument"] == "OPT"].groupby("date").size()
        if len(per_day):
            lines.append(f"  options ओळी/दिवस: median {per_day.median():.0f} (lot size: जुन्या format मध्ये नाही — E3 तक्ता)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=None, help="trade-data checkout")
    a = ap.parse_args(argv)
    lines = ["=== Elliott E0 data check ==="]
    offline_spot(lines)
    if a.data:
        golden(lines, a.data)
        probe(lines, a.data)
        bhav(lines, a.data)
    else:
        lines.append("(trade-data checkout दिला नाही — फक्त offline तपासणी)")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
