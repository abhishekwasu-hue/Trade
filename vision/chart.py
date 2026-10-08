"""vision/chart.py — signal ची 2-panel chart image (setup TF + मोठा TF), overlay सह, ~1000×700 PNG. **No-lookahead.**

🎓 नियम:
  • फक्त signal च्या क्षणापर्यंत पूर्ण झालेले 1-मिनिट bars (`cut_1m`: bar start + 1 मिनिट ≤ signal_ts). मोठे TF हे त्याच कापलेल्या 1m वरून
    NSE session (09:15) anchored resample — त्यामुळे शेवटचा (चालू) bar सुद्धा फक्त signal पर्यंतच्या माहितीचा. पुढची candle कधीच नाही.
  • Overlay: signal level (role नुसार रंग), दिशेचा बाण शेवटच्या bar वर, invalidation (असेल तर). Image मधला मजकूर इंग्रजीत (vision साठी; machine
    वरच्या Devanagari font वर अवलंबून नको). किंमती image वरून कधीच घेतल्या जात नाहीत — vision फक्त enum मत देतो.
  • Plain (overlay नसलेली) image पाठवत नाही (G-COST: एकच image).
  • v2 (signal_check_v2) overlays — `vision/context.py` (causal): major levels (M1↑ / M1↓, flip ⇒ F), PDH / PDL / PDC, PWH / PWL (dotted),
    आजचा open + opening range (फिकट पट्टा), swing H / L खुणा, session separators. 0.1 × median range पेक्षा जवळचे overlays ⇒ एक label
    (उदा. PDH+M1↑); y-range बाहेरचे ⇒ कडेला ▲ / ▼ खुणा. Labels इंग्रजीत; अचूक किंमती फक्त signal text मध्ये.
"""
import numpy as np
import pandas as pd

WIDTH, HEIGHT = 1000, 700
HEIGHT_V21 = 900                     # v2.1: तिसरा (line) panel
SESSION_START = pd.Timedelta(hours=9, minutes=15)
SESSION_END = pd.Timedelta(hours=15, minutes=30)
TF_MAP = {"1M": (5, 15), "5M": (5, 15), "15M": (15, 60), "30M": (30, 60), "60M": (60, "D")}
BARS = {"setup": 60, "higher": 50}
ROLE_COLOR = {"SUPPORT": "#26a69a", "RESISTANCE": "#ef5350"}


def to_ist_naive(ts):
    t = pd.to_datetime(ts)
    if getattr(t, "tzinfo", None) is not None:
        return t.tz_convert("Asia/Kolkata").tz_localize(None)
    if hasattr(t, "dt") and t.dt.tz is not None:
        return t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return t


def norm_1m(df):
    """Upstox 1m frame → [timestamp (naive IST), open, high, low, close], क्रमाने, duplicate नाहीत."""
    d = df[["timestamp", "open", "high", "low", "close"]].copy()
    ts = pd.to_datetime(d["timestamp"])
    if ts.dt.tz is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d["timestamp"] = ts
    return d.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def cut_1m(df1m, signal_ts):
    """signal_ts पर्यंत **पूर्ण** झालेले 1m bars फक्त."""
    t = to_ist_naive(signal_ts)
    return df1m[df1m["timestamp"] + pd.Timedelta(minutes=1) <= t].reset_index(drop=True)


