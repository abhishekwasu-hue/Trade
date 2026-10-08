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
SELL_COL, BUY_COL = "#ef5350", "#26a69a"
PHASE_COL = {"P1": "#5c6bc0", "P2": "#ffa726", "P3": "#fdd835", "P4": "#00e676", "P5": "#8d6e63"}
PHASE_TXT = "P1 drive · P2 relief · P3 exhaustion · P4 control · P5 failure"
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


# Chart settings (Abhi K-10 निर्णय D): 15M window कमाल 7 sessions — मोठा context 1H chart वर.
CHART = {"m15_min_sessions": 2, "m15_max_sessions": 7, "h1_min_sessions": 20, "h1_max_sessions": 40}


def adaptive_window(df, t_end, c=None, min_s=2, max_s=15, pre_bars=4):
    """§8.5 adaptive chart window (hard-coded 5 दिवस नाही): चालू impulse च्या सुरुवातीच्या थोडं आधी (pre_bars) — impulse + correction +
    active zone चे anchors पूर्ण दिसतील इतका; किमान min_s, कमाल max_s sessions. गणना (zones / swings / trendlines) मोठ्या history वर
    आधीच झालेली — window फक्त दाखवण्यासाठी. 15M: 2–7 sessions (CHART) · 1H: 20–40."""
    d = _sessions(df, t_end, max_s)
    base = _sessions(df, t_end, min_s)
    if not len(d):
        return base
    keep = [pd.to_datetime(base["timestamp"]).min()] if len(base) else []
    c = c or {}
    imp = c.get("impulse") or {}
    for t in (imp.get("from_ts"),) + tuple(lab.get("from_ts") for lab in c.get("labels") or []):
        if t is not None:
            keep.append(pd.Timestamp(t))
    z = c.get("area") or {}
    for a in (z.get("pair") or []) + (z.get("anchors") or []):
        keep.append(pd.Timestamp(a[0]))
    ts = pd.to_datetime(d["timestamp"])
    start = max(min(keep), ts.iloc[0])
    k = max(0, int(np.searchsorted(ts.to_numpy(), np.datetime64(start, "ns"))) - int(pre_bars))
    return d.iloc[k:].reset_index(drop=True)


def _window(df, t_end, sessions, c=None, max_sessions=15):
    """जुनं नाव (gallery): adaptive_window(min = sessions)."""
    return adaptive_window(df, t_end, c, min_s=min(sessions, 2), max_s=max_sessions)


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
    t0 = pd.Timestamp(d["timestamp"].iloc[0]) if len(d) else None
    for lab in labels or []:
        up = lab["to"] > lab["from"]
        if t0 is not None and pd.Timestamp(lab["to_ts"]) < t0:            # §8.5: pivot chart बाहेर ⇒ edge label
            fig.add_annotation(x=0, y=lab["to"], text=f"{lab['label']} ← {pd.Timestamp(lab['to_ts']):%d %b} {lab['to']:,.0f}", showarrow=False,
                               xanchor="left", font=dict(size=12, color="#ffca28"))
            continue
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


def _tl_value_fn(z, m15_ts):
    """Trendline चं मूल्य कोणत्याही वेळी (कोणत्याही chart TF वर): रेषा trigger (15M) bars मध्ये — anchor पासून 15M bars मोजून.
    Anchors chart window बाहेर असले तरी रेषा बरोबर (x = 0 ला दाबत नाही)."""
    ref = (z.get("pair") or z.get("anchors") or [None])[0]
    if ref is None or m15_ts is None or not len(m15_ts):
        return None
    ia = int(np.searchsorted(m15_ts, np.datetime64(pd.Timestamp(ref[0]), "ns")))
    a_px, sl = float(ref[1]), float(z.get("slope") or 0.0)

    def f(t):
        return a_px + sl * (int(np.searchsorted(m15_ts, np.datetime64(pd.Timestamp(t), "ns"), side="right")) - 1 - ia)
    return f


