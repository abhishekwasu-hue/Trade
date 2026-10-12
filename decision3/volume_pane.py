"""decision3/volume_pane.py — volume pane, सगळ्या setup / proposal / Telegram charts साठी एकच implementation (Abhi: "the volume test is not
visible on these charts"). फक्त दाखवण्यासाठी — engine निर्णयात नाही. Chart वरचा मजकूर English.

🎓 नियम (TRADE_SESSION_LEVEL_BOTS_CONFIRMATION, "VOLUME ON EVERY CHART"):
  • Source: index ⇒ त्याच्या futures चा volume (NIFTY ⇒ NIFTY FUT, BANKNIFTY ⇒ BANKNIFTY FUT, SENSEX ⇒ SENSEX FUT किंवा NA); किंमत spot ची.
    MCX ⇒ contract चा स्वतःचा volume. Spot index चा volume (0) कधीच वापरत नाही. नाही ⇒ pane मध्ये "volume: NA (grade cap B)".
  • Study window = area मध्ये arrival (ARMED) → commitment candle. Window मधला प्रत्येक volume bar trend-side / counter-side रंगात, window च्या
    सरासरी volume ची dashed रेघ, commitment bar वर खूण + "commitment vol 1.6× window avg".
  • Window सरासरी = commitment आधीचे window bars [arm, commit) — decision3.method.commitment (c0) सारखीच व्याख्या (arm == commit ⇒ तोच bar).
  • Caption / ticket साठी एकच ओळ: "volume: counter-side candles 0.7× → trend-side 1.4× · commitment 1.6× avg" किंवा NA_LINE.
  • Window / बाजू / commitment engine च्या output मधून (level_reaction.evaluate: arm_bar / confirm_bar; vision gate tags: arm_ts / confirm_ts;
    V22 row: bar + level; confirmation branch चा a2 / c0 / c1 dict — `info`). नसेल तर इथेच bars + area + दिशा वरून (evaluate चाच arrival
    नियम: area ला स्पर्श करणारी candle, आधीचा close approach बाजूला) — `computed` मध्ये नोंद.
  • No-lookahead: pane मध्ये फक्त दिलेले bars (setup bar पर्यंत); futures rows bar मध्ये जोडताना `asof` नंतर संपणारी row कधीच नाही.
"""
import numpy as np
import pandas as pd

NA_LINE = "volume: NA (grade cap B)"
INDEX_FUT = {"NIFTY": "NIFTY FUT", "BANKNIFTY": "BANKNIFTY FUT", "SENSEX": "SENSEX FUT", "FINNIFTY": "FINNIFTY FUT",
             "MIDCPNIFTY": "MIDCPNIFTY FUT"}
MAX_WINDOW_BARS = 48                    # fallback arrival शोध: commitment पासून इतके bars मागे (engine चं window नसेल तेव्हाच)
GID = "volume_pane"                     # tests: प्रत्येक chart मध्ये हा pane (किंवा NA मजकूर) आहे का

MPL = {"trend": "#2f6db5", "counter": "#d97a1e", "neutral": "#9e9e9e", "outside": "#c4c4c4", "avg": "#333333", "commit": "#111111",
       "na": "#8a1c1c", "ink": "#444444"}
PLOTLY = {"trend": "#42a5f5", "counter": "#ffa726", "neutral": "#78909c", "outside": "#455a64", "avg": "#eceff1", "commit": "#ffd54f",
          "na": "#ef9a9a", "ink": "#b0bec5"}


# ------------------------------------------------------------------------------------------------ source
def is_index(symbol):
    return str(symbol or "").upper() in INDEX_FUT


def source_label(symbol):
    """"NIFTY FUT" (index) / "<contract> own volume" (MCX)."""
    s = str(symbol or "").upper()
    return INDEX_FUT[s] if s in INDEX_FUT else f"{s or 'contract'} own volume"


def _ts(x):
    t = pd.to_datetime(x)
    if isinstance(t, pd.Series):
        if t.dt.tz is not None:
            t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        return t
    if getattr(t, "tzinfo", None) is not None:
        t = t.tz_convert("Asia/Kolkata").tz_localize(None)
    return t


