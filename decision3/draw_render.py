"""decision3/draw_render.py — draws the ONE object list (decision3/draw_objects.py) on a chart. Display only.

One geometry, two backends: `geometry()` turns the objects into primitives (segment / band / marker / text) in the target chart's own
x (its bar index) and price, from the objects' TIME and PRICE; `draw_mpl` (decision3 verification charts: charts.py, setup_chart.py)
and `draw_plotly` (the Telegram / Vision chart: vision/chart.py) draw exactly those primitives — so the same objects land at the same
bars / prices with the same labels on every chart. Colours are one palette (mid tones readable on white and on the dark Vision chart).

x mapping: `XMap(starts, j0)` — `starts` = the bar START times of the chart's timeframe (as long a history as the caller has, oldest
first), `j0` = the index of the first bar shown (x = index − j0). A time inside a bar maps to that bar plus the fraction of the bar
(lines keep their slope); before the history ⇒ clipped at the window's left edge. A straight line is drawn straight in the chart's
bar index between its two end points (a 15M line on a 1H chart: the same two anchors).
"""
import numpy as np
import pandas as pd

# style_key ⇒ look; the longest matching prefix wins ("area.supply.armed" ⇒ "area.supply.armed", else "area.supply", else "area").
STYLE = {
    "swing": dict(color="#868e96", size=6.5),
    "swing.D1": dict(color="#868e96", size=6.0),
    "swing.D2": dict(color="#1c7ed6", size=8.0, weight="bold"),
    "swing.D3": dict(color="#5f3dc4", size=8.5, weight="bold"),
    "area": dict(color="#868e96", alpha=0.12),
    "area.supply": dict(color="#e03131", alpha=0.12),
    "area.demand": dict(color="#2f9e44", alpha=0.12),
    "area.supply.armed": dict(color="#e03131", alpha=0.30),
    "area.demand.armed": dict(color="#2f9e44", alpha=0.30),
    "area.supply.broken": dict(color="#868e96", alpha=0.0, ls="--"),
    "area.demand.broken": dict(color="#868e96", alpha=0.0, ls="--"),
    "line": dict(color="#7048e8", lw=1.3, ls="-."),
    "channel": dict(color="#0c8599", lw=1.3, ls="-"),
    "level": dict(color="#495057", lw=1.0, ls=":"),
    "level.protected": dict(color="#7048e8", lw=1.2, ls=":"),
    "fvg": dict(color="#f08c00", alpha=0.14),
    "fib": dict(color="#ae3ec9", lw=0.9, ls="--"),
    "pattern": dict(color="#d6336c", lw=1.2, ls="-"),
    "liquidity": dict(color="#1971c2", lw=1.0, ls=":"),
    "liquidity.buy": dict(color="#1971c2", lw=1.0, ls=":"),
    "liquidity.sell": dict(color="#c2255c", lw=1.0, ls=":"),
    "sweep": dict(color="#d9480f", size=8),
    "divergence": dict(color="#f76707", lw=1.6, ls="-"),
    "divergence.hidden": dict(color="#f59f00", lw=1.4, ls="--"),
    "entry": dict(color="#1864ab", size=10),
}
BASE = dict(color="#495057", lw=1.0, ls="-", alpha=0.15, size=7, weight="normal")
PLOTLY_DASH = {"-": None, "--": "dash", ":": "dot", "-.": "dashdot"}


def style(key):
    parts = str(key).split(".")
    for k in range(len(parts), 0, -1):
        s = STYLE.get(".".join(parts[:k]))
        if s is not None:
            return {**BASE, **s}
    return dict(BASE)