def _zones_layer(fig, d, zones, m15_ts, lo, hi, per_side=4):
    """§2: selling zones लाल छटा, buying zones हिरवी; trendlines anchors सह; label "S1 · flip · 15M · ACTIVE · 2 touches"."""
    import plotly.graph_objects as go
    n = len(d)
    span = (hi - lo) or 1.0
    ts = pd.to_datetime(d["timestamp"])
    t0 = ts.iloc[0]
    shown = {"sell": 0, "buy": 0}
    for z in zones or []:
        side = z.get("side") or ("sell" if z.get("role") == "RESISTANCE" else "buy")
        col = SELL_COL if side == "sell" else BUY_COL
        label = z.get("label") or f"{z.get('id')}"
        if z.get("tool") == "f":
            f = _tl_value_fn(z, m15_ts)
            if f is None:
                continue
            ys = [f(t) for t in ts]
            if max(ys) < lo - 0.3 * span or min(ys) > hi + 0.3 * span:
                continue
            fig.add_trace(go.Scatter(x=list(range(n)), y=ys, mode="lines", line=dict(color=col, width=2, dash="dash")))
            inside = [(a, float(v)) for a, v in (z.get("anchors") or []) if pd.Timestamp(a) >= t0]
            if inside:
                xi = _xmap(d)
                fig.add_trace(go.Scatter(x=[xi(a) for a, _ in inside], y=[v for _, v in inside], mode="markers",
                                         marker=dict(color=col, size=10, symbol="circle-open", line=dict(width=2))))
            before = [(a, float(v)) for a, v in (z.get("anchors") or []) if pd.Timestamp(a) < t0]
            if before:                                                    # §8.4: window बाहेरचे anchors ⇒ edge label (x = 0 ला दाबत नाही)
                txt = " · ".join(f"{pd.Timestamp(a):%d %b} {v:,.0f}" for a, v in before)
                fig.add_annotation(x=0, y=ys[0], text=f"← {txt}", showarrow=False, xanchor="left", yanchor="bottom",
                                   font=dict(size=10, color=col))
            fig.add_annotation(x=n - 1, y=ys[-1], text=label, showarrow=False, xanchor="right", yanchor="bottom", font=dict(size=11, color=col))
            continue
        if shown[side] >= per_side or float(z["high"]) < lo - 0.1 * span or float(z["low"]) > hi + 0.1 * span:
            continue
        shown[side] += 1
        fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=float(z["low"]), y1=float(z["high"]), fillcolor=col, opacity=0.13,
                      line=dict(color=col, width=1), layer="below")
        fig.add_annotation(x=n - 1, y=float(z["high"]), text=label, showarrow=False, xanchor="right", yanchor="bottom",
                           font=dict(size=11, color=col))


def _gap_layer(fig, d, gap, day=None):
    """§4: [PDC, Open] gap पट्टा (त्या दिवसापासून), भरलेला भाग वेगळ्या छटेत, वर्ग + acceptance / rejection वेळ."""
    if not gap or gap.get("open") is None or gap.get("pdc") is None:
        return
    days = pd.to_datetime(d["timestamp"]).dt.normalize()
    day = pd.Timestamp(day).normalize() if day is not None else days.iloc[-1]
    idx = np.nonzero((days == day).to_numpy())[0]
    if not len(idx):
        return
    x0, n = int(idx[0]), len(d)
    o, pdc = float(gap["open"]), float(gap["pdc"])
    fig.add_shape(type="rect", x0=x0 - 0.5, x1=n - 0.5, y0=min(o, pdc), y1=max(o, pdc), fillcolor="#ab47bc", opacity=0.08, line_width=0,
                  layer="below")
    fill = float(gap.get("fill_pct") or 0.0) / 100.0
    if fill > 0:
        f_end = o + (pdc - o) * fill
        fig.add_shape(type="rect", x0=x0 - 0.5, x1=n - 0.5, y0=min(o, f_end), y1=max(o, f_end), fillcolor="#ab47bc", opacity=0.20,
                      line_width=0, layer="below")
    beh = gap.get("behaviour") or "—"
    at = gap.get("behaviour_at")
    fig.add_annotation(x=x0, y=max(o, pdc), text=f"{gap.get('class')} gap {gap.get('direction')} · {beh}{(' ' + str(at)) if at else ''} · "
                                                 f"fill {gap.get('fill_pct')}%", showarrow=False, xanchor="left", yanchor="bottom",
                       font=dict(size=11, color="#ce93d8"))


def _candle_tags(fig, d, story, side):
    """§5: खुणा फक्त entry area मधल्या (zone वर पोहोचल्यानंतरच्या शेवटच्या 3–6) candles वर — बाकी chart साधा."""
    if not story or not story.get("bars"):
        return
    xi = _xmap(d)
    t0 = pd.Timestamp(d["timestamp"].iloc[0])
    for b in story["bars"]:
        if pd.Timestamp(b["ts"]) < t0:
            continue
        k = xi(b["ts"])
        y = float(d["high"].iloc[k]) if side < 0 else float(d["low"].iloc[k])
        fig.add_annotation(x=k, y=y, text=b["tag"], showarrow=False, yanchor="bottom" if side < 0 else "top", textangle=-60,
                           font=dict(size=9, color="#e1f5fe"))


