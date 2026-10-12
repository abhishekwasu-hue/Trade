"""bots_common/level_gate_bot.py — level bots मध्ये confirmation gate जोडण्यासाठी पातळ थर (प्रत्येक bot मधला बदल लहान राहावा म्हणून).

वापर (प्रत्येक cycle, प्रत्येक symbol):
    mode = entry_mode(settings)                       # "confirmation" (PAPER default) | "touch" (legacy; LIVE चा mode तसाच)
    if mode == CONFIRMATION:
        g = cycle_gate(bot, symbol, access_token, settings, areas, now)   # एकदा: trend + बंद candles + सगळे areas
        r = g.result(lo, hi)                          # प्रत्येक level: entry? side? reason?
        if not r["entry"]: log_entry.update(skip_fields(r)); save; continue
        direction = r["side"]                         # BULLISH / BEARISH — trend + area बाजू (hysteresis नाही)
Fail-closed: trend / candles / exception ⇒ प्रत्येक area चा result entry=False, कारण नोंदीत; exits ला हात नाही.
"""
import numpy as np
import pandas as pd

from . import level_reaction as LR

CONFIRMATION, TOUCH = "confirmation", "touch"

# Abhi §3: confirmation timeframe (minutes) प्रत्येक bot साठी — dashboard setting `confirm_tf_minutes` ने बदलता येतो
CONFIRM_TF = {"dynamic_sr_instant": 5, "classic_sr": 5, "srv2": 15, "mcx": 15}
_INTERVAL = {1: "1minute", 5: "5minute", 15: "15minute", 30: "30minute"}

STATUS = {                                                                 # signal log trade_status (SKIPPED_* ⇒ dedupe होतात)
    LR.R_AGAINST: "SKIPPED_GATE_AGAINST_TREND", LR.R_NO_TREND: "SKIPPED_GATE_NO_TREND", LR.R_IMPULSIVE: "SKIPPED_GATE_IMPULSIVE",
    LR.R_NO_COMMIT: "SKIPPED_GATE_WAITING_COMMITMENT", LR.R_BROKEN: "SKIPPED_GATE_BROKEN", LR.R_TIMEOUT: "SKIPPED_GATE_TIMEOUT",
    LR.R_RR: "SKIPPED_GATE_RR", LR.R_NO_TARGET: "SKIPPED_GATE_NO_TARGET", LR.R_ERROR: "SKIPPED_GATE_ERROR",
}
ARMED_WHY = {"absorbing": "SKIPPED_GATE_ABSORPTION", "low_volume": "SKIPPED_GATE_LOW_VOLUME"}   # ARMED चालू, पण कारण वेगळं (L5 सारांश)


def entry_mode(settings):
    """settings["entry_mode"] दिला तर तोच; नाहीतर PAPER ⇒ confirmation (नवा default), LIVE / LIVE_PAPER ⇒ touch (Abhi बदलेपर्यंत तसाच)."""
    m = str((settings or {}).get("entry_mode") or "").strip().lower()
    if m in (CONFIRMATION, TOUCH):
        return m
    return CONFIRMATION if str((settings or {}).get("trading_mode", "PAPER")).upper() == "PAPER" else TOUCH


def gate_settings(settings):
    """bot settings मधले gate चे (dashboard) आकडे ⇒ level_reaction settings (नसतील ⇒ defaults)."""
    st = settings or {}
    return LR.settings({k: st.get(f"gate_{k}") for k in LR.DEFAULTS})


def status_of(r):
    why = str(r.get("reason") or "")
    if r.get("state") == LR.ARMED:
        for k, v in ARMED_WHY.items():
            if r.get(k):
                return v
    for k, v in STATUS.items():
        if why.startswith(k):
            return v
    if r.get("state") == LR.ARMED:
        return STATUS[LR.R_NO_COMMIT]
    if r.get("state") == LR.CONFIRMED:
        return "SKIPPED_GATE_ALREADY_CONFIRMED"
    if r.get("state") == "ERROR":
        return STATUS[LR.R_ERROR]
    return "SKIPPED_GATE_NOT_AT_AREA"


