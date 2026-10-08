"""research/vision_led_sample.py — टप्पा 0 (V-L0): Vision-led नमुना चाचणी. **Trade नाही, order नाही, bot ला हात नाही.**

🎓 Abhi (TRADE_VISION_LED_PROMPT B): NIFTY 15M, 24 Sep → 8 Oct 2026 (CONTAMINATED ⇒ फक्त illustration, tuning नाही).
  candidates (code, सैल) ⇒ vision_led_v2 (chart + OHLC तक्ते + code areas + तटस्थ facts + playbook; code side नाही) ⇒ code validation
  (ohlc_ref, R:R, पक्के नियम, A3 व्हेटो, strike σ माहिती) ⇒ annotated chart (entry bar पर्यंत) + hindsight chart ⇒ Telegram "🧪 SAMPLE"
  (≤ 20 संदेश) ⇒ अहवाल. खर्च ≤ --budget ($1.50); पुढचा call मर्यादा ओलांडेल तर थांबतो (अहवालात "थांबलो — विचारा").
VPS वर चालवा (API key, Telegram, trade-data). PNG / JSON फक्त --out-dir (trade-data) मध्ये; public repo मध्ये फक्त अहवाल (मजकूर).

    python3 research/vision_led_sample.py --data /root/trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz \
        --futures /root/trade-data/futures_volume --out-dir /root/trade-data/vision_led/2026-10-08 [--dry-run] [--no-telegram]
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chart_reader import areas as AR          # noqa: E402
from chart_reader import evaluate as EV       # noqa: E402
from chart_reader import settings as CS       # noqa: E402
from chart_reader import volume as VO         # noqa: E402
from elliott import data_policy as DP         # noqa: E402
from vision_led import candidates as CA       # noqa: E402
from vision_led import charts as CH           # noqa: E402
from vision_led import prompt as PR           # noqa: E402
from vision_led import validate as VA         # noqa: E402

START, END = "2026-09-24 09:15", "2026-10-08 15:30"
GOLDEN = ("2026-10-07 14:00", "2026-10-07 15:00")
EST_FIRST_USD = 0.06                                                    # पहिल्या call आधीचा सावध अंदाज; नंतर खऱ्या सरासरीने


def cost_usd(model, usage):
    from vision.signal_audit import cost_usd as C
    return C(model, usage)


def code_side(rec):
    """market_state F4 side (bull_put / bear_call / unclear); जुन्या records साठी impulse दिशा."""
    cs = rec.get("code_side")
    return cs if cs else side_name(rec.get("side"))


def side_name(side):
    return "bull_put" if side > 0 else "bear_call"


def future_bars(trig, j, days=2):
    """entry नंतरचे bars: entry दिवसाचे उरलेले + पुढचे `days` trading दिवस (फक्त hindsight साठी)."""
    after = trig.iloc[j + 1:]
    if not len(after):
        return after
    d0 = pd.Timestamp(trig["timestamp"].iloc[j]).normalize()
    days_after = sorted({pd.Timestamp(t).normalize() for t in after["timestamp"] if pd.Timestamp(t).normalize() > d0})[:days]
    keep = pd.to_datetime(after["timestamp"]).dt.normalize().isin([d0] + days_after)
    return after[keep].reset_index(drop=True)


def futures_series(m15, futures):
    """(array, "rel" | "raw" | None): rel_vol असेल तर तो; नाहीतर (इतिहास < 5 दिवस) raw 15M futures volume; data नसेल ⇒ (None, None)."""
    if futures is None or not len(futures):
        return None, None
    rv = VO.series_for(m15, futures, 15)
    if np.isfinite(rv).any():
        return rv, "rel"
    raw = VO.to_tf(VO.continuous(futures), 15).set_index("timestamp")["volume"]
    out = pd.to_datetime(m15["timestamp"]).map(raw).to_numpy(float)
    return (out, "raw") if np.isfinite(out).any() else (None, None)


def assert_no_lookahead(c, m15, h1, line):
    """Vision input फक्त decision bar च्या close पर्यंत: 15M चा शेवटचा bar = decision bar, 1H चे सगळे bars त्या close आधी बंद, line panel सुद्धा."""
    ds, de = pd.Timestamp(c["bar_start"]), pd.Timestamp(c["bar_end"])
    if pd.Timestamp(m15["timestamp"].iloc[-1]) != ds or (pd.to_datetime(m15["timestamp"]) > ds).any():
        raise AssertionError(f"lookahead: 15M तक्ता decision bar ({ds}) पलीकडे")
    if len(h1) and (pd.to_datetime(h1["bar_end"]) > de).any():
        raise AssertionError(f"lookahead: 1H bar {de} नंतर बंद होणारा")
    if len(line) and (pd.to_datetime(line["timestamp"]) > ds).any():
        raise AssertionError("lookahead: line panel decision bar पलीकडे")


def neutral_facts(m15, cut, be, mr, n_swings=12, swings=None, htf_swings=None, htf_tf="1h"):
    """तटस्थ facts (निष्कर्ष नाही): market_state चे confirmed swings (F1: एकच swing engine — 15M trade degree आणि HTF; वेळ, किंमत,
    H/L — HH/LH labels किंवा trend निष्कर्ष नाही), PDH / PDL / PDC (CAS वगळून, PDC = official close), आजचा open आणि gap."""
    out = []
    for name, sw in (("15M trade-degree", swings), (f"{htf_tf.upper()}", htf_swings)):
        sw = [p for p in (sw or []) if p.get("conf") is not None and pd.Timestamp(p["ts"]) < pd.Timestamp(be)][-n_swings:]
        if sw:
            out.append(f"Confirmed {name} swings (oldest first): " + "; ".join(
                f"{pd.Timestamp(p['ts']):%d %b %H:%M} {'high' if p['kind'] == 'H' else 'low'} {p['price']:.2f}" for p in sw))
    pl = AR.prior_levels(cut, be)
    if pl:
        out.append(f"Previous day: high {pl['pdh']:.2f}, low {pl['pdl']:.2f}, close {pl['pdc']:.2f}"
                   + (f"; previous week high {pl['week_high']:.2f}, low {pl['week_low']:.2f}" if pl.get("week_high") else ""))
        today = cut[pd.to_datetime(cut["timestamp"]).dt.normalize() == pd.Timestamp(be).normalize()]
        if len(today):
            o = float(today["open"].iloc[0])
            out.append(f"Today's open {o:.2f}, gap vs previous close {o - pl['pdc']:+.2f} points ({(o / pl['pdc'] - 1) * 100:+.2f}%, "
                       f"{(o - pl['pdc']) / mr:+.1f} MR); today's high so far {float(today['high'].max()):.2f}, low {float(today['low'].min()):.2f}.")
    return out


def caption(rec):
    v, res, h = rec.get("vision") or {}, rec.get("result") or {}, rec.get("hindsight") or {}
    vside = (v.get("side") if v.get("trade") else "no trade") if v else "—"
    head = (f"🧪 SAMPLE — trade नाही\n{pd.Timestamp(rec['bar_start']):%d %b %H:%M} · code side {code_side(rec)} · vision side {vside} · "
            f"grade {v.get('grade', '—')}\n(1) entry-वेळचा chart · (2) hindsight (पुढचे 2 दिवस)")
    st = res.get("status", rec.get("status"))
    if st == "OK":
        body = (f"ENTRY {res['entry']:,.0f} · SL {res['inv']:,.0f} · TARGET {res['target']:,.0f} · R:R 1:{res['rr']:.1f}\n"
                f"hindsight: {h.get('result', '—')}" + (f" @ {h['at'][5:16]}" if h.get("at") else ""))
    elif st == "NO_TRADE":
        body = "vision: NO TRADE"
    else:
        body = "REJECTED: " + "; ".join(res.get("reasons") or [rec.get("error") or "—"])[:300]
    story = "\n".join(f"• {x}" for x in (v.get("story") or [])[:4])
    return (head + "\n" + body + ("\n" + story if story else ""))[:1024]


def pick_for_telegram(recs, cap=20):
    """≤ cap संदेश: सगळे बसत असतील तर सगळे; नाहीतर सगळे A/B (OK) आधी, मग बाकी — उरलेल्यांचा एकत्रित सारांश."""
    if len(recs) <= cap:
        return recs, []
    ab = [r for r in recs if (r.get("result") or {}).get("status") == "OK" and (r.get("vision") or {}).get("grade") in ("A", "B")]
    ab_ids = {id(r) for r in ab}
    chosen = (ab + [r for r in recs if id(r) not in ab_ids])[:cap]
    ids = {id(r) for r in chosen}
    return sorted(chosen, key=lambda r: r["bar_start"]), [r for r in recs if id(r) not in ids]


def run(m1, model, client, out_dir, budget, start=START, end=END, futures=None, dry_run=False, send=None, cap=20, log=print, s=None):
    s = s or CS.load()
    os.makedirs(out_dir, exist_ok=True)
    trig = EV.frame(m1, "15m", pd.Timestamp(end) + pd.Timedelta(minutes=1))
    full_trig = EV.frame(m1, "15m", m1["timestamp"].max() + pd.Timedelta(minutes=1))

    def cut_at(be):
        return m1[pd.to_datetime(m1["timestamp"]) + pd.Timedelta(minutes=1) <= pd.Timestamp(be)].reset_index(drop=True)

    def horiz_fn(be):
        return CA.htf_levels(m1, be, EV.frame)

    def ctx_fn(be):
        return AR.prior_levels(cut_at(be), be)
    cands = CA.scan(m1, trig, start, end, s, horiz_fn=horiz_fn, ctx_fn=ctx_fn)
    log(f"candidates: {len(cands)}")
    recs, spent, n_calls, stopped = [], 0.0, 0, None
    for c in cands:
        be, j = pd.Timestamp(c["bar_end"]), c["j"]
        cut = cut_at(be)
        w = cut[cut["timestamp"] >= be - pd.Timedelta(days=90)].reset_index(drop=True)
        try:
            ev = EV.evaluate(w, "srv2", be, s=s)
        except Exception as exc:                                         # code सल्ला अपयशी ⇒ vision ला सल्ला नाही, नोंद
            ev = {"error": f"{type(exc).__name__}: {exc}"}
        m15 = trig.iloc[: j + 1].reset_index(drop=True)
        h1 = EV.frame(cut, "1h", be)
        days = sorted(pd.to_datetime(m15["timestamp"]).dt.normalize().unique())[-5:]
        line = m15[pd.to_datetime(m15["timestamp"]).dt.normalize().isin(days)].reset_index(drop=True)
        vol, vol_kind = futures_series(m15.tail(60), futures)
        rec = {"bar_start": str(c["bar_start"]), "bar_end": str(be), "side": c["side"], "code_side": c.get("code_side"),
               "side_reasons": c.get("side_reasons"), "state_lines": c.get("state_lines"), "impulse": c["impulse"], "mr": c["mr"],
               "near_area_ids": [z["id"] for z in c["areas"]], "code_grade": ev.get("grade"), "code_total": ev.get("total")}
        tag = f"{pd.Timestamp(c['bar_start']):%Y%m%d_%H%M}"
        title = f"NIFTY 15M · decision bar {pd.Timestamp(c['bar_start']):%d %b %H:%M} ({PR.PROMPT_VERSION} input; chart ends at this close)"
        img = CH.png(CH.input_figure(m15, h1, line, c["all_areas"], title, vol,
                                     "futures volume (rel_vol, slot-normalised)" if vol_kind == "rel" else "futures volume (raw contracts; rel_vol needs 5+ days)",
                                     cas=cut))
        if img:
            open(os.path.join(out_dir, f"{tag}_input.png"), "wb").write(img)
        if dry_run:
            rec["status"] = "DRY_RUN"
            recs.append(rec)
            continue
        est = (spent / n_calls) if n_calls else EST_FIRST_USD
        if spent + est > budget:
            stopped = f"budget: खर्च ${spent:.3f} + पुढचा अंदाज ${est:.3f} > ${budget}"
            rec["status"] = "NOT_RUN_BUDGET"
            recs.append(rec)
            continue
        vnote = None if vol is None or not np.isfinite(np.asarray(vol, float)).any() else \
            (f"Futures volume ({'rel_vol vs same time-slot median' if vol_kind == 'rel' else 'raw contracts, no slot baseline yet'}) "
             "per 15M bar, last 20: " + ", ".join("-" if not np.isfinite(x) else (f"{x:.2f}" if vol_kind == "rel" else f"{x:,.0f}")
                                                  for x in np.asarray(vol, float)[-20:]))
        assert_no_lookahead(c, m15, h1, line)
        text = PR.user_text(c, m15, h1, c["all_areas"], neutral_facts(m15, cut, be, c["mr"], swings=c.get("swings"),
                                                                       htf_swings=c.get("htf_swings"), htf_tf=c.get("htf_tf", "1h")), vnote)
        params = PR.build_request(img, text, model, effort=os.environ.get("VISION_SIGNAL_EFFORT") or None,
                                  thinking=os.environ.get("VISION_SIGNAL_THINKING") or None)
        t0 = time.monotonic()
        try:
            msg = client.messages.create(**params)
        except Exception as exc:
            if "temperature" in str(exc).lower() and "temperature" in params:
                params.pop("temperature")
                rec["note"] = "temperature नाकारलं ⇒ default"
                msg = client.messages.create(**params)
            else:
                rec.update(status="API_ERROR", error=f"{type(exc).__name__}: {str(exc)[:200]}")
                recs.append(rec)
                continue
        data, err, usage = PR.parse(msg)
        n_calls += 1
        c_usd = cost_usd(model, usage)
        spent += c_usd
        rec.update(latency_ms=int((time.monotonic() - t0) * 1000), usage=usage, cost_usd=round(c_usd, 5))
        if err:
            rec.update(status="PARSE_ERROR", error=err)
            recs.append(rec)
            continue
        rec["vision"] = data
        daily = cut.groupby(cut["timestamp"].dt.normalize())["close"].last()
        daily = daily[daily.index < be.normalize()]
        res = VA.validate(data, c, [m15, h1], c["bar_start"], ev if "error" not in ev else None, m15, s, daily.to_numpy())
        if res["status"] == "OK":
            res["inv_ref_label"] = data["invalidation"]["ohlc_ref"]
        rec["result"] = {k: v for k, v in res.items() if k != "area"} | {"area_id": (res.get("area") or {}).get("id")}
        fut = future_bars(full_trig, int(full_trig.index[pd.to_datetime(full_trig["timestamp"]) == pd.Timestamp(c["bar_start"])][0]))
        if res["status"] == "OK":
            rec["hindsight"] = VA.hindsight(fut, res["side"], res["entry"], res["inv"], res["target"])
        ann_title = f"NIFTY 15M · {pd.Timestamp(c['bar_start']):%d %b %H:%M} · vision {data.get('side')} grade {data.get('grade')} · {res['status']}"
        a_png = CH.png(CH.annotated_figure(m15, res, c, ann_title, cut=cut))
        h_png = CH.png(CH.annotated_figure(m15, res, c, ann_title + " · HINDSIGHT", future=fut, hindsight=rec.get("hindsight"), cut=cut))
        for nm, b in (("annotated", a_png), ("hindsight", h_png)):
            if b:
                open(os.path.join(out_dir, f"{tag}_{nm}.png"), "wb").write(b)
        rec["status"] = res["status"]
        rec["_png"] = [a_png, h_png]
        recs.append(rec)
    sent = []
    if send is not None and not dry_run:
        chosen, rest = pick_for_telegram([r for r in recs if r.get("_png")], cap)
        for r in chosen:
            ok = send(r["_png"], caption(r))
            sent.append(bool(ok))
        if rest:
            send([], "🧪 SAMPLE सारांश (उरलेले, chart शिवाय):\n" + "\n".join(
                f"{pd.Timestamp(r['bar_start']):%d %b %H:%M} {code_side(r)} · {r.get('status')} · grade {(r.get('vision') or {}).get('grade', '—')}"
                for r in rest)[:3900])
    for r in recs:
        r.pop("_png", None)
    summary = {"candidates": len(cands), "calls": n_calls, "cost_usd": round(spent, 4), "stopped": stopped, "telegram_sent": sum(sent),
               "status": {k: sum(r.get("status") == k for r in recs) for k in sorted({r.get("status") for r in recs})},
               "ab_ok": sum((r.get("result") or {}).get("status") == "OK" and (r.get("vision") or {}).get("grade") in ("A", "B") for r in recs),
               "hindsight": {k: sum((r.get("hindsight") or {}).get("result") == k for r in recs) for k in ("TARGET", "SL", "OPEN")},
               "golden": golden_check(recs)}
    json.dump({"summary": summary, "records": recs}, open(os.path.join(out_dir, "vision_led_sample.json"), "w"), ensure_ascii=False, indent=1,
              default=str)
    return summary, recs


def golden_check(recs):
    lo, hi = pd.Timestamp(GOLDEN[0]), pd.Timestamp(GOLDEN[1])
    win = [r for r in recs if lo <= pd.Timestamp(r["bar_start"]) <= hi]
    caught = [r for r in win if (r.get("vision") or {}).get("trade") and (r.get("vision") or {}).get("side") == "bear_call"]   # vision ची बाजू (code ची नाही)
    ok = [r for r in caught if (r.get("result") or {}).get("status") == "OK"]
    return {"candidates_in_window": len(win), "vision_bear_call": len(caught), "validated": len(ok),
            "detail": [(r["bar_start"], r.get("status"), (r.get("vision") or {}).get("grade")) for r in win]}


def _vside(r):
    v = r.get("vision") or {}
    if not v:
        return "—"
    return (f"{v.get('side')} / {v.get('grade')}" if v.get("trade") else f"no trade / {v.get('grade')}")


def _validation(r):
    res = r.get("result") or {}
    st = res.get("status") or r.get("status")
    if st == "REJECTED":
        return "REJECTED: " + "; ".join(res.get("reasons") or [])[:140]
    return st if st != "OK" else "OK"


def _sl_rr(res, kind):
    d = (res.get("sl_defs") or {}).get(kind)
    if not d:
        return "—"
    return f"{d['inv']:,.0f} → " + (f"1:{d['rr']:.1f}" if d.get("rr") else "—")


def report_md(summary, recs, model):
    g = summary["golden"]
    L = ["# Vision-led नमुना चाचणी (V-L0) — NIFTY 15M, 24 Sep → 8 Oct 2026", "",
         "> CONTAMINATED काळ ⇒ फक्त illustration, tuning नाही. Trade / order नाही. Model: "
         f"`{model}` (signals चाच), prompt `{PR.PROMPT_VERSION}`, temperature 0. Vision ला code ची बाजू / grade / narrative दिली नाही (anchoring "
         "टाळण्यासाठी); input फक्त decision bar च्या close पर्यंत. Charts trade-data मध्ये (public repo मध्ये नाहीत).", "",
         "## सारांश", "",
         f"- Candidates {summary['candidates']} · vision calls {summary['calls']} · खर्च **${summary['cost_usd']:.3f}**"
         + (f" · ⛔ थांबलो: {summary['stopped']} (पुढे जायचं का — विचारा)" if summary.get("stopped") else ""),
         f"- Status: {summary['status']} · validation पास + vision A/B: **{summary['ab_ok']}**",
         f"- Hindsight (validated trades): {summary['hindsight']} · Telegram संदेश: {summary['telegram_sent']}", "",
         "## Candidates", "",
         "R:R तीन प्रकारे: vision चा SL · reversal-candle SL (decision bar / आधीच्या bar चं टोक + buffer) · structural SL (active area / "
         "trendline पलीकडे + buffer). Code side = market_state (F4; vision ला दाखवली नाही).", "",
         "| candidate | code side | vision side / grade | validation | R:R vision SL | R:R candle SL | R:R structural SL | hindsight |",
         "|---|---|---|---|---|---|---|---|"]
    for r in recs:
        res, h = r.get("result") or {}, r.get("hindsight") or {}
        L.append(f"| {r['bar_start'][:16]} | {code_side(r)} | {_vside(r)} | {_validation(r)} | {res.get('rr') or '—'} | "
                 f"{_sl_rr(res, 'candle')} | {_sl_rr(res, 'structural')} | "
                 f"{h.get('result', '—')}{(' ' + h['at'][5:16]) if h.get('at') else ''} |")
    L += ["", "## 7 Oct golden (Abhi: 14:00–15:00 bear call)", "",
          f"- Window मधले candidates: {g['candidates_in_window']} · vision bear call: {g['vision_bear_call']} · validation पास: {g['validated']}"]
    for r in recs:
        if pd.Timestamp(GOLDEN[0]) <= pd.Timestamp(r["bar_start"]) <= pd.Timestamp(GOLDEN[1]):
            v, res = r.get("vision") or {}, r.get("result") or {}
            L.append(f"- {r['bar_start'][:16]}: code side {code_side(r)} · vision {_vside(r)} · {_validation(r)}"
                     + (f" · entry {res['entry']:,.1f}, SL {res['inv']:,.1f}, target {res['target']:,.1f}, R:R {res['rr']}"
                        f" · candle SL {_sl_rr(res, 'candle')} · structural SL {_sl_rr(res, 'structural')}" if res.get("entry") else "")
                     + (f" · hindsight {(r.get('hindsight') or {}).get('result')}" if r.get("hindsight") else ""))
            for x in v.get("story") or []:
                L.append(f"  - {x}")
    if not g["candidates_in_window"]:
        L.append("- या window मध्ये candidate नव्हता ⇒ सैल नियमांनी golden setup सुटला (candidate नियम तपासायचे).")
    L += ["", "## तपशील", ""]
    for r in recs:
        v, res = r.get("vision") or {}, r.get("result") or {}
        L.append(f"### {r['bar_start'][:16]} — code {code_side(r)} · vision {_vside(r)} · {r.get('status')} · ${r.get('cost_usd', 0) or 0:.3f}")
        if res.get("reasons"):
            L.append("- कारणं: " + "; ".join(res["reasons"]))
        if r.get("error"):
            L.append(f"- चूक: {r['error']}")
        for x in v.get("story") or []:
            L.append(f"  - {x}")
        if v.get("evidence_for"):
            L.append("- बाजूने: " + "; ".join(v["evidence_for"])[:400])
        if v.get("evidence_against"):
            L.append("- विरोधात: " + "; ".join(v["evidence_against"])[:400])
        if v.get("wrong_if"):
            L.append(f"- मी कुठे चुकीचा ठरेन: {v['wrong_if']}")
        L.append("")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--futures", default=None, help="trade-data/futures_volume (oe_futures_5min_NIFTY*.parquet)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report", default=os.path.join(ROOT, "docs", "reports", "vision_led_sample.md"))
    ap.add_argument("--budget", type=float, default=1.50)
    ap.add_argument("--max-telegram", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true", help="फक्त candidates + input charts (API call नाही)")
    ap.add_argument("--no-telegram", action="store_true")
    a = ap.parse_args(argv)
    m1 = DP.filter_allowed(pd.read_csv(a.data, parse_dates=["timestamp"]), "golden")
    model = os.environ.get("VISION_SIGNAL_MODEL") or None
    if not a.dry_run and not model:
        print("⛔ VISION_SIGNAL_MODEL env नाही")
        return 1
    client = None
    if not a.dry_run:
        from vision.signal_audit import make_client
        client = make_client(timeout_sec=60)
    fut = VO.load("NIFTY", a.futures) if a.futures else None
    send = None
    if not a.no_telegram and not a.dry_run:
        from vision_led import telegram as VT
        send = VT.send_album                                                # (a) annotated + (b) hindsight, एकच संदेश
    from opportunity_engine.visual_audit import render as R
    session = R.KaleidoSession() if hasattr(R, "KaleidoSession") else _null()   # visual audit PR नंतर: एकच Chrome सगळ्या charts साठी
    with session:
        summary, recs = run(m1, model, client, a.out_dir, a.budget, futures=fut, dry_run=a.dry_run, send=send, cap=a.max_telegram)
    md = report_md(summary, recs, model)
    open(os.path.join(a.out_dir, "vision_led_sample.md"), "w").write(md)
    if a.report:
        os.makedirs(os.path.dirname(a.report), exist_ok=True)
        open(a.report, "w").write(md)
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0


class _null:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


if __name__ == "__main__":
    sys.exit(main())
