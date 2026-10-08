"""research/chart_reader_funnel.py — Chart Reader निदान (report-only; settings / thresholds बदलत नाही — निर्णय Abhi चा).

  1. Funnel (संपूर्ण IS, 15m, प्रति आठवडा): (a) bars → (b) impulse + corrective pullback (zigzag/flat/triangle) → (c) pullback-end candidates →
     (d) ठोस area touch → (e) reversal ok → (f) व्हेटो पास → (g) R:R ≥ 3 → (h) grade A/B (+ बाकी पक्के नियम ⇒ entry). Unique setups सुद्धा.
  2. (b) का गळतं: correction प्रकार / legs वितरण, reversal कारणं; structure settings ची sensitivity (impulse_min_mr, swing_atr_mult,
     internal_atr_mult) — फक्त (a)→(c) मोजणी.
  3. "ठोस area touch नाही": साधनं (a–l) कोणती candidates बनवतात आणि वाटा; zone रुंदी (MR); touch नसलेल्या bars चं जवळच्या trade-बाजूच्या ठोस
     area पासून अंतर (MR); 10 random उदाहरणं chart सह ⇒ trade-data (public repo मध्ये नाही).
  4. R:R: invalidation (i) area दूरची कड + buffer / (ii) reversal composite टोक + buffer × target (i) पुढचा ठोस opposite area / (ii) impulse टोक
     ⇒ चारही संयोजनं: risk, reward (MR) वितरण, R:R ≥ 3 setups / आठवडा. सध्याचा नियम सुद्धा.

    python3 research/chart_reader_funnel.py [--examples-dir /home/user/trade-data/chart_reader/no_touch]
"""
import argparse
import collections
import json
import os
import random
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research"))
from chart_reader import areas as AR          # noqa: E402
from chart_reader import chart as CH          # noqa: E402
from chart_reader import evaluate as EV       # noqa: E402
from chart_reader import settings as CS       # noqa: E402
from chart_reader import structure as ST      # noqa: E402
from elliott import data_policy as DP         # noqa: E402
import market_state as MS                      # noqa: E402

REPORT = os.path.join(ROOT, "docs", "reports", "chart_reader_funnel.md")
OUT_JSON = os.path.join(ROOT, "data", "research", "chart_reader_funnel.json")
CORRECTIVE = ("zigzag", "flat", "triangle")


def window(m1, asof, days=90):
    t = pd.Timestamp(asof)
    return m1[(m1["timestamp"] >= t - pd.Timedelta(days=days)) & (m1["timestamp"] < t)].reset_index(drop=True)


def scan(trig, s, look=300, m1=None, frames=None):
    """(a)→(c): प्रत्येक 15m bar वर structure (शेवटचे `look` bars). frames (market_state.full_frames) दिले ⇒ C-V1: impulse / A-B-C /
    side market_state मधून (F1–F4; Elliott vote इथे नाही — candidates वरच्या evaluate मध्ये); नाहीतर जुना ad-hoc finder (--legacy)."""
    out = []
    for j in range(look, len(trig)):
        ms = MS.read(m1, trig["bar_end"].iloc[j], run_elliott=False, frames=frames) if frames is not None else None
        r = ST.read(trig.iloc[j - look:j + 1].reset_index(drop=True), s, ms=ms)
        side_unclear = ms is not None and ms["side"] == "unclear"
        out.append({"bar_end": trig["bar_end"].iloc[j], "impulse": r["impulse"] is not None, "ctype": r["correction_type"],
                    "legs": max(len(r["correction"]) - 1, 0), "pullback": r["pullback"], "reasons": r["reversal_reasons"],
                    "entry_point": None if side_unclear else r["entry_point"], "side_unclear": side_unclear,
                    "key": f"{r['side']}|{(r['impulse'] or {}).get('end')}"})
    return out


def q(x, ps=(0.1, 0.25, 0.5, 0.75, 0.9)):
    x = [v for v in x if v is not None and np.isfinite(v)]
    return [round(float(v), 2) for v in np.quantile(x, ps)] if x else []


