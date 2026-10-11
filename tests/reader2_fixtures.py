"""Synthetic OHLC(V) fixtures for reader2 (Chart Reader v2) — deterministic, no dates (synthetic business days from SYN_EPOCH).

Candles are drawn with a chosen anatomy so the anatomy vote has something to read:
  imp  — large bodies, closes near the leg-direction extreme, small wicks, little overlap, ranges ~1.4–1.6 × the warm-up range;
  cor  — small bodies alternating in colour, wicks on both sides, closes mid-range, heavy overlap, contracting ranges.
Shapes are lists of (kind, delta, bars). Mirror = prices reflected (MIRROR − p): an UP fixture becomes the same DOWN fixture.
Volume (optional) mimics futures volume: impulsive candles heavier than corrective ones.
"""
import numpy as np
import pandas as pd

U = 10.0                                   # warm-up candle range (≈ the median range before the shapes)
P0 = 1000.0
MIRROR = 3000.0
WARM = 30


def _warm(n, p):
    """Quiet, slightly drifting-down base so the shapes start from the warm-up low."""
    rows = []
    for k in range(n):
        sg = 1 if k % 2 == 0 else -1
        m = p + 0.4 * (n - 1 - k)
        o, c = m - 0.15 * U * sg, m + 0.15 * U * sg
        rows.append((o, max(o, c) + 0.35 * U, min(o, c) - 0.35 * U, c, 100.0))
    return rows


def _imp(p, delta, n):
    w = np.array([1.15, 0.85, 1.1, 0.9] * (n // 4 + 1))[:n]
    steps = delta * w / w.sum()
    rows, c = [], p
    for st in steps:
        o = c
        c = o + st
        a = abs(st)
        h, lo = (c + 0.08 * a, o - 0.08 * a) if st > 0 else (o + 0.08 * a, c - 0.08 * a)
        rows.append((o, h, lo, c, 220.0))
    return rows


def _cor(p, delta, n):
    """Overlapping candles: ranges a few times the drift per bar (contracting), closes alternate around the path, wicks both sides."""
    rows, c = [], p
    drift = abs(delta) / n
    mids = p + delta * np.arange(1, n + 1) / n
    sg0 = 1 if delta < 0 else -1                                   # first candle closes against the drift (choppy)
    for k, m in enumerate(mids):
        r = max(0.9 * U, 5.0 * drift) * (1.0 - 0.4 * k / max(n - 1, 1))
        sg = sg0 if k % 2 == 0 else -sg0
        o = c
        c = m + 0.25 * r * sg if k < n - 1 else m
        hi, lo = max(o, c) + 0.4 * r, min(o, c) - 0.4 * r
        rows.append((o, hi, lo, c, 90.0))
    return rows


def frame(shape, mirror=False, volume=False, warm=WARM, start=P0):
    """shape = [(kind, delta, bars)] ⇒ OHLC DataFrame (timestamp, open, high, low, close[, volume]) + waypoint bars."""
    rows = _warm(warm, start)
    marks = [len(rows) - 1]
    p = rows[-1][3]
    for kind, delta, n in shape:
        seg = _imp(p, delta, n) if kind == "imp" else _cor(p, delta, n)
        rows += seg
        p = rows[-1][3]
        marks.append(len(rows) - 1)
    a = np.array(rows, float)
    o, h, lo, c, v = a.T
    if mirror:
        o, h, lo, c = MIRROR - o, MIRROR - lo, MIRROR - h, MIRROR - c
    from mtf.adapter import SYN_EPOCH
    df = pd.DataFrame({"timestamp": pd.bdate_range(SYN_EPOCH, periods=len(a)), "open": o, "high": h, "low": lo, "close": c})
    if volume:
        df["volume"] = v
    return df, marks


# 5-wave impulse up: 1 (imp), 2 (cor), 3 (imp, longest), 4 (cor), 5 (imp)
IMPULSE = [("imp", 150, 14), ("cor", -70, 20), ("imp", 300, 24), ("cor", -80, 22), ("imp", 160, 14)]
IMP_SIZE = 150 - 70 + 300 - 80 + 160
# overlapping a-b-c correction of the impulse (zigzag-like, all overlapping candles), stays above the impulse origin
OVERLAP_ABC = [("cor", -150, 40), ("cor", 70, 20), ("cor", -150, 40)]
# zigzag with a big, impulsive c (c ≈ 2 × a, beyond the end of a) that stays a correction
BIG_C_ABC = [("cor", -110, 30), ("cor", 60, 18), ("imp", -220, 12)]
# continuation up after the correction (new high)
CONT = [("imp", 200, 12), ("cor", -70, 20), ("imp", 220, 14), ("cor", -90, 24)]
# sideways overlapping decline that closes below the impulse origin (corrective anatomy, not an impulse)
DEEP_SIDEWAYS = [("cor", -220, 30), ("cor", 90, 16), ("cor", -400, 50), ("cor", 150, 24)]
# sharp 5-wave counter-move (impulsive candles) that retraces ~65% but does not break the impulse origin
SHARP_A = [("imp", -150, 6), ("cor", 50, 5), ("imp", -200, 8), ("cor", 45, 5), ("imp", -140, 6), ("cor", 80, 8)]


def clean_impulse(mirror=False, volume=False):
    """5-wave impulse, then only the first overlapping leg of a pullback (enough to confirm the impulse top)."""
    return frame(IMPULSE + OVERLAP_ABC[:1], mirror, volume)


def overlapping_correction(mirror=False, volume=False):
    """Impulse, overlapping a-b-c correction (above the impulse origin), continuation to a new high."""
    return frame(IMPULSE + OVERLAP_ABC + CONT, mirror, volume)


def big_c_correction(mirror=False, volume=False):
    """Impulse, zigzag whose c is impulsive and ends well beyond the end of a, continuation."""
    return frame(IMPULSE + BIG_C_ABC + CONT, mirror, volume)


def deep_sideways(mirror=False, volume=False):
    """Impulse, then an overlapping sideways decline that closes beyond the impulse origin."""
    return frame(IMPULSE + DEEP_SIDEWAYS, mirror, volume)


def sharp_a(mirror=False, volume=False):
    """Impulse, then a sharp 5-wave counter-move with impulsive candles that does not break the impulse origin."""
    return frame(IMPULSE + SHARP_A + CONT, mirror, volume)


def hourly(df, per_day=7, start=None):
    """Same candles re-stamped as 1H bars (09:15 … 15:15, per_day a session) starting the business day after `start`."""
    from mtf.adapter import SYN_EPOCH
    day0 = pd.Timestamp(start).normalize() + pd.offsets.BDay(1) if start is not None else SYN_EPOCH
    days = pd.bdate_range(day0, periods=len(df) // per_day + 1)
    ts = [days[k // per_day] + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(hours=k % per_day) for k in range(len(df))]
    return df.assign(timestamp=ts)


def split_hourly(daily, per_day=7):
    """Each daily candle ⇒ per_day 1H candles along open → first extreme → second extreme → close (same day, same OHLC)."""
    rows = []
    for _, r in daily.iterrows():
        o, h, lo, c = r["open"], r["high"], r["low"], r["close"]
        path = [o, lo, h, c] if c >= o else [o, h, lo, c]
        xs = np.interp(np.linspace(0, 3, per_day + 1), [0, 1, 2, 3], path)
        for k in range(per_day):
            a, b = xs[k], xs[k + 1]
            rows.append((r["timestamp"] + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(hours=k), a, max(a, b), min(a, b), b))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])
