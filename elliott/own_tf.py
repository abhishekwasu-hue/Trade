"""elliott/own_tf.py — Daily / Weekly count त्यांच्याच OHLC च्या pivots वरून (Phase B §2.6; Abhi 2026-10-09).

सध्याच्या `auto_by_bars` मध्ये D0–D3 सगळे 5m pivots वरून ⇒ Daily count (A4b) बहुतेक gray. इथे: daily / weekly bars (बंद bars फक्त, decision
वेळेपर्यंत) वरच swings.degree_pivots (त्याच TF चा ATR ⇒ त्याच TF चा MR) आणि counts.CountEngine. टप्पा B मध्ये फक्त मोजमाप; live वापर
Evening Plan PR मध्ये. 1H / 15M ची सध्याची पद्धत बदलत नाही.

Weekly bar = सोमवार–शुक्रवार (NSE sessions), फक्त पूर्ण झालेले आठवडे (त्या आठवड्याचा शुक्रवार 15:30 ≤ asof) — चालू आठवडा अर्धवट ⇒ नाही.
"""
import pandas as pd

from . import swings as W

TFS = ("1d", "1w")


def daily_frame(df1m):
    """1m ⇒ बंद daily bars (timestamp, bar_end, OHLC). लांब इतिहास: caller data_policy नेच data देतो."""
    return W.build_frame(df1m, "1d")


def weekly_frame(daily):
    """बंद daily bars ⇒ weekly bars. timestamp = आठवड्याचा पहिला session, bar_end = त्या आठवड्याचा शुक्रवार 15:30 (सुट्टी असली तरी)."""
    if daily is None or not len(daily):
        return pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close"])
    d = daily.copy()
    d["_wk"] = pd.to_datetime(d["timestamp"]).dt.to_period("W-FRI")
    g = d.groupby("_wk").agg(timestamp=("timestamp", "first"), open=("open", "first"), high=("high", "max"), low=("low", "min"),
                             close=("close", "last")).reset_index()
    g["bar_end"] = g["_wk"].dt.end_time.dt.normalize() + pd.Timedelta(hours=15, minutes=30)
    return g[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


def multi_degree(frame, s, now, tf):
    """एकाच TF frame वर सगळ्या degrees (degree = swing_atr_mult[d] × त्या TF चा ATR). फक्त bar_end ≤ now. swings.multi_degree चाच आकार."""
    fr = W.asof(frame, now)
    out = {}
    for d in range(s["degree_levels"]):
        conf = W.degree_pivots(fr, d, s, tf)
        out[d] = {"tf": tf, "frame": fr, "confirmed": conf, "tentative": W.tentative_pivot(fr, conf, d, tf=tf)}
    return out


def snapshot(frame, now, tf, es=None):
    """(md, CountEngine snapshot) — decision वेळ `now` पर्यंतचे बंद bars फक्त. अपयश ⇒ (None, कारण)."""
    from . import settings as ES
    from .counts import CountEngine
    es = es or dict(ES.DEFAULTS)
    try:
        md = multi_degree(frame, es, pd.Timestamp(now), tf)
        return md, CountEngine(md, es).snapshot(pd.Timestamp(now))
    except Exception as exc:                                               # noqa: BLE001 — गुपचूप नाही: कारण नोंदीत
        return None, f"{type(exc).__name__}: {str(exc)[:80]}"


def brief(md, snap):
    """अहवालासाठी: प्रत्येक degree चे pivots, gray, preferred / alternate."""
    if md is None:
        return {"error": snap}
    out = {}
    for d, v in snap.degrees.items():
        pref = v.preferred or (v.nodes[0] if v.nodes else None)
        alt = next((n for n in v.nodes if n is not pref), None)
        out[d] = {"n_pivots": len(md[d]["confirmed"]), "gray": bool(v.gray), "beam": len(v.nodes),
                  "preferred": None if pref is None else f"{pref.pattern}/{pref.current_wave}",
                  "alternate": None if alt is None else f"{alt.pattern}/{alt.current_wave}",
                  "points": [] if pref is None else [(str(pd.Timestamp(p.ts).date()), round(float(p.price), 1)) for p in pref.points]}
    return out
