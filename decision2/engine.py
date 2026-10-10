"""decision2/engine.py — थर 7: regime, gates (G-A … G-I), commitment candle, risk, grade, size, `decision` (PAPER / shadow).

निर्णय = थोडे gates (Abhi चे) + grade (पुरावे). AI / vision कधीच order देत नाही; हा module order / broker call करत नाही.
Exits (`hard_exits`) कोणत्याही budget / listener / vision / approval / वेळ-gate / holdout guard पासून स्वतंत्र — वेगळं शुद्ध फंक्शन.
बाह्य data (VIX, event calendar, expiry, macro row, gray_policy दिशा) = `ext` dict मधल्या rows (`known_at` सह); नसेल ⇒ नोंद (NA).
VIX / event / macro (Abhi उत्तर 14) = फक्त size_weight + नोंद, gate नाही. Tier (Abhi निर्णय) default 1: G1–G6 + G8 hard, G7 grade; tier 2
= पुढची candle confirm (setting, default नाही). Trendline-break flavour: area स्पर्श break आधी ≤ tl_break_n candles.
"""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from legs2 import features as LF
from swings2 import structure as SST
from trendlines2 import settings as TS

from . import settings as DS

SETUP, WAIT, NO_TRADE = "setup", "wait", "no_trade"
UP, DOWN = "trend_up", "trend_down"
RANGE, BARB, TRANS, DRIFT = "range", "barbwire", "transition", "drift"


class Ctx:
    """सगळे थर एकत्र (एकाच run चे): res, st, lg, trk, f1, f2, Z, L4, L5, L6."""

    def __init__(self, lg, st, trk, f1, f2, Z, L4, L5, L6, s=None, ext=None):
        self.lg, self.st, self.trk, self.f1, self.f2, self.Z, self.L4, self.L5, self.L6 = lg, st, trk, f1, f2, Z, L4, L5, L6
        self.res = lg["res"]
        self.s = DS.load(s)
        self.ext = ext or {}
        self.m15 = self.res["m15"]
        self.A = lg["A"]
        self.rr = lg["rr"]
        self.ts = pd.to_datetime(self.m15["timestamp"]).reset_index(drop=True)
        self.day = self.ts.dt.normalize()
        self.n = len(self.m15)
        H, L, E, S1, G1, F1 = SST._h1(self.res)
        from pivots import charts as PC
        h1 = PC.agg_1h(self.m15)
        self.h1 = {"H": H, "L": L, "E": E, "S": S1, "C": h1["close"].to_numpy(float), "O": h1["open"].to_numpy(float)}
        self.mr = BR.median_range(self.m15, int(DS.MUST_HOLD_BREAK["median_range_n"]))
        self._mh_start = self._protected_starts()

    def _protected_starts(self):
        """D2 protected (strong low / high) प्रत्येक bar ला आणि तो कधीपासून (बदलला तो bar)."""
        out, last, start = [], None, 0
        for t, x in enumerate(self.st[2]["states"]):
            p = x["protected"]
            if p != last:
                start, last = t, p
            out.append((p, start, x["trend"]))
        return out


# ---------------------------------------------------------------------------------------------------- regime
def regime(C, t):
    s = C.s
    E = C.h1["E"]
    closed = np.flatnonzero((E >= 0) & (E <= t))
    st2 = C.st[2]["states"][t]
    if len(closed) < int(s["h1_window"]):
        return {"regime": DRIFT, "why": "1H इतिहास अपुरा"}
    w = closed[-int(s["h1_window"]):]
    sig = C.h1["S"][w[-1]]
    RH, RL = float(C.h1["H"][w].max()), float(C.h1["L"][w].min())
    Hh = RH - RL
    net = float(C.A["c"][t] - C.h1["O"][w[0]])
    out = {"H_sigma": round(Hh / sig, 2) if sig else None, "net_ratio": round(net / Hh, 3) if Hh else None, "d2": st2["trend"]}
    tr = _transition(C, t)
    if tr is not None:
        out.update(regime=TRANS, **tr)
        return out
    if not np.isfinite(sig) or sig <= 0 or Hh <= 0:
        out["regime"] = DRIFT
        return out
    if st2["trend"] == SST.UPT and Hh >= float(s["trend_h"]) * sig and net / Hh >= float(s["trend_net"]):
        out["regime"] = UP
    elif st2["trend"] == SST.DNT and Hh >= float(s["trend_h"]) * sig and -net / Hh >= float(s["trend_net"]):
        out["regime"] = DOWN
    elif st2["trend"] == SST.RNG and abs(net) / Hh < float(s["range_net"]):
        med = float(np.median(C.h1["H"][w] - C.h1["L"][w]))
        out["regime"] = BARB if med < float(s["barbwire"]) * sig else RANGE
        out["band"] = st2["range"]
    else:
        out["regime"] = DRIFT
    return out


