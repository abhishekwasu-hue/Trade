"""correction/reader.py — Correction Reader (नकाशा भाग II) चं shadow वाचन: एका decision bar साठी `correction_read`.

🎓 क्रम (spec §0.2): 0 नकाशा संदर्भ (पालक दिशा, Gray-1) → 1 व्याख्यात्मक अटी (§2.3) → 2 pattern (§3, §4) → 3 शेवटचा leg हजर (§4) →
4 खरा area (§6) → 5 price failure (§7) → 6 risk (§8). स्वभाव मापक, खोली, गुणोत्तरं, completion zone = पुरावे (grade), gate नाहीत;
अपवाद: खोली 80–100% ⇒ फक्त sweep trigger. Output चा क्रम = vision checklist चे 12 मुद्दे (परिशिष्ट A).

एकच अंमलबजावणी (§0.3): elliott count engine (preferred / alternate, टप्पा B चा count स्रोत), market_state (trend, protected, impulse —
तुलना), chart_reader areas / zones / sloping() (12 साधनं), chart_reader.reversal composite (rejection), breaks.py (origin real break —
market_state.correction मधून). नवं Elliott engine नाही, नवे thresholds नाहीत. सगळं फक्त decision bar च्या close पर्यंतच्या data वर.
"""
import numpy as np
import pandas as pd

from . import settings as CRS

ITEMS = {1: "Weekly + Daily स्थिती", 2: "1H: trend, protected, impulse", 3: "Impulse खरा", 4: "स्वभाव (correction की नवी चाल)",
         5: "Pattern", 6: "पूर्णता (शेवटचा leg)", 7: "खरा area", 8: "खोली", 9: "Price failure", 10: "Risk / R:R", 11: "संदर्भ",
         12: "पक्के नियम"}
GATE_ORDER = (1, 4, 5, 6, 7, 9, 10, 12)                                  # §0.2 चा क्रम (item क्रमांकात)
SOLID_TOOLS = ("a", "b", "c", "d", "e", "f", "k")                        # spec §6 तक्ता
WEAK_TOOLS = ("j", "l")
RULER_TOOLS = ("g", "h", "i")
TOOL_MR = {"a": "swing cluster", "b": "flip", "c": "base", "d": "range edge", "e": "liquidity", "f": "trendline", "g": "channel",
           "h": "Fibonacci", "i": "C = A", "j": "round number", "k": "PDH / PDL / PDC", "l": "gap edge"}
STATE_MR = {"final_leg_present": "शेवटचा leg हजर", "final_leg_in_progress": "शेवटचा leg चालू", "final_leg_short": "शेवटचा leg लहान (Gray-2)",
            "forming_A": "A चालू", "forming_B": "B चालू", "in_X": "X चालू", "in_triangle": "triangle च्या आत", "k_is_five": "K स्वतः 5 waves",
            "invalid": "नियम मोडला", "not_identified": "ओळखता येत नाही"}
PAT_MR = {"zigzag": "zigzag", "flat": "flat", "triangle": "triangle", "wxy": "W-X-Y", "impulse": "impulse (5)", "lead_diag": "leading diagonal",
          "end_diag": "ending diagonal"}
MOTIVE = ("impulse", "lead_diag", "end_diag")
LAST = {"zigzag": "C", "flat": "C", "triangle": "E", "wxy": "Y"}
FIRST_END = {"zigzag": "A", "flat": "A", "triangle": None, "wxy": "W"}


def _ts(x):
    return None if x is None else pd.Timestamp(x)


def _idx(fr, t):
    """frame मधला bar जिथे t (bar start) येतो (≤ t चा शेवटचा)."""
    tsx = pd.to_datetime(fr["timestamp"]).to_numpy(dtype="datetime64[ns]")
    return int(np.clip(np.searchsorted(tsx, np.datetime64(pd.Timestamp(t), "ns"), side="right") - 1, 0, max(len(fr) - 1, 0)))


def frames(df1m, asof):
    """फक्त बंद bars (bar_end ≤ asof): 15M (trigger), 1H, Daily, Weekly (पूर्ण आठवडे)."""
    from chart_reader import evaluate as EV
    from elliott import own_tf as OT
    asof = pd.Timestamp(asof)
    cut = df1m[pd.to_datetime(df1m["timestamp"]) + pd.Timedelta(minutes=1) <= asof].reset_index(drop=True)
    d = OT.daily_frame(cut)
    d = d[pd.to_datetime(d["bar_end"]) <= asof].reset_index(drop=True) if len(d) else d
    w = OT.weekly_frame(d)
    w = w[pd.to_datetime(w["bar_end"]) <= asof].reset_index(drop=True) if len(w) else w
    return cut, {"15M": EV.frame(df1m, "15m", asof), "1H": EV.frame(df1m, "1h", asof), "D": d, "W": w}


# ---------------------------------------------------------------------------------------------------------------- 1: HTF
def htf_state(fr, s_ms=None):
    """Weekly / Daily: market_state.trend त्याच TF च्या bars वर (त्याच TF चे swings / protected). Context फक्त."""
    import market_state.core as MC
    out = {}
    for tf, key in (("W", "weekly"), ("D", "daily")):
        f = fr[tf]
        if f is None or len(f) < 8:
            out[key] = {"dir": 0, "state": "data अपुरा", "protected": None, "swings": []}
            continue
        tr = MC.trend(f.reset_index(drop=True), {**(s_ms or {}), "trend_tf": "1d", "trend_swing_atr_mult": 1.0})
        sw = [{"ts": str(p["ts"]), "price": round(float(p["price"]), 2), "kind": p["kind"], "label": p.get("label")} for p in tr["swings"][-8:]]
        out[key] = {"dir": int(tr["dir"]), "state": tr["state"], "swings": sw,
                    "protected": None if not tr.get("protected") else {"price": round(float(tr["protected"]["price"]), 2),
                                                                       "ts": str(tr["protected"]["ts"]), "kind": tr["protected"]["kind"]}}
    return out


def _dir_mr(d):
    return {1: "वर (HH / HL)", -1: "खाली (LH / LL)", 0: "range"}.get(int(d or 0), "range")


