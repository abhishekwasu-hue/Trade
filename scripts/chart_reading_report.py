#!/usr/bin/env python3
"""scripts/chart_reading_report.py — the daily Chart Reading Report on Telegram (Abhi's order, owner-orders DECISIONS 35).

Per symbol (dashboard `chart_reading_symbols`, empty ⇒ `signal_symbols`):
  --mode close   (after the market close; the reading for the next session):
                 Message 1 = an album of 3 annotated PNGs (Weekly + Daily, 1H, 15M — decision3/chart_reading_charts.py);
                 Message 2 = the reading (bots_common/chart_reading_text.py, language + detail from the dashboard), ≤ one Telegram
                 message, the full detail on the dashboard page (page_chart_reading.py) linked at the end;
                 Vision's part only when `chart_reading_vision = on` (and the Vision env / key / budget allow it) — information only.
  --mode preopen (a short refresh before the open): what changed since the stored close reading; text only.
Built only from the decision3 READER's facts (decision3/chart_reading.py): no new reading rule, score or number. Never an order, a gate
or a setting change; PAPER / LIVE untouched. The report is OFF by default (`chart_reading_report`, until Abhi approves the sample):
off ⇒ the script prints one line and exits 0 (the cron line is harmless). --force runs it anyway (review / sample).
Stored for the dashboard page (never in git — .gitignore data/chart_reading/): data/chart_reading/<SYM>/latest_<mode>.json (+ PNGs),
data/chart_reading/reading_checks.jsonl (Vision's disagreements as reading checks for OPEN_QUESTIONS).

Live inputs = the live engine's own (engine3_live: Upstox 15M / Daily / 5M LTF / near-month FUT 5M / 1m, the dashboard engine3 settings);
after the close the completed Daily candle of the day is included (the next session's engine reads it). Offline (review / sample):
--inputs DIR (engine_<SYM>_{m15,m1,daily,ltf5,fut5}.csv.gz, as scripts/pa_t8_objects_charts.py) --at "YYYY-MM-DD HH:MM" = the data cut
(every bar ends ≤ it — no look-ahead).

    python3 scripts/chart_reading_report.py --mode close [--symbols NIFTY,BANKNIFTY] [--dry-run] [--force] [--out DIR]
    python3 scripts/chart_reading_report.py --mode preopen
    python3 scripts/chart_reading_report.py --inputs DIR --symbols NIFTY --at "2026-10-19 15:30" --force --dry-run --out DIR --lang en
"""
import argparse
import contextlib
import html
import io
import json
import os
import sys
import time
import warnings

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

STORE = os.path.join(ROOT, "data", "chart_reading")
CHART_BUDGET_S = 120                                                       # operational: all charts of one run (seconds)
SESSION_CLOSE = (15, 30)                                                   # operational: after it the day's Daily candle is complete


# ------------------------------------------------------------------------------------------------------------------------ inputs
def _read(path):
    if not path or not os.path.exists(path):
        return None
    d = pd.read_csv(path)
    for c in ("timestamp", "bar_end"):
        if c in d.columns:
            t = pd.to_datetime(d[c])
            if getattr(t.dt, "tz", None) is not None:
                t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
            d[c] = t
    return d


def _with_end(d, minutes):
    if d is not None and "bar_end" not in d.columns:
        d["bar_end"] = d["timestamp"] + pd.Timedelta(minutes=minutes)
    return d


def cut_inputs(m15, m1, daily, ltf, fut, at):
    """No look-ahead: every bar ends ≤ the cut (`at`); Daily = candles whose session ended ≤ the cut."""
    at = pd.Timestamp(at)
    m15 = m15[m15["bar_end"] <= at].reset_index(drop=True)
    if m1 is not None:
        m1 = m1[m1["timestamp"] + pd.Timedelta(minutes=1) <= at].reset_index(drop=True)
    if ltf is not None:
        ltf = _with_end(ltf, 5)
        ltf = ltf[ltf["bar_end"] <= at].reset_index(drop=True)
    if fut is not None:
        fut = _with_end(fut, 5)
        fut = fut[fut["bar_end"] <= at].reset_index(drop=True)
    if daily is not None:
        d = daily.copy()
        end = d["bar_end"] if "bar_end" in d.columns else pd.to_datetime(d["timestamp"]).dt.normalize() + pd.Timedelta(hours=15, minutes=30)
        daily = d[end <= at].reset_index(drop=True)
    return m15, m1, daily, ltf, fut


