"""review7/charts.py — Telegram ला जाणाऱ्या प्रत्येक chart साठी एकच function `telegram_charts(C, D, t)`: सातही-थर chart (decision2.charts7,
फक्त वाचन) + B1 बाण (✅ भरीव / 🟡 पोकळ, लहान लेबल) + B2 "पुढे पाहायचे" areas + सगळ्या बाणांचा / योजनेचा तक्ता + caption (≤ 1024).
Shadow: निर्णय / order नाही."""
import numpy as np
import pandas as pd

import instruments as INS
from decision2 import charts7 as D7
from pivots import charts as PC

from . import method as RM
from . import settings as RS

MAX_CAPTION = 1024


def u16(x):
    """Telegram caption लांबी = UTF-16 units (emoji = 2)."""
    return len(x.encode("utf-16-le")) // 2
TF_MR = {"15M": "15M", "1H": "1H"}


def _window_start(C, t, tf):
    """chart window ची पहिली 15M bar (charts7 सारखीच खिडकी)."""
    m = C.m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    frame = m if tf == "15M" else PC.agg_1h(m)
    d = PC.window(frame, tf, asof, sessions=D7.SESSIONS[tf]).reset_index(drop=True)
    t0 = pd.Timestamp(pd.to_datetime(d["timestamp"]).iloc[0])
    return int(np.searchsorted(C.ts.to_numpy(dtype="datetime64[ns]"), np.datetime64(t0, "ns"))), d


def label(mk):
    """लहान लेबल: trend · area (★) · pattern · ④ · ⑥ · engine."""
    a = mk["area"]
    ar = ("Z" + ("★" * a["stars"]) + ("·self" if a["self"] else "")) if a["kind"] == "zone" else "रेघ"
    c4 = "+".join({"shrink": "sh", "momentum": "mom", "RSI": "rsi"}[x] for x in mk["c4"]) or "—"
    pat = (mk["pattern"] or "—").split("/")[0]
    return (f"D{mk['deg']}{'↓' if mk['dir'] < 0 else '↑'} · {ar} · {pat} · ④{c4} · ⑥{'✓' if mk['c6'] else '✗'} · "
            f"engine: {mk['engine']}")


def overlay(fig, C, t, tf, marks, pl):
    b0, d = _window_start(C, t, tf)
    n = len(d)
    tsx = pd.to_datetime(d["timestamp"]).to_numpy(dtype="datetime64[ns]")

    def X(b):
        if b is None or b < b0 or b > t:
            return None
        return int(np.searchsorted(tsx, np.datetime64(pd.Timestamp(C.ts.iloc[b]), "ns"), side="right") - 1)
    A = C.A
    lo, hi = float(d["low"].min()), float(d["high"].max())
    span = (hi - lo) or 1.0
    shown = [(i, mk) for i, mk in enumerate(marks, 1) if X(mk["bar"]) is not None]       # क्रमांक = तक्त्यातलाच
    for i, mk in shown:
        x = X(mk["bar"])
        dn = mk["dir"] < 0
        y = float(A["h"][mk["bar"]]) + 0.02 * span if dn else float(A["l"][mk["bar"]]) - 0.02 * span
        full = mk["type"] == "✅"
        col = ("#ef5350" if dn else "#26a69a") if full else "#ffd54f"
        sym = ("triangle-down" if dn else "triangle-up") + ("" if full else "-open")
        fig.add_scatter(x=[x], y=[y], mode="markers", marker=dict(symbol=sym, size=16, color=col, line=dict(color=col, width=2)),
                        showlegend=False, hoverinfo="skip")
        txt = f"{mk['type']}{i} {label(mk)}" if tf == "15M" else f"{mk['type']}{i}"
        fig.add_annotation(x=x, y=y, text=txt, showarrow=False, yshift=16 if dn else -16, font=dict(size=9 if tf == "15M" else 10, color=col),
                           bgcolor="rgba(14,17,23,0.75)")
        if full and tf == "15M" and mk.get("sl") is not None:
            x1 = min(x + 6, n - 1)
            for yy, cc in ((mk["entry"], "#90caf9"), (mk["sl"], "#ef9a9a"), (mk.get("target"), "#a5d6a7")):
                if yy is not None and lo - span < yy < hi + span:
                    fig.add_shape(type="line", x0=x, x1=x1, y0=yy, y1=yy, line=dict(color=cc, width=1.5, dash="dot"))
    x0 = max(int(n * 0.86), 0)
    for k, it in enumerate(pl.get("items") or []):
        if not (lo - span < it["top"] and it["bot"] < hi + span):
            continue
        col = "#ef5350" if it["dir"] < 0 else "#26a69a"
        fig.add_shape(type="rect", x0=x0, x1=n - 1, y0=it["bot"], y1=it["top"], line=dict(color=col, width=2.5, dash="dash"),
                      fillcolor="rgba(255,213,79,0.10)")
        fig.add_annotation(x=x0, y=it["top"] if it["dir"] < 0 else it["bot"], xanchor="left", showarrow=False,
                           yshift=10 if it["dir"] < 0 else -10, text=f"पुढे पाहायचे {k + 1}: {it['side']}", font=dict(size=10, color="#ffd54f"))
    return len(shown)


