"""vision_led/blind_test.py — चार MAP CHECK केसेसवर vision ची blind चाचणी (Abhi 2026-10-09). **Trade नाही, order नाही, नियम बदल नाही.**

Vision ला फक्त: चार स्वच्छ charts (Weekly, Daily, 1H, 15M — candles फक्त, decision bar च्या close वर कापलेले) + OHLC तक्ते (किंमती फक्त
तिथून). Code ची marking, नकाशाचं उत्तर, Abhi चं मत — काहीच नाही. System = सध्याचा playbook (vision_led/playbook.py) जसाच्या तसा +
12-मुद्दे checklist (Abhi, क्रमाने). उत्तर ठराविक JSON (प्रत्येक मुद्दा {क्रमांक, ✔ / ✘ / लागू नाही, पुरावा, bar वेळा}).
Vision च्या खुणा (labels, areas, trendline anchors — bar वेळ + high/low/open/close) code खऱ्या OHLC वरून काढतो (image वरून कधीच नाही)
आणि 1H / 15M (आणि W / D वर मुख्य) charts वर क्रमांक-खुणा + legend. निर्णय नियम code चा: 4, 5, 6, 9, 10, 12 पैकी एकही ✘ ⇒ trade नाही.
"""
import base64
import json

import numpy as np
import pandas as pd

from .playbook import PLAYBOOK

CASES = ("2026-09-22 15:00", "2026-09-28 14:15", "2018-02-16 09:30", "2021-11-15 13:00")
TFS = ("W", "D", "1H", "15M")
BARS = {"W": 80, "D": 120, "1H": 70, "15M": 100}                         # chart + OHLC तक्ता (शेवटचे इतके बंद bars)
GATING = (4, 5, 6, 9, 10, 12)                                          # यापैकी एकही ✘ ⇒ trade नाही (Abhi)
ITEM_MR = {1: "Weekly + Daily स्थिती", 2: "1H trend / protected swing", 3: "impulse खरा", 4: "pullback = correction", 5: "pattern",
           6: "pattern पूर्ण", 7: "area confluence", 8: "खोली", 9: "price failure", 10: "risk / R:R ≥ 3", 11: "संदर्भ",
           12: "पक्के नियम"}
STATUS = ("✔", "✘", "लागू नाही")
CIRC = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

CHECKLIST = """
BLIND TEST CHECKLIST (Abhi) — answer EVERY item, in this order, for the decision bar (the last closed 15M bar). Status is exactly one of
"✔", "✘", "लागू नाही". Give evidence and the bar times (as printed in the OHLC tables) you used. Write all free text in simple Marathi
(Devanagari); prices only from the OHLC tables (never read from the image).
1 Weekly + Daily: स्थिती (trend / correction / range), मोठे areas.
2 1H: trend, protected swing, शेवटचा impulse (कुठून कुठे, वेळ).
3 Impulse खरा: लांब, मोठ्या bodies, कमी overlap, structure तोडतो.
4 Pullback = correction, reversal नाही: overlap, मिश्र candles, impulse पेक्षा जास्त वेळ, legs / bodies लहान, जोर कमी, futures volume कमी.
  Impulsive counter-move किंवा origin चा real break ⇒ थांबा.
5 Pattern: zigzag / flat (regular, expanded) / triangle / ending diagonal (wedge) / W-X-Y; labels bar वेळांसह. ओळखता येत नाही ⇒ trade नाही.
6 Pattern पूर्ण: शेवटचा leg (C / E / 5) आला? A-end / B च्या आत / X ⇒ trade नाही.
7 Pattern च्या शेवटी area: playbook ची 12 साधनं; किमान दोन वेगळ्या प्रकारांचा confluence; Fibonacci फक्त खऱ्या area सोबत.
8 खोली 38.2–80% (2–6 candles च्या flag साठी 23.6–38.2%).
9 Price failure, बंद candle वर: rejection wick / sweep + reclaim / engulfing; correction ची trendline तुटणे हा अधिकचा पुरावा.
10 Risk: invalidation pattern च्या टोकाच्या / area च्या पलीकडे; target opposite area / impulse टोक; R:R ≥ 3.
11 संदर्भ: gap, वेळ (09:15–09:45), expiry, event, VIX.
12 पक्के नियम: breakout / पाठलाग नाही, बंद candle, स्पष्ट invalidation, R:R ≥ 3.
निर्णय: 4, 5, 6, 9, 10, 12 पैकी एकही ✘ ⇒ trade नाही (तरी सगळी उत्तरं द्यायची). शेवटी "मी कुठे चुकीचा ठरेन".

MARKS (for the chart the code will draw): pattern labels, areas and trendline anchors — each anchored to a bar as
{tf: "W"|"D"|"1H"|"15M", time: exactly as in that table's first column, field: "high"|"low"|"open"|"close"}. An area = two anchors (its
two edges); a trendline = two anchors. Trend words in Marathi (तेजी / मंदी / correction / range), 1–3 words each.
No futures volume, VIX or event data is provided in this test: say so where an item needs it.
"""

