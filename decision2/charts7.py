"""decision2/charts7.py — 🧭 सातही थर (Abhi): 15M आणि 1H दोन्ही chart वर थर 1–7 च्या मराठी खुणा. फक्त दाखवणं (निर्णय बदलत नाही).

थर 1: D1 zigzag + HH / HL / LH / LL, D2 pivots, D2 संरक्षित, D2 range पट्टा · थर 2: I रेघ (सुरुवात ⇒ टोक; window बाहेरचा भाग कापून,
सुरुवातीचा भाव लिहून), I चालू टोक, K टोक · थर 3: pattern + momentum (box) · थर 4: trade-बाजूचे / उलट zones (★) · थर 5: रेघा — trade-योग्य
ठळक, बाकी (लागू नाही / तीव्र / तुटलेली) फिकट, K आधार-रेघ · थर 6: शेवटची RSI divergence · थर 7: निर्णय, ⭐ commitment candle, प्रवेश / SL /
लक्ष्य, area. खाली खुणांचा मराठी अर्थ. सगळं t पर्यंत माहीत असलेलंच (known_at ≤ t).
"""
import numpy as np
import pandas as pd

from backtest_review import charts as BC
from pivots import charts as PC

from . import charts as DC
from . import engine as DE

TREND_MR = {"UP": "वर", "DOWN": "खाली", "RANGE": "range", "unknown": "अज्ञात"}
MODE_MR = {"trend": "trend", "range_alt": "range (कडेपासून)"}
ROLE_MR = {"seller": "विक्रेते", "buyer": "खरेदीदार"}
CLASS_MR = {"trade-योग्य": "trade-योग्य", "लागू नाही": "लागू नाही", "तीव्र": "तीव्र", "सपाट": "सपाट", "तुटलेली": "तुटलेली"}
REG_MR = {"trend_up": "trend वर", "trend_down": "trend खाली", "range": "range", "barbwire": "barbwire", "transition": "transition",
          "drift": "drift"}
SESSIONS = {"15M": 3, "1H": 15}
LEGEND = ("खुणा: पिवळी जाड = I (आवेग) · जांभळी तुटक = K टोक · राखाडी zigzag = D1 swings · सोनेरी = D2 · लाल / हिरवे पट्टे = "
          "विक्रेते / खरेदीदार zones<br>लाल / हिरवी रेघ = trade-योग्य trendline (फिकट ठिपके = लागू नाही) · निळी तुटक = K आधार-रेघ · "
          "नारिंगी ठिपके = D2 संरक्षित · जांभळे ठिपके = RSI divergence · सोनेरी चौकट = area")


def _lbl(ps, p):
    prev = [q for q in ps if q.kind == p.kind and q.bar < p.bar]
    if p.eq:
        return "EQ" + p.kind
    if not prev:
        return p.kind
    up = p.price > prev[-1].price
    return ("HH" if up else "LH") if p.kind == "H" else ("HL" if up else "LL")