def _transition(C, t):
    """D2 range_break पासून transition (दिशा = break). संपतो: (1) > transition_bars 1H bars बाहेर **आणि** पहिला pullback (D1 counter
    pivot) जुन्या कडेबाहेर held; (2) close परत जुन्या कडेच्या आत (failed breakout); (3) नवा range_start. नाहीतर None."""
    ev = [e for e in C.st[2]["events"] if e["type"] == "range_break" and e["bar"] <= t]
    if not ev:
        return None
    e = ev[-1]
    d, lvl, b0 = e["dir"], e["level"], e["bar"]
    if any(x["type"] == "range_start" and b0 < x["bar"] <= t for x in C.st[2]["events"]):
        return None
    back = [j for j in range(b0 + 1, t + 1) if (C.A["c"][j] - lvl) * d < 0]
    if back:
        return None                                                                 # failed breakout ⇒ transition नाही
    E = C.h1["E"]
    kind = "L" if d > 0 else "H"
    pb = [p for p in C.res["pivots"][1] if p.kind == kind and b0 < p.bar and p.confirm_bar <= t]
    held = bool(pb and ((pb[0].price > lvl) if d > 0 else (pb[0].price < lvl)))
    if held:
        after = np.flatnonzero(E > b0)                                             # break नंतरच्या बंद 1H candles (1H index)
        nb = int(C.s["transition_bars"])
        done_at = max(pb[0].confirm_bar, int(E[after[nb]]) if len(after) > nb else C.n)   # 15M bar जिथे (nb+1)-वी 1H candle बंद
        if t >= done_at:
            return None                                                             # transition पूर्ण ⇒ नवा trend regime
    return {"dir": d, "bars_out": int(((E > b0) & (E <= t)).sum()), "pullback_held": held, "edge": lvl}


# ---------------------------------------------------------------------------------------------------- commitment candle
def merged(C, t, k):
    """शेवटच्या k candles (≤ merge_max) चा merged candle — सगळ्या 09:30 नंतर आणि एकाच session मध्ये. नाहीतर None."""
    i0 = t - k + 1
    if i0 < 0 or C.day[i0] != C.day[t]:
        return None
    st = pd.Timestamp(C.s["entry_start"]).time()
    if any(C.ts[i].time() < st for i in range(i0, t + 1)):
        return None
    A = C.A
    return {"o": A["o"][i0], "h": float(A["h"][i0:t + 1].max()), "l": float(A["l"][i0:t + 1].min()), "c": A["c"][t], "i0": i0, "t": t,
            "k": k}


def commitment(C, t, d, area, s=None):
    """§4 G1–G8 (trade दिशा d; area = (bottom, top) zone / रेघ पट्टा, accept = bool). रिटर्न dict: pass (tier नुसार), checks, flavour."""
    s = s or C.s
    A = C.A
    best = None
    for k in range(1, int(s["merge_max"]) + 1):
        m = merged(C, t, k)
        if m is None:
            continue
        rng = m["h"] - m["l"]
        if rng <= 0:
            continue
        bot, top = area["band"]
        far = m["l"] if d > 0 else m["h"]                                       # उलट टोक (buy ⇒ low)
        g1 = (far <= top) if d > 0 else (far >= bot)
        g2 = (m["l"] <= top) if d > 0 else (m["h"] >= bot)
        clv = (m["c"] - m["l"]) / rng if d > 0 else (m["h"] - m["c"]) / rng
        prev = m["i0"] - 1
        beyond_prev = prev >= 0 and ((m["c"] > A["h"][prev]) if d > 0 else (m["c"] < A["l"][prev]))
        side_ok = (m["c"] > top) if d > 0 else (m["c"] < bot)                    # close area च्या trade-बाजूला (reclaim)
        g3 = bool(side_ok and (clv >= float(s["g3_clv"]) or beyond_prev))
        rej_wick = ((min(m["o"], m["c"]) - m["l"]) / rng) if d > 0 else ((m["h"] - max(m["o"], m["c"])) / rng)
        body = abs(m["c"] - m["o"]) / rng
        strong = body >= float(s["g4_body"]) and (m["c"] - m["o"]) * d > 0
        pin = rej_wick >= float(s["g4_wick"])
        g4 = bool(pin or strong)
        meds = [(A["h"][i] - A["l"][i]) / C.rr[i] for i in range(m["i0"], m["t"] + 1) if np.isfinite(C.rr[i]) and C.rr[i] > 0]
        rr = rng / float(np.mean(meds)) if meds else np.nan                    # merged: range ÷ त्या slots च्या median ची सरासरी
        counter_climax = any(LF.climax_candle(A, C.rr, i, -d, C.lg["settings"]) for i in range(m["i0"], m["t"] + 1))
        g5 = bool(np.isfinite(rr) and rr >= float(s["g5_rng"]) and not counter_climax)
        o3 = LF.overlap3(A, m["t"])
        g6 = bool((o3 is not None and o3 < float(s["g6_overlap3"])) or beyond_prev)
        g8 = not area.get("accept", False)
        checks = {"G1": bool(g1), "G2": bool(g2), "G3": g3, "G4": g4, "G5": g5, "G6": g6, "G8": bool(g8)}
        hard = all(checks.values()) if int(s["tier"]) >= 1 else True
        engulf = prev >= 0 and (m["c"] - m["o"]) * d > 0 and abs(m["c"] - m["o"]) >= abs(A["c"][prev] - A["o"][prev]) and \
            ((A["c"][prev] - A["o"][prev]) * d < 0)
        rec = {"pass": bool(hard), "checks": checks, "merged": k, "candle": {"i0": int(m["i0"]), "t": int(m["t"]), "o": round(m["o"], 2),
               "h": round(m["h"], 2), "l": round(m["l"], 2), "c": round(m["c"], 2)}, "g4_both": bool(pin and strong),
               "engulf": bool(engulf), "rng_ratio": None if not np.isfinite(rr) else round(float(rr), 2), "overlap3": o3}
        if best is None or (rec["pass"] and not best["pass"]):
            best = rec
        if rec["pass"]:
            break
    return best


