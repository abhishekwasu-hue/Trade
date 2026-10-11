"""decision3/method.py — थर v2.2 पायरी C: ③ Pullback (K), ④ power shift, ⑥ commitment, ⑦ risk, §5–§7 पुरावे आणि conviction.

कठोर नियम फक्त तीन (spec §6.2): H1 दिशा = Daily Dow (①); H2 entry pullback नंतर significant level वर, किंमत level मध्ये उलट बाजूने
आलेली — breakout / gap-through ⇒ नाही (②③); H3 SL आणि target ठरतात, R:R ≥ 3 (⑦). ⑥ commitment candle = entry trigger (entry bar).
बाकी सगळं (④ power shift, ★, trap / sweep, दुसरा प्रयत्न, signal-bar गुणवत्ता, engulf, RSI, volume, pattern) = पुरावा ⇒ conviction
(A / B / weak / against). §5.3 overlap नियम (3+ overlapping candles + doji ⇒ range अवस्था) = gate. Fixed "मोठा / लहान" आकडे नाहीत —
तुलना मागच्या candles शी; सगळे आकडे register मध्ये.
"""
import numpy as np
import pandas as pd

from . import levels as LV
from . import settings as S3

UP, DOWN = 1, -1


def _dir(trend, level_role=None):
    if trend == "UP":
        return UP
    if trend == "DOWN":
        return DOWN
    if trend == "RANGE" and level_role is not None:
        return UP if level_role == LV.SUP else DOWN
    return 0


# ------------------------------------------------------------------------------------------------ ③ K
class Pullbacks:
    """प्रत्येक 15M bar ला दोन्ही दिशांसाठी K state (sequential ⇒ truncation-safe).
    Impulse = trend-दिशेचा BOS (D2); origin = BOS आधीचा उलट D2 pivot; I_end = BOS नंतरचं टोक. K उघडते: I_end नंतर पहिला उलट D1 pivot
    confirm किंवा किंमत trade-बाजूच्या level मध्ये — जे आधी. नवं टोक ≥ k_reset_sigma × σ_1H ने पुढे ⇒ नवा I_end (K बंद, पुन्हा उघडेल);
    कमी ⇒ तेच टोक. Origin close ने तुटला ⇒ K रद्द (नव्या BOS पर्यंत)."""

    def __init__(self, V):
        self.V = V
        lv = V.levels
        self.lv = lv
        self.A = lv.A
        self.n = lv.n
        self.sig1h = lv.sig1h
        self.p1 = sorted(V.res["pivots"][1], key=lambda p: p.confirm_bar)
        self.state = {UP: [], DOWN: []}
        for d in (UP, DOWN):
            self._run(d)

    def _run(self, d):
        H, L, C = self.A["high"], self.A["low"], self.A["close"]
        bos = {t: (dd, o) for t, dd, o in self.lv.bos if dd == d}
        imp = None
        out = self.state[d]
        kr = float(self.V.s["k_reset_sigma"])
        for t in range(self.n):
            if t in bos:
                o = bos[t][1]
                ext = H[t] if d == UP else L[t]
                imp = {"origin": o.price, "origin_bar": o.bar, "bos_bar": t, "i_end": float(ext), "i_end_bar": t, "open": False,
                       "k_open_bar": None, "k_ext": None, "k_ext_bar": None, "why_open": None, "legs": 0}
            elif imp is not None:
                if (C[t] - imp["origin"]) * d < 0:
                    imp = None                                           # origin close ने तुटला ⇒ K रद्द
                else:
                    ext = H[t] if d == UP else L[t]
                    beyond = (ext - imp["i_end"]) * d
                    sg = self.sig1h[t] if np.isfinite(self.sig1h[t]) else 0.0
                    if beyond >= kr * sg and beyond > 0:
                        imp.update(i_end=float(ext), i_end_bar=t, open=False, k_open_bar=None, k_ext=None, k_ext_bar=None,
                                   why_open=None, legs=0)
                    elif not imp["open"]:
                        piv = [p for p in self.p1 if p.confirm_bar <= t and p.bar >= imp["i_end_bar"]
                               and p.kind == ("H" if d == UP else "L")]
                        lvl = [x for x in self.lv.snapshot(t) if x["role"] == (LV.SUP if d == UP else LV.RES)
                               and (L[t] <= x["hi"] if d == UP else H[t] >= x["lo"]) and (x["hi"] < imp["i_end"] if d == UP else x["lo"] > imp["i_end"])]
                        if piv or lvl:
                            imp.update(open=True, k_open_bar=t, why_open="उलट D1 swing confirm" if piv else "trade-बाजूच्या level मध्ये")
                    if imp is not None and imp["open"]:
                        cext = L[t] if d == UP else H[t]
                        if imp["k_ext"] is None or (cext - imp["k_ext"]) * d < 0:
                            imp["k_ext"], imp["k_ext_bar"] = float(cext), t
                        legs = [p for p in self.p1 if imp["k_open_bar"] is not None and p.confirm_bar <= t
                                and p.bar > imp["i_end_bar"] and p.kind == ("L" if d == UP else "H")]
                        imp["legs"] = len(legs) + 1                       # counter पाय (D1 counter swings + चालू)
            out.append(dict(imp) if imp is not None else None)

    def at(self, t, d):
        return self.state[d][t] if d in self.state else None


