"""opportunity_engine/detectors/trendline.py — D4 TRENDLINE_3RD_TOUCH आणि D5 TRENDLINE_BREAK_RETEST (spec §4). कुठलाही indicator नाही.

🎓 Line (`patterns.find_trendline`, 1H बंद bars, `bars_by_tf["hist"]` मधून — no-lookahead): दोन confirmed swings A < B (≥ 5 bars अंतर),
|slope| ≤ 0.5 × ref_range(1H) प्रति bar, A पासून शेवटच्या बंद 1H bar पर्यंत एकही close line पलीकडे नाही. Line चं आत्ताचं मूल्य = चालू (अपूर्ण)
1H bar च्या x वर projection. Touch सहनशीलता = max(0.1% × किंमत, 0.25 × ref_range(1H)).

D4 (long; short आरशात): primary HTF UPTREND ⇒ swing lows वरची वाढती support line; line वर आधीचे touches (anchors सकट) 2 ⇒ आत्ताचा तिसरा,
  3 ⇒ चौथा (कमी quality), जास्त ⇒ नाही.
  • Touch: शेवटच्या `d4_touch_bars` 5M bars चा low line ± tol मध्ये, आणि त्यांचे सर्व closes line च्या वर.
  • Trigger: 5M reversal candle (D6 प्रमाणेच — BULLISH_ENGULFING/HAMMER/MORNING_STAR) आणि पुढचा 5M close त्या candle च्या high वर.
  • SL: line − 0.25 × ref_range(1H) आणि touch low — जे खाली (जास्त सुरक्षित). Target hint: A–B मधला सर्वोच्च high.
  • Quality: तिसरा touch +10 (चौथा +5), line ची लांबी (≤10), touch candle वर wick-rejection (+5), line + HTF zone confluence (+10).
D5 (long; short आरशात): primary HTF UPTREND मधल्या pullback ची **घटती** resistance line (swing highs, ≥ 3 touches).
  • Break: नुकताच बंद झालेला 15M bar line वर close (आधीचा 15M आत) आणि §5 breakout validation पास (volume/room शिवाय) — ही entry नाही, फक्त नोंद.
  • Retest: break नंतर `d5_retest_bars` (10 × 15M) मध्ये low line ± tol ला स्पर्श, आणि confirmation candle (close line वर आणि close > open) ⇒ entry.
    line च्या खाली tol पेक्षा जास्त close ⇒ break रद्द.
  • SL: retest low / line पलीकडे. Target hint: entry वरचा शेवटचा 1H swing high (नाहीतर 2R).
"""
import numpy as np
import pandas as pd

from signals import detect_candlestick_pattern, find_swings

from ..context import trend_sign
from ..measures import ref_range
from ..validation import validate_breakout
from .base import Candidate, Detector, KIND_PULLBACK_END, KIND_REVERSAL
from .patterns import find_trendline

HTF_TFS = ("1h", "4h", "1d")


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def _in_window(now, start, end):
    t = pd.Timestamp(now)
    return _hm(start) <= t.hour * 60 + t.minute <= _hm(end)


def htf_frame(bars_by_tf, tf, n, cache_key):
    """(df, rr) — `hist(tf, n)` चे बंद bars आणि त्यांची ref_range; त्याच शेवटच्या bar साठी पुन्हा गणना नको म्हणून state मध्ये cache."""
    hist = bars_by_tf.get("hist")
    if hist is None:
        return None, None
    df = hist(tf, n)
    if df is None or len(df) < 10:
        return None, None
    cache = bars_by_tf["state"].setdefault(cache_key, {})
    last = df["bar_end"].iloc[-1] if "bar_end" in df.columns else len(df)
    if cache.get("last") != last:
        cache.clear()
        cache["last"] = last
        cache["rr"] = ref_range(df)
    return df, cache["rr"]


def cached_line(bars_by_tf, cfg, side, slope_sign, min_touches, cache_key):
    """1H line (global index मध्ये: x = frame चा मूळ index) — 1H bar बदलल्यावरच नव्याने शोध. रिटर्न (df, rr, line, i0) किंवा None."""
    df, rr = htf_frame(bars_by_tf, cfg.tl_tf, cfg.tl_lookback_bars, cache_key)
    if df is None or rr is None or not np.isfinite(rr):
        return None
    cache = bars_by_tf["state"][cache_key]
    k = ("line", side, slope_sign, min_touches)
    if k not in cache:
        cache[k] = find_trendline(df, rr, side, slope_sign, cfg.tl_swing_order, cfg.tl_min_gap, cfg.tl_max_slope_k, tol=cfg.tl_touch_k * rr,
                                  min_touches=min_touches)
    line = cache[k]
    if line is None:
        return None
    return df, rr, line, int(df.index[0])


def line_value(line, i0, x_global):
    """line positional (df मध्ये) — global x वर मूल्य."""
    return line.at(x_global - i0)