def offline_inputs(inputs, sym, at):
    f = lambda k: os.path.join(inputs, f"engine_{sym}_{k}.csv.gz")       # noqa: E731
    m15 = _with_end(_read(f("m15")), 15)
    if m15 is None:
        raise SystemExit(f"{sym}: no 15M bars in {inputs}")
    m15 = m15[["timestamp", "bar_end", "open", "high", "low", "close"]]
    return cut_inputs(m15, _read(f("m1")), _read(f("daily")), _read(f("ltf5")), _read(f("fut5")), at)


def live_inputs(sym, token, now):
    """The live engine's inputs (engine3_live.build_inputs + load_m1); after the close the day's completed Daily candle is kept.
    FUT volume missing (a data problem) ⇒ the reading is still built and says so (volume = missing)."""
    import engine3_live as L3
    import engine_signal as ES
    from bots_common import level_reaction as LR
    feed = L3.UpstoxFeed(token, now.date())
    s = ES.engine3_settings(sym)
    try:
        m15, daily, ltf, fut, _note = L3.build_inputs(feed, sym, now, s)
    except L3.FutVolumeMissing:
        m15, daily, ltf, fut, _note = L3.build_inputs(feed, sym, now, s, levels_only=True)
    if (now.hour, now.minute) >= SESSION_CLOSE:
        ss = {**L3.DEFAULTS, **(s or {})}
        dd = feed.index(sym, "day", ss["engine3_daily_days"])
        daily = LR.prepare_daily(L3._naive(dd)[["timestamp", "open", "high", "low", "close"]], now.normalize() + pd.Timedelta(days=1))
    m1, _info = L3.load_m1(feed, sym, m15, pd.Timestamp(now), s)
    return m15, m1, daily, ltf, fut, L3.v22_settings(s)


def build_v(sym, m15, m1, daily, ltf, fut, s3=None):
    import instruments as INS
    from decision3 import engine as E3
    from decision3 import history as HI
    prev = INS._current["name"]
    INS.set_current(sym)
    try:
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            m15 = m15.drop(columns=[c for c in ("volume",) if c in m15.columns])
            kw = {"sealed": HI.sealed_fn(sym), "ltf": ltf, "futures": fut}
            if s3:
                kw["s"] = s3
            return E3.V22(m15, m1, daily, **kw)
    finally:
        INS._current["name"] = prev


# ------------------------------------------------------------------------------------------------------------------------ vision
def vision_part(V, sym, facts, settings, enabled=None, client_factory=None, allow_factory=None, record=None, log=print):
    """Vision's part when switched on — None (not run) otherwise. Budget = run_visual_audit's own caps (make_allow / record_usage)."""
    if str(settings.get("chart_reading_vision")) != "on":
        return None, []
    if (enabled if enabled is not None else os.environ.get("VISUAL_AUDIT_ENABLED", "").strip() in ("1", "true", "yes")) is False:
        return {"status": "not_run", "why": "VISUAL_AUDIT_ENABLED is not 1"}, []
    from decision3 import chart_reading_vision as CRV
    from opportunity_engine.visual_audit import auditor as AU
    cfg = AU.VisualAuditConfig.from_env()
    if not cfg.model:
        return {"status": "not_run", "why": "VISUAL_AUDIT_MODEL not set"}, []
    try:
        if allow_factory is None or client_factory is None or record is None:
            import run_visual_audit as RVA
            allow_factory = allow_factory or RVA.make_allow
            record = record or (lambda rec: RVA.record_usage(cfg.model, rec))
            client_factory = client_factory or AU.make_client
        client = client_factory()
        allow = allow_factory(cfg.model)
        res = CRV.audit(client, cfg, V, sym, facts, allow=allow, on_usage=record)
    except Exception as exc:                                               # noqa: BLE001 — information only
        log(f"⚠️ {sym} Vision: {type(exc).__name__}: {exc}")
        return {"status": "not_run", "why": f"{type(exc).__name__}"}, []
    return CRV.summarise(res), CRV.reading_checks(sym, res)