def rr_variants(r):
    """चार संयोजनं: inv (area / candle) × target (nearest solid / impulse टोक). रिटर्न {combo: (risk_mr, reward_mr, rr)}."""
    side, mr = r["side"], r.get("mr") or 0
    a = (r.get("active") or {}).get("area")
    if not side or a is None or not mr:
        return {}
    rk = r.get("risk") or {}
    entry = rk.get("entry")
    buf = CS.DEFAULTS["inv_buffer_mr"] * mr
    comp = (r.get("reversal") or {}).get("comp")
    inv = {"area": (a["low"] - buf) if side > 0 else (a["high"] + buf)}
    if comp:
        inv["candle"] = (float(comp[2]) - buf) if side > 0 else (float(comp[1]) + buf)
    cands = (r.get("areas") or {}).get("candidates") or []
    near = AR.targets(cands, side, entry)
    tg = {"nearest_area": near[0][0] if near else None}
    trig_ext = r.get("_trend_extreme")
    tg["impulse_end"] = trig_ext if trig_ext is not None and ((trig_ext > entry) if side > 0 else (trig_ext < entry)) else None
    out = {}
    for ik, iv in inv.items():
        for tk, tv in tg.items():
            risk = abs(entry - iv)
            if tv is None or risk <= 0 or ((iv >= entry) if side > 0 else (iv <= entry)):
                out[f"{ik}×{tk}"] = (round(risk / mr, 2), None, None)
                continue
            rew = abs(tv - entry)
            out[f"{ik}×{tk}"] = (round(risk / mr, 2), round(rew / mr, 2), round(rew / risk, 2))
    out["सध्याचा"] = (round((rk.get("risk_pts") or 0) / mr, 2), None if not rk.get("targets") else round(abs(rk["targets"][0]["price"] - entry) / mr, 2),
                      None if rk.get("rr") is None else round(rk["rr"], 2))
    return out


