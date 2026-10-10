"""chart_reader/gap.py — gap theory प्रत्येक दिवशी, प्रत्येक बंद bar वर (KB K13 + भाग H G7; TRADE_KB_FULL_IMPLEMENTATION_PROMPT §4, §4A, §8.1).

`vision/gap_context.build` वर्ग (G0–G5, GX, E), location, acceptance / rejection / undecided (प्रत्येक बंद 15M bar वर पुन्हा) आणि fill %
देतो. इथे त्यावरून trade चा नियम:

  • trade दिशेचा gap (gap दिशा = trade बाजू) ⇒ setup B: **पहिला pullback** येईपर्यंत entry नाही (`GAP_NO_PULLBACK`). Pullback = दिवसाच्या
    running टोकानंतर उलट चाल ≥ `gap_pb_min_mr` × MR, आणि ती gap edge (open) / PDC / trade बाजूचा zone (± `gap_pb_tol_mr` × MR) पर्यंत.
    वर्ग कोणताही (G2 सुद्धा — trend सोबतचा gap; 7 Oct G2 होता). Opening window चा नियम वेगळा (`rules.check`).
  • trade विरुद्ध gap: rejection ⇒ setup A (पुष्टी); acceptance ⇒ विरोध; undecided ⇒ तटस्थ.
  • active area जुन्या न भरलेल्या gap ची कड ⇒ setup C (कमकुवत, confluence).
  • GP पुरावा हेच वापरतो (trade दिशेचा gap pullback शिवाय ⇒ पुष्टी नाही).
  • गोष्ट: आदल्या दिवसाची शेवटची चाल (आकार MR, efficiency) + आजचा gap ⇒ पुष्टी / विरोध / सातत्य.
  • G7 exhaustion gap reversal (`g7`): stretched trend + trend दिशेचा मोठा gap (G5 / E) थेट न तुटलेल्या major HTF zone मध्ये + पहिल्या 2–6
    bars मध्ये rejection ⇒ पहिल्या pullback वर reversal candle. Trend विरुद्ध trade ⇒ स्वतंत्र scorecard (मुख्य side बदलत नाही).

सगळं फक्त बंद bars वरून (no-lookahead). आकडे settings मध्ये, MR च्या पटीत.
"""
import numpy as np
import pandas as pd

DEFAULTS = {
    "gap_pb_min_mr": 1.0,          # pullback = running टोकापासून ≥ हे × MR उलट
    "gap_pb_tol_mr": 0.3,          # … आणि gap edge / PDC / zone पासून ≤ हे × MR पर्यंत पोहोचला
    "gap_story_bars": 8,           # आदल्या दिवसाची "शेवटची चाल" = शेवटचे इतके 15M bars (2 तास)
    "gap_story_weak_er": 0.4,      # त्या चालीची efficiency (net ÷ path) < हे ⇒ कमकुवत
    "gap_story_min_mr": 1.5,       # |net| < हे × MR ⇒ "बाजूला"
    "gap_setup_g7": True,          # KB K13 D → G7 (Abhi 2026-10-08): PAPER मध्ये ON, स्वतंत्र scorecard
    "g7_classes": ["G5", "E"],     # trend दिशेचा मोठा / event gap
    "g7_min_degree": 2,            # major HTF zone = levels_v2 degree ≥ हे (D2 / D3)
    "g7_zone_tol_mr": 0.3,         # open / पहिल्या bars चं टोक zone च्या ± हे × MR मध्ये
    "g7_reject_bars": 6,           # rejection पहिल्या 2–6 bars मध्ये
    "g7_reject_min_bars": 2,
    "g7_wick_min": 0.4,            # zone मधली rejection wick ≥ range च्या हे
    "g7_rev_cl": 0.6,              # pullback नंतरची reversal candle: close location ≥ हे (bull) / ≤ 1 − हे (bear)
    "g7_inv_buffer_mr": 0.25,      # invalidation = gap दिवसाचं टोक ∓ हे × MR
    "g7_min_rr": 3.0,
}


def _s(s):
    return {**DEFAULTS, **(s or {})}


def gap_dir(g):
    if not g or not g.get("has_gap"):
        return 0
    return 1 if g.get("direction") == "up" else -1 if g.get("direction") == "down" else 0


def today_bars(trig):
    """trig मधले शेवटच्या bar च्या दिवसाचे (बंद) bars."""
    if trig is None or not len(trig):
        return trig
    d = pd.to_datetime(trig["timestamp"]).dt.normalize()
    return trig[d == d.iloc[-1]]


