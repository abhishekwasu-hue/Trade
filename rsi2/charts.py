"""rsi2/charts.py — 🧭 RSI CHECK (थर 6 §5): 15M + RSI panel (pivots वर RSI ठिपके, divergence रेघा, 30/40/60/70 रेघा, rsi_range पट्टी),
1H तसंच. Box: rsi_range (15M, 1H), शेवटची divergence + label, K जोडणी, final momentum verdict (थर 4 re-emit)."""
import numpy as np
import pandas as pd

import instruments as INS
from pivots import charts as PC
from vision_led import charts as VC

COL = {"regular_bull": "#26a69a", "hidden_bull": "#80cbc4", "regular_bear": "#ef5350", "hidden_bear": "#ef9a9a"}
RNG = {"bull_range": "rgba(38,166,154,0.25)", "bear_range": "rgba(239,83,80,0.25)", "neutral": "rgba(144,164,174,0.2)", None: "rgba(0,0,0,0)"}


def figure(frame, rsi, divs, title, ranges=None, box=None, tf="15M"):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    d = frame.reset_index(drop=True)
    n = len(d)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32], vertical_spacing=0.03)
    x = np.arange(n)
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"], showlegend=False,
                                 increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=rsi, mode="lines", line=dict(color="#ffd54f", width=1.5), showlegend=False, hoverinfo="skip"), row=2, col=1)
    for yv in (30, 40, 60, 70):
        fig.add_shape(type="line", x0=0, x1=n - 1, y0=yv, y1=yv, line=dict(color="#90a4ae", width=1, dash="dot"), row=2, col=1)
    if ranges is not None:
        for i, rg in enumerate(ranges):
            if rg:
                fig.add_shape(type="rect", x0=i - 0.5, x1=i + 0.5, y0=0, y1=6, fillcolor=RNG.get(rg), line_width=0, row=2, col=1)
    for dv in divs:
        xa, xb = PC._x_of(d, dv["L1"]["ts"]), PC._x_of(d, dv["L2"]["ts"])
        if xa is None or xb is None:
            continue
        c = COL[dv["type"]]
        fig.add_trace(go.Scatter(x=[xa, xb], y=[dv["L1"]["price"], dv["L2"]["price"]], mode="lines+markers", line=dict(color=c, width=2),
                                 showlegend=False, hoverinfo="skip"), row=1, col=1)
        fig.add_trace(go.Scatter(x=[xa, xb], y=[dv["rsi1"], dv["rsi2"]], mode="lines+markers", line=dict(color=c, width=2),
                                 showlegend=False, hoverinfo="skip"), row=2, col=1)
        tag = dv["type"].replace("_", " ") + (f" · {dv['grade']}" if dv.get("grade") else "") + (" · gap" if dv.get("gap_between") else "") + \
            (f" · {dv['tag']}" if dv.get("tag") else "")
        fig.add_annotation(x=xb, y=dv["rsi2"], text=tag, showarrow=False, yshift=12, font=dict(size=9, color=c), row=2, col=1)
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=box, font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    pad = 0.08 * ((hi - lo) or 1.0)
    fig.update_layout(template="plotly_dark", width=1600, height=1000, margin=dict(l=10, r=80, t=60, b=40), paper_bgcolor="#0e1117",
                      plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=16)), showlegend=False)
    ticks, labels = VC._x_ticks(d, fmt="%d %b %H:%M", n=10)
    fig.update_xaxes(tickvals=ticks, ticktext=labels, rangeslider_visible=False, showgrid=False)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", range=[lo - pad, hi + pad], row=1, col=1)
    fig.update_yaxes(side="right", range=[0, 100], gridcolor="#263238", row=2, col=1)
    return fig


def box_text(r):
    def rg(x):
        return "—" if not x or not x.get("range") else x["range"] + (f" · shift {x['warn']}" if x.get("warn") else "") + \
            (" (confirmed)" if x.get("confirmed") else "")
    last = r.get("last")
    rows = [f"<b>rsi_range</b>: 15M {rg(r['rsi_range_15m'])} · 1H {rg(r['rsi_range_1h'])}" + (" · rsi_disagree" if r["rsi_disagree"] else ""),
            "शेवटची divergence: " + ("—" if not last else f"{last['type']} D{last['degree']} ({last['rsi1']:.0f} → {last['rsi2']:.0f})"),
            f"on_K: {'✓ ' + r['on_K']['ref'] if r['on_K'] else '—'} · regular_in_K: {'✓' if r['regular_in_K'] else '—'} · "
            f"at_impulse_end: {'✓' if r['at_impulse_end'] else '—'} · cascade: {'✓' if r['cascade'] else '—'}",
            f"<b>label</b>: {r['label'] or '—'}", f"momentum (थर 4): {r.get('momentum') or '—'}"]
    return "<br>".join(rows)


