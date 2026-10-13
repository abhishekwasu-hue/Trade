"""trendlines2/charts.py — 🧭 TRENDLINE CHECK (थर 5 §6): 15M (trade-योग्य ठळक, लागू नाही फिकी, तुटलेली राखाडी, K आधार / टोक निळी
तुटक, आधार-break ⭑, trade-बाजूचे zones फिके, ∩ ★) + box; 1H (D2 रेघा)."""
import pandas as pd

import instruments as INS
from backtest_review import charts as BC
from pivots import charts as PC

COL = {"trade-योग्य": ("#ef5350", 3, "solid"), "लागू नाही": ("rgba(239,154,154,0.5)", 1.5, "solid"),
       "तुटलेली": ("rgba(144,164,174,0.6)", 1.2, "dot"), "सपाट": ("rgba(176,190,197,0.5)", 1, "dash"),
       "तीव्र": ("rgba(255,183,77,0.5)", 1, "dash"), "K": ("#42a5f5", 2, "dash")}


def checked_lines(lines, chk, keep_broken=False):
    """TA1 (Abhi, design §10), drawing layer only: each engine line through the shared K6 check (facts/validity.py) on the 15M bars up
    to t (`chk`; the engine's own frame). Returns [(line json, facts or None)]; facts None = anchors not in the frame (unverifiable).
    keep_broken: K base / tip lines — their real break is the trigger (K6.5), so "broken" alone does not make them invalid."""
    from facts import validity as FV
    pos = {pd.Timestamp(x): i for i, x in enumerate(pd.to_datetime(chk["timestamp"]))}
    t = len(chk) - 1
    out = []
    for lj in lines:
        b1, b2 = pos.get(pd.Timestamp(lj["a1"]["ts"])), pos.get(pd.Timestamp(lj["a2"]["ts"]))
        f = None
        if b1 is not None and b2 is not None and b1 < b2:
            f = FV.check_line(chk, t, (b1, float(lj["a1"]["price"])), (b2, float(lj["a2"]["price"])), FV.RES if lj["kind"] == "H" else FV.SUP)
            if keep_broken and f["reasons"] == ["broken"]:
                f = dict(f, valid=True)
        out.append((lj, f))
    return out


def shown_lines(lines, chk, debug=False):
    """TA1: at most 2 valid lines (facts.validity.select_lines); debug: every line, invalid ones marked."""
    from facts import validity as FV
    ch = checked_lines(lines, chk)
    if debug:
        return ch
    pick = {id(f) for f in FV.select_lines([f for _, f in ch if f is not None and f["valid"]])}
    return [(lj, f) for lj, f in ch if f is not None and id(f) in pick]


def _draw(fig, d, E, lj, t, cls, facts=None):
    import plotly.graph_objects as go
    t0 = pd.to_datetime(d["timestamp"]).min()
    n = len(d)
    a1t, a2t = pd.Timestamp(lj["a1"]["ts"]), pd.Timestamp(lj["a2"]["ts"])
    x2 = PC._x_of(d, a2t) if a2t >= t0 else None
    xn = n - 1
    if x2 is None:
        return
    p2 = lj["a2"]["price"]
    slope_x = (lj["value_now"] - p2) / max(xn - x2, 1)
    x1 = PC._x_of(d, a1t) if a1t >= t0 else 0
    y1 = lj["a1"]["price"] if a1t >= t0 else p2 - slope_x * (x2 - x1)
    col, w, dash = COL.get(cls, COL["लागू नाही"])
    if lj["kind"] == "L" and cls == "trade-योग्य":
        col = "#26a69a"
    fig.add_trace(go.Scatter(x=[x1, x2, xn, xn + 4], y=[y1, p2, lj["value_now"], lj["value_now"] + 4 * slope_x], mode="lines",
                             line=dict(color=col, width=w, dash=dash), showlegend=False, hoverinfo="skip"))
    if facts is not None:                                                  # TA3 label: shared touch count + projected 3rd touch
        from trendlines2 import two_touch as TT
        tag = f"{lj['name'] or ''} · " + TT.line_label(facts)
    else:
        tag = f"{lj['name'] or ''} · {lj['touches']['held']} touches" + (" · flip" if lj["status"] == "flip" else "") + \
            (f" · {lj['touches']['slope_cls']}" if lj["touches"].get("slope_cls") else "")
    fig.add_annotation(x=xn, y=lj["value_now"], text=tag, showarrow=False, xanchor="left", font=dict(size=9, color=col))


