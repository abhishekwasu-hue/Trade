"""research/k10_days.py — थांबा-बिंदू K-10 (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §6): 10 random दिवस, सगळ्या layers सह charts.

IS (2015–2021) मधून 5 आणि Jul–Oct 2026 (contaminated, फक्त पडताळणी) मधून 5; holdout / VAL नाही. Seed नोंदवलेला. प्रकार वेगवेगळे
(stratified): gap-up, gap-down, trend ×2, range — प्रत्येक भागात. प्रकार daily candles वरून: gap = (open − आदला close) ÷ ATR14
(≥ 0.4 ⇒ gap), trend = |close − open| ÷ ATR14 ≥ 0.8, नाहीतर range.
प्रत्येक दिवस (Simple Core, Abhi 2026-10-08): प्रत्येक बंद 15M bar वर signal / कारण; 15M chart (trend label, areas, pause फिकट,
commitment ठळक, 🚩 ENTRY SIGNAL, ref_levels, shadow engine चा निर्णय एका ओळीत) + 1H context; --exec-profile ⇒ plan + simulate.
वेळ (core / shadow / render p50 / max). PNG / JSON फक्त --out-dir (trade-data / scratch); repo मध्ये फक्त अहवाल.

    python3 research/k10_days.py --is-data data/nifty50_1min.parquet \\
        --recent-data /root/trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz --out-dir /root/trade-data/review/k10/run2 \\
        --run-id k10/run2 --dates 2015-07-08,… --seed 20261009 \\
        --exec-json '{"rr_filter": true, "min_rr": 3, "sl_mode": "structural_invalidation", "target_mode": "next_opposite_area", …}'
Execution settings (--exec-profile dashboard profile किंवा --exec-json) ⇒ प्रत्येक signal वर spot plan (SL / target / R:R / rr_filter) +
simulate — code कुठलाही default भरत नाही. Out-dir मध्ये review manifest.json (Telegram: scripts/send_review_to_telegram.py) — प्रत्येक
दिवस: 1H + 15M (+ signal असेल तर trade chart) आणि एका ओळीत वाचन (trend / area / pause-commitment / signal किंवा कारण).
"""
import argparse
import json
import os
import random
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research"))

from elliott import data_policy as DP            # noqa: E402
from opportunity_engine import cas as CAS        # noqa: E402

PARTS = {"IS": ("2015-02-01", "2021-12-31"), "2026": ("2026-07-01", "2026-10-08")}
QUOTA = {"gap_up": 1, "gap_down": 1, "trend": 2, "range": 1}
SEED = 20261008


def read(path):
    return pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])


def day_types(m1):
    """daily candles ⇒ प्रत्येक दिवसाचा प्रकार (gap_up / gap_down / trend / range)."""
    d = CAS.daily_levels(m1)[["open", "high", "low", "close"]].dropna()
    pc = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().shift(1)
    gap = (d["open"] - pc) / atr
    body = (d["close"] - d["open"]).abs() / atr
    t = np.where(gap >= 0.4, "gap_up", np.where(gap <= -0.4, "gap_down", np.where(body >= 0.8, "trend", "range")))
    return pd.DataFrame({"type": t, "gap_atr": gap.round(2), "body_atr": body.round(2)}, index=d.index).dropna()


def pick(types, start, end, rng):
    t = types[(types.index >= pd.Timestamp(start)) & (types.index <= pd.Timestamp(end))]
    ok = [d for d in t.index if DP.allowed(d, "golden")]
    t = t.loc[ok]
    out = []
    for k, n in QUOTA.items():
        pool = sorted(t.index[t["type"] == k])
        out += [(d, k) for d in rng.sample(pool, min(n, len(pool)))]
    return sorted(out)


def _png(fig, path):
    fig.write_image(path, format="png", scale=1)
    return os.path.basename(path)


