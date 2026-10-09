"""legs2/charts2.py — 🧭 LEG CHECK v2.1 charts (थर 2 §8): 15M (D1 legs + D0 ठिपके + RVOL panel, I कंस + गुणवत्ता, K फिका,
CHoCH strict ⚑, cisd ◇, sweep_of_I_end ~), 1H (D2 legs), Daily (D3 legs, फक्त R). Box: I, K (अवस्था, खोली मुख्य / दुय्यम, वेळ,
volume). Chart मजकूर इंग्रजी / मराठी; caption मराठी, code keys नाहीत."""
import numpy as np
import pandas as pd

from pivots import charts as PC
from swings2 import engine as SE

from . import charts as LC
from . import ik2 as LI
from . import measure2 as M2

STATE_MR = {LI.ST_NONE: "I नाही", LI.ST_IMP: "impulse चालू", LI.ST_KSTART: "K सुरू झाला असावा", LI.ST_K: "K चालू"}


def _fmt(x, p=0):
    return "—" if x is None else f"{x:,.{p}f}"


def ik_line(st, nm):
    I = st.get("I")
    if not I:
        return f"<b>{nm}</b>: I नाही ({st.get('why', '')})"
    k = st.get("K") or {}
    fl = st.get("flags") or {}
    q = [I["quality"]] + (["climax"] if I["climax"] else []) + (["SOT_trend"] if I["SOT_trend"] else [])
    mode = " · range_alt" if I["mode"] == LI.MODE_RANGE else ""
    tags = [t for t, on in (("origin_bounded", I["origin_bounded"]), ("I_weak_basis", I["I_weak_basis"])) if on]
    s = (f"<b>{nm}</b>: I {'वर' if I['dir'] > 0 else 'खाली'} {_fmt(I['origin']['price'])} → {_fmt(I['end']['price'])} "
         f"({I['size_sigma']}σ, {I['legs']} legs, {'/'.join(q)}{mode}{', ' + ', '.join(tags) if tags else ''}) · {STATE_MR[st['state']]}")
    if k:
        s += (f"<br>&nbsp;&nbsp;K: खोली मुख्य {_fmt(k.get('depth_main'), 2)} · दुय्यम {_fmt(k.get('depth_secondary'), 2)} · "
              f"वेळ ×{_fmt(k.get('time_main'), 2)} · C K/I {_fmt(k.get('C_K'), 2)}/{_fmt(k.get('C_I'), 2)} · "
              f"RVOL K/I {_fmt(k.get('rvol_K'), 2)}/{_fmt(k.get('rvol_I'), 2)}"
              + (" · quiet" if fl.get("pullback_quiet") else "") + (" · heavy" if fl.get("pullback_heavy") else ""))
        ch = fl.get("choch_strict")
        extra = []
        if ch:
            extra.append(f"CHoCH strict ({ch['read']})")
        if fl.get("cisd") is not None:
            extra.append("cisd ✓")
        if fl.get("last_leg_start_broken") is not None:
            extra.append("last_leg_start_broken ✓")
        if k.get("counter_impulse"):
            extra.append(f"counter-impulse {len(k['counter_impulse'])}")
        if extra:
            s += "<br>&nbsp;&nbsp;" + " · ".join(extra)
    return s


def _marks(fig, d, st, m15, t0):
    """⚑ CHoCH strict, ◇ cisd, ~ sweep_of_I_end (15M)."""
    import plotly.graph_objects as go
    fl = st.get("flags") or {}
    xs, ys, txt = [], [], []

    def put(bar, y, s):
        ts = pd.Timestamp(m15["timestamp"].iloc[bar])
        if ts < t0:
            return
        x = PC._x_of(d, ts)
        if x is not None:
            xs.append(x)
            ys.append(y)
            txt.append(s)
    ch = fl.get("choch_strict")
    if ch:
        put(ch["bar"], float(m15["close"].iloc[ch["bar"]]), "⚑" + (" disp" if ch["disp"] else ""))
    if fl.get("cisd") is not None:
        put(fl["cisd"], float(m15["close"].iloc[fl["cisd"]]), "◇ cisd")
    if xs:
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="text", text=txt, textfont=dict(size=14, color="#ffd54f"), showlegend=False,
                                 hoverinfo="skip"), row=1, col=1)
    I = st.get("I")
    for p in (I or {}).get("sweeps", []):
        fig.add_annotation(x=len(d) - 1, y=p, text=f"~ sweep I_end {p:,.0f}", showarrow=False, xanchor="right",
                           font=dict(size=10, color="#90a4ae"), row=1, col=1)


