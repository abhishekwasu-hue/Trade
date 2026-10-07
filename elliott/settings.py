"""
elliott/settings.py
-------------------
🎓 Elliott Pullback Credit Spread चे सगळे settings — एकाच schema मध्ये (dashboard E5 हाच schema वापरेल; code मध्ये आकडा hard-code नाही).
प्रत्येक phase आपापला विभाग जोडतो. Defaults = spec विभाग 11 + 14 (बहुतेक "[अनुमान] — IS मध्ये calibration आवश्यक").

प्रकार: int / float / bool / choice / time ("HH:MM") / list_float / list_int / list_tf / list_str (comma-separated; list_str चे
प्रत्येक मूल्य choices पैकी).
"""
import hashlib
import json
import math

TFS = ("3m", "5m", "15m", "30m", "1h", "1d")
TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 1440}

SECTIONS = (
    ("degrees", "Degrees / swings"),
    ("counts", "Count engine"),
    ("breaks", "Real break (count आणि exits)"),
    ("setups", "Setups (S1–S14)"),
    ("trigger", "Entry trigger (T1–T7)"),
    ("strike", "Strike / expiry / sizing"),
    ("manage", "Trade management (exits)"),
    ("costs", "खर्च (backtest)"),
    ("candle", "Candle trigger (C1 — experimental, G2 pending)"),
)
SETUP_CODES = ("S1", "S2", "S3", "S4", "S5", "S6a", "S6b", "S6c", "S7", "S8", "S9", "S10", "S11", "S12", "S13", "S14")


def _s(key, section, label, help_, kind, default, lo=None, hi=None, choices=None, step=None, calibrate=True):
    return {"key": key, "section": section, "label": label, "help": help_, "type": kind, "default": default, "min": lo, "max": hi,
            "choices": choices, "step": step, "calibrate": calibrate}


