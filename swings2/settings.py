"""swings2/settings.py — थर 1 चे आकडे आणि "अंदाज" register (MASTER §2: प्रत्येक आकडा, default, 3 पर्याय, वर्ग, स्रोत).
Test: register मध्ये नसलेला अंदाज-आकडा code मध्ये नाही."""

DEFAULTS = {
    "k": {0: 2.0, 1: 4.0, 2: 6.0, 3: 16.0, 4: 32.0},         # θ_D = k_D × σ (D1 = 4, D2 = 6: Abhi ची निवड, SWING CHECK run1)
    "sigma_sessions": 20,
    "warmup_sessions": {0: 3, 1: 3, 2: 10, 3: 30, 4: 60},
    "eq_tol_sigma": 0.1,
    "gap_bar_sigma": 2.0,
    "rhea_band_sigma": 3.0,
    "rhea_min_bars": 8,
    "rhea_touch_sigma": 0.25,
    "rhea_min_touches": 2,
    "rhea_d2_scale": "k2/k1",                    # D2 Rhea 15M वर: पट्टा आणि min bars × k_D2 / k_D1 (Abhi, audit #4)
    "range_band_source": "pivots",               # pivot-RANGE चा range_break पट्टा = शेवटचे 2 H / 2 L (audit #5)
    "k_compare_days": 3,
    "disp_rng_ratio": 1.5,
    "disp_body": 0.6,
    "disp_wick_opp": 0.2,
    "trend_body": 0.5,
    "trend_clv": 0.6,
    "rng_sessions": 20,
    "always_in_candles": 3,
    "always_in_sigma": 3.0,
    "failed_gap_candles": 2,
    "structure_degrees": (1, 2),
    "run_days": 22,
    "moments_per_day": 3,
}
K_OPTIONS = {0: (1.5, 2.0, 2.5), 1: (3.0, 4.0, 5.0), 2: (4.0, 6.0, 8.0), 3: (12.0, 16.0, 20.0), 4: (24.0, 32.0, 40.0)}

# आकडा: (default, पर्याय, वर्ग, स्रोत)
REGISTER = {
    "k": ("2/4/6/16/32", "K_OPTIONS", "Abhi (charts)", "थर 1 §1.2; D1 = 4, D2 = 6 Abhi ची निवड (SWING CHECK run1 k-तुलना)"),
    "sigma_sessions": (20, "—", "व्याख्या", "MASTER §3 σ"),
    "warmup_sessions": ("3/3/10/30/60", "±50%", "अंदाज", "थर 1 §1.4"),
    "eq_tol_sigma": (0.1, "0.05/0.1/0.15", "अंदाज", "थर 1 §2.1"),
    "gap_bar_sigma": (2.0, "1.5/2/3", "अंदाज", "थर 1 §1.5"),
    "rhea_band_sigma": (3.0, "2/3/4", "अंदाज", "Rhea / Dow line, Brooks TR (थर 1 §2.1)"),
    "rhea_min_bars": (8, "6/8/10", "अंदाज", "थर 1 §2.1"),
    "rhea_touch_sigma": (0.25, "0.15/0.25/0.35", "अंदाज", "थर 1 §2.1"),
    "rhea_min_touches": (2, "—", "व्याख्या", "थर 1 §2.1: प्रत्येक कडेला ≥ 2 स्पर्श"),
    "rhea_d2_scale": ("k2/k1 (= 1.5 ⇒ 4.5σ, 12 bars)", "1 / k2/k1", "Abhi (audit #4 उत्तर)",
                      "D2 Rhea 15M bars + σ वर (MASTER §3: D2 साखळी 15M वर); पट्टा / min bars D2 च्या आकाराप्रमाणे; touch tol तसाच"),
    "range_band_source": ("pivots", "—", "व्याख्या (audit #5)", "pivot-RANGE चा range_break पट्टा = शेवटच्या 2 H चा वरचा / 2 L चा खालचा"),
    "k_compare_days": (3, "—", "व्याख्या", "थर 1 §5: k-तुलना charts शेवटचे 3 दिवस (audit #8)"),
    "disp_rng_ratio": (1.5, "1.25/1.5/1.75", "research-practitioner", "MASTER §3 displacement (ICT heuristic)"),
    "disp_body": (0.6, "0.35/0.6/0.85", "research-practitioner", "MASTER §3"),
    "disp_wick_opp": (0.2, "0.0/0.2/0.45", "research-practitioner", "MASTER §3"),
    "trend_body": (0.5, "—", "व्याख्या", "MASTER §3 trend candle"),
    "trend_clv": (0.6, "—", "व्याख्या", "MASTER §3 trend candle"),
    "rng_sessions": (20, "—", "व्याख्या", "MASTER §3 rng_ratio"),
    "always_in_candles": (3, "3/4/5", "Brooks", "थर 1 §2.3"),
    "always_in_sigma": (3.0, "2/3/4", "Brooks", "थर 1 §2.3"),
    "failed_gap_candles": (2, "—", "व्याख्या", "थर 1 §1.5"),
    "structure_degrees": ("D1, D2", "—", "व्याख्या", "थर 1 §2"),
    "run_days": (22, "—", "Abhi", "MASTER §2"),
    "moments_per_day": (3, "—", "Abhi", "MASTER §4"),
}
NOTES = {
    "D2 घटना": "BOS / CHoCH / sweep सगळ्या degrees साठी 15M close वर (series = 15M; known_at = त्या candle चा close)",
    "Rhea": "D1: 15M bars आणि σ; D2: 15M bars आणि σ, पट्टा / min bars × k_D2 / k_D1 (MASTER §3: D2 साखळी 15M वर)",
    "strong low": "शेवटच्या BOS_up ची चाल ज्या confirmed D(n) low पासून सुरू झाली (तुटलेल्या H नंतरचा, BOS आधीचा); तो confirm होईपर्यंत "
                  "strict_HL. आरसा DOWN",
    "weak high": "UP मध्ये शेवटचा H जर आधीचा H न ओलांडलेला (price ≤ आधीचा H) असेल तर तो; नाहीतर None. आरसा DOWN",
    "pivot RANGE": "pivot वरून RANGE (HH + LL / EQ) ⇒ पट्टा = शेवटच्या दोन H चा वरचा आणि दोन L चा खालचा; close बाहेर ⇒ range_break",
    "split candle": "D0 ने same-bar मुळे candle चा भाग वापरला नाही ⇒ D(n+1) त्या candle वर crossing मोजत नाही",
    "1m replay": "stream.json मध्ये प्रत्येक candle चा 1m_status **आणि** 1m चा निर्णय (order: first_ext / first_rev / none + "
                 "after_extreme); replay त्या निर्णयावरच (1m rows पुन्हा वाचत नाही ⇒ backfill pivot बदलत नाही)",
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    return s
