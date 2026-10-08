"""backtest_review/gallery.py — Golden Gallery G1–G6 (KB भाग H; TRADE_GOLDEN_GALLERY_PROMPT). Code detectors, सैल नियम (high recall); Abhi निवडतो.

सगळ्यांमध्ये समान (KB H): impulse (BOS, market_state F3) → corrective pullback (origin अबाधित) → area वर शेवट → बंद reversal candle → R:R.
Detector फक्त **बंद bars** (bar j पर्यंत) वर — no-lookahead. Hindsight निकाल फक्त नोंद; ranking मध्ये कधीच नाही (survivorship bias).

  G1 zigzag / ABC end   A-B-C (trade-degree), B ≤ 0.79 A, C/A 0.618–1.618, retrace 38.2–80%, C च्या टोकाजवळ (back ≤ 0.618 C), reversal candle.
  G2 expanded flat spring  B > 1.05 A; C ने A चं टोक 0.1–1.0 MR ने ओलांडलं (sweep) आणि शेवटचा close परत A टोकाच्या आत (reclaim).
  G3 triangle E-end     impulse नंतरचे 5 आकुंचन पावणारे legs (आतले swings), सगळे A च्या पट्ट्यात (प्रत्येक रेषेला A-C / B-D ≥ 2 touches), E-end ला
                        reversal; R5: HTF trend आधीच established (trend state "trend", impulse = पहिला leg नाही) ⇒ wave 2 नाही.
  G4 role flip retest   impulse ने तोडलेला swing (BOS level) — correction चं टोक त्या level च्या ±0.5 MR मध्ये (दुसऱ्या बाजूने retest) आणि reversal.
                        (futures volume असेल तर pullback volume — evaluate च्या VL पुराव्यात.)
  G5 ending diagonal C  A-B-C; C मध्ये ≥ 5 आतले legs, लहान होत जाणारे (1 > 3 > 5) आणि overlapping (4 ने 1 च्या पट्ट्यात), शेवट area वर
                        (evaluate: active area — trendline ≥ 3 touches अधिक) + reversal.
  G6 साधा pullback       HTF trend impulse च्या दिशेने ("trend"), फक्त A (किंवा लहान A-B), overlapping (K10.1 ≥ 0.6), pullback speed ≤ impulse,
                        retrace 38.2–61.8%, displacement base (evaluate: tool c) वर hammer / engulfing (reversal candle).
  G7 exhaustion gap     trend दिशेने मोठा gap (≥ G7_GAP_MR × MR), पहिल्या 6 bars मध्ये gap दिशेचं टोक आणि नंतर close day open च्या पलीकडे
                        परत (rejection / reclaim), मग पहिल्या pullback वर उलट reversal candle (opening window नंतर). Major HTF zone तपासणी
                        evaluate / Abhi च्या डोळ्यावर (सैल detector).
  G8 (ii)/(iv) of 3     simple_core.waves: wave 3 मधला उथळ (≤ 38.2% + tol), जलद (≤ 6 bars) pullback, wave 1 overlap नाही + reversal candle.
  G9 wave 4 end         simple_core.waves: wave 3 ≥ wave 1, pullback wave 1 च्या भागात नाही (R3) + reversal candle (Tier C).
Ranking (प्रति G): code grade total + confluence (evaluate) — hindsight नाही. वेगवेगळी वर्षं, दोन्ही बाजू, एका आठवड्यात एकच.
"""
import numpy as np
import pandas as pd

import market_state as MS
from market_state import core as C
from vision_led import candidates as CA

SETUPS = {
    "G1": "zigzag / ABC end",
    "G2": "expanded flat spring",
    "G3": "triangle E-end",
    "G4": "role flip retest",
    "G5": "ending diagonal C + trendline",
    "G6": "simple pullback on demand",
    "G7": "exhaustion gap reversal",
    "G8": "(ii)/(iv) of 3 shallow pullback",
    "G9": "wave 4 end → wave 5",
}
G7_GAP_MR = 3.0                  # [अनुमान, सैल] gap ≥ इतके × 15M MR
INTERNAL_ATR = 1.5