def first_pullback(today, gdir, levels, s, mr):
    """trade दिशेच्या gap नंतर पहिला pullback. gdir = gap दिशा (±1); levels = [(नाव, किंमत)] — gap edge / PDC / zone ची जवळची कड.
    Running टोक (gap दिशेने) ज्या bar वर झालं त्यानंतरच्या bar ने उलट ≥ gap_pb_min_mr × MR आणि एखादी level (± tol) गाठली ⇒ seen.
    एकाच bar मधला high / low क्रम माहीत नाही ⇒ टोकाचा bar स्वतः pullback मानत नाही. रिटर्न {seen, at, to, price}."""
    s = _s(s)
    out = {"seen": False, "at": None, "to": None, "price": None}
    if today is None or not len(today) or not gdir or not mr:
        return out
    h, lo = today["high"].to_numpy(float), today["low"].to_numpy(float)
    ts = pd.to_datetime(today["timestamp"]).to_numpy()
    tol = s["gap_pb_tol_mr"] * mr
    ext = lo[0] if gdir < 0 else h[0]
    for k in range(1, len(today)):
        if (gdir < 0 and lo[k] < ext) or (gdir > 0 and h[k] > ext):      # नवं टोक करणारा bar pullback नाही (आत high / low क्रम माहीत नाही)
            ext = lo[k] if gdir < 0 else h[k]
            continue
        back = (h[k] - ext) if gdir < 0 else (ext - lo[k])
        if back >= s["gap_pb_min_mr"] * mr:
            for name, px in levels:
                if px is None:
                    continue
                if (gdir < 0 and px > ext and h[k] >= px - tol) or (gdir > 0 and px < ext and lo[k] <= px + tol):
                    return {"seen": True, "at": str(pd.Timestamp(ts[k])), "to": name, "price": round(float(h[k] if gdir < 0 else lo[k]), 2)}
    return out


def pullback_levels(g, zones, side):
    """Pullback ची लक्ष्यं: gap edge (open), PDC, आणि trade बाजूचे zones (bear ⇒ selling zones ची खालची कड, bull ⇒ buying zones ची वरची)."""
    out = [("gap edge (open)", g.get("open")), ("PDC", g.get("pdc"))]
    want = "RESISTANCE" if side < 0 else "SUPPORT"
    for z in zones or []:
        if z.get("kind") == "solid" and z.get("role") == want and z.get("state") not in ("BROKEN", "DEAD", "MAGNET"):
            out.append((z["id"], float(z["low"] if side < 0 else z["high"])))
    return out


def story(prev, g, s, mr):
    """आदल्या दिवसाची शेवटची चाल + आजचा gap (KB K13 "गोष्ट"). prev = आदल्या दिवसाचे बंद 15M bars."""
    s = _s(s)
    gd = gap_dir(g)
    if prev is None or len(prev) < 2 or not mr:
        return {"prev_move": None, "relation": "none", "line": "आदल्या दिवसाचे bars नाहीत"}
    last = prev.tail(int(s["gap_story_bars"]))
    c = last["close"].to_numpy(float)
    net = float(c[-1] - float(last["open"].iloc[0]))
    path = float(np.abs(np.diff(np.concatenate([[float(last["open"].iloc[0])], c]))).sum()) or 1e-9
    er = abs(net) / path
    size = net / mr
    if abs(size) < s["gap_story_min_mr"]:
        move, word = 0, "बाजूला"
    else:
        move = 1 if net > 0 else -1
        word = ("कमकुवत " if er < s["gap_story_weak_er"] else "ताकदीची ") + ("तेजी" if move > 0 else "घसरण")
    gtxt = "gap नाही" if not gd else ("gap up" if gd > 0 else "gap down")
    if not gd:
        rel, concl = "none", "gap नाही"
    elif move == 0:
        rel, concl = "neutral", "आदल्या दिवशी दिशा नाही ⇒ gap हाच पहिला संकेत"
    elif move == gd:
        rel, concl = "continuation", "त्याच दिशेचं सातत्य (gap टिकतो का ते acceptance वरून)"
    elif er < s["gap_story_weak_er"]:
        rel = "confirms"
        concl = "कमजोरीची पुष्टी" if gd < 0 else "ताकदीची पुष्टी"
    else:
        rel, concl = "opposes", "आदल्या चालीशी विरोध (gap अपयशी होऊ शकतो)"
    return {"prev_move": word, "prev_mr": round(size, 2), "prev_er": round(er, 2), "relation": rel,
            "line": f"गोष्ट [K13]: आदल्या दिवशी शेवटी {word} ({size:+.1f} MR, ER {er:.2f}) + आज {gtxt} = {concl}"}


