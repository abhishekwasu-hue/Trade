"""correction/annotate.py — correction_read ⇒ W / D / 1H / 15M charts + checklist box, Telegram caption, PDF पान.

🎓 Abhi (annotation prompt): code ने checklist प्रमाणे chart वाचला का हे Abhi chart पाहून तपासेल. म्हणून chart वर:
  I ची रेघ (origin → शेवट), K चे labels (pivot वर, किंमत legend मध्ये), alternate फिकट; seller / buyer zones (प्रत्येक बाजूला ≤ 4;
  solid गडद, weak solid फिकट, ruler ठिपके); trendlines (anchors legend मध्ये); pattern च्या रेघा; completion zone; price failure candle;
  SL / target (setup असेल तरच); कोपऱ्यात checklist box (12 मुद्दे + निर्णय). किंमती फक्त OHLC / correction_read मधून.
"""
import io

import numpy as np
import pandas as pd

from backtest_review import charts as BC

SELL, BUY = "#ef5350", "#26a69a"
LABEL_COL = "#ffd54f"
ALT_COL = "rgba(255,213,79,0.45)"
IMP_COL = "#42a5f5"
BARS = {"W": 80, "D": 120, "1H": 70, "15M": 100}
MAX_BARS = {"1H": 260, "15M": 420}
OUTCOME_MR = {"setup": "setup", "wait": "थांबा", "no_trade": "trade नाही"}


def window(f, tf, start):
    """1H / 15M: start (I origin च्या आधीचा swing) पासून — किमान BARS, कमाल MAX_BARS. W / D: शेवटचे BARS."""
    if start is None or tf not in MAX_BARS:
        return f.tail(BARS[tf]).reset_index(drop=True)
    i = int(np.searchsorted(pd.to_datetime(f["timestamp"]).to_numpy(), np.datetime64(pd.Timestamp(start))))
    i = max(0, i - 3)
    n = min(max(len(f) - i, BARS[tf]), MAX_BARS[tf])
    return f.tail(n).reset_index(drop=True)


def window_start(R, ms_swings=None):
    """I origin च्या आधीचा swing (market_state swings, फक्त asof पर्यंतचे) — नसेल ⇒ I origin."""
    I = (R.get("impulse") or {}).get("I")
    if not I:
        return None
    s0 = pd.Timestamp(I["from_ts"])
    before = sorted(pd.Timestamp(p["ts"]) for p in (ms_swings or []) if pd.Timestamp(p["ts"]) < s0)
    return before[-1] if before else s0


def _rgba(hexcol, a):
    h = hexcol.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def chart_trendlines(R, per_role=2):
    """Valid, न तुटलेल्या trendlines — प्रत्येक role ला जास्तीत जास्त per_role (touches जास्त, मग ताजी). बाकी JSON मध्ये."""
    tls = [z for z in (R.get("area") or {}).get("trendlines") or [] if z.get("valid") and z.get("state") != "BROKEN"]
    out = []
    for role in ("RESISTANCE", "SUPPORT"):
        zs = sorted([z for z in tls if z.get("role") == role],
                    key=lambda z: (-(z.get("touches") or 0), -max([pd.Timestamp(a[0]).value for a in z.get("anchors") or []] or [0])))
        out += zs[:per_role]
    return out


def checklist_box(R, compact=False):
    """कोपऱ्यातला box: 12 मुद्दे (code चं ✔ / ✘ / –, पुरावा) + निर्णय."""
    rows = []
    for n in range(1, 13):
        it = R["items"].get(n)
        if not it:
            continue
        ev = it["evidence"]
        lim = 46 if compact else 78
        ev = ev if len(ev) <= lim else ev[:lim - 1] + "…"
        col = {"✔": "#66bb6a", "✘": "#ef5350"}.get(it["status"], "#90a4ae")
        g = "◆" if it.get("gate") else " "
        rows.append(f"<span style='color:{col}'>{it['status']}</span> {n}{g} {it['name']}: {ev}")
    rows.append("<span style='color:#90caf9'>📊 " + volume_line(R) + "</span>")
    if R.get("noise"):
        rows.append("<span style='color:#90a4ae'>· नोंद (noise, पुष्टी नाही): " + "; ".join(R["noise"]) + "</span>")
    d = R.get("decision") or {}
    rows.append(f"<b>🎯 {OUTCOME_MR.get(d.get('outcome'), d.get('outcome'))}: {d.get('what', '')}</b>"
                + (f" · grade {R['grade']}" if R.get("grade") else ""))
    return "<br>".join(rows)


