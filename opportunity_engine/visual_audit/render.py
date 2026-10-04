"""opportunity_engine/visual_audit/render.py — audit साठी chart PNG (spec §17.2). फक्त candles + levels; कुठलाही indicator नाही.

🎓 `pdf_reports.build_report_chart_image` चाच plotly + kaleido पॅटर्न (kaleido/Chrome नसेल तर None — graceful). फरक:
  • x-अक्ष = bar क्रमांक (सलग; शनि-रवि/रात्र आपोआप गायब) आणि तारखेचे ticks — trendline/rangebreak चा प्रश्नच नाही.
  • प्रत्येक level: outer band फिकट, core band गडद; डावीकडे `L1, L2…` (label ↔ level_id mapping `assign_labels`).
  • Swing labels (HH/HL/LH/LL) — structure tracker चे confirmed swings, chart च्या खिडकीतले.
  • Overlay नसलेली आवृत्ती (फक्त candles + swings नाहीत) — स्वतंत्र visual वाचनासाठी (§17.8), म्हणजे model ची नजर गणितावर अवलंबून नाही.
  • Dark theme, 1280×720 (image tokens ≈ 1,200 च्या आसपास मर्यादित).
"""
import numpy as np
import pandas as pd

ZONE_KINDS = ("DEMAND", "SUPPLY", "SUPPORT", "RESISTANCE")       # नजरेने तपासायचे (KEY/GAP/ROUND हे अचूक तथ्य — audit नाही)
CHART_TFS = {"1d": ("1d",), "1h": ("1h", "4h"), "15m": ("15m",)}  # कोणत्या chart वर कोणत्या TF चे levels
DEFAULT_BARS = {"1d": 120, "1h": 70, "15m": 75}                   # Daily ~120 bars · 1H ~10 sessions · 15M ~3 sessions
MAX_LEVELS = 12
WIDTH, HEIGHT = 1280, 720
COLORS = {"DEMAND": "#26a69a", "SUPPORT": "#26a69a", "SUPPLY": "#ef5350", "RESISTANCE": "#ef5350"}


def window(df, tf, bars=None):
    """chart साठी शेवटचे N बंद bars (bar_closed असेल तर फक्त बंद)."""
    if df is None or len(df) == 0:
        return df
    d = df[df["bar_closed"]] if "bar_closed" in df.columns else df
    return d.tail(int(bars or DEFAULT_BARS.get(tf, 100))).reset_index(drop=True)


def assign_labels(levels, tf, lo=None, hi=None, max_levels=MAX_LEVELS, price=None, near=2, near_pct=4.0):
    """chart TF चे zone-levels (तुटलेले/नाकारलेले नाहीत): दिसणाऱ्या किंमत-पट्ट्यातले + `price` च्या वर आणि खालचे सर्वात जवळचे `near` (≤ near_pct %) — ट्रेडरला
    पुढचा अडथळा/आधार chart वर दिसायला हवा (chart चा y-अक्ष त्यांना सामावून घेतो). quality_score नुसार कमाल `max_levels`; किंमतीनुसार वरून खाली L1, L2…
    रिटर्न [{label, level_id, kind, tf, core_low, core_high, outer_low, outer_high, grade}]."""
    tfs = CHART_TFS.get(tf, (tf,))
    cands, pool = [], []
    for lv in levels:
        if lv.get("kind") not in ZONE_KINDS or lv.get("tf") not in tfs or lv.get("reject_reason") or lv.get("status") == "BROKEN" or not lv.get("level_id"):
            continue
        cands.append(lv)
        olo, ohi = float(lv.get("outer_low", lv["low"])), float(lv.get("outer_high", lv["high"]))
        if lo is not None and hi is not None:
            pad = 0.05 * (hi - lo)
            if ohi < lo - pad or olo > hi + pad:
                continue
        pool.append(lv)
    if price is not None and near:
        ids = {id(z) for z in pool}
        above = sorted((z for z in cands if float(z.get("outer_low", z["low"])) > price and id(z) not in ids
                        and (float(z.get("outer_low", z["low"])) - price) / price * 100 <= near_pct), key=lambda z: float(z.get("outer_low", z["low"])))[:near]
        below = sorted((z for z in cands if float(z.get("outer_high", z["high"])) < price and id(z) not in ids
                        and (price - float(z.get("outer_high", z["high"]))) / price * 100 <= near_pct), key=lambda z: -float(z.get("outer_high", z["high"])))[:near]
        pool += above + below
    pool = sorted(pool, key=lambda z: -float(z.get("quality_score") or 0.0))[:max_levels]
    pool = sorted(pool, key=lambda z: -float(z.get("outer_high", z["high"])))
    out = []
    for n, lv in enumerate(pool, start=1):
        out.append({"label": f"L{n}", "level_id": lv["level_id"], "kind": lv["kind"], "tf": lv["tf"],
                    "core_low": round(float(lv.get("core_low", lv["low"])), 2), "core_high": round(float(lv.get("core_high", lv["high"])), 2),
                    "outer_low": round(float(lv.get("outer_low", lv["low"])), 2), "outer_high": round(float(lv.get("outer_high", lv["high"])), 2),
                    "grade": lv.get("quality_grade")})
    return out


