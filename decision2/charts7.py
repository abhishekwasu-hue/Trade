"""decision2/charts7.py — 🧭 सातही थर (Abhi): एकाच 15M chart वर थर 1–7 च्या मराठी खुणा + 1H. फक्त दाखवणं (निर्णय बदलत नाही).

थर 1: D1 / D2 pivots (HH / HL / LH / LL), D2 संरक्षित पातळी, D2 range पट्टा · थर 2: I (सुरुवात ⇒ टोक), K टोक · थर 3: pattern + momentum
(box) · थर 4: trade-बाजूचे / उलट zones (★) · थर 5: trade-योग्य रेघा, K आधार-रेघ · थर 6: शेवटची RSI divergence · थर 7: निर्णय, ⭐
commitment candle, प्रवेश / SL / लक्ष्य, area. Caption मराठी, code keys नाहीत. सगळं t पर्यंत माहीत असलेलंच (known_at ≤ t).
"""
import pandas as pd

from backtest_review import charts as BC
from pivots import charts as PC

from . import charts as DC
from . import engine as DE

TREND_MR = {"UP": "वर", "DOWN": "खाली", "RANGE": "range", "unknown": "अज्ञात"}
MODE_MR = {"trend": "trend", "range_alt": "range (कडेपासून)"}
ROLE_MR = {"seller": "विक्रेते", "buyer": "खरेदीदार"}
REG_MR = {"trend_up": "trend वर", "trend_down": "trend खाली", "range": "range", "barbwire": "barbwire", "transition": "transition",
          "drift": "drift"}
SESSIONS_15M = 3


def _lbl(ps, p):
    prev = [q for q in ps if q.kind == p.kind and q.bar < p.bar]
    if p.eq:
        return "EQ" + p.kind
    if not prev:
        return p.kind
    up = p.price > prev[-1].price
    return ("HH" if up else "LH") if p.kind == "H" else ("HL" if up else "LL")