# ------------------------------------------------------------------------------------------------ ③ ✔ (H2)
def at_level(A, t, d, lvl, win=1):
    """③: शेवटच्या `win` bars (t सकट) पैकी एकाचा wick level पट्ट्यात / स्पर्श ("level मध्ये / लगत"), उलट बाजूने आलेली (पहिल्या
    स्पर्शाआधीचा close trade-बाजूला), आणि bar t gap / close ने पार नाही (breakout ✘)."""
    lo, hi = lvl["lo"], lvl["hi"]
    o, c = A["open"][t], A["close"][t]
    hits = [i for i in range(max(0, t - int(win) + 1), t + 1) if A["low"][i] <= hi and A["high"][i] >= lo]
    if not hits:
        return False, "level ला स्पर्श नाही"
    i1 = hits[0]
    prev_c = A["close"][i1 - 1] if i1 > 0 else A["close"][i1]
    if d == UP:
        if o < lo:
            return False, "gap ने level खाली पार (breakout) ⇒ नाही"
        if c < lo:
            return False, "close level खाली (पार) ⇒ नाही"
        if prev_c < lo:
            return False, "किंमत खालून आली (उलट बाजू नाही)"
    else:
        if o > hi:
            return False, "gap ने level वर पार (breakout) ⇒ नाही"
        if c > hi:
            return False, "close level वर (पार) ⇒ नाही"
        if prev_c > hi:
            return False, "किंमत वरून आली (उलट बाजू नाही)"
    return True, "pullback level मध्ये, उलट बाजूने" + ("" if i1 == t else f" (स्पर्श {t - i1} bar आधी)")


def at_level_or_confirm(A, t, d, lvl, s, tss=None):
    """③ + Q16 "वाट एक candle": t ला स्पर्श खिडकीत नसला, पण t − 1 ला ③ ✔ आणि t − 1 ची candle doji / inside (⑥ ने वाट) होती ⇒ t
    ही पुष्टीची candle ⇒ ③ ✔ वारसा. breakout / gap तपासणी तरीही t वर (at_level सारखी)."""
    win = int(s["touch_window_bars"])
    ok, why = at_level(A, t, d, lvl, win)
    if ok or t < 2:
        return ok, why
    o, c = A["open"][t], A["close"][t]
    if (d == UP and (o < lvl["lo"] or c < lvl["lo"])) or (d == DOWN and (o > lvl["hi"] or c > lvl["hi"])):
        return ok, why                                                     # t ने level पार ⇒ breakout, वारसा नाही
    ok_p, _ = at_level(A, t - 1, d, lvl, win)
    if ok_p and commitment(A, t - 1, d, lvl, s, tss)[2].get("wait") in ("doji", "inside"):
        return True, "doji / inside नंतरची पुष्टी candle (③ आधीच्या bar वरून)"
    return ok, why


