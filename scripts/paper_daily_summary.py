#!/usr/bin/env python3
"""🗓 PAPER दिवस-सारांश (Abhi §10e, 15:45 IST) ⇒ **एकच** Telegram संदेश, साध्या शब्दांत (Abhi, TELEGRAM_CLEANUP 1c / 4):

  ओळ 1  साधी (काय पाहायचं) · "Decision needed: none — information"
  symbol-निहाय एक ओळ (NIFTY / BANKNIFTY / SENSEX): setup झाला का, Daily trend, किंमत trade-बाजूच्या area पर्यंत पोचली का (gate नोंदी:
        armed / confirmed / ignored कारण), दिवसाच्या high / low पासून जवळचा trade-बाजूचा area (points), impulse mature ⇒ cap engine च्याच नियमाने (रचना अखंड ⇒ कमाल B, नाहीतर weak) / origin जवळ ⇒ weak.
        एखादा भाग मिळाला नाही ⇒ तसं स्पष्ट ("no data today …").
  तुमचे निर्णय (approvals / ✏️ / ❌ कारणानुसार / उत्तर नाही) + approved trades चा net P&L + would-have + 📝 corrections (साधे शब्द).
  "── details ──" खाली level bots चा gate सारांश (L5 §5: armed / confirmed / ignored कारणानुसार, MCX, touch-legacy) — जुना तपशील.
फक्त वाचन (vision.db + paper journal + signal_log + market_zones + trend cache; दिवसाचा high / low ⇒ Upstox 15M candles, फक्त VPS वर
token असल्यास) — order / settings / engine निर्णयाला हात नाही. Dry-run नोंदी वगळून.

VPS cron (VPS ची वेळ UTC ⇒ 15:45 IST = 10:15 UTC; crontab या script मधून बदलत नाही — Abhi स्वतः जोडतो):
  15 10 * * 1-5  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_daily_summary.py >> paper_daily_summary.log 2>&1
"""
import argparse
import html
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TG_MAX = 4096                                                              # Telegram एका संदेशाची कमाल लांबी
SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
AREA_TFS = ("1M", "5M", "15M", "30M", "60M")                               # level bots जे areas पाहतात (preopen सारखेच)
WHY_PLAIN = {"no_commitment": "no strong candle closed out of the area", "impulsive": "price ran into the area too fast",
             "rr": "the reward was too small for the risk", "against_trend": "the area was against the trend",
             "trend_unclear": "the trend was unclear", "broken": "price broke through the area", "timeout": "no entry candle in time",
             "low_volume": "the entry candle had low volume", "absorption": "the other side kept absorbing at the area",
             "no_target": "there was no target area in front", "error": "a gate error (no entry, safe side)",
             "invalidated": "the setup was invalidated before entry", "target_passed": "price had already reached the target",
             "sl_too_wide": "the stop was too wide"}


def level_section(day):
    """L5 (Abhi §5): bot-निहाय level gate सारांश (armed / confirmed / ignored कारणानुसार + touch-legacy). कधीच raise नाही ⇒ "NA (कारण)"."""
    try:
        from bots_common import level_visibility as LV
        return LV.summary_text(day)
    except Exception as exc:                                               # noqa: BLE001 — approval सारांश तरी जावा
        return f"🎯 Level bots — confirmation gate: NA ({html.escape(type(exc).__name__)}: {html.escape(str(exc)[:80])})"


def combine(approvals, gate, limit=TG_MAX):
    """एकच संदेश ≤ limit: approvals भाग कधीच कापत नाही; जागा कमी ⇒ gate भाग ओळी-निहाय कापतो (HTML tag अर्धवट राहू नये) + "…"."""
    text = approvals + "\n\n" + gate
    if len(text) <= limit:
        return text
    room = limit - len(approvals) - 2 - len("\n…")
    keep = []
    for ln in gate.split("\n"):
        if len("\n".join(keep + [ln])) > room:
            break
        keep.append(ln)
    return approvals + ("\n\n" + "\n".join(keep) + "\n…" if keep else "")


# ------------------------------------------------------------------------------------------------ symbol-निहाय साधी ओळ
def _areas(zones, ctx):
    """ACTIVE, bot TFs चे areas ⇒ [(lo, hi, zone_type)]."""
    if zones is None or len(zones) == 0:
        return []
    out = []
    for _, z in zones.iterrows():
        zt = str(z.get("zone_type", ""))
        if z.get("status") != "ACTIVE" or not any(zt.endswith(f"_{tf}") for tf in AREA_TFS):
            continue
        lo = float(z["zone_low"])
        hi = float(z["zone_high"]) if z.get("zone_high") is not None else lo
        out.append((min(lo, hi), max(lo, hi), zt))
    return out