SYSTEM = PLAYBOOK + "\n" + CHECKLIST

REF = {"type": "object", "additionalProperties": False, "required": ["tf", "time", "field"],
       "properties": {"tf": {"type": "string", "enum": list(TFS)}, "time": {"type": "string"},
                      "field": {"type": "string", "enum": ["open", "high", "low", "close"]}}}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["trend", "checklist", "pattern", "labels", "areas", "trendlines", "decision", "wrong_if"],
    "properties": {
        "trend": {"type": "object", "additionalProperties": False, "required": ["weekly", "daily", "h1", "m15"],
                  "properties": {k: {"type": "string"} for k in ("weekly", "daily", "h1", "m15")}},
        "checklist": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["n", "status", "evidence", "bar_times"],
            "properties": {"n": {"type": "integer"}, "status": {"type": "string", "enum": list(STATUS)}, "evidence": {"type": "string"},
                           "bar_times": {"type": "array", "items": {"type": "string"}}}}},
        "pattern": {"type": "object", "additionalProperties": False, "required": ["name", "complete"],
                    "properties": {"name": {"type": "string"}, "complete": {"type": "boolean"}}},
        "labels": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["text", "at"],
                                              "properties": {"text": {"type": "string"}, "at": REF}}},
        "areas": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["name", "a", "b"],
                                             "properties": {"name": {"type": "string"}, "a": REF, "b": REF}}},
        "trendlines": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["name", "a", "b"],
                                                  "properties": {"name": {"type": "string"}, "a": REF, "b": REF}}},
        "decision": {"type": "object", "additionalProperties": False, "required": ["side", "entry", "invalidation", "target"],
                     "properties": {"side": {"type": "string", "enum": ["bear", "bull", "none"]}, "entry": REF, "invalidation": REF,
                                    "target": REF}},
        "wrong_if": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------------------------------------------- frames
