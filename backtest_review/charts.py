"""backtest_review/charts.py — प्रत्येक trade साठी 3 images (1H context, 15M entry, 15M hindsight) आणि प्रत्येक दिवसासाठी 2 (1H, 15M सगळे
candidates). TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §2. Code चे labels; vision नाही. No-lookahead: entry chart entry bar च्या close पर्यंत,
दिवसाचा chart त्या दिवसाच्या शेवटापर्यंत (caller कापून देतो; `assert_upto` तपासतो). CAS bars राखाडी (vision_led.charts.cas_marks).
PNG फक्त trade-data / VPS archive मध्ये.
"""
import numpy as np
import pandas as pd

from vision_led import charts as VC

W, H = 1400, 860
DIRN = {1: "UP", -1: "DOWN", 0: "RANGE"}
STATUS_MARK = {"ENTRY": ("✅", "#00e676"), "C": ("🟡", "#ffd54f"), "REJECTED": ("✖", "#ef5350")}
TOOL_NAME = {"a": "swing cluster", "b": "flip", "c": "base", "d": "range edge", "e": "liquidity", "f": "TL", "g": "channel", "h": "Fib",
             "i": "C=A", "j": "round", "k": "PDH/PDL/PDC", "l": "gap"}


def assert_upto(df, t, what="chart"):
    """No-lookahead: df मध्ये t नंतर बंद होणारा bar नाही."""
    col = "bar_end" if "bar_end" in df.columns else "timestamp"
    if len(df) and (pd.to_datetime(df[col]) > pd.Timestamp(t)).any():
        raise AssertionError(f"lookahead: {what} मध्ये {t} नंतरचा data")


def _base(d, title):
    import plotly.graph_objects as go
    fig = go.Figure(go.Candlestick(x=np.arange(len(d)), open=d["open"], high=d["high"], low=d["low"], close=d["close"], showlegend=False,
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350"))
    fig.update_layout(template="plotly_dark", width=W, height=H, margin=dict(l=10, r=80, t=60, b=40), paper_bgcolor="#0e1117",
                      plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=16)), showlegend=False, font=dict(size=13))
    return fig


def _xmap(d):
    tsx = pd.to_datetime(d["timestamp"]).to_numpy(dtype="datetime64[ns]")

    def xi(t):
        return int(np.clip(np.searchsorted(tsx, np.datetime64(pd.Timestamp(t), "ns"), side="right") - 1, 0, max(len(d) - 1, 0)))
    return xi


def _finish(fig, d, lo, hi, fmt="%d %b %H:%M", n=10):
    ticks, labels = VC._x_ticks(d, fmt=fmt, n=n)
    pad = 0.06 * ((hi - lo) or 1.0)
    fig.update_xaxes(tickvals=ticks, ticktext=labels, rangeslider_visible=False, showgrid=False)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", range=[lo - pad, hi + pad])
    return fig


def _window(df, t_end, sessions, c=None, max_sessions=15):
    """किमान sessions इतके sessions, आणि impulse origin / area anchors दिसतील इतका (≤ max_sessions) — anchors x=0 ला चिकटू नयेत."""
    d = _sessions(df, t_end, max_sessions)
    base = _sessions(df, t_end, sessions)
    keep = [pd.to_datetime(base["timestamp"]).min()] if len(base) else []
    imp = (c or {}).get("impulse") or {}
    if imp.get("from_ts") is not None:
        keep.append(pd.Timestamp(imp["from_ts"]).normalize())
    for a in ((c or {}).get("area") or {}).get("anchors") or []:
        keep.append(pd.Timestamp(a[0]).normalize())
    if not keep or not len(d):
        return base
    return d[pd.to_datetime(d["timestamp"]) >= min(keep)].reset_index(drop=True)


def _sessions(df, t_end, sessions):
    col = "bar_end" if "bar_end" in df.columns else "timestamp"
    d = df[pd.to_datetime(df[col]) <= pd.Timestamp(t_end)]                 # फक्त t_end पर्यंत **बंद** bars
    days = pd.to_datetime(d["timestamp"]).dt.normalize().unique()
    if not len(days):
        return d.reset_index(drop=True)
    first = days[-sessions] if len(days) >= sessions else days[0]
    return d[pd.to_datetime(d["timestamp"]) >= first].reset_index(drop=True)


