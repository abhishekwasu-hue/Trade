"""chart_reader/measures.py — एकच मोजपट्टी (KB भाग G): MR = 20 बंद bars चा (high − low) median, **चालू bar वगळून**; swings =
`elliott/swings.py` (degree सह); real break = `elliott/breaks.py`. Chart Reader चे सगळे modules हेच वापरतात."""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from elliott import swings as W

MR_N = 20


def mr_array(df, n=MR_N):
    """bar i वर: bars [i−n … i−1] चा median range (bar i वगळून) — breaks.median_range."""
    return BR.median_range(df, n)


def mr_now(df, n=MR_N):
    """पुढच्या (चालू, अजून न आलेल्या) bar साठी MR = शेवटच्या n **बंद** bars चा median (df मध्ये फक्त बंद bars)."""
    rng = (df["high"].astype(float) - df["low"].astype(float)).to_numpy(float)[-n:]
    return float(np.median(rng)) if len(rng) else float("nan")


def _with_bar_end(df, tf_min):
    if "bar_end" in df.columns:
        return df
    d = df.copy()
    d["bar_end"] = pd.to_datetime(d["timestamp"]) + pd.Timedelta(minutes=tf_min)
    return d


def pivots(df, atr_mult, tf="15m", tf_min=15, atr_len=14):
    """elliott/swings.py चे confirmed pivots (ATR × atr_mult threshold) ⇒ [(bar, price, kind, confirm_bar)] क्रमाने."""
    fr = _with_bar_end(df, tf_min)
    es = {"swing_mode": "atr", "atr_len": int(atr_len), "swing_atr_mult": {0: float(atr_mult)}}
    return [(p.bar_idx, float(p.price), p.kind, p.confirmed_idx) for p in W.degree_pivots(fr, 0, es, tf)]
