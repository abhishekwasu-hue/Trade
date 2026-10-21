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
    "daily_leg_read": "elliott",             # Abhi 21 Oct: a Daily leg's nature — "compare" (legs_compare: bodies / overlap vs the
                                             # neighbouring legs of the same degree) or "elliott" (5-wave / zigzag / flat rules + legs2 C
                                             # percentiles; today's reading, kept as the what-if). Default flips only with Abhi's ✅.
    "daily_parent_gate": True,               # A1 (Abhi review): counter impulse trend उलटवत नाही जोपर्यंत trend च्या सुरुवातीचा origin close ने तुटत नाही
    "q49_impulse_origin": "complete_impulse",  # Q49 (a) origin: "complete_impulse" = चालू leg पूर्ण 5-wave चा wave 5 असेल तर त्या
                                             # impulse ची सुरुवात (Abhi मंजुरी बाकी); "leg" = साधं वाचन (चालू impulse leg चा origin)
    "range_after_trend": True,               # Q27 (Abhi): origin तुटला + दोन समान H आणि दोन समान L ⇒ RANGE (कडांवर trade)
    "daily_range_rule": "structure",         # Abhi 21 Oct: RANGE = दोन कडांपलीकडे (एक swing H + एक swing L) नंतरचे swings दोन्ही बाजूंनी
                                             # नवा टोक करू शकत नाहीत (कडेपलीकडे close नाही; wick = sweep, आत); संपते = कडेपलीकडे close +
                                             # पलीकडे swing (breakout = context). "c13" = जुनं (दोन समान H + दोन समान L) — what-if
    "weekly_min_bars": 10,                   # weekly पालक: यापेक्षा कमी weekly candles ⇒ weekly UNKNOWN
    "daily_swing_method": "pivot",           # pivot (N bars दोन्ही बाजूला) / dc (k_D × σ_D) — Q15: pivot; dc फक्त what-if
    "daily_pivot_n": 2,                      # Abhi L1-c: N = 2 provisional (recorded); तो नंतर dashboard वरून बदलू शकतो
    "daily_dc_k": 1.0,                       # θ_D = k_D × σ_D (σ_D = Daily range median)
    "daily_sigma_sessions": 10,              # σ_D साठी Daily candles (warm-up फक्त σ साठी)
    "daily_min_sessions": 10,                # यापेक्षा कमी (≤) Daily candles ⇒ trend UNKNOWN (data अपुरा)
    "range_eq_sigma_d": 0.25,                # RANGE: दोन H आणि दोन L "जवळपास समान" = σ_D च्या इतक्या अपूर्णांकात
    # ② Level (1H)
    "swing_k": None,                         # Abhi calibration (layer 1 ✅): None = swings2 चा approved scale (D1 = 4, D2 = 6); {1: k, 2: k} = advanced
                                             # dashboard override (engine च्या swings साठी); swing चं महत्त्व = market च्या सामान्य हालचालीशी (σ) तुलना
    "level_degree": 2,                       # swings2 degree = 1H trend-degree (D2)
    "div_degree_rule": "zone",               # Abhi L5-a: RSI divergence between the pushes INSIDE the move into the zone (the highest degree
                                             # with two pushes there); the zone's own degree reported too. "all" = the old D0–D2 read (what-if)
    "level_min_width_sigma": 0.0,            # Abhi Z-1x: zone = त्या base / reaction candles चा स्वतःचा wick-to-body — आकड्याने रुंद नाही (0).
                                             # > 0 = जुनी किमान रुंदी (σ_1H × हे) — फक्त जुने tests / what-if
    "liquidity_eq_sigma": 0.15,              # equal highs / lows = σ_1H च्या इतक्या अपूर्णांकात
    "active_levels_max": 2,                  # RANGE: प्रत्येक कडेचे जवळचे levels (UP / DOWN साठी watch_levels_max)
    "watch_levels_max": 3,                   # Abhi B2 (watch-list): trend दिशेचे पुढचे सगळे counter-side zones armed, जवळचे पहिले, इतके
                                             # (KB K4 chart display: किंमतीवर / खाली कमाल 3 bands) — zone तुटला ⇒ पुढचा आधीच armed
    "wave_gates": False,                     # Abhi B1 (trader's patience): wave count / maturity / projections फक्त context — maturity cap,
                                             # mature step-down, origin_risk cap, §5.1 first-leg cap, 4th-attempt no-trade, leg-count पुरावा
                                             # नाहीत. True = जुने gates (फक्त जुने tests / what-if)
    "prior_level_rule": "all",               # Abhi's method: every trend-degree prior Daily / Weekly swing is an area (role = its side of price);
                                             # no distance filter. "atr" = जुनं (prior_level_atr_mult × ATR_D अंतर) — फक्त what-if
    "liquidity_rule": "equal",               # Abhi's method §3 "equal": later extreme reaches the earlier swing's band, not beyond. "sigma" = जुनं
    "prior_level_atr_mult": 8.0,             # Q40: window आधीचे trend-degree Daily / Weekly swings — किंमतीपासून इतक्या ATR_D आत
    "prior_level_atr_n": 14,                 # Q40: ATR_D = window आधीच्या इतक्या Daily candles चा सरासरी true range
    "level_merge": False,                    # Abhi Z-1u: पट्टे फक्त बांधायचे, merge ने रुंद नाहीत (प्रत्येक timeframe वेगळा). True = जुनं
                                             # merge + widen — फक्त जुने synthetic tests / what-if (dashboard वर नाही)
    "zone_visit_rule": "structure",          # method §3 Visit: संपते फक्त रचनेने — area पासून दूर swing, किंवा अपयशी commitment बाहेर close.
                                             # "close_away" (Z-1v: बाहेर एक close) / "touch_window" = जुनं — फक्त जुने tests / what-if
    "trade_band_max_sigma": None,            # Abhi Z-1x (final): zone रुंदीला आकड्याची मर्यादा नाही — रुंद दिसणारा zone = दोन bases एकत्र ⇒ रचना
                                             # दुरुस्त (Z-1u). फक्त what-if (× σ_1H) — dashboard वर नाही
    "break_rule": "structure",               # Abhi's method §3: broken = close beyond AND a swing formed beyond; sweep = back before any swing
                                             # beyond. "closes" = जुनं (accept_closes सलग closes) — फक्त जुने tests / what-if
    "accept_closes": 3,                      # फक्त break_rule = "closes" (legacy what-if): पलीकडे सलग इतके closes ⇒ acceptance
    "level_death_side": "role",              # Q2 / TL1 (✅ Abhi मंजूर): मृत्यू-swing चालू भूमिकेच्या बाजूचा (flipped support = supply ⇒ वरचा D2 H);
                                             # "role0" = जुना Q2 default (मूळ भूमिकेची बाजू, flip नंतरही) — revert साठी
    "level_flip_rule": "far_swing",          # KB K4 (Abhi, final): flip = पट्ट्यापलीकडे + पलीकडचा swing पार (trade ने) ⇒ FLIPPED; acceptance
                                             # (accept_closes) पण swing पार नाही ⇒ BROKEN (trade location नाही). पलीकडे swing नसेल ⇒ break नंतरचा
                                             # पहिला swing confirm होताच FLIPPED (Z-1s; तोडायची गरज नाही). FLIPPED zone पुन्हा तुटून त्याचा far swing
                                             # गाठला (पार / नसेल ⇒ break नंतरचा पहिला swing confirm) ⇒ DEAD (दुसरा flip नाही,
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
    "vol_gap_max_frac": 0.5,                 # Abhi RF-2 (b): in-zone window (arm … commitment) च्या इतक्यापेक्षा जास्त bars ला FUT volume नाही
                                             # ⇒ data problem: entry नाही + Telegram "data problem: FUT volume gaps" (NIFTY / BANKNIFTY, दिवसातून
                                             # एकदा); कमी ⇒ volume असलेल्या bars ची सरासरी + "gaps n/m" नोंद
    "show_distance_sigma": 12.0,             # chart वर फक्त इतक्या σ_1H अंतरातली levels (snapshot मधून कधीच prune नाही)
    "chart_old_box_sessions": 126,           # §5.1 (Abhi): Daily chart window यापेक्षा लांब (≈ 6 महिने) ⇒ जुने correction boxes नाहीत (फक्त chart)
    "chart_leg_path_points": 15,             # Abhi review: trend leg ची chart रेषा कमाल इतक्या बिंदूंतून (लांब leg ⇒ मोठे swings च)
    "chart_atr_n": 14,                       # §5.7 (Abhi): caption मधलं अंतर ATR_D मध्ये — शेवटच्या इतक्या Daily candles चा सरासरी true range
    "liq_marks_per_side": 3,                 # chart वर प्रत्येक बाजूचे जवळचे liquidity pools (फक्त chart)
    # ③ Pullback (C पायरी)
    # ④ Power shift (C)
    "power_shift_min": 2,                    # (a)–(d) पैकी किमान इतके
    "power_a_rule": "relative",              # (a) Abhi (level bots): area मधल्या pullback candles चा सरासरी range < pullback च्या आधीच्या आणि impulse च्या
                                             #     candles पेक्षा (relative contraction); "strict3" = जुना "शेवटचे 3 सलग लहान" (फक्त what-if)
    "c0_dominance": True,                    # ⑥ c0 (Abhi): commitment candle dominant ⇔ body visit मधल्या प्रत्येक इतर candle पेक्षा मोठी (तुलना,
                                             # आकडा नाही). False = फक्त जुने synthetic fixtures (dominant candle नसलेले) / what-if
    "fast_form_rule": "push_body",           # method §3 Handover fast form: dominant opposite candle closes beyond the push candle's BODY;
                                             # "engulf" = जुनं (#329: body झाकते + candle 1 च्या टोकापलीकडे close) — what-if
    "slow_form_rule": "method",              # method §3 slow form: trend-side bodies ↑, opposite ↓, volume trend-side ला झुकतो; "majority" = जुनं
    "absorption_rule": "method",             # method §3: opposite side लहान candles मध्ये येत राहते आणि किंमत दूर जात नाही; "strengthening" = जुनं
    "commit_volume_rule": "approach_and_opposite",   # method §3 Commitment (Abhi L3-c): approach leg + visit मधल्या opposite candles च्या
                                             # सरासरीपेक्षा जास्त (push + commitment वगळून); "opposite" = जुनं (#329, opposite नाही ⇒ grade cap B)
    "volume_baseline": "raw",                # method §3 Volume: raw bars; "slot" = जुनं time-of-day slot baseline (Z-1) — what-if
    "candle_rule": "compare",                # method §3: candle forms / doji / "big" by comparing body and wicks (big = vs the visit); "ratio" = जुनं
    "session_windows": False,                # method P2: एकच सलग chart — 2-candle forms दिवस ओलांडतात; entry तास = operational schedule (engine);
                                             # True = जुनं (form खिडकी + entry खिडकी commitment मध्ये) — what-if
    "verdict_rule": "method",               # method §4 / §5: required set ⇒ enter; label A = + ≥ 1 confirming piece, B = required only;
                                             # evidence listed, never scored; "score" = जुनं (evidence_weights / conv_* / ④ / §5.3) what-if
    "line_rule": "logic",                    # method §3 Lines: touch = wick reaches the line, body on its side; two reactions = a line;
                                             # confluence = the line passes through the area, or a reaction out of it turns at the line
                                             # (Abhi 4 B) ⇒ labelled "confluence: line", never a new band; "sigma" = जुनं
    "sharp_reversal_handover": True,         # Abhi Z-1z: zone मध्ये push नाकारला + dominant उलट candle ने गिळला = handover (तुलना, आकडा नाही)
    "pattern_eq_mr": 0.5,                    # a2 patterns: double / triple top-bottom ⇔ swing टोकं इतक्या × median range आत
    "a2_handover_required": True,            # Abhi Z-1m: a2 handover अनिवार्य (trade-बाजू वाढते + उलट बाजू दमते, zone मध्ये); क्रम a2 → c1 → c0.
                                             # False = जुनं (a2 फक्त absorption ⇒ वाट) — जुने tests / what-if
    "range_state_gate": False,               # Abhi Z-1j: §5.3 range अवस्था (overlap + doji) = context fact, gate नाही (sideways = handover study;
                                             # range trades चालतात). True = जुना gate (फक्त जुने tests)
    "range_state_rule": "structure",         # Abhi 21 Oct (decided): row चा `range_state` = रचनेतून, प्रत्येक TF (W / D / 1H / 15M;
                                             # daily_range_rule ची व्याख्या; कडा = range_edges areas). "overlap" = जुनं (§5.3 overlap + doji,
                                             # फक्त verdict_rule = score) — admin diagnostics / what-if
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
    "evidence_start": "09:15",               # Abhi: पुरावा-खिडकी (2-candle form / संदर्भ candle) सत्राच्या सुरुवातीपासून — opening candle चा
                                             # sweep + wick = पुरावा; entry खिडकी (entry_start) तशीच
    "entry_first_bar": True,                 # Abhi: सत्राची पहिली candle (evidence_start, 09:15) स्वतः commitment / entry candle असू शकते
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
    "rr_step": False,                        # Abhi: R:R engine मधून काढला — setup निर्णय ⑥ (commitment + c1) वर संपतो; SL / target dashboard चे,
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
    "daily_leg_read": ("elliott", "compare / elliott", "Abhi नियम",
                       "Abhi 21 Oct: Daily leg nature (Q28 / Q36 nature gate, A1 counter-move, Q49 origin, continuation start, G4 approach) "
                       "by comparison with the neighbouring legs (decision3/legs_compare) instead of Elliott counts + legs2 percentiles; "
                       "elliott = today's reading (what-if). Default stays elliott until Abhi's ✅ at deploy"),
    "daily_parent_gate": (True, "True / False", "Abhi नियम", "A1: impulse origin तुटला पण parent (trend सुरुवातीचा origin) टिकला ⇒ same-degree correction, flip नाही"),
    "range_after_trend": (True, "True / False", "Abhi नियम", "Q27: origin_broken + दोन समान H / L ⇒ RANGE; पट्टा ② / ③ ला"),
    "daily_range_rule": ("structure", "structure / c13", "Abhi नियम", "Abhi 21 Oct: a range from structure — after a swing high H and a "
                         "swing low L the later swings fail to make a new extreme on both sides (no close beyond the edge; a wick = a sweep, "
                         "inside); it ends at a close beyond an edge + a swing beyond (breakout = context). Daily / Weekly fold (where C-13 "
                         "equal declared RANGE) and decision3/range_edges (1H / 15M). c13 = two equal highs + two equal lows (what-if)"),
    "weekly_min_bars": (10, "—", "Abhi नियम", "daily_min_sessions सारखाच — weekly data अपुरा ⇒ UNKNOWN"),
    "daily_swing_method": ("pivot", "pivot / dc", "setting", "spec ① — pivot default; Q15: N = 1 / DC primary नाहीत (फक्त what-if)"),
    "daily_pivot_n": (2, "1/2/3", "Abhi नियम",
                      "Abhi L1-c: provisional N = 2; dashboard setting via the live-switches track (spec ① N config default 2)"),
    "daily_dc_k": (1.0, "0.75/1.0/1.5", "अंदाज", "spec ① (k_D config)"),
    "daily_sigma_sessions": (10, "10/15/20", "अंदाज", "spec ① warm-up फक्त σ साठी, default 10"),
    "daily_min_sessions": (10, "—", "Abhi नियम", "spec §3: Daily unknown फक्त data अपुरा (≤ 10 sessions)"),
    "range_eq_sigma_d": (0.25, "0.15/0.25/0.35", "अंदाज", "spec ① RANGE: σ_D च्या अपूर्णांकात (config)"),
    "swing_k": ("None (swings2: D1 = 4, D2 = 6)", "swings2 K_OPTIONS", "Abhi नियम",
                "Abhi calibration (layer 1 ✅): approved swings2 D1 / D2 = swing ची व्याख्या; scale = त्यांचं visual calibration (advanced dashboard)"),
    "level_degree": (2, "—", "व्याख्या", "spec ② (a) 1H trend-degree swing = थर 1 D2"),
    "div_degree_rule": ("zone", "zone / all", "Abhi नियम",
                        "Abhi L5-a: zone मध्ये येणाऱ्या चालीच्या आतले लागोपाठचे pushes, किमान दोन pushes दाखवणारी सर्वात मोठी degree; चालीआधीचा swing कधीच नाही; zone degree माहिती"),
    "level_min_width_sigma": (0.0, "0 (Abhi) / जुना 0.15", "Abhi नियम", "Abhi Z-1x: zone = base candles चा स्वतःचा पट्टा, आकड्याने रुंद नाही"),
    "liquidity_eq_sigma": (0.15, "0.1/0.15/0.25", "अंदाज", "spec ② (d) equal highs / lows"),
    "active_levels_max": (2, "—", "Abhi नियम", "spec ② active level = जवळची 2"),
    "prior_level_rule": ("all", "all / atr (legacy)", "Abhi नियम", "Abhi's method: every trend-degree prior swing is an area; no ATR distance"),
    "liquidity_rule": ("equal", "equal / sigma (legacy)", "Abhi नियम", "Abhi's method §3: equal = the later extreme reaches the earlier swing's band, not beyond"),
    "prior_level_atr_mult": (8.0, "5/8/12", "अंदाज", "Q40: window आधीचे महत्त्वाचे Daily / Weekly levels — किंमतीपासूनचं अंतर (ATR-scaled)"),
    "prior_level_atr_n": (14, "—", "व्याख्या", "Q40: ATR_D कालावधी (सामान्य 14)"),
    "level_merge": (False, "False / True (legacy)", "Abhi नियम", "Abhi Z-1u: bands built, never widened; True फक्त जुने tests / what-if"),
    "zone_visit_rule": ("structure", "structure / close_away / touch_window (legacy)", "Abhi नियम", "Abhi's method §3 Visit: ends only by "
                        "structure — a swing built away from the area, or a failed commitment closing outside; time never ends it"),
    "trade_band_max_sigma": (None, "None / × σ_1H (what-if)", "Abhi नियम", "Abhi Z-1x (final): रुंदीला आकड्याची मर्यादा नाही — रचना दुरुस्त करा"),
    "break_rule": ("structure", "structure / closes (legacy)", "Abhi नियम", "Abhi's method §3: broken = a close beyond + a swing formed beyond; no close count"),
    "accept_closes": (3, "2/3/4", "Abhi नियम", "spec §5.4 / §7.2 / §7.7: पलीकडे 3+ closes टिकले ⇒ acceptance; नाहीतर sweep"),
    "level_death_side": ("role", "role / role0", "Abhi नियम", "Q2 / TL1 (Abhi मंजूर): spec ② (c) flip = भूमिका उलट; मृत्यू = चालू भूमिकेच्या पलीकडचा structural swing close ने तुटला"),
    "a2_handover_required": (True, "True / False", "Abhi नियम", "Abhi Z-1m: handover (a2) अनिवार्य, क्रम a2 → c1 → c0; False फक्त जुने tests"),
    "range_state_gate": (False, "False / True", "Abhi नियम", "Abhi Z-1j: §5.3 range अवस्था context fact फक्त; True फक्त जुने tests"),
    "range_state_rule": ("structure", "structure / overlap", "Abhi नियम", "Abhi 21 Oct (decided): the row's range_state from structure "
                         "per timeframe (daily_range_rule's definition on that TF's swings; edges = decision3/range_edges areas; breakout = "
                         "context only). overlap = legacy §5.3 overlap + doji (admin diagnostics; range_state_gate only with it)"),
    "watch_levels_max": (3, "—", "Abhi नियम", "Abhi B2 watch-list (final) + KB K4 chart display (≤ 3 bands above / below price)"),
    "wave_gates": (False, "False / True", "Abhi नियम", "Abhi B1: no wave prediction — wave / maturity / C = a context only; True फक्त जुने tests"),
    "level_flip_rule": ("far_swing", "far_swing / acceptance", "Abhi नियम", "KB K4 / G4 (Abhi final, Z-1): flip = पलीकडे + पलीकडचा swing पार (swing नसेल ⇒ break नंतरचा पहिला swing confirm होताच — Z-1s, तोडायची गरज नाही); नाहीतर BROKEN; flipped zone दुसऱ्यांदा ⇒ DEAD"),
    "flip_pullback_inner_degree": (1, "0 / 1", "व्याख्या", "KB G4 context (a): pullback ची रचना एक degree खालच्या pivots वर (daily_legs.classify inner_seq) — फक्त fact"),
    "flip_pullback_vol_ratio": (1.0, "—", "setting", "KB G4 context (b) 'lower FUT volume than the impulse' ⇒ ratio < 1.0 — फक्त fact, gate नाही (Abhi Z-1)"),
    "flip_vol_min_coverage": (1.0, "—", "setting", "KB G4 context (b): volume NA कधीच शांत 'lower' नाही — सगळ्या bars ला volume हवा"),
    "vol_slot_sessions": (20, "—", "Abhi नियम", "Abhi (Z-1 volume): bar volume ÷ त्याच time-of-day slot चा मागच्या 20 sessions चा median"),
    "c0_volume_required": (True, "True / False", "Abhi नियम", "Abhi Z-1c: FUT volume नाही = data error ⇒ entry नाही; False फक्त जुने volume-नसलेले tests"),
    "vol_slot_min_sessions": (10, "5 / 10 / 20", "अंदाज", "slot history किमान (legs2 rvol_min_sessions सारखं); कमी ⇒ NA — OPEN_QUESTIONS Z-1h"),
    "vol_gap_max_frac": (0.5, "0–1 (share of the window's bars)", "Abhi नियम", "Abhi RF-2 (b): FUT volume gaps > इतका भाग ⇒ data problem, "
                         "entry नाही (default 50% — Abhi चा आकडा); commitment bar चाच volume नाही ⇒ Z-1c (entry नाही)"),
    "liq_marks_per_side": (3, "2/3/5", "अंदाज (फक्त chart)", "spec §7.6 pools लहान खुणा — गर्दी टाळायला; क्रम PWH/PWL > PDH/PDL > equal > swing (liquidity.pool_marks prio, फक्त display)"),
    "show_distance_sigma": (12.0, "8/12/20", "अंदाज (फक्त chart)", "spec ② दूरची levels chart वर लपवा"),
    "chart_old_box_sessions": (126, "—", "अंदाज (फक्त chart)", "§5.1 (Abhi): '~6 महिन्यांपेक्षा लांब window ⇒ जुने boxes नाहीत' (≈ 126 sessions)"),
    "chart_atr_n": (14, "—", "व्याख्या", "§5.7 caption: ATR_D कालावधी (सामान्य 14)"),
    "chart_leg_path_points": (15, "≥ 6 (code मध्ये किमान 6)", "अंदाज (फक्त chart)", "Abhi review: लांब leg 207-wave tracing नको — leg चे स्वतःचे मोठे swings (≤ ~15 बिंदू)"),
    "power_shift_min": (2, "2/3", "Abhi नियम", "spec ④ किमान 2 (config)"),
    "power_a_rule": ("relative", "relative / strict3", "Abhi नियम", "level bots spec: (a) relative contraction — 'नेमके 3 सलग लहान' ही आपली यांत्रिक आवृत्ती होती"),
    "c0_dominance": (True, "True / False", "Abhi नियम", "Abhi (final): dominant = visit मधल्या प्रत्येक इतर candle पेक्षा मोठी body — तुलना, आकडा नाही"),
    "fast_form_rule": ("push_body", "push_body / engulf (legacy)", "Abhi नियम", "method §3: closes beyond the push candle's body"),
    "slow_form_rule": ("method", "method / majority (legacy)", "Abhi नियम", "method §3: trend side grows, opposite shrinks, volume tilts"),
    "absorption_rule": ("method", "method / strengthening (legacy)", "Abhi नियम", "method §3: opposite side in small candles, price stuck"),
    "commit_volume_rule": ("approach_and_opposite", "approach_and_opposite / opposite (legacy)", "Abhi नियम",
                           "method §3 (Abhi L3-c): above the AVERAGE of the approach leg + the visit's opposite side; push + commitment excluded"),
    "volume_baseline": ("raw", "raw / slot (legacy)", "Abhi नियम", "method §3 Volume: raw bars, no time-slot baselines"),
    "candle_rule": ("compare", "compare / ratio (legacy)", "Abhi नियम", "method §3: body and wicks compared, never ratios; big = vs the visit"),
    "session_windows": (False, "False / True (legacy)", "Abhi नियम", "method P2: no session / day split in reading; entry hours = operational"),
    "verdict_rule": ("method", "method / score (legacy)", "Abhi नियम", "method §4 / §5: enter on the required set; A / B by confirming evidence; no scores"),
    "line_rule": ("logic", "logic / sigma (legacy)", "Abhi नियम", "method §3 Lines: comparisons with the candle, no σ tolerance or touch count"),
    "sharp_reversal_handover": (True, "—", "Abhi नियम", "Abhi Z-1z: zone मध्ये push नाकारला आणि dominant उलट candle ने लगेच गिळला = handover"),
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
    "entry_first_bar": (True, "True / False", "Abhi नियम", "Abhi (chart review): 09:15 candle = entry candle शक्य; setup तिच्या "
                        "close ला (bar_end 09:30), entry 09:30. False = जुनं (09:15 फक्त पुरावा)"),
    "evidence_start": ("09:15", "09:15 / entry_start", "व्याख्या", "Abhi: NSE सत्राची सुरुवात — opening candle पुरावा म्हणून मोजायची, entry नाही"),
    "candle_avg_n": (5, "—", "Abhi नियम", "spec §5.2 मागच्या 5 candles ची सरासरी"),
    "doji_body_max": (0.1, "0.05/0.1/0.15", "अंदाज", "spec §5.2 / §5.3 doji (body लहान)"),
    "range_overlap_min": (0.5, "—", "व्याख्या", "spec §5.3 'बहुतांश overlap' (≥ 50%)"),
    "range_state_n": (3, "—", "Abhi नियम", "spec §5.3 3+ overlapping candles"),
    "power_fallback_bars": (8, "—", "व्याख्या", "④ K उघडी नसताना (chart / पुरावा) — निर्णयात ③ आधी लागतो"),
    "liquidity_lookback": (8, "4/8/12", "अंदाज", "spec §7.2 'लवकर' परत (काही candles)"),
    "score_daily_bonus / score_fresh_bonus / score_test_penalty": ("1 / 1 / 0.5", "—", "अंदाज",
                                                                   "spec §5.4 ★ provenance / freshness; निर्णयात नाही"),
    "rr_step": (False, "False / True (legacy)", "Abhi नियम", "Abhi: R:R removed from the engine; R:R is Abhi's own judgement at "
                "approval; SL / target from dashboard. True = जुना ⑦ (फक्त reproduce, dashboard वर नाही)"),
    "sl_buffer_sigma": (0.25, "0.1/0.25/0.5", "अंदाज", "spec ⑦ buffer σ_15M × अपूर्णांक (फक्त rr_step = True)"),
    "min_rr": (3.0, "—", "Abhi नियम", "spec ⑦ R:R < 3 ⇒ trade नाही (फक्त rr_step = True; Abhi ने default मधून काढला)"),
    "entry_tick": (0.05, "—", "व्याख्या", "spec §5.2 B2 'signal-bar extreme च्या 1 tick पलीकडे' (Q21)"),
    "evidence_weights": ("§6.3 यादी", "±0.5", "अंदाज", "spec §6.3–6.4 पुराव्यांचं वजन (Abhi च्या E1–E4 खुणांशी जुळवायचं, निकाल पाहून नाही)"),
    "conv_a / conv_b / conv_weak": ("0.6 / 0.4 / 0.2", "±0.1", "अंदाज", "spec §6.4 conviction स्तरांच्या सीमा"),
    "max_attempts": (3, "—", "Abhi नियम", "spec §5.1 H4 / L4 ⇒ trade नाही"),
}

