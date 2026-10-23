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
  • PA standard §4 (track T8) — **setting `chart_objects`, default "off"** (off ⇒ byte-for-byte today): "on" ⇒ the signal's object list
    (decision3.draw_objects: swings, areas + state, lines, channels, levels, patterns, liquidity, sweeps, divergence, E1–E4 marks —
    `sig["objects"]` or the gate tags' `objects`) drawn by decision3.draw_render, the same drawing as the verification charts.
  • TA4 (Abhi, design §10) — **setting `vision_chart_bands`, default OFF** (OFF ⇒ image main सारखीच, byte-for-byte): ON ⇒ major levels
    (एकच किंमत, M1↑ / M1↓) chart वर रेषा नाहीत; त्याऐवजी 15m वरचे shared band check pass होणारे पट्टे (`chart_bands`:
    decision3.levels.display_bands — ≤ 3 वर, ≤ 3 खाली, शेवटचा तुटलेला dashed). रंग L (हिरवा / लाल) पासून वेगळे: supply नारिंगी, demand
    फिकट निळा, broken तपकिरी-राखाडी dashed. ctx["bands"] ⇒ signal text मध्ये legend + अचूक किंमती (signal_audit.signal_text).
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


ROLE_SHORT = {"held_as_support": "held S", "held_as_resistance": "held R", "broken_down": "broken↓", "broken_up": "broken↑",
              "reclaimed": "reclaimed", "untested": ""}
OVL_STYLE = {"major": dict(color="#90caf9", width=1), "ref": dict(color="#b0bec5", width=1, dash="dot")}


def no_majors(o):
    """TA4: an overlay without its single-price major levels (M1↑ / M1↓ …) — None when only majors are left."""
    names = [x for x in o["label"].split("+") if not x.startswith("M")]
    kinds = [k for k in o["kinds"] if k != "major"]
    if not names or not kinds:
        return None
    return {**o, "label": "+".join(names), "kinds": kinds}


def chart_bands(cut, s=None):
    """TA4: the bands the approval chart draws — the shared band finder (decision3.levels.display_bands) on the 15m bars of `cut`
    (signal-time 1m, no look-ahead). Returns the facts list (may be empty)."""
    from decision3 import levels as LV
    m15 = resample(cut, 15).rename(columns={"start": "timestamp"})
    if len(m15) < 30:
        return []
    return LV.display_bands(m15[["timestamp", "open", "high", "low", "close"]], len(m15) - 1, s)


BAND_COLOR = {"resistance": ("#ffa726", "rgba(255,167,38,0.10)"), "support": ("#4fc3f7", "rgba(79,195,247,0.10)"),
              "broken": ("#bcaaa4", "rgba(0,0,0,0)")}                  # L = हिरवा / लाल ⇒ पट्टे नारिंगी / फिकट निळे (टक्कर नाही)


def method_bands(sig):
    """Layer 6b (`vision_chart_band_finder = method`): the decision's own areas from the engine gate tags (`gate.areas`, written by
    paper.engine_entry.engine_gate_tags from the engine row: the traded area + the watch list) — one base, wick to body, with the K4 state
    and the confluence label; nothing re-found from the chart. None when the signal carries no engine areas (then nothing is drawn)."""
    g = ((sig.get("tags") or {}).get("gate") or {}) if isinstance(sig.get("tags"), dict) else {}
    areas = g.get("areas")
    if not isinstance(areas, list):
        return None
    out = []
    for a in areas:
        try:
            lo, hi = sorted((float(a["lo"]), float(a["hi"])))
        except (KeyError, TypeError, ValueError):
            continue
        st = str(a.get("state") or "ACTIVE").upper()
        out.append({"role": a.get("role"), "lo": lo, "hi": hi, "method": True, "state": st, "valid": st != "BROKEN",
                    "broken": st == "BROKEN", "flipped": st == "FLIPPED", "confluence_label": a.get("confluence_label"),
                    "touch_count": None})
    return out


def band_rows(bands):
    """ctx["bands"] (signal text साठी): role, low, high, reaction touches, state. Method bands (layer 6b): touches None, the K4 state,
    `finder` = "method"."""
    if any(b.get("method") for b in bands or ()):
        return [{"role": b.get("role"), "lo": float(b["lo"]), "hi": float(b["hi"]), "touches": None, "finder": "method",
                 "state": b["state"].lower() + (f" ({b['confluence_label']})" if b.get("confluence_label") else "")} for b in bands]
    return [{"role": b.get("role"), "lo": float(b["lo"]), "hi": float(b["hi"]), "touches": int(b.get("touch_count") or 0),
             "state": "broken (most recent)" if (b.get("broken") and not b.get("valid")) else
             ("flipped" if b.get("flipped") else ("established" if b.get("established") else "valid"))} for b in bands]


def _bands(fig, bands, lo, hi, c, n, label_x):
    """TA4 bands on one price panel: valid filled (supply red / demand green), the most recent broken one dashed grey; labels in English."""
    for b in bands or []:
        if b["hi"] < lo or b["lo"] > hi:
            continue
        broken = b.get("broken") and not b.get("valid")
        colr, fill = BAND_COLOR["broken" if broken else ("resistance" if b.get("role") == "resistance" else "support")]
        fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=max(lo, b["lo"]), y1=min(hi, b["hi"]), layer="below", fillcolor=fill,
                      line=dict(color=colr, width=1, dash="dash" if broken else None), row=1, col=c)
        if c == 1:
            role = "supply" if b.get("role") == "resistance" else "demand"
            txt = f"{role} {b['lo']:,.0f}-{b['hi']:,.0f} · " + (
                b["state"].lower() + (f" · {b['confluence_label']}" if b.get("confluence_label") else "") if b.get("method")
                else "broken" if broken else f"{b['touch_count']} touches")
            fig.add_annotation(x=label_x, y=min(hi, b["hi"]), text=txt, showarrow=False, xanchor="right", yshift=-7,
                               font=dict(size=8, color=colr), row=1, col=c)


