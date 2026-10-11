"""legs2/charts.py — 🧭 LEG CHECK charts (थर 2 §4): 15M (D1 legs + D0 ठिपके + futures RVOL panel), 1H (D2 legs), Daily (D3 legs).

Leg रंग: आवेग = जाड हिरवी (वर) / लाल (खाली) रेघ · सुधार = तुटक रेघ · विरोध-1 / विरोध-2 = जांभळी, लेबलसह · कमकुवत / बरोबरी / अज्ञात = फिकी.
प्रत्येक leg वर छोटं लेबल (R, C, V, रचना). I ला कंस (origin → end), K चा भाग फिक्या रंगात. किंमती फक्त OHLC / pivots मधून.
"""
import io

import numpy as np
import pandas as pd

import instruments as INS
from backtest_review import charts as BC
from pivots import charts as PC
from vision_led import charts as VC

from . import ik as LI
from . import measure as LM
from . import settings as LS

UP, DN, PURPLE, FAINT = "#26a69a", "#ef5350", "#b388ff", "rgba(176,190,197,0.45)"


def style(L):
    lab = L["label"]
    col = UP if L["dir"] > 0 else DN
    if lab == "आवेग":
        return dict(color=col, width=4, dash="solid"), 1.0
    if lab in LM.CONFLICT_LABELS:
        return dict(color=PURPLE, width=3, dash="solid"), 1.0
    if lab == "सुधार":
        return dict(color=col, width=2, dash="dash"), 1.0
    if lab == "सुधार (कमकुवत)":
        return dict(color=FAINT, width=2, dash="dash"), 0.6
    return dict(color=FAINT, width=2, dash="solid"), 0.6                       # आवेग (कमकुवत) / बरोबरी / अज्ञात


def short_tag(L):
    p = []
    if L.get("R") is not None:
        p.append(f"R{L['R']:.1f}" if np.isfinite(L["R"]) else "R∞")
    p.append(f"C{L['C']:.2f}" if L.get("C") is not None else "C NA")
    if L.get("V") is not None:
        p.append(f"V{L['V']:.1f}")
    st = L.get("structure")
    if st and st.get("note"):
        p.append(st["note"])
    if L.get("weak"):
        p.append(f"{L['nature']}(क)")
    if L.get("gap"):
        p.append(f"gap{L['gap_sigma']:.1f}σ")
    return " ".join(p)


def _x(frame, ts):
    return PC._x_of(frame, ts)


