"""swings2/charts.py — 🧭 SWING CHECK (v2.1 §5): 15M (D1 + D0 लहान), 1H (D2), Daily (D3), Weekly (D4; holdout राखाडी display_only).
खुणा: HH / HL / LH / LL / EQ, tentative पोकळ, protected (strict) रेघ, BOS ▲▼, CHoCH ⚑, sweep ~, RANGE पट्टा, gap_bar खूण.
अपूर्ण aggregate candle (1H / Daily / Weekly) कधीच नाही. Box: प्रत्येक degree चा trend, शेवटचे 2 pivots, protected, शेवटची घटना."""
import numpy as np
import pandas as pd

from pivots import charts as PC
from pivots import engine as PE

from . import engine as SE
from . import structure as ST

MARK = {"BOS": ("▲", "▼"), "CHoCH": ("⚑", "⚑"), "sweep": ("~", "~"), "reversal": ("R▲", "R▼"), "range_break": ("⇧", "⇩"),
        "failed_gap_break": ("✕", "✕")}
EVNAME = {"BOS": "BOS", "CHoCH": "CHoCH", "sweep": "sweep", "reversal": "reversal पूर्ण", "range_break": "range तुटला",
          "failed_gap_break": "gap break अयशस्वी"}
COLOR = {"BOS": "#ffd54f", "CHoCH": "#ff8a65", "sweep": "#80deea", "reversal": "#ce93d8", "range_break": "#a5d6a7",
         "failed_gap_break": "#ef9a9a"}


def complete_1h(m, asof):
    """फक्त पूर्ण 1H candles: पूर्ण तास, किंवा session पूर्ण झाल्यावर शेवटची लहान candle."""
    h1 = PC.agg_1h(m)
    if not len(h1):
        return h1
    t = pd.to_datetime(h1["timestamp"])
    full = (pd.to_datetime(h1["bar_end"]) - t) >= pd.Timedelta(hours=1)
    sess = [PE.session_complete(d, e) for d, e in zip(t.dt.normalize(), m.assign(_d=pd.to_datetime(m["timestamp"]).dt.normalize())
                                                          .groupby("_d")["bar_end"].max().reindex(t.dt.normalize()).to_numpy())]
    return h1[full.to_numpy() | np.array(sess)].reset_index(drop=True)


TREND_MR = {"UP": "वर", "DOWN": "खाली", "RANGE": "range", "unknown": "अज्ञात"}


def complete_weekly(daily, asof):
    """फक्त पूर्ण आठवडे: चालू आठवड्यात asof नंतर अजून trading दिवस बाकी ⇒ ती weekly candle नाही (एकच calendar: data दिवस +
    NSE सुट्ट्या)."""
    import datetime as dt

    from elliott import contracts as EC
    w = PC.weekly_from_daily(daily, asof)
    if not len(w) or not len(daily):
        return w
    try:
        import config
        hol = set().union(*[set(v) for k, v in vars(config).items() if k.startswith("NSE_HOLIDAYS") and isinstance(v, (set, frozenset, list, tuple))])
    except Exception:                                                              # noqa: BLE001
        hol = set()
    cal = EC.TradingCalendar(pd.to_datetime(daily["timestamp"]), hol)
    day = pd.Timestamp(asof).normalize().date()
    nxt = day + dt.timedelta(days=1)
    left = False
    while nxt.weekday() < 5:
        if cal.is_trading(nxt):
            left = True
            break
        nxt += dt.timedelta(days=1)
    return w.iloc[:-1].reset_index(drop=True) if left else w


def state_at(struct, d, t):
    return struct[d]["states"][t] if d in struct else None


def snap(res, struct, asof, t):
    """pivots.charts.figure ला चालणारा snapshot + structure."""
    out = {}
    for d in SE.DEGREES:
        ps = SE.known(res, d, asof)
        lab = SE.labels(ps)
        st = state_at(struct, d, t)
        name = st["trend"] if st else ST.trend_of([p for p in ps if not p.warmup])
        prot = {"price": st["strict"]} if st and st.get("strict") is not None else None
        out[f"D{d}"] = {"pivots": [SE.pivot_json(p, lab[id(p)]) for p in ps], "tentative": SE.tentative(res, d, asof),
                        "trend": {"name": name, "protected": prot}, "warmup_done": any(not p.warmup for p in ps), "state": st}
    return out


