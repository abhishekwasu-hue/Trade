"""
run_visual_forward_report.py
------------------------------
🎓 Opportunity Engine PR-V forward testing (historical backfill नाही — वापरकर्त्याचा निर्णय, खर्च टाळण्यासाठी): रोजच्या EOD visual audit (`run_visual_audit.py`)
चे निकाल पुढे आलेल्या प्रत्यक्ष डेटावर तपासणे. कुठलाही API call नाही (फक्त साठवलेले records + collector चा 5M डेटा).

  1. तयारी: किती आठवडे / किती audited levels (निष्कर्षासाठी ≥ 4 आठवडे आणि 200+ levels).
  2. Agreement: engine grade × model verdict.
  3. Level reaction (पुढच्या 10 sessions, 1H): model verdict नुसार आणि consensus वर्गानुसार — VALID/CONSENSUS levels खरंच जास्त टिकतात का.
  4. off / score / gate तुलना — forward कालावधीतल्या (collector चा index 5M) backtest वर, तेच निर्णय-नियम.
  5. खर्च: calls, tokens, ($ दर दिल्यास) रक्कम.

    python3 run_visual_forward_report.py --symbol NIFTY
    python3 run_visual_forward_report.py --symbol BANKNIFTY --price-in 4 --price-out 20 --out /root/oe_forward
"""
import argparse
import os
import sys

import pandas as pd

from opportunity_engine import backtest as BT
from opportunity_engine import volume as VOL
from opportunity_engine.visual_audit import compare as CMP
from opportunity_engine.visual_audit import evaluate as EV
from opportunity_engine.visual_audit import store as VS

CACHE = os.path.join("data", "oe_visual_audit.jsonl")


def records_to_audit_df(records):
    """JSONL records -> प्रत्येक label ची एक row (audit_date, symbol, tf, level_id, label, kind, zone_low/high = outer, engine_grade, model_verdict, reason)."""
    rows = []
    for r in records:
        ov = r.get("overlay") or {}
        verdicts = {v["label"]: v for v in ((ov.get("data") or {}).get("verdicts") or [])} if ov.get("status") == "OK" else {}
        for lab in r.get("labels") or []:
            v = verdicts.get(lab["label"], {})
            rows.append({"audit_date": pd.Timestamp(r["audit_date"]).normalize(), "symbol": r.get("symbol"), "tf": r.get("tf"), "level_id": lab["level_id"],
                         "label": lab["label"], "kind": lab.get("kind"), "zone_low": lab.get("outer_low"), "zone_high": lab.get("outer_high"),
                         "engine_grade": lab.get("grade"), "model_verdict": v.get("verdict"), "model_reason": v.get("reason")})
    return pd.DataFrame(rows)


def cost_summary(records, price_in=None, price_out=None):
    tin = sum(int((r.get("usage") or {}).get("input_tokens", 0) or 0) for r in records)
    tout = sum(int((r.get("usage") or {}).get("output_tokens", 0) or 0) for r in records)
    calls = sum(int((r.get("usage") or {}).get("calls", 0) or 0) for r in records)
    days = len({r["audit_date"] for r in records})
    out = {"दिवस": days, "charts": len(records), "calls": calls, "input_tokens": tin, "output_tokens": tout, "cost_usd": None, "cost_per_day_usd": None}
    if price_in is not None and price_out is not None:
        cost = tin / 1e6 * float(price_in) + tout / 1e6 * float(price_out)
        out["cost_usd"] = round(cost, 2)
        out["cost_per_day_usd"] = round(cost / days, 3) if days else None
    return out


def adr_lookup_from(daily, n=14):
    """तारीख -> त्या दिवसाआधीच्या n दिवसांचा सरासरी range (ADR; फक्त मोजपट्टी)."""
    d = daily.copy()
    d["date"] = pd.to_datetime(d["timestamp"]).dt.normalize()
    rng = (d["high"] - d["low"]).astype(float)
    adr = rng.rolling(n, min_periods=5).mean().shift(1)
    m = dict(zip(d["date"], adr))
    return lambda x: m.get(pd.Timestamp(x).normalize())