# ---------------------------------------------------------------------------------------------------------------- I आणि K
def impulse_and_hypotheses(df1m, asof, ms, es=None, md_snap=None):
    """I (preferred count मधून; market_state.impulse तुलना) आणि K चे hypotheses (count degree च्या एक खालच्या degree वर E पासून सुरू
    होणारे nodes; नसेल ⇒ त्याच degree वर). रिटर्न dict."""
    from simple_core import count_source as CSRC
    imp_ms = ms.get("impulse")
    out = {"I": None, "I_ms": None, "I_source": None, "E": None, "degree": None, "k_degree": None, "parent": None, "hyps": [],
           "count_tie": None, "why": ""}
    if not imp_ms:
        out["why"] = "market_state: trade-degree impulse नाही"
        return out
    out["I_ms"] = {"dir": int(imp_ms["dir"]), "from": float(imp_ms["from"]), "to": float(imp_ms["to"]), "from_ts": str(imp_ms["from_ts"]),
                   "to_ts": str(imp_ms["to_ts"])}
    e_ts = pd.Timestamp(imp_ms["to_ts"])
    side_k = -int(imp_ms["dir"])                                           # K ची दिशा = I च्या उलट
    md, snap = md_snap if md_snap is not None else CSRC.engine(df1m, asof, es)
    out["E"] = {"ts": str(e_ts), "price": float(imp_ms["to"])}
    I = dict(out["I_ms"])
    out["I_source"] = "market_state"
    if md is None:
        out["I"], out["why"] = I, f"count engine अपयश: {snap}"
        return out
    cnt = CSRC.read(df1m, asof, e_ts, int(imp_ms["dir"]), es, md_snap=(md, snap))
    out["degree"] = cnt.get("degree")
    out["parent"] = {"preferred": cnt.get("preferred"), "alternate": cnt.get("alternate"), "parent_dir": cnt.get("parent_dir"),
                     "S11": cnt.get("S11"), "why": cnt.get("why"), "count_tie": cnt.get("count_tie")}
    pref = cnt.get("preferred") or {}
    pts = pref.get("points") or []
    if len(pts) >= 2 and abs(pd.Timestamp(pts[-1][0]) - e_ts) <= pd.Timedelta(hours=2):
        a, b = pts[-2], pts[-1]                                            # parent ची चालू wave E पासून ⇒ आधीची wave = I
        if (b[1] - a[1]) * int(imp_ms["dir"]) > 0:
            I = {"dir": int(imp_ms["dir"]), "from": float(a[1]), "to": float(b[1]), "from_ts": str(a[0]), "to_ts": str(b[0])}
            out["I_source"] = "preferred count"
    out["I"] = I
    deg = cnt.get("degree")
    cands = []
    for d in ([deg - 1, deg] if deg is not None else sorted(snap.degrees, reverse=True)):
        v = snap.degrees.get(d)
        if v is None or d not in md:
            continue
        tol = pd.Timedelta(minutes=30 if md[d]["tf"] in ("5m", "15m") else 120)   # count_source.read ची same-pivot सहनशीलता
        for n in v.nodes:
            if abs(pd.Timestamp(n.points[0].ts) - e_ts) <= tol and int(n.direction) == side_k:
                cands.append(n)
        if cands:
            out["k_degree"] = int(d)
            break
    cands.sort(key=lambda n: -float(n.joint_score or 0.0))
    if len(cands) >= 2 and abs(float(cands[0].joint_score or 0) - float(cands[1].joint_score or 0)) <= CSRC.TIE_EPS:
        out["count_tie"] = [f"{n.pattern}/{n.current_wave}" for n in cands if abs(float(n.joint_score or 0) - float(cands[0].joint_score or 0))
                            <= CSRC.TIE_EPS]
    out["hyps"] = cands[:4]
    out["md"] = md
    return out


def _labels(n):
    """Node ⇒ labels [{label, ts, price, tentative}] (origin वगळून). चालू wave चं टोक = tentative."""
    from elliott.patterns import LABELS
    lab = LABELS[n.pattern]
    out = [{"label": lab[i], "ts": str(pd.Timestamp(p.ts)), "price": round(float(p.price), 2), "tentative": False}
           for i, p in enumerate(n.points[1:])]
    t = n.tentative
    if t is not None and len(out) < len(lab):
        out.append({"label": n.current_wave, "ts": str(pd.Timestamp(t.ts)), "price": round(float(t.price), 2), "tentative": True})
    return out


def lower_degree_against(md, k_deg, c_start_ts, c_dir, asof, price_now):
    """§4 "विरोधात": C (शेवटचा leg) च्या आत lower degree (Dk−1) चे पहिले तीन sub-legs confirmed (तिसऱ्याचा शेवट confirmed pivot) आणि
    भाव आता चौथ्या sub-leg मध्ये (उलट दिशेने) ⇒ True. Pivots पुरेसे नाहीत / Dk−1 नाही ⇒ None ("अज्ञात", gate नाही)."""
    from elliott import swings as W
    if md is None or k_deg is None or (k_deg - 1) not in md:
        return None
    piv = [p for p in W.known_at(md[k_deg - 1]["confirmed"], asof) if pd.Timestamp(p.ts) > pd.Timestamp(c_start_ts)]
    if len(piv) < 3:
        return None
    if len(piv) == 3:
        p3 = piv[2]
        want = "H" if c_dir > 0 else "L"
        if p3.kind == want and (float(price_now) - float(p3.price)) * c_dir < 0:
            return True
    return False


def hypothesis_state(n, labels, k_dir, area_failure=False, against=None, s5=False):
    """§4 क्रम: invalid → forming_* → final_leg_in_progress → final_leg_present → final_leg_short."""
    p, w = n.pattern, n.current_wave
    if p in MOTIVE:
        return "k_is_five" if w == "5" and p == "impulse" else "forming_A"
    if p == "triangle":
        return "in_triangle" if w != "E" else ("final_leg_in_progress" if against else "final_leg_present")
    if p == "wxy" and w == "X":
        return "in_X"
    if w in ("A", "W"):
        return "forming_A"
    if w == "B":
        return "forming_B"
    first = FIRST_END.get(p)
    a_end = next((x["price"] for x in labels if x["label"] == first), None)
    last = next((x for x in labels if x["label"] == LAST[p]), None)
    if a_end is None or last is None:
        return "not_identified"
    reached = (last["price"] - a_end) * k_dir >= 0                       # P2: C ने A चं टोक गाठलं / ओलांडलं
    if against:
        return "final_leg_in_progress"
    if reached:
        return "final_leg_present"
    if area_failure:
        return "final_leg_short"
    return "final_leg_in_progress"


# ---------------------------------------------------------------------------------------------------------------- 4: स्वभाव
def _rsi(c, n):
    d = np.diff(c, prepend=c[0])
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    a = 1.0 / n
    ru = pd.Series(up).ewm(alpha=a, adjust=False).mean().to_numpy()
    rd = pd.Series(dn).ewm(alpha=a, adjust=False).mean().to_numpy()
    return 100 - 100 / (1 + ru / np.maximum(rd, 1e-9))