# ------------------------------------------------------------------------------------------------ candle read (§6.6)
def candle_read(A, t, s=None):
    """कोण जिंकला + ताकद. रिटर्न dict. "मोठा" = मागच्या `candle_avg_n` च्या सरासरीपेक्षा (§5.2)."""
    s = s or S3.DEFAULTS
    n_avg = int(s["candle_avg_n"])
    o, h, l, c = (float(A[k][t]) for k in ("open", "high", "low", "close"))
    rng = max(h - l, 1e-9)
    body = abs(c - o)
    lo_i = max(0, t - n_avg)
    bodies = np.abs(A["close"][lo_i:t] - A["open"][lo_i:t])
    ranges = A["high"][lo_i:t] - A["low"][lo_i:t]
    pos = (c - l) / rng
    return {"winner": "buyers" if c > o else ("sellers" if c < o else "none"), "body_pct": body / rng, "close_pos": pos,
            "upper_wick": (h - max(o, c)) / rng, "lower_wick": (min(o, c) - l) / rng,
            "big_body": bool(len(bodies)) and body > float(np.mean(bodies)), "big_range": bool(len(ranges)) and rng > float(np.mean(ranges)),
            "doji": body / rng < float(s["doji_body_max"])}


# ------------------------------------------------------------------------------------------------ ④ power shift
def power_shift(A, t, d, k, s):
    """(a) counter candles च्या ranges शेवटच्या 3 मध्ये लहान होत; (b) शेवटच्या 3 bodies overlap ≥ power_overlap; (c) शेवटचा counter push
    नवं टोक नाही किंवा sweep करून परत; (d) trend-दिशेचे wicks / rejection. ≥ power_shift_min ⇒ ✔. (e) RSI पूरक (NA)."""
    items = {}
    k0 = k["k_open_bar"] if k and k.get("k_open_bar") is not None else max(0, t - int(s["power_fallback_bars"]))
    idx = [i for i in range(k0, t + 1) if (A["close"][i] - A["open"][i]) * d < 0]
    r = [A["high"][i] - A["low"][i] for i in idx[-3:]]
    items["a_shrinking"] = len(r) == 3 and r[0] > r[1] > r[2]
    bl = [(min(A["open"][i], A["close"][i]), max(A["open"][i], A["close"][i])) for i in range(max(0, t - 2), t + 1)]
    ov = []
    for (a0, a1), (b0, b1) in zip(bl[:-1], bl[1:]):
        m = min(a1 - a0, b1 - b0)
        ov.append((min(a1, b1) - max(a0, b0)) / m if m > 0 else 0.0)
    items["b_overlap"] = len(ov) == 2 and all(x >= float(s["power_overlap"]) for x in ov)
    ext = k.get("k_ext") if k else None
    eb = k.get("k_ext_bar") if k else None
    if ext is not None and eb is not None:
        no_new = eb < t
        cur = A["low"][t] if d == UP else A["high"][t]
        prev_ext = min(A["low"][k0:t]) if d == UP and t > k0 else (max(A["high"][k0:t]) if t > k0 else cur)
        swept = (cur - prev_ext) * d < 0 and (A["close"][t] - prev_ext) * d > 0
        items["c_no_new_extreme_or_sweep"] = bool(no_new or swept)
        items["sweep"] = bool(swept)
    else:
        items["c_no_new_extreme_or_sweep"] = False
        items["sweep"] = False
    rej = False
    for i in range(max(0, t - 1), t + 1):
        cr = candle_read(A, i, s)
        w = cr["lower_wick"] if d == UP else cr["upper_wick"]
        ow = cr["upper_wick"] if d == UP else cr["lower_wick"]
        rej = rej or (w >= cr["body_pct"] and w > ow)
    items["d_rejection_wick"] = rej
    items["e_rsi_div"] = None                                            # पूरक; थर 6 जोडणी पुढे (NA)
    n = sum(1 for k_ in ("a_shrinking", "b_overlap", "c_no_new_extreme_or_sweep", "d_rejection_wick") if items[k_])
    return n >= int(s["power_shift_min"]), n, items


