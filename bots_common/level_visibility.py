"""bots_common/level_visibility.py — L5 (Abhi §5 Visibility): level bots चे आजचे areas + gate अवस्था (dashboard) आणि bot-निहाय दैनिक
सारांश (15:45 Telegram). फक्त वाचन: signal_log rows (cloud_db.get_signal_log — bots `SKIPPED_GATE_*` + "[GATE] …" लिहितात), paper_would_have
(`<bot>_touch_legacy`) आणि trend cache file (data/level_gate/trend_<SYM>_<day>.json). Order / settings / network ला हात नाही.

signal_log मध्ये bot column नाही ⇒ bot level_type + symbol वरून ओळखतो:
  5M Instant = DYNAMIC_SR_*_1M / _5M · Classic = DYNAMIC_SR_*_5M / _15M · साधा "SUPPORT" / "RESISTANCE" = index symbol ⇒ 15M SRv2,
  MCX symbol ⇒ MCX Futures (L4). 5M levels दोन्ही bots चे एकाच rows मध्ये (save_signal_log चा dedupe level वर, bot वर नाही) ⇒ सारांशात
  वेगळा "5M levels (Instant + Classic)" गट (दुहेरी मोजणी नाही); dashboard वर दोन्ही bots खाली दिसतात (caption मध्ये सांगितलं).
Confirmed hit_type: srv2 / Classic "CONFIRMATION", 5M Instant / MCX "CONFIRMED" — दोन्ही.
"""
import glob
import html
import json
import os
import re
from collections import Counter

import pandas as pd

from . import level_reaction as LR

SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
MCX_SYMBOLS = ("CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER")       # page_mcx_futures.MCX_SYMBOLS सारखेच
CONFIRMED_HITS = ("CONFIRMATION", "CONFIRMED")
PLAIN = "PLAIN"                                                            # TF नसलेला level_type (SRv2 / MCX)
BOT_TFS = {"1m_instant": ("1M", "5M"), "classic_sr_reversal": ("5M", "15M"), "15m_dynamic_sr": None, "mcx_futures": None}
BOT_TF_MIN = {"1m_instant": 5, "classic_sr_reversal": 5, "15m_dynamic_sr": 15, "mcx_futures": 15}   # confirmation TF (default)
TOUCH_SRC = {"1m_instant": "dynamic_sr_instant", "classic_sr_reversal": "classic_sr_reversal", "15m_dynamic_sr": "srv2_momentum_reversal",
             "mcx_futures": "mcx_futures"}
# सारांशाचे गट: (label, level TFs — None ⇒ साधा SUPPORT / RESISTANCE, market)
GROUPS = (("5M Instant (1M levels)", ("1M",), "index"), ("5M levels (Instant + Classic, एकत्र rows)", ("5M",), "index"),
          ("Classic (15M levels)", ("15M",), "index"), ("15M SRv2", None, "index"), ("MCX Futures (15M)", None, "mcx"))

CAT = {"SKIPPED_GATE_WAITING_COMMITMENT": "waiting", "SKIPPED_GATE_ABSORPTION": "absorption", "SKIPPED_GATE_LOW_VOLUME": "low_volume",
       "SKIPPED_GATE_ALREADY_CONFIRMED": "confirmed_earlier", "SKIPPED_GATE_AGAINST_TREND": "against_trend",
       "SKIPPED_GATE_NO_TREND": "trend_unclear", "SKIPPED_GATE_IMPULSIVE": "impulsive", "SKIPPED_GATE_BROKEN": "broken",
       "SKIPPED_GATE_TIMEOUT": "timeout", "SKIPPED_GATE_RR": "rr", "SKIPPED_GATE_NO_TARGET": "no_target", "SKIPPED_GATE_ERROR": "error",
       "SKIPPED_GATE_INVALID_SL": "invalid_sl",                          # SL entry च्या चुकीच्या बाजूला (R:R-निरपेक्ष guard)
       "SKIPPED_GATE_NOT_AT_AREA": "idle",
       "SKIPPED_GATE_FIRST_BAR_PENDING": "first_bar",                   # today's first candle not closed yet — a wait, never an error
       # MCX (L4): CONFIRMED नंतर entry भावावर पुन्हा तपासणी — Abhi RR1 नंतर फक्त जुन्या rows साठी (आता dashboard SL / target)
       "SKIPPED_GATE_INVALIDATED": "invalidated", "SKIPPED_GATE_TARGET_PASSED": "target_passed", "SKIPPED_GATE_SL_TOO_WIDE": "sl_too_wide",
       "SKIPPED_GATE_CONFIRM_USED": "confirm_used"}
