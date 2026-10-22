"""decision3/chart_reading_charts.py — Message 1 of the daily Chart Reading Report (Abhi's order, owner-orders DECISIONS 35): an album of
three annotated PNGs, chart text in English, extending the pre-open charts (`decision3.preopen_chart`: the same candles, colours, label
spreading and line drawing; `decision3.charts._png`).

  1. Weekly + Daily — the trend, the protected level, the Daily / Weekly legs with the reader's own leg nature (legs_compare), the
     Daily / Weekly areas the report names.
  2. 1H — the alive areas with their ids and K4 states (broken / flipped dashed), the liquidity pools, the channel lines with their
     touch counts, the latest pattern's boundaries, the last BOS / CHoCH.
  3. 15M — the refined 15M base, the current visit, the "entry only if" sequence at the nearest trade-side area, the invalidation line,
     the next area.
Each chart has a near-month FUT volume pane (never spot volume; missing bars stay empty and are named) and an RSI pane with the
reader's divergence pairs marked. Everything drawn comes from `decision3.chart_reading.collect` facts (+ the bars) — display only, no
reading, no number of its own.

Clean charts (P8, DECISIONS 14): lines in the P8 order — the channel price is in, the next line in the path above / below, the latest
pattern's boundaries, then the other unbroken lines of that degree by touches — at most `chart_max_lines` (the display setting); the
legend lists only the shown lines; the rest are counted as "hidden: N". Areas: the refined base strong, the nearest trade-side area as
the context (faint), the next opposite area outlined, the other alive areas faded; dead areas are never drawn.
NIFTY: no sealed (holdout) Daily / Weekly candle is drawn (`history.display_start`)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import charts as CH  # noqa: E402
from . import preopen_chart as PCH  # noqa: E402

SUPPLY, DEMAND, MUTED, INK, PROT, LINE, PAT, LIQ = PCH.SUPPLY, PCH.DEMAND, PCH.MUTED, PCH.INK, PCH.PROT, PCH.LINE, "#d6336c", "#1971c2"
REFINED_SUP, REFINED_DEM, NEXT = "#c92a2a", "#2b8a3e", "#1c7ed6"
VIEW = {"Daily": 80, "Weekly": 60, "1H": 8, "15M": 3}                     # display windows: candles (D / W), sessions (1H / 15M)
FIG = (13, 8.2)
ENTRY_ONLY_IF = "entry only if: visit → handover → commitment (FUT volume) → 5M CHoCH ⇒ E1–E4"


def max_lines(value=None):
    from . import chart_lines as CL
    try:
        return int(value) if value is not None else CL.max_lines_default()
    except (TypeError, ValueError):
        return CL.max_lines_default()


def rsi_period():
    from rsi2 import settings as RS
    return int(RS.DEFAULTS["period"])


def rsi_of(close):
    from chart_reader import evidence as EV
    return EV.rsi(np.asarray(close, float), rsi_period())


def _axes(cols=1):
    fig = plt.figure(figsize=FIG)
    gs = fig.add_gridspec(3, cols, height_ratios=(5, 1.3, 1.3), hspace=0.08, wspace=0.18)
    out = []
    for c in range(cols):
        ax = fig.add_subplot(gs[0, c])
        axv = fig.add_subplot(gs[1, c], sharex=ax)
        axr = fig.add_subplot(gs[2, c], sharex=ax)
        plt.setp(ax.get_xticklabels(), visible=False)
        plt.setp(axv.get_xticklabels(), visible=False)
        out.append((ax, axv, axr))
    return fig, out


def _vol_pane(axv, vol, title="FUT volume (near month)"):
    v = np.asarray(vol if vol is not None else [], float)
    have = np.isfinite(v) & (v > 0)
    if not have.any():
        axv.text(0.5, 0.5, "FUT volume missing (data problem) — never spot volume", transform=axv.transAxes, ha="center", va="center",
                 fontsize=7.5, color=SUPPLY)
    else:
        x = np.flatnonzero(have)
        axv.bar(x, v[have], width=0.7, color="#868e96")
        miss = int((~have).sum())
        if miss:
            axv.text(0.005, 0.95, f"no FUT bar: {miss} (left empty)", transform=axv.transAxes, fontsize=6, color=MUTED, va="top")
    axv.set_ylabel("FUT vol", fontsize=6.5)
    axv.tick_params(labelsize=6)
    axv.text(0.995, 0.95, title, transform=axv.transAxes, fontsize=6, color=MUTED, ha="right", va="top")


def _rsi_pane(axr, rsi, pairs=(), note=None):
    r = np.asarray(rsi, float)
    axr.plot(np.arange(len(r)), r, color="#5f3dc4", lw=0.9)
    for (x0, x1, side, kind) in pairs:
        if 0 <= x0 < len(r) and 0 <= x1 < len(r) and np.isfinite(r[x0]) and np.isfinite(r[x1]):
            axr.plot([x0, x1], [r[x0], r[x1]], color="#f76707" if kind == "regular" else "#f59f00", lw=1.5,
                     ls="-" if kind == "regular" else "--")
    axr.set_ylim(0, 100)
    axr.set_ylabel(f"RSI {rsi_period()}", fontsize=6.5)
    axr.tick_params(labelsize=6)
    if note:
        axr.text(0.005, 0.92, note, transform=axr.transAxes, fontsize=6.3, color=INK, va="top")


def _band(ax, lo, hi, color, alpha, x0=None, x1=None, n=None, ls=None, lw=0):
    if x0 is None:
        if ls:
            ax.axhspan(lo, hi, facecolor="none", edgecolor=color, ls=ls, lw=lw or 1.0)
        else:
            ax.axhspan(lo, hi, color=color, alpha=alpha, lw=0)
        return
    w = (x1 if x1 is not None else n) - x0
    if ls:
        ax.add_patch(plt.Rectangle((x0, lo), w, hi - lo, facecolor="none", edgecolor=color, ls=ls, lw=lw or 1.0))
    else:
        ax.add_patch(plt.Rectangle((x0, lo), w, hi - lo, facecolor=color, alpha=alpha, lw=0))


def _labels(ax, labels, n_bars, y0, y1):
    from . import setup_chart as SC
    inside = [z for z in labels if y0 <= z[0] <= y1]
    if not inside:
        return
    x_lab = n_bars + 1.0
    for y, text, col, y_true, bold in SC.spread_labels(inside, y0, y1, (y1 - y0) * 0.04):
        ax.plot([n_bars - 0.4, x_lab - 0.2], [y_true, y], color=col, lw=0.5, alpha=0.6)
        ax.text(x_lab, y, " " + text, fontsize=6.8, color=col, va="center", fontweight="bold" if bold else "normal",
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.3))


def _short_state(a):
    st = {"ACTIVE": "FRESH"}.get(a["state"], a["state"])
    if a.get("was"):
        st += f" (was {a['was']})"
    if a.get("tests"):
        st += f", {a['tests']}× tested"
    return st


def area_label(a):
    tf = {"D": "Daily", "W": "Weekly"}.get(a["tf"], a["tf"])
    return f"#{a['id']} {tf} {a['kind']} {PCH._rng(a['lo'], a['hi'])} · {_short_state(a)}"


def _ylim(lo, hi, extra=()):
    ys = [lo, hi] + [y for y in extra if y is not None]
    span = max(hi - lo, 1e-6)
    ys = [y for y in ys if lo - span <= y <= hi + span]                     # far objects become a note, not a squashed chart
    y0, y1 = min(ys), max(ys)
    pad = 0.05 * max(y1 - y0, 1e-6)
    return y0 - pad, y1 + pad


def _finish(fig, ax, axr, title, foot, n_bars, ts, fmt):
    ax.set_title(title, fontsize=9.5, loc="left")
    ax.set_xlim(-1, n_bars + max(14, n_bars * 0.55))
    ax.grid(axis="y", color="#e9ecef", lw=0.5)
    ax.tick_params(labelsize=7)
    every = max(1, n_bars // 10)
    idx = list(range(0, n_bars, every))
    axr.set_xticks(idx)
    axr.set_xticklabels([pd.Timestamp(ts[i]).strftime(fmt) for i in idx], rotation=40, fontsize=6.3)
    if foot:
        ax.text(0.995, 0.01, foot, transform=ax.transAxes, fontsize=6.3, color=MUTED, ha="right", va="bottom")


# ---------------------------------------------------------------------------------------------------------------- volume per frame
def fut_15m(V):
    A = V.levels.A
    v = A.get("volume_raw") if hasattr(A, "get") else None
    return None if v is None else np.asarray(v, float)


def _group_volume(v15, keys, frame_keys):
    """Sum of the 15M FUT volume per frame bar; a frame bar with a missing 15M FUT bar stays NaN (never under-counted)."""
    if v15 is None:
        return np.full(len(frame_keys), np.nan)
    df = pd.DataFrame({"k": keys, "v": v15})
    g = df.groupby("k")["v"].agg(lambda s: s.sum() if np.isfinite(s).all() and len(s) else np.nan)
    return np.array([g.get(k, np.nan) for k in frame_keys], float)


# ---------------------------------------------------------------------------------------------------------------- 1) Weekly + Daily
def htf_png(V, sym, facts):
    from . import history as HI
    sealed = HI.sealed_fn(sym)
    fig, cols = _axes(2)
    t = int(facts["t"])
    v15 = fut_15m(V)
    m15_day = pd.to_datetime(V.m15["timestamp"]).dt.normalize().to_numpy()[: t + 1]
    shown = [a for a in (facts.get("areas") or {}).get("htf") or ()]
    shown += [a for a in ((facts.get("areas") or {}).get("watch") or ())[:2] if a["tf"] in ("D", "W")]
    bp = (facts.get("big_picture") or {})
    for (ax, axv, axr), tf in zip(cols, ("Weekly", "Daily")):
        d = (V.weekly_df if tf == "Weekly" else V.daily_df).reset_index(drop=True)
        ts = pd.to_datetime(d["timestamp"])
        n = len(d)
        st0 = HI.display_start(ts, None, sealed, sessions=VIEW[tf])
        if st0 > n - 1:
            ax.text(0.5, 0.5, f"no {tf} candle to show after the sealed dates", transform=ax.transAxes, ha="center")
            continue
        w = d.iloc[st0:n].reset_index(drop=True)
        CH._candles(ax, w)
        wts = pd.to_datetime(w["timestamp"])
        key_tf = "W" if tf == "Weekly" else "D"
        for lg in (facts.get("structure") or {}).get("legs_htf") or ():    # the reader's own legs (legs_compare) and their nature
            if lg["tf"] != key_tf or lg.get("p0") is None or lg.get("p1") is None:
                continue
            x0 = _x_of(wts, lg["t0"], tf)
            x1 = _x_of(wts, lg["t1"], tf) if lg.get("t1") else len(w) - 1
            if x0 is None or x1 is None:
                continue
            col = "#1864ab" if lg["verdict"] == "impulse" else "#e8590c" if lg["verdict"] == "correction" else "#868e96"
            ax.plot([x0, x1], [lg["p0"], lg["p1"]], color=col, lw=1.4, ls="-" if lg["verdict"] == "impulse" else "--", alpha=0.85)
            ax.text((x0 + x1) / 2, (lg["p0"] + lg["p1"]) / 2, f" {lg['verdict']}" + ("" if lg["complete"] else " (so far)"), fontsize=6.5,
                    color=col)
        labels = []
        tfr = bp.get("tfs", {}).get(key_tf) or {}
        prot = tfr.get("protected")
        lo, hi = float(w["low"].min()), float(w["high"].max())
        if prot is not None:
            ax.axhline(float(prot), color=PROT, lw=1.1, ls=":")
            labels.append((float(prot), f"protected {float(prot):,.0f} ({tf})", PROT, False))
        for a in shown:
            if a["tf"] != key_tf:
                continue
            col = SUPPLY if a["kind"] == "supply" else DEMAND
            _band(ax, a["lo"], a["hi"], col, 0.18)
            labels.append(((a["lo"] + a["hi"]) / 2, area_label(a), col, False))
        y0, y1 = _ylim(lo, hi, [prot] + [a["lo"] for a in shown if a["tf"] == key_tf] + [a["hi"] for a in shown if a["tf"] == key_tf])
        ax.set_ylim(y0, y1)
        _labels(ax, labels, len(w), y0, y1)
        vol = _group_volume(v15, m15_day if tf == "Daily" else _week_key(m15_day), wts.dt.normalize().to_numpy() if tf == "Daily"
                            else _week_key(wts.dt.normalize().to_numpy()))
        _vol_pane(axv, vol, "FUT volume (near month) — only where FUT bars exist")
        _rsi_pane(axr, rsi_of(d["close"])[st0:n], note="divergence pairs are read on 15M / 1H (D1 / D2) — see those charts")
        state = tfr.get("state") or "NA"
        title = f"{sym} · {tf} · {state}" + (f" ({tfr.get('trend')})" if tfr.get("trend") else "")
        if tf == "Daily":
            dd = bp.get("daily") or {}
            title += f"\nDaily side {dd.get('trend') or 'NA'} · {dd.get('phase') or ''}"
            wv = facts.get("wave") or {}
            if wv.get("corr_label"):                                       # the reader's own correction leg label (a / b / c)
                title += f" · correction leg {wv['corr_label']}"
        elif (facts.get("wave") or {}).get("weekly_detail"):
            title += f"\n{facts['wave']['weekly_detail']}"
        _finish(fig, ax, axr, title, f"bars to {pd.Timestamp(wts.iloc[-1]).strftime('%d %b %Y')}", len(w), wts.to_numpy(), "%d %b %y")
    return CH._png(fig), {"lines_view": {"max_lines": None, "shown": [], "legend": [], "hidden": 0}}


def _week_key(days):
    d = pd.to_datetime(pd.Series(days))
    return (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize().to_numpy()


def _x_of(ts, when, tf):
    if when is None:
        return None
    w = pd.Timestamp(when)
    if tf == "Weekly":
        w = w - pd.Timedelta(days=w.weekday())
    k = np.flatnonzero(pd.to_datetime(ts).dt.normalize().to_numpy() <= np.datetime64(w.normalize()))
    if not len(k):
        return None
    return int(k[-1])


# ---------------------------------------------------------------------------------------------------------------- lines (P8)
def pick_lines(facts, degree, cap):
    """P8 order on one chart: (b) the channel price is in (both lines), (c) the next line above / below, the latest pattern's
    boundaries, then nothing else; at most `cap`. Returns (shown [(label, geom, color, ls)], hidden_count)."""
    li = facts.get("lines") or {}
    cands = []
    chans = [c for c in li.get("channels") or () if int(c.get("degree") or 0) == degree and c.get("geom")]
    # (b) THE channel price is in now: of the channels price is inside, the one drawn through the latest swing (comparison)
    chans = sorted(chans, key=lambda c: -max(int(g.get("last") or g["bar"]) for g in c["geom"]))[:1]
    for c in chans:
        for g, part in zip(c.get("geom") or (), ("main", "parallel")):
            cands.append((f"{c['tf']} {c['slope']} channel {part}" + (f" ({c['touches']} touches)" if part == "main" else ""), g, "#0c8599",
                          "-"))
    for side in ("above", "below"):
        x = li.get(side)
        if x and x.get("geom") and int(x.get("degree") or 0) == degree:
            cands.append((f"next line {side}: {x['tf']} {x['family']} ({x['touches']} touches)", x["geom"], LINE, "-."))
    pats = facts.get("patterns") or []
    if pats and degree == 2:
        p = pats[0]
        for ln in p.get("lines") or ():
            if ln.get("geom"):
                cands.append((f"{p['name']} {ln['name']} ({p['state']})", ln["geom"], PAT, "-"))
    seen, out = set(), []
    for c in cands:
        k = (c[1]["bar"], c[1]["price"], c[1]["slope"])
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out[:cap], max(0, len(out) - cap)


def _draw_geom(ax, g, xmap, t, color, ls, label):
    b1, y1, sl = int(g["bar"]), float(g["price"]), float(g["slope"])
    by_x = {}
    for b in range(b1, t + 1):                                             # one point per chart bar (the last 15M bar in it)
        x = xmap(b)
        if x is not None:
            by_x[x] = y1 + sl * (b - b1)
    pts = sorted(by_x.items())
    if len(pts) < 2:
        return False
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, lw=1.2, ls=ls, label=label)
    return True


# ---------------------------------------------------------------------------------------------------------------- 2) 1H
def _divergence_pairs(facts, to_x):
    out = []
    r = facts.get("rsi") or {}
    for x in r.get("regular") or ():
        a, b = to_x(x["t0"]), to_x(x["t1"])
        if a is not None and b is not None:
            out.append((a, b, x["side"], "regular", x))
    return out


def h1_png(V, sym, facts, cap=None):
    lv = V.levels
    t = int(facts["t"])
    cap = max_lines(cap)
    j_end = int(lv.h1_of[t])
    h1 = lv.h1.iloc[: j_end + 1].reset_index(drop=True)
    o, hh, ll, cc = lv._h1_upto(j_end, t)                                  # the running hour only up to t
    h1.loc[len(h1) - 1, ["open", "high", "low", "close"]] = [o, hh, ll, cc]
    j0 = PCH._sessions(h1["timestamp"], VIEW["1H"])
    w = h1.iloc[j0:].reset_index(drop=True)
    fig, ((ax, axv, axr),) = _axes(1)
    CH._candles(ax, w)
    lo, hi = float(w["low"].min()), float(w["high"].max())
    A = facts.get("areas") or {}
    near = sorted(A.get("watch") or (), key=lambda a: a["dist"])
    key_ids = {a["id"] for a in near[:2]} | ({A["next_opposite"]["id"]} if A.get("next_opposite") else set())
    labels = []
    span = hi - lo
    for a in A.get("alive") or ():
        if a["tf"] != "1H" or a["hi"] < lo - 0.1 * span or a["lo"] > hi + 0.1 * span:
            continue
        col = SUPPLY if a["kind"] == "supply" else DEMAND
        strong = a["id"] in key_ids
        x0 = max(0, int(lv.h1_of[int(a["born_bar"])]) - j0) if a.get("born_bar") is not None else 0
        if a["state"] == "FLIPPED":
            _band(ax, a["lo"], a["hi"], col, 0.0, x0=x0, n=len(w), ls="--", lw=0.9)
        _band(ax, a["lo"], a["hi"], col, 0.26 if strong else 0.07, x0=x0, n=len(w))
        if strong or a["state"] == "FLIPPED":
            labels.append(((a["lo"] + a["hi"]) / 2, area_label(a), col if strong else MUTED, strong))
    for a in A.get("broken") or ():                                        # BROKEN (alive, not a trade location): dashed outline
        if a["tf"] == "1H" and lo - 0.1 * span <= a["lo"] <= hi + 0.1 * span:
            _band(ax, a["lo"], a["hi"], MUTED, 0.0, ls="--", lw=1.0)
            labels.append(((a["lo"] + a["hi"]) / 2, f"#{a['id']} 1H {a['kind']} {PCH._rng(a['lo'], a['hi'])} · BROKEN", MUTED, False))
    q = facts.get("liquidity") or {}
    for side in ("above", "below"):
        x = q.get(side)
        if x:
            ax.axhline(x["price"], color=LIQ, lw=0.9, ls=(0, (1, 2)))
            what = ("equal highs" if side == "above" else "equal lows") if x.get("equal") else ("swing high" if side == "above" else "swing low")
            labels.append((x["price"], f"liquidity {side}: {what} {x['price']:,.0f} (resting)", LIQ, False))
    ev = [e for e in (facts.get("structure") or {}).get("events") or () if e["tf"] == "1H"]
    for e in ev[-1:]:
        ax.axhline(e["level"], xmin=0.55, xmax=0.70, color="#212529", lw=1.3)
        labels.append((e["level"], f"last 1H {e['type']} {'↑' if e['dir'] == 'up' else '↓'} (close beyond {e['level']:,.0f})", INK, True))
    xmap = lambda b: (int(lv.h1_of[b]) - j0) if 0 <= b < len(lv.h1_of) and int(lv.h1_of[b]) >= j0 else None   # noqa: E731
    shown, hidden = pick_lines(facts, 2, cap)
    legend = []
    for lab, g, col, ls in shown:
        if _draw_geom(ax, g, xmap, t, col, ls, lab):
            legend.append(lab)
    if legend:
        ax.legend(loc="upper left", fontsize=6.3, framealpha=0.85)
    y0, y1 = _ylim(lo, hi, [z[0] for z in labels])
    ax.set_ylim(y0, y1)
    _labels(ax, labels, len(w), y0, y1)
    m15ts = pd.to_datetime(V.m15["timestamp"]).iloc[: t + 1]
    hkey = lv.h1_of[: t + 1]
    vol = _group_volume(fut_15m(V)[: t + 1] if fut_15m(V) is not None else None, hkey, list(range(j0, j0 + len(w))))
    _vol_pane(axv, vol)
    pairs = _divergence_pairs(facts, lambda ts: _h1_x(lv, m15ts, ts, j0, len(w)))
    for a, b, side, kind, x in pairs:
        ax.plot([a, b], [x["p0"], x["p1"]], color="#f76707", lw=1.4)
        ax.text(b, x["p1"], f" {side} RSI div", fontsize=6.3, color="#f76707")
    _rsi_pane(axr, rsi_of(h1["close"])[j0:], [(a, b, s, k) for a, b, s, k, _ in pairs],
              note=None if pairs else "no divergence pair in this window")
    st = ((facts.get("big_picture") or {}).get("tfs") or {}).get("1H") or {}
    foot = f"data to {pd.Timestamp(facts['as_of']).strftime('%d %b %H:%M')}" + (f" · hidden: {hidden} lines" if hidden else "")
    _finish(fig, ax, axr, f"{sym} · 1H · {st.get('state') or 'NA'} ({st.get('trend') or ''}) · ids = engine area ids", foot, len(w),
            w["timestamp"].to_numpy(), "%d %b %H:%M")
    return CH._png(fig), {"lines_view": {"max_lines": cap, "shown": legend, "legend": legend, "hidden": hidden}}


def _h1_x(lv, m15ts, ts, j0, n):
    k = np.flatnonzero(m15ts.to_numpy() == np.datetime64(pd.Timestamp(ts)))
    if not len(k):
        return None
    x = int(lv.h1_of[int(k[0])]) - j0
    return x if 0 <= x < n else None


# ---------------------------------------------------------------------------------------------------------------- 3) 15M
def m15_png(V, sym, facts, cap=None):
    t = int(facts["t"])
    cap = max_lines(cap)
    m = V.m15.iloc[: t + 1]
    i0 = PCH._sessions(m["timestamp"], VIEW["15M"])
    w = m.iloc[i0:].reset_index(drop=True)
    fig, ((ax, axv, axr),) = _axes(1)
    CH._candles(ax, w)
    lo, hi = float(w["low"].min()), float(w["high"].max())
    p = facts.get("plan") or {}
    A = facts.get("areas") or {}
    labels, extra = [], []
    nb = p.get("nearest")
    if nb:
        col = SUPPLY if nb["kind"] == "supply" else DEMAND
        _band(ax, nb["lo"], nb["hi"], col, 0.08)                            # the context area (faint)
        labels.append(((nb["lo"] + nb["hi"]) / 2, "context: " + area_label(nb), col, False))
        extra += [nb["lo"], nb["hi"]]
        rb = p.get("refined")
        if rb:
            _band(ax, rb["lo"], rb["hi"], REFINED_SUP if nb["kind"] == "supply" else REFINED_DEM, 0.42)
            labels.append(((rb["lo"] + rb["hi"]) / 2, f"refined 15M base {PCH._rng(rb['lo'], rb['hi'])} (trigger candle trades into it)",
                           REFINED_SUP if nb["kind"] == "supply" else REFINED_DEM, True))
            ax.axhline(rb["far"], color=INK, lw=0.9, ls="--")
            labels.append((rb["far"], f"E1 invalidation: beyond {rb['far']:,.0f}", INK, False))
            extra += [rb["lo"], rb["hi"]]
        far = p.get("far_edge")
        if far is not None:
            ax.axhline(far, color=col, lw=1.1, ls="--")
            labels.append((far, f"area BROKEN = a close {'above' if nb['kind'] == 'supply' else 'below'} {far:,.0f} + a swing beyond", col,
                           False))
        vs = p.get("visit_start_bar")
        if vs is not None and int(vs) >= i0:
            ax.axvspan(int(vs) - i0 - 0.5, len(w) - 0.5, color="#fab005", alpha=0.10, lw=0)
            ax.text(int(vs) - i0, hi, " current visit", fontsize=6.5, color="#e67700", va="top")
        mid = (nb["lo"] + nb["hi"]) / 2
        ax.annotate(ENTRY_ONLY_IF, xy=(len(w) - 1, mid), xytext=(max(1, len(w) * 0.03), mid), textcoords="data", fontsize=7, color=INK,
                    va="center", bbox=dict(boxstyle="round,pad=0.3", fc="#fff9db", ec="#d97a1e", lw=0.8, alpha=0.92), clip_on=True)
    for key, word in (("next_same_side", "next area if broken"),):
        a = p.get(key)
        if a:
            _band(ax, a["lo"], a["hi"], NEXT, 0.0, ls=":", lw=1.0)
            labels.append(((a["lo"] + a["hi"]) / 2, f"{word}: " + area_label(a), NEXT, False))
            extra += [a["lo"], a["hi"]]
    o = A.get("next_opposite")
    if o:
        _band(ax, o["lo"], o["hi"], NEXT, 0.0, ls="-", lw=1.1)
        labels.append(((o["lo"] + o["hi"]) / 2, "next opposite area: " + area_label(o), NEXT, False))
        extra += [o["lo"], o["hi"]]
    xmap = lambda b: (b - i0) if i0 <= b <= t else None                     # noqa: E731
    shown, hidden = pick_lines(facts, 1, cap)
    legend = []
    for lab, g, col, ls in shown:
        if _draw_geom(ax, g, xmap, t, col, ls, lab):
            legend.append(lab)
    if legend:
        ax.legend(loc="upper left", fontsize=6.3, framealpha=0.85)
    last = facts.get("last_close")
    if last is not None:
        ax.axhline(float(last), color=MUTED, lw=0.7, ls=(0, (2, 2)))
        labels.append((float(last), f"last close {float(last):,.0f}", INK, False))
    y0, y1 = _ylim(lo, hi, extra)
    ax.set_ylim(y0, y1)
    _labels(ax, labels, len(w), y0, y1)
    v = fut_15m(V)
    _vol_pane(axv, None if v is None else v[i0: t + 1])
    ts = pd.to_datetime(w["timestamp"]).to_numpy()
    to_x = lambda s: (lambda k: int(k[0]) if len(k) else None)(np.flatnonzero(ts == np.datetime64(pd.Timestamp(s))))   # noqa: E731
    pairs = _divergence_pairs(facts, to_x)
    for a, b, side, kind, x in pairs:
        ax.plot([a, b], [x["p0"], x["p1"]], color="#f76707", lw=1.4)
        ax.text(b, x["p1"], f" {side} RSI div", fontsize=6.3, color="#f76707")
    from . import draw_objects as DO
    try:
        r = np.asarray(DO._rsi(V).rsi, float)[i0: t + 1]                    # the reader's own 15M RSI (rsi2, per data segment)
    except Exception:                                                      # noqa: BLE001 — display only
        r = rsi_of(m["close"])[i0:]
    _rsi_pane(axr, r, [(a, b, s, k) for a, b, s, k, _ in pairs], note=None if pairs else "no divergence pair in this window")
    st = ((facts.get("big_picture") or {}).get("tfs") or {}).get("15M") or {}
    foot = f"data to {pd.Timestamp(facts['as_of']).strftime('%d %b %H:%M')}" + (f" · hidden: {hidden} lines" if hidden else "")
    _finish(fig, ax, axr, f"{sym} · 15M · {st.get('state') or 'NA'} · refined base / visit / entry-only-if at the nearest trade-side area",
            foot, len(w), w["timestamp"].to_numpy(), "%d %b %H:%M")
    return CH._png(fig), {"lines_view": {"max_lines": cap, "shown": legend, "legend": legend, "hidden": hidden}}


def caption(sym, tf, facts):
    p = (facts.get("plan") or {}).get("nearest")
    head = f"{sym} · {tf} · chart reading"
    if p:
        head += f" · nearest trade-side area #{p['id']} {PCH._rng(p['lo'], p['hi'])}"
    return head[:1024]


def render(V, sym, facts, cap=None, deadline=None, clock=None):
    """[(name, png, caption, meta)] for "W+D", "1H", "15M" — each chart independent (a failure skips only that chart, the reason in
    errors). Returns (items, errors)."""
    import time
    clock = clock or time.monotonic
    items, errors = [], []
    for name, fn in (("W+D", lambda: htf_png(V, sym, facts)), ("1H", lambda: h1_png(V, sym, facts, cap)),
                     ("15M", lambda: m15_png(V, sym, facts, cap))):
        if deadline is not None and clock() > deadline:
            errors.append(f"{name}: skipped (time budget)")
            continue
        try:
            png, meta = fn()
            items.append((name, png, caption(sym, name, facts), meta))
        except Exception as exc:                                           # noqa: BLE001 — a chart never stops the message
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
        finally:
            plt.close("all")
    return items, errors