def range_broken_by(A, t, d, s=None):
    """Q24: commitment candle ने मागच्या `range_state_n` candles च्या पट्ट्याबाहेर trade-दिशेने close केला ⇒ range अवस्था संपली."""
    s = s or S3.DEFAULTS
    n = int(s["range_state_n"])
    if t < n:
        return False
    c = float(A["close"][t])
    return bool(c > float(np.max(A["high"][t - n:t]))) if d == UP else bool(c < float(np.min(A["low"][t - n:t])))


def range_state(A, t, s=None):
    """§5.3 gate: शेवटच्या n candles बहुतांश overlap (प्रत्येक जोडी ≥ range_overlap_min) आणि त्यात doji ⇒ range अवस्था."""
    s = s or S3.DEFAULTS
    n = int(s["range_state_n"])
    if t < n - 1:
        return False
    ix = list(range(t - n + 1, t + 1))
    ok = True
    for a, b in zip(ix[:-1], ix[1:]):
        lo, hi = max(A["low"][a], A["low"][b]), min(A["high"][a], A["high"][b])
        m = min(A["high"][a] - A["low"][a], A["high"][b] - A["low"][b])
        ok = ok and m > 0 and (hi - lo) / m >= float(s["range_overlap_min"])
    return ok and any(candle_read(A, i, s)["doji"] for i in ix)


# ------------------------------------------------------------------------------------------------ ⑥ commitment
def _ohlc(A, i):
    return float(A["open"][i]), float(A["high"][i]), float(A["low"][i]), float(A["close"][i])


def _same_window(tss, t, i, s):
    """merged / संदर्भ candle i हा t च्या दिवसाचा आणि entry_start नंतरचा? (tss नसेल ⇒ हो)."""
    if tss is None:
        return True
    ti, tt = pd.Timestamp(tss[i]), pd.Timestamp(tss[t])
    return ti.normalize() == tt.normalize() and ti.strftime("%H:%M") >= s["entry_start"]