def skip_fields(r):
    """signal log साठी: trade_status + reason (कारण Abhi च्या यादीतलं + dashboard ओळ)."""
    return {"trade_status": status_of(r), "reason": f"[GATE] {LR.describe(r)}"}


class CycleGate:
    def __init__(self, ctx, bars, k0, areas, s, err=None):
        self.ctx, self.bars, self.k0, self.areas, self.s, self.err = ctx, bars, k0, list(areas), s, err
        self._cache = {}

    def result(self, lo, hi):
        lo, hi = float(min(lo, hi)), float(max(lo, hi))
        key = (round(lo, 4), round(hi, 4))
        if key in self._cache:
            return self._cache[key]
        if self.err:
            r = {"state": "ERROR", "entry": False, "side": None, "reason": self.err, "events": [], "area": (lo, hi)}
        else:
            others = [a for a in self.areas if (round(min(a), 4), round(max(a), 4)) != key]
            r = LR.safe_evaluate(self.bars, (lo, hi), self.ctx, others, self.k0, s=self.s)
            r.setdefault("area", (lo, hi))
        self._cache[key] = r
        return r


def _area_of(row, pad):
    lo = float(row.get("zone_low"))
    hi = row.get("zone_high")
    hi = float(hi) if hi is not None and pd.notna(hi) else lo
    if hi - lo < pad:                                                      # single-price level ⇒ लहान पट्टा (median range units)
        m = (lo + hi) / 2.0
        lo, hi = m - pad / 2.0, m + pad / 2.0
    return lo, hi


def areas_from_rows(rows, pad=0.0):
    """market_zones rows (zone_low, zone_high) ⇒ [(lo, hi)]."""
    return [_area_of(r, pad) for r in rows]


def _ts_naive(x):
    t = pd.to_datetime(x)
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return t


def attach_futures_volume(bars, symbol, token, tf, now, fetch_volume=None, cache_dir=None):
    """Abhi a2: volume = त्या index चा front futures (NIFTY ⇒ NIFTY FUT, BANKNIFTY ⇒ BANKNIFTY FUT; SENSEX FUT मिळाला नाही ⇒ NA); किंमत spot
    चीच. spot चा volume (0) कधीच वापरत नाही. fetch_volume(token, symbol, minutes) ⇒ futures candles (timestamp, volume). अपयश ⇒ volume NA."""
    if bars is None or len(bars) == 0:
        return bars
    out = bars.copy()
    out["volume"] = np.nan
    try:
        if fetch_volume is None:
            fetch_volume = _default_futures_candles
        fut = LR.call_with_timeout(fetch_volume, (token, symbol, int(tf)), 10.0)   # volume पूरक ⇒ cycle अडकू नये
        if fut is None or len(fut) == 0 or "volume" not in fut.columns:
            return out
        f = pd.DataFrame({"timestamp": _ts_naive(fut["timestamp"]), "fvol": pd.to_numeric(fut["volume"], errors="coerce")})
        m = pd.DataFrame({"timestamp": _ts_naive(out["timestamp"])}).merge(f.drop_duplicates("timestamp"), on="timestamp", how="left")
        out["volume"] = m["fvol"].to_numpy(float)
    except Exception as exc:                                               # noqa: BLE001 — volume NA (grade कमाल B), entry ला अडथळा नाही
        print(f"⚠️ {symbol} futures volume NA: {type(exc).__name__}: {str(exc)[:80]}")
    return out


def _default_futures_candles(token, symbol, minutes, cache_dir=None, lookback_days=5):
    import datetime as _dt
    import json as _json
    import os as _os
    day = _dt.date.today()
    base = cache_dir or _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data", "level_gate")
    p = _os.path.join(base, f"fut_{symbol}_{day.isoformat()}.json")
    cached = None
    try:
        cached = _json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if cached is not None and not cached.get("instrument_key"):
        return None                                                        # आज resolve आधीच अपयशी (उदा. SENSEX) ⇒ NA, पुन्हा network नाही
    key = (cached or {}).get("instrument_key")
    if not key:
        import verify_opportunity_data_availability as V
        info, err = V.resolve_front_future(token, symbol, day)
        key = (info or {}).get("instrument_key")
        try:
            _os.makedirs(base, exist_ok=True)
            _json.dump({"instrument_key": key, "trading_symbol": (info or {}).get("trading_symbol"), "error": err},
                       open(p, "w", encoding="utf-8"), ensure_ascii=False)
        except OSError:
            pass
        if not key:
            return None                                                    # उदा. SENSEX (BSE) ⇒ NA
    from upstox_api import fetch_mcx_candles
    return fetch_mcx_candles(token, key, interval=_INTERVAL.get(int(minutes), "5minute"), lookback_days=lookback_days)


