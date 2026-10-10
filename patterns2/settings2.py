"""patterns2/settings2.py — थर 3 v2.1 चे आकडे आणि "अंदाज" register (थर 3 §8; प्रत्येकी पर्याय, वर्ग, स्रोत)."""
from . import settings as PS1

ORDER = ("zigzag", "flat", "triangle", "double_zigzag", "combination", "wedge", "impulse_k")

DEFAULTS = {
    **{k: v for k, v in PS1.DEFAULTS.items() if k != "wedge_as_ending"},
    "zz_max_ba": 0.90,                 # B/A ≥ 0.90 ⇒ फक्त flat
    "flat_min_ba": 0.618,              # B/A < 0.618 ⇒ फक्त zigzag
    "flat_b_min_ratio": 0.90,          # flat B/A guideline पूर्ण पट्टा 0.90–1.382
    "apex_frac": 0.85, "apex_m": 0.6,
    "three_push_m": 0.6,               # wedge "3 > 1-end" नसेल (Brooks three push)
    "short_final_m": 0.6,              # अपूर्ण शेवटचा wave (final_leg_short / wedge 5 ने 3 गाठलं नाही)
    "exp_b_imp_m": 0.3, "exp_b_weak_m": 0.6,   # expanded-flat B: label आवेग / आवेग (कमकुवत)
    "vol_flat_m": 0.6,                 # K RVOL slope ≥ 0
    "range_like_x": 2.0,               # K वेळ > 2 × I-leg ⇒ range_like
    "final_flag_slope": 0.02,          # K slope < इतका σ / bar
    "final_flag_pushes": 3,
    "partial_lo": 0.70,                # rectangle / flat: swing ≥ 70% पण < 100%
    # momentum (§7)
    "m_sot_ratio": 0.5,
    "m_wick": 0.5,
    "m_small_ratio": 0.7,
    "m_clv": 0.5, "m_trend_pct": 0.4,
    "m_speed": 0.6, "m_bars": 0.8,
    "m_new_ext_sigma": 0.5,
    "m_absorb": 1.5,
    "m_depth_lo": 0.33, "m_depth_hi": 1.00,
    "m_hi": 0.65, "m_lo": 0.35, "m_min_non_na": 6,
    "m_min_k_candles": 6,
    "retrace_note": 0.80,              # MASTER retrace खूण (नोंद; danger नाही)
}

REGISTER = {
    **{k: (str(PS1.DEFAULTS.get(k)), "—", v[0], v[1]) for k, v in PS1.REGISTER.items() if k in PS1.DEFAULTS and k != "wedge_as_ending"},
    "strong_penalty (m floor)": ("0.2", "0.1/0.2/0.3", "अंदाज", "थर 3 §0.2, §8"),
    "simplicity": ("1/0.9/0.8", "—", "अंदाज", "थर 3 §4"),
    "hysteresis": ("1.2× / 2", "1.1/1.2/1.3", "अंदाज", "थर 3 §5"),
    "struct_r": ("0.236", "0.18/0.236/0.3", "अंदाज", "थर 3 §2.3 माप 2"),
    "max_points (coarse)": ("30", "20/30/40", "अंदाज", "थर 3 §2.1"),
    "zz_max_ba / flat_min_ba": ("0.90 / 0.618", "—", "व्याख्या (EWP)", "थर 3 §3 प्रकार"),
    "flat_b_max": ("2.0", "—", "व्याख्या", "थर 3 §3 मजबूत: flat B ≤ 2A"),
    "apex_frac / apex_m": ("0.85 / 0.6", "0.8/0.85/0.9", "अंदाज", "थर 3 §4 triangle apex"),
    "three_push_m": ("0.6", "0.5/0.6/0.7", "Brooks", "थर 3 §3 wedge 3 > 1-end guideline"),
    "short_final_m": ("0.6", "0.5/0.6/0.7", "अंदाज", "थर 3 §4, §6 final_leg_short"),
    "exp_b_imp_m / exp_b_weak_m": ("0.3 / 0.6", "±0.1", "अंदाज", "थर 3 §4 स्वभाव-ओळ expanded-flat B"),
    "vol_flat_m": ("0.6", "0.5/0.6/0.7", "अंदाज", "थर 3 §4 volume"),
    "range_like_x": ("2.0", "1.5/2/3", "अंदाज", "थर 3 §4 K > 2 × I-leg"),
    "final_flag_slope / final_flag_pushes": ("0.02 σ/bar / 3", "0.01/0.02/0.03", "अंदाज (Brooks final flag ~40%)", "थर 3 §6"),
    "partial_lo": ("0.70", "0.65/0.70/0.75", "Bulkowski", "थर 3 §6 partial_rise"),
    "m_sot_ratio": ("0.5", "0.4/0.5/0.6", "अंदाज", "थर 3 §7 item 1"),
    "m_wick": ("0.5", "0.4/0.5/0.6", "अंदाज", "item 2"),
    "m_small_ratio": ("0.7", "0.6/0.7/0.8", "अंदाज", "item 3"),
    "m_clv / m_trend_pct": ("0.5 / 0.4", "±0.1", "अंदाज", "item 4"),
    "m_speed / m_bars": ("0.6 / 0.8", "±0.1", "अंदाज", "item 6"),
    "m_new_ext_sigma": ("0.5 σ", "0.3/0.5/0.8", "अंदाज", "item 7"),
    "m_absorb": ("1.5×", "1.25/1.5/2", "अंदाज", "item 9"),
    "m_depth_lo / m_depth_hi": ("0.33–1.00", "—", "अंदाज", "item 10"),
    "m_hi / m_lo": ("0.65 / 0.35", "0.6/0.65/0.7, 0.3/0.35/0.4", "अंदाज", "§7 निकाल"),
    "m_min_non_na": ("6", "5/6/7", "अंदाज", "§7 निकाल"),
    "m_min_k_candles": ("6", "—", "व्याख्या", "item 3 NA"),
    "retrace_note": ("0.80", "0.786/0.80/0.85", "MASTER", "retrace खूण (नोंद + थर 7 flavour)"),
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    s.update(overrides or {})
    return s