# Layer 6b — OUTPUT (display) settings: what the live Vision card / Telegram / pre-open TEXT shows, never a reading or an entry. Each
# default = today's output byte-for-byte; the live-switch track wires them to the dashboard (bot settings, the same key) and Abhi flips
# them. {key: (default, options, where it is read)}. The facts dossier's own `display_finder` (facts/dossier.py, not wired live) is listed
# in REGISTER for completeness.
OUTPUT = {
    "approval_band_warn_rule": ("points", ("points", "method"),
                                "bots_common.plain_text.band_flag / band_wide_words ⇐ vision.approval (ticket), vision.worker (caption), "
                                "paper.engine_entry (gate tags), scripts.level_gate_preopen (pre-open), scripts.paper_daily_summary (15:45)"),
    "vision_chart_band_finder": ("validity", ("validity", "method"),
                                 "vision.chart.render (only with vision_chart_bands ON) + vision.signal_audit chart note; vision/config.py"),
    "vision_volume_words": ("legacy", ("legacy", "method"),
                            "decision3.volume_pane.study ⇐ vision.chart (Vision card volume pane + volume line); vision/config.py"),
    "approval_card_layout": ("classic", ("classic", "summary"),
                             "vision.worker.caption / v1_caption + vision.approval.ticket_text (Telegram card text); vision/config.py"),
}
REGISTER.update({
    "approval_band_warn_rule": ("points", "points / method", "setting",
                                "layer 6b display (C-18): points = today's '⚠️ merged band — check' over approval_band_warn_pts; method = an "
                                "engine area is one base, never merged (#329, Z-1u) ⇒ width as a fact, no line; other sources keep points"),
    "approval_band_warn_pts": (150, "pts (display only)", "setting",
                               "C-18 display alert (cloud_db default 150); read only under approval_band_warn_rule = points / non-engine bands"),
    "vision_chart_band_finder": ("validity", "validity / method", "setting",
                                 "layer 6b display: with vision_chart_bands ON, validity = the R1a band finder (today); method = the "
                                 "decision's own areas (engine gate tags: one base, K4 state, confluence label)"),
    "vision_volume_words": ("legacy", "legacy / method", "setting",
                            "layer 6b display: legacy = 'volume: NA (grade cap B)' + chart window average (today); method = FUT missing "
                            "= data problem (no entry), nothing to compare = no commitment, no chart-side average"),
    "approval_card_layout": ("classic", "classic / summary", "setting",
                             "Abhi (simple card): classic = today's Vision / approval card byte-for-byte; summary = 5 short lines on top "
                             "(side + label, area + last price, the reader's required set ✓ / ✗ + confirming pieces from the engine's "
                             "layer 6a evidence list, Vision in one line, what you do + deadline), today's text below the details line; "
                             "display only, no new rule / score"),
    "display_finder": ("method", "method / validity (legacy R1a)", "setting",
                                       "facts/dossier.py DEFAULTS (dossier config, not a V22 setting) — layer 6b: the Vision facts dossier reads the "
                                       "decision's own areas / lines / visits; validity = the R1a facts.validity finder (golden only); not live"),
})

TRENDS = ("UP", "DOWN", "RANGE", "NEUTRAL", "UNKNOWN")


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update(overrides or {})
    return s