def _len(lab):
    return abs(lab["to"] - lab["from"])


def _rejection(bar, side):
    ok, _, _ = CA.rejection(float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]), side, CA.DEFAULTS)
    return ok


def internal_legs(trig, start_ts, upto):
    """impulse टोकापासून bar `upto` पर्यंतचे आतले swings (ATR × 1.5, confirmed + चालू टोक) ⇒ [(idx, price, kind)]."""
    sub = trig.iloc[: upto + 1].reset_index(drop=True)
    pv = C.pivots(sub, INTERNAL_ATR)
    t = C._tentative(sub, pv)
    pts = [p for p in pv + ([t] if t else []) if pd.Timestamp(p["ts"]) >= pd.Timestamp(start_ts)]
    return [(p["idx"], p["price"], p["kind"]) for p in pts]


def detect_g7(ms, trig, j, mr):
    """G7 exhaustion gap reversal (सैल): bar j = gap दिवसाचा पहिला pullback reversal (gap विरुद्ध दिशेने)."""
    if not np.isfinite(mr) or mr <= 0:
        return []
    ts = pd.to_datetime(trig["timestamp"])
    d0 = ts.iloc[j].normalize()
    today = np.nonzero((ts.dt.normalize() == d0).to_numpy())[0]
    prev = np.nonzero((ts.dt.normalize() < d0).to_numpy())[0]
    if not len(today) or not len(prev) or j - today[0] < 2:
        return []
    o0, pc = float(trig["open"].iloc[today[0]]), float(trig["close"].iloc[prev[-1]])
    gap = o0 - pc
    gd = 1 if gap > 0 else -1
    tr = ms.get("trend") or {}
    if abs(gap) < G7_GAP_MR * mr or int(tr.get("dir") or 0) != gd:
        return []
    seg = trig.iloc[today[0]:j + 1]
    first = seg.iloc[:6]
    ext_i = int(np.argmax(first["high"].to_numpy()) if gd > 0 else np.argmin(first["low"].to_numpy()))
    after = seg.iloc[ext_i + 1:-1]
    reclaimed = bool(((after["close"] < o0) if gd > 0 else (after["close"] > o0)).any()) if len(after) else False
    if not reclaimed or not _rejection(trig.iloc[j], -gd):
        return []
    return [{"setup": "G7", "side": -gd, "key": ("G7", f"{d0:%Y-%m-%d}"),
             "why": f"gap {gap:+,.0f} ({abs(gap) / mr:.1f} MR) trend दिशेने, टोकानंतर open {o0:,.0f} च्या पलीकडे close, पहिल्या pullback वर reversal"}]


def detect_waves(ms, trig, j, mr):
    """G8 / G9: simple_core.waves count (trade-degree swings) + bar j reversal candle."""
    from simple_core import waves as WV
    tr = ms.get("trend") or {}
    side = int(tr.get("dir") or 0) if tr.get("state") == "trend" else 0
    if not side or not _rejection(trig.iloc[j], side):
        return []
    piv = [{"ts": p["ts"], "price": p["price"], "kind": p["kind"]} for p in ms.get("swings") or []]
    w = WV.count(trig.iloc[:j + 1].reset_index(drop=True), piv, side)
    if w["setup"] not in ("G8", "G9"):
        return []
    ref = w["ref"]
    return [{"setup": w["setup"], "side": side, "key": (w["setup"], side, ref.get("wave1_origin"), ref.get("wave1_extreme")),
             "why": w["story"]}]


