"""scripts/level_gate_preopen.py — 09:15 आधी एकदा: आजची Daily + Weekly trend अवस्था + bots कोणते areas पाहणार (trade-बाजूचे), Telegram ला.

Abhi (TRADE_SESSION_LEVEL_BOTS_CONFIRMATION §8; TELEGRAM_CLEANUP 1b / 3): दिवसातून **एकच** संदेश —
  ओळ 1 साधी (काय पाहायचं) · "Decision needed: none — information" · प्रत्येक symbol ची **एक** ओळ (Daily + Weekly trend, last close,
  trade-बाजूचे areas आणि किंमतीपासूनचं अंतर points मध्ये) · "── details ──" खाली bot-निहाय areas + MCX / entry नियम (जुना तपशील).
Trend (decision3 Daily, कालच्या close पर्यंत) दिवसासाठी cache होतो — bots तोच वापरतात. Trend काढता आला नाही ⇒ "NO NEW ENTRIES
(fail-closed)" स्पष्ट. Weekly फक्त माहिती (engine च्या ① सारखीच गणना: Daily ⇒ W-FRI ⇒ fold) — gate निर्णय बदलत नाही. Order नाही.

ONE_BOT_TOMORROW §4: संदेशाची पहिली ओळ = dashboard settings वरून चालू bot(s), उदा. "Only 15M SRv2 active · signal source: engine · symbols
NIFTY / BANKNIFTY / SENSEX · mode PAPER" (hard-coded नाही — वेगळं असेल तर जे चालू ते). signal source engine / both ⇒ प्रत्येक symbol साठी
engine_signal store चा शेवटचा computed_at: नाही / ENGINE_STALE_HOURS पेक्षा जुना ⇒ ❌ ओळ. Price / trend data नाही, Upstox login नाही,
settings DB नाही ⇒ ❌ ओळ.

    python3 scripts/level_gate_preopen.py [--symbols NIFTY,BANKNIFTY,SENSEX] [--no-telegram | --dry-run]
"""
import argparse
import html
import datetime as dt
import os
import sys

import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots_common import level_reaction as LR  # noqa: E402
from bots_common import plain_text as PT  # noqa: E402

BOT_TFS = {"5M Instant": ("1M", "5M"), "Classic": ("5M", "15M"), "15M SRv2": ("15M", "30M", "60M")}
ALL_TFS = ("1M", "5M", "15M", "30M", "60M")


def trade_side_areas(zones, tfs, last, ctx, n=3):
    """त्या bot च्या timeframes चे ACTIVE areas ⇒ trend ने परवानगी दिलेल्या बाजूचे, किंमतीच्या सर्वात जवळचे n."""
    if zones is None or len(zones) == 0 or last is None:
        return []
    out = []
    for _, z in zones.iterrows():
        if z.get("status") != "ACTIVE" or not any(str(z.get("zone_type", "")).endswith(f"_{tf}") for tf in tfs):
            continue
        lo = float(z["zone_low"])
        hi = float(z["zone_high"]) if z.get("zone_high") is not None else lo
        lo, hi = min(lo, hi), max(lo, hi)
        side = LR.BULL if hi < last else (LR.BEAR if lo > last else None)
        if side and LR.side_allowed(ctx, side, (lo, hi)):
            out.append((abs((lo + hi) / 2 - last), side, lo, hi, str(z.get("zone_type"))))
    out.sort()
    seen, res = set(), []
    for _, side, lo, hi, zt in out:
        k = (round(lo), round(hi))
        if k not in seen:
            seen.add(k)
            res.append((side, lo, hi, zt))
        if len(res) >= n:
            break
    return res


