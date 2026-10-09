"""decision2/charts.py — 🧭 DECISION CHECK (थर 7 §9): 15M decision chart (⭐ commitment candle, invalidation / target, gates ✓✗,
grade, size, momentum, divergence) + 1H. Caption मराठी, code keys नाहीत."""
import pandas as pd

from backtest_review import charts as BC
from pivots import charts as PC

GATES = ("G-A", "G-B", "G-C", "G-D", "G-E", "G-F", "G-G", "G-H", "G-I")
DEC_MR = {"setup": "📌 setup", "wait": "थांबा", "no_trade": "trade नाही"}


def gate_line(dec):
    g = dec.get("gate")
    out = []
    for x in GATES:
        if dec["decision"] == "setup":
            out.append(f"{x}✓")
        elif x == g:
            out.append(f"{x}✗")
            break
        else:
            out.append(f"{x}✓")
    return " ".join(out)


def figure(frame, dec, C, t, title, box=None):
    import plotly.graph_objects as go
    d = frame.reset_index(drop=True)
    fig = BC._base(d, title)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    pf = (dec.get("points") or {}).get("9_price_failure") or {}
    cm = pf.get("candle")
    if cm:
        x = PC._x_of(d, C.ts[cm["candle"]["t"]])
        if x is not None:
            fig.add_trace(go.Scatter(x=[x], y=[cm["candle"]["h"]], mode="text", text=["⭐"], textfont=dict(size=18), showlegend=False,
                                     hoverinfo="skip"))
    rk = (dec.get("points") or {}).get("10_risk")
    if rk:
        for nm, y, col in (("invalidation", rk["invalidation"], "#ef5350"), ("target", rk["target"], "#26a69a"), ("entry", rk["entry"], "#ffd54f")):
            fig.add_shape(type="line", x0=0, x1=len(d) - 1, y0=y, y1=y, line=dict(color=col, width=1.5, dash="dash"))
            fig.add_annotation(x=len(d) - 1, y=y, text=f"{nm} {y:,.0f}", showarrow=False, xanchor="left", font=dict(size=10, color=col))
    ar = (dec.get("points") or {}).get("7_area")
    if ar and ar.get("band"):
        fig.add_shape(type="rect", x0=0, x1=len(d) - 1, y0=ar["band"][0], y1=ar["band"][1], fillcolor="rgba(255,213,79,0.10)", line_width=0,
                      layer="below")
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=box, font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    BC._finish(fig, d, lo, hi, fmt="%d %b %H:%M")
    return fig


def box_text(dec):
    p = dec.get("points") or {}
    reg = ((p.get("1_htf_state") or {}).get("regime") or {}).get("regime")
    mom = (p.get("4_character") or {}).get("momentum")
    rows = [f"<b>{DEC_MR[dec['decision']]}</b>" + (f" · {dec['gate']}: {dec['where_wrong']}" if dec["decision"] != "setup" else
                                                   f" · grade {dec['grade']} ({dec['grade_score']}) · size {dec['size_weight']}"),
            f"gates: {gate_line(dec)}", f"regime: {reg or '—'} · momentum: {mom or '—'}"]
    pf = p.get("9_price_failure") or {}
    if pf.get("flavours"):
        rows.append("flavour: " + ", ".join(pf["flavours"]))
    rk = p.get("10_risk")
    if rk:
        rows.append(f"R:R {rk['rr']} · invalidation {rk['invalidation']:,.0f} ({rk['invalidation_mode']})")
    if dec.get("flags"):
        rows.append("नोंद: " + ", ".join(dec["flags"]))
    return "<br>".join(rows)


def charts(C, dec, t):
    m = C.m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    title = "🧭 DECISION CHECK · NIFTY {tf} · {d:%d %b %Y %H:%M}"
    return {"15M": PC.png(figure(PC.window(m, "15M", asof), dec, C, t, title.format(tf="15M", d=asof), box_text(dec))),
            "1H": PC.png(figure(PC.window(PC.agg_1h(m), "1H", asof), dec, C, t, title.format(tf="1H", d=asof)))}


def caption(n, total, asof, dec, why=None):
    p = dec.get("points") or {}
    reg = ((p.get("1_htf_state") or {}).get("regime") or {}).get("regime")
    REG = {"trend_up": "trend वर", "trend_down": "trend खाली", "range": "range", "barbwire": "barbwire", "transition": "transition",
           "drift": "drift"}
    lines = [f"🧭 DECISION CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर"),
             f"निर्णय: {DEC_MR[dec['decision']]}" + (f" · grade {dec['grade']} · size {dec['size_weight']}" if dec["decision"] == "setup"
                                                     else f" · कारण: {dec['where_wrong']}"),
             f"regime: {REG.get(reg, '—')}",
             f"momentum: {(p.get('4_character') or {}).get('momentum') or '—'}",
             "Reply: ✔ मी घेतला असता · ✘ मी घेतला नसता — का"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)


def moments(D, bars, k):
    out, prev = [], None
    for t in bars[:-1]:
        d = D.get(t) or {}
        key = (d.get("decision"), d.get("gate"))
        why = None
        if d.get("decision") == "setup" and (prev is None or prev[0] != "setup"):
            why = "setup"
        elif prev is not None and key != prev and d.get("gate") in ("G-E", "G-D", "G-C"):
            why = f"gate बदल ({d.get('gate')})"
        if why:
            out.append((t, why))
        prev = key
        if len(out) >= k:
            break
    return out


def rows(D, t0, t1):
    ds = [D[t] for t in D if t0 <= t <= t1]
    by = {}
    for d in ds:
        k = d["decision"] if d["decision"] == "setup" else f"{d['decision']}:{d['gate']}"
        by[k] = by.get(k, 0) + 1
    gr = {}
    for d in ds:
        if d["decision"] == "setup":
            gr[d["grade"]] = gr.get(d["grade"], 0) + 1
    return [{"निर्णय वाटप (bars)": ", ".join(f"{k}:{v}" for k, v in sorted(by.items())),
             "setup grade": ", ".join(f"{k}:{v}" for k, v in sorted(gr.items())) or "—", "bars": len(ds)}]


def register_rows():
    from . import settings as DS
    return [{"आकडा": k, "default": str(v[0]), "पर्याय": str(v[1]), "वर्ग": v[2], "स्रोत": v[3]} for k, v in DS.REGISTER.items()]
