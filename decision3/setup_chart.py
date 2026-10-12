"""decision3/setup_chart.py — V22 setup review chart (एका setup ची एक image) + caption. फक्त वाचन / review — निर्णयात नाही, order नाही.

🎓 नियम (Abhi):
  • Chart वरचा सगळा मजकूर English. P&L / outcome नाही.
  • 15M panel setup bar वर संपतो — त्यानंतरची candle नाही (volume pane मध्येही नाही). Daily panel: setup दिवस = setup bar पर्यंतची अर्धवट
    candle; NIFTY holdout (sealed) Daily bars कधीच दाखवत नाही (setup holdout नंतरचा असेल तर Daily panel holdout नंतरपासूनच).
  • Q44 maturity target फक्त Daily panel आणि caption / footer मध्ये — 15M entry panel वर रेघ नाही (Abhi: फक्त caption).
  • Volume (decision3/volume_pane.py, एकच implementation): 15M खाली, lower-timeframe (5M) panel खाली आणि Daily खाली. Index ⇒ futures
    volume, MCX ⇒ contract चा स्वतःचा; नाही ⇒ "volume: NA (grade cap B)". Study window (area arrival → commitment) trend-side / counter-side
    रंग, window सरासरीची dashed रेघ, commitment bar ची खूण. Caption / footer मध्ये एकच volume ओळ.
Script: scripts/v22_setup_charts.py."""
from dataclasses import dataclass, field

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from . import daily as DD  # noqa: E402
from . import volume_pane as VP  # noqa: E402

UPC, DNC = "#1f8a4c", "#c8323c"
C = {"prot": "#6a3fd6", "parent": "#8a6fc2", "target": "#d97a1e", "level": "#2f6db5", "entry": "#1d4f91", "sl": "#c8323c",
     "tgt": "#1f8a4c", "setup": "#f2c230", "ink": "#222222", "muted": "#666666"}
TREND_BG = {"UP": "#cfe9d6", "DOWN": "#f4cccc", "RANGE": "#f6e3b4", "NEUTRAL": "#dddddd", "UNKNOWN": "#eeeeee"}
LTF_MIN = 5                                                                 # 15M setup ⇒ 5M lower timeframe (c1 mapping)
LTF_BARS = 60

NOTE_EN = [
    ("Weekly", lambda n: n.split("=")[0].strip() + " runs against " + n.split("=")[1].split("विरुद्ध")[0].strip() + " (correction) => cap B"),
    ("protected origin close ने तुटला", lambda n: "protected origin broken on close - correction running, no reverse impulse yet => cap B"),
    ("impulse origin close ने तुटला", lambda n: "impulse origin broken on close, parent held - same-degree correction => cap B"),
    ("origin धोक्यात", lambda n: "correction near protected origin (origin at risk) => new entries weak"),
    ("continuation evidence", lambda n: n),
    ("impulse mature", lambda n: "impulse mature - near Q44 target => new entries weak"),
    ("Daily वाचता येत नाही", lambda n: "Daily unreadable => Weekly fallback (cap B)"),
]
WHY_OPEN = {"उलट D1 swing confirm": "opposite D1 swing confirmed", "trade-बाजूच्या level मध्ये": "inside trade-side level"}


@dataclass
class SetupData:
    """एका symbol चा डेटा. m15 / daily_df: timestamp, bar_end, open, high, low, close. states: decision3.daily states (V22.daily).
    m1: 1m bars (LTF panel; नाही ⇒ LTF panel नाही). fut: intraday volume rows (timestamp, volume) — index ⇒ futures, MCX ⇒ contract.
    daily_vol: पूर्ण-दिवस volume (timestamp, volume) — setup दिवस कधीच यातून नाही (भविष्य), fut मधून setup bar पर्यंतची बेरीज."""
    symbol: str
    m15: pd.DataFrame
    daily_df: pd.DataFrame
    states: list
    m1: pd.DataFrame = None
    fut: pd.DataFrame = None
    daily_vol: pd.DataFrame = None
    sealed: object = None                                                   # fn(ts) -> bool (NIFTY holdout); None ⇒ HI.sealed_fn(symbol)
    state_at: object = None                                                 # fn(ts) -> DState; None ⇒ DD.state_at(states, ts)
    info: dict = field(default_factory=dict)                                # setup ts ⇒ confirmation (a2 / c0 / c1) dict, असेल तर

    def __post_init__(self):
        for df in (self.m15, self.daily_df):
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["bar_end"] = pd.to_datetime(df["bar_end"])
        if self.sealed is None:
            from . import history as HI
            self.sealed = HI.sealed_fn(self.symbol) or (lambda ts: False)
        if self.state_at is None:
            self.state_at = lambda ts: DD.state_at(self.states, ts)


def note_en(n):
    for key, f in NOTE_EN:
        if key in n:
            try:
                return f(n)
            except Exception:                                               # noqa: BLE001
                break
    return "".join(ch for ch in n if ord(ch) < 0x0900 or ord(ch) > 0x097F).strip()


