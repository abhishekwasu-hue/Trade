"""decision3/method.py — थर v2.2 पायरी C: ③ Pullback (K), ④ power shift, ⑥ commitment, (⑦ risk — legacy `rr_step` फक्त), §5–§7 पुरावे, conviction.
Abhi 13 Oct: R:R engine मधून काढला (default `rr_step` = False) — setup ⑥ (commitment + c1) वर संपतो; SL / target dashboard चे.

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
                               and x.get("state") != "BROKEN"                 # K4: BROKEN ⇒ trade location नाही (`Levels.active` सारखं)
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
def _ratio_rules(s):
    """`candle_rule`: "compare" (method §3 — body and wicks compared with each other, "big" = larger than the other candles of the same
    visit) or "ratio" (the legacy fractions of the range / average of the last `candle_avg_n`), what-if only."""
    r = (s or S3.DEFAULTS).get("candle_rule", "compare")
    if r not in ("compare", "ratio"):
        raise ValueError(f"candle_rule {r!r} — compare / ratio पैकी")
    return r == "ratio"


def is_doji(o, h, lo, c, s=None):
    """Doji: method — the body is smaller than each of its wicks (no ratio); legacy — body / range < `doji_body_max`."""
    if _ratio_rules(s):
        return abs(c - o) / max(h - lo, 1e-9) < float((s or S3.DEFAULTS)["doji_body_max"])
    return abs(c - o) < min(h - max(o, c), min(o, c) - lo)


def candle_read(A, t, s=None, ctx=None):
    """कोण जिंकला + ताकद. रिटर्न dict. Method §3 "big" = larger than the other candles of the same visit or leg: body / range above the
    average of the candles ctx … t − 1 (ctx = the visit's or leg's first bar; none ⇒ None — no context, no reading). Legacy
    (`candle_rule = ratio`): the average of the last `candle_avg_n` (§5.2)."""
    s = s or S3.DEFAULTS
    o, h, l, c = (float(A[k][t]) for k in ("open", "high", "low", "close"))
    rng = max(h - l, 1e-9)
    body = abs(c - o)
    if _ratio_rules(s):
        lo_i = max(0, t - int(s["candle_avg_n"]))
    else:
        lo_i = None if ctx is None else max(0, int(ctx))
    bodies = np.abs(A["close"][lo_i:t] - A["open"][lo_i:t]) if lo_i is not None else np.array([])
    ranges = A["high"][lo_i:t] - A["low"][lo_i:t] if lo_i is not None else np.array([])
    pos = (c - l) / rng
    big_b = (bool(len(bodies)) and body > float(np.mean(bodies))) if lo_i is not None else None
    big_r = (bool(len(ranges)) and rng > float(np.mean(ranges))) if lo_i is not None else None
    return {"winner": "buyers" if c > o else ("sellers" if c < o else "none"), "body_pct": body / rng, "close_pos": pos,
            "upper_wick": (h - max(o, c)) / rng, "lower_wick": (min(o, c) - l) / rng,
            "big_body": big_b, "big_range": big_r, "doji": is_doji(o, h, l, c, s)}


# ------------------------------------------------------------------------------------------------ ④ power shift
def _mean(x):
    return float(np.mean(x)) if len(x) else None


def _vol(A):
    v = A.get("volume") if hasattr(A, "get") else None
    if v is None:
        return None
    v = np.asarray(v, dtype=float)
    return v if np.isfinite(v).any() and np.nanmax(v) > 0 else None


def slot_rel_volume(ts, vol, sessions=20, min_sessions=10, exclude_days=None):
    """Abhi (Z-1 volume): per-bar volume ÷ the median volume of the SAME time-of-day slot over the previous `sessions` sessions that have
    volume in that slot (the 09:15 and closing bars are always heavy). Fewer than `min_sessions` such sessions ⇒ NaN (NA). Only earlier
    sessions are used (no look-ahead). exclude_days = sessions never used in a baseline (FUT rollover days, as legs2.volume.rvol).
    Returns (rel array, history-count array). vol None ⇒ (None, None)."""
    if vol is None:
        return None, None
    t = pd.to_datetime(pd.Series(ts)).reset_index(drop=True)
    v = np.asarray(vol, float)
    day = t.dt.normalize()
    slot = (t - day).to_numpy()
    days = day.to_numpy()
    rel = np.full(len(v), np.nan)
    cnt = np.zeros(len(v), int)
    hist = {}                                                              # slot ⇒ [(day, vol)] of earlier sessions (in order)
    skip = {pd.Timestamp(x).normalize() for x in (exclude_days or ())}
    order = np.argsort(t.to_numpy(), kind="stable")
    cur_day, pending = None, []
    for i in order:
        if days[i] != cur_day:                                             # a new session: the previous one becomes history
            for j in ([] if cur_day is not None and pd.Timestamp(cur_day) in skip else pending):
                if np.isfinite(v[j]) and v[j] > 0:
                    hist.setdefault(slot[j], []).append(v[j])
            pending, cur_day = [], days[i]
        pending.append(i)
        h = hist.get(slot[i], [])[-int(sessions):]
        cnt[i] = len(h)
        if len(h) >= int(min_sessions) and np.isfinite(v[i]) and v[i] > 0:
            med = float(np.median(h))
            rel[i] = v[i] / med if med > 0 else np.nan
    return rel, cnt


def contraction(A, t, d, k, s, lvl=None):
    """④ (a) Abhi (level bots spec): विरुद्ध बाजू area मध्ये दमली ⇒ candles लहान. Relative: area मधल्या (lvl नसेल ⇒ pullback चा शेवटचा
    तिसरा भाग) pullback candles चा सरासरी range < pullback च्या आधीच्या candles चा **आणि** impulse candles चा सरासरी range. नेमके 3 नाहीत."""
    k0 = k["k_open_bar"] if k and k.get("k_open_bar") is not None else max(0, t - int(s["power_fallback_bars"]))
    idx = [i for i in range(k0, t + 1) if (A["close"][i] - A["open"][i]) * d < 0]
    if lvl is not None:
        inside = [i for i in idx if A["low"][i] <= lvl["hi"] and A["high"][i] >= lvl["lo"]]
    else:
        inside = idx[-max(1, len(idx) // 3):] if idx else []
    earlier = [i for i in idx if inside and i < inside[0]]
    if k and k.get("origin_bar") is not None and k.get("i_end_bar") is not None:
        imp = [i for i in range(int(k["origin_bar"]), int(k["i_end_bar"]) + 1) if (A["close"][i] - A["open"][i]) * d > 0]
    else:
        imp = [i for i in range(max(0, k0 - int(s["power_fallback_bars"])), k0) if (A["close"][i] - A["open"][i]) * d > 0]
    rng = lambda ii: _mean([A["high"][i] - A["low"][i] for i in ii])     # noqa: E731
    a_in, a_er, a_im = rng(inside), rng(earlier), rng(imp)
    return bool(a_in is not None and a_er is not None and a_im is not None and a_in < a_er and a_in < a_im)


def power_shift(A, t, d, k, s, lvl=None):
    """(a) विरुद्ध candles लहान होत (power_a_rule: relative = `contraction`; strict3 = जुना शेवटचे 3 सलग लहान); (b) शेवटच्या 3 bodies overlap ≥
    power_overlap; (c) शेवटचा counter push नवं टोक नाही किंवा sweep करून परत; (d) trend-दिशेचे wicks / rejection. ≥ power_shift_min ⇒ ✔.
    (e) handover-volume (a2 zone study, volume असेल तर; नाहीतर NA) — पूरक, मोजणीत नाही."""
    items = {}
    k0 = k["k_open_bar"] if k and k.get("k_open_bar") is not None else max(0, t - int(s["power_fallback_bars"]))
    if s.get("power_a_rule", "relative") == "strict3":
        idx = [i for i in range(k0, t + 1) if (A["close"][i] - A["open"][i]) * d < 0]
        r = [A["high"][i] - A["low"][i] for i in idx[-3:]]
        items["a_shrinking"] = len(r) == 3 and r[0] > r[1] > r[2]
    else:
        items["a_shrinking"] = contraction(A, t, d, k, s, lvl)
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
    zs = zone_study(A, k0, t, d, s) if _vol(A) is not None else None
    items["e_handover_volume"] = None if zs is None or zs.get("handover") is None else bool(zs["handover"] and zs.get("vol_ok"))
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


# ------------------------------------------------------------------------------------------------ a2 zone study (level bots)
def _cmp(first, second):
    """+1 दुसरा अर्धा मोठा, -1 लहान, None (एखादा अर्धा रिकामा / NA)."""
    a, b = _mean([x for x in first if x is not None and np.isfinite(x)]), _mean([x for x in second if x is not None and np.isfinite(x)])
    if a is None or b is None:
        return None
    return 1 if b > a else (-1 if b < a else 0)


def _majority(req, others):
    """req (आवश्यक) खरं आणि उपलब्ध इतर उप-तपासण्यांपैकी किमान अर्ध्या खऱ्या."""
    if req is None:
        return None
    av = [x for x in others if x is not None]
    return bool(req and (not av or sum(1 for x in av if x) * 2 >= len(av)))


def zone_study(A, a, t, d, s, mr=None):
    """Abhi a2: ARMED (a) पासून t पर्यंतच्या बंद candles — trend-बाजूच्या (d दिशेचा रंग) आणि उलट-बाजूच्या candles ची पहिल्या / दुसऱ्या अर्ध्यात
    तुलना (सगळं सापेक्ष; volume असेल तर). handover = trend-बाजू मोठी होत (body ↑ आवश्यक; range ↑, close टोकाजवळ ↑, volume ↑) आणि उलट-बाजू दमत
    (body ↓ आवश्यक; उलट wick ↑, close टोकापासून दूर ↑, volume ↓). absorption = उलट-बाजू मजबूत होत (body ↑, range ↑, volume असेल तर ↑).
    Method §3 (default `slow_form_rule = method`): handover = trend-side bodies grow AND opposite-side bodies shrink AND volume tilts to the
    trend side (later part: trend-side volume above the opposite side's; NA ⇒ not read). `absorption_rule = method`: the opposite side
    keeps coming in the later part, in candles smaller than the trend side's, the trade side is not growing, and no later close goes
    beyond the earlier part's closes on the trade side (sideways base) — so absorption and the slow handover exclude each other.
    The legacy majority / strengthening reads above stay as what-if switches.
    Abhi Z-1p (a): उलट-बाजू zone मधून गायब (पहिल्या अर्ध्यात counter candle होती, दुसऱ्या अर्ध्यात एकही नाही) ⇒ दमली (दमण्याचं टोक) ⇒
    counter_weakening = True, `counter_gone` = True; handover = फक्त trend-बाजू वाढतेय का.
    Pattern (पुरावा): area मधल्या swings वरून wedge / channel-flag / double-triple. एकाच function मध्ये दोन्ही दिशा (d = ±1)."""
    s = s or S3.DEFAULTS
    w = list(range(max(0, int(a)), int(t) + 1))
    vol = _vol(A)
    out = {"handover": None, "absorption": None, "trend_growing": None, "counter_weakening": None, "counter_gone": False,
           "vol_ok": vol is not None, "vol_tilt": None, "pattern": None, "line": ""}
    if len(w) < 2:                                                         # logic, not a threshold: a comparison needs an earlier and a later part
        out["pattern"] = zone_pattern(A, a, t, d, s, mr)
        return out
    m = len(w) // 2
    halves = (w[:m], w[m:])

    def feats(ii, side):
        o_, h_, l_, c_ = A["open"], A["high"], A["low"], A["close"]
        sel = [i for i in ii if (c_[i] - o_[i]) * d * side > 0]
        rng = [max(h_[i] - l_[i], 1e-9) for i in sel]
        body = [abs(c_[i] - o_[i]) for i in sel]
        loc = [((c_[i] - l_[i]) if d > 0 else (h_[i] - c_[i])) / r for i, r in zip(sel, rng)]   # trade-दिशेच्या टोकाकडे close
        opp = [((min(o_[i], c_[i]) - l_[i]) if d > 0 else (h_[i] - max(o_[i], c_[i]))) / r for i, r in zip(sel, rng)]
        v = [float(vol[i]) for i in sel] if vol is not None else []
        return {"body": body, "range": rng, "loc": loc, "opp": opp, "vol": v}
    T = [feats(x, 1) for x in halves]
    C = [feats(x, -1) for x in halves]
    tb, tr, tl = _cmp(T[0]["body"], T[1]["body"]), _cmp(T[0]["range"], T[1]["range"]), _cmp(T[0]["loc"], T[1]["loc"])
    tv = _cmp(T[0]["vol"], T[1]["vol"]) if vol is not None else None
    cb, cr, co = _cmp(C[0]["body"], C[1]["body"]), _cmp(C[0]["range"], C[1]["range"]), _cmp(C[0]["opp"], C[1]["opp"])
    cl = _cmp(C[0]["loc"], C[1]["loc"])
    cv = _cmp(C[0]["vol"], C[1]["vol"]) if vol is not None else None
    slow = s.get("slow_form_rule", "method")
    if slow not in ("method", "majority"):
        raise ValueError(f"slow_form_rule {slow!r} — method / majority पैकी")
    if slow == "majority":                                                 # legacy what-if (#329): body required + at least half the others
        out["trend_growing"] = _majority(None if tb is None else tb > 0, [None if x is None else x > 0 for x in (tr, tl, tv)])
        out["counter_weakening"] = _majority(None if cb is None else cb < 0, [None if co is None else co > 0, None if cl is None else cl > 0,
                                                                              None if cv is None else cv < 0])
    else:                                                                  # method §3 slow form: trend-side candles grow, the others shrink
        out["trend_growing"] = None if tb is None else tb > 0
        out["counter_weakening"] = None if cb is None else cb < 0
    if C[0]["body"] and not C[1]["body"]:                                  # Abhi Z-1p (a): counter side gone from the zone ⇒ exhausted
        out["counter_weakening"] = out["counter_gone"] = True
    # method §3: "volume tilts to the trend side" — in the later part the trend side's candles carry more volume than the opposite side's
    # (the opposite side gone ⇒ tilted). Volume NA ⇒ None: the candles are read alone and the commitment's volume check reports the gap.
    tilt = None
    tv1 = [x for x in T[1]["vol"] if np.isfinite(x) and x > 0]             # bars with volume only (FUT gaps never count as zero)
    cv1 = [x for x in C[1]["vol"] if np.isfinite(x) and x > 0]
    if vol is not None and tv1:
        tilt = True if not C[1]["body"] else (None if not cv1 else _mean(tv1) > _mean(cv1))
    out["vol_tilt"] = tilt
    out["handover"] = bool(out["trend_growing"] and out["counter_weakening"] and (slow == "majority" or tilt is not False))
    ab = s.get("absorption_rule", "method")
    if ab not in ("method", "strengthening"):
        raise ValueError(f"absorption_rule {ab!r} — method / strengthening पैकी")
    if ab == "strengthening":                                              # legacy what-if: counter side body ↑, range ↑, volume ↑
        out["absorption"] = bool(cb is not None and cb > 0 and cr is not None and cr > 0 and (cv is None or cv > 0))
    else:                                                                  # method §3 Absorption (the sideways base)
        C_ = A["close"]
        tb_all = T[0]["body"] + T[1]["body"]
        keeps = bool(C[1]["body"])                                         # the opposite side keeps coming in the later part
        small = bool(tb_all) and keeps and max(C[1]["body"]) < max(tb_all)  # …in candles smaller than the trend side's
        e0, e1 = halves                                                    # …and price does not move away: no later close beyond the
        stuck = (min(C_[i] for i in e1) >= min(C_[i] for i in e0)) if d < 0 else (max(C_[i] for i in e1) <= max(C_[i] for i in e0))
        out["absorption"] = bool(keeps and small and stuck and not out["trend_growing"])   # earlier part's closes on the trade side; the
        # trade side NOT growing — a growing trade side with a shrinking opposite side is the handover, never absorption (they exclude)
    out["vol_trend_rising"] = None if tv is None else tv > 0
    out["pattern"] = zone_pattern(A, a, t, d, s, mr)
    tw, cw = ("buying", "selling") if d > 0 else ("selling", "buying")
    parts = []
    if out["trend_growing"]:
        parts.append(f"{tw} candles growing")
    if out["counter_gone"]:
        parts.append(f"{cw} candles gone from the zone (exhausted)")
    elif out["counter_weakening"]:
        parts.append(f"{cw} candles weakening")
    if out["absorption"]:
        parts.append(f"{cw} candles strengthening (absorption)" if ab == "strengthening" else
                     f"{cw} keeps coming in small candles and price does not move away (absorption)")
    if out["vol_tilt"] is not None and out["trend_growing"]:
        parts.append(f"volume {'tilts to' if out['vol_tilt'] else 'does not tilt to'} the {tw} side")
    if out["vol_trend_rising"]:
        parts.append(f"volume rising on {tw} candles")
    out["line"] = " · ".join(([out["pattern"]] if out["pattern"] else []) + parts)
    return out


def sharp_reversal(A, i, d, lo, hi, s=None, a0=None):
    """Abhi Z-1z: inside the zone, a push that is REJECTED and immediately SWALLOWED by a dominant opposite candle is a handover in
    itself (method §3 Handover, fast form). Candle 1 = bar i − 1, candle 2 = bar i (bars ≤ i). Comparisons only — no numbers:
      • candle 1 pushes into or through the zone (supply: its high reaches the zone; demand: its low) and is rejected — its wick on the
        push side is longer than its body and it closes back, not beyond the zone (a wick through the zone and back = a sweep, K5);
      • candle 2 goes the other way (the trade side), is dominant — its body larger than every other candle of the visit (a0 … i − 1) —
        and closes beyond the push candle's body (`fast_form_rule = push_body`; "engulf" = the legacy what-if: body covers body and
        close beyond candle 1's trade-side extreme).
    Volume is the commitment's own comparison (c0), not part of this read. a0 = the visit's (or post-break window's) first bar; candle 1
    must be inside it. Returns {found, why (every missing part), parts {c1_rejected, c2_dominant, c2_closes_beyond_push_body — or the
    legacy c2_engulfs_body, c2_closes_beyond_c1}, c1, c2}."""
    i = int(i)
    a0 = int(a0) if a0 is not None else i - 1
    out = {"found": False, "why": None, "c1": i - 1, "c2": i, "parts": {}}
    if i - 1 < max(a0, 0):
        out["why"] = "candle 1 is not inside the visit"
        return out
    o1, h1, l1, c1 = _ohlc(A, i - 1)
    o2, h2, l2, c2 = _ohlc(A, i)
    b1, b2 = abs(c1 - o1), abs(c2 - o2)
    push_wick = (h1 - max(o1, c1)) if d == DOWN else (min(o1, c1) - l1)
    pushed = (h1 >= lo) if d == DOWN else (l1 <= hi)
    back = (c1 <= hi) if d == DOWN else (c1 >= lo)
    others = [abs(A["close"][j] - A["open"][j]) for j in range(a0, i)]
    far1 = l1 if d == DOWN else h1                                         # candle 1's trade-side extreme
    body1 = min(o1, c1) if d == DOWN else max(o1, c1)                      # candle 1's body edge on the trade side
    P = {"c1_rejected": bool(pushed and back and push_wick > b1),
         "c2_dominant": bool((c2 - o2) * d > 0 and b2 > max(others))}
    rule = (s or S3.DEFAULTS).get("fast_form_rule", "push_body")
    if rule not in ("push_body", "engulf"):
        raise ValueError(f"fast_form_rule {rule!r} — push_body / engulf पैकी")
    if rule == "push_body":                                                # method §3: closes beyond the push candle's body
        P["c2_closes_beyond_push_body"] = bool((c2 < body1) if d == DOWN else (c2 > body1))
    else:                                                                  # legacy what-if (#329): body covers body + close beyond extreme
        P["c2_engulfs_body"] = bool(max(o2, c2) >= max(o1, c1) and min(o2, c2) <= min(o1, c1))
        P["c2_closes_beyond_c1"] = bool((c2 < far1) if d == DOWN else (c2 > far1))
    out["parts"] = P
    words = {"c1_rejected": "candle 1: no push into the zone rejected by a wick back",
             "c2_dominant": "candle 2: not a dominant trade-side candle (a candle of this visit is as large or larger)",
             "c2_closes_beyond_push_body": "candle 2 does not close beyond the push candle's body",
             "c2_engulfs_body": "candle 2's body does not cover candle 1's body",
             "c2_closes_beyond_c1": f"candle 2 does not close beyond candle 1's {'low' if d == DOWN else 'high'}"}
    miss = [words[k] for k, v in P.items() if v is not True]
    if miss:
        out["why"] = "; ".join(miss)
        return out
    out.update(found=True, why="push rejected, then a dominant opposite candle closed beyond its body (fast form)")
    return out


def handover_episode(A, arm, t, d, s, broken=None, mr=None, sharp=None):
    """Abhi Z-1q (a): the handover per armed zone episode (arm = arrival in the zone), as known at the decision bar t (bars ≤ t only).
    Every in-zone window arm … e (e < t; any window with an earlier and a later part — Abhi: never a minimum count) is read with
    `zone_study` in time order: the first window with a
    handover ⇒ SEEN (bar e); once seen it HOLDS until the commitment candle — cancelled only by a later absorption (a later window with
    the counter side strengthening again) or by the zone breaking (`broken(u)` True at a bar u after it was seen, u ≤ t — the caller's
    K4 state). A cancelled handover may be seen again by a later window — after a zone break only from bars after the break (windows
    start at the bar after it, while the zone is not broken). Never re-required on the commitment bar's own window.
    The caller passes arm = the start of the current VISIT (Abhi Z-1v), so a handover never carries from an earlier visit.
    sharp = callable(i, a0) ⇒ `sharp_reversal` facts for candles i − 1, i (Abhi Z-1z (c)): a found two-candle sharp reversal is a handover
    too (form "sharp_reversal"), read on every pair inside the visit including the commitment bar t itself (candle 2 may be the
    commitment); the slower read (form "study": one side growing while the other weakens) covers slower visits.
    Returns {present, seen_at, form, cancelled ("absorption" / "zone broken" / None), cancelled_at, window_start (after a break: the bar
    after it — the absorption gate uses the same window), sharp (the last pair read: facts), events [(bar, what)]}."""
    s = s or S3.DEFAULTS
    arm, t = int(arm), int(t)
    st = {"present": False, "seen_at": None, "form": None, "cancelled": None, "cancelled_at": None, "sharp": None, "events": []}
    a0 = arm                                                               # window start (moves past a zone break)

    def cancel(u, why):
        st.update(present=False, form=None, cancelled=why, cancelled_at=int(u))
        st["events"].append((int(u), "cancelled: " + why))

    def seen(e, form):
        st.update(present=True, seen_at=int(e), form=form, cancelled=None, cancelled_at=None)
        st["events"].append((int(e), "handover seen" + (" (two-candle sharp reversal)" if form == "sharp_reversal" else "")))

    def read_sharp(e):
        if sharp is None or st["present"] or e - 1 < a0:
            return False
        sr = sharp(e, a0)
        st["sharp"] = sr
        if sr.get("found"):
            seen(e, "sharp_reversal")
            return True
        return False
    for e in range(arm, t):
        if broken is not None and broken(e):
            if st["present"]:
                cancel(e, "zone broken")
            a0 = e + 1                                                     # a broken zone's earlier read never counts again
            continue
        if read_sharp(e):
            continue
        if e - a0 + 1 < 2:                                                 # one candle: nothing to compare yet (logic, not a count)
            continue
        zs = zone_study(A, a0, e, d, s, mr)
        if st["present"] and zs.get("absorption"):
            cancel(e, "absorption")
        elif not st["present"] and zs.get("handover"):
            seen(e, "study")
    if broken is not None and broken(t):
        if st["present"]:
            cancel(t, "zone broken")
        a0 = t + 1
    else:
        read_sharp(t)                                                      # Z-1z: candle 2 may be the commitment bar itself
    st["window_start"] = int(a0)
    return st


def zone_pattern(A, a, t, d, s, mr=None):
    """a2 patterns (पुरावा, कधीच आवश्यक नाही): area मधले swings (a … t − 1, साधे 1-bar pivots). UP (demand): falling wedge / falling channel–bull
    flag / double–triple bottom; DOWN (supply): आरसा — rising wedge / rising channel–bear flag / double–triple top. नसेल ⇒ None."""
    s = s or S3.DEFAULTS
    H, L = A["high"], A["low"]
    ii = list(range(max(1, int(a)), int(t) - 1))                           # pivot ला दोन्ही शेजारी हवेत (t − 1 पर्यंत, commitment वगळून)
    hs = [(i, float(H[i])) for i in ii if H[i] > H[i - 1] and H[i] >= H[i + 1]]
    ls = [(i, float(L[i])) for i in ii if L[i] < L[i - 1] and L[i] <= L[i + 1]]
    tol = 0.0
    if _ratio_rules(s):                                                    # legacy only: the MR tolerance
        if mr is None or not np.isfinite(mr):
            rr = [H[i] - L[i] for i in range(max(0, int(a)), int(t) + 1)]
            mr = float(np.median(rr)) if rr else 0.0
        tol = float(s.get("pattern_eq_mr", 0.5)) * mr
    if len(hs) >= 2 and len(ls) >= 2:
        sh = (hs[-1][1] - hs[0][1]) / max(hs[-1][0] - hs[0][0], 1)
        sl = (ls[-1][1] - ls[0][1]) / max(ls[-1][0] - ls[0][0], 1)
        if d > 0 and sh < 0 and sl < 0:
            return "falling wedge" if sh < sl else "falling channel / bull flag"
        if d < 0 and sh > 0 and sl > 0:
            return "rising wedge" if sl > sh else "rising channel / bear flag"
    ext = ls if d > 0 else hs
    if len(ext) >= 2 and not _ratio_rules(s):                             # method §3 equal, in time order: each later extreme reaches the
        (ri, rp), n = ext[0], 1                                            # reference swing candle's own wick-to-body band and does not go
        for i, p in ext[1:]:                                               # beyond it; one that goes beyond becomes the new reference
            edge = min(A["open"][ri], A["close"][ri]) if d > 0 else max(A["open"][ri], A["close"][ri])
            if (p < rp) if d > 0 else (p > rp):
                (ri, rp), n = (i, p), 1
            elif (p <= edge) if d > 0 else (p >= edge):
                n += 1
        if n >= 2:
            return f"{'triple' if n >= 3 else 'double'} {'bottom' if d > 0 else 'top'}"
        return None
    if len(ext) >= 2 and tol > 0:
        best = min(p for _, p in ext) if d > 0 else max(p for _, p in ext)
        n = sum(1 for _, p in ext if abs(p - best) <= tol)
        if n >= 2:
            return f"{'triple' if n >= 3 else 'double'} {'bottom' if d > 0 else 'top'}"
    return None


# ------------------------------------------------------------------------------------------------ ⑥ commitment
def _ohlc(A, i):
    return float(A["open"][i]), float(A["high"][i]), float(A["low"][i]), float(A["close"][i])


def _same_window(tss, t, i, s):
    """Method P2 (default): always True — no reading step splits on a day or a session. Legacy (`session_windows = True`, what-if):
    merged / संदर्भ candle i हा t च्या दिवसाचा आणि पुरावा-खिडकीतला (`evidence_start`, default सत्राची सुरुवात 09:15)? (tss नसेल ⇒ हो).
    Abhi (12 Oct): opening candle चा sweep / wick / volume = पुरावा (2-candle form चा पहिला भाग / "मागची" candle) — entry मात्र फक्त
    `entry_start` … `entry_end` मधल्या commitment candle वर (`commitment` ची वेळ-खिडकी तशीच)."""
    if tss is None or not bool(s.get("session_windows", False)):          # method P2: one continuous chart — a gap is the next candle
        return True
    ti, tt = pd.Timestamp(tss[i]), pd.Timestamp(tss[t])
    return ti.normalize() == tt.normalize() and ti.strftime("%H:%M") >= s.get("evidence_start", s["entry_start"])


def _one_candle_form(A, t, d):
    """The 1-candle forms by comparison: pin (rejection wick longer than the rest of the candle) or strong close (body larger than both
    wicks together); None otherwise."""
    o, h, lo, c = _ohlc(A, t)
    rej = (min(o, c) - lo) if d == UP else (h - max(o, c))
    opp = (h - max(o, c)) if d == UP else (min(o, c) - lo)
    if rej > abs(c - o) + opp:
        return "pin"
    if (c - o) * d > 0 and (c - o) * d > rej + opp:
        return "strong_close"
    return None


def _reversal_form_compare(A, t, d, s, tss=None):
    """Method §3 commitment forms by comparing body and wicks — never ratios. Order as the legacy read: engulf, star, inside_break,
    doji_confirm, tweezer, pin, strong_close (1 candle), strong_close_2 (2 merged). d = trade direction."""
    if t < 1:
        return None
    o, h, lo, c = _ohlc(A, t)
    po, ph, pl, pc = _ohlc(A, t - 1)
    body = (c - o) * d
    pbody = (pc - po) * d
    two = _same_window(tss, t, t - 1, s)
    rej = (min(o, c) - lo) if d == UP else (h - max(o, c))                 # the rejection wick (against the trade direction)
    opp = (h - max(o, c)) if d == UP else (min(o, c) - lo)                 # the wick on the trade side
    if two and body > 0 and pbody < 0 and max(o, c) >= max(po, pc) and min(o, c) <= min(po, pc):
        return "engulf", 1
    if two and t >= 2 and body > 0 and _same_window(tss, t, t - 2, s):
        qo, qh, ql, qc = _ohlc(A, t - 2)
        qbody = (qc - qo) * d
        if qbody < 0 and -qbody > (qh - ql) + qbody and abs(pc - po) < -qbody and abs(pc - po) < body and (c - qc) * d > 0:
            return "star", 2                                               # a strong first candle, a small middle one, back into the first
        inside = ph <= qh and pl >= ql
        harami = max(po, pc) <= max(qo, qc) and min(po, pc) >= min(qo, qc)
        if (inside or harami) and (c - (ph if d == UP else pl)) * d > 0:
            return "inside_break", 2
    if two and body > 0 and is_doji(po, ph, pl, pc, s) and (c - (ph if d == UP else pl)) * d > 0:
        return "doji_confirm", 2
    if two and body > 0 and pbody <= 0 and \
            ((pl <= lo <= min(po, pc)) if d == UP else (max(po, pc) <= h <= ph)):
        return "tweezer", 2                                                # equal extreme: reaches the earlier wick, not beyond it
    if rej > abs(c - o) + opp:
        return "pin", 1                                                    # the rejection wick longer than the rest of the candle
    if body > 0 and body > rej + opp:
        return "strong_close", 1                                           # the body larger than both wicks together
    if two:
        mo, mh, ml = po, max(h, ph), min(lo, pl)
        mb = (c - mo) * d
        mrej = (min(mo, c) - ml) if d == UP else (mh - max(mo, c))
        mopp = (mh - max(mo, c)) if d == UP else (min(mo, c) - ml)
        if mb > 0 and mb > mrej + mopp:
            return "strong_close_2", 2
    return None


def reversal_form(A, t, d, s, tss=None):
    """Q16: level वरची reversal candle ओळख (तर्काने, checklist नाही). रिटर्न (form, merged) किंवा None. क्रम: engulf, star, inside_break,
    doji_confirm, tweezer, pin, strong_close (1 candle), strong_close_2 (2 merged). d = trade दिशा (UP ⇒ खाली नकार, वर close)."""
    if not _ratio_rules(s):                                                # method §3 (default): comparisons of body and wicks
        return _reversal_form_compare(A, t, d, s, tss)
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


def entry_open(s):
    """commitment (entry) candle ची सर्वात लवकरची सुरुवात: `entry_first_bar` (Abhi 13 Oct, default True) ⇒ सत्राची पहिली candle
    (`evidence_start`, 09:15 — निर्णय तिच्या close ला, bar_end 09:30); False / setting नाही ⇒ जुनं `entry_start` (09:30)."""
    if s.get("entry_first_bar", False):
        return min(s.get("evidence_start", s["entry_start"]), s["entry_start"])
    return s["entry_start"]


def commitment(A, t, d, lvl, s, tss=None, win=None, approach=None, exclude=()):
    """⑥ Q16 (Abhi): commitment = level वरची price-reversal candle (≤ 2 merged); कोणताही ओळखलेला reversal form चालतो.
    किमान सामायिक अट: close मागच्या candle च्या **close** पलीकडे trade-दिशेने (`commit_beyond` = close, default; "extreme" = what-if) आणि
    (merged 2-candle form ⇒ "मागची" = pattern आधीची candle t − 2, त्याच दिवसाची असेल तर; Q30)
    close level च्या trade-बाजूला / level मध्ये. Grade: मागच्या candle च्या extreme पलीकडे close किंवा engulf ⇒ A; बाकी (wick नकार + close
    पलीकडे) ⇒ B. वाट: चालू candle pullback-दिशेची / doji / inside bar ⇒ पुढच्या candle ची वाट. वेळ-खिडकी settings.
    Volume (method §3 Commitment, `commit_volume_rule = approach_and_opposite`): larger than every candle of the approach leg (`approach` =
    its bar indices, given by the caller) and every opposite-side candle of the visit (win … t − 1); the rejected push (`exclude`) and the
    commitment itself (both candles when merged) are not compared. Nothing to compare ⇒ no commitment (Abhi, L3-c). Volume NA ⇒ vol_na (the caller's
    data-problem rule). "opposite" = the legacy #329 read (visit's opposite side only, none ⇒ grade cap B)."""
    if s["commit_beyond"] not in ("extreme", "close"):
        raise ValueError(f"commit_beyond {s['commit_beyond']!r} — extreme / close पैकी")
    if tss is not None and bool(s.get("session_windows", False)):          # legacy only — method P2: the entry schedule is operational
        hm = pd.Timestamp(tss[t]).strftime("%H:%M")                        # (V22 applies it after the reading, `engine.entry_window`)
        if not (entry_open(s) <= hm < s["entry_end"]):                  # 15:15 चा bar बाजार बंदला close ⇒ entry नाही (v2.1 सारखं)
            return False, "entry वेळ-खिडकीबाहेर", {}
    if t < 1:
        return False, "commitment candle नाही", {}
    o, h, lo, c = _ohlc(A, t)
    po, ph, pl, pc = _ohlc(A, t - 1)
    rng = max(h - lo, 1e-9)
    beyond_close = (c - pc) * d > 0
    beyond_ext = (c - (ph if d == UP else pl)) * d > 0
    side = (c >= lvl["lo"]) if d == UP else (c <= lvl["hi"])
    if is_doji(o, h, lo, c, s):
        return False, "doji level वर — पुढच्या candle ची वाट", {"wait": "doji"}
    if h <= ph and lo >= pl:
        return False, "inside bar — पुढच्या candle ची वाट", {"wait": "inside"}
    if (c - o) * d < 0 and not beyond_close:
        return False, "candle अजून pullback-दिशेची — वाट", {"wait": "pullback"}
    fm = reversal_form(A, t, d, s, tss)
    one = (beyond_close, beyond_ext)                                       # vs t − 1 (a 1-candle form)
    if fm is not None and fm[1] == 2 and t >= 2 and _same_window(tss, t, t - 2, s):
        r = t - 2                                                          # merged (≤ 2) = एक candle ⇒ "मागची" = pattern आधीची (Q30)
        qo, qh, ql, qc = _ohlc(A, r)
        beyond_close = (c - qc) * d > 0
        beyond_ext = (c - (qh if d == UP else ql)) * d > 0
        need2 = beyond_close if s["commit_beyond"] == "close" else beyond_ext
        f1 = _one_candle_form(A, t, d) if not _ratio_rules(s) else None
        if not need2 and f1 is not None:                                   # the merged read fails but the candle is a pin / strong close on
            fm, (beyond_close, beyond_ext) = (f1, 1), one                  # its own ⇒ read it as that 1-candle form (never lost to a tweezer)
    need = beyond_close if s["commit_beyond"] == "close" else beyond_ext
    if not (need and side):
        return False, "commitment candle नाही" + ("" if side else " (close level पलीकडे चुकीच्या बाजूला)"), {}
    if fm is None:
        return False, "commitment candle नाही (reversal form नाही)", {}
    form, merged = fm
    grade = "A" if (beyond_ext or form == "engulf") else "B"
    cm = {"form": form, "merged": merged, "grade": grade, "beyond_extreme": bool(beyond_ext), "engulf": form == "engulf",
          "body_pct": round(abs(c - o) / rng, 2), "big_body": candle_read(A, t, s, win)["big_body"], "big_range": candle_read(A, t, s, win)["big_range"]}
    if win is not None:                                                    # c0 (Abhi): dominant in this visit + volume, by comparison only
        ww = list(range(max(0, int(win)), t))                              # the visit's earlier candles (the commitment compared with them)
        body = max(abs(c - o), abs(c - po) if merged == 2 else 0.0)
        bodies = [abs(A["close"][i] - A["open"][i]) for i in ww]
        if not bodies and bool(s.get("c0_dominance", True)):
            return False, "commitment candle: nothing to compare it with in this visit yet", {"wait": "not_dominant", **cm}
        cm["body_mult"] = round(body / max(bodies), 2) if bodies and max(bodies) > 0 else None   # fact only (the rule is the comparison)
        if bool(s.get("c0_dominance", True)) and not body > max(bodies):  # Abhi: dominant = larger than every other candle in the visit
            return False, "commitment candle not dominant (a candle in this visit is as large or larger)", {"wait": "not_dominant", **cm}
        V = _vol(A)
        vrule = s.get("commit_volume_rule", "approach_and_opposite")
        if vrule not in ("approach_and_opposite", "opposite"):
            raise ValueError(f"commit_volume_rule {vrule!r} — approach_and_opposite / opposite पैकी")
        if vrule == "approach_and_opposite":                               # method §3 Commitment: larger than the approach leg's candles and
            skip = {int(x) for x in exclude} | {t} | ({t - 1} if merged == 2 else set())   # the visit's opposite side; push + itself out
            opp = [i for i in ww if (A["close"][i] - A["open"][i]) * d < 0 and i not in skip]
            appr = {int(i) for i in (approach or ()) if int(i) < t and int(i) not in skip}
            refs = sorted(appr | set(opp))
            ref = [(float(V[i]), i) for i in refs if np.isfinite(V[i]) and V[i] > 0] if V is not None else []
            cm["vol_ref_gaps"] = len(refs) - len(ref)                      # compared bars without FUT volume (reported, never zero)
            if V is None or not (np.isfinite(V[t]) and V[t] > 0) or (refs and not ref):
                cm.update(vol_mult=None, vol_na=True)                      # volume NA ⇒ the caller's data-problem rule (V22: no entry)
                grade = cm["grade"] = "B"
            elif not refs:                                                 # Abhi (L3-c): never an automatic pass — no approach leg known and no
                return False, "commitment volume: nothing to compare it with (no approach leg known, no opposite-side candle)", \
                    {"wait": "no_volume_reference", **cm, "vol_na": False, "vol_mult": None}   # opposite candle ⇒ no commitment
            else:
                top, top_i = max(ref)
                cm.update(vol_mult=round(float(V[t]) / top, 2), vol_na=False, vol_ref_bar=int(top_i),
                          vol_vs="the approach leg and the visit's opposite-side candles" if (appr and opp) else
                          "the approach leg's candles" if appr else "the visit's opposite-side candles")
                if not V[t] > top:
                    return False, f"commitment on low volume (not larger than {cm['vol_vs']})", {"wait": "low_volume", **cm}
            return True, f"commitment {form} ({merged} candle) · grade {grade}", cm
        opp = [i for i in ww if (A["close"][i] - A["open"][i]) * d < 0]     # legacy: the opposite side's candles in the same visit
        ref = [float(V[i]) for i in opp if np.isfinite(V[i]) and V[i] > 0] if V is not None else []
        if V is not None and np.isfinite(V[t]) and V[t] > 0 and (ref or not opp):
            vm = float(V[t]) / max(ref) if ref else None
            cm.update(vol_mult=None if vm is None else round(vm, 2), vol_na=False,
                      vol_vs="opposite-side candles" if ref else "no opposite-side candle in this visit")
            if ref and not V[t] > max(ref):                                # Abhi: clearly larger than the opposite side's candles
                return False, "commitment on low volume (not larger than the opposite-side candles in this visit)", {"wait": "low_volume", **cm}
            if not ref:                                                    # nothing compared (OPEN_QUESTIONS Z-1z-d) ⇒ fail-safe: grade cap B
                grade = cm["grade"] = "B"
        else:
            cm.update(vol_mult=None, vol_na=True)                          # volume NA ⇒ चालतं, पण grade कमाल B
            grade = cm["grade"] = "B"
    return True, f"commitment {form} ({merged} candle) · grade {grade}", cm


# ------------------------------------------------------------------------------------------------ c1 LTF CHoCH + एकच confirmation (a2 + c0 + c1)
C_ABSORB, C_COMMIT, C_NO_HANDOVER = "absorption", "no_commitment", "no_handover"
C_LTF_MISSING, C_LTF_AGAINST, C_LTF_PENDING = "ltf_missing", "ltf_against", "ltf_pending"
REASON = {C_ABSORB: "absorption (the opposite side keeps coming in small candles and price does not move away)", C_COMMIT: "no commitment",
          C_NO_HANDOVER: "no handover yet (trade-side candles not growing while the opposite side shrinks and volume tilts to the trade side)",
          "low_volume": "commitment on low volume", "not_dominant": "commitment candle not dominant",
          "no_volume_reference": "commitment volume: no approach leg known and no opposite-side candle to compare it with",
          C_LTF_MISSING: "LTF data missing", C_LTF_AGAINST: "LTF still trending against",
          C_LTF_PENDING: "waiting for LTF CHoCH (no close beyond the last LTF swing)"}
LTF_OF = {60: 5, 15: 5, 5: 1}                                              # Abhi c1 mapping: 1H area / 15M setup ⇒ 5M; 5M ⇒ 1M; MCX 15M ⇒ 5M


def _px(x):
    """ticket किंमत: 17041 ⇒ "17,041", 1002.5 ⇒ "1,002.5" (शेवटची शून्ये नाहीत)."""
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def _naive(ts):
    ts = pd.to_datetime(ts)
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return ts


_LTF_WARNED = set()


def warn_ltf_missing(where):
    """c1 आवश्यक पण LTF दिलेलं नाही ⇒ प्रत्येक caller साठी एकदाच ठळक इशारा (batch tools शांतपणे 0 entries देऊ नयेत). Entry fail-closed राहते."""
    if where in _LTF_WARNED:
        return
    _LTF_WARNED.add(where)
    import warnings
    msg = (f"{where}: c1 (LTF CHoCH) is required (ltf_choch=True) but no lower-timeframe bars were given — every entry will wait with "
           f"'LTF data missing'. Pass ltf= (5M / 1M bars) or set ltf_choch=False for a what-if.")
    warnings.warn(msg, RuntimeWarning, stacklevel=3)
    print(f"⚠️ {msg}")


def ltf_frame(df, minutes, label=None):
    """c1: lower-timeframe bars (timestamp = bar सुरुवात[, bar_end]) ⇒ arrays (bar_end क्रमाने). None / रिकामे ⇒ None (c1 fail-closed)."""
    if df is None or not len(df):
        return None
    ts = _naive(df["timestamp"]).reset_index(drop=True)
    end = _naive(df["bar_end"]).reset_index(drop=True) if "bar_end" in df.columns else ts + pd.Timedelta(minutes=int(minutes))
    o = np.argsort(end.to_numpy(), kind="stable")
    out = {"start": ts.to_numpy()[o], "end": end.to_numpy()[o], "minutes": int(minutes), "label": label or f"{int(minutes)}M"}
    for k in ("open", "high", "low", "close"):
        out[k] = df[k].to_numpy(float)[o]
    return out


def ltf_choch(L, d, t_ctx, t_start, t_end, lvl=None):
    """c1 (Abhi): lower-timeframe change of character, फक्त CLOSE ने. LTF bars = bar_end ≤ t_end (setup bar चा close ⇒ lookahead नाही);
    study = t_start (area मध्ये arrival) पासून; संदर्भ (pullback चे swings) = t_ctx पासून. Bullish (d = +1): study मधला सर्वात खालचा low
    (LL). LTF ने lower lows थांबवले ⇔ LL नंतर किमान एक बंद candle (तिचा low LL पेक्षा कमी नाही — LL = window चा किमान) **किंवा** LL candle
    ने आधीचा LTF swing low / area ची far edge sweep करून close परत आत. **मग** LL नंतर (sweep असेल तर LL candle पासूनच) एखादी candle LL
    आधीच्या शेवटच्या LTF swing high (lower high) च्या वर CLOSE ⇒ CHoCH; higher low = LL नंतर CHoCH candle पर्यंतचा सर्वात खालचा low
    (समान ⇒ double bottom). V-reversal / stair-step recovery / gap-down चा पहिलाच bar low — सगळे चालतात. Wick वर गेला पण close नाही ⇒
    CHoCH नाही. शेवटचा बंद LTF bar च LL ⇒ "still trending against". Bearish = आरसा (किंमती उलट करून तेच गणित).
    Abhi Z-1r: CHoCH price zone मध्ये आल्यानंतरचाच — lvl दिला ⇒ study = t_start नंतरची पहिली zone ला स्पर्श करणारी LTF candle (arrival)
    पासून; arrival आधीचा CHoCH मोजत नाही (`arrival_at`;
    LL / HH arrival नंतरच्या window मध्ये ⇒ CHoCH candle नेहमी arrival नंतर —
    रचनेनेच, वेगळा flag नाही). स्पर्श करणारी LTF candle नाही ⇒ t_start पासून (arm bar).
    रिटर्न dict: done, code (ltf_missing / ltf_against / ltf_pending), line + किंमती."""
    lab = (L or {}).get("label", "LTF")
    miss = {"done": False, "code": C_LTF_MISSING, "line": f"{lab}: LTF data missing"}
    if L is None or not len(L["end"]):
        return miss
    t_ctx, t_start, t_end = (np.datetime64(pd.Timestamp(x)) for x in (t_ctx, t_start, t_end))
    n_ok = int(np.searchsorted(L["end"], t_end, side="right"))
    ii = np.flatnonzero(L["start"][:n_ok] >= min(t_ctx, t_start))
    w = ii[L["start"][ii] >= t_start]
    if not len(w):
        return miss
    if lvl is not None:                                                    # Abhi Z-1r: from price's arrival in the zone (no earlier CHoCH)
        touch = (L["high"][w] >= float(lvl["lo"])) & (L["low"][w] <= float(lvl["hi"]))
        if touch.any():
            w = w[int(np.argmax(touch)):]
    arrival = pd.Timestamp(L["start"][w[0]])
    sg = 1.0 if d > 0 else -1.0
    H = (L["high"] if d > 0 else -L["low"])[ii]                            # आरसा: bearish ⇒ high ↔ −low
    Lo = (L["low"] if d > 0 else -L["high"])[ii]
    C = sg * L["close"][ii]
    E = L["end"][ii]
    m = len(ii)
    w0 = m - len(w)
    jl = w0 + int(np.argmin(Lo[w0:]))                                      # पहिली घटना (नंतरचा समान low = double bottom)
    lmin = float(Lo[jl])
    ph = [i for i in range(1, m - 1) if H[i] > H[i - 1] and H[i] >= H[i + 1]]
    pl = [i for i in range(1, m - 1) if Lo[i] < Lo[i - 1] and Lo[i] <= Lo[i + 1]]
    lhs = [i for i in ph if i < jl]
    j_lh = lhs[-1] if lhs else max(jl - 1, 0)                              # pivot नसेल (सरळ घसरण / gap) ⇒ LL आधीच्या candle चा high
    lh = float(H[j_lh])
    prior = [i for i in pl if i < jl]
    sweep = bool(prior and Lo[jl] < Lo[prior[-1]] and C[jl] > Lo[prior[-1]])
    if lvl is not None:
        edge = float(lvl["lo"]) if d > 0 else -float(lvl["hi"])
        sweep = sweep or bool(Lo[jl] < edge and C[jl] >= edge)
    jc = next((j for j in range(jl if sweep else jl + 1, m) if C[j] > lh), None)
    seg_end = jc if jc is not None else m - 1
    hl = float(np.min(Lo[jl + 1:seg_end + 1])) if seg_end > jl else None
    back = (lambda x: x) if d > 0 else (lambda x: -x)                     # noqa: E731
    hl_word, lh_word = ("higher low", "LH") if d > 0 else ("lower high", "HL")
    ext_word, beyond = ("low", "above") if d > 0 else ("high", "below")
    trend_word = "lower lows" if d > 0 else "higher highs"
    out = {"done": jc is not None, "low": back(lmin), "lh": back(lh), "sweep": sweep, "hl": None if hl is None else back(hl),
           "low_at": str(pd.Timestamp(E[jl])), "label": lab, "arrival_at": str(arrival)}
    parts = [f"sweep of {ext_word} {_px(out['low'])} closed back inside"] if sweep else []
    if hl is not None:
        parts.append(f"double {'bottom' if d > 0 else 'top'} {_px(out['hl'])}" if hl <= lmin else f"{hl_word} {_px(out['hl'])}")
    first = ", ".join(parts) or f"{ext_word} {_px(out['low'])}"
    if jc is not None:
        hm = pd.Timestamp(E[jc]).strftime("%H:%M")
        out.update(code=None, at=str(pd.Timestamp(E[jc])), close=back(float(C[jc])),
                   line=f"{lab} CHoCH: {first}, close {beyond} {lh_word} {_px(out['lh'])} at {hm}")
        return out
    if jl < m - 1 or sweep:
        wick = any(H[j] > lh for j in range(jl, m))
        out.update(code=C_LTF_PENDING, line=f"{lab}: {first}, no close {beyond} {lh_word} {_px(out['lh'])} yet"
                   + (" (wick only)" if wick else ""))
    else:
        out.update(code=C_LTF_AGAINST, line=f"{lab}: still making {trend_word} "
                   f"({ext_word} {_px(out['low'])} at {pd.Timestamp(E[jl]).strftime('%H:%M')}) — LTF still trending against")
    return out


def confirm(A, arm, t, d, lvl, s, tss=None, mr=None, ltf=None, ltf_times=None, handover=None, approach=None):
    """एकच confirmation (Abhi, LEVEL_BOTS_CONFIRMATION §2 a2 + c0 + c1) — V22 ⑥ आणि level bots (bots_common/level_reaction) दोघेही हेच
    वापरतात; d = ±1 (आरसा). Study window = arm (area मध्ये arrival) … commitment candle t. क्रम:
      a2 — window arm … t − 1 मध्ये उलट-बाजू volume वाढत मजबूत (absorption) ⇒ वाट (commitment पाहतच नाही);
      c0 — commitment (Q16 form), dominant = body larger than every other candle of the visit, volume larger than the opposite side's
           candles of the visit (none in the visit ⇒ nothing to beat, noted) — comparisons only, no multiplier (volume NA ⇒ चालतं, कमाल B);
      c1 — LTF CHoCH by close (`ltf_choch`; ltf = ltf_frame किंवा तो देणारं callable (commitment असेल तरच बोलावतो); ltf_times = (संदर्भ सुरुवात, arrival सुरुवात, setup bar close)), `ltf_choch` setting (default
           True = आवश्यक). LTF नाही ⇒ "LTF data missing" ⇒ वाट (fail-closed, कधीच शांतपणे वगळत नाही).
    प्रत्येक गहाळ भाग ⇒ वाट (code), कायमचा नकार नाही (timeout / disarm caller चे नियम). रिटर्न dict: ok, wait (code | None), why, commit (cm),
    study (zone_study), absorption, study_ran, c0, c1, choch, lines (ticket ओळी).
    handover (Abhi Z-1q, V22): `handover_episode` चा sticky निकाल {present, seen_at, cancelled, …} — दिला ⇒ handover = तो (commitment bar
    च्या window मध्ये पुन्हा दिसायची गरज नाही); नाही ⇒ जुनं (zone_study(arm … t − 1)["handover"]). Abhi Z-1r: handover, c1 आणि c0
    तिन्ही commitment bar ला हवेत; क्रम महत्त्वाचा नाही (wait code फक्त पहिला गहाळ भाग सांगतो)."""
    out = {"ok": False, "wait": None, "why": "", "commit": {}, "study": None, "absorption": False, "study_ran": False, "c0": False,
           "c1": None, "choch": None, "lines": [], "handover": None}
    zp = None
    a_ab = int(handover.get("window_start", arm)) if handover else int(arm)   # the episode's window (restarts after a zone break)
    if t - 1 >= a_ab:
        zp = zone_study(A, a_ab, t - 1, d, s, mr=mr)
        out["study_ran"] = True
        if zp.get("absorption"):
            out.update(absorption=True, wait=C_ABSORB, why=REASON[C_ABSORB], study=zp, handover=bool(zp.get("handover")))
            return out
    # Abhi Z-1m: a2 handover is MANDATORY (setting `a2_handover_required`); order a2 handover → c1 LTF CHoCH → c0 commitment. Handover
    # present ⇔ zone_study(arm … t − 1)["handover"]: trade-side candles growing (body ↑ required + majority of range ↑ / close near the
    # trade-side end ↑ / volume ↑) AND counter-side candles weakening (body ↓ required + majority of opposite wick ↑ / close away ↑ /
    # volume ↓), first half vs second half of the in-zone window (any visit with an earlier and a later part — no minimum count).
    hreq = bool(s.get("a2_handover_required", False))
    if handover is not None:                                               # Abhi Z-1q: sticky per zone episode (caller)
        out["handover_state"] = handover
        handover = bool(handover.get("present"))
    else:
        handover = bool(zp.get("handover")) if zp else False
    out["handover"] = handover
    no_ho = hreq and not handover
    hs = out.get("handover_state") or {}
    ho_why = REASON[C_NO_HANDOVER] + (f" · {zp.get('line')}" if zp and zp.get("line") else "") + \
        (f" · handover cancelled ({hs['cancelled']})" if hs.get("cancelled") else "") + \
        (f" · two-candle reversal: {hs['sharp']['why']}" if (hs.get("sharp") or {}).get("why") and not hs.get("present") else "")
    push = [int(hs["seen_at"]) - 1] if hs.get("form") == "sharp_reversal" and hs.get("seen_at") is not None else []   # the rejected push
    ok, why, cm = commitment(A, t, d, lvl, s, tss, win=arm, approach=approach, exclude=push)
    out.update(commit=cm, c0=bool(ok), why=why, study=zp)
    if callable(ltf) and (not ok or no_ho):                                # lazy LTF (bots): commitment / handover नाही ⇒ LTF fetch नाही
        out.update(wait=C_NO_HANDOVER, why=ho_why) if no_ho else out.update(wait=cm.get("wait") or C_COMMIT)
        return out
    L = ltf() if callable(ltf) else ltf
    if L is not None and ltf_times is not None:
        ch = ltf_choch(L, d, *ltf_times, lvl=lvl)
    else:
        ch = {"done": False, "code": C_LTF_MISSING, "line": "LTF: LTF data missing"}
    out["choch"], out["c1"] = ch, bool(ch["done"])
    if no_ho:
        out.update(wait=C_NO_HANDOVER, why=ho_why)
        return out
    if hreq and bool(s.get("ltf_choch", True)) and not ch["done"]:         # Abhi Z-1m order: c1 before c0
        out.update(wait=ch["code"], why=f"{REASON[ch['code']]} · {ch['line']}")
        return out
    if not ok:
        out["wait"] = cm.get("wait") or C_COMMIT
        return out
    if bool(s.get("ltf_choch", True)) and not ch["done"]:
        out.update(wait=ch["code"], why=f"{REASON[ch['code']]} · {ch['line']}")
        return out
    zs = zone_study(A, arm, t, d, s, mr=mr)
    vtxt = ("volume: NA (grade cap B)" if cm.get("vol_na") else f"volume above {cm['vol_vs']}"
            if cm.get("vol_mult") is not None and str(cm.get("vol_vs", "")).startswith("the ") else "volume above the opposite side"
            if cm.get("vol_mult") is not None else "no opposite-side candle (grade cap B)")   # Abhi: the reading in words, not ratios
    btxt = "largest of the visit" if cm.get("body_mult") is not None and bool(s.get("c0_dominance", True)) else ""
    kind = "demand" if d > 0 else "supply"
    sr = (hs.get("sharp") or {}) if hs.get("form") == "sharp_reversal" else {}
    lines = [f"inside {kind}: " + (sr.get("why") if sr.get("found") else (zs.get("line") or "no clear handover read")),
             "commitment: " + " · ".join(x for x in (str(cm.get("form")), btxt, vtxt) if x),
             ch["line"] if ch["done"] else f"LTF CHoCH not required (what-if): {ch['line']}"]
    out.update(ok=True, study=zs, lines=lines, why=f"{why} · {ch['line']}")
    return out


# ------------------------------------------------------------------------------------------------ ⑦ risk (legacy: फक्त rr_step = True)
def risk(V, t, d, lvl, k, s):
    """Legacy (`rr_step` = True; Abhi 13 Oct ने default मधून काढला — SL / target dashboard चे, R:R Abhi चा निर्णय). SL = level आणि K टोक पलीकडे + buffer (σ_15M × sl_buffer_sigma); target = I_end किंवा विरुद्ध बाजूचा जवळचा जिवंत level (जवळचा)."""
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


def step_down_conv(conv):
    """Abhi (12 Oct): mature + trend रचना अखंड ⇒ grade फक्त एक पायरी खाली, पण entry अडवत नाही: A ⇒ B; B / weak / against तसेच
    (B ⇒ weak केलं असतं तर maturity ने entry अडली असती — owner नियमाविरुद्ध)."""
    return "B" if conv == "A" else conv


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
