"""chart_reader/evidence.py — KB भाग D चे नवीन (✚) पुरावे आणि A3 चे व्याख्यात्मक व्हेटो.

🎓 Abhi (2026-10-08, Knowledge Base): प्रत्येक पुरावा = आधी ठरवलेले गुण (settings) + एक ओळ (chapter tag सह); tuning नाही.
  PB [K2]   pullback चं स्वरूप: 3 waves + overlap + origin अबाधित + खोली 38.2–80% ⇒ +10 · धोक्याची चिन्हं ⇒ −10 · origin जवळ /
            100% पलीकडे wick पण acceptance नाही ⇒ −15 (acceptance = व्हेटो)
  LQ [K5]   A चा low / equal lows / PDL / range edge चा sweep (0.1–1.0 MR पलीकडे) आणि reclaim close ⇒ +5; sweep bar ची wick ≥ 50% ⇒ +3
  DV [K10.2] RSI(14) divergence, फक्त price pivots वर (RSI त्याच bar चा): C-end ला regular +5, pullback मध्ये hidden +3,
            impulse च्या टोकावर विरुद्ध regular −3
  PT [K11]  flag +5 · correction चा opposite wedge +3 · double top/bottom किंवा H&S (neckline close ने तुटलेली), impulse स्वतः wedge ⇒ −10
  TM [K14]  09:15–09:45 −5 · expiry दिवस सकाळ −3
  VX [K14]  pullback दरम्यान VIX उडी −5 · VIX घटतोय +2 · data नाही ⇒ 0
  (VL [K10.3] ⇒ volume.py)
व्हेटो (score च्या बाहेर, A3): count स्पष्ट असताना A-end / B च्या आत · impulse origin पलीकडे acceptance (real break, elliott/breaks.py) ·
MAGNET level · gap setup B मध्ये pullback आलाच नाही.
सगळं फक्त दिलेल्या **बंद** bars वरून (no-lookahead); pivots = elliott/swings.py (measures.pivots), MR = 20 बंद bars.
"""
import numpy as np
import pandas as pd

from . import measures as M


def _res(pts, line, **kw):
    return {"pts": float(pts), "line": line, **kw}


# ---------------------------------------------------------------------------------------------------------------------
# PB [K2]
# ---------------------------------------------------------------------------------------------------------------------
def pullback(st, s, deep_support=False):
    """st = structure.read चा निकाल. deep_support = 80% पलीकडच्या खोलीवर ठोस area / sweep आहे का (evaluate देतो)."""
    if not st.get("impulse"):
        return _res(0, "PB 0 [K2]: impulse नाही")
    reasons = st.get("reversal_reasons") or []
    r = st.get("retrace")
    if "impulse_origin_acceptance" in reasons:
        return _res(0, "PB 0 [K2]: impulse origin पलीकडे acceptance ⇒ व्हेटो (A3)", veto=True)
    if st.get("origin_probe") or (r is not None and r >= s["pb_near_origin_retrace"]):
        why = "100% पलीकडे wick / close पण acceptance नाही" if st.get("origin_probe") else f"origin जवळ (retrace {r:.0%})"
        return _res(s["w_pb_near_origin"], f"PB {s['w_pb_near_origin']:+g} [K2]: {why}")
    danger = []
    if "counter_move_impulsive" in reasons:
        danger.append("counter-move impulsive (displacement / 5 waves)")
    if "acceptance_major_level" in reasons:
        danger.append("major level पलीकडे acceptance")
    if r is not None and r > s["retrace_max"] and not deep_support:
        danger.append(f"खोली {r:.0%} > {s['retrace_max']:.0%} आणि तिथे area / sweep नाही")
    if danger:
        return _res(s["w_pb_danger"], f"PB {s['w_pb_danger']:+g} [K2]: धोक्याची चिन्हं — " + "; ".join(danger))
    ctype, ov = st.get("correction_type"), st.get("overlap")
    three = ctype in ("zigzag", "flat", "triangle")
    overlap = ov is not None and ov >= s["pb_overlap_min"]
    depth = ctype == "triangle" or (r is not None and s["retrace_lo"] <= r <= s["retrace_max"])
    parts = {"3 waves": three, "overlap": overlap, "origin अबाधित": True, "खोली 38.2–80%": depth}
    txt = ", ".join(f"{k} {'✓' if v else '✗'}" for k, v in parts.items()) + f" (overlap {ov if ov is not None else '—'})"
    if all(parts.values()):
        return _res(s["w_pb_healthy"], f"PB {s['w_pb_healthy']:+g} [K2]: healthy pullback — {txt}")
    return _res(0, f"PB 0 [K2]: {txt}")


