"""pivots/settings.py — थर 1 चे आकडे, वर्ग आणि उगम (नकाशा I5). k ची अंतिम निवड Abhi charts पाहून करेल (उगम इथे नोंदवायचा)."""

DEFAULTS = {
    "k": {0: 2.0, 1: 4.0, 2: 8.0, 3: 16.0, 4: 32.0},          # θ_d = k_d × σ
    "sigma_sessions": 20,                                       # σ = मागच्या 20 पूर्ण sessions च्या 15M range चा median
    "warmup_sessions": {0: 3, 1: 3, 2: 10, 3: 30, 4: 60},      # warm-up मधले pivots फिके, निर्णयासाठी नाहीत
    "eq_tol_sigma": 0.1,                                        # EQH / EQL: लागोपाठचे same-type pivots ≤ 0.1 × σ
    "run_days": 22,                                             # "शेवटचे N trading days"
}
K_OPTIONS = {0: (1.5, 2.0, 2.5), 1: (3.0, 4.0, 5.0), 2: (6.0, 8.0, 10.0), 3: (12.0, 16.0, 20.0), 4: (24.0, 32.0, 40.0)}
DEGREE_NAME = {0: "D0 आतली रचना", 1: "D1 trade (15M)", 2: "D2 पालक (1H)", 3: "D3 आजोबा (Daily)", 4: "D4 Weekly"}

REGISTER = {
    "k": ("अंदाज", "Abhi ची प्राथमिक नोंद (शेवटच्या महिन्याचे charts): 2 / 4 / 8 च्या पायरीचे swings वाचनाशी जुळले; अंतिम निवड Abhi"),
    "k_choice_origin": ("—", "अजून निवड नाही (default)"),
    "sigma_sessions": ("Abhi", "थर 1 prompt §1.1 (09:15 आणि CAS candles वगळून; session आधी एकदा, session भर गोठलेला)"),
    "warmup_sessions": ("अंदाज", "थर 1 prompt §1.6"),
    "eq_tol_sigma": ("अंदाज", "थर 1 prompt §2.3"),
    "run_days": ("Abhi", "थर 1 prompt §4"),
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    return s