def confirm_tf(bot, settings):
    """settings["confirm_tf_minutes"] (dashboard) — Upstox interval असलेला (1 / 5 / 15 / 30) नसेल तर शांतपणे दुसऱ्या TF चे candles आणून
    चुकीचे "बंद" candles मोजू नयेत ⇒ bot चा default TF (MCX 15) आणि log."""
    default = CONFIRM_TF.get(bot, 5)
    raw = (settings or {}).get("confirm_tf_minutes")
    try:
        tf = int(raw) if raw not in (None, "") else default
    except (TypeError, ValueError):
        tf = None
    if tf not in _INTERVAL:
        print(f"⚠️ {bot}: confirm_tf_minutes={raw!r} चालत नाही (फक्त {sorted(_INTERVAL)}) ⇒ default {default}m")
        tf = default
    return tf


def cycle_gate(bot, symbol, access_token, settings, areas, now, fetch_bars=None, fetch_daily=None, cache_dir=None, fetch_volume=None):
    """एका cycle साठी: trend (दिवसातून एकदा, cache), confirmation-TF चे बंद candles (मागचे काही दिवस median range साठी), सगळे areas."""
    s = gate_settings(settings)
    tf = confirm_tf(bot, settings)
    now = pd.Timestamp(now)
    try:
        ctx = LR.daily_trend(symbol, access_token, today=now.normalize().tz_localize(None) if now.tzinfo else now.normalize(),
                             fetch=fetch_daily, cache_dir=cache_dir, s=s)
        if fetch_bars is None:
            from upstox_api import fetch_candles

            def fetch_bars(tok, sym, minutes):
                return fetch_candles(tok, sym, current_spot=0, interval=_INTERVAL.get(minutes, "5minute"), lookback_days=5)
        raw = fetch_bars(access_token, symbol, tf)
        if raw is None or len(raw) == 0:
            return CycleGate(ctx, None, 0, areas, s, err=f"{LR.R_ERROR}: {tf}m candles मिळाले नाहीत")
        bars = LR.closed_bars(raw, tf, now)
        bars = attach_futures_volume(bars, symbol, access_token, tf, now, fetch_volume)   # a2 / c0: index ⇒ त्याच्या futures चा volume
        k0 = LR.session_start_index(bars, now.tz_localize(None) if now.tzinfo else now)
        if k0 >= len(bars):
            return CycleGate(ctx, bars, k0, areas, s, err="आजचा पहिला बंद candle अजून नाही")
        return CycleGate(ctx, bars, k0, areas, s)
    except Exception as exc:                                               # noqa: BLE001 — fail-closed
        return CycleGate(None, None, 0, areas, s, err=f"{LR.R_ERROR}: {type(exc).__name__}: {str(exc)[:80]}")


def gate_tags(r, ctx=None, tf=None):
    """Vision row tags (§9): caption / approval संदेशात trend, area, commitment form, entry / SL / target, R:R."""
    lo, hi = r.get("area") or (None, None)
    return {"gate": {"mode": CONFIRMATION, "side": r.get("side"), "area": [lo, hi], "form": r.get("form"), "grade": r.get("grade"),
                     "commit_grade": r.get("commit_grade"), "entry": r.get("entry_price"), "sl": r.get("sl"), "target": r.get("target"),
                     "rr": r.get("rr"), "confirm_ts": r.get("confirm_ts"), "arm_ts": r.get("arm_ts"),
                     **{k: r.get(k) for k in ("vol_mult", "vol_na", "vol_trend_mult", "vol_counter_mult", "bar_volumes") if k in r},
                     "trend": (ctx or {}).get("reason"), "tf": tf,
                     "study": r.get("study"), "commit_line": r.get("commit_line"),
                     "evidence": {k: v for k, v in (r.get("evidence") or {}).items() if v is not None}}}


