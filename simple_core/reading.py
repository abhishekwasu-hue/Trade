"""simple_core/reading.py — टप्पा B reading layer (नकाशा भाग I; Abhi G-MAP1 निर्णय 2026-10-09). Simple Core (area → pause → commitment)
बदलत नाही; त्याच्या candidate signal वर, decision bar पर्यंतच्या data वरूनच (no-lookahead):

  impulse (निर्णय 9 / Phase B §2.4): ज्या correction च्या शेवटी trade घेतो त्याच correction च्या आधीचा impulse — trade-degree
      (market_state, 15M ATR × trade_swing_atr_mult) confirmed pivots वरून:
        S = trade दिशेचा सगळ्यात अलीकडचा confirmed pivot जो area च्या पलीकडे आहे (bear ⇒ H, area च्या वर) — impulse ची सुरुवात;
        E = S नंतर decision bar पर्यंतचं सगळ्यात टोकाचं (bear ⇒ low) — तो confirmed pivot हवा — correction origin = impulse end.
      दोन्ही pivots decision bar आधी confirm. नाहीतर impulse = None (`IMPULSE_NA`; target impulse_end नाही).
  correction: E नंतरचे confirmed pivots + चालू टोक ⇒ legs; Gray-2 (नकाशा P2): zigzag / flat ⇒ A, B, C दिसतात आणि C ≥ A चं टोक;
      triangle ⇒ 5 legs (आकुंचन); counter-move स्वतः 5 waves (वाढती टोकं) ⇒ A ⇒ gray; flag (G8) ⇒ रचना पुरेशी.
  S4 / S7 (नकाशा I8.3, breaks.py): correction ने S चा real break ⇒ S4 (फक्त flip retest); S पलीकडे गेला पण real break नाही ⇒ S7.
  S3 (निर्णय 3, §2.2): impulse मधला शेवटचा confirmed 1H LH (bear impulse) / HL (bull) — 1H pivots = market_state trend pivots —
      correction ने breaks.py real break (1H frame) ने तोडला, आणि S real-broken नाही ⇒ S3 ⇒ Gray-1. Impulse मध्ये confirmed 1H pivot
      नाही ⇒ `S3_NO_1H_PIVOT` (S3 नाही; साधा pullback म्हणून वाचन — ढिला default, अहवालात वेगळा).
  S2 खोल (retrace ≥ 61.8%), S5 flag (G8 area), S6 बाजूचा (legs ≥ 3 आणि correction bars > impulse bars), S8 (with-trend legs लहान),
      S10 gap दिवस, S12 15:15 — फक्त नोंद / पुरावा (I2 precedence: जास्त कडक जिंकते).
  commit_vs_impulse (निर्णय 1, §2.1): commitment range ÷ impulse मधल्या बंद 15M bars चा median range — फक्त report, gate नाही.
  gray धोरण: `get_gray_policy(date)` — Evening Plan PR येईपर्यंत नेहमी block.
नवे आकडे नाहीत: 0.618 (S2) = नकाशा P4 / KB [Abhi]; बाकी सगळं व्याख्या (A1 register).
"""
import numpy as np
import pandas as pd

S2_DEEP = 0.618          # नकाशा P4: 61.8–80% valid खोल [Abhi]; 80–100% कमकुवत


def get_gray_policy(date=None):
    """Abhi चं त्या दिवसाचं gray धोरण. Evening Plan PR (plan reply) येईपर्यंत नेहमी block (नकाशा P2: धोरण नाही ⇒ block)."""
    return {"policy": "block", "dir": None, "source": "default"}


def trade_pivots(trig, k, s_ms=None):
    """Trade-degree confirmed pivots (market_state F3 सारखेच), फक्त conf ≤ k."""
    from market_state import core as MC
    s = {**MC.DEFAULTS, **(s_ms or {})}
    pv = MC.label(MC.pivots(trig.iloc[:k + 1].reset_index(drop=True), s["trade_swing_atr_mult"], s["trade_tf"]))
    return [p for p in pv if p["conf"] <= k]