def bar_volume(starts, ends, fut, asof=None):
    """प्रत्येक chart bar [start, end) मध्ये सुरू होणाऱ्या futures rows चा volume बेरीज (rows ची स्वतःची लांबी = त्यांच्या timestamps मधला
    median अंतर). asof ⇒ त्यानंतर संपणारी row नाही (भविष्य नाही). Row नाही ⇒ NaN. fut: DataFrame (timestamp, volume)."""
    st = _ts(pd.Series(starts)).to_numpy("datetime64[ns]")
    en = _ts(pd.Series(ends)).to_numpy("datetime64[ns]")
    out = np.full(len(st), np.nan)
    if fut is None or len(fut) == 0 or "volume" not in fut.columns or len(st) == 0:
        return out
    f = pd.DataFrame({"timestamp": _ts(fut["timestamp"]), "volume": pd.to_numeric(fut["volume"], errors="coerce")})
    f = f.dropna(subset=["timestamp"]).drop_duplicates("timestamp").sort_values("timestamp")
    if asof is not None:
        d = f["timestamp"].diff().dropna()
        step = d[d > pd.Timedelta(0)].median() if len(d) else pd.Timedelta(minutes=1)
        step = step if pd.notna(step) else pd.Timedelta(minutes=1)
        f = f[f["timestamp"] + step <= _ts(asof)]
    ft = f["timestamp"].to_numpy("datetime64[ns]")
    fv = f["volume"].to_numpy(float)
    pos = np.searchsorted(st, ft, side="right") - 1
    ok = (pos >= 0) & np.isfinite(fv)
    ok[ok] &= ft[ok] < en[pos[ok]]
    if ok.any():
        s = pd.Series(fv[ok]).groupby(pos[ok]).sum()
        out[s.index.to_numpy()] = s.to_numpy()
    return out


def own_volume(df):
    """MCX: bars चा स्वतःचा volume column (≤ 0 / नाही ⇒ NaN)."""
    if df is None or "volume" not in getattr(df, "columns", ()):
        return np.full(0 if df is None else len(df), np.nan)
    v = pd.to_numeric(df["volume"], errors="coerce").to_numpy(float)
    return np.where(v > 0, v, np.nan)


def available(vol):
    v = np.asarray(vol if vol is not None else [], dtype=float)
    return bool(len(v) and np.isfinite(v).any() and np.nanmax(v) > 0)


# ------------------------------------------------------------------------------------------------ window (engine output ⇒ indices)
_SIDE_WORDS = {"BULLISH": 1, "BULL": 1, "BUY": 1, "LONG": 1, "UP": 1, "SUPPORT": 1, "DEMAND": 1, "BULL PUT": 1,
               "BEARISH": -1, "BEAR": -1, "SELL": -1, "SHORT": -1, "DOWN": -1, "RESISTANCE": -1, "SUPPLY": -1, "BEAR CALL": -1}


def direction_of(x):
    """+1 (bullish: demand / support) / -1 (bearish: supply / resistance) / None."""
    if x is None:
        return None
    if isinstance(x, (int, float, np.integer, np.floating)) and np.isfinite(x) and x != 0:
        return 1 if x > 0 else -1
    return _SIDE_WORDS.get(str(x).strip().upper())


def _first(dicts, *keys):
    for d in dicts:
        for k in keys:
            if isinstance(d, dict) and d.get(k) is not None:
                return d[k]
    return None