# ---------------------------------------------------------------------------------------------------------------------
# LQ [K5]
# ---------------------------------------------------------------------------------------------------------------------
def pools(st, cands, side):
    """trade विरुद्धच्या बाजूचे stop pools [(level, bar | None, नाव)]: A-end, equal highs/lows, PDL/PDH, range edge."""
    out = []
    corr, cb = st.get("correction") or [], st.get("correction_bars") or []
    if len(corr) >= 4:                                                    # A संपून B आलेला ⇒ A चं टोक pool
        out.append((float(corr[1]), int(cb[1]), "A-end"))
    want = "equal_lows" if side > 0 else "equal_highs"
    for z in cands or []:
        if z.get("pool") == want and z.get("level") is not None:
            out.append((float(z["level"]), z.get("bar"), z["id"]))
        elif z.get("id") == ("PDL" if side > 0 else "PDH"):
            out.append(((z["low"] + z["high"]) / 2.0, None, z["id"]))
        elif z.get("tool") == "d" and z.get("role") == ("SUPPORT" if side > 0 else "RESISTANCE"):
            out.append((float(z["low"] if side > 0 else z["high"]), None, f"range edge {z['id']}"))
    return out


def _intact_since(df, level, side, pbar, j):
    """Pool अबाधित: pool बनल्यानंतर (pbar नसेल ⇒ त्याच दिवसाच्या सुरुवातीपासून) sweep bar च्या आधी कोणत्याही bar ने level पार केली नाही,
    आणि sweep bar आतल्या बाजूने उघडला. Gap open ने level ओलांडली (उदा. gap down open pool च्या वर, मग खाली) ⇒ pool आधीच वापरला गेला ⇒
    sweep नाही (KB K5; TRADE_KB_FULL_IMPLEMENTATION_PROMPT §8.2)."""
    o, h, lo = (df[k].to_numpy(float) for k in ("open", "high", "low"))
    beyond_open = (o[j] <= level) if side > 0 else (o[j] >= level)
    if beyond_open:
        return False
    if pbar is not None:
        a = int(pbar) + 1
    else:
        d = pd.to_datetime(df["timestamp"]).dt.normalize().to_numpy()
        a = j
        while a > 0 and d[a - 1] == d[j]:
            a -= 1
    seg = lo[a:j] if side > 0 else h[a:j]
    return not len(seg) or (bool((seg >= level).all()) if side > 0 else bool((seg <= level).all()))


def liquidity(df, st, cands, side, s, mr, n_recent=3):
    """शेवटच्या n_recent बंद bars पैकी एकाने pool च्या 0.1–1.0 MR पलीकडे जाऊन आत close (किंवा पुढच्या 1–2 bars नी), आणि शेवटचा close
    अजून आत ⇒ sweep + reclaim. Pool sweep bar च्या आधी तयार झालेला हवा (no-lookahead), आणि तोपर्यंत अबाधित; sweep bar आतल्या बाजूने
    उघडलेला (gap open / gap ने ओलांडलेली level = sweep नाही)."""
    if not side or not mr:
        return _res(0, "LQ 0 [K5]: —")
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(c)
    best = None
    for level, pbar, name in pools(st, cands, side):
        for j in range(max(0, n - int(n_recent)), n):
            if pbar is not None and pbar >= j:
                continue
            if not _intact_since(df, level, side, pbar, j):
                continue
            depth = (level - lo[j]) if side > 0 else (h[j] - level)
            if not (s["sweep_min_mr"] * mr <= depth <= s["sweep_max_mr"] * mr):
                continue
            inside = [k for k in range(j, min(j + 3, n)) if ((c[k] > level) if side > 0 else (c[k] < level))]
            if not inside or not ((c[-1] > level) if side > 0 else (c[-1] < level)):
                continue
            rng = max(h[j] - lo[j], 1e-9)
            wick = ((min(o[j], c[j]) - lo[j]) if side > 0 else (h[j] - max(o[j], c[j]))) / rng
            pts = s["w_lq_sweep"] + (s["w_lq_wick"] if wick >= s["lq_wick_min"] else 0.0)
            if best is None or pts > best["pts"]:
                best = _res(pts, f"LQ {pts:+g} [K5]: {name} ({level:,.1f}) चा sweep {depth / mr:.2f}× MR आणि reclaim close"
                                 + (f" · wick {wick:.0%}" if wick >= s["lq_wick_min"] else ""), pool=name, level=round(level, 2))
    return best or _res(0, "LQ 0 [K5]: sweep + reclaim नाही")


