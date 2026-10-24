"""decision3/preopen_chart.py — pre-open charts (Abhi, track F): प्रत्येक symbol साठी Daily / 1H / 15M एक-एक PNG, reader च्या स्वतःच्या
chart code ने (`charts._candles` / `_xticks` / `_png`, Daily swings + protected `charts.daily_png` सारखे) — matplotlib, Chrome / kaleido नाही.

काढतो (chart वर मजकूर English — Abhi: chart वर मराठी नको): engine पाहत असलेले trade-बाजूचे areas (पट्टा, kind, tf, state), जवळच्या area चे
confluence पट्टे (फिके), protected Daily level, trend, reader ची trade-बाजूची रेघ (touch N; `trendline.swing_line`), last close + जवळच्या
area पर्यंतचं अंतर, आणि जवळच्या area वर "entry zone only if: handover + commitment + 5M CHoCH" + invalidation रेघ + target area.
फक्त दाखवणं — निर्णय / reader logic बदलत नाही; सगळे आकडे `bots_common.preopen_crux.facts` मधूनच (नवा आकडा नाही). हलकं: V22 जो pre-open
ने आधीच बनवला तोच (पुन्हा fetch / build नाही), लहान खिडक्या, प्रत्येक figure बंद (`charts._png`). NIFTY: holdout तारखा chart वर नाहीत
(Daily `history.display_start`; 15M / 1H engine input आधीच annotation-filtered).
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import charts as CH  # noqa: E402

TFS = ("Daily", "1H", "15M")
BARS = {"Daily": 80, "1H": 6, "15M": 3}                                    # Daily candles; 1H / 15M = sessions
SUPPLY, DEMAND = "#e03131", "#2f9e44"                                      # reader च्या 1H / 15M chart सारखेच
PROT, TARGET, CONF, INK, MUTED = "#7048e8", "#d97a1e", "#868e96", "#212529", "#495057"
LINE = "#1c7ed6"
ENTRY_NOTE = "entry zone only if: handover + commitment (volume) + 5M CHoCH"
FIGSIZE = (11, 5.6)


def line_facts(V, trend):
    """Reader ची trade-बाजूची रेघ (`trendline.swing_line`, t = शेवटचा बंद 15M bar) + area tags ({level id: "line (touch N)"} —
    `trendline.confluence_areas`, engine च्या ② सारखंच). RANGE / UNKNOWN ⇒ रेघ नाही. त्रुटी ⇒ रिकामं (chart तरी बनतो)."""
    from . import trendline as TL
    d = {"DOWN": TL.DOWN, "UP": TL.UP}.get(str(trend))
    out = {"line": None, "tags": {}, "t": len(V.m15) - 1}
    if d is None:
        return out
    t = out["t"]
    try:
        out["line"] = TL.swing_line(V, t, d)
    except Exception:                                                      # noqa: BLE001 — फक्त दाखवणं
        out["line"] = None
    try:
        for x in TL.confluence_areas(V, t, d, V.levels.active(t, trend)):
            lab = str(x.get("confluence_label") or "")
            i = lab.find("line")
            if i >= 0:
                out["tags"][x["id"]] = lab[i:].split(";", 1)[0].strip()
    except Exception:                                                      # noqa: BLE001
        pass
    return out


def _rng(lo, hi):
    return f"{lo:,.0f}–{hi:,.0f}"


def _kind(side):
    from bots_common import level_reaction as LR
    return "demand" if side == LR.BULL else "supply"


def _ylim(lo, hi, f, include_protected):
    """Candles ची खिडकी + जवळचा area (नेहमी) + target / protected (जवळ असतील तर) ⇒ (ymin, ymax, off-chart नोंदी)."""
    span = max(hi - lo, 1e-6)
    ys, notes = [lo, hi], []
    n, t, p = f.get("nearest"), f.get("target"), f.get("protected")
    if n:
        ys += [n["lo"], n["hi"]]
    if t:
        if min(abs(t["hi"] - lo), abs(t["lo"] - hi)) <= 1.5 * span or (t["lo"] >= lo and t["hi"] <= hi):
            ys += [t["lo"], t["hi"]]
        else:
            notes.append(f"target {_kind(t['side'])} {_rng(t['lo'], t['hi'])} off chart ({'above' if t['lo'] > hi else 'below'})")
    if p is not None:
        if include_protected or lo - 0.5 * span <= p <= hi + 0.5 * span:
            ys.append(float(p))
        else:
            notes.append(f"protected {float(p):,.0f} off chart ({'above' if p > hi else 'below'})")
    y0, y1 = min(ys), max(ys)
    pad = 0.06 * max(y1 - y0, 1e-6)
    return y0 - pad, y1 + pad, notes


def _state_short(a):
    """"flipped (reader role now demand, was supply), tested 6×" ⇒ "flipped, tested 6×"; "fresh (not tested yet)" ⇒ "fresh"."""
    import re
    return re.sub(r" \([^)]*\)", "", str(a.get("state") or ""))


def _overlay(ax, f, n_bars, tf):
    """Areas / confluence / target / invalidation / protected / last close / entry note. उजवीकडच्या labels ची यादी परत (ylim नंतर
    एकमेकांवर न येता `setup_chart.spread_labels` ने काढतो)."""
    from bots_common import level_reaction as LR
    labels = []
    near, last = f.get("nearest"), f.get("last")
    for a in f.get("watched") or ():
        col = DEMAND if a["side"] == LR.BULL else SUPPLY
        is_near = near is not None and a is near
        ax.axhspan(a["lo"], a["hi"], color=col, alpha=0.30 if is_near else 0.12, lw=0)
        bits = [f"{_kind(a['side'])} {_rng(a['lo'], a['hi'])}", a.get("tf") or "", _state_short(a)]
        if a.get("conf") and a["conf"] != "none":
            bits.append(f"conf: {a['conf']}")
        labels.append(((a["lo"] + a["hi"]) / 2, ("▶ " if is_near else "") + " · ".join(b for b in bits if b), col, is_near))
    if near:
        for c in near.get("confluence") or ():                             # Daily / Weekly पट्टे — फिके, डावीकडे कंस (पुरावा, location नाही)
            ax.axhspan(c["lo"], c["hi"], xmin=0.0, xmax=0.012, color=CONF, alpha=0.35, lw=0)
            ax.axhline(c["lo"], color=CONF, lw=0.5, ls=(0, (1, 3)), alpha=0.7)
            ax.axhline(c["hi"], color=CONF, lw=0.5, ls=(0, (1, 3)), alpha=0.7)
        bull = near["side"] == LR.BULL
        edge = near["lo"] if bull else near["hi"]
        ax.axhline(edge, color=SUPPLY if not bull else DEMAND, lw=1.0, ls="--")
        labels.append((edge, f"invalid: close {'below' if bull else 'above'} {edge:,.0f} + a swing beyond it (area broken)", INK, False))
        mid = (near["lo"] + near["hi"]) / 2
        ax.annotate(ENTRY_NOTE + ("\nA: one confirming piece (confluence / RSI divergence …); else B" if near.get("conf") == "none"
                                  else "\nconfluence present ⇒ A if all of this happens"),
                    xy=(n_bars - 1, mid), xytext=(max(1, n_bars * 0.03), mid), textcoords="data", fontsize=7.5, color=INK, va="center",
                    bbox=dict(boxstyle="round,pad=0.3", fc="#fff9db", ec=TARGET, lw=0.8, alpha=0.92), clip_on=True)
    t = f.get("target")
    if t:
        ax.axhspan(t["lo"], t["hi"], facecolor="none", edgecolor=TARGET, lw=1.2, ls="-")
        labels.append(((t["lo"] + t["hi"]) / 2, f"next opposite area (engine): {_kind(t['side'])} {_rng(t['lo'], t['hi'])}"
                       + (f" · {t['tf']}" if t.get("tf") else "") + " · SL / target = dashboard", TARGET, False))
    p = f.get("protected")
    if p is not None:
        ax.axhline(float(p), color=PROT, lw=1.1, ls=":")
        labels.append((float(p), f"protected {float(p):,.0f} (Daily)", PROT, False))
    if last is not None:
        ax.axhline(float(last), color=MUTED, lw=0.8, ls=(0, (2, 2)))
        dist = f" · {abs(near['dist']):,.0f} pts to {_kind(near['side'])}" if near else ""
        labels.append((float(last), f"last close {float(last):,.0f}{dist}", INK, False))
    return labels


def _finish(ax, f, n_bars, frame_lo, frame_hi, include_protected, title, asof, labels=()):
    from . import setup_chart as SC
    y0, y1, notes = _ylim(frame_lo, frame_hi, f, include_protected)
    ax.set_ylim(y0, y1)
    ax.set_xlim(-1, n_bars + max(12, n_bars * 0.7))                         # उजवीकडे labels साठी जागा
    inside = [z for z in labels if y0 <= z[0] <= y1]
    x_lab = n_bars + 1.5
    for y, text, col, y_true, bold in SC.spread_labels(inside, y0, y1, (y1 - y0) * 0.045):
        ax.plot([n_bars - 0.4, x_lab - 0.2], [y_true, y], color=col, lw=0.5, alpha=0.6)
        ax.text(x_lab, y, " " + text, fontsize=7.3, color=col, va="center", fontweight="bold" if bold else "normal",
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.4))
    ax.set_title(title, fontsize=10, loc="left")
    foot = [f"data to {asof}"] + notes
    ax.text(0.995, 0.01, " · ".join(foot), transform=ax.transAxes, fontsize=6.5, color=MUTED, ha="right", va="bottom")
    ax.grid(axis="y", color="#e9ecef", lw=0.5)
    ax.tick_params(labelsize=7)


def _xticks_intraday(ax, ts, every):
    idx = list(range(0, len(ts), max(1, every)))
    ax.set_xticks(idx)
    ax.set_xticklabels([pd.Timestamp(ts[i]).strftime("%d %b %H:%M") for i in idx], rotation=45, fontsize=7)


def _title(sym, tf, f, weekly):
    ctx = f.get("ctx") or {}
    return f"{sym} · {tf} · Daily {ctx.get('trend') or 'n/a'} · Weekly {weekly or 'n/a'}"


def daily_png(V, sym, f, weekly=None, bars=BARS["Daily"]):
    from . import history as HI
    d = V.daily_df.reset_index(drop=True)
    n = len(d)
    st0 = HI.display_start(d["timestamp"], None, HI.sealed_fn(sym))       # Q33: NIFTY holdout Daily candles chart वर नाहीत
    start = max(st0, n - int(bars))
    if start > n - 1:
        raise ValueError("no daily candle to show after the sealed dates")
    w = d.iloc[start:n].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=FIGSIZE)
    for i in range(start, n):
        ax.axvspan(i - start - 0.5, i - start + 0.5, color=CH.TREND_COLOR.get(V.daily[i].trend, "#fff"), lw=0, alpha=0.6)
    CH._candles(ax, w)
    last = V.daily[n - 1]
    from . import daily_swings as DS
    tags = DS.tag_pivots(last.pivots, d["open"].to_numpy(float), d["close"].to_numpy(float))   # charts.daily_png सारखे (F1)
    for p, lab in zip(last.pivots, tags):
        if p.bar >= start:
            ax.annotate(lab, (p.bar - start, p.price), textcoords="offset points", xytext=(0, 8 if p.kind == "H" else -12), ha="center",
                        fontsize=7, color="#1c7ed6" if p.kind == "H" else "#e8590c")
    labels = _overlay(ax, f, len(w), "Daily")
    asof = pd.Timestamp(w["timestamp"].iloc[-1]).strftime("%d %b %Y")
    _finish(ax, f, len(w), float(w["low"].min()), float(w["high"].max()), True, _title(sym, "Daily", f, weekly), asof, labels)
    CH._xticks(ax, w["timestamp"].to_numpy(), max(1, len(w) // 12))
    return CH._png(fig)


def _sessions(ts, k):
    days = pd.to_datetime(ts).dt.normalize()
    keep = sorted(days.unique())[-int(k):]
    return int(np.flatnonzero(days.isin(keep).to_numpy())[0])


def _draw_line(ax, ln, xmap, t, color=LINE):
    """Reader ची रेघ (15M bar index वर) ⇒ chart x (xmap(b) None ⇒ खिडकीबाहेर)."""
    if not ln:
        return
    (b1, y1), sl = ln["p1"], float(ln["slope"])
    pts = [(xmap(b), y1 + sl * (b - b1)) for b in range(int(b1), t + 1)]
    pts = [(x, y) for x, y in pts if x is not None]
    if len(pts) < 2:
        return
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, lw=1.2, ls="-.")
    ax.text(pts[-1][0], pts[-1][1], f" line ({ln.get('touches')} touches)", fontsize=7, color=color, va="bottom", clip_on=True)


def h1_png(V, sym, f, weekly=None, sessions=BARS["1H"], line=None):
    lv = V.levels
    t = len(V.m15) - 1
    j_end = int(lv.h1_of[t])
    h1 = lv.h1.iloc[:j_end + 1].reset_index(drop=True)
    j0 = _sessions(h1["timestamp"], sessions)
    w = h1.iloc[j0:].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=FIGSIZE)
    CH._candles(ax, w)
    labels = _overlay(ax, f, len(w), "1H")
    ln = (line or {}).get("line")
    _draw_line(ax, ln, lambda b: (int(lv.h1_of[b]) - j0) if int(lv.h1_of[b]) >= j0 else None, t)
    asof = pd.Timestamp(V.m15["bar_end"].iloc[t]).strftime("%d %b %H:%M") if "bar_end" in V.m15.columns else \
        pd.Timestamp(V.m15["timestamp"].iloc[t]).strftime("%d %b %H:%M")
    _finish(ax, f, len(w), float(w["low"].min()), float(w["high"].max()), False, _title(sym, "1H", f, weekly), asof, labels)
    _xticks_intraday(ax, w["timestamp"].to_numpy(), max(1, len(w) // 10))
    return CH._png(fig)


def m15_png(V, sym, f, weekly=None, sessions=BARS["15M"], line=None):
    m = V.m15
    t = len(m) - 1
    i0 = _sessions(m["timestamp"], sessions)
    w = m.iloc[i0:t + 1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=FIGSIZE)
    CH._candles(ax, w)
    labels = _overlay(ax, f, len(w), "15M")
    _draw_line(ax, (line or {}).get("line"), lambda b: (b - i0) if b >= i0 else None, t)
    end = m["bar_end"].iloc[t] if "bar_end" in m.columns else m["timestamp"].iloc[t]
    _finish(ax, f, len(w), float(w["low"].min()), float(w["high"].max()), False, _title(sym, "15M", f, weekly),
            pd.Timestamp(end).strftime("%d %b %H:%M"), labels)
    _xticks_intraday(ax, w["timestamp"].to_numpy(), max(1, len(w) // 10))
    return CH._png(fig)


def caption(sym, tf, f):
    """लहान caption (Telegram, HTML-safe — फक्त आकडे / शब्द)."""
    n = f.get("nearest")
    ctx = f.get("ctx") or {}
    head = f"{sym} · {tf} · Daily {ctx.get('trend') or 'n/a'}"
    if not n:
        return head
    return head + f" · nearest {_kind(n['side'])} {_rng(n['lo'], n['hi'])} ({n.get('tf') or ''}) · entry only after handover + commitment + 5M CHoCH"


def render(V, sym, f, weekly=None, line=None, tfs=TFS, deadline=None, clock=None):
    """[(tf, png bytes, caption)] — प्रत्येक tf स्वतंत्र (एक अयशस्वी ⇒ तोच वगळला, कारण errors मध्ये). deadline (clock() वेळ) पार ⇒
    उरलेले charts वगळले ("skipped (time budget)") — संदेश उशिरा जाऊ नये. रिटर्न (items, errors)."""
    import time
    clock = clock or time.monotonic
    fn = {"Daily": daily_png, "1H": h1_png, "15M": m15_png}
    items, errors = [], []
    for tf in tfs:
        if deadline is not None and clock() > deadline:
            errors.append(f"{tf}: skipped (time budget)")
            continue
        try:
            kw = {} if tf == "Daily" else {"line": line}
            items.append((tf, fn[tf](V, sym, f, weekly, **kw), caption(sym, tf, f)))
        except Exception as exc:                                           # noqa: BLE001 — chart कधीच संदेश थांबवत नाही
            errors.append(f"{tf}: {type(exc).__name__}: {exc}")
        finally:
            plt.close("all")
    return items, errors
