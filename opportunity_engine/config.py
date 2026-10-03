"""opportunity_engine/config.py — सर्व पॅरामीटर्स एकाच ठिकाणी (प्रारंभिक अंदाज; backtest नंतर सुधारले जातील — चांगले दिसावेत म्हणून ट्यून केलेले नाहीत)."""
from dataclasses import dataclass, field

TF_ORDER = ("5m", "15m", "1h", "4h", "1d")
TF_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}      # 1d = पूर्ण session
TF_LABEL = {"5m": "5M", "15m": "15M", "1h": "1H", "4h": "4H", "1d": "Daily"}


@dataclass
class EngineConfig:
    # ---- मोजपट्टी (measures.py) ----
    ref_range_bars: int = 20             # शेवटचे इतके closed *पूर्ण* bars चा median(high−low)
    ref_range_min_bars: int = 10         # यापेक्षा कमी पूर्ण bars => NaN (warm-up; त्या TF वर निर्णय नाही)
    adr_days: int = 14
    # ---- Swings ----
    pivot_n: dict = field(default_factory=lambda: {"5m": 2, "15m": 3, "1h": 3, "4h": 3, "1d": 3})
    swing_k: dict = field(default_factory=lambda: {"5m": 1.5, "15m": 1.5, "1h": 1.5, "4h": 2.0, "1d": 2.0})   # swing significance = k × ref_range
    eq_tol: float = 0.1                  # |Δ| ≤ 0.1×ref_range => EQH/EQL
    # ---- State machine ----
    pullback_k: float = 1.0              # trend extreme पासून इतक्या × ref_range खाली close => PULLBACK
    lh_tol: float = 0.1                  # पात्र LH: last_HH − 0.1×ref_range पेक्षा खाली
    weak_to_range_swings: int = 4        # WEAK नंतर इतके नवीन swings झाले आणि काहीच नाही => RANGE
    range_exit_k: float = 0.1            # RANGE च्या कडेपलीकडे ≥ 0.1×ref_range close + एक confirmed HL/LH
    init_swings: int = 4
    # ---- Spike (§2.6) ----
    spike_wick_k: float = 2.5
    spike_body_max: float = 0.30
    spike_return_bars: int = 2
    spike_body_edge: bool = True         # spike ची wick न वापरता body-edge (swing किंमत आणि weak_low साठी)
    # ---- Zones / Level quality ----
    displacement_k: float = 1.5
    displacement_single_k: float = 2.5
    displacement_body_min: float = 0.6
    reaction_bars: int = 6
    density_bin_pct: float = 0.05
    density_sessions: int = 10
    merge_pct: float = 0.30
    confluence_pct: float = 0.15
    gap_min_pct: float = 0.25
    gap_sessions: int = 20
    grade_weights: dict = field(default_factory=lambda: {
        "clean": 0.15, "body_core": 0.10, "origin": 0.25, "reaction": 0.25, "density": 0.10, "mtf": 0.15})
    grade_a: float = 0.70
    grade_b: float = 0.50
    grade_c: float = 0.30
