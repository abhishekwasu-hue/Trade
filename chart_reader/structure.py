"""chart_reader/structure.py — impulse, corrective pullback आणि त्याचा प्रकार; pullback की reversal (Abhi 2026-10-08).

🎓 मुख्य setup = PULLBACK END: trade-degree च्या आधीच्या impulse नंतरचा corrective pullback (zigzag / flat / triangle) पूर्ण होताना,
impulse च्या दिशेने credit spread. Entry points: zigzag C-end, flat C-end, triangle E-end.
  impulse   elliott/swings.py pivots (ATR × swing_atr_mult) — शेवटच्या impulse_lookback_legs पैकी सर्वात मोठा leg ज्यानंतरचे सगळे legs लहान
  correction impulse टोकानंतरचे lower-degree pivots (ATR × internal_atr_mult) + चालू tentative टोक. MR = 20 बंद bars (measures.py).
            3 legs: B ≥ flat_b_min × A ⇒ flat (C-end फक्त C ≥ flat_c_min × A) · B ≤ zigzag_b_max × A आणि C ने A चं टोक
            ओलांडलं ⇒ zigzag
            5 legs: आकुंचन पावणारे (c < a, d < b, e < c) आणि a च्या पट्ट्यात ⇒ triangle; सलग LL/LH ⇒ impulsive (reversal)
  reversal चे पुरावे (कुठलाही ⇒ "pullback नाही"): counter-move impulsive (5-wave LL/LH किंवा ≥ disp_bars_reversal displacement bars),
            impulse origin चा real break (elliott/breaks.py), major zone पलीकडे acceptance (सलग closes)
  correction कमकुवत होण्याचे पुरावे (0–1): शेवटचा correction-दिशेचा leg पहिल्यापेक्षा हळू, लहान bodies, जास्त overlap,
            correction विरुद्ध wicks जास्त, आणि A च्या टोकापलीकडे फारसा विस्तार नाही (failed extension).
फक्त दिलेले (बंद) bars; state नाही ⇒ तेच इनपुट तेच उत्तर (no-lookahead: caller फक्त बंद bars देतो; `upto` ⇒ तिथपर्यंतच).
"""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from elliott import settings as ES

from . import measures as M


def _points(d, atr_mult):
    """elliott/swings.py चे confirmed pivots (ATR × atr_mult — KB भाग G: एकच swing engine) + चालू tentative टोक ⇒ [(bar, price, kind)]."""
    pts = [(b, px, k) for b, px, k, _ in M.pivots(d, atr_mult)]
    return _with_tentative(d, pts)


def _with_tentative(d, pts, after=None):
    h, lo = d["high"].to_numpy(float), d["low"].to_numpy(float)
    if not pts:
        return pts
    b0, _, kind = pts[-1]
    a = b0 + 1
    if a < len(d):
        if kind == "H":
            j = a + int(np.argmin(lo[a:]))
            pts = pts + [(j, float(lo[j]), "L")]
        else:
            j = a + int(np.argmax(h[a:]))
            pts = pts + [(j, float(h[j]), "H")]
    return pts


def _alternate(pts):
    out = []
    for p in pts:
        if out and out[-1][2] == p[2]:
            if (p[2] == "H" and p[1] >= out[-1][1]) or (p[2] == "L" and p[1] <= out[-1][1]):
                out[-1] = p
            continue
        out.append(p)
    return out


def _leg_stats(d, a, b, direction, mr):
    """Leg [a, b] चे गुण: speed (pts/bar ÷ MR), avg body ÷ MR, overlap, correction-विरुद्ध wick share."""
    o, h, lo, c = (d[x].to_numpy(float)[a:b + 1] for x in ("open", "high", "low", "close"))
    n = max(b - a, 1)
    rng = np.maximum(h - lo, 1e-9)
    body = np.abs(c - o)
    ov = [max(0.0, min(h[i], h[i - 1]) - max(lo[i], lo[i - 1])) / rng[i] for i in range(1, len(h))] or [0.0]
    # correction खाली (direction −1) ⇒ विरुद्ध wick = lower wick; वर ⇒ upper wick
    wick = (np.minimum(o, c) - lo) if direction < 0 else (h - np.maximum(o, c))
    return {"speed": abs(c[-1] - o[0]) / n / mr, "body": float(body.mean() / mr), "overlap": float(np.mean(ov)),
            "wick": float((wick / rng).mean())}