def _band(lo, hi, zt):
    from bots_common import plain_text as PT
    tf = PT.tf_word(zt)
    rng = f"{lo:,.0f}" if round(lo) == round(hi) else f"{lo:,.0f}–{hi:,.0f}"
    return rng + (f" ({tf})" if tf else "")


def nearest_area(ctx, zones, rng):
    """दिवसाच्या high / low च्या तुलनेत trade-बाजूचा area: ("inside", kind, lo, hi, zt, 0) — किंमत area मध्ये गेली; ("away", kind, lo, hi,
    zt, अंतर) — सर्वात जवळचा (supply: high च्या वर, demand: low च्या खाली); काहीच नाही ⇒ None."""
    from bots_common import level_reaction as LR
    hi_d, lo_d = float(rng["high"]), float(rng["low"])
    inside, away = [], []
    for lo, hi, zt in _areas(zones, ctx):
        for side in sorted(ctx.get("sides") or ()):
            bull = side == LR.BULL
            if (bull and lo > hi_d) or (not bull and hi < lo_d):          # demand किमतीच्या वर / supply खाली ⇒ त्या बाजूचा नाही
                continue
            if not LR.side_allowed(ctx, side, (lo, hi)):
                continue
            kind = "demand" if bull else "supply"
            if lo <= hi_d and hi >= lo_d:
                inside.append((abs((lo + hi) / 2 - (hi_d + lo_d) / 2), kind, lo, hi, zt))
            else:
                away.append((lo_d - hi if bull else lo - hi_d, kind, lo, hi, zt))
    if inside:
        _, kind, lo, hi, zt = min(inside)
        return "inside", kind, lo, hi, zt, 0.0
    if away:
        d, kind, lo, hi, zt = min(away)
        return "away", kind, lo, hi, zt, d
    return None


def symbol_line(sym, ctx, gate, zones, rng):
    """एका symbol ची साधी ओळ (Abhi चं उदाहरण: "NIFTY: no setup today. Trend DOWN (daily), but price never reached a supply area. Nearest
    supply 22,715–22,776 (≈150 pts above the high). Daily move: mature (context only), near target 22,183.").
    ctx = trend cache (None ⇒ नाही) · gate = LV.summarize निकाल (None ⇒ bot नोंदी वाचता आल्या नाहीत) · rng = {"high", "low"} (None ⇒ नाही)."""
    from bots_common import level_reaction as LR
    from bots_common import plain_text as PT
    if ctx is None and gate is None and rng is None:
        return f"<b>{sym}</b>: no data today (no trend file, bot records and day high / low not available)."
    conf = (gate or {}).get("confirmed", 0)
    armed = (gate or {}).get("armed", 0)
    s = [f"<b>{sym}</b>: " + (f"{conf} setup{'s' if conf != 1 else ''} confirmed today." if conf else "no setup today.")]
    sides = sorted((ctx or {}).get("sides") or ())
    kind = " or ".join("demand" if x == LR.BULL else "supply" for x in sides) or "trade-side"
    if ctx is None:
        s.append("Trend: no trend file for today.")
    elif not ctx.get("ok"):
        s.append(f"No new entries: {PT.unclear_words(ctx)}.")
    else:
        tr = PT.trend_words(ctx).replace("Daily ", "")
        if gate is None:
            s.append(f"Trend {tr} (daily); bot records not available.")
        elif armed == 0:
            s.append(f"Trend {tr} (daily), " + ("and" if conf else "but") + f" price never reached a {kind} area.")
        else:
            why = [WHY_PLAIN.get(k, k) for k, n in sorted((gate.get("ignored") or {}).items(), key=lambda x: -x[1]) if n]
            s.append(f"Trend {tr} (daily). Price reached a {kind} area {armed} time{'s' if armed != 1 else ''}"
                     + (f"; no entry because {', '.join(why[:2])}." if why and not conf else "."))
        if rng is None:
            s.append("Day high / low not available, so no area distance.")
        else:
            near = nearest_area(ctx, zones, rng)
            if near is None:
                s.append(f"No {kind} area on the list near today's range.")
            elif near[0] == "inside":
                s.append(f"Price traded into {near[1]} {_band(*near[2:5])} today.")
            else:
                where = "below the low" if near[1] == "demand" else "above the high"
                tf = PT.tf_word(near[4])
                s.append(f"Nearest {near[1]} {_band(near[2], near[3], '')} ({(tf + ', ') if tf else ''}{PT.pts(near[5])} {where}).")
    if ctx is not None and ctx.get("mature"):
        from bots_common import level_reaction as LR
        tg = [float(x) for x in ctx.get("targets") or []]
        s.append("Daily move: " + LR.mature_words(ctx) + (f", near target {tg[0]:,.0f}" if tg else "") + ".")   # Abhi B1: context only
    elif ctx is not None and ctx.get("ok") and ctx.get("origin_risk"):
        s.append("Context: price is near the trend's starting point.")                   # Abhi B1: context only
    return " ".join(s)