# ---------------------------------------------------------------------------------------------------------------------
# DV [K10.2]
# ---------------------------------------------------------------------------------------------------------------------
def rsi(close, n=14):
    """Wilder RSI(n). पहिल्या n bars ला NaN. फक्त आधीचे closes ⇒ causal."""
    c = np.asarray(close, float)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c, prepend=c[0])
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    au, ad = up[1:n + 1].mean(), dn[1:n + 1].mean()
    for i in range(n, len(c)):
        if i > n:
            au = (au * (n - 1) + up[i]) / n
            ad = (ad * (n - 1) + dn[i]) / n
        out[i] = 100.0 if ad == 0 else 100.0 - 100.0 / (1.0 + au / ad)
    return out


def _line_ok(x, a, b, kind):
    """a, b (bar indices) मधल्या bars नी a–b रेषा तोडलेली नाही (lows साठी खाली नाही, highs साठी वर नाही)."""
    if b - a < 2:
        return True
    seg = np.arange(a + 1, b)
    line = x[a] + (x[b] - x[a]) * (seg - a) / (b - a)
    return bool((x[seg] >= line - 1e-9).all()) if kind == "L" else bool((x[seg] <= line + 1e-9).all())


def _confirmed(x, i, kind, k):
    """bar i नंतर ≥ k बंद bars आणि त्यांनी i चं टोक ओलांडलं नाही ⇒ pivot confirmed (no-lookahead)."""
    after = x[i + 1:]
    if len(after) < k:
        return False
    return bool((after >= x[i]).all()) if kind == "L" else bool((after <= x[i]).all())