# ---------------------------------------------------------------------------------------------------- hard exits (स्वतंत्र)
def hard_exits(C, t, trade_dir, I_trade=None):
    """नेहमी (hold मध्येही) फक्त दोन: (1) trade च्या I चा I_origin real break; (2) D2 must-hold real break. कोणत्याही gate / vision /
    approval / budget / वेळ-gate शी संबंध नाही. I_trade = entry वेळचा I (नसेल ⇒ सध्याचा)."""
    out = []
    I = I_trade if I_trade is not None else C.trk[1].I_at(t)
    if I is not None:
        side = "below" if I["dir"] > 0 else "above"
        rb = BR.first_real_break(C.m15, I["end"].bar, I["origin"].price, side, DS.MUST_HOLD_BREAK, mr=C.mr, end=t, retest_fn=None)
        if rb is not None and rb <= t:
            out.append("I_origin real break")
    if must_hold_broken(C, t, trade_dir):
        out.append("D2 must-hold real break")
    return out


def must_hold_broken(C, t, trade_dir):
    """D2 strong low (UP) / high (DOWN) चा real break — फक्त तो protected trade-दिशेचा असेल तर (UP ⇒ long); नाहीतर NA (False)."""
    p, start, tr = C._mh_start[t]
    if p is None or tr not in (SST.UPT, SST.DNT) or (tr == SST.UPT) != (trade_dir > 0):
        return False
    side = "below" if tr == SST.UPT else "above"
    rb = BR.first_real_break(C.m15, start, p, side, DS.MUST_HOLD_BREAK, mr=C.mr, end=t, retest_fn=None)
    return rb is not None and rb <= t


def d3_trend(C, t):
    seg = C.res["segments"].get(pd.Timestamp(C.day[t]))
    return SST.trend_of([p for p in C.res["pivots"][3] if p.confirm_bar <= t and not p.warmup
                         and C.res["segments"].get(pd.Timestamp(p.ts).normalize()) == seg])


def range_band(C, t):
    """थर 1 D2 RANGE पट्टा (Rhea) किंवा pivot पट्टा (शेवटचे दोन H चा वरचा / दोन L चा खालचा)."""
    st2 = C.st[2]["states"][t]
    if st2["range"] is not None:
        return st2["range"]["top"], st2["range"]["bottom"]
    seg = C.res["segments"].get(pd.Timestamp(C.day[t]))
    ps = [p for p in C.res["pivots"][2] if p.confirm_bar <= t and not p.warmup and C.res["segments"].get(pd.Timestamp(p.ts).normalize()) == seg]
    hs, ls = [p for p in ps if p.kind == "H"][-2:], [p for p in ps if p.kind == "L"][-2:]
    if len(hs) < 2 or len(ls) < 2:
        return None
    return max(p.price for p in hs), min(p.price for p in ls)