def default_range(sym, day):
    """दिवसाचा high / low (Upstox 15M; फक्त VPS वर token असल्यास). अपयश ⇒ None (ओळ "not available" सांगते)."""
    try:
        import cloud_db
        import pandas as pd
        token = cloud_db.get_effective_upstox_token(None)
        if not token:
            return None
        from upstox_api import fetch_candles
        df = fetch_candles(token, sym, current_spot=0, interval="15minute", lookback_days=5)
        if df is None or len(df) == 0:
            return None
        d = df[pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d") == str(day)]
        return {"high": float(d["high"].max()), "low": float(d["low"].min())} if len(d) else None
    except Exception:                                                      # noqa: BLE001
        return None


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:                                                      # noqa: BLE001 — एक भाग नाही ⇒ ओळ "not available" सांगते
        return None


def symbols_section(day, symbols=SYMBOLS, ctx_fn=None, rows_fn=None, zones_fn=None, range_fn=None):
    """symbol-निहाय साध्या ओळी. प्रत्येक dependency injectable (tests — network नाही); कुठलीही चूक ⇒ त्या भागासाठी "not available".
    rows_fn(sym, day) ⇒ (rows, err) — LV.fetch_rows सारखं; rows रिकामे ⇒ आज कुठलाही area armed नाही (armed 0)."""
    from bots_common import level_visibility as LV
    ctx_fn = ctx_fn or (lambda sym, d: LV.trend_from_cache(sym, d))
    rows_fn = rows_fn or (lambda sym, d: LV.fetch_rows(d, (sym,)))
    if zones_fn is None:
        def zones_fn(sym):
            import cloud_db
            return cloud_db.get_market_zones(sym)
    range_fn = range_fn or default_range
    out = []
    for sym in symbols:
        ctx = _safe(ctx_fn, sym, day)
        rows, err = _safe(rows_fn, sym, day) or (None, "error")
        gate = None if err or rows is None else _safe(LV.summarize, [r for r in rows if LV.market(r.get("symbol") or sym) == "index"])
        zones = _safe(zones_fn, sym) if ctx is not None and ctx.get("ok") else None
        out.append(symbol_line(sym, ctx, gate, zones, _safe(range_fn, sym, day)))
    return "\n".join(out)


def build_text(day, approvals, gate, plain):
    from bots_common import plain_text as PT
    head = (f"🗓 Day summary {day} (15:45, PAPER): what each index did against the bots' areas, and your decisions.\n"
            f"{PT.DECISION_NONE}")
    return combine(f"{head}\n\n{plain}\n\n{approvals}", f"{PT.SEP}\n{gate}")


def main(argv=None, send=None, level=None, plain=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None, help="YYYY-MM-DD (default: आज, IST)")
    ap.add_argument("--print", dest="print_only", action="store_true", help="Telegram नाही, फक्त छाप")
    a = ap.parse_args(argv)
    from vision import approval as AP
    day = a.day or AP.VS.now_ist().strftime("%Y-%m-%d")                     # daily_summary सारखाच दिवस (IST)
    appr = AP.daily_summary_text(a.day)
    try:
        sym = (plain or symbols_section)(day)
    except Exception as exc:                                               # noqa: BLE001 — निर्णय / P&L भाग तरी जावा
        sym = f"Index lines not available ({html.escape(type(exc).__name__)})."
    text = build_text(day, appr, (level or level_section)(day), sym)        # एकाच Telegram संदेशात सगळं (≤ 4096)
    print(text)
    if a.print_only:
        return 0
    if send is None:
        from notifications import send_telegram_message as send
    try:
        ok = send(text)
    except Exception as exc:
        print(f"⚠️ सारांश Telegram वर गेला नाही: {type(exc).__name__}: {exc}")
        return 1
    if ok is False:                                                        # send_telegram_message raise करत नाही, False देतो
        print("⚠️ सारांश Telegram वर गेला नाही (send False)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
