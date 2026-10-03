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
    # ---- Bias / Gate (bias.py) ----
    primary_htf: str = "4h"                  # "4h" (डीफॉल्ट: bias) | "1d". Daily = veto, 1H = पुष्टी
    daily_veto: bool = True
    veto_zone_r: float = 1.5                 # entry Daily FRESH supply / grade A/B resistance च्या इतक्या R आत => veto (c)
    daily_range_location_r: float = 2.5      # Daily RANGE: range edge पासून किमान इतके R
    room_min_r: float = 1.5                  # HTF opposing zone पर्यंत किमान R (location rule)
    weak_half_size: bool = False             # True => primary HTF WEAK मध्ये NO_TRADE ऐवजी (trend-दिशेचे) setups अर्ध्या साइजने
    range_edge_frac: float = 0.25            # RANGE_EDGES_ONLY: range उंचीच्या इतक्या अंशातच entry (कडेजवळ)
    pullback_end_setups: tuple = ("D2", "D3", "D4", "D6", "D10")      # WAIT_PULLBACK_END मध्ये चालणारे (breakouts नाहीत)
    breakout_setups: tuple = ("D1", "D5", "D7", "D8", "D9")
    # ---- Validation (validation.py) ----
    val_body_min: float = 0.6
    val_close_loc: float = 0.25
    val_expansion_k: float = 1.2
    val_beyond_k: float = 0.1
    val_volume_mult: float = 1.5
    val_exhaustion_k: float = 2.5
    val_pass: float = 60.0
    val_weights: dict = field(default_factory=lambda: {"body": 20, "close_loc": 15, "expansion": 15, "beyond": 10, "volume": 20, "room": 10, "exhaustion": 10})
    # ---- Scoring (scoring.py) ----
    score_full: float = 75.0
    score_half: float = 60.0
    setup_thresholds: dict = field(default_factory=dict)     # {"D6": {"full": 80, "half": 65}} — setup-निहाय override
    rr_zero: float = 1.5                     # RR component: इथे 0 गुण
    rr_full: float = 3.0                     # RR component: इथे/यापेक्षा जास्त = 10 गुण
    confluence_bonus: float = 5.0
    # ---- Selector (selector.py) ----
    max_trades_per_day: int = 2
    max_sl_per_day: int = 2
    cooldown_minutes: int = 30
    opening_window_end: str = "09:30"
    opening_setups: tuple = ("D1", "D2")
    no_entry_after: str = "14:45"
    eod_exit: str = "15:15"
    # ---- Risk (risk.py) ----
    adr_min_frac: float = 0.1
    adr_max_frac: float = 0.6
    sl_buffer_k: float = 0.25                # SL = structural level पलीकडे 0.25 × ref_range
    t1_r: float = 1.0
    t1_book_frac: float = 0.5
    t2_default_r: float = 2.0
    time_stop_bars: int = 6
    time_stop_r: float = 0.5
    followthrough_bars: int = 2
    slippage_pts: dict = field(default_factory=lambda: {"NIFTY": 1.0, "BANKNIFTY": 3.0, "SENSEX": 3.0})