def read(trig, g, side, zones, active, s, mr, prev=None):
    """प्रत्येक बंद bar वर gap नियम. रिटर्न: gdir, relation, setup (A / B / C / None), pullback, block (reason code / None), gp
    ("confirms" / "opposes" / "neutral"), line, story."""
    s = _s(s)
    g = g or {}
    gd = gap_dir(g)
    base = f"{g.get('class')} gap {g.get('direction')} {g.get('gap_atr')}× ATR · {g.get('location')} · {g.get('behaviour')} · fill {g.get('fill_pct')}%"
    out = {"gdir": gd, "relation": "none", "setup": None, "pullback": None, "block": None, "gp": "neutral",
           "line": "gap नाही / G0", "story": story(prev, g, s, mr)}
    act = (active or {}).get("area") or {}
    if act.get("tool") == "l" and act.get("old"):
        out["setup"] = "C"
    if not gd or not side:
        return out
    if gd == side:
        out["relation"] = "with"
        pb = first_pullback(today_bars(trig), gd, pullback_levels(g, zones, side), s, mr)
        out["pullback"] = pb
        if pb["seen"]:
            out.update(setup="B", gp="confirms", line=f"{base} ⇒ setup B: पहिला pullback {pb['to']} पर्यंत ({pb['at'][11:16]}) ⇒ आता reversal ची वाट")
        else:
            out.update(block="GAP_NO_PULLBACK", line=f"{base} ⇒ trade दिशेचा gap, पहिला pullback अजून नाही ⇒ entry नाही (gap chase)")
        return out
    out["relation"] = "against"
    beh = g.get("behaviour")
    if beh == "rejection":
        out.update(setup=out["setup"] or "A", gp="confirms", line=f"{base} ⇒ trade विरुद्ध gap अपयशी (setup A)")
    elif beh == "acceptance":
        out.update(gp="opposes", line=f"{base} ⇒ trade विरुद्ध gap स्वीकारला")
    else:
        out["line"] = f"{base} ⇒ अजून अनिर्णित"
    return out


# ---------------------------------------------------------------------------------------------------------------------
# G7 exhaustion gap reversal
# ---------------------------------------------------------------------------------------------------------------------
def major_zone_hit(g, today, htf, s, mr):
    """Gap दिशेच्या विरुद्ध भूमिकेचा (gap down ⇒ demand / SUPPORT) न तुटलेला major HTF zone (degree ≥ g7_min_degree) ज्यात open किंवा
    पहिल्या bars चं टोक (± tol) गेलं. रिटर्न zone / None."""
    s = _s(s)
    gd = gap_dir(g)
    if not gd or today is None or not len(today):
        return None
    tol = s["g7_zone_tol_mr"] * mr
    n = min(len(today), int(s["g7_reject_bars"]))
    tip = float(today["low"].iloc[:n].min()) if gd < 0 else float(today["high"].iloc[:n].max())
    o = float(g.get("open"))
    want = "SUPPORT" if gd < 0 else "RESISTANCE"
    best = None
    for z in htf or []:
        if int(z.get("degree") or 0) < int(s["g7_min_degree"]) or z.get("state") in ("BROKEN", "DEAD", "MAGNET"):
            continue
        if z.get("role") and z.get("role") != want:
            continue
        lo_, hi_ = float(z["low"]) - tol, float(z["high"]) + tol
        if lo_ <= o <= hi_ or lo_ <= tip <= hi_:
            if best is None or int(z.get("degree") or 0) > int(best.get("degree") or 0):
                best = z
    return best