class XMap:
    """Time ⇒ the chart's x (bar index − j0). starts = bar start times (oldest first) of the chart's own timeframe."""

    def __init__(self, starts, j0=0, n=None):
        self.s = pd.to_datetime(pd.Series(starts)).to_numpy("datetime64[ns]")
        self.j0 = int(j0)
        self.n = int(n) if n is not None else len(self.s) - self.j0
        d = np.diff(self.s).astype("timedelta64[s]").astype(float)
        same = d[d > 0]
        self.bar = float(np.median(same)) if len(same) else 900.0          # a bar's length (the last bar of a day has no successor)

    def x(self, t, frac=True):
        """x of time t (float when frac); None when t is after the chart's last bar's end."""
        tt = np.datetime64(pd.Timestamp(t), "ns")
        i = int(np.searchsorted(self.s, tt, side="right")) - 1
        if i < 0:
            return -0.5 - self.j0                                           # before the history: left of everything
        if i > self.j0 + self.n - 1:
            return None
        if not frac:
            return float(i - self.j0)
        nxt = self.s[i + 1] if i + 1 < len(self.s) else None
        if nxt is None and float((tt - self.s[i]).astype("timedelta64[s]").astype(float)) >= self.bar:
            return None                                                     # after the last bar's end
        span = float((nxt - self.s[i]).astype("timedelta64[s]").astype(float)) if nxt is not None else self.bar
        span = min(span, self.bar) if span > 0 else self.bar
        f = float((tt - self.s[i]).astype("timedelta64[s]").astype(float)) / span
        return i - self.j0 + min(max(f, 0.0), 0.999)


def _clip(x0, y0, x1, y1, left):
    """The segment from `left` on (linear in x); None when it ends before `left`."""
    if x1 < left:
        return None
    if x0 < left and x1 > x0:
        y0 = y0 + (y1 - y0) * (left - x0) / (x1 - x0)
        x0 = left
    return x0, y0, x1, y1


def _is_high(o):
    """A swing high? `src` = "H" / "L" (draw_objects.swings), else its label (HH / LH / EQH / H)."""
    if o.get("src") in ("H", "L"):
        return o["src"] == "H"
    return str(o.get("label", "")).strip().upper() in ("HH", "LH", "EQH", "H")


def _short(text):
    """Short label (the Vision panel is narrow): the words before the details in brackets."""
    return str(text).split(" (")[0].lstrip("> ").strip()


def _note(items):
    """Edge note text: the first two names + how many more."""
    return " · ".join(items[:2]) + (f" +{len(items) - 2} more" if len(items) > 2 else "")