def trade_impulse(trig, piv, side, k, area, tol, lim=None):
    """Phase B §2.4. रिटर्न {start, end, start_idx, end_idx, start_ts, end_ts, dir} किंवा None (+ कारण). lim = pause सुरू होण्याआधीचा
    bar — origin शोध (S, lim] मध्येच (pause / commitment चे bars correction च्या शेवटाचे, origin नाहीत)."""
    lim = k if lim is None else min(int(lim), k)
    h, lo = trig["high"].to_numpy(float), trig["low"].to_numpy(float)
    skind, ekind = ("H", "L") if side < 0 else ("L", "H")
    for S in reversed([p for p in piv if p["kind"] == skind]):
        beyond = S["price"] >= area["high"] + tol if side < 0 else S["price"] <= area["low"] - tol
        if not beyond or S["idx"] >= lim:
            continue
        oseg = slice(S["idx"] + 1, lim + 1)
        e = S["idx"] + 1 + (int(np.argmin(lo[oseg])) if side < 0 else int(np.argmax(h[oseg])))
        E = next((p for p in piv if p["kind"] == ekind and p["idx"] == e), None)
        if E is None:
            return None, "IMPULSE_NA: correction origin अजून confirmed pivot नाही"
        return {"dir": side, "start": float(S["price"]), "end": float(E["price"]), "start_idx": int(S["idx"]), "end_idx": int(E["idx"]),
                "start_ts": pd.Timestamp(trig["timestamp"].iloc[S["idx"]]), "end_ts": pd.Timestamp(trig["timestamp"].iloc[E["idx"]])}, ""
    return None, "IMPULSE_NA: area पलीकडचा impulse start pivot नाही"


def correction_legs(trig, piv, imp, k, area_type=""):
    """E नंतरची correction: tops / bottoms (counter दिशेची टोकं) ⇒ legs, Gray-2 निकाल. रिटर्न dict."""
    side = imp["dir"]
    h, lo = trig["high"].to_numpy(float), trig["low"].to_numpy(float)
    ckind = "H" if side < 0 else "L"                                         # counter-move चं टोक
    cps = [p for p in piv if p["idx"] > imp["end_idx"]]
    tops = [p["price"] for p in cps if p["kind"] == ckind]
    last = cps[-1] if cps else None
    if last is None or last["kind"] != ckind:                               # चालू counter टोक (tentative)
        a = (last["idx"] + 1) if last else imp["end_idx"] + 1
        if a <= k:
            tops.append(float(h[a:k + 1].max()) if side < 0 else float(lo[a:k + 1].min()))
    ext = (max(tops) if side < 0 else min(tops)) if tops else None
    size = abs(imp["start"] - imp["end"])
    retrace = round(abs(ext - imp["end"]) / size, 3) if (ext is not None and size > 0) else None
    out = {"tops": [round(t, 2) for t in tops], "legs": 2 * len(tops) - 1 if tops else 0, "retrace": retrace, "complete": False,
           "why": "", "bars": int(k - imp["end_idx"])}
    xs = [(-t if side > 0 else t) for t in tops]                            # x-space: counter दिशा वर
    bots = [p["price"] for p in cps if p["kind"] != ckind]
    xb = [(-b if side > 0 else b) for b in bots]
    out["bottoms"] = [round(b, 2) for b in bots]
    if "flag channel" in str(area_type):
        out.update(complete=True, why="flag (G8) रचना")
    elif len(xs) < 2:
        out["why"] = "Gray-2: correction चे legs पुरेसे दिसत नाहीत (फक्त A)"
    elif len(xs) >= 3 and all(b > a for a, b in zip(xs, xs[1:])) and len(xb) >= 2 and xb[1] > xs[0]:
        out["why"] = "Gray-2: counter-move स्वतः 5 waves (वाढती टोकं, wave 4 चा wave 1 शी overlap नाही) ⇒ A"   # R4 / KB A-end ban
    elif len(xs) >= 3 and all(b < a for a, b in zip(xs, xs[1:])):
        out.update(complete=True, why="triangle (आकुंचन, 5 legs)")
    elif max(xs[1:]) >= xs[0]:
        out.update(complete=True, why="A-B-C: C ने A चं टोक गाठलं / ओलांडलं")
    else:
        out["why"] = "Gray-2: truncated C (A चं टोक गाठलं नाही)"
    return out