def character(trig, I, k_ext_idx, labels, mr, s, s_ms):
    """§2.1 मापक (decision bar पर्यंत). प्रत्येक ⇒ "correction सारखा" / "नवी चाल सारखी" / "तटस्थ" (तुलना 1 शी = व्याख्या). Overlap नोंद."""
    import market_state.core as MC
    ia, ie = _idx(trig, I["from_ts"]), _idx(trig, I["to_ts"])
    j = len(trig) - 1
    out = {"rows": [], "reversal_evidence": None}
    if ie <= ia or j <= ie:
        return out
    h, lo, c, o = (trig[k].to_numpy(float) for k in ("high", "low", "close", "open"))
    i_bars, k_bars = ie - ia, j - ie
    i_size, k_size = abs(I["to"] - I["from"]), abs(float(h[ie + 1:j + 1].max() if I["dir"] < 0 else lo[ie + 1:j + 1].min()) - I["to"])

    def row(name, val, corr_like, note=""):
        v = "तटस्थ" if corr_like is None else ("correction सारखा" if corr_like else "नवी चाल सारखी")
        out["rows"].append({"name": name, "value": val, "verdict": v, "note": note})
    tr = k_bars / i_bars
    row("वेळ (K ÷ I bars)", round(tr, 2), tr > 1.0)
    sp = (k_size / max(k_bars, 1)) / (i_size / max(i_bars, 1)) if i_size > 0 else None
    row("वेग (K ÷ I)", None if sp is None else round(sp, 2), None if sp is None else sp < 1.0)
    er_i, er_k = MC.efficiency(trig, ia, ie), MC.efficiency(trig, ie, j)
    row("Efficiency (K वि. I)", f"{er_k} / {er_i}", er_k < er_i)
    rng = h - lo
    legs = [_idx(trig, x["ts"]) for x in labels]
    if len(legs) >= 2:
        first = rng[ie + 1:legs[0] + 1].mean() if legs[0] > ie else np.nan
        lastr = rng[legs[-2] + 1:j + 1].mean() if legs[-2] < j else np.nan
        rc = lastr / first if first and np.isfinite(first) and np.isfinite(lastr) else None
        row("Range आकुंचन (शेवटचा leg ÷ पहिला)", None if rc is None else round(float(rc), 2), None if rc is None else rc < 1.0)
    rci = rng[ie + 1:j + 1].mean() / rng[ia + 1:ie + 1].mean() if ie > ia else None
    row("Range (K ÷ I)", None if rci is None else round(float(rci), 2), None if rci is None else rci < 1.0)
    ov = MC.overlap_ratio(trig, ie + 1, j)
    out["rows"].append({"name": "Overlap (फक्त नोंद)", "value": ov, "verdict": "नोंद", "note": "G-MAP1 निर्णय 2"})
    mm = np.asarray([mr] * len(c)) if np.isscalar(mr) else mr
    kdir = -int(I["dir"])
    body = np.abs(c - o)
    seg = slice(ie + 1, j + 1)
    disp = int(((body[seg] >= s_ms["disp_body_mr"] * np.asarray(mm)[seg]) & (body[seg] / np.maximum(rng[seg], 1e-9) >= s_ms["disp_body_frac"])
                & ((c[seg] - o[seg]) * kdir > 0)).sum())
    row("Counter displacement candles (कमकुवत पुरावा)", disp, disp == 0)
    rsi = _rsi(c, int(s["rsi_len"]))
    ext_pts = [x for x in labels if (x["label"] in ("A", "C", "W", "Y", "1", "3", "5"))]
    if len(ext_pts) >= 2:
        a1, a2 = _idx(trig, ext_pts[-2]["ts"]), _idx(trig, ext_pts[-1]["ts"])
        p1, p2 = ext_pts[-2]["price"], ext_pts[-1]["price"]
        if (p2 - p1) * kdir > 0:
            div = (rsi[a2] - rsi[a1]) * kdir < 0
            row("RSI divergence (C-end वर regular)", "हो" if div else "नाही", True if div else None)
    # §2.2 reversal_evidence (नोंद): K हा I-trend मधला सगळ्यात मोठा आणि वेगवान counter-move
    out["reversal_evidence"] = None
    return out


# ---------------------------------------------------------------------------------------------------------------- 7: areas
def area_class(tool):
    return "solid" if tool in SOLID_TOOLS else ("weak solid" if tool in WEAK_TOOLS else "ruler")


def zones_at(df1m, cut, asof, trig, mr, profile="srv2"):
    """chart_reader ची 12 साधनं ⇒ zones (Simple Core signal_at सारखंच; stateless). रिटर्न (zones, cands, ctx, gap)."""
    from chart_reader import areas as AR
    from chart_reader import evaluate as EV
    from chart_reader import settings as CS
    from chart_reader import zones as ZN
    from chart_reader.profiles import PROFILES
    from price_action import levels_v2 as LV
    cs = CS.load()
    pr = PROFILES[profile]
    horiz = []
    for tf in pr["areas_tfs"]:
        horiz += [{**z, "tf": tf.upper()} for z in LV.build(EV.frame(df1m, tf, asof), tf=tf)["candidates"]]
    try:
        from vision import gap_context as GC
        g = GC.build(cut, asof, mr, None, None, None)
    except Exception:                                                      # noqa: BLE001 — gap नसेल तर gap edge zone नाही
        g = {"has_gap": False}
    ctx = EV._ctx(cut, asof, g, mr)
    cands = AR.tools(trig, horiz, {}, ctx, cs, mr)
    zones = ZN.annotate(cands, trig, cs, mr, tf=pr["trigger_tf"].upper())
    return zones, cands, ctx, g


def pick_zones(zones, price, mr, per_side):
    """Chart साठी प्रत्येक बाजूला जवळचे आणि मोठे ≤ per_side (MAGNET / BROKEN / DEAD नाहीत; trendlines रेघ म्हणून वेगळ्या). बाकी JSON मध्ये."""
    from chart_reader.areas import BAD
    live = [z for z in zones if z.get("state") not in BAD and z.get("tool") != "f"]
    out = []
    for side in ("sell", "buy"):
        zs = [z for z in live if z.get("side") == side]
        zs.sort(key=lambda z: (abs((z["low"] + z["high"]) / 2 - price) / max(mr, 1e-9) - 2.0 * float(z.get("quality") or 0)))
        out += zs[:per_side]
    return out


