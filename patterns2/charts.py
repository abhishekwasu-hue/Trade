"""patterns2/charts.py — 🧭 PATTERN CHECK charts (थर 3 §7): 15M (D1 pattern) आणि 1H (D2 pattern).

I ची रेघ; preferred चे labels ठळक, alternate चे फिके (वेगळा रंग); pattern च्या साध्या रेघा फक्त pattern च्या pivots मधून (zigzag channel,
flat चा A–B पट्टा, triangle च्या A–C / B–D, wedge च्या 1–3 / 2–4; थर 5 च्या trendlines नाहीत); D0 pivots लहान ठिपके; कोपऱ्यात box.
"""
import io

import numpy as np
import pandas as pd

from backtest_review import charts as BC
from pivots import charts as PC
from vision_led import charts as VC

from . import fold as PF

PREF, ALT, ICOL = "#ffd54f", "rgba(128,222,234,0.55)", "#90a4ae"


def _xy(frame, pts):
    xs, ys, ls = [], [], []
    t0 = pd.to_datetime(frame["timestamp"]).min()
    for p in pts:
        if pd.Timestamp(p["ts"]) < t0:
            continue
        x = PC._x_of(frame, p["ts"])
        if x is None:
            continue
        xs.append(x)
        ys.append(p["price"])
        ls.append(p["label"])
    return xs, ys, ls


def _line(fig, frame, p1, p2, color, n):
    """दोन pattern-pivots मधून रेघ, chart च्या उजव्या कडेपर्यंत वाढवलेली."""
    import plotly.graph_objects as go
    xs, ys, _ = _xy(frame, [p1, p2])
    if len(xs) < 2 or xs[1] == xs[0]:
        return
    slope = (ys[1] - ys[0]) / (xs[1] - xs[0])
    x2 = n - 1
    fig.add_trace(go.Scatter(x=[xs[0], x2], y=[ys[0], ys[0] + slope * (x2 - xs[0])], mode="lines",
                             line=dict(color=color, width=1.5, dash="dash"), showlegend=False, hoverinfo="skip"))


def pattern_lines(fig, frame, hj, n):
    pts = hj["points"]
    fam = hj["family"]
    if fam == "zigzag" and len(pts) >= 3:
        _line(fig, frame, pts[0], pts[2], "#ffb74d", n)                        # A सुरुवात – B टोक
        if len(pts) >= 4:
            p1, p0, p2 = pts[1], pts[0], pts[2]                               # समांतर रेघ A च्या टोकातून
            x = _xy(frame, [p0, p2, p1])
            if len(x[0]) == 3 and x[0][1] != x[0][0]:
                slope = (x[1][1] - x[1][0]) / (x[0][1] - x[0][0])
                import plotly.graph_objects as go
                fig.add_trace(go.Scatter(x=[x[0][2], n - 1], y=[x[1][2], x[1][2] + slope * (n - 1 - x[0][2])], mode="lines",
                                         line=dict(color="#ffb74d", width=1.5, dash="dash"), showlegend=False, hoverinfo="skip"))
    elif fam == "flat" and len(pts) >= 3:
        for p in (pts[1], pts[2]):
            xs, ys, _ = _xy(frame, [p])
            if xs:
                fig.add_shape(type="line", x0=xs[0], x1=n - 1, y0=ys[0], y1=ys[0], line=dict(color="#ffb74d", width=1.5, dash="dash"))
    elif fam in ("triangle", "wedge") and len(pts) >= 4:
        _line(fig, frame, pts[1], pts[3], "#ffb74d", n)
        if len(pts) >= 5:
            _line(fig, frame, pts[2], pts[4], "#ffb74d", n)


def figure(frame, tf, rec, minor, title, box=None):
    import plotly.graph_objects as go
    d = frame.reset_index(drop=True)
    n = len(d)
    fig = BC._base(d, title)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    if minor:
        xs, ys, _ = _xy(d, [{"ts": p.ts, "price": p.price, "label": ""} for p in minor])
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", marker=dict(size=5, color="#b0bec5"), showlegend=False, hoverinfo="skip"))
    I = rec.get("I_full")
    if I:
        xs, ys, _ = _xy(d, [{"ts": I["origin_ts"], "price": I["origin"], "label": ""}, {"ts": I["end_ts"], "price": I["end"], "label": ""}])
        if len(xs) == 2:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=ICOL, width=3), showlegend=False, hoverinfo="skip"))
        elif len(xs) == 1:
            fig.add_annotation(x=xs[0], y=ys[0], text="I_end", showarrow=True, arrowcolor=ICOL, font=dict(size=10, color=ICOL))
    for hj, col, size, width in ((rec.get("alt"), ALT, 10, 1.5), (rec.get("pref"), PREF, 14, 2.5)):
        if not hj:
            continue
        xs, ys, ls = _xy(d, hj["points"])
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers+text", text=ls, textposition="top center",
                                     line=dict(color=col, width=width), marker=dict(size=6, color=col),
                                     textfont=dict(size=size, color=col), showlegend=False, hoverinfo="skip"))
        if hj is rec.get("pref"):
            pattern_lines(fig, d, hj, n)
    fig.add_annotation(x=0.5, y=0.55, xref="paper", yref="paper", text=tf, showarrow=False, font=dict(size=140, color="rgba(255,255,255,0.07)"))
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=box, font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    BC._finish(fig, d, lo, hi, fmt="%d %b %H:%M")
    return fig