def figure(C, dec, t, tf, title):
    import plotly.graph_objects as go
    m = C.m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    frame = m if tf == "15M" else PC.agg_1h(m)
    d = PC.window(frame, tf, asof, sessions=SESSIONS[tf]).reset_index(drop=True)
    n = len(d)
    fig = BC._base(d, title)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    tsx = pd.to_datetime(d["timestamp"]).to_numpy(dtype="datetime64[ns]")
    t0 = pd.Timestamp(tsx[0])
    b0 = int(np.searchsorted(C.ts.to_numpy(dtype="datetime64[ns]"), np.datetime64(t0, "ns")))   # window ची पहिली 15M bar

    def X(b):
        """15M bar index ⇒ या frame मधला x (window बाहेर ⇒ None)."""
        if b is None or b < b0 or b > t:
            return None
        return int(np.searchsorted(tsx, np.datetime64(pd.Timestamp(C.ts.iloc[b]), "ns"), side="right") - 1)

    def seg(b1, p1, b2, p2):
        """15M bars मधला सरळ भाग window ला कापून ⇒ (x1, y1, x2, y2, कापला?) किंवा None."""
        if b2 < b0 or b1 > t:
            return None
        cut = b1 < b0
        y1 = p1 + (p2 - p1) * (b0 - b1) / (b2 - b1) if cut and b2 != b1 else p1
        return X(max(b1, b0)), y1, X(min(b2, t)), p2 if b2 <= t else p1 + (p2 - p1) * (t - b1) / (b2 - b1), cut

    def hline(y, col, txt, dash="dash", w=1.2):
        if not (lo - (hi - lo) < y < hi + (hi - lo)):
            return
        fig.add_shape(type="line", x0=0, x1=n - 1, y0=y, y1=y, line=dict(color=col, width=w, dash=dash))
        fig.add_annotation(x=n - 1, y=y, text=txt, showarrow=False, xanchor="left", font=dict(size=10, color=col))

    def label(x, y, txt, col, up=True, size=11, far=False):
        sh = 26 if far else 13
        fig.add_annotation(x=x, y=y, text=txt, showarrow=False, yshift=sh if up else -sh, font=dict(size=size, color=col))
    res = C.res
    d2bars = {p.bar for p in res["pivots"][2] if p.confirm_bar <= t}
    # ---- थर 1: D1 zigzag + खुणा, D2 pivots, संरक्षित, range
    for deg, col, size, w in ((1, "#cfd8dc", 11, 1.2), (2, "#ffd54f", 13, 2.0)):
        ps = [p for p in res["pivots"][deg] if p.confirm_bar <= t and not p.warmup]
        vis = [p for p in ps if X(p.bar) is not None]
        prev = [p for p in ps if p.bar < b0][-1:]
        chain = prev + vis
        xs, ys = [], []
        for a, b in zip(chain, chain[1:]):
            sg = seg(a.bar, a.price, b.bar, b.price)
            if sg is not None:
                xs += [sg[0], sg[2], None]
                ys += [sg[1], sg[3], None]
        if xs and (deg == 1 or tf == "1H"):
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=col, width=w), opacity=0.55, showlegend=False,
                                     hoverinfo="skip"))
        for p in vis:
            if deg == 1 and p.bar in d2bars:
                continue                                                       # त्याच टोकावर D2 खूण येते (एकमेकांवर नको)
            label(X(p.bar), p.price, ("D2 " if deg == 2 else "") + _lbl(ps, p), col, p.kind == "H", size)
    s2 = C.st[2]["states"][t]
    if s2.get("protected") is not None:
        hline(float(s2["protected"]), "#ff8a65", f"D2 संरक्षित {s2['protected']:,.0f}", dash="dot")
    if s2["trend"] == "RANGE":
        b = DE.range_band(C, t)
        if b is not None:
            fig.add_shape(type="rect", x0=0, x1=n - 1, y0=b[1], y1=b[0], fillcolor="rgba(144,164,174,0.06)",
                          line=dict(color="#90a4ae", width=1, dash="dot"), layer="below")
            fig.add_annotation(x=0, y=b[0], text="D2 range पट्टा", showarrow=False, xanchor="left", yshift=8,
                               font=dict(size=10, color="#90a4ae"))
    # ---- थर 4: zones
    l4 = C.L4.get(t) or {}
    zs = {z["id"]: z for z in (C.Z.snap.get(t) or [])}
    for zid in (l4.get("next") or []) + (l4.get("opp") or []):                # box मधले सगळे trade-बाजूचे (next) + उलट zones
        z = zs.get(zid)
        if z is None or z["status"] == "dead":
            continue
        x0 = X(z["pivot_bar"]) if z.get("pivot_bar") is not None else None
        sell = z["role"] == "seller"
        fig.add_shape(type="rect", x0=x0 if x0 is not None else 0, x1=n - 1, y0=z["bottom"], y1=z["top"],
                      fillcolor="rgba(239,83,80,0.14)" if sell else "rgba(38,166,154,0.14)", line_width=0, layer="below")
        fig.add_annotation(x=n - 1, y=(z["top"] + z["bottom"]) / 2, text=f"{ROLE_MR[z['role']]} zone {'★' * int(z.get('stars', 1))}",
                           showarrow=False, xanchor="left", font=dict(size=10, color="#ef9a9a" if sell else "#80cbc4"))
    # ---- थर 5: रेघा (trade-योग्य ठळक, बाकी फिकट) + K आधार
    l5 = C.L5.get(t) or {}
    tsi = {str(x): i for i, x in enumerate(C.ts)}
    items = []
    for x in (l5.get("lines") or []):
        cls = x.get("class")
        if cls == "तुटलेली" and x.get("name", "").startswith("fan"):
            continue
        strong = cls == "trade-योग्य"
        col = ("#ef5350" if x["kind"] == "H" else "#26a69a") if strong else "rgba(176,190,197,0.55)"
        items.append((x, col, 2.4 if strong else 1.0, "solid" if strong else "dot",
                      f"{x.get('name') or 'रेघ'} · {CLASS_MR.get(cls, cls)} · {x['touches']['held']} स्पर्श"))
    kb = (l5.get("k_lines") or {}).get("base")
    if kb:
        items.append((kb, "#42a5f5", 1.8, "dash", "K आधार-रेघ"))
    for x, col, w, dash, txt in items:
        b1, b2 = tsi.get(x["a1"]["ts"]), tsi.get(x["a2"]["ts"])
        if b1 is None or b2 is None or b1 == b2:
            continue
        sl = (x["a2"]["price"] - x["a1"]["price"]) / (b2 - b1)
        sg = seg(b1, x["a1"]["price"], t, x["a1"]["price"] + sl * (t - b1))
        if sg is None:
            continue
        fig.add_trace(go.Scatter(x=[sg[0], n - 1], y=[sg[1], sg[3]], mode="lines", line=dict(color=col, width=w, dash=dash),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=n - 1, y=sg[3], text=txt, showarrow=False, xanchor="left", yshift=-10,
                           font=dict(size=9, color=col if "rgba" not in col else "#b0bec5"))
    # ---- थर 2: I रेघ (window बाहेरचा भाग कापून), चालू टोक, K टोक
    I = C.trk[1].I_at(t)
    st = C.trk[1].state(t)
    if I is not None:
        o, e = I["origin"], I["end"]
        sg = seg(o.bar, o.price, e.bar, e.price)
        if sg is not None:
            fig.add_trace(go.Scatter(x=[sg[0], sg[2]], y=[sg[1], sg[3]], mode="lines", line=dict(color="#fff176", width=4),
                                     opacity=0.6, showlegend=False, hoverinfo="skip"))
            start = f"I सुरुवात {o.price:,.0f}" + (f" ({pd.Timestamp(o.ts):%d %b}, chart आधी)" if sg[4] else "")
            fig.add_annotation(x=sg[0], y=sg[1], text=start, showarrow=True, arrowhead=2, ax=40, ay=-30 if I["dir"] < 0 else 30,
                               font=dict(size=11, color="#fff176"), arrowcolor="#fff176")
            if X(e.bar) is not None:
                fig.add_annotation(x=X(e.bar), y=e.price, text=f"I टोक {e.price:,.0f}", showarrow=True, arrowhead=2, ax=0,
                                   ay=34 if I["dir"] < 0 else -34, font=dict(size=11, color="#fff176"), arrowcolor="#fff176")
        else:
            hline(float(e.price), "#fff176", f"I टोक {e.price:,.0f} (chart आधी)", dash="dash", w=1)
        if st.get("state") == "impulse चालू" and st.get("extreme") is not None:
            hline(float(st["extreme"]), "#fff59d", f"I चालू टोक {st['extreme']:,.0f}", dash="dot", w=1)
        kx = (st.get("K") or {}).get("extreme")
        if kx is not None:
            hline(float(kx), "#ce93d8", f"K टोक {kx:,.0f}", dash="dot", w=1)
    # ---- थर 6: RSI divergence
    l6 = C.L6.get(t) or {}
    last = l6.get("last")
    if last:
        x1, x2 = X(last["L1"]["bar"]), X(last["L2"]["bar"])
        if x1 is not None and x2 is not None:
            fig.add_trace(go.Scatter(x=[x1, x2], y=[last["L1"]["price"], last["L2"]["price"]], mode="lines+markers",
                                     line=dict(color="#b39ddb", width=2, dash="dot"), showlegend=False, hoverinfo="skip"))
            fig.add_annotation(x=x2, y=last["L2"]["price"], text=f"RSI {last['type']}", showarrow=False, yshift=-18,
                               font=dict(size=10, color="#b39ddb"))
    # ---- थर 7: area, ⭐, प्रवेश / SL / लक्ष्य
    p = dec.get("points") or {}
    ar = p.get("7_area")
    if ar and ar.get("band"):
        x0 = max(n - (12 if tf == "15M" else 4), 0)
        fig.add_shape(type="rect", x0=x0, x1=n - 1, y0=ar["band"][0], y1=ar["band"][1], fillcolor="rgba(255,213,79,0.16)",
                      line=dict(color="#ffd54f", width=1), layer="below")
        fig.add_annotation(x=x0, y=ar["band"][1], text=f"area ({ar.get('src')})", showarrow=False, xanchor="left", yshift=8,
                           font=dict(size=10, color="#ffd54f"))
    cm = (p.get("9_price_failure") or {}).get("candle")
    if cm and X(cm["candle"]["t"]) is not None:
        fig.add_annotation(x=X(cm["candle"]["t"]), y=cm["candle"]["h"], text="⭐ commitment", showarrow=False, yshift=16,
                           font=dict(size=12, color="#ffd54f"))
    rk = p.get("10_risk")
    if rk and dec["decision"] == "setup":
        for nm, y, col in (("SL", rk["invalidation"], "#ef5350"), ("लक्ष्य", rk["target"], "#26a69a"), ("प्रवेश", rk["entry"], "#ffd54f")):
            hline(float(y), col, f"{nm} {y:,.0f}", w=1.5)
    fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                       text=box7(C, dec, t, st, I, l4, l5, l6), font=dict(size=11), bgcolor="rgba(14,17,23,0.90)", bordercolor="#455a64",
                       borderwidth=1)
    fig.add_annotation(x=0.0, y=-0.07, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                       text=LEGEND, font=dict(size=10, color="#90a4ae"))
    fig.update_layout(margin=dict(l=10, r=160, t=60, b=95))
    BC._finish(fig, d, lo, hi, fmt="%d %b %H:%M")
    span = (hi - lo) or 1.0
    fig.update_yaxes(range=[lo - 0.06 * span, hi + 0.32 * span])                 # वर box साठी जागा (candles झाकू नयेत)
    return fig


