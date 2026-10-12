"""12-Oct reference case (Abhi, NIFTY bear call) चा **synthetic** fixture — खऱ्या data चा दावा नाही; फक्त त्याने सांगितलेली रचना:
Daily DOWN (lower highs) → शेवटचा sharp fall ("8 Oct") → sharp rally + चढता corrective channel, volume घटत ("9 Oct" … शेवटच्या दिवसाची
सकाळ) → शेवटच्या दिवशी 09:15 ला supply मध्ये spike (लांब वरचा wick, मोठा volume, close परत खाली) → पुढच्या लाल candles channel ची खालची
रेघ तोडतात (LTF CHoCH) → वाढत्या volume वर dominant लाल candle → दिवसभर घसरण.

`build(end_day, mirror=False)` ⇒ (m15, fut5, ltf5): m15 = 15M spot (timestamp = सुरुवात, bar_end), fut5 = 5M futures volume (timestamp,
volume, expiry), ltf5 = 5M spot (tests/ltf_fixtures.split_bars). mirror = किंमती उलट (p ⇒ 2·MID − p) ⇒ तोच case bull put साठी (volume तसाच).
तारखा फक्त fixture मध्ये (engine code मध्ये नाहीत). Seed ठरलेला ⇒ नेहमी तेच bars.
"""
import numpy as np
import pandas as pd

FALL, RALLY, CH_LEGS, CH_UP, CH_DN = 1600, 800, 4, 60, 20
SPIKE_OPEN, SPIKE, SPIKE_CLOSE, B2, B3 = 40, 170, 20, -20, -100
PER_DAY = 25                                                              # 09:15 … 15:15 (15M)
MID = 22000.0


def _bars_path(path, rng, noise):
    """[(target, n_bars, style, vol)] ⇒ [(o, h, l, c, vol)]: रेषेवर closes + noise; style 'spike' / 'commit' हाताने."""
    out, cur = [], path[0][0]
    for tgt, nb, st, vol in path[1:]:
        if st in ("spike", "commit", "bar"):
            o, h, lo, c = tgt
            out.append((o, h, lo, c, vol))
            cur = c
            continue
        xs = np.linspace(cur, tgt, nb + 1)[1:]
        vs = np.linspace(vol[0], vol[1], nb) if isinstance(vol, tuple) else np.full(nb, float(vol))
        for x, v in zip(xs, vs):
            o = out[-1][3] if out else cur
            c = x + rng.normal(0, noise)
            h, lo = max(o, c) + abs(rng.normal(0, noise)), min(o, c) - abs(rng.normal(0, noise))
            out.append((o, h, lo, c, v))
        cur = tgt
    return out


def _channel(start, n_legs, up, down, bars_up, bars_dn, vol0, vol1):
    """चढता corrective channel: (+up, −down) पाय, volume vol0 ⇒ vol1 घटत."""
    legs, px = [], start
    vols = np.linspace(vol0, vol1, n_legs * 2)
    for k in range(n_legs):
        px += up
        legs.append((px, bars_up, "line", float(vols[2 * k])))
        px -= down
        legs.append((px, bars_dn, "line", float(vols[2 * k + 1])))
    return legs, px


def raw_path(seed=12):
    """किंमतीचा मार्ग (bear case). रिटर्न [(o, h, l, c, vol)] — शेवटच्या दिवसाचे 25 bars शेवटी."""
    rng = np.random.default_rng(seed)
    start = 25600.0
    path = [(start, 0, "start", 0)]
    px = start
    for _ in range(6):                                                   # Daily DOWN: impulse + ABC pullback (lower highs)
        low = px - 900
        a, cc = low + 900 * 0.7 * 0.7, low + 900 * 0.6
        b = a - 900 * 0.6 * 0.35
        path += [(low, 40, "line", 9e5), (a, 25, "line", 5e5), (b, 15, "line", 5e5), (cc, 25, "line", 4e5)]
        px = cc
    low = px - FALL                                                       # "8 Oct": sharp fall
    path += [(low, 30, "line", (8e5, 1.2e6))]
    path += [(low + RALLY, 6, "line", 9e5)]                                 # "9 Oct" सकाळ: sharp rally
    legs, top = _channel(low + RALLY, CH_LEGS, CH_UP, CH_DN, 4, 3, 5e5, 2e5)            # चढता channel, volume घटत
    path += legs
    bars = _bars_path(path, rng, 6.0)
    return bars, top


def build(end_day="2030-03-04", mirror=False, seed=12):
    bars, top = raw_path(seed)
    n_prev = len(bars)
    pad = (-n_prev) % PER_DAY                                             # शेवटचा channel bar = आदल्या दिवसाचा 15:15 bar
    # शेवटचा दिवस: 09:15 spike (supply sweep, लांब वरचा wick, मोठा volume), मग CHoCH + dominant लाल candle, मग घसरण
    c0 = bars[-1][3]
    day = [(c0 + SPIKE_OPEN, c0 + SPIKE, c0 + SPIKE_CLOSE - 15, c0 + SPIKE_CLOSE, 1.6e6),   # 09:15 gap-up spike: लांब वरचा wick (sweep), लाल, मोठा volume
           (c0 + SPIKE_CLOSE, c0 + SPIKE_CLOSE + 10, c0 + B2 - 10, c0 + B2, 9e5),   # 09:30 लाल: channel ची खालची रेघ तुटते (volume कमी)
           (c0 + B2, c0 + B2 + 8, c0 + B3 - 8, c0 + B3, 1.4e6)]       # 09:45 dominant लाल, वाढता volume
    px = c0 + B3
    rng = np.random.default_rng(seed + 1)
    for k in range(PER_DAY - 3):                                          # दिवसभर घसरण
        o = px
        c = o - 9 + rng.normal(0, 5)
        day.append((o, max(o, c) + abs(rng.normal(0, 4)), min(o, c) - abs(rng.normal(0, 4)), c, 6e5))
        px = c
    allb = bars + day
    n_days = (len(allb) + pad) // PER_DAY
    days = pd.bdate_range(end=pd.Timestamp(end_day), periods=n_days)
    slots = [d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * i) for d in days for i in range(PER_DAY)][pad:]
    a = np.array([b[:4] for b in allb], float)
    if mirror:
        a = 2 * MID - a[:, [0, 2, 1, 3]]                                  # o, h, l, c ⇒ उलट (h ↔ l)
    m15 = pd.DataFrame({"timestamp": slots, "open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]})
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    vol = np.array([b[4] for b in allb], float)
    fut = pd.DataFrame({"timestamp": [t + pd.Timedelta(minutes=5 * j) for t in m15["timestamp"] for j in range(3)],
                        "volume": np.repeat(vol / 3.0, 3)})
    fut["expiry"] = pd.Timestamp(end_day) + pd.Timedelta(days=20)
    from tests.ltf_fixtures import split_bars
    ltf = split_bars(m15, 15, 3)
    return m15[["timestamp", "bar_end", "open", "high", "low", "close"]], fut, ltf