def _k(v):
    return "—" if v is None else (f"{v / 1000:,.0f}k" if v >= 1000 else f"{v:,.0f}")


def volume_line(R):
    """Box: impulse वि. correction सरासरी futures volume (rollover वगळून), area candle चं volume."""
    v = R.get("volume") or {}
    if not v.get("available"):
        return "Futures volume: data नाही (NA)"
    t = f"Futures volume सरासरी: impulse {_k(v.get('impulse_avg'))} · correction {_k(v.get('correction_avg'))}"
    if v.get("ratio") is not None:
        t += f" (K÷I {v['ratio']})"
    if v.get("rel_ratio") is not None:
        t += f" · rel_vol K÷I {v['rel_ratio']}"
    t += f" · area candle {_k(v.get('area_candle'))}" + (f" (rel {v['area_candle_rel']})" if v.get("area_candle_rel") is not None else "")
    t += f" · decision candle {_k(v.get('decision_candle'))}"
    if v.get("excluded_roll_bars"):
        t += f" · rollover {', '.join(v.get('roll_days') or [])} वगळले"
    return t


def _lab_items(R, tf, xi, d, alt=False):
    hyps = (R.get("pattern") or {}).get("hypotheses") or []
    h = hyps[1] if alt and len(hyps) > 1 else (hyps[0] if hyps and not alt else None)
    if not h:
        return []
    out = []
    for x in h["labels"]:
        t = pd.Timestamp(x["ts"])
        if t < pd.Timestamp(d["timestamp"].iloc[0]):
            continue
        out.append({"x": xi(t), "y": x["price"], "text": x["label"] + ("?" if x.get("tentative") else ""), "alt": alt})
    return out