def resample(df1m, tf):
    """tf = मिनिटं (int) किंवा "D". NSE session (09:15) anchored. रिटर्न [start, end, open, high, low, close]."""
    if df1m is None or len(df1m) == 0:
        return pd.DataFrame(columns=["start", "end", "open", "high", "low", "close"])
    d = df1m.copy()
    day = d["timestamp"].dt.normalize()
    if tf == "D":
        d["start"] = day + SESSION_START
        step = SESSION_END - SESSION_START
    else:
        mins = ((d["timestamp"] - day - SESSION_START).dt.total_seconds() // 60).astype(int)
        d["start"] = day + SESSION_START + pd.to_timedelta((mins // int(tf)) * int(tf), unit="m")
        step = pd.Timedelta(minutes=int(tf))
    g = d.groupby("start", sort=True).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                          last_ts=("timestamp", "max")).reset_index()
    g["end"] = np.minimum(g["start"] + step, g["start"].dt.normalize() + SESSION_END)
    return g[["start", "end", "open", "high", "low", "close", "last_ts"]]


def with_last_bar(cut, last_bar, signal_ts):
    """Bot ने signal च्या क्षणी पाहिलेली शेवटची 1m candle (चालू minute) — cut मध्ये नसेल आणि तिची सुरुवात ≤ signal_ts असेल तरच जोडतो.
    ही bot कडची त्या क्षणीची माहिती आहे (lookahead नाही); नसेल तर trigger touch chart वर दिसणार नाही."""
    if not last_bar:
        return cut
    try:
        t = pd.Timestamp(to_ist_naive(last_bar["timestamp"])).floor("min")
        row = {"timestamp": t, **{k: float(last_bar[k]) for k in ("open", "high", "low", "close")}}
    except (KeyError, TypeError, ValueError):
        return cut
    if t > to_ist_naive(signal_ts) or (len(cut) and t <= cut["timestamp"].iloc[-1]):
        return cut
    return pd.concat([cut, pd.DataFrame([row])], ignore_index=True)


def panels(df1m, signal_ts, setup_tf, daily=None, last_bar=None, return_cut=False):
    """(setup frame, higher frame, (setup_min, higher_tf)[, cut]). दोन्ही फक्त signal पर्यंत (+ bot ने पाहिलेली चालू 1m candle, असेल तर)."""
    s_tf, h_tf = TF_MAP.get(str(setup_tf).upper(), (5, 15))
    cut = with_last_bar(cut_1m(norm_1m(df1m), signal_ts), last_bar, signal_ts)
    setup = resample(cut, s_tf).tail(BARS["setup"]).reset_index(drop=True)
    if h_tf == "D":
        today = resample(cut, "D")
        if daily is not None and len(daily):
            dd = norm_1m(daily)
            sig_day = to_ist_naive(signal_ts).normalize()
            old = dd[dd["timestamp"].dt.normalize() < min(sig_day, today["start"].min().normalize() if len(today) else sig_day)]
            old = old.assign(start=old["timestamp"].dt.normalize() + SESSION_START, last_ts=old["timestamp"])
            old["end"] = old["start"].dt.normalize() + SESSION_END
            today = pd.concat([old[["start", "end", "open", "high", "low", "close", "last_ts"]], today], ignore_index=True)
        higher = today.tail(BARS["higher"]).reset_index(drop=True)
    else:
        higher = resample(cut, h_tf).tail(BARS["higher"]).reset_index(drop=True)
    if return_cut:
        return setup, higher, (s_tf, h_tf), cut
    return setup, higher, (s_tf, h_tf)


def _tf_label(tf):
    return "1D" if tf == "D" else (f"{tf // 60}H" if tf >= 60 and tf % 60 == 0 else f"{tf}m")


ROLE_SHORT = {"held_as_support": "held S", "held_as_resistance": "held R", "broken_down": "broken↓", "broken_up": "broken↑", "untested": ""}
OVL_STYLE = {"major": dict(color="#90caf9", width=1), "ref": dict(color="#b0bec5", width=1, dash="dot")}


def _overlays(fig, df, ctx, lo, hi, c, n, label_x):
    """ctx overlays (L वगळून — L वेगळा जाड) एका panel वर. y-range बाहेरचे ⇒ कडेला ▲ / ▼."""
    above, below, placed = [], [], []                                # placed: [(y, slot)] — जवळचे labels एकमेकांवर येऊ नयेत
    gap = 0.03 * (hi - lo)
    for o in sorted((ctx or {}).get("overlays") or [], key=lambda z: z["price"]):
        if "L" in o["kinds"]:
            continue
        y = float(o["price"])
        if y > hi:
            above.append(o["label"])
            continue
        if y < lo:
            below.append(o["label"])
            continue
        style = OVL_STYLE["major" if "major" in o["kinds"] else "ref"]
        fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=y, y1=y, line=style, row=1, col=c)
        busy = {s for py, s in placed if abs(py - y) < gap}
        slot = next((k for k in range(10) if k not in busy), 9)
        placed.append((y, slot))
        rs = "reclaimed" if o.get("reclaimed") else ROLE_SHORT.get(o.get("today_role"), "")
        fig.add_annotation(x=label_x - slot * max(1.0, n * 0.14), y=y, text=o["label"] + (f" · {rs}" if rs else ""), showarrow=False,
                           xanchor="right", yshift=7,
                           font=dict(size=9, color=style["color"]), row=1, col=c)
    if above:
        fig.add_annotation(x=label_x, y=hi, text="▲ " + ", ".join(above), showarrow=False, xanchor="right", yshift=-6,
                           font=dict(size=9, color="#b0bec5"), row=1, col=c)
    if below:
        fig.add_annotation(x=label_x, y=lo, text="▼ " + ", ".join(below), showarrow=False, xanchor="right", yshift=6,
                           font=dict(size=9, color="#b0bec5"), row=1, col=c)


def _separators(fig, df, c, hi, lo):
    days = pd.to_datetime(df["start"]).dt.normalize()
    for k in range(1, len(df)):
        if days.iloc[k] != days.iloc[k - 1]:
            fig.add_shape(type="line", x0=k - 0.5, x1=k - 0.5, y0=lo, y1=hi, line=dict(color="#37474f", width=1, dash="dot"), row=1, col=c)


def _gap_overlays(fig, df, ctx, lo, hi, n, sig):
    """Panel A: [PDC, Open] gap पट्टा (भरलेला भाग वेगळ्या छटेत), opening window (09:15–09:30) छटा, जुने unfilled gaps (UG)."""
    g = (ctx or {}).get("gap_ctx") or {}
    today = pd.Timestamp(to_ist_naive(sig["signal_ts"])).normalize()
    starts = pd.to_datetime(df["start"])
    idx = [k for k in range(n) if starts.iloc[k].normalize() == today]
    if idx:
        ow = [k for k in idx if starts.iloc[k] < today + pd.Timedelta(hours=9, minutes=30)]
        if ow:
            fig.add_shape(type="rect", x0=ow[0] - 0.5, x1=ow[-1] + 0.5, y0=lo, y1=hi, fillcolor="rgba(255,255,255,0.04)", line=dict(width=0),
                          layer="below", row=1, col=1)
    if g.get("has_gap") and idx and g.get("pdc") is not None:
        pdc, o = float(g["pdc"]), float(g["open"])
        a, b = min(pdc, o), max(pdc, o)
        fig.add_shape(type="rect", x0=idx[0] - 0.5, x1=n - 0.5, y0=max(lo, a), y1=min(hi, b), fillcolor="rgba(255,213,79,0.07)",
                      line=dict(width=0), layer="below", row=1, col=1)
        f = float(g.get("fill_pct") or 0) / 100.0
        if f > 0:                                                        # भरलेला भाग (open कडून PDC कडे)
            fa, fb = (o - f * (o - pdc), o) if o > pdc else (o, o + f * (pdc - o))
            fig.add_shape(type="rect", x0=idx[0] - 0.5, x1=n - 0.5, y0=max(lo, min(fa, fb)), y1=min(hi, max(fa, fb)),
                          fillcolor="rgba(255,213,79,0.15)", line=dict(width=0), layer="below", row=1, col=1)
        fig.add_annotation(x=idx[0], y=min(hi, b), text=f"GAP {g.get('class')} fill {g.get('fill_pct'):.0f}%", showarrow=False, xanchor="left",
                           yshift=-8, font=dict(size=9, color="#ffd54f"), row=1, col=1)
    for u in g.get("old_gaps") or []:
        if u["high"] < lo or u["low"] > hi:
            continue
        fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=max(lo, u["low"]), y1=min(hi, u["high"]), fillcolor="rgba(206,147,216,0.07)",
                      line=dict(width=0), layer="below", row=1, col=1)
        fig.add_annotation(x=n * 0.35, y=min(hi, u["high"]), text="UG", showarrow=False, xanchor="left", yshift=-7, font=dict(size=8, color="#ce93d8"),
                           row=1, col=1)