def _classify(pts, cdir, s):
    m = [abs(pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    n = len(m)
    if n == 3:
        a, b, c = m
        beyond = (pts[3][1] - pts[1][1]) * cdir > 0                       # C ने A चं टोक ओलांडलं
        if b >= s["flat_b_min"] * a:
            return "flat"
        if b <= s["zigzag_b_max"] * a and beyond:
            return "zigzag"
        return "unclear"
    if n == 5:
        lo, hi = sorted((pts[0][1], pts[1][1]))
        inside = all(lo - 1e-9 <= p[1] <= hi + 1e-9 for p in pts[2:])
        if m[2] < m[0] and m[3] < m[1] and m[4] < m[2] and inside:
            return "triangle"
        if _monotone(pts, cdir):
            return "impulsive"
        return "complex"
    return {1: "A", 2: "AB", 4: "ABCD"}.get(n, "complex")


def _monotone(pts, cdir):
    """correction दिशेने सलग नवीन टोकं (LL + LH खाली; HH + HL वर) ⇒ impulsive रचना."""
    ext = [p[1] for p in pts[1::2]]                                       # correction-दिशेची टोकं (A, C, E …)
    cnt = [p[1] for p in pts[0::2]]                                       # उलटी टोकं
    return (all((ext[i + 1] - ext[i]) * cdir > 0 for i in range(len(ext) - 1))
            and all((cnt[i + 1] - cnt[i]) * cdir > 0 for i in range(len(cnt) - 1)))


def _overlap_ratio(d, a, b):
    """K10.1: [a, b] मधल्या bars पैकी मागच्या bar शी > 50% (स्वतःच्या range च्या) overlap असलेल्यांचं प्रमाण."""
    h, lo = d["high"].to_numpy(float)[a:b + 1], d["low"].to_numpy(float)[a:b + 1]
    if len(h) < 2:
        return None
    rng = np.maximum(h - lo, 1e-9)
    ov = np.maximum(0.0, np.minimum(h[1:], h[:-1]) - np.maximum(lo[1:], lo[:-1])) / rng[1:]
    return round(float((ov > 0.5).mean()), 3)


def _origin_break(d, start, origin, idir, es):
    """Impulse origin चा **खरा** break (KB भाग G: एकच व्याख्या elliott/breaks.py — 0.25 MR buffer + displacement / acceptance / failed
    retest). रिटर्न confirm index किंवा None. फक्त दिलेले बंद bars."""
    fr = d if "bar_end" in d.columns else d.assign(bar_end=d["timestamp"])
    mr = BR.median_range(fr, es["median_range_n"])
    retest = None
    if es.get("break_retest_confirm") and es.get("count_inv_basis") != "wick":
        from elliott.reversal import retest_fn
        retest = retest_fn(fr, es, mr)
    return BR.first_real_break(fr, start, origin, "below" if idir > 0 else "above", es, mr=mr, retest_fn=retest)


def _bar_of(d, ts, price=None, kind=None, span_min=15):
    """market_state (15M) चा pivot ⇒ d मधला bar index. d बारीक TF (instant: 5M) असेल तर त्या 15M bin मधला खरा टोकाचा bar
    (kind H ⇒ high max, L ⇒ low min) — V3 review."""
    t = d["timestamp"].to_numpy(dtype="datetime64[ns]")
    a = max(int(np.searchsorted(t, np.datetime64(ts, "ns"), side="right")) - 1, 0)
    if kind is None:
        return a
    b = int(np.searchsorted(t, np.datetime64(pd.Timestamp(ts) + pd.Timedelta(minutes=span_min), "ns"), side="left"))
    if b - a <= 1:
        return a
    seg = d["high"].to_numpy(float)[a:b] if kind == "H" else d["low"].to_numpy(float)[a:b]
    return a + int(seg.argmax() if kind == "H" else seg.argmin())


def _abc_type(labels, cdir, s):
    """market_state चे A/B/C (trade-degree swings) ⇒ zigzag / flat (KB K3 family: B < 0.79 A zigzag, ≥ 0.9 A flat)."""
    if len(labels) < 3:
        return {1: "A", 2: "AB"}.get(len(labels))
    a = abs(labels[0]["to"] - labels[0]["from"])
    b = abs(labels[1]["to"] - labels[1]["from"])
    beyond = (labels[2]["to"] - labels[0]["to"]) * cdir > 0
    if a <= 0:
        return "unclear"
    if b >= s["flat_b_min"] * a:
        return "flat"
    if b <= s["zigzag_b_max"] * a and beyond:
        return "zigzag"
    return "unclear"


def read(df, s, major_zones=None, upto=None, es=None, ms=None):
    """रिटर्न dict (JSON-able): impulse, side, correction_type, entry_point, correction (टोकं), retrace, duration_ratio, pullback
    ("pullback" / "reversal" / "unclear" / "none"), reversal_reasons, correction_weakening (0–1), cw_parts, facts (ओळी).
    ms = market_state.read चा निकाल (F1): impulse आणि A/B/C तिथूनच (ad-hoc impulse finder फक्त ms नसताना — जुने callers / tests)."""
    d = df if upto is None else df.iloc[: upto + 1]
    d = d.reset_index(drop=True)
    es = es or ES.DEFAULTS
    out = {"impulse": None, "side": 0, "correction_type": None, "entry_point": None, "correction": [], "retrace": None,
           "correction_bars": [], "duration_ratio": None, "c_progress": None, "correction_extreme": None, "pullback": "none",
           "reversal_reasons": [], "origin_probe": False, "overlap": None, "correction_weakening": 0.0, "cw_parts": {}, "facts": []}
    if len(d) < 25:
        out["facts"].append("डेटा अपुरा")
        return out
    mr = M.mr_now(d)
    if not np.isfinite(mr) or mr <= 0:
        mr = float((d["high"] - d["low"]).median())
    if not np.isfinite(mr) or mr <= 0:
        mr = 1e-9                                                         # सगळे bars high == low (data) ⇒ division by zero टाळा
    labels = None
    if ms is not None:
        mi = ms.get("impulse")
        if not mi:
            out["facts"].append("स्पष्ट impulse नाही (market_state F3)")
            return out
        b0 = _bar_of(d, mi["from_ts"], kind="L" if mi["dir"] > 0 else "H")
        b1 = _bar_of(d, mi["to_ts"], kind="H" if mi["dir"] > 0 else "L")
        p0, p1 = float(mi["from"]), float(mi["to"])
        k1 = "H" if mi["dir"] > 0 else "L"
        best = (None, abs(p1 - p0))
        labels = (ms.get("correction") or {}).get("labels") or []
    else:
        sw = _alternate(_points(d, s["swing_atr_mult"]))
        legs = [(sw[i], sw[i + 1]) for i in range(len(sw) - 1)]
        cand = list(range(max(0, len(legs) - int(s["impulse_lookback_legs"])), len(legs) - 1))
        best = None
        for i in cand:
            mag = abs(legs[i][1][1] - legs[i][0][1])
            if mag >= s["impulse_min_mr"] * mr and all(abs(b[1] - a[1]) < mag for a, b in legs[i + 1:]):
                if best is None or mag > best[1]:
                    best = (i, mag)
        if best is None:
            out["facts"].append("स्पष्ट impulse नाही")
            return out
        (b0, p0, _), (b1, p1, k1) = legs[best[0]]
    idir = 1 if p1 > p0 else -1
    cdir = -idir
    out["impulse"] = {"dir": idir, "origin": round(p0, 2), "end": round(p1, 2), "start_bar": int(b0), "end_bar": int(b1),
                      "bars": int(b1 - b0), "size_mr": round(best[1] / mr, 2)}
    out["side"] = idir
    # correction: impulse टोकानंतरचे internal pivots
    inner = [(b, px, k) for b, px, k, _ in M.pivots(d, s["internal_atr_mult"]) if b > b1]
    pts = _alternate([(b1, p1, k1)] + inner)
    pts = _alternate(_with_tentative(d, pts))
    out["correction"] = [round(p[1], 2) for p in pts]
    out["correction_bars"] = [int(p[0]) for p in pts]
    ctype = _classify(pts, cdir, s) if len(pts) >= 2 else None
    n_legs = len(pts) - 1
    last_dir_ok = n_legs >= 1 and (pts[-1][1] - pts[-2][1]) * cdir > 0
    if n_legs >= 3:
        a_len = abs(pts[1][1] - pts[0][1])
        out["c_progress"] = round(abs(pts[3][1] - pts[2][1]) / a_len, 3) if a_len > 0 else None
    if labels is not None and len(labels) >= 1:
        # F1/F3: A/B/C trade-degree swings वरून (market_state); आतले pivots फक्त weakening / overlap साठी
        ctype = _abc_type(labels, cdir, s)
        n_legs = len(labels)
        out["abc"] = [{"label": x["label"], "from": x["from"], "to": x["to"]} for x in labels]
        if n_legs >= 3:
            a_len = abs(labels[0]["to"] - labels[0]["from"])
            out["c_progress"] = round(abs(labels[2]["to"] - labels[2]["from"]) / a_len, 3) if a_len > 0 else None
            c_len = abs(labels[2]["to"] - labels[2]["from"])
            back = abs(labels[2]["to"] - float(d["close"].iloc[-1]))
            last_dir_ok = c_len > 0 and back <= s["c_end_back_max"] * c_len   # C च्या टोकाजवळ (C चा 61.8% पेक्षा कमी परत)
            n_legs = 3
    out["correction_type"] = ctype
    if ctype == "zigzag" and n_legs == 3 and last_dir_ok:
        out["entry_point"] = "C-end"
    elif ctype == "flat" and n_legs == 3 and last_dir_ok and (out.get("c_progress") or 0) >= s["flat_c_min"]:
        out["entry_point"] = "C-end"                                     # flat: C ने A एवढं अंतर (≥ 0.9 × A) गाठलं तरच C-end
    elif ctype == "triangle" and n_legs == 5 and last_dir_ok:
        out["entry_point"] = "E-end"
    h, lo, c, o = (d[x].to_numpy(float) for x in ("high", "low", "close", "open"))
    span = slice(b1 + 1, len(d))
    deep = (lo[span].min() if cdir < 0 else h[span].max()) if b1 + 1 < len(d) else p1
    out["retrace"] = round(abs(p1 - deep) / abs(p1 - p0), 3)
    out["correction_extreme"] = round(float(deep), 2)                    # risk: invalidation correction च्या टोकापलीकडे सुद्धा
    cbars = len(d) - 1 - b1
    out["duration_ratio"] = round(cbars / max(b1 - b0, 1), 2)
    # ---- reversal चे पुरावे ----
    reasons = []
    if ctype == "impulsive" or (n_legs >= 5 and _monotone(pts, cdir)):
        reasons.append("counter_move_impulsive")
    else:
        body = np.abs(c[span] - o[span])
        rng = np.maximum(h[span] - lo[span], 1e-9)
        disp = ((body >= s["disp_body_mr"] * mr) & (body / rng >= s["disp_body_frac"]) & ((c[span] - o[span]) * cdir > 0)).sum()
        if disp >= s["disp_bars_reversal"]:
            reasons.append("counter_move_impulsive")
    if b1 + 1 < len(d):
        if _origin_break(d, b1 + 1, p0, idir, es) is not None:
            reasons.append("impulse_origin_acceptance")                 # real break ⇒ A3 व्हेटो
        elif ((lo[span] < p0) if idir > 0 else (h[span] > p0)).any():
            out["origin_probe"] = True                                   # 100% पलीकडे wick / कमकुवत close, acceptance नाही ⇒ PB −15
    out["overlap"] = _overlap_ratio(d, b1 + 1, len(d) - 1)
    for zlo, zhi in (major_zones or []):
        ab = s["acceptance_buffer_mr"] * mr
        beyond = (c[span] < zlo - ab) if cdir < 0 else (c[span] > zhi + ab)
        run = best_run = 0
        for x in beyond:
            run = run + 1 if x else 0
            best_run = max(best_run, run)
        if best_run >= s["acceptance_bars"]:
            reasons.append("acceptance_major_level")
            break
    out["reversal_reasons"] = reasons
    # F2 (Abhi 2026-10-08): counter चाल protected swing (impulse origin) च्या real break पर्यंत correction — लांबी / displacement / major
    # level acceptance हे फक्त धोक्याचे पुरावे (PB −10), "reversal" नाही. ms नसताना (जुने callers) जुनं वर्तन.
    flip = ("impulse_origin_acceptance" in reasons) if ms is not None else bool(reasons)
    if flip:
        out["pullback"], out["entry_point"] = "reversal", None
    elif out["retrace"] <= s["retrace_max"] or ctype == "triangle":
        out["pullback"] = "pullback"
    else:
        out["pullback"] = "unclear"
    # ---- correction कमकुवत होणं ----
    cd = [(pts[i][0], pts[i + 1][0]) for i in range(len(pts) - 1) if (pts[i + 1][1] - pts[i][1]) * cdir > 0]
    if len(cd) >= 2:
        A = _leg_stats(d, cd[0][0], cd[0][1], cdir, mr)
        L = _leg_stats(d, cd[-1][0], cd[-1][1], cdir, mr)
        a_len = abs(pts[1][1] - pts[0][1])
        ext = (pts[-1][1] - pts[1][1]) * cdir
        parts = {"slower": L["speed"] < A["speed"], "smaller_bodies": L["body"] < A["body"], "more_overlap": L["overlap"] > A["overlap"],
                 "more_counter_wicks": L["wick"] > A["wick"], "failed_extension": ext < 0.382 * a_len}
        out["cw_parts"] = {k: bool(v) for k, v in parts.items()}
        out["correction_weakening"] = round(sum(parts.values()) / len(parts), 3)
    # ---- facts (ओळी) ----
    f = out["facts"]
    f.append(f"impulse {'वर' if idir > 0 else 'खाली'} {p0:,.1f} → {p1:,.1f} ({out['impulse']['size_mr']}× MR, {b1 - b0} bars)")
    cp = out["correction"]
    shown = " → ".join(f"{x:,.1f}" for x in cp) if len(cp) <= 8 else f"{cp[0]:,.1f} → … → " + " → ".join(f"{x:,.1f}" for x in cp[-5:])
    f.append(f"correction {ctype or '—'} ({n_legs} legs): {shown}; retrace "
             f"{out['retrace']:.0%}, वेळ impulse च्या {out['duration_ratio']}×")
    if out["retrace"] < s["retrace_lo"]:
        f.append("pullback उथळ (< 38.2%)")
    if flip:
        f.append("reversal चे पुरावे: " + ", ".join(reasons) + " ⇒ pullback नाही")
    elif reasons:
        f.append("धोक्याचे पुरावे (F2: protected swing अबाधित ⇒ अजून correction): " + ", ".join(reasons))
    elif out["entry_point"]:
        f.append(f"entry point: {ctype} {out['entry_point']} — impulse दिशेने ({'bull put' if idir > 0 else 'bear call'})")
    if out["cw_parts"]:
        f.append("correction कमकुवत: " + ", ".join(k for k, v in out["cw_parts"].items() if v) + f" ⇒ {out['correction_weakening']:.2f}")
    return out