def load_daily(symbol, token=None):
    """Daily इतिहास: Upstox (token असल्यास) नाहीतर offline NIFTY (फक्त NIFTY)."""
    if token:
        from upstox_api import fetch_candles
        df = fetch_candles(token, symbol, current_spot=0, interval="day", lookback_days=900)
        if df is not None and len(df):
            return df
    if symbol == "NIFTY":
        import real_nifty_data
        return real_nifty_data.load_nifty_daily_combined()
    return None


def main(argv=None, frames=None, daily=None):
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="NIFTY")
    p.add_argument("--cache", default=CACHE)
    p.add_argument("--index-5m", default=None, help="collector चा index 5M parquet (डीफॉल्ट data/oe_index_5min_<SYMBOL>.parquet)")
    p.add_argument("--token", default=None)
    p.add_argument("--price-in", type=float, default=None)
    p.add_argument("--price-out", type=float, default=None)
    p.add_argument("--out", default="oe_forward_out")
    args = p.parse_args(argv)
    sym = args.symbol.upper()
    recs = [r for r in VS.read_jsonl(args.cache) if r.get("symbol") == sym]
    if not recs:
        print(f"ℹ️ {args.cache} मध्ये {sym} चे visual audit records नाहीत — रोजचा run_visual_audit.py चालू झाल्यावर अहवाल मिळेल.")
        return 0
    os.makedirs(args.out, exist_ok=True)
    audit = records_to_audit_df(recs)
    ok, msg = EV.readiness(audit)
    print(("✅ " if ok else "ℹ️ ") + msg)
    cost = cost_summary(recs, args.price_in, args.price_out)
    print(f"खर्च: {cost['दिवस']} दिवस, {cost['calls']} calls, tokens {cost['input_tokens']:,}/{cost['output_tokens']:,}" +
          (f", ≈ ${cost['cost_usd']} (प्रति दिवस ${cost['cost_per_day_usd']})" if cost["cost_usd"] is not None else ""))
    pd.DataFrame([cost]).to_csv(os.path.join(args.out, "forward_cost.csv"), index=False)
    mats = EV.agreement_matrix(audit)
    if len(mats["grade_vs_model"]):
        print("\n=== Engine grade × model verdict ===")
        print(mats["grade_vs_model"].to_string())
        mats["grade_vs_model"].to_csv(os.path.join(args.out, "forward_agreement.csv"))
    if frames is None:
        path = args.index_5m or os.path.join("data", f"oe_index_5min_{sym}.parquet")
        if not os.path.exists(path):
            print(f"⚠️ {path} नाही — reaction/तुलनेसाठी collector (collect_index_futures_volume.py) चा index 5M हवा. फक्त वरचे तक्ते.")
            return 0
        if daily is None:
            import cloud_db
            daily = load_daily(sym, cloud_db.get_effective_upstox_token(args.token))
        frames = VOL.frames_from_index_5m(pd.read_parquet(path), daily=daily)
    adr = adr_lookup_from(daily) if daily is not None and len(daily) else None
    rx = EV.reactions(audit, frames["1h"], adr_lookup=adr)
    rt = EV.reaction_table(rx, "model_verdict")
    rx.to_csv(os.path.join(args.out, "forward_reaction_rows.csv"), index=False)
    rt.to_csv(os.path.join(args.out, "forward_reaction_by_verdict.csv"), index=False)
    print("\n=== Level reaction (पुढच्या 10 sessions, 1H) — model verdict नुसार ===")
    print(rt.to_string(index=False) if len(rt) else "(अजून पुरेसे पुढचे bars नाहीत)")
    by_date = VS.records_by_date(recs)
    first = min(by_date)
    bcfg = BT.BacktestConfig(symbol=sym, start=first, variants=("V1",))
    tl = BT.prepare_timeline(frames, bcfg)
    rc, _ = CMP.reaction_by_class(tl, frames, by_date)
    rc.to_csv(os.path.join(args.out, "forward_reaction_by_class.csv"), index=False)
    print("\n=== Level reaction — consensus वर्गानुसार ===")
    print(rc.to_string(index=False) if len(rc) else "(levels तयार होण्याइतका इतिहास अजून नाही — 4H ला ~15 sessions लागतात)")
    table, _ = CMP.modes_table(tl, bcfg, by_date)
    table.to_csv(os.path.join(args.out, "forward_consensus_modes.csv"), index=False)
    print("\n=== off / score / gate (forward कालावधी; R साइज-विना) ===")
    print(table.to_string(index=False))
    print(f"\nCSV: {os.path.abspath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