def phase_en(st):
    if st.phase is None:
        return st.trend
    if st.phase == "impulse":
        return "impulse" + (" (lower-degree pullback in progress)" if st.counter == "pullback" else "")
    if st.phase == "correction" and st.counter == "correction":
        return f"same-degree correction (impulse origin broken, parent {st.parent.price:,.0f} held; leg {st.corr_label})"
    if st.phase == "correction":
        return f"same-degree correction candidate (leg {st.corr_label})"
    return f"origin broken on close, waiting for reverse impulse (leg {st.corr_label or '-'})"


def side_of(r):
    return "BULL PUT" if r["level"]["role"] == "support" else "BEAR CALL"


def fmt(x):
    return "-" if x is None else f"{float(x):,.0f}"


def candles(ax, x, O, H, L, Cc, w=0.62, alpha=1.0, lw=0.8):
    for xi, o_, h, l_, c in zip(x, O, H, L, Cc):
        col = UPC if c >= o_ else DNC
        ax.vlines(xi, l_, h, color=col, lw=lw, alpha=alpha, zorder=3)
        ax.add_patch(Rectangle((xi - w / 2, min(o_, c)), w, max(abs(c - o_), 1e-6), facecolor=col, edgecolor=col, lw=0.4,
                               alpha=alpha, zorder=4))


def spread_labels(items, lo, hi, min_gap):
    """items [(y, text, color[, x])] ⇒ एकमेकांवर न येणारे y (क्रम तोच, [lo, hi] आत)."""
    items = sorted([tuple(z) + (None,) * (4 - len(z)) for z in items], key=lambda z: z[0])
    ys = [min(max(z[0], lo + min_gap / 2), hi - min_gap / 2) for z in items]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + min_gap)
    over = ys[-1] - (hi - min_gap / 2) if ys else 0
    if over > 0:
        ys = [y - over for y in ys]
        for i in range(len(ys) - 2, -1, -1):
            ys[i] = min(ys[i], ys[i + 1] - min_gap)
    return [(y, t, c, y0, xa) for (y0, t, c, xa), y in zip(items, ys)]


def _area(r):
    lv = r["level"]
    return float(lv["lo"]), float(lv["hi"])


def _dir(r):
    return 1 if r["level"]["role"] == "support" else -1


def _dlab(D, day):
    return "before window" if D.sealed(day) else f"{pd.Timestamp(day):%d %b %y}"


def daily_hist(D, day, n=119):
    """setup दिवसाआधीचे दाखवण्याजोगे Daily bars: शेवटचे n, sealed (holdout) नाहीत आणि शेवटच्या sealed दिवसानंतरचेच (सलग)."""
    h = D.daily_df[D.daily_df["timestamp"].dt.normalize() < day]
    sealed = np.array([bool(D.sealed(t)) for t in h["timestamp"]], dtype=bool)
    if sealed.any():
        h = h.iloc[int(np.flatnonzero(sealed)[-1]) + 1:]
    h = h.tail(n).reset_index(drop=True)
    assert not any(D.sealed(t) for t in h["timestamp"])
    return h


def structure_move(D, day, n=60):
    """setup दिवसाआधीच्या शेवटच्या n दाखवण्याजोग्या Daily closes चा बदल % (holdout कधीच नाही) ⇒ (pct, sessions)."""
    h = daily_hist(D, pd.Timestamp(day).normalize(), n)
    if len(h) < 2:
        return 0.0, len(h)
    return (h["close"].iloc[-1] / h["close"].iloc[0] - 1) * 100, len(h)


def trend_first_status(D, r):
    pct, n = structure_move(D, r["ts"])
    side = side_of(r)
    against = (side == "BEAR CALL" and pct > 5) or (side == "BULL PUT" and pct < -5)
    txt = (f"Trend-first check: {side.lower()} vs Daily {n}-session move {pct:+.1f}% (Weekly {r['weekly_trend']}) - "
           + ("DEFECT FLAG: side against the multi-month Daily structure" if against else "side agrees with the Daily structure"))
    return ("DEFECT FLAG: against Daily structure" if against else "trend-first OK"), txt


# ------------------------------------------------------------------------------------------------ volume (shared helper वापरून)
def m15_frame(D, setup_ts, sessions=3):
    day = setup_ts.normalize()
    m15 = D.m15
    days = sorted(m15.loc[m15["timestamp"].dt.normalize() <= day, "timestamp"].dt.normalize().unique())[-sessions:]
    w = m15[(m15["timestamp"].dt.normalize().isin(days)) & (m15["timestamp"] <= setup_ts)].copy()
    assert len(w) and w["timestamp"].max() == setup_ts                     # setup bar नंतर काहीच नाही
    return w


