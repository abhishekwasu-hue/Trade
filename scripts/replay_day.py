#!/usr/bin/env python3
"""🧭 एका दिवसाचा decision3 V22 replay (Abhi, 12-Oct reference case): दिवसाच्या प्रत्येक बंद 15M bar चा निर्णय + कारण; `--dry-run-telegram`
⇒ पहिल्या setup चा approval chart (PNG) + approval संदेशाचा नेमका मजकूर. Network नाही: Vision = "Vision skipped: dry run", Telegram send
= print. Order / broker / Upstox call नाही. Code मध्ये तारीख नाही (दिवस CLI ने). NIFTY holdout: Daily warm-up फक्त input (Q33), output नाही.

Data (real):
  • 1m spot (`--data`, default <trade-data>/upstox/<SYM>_1m_*.csv.gz) — data_policy (annotation) ने holdout वगळून;
  • collector export (`--export-dir`, default <trade-data>/live_export/<DAY>): oe_index_5min_<SYM>.parquet (1m नसलेल्या दिवसांचे 15M + 5M LTF),
    oe_futures_5min_<SYM>.parquet (FUT volume);
  • FUT 5M volume: export + <trade-data>/futures*/oe_futures_5min_<SYM>*.parquet (near-month, legs2.volume — 15M = 09:15-anchored बेरीज);
  • Daily warm-up (`--daily`, जुने आधी) + replay data चे दिवस.
`--synthetic`: tests/oct12_fixture (Abhi ने सांगितलेली रचना, खरा data नाही) — export अजून आला नसेल तेव्हा.

  python3 scripts/replay_day.py --symbol NIFTY --day 2026-10-12 [--daily f1 f2 ...] [--dry-run-telegram --out-dir DIR]
  python3 scripts/replay_day.py --symbol NIFTY --day 2026-10-12 --synthetic --dry-run-telegram --out-dir DIR
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TRADE_DATA = os.environ.get("TRADE_DATA_DIR") or next((p for p in (os.path.join(os.path.dirname(ROOT), "trade-data"),
                                                                   os.path.expanduser("~/trade-data")) if os.path.isdir(p)),
                                                        os.path.join(os.path.dirname(ROOT), "trade-data"))   # VPS: /root/trade-data
ENGINE_S = {"level_death_side": "role"}          # Abhi TL1 (claude/v22-touch-levels) — merge होईपर्यंत स्पष्ट; नसलेली key engine दुर्लक्षित करतो


def _naive(s):
    t = pd.to_datetime(s)
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return t.astype("datetime64[ns]")


def bins_15m(idx5):
    """5M spot ⇒ 15M (09:15-anchored; फक्त पूर्ण तीन 5M bins). timestamp = सुरुवात, bar_end."""
    if idx5 is None or not len(idx5):
        return pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close"])
    d = idx5.copy()
    d["timestamp"] = _naive(d["timestamp"])
    day = d["timestamp"].dt.normalize()
    open_ = day + pd.Timedelta(hours=9, minutes=15)
    k = (d["timestamp"] - open_) // pd.Timedelta(minutes=15)
    d["_b"] = open_ + k * pd.Timedelta(minutes=15)
    g = d.sort_values("timestamp").groupby("_b").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                     close=("close", "last"), n=("close", "size")).reset_index()
    g = g[g["n"] == 3].rename(columns={"_b": "timestamp"}).drop(columns="n")
    g["bar_end"] = g["timestamp"] + pd.Timedelta(minutes=15)
    return g[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


def _read_any(paths):
    fr = []
    for p in paths:
        if p and os.path.exists(p):
            fr.append(pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p))
    return pd.concat(fr, ignore_index=True) if fr else None


def load_real(a, day):
    """(m15, df1m, ltf5, fut5, daily) — 1m जिथे आहे तिथे 1m, पुढचे दिवस export च्या 5M index मधून."""
    import market_state.core as MC
    from decision3 import history as HI
    from pivots import engine as PE
    from scripts import swing_check as SC
    sym = a.symbol.upper()
    files = a.data or sorted(glob.glob(os.path.join(TRADE_DATA, "upstox", f"{sym}_1m_*.csv.gz")))
    m1 = SC.load_1m(files) if files else None
    m15 = PE.bars_15m(m1) if m1 is not None and len(m1) else pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close"])
    ltf = MC.frame(m1, "5m", pd.to_datetime(m1["timestamp"]).max() + pd.Timedelta(minutes=1)) if m1 is not None and len(m1) else None
    exp = a.export_dir or os.path.join(TRADE_DATA, "live_export", str(day.date()))
    idx5 = _read_any([os.path.join(exp, f"oe_index_5min_{sym}.parquet")])
    if idx5 is not None and len(idx5):
        idx5["timestamp"] = _naive(idx5["timestamp"])
        last = pd.to_datetime(m15["timestamp"]).max().normalize() if len(m15) else pd.Timestamp.min
        new = idx5[idx5["timestamp"].dt.normalize() > last]
        new = new[new["timestamp"].dt.normalize() <= day]
        m15 = pd.concat([m15[["timestamp", "bar_end", "open", "high", "low", "close"]], bins_15m(new)], ignore_index=True)
        n5 = new[["timestamp", "open", "high", "low", "close"]].assign(bar_end=new["timestamp"] + pd.Timedelta(minutes=5))
        ltf = n5 if ltf is None else pd.concat([ltf[["timestamp", "bar_end", "open", "high", "low", "close"]], n5], ignore_index=True)
    m15 = m15[pd.to_datetime(m15["timestamp"]).dt.normalize() <= day].reset_index(drop=True)
    PE.guard(m15)
    fpaths = [os.path.join(exp, f"oe_futures_5min_{sym}.parquet")] + sorted(glob.glob(os.path.join(TRADE_DATA, "futures*", f"oe_futures_5min_{sym}*.parquet")))
    fut = _read_any(fpaths)
    if fut is not None:
        fut["timestamp"] = _naive(fut["timestamp"])
        fut = fut.drop_duplicates(["timestamp"] + (["contract"] if "contract" in fut.columns else []), keep="first")
    daily = None
    if a.daily:
        daily = HI.load_daily(a.daily)[["timestamp", "open", "high", "low", "close"]]
    d15 = m15.assign(_d=pd.to_datetime(m15["timestamp"]).dt.normalize()).groupby("_d").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index().rename(columns={"_d": "timestamp"})
    if daily is not None:
        d15 = d15[d15["timestamp"] > daily["timestamp"].max()]
    daily = pd.concat([x for x in (daily, d15) if x is not None], ignore_index=True)
    daily = daily[daily["timestamp"] <= day].reset_index(drop=True)
    daily["bar_end"] = daily["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    return m15.reset_index(drop=True), m1, ltf, fut, daily


def load_synthetic(day):
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(end_day=str(day.date()))
    return m15, None, ltf, fut, None


def side_of(r):
    lv = r.get("level") or {}
    return "bull put" if lv.get("role") == "support" else ("bear call" if lv else "—")


def bar_line(r):
    c = r["checklist"]
    hm = r["ts"][11:16]
    lv = r.get("level") or {}
    lvl = f"{lv.get('role', '')[:3]} {lv['lo']:,.0f}–{lv['hi']:,.0f} {'+'.join(lv.get('births', []))}" if lv else "—"
    rk = r.get("risk") or {}
    rr = f"R:R {rk.get('rr')}" if rk.get("rr") is not None else ""
    head = f"{hm} {r['decision']:<8} {r.get('mark') or '  '} {side_of(r) if r['decision'] == 'setup' else '':<9} {r.get('conviction') or '':<7}"
    why = r.get("why") or next((f"{k} {c[k][1]}" for k in ("①", "②", "③", "⑥", "⑦") if c[k][0] is False), "")
    return f"{head} | {lvl} | {str(why)[:150]} {rr}"


def approval(V, r, symbol, out_dir):
    """Dry run: approval chart + संदेश (vision.worker.v1_caption — खऱ्या approval चाच मजकूर), Vision / Telegram mock."""
    from bots_common import level_gate_bot as LGB
    from bots_common import level_reaction as LR
    from decision3 import charts as CH
    from vision import decide as VD
    from vision import worker as VW
    from vision import config as VC
    import engine_signal as ES
    os.makedirs(out_dir, exist_ok=True)
    os.environ["ENGINE_SIGNAL_DB"] = os.path.join(out_dir, "engine_signals_dryrun.db")    # repo चा data/ store नाही
    t = int(r["bar"])
    lv = r["level"]
    bull = lv["role"] == "support"
    rk = r["risk"]
    cm = r.get("commit") or {}
    lines = cm.get("confirm_lines") or []
    png = os.path.join(out_dir, f"approval_{symbol}_{r['ts'][:16].replace(' ', '_').replace(':', '')}.png")
    open(png, "wb").write(CH.m15_png(V, t, f"{symbol} 15M", r=r))
    ES.save({"symbol": symbol.upper(), "bar_ts": str(V.bar_end[t]), "computed_at": str(V.bar_end[t]), "decision": "setup", "gate": "v22",
             "direction": 1 if bull else -1, "level_lo": lv["lo"], "level_hi": lv["hi"], "entry": rk["entry"], "invalidation": rk["sl"],
             "target": rk["target"], "grade": r.get("conviction"), "reason": "", "payload": "{}"})
    gr = {"side": LR.BULL if bull else LR.BEAR, "area": (lv["lo"], lv["hi"]), "form": cm.get("form"), "grade": r.get("conviction"),
          "commit_grade": cm.get("grade"), "entry_price": rk["entry"], "sl": rk["sl"], "target": rk["target"], "rr": rk["rr"],
          "confirm_ts": str(V.bar_end[t]), "study": lines[0] if lines else None, "commit_line": " · ".join(lines[1:]) or None,
          "evidence": {k: v for k, v in (r.get("evidence") or {}).items() if v is not None}}
    tags = LGB.gate_tags(gr, {"reason": r["checklist"]["①"][1]}, 15)
    tags.update(engine=True, engine_bar=str(V.bar_end[t]), engine_grade=r.get("conviction"), dry_run=True)
    row = {"signal_id": "dry-run", "bot": "srv2_momentum_reversal", "bot_label": VC.BOTS["srv2_momentum_reversal"][0] + " · engine",
           "symbol": symbol.upper(), "direction": "BULLISH" if bull else "BEARISH", "level": (lv["lo"] + lv["hi"]) / 2,
           "role": "Support" if bull else "Resistance", "setup_tf": "15M", "signal_ts": str(V.bar_end[t]), "mode": "human_confirm",
           "setup_json": json.dumps({"tags": tags}, default=str)}
    res = {"verdict": "unavailable", "error": "Vision skipped: dry run"}
    d = VD.decide("human_confirm", "unavailable", VC.BOT_DEFAULTS)
    deadline = pd.Timestamp(V.bar_end[t]) + pd.Timedelta(minutes=int(VC.BOT_DEFAULTS["approve_window_min"]))
    cap = VW.v1_caption(row, res, d, deadline, buttons=True)
    print(f"\n[DRY-RUN] Telegram send_photo(chat=approver, photo={png}, buttons=✅ / ✏️ / ❌ / 📝) — network नाही")
    print("-" * 100 + "\n" + cap + "\n" + "-" * 100)
    open(png[:-4] + "_message.txt", "w", encoding="utf-8").write(cap)
    return png, cap


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--day", required=True)
    ap.add_argument("--data", nargs="*", help="1m csv(.gz) files (default <trade-data>/upstox/<SYM>_1m_*.csv.gz)")
    ap.add_argument("--export-dir", help="collector export (default <trade-data>/live_export/<DAY>)")
    ap.add_argument("--daily", nargs="*", help="Daily warm-up files, जुने आधी (Q33)")
    ap.add_argument("--synthetic", action="store_true", help="tests/oct12_fixture (खरा data नाही)")
    ap.add_argument("--dry-run-telegram", action="store_true")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args(argv)
    from decision3 import engine as E3
    from decision3 import history as HI
    from elliott import data_policy as DP
    day = pd.Timestamp(a.day).normalize()
    if HI.is_nifty(a.symbol) and DP.period(day) == "HOLDOUT":
        print("❌ sealed holdout दिवस — replay नाही")
        return 2
    m15, m1, ltf, fut, daily = load_synthetic(day) if a.synthetic else load_real(a, day)
    ts = pd.to_datetime(m15["timestamp"])
    bars = [i for i in range(len(ts)) if ts.iloc[i].normalize() == day]
    if not bars:
        print(f"❌ {a.symbol} {day.date()}: त्या दिवसाचे 15M bars नाहीत (export आला नाही?) — `--synthetic` वापरा किंवा export ची वाट")
        return 2
    V = E3.V22(m15, m1, daily, s=ENGINE_S, sealed=HI.sealed_fn(a.symbol) if not a.synthetic else None, ltf=ltf, futures=fut)
    vol = V.levels.A.get("volume")
    nv = int(np.isfinite(vol[bars]).sum()) if vol is not None else 0
    print(f"{a.symbol} {day.date()} {'SYNTHETIC FIXTURE (tests/oct12_fixture)' if a.synthetic else 'real data'} · 15M bars {len(bars)} · "
          f"FUT volume on {nv}/{len(bars)} bars · LTF 5M {'yes' if V.ltf is not None else 'MISSING'} · "
          f"c0 dominant ×{V.s['commit_dom_mult']} · c1 LTF CHoCH {'required' if V.s.get('ltf_choch', True) else 'off'}")
    rows = V.run(bars)
    for r in rows:
        print(bar_line(r))
    st = [r for r in rows if r["decision"] == "setup"]
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
        with open(os.path.join(a.out_dir, f"replay_{a.symbol}_{day.date()}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    if not st:
        print("\nsetup नाही.")
        return 1
    r = st[0]
    rk = r["risk"]
    print(f"\nFIRST SETUP {r['ts'][:16]} (bar close {r['bar_end'][11:16]}) · {side_of(r)} · {r.get('mark')} {r.get('conviction')} · "
          f"entry {rk['entry']:,.2f} · SL {rk['sl']:,.2f} · target {rk['target']:,.2f} · R:R {rk['rr']}")
    print("reasons:", " | ".join(f"{k} {v[1]}" for k, v in r["checklist"].items() if v[0] is not None))
    for x in (r.get("commit") or {}).get("confirm_lines") or []:
        print("  ", x)
    if a.dry_run_telegram:
        approval(V, r, a.symbol, a.out_dir or os.path.join(ROOT, "data", "replay_dryrun"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