def normalize_info(info):
    """Engine output (level_reaction.evaluate result, vision gate tags, V22 row, किंवा confirmation branch चा a2 / c0 / c1 dict) ⇒
    {arm_bar, arm_ts, commit_bar, commit_ts, d, area, vol_mult, ltf_bar, ltf_ts}. नसलेले keys ⇒ None."""
    info = info or {}
    subs = [info] + [info.get(k) for k in ("gate", "a2", "c0", "c1", "zone_study", "study", "commit", "commitment", "window", "ltf",
                                            "choch", "confirmation") if isinstance(info.get(k), dict)]
    tags = info.get("tags")
    if isinstance(tags, dict) and isinstance(tags.get("gate"), dict):
        subs.append(tags["gate"])
    win = _first(subs, "study_window", "window_bars")
    arm_bar = _first(subs, "arm_bar", "study_start", "window_start", "armed_bar")
    commit_bar = _first(subs, "confirm_bar", "commit_bar", "commitment_bar", "window_end")
    if isinstance(win, (list, tuple)) and len(win) == 2:
        arm_bar = win[0] if arm_bar is None else arm_bar
        commit_bar = win[1] if commit_bar is None else commit_bar
    area = _first(subs, "area")
    lv = info.get("level") if isinstance(info.get("level"), dict) else None
    if area is None and lv and lv.get("lo") is not None:
        area = (lv["lo"], lv["hi"])
    d = None
    for k in ("d", "direction", "side", "trade_side"):
        d = direction_of(_first(subs, k))
        if d is not None:
            break
    if d is None and lv:
        d = direction_of(lv.get("role"))
    vm = _first(subs, "vol_mult", "commit_vol_mult")
    return {"arm_bar": arm_bar, "arm_ts": _first(subs, "arm_ts", "study_start_ts", "window_start_ts"),
            "commit_bar": commit_bar,
            "commit_ts": _first(subs, "confirm_ts", "commit_ts", "commitment_ts"),
            "d": d, "area": None if area is None else (float(min(area)), float(max(area))), "vol_mult": vm,
            "ltf_bar": _first(subs, "choch_bar", "ltf_bar"), "ltf_ts": _first(subs, "choch_ts", "ltf_ts")}


def index_at(times, ts):
    """times (bar starts, क्रमाने) मधला ts असलेला bar (start ≤ ts < पुढचा start). बाहेर ⇒ None."""
    if ts is None or times is None or len(times) == 0:
        return None
    t = np.asarray(_ts(pd.Series(times)).to_numpy("datetime64[ns]"))
    x = np.datetime64(pd.Timestamp(_ts(ts)).to_datetime64(), "ns")
    i = int(np.searchsorted(t, x, side="right") - 1)
    return i if 0 <= i < len(t) else None


def find_arrival(O, H, L, C, area, d, t, max_back=MAX_WINDOW_BARS):
    """level_reaction.evaluate चा arrival नियम: area ला स्पर्श (overlap) आणि आधीचा close approach बाजूला (demand ⇒ वर, supply ⇒ खाली).
    t पासून मागे सर्वात जवळचा. नाही ⇒ t पर्यंत area ला सलग स्पर्श करणाऱ्या bars ची सुरुवात (तीही नाही ⇒ t)."""
    lo, hi = area
    for i in range(int(t), max(-1, int(t) - int(max_back)), -1):
        if L[i] <= hi and H[i] >= lo:
            pc = C[i - 1] if i > 0 else O[i]
            if (pc > hi) if d > 0 else (pc < lo):
                return i, "arrival"
    i = int(t)
    while i - 1 >= max(0, int(t) - int(max_back)) and L[i - 1] <= hi and H[i - 1] >= lo:
        i -= 1
    return i, "contiguous touch"


def _resolve(times, ts, bar, n):
    """Engine चा ts (असेल तर तोच — chart चे bars engine पेक्षा वेगळे / कापलेले असू शकतात) नाहीतर bar index. ts पहिल्या दाखवलेल्या
    bar आधी ⇒ 0 ("clamped"); नंतर ⇒ None."""
    if ts is not None and times is not None and len(times):
        i = index_at(times, ts)
        if i is None and _ts(ts) < _ts(pd.Series(times)).iloc[0]:
            return 0, "clamped"
        return i, "ts"
    if bar is not None and 0 <= int(bar) < n:
        return int(bar), "bar"
    return None, None