def area_words(side, lo, hi, zt, last):
    """"supply 22,715–22,776 (1H, ≈150 pts above)" — अंतर = last close पासून area च्या जवळच्या कडेपर्यंत."""
    bull = side == LR.BULL
    tf = PT.tf_word(zt)
    dist = (last - hi) if bull else (lo - last)
    rng = f"{lo:,.0f}" if round(lo) == round(hi) else f"{lo:,.0f}–{hi:,.0f}"
    return f"{'demand' if bull else 'supply'} {rng} ({(tf + ', ') if tf else ''}{PT.pts(dist)} {'below' if bull else 'above'})"


# ------------------------------------------------------------------------------------------------ कोणते bots चालू (settings वरून)
# (label, settings key, चालू आहे का (settings, symbol), signal_source key) — bots स्वतः जे तपासतात तेच default (symbol_enabled)
INDEX_BOTS = (
    ("15M SRv2", "15m_dynamic_sr", lambda s, sym: bool(s.get("symbol_enabled", sym == "NIFTY")), "signal_source"),
    ("5M Instant", "1m_instant", lambda s, sym: bool(s.get("symbol_enabled", sym == "NIFTY")), "signal_source"),
    ("SR V3 shadow", "1m_instant", lambda s, sym: bool(s.get("srv3_shadow_enabled", False) and s.get("symbol_enabled", sym == "NIFTY")),
     "srv3_signal_source"),
    ("Classic SR", "classic_sr_reversal", lambda s, sym: bool(s.get("symbol_enabled", False)), "signal_source"),
)
LABEL_TFS = {"15M SRv2": BOT_TFS["15M SRv2"], "5M Instant": BOT_TFS["5M Instant"], "SR V3 shadow": BOT_TFS["5M Instant"],
             "Classic SR": BOT_TFS["Classic"]}
ENGINE_STALE_HOURS = 96                                                    # weekend + एक सुट्टी: त्यापेक्षा जुना engine ⇒ ❌ चालू नाही


def bot_status(symbols, get_settings, mcx_fn=None):
    """Settings (dashboard) वरून: [{"label", "symbol", "source", "mode"}] चालू bots. वाचता आलं नाही ⇒ raise (caller ❌ लिहितो)."""
    import engine_signal as ES
    out = []
    for label, key, on, src_key in INDEX_BOTS:
        for sym in symbols:
            s = get_settings(key, sym)
            if s is None:
                raise RuntimeError(f"settings {key}/{sym} not readable")
            if on(s, sym):
                out.append({"label": label, "symbol": sym, "source": ES.source_of(s, src_key), "mode": str(s.get("trading_mode", "PAPER"))})
    for sym in (mcx_fn() if mcx_fn else ()):
        out.append({"label": "MCX Futures", "symbol": sym, "source": "own", "mode": "PAPER/LIVE (MCX settings)"})
    return out


def status_line(active, symbols):
    """HTML-escaped (settings मधली मूल्यं Telegram HTML मोडत नाहीत)."""
    return html.escape(_status_line(active, symbols), quote=False)


def _status_line(active, symbols):
    """संदेशाची पहिली ओळ: "Only 15M SRv2 active · signal source: engine · symbols NIFTY / BANKNIFTY / SENSEX · mode PAPER" (settings वरून)."""
    if active is None:
        return "❌ Bot settings could not be read — cannot confirm which bot is active (check the dashboard / database)."
    if not active:
        return f"❌ No bot is active for {' / '.join(symbols)} — no new entries today."
    labels = list(dict.fromkeys(a["label"] for a in active))

    def part(label):
        rows = [a for a in active if a["label"] == label]
        syms = " / ".join(dict.fromkeys(a["symbol"] for a in rows))
        src = " / ".join(sorted({a["source"] for a in rows}))
        mode = " / ".join(sorted({a["mode"] for a in rows}))
        return syms, src, mode
    if len(labels) == 1:
        syms, src, mode = part(labels[0])
        off = [s for s in symbols if s not in syms.split(" / ")]
        return (f"Only {labels[0]} active · signal source: {src} · symbols {syms} · mode {mode}"
                + (f" · not active for {' / '.join(off)}" if off else ""))
    return f"⚠️ {len(labels)} bots active: " + " · ".join(f"{lb} ({'; '.join(part(lb))})" for lb in labels)