def charts(lg, trk, t):
    """bar t (बंद) चे तीन charts ⇒ ({tf: png}, {1: state, 2: state})."""
    res = lg["res"]
    m15 = res["m15"]
    asof = pd.Timestamp(m15["bar_end"].iloc[t])
    m = m15.iloc[:t + 1]
    sts = {d: trk[d].state(t) for d in trk}
    box = "<br>".join([ik_line(sts[1], "15M (D1)"), ik_line(sts[2], "1H (D2)")])
    title = "🧭 LEG CHECK v2 · NIFTY {tf} · {d:%d %b %Y %H:%M} · {deg}"
    w15 = PC.window(m, "15M", asof)
    off = len(m) - len(w15)
    out = {}
    cur1 = _cur(lg, 1, asof, m15)
    fig = LC.figure(w15, "15M", M2.known(lg, 1, asof), cur1, SE.known(res, 0, asof), sts[1],
                    title.format(tf="15M", d=pd.Timestamp(m15["timestamp"].iloc[t]), deg="D1 legs + D0 ठिपके"),
                    rv=lg["rv"][off:t + 1], bad=lg["bad"][off:t + 1], box=box)
    _marks(fig, w15.reset_index(drop=True), sts[1], m15, pd.to_datetime(w15["timestamp"]).min())
    out["15M"] = PC.png(fig)
    h1 = PC.window(PC.agg_1h(m), "1H", asof)
    out["1H"] = PC.png(LC.figure(h1, "1H", M2.known(lg, 2, asof), _cur(lg, 2, asof, m15), None, sts[2],
                                 title.format(tf="1H", d=pd.Timestamp(m15["timestamp"].iloc[t]), deg="D2 legs")))
    daily = PC.daily_from_15m(m, asof)
    out["D"] = PC.png(LC.figure(daily, "D", M2.known(lg, 3, asof), None, None, None,
                                title.format(tf="Daily", d=pd.Timestamp(m15["timestamp"].iloc[t]), deg="D3 legs (फक्त R)")))
    return out, sts


def _cur(lg, d, asof, m15):
    L = M2.current(lg, d, asof)
    if L is not None:
        L["end_ts"] = pd.Timestamp(m15["timestamp"].iloc[L["end_bar"]])
    return L


def caption(n, total, asof, sts, why=None):
    """≤ 8 ओळी, ≤ 1024 (UTF-16), code keys नाहीत."""
    def imp(st):
        I = st.get("I")
        if not I:
            return "नाही"
        return (f"{'वर' if I['dir'] > 0 else 'खाली'} {I['origin']['price']:,.0f} → {I['end']['price']:,.0f}"
                + (" (range मोड)" if I["mode"] == LI.MODE_RANGE else "") + (" · spike" if I["quality"] == "spike" else " · channel"))

    def kk(st):
        if not st.get("I"):
            return "—"
        k = st.get("K") or {}
        s = STATE_MR[st["state"]]
        if k.get("depth_main") is not None:
            s += f" · खोली {k['depth_main']:.2f}"
        fl = st.get("flags") or {}
        if fl.get("pullback_quiet"):
            s += " · शांत volume"
        if fl.get("pullback_heavy"):
            s += " · जड volume"
        if fl.get("choch_strict"):
            s += " · " + ("reversal उमेदवार" if fl["choch_strict"]["disp"] else "खोल pullback")
        return s
    head = f"🧭 LEG CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर")
    lines = [head, f"15M impulse: {imp(sts[1])}", f"15M correction: {kk(sts[1])}", f"1H impulse: {imp(sts[2])}",
             f"1H correction: {kk(sts[2])}", "Reply: ✔ बरोबर · ✘ कोणता leg / I / K चुकला"]
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)


