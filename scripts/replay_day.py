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

  VPS (Upstox, read-only):  python3 scripts/replay_day.py --date 2026-10-12 --symbol NIFTY --dry-run [--json out.json]
  local (sandbox, ≤ 9 Oct):  python3 scripts/replay_day.py --date 2026-10-09 --symbol NIFTY --source local --daily f1 f2 ... [--json out.json]
  synthetic:                 python3 scripts/replay_day.py --date 2026-10-12 --synthetic --dry-run --out-dir DIR
Read-only: engine_signal / vision store ला लिहीत नाही, Telegram नाही, order नाही (फक्त PNG / JSON out-dir / --json मध्ये).
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


def allowed(df, symbol):
    """NIFTY: data_policy (annotation) — sealed holdout चा एकही 15M / 5M / FUT row engine मध्ये येत नाही (Daily warm-up वेगळा: Q33).
    इतर symbols ⇒ तसाच. None / रिकामा ⇒ तसाच."""
    if df is None or not len(df):
        return df
    from decision3 import history as HI
    if not HI.is_nifty(symbol):
        return df
    from elliott import data_policy as DP
    d = df.copy()
    d["timestamp"] = _naive(d["timestamp"])
    return DP.filter_allowed(d, "annotation")


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
    idx5 = allowed(idx5, sym)
    if idx5 is not None and len(idx5):
        idx5["timestamp"] = _naive(idx5["timestamp"])
        last = pd.to_datetime(m15["timestamp"]).max().normalize() if len(m15) else pd.Timestamp.min
        new = idx5[idx5["timestamp"].dt.normalize() > last]
        new = new[new["timestamp"].dt.normalize() <= day]
        m15 = pd.concat([m15[["timestamp", "bar_end", "open", "high", "low", "close"]], bins_15m(new)], ignore_index=True)
        n5 = new[["timestamp", "open", "high", "low", "close"]].assign(bar_end=new["timestamp"] + pd.Timedelta(minutes=5))
        ltf = n5 if ltf is None else pd.concat([ltf[["timestamp", "bar_end", "open", "high", "low", "close"]], n5], ignore_index=True)
    m15 = m15[pd.to_datetime(m15["timestamp"]).dt.normalize() <= day].reset_index(drop=True)
    m15 = allowed(m15, sym)
    ltf = allowed(ltf, sym)
    PE.guard(m15)
    fpaths = [os.path.join(exp, f"oe_futures_5min_{sym}.parquet")] + sorted(glob.glob(os.path.join(TRADE_DATA, "futures*", f"oe_futures_5min_{sym}*.parquet")))
    fut = allowed(_read_any(fpaths), sym)
    if fut is not None and len(fut):
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


def engine_line_of(r):
    """engine_signal.opinion चाच मजकूर (setup row साठी) — store न वाचता / न लिहिता (read-only dry run)."""
    lv = r["level"]
    d = 1 if lv["role"] == "support" else -1
    return (f"engine ({pd.Timestamp(r['bar_end']):%H:%M}): setup {'↑' if d > 0 else '↓'} {'bull put' if d > 0 else 'bear call'} · "
            f"grade {r.get('conviction') or '—'} · area {lv['lo']:,.0f}–{lv['hi']:,.0f}")