def charts(R, r, t):
    m = R.res["m15"].iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    w = PC.window(m, "15M", asof)
    off = len(m) - len(w)
    divs = [dict(x) for x in R.known(t)[-6:]]
    for nm in ("on_K", "regular_in_K", "at_impulse_end"):
        if r.get(nm):
            divs.append(dict(r[nm], tag=nm))
    ranges = [R.classify(i, "15M").get("range") for i in range(off, t + 1)]
    title = "🧭 RSI CHECK · " + INS.label() + " {tf} · {d:%d %b %Y %H:%M}"
    p15 = PC.png(figure(w, R.r15[off:t + 1], divs, title.format(tf="15M", d=asof), ranges, box_text(r)))
    h1 = PC.window(PC.agg_1h(m), "1H", asof)
    k = R.bar_to_h1[t]
    rr = R.r1h[max(k - len(h1) + 1, 0):k + 1] if k >= 0 else np.full(len(h1), np.nan)
    rr = np.r_[np.full(max(len(h1) - len(rr), 0), np.nan), rr][-len(h1):]
    p1h = PC.png(figure(h1, rr, [x for x in divs if x["degree"] == 2], title.format(tf="1H", d=asof), tf="1H"))
    return {"15M": p15, "1H": p1h}


def caption(n, total, asof, r, why=None):
    def rg(x):
        return {"bull_range": "bull", "bear_range": "bear", "neutral": "neutral"}.get((x or {}).get("range"), "—")
    last = r.get("last")
    lines = [f"🧭 RSI CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर"),
             f"RSI range: 15M {rg(r['rsi_range_15m'])} · 1H {rg(r['rsi_range_1h'])}",
             "शेवटची divergence: " + ("—" if not last else {"regular_bull": "regular bull", "hidden_bull": "hidden bull",
                                                             "regular_bear": "regular bear", "hidden_bear": "hidden bear"}[last["type"]]),
             f"अर्थ: {r['label'] or '—'}",
             f"momentum: {r.get('momentum') or '—'}",
             "Reply: ✔ बरोबर · ✘ कोणती divergence चुकली / सुटली"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)


def moments(L6, bars, k):
    out, prev = [], {}
    for t in bars[:-1]:
        r = L6.get(t) or {}
        why = None
        if r.get("on_K") and not prev.get("on_K"):
            why = "on_K"
        elif r.get("at_impulse_end") and not prev.get("at_impulse_end"):
            why = "at_impulse_end"
        elif (r.get("rsi_range_15m") or {}).get("confirmed") and not (prev.get("rsi_range_15m") or {}).get("confirmed"):
            why = "range_shift_confirmed"
        if why:
            out.append((t, why))
        prev = r
        if len(out) >= k:
            break
    return out


def rows(R, L6, t0, t1):
    ds = [x for x in R.divs if t0 <= x["known_bar"] <= t1]
    ty = {}
    for x in ds:
        key = f"{x['type']} D{x['degree']}" + (f" {x['grade']}" if x.get("grade") else "")
        ty[key] = ty.get(key, 0) + 1
    rs = [L6[t] for t in L6 if t0 <= t <= t1]
    rg = {}
    for r in rs:
        k = (r["rsi_range_15m"] or {}).get("range")
        rg[k] = rg.get(k, 0) + 1
    return [{"divergences": ", ".join(f"{k}:{v}" for k, v in sorted(ty.items())),
             "on_K bars": sum(bool(r["on_K"]) for r in rs), "regular_in_K bars": sum(bool(r["regular_in_K"]) for r in rs),
             "cascade bars": sum(bool(r["cascade"]) for r in rs), "rsi_range 15M": ", ".join(f"{k}:{v}" for k, v in rg.items()),
             "rsi_disagree %": round(100 * sum(r["rsi_disagree"] for r in rs) / max(len(rs), 1))}]