def geometry(objects, xm, ylim=None, min_degree=None, kinds=None, label_gap=None, short=False):
    """Objects ⇒ primitives [{type: seg | band | marker | text, …}] in the chart's (x, price). ylim = (lo, hi) of the chart's price axis:
    a horizontal object outside it becomes an edge note (▲ / ▼); None ⇒ no clipping. min_degree: swings below it are not drawn (a 1H
    chart shows the D2 structure only). kinds: only these kinds. Right-margin labels are spread so they never overlap. short=True: the
    labels without their bracketed details (a narrow panel)."""
    n = xm.n
    right = n - 0.5
    left = -0.5
    lo, hi = ylim if ylim is not None else (-np.inf, np.inf)
    prims, margin, above, below = [], [], [], []

    def inside(y):
        return lo <= y <= hi

    def edge(y, text):
        (above if y > hi else below).append(text)

    for o in objects:
        if kinds is not None and o["kind"] not in kinds:
            continue
        st = style(o["style_key"])
        k = o["kind"]
        x0 = xm.x(o["t0"])
        x1 = xm.x(o["t1"])
        if x0 is None:                                                     # starts after the chart's last bar (never by construction)
            continue
        x1 = right if x1 is None else x1
        p0, p1 = float(o["p0"]), float(o["p1"])
        if k == "swing":
            if min_degree is not None and int(o.get("degree") or 0) < int(min_degree):
                continue
            xs = xm.x(o["t0"], frac=False)
            if xs is None or xs < 0 or not inside(p0):
                continue
            up = _is_high(o)
            prims.append({"type": "text", "x": xs, "y": p0, "text": o["label"], "color": st["color"], "size": st["size"],
                          "weight": st["weight"], "ha": "center", "va": "bottom" if up else "top", "dy": 3 if up else -3})
        elif k in ("area", "fvg"):
            a, b = max(p0, lo), min(p1, hi)
            if a > b:
                edge(p0, o["label"])
                continue
            xa = max(x0, left)
            xb = right if k == "area" else max(x1 + 0.5, xa + 1)
            prims.append({"type": "band", "x0": xa, "x1": xb, "y0": a, "y1": b, "color": st["color"], "alpha": st["alpha"],
                          "ls": st["ls"] if st["alpha"] == 0 else None})
            margin.append(((a + b) / 2, o["label"], st["color"]))
        elif k in ("level", "liquidity", "fib") and abs(p1 - p0) < 1e-9:
            if not inside(p0):
                edge(p0, o["label"])
                continue
            xa = max(x0, left)
            xb = right if o.get("state") not in ("taken",) else max(x1, xa + 1)
            prims.append({"type": "seg", "x0": xa, "y0": p0, "x1": xb, "y1": p0, "color": st["color"], "lw": st["lw"], "ls": st["ls"]})
            margin.append((p0, o["label"], st["color"]))
        elif k in ("line", "channel", "pattern", "liquidity", "level", "fib"):
            segs = [(x0, p0, x1, p1)] + [(xm.x(d["t0"]), d["p0"], xm.x(d["t1"]) or right, d["p1"]) for d in o.get("lines") or ()
                                         if xm.x(d["t0"]) is not None]
            for (a0, b0, a1, b1) in segs:
                c = _clip(a0, b0, a1, b1, left)
                if c is not None:
                    prims.append({"type": "seg", "x0": c[0], "y0": c[1], "x1": c[2], "y1": c[3], "color": st["color"], "lw": st["lw"],
                                  "ls": st["ls"]})
            for tp, pp in o.get("points") or ():
                xp = xm.x(tp, frac=False)
                if xp is not None and xp >= 0:
                    prims.append({"type": "marker", "x": xp, "y": float(pp), "marker": "o", "size": 5, "color": st["color"], "hollow": True})
            if x1 >= left:
                margin.append((p1, o["label"] + (f" ({o['state']})" if o.get("state") and o["state"] not in o["label"] else ""),
                               st["color"]))
        elif k == "sweep":
            xs = xm.x(o["t0"], frac=False)
            if xs is None or xs < 0:
                continue
            up = p1 > p0
            prims.append({"type": "seg", "x0": max(xs - 2, left), "y0": p0, "x1": max(x1, xs) + 0.5, "y1": p0, "color": st["color"],
                          "lw": 1.0, "ls": ":"})
            prims.append({"type": "marker", "x": xs, "y": p1, "marker": "X", "size": st["size"], "color": st["color"]})
            prims.append({"type": "text", "x": xs, "y": p1, "text": o["label"], "color": st["color"], "size": 6.5, "weight": "normal",
                          "ha": "center", "va": "bottom" if up else "top", "dy": 6 if up else -6})
        elif k == "divergence":
            c = _clip(x0, p0, x1, p1, left)
            if c is None:
                continue
            prims.append({"type": "seg", "x0": c[0], "y0": c[1], "x1": c[2], "y1": c[3], "color": st["color"], "lw": st["lw"], "ls": st["ls"]})
            up = "bear" in o["style_key"]
            prims.append({"type": "text", "x": c[2], "y": c[3], "text": o["label"], "color": st["color"], "size": 6.5, "weight": "bold",
                          "ha": "center", "va": "bottom" if up else "top", "dy": 14 if up else -14})
        elif k == "entry":
            xs = xm.x(o["t0"], frac=False)
            if xs is None or xs < 0:
                continue
            up = p1 < p0                                                   # invalidation below the entry ⇒ a long (bull) mark
            prims.append({"type": "marker", "x": xs, "y": p0, "marker": "^" if up else "v", "size": st["size"], "color": st["color"]})
            prims.append({"type": "text", "x": xs, "y": p0, "text": o["label"], "color": st["color"], "size": 8, "weight": "bold",
                          "ha": "center", "va": "top" if up else "bottom", "dy": -9 if up else 9})
            if inside(p1):
                prims.append({"type": "seg", "x0": xs - 0.5, "y0": p1, "x1": min(xs + 4, right), "y1": p1, "color": "#c92a2a", "lw": 1.0,
                              "ls": "--"})
                prims.append({"type": "text", "x": min(xs + 4, right), "y": p1, "text": "invalidation", "color": "#c92a2a", "size": 6.5,
                              "weight": "normal", "ha": "left", "va": "center", "dy": 0})
    gap = label_gap if label_gap is not None else (0.035 * (hi - lo) if np.isfinite(hi - lo) else 0.0)
    if short:
        margin = [(y, _short(t), c) for y, t, c in margin]
        above, below = [_short(t) for t in above], [_short(t) for t in below]
    for y, text, color in _spread(margin, lo, hi, gap):
        prims.append({"type": "text", "x": right, "y": y, "text": text, "color": color, "size": 7, "weight": "normal", "ha": "left",
                      "va": "center", "dy": 0, "margin": True})
    if above:
        prims.append({"type": "note", "where": "top", "x": right, "y": hi, "text": "▲ " + _note(above), "color": "#868e96"})
    if below:
        prims.append({"type": "note", "where": "bottom", "x": right, "y": lo, "text": "▼ " + _note(below), "color": "#868e96"})
    return prims


