"""rsi2/settings.py — थर 6 चे आकडे आणि "अंदाज" register (थर 6 §3a)."""

DEFAULTS = {
    "period": 14,
    "warmup_bars": 50,                                   # segment च्या पहिल्या इतक्या bars ला rsi_warmup
    "gaps": {0: (5, 60), 1: (5, 120), 2: (3, 60)},       # minGap / maxGap (D0, D1: 15M bars; D2: 1H bars)
    "min_price_sigma": 0.25,
    "min_rsi": 3.0,
    "line_skip": 2,                                      # line_clear: L1 / L2 शेजारचे इतके bars वगळ (RSI pivot candle च्या close वर)
    "bull_min": 38, "bull_max": 65, "bull_trough": 40,
    "bear_max": 62, "bear_min": 35, "bear_peak": 60,
    "window_15m": 40, "window_1h": 20,
    "pivot_k": 3,
    "grade_os": 30, "grade_ob": 70,
    "onk_trough_lo": 40, "onk_trough_hi": 55,
    "shift_trough": 40, "shift_peak": 60,
    "edge_recent_bars": 4,                               # range-fade: L2 इतक्या bars आतला (range-कड zone वर)
    # K-RSI (KB K10.4, pending Abhi): regular divergence facts — `engine.Divergence` (evidence only, never a gate)
    "div_rsi_window": 2,                                 # RSI extreme = price pivot ± इतके bars (RSI peak 1 bar lead / lag करू शकतो)
    "div_bars": {"15M": (3, 50), "1H": (3, 35), "5M": (3, 60)},   # दोन pivots मधले bars (min, cap): Abhi RSI-2 ⇒ किमान 3 सगळ्या TF वर
                                                                  # (dashboard: "RSI div min bars"); cap फक्त safety; मुख्य मर्यादा = लागोपाठचे pushes
    "div_hidden": False,                                 # hidden divergence फक्त fact म्हणून, default बंद (Abhi ने वापर सांगितलेला नाही)
    "div_degrees": (0, 1, 2),                            # swings2 degrees (प्रत्येक degree वेगळी; same pair दोन degrees ⇒ दोन्ही नोंद)
    "div_show": True,                                    # dashboard toggle "Show RSI divergences" default (फक्त display)
}

REGISTER = {
    "period": ("14", "9/14/21", "research (Wilder)", "थर 6 §1"),
    "warmup_bars": ("50", "30/50/100", "अंदाज", "थर 6 §1 rsi_warmup (holdout मधून warm-up नाही)"),
    "gaps": ("5/60, 5/120, 3/60", "±50%", "अंदाज", "थर 6 §2 minGap / maxGap"),
    "min_price_sigma": ("0.25 σ", "0.15/0.25/0.4", "अंदाज", "थर 6 §2 minPriceDiff"),
    "min_rsi": ("3", "2/3/5", "अंदाज", "थर 6 §2 minRsiDiff"),
    "line_skip": ("2 bars", "0/1/2", "Abhi ✔ (उत्तर 12)", "line_clear: RSI रेघ 2 bars पर्यंत ओलांडली तरी ग्राह्य; `line_clear_strict` (0) खूण"),
    "bull_min / bull_max / bull_trough": ("38 / 65 / 40", "±2", "Cardwell / Brown", "थर 6 §3"),
    "bear_max / bear_min / bear_peak": ("62 / 35 / 60", "±2", "Cardwell / Brown", "थर 6 §3"),
    "window_15m / window_1h": ("40 / 20", "30/40/60, 15/20/30", "अंदाज", "थर 6 §3"),
    "pivot_k": ("3", "2/3/5", "अंदाज", "थर 6 §3 RSI pivots"),
    "grade_os / grade_ob": ("30 / 70", "25/30/35", "Bulkowski", "थर 6 §2 grade"),
    "onk_trough_lo / onk_trough_hi": ("40–55", "—", "Cardwell", "थर 6 §4 'K संपतोय' (RSI trough 40–55)"),
    "shift_trough / shift_peak": ("40 / 60", "—", "Cardwell", "थर 6 §3 range_shift"),
    "edge_recent_bars": ("4", "2/4/8", "अंदाज", "थर 6 §4 range-fade: divergence L2 range-कड zone वर अलीकडे"),
    "div_rsi_window": ("±2 bars", "1/2/3", "Abhi spec (K-RSI §3)", "RSI extreme price pivot च्या ± N bars मध्ये (फक्त read / confirm bar पर्यंतचे)"),
    "div_bars": ("15M 3–50 · 1H 3–35 · 5M 3–60", "dashboard (min)", "Abhi नियम (RSI-2: किमान 3 bars)",
                 "bar window (safety cap ≈ 3–4 × RSI period); cap ने नाकारलेल्या जोड्या `cap_rejected` मध्ये नोंद"),
    "div_hidden": ("off", "on / off", "Abhi spec (K-RSI §4)", "hidden divergence: फक्त fact, verdict मध्ये कधीच नाही"),
    "div_degrees": ("D0, D1, D2", "—", "व्याख्या (RSI-1 उघडा)", "swings2 degrees: प्रत्येक degree चे लागोपाठचे same-kind pivots (open question RSI-1)"),
    "div_show": ("on", "on / off", "Abhi spec (K-RSI §8a)", "dashboard toggle 'Show RSI divergences' — display only, trading वर परिणाम नाही"),
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    s.update(overrides or {})
    return s