IDLE_CATS = ("idle", "first_bar")                                         # nothing read at the area ⇒ a visit boundary
POST_CONFIRM = ("invalidated", "target_passed", "sl_too_wide", "rr")       # confirmed पण gate ने entry थांबवली ⇒ ignored (शेवटचं कारण)
ARMED_CATS = ("waiting", "absorption", "low_volume")                     # ARMED चालू
EPISODE = ARMED_CATS + ("confirmed", "confirmed_earlier", "impulsive", "timeout", "rr", "no_target", "invalid_sl")   # ARMED नंतरच येणाऱ्या अवस्था
IGNORED = {"against_trend": "against trend", "trend_unclear": "trend unclear", "impulsive": "impulsive", "no_commitment": "no commitment",
           "broken": "broken", "timeout": "timeout", "rr": "R:R < min", "no_target": "no target", "invalid_sl": "invalid SL", "low_volume": "low volume",
           "absorption": "absorption", "error": "error", "invalidated": "invalidated", "target_passed": "target passed",
           "sl_too_wide": "SL too wide"}
STATE_LABEL = {"waiting": "🟡 armed — commitment ची वाट", "absorption": "🟠 armed — absorption", "low_volume": "🟠 armed — low-volume commitment",
               "confirmed": "✅ confirmed", "confirmed_earlier": "✅ confirmed (आधी)", "against_trend": "⛔ against trend",
               "trend_unclear": "⛔ trend unclear", "impulsive": "⛔ impulsive approach", "broken": "💥 broken", "timeout": "⌛ timeout",
               "rr": "⛔ R:R < min", "no_target": "⛔ no target", "invalid_sl": "⛔ invalid SL", "error": "⚠️ gate error", "idle": "⚪ price not at area",
               "first_bar": "⚪ waiting for today's first closed candle",
               "invalidated": "⛔ invalidated", "target_passed": "⛔ target passed", "sl_too_wide": "⛔ SL too wide",
               "confirm_used": "✅ confirmation वापरली"}
_ORDER = {c: i for i, c in enumerate(("waiting", "absorption", "low_volume", "confirmed", "confirmed_earlier", "confirm_used", "impulsive",
                                      "timeout", "rr", "no_target", "invalid_sl", "invalidated", "target_passed", "sl_too_wide", "broken", "against_trend",
                                      "trend_unclear", "error", "idle", "first_bar"))}
_BARS = re.compile(r"(\d+)/(\d+) bars")


def level_tf(level_type):
    """level_type ⇒ "1M" / "5M" / "15M" … (DYNAMIC_SR_*), PLAIN (साधा SUPPORT / RESISTANCE — SRv2 / MCX) किंवा None."""
    t = str(level_type or "")
    if t.startswith("DYNAMIC_SR_"):
        return t.rsplit("_", 1)[-1]
    return PLAIN if t in ("SUPPORT", "RESISTANCE") else None


def market(symbol):
    return "mcx" if str(symbol or "").upper() in MCX_SYMBOLS else "index"


def bot_matches(level_type, strategy_key, symbol=None):
    """साधा SUPPORT / RESISTANCE: MCX symbol ⇒ mcx_futures, नाहीतर 15M SRv2 (दोघे एकमेकांचे rows वाचत नाहीत)."""
    tfs, tf = BOT_TFS.get(strategy_key, ()), level_tf(level_type)
    if tfs is None:
        return tf == PLAIN and market(symbol) == ("mcx" if strategy_key == "mcx_futures" else "index")
    return tf in (tfs or ()) and market(symbol) == "index"


def category(row):
    """एका signal_log row ची gate अवस्था (वरचे CAT) किंवा "confirmed" (hit_type CONFIRMATION / CONFIRMED); gate ची नसेल ⇒ None."""
    if str(row.get("hit_type") or "") in CONFIRMED_HITS:
        return "confirmed"
    return CAT.get(str(row.get("trade_status") or ""))


def _records(rows):
    if rows is None:
        return []
    if isinstance(rows, pd.DataFrame):
        return rows.to_dict("records")
    return [dict(r) for r in rows]