def pattern_lines(n, labels, e):
    """§3 pattern च्या स्वतःच्या रेघा: zigzag channel (A सुरुवात–B टोक, A टोकातून समांतर), triangle A–C / B–D, flat A / B पट्टा."""
    pts = [{"ts": e["ts"], "price": e["price"]}] + labels
    lab = {x["label"]: x for x in labels}
    out = []
    if n.pattern in ("zigzag", "wxy") and "B" in lab or (n.pattern == "wxy" and "X" in lab):
        b = lab.get("B") or lab.get("X")
        a = lab.get("A") or lab.get("W")
        if a and b:
            out.append({"name": "channel (A सुरुवात – B)", "a": pts[0], "b": b, "kind": "ruler"})
            out.append({"name": "channel (A टोकातून समांतर)", "a": a, "b": None, "parallel_to": (pts[0], b), "kind": "ruler"})
    if n.pattern == "triangle":
        if "A" in lab and "C" in lab:
            out.append({"name": "triangle A–C", "a": lab["A"], "b": lab["C"], "kind": "ruler"})
        if "B" in lab and "D" in lab:
            out.append({"name": "triangle B–D", "a": lab["B"], "b": lab["D"], "kind": "ruler"})
    if n.pattern == "flat" and "A" in lab and "B" in lab:
        out.append({"name": "flat: A टोक", "a": lab["A"], "b": None, "horizontal": True, "kind": "ruler"})
        out.append({"name": "flat: B टोक", "a": lab["B"], "b": None, "horizontal": True, "kind": "ruler"})
    return out


# ---------------------------------------------------------------------------------------------------------------- 9: trigger
def _engulf(trig, j, side):
    if j < 1:
        return False
    o, c = trig["open"].to_numpy(float), trig["close"].to_numpy(float)
    if (c[j] - o[j]) * side <= 0:
        return False
    return max(o[j], c[j]) >= max(o[j - 1], c[j - 1]) and min(o[j], c[j]) <= min(o[j - 1], c[j - 1])


def price_failure(trig, side, touched, liquidity, mr, es, depth, s, entry_start):
    """§7: rejection (chart_reader.reversal composite) / sweep + reclaim (reclaim close वर) / engulfing = feature. Trigger मधले सगळे
    candles entry_start नंतर सुरू. खोली 80–100% ⇒ फक्त sweep. रिटर्न dict."""
    from chart_reader import reversal as CRV
    from chart_reader import settings as CS
    from elliott import breaks as BR
    from elliott import reversal as RV
    j = len(trig) - 1
    out = {"ok": False, "type": None, "zone": None, "n": None, "engulfing": _engulf(trig, j, side), "start_ok": True, "why": "",
           "composite": None}
    tsx = pd.to_datetime(trig["timestamp"])
    if not touched and not liquidity:
        out["why"] = "solid area ला स्पर्श नाही"
        return out
    b = RV.Bars(trig, BR.median_range(trig, es["median_range_n"]))
    atr = trig["high"].sub(trig["low"]).rolling(14).mean().iloc[-1]
    tol = es["zone_tol_atr"] * float(atr if np.isfinite(atr) else mr)
    cs = CS.load()
    sweep_only = depth is not None and depth > float(s["depth_valid_hi"])     # 80–100% (S2) आणि 100%+ फक्त wick (sweep पुरावा)
    if not sweep_only:
        for z in touched:
            rv = CRV.evaluate(b, j, side, [z["low"], z["high"]], tol, es, cs, frame=trig)
            if rv.get("status") == "ok":
                start = tsx.iloc[j - int(rv["n"]) + 1]
                if start.strftime("%H:%M") < entry_start:
                    out.update(start_ok=False, why=f"composite {start:%H:%M} ला सुरू ({entry_start} आधी) ⇒ trigger नाही")
                    continue
                out.update(ok=True, start_ok=True, why="", type="rejection", zone=z.get("id"), n=int(rv["n"]), composite=rv.get("label"))
                return out
            out["composite"] = out["composite"] or rv.get("status")
    h, lo, c = (trig[k].to_numpy(float) for k in ("high", "low", "close"))
    nmax = int(es["touch_reclaim_window"])
    for z in liquidity:
        lvl = float(z.get("level") or (z["high"] if side < 0 else z["low"]))
        for k in range(max(0, j - nmax + 1), j + 1):
            swept = h[k] > lvl if side < 0 else lo[k] < lvl
            back = c[j] < lvl if side < 0 else c[j] > lvl
            if swept and back and tsx.iloc[k].strftime("%H:%M") >= entry_start:
                out.update(ok=True, start_ok=True, why="", type="sweep + reclaim", zone=z.get("id"), n=j - k + 1)
                return out
    out["why"] = out["why"] or ("खोली 80–100% ⇒ फक्त sweep + reclaim चालतो; तो नाही" if sweep_only else
                                f"price failure नाही (composite: {out['composite'] or '—'})")
    return out


# ---------------------------------------------------------------------------------------------------------------- read
def futures_volume(trig, fut5, asof):
    """Futures फक्त volume साठी (Abhi): spot 15M bars ला **वेळेने** जोडलेला futures volume (continuous contract, chart_reader/volume.py).
    Futures चे भाव कुठेच वापरत नाही. Rollover चा दिवस (`roll_day`) वेगळा खूण, तुलनेत नाही. फक्त asof पर्यंत बंद झालेले 5M bars.
    रिटर्न (volume array, rel_vol array, roll array) — data नसेल ⇒ None."""
    from chart_reader import volume as VL
    if fut5 is None or not len(fut5):
        return None
    f = VL._naive_ist(fut5)                                                  # data_policy filter caller (script loader) करतो — spot सारखा
    f = f[pd.to_datetime(f["timestamp"]) + pd.Timedelta(minutes=5) <= pd.Timestamp(asof)]
    if not len(f):
        return None
    v15 = VL.to_tf(VL.continuous(f), 15)
    if not len(v15):
        return None
    rv = VL.rel_vol(v15)
    ts = pd.to_datetime(trig["timestamp"])
    vol = ts.map(dict(zip(pd.to_datetime(v15["timestamp"]), v15["volume"].astype(float)))).to_numpy(float)
    roll = ts.map(dict(zip(pd.to_datetime(v15["timestamp"]), v15["roll_day"].astype(bool)))).fillna(False).to_numpy(bool)
    rel = ts.map(rv).to_numpy(float) if len(rv) else np.full(len(ts), np.nan)
    return vol, rel, roll