def engine_last_run(symbol, path=None):
    """engine_signal store मधला त्या symbol चा सर्वात नवा computed_at (IST naive) किंवा None. Store वाचता नाही ⇒ raise."""
    import engine_signal as ES
    with ES.connect(path) as c:
        r = c.execute("SELECT MAX(computed_at) AS t FROM engine_signals WHERE symbol=?", (str(symbol).upper(),)).fetchone()
    t = r["t"] if r is not None else None
    return None if not t else ES._naive(t)


ENGINE_FIRST_RUN = (9, 31)                                                  # one-bot engine cron: 1,16,31,46 4-9 UTC ⇒ पहिला run 09:31 IST
ENGINE_FIRST_RUN_GRACE = (9, 45)                                           # त्यानंतरही एकही row नाही ⇒ ❌ (चालत नाही)
ENGINE_CRON_MARK = "# one-bot-engine"                                      # install_engine_schedule.sh ची engine ओळ (warm ओळ नाही)


def engine_volume_note(symbol, path=None):
    """Abhi Z-1h: engine चा शेवटचा row "volume normalisation: insufficient history" (raw per-bar average) वापरत असेल तर ती ओळ; नाहीतर /
    store वाचता नाही ⇒ None."""
    try:
        import json
        import engine_signal as ES
        with ES.connect(path) as c:
            r = c.execute("SELECT payload FROM engine_signals WHERE symbol=? ORDER BY bar_ts DESC LIMIT 1", (str(symbol).upper(),)).fetchone()
        vm = (json.loads(r["payload"] or "{}") or {}).get("volume_measure") if r else None
    except Exception:                                                      # noqa: BLE001 — फक्त माहिती
        return None
    return f"ℹ️ {symbol}: {vm}." if vm and "insufficient history" in vm else None


def engine_cron_installed(text):
    """crontab मध्ये चालू (comment नसलेली) one-bot engine ओळ आहे का. crontab वाचता नाही (None) ⇒ False (खात्री नाही ⇒ ❌ कायम)."""
    return any(x.rstrip().endswith(ENGINE_CRON_MARK) and "engine_signal_run.py" in x and not x.lstrip().startswith("#")
               for x in (text or "").splitlines())


def previous_session(day):
    """`day` च्या आधीचा trading session (weekday, config.NSE_HOLIDAYS_2026 सुट्टी नाही)."""
    try:
        import config
        hol = getattr(config, "NSE_HOLIDAYS_2026", set())
    except Exception:                                                      # noqa: BLE001
        hol = set()
    d = pd.Timestamp(day).date() - dt.timedelta(days=1)
    while d.weekday() >= 5 or d in hol:
        d -= dt.timedelta(days=1)
    return d


def engine_problem(sym, engine_fn, now, stale_hours=ENGINE_STALE_HOURS, cron_installed=False):
    """(ओळ किंवा None, शेवटचा run किंवा None). आजचा पहिला run अजून नाही (09:45 IST आधी, आज row नाही) आणि one-bot engine cron ओळ आहे:
      • मागच्या trading session चा किमान एक row (decision / error) ⇒ ℹ️ "engine starts at 09:31 (cron installed)";
      • नाही ⇒ ❌ "engine did not run in the last session — check engine_signal.log".
    बाकी: row नाही ⇒ ❌ no records; ENGINE_STALE_HOURS पेक्षा जुना ⇒ ❌ stopped; नाहीतर OK (None, t)."""
    try:
        t = engine_fn(sym)
    except Exception as exc:                                               # noqa: BLE001
        return f"❌ {sym}: engine status not readable ({type(exc).__name__}) — no engine setups can be trusted today.", None
    n = pd.Timestamp(now)
    t = None if t is None else pd.Timestamp(t)
    before_first = (n.hour, n.minute) < ENGINE_FIRST_RUN_GRACE and (t is None or t.normalize() < n.normalize())
    if cron_installed and before_first:
        prev = previous_session(n)
        if t is not None and t.date() >= prev:
            return (f"ℹ️ {sym}: engine starts at {ENGINE_FIRST_RUN[0]:02d}:{ENGINE_FIRST_RUN[1]:02d} (cron installed) — "
                    f"last run {t:%d %b %H:%M}."), t
        return f"❌ {sym}: engine did not run in the last session ({prev:%d %b}) — check engine_signal.log.", None
    if t is None:
        return f"❌ {sym}: the engine has no records — it is not running, so no setups will come for {sym}.", None
    age = (n - t).total_seconds() / 3600
    if age > stale_hours:
        return f"❌ {sym}: the engine last ran {t:%d %b %H:%M} ({age:,.0f} h ago) — it looks stopped.", None
    return None, t