def figure(f, tf, R, title, m15_ts=None, box=True):
    """एक chart. f = त्या TF चे बंद bars (window). R = correction_read."""
    import plotly.graph_objects as go
    d = f.reset_index(drop=True)
    fig = BC._base(d, title)
    xi = BC._xmap(d)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    span = hi - lo
    for z in (R.get("area") or {}).get("chart_zones") or []:           # निवडलेले zones axis मध्ये (edge label legend खाली लपत नाही)
        if z["low"] >= lo - 0.25 * span and z["high"] <= hi + 0.25 * span:
            lo, hi = min(lo, z["low"]), max(hi, z["high"])
    n = len(d)
    marks = []
    t0 = pd.Timestamp(d["timestamp"].iloc[0])
    # zones (prices only from correction_read)
    for z in (R.get("area") or {}).get("chart_zones") or []:
        col = SELL if z["side"] == "sell" else BUY
        a = 0.28 if z["class"] == "solid" else 0.12
        fig.add_shape(type="rect", x0=0, x1=n - 1, y0=z["low"], y1=z["high"], fillcolor=_rgba(col, a), line=dict(width=0), layer="below")
        nm = {"a": "swing cluster", "b": "flip F", "c": "base", "d": "range edge", "e": "liquidity", "f": "trendline", "j": "round",
              "k": "PDH/PDL/PDC", "l": "gap edge"}.get(z["tool"], z["tool"])
        marks.append({"y": (z["low"] + z["high"]) / 2, "text": f"{'seller' if z['side'] == 'sell' else 'buyer'} {nm} {z['low']:,.0f}–{z['high']:,.0f}"
                      + (" (weak)" if z["class"] == "weak solid" else ""), "color": col})
    cz = (R.get("area") or {}).get("completion_zone")
    if cz and tf in ("1H", "15M"):
        fig.add_shape(type="rect", x0=max(0, n - 30), x1=n - 1, y0=cz["low"], y1=cz["high"], fillcolor="rgba(255,235,59,0.18)",
                      line=dict(color="rgba(255,235,59,0.6)", width=1, dash="dot"))
        marks.append({"y": (cz["low"] + cz["high"]) / 2, "text": f"completion zone {cz['low']:,.0f}–{cz['high']:,.0f} ({' + '.join(cz['parts'])})",
                      "color": "#fff176"})
    if tf in ("1H", "15M"):
        # trendlines (valid) — 15M bars मध्ये anchor पासून slope
        for z in chart_trendlines(R):
            fn = BC._tl_value_fn(z, m15_ts)
            if fn is None:
                continue
            a0 = pd.Timestamp((z.get("pair") or z.get("anchors"))[0][0])
            xs = [i for i in range(n) if pd.Timestamp(d["timestamp"].iloc[i]) >= a0]
            if not xs:
                continue
            ys = [fn(d["timestamp"].iloc[i]) for i in xs]
            col = SELL if z.get("role") == "RESISTANCE" else BUY
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=col, width=2), showlegend=False, hoverinfo="skip"))
            anc = ", ".join(f"{pd.Timestamp(a[0]):%d %b %H:%M}" for a in (z.get("anchors") or [])[:4])
            marks.append({"y": ys[-1], "text": f"trendline {ys[-1]:,.0f} ({z.get('touches')} touches: {anc})", "color": col})
        # I रेघ
        I = (R.get("impulse") or {}).get("I")
        if I and pd.Timestamp(I["from_ts"]) >= t0 - pd.Timedelta(days=0):
            xa, xb = xi(I["from_ts"]), xi(I["to_ts"])
            fig.add_trace(go.Scatter(x=[xa, xb], y=[I["from"], I["to"]], mode="lines+markers", line=dict(color=IMP_COL, width=2, dash="dot"),
                                     marker=dict(size=8), showlegend=False, hoverinfo="skip"))
            marks.append({"y": I["from"], "text": f"I origin {I['from']:,.1f} ({pd.Timestamp(I['from_ts']):%d %b %H:%M})", "color": IMP_COL})
            marks.append({"y": I["to"], "text": f"I शेवट {I['to']:,.1f} ({pd.Timestamp(I['to_ts']):%d %b %H:%M})", "color": IMP_COL})
        # pattern labels (preferred ठळक, alternate फिकट) — pivot वर
        for it in _lab_items(R, tf, xi, d) + _lab_items(R, tf, xi, d, alt=True):
            up = it["y"] >= float(d["high"].iloc[it["x"]]) - 1e-6
            fig.add_annotation(x=it["x"], y=it["y"], text=f"<b>{it['text']}</b>" if not it["alt"] else f"({it['text']})", showarrow=True,
                               arrowhead=0, ay=-24 if up else 24, ax=0, font=dict(size=14 if not it["alt"] else 11,
                                                                                   color=LABEL_COL if not it["alt"] else ALT_COL))
        hyps = (R.get("pattern") or {}).get("hypotheses") or []
        if hyps:
            for x in hyps[0]["labels"]:
                marks.append({"y": x["price"], "text": f"{x['label']}{'?' if x.get('tentative') else ''} {x['price']:,.1f} "
                              f"({pd.Timestamp(x['ts']):%d %b %H:%M})", "color": LABEL_COL})
        # pattern lines (channel / triangle / flat पट्टा)
        for ln in (R.get("pattern") or {}).get("lines") or []:
            a = ln["a"]
            anchors = [a, ln.get("b")] + list(ln.get("parallel_to") or [])
            if any(x is not None and pd.Timestamp(x["ts"]) < t0 for x in anchors):
                continue                                                    # anchor खिडकीबाहेर ⇒ slope चुकेल; रेघ नाही (JSON मध्ये आहे)
            if ln.get("horizontal"):
                fig.add_shape(type="line", x0=xi(a["ts"]), x1=n - 1, y0=a["price"], y1=a["price"], line=dict(color=ALT_COL, width=1, dash="dot"))
                continue
            if ln.get("parallel_to"):
                p0, p1 = ln["parallel_to"]
                x0, x1 = xi(p0["ts"]), xi(p1["ts"])
                if x1 == x0:
                    continue
                sl = (p1["price"] - p0["price"]) / (x1 - x0)
                xa = xi(a["ts"])
                fig.add_shape(type="line", x0=xa, x1=n - 1, y0=a["price"], y1=a["price"] + sl * (n - 1 - xa),
                              line=dict(color=ALT_COL, width=1, dash="dot"))
                continue
            b = ln["b"]
            x0, x1 = xi(a["ts"]), xi(b["ts"])
            if x1 == x0:
                continue
            sl = (b["price"] - a["price"]) / (x1 - x0)
            fig.add_shape(type="line", x0=x0, x1=n - 1, y0=a["price"], y1=a["price"] + sl * (n - 1 - x0),
                          line=dict(color=ALT_COL, width=1, dash="dot"))
        # price failure candle + SL / target (setup असेल तरच)
        pf = R.get("price_failure") or {}
        if pf.get("ok") and tf == "15M":
            fig.add_annotation(x=n - 1, y=float(d["high"].iloc[-1]) if R["side"] < 0 else float(d["low"].iloc[-1]), text="⚑ price failure",
                               showarrow=True, ay=-30 if R["side"] < 0 else 30, ax=0, font=dict(color="#ff9800", size=12))
        rk = R.get("risk") or {}
        if (R.get("decision") or {}).get("outcome") == "setup" and rk:
            for k, col, nm in (("sl", "#ef5350", "SL"), ("target", "#00e676", "target")):
                fig.add_shape(type="line", x0=max(0, n - 25), x1=n - 1, y0=rk[k], y1=rk[k], line=dict(color=col, width=2, dash="dash"))
                marks.append({"y": rk[k], "text": f"{nm} {rk[k]:,.1f}", "color": col, "bold": True})
    else:
        # W / D: confirmed swings (HH / HL / LH / LL), protected
        key = "weekly" if tf == "W" else "daily"
        h = (R.get("htf_state") or {}).get(key) or {}
        for p in h.get("swings") or []:
            t = pd.Timestamp(p["ts"])
            if t < t0:
                continue
            fig.add_annotation(x=xi(t), y=p["price"], text=p.get("label") or p["kind"], showarrow=True, arrowhead=0,
                               ay=-20 if p["kind"] == "H" else 20, ax=0, font=dict(size=11, color="#b0bec5"))
        pr = h.get("protected")
        if pr:
            marks.append({"y": pr["price"], "text": f"protected {pr['kind']} {pr['price']:,.0f}", "color": "#ce93d8", "bold": True})
    fig.add_annotation(x=0.5, y=0.6, xref="paper", yref="paper", text={"W": "WEEKLY", "D": "DAILY"}.get(tf, tf), showarrow=False,
                       font=dict(size=150, color="rgba(255,255,255,0.08)"), xanchor="center", yanchor="middle")   # thumbnail मध्येही TF
    vser = R.get("volume_series") if tf == "15M" else None
    blocked = ("top-left",) if box else ()
    if vser:
        blocked = ("top-left", "bottom-left", "bottom-right")              # खाली volume panel
    rows = BC.level_marks(fig, n - 1, marks, lo, hi, d=d, blocked=blocked)
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=checklist_box(R, compact=tf not in ("15M",)), font=dict(size=10 if tf == "15M" else 9),
                           bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    del rows
    BC._finish(fig, d, lo, hi, fmt="%d %b" if tf in ("W", "D") else "%d %b %H:%M")
    if vser:
        volume_panel(fig, d, vser)
    return fig