def divergence(df, st, side, s, mr, htf=None):
    imp = st.get("impulse")
    if not side or not imp or len(df) <= s["dv_rsi_len"] + 2:
        return _res(0, "DV 0 [K10.2]: —")
    r = rsi(df["close"].to_numpy(float), int(s["dv_rsi_len"]))
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    ext = lo if side > 0 else hi                                         # pullback ची टोकं (bull ⇒ lows)
    kind = "L" if side > 0 else "H"
    corr, cb = st.get("correction") or [], st.get("correction_bars") or []
    k, nmin, nmax = int(s["dv_confirm_bars"]), int(s["dv_min_bars"]), int(s["dv_max_bars"])
    dp, dr = s["dv_price_mr"] * mr, s["dv_rsi_pts"]
    pos, neg, txt = 0.0, 0.0, []

    def ok_rsi(*ix):
        return all(np.isfinite(r[i]) for i in ix)

    # regular at C-end: C, A पेक्षा पुढे (LL / HH), RSI उलट
    if len(corr) >= 4 and len(cb) >= 4:
        a, cc = int(cb[1]), int(cb[-1])
        if ((len(corr) - 1) % 2 == 1) and nmin <= cc - a <= nmax and ok_rsi(a, cc) and _confirmed(ext, cc, kind, k):
            further = (ext[a] - ext[cc]) if side > 0 else (ext[cc] - ext[a])
            rsi_turn = (r[cc] - r[a]) if side > 0 else (r[a] - r[cc])
            loc = r[a] <= s["dv_regular_os"] if side > 0 else r[a] >= 100 - s["dv_regular_os"]
            if further >= dp and rsi_turn >= dr and loc and _line_ok(ext, a, cc, kind):
                pos = max(pos, s["w_dv_regular"])
                txt.append(f"C-end ला regular divergence (RSI {r[a]:.0f} → {r[cc]:.0f})")
    # hidden in pullback: pullback टोक impulse origin पेक्षा आत (HL / LH), RSI पुढे
    pb = int(cb[-1]) if cb and (len(cb) - 1) % 2 == 1 else None          # शेवटचा leg correction दिशेने
    o_bar = int(imp["start_bar"])
    trend_ok = htf in (None, "up" if side > 0 else "down")
    if pb is not None and pb > o_bar and nmin <= pb - o_bar <= nmax and ok_rsi(o_bar, pb) and trend_ok and _confirmed(ext, pb, kind, k):
        inside = (ext[pb] - ext[o_bar]) if side > 0 else (ext[o_bar] - ext[pb])
        rsi_more = (r[o_bar] - r[pb]) if side > 0 else (r[pb] - r[o_bar])
        loc = r[pb] >= s["dv_hidden_rsi_min"] if side > 0 else r[pb] <= 100 - s["dv_hidden_rsi_min"]
        if inside >= dp and rsi_more >= dr and loc:
            pos = max(pos, s["w_dv_hidden"])
            txt.append(f"pullback मध्ये hidden divergence (origin RSI {r[o_bar]:.0f}, pullback RSI {r[pb]:.0f})")
    # against: impulse च्या टोकावर विरुद्ध regular divergence
    e_bar = int(imp["end_bar"])
    okind = "H" if side > 0 else "L"
    prev = [p for p in M.pivots(df.iloc[: e_bar + 1].reset_index(drop=True), s["internal_atr_mult"])
            if p[2] == okind and nmin <= e_bar - p[0] <= nmax]
    if prev and ok_rsi(prev[-1][0], e_bar):
        b0 = prev[-1][0]
        x = hi if side > 0 else lo
        further = (x[e_bar] - x[b0]) if side > 0 else (x[b0] - x[e_bar])
        weaker = (r[b0] - r[e_bar]) if side > 0 else (r[e_bar] - r[b0])
        loc = r[b0] >= 100 - s["dv_regular_os"] if side > 0 else r[b0] <= s["dv_regular_os"]
        if further >= dp and weaker >= dr and loc and _line_ok(x, b0, e_bar, okind):
            neg = s["w_dv_against"]
            txt.append(f"impulse च्या टोकावर विरुद्ध regular divergence (RSI {r[b0]:.0f} → {r[e_bar]:.0f})")
    pts = pos + neg
    return _res(pts, f"DV {pts:+g} [K10.2]: " + ("; ".join(txt) if txt else "divergence नाही"), rsi_last=None if not np.isfinite(r[-1])
                else round(float(r[-1]), 1))


# ---------------------------------------------------------------------------------------------------------------------
# PT [K11]
# ---------------------------------------------------------------------------------------------------------------------
def _wedge(pts, dirn):
    """pts = [(bar, price, kind)] क्रमाने. ≥ 3 highs आणि ≥ 3 lows, दोन्ही रेषा dirn दिशेने, एकमेकांकडे येणाऱ्या, legs लहान होत जाणारे."""
    H = [p for p in pts if p[2] == "H"][-3:]
    L = [p for p in pts if p[2] == "L"][-3:]
    if len(H) < 3 or len(L) < 3:
        return False
    sh = (H[-1][1] - H[0][1]) / max(H[-1][0] - H[0][0], 1)
    sl = (L[-1][1] - L[0][1]) / max(L[-1][0] - L[0][0], 1)
    if not (sh * dirn > 0 and sl * dirn > 0):
        return False
    w0, w1 = H[0][1] - L[0][1], H[-1][1] - L[-1][1]
    trend_legs = [abs(b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:]) if (b[1] - a[1]) * dirn > 0][-3:]
    return w1 < w0 and len(trend_legs) >= 2 and all(trend_legs[i + 1] < trend_legs[i] for i in range(len(trend_legs) - 1))


