"""opportunity_engine/visual_audit/compare.py — consensus modes (off / score / gate) चा backtest तुलना तक्ता (spec §17.9). एकच timeline, एकच निर्णय-साखळी.

तक्ता: trades, win %, avg win/loss, expectancy (R साइज-विना), दिवसाला trades आणि off च्या तुलनेत किती कमी — फक्त visual records असलेल्या कालावधीसाठी.
Level reaction rate: CONSENSUS वि. MATH_ONLY वि. VISUAL_ONLY (पुढच्या 10 sessions मधली प्रत्यक्ष reaction, 1H bars वर).
"""
from dataclasses import replace

import pandas as pd

from .. import backtest as BT
from . import consensus as CONS
from . import evaluate as EV


def covered_range(records_by_date):
    if not records_by_date:
        return None, None
    ds = sorted(records_by_date)
    return ds[0], ds[-1]


def modes_table(tl, bcfg, records_by_date, modes=("off", "score", "gate"), variant="V1", progress=None):
    """रिटर्न (तक्ता DataFrame, {mode: run_variant dict})."""
    lo, hi = covered_range(records_by_date)
    results, rows = {}, []
    base_trades = None
    for mode in modes:
        cfg = replace(bcfg, engine=replace(bcfg.engine, consensus_mode=mode), visual_records=records_by_date)
        r = BT.run_variant(tl, variant, cfg, progress)
        results[mode] = r
        tr = r["trades"]
        if lo is not None and len(tr):
            d = pd.to_datetime(tr["date"])
            tr = tr[(d >= lo) & (d <= hi)]
        n_days = sum(1 for day in tl.days if lo is not None and lo <= pd.Timestamp(day.date) <= hi)
        m = BT.summarize(tr, "r")
        cons = r.get("consensus")
        fb = int(cons["fallback"].sum()) if cons is not None and len(cons) else 0
        if mode == "off":
            base_trades = m["trades"]
        rows.append({"mode": mode, "trades": m["trades"], "win_pct": m["win_pct"], "avg_win_r": m["avg_win_r"], "avg_loss_r": m["avg_loss_r"],
                     "expectancy_r": m["expectancy_r"], "total_r": m["total_r"], "दिवस": n_days, "trades/दिवस": round(m["trades"] / n_days, 3) if n_days else None,
                     "off_पेक्षा_कमी_trades": None if base_trades is None else base_trades - m["trades"], "gate→score fallback दिवस": fb})
    return pd.DataFrame(rows), results


def class_rows(tl, records_by_date):
    """प्रत्येक दिवसाचे audit केलेले levels + consensus वर्ग (feedback शिवाय) — reaction तक्त्यासाठी."""
    rows = []
    for day in tl.days:
        recs = records_by_date.get(pd.Timestamp(day.date).normalize())
        if not recs:
            continue
        res = CONS.classify(day.levels, day.pool, recs)
        by_id = {z["level_id"]: z for z in day.levels + day.pool if z.get("level_id")}
        for z in res["added"]:
            by_id.setdefault(z["level_id"], z)
        for lid, c in res["classes"].items():
            z = by_id.get(lid)
            if z is None:
                continue
            rows.append({"audit_date": day.date, "level_id": lid, "kind": z["kind"], "tf": z["tf"], "zone_low": float(z.get("outer_low", z["low"])),
                         "zone_high": float(z.get("outer_high", z["high"])), "consensus_class": c["class"], "model_verdict": c.get("verdict"), "adr": day.adr})
        for z in res["added"]:
            rows.append({"audit_date": day.date, "level_id": z["level_id"], "kind": z["kind"], "tf": z["tf"], "zone_low": float(z.get("outer_low", z["low"])),
                         "zone_high": float(z.get("outer_high", z["high"])), "consensus_class": z["consensus"], "model_verdict": None, "adr": day.adr})
    return pd.DataFrame(rows)


def reaction_by_class(tl, frames, records_by_date, tf="1h"):
    rows = class_rows(tl, records_by_date)
    if not len(rows):
        return pd.DataFrame(), rows
    adr = dict(zip(rows["audit_date"], rows["adr"]))
    rx = EV.reactions(rows, frames[tf], adr_lookup=lambda d: adr.get(d))
    return EV.reaction_table(rx, "consensus_class"), rx