def volume_panel(fig, d, vser):
    """15M खाली futures volume panel (spot bars शी वेळेने जुळवलेला). Rollover दिवसाचे bars नारिंगी (तुलनेत नाहीत)."""
    import plotly.graph_objects as go
    m = {pd.Timestamp(x["ts"]): x for x in vser}
    xs, ys, cols = [], [], []
    for i, t in enumerate(pd.to_datetime(d["timestamp"])):
        x = m.get(t)
        if x is None or x["v"] is None:
            continue
        xs.append(i)
        ys.append(x["v"])
        cols.append("#ff9800" if x["roll"] else "#5c6bc0")
    fig.update_layout(yaxis=dict(domain=[0.24, 1.0]), yaxis2=dict(domain=[0.0, 0.18], anchor="x", side="right", showgrid=False,
                                                                     tickformat="~s", title=dict(text="fut vol", font=dict(size=10))))
    if xs:
        fig.add_trace(go.Bar(x=xs, y=ys, marker_color=cols, yaxis="y2", showlegend=False, hoverinfo="skip"))
    if any(c == "#ff9800" for c in cols):
        fig.add_annotation(x=0.005, y=0.19, xref="paper", yref="paper", xanchor="left", yanchor="top", showarrow=False,
                           text="🟧 rollover दिवस (तुलनेत नाही)", font=dict(size=10, color="#ff9800"))
    if not xs:
        fig.add_annotation(x=0.5, y=0.09, xref="paper", yref="paper", showarrow=False, text="futures volume data नाही",
                           font=dict(size=11, color="#90a4ae"))


def png(fig):
    return fig.to_image(format="png", scale=1)


