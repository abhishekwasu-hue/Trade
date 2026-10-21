"""scripts/level_gate_preopen.py — 09:15 आधी एकदा: आजची Daily + Weekly trend अवस्था + bots कोणते areas पाहणार (trade-बाजूचे), Telegram ला.

Abhi (TRADE_SESSION_LEVEL_BOTS_CONFIRMATION §8; TELEGRAM_CLEANUP 1b / 3): दिवसातून **एकच** संदेश —
  ओळ 1 साधी (काय पाहायचं) · "Decision needed: none — information" · प्रत्येक symbol ची **एक** ओळ (Daily + Weekly trend, last close,
  trade-बाजूचे areas आणि किंमतीपासूनचं अंतर points मध्ये) · "── details ──" खाली bot-निहाय areas + MCX / entry नियम (जुना तपशील).
Trend (decision3 Daily, कालच्या close पर्यंत) दिवसासाठी cache होतो — bots तोच वापरतात. Trend काढता आला नाही ⇒ "NO NEW ENTRIES
(fail-closed)" स्पष्ट. Weekly फक्त माहिती (engine च्या ① सारखीच गणना: Daily ⇒ W-FRI ⇒ fold) — gate निर्णय बदलत नाही. Order नाही.

ONE_BOT_TOMORROW §4: संदेशाची पहिली ओळ = dashboard settings वरून चालू bot(s), उदा. "Only 15M SRv2 active · signal source: engine · symbols
NIFTY / BANKNIFTY · mode PAPER" (hard-coded नाही — वेगळं असेल तर जे चालू ते). signal source engine / both ⇒ प्रत्येक symbol साठी
engine_signal store चा शेवटचा computed_at: नाही / ENGINE_STALE_HOURS पेक्षा जुना ⇒ ❌ ओळ. Price / trend data नाही, Upstox login नाही,
settings DB नाही ⇒ ❌ ओळ.

Symbols = dashboard setting `signal_symbols` (default NIFTY / BANKNIFTY; `--symbols` दिले तरी त्या यादीबाहेरचे वगळले) — SENSEX फक्त data.
फक्त **चालू** bots आणि त्यांचे पट्टे (bands, low–high; Abhi TA4): signal source engine ⇒ engine (decision3 ② Levels) चे पट्टे
(`engine3_live.watched_levels`); own / both ⇒ market_zones, एकच-किंमत level ⇒ bot चाच gate पट्टा (level ± `gate_area_pad_pct`). बंद bots
(5M Instant, Classic …) संदेशात नाहीत; तपशील / त्रुटी फक्त log (stdout) मध्ये.

    python3 scripts/level_gate_preopen.py [--symbols NIFTY,BANKNIFTY] [--no-telegram | --dry-run]
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
from bots_common import preopen_crux as PC  # noqa: E402

BOT_TFS = {"5M Instant": ("1M", "5M"), "Classic": ("5M", "15M"), "15M SRv2": ("15M", "30M", "60M")}
ALL_TFS = ("1M", "5M", "15M", "30M", "60M")


def trade_side_areas(zones, tfs, last, ctx, n=3, pad_pct=None):
    """त्या bot च्या timeframes चे ACTIVE areas ⇒ trend ने परवानगी दिलेल्या बाजूचे, किंमतीच्या सर्वात जवळचे n. pad_pct (bot चा
    `gate_area_pad_pct`) ⇒ एकच-किंमत level (DYNAMIC_SR rows: zone_low = zone_high) bot सारखाच gate पट्टा (level ± pad / 2) — bot तोच
    पट्टा पाहतो (`level_gate_bot.areas_from_rows`)."""
    if zones is None or len(zones) == 0 or last is None:
        return []
    out = []
    for _, z in zones.iterrows():
        if z.get("status") != "ACTIVE" or not any(str(z.get("zone_type", "")).split("|", 1)[0].endswith(f"_{tf}") for tf in tfs):
            continue
        lo = float(z["zone_low"])
        hi = float(z["zone_high"]) if z.get("zone_high") is not None and pd.notna(z.get("zone_high")) else lo
        lo, hi = min(lo, hi), max(lo, hi)
        if pad_pct is not None:
            from bots_common.level_gate_bot import areas_from_rows
            lo, hi = areas_from_rows([{"zone_low": lo, "zone_high": hi}], lo * float(pad_pct) / 100.0)[0]
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


def area_words(side, lo, hi, zt, last, warn_pts=None, warn_rule=None):
    """"supply 22,715–22,776 (1H, ≈150 pts above), 61 pts wide" — अंतर = last close पासून area च्या जवळच्या कडेपर्यंत. रुंदी > warn_pts
    (`approval_band_warn_pts`, default 150) ⇒ "… 312 pts wide ⚠️ merged band — check (over 150 pts)" (Abhi; फक्त दाखवणं)."""
    bull = side == LR.BULL
    tf = PT.tf_word(zt)
    dist = (last - hi) if bull else (lo - last)
    one = round(lo) == round(hi)
    rng = f"{lo:,.0f}" if one else f"{lo:,.0f}–{hi:,.0f}"
    note = PT.zone_note(zt)
    wide = "" if one else PT.band_wide_words(lo, hi, warn_pts, warn_rule, engine_area=is_engine_zone(zt))   # layer 6b setting
    return (f"{'demand' if bull else 'supply'} {rng} ({(tf + ', ') if tf else ''}{PT.pts(dist)} {'below' if bull else 'above'}"
            + (f"; {note})" if note else ")") + (f", {wide}" if wide else ""))


def is_engine_zone(zt):
    """An engine (decision3) area row (`engine_zone_rows`: zone_type ENGINE_LEVEL_…) — one base, wick to body, never merged (#329)."""
    return str(zt or "").startswith("ENGINE_LEVEL")


def band_detail(lo, hi, warn_pts=None, warn_rule=None, engine_area=False):
    """details ओळीसाठी (HTML-escaped): "22,715–22,776 (61 pts)" (+ " ⚠️ merged band — check (width N pts &gt; 150)").
    Layer 6b: `approval_band_warn_rule` "method" + an engine area ⇒ no line (PT.band_flag)."""
    flag = PT.band_flag(lo, hi, warn_pts, warn_rule, engine_area=engine_area)
    return PT.band_range(lo, hi) + (f" {html.escape(flag, quote=False)}" if flag else "")


def warn_pts_for(active, sym):
    """चालू bots च्या settings मधला `approval_band_warn_pts` (त्या symbol चा पहिला) ⇒ float; नाही ⇒ default 150."""
    for a in active or ():
        if a.get("symbol") == sym and a.get("band_warn_pts") is not None:
            return PT.band_warn_pts(a["band_warn_pts"])
    return PT.band_warn_pts(None)


def warn_rule_for(active, sym):
    """Layer 6b: चालू bots च्या settings मधला `approval_band_warn_rule` (त्या symbol चा पहिला); नाही ⇒ "points" (आजचं)."""
    for a in active or ():
        if a.get("symbol") == sym and a.get("band_warn_rule") is not None:
            return PT.band_warn_rule(a["band_warn_rule"])
    return PT.band_warn_rule(None)


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
CHART_BUDGET_S = 60                                                        # pre-open charts: एका run मध्ये एकूण कमाल वेळ (s)
ENGINE_STALE_HOURS = 96                                                    # weekend + एक सुट्टी: त्यापेक्षा जुना engine ⇒ ❌ चालू नाही
ENGINE_TFS = ("1H", "1D")              # decision3 ② Levels: 1H areas (+ a Daily band where no 1H zone overlaps it, Abhi Z-1u)


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
                out.append({"label": label, "symbol": sym, "source": ES.source_of(s, src_key), "mode": str(s.get("trading_mode", "PAPER")),
                            "pad_pct": s.get("gate_area_pad_pct"), "band_warn_pts": s.get(PT.BAND_WARN_KEY),
                            "band_warn_rule": s.get(PT.BAND_WARN_RULE_KEY), PC.SETTING_KEY: s.get(PC.SETTING_KEY)})
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


def engine_zone_rows(levels):
    """engine levels (`watched_levels`: role / lo / hi) ⇒ market_zones सारख्या rows (zone_type …_1H) — trade_side_areas तेच वापरते.
    फक्त tradeable (`engine3_live.tradeable_levels`: BROKEN / DEAD नाहीत)."""
    from engine3_live import tradeable_levels
    tf = {"1H": "1H", "D": "1D", "W": "W"}

    def note(x):                                                           # Abhi Z-1u: confluence = label only
        return f"|{x['confluence_label']}" if x.get("confluence_label") else ""
    return pd.DataFrame([{"zone_type": f"ENGINE_LEVEL_{tf.get(x.get('tf'), '1H')}" + note(x),
                          "zone_low": float(x["lo"]), "zone_high": float(x["hi"]), "status": "ACTIVE"}
                         for x in tradeable_levels(levels)], columns=["zone_type", "zone_low", "zone_high", "status"])


def active_bot_areas(sym, active, ctx, last, zones, engine_fn=None, n=3):
    """त्या symbol वर चालू bots ⇒ [(label, source, areas | None, NA कारण | None)]. engine source ⇒ engine चे पट्टे; own / both ⇒ market_zones
    (bot चे TFs, bot चा gate पट्टा). engine areas आणता आले नाहीत ⇒ areas None + लहान कारण (तपशील stdout मध्ये)."""
    out, eng = [], {}
    for a in [x for x in (active or []) if x["symbol"] == sym and x["label"] in LABEL_TFS]:
        if a["source"] == "engine":
            if "levels" not in eng:
                try:
                    if engine_fn is None:
                        raise RuntimeError("engine areas not wired")
                    eng["levels"], eng["why"] = engine_zone_rows(engine_fn(sym)), None
                except Exception as exc:                                   # noqa: BLE001 — NA + कारण (नवा entry engine च ठरवतो)
                    print(f"⚠️ {sym} engine areas: {type(exc).__name__}: {exc}")
                    eng["levels"], eng["why"] = None, "engine areas not available (see the pre-open log)"
            if eng["levels"] is None:
                out.append((a["label"], "engine", None, eng["why"]))
            else:
                out.append((a["label"], "engine", trade_side_areas(eng["levels"], ENGINE_TFS, last, ctx, n), None))
        else:
            pad = a.get("pad_pct")
            if pad is None:
                from bots_common.level_gate_bot import AREA_PAD_PCT as pad
            out.append((a["label"], a["source"], trade_side_areas(zones, LABEL_TFS[a["label"]], last, ctx, n, pad_pct=pad), None))
    return out


def nearest(areas, last, n=3):
    """अनेक bots चे areas ⇒ किंमतीच्या सर्वात जवळचे n (duplicate नाही)."""
    seen, res = set(), []
    for side, lo, hi, zt in sorted(areas, key=lambda x: abs((x[1] + x[2]) / 2 - last)):
        if (round(lo), round(hi)) not in seen:
            seen.add((round(lo), round(hi)))
            res.append((side, lo, hi, zt))
    return res[:n]


def symbol_line(sym, ctx, weekly, last, zones, tfs=ALL_TFS, areas=None, na=None, warn_pts=None, warn_rule=None):
    """प्रत्येक symbol ची एक साधी ओळ (engine codes नाहीत). areas (चालू bots चे पट्टे) दिले ⇒ तेच; na ⇒ "Watched areas NA"."""
    wk = f"Weekly {html.escape(str(weekly), quote=False)}" if weekly else "Weekly n/a"
    if not ctx.get("ok"):
        mark = "❌ " if str(ctx.get("trend") or "UNKNOWN") == "UNKNOWN" else ""
        return f"{mark}<b>{sym}</b>: NO NEW ENTRIES today — {html.escape(PT.unclear_words(ctx), quote=False)}, {wk}. Open trades still exit as usual."
    head = f"<b>{sym}</b>: {html.escape(PT.trend_words(ctx), quote=False)}, {wk}"
    if ctx.get("mature"):
        head += f" (daily move: {LR.mature_words(ctx)})"                            # Abhi B1: context only, no grade cap
    elif ctx.get("origin_risk"):
        head += " (context: price is near the trend's starting point)"           # Abhi B1: context only, no block / downgrade
    if last is None:
        return "❌ " + head + ". Price data missing (no last close), so no area distances."
    ar = trade_side_areas(zones, tfs, last, ctx, n=3) if areas is None else nearest(areas, last, 3)
    sides = sorted(ctx.get("sides") or ())
    want = " or ".join("demand" if s == LR.BULL else "supply" for s in sides) or "trade-side"
    if na and not ar:
        return "❌ " + head + f". Last close {last:,.0f}. Watched areas NA — {html.escape(na, quote=False)}."
    if not ar:
        return head + f". Last close {last:,.0f}. No {want} area near price yet."
    return head + f". Last close {last:,.0f}. Watching " + "; ".join(area_words(s, lo, hi, zt, last, warn_pts, warn_rule) for s, lo, hi, zt in ar) + "."


def build_report(symbols, token, get_zones, last_close, trend_fn=None, weekly_fn=None, day=None, active=False, engine_fn=None,
                 now=None, problems=(), engine_cron=False, engine_areas_fn=None, crux_on=None, views=None, chart_fn=None):
    """एकच संदेश (HTML). ओळ 1 = चालू bot(s) (settings वरून: "Only 15M SRv2 active · signal source: engine · symbols … · mode PAPER"),
    ओळ 2 साधी (काय पाहायचं), ओळ 3 Decision needed; symbol-निहाय एक ओळ (+ ❌ engine / data ओळ) · ── details ── (bot-निहाय areas, MCX, नियम).
    active = bot_status() निकाल (None ⇒ settings वाचता नाही ⇒ ❌; False ⇒ status ओळ नाही — जुने callers). engine_fn(sym) ⇒ computed_at —
    signal source engine / both असलेल्या symbols साठीच तपासणी. engine_cron = one-bot engine cron ओळ आहे (`engine_cron_installed`).
    active list ⇒ फक्त चालू bots चे पट्टे (engine source ⇒ engine_areas_fn(sym) = `watched_levels`); बंद bots / MCX नियम संदेशात नाहीत.
    Abhi (track F): setting `preopen_charts` (crux_on None ⇒ चालू bots च्या settings वरून, default ON; जुने callers / settings वाचता नाहीत
    ⇒ बंद) ⇒ "Decision needed" नंतर symbol-निहाय CRUX block (`bots_common.preopen_crux`); बंद ⇒ आजचाच संदेश, अक्षरशः. views = {sym: V22}
    (pre-open चा तोच engine run ⇒ reader ची रेघ / touch N); chart_fn(sym, facts, weekly, line) ⇒ True (charts तयार) / False / raise ⇒
    crux ओळीत "(chart unavailable)" — chart कधीच संदेश थांबवत नाही."""
    trend_fn = trend_fn or (lambda sym: LR.daily_trend(sym, token))
    weekly_fn = weekly_fn or (lambda sym: None)
    day = day or dt.date.today().isoformat()
    now = now or pd.Timestamp.now("UTC").tz_localize(None) + pd.Timedelta(hours=5, minutes=30)
    tfs = ALL_TFS
    if active:
        tfs = tuple(dict.fromkeys(tf for a in active for tf in LABEL_TFS.get(a["label"], ()))) or ALL_TFS
    eng_syms = {a["symbol"] for a in (active or []) if a["source"] in ("engine", "both")}
    plain, det = list(problems), []
    legacy = active is False                                               # जुने callers: सगळे bots (settings माहीत नाहीत)
    crux, raw = [], {}
    if engine_areas_fn is not None:                                        # engine चे मूळ पट्टे (state / tf / confluence) crux साठी
        _areas_fn = engine_areas_fn

        def engine_areas_fn(sym):
            raw[sym] = _areas_fn(sym)
            return raw[sym]
    for sym in symbols:
        ctx = trend_fn(sym)
        last = last_close(sym)
        zones = get_zones(sym) if ctx.get("ok") else None
        try:
            wk = weekly_fn(sym)
        except Exception:                                                  # noqa: BLE001 — weekly फक्त माहिती
            wk = None
        per_bot = [] if legacy or not ctx.get("ok") or last is None else active_bot_areas(sym, active, ctx, last, zones, engine_areas_fn)
        warn = warn_pts_for(active if not legacy else None, sym)          # Abhi: merged band — check (setting, default 150)
        rule = warn_rule_for(active if not legacy else None, sym)         # layer 6b: approval_band_warn_rule (default points)
        if legacy:
            plain.append(symbol_line(sym, ctx, wk, last, zones, tfs, warn_pts=warn, warn_rule=rule))
        else:
            nas = [why for _, _, ar, why in per_bot if ar is None]
            na = ("bot settings could not be read" if active is None else "no active bot for this index" if not per_bot
                  else nas[0] if len(nas) == len(per_bot) else None)
            plain.append(symbol_line(sym, ctx, wk, last, zones, tfs, areas=[x for _, _, ar, _ in per_bot for x in (ar or [])], na=na,
                                     warn_pts=warn, warn_rule=rule))
            if (PC.setting_for(active, sym) if crux_on is None else crux_on):
                try:                                                       # crux कधीच संदेश थांबवत नाही: त्रुटी ⇒ log + crux नाही
                    cx = crux_block(sym, ctx, wk, last, per_bot, na, raw.get(sym), (views or {}).get(sym), chart_fn)
                except Exception as exc:                                   # noqa: BLE001
                    print(f"⚠️ {sym} pre-open crux: {type(exc).__name__}: {exc}")
                    cx = []
                if cx:
                    crux.extend(([""] if crux else []) + cx)
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
        rows = [(bot, "", trade_side_areas(zones, tf_, last, ctx), None) for bot, tf_ in BOT_TFS.items()] if legacy else per_bot
        for bot, src, ar, why in rows:
            name = f"{bot} (engine areas)" if src == "engine" else bot
            if ar is None:
                det.append(f"• {name}: {html.escape(why or 'areas not available', quote=False)}")
            elif not ar:
                det.append(f"• {name}: no trade-side area near price")
            else:
                txt = "; ".join(f"{'demand' if s == LR.BULL else 'supply'} {band_detail(lo, hi, warn, rule, is_engine_zone(zt))}"
                                for s, lo, hi, zt in ar)
                det.append(f"• {name}: watching {txt}")
    if legacy or any(a.get("label") == "MCX Futures" for a in (active or [])):
        det.append("MCX: PAPER = confirmation gate on 15M (trend from the current contract's Daily); entry only after CONFIRMED "
                   "(no Vision approval for MCX yet). LIVE MCX stays on touch until you change its entry mode. Exits run as usual.")
    det.append("Entry only after a closed-candle commitment → Vision → your ✅. PAPER only.")
    head = (f"🧭 Pre-open check {day}: today's trend for each index and the areas the bots will trade "
            "(distance in points from the last close).")
    if active is not False:                                                # ONE_BOT §4: संदेश चालू bot च्या ओळीने सुरू
        head = status_line(active, symbols) + "\n" + head
    top = ("\n".join(crux) + "\n\n") if crux else ""                       # Abhi (track F): crux वर, जुना मजकूर खाली तसाच
    return f"{head}\n{PT.DECISION_NONE}\n\n" + top + "\n".join(plain) + f"\n{PT.SEP}\n" + "\n".join(det)


def crux_block(sym, ctx, wk, last, per_bot, na, levels=None, V=None, chart_fn=None):
    """एका symbol च्या crux ओळी (`preopen_crux.lines`). areas = symbol ओळीतलाच watched list (nearest 3); levels = engine चे मूळ पट्टे;
    V ⇒ reader ची रेघ (touch N). chart_fn फक्त trend ठीक + last close असताना; त्रुटी / False ⇒ "(chart unavailable)" (log मध्ये कारण)."""
    ar = nearest([x for _, _, a, _ in per_bot for x in (a or [])], last, 3) if last is not None else []
    line = None
    if V is not None and ctx.get("ok"):
        try:
            from decision3 import preopen_chart as PCH
            line = PCH.line_facts(V, ctx.get("trend"))
        except Exception as exc:                                           # noqa: BLE001 — रेघ फक्त माहिती
            print(f"⚠️ {sym} line facts: {type(exc).__name__}: {exc}")
    try:
        from engine3_live import tradeable_levels
        lv = tradeable_levels(levels) if levels else None
    except Exception:                                                      # noqa: BLE001
        lv = None
    f = PC.facts(ctx, last, ar, lv, (line or {}).get("tags"))
    ok = True
    if chart_fn is not None and ctx.get("ok") and last is not None:
        try:
            ok = bool(chart_fn(sym, f, wk, line))
        except Exception as exc:                                           # noqa: BLE001 — chart कधीच संदेश थांबवत नाही
            print(f"⚠️ {sym} pre-open charts: {type(exc).__name__}: {exc}")
            ok = False
    return PC.lines(sym, ctx, wk, last, f, na=na, chart_ok=ok)


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
    ap.add_argument("--symbols", default=None, help="default: dashboard signal_symbols (त्या यादीबाहेरचे वगळले)")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="फक्त छाप — Telegram ला पाठवत नाही (--no-telegram सारखंच)")
    ap.add_argument("--no-charts", action="store_true", help="charts बनवत नाही (crux setting प्रमाणे राहतो)")
    ap.add_argument("--charts-dir", default=None, help="charts PNG इथे सुद्धा जतन करा (review)")
    a = ap.parse_args(argv)
    import cloud_db
    token = cloud_db.get_effective_upstox_token(None)
    problems = []
    if not token:
        print("❌ Upstox token नाही — आधी daily login करा. Trend काढता येत नाही ⇒ bots नवे entries घेणार नाहीत (fail-closed).")
        problems.append("❌ Upstox login missing — no price data, so no trend and no new entries until you log in.")
    allowed = cloud_db.get_signal_symbols()                                # dashboard setting (वाचता नाही ⇒ default NIFTY / BANKNIFTY)
    want = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] if a.symbols else allowed
    syms = [s for s in dict.fromkeys(want) if s in allowed]
    for s_ in dict.fromkeys(want):
        if s_ not in allowed:
            print(f"⏭️ {s_}: signal_symbols ({' / '.join(allowed)}) मध्ये नाही ⇒ pre-open ओळ नाही")
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
    feed, views, pngs = {}, {}, {}

    def engine_areas(sym):
        """engine (decision3) चे शेवटच्या बंद 15M bar चे पट्टे — engine तेच trade करतो. Token नाही / data नाही ⇒ raise (NA + कारण)."""
        import engine3_live as L3
        import engine_signal as ES
        if not token:
            raise L3.EngineDataError("Upstox login missing")
        if "f" not in feed:
            feed["f"] = L3.UpstoxFeed(token, today)
        # Z-1o: live engine सारखाच 1m (engine3_use_1m dashboard setting; OFF ⇒ 1m मागवत नाही) ⇒ pre-open पट्टे = engine चे पट्टे
        if a.no_charts or not PC.setting_for(active, sym):
            return L3.watched_levels(sym, feed["f"], ES._naive(ES.now_ist()), ES.engine3_settings(sym))
        keep = {}                                                          # Abhi (track F): तोच V22 charts साठी (पुन्हा fetch / build नाही)
        out = L3.watched_levels(sym, feed["f"], ES._naive(ES.now_ist()), ES.engine3_settings(sym), keep=keep)
        if keep.get("V") is not None:
            views[sym] = keep["V"]
        return out

    budget = {}

    def chart_fn(sym, f, wk, line):
        """Daily / 1H / 15M PNG (रिटर्न True = तिन्ही तयार). V वापरून झाल्यावर लगेच सोडतो (1 GB VPS). सगळ्या charts साठी एकूण
        CHART_BUDGET_S (पहिल्या chart पासून) — पार ⇒ उरलेले वगळले, संदेश उशिरा नाही."""
        import time
        V = views.pop(sym, None)
        if V is None:
            print(f"⚠️ {sym} pre-open charts: no engine run to draw from (engine areas not available / signal source not engine)")
            return False
        from decision3 import preopen_chart as PCH
        budget.setdefault("deadline", time.monotonic() + CHART_BUDGET_S)
        items, errs = PCH.render(V, sym, f, wk, line, deadline=budget["deadline"])
        del V
        for e in errs:
            print(f"⚠️ {sym} pre-open chart {e}")
        if items:
            pngs[sym] = items
        return bool(items) and not errs

    msg = build_report(syms, token, lambda s: cloud_db.get_market_zones(s), last_close,
                       trend_fn=lambda s: LR.daily_trend(s, token, fetch=lambda tok, sy: daily_df(sy)),
                       weekly_fn=lambda s: weekly_trend(daily_df(s), today), day=today.isoformat(), active=active,
                       problems=problems, engine_cron=engine_cron, engine_areas_fn=engine_areas, views=views,
                       chart_fn=None if a.no_charts else chart_fn)
    views.clear()
    print(msg)
    save_charts(pngs, a.charts_dir)
    if a.no_telegram or a.dry_run:
        return 0
    from notifications import send_telegram_message
    ok = send_checked(msg, send_telegram_message)
    send_charts(pngs)                                                      # संदेशानंतर; अयशस्वी ⇒ फक्त log (exit code संदेशाचाच)
    return 0 if ok else 1


