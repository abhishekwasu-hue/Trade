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
    upto = len(d) - 1                                                      # chart चा शेवटचा bar — त्यानंतर confirm होणारे pivots नाहीत
    live = last is not None and last.trend in ("UP", "DOWN") and last.phase == "impulse" and last.counter in (None, "pullback")
    out_legs = [{"dir": lg["dir"], "from": lg["from"], "to": lg["to"], "p0": lg["p0"], "p1": lg["p1"]} for lg in legs]
    return {"legs": out_legs, "corrections": corrs, "bounces": bounces,
            "impulses": trend_impulses(out_legs, corrs, tpv, low, upto, live and bool(legs) and legs[-1] is cur,
                                       int(s["chart_leg_path_points"]))}


def trend_impulses(legs, corrs, trend_pv, low, upto, live=False, max_points=15):
    """Abhi review (chart, trend degree): engine चे एकाच दिशेचे सलग sub-legs (मधली correction origin तोडत नाही — A1 नाही) = एकच
    trend-degree impulse. सीमा: दिशा बदल किंवा A1 correction (broke_origin). Trend उलटल्यावरचा पहिला impulse आधीच्या उलट leg च्या टोकापासून
    (उदा. Feb top) — मधे box नसेल तर. प्रत्येक impulse वर leg_check (संपूर्ण leg, एक degree खालचे pivots); शेवटचा live ⇒ in progress.
    Engine चे आतले sub-legs = आतल्या waves (chart वर वेगळे legs नाहीत). Fold बदल नाही."""
    a1 = [c for c in corrs if c["state"] == "done" and c.get("broke_origin")]
    groups = []
    for k, lg in enumerate(legs):
        if groups:
            p = legs[k - 1]
            if p["dir"] != lg["dir"] or any(p["to"] <= c["start_bar"] and c["end_bar"] <= lg["from"] for c in a1):
                groups.append([k])
                continue
            groups[-1].append(k)
        else:
            groups.append([k])
    out = []
    for gi, g in enumerate(groups):
        first, dirn = legs[g[0]], legs[g[0]]["dir"]
        a_bar, a_px = first["from"], first["p0"]
        if g[0] > 0:
            p = legs[g[0] - 1]
            boxed = any(p["to"] <= c["start_bar"] and c["end_bar"] <= first["from"] for c in corrs if c["state"] == "done")
            if p["dir"] != dirn and not boxed and (p["p1"] - a_px) * dirn <= 0:   # trend उलटला ⇒ आधीच्या टोकापासून
                a_bar, a_px = p["to"], p["p1"]
        end = (max if dirn > 0 else min)((legs[k] for k in g), key=lambda x: x["p1"])
        prog = bool(live and gi == len(groups) - 1)
        leg = {"dir": dirn, "from": int(a_bar), "to": int(end["to"]), "p0": float(a_px), "p1": float(end["p1"])}
        out.append({**leg, "sub_legs": len(g), **leg_check(leg, trend_pv, low, upto, prog, max_points)})
    return out


def leg_check(lg, trend_pv, low, upto, in_progress=False, max_points=15):
    """Abhi review (chart): trend leg खरा impulse आहे का — leg च्या स्वतःच्या (एक degree खालच्या) pivots वर read_counter; pivots
    confirm_bar ≤ upto (look-ahead नाही). आधी engine चे trend-degree pivots (leg च्या आत), ते 3 waves इतकेही नसले तरच आणखी एक degree
    खाली. pivots = ते सगळे बिंदू; path = त्यांतले मोठे swings (≤ max_points, chart रेषा). verified ⇔ impulse / diagonal. style: "impulse"
    किंवा "unconfirmed" — structure-only तपासणी trend leg ला कधीच corrective म्हणत नाही (Abhi review; reader2 anatomy पुढे); family + n
    audit साठी JSON / Vision facts मध्ये. Engine ची phase / trend बदलत नाही — फक्त दाखवणं."""
    from . import daily_legs as DL
    prices, bars = _leg_waves(lg, trend_pv, upto)
    if len(prices) - 1 < 3:
        prices, bars = _leg_waves(lg, low, upto)
    fam = DL.read_counter(prices)["family"] if len(prices) > 2 else "single"
    ok = fam in DL.MOTIVE
    n = len(prices) - 1
    path = coarse_path(list(zip(bars, prices)), max_points)
    # Abhi review: structure-only तपासणी Abhi च्या count शी नेहमी जुळत नाही (candle anatomy — reader2 — पुढे) ⇒ trend leg ला कधीच
    # "corrective / not an impulse" म्हणत नाही: impulse / diagonal ⇒ "impulse", बाकी ⇒ "unconfirmed" (family + n audit साठी)
    return {"path": [[int(b), float(p)] for b, p in path], "pivots": [[int(b), float(p)] for b, p in zip(bars, prices)],
            "family": fam, "n": int(n), "verified": bool(ok),
            "state": "in progress" if in_progress else "done", "style": "impulse" if ok else "unconfirmed"}


def coarse_path(pts, max_points=15):
    """[(bar, price)] आलटून पालटून ⇒ कमाल max_points बिंदू: सर्वात लहान आतल्या जोड्या गाळून (daily_legs.reduce_counted — टोकं तीच,
    उरलेले बिंदू मूळ pivots च)."""
    from . import daily_legs as DL
    mp = max(int(max_points), MIN_PATH_POINTS)                             # register: chart_leg_path_points ≥ 6
    if len(pts) <= mp or len(pts) < 3:
        return list(pts)
    red = DL.reduce_counted([p for _, p in pts])
    k = max((m for m in red if m + 1 <= mp), default=None)
    if k is None:                                                          # reduce_counted लवकर थांबला ⇒ गाळता येत नाही, जसे आहे तसे
        return list(pts)
    ends = [0] + [sum(red[k][1][:j + 1]) for j in range(len(red[k][1]))]
    return [pts[e] for e in ends]


