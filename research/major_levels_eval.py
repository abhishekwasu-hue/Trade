"""
research/major_levels_eval.py
-----------------------------
🎓 Major Level (Trader's Eye) engine v1 — टप्पा (a): वापरकर्त्याच्या हाताने काढलेल्या levels (docs/reports/ground_truth_levels.csv) शी तुलना.
Report-only; कुठलाही bot gate नाही.

दोन भाग:
  1) --export (VPS वर; Upstox token लागतो, फक्त candles **वाचतो** — order/DB write नाही):
       NIFTY 15m (fetch_candles, 70 दिवस) आणि GOLD/COPPER/SILVER 30m (front-month, fetch_mcx_candles, 110 दिवस) →
       data/research/major_levels_candles/<SYMBOL>_<tf>.csv (gitignored). MCX साठी bot चा (roll) contract आणि सर्वात जवळचा न-expire contract
       वेगळे असतील तर दोन्ही (`__near`). **बदल (Abhi, 2026-10-06):** Trade repo public आहे ⇒ Upstox candles इथे push करायचे नाहीत.
       Export आता `research/elliott_vps_data.py --repo <trade-data> major-levels` मधून **private trade-data repo** मध्ये
       (major_levels_candles/); --eval ला `--candles <त्या checkout चा major_levels_candles>` द्या.
  2) --eval (कुठेही; network नाही): ground-truth window च्या शेवटापर्यंतच्या candles वर (no-lookahead) algo levels, लहान grid
     (lookback × k × min_react × prominence × price-mode = 72 संयोजनं), precision/recall/F1 (±0.15%), leave-one-chart-out, आणि
     चार charts चे overlay PNGs (algo वि. वापरकर्ता) → docs/reports/major_levels/

    python3 research/major_levels_eval.py --export
    python3 research/major_levels_eval.py --eval
"""
import argparse
import itertools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np            # noqa: E402
import pandas as pd           # noqa: E402

from price_action import major_levels as ML   # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "reports", "major_levels")
CANDLE_DIR = os.path.join(OUT_DIR, "candles")                                 # eval इथून वाचतो (VPS वरून data branch मार्गे आलेले)
EXPORT_DIR = os.path.join(ROOT, "data", "research", "major_levels_candles")   # VPS वर export इथे (gitignored — चालू checkout ला धक्का नाही)
GT_PATH = os.path.join(ROOT, "docs", "reports", "ground_truth_levels.csv")
TOL_PCT = 0.15
EXCHANGE = {"NIFTY": "NSE", "BANKNIFTY": "NSE", "SENSEX": "NSE"}
GRID = {"lookback_weeks": (2, 4, 8), "k_tol": (0.25, 0.5, 0.75), "min_react": (2, 3), "prom_s": (1.0, 2.0), "price_mode": ("median", "extreme")}


def load_gt(path=GT_PATH):
    gt = pd.read_csv(path)
    gt["window_start"] = pd.to_datetime(gt["window_start"])
    gt["window_end"] = pd.to_datetime(gt["window_end"])
    return gt


def charts(gt):
    out = []
    for (sym, tf), g in gt.groupby(["symbol", "tf"], sort=False):
        out.append({"symbol": sym, "tf": tf, "levels": g[g["type"] == "horizontal"]["price"].astype(float).tolist(),
                    "trend": g[g["type"].str.startswith("trendline")].to_dict("records"),
                    "start": g["window_start"].min(), "end": g["window_end"].max()})
    return out


def candle_path(sym, tf, d=CANDLE_DIR):
    return os.path.join(d, f"{sym}_{tf}.csv")