def last_event(struct, d, t):
    ev = [e for e in struct.get(d, {}).get("events", []) if e["bar"] <= t and e["type"] in MARK]
    return ev[-1] if ev else None


def box_text(sn, struct, t):
    rows = []
    for d, nm in ((1, "15M (D1)"), (2, "1H (D2)"), (3, "Daily (D3)"), (4, "Weekly (D4)")):
        s = sn[f"D{d}"]
        last = " · ".join(f"{p['label']} {p['price']:,.0f}" for p in s["pivots"][-2:]) or "—"
        pr = s["trend"]["protected"]
        e = last_event(struct, d, t)
        tag = ("" if s["warmup_done"] else " (warm-up)") + (" · display only (gate नाही)" if d == 4 else "")
        rows.append(f"<b>{nm}</b>: {TREND_MR.get(s['trend']['name'], s['trend']['name'])}{tag} · {last}"
                    + (f" · protected {pr['price']:,.0f}" if pr else "") + (f" · {e['type']} {e['ts'][5:16]}" if e else ""))
    return "<br>".join(rows)


def overlay(fig, frame, struct, d, t, res, minor_gaps=True):
    import plotly.graph_objects as go
    if d not in struct:
        return
    t0 = pd.to_datetime(frame["timestamp"]).min()
    st = struct[d]["states"][t]
    if st and st.get("strict") is not None:                                         # strict_HL / strict_LH खूण
        fig.add_shape(type="line", x0=0, x1=len(frame) - 1, y0=st["strict"], y1=st["strict"],
                      line=dict(color="#ff8a65", width=1, dash="dashdot"))
        fig.add_annotation(x=0, y=st["strict"], text=f"strict {st['strict']:,.0f}", showarrow=False, xanchor="left", yanchor="bottom",
                           font=dict(size=10, color="#ff8a65"))
    if st and st.get("range"):
        r = st["range"]
        fig.add_hrect(y0=r["bottom"], y1=r["top"], fillcolor="rgba(165,214,167,0.12)", line_width=0, layer="below")
        fig.add_annotation(x=0.99, y=r["top"], xref="paper", text="RANGE", showarrow=False, xanchor="right", yanchor="bottom",
                           font=dict(size=10, color="#a5d6a7"))
    xs, ys, tx, cs = [], [], [], []
    for e in struct[d]["events"]:
        if e["bar"] > t or e["type"] not in MARK or pd.Timestamp(e["ts"]) < t0:
            continue
        x = PC._x_of(frame, e["ts"])
        if x is None:
            continue
        up = e["dir"] > 0
        y = res["A"]["h"][e["bar"]] if up else res["A"]["l"][e["bar"]]
        xs.append(x)
        ys.append(y)
        tx.append(MARK[e["type"]][0 if up else 1])
        cs.append(COLOR[e["type"]])
    if xs:
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="text", text=tx, textposition="top center", textfont=dict(size=14, color=cs),
                                 showlegend=False, hoverinfo="skip"))
    if minor_gaps:
        gx = [PC._x_of(frame, str(res["m15"]["timestamp"].iloc[g])) for g in res["gap_bar_2s"] if g <= t
              and pd.Timestamp(res["m15"]["timestamp"].iloc[g]) >= t0]
        gx = [x for x in gx if x is not None]
        for x in gx:
            fig.add_vline(x=x - 0.5, line=dict(color="rgba(239,154,154,0.5)", width=1, dash="dot"))


