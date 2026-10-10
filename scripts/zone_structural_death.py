#!/usr/bin/env python3
"""Zone चा संरचनात्मक मृत्यू (फक्त मोजमाप; आत्ताच्या code चा मृत्यू बदलत नाही): प्रत्येक zone ला — zone पलीकडचा पहिला confirmed swing
(प्रत्येक degree), तो तुटला का / केव्हा, तुटेपर्यंत किती स्पर्श आणि किती वेळा किंमत ≥ 1 × σ_1H उलट गेली; code मृत्यूनंतर पुन्हा स्पर्श / उलट.
Code मध्ये तारीख / किंमत नाही; window = CLI.

  python3 scripts/zone_structural_death.py --data <1m csv> [...] --out-dir <dir> [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--days N]
      [--futures-dir <dir>] [--degrees 1 2 3]
Output: zone_structural_death.csv, zone_structural_death.json

window आधीपासून जिवंत zones साठी first_seen / eval = window सुरुवात (खरा जन्म `born_bar` स्तंभात).
व्याख्या: eval = zone ची शेवटची role, flip असेल तर flip bar पासून नाहीतर पहिल्यांदा दिसल्यापासून; swing = त्या वेळी confirmed, zone पलीकडचा
(seller: H ≥ top, buyer: L ≤ bottom) सगळ्यात जवळचा, त्याच segment चा आणि tref पर्यंत न तुटलेला; तुटला = close पलीकडे; स्पर्श = wick overlap (सलग bars = एक); उलट = पुढच्या
स्पर्शापर्यंत zone पासून ≥ 1 σ_1H.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from mtf import adapter as MA  # noqa: E402
from pivots import engine as PE  # noqa: E402
from scripts import degree_diag as DD  # noqa: E402
from scripts import leg_check as OLD  # noqa: E402
from scripts import leg_check2 as L2  # noqa: E402
from scripts import pattern_check2 as P2  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from scripts import zone_check as Z4  # noqa: E402

EV_DEAD = ("दुसरा real break (flip नंतर)", "accept", "real break")


def first_swing(pivots, role, bot, top, tref, close=None, seg_of=None, seg=None):
    """tref ला confirmed, zone पलीकडचा सगळ्यात जवळचा **जिवंत** swing (seller: H ≥ top; buyer: L ≤ bottom): त्याच segment चा, आणि
    pivot पासून tref पर्यंत close त्याच्या पलीकडे गेलेला नाही (आधीच तुटलेला swing नाही)."""
    ps = [p for p in pivots if p.confirm_bar <= tref and (seg_of is None or seg_of(p) == seg)]
    if close is not None:
        ps = [p for p in ps if not ((close[p.bar + 1:tref] > p.price).any() if p.kind == "H" else (close[p.bar + 1:tref] < p.price).any())]
    if role == "seller":
        c = [p for p in ps if p.kind == "H" and p.price >= top]
        return min(c, key=lambda p: (p.price, -p.bar)) if c else None
    c = [p for p in ps if p.kind == "L" and p.price <= bot]
    return max(c, key=lambda p: (p.price, p.bar)) if c else None


def broken_at(close, price, role, tref):
    for j in range(tref, len(close)):
        if (close[j] > price) if role == "seller" else (close[j] < price):
            return j
    return None


def touches(h, l, sig1h, bot, top, role, a, b):
    """[a, b) मध्ये भेटी (wick overlap, सलग = एक) आणि प्रत्येक भेटीनंतर पुढच्या भेटीपर्यंत ≥ 1 σ_1H उलट गेला का."""
    ep, inside = [], False
    for j in range(a, b):
        hit = h[j] >= bot and l[j] <= top
        if hit and not inside:
            ep.append(j)
        inside = hit
    rev = []
    for k, j in enumerate(ep):
        end = max(ep[k + 1] if k + 1 < len(ep) else b, j + 1)
        sg = sig1h[j]
        if not np.isfinite(sg):
            rev.append(False)
            continue
        rev.append(bool(l[j:end].min() <= bot - sg) if role == "seller" else bool(h[j:end].max() >= top + sg))
    return ep, rev


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", default=None, help="1m csv (NIFTY)")
    ap.add_argument("--tf-csv", default=None, help="index_candles_fetch चा TF csv (उदा. BANKNIFTY_15M.csv.gz) — 1m ऐवजी")
    ap.add_argument("--tf", default=None, choices=MA.TFS, help="--tf-csv चा TF (नसेल ⇒ file नावातून <INS>_<TF>.csv.gz)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--degrees", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--instrument", default=None, choices=INS.names(), help="index (default: TRADE_INSTRUMENT / NIFTY)")
    a = ap.parse_args(argv)
    INS.set_current(a.instrument)
    if a.tf_csv:
        a.tf = a.tf or MA.tf_of_path(a.tf_csv)
        m1 = None
        m15, real = MA.frame(a.tf_csv, a.tf)
    elif a.data:
        m1 = SC.load_1m(a.data)
        m15, real = PE.bars_15m(m1), None
    else:
        ap.error("--data किंवा --tf-csv हवं")
    res, struct, lg, trk = L2.build_all(m15, m1, OLD.load_futures(a.futures_dir), None)
    f1, f2 = P2.build_folds(lg, trk)
    t0, t1, ds = DD.window(m15, a.start, a.end, a.days) if real is None else MA.window_real(real, a.start, a.end, a.days)
    n = len(m15)
    syn = real is not None and a.tf != "15M"                                    # कृत्रिम sessions (W / D / 1H) ⇒ PDH / PDL zones नाहीत
    Z, _ = Z4.build_zones(lg, struct, trk, f1, f2, range(t0, n), s={"k_atoms": False} if syn else None)
    A = res["A"]
    h, l, c = A["h"], A["l"], A["c"]
    eday = pd.to_datetime(m15["timestamp"]).dt.normalize()                        # engine चा session (σ / segment)
    ts = pd.to_datetime(m15["timestamp"]) if real is None else real              # दाखवायची खरी वेळ
    S = lambda t: str(ts.iloc[t])[:16]  # noqa: E731
    sig1h = np.array([(res["sigma"] if syn else res["sigma_1h"]).get(pd.Timestamp(x), np.nan) for x in eday], float)  # TF csv ⇒ त्या TF चा σ
    seg_t = [res["segments"].get(pd.Timestamp(x)) for x in eday]
    seg_of = lambda p: res["segments"].get(pd.Timestamp(p.ts).normalize())  # noqa: E731
    life = {}
    for t in range(t0, t1):
        for z in Z.snap.get(t) or []:
            L = life.setdefault(z["id"], {"snaps": {}, "first": t})
            L["snaps"][t] = (z["bottom"], z["top"], z["role"], z.get("flip_bar"), z.get("pivot_bar"))
            L["last"] = t
    evs = {}
    for e in Z.events:
        if t0 <= e["bar"] < t1:
            evs.setdefault(e["id"], []).append((e["bar"], e["type"]))
    out = []
    for zid, L in life.items():
        es = sorted(evs.get(zid, []))
        first, last = L["first"], L["snaps"][L["last"]]
        fb = last[3]
        tref = fb if (fb is not None and fb >= first) else first
        ref = L["snaps"].get(tref) or L["snaps"][min(L["snaps"], key=lambda x: abs(x - tref))]
        bot, top, role = ref[0], ref[1], last[2]
        dead = [b for b, ty in es if ty == "मेला"]
        if dead:
            same = {ty for bb, ty in es if bb == dead[0]}
            reason, dbar = ("accept" if "accept" in same else ("दुसरा real break (flip नंतर)" if fb is not None else "real break")), dead[0]
        elif L["last"] < t1 - 1:
            reason, dbar = "prune / merge", L["last"] + 1
        else:
            reason, dbar = "जिवंत (window शेवटी)", None
        r = {"id": zid, "born_bar": "" if last[4] is None else S(last[4]), "first_seen": S(first), "flip_bar": "" if fb is None else S(fb),
             "code_death_bar": "" if dbar is None else S(dbar), "code_death_reason": reason, "eval_from": S(tref), "eval_role": role,
             "eval_band": f"{bot:.1f}-{top:.1f}"}
        for d in a.degrees:
            p = first_swing(res["pivots"].get(d, []), role, bot, top, tref, c, seg_of, seg_t[tref])
            b = None if p is None else broken_at(c[:t1], p.price, role, tref)
            end = b if b is not None else t1
            ep, rev = touches(h, l, sig1h, bot, top, role, tref + 1, end)
            r[f"D{d}_swing"] = "" if p is None else f"{p.kind} {p.price:.1f} ({S(p.bar)})"
            r[f"D{d}_swing_broken"] = "NA" if p is None else ("हो" if b is not None else "नाही")
            r[f"D{d}_broken_bar"] = "" if b is None else S(b)
            r[f"D{d}_touches_until_break"] = len(ep)
            r[f"D{d}_reversed_1sigma1h"] = sum(rev)
            r[f"D{d}_touch_bars"] = " ".join(S(j) for j in ep[:25])
            if dbar is not None:
                intact = "NA" if p is None else ("हो" if (b is None or b > dbar) else "नाही")
                r[f"D{d}_swing_intact_at_code_death"] = intact
                ep2, rev2 = touches(h, l, sig1h, bot, top, role, dbar + 1, end) if intact == "हो" else ([], [])
                r[f"D{d}_touches_after_code_death"] = len(ep2)
                r[f"D{d}_reversed_after_code_death"] = sum(rev2)
        out.append(r)
    os.makedirs(a.out_dir, exist_ok=True)
    keys = list(dict.fromkeys(k for r in out for k in r)) or ["—"]
    with open(os.path.join(a.out_dir, "zone_structural_death.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        [w.writerow(r) for r in sorted(out, key=lambda r: r["first_seen"])]

    def agg(d, reasons):
        dd = [r for r in out if r["code_death_reason"] in reasons]
        it = [r for r in dd if r.get(f"D{d}_swing_intact_at_code_death") == "हो"]
        return {"code ने मेलेले": len(dd), "swing अखंड (मृत्यूच्या वेळी)": len(it),
                "swing NA": sum(1 for r in dd if r.get(f"D{d}_swing_intact_at_code_death") == "NA"),
                "नंतर पुन्हा स्पर्श": sum(1 for r in it if r.get(f"D{d}_touches_after_code_death", 0) > 0),
                "नंतर स्पर्श + ≥1σ_1H उलट": sum(1 for r in it if r.get(f"D{d}_reversed_after_code_death", 0) > 0)}
    summ = {"instrument": INS.label(), "tf": a.tf if a.tf_csv else "15M (1m वरून)", "sigma_unit": f"σ_{a.tf} (त्याच TF चा)" if syn else "σ_1H", "window": [str(pd.Timestamp(ds[0]).date()), str(pd.Timestamp(ds[-1]).date())] if ds else None, "zones_total": len(out),
            "code_death_reason": dict(Counter(r["code_death_reason"] for r in out)),
            **{f"D{d}": {"मेला घटना (दुसरा break / accept)": agg(d, EV_DEAD), "prune / merge": agg(d, ("prune / merge",)),
                         "swing तुटलेले (window शेवटपर्यंत)": sum(1 for r in out if r[f"D{d}_swing_broken"] == "हो"),
                         "swing नाही (NA)": sum(1 for r in out if r[f"D{d}_swing_broken"] == "NA")} for d in a.degrees}}
    json.dump(summ, open(os.path.join(a.out_dir, "zone_structural_death.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
