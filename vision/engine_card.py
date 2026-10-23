"""vision/engine_card.py — T-5 (DECISIONS 31, PROVISIONAL): the approval chart of an ENGINE signal = the engine's own reading.

Drawn (CLAUDE.md P8: refined base, target and invalidation strong; the context area faint; the rest faded; dead hidden):
  • the visited area (context, faint) — or, for E4 (b), the broken object being retested (dashed band / line, strong);
  • the refined 15M base (strong);  • the trigger candle (yellow box "T");  • the invalidation (dashed yellow "INV");
  • the next area in the trade direction ("NEXT", outlined strong);  • the other engine areas (faded; DEAD hidden);
  • with a 5M trigger (DECISIONS 37 / 52, O-13): the 5M trigger as its OWN panel beside the 15M setup panel (setup | trigger 5M |
    higher), never an inset over the 15M candles; volume panes in the engine card's words (DECISIONS 53, VP3: no "grade cap");
  • the HTF strip (Weekly / Daily / trend used) in the title;  • the futures volume panes and, with `chart_objects = on`, the signal's
    object list (decision3.draw_render via vision.chart._objects — the same drawing as the verification charts).
Not drawn: the L line, PDH / PDL / PDC, ORH / ORL, the opening band, gap bands, session separators (the old level-bot card).
Reuses vision/chart.py (panels, volume panes, object drawing) — display only; never an order, never a reading decision.
"""
import numpy as np
import pandas as pd

from . import chart as CH

ROLE_FILL = {"resistance": ("#ffa726", "rgba(255,167,38,{a})"), "support": ("#4fc3f7", "rgba(79,195,247,{a})")}
FAINT, STRONG, FADED = 0.08, 0.28, 0.04
INV_COLOR = "#ffca28"
NEXT_COLOR = "#66bb6a"


def trigger_index(df, ts):
    """The trigger candle's index on the setup panel: the bar whose start is the engine's trigger_ts; unknown / outside ⇒ the last bar
    (the chart is cut at the trigger bar's close)."""
    n = len(df)
    if ts is not None and n:
        try:
            t = pd.Timestamp(CH.to_ist_naive(ts))
            hit = [k for k in range(n) if pd.Timestamp(df["start"].iloc[k]) == t]
            if hit:
                return hit[-1]
        except (TypeError, ValueError):
            pass
    return n - 1


def htf_strip(rd):
    h = rd.get("htf") or {}
    parts = [f"W {h['weekly']}" if h.get("weekly") else None,
             f"D {h['daily']}" + (f" ({h['daily_phase']})" if h.get("daily_phase") else "") if h.get("daily") else None,
             f"trend used {rd['trend']}" if rd.get("trend") else None]
    return "HTF: " + (" · ".join(p for p in parts if p) or "n/a")


def _rect(fig, lo, hi, c, n, fill, line, layer="below"):
    fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=lo, y1=hi, fillcolor=fill, line=line, layer=layer, row=1, col=c)


def _label(fig, c, n, y, text, color, shift=-7):
    if c == 1:
        fig.add_annotation(x=n - 1, y=y, text=text, showarrow=False, xanchor="right", yshift=shift, font=dict(size=9, color=color),
                           row=1, col=c)


def _edge_note(fig, c, n, lo, hi, band, text, color):
    """A band outside the panel's price range ⇒ an ▲ / ▼ note at the edge (the candles keep their scale)."""
    up = band[0] > hi
    fig.add_annotation(x=n - 1, y=hi if up else lo, text=("▲ " if up else "▼ ") + text, showarrow=False, xanchor="right",
                       yshift=-8 if up else 8, font=dict(size=9, color=color), row=1, col=c)


def object_label(rd):
    """The chart label of the engine object (DECISIONS 41): "BROKEN 1H LINE (retest from below)", "BROKEN 1H AREA (retest from
    below)", "1H RANGE UPPER EDGE tested", "AREA 1H tested"."""
    area = rd.get("area") or {}
    frm = "below" if rd.get("direction", -1) < 0 else "above"
    ob = str(rd.get("object") or "")
    if ob == "broken_line" or rd.get("line"):
        tf = (rd.get("line") or {}).get("tf") or ""
        return f"BROKEN {tf} LINE (retest from {frm})".replace("  ", " ")
    if ob == "broken_area":
        return f"BROKEN {area.get('tf') or ''} AREA (retest from {frm})".replace("  ", " ")
    re_ = rd.get("range_edge")
    st = str(area.get("state") or "").lower()
    if re_:
        return f"{re_.get('tf') or ''} RANGE {str(re_.get('edge') or '').upper()} EDGE {st}".strip().replace("  ", " ")
    return f"AREA {area.get('tf') or ''} {st}".strip().replace("  ", " ")