def charts(fr, R, ms_swings=None, title_dt=None):
    """चारही charts ⇒ {tf: png bytes}. fr = reader.frames(...)[1] (बंद bars)."""
    if not R.get("decision_bar"):
        return {}                                                           # data अपुरा ⇒ chart नाही
    start = window_start(R, ms_swings)
    m15_ts = pd.to_datetime(fr["15M"]["timestamp"]).to_numpy(dtype="datetime64[ns]")
    d = (R.get("decision") or {})
    head = f"{OUTCOME_MR.get(d.get('outcome'), '')}"
    out = {}
    for tf in ("15M", "1H", "D", "W"):
        f = window(fr[tf], tf, start)
        if not len(f):
            continue
        BC.assert_upto(f, R["asof"], f"annotation {tf}")
        t = f"🧭 ANNOTATION · NIFTY {tf} · decision bar {pd.Timestamp(R['decision_bar']):%d %b %Y %H:%M} · code: {head}"
        out[tf] = png(figure(f, tf, R, t, m15_ts=m15_ts, box=tf in ("15M", "1H")))
    return out


def _short(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def caption(n, total, R):
    """Prompt §5 चा caption: ≤ 8 ओळी, ≤ 1024 (UTF-16), साधी मराठी, code keys नाहीत."""
    if not R.get("decision_bar"):
        return f"🧭 ANNOTATION CHECK {n}/{total} · data अपुरा\nReply: ✔ बरोबर · ✘ कारण"
    dbar = pd.Timestamp(R["decision_bar"])
    htf = R.get("htf_state") or {}
    dn = {1: "वर", -1: "खाली", 0: "range"}
    I = (R.get("impulse") or {}).get("I")
    hyps = (R.get("pattern") or {}).get("hypotheses") or []
    pat = "ओळखता येत नाही"
    if hyps:
        h = hyps[0]
        from .reader import PAT_MR
        pat = f"{PAT_MR.get(h['pattern'], 'pattern')} ({' '.join(x['label'] for x in h['labels'])}) — {(R.get('complete') or {}).get('mr', '')}"
    zs = [f"{'seller' if z['side'] == 'sell' else 'buyer'} {z['low']:,.0f}–{z['high']:,.0f}" for z in (R.get("area") or {}).get("touched") or []][:2]
    tls = chart_trendlines(R)
    if tls:
        zs.append(f"{len(tls)} trendline")
    items = R.get("items") or {}
    n_ok = sum(1 for it in items.values() if it["status"] == "✔")
    d = R.get("decision") or {}
    g = d.get("gate")
    gtxt = f" · पहिला gate ✘: {g} {items[g]['name']}" if g in items else ""
    dec = {"setup": f"setup ({'bear' if R['side'] < 0 else 'bull'})", "wait": "थांबा", "no_trade": "trade नाही"}.get(d.get("outcome"), "—")
    dec += f" — {_short(d.get('what'), 70)}"
    tr = (R.get("step0") or {}).get("parent_dir", 0)
    lines = [f"🧭 ANNOTATION CHECK {n}/{total} · {dbar:%d %b %Y} · {dbar:%H:%M}",
             f"📈 Trend: W {dn.get((htf.get('weekly') or {}).get('dir', 0))} / D {dn.get((htf.get('daily') or {}).get('dir', 0))} / "
             f"1H {dn.get(tr)} / 15M {'correction' if I else '—'}",
             "🌊 Impulse: " + (f"{I['from']:,.1f} → {I['to']:,.1f}" if I else "नाही"),
             f"🌀 Pattern: {_short(pat, 110)}",
             f"🧱 Zones / trendline: {_short(' · '.join(zs) or '—', 140)}",
             f"✅ Checklist: {n_ok}/12{gtxt}",
             f"🎯 Code चा निर्णय: {_short(dec, 140)}",
             "Reply: ✔ बरोबर · ✘ कारण"]
    cap = "\n".join(lines)
    while len(cap.encode("utf-16-le")) // 2 > 1024:
        cap = cap[:-2]
    return cap


def pdf_page(pngs, title):
    """एक PDF पान (PIL image): शीर्षक + 2×2 charts (15M, 1H / D, W)."""
    from PIL import Image, ImageDraw
    ims = [Image.open(io.BytesIO(pngs[tf])).convert("RGB") for tf in ("15M", "1H", "D", "W") if tf in pngs]
    if not ims:
        return None
    w, h = ims[0].size
    page = Image.new("RGB", (2 * w, 2 * h + 60), "#0e1117")
    ascii_title = "".join(ch for ch in title if ord(ch) < 128)              # PIL default font ला देवनागरी / emoji नाही (charts मध्ये आहे)
    ImageDraw.Draw(page).text((20, 20), " ".join(ascii_title.split()), fill="#ffffff")
    for k, im in enumerate(ims):
        page.paste(im.resize((w, h)), ((k % 2) * w, 60 + (k // 2) * h))
    return page
