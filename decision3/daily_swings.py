"""decision3/daily_swings.py — Daily swing review (Abhi: Telegram वर Daily swings engine ने कुठे मांडले ते पाहणे; फक्त दृश्य तपासणी).

दोन थर (engine पूर्ण उपलब्ध history वर; chart फक्त शेवटची `window` sessions दाखवतो — कोणताही parameter chart पाहून बदलत नाही):
  a. Dow (minor swings, Q15 आधीचा engine — `daily_trend_mode: minor`): confirmed pivots (daily_pivot_n), HH/HL/LH/LL, protected swing
     (pivot पासून तो तुटला / बदलला तिथपर्यंत), trend पट्टे (UP / DOWN / NEUTRAL / RANGE) — engine NEUTRAL कुठे झाला ते दिसतं.
  b. Degree-aware (Q15, आताचा default `impulse`): protected = impulse origin, phase (mechanical leg क्रमांक L3 / L4 … फक्त JSON debug —
     Q34), legs impulse / corrective
     (Q15 fold च्या phase वरून — legs2 / patterns2 intraday swings2 वर चालतात, Daily वर नाहीत ⇒ Q32), maturity.
  Elliott (advisory, निर्णयात नाही): elliott.counts CountEngine Daily frames वर (fixed degree TF = 1d); preferred count चे wave labels,
  vote कमकुवत (gray) ⇒ "?".
Order / broker / AI call नाही. तारखा / किंमती code मध्ये नाहीत.
"""
import numpy as np
import pandas as pd

from . import daily as DD
from . import settings as S3

TAG_KINDS = ("HH", "LH", "HL", "LL")


