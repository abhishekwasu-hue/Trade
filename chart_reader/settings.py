"""chart_reader/settings.py — Chart Reader चे settings (dashboard वर; % ऐवजी median range / ATR च्या पटीत).

🎓 Evidence weights आणि A/B/C सीमा Abhi ने 2026-10-08 ला मंजूर केल्या — **tuning नाही**; बदल फक्त Abhi (scorecard पाहून).
"""
import copy

DEFAULTS = {
    # ---- evidence weights (गुण) ----
    "w_trend_strong": 15.0,            # T: HTF दिशेने, मजबूत trend
    "w_trend_weakening": 8.0,          # T: HTF दिशेने, कमकुवत होणारा / अस्पष्ट
    "w_trend_range_edge": 5.0,         # T: range edge वरून
    "w_trend_counter": -20.0,          # T: HTF विरुद्ध (Elliott C-wave setup S6a/S13 असेल तर लागू नाही)
    "w_correction_weakening": 15.0,    # CW: 0–1 × हे
    "w_area_quality": 20.0,            # AQ: 0–1 × हे
    "w_confluence_each": 5.0,          # CF: प्रत्येक अतिरिक्त प्रकार
    "confluence_max_extra": 2,         # CF कमाल = 2 × 5 = 10
    "rv_scale": 50.0,                  # RV = rv_scale × (s − rv_zero), clip [rv_min, rv_max]
    "rv_zero": 0.30,
    "rv_min": -10.0,
    "rv_max": 25.0,
    "w_gap_confirms": 10.0,
    "w_gap_opposes": -10.0,
    "w_elliott_end": 10.0,             # 2 / 4 / C-end ची शक्यता
    "w_elliott_bad": -15.0,            # A-end किंवा wave-B च्या आत
    "w_rr_bonus": 5.0,
    "rr_bonus_min": 5.0,
    "w_event_day": -5.0,
    # ---- KB भाग D ✚ नवीन पुरावे (Abhi 2026-10-08; गुण KB तक्त्यानुसार, tuning नाही) ----
    "w_pb_healthy": 10.0,              # PB [K2]: 3 waves + overlap + origin अबाधित + खोली 38.2–80%
    "w_pb_danger": -10.0,              # PB: counter displacement / 5-wave counter-move / खोली > 80% आणि तिथे area/sweep नाही
    "w_pb_near_origin": -15.0,         # PB: origin जवळ / 100% पलीकडे wick पण acceptance नाही (acceptance = व्हेटो)
    "pb_near_origin_retrace": 0.90,    # PB: retrace ≥ हे ⇒ "origin जवळ"
    "pb_overlap_min": 0.60,            # PB: correction bars चं overlap ratio ≥ हे (K10.1: correction > 0.6)
    "w_lq_sweep": 5.0,                 # LQ [K5]: pool sweep + reclaim close
    "w_lq_wick": 3.0,                  # LQ: sweep bar ची wick ≥ lq_wick_min × range ⇒ अधिक (कमाल 8)
    "lq_wick_min": 0.5,
    "w_vl_dryup": 3.0,                 # VL [K10.3]: pullback rel_vol ÷ impulse rel_vol < vl_dryup_max
    "vl_dryup_max": 0.8,
    "w_vl_spike": 2.0,                 # VL: C-end absorption spike किंवा reversal candle ला volume
    "vl_spike_min": 1.5,               # absorption: rel_vol ≥ हे, निव्वळ प्रगती ≤ vl_spike_prog_mr × MR, close परत आत
    "vl_spike_prog_mr": 0.3,
    "vl_rev_min": 1.2,                 # reversal candle rel_vol ≥ हे
    "w_vl_rising": -5.0,               # VL: pullback मध्ये वाढता volume (ratio > vl_rising_min)
    "vl_rising_min": 1.0,
    "vl_slot_days": 20,                # rel_vol = bar volume ÷ मागच्या इतक्या दिवसांच्या त्याच वेळेच्या slot चा median
    "w_dv_regular": 5.0,               # DV [K10.2]: C-end ला regular divergence
    "w_dv_hidden": 3.0,                # DV: pullback मध्ये hidden divergence
    "w_dv_against": -3.0,              # DV: impulse च्या टोकावर विरुद्ध regular divergence
    "dv_rsi_len": 14,
    "dv_min_bars": 8,                  # तुलना 8–60 bars मागच्या त्याच प्रकारच्या pivot शी
    "dv_max_bars": 60,
    "dv_price_mr": 0.25,               # price फरक ≥ हे × MR
    "dv_rsi_pts": 3.0,                 # RSI फरक ≥ इतके points
    "dv_regular_os": 30.0,             # regular bullish फक्त पहिल्या low चा RSI ≤ 30 (bearish ≥ 70)
    "dv_hidden_rsi_min": 35.0,         # hidden bullish: pullback RSI ≥ 35 (bearish ≤ 65)
    "dv_confirm_bars": 2,              # pivot नंतर इतके बंद bars ⇒ confirmed
    "w_pt_flag": 5.0,                  # PT [K11]: flag
    "w_pt_wedge": 3.0,                 # PT: correction चा opposite wedge
    "w_pt_reversal": -10.0,            # PT: double top/bottom, H&S (neckline तुटलेली), impulse स्वतः wedge
    "pt_pole_min_mr": 6.0,
    "pt_pole_max_bars": 12,
    "pt_flag_min_bars": 4,
    "pt_flag_max_bars": 20,
    "pt_flag_max_retrace": 0.5,
    "pt_dt_tol_mr": 0.5,               # double top: दोन highs ≤ 0.5 MR, ≥ 8 bars दूर, मधला trough ≥ 2 MR खाली
    "pt_dt_min_bars": 8,
    "pt_dt_trough_mr": 2.0,
    "pt_hs_head_mr": 0.5,              # H&S: head ≥ खांद्यांपेक्षा 0.5 MR वर, खांदे ≤ 1.5 MR अंतरात
    "pt_hs_shoulder_mr": 1.5,
    "w_tm_open": -5.0,                 # TM [K14]: 09:15–09:45
    "tm_open_end": "09:45",
    "w_tm_expiry_morning": -3.0,       # TM: expiry दिवस सकाळ
    "tm_expiry_weekday": 1,            # NIFTY weekly expiry = मंगळवार (0 = सोमवार)
    "tm_expiry_morning_end": "12:00",
    "w_vx_jump": -5.0,                 # VX [K14]: pullback दरम्यान VIX उडी (≥ vx_jump_pct %)
    "vx_jump_pct": 5.0,
    "w_vx_falling": 2.0,               # VX: VIX घटतोय (≤ vx_fall_pct %)
    "vx_fall_pct": -2.0,
    # ---- gap नियम (K13; TRADE_KB_FULL_IMPLEMENTATION_PROMPT §4 / §8.1): trade दिशेचा कुठलाही gap ⇒ पहिला pullback हवा ----
    "gap_pb_min_mr": 1.0,              # "pullback आला" = running टोकापासून ≥ हे × MR उलट …
    "gap_pb_tol_mr": 0.3,              # … आणि gap edge (open) / PDC / trade बाजूचा zone पासून ≤ हे × MR पर्यंत
    "gap_story_bars": 8,               # गोष्ट: आदल्या दिवसाची शेवटची चाल = शेवटचे इतके bars
    "gap_story_weak_er": 0.4,          # … efficiency < हे ⇒ कमकुवत
    "gap_story_min_mr": 1.5,           # … |चाल| < हे × MR ⇒ बाजूला
    "gap_setup_g7": True,              # §4A G7 exhaustion gap reversal (PAPER ON, स्वतंत्र scorecard; entry वर परिणाम नाही)
    "g7_min_degree": 2,                # G7: major HTF zone = degree ≥ हे
    "g7_zone_tol_mr": 0.3,
    "g7_reject_bars": 6,               # rejection पहिल्या 2–6 bars मध्ये
    "g7_wick_min": 0.4,
    "g7_rev_cl": 0.6,
    "g7_inv_buffer_mr": 0.25,
    # ---- zones (§2) आणि zone entry (§3) ----
    "zone_entry_tol_mr": 0.3,          # reversal composite zone च्या आत किंवा ≤ हे × MR (नाहीतर FAR_FROM_ZONE)
    "f4_gate": True,                   # Abhi 2026-10-08 (c): code-mode मध्ये F4 side unclear ⇒ entry नाही (SIDE_UNCLEAR)
    "zone_break_buffer_mr": 0.25,      # zone real break: close पलीकडे हे × MR
    "zone_reaction_bars": 8,           # reaction ताकद: touch नंतरचे इतके bars
    "zone_worn_tests": 3,              # ≥ इतके tests ⇒ worn
    # ---- candle-by-candle (§5) ----
    "cs_absorption_ratio": 3.0,        # effort (Σ range) ÷ result (|net|) ≥ हे ⇒ absorption
    "cs_absorption_min_mr": 1.2,
    "cs_wick_tag": 0.4,
    "cs_tired_min": 3,                 # leg मालिकेत इतक्या खुणा ⇒ "थकतोय"
    # ---- grade ----
    "grade_a_min": 60.0,
    "grade_b_min": 45.0,
    "c_wave_setups": ["S6a", "S13"],   # B-end → C setups (spec S6a / S13)
    "c_wave_setups_enabled": False,    # Abhi 2026-10-08: मुख्य setup = pullback end; हे default OFF (OFF ⇒ C). ON ⇒ counter −20 नाही, Tier B
    "tier_mult": {"A": 1.0, "B": 0.5, "C": 0.25},   # spec §4/§11 — size = full × tier multiplier
    # ---- reversal modifiers (elliott/reversal.py च्या 0–1 score वर) ----
    "rev_weak_floor": 0.5,             # range < strength_min × MR ⇒ s × max(floor, range ÷ (strength_min × MR))
    "rev_climax_penalty": 0.20,        # range > strength_max × MR आणि CL < 0.6 ⇒ − हे
    "rev_last_against_penalty": 0.15,  # N ≥ 2 आणि शेवटची candle trade विरुद्ध ⇒ − हे
    "rev_n3_penalty": 0.05,            # N = 3 ⇒ − हे
    "rev_label_strong": 0.60,          # फक्त label (log / narrative / vision), निर्णय नाही
    "rev_label_medium": 0.45,
    # ---- structure (pullback वि. reversal; × median range) ----
    "swing_k": 3.0,                    # sloping lines साठी ZigZag (× MR) — areas.py
    "swing_atr_mult": 3.0,             # impulse: elliott/swings.py pivots, ATR14 × हे (Elliott D1 चा default)
    "internal_atr_mult": 1.5,          # correction चे आतले legs: ATR14 × हे (Elliott D0)
    "impulse_lookback_legs": 8,        # शेवटच्या इतक्या swing legs मधून impulse
    "impulse_min_mr": 6.0,             # impulse किमान आकार (× MR)
    "zigzag_b_max": 0.79,              # zigzag: B ≤ 0.79 × A (spec 38–79%)
    "flat_b_min": 0.90,                # flat: B ≥ 0.9 × A (R7)
    "flat_c_min": 0.90,                # flat C-end: C ≥ 0.9 × A (C ने A एवढं अंतर; नाहीतर C चालू)
    "retrace_max": 0.80,               # pullback valid खोली कमाल (Abhi / KB: 38.2–80%); पलीकडे ⇒ unclear
    "retrace_lo": 0.382,               # 38.2% — त्याखाली "उथळ" (फक्त fact)
    "c_end_back_max": 0.618,           # C-end: C च्या टोकापासून परत आलेलं अंतर ≤ हे × C (market_state A/B/C; C-V1)
    "origin_break_buffer_mr": 0.25,    # impulse origin real break: close origin ∓ हे × MR पलीकडे
    "disp_body_mr": 1.5,               # displacement candle: body ≥ हे × MR आणि body% ≥ disp_body_frac
    "disp_body_frac": 0.6,
    "disp_bars_reversal": 2,           # correction दिशेने इतके displacement bars ⇒ counter-move impulsive
    "acceptance_bars": 2,              # major zone पलीकडे सलग इतके closes (buffer सह) ⇒ acceptance
    "acceptance_buffer_mr": 0.25,
    # ---- areas: KB टप्पा 3 ची साधनं (× MR, MR = 20 बंद bars) — MR-आधारित आकडे IS वर पुन्हा calibrate (अहवाल), बदल Abhi च्या मंजुरीने ----
    "tl_touch_mr": 0.2,                # K6.1: touch = pivot रेषेपासून ± हे × MR
    "tl_close_beyond_mr": 0.3,         # K6.1: anchors मध्ये कुठलाही close रेषेपलीकडे > हे × MR नाही
    "tl_min_spacing": 6,               # K6.1: touches एकमेकांपासून ≥ इतके bars
    "tl_max_slope_mr": 0.5,
    "tl_search_pivots": 16,            # K6.1 शोध: शेवटच्या इतक्या आतल्या swings मधल्या जोड्या (C-V1)
    "tl_search_bars": 200,             # … आणि फक्त शेवटच्या इतक्या bars मधले (15M ⇒ 8 sessions)
    "tl_switch_touches": 2,            # (b) memory: नवी रेषा फक्त जुनीपेक्षा ≥ इतके जास्त touches आणि ताजा touch असेल तर (नाहीतर जुनी कायम)
    "tl_max_lines": 3,                 # §8.4: प्रति role इतक्या valid रेषा (anchors स्थिर) — दर bar ला एकच "सर्वोत्तम" बदलत नाही
    "active_extreme_bars": 12,         # K6.4: active area = ताजे bars + शेवटच्या इतक्या bars मधलं trade-विरुद्ध टोक (C-V1)            # K6.1: |slope| ≤ हे × MR प्रति bar
    "disp_single_mr": 2.5,             # K4: एकच displacement candle ≥ हे × MR
    "base_max_range_mr": 0.8,          # K4: base candle range ≤ हे × MR
    "base_max_height_mr": 1.5,         # K4: base zone उंची ≤ हे × MR
    "eq_tol_mr": 0.15,                 # K5: equal highs/lows ≤ हे × MR अंतरात
    "eq_min_bars": 5,                  # K5: ≥ इतके bars अंतराने
    "fib_band_mr": 0.25,               # K7: Fibonacci / C = A / channel band ± हे × MR
    "fib_min_impulse_mr": 4.0,         # K7: impulse ≥ हे × MR तरच Fibonacci
    "round_max_dist_mr": 6.0,          # K8: किंमतीपासून इतक्या MR मधले round numbers
    "level_band_mr": 0.25,             # K8: round / PDH-PDL band ± हे × MR
    "sweep_min_mr": 0.1,               # K5: sweep = pool च्या 0.1–1.0 MR पलीकडे, आत close
    "sweep_max_mr": 1.0,
    # ---- risk ----
    "inv_buffer_mr": 0.25,             # invalidation = area / reversal candle च्या टोकापलीकडे हे × MR (दोन्हीतलं दूरचं)
    "max_targets": 2,                  # पुढचे 1–2 opposite areas
    # ---- पक्के नियम ----
    "min_rr": 3.0,                     # spot R:R ≥ 1:3
    "opening_block_min": 15,           # 09:15–09:30 entry नाही
}

