"""trendlines2/settings.py — थर 5 चे आकडे आणि "अंदाज" register (थर 5 §5a)."""

DEFAULTS = {
    "close_beyond": 0.3,          # A1–A2 मध्ये close रेघेपलीकडे > 0.3 σ ⇒ अवैध
    "max_slope": 0.5,             # σ / bar (live tl_max_slope_mr ची प्रत)
    "min_spacing": 6,             # A1–A2 bars (live tl_min_spacing)
    "k_spacing": 2,               # K-रेघ spacing
    "flat_slope": 0.02,           # σ / bar ⇒ सपाट
    "tau": 0.2,                   # touch tolerance σ
    "k_near": 1.0,                # K चं टोक रेघेपासून ≤ 1 σ
    "stale_x": 3,                 # median touch-spacing × 3 ⇒ stale
    "slope_cls": (0.5, 1.0),      # I सरासरी slope च्या तुलनेत सपाट / मध्यम / तीव्र
    "inbound_bars": 20,
    "fan_valid": 2, "fan_cand": 1,
    "accept_sigma": 0.5, "accept_closes": 2,       # MASTER accept (detrended)
    "valid_touches": 3,
    "prov_break_n": 6,            # provisional रेघ: touch नंतर ≤ N candles मध्ये K आधार-रेघ break (थर 7 tl_break_n शी समान)
}

REGISTER = {
    "close_beyond": ("0.3 σ", "0.2/0.3/0.5", "अंदाज", "थर 5 §2.3.1"),
    "max_slope": ("0.5 σ/bar", "0.3/0.5/0.8", "live-code", "tl_max_slope_mr"),
    "min_spacing / k_spacing": ("6 / 2 bars", "4/6/8, 1/2/3", "live-code / अंदाज", "tl_min_spacing; थर 5 §4"),
    "flat_slope": ("0.02 σ/bar", "0.01/0.02/0.03", "अंदाज", "थर 5 §2.3.4"),
    "tau": ("0.2 σ", "0.1/0.2/0.3", "अंदाज", "थर 5 §2.4"),
    "k_near": ("1 σ", "0.5/1/1.5", "अंदाज", "थर 5 §2.7.4"),
    "stale_x": ("3×", "2/3/4", "अंदाज", "थर 5 §3 मेली / stale"),
    "slope_cls": ("0.5× / 1×", "—", "Bulkowski", "थर 5 §2.7 descriptors"),
    "inbound_bars": ("20", "—", "Bulkowski", "inbound trend"),
    "fan_valid / fan_cand": ("2 / 1", "—", "व्याख्या", "थर 5 §2.6"),
    "accept_sigma / accept_closes": ("0.5 σ / 2", "—", "MASTER", "accept (detrended)"),
    "valid_touches": ("3", "—", "व्याख्या", "थर 5 §2.4: 3 held ⇒ valid, 2 ⇒ उमेदवार; तीव्र ⇒ ≥ 3 held (Abhi उत्तर 11)"),
    "prov_break_n": ("6", "4/6/8", "Abhi (उत्तर 10-ब)", "provisional K-टोक रेघ: 3रा touch + ≤ N candles मध्ये K आधार-रेघ break"),
    "line_break (breaks.py settings)": ("elliott.settings DEFAULTS", "±1 पायरी", "code (MR ≠ σ)", "थर 5 §3"),
}


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update(overrides or {})
    return s