def rows(C, marks, pl):
    out = []
    for i, mk in enumerate(marks, 1):
        a = mk["area"]
        out.append({"#": f"{mk['type']}{i}", "वेळ": pd.Timestamp(mk["ts"]).strftime("%d %b %H:%M"), "दिशा": mk["side"],
                    "area": f"{a['kind']} {a['id']} {a['bot']:,.0f}–{a['top']:,.0f}" + (f" ★{a['stars']}" if a["kind"] == "zone" else "")
                    + (" self" if a["self"] else ""),
                    "trend": f"D{mk['deg']} {mk['trend']}", "pattern": mk["pattern"] or "—", "④": "+".join(mk["c4"]) or "—",
                    "⑤": "हो" if mk["c5"] else "—", "⑥": "✓" if mk["c6"] else "✗",
                    "entry / SL / target / R:R": "—" if mk["type"] != "✅" else f"{mk['entry']:,.0f} / {mk['sl']:,.0f} / "
                    f"{'—' if mk.get('target') is None else format(mk['target'], ',.0f')} / {mk.get('rr') or '—'}",
                    "engine": f"{mk['engine']}" + (f" · {mk['engine_why']}" if mk.get("engine_why") else ""),
                    "स्थिती": "" if mk["final"] else "चाचणी चालू"})
    for k, it in enumerate(pl.get("items") or [], 1):
        out.append({"#": f"पुढे {k}", "वेळ": "पुढचा दिवस", "दिशा": it["side"], "area": f"{it.get('kind')} {it.get('id', '')} "
                    f"{it['bot']:,.0f}–{it['top']:,.0f}", "trend": f"D{pl['deg']} {pl['trend']}", "pattern": "—", "④": "प्रतिक्रिया",
                    "⑤": "—", "⑥": "हवी", "entry / SL / target / R:R": f"{it.get('entry', it['bot']):,.0f} / {it['sl']:,.0f} / "
                    f"{'—' if it.get('target') is None else format(it['target'], ',.0f')} / {it.get('rr') or '—'}",
                    "engine": "—", "स्थिती": pl.get("invalid") or ""})
    return out


def table_png(rws, title):
    import plotly.graph_objects as go
    head = list(rws[0].keys()) if rws else ["—"]
    fig = go.Figure(go.Table(columnwidth=[50, 80, 60, 170, 70, 120, 80, 30, 30, 170, 220, 120],
                             header=dict(values=head, fill_color="#263238", font=dict(color="white", size=12)),
                             cells=dict(values=[[r.get(c, "—") for r in rws] for c in head] if rws else [["बाण नाहीत"]], height=26,
                                        fill_color="#0e1117", font=dict(color="white", size=11), align="left")))
    fig.update_layout(title=title, template="plotly_dark", width=1800, height=max(400, 120 + 28 * (len(rws) + 1)), paper_bgcolor="#0e1117",
                      margin=dict(l=10, r=10, t=50, b=10))
    return PC.png(fig)


