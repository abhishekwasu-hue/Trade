"""pivots/charts.py — थर 1 तपासणीचे charts (Abhi साठी): 15M (D1 मोठे ठिपके + D0 लहान), 1H (D2), Daily (D3), Weekly (D4). 1H / Daily /
Weekly candles 15M पासून aggregate (तोच CAS नियम). Tentative टोक पोकळ खूण; protected swing ठिपक्यांची आडवी रेघ; warm-up pivots फिके;
कोपऱ्यात box (प्रत्येक degree चा trend + शेवटचे दोन pivots). किंमती फक्त OHLC / pivots मधून.

`display_only`: holdout काळातल्या जुन्या daily / weekly candles **फक्त दाखवायला** (Abhi ची परवानगी). त्या rows ला खूण लागते आणि
engine चा guard त्यांना नाकारतो — म्हणून त्या σ / DC / मोजमाप / JSON मध्ये कधीच पोचत नाहीत. Chart वर तो भाग राखाडी.
"""
import io

import numpy as np
import pandas as pd

from backtest_review import charts as BC

from . import engine as PE

TREND_MR = {1: "वर", -1: "खाली", 0: "range"}
COL = {"H": "#ef5350", "L": "#26a69a"}
W_MIN = {"15M": 5, "1H": 20}                                   # किमान sessions


def display_only(df):
    """chart-drawing path साठीचा नाव दिलेला अपवाद: rows ना `display_only=True` खूण (engine guard ही खूण असलेला data नाकारतो)."""
    return df.assign(display_only=True)


def agg_1h(m15):
    """15M ⇒ 1H (09:15-anchored, session मध्ये)."""
    t = pd.to_datetime(m15["timestamp"])
    day = t.dt.normalize()
    k = ((t - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(hours=1)).astype(int)
    start = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(hours=1)
    g = m15.assign(timestamp=start).groupby("timestamp").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                            close=("close", "last"), bar_end=("bar_end", "max"))
    return g.reset_index()


def daily_from_15m(m15, asof):
    """15M ⇒ daily; फक्त पूर्ण sessions (त्या दिवसाचा शेवटचा अपेक्षित 15M bar — CAS असेल तर 15:15 ला संपणारा — asof पर्यंत बंद).
    अर्धवट दिवसाची candle नाही."""
    m = m15[pd.to_datetime(m15["bar_end"]) <= pd.Timestamp(asof)]
    t = pd.to_datetime(m["timestamp"])
    g = m.assign(timestamp=t.dt.normalize()).groupby("timestamp").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                                   close=("close", "last"), bar_end=("bar_end", "max")).reset_index()
    ok = [PE.session_complete(d, e) for d, e in zip(g["timestamp"], g["bar_end"])]
    return g[ok].reset_index(drop=True)


