"""opportunity_engine/detectors/range_box.py — D10 FAILED_BREAKOUT_TRAP (spec §4). (D7 RANGE_BOX_BREAKOUT आणि box-आधारित trap PR-3 मध्ये.) कुठलाही indicator नाही.

🎓 नियम (वापरकर्त्याने मंजूर केलेले डीफॉल्ट — PR-2 मध्ये फक्त swing/zone-आधारित trap):
  • दिशा = primary HTF trend (UP ⇒ long trap, DOWN ⇒ short trap); primary RANGE ⇒ दोन्ही (gate चा RANGE_LOCATION कडेजवळच परवानगी देतो); INIT ⇒ नाही.
  • Level (long; short आरशात): आजचे confirmed 5M swing lows (`signals.find_swings`, sweep bar आधी confirm झालेले) · 1H/4H/Daily demand/support zone चा
    खालचा किनारा (तुटलेला नाही) · PDL/PWL (KEY) · PDL (DayInfo).
  • Trap: bar j चा low level खाली गेला (त्याआधी आज level अबाधित होता), आणि `d10_reclaim_bars` (2) bars च्या आत close परत level वर —
    j == आत्ताचा bar (wick sweep, `signals.detect_liquidity_sweep` सारखा) किंवा j..आधीचे bars level खाली close आणि आत्ताचा bar वर close.
  • SL: sweep चा सर्वात खालचा low पलीकडे (buffer risk.py). Target hints: sweep आधीच्या `d10_range_bars` bars च्या range चा वरचा किनारा, आणि entry वरचा पुढचा swing high.
  • एक level दिवसातून एकदाच.
"""
import pandas as pd

from signals import find_swings

from ..context import trend_sign
from .base import Candidate, Detector, KIND_REVERSAL

GRADE_Q = {"A": 15.0, "B": 10.0, "C": 5.0}
HTF_TFS = ("1h", "4h", "1d")


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def _minutes(ts):
    t = pd.Timestamp(ts)
    return t.hour * 60 + t.minute


def trap_levels(ctx, info, df5_before, sign, cfg):
    """sweep होऊ शकणारे levels (long: खालचे; short: वरचे). df5_before = आत्ताच्या bar आधीचे आजचे 5M bars.
    रिटर्न [{price, type, key, level, since, confirmed}] — `since` = आजच्या कुठल्या bar index पासून level अबाधित असायला हवा;
    `confirmed` = 5M swing कोणत्या bar ला confirm झाला (sweep bar याच्या नंतरचा हवा)."""
    out = []
    order = cfg.d10_swing_order
    highs, lows = find_swings(df5_before, order=order)
    if sign > 0:
        for i in lows:
            p = float(df5_before["low"].iloc[i])
            out.append({"price": p, "type": "SWING_5M", "key": f"SWL:{i}:{p:.2f}", "level": None, "since": i + 1, "confirmed": i + order})
    else:
        for i in highs:
            p = float(df5_before["high"].iloc[i])
            out.append({"price": p, "type": "SWING_5M", "key": f"SWH:{i}:{p:.2f}", "level": None, "since": i + 1, "confirmed": i + order})
    for lv in ctx.levels:
        if lv.get("tf") not in HTF_TFS or lv.get("status") == "BROKEN" or lv.get("reject_reason"):
            continue
        kind, src = lv.get("kind"), str(lv.get("source", ""))
        if sign > 0 and (kind in ("DEMAND", "SUPPORT") or (kind == "KEY" and src in ("PDL", "PWL"))):
            out.append({"price": float(lv["low"]), "type": "KEY" if kind == "KEY" else "ZONE", "key": lv.get("level_id") or f"{kind}:{lv['low']:.2f}",
                        "level": lv, "since": 0, "confirmed": -1})
        elif sign < 0 and (kind in ("SUPPLY", "RESISTANCE") or (kind == "KEY" and src in ("PDH", "PWH"))):
            out.append({"price": float(lv["high"]), "type": "KEY" if kind == "KEY" else "ZONE", "key": lv.get("level_id") or f"{kind}:{lv['high']:.2f}",
                        "level": lv, "since": 0, "confirmed": -1})
    if info is not None:
        p = info.pdl if sign > 0 else info.pdh
        if p:
            out.append({"price": float(p), "type": "KEY", "key": "PDL" if sign > 0 else "PDH", "level": None, "since": 0, "confirmed": -1})
    return out