SCHEMA = [
    # ---------------------------------------------------------------- E1a: degrees / swings (spec §11 "Degrees / swings", §12, §14 Q3)
    _s("structure_tf", "degrees", "Structure timeframe", "Pivots/counts या TF वर (NIFTY spot). लहान TF ⇒ जास्त तपशील, जास्त noise.",
       "choice", "5m", choices=("3m", "5m", "15m")),
    _s("atr_len", "degrees", "ATR लांबी (bars)", "Swing threshold साठी ATR. वाढवल्यास threshold हळू बदलतो.", "int", 14, 5, 100),
    _s("degree_levels", "degrees", "Degrees ची संख्या", "D0 (सर्वात लहान) ते D(n−1). 4 = D0–D3.", "int", 4, 2, 5),
    _s("swing_mode", "degrees", "Swing पद्धत", "atr: उलट हालचाल ≥ पट × ATR; pct: ≥ % × भाव; fractal: r-bar fractal (आलटून-पालटून).",
       "choice", "atr", choices=("atr", "pct", "fractal")),
    _s("swing_atr_mult", "degrees", "ATR पट (प्रति degree)", "D0, D1, D2, D3 … साठी. वाढवल्यास त्या degree चे swings मोठे आणि कमी.",
       "list_float", [1.5, 3.0, 6.0, 12.0], 0.1, 100.0),
    _s("swing_pct", "degrees", "% हालचाल (प्रति degree)", "pct पद्धतीसाठी, भावाच्या % मध्ये.", "list_float", [0.15, 0.30, 0.60, 1.20], 0.01, 20.0),
    _s("swing_fractal_r", "degrees", "Fractal r (प्रति degree)", "fractal पद्धतीसाठी: दोन्ही बाजूंचे bars. Confirm = r bars नंतर.",
       "list_int", [2, 4, 8, 16], 1, 100),
    _s("similarity_balance_min", "degrees", "Similarity & Balance किमान", "Neely: शेजारच्या दोन legs पैकी लहान ≥ इतका × मोठा (price किंवा time) "
       "⇒ एकाच degree चे.", "float", 1 / 3, 0.05, 1.0, calibrate=False),
    _s("degree_tf_mode", "degrees", "Degree → TF पद्धत", "auto_by_bars: setup च्या corrective wave साठी TF आपोआप (बंद candles च्या "
       "संख्येवरून); fixed: खालची degree_tf यादी.", "choice", "auto_by_bars", choices=("auto_by_bars", "fixed"), calibrate=False),
    _s("degree_tf", "degrees", "Degree TF (fixed mode)", "D0, D1, … साठी TF. फक्त fixed mode मध्ये.", "list_tf", ["5m", "15m", "1h", "1d"]),
    _s("auto_tfs", "degrees", "Auto TF पर्याय", "auto_by_bars मध्ये यांपैकी सर्वात लहान TF निवडतो.", "list_tf", ["5m", "15m", "30m", "1h", "1d"],
       calibrate=False),
    _s("tf_bars_min", "degrees", "Wave किमान candles", "Corrective wave इतक्या बंद candles मध्ये दिसावी (कमी ⇒ आतली रचना दिसत नाही).",
       "int", 8, 3, 100),
    _s("tf_bars_max", "degrees", "Wave कमाल candles", "यापेक्षा जास्त ⇒ noise; मोठा TF घ्या.", "int", 40, 5, 400),
    _s("trade_degrees_enabled", "degrees", "Trade degrees", "कोणत्या degrees वर trades (उदा. 0,1,2).", "list_int", [0, 1, 2], 0, 4,
       calibrate=False),
]
SCHEMA += [
    # ---------------------------------------------------------------- E1b: count engine (spec §2, §3, §4 vote, §7, §11 "Count engine", §12)
    _s("count_lookback_pivots", "counts", "Count साठी मागचे pivots", "प्रत्येक degree वर count शोधताना इतक्या मागच्या confirmed pivots पैकी "
       "कुठलाही origin असू शकतो. कुठल्याही pattern मध्ये 5 पेक्षा जास्त legs नाहीत ⇒ 5 पेक्षा जास्त निरर्थक. (parent च्या चालू wave ची सुरुवात "
       "lookback बाहेर असली तरी origin म्हणून घेतली जाते.)", "int", 5, 1, 5),
    _s("beam_k", "counts", "प्रति degree counts (beam)", "प्रत्येक degree वर जास्तीत जास्त इतके valid counts ठेवतो (score क्रमाने).",
       "int", 5, 1, 20),
    _s("hysteresis_margin", "counts", "Preferred बदलण्याचा फरक", "नवीन count चं score जुन्या preferred पेक्षा इतकं जास्त असेल तरच preferred बदलतो "
       "(वारंवार उलटसुलट टाळतो).", "float", 0.15, 0.0, 1.0),
    _s("vote_min", "counts", "Vote किमान", "पुढच्या wave च्या दिशेने counts च्या score चा वाटा किमान इतका हवा (कमी ⇒ 'gray', trade नाही).",
       "float", 0.60, 0.5, 1.0),
    _s("alt_weight_min", "counts", "Strike साठी alternate weight", "इतक्या score च्या समान-दिशेच्या counts चा invalidation strike साठी विचारात.",
       "float", 0.25, 0.0, 1.0),
    _s("alt_block_weight", "counts", "उलट count block weight", "उलट दिशेचा count इतका मजबूत (वाटा) असेल तर trade नाही.", "float", 0.35, 0.0, 1.0),
    _s("impulse_time_rule", "counts", "Impulse time नियम (Neely)", "t(w2)>t(w1) किंवा t(w4)>t(w3). off / score / filter.", "choice", "score",
       choices=("off", "score", "filter")),
    _s("c_time_rule", "counts", "C time नियम (Neely)", "Zigzag/flat मध्ये t(c) ≤ t(a)+t(b). off / score / delay (delay ⇒ C-end entry पुढे ढकलणे).",
       "choice", "delay", choices=("off", "score", "delay")),
    _s("wave4_overlap_strict", "counts", "Wave 4 overlap काटेकोर", "true ⇒ wave 4 चा wick सुद्धा wave 1 च्या प्रदेशात चालत नाही (R3).",
       "bool", True, calibrate=False),
    _s("count_inv_basis", "counts", "Count invalidation आधार", "real_break (default: buffer पलीकडे close + पुरावा) / wick (strict EWP).",
       "choice", "real_break", choices=("real_break", "wick"), calibrate=False),
    _s("zigzag_b_band", "counts", "Zigzag B band (× A)", "B चा A च्या तुलनेत अपेक्षित पट्टा — फक्त score.", "list_float", [0.38, 0.79], 0.0, 2.0),
    _s("flat_b_min_ratio", "counts", "Flat B किमान (× A)", "R7: flat मध्ये B ≥ 90% A (नियम).", "float", 0.90, 0.5, 1.0, calibrate=False),
    _s("flat_b_max_ratio", "counts", "Flat B कमाल (× A)", "B > इतका × A ⇒ flat count सोडा [अनुमान].", "float", 2.0, 1.05, 5.0),
    _s("barrier_d_tol_atr", "counts", "Barrier triangle D सहनशीलता (× ATR)", "Barrier triangle मध्ये D, B च्या पलीकडे इतका जाऊ शकतो.",
       "float", 0.25, 0.0, 2.0),
    _s("fib_tol", "counts", "Fibonacci सहनशीलता", "Ratio guideline 'जुळलं' मानण्यासाठी सापेक्ष सहनशीलता (फक्त score).", "float", 0.10, 0.01, 0.5),
    _s("guideline_prior", "counts", "Score smoothing", "score = (hits + prior) / (n + 2·prior). कमी guidelines असलेल्या counts ना अति-score टाळतो.",
       "float", 1.0, 0.0, 10.0),
    _s("cross_degree_mode", "counts", "Degree-संबंध", "strict: लहान degree चा count मोठ्या degree च्या चालू wave चा कायदेशीर भाग असेल तरच "
       "(spec §4); penalty: नसेल तर score × penalty.", "choice", "strict", choices=("strict", "penalty"), calibrate=False),
    _s("cross_degree_penalty", "counts", "Degree-संबंध penalty", "penalty mode मध्ये parent नसलेल्या count चा score गुणक.", "float", 0.5, 0.0, 1.0),
    _s("orphan_position_penalty", "counts", "स्थान अज्ञात penalty", "Parent count नसताना (सर्वात वरची degree) स्थान-बंधित patterns "
       "(diagonals, triangle — R5/R9: ते फक्त ठराविक wave म्हणून येतात) चा score गुणक. 1 ⇒ penalty नाही.", "float", 0.5, 0.0, 1.0),
    _s("cross_degree_tol_bars", "counts", "Origin जुळणी सहनशीलता (bars)", "Child origin आणि parent च्या चालू wave ची सुरुवात इतक्या bars मध्ये "
       "असेल तर एकच pivot मानतो.", "int", 2, 0, 20),
    # ---------------------------------------------------------------- real break (spec §7, §14 Q1) — count invalidation आणि (E3) exits
    _s("median_range_n", "breaks", "Median range bars", "बाजाराचा noise = मागच्या इतक्या बंद bars च्या (high−low) चा median (चालू bar वगळून).",
       "int", 20, 5, 200),
    _s("break_buffer_mr", "breaks", "Break buffer (× median range)", "Level पलीकडे इतका close हवा. Fixed points नाहीत.", "float", 0.25, 0.0, 2.0),
    _s("break_displacement_confirm", "breaks", "Displacement ने लगेच break", "Breaking candle स्वतः ताकदीची असेल तर त्याच close वर खरा break.",
       "bool", True, calibrate=False),
    _s("break_close_loc", "breaks", "Displacement close-location", "Breaking candle चा close break-दिशेच्या टोकाच्या इतक्या भागात हवा.",
       "float", 0.30, 0.05, 0.5),
    _s("strength_min", "breaks", "Strength किमान (× median range)", "Candle 'ताकदीची' = range ≥ इतका × median range (entry trigger सुद्धा).",
       "float", 1.2, 0.5, 5.0, calibrate=False),
    _s("strength_max", "breaks", "Strength कमाल (× median range)", "यापेक्षा मोठी candle = news spike/exhaustion (entry नाकार).", "float", 2.5, 1.0, 10.0,
       calibrate=False),
    _s("break_no_reclaim_bars", "breaks", "Acceptance bars", "कमकुवत breaking close नंतर इतके bars reclaim नाही ⇒ खरा break. 0 ⇒ एका close वर "
       "(तुमच्या नियमाविरुद्ध, फक्त तुलनेसाठी).", "int", 1, 0, 5),
    _s("break_confirm_tf", "breaks", "Break confirmation TF", "level_tf (default, F4): count आणि trade exit दोन्ही त्या wave च्या TF वर "
       "(fixed mode ⇒ degree_tf; auto ⇒ wave start → आत्ता चा auto TF, trigger TF सारखा नियम) — 5m वरच्या कमकुवत closes ने 15m trade चा "
       "count मरत नाही. 5m / 15m ⇒ ठराविक.", "choice", "level_tf", choices=("level_tf", "5m", "15m"), calibrate=False),
    _s("break_retest_confirm", "breaks", "Failed retest ने break", "Break नंतर reclaim झाला, पण लगेच (trigger window मध्ये) level ला "
       "उलट logical reversal ने नाकारलं ⇒ खरा break (role reversal, §14 Q1 c).", "bool", True, calibrate=False),
]
SCHEMA += [
    # ---------------------------------------------------------------- E2: setups (spec §4 tiers, §5 catalogue, §11 "Setups", §14 Q6)
    _s("setups_enabled", "setups", "चालू setups", "S5, S8, S11, S14 default बंद (spec §11).", "list_str",
       ["S1", "S2", "S3", "S4", "S6a", "S6b", "S6c", "S7", "S9", "S10", "S12", "S13"], choices=SETUP_CODES, calibrate=False),
    _s("htf_gate_enabled", "setups", "HTF gate", "true ⇒ Tier B setups block (जुनं वर्तन; दुरुस्ती 1). Default बंद.", "bool", False,
       calibrate=False),
    _s("min_corrective_legs", "setups", "Correction किमान sub-legs", "ज्या corrective wave च्या शेवटी entry, तिच्या आत किमान इतके lower-degree "
       "legs (A-B-C = 3). A-end ban (R4).", "int", 3, 2, 9, calibrate=False),
    _s("zone_fibs_w2", "setups", "Zone: wave 2 / (ii) (× wave 1)", "Wave 1 च्या टोकापासून retrace (S1, S2, S10, S11, S13).", "list_float",
       [0.382, 0.5, 0.618, 0.786], 0.0, 3.0),
    _s("zone_fibs_w4", "setups", "Zone: wave 4 / (iv) (× wave 3)", "Wave 3 च्या टोकापासून retrace (S3, S4, S5, S14).", "list_float",
       [0.236, 0.382, 0.5], 0.0, 3.0),
    _s("zone_fibs_zz_b", "setups", "Zone: zigzag B (× A)", "A च्या टोकापासून retrace (S6a, S12).", "list_float", [0.382, 0.5, 0.618, 0.786],
       0.0, 3.0),
    _s("zone_fibs_flat_b", "setups", "Zone: flat B (× A)", "A च्या टोकापासून retrace; regular ≈ 0.9–1.05, expanded > 1.05 (S6b).",
       "list_float", [0.9, 1.0, 1.236, 1.382], 0.0, 3.0),
    _s("zone_fibs_tri_e", "setups", "Zone: triangle E (× D)", "D च्या टोकापासून retrace (S6c, S9).", "list_float", [0.5, 0.618, 0.786],
       0.0, 3.0),
    _s("zone_fibs_c", "setups", "Zone: C / Y (× A किंवा W)", "B (किंवा X) च्या टोकापासून projection (S7).", "list_float", [0.618, 1.0, 1.618],
       0.0, 5.0),
    _s("zone_fibs_x", "setups", "Zone: X (× W)", "W च्या टोकापासून retrace (S8).", "list_float", [0.382, 0.5, 0.618, 0.786], 0.0, 3.0),
    _s("zone_tol_atr", "setups", "Zone सहनशीलता (× ATR)", "प्रत्येक zone level ± इतका × ATR (trigger TF).", "float", 0.5, 0.0, 3.0),
    _s("wick_beyond_inv_action", "setups", "Wick inv पलीकडे (close आत)", "recount: तो count सोडून त्याच दिशेचा दुसरा valid count (उदा. expanded "
       "flat) — नवीन inv = wick टोक; skip: त्या degree वर entry नाही (§14 Q6).", "choice", "recount", choices=("recount", "skip"),
       calibrate=False),
    # ---------------------------------------------------------------- E2: entry trigger (spec §6, §14 Q2)
    _s("trigger_tf_mode", "trigger", "Trigger TF पद्धत", "level_tf: candle TF = setup च्या corrective wave चा TF (auto/fixed degree TF); "
       "fixed: खालचा TF.", "choice", "level_tf", choices=("level_tf", "fixed"), calibrate=False),
    _s("trigger_tf_fixed", "trigger", "Trigger TF (fixed)", "फक्त fixed mode मध्ये.", "choice", "5m", choices=TFS),
    _s("reclaim_ref", "trigger", "Reclaim संदर्भ", "touched_level: शिवलेल्या zone level वर परत close; zone_high: zone च्या टोकावर. (आधीच्या "
       "candle चा high / sub-wave break निषिद्ध — breakout.)", "choice", "touched_level", choices=("touched_level", "zone_high"),
       calibrate=False),
    _s("touch_reclaim_window", "trigger", "Composite candles (N कमाल)", "शेवटच्या 1–N बंद candles एकत्र (hammer / engulfing / star). "
       "अनिर्णय असल्यास follow-through ने N+1.", "int", 3, 1, 3, calibrate=False),
    _s("rsi_len", "trigger", "RSI लांबी", "फक्त divergence weight > 0 असेल तर.", "int", 14, 2, 100),
    _s("rejection_weights", "trigger", "Rejection weights", "wick, close-location, body, time, divergence (बेरीज 1).", "list_float",
       [0.30, 0.30, 0.20, 0.20, 0.00], 0.0, 1.0),
    _s("rejection_min", "trigger", "Rejection score किमान", "0–1.", "float", 0.60, 0.0, 1.0),
    _s("entry_start", "trigger", "Entry सुरुवात", "पहिली 15 मिनिटं टाळा (gap). Composite चे सगळे candles यानंतर सुरू झालेले हवेत.", "time",
       "09:30", calibrate=False),
    _s("entry_end", "trigger", "Entry शेवट", "यानंतर बंद होणाऱ्या candle वर नवीन entry नाही (exits चालू).", "time", "14:45", calibrate=False),
    _s("soft_buffer_pts", "trigger", "Soft stop buffer (points)", "Soft stop = reversal composite चं टोक ± इतके points.", "float", 5.0, 0.0, 100.0),
]
SCHEMA += [
    # ---------------------------------------------------------------- E3: strike / expiry / sizing (spec §8, §9 Sizing, §11)
    _s("underlying", "strike", "Underlying", "v1 फक्त NIFTY (वापरकर्त्याचं उत्तर 5).", "choice", "NIFTY", choices=("NIFTY",), calibrate=False),
    _s("capital", "strike", "Capital (₹)", "Sizing आणि % निकालांसाठी (उत्तर 9: ₹10 लाख).", "float", 1_000_000.0, 10_000.0, 1e9,
       calibrate=False),
    _s("risk_per_trade_pct", "strike", "Risk प्रति trade (% capital)", "Max loss = (width − credit) × lot × lots ≤ हा % × tier गुणक.",
       "float", 1.0, 0.05, 10.0),
    _s("tier_mult", "strike", "Tier size गुणक (A, B, C)", "C = 0 ⇒ Tier C skip.", "list_float", [1.0, 0.5, 0.25], 0.0, 2.0),
    _s("sizing_mode", "strike", "Sizing पद्धत", "tier_of_A (default, F1): आधी Tier A lots (risk budget वरून, किमान 1), मग lots = "
       "round(A × tier गुणक), Tier B/C किमान खालीलप्रमाणे; risk_budget: प्रत्येक tier चा budget ÷ प्रति-lot तोटा (जुनं — lot 65/75 वर "
       "Tier B कायम 0).", "choice", "tier_of_A", choices=("tier_of_A", "risk_budget"), calibrate=False),
    _s("tierB_min_lots", "strike", "Tier B किमान lots", "tier_of_A मध्ये.", "int", 1, 0, 50, calibrate=False),
    _s("tierC_min_lots", "strike", "Tier C किमान lots", "tier_of_A मध्ये (0 ⇒ A 1 lot असताना C skip).", "int", 0, 0, 50,
       calibrate=False),
    _s("leading_diag_mult", "strike", "Leading diagonal गुणक", "S10 (Neely leading diagonals नाकारतो).", "float", 0.75, 0.0, 1.0),
    _s("max_open_spreads", "strike", "एकाच वेळी कमाल spreads", "फक्त नवीन entries थांबवतो, exits नाही.", "int", 2, 1, 20),
    _s("max_daily_loss_pct", "strike", "दैनिक कमाल तोटा (% capital)", "गाठला ⇒ त्या दिवशी नवीन entry नाही (exits चालू).", "float", 2.0,
       0.1, 20.0),
    _s("expiry_rule", "strike", "Expiry नियम", "current_unless_today_expiry: पहिली weekly; आज expiry असेल तर पुढची (दुरुस्ती 2). "
       "Weekly नसलेल्या काळात (2019 आधी) सर्वात जवळची listed expiry.", "choice", "current_unless_today_expiry",
       choices=("current_unless_today_expiry",), calibrate=False),
    _s("min_dte_override", "strike", "किमान DTE (override)", "0 ⇒ बंद (default). >0 ⇒ इतके DTE नसलेली expiry वगळा.", "int", 0, 0, 10,
       calibrate=False),
    _s("inv_buffer_mr", "strike", "Inv buffer (× median range)", "Short strike invalidation च्या पलीकडे इतका; ≥ break buffer हवा.",
       "float", 0.5, 0.0, 5.0),
    _s("k_sd", "strike", "Volatility अंतर (× SD)", "dist_vol = k × spot × IV × √(dte/252).", "float", 1.0, 0.5, 3.0),
    _s("dte_mode", "strike", "DTE पद्धत", "session_fraction: आजची उरलेली मिनिटं + पूर्ण sessions; whole_days: पूर्ण sessions.",
       "choice", "session_fraction", choices=("session_fraction", "whole_days"), calibrate=False),
    _s("min_dist_pts", "strike", "किमान अंतर (points)", "Short strike spot पासून किमान इतका दूर.", "float", 100.0, 0.0, 2000.0),
    _s("width_pts", "strike", "Spread width (points)", "Long leg = short ∓ width (50 / 100 / 150 / 200; strike step च्या पटीत).",
       "int", 100, 50, 500, step=50),
    _s("c_min_by_dte", "strike", "किमान credit/width (DTE 1,2,3,4,5+)", "Credit guard. **Data वरून calibrate** (E4, फक्त IS).",
       "list_float", [0.06, 0.08, 0.10, 0.12, 0.12], 0.0, 1.0),
    _s("min_credit_pts", "strike", "किमान credit (points)", "", "float", 3.0, 0.0, 100.0),
    _s("max_short_delta", "strike", "Short leg कमाल |delta|", "", "float", 0.30, 0.01, 0.5),
    _s("credit_fail_action", "strike", "Guard fail ⇒", "skip (default) / widen_width / try_next_weekly (तुमच्या नियमापेक्षा वेगळा — "
       "backtest मध्ये वेगळा नोंदवा).", "choice", "skip", choices=("skip", "widen_width", "try_next_weekly"), calibrate=False),
    _s("risk_free_rate", "strike", "Risk-free rate", "Black-Scholes साठी (वार्षिक; delta guard, model premium).", "float", 0.065, 0.0, 0.2),
    _s("strike_step", "strike", "Strike step (points)", "Contract master मधून (NIFTY weekly 50).", "int", 50, 5, 500, calibrate=False),
    _s("iv_source", "strike", "IV स्रोत", "atm_iv: निवडलेल्या expiry चा ATM IV (bhavcopy/option chain); vix: India VIX (fallback).",
       "choice", "atm_iv", choices=("atm_iv", "vix"), calibrate=False),
    _s("min_one_lot", "strike", "Budget कमी तरी 1 lot", "true ⇒ size 0 येत असला तरी (गुणक > 0) 1 lot (risk% ओलांडतो). Default बंद; "
       "backtest shadow trades साठी वापरतो.",
       "bool", False, calibrate=False),
    # ---------------------------------------------------------------- E3: trade management (spec §9, §14 Q4/Q5)
    _s("emergency_spot_cross_short", "manage", "Emergency: spot short strike ओलांडतो", "Intrabar लगेच exit (क्रम 0).", "bool", True,
       calibrate=False),
    _s("hard_stop_mult", "manage", "Premium stop (× credit)", "Spread MTM debit ≥ इतका × credit.", "float", 2.0, 1.0, 10.0),
    _s("hard_stop_eval", "manage", "Premium stop तपासणी", "bar_close (default — 1 DTE gamma wicks टाळतो) / intrabar.", "choice",
       "bar_close", choices=("bar_close", "intrabar"), calibrate=False),
    _s("soft_stop_action", "manage", "Soft stop ⇒", "exit / reduce (निम्मे) / alert.", "choice", "exit", choices=("exit", "reduce", "alert")),
    _s("max_reentries", "manage", "कमाल re-entries", "फक्त soft stop नंतर, hard inv अबाधित असेल तर.", "int", 1, 0, 5),
    _s("reentry_after_premium_stop", "manage", "Premium stop नंतर re-entry", "", "bool", False, calibrate=False),
    _s("tierB_exit_mode", "manage", "Tier B exit", "opposite_reversal: C zone मध्ये उलट logical reversal ⇒ पूर्ण exit (§14 Q4); "
       "fixed_mult: spot ≥ B end + mult × A (तुलनेसाठी).", "choice", "opposite_reversal", choices=("opposite_reversal", "fixed_mult"),
       calibrate=False),
    _s("tierB_target_mult", "manage", "Tier B fixed target (× A)", "फक्त fixed_mult mode.", "float", 1.0, 0.3, 3.0),
    _s("tp_pct_credit", "manage", "Profit exit (% credit: A, B, C)", "Captured ≥ इतका ⇒ exit.", "list_float", [65.0, 50.0, 40.0], 5.0, 100.0),
    _s("tierA_target_action", "manage", "Tier A target ⇒", "exit_50pct_trail_rest: निम्मे बंद, उरलेले progressive inv ने; exit_all.",
       "choice", "exit_50pct_trail_rest", choices=("exit_50pct_trail_rest", "exit_all"), calibrate=False),
    _s("tierA_target_fibs", "manage", "Tier A targets (× (i))", "(ii) end पासून.", "list_float", [1.0, 1.618], 0.3, 5.0),
    _s("target_tol_atr", "manage", "Target सहनशीलता (× ATR)", "", "float", 0.25, 0.0, 2.0),
    _s("progress_bars_mult", "manage", "Progress time exit (× bars_last_subleg)", "इतक्या TTF bars मध्ये spot ने शेवटच्या sub-leg चा "
       "origin ओलांडला नाही ⇒ exit.", "float", 1.0, 0.0, 20.0),
    _s("expiry_exit_time", "manage", "Expiry दिवशी तपासणी वेळ", "", "time", "14:45", calibrate=False),
    _s("expiry_hold_min_dist_sd", "manage", "Expiry hold किमान अंतर (SD)", "Expiry दिवशी spot short strike पासून < इतके SD ⇒ exit.",
       "float", 0.5, 0.0, 3.0),
    _s("progressive_inv", "manage", "Progressive inv", "(i) टोक ओलांडल्यावर hard inv = correction end (S1/S2/S10/S13).", "bool", True,
       calibrate=False),
    _s("lower_inv_action", "manage", "Lower degree inv तुटला ⇒", "alert (default) / reduce / exit.", "choice", "alert",
       choices=("alert", "reduce", "exit")),
    # ---------------------------------------------------------------- E3: खर्च (spec §8 India facts, §11 Backtest)
    _s("brokerage_per_order", "costs", "Brokerage प्रति order (₹)", "Discount broker flat (Upstox ₹20).", "float", 20.0, 0.0, 100.0,
       calibrate=False),
    _s("slippage_ticks", "costs", "Slippage (ticks प्रति leg)", "Tick ₹0.05.", "int", 2, 0, 50),
]
SCHEMA += [
    # ---------------------------------------------------------------- C1: Elliott + candle merge (addendum §2–§5) — सगळे default OFF
    _s("candle_profile_mode", "candle", "Wave-profile mode", "off: सगळ्या setups ना generic score; shadow: profile चा निर्णय फक्त log; "
       "on: profile (reduce-only — wave 4/triangle own_correction मुळे pass झालेले profile_admitted tag; बाकी families फक्त कमी करतात).", "choice", "off",
       choices=("off", "shadow", "on")),
    _s("profile_ref_w4", "candle", "Profile: wave 4 strength संदर्भ", "own_correction = त्या wave च्या bars चा median range.", "choice",
       "own_correction", choices=("last_20", "own_correction", "time_slot")),
    _s("profile_ref_flat_c", "candle", "Profile: expanded flat C संदर्भ", "", "choice", "own_correction",
       choices=("last_20", "own_correction", "time_slot")),
    _s("profile_ref_tri_e", "candle", "Profile: triangle E संदर्भ", "", "choice", "own_correction",
       choices=("last_20", "own_correction", "time_slot")),
    _s("profile_ref_default", "candle", "Profile: बाकी setups संदर्भ", "", "choice", "last_20",
       choices=("last_20", "own_correction", "time_slot")),
    _s("profile_counter_extra", "candle", "Profile: B-end (counter) अतिरिक्त score", "S6a/S6b/S12: rejection_min + इतका.", "float", 0.05,
       0.0, 0.5),
    _s("strength_ref", "candle", "Strength संदर्भ (generic)", "last_20 (सध्याचं) / time_slot: max(median20, त्याच 15m slot चा मागच्या "
       "sessions चा median). Profile मध्ये last_20 = हा generic संदर्भ.", "choice", "last_20", choices=("last_20", "time_slot")),
    _s("slot_median_sessions", "candle", "Slot median sessions", "time_slot साठी.", "int", 20, 5, 100),
    _s("strength_cap_mode", "candle", "Strength कमाल नियम", "fixed: > strength_max ⇒ reject (सध्याचं); logic: रुंद candle ने level परत "
       "मिळवला (close-location ≥ 0.6) ⇒ pass, नाहीतर reject.", "choice", "fixed", choices=("fixed", "logic")),
    _s("strength_risk_guard_mult", "candle", "Logic mode: risk guard (× median)", "strength_cap_mode = logic मध्येही range यापेक्षा मोठी ⇒ "
       "reject (soft stop फार दूर). 0 ⇒ guard नाही.", "float", 0.0, 0.0, 10.0),
    _s("w_reclaim_depth", "candle", "Reclaim depth weight", "Level पलीकडे किती stab आणि किती आत close (दोन्ही × median range, सरासरी) — "
       "score घटक. 0 ⇒ बंद.", "float",
       0.0, 0.0, 1.0),
    _s("w_overlap", "candle", "Overlap weight", "आधीच्या 1–3 candles शी कमी overlap = खरा ताबा बदल — score घटक. 0 ⇒ बंद.", "float", 0.0,
       0.0, 1.0),
    _s("path_checks", "candle", "Composite path checks", "N ≥ 2: शेवटच्या candle ने (स्वतःच्या high/आधीच्या close पासून) merged range चा "
       "अर्ध्यापेक्षा जास्त परत दिला ⇒ reject.",
       "bool", False),
    _s("n3_penalty", "candle", "N = 3 penalty", "3 candles लागल्या तर score मधून वजा (सुचवलेलं 0.05). 0 ⇒ बंद.", "float", 0.0, 0.0, 0.3),
    _s("body_term_mode", "candle", "Body घटक", "bull_body: |C−O|·[trade दिशा] (सध्याचं); body_or_reclaim: trade दिशेची body **किंवा** "
       "पहिल्या candle च्या body मध्ये ≥ 50% reclaim (piercing).", "choice", "bull_body", choices=("bull_body", "body_or_reclaim")),
    _s("min_body_or_reclaim", "candle", "Body / reclaim किमान", "Trade दिशेची body < 10% range (dragonfly/gravestone) आणि reclaim < 50% ⇒ "
       "एकट्याने pass नाही.",
       "bool", False),
    _s("followthrough_mode", "candle", "Follow-through व्याख्या", "legacy: N=3 अनिर्णयी + पुढची candle दिशेने ⇒ N+1 (सध्याचं); addendum: "
       "कुठलाही N अनिर्णयी ⇒ पुढच्या बंद candle चा close composite close पलीकडे (T7 कायम; stop-entry नाही), कमाल 1 bar.",
       "choice", "legacy", choices=("legacy", "addendum")),
    _s("followthrough_max_bars", "candle", "Follow-through कमाल bars", "addendum mode: अनिर्णयी composite नंतर इतक्या बंद candles पर्यंत "
       "follow-through पाहतो.", "int", 1, 1, 3),
    _s("c_leg_exhaustion_required", "candle", "C-leg displacement चालू ⇒ थांबा", "Correction चा शेवटचा leg अजून displacement candles ने "
       "(शेवटच्या 2 bars पैकी) येत असेल तर पहिली reversal candle नाही.", "bool", False),
    _s("opposite_candle_action", "candle", "उलट reversal candle (position विरुद्ध)", "watch: फक्त log/alert, exit नाही; "
       "tighten_profit_target: profit target निम्मा. **कधीच थेट exit नाही.**", "choice", "watch",
       choices=("watch", "tighten_profit_target")),
]
for _x in SCHEMA:                                                               # C1 candle settings: निर्णय G2 ला तुमचा — calibrator नाही
    if _x["section"] == "candle":
        _x["calibrate"] = False
