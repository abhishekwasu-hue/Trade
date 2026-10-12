"""c1 tests साठी synthetic lower-timeframe bars: एक setup-TF candle ⇒ `parts` लहान candles, किंमतीचा मार्ग o → (bullish: low → high,
bearish: high → low) → c, सरळ रेषांनी (प्रत्येक लहान candle चा high / low = त्याच्या तुकड्यातलं टोक). खऱ्या data चा दावा नाही — फक्त
"LTF वर ही रचना" दाखवायला. Timestamps = setup candle ची सुरुवात + i × (tf / parts)."""
import numpy as np
import pandas as pd


def _path(o, h, lo, c):
    return [o, lo, h, c] if c >= o else [o, h, lo, c]


def split_bars(df, tf, parts):
    rows = []
    step = pd.Timedelta(minutes=tf / parts)
    for ts, o, h, lo, c in zip(pd.to_datetime(df["timestamp"]), df["open"], df["high"], df["low"], df["close"]):
        pts = np.array(_path(float(o), float(h), float(lo), float(c)))
        seg = np.abs(np.diff(pts))
        cum = np.r_[0.0, np.cumsum(seg)]
        tot = cum[-1] if cum[-1] > 0 else 1.0
        at = np.linspace(0.0, tot, parts + 1)
        px = np.interp(at, cum, pts)
        for i in range(parts):
            inside = [pts[j] for j in range(len(pts)) if at[i] < cum[j] < at[i + 1]]
            seg_px = [px[i], px[i + 1], *inside]
            rows.append((ts + i * step, px[i], max(seg_px), min(seg_px), px[i + 1]))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def ltf_rows(rows, t0, minutes):
    """[(o, h, l, c)] ⇒ LTF DataFrame (t0 पासून `minutes` अंतराने) — हाताने लिहिलेल्या LTF रचनेसाठी."""
    df = pd.DataFrame([tuple(map(float, r)) for r in rows], columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", [pd.Timestamp(t0) + pd.Timedelta(minutes=minutes * i) for i in range(len(rows))])
    return df