def _name(hj):
    if not hj:
        return "—"
    nm = PF.FAMILY_MR[hj["family"]] + (f" {hj['kind']}" if hj["kind"] else "") + (f" ({hj['sub']})" if hj.get("sub") else "")
    return nm + (" · barrier" if hj.get("barrier") else "")


def ratios(hj):
    """B/A, C/A आणि वेळ गुणोत्तरं (preferred च्या points वरून)."""
    if not hj or len(hj["points"]) < 3:
        return ""
    p = [x["price"] for x in hj["points"]]
    t = [pd.Timestamp(x["ts"]) for x in hj["points"]]
    A = abs(p[1] - p[0])
    out = [f"B/A {abs(p[2] - p[1]) / A:.2f}"] if A else []
    if len(p) >= 4 and A:
        out.append(f"C/A {abs(p[3] - p[2]) / A:.2f}")
    ta = (t[1] - t[0]).total_seconds()
    if ta > 0:
        out.append(f"वेळ B/A {(t[2] - t[1]).total_seconds() / ta:.1f}")
    return " · ".join(out)


def box_text(j1, j2, pos):
    def one(j, nm):
        p = j.get("pref")
        if not p:
            return f"<b>{nm}</b>: {j['agg_mr']}"
        comp = ", ".join(f"{a} {m:.2f}" for a, m in p["completion"][:3]) or "—"
        alt = j.get("alt")
        return (f"<b>{nm}</b>: {_name(p)} · {PF.STATE_MR.get(p['state'], p['state'])} · गुण {p['score']:.2f}"
                f"{' · coarse' if p['coarse'] else ''}{' · जुन्या I_end पासून' if p['from_old_I_end'] else ''}"
                f"<br>&nbsp;&nbsp;पूर्णता: {comp} · {ratios(p)}"
                f"<br>&nbsp;&nbsp;पर्याय: {_name(alt)}{(' · गुण ' + format(alt['score'], '.2f')) if alt else ''}")
    rows = [one(j1, "15M (D1)"), one(j2, "1H (D2)")]
    if pos and pos.get("inside"):
        rows.append(f"D1 चा K हा D2 च्या K च्या आत · D2 मध्ये जागा: {pos.get('where') or '—'}")
    return "<br>".join(rows)


def charts(res, f1, f2, t, j1, j2, pos):
    m15 = res["m15"]
    m = m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    title = "🧭 PATTERN CHECK · NIFTY {tf} · {d:%d %b %Y %H:%M} · {deg}"
    from pivots import engine as PE
    d0 = PE.known(res, 0, asof)
    d1 = PE.known(res, 1, asof)
    out = {"15M": PC.png(figure(PC.window(m, "15M", asof), "15M", j1, d0, title.format(tf="15M", d=asof, deg="D1 pattern"),
                                box=box_text(j1, j2, pos))),
           "1H": PC.png(figure(PC.window(PC.agg_1h(m), "1H", asof), "1H", j2, d1, title.format(tf="1H", d=asof, deg="D2 pattern")))}
    return out


def caption(n, total, asof, j1, j2):
    """≤ 8 ओळी, ≤ 1024 (UTF-16), code keys नाहीत."""
    p1, p2 = j1.get("pref"), j2.get("pref")
    alt = j1.get("alt")
    lines = [f"🧭 PATTERN CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y} · {pd.Timestamp(asof):%H:%M}",
             f"15M: {_name(p1)} · {PF.STATE_MR.get(p1['state'], p1['state']) if p1 else j1['agg_mr']} · " + (f"गुण {p1['score']:.2f}" if p1 else "—"),
             f"पर्याय: {_name(alt)} · " + (f"गुण {alt['score']:.2f}" if alt else "—"),
             ratios(p1) or "—",
             f"1H: {_name(p2)} · {PF.STATE_MR.get(p2['state'], p2['state']) if p2 else j2['agg_mr']}",
             "Reply: ✔ बरोबर · ✘ कोणता pattern / label चुकला"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)


def pair(pngs):
    from PIL import Image
    ims = [Image.open(io.BytesIO(pngs[k])).convert("RGB") for k in ("15M", "1H")]
    w, h = ims[0].size
    page = Image.new("RGB", (2 * w, h), "#0e1117")
    for i, im in enumerate(ims):
        page.paste(im.resize((w, h)), (i * w, 0))
    buf = io.BytesIO()
    page.save(buf, "PNG")
    return buf.getvalue()