_RANGES = {"grade_a_min": (0.0, 100.0), "grade_b_min": (0.0, 100.0), "min_rr": (1.0, 10.0), "rv_zero": (0.0, 1.0),
           "rv_scale": (0.0, 200.0), "rev_weak_floor": (0.0, 1.0), "rev_climax_penalty": (0.0, 1.0),
           "rev_last_against_penalty": (0.0, 1.0), "rev_n3_penalty": (0.0, 1.0), "opening_block_min": (0, 120),
           "confluence_max_extra": (0, 5)}


def validate(s):
    """पूर्ण settings dict तपासतो; चूक ⇒ ValueError. रिटर्न तोच dict."""
    missing = [k for k in DEFAULTS if k not in s]
    if missing:
        raise ValueError(f"settings अपूर्ण: {missing}")
    for k, (lo, hi) in _RANGES.items():
        if not lo <= float(s[k]) <= hi:
            raise ValueError(f"{k} = {s[k]} — {lo}…{hi} मध्ये हवा")
    if not s["grade_a_min"] > s["grade_b_min"]:
        raise ValueError("grade_a_min > grade_b_min हवा")
    if s["rv_min"] > s["rv_max"]:
        raise ValueError("rv_min ≤ rv_max हवा")
    tm = s["tier_mult"]
    if set(tm) != {"A", "B", "C"} or any(not 0.0 <= float(v) <= 1.0 for v in tm.values()):
        raise ValueError("tier_mult = {A, B, C}, प्रत्येकी 0–1 (reduce-only)")
    if not isinstance(s["c_wave_setups_enabled"], bool):
        raise ValueError("c_wave_setups_enabled = true / false")
    if not s["rev_label_strong"] > s["rev_label_medium"]:
        raise ValueError("rev_label_strong > rev_label_medium हवा")
    return s


def load(overrides=None):
    s = copy.deepcopy(DEFAULTS)
    if overrides:
        s.update(overrides)
    return validate(s)