def origin_state(trig, imp, k, es=None):
    """S4 / S7: correction ने impulse start (S) चा real break (breaks.py, रचना ⇒ 3-close सह) ⇒ S4; पलीकडे गेला पण real break नाही ⇒ S7."""
    from elliott import breaks as BR
    from elliott import settings as ES
    es = es or dict(ES.DEFAULTS)
    side = imp["dir"]
    start = imp["end_idx"] + 1
    if start > k:
        return None
    fr = trig.iloc[:k + 1].reset_index(drop=True)
    mr = BR.median_range(fr, es["median_range_n"])
    b = BR.first_real_break(fr, start, imp["start"], "above" if side < 0 else "below", es, mr=mr, end=k)
    if b is not None:
        return "S4"
    h, lo = fr["high"].to_numpy(float), fr["low"].to_numpy(float)
    beyond = (h[start:k + 1] > imp["start"]).any() if side < 0 else (lo[start:k + 1] < imp["start"]).any()
    return "S7" if beyond else None


def s3_trigger(h1, trig, imp, asof, es=None):
    """§2.2: impulse (S→E) मधला शेवटचा confirmed 1H LH / HL, correction ने 1H real break (breaks.py) ने तोडला ⇒ S3. रिटर्न
    {"s3": bool, "code": None | "S3_NO_1H_PIVOT", "pivot": price | None}."""
    from elliott import breaks as BR
    from elliott import settings as ES
    from market_state import core as MC
    es = es or dict(ES.DEFAULTS)
    side = imp["dir"]
    asof = pd.Timestamp(asof)
    f = h1[pd.to_datetime(h1["bar_end"]) <= asof].reset_index(drop=True)
    if len(f) < 20:
        return {"s3": False, "code": "S3_NO_1H_PIVOT", "pivot": None}
    pv = MC.label(MC.pivots(f, MC.DEFAULTS["trend_swing_atr_mult"], "1h"))
    t0, t1 = imp["start_ts"], imp["end_ts"]
    want = "H" if side < 0 else "L"                                          # bear impulse ⇒ आतला LH; bull ⇒ HL
    inner = [p for p in pv if p["kind"] == want and t0 < pd.Timestamp(p["ts"]) < t1 and p["conf"] <= len(f) - 1]
    if not inner:
        return {"s3": False, "code": "S3_NO_1H_PIVOT", "pivot": None}
    p = inner[-1]
    e_idx = int(np.searchsorted(pd.to_datetime(f["timestamp"]).to_numpy(), np.datetime64(t1), side="right"))
    mr = BR.median_range(f, es["median_range_n"])
    b = BR.first_real_break(f, e_idx, float(p["price"]), "above" if side < 0 else "below", es, mr=mr, end=len(f) - 1)
    return {"s3": b is not None, "code": None, "pivot": round(float(p["price"]), 2)}


def commit_vs_impulse(trig, imp, commitment):
    """§2.1 (फक्त report): commitment range ÷ impulse span मधल्या बंद 15M bars चा median range. Impulse नाही ⇒ None (NA)."""
    if not imp or not commitment:
        return None
    seg = trig.iloc[imp["start_idx"]:imp["end_idx"] + 1]
    if not len(seg):
        return None
    med = float(np.median((seg["high"] - seg["low"]).to_numpy(float)))
    rng = float(commitment["high"]) - float(commitment["low"])
    return round(rng / med, 3) if med > 0 else None


def with_trend_shrinking(piv, side, n=3):
    """S8: शेवटचे n with-trend legs लहान होत आहेत का (trade-degree confirmed pivots)."""
    legs = []
    for a, b in zip(piv, piv[1:]):
        if (b["price"] - a["price"]) * side > 0:
            legs.append(abs(b["price"] - a["price"]))
    legs = legs[-n:]
    return len(legs) == n and all(y < x for x, y in zip(legs, legs[1:]))


