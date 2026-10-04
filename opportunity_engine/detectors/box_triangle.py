"""opportunity_engine/detectors/box_triangle.py — D7 RANGE_BOX_BREAKOUT आणि D8 TRIANGLE_BREAKOUT (spec §4). कुठलाही indicator नाही.

🎓 D7 नियम (5M आणि 15M; 15M फक्त 15M bar नुकताच बंद झाला तेव्हा):
  • Box = breakout bar आधीचे आजचे `box_min_bars`–`box_max_bars` bars, उंची ≤ `box_max_adr × ADR`, वरच्या आणि खालच्या कडेला प्रत्येकी ≥ 2 वेगळे touches
    (`patterns.find_box`, सर्वात लांब पात्र box). 5M वर box नसेल तर Opening Range (पहिले `or_bars`) box म्हणून.
  • Breakout = close box पलीकडे ≥ `box_break_frac × उंची`. दोन्ही दिशा दिसतात — trend-विरुद्ध दिशा gate नाकारतो.
  • Entry: `aggressive` (breakout close) किंवा `retest` (breakout नंतर `d7_retest_bars` मध्ये कडेला परत स्पर्श आणि close पुन्हा बाहेर).
  • SL: box मध्य (`mid`) किंवा विरुद्ध कड (`edge`). T1 = entry ± 1 × box उंची (`meta.t1_hint`), T2 hint = entry ± 2 × उंची (measured move).
  • Quality: 50 + लांबी (≤10) + touches (≤10) + compression (≤10) + box HTF zone वर बसलेला (+10).
  • एकाच TF/दिशेत box पुन्हा वापरला जात नाही: नवीन box पूर्वीच्या breakout bar नंतर सुरू व्हायला हवा.

🎓 D8 नियम (5M आणि 15M): `patterns.find_triangle` — swing highs/lows वर रेषा, ascending/descending/symmetrical, रुंदी ≥ 40% कमी, apex च्या 75% आधी.
  • Breakout = close रेषेपलीकडे (breakout bar वरचं रेषेचं मूल्य). SL: शेवटचा आतला swing (`swing`) किंवा विरुद्ध रेषा (`line`).
  • Target hint = रेषा ± सुरुवातीची रुंदी (measured move). Quality: प्रकार दिशेशी जुळतो (+10; ascending ⇒ long, descending ⇒ short, symmetrical ⇒ primary trend),
    touches (≤10), primary HTF trend त्याच दिशेने (+10).
  • मर्यादा (प्रामाणिकपणे): फक्त आजचे bars पाहतो — 15M वर दिवसात ≤ 25 bars असल्याने मोठे triangle दिसत नाहीत.
"""
import numpy as np
import pandas as pd

from ..context import trend_sign
from .base import Candidate, Detector, KIND_BREAKOUT
from .patterns import find_box, find_triangle, or_box


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def _minutes(ts):
    t = pd.Timestamp(ts)
    return t.hour * 60 + t.minute


def _in_window(now, start, end):
    m = _minutes(now)
    return _hm(start) <= m <= _hm(end)


def pattern_frames(bars_by_tf, now, tfs):
    """(tf, df, ref_range) — 5M नेहमी; 15M फक्त त्याचा शेवटचा bar `now` ला बंद झाला असेल तर (नाहीतर तोच breakout 3 वेळा दिसेल)."""
    out = []
    for tf in tfs:
        df = bars_by_tf.get(tf)
        if df is None or len(df) == 0:
            continue
        if tf != "5m" and "bar_end" in df.columns and pd.Timestamp(df["bar_end"].iloc[-1]) != pd.Timestamp(now):
            continue
        out.append((tf, df, bars_by_tf.get("rr5" if tf == "5m" else "rr15")))
    return out


def _htf_zone_under(ctx, price, sign):
    """long: box चा तळ HTF demand/support zone मध्ये (short: box चा माथा supply/resistance मध्ये)? रिटर्न level किंवा None."""
    kinds = ("DEMAND", "SUPPORT") if sign > 0 else ("SUPPLY", "RESISTANCE")
    for lv in ctx.levels:
        if lv.get("tf") not in ("1h", "4h", "1d") or lv.get("kind") not in kinds or lv.get("status") == "BROKEN" or lv.get("reject_reason"):
            continue
        lo, hi = float(lv.get("outer_low", lv["low"])), float(lv.get("outer_high", lv["high"]))
        if lo <= price <= hi:
            return lv
    return None


