"""decision3/charts.py — v2.2 charts (Abhi ✔ साठी). Chart वरचा सगळा मजकूर English (Abhi: chart वर मराठी नको; Telegram caption `story` मराठी): W+D (Dow swings, trend, protected, range) आणि 1H (D2 swings, जिवंत levels ★,
active levels). फक्त दाखवण्यासाठी — निर्णयात नाही. Order / broker call नाही."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import levels as LV  # noqa: E402

TREND_COLOR = {"UP": "#d8f3dc", "DOWN": "#ffd6d6", "RANGE": "#fff3bf", "NEUTRAL": "#eeeeee", "UNKNOWN": "#ffffff"}


def _candles(ax, df):
    for i, r in enumerate(df.itertuples()):
        up = r.close >= r.open
        col = "#2b8a3e" if up else "#c92a2a"
        ax.plot([i, i], [r.low, r.high], color=col, lw=0.8)
        ax.add_patch(plt.Rectangle((i - 0.3, min(r.open, r.close)), 0.6, max(abs(r.close - r.open), 1e-6), color=col))
    ax.set_xlim(-1, len(df))


def _xticks(ax, ts, every):
    idx = list(range(0, len(ts), max(1, every)))
    ax.set_xticks(idx)
    ax.set_xticklabels([pd.Timestamp(ts[i]).strftime("%d %b") for i in idx], rotation=45, fontsize=7)


def _png(fig):
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return b.getvalue()


def _why_en(st):
    """Chart वर फक्त English (Abhi): Daily state चं कारण."""
    p = st.protected
    if st.trend in ("UP", "DOWN") and p is not None:
        return f" · protected {'HL' if p.kind == 'L' else 'LH'} {p.price:,.0f}"
    if st.trend == "NEUTRAL" and p is not None:
        return f" · protected {'HL' if p.kind == 'L' else 'LH'} {p.price:,.0f} broken by daily close"
    if st.trend == "RANGE" and st.band:
        return f" · range {st.band[0]:,.0f}-{st.band[1]:,.0f}"
    if st.trend == "UNKNOWN":
        return " · not enough daily data"
    return ""


def daily_png(daily_df, states, title, upto=None):
    """Daily: candles, trend पार्श्वभूमी, confirmed swings (HH/HL/LH/LL), protected रेघ, range पट्टा."""
    d = daily_df.reset_index(drop=True)
    n = len(d) if upto is None else upto + 1
    d = d.iloc[:n]
    fig, ax = plt.subplots(figsize=(12, 5))
    for i in range(n):
        ax.axvspan(i - 0.5, i + 0.5, color=TREND_COLOR.get(states[i].trend, "#fff"), lw=0)
    _candles(ax, d)
    last = states[n - 1]
    hs, ls = [], []
    for p in last.pivots:
        seq = hs if p.kind == "H" else ls
        lab = p.kind
        if seq:
            lab = ("HH" if p.price > seq[-1] else "LH") if p.kind == "H" else ("HL" if p.price > seq[-1] else "LL")
        seq.append(p.price)
        ax.annotate(lab, (p.bar, p.price), textcoords="offset points", xytext=(0, 8 if p.kind == "H" else -12), ha="center", fontsize=8,
                    color="#1c7ed6" if p.kind == "H" else "#e8590c")
    if last.pivots:
        ax.plot([p.bar for p in last.pivots], [p.price for p in last.pivots], color="#495057", lw=0.8, ls="--")
    if last.protected is not None:
        ax.axhline(last.protected.price, color="#7048e8", lw=1.2, ls=":")
        ax.text(n - 0.5, last.protected.price, f" protected {last.protected.price:,.0f}", color="#7048e8", fontsize=8, va="bottom")
    if last.band:
        ax.axhspan(last.band[0], last.band[1], color="#fab005", alpha=0.15)
    ax.set_title(f"{title} · Daily trend {last.trend}" + _why_en(last), fontsize=10)
    _xticks(ax, d["timestamp"].to_numpy(), max(1, n // 15))
    return _png(fig)


def weekly_png(daily_df, title):
    """Weekly: फक्त संदर्भ (gate नाही)."""
    d = daily_df.copy()
    wk = pd.to_datetime(d["timestamp"]).dt.to_period("W-FRI")
    w = d.assign(_w=wk).groupby("_w").agg(timestamp=("timestamp", "first"), open=("open", "first"), high=("high", "max"),
                                          low=("low", "min"), close=("close", "last")).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    _candles(ax, w)
    ax.set_title(f"{title} · Weekly (context only)", fontsize=10)
    _xticks(ax, w["timestamp"].to_numpy(), max(1, len(w) // 10))
    return _png(fig)


def h1_png(lv, t, trend, title, sessions=8, max_sigma=None):
    """1H: शेवटच्या `sessions` sessions चे candles (t पर्यंत), D2 swings, जिवंत levels (role रंग, ★ sweeps, जन्म-कारण), active ठळक."""
    h1, h1_of = lv.h1, lv.h1_of
    j_end = int(h1_of[t])
    days = pd.to_datetime(h1["timestamp"]).dt.normalize()
    keep_days = sorted(days.iloc[:j_end + 1].unique())[-sessions:]
    j0 = int(np.flatnonzero(days.isin(keep_days).to_numpy())[0])
    frame = h1.iloc[j0:j_end + 1].reset_index(drop=True)
    o, hh, ll, cc = lv._h1_upto(j_end, t)                                      # चालू (अपूर्ण) तास: फक्त t पर्यंतचे bars
    frame.loc[len(frame) - 1, ["open", "high", "low", "close"]] = [o, hh, ll, cc]
    fig, ax = plt.subplots(figsize=(13, 6))
    _candles(ax, frame)
    sg = lv.sig1h[t]
    lim = (max_sigma or float(lv.s["show_distance_sigma"])) * (sg if np.isfinite(sg) else np.inf)
    act = {x["id"] for x in lv.active(t, trend)}
    for x in lv.snapshot(t):
        if x["dist"] > lim and x["id"] not in act:
            continue                                                           # दूरची levels chart वर लपवा (snapshot मध्ये आहेत)
        col = "#2f9e44" if x["role"] == LV.SUP else "#e03131"
        ax.axhspan(x["lo"], x["hi"], color=col, alpha=0.30 if x["id"] in act else 0.10, lw=0)
        lab = f"{'▶ ' if x['id'] in act else ''}{x['role'][:3]} {'+'.join(x['births'])} {'★' * x['sweeps']} t{x['tests']}"
        ax.text(len(frame) - 0.5, (x["lo"] + x["hi"]) / 2, " " + lab, fontsize=7, color=col, va="center")
    for p in lv.piv:
        if p.confirm_bar <= t:
            j = int(h1_of[p.bar]) - j0
            if 0 <= j < len(frame):
                ax.plot(j, p.price, marker="v" if p.kind == "H" else "^", color="#1c7ed6" if p.kind == "H" else "#e8590c", ms=6)
    ax.set_title(f"{title} · 1H · Daily {trend} · {str(pd.Timestamp(lv.m15['timestamp'].iloc[t]))[:16]}", fontsize=10)
    _xticks(ax, frame["timestamp"].to_numpy(), max(1, len(frame) // 12))
    return _png(fig)


def story(r):
    """§6.5 वाचन: 3–5 ओळींची कथा (Telegram / Vision caption)."""
    tr = {"UP": "Daily ↑: खरेदीदार नियंत्रणात", "DOWN": "Daily ↓: विक्रेते नियंत्रणात", "RANGE": "Daily range: कडांवरच",
          "NEUTRAL": "Daily neutral: trade नाही", "UNKNOWN": "Daily data अपुरा"}[r["daily_trend"]]
    lines = [tr + (f" (protected {r['protected']['price']:,.0f})" if r.get("protected") else "")]
    lv = r.get("level")
    if lv:
        lines.append(f"1H: pullback {lv['role']} {lv['lo']:,.0f}–{lv['hi']:,.0f} ({'+'.join(lv['births'])}) {'★' * lv['sweeps']} कडे")
    k = r.get("K")
    if k and k.get("open"):
        ev = r.get("evidence") or {}
        bits = [f"pullback चे {k['legs']} पाय"]
        if ev.get("power_shift"):
            bits.append("counter जोर संपतोय")
        if ev.get("trap_sweep"):
            bits.append("sweep होऊन परत ⇒ अडकलेले traders")
        lines.append("15M: " + ", ".join(bits))
    lq = r.get("liquidity") or {}
    if lq.get("sweeps"):
        x = lq["sweeps"][0]
        who = "buyers" if x["side"] == "buy" else "sellers"
        lines.append(f"liquidity: {x['src']} {x['price']:,.0f} ⚡ sweep ⇒ {who} अडकले")
    c = r["checklist"]
    lines.append(f"Commitment: {c['⑥'][1]}")
    if r.get("risk"):
        rk = r["risk"]
        lines.append(f"Conviction {r.get('conviction')} · entry {rk['entry']:,.0f} · SL {rk['sl']:,.0f} · target {rk['target'] or 0:,.0f} · R:R {rk['rr']}")
    elif r.get("why"):
        lines.append(r["why"])
    return "\n".join(lines[:6])


def m15_png(V, t, title, bars=60, r=None):
    """15M: level, K टोक, commitment खूण (✅ / 🟡), entry / SL / target."""
    i0 = max(0, t - bars + 1)
    m = V.m15.iloc[i0:t + 1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(13, 5.5))
    _candles(ax, m)
    if r and r.get("level"):
        lv = r["level"]
        ax.axhspan(lv["lo"], lv["hi"], color="#2f9e44" if lv["role"] == LV.SUP else "#e03131", alpha=0.18)
    if r and r.get("risk"):
        rk = r["risk"]
        for y, col, lab in ((rk["entry"], "#1c7ed6", "entry"), (rk["sl"], "#e03131", "SL"), (rk["target"], "#2f9e44", "target")):
            if y is not None:
                ax.axhline(y, color=col, lw=0.9, ls="--")
                ax.text(len(m) - 0.5, y, f" {lab} {y:,.0f}", color=col, fontsize=8, va="bottom")
    if r and r.get("mark"):
        ax.annotate(r["mark"], (len(m) - 1, float(m["close"].iloc[-1])), textcoords="offset points", xytext=(0, 18), ha="center", fontsize=14)
    ax.set_title(f"{title} · 15M · {r['decision'] if r else ''} {r.get('conviction') or '' if r else ''}", fontsize=10)
    _xticks(ax, m["timestamp"].to_numpy(), max(1, len(m) // 12))
    return _png(fig)