# ---------------------------------------------------------------------------------------------------------------------
# export (VPS)
# ---------------------------------------------------------------------------------------------------------------------
def export(gt, out_dir=EXPORT_DIR, token=None, fetch_index=None, fetch_mcx=None, resolve=None):
    if token is None:
        import cloud_db
        token = cloud_db.get_effective_upstox_token(None)
    if not token:
        print("❌ Upstox token नाही.")
        return 1
    if fetch_index is None:
        from upstox_api import fetch_candles as fetch_index
    if fetch_mcx is None:
        from upstox_api import fetch_mcx_candles as fetch_mcx
    if resolve is None:
        import resolve_mcx_futures_instruments as R
        resolve = R.resolve_symbol
    os.makedirs(out_dir, exist_ok=True)
    for c in charts(gt):
        sym, tf = c["symbol"], c["tf"]
        interval = {"15m": "15minute", "30m": "30minute"}[tf]
        jobs = []
        if sym in EXCHANGE:
            jobs.append(("", lambda: fetch_index(token, sym, None, interval=interval, lookback_days=70), sym))
        else:
            seen = set()
            for suffix, kw in (("", {}), ("__near", {"roll_days": 0})):      # bot चा contract, आणि सर्वात जवळचा न-expire contract
                try:
                    ok, r = resolve(token, sym, **kw)
                except TypeError:
                    ok, r = resolve(token, sym)
                if not ok:
                    print(f"❌ {sym}{suffix}: contract सापडला नाही ({r})")
                    continue
                if r["instrument_key"] in seen:
                    continue
                seen.add(r["instrument_key"])
                jobs.append((suffix, lambda r=r: fetch_mcx(token, r["instrument_key"], interval=interval, lookback_days=110),
                             r.get("trading_symbol", sym)))
        for suffix, fn, label in jobs:
            df = fn()
            if df is None or len(df) == 0:
                print(f"❌ {sym} {tf}{suffix}: candles मिळाले नाहीत")
                continue
            d = df[["timestamp", "open", "high", "low", "close"]].copy()
            d["contract"] = label
            d.to_csv(candle_path(sym + suffix, tf, out_dir), index=False)
            ts = pd.to_datetime(d["timestamp"])
            print(f"✅ {sym} {tf}{suffix} ({label}): {len(d)} candles, {ts.min():%d %b %H:%M} → {ts.max():%d %b %H:%M}")
    return 0


# ---------------------------------------------------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------------------------------------------------
def choose_contract(c, d=CANDLE_DIR):
    """MCX: bot चा contract आणि `__near` पैकी, ज्याच्या GT-window मधल्या किंमत-पट्ट्यात वापरकर्त्याचे सर्व levels बसतात तो (डेटा-निवड —
    params fitting नाही). दोन्ही/कोणीच नाही ⇒ bot चा. रिटर्न (df, contract label)."""
    opts = []
    for suffix in ("", "__near"):
        df = load_candles(c["symbol"] + suffix, c["tf"], d)
        if df is not None:
            opts.append(df)
    if not opts:
        return None, None
    def fits(df):
        w = df[(df["timestamp"] >= c["start"]) & (df["timestamp"] <= asof_of(c))]
        return len(w) and all(w["low"].min() * 0.995 <= v <= w["high"].max() * 1.005 for v in c["levels"])
    pick_df = next((o for o in opts if fits(o)), opts[0])
    label = str(pick_df["contract"].iloc[0]) if "contract" in pick_df.columns else c["symbol"]
    return pick_df, label


def load_candles(sym, tf, d=CANDLE_DIR):
    p = candle_path(sym, tf, d)
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    ts = pd.to_datetime(df["timestamp"], utc=False)
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    df["timestamp"] = ts
    return df.sort_values("timestamp").reset_index(drop=True)


def asof_of(c):
    return c["end"] + pd.Timedelta(hours=23, minutes=59)                          # ground-truth window च्या शेवटच्या दिवसाचा शेवट


def trend_match(lines, gt_trend, days=1.5):
    """GT trendline (anchor तारखा) शी जुळणारी algo रेषा: त्याच प्रकारची, आणि ≥ 2 GT anchors प्रत्येकी algo anchor पासून ±days मध्ये."""
    if not gt_trend:
        return None
    out = []
    for t in gt_trend:
        want = "desc_resistance" if "desc" in t["type"] else "asc_support"
        anchors = [pd.Timestamp(x) for x in str(t.get("anchor_dates") or "").split(";") if x]
        best = 0
        for ln in lines:
            if ln["type"] != want:
                continue
            hit = sum(any(abs((pd.Timestamp(a).normalize() - g).days) <= days for a in ln["anchors"]) for g in anchors)
            best = max(best, hit)
        out.append({"type": want, "gt_anchors": len(anchors), "matched_anchors": best, "match": best >= 2})
    return out