# ------------------------------------------------------------------------------------------------ study (numbers + caption line)
def study(bars, vol=None, info=None, area=None, d=None, commit=None, arm=None, symbol=None):
    """bars: DataFrame (open, high, low, close + timestamp / start). vol: bars शी जुळणारा array (नसेल ⇒ bars["volume"]). info: engine
    output (normalize_info). area / d / commit / arm: थेट दिलेले (info पेक्षा प्राधान्य). रिटर्न dict: vol, ok (window मध्ये volume आहे),
    arm, commit, d, side (+1 trend / -1 counter / 0 doji, window बाहेर None), avg, commit_mult, trend_mult, counter_mult, line, computed."""
    n = len(bars)
    if vol is None:
        vol = own_volume(bars) if "volume" in bars.columns else np.full(n, np.nan)
    vol = np.asarray(vol, dtype=float)
    vol = np.where(vol > 0, vol, np.nan)
    ni = normalize_info(info)
    times = bars["timestamp"] if "timestamp" in bars.columns else bars.get("start")
    computed = []
    d = direction_of(d) if d is not None else ni["d"]
    area = area if area is not None else ni["area"]
    from_engine = commit is not None
    if commit is None:
        commit, how = _resolve(times, ni["commit_ts"], ni["commit_bar"], n)
        from_engine = commit is not None
        if commit is None:
            commit = n - 1                                                # setup / signal bar = शेवटचा दाखवलेला bar
            computed.append("commitment = last bar")
    if arm is None:
        arm, how = _resolve(times, ni["arm_ts"], ni["arm_bar"], n)
        if how == "clamped":
            computed.append("window starts before the first bar shown")
    out = {"vol": vol, "n": n, "symbol": symbol, "source": source_label(symbol) if symbol else None, "d": d, "arm": None,
           "commit": None, "side": [None] * n, "avg": None, "commit_mult": None, "trend_mult": None, "counter_mult": None,
           "ok": False, "pane": available(vol), "computed": computed, "line": NA_LINE}
    if n == 0 or commit is None or not (0 <= int(commit) < n):
        return out
    commit = int(commit)
    O, H, L, C = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    if d is None:
        d = 1 if C[commit] >= O[commit] else -1                           # दिशा नाही ⇒ commitment candle चा रंग
        computed.append("direction from commitment candle")
    if arm is None or not (0 <= int(arm) <= commit):
        if area is not None:
            arm, how = find_arrival(O, H, L, C, area, d, commit)
            computed.append(f"window start = {how} (bars + area + direction)")
        else:
            arm = max(0, commit - 7)
            computed.append("window start = commitment - 7 bars (no area)")
    arm = int(arm)
    out.update(arm=arm, commit=commit, d=d)
    for i in range(arm, commit + 1):
        b = (C[i] - O[i]) * d
        out["side"][i] = 1 if b > 0 else (-1 if b < 0 else 0)
    pre = list(range(arm, commit)) or [commit]
    pv = vol[pre]
    pv = pv[np.isfinite(pv)]
    if not len(pv) or not np.isfinite(vol[commit]):
        return out                                                         # window मध्ये volume नाही ⇒ NA (grade cap B)
    avg = float(pv.mean())
    if avg <= 0:
        return out

    def side_mult(sd):
        x = [vol[i] for i in pre if out["side"][i] == sd and i != commit and np.isfinite(vol[i])]
        return round(float(np.mean(x)) / avg, 2) if x else None
    cm = float(vol[commit]) / avg
    if ni["vol_mult"] is not None and from_engine:
        cm = float(ni["vol_mult"])                                         # engine (c0) चा आकडा — तोच दाखवायचा
    out.update(ok=True, avg=avg, commit_mult=round(cm, 2), trend_mult=side_mult(1), counter_mult=side_mult(-1))
    out["line"] = line(out)
    return out


def _x(v):
    return "-" if v is None else f"{v:.1f}×"


def line(st):
    """Caption / ticket ची एकच volume ओळ."""
    if not st or not st.get("ok"):
        return NA_LINE
    return (f"volume: counter-side candles {_x(st['counter_mult'])} → trend-side {_x(st['trend_mult'])} · "
            f"commitment {_x(st['commit_mult'])} avg")


def commit_label(st, what="commitment"):
    return f"{what} vol {st['commit_mult']:.1f}× window avg" if st.get("ok") else NA_LINE


def colors(st, pal):
    out = []
    for i in range(st["n"]):
        s = st["side"][i]
        out.append(pal["outside"] if s is None else pal["trend"] if s == 1 else pal["counter"] if s == -1 else pal["neutral"])
    return out


