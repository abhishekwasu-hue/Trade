"""research/map_a6_sepoct_targets.py — Abhi Sep–Oct review (टप्पा A, फक्त अहवाल; settings बदल नाही):
  1(a) प्रत्येक signal: target_mode next_opposite_area (सध्याचं) वि. impulse_end — R:R आणि spot निकाल (rr_filter on आणि off दोन्ही);
  2    G9 signals (g9_tier रिकामा ⇒ trade नाही): "full / half असता तर" shadow निकाल (R × 1 / × 0.5); g9_tier setting भरलेलं नाही.
Signals = trade-data review/sept2026/run1/<date>/day.json (Simple Core, decision bar पर्यंतचं वाचन). Data: Jul–Oct 2026 (contaminated —
फक्त illustration, tuning नाही).

    python3 research/map_a6_sepoct_targets.py --run-dir /root/trade-data/review/sept2026/run1 --data <NIFTY_1m csv.gz>
"""
import argparse
import glob
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = {"rr_filter": True, "min_rr": 3, "sl_mode": "structural_invalidation", "sl_buffer": 0.25, "sl_buffer_unit": "mr",
        "target_mode": "next_opposite_area"}                                # K-10 round 2 dashboard settings (बदल नाही)
VARIANTS = {"next_opposite_area": {}, "impulse_end": {"target_mode": "impulse_end"}}


def r_mult(p, sim):
    if not p.get("ok") or sim.get("exit") is None or p.get("sl") is None:
        return None
    risk = abs(float(p["entry"]) - float(p["sl"]))
    return round((float(sim["exit"]) - float(p["entry"])) * int(p["side"]) / risk, 2) if risk > 0 else None


