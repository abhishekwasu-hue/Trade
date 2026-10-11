"""reader2/anatomy.py — anatomy vote (spec §2b / §2d): −1 (पूर्ण सुधारात्मक) ते +1 (पूर्ण आवेगी).

§2d: candles फक्त lowest degree ला वाचतो (`vote`): leg च्या आत खालच्या degree चे pivots नाहीत ⇒ तो leg स्वतःच lowest-degree swing.
वरच्या degree चा vote = sub-legs (एक degree खाली, recursive — शेवटी candles) चा roll-up (`rollup`): आवेगी leg ⇒ leg-दिशेचे (motive)
sub-legs आवेगी आणि उलट (counter) sub-legs सुधारात्मक / थोडक्यात / उथळ; सुधारात्मक leg ⇒ motive sub-legs सुधारात्मक (overlapping), लांब /
खोल थांबे. लांब leg च्या सगळ्या candles ची सरासरी नाही (waves 2 / 4 ती पातळ करतात). Motive sub-leg निर्णायक आवेगी नसेल तर pause पुरावा
leg ला आवेगी करू शकत नाही (score ≤ motive); motive चालीचा मोठा वाटा (≥ rollup_veto_share) असलेला सुधारात्मक motive sub-leg सुद्धा —
उदा. big-c zigzag: a सुधारात्मक ⇒ leg आवेगी नाही; टोकाजवळचा लहान आळशी push impulse रद्द करत नाही. Sub-legs ची संख्या anatomy मध्ये
कधीच वापरत नाही (wave count फक्त structure vote मध्ये — दोन votes स्वतंत्र); a-b-c आणि 1-2-3-4-5 candles च्या पुराव्याने वेगळे:
c चे candles a सारखे, b लांब / overlapping ⇒ सुधार; wave 2 / 4 थोडके, wave 3 सर्वात आवेगी ⇒ आवेग.

Candle मापं legs2/features.py मधूनच (`leg_features`: body, CLV_d, overlap, ER, displacement, FVG, wave volume); इथे फक्त जे legs2 मध्ये
नाही ते: MR units मधली range expansion / contraction, दोन्ही बाजूंच्या wicks, आधीच्या counter-move शी volume तुलना, effort vs result
(MR units), swing मधली pause. प्रत्येक feature ⇒ settings च्या (corrective, impulsive) टोकांमध्ये रेषीय score; NA आणि एकतर्फी
feature चा 0 सरासरीत नाहीत (evidence मध्ये कारणासह). Points / % नाहीत.
"""
import numpy as np

from legs2 import features as LF

from . import legs as RL

LEAN_IMP, LEAN_COR, LEAN_NEU = "impulsive", "corrective", "neutral"


def feature_score(x, lo, hi, side):
    """x ⇒ [−1, +1]: lo (corrective टोक) ⇒ −1, hi (impulsive टोक) ⇒ +1, मध्ये रेषीय. side "imp" / "cor" ⇒ एकाच बाजूला."""
    if x is None or not np.isfinite(x) or hi == lo:
        return None
    v = float(np.clip(-1.0 + 2.0 * (x - lo) / (hi - lo), -1.0, 1.0))
    if side == "imp":
        v = max(v, 0.0)
    elif side == "cor":
        v = min(v, 0.0)
    return v


def _mean(xs):
    xs = [x for x in xs if x is not None and np.isfinite(x)]
    return float(np.mean(xs)) if xs else None


def _vol_per_bar(ch, i0, i1, s):
    if ch.vol is None:
        return None
    v = ch.vol[i0 + 1:i1 + 1]
    v = v[np.isfinite(v)]
    return float(v.mean()) if len(v) >= int(s["v_min_reliable"]) else None


def _pause(ch, i0, i1, d):
    """सर्वात खोल आतली उलट चाल (चालू टोकापासून, wicks) आणि नवीन टोकाशिवायचा सर्वात लांब काळ (bars)."""
    A = ch.A
    ext = A["l"][i0] if d > 0 else A["h"][i0]                    # चालू leg-दिशेचं टोक (leg सुरुवातीपासून)
    deep = 0.0
    run = best = 0
    for i in range(i0 + 1, i1 + 1):
        far = A["h"][i] if d > 0 else A["l"][i]
        back = A["l"][i] if d > 0 else A["h"][i]
        if (far - ext) * d > 0:
            ext, run = far, 0
        else:
            run += 1
            best = max(best, run)
        deep = max(deep, (ext - back) * d)
    return deep, best