def _ts(x):
    try:
        t = pd.Timestamp(x)
        if pd.isna(t):
            return None
        return t.tz_convert("Asia/Kolkata").tz_localize(None) if t.tzinfo else t
    except (TypeError, ValueError):
        return None


def _key(r):
    """एक area = (symbol, TF, किंमत) — role (SUPPORT / RESISTANCE) नाही: area च्या आत hysteresis ने role उलटला तरी तीच भेट."""
    try:
        p = round(float(r.get("level_price")), 2)
    except (TypeError, ValueError):
        p = r.get("level_price")
    return str(r.get("symbol") or ""), level_tf(r.get("level_type")), p


def _visits(items):
    """एका area च्या (वेळेनुसार) gate rows ⇒ भेटी. सीमा: "price not at area" row, किंवा "broken" नंतर पुन्हा armed / confirmed (flip retest)."""
    out, cur, prev = [], None, None
    for _, c, r in items:
        if c in IDLE_CATS:
            if cur:
                out.append(cur)
            cur, prev = None, c
            continue
        if cur is not None and prev == "broken" and c in ARMED_CATS + ("confirmed",):
            out.append(cur)
            cur = None
        if cur is None:
            cur = {"cats": [], "statuses": []}
        cur["cats"].append(c)
        if c == "confirmed":
            cur["statuses"].append(str(r.get("trade_status") or "—"))
        prev = c
    if cur:
        out.append(cur)
    return out


def summarize(rows):
    """एका गटाचे gate rows ⇒ {armed, confirmed, ignored: Counter, entry_statuses: Counter}. प्रत्येक area च्या भेटी (_visits):
    armed = ARMED-नंतरची कुठलीही अवस्था असलेल्या भेटी; confirmed = CONFIRMED / ALREADY_CONFIRMED असलेल्या (entry_statuses = त्या भेटीचा
    entry निकाल: पहिला खरा order status, नाहीतर शेवटचा); ignored = entry शिवाय संपलेल्या भेटीचं **शेवटचं** कारण ("waiting" ⇒ no commitment;
    मधले absorption / low volume नंतर confirmed झाले तर मोजत नाही). MCX: confirmed पण entry ला gate ने थांबवलं (आता फक्त dashboard R:R gate चालू असेल तर "R:R < min"; जुन्या rows मध्ये SL too wide …) ⇒ ते कारण."""
    out = {"armed": 0, "confirmed": 0, "ignored": Counter(), "entry_statuses": Counter()}
    by = {}
    for i, r in enumerate(_records(rows)):
        c = category(r)
        if c is not None:
            by.setdefault(_key(r), []).append((_ts(r.get("signal_time")) or pd.Timestamp.min, i, c, r))
    for items in by.values():
        items.sort(key=lambda x: (x[0], x[1]))
        for v in _visits([x[1:] for x in items]):
            cats, sts = v["cats"], v["statuses"]
            if any(c in EPISODE for c in cats):
                out["armed"] += 1
            if "confirmed" in cats or "confirmed_earlier" in cats:
                out["confirmed"] += 1
                entry = next((s for s in sts if not s.startswith("SKIPPED") and s != "—"), sts[-1] if sts else "(confirmed row नाही)")
                out["entry_statuses"][entry] += 1
                post = [CAT.get(s) for s in sts]
                if sts and all(p in POST_CONFIRM for p in post):
                    out["ignored"][post[-1]] += 1
                continue
            last = "no_commitment" if cats[-1] == "waiting" else cats[-1]
            if last in IGNORED:
                out["ignored"][last] += 1
    return out


def group_rows(rows, tfs, mkt="index"):
    """tfs = level TFs (उदा. ("1M",)) किंवा None (साधा SUPPORT / RESISTANCE); mkt = "index" / "mcx" (symbol वरून)."""
    want = (PLAIN,) if tfs is None else tuple(tfs)
    return [r for r in _records(rows) if level_tf(r.get("level_type")) in want and market(r.get("symbol")) == mkt]


def fetch_rows(day, symbols=SYMBOLS, get_log=None):
    """आजचे signal_log rows (symbol column जोडून) ⇒ (rows, None) किंवा (None, कारण). कुठलाही symbol वाचता आला नाही ⇒ संपूर्ण NA (अपूर्ण आकडे नकोत)."""
    try:
        if get_log is None:
            import cloud_db
            get_log = cloud_db.get_signal_log
        out = []
        for sym in symbols:
            df = get_log(sym, str(day))
            if df is None:
                return None, f"signal log {sym} वाचता आला नाही (DB नाही / त्रुटी)"
            for r in _records(df):
                r["symbol"] = sym
                out.append(r)
        return out, None
    except Exception as exc:                                               # noqa: BLE001 — सारांशाचा बाकी भाग तरी जावा
        return None, f"{type(exc).__name__}: {str(exc)[:80]}"


