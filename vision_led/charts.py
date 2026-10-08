"""vision_led/charts.py — (1) vision input chart, (2) annotated chart (validation नंतर), (3) hindsight chart. Code काढतो; image वरून किंमत कधीच नाही.

  input      15M (शेवटचे 60) + code areas (फिकट पट्टे, id) · futures volume (असेल तर) · 1H (शेवटचे 20) · line panel (15M closes, 5 sessions)
  annotated  फक्त entry bar पर्यंत (no-lookahead): ENTRY marker + "ENTRY 22,680 · 7 Oct 14:30", लाल SL रेषा + कारण, हिरवी target, R:R label,
             vision ने निवडलेला area ठळक (पट्टा / तिरकी trendline + anchors), short strike रेषा (माहिती). Labels एकमेकांवर येत नाहीत (`spread`).
             C-V1: context ≥ 10 sessions / anchors दिसेपर्यंत, impulse origin (protected) रेषा, दोन SL (reversal-candle आणि structural, R:R सह),
             "SIM" watermark (grade chart वर नाही), CAS bars राखाडी + "CAS" (setting cas_window.chart).
             Validation fail ⇒ "REJECTED: <कारण>", रेषा नाहीत. NO_TRADE ⇒ "NO TRADE (vision)".
  hindsight  तोच chart + entry नंतरचे पुढचे 2 trading दिवस (फिकट पार्श्वभूमी) — फक्त अहवाल / Telegram, निर्णयात नाही.
PNG फक्त trade-data / VPS archive मध्ये (public repo मध्ये नाही).
"""
import numpy as np
import pandas as pd

W, H_INPUT, H_ANN = 1400, 1050, 820


def spread(ys, span, min_frac=0.035):
    """Label y-positions (क्रम राखून) एकमेकांपासून किमान min_frac × span अंतरावर. रिटर्न नवीन y यादी (मूळ क्रमात)."""
    if not ys:
        return []
    gap = min_frac * (span or 1.0)
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = [0.0] * len(ys)
    prev = None
    for i in order:
        y = ys[i] if prev is None else max(ys[i], prev + gap)
        out[i] = y
        prev = y
    return out


def cas_marks(cut, frame):
    """CAS bins (opportunity_engine/cas.py) chart वर राखाडी + "CAS" (setting chart = grey). frame = CAS-clean 15M bars (x = index).
    रिटर्न [(x, open, high, low, close)] — त्या दिवसाच्या शेवटच्या clean bar नंतर (x + 0.5). Setting "exclude" ⇒ []."""
    from opportunity_engine import cas as CAS
    from opportunity_engine.sessions import resample_nse
    w = CAS.load_cas_window()
    if not w.get("enabled") or w.get("chart") != "grey" or cut is None or not len(cut) or not len(frame):
        return []
    raw = resample_nse(cut[pd.to_datetime(cut["timestamp"]) >= pd.Timestamp(frame["timestamp"].iloc[0]).normalize()], 15, cas=False)
    m = CAS.cas_mask(raw["timestamp"]).to_numpy()
    if not m.any():
        return []
    days = pd.to_datetime(frame["timestamp"]).dt.normalize().to_numpy()
    out = []
    for r in raw[m].itertuples():
        idx = np.nonzero(days == np.datetime64(pd.Timestamp(r.timestamp).normalize(), "ns"))[0]
        if len(idx):
            out.append((float(idx[-1]) + 0.5, r.open, r.high, r.low, r.close))
    return out


def _draw_cas(fig, marks, row=None, col=None):
    import plotly.graph_objects as go
    if not marks:
        return
    kw = {} if row is None else {"row": row, "col": col}
    x, o, h, lo, c = (list(v) for v in zip(*marks))
    fig.add_trace(go.Candlestick(x=x, open=o, high=h, low=lo, close=c, showlegend=False, increasing_line_color="#9e9e9e",
                                 decreasing_line_color="#9e9e9e", increasing_fillcolor="#616161", decreasing_fillcolor="#616161",
                                 whiskerwidth=0.2), **kw)
    for xi, hi in zip(x, h):
        fig.add_annotation(x=xi, y=hi, text="CAS", showarrow=False, yanchor="bottom", font=dict(size=8, color="#9e9e9e"), **kw)