# ------------------------------------------------------------------------------------------------------------------------ store
def store_dir(sym, root=None):
    d = os.path.join(root or STORE, sym)
    os.makedirs(d, exist_ok=True)
    return d


def save(sym, mode, rec, pngs=(), root=None):
    d = store_dir(sym, root)
    for name, png, _cap, _meta in pngs or ():
        with open(os.path.join(d, f"{mode}_{name.replace('+', '')}.png"), "wb") as fh:
            fh.write(png)
    with open(os.path.join(d, f"latest_{mode}.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1, default=str)
    return d


def load_latest(sym, mode="close", root=None):
    p = os.path.join(root or STORE, sym, f"latest_{mode}.json")
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def append_checks(lines, root=None):
    if not lines:
        return
    os.makedirs(root or STORE, exist_ok=True)
    with open(os.path.join(root or STORE, "reading_checks.jsonl"), "a", encoding="utf-8") as fh:
        for x in lines:
            fh.write(json.dumps({"at": str(pd.Timestamp.now()), "check": x}, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------------------------------------------------------------ one symbol
def report_symbol(sym, V, settings, mode="close", link=None, lang=None, detail=None, charts=True, deadline=None, vision_fn=None,
                  prev=None):
    """Facts ⇒ (charts) ⇒ (Vision) ⇒ texts. Returns the record (texts EN + MR, facts, vision, chart meta, errors) and the PNG items."""
    from bots_common import chart_reading_text as CT
    from decision3 import chart_reading as CR
    from decision3 import chart_reading_charts as CC
    t = len(V.m15) - 1
    row = V.decide(t)
    facts = CR.collect(V, t, sym, row=row)
    lang = lang or settings.get("chart_reading_language") or "mr"
    detail = detail or settings.get("chart_reading_detail") or "short"
    link = link if link is not None else (settings.get("chart_reading_page_url") or None)
    rec = {"symbol": sym, "mode": mode, "as_of": facts["as_of"], "language": lang, "detail": detail, "facts": facts, "errors": {}}
    items = []
    if mode == "preopen":
        rec["text"] = {lg: CT.refresh((prev or {}).get("facts"), facts, lg, link) for lg in ("en", "mr")}
        rec["send"] = rec["text"][lang]
        return rec, items
    if charts:
        items, errs = CC.render(V, sym, facts, deadline=deadline)
        rec["charts"] = [{"name": n, "caption": c, **m} for n, _p, c, m in items]
        if errs:
            rec["errors"]["charts"] = errs
    vision, checks = vision_fn(facts) if vision_fn is not None else (None, [])
    rec["vision"], rec["reading_checks"] = vision, checks
    rec["text"], rec["meta"] = {}, {}
    for lg in ("en", "mr"):
        for dl in ("short", "full"):
            txt, meta = CT.render(facts, lg, dl, link=link, vision=vision)
            rec["text"][f"{lg}_{dl}"] = txt
            rec["meta"][f"{lg}_{dl}"] = meta
    rec["send"] = rec["text"][f"{lang}_{detail}"]
    rec["problems"] = CT.check(rec["send"])
    return rec, items


def send(rec, items, send_text=None, send_album=None, log=print):
    """Album first (Message 1), then the reading (Message 2, HTML-escaped plain text). A failure is logged, never raised."""
    ok = True
    if items:
        try:
            if send_album is None:
                from notifications import send_telegram_media_group as send_album
            ok = bool(send_album([(p, c) for _n, p, c, _m in items])) and ok
        except Exception as exc:                                           # noqa: BLE001
            log(f"⚠️ {rec['symbol']} charts not sent: {type(exc).__name__}: {exc}")
            ok = False
    try:
        if send_text is None:
            from notifications import send_telegram_message as send_text
        ok = bool(send_text(html.escape(rec["send"], quote=False))) and ok
    except Exception as exc:                                               # noqa: BLE001
        log(f"⚠️ {rec['symbol']} reading not sent: {type(exc).__name__}: {exc}")
        ok = False
    return ok


# ------------------------------------------------------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=("close", "preopen"), default="close")
    ap.add_argument("--symbols", default=None)
    ap.add_argument("--dry-run", action="store_true", help="build + store, no Telegram")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--force", action="store_true", help="run even when chart_reading_report = off (review / sample)")
    ap.add_argument("--out", default=None, help="also write the PNGs + texts here")
    ap.add_argument("--store", default=None, help="store root (default data/chart_reading)")
    ap.add_argument("--inputs", default=None, help="offline engine inputs dir (review / sample)")
    ap.add_argument("--at", default=None, help="offline data cut 'YYYY-MM-DD HH:MM' (bars ending ≤ it)")
    ap.add_argument("--lang", choices=("mr", "en"), default=None)
    ap.add_argument("--detail", choices=("short", "full"), default=None)
    a = ap.parse_args(argv)
    import cloud_db
    settings = cloud_db.get_chart_reading_settings()
    if settings.get("chart_reading_report") != "on" and not a.force:
        print("ℹ️ chart_reading_report = off (dashboard) — no report (the pre-open / close messages are unchanged).")
        return 0
    syms = [s.strip().upper() for s in a.symbols.split(",")] if a.symbols else cloud_db.chart_reading_symbols(settings)
    token = None
    if not a.inputs:
        token = cloud_db.get_effective_upstox_token(None)
        if not token:
            print("❌ Upstox login missing — no chart reading report.")
            return 1
    import engine_signal as ES
    now = ES._naive(ES.now_ist())
    deadline = time.monotonic() + CHART_BUDGET_S
    rc = 0
    for sym in syms:
        try:
            if a.inputs:
                m15, m1, daily, ltf, fut = offline_inputs(a.inputs, sym, a.at or now)
                s3 = None
            else:
                m15, m1, daily, ltf, fut, s3 = live_inputs(sym, token, now)
            V = build_v(sym, m15, m1, daily, ltf, fut, s3)
            prev = load_latest(sym, "close", a.store) if a.mode == "preopen" else None
            rec, items = report_symbol(sym, V, settings, a.mode, lang=a.lang, detail=a.detail, deadline=deadline, prev=prev,
                                       vision_fn=lambda facts, V=V, sym=sym: vision_part(V, sym, facts, settings))
            del V
        except Exception as exc:                                           # noqa: BLE001 — one symbol never stops the others
            print(f"❌ {sym}: {type(exc).__name__}: {exc}")
            rc = 1
            continue
        save(sym, a.mode, rec, items, a.store)
        append_checks(rec.get("reading_checks"), a.store)
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            for name, png, _c, _m in items:
                with open(os.path.join(a.out, f"{sym}_{name.replace('+', '')}.png"), "wb") as fh:
                    fh.write(png)
            for k, txt in rec["text"].items():
                with open(os.path.join(a.out, f"{sym}_{a.mode}_{k}.txt"), "w", encoding="utf-8") as fh:
                    fh.write(txt + "\n")
        print(f"✅ {sym} {a.mode}: as of {rec['as_of']} · {len(items)} charts · message {len(rec['send'])} chars"
              + (f" · problems {rec.get('problems')}" if rec.get("problems") else "") + (f" · errors {rec['errors']}" if rec["errors"] else ""))
        if a.dry_run or a.no_telegram:
            print(rec["send"])
            continue
        if not send(rec, items):
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