def charts(res, struct, t, history_daily=None, title_kind="दिवस-अखेर"):
    """bar t (बंद) पर्यंतचे चार charts ⇒ ({tf: png}, snapshot)."""
    m15 = res["m15"]
    m = m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    sn = snap(res, struct, asof, t)
    daily = PC.daily_from_15m(m, asof)
    weekly = complete_weekly(daily, asof)
    hd = hw = None
    if history_daily is not None and len(history_daily):
        hd = history_daily[pd.to_datetime(history_daily["timestamp"]) + pd.Timedelta(hours=15, minutes=30) <= asof]
        hw = PC.weekly_from_daily(hd.assign(bar_end=pd.to_datetime(hd["timestamp"]) + pd.Timedelta(hours=15, minutes=30)), asof)
        hd, hw = PC.display_only(hd), PC.display_only(hw)
    title = "🧭 SWING CHECK · NIFTY {tf} · {d:%d %b %Y %H:%M} " + title_kind + " · {deg}"
    f15 = PC.window(m, "15M", asof)
    fig = PC.figure(f15, "15M", sn, 1, title.format(tf="15M", d=asof, deg="D1 (मोठे) + D0 (लहान)"), minor=0, box=False)
    overlay(fig, f15, struct, 1, t, res)
    fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                       text=box_text(sn, struct, t), font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64",
                       borderwidth=1)
    h1 = PC.window(complete_1h(m, asof), "1H", asof)
    fig1 = PC.figure(h1, "1H", sn, 2, title.format(tf="1H", d=asof, deg="D2"), box=False)
    overlay(fig1, h1, struct, 2, t, res, minor_gaps=False)
    out = {"15M": PC.png(fig), "1H": PC.png(fig1),
           "D": PC.png(PC.figure(daily, "D", sn, 3, title.format(tf="Daily", d=asof, deg="D3"), history=hd, box=False)),
           "W": PC.png(PC.figure(weekly, "W", sn, 4, title.format(tf="Weekly", d=asof, deg="D4"), history=hw, box=False))}
    return out, sn


def caption(n, total, sn, struct, t, asof, why=None):
    """≤ 8 ओळी, ≤ 1024 (UTF-16), code keys नाहीत."""
    def line(d, nm):
        s = sn[f"D{d}"]
        last = " / ".join(f"{p['kind']} {p['price']:,.0f}" for p in s["pivots"][-2:]) or "—"
        e = last_event(struct, d, t)
        return f"{nm}: {TREND_MR.get(s['trend']['name'], s['trend']['name'])} · {last}" + (f" · {EVNAME[e['type']]}" if e else "")
    head = f"🧭 SWING CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y} · {pd.Timestamp(asof):%H:%M}"
    lines = [head + (f" · {EVNAME.get(why, why)}" if why else ""), line(1, "15M"), line(2, "1H"), line(3, "Daily"), line(4, "Weekly"),
             "Reply: ✔ बरोबर · ✘ कोणती degree, कोणता swing / घटना चुकली"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        if lines[-2]:
            lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
        else:
            lines.pop(-2)
    return "\n".join(lines)


def k_options_png(m15, df1m, asof, degree, ks, s=None):
    """एकाच दिवसाचे तीन k (swings2 engine — raw crossing) शेजारी."""
    import io

    from PIL import Image
    ims = []
    for k in ks:
        res = SE.build(m15, df1m, {**(s or {}), "k": {degree: k}})
        sn = snap(res, {}, asof, int((pd.to_datetime(m15["bar_end"]) <= pd.Timestamp(asof)).sum()) - 1)
        m = m15[pd.to_datetime(m15["bar_end"]) <= pd.Timestamp(asof)]
        f = PC.window(m, "15M", asof) if degree == 1 else PC.window(complete_1h(m, asof), "1H", asof)
        fig = PC.figure(f, "15M" if degree == 1 else "1H", sn, degree, f"D{degree} · k = {k:g} (swings2)", box=False)
        ims.append(Image.open(io.BytesIO(PC.png(fig))).convert("RGB"))
    w, h = ims[0].size
    page = Image.new("RGB", (w * len(ims), h), "#0e1117")
    for i, im in enumerate(ims):
        page.paste(im, (i * w, 0))
    buf = io.BytesIO()
    page.save(buf, "PNG")
    return buf.getvalue()