MIN_PATH_POINTS = 6


def _leg_waves(lg, piv, upto):
    """Leg (origin ⇒ टोक) मधले आलटून पालटून confirmed pivots (confirm_bar ≤ upto; सलग तोच प्रकार ⇒ जास्त टोकाचा) ⇒ (prices, bars)."""
    k0, k1 = ("L", "H") if lg["dir"] > 0 else ("H", "L")
    inner = sorted((q for q in piv if lg["from"] < q.bar < lg["to"] and q.confirm_bar <= upto), key=lambda q: q.bar)
    prices, kinds, bars = [float(lg["p0"])], [k0], [int(lg["from"])]
    for q in inner:
        if q.kind != kinds[-1]:
            prices.append(float(q.price))
            kinds.append(q.kind)
            bars.append(int(q.bar))
        elif len(prices) > 1 and (q.price - prices[-1]) * (1 if q.kind == "H" else -1) > 0:
            prices[-1], bars[-1] = float(q.price), int(q.bar)
    if len(prices) > 1 and kinds[-1] == k1:                                # शेवटचा आतला pivot leg-दिशेचा ⇒ टोकाशी merge
        prices, kinds, bars = prices[:-1], kinds[:-1], bars[:-1]
    prices.append(float(lg["p1"]))
    bars.append(int(lg["to"]))
    return prices, bars


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
    _, ends = DL.wave_ends(prices) if len(prices) > 2 else (None, [])      # Abhi review: family ज्या pivots वरून वाचलं तिथे a / b / c …
    if state == "in progress":
        ends = [(k, w) for k, w in ends if k < len(prices) - 1]            # चालू wave (आजच्या टोकापर्यंत) ला अक्षर नाही
    marks = [{"bar": int(bars[k]), "price": float(prices[k]), "letter": w, "kind": "H" if prices[k] > prices[k - 1] else "L"}
             for k, w in ends]
    return {"start_bar": int(leg["to"]), "start_price": float(leg["p1"]), "end_bar": int(end_bar), "end_price": float(end_px),
            "state": state, "kind": kind, "broke_origin": bool(broke_origin or (kind == "correction" and state == "in progress")), "depth": None if depth is None else round(float(depth), 3), "shape": shape,
            "b_price": b_px, "b_bar": b_bar, "wave_prices": [float(x) for x in prices], "wave_bars": [int(b) for b in bars],
            "marks": marks}


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


def build(df, s=None, window=500, es=None, with_elliott=True, sealed=None, symbol=None, accepted=None):
    """पूर्ण history वर दोन थर + elliott ⇒ view dict (chart + JSON साठी). window = दाखवायची शेवटची sessions.
    CD14: symbol ⇒ Abhi ने स्वीकारलेली वाचनं (`accepted_legs.load`) trend legs वर (`accepted`); accepted = नोंदींची list ⇒ त्याच
    (tests; symbol नसला तरी). दोन्ही नाहीत ⇒ कोणतंही स्वीकारलेलं वाचन नाही.
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
    mark_accepted(objs["impulses"], d["timestamp"], s, symbol, accepted)
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
                "rev": None if getattr(last_q, "rev", None) is None else {"kind": last_q.rev[0].kind, "price": last_q.rev[0].price,
                                                                          "beyond": last_q.rev[1].price},
                "parent": None if last_q.parent is None else {"kind": last_q.parent.kind, "price": last_q.parent.price, "bar": last_q.parent.bar},
                "states": runs([state_label(x) for x in q15]), "objects": objs,
                "leg_now": next(({k: lg.get(k) for k in ("state", "verified", "family", "n", "accepted", "anatomy")}
                                 for lg in objs["impulses"][-1:] if lg["state"] == "in progress"), None),
                "leg_last": next(({k: lg.get(k) for k in ("state", "verified", "family", "n", "accepted", "anatomy", "dir")}
                                  for lg in objs["impulses"][-1:]), None),   # PR #304: chart वरचा शेवटचा trend leg (चालू / पूर्ण)
                "retrace": _retrace(d, last_q), "range_check": range_check(d, objs, s),
                "sharp_end": getattr(last_q, "corr_zone", None), "evidence": list(getattr(last_q, "evidence", ()) or ()),
                "wave_a": _wave_a(last_q), "alt": getattr(last_q, "alt", None),
                **_after_correction(last_q, objs, float(d["close"].iloc[-1]))},
        "elliott": ev, "elliott_degree": deg, "sealed": sealed,
    }
    v["s"] = s
    v["q15"]["levels"] = level_bands(v, s)
    return v


def mark_accepted(impulses, ts, s=None, symbol=None, accepted=None):
    """CD14: प्रत्येक trend-degree leg वर `accepted` (Abhi ची जुळलेली नोंद किंवा None) + `drawn_as` (default chart वर काय: "impulse" ⇔
    read_counter impulse / diagonal किंवा स्वीकारलेलं वाचन; नाहीतर "trend leg") + `check` (debug / JSON चा पूर्ण तपशील). जुळवणं फक्त
    pivot तारखांवरून, ± daily_pivot_n sessions (`accepted_legs`)."""
    from . import accepted_legs as AL
    s = S3.load(s)
    if accepted is not None:
        recs = [AL.validate(r) for r in accepted]
        if symbol is not None:
            recs = [r for r in recs if r["symbol"] == str(symbol).upper()]
    else:
        try:
            recs = AL.load(symbol=symbol) if symbol else []
        except (OSError, ValueError) as e:                                 # PR #304: नोंदींची file चुकीची ⇒ chart / Telegram थांबत नाही
            AL.log.warning("accepted legs unreadable (%s) — chart drawn without accepted readings", e)
            recs = []
    AL.annotate(impulses, recs, ts, int(s["daily_pivot_n"]))
    for lg in impulses:
        lg.setdefault("anatomy", None)
        lg["drawn_as"] = drawn_as(lg)
        lg["check"] = leg_check_text(lg)
    return impulses


def drawn_as(lg):
    """Default / Telegram chart वरचं नाव: verified (5 waves) किंवा Abhi ने स्वीकारलेलं ⇒ "impulse"; बाकी ⇒ "trend leg" (impulse दावा नाही,
    "not verified" मजकूर नाही — CD14)."""
    return "impulse" if lg.get("verified") or lg.get("accepted") else "trend leg"


def _anatomy_txt(a):
    """reader2 anatomy vote (असेल तर): {"lean", "score"} ⇒ "impulsive +0.42"; नाही ⇒ "not run" (हा chart reader2 चालवत नाही)."""
    if not a:
        return "not run"
    sc = a.get("score")
    return f"{a.get('lean') or '?'}" + ("" if sc is None else f" {sc:+.2f}")


def leg_check_text(lg):
    """Debug / JSON (CD14): पूर्ण तपासणी — "impulse (5 waves; structure vote: impulse, n 5)" किंवा "impulse not verified (structure vote:
    zigzag, n 9; anatomy vote: not run)" + स्वीकारलेलं असेल ⇒ " · accepted by Abhi as impulse (source)". Default chart वर हा मजकूर नाही."""
    sv = f"structure vote: {lg.get('family')}, n {lg.get('n')}"
    if lg.get("verified"):
        txt = f"impulse (5 waves; {sv})"
    else:
        txt = f"impulse not verified ({sv}; anatomy vote: {_anatomy_txt(lg.get('anatomy'))})"
    acc = lg.get("accepted")
    if acc:
        txt += f" · accepted by Abhi as {acc['reading']} (source: {acc['source']})"
    return txt