def figure(frame, tf, legs, cur, d0, ikst, title, rv=None, bad=None, box=None):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    d = frame.reset_index(drop=True)
    vol = rv is not None
    fig = make_subplots(rows=2 if vol else 1, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22] if vol else [1.0],
                        vertical_spacing=0.03)
    x = np.arange(len(d))
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"], showlegend=False,
                                 increasing_line_color=UP, decreasing_line_color=DN), row=1, col=1)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    t0 = pd.to_datetime(d["timestamp"]).min()
    for L in legs + ([cur] if cur else []):
        a = L["a"]
        if pd.Timestamp(a.ts) < t0:                                             # window च्या आधी सुरू झालेला leg: दाखवत नाही
            continue
        ts_b, pb = (L["end_ts"], L["end_price"]) if L.get("current") else (L["b"].ts, L["b"].price)
        xa, xb, ya = _x(d, a.ts), _x(d, ts_b), a.price
        if xa is None or xb is None:
            continue
        line, op = style(L)
        if L.get("current"):
            line = dict(color="#ffd54f", width=2, dash="dot")
        fig.add_trace(go.Scatter(x=[xa, xb], y=[ya, pb], mode="lines", line=line, opacity=op, showlegend=False, hoverinfo="skip"),
                      row=1, col=1)
        tag = ("चालू · " if L.get("current") else "") + (L["label"] + " · " if L["label"] in LM.CONFLICT_LABELS else "") + short_tag(L)
        fig.add_annotation(x=(xa + xb) / 2, y=(ya + pb) / 2, text=tag, showarrow=False, font=dict(size=9, color=line["color"]),
                           bgcolor="rgba(14,17,23,0.6)", xshift=-28 if L["dir"] > 0 else 28, row=1, col=1)
    if d0:
        xs, ys, cs = [], [], []
        for p in d0:
            if pd.Timestamp(p.ts) < t0:
                continue
            xx = _x(d, p.ts)
            if xx is None:
                continue
            xs.append(xx)
            ys.append(p.price)
            cs.append(DN if p.kind == "H" else UP)
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", marker=dict(size=5, color=cs), showlegend=False, hoverinfo="skip"),
                          row=1, col=1)
    I = (ikst or {}).get("I")
    if I:
        to = pd.Timestamp(I["origin"]["ts"])
        xo = _x(d, to) if to >= t0 else 0
        xe = _x(d, I["end"]["ts"]) if pd.Timestamp(I["end"]["ts"]) >= t0 else None
        if xe is not None:
            xk = len(d) - 1
            col = UP if I["dir"] > 0 else DN
            yb = (lo - 0.03 * (hi - lo)) if I["dir"] > 0 else (hi + 0.03 * (hi - lo))
            fig.add_shape(type="line", x0=xo, x1=xe, y0=yb, y1=yb, line=dict(color=col, width=3), row=1, col=1)
            for xx in (xo, xe):
                fig.add_shape(type="line", x0=xx, x1=xx, y0=yb, y1=yb + (1 if I["dir"] > 0 else -1) * 0.04 * (hi - lo),
                              line=dict(color=col, width=3), row=1, col=1)
            fig.add_annotation(x=(xo + xe) / 2, y=yb, text=f"I {I['origin']['price']:,.0f} → {I['end']['price']:,.0f}"
                               + (" (origin chart च्या आधी)" if to < t0 else ""), showarrow=False, yshift=-12 if I["dir"] > 0 else 12,
                               font=dict(size=11, color=col), row=1, col=1)
            if xk > xe:
                fig.add_vrect(x0=xe, x1=xk + 0.5, fillcolor="rgba(255,213,79,0.06)", line_width=0, layer="below", row=1, col=1)
                fig.add_annotation(x=xk, y=hi, text=f"अवस्था: {ikst['state']}", showarrow=False, xanchor="right", yanchor="top",
                                   font=dict(size=11, color="#ffd54f"), row=1, col=1)
    if vol:
        rvw, bw = rv, bad
        vh, vl = float(LS.DEFAULTS["v_hi"]), float(LS.DEFAULTS["v_lo"])
        cols = ["#78909c" if b else ("#26a69a" if np.isfinite(r) and r >= vh else ("#ef5350" if np.isfinite(r) and r <= vl else "#546e7a"))
                for r, b in zip(rvw, bw)]
        fig.add_trace(go.Bar(x=x, y=np.where(np.isfinite(rvw), rvw, 0.0), marker_color=cols, showlegend=False, hoverinfo="skip"),
                      row=2, col=1)
        for yv in (vh, vl):
            fig.add_shape(type="line", x0=0, x1=len(d) - 1, y0=yv, y1=yv, line=dict(color="#90a4ae", width=1, dash="dot"), row=2, col=1)
        if not np.isfinite(rvw).any():
            fig.add_annotation(x=0.5, y=0.08, xref="paper", yref="paper", text="futures volume नाही ⇒ V तटस्थ", showarrow=False,
                               font=dict(size=11, color="#90a4ae"))
        fig.update_yaxes(title_text="RVOL", row=2, col=1, side="right", gridcolor="#263238")
    fig.add_annotation(x=0.5, y=0.6, xref="paper", yref="paper", text={"D": "DAILY"}.get(tf, tf), showarrow=False,
                       font=dict(size=140, color="rgba(255,255,255,0.07)"))
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=box, font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    fig.update_layout(template="plotly_dark", width=BC.W, height=BC.H + (160 if vol else 0), margin=dict(l=10, r=80, t=60, b=40),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=16)), showlegend=False,
                      font=dict(size=13))
    ticks, labels = VC._x_ticks(d, fmt="%d %b" if tf == "D" else "%d %b %H:%M", n=10)
    pad = 0.08 * ((hi - lo) or 1.0)
    fig.update_xaxes(tickvals=ticks, ticktext=labels, rangeslider_visible=False, showgrid=False)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", range=[lo - pad, hi + pad], row=1, col=1)
    return fig


def box_text(st1, st2):
    def ik(st, nm):
        I = st.get("I")
        if not I:
            return f"<b>{nm}</b>: I नाही"
        k = st.get("K") or {}
        extra = (f" · खोली {k.get('depth_pct')}% · वेळ ×{k.get('time_ratio')}" if st["state"] == LI.ST_K else
                 (f" · परत {st.get('retrace_pct')}%" if st.get("retrace_pct") is not None else ""))
        return (f"<b>{nm}</b>: I {'वर' if I['dir'] > 0 else 'खाली'} {I['origin']['price']:,.0f} → {I['end']['price']:,.0f} "
                f"({I['size_sigma']}σ, {I['legs']} legs{', origin उघडा' if I['origin_open'] else ''}) · {st['state']}{extra}")
    return "<br>".join([ik(st1, "15M (D1)"), ik(st2, "1H (D2)")])