def raw(ch, i0, i1, d, prev=None):
    """Leg bars (i0, i1] ची मापं (MR units / unit-नसलेली). prev = आधीच्या counter-move चे (j0, j1) (volume तुलनेसाठी)."""
    s, A = ch.s, ch.A
    unit = ch.mr[i0]
    n = i1 - i0
    size = abs(A["h"][i1] - A["l"][i0]) if d > 0 else abs(A["h"][i0] - A["l"][i1])
    size_mr = size / unit if unit and np.isfinite(unit) and unit > 0 else None
    sigma = unit if size_mr is not None else None
    f = LF.leg_features(A, ch.rr, ch.vol, None, np.zeros(len(ch), bool), i0, i1, d, size, sigma, s)
    idx = range(i0 + 1, i1 + 1)
    out = {"bars": n, "size_mr": size_mr, "body": f["body"], "close_loc": f["clv_d"], "overlap": f["overlap"], "er": f["er"],
           "displacement": ((f["n_disp"] + f["n_fvg"]) / n) if n and size_mr is not None else None,
           "wick_opp": _mean([LF.wick_opp_d(A, i, d) for i in idx])}
    rng = ch.rng[i0 + 1:i1 + 1]
    out["range"] = float(rng.mean() / unit) if size_mr is not None and n else None
    half = n // 2
    ok = half >= int(s["contraction_min_half"]) and rng[:half].mean() > 0
    out["contraction"] = float(rng[n - half:].mean() / rng[:half].mean()) if ok else None
    wb = float(s["wick_both_min"])
    both = []
    for i in idx:
        r = ch.rng[i]
        if r > 0:
            o, c = A["o"][i], A["c"][i]
            both.append((A["h"][i] - max(o, c)) / r >= wb and (min(o, c) - A["l"][i]) / r >= wb)
    out["wick_both"] = float(np.mean(both)) if both else None
    deep, stall = _pause(ch, i0, i1, d)
    out["pause_depth"] = (deep / size) if size > 0 else None
    out["stall"] = stall / n if n else None
    out["volume"] = out["effort_result"] = None
    if prev is not None and ch.vol is not None:
        j0, j1 = prev
        va, vb = _vol_per_bar(ch, i0, i1, s), _vol_per_bar(ch, j0, j1, s)
        if va is not None and vb:
            out["volume"] = va / vb
            unit_p = ch.mr[j0]
            psize = float(A["h"][j0:j1 + 1].max() - A["l"][j0:j1 + 1].min())
            if unit_p and np.isfinite(unit_p) and psize > 0 and size_mr:
                speed, pspeed = size_mr / n, (psize / unit_p) / (j1 - j0)
                out["effort_result"] = out["volume"] / (speed / pspeed) if speed > 0 else None
    return out


def _fmt(x):
    return "NA" if x is None else f"{x:.2f}"


def vote(ch, i0, i1, d, prev=None):
    """रिटर्न {"score" (None = NA), "cls" (impulsive / corrective / neutral / NA), "evidence": [...], "raw": {...}}."""
    s = ch.s
    n = i1 - i0
    if n <= int(s["short_leg_bars"]):
        return {"score": None, "cls": "NA", "evidence": [{"feature": "bars", "value": n, "score": None, "lean": LEAN_NEU,
                                                           "text": f"{n} bars ≤ {s['short_leg_bars']}: too short to read candles"}],
                "raw": {"bars": n}}
    m = raw(ch, i0, i1, d, prev)
    if m["size_mr"] is None:
        return {"score": None, "cls": "NA", "raw": m,
                "evidence": [{"feature": "mr", "value": None, "score": None, "lean": LEAN_NEU, "text": "median range warm-up: NA"}]}
    ev, num, den = [], 0.0, 0.0
    for k, (lo, hi, side) in s["features"].items():
        x = m.get(k)
        sc = feature_score(x, lo, hi, side)
        lean = LEAN_NEU if sc is None or abs(sc) < 1e-9 else (LEAN_IMP if sc > 0 else LEAN_COR)
        why = "NA (no volume)" if x is None and k in ("volume", "effort_result") else ("NA" if x is None else f"{_fmt(x)}")
        ev.append({"feature": k, "value": x, "score": sc, "lean": lean,
                   "text": f"{k} {why} (corrective {lo}, impulsive {hi}) ⇒ {lean}" if sc is not None else f"{k} {why}"})
        e = ev[-1]
        e["counted"] = sc is not None and not (side != "both" and sc == 0.0)      # एकतर्फी feature चा 0 = पुरावा नाही
        if e["counted"]:
            w = float(s["weights"].get(k, 1.0))
            num, den = num + w * sc, den + w
    used = sum(1 for e in ev if e["counted"])
    if used < int(s["min_features"]) or den <= 0:
        return {"score": None, "cls": "NA", "evidence": ev, "raw": m}
    score = num / den
    return {"score": score, "cls": classify(score, s), "evidence": ev, "raw": m}


