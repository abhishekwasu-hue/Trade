"""decision3/settings.py — थर v2.2 "method-first" चे आकडे आणि register (docs/prompts_v2/08_थर_v22_METHOD_FIRST.md).

प्रत्येक आकडा register मध्ये: (default, पर्याय, वर्ग, स्रोत). वर्ग = "Abhi नियम" / "व्याख्या" / "अंदाज". Thresholds निकाल पाहून फिरवायचे नाहीत;
बदल फक्त Abhi-मंजूर batch PR. Test: register मध्ये नसलेला अंदाज-आकडा DEFAULTS मध्ये नाही.
"""

DEFAULTS = {
    "engine_version": "v22",                 # v21 (decision2, जुना) / v22 (हा) — shadow तुलनेसाठी दोन्ही चालतात
    # ① Daily trend (Dow)
    "daily_trend_mode": "impulse",           # Q15 (Abhi FINAL): impulse-degree Dow; "minor" = जुना (फक्त what-if)
    "corr_degree_rule": "internal_pullback", # Q22 (Abhi): correction त्याच degree ची ⇔ impulse च्या सर्वात मोठ्या आतल्या pullback पलीकडे
    "corr_degree_frac": 0.5,                 # फक्त corr_degree_rule = "ratio" (जुना, what-if): मागच्या same-degree correction चा भाग
    "daily_start_nature_gate": True,         # Q28 (Abhi): 3-wave / corrective रचना trend लावत नाही — impulse-स्वभावाचा पाय लागतो
    "daily_parent_gate": True,               # A1 (Abhi review): counter impulse trend उलटवत नाही जोपर्यंत trend च्या सुरुवातीचा origin close ने तुटत नाही
    "q49_impulse_origin": "complete_impulse",  # Q49 (a) origin: "complete_impulse" = चालू leg पूर्ण 5-wave चा wave 5 असेल तर त्या
                                             # impulse ची सुरुवात (Abhi मंजुरी बाकी); "leg" = साधं वाचन (चालू impulse leg चा origin)
    "range_after_trend": True,               # Q27 (Abhi): origin तुटला + दोन समान H आणि दोन समान L ⇒ RANGE (कडांवर trade)
    "maturity_sigma_d": 0.5,                 # maturity: (5) target च्या इतक्या σ_D आत ⇒ "impulse mature" (पुरावा)
    "weekly_min_bars": 10,                   # weekly पालक: यापेक्षा कमी weekly candles ⇒ weekly UNKNOWN
    "daily_swing_method": "pivot",           # pivot (N bars दोन्ही बाजूला) / dc (k_D × σ_D) — Q15: pivot; dc फक्त what-if
    "daily_pivot_n": 2,
    "daily_dc_k": 1.0,                       # θ_D = k_D × σ_D (σ_D = Daily range median)
    "daily_sigma_sessions": 10,              # σ_D साठी Daily candles (warm-up फक्त σ साठी)
    "daily_min_sessions": 10,                # यापेक्षा कमी (≤) Daily candles ⇒ trend UNKNOWN (data अपुरा)
    "range_eq_sigma_d": 0.25,                # RANGE: दोन H आणि दोन L "जवळपास समान" = σ_D च्या इतक्या अपूर्णांकात
    # ② Level (1H)
    "level_degree": 2,                       # swings2 degree = 1H trend-degree (D2)
    "level_min_width_sigma": 0.15,           # पट्ट्याची किमान रुंदी = σ_1H × हे
    "liquidity_eq_sigma": 0.15,              # equal highs / lows = σ_1H च्या इतक्या अपूर्णांकात
    "active_levels_max": 2,                  # trade-बाजूची जवळची levels
    "prior_level_atr_mult": 8.0,             # Q40: window आधीचे trend-degree Daily / Weekly swings — किंमतीपासून इतक्या ATR_D आत
    "prior_level_atr_n": 14,                 # Q40: ATR_D = window आधीच्या इतक्या Daily candles चा सरासरी true range
    "accept_closes": 3,                      # पलीकडे सलग इतके closes ⇒ acceptance (flip पक्का); कमी आणि परत ⇒ sweep ★
    "level_death_side": "role",              # Q2 / TL1 (✅ Abhi मंजूर): मृत्यू-swing चालू भूमिकेच्या बाजूचा (flipped support = supply ⇒ वरचा D2 H);
                                             # "role0" = जुना Q2 default (मूळ भूमिकेची बाजू, flip नंतरही) — revert साठी
    "level_flip_rule": "far_swing",          # KB K4 (Abhi, final): flip = पट्ट्यापलीकडे + पलीकडचा swing पार (trade ने) ⇒ FLIPPED; acceptance
                                             # (accept_closes) पण swing पार नाही ⇒ BROKEN (trade location नाही). पलीकडे swing नसेल ⇒ break नंतरचा
                                             # पहिला confirmed swing (Z-1a). FLIPPED zone पुन्हा तुटून त्याचा far swing पार ⇒ DEAD (दुसरा flip नाही,
                                             # Z-1f). "acceptance" = जुना spec §5.4 (acceptance ⇒ लगेच flip) — फक्त जुने tests / what-if;
                                             # level_death_side फक्त "acceptance" सोबत लागू
    "flip_pullback_inner_degree": 1,         # G4 context (a): pullback ची आतली रचना या swings2 degree च्या pivots वर (level_degree च्या एक खाली)
    "flip_pullback_vol_ratio": 1.0,          # G4 context (b): pullback ची सरासरी (normalised) FUT volume < हे × flip impulse ची ⇒ "lower" (फक्त fact)
    "flip_vol_min_coverage": 1.0,            # G4 context (b): impulse / pullback bars पैकी इतक्या bars ला volume हवा; कमी ⇒ (b) NA (फक्त fact)
    "vol_slot_sessions": 20,                 # Abhi (Z-1): प्रत्येक bar चा volume ÷ त्याच 15M slot चा मागच्या इतक्या sessions चा median (09:15 / close
                                             # bars नेहमी जड) — a2, c0 आणि in-zone facts सगळीकडे हाच normalised volume (सरासरी per bar, बेरीज नाही)
    "c0_volume_required": True,              # Abhi Z-1c: commitment (c0) ला FUT volume हवाच — NA ⇒ "data problem", entry नाही (volume शिवाय
                                             # grade-B trade नाही). False = जुनी प्रथा (NA ⇒ कमाल B) — फक्त volume नसलेले जुने synthetic tests
    "vol_slot_min_sessions": 10,             # slot history इतक्यापेक्षा कमी ⇒ NA (कारणासह); 10–19 ⇒ उपलब्ध sessions चा median (OPEN_QUESTIONS)
    "show_distance_sigma": 12.0,             # chart वर फक्त इतक्या σ_1H अंतरातली levels (snapshot मधून कधीच prune नाही)
    "chart_old_box_sessions": 126,           # §5.1 (Abhi): Daily chart window यापेक्षा लांब (≈ 6 महिने) ⇒ जुने correction boxes नाहीत (फक्त chart)
    "chart_leg_path_points": 15,             # Abhi review: trend leg ची chart रेषा कमाल इतक्या बिंदूंतून (लांब leg ⇒ मोठे swings च)
    "chart_atr_n": 14,                       # §5.7 (Abhi): caption मधलं अंतर ATR_D मध्ये — शेवटच्या इतक्या Daily candles चा सरासरी true range
    "liq_marks_per_side": 3,                 # chart वर प्रत्येक बाजूचे जवळचे liquidity pools (फक्त chart)
    # ③ Pullback (C पायरी)
    "k_reset_sigma": 0.25,                   # नवं टोक < हे × σ_1H ने सरकलं ⇒ तेच टोक (reset नाही)
    # ④ Power shift (C)
    "power_shift_min": 2,                    # (a)–(d) पैकी किमान इतके
    "power_a_rule": "relative",              # (a) Abhi (level bots): area मधल्या pullback candles चा सरासरी range < pullback च्या आधीच्या आणि impulse च्या
                                             #     candles पेक्षा (relative contraction); "strict3" = जुना "शेवटचे 3 सलग लहान" (फक्त what-if)
    "commit_dom_mult": 1.5,                  # ⑥ c0 (Abhi): commitment candle "dominant" ⇔ body ≥ इतके × study window ची सरासरी body (window दिला तरच)
    "study_min_bars": 4,                     # a2 zone study: window मध्ये किमान इतक्या candles (पहिला / दुसरा अर्धा तुलना)
    "pattern_eq_mr": 0.5,                    # a2 patterns: double / triple top-bottom ⇔ swing टोकं इतक्या × median range आत
    "ltf_choch": True,                       # ⑥ c1 (Abhi, REQUIRED): lower-timeframe CHoCH by close (15M setup ⇒ 5M; method.LTF_OF). False = फक्त what-if
    "power_overlap": 0.5,                    # (b) bodies overlap
    # ⑤ Trendline (grade फक्त)
    "tl_degree": 1,                          # K मधले counter pivots (D1 — §5.1 पाय-मोजणीचीच degree)
    "tl_touch_sigma": 0.15,                  # स्पर्श = रेघेपासून σ_1H × हे
    "tl_min_touches": 2,
    # ⑥ Commitment (C)
    "commit_body": 0.5,                      # body ≥ range च्या हे
    "commit_merge_max": 2,
    "commit_beyond": "close",                # Q16 (Abhi): किमान अट = मागच्या candle च्या close पलीकडे; "extreme" फक्त what-if
    "pin_wick_min": 0.5,                     # pin / hammer: level कडचा wick ≥ range च्या इतका
    "star_body_max": 0.3,                    # morning / evening star: मधली candle body ≤ range च्या इतकी
    "tweezer_tol": 0.1,                      # tweezer: दोन lows / highs मधला फरक ≤ सरासरी range × हे
    "commit_close_frac": 2 / 3,              # signal-bar: close range च्या trend-बाजूच्या तृतीयांशात (§5.2)
    "touch_window_bars": 3,                  # ③ "level मध्ये / लगत": शेवटच्या इतक्या 15M bars पैकी एकाने पट्ट्याला स्पर्श (commitment + आधीचा)
    "entry_start": "09:30", "entry_end": "15:15",   # entry bar ची सुरुवात start ≤ hm < end (15:15 चा bar बाजार बंदला close ⇒ नाही)
    "evidence_start": "09:15",               # Abhi (12 Oct): पुरावा-खिडकी (2-candle form / संदर्भ candle) सत्राच्या सुरुवातीपासून — opening candle चा
                                             # sweep + wick = पुरावा; entry खिडकी (entry_start) तशीच
    "entry_first_bar": True,                 # Abhi (13 Oct): सत्राची पहिली candle (evidence_start, 09:15) स्वतः commitment / entry candle असू शकते
                                             # (निर्णय तिच्या close ला, bar_end 09:30); False = जुनं (entry फक्त entry_start पासून — जुने reports)
    # candle वाचन / §5.3
    "candle_avg_n": 5,                       # "मोठा / लहान" = मागच्या इतक्या candles च्या सरासरीशी तुलना (§5.2)
    "doji_body_max": 0.1,                    # body / range < हे ⇒ doji
    "range_overlap_min": 0.5,                # §5.3: प्रत्येक जोडी range overlap ≥ हे
    "range_state_n": 3,                      # §5.3: 3+ overlapping candles
    "power_fallback_bars": 8,                # ④: K उघडी नसल्यास मागचे इतके bars
    "liquidity_lookback": 8,                 # §7 sweeps / traps: शेवटचे इतके bars
    # level score (फक्त माहिती, निर्णयात नाही)
    "score_daily_bonus": 1.0, "score_fresh_bonus": 1.0, "score_test_penalty": 0.5,
    # ⑦ Risk (C) — legacy फक्त
    "rr_step": False,                        # Abhi (13 Oct): R:R engine मधून काढला — setup निर्णय ⑥ (commitment + c1) वर संपतो; SL / target dashboard चे,
                                             # R:R = Abhi चा approval वेळचा निर्णय. True = जुना ⑦ (SL / target / R:R ≥ min_rr gate) — फक्त जुने reports /
                                             # golden tests reproduce; dashboard वर नाही
    "sl_buffer_sigma": 0.25,                 # SL buffer = σ_15M × हे (फक्त rr_step = True)
    "min_rr": 3.0,                           # फक्त rr_step = True
    # D Telegram trader view
    "entry_tick": 0.05,                      # B2: signal-bar extreme च्या इतक्या पलीकडे break (index tick)
    # §6 पुरावे ⇒ conviction (वजन; NA ⇒ बेरजेत नाही)
    "evidence_weights": {"level_star": 1.0, "fresh": 0.5, "power_shift": 1.5, "trap_sweep": 1.5, "second_attempt": 1.0,
                         "commit_strong": 1.0, "engulf": 0.5, "rsi_div": 0.5, "volume_low": 0.5, "pattern": 0.5,
                         "against_bodies": -1.0, "fourth_attempt": -1.5, "tl_break": 1.0},
    "conv_a": 0.6, "conv_b": 0.4, "conv_weak": 0.2,
    "max_attempts": 3,                       # §5.1: चौथा प्रयत्न (H4 / L4) ⇒ reversal शक्यता ⇒ trade नाही
}