def run_day(raw, day, out_dir, exec_ex=None, render=True, alts=None, engine_s=None):
    """एक दिवस: प्रत्येक बंद 15M bar वर simple_core.signal_at (trendline memory + एक setup = एक entry); signal वर shadow engine
    (chart_reader.evaluate) चा निर्णय एक ओळ; execution profile असेल तर plan + simulate. Charts: दिवस 15M (core) + 1H context."""
    import time
    import market_state as MS
    from backtest_review import charts as BC
    from chart_reader import evaluate as EV
    from chart_reader import setups as SU
    from simple_core import engine as EN
    from simple_core import execution as EX
    os.makedirs(out_dir, exist_ok=True)
    m1 = raw[(raw["timestamp"] >= day - pd.Timedelta(days=130)) & (raw["timestamp"] < day + pd.Timedelta(days=5))].reset_index(drop=True)
    mem, tr = SU.LineMemory(), EN.Tracker()
    bars, timing = [], {"core_s": [], "shadow_s": [], "render_s": []}
    for t in pd.date_range(day + pd.Timedelta(hours=9, minutes=15), day + pd.Timedelta(hours=15, minutes=15), freq="15min"):
        asof = t + pd.Timedelta(minutes=15)
        t0 = time.monotonic()
        r = EN.signal_at(m1, asof, s=engine_s, memory=mem, tracker=tr)
        timing["core_s"].append(round(time.monotonic() - t0, 2))
        b = {"bar_start": str(t), "signal": r.get("signal"), "why": r.get("why"), "pause_bars": r.get("pause_bars", 0)}
        if r["signal"]:
            t0 = time.monotonic()
            sh = EV.evaluate(m1, "srv2", asof, run_elliott=False)
            timing["shadow_s"].append(round(time.monotonic() - t0, 2))
            b["shadow"] = (f"{'entry' if sh['entry'] else 'no entry'} · grade {sh['grade']} ({sh.get('total')})"
                           + ("" if sh["entry"] else f" · {(sh['why_no_entry'] or ['—'])[0][:60]}"))
            if alts:                                                       # sensitivity: तोच signal, दुसरे settings
                full_a = EV.frame(m1, "15m", day + pd.Timedelta(days=5))
                after_a = full_a[pd.to_datetime(full_a["timestamp"]) > pd.Timestamp(t)]
                b["alts"] = {}
                for nm, ax in alts.items():
                    pa = EX.plan(r["signal"], ax, r["mr"], spot_only=True)
                    b["alts"][nm] = {"plan": pa, "sim": EX.simulate(pa, after_a)}
            if exec_ex is not None:
                pl = EX.plan(r["signal"], exec_ex, r["mr"], spot_only=True)
                after = r["trig"].iloc[0:0]
                full = EV.frame(m1, "15m", day + pd.Timedelta(days=5))
                after = full[pd.to_datetime(full["timestamp"]) > pd.Timestamp(t)]
                b["plan"], b["sim"] = pl, EX.simulate(pl, after)
        b["zones"] = [{k: z.get(k) for k in ("id", "zid", "tool", "type", "side", "role", "label", "low", "high", "slope", "anchors", "pair",
                                             "state")} for z in r.get("zones") or [] if z.get("state") not in ("DEAD", "MAGNET")]
        bars.append(b)
    sigs = [b for b in bars if b["signal"]]
    rec = {"date": f"{day:%Y-%m-%d}", "signals": [{"time": b["bar_start"][11:16], **{k: b["signal"].get(k) for k in
                                                   ("side", "trigger_price", "area", "pause_bars", "pause_from", "ref_levels", "context_story",
                                                    "setup", "ref_notes")},
                                                   "shadow": b.get("shadow"), "plan": b.get("plan"), "sim": b.get("sim"), "alts": b.get("alts")} for b in sigs],
           "why_by_bar": [(b["bar_start"][11:16], b["why"]) for b in bars], "pngs": {}, "tl_log": mem.log}
    if render:
        t0 = time.monotonic()
        frames = MS.full_frames(m1)
        m15 = frames["15m"]
        m15_ts = pd.to_datetime(m15["timestamp"]).to_numpy(dtype="datetime64[ns]")
        day_end = day + pd.Timedelta(hours=15, minutes=30)
        ms_close = MS.read(m1, day_end, run_elliott=False, frames=frames)
        tr = ms_close["trend"]
        rec["trend"] = ("testing" if tr.get("state") == "testing" else {1: "up", -1: "down"}.get(int(tr.get("dir") or 0), "range"))
        for s_ in rec["signals"]:
            rec["pngs"].setdefault("trade", trade_chart(m15[m15["bar_end"] <= day_end + pd.Timedelta(days=5)], day, s_,
                                                        os.path.join(out_dir, "trade.png")))
        cut = m1[(m1["timestamp"] >= day - pd.Timedelta(days=20)) & (m1["timestamp"] < day + pd.Timedelta(days=1))]
        rec["pngs"]["day_15m"] = _png(BC.core_day_15m(m15[m15["bar_end"] <= day_end], day, bars, f"{day:%Y-%m-%d} · 15M · Simple Core",
                                                      m15_ts=m15_ts, cut=cut, ms_close=ms_close), os.path.join(out_dir, "day_15m.png"))
        last = next((b for b in reversed(bars) if b.get("zones")), {})
        c = {"bar_end": day_end, "trend": ms_close["trend"], "impulse": ms_close["impulse"],
             "labels": (ms_close.get("correction") or {}).get("labels"), "zones": last.get("zones")}
        rec["pngs"]["day_1h"] = _png(BC.context_1h(frames["1h"], c, f"{day:%Y-%m-%d} · 1H context", m15_ts=m15_ts),
                                     os.path.join(out_dir, "day_1h.png"))
        from backtest_review import daily as DL                           # 1D = आजोबा degree (नकाशा P1), दिवसाच्या close पर्यंतच
        f1d = DL.facts(m1[m1["timestamp"] < day_end], day_end)
        rec["daily"] = {"line": f1d["line"], "struct": f1d["struct"], "count_gray": bool(f1d["count"].get("gray"))}
        rec["pngs"]["day_1d"] = _png(BC.daily_1d(f1d, f"{day:%Y-%m-%d} · 1D · आजोबा degree"), os.path.join(out_dir, "day_1d.png"))
        timing["render_s"].append(round(time.monotonic() - t0, 2))
    rec["timing"] = {k: {"n": len(v), "p50": float(np.median(v)) if v else None, "max": max(v) if v else None} for k, v in timing.items()}
    json.dump(rec, open(os.path.join(out_dir, "day.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return rec


def exec_from_args(profile=None, exec_json=None):
    """--exec-profile (dashboard store) किंवा --exec-json ⇒ settings dict (validate; default नाही). दोन्ही नाहीत ⇒ None."""
    from simple_core import settings as SS
    if exec_json:
        return SS.validate(json.loads(exec_json))
    return SS.load_profile(profile) if profile else None


def _px(v):
    return "—" if v is None else f"{float(v):,.1f}"


def reading(rec):
    """दिवसाचं एका ओळीत वाचन: trend · signal (area, pause, setup, plan / sim) किंवा मुख्य कारण."""
    head = f"Trend: {rec.get('trend') or '—'}"
    if rec.get("signals"):
        parts = []
        for s in rec["signals"]:
            a = s["area"]
            x = (f"🚩 {s['time']} {'bear' if s['side'] < 0 else 'bull'} {s['trigger_price']:,.1f} · area {a['id']} ({a['type']}) "
                 f"{a['low']:,.1f}–{a['high']:,.1f} · pause {s['pause_bars']} + commitment" + (f" · {s['setup']}" if s.get("setup") else ""))
            pl, sm = s.get("plan"), s.get("sim") or {}
            if pl:
                x += (f" · SL {_px(pl.get('sl'))} T {_px(pl.get('target'))} R:R {pl.get('rr')} ⇒ {sm.get('result')}" if pl.get("ok")
                      else f" · trade नाही: {pl.get('reason')}")
            for nm, al in (s.get("alts") or {}).items():
                ap_, as_ = al.get("plan") or {}, al.get("sim") or {}
                x += f" · [{nm}: " + (f"R:R {ap_.get('rr')} ⇒ {as_.get('result')}" if ap_.get("ok") else f"नाही — {ap_.get('reason')}") + "]"
            parts.append(x)
        return head + " · " + " | ".join(parts)
    whys = pd.Series([w for _, w in rec.get("why_by_bar") or []])
    if not len(whys):
        return head + " · Signal नाही"
    top = whys.value_counts()
    return head + f" · Signal नाही: {top.index[0]} ({int(top.iloc[0])} bars)" + (f"; {top.index[1]} ({int(top.iloc[1])})" if len(top) > 1 else "")


def trade_chart(m15, day, s, path):
    """Signal दिवस + पुढचं session (hindsight): area, ENTRY, चालू SL / target (BC.sl_target)."""
    import plotly.graph_objects as go
    days = sorted(pd.to_datetime(m15["timestamp"]).dt.normalize().unique())
    i = days.index(pd.Timestamp(day))
    f = m15[pd.to_datetime(m15["timestamp"]).dt.normalize().isin(days[max(0, i - 1): i + 2])].reset_index(drop=True)
    x = [t.strftime("%d %b %H:%M") for t in pd.to_datetime(f["timestamp"])]
    fig = go.Figure(go.Candlestick(x=x, open=f["open"], high=f["high"], low=f["low"], close=f["close"], increasing_line_color="#26a69a",
                                   decreasing_line_color="#ef5350"))
    xs = (pd.Timestamp(day) + pd.Timedelta(hours=int(s["time"][:2]), minutes=int(s["time"][3:]))).strftime("%d %b %H:%M")
    from backtest_review import charts as BC
    (sl, sl_lab), (tg, tg_lab) = BC.sl_target({"signal": s, "plan": s.get("plan")})   # फक्त चालू SL / target (Abhi 2026-10-09)
    lines = [(s["trigger_price"], "ENTRY", "#f5c518"), (sl, sl_lab, "#ef5350"), (tg, tg_lab, "#26a69a")]
    a = s["area"]
    rl = [{"y": (a["low"] + a["high"]) / 2.0, "text": f"area {a['id']} {a['low']:,.0f}–{a['high']:,.0f}",
           "color": "#ef9a9a" if s["side"] < 0 else "#80cbc4", "bold": True}]   # entry-area label ठळक
    for v, nm, col in lines:
        if v is not None:
            fig.add_shape(type="line", x0=xs, x1=x[-1], y0=v, y1=v, line=dict(color=col, width=1.5, dash="dash"))
            rl.append({"y": v, "text": f"{nm} {v:,.1f}", "color": col, "bold": False})
    ys = [float(v) for v in f["low"].tolist() + f["high"].tolist()] + [float(v) for v, _, _ in lines if v is not None]
    lo_, hi_ = min(ys), max(ys)
    BC.level_marks(fig, x[-1], rl, lo_, hi_, d=f)
    pad = 0.05 * ((hi_ - lo_) or 1.0)
    fig.update_yaxes(range=[lo_ - pad, hi_ + pad])
    fig.add_shape(type="rect", x0=x[0], x1=x[-1], y0=a["low"], y1=a["high"], line=dict(width=0),
                  fillcolor="rgba(239,83,80,0.15)" if s["side"] < 0 else "rgba(38,166,154,0.15)")
    fig.add_annotation(x=xs, y=s["trigger_price"], text=f"🚩 {s['time']}", showarrow=True, font=dict(color="#f5c518"))
    sm = s.get("sim") or {}
    fig.update_layout(title=f"{day:%Y-%m-%d} · trade (hindsight) · area {a['id']}" + (f" · {sm.get('result')}" if sm else ""),
                      template="plotly_dark", xaxis_rangeslider_visible=False, width=1400, height=800, showlegend=False,
                      xaxis=dict(type="category", nticks=12))
    return _png(fig, path)


def _cell(pl, sm):
    if not pl:
        return "—"
    if not pl.get("ok"):
        return f"trade नाही: {pl.get('reason')}"
    return f"SL {_px(pl.get('sl'))} · T {_px(pl.get('target'))} · R:R {pl.get('rr')} ⇒ {(sm or {}).get('result')}"


def sensitivity_md(recs, main_name, alt_names):
    """प्रत्येक signal: मुख्य settings विरुद्ध पर्यायी (उदा. buffer 0) — SL / target / R:R / निकाल, आणि RR<3 मुळे नाकारलेले शेजारी."""
    cols = [main_name] + list(alt_names)
    L = ["| दिवस | वेळ | बाजू | entry | setup | " + " | ".join(cols) + " |", "|" + "---|" * (5 + len(cols))]
    stats = {c: {"signals": 0, "trades": 0, "rr_reject": 0, "target": 0, "sl": 0} for c in cols}
    for rec in recs:
        for s in rec["signals"]:
            cells = []
            for c in cols:
                pl, sm = (s.get("plan"), s.get("sim")) if c == main_name else ((s.get("alts") or {}).get(c, {}).get("plan"),
                                                                              (s.get("alts") or {}).get(c, {}).get("sim"))
                st = stats[c]
                st["signals"] += 1
                if pl and pl.get("ok"):
                    st["trades"] += 1
                    st["target"] += (sm or {}).get("result") == "TARGET"
                    st["sl"] += (sm or {}).get("result") == "SL"
                elif pl and "rr_filter" in str(pl.get("reason")):
                    st["rr_reject"] += 1
                cells.append(_cell(pl, sm))
            L.append(f"| {rec['date']} | {s['time']} | {'bear' if s['side'] < 0 else 'bull'} | {s['trigger_price']:,.1f} | {s.get('setup') or '—'} | "
                     + " | ".join(cells) + " |")
    L += ["", "| settings | signals | trades | RR<3 मुळे नाकारले | TARGET | SL |", "|---|---|---|---|---|---|"]
    L += [f"| {c} | {v['signals']} | {v['trades']} | {v['rr_reject']} | {v['target']} | {v['sl']} |" for c, v in stats.items()]
    return "\n".join(L), stats


def write_manifest(out_dir, run_id, days):
    """review manifest (backtest_review/telegram.py): items = दिवस, files = 1H + 15M (+ trade)."""
    items = []
    for n, rec in enumerate(days, 1):
        d = rec["date"]
        files = [f"{d}/{f}" for f in ("day_1h.png", "day_15m.png", "trade.png") if os.path.exists(os.path.join(out_dir, d, f))]
        if files:
            items.append({"n": n, "date": d, "item": f"{run_id}|day:{d}", "reading": reading(rec), "files": files})
    m = {"run_id": run_id, "title": "K-10", "items": items}
    json.dump(m, open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return m


def main(argv=None):
    from simple_core import settings as SS
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--recent-data", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--exec-profile", default=None, help="simple_core execution profile (dashboard); नसेल ⇒ फक्त signals")
    ap.add_argument("--exec-json", default=None, help="execution settings JSON (profile ऐवजी)")
    ap.add_argument("--exec-alt", action="append", default=[], help="sensitivity: NAME=JSON (उदा. buffer0='{...}'), अनेक वेळा")
    ap.add_argument("--exec-name", default="main", help="मुख्य settings चं नाव (अहवाल)")
    ap.add_argument("--engine-alt", action="append", default=[], help="engine sensitivity: NAME=JSON (उदा. cvp1.3='{\"commitment_vs_pause\": 1.3}')")
    ap.add_argument("--dates", default="", help="ठराविक दिवस (comma) — seed ने निवडलेल्या दिवसांच्या आधी")
    ap.add_argument("--run-id", default="k10/run", help="review manifest run id (उदा. k10/run2)")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    ex = exec_from_args(a.exec_profile, a.exec_json)
    alts = {}
    for item in a.exec_alt:
        nm, _, js = item.partition("=")
        alts[nm.strip()] = exec_from_args(None, js)
    os.makedirs(a.out_dir, exist_ok=True)
    summary = {"seed": a.seed, "exec_profile": a.exec_profile, "exec": ex, "exec_alts": alts, "exec_hash": SS.settings_hash(ex) if ex is not None else None,
               "days": []}
    fixed = [pd.Timestamp(x) for x in a.dates.split(",") if x.strip()]
    recs = []
    for part, path in (("IS", a.is_data), ("2026", a.recent_data)):
        raw = read(path)
        raw["timestamp"] = pd.to_datetime(raw["timestamp"])
        raw = DP.filter_allowed(raw, "golden")
        types = day_types(raw)
        lo, hi = (pd.Timestamp(x) for x in PARTS[part])
        mine = [(d, str(types["type"].get(d, "fixed"))) for d in fixed if lo <= d <= hi]
        new = [(d, k) for d, k in pick(types, *PARTS[part], rng) if d not in fixed]
        for day, kind in sorted(mine) + new:
            rec = run_day(raw, day, os.path.join(a.out_dir, f"{day:%Y-%m-%d}"), ex, render=not a.no_render, alts=alts)
            recs.append(rec)
            summary["days"].append({"date": rec["date"], "part": part, "type": kind, "fixed": day in fixed, "trend": rec.get("trend"),
                                    "signals": rec["signals"], "timing": rec["timing"]})
            print(f"{day:%Y-%m-%d} {part} {kind}: signals {[s_['time'] for s_ in rec['signals']]} · core p50 {rec['timing']['core_s']['p50']}s")
    eng = {}
    for item in a.engine_alt:                                                # तेच दिवस, engine setting बदलून (charts नाहीत)
        nm, _, js = item.partition("=")
        es_ = json.loads(js)
        from simple_core import settings as SS_
        bad = [k_ for k_ in es_ if k_ not in SS_.ENGINE_DEFAULTS]
        if bad:
            raise ValueError(f"--engine-alt {nm}: अज्ञात engine settings {bad}")
        eng[nm.strip()] = {}
        for rec in recs:
            d0 = pd.Timestamp(rec["date"])
            raw = read(a.is_data if d0.year < 2026 else a.recent_data)
            raw["timestamp"] = pd.to_datetime(raw["timestamp"])
            r2 = run_day(DP.filter_allowed(raw, "golden"), d0, os.path.join(a.out_dir, "_engine_alt", nm.strip(), rec["date"]), ex,
                         render=False, engine_s=es_)
            eng[nm.strip()][rec["date"]] = r2["signals"]
    if eng:
        L = ["| दिवस | main | " + " | ".join(eng) + " |", "|" + "---|" * (2 + len(eng))]
        fmt = lambda ss: ", ".join(f"{x['time']} {'bear' if x['side'] < 0 else 'bull'}" for x in ss) or "—"     # noqa: E731
        for rec in recs:
            L.append(f"| {rec['date']} | {fmt(rec['signals'])} | " + " | ".join(fmt(eng[n][rec['date']]) for n in eng) + " |")
        summary["engine_sensitivity"] = {n: {d: [x["time"] for x in v] for d, v in eng[n].items()} for n in eng}
        with open(os.path.join(a.out_dir, "k10_engine_sensitivity.md"), "w", encoding="utf-8") as fh:
            fh.write("# Engine sensitivity (signals)\n\n" + "\n".join(L) + "\n")
    if ex is not None:
        md, stats = sensitivity_md(recs, a.exec_name, list(alts))
        summary["sensitivity"] = {"settings": {a.exec_name: ex, **alts}, "stats": stats}
        with open(os.path.join(a.out_dir, "k10_report.md"), "w", encoding="utf-8") as fh:
            fh.write(f"# K-10 {a.run_id} · seed {a.seed}\n\n" + md + "\n")
        print(md.splitlines()[-1 - len(alts)])
    if not a.no_render:
        m = write_manifest(a.out_dir, a.run_id, recs)
        print(f"manifest: {len(m['items'])} items")
    json.dump(summary, open(os.path.join(a.out_dir, "k10_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("ok", a.out_dir)


if __name__ == "__main__":
    main()