# ---------------------------------------------------------------------------------------------------- निर्णय
def _area(C, t, d, l4, l5):
    """G-C: थर 4 zone (हो / sweep / pending) किंवा थर 5 trade-योग्य रेघ; htf_against ⇒ नाही. रिटर्न area dict किंवा None."""
    ka = (l4 or {}).get("k_area") or {}
    if ka.get("ans", "").startswith("हो") and ka.get("htf_against"):
        return None                                                                 # htf_against ⇒ G-C नाही (रेघेकडे जात नाही)
    if ka.get("ans", "").startswith("हो"):
        return {"src": "zone", "band": ka["band"], "ans": ka["ans"], "stars": ka.get("stars", 1), "accept": False, "zone": ka.get("zone"),
                "spring": ka.get("spring")}
    la = (l5 or {}).get("k_area_line") or {}
    if la.get("ans", "").startswith("हो"):
        tau = float(TS.DEFAULTS["tau"]) * float(C.res["sigma"].get(pd.Timestamp(C.day[t]), np.nan))
        v = la["value"]
        return {"src": "रेघ", "band": (v - tau, v + tau), "ans": la["ans"], "stars": 1, "accept": False, "line": la.get("line"),
                "intersection": la.get("intersection"), "steep": bool(la.get("steep")), "bar": la.get("bar")}
    return None