def detect(ms, trig, j, mr):
    """bar j (बंद) वर कोणते G जुळतात ⇒ [{"setup", "why", "labels"(ऐच्छिक)}]. ms = market_state at bar j close."""
    imp, corr = ms.get("impulse"), ms.get("correction") or {}
    extra = detect_g7(ms, trig, j, mr) + detect_waves(ms, trig, j, mr)
    if not imp or corr.get("status") in (None, "origin_broken", "not_started", "none") or not np.isfinite(mr) or mr <= 0:
        return extra
    side = imp["dir"]
    bar = trig.iloc[j]
    close = float(bar["close"])
    rej = _rejection(bar, side)
    labels = corr.get("labels") or []
    names = [x["label"] for x in labels]
    r = float(corr.get("retrace") or 0.0)
    tr = ms.get("trend") or {}
    out = []
    if names[:3] == ["A", "B", "C"]:
        A, B, Cc = labels[0], labels[1], labels[2]
        a, b, c = _len(A), _len(B), _len(Cc)
        back = abs(Cc["to"] - close)
        near_c = c > 0 and back <= 0.618 * c
        if a > 0 and b <= 0.79 * a and 0.618 <= c / a <= 1.618 and 0.382 <= r <= 0.80 and near_c and rej:
            out.append({"setup": "G1", "why": f"A-B-C zigzag: B/A {b / a:.2f}, C/A {c / a:.2f}, retrace {r:.0%}"})
        a_end = A["to"]
        over = (a_end - Cc["to"]) * side                                   # bull: C चा low A low च्या किती खाली
        if a > 0 and b > 1.05 * a and 0.1 * mr <= over <= 1.0 * mr and (close - a_end) * side > 0 and rej:
            out.append({"setup": "G2", "why": f"expanded flat: B/A {b / a:.2f}, C sweep {over / mr:.2f} MR पलीकडे, reclaim close"})
        if near_c and rej:
            legs = [p for p in internal_legs(trig, Cc["from_ts"], j)]
            m = [abs(legs[i + 1][1] - legs[i][1]) for i in range(len(legs) - 1)]
            if len(m) >= 5:
                m5 = m[-5:]
                p5 = legs[-6:]
                shrinking = m5[0] > m5[2] > m5[4]
                overlap = (p5[4][1] - p5[1][1]) * side < 0                  # wave 4 चं टोक wave 1 च्या पट्ट्यात
                if shrinking and overlap:
                    out.append({"setup": "G5", "why": f"C मध्ये ending diagonal: legs {', '.join(f'{x:.0f}' for x in m5)} (लहान होत, overlap)"})
    pts = internal_legs(trig, imp["to_ts"], j)
    if len(pts) >= 6 and rej and tr.get("dir") == side and tr.get("state") == "trend":
        p6 = pts[-6:]
        m = [abs(p6[i + 1][1] - p6[i][1]) for i in range(5)]
        lo, hi = sorted((p6[0][1], p6[1][1]))
        inside = all(lo - 0.25 * mr <= p[1] <= hi + 0.25 * mr for p in p6[2:])
        if m[2] < m[0] and m[3] < m[1] and m[4] < m[2] and inside:
            tl = [{"label": n, "from": round(p6[i][1], 2), "to": round(p6[i + 1][1], 2), "from_ts": trig["timestamp"].iloc[p6[i][0]],
                   "to_ts": trig["timestamp"].iloc[p6[i + 1][0]]} for i, n in enumerate("ABCDE")]
            out.append({"setup": "G3", "why": f"triangle: legs {', '.join(f'{x:.0f}' for x in m)} आकुंचन", "labels": tl})
    bos = imp.get("bos")
    ext = corr.get("extreme")
    if bos is not None and ext is not None and abs(float(ext) - float(bos)) <= 0.5 * mr and (close - float(bos)) * side > 0 and rej:
        out.append({"setup": "G4", "why": f"role flip: impulse ने तोडलेला {bos:,.0f} — correction टोक {ext:,.0f} (±0.5 MR) retest, rejection"})
    if tr.get("dir") == side and tr.get("state") == "trend" and names[:1] == ["A"] and len(names) <= 2 and 0.382 <= r <= 0.618 and rej:
        ov = corr.get("overlap")
        if ov is not None and ov >= 0.6:
            out.append({"setup": "G6", "why": f"साधा pullback: retrace {r:.0%}, overlap {ov}, trend सोबत"})
    return out + extra


