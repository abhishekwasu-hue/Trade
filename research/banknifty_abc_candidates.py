"""research/banknifty_abc_candidates.py — R0-4 (Abhi): BANKNIFTY golden-day उमेदवार — 15M pullback (a-b-c) daily trend दिशेने valid area
वर संपला. **Research only** (live मार्ग नाही, API / Upstox / order नाही); Abhi charts पाहून एक निवडतो.

decision3 V22 (तोच engine) BANKNIFTY 15M + Daily + 5M LTF + FUT 5M volume वर: ① trend, ② area, ③ K (pullback) पास आणि ⑥ commitment
candle (c0) असलेले bars ⇒ दिवसाला एक (setup आधी, मग grade, मग K चे पाय ≥ 2) ⇒ पहिले N. Chart = `decision3.charts.m15_png` (15M + FUT
volume pane, English). तारखा CLI ने (code मध्ये नाहीत). NIFTY holdout नियम BANKNIFTY ला लागू नाही (replay_day `allowed` सारखंच); उमेदवार
फक्त `--from` नंतरचे.

    python3 research/banknifty_abc_candidates.py --from 2026-07-01 --out-dir ../trade-data/review/banknifty_abc_candidates
"""
import argparse
import json
import os
import sys
import warnings

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TRADE_DATA = os.environ.get("TRADE_DATA_DIR") or os.path.join(os.path.dirname(ROOT), "trade-data")


def _read(p):
    x = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p)
    t = pd.to_datetime(x["timestamp"])
    x["timestamp"] = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None) if t.dt.tz is not None else t
    return x


def _cat(paths):
    fr = [_read(p) for p in paths if p and os.path.exists(p)]
    if not fr:
        return None
    return pd.concat(fr, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)


def load(a):
    m15 = _cat(a.m15)[["timestamp", "open", "high", "low", "close"]]
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    d = _cat(a.daily)[["timestamp", "open", "high", "low", "close"]]
    d["timestamp"] = d["timestamp"].dt.normalize()
    extra = m15[m15["timestamp"].dt.normalize() > d["timestamp"].max()]
    if len(extra):                                                         # Daily file नंतरचे दिवस 15M वरून
        g = extra.assign(_d=extra["timestamp"].dt.normalize()).groupby("_d").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index()
        d = pd.concat([d, g.rename(columns={"_d": "timestamp"})], ignore_index=True)
    d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    ltf = _cat(a.ltf)
    if ltf is not None:
        ltf = ltf[["timestamp", "open", "high", "low", "close"]].assign(bar_end=ltf["timestamp"] + pd.Timedelta(minutes=5))
    fut = _cat(a.futures)
    return m15, d, ltf, fut


def _legs(txt):
    try:
        return int(str(txt).rsplit("पाय", 1)[1].strip().split()[0])
    except (IndexError, ValueError):
        return 0


def candidates(V, start, n):
    """दिवसाला एक उमेदवार ⇒ (score क्रमाने) पहिले n. Score: setup > wait; grade A > B; K पाय ≥ 2."""
    best = {}
    for t in range(len(V.m15)):
        ts = pd.Timestamp(V.m15["timestamp"].iloc[t])
        if ts < start:
            continue
        r = V.decide(t)
        ck = r.get("checklist") or {}
        ok = {k: bool(v[0]) for k, v in ck.items() if isinstance(v, list)}
        c6 = str((ck.get("⑥") or [None, ""])[1])
        weak = c6.startswith(("commitment candle", "commitment on low volume"))   # form नाही / dominant नाही / कमी volume
        if not (ok.get("①") and ok.get("②") and ok.get("③")) or not c6.startswith("commitment ") or weak:
            continue
        legs = _legs((ck.get("③") or [None, ""])[1])
        score = (r["decision"] == "setup", "grade A" in c6, legs >= 2, "CHoCH" in c6)
        day = str(ts.date())
        if day not in best or score > best[day][0]:
            best[day] = (score, t, r, legs, c6)
    return sorted(best.values(), key=lambda x: x[0], reverse=True)[:n]


def main(argv=None):
    ap = argparse.ArgumentParser(description="BANKNIFTY a-b-c golden-day candidates (research)")
    ap.add_argument("--from", dest="start", required=True, help="उमेदवार या दिवसापासून (उदा. holdout नंतर)")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--m15", nargs="+", default=[os.path.join(TRADE_DATA, "banknifty", "BANKNIFTY_15M.csv.gz")])
    ap.add_argument("--daily", nargs="+", default=[os.path.join(TRADE_DATA, "banknifty", "BANKNIFTY_D.csv.gz")])
    ap.add_argument("--ltf", nargs="*", default=[], help="5M spot (LTF CHoCH)")
    ap.add_argument("--futures", nargs="*", default=[], help="FUT 5M parquet (volume)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--bars", type=int, default=90, help="chart वर 15M bars")
    a = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    from decision3 import charts as CH
    from decision3 import engine as E3
    m15, d, ltf, fut = load(a)
    V = E3.V22(m15, daily_df=d, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    os.makedirs(a.out_dir, exist_ok=True)
    from legs2 import volume as LV2
    vol = LV2.bar_volume(V.m15, fut) if fut is not None else None          # FUT volume pane (spot volume कधीच नाही)
    out = []
    for score, t, r, legs, c6 in candidates(V, pd.Timestamp(a.start), a.n):
        name = f"BANKNIFTY_{str(r['ts'])[:16].replace(' ', '_').replace(':', '')}.png"
        open(os.path.join(a.out_dir, name), "wb").write(CH.m15_png(V, t, "BANKNIFTY 15M - candidate pullback end (engine read)", bars=a.bars,
                                                                   r=r, vol=vol, symbol="BANKNIFTY"))
        lv = r.get("level") or {}
        out.append({"bar": str(r["ts"]), "decision": r["decision"], "trend": r.get("trend_used"), "area": [lv.get("lo"), lv.get("hi")],
                    "role": lv.get("role"), "k_legs": legs, "commitment": c6[:160], "chart": name,
                    "checklist": {k: v[1] for k, v in (r.get("checklist") or {}).items() if isinstance(v, list)}})
        print(f"{r['ts']} · {r['decision']} · trend {r.get('trend_used')} · {lv.get('role')} {lv.get('lo')}–{lv.get('hi')} · K legs {legs} · "
              f"{c6[:110]}")
    json.dump(out, open(os.path.join(a.out_dir, "candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