def volume_summary(trig, fv, I, k_ext_i):
    """Box साठी: impulse वि. correction चं सरासरी futures volume (rollover bars वगळून) + rel_vol, area वरच्या candle चं (K चं टोक)
    आणि decision candle चं volume. Data नाही ⇒ available False."""
    if fv is None:
        return {"available": False, "why": "futures volume data नाही"}
    vol, rel, roll = fv
    ia, ie, j = _idx(trig, I["from_ts"]), _idx(trig, I["to_ts"]), len(trig) - 1

    def avg(a, lo, hi):
        x = a[lo:hi + 1][~roll[lo:hi + 1]]
        x = x[np.isfinite(x)]
        return (float(x.mean()), int(len(x))) if len(x) else (None, 0)
    iv, n_i = avg(vol, ia + 1, ie)
    kv, n_k = avg(vol, ie + 1, j)
    ir, _ = avg(rel, ia + 1, ie)
    kr, _ = avg(rel, ie + 1, j)
    ts = pd.to_datetime(trig["timestamp"])
    ka = int(k_ext_i) if k_ext_i is not None and 0 <= int(k_ext_i) <= j else j     # area वरची candle = K च्या टोकाची
    roll_days = sorted({f"{t:%d %b}" for t, r in zip(ts[ia:], roll[ia:]) if r})
    return {"available": iv is not None or kv is not None, "impulse_avg": iv, "correction_avg": kv, "n_impulse": n_i, "n_correction": n_k,
            "ratio": round(kv / iv, 2) if iv and kv else None, "impulse_rel": ir, "correction_rel": kr,
            "rel_ratio": round(kr / ir, 2) if ir and kr else None,
            "area_candle": None if not np.isfinite(vol[ka]) else float(vol[ka]), "area_candle_rel": None if not np.isfinite(rel[ka]) else
            round(float(rel[ka]), 2), "area_candle_roll": bool(roll[ka]), "area_candle_ts": str(ts.iloc[ka]),
            "decision_candle": None if not np.isfinite(vol[j]) else float(vol[j]), "roll_days": roll_days,
            "excluded_roll_bars": int(roll[ia:].sum())}


def noise_notes(trig, I, labels, k_dir, ms_swings):
    """Abhi (नियम 3): correction मधला छोटा swing किंवा correction ची स्वतःची रेघ तुटणे = noise ⇒ फक्त नोंद (पुष्टी / grade / entry नाही)."""
    out = []
    c = float(trig["close"].iloc[-1])
    e_ts = pd.Timestamp(I["to_ts"])
    sw = [p for p in ms_swings or [] if pd.Timestamp(p["ts"]) > e_ts and p["kind"] == ("L" if k_dir > 0 else "H")]
    if sw and (c - sw[-1]["price"]) * k_dir < 0:
        out.append(f"correction मधला छोटा swing {sw[-1]['price']:,.1f} तुटला")
    lab = {x["label"]: x for x in labels}
    b = lab.get("B")
    if b is not None:
        x0, x1, xj = _idx(trig, e_ts), _idx(trig, b["ts"]), len(trig) - 1
        if x1 > x0:
            line = I["to"] + (b["price"] - I["to"]) / (x1 - x0) * (xj - x0)
            if (c - line) * k_dir < 0:
                out.append(f"correction ची रेघ (A सुरुवात–B) {line:,.1f} तुटली")
    return out