def _x_ticks(df, fmt="%d %b %H:%M", n=7):
    step = max(1, len(df) // n)
    ticks = list(range(0, len(df), step))
    return ticks, [pd.Timestamp(df["timestamp"].iloc[k]).strftime(fmt) for k in ticks]


def input_figure(m15, h1, line, areas, title, vol=None, vol_title="futures volume (rel_vol, slot-normalised)", bars15=100, bars1h=70,
                 cas=None):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    has_vol = vol is not None and np.isfinite(np.asarray(vol, float)).any()
    rows = 3 if has_vol else 2
    heights = [0.5, 0.12, 0.38] if has_vol else [0.6, 0.4]
    specs = [[{"colspan": 2}, None]] + ([[{"colspan": 2}, None]] if has_vol else []) + [[{}, {}]]
    titles = [f"15M (last {bars15} closed bars) + code candidate areas · grey = CAS (closing auction, excluded)"] + \
             ([vol_title] if has_vol else []) + [f"1H (last {bars1h})", "line: 15M closes, 5 sessions"]
    fig = make_subplots(rows=rows, cols=2, row_heights=heights, specs=specs, subplot_titles=titles, vertical_spacing=0.06, horizontal_spacing=0.06)
    d = m15.tail(int(bars15)).reset_index(drop=True)
    x = np.arange(len(d))
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"], showlegend=False,
                                 increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=1)
    _draw_cas(fig, cas_marks(cas, d), row=1, col=1)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    span = hi - lo
    vis = [z for z in areas if z["high"] >= lo - 0.15 * span and z["low"] <= hi + 0.15 * span][:14]
    ys = spread([(z["low"] + z["high"]) / 2.0 for z in vis], span, 0.03)
    n = len(d)
    for z, y in zip(vis, ys):
        col = "#42a5f5" if z.get("kind") == "solid" else "#8d6e63"
        if z.get("tool") == "f" and z.get("slope") is not None:          # trendline तिरकीच काढायची (फक्त आडवा पट्टा नाही)
            y0 = z["value"] - z["slope"] * (n - 1)
            fig.add_trace(go.Scatter(x=[0, n - 1], y=[y0, z["value"]], mode="lines", showlegend=False,
                                     line=dict(color="#ab47bc" if z.get("valid") else "#6a4f6f", width=2 if z.get("valid") else 1, dash="dot")),
                          row=1, col=1)
            col = "#ab47bc"
        else:
            fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=z["low"], y1=z["high"], fillcolor=col, opacity=0.10, line_width=0, row=1, col=1)
        fig.add_annotation(x=len(d) - 0.5, y=y, text=z["id"][:16], showarrow=False, xanchor="left", font=dict(size=8, color=col), row=1, col=1)
    ticks, labels = _x_ticks(d)
    fig.update_xaxes(tickvals=ticks, ticktext=labels, rangeslider_visible=False, row=1, col=1)
    if has_vol:
        v = np.asarray(vol, float)[-len(d):]
        fig.add_trace(go.Bar(x=x[-len(v):], y=v, marker_color="#78909c", showlegend=False), row=2, col=1)
        fig.update_xaxes(showticklabels=False, row=2, col=1)
    r = rows
    hh = h1.tail(int(bars1h)).reset_index(drop=True)
    fig.add_trace(go.Candlestick(x=np.arange(len(hh)), open=hh["open"], high=hh["high"], low=hh["low"], close=hh["close"], showlegend=False,
                                 increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=r, col=1)
    t2, l2 = _x_ticks(hh, n=4)
    fig.update_xaxes(tickvals=t2, ticktext=l2, rangeslider_visible=False, row=r, col=1)
    if line is not None and len(line):
        fig.add_trace(go.Scatter(x=np.arange(len(line)), y=line["close"], mode="lines", line=dict(color="#ffd54f", width=1.5), showlegend=False),
                      row=r, col=2)
        t3, l3 = _x_ticks(line, fmt="%d %b", n=5)
        fig.update_xaxes(tickvals=t3, ticktext=l3, row=r, col=2)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238")
    fig.update_layout(template="plotly_dark", width=W, height=H_INPUT, margin=dict(l=10, r=90, t=60, b=30), paper_bgcolor="#0e1117",
                      plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=14)), showlegend=False)
    return fig


def _context_bars(m15, cand, area, sessions=10):
    """Annotated chart चा context: किमान `sessions` sessions, आणि impulse origin / active area चे anchors दिसतील इतका (C-V1 §4)."""
    ts = pd.to_datetime(m15["timestamp"])
    days = ts.dt.normalize().unique()
    start = days[-sessions] if len(days) >= sessions else days[0]
    keep = [pd.Timestamp(start)]
    imp = (cand or {}).get("impulse") or {}
    if imp.get("s_bar") is not None and 0 <= int(imp["s_bar"]) < len(m15):
        keep.append(ts.iloc[int(imp["s_bar"])].normalize())
    for a in (area or {}).get("anchors") or []:
        keep.append(pd.Timestamp(a[0]).normalize())
    first = min(keep)
    return int((ts >= first).sum())