def _trig(row, prev, rr, level):
    return {"open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"]),
            "prev_high": float(prev["high"]), "prev_low": float(prev["low"]), "ref_range": rr, "level": float(level)}


class RangeBoxBreakout(Detector):
    """D7: घट्ट range box (किंवा OR) चा close-breakout."""
    setup_id = "D7"
    default_kind = KIND_BREAKOUT

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def _box(self, tf, before, adr):
        cfg = self.cfg
        box = find_box(before["high"].to_numpy(float), before["low"].to_numpy(float), adr, cfg.box_min_bars, cfg.box_max_bars, cfg.box_max_adr,
                       cfg.box_touch_frac, cfg.box_min_touches)
        if box is None and tf == "5m":
            box = or_box(before, cfg.or_bars, adr, cfg.box_max_adr)
        return box

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg = self.cfg
        if not _in_window(now, cfg.d7_window_start, cfg.d7_window_end):
            return []
        adr = getattr(ctx, "adr", None)
        if adr is None or not np.isfinite(adr) or adr <= 0:
            return []
        mem = bars_by_tf["state"]
        last = mem.setdefault("d7_last", {})                 # (tf, sign) -> शेवटच्या breakout bar चा index
        pending = mem.setdefault("d7_pending", [])           # retest mode: [{tf, sign, box, k}]
        out = []
        for tf, df, rr in pattern_frames(bars_by_tf, now, cfg.pattern_tfs):
            k = len(df) - 1
            if k < max(cfg.or_bars, 2):
                continue
            row, prev = df.iloc[-1], df.iloc[-2]
            cl = float(row["close"])
            if cfg.d7_entry_mode == "retest":
                out += self._retests(ctx, tf, df, rr, now, pending, last)
            box = self._box(tf, df.iloc[:k], adr)
            if box is None or box.height <= 0:
                continue
            for s in (1, -1):
                if box.start <= last.get((tf, s), -1):
                    continue                                     # हा box (किंवा त्याचा भाग) आधीच फुटून वापरला गेला
                edge = box.top if s > 0 else box.bottom
                if (cl - edge) * s < cfg.box_break_frac * box.height:
                    continue
                last[(tf, s)] = k
                if cfg.d7_entry_mode == "retest":
                    pending.append({"tf": tf, "sign": s, "box": box, "k": k})
                    continue
                out.append(self._cand(ctx, tf, box, s, row, prev, rr, now, adr, retest=False))
        return out

    def _retests(self, ctx, tf, df, rr, now, pending, last):
        cfg = self.cfg
        k = len(df) - 1
        row, prev = df.iloc[-1], df.iloc[-2]
        out = []
        for p in list(pending):
            if p["tf"] != tf:
                continue
            box, s = p["box"], p["sign"]
            edge = box.top if s > 0 else box.bottom
            if k - p["k"] > cfg.d7_retest_bars or (float(row["close"]) - box.mid) * s < 0:
                pending.remove(p)                               # वेळ संपली किंवा box मध्याच्या आत परत — breakout अपयशी
                continue
            touched = (float(row["low"]) <= edge) if s > 0 else (float(row["high"]) >= edge)
            if k > p["k"] and touched and (float(row["close"]) - edge) * s > 0:
                pending.remove(p)
                out.append(self._cand(ctx, tf, box, s, row, prev, rr, now, getattr(ctx, "adr", None), retest=True))
        return out

    def _cand(self, ctx, tf, box, s, row, prev, rr, now, adr, retest):
        cfg = self.cfg
        long = s > 0
        entry = float(row["close"])
        edge = box.top if long else box.bottom
        sl_ref = box.mid if cfg.d7_sl_mode == "mid" else (box.bottom if long else box.top)
        quality = 50.0 + min(10.0, 10.0 * box.bars / max(cfg.box_max_bars, 1)) + min(10.0, 2.5 * max(0, box.touches_top + box.touches_bottom - 2)) + \
            max(0.0, 10.0 * (1.0 - box.height / (cfg.box_max_adr * adr)))
        base = _htf_zone_under(ctx, box.bottom if long else box.top, s)
        if base is not None:
            quality += 10.0
        zone = dict(base) if base is not None else {"kind": "BOX", "low": box.bottom, "high": box.top, "tf": tf, "quality_grade": "—"}
        what = "Opening Range" if box.kind == "OR" else f"{box.bars} bars box"
        return Candidate(setup_id="D7", direction="LONG" if long else "SHORT", time=now, entry=entry, sl_ref=float(sl_ref), kind=KIND_BREAKOUT,
                         tf=tf, trigger_tf=tf, setup_quality=min(quality, 100.0), trigger=_trig(row, prev, rr, edge), zone=zone,
                         targets_hint=[entry + s * 2.0 * box.height],
                         notes=[f"{tf.upper()} {what} {box.bottom:,.0f}–{box.top:,.0f} (touches {box.touches_top}/{box.touches_bottom}) "
                                f"{'वर' if long else 'खाली'} close-breakout" + (" + retest" if retest else "")],
                         meta={"t1_hint": entry + s * box.height, "box_top": box.top, "box_bottom": box.bottom, "box_bars": box.bars, "box_kind": box.kind,
                               "retest": retest, "on_htf_zone": base is not None})


