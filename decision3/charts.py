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
        ph = {"impulse": "impulse", "correction": f"correction leg {st.corr_label}",
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


def daily_png(daily_df, states, title, upto=None, start=0):
    """Daily: candles, trend पार्श्वभूमी, confirmed swings (HH/HL/LH/LL), protected रेघ, range पट्टा. start ⇒ फक्त त्या index पासून
    दाखवतो (engine पूर्ण history वर; Q33: NIFTY holdout तारखा chart वर नाहीत)."""
    d = daily_df.reset_index(drop=True)
    n = len(d) if upto is None else upto + 1
    if int(start) > n - 1:
        raise ValueError("daily_png: no daily candle to show after start (sealed or not enough data)")
    start = max(0, int(start))
    d = d.iloc[start:n]
    fig, ax = plt.subplots(figsize=(12, 5))
    for i in range(start, n):
        ax.axvspan(i - start - 0.5, i - start + 0.5, color=TREND_COLOR.get(states[i].trend, "#fff"), lw=0)
    _candles(ax, d)
    last = states[n - 1]
    hs, ls = [], []
    shown = [p for p in last.pivots if p.bar >= start]
    for p in last.pivots:
        seq = hs if p.kind == "H" else ls
        lab = p.kind
        if seq:
            lab = ("HH" if p.price > seq[-1] else "LH") if p.kind == "H" else ("HL" if p.price > seq[-1] else "LL")
        seq.append(p.price)
        if p.bar >= start:
            ax.annotate(lab, (p.bar - start, p.price), textcoords="offset points", xytext=(0, 8 if p.kind == "H" else -12), ha="center",
                        fontsize=8, color="#1c7ed6" if p.kind == "H" else "#e8590c")
    if shown:
        ax.plot([p.bar - start for p in shown], [p.price for p in shown], color="#495057", lw=0.8, ls="--")
    if last.protected is not None:
        ax.axhline(last.protected.price, color="#7048e8", lw=1.2, ls=":")
        ax.text(n - start - 0.5, last.protected.price, f" protected {last.protected.price:,.0f}", color="#7048e8", fontsize=8, va="bottom")
    if last.band:
        ax.axhspan(last.band[0], last.band[1], color="#fab005", alpha=0.15)
    for x in getattr(last, "targets", ()) or ():                               # Q44 structural target (parent नंतरच्या पहिल्या impulse leg चं टोक)
        ax.axhline(x, color="#868e96", lw=0.8, ls="--")
        ax.text(n - start - 0.5, x, f" target {x:,.0f}", color="#868e96", fontsize=7, va="top")
    ax.set_title(f"{title} · Daily trend {last.trend}" + _why_en(last), fontsize=10)
    _xticks(ax, d["timestamp"].to_numpy(), max(1, (n - start) // 15))
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


MAX_LEVEL_BANDS = 6                                                        # C1 (Abhi): review charts वर कमाल 6 level पट्टे


def h1_png(lv, t, trend, title, sessions=8, max_sigma=None, liq=None, band=None, debug=False):
    """1H (C1 default): candles of the last `sessions` sessions (up to t), at most 6 level bands (active first, then nearest; one
    label: role, price, state) and the highlighted trigger candle - nothing else. debug=True: all nearby levels (births, sweeps,
    tests), D2 swings and liquidity marks."""
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
    act = {x["id"] for x in lv.active(t, trend, band)}                    # Q27: engine ② सारखाच पट्टा
    shown = [x for x in lv.snapshot(t) if x["dist"] <= lim or x["id"] in act]   # दूरची levels chart वर लपवा (snapshot मध्ये आहेत)
    if not debug:
        shown = sorted(shown, key=lambda x: (x["id"] not in act, x["dist"]))[:MAX_LEVEL_BANDS]
    for x in shown:
        col = "#2f9e44" if x["role"] == LV.SUP else "#e03131"
        ax.axhspan(x["lo"], x["hi"], color=col, alpha=0.30 if x["id"] in act else 0.10, lw=0)
        if debug:
            lab = f"{'▶ ' if x['id'] in act else ''}{x['role'][:3]} {'+'.join(x['births'])} {'★' * x['sweeps']} t{x['tests']}"
        else:
            st = "tested" if x.get("tests") else "fresh"
            lab = f"{'▶ ' if x['id'] in act else ''}{x['role'].lower()} {x['lo']:,.0f}-{x['hi']:,.0f} ({st})"
        ax.text(len(frame) - 0.5, (x["lo"] + x["hi"]) / 2, " " + lab, fontsize=7, color=col, va="center")
    ax.axvspan(len(frame) - 1.5, len(frame) - 0.5, color="#fab005", alpha=0.18, lw=0)   # C1: trigger candle (चालू तास)
    for q in (liq or ()) if debug else ():                                                        # §7.6 liquidity pools (BSL वर / SSL खाली) — लहान खुणा
        col = "#1971c2" if q["side"] == "buy" else "#c2255c"
        ax.plot([len(frame) - 3, len(frame) - 0.5], [q["price"], q["price"]], color=col, lw=1.0, ls=(0, (1, 1)))
        ax.text(len(frame) - 3, q["price"], f"{q['label']} {q['price']:,.0f} ", color=col, fontsize=6, va="bottom", ha="right")
    for p in (lv.piv if debug else ()):
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


def m15_png(V, t, title, bars=60, r=None, debug=False):
    """15M (C1 default): level band, highlighted trigger candle, entry / SL / target and the setup mark - nothing else. debug=True
    adds the B2 trigger, trapped zones, sweeps and the K line (old dense view)."""
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
    ax.axvspan(len(m) - 1.5, len(m) - 0.5, color="#fab005", alpha=0.18, lw=0)   # C1: trigger candle (निर्णयाचा bar)
    bp = M.plans_of(V, r) if (debug and r and r.get("risk")) else None
    if bp:                                                                     # B2 योजना: signal-bar extreme पलीकडचा trigger
        y = bp["B2"]["trigger"]
        ax.axhline(y, color="#868e96", lw=0.8, ls=":")
        ax.text(len(m) - 0.5, y, f" B2 trigger {y:,.0f} (R:R {bp['B2']['rr']})", color="#868e96", fontsize=7, va="top")
    lq = (r.get("liquidity") or {}) if (r and debug) else {}
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
    tl = r.get("trendline") if (r and debug) else None
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


STATE_COLOR = {"UP · impulse": "#69db7c", "UP · correction": "#b2f2bb", "DOWN · impulse": "#ff8787", "DOWN · correction": "#ffc9c9",
               "RANGE": "#ffe066", "NEUTRAL": "#ced4da", "UNKNOWN": "#f8f9fa", "UP": "#8ce99a", "DOWN": "#ffa8a8"}
BAND_STATE_COLOR = {"fresh": "#1971c2", "tested": "#e67700", "broken": "#868e96", "target": "#5f3dc4"}


def daily_swings_png(v, title):
    """C1 (Abhi) default Daily chart - trend-degree structure only: impulse legs (one line each), corrections as labelled boxes
    (depth, shape), the protected origin as one line with its price, at most 6 level bands (label + state; off-window bands at the
    edge with an arrow and the price), small "pullback" marks inside the current impulse. No minor pivots, no HH/LL tags, no Elliott
    labels (debug chart). Bottom strip: degree-aware and Dow-minor states in trader words. Visual review only."""
    from matplotlib.patches import Rectangle

    from . import daily_swings as DS
    sp = DS.view_spec(v)
    d, i0 = v["frame"], v["i0"]
    fr = d.iloc[i0:].reset_index(drop=True)
    nn = len(fr)
    x = lambda b: b - i0                                                   # noqa: E731
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(20, 9.5), gridspec_kw={"height_ratios": [7, 1]}, sharex=True)
    _candles(ax, fr)
    lo_, hi_ = float(fr["low"].min()), float(fr["high"].max())
    rng = (hi_ - lo_) or 1.0
    for lg in sp["legs"]:                                                  # impulse legs
        a = max(lg["from"], i0)
        p0 = lg["p0"] if lg["from"] >= i0 else lg["p0"] + (lg["p1"] - lg["p0"]) * (a - lg["from"]) / max(lg["to"] - lg["from"], 1)
        ax.plot([x(a), x(lg["to"])], [p0, lg["p1"]], color="#e8590c", lw=3, alpha=0.55, solid_capstyle="round")
    for c in sp["boxes"]:                                                  # corrections = boxes
        a, b = max(c["start_bar"], i0), c["end_bar"] if c["state"] == "done" else v["n"] - 1
        y0, y1 = sorted((c["start_price"], c["end_price"]))
        ax.add_patch(Rectangle((x(a) - 0.5, y0), b - a + 1, y1 - y0, fill=True, fc="#7048e8", alpha=0.07, ec="#7048e8", lw=1.0,
                               ls="-" if c["state"] == "done" else "--"))
        ax.text(x(a), y1, c["label"], fontsize=7.5 if nn <= 200 else 6, color="#5f3dc4", va="bottom", ha="left")
    for pb in sp["pullbacks"]:                                             # lower-degree pullbacks / candidate (current impulse)
        up = pb["kind"] == "H"
        ax.annotate(pb["tag"], (x(pb["bar"]), pb["price"]), textcoords="offset points", xytext=(0, 9 if up else -13), ha="center",
                    fontsize=6.5, color="#868e96" if pb["tag"] == "pullback" else "#5f3dc4")
    for wv in sp.get("waves") or ():                                       # Q49: 5-wave पहिला पाय = "A" (पर्याय फक्त debug)
        up = wv["kind"] == "H"
        ax.annotate(wv["label"], (x(wv["bar"]), wv["price"]), textcoords="offset points", xytext=(0, 14 if up else -18), ha="center",
                    fontsize=10, color="#5f3dc4", fontweight="bold")
    off_n = {"above": 0, "below": 0}
    for bd in sp["bands"]:                                                 # ≤ 6 level bands
        col = BAND_STATE_COLOR.get(bd["state"], "#495057")
        lab = f"{bd['label']} {bd['price']:,.0f} ({bd['state']})"
        if bd["off_window"]:                                               # window बाहेर ⇒ कडेला बाण; अनेक असतील तर एकाखाली एक
            k = off_n[bd["off_window"]]
            off_n[bd["off_window"]] += 1
            yy = hi_ + (0.06 - 0.03 * k) * rng if bd["off_window"] == "above" else lo_ - (0.06 - 0.03 * k) * rng
            ax.annotate(("▲ " if bd["off_window"] == "above" else "▼ ") + lab, (nn - 1, yy), ha="right", fontsize=8, color=col,
                        va="center")
            continue
        ax.axhspan(bd["lo"], bd["hi"], color=col, alpha=0.13, lw=0)
        ax.text(nn - 0.5, bd["price"], " " + lab, fontsize=7.5, color=col, va="center")
    pq = sp["protected"]
    if pq and lo_ <= pq["price"] <= hi_:                                   # window बाहेरचा origin ⇒ पट्ट्याचा बाण पुरे (label plot बाहेर नाही)
        a = max(pq["bar"], i0)
        ax.plot([x(a), nn - 1], [pq["price"]] * 2, color="#c92a2a", lw=1.4)
        ax.text(x(a), pq["price"], f"origin {pq['price']:,.0f} ", fontsize=8, color="#c92a2a", ha="right", va="center")
    ax.set_ylim(lo_ - 0.1 * rng, hi_ + 0.1 * rng)
    for row, (name, runs_) in enumerate((("degree-aware", sp["strip"]["degree-aware"]), ("Dow minor", sp["strip"]["Dow minor"]))):
        for a, b, st in runs_:
            if b < i0:
                continue
            a2 = max(a, i0)
            bx.add_patch(plt.Rectangle((x(a2) - 0.5, row), b - a2 + 1, 0.9, color=STATE_COLOR.get(st, "#fff"), lw=0))
            if b - a2 >= max(8, nn // 14):                                 # लहान runs वर नाव नाही (गर्दी)
                bx.text(x(a2) + (b - a2) / 2, row + 0.45, st, ha="center", va="center", fontsize=7)
        bx.text(-1, row + 0.45, name, ha="right", va="center", fontsize=8)
    bx.set_ylim(0, 2)
    bx.set_yticks([])
    ax.set_title(f"{title} · Daily structure (trend degree) · " + DS.trend_line(v["q15"]) + " · visual review only", fontsize=10)
    ax.grid(alpha=0.12)
    _xticks(bx, fr["timestamp"].to_numpy(), max(1, len(fr) // 24))
    fig.tight_layout()
    return _png(fig)


def daily_swings_debug_png(v, title):
    """Debug (C1): the old dense view - Dow minor pivots with HH/HL/LH/LL and protected swings, Q15 legs / origin / phases, Elliott
    advisory labels (gray = "?"). Not sent to Telegram unless asked. Visual review only."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    d, i0 = v["frame"], v["i0"]
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
    wa = v["q15"].get("wave_a")                                            # Q49 debug: "A (alt: 1)"
    if wa and wa["bar"] >= i0:
        up = wa["kind"] == "H"
        ax.text(x(wa["bar"]), wa["price"] + (0.075 if up else -0.075) * rng, f"A (alt: {v['q15'].get('alt') or '-'})", ha="center",
                va="center", fontsize=8, color="#c92a2a", fontweight="bold")
    lo_, hi_ = float(fr["low"].min()), float(fr["high"].max())
    ax.set_ylim(lo_ - 0.09 * rng, hi_ + 0.09 * rng)                        # labels / tags कापले जात नाहीत
    for t in v["q15"]["targets"] or ():
        ax.axhline(t, color="#868e96", lw=0.8, ls="--")
        ax.text(len(fr) - 0.5, t, f" target {t:,.0f}", color="#868e96", fontsize=7, va="bottom")
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
            bx.text(x(a2) + (b - a2) / 2, 0.45, ph.replace("_", " "), ha="center", va="center", fontsize=6.5)   # Q34: क्रमांक नाही
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
    ax.set_title(f"{title} · Daily swings DEBUG — Dow minor vs degree-aware (Q15) · visual review only", fontsize=11)
    ax.grid(alpha=0.15)
    _xticks(bx, fr["timestamp"].to_numpy(), max(1, len(fr) // 24))
    fig.tight_layout()
    return _png(fig)