def _wave_a(st):
    """Q49: A1 correction चा 5-wave पहिला पाय (default wave A) — chart label "A"; पर्यायी count ("1") फक्त debug (alt)."""
    a = getattr(st, "wave_a", None)
    if a is None:
        return None
    return {"kind": a.kind, "price": float(a.price), "bar": int(a.bar), "label": "A"}


def range_check(d, objs, s=None):
    """B1 (Abhi): Q27 RANGE चाचणी trend-degree रचनेवर — शेवटचे दोन trend-degree lows (UP leg origin / DOWN leg टोक) आणि दोन highs.
    "Equal" = C-13 (Abhi L1-b, the reading's own definition — `daily.c13_equal`): the later extreme reaches the earlier swing candle's
    area (wick to body) and does not go beyond it — no σ tolerance (layer 6b). फक्त अहवाल (engine चा RANGE नियम बदलत नाही)."""
    lows, highs = [], []
    for lg in objs["legs"]:
        a = (lg["from"], lg["p0"]) if lg["dir"] > 0 else (lg["to"], lg["p1"])
        b = (lg["to"], lg["p1"]) if lg["dir"] > 0 else (lg["from"], lg["p0"])
        lows.append(a)
        highs.append(b)
    lows = sorted(set(lows))[-2:]
    highs = sorted(set(highs))[-2:]
    O, C = d["open"].to_numpy(float), d["close"].to_numpy(float)

    def eq(xs, kind):
        return len(xs) == 2 and DD.c13_equal(O, C, xs[1][1], kind, int(xs[0][0]), xs[0][1])
    return {"rule": "C-13: the later extreme reaches the earlier swing candle's area (wick to body), not beyond",
            "lows": [{"bar": int(b), "price": float(p)} for b, p in lows], "highs": [{"bar": int(b), "price": float(p)} for b, p in highs],
            "lows_equal": bool(eq(lows, "L")), "highs_equal": bool(eq(highs, "H")), "range": bool(eq(lows, "L") and eq(highs, "H"))}


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