# ================================================================================================ K-RSI verification plot (spec §8a)
DIV_COL = {("bear", "regular"): "#ef5350", ("bull", "regular"): "#26a69a", ("bear", "hidden"): "#ef9a9a", ("bull", "hidden"): "#80cbc4"}
CAP_COL = "#9e9e9e"


def merge_degrees(recs):
    """The same pivot pair found at several swings2 degrees ⇒ one chart line (degrees joined, the first record kept)."""
    out = {}
    for x in recs:
        k = (x["side"], x["type"], x["L1"]["bar"], x["L2"]["bar"], x["status"])
        if k in out:
            out[k]["degrees"].append(x["degree"])
        else:
            out[k] = dict(x, degrees=[x["degree"]])
    return list(out.values())


def div_rows(divs, caps):
    """Table rows under the chart (English): both pivots (time, price, RSI), bars apart, RSI difference, status, count, area."""
    rows = []
    for x in merge_degrees(divs) + merge_degrees(caps):
        area = (x.get("area") or {})
        rows.append({"kind": ("cap-rejected " if x.get("cap") else "") + ("hidden " if x["type"] == "hidden" else "") + x["side"] + " div",
                     "degree": "/".join(f"D{d}" for d in sorted(x["degrees"])),
                     "pivot 1": f"{pd.Timestamp(x['L1']['time']):%d %b %H:%M} · {x['L1']['price']:,.2f} · RSI {x['L1']['rsi']:.2f}",
                     "pivot 2": f"{pd.Timestamp(x['L2']['time']):%d %b %H:%M} · {x['L2']['price']:,.2f} · RSI {x['L2']['rsi']:.2f}",
                     "bars": x["bars"], "RSI diff": f"{x['rsi_diff']:+.2f}",
                     "status": x["status"] + (f" ({x['status_by'].replace('_', ' ')})" if x.get("status_by") else ""),
                     "count": x.get("count", "—") if not x.get("cap") else "—",
                     "area": "—" if x.get("cap") else (area.get("status", "—") + (
                         f" {area['band']['role']} {area['band']['lo']:,.0f}-{area['band']['hi']:,.0f}" if area.get("band") else ""))})
    return rows