def figure15(C, dec, t, title):
    return figure(C, dec, t, "15M", title)


def box7(C, dec, t, st, I, l4, l5, l6):
    s1, s2 = C.st[1]["states"][t], C.st[2]["states"][t]
    rec3 = C.f1.out.get(t) or {}
    pref = rec3.get("pref")
    m = l4.get("momentum") or rec3.get("momentum") or {}
    ka, la = (l4.get("k_area") or {}), (l5.get("k_area_line") or {})
    rows = [f"<b>थर 1</b> · D1 {TREND_MR.get(s1['trend'], s1['trend'])} · D2 {TREND_MR.get(s2['trend'], s2['trend'])}"]
    if I is None:
        rows.append(f"<b>थर 2</b> · I नाही ({st.get('why', '—')})")
    else:
        dep = (st.get("K") or {}).get("depth_main")
        rows.append(f"<b>थर 2</b> · I {'↑' if I['dir'] > 0 else '↓'} {MODE_MR.get(I['mode'], I['mode'])} {I['origin'].price:,.0f} ⇒ "
                    f"{I['end'].price:,.0f} · {st.get('state')}" + (f" · खोली {dep:.2f}" if dep is not None else ""))
    rows.append(f"<b>थर 3</b> · pattern {(pref or {}).get('family', '—')} / {(pref or {}).get('state', '—')} · momentum {m.get('verdict') or '—'}")
    nz = len(l4.get("next") or [])
    rows.append(f"<b>थर 4</b> · trade-बाजूचे zones {nz} · K area (zone): {ka.get('ans', 'NA')}")
    nl = sum(1 for x in (l5.get("lines") or []) if x.get("class") == "trade-योग्य")
    rows.append(f"<b>थर 5</b> · trade-योग्य रेघा {nl} · K area (रेघ): {la.get('ans', 'NA')}"
                + (" · K आधार break" if (l5.get("k_base") or {}).get("bar") == t else ""))
    rows.append(f"<b>थर 6</b> · RSI: {l6.get('label') or '—'}" + (f" ({l6['rsi15']:.0f})" if l6.get("rsi15") is not None else ""))
    reg = ((dec.get("points") or {}).get("1_htf_state") or {}).get("regime") or {}
    rows.append(f"<b>थर 7</b> · {DC.DEC_MR[dec['decision']]}" + (f" · grade {dec['grade']}" if dec["decision"] == "setup" else
                                                               f" · {dec['gate']}: {dec['where_wrong']}")
                + f" · regime {REG_MR.get(reg.get('regime'), '—')}")
    return "<br>".join(rows)


def charts(C, dec, t):
    asof = pd.Timestamp(C.m15["bar_end"].iloc[t])
    title = "🧭 सातही थर · NIFTY {tf} · {d:%d %b %Y %H:%M}"
    return {tf: PC.png(figure(C, dec, t, tf, title.format(tf=tf, d=asof))) for tf in ("15M", "1H")}


def caption(n, total, asof, dec, why=None):
    p = dec.get("points") or {}
    reg = ((p.get("1_htf_state") or {}).get("regime") or {}).get("regime")
    lines = [f"🧭 सातही थर {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर"),
             f"निर्णय: {DC.DEC_MR[dec['decision']]}" + (f" · grade {dec['grade']} · size {dec['size_weight']}" if dec["decision"] == "setup"
                                                        else f" · कारण: {dec['where_wrong']}"),
             f"regime: {REG_MR.get(reg, '—')} · momentum: {(p.get('4_character') or {}).get('momentum') or '—'}",
             "Chart वर: थर 1 swings · थर 2 I / K · थर 4 zones · थर 5 रेघा · थर 6 RSI · थर 7 area / निर्णय (box मध्ये सातही)",
             "Reply: ✔ बरोबर वाचलं · ✘ कोणता थर चुकला (1–7) आणि का"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)