def classify(score, s):
    if score is None:
        return "NA"
    return LEAN_IMP if score >= float(s["a_hi"]) else (LEAN_COR if score <= float(s["a_lo"]) else LEAN_NEU)


def lower_bars(ch, i0, i1, low):
    """Leg (i0, i1] च्या वेळेतले खालच्या TF चे bars ⇒ (j0, j1) त्या frame मध्ये (j0 = आधीचा bar). नाहीत ⇒ None."""
    ts = ch.d["timestamp"]
    t0 = ts.iloc[i0 + 1] if i0 + 1 < len(ts) else None
    t1 = ts.iloc[i1 + 1] if i1 + 1 < len(ts) else ch.kat[i1]
    if t0 is None:
        return None
    lt = low.d["timestamp"]
    sel = np.flatnonzero((lt >= t0).to_numpy() & (lt < t1).to_numpy())
    if len(sel) < 2 or sel[0] < 1:
        return None
    return int(sel[0] - 1), int(sel[-1])


def candle_vote(ch, i0, i1, d, prev=None, low=None):
    """Lowest degree: leg च्या candles; low = खालच्या TF चा Chart (उदा. Daily साठी 1H) ⇒ दोघांची वजनी सरासरी (spec §2d).
    शुद्ध function ⇒ Chart वर cache (roll-up / re-read तेच sub-legs पुन्हा वाचतात)."""
    key = (int(i0), int(i1), int(d), prev, id(low))
    cache = ch.__dict__.setdefault("_cv", {})
    if key not in cache:
        cache[key] = _candle_vote(ch, i0, i1, d, prev, low)
    return cache[key]


def _candle_vote(ch, i0, i1, d, prev, low):
    own = vote(ch, i0, i1, d, prev)
    own["level"] = "candles"
    if low is None:
        return own
    jj = lower_bars(ch, i0, i1, low)
    if jj is None:
        return own
    sub = vote(low, jj[0], jj[1], d)
    if sub["score"] is None:
        return own
    if own["score"] is None:
        score = sub["score"]
    else:
        w = float(ch.s["lower_weight"])
        score = (1 - w) * own["score"] + w * sub["score"]
    ev = own["evidence"] + [dict(e, feature="lower:" + e["feature"], text="lower TF " + e["text"]) for e in sub["evidence"]]
    return {"score": score, "cls": classify(score, ch.s), "evidence": ev, "raw": own["raw"], "lower": sub, "level": "candles"}


def _speed(x):
    return x["size"] / x["bars"] if x["bars"] else None