def htf_zone_at(ctx, price, sign, pad=0.0):
    kinds = ("DEMAND", "SUPPORT") if sign > 0 else ("SUPPLY", "RESISTANCE")
    for lv in ctx.levels:
        if lv.get("tf") not in HTF_TFS or lv.get("kind") not in kinds or lv.get("status") == "BROKEN" or lv.get("reject_reason"):
            continue
        lo, hi = float(lv.get("outer_low", lv["low"])), float(lv.get("outer_high", lv["high"]))
        if lo - pad <= price <= hi + pad:
            return lv
    return None


def _trig(row, prev, rr, level=None, **extra):
    t = {"open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"]),
         "prev_high": float(prev["high"]), "prev_low": float(prev["low"]), "ref_range": rr, **extra}
    if level is not None:
        t["level"] = float(level)
    return t


class TrendlineThirdTouch(Detector):
    """D4: trend-दिशेच्या 1H trendline ला तिसरा (किंवा चौथा) touch + 5M reversal candle."""
    setup_id = "D4"
    default_kind = KIND_PULLBACK_END

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg = self.cfg
        if not _in_window(now, cfg.d4_window_start, cfg.d4_window_end):
            return []
        df5 = bars_by_tf["5m"]
        if len(df5) < 4:
            return []
        sign = trend_sign(ctx.state_name(cfg.primary_htf))
        if sign == 0:
            return []
        long = sign > 0
        row, prev = df5.iloc[-1], df5.iloc[-2]
        pat = detect_candlestick_pattern(df5.iloc[-4:-1])
        wanted = cfg.d2_patterns_long if long else cfg.d2_patterns_short
        if pat not in wanted or not ((row["close"] > prev["high"]) if long else (row["close"] < prev["low"])):
            return []
        got = cached_line(bars_by_tf, cfg, "support" if long else "resistance", sign, 2, "d4_cache")
        if got is None:
            return []
        df1h, rr1h, line, i0 = got
        nth = line.touches + 1                                  # आत्ताचा touch कितवा (anchors + मधले touches + हा)
        if nth > 4:
            return []                                           # पाचवा+ touch — line जुनी/कमकुवत
        key = (i0 + line.a, i0 + line.b_idx)
        used = bars_by_tf["state"].setdefault("d4_used", set())
        if key in used:
            return []
        L = line_value(line, i0, int(df1h.index[-1]) + 1)
        tol = max(cfg.tl_touch_pct * abs(L), cfg.tl_touch_k * rr1h)
        win = df5.iloc[-cfg.d4_touch_bars:]
        ext = float(win["low"].min()) if long else float(win["high"].max())
        if abs(ext - L) > tol:
            return []
        held = (win["close"] >= L).all() if long else (win["close"] <= L).all()
        if not held:
            return []
        entry = float(row["close"])
        sl_ref = min(L - cfg.tl_touch_k * rr1h, ext) if long else max(L + cfg.tl_touch_k * rr1h, ext)
        if (entry - sl_ref) * sign <= 0:
            return []
        used.add(key)
        tb = win.loc[win["low"].idxmin()] if long else win.loc[win["high"].idxmax()]
        rng = float(tb["high"] - tb["low"])
        wick = (min(tb["open"], tb["close"]) - tb["low"]) if long else (tb["high"] - max(tb["open"], tb["close"]))
        conf = htf_zone_at(ctx, L, sign, pad=tol)
        quality = 50.0 + (10.0 if nth == 3 else 5.0) + min(10.0, (line.b_idx - line.a) / 3.0) + \
            (5.0 if rng > 0 and wick / rng >= 0.5 else 0.0) + (10.0 if conf is not None else 0.0)
        hints = [line.between_ext] if (line.between_ext - entry) * sign > 0 else []
        zone = dict(conf) if conf is not None else {"kind": "TRENDLINE", "low": L - tol, "high": L + tol, "tf": cfg.tl_tf, "quality_grade": "—"}
        return [Candidate(setup_id="D4", direction="LONG" if long else "SHORT", time=now, entry=entry, sl_ref=float(sl_ref), kind=KIND_PULLBACK_END,
                          tf=cfg.tl_tf, trigger_tf="5m", setup_quality=min(quality, 100.0), trigger=_trig(row, prev, bars_by_tf.get("rr5"), pattern=pat),
                          zone=zone, targets_hint=hints,
                          notes=[f"1H {'वाढत्या support' if long else 'घटत्या resistance'} trendline ({line.touches} touches) ला {nth}वा touch "
                                 f"{L:,.0f} वर, 5M {pat}" + (" + HTF zone confluence" if conf is not None else "")],
                          meta={"trendline_overlap": conf is not None, "touch_no": nth, "line_value": L, "line_bars": line.b_idx - line.a, "pattern": pat})]