def swing_marks(swings, bar_end, lo_time, hi_time):
    """structure tracker चे Swing objects -> chart खिडकीतले [(time, price, label, kind)]."""
    out = []
    for sw in swings or []:
        t = getattr(sw, "time", None)
        if t is None or not (lo_time <= t <= hi_time):
            continue
        out.append((t, float(sw.price), getattr(sw, "label", "") or "", sw.kind))
    return out


def build_figure(df, tf, symbol, labels=None, swings=None, overlay=True, title=None):
    """plotly Figure (PNG export वेगळं). df = window केलेला engine frame (bar_end/open/high/low/close)."""
    import plotly.graph_objects as go
    x = np.arange(len(df))
    fig = go.Figure(go.Candlestick(x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350", showlegend=False))
    n = len(df)
    if overlay:
        for lab in labels or []:
            col = COLORS.get(lab["kind"], "#90a4ae")
            fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=lab["outer_low"], y1=lab["outer_high"], fillcolor=col, opacity=0.10, line_width=0, layer="below")
            fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=lab["core_low"], y1=lab["core_high"], fillcolor=col, opacity=0.30, line_width=0, layer="below")
            fig.add_annotation(x=0, y=(lab["core_low"] + lab["core_high"]) / 2.0, text=f"<b>{lab['label']}</b>", showarrow=False, xanchor="left",
                               font=dict(size=13, color="#ffffff"), bgcolor=col, opacity=0.9)
        times = pd.Series(df["bar_end"])
        idx = {t: k for k, t in enumerate(times)}
        for t, price, lab, kind in swing_marks(swings, times, times.iloc[0], times.iloc[-1]) if len(df) else []:
            k = idx.get(t)
            if k is None or not lab:
                continue
            fig.add_annotation(x=k, y=price, text=lab, showarrow=False, yshift=12 if kind == "H" else -12, font=dict(size=10, color="#ffd54f"))
    ylo, yhi = float(df["low"].min()), float(df["high"].max())
    if overlay and labels:
        ylo, yhi = min(ylo, min(l["outer_low"] for l in labels)), max(yhi, max(l["outer_high"] for l in labels))
    ypad = 0.03 * (yhi - ylo)
    step = max(1, n // 10)
    ticks = list(range(0, n, step))
    fmt = "%d %b %y" if tf == "1d" else "%d %b %H:%M"
    fig.update_xaxes(tickvals=ticks, ticktext=[pd.Timestamp(df["bar_end"].iloc[k]).strftime(fmt) for k in ticks], rangeslider_visible=False,
                     showgrid=False, color="#b0bec5")
    fig.update_yaxes(side="right", nticks=14, tickformat=",.0f", gridcolor="#263238", color="#eceff1", range=[ylo - ypad, yhi + ypad])
    fig.update_layout(template="plotly_dark", width=WIDTH, height=HEIGHT, margin=dict(l=10, r=70, t=40, b=30), paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                      title=dict(text=title or f"{symbol} {tf.upper()} — {'levels L1..' if overlay else 'candles only'}", font=dict(size=15)))
    return fig


def render_png(df, tf, symbol, labels=None, swings=None, overlay=True, title=None):
    """PNG bytes किंवा None (डेटा नाही / kaleido-Chrome नाही — कधीच raise नाही)."""
    if df is None or len(df) < 5:
        return None
    try:
        return build_figure(df, tf, symbol, labels, swings, overlay, title).to_image(format="png", width=WIDTH, height=HEIGHT, scale=1)
    except Exception:
        return None