def g7(trig, g, htf, trend_dir, s, mr, opening_end=None):
    """G7 state: none / watch (अटी पूर्ण, rejection ची वाट) / rejected (pullback ची वाट) / entry. Trade बाजू = gap विरुद्ध (−gap दिशा).
    trend_dir = HTF trend (±1 / 0); gap trend दिशेचा हवा. opening_end = opening window चा शेवट (Timestamp) — त्याआधी entry नाही."""
    s = _s(s)
    out = {"state": "none", "side": 0, "zone": None, "why": [], "entry": None, "inv": None, "target": None, "rr": None, "line": "G7: —"}
    if not s["gap_setup_g7"]:
        out["line"] = "G7: setting OFF"
        return out
    gd = gap_dir(g)
    cls = g.get("class")
    if not gd or not (cls in s["g7_classes"] or (g.get("event") and "E" in s["g7_classes"])):
        out["line"] = f"G7: नाही (gap {cls or 'G0'}; मोठा / event gap हवा)"
        return out
    if trend_dir and gd != trend_dir:
        out["line"] = "G7: नाही (gap trend दिशेचा नाही)"
        return out
    today = today_bars(trig)
    z = major_zone_hit(g, today, htf, s, mr)
    if z is None:
        out["line"] = "G7: नाही (gap major HTF zone मध्ये नाही)"
        return out
    side = -gd
    out.update(state="watch", side=side, zone={k: z.get(k) for k in ("id", "low", "high", "degree", "tf")})
    o, h, lo, c = (today[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    gap_open = float(g["open"])
    n = len(today)
    # rejection: पहिल्या 2–6 bars मध्ये; gap दिशेचं टोक त्यानंतर ≥ 2 bars नवं नाही, आणि (zone मध्ये wick ≥ g7_wick_min किंवा close परत open पलीकडे)
    rej = None
    lim = min(n, int(s["g7_reject_bars"]))
    for k in range(int(s["g7_reject_min_bars"]) - 1, lim):
        seg_tip = lo[: k + 1].min() if gd < 0 else h[: k + 1].max()
        tip_k = int(np.argmin(lo[: k + 1]) if gd < 0 else np.argmax(h[: k + 1]))
        if k - tip_k < 1:
            continue                                                       # टोक अजून चालू ⇒ extension अपयशी नाही
        rng = max(h[tip_k] - lo[tip_k], 1e-9)
        wick = ((min(o[tip_k], c[tip_k]) - lo[tip_k]) if gd < 0 else (h[tip_k] - max(o[tip_k], c[tip_k]))) / rng
        reclaim = (c[k] > gap_open) if gd < 0 else (c[k] < gap_open)
        if wick >= s["g7_wick_min"] or reclaim:
            rej = {"bar": k, "tip": float(seg_tip), "tip_bar": tip_k, "wick": round(float(wick), 2), "reclaim": bool(reclaim)}
            break
    if rej is None:
        out["line"] = f"G7 watch: gap {cls} major zone {z.get('id')} मध्ये — rejection ची वाट (पहिले {lim} bars)"
        return out
    out["state"] = "rejected"
    out["rejection"] = rej
    # पहिला pullback: rejection नंतर reversal दिशेने running टोक, मग उलट चाल (higher low / lower high) जी दिवसाचं टोक तोडत नाही, आणि
    # मग reversal candle (CL). पहिल्या recovery candle वर entry नाही ⇒ pullback चा किमान एक bar हवा.
    run = rej["bar"]
    pb_k = None
    for k in range(rej["bar"] + 1, n):
        if (side > 0 and lo[k] <= rej["tip"]) or (side < 0 and h[k] >= rej["tip"]):
            out.update(state="none", line="G7: दिवसाचं टोक तुटलं ⇒ zone टिकला नाही")
            return out
        if pb_k is not None:
            rng = max(h[k] - lo[k], 1e-9)
            cl = (c[k] - lo[k]) / rng
            if (cl >= s["g7_rev_cl"] and c[k] > o[k]) if side > 0 else (cl <= 1 - s["g7_rev_cl"] and c[k] < o[k]):
                if k < n - 1:                                              # एक setup = एक entry: संधी आधीच येऊन गेली
                    out.update(state="done", line=f"G7: reversal candle आधीच ({pd.Timestamp(today['timestamp'].iloc[k]):%H:%M})")
                    return out
                be = pd.Timestamp(today["bar_end"].iloc[k]) if "bar_end" in today else None
                if opening_end is not None and be is not None and be <= opening_end:
                    out["line"] = "G7: opening window — entry नाही"
                    return out
                entry = float(c[k])
                inv = rej["tip"] - side * s["g7_inv_buffer_mr"] * mr
                tgt = float(g.get("pdc"))
                rr = abs(tgt - entry) / max(abs(entry - inv), 1e-9) if (tgt - entry) * side > 0 else 0.0
                out.update(entry=round(entry, 2), inv=round(inv, 2), target=round(tgt, 2), rr=round(rr, 2))
                if rr >= s["g7_min_rr"]:
                    out.update(state="entry", line=f"G7 ENTRY: exhaustion gap {cls} → zone {z.get('id')} (D{z.get('degree')}) · rejection "
                                                     f"{'reclaim' if rej['reclaim'] else 'wick'} · pullback नंतर reversal · SL {inv:,.1f} · "
                                                     f"target PDC {tgt:,.1f} · R:R {rr:.1f}")
                else:
                    out.update(state="rejected", line=f"G7: reversal आला पण R:R {rr:.1f} < {s['g7_min_rr']:g}")
                return out
            continue
        if (side > 0 and h[k] > h[run]) or (side < 0 and lo[k] < lo[run]):
            run = k                                                        # recovery चालू (पहिल्या recovery candle वर entry नाही)
        elif (side > 0 and c[k] < c[k - 1]) or (side < 0 and c[k] > c[k - 1]):
            pb_k = k                                                       # पहिला pullback bar
    out["line"] = (f"G7 rejected: zone {z.get('id')} मध्ये rejection ({'reclaim' if rej['reclaim'] else 'wick'}) — पहिल्या pullback ची वाट"
                   if pb_k is None else f"G7: pullback चालू — reversal candle ची वाट")
    return out