def nearest_solid_mr(r, trig):
    """touch नसताना: शेवटच्या 3 bars पासून trade-बाजूच्या (role) जवळच्या ठोस area चं अंतर (MR)."""
    side, mr = r["side"], r.get("mr") or 0
    if not side or not mr:
        return None
    want = "SUPPORT" if side > 0 else "RESISTANCE"
    rec = trig.tail(3)
    lo, hi = float(rec["low"].min()), float(rec["high"].max())
    best = None
    for z in (r.get("areas") or {}).get("candidates") or []:
        if z.get("kind") != "solid" or z.get("role") != want or z.get("state") in AR.BAD or (z.get("tool") == "f" and not z.get("valid")):
            continue
        d = max(0.0, z["low"] - hi, lo - z["high"]) / mr
        best = d if best is None else min(best, d)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples-dir", default="/home/user/trade-data/chart_reader/no_touch")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--legacy", action="store_true", help="C-V1 आधीचा ad-hoc impulse finder (तुलनेसाठी)")
    ap.add_argument("--report", default=REPORT)
    a = ap.parse_args(argv)
    s = CS.load()
    m1 = DP.load_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"), "research")
    m1 = m1[m1["timestamp"] < DP._IS_END_X].reset_index(drop=True)
    trig = EV.frame(m1, "15m", m1["timestamp"].iloc[-1] + pd.Timedelta(minutes=1))
    weeks = (trig["bar_end"].iloc[-1] - trig["bar_end"].iloc[0]).days / 7.0
    res = {"weeks": round(weeks, 1), "settings": {k: s[k] for k in ("impulse_min_mr", "swing_atr_mult", "internal_atr_mult", "impulse_lookback_legs",
                                                                       "zigzag_b_max", "flat_b_min", "flat_c_min", "retrace_max", "disp_bars_reversal")}}
    t0 = time.time()
    frames = None if a.legacy else MS.full_frames(m1)
    res["mode"] = "legacy (C-V1 आधी)" if a.legacy else "C-V1 market_state (F1–F4)"
    sc = scan(trig, s, m1=m1, frames=frames)
    res["scan_sec"] = round(time.time() - t0, 1)
    pw = lambda n: round(n / weeks, 2)                                    # noqa: E731
    n_a = len(sc)
    n_imp = sum(x["impulse"] for x in sc)
    n_b = sum(x["impulse"] and x["ctype"] in CORRECTIVE and x["pullback"] == "pullback" for x in sc)
    cand = [x for x in sc if x["entry_point"]]
    res["b_detail"] = {"impulse_found_pct": round(100 * n_imp / n_a, 1),
                       "ctype_pct": {k: round(100 * v / max(n_imp, 1), 1) for k, v in collections.Counter(x["ctype"] for x in sc if x["impulse"]).most_common()},
                       "pullback_pct": {k: round(100 * v / max(n_imp, 1), 1) for k, v in collections.Counter(x["pullback"] for x in sc if x["impulse"]).most_common()},
                       "reasons_pct": {k: round(100 * v / max(n_imp, 1), 1) for k, v in collections.Counter(r for x in sc for r in x["reasons"]).most_common()},
                       "legs_quantiles": q([x["legs"] for x in sc if x["impulse"]]),
                       "legs_gt5_pct": round(100 * sum(x["legs"] > 5 for x in sc if x["impulse"]) / max(n_imp, 1), 1)}
    # sensitivity (फक्त a→c)
    sens = {}
    for name, ov in () if not a.legacy else (("impulse_min_mr 4", {"impulse_min_mr": 4.0}), ("swing_atr_mult 2", {"swing_atr_mult": 2.0}),
                     ("internal_atr_mult 1.0", {"internal_atr_mult": 1.0}), ("impulse_lookback_legs 4", {"impulse_lookback_legs": 4})):
        s2 = CS.load(ov)
        sub = scan(trig, s2)
        sens[name] = {"candidates_per_week": pw(sum(bool(x["entry_point"]) for x in sub)),
                      "unique_per_week": pw(len({x["key"] for x in sub if x["entry_point"]})),
                      "corrective_per_week": pw(sum(x["impulse"] and x["ctype"] in CORRECTIVE and x["pullback"] == "pullback" for x in sub))}
    res["sensitivity"] = sens
    res["side_unclear_pct"] = round(100 * sum(x.get("side_unclear", False) for x in sc if x["impulse"]) / max(n_imp, 1), 1)
    # (d)→(h): candidates वर पूर्ण evaluate
    rows, ev = [], []
    t0 = time.time()
    for x in cand:
        t = x["bar_end"]
        w = window(m1, t)
        r = EV.evaluate(w, "srv2", t, s=s)
        tw = EV.frame(w, "15m", t)
        r["_trend_extreme"] = EV.trend_extreme(tw, r.get("structure") or {}, r["side"])
        touch = (r.get("active") or {}).get("area") is not None
        rv_ok = (r.get("reversal") or {}).get("status") == "ok"
        veto_ok = not r.get("vetoes")
        rr = (r.get("risk") or {}).get("rr")
        row = {"asof": str(t), "key": x["key"], "side": r["side"], "touch": touch, "rv_ok": rv_ok, "veto_ok": veto_ok,
               "rr_ok": rr is not None and rr >= s["min_rr"], "ab": r["grade"] in "AB", "entry": r["entry"],
               "tool": ((r.get("active") or {}).get("area") or {}).get("tool"), "rr": rr,
               "variants": rr_variants(r), "no_touch_dist": None if touch else nearest_solid_mr(r, tw),
               "zone_w": None if not touch else round((r["active"]["area"]["high"] - r["active"]["area"]["low"]) / r["mr"], 2),
               "by_tool": (r.get("areas") or {}).get("by_tool"), "touched_tools": sorted({z.split("-")[0] for z in (r.get("active") or {}).get("touched_ids", [])})}
        rows.append(row)
        ev.append((t, r, tw))
    res["eval_sec"] = round(time.time() - t0, 1)
    # funnel
    stages = [("a 15M bars", n_a), ("b impulse + corrective pullback", n_b), ("c pullback-end candidates", len(cand))]
    cur = rows
    for name, f in (("d ठोस area touch", "touch"), ("e reversal ok", "rv_ok"), ("f व्हेटो पास", "veto_ok"), ("g R:R ≥ 3", "rr_ok"), ("h grade A/B", "ab")):
        cur = [r for r in cur if r[f]]
        stages.append((name, len(cur)))
    stages.append(("entry (बाकी पक्के नियम सुद्धा)", sum(r["entry"] for r in rows)))
    uniq = lambda rs: len({r["key"] for r in rs})                         # noqa: E731
    res["funnel"] = [{"stage": n, "bars": c, "per_week": pw(c)} for n, c in stages]
    res["unique"] = {"c": len({x["key"] for x in cand}), "h": uniq([r for r in rows if r["touch"] and r["rv_ok"] and r["veto_ok"] and r["rr_ok"] and r["ab"]]),
                     "entry": uniq([r for r in rows if r["entry"]])}
    # tools
    tools_cnt = collections.Counter()
    for r in rows:
        for k, v in (r["by_tool"] or {}).items():
            tools_cnt[k] += v
    res["tools"] = {"avg_candidates_per_bar": {k: round(tools_cnt[k] / max(len(rows), 1), 2) for k in "abcdefghijkl"},
                    "active_area_tool_pct": {k: round(100 * v / max(sum(r["touch"] for r in rows), 1), 1)
                                             for k, v in collections.Counter(r["tool"] for r in rows if r["touch"]).most_common()},
                    "zone_width_mr": q([r["zone_w"] for r in rows]), "no_touch_pct": round(100 * sum(not r["touch"] for r in rows) / max(len(rows), 1), 1),
                    "no_touch_dist_mr": q([r["no_touch_dist"] for r in rows]),
                    "no_touch_within": {f"≤{d} MR": round(100 * np.mean([r["no_touch_dist"] is not None and r["no_touch_dist"] <= d
                                                                          for r in rows if not r["touch"]]), 1) for d in (0.25, 0.5, 1.0, 2.0)}}
    # R:R combos
    combos = collections.defaultdict(list)
    for r in rows:
        for k, v in r["variants"].items():
            combos[k].append((r, v))
    rrr = {}
    for k, lst in combos.items():
        ok = [r for r, v in lst if v[2] is not None and v[2] >= s["min_rr"]]
        rrr[k] = {"n": len(lst), "risk_mr": q([v[0] for _, v in lst]), "reward_mr": q([v[1] for _, v in lst]), "rr": q([v[2] for _, v in lst]),
                  "rr_ge3_pct": round(100 * len(ok) / max(len(lst), 1), 1),
                  "setups_per_week_all_other_stages": pw(uniq([r for r in ok if r["rv_ok"] and r["veto_ok"] and r["ab"]]))}
    res["rr_combos"] = rrr
    # examples (touch नाही)
    nt = [e for e, r in zip(ev, rows) if not r["touch"]]
    random.Random(a.seed).shuffle(nt)
    os.makedirs(a.examples_dir, exist_ok=True)
    ex = []
    for t, r, tw in nt[:10]:
        img = CH.png(tw, r)
        name = f"no_touch_{pd.Timestamp(t):%Y%m%d_%H%M}.png"
        if img:
            open(os.path.join(a.examples_dir, name), "wb").write(img)
        ex.append({"asof": str(t), "side": r["side"], "png": name if img else None, "dist_mr": nearest_solid_mr(r, tw),
                   "story": r["story"][:4]})
    res["examples"] = ex
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump({**res, "rows": rows}, open(OUT_JSON, "w"), ensure_ascii=False, default=str, indent=1)
    res["golden_sl"] = golden_sl_example(s)
    write_md(res, a.report)
    print(json.dumps({"funnel": res["funnel"], "unique": res["unique"], "sens": sens}, ensure_ascii=False, default=str))
    return 0


