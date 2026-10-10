"""swings2/structure.py — थर 1 §2: market structure (D1, D2; माहिती). प्रत्येक बंद 15M candle ला शुद्ध fold (replay = live).

Trend: शेवटचे दोन confirmed (non-warmup) H आणि L ⇒ UP / DOWN / RANGE; < 2 ⇒ unknown; EQH / EQL ⇒ RANGE.
Rhea / Brooks TR: ≥ 8 bars चा पट्टा ≤ 3σ, प्रत्येक कडेला ≥ 2 स्पर्श ⇒ RANGE (पट्ट्यासह); D1 15M + σ, D2 बंद 1H + σ_1H.
RANGE मध्ये BOS / CHoCH / protected नाहीत; फक्त range_break (close पट्ट्याबाहेर).
घटना (plain close; known_at = त्या 15M candle चा close): BOS, CHoCH (+ choch_disp), sweep, reversal (CHoCH ⇒ LH ⇒ BOS),
always-in flip (reversal / 3 उलट trend candles ≥ 3σ / range_break + follow-through), failed_gap_break.
"""
import numpy as np
import pandas as pd

from pivots.dc import BAR

from . import candles as SC

UPT, DNT, RNG, UNK = "UP", "DOWN", "RANGE", "unknown"


def trend_of(ps):
    hs = [p for p in ps if p.kind == "H"][-2:]
    ls = [p for p in ps if p.kind == "L"][-2:]
    if len(hs) < 2 or len(ls) < 2:
        return UNK
    if hs[1].eq or ls[1].eq:
        return RNG
    if hs[1].price > hs[0].price and ls[1].price > ls[0].price:
        return UPT
    if hs[1].price < hs[0].price and ls[1].price < ls[0].price:
        return DNT
    return RNG


def rhea(H, L, sig, i, start, s):
    """i ला संपणारा सगळ्यात लांब trailing पट्टा (span ≤ band·σ); ≥ min_bars आणि दोन्ही कडांना ≥ 2 स्पर्श ⇒ (top, bottom, bars)."""
    sg = sig[i]
    if not np.isfinite(sg) or sg <= 0:
        return None
    band = float(s["rhea_band_sigma"]) * sg
    top, bot, j = H[i], L[i], i
    while j - 1 >= start:
        t2, b2 = max(top, H[j - 1]), min(bot, L[j - 1])
        if t2 - b2 > band:
            break
        top, bot, j = t2, b2, j - 1
    nb = i - j + 1
    if nb < int(s["rhea_min_bars"]):
        return None
    tol = float(s["rhea_touch_sigma"]) * sg
    tt = int((H[j:i + 1] >= top - tol).sum())
    tb = int((L[j:i + 1] <= bot + tol).sum())
    if tt >= int(s["rhea_min_touches"]) and tb >= int(s["rhea_min_touches"]):
        return float(top), float(bot), nb
    return None