def decide(C, t):
    """एका बंद 15M candle चा `decision` (12 मुद्दे + decision + grade + size)."""
    s = C.s
    out = {"bar": t, "ts": str(C.ts[t]), "decision": None, "gate": None, "grade": None, "grade_score": None, "size_weight": None,
           "points": {}, "where_wrong": None, "flags": []}
    reg = regime(C, t)
    I = C.trk[1].I_at(t)
    st = C.trk[1].state(t)
    rec3 = C.f1.out.get(t) or {}
    l4, l5, l6 = C.L4.get(t) or {}, C.L5.get(t) or {}, C.L6.get(t) or {}
    pts = out["points"]
    st3 = C.st[2]["states"][t]
    d3 = d3_trend(C, t)
    pts["1_htf_state"] = {"regime": reg, "d3": d3}
    pts["2_parent"] = {"d2": st3["trend"], "protected": st3["protected"], "I": None if I is None else
                       {"dir": I["dir"], "origin": round(I["origin"].price, 2), "end": round(I["end"].price, 2)}}

    def stop(kind, gate, why):
        out.update(decision=kind, gate=gate, where_wrong=why)
        return out
    # ---- G-A
    if I is None:
        return stop(WAIT, "G-A", "I नाही")
    d = I["dir"]
    size = 1.0
    grade_adj = 0.0
    rg = reg["regime"]
    if rg in (UP, DOWN):
        if (rg == UP) != (d > 0):
            return stop(NO_TRADE, "G-A", "against_parent")
    elif rg == RANGE:
        if I["mode"] != "range_alt":
            return stop(WAIT, "G-A", "range mode: I range_alt नाही")
        band = range_band(C, t)
        if band is None:
            return stop(WAIT, "G-A", "range mode: पट्टा नाही")
        top, bot = band
        third = (top - bot) / 3.0
        c = C.A["c"][t]
        closed = np.flatnonzero((C.h1["E"] >= 0) & (C.h1["E"] <= t))
        s1h = C.h1["S"][closed[-1]] if len(closed) else np.nan
        mid = (top + bot) / 2.0
        if (d > 0 and c > bot + third) or (d < 0 and c < top - third) or (np.isfinite(s1h) and abs(c - mid) <= s1h):
            return stop(WAIT, "G-A", "range मध्ये (कडेच्या तृतीयांशात नाही)")
        return range_mode(C, t, d, out, stop, (top, bot), I, st, l4, l5, l6, rec3, reg)
    elif rg == TRANS:
        if reg["dir"] != d or not reg["pullback_held"]:
            return stop(WAIT, "G-A", "transition: break-दिशा / held pullback नाही")
        size *= float(s["reduce_size"])
    elif rg == BARB:
        return stop(NO_TRADE, "G-A", "barbwire")
    else:
        return stop(WAIT, "G-A", "drift")
    if d3 in (SST.UPT, SST.DNT) and (d3 == SST.UPT) != (d > 0):
        return stop(NO_TRADE, "G-A", "HTF veto (D3)")
    if d3 not in (SST.UPT, SST.DNT, SST.RNG):
        if s["htf_unknown_action"] == "block":
            return stop(NO_TRADE, "G-A", "htf_unknown")
        grade_adj += float(s["w_htf_unknown"])
        out["flags"].append("htf_unknown")
    if st3["reversal"] is not None:
        pol = (C.ext.get("gray_policy") or s["gray_policy"])
        if pol == "block":
            return stop(NO_TRADE, "G-A", "Gray-1 (D2 CHoCH इशारा) · gray_policy block")
        abhi = C.ext.get("abhi_dir")
        if abhi is None or abhi != d:
            return stop(NO_TRADE, "G-A", "Gray-1 · Abhi दिशा नाही / उलट")
        size *= float(s["reduce_size"])
        out["flags"].append("gray-reduce")
    # ---- G-B
    if must_hold_broken(C, t, d):
        return stop(NO_TRADE, "G-B", "D2 must-hold real break")
    # ---- G-G (आधी position_ban ⇒ no_trade)
    pref = rec3.get("pref") if rec3.get("agg") != "none" else None
    pos = rec3.get("position") or {}
    pts["5_pattern"] = None if pref is None else {"family": pref["family"], "state": pref["state"], "score": pref["score"]}
    pts["6_complete"] = {"state": rec3.get("agg"), "position_ban": bool(pos.get("ban")), "final_flag_risk": rec3.get("final_flag_risk")}
    if pos.get("ban"):
        return stop(NO_TRADE, "G-G", f"position_ban (D2: {pos.get('where')})")
    # ---- G-C
    area = _area(C, t, d, l4, l5)
    pts["7_area"] = area and {k: v for k, v in area.items() if k != "band"} | {"band": [round(x, 2) for x in area["band"]]}
    if area is None:
        return stop(WAIT, "G-C", "area नाही")
    # ---- G-D
    m = l4.get("momentum") or rec3.get("momentum") or {}
    v = m.get("verdict")
    onk = l6.get("label") == "K संपतोय"
    pts["4_character"] = {"momentum": v, "danger": m.get("danger"), "choch_strict": (st.get("flags") or {}).get("choch_strict")}
    if not (v == "कमकुवत होतोय" or (v == "अस्पष्ट" and onk)):
        return stop(WAIT, "G-D", f"momentum {v}")
    # ---- G-G (अवस्था)
    k_base = (l5.get("k_base") or {})
    s5 = False
    if pref is None or pref["state"] in ("forming_A", "forming_B", "in_X", "in_triangle", "forming_Y", "forming_wedge", "impulse_K"):
        return stop(WAIT, "G-G", "pattern अवस्था " + ("ओळखता येत नाही" if pref is None else pref["state"]))
    if pref["state"] == "final_leg_in_progress":
        short = "C_short_possible" in (pref.get("flags") or [])
        if not (k_base.get("bar") == t or short):
            return stop(WAIT, "G-G", "final_leg_in_progress")
        sot = (st.get("I") or {}).get("SOT_trend")
        if not sot and not l6.get("at_impulse_end"):
            s5 = True
        else:
            pol = (C.ext.get("gray_policy") or s["gray_policy"])
            if pol == "block":
                return stop(NO_TRADE, "G-G", "Gray-2 (S5 नाही) · gray_policy block")
            if C.ext.get("abhi_dir") != d:
                return stop(NO_TRADE, "G-G", "Gray-2 · Abhi दिशा नाही / उलट")
            size *= float(s["reduce_size"])
    # ---- G-E
    cm = commit_tier(C, t, d, area)
    depth = ((st.get("K") or {}).get("depth_main"))
    pts["8_depth"] = {"main": depth, "secondary": (st.get("K") or {}).get("depth_secondary")}
    flavours = []
    if cm is not None:
        if cm["engulf"]:
            flavours.append("engulf")
        if area["src"] == "zone" and area["ans"] == "हो (sweep)":
            flavours.append("sweep-reclaim")
        if (l5.get("k_tip") or {}).get("throw_over"):
            flavours.append("throw-over")
        cm_t = cm["candle"]["t"]
        if k_base.get("bar") == cm_t and area_touched(C, cm_t, area, int(s["tl_break_n"])):
            flavours.append("trendline-break")
        if not flavours:
            flavours.append("rejection")
    pts["9_price_failure"] = {"candle": cm, "flavours": flavours, "tier": int(s["tier"])}
    if cm is None or not cm["pass"]:
        return stop(WAIT, "G-E", "commitment candle नाही")
    if depth is not None and depth >= float(s["retrace_flavour"]) and not ({"sweep-reclaim", "throw-over"} & set(flavours)):
        return stop(WAIT, "G-E", "retrace ≥ 0.80 ⇒ फक्त sweep-reclaim / throw-over")
    # ---- G-F
    entry = cm["entry"]
    small = (cm["rng_ratio"] or 0) < float(s["g5_rng"]) or (cm["overlap3"] or 0) >= float(s["g6_overlap3"])
    mode = s["invalidation_mode"] if s["invalidation_mode"] != "auto" else ("structural" if small else "candle")
    kx = (st.get("K") or {}).get("extreme")
    if mode == "candle":
        inv = (cm["candle"]["l"] - float(s["sl_buffer"])) if d > 0 else (cm["candle"]["h"] + float(s["sl_buffer"]))
    else:
        cand = [x for x in (kx, area["band"][0] if d > 0 else area["band"][1]) if x is not None]
        inv = (min(cand) - float(s["sl_buffer"])) if d > 0 else (max(cand) + float(s["sl_buffer"]))
    target = I["end"].price
    risk = (entry - inv) * d
    rr = (target - entry) * d / risk if risk > 0 else None
    pts["10_risk"] = {"invalidation_mode": mode, "entry": round(entry, 2), "invalidation": round(inv, 2), "target": round(target, 2),
                      "rr": None if rr is None else round(rr, 2), "strike_beyond": round(inv, 2)}
    if rr is None or rr < float(s["min_rr"]):
        return stop(NO_TRADE, "G-F", f"R:R {rr if rr is None else round(rr, 2)} < {s['min_rr']}")
    # ---- G-H
    tt = C.ts[t].time()
    if tt >= pd.Timestamp(s["entry_end"]).time():
        return stop(NO_TRADE, "G-H", "15:15 नंतर नवी entry नाही")
    exp = C.ext.get("expiries")
    if exp is not None:
        ex = expiry_choice(C, t, exp)
        out["flags"] += ex["flags"]
        pts_ex = ex
    else:
        out["flags"].append("expiry data नाही")
        pts_ex = None
    # ---- संदर्भ (VIX / event / macro: फक्त size + नोंद; gate नाही)
    vix = (C.ext.get("vix") or {}).get(t)
    if vix is None:
        out["flags"].append("VIX data नाही")
    ctx = context_rows(C, t, d)
    out["flags"] += ctx["flags"]
    pts["11_context"] = {"open_noise": bool(l4.get("open_noise")), "vix": vix, "gap": bool(t in C.res["gap_bar_2s"]), "expiry": pts_ex,
                         "event": ctx["event"], "macro": ctx["macro"]}
    pts["12_hard_rules"] = {"exits": hard_exits(C, t, d)}
    pts["3_impulse_ok"] = {k: (st.get("I") or {}).get(k) for k in ("quality", "climax", "SOT_trend", "origin_bounded", "I_weak_basis")}
    # ---- grade + size
    g7 = second_attempt(C, t, d, area, I["end"].bar)
    out["flags"] += ["second attempt"] if g7 else []
    g = grade(C, t, d, area, cm, flavours, m, l6, rec3, st, s5, grade_adj, g7)
    out["grade_score"] = g
    out["grade"] = "A" if g >= float(s["grade_a"]) else ("B" if g >= float(s["grade_b"]) else "C")
    out["size_weight"] = size_weight(C, t, vix, size, d)
    out["decision"] = SETUP
    out["where_wrong"] = f"invalidation {inv:,.0f} (mode {mode})"
    out["paper_only"] = True
    out["approval_required"] = bool(s["signal_approval_required"])
    return out


