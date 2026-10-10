# नकाशा A1: Constants register (entry engine)

फक्त अहवाल — कोणतंही मूल्य बदललं / निवडलं नाही. वर्ग: व्याख्या / Abhi / research / NIFTY / अंदाज. `used_by` रिकामा ⇒ entry मार्गात वापर नाही (shadow / context).

**Real break ची एकच व्याख्या:** `elliott/breaks.py` — `first_real_break` (buffer + displacement / no-reclaim / failed retest) आणि `time_accepted` (`break_accept_closes` = 3, Abhi). `levels_v2.lifecycle` (`accept_closes`) आणि Simple Core engine ची area acceptance दोन्ही `breaks.time_accepted` च वापरतात. **टप्पा B (G-MAP1 निर्णय 8):** Simple Core engine `accept_bars` (सलग 2 closes) काढला ⇒ area चा real break = `breaks.break_from` (= `first_real_break`: displacement ⇒ लगेच, नाहीतर no-reclaim, time acceptance). Elliott count नियम (R1–R11, invalidation) भावावरूनच — 3-close नाही. **⚠ उघडा (Abhi):** `levels_v2` lifecycle — 3-close (time acceptance) breaks.py चाच, पण 'buffer + पुढचा bar' नियम ठेवला: त्यात breaks.py चा displacement-मार्ग लावल्यावर 26 Aug चा 1H flip zone (24,356–24,379) FLIPPED ऐवजी DEAD ⇒ Abhi-✔ 26 Aug G4 bear गेला. विलीन करायचं का, Abhi ठरवेल.

## टप्पा B: नवे / बदललेले आकडे (G-MAP1, 2026-10-09)

| आकडा | मूल्य | कुठे | वर्ग | कारण |
|---|---|---|---|---|
| `S2_DEEP` | 0.618 | simple_core/reading.py | Abhi | नकाशा P4 / S2: 61.8–80% खोल (फक्त नोंद / पुरावा, gate नाही) |
| count degree जुळवणी सहनशीलता | 30 मि (5m / 15m) · 120 मि (1h+) | simple_core/count_source.py | व्याख्या | correction origin E आणि count pivot एकच आहे का (TF च्या 2–6 bars) |
| `commit_vs_impulse` [प्रस्ताव] स्तंभ | ≥ 1.0 | research/map_b_measure.py | प्रस्ताव, Abhi चा निर्णय बाकी | §2.1: 'impulse ची सामान्य candle' — फक्त अहवालात, gate नाही |
| `commit_vs_impulse` median | median | simple_core/reading.py | व्याख्या | §2.1: impulse bars चा median range (व्याख्येची निवड) |
| random-entry draws | N = 20 | research/map_b_measure.py | research | §4 baseline: प्रति signal draws (fixed seed 20261011) |
| random-entry window | 09:30–15:00 | research/map_b_measure.py | व्याख्या | engine opening window वगळून, 15:15 eod recheck आधी |
| §4 नमुना seed | 20261010 | research/map_b_measure.py | research | 200 IS दिवस (वगळलेले दिवस अहवालात) |
| `gray_size` half | floor(lots / 2) | simple_core/execution.py | Abhi | G-MAP1 निर्णय 6 |
| `flag_min_bars` | 4 → 2 | simple_core/settings.py | Abhi | G8 2–6 candles |
| `accept_bars` | काढला (2) | simple_core/settings.py | — | breaks.py ची एकच व्याख्या (निर्णय 8) |

## Abhi (16)

| key | मूल्य | file:line | used_by | कारण |
|---|---|---|---|---|
| `g7_min_rr` | 3.0 | chart_reader/gap.py:36 | gap.py | A3: R:R ≥ 3 (G7) |
| `retrace_lo` | 0.382 | chart_reader/settings.py:126 | core.py | valid खोली 38.2% पासून (नकाशा P4) |
| `min_rr` | 3.0 | chart_reader/settings.py:159 | execution.py, settings.py | A3: R:R ≥ 3 |
| `opening_block_min` | 15 | chart_reader/settings.py:160 | engine.py, settings.py | opening window (A3 / KB K14: पहिली candle नाही) |
| `break_accept_closes` | 3 | elliott/settings.py:128 | engine.py, breaks.py | K-10 B2; breaks.py (KB G ची एकच real-break व्याख्या) चा भाग |
| `retrace_lo` | 0.382 | market_state/core.py:48 | core.py | valid खोली 38.2% पासून (नकाशा P4) |
| `accept_closes` | 3 | price_action/levels_v2.py:35 | engine.py, zones.py, levels_v2.py | K-10 निर्णय B2 (16 Feb PDL): सलग 3 closes ⇒ acceptance; elliott/breaks.time_accepted हीच व्याख्या |
| `parent_source` | market_state | simple_core/settings.py:13 | engine.py, settings.py | G-MAP1 निर्णय 4: market_state (default) / preferred_count |
| `g10_enabled` | True | simple_core/settings.py:14 | engine.py, settings.py | G-MAP1 निर्णय 5: G10 signals (default on) |
| `g10_mode` | shadow | simple_core/settings.py:15 | engine.py, execution.py, settings.py | G-MAP1 निर्णय 5: shadow (default) / paper |
| `eod_signal_carry` | recheck | simple_core/settings.py:16 | engine.py, settings.py | G-MAP1 निर्णय 7: recheck (नकाशा S12) |
| `pause_min_bars` | 1 | simple_core/settings.py:23 | engine.py, settings.py | Simple Core: area वर किमान एक pause (थेट entry नाही) |
| `opening_block_min` | 15 | simple_core/settings.py:31 | engine.py, settings.py | opening window (A3 / KB K14: पहिली candle नाही) |
| `g8_retrace_max` | 0.382 | simple_core/settings.py:34 | waves.py, settings.py | KB H G8: उथळ 23.6–38.2% |
| `g8_max_bars` | 6 | simple_core/settings.py:36 | waves.py, flags.py, settings.py | KB H G8: 2–6 candles |
| `flag_min_bars` | 2 | simple_core/settings.py:43 | flags.py, settings.py | नकाशा S5 / KB H G8: 2–6 candles (टप्पा B: 4 → 2; 1 candle = flag नाही) |

## config (TF / स्रोत निवड) (16)