def symbol_line(sym, ctx, weekly, last, zones, tfs=ALL_TFS):
    """प्रत्येक symbol ची एक साधी ओळ (engine codes नाहीत)."""
    wk = f"Weekly {html.escape(str(weekly), quote=False)}" if weekly else "Weekly n/a"
    if not ctx.get("ok"):
        mark = "❌ " if str(ctx.get("trend") or "UNKNOWN") == "UNKNOWN" else ""
        return f"{mark}<b>{sym}</b>: NO NEW ENTRIES today — {html.escape(PT.unclear_words(ctx), quote=False)}, {wk}. Open trades still exit as usual."
    head = f"<b>{sym}</b>: {html.escape(PT.trend_words(ctx), quote=False)}, {wk}"
    if ctx.get("mature"):
        head += f" (daily move: {LR.mature_words(ctx)})"                            # Abhi B1: context only, no grade cap
    elif ctx.get("origin_risk"):
        head += " (price is near the trend's starting point, so new entries are weak)"
    if last is None:
        return "❌ " + head + ". Price data missing (no last close), so no area distances."
    ar = trade_side_areas(zones, tfs, last, ctx, n=3)
    sides = sorted(ctx.get("sides") or ())
    want = " or ".join("demand" if s == LR.BULL else "supply" for s in sides) or "trade-side"
    if not ar:
        return head + f". Last close {last:,.0f}. No {want} area near price yet."
    return head + f". Last close {last:,.0f}. Watching " + "; ".join(area_words(s, lo, hi, zt, last) for s, lo, hi, zt in ar) + "."