def patterns(df, st, side, s, mr):
    imp = st.get("impulse")
    if not side or not imp or not mr:
        return _res(0, "PT 0 [K11]: —")
    c = df["close"].to_numpy(float)
    n = len(c)
    pos, found = 0.0, []
    # flag: pole = impulse (≥ 6 MR, ≤ 12 bars); consolidation 4–20 bars, ≤ 0.5 pole, pole विरुद्ध उतार
    cbars = n - 1 - imp["end_bar"]
    pole = abs(imp["end"] - imp["origin"])
    if (pole >= s["pt_pole_min_mr"] * mr and imp["bars"] <= s["pt_pole_max_bars"] and s["pt_flag_min_bars"] <= cbars <= s["pt_flag_max_bars"]
            and (st.get("retrace") or 1.0) <= s["pt_flag_max_retrace"] and (c[-1] - imp["end"]) * side < 0):
        pos = max(pos, s["w_pt_flag"])
        found.append("flag (pole नंतर लहान counter consolidation)")
    piv = [(b, px, k) for b, px, k, _ in M.pivots(df, s["internal_atr_mult"])]
    corr_piv = [p for p in piv if p[0] >= imp["end_bar"]]
    if _wedge(corr_piv, -side):
        pos = max(pos, s["w_pt_wedge"])
        found.append("correction चा opposite wedge")
    neg = []
    imp_piv = [p for p in piv if imp["start_bar"] <= p[0] <= imp["end_bar"]]
    if _wedge(imp_piv, side):
        neg.append("impulse स्वतः " + ("rising" if side > 0 else "falling") + " wedge (थकवा)")
    tops = "H" if side > 0 else "L"
    T = [p for p in piv if p[2] == tops]
    if not any(abs(p[0] - imp["end_bar"]) <= 2 for p in T):                 # impulse टोक (pivot अजून confirmed नसेल तर)
        T = sorted(T + [(imp["end_bar"], float(imp["end"]), tops)])
    x = df["high"].to_numpy(float) if side > 0 else df["low"].to_numpy(float)
    y = df["low"].to_numpy(float) if side > 0 else df["high"].to_numpy(float)
    cb = st.get("correction_bars") or []
    flat_b = st.get("correction_type") == "flat" and len(cb) >= 3                 # flat मध्ये B ≈ impulse टोक आणि C, A पलीकडे = सामान्य (K3)
    if len(T) >= 2:
        (b1, p1, _), (b2, p2, _) = T[-2], T[-1]
        if flat_b and abs(b2 - cb[2]) <= 2:
            pass                                                         # तो "double top" नाही — flat चा B (C-end हा मुख्य setup)
        elif abs(p2 - p1) <= s["pt_dt_tol_mr"] * mr and b2 - b1 >= s["pt_dt_min_bars"]:
            trough = y[b1:b2 + 1].min() if side > 0 else y[b1:b2 + 1].max()
            deep = (min(p1, p2) - trough) if side > 0 else (trough - max(p1, p2))
            broke = ((c[b2 + 1:] < trough) if side > 0 else (c[b2 + 1:] > trough)).any()
            if deep >= s["pt_dt_trough_mr"] * mr and broke:
                neg.append(("double top" if side > 0 else "double bottom") + " (neckline close ने तुटली)")
    if len(T) >= 3:
        (bl, pl, _), (bh, ph, _), (br, pr, _) = T[-3], T[-2], T[-1]
        head = (ph - max(pl, pr)) if side > 0 else (min(pl, pr) - ph)
        if head >= s["pt_hs_head_mr"] * mr and abs(pl - pr) <= s["pt_hs_shoulder_mr"] * mr:
            t1 = bl + int(np.argmin(y[bl:bh + 1]) if side > 0 else np.argmax(y[bl:bh + 1]))
            t2 = bh + int(np.argmin(y[bh:br + 1]) if side > 0 else np.argmax(y[bh:br + 1]))
            if t2 > t1:
                slope = (y[t2] - y[t1]) / (t2 - t1)
                after = np.arange(br + 1, n)
                neck = y[t1] + slope * (after - t1)
                if len(after) and (((c[after] < neck) if side > 0 else (c[after] > neck)).any()):
                    neg.append(("H&S" if side > 0 else "inverse H&S") + " (neckline close ने तुटली)")
    if neg:
        return _res(s["w_pt_reversal"], f"PT {s['w_pt_reversal']:+g} [K11]: reversal pattern — " + "; ".join(neg), found=neg)
    return _res(pos, f"PT {pos:+g} [K11]: " + ("; ".join(found) if found else "pattern नाही"), found=found)


