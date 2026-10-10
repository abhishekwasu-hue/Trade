"""legs2/settings.py — थर 2 चे आकडे, वर्ग आणि उगम (नकाशा I5). "अंदाज" आकड्यांची sensitivity ±1 पायरी (मोजमाप पान)."""

DEFAULTS = {
    "baseline_legs": 40,              # percentile baseline: त्याच degree चे मागचे इतके confirmed legs
    "baseline_min": 10,               # यापेक्षा कमी ⇒ C = NA (तटस्थ)
    "c_hi": 0.60, "c_lo": 0.40,       # C ≥ c_hi ⇒ आवेगी; C ≤ c_lo ⇒ सुधारात्मक
    "v_hi": 1.20, "v_lo": 0.83,       # V ≥ v_hi ⇒ आवेगी; V ≤ v_lo ⇒ सुधारात्मक
    "gap_sigma": 0.5,                 # leg मधला overnight gap ≥ इतका σ ⇒ `gap` खूण
    "rvol_sessions": 20,              # RVOL: त्याच slot चा मागच्या इतक्या पात्र sessions चा median
    "rvol_min_sessions": 10,          # यापेक्षा कमी पात्र sessions ⇒ RVOL नाही
    "roll_sessions_before": 2,        # monthly expiry चा दिवस + त्याआधीचे इतके sessions ⇒ vol_unreliable
    "short_leg_bars": 2,              # ≤ इतके bars ⇒ स्वभाव तटस्थ (माप अर्थहीन)
    "degrees": (0, 1, 2, 3),          # legs मोजायच्या degrees
}

SENSITIVITY = {"c": ((0.55, 0.45), (0.65, 0.35)), "v": ((1.15, 0.87), (1.25, 0.80))}

REGISTER = {
    "baseline_legs": ("Abhi", "थर 2 prompt §1.2"),
    "baseline_min": ("Abhi", "थर 2 prompt §1.2"),
    "c_hi / c_lo": ("अंदाज", "थर 2 prompt §1.2; sensitivity 0.55 / 0.45 आणि 0.65 / 0.35"),
    "v_hi / v_lo": ("अंदाज", "थर 2 prompt §1.2; sensitivity"),
    "gap_sigma": ("अंदाज", "थर 2 prompt §1.2"),
    "rvol_sessions": ("Abhi", "थर 2 prompt §1.2"),
    "rvol_min_sessions": ("अंदाज", "prompt मध्ये नाही: सुरुवातीला 20 पात्र sessions नसतील तेव्हा किमान 10 (कमी ⇒ RVOL नाही)"),
    "roll_sessions_before": ("Abhi", "थर 2 prompt §1.2: expiry दिवस + आधीचे 2 sessions"),
    "short_leg_bars": ("Abhi", "थर 2 prompt §1: 1–2 bars ⇒ तटस्थ"),
    "रचना gap (नोंद)": ("अंदाज", "§1.3 'sub-leg पूर्णपणे overnight gap' ≈ 09:15 ला सुरू होणारा 1-bar sub-leg ज्यात gap ≥ त्याच्या आकाराच्या 50%"),
    "retrace_pct": ("नोंद", "K सुरू झाला असावा: tentative टोकापासून सगळ्यात खोल बिंदूपर्यंत %; आत्ताच्या close पर्यंतचा % वेगळा (retrace_now_pct)"),
    # व्याख्या-फरक (prompt: "वेगळी असेल तर फरक register मध्ये")
    "overlap (फरक)": ("नोंद", "market_state.overlap_ratio = 50% पेक्षा जास्त overlap असलेल्या bars चं प्रमाण; थर 2 = overlap ÷ candle range ची "
                               "सरासरी, session ओलांडणारी जोडी वगळून. म्हणून थर 2 चं स्वतःचं माप."),
    "RVOL (फरक)": ("नोंद", "chart_reader/volume.rel_vol = जास्त-volume contract वर causal roll, roll नंतरचा पहिला दिवसच वगळतो, किमान 5 दिवस; "
                           "थर 2 = near-month (contract-expiry field), expiry दिवस + आधीचे 2 sessions unreliable आणि baseline बाहेर. म्हणून "
                           "थर 2 चं स्वतःचं माप."),
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    s.update(overrides or {})
    return s