def reversal_form(A, t, d, s, tss=None):
    """Q16: level वरची reversal candle ओळख (तर्काने, checklist नाही). रिटर्न (form, merged) किंवा None. क्रम: engulf, star, inside_break,
    doji_confirm, tweezer, pin, strong_close (1 candle), strong_close_2 (2 merged). d = trade दिशा (UP ⇒ खाली नकार, वर close)."""
    if t < 1:
        return None
    o, h, lo, c = _ohlc(A, t)
    po, ph, pl, pc = _ohlc(A, t - 1)
    rng, prng = max(h - lo, 1e-9), max(ph - pl, 1e-9)
    body = (c - o) * d
    pbody = (pc - po) * d
    two = _same_window(tss, t, t - 1, s)                                  # 2-candle forms: t − 1 आजचा / खिडकीत
    doji_max, cbody, cfrac = float(s["doji_body_max"]), float(s["commit_body"]), float(s["commit_close_frac"])
    pos = (c - lo) / rng if d == UP else (h - c) / rng                     # close trade-बाजूच्या टोकाजवळ (1 = टोकावर)
    rej = (min(o, c) - lo) / rng if d == UP else (h - max(o, c)) / rng     # level कडचा नकाराचा wick
    opp = (h - max(o, c)) / rng if d == UP else (min(o, c) - lo) / rng
    if two and body > 0 and pbody < 0 and max(o, c) >= max(po, pc) and min(o, c) <= min(po, pc):
        return "engulf", 1                                                 # pullback च्या शेवटच्या candle ला गिळलं
    if two and t >= 2 and body > 0 and _same_window(tss, t, t - 2, s):
        qo, qh, ql, qc = _ohlc(A, t - 2)
        q_rng, qbody = max(qh - ql, 1e-9), (qc - qo) * d
        if qbody < 0 and -qbody / q_rng >= cbody and abs(pc - po) / prng <= float(s["star_body_max"]) and \
                (c - (qo + qc) / 2) * d > 0:
            return "star", 2                                               # morning / evening star (t − 1 लहान, t परत अर्ध्या पलीकडे)
        inside = ph <= qh and pl >= ql
        harami = max(po, pc) <= max(qo, qc) and min(po, pc) >= min(qo, qc)
        if (inside or harami) and (c - (ph if d == UP else pl)) * d > 0:
            return "inside_break", 2                                       # inside / harami नंतर trade-दिशेचा break
    if two and body > 0 and abs(pc - po) / prng < doji_max and (c - (ph if d == UP else pl)) * d > 0:
        return "doji_confirm", 2                                           # level वर doji, पुढची candle पुष्टी
    if two and body > 0 and pbody <= 0 and \
            abs((lo - pl) if d == UP else (h - ph)) <= float(s["tweezer_tol"]) * (rng + prng) / 2:
        return "tweezer", 2                                                # tweezer bottom / top
    if rej >= float(s["pin_wick_min"]) and rej > opp and pos >= cfrac:
        return "pin", 1                                                    # pin bar / hammer / shooting star
    if body > 0 and body / rng >= cbody and pos >= cfrac and opp < body / rng:
        return "strong_close", 1
    if two:                                                                # ≤ 2 merged strong close (spec ⑥)
        mo, mh, ml = po, max(h, ph), min(lo, pl)
        mr = max(mh - ml, 1e-9)
        mb = (c - mo) * d
        mpos = (c - ml) / mr if d == UP else (mh - c) / mr
        mopp = (mh - max(mo, c)) / mr if d == UP else (min(mo, c) - ml) / mr
        if mb > 0 and mb / mr >= cbody and mpos >= cfrac and mopp < mb / mr:
            return "strong_close_2", 2
    return None


