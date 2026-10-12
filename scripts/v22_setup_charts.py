"""scripts/v22_setup_charts.py — V22 setups: engine run (pickle) आणि प्रत्येक setup ची review chart + caption + manifest (Reader gallery /
Telegram review साठी). Chart: decision3/setup_chart.py (Daily + 15M + 5M, प्रत्येकाखाली volume pane). फक्त वाचन — order / broker नाही.
Upstox call नाही: सगळा डेटा दिलेल्या फाइलींतून. NIFTY holdout (sealed) rows कधीच load / दाखवत नाही.

    # 1) V22 run ⇒ pickle (setups + m15 + daily states)
    python3 scripts/v22_setup_charts.py run --symbol NIFTY --m1 data/nifty50_1min.parquet --out setups_rows.pkl [--from 2026-09-01]
    # 2) charts
    python3 scripts/v22_setup_charts.py render setups_rows.pkl OUT_DIR --symbol NIFTY \
        [--futures trade-data/futures_volume/oe_futures_5min_NIFTY.parquet] [--bhavcopy trade-data/nse_fo_bhavcopy/NIFTY ...] \
        [--m1 data/nifty50_1min.parquet] [--old v22n_old.json] [--only "2019-09-25 10:45,..."] [--run-id ID --title T --header H]

Volume: index ⇒ futures (--futures: collector चे 5M candles; अनेक contracts ⇒ chart_reader.volume.continuous roll) आणि Daily साठी NSE F&O
bhavcopy चा near-month FUT volume (--bhavcopy); MCX ⇒ contract चा स्वतःचा (--futures मध्ये तोच). नाही ⇒ "volume: NA (grade cap B)".
"""
import argparse
import collections
import glob
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision3 import setup_chart as SC  # noqa: E402
from decision3 import volume_pane as VP  # noqa: E402
from elliott import data_policy as DP  # noqa: E402

KEEP = ("ts", "bar_end", "decision", "daily_trend", "trend_used", "weekly_trend", "daily_phase", "corr_label", "mature",
        "maturity_targets", "trend_notes", "trend_cap", "trade_side", "protected", "checklist", "risk", "level", "K", "conviction",
        "conv_score", "missing", "evidence", "commit", "trendline", "why")


def _read(path):
    if str(path).endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _no_holdout(df, symbol, col="timestamp"):
    if str(symbol).upper() != "NIFTY" or df is None or not len(df):
        return df
    ts = pd.to_datetime(df[col])
    return df[[DP.period(t) != "HOLDOUT" for t in ts.dt.normalize()]].reset_index(drop=True)


