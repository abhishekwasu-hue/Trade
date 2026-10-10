"""zones2/charts.py — 🧭 ZONE CHECK (थर 4 §9): 15M (सगळे zones), 1H (D2+), Daily (D3+). पट्टे: seller लाल / buyer हिरवा / flip
पट्टेदार (तुटक कडा) / pending तुटक / breaker ◆ / self फिके-राखाडी; लेबल (degree, flags, ★, touch_score); box: बाजू, K area, confluence,
पुढचे / उलट, momentum (re-emitted)."""
import pandas as pd

import instruments as INS
from backtest_review import charts as BC
from pivots import charts as PC

from . import engine as ZE

RED, GREEN, GREY = "rgba(239,83,80,{a})", "rgba(38,166,154,{a})", "rgba(144,164,174,{a})"


def label(z):
    fl = z["flags"]
    f = "".join(k for k in ("c", "d", "e") if fl.get(k)) + ("k" if z["k"] else "")
    st = {"flipped": " flip", "dead": " मेला"}.get(z["status"], "") + (" pending" if z["pending"] else "") + \
        (" accept" if z["accept"] else "") + (" ◆" if z["breaker"] else "")
    return f"D{z['degree'] or '-'} {f or '-'} {'★' * z['stars']} ts{z['touch_score']:+d}{st}"


def figure(frame, tf, zones, title, i_end_bar=None, side=None, box=None, min_deg=0):
    d = frame.reset_index(drop=True)
    n = len(d)
    fig = BC._base(d, title)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    for z in zones:
        if (z["degree"] or 0) < min_deg and not z["k"]:
            continue
        if z["top"] < lo - (hi - lo) or z["bottom"] > hi + (hi - lo):
            continue
        self_ = i_end_bar is not None and z["pivot_bar"] is not None and z["pivot_bar"] > i_end_bar
        trade = side is not None and z["role"] == side and not self_
        col = GREY if (self_ or z["status"] == "dead") else (RED if z["role"] == ZE.SELLER else GREEN)
        dash = "dash" if (z["pending"] or z["status"] == "flipped") else "solid"
        fig.add_shape(type="rect", x0=0, x1=n - 1, y0=z["bottom"], y1=z["top"], fillcolor=col.format(a=0.22 if trade else 0.10),
                      line=dict(color=col.format(a=0.9), width=2 if trade else 1, dash=dash), layer="below")
        fig.add_annotation(x=n - 1, y=z["top"], text=label(z), showarrow=False, xanchor="right", yanchor="bottom",
                           font=dict(size=9, color=col.format(a=1.0)))
    if box:
        fig.add_annotation(x=0.005, y=0.995, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                           text=box, font=dict(size=10), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)
    fig.add_annotation(x=0.5, y=0.55, xref="paper", yref="paper", text=tf, showarrow=False, font=dict(size=140, color="rgba(255,255,255,0.07)"))
    BC._finish(fig, d, lo, hi, fmt="%d %b" if tf == "D" else "%d %b %H:%M")
    return fig


def box_text(r, zmap):
    ka = r["k_area"]
    m = r.get("momentum")
    nxt = ", ".join(f"{zmap[i]['bottom']:,.0f}–{zmap[i]['top']:,.0f} {'★' * zmap[i]['stars']}" for i in r["next"] if i in zmap) or "—"
    opp = ", ".join(f"{zmap[i]['bottom']:,.0f}–{zmap[i]['top']:,.0f}" for i in r["opp"] if i in zmap) or "—"
    side = {ZE.SELLER: "seller (I खाली)", ZE.BUYER: "buyer (I वर)", "range_mode": "range (दोन्ही कडा)", None: "—"}[r["side"]]
    rows = [f"<b>बाजू</b>: {side}",
            f"<b>K area</b>: {ka['ans']}" + (f" · {ka.get('why')}" if ka.get("why") else "")
            + (f" · {'★' * ka['stars']}" if ka.get("stars") else "") + (" · htf_against" if ka.get("htf_against") else "")
            + (" · spring ✓" if ka.get("spring") else ""),
            f"confluence: {', '.join(r['confluence']) or '—'}", f"पुढचे: {nxt}", f"उलट: {opp}"]
    if m:
        rows.append(f"momentum (zone सह): <b>{m['verdict']}</b> · item 9 {m['items'][8]}")
    if r.get("open_noise"):
        rows.append("09:15–09:45 noise")
    return "<br>".join(rows)