CANDLE_KEYS = tuple(x["key"] for x in SCHEMA if x["section"] == "candle")
BY_KEY = {s["key"]: s for s in SCHEMA}
DEFAULTS = {s["key"]: (list(s["default"]) if isinstance(s["default"], list) else s["default"]) for s in SCHEMA}


def _coerce(spec, v):
    t = spec["type"]
    if t == "bool":
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on", "हो")
        return bool(v)
    if t in ("int", "float"):
        f = float(v)
        if not math.isfinite(f):
            raise ValueError("NaN/inf")
        return int(round(f)) if t == "int" else f
    if t == "time":
        hh, mm = str(v).strip().split(":")[:2]
        if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError("HH:MM हवं")
        return f"{int(hh):02d}:{int(mm):02d}"
    if t.startswith("list_"):
        items = v if isinstance(v, (list, tuple)) else [x for x in str(v).split(",") if x.strip()]
        if t == "list_str":
            out = [str(x).strip() for x in items]
            if any(x not in spec["choices"] for x in out):
                raise ValueError("अज्ञात मूल्य")
            return list(dict.fromkeys(out))
        if t == "list_tf":
            out = [str(x).strip() for x in items]
            if any(x not in TFS for x in out):
                raise ValueError("अज्ञात TF")
            return out
        out = []
        for x in items:
            f = float(x)
            if not math.isfinite(f):
                raise ValueError("NaN/inf")
            if t == "list_int" and not f.is_integer():
                raise ValueError("पूर्णांक हवा")
            out.append(int(f) if t == "list_int" else f)
        return out
    return str(v) if v is not None else ""