def find_trap(lo, hi, cl, level, sign, reclaim_bars):
    """शेवटच्या bar k वर trap पूर्ण झाला का (arrays = आजचे 5M low/high/close). रिटर्न sweep bar j किंवा None.
    j: level पहिल्यांदा पलीकडे गेला तो bar (त्याआधी `since` पासून level अबाधित), k − j ≤ reclaim_bars, j..k−1 चे closes level पलीकडेच, आणि k चा close परत आत."""
    k = len(cl) - 1
    L = level["price"]
    if (cl[k] <= L) if sign > 0 else (cl[k] >= L):
        return None
    for j in range(max(level["since"], k - reclaim_bars), k + 1):
        pierced = lo[j] < L if sign > 0 else hi[j] > L
        if not pierced:
            continue
        earlier = lo[level["since"]:j] if sign > 0 else hi[level["since"]:j]
        intact = bool((earlier >= L).all()) if sign > 0 else bool((earlier <= L).all())
        if not intact:
            return None                                          # level आज आधीच तुटलेला — हा fresh trap नाही
        outside = cl[j:k]
        stayed = bool((outside < L).all()) if sign > 0 else bool((outside > L).all())
        return j if stayed else None
    return None


class FailedBreakoutTrap(Detector):
    """D10: trend-दिशेविरुद्ध level break खोटा ठरला (2 bars मध्ये परत आत close) ⇒ trend-दिशेने entry."""
    setup_id = "D10"
    default_kind = KIND_REVERSAL

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg = self.cfg
        mins = _minutes(now)
        if mins < _hm(cfg.d10_window_start) or mins > _hm(cfg.d10_window_end):
            return []
        df5 = bars_by_tf["5m"]
        if len(df5) < 4:
            return []
        state_p = ctx.state_name(cfg.primary_htf)
        sign = trend_sign(state_p)
        signs = (sign,) if sign != 0 else ((1, -1) if state_p == "RANGE" else ())
        used = bars_by_tf["state"].setdefault("d10_used", set())
        info = bars_by_tf.get("info")
        k = len(df5) - 1
        row, prev = df5.iloc[-1], df5.iloc[-2]
        out = []
        lo, hi, cl = df5["low"].to_numpy(float), df5["high"].to_numpy(float), df5["close"].to_numpy(float)
        recent = slice(max(0, k - cfg.d10_reclaim_bars), k + 1)
        before = df5.iloc[:k]
        for s in signs:
            best = None
            r_ext = lo[recent].min() if s > 0 else hi[recent].max()
            for lv in trap_levels(ctx, info, before, s, cfg):
                L = lv["price"]
                if (s, lv["key"]) in used or not ((r_ext < L < cl[k]) if s > 0 else (cl[k] < L < r_ext)):
                    continue                                       # जलद फिल्टर: अलीकडे level पलीकडे गेलो नाही / आत्ता परत आत नाही
                j = find_trap(lo, hi, cl, lv, s, cfg.d10_reclaim_bars)
                if j is None or lv["confirmed"] >= j:
                    continue                                       # 5M swing sweep आधीच confirm झालेला हवा
                rank = {"ZONE": 3, "KEY": 2, "SWING_5M": 1}[lv["type"]]
                if best is None or rank > best[0][0]:
                    best = ((rank, j), lv)
            if best is None:
                continue
            (_, j), lv = best
            used.add((s, lv["key"]))
            long = s > 0
            seg = df5.iloc[j:k + 1]
            sweep_ext = float(seg["low"].min()) if long else float(seg["high"].max())
            entry = float(row["close"])
            pre = df5.iloc[max(0, j - cfg.d10_range_bars):j]
            hints = []
            if len(pre):
                edge = float(pre["high"].max()) if long else float(pre["low"].min())
                if (edge > entry) if long else (edge < entry):
                    hints.append(edge)
            sh, sl = find_swings(df5, order=cfg.d10_swing_order)
            if long:
                nxt = sorted(float(df5["high"].iloc[i]) for i in sh if df5["high"].iloc[i] > entry)
            else:
                nxt = sorted((float(df5["low"].iloc[i]) for i in sl if df5["low"].iloc[i] < entry), reverse=True)
            if nxt:
                hints.append(nxt[0])
            L = lv["price"]
            src = lv["level"]
            quality = 50.0 + ((GRADE_Q.get(src.get("quality_grade"), 0.0) + 5.0) if lv["type"] == "ZONE" and src else 10.0 if lv["type"] == "KEY" else 5.0) + \
                (5.0 if j == k else 0.0)
            st4 = ctx.get("4h")
            if st4 is not None and trend_sign(st4.state) == s:
                quality += 10.0
            zone = dict(src) if src else {"kind": lv["type"], "low": L, "high": L, "tf": "5m" if lv["type"] == "SWING_5M" else "1d", "quality_grade": "—"}
            trig = {"open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"]),
                    "prev_high": float(prev["high"]), "prev_low": float(prev["low"]), "ref_range": bars_by_tf.get("rr5"), "level": L}
            out.append(Candidate(setup_id="D10", direction="LONG" if long else "SHORT", time=now, entry=entry, sl_ref=sweep_ext, kind=KIND_REVERSAL,
                                 tf="5m", trigger_tf="5m", setup_quality=min(quality, 100.0), trigger=trig, zone=zone, targets_hint=hints,
                                 notes=[f"{lv['type']} {L:,.0f} {'खाली' if long else 'वर'} sweep ({k - j} bars), परत आत close — trap"],
                                 meta={"level_type": lv["type"], "sweep_bars": k - j, "swept_level": L}))
        return out
