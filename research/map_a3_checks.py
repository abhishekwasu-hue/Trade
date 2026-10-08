"""research/map_a3_checks.py — नकाशा A3 (I7, I6.7): चार केसेसवर नकाशाच्या अटी **decision bar ला जे माहीत होतं त्यावर**. आधी नकाशाचं उत्तर
(code ने मोजलेल्या तथ्यांवरून), मग decision bar वर कापलेले 1H + 15M charts (hindsight labels नाहीत). Charts + manifest ⇒ trade-data
`review/map/a3/` (Telegram "🗺 MAP CHECK", Approve नाही; Abhi ✔ / ✘).

    python3 research/map_a3_checks.py --is-data data/nifty50_1min.parquet --recent-data <csv.gz> --out-dir /root/trade-data/review/map/a3
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import breaks as BR                 # noqa: E402
from elliott import data_policy as DP            # noqa: E402
from elliott import settings as ES               # noqa: E402


def read(path):
    raw = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return DP.filter_allowed(raw, "golden")


def state_at(raw, bar_start):
    """bar_start चा 15M bar बंद झाल्यावर (asof = +15 min): market_state, trade frame, MR — फक्त तोपर्यंतचा data."""
    import market_state as MS
    from market_state import core as C
    asof = pd.Timestamp(bar_start) + pd.Timedelta(minutes=15)
    m1 = raw[(raw["timestamp"] >= asof - pd.Timedelta(days=70)) & (raw["timestamp"] < asof)]
    ms = MS.read(m1, asof, run_elliott=False)
    fr = C.frame(m1[m1["timestamp"] >= asof - pd.Timedelta(days=20)], "15m", asof)
    return ms, fr, BR.median_range(fr, 20), asof, m1


def _idx(fr, t):
    return int(np.searchsorted(pd.to_datetime(fr["timestamp"]).to_numpy(), np.datetime64(pd.Timestamp(t))))


def check_16feb(raw):
    ms, fr, mr, asof, _ = state_at(raw, "2018-02-16 09:30")
    imp = ms["impulse"]
    es = dict(ES.DEFAULTS)
    e, k = _idx(fr, imp["to_ts"]), len(fr) - 1
    d = imp["dir"]
    side = "above" if d < 0 else "below"
    b = BR.first_real_break(fr, e + 1, imp["from"], side, es, mr=mr, end=k)
    failed = None
    if b is not None:
        back = BR.first_real_break(fr, b + 1, imp["from"], "below" if d < 0 else "above", es, mr=mr, end=k)
        c = fr["close"].to_numpy(float)[b + 1:k + 1]
        old = bool(((c < imp["to"]) if d < 0 else (c > imp["to"])).any())
        failed = bool(back is not None or old)
    facts = {"impulse": f"{imp['from']:,.1f} → {imp['to']:,.1f} ({'down' if d < 0 else 'up'})", "origin": imp["from"],
             "origin_real_break": None if b is None else str(fr["timestamp"].iloc[b]), "break_failed_by_decision": failed,
             "trend": f"{ms['trend']['dir']} {ms['trend']['state']}"}
    if b is None:
        ans = "origin real-broken नाही ⇒ S3 / S1 प्रश्न (counter-move origin च्या आत)"
    elif failed:
        ans = "origin real-broken, पण 09:30 पर्यंत break अपयशी ⇒ जुना downtrend ⇒ S1 ⇒ area + commitment असेल तर bear setup शक्य"
    else:
        ans = "origin real-broken आणि 09:30 पर्यंत break अपयशी नाही ⇒ S4 ⇒ फक्त वरच्या दिशेने flip retest ⇒ bear नाही"
    return {"id": "2018-02-16 09:30", "date": "2018-02-16", "bar": "09:30", "facts": facts, "answer": ans, "levels": {"origin": imp["from"]}}


def check_15nov(raw):
    from market_state import core as C
    ms, fr, mr, asof, _ = state_at(raw, "2021-11-15 13:00")
    tr = ms["trend"]
    prot = (tr.get("protected") or {}).get("price")
    k = len(fr) - 1
    bts = tr.get("break_ts")
    o, h, lo, c = (fr[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    facts = {"trend": f"{tr['dir']} {tr['state']}", "protected": prot, "real_break_ts": None if bts is None else str(bts),
             "note": "real break तारीख market_state च्या HTF (1H) trend मधून"}
    if tr.get("state") != "testing" or bts is None:
        ans = "protected चा real break नाही ⇒ S4 नाही ⇒ G4 नाही"
        return {"id": "2021-11-15 13:00", "date": "2021-11-15", "bar": "13:00", "facts": facts, "answer": ans, "levels": {"protected": prot}}
    # retest leg = 13:00 मध्ये येणारा leg: decision bar आधी confirm झालेला शेवटचा trade-degree swing (up-trend तुटला ⇒ low) पासून
    kind = "L" if tr["dir"] > 0 else "H"
    sw = [p for p in C.pivots(fr, 3.0) if p["conf"] < k and p["kind"] == kind]
    j = sw[-1]["idx"] if sw else max(0, k - 12)
    ov = C.overlap_ratio(fr, j + 1, k)
    er = C.efficiency(fr, j, k)
    rng = max(h[k] - lo[k], 1e-9)
    upper_wick = (h[k] - max(o[k], c[k])) / rng
    cl = (c[k] - lo[k]) / rng
    corrective = bool(ov is not None and ov >= 0.6)                         # K10.1 correction overlap (A1 register: research)
    rejection = bool((c[k] < o[k]) and cl <= 0.3) if tr["dir"] > 0 else bool((c[k] > o[k]) and cl >= 0.7)
    facts.update(retest_from=str(fr["timestamp"].iloc[j]), retest_overlap=ov, retest_er=er, bar_upper_wick=round(upper_wick, 2),
                 bar_close_loc=round(cl, 2))
    ans = ("real break + retest corrective (overlap ≥ 0.6) + rejection ⇒ G4 bear" if corrective and rejection else
           f"G4 नाही: retest corrective {corrective}, rejection {rejection}")
    return {"id": "2021-11-15 13:00", "date": "2021-11-15", "bar": "13:00", "facts": facts, "answer": ans, "levels": {"protected": prot}}


def check_28sep(raw):
    from market_state import core as C
    ms, fr, mr, asof, _ = state_at(raw, "2026-09-28 14:15")
    imp = ms["impulse"]
    k = len(fr) - 1
    # breakout bar ने नवं टोक केलं ⇒ flag आधीचं टोक: k आधीचं impulse-दिशेचं टोक
    lo = fr["low"].to_numpy(float)
    s0 = _idx(fr, imp["from_ts"])
    e = s0 + int(np.argmin(lo[s0:k])) if imp["dir"] < 0 else s0 + int(np.argmax(fr["high"].to_numpy(float)[s0:k]))
    flag_bars = k - e - 1
    pv = [p for p in C.pivots(fr, 3.0) if p["conf"] <= k]
    legs = [abs(pv[i + 1]["price"] - pv[i]["price"]) for i in range(len(pv) - 1)
            if (pv[i + 1]["price"] - pv[i]["price"]) * imp["dir"] > 0][-3:]
    shrinking = bool(len(legs) == 3 and legs[0] > legs[1] > legs[2])
    disp = [i for i in range(s0, e + 1) if abs(fr["close"].iloc[i] - fr["open"].iloc[i]) >= 1.5 * mr[i]]
    base = None if not disp else (round(float(fr["low"].iloc[disp[-1]]), 1), round(float(fr["high"].iloc[disp[-1]]), 1))
    facts = {"impulse": f"{imp['from']:,.1f} → (flag आधी) {lo[e]:,.1f}", "flag_bars": int(flag_bars), "with_trend_legs_last3": [round(x) for x in legs],
             "legs_shrinking": shrinking, "broken_swing (impulse BOS)": imp.get("bos"), "last_displacement_base": base}
    g8 = 2 <= flag_bars <= 6
    s1 = s1_on_areas(raw, "2026-09-28", imp.get("bos"), base, disp[-1] if disp else None, fr)
    facts["S1_check"] = s1["summary"]
    ans = (("G8 रचना (2–6 candles) ✔" if g8 else f"G8 नाही: flag {flag_bars} candles (G8 = 2–6; व्याख्या बदलली नाही — G-MAP1)") + " · "
           + ("S8 (with-trend legs लहान होत आहेत)" if shrinking else "with-trend legs लहान होत नाहीत (S8 नाही)") + " · "
           + f"S1 म्हणून: area = तुटलेला swing {imp.get('bos')} / displacement base {base} ⇒ {s1['answer']}")
    return {"id": "2026-09-28 14:15", "date": "2026-09-28", "bar": "14:15", "facts": facts, "answer": ans,
            "levels": {k_: v for k_, v in (("broken_swing", imp.get("bos")),) if v}}


def s1_on_areas(raw, day, swing_px, base, base_bar, fr_dec):
    """28 Sep: नकाशा S1 — फक्त हे दोन areas (तुटलेला swing, displacement base) seller areas म्हणून; प्रत्येक बंद bar वर Simple Core
    (pause + commitment). Area चा जन्म: displacement base = त्या bar वर; तुटलेला swing = impulse ने तो तोडला तो bar (त्याआधी)."""
    from simple_core import engine as EN
    d = pd.Timestamp(day)
    m1 = raw[(raw["timestamp"] >= d - pd.Timedelta(days=130)) & (raw["timestamp"] < d + pd.Timedelta(days=1))].reset_index(drop=True)
    tr, rows, first = EN.Tracker(), [], None
    for t in pd.date_range(d + pd.Timedelta(hours=11, minutes=30), d + pd.Timedelta(hours=15, minutes=15), freq="15min"):
        r = EN.signal_at(m1, t + pd.Timedelta(minutes=15))
        trig = r["trig"]
        zs = []
        if swing_px is not None:
            zs.append({"id": "BRK-SWING", "zid": "S1a", "side": "sell", "role": "RESISTANCE", "tool": "e", "type": "तुटलेला swing", "kind": "solid",
                       "low": float(swing_px), "high": float(swing_px), "state": "FLIPPED"})
        if base is not None:
            ts_b = fr_dec["timestamp"].iloc[base_bar] if base_bar is not None else None
            bb = None if ts_b is None else int(np.searchsorted(pd.to_datetime(trig["timestamp"]).to_numpy(), np.datetime64(pd.Timestamp(ts_b))))
            zs.append({"id": "DISP-BASE", "zid": "S1b", "side": "sell", "role": "RESISTANCE", "tool": "c", "type": "displacement base",
                       "kind": "solid", "low": float(base[0]), "high": float(base[1]), "state": "ACTIVE", "bar": bb})
        ctx = {**(r.get("ctx") or {}), "side": -1}
        ctx.pop("impulse", None)                                          # S1 तपासणी: flag area नाही, फक्त हे दोन areas
        ctx.pop("pivots", None)                                           # wave1 flip area सुद्धा नाही
        x = EN.detect(trig, zs, ctx, r["mr"], None, tr)
        rows.append((f"{t:%H:%M}", x["why"][:70]))
        if x.get("signal") and first is None:
            first = (f"{t:%H:%M}", x["signal"]["area"]["id"], round(x["signal"]["trigger_price"], 1), x["signal"]["pause_bars"])
    whys = pd.Series([w for _, w in rows]).value_counts().head(3).to_dict()
    ans = (f"S1 bear signal {first[0]} (area {first[1]}, entry {first[2]:,.1f}, pause {first[3]})" if first else
           f"S1 म्हणून signal नाही — मुख्य कारणं {whys}")
    return {"answer": ans, "summary": {"first_signal": first, "why_top": whys, "per_bar": rows}}


def layer_22sep(rows):
    """22 Sep: कोणता थर चुकला — वाचन (area / trend / count नव्हता), निर्णय (नियमाने नाकारलं), अंमलबजावणी (bug)."""
    txt = " ".join(w for _, w, _ in rows)
    if "बाजू स्पष्ट नाही" in txt or "TESTING" in txt or "POSSIBLE_REVERSAL" in txt:
        return "निर्णय / वाचन: trend बाजू (testing / possible reversal) — पालक दिशा वाचनात"
    near = [n for _, _, n in rows if n is not None]
    if not near or min(near) > 1.0:
        return "वाचन: wave (4) end जवळ seller area नव्हता (area source सुटला — नकाशा S6: E / C-end चा area)"
    return "निर्णय: area होता, पण pause / commitment नियमाने नाकारलं (bar-निहाय कारणं पाहा)"


def check_22sep(raw):
    from simple_core import engine as EN
    from chart_reader import setups as SU
    d = pd.Timestamp("2026-09-22")
    m1 = raw[(raw["timestamp"] >= d - pd.Timedelta(days=130)) & (raw["timestamp"] < d + pd.Timedelta(days=1))].reset_index(drop=True)
    mem, tr = SU.LineMemory(), EN.Tracker()
    sig_bar, whys, rows = None, [], []
    for t in pd.date_range(d + pd.Timedelta(hours=9, minutes=15), d + pd.Timedelta(hours=15, minutes=15), freq="15min"):
        r = EN.signal_at(m1, t + pd.Timedelta(minutes=15), memory=mem, tracker=tr)
        whys.append(str(r.get("why"))[:60])
        hi = float(r["trig"]["high"].iloc[-1]) if r.get("trig") is not None and len(r["trig"]) else None
        sells = [z for z in r.get("zones") or [] if z.get("side") == "sell" and z.get("state") not in ("BROKEN", "DEAD", "MAGNET")]
        dist = (min(max(0.0, float(z["low"]) - hi, hi - float(z["high"])) for z in sells) / float(r["mr"])) if sells and hi and r.get("mr") else None
        rows.append((f"{t:%H:%M}", str(r.get("why"))[:70], None if dist is None else round(dist, 2)))
        if r.get("signal") and r["signal"]["side"] < 0:
            sig_bar = t
            break
    bar = sig_bar or (d + pd.Timedelta(hours=15))
    ms, fr, mr, asof, _ = state_at(raw, bar)
    corr = ms.get("correction") or {}
    labs = corr.get("labels") or []
    names = [x["label"] for x in labs]
    tent = [x["label"] for x in labs if x.get("tentative")]
    c_beyond_a = None
    if names[:3] == ["A", "B", "C"]:
        A, Cc = labs[0], labs[2]
        c_beyond_a = bool((Cc["to"] - A["to"]) * (1 if A["to"] > A["from"] else -1) >= 0)
    complete = bool(names[:3] == ["A", "B", "C"] and c_beyond_a and "C" not in tent)
    facts = {"code_signal": None if sig_bar is None else f"{sig_bar:%H:%M} bear", "decision_bar": f"{bar:%H:%M}",
             "impulse": None if not ms.get("impulse") else f"{ms['impulse']['from']:,.1f} → {ms['impulse']['to']:,.1f}",
             "correction_labels": names, "tentative": tent, "retrace": corr.get("retrace"), "C_reached_A_end": c_beyond_a,
             "code_why_top": pd.Series(whys).value_counts().head(3).to_dict(),
             "layer": layer_22sep(rows), "per_bar (वेळ, कारण, जवळच्या seller area चं अंतर MR)": rows}
    ans = ("wave (4) ची legs (A-B-C, C ने A चं टोक गाठलं) decision bar ला पूर्ण ⇒ Gray-2 नाही ⇒ G9 bear शक्य" if complete else
           "wave (4) ची legs decision bar ला पूर्ण दिसत नाहीत ⇒ Gray-2")
    return {"id": f"2026-09-22 {bar:%H:%M}", "date": "2026-09-22", "bar": f"{bar:%H:%M}", "facts": facts, "answer": ans, "levels": {}}


def charts(raw, case, out_dir):
    """15M (5 sessions) + 1H, decision bar वर कापलेले; levels आणि नकाशाचं उत्तर."""
    import plotly.graph_objects as go
    import market_state as MS
    from backtest_review import charts as BC
    t = pd.Timestamp(f"{case['date']} {case['bar']}") + pd.Timedelta(minutes=15)
    m1 = raw[(raw["timestamp"] >= t - pd.Timedelta(days=90)) & (raw["timestamp"] < t)]
    frames = MS.full_frames(m1)
    m15 = frames["15m"]
    m15 = m15[pd.to_datetime(m15["bar_end"]) <= t]
    days = sorted(pd.to_datetime(m15["timestamp"]).dt.normalize().unique())[-5:]
    d15 = m15[pd.to_datetime(m15["timestamp"]).dt.normalize().isin(days)].reset_index(drop=True)
    x = [s.strftime("%d %b %H:%M") for s in pd.to_datetime(d15["timestamp"])]
    fig = go.Figure(go.Candlestick(x=x, open=d15["open"], high=d15["high"], low=d15["low"], close=d15["close"],
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350"))
    for nm, v in (case.get("levels") or {}).items():
        if v is not None:
            fig.add_hline(y=float(v), line=dict(color="#f5c518", dash="dash"), annotation_text=f"{nm} {float(v):,.1f}")
    fig.add_annotation(x=x[-1], y=float(d15["high"].iloc[-1]), text="decision bar", showarrow=True, font=dict(color="#f5c518"))
    fig.update_layout(title=f"🗺 {case['id']} · 15M (decision bar पर्यंतच) · {case['answer'][:90]}", template="plotly_dark",
                      xaxis_rangeslider_visible=False, width=1400, height=800, showlegend=False, xaxis=dict(type="category", nticks=12))
    sub = os.path.join(out_dir, case["date"])
    os.makedirs(sub, exist_ok=True)
    fig.write_image(os.path.join(sub, "map_15m.png"), format="png", scale=1)
    ms = MS.read(m1, t, run_elliott=False, frames=frames)
    c = {"bar_end": t, "trend": ms["trend"], "impulse": ms["impulse"], "labels": (ms.get("correction") or {}).get("labels"), "zones": []}
    BC.context_1h(frames["1h"], c, f"🗺 {case['id']} · 1H (decision bar पर्यंत)",
                  m15_ts=pd.to_datetime(frames["15m"]["timestamp"]).to_numpy(dtype="datetime64[ns]")).write_image(
        os.path.join(sub, "map_1h.png"), format="png", scale=1)
    return [f"{case['date']}/map_1h.png", f"{case['date']}/map_15m.png"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--recent-data", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report", default=os.path.join(ROOT, "docs", "reports", "situation_map", "A3_map_checks.md"))
    a = ap.parse_args(argv)
    IS, RC = read(a.is_data), read(a.recent_data)
    cases = [(RC, check_22sep), (RC, check_28sep), (IS, check_16feb), (IS, check_15nov)]
    out, items = [], []
    for n, (raw, fn) in enumerate(cases, 1):
        case = fn(raw)
        case["files"] = charts(raw, case, a.out_dir)
        out.append(case)
        items.append({"n": n, "date": case["date"], "item": f"map/a3|day:{case['date']}",
                      "reading": f"{case['bar']} · नकाशाचं उत्तर: {case['answer']}\nतथ्ये: " + "; ".join(f"{k}={v}" for k, v in case["facts"].items()),
                      "files": case["files"]})
    json.dump({"run_id": "map/a3", "title": "🗺 MAP CHECK", "unit": "केस", "items": items},
              open(os.path.join(a.out_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    L = ["# नकाशा A3: decision-bar तपासणी (आधी नकाशाचं उत्तर, मग chart)", "",
         "Labels / तथ्ये फक्त decision bar पर्यंतच्या data वरून (breaks.py, market_state). Abhi ✔ / ✘ Telegram वर (🗺 MAP CHECK).", ""]
    for c in out:
        L += [f"## {c['id']}", "", f"**नकाशाचं उत्तर:** {c['answer']}", "", "| तथ्य | मूल्य |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in c["facts"].items()]
        L.append("")
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    open(a.report, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