def level_bands(v, s=None, limit=MAX_BANDS, max_broken=1):
    """C1 / §5.4 (Abhi): महत्त्वाची levels पट्टे म्हणून — degree आधी, मग किंमतीपासून जवळीक; कमाल `limit` (None ⇒ सगळे, full view).
    उमेदवार (rank = degree): 0 मोठ्या degree चा origin (parent, window बाहेर असला तरी — कडेला बाण), 1 protected origin + sharp-fall
    supply / sharp-rise demand, 2 रचना ज्या major टोकावर उभी (शेवटच्या पूर्ण same-degree correction ची सुरुवात = आधीच्या impulse चं
    टोक; उदा. BANKNIFTY चा March low) + b टोक (पुढची demand / supply), 3 window चे high / low, 4 structural target (Q44), 5 correction
    टोकं. पट्टा = swing candle चा स्वतःचा area, wick ते body (C-13, layer 6b; target = फक्त किंमत). State: fresh / tested / broken (birth नंतरचे closes / ranges); target ⇒ "target".
    तुटलेले पट्टे: कमाल `max_broken` (सर्वात अलीकडे तुटलेला). नाव (trader): "demand / supply <price> (state)" — बाजू आजच्या close
    वरून (तुटलेला ⇒ तुटण्याआधीची भूमिका), "protected", "sharp-fall supply" / "sharp-rise demand", "target"."""
    s = S3.load(s)
    d = v["frame"]
    C, Hh, Ll = d["close"].to_numpy(float), d["high"].to_numpy(float), d["low"].to_numpy(float)
    n, i0 = v["n"], v["i0"]
    q = v["q15"]
    O = d["open"].to_numpy(float)
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
    base = _structure_base(q)
    if base is not None:                                                   # §5.4: रचनेचा major low / high > window low / high
        cand.append((2, base[0], base[1], base[2]))
    win_h = i0 + int(np.argmax(Hh[i0:]))
    win_l = i0 + int(np.argmin(Ll[i0:]))
    cand += [(3, "window high", float(Hh[win_h]), win_h), (3, "window low", float(Ll[win_l]), win_l)]
    for x in q.get("targets") or ():                                       # rule 5 च्या पट्ट्यांनंतर (Q44: फक्त रचनेतला target)
        cand.append((4, "target", float(x), None))
    for c in (q.get("objects") or {}).get("corrections", []):
        if c["end_bar"] >= i0 and c["state"] == "done":
            cand.append((5, "correction end", c["end_price"], c["end_bar"]))
    wlo, whi = float(Ll[i0:].min()), float(Hh[i0:].max())
    rows = []                                                              # 1) प्रत्येक उमेदवार स्वतंत्र: पट्टा + state
    for rank, label, px, bar in sorted(cand, key=lambda x: (x[0], x[1].startswith("sharp-"), abs(x[2] - C[-1]))):
        lo, hi = _band_of(label, px, bar, zone, O, Hh, Ll, C)               # layer 6b (C-13): the swing candle's own area, wick to body
        brk = None
        if bar is None:
            state = "target"
        else:
            after = slice(int(bar) + 1, n)
            above_now = C[-1] > hi
            far = (C[after] < lo) if above_now else (C[after] > hi)        # आजच्या उलट बाजूचे closes ⇒ तुटला (शेवटचा ⇒ तुटण्याचा bar)
            crossed = bool(far.any()) if C[-1] > hi or C[-1] < lo else False
            touched = bool(((Ll[after] <= hi) & (Hh[after] >= lo)).any())
            state = "broken" if crossed else ("tested" if touched else "fresh")
            if crossed:
                brk = int(bar) + 2 + int(np.flatnonzero(far)[-1])
            if crossed and label.startswith("structure "):
                continue                                                   # तुटलेल्या टोकावर रचना "उभी" नाही ⇒ उमेदवार नाही
        off = "above" if lo > whi else ("below" if hi < wlo else None)
        rows.append({"rank": rank, "label": label, "price": round(float(px), 2), "lo": round(float(lo), 2), "hi": round(float(hi), 2),
                     "state": state, "bar": None if bar is None else int(bar), "off_window": off, "broken_bar": brk, "also": [],
                     "role": _role(label, px, C[-1], state)})
    if max_broken is not None:                                             # 2) §5.4: तुटलेले कमाल max_broken (सर्वात अलीकडे तुटलेले) —
        br = sorted((b for b in rows if b["state"] == "broken"), key=lambda b: b["broken_bar"])   # merge आधी (टाकलेला पट्टा
        drop = {id(b) for b in br[:max(0, len(br) - int(max_broken))]}                           # जवळचे उमेदवार गिळत नाही)
        rows = [b for b in rows if id(b) not in drop]
    out = []                                                               # 3) degree क्रमाने; आधीच्या पट्ट्यात ⇒ नवा नाही. target शेवटी
    rows = [b for b in rows if b["label"] != "target"] + [b for b in rows if b["label"] == "target"]   # (कोणत्याही न तुटलेल्या पट्ट्यात
    for b in rows:                                                                                    # जोडता यावा म्हणून)
        if b["label"].startswith("sharp-"):
            prot = next((o for o in out if o["role"] == "protected" and o["state"] != "broken" and b["state"] != "broken"
                         and b["lo"] <= o["lo"] and o["hi"] <= b["hi"]), None)
            if prot is not None:                                           # protected पूर्ण sharp zone च्या आत ⇒ एकच पट्टा, एकच label
                prot["label"] += f" · {b['label']}"
                prot.update(sharp=b["label"], lo=b["lo"], hi=b["hi"])
                continue
        hit = [o for o in out if o["lo"] <= b["price"] <= o["hi"]]           # C-13: the same place = inside that swing's own area
        if b["label"] == "target":
            live = [o for o in hit if o["state"] != "broken"]
            if live:                                                       # target: कोणत्याही न तुटलेल्या hit मध्ये जोडतो
                live[0]["also"].append("target")
                continue
            hit = []
        if hit:
            if b["label"].startswith("sharp-"):
                hit[0]["label"] += f" · {b['label']}"
                hit[0]["also"].append(b["label"])
            continue
        out.append(b)
    out.sort(key=lambda b: b["rank"])                                      # stable: rank क्रम (target त्याच्या rank वर)
    out = out if limit is None else out[:int(limit)]
    for b in out:
        b["name"] = band_name(b)
    return out