def build_report(symbols, token, get_zones, last_close, trend_fn=None, weekly_fn=None, day=None, active=False, engine_fn=None,
                 now=None, problems=(), engine_cron=False):
    """एकच संदेश (HTML). ओळ 1 = चालू bot(s) (settings वरून: "Only 15M SRv2 active · signal source: engine · symbols … · mode PAPER"),
    ओळ 2 साधी (काय पाहायचं), ओळ 3 Decision needed; symbol-निहाय एक ओळ (+ ❌ engine / data ओळ) · ── details ── (bot-निहाय areas, MCX, नियम).
    active = bot_status() निकाल (None ⇒ settings वाचता नाही ⇒ ❌; False ⇒ status ओळ नाही — जुने callers). engine_fn(sym) ⇒ computed_at —
    signal source engine / both असलेल्या symbols साठीच तपासणी. engine_cron = one-bot engine cron ओळ आहे (`engine_cron_installed`)."""
    trend_fn = trend_fn or (lambda sym: LR.daily_trend(sym, token))
    weekly_fn = weekly_fn or (lambda sym: None)
    day = day or dt.date.today().isoformat()
    now = now or pd.Timestamp.now("UTC").tz_localize(None) + pd.Timedelta(hours=5, minutes=30)
    tfs = ALL_TFS
    if active:
        tfs = tuple(dict.fromkeys(tf for a in active for tf in LABEL_TFS.get(a["label"], ()))) or ALL_TFS
    eng_syms = {a["symbol"] for a in (active or []) if a["source"] in ("engine", "both")}
    plain, det = list(problems), []
    for sym in symbols:
        ctx = trend_fn(sym)
        last = last_close(sym)
        zones = get_zones(sym) if ctx.get("ok") else None
        try:
            wk = weekly_fn(sym)
        except Exception:                                                  # noqa: BLE001 — weekly फक्त माहिती
            wk = None
        plain.append(symbol_line(sym, ctx, wk, last, zones, tfs))
        if sym in eng_syms:
            bad, t = engine_problem(sym, engine_fn or engine_last_run, now, cron_installed=engine_cron)
            if bad:
                plain.append(bad)
            if t is not None:
                det.append(f"{sym} engine: last run {t:%d %b %H:%M}")
            vnote = engine_volume_note(sym)                                # Abhi Z-1h: raw-volume fallback स्पष्ट
            if vnote:
                plain.append(vnote)
        head = f"{sym} · {html.escape(str(ctx.get('reason')), quote=False)}"
        if ctx.get("protected") is not None:
            head += f" · protected {ctx['protected']:,.0f}"
        if not ctx.get("ok"):
            det.append(head + "\n⛔ NO NEW ENTRIES today (fail-closed) — exits run as usual")
            continue
        det.append(head + (f" · last close {last:,.0f}" if last else ""))
        for bot, tfs in BOT_TFS.items():
            ar = trade_side_areas(zones, tfs, last, ctx)
            if not ar:
                det.append(f"• {bot}: no trade-side area near price")
                continue
            txt = "; ".join(f"{'demand' if s == LR.BULL else 'supply'} {lo:,.0f}–{hi:,.0f}" for s, lo, hi, _ in ar)
            det.append(f"• {bot}: watching {txt}")
    det.append("MCX: PAPER = confirmation gate on 15M (trend from the current contract's Daily); entry only after CONFIRMED "
               "(no Vision approval for MCX yet). LIVE MCX stays on touch until you change its entry mode. Exits run as usual.")
    det.append("Entry only after a closed-candle commitment → Vision → your ✅. PAPER only.")
    head = (f"🧭 Pre-open check {day}: today's trend for each index and the areas the bots will trade "
            "(distance in points from the last close).")
    if active is not False:                                                # ONE_BOT §4: संदेश चालू bot च्या ओळीने सुरू
        head = status_line(active, symbols) + "\n" + head
    return f"{head}\n{PT.DECISION_NONE}\n\n" + "\n".join(plain) + f"\n{PT.SEP}\n" + "\n".join(det)


def one_bot_problems(status_fn=None):
    """ONE_BOT §4: `bots_common.one_bot.one_bot_status()` — फक्त 15M SRv2 (engine, PAPER) चालू नसेल / Vision approval / PAPER instruments /
    engine schedule / auto-trader cron / LIVE (untouched) ⇒ ❌ / ⚠️ ओळ (`preopen_line`, HTML-escaped). सगळं ठीक ⇒ [] (status ओळ पुरेशी)."""
    try:
        if status_fn is None:
            from bots_common.one_bot import one_bot_status as status_fn
        st = status_fn()
    except Exception as exc:                                               # noqa: BLE001
        return [f"❌ One-bot status not readable ({type(exc).__name__}) — check settings / crontab before trading."]
    if st.get("ok") and not st.get("live_untouched"):
        return []
    return [html.escape(st.get("line") or "❌ One-bot mode NOT clean", quote=False)]