def charts(Z, t, r, i_end_bar=None):
    m15 = Z.m15
    m = m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    zones = Z.snap[t]
    zmap = {z["id"]: z for z in zones}
    side = r["side"] if r["side"] in (ZE.SELLER, ZE.BUYER) else None
    title = "🧭 ZONE CHECK · " + INS.label() + " {tf} · {d:%d %b %Y %H:%M}"
    return {"15M": PC.png(figure(PC.window(m, "15M", asof), "15M", zones, title.format(tf="15M", d=asof), i_end_bar, side,
                                 box_text(r, zmap))),
            "1H": PC.png(figure(PC.window(PC.agg_1h(m), "1H", asof), "1H", zones, title.format(tf="1H", d=asof), i_end_bar, side,
                                min_deg=2)),
            "D": PC.png(figure(PC.daily_from_15m(m, asof), "D", zones, title.format(tf="Daily", d=asof), i_end_bar, side, min_deg=3))}


def caption(n, total, asof, r, zmap, why=None):
    ka = r["k_area"]
    side = {ZE.SELLER: "seller", ZE.BUYER: "buyer", "range_mode": "range", None: "—"}[r["side"]]
    m = r.get("momentum")
    lines = [f"🧭 ZONE CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर"),
             f"बाजू: {side}",
             f"K area मध्ये: {ka['ans']}" + (f" · {'★' * ka['stars']}" if ka.get("stars") else ""),
             f"confluence: {', '.join(r['confluence'][:4]) or '—'}",
             f"momentum: {m['verdict'] if m else '—'}",
             "Reply: ✔ बरोबर · ✘ सुटलेला / चुकीचा zone (किंमत)"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)


def moments(Z, L, bars, k):
    """पहिला स्पर्श (K area हो), flip, मेला, accept — दिवसात कमाल k (दिवस-अखेर वगळून)."""
    bs = set(bars[:-1])
    ev = [(e["bar"], e["type"]) for e in Z.events if e["bar"] in bs and e["type"] in ("flip", "मेला", "accept")]
    prev = None
    for t in bars[:-1]:
        a = (L.get(t) or {}).get("k_area", {}).get("ans", "NA")
        if a.startswith("हो") and (prev is None or not prev.startswith("हो")):
            ev.append((t, "K area मध्ये"))
        prev = a
    ev.sort()
    out, seen = [], set()
    for b, why in ev:
        if b in seen:
            continue
        seen.add(b)
        out.append((b, why))
        if len(out) >= k:
            break
    return out


def rows(Z, L, t0, t1):
    ev = [e for e in Z.events if t0 <= e["bar"] <= t1]
    cnt = {}
    for e in ev:
        cnt[e["type"]] = cnt.get(e["type"], 0) + 1
    ka = [L[t]["k_area"]["ans"] for t in L if t0 <= t <= t1]
    kn = [a for a in ka if a != "NA"]
    last = Z.snap.get(t1) or []
    stars = {}
    for z in last:
        stars[z["stars"]] = stars.get(z["stars"], 0) + 1
    return [{"zones (शेवटी)": len(last), "★ वाटप": ", ".join(f"{k}★:{v}" for k, v in sorted(stars.items())),
             "घटना": ", ".join(f"{k}:{v}" for k, v in sorted(cnt.items())),
             "K area हो %": round(100 * sum(a.startswith("हो") for a in kn) / len(kn)) if kn else "—",
             "हो (sweep) / (pending)": f"{sum(a == 'हो (sweep)' for a in kn)} / {sum(a == 'हो (pending)' for a in kn)}",
             "flags c/d/e (शेवटी)": "/".join(str(sum(bool(z['flags'][k]) for z in last)) for k in ("c", "d", "e"))}]


def register_rows():
    from . import settings as ZS
    return [{"आकडा": k, "default": str(v[0]), "पर्याय": str(v[1]), "वर्ग": v[2], "स्रोत": v[3]} for k, v in ZS.REGISTER.items()]
