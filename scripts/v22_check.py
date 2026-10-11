#!/usr/bin/env python3
"""🧭 v2.2 CHECK (थर v2.2 पायरी B, Abhi ✔ साठी): ① Daily Dow + ② 1H levels — W / D / 1H charts, प्रत्येक बंद 15M bar चा checklist ①②,
funnel आकडे. Code मध्ये तारीख नाही (window / क्षण CLI ने). Order / broker call नाही; LIVE ला हात नाही. Holdout rows कधीच नाहीत (guard).

  python3 scripts/v22_check.py --symbol NIFTY --data <1m csv.gz> --out-dir <dir> [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                               [--moments "YYYY-MM-DD HH:MM" ...]
  python3 scripts/v22_check.py --symbol BANKNIFTY --m15 <15M csv.gz> --daily <D csv.gz> --out-dir <dir> [...]
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from decision3 import charts as CH  # noqa: E402
from decision3 import daily as DD  # noqa: E402
from decision3 import engine as E3  # noqa: E402
from decision3 import liquidity as LQ  # noqa: E402


def load_inputs(a):
    from pivots import engine as PE
    from scripts import swing_check as SC
    if a.data:
        m1 = SC.load_1m(a.data)
        return PE.bars_15m(m1), m1, None
    m15 = pd.read_csv(a.m15)
    m15["timestamp"] = pd.to_datetime(m15["timestamp"])
    if getattr(m15["timestamp"].dt, "tz", None) is not None:
        m15["timestamp"] = m15["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    if "bar_end" not in m15.columns:
        m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    PE.guard(m15)
    d = None
    if a.daily:                                                            # Q33: पूर्ण उपलब्ध history (warm-up; degree तिच्यावर)
        from decision3 import history as HI
        d = HI.load_daily(a.daily)
        if "display_only" in d.columns and d["display_only"].fillna(False).astype(bool).any():
            from elliott import data_policy as DP
            raise DP.HoldoutError("display_only rows (फक्त chart साठी) Daily engine input मध्ये नाहीत")
        d = d[["timestamp", "open", "high", "low", "close"]]
        d = d[d["timestamp"] <= m15["timestamp"].max().normalize()].reset_index(drop=True)
        d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
        # Q33 (Abhi): Daily holdout candles = फक्त warm-up input (holdout evaluation साठी sealed, आधीच्या candles म्हणून मनाई नाही) ⇒
        # PE.guard चा holdout पहारा Daily ला लावत नाही; output मध्ये holdout तारीख नाही (history.sealed_fn). display_only पहारा वर.
    return m15[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True), None, d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--data", nargs="*")
    ap.add_argument("--m15")
    ap.add_argument("--daily", nargs="+", help="Daily files (csv / parquet), जुने आधी — पूर्ण history (Q33)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--moments", nargs="*", default=[], help="Abhi च्या खुणा: 'YYYY-MM-DD' (त्या दिवसाचे ✅ / 🟡 / कारण) किंवा 'YYYY-MM-DD HH:MM'")
    ap.add_argument("--max-charts", type=int, default=12)
    ap.add_argument("--tg-run", help="पायरी D: Telegram trader view run folder (उदा. <trade-data>/review/v22/nifty_run3) — फक्त फाइली, पाठवणं नाही")
    a = ap.parse_args(argv)
    m15, m1, daily = load_inputs(a)
    print(f"{a.symbol}: 15M bars {len(m15)} · engine बांधतो…", flush=True)
    from decision3 import history as HI
    V = E3.V22(m15, m1, daily, sealed=HI.sealed_fn(a.symbol))
    ts = pd.to_datetime(V.m15["timestamp"])
    lo = pd.Timestamp(a.frm) if a.frm else ts.min()
    hi = pd.Timestamp(a.to) + pd.Timedelta(days=1) if a.to else ts.max() + pd.Timedelta(days=1)
    bars = [i for i in range(len(ts)) if lo <= ts.iloc[i] < hi]
    rows = V.run(bars)
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "bars.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    fun = {"bars": len(rows), "trend": {}, "step1_ok": 0, "step2_ok": 0, "step2_fail": {}, "decision": {}, "setups": [], "funnel": {}}
    for r in rows:
        fun["decision"][r["decision"]] = fun["decision"].get(r["decision"], 0) + 1
        for k in ("①", "②", "③", "④", "⑥", "⑦"):
            v = r["checklist"][k][0]
            if v is not None:
                fun["funnel"].setdefault(k, {"ok": 0, "no": 0})["ok" if v else "no"] += 1
        if r["decision"] == "setup":
            lv = r["level"]
            fun["setups"].append({"ts": r["ts"], "mark": r["mark"], "side": "bull put" if lv["role"] == "support" else "bear call",
                                  "level": f"{lv['lo']:,.0f}–{lv['hi']:,.0f} {'+'.join(lv['births'])}{'★' * lv['sweeps']}",
                                  "conviction": r["conviction"], "score": r["conv_score"], "risk": r["risk"],
                                  "why": {k: v[1] for k, v in r["checklist"].items()}})
    for r in rows:
        fun["trend"][r["daily_trend"]] = fun["trend"].get(r["daily_trend"], 0) + 1
        if r["checklist"]["①"][0]:
            fun["step1_ok"] += 1
            if r["checklist"]["②"][0]:
                fun["step2_ok"] += 1
            else:
                k = r["checklist"]["②"][1]
                fun["step2_fail"][k] = fun["step2_fail"].get(k, 0) + 1
    days = sorted({ts.iloc[b].normalize() for b in bars})
    eod = []
    for d in days:
        b = max(i for i in bars if ts.iloc[i].normalize() == d)
        r = rows[bars.index(b)]
        eod.append({"day": str(d.date()), "trend": r["daily_trend"], "protected": r["protected"],
                    "active": [f"{x['role']} {x['lo']:,.0f}–{x['hi']:,.0f} {'+'.join(x['births'])}{'★' * x['sweeps']}" for x in r["active_levels"]]})
    fun["eod"] = eod
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(fun, f, ensure_ascii=False, indent=1, default=str)
    pngs = []
    from decision3 import history as HI
    st0 = HI.display_start(V.daily_df["timestamp"], None, HI.sealed_fn(a.symbol))   # Q33: NIFTY holdout तारखा chart वर नाहीत
    p = os.path.join(a.out_dir, "01_weekly.png")
    open(p, "wb").write(CH.weekly_png(V.daily_df.iloc[st0:], a.symbol))
    pngs.append(p)
    p = os.path.join(a.out_dir, "02_daily.png")
    open(p, "wb").write(CH.daily_png(V.daily_df, V.daily, a.symbol, start=st0))
    pngs.append(p)
    moments = [pd.Timestamp(x) + (pd.Timedelta(days=1) - pd.Timedelta(minutes=1) if len(x.strip()) == 10 else pd.Timedelta(0))
               for x in a.moments] or [ts.iloc[max(i for i in bars if ts.iloc[i].normalize() == d)] for d in days[-3:]]
    for k, mt in enumerate(moments, 1):
        cand = [i for i in bars if ts.iloc[i] <= mt]
        if not cand:
            continue
        t = cand[-1]
        st_ = DD.state_at(V.daily, V.bar_end[t])
        trend = st_.trend
        p = os.path.join(a.out_dir, f"{k + 2:02d}_1h_{str(ts.iloc[t])[:16].replace(' ', '_').replace(':', '')}.png")
        open(p, "wb").write(CH.h1_png(V.levels, t, trend, a.symbol, liq=LQ.pool_marks(V, t), band=st_.band if trend == "RANGE" else None))
        pngs.append(p)
    for k, st in enumerate([x for x in fun["setups"]][:a.max_charts], 1):
        t = next(r["bar"] for r in rows if r["ts"] == st["ts"])
        r = rows[bars.index(t)]
        tag = str(ts.iloc[t])[:16].replace(" ", "_").replace(":", "")
        p = os.path.join(a.out_dir, f"S{k:02d}_15m_{tag}.png")
        open(p, "wb").write(CH.m15_png(V, t, a.symbol, r=r))
        open(os.path.join(a.out_dir, f"S{k:02d}_story.txt"), "w", encoding="utf-8").write(CH.story(r))
        pngs.append(p)
    marks = {}
    for mstr in a.moments:
        day = pd.Timestamp(mstr).normalize()
        dr = [r for r in rows if pd.Timestamp(r["ts"]).normalize() == day]
        best = [r for r in dr if r["decision"] == "setup"]
        far = max(dr, key=lambda r: sum(1 for k in ("①", "②", "③", "④", "⑥", "⑦") if r["checklist"][k][0]), default=None)
        # सर्वात पुढे गेलेलं (bar, level) — decide फक्त सर्वोत्तम level दाखवतो; R:R ने अडलेले levels level_evals मध्ये
        cand = [(r, e) for r in dr for e in (r.get("level_evals") or [])]
        far_lv = max(cand, key=lambda x: (x[1]["n_ok"], x[0]["bar"]), default=(None, None))
        def brief(r):
            if r is None:
                return None
            steps = ("①", "②", "③", "⑥", "⑦")
            reached = max([k for k in steps if r["checklist"][k][0]], default="—", key=steps.index)
            rk = r.get("risk") or {}
            lv = r.get("level") or {}
            return {"ts": r["ts"], "decision": r["decision"], "mark": r.get("mark"), "step_reached": reached,
                    "trend_used": r.get("trend_used"), "resolution": r.get("trend_resolution"), "daily_phase": r.get("daily_phase"),
                    "daily_leg": r.get("daily_leg"), "corr_label": r.get("corr_label"), "weekly": r.get("weekly_trend"),
                    "mature": r.get("mature"), "conviction": r.get("conviction"), "form": r.get("commitment_form"),
                    "rr": rk.get("rr"), "entry": rk.get("entry"), "sl": rk.get("sl"), "target": rk.get("target"),
                    "level": None if not lv else f"{lv.get('role')} {lv.get('lo'):,.0f}–{lv.get('hi'):,.0f}",
                    "checklist": {k: v for k, v in r["checklist"].items()}, "why": r.get("why"), "notes": r.get("trend_notes")}
        r_, e_ = far_lv
        marks[mstr] = {"setups": [(r["ts"][11:16], r["mark"], r["conviction"]) for r in best],
                       "best_bar": brief(best[0] if best else far),
                       "furthest_level": None if e_ is None else {"ts": r_["ts"], "trend_used": r_.get("trend_used"),
                                                                  "resolution": r_.get("trend_resolution"), "daily_phase": r_.get("daily_phase"),
                                                                  "daily_leg": r_.get("daily_leg"), **e_}}
    fun["moments"] = marks
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(fun, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in fun.items() if k not in ("eod", "setups", "moments")}, ensure_ascii=False, indent=1))
    print(f"setups {len(fun['setups'])}:")
    for x in fun["setups"]:
        print(" ", x["ts"], x["mark"], x["side"], x["level"], x["conviction"], (x["risk"] or {}).get("rr"))
    for m_, v in marks.items():
        print("moment", m_, v["setups"], json.dumps(v["best_bar"], ensure_ascii=False, default=str)[:700])
    for e in eod[-5:]:
        print(e)
    print("charts:", *pngs, sep="\n  ")
    if a.tg_run:
        from decision3 import telegram_view as TV
        man = TV.build_run(V, rows, a.tg_run, a.symbol, os.path.basename(os.path.normpath(a.tg_run)), a.moments, a.max_charts)
        print(f"Telegram run: {a.tg_run} · items {0 if man is None else len(man['items'])} (पाठवणं फक्त VPS: "
              f"scripts/send_review_to_telegram.py --run review/v22/<run>)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