def figure15(C, dec, t, title):
    import plotly.graph_objects as go
    m = C.m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    d = PC.window(m, "15M", asof, sessions=SESSIONS_15M)
    off = t - (len(d) - 1)
    n = len(d)
    fig = BC._base(d, title)
    lo, hi = float(d["low"].min()), float(d["high"].max())

    def X(b):
        x = b - off
        return x if 0 <= x < n else None

    def hline(y, col, txt, dash="dash", w=1.2):
        fig.add_shape(type="line", x0=0, x1=n - 1, y0=y, y1=y, line=dict(color=col, width=w, dash=dash))
        fig.add_annotation(x=n - 1, y=y, text=txt, showarrow=False, xanchor="left", font=dict(size=10, color=col))
    res = C.res
    # ---- थर 1: pivots, संरक्षित, range
    for deg, col, size in ((1, "#b0bec5", 9), (2, "#ffd54f", 12)):
        ps = [p for p in res["pivots"][deg] if p.confirm_bar <= t and not p.warmup]
        for p in ps:
            x = X(p.bar)
            if x is None:
                continue
            up = p.kind == "H"
            fig.add_annotation(x=x, y=p.price, text=("D2 " if deg == 2 else "") + _lbl(ps, p), showarrow=False,
                               yshift=14 if up else -14, font=dict(size=size, color=col))
    s2 = C.st[2]["states"][t]
    if s2.get("protected") is not None and lo - 3 * (hi - lo) < s2["protected"] < hi + 3 * (hi - lo):
        hline(float(s2["protected"]), "#ff8a65", f"D2 संरक्षित {s2['protected']:,.0f}", dash="dot")
    if s2["trend"] == "RANGE":
        b = DE.range_band(C, t)
        if b is not None:
            fig.add_shape(type="rect", x0=0, x1=n - 1, y0=b[1], y1=b[0], fillcolor="rgba(144,164,174,0.06)",
                          line=dict(color="#90a4ae", width=1, dash="dot"), layer="below")
            fig.add_annotation(x=0, y=b[0], text="D2 range पट्टा", showarrow=False, xanchor="left", yshift=8,
                               font=dict(size=10, color="#90a4ae"))
    # ---- थर 4: zones (trade-बाजूचे + उलट, जवळचे)
    l4 = C.L4.get(t) or {}
    zs = {z["id"]: z for z in (C.Z.snap.get(t) or [])}
    for zid in (l4.get("next") or [])[:3] + (l4.get("opp") or [])[:1]:
        z = zs.get(zid)
        if z is None or z["status"] == "dead":
            continue
        x0 = X(z["pivot_bar"]) if z.get("pivot_bar") is not None else None
        sell = z["role"] == "seller"
        fig.add_shape(type="rect", x0=x0 if x0 is not None else 0, x1=n - 1, y0=z["bottom"], y1=z["top"],
                      fillcolor="rgba(239,83,80,0.12)" if sell else "rgba(38,166,154,0.12)", line_width=0, layer="below")
        fig.add_annotation(x=n - 1, y=(z["top"] + z["bottom"]) / 2, text=f"{ROLE_MR[z['role']]} zone {'★' * int(z.get('stars', 1))}",
                           showarrow=False, xanchor="left", font=dict(size=10, color="#ef9a9a" if sell else "#80cbc4"))
    # ---- थर 5: trade-योग्य रेघा + K आधार
    l5 = C.L5.get(t) or {}
    tsi = {str(x): i for i, x in enumerate(C.ts)}
    lines = [(x, "#ef5350" if x["kind"] == "H" else "#26a69a", f"रेघ ({x['touches']['held']} स्पर्श)")
             for x in (l5.get("lines") or []) if x.get("class") == "trade-योग्य"]
    kb = (l5.get("k_lines") or {}).get("base")
    if kb:
        lines.append((kb, "#42a5f5", "K आधार-रेघ"))
    for x, col, txt in lines:
        b1, b2 = tsi.get(x["a1"]["ts"]), tsi.get(x["a2"]["ts"])
        if b1 is None or b2 is None or b1 == b2:
            continue
        sl = (x["a2"]["price"] - x["a1"]["price"]) / (b2 - b1)
        j0 = max(b1, off)
        fig.add_trace(go.Scatter(x=[X(j0), n - 1], y=[x["a1"]["price"] + sl * (j0 - b1), x["a1"]["price"] + sl * (t - b1)], mode="lines",
                                 line=dict(color=col, width=2, dash="dash" if col == "#42a5f5" else "solid"), showlegend=False,
                                 hoverinfo="skip"))
        fig.add_annotation(x=n - 1, y=x["a1"]["price"] + sl * (t - b1), text=txt, showarrow=False, xanchor="left", yshift=-10,
                           font=dict(size=10, color=col))
    # ---- थर 2: I आणि K
    I = C.trk[1].I_at(t)
    st = C.trk[1].state(t)
    if I is not None:
        xo, xe = X(I["origin"].bar), X(I["end"].bar)
        if xo is not None and xe is not None:
            fig.add_trace(go.Scatter(x=[xo, xe], y=[I["origin"].price, I["end"].price], mode="lines", line=dict(color="#fff176", width=3),
                                     opacity=0.55, showlegend=False, hoverinfo="skip"))
        for xx, y, txt in ((xo, I["origin"].price, "I सुरुवात"), (xe, I["end"].price, "I टोक")):
            if xx is not None:
                fig.add_annotation(x=xx, y=y, text=txt, showarrow=True, arrowhead=2, ax=0, ay=-34 if y >= I["origin"].price else 34,
                                   font=dict(size=11, color="#fff176"), arrowcolor="#fff176")
        kx = (st.get("K") or {}).get("extreme")
        if kx is not None:
            hline(float(kx), "#ce93d8", f"K टोक {kx:,.0f}", dash="dot", w=1)
    # ---- थर 6: RSI divergence (price वर)
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
        fig.add_shape(type="rect", x0=max(n - 12, 0), x1=n - 1, y0=ar["band"][0], y1=ar["band"][1], fillcolor="rgba(255,213,79,0.16)",
                      line=dict(color="#ffd54f", width=1), layer="below")
        fig.add_annotation(x=max(n - 12, 0), y=ar["band"][1], text=f"area ({ar.get('src')})", showarrow=False, xanchor="left", yshift=8,
                           font=dict(size=10, color="#ffd54f"))
    cm = (p.get("9_price_failure") or {}).get("candle")
    if cm:
        x = X(cm["candle"]["t"])
        if x is not None:
            fig.add_annotation(x=x, y=cm["candle"]["h"], text="⭐ commitment", showarrow=False, yshift=16, font=dict(size=12, color="#ffd54f"))
    rk = p.get("10_risk")
    if rk and dec["decision"] == "setup":
        for nm, y, col in (("SL", rk["invalidation"], "#ef5350"), ("लक्ष्य", rk["target"], "#26a69a"), ("प्रवेश", rk["entry"], "#ffd54f")):
            hline(float(y), col, f"{nm} {y:,.0f}", w=1.5)
    fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                       text=box7(C, dec, t, st, I, l4, l5, l6), font=dict(size=11), bgcolor="rgba(14,17,23,0.90)", bordercolor="#455a64",
                       borderwidth=1)
    BC._finish(fig, d, lo, hi, fmt="%d %b %H:%M")
    return fig


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
        rows.append(f"<b>थर 2</b> · I {'↑' if I['dir'] > 0 else '↓'} {MODE_MR.get(I['mode'], I['mode'])} · {st.get('state')}"
                    + (f" · खोली {dep:.2f}" if dep is not None else ""))
    rows.append(f"<b>थर 3</b> · pattern {(pref or {}).get('family', '—')} / {(pref or {}).get('state', '—')} · momentum {m.get('verdict') or '—'}")
    rows.append(f"<b>थर 4</b> · K area (zone): {ka.get('ans', 'NA')}")
    rows.append(f"<b>थर 5</b> · K area (रेघ): {la.get('ans', 'NA')}" + (" · K आधार break" if (l5.get("k_base") or {}).get("bar") == t else ""))
    rows.append(f"<b>थर 6</b> · RSI: {l6.get('label') or '—'}" + (f" ({l6['rsi15']:.0f})" if l6.get("rsi15") is not None else ""))
    reg = ((dec.get("points") or {}).get("1_htf_state") or {}).get("regime") or {}
    rows.append(f"<b>थर 7</b> · {DC.DEC_MR[dec['decision']]}" + (f" · grade {dec['grade']}" if dec["decision"] == "setup" else
                                                               f" · {dec['gate']}: {dec['where_wrong']}")
                + f" · regime {REG_MR.get(reg.get('regime'), '—')}")
    return "<br>".join(rows)


def charts(C, dec, t):
    m = C.m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    title = "🧭 सातही थर · NIFTY {tf} · {d:%d %b %Y %H:%M}"
    return {"15M": PC.png(figure15(C, dec, t, title.format(tf="15M", d=asof))),
            "1H": PC.png(DC.figure(PC.window(PC.agg_1h(m), "1H", asof), dec, C, t, title.format(tf="1H", d=asof)))}


def caption(n, total, asof, dec, why=None):
    p = dec.get("points") or {}
    reg = ((p.get("1_htf_state") or {}).get("regime") or {}).get("regime")
    lines = [f"🧭 सातही थर {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर"),
             f"निर्णय: {DC.DEC_MR[dec['decision']]}" + (f" · grade {dec['grade']} · size {dec['size_weight']}" if dec["decision"] == "setup"
                                                        else f" · कारण: {dec['where_wrong']}"),
             f"regime: {REG_MR.get(reg, '—')} · momentum: {(p.get('4_character') or {}).get('momentum') or '—'}",
             "Reply: ✔ बरोबर वाचलं · ✘ कोणता थर चुकला (1–7) आणि का"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)
