"""backtest_review/daily.py — Daily (आजोबा degree, नकाशा P1) chart ची तथ्ये. Abhi 2026-10-09: review / plan / manual charts चं 1D पान.

सगळं **decision दिवसाच्या close पर्यंतच्या** data वरून (no-lookahead): market_state.frame("1d", asof) फक्त bar_end ≤ asof चे bars.
  1. trend (HH/HL किंवा LH/LL) + daily protected level — market_state.trend त्याच नियमांनी, trend_tf = 1d (ATR14 × trend_swing_atr_mult);
  2. confirmed daily swings (त्याच trend चे pivots; मोठे swings पुरते);
  3. 2–3 मुख्य daily areas — chart_reader टप्पा 3 ची साधनं (levels_v2 1D + areas.tools + zones.annotate) daily frame वर: seller वर,
     buyer खाली, किंमतीपासून जवळचे;
  4. daily trendline (≥ 2 anchors; areas.sloping) touch-बिंदूंसह;
  5. daily degree count: elliott count engine, degree_tf_mode fixed (D3 = 1d) — preferred + alternate; gray / count नाही ⇒ "count gray";
  6. न भरलेले daily gaps (wick-to-wick: low > आधीचा high / high < आधीचा low; नंतरच्या bars नी पूर्ण भरले नाहीत; अर्धवट ⇒ उरलेला पट्टा);
  7. शेवटच्या candle जवळ एक ओळ: आजोबा degree ची दिशा + P1 पुरावा.
नवे आकडे नाहीत — सगळे parameters त्या त्या module चे (A1 register).
"""
import numpy as np
import pandas as pd

LIVE_STATES = ("ACTIVE", "TESTED", "FLIPPED")


def _struct(swings):
    """शेवटच्या H आणि L चे labels ⇒ "LH / LL" (नसेल ⇒ None)."""
    h = next((p for p in reversed(swings) if p["kind"] == "H"), None)
    lo = next((p for p in reversed(swings) if p["kind"] == "L"), None)
    if not h or not lo:
        return None
    return f"{h['label']} / {lo['label']}"


def unfilled_gaps(fr):
    """Wick-to-wick daily gaps जे नंतरच्या bars नी (asof पर्यंत) पूर्ण भरले नाहीत ⇒ [{dir, low, high, ts}] (अर्धवट ⇒ उरलेला पट्टा)."""
    h, lo = fr["high"].to_numpy(float), fr["low"].to_numpy(float)
    out = []
    for i in range(1, len(fr)):
        if lo[i] > h[i - 1]:                                              # gap up: पट्टा (आधीचा high, आजचा low)
            m = float(lo[i + 1:].min()) if i + 1 < len(fr) else np.inf
            if m > h[i - 1]:
                out.append({"dir": "up", "low": float(h[i - 1]), "high": float(min(lo[i], m)), "ts": fr["timestamp"].iloc[i]})
        elif h[i] < lo[i - 1]:                                            # gap down: पट्टा (आजचा high, आधीचा low)
            m = float(h[i + 1:].max()) if i + 1 < len(fr) else -np.inf
            if m < lo[i - 1]:
                out.append({"dir": "down", "low": float(max(h[i], m)), "high": float(lo[i - 1]), "ts": fr["timestamp"].iloc[i]})
    return out


def _node(n):
    from elliott.patterns import LABELS
    labs = LABELS.get(n.pattern, [])
    pts = [(pd.Timestamp(p.ts), float(p.price)) for p in n.points]
    return {"pattern": n.pattern, "points": pts, "labels": ["0"] + labs[:max(0, len(pts) - 1)], "current_wave": n.current_wave,
            "next_motive_dir": int(n.next_motive_dir or 0)}


def daily_count(df1m, asof):
    """Daily degree (fixed mode D3 = 1d) चा preferred + alternate. gray / count नाही ⇒ {"gray": True, "why": …}."""
    from elliott import settings as ES
    from elliott import swings as W
    from elliott.counts import CountEngine
    es = {**ES.DEFAULTS, "degree_tf_mode": "fixed"}
    d_daily = es["degree_levels"] - 1
    if W.degree_tf(es, d_daily) != "1d":
        return {"gray": True, "why": "daily degree settings मध्ये नाही"}
    try:
        md = W.multi_degree(df1m, es, now=asof)
        v = CountEngine(md, es).snapshot(asof).degrees.get(d_daily)
    except Exception as exc:                                             # noqa: BLE001 — गुपचूप नाही: कारण chart वर
        return {"gray": True, "why": f"count engine: {type(exc).__name__}"}
    if v is None or not v.nodes:
        return {"gray": True, "why": "daily count नाही (pivots अपुरे)"}
    if v.gray:
        return {"gray": True, "why": "vote gray"}
    pref = v.preferred or v.nodes[0]
    alt = next((n for n in v.nodes if n is not pref), None)
    return {"gray": False, "preferred": _node(pref), "alternate": _node(alt) if alt is not None else None}


