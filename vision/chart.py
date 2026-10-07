"""vision/chart.py — signal ची 2-panel chart image (setup TF + मोठा TF), overlay सह, ~1000×700 PNG. **No-lookahead.**

🎓 नियम:
  • फक्त signal च्या क्षणापर्यंत पूर्ण झालेले 1-मिनिट bars (`cut_1m`: bar start + 1 मिनिट ≤ signal_ts). मोठे TF हे त्याच कापलेल्या 1m वरून
    NSE session (09:15) anchored resample — त्यामुळे शेवटचा (चालू) bar सुद्धा फक्त signal पर्यंतच्या माहितीचा. पुढची candle कधीच नाही.
  • Overlay: signal level (role नुसार रंग), दिशेचा बाण शेवटच्या bar वर, invalidation (असेल तर). Image मधला मजकूर इंग्रजीत (kaleido मध्ये
    Devanagari font नसतो). किंमती image वरून कधीच घेतल्या जात नाहीत — vision फक्त enum मत देतो.
  • Plain (overlay नसलेली) image पाठवत नाही (G-COST: एकच image).
"""
import numpy as np
import pandas as pd

WIDTH, HEIGHT = 1000, 700
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


def panels(df1m, signal_ts, setup_tf, daily=None, last_bar=None):
    """(setup frame, higher frame, (setup_min, higher_tf)). दोन्ही फक्त signal पर्यंत (+ bot ने पाहिलेली चालू 1m candle, असेल तर)."""
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
    return setup, higher, (s_tf, h_tf)


def _tf_label(tf):
    return "1D" if tf == "D" else (f"{tf // 60}H" if tf >= 60 and tf % 60 == 0 else f"{tf}m")


def build_figure(setup, higher, sig, tfs):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    s_tf, h_tf = tfs
    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.06,
                        subplot_titles=(f"setup {_tf_label(s_tf)}", f"higher {_tf_label(h_tf)}"))
    level = sig.get("level")
    role = (sig.get("role") or "").upper()
    col = ROLE_COLOR.get(role, "#ffca28")
    inv = sig.get("invalidation")
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
        fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=c)
        step = max(1, len(df) // 6)
        fmt = "%d %b" if h_tf == "D" and c == 2 else "%d %b %H:%M"
        fig.update_xaxes(tickvals=list(range(0, len(df), step)), ticktext=[pd.Timestamp(df["start"].iloc[k]).strftime(fmt) for k in range(0, len(df), step)],
                         rangeslider_visible=False, showgrid=False, color="#b0bec5", row=1, col=c)
        n = len(df)
        if level is not None:
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=level, y1=level, line=dict(color=col, width=2), row=1, col=c)
            fig.add_annotation(x=0, y=level, text=f"<b>L {role or 'LEVEL'}</b>", showarrow=False, xanchor="left", yshift=9,
                               font=dict(size=11, color="#ffffff"), bgcolor=col, row=1, col=c)
        if inv is not None:
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=inv, y1=inv, line=dict(color="#ffca28", width=1, dash="dash"), row=1, col=c)
        if c == 1:
            up = str(sig.get("direction", "")).upper().startswith("BULL")
            y = float(df["low"].iloc[-1]) if up else float(df["high"].iloc[-1])
            fig.add_annotation(x=n - 1, y=y, text="▲ signal" if up else "▼ signal", showarrow=False, yshift=-16 if up else 16,
                               font=dict(size=12, color="#ffd54f"), row=1, col=c)
    ts = pd.Timestamp(to_ist_naive(sig["signal_ts"]))
    title = f"{sig.get('symbol', '')} · {sig.get('bot_label') or sig.get('bot', '')} · {sig.get('direction', '')} · signal {ts:%d %b %H:%M} (chart cut at signal)"
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", color="#eceff1")
    fig.update_layout(template="plotly_dark", width=WIDTH, height=HEIGHT, margin=dict(l=10, r=60, t=60, b=30), paper_bgcolor="#0e1117",
                      plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=14)), showlegend=False)
    return fig


def render(df1m, sig, daily=None):
    """रिटर्न (png bytes | None, meta). meta = {setup_last, higher_last, setup_bars, higher_bars, error}. कधीच raise नाही."""
    meta = {"setup_last": None, "higher_last": None, "setup_bars": 0, "higher_bars": 0, "error": None}
    try:
        setup, higher, tfs = panels(df1m, sig["signal_ts"], sig.get("setup_tf"), daily, sig.get("last_bar"))
        meta.update(setup_last=str(setup["last_ts"].max()) if len(setup) else None, higher_last=str(higher["last_ts"].max()) if len(higher) else None,
                    setup_bars=len(setup), higher_bars=len(higher), tfs=[s for s in tfs])
        if len(setup) < 5:
            meta["error"] = "setup TF चे bars अपुरे"
            return None, meta
        png = build_figure(setup, higher, sig, tfs).to_image(format="png", width=WIDTH, height=HEIGHT, scale=1)
        return png, meta
    except Exception as exc:                                             # kaleido/Chrome नाही, डेटा विचित्र — worker ने unavailable नोंदवावं
        meta["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        return None, meta