def run_grid(chart_list, candles):
    keys = list(GRID)
    rows = []
    for vals in itertools.product(*(GRID[k] for k in keys)):
        cfg = ML.MLConfig(**dict(zip(keys, vals)))
        for c in chart_list:
            df = candles.get((c["symbol"], c["tf"]))
            if df is None:
                continue
            lv, lines, info = ML.major_levels(df, asof=asof_of(c), cfg=cfg, exchange=EXCHANGE.get(c["symbol"], "MCX"))
            p, r, f1 = ML.match_levels([x["price"] for x in lv], c["levels"], TOL_PCT)
            tm = trend_match(lines, c["trend"]) or []
            rows.append({**dict(zip(keys, vals)), "symbol": c["symbol"], "n_algo": len(lv), "precision": p, "recall": r, "f1": f1,
                         "trend_match": all(t["match"] for t in tm) if tm else None})
    return pd.DataFrame(rows)


def pick(grid_df, exclude=None):
    g = grid_df if exclude is None else grid_df[grid_df["symbol"] != exclude]
    keys = list(GRID)
    agg = g.groupby(keys, as_index=False).agg(f1=("f1", "mean"), recall=("recall", "mean"), precision=("precision", "mean"))
    agg = agg.sort_values(["f1", "recall", "lookback_weeks", "k_tol"], ascending=[False, False, True, True])   # बरोबरी ⇒ लहान lookback, लहान k
    return agg.iloc[0][keys].to_dict(), agg


def loco(grid_df):
    """leave-one-chart-out: 3 charts वर निवडलेले params चौथ्या chart वर — fitting चा प्रामाणिक अंदाज."""
    keys = list(GRID)
    out = []
    for sym in grid_df["symbol"].unique():
        best, _ = pick(grid_df, exclude=sym)
        m = np.ones(len(grid_df), bool)
        for k in keys:
            m &= (grid_df[k] == best[k]).to_numpy()
        r = grid_df[m & (grid_df["symbol"] == sym).to_numpy()].iloc[0]
        out.append({"held_out": sym, **{k: best[k] for k in keys}, "precision": round(r["precision"], 2), "recall": round(r["recall"], 2),
                    "f1": round(r["f1"], 2)})
    return pd.DataFrame(out)