# ------------------------------------------------------------------------------------------------ matplotlib
def draw_mpl(ax, st, x=None, title=None, label_commit=True, commit_what="commitment", legend=True, xlim=None):
    """Price panel खालच्या ax वर volume pane. x = bars चे x (default 0..n-1). Volume नाही ⇒ फक्त NA मजकूर (pane तरी राहतो)."""
    n = st["n"]
    x = np.arange(n) if x is None else np.asarray(x, dtype=float)
    ax.set_gid(GID)
    ax.set_yticks([])
    ax.tick_params(labelsize=7.5)
    if xlim is not None:
        ax.set_xlim(*xlim)
    ttl = title or f"volume ({st.get('source') or 'futures'})"
    if legend and st["commit"] is not None and st["pane"]:
        ttl += " · blue = trend-side, orange = counter-side (study window) · dashed = window avg"
    ax.text(0.003, 0.97, ttl, transform=ax.transAxes, fontsize=7.5, color=MPL["ink"], va="top", ha="left", zorder=9,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.5))
    v = st["vol"]
    if not st["pane"]:
        t = ax.text(0.5, 0.5, NA_LINE, transform=ax.transAxes, fontsize=9, color=MPL["na"], ha="center", va="center")
        t.set_gid(GID + "_na")
        ax.set_ylim(0, 1)
        return ax
    vv = np.where(np.isfinite(v), v, 0.0)
    ax.bar(x, vv, width=0.66, color=colors(st, MPL), lw=0, zorder=3)
    top = float(np.nanmax(v)) if np.isfinite(v).any() else 1.0
    ax.set_ylim(0, top * 1.6)
    miss = ~np.isfinite(v)
    if miss.any():
        ax.plot(x[miss], np.full(miss.sum(), top * 0.02), ls="none", marker="|", ms=4, color="#bbbbbb", zorder=2)
    if st["ok"]:
        a, c = st["arm"], st["commit"]
        ax.hlines(st["avg"], x[a] - 0.5, x[c] + 0.5, colors=MPL["avg"], linestyles="--", lw=1.1, zorder=5)
        ax.bar([x[c]], [vv[c]], width=0.8, facecolor="none", edgecolor=MPL["commit"], lw=1.6, zorder=6)
        if label_commit:                                                   # pane च्या वरच्या भागात, commitment bar कडे बाण
            ax.annotate(commit_label(st, commit_what), (x[c], vv[c]), xytext=(x[c], top * 1.3), textcoords="data", ha="right",
                        va="center", fontsize=8, color=MPL["commit"], fontweight="bold", zorder=9, annotation_clip=False,
                        arrowprops=dict(arrowstyle="-", color=MPL["commit"], lw=0.7),
                        bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=0.5))
    elif st["commit"] is not None:
        ax.text(0.5, 0.80, NA_LINE + " (no volume in the study window)", transform=ax.transAxes, fontsize=8, color=MPL["na"],
                ha="center", va="center").set_gid(GID + "_na")
    return ax


def draw_daily_mpl(ax, vol, x=None, source=None, partial_last=True):
    """Daily volume pane: साधे bars (window नाही). शेवटचा (setup दिवस, setup bar पर्यंत) फिकट. सगळे NaN ⇒ NA मजकूर."""
    v = np.asarray(vol, dtype=float)
    v = np.where(v > 0, v, np.nan)
    x = np.arange(len(v)) if x is None else np.asarray(x, dtype=float)
    ax.set_gid(GID)
    ax.set_yticks([])
    ax.text(0.003, 0.95, f"Daily volume ({source or 'futures'})" + ("; last bar = setup day up to the setup bar" if partial_last else ""),
            transform=ax.transAxes, fontsize=7.5, color=MPL["ink"], va="top", ha="left", zorder=9,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.5))
    if not available(v):
        ax.text(0.5, 0.45, NA_LINE, transform=ax.transAxes, fontsize=9, color=MPL["na"], ha="center", va="center").set_gid(GID + "_na")
        ax.set_ylim(0, 1)
        return ax
    cols = [MPL["outside"]] * len(v)
    if partial_last and len(v) and np.isfinite(v[-1]):
        cols[-1] = "#e7c66a"
    ax.bar(x, np.where(np.isfinite(v), v, 0.0), width=0.62, color=cols, lw=0, zorder=3)
    ax.set_ylim(0, float(np.nanmax(v)) * 1.3)
    if len(v) and not np.isfinite(v[-1]) and partial_last:
        ax.text(x[-1], float(np.nanmax(v)) * 0.05, "NA", fontsize=6.5, color=MPL["na"], ha="center", va="bottom")
    return ax