def commitment(A, t, d, lvl, s, tss=None):
    """⑥ Q16 (Abhi): commitment = level वरची price-reversal candle (≤ 2 merged); कोणताही ओळखलेला reversal form चालतो.
    किमान सामायिक अट: close मागच्या candle च्या **close** पलीकडे trade-दिशेने (`commit_beyond` = close, default; "extreme" = what-if) आणि
    (merged 2-candle form ⇒ "मागची" = pattern आधीची candle t − 2, त्याच दिवसाची असेल तर; Q30)
    close level च्या trade-बाजूला / level मध्ये. Grade: मागच्या candle च्या extreme पलीकडे close किंवा engulf ⇒ A; बाकी (wick नकार + close
    पलीकडे) ⇒ B. वाट: चालू candle pullback-दिशेची / doji / inside bar ⇒ पुढच्या candle ची वाट. वेळ-खिडकी settings."""
    if s["commit_beyond"] not in ("extreme", "close"):
        raise ValueError(f"commit_beyond {s['commit_beyond']!r} — extreme / close पैकी")
    if tss is not None:                                                    # tss = 15M bars चे timestamps (bar सुरुवात)
        hm = pd.Timestamp(tss[t]).strftime("%H:%M")
        if not (s["entry_start"] <= hm < s["entry_end"]):               # 15:15 चा bar बाजार बंदला close ⇒ entry नाही (v2.1 सारखं)
            return False, "entry वेळ-खिडकीबाहेर", {}
    if t < 1:
        return False, "commitment candle नाही", {}
    o, h, lo, c = _ohlc(A, t)
    po, ph, pl, pc = _ohlc(A, t - 1)
    rng = max(h - lo, 1e-9)
    beyond_close = (c - pc) * d > 0
    beyond_ext = (c - (ph if d == UP else pl)) * d > 0
    side = (c >= lvl["lo"]) if d == UP else (c <= lvl["hi"])
    if abs(c - o) / rng < float(s["doji_body_max"]):
        return False, "doji level वर — पुढच्या candle ची वाट", {"wait": "doji"}
    if h <= ph and lo >= pl:
        return False, "inside bar — पुढच्या candle ची वाट", {"wait": "inside"}
    if (c - o) * d < 0 and not beyond_close:
        return False, "candle अजून pullback-दिशेची — वाट", {"wait": "pullback"}
    fm = reversal_form(A, t, d, s, tss)
    if fm is not None and fm[1] == 2 and t >= 2 and _same_window(tss, t, t - 2, s):
        r = t - 2                                                          # merged (≤ 2) = एक candle ⇒ "मागची" = pattern आधीची (Q30)
        qo, qh, ql, qc = _ohlc(A, r)
        beyond_close = (c - qc) * d > 0
        beyond_ext = (c - (qh if d == UP else ql)) * d > 0
    need = beyond_close if s["commit_beyond"] == "close" else beyond_ext
    if not (need and side):
        return False, "commitment candle नाही" + ("" if side else " (close level पलीकडे चुकीच्या बाजूला)"), {}
    if fm is None:
        return False, "commitment candle नाही (reversal form नाही)", {}
    form, merged = fm
    grade = "A" if (beyond_ext or form == "engulf") else "B"
    cm = {"form": form, "merged": merged, "grade": grade, "beyond_extreme": bool(beyond_ext), "engulf": form == "engulf",
          "body_pct": round(abs(c - o) / rng, 2), "big_body": candle_read(A, t, s)["big_body"], "big_range": candle_read(A, t, s)["big_range"]}
    return True, f"commitment {form} ({merged} candle) · grade {grade}", cm


# ------------------------------------------------------------------------------------------------ ⑦ risk
def risk(V, t, d, lvl, k, s):
    """SL = level आणि K टोक पलीकडे + buffer (σ_15M × sl_buffer_sigma); target = I_end किंवा विरुद्ध बाजूचा जवळचा जिवंत level (जवळचा)."""
    A = V.levels.A
    entry = float(A["close"][t])
    sg15 = V.res["sigma"].get(pd.Timestamp(V.levels.ts[t]).normalize(), np.nan)
    buf = float(s["sl_buffer_sigma"]) * (sg15 if np.isfinite(sg15) else 0.0)
    kx = k.get("k_ext") if k else None
    if d == UP:
        sl = min(lvl["lo"], kx if kx is not None else lvl["lo"]) - buf
        opp = [x["lo"] for x in V.levels.snapshot(t) if x["role"] == LV.RES and x["lo"] > entry]
        cands = [x for x in ([k["i_end"]] if k else []) + opp if x > entry]
        tgt = min(cands) if cands else None
    else:
        sl = max(lvl["hi"], kx if kx is not None else lvl["hi"]) + buf
        opp = [x["hi"] for x in V.levels.snapshot(t) if x["role"] == LV.SUP and x["hi"] < entry]
        cands = [x for x in ([k["i_end"]] if k else []) + opp if x < entry]
        tgt = max(cands) if cands else None
    rk = (entry - sl) * d
    rr = (tgt - entry) * d / rk if (tgt is not None and rk > 0) else None
    ok = rr is not None and rr >= float(s["min_rr"])
    return ok, {"entry": round(entry, 2), "sl": round(sl, 2), "target": None if tgt is None else round(tgt, 2),
                "rr": None if rr is None else round(rr, 2)}