def _combine(subs, d, s):
    """Sub-legs ⇒ leg चा vote — फक्त candles चा पुरावा, wave count नाही (count = structure vote चं काम):
      motive (leg-दिशेचे sub-legs, आकाराने वजनी), counter (उलट sub-legs सुधारात्मक ⇒ आवेगी पुरावा), pause_time / pause_depth
      (≥ 2 counters असताना), c_like_a (शेवटचा push त्याआधीच्या सर्वात मजबूत push सारखा — candles, वेग, आकार — zigzag चा c ≈ a ⇒
      सुधार; impulse मध्ये wave 5 ≠ wave 3), b_brief (counter
      sub-leg चे bars ÷ आधीच्या push चे bars: wave 2 / 4 थोडके ⇒ आवेग; zigzag चा b लांब ⇒ सुधार), middle_push (≥ 3 pushes: सर्वात
      आवेगी push — candle score × आकार — मधला: wave 3 ⇒ आवेग; पहिला / शेवटचा ⇒ सुधार).
    Motive चालीचा ≥ rollup_veto_share वाटा असलेला सुधारात्मक motive sub-leg ⇒ score ≤ त्याचा score."""
    mot = [x for x in subs if x["dirn"] == d]
    cnt = [x for x in subs if x["dirn"] != d]
    mv = [(x["vote"]["score"], x["size"]) for x in mot if x["vote"]["score"] is not None]
    ms = [v for v, _ in mv]
    cs = [-x["vote"]["score"] for x in cnt if x["vote"]["score"] is not None]       # सुधारात्मक counter ⇒ आवेगी पुरावा
    wsum = sum(w for _, w in mv)
    m = (sum(v * w for v, w in mv) / wsum) if wsum > 0 else None
    msize = sum(x["size"] for x in mot)
    veto = [v for v, w in mv if v <= float(s["a_lo"]) and msize > 0 and w / msize >= float(s["rollup_veto_share"])]
    c = float(np.mean(cs)) if cs else None
    tot = sum(x["bars"] for x in subs)
    ptime = pdepth = None
    if len(cnt) >= int(s["rollup_pause_min_counters"]):                            # एकच थांबा impulse / zigzag वेगळं करत नाही
        ptime = sum(x["bars"] for x in cnt) / tot if tot else None
        pdepth = (sum(x["size"] for x in cnt) / msize) if msize > 0 else None
    def strength(x):                                                                # push ची आवेगी चाल = candle score × आकार
        return (x["vote"]["score"] or 0.0) * x["size"]

    like = None                                                    # शेवटचा push vs त्याआधीचा सर्वात मजबूत push (zigzag: c ≈ a)
    if len(mot) >= 2 and all(x["vote"]["score"] is not None for x in mot):
        last, ref = mot[-1], max(mot[:-1], key=strength)
        v0, v1 = _speed(ref), _speed(last)
        if v0 and v1 and ref["size"] > 0 and last["size"] > 0:
            like = ((1.0 - abs(ref["vote"]["score"] - last["vote"]["score"]) / 2.0) * min(v0, v1) / max(v0, v1)
                    * min(ref["size"], last["size"]) / max(ref["size"], last["size"]))
    brief = [x["bars"] / subs[k - 1]["bars"] for k, x in enumerate(subs) if x["dirn"] != d and k > 0 and subs[k - 1]["bars"]]
    brief = float(np.mean(brief)) if brief else None
    middle = None                                                                   # सर्वात आवेगी push मधला (wave 3)?
    if len(mot) >= 3 and all(x["vote"]["score"] is not None for x in mot):
        top = max(range(len(mot)), key=lambda k: strength(mot[k]))
        middle = 1.0 if 0 < top < len(mot) - 1 else -1.0
    vals = {"motive": m, "counter": c,
            "pause_time": feature_score(ptime, *s["rollup"]["pause_time"]),
            "pause_depth": feature_score(pdepth, *s["rollup"]["pause_depth"]),
            "c_like_a": feature_score(like, *s["rollup"]["c_like_a"]),
            "b_brief": feature_score(brief, *s["rollup"]["b_brief"]),
            "middle_push": middle}
    raws = {"motive": ms, "counter": [-x for x in cs], "pause_time": ptime, "pause_depth": pdepth, "c_like_a": like,
            "b_brief": brief, "middle_push": middle}
    ev = []
    num = den = 0.0
    for k, sc in vals.items():
        lean = LEAN_NEU if sc is None or abs(sc) < 1e-9 else (LEAN_IMP if sc > 0 else LEAN_COR)
        rv = raws[k]
        shown = ("[" + ", ".join(f"{x:+.2f}" for x in rv) + "]") if isinstance(rv, list) else _fmt(rv)
        counted = sc is not None and not (k == "c_like_a" and sc == 0.0)              # एकतर्फी: 0 = पुरावा नाही
        ev.append({"feature": "sub:" + k, "value": rv, "score": sc, "lean": lean, "counted": counted,
                   "text": f"sub-legs {k} {shown} ⇒ {lean}" + ("" if sc is None else f" ({sc:+.2f})")})
        if counted:
            w = float(s["rollup_weights"].get(k, 1.0))
            num, den = num + w * sc, den + w
    for x in subs:
        v = x["vote"]
        ev.append({"feature": "sub-leg", "value": v["score"], "score": None, "lean": v["cls"], "counted": False,
                   "text": f"{'UP' if x['dirn'] > 0 else 'DOWN'} bars {x['i0']}-{x['i1']} ({'motive' if x['dirn'] == d else 'counter'}): "
                           f"{v['cls']}" + ("" if v["score"] is None else f" {v['score']:+.2f}") + f" [{v.get('level')}]"})
    if m is None or den <= 0:
        return {"score": None, "cls": "NA", "evidence": ev, "raw": raws, "subs": subs, "level": "rollup"}
    score = num / den
    if m < float(s["a_hi"]):
        score = min(score, m)                                                       # motive आवेगी नाही ⇒ pause पुरावा leg आवेगी करत नाही
    if veto:
        score = min(score, min(veto))
        ev.append({"feature": "sub:veto", "value": min(veto), "score": None, "lean": LEAN_COR, "counted": False,
                   "text": f"a corrective motive sub-leg carries ≥ {s['rollup_veto_share']} of the leg's travel ⇒ not impulsive"})
    return {"score": score, "cls": classify(score, s), "evidence": ev, "raw": raws, "subs": subs, "level": "rollup"}