def _band_of(label, px, bar, zone, O, H, L, C):
    """Layer 6b (Abhi L1-b ⇒ C-13): a Daily level's band = its swing candle's own area, wick to body (`daily.c13_area`) — a low:
    [low, body bottom]; a high: [body top, high] — never a price ± a σ fraction. The sharp-fall / sharp-rise zone = the area itself.
    A target has no candle (a projection) ⇒ its own price (drawn as a line). A price that is neither the candle's high nor its low (never
    seen; defensive) ⇒ the candle's side by that price's half of the candle."""
    if label.startswith("sharp-") and zone is not None:
        return float(zone[0]), float(zone[1])
    if bar is None:
        return float(px), float(px)
    b = int(bar)
    if np.isclose(px, L[b]) and not np.isclose(px, H[b]):
        kind = "L"
    elif np.isclose(px, H[b]) and not np.isclose(px, L[b]):
        kind = "H"
    else:
        kind = "L" if px <= (H[b] + L[b]) / 2.0 else "H"
    return DD.c13_area(O, H, L, C, b, kind)


def _structure_base(q):
    """§5.4: रचना ज्या major टोकावर उभी — शेवटच्या पूर्ण same-degree correction ची सुरुवात (आधीच्या impulse चं टोक: DOWN ⇒ low,
    UP ⇒ high). नसेल ⇒ None. रिटर्न (label, price, bar)."""
    t = q.get("trend")
    if t not in ("UP", "DOWN"):
        return None
    for c in reversed((q.get("objects") or {}).get("corrections", [])):
        if c["state"] != "done":
            continue
        if (t == "DOWN" and c["start_price"] < c["end_price"]) or (t == "UP" and c["start_price"] > c["end_price"]):
            return ("structure low" if t == "DOWN" else "structure high", float(c["start_price"]), int(c["start_bar"]))
    return None


def _role(label, px, close, state):
    """Trader भूमिका: protected / parent protected / sharp-* / target; बाकी आजच्या close च्या खाली ⇒ demand, वर ⇒ supply (तुटलेला ⇒
    उलट: तुटण्याआधी तो त्या बाजूचा होता)."""
    if label == "protected origin":
        return "protected"
    if label == "larger-degree origin":
        return "parent protected"
    if label.startswith("sharp-"):
        return label
    if label == "target":
        return "target"
    side = "demand" if px < close else "supply"
    if state == "broken":
        side = "supply" if side == "demand" else "demand"
    return side


def band_name(b):
    """Chart / caption वरचं नाव: "demand 52,783 (tested)", "protected 58,706 (tested) · sharp-fall supply", "target 49,955";
    protected sharp zone च्या आत ⇒ "sharp-fall supply · protected 58,706 (tested)"."""
    if b.get("sharp"):
        return f"{b['sharp']} · protected {b['price']:,.0f} ({b['state']})" + "".join(f" · {a}" for a in b.get("also") or ())
    txt = f"{b['role']} {b['price']:,.0f}" + ("" if b["state"] == "target" else f" ({b['state']})")
    return txt + "".join(f" · {a}" for a in b.get("also") or ())


def band_style(b):
    """Chart style (legend शी एक-एक): broken / protected origin / sharp band / demand / supply / target."""
    if b["state"] == "broken":
        return "broken"
    if b.get("sharp"):
        return "sharp band"
    r = b["role"]
    if r in ("protected", "parent protected"):
        return "protected origin"
    if r.startswith("sharp-"):
        return "sharp band"
    return r


def view_spec(v, full=False):
    """C1 / §5 (Abhi): default Daily chart वर काय काढायचं (फक्त trend-degree) — chart आणि tests याच spec वरून.
    Default (declutter): text फक्त चालू correction + आधीची same-degree correction (चालू = in-progress box, किंवा box नसताना lower-degree
    pullback ची एकच खूण "pullback", नाहीतर शेवटची पूर्ण correction); in-progress candidate box वर "pullback" एकदाच ("candidate" शब्द
    नाही); जुने boxes text शिवाय फिके — window `chart_old_box_sessions` पेक्षा लांब ⇒ जुने boxes नाहीतच. tags = chart वरचे सगळे
    correction / pullback labels. full=True (debug): सगळे boxes labels सह, सगळे pullback marks, सगळे पट्टे (cap / broken मर्यादा नाही)."""
    s = S3.load(v.get("s"))
    i0 = v["i0"]
    q = v["q15"]
    ob = q["objects"]
    legs = [lg for lg in ob["legs"] if lg["to"] >= i0]
    allb = [c for c in ob["corrections"] if c["end_bar"] >= i0]
    cur_box = next((c for c in reversed(allb) if c["state"] == "in progress"), None)
    done = [c for c in allb if c["state"] == "done"]
    cur = ob["legs"][-1] if ob["legs"] else None
    trending = q["trend"] in ("UP", "DOWN")
    boxed = {c["end_bar"] for c in allb}
    pulls = [b for b in ob["bounces"] if cur is not None and b["bar"] > cur["from"] and b["bar"] >= i0 and b["bar"] not in boxed
             and b["tag"] in ("pullback", "candidate") and trending]
    if cur_box is not None and not full:                                   # §5.2: box मधले pullback / candidate marks नाहीत
        pulls = []
    one = None
    if not full and cur_box is None and trending and q.get("counter") == "pullback" and cur is not None:
        one = _current_pullback(v["frame"], cur)                           # box नसलेला चालू pullback ⇒ एकच खूण, चालू bounce वर
        if one is None:                                                    # bounce अजून नाही ⇒ शेवटचा confirmed pullback pivot
            one = next(({**b, "text": f"last pullback {'high' if b['kind'] == 'H' else 'low'}"} for b in reversed(pulls)
                        if b["tag"] == "pullback"), None)
    if full:
        keep = {id(c) for c in allb}
    elif cur_box is not None:
        keep = {id(cur_box)} | {id(c) for c in done[-1:]}
    elif one is not None:
        keep = {id(c) for c in done[-1:]}
    else:
        keep = {id(c) for c in done[-2:]}
    old_ok = full or (v["n"] - i0) <= int(s["chart_old_box_sessions"])
    boxes = []
    for c in allb:
        lab = box_label(c) if id(c) in keep else None
        if lab is None and not old_ok:
            continue                                                       # लांब window ⇒ जुने boxes नाहीत
        boxes.append({**c, "label": lab, "faint": lab is None})
    marks = [{**b, "tag": "pullback"} for b in pulls] if full else ([{"text": "pullback", **one, "tag": "pullback"}] if one is not None
                                                                     else [])
    tags = [b["label"] for b in boxes if b["label"]] + [b["tag"] for b in marks]
    bands = level_bands(v, s, limit=None, max_broken=None) if full else (q.get("levels") or [])
    imps = [x for x in ob.get("impulses") or [] if x["to"] >= i0]
    wa = q.get("wave_a")                                                   # Q49: chart वर "A" (पर्याय "1" फक्त debug)
    waves = [wa] if wa and wa["bar"] >= i0 else []
    return {"legs": legs, "impulses": imps, "boxes": boxes, "pullbacks": marks, "tags": tags, "waves": waves, "bands": bands,
            "protected": q.get("protected_now"), "strip": {"degree-aware": q["states"], "Dow minor": v["minor"]["bands"]}}