class TrendlineBreakRetest(Detector):
    """D5: pullback ची counter-trendline trend-दिशेने तुटली, retest वर confirmation ⇒ entry."""
    setup_id = "D5"
    default_kind = KIND_REVERSAL

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg = self.cfg
        if not _in_window(now, cfg.d5_window_start, cfg.d5_window_end):
            return []
        df15 = bars_by_tf["15m"]
        if len(df15) < 2 or pd.Timestamp(df15["bar_end"].iloc[-1]) != pd.Timestamp(now):
            return []                                           # फक्त 15M bar नुकताच बंद झाल्यावर
        rr15 = bars_by_tf.get("rr15")
        if rr15 is None or not np.isfinite(rr15) or rr15 <= 0:
            return []
        sign = trend_sign(ctx.state_name(cfg.primary_htf))
        if sign == 0:
            return []
        long = sign > 0
        mem = bars_by_tf["state"]
        pending, used = mem.setdefault("d5_pending", []), mem.setdefault("d5_used", set())
        k = len(df15) - 1
        row, prev = df15.iloc[-1], df15.iloc[-2]
        cl, op, lo, hi = float(row["close"]), float(row["open"]), float(row["low"]), float(row["high"])
        df1h, _ = htf_frame(bars_by_tf, cfg.tl_tf, cfg.tl_lookback_bars, "d5_cache")
        if df1h is None:
            return []
        x_now = int(df1h.index[-1]) + 1                         # चालू (अपूर्ण) 1H bar चा global x
        got = cached_line(bars_by_tf, cfg, "resistance" if long else "support", -sign, cfg.d5_min_touches, "d5_cache")
        out = []
        for p in list(pending):
            if p["sign"] != sign:
                pending.remove(p)
                continue
            L = p["m"] * x_now + p["b"]
            if k - p["k"] > cfg.d5_retest_bars or (cl - L) * sign < -p["tol"]:
                pending.remove(p)                               # वेळ संपली / line च्या आत परत ⇒ break अपयशी
                continue
            touched = (lo <= L + p["tol"]) if long else (hi >= L - p["tol"])
            confirm = (cl > L and cl > op) if long else (cl < L and cl < op)
            if k > p["k"] and touched and confirm:
                pending.remove(p)
                out.append(self._cand(ctx, row, prev, rr15, L, p, now, sign, df1h, k - p["k"]))
        if got is None:
            return out
        _, rr1h, line, i0 = got
        key = (i0 + line.a, i0 + line.b_idx)
        if key in used:
            return out
        L = line_value(line, i0, x_now)
        if (cl - L) * sign < cfg.val_beyond_k * rr15 or (float(prev["close"]) - L) * sign > 0:
            return out                                          # ताजा close-break नाही
        val = validate_breakout(_trig(row, prev, rr15), "LONG" if long else "SHORT", L, rr15, cfg)
        if not val.passed:
            return out
        used.add(key)
        tol = max(cfg.tl_touch_pct * abs(L), cfg.tl_touch_k * rr1h)
        pending.append({"sign": sign, "k": k, "m": line.m, "b": line.b - line.m * i0, "x": x_now, "tol": tol, "touches": line.touches,
                        "length": line.b_idx - line.a})
        return out

    def _cand(self, ctx, row, prev, rr15, L, p, now, sign, df1h, waited):
        long = sign > 0
        entry = float(row["close"])
        sl_ref = min(float(row["low"]), L) if long else max(float(row["high"]), L)
        hints = []
        sh, sl = find_swings(df1h, order=self.cfg.tl_swing_order)
        pts = [float(df1h["high"].iloc[i]) for i in sh] if long else [float(df1h["low"].iloc[i]) for i in sl]
        ahead = [x for x in pts if (x - entry) * sign > 0]
        if ahead:
            hints.append(min(ahead, key=lambda x: abs(x - entry)))
        conf = htf_zone_at(ctx, L, sign, pad=p["tol"])
        quality = 50.0 + min(10.0, 2.5 * (p["touches"] - 2)) + min(10.0, p["length"] / 4.0) + (10.0 if conf is not None else 0.0)
        zone = dict(conf) if conf is not None else {"kind": "TRENDLINE", "low": L - p["tol"], "high": L + p["tol"], "tf": self.cfg.tl_tf, "quality_grade": "—"}
        return Candidate(setup_id="D5", direction="LONG" if long else "SHORT", time=now, entry=entry, sl_ref=float(sl_ref), kind=KIND_REVERSAL,
                         tf=self.cfg.tl_tf, trigger_tf="15m", setup_quality=min(quality, 100.0), trigger=_trig(row, prev, rr15, level=L), zone=zone,
                         targets_hint=hints,
                         notes=[f"1H pullback trendline ({p['touches']} touches) {'वर' if long else 'खाली'} तुटली, {L:,.0f} ला retest + 15M confirmation"],
                         meta={"trendline_overlap": conf is not None, "line_value": L, "touches": p["touches"], "retest_bars": int(waited)})
