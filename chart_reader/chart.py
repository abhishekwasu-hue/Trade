"""chart_reader/chart.py — Chart Reader चा chart (report / dashboard / नंतर vision): trigger-TF candles, horizontal + sloping areas
(KB टप्पा 3 ची सगळी साधनं: ठोस पट्टे, मोजपट्टी रेषा, trendlines), active area, invalidation आणि targets. फक्त asof पर्यंतचे bars. कधीच raise नाही."""
import pandas as pd


def figure(trig, r, bars=140, title=None):
    import plotly.graph_objects as go
    d = trig.tail(bars).reset_index(drop=True)
    x = list(range(len(d)))
    off = len(trig) - len(d)
    fig = go.Figure(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350", showlegend=False))
    lo, hi = float(d["low"].min()), float(d["high"].max())
    pad = (hi - lo) * 0.15
    act = (r.get("active") or {}).get("area") or {}
    cands = (r.get("areas") or {}).get("candidates", [])
    for z in cands:                                                      # ठोस areas (a–e, j–l) ⇒ पट्टे; मोजपट्टी (g/h/i) ⇒ पातळ रेषा
        if z.get("tool") == "f" or z["high"] < lo - pad or z["low"] > hi + pad or z.get("state") == "DEAD":
            continue
        is_act = z["id"] == act.get("id")
        if z.get("kind") == "ruler":
            fig.add_hline(y=(z["low"] + z["high"]) / 2.0, line=dict(color="#8d6e63", dash="dot", width=1))
            continue
        col = "#ffca28" if is_act else ("#78909c" if z.get("state") == "MAGNET" else "#42a5f5" if z.get("tool") in "abcd" else "#26c6da")
        fig.add_hrect(y0=z["low"], y1=z["high"], fillcolor=col, opacity=0.35 if is_act else 0.12, line_width=0)
        if z.get("tool") in "abcdek" or is_act:
            fig.add_annotation(x=len(d) - 1, y=z["high"], text=f"{z.get('tool')}:{z['id'][-10:]} {str(z.get('state', ''))[:4]}", showarrow=False,
                               xanchor="right", font=dict(size=9, color=col), yshift=6)
    for t in [z for z in cands if z.get("tool") == "f"]:
        try:
            ts = pd.to_datetime(trig["timestamp"])
            pts = [(int((ts <= pd.Timestamp(a)).sum()) - 1, p) for a, p in t["anchors"]]          # anchor bar index (रात्र / सुट्ट्या सह बरोबर)
        except Exception:
            continue
        x0 = pts[0][0] - off
        col = "#ffca28" if t["id"] == act.get("id") else ("#ab47bc" if t.get("valid") else "#6a4f6f")
        fig.add_trace(go.Scatter(x=[x0, len(d) - 1], y=[pts[0][1], t["value"]], mode="lines", showlegend=False,
                                 line=dict(color=col, width=2 if t.get("valid") else 1, dash="dot")))
        fig.add_annotation(x=len(d) - 1, y=t["value"], text=t["id"][:5], showarrow=False, xanchor="left", font=dict(size=9, color=col))
    rk = r.get("risk") or {}
    if rk.get("invalidation"):
        fig.add_hline(y=rk["invalidation"], line=dict(color="#ef5350", dash="dash", width=1))
        fig.add_annotation(x=0, y=rk["invalidation"], text="INV", showarrow=False, xanchor="left", font=dict(size=9, color="#ef5350"))
    for tg in rk.get("targets") or []:
        fig.add_hline(y=tg["price"], line=dict(color="#66bb6a", dash="dash", width=1))
        fig.add_annotation(x=0, y=tg["price"], text=f"T {tg['id'][-8:]}", showarrow=False, xanchor="left", font=dict(size=9, color="#66bb6a"))
    head = title or f"{r.get('profile')} · {r.get('asof')} · grade {r.get('grade')} ({r.get('total')}) · " \
                    f"{'bull put' if r.get('side', 0) > 0 else 'bear call' if r.get('side', 0) < 0 else '—'}"
    fig.update_layout(template="plotly_dark", width=1100, height=640, margin=dict(l=10, r=70, t=50, b=20), xaxis_rangeslider_visible=False,
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", title=dict(text=head, font=dict(size=13)))
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238")
    return fig


def png(trig, r, **kw):
    try:
        return figure(trig, r, **kw).to_image(format="png", scale=1)
    except Exception:
        return None