# ---------------------------------------------------------------------------------------------------------------------
# TM / VX [K14]
# ---------------------------------------------------------------------------------------------------------------------
def time_of_day(bar_end, s, expiry_day=None):
    t = pd.Timestamp(bar_end)
    pts, why = 0.0, []
    hm = t.strftime("%H:%M")
    if hm <= s["tm_open_end"]:
        pts += s["w_tm_open"]
        why.append(f"09:15–{s['tm_open_end']} signal (कमी विश्वासार्ह)")
    exp = (t.weekday() == int(s["tm_expiry_weekday"])) if expiry_day is None else bool(expiry_day)
    if exp and hm <= s["tm_expiry_morning_end"]:
        pts += s["w_tm_expiry_morning"]
        why.append("expiry दिवस सकाळ")
    pts = max(pts, s["w_tm_open"])
    return _res(pts, f"TM {pts:+g} [K14]: " + ("; ".join(why) if why else f"वेळ {hm} — ठीक"))


def vix(vix_df, t0, t1, s):
    """VIX बदल pullback दरम्यान: t0 = correction सुरू (impulse टोकाचा bar end), t1 = signal. vix_df: bar_end (किंवा timestamp = bar start +
    bar_minutes, default 1) आणि close — फक्त t पर्यंत **बंद** झालेले VIX bars (no-lookahead)."""
    if vix_df is None or not len(vix_df) or t0 is None:
        return _res(0, "VX 0 [K14]: VIX data नाही")
    if "bar_end" in vix_df.columns:
        ts = pd.to_datetime(vix_df["bar_end"])
    else:
        ts = pd.to_datetime(vix_df["timestamp"]) + pd.Timedelta(minutes=int(vix_df.attrs.get("bar_minutes", 1)))
    v0 = vix_df.loc[ts <= pd.Timestamp(t0), "close"]
    v1 = vix_df.loc[ts <= pd.Timestamp(t1), "close"]
    if v0.empty or v1.empty or float(v0.iloc[-1]) <= 0:
        return _res(0, "VX 0 [K14]: VIX data नाही")
    a, b = float(v0.iloc[-1]), float(v1.iloc[-1])
    chg = (b / a - 1.0) * 100.0
    if chg >= s["vx_jump_pct"]:
        return _res(s["w_vx_jump"], f"VX {s['w_vx_jump']:+g} [K14]: pullback दरम्यान VIX उडी {a:.2f} → {b:.2f} ({chg:+.1f}%)", chg=round(chg, 2))
    if chg <= s["vx_fall_pct"]:
        return _res(s["w_vx_falling"], f"VX {s['w_vx_falling']:+g} [K14]: VIX घटतोय {a:.2f} → {b:.2f} ({chg:+.1f}%)", chg=round(chg, 2))
    return _res(0, f"VX 0 [K14]: VIX {a:.2f} → {b:.2f} ({chg:+.1f}%)", chg=round(chg, 2))


# ---------------------------------------------------------------------------------------------------------------------
# A3 व्याख्यात्मक व्हेटो
# ---------------------------------------------------------------------------------------------------------------------
def vetoes(st, el, act, cands, gap, side, trig, s, mr):
    """रिटर्न व्हेटो ओळींची यादी (रिकामी ⇒ व्हेटो नाही)."""
    out = []
    if (el or {}).get("state") == "a_end_or_in_b" and (el or {}).get("clear"):
        out.append("⛔ [K3] count स्पष्ट: A-end / B च्या आत ⇒ pullback संपलेला नाही")
    if "impulse_origin_acceptance" in (st.get("reversal_reasons") or []):
        out.append("⛔ [K2/K5] impulse origin पलीकडे acceptance (real break) ⇒ trend बदलला, pullback नाही")
    area = (act or {}).get("area")
    if trig is not None and len(trig):
        px = float(trig["close"].iloc[-1])
        for z in cands or []:
            if z.get("state") != "MAGNET":
                continue
            hit = z["low"] <= px <= z["high"] or (area is not None and z["low"] <= area["high"] and area["low"] <= z["high"])
            if hit:
                out.append(f"⛔ [K5] MAGNET level {z['id']} ({z['low']:,.1f}–{z['high']:,.1f}) ⇒ no-trade level")
                break
    # gap setup B ("पहिला pullback नाही") आता chart_reader/gap.py (सगळे वर्ग, gap edge / PDC / zone पर्यंत) ⇒ पक्का नियम GAP_NO_PULLBACK
    return out
