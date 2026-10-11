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
    "show_distance_sigma": 12.0,             # chart वर फक्त इतक्या σ_1H अंतरातली levels (snapshot मधून कधीच prune नाही)
    "liq_marks_per_side": 3,                 # chart वर प्रत्येक बाजूचे जवळचे liquidity pools (फक्त chart)
    # ③ Pullback (C पायरी)
    "k_reset_sigma": 0.25,                   # नवं टोक < हे × σ_1H ने सरकलं ⇒ तेच टोक (reset नाही)
    # ④ Power shift (C)
    "power_shift_min": 2,                    # (a)–(d) पैकी किमान इतके
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
    # candle वाचन / §5.3
    "candle_avg_n": 5,                       # "मोठा / लहान" = मागच्या इतक्या candles च्या सरासरीशी तुलना (§5.2)
    "doji_body_max": 0.1,                    # body / range < हे ⇒ doji
    "range_overlap_min": 0.5,                # §5.3: प्रत्येक जोडी range overlap ≥ हे
    "range_state_n": 3,                      # §5.3: 3+ overlapping candles
    "power_fallback_bars": 8,                # ④: K उघडी नसल्यास मागचे इतके bars
    "liquidity_lookback": 8,                 # §7 sweeps / traps: शेवटचे इतके bars
    # level score (फक्त माहिती, निर्णयात नाही)
    "score_daily_bonus": 1.0, "score_fresh_bonus": 1.0, "score_test_penalty": 0.5,
    # ⑦ Risk (C)
    "sl_buffer_sigma": 0.25,                 # SL buffer = σ_15M × हे
    "min_rr": 3.0,
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
    "liq_marks_per_side": (3, "2/3/5", "अंदाज (फक्त chart)", "spec §7.6 pools लहान खुणा — गर्दी टाळायला; क्रम PWH/PWL > PDH/PDL > equal > swing (liquidity.pool_marks prio, फक्त display)"),
    "show_distance_sigma": (12.0, "8/12/20", "अंदाज (फक्त chart)", "spec ② दूरची levels chart वर लपवा"),
    "k_reset_sigma": (0.25, "—", "Abhi नियम", "spec ③ < 0.25 σ_1H ⇒ reset नाही"),
    "power_shift_min": (2, "2/3", "Abhi नियम", "spec ④ किमान 2 (config)"),
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
    "candle_avg_n": (5, "—", "Abhi नियम", "spec §5.2 मागच्या 5 candles ची सरासरी"),
    "doji_body_max": (0.1, "0.05/0.1/0.15", "अंदाज", "spec §5.2 / §5.3 doji (body लहान)"),
    "range_overlap_min": (0.5, "—", "व्याख्या", "spec §5.3 'बहुतांश overlap' (≥ 50%)"),
    "range_state_n": (3, "—", "Abhi नियम", "spec §5.3 3+ overlapping candles"),
    "power_fallback_bars": (8, "—", "व्याख्या", "④ K उघडी नसताना (chart / पुरावा) — निर्णयात ③ आधी लागतो"),
    "liquidity_lookback": (8, "4/8/12", "अंदाज", "spec §7.2 'लवकर' परत (काही candles)"),
    "score_daily_bonus / score_fresh_bonus / score_test_penalty": ("1 / 1 / 0.5", "—", "अंदाज",
                                                                   "spec §5.4 ★ provenance / freshness; निर्णयात नाही"),
    "sl_buffer_sigma": (0.25, "0.1/0.25/0.5", "अंदाज", "spec ⑦ buffer σ_15M × अपूर्णांक"),
    "min_rr": (3.0, "—", "Abhi नियम", "spec ⑦ R:R < 3 ⇒ trade नाही (एकमेव numeric gate)"),
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