PRECEDENCE = ("S4", "S3", "S7", "S8", "S2", "S5", "S6", "S1")                # I2: जास्त कडक आधी (S4/S3 Gray / बंधन)


def situation(flags):
    """flags = {S#: True} ⇒ (मुख्य S#, सगळे). I2: S2 + S3 ⇒ S3; S5 + S8 ⇒ S8; S4 + S10/S12 ⇒ S4 (S10/S12 वेळ / पुरावा)."""
    on = [s for s in PRECEDENCE if flags.get(s)]
    extra = [s for s in ("S9", "S10", "S12") if flags.get(s)]
    main = on[0] if on else ("S9" if flags.get("S9") else "S1")
    return main, on + extra


def read_signal(trig, h1, sig, area_full, mr, s, asof, piv=None, gap=None, es=None):
    """Simple Core candidate signal ⇒ reading (S#, gray, impulse, legs, commit_vs_impulse). area_full = engine चा area (zones सह)."""
    side = int(sig["side"])
    k = len(trig) - 1
    piv = piv if piv is not None else trade_pivots(trig, k)
    tol = float(s["area_tol_mr"]) * float(mr)
    ts = pd.to_datetime(trig["timestamp"]).to_numpy()
    p_from = sig.get("pause_from") or sig["bar_start"]
    lim = int(np.searchsorted(ts, np.datetime64(pd.Timestamp(p_from)))) - 1   # pause / commitment आधीचा bar
    imp, why_na = trade_impulse(trig, piv, side, k, area_full, tol, lim=lim)
    r = {"impulse": None, "impulse_na": why_na or None, "S": "S1", "flags": [], "gray": None, "gray_why": "", "legs": None,
         "commit_vs_impulse": None, "s3": None}
    fl = {}
    hhmm = pd.Timestamp(sig["bar_start"]).strftime("%H:%M")
    if hhmm >= "15:15":
        fl["S12"] = True
    if gap and gap.get("has_gap"):
        fl["S10"] = True
    if "flag channel" in str(sig["area"].get("type", "")):
        fl["S5"] = True
    if with_trend_shrinking(piv, side):
        fl["S8"] = True
    if imp is None:                                                          # correction ओळखता येत नाही ⇒ संपल्याचं ठरवता येत नाही
        r.update(S=situation(fl)[0], flags=situation(fl)[1], gray="Gray-2", gray_why=f"Gray-2: {why_na}")
        return r
    r["impulse"] = {kk: (str(v) if isinstance(v, pd.Timestamp) else v) for kk, v in imp.items()}
    legs = correction_legs(trig, piv, imp, k, sig["area"].get("type", ""))
    r["legs"] = legs
    os_ = origin_state(trig, imp, k, es)
    if os_:
        fl[os_] = True
    s3 = s3_trigger(h1, trig, imp, asof, es) if h1 is not None else {"s3": False, "code": "S3_NO_1H_PIVOT", "pivot": None}
    r["s3"] = s3
    if s3["s3"] and os_ != "S4":
        fl["S3"] = True
    if legs["retrace"] is not None and legs["retrace"] >= S2_DEEP:
        fl["S2"] = True
    if legs["legs"] >= 3 and legs["bars"] > (imp["end_idx"] - imp["start_idx"]):
        fl["S6"] = True
    main, allf = situation(fl)
    r.update(S=main, flags=allf, commit_vs_impulse=commit_vs_impulse(trig, imp, sig.get("commitment")))
    if main == "S3":
        r.update(gray="Gray-1", gray_why=f"S3: impulse मधला 1H {'LH' if side < 0 else 'HL'} {s3['pivot']:,.1f} real-broken — reaction उघडा")
    elif main == "S4":
        r.update(gray="S4", gray_why="S4: impulse start चा real break — फक्त flip retest (break दिशेने)")
    elif not legs["complete"]:
        r.update(gray="Gray-2", gray_why=legs["why"])
    return r
