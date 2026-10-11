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
    return {
        "n": n, "i0": i0, "first_day": str(d["timestamp"].iloc[0].date()), "last_day": str(d["timestamp"].iloc[-1].date()),
        "frame": d, "pivots": pivots, "legs": [x for x in legs(piv, q15) if x["to"] >= i0],
        "minor": {"bands": runs(tm), "protected": seg_m, "trend": last_m.trend, "since": since_m, "why": why_m,
                  "protected_now": None if last_m.protected is None else {"kind": last_m.protected.kind, "price": last_m.protected.price,
                                                                          "bar": last_m.protected.bar}},
        "q15": {"bands": runs(tq), "protected": seg_q, "trend": last_q.trend, "since": since_q, "phase": last_q.phase, "wave": last_q.wave,
                "corr_label": last_q.corr_label, "mature": bool(last_q.mature), "targets": list(last_q.targets),
                "protected_now": None if last_q.protected is None else {"kind": last_q.protected.kind, "price": last_q.protected.price,
                                                                        "bar": last_q.protected.bar},
                "phases": runs([(x.phase or "-") + "|" + (x.wave or "") for x in q15])},
        "elliott": ev, "elliott_degree": deg, "sealed": sealed,
    }


def caption(v, symbol, audit_line=None, years=None):
    """≤ 7 ओळी (English) — audit ओळ धरून."""
    n = v["n"]
    m, q = v["minor"], v["q15"]
    shown = n - v["i0"]
    w0 = v["i0"] if v.get("sealed") is not None else None                 # Q33: sealed काळातली सुरुवात ⇒ "window आधी" (तारीख / मोजणी नाही)
    span = f"last {years}y" if years and v.get("full_window", True) else f"{shown} sessions"
    pm = m["protected_now"]
    pq = q["protected_now"]
    lab = "—"
    if v.get("elliott_degree"):
        e = v["elliott"]["degrees"][v["elliott_degree"]]
        lab = f"{v['elliott_degree']} {e['pattern']} wave {e['current_wave']}" + (" ? (weak vote)" if e["gray"] else "")
    elif v["elliott"].get("error"):
        lab = f"NA ({v['elliott']['error'][:40]})"
    why = _en(m["why"])
    lines = [
        f"{symbol} · Daily · {span} (engine on full history)",
        f"Dow (minor swings): {m['trend']} since {ago(m['since'], n, w0)}" + (f" — {why}" if why else ""),
        f"Protected: minor {_pv(pm, m['trend'] == 'NEUTRAL')} | Q15 origin {_pv(pq, q['phase'] == 'origin_broken')}",
        f"Degree-aware (Q15): {q['trend']} {(q['phase'] or '').replace('_', ' ')}".rstrip() + f" since {ago(q['since'], n, w0)}"
        + (" · impulse mature" if q["mature"] else ""),
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
            "note": "Visual review only — no trade, no order. Engine numbers from data."}
