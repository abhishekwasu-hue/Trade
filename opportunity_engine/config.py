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
    time_stop_kinds: tuple = ("BREAKOUT",)           # time stop फक्त breakout setups ला (spec: "breakout नंतर 6 bars")
    followthrough_bars: int = 2
    slippage_pts: dict = field(default_factory=lambda: {"NIFTY": 1.0, "BANKNIFTY": 3.0, "SENSEX": 3.0})
    # ---- Gap detectors D1–D3 (detectors/gap.py) ----
    gap_small_pct: float = 0.30
    gap_exhaustion_zone_pct: float = 0.15
    gap_exhaustion_adr: float = 2.5          # आदल्या 3 दिवसांत एकाच दिशेने इतकी × ADR हालचाल => EXHAUSTION
    or_bars: int = 3                         # Opening Range = पहिले 3 × 5M (15 मिनिटं)
    d1_sl_mode: str = "mid"                  # "mid" | "opposite"
    d1_window_end: str = "11:00"             # (मी ठरवलेला डीफॉल्ट — spec मध्ये नाही) OR breakout साठी शेवटची वेळ
    d2_window_end: str = "12:00"             # (मी ठरवलेला डीफॉल्ट) fade trigger साठी शेवटची वेळ
    d2_min_rr: float = 1.5
    d2_patterns_long: tuple = ("BULLISH_ENGULFING", "HAMMER", "MORNING_STAR")
    d2_patterns_short: tuple = ("BEARISH_ENGULFING", "SHOOTING_STAR", "EVENING_STAR")
    d3_window_start: str = "09:45"
    d3_window_end: str = "14:30"
    d3_sl_buffer_k: float = 0.1              # zone च्या लांबच्या किनाऱ्यापलीकडे 0.1 × ref_range(15M)
    d3_max_age_sessions: int = 20
    weak_exit: str = "be"                    # trade चालू असताना primary HTF WEAK झाला: "be" (SL BE ला) | "exit"
    # ---- Dual-Eye Consensus (visual_audit, spec §17.8) — डीफॉल्ट off: फक्त माहिती; तुलना अहवालानंतर वापरकर्ता mode बदलेल ----
    consensus_mode: str = "off"              # "off" | "score" (CONSENSUS +bonus, MATH_ONLY −penalty location score मध्ये) | "gate" (detectors ला फक्त CONSENSUS zones)
    consensus_bonus: float = 10.0
    consensus_penalty: float = 10.0
    # ---- D6 HTF Zone Pullback (detectors/zone_pullback.py) — वापरकर्त्याने मंजूर केलेले सुरुवातीचे डीफॉल्ट ----
    d6_zone_tfs: tuple = ("1h", "4h")        # FRESH/TESTED_1 demand (short: supply) आणि flip zones या TFs चे
    d6_retrace: tuple = (0.50, 0.62)         # primary HTF च्या शेवटच्या impulse leg (protected → last swing) चा 50–62% retracement (शुद्ध किंमत)
    d6_touch_bars: int = 12                  # zone ला स्पर्श शेवटच्या इतक्या 5M bars मध्ये (1 तास) झालेला हवा
    d6_window_start: str = "09:45"
    d6_window_end: str = "14:45"
    # ---- D10 Failed-breakout trap (detectors/range_box.py) ----
    d10_reclaim_bars: int = 2                # level खाली break नंतर इतक्या bars च्या आत परत आत close
    d10_swing_order: int = 2                 # 5M swing lows/highs (signals.find_swings, फक्त confirmed)
    d10_range_bars: int = 20                 # target: sweep आधीच्या इतक्या 5M bars च्या range चा विरुद्ध किनारा
    d10_window_start: str = "09:30"
    d10_window_end: str = "14:45"
    # ---- D7 Range Box / D8 Triangle (detectors/box_triangle.py, PR-3) — spec §4 चे डीफॉल्ट; वेळ-खिडकी मी ठरवलेली ----
    pattern_tfs: tuple = ("5m", "15m")      # box/triangle शोधायचे TF
    box_min_bars: int = 12
    box_max_bars: int = 36
    box_max_adr: float = 0.35               # box उंची ≤ 0.35 × ADR
    box_touch_frac: float = 0.15            # कडेपासून box उंचीच्या 15% आत = touch
    box_min_touches: int = 2                # वर आणि खाली प्रत्येकी
    box_break_frac: float = 0.10            # box पलीकडे close ≥ 0.1 × box उंची
    d7_entry_mode: str = "aggressive"       # "aggressive" (breakout close) | "retest" (6 bars मध्ये edge retest + confirmation candle)
    d7_retest_bars: int = 6
    d7_sl_mode: str = "mid"                 # "mid" | "edge" (विरुद्ध कड)
    d7_window_start: str = "09:30"
    d7_window_end: str = "14:45"
    tri_max_bars: int = 40
    tri_swing_order: int = 2
    tri_flat_k: float = 0.05                # सपाट रेषा: |slope| ≤ 0.05 × ref_range प्रति bar
    tri_min_convergence: float = 0.40       # रुंदी ≥ 40% कमी
    tri_max_apex_frac: float = 0.75         # apex च्या मार्गाच्या 75% आधी breakout
    d8_sl_mode: str = "swing"               # "swing" (शेवटचा आतला swing) | "line" (विरुद्ध रेषा)
    d8_window_start: str = "09:30"
    d8_window_end: str = "14:45"
    # ---- D4 Trendline 3rd touch / D5 Break-Retest (detectors/trendline.py, PR-4) — spec §4 ----
    tl_tf: str = "1h"                       # trendline TF
    tl_lookback_bars: int = 120             # इतके शेवटचे बंद 1H bars
    tl_swing_order: int = 3
    tl_min_gap: int = 5                     # A आणि B मध्ये किमान bars
    tl_max_slope_k: float = 0.5             # |slope| ≤ 0.5 × ref_range(1H) प्रति bar
    tl_touch_pct: float = 0.001             # touch सहनशीलता = max(0.1% × किंमत, 0.25 × ref_range(1H))
    tl_touch_k: float = 0.25
    d4_touch_bars: int = 12                 # 5M: touch शेवटच्या इतक्या bars मध्ये
    d4_window_start: str = "09:30"
    d4_window_end: str = "14:45"
    d5_min_touches: int = 3
    d5_retest_bars: int = 10                # 15M: break नंतर इतक्या bars मध्ये retest
    d5_window_start: str = "09:30"
    d5_window_end: str = "14:45"
    # ---- D9 Flag / Double top-bottom (detectors/chart_pattern.py, PR-4) — spec §4 ----
    d9_tfs: tuple = ("1h", "1d")            # pattern TF; breakout trigger 15M close
    d9_lookback_bars: int = 80
    flag_pole_max_bars: int = 8
    flag_pole_k: float = 2.0                # pole हालचाल ≥ 2 × ref_range(tf) × √bars
    flag_min_bars: int = 5
    flag_max_bars: int = 20
    flag_max_retrace: float = 0.5
    dbl_tol_pct: float = 0.003              # दोन lows/highs 0.3% आत
    dbl_min_gap: int = 10
    dbl_peak_k: float = 1.5                 # मधला peak ≥ 1.5 × ref_range(tf)
    dbl_swing_order: int = 3
    d9_window_start: str = "09:30"
    d9_window_end: str = "14:45"
    # ---- Positional mode (positional.py, PR-4) — spec §9 ----
    pos_strike_buffer_adr: float = 0.25     # short strike = anchor पलीकडे 0.25 × ADR, किंमतीपासून दूर round
    pos_hedge_steps: int = 4                # long (hedge) strike = short ± 4 strike steps
    pos_hold_days: int = 5