def expiry_choice(C, t, exp):
    """त्या दिवशीचा expiry नाही; पुढच्या expiry पर्यंत < min_sessions_to_expiry sessions ⇒ त्याच्या पुढचा. Trading calendar = data मधले
    आजपर्यंतचे दिवस + पुढे weekdays − NSE सुट्ट्या (replay = live; भविष्यातले data दिवस वापरत नाही)."""
    import datetime as dt

    from elliott import contracts as EC
    d0 = pd.Timestamp(C.day[t])
    try:
        import config
        hol = set().union(*[set(v) for k, v in vars(config).items() if k.startswith("NSE_HOLIDAYS") and isinstance(v, (set, frozenset, list, tuple))])
    except Exception:                                                                # noqa: BLE001
        hol = set()
    cal = EC.TradingCalendar([x for x in C.res["sessions"] if x <= d0], hol)
    flags = []
    cands = sorted(pd.Timestamp(e).normalize() for e in exp if pd.Timestamp(e).normalize() >= d0)
    if cands and cands[0] == d0:
        cands = cands[1:]
        flags.append("आज expiry ⇒ पुढचा")
    pick = None
    for e in cands:
        n, day = 0, d0.date()
        while day < e.date():
            day += dt.timedelta(days=1)
            if cal.is_trading(day):
                n += 1
        if n >= int(C.s["min_sessions_to_expiry"]):
            pick = (e, n)
            break
        flags.append("जवळचा expiry फार जवळ ⇒ पुढचा")
    return {"expiry": None if pick is None else str(pick[0].date()), "sessions": None if pick is None else pick[1], "flags": flags}


