"""decision3/charts.py — v2.2 charts (Abhi ✔ साठी). Chart वरचा सगळा मजकूर English (Abhi: chart वर मराठी नको; Telegram caption `story` मराठी): W+D (Dow swings, trend, protected, range) आणि 1H (D2 swings, जिवंत levels ★,
active levels). फक्त दाखवण्यासाठी — निर्णयात नाही. Order / broker call नाही."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import levels as LV  # noqa: E402
from . import settings as S3  # noqa: E402
from . import method as M  # noqa: E402
from . import volume_pane as VP  # noqa: E402

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


def _vol_axes(figsize, ratio=(4, 1)):
    """Price ax + त्याखाली volume pane (एकच x)."""
    fig, (ax, axv) = plt.subplots(2, 1, figsize=figsize, sharex=True, gridspec_kw={"height_ratios": list(ratio), "hspace": 0.04})
    return fig, ax, axv


def _col(df, name):
    return df[name].to_numpy(float) if name in df.columns else np.full(len(df), np.nan)


def daily_png(daily_df, states, title, upto=None, start=0, symbol=None):
    """Daily: candles, trend पार्श्वभूमी, confirmed swings (HH/HL/LH/LL), protected रेघ, range पट्टा. start ⇒ फक्त त्या index पासून
    दाखवतो (engine पूर्ण history वर; Q33: NIFTY holdout तारखा chart वर नाहीत)."""
    d = daily_df.reset_index(drop=True)
    n = len(d) if upto is None else upto + 1
    if int(start) > n - 1:
        raise ValueError("daily_png: no daily candle to show after start (sealed or not enough data)")
    start = max(0, int(start))
    d = d.iloc[start:n]
    fig, ax, axv = _vol_axes((12, 6.2))
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
    VP.draw_daily_mpl(axv, _col(d, "volume"), source=VP.source_label(symbol or title), partial_last=False)   # volume नाही ⇒ NA
    _xticks(axv, d["timestamp"].to_numpy(), max(1, (n - start) // 15))
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


def m15_png(V, t, title, bars=60, r=None, debug=False, vol=None, symbol=None):
    """15M (C1 default): level band, highlighted trigger candle, entry / SL / target and the setup mark - nothing else. debug=True
    adds the B2 trigger, trapped zones, sweeps and the K line (old dense view). Volume pane below (vol = array aligned with V.m15,
    else V.m15["volume"], else "volume: NA (grade cap B)")."""
    i0 = max(0, t - bars + 1)
    m = V.m15.iloc[i0:t + 1].reset_index(drop=True)
    fig, ax, axv = _vol_axes((13, 7.0))
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
    vv = (np.asarray(vol, dtype=float)[i0:t + 1] if vol is not None else _col(m, "volume"))
    lv = (r or {}).get("level") or {}
    VP.draw_mpl(axv, VP.study(m, vol=vv, info=r, commit=len(m) - 1, symbol=symbol or title,
                              area=(lv["lo"], lv["hi"]) if lv.get("lo") is not None else None, d=lv.get("role")))
    _xticks(axv, m["timestamp"].to_numpy(), max(1, len(m) // 12))
    return _png(fig)


BAND_COLOR = {"UP": "#8ce99a", "DOWN": "#ffa8a8", "RANGE": "#ffe066", "NEUTRAL": "#ced4da", "UNKNOWN": "#f8f9fa"}


STATE_COLOR = {"UP · impulse": "#69db7c", "UP · correction": "#b2f2bb", "DOWN · impulse": "#ff8787", "DOWN · correction": "#ffc9c9",
               "RANGE": "#ffe066", "NEUTRAL": "#ced4da", "UNKNOWN": "#f8f9fa", "UP": "#8ce99a", "DOWN": "#ffa8a8"}
BAND_STATE_COLOR = {"fresh": "#1971c2", "tested": "#e67700", "broken": "#868e96", "target": "#5f3dc4"}

# §5.4–5.6 (Abhi): default Daily chart वरची प्रत्येक रेषा / पट्टा legend मध्ये — style (gid) ⇒ legend मजकूर, रंग
STYLE_COLOR = {"impulse leg": "#e8590c", "leg in progress": "#e8590c", "correction (done)": "#1c7ed6", "counter-move (in progress)": "#1c7ed6",
               "older correction": "#1c7ed6", "protected origin": "#7048e8", "sharp band": "#f08c00", "demand": "#2f9e44",
               "supply": "#e03131", "broken": "#868e96", "target": "#0c8599", "pullback": "#495057"}
LEGEND_TEXT = {"impulse leg": "impulse (5 waves)", "leg in progress": "trend leg — impulse not verified (structure-only check)", "correction (done)": "correction (done)",
               "counter-move (in progress)": "counter-move in progress", "older correction": "older correction (no label)",
               "protected origin": "protected origin", "sharp band": "sharp-fall / sharp-rise band", "demand": "demand",
               "supply": "supply", "broken": "broken level (dashed)", "target": "structural target"}
LEGEND_ORDER = tuple(LEGEND_TEXT)


def _legend_handles(styles):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    C = STYLE_COLOR
    mk = {"impulse leg": lambda: Line2D([], [], color=C["impulse leg"], lw=3, alpha=0.55),
          "leg in progress": lambda: Line2D([], [], color=C["leg in progress"], lw=2.4, alpha=0.8, ls="--"),
          "correction (done)": lambda: Patch(fc=C["correction (done)"], ec=C["correction (done)"], alpha=0.25),
          "counter-move (in progress)": lambda: Patch(fc="none", ec=C["counter-move (in progress)"], ls="--"),
          "older correction": lambda: Patch(fc=C["older correction"], ec=C["older correction"], alpha=0.08),
          "protected origin": lambda: Line2D([], [], color=C["protected origin"], lw=1.6),
          "sharp band": lambda: Patch(color=C["sharp band"], alpha=0.30),
          "demand": lambda: Patch(color=C["demand"], alpha=0.30),
          "supply": lambda: Patch(color=C["supply"], alpha=0.25),
          "broken": lambda: Line2D([], [], color=C["broken"], lw=1.1, ls="--"),
          "target": lambda: Line2D([], [], color=C["target"], lw=1.3, ls=":")}
    return [mk[k]() for k in LEGEND_ORDER if k in styles], [LEGEND_TEXT[k] for k in LEGEND_ORDER if k in styles]


class _Layout:
    """§5.5 (Abhi): मजकूर candles वर / दुसऱ्या मजकुरावर नाही — display (pixel) bboxes; जागा नाही ⇒ label सोडतो."""

    def __init__(self, fig, ax, fr):
        self.fig, self.ax = fig, ax
        self.lo, self.hi = fr["low"].to_numpy(float), fr["high"].to_numpy(float)
        self.boxes = []
        self.r = fig.canvas.get_renderer()

    def candles_hit(self, bb):
        (x0, y0), (x1, y1) = self.ax.transData.inverted().transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
        a, b = max(0, int(np.ceil(x0 - 0.3))), min(len(self.lo) - 1, int(np.floor(x1 + 0.3)))
        return a <= b and bool(((self.lo[a:b + 1] <= y1) & (self.hi[a:b + 1] >= y0)).any())

    def free(self, bb, inside=True, pad=4.0):
        ab = self.ax.get_window_extent(self.r)
        if inside and not (bb.x0 >= ab.x0 and bb.x1 <= ab.x1 and bb.y0 >= ab.y0 and bb.y1 <= ab.y1):
            return False
        if not inside and not (bb.y0 >= ab.y0 and bb.y1 <= ab.y1):
            return False
        g = bb.expanded(1.0, 1.0).padded(pad)
        if any(g.overlaps(o) for o in self.boxes):
            return False
        return not (inside and self.candles_hit(bb))

    def take(self, t, inside=True):
        bb = t.get_window_extent(self.r)
        if self.free(bb, inside):
            self.boxes.append(bb)
            return True
        return False


def daily_swings_fig(v, title, full=False):
    """C1 / §5 (Abhi) default Daily chart — trend-degree structure only, decluttered: impulse legs (one line each); correction boxes
    (depth = start extreme to end extreme) with text only on the current and the previous same-degree correction ("pullback" once in
    the in-progress box; older boxes faint without text, omitted on windows longer than `chart_old_box_sessions`); at most 6 level
    bands ranked by degree with trader names in the right margin (one broken band at most, dashed); a legend for every style drawn;
    no text over candles or other text (a label without room is dropped together with its band). full=True: every box labelled,
    every pullback mark and every band (debug). Bottom strip: degree-aware and Dow-minor states. Visual review only.
    रिटर्न (fig, info) — info: ax, bx, frame, labels [{kind, text, artist}], styles (drawn), dropped."""
    import matplotlib.transforms as mtransforms
    from matplotlib.patches import Rectangle

    from . import daily_swings as DS
    sp = DS.view_spec(v, full=full)
    d, i0 = v["frame"], v["i0"]
    fr = d.iloc[i0:].reset_index(drop=True)
    nn = len(fr)
    x = lambda b: b - i0                                                   # noqa: E731
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(20, 9.5), gridspec_kw={"height_ratios": [7, 1]}, sharex=True)
    fig.subplots_adjust(left=0.06, right=0.84, top=0.94, bottom=0.08, hspace=0.05)
    _candles(ax, fr)
    lo_, hi_ = float(fr["low"].min()), float(fr["high"].max())
    rng = (hi_ - lo_) or 1.0
    ylo, yhi = lo_ - 0.06 * rng, hi_ + 0.06 * rng
    C = STYLE_COLOR
    styles, labels, dropped = set(), [], []
    leg_style = {"impulse": "impulse leg", "unconfirmed": "leg in progress"}
    npts = int(S3.load(v.get("s"))["chart_leg_path_points"])
    for lg in sp["impulses"]:                                              # trend-degree impulses: खऱ्या pivots मधून zig-zag (Abhi review), read_counter
        st = leg_style[lg.get("style", "impulse")]                         # ने तपासलेला style
        xs, ys = _clip_path(leg_window_path(lg, i0, npts), i0)
        if len(xs) < 2:
            continue
        kw = dict(lw=3, alpha=0.55) if st == "impulse leg" else dict(lw=2.4, alpha=0.8, ls="--")
        ax.plot(xs, ys, color=C[st], solid_capstyle="round", gid=st, **kw)
        styles.add(st)
    for c in sp["boxes"]:                                                  # corrections = boxes (start extreme ⇒ end extreme)
        st = "older correction" if c["faint"] else ("correction (done)" if c["state"] == "done" else "counter-move (in progress)")
        a, b = max(c["start_bar"], i0), c["end_bar"] if c["state"] == "done" else v["n"] - 1
        y0, y1 = sorted((c["start_price"], c["end_price"]))
        ax.add_patch(Rectangle((x(a) - 0.5, y0), b - a + 1, y1 - y0, fill=True, fc=C[st], ec=C[st],
                               alpha=0.04 if c["faint"] else 0.08, lw=0.6 if c["faint"] else 1.0,
                               ls="--" if c["state"] != "done" else "-", gid=st))
        styles.add(st)
    bands = [dict(b, style=DS.band_style(b)) for b in sp["bands"]]
    styles |= {b["style"] for b in bands if ylo <= b["price"] <= yhi}
    if any(b["role"] == "protected" for b in bands):
        styles.add("protected origin")
    ax.set_ylim(ylo, yhi)
    ax.set_title(f"{title} · Daily structure (trend degree) · " + DS.trend_line(v["q15"]) + " · visual review only", fontsize=10)
    lay = _Layout(fig, ax, fr)
    fig.canvas.draw()

    def legend(st):
        h, t = _legend_handles(st)
        return ax.legend(handles=h, labels=t, fontsize=7, framealpha=0.92, ncol=1, borderaxespad=0.4)

    best = None                                                            # §5.6: legend त्या कोपऱ्यात जिथे y-axis कमी वाढवावा लागतो
    for loc in ("upper left", "lower left", "upper right", "lower right"):
        lgd = legend(styles)
        lgd.set_loc(loc)
        bb = lgd.get_window_extent(lay.r)
        (fx0, fy0), (fx1, fy1) = ax.transAxes.inverted().transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
        lgd.remove()
        xa, xb = ax.transData.inverted().transform([[bb.x0, 0], [bb.x1, 0]])[:, 0]
        ia, ib = max(0, int(np.ceil(xa - 0.3))), min(nn - 1, int(np.floor(xb + 0.3)))
        if ia > ib:
            ext, lim = 0.0, (ylo, yhi)
        elif loc.startswith("upper"):
            f0 = max(fy0 - 0.015, 0.2)
            top = ylo + (float(fr["high"].iloc[ia:ib + 1].max()) - ylo) / f0
            ext, lim = max(0.0, top - yhi), (ylo, max(yhi, top))
        else:
            f1 = min(fy1 + 0.015, 0.8)
            bot = (float(fr["low"].iloc[ia:ib + 1].min()) - yhi * f1) / (1 - f1)
            ext, lim = max(0.0, ylo - bot), (min(ylo, bot), yhi)
        if best is None or ext < best[0] - 1e-9:
            best = (ext, loc, lim)
    ylo, yhi = best[2]
    ax.set_ylim(ylo, yhi)
    fig.canvas.draw()

    # §5.4 / §5.5: पट्टे — label उजव्या margin मध्ये. आधी "ठेवायचेच" (protected / sharp / parent = rank ≤ 1, target, title मधली next
    # demand / supply, caption मधले जवळचे दोन) — जागा मिळेपर्यंत वर / खाली सरकवतो (लहान leader रेषा); बाकी rank क्रमाने, जागा नाही ⇒
    # label आणि पट्टा दोन्ही नाहीत (नाव `dropped` मध्ये ⇒ JSON / Vision facts)
    tr = mtransforms.blended_transform_factory(ax.transAxes, ax.transData)
    step = (yhi - ylo) * 11.0 / max(ax.get_window_extent(lay.r).height, 1.0)
    near = {b["name"] for b in DS.nearest_bands(v) if b is not None}
    keep = lambda b: b["rank"] <= 1 or b["role"] == "target" or "target" in b.get("also", ()) or \
        b["label"].startswith("next ") or b["name"] in near                # noqa: E731
    shown = []
    for bd in sorted(bands, key=lambda b: not keep(b)):                    # sort stable ⇒ rank क्रम टिकतो
        col = C[bd["style"]]
        inside = ylo <= bd["price"] <= yhi
        y = bd["price"] if inside else (yhi if bd["price"] > yhi else ylo)
        txt = (" " if inside else (" ▲ " if bd["price"] > yhi else " ▼ ")) + bd["name"]
        t = ax.text(1.003, y, txt, transform=tr, fontsize=7.5, color=col, va="center", ha="left", clip_on=False,
                    gid=bd["style"] if inside else None)                   # कडेचा बाण (पट्टा काढलेला नाही) ⇒ legend मध्ये नाही
        ok = None
        span = 60 if keep(bd) else 2
        for k in [0] + [j * sg for j in range(1, span + 1) for sg in (1, -1)]:
            t.set_y(y + k * step)
            if lay.take(t, inside=False):
                ok = k
                break
        if ok is None:
            t.remove()
            dropped.append(bd["name"])
            continue
        if ok:                                                             # सरकवलेला label ⇒ पट्ट्याकडे लहान रेषा
            ax.plot([1.0, 1.003], [y, y + ok * step], transform=tr, color=col, lw=0.6, clip_on=False)
        shown.append(bd)
        labels.append({"kind": "band", "text": t.get_text(), "artist": t, "name": bd["name"]})
        if not inside:
            continue
        if bd["style"] == "broken":
            ax.plot([-0.5, nn - 0.5], [bd["price"]] * 2, color=col, lw=1.1, ls="--", gid="broken")
        elif bd["style"] == "target":
            ax.plot([-0.5, nn - 0.5], [bd["price"]] * 2, color=col, lw=1.3, ls=":", gid="target")
        else:
            ax.axhspan(bd["lo"], bd["hi"], color=col, alpha=0.10 if bd["style"] == "protected origin" else 0.15, lw=0, gid=bd["style"])
    pq = sp["protected"]
    if pq and ylo <= pq["price"] <= yhi and any(b["role"] == "protected" for b in shown):   # origin रेषा (label = पट्ट्याचा)
        a = max(pq["bar"], i0)
        ax.plot([x(a), nn - 0.5], [pq["price"]] * 2, color=C["protected origin"], lw=1.6, gid="protected origin")
        styles.add("protected origin")
    shown_in = {b["style"] for b in shown if ylo <= b["price"] <= yhi}
    styles = (styles - {b["style"] for b in bands}) | shown_in            # टाकलेले / कडेचे पट्टे legend मध्ये नाहीत
    if pq and any(b["role"] == "protected" for b in shown) and ylo <= pq["price"] <= yhi:
        styles.add("protected origin")
    lgd = legend(styles)
    lgd.set_loc(best[1])
    fig.canvas.draw()
    lay.boxes.append(lgd.get_window_extent(lay.r))
    lay.boxes.append(ax.title.get_window_extent(lay.r))

    wa_bars = {wv["bar"] for wv in sp.get("waves") or ()}                  # Q49: 5-wave पहिला पाय = "A" (पर्याय "1" फक्त debug)
    marked = set()
    for c in sp["boxes"]:                                                  # Abhi review: family वाचलेल्या pivots वर a / b / c (W X Y, a–e)
        if not c["label"]:
            continue
        marks = c.get("marks") or ()
        upper = False
        if c["state"] != "done" and any(c["start_bar"] <= b <= c["end_bar"] for b in wa_bars):
            # Q49: चालू counter-move चा पहिला पाय = wave A. Box चं "a" त्याच pivot वर ⇒ तीच count, मोठ्या अक्षरांत (A B C);
            # नाहीतर box चं तात्पुरतं family वाचन (उदा. triangle, A = "c") Q49 शी विसंगत ⇒ त्याची अक्षरं नाहीत, फक्त "A" (खाली)
            upper = any(mk["letter"] == "a" and mk["bar"] in wa_bars for mk in marks)
            if not upper:
                marks = ()
        for mk in marks:
            if mk["bar"] < i0:
                continue
            up = mk["kind"] == "H"
            sg = 1 if up else -1
            txt, kind = (mk["letter"].upper(), "wave_a") if upper else (mk["letter"], "wave")
            tries = [(x(mk["bar"]), mk["price"], "center", "bottom" if up else "top", (dx, sg * dy))
                     for dy, dx in ((3, 0), (3, 7), (3, -7), (12, 0))]
            t = _place(ax, lay, txt, tries, 9 if kind == "wave_a" else 8, "#1864ab", weight="bold")
            marked.add(mk["bar"])
            if t is None:
                dropped.append(txt)
            else:
                labels.append({"kind": kind, "text": txt, "artist": t, "bar": mk["bar"], "price": mk["price"]})
    for wv in sp.get("waves") or ():
        if wv["bar"] in marked:                                            # त्या pivot वर family अक्षर आधीच (a ⇒ A वर) ⇒ दुसरं नाही
            continue
        up = wv["kind"] == "H"
        sg = 1 if up else -1
        tries = [(x(wv["bar"]), wv["price"], "center", "bottom" if up else "top", (dx, sg * dy))
                 for dy, dx in ((3, 0), (3, 7), (3, -7), (12, 0))]
        t = _place(ax, lay, wv["label"], tries, 9, "#1864ab", weight="bold")
        if t is None:
            dropped.append(wv["label"])
        else:
            labels.append({"kind": "wave_a", "text": wv["label"], "artist": t, "bar": wv["bar"], "price": wv["price"]})
    # §5.1 / §5.2 / §5.5: box labels (चालू + आधीची) — box वर / आत, collision नाही ⇒ label नाही
    fs = 7.5 if nn <= 200 else 7
    for c in sp["boxes"]:
        if not c["label"]:
            continue
        a, b = max(c["start_bar"], i0), c["end_bar"] if c["state"] == "done" else v["n"] - 1
        xa, xb = x(a) - 0.5, x(b) + 0.5
        y0, y1 = sorted((c["start_price"], c["end_price"]))
        above = [(xa, y1, "left", "bottom", (0, 3)), (xb, y1, "right", "bottom", (0, 3))]
        below = [(xa, y0, "left", "top", (0, -3)), (xb, y0, "right", "top", (0, -3))]
        inner = [(xa, y1, "left", "top", (3, -3)), (xb, y1, "right", "top", (-3, -3)), (xa, y0, "left", "bottom", (3, 3)),
                 (xb, y0, "right", "bottom", (-3, 3))]
        far = [(px, py, ha, va, (dx, dy + (12 * k if dy > 0 else -12 * k))) for k in (1, 2, 3)
               for px, py, ha, va, (dx, dy) in above + below]
        tries = (inner + above + below if c["state"] != "done" else above + below + inner) + far
        t = _place(ax, lay, c["label"], tries, fs, C["counter-move (in progress)"] if c["state"] != "done" else "#1864ab")
        if t is None:
            dropped.append(c["label"])
        else:
            labels.append({"kind": "correction", "text": c["label"], "artist": t})
    for pb in sp["pullbacks"]:                                             # §5.2: एकच "pullback" खूण (full ⇒ सगळ्या)
        up = pb["kind"] == "H"
        px, py = x(pb["bar"]), pb["price"]
        tries = [(px, py, ha, "bottom" if up else "top", (dx, (6 + 10 * k) * (1 if up else -1))) for k in range(10)
                 for ha, dx in (("center", 0), ("right", -4), ("left", 4))]   # leader रेषा ⇒ लांब offset चालतो
        txt = pb.get("text") or "pullback"
        t = _place(ax, lay, txt, tries, 7, C["pullback"])                 # मजकूरच स्वतःचं स्पष्टीकरण ⇒ legend नाही
        if t is None:
            dropped.append(txt)
        else:
            labels.append({"kind": "correction", "text": txt, "artist": t, "bar": pb["bar"], "price": pb["price"]})
            bb = t.get_window_extent(lay.r)                                # label सरकलेला ⇒ टोकापासून label पर्यंत लहान leader रेषा
            ex, ey = ax.transData.inverted().transform([(bb.x0 + bb.x1) / 2, bb.y0 if up else bb.y1])
            ax.plot([px, ex], [py, ey], color=C["pullback"], lw=0.6, alpha=0.8)
    for lg in sp["impulses"]:                                              # चालू leg: "decline in progress — impulse not verified"
        if lg.get("state") != "in progress":
            continue
        word = "decline" if lg["dir"] < 0 else "advance"
        txt = "impulse (5 waves)" if lg.get("verified") else f"{word} in progress — impulse not verified"   # (चालू leg)
        pts = [p for p in leg_window_path(lg, i0, npts) if p[0] >= i0]
        dn = lg["dir"] < 0
        tries = []
        for b_, y_ in reversed(pts):
            for dy in (6, 16, 28):
                tries += [(x(b_), y_, ha, "top" if dn else "bottom", (0, -dy if dn else dy)) for ha in ("right", "center", "left")]
        t = _place(ax, lay, txt, tries, 7.5, C["leg in progress"] if not lg.get("verified") else C["impulse leg"])
        if t is None:
            dropped.append(txt)
        else:
            labels.append({"kind": "leg", "text": txt, "artist": t})
    for row, (name, runs_) in enumerate((("degree-aware", sp["strip"]["degree-aware"]), ("Dow minor", sp["strip"]["Dow minor"]))):
        for a, b, st in runs_:
            if b < i0:
                continue
            a2 = max(a, i0)
            bx.add_patch(plt.Rectangle((x(a2) - 0.5, row), b - a2 + 1, 0.9, color=STATE_COLOR.get(st, "#fff"), lw=0))
            if b - a2 >= max(8, nn // 14):                                 # लहान runs वर नाव नाही (गर्दी)
                bx.text(x(a2) + (b - a2) / 2, row + 0.45, st.replace("· impulse", "· trend leg"), ha="center", va="center",
                        fontsize=7)                                         # CD11: engine phase "impulse" = Dow trend leg
        bx.text(-1, row + 0.45, name, ha="right", va="center", fontsize=8)
    bx.set_ylim(0, 2)
    bx.set_yticks([])
    ax.grid(alpha=0.12)
    _xticks(bx, fr["timestamp"].to_numpy(), max(1, len(fr) // 24))
    return fig, {"ax": ax, "bx": bx, "frame": fr, "labels": labels, "styles": styles, "dropped": dropped, "spec": sp}


def leg_window_path(lg, i0, max_points=15):
    """Window मधला leg चा भाग: leg चे स्वतःचे pivots (window आधीचा एक बिंदू कापण्यासाठी) ⇒ कमाल max_points (मोठे swings च)."""
    from . import daily_swings as DS
    pts = [tuple(p) for p in (lg.get("pivots") or lg.get("path") or [[lg["from"], lg["p0"]], [lg["to"], lg["p1"]]])]
    k = next((j for j, (b, _) in enumerate(pts) if b >= i0), len(pts) - 1)
    return [list(p) for p in DS.coarse_path(pts[max(k - 1, 0):], max_points)]


def _clip_path(path, i0):
    """[[bar, price], …] ⇒ window (i0 पासून) मधले x / y; i0 ओलांडणारा भाग i0 ला कापतो."""
    xs, ys = [], []
    for k, (b, p) in enumerate(path):
        if b >= i0:
            if not xs and k > 0 and path[k - 1][0] < i0:
                (b0, p0) = path[k - 1]
                xs.append(0)
                ys.append(p0 + (p - p0) * (i0 - b0) / max(b - b0, 1))
            xs.append(b - i0)
            ys.append(p)
    return xs, ys


def _place(ax, lay, text, tries, fs, color, weight="normal"):
    """पहिली मोकळी जागा (candles / मजकूर / legend वर नाही, axes आत) ⇒ text artist; कुठेच नाही ⇒ None (label सोडतो)."""
    for px, py, ha, va, off in tries:
        t = ax.annotate(text, (px, py), textcoords="offset points", xytext=off, ha=ha, va=va, fontsize=fs, color=color,
                        annotation_clip=False, fontweight=weight)
        if lay.take(t):
            return t
        t.remove()
    return None


def daily_swings_render(v, title, full=False):
    """daily_swings_fig ⇒ (PNG, meta) — meta = chart वर प्रत्यक्ष काय आलं (JSON `chart` / Vision facts): bands_drawn, dropped, labels."""
    fig, info = daily_swings_fig(v, title, full=full)
    meta = {"bands_drawn": [x["name"] for x in info["labels"] if x["kind"] == "band"], "dropped": list(info["dropped"]),
            "labels": [x["text"].strip() for x in info["labels"]]}
    return _png(fig), meta


def daily_swings_png(v, title, full=False):
    """daily_swings_fig ⇒ PNG (Telegram default; full=True ⇒ सगळं, debug)."""
    return daily_swings_render(v, title, full=full)[0]


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