# आकडा: (default, पर्याय, वर्ग, स्रोत)
REGISTER = {
    "engine_version": ("v22", "v21 / v22", "setting", "spec §4.A — जुना code shadow तुलना"),
    "daily_trend_mode": ("impulse", "impulse / minor", "Abhi नियम", "Q15 FINAL: trend = शेवटचा impulse leg, protected = त्याचा origin"),
    "corr_degree_rule": ("internal_pullback", "internal_pullback / ratio", "Abhi नियम", "Q22: रचनात्मक — impulse च्या सर्वात मोठ्या आतल्या pullback पलीकडे (प्रमाण नाही); ratio = जुना what-if"),
    "corr_degree_frac": (0.5, "0.382/0.5/0.618", "व्याख्या", "फक्त ratio what-if (Q22 आधीचा नियम)"),
    "daily_start_nature_gate": (True, "True / False", "Abhi नियम", "Q28: trend सुरुवात फक्त impulse-स्वभावाच्या पायाने (decision3/daily_legs, Q32 adapter)"),
    "q49_impulse_origin": ("complete_impulse", "complete_impulse / leg", "व्याख्या", "Q49 (a): counter-move correct करत असलेल्या impulse चा origin — विस्तार Abhi मंजूर (OPEN_QUESTIONS Q49)"),
    "daily_parent_gate": (True, "True / False", "Abhi नियम", "A1: impulse origin तुटला पण parent (trend सुरुवातीचा origin) टिकला ⇒ same-degree correction, flip नाही"),
    "range_after_trend": (True, "True / False", "Abhi नियम", "Q27: origin_broken + दोन समान H / L ⇒ RANGE; पट्टा ② / ③ ला"),
    "maturity_sigma_d": (0.5, "0.25/0.5/1.0", "अंदाज", "Q15 (5): target 'जवळ' = σ_D चा अपूर्णांक (पुरावा, gate नाही)"),
    "weekly_min_bars": (10, "—", "Abhi नियम", "daily_min_sessions सारखाच — weekly data अपुरा ⇒ UNKNOWN"),
    "daily_swing_method": ("pivot", "pivot / dc", "setting", "spec ① — pivot default; Q15: N = 1 / DC primary नाहीत (फक्त what-if)"),
    "daily_pivot_n": (2, "1/2/3", "अंदाज", "spec ① (N config default 2)"),
    "daily_dc_k": (1.0, "0.75/1.0/1.5", "अंदाज", "spec ① (k_D config)"),
    "daily_sigma_sessions": (10, "10/15/20", "अंदाज", "spec ① warm-up फक्त σ साठी, default 10"),
    "daily_min_sessions": (10, "—", "Abhi नियम", "spec §3: Daily unknown फक्त data अपुरा (≤ 10 sessions)"),
    "range_eq_sigma_d": (0.25, "0.15/0.25/0.35", "अंदाज", "spec ① RANGE: σ_D च्या अपूर्णांकात (config)"),
    "level_degree": (2, "—", "व्याख्या", "spec ② (a) 1H trend-degree swing = थर 1 D2"),
    "level_min_width_sigma": (0.15, "0.1/0.15/0.25", "अंदाज", "spec ② पट्टा किमान रुंदी σ_1H × अपूर्णांक"),
    "liquidity_eq_sigma": (0.15, "0.1/0.15/0.25", "अंदाज", "spec ② (d) equal highs / lows"),
    "active_levels_max": (2, "—", "Abhi नियम", "spec ② active level = जवळची 2"),
    "prior_level_atr_mult": (8.0, "5/8/12", "अंदाज", "Q40: window आधीचे महत्त्वाचे Daily / Weekly levels — किंमतीपासूनचं अंतर (ATR-scaled)"),
    "prior_level_atr_n": (14, "—", "व्याख्या", "Q40: ATR_D कालावधी (सामान्य 14)"),
    "accept_closes": (3, "2/3/4", "Abhi नियम", "spec §5.4 / §7.2 / §7.7: पलीकडे 3+ closes टिकले ⇒ acceptance; नाहीतर sweep"),
    "level_death_side": ("role", "role / role0", "Abhi नियम", "Q2 / TL1 (Abhi मंजूर): spec ② (c) flip = भूमिका उलट; मृत्यू = चालू भूमिकेच्या पलीकडचा structural swing close ने तुटला"),
    "level_flip_rule": ("far_swing", "far_swing / acceptance", "Abhi नियम", "KB K4 / G4 (Abhi final, Z-1): flip = पलीकडे + पलीकडचा swing पार (swing नसेल ⇒ break नंतरचा पहिला confirmed swing); नाहीतर BROKEN; flipped zone दुसऱ्यांदा ⇒ DEAD"),
    "flip_pullback_inner_degree": (1, "0 / 1", "व्याख्या", "KB G4 context (a): pullback ची रचना एक degree खालच्या pivots वर (daily_legs.classify inner_seq) — फक्त fact"),
    "flip_pullback_vol_ratio": (1.0, "—", "setting", "KB G4 context (b) 'lower FUT volume than the impulse' ⇒ ratio < 1.0 — फक्त fact, gate नाही (Abhi Z-1)"),
    "flip_vol_min_coverage": (1.0, "—", "setting", "KB G4 context (b): volume NA कधीच शांत 'lower' नाही — सगळ्या bars ला volume हवा"),
    "vol_slot_sessions": (20, "—", "Abhi नियम", "Abhi (Z-1 volume): bar volume ÷ त्याच time-of-day slot चा मागच्या 20 sessions चा median"),
    "c0_volume_required": (True, "True / False", "Abhi नियम", "Abhi Z-1c: FUT volume नाही = data error ⇒ entry नाही; False फक्त जुने volume-नसलेले tests"),
    "vol_slot_min_sessions": (10, "5 / 10 / 20", "अंदाज", "slot history किमान (legs2 rvol_min_sessions सारखं); कमी ⇒ NA — OPEN_QUESTIONS Z-1h"),
    "liq_marks_per_side": (3, "2/3/5", "अंदाज (फक्त chart)", "spec §7.6 pools लहान खुणा — गर्दी टाळायला; क्रम PWH/PWL > PDH/PDL > equal > swing (liquidity.pool_marks prio, फक्त display)"),
    "show_distance_sigma": (12.0, "8/12/20", "अंदाज (फक्त chart)", "spec ② दूरची levels chart वर लपवा"),
    "chart_old_box_sessions": (126, "—", "अंदाज (फक्त chart)", "§5.1 (Abhi): '~6 महिन्यांपेक्षा लांब window ⇒ जुने boxes नाहीत' (≈ 126 sessions)"),
    "chart_atr_n": (14, "—", "व्याख्या", "§5.7 caption: ATR_D कालावधी (सामान्य 14)"),
    "chart_leg_path_points": (15, "≥ 6 (code मध्ये किमान 6)", "अंदाज (फक्त chart)", "Abhi review: लांब leg 207-wave tracing नको — leg चे स्वतःचे मोठे swings (≤ ~15 बिंदू)"),
    "k_reset_sigma": (0.25, "—", "Abhi नियम", "spec ③ < 0.25 σ_1H ⇒ reset नाही"),
    "power_shift_min": (2, "2/3", "Abhi नियम", "spec ④ किमान 2 (config)"),
    "power_a_rule": ("relative", "relative / strict3", "Abhi नियम", "level bots spec: (a) relative contraction — 'नेमके 3 सलग लहान' ही आपली यांत्रिक आवृत्ती होती"),
    "commit_dom_mult": (1.5, "1.25/1.5/2.0", "अंदाज", "level bots c0: 'clearly larger than the window average' — आकडा Abhi ने ठरवायचा (OPEN_QUESTIONS LB8)"),
    "study_min_bars": (4, "—", "व्याख्या", "a2: पहिला / दुसरा अर्धा तुलना करायला किमान candles"),
    "pattern_eq_mr": (0.5, "0.3/0.5/0.75", "अंदाज", "a2: double / triple top-bottom टोकं median range च्या इतक्या आत"),
    "ltf_choch": (True, "True / False (what-if)", "Abhi नियम", "LEVEL_BOTS_CONFIRMATION c1: LTF CHoCH by close आवश्यक; mapping 1H/15M ⇒ 5M, 5M ⇒ 1M (method.LTF_OF); swings = साधे 1-bar pivots (zone_pattern सारखेच)"),
    "power_overlap": (0.5, "—", "Abhi नियम", "spec ④ (b) ≥ 50%"),
    "tl_degree": (1, "0/1", "व्याख्या", "spec ⑤ 'K ची आतली रेघ' — K चे पाय D1 (Q20)"),
    "tl_touch_sigma": (0.15, "0.1/0.15/0.25", "अंदाज", "spec ⑤ स्पर्श सहनशीलता"),
    "tl_min_touches": (2, "—", "Abhi नियम", "spec ⑤ K चे ≥ 2 स्पर्श"),
    "commit_body": (0.5, "—", "Abhi नियम", "spec ⑥ body ≥ 50% range"),
    "commit_merge_max": (2, "1/2", "Abhi नियम", "spec ⑥ ≤ 2 merged"),
    "commit_beyond": ("close", "close / extreme", "Abhi नियम", "Q16: किमान अट close पलीकडे; extreme पलीकडे = grade A (extreme मोड फक्त what-if)"),
    "pin_wick_min": (0.5, "0.5/0.6/0.66", "व्याख्या", "Q16 pin bar: लांब wick level मध्ये (range च्या निम्म्याहून)"),
    "star_body_max": (0.3, "0.25/0.3/0.4", "व्याख्या", "Q16 star: मधली candle लहान body"),
    "tweezer_tol": (0.1, "0.05/0.1/0.2", "व्याख्या", "Q16 tweezer: दोन टोकं जवळपास समान (range चा अपूर्णांक)"),
    "commit_close_frac": ("2/3", "—", "व्याख्या", "spec §5.2 close trend-बाजूच्या तृतीयांशात"),
    "touch_window_bars": (3, "1/2/3", "व्याख्या", "spec ⑥ 'level मध्ये / लगत' + §6.2 H2 'वर / जवळ' (Q18)"),
    "entry_start / entry_end": ("09:30 / 15:15", "settings", "setting", "spec ⑥ वेळ-खिडकी फक्त settings; v2.1 प्रमाणे end exclusive"),
    "entry_first_bar": (True, "True / False", "Abhi नियम", "Abhi 13 Oct (12 Oct chart): 09:15 candle = entry candle शक्य; setup तिच्या "
                        "close ला (bar_end 09:30), entry 09:30. False = जुनं (09:15 फक्त पुरावा)"),
    "evidence_start": ("09:15", "09:15 / entry_start", "व्याख्या", "Abhi (12 Oct): NSE सत्राची सुरुवात — opening candle पुरावा म्हणून मोजायची, entry नाही"),
    "candle_avg_n": (5, "—", "Abhi नियम", "spec §5.2 मागच्या 5 candles ची सरासरी"),
    "doji_body_max": (0.1, "0.05/0.1/0.15", "अंदाज", "spec §5.2 / §5.3 doji (body लहान)"),
    "range_overlap_min": (0.5, "—", "व्याख्या", "spec §5.3 'बहुतांश overlap' (≥ 50%)"),
    "range_state_n": (3, "—", "Abhi नियम", "spec §5.3 3+ overlapping candles"),
    "power_fallback_bars": (8, "—", "व्याख्या", "④ K उघडी नसताना (chart / पुरावा) — निर्णयात ③ आधी लागतो"),
    "liquidity_lookback": (8, "4/8/12", "अंदाज", "spec §7.2 'लवकर' परत (काही candles)"),
    "score_daily_bonus / score_fresh_bonus / score_test_penalty": ("1 / 1 / 0.5", "—", "अंदाज",
                                                                   "spec §5.4 ★ provenance / freshness; निर्णयात नाही"),
    "rr_step": (False, "False / True (legacy)", "Abhi नियम", "Abhi 13 Oct: R:R removed from the engine; R:R is Abhi's own judgement at "
                "approval; SL / target from dashboard. True = जुना ⑦ (फक्त reproduce, dashboard वर नाही)"),
    "sl_buffer_sigma": (0.25, "0.1/0.25/0.5", "अंदाज", "spec ⑦ buffer σ_15M × अपूर्णांक (फक्त rr_step = True)"),
    "min_rr": (3.0, "—", "Abhi नियम", "spec ⑦ R:R < 3 ⇒ trade नाही (फक्त rr_step = True; Abhi 13 Oct ने default मधून काढला)"),
    "entry_tick": (0.05, "—", "व्याख्या", "spec §5.2 B2 'signal-bar extreme च्या 1 tick पलीकडे' (Q21)"),
    "evidence_weights": ("§6.3 यादी", "±0.5", "अंदाज", "spec §6.3–6.4 पुराव्यांचं वजन (Abhi च्या E1–E4 खुणांशी जुळवायचं, निकाल पाहून नाही)"),
    "conv_a / conv_b / conv_weak": ("0.6 / 0.4 / 0.2", "±0.1", "अंदाज", "spec §6.4 conviction स्तरांच्या सीमा"),
    "max_attempts": (3, "—", "Abhi नियम", "spec §5.1 H4 / L4 ⇒ trade नाही"),
}

TRENDS = ("UP", "DOWN", "RANGE", "NEUTRAL", "UNKNOWN")


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update(overrides or {})
    return s
