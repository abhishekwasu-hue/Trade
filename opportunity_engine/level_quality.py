"""opportunity_engine/level_quality.py — Level Quality Engine ("ट्रेडरची नजर", deterministic; spec §2.6).

एक spike पूर्ण level बिघडवू नये म्हणून प्रत्येक zone/level या टप्प्यातून जातो:
  1. Spike filter  — wick ≥ 2.5×ref_range ∧ body ≤ 30% range ∧ पुढच्या 1–2 bars मध्ये wick च्या मुळाशी परत ⇒ SPIKE: wick पासून S/R नाही, `SWEEP` level.
  2. Core/outer    — core = touches च्या candles चे *body edges*, outer = wicks.
  3. Origin        — खऱ्या चालीचा उगम (ORIGIN_BOS सर्वोच्च, ORIGIN_MINOR, नसल्यास ORIGIN_NONE).
  4. Reaction      — touch नंतरची हालचाल / ref_range (recent जास्त वजन); 2 जोरदार rejections > 3 कमजोर touches.
  5. Density       — time-at-price histogram (bin = 0.05%): फक्त किंमतीचं वितरण, indicator नाही.
  6. MTF           — एकाच भागात अनेक TF वर दिसतो तर दर्जा वाढतो; फक्त सर्वात खालच्या TF वर = MINOR.
Output: quality_grade A|B|C|REJECT + quality_components + core/outer + stable `level_id`.
`ref_range` इथे फक्त `k × ref_range` (मोजपट्टी) म्हणून — कॉलर `rr` (scalar) देतो.
"""
import hashlib

import numpy as np
import pandas as pd

ORIGIN_SCORE = {"ORIGIN_BOS": 1.0, "ORIGIN_MINOR": 0.5, "ORIGIN_NONE": 0.2}


def spike_kind(o, h, l, c_next, rr, cfg, body_open, body_close):
    """एक bar spike आहे का? `c_next` = पुढच्या ≤2 bars चे closes (यादी). रिटर्न 'UP' / 'DOWN' / None.
    (structure.py मधील `_spike_kind` शी समान नियम; हा standalone, चाचणीयोग्य रूप.)"""
    if not np.isfinite(rr) or rr <= 0:
        return None
    rng = h - l
    if rng <= 0:
        return None
    body_hi, body_lo = max(body_open, body_close), min(body_open, body_close)
    if (body_hi - body_lo) > cfg.spike_body_max * rng:
        return None
    nxt = list(c_next)[:int(cfg.spike_return_bars)]
    if (body_lo - l) >= cfg.spike_wick_k * rr and (body_lo - l) >= (h - body_hi) and any(x >= body_lo for x in nxt):
        return "DOWN"
    if (h - body_hi) >= cfg.spike_wick_k * rr and (h - body_hi) > (body_lo - l) and any(x <= body_hi for x in nxt):
        return "UP"
    return None


def price_density(df, n_sessions=10, bin_pct=0.05):
    """शेवटच्या n sessions चा time-at-price histogram (प्रत्येक bar चा प्रत्येक price-bin मध्ये घालवलेला वेळ = bar चा range ज्या bins ना स्पर्श करतो).
    रिटर्न: (bin_edges, share) — share चा बेरीज 1. रिकामा/अवैध => ([], [])."""
    if df is None or len(df) == 0:
        return np.array([]), np.array([])
    d = df
    days = pd.Series(d["timestamp"]).dt.normalize().drop_duplicates().sort_values().tail(int(n_sessions))
    d = d[pd.Series(d["timestamp"]).dt.normalize().isin(set(days)).values]
    if len(d) == 0:
        return np.array([]), np.array([])
    lo, hi = float(d["low"].min()), float(d["high"].max())
    mid = (lo + hi) / 2.0
    width = max(mid * bin_pct / 100.0, 1e-9)
    n_bins = int(np.ceil((hi - lo) / width)) + 1
    edges = lo + width * np.arange(n_bins + 1)
    counts = np.zeros(n_bins)
    for l, h in zip(d["low"].to_numpy(dtype="float64"), d["high"].to_numpy(dtype="float64")):
        a = int((l - lo) // width)
        b = int((h - lo) // width)
        counts[a:b + 1] += 1.0
    total = counts.sum()
    return edges, (counts / total if total > 0 else counts)


def density_percentile(edges, share, price):
    """दिलेल्या किंमतीच्या bin चं density चं percentile (0..1; सर्व bins मध्ये किती % bins पेक्षा जास्त/बरोबर). वितरण नसेल तर 0.5."""
    if len(edges) < 2 or len(share) == 0:
        return 0.5
    i = int(np.clip(np.searchsorted(edges, price, side="right") - 1, 0, len(share) - 1))
    nz = share[share > 0]
    if len(nz) == 0:
        return 0.5
    return float((nz < share[i]).mean()) if share[i] > 0 else 0.0


def level_id(symbol, tf, kind, core_mid, formed_at):
    """stable id: symbol + tf + kind + rounded core + formed_at चा hash — एकाच इनपुटवर नेहमी सारखाच (visual audit / feedback याला जोडतात)."""
    stamp = pd.Timestamp(formed_at).strftime("%Y-%m-%d %H:%M") if formed_at is not None else ""
    raw = f"{symbol}|{tf}|{kind}|{round(float(core_mid), 1)}|{stamp}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def reaction_strength(excursions_rr, ages_bars, departure_rr=0.0, half_life_bars=120.0, cap_each=5.0, scale=10.0):
    """level_strength: Σ min(excursion/rr, cap) × recency_weight (+ पहिल्या departure चे अर्धे वजन) / scale, 0..1 मध्ये.
    3 कमजोर touches (excursion ≈1×rr) पेक्षा 2 जोरदार rejections (≈5×rr) जास्त मजबूत."""
    total = 0.0
    for exc, age in zip(excursions_rr, ages_bars):
        total += min(max(float(exc), 0.0), cap_each) * (0.5 ** (max(float(age), 0.0) / half_life_bars))
    total += 0.5 * min(max(float(departure_rr), 0.0), 8.0)
    return float(np.clip(total / scale, 0.0, 1.0))


def body_core_score(core_width, outer_width, rr):
    """core जितका लहान/घट्ट (`k × rr` च्या तुलनेत) तितका चांगला: core ≤ 1×rr => 1.0, ≥ 4×rr => 0. outer पेक्षा core मोठा नसतो."""
    if not np.isfinite(rr) or rr <= 0:
        return 0.0
    w = min(core_width, outer_width) if outer_width > 0 else core_width
    return float(np.clip(1.0 - (w / rr - 1.0) / 3.0, 0.0, 1.0))


def grade(components, cfg):
    """components (0..1 प्रत्येकी: clean, body_core, origin, reaction, density, mtf) -> (score 0..1, 'A'|'B'|'C'|'REJECT')."""
    weights = cfg.grade_weights
    score = float(sum(weights[k] * float(components.get(k, 0.0)) for k in weights))
    letter = "A" if score >= cfg.grade_a else "B" if score >= cfg.grade_b else "C" if score >= cfg.grade_c else "REJECT"
    return round(score, 4), letter


REJECT_REASONS = {
    "SPIKE": "एकच spike wick (फक्त SWEEP; S/R नाही)",
    "BROKEN": "level तुटलेला (acceptance) — flip-candidate",
    "FILLED": "Gap पूर्ण भरला (FILLED) — आता level नाही",
    "LOW_SCORE": "गुण कमी (< C)",
    "WARMUP": "ref_range साठी पुरेसा डेटा नाही",
}