def _line_panel(fig, line, ctx, sig):
    """Panel C: closes ची रेषा (मोठा lookback), L / M / PDC / PDH / PDL, swing ठिपके, session separators, signal क्षणी उभी रेषा — त्यानंतर काहीच नाही."""
    import plotly.graph_objects as go
    if line is None or len(line) < 3:
        return
    x = np.arange(len(line))
    y = line["close"].to_numpy(float)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="#e0e0e0", width=1.4), showlegend=False), row=2, col=1)
    lo, hi = float(y.min()), float(y.max())
    lvl = sig.get("level")
    if lvl is not None:
        lo, hi = min(lo, float(lvl)), max(hi, float(lvl))
    pad = 0.05 * (hi - lo or 1.0)
    lo, hi = lo - pad, hi + pad
    fig.update_yaxes(range=[lo, hi], row=2, col=1)
    n = len(line)
    days = pd.to_datetime(line["start"]).dt.normalize()
    for k in range(1, n):
        if days.iloc[k] != days.iloc[k - 1]:
            fig.add_shape(type="line", x0=k - 0.5, x1=k - 0.5, y0=lo, y1=hi, line=dict(color="#37474f", width=1, dash="dot"), row=2, col=1)
    placed = []
    for o in sorted((ctx or {}).get("overlays") or [], key=lambda z: z["price"]):
        names = o["label"].split("+")
        if not any(nm.startswith(("L", "M", "PDC", "PDH", "PDL")) for nm in names) or not (lo <= o["price"] <= hi):
            continue
        isl = "L" in o["kinds"]
        color = ROLE_COLOR.get((sig.get("role") or "").upper(), "#ffca28") if isl else ("#90caf9" if "major" in o["kinds"] else "#78909c")
        fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=o["price"], y1=o["price"], line=dict(color=color, width=2 if isl else 1,
                      dash=None if isl or "major" in o["kinds"] else "dot"), row=2, col=1)
        busy = {s for py, s in placed if abs(py - o["price"]) < 0.06 * (hi - lo)}
        slot = next((k for k in range(8) if k not in busy), 7)
        placed.append((o["price"], slot))
        fig.add_annotation(x=slot * max(1.0, n * 0.1), y=o["price"], text=o["label"], showarrow=False, xanchor="left", yshift=6,
                           font=dict(size=8, color=color), row=2, col=1)
    for i in range(2, n - 2):                                            # closes वरचे confirmed swings (दोन्ही बाजूंना 2 पूर्ण points)
        if y[i] > y[i - 2:i].max() and y[i] >= y[i + 1:i + 3].max():
            fig.add_trace(go.Scatter(x=[i], y=[y[i]], mode="markers", marker=dict(size=5, color="#ffcc80"), showlegend=False), row=2, col=1)
        if y[i] < y[i - 2:i].min() and y[i] <= y[i + 1:i + 3].min():
            fig.add_trace(go.Scatter(x=[i], y=[y[i]], mode="markers", marker=dict(size=5, color="#80cbc4"), showlegend=False), row=2, col=1)
    fig.add_shape(type="line", x0=n - 1, x1=n - 1, y0=lo, y1=hi, line=dict(color="#ffd54f", width=1), row=2, col=1)
    step = max(1, n // 8)
    fig.update_xaxes(tickvals=list(range(0, n, step)), ticktext=[pd.Timestamp(line["start"].iloc[k]).strftime("%d %b %H:%M") for k in range(0, n, step)],
                     showgrid=False, color="#b0bec5", row=2, col=1)


def build_figure(setup, higher, sig, tfs, ctx=None, line=None):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    s_tf, h_tf = tfs
    with_line = line is not None and len(line) >= 3
    if with_line:
        fig = make_subplots(rows=2, cols=2, column_widths=[0.6, 0.4], row_heights=[0.66, 0.34], horizontal_spacing=0.06, vertical_spacing=0.09,
                            specs=[[{}, {}], [{"colspan": 2}, None]],
                            subplot_titles=(f"setup {_tf_label(s_tf)}", f"higher {_tf_label(h_tf)}", "line: 15m closes (structure, no wicks)"))
    else:
        fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.06,
                            subplot_titles=(f"setup {_tf_label(s_tf)}", f"higher {_tf_label(h_tf)}"))
    level = sig.get("level")
    role = (sig.get("role") or "").upper()
    col = ROLE_COLOR.get(role, "#ffca28")
    inv = sig.get("invalidation")
    if inv is None and ctx is not None:
        inv = ctx.get("invalidation")                                   # bot ने न दिल्यास L ∓ inv_buffer (derived)
    for c, df in ((1, setup), (2, higher)):
        if df is None or len(df) == 0:
            continue
        x = np.arange(len(df))
        fig.add_trace(go.Candlestick(x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"], showlegend=False,
                                     increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=c)
        lo, hi = float(df["low"].min()), float(df["high"].max())
        for v in (level, inv):
            if v is not None and np.isfinite(v):
                lo, hi = min(lo, float(v)), max(hi, float(v))
        pad = 0.04 * (hi - lo or 1.0)
        lo, hi = lo - pad, hi + pad
        fig.update_yaxes(range=[lo, hi], row=1, col=c)
        step = max(1, len(df) // 6)
        fmt = "%d %b" if h_tf == "D" and c == 2 else "%d %b %H:%M"
        fig.update_xaxes(tickvals=list(range(0, len(df), step)), ticktext=[pd.Timestamp(df["start"].iloc[k]).strftime(fmt) for k in range(0, len(df), step)],
                         rangeslider_visible=False, showgrid=False, color="#b0bec5", row=1, col=c)
        n = len(df)
        if ctx is not None:
            if not (h_tf == "D" and c == 2):
                _separators(fig, df, c, hi, lo)
            op = ctx.get("opening") or {}
            if c == 1:
                _gap_overlays(fig, df, ctx, lo, hi, n, sig)
            if c == 1 and op.get("or_high") is not None:                  # आजचा opening range — फिकट पट्टा (आजच्या bars वर)
                today = pd.Timestamp(to_ist_naive(sig["signal_ts"])).normalize()
                idx = [k for k in range(n) if pd.Timestamp(df["start"].iloc[k]).normalize() == today]
                if idx:
                    fig.add_shape(type="rect", x0=idx[0] - 0.5, x1=n - 0.5, y0=max(lo, op["or_low"]), y1=min(hi, op["or_high"]),
                                  fillcolor="rgba(176,190,197,0.06)", line=dict(width=0), layer="below", row=1, col=c)
            _overlays(fig, df, ctx, lo, hi, c, n, n - 1)
            if c == 1:
                for s_ in ctx.get("swings") or []:
                    i = s_["i"]
                    if 0 <= i < n:                                       # sH / sL — "L" अक्षर फक्त traded level साठी
                        fig.add_annotation(x=i, y=s_["price"], text="sH" if s_["kind"] == "H" else "sL", showarrow=False,
                                           yshift=9 if s_["kind"] == "H" else -9, font=dict(size=8, color="#ffcc80"), row=1, col=c)
                comp = ctx.get("composite")
                if comp and 0 <= comp[0] <= comp[1] < n:                 # composite reversal candles (1–3) भोवती फिकट box
                    seg = df.iloc[comp[0]:comp[1] + 1]
                    fig.add_shape(type="rect", x0=comp[0] - 0.45, x1=comp[1] + 0.45, y0=float(seg["low"].min()), y1=float(seg["high"].max()),
                                  line=dict(color="#ffd54f", width=1, dash="dot"), fillcolor="rgba(255,213,79,0.05)", row=1, col=c)
        if level is not None:
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=level, y1=level, line=dict(color=col, width=2), row=1, col=c)
            lo_ = next((o for o in (ctx or {}).get("overlays") or [] if "L" in o["kinds"]), None)
            others = "+".join(x for x in (lo_["label"] if lo_ else "").split("+") if x != "L")
            rshort = ("reclaimed" if lo_.get("reclaimed") else ROLE_SHORT.get(lo_.get("today_role"), "")) if lo_ else ""
            ltxt = f"<b>L {role or 'LEVEL'}</b>" + (f" ({others})" if others else "") + (f" · {rshort}" if rshort else "")
            fig.add_annotation(x=0, y=level, text=ltxt, showarrow=False, xanchor="left", yshift=9,
                               font=dict(size=11, color="#ffffff"), bgcolor=col, row=1, col=c)
        if inv is not None:
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=inv, y1=inv, line=dict(color="#ffca28", width=1, dash="dash"), row=1, col=c)
            if c == 1:
                fig.add_annotation(x=0, y=inv, text="INV", showarrow=False, xanchor="left", yshift=-8, font=dict(size=8, color="#ffca28"),
                                   row=1, col=c)
        if c == 1:
            up = str(sig.get("direction", "")).upper().startswith("BULL")
            y = float(df["low"].iloc[-1]) if up else float(df["high"].iloc[-1])
            fig.add_annotation(x=n - 1, y=y, text="▲ signal" if up else "▼ signal", showarrow=False, yshift=-16 if up else 16,
                               font=dict(size=12, color="#ffd54f"), row=1, col=c)
    if with_line:
        _line_panel(fig, line, ctx, sig)
    ts = pd.Timestamp(to_ist_naive(sig["signal_ts"]))
    title = f"{sig.get('symbol', '')} · {sig.get('bot_label') or sig.get('bot', '')} · {sig.get('direction', '')} · signal {ts:%d %b %H:%M} (chart cut at signal)"
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", color="#eceff1")
    fig.update_layout(template="plotly_dark", width=WIDTH, height=HEIGHT_V21 if with_line else HEIGHT, margin=dict(l=10, r=60, t=60, b=30),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=14)), showlegend=False)
    return fig


