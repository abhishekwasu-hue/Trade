"""decision3/settings.py — थर v2.2 "method-first" चे आकडे आणि register (docs/prompts_v2/08_थर_v22_METHOD_FIRST.md).

प्रत्येक आकडा register मध्ये: (default, पर्याय, वर्ग, स्रोत). वर्ग = "Abhi नियम" / "व्याख्या" / "अंदाज". Thresholds निकाल पाहून फिरवायचे नाहीत;
बदल फक्त Abhi-मंजूर batch PR. Test: register मध्ये नसलेला अंदाज-आकडा DEFAULTS मध्ये नाही.
"""

DEFAULTS = {
    "engine_version": "v22",                 # v21 (decision2, जुना) / v22 (हा) — shadow तुलनेसाठी दोन्ही चालतात
    # ① Daily trend (Dow)
    "daily_swing_method": "pivot",           # pivot (N bars दोन्ही बाजूला) / dc (k_D × σ_D)
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
    "accept_closes": 3,                      # पलीकडे सलग इतके closes ⇒ acceptance (flip पक्का); कमी आणि परत ⇒ sweep ★
    "show_distance_sigma": 12.0,             # chart वर फक्त इतक्या σ_1H अंतरातली levels (snapshot मधून कधीच prune नाही)
    # ③ Pullback (C पायरी)
    "k_reset_sigma": 0.25,                   # नवं टोक < हे × σ_1H ने सरकलं ⇒ तेच टोक (reset नाही)
    # ④ Power shift (C)
    "power_shift_min": 2,                    # (a)–(d) पैकी किमान इतके
    "power_overlap": 0.5,                    # (b) bodies overlap
    # ⑥ Commitment (C)
    "commit_body": 0.5,                      # body ≥ range च्या हे
    "commit_merge_max": 2,
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
    # §6 पुरावे ⇒ conviction (वजन; NA ⇒ बेरजेत नाही)
    "evidence_weights": {"level_star": 1.0, "fresh": 0.5, "power_shift": 1.5, "trap_sweep": 1.5, "second_attempt": 1.0,
                         "commit_strong": 1.0, "engulf": 0.5, "rsi_div": 0.5, "volume_low": 0.5, "pattern": 0.5,
                         "against_bodies": -1.0, "fourth_attempt": -1.5},
    "conv_a": 0.6, "conv_b": 0.4, "conv_weak": 0.2,
    "max_attempts": 3,                       # §5.1: चौथा प्रयत्न (H4 / L4) ⇒ reversal शक्यता ⇒ trade नाही
}

# आकडा: (default, पर्याय, वर्ग, स्रोत)
REGISTER = {
    "engine_version": ("v22", "v21 / v22", "setting", "spec §4.A — जुना code shadow तुलना"),
    "daily_swing_method": ("pivot", "pivot / dc", "setting", "spec ① — कमी warm-up ⇒ pivot default"),
    "daily_pivot_n": (2, "1/2/3", "अंदाज", "spec ① (N config default 2)"),
    "daily_dc_k": (1.0, "0.75/1.0/1.5", "अंदाज", "spec ① (k_D config)"),
    "daily_sigma_sessions": (10, "10/15/20", "अंदाज", "spec ① warm-up फक्त σ साठी, default 10"),
    "daily_min_sessions": (10, "—", "Abhi नियम", "spec §3: Daily unknown फक्त data अपुरा (≤ 10 sessions)"),
    "range_eq_sigma_d": (0.25, "0.15/0.25/0.35", "अंदाज", "spec ① RANGE: σ_D च्या अपूर्णांकात (config)"),
    "level_degree": (2, "—", "व्याख्या", "spec ② (a) 1H trend-degree swing = थर 1 D2"),
    "level_min_width_sigma": (0.15, "0.1/0.15/0.25", "अंदाज", "spec ② पट्टा किमान रुंदी σ_1H × अपूर्णांक"),
    "liquidity_eq_sigma": (0.15, "0.1/0.15/0.25", "अंदाज", "spec ② (d) equal highs / lows"),
    "active_levels_max": (2, "—", "Abhi नियम", "spec ② active level = जवळची 2"),
    "accept_closes": (3, "2/3/4", "Abhi नियम", "spec §5.4 / §7.2 / §7.7: पलीकडे 3+ closes टिकले ⇒ acceptance; नाहीतर sweep"),
    "show_distance_sigma": (12.0, "8/12/20", "अंदाज (फक्त chart)", "spec ② दूरची levels chart वर लपवा"),
    "k_reset_sigma": (0.25, "—", "Abhi नियम", "spec ③ < 0.25 σ_1H ⇒ reset नाही"),
    "power_shift_min": (2, "2/3", "Abhi नियम", "spec ④ किमान 2 (config)"),
    "power_overlap": (0.5, "—", "Abhi नियम", "spec ④ (b) ≥ 50%"),
    "commit_body": (0.5, "—", "Abhi नियम", "spec ⑥ body ≥ 50% range"),
    "commit_merge_max": (2, "1/2", "Abhi नियम", "spec ⑥ ≤ 2 merged"),
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
    "evidence_weights": ("§6.3 यादी", "±0.5", "अंदाज", "spec §6.3–6.4 पुराव्यांचं वजन (Abhi च्या E1–E4 खुणांशी जुळवायचं, निकाल पाहून नाही)"),
    "conv_a / conv_b / conv_weak": ("0.6 / 0.4 / 0.2", "±0.1", "अंदाज", "spec §6.4 conviction स्तरांच्या सीमा"),
    "max_attempts": (3, "—", "Abhi नियम", "spec §5.1 H4 / L4 ⇒ trade नाही"),
}

TRENDS = ("UP", "DOWN", "RANGE", "NEUTRAL", "UNKNOWN")


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update(overrides or {})
    return s
