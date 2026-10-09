"""patterns2/settings.py — थर 3 चे आकडे, वर्ग आणि उगम (नकाशा I5)."""

ORDER = ("zigzag", "flat", "triangle", "double_zigzag", "combination", "wedge", "impulse_k")   # बरोबरीत निश्चित क्रम (अक्षरानुसार नाही)

DEFAULTS = {
    "max_points": 30,                 # P मध्ये यापेक्षा जास्त pivots ⇒ त्या K साठी एकदाच `coarse` (एक degree वरचे pivots)
    "node_budget": 20000,             # enumeration ची निश्चित मर्यादा (घड्याळावर नाही)
    "struct_r": 0.236,                # आतली रचना माप 2: θ = r × |wave|
    "flat_b_min_ratio": 0.90,         # R7 (आजचं code; §3.7)
    "flat_b_max": 2.0,                # B/A > यापेक्षा ⇒ m 0.2 (gate नाही)
    "flat_expanded_min": 1.05,
    "barrier_sigma": 0.1,             # triangle: B आणि D 0.1σ च्या आत ⇒ barrier
    "fib_tol": 0.08,                  # C/A Fibonacci जवळीक (पूर्णता-पुरावा)
    "strong_penalty": 0.2,            # "मोठी घट" = m 0.2 (एकच setting)
    "unknown_m": 0.7,                 # रचना / label "अज्ञात"
    "one_match_m": 0.85,              # रचना "3 किंवा 5" सारखी, एक पर्याय जुळतो
    "simplicity": {"3": 1.0, "5": 0.9, "wxy": 0.8},
    "empty_m": 0.7,                   # एकही guideline लागू नाही ⇒ (रिकामा संच जिंकू नये)
    "hysteresis": 1.2,                # challenger ≥ 1.2 × preferred
    "hysteresis_bars": 2,             # लागोपाठ बंद candles
    "wedge_as_ending": False,         # संपूर्ण-K wedge "ending" म्हणून (Abhi चा निर्णय; default नाही ⇒ leading A ⇒ थांबा)
    "moments_per_day": 3,
}

SENSITIVITY = {"struct_r": (0.18, 0.236, 0.3), "hysteresis": (1.1, 1.2, 1.3)}

REGISTER = {
    "max_points": ("Abhi", "थर 3 prompt §2.2"),
    "node_budget": ("अंदाज", "थर 3 prompt §2.2: निश्चित मर्यादा"),
    "struct_r": ("अंदाज", "थर 3 prompt §2.3; sensitivity 0.18 / 0.236 / 0.3"),
    "flat_b_min_ratio": ("code", "R7 (elliott/patterns.py); Correction Reader §3.7"),
    "flat_b_max": ("अंदाज", "§4: > 2.0 ⇒ 0.2 (gate नाही)"),
    "flat_expanded_min": ("Abhi", "थर 3 prompt §3"),
    "barrier_sigma": ("अंदाज", "थर 3 prompt §3"),
    "fib_tol": ("अंदाज", "EWP (recalled, verify)"),
    "strong_penalty": ("Abhi", "थर 3 prompt §4"),
    "unknown_m": ("Abhi", "थर 3 prompt §4"),
    "one_match_m": ("Abhi", "थर 3 prompt §4"),
    "simplicity": ("अंदाज", "थर 3 prompt §4"),
    "empty_m": ("अंदाज", "prompt मध्ये नाही: रिकामा guideline संच 1.0 मिळवून जिंकू नये (test 8)"),
    "hysteresis": ("अंदाज", "थर 3 prompt §5.4"),
    "hysteresis_bars": ("Abhi", "थर 3 prompt §5.4"),
    "wedge_as_ending": ("Abhi-निर्णय बाकी", "Correction Reader §3.5 / §3.7"),
    "extension": ("नोंद", "शेवटच्या wave चं confirmed टोक पुढे सरकलं ⇒ तोच hypothesis (§3.7 यादीत, Abhi च्या निर्णयासाठी)"),
    "touch": ("अंदाज", "पूर्णता-पुरावा: pattern रेघेला 0.5σ आत / पलीकडे ⇒ स्पर्श"),
    "guideline bands": ("अंदाज", "trapezoid मर्यादा: पूर्ण पट्ट्याबाहेर रेषीय घट, 0.2 तळ (patterns2/score.py)"),
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    s.update(overrides or {})
    return s