def _current_pullback(d, leg):
    """चालू (अजून confirm न झालेला) pullback: leg च्या टोकानंतरचं उलट टोक (DOWN ⇒ सर्वात उंच high, UP ⇒ सर्वात खालचा low). टोक
    शेवटचा bar असेल ⇒ None."""
    j0, n = int(leg["to"]), len(d)
    if j0 + 1 >= n:
        return None
    if leg["dir"] < 0:
        H = d["high"].to_numpy(float)
        j = j0 + 1 + int(np.argmax(H[j0 + 1:]))
        return {"bar": j, "price": float(H[j]), "kind": "H", "text": "pullback"}
    L = d["low"].to_numpy(float)
    j = j0 + 1 + int(np.argmin(L[j0 + 1:]))
    return {"bar": j, "price": float(L[j]), "kind": "L", "text": "pullback"}


def box_label(c):
    """Box वरचा एकच label: पूर्ण ⇒ "correction · 64% of impulse · zigzag"; चालू candidate ⇒ "pullback (in progress) · …";
    चालू same-degree correction ⇒ "correction (in progress) · …"."""
    if c["state"] == "in progress":
        bits = ["pullback (in progress)" if c["kind"] == "candidate" else "correction (in progress)"]
    else:
        bits = ["correction"]
    if c.get("depth") is not None:
        bits.append(f"{c['depth']:.0%} of impulse")
    if c.get("shape"):
        bits.append(c["shape"])
    return " · ".join(bits)


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


def _leg_cur(q):
    """Chart वरचा शेवटचा trend-degree leg (चालू असेल तर leg_now, नाहीतर leg_last — candidate / pullback चालू असताना पूर्ण झालेला), trend च्या
    दिशेचा असेल तरच; नाही / हाताने बनवलेले q ⇒ None."""
    ln = q.get("leg_now") or q.get("leg_last")
    if not ln:
        return None
    want = {"UP": 1, "DOWN": -1}.get(q.get("trend"))
    return ln if ln.get("dir") in (None, want) else None


def unverified(q):
    """Abhi review + CD14 + PR #304: chart वरचा शेवटचा trend leg (चालू किंवा पूर्ण) read_counter ने 5-wave impulse म्हणून वाचला नाही **आणि**
    Abhi ने तो impulse म्हणून स्वीकारलेला नाही ⇒ True (title / caption "impulse" म्हणत नाहीत — chart वर तो dashed "trend leg"). leg माहिती
    नसलेले (हाताने बनवलेले) q ⇒ False (जुनं वाचन)."""
    ln = _leg_cur(q)
    return bool(ln) and not ln.get("verified") and not ln.get("accepted")


def _leg_now_detail(q):
    """Debug: शेवटच्या trend leg ची तपासणी (leg_check_text) — default मध्ये कधीच नाही."""
    return leg_check_text(_leg_cur(q) or {})


def _leg_word(q):
    """Unverified + न-स्वीकारलेला leg: चालू ⇒ "new decline in progress", पूर्ण ⇒ "trend leg" (strip वरचं नाव) — impulse दावा नाही."""
    return f"new {_move(q['trend'])} in progress" if (_leg_cur(q) or {}).get("state") == "in progress" else "trend leg"


def _depth(q):
    """Counter-move ची खोली — शेवटचा leg impulse (verified / स्वीकारलेला / माहिती नाही) ⇒ "of last impulse", नाहीतर "of last trend leg"."""
    return f" (depth {q['retrace']:.0%} of last {'trend leg' if unverified(q) else 'impulse'})"


def _move(t):
    return "decline" if t == "DOWN" else "advance"