class TriangleBreakout(Detector):
    """D8: converging triangle चा close-breakout."""
    setup_id = "D8"
    default_kind = KIND_BREAKOUT

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg = self.cfg
        if not _in_window(now, cfg.d8_window_start, cfg.d8_window_end):
            return []
        last = bars_by_tf["state"].setdefault("d8_last", {})
        sign_p = trend_sign(ctx.state_name(cfg.primary_htf))
        out = []
        for tf, df, rr in pattern_frames(bars_by_tf, now, cfg.pattern_tfs):
            k = len(df) - 1
            if k < 8 or rr is None or not np.isfinite(rr) or rr <= 0:
                continue
            before = df.iloc[:k]
            tri = find_triangle(before, rr, cfg.tri_max_bars, cfg.tri_swing_order, cfg.tri_flat_k, cfg.tri_min_convergence, cfg.tri_max_apex_frac)
            if tri is None:
                continue
            off = len(before) - min(len(before), cfg.tri_max_bars)     # triangle चे x हे before च्या शेवटच्या tri_max_bars च्या आत
            xb = len(before) - off                                       # breakout bar चा x
            row, prev = df.iloc[-1], df.iloc[-2]
            cl = float(row["close"])
            for s in (1, -1):
                line = tri.upper(xb) if s > 0 else tri.lower(xb)
                if (cl - line) * s <= 0 or off + tri.x0 <= last.get((tf, s), -1):
                    continue
                if s > 0:
                    sl_ref = tri.last_lo if cfg.d8_sl_mode == "swing" else tri.lower(xb)
                else:
                    sl_ref = tri.last_hi if cfg.d8_sl_mode == "swing" else tri.upper(xb)
                if (cl - sl_ref) * s <= 0:
                    continue
                last[(tf, s)] = k
                aligned = (tri.kind == "ASCENDING" and s > 0) or (tri.kind == "DESCENDING" and s < 0) or (tri.kind == "SYMMETRICAL" and sign_p == s)
                quality = 50.0 + (10.0 if aligned else 0.0) + min(10.0, 2.5 * max(0, tri.n_hi + tri.n_lo - 4)) + (10.0 if sign_p == s else 0.0)
                lo_now, hi_now = tri.lower(xb), tri.upper(xb)
                out.append(Candidate(setup_id="D8", direction="LONG" if s > 0 else "SHORT", time=now, entry=cl, sl_ref=float(sl_ref), kind=KIND_BREAKOUT,
                                     tf=tf, trigger_tf=tf, setup_quality=min(quality, 100.0), trigger=_trig(row, prev, rr, line),
                                     zone={"kind": "TRIANGLE", "low": float(min(lo_now, hi_now)), "high": float(max(lo_now, hi_now)), "tf": tf, "quality_grade": "—"},
                                     targets_hint=[float(line + s * tri.width0)],
                                     notes=[f"{tf.upper()} {tri.kind.lower()} triangle ({tri.n_hi}H/{tri.n_lo}L swings) रेषा {line:,.0f} "
                                            f"{'वर' if s > 0 else 'खाली'} close-breakout"],
                                     meta={"triangle": tri.kind, "width0": tri.width0, "aligned": aligned}))
        return out