def _areas(fr, price):
    from chart_reader import areas as AR
    from chart_reader import measures as M
    from chart_reader import settings as CS
    from chart_reader import zones as ZN
    from price_action import levels_v2 as LV
    cs = CS.load()
    mr = M.mr_now(fr)
    if not np.isfinite(mr) or mr <= 0:
        return [], [], mr
    horiz = [{**z, "tf": "1D"} for z in LV.build(fr, tf="1d")["candidates"]]
    zones = ZN.annotate(AR.tools(fr, horiz, {}, {}, cs, mr), fr, cs, mr, tf="1D")
    live = [z for z in zones if z.get("state") in LIVE_STATES]
    mid = lambda z: (float(z["low"]) + float(z["high"])) / 2.0          # noqa: E731
    sells = sorted([z for z in live if z["side"] == "sell" and z.get("tool") != "f" and mid(z) >= price], key=lambda z: mid(z) - price)
    buys = sorted([z for z in live if z["side"] == "buy" and z.get("tool") != "f" and mid(z) <= price], key=lambda z: price - mid(z))
    pick = sells[:1] + buys[:1]
    rest = sorted(sells[1:2] + buys[1:2], key=lambda z: abs(mid(z) - price))
    areas = pick + rest[:1]                                              # 2–3: seller वर + buyer खाली + पुढचा सर्वात जवळचा
    lines = [z for z in live if z.get("tool") == "f" and len(z.get("anchors") or []) >= 2]
    return areas, lines, mr


def p1_line(trend, struct, count):
    """आजोबा degree ची दिशा + P1 पुरावा (नियम: count / trend state वरून; नवा आकडा नाही)."""
    d = {1: "UP", -1: "DOWN"}.get(int(trend.get("dir") or 0), "RANGE")
    prot = trend.get("protected") or {}
    head = f"आजोबा (Daily): {d}" + (f" · protected {prot.get('kind', '')} {float(prot['price']):,.0f}" if prot.get("price") else "")
    ev = []
    if trend.get("state") == "testing":
        ev.append("protected तुटला, पुष्टी बाकी ⇒ कमी विश्वास")
    if count.get("gray"):
        ev.append(f"count gray ({count.get('why')}) ⇒ P1 पुरावा फक्त रचना" + (f" ({struct})" if struct else ""))
    else:
        n = count["preferred"]
        w = n["current_wave"]
        if n["pattern"] in ("impulse", "lead_diag", "end_diag") and w == "5":
            ev.append("wave 5 शक्य ⇒ कमी विश्वास")
        elif n["pattern"] in ("impulse", "lead_diag") and w == "3":
            ev.append("wave 3 चालू ⇒ दिशेला आधार")
        elif w in ("C", "E", "Y"):
            ev.append(f"{n['pattern']} चा {w} चालू ⇒ correction शेवटच्या भागात")
        else:
            ev.append(f"{n['pattern']} · wave {w} चालू")
    return head + (" · " + "; ".join(ev) if ev else "")


def facts(df1m, asof):
    """1D chart साठी सगळी तथ्ये, asof (decision दिवसाचा close) पर्यंतच."""
    from market_state import core as MS
    asof = pd.Timestamp(asof)
    cut = df1m[pd.to_datetime(df1m["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
    fr = MS.frame(cut, "1d", asof)
    out = {"asof": asof, "frame": fr, "trend": {}, "struct": None, "swings": [], "areas": [], "trendline": None, "count": {"gray": True,
           "why": "data अपुरा"}, "gaps": [], "line": "आजोबा (Daily): data अपुरा"}
    if len(fr) < 20:
        return out
    tr = MS.trend(fr, s={"trend_tf": "1d"})
    swings = [p for p in tr.get("swings") or [] if p["conf"] <= len(fr) - 1]   # फक्त confirmed
    price = float(fr["close"].iloc[-1])
    areas, lines, mr = _areas(fr, price)
    tl = None
    if lines:
        from backtest_review.charts import _tl_value_fn
        ts = pd.to_datetime(fr["timestamp"]).to_numpy(dtype="datetime64[ns]")
        best = None
        for z in lines:
            f = _tl_value_fn(z, ts)
            if f is None:
                continue
            v = f(fr["timestamp"].iloc[-1])
            if best is None or abs(v - price) < best[0]:
                best = (abs(v - price), z)
        tl = best[1] if best else None
    count = daily_count(cut, asof)
    struct = _struct(swings)
    out.update(trend=tr, struct=struct, swings=swings, areas=areas, trendline=tl, count=count, gaps=unfilled_gaps(fr), mr=mr,
               line=p1_line(tr, struct, count))
    return out
