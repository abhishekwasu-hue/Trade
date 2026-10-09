"""research/map_b_measure.py — टप्पा B §4 मोजमाप (report-only; कोणताही आकडा निवडायचा नाही).

नमुना: IS (data_policy नेच) मधले random दिवस, seed नोंद. वगळले: A1 चे 40 (map_a1_sensitivity seed ने पुन्हा काढलेले), K-10 run1 चे IS दिवस,
16 Feb 2018, 15 Nov 2021 (A3 / I7) — यादी अहवालात. प्रत्येक दिवस: research.k10_days.run_day (render नाही) — टप्पा B engine, PAPER seed
execution (main) + A1-सारखं (target 3R, rr filter नाही) तुलना; थांबलेले candidates (gray / blocked) चा reduce shadow निकाल.

अहवाल: signals / trades / R / expectancy (S# नुसार) · gray block वि. reduce (shadow) · G10 shadow (sweep सह / शिवाय) · commit_vs_impulse वितरण
(target / SL / time) + [प्रस्ताव] ≥ 1.0 स्तंभ · PARENT_UNKNOWN (preferred_count mode मध्ये) / S3_NO_1H_PIVOT गणना + R ·
baselines: A1 (−0.24R) आणि random-entry (प्रत्येक signal: त्याच दिवशी, त्याच दिशेने, त्याच window मधला random बंद 15M bar; तोच risk आणि 3R;
fixed seed; N draws — register).

    python3 research/map_b_measure.py --is-data data/nifty50_1min.parquet --days 200 --out-dir <trade-data>/research/situation_map/b_measure \
        --report docs/reports/situation_map/B_measure_IS.md
"""
import argparse
import collections
import json
import os
import random
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP            # noqa: E402

SEED = 20261010
A1_SEED = 20261009                               # map_a1_sensitivity.SEED
A1_POOL = ("2015-06-01", "2021-12-31")
POOL = ("2015-06-01", "2021-12-31")              # 130 दिवसांचा lookback (data 2015-01-09 पासून)
K10_RUN1_IS = ("2015-07-08", "2016-07-21", "2018-02-16", "2018-07-12", "2021-11-15")
MAP_DAYS = ("2018-02-16", "2021-11-15")
A1_BASELINE_R = -0.24
N_DRAWS = 20                                     # random-entry draws प्रति signal (register: research, व्याख्या)
WINDOW = ("09:30", "15:00")                      # random-entry window (engine चा opening window वगळून, 15:15 eod आधी)
A1_LIKE = {"rr_filter": False, "sl_mode": "structural_invalidation", "sl_buffer": 0.25, "sl_buffer_unit": "mr", "target_mode": "r_multiple",
           "target_value": 3.0, "g9_tier": "full", "gray_size": "half", "eod_signal_carry": "recheck", "g10_enabled": True,
           "g10_mode": "shadow", "parent_source": "market_state"}


def read(path):
    raw = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return DP.filter_allowed(raw, "research")


def sample_days(raw, n, seed=SEED):
    all_days = sorted(pd.to_datetime(raw["timestamp"]).dt.normalize().unique())
    a1_pool = [pd.Timestamp(d) for d in all_days if pd.Timestamp(A1_POOL[0]) <= pd.Timestamp(d) <= pd.Timestamp(A1_POOL[1])]
    a1 = set(random.Random(A1_SEED).sample(a1_pool, 40))
    excl = a1 | {pd.Timestamp(d) for d in K10_RUN1_IS + MAP_DAYS}
    pool = [pd.Timestamp(d) for d in all_days if pd.Timestamp(POOL[0]) <= pd.Timestamp(d) <= pd.Timestamp(POOL[1])
            and pd.Timestamp(d) not in excl and DP.allowed(pd.Timestamp(d), "research")]
    return sorted(random.Random(seed).sample(pool, n)), sorted(excl)


def r_of(plan, sim):
    if not plan or not plan.get("ok") or not sim or sim.get("result") in (None, "NO_TRADE"):
        return None
    risk = abs(float(plan["entry"]) - float(plan["sl"]))
    if risk <= 0 or sim.get("exit") is None:
        return None
    return round((float(sim["exit"]) - float(plan["entry"])) * int(plan["side"]) / risk, 3)