def _overlays(fig, df, ctx, lo, hi, c, n, label_x, hide_majors=False):
    """ctx overlays (L वगळून — L वेगळा जाड) एका panel वर. y-range बाहेरचे ⇒ कडेला ▲ / ▼. hide_majors (TA4): single-price major levels नाहीत."""
    above, below, placed = [], [], []                                # placed: [(y, slot)] — जवळचे labels एकमेकांवर येऊ नयेत
    gap = 0.03 * (hi - lo)
    for o in sorted((ctx or {}).get("overlays") or [], key=lambda z: z["price"]):
        if "L" in o["kinds"]:
            continue
        if hide_majors:
            o = no_majors(o)
            if o is None:
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
        rs = ROLE_SHORT.get(o.get("today_role"), "")
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


def _line_panel(fig, line, ctx, sig, row=3, hide_majors=False):
    """Panel C: closes ची रेषा (मोठा lookback), L / M / PDC / PDH / PDL, swing ठिपके, session separators, signal क्षणी उभी रेषा — त्यानंतर काहीच नाही."""
    import plotly.graph_objects as go
    if line is None or len(line) < 3:
        return
    x = np.arange(len(line))
    y = line["close"].to_numpy(float)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="#e0e0e0", width=1.4), showlegend=False), row=row, col=1)
    lo, hi = float(y.min()), float(y.max())
    lvl = sig.get("level")
    if lvl is not None:
        lo, hi = min(lo, float(lvl)), max(hi, float(lvl))
    pad = 0.05 * (hi - lo or 1.0)
    lo, hi = lo - pad, hi + pad
    fig.update_yaxes(range=[lo, hi], row=row, col=1)
    n = len(line)
    days = pd.to_datetime(line["start"]).dt.normalize()
    for k in range(1, n):
        if days.iloc[k] != days.iloc[k - 1]:
            fig.add_shape(type="line", x0=k - 0.5, x1=k - 0.5, y0=lo, y1=hi, line=dict(color="#37474f", width=1, dash="dot"), row=row, col=1)
    placed = []
    for o in sorted((ctx or {}).get("overlays") or [], key=lambda z: z["price"]):
        if hide_majors and "L" not in o["kinds"]:
            o = no_majors(o)
            if o is None:
                continue
        names = o["label"].split("+")
        if not any(nm.startswith(("L", "M", "PDC", "PDH", "PDL")) for nm in names) or not (lo <= o["price"] <= hi):
            continue
        isl = "L" in o["kinds"]
        color = ROLE_COLOR.get((sig.get("role") or "").upper(), "#ffca28") if isl else ("#90caf9" if "major" in o["kinds"] else "#78909c")
        fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=o["price"], y1=o["price"], line=dict(color=color, width=2 if isl else 1,
                      dash=None if isl or "major" in o["kinds"] else "dot"), row=row, col=1)
        busy = {s for py, s in placed if abs(py - o["price"]) < 0.06 * (hi - lo)}
        slot = next((k for k in range(8) if k not in busy), 7)
        placed.append((o["price"], slot))
        fig.add_annotation(x=slot * max(1.0, n * 0.1), y=o["price"], text=o["label"], showarrow=False, xanchor="left", yshift=6,
                           font=dict(size=8, color=color), row=row, col=1)
    for i in range(2, n - 2):                                            # closes वरचे confirmed swings (दोन्ही बाजूंना 2 पूर्ण points)
        if y[i] > y[i - 2:i].max() and y[i] >= y[i + 1:i + 3].max():
            fig.add_trace(go.Scatter(x=[i], y=[y[i]], mode="markers", marker=dict(size=5, color="#ffcc80"), showlegend=False), row=row, col=1)
        if y[i] < y[i - 2:i].min() and y[i] <= y[i + 1:i + 3].min():
            fig.add_trace(go.Scatter(x=[i], y=[y[i]], mode="markers", marker=dict(size=5, color="#80cbc4"), showlegend=False), row=row, col=1)
    fig.add_shape(type="line", x0=n - 1, x1=n - 1, y0=lo, y1=hi, line=dict(color="#ffd54f", width=1), row=row, col=1)
    step = max(1, n // 8)
    fig.update_xaxes(tickvals=list(range(0, n, step)), ticktext=[pd.Timestamp(line["start"].iloc[k]).strftime("%d %b %H:%M") for k in range(0, n, step)],
                     showgrid=False, color="#b0bec5", row=row, col=1)


def build_figure(setup, higher, sig, tfs, ctx=None, line=None, vols=None, bands=None, objects=None, xmaps=None, errors=None):
    """objects (PA standard §4, setting `chart_objects` = on) = the signal's object list (decision3.draw_objects, already validated),
    drawn by decision3.draw_render — the same geometry and labels as the verification charts; xmaps = (setup XMap, higher XMap) over
    the full signal-time bars (lines anchored before the window keep their slope). None (default) ⇒ the image exactly as today.
    vols = (setup volume array, higher volume array) — `panel_volumes`; None ⇒ volume pane मध्ये "volume: NA (grade cap B)".
    Volume pane (row 2) प्रत्येक price panel खाली — image size तोच (price panel ची उंची कमी).
    bands (TA4) = `chart_bands` चे पट्टे; दिले ⇒ ते पट्टे काढतो आणि single-price major levels लपवतो; None ⇒ जुनं drawing."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from decision3 import volume_pane as VP
    s_tf, h_tf = tfs
    with_line = line is not None and len(line) >= 3
    if with_line:
        fig = make_subplots(rows=3, cols=2, column_widths=[0.6, 0.4], row_heights=[0.50, 0.14, 0.36], horizontal_spacing=0.06,
                            vertical_spacing=0.06, specs=[[{}, {}], [{}, {}], [{"colspan": 2}, None]],
                            subplot_titles=(f"setup {_tf_label(s_tf)}", f"higher {_tf_label(h_tf)}", "", "",
                                            "line: 15m closes (structure, no wicks)"))
    else:
        fig = make_subplots(rows=2, cols=2, column_widths=[0.6, 0.4], row_heights=[0.78, 0.22], horizontal_spacing=0.06,
                            vertical_spacing=0.07, subplot_titles=(f"setup {_tf_label(s_tf)}", f"higher {_tf_label(h_tf)}", "", ""))
    level = sig.get("level")
    role = (sig.get("role") or "").upper()
    col = ROLE_COLOR.get(role, "#ffca28")
    gate = ((sig.get("tags") or {}).get("gate") or {}) if isinstance(sig.get("tags"), dict) else {}   # level bots confirmation (§9)
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
        for v in (level, inv) + (tuple(gate.get(k) for k in ("sl", "target")) if c == 1 else ()):
            if v is not None and np.isfinite(v):
                lo, hi = min(lo, float(v)), max(hi, float(v))
        pad = 0.04 * (hi - lo or 1.0)
        lo, hi = lo - pad, hi + pad
        fig.update_yaxes(range=[lo, hi], row=1, col=c)
        step = max(1, len(df) // 6)
        fmt = "%d %b" if h_tf == "D" and c == 2 else "%d %b %H:%M"
        fig.update_xaxes(tickvals=list(range(0, len(df), step)), ticktext=[pd.Timestamp(df["start"].iloc[k]).strftime(fmt) for k in range(0, len(df), step)],
                         rangeslider_visible=False, showgrid=False, color="#b0bec5", range=[-0.5, len(df) - 0.5], row=1, col=c)
        vol = (vols or (None, None))[c - 1]
        vst = VP.study(df, vol=np.full(len(df), np.nan) if vol is None else vol, info=sig, symbol=sig.get("symbol"),
                       d=sig.get("direction"), area=_area_of(sig), engine_numbers=c == 1,   # engine आकडे फक्त setup (confirmation) TF चे
                       words=volume_words(sig))                         # layer 6b setting (default legacy = today's text)
        if c == 2 and (vst["arm"] is None or vst["arm"] >= vst["commit"]):
            vst = VP.plain(vst)                                         # मोठा TF: arrival आणि commitment एकाच bar मध्ये ⇒ साधे bars, label नाही
        VP.add_plotly(fig, vst, row=2, col=c, title=f"vol {VP.source_label(sig.get('symbol'))}")
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
            if bands is not None and not (objects and any(o["kind"] == "area" for o in objects)):   # PA §4: object areas win
                _bands(fig, bands, lo, hi, c, n, n - 1)
            _overlays(fig, df, ctx, lo, hi, c, n, n - 1, hide_majors=bands is not None)
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
        if objects:
            _objects(fig, objects, df, lo, hi, c, (xmaps or (None, None))[c - 1], sig=sig, inv=inv, errors=errors)
        if level is not None:
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=level, y1=level, line=dict(color=col, width=2), row=1, col=c)
            lo_ = next((o for o in (ctx or {}).get("overlays") or [] if "L" in o["kinds"]), None)
            others = "+".join(x for x in (lo_["label"] if lo_ else "").split("+") if x != "L")
            rshort = ROLE_SHORT.get(lo_.get("today_role"), "") if lo_ else ""
            ltxt = f"<b>L {role or 'LEVEL'}</b>" + (f" ({others})" if others else "") + (f" · {rshort}" if rshort else "")
            fig.add_annotation(x=0, y=level, text=ltxt, showarrow=False, xanchor="left", yshift=9,
                               font=dict(size=11, color="#ffffff"), bgcolor=col, row=1, col=c)
        if inv is not None:
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=inv, y1=inv, line=dict(color="#ffca28", width=1, dash="dash"), row=1, col=c)
            if c == 1:
                fig.add_annotation(x=0, y=inv, text="INV", showarrow=False, xanchor="left", yshift=-8, font=dict(size=8, color="#ffca28"),
                                   row=1, col=c)
        if c == 1 and gate:                                                # area पट्टा + entry / SL / target (confirmation)
            a = gate.get("area") or [None, None]
            if a[0] is not None and a[1] is not None:
                fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=float(a[0]), y1=float(a[1]), fillcolor="rgba(66,165,245,0.12)",
                              line=dict(width=0), layer="below", row=1, col=c)
            for k_, lab, colr in (("entry", "ENTRY", "#ffd54f"), ("sl", "ENGINE REF SL", "#ef5350"),      # Abhi RR2: trade SL / target
                                  ("target", "ENGINE REF TARGET", "#66bb6a")):                      # = dashboard; हे फक्त माहिती
                v = gate.get(k_)
                if v is not None and np.isfinite(float(v)):
                    fig.add_shape(type="line", x0=n * 0.6, x1=n - 0.5, y0=float(v), y1=float(v), line=dict(color=colr, width=1, dash="dot"),
                                  row=1, col=c)
                    fig.add_annotation(x=n - 1, y=float(v), text=f"{lab} {float(v):,.0f}", showarrow=False, xanchor="right", yshift=8,
                                       font=dict(size=9, color=colr), row=1, col=c)
        if c == 1:
            up = str(sig.get("direction", "")).upper().startswith("BULL")
            y = float(df["low"].iloc[-1]) if up else float(df["high"].iloc[-1])
            fig.add_annotation(x=n - 1, y=y, text="▲ signal" if up else "▼ signal", showarrow=False, yshift=-16 if up else 16,
                               font=dict(size=12, color="#ffd54f"), row=1, col=c)
    if with_line:
        _line_panel(fig, line, ctx, sig, row=3, hide_majors=bands is not None)
    ts = pd.Timestamp(to_ist_naive(sig["signal_ts"]))
    ev = pd.Timestamp(to_ist_naive(sig["asof"])) if sig.get("asof") is not None else ts
    cutnote = "chart cut at signal" if ev == ts else f"evaluated at bar close {ev:%H:%M}"
    title = f"{sig.get('symbol', '')} · {sig.get('bot_label') or sig.get('bot', '')} · {sig.get('direction', '')} · signal {ts:%d %b %H:%M} ({cutnote})"
    if gate:
        rr = f" · R:R {gate.get('rr')}" if gate.get("rr") is not None else ""   # R:R फक्त dashboard rr gate चालू असेल तर
        title += f"<br><sup>{gate.get('trend') or ''} · {gate.get('form') or ''}{rr}</sup>"
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", color="#eceff1")
    fig.update_layout(template="plotly_dark", width=WIDTH, height=HEIGHT_V21 if with_line else HEIGHT, margin=dict(l=10, r=60, t=60, b=30),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=14)), showlegend=False)
    return fig


def clean_ctx(sig, df, inv=None):
    """P8 clean charts: the trade context of a signal for decision3.chart_lines.select — direction, the entry area (gate tags), the
    refined base and evidence line ids (entry tags, when the engine sent them), the invalidation, the setup bars. Display only."""
    tags = (sig.get("tags") or {}) if isinstance(sig.get("tags"), dict) else {}
    g = tags.get("gate") or {}
    a = g.get("area") or [None, None]
    rb = g.get("refined") or {}
    d = 1 if str(sig.get("direction", "")).upper().startswith("BULL") else -1
    inv = tags.get("entry_invalidation", inv)
    inv = inv.get("price") if isinstance(inv, dict) else inv
    bars = df.rename(columns={"start": "timestamp"})[["timestamp", "high", "low", "close"]] if df is not None and len(df) else None
    return {"t": None if bars is None else bars["timestamp"].iloc[-1], "d": d, "bars": bars,
            "area": (float(a[0]), float(a[1])) if a[0] is not None and a[1] is not None else None,
            "refined": (float(rb["lo"]), float(rb["hi"])) if rb.get("lo") is not None and rb.get("hi") is not None else None,
            "invalidation": None if inv is None else float(inv), "evidence_ids": g.get("evidence_lines") or [],
            "entry_ref": tags.get("entry_ref"), "setup_tf": "15M"}


def _objects(fig, objects, df, lo, hi, c, xm=None, sig=None, inv=None, errors=None):
    """PA §4: the object list on one price panel (decision3.draw_render primitives). Setup panel: shapes + labels; higher panel:
    shapes only (it is narrow). The panel's price range is kept — an object outside it becomes an ▲ / ▼ note. P8 clean charts:
    decision3.chart_lines.select picks the lines shown (cap = the display setting `chart_max_lines`); the rest are listed as
    "hidden: N" (the PNG has no toggle). Display only: any failure here leaves the chart without its objects (noted in `errors`,
    render's meta["objects_error"]) — never no PNG."""
    try:
        from decision3 import chart_lines as CL
        from decision3 import draw_render as DR
        xm = xm or DR.XMap(df["start"], 0)
        n = int(((sig or {}).get("ctx_settings") or {}).get("chart_max_lines") or CL.max_lines_default())
        sel = CL.select(objects, clean_ctx(sig or {}, df, inv), max_lines=n)
        prims = DR.geometry(sel["shown"], xm, ylim=(lo, hi), short=True, max_lines=n, hidden_n=len(sel["hidden"]) if c == 1 else None)
    except Exception as exc:                                             # noqa: BLE001 — display only
        if errors is not None:
            errors.append(f"panel {c}: {type(exc).__name__}: {str(exc)[:120]}")
        return
    DR.draw_plotly(fig, prims, row=1, col=c, label=c == 1)


def chart_objects_of(sig):
    """The signal's object list (PA §4): `sig["objects"]`, else the engine gate tags' `objects` (written by the engine adapter —
    track T9). Returns (valid objects, dropped reasons); never raises."""
    from decision3 import draw_objects as DO
    g = ((sig.get("tags") or {}).get("gate") or {}) if isinstance(sig.get("tags"), dict) else {}
    raw = sig.get("objects") if sig.get("objects") is not None else g.get("objects")
    return DO.clean(raw if isinstance(raw, list) else [])


def _xmaps(cut, setup, higher, tfs):
    """XMaps over the full signal-time bars of each panel (setup = resample of cut; higher Daily panel = its own rows)."""
    from decision3 import draw_render as DR
    out = []
    for df, tf in ((setup, tfs[0]), (higher, tfs[1])):
        if df is None or not len(df):
            out.append(None)
            continue
        full = resample(cut, tf) if tf != "D" else df
        j0 = max(0, len(full) - len(df)) if tf != "D" else 0
        out.append(DR.XMap(full["start"], j0, n=len(df)))
    return tuple(out)


def _area_of(sig):
    """Volume pane चा area: gate area (confirmation) नाहीतर signal level (एकच किंमत)."""
    g = ((sig.get("tags") or {}).get("gate") or {}) if isinstance(sig.get("tags"), dict) else {}
    a = g.get("area") or [None, None]
    if a[0] is not None and a[1] is not None:
        return float(a[0]), float(a[1])
    lv = sig.get("level")
    return (float(lv), float(lv)) if lv is not None else None


def panel_volumes(setup, higher, sig, asof, df1m=None, fut=None):
    """(setup vol, higher vol) arrays. Index ⇒ futures volume (`fut`: timestamp, volume — worker आणतो; नाही ⇒ NA); MCX / इतर ⇒ df1m चा
    स्वतःचा volume. फक्त asof पर्यंत संपलेल्या rows (भविष्य नाही)."""
    from decision3 import volume_pane as VP
    src = fut if VP.is_index(sig.get("symbol")) else (df1m[["timestamp", "volume"]] if df1m is not None and "volume" in df1m.columns else None)
    if src is not None and len(src):
        src = src.assign(timestamp=to_ist_naive(pd.to_datetime(src["timestamp"])))
    return tuple(VP.bar_volume(df["start"], df["end"], src, asof) if df is not None and len(df) else None for df in (setup, higher))


def line_frame(cut, sessions=5):
    """Panel C: शेवटच्या `sessions` दिवसांचे 15m closes (signal पर्यंतच — cut मधून)."""
    m15 = resample(cut, 15)
    if len(m15) == 0:
        return m15
    days = sorted(pd.to_datetime(m15["start"]).dt.normalize().unique())[-int(sessions):]
    return m15[pd.to_datetime(m15["start"]).dt.normalize().isin(days)].reset_index(drop=True)


def volume_words(sig):
    """Layer 6b: `vision_volume_words` (ctx_settings) — "legacy" (default, today's text) / "method"."""
    from decision3 import volume_pane as VP
    return VP.words_of((sig.get("ctx_settings") or {}).get("vision_volume_words"))


def _volume_line(setup, sig, vols, engine=False):
    """The caption's volume line (the setup pane's study). engine (the engine card, DECISIONS 53 VP3) ⇒ its words (`VP.engine_words`)."""
    from decision3 import volume_pane as VP
    v = (vols or (None,))[0]
    st = VP.study(setup, vol=np.full(len(setup), np.nan) if v is None else v, info=sig, d=sig.get("direction"), area=_area_of(sig),
                  words=volume_words(sig))
    return VP.engine_words(st)["line"] if engine else st["line"]


def render(df1m, sig, daily=None, fut=None):
    """रिटर्न (png bytes | None, meta). meta = {setup_last, higher_last, setup_bars, higher_bars, error}. कधीच raise नाही.
    fut = index च्या futures चे candles (timestamp, volume) — volume pane साठी (नाही ⇒ "volume: NA (grade cap B)")."""
    meta = {"setup_last": None, "higher_last": None, "setup_bars": 0, "higher_bars": 0, "error": None}
    try:
        asof = sig.get("asof") if sig.get("asof") is not None else sig["signal_ts"]   # bar बंद होईपर्यंत थांबलं असेल तर तिथपर्यंत (भविष्य नाही)
        setup, higher, tfs, cut = panels(df1m, asof, sig.get("setup_tf"), daily, sig.get("last_bar"), return_cut=True)
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
        try:
            vols = panel_volumes(setup, higher, sig, asof, df1m, fut)
        except Exception as exc:                                         # volume पूरक ⇒ NA pane, chart तरी
            vols, meta["vol_error"] = None, f"{type(exc).__name__}: {str(exc)[:120]}"
        from . import engine_audit as EA
        if EA.use_engine(sig):                                           # T-5: an engine signal ⇒ the engine's own card
            return _render_engine(cut, setup, higher, tfs, sig, ctx, vols, meta, fut=fut)
        bands = None                                                    # default (setting OFF) ⇒ जुनं drawing, ctx तसाच
        if ctx is not None and (sig.get("ctx_settings") or {}).get("vision_chart_bands"):
            try:
                finder = (sig.get("ctx_settings") or {}).get("vision_chart_band_finder") or "validity"   # layer 6b setting
                bands = method_bands(sig) if finder == "method" else chart_bands(cut)
                bands = [] if bands is None else bands
                ctx["bands"] = band_rows(bands)                          # signal text: legend + अचूक किंमती
                if finder == "method":
                    ctx["bands_finder"] = "method"
            except Exception as exc:                                     # पट्टे अपयशी ⇒ जुनं drawing (majors सह), नोंद
                bands, meta["bands_error"] = None, f"{type(exc).__name__}: {str(exc)[:120]}"
        objs, xmaps = None, None                                         # PA §4 (`chart_objects`, default off ⇒ image as today)
        if (sig.get("ctx_settings") or {}).get("chart_objects") == "on":
            try:
                objs, dropped = chart_objects_of(sig)
                xmaps = _xmaps(cut, setup, higher, tfs)
                meta["objects"] = len(objs)
                if dropped:
                    meta["objects_dropped"] = dropped[:10]
            except Exception as exc:                                     # objects are display only ⇒ the chart without them, noted
                objs, xmaps, meta["objects_error"] = None, None, f"{type(exc).__name__}: {str(exc)[:120]}"
        obj_errors = []
        fig = build_figure(setup, higher, sig, tfs, ctx, line, vols, bands, objs or None, xmaps, errors=obj_errors)
        if obj_errors:                                                   # objects are display only ⇒ the chart without them, noted
            meta["objects_error"] = "; ".join(obj_errors)[:240]
        meta["volume_line"] = _volume_line(setup, sig, vols)
        png = fig.to_image(format="png", width=WIDTH, height=int(fig.layout.height or HEIGHT), scale=1)
        return png, meta
    except Exception as exc:                                             # kaleido/Chrome नाही, डेटा विचित्र — worker ने unavailable नोंदवावं
        meta["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        return None, meta


def trigger_frame(cut, sig, rd, fut=None):
    """DECISIONS 37: the 5M trigger panel's frame — the 5M candles of the 1m cut (closed by the signal) + their FUT 5M volume; None for
    a signal without a 5M trigger (the card as before)."""
    if str(rd.get("trigger_tf") or "").upper() != "5M":
        return None
    t5 = resample(cut, 5).reset_index(drop=True)
    vol = None
    try:
        from decision3 import volume_pane as VP
        src = fut if VP.is_index(sig.get("symbol")) else None
        if src is not None and len(src) and len(t5):
            src = src.assign(timestamp=to_ist_naive(pd.to_datetime(src["timestamp"])))
            vol = VP.bar_volume(t5["start"], t5["end"], src, sig.get("asof") if sig.get("asof") is not None else sig.get("signal_ts"))
    except Exception:                                                    # noqa: BLE001 — display only: the panel without volume
        vol = None
    return {"tf": "5M", "df": t5, "vol": vol}


def engine_figure(cut, setup, higher, tfs, sig, ctx, vols, meta, fut=None):
    """T-5: the engine card's figure + the context marked for the engine audit (ctx["signal_source"] = "engine", ctx["engine"] = the
    engine's reading). The old context (levels, l_line, gap_ctx …) stays in ctx for the record / context lines only. The next area
    comes from the engine's areas; only when the engine row carries no opposite area, from the chart band finder (no look-ahead)."""
    from . import engine_audit as EA
    from . import engine_card as EC
    try:
        fb = chart_bands(cut)
    except Exception:                                                    # noqa: BLE001 — display only
        fb = []
    rd = EA.reading(sig, fallback_areas=fb)
    ctx = dict(ctx or {})
    ctx.update(signal_source="engine", engine=rd)
    meta["ctx"] = ctx
    objs, xmaps = None, None
    if (sig.get("ctx_settings") or {}).get("chart_objects") == "on":
        try:
            objs, dropped = chart_objects_of(sig)
            xmaps = _xmaps(cut, setup, higher, tfs)
            meta["objects"] = len(objs)
            if dropped:
                meta["objects_dropped"] = dropped[:10]
        except Exception as exc:                                         # noqa: BLE001 — display only
            objs, xmaps, meta["objects_error"] = None, None, f"{type(exc).__name__}: {str(exc)[:120]}"
    errors = []
    trig = trigger_frame(cut, sig, rd, fut)
    fig = EC.build_figure(setup, higher, sig, tfs, rd, vols, objs or None, xmaps, errors=errors, trigger=trig)
    if errors:
        meta["objects_error"] = "; ".join(errors)[:240]
    meta["volume_line"] = _volume_line(setup, sig, vols, engine=True)    # DECISIONS 53 (VP3): the engine card's words, no "grade cap"
    meta["card"] = "engine"
    if trig is not None:
        meta["trigger_panel"] = {"tf": "5M", "bars": int(len(trig["df"]))}
    return fig


def _render_engine(cut, setup, higher, tfs, sig, ctx, vols, meta, fut=None):
    fig = engine_figure(cut, setup, higher, tfs, sig, ctx, vols, meta, fut=fut)
    png = fig.to_image(format="png", width=WIDTH, height=int(fig.layout.height or HEIGHT), scale=1)
    return png, meta