TRIGGER_COL = 2                                                          # DECISIONS 52 (O-13): the 5M panel = its own column


def trigger_title(trigger, rd):
    """The 5M panel's title: "trigger 5M · T · context 15M 09:45"."""
    tr = rd.get("trigger") if isinstance(rd.get("trigger"), dict) else {}
    ctx = tr.get("context_bar_ts")
    return f"trigger {(trigger or {}).get('tf') or ''} · T" + (f" · context 15M {str(ctx)[11:16]}" if ctx else "")


def trigger_panel(fig, trigger, rd, col=TRIGGER_COL):
    """DECISIONS 37 / 52 (O-13) — the 5M TRIGGER panel, its OWN panel beside the 15M setup panel (column `col` of the card; never drawn
    over the 15M candles): trigger = {"tf": "5M", "df": the trigger-TF candles closed by the signal (with "start"), "vol": their FUT
    volume (optional)} ⇒ the visit's 5M candles up to the trigger candle (boxed, "T"), the refined base (strong), the context area
    (faint), the invalidation (dashed), and the model's own 5M facts: the E3 CHoCH level, the E4 (a) sweep extreme + the failed push, the
    E4 (b) line's value per 5M candle; the FUT 5M volume under it (missing ⇒ "FUT volume missing — E2 cannot be read", DECISIONS 53).
    P8: display only, nothing else drawn; a failure here leaves the card without the panel (the caller notes it)."""
    import plotly.graph_objects as go
    from decision3 import volume_pane as VP
    df = trigger.get("df")
    if df is None or not len(df):
        return
    tr = rd.get("trigger") if isinstance(rd.get("trigger"), dict) else {}
    k = trigger_index(df, rd.get("trigger_ts"))
    lo0 = max(0, k - 23)
    vs = tr.get("visit_start5")
    if vs is not None:                                                    # from the visit's first 5M candle (at most 36 candles)
        try:
            t0 = pd.Timestamp(CH.to_ist_naive(vs))
            hit = [i for i in range(k + 1) if pd.Timestamp(df["start"].iloc[i]) >= t0]
            if hit:
                lo0 = max(min(hit[0], k), k - 35)
        except (TypeError, ValueError):
            pass
    sub = df.iloc[lo0:k + 1].reset_index(drop=True)
    n = len(sub)
    fig.add_trace(go.Candlestick(x=list(range(n)), open=sub["open"], high=sub["high"], low=sub["low"], close=sub["close"],
                                 showlegend=False, increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=col)
    plo, phi = float(sub["low"].min()), float(sub["high"].max())
    area, rb, inv = rd.get("area"), rd.get("refined"), rd.get("invalidation")
    f = tr.get("facts") if isinstance(tr.get("facts"), dict) else {}
    for v in [inv] + list(rb or []) + [f.get("choch_level"), f.get("sweep_extreme")]:
        if v is not None and np.isfinite(float(v)):
            plo, phi = min(plo, float(v)), max(phi, float(v))
    pad = 0.05 * (phi - plo or 1.0)
    step = max(1, n // 3)
    fig.update_xaxes(tickvals=list(range(0, n, step)), ticktext=[pd.Timestamp(sub["start"].iloc[i]).strftime("%H:%M") for i in range(0, n, step)],
                     rangeslider_visible=False, showgrid=False, color="#b0bec5", range=[-0.6, n - 0.4], row=1, col=col)
    fig.update_yaxes(range=[plo - pad, phi + pad], row=1, col=col)
    role = "support" if rd.get("direction", -1) > 0 else "resistance"
    colr, fill = ROLE_FILL[role]

    def band(lo, hi, a, width):
        fig.add_shape(type="rect", x0=-0.5, x1=n - 0.5, y0=max(lo, plo - pad), y1=min(hi, phi + pad), fillcolor=fill.format(a=a),
                      line=dict(color=colr, width=width), layer="below", row=1, col=col)

    def hline(y, color, dash, text):
        fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=y, y1=y, line=dict(color=color, width=1, dash=dash), row=1, col=col)
        fig.add_annotation(x=0, y=y, text=text, showarrow=False, xanchor="left", yshift=6, font=dict(size=8, color=color), row=1, col=col)
    if area and area.get("lo") is not None and area["lo"] != area["hi"] and area["hi"] >= plo - pad and area["lo"] <= phi + pad:
        band(float(area["lo"]), float(area["hi"]), FAINT, 0.5)            # the context area (faint)
    if rb:
        band(float(rb[0]), float(rb[1]), STRONG, 1.2)                     # the refined 15M base (strong)
    if inv is not None:
        hline(float(inv), INV_COLOR, "dash", "INV")
    if f.get("choch_level") is not None:                                  # E3: the 5M CHoCH level
        hline(float(f["choch_level"]), "#ce93d8", "dot", "CHoCH 5M")
    if f.get("sweep_extreme") is not None:                                # E4 (a): the sweep extreme + the failed push
        hline(float(f["sweep_extreme"]), "#ff8a65", "dot", "SWEEP")
        if f.get("push_ts") is not None and f.get("push_price") is not None:
            px = [i for i in range(n) if str(pd.Timestamp(sub["start"].iloc[i])) == str(pd.Timestamp(f["push_ts"]))]
            if px:
                fig.add_annotation(x=px[0], y=float(f["push_price"]), text="push ✗", showarrow=False, yshift=8,
                                   font=dict(size=8, color="#ff8a65"), row=1, col=col)
    lv = tr.get("line_values") if isinstance(tr.get("line_values"), list) else None
    if lv:                                                                # E4 (b) on a line: its value at each 5M candle
        at = {str(pd.Timestamp(a)): float(b) for a, b in lv}
        xs = [i for i in range(n) if str(pd.Timestamp(sub["start"].iloc[i])) in at]
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=[at[str(pd.Timestamp(sub["start"].iloc[i]))] for i in xs], mode="lines", showlegend=False,
                                     line=dict(color=colr, width=1.5, dash="dash")), row=1, col=col)
    j = n - 1
    fig.add_shape(type="rect", x0=j - 0.45, x1=j + 0.45, y0=float(sub["low"].iloc[j]), y1=float(sub["high"].iloc[j]),
                  line=dict(color="#ffd54f", width=1.5), fillcolor="rgba(255,213,79,0.08)", row=1, col=col)
    up = rd.get("direction", -1) > 0
    fig.add_annotation(x=j, y=float(sub["low"].iloc[j]) if up else float(sub["high"].iloc[j]), text="T ▲" if up else "T ▼",
                       showarrow=False, yshift=-14 if up else 14, font=dict(size=12, color="#ffd54f"), row=1, col=col)
    vol = trigger.get("vol")
    v = np.asarray(vol, float)[lo0:k + 1] if vol is not None and len(vol) == len(df) else np.full(n, np.nan)
    fig.update_xaxes(showticklabels=False, showgrid=False, range=[-0.6, n - 0.4], row=2, col=col)
    fig.update_yaxes(showticklabels=False, showgrid=False, row=2, col=col)
    if np.isfinite(v).any():
        fig.add_trace(go.Bar(x=list(range(n)), y=[0 if not np.isfinite(x) else x for x in v], showlegend=False, marker_color="#78909c",
                             marker_line_width=0), row=2, col=col)
        fig.add_annotation(x=-0.5, y=float(np.nanmax(v)) * 1.45, text=f"vol {VP.source_label(trigger.get('symbol'))} 5M",
                           showarrow=False, xanchor="left", yanchor="top", font=dict(size=8, color=VP.PLOTLY["ink"]), row=2, col=col)
        fig.update_yaxes(range=[0, float(np.nanmax(v)) * 1.45], row=2, col=col)
    else:                                                                 # DECISIONS 53 (VP3): never "grade cap"
        fig.update_yaxes(range=[0, 1], row=2, col=col)
        fig.add_annotation(x=(n - 1) / 2, y=0.5, text=VP.ENGINE_NA_LINE, showarrow=False, font=dict(size=9, color=VP.PLOTLY["na"]),
                           row=2, col=col)