def weekly(daily, asof):
    """बंद daily ⇒ पूर्ण झालेले आठवडे (शुक्रवार 15:30 ≤ asof). timestamp = आठवड्याचा पहिला session."""
    if daily is None or not len(daily):
        return pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close"])
    d = daily.copy()
    wk = pd.to_datetime(d["timestamp"]).dt.to_period("W-FRI")
    g = d.assign(_w=wk).groupby("_w").agg(timestamp=("timestamp", "first"), open=("open", "first"), high=("high", "max"),
                                          low=("low", "min"), close=("close", "last")).reset_index()
    g["bar_end"] = g["_w"].dt.end_time.dt.normalize() + pd.Timedelta(hours=15, minutes=30)
    g = g[g["bar_end"] <= pd.Timestamp(asof)]
    return g[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


def frames(m1, decision):
    """decision = 15M bar start ⇒ asof = त्याचा close. फक्त बंद bars (bar_end ≤ asof); decision दिवसाचा daily bar अर्धवट ⇒ नाही."""
    from market_state import core as MC
    asof = pd.Timestamp(decision) + pd.Timedelta(minutes=15)
    cut = m1[pd.to_datetime(m1["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
    d = MC.frame(cut, "1d", asof)
    out = {"W": weekly(d, asof), "D": d, "1H": MC.frame(cut, "1h", asof), "15M": MC.frame(cut, "15m", asof)}
    for tf, f in out.items():
        assert not len(f) or pd.Timestamp(f["bar_end"].max()) <= asof, f"{tf}: decision नंतरचा bar"
    return {tf: f.tail(BARS[tf]).reset_index(drop=True) for tf, f in out.items()}, asof


def fmt_time(ts, tf):
    return f"{pd.Timestamp(ts):%Y-%m-%d}" if tf in ("W", "D") else f"{pd.Timestamp(ts):%Y-%m-%d %H:%M}"


def ohlc_table(df, tf):
    rows = [f"{fmt_time(r.timestamp, tf)},{r.open:.2f},{r.high:.2f},{r.low:.2f},{r.close:.2f}" for r in df.itertuples()]
    label = {"W": "Weekly (bar = week, time = first session of the week)", "D": "Daily", "1H": "1H (bar start IST)",
             "15M": "15M (bar start IST)"}[tf]
    return f"{label} OHLC — time,open,high,low,close; last row = last CLOSED bar:\n" + "\n".join(rows)


def user_text(decision, fr, history_note=None):
    head = (f"NIFTY. Decision bar = the 15M bar starting {pd.Timestamp(decision):%Y-%m-%d %H:%M} (closed at "
            f"{pd.Timestamp(decision) + pd.Timedelta(minutes=15):%H:%M}). No data after that close exists anywhere in this request. "
            "Four clean candle charts (Weekly, Daily, 1H, 15M; no marks) and their OHLC tables follow. Decide yourself.")
    parts = [head] + ([history_note] if history_note else []) + [ohlc_table(fr[tf], tf) for tf in TFS]
    parts.append("Answer with the JSON schema: all 12 checklist items (n 1–12, in order), marks anchored to table rows, decision "
                 "(side bear / bull / none; entry / invalidation / target as table anchors — when side is none, anchor them to the "
                 "decision bar close), and wrong_if.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------------------------------------------- request
def build_request(pngs, text, model, max_tokens=6000, effort=None, thinking=None, temperature=0.0):
    if not model:
        raise ValueError("model env नाही (VISION_SIGNAL_MODEL)")
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.standard_b64encode(p).decode("utf-8")}} for p in pngs if p]
    content.append({"type": "text", "text": text})
    p = {"model": model, "max_tokens": int(max_tokens), "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
         "messages": [{"role": "user", "content": content}], "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}
    if effort:
        p["output_config"]["effort"] = effort
    if thinking:
        p["thinking"] = {"type": thinking}
    elif temperature is not None:
        p["temperature"] = float(temperature)
    return p


def parse(message):
    """(data | None, error | None, usage)."""
    from vision.signal_audit import usage_of
    usage = usage_of(message)
    stop = getattr(message, "stop_reason", None)
    if stop in ("refusal", "max_tokens"):
        return None, f"stop_reason {stop}", usage
    text = next((b.text for b in (getattr(message, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, "text उत्तर नाही", usage
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"JSON parse: {exc}", usage
    miss = [k for k in SCHEMA["required"] if k not in data]
    return (None, f"JSON field नाही: {miss}", usage) if miss else (data, None, usage)


def estimate_usd(model, n_images=4, text_chars=40000, max_tokens=6000):
    """सावध अंदाज: cache नाही, output = max_tokens. Image ≈ 1,600 tokens, मजकूर ≈ 3.5 अक्षरं / token."""
    from vision.signal_audit import cost_usd
    return cost_usd(model, {"input_tokens": n_images * 1600 + len(SYSTEM) // 3 + text_chars // 3, "output_tokens": max_tokens})


# ---------------------------------------------------------------------------------------------------------------- code-side checks
def price_of(ref, fr):
    """{tf, time, field} ⇒ खरी OHLC किंमत (तक्त्यातून) किंवा None (bar सापडला नाही)."""
    if not ref or ref.get("tf") not in fr:
        return None
    f = fr[ref["tf"]]
    t = str(ref.get("time", "")).strip()
    hit = f[[fmt_time(x, ref["tf"]) == t for x in f["timestamp"]]]
    if not len(hit) or ref.get("field") not in ("open", "high", "low", "close"):
        return None
    return round(float(hit[ref["field"]].iloc[0]), 2)


def resolve(v, fr):
    """Vision JSON ⇒ code निकाल: प्रत्येक खुणेची खरी किंमत, निर्णय नियम (GATING), entry / SL / target / R:R, गहाळ refs."""
    items = {int(c["n"]): c for c in v.get("checklist") or [] if isinstance(c.get("n"), int)}
    missing_items = [n for n in range(1, 13) if n not in items]
    fails = [n for n in range(1, 13) if items.get(n, {}).get("status") == "✘"]
    gate_fail = [n for n in GATING if n in fails or n in missing_items]
    bad_refs = []

    def px(ref, what):
        p = price_of(ref, fr)
        if p is None:
            bad_refs.append(f"{what}: {ref}")
        return p

    labels = [{"text": x["text"], "tf": x["at"]["tf"], "time": x["at"]["time"], "price": px(x["at"], f"label {x['text']}")}
              for x in v.get("labels") or []]
    areas = [{"name": a["name"], "tf": a["a"]["tf"], "time": a["a"]["time"], "lo": None, "hi": None,
              "p": [px(a["a"], f"area {a['name']}"), px(a["b"], f"area {a['name']}")]} for a in v.get("areas") or []]
    for a in areas:
        ps = [p for p in a.pop("p") if p is not None]
        a["lo"], a["hi"] = (min(ps), max(ps)) if ps else (None, None)
    tls = [{"name": t["name"], "a": {**t["a"], "price": px(t["a"], f"trendline {t['name']}")},
            "b": {**t["b"], "price": px(t["b"], f"trendline {t['name']}")}} for t in v.get("trendlines") or []]
    d = v.get("decision") or {}
    side = d.get("side", "none")
    entry, inv, tgt = (px(d.get(k), f"decision {k}") if side != "none" else price_of(d.get(k), fr) for k in ("entry", "invalidation", "target"))
    rr, order_ok = None, True
    if side != "none" and None not in (entry, inv, tgt) and abs(entry - inv) > 0:
        rr = round(abs(tgt - entry) / abs(entry - inv), 2)
        sgn = -1 if side == "bear" else 1                                   # bear: SL वर, target खाली; bull उलट
        order_ok = (inv - entry) * sgn < 0 < (tgt - entry) * sgn
    trade = side != "none" and not gate_fail and rr is not None and rr >= 3.0 and order_ok
    why = []
    if gate_fail:
        why.append("✘ मुद्दे " + ", ".join(str(n) for n in gate_fail) + " ⇒ trade नाही (नियम)")
    if side != "none" and not order_ok:
        why.append("SL / target चुकीच्या बाजूला")
    elif side != "none" and (rr is None or rr < 3.0):
        why.append(f"R:R {rr} < 3" if rr is not None else "R:R मोजता आला नाही")
    return {"n_ok": sum(1 for n in range(1, 13) if items.get(n, {}).get("status") == "✔"), "fails": fails, "gate_fail": gate_fail,
            "missing_items": missing_items, "first_fail": (fails or [None])[0], "side": side, "trade": trade, "entry": entry,
            "invalidation": inv, "target": tgt, "rr": rr, "order_ok": order_ok, "labels": labels, "areas": areas, "trendlines": tls, "bad_refs": bad_refs,
            "code_why": "; ".join(why), "vision_said_trade": side != "none"}


# ---------------------------------------------------------------------------------------------------------------- caption
def _short(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def caption(n, total, decision, v, r):
    """≤ 8 ओळी, ≤ 1024 अक्षरं, साधी मराठी, code keys नाहीत."""
    t = v.get("trend") or {}
    side_mr = {"bear": "bear", "bull": "bull"}.get(r["side"], "trade नाही")
    dec = (f"{side_mr} · entry {r['entry']:,.1f} · SL {r['invalidation']:,.1f} · target {r['target']:,.1f} · R:R {r['rr']}"
           if r["side"] != "none" and None not in (r["entry"], r["invalidation"], r["target"]) else side_mr)
    if r["side"] != "none" and not r["trade"]:
        dec = f"trade नाही ({_short(r['code_why'], 60)}) · vision: {dec}"
    ar = [f"{a['name']} {a['lo']:,.0f}–{a['hi']:,.0f}" for a in r["areas"] if a["lo"] is not None][:3]
    ar += [f"{x['name']} रेषा" for x in r["trendlines"]][:2]
    ff = r["first_fail"]
    lines = [f"🧪 VISION TEST {n}/{total} · {pd.Timestamp(decision):%d %b %Y} · {pd.Timestamp(decision):%H:%M}",
             f"📈 Trend: W {_short(t.get('weekly'), 20)} / D {_short(t.get('daily'), 20)} / 1H {_short(t.get('h1'), 20)} / "
             f"15M {_short(t.get('m15'), 20)}",
             f"🌀 Pattern: {_short((v.get('pattern') or {}).get('name'), 80)} ({'पूर्ण' if (v.get('pattern') or {}).get('complete') else 'अपूर्ण'})",
             f"🧱 Areas / trendline: {_short(' · '.join(ar) or '—', 160)}",
             f"✅ Checklist: {r['n_ok']}/12 ✔" + (f" · पहिला ✘: {ff} {ITEM_MR[ff]}" if ff else ""),
             f"🎯 निर्णय: {dec}",
             "Reply: ✔ बरोबर · ✘ कारण"]
    cap = "\n".join(lines)
    return cap[:1024]


# ---------------------------------------------------------------------------------------------------------------- charts
def figure(df, tf, title, marks=None, legend=True):
    """स्वच्छ candles (x = bar क्रमांक, tick = वेळ). marks (code ने खऱ्या OHLC वरून) ⇒ क्रमांक-खुणा + legend."""
    import plotly.graph_objects as go
    x = np.arange(len(df))
    fig = go.Figure(go.Candlestick(x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350", showlegend=False))
    step = max(1, len(df) // 8)
    fig.update_layout(title=dict(text=title, x=0.01, font=dict(size=14)), template="plotly_dark", width=1400, height=720,
                      margin=dict(l=40, r=90, t=50, b=40), xaxis_rangeslider_visible=False, paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                      xaxis=dict(tickmode="array", tickvals=list(x[::step]), ticktext=[fmt_time(t, tf) for t in df["timestamp"].iloc[::step]],
                                 zeroline=False),
                      yaxis=dict(side="right", tickformat=",.0f", zeroline=False))
    if marks:
        _draw(fig, df, tf, marks, legend)
    return fig


def _xi(df, tf, ref_tf, time):
    """दुसऱ्या TF ची वेळ ⇒ या chart वरचा bar क्रमांक (त्या वेळेपर्यंतचा शेवटचा bar); chart बाहेर ⇒ None."""
    try:
        t = pd.Timestamp(time)
    except (ValueError, TypeError):
        return None
    ts = pd.to_datetime(df["timestamp"])
    idx = np.nonzero((ts <= t).to_numpy())[0]
    return int(idx[-1]) if len(idx) else None


def _draw(fig, df, tf, r, legend):
    lo, hi = float(df["low"].min()), float(df["high"].max())
    pad = (hi - lo) * 0.04
    rows, k = [], 0
    n = len(df)
    for a in r["areas"]:
        if a["lo"] is None:
            continue
        x0 = _xi(df, tf, a["tf"], a["time"])
        fig.add_shape(type="rect", x0=0 if x0 is None else x0, x1=n - 0.5, y0=a["lo"], y1=a["hi"], line_width=0,
                      fillcolor="rgba(255,193,7,0.18)" if a["tf"] in (tf, "15M", "1H") else "rgba(120,144,156,0.22)")
        rows.append((a["hi"], f"{a['name']} {a['lo']:,.1f}–{a['hi']:,.1f}", n - 1))
    for t_ in r["trendlines"]:
        pa, pb = t_["a"].get("price"), t_["b"].get("price")
        xa, xb = _xi(df, tf, t_["a"]["tf"], t_["a"]["time"]), _xi(df, tf, t_["b"]["tf"], t_["b"]["time"])
        if None in (pa, pb, xa, xb) or xa == xb:
            continue
        slope = (pb - pa) / (xb - xa)
        fig.add_shape(type="line", x0=xa, y0=pa, x1=n - 1, y1=pa + slope * (n - 1 - xa), line=dict(color="#ab47bc", width=2))
        rows.append((pa + slope * (n - 1 - xa), f"{t_['name']} ({pa:,.1f} → {pb:,.1f})", n - 1))
    for lb in r["labels"]:
        xi = _xi(df, tf, lb["tf"], lb["time"])
        if lb["price"] is None or xi is None:
            continue
        rows.append((lb["price"], f"{lb['text']} {lb['price']:,.1f} ({lb['time'][-5:] if ':' in lb['time'] else lb['time']})", xi))
    rows = [x for x in rows if lo - pad <= x[0] <= hi + pad]
    rows.sort(key=lambda x: -x[0])
    leg = []
    for y, text, xi in rows[:len(CIRC)]:
        c = CIRC[k]
        k += 1
        fig.add_annotation(x=xi, y=y, text=c, showarrow=False, font=dict(size=14, color="#ffeb3b"), xanchor="left")
        leg.append(f"{c} {text}")
    if legend and leg:
        fig.add_annotation(xref="paper", yref="paper", x=0.01, y=0.98, xanchor="left", yanchor="top", align="left", showarrow=False,
                           text="<br>".join(leg), font=dict(size=13, color="#e0e0e0"), bgcolor="rgba(14,17,23,0.85)",
                           bordercolor="#555", borderwidth=1)


def png(fig):
    return fig.to_image(format="png", scale=1)