def line_frame(cut, sessions=5):
    """Panel C: शेवटच्या `sessions` दिवसांचे 15m closes (signal पर्यंतच — cut मधून)."""
    m15 = resample(cut, 15)
    if len(m15) == 0:
        return m15
    days = sorted(pd.to_datetime(m15["start"]).dt.normalize().unique())[-int(sessions):]
    return m15[pd.to_datetime(m15["start"]).dt.normalize().isin(days)].reset_index(drop=True)


def render(df1m, sig, daily=None):
    """रिटर्न (png bytes | None, meta). meta = {setup_last, higher_last, setup_bars, higher_bars, error}. कधीच raise नाही."""
    meta = {"setup_last": None, "higher_last": None, "setup_bars": 0, "higher_bars": 0, "error": None}
    try:
        setup, higher, tfs, cut = panels(df1m, sig["signal_ts"], sig.get("setup_tf"), daily, sig.get("last_bar"), return_cut=True)
        meta.update(setup_last=str(setup["last_ts"].max()) if len(setup) else None, higher_last=str(higher["last_ts"].max()) if len(higher) else None,
                    setup_bars=len(setup), higher_bars=len(higher), tfs=[s for s in tfs])
        rng = (setup["high"] - setup["low"]).tail(20)
        meta["median_range"] = float(rng.median()) if len(rng) else None              # V1 drift guard (setup TF, signal पर्यंतच)
        if len(setup) < 5:
            meta["error"] = "setup TF चे bars अपुरे"
            return None, meta
        ctx = None
        if sig.get("chart_version", 2) >= 2:
            try:
                from . import context as CX
                ctx = CX.build(cut, setup, sig, meta["median_range"], daily)
            except Exception as exc:                                     # संदर्भ अपयशी ⇒ v1 सारखा chart (overlays शिवाय), नोंद
                meta["ctx_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        meta["ctx"] = ctx
        line = line_frame(cut, int((sig.get("ctx_settings") or {}).get("line_lookback_sessions", 5))) if ctx is not None else None
        fig = build_figure(setup, higher, sig, tfs, ctx, line)
        png = fig.to_image(format="png", width=WIDTH, height=int(fig.layout.height or HEIGHT), scale=1)
        return png, meta
    except Exception as exc:                                             # kaleido/Chrome नाही, डेटा विचित्र — worker ने unavailable नोंदवावं
        meta["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        return None, meta