def _spread(items, lo, hi, gap):
    """Right-margin labels sorted by price and pushed apart by `gap` (kept inside lo … hi when finite)."""
    items = sorted(items, key=lambda x: x[0])
    ys = [y for y, _, _ in items]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + gap)
    if ys and np.isfinite(hi) and ys[-1] > hi:
        shift = ys[-1] - hi
        ys = [y - shift for y in ys]
        for i in range(len(ys) - 2, -1, -1):
            ys[i] = min(ys[i], ys[i + 1] - gap)
    return [(y, t, c) for y, (_, t, c) in zip(ys, items)]


def y_range(df_lo, df_hi, objects, pad=0.04):
    """The price axis: the candles, widened to the areas / lines drawn (the 1H chart today also shows its areas); far levels become
    edge notes instead of squashing the candles."""
    lo, hi = float(df_lo), float(df_hi)
    for o in objects:
        if o["kind"] in ("area", "line", "channel", "entry"):
            lo, hi = min(lo, o["p0"], o["p1"]), max(hi, o["p0"], o["p1"])
    p = pad * (hi - lo or 1.0)
    return lo - p, hi + p


# ------------------------------------------------------------------------------------------------------------------------- backends
MPL_MARK = {"o": "o", "X": "X", "^": "^", "v": "v"}