def annotated_figure(m15, res, cand, title, future=None, hindsight=None, cut=None, sessions=10):
    """m15 = entry bar पर्यंतचे 15M bars (CAS-clean). future (hindsight chart साठीच) = entry नंतरचे bars. cut = 1m (CAS राखाडी खुणा).
    Context ≥ `sessions` sessions / anchors दिसेपर्यंत · vision चा area ठळक (trendline तिरकी) · impulse origin (protected) रेषा ·
    दोन SL व्याख्या (reversal-candle आणि structural, प्रत्येकी R:R) · "SIM" watermark (grade chart वर नाही)."""
    import plotly.graph_objects as go
    z = res.get("area")
    nb = _context_bars(m15, cand, z, sessions)
    d = m15.tail(nb).reset_index(drop=True)
    n0 = len(d)
    full = d if future is None or not len(future) else pd.concat([d, future.reset_index(drop=True)], ignore_index=True)
    x = np.arange(len(full))
    fig = go.Figure(go.Candlestick(x=x, open=full["open"], high=full["high"], low=full["low"], close=full["close"], showlegend=False,
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350"))
    _draw_cas(fig, cas_marks(cut, full))
    lo, hi = float(full["low"].min()), float(full["high"].max())
    fig.add_annotation(x=len(full) / 2, y=(lo + hi) / 2, text="SIM", showarrow=False, font=dict(size=120, color="rgba(255,255,255,0.07)"))
    if future is not None and len(future):
        fig.add_shape(type="rect", x0=n0 - 0.5, x1=len(full) - 0.5, y0=lo, y1=hi, fillcolor="rgba(255,255,255,0.04)", line_width=0, layer="below")
        fig.add_annotation(x=n0, y=hi, text="AFTER ENTRY (hindsight only)", showarrow=False, xanchor="left", yanchor="top",
                           font=dict(size=10, color="#b0bec5"))
    imp = (cand or {}).get("impulse") or {}
    if imp.get("s_px") is not None:
        fig.add_shape(type="line", x0=-0.5, x1=len(full) - 0.5, y0=imp["s_px"], y1=imp["s_px"], line=dict(color="#90a4ae", width=1, dash="dot"))
        fig.add_annotation(x=len(full) - 1, y=imp["s_px"], text=f"impulse origin / protected {imp['s_px']:,.1f}", showarrow=False,
                           xanchor="right", yanchor="bottom", font=dict(size=10, color="#cfd8dc"))
    st = res["status"]
    if z is not None:                                                    # vision ने निवडलेला area ठळक
        if z.get("tool") == "f" and z.get("anchors"):
            tsx = pd.to_datetime(full["timestamp"]).to_numpy(dtype="datetime64[ns]")
            ax = [(int(np.searchsorted(tsx, np.datetime64(pd.Timestamp(a[0]), "ns"))), float(a[1])) for a in z["anchors"]]
            ax = [(k, v) for k, v in ax if k < n0]
            if ax:
                k0, v0 = ax[0]
                slope = float(z.get("slope") or 0.0)
                fig.add_trace(go.Scatter(x=[k0, len(full) - 1], y=[v0, v0 + slope * (len(full) - 1 - k0)], mode="lines", showlegend=False,
                                         line=dict(color="#ffca28", width=3)))
                fig.add_trace(go.Scatter(x=[k for k, _ in ax], y=[v for _, v in ax], mode="markers", showlegend=False,
                                         marker=dict(color="#ffca28", size=9, symbol="circle-open", line=dict(width=2))))
        else:
            fig.add_shape(type="rect", x0=-0.5, x1=len(full) - 0.5, y0=z["low"], y1=z["high"], fillcolor="#ffca28", opacity=0.25,
                          line=dict(color="#ffca28", width=2), layer="below")
        fig.add_annotation(x=0, y=z["high"], text=f"ACTIVE AREA (vision): {z['id']}", showarrow=False, xanchor="left", yanchor="bottom",
                           font=dict(size=11, color="#ffca28"))
    if st != "OK":
        txt = "NO TRADE (vision)" if st == "NO_TRADE" else "REJECTED: " + "; ".join(res.get("reasons") or [])[:160]
        fig.add_annotation(x=n0 / 2, y=(lo + hi) / 2, text=txt, showarrow=False, font=dict(size=15, color="#ff8a65"), bgcolor="rgba(0,0,0,0.6)")
    else:
        side, entry, inv, tgt = res["side"], res["entry"], res["inv"], res["target"]
        sl = res.get("sl_defs") or {}
        extra = [v["inv"] for v in sl.values() if v]
        lo, hi = min([lo, inv, tgt] + extra), max([hi, inv, tgt] + extra)
        span = hi - lo
        lines = [("ENTRY", entry, "#ffd54f", f"ENTRY {entry:,.0f} · {pd.Timestamp(cand['bar_start']):%d %b %H:%M}", "solid"),
                 ("SL", inv, "#ef5350", f"vision SL {inv:,.0f} ({res.get('inv_ref_label') or 'ref'} + buffer) · R:R 1:{res['rr']:.1f}", "solid"),
                 ("TARGET", tgt, "#66bb6a", f"TARGET {tgt:,.0f}", "solid")]
        if sl.get("candle"):
            c_ = sl["candle"]
            lines.append(("SLC", c_["inv"], "#ff9800", f"reversal-candle SL {c_['inv']:,.0f} · R:R " + (f"1:{c_['rr']:.1f}" if c_.get("rr") else "—"),
                          "dot"))
        if sl.get("structural"):
            c_ = sl["structural"]
            lines.append(("SLS", c_["inv"], "#d32f2f", f"structural SL {c_['inv']:,.0f} · R:R " + (f"1:{c_['rr']:.1f}" if c_.get("rr") else "—"),
                          "dash"))
        strike = (res.get("strike") or {}).get("strike")
        if strike is not None and lo - 0.15 * span <= strike <= hi + 0.15 * span:
            lines.append(("STRIKE", strike, "#ab47bc", f"short strike {strike} (σ, info)", "dot"))
        elif strike is not None:                                         # range बाहेर ⇒ candles लहान न करता कडेला खूण
            up = strike > hi
            fig.add_annotation(x=0, y=hi if up else lo, text=f"{'▲' if up else '▼'} short strike {strike} (σ, info)", showarrow=False,
                               xanchor="left", yanchor="top" if up else "bottom", font=dict(size=10, color="#ffffff"), bgcolor="#ab47bc")
        ys = spread([v for _, v, _, _, _ in lines], span, 0.045)
        for (name, v, col, lab, dash), y in zip(lines, ys):
            if name != "ENTRY":
                fig.add_shape(type="line", x0=-0.5, x1=len(full) - 0.5, y0=v, y1=v,
                              line=dict(color=col, width=2 if name in ("SL", "TARGET") else 1, dash=dash))
            fig.add_annotation(x=0, y=y, text=lab, showarrow=False, xanchor="left", font=dict(size=11, color="#ffffff"), bgcolor=col, opacity=0.9)
        fig.add_annotation(x=n0 - 1, y=entry, text="▼ ENTRY" if side < 0 else "▲ ENTRY", showarrow=True, arrowcolor="#ffd54f", ax=0,
                           ay=-36 if side < 0 else 36, font=dict(size=11, color="#ffd54f"))
        fig.add_annotation(x=n0 - 1, y=hi, text=f"SIM — trade नाही · vision R:R 1:{res['rr']:.1f}", showarrow=False, xanchor="right",
                           yanchor="top", font=dict(size=13, color="#ffffff"), bgcolor="rgba(0,0,0,0.6)")
        if hindsight:
            fig.add_annotation(x=len(full) - 1, y=lo, text=f"hindsight: {hindsight.get('result')}", showarrow=False, xanchor="right",
                               yanchor="bottom", font=dict(size=12, color="#ffffff"), bgcolor="rgba(0,0,0,0.6)")
    pad = 0.05 * ((hi - lo) or 1.0)
    ticks, labels = _x_ticks(full, n=10)
    fig.update_xaxes(tickvals=ticks, ticktext=labels, rangeslider_visible=False, showgrid=False)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", range=[lo - pad, hi + pad])
    fig.update_layout(template="plotly_dark", width=W, height=H_ANN, margin=dict(l=10, r=70, t=60, b=30), paper_bgcolor="#0e1117",
                      plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=14)), showlegend=False)
    return fig


def png(fig, attempts=2):
    """PNG bytes किंवा None. अपयश ⇒ कारण log मध्ये, kaleido server (चालू असेल तर) restart, एकदा पुन्हा."""
    for k in range(attempts):
        try:
            return fig.to_image(format="png", scale=1)
        except Exception as exc:
            print(f"  ⚠️ render (प्रयत्न {k + 1}/{attempts}): {type(exc).__name__}: {str(exc)[:160]}")
            try:
                import kaleido
                from kaleido import _global_server
                if _global_server.is_running():
                    kaleido.stop_sync_server(silence_warnings=True)
                    kaleido.start_sync_server(silence_warnings=True)
            except Exception:
                pass
    return None