| key | मूल्य | file:line | used_by | कारण |
|---|---|---|---|---|
| `gap_setup_g7` | True | chart_reader/gap.py:27 | gap.py | KB K13 D → G7 (Abhi 2026-10-08): PAPER मध्ये ON, स्वतंत्र scorecard |
| `g7_classes` | ['G5', 'E'] | chart_reader/gap.py:28 | gap.py | trend दिशेचा मोठा / event gap |
| `gap_setup_g7` | True | chart_reader/settings.py:85 | gap.py | §4A G7 exhaustion gap reversal (PAPER ON, स्वतंत्र scorecard; entry वर परिणाम नाही) |
| `structure_tf` | 5m | elliott/settings.py:44 | swings.py | [degrees] Structure timeframe — Pivots/counts या TF वर (NIFTY spot). लहान TF ⇒ जास्त तपशील, जास्त noise. |
| `swing_mode` | atr | elliott/settings.py:48 | core.py, measures.py, levels_v2.py, swings.py | [degrees] Swing पद्धत — atr: उलट हालचाल ≥ पट × ATR; pct: ≥ % × भाव; fractal: r-bar fractal (आलटून-पालटून). |
| `degree_tf_mode` | auto_by_bars | elliott/settings.py:57 | swings.py | [degrees] Degree → TF पद्धत — auto_by_bars: setup च्या corrective wave साठी TF आपोआप (बंद candles च्या संख्येवरून); fixed: खालची degree_tf यादी. |
| `degree_tf` | ['5m', '15m', '1h', '1d'] | elliott/settings.py:59 | swings.py | [degrees] Degree TF (fixed mode) — D0, D1, … साठी TF. फक्त fixed mode मध्ये. |
| `auto_tfs` | ['5m', '15m', '30m', '1h', '1d'] | elliott/settings.py:60 | swings.py | [degrees] Auto TF पर्याय — auto_by_bars मध्ये यांपैकी सर्वात लहान TF निवडतो. |
| `trade_degrees_enabled` | [0, 1, 2] | elliott/settings.py:65 | — | [degrees] Trade degrees — कोणत्या degrees वर trades (उदा. 0,1,2). |
| `break_confirm_tf` | level_tf | elliott/settings.py:130 | — | [breaks] Break confirmation TF — level_tf (default, F4): count आणि trade exit दोन्ही त्या wave च्या TF वर (fixed mode ⇒ degree_tf; auto ⇒ wave start → |
| `break_retest_confirm` | True | elliott/settings.py:133 | breaks.py | [breaks] Failed retest ने break — Break नंतर reclaim झाला, पण लगेच (trigger window मध्ये) level ला उलट logical reversal ने नाकारलं ⇒ खरा break (role r |
| `trend_tf` | 1h | market_state/core.py:34 | core.py | F2 HTF: "1h" / "75m" |
| `trade_tf` | 15m | market_state/core.py:36 | reading.py, core.py |  |
| `elliott_degrees` | (1, 2) | market_state/core.py:52 | core.py | F4 Elliott vote (trade degree) |
| `pivot_source` | elliott | price_action/levels_v2.py:26 | levels_v2.py |  |
| `degrees` | [1, 2, 3] | price_action/levels_v2.py:27 | engine.py, count_source.py, levels_v2.py |  |

## research (14)

| key | मूल्य | file:line | used_by | कारण |
|---|---|---|---|---|
| `impulse_min_mr` | 6.0 | chart_reader/settings.py:121 | core.py | KB भाग B टप्पा 2: impulse ≥ 4 MR |
| `fib_min_impulse_mr` | 4.0 | chart_reader/settings.py:150 | areas.py | KB भाग B: impulse ≥ 4 MR |
| `atr_len` | 14 | elliott/settings.py:46 | core.py, measures.py, levels_v2.py, swings.py | standard ATR14 |
| `break_buffer_mr` | 0.25 | elliott/settings.py:117 | zones.py, levels_v2.py, breaks.py | KB G: break buffer × MR (Osler stop clusters / spec §7); आकडा 0.25 अंदाज-समान |
| `trend_swing_atr_mult` | 1.5 | market_state/core.py:35 | reading.py, core.py | KB K1: HTF swing ≥ 1.5–2 MR |
| `impulse_min_mr` | 4.0 | market_state/core.py:38 | core.py | KB भाग B टप्पा 2: impulse ≥ 4 MR |
| `impulse_overlap_max` | 0.4 | market_state/core.py:43 | core.py | KB K2: overlap < 0.4 |
| `correction_overlap_min` | 0.6 | market_state/core.py:44 | core.py | KB K10.1: correction overlap > 0.6 |
| `atr_len` | 14 | price_action/levels_v2.py:29 | core.py, measures.py, levels_v2.py, swings.py | standard ATR14 |
| `break_buffer_mr` | 0.25 | price_action/levels_v2.py:34 | zones.py, levels_v2.py, breaks.py | KB G: break buffer × MR (Osler stop clusters / spec §7); आकडा 0.25 अंदाज-समान |
| `w3_proj` | 1.618 | simple_core/settings.py:37 | count_source.py, waves.py, settings.py | Elliott guideline 1.618 (K7: Fibonacci ला सांख्यिकीय आधार नाही ⇒ फक्त माहिती) |
| `w5_proj_w1` | 1.0 | simple_core/settings.py:39 | count_source.py, waves.py, settings.py | Elliott guideline wave 5 = wave 1 |
| `w5_proj_w13` | 0.618 | simple_core/settings.py:40 | waves.py, settings.py | Elliott guideline 0.618 × (1 start → 3 end) |
| `flag_overlap_min` | 0.6 | simple_core/settings.py:45 | flags.py, settings.py | KB K10.1 correction overlap > 0.6 |

## shadow (entry मार्गात नाही) (97)

| key | मूल्य | file:line | used_by | कारण |
|---|---|---|---|---|
| `w_trend_strong` | 15.0 | chart_reader/settings.py:9 | — | T: HTF दिशेने, मजबूत trend |
| `w_trend_weakening` | 8.0 | chart_reader/settings.py:10 | — | T: HTF दिशेने, कमकुवत होणारा / अस्पष्ट |
| `w_trend_range_edge` | 5.0 | chart_reader/settings.py:11 | — | T: range edge वरून |
| `w_trend_counter` | -20.0 | chart_reader/settings.py:12 | — | T: HTF विरुद्ध (Elliott C-wave setup S6a/S13 असेल तर लागू नाही) |
| `w_correction_weakening` | 15.0 | chart_reader/settings.py:13 | — | CW: 0–1 × हे |
| `w_area_quality` | 20.0 | chart_reader/settings.py:14 | — | AQ: 0–1 × हे |
| `w_confluence_each` | 5.0 | chart_reader/settings.py:15 | — | CF: प्रत्येक अतिरिक्त प्रकार |
| `confluence_max_extra` | 2 | chart_reader/settings.py:16 | — | CF कमाल = 2 × 5 = 10 |
| `rv_scale` | 50.0 | chart_reader/settings.py:17 | — | RV = rv_scale × (s − rv_zero), clip [rv_min, rv_max] |
| `rv_zero` | 0.3 | chart_reader/settings.py:18 | — | chart_reader evidence / grade |
| `rv_min` | -10.0 | chart_reader/settings.py:19 | — | chart_reader evidence / grade |
| `rv_max` | 25.0 | chart_reader/settings.py:20 | — | chart_reader evidence / grade |
| `w_gap_confirms` | 10.0 | chart_reader/settings.py:21 | — | chart_reader evidence / grade |
| `w_gap_opposes` | -10.0 | chart_reader/settings.py:22 | — | chart_reader evidence / grade |
| `w_elliott_end` | 10.0 | chart_reader/settings.py:23 | — | 2 / 4 / C-end ची शक्यता |
| `w_elliott_bad` | -15.0 | chart_reader/settings.py:24 | — | A-end किंवा wave-B च्या आत |
| `w_rr_bonus` | 5.0 | chart_reader/settings.py:25 | — | chart_reader evidence / grade |
| `rr_bonus_min` | 5.0 | chart_reader/settings.py:26 | — | chart_reader evidence / grade |
| `w_event_day` | -5.0 | chart_reader/settings.py:27 | — | chart_reader evidence / grade |
| `w_pb_healthy` | 10.0 | chart_reader/settings.py:29 | — | PB [K2]: 3 waves + overlap + origin अबाधित + खोली 38.2–80% |
| `w_pb_danger` | -10.0 | chart_reader/settings.py:30 | — | PB: counter displacement / 5-wave counter-move / खोली > 80% आणि तिथे area/sweep नाही |
| `w_pb_near_origin` | -15.0 | chart_reader/settings.py:31 | — | PB: origin जवळ / 100% पलीकडे wick पण acceptance नाही (acceptance = व्हेटो) |
| `pb_near_origin_retrace` | 0.9 | chart_reader/settings.py:32 | — | PB: retrace ≥ हे ⇒ "origin जवळ" |
| `pb_overlap_min` | 0.6 | chart_reader/settings.py:33 | — | PB: correction bars चं overlap ratio ≥ हे (K10.1: correction > 0.6) |
| `w_lq_sweep` | 5.0 | chart_reader/settings.py:34 | — | LQ [K5]: pool sweep + reclaim close |
| `w_lq_wick` | 3.0 | chart_reader/settings.py:35 | — | LQ: sweep bar ची wick ≥ lq_wick_min × range ⇒ अधिक (कमाल 8) |
| `lq_wick_min` | 0.5 | chart_reader/settings.py:36 | — | chart_reader evidence / grade |
| `w_vl_dryup` | 3.0 | chart_reader/settings.py:37 | — | VL [K10.3]: pullback rel_vol ÷ impulse rel_vol < vl_dryup_max |
| `vl_dryup_max` | 0.8 | chart_reader/settings.py:38 | — | chart_reader evidence / grade |
| `w_vl_spike` | 2.0 | chart_reader/settings.py:39 | — | VL: C-end absorption spike किंवा reversal candle ला volume |
| `vl_spike_min` | 1.5 | chart_reader/settings.py:40 | — | absorption: rel_vol ≥ हे, निव्वळ प्रगती ≤ vl_spike_prog_mr × MR, close परत आत |
| `vl_spike_prog_mr` | 0.3 | chart_reader/settings.py:41 | — | chart_reader evidence / grade |
| `vl_rev_min` | 1.2 | chart_reader/settings.py:42 | — | reversal candle rel_vol ≥ हे |
| `w_vl_rising` | -5.0 | chart_reader/settings.py:43 | — | VL: pullback मध्ये वाढता volume (ratio > vl_rising_min) |
| `vl_rising_min` | 1.0 | chart_reader/settings.py:44 | — | chart_reader evidence / grade |
| `vl_slot_days` | 20 | chart_reader/settings.py:45 | — | rel_vol = bar volume ÷ मागच्या इतक्या दिवसांच्या त्याच वेळेच्या slot चा median |
| `w_dv_regular` | 5.0 | chart_reader/settings.py:46 | — | DV [K10.2]: C-end ला regular divergence |
| `w_dv_hidden` | 3.0 | chart_reader/settings.py:47 | — | DV: pullback मध्ये hidden divergence |
| `w_dv_against` | -3.0 | chart_reader/settings.py:48 | — | DV: impulse च्या टोकावर विरुद्ध regular divergence |
| `dv_rsi_len` | 14 | chart_reader/settings.py:49 | — | chart_reader evidence / grade |
| `dv_min_bars` | 8 | chart_reader/settings.py:50 | — | तुलना 8–60 bars मागच्या त्याच प्रकारच्या pivot शी |
| `dv_max_bars` | 60 | chart_reader/settings.py:51 | — | chart_reader evidence / grade |
| `dv_price_mr` | 0.25 | chart_reader/settings.py:52 | — | price फरक ≥ हे × MR |
| `dv_rsi_pts` | 3.0 | chart_reader/settings.py:53 | — | RSI फरक ≥ इतके points |
| `dv_regular_os` | 30.0 | chart_reader/settings.py:54 | — | regular bullish फक्त पहिल्या low चा RSI ≤ 30 (bearish ≥ 70) |
| `dv_hidden_rsi_min` | 35.0 | chart_reader/settings.py:55 | — | hidden bullish: pullback RSI ≥ 35 (bearish ≤ 65) |
| `dv_confirm_bars` | 2 | chart_reader/settings.py:56 | — | pivot नंतर इतके बंद bars ⇒ confirmed |
| `w_pt_flag` | 5.0 | chart_reader/settings.py:57 | — | PT [K11]: flag |
| `w_pt_wedge` | 3.0 | chart_reader/settings.py:58 | — | PT: correction चा opposite wedge |
| `w_pt_reversal` | -10.0 | chart_reader/settings.py:59 | — | PT: double top/bottom, H&S (neckline तुटलेली), impulse स्वतः wedge |
| `pt_pole_min_mr` | 6.0 | chart_reader/settings.py:60 | — | chart_reader evidence / grade |
| `pt_pole_max_bars` | 12 | chart_reader/settings.py:61 | — | chart_reader evidence / grade |
| `pt_flag_min_bars` | 4 | chart_reader/settings.py:62 | — | chart_reader evidence / grade |
| `pt_flag_max_bars` | 20 | chart_reader/settings.py:63 | — | chart_reader evidence / grade |
| `pt_flag_max_retrace` | 0.5 | chart_reader/settings.py:64 | — | chart_reader evidence / grade |
| `pt_dt_tol_mr` | 0.5 | chart_reader/settings.py:65 | — | double top: दोन highs ≤ 0.5 MR, ≥ 8 bars दूर, मधला trough ≥ 2 MR खाली |
| `pt_dt_min_bars` | 8 | chart_reader/settings.py:66 | — | chart_reader evidence / grade |
| `pt_dt_trough_mr` | 2.0 | chart_reader/settings.py:67 | — | chart_reader evidence / grade |
| `pt_hs_head_mr` | 0.5 | chart_reader/settings.py:68 | — | H&S: head ≥ खांद्यांपेक्षा 0.5 MR वर, खांदे ≤ 1.5 MR अंतरात |
| `pt_hs_shoulder_mr` | 1.5 | chart_reader/settings.py:69 | — | chart_reader evidence / grade |
| `w_tm_open` | -5.0 | chart_reader/settings.py:70 | — | TM [K14]: 09:15–09:45 |
| `tm_open_end` | 09:45 | chart_reader/settings.py:71 | — | chart_reader evidence / grade |
| `w_tm_expiry_morning` | -3.0 | chart_reader/settings.py:72 | — | TM: expiry दिवस सकाळ |
| `tm_expiry_weekday` | 1 | chart_reader/settings.py:73 | — | NIFTY weekly expiry = मंगळवार (0 = सोमवार) |
| `tm_expiry_morning_end` | 12:00 | chart_reader/settings.py:74 | — | chart_reader evidence / grade |
| `w_vx_jump` | -5.0 | chart_reader/settings.py:75 | — | VX [K14]: pullback दरम्यान VIX उडी (≥ vx_jump_pct %) |
| `vx_jump_pct` | 5.0 | chart_reader/settings.py:76 | — | chart_reader evidence / grade |
| `w_vx_falling` | 2.0 | chart_reader/settings.py:77 | — | VX: VIX घटतोय (≤ vx_fall_pct %) |
| `vx_fall_pct` | -2.0 | chart_reader/settings.py:78 | — | chart_reader evidence / grade |
| `zone_entry_tol_mr` | 0.3 | chart_reader/settings.py:93 | — | reversal composite zone च्या आत किंवा ≤ हे × MR (नाहीतर FAR_FROM_ZONE) |
| `f4_gate` | True | chart_reader/settings.py:94 | — | Abhi 2026-10-08 (c): code-mode मध्ये F4 side unclear ⇒ entry नाही (SIDE_UNCLEAR) |
| `grade_a_min` | 60.0 | chart_reader/settings.py:104 | — | chart_reader evidence / grade |
| `grade_b_min` | 45.0 | chart_reader/settings.py:105 | — | chart_reader evidence / grade |
| `c_wave_setups` | ['S6a', 'S13'] | chart_reader/settings.py:106 | — | B-end → C setups (spec S6a / S13) |
| `c_wave_setups_enabled` | False | chart_reader/settings.py:107 | — | Abhi 2026-10-08: मुख्य setup = pullback end; हे default OFF (OFF ⇒ C). ON ⇒ counter −20 नाही, Tier B |
| `tier_mult` | {'A': 1.0, 'B': 0.5, 'C': 0.25} | chart_reader/settings.py:108 | — | spec §4/§11 — size = full × tier multiplier |
| `rev_weak_floor` | 0.5 | chart_reader/settings.py:110 | — | range < strength_min × MR ⇒ s × max(floor, range ÷ (strength_min × MR)) |
| `rev_climax_penalty` | 0.2 | chart_reader/settings.py:111 | — | range > strength_max × MR आणि CL < 0.6 ⇒ − हे |
| `rev_last_against_penalty` | 0.15 | chart_reader/settings.py:112 | — | N ≥ 2 आणि शेवटची candle trade विरुद्ध ⇒ − हे |
| `rev_n3_penalty` | 0.05 | chart_reader/settings.py:113 | — | N = 3 ⇒ − हे |
| `rev_label_strong` | 0.6 | chart_reader/settings.py:114 | — | फक्त label (log / narrative / vision), निर्णय नाही |
| `rev_label_medium` | 0.45 | chart_reader/settings.py:115 | — | chart_reader evidence / grade |
| `swing_k` | 3.0 | chart_reader/settings.py:117 | — | sloping lines साठी ZigZag (× MR) — areas.py |
| `impulse_lookback_legs` | 8 | chart_reader/settings.py:120 | — | शेवटच्या इतक्या swing legs मधून impulse |
| `zigzag_b_max` | 0.79 | chart_reader/settings.py:122 | — | zigzag: B ≤ 0.79 × A (spec 38–79%) |
| `flat_b_min` | 0.9 | chart_reader/settings.py:123 | — | flat: B ≥ 0.9 × A (R7) |
| `flat_c_min` | 0.9 | chart_reader/settings.py:124 | — | flat C-end: C ≥ 0.9 × A (C ने A एवढं अंतर; नाहीतर C चालू) |
| `retrace_max` | 0.8 | chart_reader/settings.py:125 | — | pullback valid खोली कमाल (Abhi / KB: 38.2–80%); पलीकडे ⇒ unclear |
| `c_end_back_max` | 0.618 | chart_reader/settings.py:127 | — | C-end: C च्या टोकापासून परत आलेलं अंतर ≤ हे × C (market_state A/B/C; C-V1) |
| `origin_break_buffer_mr` | 0.25 | chart_reader/settings.py:128 | — | impulse origin real break: close origin ∓ हे × MR पलीकडे |
| `disp_bars_reversal` | 2 | chart_reader/settings.py:131 | — | correction दिशेने इतके displacement bars ⇒ counter-move impulsive |
| `acceptance_bars` | 2 | chart_reader/settings.py:132 | — | major zone पलीकडे सलग इतके closes (buffer सह) ⇒ acceptance |
| `acceptance_buffer_mr` | 0.25 | chart_reader/settings.py:133 | — | chart_reader evidence / grade |
| `sweep_min_mr` | 0.1 | chart_reader/settings.py:153 | — | K5: sweep = pool च्या 0.1–1.0 MR पलीकडे, आत close |
| `sweep_max_mr` | 1.0 | chart_reader/settings.py:154 | — | chart_reader evidence / grade |
| `inv_buffer_mr` | 0.25 | chart_reader/settings.py:156 | — | invalidation = area / reversal candle च्या टोकापलीकडे हे × MR (दोन्हीतलं दूरचं) |
| `max_targets` | 2 | chart_reader/settings.py:157 | — | पुढचे 1–2 opposite areas |

## अंदाज (119)

| key | मूल्य | file:line | used_by | कारण |
|---|---|---|---|---|
| `cs_absorption_ratio` | 3.0 | chart_reader/candles.py:42 | candles.py | effort (Σ range ÷ MR) ÷ result (/net/ ÷ MR) ≥ हे ⇒ absorption (K12) — [स्रोत नाही ⇒ अंदाज] |
| `cs_absorption_min_mr` | 1.2 | chart_reader/candles.py:43 | candles.py | absorption candle: range ≥ हे × MR पण body ≤ cs_absorption_body — [स्रोत नाही ⇒ अंदाज] |
| `cs_absorption_body` | 0.3 | chart_reader/candles.py:44 | candles.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `cs_wick_tag` | 0.4 | chart_reader/candles.py:45 | candles.py | zone story: trade दिशेने rejection wick ≥ range च्या हे — [स्रोत नाही ⇒ अंदाज] |
| `cs_close_tag` | 0.3 | chart_reader/candles.py:46 | candles.py | sellers close: CL ≤ हे (buyers: ≥ 1 − हे) आणि body ≥ 0.5 — [स्रोत नाही ⇒ अंदाज] |
| `cs_zone_tol_mr` | 0.3 | chart_reader/candles.py:47 | candles.py | zone ला "पोहोचला" = ± हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `cs_story_min` | 3 | chart_reader/candles.py:48 | candles.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `cs_story_max` | 6 | chart_reader/candles.py:49 | candles.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `cs_tired_min` | 3 | chart_reader/candles.py:50 | candles.py | leg मालिकेत इतक्या खुणा ⇒ "थकतोय" — [स्रोत नाही ⇒ अंदाज] |
| `gap_pb_min_mr` | 1.0 | chart_reader/gap.py:22 | gap.py | pullback = running टोकापासून ≥ हे × MR उलट — [स्रोत नाही ⇒ अंदाज] |
| `gap_pb_tol_mr` | 0.3 | chart_reader/gap.py:23 | gap.py | … आणि gap edge / PDC / zone पासून ≤ हे × MR पर्यंत पोहोचला — [स्रोत नाही ⇒ अंदाज] |
| `gap_story_bars` | 8 | chart_reader/gap.py:24 | gap.py | आदल्या दिवसाची "शेवटची चाल" = शेवटचे इतके 15M bars (2 तास) — [स्रोत नाही ⇒ अंदाज] |
| `gap_story_weak_er` | 0.4 | chart_reader/gap.py:25 | gap.py | त्या चालीची efficiency (net ÷ path) < हे ⇒ कमकुवत — [स्रोत नाही ⇒ अंदाज] |
| `gap_story_min_mr` | 1.5 | chart_reader/gap.py:26 | gap.py | /net/ < हे × MR ⇒ "बाजूला" — [स्रोत नाही ⇒ अंदाज] |
| `g7_min_degree` | 2 | chart_reader/gap.py:29 | gap.py | major HTF zone = levels_v2 degree ≥ हे (D2 / D3) — [स्रोत नाही ⇒ अंदाज] |
| `g7_zone_tol_mr` | 0.3 | chart_reader/gap.py:30 | gap.py | open / पहिल्या bars चं टोक zone च्या ± हे × MR मध्ये — [स्रोत नाही ⇒ अंदाज] |
| `g7_reject_bars` | 6 | chart_reader/gap.py:31 | gap.py | rejection पहिल्या 2–6 bars मध्ये — [स्रोत नाही ⇒ अंदाज] |
| `g7_reject_min_bars` | 2 | chart_reader/gap.py:32 | gap.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `g7_wick_min` | 0.4 | chart_reader/gap.py:33 | gap.py | zone मधली rejection wick ≥ range च्या हे — [स्रोत नाही ⇒ अंदाज] |
| `g7_rev_cl` | 0.6 | chart_reader/gap.py:34 | gap.py | pullback नंतरची reversal candle: close location ≥ हे (bull) / ≤ 1 − हे (bear) — [स्रोत नाही ⇒ अंदाज] |
| `g7_inv_buffer_mr` | 0.25 | chart_reader/gap.py:35 | gap.py | invalidation = gap दिवसाचं टोक ∓ हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `gap_pb_min_mr` | 1.0 | chart_reader/settings.py:80 | gap.py | "pullback आला" = running टोकापासून ≥ हे × MR उलट … — [स्रोत नाही ⇒ अंदाज] |
| `gap_pb_tol_mr` | 0.3 | chart_reader/settings.py:81 | gap.py | … आणि gap edge (open) / PDC / trade बाजूचा zone पासून ≤ हे × MR पर्यंत — [स्रोत नाही ⇒ अंदाज] |
| `gap_story_bars` | 8 | chart_reader/settings.py:82 | gap.py | गोष्ट: आदल्या दिवसाची शेवटची चाल = शेवटचे इतके bars — [स्रोत नाही ⇒ अंदाज] |
| `gap_story_weak_er` | 0.4 | chart_reader/settings.py:83 | gap.py | … efficiency < हे ⇒ कमकुवत — [स्रोत नाही ⇒ अंदाज] |
| `gap_story_min_mr` | 1.5 | chart_reader/settings.py:84 | gap.py | … /चाल/ < हे × MR ⇒ बाजूला — [स्रोत नाही ⇒ अंदाज] |
| `g7_min_degree` | 2 | chart_reader/settings.py:86 | gap.py | G7: major HTF zone = degree ≥ हे — [स्रोत नाही ⇒ अंदाज] |
| `g7_zone_tol_mr` | 0.3 | chart_reader/settings.py:87 | gap.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `g7_reject_bars` | 6 | chart_reader/settings.py:88 | gap.py | rejection पहिल्या 2–6 bars मध्ये — [स्रोत नाही ⇒ अंदाज] |
| `g7_wick_min` | 0.4 | chart_reader/settings.py:89 | gap.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `g7_rev_cl` | 0.6 | chart_reader/settings.py:90 | gap.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `g7_inv_buffer_mr` | 0.25 | chart_reader/settings.py:91 | gap.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `zone_break_buffer_mr` | 0.25 | chart_reader/settings.py:95 | zones.py | zone lifecycle buffer (breaks.py break_buffer_mr सारखाच 0.25 — एकच स्रोत करायचा) |
| `zone_reaction_bars` | 8 | chart_reader/settings.py:96 | zones.py | reaction ताकद: touch नंतरचे इतके bars — [स्रोत नाही ⇒ अंदाज] |
| `zone_worn_tests` | 3 | chart_reader/settings.py:97 | zones.py | ≥ इतके tests ⇒ worn — [स्रोत नाही ⇒ अंदाज] |
| `cs_absorption_ratio` | 3.0 | chart_reader/settings.py:99 | candles.py | effort (Σ range) ÷ result (/net/) ≥ हे ⇒ absorption — [स्रोत नाही ⇒ अंदाज] |
| `cs_absorption_min_mr` | 1.2 | chart_reader/settings.py:100 | candles.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `cs_wick_tag` | 0.4 | chart_reader/settings.py:101 | candles.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `cs_tired_min` | 3 | chart_reader/settings.py:102 | candles.py | leg मालिकेत इतक्या खुणा ⇒ "थकतोय" — [स्रोत नाही ⇒ अंदाज] |
| `swing_atr_mult` | 3.0 | chart_reader/settings.py:118 | core.py, areas.py, measures.py, levels_v2.py, swings.py | impulse: elliott/swings.py pivots, ATR14 × हे (Elliott D1 चा default) — [स्रोत नाही ⇒ अंदाज] |
| `internal_atr_mult` | 1.5 | chart_reader/settings.py:119 | areas.py | correction चे आतले legs: ATR14 × हे (Elliott D0) — [स्रोत नाही ⇒ अंदाज] |
| `disp_body_mr` | 1.5 | chart_reader/settings.py:129 | core.py, areas.py | displacement body ≥ 1.5 MR |
| `disp_body_frac` | 0.6 | chart_reader/settings.py:130 | core.py, areas.py | displacement body ÷ range ≥ 0.6 |
| `tl_touch_mr` | 0.2 | chart_reader/settings.py:135 | areas.py | K6.1: touch = pivot रेषेपासून ± हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `tl_close_beyond_mr` | 0.3 | chart_reader/settings.py:136 | areas.py | K6.1: anchors मध्ये कुठलाही close रेषेपलीकडे > हे × MR नाही — [स्रोत नाही ⇒ अंदाज] |
| `tl_min_spacing` | 6 | chart_reader/settings.py:137 | areas.py | K6.1: touches एकमेकांपासून ≥ इतके bars — [स्रोत नाही ⇒ अंदाज] |
| `tl_max_slope_mr` | 0.5 | chart_reader/settings.py:138 | areas.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `tl_search_pivots` | 16 | chart_reader/settings.py:139 | areas.py | K6.1 शोध: शेवटच्या इतक्या आतल्या swings मधल्या जोड्या (C-V1) — [स्रोत नाही ⇒ अंदाज] |
| `tl_search_bars` | 200 | chart_reader/settings.py:140 | areas.py | … आणि फक्त शेवटच्या इतक्या bars मधले (15M ⇒ 8 sessions) — [स्रोत नाही ⇒ अंदाज] |
| `tl_switch_touches` | 2 | chart_reader/settings.py:141 | areas.py | (b) memory: नवी रेषा फक्त जुनीपेक्षा ≥ इतके जास्त touches आणि ताजा touch असेल तर (नाहीतर जुनी कायम) — [स्रोत नाही ⇒ अंदाज] |
| `tl_max_lines` | 3 | chart_reader/settings.py:142 | areas.py | §8.4: प्रति role इतक्या valid रेषा (anchors स्थिर) — दर bar ला एकच "सर्वोत्तम" बदलत नाही — [स्रोत नाही ⇒ अंदाज] |
| `active_extreme_bars` | 12 | chart_reader/settings.py:143 | areas.py | K6.4: active area = ताजे bars + शेवटच्या इतक्या bars मधलं trade-विरुद्ध टोक (C-V1)            # K6.1: /slope/ ≤ हे × MR प्रति bar — [स्रोत नाही ⇒ अंदा |
| `disp_single_mr` | 2.5 | chart_reader/settings.py:144 | areas.py | K4: एकच displacement candle ≥ हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `base_max_range_mr` | 0.8 | chart_reader/settings.py:145 | areas.py | K4: base candle range ≤ हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `base_max_height_mr` | 1.5 | chart_reader/settings.py:146 | areas.py | K4: base zone उंची ≤ हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `eq_tol_mr` | 0.15 | chart_reader/settings.py:147 | areas.py | K5: equal highs/lows ≤ हे × MR अंतरात — [स्रोत नाही ⇒ अंदाज] |
| `eq_min_bars` | 5 | chart_reader/settings.py:148 | areas.py | K5: ≥ इतके bars अंतराने — [स्रोत नाही ⇒ अंदाज] |
| `fib_band_mr` | 0.25 | chart_reader/settings.py:149 | areas.py | K7: Fibonacci / C = A / channel band ± हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `round_max_dist_mr` | 6.0 | chart_reader/settings.py:151 | areas.py | K8: किंमतीपासून इतक्या MR मधले round numbers — [स्रोत नाही ⇒ अंदाज] |
| `level_band_mr` | 0.25 | chart_reader/settings.py:152 | areas.py | K8: round / PDH-PDL band ± हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `zone_break_buffer_mr` | 0.25 | chart_reader/zones.py:21 | zones.py | zone lifecycle buffer (breaks.py break_buffer_mr सारखाच 0.25 — एकच स्रोत करायचा) |
| `zone_chop_window` | 20 | chart_reader/zones.py:22 | zones.py | MAGNET: शेवटच्या इतक्या closes मध्ये — [स्रोत नाही ⇒ अंदाज] |
| `zone_chop_max_crossings` | 4 | chart_reader/zones.py:23 | zones.py | … mid च्या इतक्यापेक्षा जास्त वेळा आरपार ⇒ MAGNET — [स्रोत नाही ⇒ अंदाज] |
| `zone_reaction_bars` | 8 | chart_reader/zones.py:24 | zones.py | reaction = touch नंतरच्या इतक्या bars मधली zone पासूनची कमाल चाल — [स्रोत नाही ⇒ अंदाज] |
| `zone_worn_tests` | 3 | chart_reader/zones.py:25 | zones.py | ≥ इतके tests ⇒ worn — [स्रोत नाही ⇒ अंदाज] |
| `zone_lookback_bars` | 400 | chart_reader/zones.py:26 | zones.py | birth नसलेल्या (round / PDC) zones चा lifecycle शेवटच्या इतक्या bars वर (~16 sessions) — [स्रोत नाही ⇒ अंदाज] |
| `degree_levels` | 4 | elliott/settings.py:47 | swings.py | [degrees] Degrees ची संख्या — D0 (सर्वात लहान) ते D(n−1). 4 = D0–D3. — [स्रोत नाही ⇒ अंदाज] |
| `swing_atr_mult` | [1.5, 3.0, 6.0, 12.0] | elliott/settings.py:50 | core.py, areas.py, measures.py, levels_v2.py, swings.py | [degrees] ATR पट (प्रति degree) — D0, D1, D2, D3 … साठी. वाढवल्यास त्या degree चे swings मोठे आणि कमी. — [स्रोत नाही ⇒ अंदाज] |
| `swing_pct` | [0.15, 0.3, 0.6, 1.2] | elliott/settings.py:52 | swings.py | [degrees] % हालचाल (प्रति degree) — pct पद्धतीसाठी, भावाच्या % मध्ये. — [स्रोत नाही ⇒ अंदाज] |
| `swing_fractal_r` | [2, 4, 8, 16] | elliott/settings.py:53 | swings.py | [degrees] Fractal r (प्रति degree) — fractal पद्धतीसाठी: दोन्ही बाजूंचे bars. Confirm = r bars नंतर. — [स्रोत नाही ⇒ अंदाज] |
| `tf_bars_min` | 8 | elliott/settings.py:62 | swings.py | [degrees] Wave किमान candles — Corrective wave इतक्या बंद candles मध्ये दिसावी (कमी ⇒ आतली रचना दिसत नाही). — [स्रोत नाही ⇒ अंदाज] |
| `tf_bars_max` | 40 | elliott/settings.py:64 | swings.py | [degrees] Wave कमाल candles — यापेक्षा जास्त ⇒ noise; मोठा TF घ्या. — [स्रोत नाही ⇒ अंदाज] |
| `median_range_n` | 20 | elliott/settings.py:115 | reading.py, core.py, breaks.py | MR lookback (20); sensitivity हवी |
| `break_close_loc` | 0.3 | elliott/settings.py:120 | breaks.py | displacement close location (0.3) |
| `strength_min` | 1.2 | elliott/settings.py:122 | breaks.py | displacement / commitment ताकद × MR (1.2); sensitivity हवी |
| `strength_max` | 2.5 | elliott/settings.py:124 | — | news spike मर्यादा × MR (2.5) |
| `trade_swing_atr_mult` | 3.0 | market_state/core.py:37 | reading.py, core.py | trade-degree swings ATR × 3 (Elliott D1) |
| `disp_body_mr` | 1.5 | market_state/core.py:40 | core.py, areas.py | displacement body ≥ 1.5 MR |
| `disp_body_frac` | 0.6 | market_state/core.py:41 | core.py, areas.py | displacement body ÷ range ≥ 0.6 |
| `impulse_er_min` | 0.45 | market_state/core.py:42 | core.py | market_state: ER ≥ 0.45 [अनुमान, Abhi मंजुरी] — 7 Oct impulse overlap 0.62 |
| `htf_days` | 60 | market_state/core.py:50 | core.py | HTF lookback दिवस |
| `trade_days` | 20 | market_state/core.py:51 | core.py | trade TF lookback दिवस |
| `swing_atr_mult_by_degree` | {1: 3.0, 2: 6.0, 3: 12.0} | price_action/levels_v2.py:28 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `lookback_weeks_by_degree` | {1: 2, 2: 6, 3: 26} | price_action/levels_v2.py:30 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `cluster_tol_mr` | 0.75 | price_action/levels_v2.py:31 | levels_v2.py | pivot clustering सहनशीलता |
| `zone_pad_mr` | 0.25 | price_action/levels_v2.py:32 | levels_v2.py | zone पट्टा pad |
| `zone_min_mr` | 0.5 | price_action/levels_v2.py:33 | levels_v2.py | zone किमान रुंदी |
| `chop_window` | 20 | price_action/levels_v2.py:36 | zones.py, levels_v2.py | MAGNET खिडकी 20 bars |
| `chop_max_crossings` | 4 | price_action/levels_v2.py:37 | zones.py, levels_v2.py | MAGNET: chop window मध्ये > 4 crossings |
| `max_per_side` | 2 | price_action/levels_v2.py:38 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `max_total` | 4 | price_action/levels_v2.py:39 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `min_quality` | 0.3 | price_action/levels_v2.py:40 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `w_quality` | 1.0 | price_action/levels_v2.py:41 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `w_role_reversal` | 2.0 | price_action/levels_v2.py:42 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `w_edge` | 1.0 | price_action/levels_v2.py:43 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `w_degree` | {1: 0.5, 2: 1.0, 3: 1.5} | price_action/levels_v2.py:44 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `origin_bonus` | 1.0 | price_action/levels_v2.py:45 | levels_v2.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `area_tol_mr` | 0.3 | simple_core/settings.py:18 | engine.py, reading.py, flags.py, settings.py | touch सहनशीलता 0.3 MR (Abhi: contaminated वर tune नाही; IS sensitivity हवी) |
| `area_merge_mr` | 0.5 | simple_core/settings.py:19 | engine.py, settings.py | zones एकत्र करण्याचं अंतर |
| `pause_body_max` | 0.5 | simple_core/settings.py:20 | engine.py, settings.py | indecision body ≤ 0.5 range |
| `pause_range_max_mr` | 1.0 | simple_core/settings.py:21 | engine.py, settings.py | indecision range ≤ 1 MR |
| `pause_wick_min` | 0.2 | simple_core/settings.py:22 | engine.py, settings.py | दोन्ही wicks ≥ 0.2 |
| `pause_lookback` | 12 | simple_core/settings.py:24 | engine.py, settings.py | pause शोध खिडकी |
| `commit_strength_min_mr` | 1.2 | simple_core/settings.py:25 | engine.py, settings.py | commitment range ≥ 1.2 MR (elliott strength_min सारखं) |
| `commit_strength_max_mr` | 2.5 | simple_core/settings.py:26 | engine.py, settings.py | commitment ≤ 2.5 MR (news spike नाही) |
| `commit_body_min` | 0.5 | simple_core/settings.py:27 | engine.py, settings.py | commitment body ≥ 0.5 |
| `commit_close_max` | 0.3 | simple_core/settings.py:28 | engine.py, settings.py | close टोकाजवळ (0.3) |
| `commitment_vs_pause` | 1.5 | simple_core/settings.py:29 | engine.py, settings.py | Evening plan §5 [अनुमान] 1.5; Abhi: 1.3 / 1.5 / 2.0 sensitivity |
| `wave_lookback_pivots` | 12 | simple_core/settings.py:33 | waves.py, settings.py | trade-degree swings पैकी मागचे इतके (origin शोध) — [स्रोत नाही ⇒ अंदाज] |
| `g8_retrace_tol` | 0.05 | simple_core/settings.py:35 | waves.py, settings.py | G8 retrace सहनशीलता |
| `w3_proj_alts` | (1.0, 2.618) | simple_core/settings.py:38 | waves.py, settings.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `wave1_zone_mr` | 0.15 | simple_core/settings.py:41 | waves.py, settings.py | wave 1 टोकाचा flip area = टोक ± हे × MR — [स्रोत नाही ⇒ अंदाज] |
| `flag_retrace_max` | 0.5 | simple_core/settings.py:44 | flags.py, settings.py | flag ≤ 50% (research notes 'codable rule' ⇒ अंदाज वर्ग, नकाशा I5) |
| `flag_slope_tol_mr` | 0.05 | simple_core/settings.py:47 | flags.py, settings.py | flag slope सहनशीलता |
| `gap_g0_atr` | 0.25 | vision/gap_context.py:22 | gap_context.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `gap_large_atr` | 0.63 | vision/gap_context.py:22 | gap_context.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `gap_stretch_atr` | 3.0 | vision/gap_context.py:22 | gap_context.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `gap_max_age_sessions` | 10 | vision/gap_context.py:22 | gap_context.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |
| `gap_accept_buf_mr` | 0.25 | vision/gap_context.py:22 | gap_context.py | स्रोत नोंद नाही — [स्रोत नाही ⇒ अंदाज] |

## रद्द (टप्पा B) (3)

| key | मूल्य | file:line | used_by | कारण |
|---|---|---|---|---|
| `reversal_retrace_min` | 0.382 | market_state/core.py:45 | core.py | POSSIBLE_REVERSAL — नकाशा: S3 + Gray-1 + reaction test ने बदलणार |
| `reversal_min_criteria` | 3 | market_state/core.py:46 | core.py | POSSIBLE_REVERSAL — नकाशा: बदलणार |
| `reversal_internal_atr` | 1.5 | market_state/core.py:47 | core.py | POSSIBLE_REVERSAL — नकाशा: बदलणार |

## व्याख्या (7)

| key | मूल्य | file:line | used_by | कारण |
|---|---|---|---|---|
| `break_displacement_confirm` | True | elliott/settings.py:118 | breaks.py | KB G: displacement close वर लगेच break |
| `break_no_reclaim_bars` | 1 | elliott/settings.py:126 | breaks.py | KB G: कमकुवत close नंतर reclaim नाही ⇒ acceptance |
| `impulse_disp_min` | 1 | market_state/core.py:39 | core.py | impulse मध्ये किमान एक displacement candle (F3) |
| `retrace_hi` | 1.0 | market_state/core.py:49 | core.py | 100% = origin |
| `g10_range_bars` | 400 | simple_core/settings.py:17 | engine.py, settings.py | G10 StructureTracker lookback = zones.zone_lookback_bars (400, ~16 sessions) — नवा आकडा नाही |
| `accept_buf_mr` | 0.25 | simple_core/settings.py:30 | engine.py, settings.py | area कडेपलीकडचा close ⇒ breaks.break_from तपासणी सुरू (break_buffer_mr शी समान 0.25); accept_bars (2 closes) टप्पा B मध्ये काढला — real break = breaks |
| `flag_min_touches` | 2 | simple_core/settings.py:46 | flags.py, settings.py | channel = प्रत्येक रेषेला ≥ 2 touches |

## Inline आकडे (settings बाहेर) — प्रत्येक setting मध्ये न्यायचा का ते टप्पा B मध्ये

| file:line | आकडे | code |
|---|---|---|
| simple_core/engine.py:17 | 3 | `subwave_origin (gray ⇒ None + ref_notes मध्ये "लागू नाही — कारण"). Wave 1 चं टोक (wave 3 ने पार केलं) ⇒ flip area.` |
| simple_core/engine.py:34 | 0.0 | `sl = float(z.get("slope") or 0.0)` |
| simple_core/engine.py:65 | 1e-9 | `rng = max(h - lo, 1e-9)` |
| simple_core/engine.py:72 | 1e-9 | `rng = max(h - lo, 1e-9)` |
| simple_core/engine.py:218 | 3 | `if df is None or len(df) < 3 or not mr or not np.isfinite(float(mr)):` |
| simple_core/engine.py:404 | 40 | `if len(trig) < 40:` |
| simple_core/engine.py:446 | 15, 15 | `(G1 / G9 labels, wave refs), commit_vs_impulse (report), 15:15 ⇒ eod recheck. Gray मुळे थांबलेला signal `gray_candidate` मध्ये` |
| simple_core/reading.py:4 | 9, 2.4 | `impulse (निर्णय 9 / Phase B §2.4): ज्या correction च्या शेवटी trade घेतो त्याच correction च्या आधीचा impulse — trade-degree` |
| simple_core/reading.py:10 | 5, 5 | `triangle ⇒ 5 legs (आकुंचन); counter-move स्वतः 5 waves (वाढती टोकं) ⇒ A ⇒ gray; flag (G8) ⇒ रचना पुरेशी.` |
| simple_core/reading.py:12 | 3, 2.2 | `S3 (निर्णय 3, §2.2): impulse मधला शेवटचा confirmed 1H LH (bear impulse) / HL (bull) — 1H pivots = market_state trend pivots —` |
| simple_core/reading.py:15 | 61.8, 3 | `S2 खोल (retrace ≥ 61.8%), S5 flag (G8 area), S6 बाजूचा (legs ≥ 3 आणि correction bars > impulse bars), S8 (with-trend legs लहान),` |
| simple_core/reading.py:16 | 15, 15 | `S10 gap दिवस, S12 15:15 — फक्त नोंद / पुरावा (I2 precedence: जास्त कडक जिंकते).` |
| simple_core/reading.py:17 | 2.1 | `commit_vs_impulse (निर्णय 1, §2.1): commitment range ÷ impulse मधल्या बंद 15M bars चा median range — फक्त report, gate नाही.` |
| simple_core/reading.py:19 | 0.618 | `नवे आकडे नाहीत: 0.618 (S2) = नकाशा P4 / KB [Abhi]; बाकी सगळं व्याख्या (A1 register).` |
| simple_core/reading.py:24 | 0.618 | `S2_DEEP = 0.618` |
| simple_core/reading.py:74 | 3 | `retrace = round(abs(ext - imp["end"]) / size, 3) if (ext is not None and size > 0) else None` |
| simple_core/reading.py:86 | 5, 4 | `out["why"] = "Gray-2: counter-move स्वतः 5 waves (वाढती टोकं, wave 4 चा wave 1 शी overlap नाही) ⇒ A"` |
| simple_core/reading.py:88 | 5 | `out.update(complete=True, why="triangle (आकुंचन, 5 legs)")` |
| simple_core/reading.py:125 | 20 | `if len(f) < 20:` |
| simple_core/reading.py:149 | 3 | `return round(rng / med, 3) if med > 0 else None` |
| simple_core/reading.py:187 | 15 | `if hhmm >= "15:15":` |
| simple_core/reading.py:210 | 3 | `if legs["legs"] >= 3 and legs["bars"] > (imp["end_idx"] - imp["start_idx"]):` |
| simple_core/count_source.py:5 | 9, 2.4 | `Degree (निर्णय 9 / §2.4): reading layer चा correction origin E (trade-degree confirmed pivot) ज्या count-degree वर confirmed pivot म्हणून` |
| simple_core/count_source.py:8 | 4, 4 | `• motive (impulse / diagonal) + चालू wave 2 ⇒ G1, 4 ⇒ G9 (G9 फक्त preferred wave 4 म्हणतो तेव्हा; alternate ⇒ फक्त grade वाढ);` |
| simple_core/count_source.py:109 | 4, 4 | `G9 (चालू wave 4): wave1_origin = O, wave1_extreme = W1, wave5_projection = wave 4 टोक (ext) + w5_proj_w1 × wave 1.` |
| simple_core/count_source.py:116 | 1.0, 1.0 | `d = 1.0 if w1 > o else -1.0` |
| simple_core/waves.py:4 | 3 | `Trade-degree swings (market_state, 15M ATR × 3) + चालू pullback, "x-space" मध्ये (trend दिशा = वर; bear ⇒ किंमत उलटी):` |
| simple_core/waves.py:6 | 3 | `W2          = O नंतरचा पहिला start-kind pivot जो O च्या वर, नंतरचे सगळे pullbacks त्याच्या वर (R1: (ii) of 3 सुद्धा W2 खाली नाही),` |
| simple_core/waves.py:9 | 3, 4, 3, 5 | `W2 आहे     ⇒ wave 3 चं टोक X3; त्याआधी पूर्ण झालेली wave 4 (W1 overlap नाही, खोल, wave 3 ≥ wave 1) आणि नवा high ⇒ wave 5 नंतर ⇒ gray.` |
| simple_core/waves.py:11 | 3, 4 | `नाहीतर wave 3 ≥ wave 1 ⇒ G9 (wave 4 end); नाहीतर gray.` |
| simple_core/waves.py:13 | 4 | `wave3_projection = wave 2 end + w3_proj × wave 1 (पर्याय w3_proj_alts) · wave5_projection = wave 4 end + w5_proj_w1 × wave 1` |
| simple_core/waves.py:14 | 3, 3 | `(पर्याय: + w5_proj_w13 × (wave 1 start → wave 3 end)) · wave1_origin · wave1_extreme · subwave_origin (G8: (i) of 3 ची सुरुवात = W2).` |
| simple_core/waves.py:104 | 4, 5 | `return {"gray": "wave 4 आधीच पूर्ण, नवं टोक = wave 5 — motive पूर्ण असू शकते"}` |
| simple_core/waves.py:106 | 3 | `out.update(phase=3, W1=w1, W2=w2, X3=x3, P4=p4, leg1=leg1, leg3=leg3, bars=int(k - x3["i"]))` |
| simple_core/waves.py:130 | 4 | `out["notes"] = {"wave5_projection": "लागू नाही — wave 4 अजून नाही (G1 = wave 2 end)",` |
| simple_core/waves.py:135 | 1.0 | `r = (x3 - p4) / leg3 if leg3 > 0 else 1.0` |
| simple_core/waves.py:138 | 4 | `g = "pullback wave 1 च्या भागात (R3 overlap) — wave 4 नाही, count gray"` |
| simple_core/waves.py:145 | 3, 4 | `out["notes"] = {"wave5_projection": "लागू नाही — wave 3 चालू (G8), wave 4 अजून नाही"}` |
| simple_core/waves.py:152 | 3, 4 | `out["notes"] = {"wave3_projection": "लागू नाही — wave 3 पूर्ण (G9 = wave 4 end)",` |
| simple_core/waves.py:156 | 3, 4 | `g = "wave 3 wave 1 पेक्षा लहान आणि pullback उथळ / जलद नाही — wave 4 म्हणता येत नाही"` |
| simple_core/waves.py:167 | 3 | `if st.get("gray") or st.get("phase") != 3 or not mr:` |
| simple_core/flags.py:5 | 50 | `• flag bars ≥ flag_min_bars; retrace ≤ flag_retrace_max (50%) × impulse; overlap (K10.1) ≥ flag_overlap_min;` |
| simple_core/flags.py:20 | 6 | `if not impulse or not side or not mr or impulse.get("to_ts") is None or len(df) < 6:` |
| simple_core/flags.py:42 | 0.0, 1e-9 | `ov = np.maximum(0.0, np.minimum(hh[1:], hh[:-1]) - np.maximum(ll[1:], ll[:-1])) / np.maximum(hh[1:] - ll[1:], 1e-9)` |
| simple_core/flags.py:43 | 0.5 | `if float((ov > 0.5).mean()) < float(s["flag_overlap_min"]):` |
| market_state/core.py:3 | 2026, 08 | `🎓 व्याख्या (KB K1, K2, K3, भाग G; Abhi 2026-10-08 TRADE_CODE_FIX_CROSSVERIFY_PROMPT §2):` |
| market_state/core.py:4 | 09, 15 | `Frames    1m ⇒ NSE 09:15-anchored, CAS bars वगळून (opportunity_engine/cas.py), फक्त bar_end ≤ asof.` |
| market_state/core.py:6 | 20 | `MR        मागच्या 20 बंद bars चा (high − low) median, चालू bar वगळून (elliott/breaks.py::median_range).` |
| market_state/core.py:9 | 0.25 | `Counter चाल **correction** राहते — लांबी कितीही असो — जोपर्यंत protected swing चा **real break** (elliott/breaks.py: 0.25 MR` |
| market_state/core.py:17 | 0.6 | `Correction impulse टोकानंतरची चाल. Origin न तोडता (real break नाही) आणि overlapping (B आला / K10.1 overlap ≥ 0.6) ⇒ correction,` |
| market_state/core.py:18 | 38.2, 100, 38.2 | `दिशा impulse ची. retrace 38.2–100% = सामान्य; < 38.2% उथळ; origin real break ⇒ "origin_broken" (A3 व्हेटो, side unclear).` |
| market_state/core.py:22 | 0.45, 0.4, 7, 0.62 | `Defaults [अनुमान]: impulse_er_min 0.45 हा NIFTY 15M वर KB च्या overlap < 0.4 ऐवजी (7 Oct impulse चा K10.1 overlap 0.62) — Abhi च्या मंजुरीसा` |
| market_state/core.py:54 | 5, 15, 30, 60, 75, 240, 1440 | `TF_MIN = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "75m": 75, "4h": 240, "1d": 1440}` |
| market_state/core.py:80 | 20 | `if len(fr) < 20:` |
| market_state/core.py:101 | 5e-4 | `elif abs(p["price"] - prev) <= 5e-4 * prev:` |
| market_state/core.py:148 | 2026, 08 | `(Abhi 2026-10-08: counter चाल लांबी कितीही असो correction) ⇒ दिशा ठरल्यावर range मध्ये परत जात नाही."""` |
| market_state/core.py:154 | 4 | `if len(pv) < 4:` |
| market_state/core.py:253 | 1e-9 | `rng = np.maximum(h - lo, 1e-9)` |
| market_state/core.py:254 | 0.0 | `ov = np.maximum(0.0, np.minimum(h[1:], h[:-1]) - np.maximum(lo[1:], lo[:-1])) / rng[1:]` |
| market_state/core.py:255 | 0.5, 3 | `return round(float((ov > 0.5).mean()), 3)` |
| market_state/core.py:261 | 3, 0.0 | `return round(abs(c[-1] - c[0]) / path, 3) if path > 0 else 0.0` |
| market_state/core.py:272 | 1e-9 | `body, rng = np.abs(c - o), np.maximum(h - lo, 1e-9)` |
| market_state/core.py:281 | 0.0 | `size = abs(b["price"] - a["price"]) / m if np.isfinite(m) and m > 0 else 0.0` |
| market_state/core.py:325 | 3 | `retrace=round(abs(ext - imp["to"]) / size, 3) if size > 0 else None)` |
| market_state/core.py:333 | 3 | `if len(pts) >= 3:` |
| market_state/core.py:335 | 3 | `if len(pts) >= 3:` |
| market_state/core.py:359 | 3 | `out["overlapping"] = bool(len(pts) >= 3 or (ov is not None and ov >= s["correction_overlap_min"]))` |
| market_state/core.py:360 | 0.0 | `r = out["retrace"] or 0.0` |
| market_state/core.py:411 | 3, 3 | `out[d] = {"up": None if up is None else round(up, 3), "down": None if dn is None else round(dn, 3), "gray": bool(v.gray), "dir": dr}` |
| market_state/core.py:456 | 5, 3, 4 | `(1) 5 legs किंवा कमी overlap, (2) displacement candles, (3) गती मागच्या impulse पेक्षा जास्त, (4) impulse ची सुरुवात close ने तुटली,` |
| market_state/core.py:457 | 5, 38.2, 3 | `(5) वाटेत उथळ pauses (आतले pullbacks ≤ 38.2%). रिटर्न (count, {निकष: bool}). Corrective (3 legs, overlap, संथ) ⇒ कमी count."""` |
| market_state/core.py:461 | 1e-9 | `body, rng = np.abs(c[e + 1:x + 1] - o[e + 1:x + 1]), np.maximum(h[e + 1:x + 1] - lo[e + 1:x + 1], 1e-9)` |
| market_state/core.py:481 | 5 | `crit = {"legs5_or_low_overlap": bool(legs >= 5 or er >= s["impulse_er_min"] or (ov is not None and ov < s["impulse_overlap_max"])),` |
| market_state/core.py:525 | 11, 11, 58 | `impulse दिशेचा शेवटचा confirmed swing ⇒ त्यानंतरचं टोक (उदा. 11 Aug: 10 Aug high ⇒ 11 Aug घसरण, impulse च्या 58%).` |
| market_state/core.py:527 | 61.8 | `cancelled; (c) नव्या दिशेत HL / LH confirm ⇒ new_trend (wave (2) setup). 61.8% परत गेल्याने flag संपत नाही (wave (2)).` |
| market_state/core.py:567 | 3 | `st["retrace"] = round(depth, 3)` |
| chart_reader/zones.py:49 | 2.0 | `return "SUPPORT" if (float(z["low"]) + float(z["high"])) / 2.0 < price else "RESISTANCE"` |
| chart_reader/zones.py:81 | 0.0 | `best, prev_touch = 0.0, False` |
| chart_reader/zones.py:88 | 0.0 | `best = max(best, float(away) / mr if mr else 0.0)` |
| chart_reader/zones.py:136 | 2.0 | `zs = sorted([z for z in out if z["side"] == side], key=lambda z: abs((float(z["low"]) + float(z["high"])) / 2.0 - price))` |
| chart_reader/zones.py:148 | 2.0 | `return sorted(ok, key=lambda z: abs((float(z["low"]) + float(z["high"])) / 2.0 - price))[:n]` |
| chart_reader/areas.py:3 | 2026, 08, 7 | `🎓 Abhi (2026-10-08): 7 Oct ला फक्त horizontal पाहिल्याने उतरती trendline सुटली — म्हणून प्रत्येक वेळी पूर्ण यादी.` |
| chart_reader/areas.py:5 | 3 | `e liquidity: equal highs/lows, आधीचे swing extremes, PDH/PDL (K5) · f sloping trendline ≥ 3 touches (K6)` |
| chart_reader/areas.py:6 | 38.2, 50, 61.8, 78.6 | `g channel — impulse आणि correction चा (K6, मोजपट्टी) · h Fibonacci 38.2/50/61.8/78.6 ± band (K7, मोजपट्टी) · i C = A (K3/K7, मोजपट्टी)` |
| chart_reader/areas.py:7 | 100, 500, 1000 | `j round numbers 100/500/1000 (K8) · k PDH/PDL/PDC, आठवड्याचे H/L (K8) · l gap edge / PDC, जुने unfilled gaps (K13)` |
| chart_reader/areas.py:10 | 0.5, 1.0 | `horizontal आणि sloping ≤ 0.5 MR मध्ये भेटत असतील तर तो छेदबिंदू सर्वोच्च (quality 1.0).` |
| chart_reader/areas.py:26 | 2.0 | `return "SUPPORT" if (lo + hi) / 2.0 < price else "RESISTANCE"` |
| chart_reader/areas.py:43 | 0.0 | `if BRK.first_real_break(det, int(start), 0.0, side, dict(ESET.DEFAULTS)) is not None:` |
| chart_reader/areas.py:60 | 3 | `valid = (len(on) >= 3 and not (beyond > s["tl_close_beyond_mr"] * mr).any() and spaced` |
| chart_reader/areas.py:87 | 7, 28, 30, 7 | `(2) शोध (C-V1, 7 Oct उतरती रेषा 28 Sep / 30 Sep / 7 Oct सुटली होती): शेवटच्या tl_search_pivots swings (आतले pivots, ATR ×` |
| chart_reader/areas.py:90 | 3 | `valid (गुण मिळतात) फक्त: ≥ 3 touches (± tl_touch_mr × MR), पहिल्या anchor पासून शेवटच्या touch पर्यंत कुठलाही close रेषेपलीकडे >` |
| chart_reader/areas.py:92 | 2026, 08 | `keep (Abhi 2026-10-08 (b), स्थिर ओळख): {role: [anchor0, anchor1]} — memory मधली रेषा कायम (नवीन touches त्याच रेषेत); बदल फक्त` |
| chart_reader/areas.py:103 | 3 | `if len(pts) >= 3:` |
| chart_reader/areas.py:135 | 3 | `if sum(1 for x in out if x.get("role") == role) >= int(s.get("tl_max_lines", 3)) + 1:` |
| chart_reader/areas.py:149 | 4 | `+ आधीचा swing तुटलेला (BOS) ⇒ त्याच्या आधीचा base (1–4 लहान candles, range ≤ base_max_range_mr × MR). Zone: demand = [lowest low,` |
| chart_reader/areas.py:154 | 1e-9 | `big = (rng >= s["disp_body_mr"] * mr) & (body >= s["disp_body_frac"] * np.maximum(rng, 1e-9))` |
| chart_reader/areas.py:167 | 4 | `while j >= 0 and len(base) < 4 and rng[j] <= s["base_max_range_mr"] * mr:` |
| chart_reader/areas.py:190 | 1.0 | `tool, q = "b", 1.0` |
| chart_reader/areas.py:192 | 0.6 | `tool, q = "d", 0.6` |
| chart_reader/areas.py:194 | 0.8, 0.5, 0.3 | `tool, q = "a", 0.8 if z.get("quality_n", 0) >= 2 else (0.5 if z.get("degree", 0) >= 2 else 0.3)` |
| chart_reader/areas.py:208 | 0.1, 0.1 | `lo_, hi_ = lo_ - 0.1 * mr, hi_ + 0.1 * mr` |
| chart_reader/areas.py:215 | 0.1 | `lo_, hi_ = _zone(p[1], 0.1 * mr)` |
| chart_reader/areas.py:227 | 3 | `if imp and len(corr) >= 3 and st.get("correction_bars"):` |
| chart_reader/areas.py:251 | 0.382, 0.5, 0.618, 0.786 | `for r in (0.382, 0.5, 0.618, 0.786):` |
| chart_reader/areas.py:261 | 3 | `if len(corr) < 3:` |
| chart_reader/areas.py:265 | 0.618, 1.0, 1.618 | `for r in (0.618, 1.0, 1.618):` |
| chart_reader/areas.py:275 | 100, 100 | `base = int(price // 100) * 100` |
| chart_reader/areas.py:277 | 100 | `nearest = v in (base, base + 100)` |
| chart_reader/areas.py:280 | 3, 1000, 500 | `w = 3 if v % 1000 == 0 else 2 if v % 500 == 0 else 1` |
| chart_reader/areas.py:289 | 0.5, 0.5, 0.4, 0.5, 0.5 | `for key, name, q in (("pdh", "PDH", 0.5), ("pdl", "PDL", 0.5), ("pdc", "PDC", 0.4), ("week_high", "PWH", 0.5), ("week_low", "PWL", 0.5)):` |
| chart_reader/areas.py:344 | 0.0 | `out = {"area": None, "quality": 0.0, "confluence": [], "confluence_extra": 0, "touched_ids": [], "intersection": False}` |
| chart_reader/areas.py:352 | 0.0, 0.0 | `shift = float(z.get("slope") or 0.0) * back if z.get("tool") == "f" else 0.0` |
| chart_reader/areas.py:358 | 0.5 | `near = 0.5 * mr` |
| chart_reader/areas.py:359 | 0.0 | `best = max(touched, key=lambda z: (z.get("quality", 0.0), z.get("tool") in ("b", "a", "f")))` |
| chart_reader/areas.py:360 | 0.0 | `q = float(best.get("quality", 0.0))` |
| chart_reader/areas.py:364 | 1.0 | `q = 1.0` |
| chart_reader/areas.py:412 | 200 | `g = g[g["n"] >= 200]` |
| elliott/breaks.py:2 | 7, 14 | `elliott/breaks.py — "खरा break" (spec §7, §14 Q1): count invalidation आणि (E3) exits एकाच व्याख्येवर` |
| elliott/breaks.py:104 | 8 | `(Abhi G-MAP1 निर्णय 8: रचनेच्या breaks ना एकच व्याख्या)."""` |
| elliott/breaks.py:151 | 6 | `key = (int(start), round(float(level), 6), side, self.s["count_inv_basis"])` |
| price_action/levels_v2.py:5 | 2026, 08 | `Abhi (2026-10-08): PAPER bots नव्या levels वर चालतील; G-L1 (eye-match) / G-L2 (edge) अहवाल समांतर, report-only. LIVE ⇒ G-L2 PASS अनिवार्य.` |
| price_action/levels_v2.py:9 | 6, 26 | `L2 lookback    degree नुसार (`lookback_weeks_by_degree`: D1 2, D2 6, D3 26 आठवडे). Recency decay नाही.` |
| price_action/levels_v2.py:16 | 4 | `L6 selection   प्रत्येक बाजूला ≤ max_per_side (2), एकूण ≤ max_total (4); प्राधान्य FLIPPED > ≥ 2 quality rejections > range edge;` |
| price_action/levels_v2.py:117 | 2.0 | `mid = (lo + hi) / 2.0` |
| price_action/levels_v2.py:137 | 3 | `return 3` |
| price_action/levels_v2.py:147 | 2.0 | `z["side"] = "below" if (z["low"] + z["high"]) / 2.0 < price else "above"` |
| price_action/levels_v2.py:171 | 60, 60 | `return int(diffs.dt.total_seconds().min() // 60) if len(diffs) else 60` |
| price_action/levels_v2.py:232 | 30 | `if len(d) < 30:` |
| price_action/levels_v2.py:256 | 2.0 | `m = (lo_ + hi_) / 2.0` |
| price_action/levels_v2.py:257 | 2.0, 2.0 | `lo_, hi_ = m - s["zone_min_mr"] * mr / 2.0, m + s["zone_min_mr"] * mr / 2.0` |
| price_action/levels_v2.py:262 | 1e-9 | `r = max(h[idx] - l[idx], 1e-9)` |
| price_action/levels_v2.py:265 | 0.5, 0.5 | `q.append(0.5 * wick + 0.5 * float(back))` |
| price_action/levels_v2.py:270 | 0.0, 0.0 | `+ s["w_degree"].get(deg, 0.0) + (s["origin_bonus"] if origin else 0.0))` |
| price_action/levels_v2.py:272 | 0.0 | `score = 0.0` |
