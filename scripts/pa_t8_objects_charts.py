#!/usr/bin/env python3
"""PA standard §4 (track T8) verification: the ONE object list (decision3.draw_objects) drawn on the 1H and 15M verification charts and
on the Telegram (Vision) chart, with the per-timeframe reader story. Review only: no Telegram, no order, no store write, no network.
Code मध्ये तारीख नाही — bars come from the CLI. NIFTY holdout dates are refused by V22 itself (sealed guard).

  python3 scripts/pa_t8_objects_charts.py --inputs <dir with engine_<SYM>_{m15,m1,daily,ltf5,fut5}.csv.gz> --symbol NIFTY \
      --at last --at "2026-10-21 11:15" --out <trade-data>/review/pa_standard/t8/nifty_2026-10-21
  python3 scripts/pa_t8_objects_charts.py --m15 BANKNIFTY_15M.csv.gz --daily BANKNIFTY_D.csv.gz --symbol BANKNIFTY --sample 8 --out DIR

Per bar: h1_<ts>_today.png (chart_objects off = today's chart), h1_<ts>_objects.png, m15_<ts>_objects.png, vision_<ts>_objects.png
(when 1m bars are given and kaleido / Chrome are present), objects_<ts>.json, story_<ts>.txt."""
import argparse
import contextlib
import io
import json
import os
import sys
import warnings

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _read(path):
    if not path or not os.path.exists(path):
        return None
    d = pd.read_csv(path)
    for c in ("timestamp", "bar_end"):
        if c in d.columns:
            d[c] = pd.to_datetime(d[c])
    return d


def _with_end(d, minutes=None):
    if d is not None and "bar_end" not in d.columns:
        d["bar_end"] = d["timestamp"] + (pd.Timedelta(minutes=minutes) if minutes else pd.Timedelta(hours=15, minutes=30))
        if not minutes:
            d["timestamp"] = d["timestamp"].dt.normalize()
            d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    return d


def load(a):
    sym = a.symbol.upper()
    f = (lambda k: os.path.join(a.inputs, f"engine_{sym}_{k}.csv.gz")) if a.inputs else (lambda k: None)
    m15 = _with_end(_read(a.m15 or f("m15")), 15)
    daily = _with_end(_read(a.daily or f("daily")))
    m1, ltf, fut = _read(f("m1")), _read(f("ltf5")), _read(f("fut5"))
    if m15 is None:
        raise SystemExit("no 15M bars (--inputs or --m15)")
    m15 = m15[["timestamp", "bar_end", "open", "high", "low", "close"]]
    return m15, m1, daily, ltf, fut


def bars_of(V, a):
    ts = pd.to_datetime(V.m15["timestamp"]).reset_index(drop=True)
    out = []
    for x in a.at or ():
        if x == "last":
            out.append(len(ts) - 1)
        else:
            k = int((ts <= pd.Timestamp(x)).sum()) - 1
            if k >= 0:
                out.append(k)
    if a.sample:
        days = ts.dt.normalize()
        uniq = sorted(days.unique())[-int(a.sample_sessions):]
        pick = [uniq[int(round(i * (len(uniq) - 1) / max(1, a.sample - 1)))] for i in range(a.sample)]
        for d in dict.fromkeys(pick):
            idx = days.index[days == d]
            out.append(int(idx[len(idx) * 2 // 3]))                       # a bar two thirds into the session (display sample)
    return sorted(dict.fromkeys(out))


def vision_png(m1, fut, V, t, r, objs, sym):
    """The Telegram (Vision) approval chart at the bar's close with chart_objects = on and the same object list."""
    from vision import chart as VCH
    from vision import config as VCF
    if m1 is None:
        return None, {"error": "no 1m bars"}
    lv = r.get("level") or {}
    bull = lv.get("role") == "support" or (not lv and r.get("trend_used") == "UP")
    cs = {**{k: VCF.BOT_DEFAULTS[k] for k in VCF.CTX_KEYS}, "events": {}, "chart_objects": "on"}
    sig = {"bot": "srv2_momentum_reversal", "bot_label": "verification (T8)", "symbol": sym, "direction": "BULLISH" if bull else "BEARISH",
           "role": "SUPPORT" if bull else "RESISTANCE", "level": (lv["lo"] + lv["hi"]) / 2 if lv else None, "setup_tf": "15M",
           "signal_ts": pd.Timestamp(V.bar_end[t]), "tags": {}, "ctx_settings": cs, "objects": objs}
    return VCH.render(m1, sig, fut=fut)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--inputs")
    p.add_argument("--m15")
    p.add_argument("--daily")
    p.add_argument("--symbol", default="NIFTY")
    p.add_argument("--at", action="append", help='"last" or a bar time "YYYY-MM-DD HH:MM" (repeatable)')
    p.add_argument("--sample", type=int, default=0, help="N bars spread over the last --sample-sessions sessions")
    p.add_argument("--sample-sessions", type=int, default=60)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    warnings.simplefilter("ignore")
    from decision3 import charts as CH
    from decision3 import draw_objects as DO
    from decision3 import engine as E3
    from decision3 import history as HI
    m15, m1, daily, ltf, fut = load(a)
    with contextlib.redirect_stdout(io.StringIO()):
        V = E3.V22(m15, m1, daily, sealed=HI.sealed_fn(a.symbol), ltf=ltf, futures=fut)
    os.makedirs(a.out, exist_ok=True)
    index = []
    for t in bars_of(V, a):
        r = V.decide(t)
        why = []
        objs = DO.collect(V, t, r=r, why=why)
        st = DO.tf_story(V, t, objs, r=r)
        txt = DO.story_text(st)
        tag = pd.Timestamp(V.m15["timestamp"].iloc[t]).strftime("%Y-%m-%d_%H%M")
        tr = r["trend_used"]
        title = f"{a.symbol} · {r['decision']}"
        files = {"h1_today": f"h1_{tag}_today.png", "h1_objects": f"h1_{tag}_objects.png", "m15_objects": f"m15_{tag}_objects.png"}
        open(os.path.join(a.out, files["h1_today"]), "wb").write(CH.h1_png(V.levels, t, tr, title))
        open(os.path.join(a.out, files["h1_objects"]), "wb").write(CH.h1_png(V.levels, t, tr, title, chart_objects="on", objects=objs,
                                                                             story=txt))
        open(os.path.join(a.out, files["m15_objects"]), "wb").write(CH.m15_png(V, t, title, r=r, chart_objects="on", objects=objs,
                                                                               bars=75, story=txt))
        png, meta = vision_png(m1, fut, V, t, r, objs, a.symbol.upper())
        if png:
            files["vision_objects"] = f"vision_{tag}_objects.png"
            open(os.path.join(a.out, files["vision_objects"]), "wb").write(png)
        json.dump({"bar": t, "ts": r["ts"], "decision": r["decision"], "trend_used": tr, "skipped": why, "objects": objs},
                  open(os.path.join(a.out, f"objects_{tag}.json"), "w"), indent=1, ensure_ascii=False)
        open(os.path.join(a.out, f"story_{tag}.txt"), "w").write(txt + "\n")
        kinds = {}
        for o in objs:
            kinds[o["kind"]] = kinds.get(o["kind"], 0) + 1
        index.append({"ts": r["ts"], "decision": r["decision"], "kinds": kinds, "files": files, "vision_error": (meta or {}).get("error"),
                      "skipped": why})
        print(r["ts"], r["decision"], kinds, "vision:", "ok" if png else (meta or {}).get("error"))
        print(txt)
    json.dump(index, open(os.path.join(a.out, "index.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