def golden_sl_example(s):
    """§4 (C-V1): 7 Oct 14:30 (SIM entry 22,620) — reversal-candle SL वि. structural SL. Contaminated ⇒ फक्त illustration."""
    p = os.path.join(os.environ.get("TRADE_DATA", "/home/user/trade-data"), "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz")
    if not os.path.exists(p):
        return None
    from vision_led import validate as VA
    g = DP.filter_allowed(pd.read_csv(p, parse_dates=["timestamp"]), "golden")
    t = pd.Timestamp("2026-10-07 14:45")                                 # 14:30 bar बंद
    r = EV.evaluate(g[g["timestamp"] >= t - pd.Timedelta(days=90)], "srv2", t, s=s)
    trig = EV.frame(g, "15m", t)
    area = (r.get("active") or {}).get("area")
    entry, target = float(trig["close"].iloc[-1]), 22400.0
    sl = VA.sl_definitions(-1, entry, target, trig, area, float(r["mr"]), VA.DEFAULTS)
    return {"asof": str(t), "entry": round(entry, 2), "target": target, "area": (area or {}).get("id"), "mr": r["mr"], "sl": sl,
            "code_side": (r.get("market_state") or {}).get("side"), "code_rr": r.get("rr"), "code_inv": r.get("invalidation")}