def read(df1m, asof, s=None, es=None, profile="srv2", md_snap=None, fut5=None):
    """एका decision bar (asof = 15M bar चा close) साठी correction_read. फक्त bar_end ≤ asof चे bars. Spot वरच रचना / levels / RSI;
    fut5 (futures 5M) फक्त volume साठी, वेळेने जोडलेला."""
    import market_state as MS
    import market_state.core as MC
    from chart_reader import measures as M
    from elliott import settings as ES
    from simple_core import reading as RD
    s = CRS.load(s)
    es = es or dict(ES.DEFAULTS)
    asof = pd.Timestamp(asof)
    cut, fr = frames(df1m, asof)
    trig = fr["15M"]
    R = {"asof": str(asof), "decision_bar": None, "side": 0, "items": {}, "frames_ok": len(trig) >= 40}
    if len(trig) < 40:
        R["decision"] = {"outcome": "no_trade", "gate": None, "what": "data अपुरा", "why": "15M bars < 40"}
        return R
    R["decision_bar"] = str(pd.Timestamp(trig["timestamp"].iloc[-1]))
    mr = M.mr_now(trig)
    R["mr"] = round(float(mr), 2)
    ms = MS.read(cut, asof, run_elliott=False)
    R["ms_swings"] = [{"ts": str(p["ts"]), "price": round(float(p["price"]), 2), "kind": p["kind"]} for p in ms.get("swings") or []]
    s_ms = {**MC.DEFAULTS}
    price = float(trig["close"].iloc[-1])
    items = R["items"]

    def item(n, status, ev, gate=False):
        items[n] = {"n": n, "name": ITEMS[n], "status": status, "evidence": ev, "gate": gate}

    # 1: HTF + पायरी 0 (पालक दिशा: parent_source default market_state; Gray-1 = HTF testing)
    htf = htf_state(fr)
    R["htf_state"] = htf
    tr = ms.get("trend") or {}
    kk = impulse_and_hypotheses(df1m, asof, ms, es, md_snap)
    I = kk["I"]
    R["impulse"] = {"I": I, "I_ms": kk["I_ms"], "source": kk["I_source"], "E": kk["E"]}
    R["count"] = {"degree": kk["degree"], "k_degree": kk["k_degree"], "parent": kk["parent"], "count_tie": kk["count_tie"]}
    side = int(I["dir"]) if I else 0
    R["side"] = side
    parent_dir = int(tr.get("dir") or 0)
    gray1 = tr.get("state") == "testing"
    pol = RD.get_gray_policy()
    p1 = (f"W {_dir_mr(htf['weekly']['dir'])} · D {_dir_mr(htf['daily']['dir'])} · पालक (1H) {_dir_mr(parent_dir)}"
          + (" · Gray-1 (protected तुटला, testing)" if gray1 else ""))
    step0 = None
    if not parent_dir:
        step0 = "पालक दिशा ठरलेली नाही (PARENT_UNKNOWN)"
    elif gray1 and pol == "block":
        step0 = "Gray-1 ⇒ gray धोरण block"
    elif side and side != parent_dir:
        step0 = "I ची दिशा पालक दिशेच्या विरुद्ध (AGAINST_PARENT)"
    item(1, "✘" if step0 else "✔", p1 + (f" ⇒ {step0}" if step0 else ""), gate=bool(step0))
    R["step0"] = {"parent_dir": parent_dir, "gray1": gray1, "gray_policy": pol, "block": step0}

    # 2: 1H trend, protected, I
    prot = tr.get("protected")
    if I:
        item(2, "✔", f"1H {_dir_mr(parent_dir)}" + (f" · protected {prot['kind']} {float(prot['price']):,.1f}" if prot else "")
             + f" · I {I['from']:,.1f} → {I['to']:,.1f} ({pd.Timestamp(I['from_ts']):%d %b %H:%M} → {pd.Timestamp(I['to_ts']):%d %b %H:%M})")
    else:
        item(2, "✘", "trade-degree impulse नाही")
    # 3: impulse खरा
    imp_ms = ms.get("impulse") or {}
    if I:
        same = kk["I_source"] == "market_state" or (abs(I["from"] - kk["I_ms"]["from"]) < 1e-6 and abs(I["to"] - kk["I_ms"]["to"]) < 1e-6)
        ev = (f"{imp_ms.get('size_mr')}× MR · displacement {imp_ms.get('disp')} · ER {imp_ms.get('er')} · BOS "
              f"{imp_ms.get('bos')}" + ("" if same else f" · count चा I {I['from']:,.1f} → {I['to']:,.1f} (market_state "
                                                        f"{kk['I_ms']['from']:,.1f} → {kk['I_ms']['to']:,.1f})"))
        item(3, "✔" if imp_ms.get("impulse") else "–", ev)
    else:
        item(3, "–", "impulse नाही")
    if not I:
        for n in range(4, 13):
            item(n, "–", "impulse नाही ⇒ correction वाचता येत नाही")
        items[5].update(status="✘", gate=True, evidence="impulse नाही ⇒ pattern ओळखता येत नाही")
        return _finish(R, s)

    # K: E पासून decision bar पर्यंत
    k_dir = -side
    e_i = _idx(trig, I["to_ts"])
    seg_h, seg_l = trig["high"].to_numpy(float)[e_i + 1:], trig["low"].to_numpy(float)[e_i + 1:]
    if not len(seg_h):
        k_ext, k_ext_i = I["to"], e_i
    elif k_dir > 0:
        k_ext_i = e_i + 1 + int(np.argmax(seg_h))
        k_ext = float(seg_h.max())
    else:
        k_ext_i = e_i + 1 + int(np.argmin(seg_l))
        k_ext = float(seg_l.min())
    i_size = abs(I["to"] - I["from"])
    depth = abs(k_ext - I["to"]) / i_size if i_size > 0 else None
    R["K"] = {"dir": k_dir, "extreme": round(k_ext, 2), "extreme_ts": str(pd.Timestamp(trig["timestamp"].iloc[k_ext_i])), "depth": depth}

    # areas (12 साधनं) — खरा area = trade बाजूचा solid / weak solid zone ज्याला K च्या टोकाने स्पर्श केला
    zones, cands, ctx, gap = zones_at(df1m, cut, asof, trig, mr, profile)
    trade_side = "sell" if side < 0 else "buy"
    from chart_reader.areas import BAD
    tolz = float(s["confluence_tol_mr"]) * mr
    touched = [z for z in zones if z.get("side") == trade_side and z.get("state") not in BAD
               and z["low"] - tolz <= k_ext <= z["high"] + tolz]
    liq = [z for z in zones if z.get("tool") in ("e", "k") and z.get("side") == trade_side and z.get("state") not in BAD
           and abs(float(z.get("level") or (z["high"] if side < 0 else z["low"])) - k_ext) <= 2 * tolz]
    trendlines = [z for z in cands if z.get("tool") == "f"]
    R["area"] = {"zones_all": [_zbrief(z) for z in zones], "chart_zones": [_zbrief(z) for z in pick_zones(zones, price, mr,
                                                                                                        int(s["annot_zones_per_side"]))],
                 "trendlines": [_tlbrief(z) for z in trendlines], "touched": [_zbrief(z) for z in touched]}

    # 4: §2.3 व्याख्यात्मक अटी + स्वभाव मापक
    corr = ms.get("correction") or {}
    hyps = kk["hyps"]
    n0 = hyps[0] if hyps else None
    labs0 = _labels(n0) if n0 is not None else []
    ch = character(trig, I, k_ext_i, labs0, BR_mr(trig, es), s, s_ms)
    fv = futures_volume(trig, fut5, asof)
    vs = volume_summary(trig, fv, I, k_ext_i)
    R["volume"] = vs
    if fv is not None:
        tail = slice(max(0, len(trig) - 420), len(trig))
        R["volume_series"] = [{"ts": str(t), "v": None if not np.isfinite(v) else float(v), "roll": bool(r)}
                              for t, v, r in zip(pd.to_datetime(trig["timestamp"]).iloc[tail], fv[0][tail], fv[2][tail])]
    vr = vs.get("rel_ratio") if vs.get("rel_ratio") is not None else vs.get("ratio")
    ch["rows"].append({"name": "Futures volume (K ÷ I, rollover वगळून)", "value": vr if vs.get("available") else "NA",
                       "verdict": "तटस्थ" if vr is None else ("correction सारखा" if vr < 1.0 else "नवी चाल सारखी"), "note": ""})
    R["character"] = ch
    R["noise"] = noise_notes(trig, I, labs0, k_dir, R.get("ms_swings"))
    g4 = None
    if corr.get("origin_broken"):
        g4 = ("no_trade", "impulse origin चा real break ⇒ pullback नाही")
    elif depth is not None and depth > float(s["depth_sweep_hi"]):
        # वापरलेल्या I (count / market_state) च्या origin पलीकडे: real break (breaks.py) ⇒ pullback नाही; फक्त wick ⇒ sweep पुरावा (§1.2)
        import market_state.core as MCB
        brk = MCB._real_break(trig, e_i + 1, I["from"], "below" if side > 0 else "above", es, BR_mr(trig, es))
        if brk is not None:
            g4 = ("no_trade", f"I origin {I['from']:,.1f} चा real break ⇒ pullback नाही")
    par = (kk["parent"] or {}).get("preferred") or {}
    if not g4 and par and par.get("pattern") not in MOTIVE:
        if par.get("wave") == "B":
            g4 = ("no_trade", "K हा पालक degree चा B ⇒ B-end ⇒ C (default OFF)")
        elif par.get("wave") == "X":
            g4 = ("no_trade", "K हा पालक degree चा X ⇒ entry नाही")
        elif par.get("pattern") == "triangle" and par.get("wave") in ("A", "B", "C", "D"):
            g4 = ("no_trade", "K triangle च्या आत ⇒ entry नाही")
    votes = [r["verdict"] for r in ch["rows"]]
    summ = f"correction सारखे {votes.count('correction सारखा')} · नवी चाल सारखे {votes.count('नवी चाल सारखी')}"
    item(4, "✘" if g4 else "✔", (g4[1] + " · " if g4 else "") + summ, gate=bool(g4))
    R["gate4"] = g4

    # 5 + 6: pattern आणि स्थिती
    hyp_out = []
    md = kk.get("md")
    for n in hyps:
        labs = _labels(n)
        last = labs[-1] if labs else None
        against = None
        if last is not None and n.pattern in LAST and n.current_wave == LAST[n.pattern]:
            c_start = labs[-2]["ts"] if len(labs) >= 2 else I["to_ts"]
            against = lower_degree_against(md, kk["k_degree"], c_start, k_dir, asof, price)
        hyp_out.append({"pattern": n.pattern, "subtype": n.subtype, "wave": n.current_wave, "score": round(float(n.joint_score or 0), 3),
                        "labels": labs, "against": against, "invs": [(round(float(l), 2), sd) for l, sd, _ in (n.invs or [])][:2],
                        "_node": n})
    # area failure (final_leg_short साठी) नंतर ठरतो; आधी स्थिती area शिवाय
    pf = price_failure(trig, side, touched, liq, mr, es, depth, s, es.get("entry_start", "09:30"))
    for h in hyp_out:
        h["time"] = time_evidence(trig, I["to_ts"], h["labels"], R["decision_bar"])
        h["state"] = hypothesis_state(h["_node"], h["labels"], k_dir, area_failure=bool(touched) and pf["ok"], against=h["against"])
    pref = hyp_out[0] if hyp_out else None
    alt = hyp_out[1] if len(hyp_out) > 1 else None
    R["pattern"] = {"hypotheses": [{k: v for k, v in h.items() if k != "_node"} for h in hyp_out], "count_tie": kk["count_tie"],
                    "lines": pattern_lines(pref["_node"], pref["labels"], kk["E"]) if pref else [],
                    "ms_labels": corr.get("labels") or []}
    if pref is None:
        item(5, "✘", "E पासून सुरू होणारा correction count नाही ⇒ pattern ओळखता येत नाही", gate=True)
        st = "not_identified"
    else:
        tie = f" · count tie: {', '.join(kk['count_tie'])}" if kk["count_tie"] else ""
        lab = " ".join(f"{x['label']} {x['price']:,.0f}" for x in pref["labels"])
        ok5 = pref["pattern"] not in MOTIVE and pref["state"] != "not_identified"
        tm = pref.get("time") or {}
        if tm:
            lab += (f" · वेळ A {tm['t_A']} / B {tm['t_B']} / C {tm['t_C']} bars (C > A {'✔' if tm['C_gt_A'] else '✘'}, "
                    f"C ≤ A+B {'✔' if tm['C_le_A_plus_B'] else '✘'})")
        item(5, "✔" if ok5 else "✘", f"{PAT_MR.get(pref['pattern'], pref['pattern'])} ({pref['subtype']}): {lab}"
             + (f" · alternate {PAT_MR.get(alt['pattern'], alt['pattern'])}/{alt['wave']}" if alt else "") + tie,
             gate=not ok5 and pref["state"] not in ("k_is_five", "forming_A"))
        st = pref["state"]
    R["complete"] = {"state": st, "mr": STATE_MR.get(st, st)}
    ok6 = st in ("final_leg_present", "final_leg_short")
    ev6 = STATE_MR.get(st, st)
    if st == "final_leg_short":
        ev6 += " ⇒ Gray-2 ⇒ gray धोरण " + pol
    item(6, "✔" if ok6 and not (st == "final_leg_short" and pol == "block") else "✘", ev6,
         gate=not ok6 or (st == "final_leg_short" and pol == "block"))
    if pref is not None and pref["pattern"] in MOTIVE:                      # K स्वतः motive ⇒ item 5 नव्हे तर 6 / 4 (A / नवी चाल)
        items[5]["gate"] = False

    # 7: खरा area
    kinds = sorted({area_class(z.get("tool")) for z in touched})
    types = sorted({z.get("tool") for z in touched})
    if touched:
        ev7 = " + ".join(f"{TOOL_MR.get(z.get('tool'), z.get('tool'))} {z['low']:,.0f}–{z['high']:,.0f}" for z in touched[:3])
        weak_only = kinds == ["weak solid"]
        item(7, "✔", ev7 + (" (फक्त weak solid ⇒ grade कमी)" if weak_only else "") + f" · confluence प्रकार {len(types)}")
    else:
        item(7, "✘", f"K चं टोक {k_ext:,.1f} trade बाजूच्या solid area वर नाही", gate=True)
    # completion zone (display + grade): fib (I च्या) + C=A + touched zones एकत्र
    R["area"]["completion_zone"] = completion_zone(I, pref, touched, k_ext, tolz)

    # 8: खोली
    if depth is None:
        item(8, "–", "I ची लांबी 0")
    else:
        band = ("valid 38.2–80%" if s["depth_valid_lo"] <= depth <= s["depth_valid_hi"] else
                "80–100% ⇒ फक्त sweep" if depth <= s["depth_sweep_hi"] else
                "flag पट्टा 23.6–38.2%" if s["depth_flag_lo"] <= depth < s["depth_valid_lo"] else
                "100% पेक्षा जास्त" if depth > s["depth_sweep_hi"] else "उथळ")
        item(8, "✔" if s["depth_flag_lo"] <= depth <= s["depth_valid_hi"] else "–", f"{depth:.0%} ({band})")

    # 9: price failure
    if pf["ok"]:
        item(9, "✔", f"{pf['type']} ({pf['n']} candle) · area {pf['zone']}" + (" · engulfing feature" if pf["engulfing"] else ""))
    else:
        item(9, "✘", pf["why"] + (" · engulfing feature" if pf["engulfing"] else ""), gate=True)
    R["price_failure"] = pf

    # 10: risk
    buf = float(s["sl_buffer_mr"]) * mr
    sl = k_ext + buf * k_dir
    tgt = float(I["to"])
    risk = abs(sl - price)
    rr = round(abs(tgt - price) / risk, 2) if risk > 0 and (tgt - price) * side > 0 else None
    R["risk"] = {"entry": round(price, 2), "sl": round(sl, 2), "target": round(tgt, 2), "rr": rr,
                 "count_dead": (pref or {}).get("invs", [None])[0] if pref and pref.get("invs") else None}
    item(10, "✔" if rr is not None and rr >= s["min_rr"] else "✘",
         f"entry {price:,.1f} · SL {sl:,.1f} · target (I टोक) {tgt:,.1f} · R:R {rr if rr is not None else '—'}",
         gate=not (rr is not None and rr >= s["min_rr"]))

    # 11: संदर्भ
    tnow = pd.Timestamp(trig["timestamp"].iloc[-1])
    c11 = [f"वेळ {tnow:%H:%M}"]
    if gap.get("has_gap"):
        c11.append(f"gap {gap.get('class')} {gap.get('direction')}")
    for k, nm in (("pdh", "PDH"), ("pdl", "PDL"), ("pdc", "PDC")):
        if ctx.get(k) is not None:
            c11.append(f"{nm} {float(ctx[k]):,.0f}")
    item(11, "–", " · ".join(c11))
    R["context"] = {"time": f"{tnow:%H:%M}", "gap": {k: gap.get(k) for k in ("has_gap", "class", "direction")},
                    "pdh": ctx.get("pdh"), "pdl": ctx.get("pdl"), "pdc": ctx.get("pdc")}

    # 12: पक्के नियम (KB A3): बंद candle (नेहमी — फक्त बंद bars), breakout / पाठलाग नाही, स्पष्ट invalidation, R:R ≥ 3
    hard = {"बंद candle": True, "स्पष्ट invalidation": sl is not None, "R:R ≥ 3": rr is not None and rr >= s["min_rr"],
            "entry वेळ": pf.get("start_ok", True) and tnow.strftime("%H:%M") >= es.get("entry_start", "09:30"),
            "breakout / पाठलाग नाही": True}                                  # trigger फक्त area वरचा price failure (§7); breakout वर entry नाहीच
    bad = [k for k, v in hard.items() if not v]
    item(12, "✘" if bad else "✔", "✘: " + ", ".join(bad) if bad else "पाचही ✔", gate=bool(bad))
    R["hard_rules"] = hard
    return _finish(R, s)