def weekly_trend(df, today=None):
    """Daily candles ⇒ Weekly trend (engine ① सारखीच: W-FRI + fold, weekly_min_bars). फक्त माहिती. अपुरा data ⇒ None."""
    if df is None or len(df) == 0:
        return None
    from decision3 import daily as DD
    from decision3 import settings as S3
    d = LR.prepare_daily(df, today)
    if len(d) < 30:
        return None
    s = S3.load(None)
    st = DD.fold(DD.weekly_from_daily(d), {**s, "daily_min_sessions": int(s["weekly_min_bars"])})
    return st[-1].trend if st else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="फक्त छाप — Telegram ला पाठवत नाही (--no-telegram सारखंच)")
    a = ap.parse_args(argv)
    import cloud_db
    token = cloud_db.get_effective_upstox_token(None)
    problems = []
    if not token:
        print("❌ Upstox token नाही — आधी daily login करा. Trend काढता येत नाही ⇒ bots नवे entries घेणार नाहीत (fail-closed).")
        problems.append("❌ Upstox login missing — no price data, so no trend and no new entries until you log in.")
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    today = dt.date.today()
    cache = {}

    def daily_df(sym):
        """एका symbol चे Daily candles एकदाच (trend + weekly + last close तिघांना)."""
        if sym not in cache:
            try:
                from upstox_api import fetch_candles
                cache[sym] = fetch_candles(token, sym, current_spot=0, interval="day", lookback_days=3650) if token else None
            except Exception:                                              # noqa: BLE001
                cache[sym] = None
        return cache[sym]

    def last_close(sym):
        df = daily_df(sym)
        try:
            return float(df["close"].iloc[-1]) if df is not None and len(df) else None
        except Exception:                                                  # noqa: BLE001
            return None

    conn = cloud_db.get_connection()
    if conn is None:                                                       # settings ⇒ defaults (bots सुद्धा तेच पाहतात) — स्पष्ट सांगा
        problems.append("❌ Settings database not reachable — the bot line above shows DEFAULT settings, not your dashboard values.")
    else:
        conn.close()
    try:                                                                   # ONE_BOT §4: कोणता bot चालू — dashboard settings वरून
        from bots_common import level_visibility as LV
        active = bot_status(syms, cloud_db.get_strategy_settings, LV.mcx_symbols)
    except Exception as exc:                                               # noqa: BLE001 — status ओळ ❌ सांगते
        print(f"⚠️ bot settings: {type(exc).__name__}: {exc}")
        active = None
    problems = one_bot_problems() + problems
    try:
        from bots_common.one_bot import read_crontab
        engine_cron = engine_cron_installed(read_crontab())
    except Exception:                                                      # noqa: BLE001 — खात्री नाही ⇒ ❌ कायम
        engine_cron = False
    msg = build_report(syms, token, lambda s: cloud_db.get_market_zones(s), last_close,
                       trend_fn=lambda s: LR.daily_trend(s, token, fetch=lambda tok, sy: daily_df(sy)),
                       weekly_fn=lambda s: weekly_trend(daily_df(s), today), day=today.isoformat(), active=active,
                       problems=problems, engine_cron=engine_cron)
    print(msg)
    if a.no_telegram or a.dry_run:
        return 0
    from notifications import send_telegram_message
    return 0 if send_checked(msg, send_telegram_message) else 1


def send_checked(msg, send):
    """send(msg) (HTML) ⇒ False / चूक ⇒ एकदा साध्या मजकुराने (tags काढून, escape) पुन्हा. दोन्ही वेळा ❌ stdout / log मध्ये. रिटर्न bool."""
    import re

    def _try(text):
        try:
            return send(text) is not False
        except Exception as exc:                                           # noqa: BLE001
            print(f"❌ Telegram error: {type(exc).__name__}: {exc}")
            return False
    if _try(msg):
        return True
    print("❌ Pre-open (HTML) was not sent to Telegram — retrying as plain text")
    plain = html.escape(html.unescape(re.sub(r"<[^>]+>", "", msg)), quote=False)
    if _try(plain):
        print("✅ Pre-open sent as plain text")
        return True
    print("❌ Pre-open NOT sent to Telegram (both attempts failed) — check the bot token / chat id / network")
    return False


if __name__ == "__main__":
    sys.exit(main())