def cheap_score(hit, ms):
    """Stage-1 shortlist (hindsight नाही): impulse आकार + retrace केंद्राजवळ."""
    imp = ms.get("impulse") or {}
    r = float((ms.get("correction") or {}).get("retrace") or 0.0)
    return float(imp.get("size_mr") or 0.0) - 5.0 * abs(r - 0.55)


def scan(m1, trig, frames, start=None, end=None, step=1, log=None):
    """Stage 1: प्रत्येक बंद 15M bar वर market_state (frames, Elliott नाही) + detect. एका correction (impulse) चा प्रति G एकच — पहिला hit.
    रिटर्न [{setup, bar_start, bar_end, side, why, labels, impulse, score, ms_lines}]."""
    mra = C.BR.median_range(trig, 20)
    ts = pd.to_datetime(trig["timestamp"])
    seen, out = set(), []
    js = np.nonzero(((ts >= pd.Timestamp(start)) if start else ts.notna()).to_numpy() & ((ts <= pd.Timestamp(end)) if end else ts.notna()).to_numpy())[0]
    for n, j in enumerate(js[::step]):
        if ts.iloc[j].strftime("%H:%M") < CA.DEFAULTS["start_hm"]:
            continue
        ms = MS.read(m1, trig["bar_end"].iloc[j], run_elliott=False, frames=frames)
        for h in detect(ms, trig, int(j), float(mra[j]) if np.isfinite(mra[j]) else float("nan")):
            imp = ms["impulse"] or {}
            key = h.get("key") or (h["setup"], imp.get("dir"), imp.get("from"), imp.get("to"))
            if key in seen:
                continue
            seen.add(key)
            out.append({**{k: v for k, v in h.items() if k != "key"}, "bar_start": ts.iloc[j], "bar_end": pd.Timestamp(trig["bar_end"].iloc[j]),
                        "side": h.get("side") or imp.get("dir"), "impulse": imp,
                        "trend": ms["trend"], "labels": h.get("labels") or (ms.get("correction") or {}).get("labels") or [],
                        "score": cheap_score(h, ms), "code_side": ms["side"]})
        if log and n % 2000 == 0:
            log(f"  {ts.iloc[j]:%Y-%m-%d}: hits {len(out)}")
    return out


def select(cands, per_setup=8):
    """प्रति G सर्वोत्तम `per_setup` (key = rank: code total + confluence, ज्यावर hindsight नाही): वेगवेगळी वर्षं आधी, दोन्ही बाजू, एका
    आठवड्यात एकच. cands मध्ये "rank" (evaluate नंतर) असावा."""
    out = []
    for g in SETUPS:
        pool = sorted([c for c in cands if c["setup"] == g], key=lambda c: -c.get("rank", c.get("score", 0.0)))
        chosen, weeks, years, sides = [], set(), {}, {1: 0, -1: 0}
        for rnd in range(3):                                            # 1: नवीन वर्ष + कमी side · 2: नवीन आठवडा · 3: उरलेले
            for c in pool:
                if len(chosen) >= per_setup or c in chosen:
                    continue
                wk = pd.Timestamp(c["bar_start"]).strftime("%G-%V")
                if wk in weeks:
                    continue
                y = pd.Timestamp(c["bar_start"]).year
                if rnd == 0 and (y in years or sides[c["side"]] > sides[-c["side"]]):
                    continue
                chosen.append(c)
                weeks.add(wk)
                years[y] = years.get(y, 0) + 1
                sides[c["side"]] += 1
        out += chosen
    return out
