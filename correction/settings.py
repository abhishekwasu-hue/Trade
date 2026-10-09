"""correction/settings.py — Correction Reader / annotation चे आकडे. प्रत्येक आकडा नकाशा I5 च्या वर्गात, स्रोतासह (REGISTER).
नवा gate नाही: gates फक्त Elliott चे पक्के नियम, नकाशा / Abhi चे मंजूर नियम आणि तपासणीचा क्रम (spec §0.5). बाकी पुरावा."""

DEFAULTS = {
    # run (Abhi, annotation prompt §5): शेवटचे N trading days, प्रत्येक दिवसाला दिवस-अखेर + setup / wait bars (कमाल)
    "annot_days": 22,
    "annot_max_bars_per_day": 3,
    # chart वर प्रत्येक बाजूला zones (Abhi: "Only 2–4 major levels per chart matter"; vision/signal_audit.py)
    "annot_zones_per_side": 4,
    # खोली पट्टे (I च्या टक्क्यांत, wick टोकांवरून) — Abhi
    "depth_valid_lo": 0.382,
    "depth_valid_hi": 0.80,
    "depth_flag_lo": 0.236,
    "depth_sweep_hi": 1.00,            # 80–100% ⇒ फक्त sweep प्रकारचा trigger (नकाशा S2)
    # confluence: वेगवेगळे प्रकार इतक्या MR मध्ये (playbook ~0.5 MR)
    "confluence_tol_mr": 0.5,
    # R:R (Abhi)
    "min_rr": 3.0,
    # SL buffer (PAPER profile seed सारखं: 0.25 MR)
    "sl_buffer_mr": 0.25,
    # RSI (momentum divergence; सध्याचं evidence.divergence सारखी लांबी)
    "rsi_len": 14,
}

# (वर्ग, स्रोत) — नकाशा I5: व्याख्या / Abhi / research-practitioner / NIFTY वर मोजलेला / अंदाज
REGISTER = {
    "annot_days": ("Abhi", "annotation prompt §5: सुमारे एक महिना"),
    "annot_max_bars_per_day": ("Abhi", "annotation prompt §5"),
    "annot_zones_per_side": ("Abhi", "vision/signal_audit.py: Only 2–4 major levels per chart matter"),
    "depth_valid_lo": ("Abhi", "खोली पट्टा 38.2–80% (पुरावा)"),
    "depth_valid_hi": ("Abhi", "खोली पट्टा 38.2–80% (पुरावा)"),
    "depth_flag_lo": ("Abhi", "G8 flag: 23.6–38.2%"),
    "depth_sweep_hi": ("व्याख्या", "नकाशा S2: 80–100% ⇒ sweep / spring आवश्यक"),
    "confluence_tol_mr": ("अंदाज", "playbook ~0.5 MR; sensitivity अहवालात (backtest बंद असेपर्यंत नाही)"),
    "min_rr": ("Abhi", "R:R ≥ 3"),
    "sl_buffer_mr": ("Abhi", "PAPER profile seed (dashboard)"),
    "rsi_len": ("research-practitioner", "RSI(14), Wilder"),
}


def load(overrides=None):
    return {**DEFAULTS, **(overrides or {})}
