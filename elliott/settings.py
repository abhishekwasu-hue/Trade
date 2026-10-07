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
    bad = [d for d in clean["trade_degrees_enabled"] if d >= clean["degree_levels"]]
    if bad:
        errors.append(f"Trade degrees {bad} अस्तित्वात नाहीत — वगळल्या")
        clean["trade_degrees_enabled"] = [d for d in clean["trade_degrees_enabled"] if d < clean["degree_levels"]]
    return clean, errors


def snapshot(settings):
    """प्रत्येक signal/trade सोबत: {"settings": {...}, "hash": sha1[:12]} (sorted JSON)."""
    s = {k: settings.get(k, DEFAULTS[k]) for k in sorted(DEFAULTS)}
    blob = json.dumps(s, sort_keys=True, ensure_ascii=False)
    return {"settings": s, "hash": hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]}