def rollup(ch, i0, i1, p0, p1, d, lowers, upto, prev=None, low=None):
    """lowers = leg च्या खालच्या degrees चे pivots, जवळच्यापासून. आत रचना दिसणारा पहिला संच ⇒ sub-legs (प्रत्येक त्याच्या खालच्या
    संचांनी recursive); कुठेच नाही ⇒ lowest degree ⇒ candles."""
    for k, pv in enumerate(lowers):
        pts = RL.inner_points(i0, i1, p0, p1, d, pv, upto)
        if len(pts) > 2:
            break
    else:
        return candle_vote(ch, i0, i1, d, prev, low)
    subs, pseg = [], prev
    for (a, pa), (b, pb) in zip(pts, pts[1:]):
        sd = 1 if pb > pa else -1
        v = rollup(ch, a, b, pa, pb, sd, lowers[k + 1:], upto, pseg, low)
        subs.append({"i0": a, "i1": b, "dirn": sd, "bars": b - a, "size": abs(pb - pa), "vote": v})
        pseg = (a, b)
    return _combine(subs, d, ch.s)


def own_lowers(ch, degree):
    """Reader चे स्वतःचे खालचे pivot संच (जवळच्यापासून). Anatomy नेहमी हेच वापरते — बाहेरची (hand / v1) marking फक्त structure vote
    बदलते, म्हणून चुकीचे pivots candles च्या vote ला दूषित करत नाहीत (दोन votes स्वतंत्र)."""
    return [ch.pivots(ch.s["dc_k"][D]) for D in range(int(degree) - 1, -1, -1)]


def leg_vote(ch, leg, prev=None, low=None, lowers=None):
    """Leg चा anatomy vote: खालचे pivots (default: reader चे स्वतःचे) असतील तर sub-legs चा roll-up, नाहीतर candles (spec §2d)."""
    pb = (prev.i0, prev.i1) if prev is not None else None
    lw = own_lowers(ch, leg.degree) if lowers is None else list(lowers)
    return rollup(ch, leg.i0, leg.i1, leg.p0, leg.p1, leg.dirn, lw, leg.known_bar, pb, low)


def alternatives(ch, leg, prev=None, low=None):
    """Re-read (§3.1): पर्यायी pivots फक्त एक degree खाली (structure.alt_thresholds, स्वतःच्या pivots वर) वापरून roll-up.
    रिटर्न [(k, vote)]."""
    from . import structure as RSt                                         # structure → legs; anatomy → structure (चक्र नाही)
    ks, rest = RSt.alt_thresholds(ch, leg, own_lowers(ch, leg.degree))
    return [(k, leg_vote(ch, leg, prev, low, [ch.pivots(k)] + rest)) for k in ks]