def _phase_strip(fig, d, timeline, lo, hi):
    """Abhi: दिवसाच्या chart खाली phase timeline एका पट्टीत (P1…P5 रंग) + legend."""
    if not timeline:
        return lo
    xi = _xmap(d)
    span = (hi - lo) or 1.0
    y0, y1 = lo - 0.09 * span, lo - 0.04 * span
    for p in timeline:
        k = xi(p["ts"])
        fig.add_shape(type="rect", x0=k - 0.5, x1=k + 0.5, y0=y0, y1=y1, fillcolor=PHASE_COL.get(p["phase"], "#607d8b"), line_width=0)
    fig.add_annotation(x=0, y=y0, text=PHASE_TXT, showarrow=False, xanchor="left", yanchor="top", font=dict(size=10, color="#cfd8dc"))
    return y0 - 0.04 * span


def context_1h(h1, c, title, elliott_line=None, areas=None, sessions=20, m15_ts=None, max_sessions=40):
    """1H context (entry / दिवस पर्यंत): adaptive 20–40 sessions (मोठ्या degree चे swings), HTF trend + protected, selling / buying
    zones (HTF + trendlines), impulse + correction (बाहेर ⇒ edge label), Elliott (gray असेल तर gray)."""
    d = adaptive_window(h1, c["bar_end"], c, min_s=sessions, max_s=max_sessions, pre_bars=2)
    assert_upto(d, c["bar_end"], "1H context")
    fig = _base(d, title)
    xi = _xmap(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    zones = c.get("zones")
    if zones:
        _zones_layer(fig, d, [z for z in zones if z.get("tool") in ("a", "b", "c", "d", "f") or z.get("tf") not in (None, "15M")], m15_ts,
                     lo, hi)
    else:
        for z in (areas or [])[:8]:
            if z.get("tool") in ("a", "b", "d", "f") and (z["high"] >= lo and z["low"] <= hi or z.get("tool") == "f"):
                _area(fig, d, xi, z, len(d), color="#7e57c2" if z.get("tool") == "f" else "#42a5f5", width=1)
    _impulse_abc(fig, d, xi, c.get("impulse"), c.get("labels"))
    _trend_box(fig, d, hi, c.get("trend"), extra=f" · Elliott: {elliott_line or 'gray'}")
    return _finish(fig, d, lo, hi, fmt="%d %b", n=8)


def entry_15m(m15, c, title, cut=None, strike=None, sessions=2, m15_ts=None):
    """15M entry chart: entry bar च्या close पर्यंत, adaptive window (impulse + correction + zone anchors; 2–7 sessions (CHART)).
    Selling / buying zones (लाल / हिरवे, labels), active zone ठळक, gap पट्टा, impulse / A-B-C (बाहेर ⇒ edge label), entry area च्या
    candles वरच खुणा, reversal candle(s), ENTRY / SL (कुठून; दोन व्याख्या) / TARGET / R:R / strike σ, story phase, grade (नोंद), CAS राखाडी."""
    d = adaptive_window(m15, c["bar_end"], c, min_s=CHART["m15_min_sessions"], max_s=CHART["m15_max_sessions"])
    assert_upto(d, c["bar_end"], "15M entry")
    fig = _base(d, title)
    VC._draw_cas(fig, VC.cas_marks(cut, d))
    xi = _xmap(d)
    n = len(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    if m15_ts is None:
        m15_ts = pd.to_datetime(m15["timestamp"]).to_numpy(dtype="datetime64[ns]")
    _zones_layer(fig, d, c.get("zones") or [], m15_ts, lo, hi)
    _gap_layer(fig, d, c.get("gap"), day=c.get("bar_start"))
    z = c.get("area")
    conf = ", ".join(TOOL_NAME.get(t, t) for t in c.get("confluence") or [])
    if z and z.get("tool") != "f":
        _area(fig, d, xi, z, n, label=f"ACTIVE: {c.get('area_label') or z.get('id')}" + (f" + {conf}" if conf else ""), color="#ffca28", width=3)
    elif z:
        fig.add_annotation(x=n - 1, y=float(z.get("high") or hi), text=f"ACTIVE: {c.get('area_label') or z.get('id')}" + (f" + {conf}" if conf else ""),
                           showarrow=False, xanchor="right", yanchor="top", font=dict(size=12, color="#ffca28"))
    _impulse_abc(fig, d, xi, c.get("impulse"), c.get("labels"), c.get("ctype"))
    _candle_tags(fig, d, c.get("zone_story"), c.get("side") or -1)
    k = n - 1
    nrev = 2 if c.get("rev_comp") else 1
    for j in range(max(0, k - nrev + 1), k + 1):
        fig.add_shape(type="rect", x0=j - 0.45, x1=j + 0.45, y0=float(d["low"].iloc[j]), y1=float(d["high"].iloc[j]),
                      line=dict(color="#ffffff", width=2), fillcolor="rgba(0,0,0,0)")
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
    side = {1: "bull_put", -1: "bear_call"}.get(c.get("side"), "—")
    rr = f"1:{c['rr']:.1f}" if c.get("rr") else "—"
    fig.add_annotation(x=n - 1, y=hi, text=f"<b>{side}</b> · R:R {rr} · grade {c.get('grade')} ({c.get('total')})<br>"
                                           + " ".join(c.get("codes") or []) + (f"<br>{c.get('checklist_summary')}" if c.get("checklist_summary") else ""),
                       showarrow=False, xanchor="right", yanchor="top", font=dict(size=13, color="#ffffff"), bgcolor="rgba(0,0,0,0.7)", align="right")
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


def day_15m(m15_day, cands, story, title, ms_close=None, cut=None, areas=None, zones=None, gap=None, timeline=None, m15_ts=None,
            day=None):
    """दिवसाचा 15M chart (adaptive window: आदल्या impulse पासून, 2–7 sessions (CHART); caller कापून देतो — दिवसाच्या शेवटापर्यंतच):
    selling / buying zones + trendlines (anchors), gap पट्टा, impulse / A-B-C, **सगळे candidates** (✅ "12:15 A 67.5 · area …" /
    🟡 / ✖ + code), खाली P1…P5 phase पट्टी आणि "code ची गोष्ट"."""
    d = m15_day.reset_index(drop=True)
    fig = _base(d, title)
    VC._draw_cas(fig, VC.cas_marks(cut, d))
    xi = _xmap(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    if m15_ts is None:
        m15_ts = pd.to_datetime(d["timestamp"]).to_numpy(dtype="datetime64[ns]")
    if zones:
        _zones_layer(fig, d, zones, m15_ts, lo, hi)
    else:
        for z in (areas or [])[:6]:
            if z.get("tool") == "f" or (z["high"] >= lo and z["low"] <= hi):
                _area(fig, d, xi, z, len(d), color="#7e57c2" if z.get("tool") == "f" else "#42a5f5", width=1)
    _gap_layer(fig, d, gap, day=day)
    if ms_close:
        _impulse_abc(fig, d, xi, ms_close.get("impulse"), (ms_close.get("correction") or {}).get("labels"))
    ys_top = VC.spread([float(d["high"].iloc[xi(c["bar_start"])]) for c in cands], hi - lo, 0.04)
    for c, y in zip(cands, ys_top):
        mark, col = STATUS_MARK[c["status"]]
        hm = f"{pd.Timestamp(c['bar_start']):%H:%M}"
        if c["status"] == "ENTRY":
            txt = f"{mark} {hm} {c.get('grade')} {c.get('total')} · area {c.get('area_label') or '—'}"
        elif c["status"] == "C":
            txt = f"{mark} {hm} {c.get('grade')} {c.get('total')}"
        else:
            txt = f"{mark} {hm} " + ",".join(c["codes"][:2])
        fig.add_annotation(x=xi(c["bar_start"]), y=y, text=txt, showarrow=True, ay=-25, font=dict(size=11, color=col),
                           bgcolor="rgba(0,0,0,0.6)")
    bottom = _phase_strip(fig, d, timeline, lo, hi)
    fig.add_annotation(x=0, y=bottom, text=story[:240], showarrow=False, xanchor="left", yanchor="top", font=dict(size=12, color="#eceff1"),
                       bgcolor="rgba(0,0,0,0.7)")
    _trend_box(fig, d, hi, (ms_close or {}).get("trend"))
    return _finish(fig, d, min(lo, bottom), hi)


def core_day_15m(m15, day, bars, title, m15_ts=None, cut=None, ms_close=None):
    """Simple Core दिवस chart (K-10): trend label, selling / buying areas, pause candles फिकट, commitment ठळक, 🚩 ENTRY SIGNAL,
    ref_levels (फक्त माहिती), प्रत्येक signal वर shadow engine चा निर्णय एका ओळीत. bars = [{bar_start, signal, pause_bars, why,
    zones, shadow}] (दिवसाचे प्रत्येक बंद bar)."""
    day_end = pd.Timestamp(day) + pd.Timedelta(hours=15, minutes=30)
    c0 = {"impulse": (ms_close or {}).get("impulse"), "labels": ((ms_close or {}).get("correction") or {}).get("labels")}
    d = adaptive_window(m15, day_end, c0, min_s=CHART["m15_min_sessions"], max_s=CHART["m15_max_sessions"])
    fig = _base(d, title)
    VC._draw_cas(fig, VC.cas_marks(cut, d))
    xi = _xmap(d)
    n = len(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    if m15_ts is None:
        m15_ts = pd.to_datetime(m15["timestamp"]).to_numpy(dtype="datetime64[ns]")
    sig_bar = next((b for b in bars if b.get("signal") and b.get("zones")), None)     # signal च्या वेळचे zones (दिवस अखेरचे नाहीत)
    src = sig_bar or next((b for b in reversed(bars) if b.get("zones")), {})
    live = [z for z in src.get("zones") or [] if z.get("state") not in ("BROKEN", "DEAD", "MAGNET")]
    _zones_layer(fig, d, live, m15_ts, lo, hi)
    if ms_close:
        corr = ms_close.get("correction") or {}
        labels = [] if corr.get("origin_broken") else corr.get("labels")       # origin तुटला ⇒ correction नाही ⇒ ABC नाही
        _impulse_abc(fig, d, xi, ms_close.get("impulse"), labels)
    notes = []
    for b in bars:
        sg = b.get("signal")
        if not sg:
            continue
        k = xi(sg["bar_start"])
        p0 = xi(sg["pause_from"]) if sg.get("pause_from") else k
        for j in range(p0, k - sg["commitment"]["bars"] + 1):             # pause candles फिकट
            fig.add_shape(type="rect", x0=j - 0.45, x1=j + 0.45, y0=float(d["low"].iloc[j]), y1=float(d["high"].iloc[j]),
                          fillcolor="#fff59d", opacity=0.18, line_width=0, layer="below")
        for j in range(k - sg["commitment"]["bars"] + 1, k + 1):          # commitment ठळक
            fig.add_shape(type="rect", x0=j - 0.48, x1=j + 0.48, y0=float(d["low"].iloc[j]), y1=float(d["high"].iloc[j]),
                          line=dict(color="#ffffff", width=3), fillcolor="rgba(0,0,0,0)")
        up = sg["side"] > 0
        fig.add_annotation(x=k, y=float(d["low"].iloc[k] if up else d["high"].iloc[k]), text=f"🚩 ENTRY {pd.Timestamp(sg['bar_start']):%H:%M} "
                           f"{'bull' if up else 'bear'} · {sg['trigger_price']:,.0f}", showarrow=True, ay=40 if up else -40,
                           font=dict(size=13, color="#ffd54f"), bgcolor="rgba(0,0,0,0.7)")
        for name, v in (sg.get("ref_levels") or {}).items():
            if v is None:
                continue
            fig.add_shape(type="line", x0=k, x1=n - 0.5, y0=v, y1=v, line=dict(color="#b0bec5", width=1, dash="dot"))
            fig.add_annotation(x=n - 1, y=v, text=f"{name} {v:,.0f}", showarrow=False, xanchor="right", font=dict(size=10, color="#b0bec5"))
            lo, hi = min(lo, v), max(hi, v)
        notes.append(f"{pd.Timestamp(sg['bar_start']):%H:%M}: area {sg['area']['id']} · pause {sg['pause_bars']} · shadow: {b.get('shadow') or '—'}")
    _trend_box(fig, d, hi, (ms_close or {}).get("trend"))
    txt = "<br>".join(notes) if notes else "आज ENTRY SIGNAL नाही"
    span = (hi - lo) or 1.0
    fig.add_annotation(x=0, y=lo - 0.03 * span, text=(f"zones: {pd.Timestamp(sig_bar['bar_start']):%H:%M} (signal) च्या वेळचे<br>" if sig_bar else
                                                       "zones: दिवस अखेरचे<br>") + txt[:600], showarrow=False, xanchor="left", yanchor="top", font=dict(size=12, color="#eceff1"),
                       bgcolor="rgba(0,0,0,0.7)", align="left")
    return _finish(fig, d, lo - 0.12 * span, hi)