def overlay_png(c, df, levels, lines, path):
    import plotly.graph_objects as go
    d = df[(df["timestamp"] >= c["start"]) & (df["timestamp"] <= asof_of(c))].reset_index(drop=True)
    if len(d) < 5:
        return False
    x = np.arange(len(d))
    fig = go.Figure(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                                   increasing_line_color="#26a69a", decreasing_line_color="#ef5350", showlegend=False))
    for v in c["levels"]:
        fig.add_hline(y=v, line=dict(color="#ffa726", width=2, dash="dash"),
                      annotation=dict(text=f"माझा {v:,.2f}", font=dict(color="#ffa726"), xanchor="left"), annotation_position="top left")
    for lv in levels:
        fig.add_hline(y=lv["price"], line=dict(color="#4fc3f7", width=2),
                      annotation=dict(text=f"algo {lv['price']:,.2f} ({lv['n_react']}R{' RR' if lv['role_reversal'] else ''})",
                                      font=dict(color="#4fc3f7"), xanchor="right"), annotation_position="bottom right")
    full_pos = {t: i for i, t in enumerate(pd.to_datetime(df["timestamp"]))}
    for ln in lines:                                                              # engine ने fit केलेली रेषाच (a_ts, a_price, प्रति chart-TF bar slope)
        a_full = full_pos.get(pd.Timestamp(ln["a_ts"]))
        if a_full is None:
            continue
        xs = [i for i in range(len(d)) if full_pos[d["timestamp"].iloc[i]] >= a_full]
        if len(xs) < 2:
            continue
        ys = [ln["a_price"] + ln["slope"] * (full_pos[d["timestamp"].iloc[i]] - a_full) for i in (xs[0], xs[-1])]
        fig.add_trace(go.Scatter(x=[xs[0], xs[-1]], y=ys, mode="lines", line=dict(color="#ce93d8", width=2),
                                 name=f"algo {ln['type']} ({ln['n_pivots']} pivots)"))
    step = max(1, len(d) // 10)
    fig.update_xaxes(tickvals=list(range(0, len(d), step)), ticktext=[d["timestamp"].iloc[k].strftime("%d %b %H:%M") for k in range(0, len(d), step)],
                     rangeslider_visible=False)
    fig.update_layout(template="plotly_dark", width=1400, height=760, margin=dict(l=10, r=90, t=50, b=30),
                      title=f"{c['symbol']} {c['tf']} — algo (निळा) वि. माझे levels (नारिंगी), {c['start']:%d %b} → {c['end']:%d %b}")
    try:
        with open(path, "wb") as f:
            f.write(fig.to_image(format="png", width=1400, height=760, scale=1))
        return True
    except Exception as e:                                                       # noqa: BLE001
        print(f"PNG {path} बनवता आला नाही: {e}")
        return False


def evaluate(candle_dir=CANDLE_DIR, out_dir=OUT_DIR, gt_path=GT_PATH, png=True):
    gt = load_gt(gt_path)
    chart_list = charts(gt)
    candles, contracts = {}, {}
    for c in chart_list:
        candles[(c["symbol"], c["tf"])], contracts[(c["symbol"], c["tf"])] = choose_contract(c, candle_dir)
    missing = [k for k, d in candles.items() if d is None]
    if missing:
        print(f"❌ candles नाहीत: {missing} — आधी VPS वर --export चालवा")
    chart_list = [c for c in chart_list if candles.get((c["symbol"], c["tf"])) is not None]
    if not chart_list:
        return None
    grid = run_grid(chart_list, candles)
    best, agg = pick(grid)
    lo = loco(grid) if len(chart_list) > 1 else pd.DataFrame()
    cfg = ML.MLConfig(**best)
    per_chart = []
    os.makedirs(out_dir, exist_ok=True)
    for c in chart_list:
        key = (c["symbol"], c["tf"])
        lv, lines, info = ML.major_levels(candles[key], asof=asof_of(c), cfg=cfg, exchange=EXCHANGE.get(c["symbol"], "MCX"))
        p, r, f1 = ML.match_levels([x["price"] for x in lv], c["levels"], TOL_PCT)
        tm = trend_match(lines, c["trend"])
        per_chart.append({"chart": f"{c['symbol']} {c['tf']}", "contract": contracts[key], "माझे": ", ".join(f"{v:,.2f}" for v in c["levels"]),
                          "algo": ", ".join(f"{x['price']:,.2f}" for x in lv), "precision": round(p, 2), "recall": round(r, 2), "f1": round(f1, 2),
                          "trendline": ("—" if not tm else ("जुळली" if all(t["match"] for t in tm) else
                                                            f"नाही ({max(t['matched_anchors'] for t in tm)}/{tm[0]['gt_anchors']} anchors)"))})
        if png:
            overlay_png(c, candles[key], lv, lines, os.path.join(out_dir, f"{c['symbol']}_{c['tf']}_overlay.png"))
    pc = pd.DataFrame(per_chart)
    grid.to_csv(os.path.join(out_dir, "agreement_grid.csv"), index=False)
    pc.to_csv(os.path.join(out_dir, "agreement_per_chart.csv"), index=False)
    if len(lo):
        lo.to_csv(os.path.join(out_dir, "agreement_loco.csv"), index=False)
    return {"best": best, "per_chart": pc, "loco": lo, "grid_top": agg.head(10)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", action="store_true")
    g.add_argument("--eval", action="store_true")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--candles", default=CANDLE_DIR)
    a = ap.parse_args(argv)
    if a.export:
        return export(load_gt())
    res = evaluate(candle_dir=a.candles, png=not a.no_png)
    if res is None:
        return 2
    print("सर्वोत्तम params (चारही charts वर सरासरी F1):", res["best"])
    print(res["per_chart"].to_string(index=False))
    if len(res["loco"]):
        print("\nleave-one-chart-out (प्रामाणिक अंदाज):")
        print(res["loco"][["held_out", "precision", "recall", "f1"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
