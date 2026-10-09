"""research/map_b_i7.py — नकाशा I7 (Abhi ची उदाहरणं) टप्पा B engine वर: decision bar पर्यंतच्या data वर code चं उत्तर वि. नकाशाचं उत्तर.

PROVISIONAL (Phase B §5): case fail ⇒ नकाशा I6 प्रक्रिया (कोणता थर: वाचन / निर्णय / अंमलबजावणी) आणि अहवाल — constants बदलून pass नाही.
दिवसाचा 15M replay (LineMemory + Tracker, K-10 सारखा) decision bar पर्यंत; त्या bar चा signal / gray / blocked candidate आणि reading नोंद.
Jul–Oct 2026 = illustration; 2018 / 2021 = IS (data_policy नेच).

    python3 research/map_b_i7.py --is-data data/nifty50_1min.parquet --recent-data <csv.gz> --out docs/reports/situation_map --json-out <dir>
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP            # noqa: E402

# (दिवस, decision bar, नकाशाचं उत्तर: "none" / "bear" / "bull" / "check", I7 परिस्थिती)
CASES = [
    ("2026-08-12", "10:15", "none", "S3: 5-wave घसरण, reaction सुरू नाही ⇒ bull put नाही (Gray-1 / Gray-2 / पालक)"),
    ("2026-08-25", "10:45", "none", "S3 reaction चालू ⇒ Gray-1 ⇒ buy नाही"),
    ("2026-08-26", None, "bear", "S3 reaction corrective, flip ओलांडली नाही ⇒ पालक खाली ⇒ bear call"),
    ("2026-08-31", None, "none", "wave (3) चालू; commitment कमकुवत / R:R < 3 ⇒ नाही"),
    ("2026-09-22", "15:00", "bear", "S6: wave (4) end ⇒ G9 bear call"),
    ("2026-09-28", "14:15", "bear", "S1 bear (flag 11 candles ⇒ G8 नाही)"),
    ("2026-10-07", "09:30", "none", "S10-B: trend दिशेचा gap, pullback नाही ⇒ chase नाही"),
    ("2026-10-07", "12:15", "bear", "S10-B → S1: C-diagonal + seller zone ⇒ G5 bear call (Abhi ✔ 2026-10-09: 12:15 = C-end)"),
    ("2018-02-16", "13:30", "none", "S4 MAGNET ⇒ setup नाही"),
    ("2018-02-16", "09:30", "check", "आधीची चाल 144% ⇒ S4 (break अपयशी ⇒ S1 शक्य) — नकाशाची अट"),
    ("2021-11-15", "13:00", "check", "S4 testing: break real + retest corrective + rejection ⇒ G4 bear; नाहीतर नाही"),
]


# I6 पायरी 2 (कोणता थर) — decision bar पर्यंतच्या data वरून हाताने तपासलेलं (zones / bars probe). दुरुस्ती नाही; Abhi ला प्रश्न.
I6_NOTES = {
    ("2026-09-22", "15:00"): [
        "थर = **निर्णय (Simple Core commitment gate)**, reading layer नाही: (4) चं टोक 23,489 (09:15) / area RN23500 flip; 10:15 ची bear "
        "commitment (range 34.6) `commitment_vs_pause` 1.5 × pause सरासरी 30.6 पेक्षा लहान ⇒ नाकारली. नंतरचे bars area पासून दूर (chase नियम).",
        "`commit_vs_impulse` (§2.1, फक्त report): impulse 23,592.8 (15 Sep 09:15) → 23,116.1 (16 Sep 09:45), 27 bars median range 33.3 ⇒ "
        "10:15 ला 34.6 / 33.3 = **1.04** — [प्रस्ताव] ≥ 1.0 स्तंभात हा signal असता. G-MAP1 निर्णय 1 चा प्रश्न (Abhi), gate बदल नाही.",
    ],
    ("2026-09-28", "14:15"): [
        "थर = **वाचन (area, P5)**: नकाशाचा S1 area = तुटलेला swing 23,021 (zones मध्ये PDL / PWL flip 23,014–23,028 म्हणून आहे, पण 6.9 MR "
        "दूर) आणि displacement base 22,856–22,912 — हा base **zones यादीत नाही** (tool c ने तयार केला नाही). Pause 13:15–14:00 "
        "(22,818–22,848) च्या जवळचा फक्त SWH-1523 liquidity (22,853–22,858, 0.99 MR) — commitment 14:15 त्याला लागलेली नाही ⇒ 'दूर'.",
        "पुढची पायरी (I6.3): 'displacement base' tool c चे IS look-alike संच; constants बदल नाही. Abhi ✔ (A3 MAP CHECK) बाकी.",
    ],
    ("2026-10-07", "12:15"): [
        "Abhi ✔ (2026-10-09, run2 review): 12:15 = C-end, bear call बरोबर ⇒ golden पक्का.",
        "थर = **वाचन (count ranking)**: impulse 22,809.35 → 22,217.3 आणि legs (A-B-C, C ने A गाठलं) नकाशाशी जुळतात; पालक खाली ✔. "
        "पण D3 वर beam मधले counts (flat/B, impulse/2, wxy/X, zigzag/B, flat/A) **सगळे score 0.5 — बरोबरी**; counts.py चा sort tie-break "
        "pattern च्या नावाने ⇒ 'preferred' = flat/B ⇒ S11. म्हणजे पसंती नव्हतीच.",
        "दुरुस्ती त्याच थरात (I6.2): score tie ⇒ count-आधारित S11 / G1 / G9 नाहीत ('count tie' नोंद). Constants बदल नाही. IS वर आधी / नंतर "
        "परिणाम: §4 अहवाल विभाग 10 (I6.3–4).",
    ],
}


def read(path, purpose):
    raw = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return DP.filter_allowed(raw, purpose)


def replay(raw, day, until=None, window_days=130):
    """दिवसाचा 15M replay ⇒ [(वेळ, r)] (until दिलं तर त्या bar पर्यंत)."""
    from chart_reader import setups as SU
    from simple_core import engine as EN
    from simple_core import settings as SS
    d = pd.Timestamp(day)
    m1 = raw[(raw["timestamp"] >= d - pd.Timedelta(days=window_days)) & (raw["timestamp"] < d + pd.Timedelta(days=1))]
    mem, tr = SU.LineMemory(), EN.Tracker()
    s = {k: v for k, v in SS.PAPER_SEED.items() if k in SS.ENGINE_FROM_PROFILE}
    end = pd.Timestamp(f"{day} {until or '15:15'}")
    out = []
    for t in pd.date_range(d + pd.Timedelta(hours=9, minutes=15), end, freq="15min"):
        out.append((t, EN.signal_at(m1, t + pd.Timedelta(minutes=15), s=s, memory=mem, tracker=tr)))
    return out


def brief(t, r):
    c = r.get("signal") or r.get("gray_candidate") or r.get("blocked_candidate")
    rd = (c or {}).get("reading") or r.get("reading") or {}
    imp = rd.get("impulse") or {}
    cnt = rd.get("count") or {}
    pref = cnt.get("preferred") or {}
    return {"t": f"{t:%H:%M}", "signal": bool(r.get("signal")), "side": (c or {}).get("side"), "setup": (c or {}).get("setup"),
            "why": str(r.get("why"))[:140], "S": rd.get("S"), "flags": rd.get("flags"), "gray": rd.get("gray"),
            "impulse": (imp.get("start"), imp.get("end")) if imp else None, "impulse_na": rd.get("impulse_na"),
            "legs_why": (rd.get("legs") or {}).get("why"), "s3": (rd.get("s3") or {}).get("code") or ((rd.get("s3") or {}).get("s3")),
            "count": f"D{cnt.get('degree')} {pref.get('pattern')}/{pref.get('wave')}" if pref else cnt.get("why"),
            "parent_ms": rd.get("parent_ms"), "parent_count": rd.get("parent_count"),
            "impulse_end": ((c or {}).get("ref_levels") or {}).get("impulse_end"),
            "next_opp": ((c or {}).get("ref_levels") or {}).get("next_opposite_area")}


def verdict(expect, bars, until):
    """नकाशाचं उत्तर वि. code: decision bar दिलेला ⇒ त्या bar चा; नाहीतर दिवसभरातले signals."""
    sigs = [b for b in bars if b["signal"]] if until is None else [b for b in bars[-1:] if b["signal"]]
    sides = {(-1 if b["side"] < 0 else 1) for b in sigs if b["side"]}
    if expect == "check":
        return "Abhi ✔/✘ (अट तपासून उत्तर)"
    if expect == "none":
        return "जुळतं" if not sigs else "FAIL (code signal देतो)"
    want = -1 if expect == "bear" else 1
    if want in sides:
        return "जुळतं"
    return "FAIL (code signal नाही)" if not sigs else "FAIL (उलट दिशा)"


def run(is_raw, recent_raw, log=print):
    rows = []
    for day, until, expect, story in CASES:
        raw = is_raw if pd.Timestamp(day) < DP.CONTAMINATED_START else recent_raw
        if raw is None or not len(raw):
            rows.append({"day": day, "until": until, "expect": expect, "story": story, "error": "data नाही"})
            continue
        bars = [brief(t, r) for t, r in replay(raw, day, until)]
        rows.append({"day": day, "until": until, "expect": expect, "story": story, "bars": bars, "verdict": verdict(expect, bars, until)})
        log(f"  {day} {until or 'दिवस'}: {rows[-1]['verdict']}")
    return rows


def report(rows):
    L = ["# टप्पा B: नकाशा I7 उदाहरणं (PROVISIONAL)", "",
         "**फक्त अहवाल.** टप्पा B engine (PAPER seed) — दिवसाचा 15M replay decision bar पर्यंत, फक्त त्या वेळेपर्यंतचा data. "
         "नकाशाचं उत्तर (KB I7) आधी, code चं उत्तर नंतर. FAIL ⇒ I6 प्रक्रिया: कोणता थर (वाचन / निर्णय / अंमलबजावणी) — constants बदलून pass "
         "करायचं नाही. Jul–Oct 2026 = illustration; 2018 / 2021 = IS.", "",
         "| दिवस | bar | नकाशा | code (त्या bar ला / दिवसभर) | S# · gray | impulse | count | निकाल |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            L.append(f"| {r['day']} | {r['until'] or '—'} | {r['expect']} | {r['error']} | | | | |")
            continue
        b = r["bars"][-1] if r["until"] else next((x for x in r["bars"] if x["signal"]), r["bars"][-1])
        code = (f"SIGNAL {'bear' if (b['side'] or 0) < 0 else 'bull'} {b['setup'] or ''} ({b['t']})" if b["signal"]
                else f"नाही ({b['t']}): {b['why'][:70]}")
        imp = f"{b['impulse'][0]:,.1f} → {b['impulse'][1]:,.1f}" if b["impulse"] else (b["impulse_na"] or "—")[:40]
        L.append(f"| {r['day']} | {r['until'] or 'दिवस'} | {r['expect']} | {code} | {b['S']} · {b['gray'] or '—'} | {imp} | {b['count']} | "
                 f"**{r['verdict']}** |")
    L += ["", "## I6: FAIL केसेस (आणि I6 ने सुटलेले) — कोणता थर", ""]
    for r in rows:
        if "FAIL" not in str(r.get("verdict")) and (r["day"], r["until"]) not in I6_NOTES:
            continue
        L.append(f"### {r['day']} {r['until'] or ''} — {r['story']} · आता: **{r.get('verdict')}**")
        L += [f"- {x}" for x in I6_NOTES.get((r["day"], r["until"]), [])]
        L.append("- bar-निहाय (शेवटचे):")
        for b in r["bars"][-6:] if r["until"] else [x for x in r["bars"] if x["signal"] or x["gray"]][:6]:
            L.append(f"  - {b['t']}: {'SIGNAL' if b['signal'] else 'नाही'} · {b['why'][:110]} · S {b['S']} {b['flags'] or ''} · gray {b['gray']} · "
                     f"legs {b['legs_why']} · S3 {b['s3']} · count {b['count']} · पालक ms {b['parent_ms']} / count {b['parent_count']}")
        L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default="data/nifty50_1min.parquet")
    ap.add_argument("--recent-data", default=None)
    ap.add_argument("--out", default="docs/reports/situation_map")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    is_raw = read(a.is_data, "research")
    recent = read(a.recent_data, "golden") if a.recent_data else None
    rows = run(is_raw, recent)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "B_I7_cases.md"), "w") as f:
        f.write(report(rows))
    if a.json_out:
        os.makedirs(a.json_out, exist_ok=True)
        with open(os.path.join(a.json_out, "B_I7_cases.json"), "w") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