def trend_line(q, debug=False):
    """A4 (Abhi): एक ओळ — "Trend DOWN (impulse) · pullback in progress (lower degree) · protected 24,774". चालू leg verified नाही आणि
    स्वीकारलेलाही नाही ⇒ "Trend DOWN (new decline in progress)" — impulse दावा नाही, "not verified" मजकूर नाही (CD14: default / Telegram);
    debug=True ⇒ "(new decline in progress, impulse not verified (structure vote: …; anatomy vote: …))" (engine चा Dow trend / protected
    तसेच)."""
    t = q["trend"]
    if t not in ("UP", "DOWN"):
        return f"Trend {t}" + (f" · band {q['band'][0]:,.0f}–{q['band'][1]:,.0f}" if q.get("band") else "")
    if q["phase"] == "origin_broken":
        body = f"Trend {t} · origin broken on close — waiting for an opposite impulse"
    elif q["phase"] == "impulse" and unverified(q):
        body = f"Trend {t} ({_leg_word(q)}" + (f", {_leg_now_detail(q)})" if debug else ")")
        if q.get("counter"):
            body += f" · {COUNTER_TXT[q['counter']]}"
            if q.get("retrace") is not None:
                body += _depth(q)
    else:
        body = f"Trend {t} ({'impulse' if q['phase'] == 'impulse' else 'correction'})"
        if q.get("counter"):
            body += f" · {COUNTER_TXT[q['counter']]}"
            if q.get("retrace") is not None:
                body += _depth(q)
    r5 = bool(q.get("rule5")) and q["phase"] == "impulse" and q.get("counter") in (None, "pullback")
    if r5:                                                                 # ABC_FIX rule 5 (फक्त नवा impulse चालू असताना; नवी correction ⇒ नाही)
        fam = q.get("last_corr_shape")
        fam = "a-b-c" if fam in ("zigzag", "flat") else (fam or "")
        body = (f"Trend {t} · {fam + ' ' if fam else ''}correction completed at sharp-{'fall supply' if t == 'DOWN' else 'rise demand'}"
                + ((f" · {_leg_word(q)}" + (f" ({_leg_now_detail(q)})" if debug else "")) if unverified(q)
                   else f" · new impulse {t.lower()} in progress"))
    ln = _leg_cur(q) or {}
    if debug and q["phase"] == "impulse" and ln.get("accepted") and not ln.get("verified"):   # CD14 debug: स्वीकारलेल्या चालू leg चे votes
        body += f" [{_leg_now_detail(q)}]"
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
    if q.get("rev"):                                                       # trend first: impulse टोकानंतर रचना trend विरुद्ध ⇒ entries नाहीत
        rv = q["rev"]
        body += (f" · structure turned {'UP' if t == 'DOWN' else 'DOWN'} ({'HL' if rv['kind'] == 'L' else 'LH'} {rv['price']:,.0f}, "
                 f"close beyond {rv['beyond']:,.0f}) — no {'bear call' if t == 'DOWN' else 'bull put'}")
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


def atr(d, n):
    """ATR_D: शेवटच्या n Daily candles चा सरासरी true range (पहिल्या candle ला मागचा close = तिचाच close)."""
    H, L, C = (d[k].to_numpy(float) for k in ("high", "low", "close"))
    if not len(C):
        return 0.0
    pc = np.r_[C[0], C[:-1]]
    tr = np.maximum(H - L, np.maximum(np.abs(H - pc), np.abs(L - pc)))
    return float(tr[-int(n):].mean())


def state_short(q):
    """§5.7 caption ओळ 1 ची अवस्था: "DOWN impulse · pullback in progress" / "UP correction in progress" / "RANGE …"."""
    t = q["trend"]
    if t not in ("UP", "DOWN"):
        return t + (f" {q['band'][0]:,.0f}–{q['band'][1]:,.0f}" if q.get("band") else "")
    if q["phase"] == "origin_broken":
        return f"{t} · origin broken on close"
    c = q.get("counter")
    if c == "correction":
        return f"{t} · correction in progress"
    if q["phase"] == "impulse" and unverified(q):
        body = f"{t} · {_leg_word(q)}"                                     # CD14: impulse दावा नाही, "not verified" मजकूर नाही
    elif q["phase"] == "impulse" and (_leg_cur(q) or {}).get("verified"):
        body = f"{t} impulse (5 waves)"
    else:
        body = f"{t} {'impulse' if q['phase'] == 'impulse' else 'correction'}"
    if c == "pullback":
        body += " · pullback in progress"
    elif c == "candidate":
        body += " · pullback in progress (may become a correction)"
    return body


def band_dist(b, close):
    """§5.7: एकच नियम (ओळ 1 आणि 2): close पासून पट्ट्याच्या जवळच्या कडेपर्यंत — वर ⇒ lo − close, खाली ⇒ close − hi, आत ⇒ 0."""
    return max(0.0, float(b["lo"]) - close, close - float(b["hi"]))


def nearest_bands(v, s=None):
    """§5.7 ओळ 2: chart वरच्या पट्ट्यांपैकी (तुटलेले / target सोडून) वरची जवळची (supply) आणि खालची जवळची (demand) — निवड आणि
    अंतर दोन्ही जवळच्या कडेपर्यंत (band_dist); close पट्ट्यात ⇒ 0 (केंद्र वर ⇒ supply बाजू, खाली ⇒ demand). रिटर्न (supply, demand),
    प्रत्येकात dist_atr (ATR_D, 0.1 पर्यंत)."""
    s = S3.load(s if s is not None else v.get("s"))
    d = v["frame"]
    close = float(d["close"].iloc[-1])
    a = atr(d, int(s["chart_atr_n"])) or 1e-9
    live = [b for b in v["q15"].get("levels") or [] if b["state"] not in ("broken", "target")]
    up = [b for b in live if b["hi"] > close and (b["lo"] > close or b["price"] >= close)]
    dn = [b for b in live if b["lo"] < close and (b["hi"] < close or b["price"] < close)]
    pick = lambda xs: min(xs, key=lambda b: (band_dist(b, close), b["rank"])) if xs else None   # noqa: E731
    sup, dem = pick(up), pick(dn)
    sup = None if sup is None else {**sup, "dist_atr": round(band_dist(sup, close) / a, 1)}
    dem = None if dem is None else {**dem, "dist_atr": round(band_dist(dem, close) / a, 1)}
    return sup, dem