def m15_study(D, r, w, setup_end):
    """15M pane: futures / own volume (setup bar च्या शेवटापर्यंतच), window = engine चं (info) नाहीतर area arrival → setup bar."""
    vol = VP.bar_volume(w["timestamp"], w["bar_end"], D.fut, asof=setup_end)
    info = {**r, **(D.info.get(str(r["ts"])) or {})}
    return VP.study(w.reset_index(drop=True), vol=vol, info=info, area=_area(r), d=_dir(r), commit=len(w) - 1, symbol=D.symbol)


def ltf_frame(D, setup_end):
    """5M bars (09:15-anchored) — फक्त setup bar संपेपर्यंत पूर्ण झालेले 1m bars वरून; शेवटचे LTF_BARS."""
    if D.m1 is None or not len(D.m1):
        return None
    m1 = D.m1[["timestamp", "open", "high", "low", "close"]].copy()
    m1["timestamp"] = pd.to_datetime(m1["timestamp"])
    m1 = m1[(m1["timestamp"] + pd.Timedelta(minutes=1) <= setup_end) & (m1["timestamp"] >= setup_end.normalize() - pd.Timedelta(days=7))]
    if not len(m1):
        return None
    day = m1["timestamp"].dt.normalize()
    k = ((m1["timestamp"] - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(minutes=LTF_MIN)).astype(int)
    m1["start"] = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(minutes=LTF_MIN)
    g = m1.groupby("start").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index()
    g = g.rename(columns={"start": "timestamp"})
    g["bar_end"] = g["timestamp"] + pd.Timedelta(minutes=LTF_MIN)
    g = g[g["bar_end"] <= setup_end].tail(LTF_BARS).reset_index(drop=True)
    return g if len(g) else None


def ltf_study(D, r, g, arm_ts, setup_end):
    """5M pane: त्याच time window (15M arrival → setup bar शेवट) मधले 5M bars. Mark: c1 चा CHoCH bar (info मध्ये असेल तर) नाहीतर
    शेवटचा 5M bar (setup bar चा close)."""
    vol = VP.bar_volume(g["timestamp"], g["bar_end"], D.fut, asof=setup_end)
    ni = VP.normalize_info(D.info.get(str(r["ts"])) or {})
    commit = VP.index_at(g["timestamp"], ni["ltf_ts"]) if ni["ltf_ts"] is not None else None
    what = "CHoCH bar" if commit is not None else "last 5M bar"
    commit = len(g) - 1 if commit is None else commit
    arm = VP.index_at(g["timestamp"], arm_ts) if arm_ts is not None else None
    if arm is None and arm_ts is not None and pd.Timestamp(arm_ts) < g["timestamp"].iloc[0]:
        arm = 0
    st = VP.study(g, vol=vol, area=_area(r), d=_dir(r), commit=commit, arm=arm if arm is not None and arm <= commit else None,
                  symbol=D.symbol)
    return st, what


def daily_volume(D, rows, day, setup_end):
    """Daily pane volume: आधीचे दिवस daily_vol मधून (पूर्ण दिवस); setup दिवस फक्त fut मधून setup bar पर्यंतची बेरीज (नाही ⇒ NaN).
    एकक: fut (Upstox) = quantity, bhavcopy = contracts ⇒ daily_vol मध्ये `lot_size` असेल तर quantity (contracts × lot); नसेल तर
    contracts आणि setup दिवसाचा (quantity) bar NA — दोन एकक एकत्र कधीच नाहीत."""
    v = np.full(len(rows), np.nan)
    qty = True
    if D.daily_vol is not None and len(D.daily_vol):
        x = D.daily_vol.assign(day=pd.to_datetime(D.daily_vol["timestamp"]).dt.normalize())
        days = {pd.Timestamp(t).normalize() for t in rows["timestamp"].iloc[:-1]}
        xs = x[x["day"].isin(days)]
        lot = pd.to_numeric(xs["lot_size"], errors="coerce") if "lot_size" in xs.columns else pd.Series(np.nan, index=xs.index)
        qty = bool(len(xs)) and bool(lot.notna().all())
        dv = (xs["volume"] * (lot if qty else 1.0)).groupby(xs["day"]).sum()
        for i, t in enumerate(rows["timestamp"].iloc[:-1]):
            v[i] = dv.get(pd.Timestamp(t).normalize(), np.nan)
    if qty:
        v[-1] = VP.bar_volume([day], [setup_end], D.fut, asof=setup_end)[0]
    if qty and D.fut is not None and len(D.fut):                           # daily_vol नसलेले दिवस: fut च्या पूर्ण दिवसाची बेरीज
        for i, t in enumerate(rows["timestamp"].iloc[:-1]):
            if not np.isfinite(v[i]):
                d0 = pd.Timestamp(t).normalize()
                v[i] = VP.bar_volume([d0], [d0 + pd.Timedelta(days=1)], D.fut)[0]
    return v


# ------------------------------------------------------------------------------------------------ panels
def daily_panel(D, ax, axv, axs, r, st, setup_ts, setup_end):
    day = setup_ts.normalize()
    hist = daily_hist(D, day)
    part = D.m15[(D.m15["timestamp"].dt.normalize() == day) & (D.m15["timestamp"] <= setup_ts)]
    assert len(part) and part["timestamp"].max() == setup_ts
    rows = hist[["timestamp", "open", "high", "low", "close"]].copy()
    rows.loc[len(rows)] = [day, part["open"].iloc[0], part["high"].max(), part["low"].min(), part["close"].iloc[-1]]
    n = len(rows)
    x = np.arange(n)
    candles(ax, x[:-1], rows.open[:-1], rows.high[:-1], rows.low[:-1], rows.close[:-1])
    candles(ax, x[-1:], rows.open[-1:], rows.high[-1:], rows.low[-1:], rows.close[-1:], alpha=0.55)
    ax.axvspan(n - 1.5, n - 0.5, color=C["setup"], alpha=0.25, zorder=1)
    lo, hi = rows.low.min(), rows.high.max()
    rng = hi - lo
    ylo, yhi = lo - 0.04 * rng, hi + 0.04 * rng
    day_x = {pd.Timestamp(t).normalize(): i for i, t in enumerate(rows.timestamp)}

    def xof(ts):
        ts = pd.Timestamp(ts).normalize()
        return day_x.get(ts, 0 if ts < rows.timestamp.iloc[0] else None)

    lines = []
    if st.protected is not None:
        lines.append((st.protected.price, f"protected {st.protected.kind} {st.protected.price:,.0f} ({_dlab(D, st.protected.day)})",
                      C["prot"], "-", xof(st.protected.day)))
    if st.parent is not None and (st.protected is None or abs(st.parent.price - st.protected.price) > 1e-6):
        lines.append((st.parent.price, f"parent {st.parent.kind} {st.parent.price:,.0f} ({_dlab(D, st.parent.day)})", C["parent"], "--",
                      xof(st.parent.day)))
    for tg in st.targets or ():
        lines.append((tg, f"Q44 target {tg:,.0f}", C["target"], "--", 0))   # Q44: Daily वरच (15M वर नाही)
    off = []
    for y, lab, col, ls, x0 in lines:
        if lo - 0.5 * rng <= y <= hi + 0.5 * rng:
            ylo, yhi = min(ylo, y - 0.03 * rng), max(yhi, y + 0.03 * rng)
    labs = []
    for y, lab, col, ls, x0 in lines:
        if ylo <= y <= yhi:
            ax.hlines(y, x0 if x0 is not None else 0, n - 0.5, color=col, ls=ls, lw=1.6, zorder=5)
            labs.append((y, lab, col))
        else:
            off.append(f"{lab} {'above' if y > yhi else 'below'} chart")
    lv = r["level"]
    ax.add_patch(Rectangle((n - 12.5, lv["lo"]), 12, lv["hi"] - lv["lo"], color=C["level"], alpha=0.18, zorder=2, lw=0))
    labs.append(((lv["lo"] + lv["hi"]) / 2, f"1H {lv['role']} {lv['lo']:,.0f}-{lv['hi']:,.0f}", C["level"]))
    if st.imp_end is not None and xof(st.imp_end.day) not in (None, 0):
        xi = xof(st.imp_end.day)
        ax.plot(xi, st.imp_end.price, marker="o", ms=7, mfc="none", mec=C["target"], mew=1.6, zorder=6)
        ax.annotate("impulse end", (xi, st.imp_end.price), xytext=(-8, -4 if st.imp_end.kind == "H" else 4), ha="right",
                    textcoords="offset points", fontsize=8, color=C["target"])
    for p in st.pivots or []:
        xi = xof(p.day)
        if xi not in (None, 0) and p.known_at <= setup_end:
            ax.plot(xi, p.price * (1.004 if p.kind == "H" else 0.996), marker="v" if p.kind == "H" else "^", ms=4, color="#888888",
                    zorder=6)
    if getattr(st, "corr_zone", None) is not None:
        zlo, zhi, zb = st.corr_zone
        x0 = xof(D.daily_df["timestamp"].iloc[int(zb)]) if 0 <= int(zb) < len(D.daily_df) else None
        ax.axhspan(zlo, zhi, xmin=((x0 or 0) + 0.5) / (n + 1), xmax=1, color="#9a9a9a", alpha=0.15, zorder=1)
        labs.append(((zlo + zhi) / 2, f"sharp zone {zlo:,.0f}-{zhi:,.0f}", "#555555"))
    ax.set_ylim(ylo, yhi)
    XR = n + max(34, n // 3)
    ax.set_xlim(-1, XR)
    for y, t, c, y0, _ in spread_labels(labs, ylo, yhi, 0.045 * (yhi - ylo)):
        ax.annotate(t, xy=(n - 0.5, y0), xytext=(n + 1.5, y), textcoords="data", fontsize=8, color=c, va="center",
                    annotation_clip=False, arrowprops=dict(arrowstyle="-", color=c, lw=0.6, alpha=0.6))
    if off:
        ax.text(0.01, 0.01, "Off chart: " + "; ".join(off), transform=ax.transAxes, fontsize=8, color=C["muted"], va="bottom")
    ax.set_title(f"Daily (last {n} sessions; yellow = setup day, partial to the setup bar) - state at the setup bar: {st.trend} "
                 f"{phase_en(st)}", fontsize=9, loc="left")
    ax.grid(alpha=0.25)
    VP.draw_daily_mpl(axv, daily_volume(D, rows, day, setup_end), x=x, source=VP.source_label(D.symbol))
    axv.set_xlim(-1, XR)
    seg = []
    for i, be in enumerate(list(hist["bar_end"]) + [setup_end]):       # trend strip: त्या दिवसाच्या close ला माहीत state
        s_ = D.state_at(be)
        lab = s_.trend + ("" if s_.phase in (None, "impulse") else " corr" if s_.phase == "correction" else " broken")
        if seg and seg[-1][2] == lab:
            seg[-1][1] = i
        else:
            seg.append([i, i, lab, s_.trend])
    for a, b, lab, tr in seg:
        axs.add_patch(Rectangle((a - 0.5, 0), b - a + 1, 1, facecolor=TREND_BG.get(tr, "#eeeeee"), edgecolor="white", lw=1,
                                hatch="//" if " " in lab else None))
        if b - a >= 6:
            axs.text((a + b) / 2, 0.5, lab, ha="center", va="center", fontsize=7.5, color=C["ink"])
    axs.set_xlim(-1, XR)
    axs.set_ylim(0, 1)
    axs.set_yticks([])
    axs.set_ylabel("Daily\nstate", fontsize=7.5, rotation=0, ha="right", va="center")
    ticks = list(range(0, n, max(1, n // 8)))
    axs.set_xticks(ticks)
    axs.set_xticklabels([rows.timestamp.iloc[i].strftime("%d %b %y") for i in ticks], fontsize=7.5)
    ax.tick_params(labelbottom=False, labelsize=8)
    axv.tick_params(labelbottom=False)


def _session_ticks(ax, ts, n, hours=(11, 13)):
    dn = ts.dt.normalize().to_numpy()
    starts = [i for i in range(n) if i == 0 or dn[i] != dn[i - 1]]
    ticks, tlab = [], []
    for i in range(n):
        t = ts.iloc[i]
        if i in starts:
            ticks.append(i)
            tlab.append(t.strftime("%d %b\n%H:%M"))
        elif t.minute == 0 and t.hour in hours:
            ticks.append(i)
            tlab.append(t.strftime("%H:%M"))
    ax.set_xticks(ticks)
    ax.set_xticklabels(tlab, fontsize=7.5)
    return starts


def m15_panel(D, ax, axv, r, st, setup_ts, w, vst):
    idx = list(w.index)
    n = len(w)
    x = np.arange(n)
    bar_x = {b: i for i, b in enumerate(idx)}
    candles(ax, x, w.open, w.high, w.low, w.close, w=0.66, lw=0.7)
    sx = n - 1
    ax.axvspan(sx - 0.5, sx + 0.5, color=C["setup"], alpha=0.35, zorder=1)
    rk, lv, K = r.get("risk") or {}, r["level"], r.get("K") or {}
    lo, hi = w.low.min(), w.high.max()
    vals = [lv["lo"], lv["hi"]] + [rk.get(k) for k in ("entry", "sl") if rk.get(k) is not None]
    rng0 = hi - lo
    tg = rk.get("target")
    if tg is not None and lo - 2 * rng0 <= tg <= hi + 2 * rng0:
        vals.append(tg)
    ylo, yhi = min([lo] + vals), max([hi] + vals)
    pad = 0.05 * (yhi - ylo)
    ylo, yhi = ylo - pad, yhi + pad
    right = n + max(24, n // 3)                                            # labels साठी रिकामी जागा (candles नाहीत)
    ax.axhspan(lv["lo"], lv["hi"], color=C["level"], alpha=0.14, zorder=2)
    stars = f", {lv['sweeps']} sweeps" if lv.get("sweeps") else ""
    ax.text(0.5, lv["hi"], f"1H {lv['role']} {lv['lo']:,.0f}-{lv['hi']:,.0f} ({'+'.join(lv['births'])}{stars}, "
            f"{'fresh' if lv['fresh'] else 'tested'})", fontsize=8, color=C["level"], va="bottom", zorder=7,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=1))
    if vst["arm"] is not None:                                             # study window (volume pane सारखाच) — वर पातळ पट्टी
        ax.axvspan(vst["arm"] - 0.5, vst["commit"] + 0.5, ymin=0.985, ymax=1.0, color=VP.MPL["trend"], alpha=0.6, zorder=8)
    labs = []
    for key, name, col, ls in (("entry", "entry", C["entry"], "-"), ("sl", "SL", C["sl"], "-"), ("target", "target", C["tgt"], "--")):
        v = rk.get(key)
        if v is None:
            continue
        if ylo <= v <= yhi:
            ax.hlines(v, sx - 0.5, sx + 3, color=col, lw=1.5, ls=ls, zorder=6)
            labs.append((v, f"{name} {v:,.0f}", col))
        else:
            labs.append((yhi if v > yhi else ylo, f"{name} {v:,.0f} ({'above' if v > yhi else 'below'}, off chart)", col))
    if rk.get("rr") is not None and rk.get("entry") is not None:
        labs.append(((rk["entry"] + rk["sl"]) / 2, f"R:R {rk['rr']:.2f}", C["ink"]))
    for nm, b, p, col in (("K extreme", K.get("k_ext_bar"), K.get("k_ext"), "#555555"),
                          ("impulse end (I_end)", K.get("i_end_bar"), K.get("i_end"), C["target"])):
        if b is not None and b in bar_x:
            ax.plot(bar_x[b], p, marker="o", ms=7, mfc="none", mec=col, mew=1.5, zorder=7)
            labs.append((p, f"{nm} {p:,.0f}", col, bar_x[b]))
    tl = r.get("trendline")
    if tl and tl.get("p1") and tl["p1"][0] in bar_x:
        (b1, p1), slope = tl["p1"], tl["slope"]
        xs = np.array([bar_x[b1], sx])
        ys = p1 + slope * np.array([0, idx[-1] - b1])
        ax.plot(xs, ys, color="#555555", lw=1, ls=":", zorder=5)
        labs.append((ys[-1], f"K line ({tl['touches']} touches, {'broken' if tl['broken'] else 'intact'})", "#555555"))
    if st.protected is not None and ylo <= st.protected.price <= yhi:
        ax.axhline(st.protected.price, color=C["prot"], lw=1.2, zorder=5)
        labs.append((st.protected.price, f"Daily protected {st.protected.price:,.0f}", C["prot"]))
    # Q44 maturity target: 15M entry panel वर नाही (Abhi) — फक्त caption / footer.
    for y, t, c, y0, xa in spread_labels(labs, ylo, yhi, 0.05 * (yhi - ylo)):
        ax.annotate(t, xy=(sx + 3 if xa is None else xa, min(max(y0, ylo), yhi)), xytext=(sx + 4, y), textcoords="data", fontsize=8, color=c, va="center",
                    annotation_clip=False, arrowprops=dict(arrowstyle="-", color=c, lw=0.6, alpha=0.6))
    up = side_of(r) == "BULL PUT"
    mark_y = w.low.iloc[-1] - 0.035 * (yhi - ylo) if up else w.high.iloc[-1] + 0.035 * (yhi - ylo)
    ax.plot(sx, mark_y, marker="^" if up else "v", ms=10, color="#b08400", zorder=8)
    starts = _session_ticks(axv, w["timestamp"], n)
    for s0 in starts[1:]:
        ax.axvline(s0 - 0.5, color="#999999", lw=0.8, ls="--", zorder=1)
        axv.axvline(s0 - 0.5, color="#999999", lw=0.8, ls="--", zorder=1)
    ax.set_xlim(-1, right)
    ax.set_ylim(ylo, yhi)
    ax.grid(alpha=0.25)
    ax.tick_params(labelsize=8, labelbottom=False)
    ax.set_title(f"15M - setup day + 2 prior sessions, ends at the setup bar ({setup_ts:%H:%M}); no candles after it", fontsize=9.5, loc="left")
    VP.draw_mpl(axv, vst, x=x, xlim=(-1, right), title=f"15M volume ({VP.source_label(D.symbol)})")
    axv.set_xlim(-1, right)


def ltf_panel(D, ax, axv, r, g, vst, what, setup_end):
    n = len(g)
    x = np.arange(n)
    candles(ax, x, g.open, g.high, g.low, g.close, w=0.66, lw=0.7)
    lv = r["level"]
    ax.axhspan(lv["lo"], lv["hi"], color=C["level"], alpha=0.14, zorder=2)
    span = [i for i in range(n) if g["timestamp"].iloc[i] >= setup_end - pd.Timedelta(minutes=15)]   # setup (15M) bar चे 5M bars
    if span:
        ax.axvspan(span[0] - 0.5, span[-1] + 0.5, color=C["setup"], alpha=0.35, zorder=1)
    lo, hi = min(g.low.min(), lv["lo"]), max(g.high.max(), lv["hi"])
    pad = 0.06 * (hi - lo)
    ax.set_ylim(lo - pad, hi + pad)
    right = n + max(10, n // 6)
    ax.set_xlim(-1, right)
    if vst["arm"] is not None:
        ax.axvspan(vst["arm"] - 0.5, vst["commit"] + 0.5, ymin=0.985, ymax=1.0, color=VP.MPL["trend"], alpha=0.6, zorder=8)
    starts = _session_ticks(axv, g["timestamp"], n, hours=(10, 11, 12, 13, 14))
    for s0 in starts[1:]:
        ax.axvline(s0 - 0.5, color="#999999", lw=0.8, ls="--", zorder=1)
        axv.axvline(s0 - 0.5, color="#999999", lw=0.8, ls="--", zorder=1)
    ax.grid(alpha=0.25)
    ax.tick_params(labelsize=8, labelbottom=False)
    ax.set_title(f"{LTF_MIN}M (lower timeframe) - ends at the setup bar close ({setup_end:%H:%M}); yellow = the setup bar's {LTF_MIN}M bars",
                 fontsize=9, loc="left")
    VP.draw_mpl(axv, vst, x=x, xlim=(-1, right), commit_what=what, title=f"{LTF_MIN}M volume ({VP.source_label(D.symbol)})")
    axv.set_xlim(-1, right)


# ------------------------------------------------------------------------------------------------ footer / caption
def footer_lines(r, st, status, vline):
    chk = r["checklist"]
    lv, K, rk, cm = r["level"], r.get("K") or {}, r.get("risk") or {}, r.get("commit") or {}
    ps = chk.get("④", [None, ""])[1]
    ps = ps[ps.find("power shift"):] if "power shift" in ps else "-"
    tl = r.get("trendline")
    why_open = WHY_OPEN.get(K.get("why_open"), K.get("why_open"))
    notes = [note_en(n) for n in r.get("trend_notes") or []]
    return [f"(1) Daily {st.trend}: {phase_en(st)} · protected {fmt(getattr(st.protected, 'price', None))} · Weekly {r['weekly_trend']} · "
            f"trend cap {r['trend_cap'] or 'none'} · mature {'YES' if r['mature'] else 'no'} · Q44 target "
            f"{' / '.join(fmt(t) for t in r['maturity_targets']) or 'none'} (Daily panel only)",
            "    trend notes: " + ("; ".join(notes) if notes else "none"),
            f"(2) 1H {lv['role']} {lv['lo']:,.0f}-{lv['hi']:,.0f} (born {'+'.join(lv['births'])}, tests {lv.get('tests')}, sweeps {lv.get('sweeps')}, "
            f"{'fresh' if lv['fresh'] else 'not fresh'})   (3) K pullback open ({why_open}), leg {K.get('legs')}   (4) {ps}",
            f"(5) K line: {'none' if not tl else ('broken (grade +)' if tl['broken'] else 'intact')}   (6) commitment {cm.get('form')} grade "
            f"{cm.get('grade')}   (7) R:R {rk.get('rr')} · entry {fmt(rk.get('entry'))} / SL {fmt(rk.get('sl'))} / target {fmt(rk.get('target'))}",
            f"(8) {vline}",
            f"Conviction {r['conviction']} (score {r.get('conv_score')}) · missing: {', '.join(r.get('missing') or []) or 'none'} · {status}"]


def headline(r, st, vst):
    """Telegram / review साठी एक साधी English ओळ ("what to look at") — engine codes नाहीत."""
    lv = r["level"]
    up = lv["role"] == "support"
    who, other = ("buyers", "sellers") if up else ("sellers", "buyers")
    trend = {"UP": "up", "DOWN": "down", "RANGE": "sideways"}.get(st.trend, str(st.trend).lower())
    vol = (f"entry candle volume {vst['commit_mult']:.1f}x the study-window average" if vst.get("ok")
           else "no volume data (grade capped at B)")
    return (f"What to look at: {'bull put' if up else 'bear call'} at 1H {'support' if up else 'resistance'} {lv['lo']:,.0f}-{lv['hi']:,.0f} "
            f"in a Daily {trend} trend - did the {who} take over from the {other} at the area? {vol[0].upper() + vol[1:]}.")


def caption(D, r, st, short, longst, head="V22 setup", tail="Reading review only: chart ends at the setup bar, no outcome, no trade, no order.",
            vline=VP.NA_LINE, vst=None):
    """भाग 1: साधं English (headline, trade, volume ओळ). भाग 2 ("Engine detail"): raw engine codes (K leg, births, sweeps, Q44, caps)."""
    rk, lv, cm, K = r.get("risk") or {}, r["level"], r.get("commit") or {}, r.get("K") or {}
    notes = [note_en(x) for x in r.get("trend_notes") or []]
    ts = pd.Timestamp(r["ts"])
    reading = f"{D.symbol} 15M {ts:%Y-%m-%d %H:%M} · {side_of(r)} · conviction {r['conviction']} · {short}"
    cap = "\n".join([
        headline(r, st, vst or {}),
        f"{head} · {reading}",
        f"Trade: entry {fmt(rk.get('entry'))} · stop {fmt(rk.get('sl'))} · target {fmt(rk.get('target'))} · reward/risk {rk.get('rr')}",
        vline,
        tail,
        "Engine detail:",
        f"Daily {st.trend} {phase_en(st)}; protected {fmt(getattr(st.protected, 'price', None))}; Weekly {r['weekly_trend']}. "
        f"Trend notes: {'; '.join(notes) if notes else 'none'}.",
        f"Trend cap {r['trend_cap'] or 'none'} · conviction {r['conviction']} (score {r.get('conv_score')}; missing "
        f"{', '.join(r.get('missing') or []) or 'none'}) · impulse mature: {'YES' if r['mature'] else 'no'} (Q44 target "
        f"{' / '.join(fmt(t) for t in r['maturity_targets']) or 'none'})",
        f"1H {lv['role']} {lv['lo']:,.0f}-{lv['hi']:,.0f} ({'+'.join(lv['births'])}, sweeps {lv.get('sweeps')}) · K leg {K.get('legs')} · "
        f"commitment {cm.get('form')} ({cm.get('grade')})",
        longst])
    assert all(not (0x0900 <= ord(ch) <= 0x097F) for ch in cap)            # English only
    return reading, cap


def render(D, r, header="", status=None, path=None, dpi=110):
    """एका setup row चा chart. रिटर्न dict (fig = path नसेल तर; नाहीतर बंद), st, short, longst, vol (15M study), ltf_vol, vline."""
    setup_ts, setup_end = pd.Timestamp(r["ts"]), pd.Timestamp(r["bar_end"])
    assert not D.sealed(setup_ts), "sealed (holdout) setup"
    st = D.state_at(setup_end)
    short, longst = status if status is not None else trend_first_status(D, r)
    w = m15_frame(D, setup_ts)
    vst = m15_study(D, r, w, setup_end)
    arm_ts = w["timestamp"].iloc[vst["arm"]] if vst["arm"] is not None else None
    g = ltf_frame(D, setup_end)
    has_ltf = g is not None
    fig = plt.figure(figsize=(19, 12.6 if has_ltf else 10.6), dpi=dpi)
    outer = fig.add_gridspec(2, 2, height_ratios=[1, 0.155 if has_ltf else 0.19], width_ratios=[1.2, 1], hspace=0.10, wspace=0.13,
                             left=0.045, right=0.985, top=0.905, bottom=0.015)
    gl = outer[0, 0].subgridspec(3, 1, height_ratios=[1, 0.24, 0.07], hspace=0.05)
    grp = outer[0, 1].subgridspec(2 if has_ltf else 1, 1, hspace=0.16)
    gr = [g_ for k in range(2 if has_ltf else 1) for g_ in grp[k].subgridspec(2, 1, height_ratios=[1, 0.34], hspace=0.04)]
    ax_d = fig.add_subplot(gl[0])
    ax_dv = fig.add_subplot(gl[1], sharex=ax_d)
    ax_s = fig.add_subplot(gl[2], sharex=ax_d)
    ax_m = fig.add_subplot(gr[0])
    ax_mv = fig.add_subplot(gr[1], sharex=ax_m)
    daily_panel(D, ax_d, ax_dv, ax_s, r, st, setup_ts, setup_end)
    m15_panel(D, ax_m, ax_mv, r, st, setup_ts, w, vst)
    lst, what = None, None
    if has_ltf:
        lst, what = ltf_study(D, r, g, arm_ts, setup_end)
        ltf_panel(D, fig.add_subplot(gr[2]), fig.add_subplot(gr[3]), r, g, lst, what, setup_end)
    ax_f = fig.add_subplot(outer[1, :])
    ax_f.axis("off")
    vline = vst["line"]
    fig.suptitle(f"{D.symbol} {setup_ts:%Y-%m-%d %H:%M} · {side_of(r)} · conviction {r['conviction']} · {short}", fontsize=14,
                 fontweight="bold", x=0.045, ha="left", y=0.990)
    fig.text(0.045, 0.957, headline(r, st, vst), fontsize=11.5, color=C["ink"], ha="left")
    fig.text(0.045, 0.936, (header + " · " if header else "") + f"Weekly {r['weekly_trend']} · Daily {r['daily_trend']} {r['daily_phase']} · "
             f"trend cap {r['trend_cap'] or 'none'} · impulse mature: {'YES' if r['mature'] else 'no'} · reading review only - no outcome, "
             "no order", fontsize=10, color=C["muted"], ha="left")
    ax_f.text(0.0, 0.98, "\n".join(footer_lines(r, st, longst, vline)), fontsize=9.2, va="top", ha="left", family="DejaVu Sans Mono",
              transform=ax_f.transAxes, color=C["ink"])
    out = {"st": st, "short": short, "longst": longst, "vol": vst, "ltf_vol": lst, "vline": vline, "fig": fig, "ltf": has_ltf}
    if path is not None:
        fig.savefig(path)
        plt.close(fig)
        out["fig"] = None
    return out
