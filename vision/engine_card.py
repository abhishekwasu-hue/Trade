"""vision/engine_card.py — T-5 (DECISIONS 31, PROVISIONAL): the approval chart of an ENGINE signal = the engine's own reading.

Drawn (CLAUDE.md P8: refined base, target and invalidation strong; the context area faint; the rest faded; dead hidden):
  • the visited area (context, faint) — or, for E4 (b), the broken object being retested (dashed band / line, strong);
  • the refined 15M base (strong);  • the trigger candle (yellow box "T");  • the invalidation (dashed yellow "INV");
  • the next area in the trade direction ("NEXT", outlined strong);  • the other engine areas (faded; DEAD hidden);
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


def build_figure(setup, higher, sig, tfs, rd, vols=None, objects=None, xmaps=None, errors=None):
    """The engine card (plotly figure). rd = vision.engine_audit.reading(sig). Same size / panels / volume panes as the level-bot card."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from decision3 import volume_pane as VP
    s_tf, h_tf = tfs
    fig = make_subplots(rows=2, cols=2, column_widths=[0.6, 0.4], row_heights=[0.78, 0.22], horizontal_spacing=0.06,
                        vertical_spacing=0.07, subplot_titles=(f"setup {CH._tf_label(s_tf)}", f"higher {CH._tf_label(h_tf)}", "", ""))
    d = rd["direction"]
    area, rb, nx, inv = rd.get("area"), rd.get("refined"), rd.get("next_area"), rd.get("invalidation")
    broken = str(rd.get("object") or "").startswith("broken")
    role = "support" if d > 0 else "resistance"
    colr, fill = ROLE_FILL[role]
    for c, df in ((1, setup), (2, higher)):
        if df is None or len(df) == 0:
            continue
        x = np.arange(len(df))
        n = len(df)
        fig.add_trace(go.Candlestick(x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"], showlegend=False,
                                     increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=c)
        lo, hi = float(df["low"].min()), float(df["high"].max())
        for v in [inv] + ([area["lo"], area["hi"]] if area else []) + (list(rb) if rb else []):
            if v is not None and np.isfinite(v):
                lo, hi = min(lo, float(v)), max(hi, float(v))
        pad = 0.04 * (hi - lo or 1.0)
        lo, hi = lo - pad, hi + pad
        fig.update_yaxes(range=[lo, hi], row=1, col=c)
        step = max(1, n // 6)
        fmt = "%d %b" if h_tf == "D" and c == 2 else "%d %b %H:%M"
        fig.update_xaxes(tickvals=list(range(0, n, step)), ticktext=[pd.Timestamp(df["start"].iloc[k]).strftime(fmt) for k in range(0, n, step)],
                         rangeslider_visible=False, showgrid=False, color="#b0bec5", range=[-0.5, n - 0.5], row=1, col=c)
        vol = (vols or (None, None))[c - 1]
        vst = VP.study(df, vol=np.full(n, np.nan) if vol is None else vol, info=sig, symbol=sig.get("symbol"), d=sig.get("direction"),
                       area=CH._area_of(sig), engine_numbers=c == 1, words=CH.volume_words(sig))
        if c == 2 and (vst["arm"] is None or vst["arm"] >= vst["commit"]):
            vst = VP.plain(vst)
        VP.add_plotly(fig, vst, row=2, col=c, title=f"vol {VP.source_label(sig.get('symbol'))}")
        for o in rd.get("others") or []:                                  # other engine areas: faded; DEAD hidden
            if o.get("lo") is None or o.get("hi") is None or str(o.get("state") or "").upper() == "DEAD":
                continue
            if nx and (o["lo"], o["hi"]) == (nx["lo"], nx["hi"]):
                continue
            if o["hi"] < lo or o["lo"] > hi:
                continue
            oc, of = ROLE_FILL.get(o.get("role"), ROLE_FILL["support"])
            _rect(fig, max(lo, o["lo"]), min(hi, o["hi"]), c, n, of.format(a=FADED), dict(width=0))
        if area:                                                           # the visited area (context) / the retested broken object
            if area["lo"] == area["hi"]:
                fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=area["lo"], y1=area["lo"], row=1, col=c,
                              line=dict(color=colr, width=2, dash="dash" if broken else None))
            else:
                _rect(fig, area["lo"], area["hi"], c, n, fill.format(a=STRONG if broken and not rb else FAINT),
                      dict(color=colr, width=1.5 if broken else 0.5, dash="dash" if broken else None))
            _label(fig, c, n, area["hi"], ("BROKEN " + ("LINE" if area["lo"] == area["hi"] else "AREA") + " (retest)" if broken else
                                           f"AREA {area.get('tf') or ''} {str(area.get('state') or '').lower()}").strip(), colr)
        if rb:                                                             # the refined 15M base (strong)
            _rect(fig, rb[0], rb[1], c, n, fill.format(a=STRONG), dict(color=colr, width=1.5), layer="below")
            _label(fig, c, n, rb[0], "BASE 15M", colr, shift=7)
        if nx:                                                             # the next area in the trade direction (strong outline)
            txt = f"NEXT {'supply' if nx['role'] == 'resistance' else 'demand'} {nx['lo']:,.0f}-{nx['hi']:,.0f}"
            if nx["hi"] < lo or nx["lo"] > hi:
                if c == 1:
                    _edge_note(fig, c, n, lo, hi, (nx["lo"], nx["hi"]), txt, NEXT_COLOR)
            else:
                _rect(fig, max(lo, nx["lo"]), min(hi, nx["hi"]), c, n, "rgba(102,187,106,0.10)", dict(color=NEXT_COLOR, width=1.5))
                _label(fig, c, n, min(hi, nx["hi"]), txt, NEXT_COLOR)
        if inv is not None:                                                # the invalidation (strong)
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=inv, y1=inv, line=dict(color=INV_COLOR, width=1.5, dash="dash"), row=1, col=c)
            if c == 1:
                fig.add_annotation(x=0, y=inv, text=f"INV {inv:,.0f}", showarrow=False, xanchor="left", yshift=-8 if d > 0 else 8,
                                   font=dict(size=9, color=INV_COLOR), row=1, col=c)
        if objects:
            CH._objects(fig, objects, df, lo, hi, c, (xmaps or (None, None))[c - 1], sig=sig, inv=inv, errors=errors)
        if c == 1:                                                         # the trigger candle
            k = trigger_index(df, rd.get("trigger_ts"))
            bar = df.iloc[k]
            fig.add_shape(type="rect", x0=k - 0.45, x1=k + 0.45, y0=float(bar["low"]), y1=float(bar["high"]),
                          line=dict(color="#ffd54f", width=1.5), fillcolor="rgba(255,213,79,0.08)", row=1, col=c)
            up = d > 0
            fig.add_annotation(x=k, y=float(bar["low"]) if up else float(bar["high"]), text="T ▲" if up else "T ▼", showarrow=False,
                               yshift=-14 if up else 14, font=dict(size=12, color="#ffd54f"), row=1, col=c)
    model = f"{rd['model']} {rd.get('name') or ''}".strip() if rd.get("model") else "engine setup"
    title = (f"{sig.get('symbol', '')} · {sig.get('bot_label') or sig.get('bot', '')} · {model} · {rd['side']} · engine reading"
             f"<br><sup>{htf_strip(rd)}</sup>")
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", color="#eceff1")
    fig.update_layout(template="plotly_dark", width=CH.WIDTH, height=CH.HEIGHT, margin=dict(l=10, r=60, t=60, b=30),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=14)), showlegend=False)
    return fig