def run(run_dir, data):
    from chart_reader import evaluate as EV
    from chart_reader import measures as M
    from simple_core import execution as EX
    raw = pd.read_csv(data, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    rows = []
    for f in sorted(glob.glob(os.path.join(run_dir, "*", "day.json"))):
        d = json.load(open(f, encoding="utf-8"))
        day = pd.Timestamp(d["date"])
        for sig in d.get("signals") or []:
            t = day + pd.Timedelta(hours=int(sig["time"][:2]), minutes=int(sig["time"][3:]))
            asof = t + pd.Timedelta(minutes=15)
            trig = EV.frame(raw[raw["timestamp"] < asof], "15m", asof)
            mr = M.mr_now(trig)                                             # engine (signal_at) सारखंच
            full = EV.frame(raw, "15m", day + pd.Timedelta(days=5))
            after = full[pd.to_datetime(full["timestamp"]) > t]
            g9 = sig.get("setup") == "G9"
            rec = {"date": d["date"], "time": sig["time"], "side": sig["side"], "entry": sig["trigger_price"], "setup": sig.get("setup"),
                   "area": (sig.get("area") or {}).get("id"), "mr": round(float(mr), 2), "ref": sig.get("ref_levels") or {}}
            for vn, vx in VARIANTS.items():
                for rf in (True, False):
                    ex = {**BASE, **vx, "rr_filter": rf}
                    if g9:
                        ex["g9_tier"] = "C"                                 # फक्त shadow: setting भरलेलं नाही
                    p = EX.plan(sig, ex, mr, spot_only=True)
                    s = EX.simulate(p, after)
                    rec[f"{vn}|{'rr_on' if rf else 'rr_off'}"] = {"rr": p.get("rr"), "sl": p.get("sl"), "target": p.get("target"),
                                                                    "ok": p.get("ok"), "reason": p.get("reason"), "result": s.get("result"),
                                                                    "R": r_mult(p, s), "mfe": s.get("mfe"), "mae": s.get("mae")}
            rows.append(rec)
    return rows


def report(rows):
    L = ["# Sep–Oct 2026 signals: target degree तुलना + G9 shadow (Abhi review, टप्पा A)", "",
         "**फक्त अहवाल; settings बदल नाही.** Data contaminated (Jul–Oct 2026) ⇒ illustration, tuning नाही. SL = structural invalidation "
         "∓ 0.25 MR (सध्याचं). Spot निकाल ≤ 3 sessions (SL / target आधी; एकाच bar मध्ये दोन्ही ⇒ SL). R = (exit − entry) ÷ risk.", "",
         "## 1(a) target_mode: next_opposite_area (सध्याचं) वि. impulse_end", "",
         "| दिवस | वेळ | setup | entry | SL | next_opp target · R:R | impulse_end target · R:R | निकाल next_opp (rr off) | निकाल impulse_end (rr off) | "
         "impulse_end rr_filter on ⇒ trade? |", "|---|---|---|---|---|---|---|---|---|---|"]
    tot = {"next_opposite_area": [], "impulse_end": []}
    for r in rows:
        a, b = r["next_opposite_area|rr_off"], r["impulse_end|rr_off"]
        on = r["impulse_end|rr_on"]
        for k, v in (("next_opposite_area", a), ("impulse_end", b)):
            if v["R"] is not None:
                tot[k].append(v["R"])
        f = lambda v: "—" if v["target"] is None else f"{v['target']:,.1f} · {v['rr']}"          # noqa: E731
        g = lambda v: (f"{v['result']} {v['R']:+.2f}R" if v["R"] is not None else (v["reason"] or v["result"] or "—")[:50])  # noqa: E731
        L.append(f"| {r['date']} | {r['time']} | {r['setup'] or '—'} | {r['entry']:,.1f} | {'—' if a['sl'] is None else format(a['sl'], ',.1f')} | "
                 f"{f(a)} | {f(b)} | {g(a)} | {g(b)} | {'हो' if on['ok'] else 'नाही: ' + (on['reason'] or '')[:40]} |")
    L += ["", "| target_mode (rr_filter off, सगळे signals) | n | एकूण R | सरासरी R |", "|---|---|---|---|"]
    for k, v in tot.items():
        L.append(f"| {k} | {len(v)} | {sum(v):+.2f} | {(sum(v) / len(v) if v else 0):+.2f} |")
    L += ["", "**वाचन:** next_opposite_area सध्या चालू correction च्या आतला area निवडतो (उदा. 7 Oct: entry 22,648.9, target 22,626.6 — "
          "22 pts) ⇒ R:R < 1. Degree-सुसंगत व्याख्या (correction च्या आतले areas target नाहीत; target impulse end वर / पलीकडे, नकाशा P1) "
          "टप्पा B मध्ये — नवा आकडा नाही.",
          "**सावधानता:** impulse_end सुद्धा नेहमी योग्य degree चा नाही — 25 Sep (23,030.0, R:R 0.48) आणि 28 Sep (22,785.5, R:R 0.13) ला "
          "signal चा ref impulse हा अगदी अलीकडचा लहान impulse आहे. म्हणजे degree-सुसंगत target साठी 'कोणत्या degree चा impulse' हे "
          "नकाशा P1 प्रमाणे ठरायला हवं; फक्त target_mode बदलून पुरेसं नाही. n = 11, contaminated ⇒ निष्कर्ष नाही.", "",
          "## 2. G9 signals (g9_tier रिकामा ⇒ trade नाही): full / half असता तर (shadow)", "",
          "g9_tier setting भरलेलं नाही — Abhi ठरवेल. खाली फक्त 'असता तर': R × 1 (full) / × 0.5 (half), सध्याचा target_mode आणि impulse_end.", "",
          "| दिवस | वेळ | entry | target_mode | R:R | rr_filter on ⇒ trade? | निकाल | full | half |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["setup"] != "G9":
            continue
        for vn in VARIANTS:
            on, off = r[f"{vn}|rr_on"], r[f"{vn}|rr_off"]
            R = off["R"]
            L.append(f"| {r['date']} | {r['time']} | {r['entry']:,.1f} | {vn} | {off['rr']} | {'हो' if on['ok'] else 'नाही (R:R)'} | "
                     f"{off['result']} | {'—' if R is None else f'{R:+.2f}R'} | {'—' if R is None else f'{R * 0.5:+.2f}R'} |")
    L += ["", "**Label फरक — 7 Oct 12:15:** code ने G9 (wave 4 end ⇒ wave 5, retrace 41%, Tier C) म्हटलं; Abhi चा golden **G5 / S1 (C-end)**. "
          "म्हणजे 22,217.3 (1 Oct चा low) नंतरची rally code साठी wave 4, Abhi साठी correction चा C ⇒ 12:15 = C-end ⇒ S1. "
          "फरक count / degree चा (नकाशा P1 / P2); टप्पा B मध्ये golden म्हणून."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    a = ap.parse_args(argv)
    rows = run(a.run_dir, a.data)
    os.makedirs(a.out, exist_ok=True)
    md = report(rows)
    open(os.path.join(a.out, "A6_sepoct_targets.md"), "w", encoding="utf-8").write(md)
    json.dump(rows, open(os.path.join(a.out, "A6_sepoct_targets.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(md)


if __name__ == "__main__":
    main()