def time_evidence(trig, e_ts, labels, now_ts):
    """§5 #1 (NEOWAVE; Abhi पायरी 2 भर 1): t(B) ≥ t(A); t(C) > t(A) (खालची सीमा, score); t(C) ≤ t(A) + t(B) (`g_c_time` सारखी वरची
    सीमा). C चालू असेल तर t(C) = आतापर्यंत (tentative). फक्त पुरावा — gate नाही."""
    lab = {x["label"]: x for x in labels}
    a, b = lab.get("A") or lab.get("W"), lab.get("B") or lab.get("X")
    if a is None or b is None:
        return {}
    c_end = (lab.get("C") or lab.get("Y") or {}).get("ts") or now_ts
    ie, ia, ib, ic = (_idx(trig, t) for t in (e_ts, a["ts"], b["ts"], c_end))
    ta, tb, tc = ia - ie, ib - ia, ic - ib
    return {"t_A": ta, "t_B": tb, "t_C": tc, "B_ge_A": tb >= ta, "C_gt_A": tc > ta, "C_le_A_plus_B": tc <= ta + tb}


def BR_mr(trig, es):
    from elliott import breaks as BR
    return BR.median_range(trig, es["median_range_n"])


def completion_zone(I, pref, touched, k_ext, tol):
    """§5: Fibonacci (I चे 38.2–78.6), C = A, आणि touched solid areas जिथे K च्या टोकाजवळ एकत्र ⇒ पट्टा (≥ 2 वेगळे प्रकार). फक्त display / grade."""
    lv = []
    size = I["to"] - I["from"]
    for r in (0.382, 0.5, 0.618, 0.786):
        lv.append(("Fib", I["to"] - size * r))
    if pref:
        lab = {x["label"]: x["price"] for x in pref["labels"]}
        if "A" in lab and "B" in lab:
            lv.append(("C = A", lab["B"] + (lab["A"] - float(I["to"]))))
    for z in touched:
        lv.append((TOOL_MR.get(z.get("tool"), "area"), (z["low"] + z["high"]) / 2))
    near = [(k, v) for k, v in lv if abs(v - k_ext) <= 2 * tol]
    if len({k for k, _ in near}) < 2:
        return None
    vals = [v for _, v in near]
    return {"low": round(min(vals) - tol / 2, 2), "high": round(max(vals) + tol / 2, 2), "parts": sorted({k for k, _ in near})}