def protected_risk(v, s=None):
    """§5.7 ओळ 1: protected **किंमती** पर्यंत risk (ATR_D) — पट्ट्याच्या कडेपर्यंत नाही (sharp zone मध्ये merge झालेला पट्टा कडा जवळ
    आणतो ⇒ risk कमी दिसेल, असुरक्षित). ओळ 2 (जवळचा पट्टा) कडेचाच नियम."""
    s = S3.load(s if s is not None else v.get("s"))
    q = v["q15"]
    pq = q.get("protected_now")
    if not pq:
        return None
    d = v["frame"]
    close = float(d["close"].iloc[-1])
    return round(abs(close - float(pq["price"])) / (atr(d, int(s["chart_atr_n"])) or 1e-9), 1)


def caption(v, symbol, audit_line=None, years=None):
    """≤ 7 ओळी (English) — audit ओळ धरून. §5.7 (Abhi): ओळ 1 = अवस्था + protected + risk (protected पर्यंत ATR_D); ओळ 2 = जवळची
    demand / supply पट्टी आणि अंतर ATR_D मध्ये; मग पूर्ण रचना ओळ, Dow minor, Elliott, audit, disclaimer."""
    s = S3.load(v.get("s"))
    n = v["n"]
    m, q = v["minor"], v["q15"]
    d = v["frame"]
    close = float(d["close"].iloc[-1])
    a = atr(d, int(s["chart_atr_n"])) or 1e-9
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
    pq = q.get("protected_now")
    one = f"{symbol} Daily: {state_short(q)}"
    if pq:
        one += f" · protected {pq['price']:,.0f} · risk {protected_risk(v, s):.1f} ATR to protected"
    else:
        one += " · no protected level"
    if q.get("origin_risk"):
        one += " (origin at risk)"
    sup, dem = nearest_bands(v, s)
    bits = []
    for b, side, where in ((sup, "supply", "above"), (dem, "demand", "below")):
        if b is not None:
            bits.append(f"{side}: {b['name']}, " + (f"{b['dist_atr']:.1f} ATR {where}" if b["dist_atr"] > 0 else "price inside"))
        else:
            bits.append(f"{side}: none on chart")
    two = "Nearest " + " · nearest ".join(bits) + f" (ATR {a:,.0f})"
    lines = [
        one,
        two,
        trend_line(q) + f" · since {ago(q['since'], n, w0)} · {span}, engine on full history",
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
            "trend_line": trend_line(v["q15"]), "trend_line_debug": trend_line(v["q15"], debug=True),   # CD14: default (chart) / तपशील
            "leg_now": v["q15"].get("leg_now"), "leg_last": v["q15"].get("leg_last"),
            "counter": v["q15"].get("counter"), "origin_risk": v["q15"].get("origin_risk"),
            "wave_a": None if not v["q15"].get("wave_a") else {**v["q15"]["wave_a"], "day": day(v["q15"]["wave_a"]["bar"]),
                                                              "alt": v["q15"].get("alt")},   # Q49 debug: "A" (alt: 1)
            "retrace": v["q15"].get("retrace"),
            "parent": None if not v["q15"].get("parent") else {**v["q15"]["parent"], "day": day(v["q15"]["parent"]["bar"])},
            "objects": _objects_json(v, day), "bands": [{**b, "day": None if b["bar"] is None else day(b["bar"])}
                                                        for b in v["q15"].get("levels") or []],
            "range_check": _range_json(v, day), "chart": _chart_json(v),
            "note": "Visual review only — no trade, no order. Engine numbers from data."}


def _chart_json(v):
    """§5 default chart वर प्रत्यक्ष काय काढलं (Vision facts साठी): boxes, labels, पट्ट्यांची नावं."""
    sp = view_spec(v)
    return {"boxes_drawn": len(sp["boxes"]), "boxes_faint": sum(1 for b in sp["boxes"] if b["faint"]), "labels": sp["tags"],
            "bands": [b["name"] for b in sp["bands"]]}


def _objects_json(v, day):
    """C1 objects (window ला लागणारे) — bars ⇒ दिवस (Q33: sealed ⇒ "before window")."""
    ob, i0 = v["q15"].get("objects") or {"legs": [], "corrections": [], "bounces": []}, v["i0"]
    return {"legs": [{**x, "from_day": day(x["from"]), "to_day": day(x["to"])} for x in ob["legs"] if x["to"] >= i0],
            "impulses": [{**x, "from_day": day(x["from"], True), "to_day": day(x["to"]), "path": [[day(b, True), p] for b, p in x["path"]]}
                         for x in ob.get("impulses") or [] if x["to"] >= i0],
            "corrections": [{**x, "start_day": day(x["start_bar"]), "end_day": day(x["end_bar"])} for x in ob["corrections"]
                            if x["end_bar"] >= i0],
            "bounces": [{**x, "day": day(x["bar"])} for x in ob["bounces"] if x["bar"] >= i0]}


def _range_json(v, day):
    rc = v["q15"].get("range_check")
    if not rc:
        return None
    return {**rc, "lows": [{**x, "day": day(x["bar"])} for x in rc["lows"]], "highs": [{**x, "day": day(x["bar"])} for x in rc["highs"]]}