def save_charts(pngs, out_dir=None):
    """charts ची नोंद (stdout) + out_dir दिलं ⇒ PNG जतन. कधीच raise नाही."""
    for sym, items in (pngs or {}).items():
        print(f"🖼️ {sym} charts: " + ", ".join(f"{tf} {len(b) // 1024} KB" for tf, b, _ in items))
        if not out_dir:
            continue
        try:
            os.makedirs(out_dir, exist_ok=True)
            for tf, b, _ in items:
                with open(os.path.join(out_dir, f"{sym}_{tf}.png"), "wb") as fh:
                    fh.write(b)
        except Exception as exc:                                           # noqa: BLE001
            print(f"⚠️ charts not saved: {type(exc).__name__}: {exc}")


def send_charts(pngs, send=None):
    """प्रत्येक symbol ⇒ एक media group (Daily / 1H / 15M). अयशस्वी / त्रुटी ⇒ फक्त log — संदेश / engine / bots / exits ला हात नाही."""
    if not pngs:
        return {}
    out = {}
    try:
        if send is None:
            from notifications import send_telegram_media_group as send
    except Exception as exc:                                               # noqa: BLE001
        print(f"⚠️ pre-open charts not sent: {type(exc).__name__}: {exc}")
        return {s: False for s in pngs}
    for sym, items in pngs.items():
        try:
            out[sym] = send([(b, cap) for _, b, cap in items]) is not False
        except Exception as exc:                                           # noqa: BLE001
            print(f"⚠️ {sym} pre-open charts: {type(exc).__name__}: {exc}")
            out[sym] = False
        print(("✅" if out[sym] else "❌") + f" {sym} pre-open charts " + ("sent" if out[sym] else "NOT sent (text message already sent)"))
    return out


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