def gate_caption_lines(tags):
    """vision/worker v1_caption साठी (HTML escape caller करतो): gate tags ⇒ 2–3 ओळी. tags मध्ये gate नसेल ⇒ []."""
    g = (tags or {}).get("gate")
    if not g:
        return []
    lo, hi = (g.get("area") or [None, None])[:2]
    kind = "demand" if g.get("side") == LR.BULL else "supply"
    area = f"{lo:,.0f}–{hi:,.0f}" if lo is not None and hi is not None else "?"
    out = [f"🎯 Confirmation: {kind} {area} · grade {g.get('grade')} · trend: {g.get('trend')}"]
    out += [x for x in (g.get("study"), g.get("commit_line")) if x]        # a2 / c0 ticket ओळी
    out.append(f"Entry {g.get('entry')} · SL {g.get('sl')} · target {g.get('target')} · R:R {g.get('rr')}")
    return out


_TOUCH_SEEN = set()


def record_touch_legacy(bot, symbol, direction, level, setup_tf, reason="legacy touch", day=None, journal=None, seen=None):
    """§9: legacy "touch" तुलना ⇒ फक्त paper_would_have (lots 0, bot "<bot>_touch_legacy"); Telegram नाही, position नाही.
    एकाच दिवशी (bot, symbol, level, tf, दिशा) एकदाच (process मध्ये + journal मध्ये तपासून)."""
    try:
        import datetime as _dt
        from zoneinfo import ZoneInfo
        _now = _dt.datetime.now(ZoneInfo("Asia/Kolkata"))                  # VPS clock UTC ⇒ IST वेळ (review ⚪)
        day = day or _now.date().isoformat()
        key = (bot, str(symbol).upper(), round(float(level), 2), setup_tf, direction, day)
        seen = _TOUCH_SEEN if seen is None else seen
        if key in seen:
            return False
        if journal is None:
            from paper import journal as journal
        src = f"{bot}_touch_legacy"
        for x in journal.would_have_rows():
            if (x.get("bot") == src and str(x.get("symbol")).upper() == key[1] and str(x.get("ts", ""))[:10] == day
                    and x.get("setup_tf") == setup_tf and x.get("direction") == direction
                    and x.get("level") is not None and abs(float(x["level"]) - key[2]) < 1e-6):
                seen.add(key)
                return False
        journal.would_have({"ts": f"{day} {_now.strftime('%H:%M:%S')}", "bot": src, "symbol": key[1], "direction": direction,
                            "level": key[2], "setup_tf": setup_tf, "status": "TOUCH_LEGACY", "reason": str(reason)[:200],
                            "signal_id": None, "orig_lots": 0, "orig_naked_lots": 0, "dry_run": 0})
        seen.add(key)
        return True
    except Exception as exc:                                               # noqa: BLE001 — तुलनेची नोंद trade ला अडवत नाही
        print(f"⚠️ touch_legacy would-have नोंद: {exc}")
        return False


def conf_gate_enabled(settings, name):
    """Confirmation mode मध्ये RSI threshold / PCR gate (name = "rsi" / "pcr"): default बंद (Abhi §4). जुने `entry_rsi_gate_enabled` /
    `entry_pcr_gate_enabled` touch mode चे आहेत (DB defaults मध्ये True) ⇒ इथे वेगळी keys: `conf_rsi_gate_enabled` / `conf_pcr_gate_enabled`."""
    return bool((settings or {}).get(f"conf_{name}_gate_enabled", False))


AREA_PAD_PCT = 0.05   # DB मधला single-price level ⇒ gate area = level ± (इतके % ÷ 2); सगळ्या bots साठी एकच (setting `gate_area_pad_pct`, OPEN_QUESTIONS LB4)
