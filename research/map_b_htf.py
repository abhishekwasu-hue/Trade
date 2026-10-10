"""research/map_b_htf.py — टप्पा B §2.6: Daily / Weekly counts त्यांच्याच OHLC च्या pivots वरून (elliott/own_tf.py). फक्त अहवाल.

IS (data_policy नेच) मधल्या दर `--every` व्या session च्या close ला (फक्त त्या close पर्यंतचे बंद daily / पूर्ण weekly bars): प्रत्येक
degree चं gray, preferred / alternate. तुलना: A4b (D0–D3 सगळे 5m pivots वरून ⇒ Daily 100% gray). काही weeks चे charts (PNG → private
trade-data). Daily trendline लांब इतिहासावर (backtest_review.daily.facts) — सापडते का, नसेल तर कारण.

Abhi च्या weekly count (A = 26,277 → 21,743, B = 26,373, (C) मधला (4) ≈ 24,677 Aug 2026) शी तुलना **इथे शक्य नाही**: त्यासाठी 2024-04 →
2026-06 daily data लागतो, जो holdout आहे (data_policy: कधीच नाही). Abhi चा निर्णय हवा (उदा. फक्त weekly OHLC ची वेगळी परवानगी).

    python3 research/map_b_htf.py --is-data data/nifty50_1min.parquet --every 5 --out docs/reports/situation_map --png-dir <trade-data>/...
"""
import argparse
import collections
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP            # noqa: E402
from elliott import own_tf as OT                 # noqa: E402


def read(path):
    raw = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return DP.filter_allowed(raw, "research")


def scan(daily, weekly, start, end, every):
    days = [d for d in daily["timestamp"] if pd.Timestamp(start) <= d <= pd.Timestamp(end)][::every]
    rows = []
    for d in days:
        now = pd.Timestamp(d) + pd.Timedelta(hours=15, minutes=30)
        for tf, fr in (("1d", daily), ("1w", weekly)):
            md, snap = OT.snapshot(fr, now, tf)
            b = OT.brief(md, snap)
            if "error" in b:
                rows.append({"t": str(now), "tf": tf, "error": b["error"]})
                continue
            for dg, v in b.items():
                rows.append({"t": str(now), "tf": tf, "degree": dg, **v})
    return rows


def chart(frame, now, tf, title, path):
    import plotly.graph_objects as go
    fr = frame[frame["bar_end"] <= now].tail(160 if tf == "1w" else 250)
    md, snap = OT.snapshot(frame, now, tf)
    fig = go.Figure(go.Candlestick(x=fr["timestamp"], open=fr["open"], high=fr["high"], low=fr["low"], close=fr["close"], name=tf))
    b = OT.brief(md, snap) if md else {}
    for dg, v in sorted(b.items(), reverse=True)[:2]:
        if v.get("points"):
            xs, ys = zip(*v["points"])
            fig.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines+markers", name=f"D{dg} {v['preferred']}" + (" (gray)" if v["gray"] else "")))
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, width=1100, height=560, template="plotly_white")
    fig.write_image(path, format="png", scale=1)
    return os.path.basename(path)


def report(rows, tl_rows, every, start, end):
    df = pd.DataFrame([r for r in rows if "degree" in r])
    err = sum(1 for r in rows if "error" in r)
    L = ["# टप्पा B §2.6: Daily / Weekly counts त्यांच्याच OHLC वरून (फक्त अहवाल)", "",
         f"IS {start} → {end}, दर {every} व्या session चा close; फक्त त्या close पर्यंतचे बंद daily bars / पूर्ण झालेले weeks (no-lookahead "
         "test: tests/test_phase_b.py). Degree = swing_atr_mult[d] × त्या TF चा ATR (swings.py), counts = elliott.counts (default settings). "
         f"Engine error {err}. **Live वापर Evening Plan PR मध्ये**; तोपर्यंत weekly context = Abhi चा मान्य weekly count.", "",
         "तुलना: A4b — सध्याच्या auto_by_bars मध्ये D0–D3 सगळे 5m pivots वरून ⇒ fixed-mode Daily (1d) 100% gray.", "",
         "| TF | degree | नमुने | gray % | median pivots | सर्वात सामान्य preferred |", "|---|---|---|---|---|---|"]
    if len(df):
        for (tf, dg), g in df.groupby(["tf", "degree"]):
            top = collections.Counter(g["preferred"].dropna()).most_common(2)
            L.append(f"| {tf} | D{dg} | {len(g)} | {100 * g['gray'].mean():.0f}% | {int(g['n_pivots'].median())} | "
                     f"{', '.join(f'{k} ×{v}' for k, v in top) or '—'} |")
    L += ["", "## Abhi च्या weekly count शी तुलना", "",
          "**शक्य नाही (data policy):** Abhi चा count (A 26,277 → 21,743, B 26,373, (C) मधला (4) ≈ 24,677) 2024-09 → 2026 मधला आहे. "
          "त्यासाठी 2024-04 → 2026-06 चा daily / weekly data लागतो = **holdout** (कधीच नाही). Jul–Oct 2026 (illustration) फक्त 3 महिने ⇒ "
          "weekly count साठी अपुरा. **Abhi चा निर्णय हवा.** तोपर्यंत weekly context = Abhi चा मान्य count (`abhi_counts`, ✔ नंतर).", "",
          "## Daily trendline (लांब इतिहास)", ""]
    for r in tl_rows:
        L.append(f"- {r['t'][:10]}: {r['line']}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2021-12-31")
    ap.add_argument("--every", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--png-dir", default=None)
    a = ap.parse_args()
    raw = read(a.is_data)
    daily = OT.daily_frame(raw)
    weekly = OT.weekly_frame(daily)
    rows = scan(daily, weekly, a.start, a.end, a.every)
    from backtest_review import daily as DL
    tl_rows = []
    for t in ("2017-06-30", "2019-06-28", "2021-06-30", "2021-12-31"):
        now = pd.Timestamp(t) + pd.Timedelta(hours=15, minutes=30)
        try:
            f = DL.facts(raw[raw["timestamp"] < now], now)
            tl = f.get("trendline")
            tl_rows.append({"t": t, "line": f"{f['line']} · daily trendline: {'आहे' if tl else 'नाही (≥ 3 touches ची रेषा सापडली नाही)'}"})
        except Exception as exc:                                            # noqa: BLE001
            tl_rows.append({"t": t, "line": f"error {type(exc).__name__}: {str(exc)[:80]}"})
    if a.png_dir:
        os.makedirs(a.png_dir, exist_ok=True)
        for t in ("2018-02-16", "2020-03-27", "2021-11-12"):
            now = pd.Timestamp(t) + pd.Timedelta(hours=15, minutes=30)
            chart(weekly, now, "1w", f"{t} · Weekly own-OHLC count (no-lookahead)", os.path.join(a.png_dir, f"weekly_{t}.png"))
            chart(daily, now, "1d", f"{t} · Daily own-OHLC count (no-lookahead)", os.path.join(a.png_dir, f"daily_{t}.png"))
    with open(os.path.join(a.out, "B_htf_own_ohlc.md"), "w", encoding="utf-8") as fh:
        fh.write(report(rows, tl_rows, a.every, a.start, a.end))
    if a.json_out:
        os.makedirs(a.json_out, exist_ok=True)
        json.dump(rows, open(os.path.join(a.json_out, "B_htf_own_ohlc.json"), "w"), ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