def _zbrief(z):
    return {"id": z.get("id"), "tool": z.get("tool"), "class": area_class(z.get("tool")), "side": z.get("side"), "low": round(float(z["low"]), 2),
            "high": round(float(z["high"]), 2), "state": z.get("state"), "quality": z.get("quality"), "tf": z.get("tf"),
            "flipped": bool(z.get("flipped") or z.get("role_reversal")), "level": z.get("level")}


def _tlbrief(z):
    return {"id": z.get("id"), "role": z.get("role"), "valid": bool(z.get("valid")), "state": z.get("state"), "touches": z.get("touches"),
            "anchors": [(str(a[0]), round(float(a[1]), 2)) for a in (z.get("anchors") or [])], "slope": z.get("slope"),
            "pair": [(str(a[0]), round(float(a[1]), 2)) for a in (z.get("pair") or [])]}


def _finish(R, s):
    """निर्णय: §0.2 क्रमाने पहिला gate ✘ ⇒ no_trade / wait; सगळे ✔ ⇒ setup."""
    items = R["items"]
    st = (R.get("complete") or {}).get("state")
    first = next((n for n in GATE_ORDER if n in items and items[n]["gate"] and items[n]["status"] == "✘"), None)
    if first is None and all(items.get(n, {}).get("status") == "✔" for n in (5, 6, 7, 9, 10)):
        outc, what = "setup", f"{'bear' if R['side'] < 0 else 'bull'} setup"
    elif first in (6,) and st == "final_leg_in_progress" or (first is None and st == "final_leg_in_progress"):
        outc, what = "wait", "शेवटच्या leg ची वाट (शेवटचा leg चालू)"
    elif first == 4 and (R.get("gate4") or ("", ""))[0] == "wait":
        outc, what = "wait", R["gate4"][1]
    elif first == 9 and items.get(6, {}).get("status") == "✔" and items.get(7, {}).get("status") == "✔":
        outc, what = "wait", "price failure ची वाट (area वर)"
    elif st == "k_is_five" and first in (None, 5, 6):
        outc, what = "wait", "K स्वतः 5 waves ⇒ तो A / नवी चाल (थांबा)"
    else:
        outc, what = "no_trade", (f"gate {first}: {ITEMS[first]}" if first else "pattern ओळखता येत नाही")
    if outc == "no_trade" and st in ("forming_A", "forming_B", "in_X", "in_triangle") and first in (None, 5, 6):
        what = f"{STATE_MR.get(st, st)} ⇒ entry नाही"
    grade = None
    if outc == "setup":
        conf = len({z.get("tool") for z in (R.get("area") or {}).get("touched") or []})
        ev = sum(1 for r in (R.get("character") or {}).get("rows", []) if r["verdict"] == "correction सारखा")
        grade = "A" if conf >= 2 and ev >= 4 else ("B" if conf >= 2 or ev >= 4 else "C")
    R["decision"] = {"outcome": outc, "gate": first, "what": what,
                     "why": items[first]["evidence"] if first else ""}
    R["grade"] = grade
    R["where_wrong"] = (f"{'वर' if R['side'] < 0 else 'खाली'} SL {R['risk']['sl']:,.1f} च्या पलीकडे close ⇒ वाचन चूक"
                        if R.get("risk") else "")
    return R