def div_figure(frame, rsi, divs, caps, title, note=None):
    """Price pane + RSI pane (70 / 30 reference lines) + a facts table. Every divergence: the price-pivot line and the RSI-point line in
    one colour (red = bear, green = bull; dashed = forming) and a label at the second pivot ("bear div · confirmed · N bars · RSI a → b",
    "=" when equal). Pairs rejected only by the bar cap: thin grey dotted lines labelled "cap N bars". English only."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from . import engine as RE
    d = frame.reset_index(drop=True)
    n = len(d)
    rows = div_rows(divs, caps)
    main, tab_px = 940, (46 + 22 * len(rows)) if rows else 24
    fig = make_subplots(rows=3, cols=1, row_heights=[0.68 * main, 0.32 * main, tab_px], vertical_spacing=0.04,
                        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]])
    x = np.arange(n)
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"], showlegend=False,
                                 increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=rsi, mode="lines", line=dict(color="#ffd54f", width=1.5), showlegend=False, hoverinfo="skip"),
                  row=2, col=1)
    for yv in (30, 70):
        fig.add_shape(type="line", x0=0, x1=n - 1, y0=yv, y1=yv, line=dict(color="#90a4ae", width=1, dash="dot"), row=2, col=1)
    for c in merge_degrees(caps):
        xa, xb = PC._x_of(d, c["L1"]["time"]), PC._x_of(d, c["L2"]["time"])
        if xa is None or xb is None:
            continue
        ln = dict(color=CAP_COL, width=1, dash="dot")
        fig.add_trace(go.Scatter(x=[xa, xb], y=[c["L1"]["price"], c["L2"]["price"]], mode="lines", line=ln, showlegend=False,
                                 hoverinfo="skip"), row=1, col=1)
        ra, rb = PC._x_of(d, c["L1"]["rsi_time"]), PC._x_of(d, c["L2"]["rsi_time"])
        if ra is not None and rb is not None:
            fig.add_trace(go.Scatter(x=[ra, rb], y=[c["L1"]["rsi"], c["L2"]["rsi"]], mode="lines", line=ln, showlegend=False,
                                     hoverinfo="skip"), row=2, col=1)
        fig.add_annotation(x=xb, y=c["L2"]["price"], text=f"cap {c['bars']} bars", showarrow=False,
                           yshift=-14 if c["side"] == "bull" else 14, font=dict(size=9, color=CAP_COL), row=1, col=1)
    for k, v in enumerate(merge_degrees(divs)):
        xa, xb = PC._x_of(d, v["L1"]["time"]), PC._x_of(d, v["L2"]["time"])
        if xa is None or xb is None:
            continue
        col = DIV_COL[(v["side"], v["type"])]
        ln = dict(color=col, width=2, dash="dash" if v["status"] == "forming" else "solid")
        fig.add_trace(go.Scatter(x=[xa, xb], y=[v["L1"]["price"], v["L2"]["price"]], mode="lines+markers", line=ln, showlegend=False,
                                 hoverinfo="skip"), row=1, col=1)
        ra, rb = PC._x_of(d, v["L1"]["rsi_time"]), PC._x_of(d, v["L2"]["rsi_time"])
        if ra is not None and rb is not None:
            fig.add_trace(go.Scatter(x=[ra, rb], y=[v["L1"]["rsi"], v["L2"]["rsi"]], mode="lines+markers", line=ln, showlegend=False,
                                     hoverinfo="skip"), row=2, col=1)
        up = v["side"] == "bear"
        fig.add_annotation(x=xb, y=v["L2"]["price"], text=RE.div_label(v), showarrow=True, arrowhead=0, arrowcolor=col,
                           ax=0, ay=(-26 - 14 * (k % 3)) if up else (26 + 14 * (k % 3)), font=dict(size=10, color=col),
                           bgcolor="rgba(14,17,23,0.85)", row=1, col=1)
    if not divs:
        fig.add_annotation(x=0.01, y=0.95, xref="x2 domain", yref="y2 domain", xanchor="left", text="no divergence", showarrow=False,
                           font=dict(size=11, color="#b0bec5"))
    if note:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=note, font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    if rows:
        cols = list(rows[0])
        fig.add_trace(go.Table(header=dict(values=cols, fill_color="#263238", font=dict(color="#eceff1", size=11), align="left"),
                               cells=dict(values=[[r[c] for r in rows] for c in cols], fill_color="#11161c",
                                          font=dict(color="#cfd8dc", size=10), align="left", height=20),
                               columnwidth=[1.4, 0.7, 2.6, 2.6, 0.6, 0.8, 2.2, 0.6, 1.8]), row=3, col=1)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    pad = 0.16 * ((hi - lo) or 1.0)
    fig.update_layout(template="plotly_dark", width=1600, height=main + tab_px + 80, margin=dict(l=10, r=80, t=60, b=20),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=16)), showlegend=False)
    ticks, labels = VC._x_ticks(d, fmt="%d %b %H:%M", n=12)
    fig.update_xaxes(tickvals=ticks, ticktext=labels, rangeslider_visible=False, showgrid=False, row=1, col=1)
    fig.update_xaxes(tickvals=ticks, ticktext=labels, showgrid=False, matches="x", row=2, col=1)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", range=[lo - pad, hi + pad], row=1, col=1)
    fig.update_yaxes(side="right", range=[0, 100], gridcolor="#263238", tickvals=[30, 50, 70], row=2, col=1)
    return fig


def div_chart(D, t, focus_from, focus_to, title, context_bars=0, note=None):
    """PNG + the records drawn: frame = bars [focus_from − context_bars, t]; divergences / cap pairs known by t whose second pivot lies in
    [focus_from, focus_to] (each first pivot pulled into the frame)."""
    divs = [D.with_area(x) for x in D.history(t) if focus_from <= x["L2"]["bar"] <= focus_to]
    caps = [x for x in D.cap_log(t) if focus_from <= x["L2"]["bar"] <= focus_to]
    first = min([focus_from - context_bars] + [x["L1"]["bar"] - 2 for x in divs + caps])
    i0 = max(first, 0)
    fr = D.df.iloc[i0:t + 1].reset_index(drop=True)
    fig = div_figure(fr, D.rsi[i0:t + 1], divs, caps, title, note=note)
    return PC.png(fig), divs, caps


def register_rows():
    from . import settings as RS
    return [{"आकडा": k, "default": str(v[0]), "पर्याय": str(v[1]), "वर्ग": v[2], "स्रोत": v[3]} for k, v in RS.REGISTER.items()]