def weekly_from_daily(d, asof):
    if not len(d):
        return d
    wk = pd.to_datetime(d["timestamp"]).dt.to_period("W-FRI")
    g = d.assign(_w=wk).groupby("_w").agg(timestamp=("timestamp", "first"), open=("open", "first"), high=("high", "max"),
                                         low=("low", "min"), close=("close", "last")).reset_index()
    g["bar_end"] = d.assign(_w=wk).groupby("_w")["bar_end"].max().to_numpy() if "bar_end" in d.columns else \
        g["_w"].dt.end_time.dt.normalize() + pd.Timedelta(hours=15, minutes=30)
    g = g[pd.to_datetime(g["bar_end"]) <= pd.Timestamp(asof)]                  # चालू आठवडा: पूर्ण झालेल्या दिवसांपर्यंत
    return g[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


def _x_of(frame, ts):
    """15M वेळ ⇒ त्या TF चा bar; chart च्या शेवटच्या candle नंतरची वेळ ⇒ None (मागच्या candle वर दाबत नाही)."""
    if not len(frame):
        return None
    if "bar_end" in frame.columns and pd.Timestamp(ts) >= pd.Timestamp(frame["bar_end"].iloc[-1]):
        return None
    t = pd.to_datetime(frame["timestamp"]).to_numpy(dtype="datetime64[ns]")
    i = int(np.searchsorted(t, np.datetime64(pd.Timestamp(ts), "ns"), side="right") - 1)
    return i if 0 <= i < len(frame) else None


def box_text(snap, asof):
    rows = []
    for d, nm in ((1, "15M (D1)"), (2, "1H (D2)"), (3, "Daily (D3)"), (4, "Weekly (D4)"), (0, "आतली (D0)")):
        s = snap[f"D{d}"]
        last = s["pivots"][-2:]
        lt = " · ".join(f"{p['label']} {p['price']:,.0f} ({pd.Timestamp(p['ts']):%d %b %H:%M})" for p in last) or "pivots नाहीत"
        wu = "" if s["warmup_done"] else " · warm-up अपूर्ण"
        rows.append(f"<b>{nm}</b>: {s['trend']['name']}{wu} · {lt}")
    return "<br>".join(rows)


def figure(frame, tf, snap, degree, title, minor=None, history=None, box=True):
    """एक chart. frame = त्या TF चे बंद bars (window). degree चे pivots मोठे; minor (D0) लहान; history = display_only candles (राखाडी)."""
    import plotly.graph_objects as go
    d = frame.reset_index(drop=True)
    n_hist = 0
    if history is not None and len(history):
        hist = history[pd.to_datetime(history["timestamp"]) < pd.to_datetime(d["timestamp"]).min()] if len(d) else history
        n_hist = len(hist)
        d = pd.concat([hist[["timestamp", "open", "high", "low", "close"]], d[["timestamp", "open", "high", "low", "close"]]],
                      ignore_index=True)
    fig = BC._base(d, title)
    if n_hist:
        fig.add_vrect(x0=-0.5, x1=n_hist - 0.5, fillcolor="rgba(120,120,120,0.25)", line_width=0, layer="below")
        fig.add_annotation(x=0.01, y=0.02, xref="paper", yref="paper", xanchor="left", showarrow=False, font=dict(size=10, color="#9e9e9e"),
                           text="राखाडी भाग: फक्त दाखवण्यासाठी (holdout / जुना इतिहास) — त्यावर pivots, σ, मोजमाप नाही")
    lo, hi = float(d["low"].min()), float(d["high"].max())
    s = snap[f"D{degree}"]
    t0 = pd.to_datetime(frame["timestamp"]).min() if len(frame) else None

    def dots(ps, size, labels):
        xs, ys, cols, txt, op = [], [], [], [], []
        for p in ps:
            if t0 is None or pd.Timestamp(p["ts"]) < t0:
                continue
            x = _x_of(frame, p["ts"])
            if x is None:
                continue
            xs.append(x + n_hist)
            ys.append(p["price"])
            cols.append(COL[p["kind"]])
            txt.append(p["label"] if labels else "")
            op.append(0.35 if p["warmup"] else 1.0)
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text" if labels else "markers", text=txt,
                                     textposition=["top center" if c == COL["H"] else "bottom center" for c in cols],
                                     marker=dict(size=size, color=cols, opacity=op, line=dict(width=1, color="#ffffff")),
                                     textfont=dict(size=12, color="#ffd54f"), showlegend=False, hoverinfo="skip"))
    if minor is not None:
        dots(snap[f"D{minor}"]["pivots"], 6, False)
    dots(s["pivots"], 13, True)
    tn = s.get("tentative")
    if tn and t0 is not None and pd.Timestamp(tn["ts"]) >= t0:
        x = _x_of(frame, tn["ts"])
        if x is not None:
            fig.add_trace(go.Scatter(x=[x + n_hist], y=[tn["price"]], mode="markers+text", text=["tentative"], textposition="middle right",
                                     marker=dict(size=13, color="rgba(0,0,0,0)", line=dict(width=2, color=COL[tn["kind"]])),
                                     textfont=dict(size=10, color="#b0bec5"), showlegend=False, hoverinfo="skip"))
    pr = s["trend"].get("protected")
    if pr:
        fig.add_shape(type="line", x0=0, x1=len(d) - 1, y0=pr["price"], y1=pr["price"], line=dict(color="#ce93d8", width=1.5, dash="dot"))
        fig.add_annotation(x=len(d) - 1, y=pr["price"], text=f"protected {pr['price']:,.0f}", showarrow=False, xanchor="right",
                           yanchor="bottom", font=dict(size=10, color="#ce93d8"))
    fig.add_annotation(x=0.5, y=0.55, xref="paper", yref="paper", text={"D": "DAILY", "W": "WEEKLY"}.get(tf, tf), showarrow=False,
                       font=dict(size=140, color="rgba(255,255,255,0.07)"))
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=box_text(snap, None), font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64",
                           borderwidth=1)
    BC._finish(fig, d, lo, hi, fmt="%d %b" if tf in ("D", "W") else "%d %b %H:%M")
    return fig


def png(fig):
    return fig.to_image(format="png", scale=1)


def window(f, tf, asof, sessions=None):
    """15M ≥ 5 sessions, 1H ≥ 20 sessions; D / W: सगळा परवानगी असलेला data."""
    if tf not in W_MIN or not len(f):
        return f
    days = sorted(pd.to_datetime(f["timestamp"]).dt.normalize().unique())
    keep = days[-(sessions or W_MIN[tf]):]
    return f[pd.to_datetime(f["timestamp"]).dt.normalize() >= keep[0]].reset_index(drop=True)