def draw_mpl(ax, prims, zorder=4):
    """matplotlib backend (decision3 charts). Texts in the right margin go just outside the last bar (as the charts' labels today)."""
    import matplotlib.pyplot as plt  # noqa: F401
    for p in prims:
        t = p["type"]
        if t == "band":
            if p["alpha"] > 0:
                ax.add_patch(_rect(p["x0"], p["y0"], p["x1"] - p["x0"], p["y1"] - p["y0"], fc=p["color"], alpha=p["alpha"], lw=0,
                                   z=zorder - 2))
            else:
                ax.add_patch(_rect(p["x0"], p["y0"], p["x1"] - p["x0"], p["y1"] - p["y0"], fc="none", ec=p["color"], ls=p["ls"] or "--",
                                   lw=1.0, z=zorder - 2))
        elif t == "seg":
            ax.plot([p["x0"], p["x1"]], [p["y0"], p["y1"]], color=p["color"], lw=p["lw"], ls=p["ls"], zorder=zorder)
        elif t == "marker":
            ax.plot(p["x"], p["y"], marker=MPL_MARK.get(p["marker"], "o"), ms=p["size"], color=p["color"], zorder=zorder + 1,
                    **({"mfc": "none", "mec": p["color"]} if p.get("hollow") else {}))
        elif t == "text":
            ax.annotate(p["text"], (p["x"], p["y"]), textcoords="offset points", xytext=(4 if p.get("margin") else 0, p["dy"]),
                        ha=p["ha"], va=p["va"], fontsize=p["size"], color=p["color"], fontweight=p["weight"], annotation_clip=False,
                        zorder=zorder + 2)
        elif t == "note":
            ax.text(0.99, 0.99 if p["where"] == "top" else 0.01, p["text"], transform=ax.transAxes, ha="right",
                    va="top" if p["where"] == "top" else "bottom", fontsize=7, color=p["color"])


def _rect(x, y, w, h, fc, alpha=1.0, ec="none", ls="-", lw=0, z=1):
    from matplotlib.patches import Rectangle
    return Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, alpha=alpha if fc != "none" else 1.0, ls=ls, lw=lw, zorder=z)


def _rgba(hex_, a):
    h = hex_.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def draw_plotly(fig, prims, row=1, col=1, label=True):
    """plotly backend (vision/chart.py, dark chart). Same primitives; margin labels inside the right edge (the Vision chart has no
    free right margin). label=False: no texts (the higher-timeframe panel keeps the shapes only)."""
    import plotly.graph_objects as go
    for p in prims:
        t = p["type"]
        if t == "band":
            fill = _rgba(p["color"], max(p["alpha"], 0.0) * 1.2) if p["alpha"] > 0 else "rgba(0,0,0,0)"
            fig.add_shape(type="rect", x0=p["x0"], x1=p["x1"], y0=p["y0"], y1=p["y1"], layer="below", fillcolor=fill,
                          line=dict(color=p["color"], width=1 if p["alpha"] == 0 else 0, dash="dash" if p["alpha"] == 0 else None),
                          row=row, col=col)
        elif t == "seg":
            fig.add_shape(type="line", x0=p["x0"], x1=p["x1"], y0=p["y0"], y1=p["y1"],
                          line=dict(color=p["color"], width=p["lw"], dash=PLOTLY_DASH.get(p["ls"])), row=row, col=col)
        elif t == "marker":
            sym = {"o": "circle-open" if p.get("hollow") else "circle", "X": "x", "^": "triangle-up", "v": "triangle-down"}[p["marker"]]
            fig.add_trace(go.Scatter(x=[p["x"]], y=[p["y"]], mode="markers", marker=dict(symbol=sym, size=p["size"] + 2, color=p["color"]),
                                     showlegend=False, hoverinfo="skip"), row=row, col=col)
        elif t == "text" and label:
            if p.get("margin"):
                fig.add_annotation(x=p["x"], y=p["y"], text=p["text"], showarrow=False, xanchor="right", yshift=0,
                                   font=dict(size=8, color=p["color"]), row=row, col=col)
            else:
                ys = p["dy"] * 1.4
                fig.add_annotation(x=p["x"], y=p["y"], text=(f"<b>{p['text']}</b>" if p["weight"] == "bold" else p["text"]), showarrow=False,
                                   xanchor={"center": "center", "left": "left", "right": "right"}[p["ha"]], yshift=ys,
                                   font=dict(size=int(round(p["size"] + 1)), color=p["color"]), row=row, col=col)
        elif t == "note" and label:
            fig.add_annotation(x=p["x"], y=p["y"], text=p["text"], showarrow=False, xanchor="right",
                               yshift=-8 if p["where"] == "top" else 8, font=dict(size=8, color="#b0bec5"), row=row, col=col)
