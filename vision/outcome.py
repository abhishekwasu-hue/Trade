"""vision/outcome.py — trade बंद झाल्यावर `_outcome.png` (POST-HOC, cross-verify साठी). **हा chart vision कडे कधीच जात नाही.**

    python3 -m vision.outcome            # cron: दर 15 मिनिटं 09:30–16:30 IST (+ 15:45 एकदा)

🎓 प्रत्येक DONE signal (outcome नसलेला, मागचे 3 दिवस): त्याच bot (source) + symbol चा live_trades (local SQLite) मधला trade — entry_time
signal च्या −1…+10 मिनिटांत, सर्वात आधीचा. Trade CLOSED ⇒ signal च्या 30 मिनिटं आधीपासून exit नंतर 15 मिनिटांपर्यंत 1m (5m candles) chart:
signal वेळ, entry (वेळ + spot), exit (वेळ + त्या minute चा close), level रेषा, SL / target (₹, P&L स्तरावर — spot मध्ये नाहीत) मजकुरात, legs चे strikes रेषा म्हणून,
आणि ठळक "POST-HOC" शीर्षक. No-lookahead नियम फक्त `_sent.png` ला. Trade सापडला नाही आणि signal 1 दिवसापेक्षा जुना ⇒ outcome = no_trade.
V1 मध्ये नाकारलेल्या signals चे shadow trades याच मार्गाने (source = <bot>_vision_shadow).
"""
import argparse
import math
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

from . import chart as CH
from . import images as IM
from . import store as VS

WIDTH, HEIGHT = 1000, 700
POST_HOC = "POST-HOC: NOT SENT TO VISION (outcome after the trade, for cross-check only)"
POST_HOC_MR = "POST-HOC: vision ला पाठवलेली नाही · NOT SENT TO VISION"
_DEVA = None


def devanagari_available():
    """Chromium (kaleido) ला Devanagari font दिसतो का (`fc-list :lang=mr`) — नसेल तर मराठी अक्षरं डबे दिसतात, म्हणून मग फक्त इंग्रजी."""
    global _DEVA
    if _DEVA is None:
        try:
            import subprocess
            _DEVA = bool(subprocess.run(["fc-list", ":lang=mr"], capture_output=True, text=True, timeout=5).stdout.strip())
        except Exception:
            _DEVA = False
    return _DEVA


def post_hoc_label():
    return POST_HOC_MR if devanagari_available() else POST_HOC


def strike_lines(trade):
    """live_trades.legs_json → [(strike, label)] (उदा. "SELL 25000 PE"). नसेल / चुकीचं ⇒ []."""
    import json
    try:
        legs = json.loads(trade.get("legs_json") or "[]")
    except (TypeError, ValueError):
        return []
    by_k = {}
    for leg in legs if isinstance(legs, list) else []:
        try:
            k = float(leg.get("strike"))
        except (TypeError, ValueError, AttributeError):
            continue
        if not math.isfinite(k) or k <= 0:                               # MCX futures चा dummy strike 0 / NaN
            continue
        side = str(leg.get("transaction_type") or leg.get("role") or "").upper()
        by_k.setdefault(k, []).append(f"{side} {k:,.0f} {leg.get('option_type') or ''}".strip())
    return [(k, " / ".join(v)) for k, v in by_k.items()]                  # एकाच strike चे legs (butterfly) एका label मध्ये


def find_trade(row, trades_db=None, path=None):
    """live_trades मधला जुळणारा PAPER trade (dict) किंवा None. entry_time ∈ [signal_ts, signal_ts + 10 मिनिटं]; आधीच दुसऱ्या signal ला जोडलेला
    trade नाही; signal आणि entry च्या मध्ये त्याच bot/symbol चा दुसरा signal असेल तर तो trade त्या नंतरच्या signal चा ⇒ None.
    DB चुका (locked / table नाही) raise होतात — `run()` त्या error म्हणून नोंदवतो आणि पुढच्या run ला पुन्हा (no_trade म्हणून चुकून नाही)."""
    if trades_db is None:
        from config import DB_PATH
        trades_db = DB_PATH
    t = pd.Timestamp(row["signal_ts"])
    # V1: entry approve नंतर (executed_at) होतो; नाकारलेले (SHADOWED / DRIFT_REJECTED) ⇒ "<bot>_vision_shadow" source चा PAPER shadow
    t_hi = pd.Timestamp(row["executed_at"]) if row.get("executed_at") else t
    source = f"{row['bot']}_vision_shadow" if row.get("status") in ("SHADOWED", "DRIFT_REJECTED") else row["bot"]
    lo, hi = t.strftime("%Y-%m-%d %H:%M:%S"), (t_hi + pd.Timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.exists(trades_db):
        raise FileNotFoundError(f"trades DB नाही: {trades_db}")
    conn = sqlite3.connect(f"file:{trades_db}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cands = [dict(r) for r in conn.execute(
            "SELECT * FROM live_trades WHERE source=? AND symbol=? AND entry_time >= ? AND entry_time <= ? AND mode='PAPER' ORDER BY entry_time",
            (source, row["symbol"], lo, hi))]
    finally:
        conn.close()
    with VS.connect(path) as c:
        linked = {r[0] for r in c.execute("SELECT trade_id FROM vision_signals WHERE trade_id IS NOT NULL AND signal_id != ?", (row["signal_id"],))}
        later = [r[0] for r in c.execute("SELECT COALESCE(executed_at, signal_ts) FROM vision_signals WHERE bot=? AND symbol=? "
                                         "AND COALESCE(executed_at, signal_ts) > ? AND COALESCE(executed_at, signal_ts) <= ? AND signal_id != ?",
                                         (row["bot"], row["symbol"], VS._iso(t_hi), VS._iso(t_hi + pd.Timedelta(minutes=10)),
                                          row["signal_id"]))]
    for tr in cands:
        if tr["trade_id"] in linked:
            continue
        e = pd.Timestamp(tr["entry_time"])
        if any(t_hi < pd.Timestamp(x) <= e for x in later):
            return None
        return tr
    return None