def charts(res, asof, history_daily=None):
    """एका दिवस-अखेरचे चार charts ⇒ {tf: png}."""
    m15 = res["m15"]
    m = m15[pd.to_datetime(m15["bar_end"]) <= pd.Timestamp(asof)]
    snap = PE.snapshot(res, asof)
    daily = daily_from_15m(m, asof)
    weekly = weekly_from_daily(daily, asof)
    hd = hw = None
    if history_daily is not None and len(history_daily):
        hd = history_daily[pd.to_datetime(history_daily["timestamp"]) + pd.Timedelta(hours=15, minutes=30) <= pd.Timestamp(asof)]
        hw = weekly_from_daily(hd.assign(bar_end=pd.to_datetime(hd["timestamp"]) + pd.Timedelta(hours=15, minutes=30)), asof)
        hd, hw = display_only(hd), display_only(hw)
    t = pd.Timestamp(asof)
    title = "🧭 SWING CHECK · NIFTY {tf} · {d:%d %b %Y} दिवस-अखेर · {deg}"
    out = {"15M": png(figure(window(m, "15M", asof), "15M", snap, 1, title.format(tf="15M", d=t, deg="D1 (मोठे) + D0 (लहान)"), minor=0)),
           "1H": png(figure(window(agg_1h(m), "1H", asof), "1H", snap, 2, title.format(tf="1H", d=t, deg="D2"), box=False)),
           "D": png(figure(daily, "D", snap, 3, title.format(tf="Daily", d=t, deg="D3"), history=hd, box=False)),
           "W": png(figure(weekly, "W", snap, 4, title.format(tf="Weekly", d=t, deg="D4"), history=hw, box=False))}
    return out, snap


def caption(n, total, snap, asof):
    """≤ 8 ओळी, ≤ 1024 (UTF-16), code keys नाहीत."""
    def last(d):
        ps = snap[f"D{d}"]["pivots"][-2:]
        return " / ".join(f"{p['kind']} {p['price']:,.0f}" for p in ps) or "—"
    lines = [f"🧭 SWING CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y}",
             f"15M (D1): {snap['D1']['trend']['name']} · {last(1)}",
             f"1H (D2): {snap['D2']['trend']['name']} · {last(2)}",
             f"Daily (D3): {snap['D3']['trend']['name']} · {last(3)}",
             f"Weekly (D4): {snap['D4']['trend']['name']}",
             "Reply: ✔ बरोबर · ✘ कोणती degree, कोणता swing चुकला / सुटला"]
    cap = "\n".join(lines)
    while len(cap.encode("utf-16-le")) // 2 > 1024:
        cap = cap[:-2]
    return cap


def k_options_png(m15, df1m, asof, degree, ks, s=None):
    """एकाच दिवसाचे तीन k चे charts शेजारी (Abhi डोळ्यांनी निवडेल). degree 1 ⇒ 15M, 2 ⇒ 1H."""
    from PIL import Image
    ims = []
    for k in ks:
        res = PE.build(m15, df1m, {**(s or {}), "k": {degree: k}})
        snap = PE.snapshot(res, asof)
        m = m15[pd.to_datetime(m15["bar_end"]) <= pd.Timestamp(asof)]
        f = window(m, "15M", asof) if degree == 1 else window(agg_1h(m), "1H", asof)
        fig = figure(f, "15M" if degree == 1 else "1H", snap, degree, f"D{degree} · k = {k:g}", box=False)
        ims.append(Image.open(io.BytesIO(png(fig))).convert("RGB"))
    w, h = ims[0].size
    page = Image.new("RGB", (w * len(ims), h), "#0e1117")
    for i, im in enumerate(ims):
        page.paste(im, (i * w, 0))
    buf = io.BytesIO()
    page.save(buf, "PNG")
    return buf.getvalue()


def table_png(rows, title):
    """मोजमापाचा तक्ता (PDF चं पहिलं पान)."""
    import plotly.graph_objects as go
    cols = ["degree", "n", "leg_bars_median", "leg_sigma_median", "lag_median", "lag_p75", "lag_p90", "at_0915_pct", "rule_1m",
            "rule_conservative", "warmup", "warmup_done"]
    head = ["Degree", "Pivots", "Leg (bars, median)", "Leg (σ, median)", "Confirm lag median", "p75", "p90", "09:15 वर %", "1m नियम",
            "सावध नियम", "Warm-up pivots", "Warm-up पूर्ण"]
    fig = go.Figure(go.Table(header=dict(values=head, fill_color="#263238", font=dict(color="white", size=13)),
                             cells=dict(values=[[r[c] if r[c] is not None else "—" for r in rows] for c in cols], height=30,
                                        fill_color="#0e1117", font=dict(color="white", size=13))))
    fig.update_layout(title=title, template="plotly_dark", width=1400, height=520, paper_bgcolor="#0e1117")
    return png(fig)


def pdf(pages_png, path):
    from PIL import Image
    ims = [Image.open(io.BytesIO(b)).convert("RGB") for b in pages_png]
    if ims:
        ims[0].save(path, save_all=True, append_images=ims[1:], resolution=100)


def grid(pngs, order=("15M", "1H", "D", "W")):
    from PIL import Image
    ims = [Image.open(io.BytesIO(pngs[k])).convert("RGB") for k in order if k in pngs]
    w, h = ims[0].size
    page = Image.new("RGB", (2 * w, 2 * h), "#0e1117")
    for i, im in enumerate(ims):
        page.paste(im.resize((w, h)), ((i % 2) * w, (i // 2) * h))
    buf = io.BytesIO()
    page.save(buf, "PNG")
    return buf.getvalue()