def _trend_box(fig, d, hi, trend, extra=""):
    tr = trend or {}
    p = tr.get("protected")
    txt = f"HTF trend: {DIRN.get(tr.get('dir', 0))}{' (testing — protected real break)' if tr.get('state') == 'testing' else ''}"
    if p:
        txt += f" · protected {p['kind']} {p['price']:,.1f}"
    fig.add_annotation(x=0, y=hi, text=txt + extra, showarrow=False, xanchor="left", yanchor="top", font=dict(size=14, color="#ffffff"),
                       bgcolor="rgba(0,0,0,0.7)")
    if p:
        fig.add_shape(type="line", x0=-0.5, x1=len(d) - 0.5, y0=p["price"], y1=p["price"], line=dict(color="#90a4ae", width=1, dash="dash"))


def _impulse_abc(fig, d, xi, imp, labels, ctype=None):
    import plotly.graph_objects as go
    if imp:
        col = "#00e676" if imp["dir"] > 0 else "#ff1744"
        fig.add_trace(go.Scatter(x=[xi(imp["from_ts"]), xi(imp["to_ts"])], y=[imp["from"], imp["to"]], mode="lines+markers",
                                 line=dict(color=col, width=5), marker=dict(size=9, color=col)))
        fig.add_annotation(x=xi(imp["from_ts"]), y=imp["from"], text=f"impulse {imp['from']:,.0f}", showarrow=True, ax=0,
                           ay=-30 if imp["dir"] < 0 else 30, font=dict(size=12, color=col))
    for lab in labels or []:
        up = lab["to"] > lab["from"]
        fig.add_trace(go.Scatter(x=[xi(lab["from_ts"]), xi(lab["to_ts"])], y=[lab["from"], lab["to"]], mode="lines",
                                 line=dict(color="#ffca28", width=2, dash="dot" if lab.get("tentative") else "solid")))
        text = f"<b>{lab['label']}</b>{'?' if lab.get('tentative') else ''}"
        if lab["label"] == "C" and ctype:
            text += f" ({ctype})"
        fig.add_annotation(x=xi(lab["to_ts"]), y=lab["to"], text=text, showarrow=False, yanchor="bottom" if up else "top",
                           font=dict(size=17, color="#ffca28"))


def _area(fig, d, xi, z, n_total, label=None, color="#42a5f5", width=2):
    import plotly.graph_objects as go
    if not z:
        return
    name = label or f"{TOOL_NAME.get(z.get('tool'), z.get('tool'))} {z.get('id')}"
    if z.get("tool") == "f" and z.get("anchors"):
        pts = [(xi(a[0]), float(a[1])) for a in z["anchors"]]
        k0, v0 = pts[0]
        slope = float(z.get("slope") or 0.0)
        fig.add_trace(go.Scatter(x=[k0, n_total - 1], y=[v0, v0 + slope * (n_total - 1 - k0)], mode="lines",
                                 line=dict(color=color, width=width + 1)))
        fig.add_trace(go.Scatter(x=[k for k, _ in pts], y=[v for _, v in pts], mode="markers",
                                 marker=dict(color=color, size=10, symbol="circle-open", line=dict(width=2))))
        fig.add_annotation(x=n_total - 1, y=v0 + slope * (n_total - 1 - k0), text=f"{name} ({len(pts)} touches)", showarrow=False,
                           xanchor="right", yanchor="bottom", font=dict(size=12, color=color))
    else:
        fig.add_shape(type="rect", x0=-0.5, x1=n_total - 0.5, y0=z["low"], y1=z["high"], fillcolor=color, opacity=0.18,
                      line=dict(color=color, width=width), layer="below")
        fig.add_annotation(x=0, y=z["high"], text=name, showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=12, color=color))