def moments(trk, bars, k):
    """दिवसातले कमाल k क्षण: I बदल / रद्द, CHoCH strict, cisd (D1; थर 2 §8). शेवटची candle (दिवस-अखेर) वगळून."""
    bs = set(bars[:-1])
    ev = []
    for e in trk[1].log:
        if e["bar"] in bs and (e["event"].startswith("I") or e["event"].startswith("range_alt")):
            ev.append((0 if "रद्द" in e["event"] else 1, e["bar"], e["event"]))
    prev = {}
    for b in bars[:-1]:
        st = trk[1].state(b)
        fl = st.get("flags") or {}
        ch = fl.get("choch_strict")
        if ch and ch["bar"] == b:
            ev.append((0, b, "CHoCH strict"))
        if fl.get("cisd") == b and prev.get("cisd") != b:
            ev.append((2, b, "cisd"))
        prev = fl
    ev.sort()
    out, seen = [], set()
    for _, b, why in ev:
        if b in seen:
            continue
        seen.add(b)
        out.append((b, why))
        if len(out) >= k:
            break
    return sorted(out)


def rows(lg, trk, t0, t1):
    """मोजमाप (वर्णन; थर 2 §7): labels वाटप, C वितरण प्रबळ vs परतावा, गुणवत्ता, gap / NA / unreliable, I बदल / रद्द, K अवस्था."""
    out = []
    for d in (1, 2):
        legs = [L for L in lg["legs"][d] if t0 <= L["b"].confirm_bar <= t1]
        lab = {}
        for L in legs:
            lab[L["label"]] = lab.get(L["label"], 0) + 1
        cd = [L["C"] for L in legs if L["role"] == "प्रबळ" and L.get("C") is not None]
        cr = [L["C"] for L in legs if L["role"] == "परतावा" and L.get("C") is not None]
        log = [e for e in trk[d].log if t0 <= e["bar"] <= t1]
        sts = [trk[d].state(t)["state"] for t in range(t0, t1 + 1, 4)]
        out.append({"degree": f"D{d}", "legs": len(legs), "labels": ", ".join(f"{k}:{v}" for k, v in sorted(lab.items(), key=str)),
                    "C प्रबळ median": round(float(np.median(cd)), 2) if cd else "—",
                    "C परतावा median": round(float(np.median(cr)), 2) if cr else "—",
                    "C NA": sum(bool(L.get("C_na")) for L in legs), "gap legs": sum(L["gap_in_leg"] for L in legs),
                    "V तटस्थ (data)": sum(L.get("v_why") is not None for L in legs),
                    "I सापडला": sum(e["event"].startswith("I सापडला") for e in log),
                    "I_end सरकला": sum(e["event"] == "I_end सरकला" for e in log),
                    "sweep_of_I_end": sum(e["event"] == "sweep_of_I_end" for e in log),
                    "रद्द (origin)": sum(e["event"] == "I रद्द: I_origin real break" for e in log),
                    "रद्द (reversal)": sum(e["event"] == "I रद्द: थर 1 reversal (I-विरुद्ध)" for e in log),
                    "अवस्था %": ", ".join(f"{STATE_MR[s]}:{round(100 * sts.count(s) / len(sts))}" for s in sorted(set(sts))) if sts else "—"})
    return out


def register_rows():
    from . import settings2 as LS
    return [{"आकडा": k, "default": str(v[0]), "पर्याय": str(v[1]), "वर्ग": v[2], "स्रोत": v[3]} for k, v in LS.REGISTER.items()]