def prepare(df):
    """Daily OHLC ⇒ timestamp (IST, normalize), bar_end (15:30), duplicates नाहीत, क्रमाने."""
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    if getattr(d["timestamp"].dt, "tz", None) is not None:
        d["timestamp"] = d["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d["timestamp"] = d["timestamp"].dt.normalize()
    d = d.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    return d[["timestamp", "bar_end", "open", "high", "low", "close"]]


def tag_pivots(pivots):
    """HH / LH (H) आणि HL / LL (L) — मागच्या त्याच प्रकारच्या pivot शी तुलना; पहिला ⇒ "H" / "L"."""
    out, last = [], {}
    for p in pivots:
        prev = last.get(p.kind)
        if prev is None:
            tag = p.kind
        elif p.kind == "H":
            tag = "HH" if p.price > prev else "LH"
        else:
            tag = "HL" if p.price > prev else "LL"
        last[p.kind] = p.price
        out.append(tag)
    return out


def runs(values):
    """[(start, end, value)] — सलग समान values (end inclusive)."""
    out, s = [], 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[s]:
            out.append((s, i - 1, values[s]))
            s = i
    return out


def protected_segments(states, C):
    """प्रत्येक protected swing: pivot पासून ज्या bar ला तो बदलला / तुटला तिथपर्यंत. ended = "broken" (त्या bar चा close पलीकडे, किंवा
    तुटल्याचा पहिला bar — Q15 phase origin_broken / minor trend UP|DOWN → NEUTRAL; protected state मध्ये तसाच राहतो पण तुटला) / "moved" (नवा protected) / "open" (अजून चालू)."""
    segs, cur, since, closed, prev_tr = [], None, None, False, None
    for i, st in enumerate(states):
        p = st.protected
        key = None if p is None else (p.kind, p.bar, round(p.price, 6))
        if key != cur:
            if cur is not None and not closed:
                kind, bar, price = cur
                broken = (C[i] < price) if kind == "L" else (C[i] > price)
                segs.append({"kind": kind, "bar": bar, "price": price, "from": since, "to": i, "ended": "broken" if broken else "moved"})
            cur, since, closed = key, i, False
        brk_now = getattr(st, "phase", None) == "origin_broken" or (st.trend == "NEUTRAL" and prev_tr in ("UP", "DOWN"))
        if cur is not None and not closed and brk_now:
            kind, bar, price = cur                                         # Q15: origin close ने तुटला; minor: trend → NEUTRAL
            segs.append({"kind": kind, "bar": bar, "price": price, "from": since, "to": i, "ended": "broken"})   # — X इथेच
            closed = True
        prev_tr = st.trend
    if cur is not None and not closed:
        kind, bar, price = cur
        segs.append({"kind": kind, "bar": bar, "price": price, "from": since, "to": len(states) - 1, "ended": "open"})
    return segs


def legs(pivots, states):
    """सलग pivots मधले legs; Q15 class: leg ची दिशा त्या वेळच्या (leg संपताना) trend शी जुळते आणि phase impulse ⇒ impulse; trend
    असून उलट ⇒ corrective; trend नाही ⇒ none."""
    out = []
    for a, b in zip(pivots, pivots[1:]):
        dirn = 1 if b.kind == "H" else -1
        st = states[min(b.bar, len(states) - 1)]
        tdir = {"UP": 1, "DOWN": -1}.get(st.trend, 0)
        cls = "none" if tdir == 0 else ("impulse" if dirn == tdir and st.phase == "impulse" else "corrective")
        out.append({"from": a.bar, "to": b.bar, "p0": a.price, "p1": b.price, "dir": dirn, "class": cls})
    return out


def structure_objects(d, states, s=None):
    """Abhi daily review A / C1: trend-degree रचना objects (chart + JSON) — फक्त engine states वरून (नवीन संख्या नाहीत).

    • legs: प्रत्येक impulse leg (origin bar ⇒ leg चं टोक), एक रेषा.
    • corrections: दोन impulse legs मधली same-degree correction (मागच्या leg च्या टोकापासून पुढच्या leg च्या origin पर्यंत) +
      चालू (counter = candidate / correction) — "in progress". depth = correction ÷ आधीचा impulse leg (data वरून); shape =
      patterns2 नियम (daily_legs.structure) एक degree खालच्या pivots वर: zigzag / flat / 3-wave / impulse; वाचता येत नाही ⇒ None.
    • bounces: impulse leg मधले same-degree उलट swings — "pullback" (lower degree), "candidate" (चालू leg, correction ची शक्यता),
      "correction" (पूर्ण झाली ⇒ पुढचा leg तिथून)."""
    from . import daily_legs as DL
    s = S3.load(s)
    d = d.reset_index(drop=True)
    H, L = d["high"].to_numpy(float), d["low"].to_numpy(float)
    nlow = int(s["daily_pivot_n"]) - 1
    low = DD.pivots_pivot(d, nlow, DD.known_at_of(d)) if nlow >= 1 else []
    legs, corrs = [], []
    cur = None
    last = states[-1] if states else None
    tpv = list(last.pivots) if last is not None else []                    # trend-degree pivots (engine चे स्वतःचे)
    for x in states:
        if x.trend not in ("UP", "DOWN") or x.leg_start is None or x.imp_end is None:
            cur = None
            continue
        dirn = 1 if x.trend == "UP" else -1
        key = (x.trend, int(x.leg_start))
        if cur is None or cur["key"] != key:
            lf = getattr(x, "leg_from", None)
            if cur is not None and lf is not None and cur["key"][0] == x.trend:   # ABC_FIX: correction मधले तात्पुरते legs (a-b-c चा
                while len(legs) > 1 and legs[-1]["from"] > lf and legs[-2]["key"][0] == x.trend:   # a / b नंतर सुरू झालेले) correction चाच भाग
                    legs.pop()
                    corrs[:] = [c for c in corrs if c["end_bar"] <= lf]
                cur = legs[-1] if legs else None
            prev = cur if (cur is not None and cur["key"][0] == x.trend and x.leg_start > cur["from"]) else None
            if prev is not None:                                           # जुना leg नव्या origin पर्यंतच: त्याचं टोक त्या मधलं
                a, b = prev["from"], int(x.leg_start)
                if lf is not None and a <= lf < b:
                    j = lf                                                 # counter-move ची सुरुवात (expanded flat चा b नवा टोक असला तरी)
                else:
                    j = a + int(np.argmin(L[a:b + 1]) if prev["dir"] < 0 else np.argmax(H[a:b + 1]))
                prev["to"], prev["p1"] = int(j), float(L[j] if prev["dir"] < 0 else H[j])
            p0 = float(L[x.leg_start] if dirn > 0 else H[x.leg_start])
            cur = {"key": key, "dir": dirn, "from": int(x.leg_start), "to": int(x.imp_end.bar), "p0": p0, "p1": float(x.imp_end.price),
                   "par": None}
            legs.append(cur)
            if prev is not None:                                           # पूर्ण same-degree correction: prev टोक ⇒ नव्या leg चा origin
                corrs.append(_corr(prev, x.leg_start, p0, "done", low, DL, broke_origin=prev["par"] is not None, trend_pv=tpv))
        else:
            cur["to"], cur["p1"] = int(x.imp_end.bar), float(x.imp_end.price)
        if x.counter == "correction" and x.parent is not None:
            cur["par"] = float(x.parent.price)                             # A1: origin तुटला, parent टिकला ⇒ खोली parent पासून
    if cur is not None and last is not None and last.counter in ("candidate", "correction"):
        j = cur["to"] + 1 + int(np.argmax(H[cur["to"] + 1:]) if cur["dir"] < 0 else np.argmin(L[cur["to"] + 1:])) \
            if cur["to"] + 1 < len(d) else cur["to"]
        px = float(H[j] if cur["dir"] < 0 else L[j])
        corrs.append(_corr(cur, j, px, "in progress", low, DL, kind=last.counter, trend_pv=tpv))
    big = [c for c in corrs if c["state"] == "done"]                       # ABC_FIX: तात्पुरती completion (a / b नंतर) नंतर पूर्ण correction
    corrs = [c for c in corrs if not any(o is not c and o["start_bar"] <= c["start_bar"] and o["end_bar"] > c["end_bar"]
                                         for o in big)]                    # मोठ्या box च्या आतला box नाही
    legs = [lg for lg in legs if not any(c["state"] == "done" and c["start_bar"] < lg["from"] < c["end_bar"] for c in corrs)]
    seen = set()
    pv = list(last.pivots) if last is not None else []
    tops = {c["end_bar"] for c in corrs if c["state"] == "done"}
    cand = set(last.corr_bars) if last is not None else set()
    bounces = []
    for lg in legs:
        ok = "H" if lg["dir"] < 0 else "L"
        hi = len(d) - 1 if lg is cur else lg["to"]
        for p in pv:
            if p.kind == ok and lg["from"] < p.bar <= hi and p.bar not in seen:
                seen.add(p.bar)
                tag = "correction" if p.bar in tops else ("candidate" if (lg is cur and p.bar in cand) else "pullback")
                bounces.append({"bar": int(p.bar), "price": float(p.price), "kind": p.kind, "tag": tag})
    out_legs = [{"dir": lg["dir"], "from": lg["from"], "to": lg["to"], "p0": lg["p0"], "p1": lg["p1"]} for lg in legs]
    return {"legs": out_legs, "corrections": corrs, "bounces": bounces}


def _corr(leg, end_bar, end_px, state, low, DL, kind="correction", broke_origin=False, trend_pv=()):
    imp = abs(leg["p1"] - (leg["par"] if leg.get("par") is not None else leg["p0"]))   # A1: parent टिकलेली correction ⇒ parent पासूनचा impulse
    depth = abs(end_px - leg["p1"]) / imp if imp > 0 else None
    prices, bars = _box_waves(leg, end_bar, end_px, trend_pv)              # Abhi item 4: family स्वतःच्या (trend) degree वर — box मधले
    if len(prices) - 1 < 3:                                                # trend-degree swings; ते a-b-c इतकेही नसले तरच एक degree खाली
        prices, bars = _box_waves(leg, end_bar, end_px, low)
    st = DL.structure(prices, elliott=True)
    x3 = DL.reduce_waves(prices).get(3) if len(prices) > 3 else None       # a-b-c reduction ⇒ b टोक (ABC_FIX rule 4: पुढची demand)
    b_px = float(x3[2]) if x3 is not None else None
    b_bar = next((bars[k] for k in range(len(prices) - 1, 0, -1) if b_px is not None and prices[k] == b_px), None)
    shape = st["form"] if st["structure"] != "single" else None
    shape = "5-wave" if shape == "impulse" else shape                     # correction box वर "impulse" शब्द नाही
    return {"start_bar": int(leg["to"]), "start_price": float(leg["p1"]), "end_bar": int(end_bar), "end_price": float(end_px),
            "state": state, "kind": kind, "broke_origin": bool(broke_origin or (kind == "correction" and state == "in progress")), "depth": None if depth is None else round(float(depth), 3), "shape": shape,
            "b_price": b_px, "b_bar": b_bar}


def _box_waves(leg, end_bar, end_px, piv):
    """correction box (leg टोक ⇒ end) मधले आलटून पालटून swings (wick टोक, सलग तोच प्रकार ⇒ जास्त टोकाचा) ⇒ (prices, bars)."""
    inner = sorted((q for q in piv if leg["to"] < q.bar < end_bar), key=lambda q: q.bar)
    prices, kinds, bars = [leg["p1"]], ["L" if leg["dir"] < 0 else "H"], [int(leg["to"])]
    for q in inner:                                                        # आलटून पालटून; सलग तोच प्रकार ⇒ जास्त टोकाचा
        if q.kind != kinds[-1]:
            prices.append(q.price)
            kinds.append(q.kind)
            bars.append(int(q.bar))
        elif len(prices) > 1 and (q.price - prices[-1]) * (1 if q.kind == "H" else -1) > 0:
            prices[-1], bars[-1] = q.price, int(q.bar)
    if len(prices) > 1 and kinds[-1] == ("H" if leg["dir"] < 0 else "L"):
        prices, kinds, bars = prices[:-1], kinds[:-1], bars[:-1]
    prices.append(end_px)
    bars.append(int(end_bar))
    return prices, bars


def _fake_1m(d):
    """Daily bars ⇒ elliott.swings.build_frame("1d") ला चालणारे rows (09:15 OHLC + 15:29 close) — resample ने तोच Daily bar परत."""
    a = d[["timestamp", "open", "high", "low", "close"]].copy()
    a["timestamp"] = a["timestamp"] + pd.Timedelta(hours=9, minutes=15)
    b = d[["timestamp", "close"]].copy()
    b["timestamp"] = b["timestamp"] + pd.Timedelta(hours=15, minutes=29)
    b["open"] = b["high"] = b["low"] = b["close"]
    return pd.concat([a, b[["timestamp", "open", "high", "low", "close"]]]).sort_values("timestamp").reset_index(drop=True)


def elliott_view(d, es=None):
    """Advisory: प्रत्येक degree चा preferred count (pattern, labels [(ts, price, label)], current wave, gray, votes). अपयश ⇒
    {"error": कारण} (गुपचूप नाही). फक्त d मधला data (शेवटच्या Daily close पर्यंत)."""
    from elliott import settings as ES
    from elliott import swings as W
    from elliott.counts import CountEngine
    from elliott.patterns import LABELS
    es = dict(es or ES.DEFAULTS)
    es["degree_tf_mode"] = "fixed"
    es["degree_tf"] = ["1d"] * int(es["degree_levels"])
    asof = d["bar_end"].max()
    try:
        m = _fake_1m(d)
        md = W.multi_degree(m, es, now=asof)
        snap = CountEngine(md, es).snapshot(asof)
    except Exception as exc:                                               # noqa: BLE001 — कारण नोंदीत, chart तरी बनतो
        return {"error": f"{type(exc).__name__}: {str(exc)[:80]}"}
    out = {"degrees": {}}
    for k, v in sorted(snap.degrees.items()):
        n = v.preferred or (v.nodes[0] if v.nodes else None)
        if n is None:
            out["degrees"][f"D{k}"] = {"pattern": None, "gray": bool(v.gray), "pivots": len(md[k]["confirmed"])}
            continue
        names = ["0"] + LABELS[n.pattern]
        labs = [{"ts": str(pd.Timestamp(p.ts).normalize().date()), "price": float(p.price), "label": names[i] if i < len(names) else "?"}
                for i, p in enumerate(n.points)]
        out["degrees"][f"D{k}"] = {"pattern": n.pattern, "direction": int(n.direction), "current_wave": n.current_wave,
                                   "gray": bool(v.gray), "vote_up": None if not np.isfinite(v.vote_up) else round(float(v.vote_up), 3),
                                   "vote_down": None if not np.isfinite(v.vote_down) else round(float(v.vote_down), 3),
                                   "labels": labs, "pivots": len(md[k]["confirmed"])}
    return out


def pick_degree(ev, t0):
    """Window मध्ये ≥ 2 labels असलेली सर्वात मोठी degree (दाखवण्यासाठी); नसेल ⇒ labels असलेली सर्वात मोठी."""
    degs = [(k, v) for k, v in sorted(ev.get("degrees", {}).items(), key=lambda kv: -int(kv[0][1:])) if v.get("labels")]
    for k, v in degs:
        if sum(1 for x in v["labels"] if pd.Timestamp(x["ts"]) >= t0) >= 2:
            return k
    return degs[0][0] if degs else None


def ago(i, n, i0=None):
    if i0 is not None and i < i0:
        return "before the shown window"
    k = n - 1 - i
    return "today" if k == 0 else f"{k} sessions ago"


def build(df, s=None, window=500, es=None, with_elliott=True, sealed=None):
    """पूर्ण history वर दोन थर + elliott ⇒ view dict (chart + JSON साठी). window = दाखवायची शेवटची sessions.
    sealed(ts) ⇒ True असलेल्या तारखा (Q33: NIFTY holdout) engine warm-up मध्ये वापरतो पण output (window, JSON, caption, chart) मध्ये कधीच
    नाहीत: window शेवटच्या sealed row नंतरच सुरू होते."""
    s = S3.load(s)
    d = prepare(df)
    C = d["close"].to_numpy()
    n = len(d)
    minor = DD.fold(d, {**s, "daily_trend_mode": "minor"})
    q15 = DD.fold(d, {**s, "daily_trend_mode": "impulse"})
    i0 = max(0, n - int(window))
    if sealed is not None:
        hit = [j for j in range(n) if sealed(d["timestamp"].iloc[j])]
        if hit:
            i0 = max(i0, hit[-1] + 1)
            if i0 >= n:
                raise ValueError("सगळ्या दाखवायच्या Daily candles sealed (holdout) — chart नाही (Q33)")
    piv = list(q15[-1].pivots)                                             # दोन्ही modes चे pivots एकच (_raw_pivots)
    objs = structure_objects(d, q15, s)
    tags = tag_pivots(piv)
    seg_m, seg_q = protected_segments(minor, C), protected_segments(q15, C)
    prot_m = {(x["kind"], x["bar"]) for x in seg_m}
    prot_q = {(x["kind"], x["bar"]) for x in seg_q}
    ev = elliott_view(d, es) if with_elliott else {"error": "disabled"}
    deg = pick_degree(ev, d["timestamp"].iloc[i0]) if "degrees" in ev else None
    lab_of = {}                                                            # elliott label ⇒ जवळचा (±3 दिवस) engine pivot, एकाच pivot ला एक
    if deg:
        g = "?" if ev["degrees"][deg]["gray"] else ""
        for x in ev["degrees"][deg]["labels"]:
            t = pd.Timestamp(x["ts"])
            cand = [(abs((pd.Timestamp(d["timestamp"].iloc[p.bar]) - t).days), j) for j, p in enumerate(piv)]
            cand = [(dd, j) for dd, j in cand if dd <= 3 and abs(piv[j].price - x["price"]) <= 0.002 * abs(x["price"]) + 1e-9]
            if cand:
                j = min(cand)[1]
                lab_of.setdefault(j, f"({x['label']}){g}" if x["label"] != "0" else f"start{g}")
    pivots = []
    for j, (p, tg) in enumerate(zip(piv, tags)):
        day = str(pd.Timestamp(d["timestamp"].iloc[p.bar]).date())
        pivots.append({"bar": int(p.bar), "day": day, "kind": p.kind, "price": float(p.price), "tag": tg, "confirm_bar": int(p.confirm_bar),
                       "protected_minor": (p.kind, p.bar) in prot_m, "protected_q15": (p.kind, p.bar) in prot_q,
                       "wave_label": lab_of.get(j), "in_window": p.bar >= i0})
    last_m, last_q = minor[-1], q15[-1]
    tm = [x.trend for x in minor]
    tq = [x.trend for x in q15]
    since_m = runs(tm)[-1][0]
    since_q = runs(tq)[-1][0]
    why_m = next((minor[j].why for j in range(since_m, n) if minor[j].why), "") or minor[since_m].why
    v = {
        "n": n, "i0": i0, "first_day": str(d["timestamp"].iloc[0].date()), "last_day": str(d["timestamp"].iloc[-1].date()),
        "frame": d, "pivots": pivots, "legs": [x for x in legs(piv, q15) if x["to"] >= i0],
        "minor": {"bands": runs(tm), "protected": seg_m, "trend": last_m.trend, "since": since_m, "why": why_m,
                  "protected_now": None if last_m.protected is None else {"kind": last_m.protected.kind, "price": last_m.protected.price,
                                                                          "bar": last_m.protected.bar}},
        "q15": {"bands": runs(tq), "protected": seg_q, "trend": last_q.trend, "since": since_q, "phase": last_q.phase, "wave": last_q.wave,
                "corr_label": last_q.corr_label, "mature": bool(last_q.mature), "targets": list(last_q.targets),
                "target_passed": bool(getattr(last_q, "target_passed", False)),
                "protected_now": None if last_q.protected is None else {"kind": last_q.protected.kind, "price": last_q.protected.price,
                                                                        "bar": last_q.protected.bar},
                "phases": runs([(x.phase or "-") + "|" + (x.wave or "") for x in q15]),
                "counter": last_q.counter, "origin_risk": bool(last_q.origin_risk), "band": last_q.band,
                "parent": None if last_q.parent is None else {"kind": last_q.parent.kind, "price": last_q.parent.price, "bar": last_q.parent.bar},
                "states": runs([state_label(x) for x in q15]), "objects": objs,
                "retrace": _retrace(d, last_q), "range_check": range_check(d, objs, s),
                "sharp_end": getattr(last_q, "corr_zone", None), "evidence": list(getattr(last_q, "evidence", ()) or ()),
                **_after_correction(last_q, objs, float(d["close"].iloc[-1]))},
        "elliott": ev, "elliott_degree": deg, "sealed": sealed,
    }
    v["q15"]["levels"] = level_bands(v, s)
    return v


def range_check(d, objs, s=None):
    """B1 (Abhi): Q27 RANGE चाचणी trend-degree रचनेवर — शेवटचे दोन trend-degree lows (UP leg origin / DOWN leg टोक) आणि दोन highs;
    tol = range_eq_sigma_d × σ_D (शेवटचा). फक्त अहवाल (engine चा RANGE नियम बदलत नाही; tune नाही)."""
    s = S3.load(s)
    lows, highs = [], []
    for lg in objs["legs"]:
        a = (lg["from"], lg["p0"]) if lg["dir"] > 0 else (lg["to"], lg["p1"])
        b = (lg["to"], lg["p1"]) if lg["dir"] > 0 else (lg["from"], lg["p0"])
        lows.append(a)
        highs.append(b)
    lows = sorted(set(lows))[-2:]
    highs = sorted(set(highs))[-2:]
    sig = DD.sigma_d(d.reset_index(drop=True), int(s["daily_sigma_sessions"]))
    tol = float(s["range_eq_sigma_d"]) * float(sig[-1]) if len(sig) and np.isfinite(sig[-1]) else 0.0
    eq = lambda xs: len(xs) == 2 and abs(xs[0][1] - xs[1][1]) <= tol   # noqa: E731
    return {"tol": round(tol, 2), "lows": [{"bar": int(b), "price": float(p)} for b, p in lows],
            "highs": [{"bar": int(b), "price": float(p)} for b, p in highs],
            "lows_equal": bool(eq(lows)), "highs_equal": bool(eq(highs)), "range": bool(eq(lows) and eq(highs))}


MAX_BANDS = 6                                                              # C1 (Abhi): Daily chart वर कमाल 6 level पट्टे


def _after_correction(st, objs, last_close=None):
    """ABC_FIX rule 4 / 5: चालू impulse leg ज्या (पूर्ण) correction नंतर सुरू झाला ती — family आणि तिच्या आतला b टोक (same-degree
    pivot, DOWN ⇒ सर्वात खालचा L = पुढची demand / target; UP आरसा). नसेल ⇒ None."""
    out = {"last_corr_shape": None, "next_level": None, "rule5": False}
    if st.trend not in ("UP", "DOWN") or st.leg_start is None:
        return out
    done = [c for c in objs.get("corrections", []) if c["state"] == "done" and c["end_bar"] == st.leg_start]
    if not done:
        return out
    c = done[-1]
    kind = "L" if st.trend == "DOWN" else "H"
    out["last_corr_shape"] = c.get("shape")
    b_px, b_bar = c.get("b_price"), c.get("b_bar")                         # a-b-c reduction चा b (एक degree खालचे pivots)
    if b_px is not None and b_bar is not None:
        ahead = last_close is None or ((b_px < last_close) if kind == "L" else (b_px > last_close))
        if ahead:                                                          # किंमत आधीच पलीकडे close झाली ⇒ "पुढची" demand / supply नाही
            out["next_level"] = {"price": float(b_px), "bar": int(b_bar)}
    out["rule5"] = st.phase == "impulse" and st.counter in (None, "pullback") and getattr(st, "corr_zone", None) is not None
    return out


def level_bands(v, s=None):
    """C1 (Abhi): महत्त्वाची levels पट्टे म्हणून — degree आधी, मग किंमतीपासून जवळीक; कमाल MAX_BANDS. उमेदवार (rank = degree):
    0 मोठ्या degree चा origin (parent, window बाहेर असला तरी — कडेला बाण), 1 protected origin + sharp-fall / rise zone (ABC_FIX
    rule 2), 2 पुढची demand / supply (b टोक, rule 4), 3 window चे major टोक (high / low), 4 structural target (Q44: parent origin
    नंतरच्या पहिल्या impulse leg चं टोक), 5 trend-degree correction टोकं. पट्टा = किंमत ±
    range_eq_sigma_d × σ_D. State: fresh / tested / broken (birth नंतरचे closes / ranges); target ⇒ "target"."""
    s = S3.load(s)
    d = v["frame"]
    C, Hh, Ll = d["close"].to_numpy(float), d["high"].to_numpy(float), d["low"].to_numpy(float)
    n, i0 = v["n"], v["i0"]
    q = v["q15"]
    sig = DD.sigma_d(d, int(s["daily_sigma_sessions"]))
    half = max(float(s["range_eq_sigma_d"]) * (float(sig[-1]) if np.isfinite(sig[-1]) else 0.0), 1e-9)
    cand = []
    if q.get("parent") and (not q.get("protected_now") or abs(q["parent"]["price"] - q["protected_now"]["price"]) > 1e-9):
        cand.append((0, "larger-degree origin", q["parent"]["price"], q["parent"]["bar"]))
    if q.get("protected_now"):
        cand.append((1, "protected origin", q["protected_now"]["price"], q["protected_now"]["bar"]))
    dn = q.get("trend") == "DOWN"
    zone = None
    if q.get("sharp_end"):                                                 # ABC_FIX rule 2: sharp-fall supply / sharp-rise demand (उच्च rank)
        zone = q["sharp_end"]
        cand.append((1, "sharp-fall supply" if dn else "sharp-rise demand", (zone[0] + zone[1]) / 2, int(zone[2])))
    if q.get("next_level"):                                                # rule 4: correction चा b टोक = पुढची demand / supply
        cand.append((2, "next demand (b low)" if dn else "next supply (b high)", q["next_level"]["price"], q["next_level"]["bar"]))
    win_h = i0 + int(np.argmax(Hh[i0:]))
    win_l = i0 + int(np.argmin(Ll[i0:]))
    cand += [(3, "window high", float(Hh[win_h]), win_h), (3, "window low", float(Ll[win_l]), win_l)]
    for x in q.get("targets") or ():                                       # rule 5 च्या पट्ट्यांनंतर (Q44: फक्त रचनेतला target)
        cand.append((4, "target", float(x), None))
    for c in (q.get("objects") or {}).get("corrections", []):
        if c["end_bar"] >= i0 and c["state"] == "done":
            cand.append((5, "correction end", c["end_price"], c["end_bar"]))
    out = []
    for rank, label, px, bar in sorted(cand, key=lambda x: (x[0], x[1].startswith("sharp-"), abs(x[2] - C[-1]))):
        hit = [b for b in out if b["lo"] - half <= px <= b["hi"] + half]
        if hit:                                                            # आधीच्या (वरच्या degree) पट्ट्यात ⇒ नवा नाही; sharp zone ⇒ नाव जोडा
            if label.startswith("sharp-"):
                hit[0]["label"] += f" · {label}"
            continue
        lo, hi = (min(zone[0], px - half), max(zone[1], px + half)) if label.startswith("sharp-") else (px - half, px + half)   # zone ची
                                                                           # खरी कडा (किमान ± half)
        if bar is None:
            state = "target"
        else:
            after = slice(int(bar) + 1, n)
            above_now = C[-1] > hi
            crossed = bool(((C[after] < lo) if above_now else (C[after] > hi)).any()) if C[-1] > hi or C[-1] < lo else False
            touched = bool(((Ll[after] <= hi) & (Hh[after] >= lo)).any())
            state = "broken" if crossed else ("tested" if touched else "fresh")
        wlo, whi = float(Ll[i0:].min()), float(Hh[i0:].max())
        off = "above" if lo > whi else ("below" if hi < wlo else None)
        out.append({"rank": rank, "label": label, "price": round(float(px), 2), "lo": round(lo, 2), "hi": round(hi, 2), "state": state,
                    "bar": None if bar is None else int(bar), "off_window": off})
        if len(out) >= MAX_BANDS:
            break
    return out


def view_spec(v):
    """C1: default Daily chart वर काय काढायचं (फक्त trend-degree) — chart आणि tests याच spec वरून. tags = chart वरचे सगळे degree
    labels (correction boxes + current impulse मधले pullbacks); minor pivot tags / Elliott labels इथे नाहीत (debug chart मध्ये)."""
    i0 = v["i0"]
    ob = v["q15"]["objects"]
    legs = [lg for lg in ob["legs"] if lg["to"] >= i0]
    boxes = []
    for c in ob["corrections"]:
        if c["end_bar"] < i0:
            continue
        name = "correction candidate" if (c["state"] == "in progress" and c["kind"] == "candidate") else "correction"
        bits = [name + (" (in progress)" if c["state"] == "in progress" else "")]
        if c.get("depth") is not None:
            bits.append(f"{c['depth']:.0%} of impulse")
        if c.get("shape"):
            bits.append(c["shape"])
        boxes.append({**c, "label": " · ".join(bits)})
    cur = ob["legs"][-1] if ob["legs"] else None
    boxed = {c["end_bar"] for c in boxes}
    pulls = [b for b in ob["bounces"] if cur is not None and b["bar"] > cur["from"] and b["bar"] >= i0 and b["bar"] not in boxed
             and b["tag"] in ("pullback", "candidate") and v["q15"]["trend"] in ("UP", "DOWN")]
    tags = [b["label"] for b in boxes] + [b["tag"] for b in pulls]
    return {"legs": legs, "boxes": boxes, "pullbacks": pulls, "tags": tags, "bands": v["q15"].get("levels") or [],
            "protected": v["q15"].get("protected_now"), "strip": {"degree-aware": v["q15"]["states"], "Dow minor": v["minor"]["bands"]}}


def state_label(st):
    """C1 पट्टा (trader वाचतो ती अवस्था): "DOWN · impulse" / "DOWN · correction" / "RANGE" / "NEUTRAL" / "UNKNOWN"."""
    if st.trend in ("UP", "DOWN"):
        return f"{st.trend} · {'impulse' if st.phase == 'impulse' else 'correction'}"
    return st.trend


def _retrace(d, st):
    """चालू correction किती खोल: (leg टोक − correction चं टोक) ÷ (leg टोक − protected origin); impulse मध्ये ⇒ None."""
    if st is None or st.trend not in ("UP", "DOWN") or st.imp_end is None or st.protected is None or st.counter is None:
        return None
    j0 = st.imp_end.bar
    seg = d["high"].to_numpy(float)[j0:] if st.trend == "DOWN" else d["low"].to_numpy(float)[j0:]
    ext = float(seg.max() if st.trend == "DOWN" else seg.min())
    org = st.protected.price if st.counter != "correction" else (st.parent.price if st.parent is not None else st.protected.price)
    span = abs(st.imp_end.price - org)
    return round(abs(ext - st.imp_end.price) / span, 3) if span > 0 else None


COUNTER_TXT = {"pullback": "pullback in progress (lower degree)", "candidate": "same-degree correction candidate in progress",
               "correction": "correction in progress (same degree; parent origin holds)"}


def trend_line(q):
    """A4 (Abhi): एक ओळ — "Trend DOWN (impulse) · pullback in progress (lower degree) · protected 24,774"."""
    t = q["trend"]
    if t not in ("UP", "DOWN"):
        return f"Trend {t}" + (f" · band {q['band'][0]:,.0f}–{q['band'][1]:,.0f}" if q.get("band") else "")
    if q["phase"] == "origin_broken":
        body = f"Trend {t} · origin broken on close — waiting for an opposite impulse"
    else:
        body = f"Trend {t} ({'impulse' if q['phase'] == 'impulse' else 'correction'})"
        if q.get("counter"):
            body += f" · {COUNTER_TXT[q['counter']]}"
            if q.get("retrace") is not None:
                body += f" (depth {q['retrace']:.0%} of last impulse)"
    r5 = bool(q.get("rule5")) and q["phase"] == "impulse" and q.get("counter") in (None, "pullback")
    if r5:                                                                 # ABC_FIX rule 5 (फक्त नवा impulse चालू असताना; नवी correction ⇒ नाही)
        fam = q.get("last_corr_shape")
        fam = "a-b-c" if fam in ("zigzag", "flat") else (fam or "")
        body = (f"Trend {t} · {fam + ' ' if fam else ''}correction completed at sharp-{'fall supply' if t == 'DOWN' else 'rise demand'}"
                f" · new impulse {t.lower()} in progress")
    pq = q["protected_now"]
    if pq:
        body += f" · protected {pq['price']:,.0f}"
    if q.get("next_level") and r5:
        body += f" · next {'demand' if t == 'DOWN' else 'supply'} {q['next_level']['price']:,.0f}"
    if q["phase"] != "origin_broken":                                     # Q44: target = पहिल्या impulse leg चं टोक; नसेल ⇒ स्पष्ट none
        tg = q.get("targets") or ()                                        # (protected आधीच पलीकडे ⇒ "target passed", रचना अपूर्ण नाही)
        body += f" · target {tg[0]:,.0f}" if tg else (" · target passed" if q.get("target_passed") else
                                                       " · target: none (structure incomplete)")
    if q["mature"]:
        body += " · impulse mature, larger reversal possible"
    if q.get("origin_risk"):
        body += " · origin at risk"
    return body


WITH_WAVES = {"1", "3", "5", "A", "C", "W", "Y", "Z", "E"}                # pattern दिशेने चालणाऱ्या waves (बाकी उलट)


def elliott_vs_dow(v):
    """A5 (Abhi): elliott advisory वि. degree-aware Dow — चालू wave ची दिशा trend शी जुळते का, आणि रचना (impulse / corrective) phase
    शी. रिटर्न {"elliott", "dow", "direction_agree", "structure_agree"} — advisory उपयोगी आहे का हे पाहण्यासाठी log (निर्णयात नाही)."""
    q = v["q15"]
    dow = trend_line(q).split(" · protected")[0]
    deg = v.get("elliott_degree")
    if not deg:
        return {"elliott": v["elliott"].get("error") or "no count", "dow": dow, "direction_agree": None, "structure_agree": None}
    e = v["elliott"]["degrees"][deg]
    cw = str(e.get("current_wave") or "").strip("()").upper()
    move = int(e.get("direction") or 0) * (1 if cw in WITH_WAVES else -1)
    tdir = {"UP": 1, "DOWN": -1}.get(q["trend"], 0)
    e_imp = e.get("pattern") in ("impulse", "lead_diag", "end_diag") and cw in {"1", "3", "5"}
    d_imp = q["phase"] == "impulse"
    return {"elliott": f"{deg} {e['pattern']} wave {e['current_wave']}" + (" ?" if e.get("gray") else ""), "dow": dow,
            "direction_agree": None if tdir == 0 or move == 0 else bool(move == tdir),
            "structure_agree": None if tdir == 0 else bool(e_imp == d_imp)}


def caption(v, symbol, audit_line=None, years=None):
    """≤ 7 ओळी (English) — audit ओळ धरून."""
    n = v["n"]
    m, q = v["minor"], v["q15"]
    shown = n - v["i0"]
    w0 = v["i0"] if v.get("sealed") is not None else None                 # Q33: sealed काळातली सुरुवात ⇒ "window आधी" (तारीख / मोजणी नाही)
    span = f"last {years}y" if years and v.get("full_window", True) else f"{shown} sessions"
    pm = m["protected_now"]
    lab = "—"
    if v.get("elliott_degree"):
        e = v["elliott"]["degrees"][v["elliott_degree"]]
        lab = f"{v['elliott_degree']} {e['pattern']} wave {e['current_wave']}" + (" ? (weak vote)" if e["gray"] else "")
    elif v["elliott"].get("error"):
        lab = f"NA ({v['elliott']['error'][:40]})"
    why = _en(m["why"])
    lines = [
        f"{symbol} · Daily · {span} (engine on full history)",
        trend_line(q) + f" · since {ago(q['since'], n, w0)}",
        f"Dow minor swings (secondary): {m['trend']} since {ago(m['since'], n, w0)}" + (f" — {why}" if why else "")
        + f" · minor protected {_pv(pm, m['trend'] == 'NEUTRAL')}",
        f"Elliott advisory (not used in decisions): {lab}",
    ]
    if audit_line:
        lines.append(audit_line)
    lines.append("Visual review only — no trade, no order")
    return "\n".join(lines[:7])


def _pv(p, broken=False):
    if not p:
        return "—"
    return f"{'H' if p['kind'] == 'H' else 'L'} {p['price']:,.0f}" + (" (broken)" if broken else "")


def _en(why):
    """Engine च्या Marathi why ⇒ छोटं English (chart / caption English)."""
    w = str(why or "")
    if not w:
        return ""
    if "LH + LL" in w:
        return "new LH + LL"
    if "HH + HL" in w:
        return "new HH + HL"
    if "LH" in w and ("low" in w or "खाली" in w):
        return "LH + close below prior low"
    if "HL" in w and ("वर" in w or "high" in w):
        return "HL + close above prior high"
    if "तुटला" in w:
        return "protected swing broke on daily close"
    if "range" in w.lower():
        return "range"
    return ""


def to_json(v, symbol):
    """Chart वर जे काढलं तेच (pivots, legs, states, labels) — frame नाही."""
    d, i0 = v["frame"], v["i0"]
    sealed = v.get("sealed")

    def day(i, clip=False):
        """Q33: sealed (NIFTY holdout) तारीख output मध्ये कधीच नाही ⇒ "before window"; clip ⇒ window सुरुवातीपर्यंत आणतो."""
        i = max(int(i), i0) if clip else int(i)
        if sealed is not None and i < i0:
            return "before window"
        return str(d["timestamp"].iloc[i].date())
    band = lambda r: [{"from": day(a, True), "to": day(b), "state": s} for a, b, s in r if b >= i0]   # noqa: E731
    seg = lambda xs: [{**x, "pivot_day": day(x["bar"]), "from_day": day(x["from"], True), "to_day": day(x["to"])} for x in xs   # noqa: E731
                      if x["to"] >= i0]
    ev = v["elliott"]
    if sealed is not None and isinstance(ev, dict) and "degrees" in ev:   # Q33: sealed तारखांचे elliott labels output मध्ये नाहीत
        ev = {**ev, "degrees": {k: {**g, "labels": [x for x in g.get("labels", []) if not sealed(x["ts"])]}
                                for k, g in ev["degrees"].items()}}
    first = v["first_day"] if sealed is None else day(0)
    return {"symbol": symbol, "timeframe": "1D", "window": {"from": day(i0), "to": v["last_day"]},
            "history": {"from": first, "to": v["last_day"], "bars": v["n"]},
            "pivots": [p for p in v["pivots"] if p["in_window"]],
            "legs": [{**x, "from_day": day(x["from"]), "to_day": day(x["to"])} for x in v["legs"]],
            "minor": {"trend": v["minor"]["trend"], "since": day(v["minor"]["since"]), "bands": band(v["minor"]["bands"]),
                      "protected": seg(v["minor"]["protected"]), "protected_now": v["minor"]["protected_now"]},
            "q15": {"trend": v["q15"]["trend"], "since": day(v["q15"]["since"]), "phase": v["q15"]["phase"], "leg_index_debug": v["q15"]["wave"],
                    "mature": v["q15"]["mature"], "targets": v["q15"]["targets"], "bands": band(v["q15"]["bands"]),
                    "protected": seg(v["q15"]["protected"]), "protected_now": v["q15"]["protected_now"],
                    "phases": [{"from": day(a, True), "to": day(b), "phase_wave": s} for a, b, s in v["q15"]["phases"] if b >= i0]},
            "elliott": ev, "elliott_degree": v["elliott_degree"],
            "trend_line": trend_line(v["q15"]), "counter": v["q15"].get("counter"), "origin_risk": v["q15"].get("origin_risk"),
            "retrace": v["q15"].get("retrace"),
            "parent": None if not v["q15"].get("parent") else {**v["q15"]["parent"], "day": day(v["q15"]["parent"]["bar"])},
            "objects": _objects_json(v, day), "bands": [{**b, "day": None if b["bar"] is None else day(b["bar"])}
                                                        for b in v["q15"].get("levels") or []],
            "range_check": _range_json(v, day),
            "note": "Visual review only — no trade, no order. Engine numbers from data."}


def _objects_json(v, day):
    """C1 objects (window ला लागणारे) — bars ⇒ दिवस (Q33: sealed ⇒ "before window")."""
    ob, i0 = v["q15"].get("objects") or {"legs": [], "corrections": [], "bounces": []}, v["i0"]
    return {"legs": [{**x, "from_day": day(x["from"]), "to_day": day(x["to"])} for x in ob["legs"] if x["to"] >= i0],
            "corrections": [{**x, "start_day": day(x["start_bar"]), "end_day": day(x["end_bar"])} for x in ob["corrections"]
                            if x["end_bar"] >= i0],
            "bounces": [{**x, "day": day(x["bar"])} for x in ob["bounces"] if x["bar"] >= i0]}


def _range_json(v, day):
    rc = v["q15"].get("range_check")
    if not rc:
        return None
    return {**rc, "lows": [{**x, "day": day(x["bar"])} for x in rc["lows"]], "highs": [{**x, "day": day(x["bar"])} for x in rc["highs"]]}