def caption(head, marks15, n_all, pl, first_no=1):
    """≤ 1024: शीर्षक · B2 योजना (3–5 ओळी) · 15M खिडकीतले बाण (वेळ, दिशा, कारण, engine) · बाकी तक्त्यात."""
    tr = f"D{pl['deg']} {pl['trend']}" if pl.get("deg") else "trend अज्ञात"
    lines = [head, f"पुढचा दिवस: {tr} · regime {pl.get('regime')} · {pl.get('state')}"]
    for k, it in enumerate((pl.get("items") or [])[:3], 1):
        lines.append(f"• {it['side']} {it['bot']:,.0f}–{it['top']:,.0f}: प्रतिक्रिया + commitment ⇒ SL {it['sl']:,.0f} · लक्ष्य "
                     f"{'—' if it.get('target') is None else format(it['target'], ',.0f')} · R:R {it.get('rr') or '—'}")
    if not pl.get("items"):
        lines.append("• trend / area नाही ⇒ वाट")
    if pl.get("invalid"):
        lines.append(f"रद्द: {pl['invalid']}")
    lines.append(f"मागे (15M खिडकी): ✅ {sum(1 for m in marks15 if m['type'] == '✅')} · 🟡 {sum(1 for m in marks15 if m['type'] == '🟡')}"
                 f" — सगळे {n_all} तक्त्यात")
    for i, mk in enumerate(marks15, first_no):
        a = mk["area"]
        why = f"{mk['side']} · {a['kind']} {a['bot']:,.0f}" + (f"★{a['stars']}" if a["kind"] == "zone" else "") + \
            f" · ④{'+'.join(mk['c4']) or '—'} · ⑥{'✓' if mk['c6'] else '✗'}"
        lines.append(f"{mk['type']}{i} {pd.Timestamp(mk['ts']):%d %b %H:%M} {why} · engine {mk['engine']}")
    tail = "\n…(बाकी तक्त्यात)"
    cut = False
    while u16("\n".join(lines) + (tail if cut else "")) > MAX_CAPTION and len(lines) > 4:
        lines.pop()
        cut = True
    out = "\n".join(lines) + (tail if cut else "")
    while u16(out) > MAX_CAPTION:
        out = out[:-1]
    return out


def telegram_charts(C, D, t, head=None, s=None, scan_start=None, cache=None):
    """एकच function (review + daily): रिटर्न ({"15M": png, "1H": png, "table": png}, caption, marks, plan).
    scan_start = run ची ठरलेली सुरुवात (सगळ्या charts साठी तीच ⇒ एका चाचणीला सगळीकडे तोच बाण); marks = 1H खिडकीतले."""
    s = s or RS.load()
    dec = D[t]
    w0, _ = _window_start(C, t, "1H")
    allm = RM.scan(C, range(min(w0, w0 if scan_start is None else scan_start), t + 1), D, s, cache)
    marks = [m for m in allm if m["bar"] >= w0]
    pl = RM.plan(C, t, s)
    asof = pd.Timestamp(C.m15["bar_end"].iloc[t])
    title = "🧭 सातही थर + मागे / पुढे · " + INS.label() + " {tf} · {d:%d %b %Y %H:%M}"
    pngs = {}
    w15, _ = _window_start(C, t, "15M")
    for tf in ("15M", "1H"):
        fig = D7.figure(C, dec, t, tf, title.format(tf=tf, d=asof))
        overlay(fig, C, t, tf, marks, pl)
        pngs[tf] = PC.png(fig)
    pngs["table"] = table_png(rows(C, marks, pl), f"मागे कुठे trade शक्य होता (1H खिडकी) + पुढचा दिवस · {asof:%d %b %Y %H:%M}")
    marks15 = [m for m in marks if m["bar"] >= w15]
    first_no = len(marks) - len(marks15) + 1
    cap = caption(head or f"🧭 मागे / पुढे · {asof:%d %b %Y %H:%M}", marks15, len(marks), pl, first_no)
    return pngs, cap, marks, pl