def load_m1(paths, symbol, days=None):
    """1m bars (timestamp naive IST). days ⇒ फक्त त्या दिवसांच्या ±7 दिवसांचे rows (मोठी फाईल)."""
    if not paths:
        return None
    fr = []
    for p in paths:
        x = _read(p)
        x["timestamp"] = pd.to_datetime(x["timestamp"])
        if getattr(x["timestamp"].dt, "tz", None) is not None:
            x["timestamp"] = x["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        if days:
            keep = pd.Series(False, index=x.index)
            for d in days:
                keep |= (x["timestamp"] >= d - pd.Timedelta(days=7)) & (x["timestamp"] < d + pd.Timedelta(days=1))
            x = x[keep]
        fr.append(x[["timestamp", "open", "high", "low", "close"]])
    m1 = pd.concat(fr, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return _no_holdout(m1, symbol)


def load_futures(paths, symbol):
    """Collector चे 5M futures (timestamp, volume[, contract]). अनेक contracts ⇒ causal continuous roll (chart_reader.volume)."""
    if not paths:
        return None
    f = pd.concat([_read(p) for p in paths], ignore_index=True)
    f["timestamp"] = pd.to_datetime(f["timestamp"])
    if getattr(f["timestamp"].dt, "tz", None) is not None:
        f["timestamp"] = f["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    if "contract" in f.columns and f["contract"].nunique() > 1:
        from chart_reader import volume as CV
        f = CV.continuous(f)
    f = f.drop_duplicates("timestamp").sort_values("timestamp")[["timestamp", "volume"]].reset_index(drop=True)
    return _no_holdout(f, symbol)


def load_bhavcopy_fut(dirs, symbol):
    """NSE F&O bhavcopy (elliott/bhavcopy.py normalize) ⇒ दिवसाचा near-month FUT volume (contracts): timestamp, volume."""
    if not dirs:
        return None
    files = sorted({p for d in dirs for p in glob.glob(os.path.join(d, "*.parquet"))})
    rows = []
    for p in files:
        x = pd.read_parquet(p)
        x = x[[c for c in ("date", "symbol", "instrument", "expiry", "volume", "lot_size") if c in x.columns]]
        x = x[(x["instrument"] == "FUT") & (x["symbol"].astype(str).str.upper() == str(symbol).upper())]
        if len(x):
            rows.append(x)
    if not rows:
        return None
    x = pd.concat(rows, ignore_index=True)
    x["date"], x["expiry"] = pd.to_datetime(x["date"]), pd.to_datetime(x["expiry"])
    x = x[x["expiry"] >= x["date"]]
    near = x[x["expiry"] == x.groupby("date")["expiry"].transform("min")]
    if "lot_size" not in near.columns:
        near = near.assign(lot_size=np.nan)
    out = near.groupby("date", as_index=False).agg(volume=("volume", "sum"), lot_size=("lot_size", "max"))
    out = out.rename(columns={"date": "timestamp"})                       # volume = contracts; lot_size (udiff) ⇒ quantity
    return _no_holdout(out, symbol)


# ------------------------------------------------------------------------------------------------ run (V22 ⇒ pickle)
def cmd_run(a):
    from decision3 import engine as E3
    from decision3 import history as HI
    from pivots import engine as PE
    t0 = time.time()
    m1 = load_m1(a.m1, a.symbol)
    assert not any(DP.period(t) == "HOLDOUT" for t in m1["timestamp"].dt.normalize().unique()) or a.symbol.upper() != "NIFTY"
    m15 = PE.bars_15m(m1)
    d = m1.set_index("timestamp").resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    if a.daily:
        dd = HI.load_daily(a.daily)[["timestamp", "open", "high", "low", "close"]]
        d = pd.concat([dd, d[d["timestamp"] > dd["timestamp"].max()]], ignore_index=True)
    d = d[d["timestamp"] <= pd.to_datetime(m15["timestamp"]).max().normalize()].reset_index(drop=True)
    d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    V = E3.V22(m15, m1, d, sealed=HI.sealed_fn(a.symbol))
    bars = None
    if a.from_:
        ts = pd.to_datetime(V.m15["timestamp"])
        bars = [i for i in range(len(ts)) if ts.iloc[i] >= pd.Timestamp(a.from_)]
    rows = V.run(bars) if bars is not None else V.run()
    setups = [r for r in rows if r["decision"] == "setup"]
    out = {"symbol": a.symbol.upper(), "setups": setups, "m15": V.m15, "daily_df": V.daily_df, "daily_states": V.daily, "n": len(rows),
           "decisions": collections.Counter(r["decision"] for r in rows)}
    with open(a.out, "wb") as fh:
        pickle.dump(out, fh)
    print(len(rows), dict(out["decisions"]), len(setups), round(time.time() - t0, 1))


# ------------------------------------------------------------------------------------------------ render
def prA_status(old):
    def f(r):
        ob = old.get(r["ts"])
        if ob is None:
            return "new after PR A", "NEW after PR A (not a setup before PR A)"
        return "also before PR A", f"ALSO before PR A (then: cap {ob[1] or 'none'}, conviction {ob[2]})"
    return f


def cmd_render(a):
    o = pickle.load(open(a.pkl, "rb"))
    sym = (a.symbol or o.get("symbol") or "NIFTY").upper()
    setups = o.get("setups") or [r for r in o.get("rows") or [] if r["decision"] == "setup"]
    n_all = len(setups)
    numbered = list(enumerate(setups, 1))
    if a.only:
        want = {pd.Timestamp(x.strip()) for x in a.only.split(",") if x.strip()}
        numbered = [(i, r) for i, r in numbered if pd.Timestamp(r["ts"]) in want]
    assert all(DP.period(r["ts"]) != "HOLDOUT" for _, r in numbered) or sym != "NIFTY"
    days = sorted({pd.Timestamp(r["ts"]).normalize() for _, r in numbered})
    info = json.load(open(a.info)) if a.info else {}
    D = SC.SetupData(sym, o["m15"].copy(), o["daily_df"].copy(), o["daily_states"], m1=load_m1(a.m1, sym, days),
                     fut=load_futures(a.futures, sym), daily_vol=load_bhavcopy_fut(a.bhavcopy, sym), info=info)
    status = prA_status({x[0]: x for x in json.load(open(a.old))["setups"]}) if a.old else (lambda r: SC.trend_first_status(D, r))
    os.makedirs(os.path.join(a.out, sym), exist_ok=True)
    items = []
    for i, r in numbered:
        ts = pd.Timestamp(r["ts"])
        rel = f"{sym}/setup_{ts:%Y%m%d_%H%M}.png"
        head = f"V22 setup #{i} of {n_all}" + (f" {a.header}" if a.header else "")
        res = SC.render(D, r, header=head, status=status(r), path=os.path.join(a.out, rel))
        reading, cap = SC.caption(D, r, res["st"], res["short"], res["longst"], head=head, vline=res["vline"], vst=res["vol"])
        jrel = rel.replace(".png", ".json")
        vs, ls = res["vol"], res["ltf_vol"]
        js = {"symbol": sym, **{k: r.get(k) for k in KEEP}, "status": res["short"], "caption": cap,
              "volume": {"line": res["vline"], "source": VP.source_label(sym), "window_bars_15m": [vs["arm"], vs["commit"]],
                         "commit_mult": vs["commit_mult"], "trend_mult": vs["trend_mult"], "counter_mult": vs["counter_mult"],
                         "computed": vs["computed"], "ltf_line": ls["line"] if ls else None}}
        with open(os.path.join(a.out, jrel), "w", encoding="utf-8") as fh:
            json.dump(js, fh, ensure_ascii=False, indent=1, default=str)
        items.append({"symbol": sym, "date": f"{ts:%Y-%m-%d %H:%M}", "item": f"{a.run_id}|{sym}|{ts:%Y-%m-%d %H:%M}", "reading": reading,
                      "caption": cap, "kind": "v22_setup", "files": [rel], "json": jrel, "n": len(items) + 1, "status": res["short"]})
        print(i, rel, res["short"], "|", res["vline"], "| LTF" if res["ltf"] else "")
    man = {"run_id": a.run_id, "title": a.title or f"v2.2 setups ({sym})", "unit": "setup", "items": items}
    if a.tag:
        man["tag"] = a.tag                                                 # "debug" ⇒ sample / debug run, Telegram ला कधीच नाही
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=1)
    return man


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--symbol", default="NIFTY")
    r.add_argument("--m1", nargs="+", required=True)
    r.add_argument("--daily", nargs="*", default=None, help="Daily files (decision3.history.load_daily); नाही ⇒ 1m वरून")
    r.add_argument("--from", dest="from_", default=None, help="या तारखेपासूनचे bars च evaluate (warm-up आधीचे)")
    r.add_argument("--out", required=True)
    g = sub.add_parser("render")
    g.add_argument("pkl")
    g.add_argument("out")
    g.add_argument("--symbol", default=None)
    g.add_argument("--futures", nargs="*", default=None)
    g.add_argument("--bhavcopy", nargs="*", default=None)
    g.add_argument("--m1", nargs="*", default=None)
    g.add_argument("--old", default=None, help="PR A आधीचे setups json ⇒ 'new / also before PR A' status")
    g.add_argument("--info", default=None, help="setup ts ⇒ confirmation (a2 / c0 / c1) dict json")
    g.add_argument("--only", default=None)
    g.add_argument("--run-id", default="v22_setups")
    g.add_argument("--title", default=None)
    g.add_argument("--header", default="")
    g.add_argument("--tag", default=None, help='manifest top-level tag (उदा. "debug": samples कधीच Telegram ला नाहीत)')
    a = ap.parse_args(argv)
    return cmd_run(a) if a.cmd == "run" else cmd_render(a)


if __name__ == "__main__":
    main()