def _h1(res):
    """बंद 1H candles (index, end-bar in 15M series, H, L, σ_1H)."""
    from pivots import charts as PC
    m15 = res["m15"]
    h1 = PC.agg_1h(m15)
    t = pd.to_datetime(h1["timestamp"])
    ts15 = pd.to_datetime(m15["timestamp"])
    day = ts15.dt.normalize()
    k = ((ts15 - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(hours=1)).astype(int)
    key = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(hours=1)
    grp = pd.Series(np.arange(len(m15))).groupby(key.to_numpy())
    last = grp.max().reindex(t.to_numpy()).to_numpy().astype(int)
    firstb = grp.min().reindex(t.to_numpy()).to_numpy().astype(int)
    sig = np.array([res["sigma_1h"].get(pd.Timestamp(d), np.nan) for d in t.dt.normalize()], float)
    # 1H candle बंद = तिचा पूर्ण तास संपला (शेवटच्या 15M bar चा bar_end = सुरुवात + 1h, किंवा session-शेवट 15:30). अपूर्ण 1H कधीच नाही.
    need = np.minimum((t + pd.Timedelta(hours=1)).to_numpy(), (t.dt.normalize() + pd.Timedelta(hours=15, minutes=30)).to_numpy())
    be = pd.to_datetime(m15["bar_end"]).to_numpy()[last]
    closed = be >= need
    return h1["high"].to_numpy(float), h1["low"].to_numpy(float), np.where(closed, last, -1), sig, \
        np.array([res["segments"].get(pd.Timestamp(d)) for d in t.dt.normalize()]), firstb


def fold(res, d, rr=None):
    """degree d ची market structure. रिटर्न {"states": [per bar], "events": [...]}"""
    s = res["settings"]
    m15 = res["m15"]
    A = res["A"]
    n = len(m15)
    ts = pd.to_datetime(m15["timestamp"])
    day = ts.dt.normalize()
    segs = np.array([res["segments"].get(pd.Timestamp(x)) for x in day])
    sig = np.array([res["sigma"].get(pd.Timestamp(x), np.nan) for x in day], float)
    rr = SC.rng_ratio(res) if rr is None else rr
    piv = sorted([p for p in res["pivots"][d] if not p.warmup], key=lambda p: (p.confirm_bar, p.bar))
    if d >= 2:
        H1, L1, E1, S1, G1, F1 = _h1(res)
    events, states = [], []
    known, pi = [], 0
    fired = set()
    rng_state, rng_start = None, 0
    rev = None
    streak = []
    pending_gap = []
    follow = None
    strong = None                          # (trend dir, भाव): शेवटच्या BOS ची चाल ज्या low / high पासून सुरू झाली
    for t in range(n):
        while pi < len(piv) and piv[pi].confirm_bar <= t:
            known.append(piv[pi])
            pi += 1
        ps = [p for p in known if res["segments"].get(pd.Timestamp(p.ts).normalize()) == segs[t]]
        if t and segs[t] != segs[t - 1]:                                          # holdout ओलांडली ⇒ सगळी अवस्था नवी
            rng_state, rng_start, rev, streak, follow, pending_gap, strong = None, t, None, [], None, [], None
        c, h, l = A["c"][t], A["h"][t], A["l"][t]
        ev_t = []

        def ev(typ, level=None, dirn=0, **kw):
            e = {"degree": d, "type": typ, "bar": t, "ts": str(ts.iloc[t]), "known_at": str(ts.iloc[t] + BAR),
                 "level": None if level is None else round(float(level), 2), "dir": dirn, **kw}
            events.append(e)
            ev_t.append(e)
        # ---- range (Rhea)
        if rng_state is not None:
            if c > rng_state["top"] or c < rng_state["bottom"]:
                dirn = 1 if c > rng_state["top"] else -1
                ev("range_break", rng_state["top"] if dirn > 0 else rng_state["bottom"], dirn)
                follow = (t, dirn, c)
                rng_state, rng_start = None, t + 1
        if rng_state is None:
            if d < 2:
                r = rhea(A["h"], A["l"], sig, t, rng_start, s) if t >= rng_start else None
            else:
                r = None
                idx = np.flatnonzero(E1 == t)
                if len(idx):
                    i1 = int(idx[0])
                    cand = np.flatnonzero((F1 >= rng_start) & (G1 == segs[t]))           # range_break नंतर सुरू होणाऱ्या 1H candles पासूनच
                    r = rhea(H1, L1, S1, i1, int(cand[0]), s) if len(cand) and cand[0] <= i1 else None
            if r is not None:
                rng_state = {"top": r[0], "bottom": r[1], "bars": r[2], "known_at": str(ts.iloc[t] + BAR)}
                ev("range_start", None, 0, top=round(r[0], 2), bottom=round(r[1], 2))
        if follow is not None and t == follow[0] + 1:
            if (c - follow[2]) * follow[1] > 0:
                ev("always_in_flip", None, follow[1], why="range_break + follow-through")
            follow = None
        tr = RNG if rng_state is not None else trend_of(ps)
        hs = [p for p in ps if p.kind == "H"]
        ls = [p for p in ps if p.kind == "L"]
        lastH, lastL = (hs[-1] if hs else None), (ls[-1] if ls else None)
        strict = None
        if tr == UPT and lastH is not None:
            pre = [p for p in ls if p.bar < lastH.bar]
            strict = pre[-1] if pre else None
        elif tr == DNT and lastL is not None:
            pre = [p for p in hs if p.bar < lastL.bar]
            strict = pre[-1] if pre else None
        # ---- pivot वरून RANGE (HH + LL / EQ): पट्टा = शेवटच्या दोन H चा वरचा, दोन L चा खालचा ⇒ फक्त range_break
        if tr == RNG and rng_state is None and len(hs) >= 2 and len(ls) >= 2:
            top, bot = max(p.price for p in hs[-2:]), min(p.price for p in ls[-2:])
            key = ("prb", hs[-1].bar, ls[-1].bar)
            if (c > top or c < bot) and key not in fired:
                fired.add(key)
                dirn = 1 if c > top else -1
                ev("range_break", top if dirn > 0 else bot, dirn, source="pivots")
                follow = (t, dirn, c)
        # ---- घटना (फक्त UP / DOWN)
        if tr in (UPT, DNT):
            up = tr == UPT
            ext = lastH if up else lastL
            dirn = 1 if up else -1
            if strong is not None and strong[0] != dirn:
                strong = None
            if ext is not None and (c - ext.price) * dirn > 0 and ("bos", d, ext.bar) not in fired:
                fired.add(("bos", d, ext.bar))
                gapbar = bool(res["first"][t] and (A["o"][t] - ext.price) * dirn > 0)
                seg_lo = A["l"][ext.bar + 1:t + 1] if up else A["h"][ext.bar + 1:t + 1]
                if len(seg_lo):                                                        # strong low / high: BOS ची चाल इथून
                    strong = (dirn, float(seg_lo.min() if up else seg_lo.max()))
                ev("BOS", ext.price, dirn, gap=gapbar)
                if gapbar:
                    pending_gap.append((t, ext.price, dirn))
            if strict is not None and (strict.price - c) * dirn > 0 and ("choch", d, strict.bar) not in fired:
                fired.add(("choch", d, strict.bar))
                disp = SC.is_displacement(A, rr, t, -dirn, s)
                ev("CHoCH", strict.price, -dirn, disp=disp)
                if disp:
                    ev("choch_disp", strict.price, -dirn)
                rev = {"dir": -dirn, "choch_bar": t, "H1": ext.price if ext is not None else None, "stage": 1, "lh": None}
            pairs = ((lastH, 1), (strict if strict is not None else lastL, -1)) if up else \
                ((lastL, -1), (strict if strict is not None else lastH, 1))
            for lv, side in pairs:                                                     # sweep: wick पलीकडे, close अलीकडे (एका पातळीला एकदा)
                if lv is None:
                    continue
                if side > 0 and h > lv.price and c <= lv.price and ("sw", lv.bar, 1) not in fired:
                    fired.add(("sw", lv.bar, 1))
                    ev("sweep", lv.price, 1)
                if side < 0 and l < lv.price and c >= lv.price and ("sw", lv.bar, -1) not in fired:
                    fired.add(("sw", lv.bar, -1))
                    ev("sweep", lv.price, -1)
        # ---- failed gap break
        for g in list(pending_gap):
            g0, lv, dirn = g
            if t > g0 and (lv - c) * dirn >= 0:
                ev("failed_gap_break", lv, dirn)
                pending_gap.remove(g)
            elif t - g0 >= int(s["failed_gap_candles"]):
                pending_gap.remove(g)
        # ---- reversal (CHoCH ⇒ LH ⇒ BOS)
        if rev is not None and rev["H1"] is not None:
            rd = rev["dir"]
            if (c - rev["H1"]) * (-rd) > 0:
                ev("reversal_cancel", rev["H1"], rd)
                rev = None
            elif rev["stage"] == 1:
                kind = "H" if rd < 0 else "L"
                cand = [p for p in ps if p.kind == kind and p.bar > rev["choch_bar"] and (p.price - rev["H1"]) * (-rd) < 0]
                if cand:
                    rev.update(stage=2, lh=cand[-1])
                    ev("LH" if rd < 0 else "HL_rev", cand[-1].price, rd)
            if rev is not None and rev["stage"] == 2:
                a, b = rev["choch_bar"], rev["lh"].bar
                lvl = float(A["l"][a:b + 1].min()) if rd < 0 else float(A["h"][a:b + 1].max())
                if (c - lvl) * rd > 0:
                    ev("reversal", lvl, rd)
                    ev("always_in_flip", None, rd, why="reversal पूर्ण")
                    rev = None
        # ---- always-in: ≥ 3 लागोपाठ उलट trend candles, net ≥ 3σ
        if tr in (UPT, DNT):
            od = -1 if tr == UPT else 1
            streak = streak + [t] if SC.is_trend_candle(A, t, od, s) else []
            k = int(s["always_in_candles"])
            if len(streak) >= k and np.isfinite(sig[t]):
                f0 = streak[0]                                                         # एका streak ला एकदाच; net = पहिल्या candle च्या open पासून
                if abs(c - A["o"][f0]) >= float(s["always_in_sigma"]) * sig[t] and ("ai", f0) not in fired:
                    fired.add(("ai", f0))
                    ev("always_in_flip", None, od, why=f"{len(streak)} उलट trend candles")
        else:
            streak = []
        states.append({"trend": tr, "range": rng_state, "lastH": None if lastH is None else lastH.price,
                       "lastL": None if lastL is None else lastL.price, "strict": None if strict is None else strict.price,
                       "strict_bar": None if strict is None else strict.bar,
                       "protected": (strong[1] if strong is not None and tr in (UPT, DNT) and strong[0] == (1 if tr == UPT else -1)
                                     else (None if strict is None else strict.price)),
                       "weak": None if (tr not in (UPT, DNT)) else
                       (lastH.price if tr == UPT else lastL.price), "reversal": None if rev is None else rev["stage"]})
    return {"states": states, "events": events}


def all_structure(res):
    rr = SC.rng_ratio(res)
    out = {d: fold(res, d, rr) for d in res["settings"]["structure_degrees"]}
    if 1 in out and 2 in out:                                     # D1 CHoCH जी D2 trend विरुद्ध ⇒ "pullback सुरू"
        for e in out[1]["events"]:
            if e["type"] == "CHoCH":
                t2 = out[2]["states"][e["bar"]]["trend"]
                if (t2 == UPT and e["dir"] < 0) or (t2 == DNT and e["dir"] > 0):
                    e["note"] = "pullback सुरू (D2 trend विरुद्ध)"
    return out, rr