def random_entry(m15_after_day, day, side, risk, rng, n=N_DRAWS, max_sessions=3):
    """त्याच दिवशी त्याच window मधला random बंद 15M bar ⇒ close वर entry, तोच risk (points), 3R target, ≤ 3 sessions. R list."""
    from simple_core import execution as EX
    d0 = pd.to_datetime(m15_after_day["timestamp"])
    same = m15_after_day[(d0.dt.normalize() == day) & (d0.dt.strftime("%H:%M") >= WINDOW[0]) & (d0.dt.strftime("%H:%M") <= WINDOW[1])]
    if not len(same) or not risk:
        return []
    out = []
    for _ in range(n):
        b = same.iloc[rng.randrange(len(same))]
        entry = float(b["close"])
        p = {"ok": True, "side": side, "entry": entry, "sl": entry + risk if side < 0 else entry - risk,
             "target": entry + side * 3.0 * risk}
        after = m15_after_day[pd.to_datetime(m15_after_day["timestamp"]) > b["timestamp"]]
        sm = EX.simulate(p, after, max_sessions=max_sessions)
        out.append(r_of(p, sm))
    return [x for x in out if x is not None]


def run(raw, days, out_dir, log=print):
    from chart_reader import evaluate as EV
    from simple_core import execution as EX
    from simple_core import settings as SS
    sys.path.insert(0, os.path.join(ROOT, "research"))
    import k10_days as K
    main = dict(SS.PAPER_SEED)
    rng = random.Random(SEED + 1)
    rows = []
    for n, day in enumerate(days):
        dd = os.path.join(out_dir, f"{day:%Y-%m-%d}")
        f = os.path.join(dd, "measure.json")
        if os.path.exists(f):
            rows.append(json.load(open(f, encoding="utf-8")))
            continue
        try:
            rec = K.run_day(raw, day, dd, main, render=False, alts={"a1like": A1_LIKE})
        except Exception as exc:                                            # noqa: BLE001 — गुपचूप नाही: error नोंद
            rows.append({"date": f"{day:%Y-%m-%d}", "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
            continue
        m1 = raw[(raw["timestamp"] >= day - pd.Timedelta(days=1)) & (raw["timestamp"] < day + pd.Timedelta(days=6))]
        m15 = EV.frame(m1, "15m", day + pd.Timedelta(days=6))
        out = {"date": rec["date"], "signals": [], "stopped": [], "bars": len(rec["why_by_bar"])}
        for s in rec["signals"]:
            a1 = (s.get("alts") or {}).get("a1like") or {}
            rd = s.get("reading") or {}
            x = {"time": s["time"], "side": s["side"], "setup": s.get("setup"), "S": rd.get("S"), "flags": rd.get("flags"),
                 "gray": s.get("gray"), "eod": s.get("eod_carry"), "cvi": s.get("commit_vs_impulse"),
                 "parent_count": rd.get("parent_count"), "parent_ms": rd.get("parent_ms"), "conflict": rd.get("PARENT_CONFLICT"),
                 "waves_setup": (s.get("waves_cmp") or {}).get("setup"),
                 "count_tie": rd.get("count_tie"), "S11_alpha": rd.get("S11_alpha"), "setup_alpha": rd.get("setup_alpha"),
                 "s3_code": (rd.get("s3") or {}).get("code"), "plan_ok": bool((s.get("plan") or {}).get("ok")),
                 "plan_reason": (s.get("plan") or {}).get("reason"), "rr": (s.get("plan") or {}).get("rr"),
                 "R_main": r_of(s.get("plan"), s.get("sim")), "R_a1like": r_of(a1.get("plan"), a1.get("sim")),
                 "res_a1like": (a1.get("sim") or {}).get("result"), "g10": s.get("g10")}
            if s.get("setup") == "G10":                                     # shadow: paper असता तर
                sg = {**s, "g10": {**(s.get("g10") or {}), "mode": "paper"}}
                full = m15[pd.to_datetime(m15["timestamp"]) > pd.Timestamp(f"{rec['date']} {s['time']}")]
                pg = EX.plan(sg, {**A1_LIKE, "g10_mode": "paper"}, 1.0, spot_only=True)
                x["R_g10_shadow"] = r_of(pg, EX.simulate(pg, full))
            pa = a1.get("plan") or {}
            if pa.get("ok"):
                risk = abs(float(pa["entry"]) - float(pa["sl"]))
                x["R_random"] = random_entry(m15, day, int(s["side"]), risk, rng)
            out["signals"].append(x)
        for st in rec.get("stopped") or []:
            rd = st.get("reading") or {}
            out["stopped"].append({"time": st["time"], "kind": st["kind"], "why": str(st["why"])[:120], "side": st["side"],
                                   "gray": rd.get("gray"), "S": rd.get("S"), "parent_count": rd.get("parent_count"),
                                   "s3_code": (rd.get("s3") or {}).get("code"), "cvi": rd.get("commit_vs_impulse"),
                                   "count_tie": rd.get("count_tie"), "S11_alpha": rd.get("S11_alpha"),
                                   "R_reduce": r_of(st.get("reduce_plan"), st.get("reduce_sim")),
                                   "reduce_reason": (st.get("reduce_plan") or {}).get("reason")})
        os.makedirs(dd, exist_ok=True)
        json.dump(out, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        rows.append(out)
        if log:
            log(f"  {n + 1}/{len(days)} {day:%Y-%m-%d}: signals {len(out['signals'])} · stopped {len(out['stopped'])}")
    return rows


def _stat(rs):
    rs = [r for r in rs if r is not None]
    if not rs:
        return "0 | — | — | —"
    w = sum(1 for r in rs if r > 0)
    return f"{len(rs)} | {w} | {np.mean(rs):+.2f} | {np.sum(rs):+.2f}"


def report(rows, excl, seed, n_req):
    ok = [r for r in rows if "error" not in r]
    sig = [s for r in ok for s in r["signals"]]
    stp = [s for r in ok for s in r["stopped"]]
    L = ["# टप्पा B §4: IS मोजमाप (report-only)", "",
         f"**फक्त अहवाल; कोणताही आकडा निवडलेला नाही.** IS random {n_req} दिवस (seed {seed}, `data_policy` नेच; पूल {POOL[0]} → {POOL[1]}), "
         f"engine error {len(rows) - len(ok)}. Engine = टप्पा B (PAPER seed: target impulse_end, rr_filter ≥ 3, SL structural ∓ 0.25 MR, "
         "g10 shadow, gray block). तुलना 'A1-सारखं' = तोच SL, target 3R, rr filter नाही (A1 baseline ची व्याख्या). Spot निकाल ≤ 3 sessions; "
         "एकाच bar मध्ये SL + target ⇒ SL.", "",
         f"**वगळलेले दिवस ({len(excl)}):** A1 चे 40 (seed {A1_SEED}), K-10 run1 IS {', '.join(K10_RUN1_IS)}, 16 Feb 2018, 15 Nov 2021. "
         "A2 / A5 नी पूर्ण IS वापरलं (counter-moves / range कडा — दिवस-निहाय golden नाहीत).", "",
         "## 1. Signals आणि निकाल", "",
         "| गट | n | जिंकले | सरासरी R | एकूण R |", "|---|---|---|---|---|",
         f"| सगळे signals — A1-सारखं (3R, rr off) | {_stat([s['R_a1like'] for s in sig])} |",
         f"| PAPER seed (impulse_end, rr ≥ 3) — trades | {_stat([s['R_main'] for s in sig])} |",
         f"| Baseline A1 (40 दिवस, टप्पा A) | 17 | 3 | {A1_BASELINE_R:+.2f} | — |"]
    rnd = [x for s in sig for x in (s.get("R_random") or [])]
    L.append(f"| Baseline random-entry (प्रति signal {N_DRAWS} draws, 3R) | {_stat(rnd)} |")
    L += ["", f"Signals {len(sig)}; PAPER trade नाही याची कारणं: " + "; ".join(
        f"{k} ×{v}" for k, v in collections.Counter(str(s['plan_reason'])[:60] for s in sig if not s["plan_ok"]).most_common(6)), ""]
    L += ["## 2. S# नुसार (A1-सारखं निकाल)", "", "| S# | n | जिंकले | सरासरी R | एकूण R |", "|---|---|---|---|---|"]
    for k in sorted({str(s["S"]) for s in sig}):
        L.append(f"| {k} | {_stat([s['R_a1like'] for s in sig if str(s['S']) == k])} |")
    L += ["", "## 3. Gray: block वि. reduce (shadow)", "",
          "Block ⇒ trade नाही (0R). Reduce ⇒ GRAY खूण, gray_size half (spot निकाल R प्रति trade; size अर्धा ⇒ खात्यावर निम्मा). "
          "**मर्यादा:** Gray-1 चा उलट दिशेचा candidate engine तयार करत नाही ⇒ फक्त candidate दिशा.", "",
          "| gray प्रकार | थांबलेले | reduce trades | जिंकले | सरासरी R | एकूण R |", "|---|---|---|---|---|---|"]
    for g in ("Gray-1", "Gray-2"):
        xs = [s for s in stp if s["kind"] == "gray" and s["gray"] == g]
        L.append(f"| {g} | {len(xs)} | {_stat([s['R_reduce'] for s in xs])} |")
    blk = collections.Counter(s["why"].split(":")[0][:50] for s in stp if s["kind"] == "blocked")
    L += ["", "Blocked (gray नाही) कारणं: " + ("; ".join(f"{k} ×{v}" for k, v in blk.most_common(8)) or "—"), ""]
    g10 = [s for s in sig if s["setup"] == "G10"]
    L += ["## 4. G10 shadow (paper असता तर, 3R)", "", "| गट | n | जिंकले | सरासरी R | एकूण R |", "|---|---|---|---|---|",
          f"| sweep + reclaim | {_stat([s.get('R_g10_shadow') for s in g10 if (s.get('g10') or {}).get('sweep_reclaim')])} |",
          f"| sweep शिवाय | {_stat([s.get('R_g10_shadow') for s in g10 if not (s.get('g10') or {}).get('sweep_reclaim')])} |", ""]
    L += ["## 5. commit_vs_impulse (§2.1, फक्त report)", "",
          "Commitment range ÷ impulse मधल्या बंद 15M bars चा median range. सगळे signals = जुन्या gate ने (`commitment_vs_pause` 1.5 + "
          "`commit_strength_min_mr` 1.2) निवडलेले. **[प्रस्ताव]** स्तंभ फक्त संदर्भ — cut-off नाही, Abhi ठरवेल.", "",
          "| निकाल (A1-सारखं) | n | NA | median | p25 | p75 | [प्रस्ताव] ≥ 1.0 (n · सरासरी R) |", "|---|---|---|---|---|---|---|"]
    for res in ("TARGET", "SL", "TIME"):
        xs = [s for s in sig if s["res_a1like"] == res]
        v = [s["cvi"] for s in xs if s["cvi"] is not None]
        hi = [s["R_a1like"] for s in xs if s["cvi"] is not None and s["cvi"] >= 1.0]
        q = (lambda p: f"{np.percentile(v, p):.2f}") if v else (lambda p: "—")
        L.append(f"| {res} | {len(xs)} | {len(xs) - len(v)} | {q(50)} | {q(25)} | {q(75)} | {len(hi)} · "
                 f"{(np.mean(hi) if hi else float('nan')):+.2f} |")
    lo = [s["R_a1like"] for s in sig if s["cvi"] is not None and s["cvi"] < 1.0]
    L += [f"| (< 1.0 सगळे) | {len(lo)} | | | | | सरासरी R {(np.mean(lo) if lo else float('nan')):+.2f} |", ""]
    allc = sig + stp
    pu = [s for s in allc if not s.get("parent_count")]
    s3n = [s for s in sig if s.get("s3_code") == "S3_NO_1H_PIVOT"]
    L += ["## 6. PARENT_UNKNOWN आणि S3_NO_1H_PIVOT", "",
          f"- **PARENT_UNKNOWN** (`parent_source = preferred_count` असता तर trade नाही; default market_state मध्ये फक्त नोंद): "
          f"{len(pu)} / {len(allc)} candidates ({100 * len(pu) / max(1, len(allc)):.0f}%). त्यापैकी signals: "
          f"{sum(1 for s in sig if not s.get('parent_count'))} — A1-सारखं R: {_stat([s['R_a1like'] for s in sig if not s.get('parent_count')])}.",
          f"- **PARENT_CONFLICT** (market_state ≠ count sequence, नोंद): {sum(1 for s in sig if s.get('conflict'))} / {len(sig)} signals.",
          f"- **S3_NO_1H_PIVOT** (ढिला default: impulse मध्ये confirmed 1H pivot नाही ⇒ S1 / S2 म्हणून trade): {len(s3n)} / {len(sig)} signals — "
          f"A1-सारखं R: {_stat([s['R_a1like'] for s in s3n])}; बाकी signals: "
          f"{_stat([s['R_a1like'] for s in sig if s.get('s3_code') != 'S3_NO_1H_PIVOT'])}.", ""]
    agree = [s for s in allc if s.get("parent_count") and s.get("parent_ms")]
    L += ["## 7. §2.3 पालक दिशा: market_state वि. preferred_count", "",
          f"दोन्ही दिशा असलेले candidates {len(agree)}; जुळतात {sum(1 for s in agree if int(s['parent_count']) == int(s['parent_ms']))}; "
          f"count दिशा नाही (PARENT_UNKNOWN) {len(pu)}. Default market_state च (बदल Abhi). D0–D3 degree वेगळेपणा: A4b अहवाल (leg median).", ""]
    diff = [s for s in sig if s.get("waves_setup") != s.get("setup") and (s.get("waves_setup") or s.get("setup"))]
    L += ["## 8. §2.5 waves.py (तुलना) वि. एकच preferred count", "",
          f"Signals {len(sig)}; label वेगळं {len(diff)} — " + ("; ".join(f"waves.py {k[0]} → count {k[1]} ×{v}" for k, v in
          collections.Counter((s.get('waves_setup'), s.get('setup')) for s in diff).most_common(6)) or "—") +
          ". Trade / tier बदल: G9 tier full असल्याने label बदलाने size बदलत नाही; G1 / G9 wave refs (माहिती) फक्त count कडून.", ""]
    tied = [s for s in sig if s.get("count_tie")]
    gained = [s for s in sig if s.get("S11_alpha")]
    lab = [s for s in sig if (s.get("setup_alpha") or None) != (s.get("setup") if s.get("setup") in ("G1", "G9") else None)]
    L += ["## 10. I6 (7 Oct): count tie नियम — आधी / नंतर (I6.3–4)", "",
          "Count engine चा preferred score बरोबरीत असताना pattern-नावाच्या क्रमाने निवडला जात होता (counts.py tie-break). टप्पा B: tie ⇒ "
          "count-आधारित S11 / G1 / G9 नाहीत ('count tie' नोंद). खाली त्या बदलाचा IS वर परिणाम.", "",
          f"- Count tie असलेले candidates: {sum(1 for s in allc if s.get('count_tie'))} / {len(allc)}; signals {len(tied)}.",
          f"- Tie नियमामुळे **नवे** signals (जुन्या नियमाने S11 ⇒ थांबले असते): {len(gained)} — A1-सारखं R: "
          f"{_stat([s['R_a1like'] for s in gained])}.",
          f"- G1 / G9 label बदललेले signals: {len(lab)}.", ""]
    L += ["## 9. Gray मुळे सोडलेल्या संधी (नकाशा I4.5)", "",
          f"Gray-थांबलेले {sum(1 for s in stp if s['kind'] == 'gray')}; त्यापैकी reduce shadow मध्ये TARGET (R > 0): "
          f"{sum(1 for s in stp if s['kind'] == 'gray' and (s['R_reduce'] or 0) > 0)}. जास्त असेल तर नकाशात अपुरी परिस्थिती शोधायची (I6) — "
          "gray सैल करायचा नाही.", ""]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--days", type=int, default=200)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report", default=os.path.join(ROOT, "docs", "reports", "situation_map", "B_measure_IS.md"))
    a = ap.parse_args()
    raw = read(a.is_data)
    days, excl = sample_days(raw, a.days, a.seed)
    os.makedirs(a.out_dir, exist_ok=True)
    json.dump({"seed": a.seed, "days": [f"{d:%Y-%m-%d}" for d in days], "excluded": [f"{d:%Y-%m-%d}" for d in excl]},
              open(os.path.join(a.out_dir, "sample.json"), "w"), indent=1)
    rows = run(raw, days, a.out_dir)
    with open(a.report, "w", encoding="utf-8") as fh:
        fh.write(report(rows, excl, a.seed, a.days))


if __name__ == "__main__":
    main()