def build_figure(setup, higher, sig, tfs, rd, vols=None, objects=None, xmaps=None, errors=None, trigger=None):
    """The engine card (plotly figure). rd = vision.engine_audit.reading(sig). Same size / panels / volume panes as the level-bot card.
    trigger = an optional trigger-TF frame (see `trigger_panel`; the 5M trigger build passes it) ⇒ three panels: setup 15M | trigger 5M |
    higher (DECISIONS 52, O-13: the 5M panel beside the 15M one, never over it); None ⇒ two panels, the trigger candle boxed on the setup
    panel (as before)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from decision3 import volume_pane as VP
    s_tf, h_tf = tfs
    three = trigger is not None and trigger.get("df") is not None and len(trigger["df"]) > 0
    if three:                                                              # DECISIONS 52 (O-13): 15M | 5M trigger | higher — the 5M
        fig = make_subplots(rows=2, cols=3, column_widths=[0.42, 0.28, 0.30], row_heights=[0.78, 0.22], horizontal_spacing=0.055,
                            vertical_spacing=0.07, subplot_titles=(f"setup {CH._tf_label(s_tf)}", trigger_title(trigger, rd),
                                                                   f"higher {CH._tf_label(h_tf)}", "", "", ""))
        cols = {1: 1, 2: 3}                                                # panel is its own panel beside the 15M one, never over it
    else:                                                                  # no 5M trigger ⇒ the card as before
        fig = make_subplots(rows=2, cols=2, column_widths=[0.6, 0.4], row_heights=[0.78, 0.22], horizontal_spacing=0.06,
                            vertical_spacing=0.07, subplot_titles=(f"setup {CH._tf_label(s_tf)}", f"higher {CH._tf_label(h_tf)}", "", ""))
        cols = {1: 1, 2: 2}
    d = rd["direction"]
    area, rb, nx, inv = rd.get("area"), rd.get("refined"), rd.get("next_area"), rd.get("invalidation")
    broken = str(rd.get("object") or "").startswith("broken")
    role = "support" if d > 0 else "resistance"
    colr, fill = ROLE_FILL[role]
    for c, df in ((1, setup), (2, higher)):
        if df is None or len(df) == 0:
            continue
        pc = cols[c]                                                       # the panel's column on the card
        x = np.arange(len(df))
        n = len(df)
        fig.add_trace(go.Candlestick(x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"], showlegend=False,
                                     increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=pc)
        lo, hi = float(df["low"].min()), float(df["high"].max())
        for v in [inv] + ([area["lo"], area["hi"]] if area else []) + (list(rb) if rb else []):
            if v is not None and np.isfinite(v):
                lo, hi = min(lo, float(v)), max(hi, float(v))
        pad = 0.04 * (hi - lo or 1.0)
        lo, hi = lo - pad, hi + pad
        fig.update_yaxes(range=[lo, hi], row=1, col=pc)
        step = max(1, n // 6)
        fmt = "%d %b" if h_tf == "D" and c == 2 else "%d %b %H:%M"
        fig.update_xaxes(tickvals=list(range(0, n, step)), ticktext=[pd.Timestamp(df["start"].iloc[k]).strftime(fmt) for k in range(0, n, step)],
                         rangeslider_visible=False, showgrid=False, color="#b0bec5", range=[-0.5, n - 0.5], row=1, col=pc)
        vol = (vols or (None, None))[c - 1]
        vst = VP.study(df, vol=np.full(n, np.nan) if vol is None else vol, info=sig, symbol=sig.get("symbol"), d=sig.get("direction"),
                       area=CH._area_of(sig), engine_numbers=c == 1, words=CH.volume_words(sig))
        if c == 2 and (vst["arm"] is None or vst["arm"] >= vst["commit"]):
            vst = VP.plain(vst)
        vst = VP.engine_words(vst)                                         # DECISIONS 53 (VP3): no "grade cap" on the engine card
        VP.add_plotly(fig, vst, row=2, col=pc, title=f"vol {VP.source_label(sig.get('symbol'))}")
        for o in rd.get("others") or []:                                  # other engine areas: faded; DEAD hidden
            if o.get("lo") is None or o.get("hi") is None or str(o.get("state") or "").upper() == "DEAD":
                continue
            if nx and (o["lo"], o["hi"]) == (nx["lo"], nx["hi"]):
                continue
            if o["hi"] < lo or o["lo"] > hi:
                continue
            oc, of = ROLE_FILL.get(o.get("role"), ROLE_FILL["support"])
            _rect(fig, max(lo, o["lo"]), min(hi, o["hi"]), pc, n, of.format(a=FADED), dict(width=0))
        if area:                                                           # the visited area (context) / the retested broken object
            if area["lo"] == area["hi"]:
                fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=area["lo"], y1=area["lo"], row=1, col=pc,
                              line=dict(color=colr, width=2, dash="dash" if broken else None))
            else:
                _rect(fig, area["lo"], area["hi"], pc, n, fill.format(a=STRONG if broken and not rb else FAINT),
                      dict(color=colr, width=1.5 if broken else 0.5, dash="dash" if broken else None))
            _label(fig, pc, n, area["hi"], object_label(rd), colr)
        if rb:                                                             # the refined 15M base (strong)
            _rect(fig, rb[0], rb[1], pc, n, fill.format(a=STRONG), dict(color=colr, width=1.5), layer="below")
            _label(fig, pc, n, rb[0], "BASE 15M", colr, shift=7)
        if nx:                                                             # the next area in the trade direction (strong outline)
            txt = f"NEXT {'supply' if nx['role'] == 'resistance' else 'demand'} {nx['lo']:,.0f}-{nx['hi']:,.0f}"
            if nx["hi"] < lo or nx["lo"] > hi:
                if c == 1:
                    _edge_note(fig, pc, n, lo, hi, (nx["lo"], nx["hi"]), txt, NEXT_COLOR)
            else:
                _rect(fig, max(lo, nx["lo"]), min(hi, nx["hi"]), pc, n, "rgba(102,187,106,0.10)", dict(color=NEXT_COLOR, width=1.5))
                _label(fig, pc, n, min(hi, nx["hi"]), txt, NEXT_COLOR)
        if inv is not None:                                                # the invalidation (strong)
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=inv, y1=inv, line=dict(color=INV_COLOR, width=1.5, dash="dash"), row=1, col=pc)
            if c == 1:
                fig.add_annotation(x=0, y=inv, text=f"INV {inv:,.0f}", showarrow=False, xanchor="left", yshift=-8 if d > 0 else 8,
                                   font=dict(size=9, color=INV_COLOR), row=1, col=pc)
        if objects:
            CH._objects(fig, objects, df, lo, hi, pc, (xmaps or (None, None))[c - 1], sig=sig, inv=inv, errors=errors)
        if c == 1:                                                         # the trigger candle on the setup panel; with a 5M trigger
            k = trigger_index(df, rd.get("trigger_ts") if trigger is None else   # panel: the 15M bar that contains the 5M trigger
                              (rd.get("trigger") or {}).get("bar15_ts") or rd.get("trigger_ts"))
            bar = df.iloc[k]
            fig.add_shape(type="rect", x0=k - 0.45, x1=k + 0.45, y0=float(bar["low"]), y1=float(bar["high"]),
                          line=dict(color="#ffd54f", width=1.5), fillcolor="rgba(255,213,79,0.08)", row=1, col=pc)
            up = d > 0
            fig.add_annotation(x=k, y=float(bar["low"]) if up else float(bar["high"]), text="T ▲" if up else "T ▼", showarrow=False,
                               yshift=-14 if up else 14, font=dict(size=12, color="#ffd54f"), row=1, col=pc)
    if three:
        try:
            trigger_panel(fig, {**trigger, "symbol": sig.get("symbol")}, rd, col=TRIGGER_COL)
        except Exception as exc:                                           # noqa: BLE001 — display only: the card without the panel
            if errors is not None:
                errors.append(f"trigger panel: {type(exc).__name__}: {str(exc)[:80]}")
    model = f"{rd['model']} {rd.get('name') or ''}".strip() if rd.get("model") else "engine setup"
    import engine_signal as ES                                             # addition D: the engine's name, as a small label
    title = (f"{sig.get('symbol', '')} · {model} · {rd['side']} · {object_label(rd).lower()}"
             f"<br><sup>{htf_strip(rd)} · {ES.ENGINE_LABEL}</sup>")
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", color="#eceff1")
    fig.update_layout(template="plotly_dark", width=CH.WIDTH, height=CH.HEIGHT, margin=dict(l=10, r=60, t=60, b=30),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=14)), showlegend=False)
    return fig