def context_1h(h1, c, title, elliott_line=None, areas=None, sessions=15):
    """1H context (entry / दिवस पर्यंत, ≥ 15 sessions): HTF trend + protected, मोठे areas (horizontal / flip / trendline anchors / range
    edge), impulse + correction, Elliott (gray असेल तर gray)."""
    d = _sessions(h1, c["bar_end"], sessions)
    assert_upto(d, c["bar_end"], "1H context")
    fig = _base(d, title)
    xi = _xmap(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    for z in (areas or [])[:8]:
        if z.get("tool") in ("a", "b", "d", "f") and (z["high"] >= lo and z["low"] <= hi or z.get("tool") == "f"):
            _area(fig, d, xi, z, len(d), color="#7e57c2" if z.get("tool") == "f" else "#42a5f5", width=1)
    _impulse_abc(fig, d, xi, c.get("impulse"), c.get("labels"))
    _trend_box(fig, d, hi, c.get("trend"), extra=f" · Elliott: {elliott_line or 'gray'}")
    return _finish(fig, d, lo, hi, fmt="%d %b", n=8)


def entry_15m(m15, c, title, cut=None, strike=None, sessions=5):
    """15M entry chart: entry bar च्या close पर्यंत, ≥ 5 sessions. Impulse (रंगीत), A-B-C + प्रकार, वापरलेले areas (साधन नावासह),
    reversal candle(s) ठळक, sweep खूण, ENTRY / SL (कुठून) / TARGET / R:R / strike, grade + मुख्य पुरावे, CAS राखाडी."""
    d = _window(m15, c["bar_end"], sessions, c)
    assert_upto(d, c["bar_end"], "15M entry")
    fig = _base(d, title)
    VC._draw_cas(fig, VC.cas_marks(cut, d))
    xi = _xmap(d)
    n = len(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    z = c.get("area")
    conf = ", ".join(TOOL_NAME.get(t, t) for t in c.get("confluence") or [])
    _area(fig, d, xi, z, n, label=(f"ACTIVE: {TOOL_NAME.get((z or {}).get('tool'), '')} {(z or {}).get('id', '')}"
                                   + (f" + {conf}" if conf else "")) if z else None, color="#ffca28", width=3)
    _impulse_abc(fig, d, xi, c.get("impulse"), c.get("labels"), c.get("ctype"))
    k = n - 1
    nrev = 2 if c.get("rev_comp") else 1
    for j in range(max(0, k - nrev + 1), k + 1):
        fig.add_shape(type="rect", x0=j - 0.45, x1=j + 0.45, y0=float(d["low"].iloc[j]), y1=float(d["high"].iloc[j]),
                      line=dict(color="#ffffff", width=2), fillcolor="rgba(0,0,0,0)")
    if c.get("lq"):
        fig.add_annotation(x=k, y=float(d["low"].iloc[k] if c["side"] > 0 else d["high"].iloc[k]), text="sweep", showarrow=True,
                           ay=30 if c["side"] > 0 else -30, font=dict(size=12, color="#80deea"))
    lines = []
    if c.get("entry_px") is not None:
        lines.append(("ENTRY", c["entry_px"], "#ffd54f", f"ENTRY {c['entry_px']:,.0f} · {pd.Timestamp(c['bar_start']):%d %b %H:%M}"))
    if c.get("inv") is not None:
        lines.append(("SL", c["inv"], "#ef5350", f"SL {c['inv']:,.0f} ({c.get('inv_src') or '—'} + buffer)"))
    for t in (c.get("targets") or [])[:1]:
        lines.append(("TG", t["price"], "#66bb6a", f"TARGET {t['price']:,.0f} ({t['id']})"))
    if strike is not None:
        lines.append(("STRIKE", strike, "#ab47bc", f"short strike {strike} (σ)"))
    vals = [v for _, v, _, _ in lines]
    if vals:
        lo, hi = min([lo] + vals), max([hi] + vals)
    ys = VC.spread(vals, hi - lo, 0.05)
    for (name, v, col, lab), y in zip(lines, ys):
        if name != "ENTRY":
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=v, y1=v, line=dict(color=col, width=2, dash="dot" if name == "STRIKE" else "solid"))
        fig.add_annotation(x=0, y=y, text=lab, showarrow=False, xanchor="left", font=dict(size=13, color="#ffffff"), bgcolor=col, opacity=0.9)
    pts = " · ".join(f"{k_} {v:+g}" for k_, v in c.get("top_points") or [])
    side = {1: "bull_put", -1: "bear_call"}.get(c.get("side"), "—")
    rr = f"1:{c['rr']:.1f}" if c.get("rr") else "—"
    fig.add_annotation(x=n - 1, y=hi, text=f"<b>{side} · grade {c.get('grade')} ({c.get('total')})</b> · R:R {rr}<br>{pts}<br>"
                                           + " ".join(c.get("codes") or []), showarrow=False, xanchor="right", yanchor="top",
                       font=dict(size=13, color="#ffffff"), bgcolor="rgba(0,0,0,0.7)", align="right")
    _trend_box(fig, d, hi, c.get("trend"))
    return _finish(fig, d, lo, hi)


def hindsight_15m(m15_all, c, h, title, days=3, cut=None):
    """entry नंतरचे 2–3 sessions + निकाल (target / SL / time), MFE / MAE. फक्त अहवाल."""
    pre = _sessions(m15_all, c["bar_end"], 2)
    after = m15_all[pd.to_datetime(m15_all["timestamp"]) > pd.Timestamp(c["bar_start"])]
    sess = pd.to_datetime(after["timestamp"]).dt.normalize().unique()[:int(days)]
    after = after[pd.to_datetime(after["timestamp"]).dt.normalize().isin(sess)]
    d = pd.concat([pre, after], ignore_index=True)
    fig = _base(d, title)
    VC._draw_cas(fig, VC.cas_marks(cut, d))
    lo, hi = float(d["low"].min()), float(d["high"].max())
    n0 = len(pre)
    fig.add_shape(type="rect", x0=n0 - 0.5, x1=len(d) - 0.5, y0=lo, y1=hi, fillcolor="rgba(255,255,255,0.05)", line_width=0, layer="below")
    for v, col in ((c.get("entry_px"), "#ffd54f"), (c.get("inv"), "#ef5350"), (((c.get("targets") or [{}])[0]).get("price"), "#66bb6a")):
        if v is not None:
            fig.add_shape(type="line", x0=-0.5, x1=len(d) - 0.5, y0=v, y1=v, line=dict(color=col, width=2))
            lo, hi = min(lo, v), max(hi, v)
    fig.add_annotation(x=len(d) - 1, y=lo, text=f"<b>{h.get('result')}</b> · MFE {h.get('mfe', '—')} · MAE {h.get('mae', '—')} pts",
                       showarrow=False, xanchor="right", yanchor="bottom", font=dict(size=15, color="#ffffff"), bgcolor="rgba(0,0,0,0.7)")
    return _finish(fig, d, lo, hi)


def day_15m(m15_day, cands, story, title, ms_close=None, cut=None, areas=None):
    """दिवसाचा 15M chart: code ची वाचनं (trend, impulse / correction, areas, trendlines) + **सगळे candidates** (✅ / 🟡 / ✖ + code)
    + खाली "code ची गोष्ट". m15_day = आदल्या 1–2 sessions + तो दिवस (दिवसाच्या शेवटापर्यंतच)."""
    d = m15_day.reset_index(drop=True)
    fig = _base(d, title)
    VC._draw_cas(fig, VC.cas_marks(cut, d))
    xi = _xmap(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    for z in (areas or [])[:6]:
        if z.get("tool") == "f" or (z["high"] >= lo and z["low"] <= hi):
            _area(fig, d, xi, z, len(d), color="#7e57c2" if z.get("tool") == "f" else "#42a5f5", width=1)
    if ms_close:
        _impulse_abc(fig, d, xi, ms_close.get("impulse"), (ms_close.get("correction") or {}).get("labels"))
    ys_top = VC.spread([float(d["high"].iloc[xi(c["bar_start"])]) for c in cands], hi - lo, 0.04)
    for c, y in zip(cands, ys_top):
        mark, col = STATUS_MARK[c["status"]]
        txt = f"{mark} {pd.Timestamp(c['bar_start']):%H:%M} " + (f"{c.get('grade')} {c.get('total')}" if c["status"] != "REJECTED"
                                                                 else ",".join(c["codes"][:2]))
        fig.add_annotation(x=xi(c["bar_start"]), y=y, text=txt, showarrow=True, ay=-25, font=dict(size=11, color=col),
                           bgcolor="rgba(0,0,0,0.6)")
    fig.add_annotation(x=0, y=lo, text=story[:220], showarrow=False, xanchor="left", yanchor="top", font=dict(size=12, color="#eceff1"),
                       bgcolor="rgba(0,0,0,0.7)")
    _trend_box(fig, d, hi, (ms_close or {}).get("trend"))
    return _finish(fig, d, lo, hi)