def mcx_symbols(get_settings=None):
    """MCX bot चे सक्रिय (symbol_enabled) commodities — फक्त settings वाचन. त्रुटी ⇒ ()."""
    try:
        if get_settings is None:
            import cloud_db
            get_settings = cloud_db.get_strategy_settings
        return tuple(s for s in MCX_SYMBOLS if (get_settings("mcx_futures", s) or {}).get("symbol_enabled"))
    except Exception:                                                      # noqa: BLE001
        return ()


def touch_legacy_counts(day, wh_rows=None, jpath=None):
    """paper_would_have मधले आजचे `<bot>_touch_legacy` (dry-run वगळून) ⇒ Counter(bot). अपयश ⇒ exception (caller NA लिहितो)."""
    if wh_rows is None:
        from paper import journal as PJ
        wh_rows = PJ.would_have_rows(jpath)
    return Counter(str(w.get("bot")) for w in wh_rows
                   if str(w.get("bot") or "").endswith("_touch_legacy") and str(w.get("ts") or "")[:10] == str(day) and not w.get("dry_run"))


def _fmt_counter(c, labels=None):
    items = sorted(((labels or {}).get(k, k), v) for k, v in c.items() if v)
    return ", ".join(f"{html.escape(str(k))} {v}" for k, v in sorted(items, key=lambda x: -x[1])) or "—"


def _group_lines(rows, mkt):
    out = []
    for label, tfs, m in GROUPS:
        if m != mkt:
            continue
        s = summarize(group_rows(rows, tfs, mkt))
        conf = f"confirmed {s['confirmed']}" + (f" ({_fmt_counter(s['entry_statuses'])})" if s["confirmed"] else "")
        out.append(f"• {html.escape(label)}: armed {s['armed']} · {conf} · ignored {sum(s['ignored'].values())}: "
                   f"{_fmt_counter(s['ignored'], IGNORED)}")
    return out


def summary_text(day, symbols=SYMBOLS, get_log=None, wh_rows=None, jpath=None, mcx=None):
    """15:45 सारांशाचा "Level bots" भाग (HTML). कधीच raise करत नाही: DB त्रुटी ⇒ "NA (कारण)", बाकी ओळी तशाच. mcx = MCX symbols
    (None ⇒ MCX bot चे सक्रिय)."""
    mcx = mcx_symbols() if mcx is None else tuple(mcx)
    lines = [f"🎯 <b>Level bots — confirmation gate</b> ({'/'.join(tuple(symbols) + mcx)})"]
    for mkt, syms in (("index", tuple(symbols)), ("mcx", mcx)):
        if mkt == "mcx" and not syms:
            lines.append("• MCX Futures: कुठलाही commodity सक्रिय नाही")
            continue
        try:
            rows, err = fetch_rows(day, syms, get_log)
            lines += [f"• {'MCX ' if mkt == 'mcx' else ''}gate आकडे: NA ({html.escape(err)})"] if err else _group_lines(rows, mkt)
        except Exception as exc:                                           # noqa: BLE001
            lines.append(f"• gate आकडे: NA ({html.escape(type(exc).__name__)}: {html.escape(str(exc)[:80])})")
    try:
        tl = touch_legacy_counts(day, wh_rows, jpath)
        lines.append("👻 touch-legacy would-have: " + " · ".join(
            f"{lbl} {tl.get(TOUCH_SRC[k] + '_touch_legacy', 0)}" for lbl, k in (("Instant", "1m_instant"), ("Classic", "classic_sr_reversal"),
                                                                                ("SRv2", "15m_dynamic_sr"), ("MCX", "mcx_futures"))))
    except Exception as exc:                                               # noqa: BLE001
        lines.append(f"👻 touch-legacy would-have: NA ({html.escape(type(exc).__name__)}: {html.escape(str(exc)[:80])})")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ dashboard