def figure(frame, tf, r, E, t, title, zones=None, box=None, chk=None, debug=False):
    """chk = the 15M bars up to t ⇒ TA1 drawing rule (≤ 2 valid lines, touch count + projected 3rd touch; zones only if they pass the
    shared band check); chk None ⇒ the old drawing (all engine lines)."""
    import plotly.graph_objects as go
    d = frame.reset_index(drop=True)
    fig = BC._base(d, title)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    if chk is not None and zones and not debug:
        from zones2 import charts as ZC
        zones = [z for z, f, _ in ZC.shown_zones(zones, chk)]
    for z in zones or []:
        fig.add_shape(type="rect", x0=0, x1=len(d) - 1, y0=z["bottom"], y1=z["top"], fillcolor="rgba(239,83,80,0.07)" if z["role"] == "seller"
                      else "rgba(38,166,154,0.07)", line=dict(width=0), layer="below")
    if chk is None:
        for lj in r.get("lines", []):
            _draw(fig, d, E, lj, t, lj["class"])
    else:
        for lj, f in shown_lines(r.get("lines", []), chk, debug):
            _draw(fig, d, E, lj, t, lj["class"] if (f is not None and f["valid"]) else "लागू नाही", f)
    kl = r.get("k_lines") or {}
    for k in ("base", "tip"):
        if kl.get(k):
            f = checked_lines([kl[k]], chk, keep_broken=True)[0][1] if chk is not None else None
            if chk is None or debug or (f is not None and f["valid"]):
                _draw(fig, d, E, kl[k], t, "K", f)
    kb = r.get("k_base")
    if kb:
        x = PC._x_of(d, pd.Timestamp(kb["ts"]))
        if x is not None:
            fig.add_trace(go.Scatter(x=[x], y=[float(E.A["c"][kb["bar"]])], mode="text", text=["⭑ K आधार break"],
                                     textfont=dict(size=12, color="#42a5f5"), showlegend=False, hoverinfo="skip"))
    ka = r.get("k_area_line") or {}
    if ka.get("intersection"):
        fig.add_annotation(x=len(d) - 1, y=ka["value"], text="★ ∩ zone", showarrow=False, font=dict(size=14, color="#ffd54f"))
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=box, font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    fig.add_annotation(x=0.5, y=0.55, xref="paper", yref="paper", text=tf, showarrow=False, font=dict(size=140, color="rgba(255,255,255,0.07)"))
    BC._finish(fig, d, lo, hi, fmt="%d %b %H:%M")
    return fig


def box_text(r, momentum=None, zone_area=None):
    ka = r.get("k_area_line") or {}
    kb = r.get("k_base")
    side = {"seller": "seller", "buyer": "buyer", None: "—"}[r.get("side")]
    rows = [f"<b>बाजू</b>: {side}",
            f"<b>K sloping area</b>: {ka.get('ans', 'NA')}" + (f" · {ka.get('name')} · {ka.get('touches')} वा स्पर्श" if ka.get("line") else "")
            + (" · ∩ zone" if ka.get("intersection") else ""),
            "<b>K आधार-रेघ</b>: " + (f"break {kb['ts'][11:16]} · {kb['beyond_sigma']}σ" + (" · Q" + "".join(k[1] for k, v in (kb['Q'] or {}).items() if v)
                                                                                           if kb.get("Q") else "") if kb else "नाही"),
            f"पुढची रेघ: {r['next_line']:,.0f}" if r.get("next_line") else "पुढची रेघ: —"]
    if zone_area:
        rows.append(f"K area (थर 4): {zone_area.get('ans')}")
    if momentum:
        rows.append(f"momentum: <b>{momentum['verdict']}</b>")
    return "<br>".join(rows)