def range_mode(C, t, d, out, stop, band, I, st, l4, l5, l6, rec3, reg):
    """§3a: range_alt I/K; G-C = थर 4 range-कड (d) zone; G-D = थर 6 range-fade पुरावा किंवा momentum; G-G = कडेकडची चाल impulse-K नाही;
    entry फक्त खालच्या / वरच्या तृतीयांशात (मध्य ±1 σ_1H नाही). मग G-E … G-I नेहमीसारखे."""
    s = C.s
    role = "buyer" if d > 0 else "seller"
    zs = [z for z in (l4.get("range_zone_bands") or []) if z[2] == role]
    A = C.A
    hit = None
    for bot, top, _ in zs:
        if A["l"][t] <= top and A["h"][t] >= bot:
            hit = (bot, top)
    if hit is None:
        return stop(WAIT, "G-C", "range mode: range-कड zone नाही")
    area = {"src": "range-कड zone", "band": hit, "ans": "हो", "stars": 1, "accept": False}
    out["points"]["7_area"] = {"src": area["src"], "band": [round(x, 2) for x in hit]}
    m = l4.get("momentum") or rec3.get("momentum") or {}
    if not (m.get("verdict") == "कमकुवत होतोय" or l6.get("label") == "range-fade पुरावा"):
        return stop(WAIT, "G-D", f"range mode: momentum {m.get('verdict')} / range-fade नाही")
    pref = rec3.get("pref") if rec3.get("agg") != "none" else None
    if pref is not None and pref["family"] == "impulse_k":
        return stop(WAIT, "G-G", "range mode: कडेकडची चाल impulse-K")
    cm = commit_tier(C, t, d, area)
    out["points"]["9_price_failure"] = {"candle": cm, "flavours": ["range-edge"], "tier": int(s["tier"])}
    if cm is None or not cm["pass"]:
        return stop(WAIT, "G-E", "commitment candle नाही")
    entry = cm["entry"]
    inv = (min(cm["candle"]["l"], hit[0]) - float(s["sl_buffer"])) if d > 0 else (max(cm["candle"]["h"], hit[1]) + float(s["sl_buffer"]))
    target = band[0] if d > 0 else band[1]                                           # range ची उलट कड
    risk = (entry - inv) * d
    rr = (target - entry) * d / risk if risk > 0 else None
    out["points"]["10_risk"] = {"invalidation_mode": "structural", "entry": round(entry, 2), "invalidation": round(inv, 2),
                                "target": round(target, 2), "rr": None if rr is None else round(rr, 2), "strike_beyond": round(inv, 2)}
    if rr is None or rr < float(s["min_rr"]):
        return stop(NO_TRADE, "G-F", f"R:R {rr if rr is None else round(rr, 2)} < {s['min_rr']}")
    if C.ts[t].time() >= pd.Timestamp(s["entry_end"]).time():
        return stop(NO_TRADE, "G-H", "15:15 नंतर नवी entry नाही")
    vix = (C.ext.get("vix") or {}).get(t)
    ctx = context_rows(C, t, d)
    out["flags"] += ctx["flags"] + ([] if vix is not None else ["VIX data नाही"])
    g = grade(C, t, d, area, cm, ["range-edge"], m, l6, rec3, st, False)
    out.update(decision=SETUP, grade_score=g, grade="A" if g >= float(s["grade_a"]) else ("B" if g >= float(s["grade_b"]) else "C"),
               size_weight=size_weight(C, t, vix, 1.0, d), where_wrong=f"invalidation {inv:,.0f} (range mode)", paper_only=True,
               approval_required=bool(s["signal_approval_required"]))
    out["flags"].append("range mode")
    return out


def second_attempt(C, t, d, area, k_from):
    """G7: याच area वर या K मध्ये (k_from नंतर) आधीची failed reclaim — candle चं उलट टोक पट्ट्यात / पलीकडे पण close trade-बाजूला नाही."""
    A = C.A
    bot, top = area["band"]
    for j in range(k_from + 1, t):
        far = A["l"][j] if d > 0 else A["h"][j]
        if ((far <= top) if d > 0 else (far >= bot)) and not ((A["c"][j] > top) if d > 0 else (A["c"][j] < bot)):
            return True
    return False


def grade(C, t, d, area, cm, flavours, m, l6, rec3, st, s5, adj=0.0, g7=False):
    s = C.s
    g = adj + min(max(area.get("stars", 1) - 1, 0), 2)
    g += float(s["w_g7"]) if g7 else 0.0
    if area.get("intersection"):
        g += float(s["w_cap"])
    g += float(s["w_onk"]) if l6.get("on_K") else 0.0
    g += float(s["w_rik"]) if l6.get("regular_in_K") else 0.0
    g += float(s["w_trap"]) if l6.get("at_impulse_end") else 0.0
    g += float(s["w_cascade"]) if l6.get("cascade") else 0.0
    pref = rec3.get("pref")
    g += float(pref["score"]) if pref else 0.0
    g += float(m.get("ratio") or 0.0)
    if {"sweep-reclaim", "throw-over"} & set(flavours):
        g += float(s["w_flavour"])
    kb = (C.L5.get(t) or {}).get("k_base") or {}
    if kb.get("bar") == t and any((kb.get("Q") or {}).values()):
        g += float(s["w_q"])
    if cm.get("g4_both"):
        g += float(s["w_g4both"])
    fl = st.get("flags") or {}
    g += float(s["w_quiet"]) if fl.get("pullback_quiet") else 0.0
    g += float(s["w_heavy"]) if fl.get("pullback_heavy") else 0.0
    g += float(s["w_flag"]) if rec3.get("final_flag_risk") else 0.0
    g += float(s["w_s5"]) if s5 else 0.0
    g += float(s["w_disagree"]) if l6.get("rsi_disagree") else 0.0
    d2 = C.st[2]["states"][t]["trend"]
    d3 = d3_trend(C, t)
    if d2 == d3 and d2 in (SST.UPT, SST.DNT):
        g += float(s["w_d2d3"])
    if (C.L4.get(t) or {}).get("open_noise"):
        g += float(s["w_open"])
    if area.get("steep"):
        g += float(s["w_steep"])                                                      # तीव्र रेघ (थर 5 उत्तर 11): नोंद + grade
    return round(float(g), 3)