def write_md(res, report=REPORT):
    L = ["# Chart Reader — funnel, साधनं, R:R निदान (report-only)", "",
         f"> IS 2015–2021, 15m, SRv2 profile, {res['weeks']} आठवडे, mode: **{res.get('mode')}**. Settings/thresholds बदलले नाहीत: "
         f"{res['settings']}.", "",
         "## 1. Funnel (प्रति आठवडा सरासरी)", "", "| पायरी | bars | / आठवडा | मागच्या पायरीतून टिकले |", "|---|---|---|---|"]
    prev = None
    for f in res["funnel"]:
        keep = "—" if prev in (None, 0) else f"{100 * f['bars'] / prev:.1f}%"
        L.append(f"| {f['stage']} | {f['bars']:,} | {f['per_week']} | {keep} |")
        prev = f["bars"]
    L += ["", f"Unique setups (एकाच correction चे सलग bars एक): candidates {res['unique']['c']}, A/B (a–h) {res['unique']['h']}, entries {res['unique']['entry']}.",
          "", "## 2. (b) का गळतं — structure", "", f"- Impulse सापडला: {res['b_detail']['impulse_found_pct']}% bars",
          f"- Correction प्रकार (impulse असलेल्या bars): {res['b_detail']['ctype_pct']}",
          f"- Pullback label: {res['b_detail']['pullback_pct']} · reversal कारणं: {res['b_detail']['reasons_pct']}",
          f"- Correction legs (p10/p25/p50/p75/p90): {res['b_detail']['legs_quantiles']} · > 5 legs (\"complex\"): {res['b_detail']['legs_gt5_pct']}%",
          f"- F4 side unclear (impulse असलेल्या bars): {res.get('side_unclear_pct', '—')}%", "",
          "Sensitivity (फक्त माहिती, settings बदलले नाहीत):", "", "| बदल | corrective / आठवडा | candidates bars / आठवडा | unique / आठवडा |", "|---|---|---|---|"]
    for k, v in res["sensitivity"].items():
        L.append(f"| {k} | {v['corrective_per_week']} | {v['candidates_per_week']} | {v['unique_per_week']} |")
    t = res["tools"]
    L += ["", "## 3. ठोस area touch", "", f"- Touch नाही: {t['no_touch_pct']}% candidates",
          f"- सरासरी candidates / bar (साधन a–l): {t['avg_candidates_per_bar']}", f"- Active area कोणत्या साधनाचा: {t['active_area_tool_pct']}",
          f"- Active zone रुंदी (MR, p10…p90): {t['zone_width_mr']}",
          f"- Touch नसताना जवळच्या trade-बाजूच्या ठोस area पर्यंत अंतर (MR, p10…p90): {t['no_touch_dist_mr']} · {t['no_touch_within']}",
          "- Touch व्याख्या: शेवटच्या 3 बंद bars पैकी एकाची high–low पट्टी zone ला छेदते (अतिरिक्त tolerance नाही); zone रुंदी साधनानुसार: "
          "trendline ± 0.2 MR, round / PDH-PDL ± 0.25 MR, swing / equal pools ± 0.1 MR, HTF levels (levels_v2) ± 0.25 HTF-MR (किमान 0.5 HTF-MR).", "",
          "10 उदाहरणं (charts trade-data मध्ये, `chart_reader/no_touch/`):", ""]
    L += [f"- {e['asof']} · बाजू {e['side']:+d} · जवळचा area {e['dist_mr'] if e['dist_mr'] is None else round(e['dist_mr'], 2)} MR · `{e['png']}`"
          for e in res["examples"]]
    L += ["", "## 4. R:R — चार संयोजनं (risk, reward MR मध्ये; p10/p25/p50/p75/p90)", "",
          "| invalidation × target | n | risk MR | reward MR | R:R | R:R ≥ 3 % | setups / आठवडा (बाकी पायऱ्या पास) |", "|---|---|---|---|---|---|---|"]
    for k, v in res["rr_combos"].items():
        L.append(f"| {k} | {v['n']} | {v['risk_mr']} | {v['reward_mr']} | {v['rr']} | {v['rr_ge3_pct']} | {v['setups_per_week_all_other_stages']} |")
    L += ["", "- area = active area ची दूरची कड + 0.25 MR · candle = reversal composite चं टोक + 0.25 MR · nearest_area = पुढचा ठोस opposite area "
          "(सगळी साधनं) · impulse_end = impulse सुरू झाल्यापासूनचं trade-दिशेचं टोक. सध्याचा = तिन्हीपैकी दूरची invalidation (area / candle / correction "
          "टोक) × impulse टोक + पलीकडचे HTF areas."]
    gs = res.get("golden_sl")
    if gs:
        sl = gs["sl"]
        L += ["", "## 5. 7 Oct 14:30 उदाहरण — SL च्या दोन व्याख्या (contaminated, फक्त illustration)", "",
              f"- Entry {gs['entry']:,.1f} (14:30 bar close), target {gs['target']:,.0f} (Abhi चं उदाहरण), active area {gs['area']}, "
              f"MR {gs['mr']}, code side {gs['code_side']}.",
              "| व्याख्या | संदर्भ | SL (+0.25 MR) | R:R |", "|---|---|---|---|",
              f"| reversal-candle SL (14:15/14:30 high) | {sl['candle']['ref']:,.1f} | {sl['candle']['inv']:,.1f} | "
              f"{'1:%.1f' % sl['candle']['rr'] if sl['candle'].get('rr') else '—'} |"]
        if sl.get("structural"):
            L.append(f"| structural SL (active area / trendline पलीकडे) | {sl['structural']['ref']:,.1f} | {sl['structural']['inv']:,.1f} | "
                     f"{'1:%.1f' % sl['structural']['rr'] if sl['structural'].get('rr') else '—'} |")
        L += ["", "- खरा rejection 22,710–22,718 (उतरती trendline / 22,700–22,730) वर होता ⇒ idea तिथे चुकीची ठरते ⇒ structural SL. "
              "Candle SL ने R:R फुगतो (SIM मध्ये 1:7) पण तो structural कारणाशिवाय tight आहे; structural SL ने याच entry वर R:R < 3 ⇒ A3 नुसार entry नाही "
              "(योग्य entry 12:00–12:30 च्या rejection वेळी होती)."]
    os.makedirs(os.path.dirname(report), exist_ok=True)
    open(report, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