# ------------------------------------------------------------------------------------------------ conviction caps (Q15)
CONV_RANK = {"A": 3, "B": 2, "weak": 1, "against": 0}


def cap_min(a, b):
    """दोन caps पैकी कडक (None = cap नाही)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if CONV_RANK[a] <= CONV_RANK[b] else b


def cap_conv(conv, cap):
    """conviction ला cap (A / B / weak) — cap पेक्षा वरचं ⇒ cap; against तसाच."""
    if cap is None or conv is None or conv not in CONV_RANK:
        return conv
    return cap if CONV_RANK[conv] > CONV_RANK[cap] else conv


# ------------------------------------------------------------------------------------------------ §5.1 पहिला पाय
def first_leg_cap(conv, legs, sweeps, commit_strong):
    """§5.1: पहिल्याच counter-leg नंतर (H1 / L1) trade फक्त level ★ ≥ 2 आणि मजबूत signal-bar असेल तर — आणि तरीही कमाल B;
    नाहीतर weak (दुसऱ्या पायाची वाट). दुसरा+ पाय ⇒ बदल नाही."""
    if legs != 1 or conv not in ("A", "B"):
        return conv
    return "B" if (sweeps >= 2 and commit_strong) else "weak"


# ------------------------------------------------------------------------------------------------ B1 / B2 (§5.2)
def b_plans(A, t, d, rk, merged, s):
    """B1 = commitment close वर entry (default); B2 = signal-bar (≤ 2 merged ⇒ संपूर्ण merged candle) extreme च्या `entry_tick`
    पलीकडे break. SL / target तेच (⑦); B2 चा R:R नव्या entry ने (< min_rr ⇒ ok False). Risk / target नसेल ⇒ None."""
    if not rk or rk.get("target") is None or d not in (UP, DOWN):
        return None
    i0 = max(0, t - max(1, int(merged or 1)) + 1)
    tick = float(s["entry_tick"])
    trig = float(max(A["high"][i0:t + 1])) + tick if d == UP else float(min(A["low"][i0:t + 1])) - tick
    sl, tgt = float(rk["sl"]), float(rk["target"])
    risk2 = (trig - sl) * d
    rr2 = (tgt - trig) * d / risk2 if risk2 > 0 else None
    return {"B1": {"entry": rk["entry"], "sl": sl, "target": tgt, "rr": rk["rr"]},
            "B2": {"trigger": round(trig, 2), "sl": sl, "target": tgt, "rr": None if rr2 is None else round(rr2, 2),
                   "ok": rr2 is not None and rr2 >= float(s["min_rr"])}}


def plans_of(V, r):
    """engine row ⇒ b_plans (setup नसेल / level नसेल ⇒ None)."""
    lv = r.get("level")
    if not lv:
        return None
    d = UP if lv["role"] == LV.SUP else DOWN
    return b_plans(V.levels.A, int(r["bar"]), d, r.get("risk"), (r.get("commit") or {}).get("merged"), V.s)


# ------------------------------------------------------------------------------------------------ §6 conviction
def conviction(ev, s):
    """ev = {पुरावा: True / False / None (NA)}; वजन register मध्ये (W). NA ⇒ बेरजेत नाही (कमाल सुद्धा नाही)."""
    W = s["evidence_weights"]
    tot = mx = 0.0
    for k, w in W.items():
        v = ev.get(k)
        if v is None:
            continue
        if w >= 0:
            mx += w
            tot += w if v else 0.0
        else:
            tot += w if v else 0.0
    score = tot / mx if mx > 0 else 0.0
    if score >= float(s["conv_a"]):
        lvl = "A"
    elif score >= float(s["conv_b"]):
        lvl = "B"
    elif score >= float(s["conv_weak"]):
        lvl = "weak"
    else:
        lvl = "against"
    missing = [k for k, w in W.items() if w > 0 and ev.get(k) is False]
    return lvl, round(score, 2), missing