def _in_range(spec, val):
    vals = val if isinstance(val, list) else [val]
    if spec["type"] in ("list_tf", "list_str", "time"):
        return True
    return all((spec["min"] is None or x >= spec["min"]) and (spec["max"] is None or x <= spec["max"]) for x in vals)


def validate(raw):
    """raw dict → (clean — डीफॉल्टसह पूर्ण, errors). अवैध ⇒ डीफॉल्ट + error. अज्ञात keys दुर्लक्षित."""
    clean, errors = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}, []
    for k, v in (raw or {}).items():
        spec = BY_KEY.get(k)
        if spec is None:
            continue
        try:
            val = _coerce(spec, v)
        except (TypeError, ValueError):
            errors.append(f"{spec['label']}: अवैध मूल्य {v!r} — डीफॉल्ट वापरला")
            continue
        if spec["choices"] and spec["type"] != "list_str" and val not in spec["choices"]:
            errors.append(f"{spec['label']}: {val!r} पर्यायांत नाही — डीफॉल्ट वापरला")
            continue
        if not _in_range(spec, val):
            errors.append(f"{spec['label']}: मर्यादेबाहेर ({spec['min']}–{spec['max']}) — डीफॉल्ट वापरला")
            continue
        clean[k] = val
    # फक्त चालू पद्धतीत वापरल्या जाणाऱ्या याद्या तपासतो (उदा. atr mode मध्ये swing_pct ची लांबी महत्त्वाची नाही)
    used = [{"atr": "swing_atr_mult", "pct": "swing_pct", "fractal": "swing_fractal_r"}[clean["swing_mode"]]]
    if clean["degree_tf_mode"] == "fixed":
        used.append("degree_tf")
    for k in used:                                                    # आधी "degree वाढताना वाढायला हवं" — मग लांबी
        v = clean[k][:clean["degree_levels"]]
        if k == "degree_tf":
            bad_order = any(TF_MIN[b] < TF_MIN[a] for a, b in zip(v, v[1:]))
        else:
            bad_order = any(b <= a for a, b in zip(v, v[1:]))
        if bad_order:
            errors.append(f"{BY_KEY[k]['label']}: degree वाढताना मूल्य वाढायला हवं — डीफॉल्ट वापरला")
            clean[k] = list(DEFAULTS[k])
    for k in used:
        n = clean["degree_levels"]
        if len(clean[k]) < n:
            errors.append(f"{BY_KEY[k]['label']}: {n} degrees साठी {n} मूल्यं हवीत — डीफॉल्ट वापरला")
            clean[k] = list(DEFAULTS[k])
            if len(clean[k]) < n:
                errors.append(f"Degrees ची संख्या {n} > डीफॉल्ट यादी — {len(clean[k])} केली")
                clean["degree_levels"] = len(clean[k])
    if clean["tf_bars_min"] >= clean["tf_bars_max"]:
        errors.append("Wave किमान candles ≥ कमाल — दोन्ही डीफॉल्ट")
        clean["tf_bars_min"], clean["tf_bars_max"] = DEFAULTS["tf_bars_min"], DEFAULTS["tf_bars_max"]
    clean["auto_tfs"] = sorted(set(clean["auto_tfs"]), key=TF_MIN.get) or list(DEFAULTS["auto_tfs"])
    clean["trade_degrees_enabled"] = sorted(set(clean["trade_degrees_enabled"]))
    zb = clean["zigzag_b_band"]
    if len(zb) != 2 or zb[0] >= zb[1]:
        errors.append("Zigzag B band: [किमान, कमाल] हवं — डीफॉल्ट वापरला")
        clean["zigzag_b_band"] = list(DEFAULTS["zigzag_b_band"])
    if clean["alt_weight_min"] > clean["alt_block_weight"]:
        errors.append("Alternate weight > block weight — दोन्ही डीफॉल्ट")
        clean["alt_weight_min"], clean["alt_block_weight"] = DEFAULTS["alt_weight_min"], DEFAULTS["alt_block_weight"]
    if clean["strength_min"] >= clean["strength_max"]:
        errors.append("Strength किमान ≥ कमाल — दोन्ही डीफॉल्ट")
        clean["strength_min"], clean["strength_max"] = DEFAULTS["strength_min"], DEFAULTS["strength_max"]
    w = clean["rejection_weights"]
    if len(w) != 5 or sum(w) <= 0:
        errors.append("Rejection weights: 5 मूल्यं (बेरीज > 0) हवीत — डीफॉल्ट वापरला")
        clean["rejection_weights"] = list(DEFAULTS["rejection_weights"])
    if sum(clean["rejection_weights"][:3]) <= 0:
        errors.append("Rejection weights: wick/close/body पैकी किमान एक > 0 हवा — डीफॉल्ट वापरला")
        clean["rejection_weights"] = list(DEFAULTS["rejection_weights"])
    if clean["entry_start"] < "09:30":
        errors.append("Entry सुरुवात 09:30 आधी नाही (पहिली 15 मिनिटं / gap) — 09:30 केली")
        clean["entry_start"] = "09:30"
    if clean["entry_start"] >= clean["entry_end"]:
        errors.append("Entry सुरुवात ≥ शेवट — दोन्ही डीफॉल्ट")
        clean["entry_start"], clean["entry_end"] = DEFAULTS["entry_start"], DEFAULTS["entry_end"]
    for k in ("zone_fibs_w2", "zone_fibs_w4", "zone_fibs_zz_b", "zone_fibs_flat_b", "zone_fibs_tri_e", "zone_fibs_c", "zone_fibs_x"):
        if not clean[k]:
            errors.append(f"{BY_KEY[k]['label']}: रिकामी — डीफॉल्ट वापरला")
            clean[k] = list(DEFAULTS[k])
    for k, n in (("tier_mult", 3), ("tp_pct_credit", 3), ("c_min_by_dte", 5)):
        if len(clean[k]) != n:
            errors.append(f"{BY_KEY[k]['label']}: {n} मूल्यं हवीत — डीफॉल्ट वापरला")
            clean[k] = list(DEFAULTS[k])
    if clean["width_pts"] % clean["strike_step"]:
        errors.append("Spread width strike step च्या पटीत हवी — डीफॉल्ट वापरला")
        clean["width_pts"] = DEFAULTS["width_pts"]
    if not clean["tierA_target_fibs"]:
        errors.append("Tier A targets: रिकामी — डीफॉल्ट वापरला")
        clean["tierA_target_fibs"] = list(DEFAULTS["tierA_target_fibs"])
    if clean["inv_buffer_mr"] < clean["break_buffer_mr"]:
        errors.append("Inv buffer < break buffer — strike count मरण्याआधी गाठला जाईल; inv buffer = break buffer केला")
        clean["inv_buffer_mr"] = clean["break_buffer_mr"]
    bad = [d for d in clean["trade_degrees_enabled"] if d >= clean["degree_levels"]]
    if bad:
        errors.append(f"Trade degrees {bad} अस्तित्वात नाहीत — वगळल्या")
        clean["trade_degrees_enabled"] = [d for d in clean["trade_degrees_enabled"] if d < clean["degree_levels"]]
    return clean, errors


def core_candle(settings):
    """C1 candle settings defaults वर — real-break (failed retest) आणि Tier B C-zone reversal exit साठी: candle प्रयोग counts,
    setups आणि exits बदलत नाहीत (ablation स्वच्छ)."""
    if all(settings.get(k) == DEFAULTS[k] for k in CANDLE_KEYS):
        return settings
    return {**settings, **{k: DEFAULTS[k] for k in CANDLE_KEYS}}


def snapshot(settings):
    """प्रत्येक signal/trade सोबत: {"settings": {...}, "hash": sha1[:12]} (sorted JSON)."""
    s = {k: settings.get(k, DEFAULTS[k]) for k in sorted(DEFAULTS)}
    blob = json.dumps(s, sort_keys=True, ensure_ascii=False)
    return {"settings": s, "hash": hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]}