def charts(lg, asof, sts):
    """एका दिवस-अखेरचे तीन charts ⇒ {tf: png}."""
    res = lg["res"]
    m15 = res["m15"]
    end = int((pd.to_datetime(m15["bar_end"]) <= pd.Timestamp(asof)).sum())
    m = m15.iloc[:end]
    t = pd.Timestamp(asof)
    title = "🧭 LEG CHECK · " + INS.label() + " {tf} · {d:%d %b %Y} दिवस-अखेर · {deg}"
    out = {}
    box = box_text(sts[1], sts[2])
    w15 = PC.window(m, "15M", asof)
    off = len(m) - len(w15)
    cur1 = _cur(lg, 1, asof, m15)
    out["15M"] = PC.png(figure(w15, "15M", LM.known(lg, 1, asof), cur1, PE_known(res, 0, asof), sts[1],
                               title.format(tf="15M", d=t, deg="D1 legs + D0 ठिपके"), rv=lg["rv"][off:end], bad=lg["bad"][off:end],
                               box=box))
    h1 = PC.window(PC.agg_1h(m), "1H", asof)
    out["1H"] = PC.png(figure(h1, "1H", LM.known(lg, 2, asof), _cur(lg, 2, asof, m15), None, sts[2],
                              title.format(tf="1H", d=t, deg="D2 legs")))
    daily = PC.daily_from_15m(m, asof)
    out["D"] = PC.png(figure(daily, "D", LM.known(lg, 3, asof), None, None, None,
                             title.format(tf="Daily", d=t, deg="D3 legs (संदर्भ)")))
    return out


def PE_known(res, d, asof):
    from pivots import engine as PE
    return PE.known(res, d, asof)


def _cur(lg, d, asof, m15):
    L = LM.current(lg, d, asof)
    if L is not None:
        L["end_ts"] = pd.Timestamp(m15["timestamp"].iloc[L["end_bar"]])
    return L


def caption(n, total, asof, sts):
    """≤ 8 ओळी, ≤ 1024 (UTF-16), code keys नाहीत."""
    def imp(st):
        I = st.get("I")
        return "नाही" if not I else f"{I['origin']['price']:,.0f} → {I['end']['price']:,.0f} · {I['size']:,.0f} अंक"

    def kk(st):
        if not st.get("I"):
            return "—"
        if st["state"] == LI.ST_K:
            k = st["K"]
            return f"{st['state']} · खोली {k['depth_pct']}% · वेळ ×{k['time_ratio']}"
        return st["state"] + (f" · परत {st['retrace_pct']}%" if st.get("retrace_pct") is not None else "")
    lines = [f"🧭 LEG CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y}",
             f"15M impulse: {imp(sts[1])}",
             f"15M correction: {kk(sts[1])}",
             f"1H impulse / correction: {imp(sts[2])} · {kk(sts[2])}",
             f"विरोध असलेले legs: {sts.get('conflicts', 0)}",
             "Reply: ✔ बरोबर · ✘ कोणता leg / I / K चुकला"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]                    # Reply ओळ आणि शीर्षक कधीच कापत नाही
    return "\n".join(lines)


def table_png(rows, title):
    import plotly.graph_objects as go
    head = list(rows[0].keys()) if rows else ["—"]
    fig = go.Figure(go.Table(header=dict(values=head, fill_color="#263238", font=dict(color="white", size=12)),
                             cells=dict(values=[[r.get(c, "—") for r in rows] for c in head], height=28, fill_color="#0e1117",
                                        font=dict(color="white", size=11), align="left")))
    fig.update_layout(title=title, template="plotly_dark", width=1600, height=900, paper_bgcolor="#0e1117")
    return PC.png(fig)


def grid3(pngs):
    from PIL import Image
    ims = [Image.open(io.BytesIO(pngs[k])).convert("RGB") for k in ("15M", "1H", "D")]
    w = max(i.size[0] for i in ims)
    h0 = ims[0].size[1]
    h1 = max(ims[1].size[1], ims[2].size[1])
    page = Image.new("RGB", (2 * w, h0 + h1), "#0e1117")
    page.paste(ims[0], (0, 0))
    page.paste(ims[1], (0, h0))
    page.paste(ims[2], (w, h0))
    buf = io.BytesIO()
    page.save(buf, "PNG")
    return buf.getvalue()