def size_weight(C, t, vix, base=1.0, d=None):
    """Size (gate नाही): VIX > vix_hi ⇒ ×vix_size; VIX > vix_extreme ⇒ size_floor; VIX jump ⇒ ×vix_size; event hold-window ⇒
    ×reduce_size; macro trade-विरुद्ध (≥ macro_against) ⇒ ×macro_size. Floor = size_floor."""
    s = C.s
    w = base
    if vix is not None:
        if vix > float(s["vix_hi"]):
            w *= float(s["vix_size"])
        if vix > float(s["vix_extreme"]):
            w = float(s["size_floor"])
        jump = (C.ext.get("vix_jump") or {}).get(t)
        if jump is not None and jump >= float(s["vix_jump"]):
            w *= float(s["vix_size"])
    if d is not None:
        ctx = context_rows(C, t, d)
        if ctx["event"]:
            w *= float(s["reduce_size"])
        if ctx["macro_against"]:
            w *= float(s["macro_size"])
    return round(max(w, float(s["size_floor"])), 3)


def context_rows(C, t, d):
    """Event calendar (ext["event_bars"]: t ⇒ नाव, `added_on` ≤ त्या दिवशी — known_at लावून आधीच तयार) आणि macro row (ext["macro"]:
    t ⇒ [-1, 1], fetch known_at ≤ t). फक्त नोंद / size."""
    ev = (C.ext.get("event_bars") or {})
    name = ev.get(t) if isinstance(ev, dict) else (True if t in ev else None)
    macro = (C.ext.get("macro") or {}).get(t)
    against = macro is not None and float(np.clip(macro, -1, 1)) * d <= -float(C.s["macro_against"])
    flags = (["event hold-window ⇒ size कमी"] if name else []) + (["macro trade-विरुद्ध ⇒ size कमी"] if against else []) + \
        ([] if macro is not None else ["macro data नाही"])
    return {"event": name, "macro": macro, "macro_against": bool(against), "flags": flags}


def area_touched(C, t, area, n):
    """Trendline-break flavour: break candle t च्या **आधीच्या** n candles ([t − n, t − 1]) मध्ये area स्पर्श. रेघ area ⇒ थर 5 चा touch
    bar (रेघेची त्या वेळची किंमत; उतरती रेघ t च्या ± τ पट्ट्याशी तुलना नाही); zone ⇒ पट्टा."""
    if area.get("src") == "रेघ":
        b = area.get("bar")
        return b is not None and t - n <= b < t
    bot, top = area["band"]
    A = C.A
    return any(A["l"][j] <= top and A["h"][j] >= bot for j in range(max(t - n, 0), t))


def commit_tier(C, t, d, area):
    """Tier ≤ 1: commitment candle (G1–G6 + G8 hard) — entry = तिचा close. Tier 2: t−1 चा commitment pass **आणि** t चा close त्याच्या
    trade-टोकापलीकडे (पुढची candle confirm) — entry = t चा close."""
    s = C.s
    if int(s["tier"]) < 2:
        cm = commitment(C, t, d, area)
        if cm is not None:
            cm = dict(cm, entry=cm["candle"]["c"])
        return cm
    if t < 1 or C.day[t - 1] != C.day[t]:
        return None                                                                  # आदल्या session ची candle + आजची ⇒ नाही
    cm = commitment(C, t - 1, d, area)
    if cm is None:
        return None
    c = C.A["c"][t]
    ok = (c > cm["candle"]["h"]) if d > 0 else (c < cm["candle"]["l"])
    out = dict(cm)
    out.update({"pass": bool(cm["pass"] and ok), "tier2_confirm": bool(ok), "entry": c})
    return out


def run(C, bars):
    return {t: decide(C, t) for t in bars}
