"""opportunity_engine/detectors/chart_pattern.py — D9 CHART_PATTERN_BREAKOUT: Flag आणि Double top/bottom (1H/Daily pattern, 15M trigger; spec §4).
कुठलाही indicator नाही. Head & Shoulders पुढच्या टप्प्यात.

🎓 नियम (pattern फक्त *बंद* 1H/Daily bars वर — `bars_by_tf["hist"]`, no-lookahead; breakout = नुकताच बंद झालेला 15M bar):
  • Bull/Bear flag (`patterns.find_flag`): pole ≤ 8 bars मध्ये ≥ 2 × ref_range(tf) × √bars, त्यानंतर 5–20 bars चा pole-विरुद्ध channel,
    retracement ≤ 50%. फक्त primary HTF trend दिशेने. Breakout = 15M close flag च्या कडेच्या रेषेपलीकडे (आधीचा 15M आत).
    SL = flag चा विरुद्ध टोक. Target hint = breakout level ± pole लांबी.
  • Double bottom/top (`patterns.find_double`): दोन swing lows/highs 0.3% आत, ≥ 10 bars अंतर, मधला peak ≥ 1.5 × ref_range(tf).
    Breakout = 15M close neckline पलीकडे (आधीचा 15M आत). SL = दोन lows पैकी खालचा पलीकडे. Target hint = neckline ± pattern उंची.
    दोन्ही दिशा दिसतात — कधी घ्यायचा ते gate ठरवतो (bias दिशा / RANGE_EDGES मध्ये range कडेजवळ).
    Quality: HTF demand/supply वर double (+10), primary trend दिशेने (+10).
  • §5 breakout validation engine करतो (kind BREAKOUT, trigger level = रेषा/neckline). एक pattern दिवसातून एकदाच.
"""
import numpy as np
import pandas as pd

from ..context import trend_sign
from .base import Candidate, Detector, KIND_BREAKOUT
from .patterns import find_double, find_flag
from .trendline import _in_window, _trig, htf_frame, htf_zone_at

TF_LABEL = {"1h": "1H", "1d": "Daily", "4h": "4H"}


class ChartPatternBreakout(Detector):
    """D9: 1H/Daily flag किंवा double top/bottom चा 15M close-breakout."""
    setup_id = "D9"
    default_kind = KIND_BREAKOUT

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def _patterns(self, bars_by_tf, tf, sign_p):
        """(df, rr, flag, doubles{+1,-1}) — त्या TF चा शेवटचा bar बदलला तरच पुन्हा शोध."""
        cfg = self.cfg
        key = f"d9_cache_{tf}"
        df, rr = htf_frame(bars_by_tf, tf, cfg.d9_lookback_bars, key)
        if df is None or rr is None or not np.isfinite(rr):
            return None
        cache = bars_by_tf["state"][key]
        if "flag" not in cache or cache.get("flag_sign") != sign_p:
            cache["flag_sign"] = sign_p
            cache["flag"] = find_flag(df, rr, sign_p, cfg.flag_pole_max_bars, cfg.flag_pole_k, cfg.flag_min_bars, cfg.flag_max_bars,
                                      cfg.flag_max_retrace) if sign_p != 0 else None
        if "dbl" not in cache:
            cache["dbl"] = {s: find_double(df, rr, s, cfg.dbl_tol_pct, cfg.dbl_min_gap, cfg.dbl_peak_k, cfg.dbl_swing_order) for s in (1, -1)}
        return df, rr, cache["flag"], cache["dbl"]

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg = self.cfg
        if not _in_window(now, cfg.d9_window_start, cfg.d9_window_end):
            return []
        df15 = bars_by_tf["15m"]
        if len(df15) < 2 or pd.Timestamp(df15["bar_end"].iloc[-1]) != pd.Timestamp(now):
            return []
        rr15 = bars_by_tf.get("rr15")
        row, prev = df15.iloc[-1], df15.iloc[-2]
        cl, pc = float(row["close"]), float(prev["close"])
        sign_p = trend_sign(ctx.state_name(cfg.primary_htf))
        used = bars_by_tf["state"].setdefault("d9_used", set())
        out = []
        for tf in cfg.d9_tfs:
            got = self._patterns(bars_by_tf, tf, sign_p)
            if got is None:
                continue
            df, rr, flag, dbl = got
            i0, n = int(df.index[0]), len(df)
            if flag is not None:
                s = flag.sign
                L = flag.at(n)                                  # चालू (अपूर्ण) tf bar वरचं रेषेचं मूल्य
                key = ("FLAG", tf, i0 + flag.pole_end)
                if key not in used and (cl - L) * s > 0 and (pc - L) * s <= 0 and (cl - flag.flag_ext) * s > 0:
                    used.add(key)
                    quality = 60.0 + min(10.0, 10.0 * flag.pole_len / (4.0 * rr)) + (5.0 if flag.bars <= 12 else 0.0)
                    out.append(Candidate(setup_id="D9", direction="LONG" if s > 0 else "SHORT", time=now, entry=cl, sl_ref=flag.flag_ext, kind=KIND_BREAKOUT,
                                         tf=tf, trigger_tf="15m", setup_quality=min(quality, 100.0), trigger=_trig(row, prev, rr15, level=L),
                                         zone={"kind": "FLAG", "low": min(L, flag.flag_ext), "high": max(L, flag.flag_ext), "tf": tf, "quality_grade": "—"},
                                         targets_hint=[L + s * flag.pole_len],
                                         notes=[f"{TF_LABEL.get(tf, tf)} {'bull' if s > 0 else 'bear'} flag (pole {flag.pole_len:,.0f}, flag {flag.bars} bars) "
                                                f"{L:,.0f} {'वर' if s > 0 else 'खाली'} 15M close-breakout"],
                                         meta={"pattern": "FLAG", "pattern_tf": tf, "pole_len": flag.pole_len}))
            for s, d in dbl.items():
                if d is None:
                    continue
                key = ("DOUBLE", tf, s, i0 + d.second)
                if key in used or (cl - d.neckline) * s <= 0 or (pc - d.neckline) * s > 0:
                    continue
                used.add(key)
                base = htf_zone_at(ctx, d.level, s)
                quality = 50.0 + (10.0 if base is not None else 0.0) + (10.0 if s == sign_p else 0.0) + min(10.0, (d.second - d.first) / 3.0)
                zone = dict(base) if base is not None else {"kind": "DOUBLE", "low": min(d.level, d.neckline), "high": max(d.level, d.neckline), "tf": tf,
                                                            "quality_grade": "—"}
                name = "double bottom" if s > 0 else "double top"
                out.append(Candidate(setup_id="D9", direction="LONG" if s > 0 else "SHORT", time=now, entry=cl, sl_ref=d.level, kind=KIND_BREAKOUT,
                                     tf=tf, trigger_tf="15m", setup_quality=min(quality, 100.0), trigger=_trig(row, prev, rr15, level=d.neckline), zone=zone,
                                     targets_hint=[d.neckline + s * d.height],
                                     notes=[f"{TF_LABEL.get(tf, tf)} {name} {d.level:,.0f}, neckline {d.neckline:,.0f} {'वर' if s > 0 else 'खाली'} 15M close"
                                            + (" (HTF zone वर)" if base is not None else "")],
                                     meta={"pattern": "DOUBLE_BOTTOM" if s > 0 else "DOUBLE_TOP", "pattern_tf": tf}))
        return out