def approval(V, r, symbol, out_dir):
    """Dry run (read-only): approval chart + संदेश (vision.worker.v1_caption — खऱ्या approval चाच मजकूर). Vision = "skipped: dry run",
    Telegram send = print; engine_signal / vision store / Telegram ला हात नाही. PNG फक्त out_dir (नसेल ⇒ temp dir) मध्ये."""
    import tempfile
    from bots_common import level_gate_bot as LGB
    from bots_common import level_reaction as LR
    from decision3 import charts as CH
    from vision import config as VC
    from vision import decide as VD
    from vision import worker as VW
    out_dir = out_dir or tempfile.mkdtemp(prefix="replay_day_")
    os.makedirs(out_dir, exist_ok=True)
    t = int(r["bar"])
    lv = r["level"]
    bull = lv["role"] == "support"
    rk = r["risk"]
    cm = r.get("commit") or {}
    lines = cm.get("confirm_lines") or []
    png = os.path.join(out_dir, f"approval_{symbol}_{r['ts'][:16].replace(' ', '_').replace(':', '')}.png")
    open(png, "wb").write(CH.m15_png(V, t, f"{symbol} 15M", r=r))
    gr ={"side": LR.BULL if bull else LR.BEAR, "area": (lv["lo"], lv["hi"]), "form": cm.get("form"), "grade": r.get("conviction"),
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
    orig = VW.engine_line
    VW.engine_line = lambda _row: engine_line_of(r)                      # store वाचत / लिहीत नाही
    try:
        cap = VW.v1_caption(row, res, d, deadline, buttons=True)
    finally:
        VW.engine_line = orig
    print(f"\n[DRY-RUN] Telegram send_photo(chat=approver, photo={png}, buttons=✅ / ✏️ / ❌ / 📝) — network नाही, पाठवलं नाही")
    print("-" * 100 + "\n" + cap + "\n" + "-" * 100)
    open(png[:-4] + "_message.txt", "w", encoding="utf-8").write(cap)
    return png, cap


def _feed(token, today):
    """Live engine चाच स्रोत (engine3_live.UpstoxFeed: history chunks + गायब दिवस भरणे + intraday). tests मध्ये fake feed."""
    import engine3_live as E3L
    return E3L.UpstoxFeed(token, today=today)


def front_month(df):
    """FUT rows: प्रत्येक दिवशी त्या दिवसाचा front-month contract (legs2.volume.near_month चाच नियम — expiry column किंवा contract नावाचे
    शेवटचे तीन शब्द; expiry ≥ दिवस असलेला सर्वात जवळचा). एकच / contract column नाही / expiry ओळखता नाही ⇒ तसाच (alphabetical निवड नाही)."""
    if df is None or not len(df) or "contract" not in df.columns or df["contract"].nunique() <= 1:
        return df
    from legs2 import volume as LVOL
    exp = LVOL.expiry_of(df)
    if exp.isna().all():
        return df
    day = pd.to_datetime(df["timestamp"]).dt.normalize()
    ok = (exp.notna() & (exp >= day)).to_numpy()
    near = exp[ok].groupby(day[ok]).transform("min")
    keep = pd.Series(False, index=df.index)
    keep[df.index[ok]] = (exp[ok] == near).to_numpy()
    return df[keep.to_numpy()]


def until_close(df, day):
    """No lookahead: दिवस `day` च्या close नंतरचा एकही row नाही (feed today = D+1 ⇒ intraday / D+1 चे rows इथे वगळले जातात).
    एका timestamp ला अनेक contracts (`_all` file) ⇒ त्या दिवसाचा front month (`front_month`), मग timestamp-निहाय एकच row."""
    if df is None or not len(df):
        return df
    df = df.copy()
    df["timestamp"] = _naive(df["timestamp"])
    df = front_month(df[df["timestamp"] < day + pd.Timedelta(hours=15, minutes=30)])
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def _front_on(token, symbol, day):
    """दिवस `day` ला front-month असलेला FUT (engine3_live.resolve_future, as of day). सापडला नाही ⇒ None. tests मध्ये fake."""
    import engine3_live as E3L
    try:
        return E3L.resolve_future(token, symbol, day)
    except E3L.EngineDataError:
        return None


def feed_contract_warning(fpath, day, fut, front):
    """Collector file मध्ये दिवस D नाही ⇒ feed चा contract वापरला: ⚠️ ओळ (contract नाव). D च्या front-month चा expiry ≤ D (expiry दिवस) किंवा
    वेगळा contract ⇒ "volume from a different contract than the day's front month — c0 volume unreliable"."""
    used = str(fut["contract"].iloc[-1]) if "contract" in fut.columns else "front-month (as of D+1)"
    exp = pd.to_datetime(fut["expiry"].iloc[-1]).date() if "expiry" in fut.columns else None
    line = f"⚠️ FUT 5M volume: {fpath} has no {day.date()} rows ⇒ Upstox feed contract {used}" + (f" (expiry {exp})" if exp else "")
    d0 = day.date()
    if front is None or str(front.get("trading_symbol")) != used or pd.Timestamp(front.get("expiry")).date() <= d0:
        name = front.get("trading_symbol") if front else "unknown"
        line += f" — volume from a different contract than the day's front month ({name}) — c0 volume unreliable"
    return line


def load_upstox(a, day):
    """VPS: live engine सारखाच स्रोत — `engine3_live.UpstoxFeed` (token .env / Supabase मधून, कधीच print नाही), today = D+1 ⇒ minute
    history D पर्यंत (D चा दिवस समाविष्ट; historical नसेल तर feed चा recent-day fill / intraday) आणि D च्या close नंतरचं काहीच नाही
    (`until_close`). 15M (`--m15-days`), 5M LTF (`--ltf-days`), Daily (`--daily-days`, Q33 warm-up). फक्त GET; order / store नाही.
    FUT volume = --futures / data/oe_futures_5min_<SYM>.parquet (collector) मध्ये दिवस D असेल तर ते, नाहीतर feed.futures (front-month
    as of D+1 — expiry दिवशी पुढचा contract असू शकतो, छापलेला contract पहा); दोन्ही नाही ⇒ NA (c0 volume NA ⇒ grade कमाल B)."""
    import datetime as _dt
    import cloud_db
    import engine3_live as E3L
    from bots_common import level_reaction as LR
    from decision3 import history as HI
    from elliott import data_policy as DP
    sym = a.symbol.upper()
    tok = cloud_db.get_effective_upstox_token(None)
    if not tok:
        raise SystemExit("❌ Upstox token नाही (.env / daily login) — replay नाही")
    d0 = day.date()
    try:
        feed = _feed(tok, d0 + _dt.timedelta(days=1))
    except E3L.EngineDataError as exc:
        raise SystemExit(f"❌ Upstox feed: {exc}")

    def get(interval, days):
        try:
            df = feed.index(sym, interval, days)
        except E3L.EngineDataError as exc:
            raise SystemExit(f"❌ {sym} {interval}: {exc}")
        df = until_close(df, day)
        if df is None or not len(df):
            raise SystemExit(f"❌ {sym} {interval}: Upstox candles मिळाले नाहीत")
        return df

    def session(df, minutes):
        end = df["timestamp"] + pd.Timedelta(minutes=minutes)
        tod = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
        eod = end.dt.hour * 60 + end.dt.minute
        keep = ((tod >= 9 * 60 + 15) & (eod <= 15 * 60 + 30) & (df["timestamp"].dt.normalize() <= day)).to_numpy()
        out = df[keep].assign(bar_end=end[keep]).reset_index(drop=True)
        return out[["timestamp", "bar_end", "open", "high", "low", "close"]]
    m15 = session(get("15minute", a.m15_days), 15)
    ltf = session(get("5minute", a.ltf_days), 5)
    if HI.is_nifty(sym):                                                 # NIFTY: holdout row 15M / 5M input मध्ये नाही
        m15 = DP.filter_allowed(m15, "annotation").reset_index(drop=True)
        ltf = DP.filter_allowed(ltf, "annotation").reset_index(drop=True)
    dd = get("day", a.daily_days)
    daily = LR.prepare_daily(dd[["timestamp", "open", "high", "low", "close"]], day + pd.Timedelta(days=1))   # Q33 warm-up फक्त
    daily = daily[["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)
    daily["bar_end"] = pd.to_datetime(daily["timestamp"]).dt.normalize() + pd.Timedelta(hours=15, minutes=30)
    fpath = a.futures or os.path.join(ROOT, "data", f"oe_futures_5min_{sym}.parquet")
    fut = until_close(allowed(_read_any([fpath]), sym), day)
    if fut is not None and len(fut) and (fut["timestamp"].dt.normalize() == day).any():
        fut = fut.drop_duplicates(["timestamp"] + (["contract"] if "contract" in fut.columns else []), keep="first")
    else:
        try:
            fut = until_close(allowed(feed.futures(sym, "5minute", a.ltf_days), sym), day)
        except E3L.EngineDataError as exc:
            fut = None
            print(f"⚠️ FUT 5M volume: {fpath} मध्ये {day.date()} नाही, feed: {exc} ⇒ volume NA (c0 grade कमाल B)")
        else:
            if fut is not None and len(fut):
                print(feed_contract_warning(fpath, day, fut, _front_on(tok, sym, d0)))
            else:
                print(f"⚠️ FUT 5M volume नाही ({fpath} / feed) ⇒ volume NA (c0 grade कमाल B)")
                fut = None
    return m15, None, ltf, fut, daily


def _hm_window(w):
    if not w or w == "all":
        return "00:00", "23:59"
    lo, hi = w.split("-")
    return lo.strip(), hi.strip()


def brief(r):
    rk = r.get("risk") or {}
    lv = r.get("level") or {}
    return {"ts": r["ts"], "bar_end": r["bar_end"], "decision": r["decision"], "mark": r.get("mark"),
            "side": side_of(r) if r["decision"] == "setup" else None, "conviction": r.get("conviction"), "trend": r.get("trend_used"),
            "mature": r.get("mature"), "mature_step_down": r.get("mature_step_down"),
            "level": {k: lv.get(k) for k in ("id", "role", "lo", "hi", "births", "sweeps")} if lv else None,
            "entry": rk.get("entry"), "sl": rk.get("sl"), "target": rk.get("target"), "rr": rk.get("rr"), "why": r.get("why"),
            "checklist": r["checklist"], "confirm_lines": (r.get("commit") or {}).get("confirm_lines"), "level_evals": r.get("level_evals")}


def main(argv=None):
    import instruments as INS
    prev = INS._current["name"]
    try:
        return _main(argv)
    finally:
        INS._current["name"] = prev                                      # process-wide instrument tests / callers ला गळू नये


def _main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--day", "--date", dest="day", required=True)
    ap.add_argument("--source", choices=("auto", "local", "upstox", "synthetic"), default="auto",
                    help="auto: local data मध्ये तो दिवस असेल तर local, नाहीतर Upstox (VPS, token .env)")
    ap.add_argument("--data", nargs="*", help="local 1m csv(.gz) files (default <trade-data>/upstox/<SYM>_1m_*.csv.gz)")
    ap.add_argument("--export-dir", help="local collector export (default <trade-data>/live_export/<DAY>)")
    ap.add_argument("--daily", nargs="*", help="local Daily warm-up files, जुने आधी (Q33)")
    ap.add_argument("--futures", help="Upstox source: FUT 5M parquet (default data/oe_futures_5min_<SYM>.parquet)")
    ap.add_argument("--m15-days", type=int, default=90)
    ap.add_argument("--ltf-days", type=int, default=10)
    ap.add_argument("--daily-days", type=int, default=3650)
    ap.add_argument("--synthetic", action="store_true", help="= --source synthetic (tests/oct12_fixture, खरा data नाही)")
    ap.add_argument("--window", default="09:15-11:15", help="छापायचे bars (bar सुरुवात HH:MM-HH:MM) किंवा all")
    ap.add_argument("--dry-run-telegram", "--dry-run", dest="dry_run", action="store_true")
    ap.add_argument("--json", help="per-bar निर्णय + setup + approval संदेश JSON file")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args(argv)
    import instruments as INS
    from decision3 import engine as E3
    from decision3 import history as HI
    from elliott import data_policy as DP
    day = pd.Timestamp(a.day).normalize()
    if HI.is_nifty(a.symbol) and DP.period(day) == "HOLDOUT":
        print("❌ sealed holdout दिवस — replay नाही")
        return 2
    try:
        INS.set_current(a.symbol)                                        # PE.guard चा holdout नियम त्याच instrument चा
    except Exception:                                                    # noqa: BLE001
        pass
    src = "synthetic" if a.synthetic else a.source
    if src == "synthetic":
        m15, m1, ltf, fut, daily = load_synthetic(day)
    elif src == "upstox":
        m15, m1, ltf, fut, daily = load_upstox(a, day)
    else:
        m15, m1, ltf, fut, daily = load_real(a, day)
        if src == "auto" and not (pd.to_datetime(m15["timestamp"]).dt.normalize() == day).any():
            print(f"local data मध्ये {day.date()} नाही ⇒ Upstox (VPS)")
            src = "upstox"
            m15, m1, ltf, fut, daily = load_upstox(a, day)
        elif src == "auto":
            src = "local"
    ts = pd.to_datetime(m15["timestamp"])
    lo, hi = _hm_window(a.window)
    bars = [i for i in range(len(ts)) if ts.iloc[i].normalize() == day and lo <= ts.iloc[i].strftime("%H:%M") <= hi]
    if not bars:
        print(f"❌ {a.symbol} {day.date()}: त्या दिवसाचे 15M bars नाहीत — `--source upstox` (VPS) किंवा `--synthetic`")
        return 2
    V = E3.V22(m15, m1, daily, s=ENGINE_S, sealed=HI.sealed_fn(a.symbol) if src != "synthetic" else None, ltf=ltf, futures=fut)
    vol = V.levels.A.get("volume")
    nv = int(np.isfinite(vol[bars]).sum()) if vol is not None else 0
    print(f"{a.symbol} {day.date()} source={src}{' (SYNTHETIC FIXTURE, खरा data नाही)' if src == 'synthetic' else ''} · bars {lo}–{hi}: "
          f"{len(bars)} · FUT volume on {nv}/{len(bars)} bars · LTF 5M {'yes' if V.ltf is not None else 'MISSING'} · "
          f"c0 dominant ×{V.s['commit_dom_mult']} · c1 LTF CHoCH {'required' if V.s.get('ltf_choch', True) else 'off'} · "
          f"level_death_side {V.s.get('level_death_side', '—')}")
    rows = V.run(bars)
    for r in rows:
        print(bar_line(r))
    st = [r for r in rows if r["decision"] == "setup"]
    out = {"symbol": a.symbol, "day": str(day.date()), "source": src, "bars": [brief(r) for r in rows], "setup": None, "approval": None}
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
        with open(os.path.join(a.out_dir, f"replay_{a.symbol}_{day.date()}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    rc = 1
    if not st:
        print("\nsetup नाही.")
    else:
        rc = 0
        r = st[0]
        rk = r["risk"]
        out["setup"] = brief(r)
        print(f"\nFIRST SETUP {r['ts'][:16]} (bar close {r['bar_end'][11:16]}) · {side_of(r)} · {r.get('mark')} {r.get('conviction')} · "
              f"entry {rk['entry']:,.2f} · SL {rk['sl']:,.2f} · target {rk['target']:,.2f} · R:R {rk['rr']}")
        print("reasons:", " | ".join(f"{k} {v[1]}" for k, v in r["checklist"].items() if v[0] is not None))
        for x in (r.get("commit") or {}).get("confirm_lines") or []:
            print("  ", x)
        if a.dry_run:
            png, cap = approval(V, r, a.symbol, a.out_dir)
            out["approval"] = {"chart": png, "message": cap}
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        print(f"json: {a.json}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