def mpl_has_pane(fig):
    """Test helper: figure मध्ये volume pane (bars) किंवा स्पष्ट "volume: NA" मजकूर."""
    for ax in fig.axes:
        if ax.get_gid() == GID:
            return True
        if any("volume: NA" in t.get_text() for t in ax.texts):
            return True
    return any("volume: NA" in t.get_text() for t in fig.texts)


# ------------------------------------------------------------------------------------------------ plotly (vision chart)
def add_plotly(fig, st, row, col, x=None, title=None, commit_what="commitment"):
    """Vision chart (plotly) च्या (row, col) subplot मध्ये volume pane. Volume नाही ⇒ NA annotation."""
    import plotly.graph_objects as go
    n = st["n"]
    x = np.arange(n) if x is None else np.asarray(x)
    fig.update_yaxes(showticklabels=False, showgrid=False, row=row, col=col)
    fig.update_xaxes(showticklabels=False, showgrid=False, range=[-0.5, max(n, 1) - 0.5], row=row, col=col)
    ttl = title or f"vol {st.get('source') or 'futures'}"
    if not st["pane"]:
        fig.update_yaxes(range=[0, 1], row=row, col=col)
        fig.add_annotation(x=(n - 1) / 2 if n else 0, y=0.5, text=NA_LINE, showarrow=False, font=dict(size=10, color=PLOTLY["na"]),
                           row=row, col=col)
        fig.add_annotation(x=-0.5, y=1, text=ttl, showarrow=False, xanchor="left", yanchor="top", font=dict(size=8, color=PLOTLY["ink"]),
                           row=row, col=col)
        return fig
    v = st["vol"]
    vv = np.where(np.isfinite(v), v, 0.0)
    top = float(np.nanmax(v))
    fig.add_trace(go.Bar(x=x, y=vv, marker_color=colors(st, PLOTLY), marker_line_width=0, showlegend=False, name="volume"),
                  row=row, col=col)
    fig.update_yaxes(range=[0, top * 1.45], row=row, col=col)
    fig.add_annotation(x=-0.5, y=top * 1.45, text=ttl + (" · blue trend-side / orange counter-side" if st["commit"] is not None else ""),
                       showarrow=False, xanchor="left", yanchor="top", font=dict(size=8, color=PLOTLY["ink"]), row=row, col=col)
    if st["ok"]:
        a, c = st["arm"], st["commit"]
        fig.add_shape(type="line", x0=x[a] - 0.5, x1=x[c] + 0.5, y0=st["avg"], y1=st["avg"], line=dict(color=PLOTLY["avg"], width=1,
                      dash="dash"), row=row, col=col)
        fig.add_shape(type="rect", x0=x[c] - 0.45, x1=x[c] + 0.45, y0=0, y1=vv[c], line=dict(color=PLOTLY["commit"], width=1.5),
                      row=row, col=col)
        fig.add_annotation(x=x[c], y=vv[c], text=commit_label(st, commit_what), showarrow=False, xanchor="right", yanchor="bottom",
                           font=dict(size=8, color=PLOTLY["commit"]), row=row, col=col)
    elif st["commit"] is not None:
        fig.add_annotation(x=(n - 1) / 2, y=top * 1.2, text=NA_LINE + " (no volume in the study window)", showarrow=False,
                           font=dict(size=9, color=PLOTLY["na"]), row=row, col=col)
    return fig


def plotly_has_pane(fig):
    """Test helper: volume Bar trace किंवा "volume: NA" annotation."""
    if any(getattr(t, "type", None) == "bar" and getattr(t, "name", None) == "volume" for t in fig.data):
        return True
    return any("volume: NA" in str(a.text) for a in fig.layout.annotations)