def build_outcome_figure(df1m, row, trade):
    import plotly.graph_objects as go
    d = CH.norm_1m(df1m)
    t_sig = pd.Timestamp(row["signal_ts"])
    t_in, t_out = pd.Timestamp(trade["entry_time"]), pd.Timestamp(trade["exit_time"])
    w = d[(d["timestamp"] >= t_sig - pd.Timedelta(minutes=30)) & (d["timestamp"] <= t_out + pd.Timedelta(minutes=15))]
    bars = CH.resample(w, 5).reset_index(drop=True)
    if len(bars) < 2:
        raise ValueError("outcome chart साठी candles अपुरे")
    x = np.arange(len(bars))
    fig = go.Figure(go.Candlestick(x=x, open=bars["open"], high=bars["high"], low=bars["low"], close=bars["close"], showlegend=False,
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350"))

    def xi(ts):
        return int(np.clip(np.searchsorted(bars["start"].to_numpy(), np.datetime64(ts), side="right") - 1, 0, len(bars) - 1))

    def close_at(ts):
        m = d[d["timestamp"] <= ts]
        return float(m["close"].iloc[-1]) if len(m) else float(bars["close"].iloc[-1])

    n = len(bars)
    if row.get("level") is not None:
        fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=row["level"], y1=row["level"], line=dict(color="#90a4ae", width=1, dash="dot"))
    fig.add_shape(type="line", x0=xi(t_sig), x1=xi(t_sig), y0=0, y1=1, yref="paper", line=dict(color="#ffd54f", width=1, dash="dash"))
    fig.add_annotation(x=xi(t_sig), y=1, yref="paper", text="signal", showarrow=False, font=dict(color="#ffd54f"), yshift=8)
    lo, hi = float(bars["low"].min()), float(bars["high"].max())
    span = max(hi - lo, 1.0)
    if row.get("level") is not None:
        lo, hi = min(lo, float(row["level"])), max(hi, float(row["level"]))
    allow = max(span, 0.006 * hi)                                        # candles चा आकार टिकावा: फक्त जवळचे strikes (range किंवा ~0.6%) range मध्ये
    near = [(k, lab) for k, lab in strike_lines(trade) if lo - allow <= k <= hi + allow]
    for k, _ in near:
        lo, hi = min(lo, k), max(hi, k)
    pad = 0.05 * (hi - lo or 1.0)
    for k, lab in strike_lines(trade):                                   # SL / target ₹ स्तरावर ⇒ chart वर legs चे strikes (नफा / तोटा सीमा)
        sell = lab.startswith("SELL") or "SHORT" in lab
        if (k, lab) in near:
            fig.add_shape(type="line", x0=-0.5, x1=n - 0.5, y0=k, y1=k, line=dict(color="#ef9a9a" if sell else "#80cbc4", width=1, dash="dash"))
            fig.add_annotation(x=n - 1, y=k, text=lab, showarrow=False, xanchor="right", yshift=8, font=dict(size=10, color="#eceff1"))
        else:                                                            # लांबचा strike ⇒ कडेला खूण
            up = k > hi
            fig.add_annotation(x=n - 1, y=(hi + pad * 0.5) if up else (lo - pad * 0.5), text=("↑ " if up else "↓ ") + lab, showarrow=False,
                               xanchor="right", font=dict(size=10, color="#ef9a9a" if sell else "#80cbc4"))
    p_in = float(trade.get("entry_spot_price") or close_at(t_in))
    p_out = close_at(t_out)
    pnl = trade.get("realized_pnl")
    win = pnl is not None and float(pnl) > 0
    fig.add_trace(go.Scatter(x=[xi(t_in)], y=[p_in], mode="markers+text", text=["ENTRY"], textposition="bottom center", showlegend=False,
                             marker=dict(symbol="triangle-up" if str(row.get("direction")).upper().startswith("BULL") else "triangle-down",
                                         size=14, color="#42a5f5")))
    fig.add_trace(go.Scatter(x=[xi(t_out)], y=[p_out], mode="markers+text", text=[f"EXIT {trade.get('exit_reason') or ''}"], showlegend=False,
                             textposition="top center", marker=dict(symbol="x", size=14, color="#66bb6a" if win else "#ef5350")))
    info = (f"P&L ₹{float(pnl):,.0f}" if pnl is not None else "P&L —") + \
           (f" · SL ₹{float(trade['sl_pnl_level']):,.0f}" if trade.get("sl_pnl_level") is not None else "") + \
           (f" · target ₹{float(trade['target_pnl_level']):,.0f}" if trade.get("target_pnl_level") is not None else "") + \
           f" · {trade.get('strategy') or ''} · {t_in:%H:%M}→{t_out:%H:%M}"
    fig.add_annotation(x=0.01, y=0.02, xref="paper", yref="paper", text=info, showarrow=False, xanchor="left", font=dict(size=12, color="#eceff1"),
                       bgcolor="rgba(0,0,0,0.6)")
    step = max(1, n // 8)
    fig.update_xaxes(tickvals=list(range(0, n, step)), ticktext=[bars["start"].iloc[k].strftime("%H:%M") for k in range(0, n, step)],
                     rangeslider_visible=False, showgrid=False, color="#b0bec5")
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", color="#eceff1", range=[lo - pad, hi + pad])
    fig.update_layout(template="plotly_dark", width=WIDTH, height=HEIGHT, margin=dict(l=10, r=60, t=80, b=30), paper_bgcolor="#1a0f0f",
                      plot_bgcolor="#0e1117",
                      title=dict(text=f"<b>{post_hoc_label()}</b><br>{row['symbol']} · {row['bot']} · {row.get('direction')} · signal {t_sig:%d %b %H:%M}",
                                 font=dict(size=14, color="#ff8a65")))
    return fig, {"entry_spot": p_in, "exit_close": p_out, "win": win}


def run(since_days=3, fetch_fn=None, trades_db=None, path=None, now=None):
    """रिटर्न [(signal_id, status)] — status: outcome / open / no_trade / error."""
    now = pd.Timestamp(now or VS.now_ist())
    out, cache = [], {}
    for row in VS.pending_outcomes((now - pd.Timedelta(days=since_days)).date(), path):
        try:
            tr = find_trade(row, trades_db, path)
            if tr is None:
                if now - pd.Timestamp(row["signal_ts"]) > pd.Timedelta(days=1):
                    VS.set_outcome(row["signal_id"], path, outcome_json={"no_trade": True})
                    out.append((row["signal_id"], "no_trade"))
                continue
            if str(tr.get("status")).upper() != "CLOSED" or not tr.get("exit_time"):
                out.append((row["signal_id"], "open"))
                continue
            if row["symbol"] not in cache:
                fetch = fetch_fn or (lambda s: __import__("vision.worker", fromlist=["default_fetch"]).default_fetch(s, False)[0])
                cache[row["symbol"]] = fetch(row["symbol"])
            fig, meta = build_outcome_figure(cache[row["symbol"]], row, tr)
            png = fig.to_image(format="png", width=WIDTH, height=HEIGHT, scale=1)
            p, sha = IM.save_exclusive(IM.signal_path(row, IM.OUTCOME), png)
            pnl = tr.get("realized_pnl")
            VS.set_outcome(row["signal_id"], path, trade_id=tr["trade_id"], outcome_path=p, outcome_sha256=sha,
                           outcome_json={"trade_id": tr["trade_id"], "entry_time": tr["entry_time"], "exit_time": tr["exit_time"],
                                         "exit_reason": tr.get("exit_reason"), "realized_pnl": pnl,
                                         "result": None if pnl is None else ("win" if float(pnl) > 0 else "loss"), **meta})
            out.append((row["signal_id"], "outcome"))
        except Exception as exc:                                         # एकाचं अपयश बाकीच्यांना थांबवत नाही; पुढच्या run ला पुन्हा
            out.append((row["signal_id"], f"error: {type(exc).__name__}: {str(exc)[:120]}"))
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--since-days", type=int, default=3)
    a = p.parse_args(argv)
    for sid, st in run(a.since_days):
        print(sid, st)
    return 0


if __name__ == "__main__":
    sys.exit(main())