def area_table(rows, strategy_key, now=None, tf_minutes=None, include_idle=True, symbol=None):
    """Dashboard table (pure): त्या bot चे आजचे gate rows ⇒ प्रत्येक area (symbol, TF, किंमत) ची सर्वात नवी अवस्था. ARMED आधी, मग confirmed,
    disarmed, idle. "k/N bars" signal_log मध्ये पहिल्या ARMED नोंदीचाच राहतो (dedupe reason बघत नाही) ⇒ now दिला तर नोंदीच्या वेळेवरून
    "~k/N bars" अंदाज. symbol = rows मध्ये symbol column नसेल तर (dashboard: एकाच symbol चा log)."""
    tf = int(tf_minutes or BOT_TF_MIN.get(strategy_key, 5))
    now = _ts(now) if now is not None else None
    latest = {}
    for r in _records(rows):
        if symbol is not None and not r.get("symbol"):
            r["symbol"] = symbol
        c = category(r)
        if c is None or not bot_matches(r.get("level_type"), strategy_key, r.get("symbol")):
            continue
        t = _ts(r.get("signal_time"))
        k = _key(r)
        if k not in latest or (t or pd.Timestamp.min) >= (latest[k][0] or pd.Timestamp.min):
            latest[k] = (t, c, r)
    out = []
    for (sym, ltf, price), (t, c, r) in latest.items():
        if c in IDLE_CATS and not include_idle:
            continue
        line = str(r.get("reason") or "")
        line = line[len("[GATE]"):].strip() if line.startswith("[GATE]") else line
        m = _BARS.search(line)
        if c in ARMED_CATS and m and now is not None and t is not None:
            k_, n_ = int(m.group(1)), int(m.group(2))
            est = min(n_, k_ + max(0, int((now - t).total_seconds() // (tf * 60))))
            line = line[:m.start()] + f"~{est}/{n_} bars" + line[m.end():]
        lt = str(r.get("level_type") or "")
        role = "SUPPORT" if "SUPPORT" in lt else ("RESISTANCE" if "RESISTANCE" in lt else lt)
        px = f"{price:,.2f}" if isinstance(price, (int, float)) else str(price)
        out.append({"Level": f"{'' if ltf == PLAIN else str(ltf) + ' '}{role} {px}", "State": STATE_LABEL.get(c, c),
                    "Gate": line or str(r.get("trade_status") or ""), "Since": t.strftime("%H:%M") if t is not None else "",
                    "Status": str(r.get("trade_status") or ""), "_o": _ORDER.get(c, 99),
                    "_p": price if isinstance(price, (int, float)) else 0.0})
    out.sort(key=lambda x: (x["_o"], -x["_p"]))
    for x in out:
        x.pop("_o")
        x.pop("_p")
    return out


def trend_from_cache(symbol, day, cache_dir=None, allow_parent=False, contract=False):
    """आजची trend अवस्था — फक्त cache files (LR._cache_path) वाचून; network नाही. यशस्वी cache आधी, मग negative ("_fail") cache (ok False).
    contract=True (MCX): cache key = contract चं trading_symbol ("<NAME> FUT <DD> <MON> <YY>") ⇒ त्या नावाच्या files पण (सर्वात नवी)."""
    key = str(day) + ("_a1" if allow_parent else "")
    for suf in (key, key + "_fail"):
        p = LR._cache_path(symbol, suf, cache_dir)
        paths = [p]
        if contract:
            pat = os.path.join(glob.escape(os.path.dirname(p)), f"trend_{glob.escape(symbol)} FUT *_{suf}.json")
            paths += sorted(glob.glob(pat), key=os.path.getmtime, reverse=True)
        for q in paths:
            try:
                with open(q, encoding="utf-8") as f:
                    c = json.load(f)
            except (OSError, ValueError):
                continue
            if suf.endswith("_fail"):
                c = {**(c.get("ctx") or {}), "ok": False, "sides": []}
            return c
    return None


def trend_text(ctx):
    if not ctx:
        return ""
    sides = ctx.get("sides") or []
    allowed = " / ".join("bullish (demand)" if s == LR.BULL else "bearish (supply)" for s in sorted(sides))
    txt = f"{ctx.get('reason')}" + (f" · as of {ctx['asof']}" if ctx.get("asof") else "")
    if ctx.get("protected") is not None:
        txt += f" · protected {float(ctx['protected']):,.0f}"
    return txt + (f" · entries: {allowed}" if ctx.get("ok") and allowed else " · ⛔ NO NEW ENTRIES (fail-closed)")
