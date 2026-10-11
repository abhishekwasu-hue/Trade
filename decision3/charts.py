"""decision3/charts.py — v2.2 charts (Abhi ✔ साठी). Chart वरचा सगळा मजकूर English (Abhi: chart वर मराठी नको; Telegram caption `story` मराठी): W+D (Dow swings, trend, protected, range) आणि 1H (D2 swings, जिवंत levels ★,
active levels). फक्त दाखवण्यासाठी — निर्णयात नाही. Order / broker call नाही."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import levels as LV  # noqa: E402
from . import method as M  # noqa: E402

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
    if st.trend in ("UP", "DOWN") and p is not None and getattr(st, "phase", None):
        ph = {"impulse": f"impulse {st.wave}", "correction": f"correction {st.wave} leg {st.corr_label}",
              "origin_broken": "origin closed through - waiting for opposite impulse"}[st.phase]
        return f" · {ph} · protected origin {p.price:,.0f}" + (" · MATURE near target" if st.mature else "")
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
    for x in getattr(last, "targets", ()) or ():                               # Q15 maturity targets ((5) equality / मोठा आधीचा swing)
        ax.axhline(x, color="#868e96", lw=0.8, ls="--")
        ax.text(n - 0.5, x, f" target {x:,.0f}", color="#868e96", fontsize=7, va="top")
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


def h1_png(lv, t, trend, title, sessions=8, max_sigma=None, liq=None):
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
    for q in liq or ():                                                        # §7.6 liquidity pools (BSL वर / SSL खाली) — लहान खुणा
        col = "#1971c2" if q["side"] == "buy" else "#c2255c"
        ax.plot([len(frame) - 3, len(frame) - 0.5], [q["price"], q["price"]], color=col, lw=1.0, ls=(0, (1, 1)))
        ax.text(len(frame) - 3, q["price"], f"{q['label']} {q['price']:,.0f} ", color=col, fontsize=6, va="bottom", ha="right")
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
        if ev.get("tl_break"):
            bits.append("K ची रेघ close ने तुटली")
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
    bp = M.plans_of(V, r) if r and r.get("risk") else None
    if bp:                                                                     # B2 योजना: signal-bar extreme पलीकडचा trigger
        y = bp["B2"]["trigger"]
        ax.axhline(y, color="#868e96", lw=0.8, ls=":")
        ax.text(len(m) - 0.5, y, f" B2 trigger {y:,.0f} (R:R {bp['B2']['rr']})", color="#868e96", fontsize=7, va="top")
    lq = (r.get("liquidity") or {}) if r else {}
    for x in lq.get("trapped") or ():                                          # §7.6 trapped zone पट्टा
        ax.axhspan(x["lo"], x["hi"], color="#fd7e14", alpha=0.12, hatch="///", lw=0)
        ax.text(0, x["hi"], f" trapped {'buyers' if x['side'] == 'buy' else 'sellers'} {x['lo']:,.0f}-{x['hi']:,.0f}",
                color="#d9480f", fontsize=7, va="bottom")
    for x in lq.get("sweeps") or ():                                           # §7.6 sweep खूण (pool पलीकडे जाऊन परत)
        b = int(x.get("bar", -1))
        if i0 <= b <= t:
            ax.plot(b - i0, x["extreme"], marker="X", color="#d9480f", ms=7)
            ax.text(b - i0, x["extreme"], f" SWEEP {x['src']} {x['price']:,.0f}", color="#d9480f", fontsize=7,
                    va="bottom" if x["side"] == "buy" else "top")
    tl = r.get("trendline") if r else None
    if tl:                                                                     # ⑤ K ची आतली रेघ (t पर्यंत) + break खूण
        (b1, y1), sl = tl["p1"], tl["slope"]
        xs = [max(b1, i0), t]
        ax.plot([x - i0 for x in xs], [y1 + sl * (x - b1) for x in xs], color="#7048e8", lw=1.1, ls="-.")
        lab = f" K line ({tl['touches']} touches)" + (" broken" if tl["broken"] else "")
        ax.text(len(m) - 0.5, y1 + sl * (t - b1), lab, color="#7048e8", fontsize=8, va="top")
        if tl["broken"] and tl["break_bar"] is not None and tl["break_bar"] >= i0:
            bb = tl["break_bar"]
            ax.plot(bb - i0, float(V.m15["close"].iloc[bb]), marker="x", color="#7048e8", ms=8)
    if r and r.get("mark"):
        up = bool(r.get("level")) and r["level"]["role"] == LV.SUP                 # chart वर emoji नाही (font) ⇒ English label + बाण
        lab = {"✅": "SETUP A", "🟡": "SETUP B"}.get(r["mark"], str(r["mark"]))
        ax.annotate(("▲ " if up else "▼ ") + lab, (len(m) - 1, float(m["close"].iloc[-1])), textcoords="offset points",
                    xytext=(0, -26 if up else 18), ha="center", fontsize=11, color="#2f9e44" if r["mark"] == "✅" else "#e8590c")
    ax.set_title(f"{title} · 15M · {r['decision'] if r else ''} {r.get('conviction') or '' if r else ''}", fontsize=10)
    _xticks(ax, m["timestamp"].to_numpy(), max(1, len(m) // 12))
    return _png(fig)


BAND_COLOR = {"UP": "#8ce99a", "DOWN": "#ffa8a8", "RANGE": "#ffe066", "NEUTRAL": "#ced4da", "UNKNOWN": "#f8f9fa"}


def daily_swings_png(v, title):
    """Daily swing review (decision3.daily_swings.build): candles (शेवटची window), (a) Dow minor — pivots + HH/HL/LH/LL + protected
    (pivot ⇒ तुटला / बदलला) + trend पट्टा; (b) Q15 — impulse / corrective legs, origin protected, phase / wave पट्टा; elliott advisory
    labels (gray ⇒ "?"). सगळा मजकूर English. फक्त दृश्य तपासणी."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    d, i0, n = v["frame"], v["i0"], v["n"]
    fr = d.iloc[i0:].reset_index(drop=True)
    x = lambda b: b - i0                                                   # noqa: E731
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(20, 9.5), gridspec_kw={"height_ratios": [7, 1]}, sharex=True)
    _candles(ax, fr)
    for lg in v["legs"]:                                                   # (b) legs
        b = lg["to"]
        if lg["class"] == "impulse":
            ax.plot([x(lg["from"]), x(b)], [lg["p0"], lg["p1"]], color="#f76707", lw=3, alpha=0.35, solid_capstyle="round")
        elif lg["class"] == "corrective":
            ax.plot([x(lg["from"]), x(b)], [lg["p0"], lg["p1"]], color="#7048e8", lw=1.2, ls=":", alpha=0.8)
    for sg in v["minor"]["protected"]:                                     # (a) protected
        if sg["to"] < i0:
            continue
        a = max(sg["bar"], i0)
        ax.plot([x(a), x(sg["to"])], [sg["price"]] * 2, color="#1c7ed6", lw=1.1, ls="--")
        if sg["ended"] == "broken":
            ax.plot([x(sg["to"])], [sg["price"]], marker="x", color="#1c7ed6", ms=7, mew=2)
    for sg in v["q15"]["protected"]:                                       # (b) impulse origin
        if sg["to"] < i0:
            continue
        a = max(sg["bar"], i0)
        ax.plot([x(a), x(sg["to"])], [sg["price"]] * 2, color="#e8590c", lw=1.6)
        if sg["ended"] == "broken":
            ax.plot([x(sg["to"])], [sg["price"]], marker="X", color="#e8590c", ms=8)
    rng = float(fr["high"].max() - fr["low"].min()) or 1.0
    for p in v["pivots"]:                                                  # (a) pivots + tags + elliott label
        if not p["in_window"]:
            continue
        up = p["kind"] == "H"
        ax.plot([x(p["bar"])], [p["price"]], marker="v" if up else "^", color="#1c7ed6" if up else "#e8590c", ms=6,
                markeredgecolor="#212529" if (p["protected_minor"] or p["protected_q15"]) else None)
        lab = p["tag"] + ("*" if p["protected_minor"] else "")
        ax.annotate(lab, (x(p["bar"]), p["price"]), textcoords="offset points", xytext=(0, 8 if up else -12), ha="center", fontsize=6.5,
                    color="#1c7ed6" if up else "#e8590c", fontweight="bold")
        if p.get("wave_label"):
            ax.text(x(p["bar"]), p["price"] + (0.055 if up else -0.055) * rng, p["wave_label"], ha="center", va="center", fontsize=9,
                    color="#5f3dc4", fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#5f3dc4", lw=0.6))
    lo_, hi_ = float(fr["low"].min()), float(fr["high"].max())
    ax.set_ylim(lo_ - 0.09 * rng, hi_ + 0.09 * rng)                        # labels / tags कापले जात नाहीत
    for t in v["q15"]["targets"] or ():
        ax.axhline(t, color="#868e96", lw=0.8, ls="--")
        ax.text(len(fr) - 0.5, t, f" Q15 target {t:,.0f}", color="#868e96", fontsize=7, va="bottom")
    for row, (key, name) in enumerate((("q15", "Q15 degree-aware"), ("minor", "Dow minor swings"))):
        for a, b, s in v[key]["bands"]:
            if b < i0:
                continue
            a2 = max(a, i0)
            bx.add_patch(plt.Rectangle((x(a2) - 0.5, row), b - a2 + 1, 0.9, color=BAND_COLOR.get(s, "#fff"), lw=0))
        bx.text(-1, row + 0.45, name, ha="right", va="center", fontsize=8)
    for a, b, s in v["q15"]["phases"]:                                     # Q15 wave नावं पट्ट्यावर
        if b < i0 or s.startswith("-"):
            continue
        a2 = max(a, i0)
        if b - a2 >= 12:                                                   # लहान runs वर नाव नाही (गर्दी)
            ph, wv = s.split("|")
            short = {"impulse": "imp", "correction": "corr", "origin_broken": "broken"}.get(ph, ph)
            bx.text(x(a2) + (b - a2) / 2, 0.45, f"{wv} {short}", ha="center", va="center", fontsize=6.5)
    bx.set_ylim(0, 2)
    bx.set_yticks([])
    hdl = [Line2D([], [], color="#1c7ed6", ls="--", label="Dow minor: protected (x = broken by close)"),
           Line2D([], [], marker="v", ls="", color="#1c7ed6", label="pivot H / L with HH-LH-HL-LL (* = was protected)"),
           Line2D([], [], color="#e8590c", lw=1.6, label="Q15: impulse origin = protected (X = broken by close)"),
           Line2D([], [], color="#f76707", lw=3, alpha=0.35, label="Q15 leg: impulse"),
           Line2D([], [], color="#7048e8", lw=1.2, ls=":", label="Q15 leg: corrective"),
           Patch(fc="white", ec="#5f3dc4", label="Elliott advisory label ('?' = weak vote) — not used in decisions")]
    hdl += [Patch(color=BAND_COLOR[k], label=f"state {k}") for k in ("UP", "DOWN", "NEUTRAL", "RANGE")]
    ax.legend(handles=hdl, loc="upper left", fontsize=7, ncol=2, framealpha=0.9)
    ax.set_title(f"{title} · Daily swings — Dow minor vs degree-aware (Q15) · visual review only", fontsize=11)
    ax.grid(alpha=0.15)
    _xticks(bx, fr["timestamp"].to_numpy(), max(1, len(fr) // 24))
    fig.tight_layout()
    return _png(fig)