def charts(E, E1h, r, r1h, t, zones=None, momentum=None, zone_area=None, debug=False):
    m = E.m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    title = "🧭 TRENDLINE CHECK · " + INS.label() + " {tf} · {d:%d %b %Y %H:%M}"
    return {"15M": PC.png(figure(PC.window(m, "15M", asof), "15M", r, E, t, title.format(tf="15M", d=asof), zones,
                                 box_text(r, momentum, zone_area), chk=m, debug=debug)),
            "1H": PC.png(figure(PC.window(PC.agg_1h(m), "1H", asof), "1H", r1h, E1h, t, title.format(tf="1H", d=asof), chk=m, debug=debug))}


def caption(n, total, asof, r, why=None):
    ka = r.get("k_area_line") or {}
    kb = r.get("k_base")
    side = {"seller": "seller", "buyer": "buyer", None: "—"}[r.get("side")]
    lines = [f"🧭 TRENDLINE CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर"),
             f"बाजू: {side}",
             f"K रेघेवर: {ka.get('ans', 'NA')}" + (f" · {ka.get('touches')} touches" if ka.get("line") else "")
             + (" · ∩ zone" if ka.get("intersection") else ""),
             "K आधार-रेघ: " + (f"break · {pd.Timestamp(kb['ts']):%H:%M}" if kb else "नाही"),
             f"पुढची रेघ: {r['next_line']:,.0f}" if r.get("next_line") else "पुढची रेघ: —",
             "Reply: ✔ बरोबर · ✘ कोणती रेघ चुकली / सुटली (दोन टोकं: वेळ, किंमत)"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)


def moments(L5, bars, k):
    out, prev = [], None
    for t in bars[:-1]:
        r = L5.get(t) or {}
        a = (r.get("k_area_line") or {}).get("ans", "NA")
        why = None
        if a.startswith("हो") and (prev is None or not prev.startswith("हो")):
            why = "K रेघेला स्पर्श"
        kb = r.get("k_base")
        if kb and kb["bar"] == t:
            why = "K आधार-रेघ break"
        if any(x["status"] == "flip" and x.get("break") and pd.Timestamp(x["break"]["ts"]) == pd.Timestamp(r.get("ts", "1970")) for x in
               r.get("lines", [])):
            why = "रेघ flip"
        if why:
            out.append((t, why))
        prev = a
        if len(out) >= k:
            break
    return out


def rows(L5, t0, t1):
    rs = [L5[t] for t in L5 if t0 <= t <= t1]
    cls, ka, kb = {}, {}, 0
    for r in rs:
        for x in r["lines"]:
            cls[x["class"]] = cls.get(x["class"], 0) + 1
        a = (r.get("k_area_line") or {}).get("ans", "NA")
        ka[a] = ka.get(a, 0) + 1
        kb += bool(r.get("k_base") and r["k_base"]["bar"] == r["bar"])
    return [{"रेघा (bar-वार)": ", ".join(f"{k}:{v}" for k, v in sorted(cls.items())),
             "K sloping area": ", ".join(f"{k}:{v}" for k, v in sorted(ka.items())), "K आधार breaks": kb,
             "∩ zone": sum(1 for r in rs if (r.get("k_area_line") or {}).get("intersection"))}]


def register_rows():
    from . import settings as TS
    return [{"आकडा": k, "default": str(v[0]), "पर्याय": str(v[1]), "वर्ग": v[2], "स्रोत": v[3]} for k, v in TS.REGISTER.items()]
