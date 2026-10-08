# Knowledge Base → code → test: traceability (v2, KB पूर्ण अंमलबजावणी)

> Abhi 2026-10-08 19:30 (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §1). प्रत्येक KB नियम (भाग A, B, D, E, G, H; K1–K14) → code (file:function) →
> test → स्थिती. v1 (C-V1) मध्ये "code आहे" एवढंच पाहिलं होतं. **v2 मध्ये प्रश्न: हा नियम प्रत्येक दिवशी, प्रत्येक candidate वर खरंच चालतो का,
> आणि chart वर दिसतो का?** 7 Oct चे दोन charts त्याचा पुरावा (खाली §0).
>
> **✅** = code + test, आणि प्रत्येक candidate वर चालतो · **आंशिक** = code आहे पण KB पेक्षा कमी / काही दिवशीच / test नाही / chart वर नाही ·
> **❌** = नाही. "golden" = `tests/test_golden_chart_cases.py` (data trade-data मध्ये, CI मध्ये skip).

## §0. सारांश: 7 Oct ला काय झालं (code चालवून तपासलं)

| वेळ | code चा निर्णय | KB प्रमाणे | कारण (code मध्ये) |
|---|---|---|---|
| 09:30 | ✅ B 56.2, entry 22,617 | ❌ gap chase | (1) gap **G2** (trend सोबत, inside); व्हेटो फक्त G3 / G5 वर (`settings.gap_b_classes`) ⇒ लागला नाही. (2) `rules.check` मध्ये `gap_chase` **नेहमी `False`** (`evaluate.py`), म्हणजे "gap-and-go नाही" हा नियम कधीच चालत नाही. (3) GP: "trade दिशेची पुष्टी" **+10**. (4) active area = उतरती trendline 22,721–22,731, पण entry तिथून **103.7 points = 4.0 MR** दूर. Active area कालच्या touch वरून (शेवटच्या 12 bars मधलं टोक) आला; entry ते area अंतराचा नियम नाही. (5) LQ +5 "A-end 22,621.8 चा sweep": gap bar ने गाठलेली level sweep म्हणून मोजली. |
| 12:15 | ✅ A 67.5 | ✅ Abhi चा golden | entry 22,649, area पासून 0.76 MR. पण active line **वेगळी** निवडली (25 Sep 14:00 23,163 / 6 Oct / 7 Oct 10:15). कारण: रेषा प्रत्येक bar ला पुन्हा निवडली जाते (K6 curve-fit धोका). |
| दिवसभर | 7 ✅ | फक्त 12:15 | "एक setup = एक entry" नियम नाही (`DUP_SETUP` नाही); backtest मध्ये फक्त एका वेळी एक position. |
| Chart | anchor 30 Sep 09:15 | 28 Sep | Code ला 28 Sep 12:15 22,855 सापडला होता (`TL-R2609281215`: 28 Sep 22,855 / 30 Sep 22,809 / 6 Oct 22,732). Day chart (आदले 1–2 sessions) ने anchor **window च्या पहिल्या bar वर दाबला**. ही chart मधली चूक, detector ची नाही. |

**मुख्य निष्कर्ष (Abhi चं निरीक्षण बरोबर):**

1. **Gap theory:** code ती gap वर्ग / acceptance इतकीच वापरतो. Setups A/B/C, "पहिल्या pullback ची वाट" आणि gap fill → zone → reversal हे काहीच नाही. Chart वर gap दिसत नाही.
2. **Zones:** सगळी 12 साधनं गणतात (33–35 areas), पण:
   - selling / buying हे **किंमतीच्या वर / खाली** यावरून ठरतं, zone कुठून जन्मला (supply / demand) यावरून नाही;
   - बहुतेक zones ची state hard-coded "ACTIVE" आहे. Freshness, reaction ताकद आणि degree नाही;
   - chart वर फक्त एक active area दिसतो.
3. **Candle-by-candle:** फक्त शेवटच्या candle चं वाचन होतं, आणि correction साठी 5 खुणा. Leg-wise मालिका, absorption आणि zone वरच्या 3–6 candles ची गोष्ट नाही.
4. **Entry zone शिवाय नाही:** हा नियम **नाही**. Reversal area ला लागायला हवा, एवढंच तपासलं जातं; entry किंमत किती दूर आहे ते पाहिलं जात नाही.

## भाग A: मूलतत्त्वं

| नियम | Code | Test | स्थिती |
|---|---|---|---|
| A1.1 impulse दिशा ठरवतो; pullback corrective | `market_state/core.py:impulse`, `:correction`; `chart_reader/structure.py:read(ms=…)` | `test_market_state::test_trend_down_protected…`, golden | ✅ |
| A1.2 आधी "pullback आहे, reversal नाही" | `market_state/core.py:correction`; `structure.py:read` (F2: फक्त origin real break ⇒ reversal) | `test_chart_reader_evidence::test_structure_origin…`, `test_market_state::test_decide_side_reasons` | ✅ |
| A1.3 पुष्टी नंतर impulse दिशेने entry | `chart_reader/reversal.py:evaluate` | `test_chart_reader_reversal::*` | ✅ |
| A1.4 entry selling / buying **zone वरच** | `areas.py:active` + reversal चा area touch; **entry ↔ zone अंतर तपासलं जात नाही** | — | ❌ (7 Oct 09:30: 4.0 MR दूर) → §3 |
| A1.5 R:R ≥ 1:3 | `rules.py:check`, `risk.py:compute`, `vision_led/validate.py` | `test_hard_rules_each_one_blocks` | ✅ |
| A1.6 breakout / gap-and-go entry नाही | `rules.py:check` (approach / role ✅; **`gap_chase` नेहमी False** — `evaluate.py`) | `test_hard_rules_each_one_blocks` (synthetic flag) | आंशिक: gap chase ❌ |
| A2 एकही साधन निर्णायक नाही | `grade.py:score`, `areas.py:active` | `test_chart_reader_grade::*` | ✅ |
| A2 Fibonacci / channel / C=A फक्त ठोस area सोबत | `areas.py:active`, `grade.py` | `test_fibonacci_alone_scores_zero`, `…ruler_counts_only_with_solid_area…` | ✅ |
| A2 horizontal की तिरका, सगळी साधनं | `areas.py:tools` (12), `areas.py:sloping` | `test_all_twelve_tools_present_as_candidates`, golden | ✅ (पण रेषा दर bar ला पुन्हा निवडली जाते — §8.4) |
| A3.1–5 पाच पक्के नियम | `rules.py:check` | `test_hard_rules_each_one_blocks` | आंशिक (नियम 1 मधला gap chase ❌) |
| A3 व्हेटो: A-end / B आत | `evidence.py:vetoes`, `elliott_ctx.py` | `test_veto_elliott_clear_count_only` | ✅ |
| A3 व्हेटो: origin पलीकडे acceptance | `evidence.py:vetoes` | `test_veto_origin_acceptance_and_magnet` | ✅ |
| A3 व्हेटो: MAGNET | `evidence.py:vetoes` | त्याच test मध्ये | ✅ |
| A3 व्हेटो: gap नंतर pullback नाही | `evidence.py:vetoes`, `_pullback_today` | `test_veto_gap_b_without_pullback` | आंशिक: फक्त G3 / G5; "pullback" = आजच्या टोकापासून ≥ 1 MR कुठलीही उलट हालचाल (zone / PDC / gap edge कडे नाही) |
| A3 व्हेटो: pullback खऱ्या area मध्ये संपला (zone शिवाय entry नाही) | — | — | ❌ → §3 (`NO_ZONE` / `FAR_FROM_ZONE`) |
| A3 grade A/B ⇒ entry, C ⇒ नाही | `grade.py:grade_of`, `evaluate.py` | `test_all_evidence_max_is_a_and_thresholds` | ✅ |

## भाग B: Chart Reading Protocol (8 टप्पे)

| टप्पा | Code | Test | स्थिती |
|---|---|---|---|
| 1 HTF trend, protected | `market_state/core.py:trend` (F2), `chart_reader/trend.py:read(ms=…)` | `test_market_state::*` (4 trend tests) | ✅ |
| 1 Daily → 1H क्रम | `trend.py` (areas_tfs: 1h, 75m, 1d levels); Daily trend स्वतंत्र नाही | — | आंशिक |
| 1 Elliott मोठी degree | `elliott_ctx.py:read`, `market_state:elliott_vote` | `test_elliott_*` | आंशिक (label फक्त F4 / EW गुणांसाठी; chart वर नाही) |
| 1 मोठे areas (HTF) | `price_action/levels_v2.py:build` | `test_levels_v2::*` | ✅ (गणना) / ❌ (chart वर नाहीत) |
| 2 impulse ओळख | `market_state:leg_metrics/impulse` (F3) | `test_f3_leg_needs_displacement_overlap_and_bos`, golden | ✅ |
| 2 correction प्रकार | `structure.py:_abc_type`, `_classify` | `test_chart_reader_structure::*` | आंशिक (combination / ending diagonal नाही) |
| 2 A / B / C, A-end entry नाही | `market_state:correction`, `elliott_ctx` | golden 5 Oct | ✅ |
| 2 reversal चिन्हं | `structure.py:read` (F2) | `test_counter_impulsive_is_pb_minus_10…` | ✅ |
| 3 सगळी 12 साधनं | `areas.py:tools` | `test_all_twelve_tools_present_as_candidates` | ✅ |
| 3 selling / buying zone (जन्म: base before displacement, flip, TL, liquidity…) | `areas.py:_role` = **किंमतीच्या वर ⇒ RESISTANCE / खाली ⇒ SUPPORT** | — | ❌ → §2 |
| 3 zone गुणधर्म: state / freshness / touches / reaction / degree | state: TL (`_line_state`) आणि levels_v2 मध्येच; बाकी साधनं hard-coded "ACTIVE"; freshness / reaction नाहीत | `test_levels_v2::*` | आंशिक → §2 |
| 3 active area | `areas.py:active` (ताजे 3 bars + शेवटच्या 12 bars चं टोक) | golden 7 Oct | आंशिक: gap नंतर कालचा touch "active" राहतो (7 Oct 09:30) |
| 3 confluence | `areas.py:active` | `test_ruler_counts…` | ✅ |
| 4 candle प्रत्येक bar | `candles.py:read`: **फक्त शेवटचा candle** | `test_candle_read_control_and_line` | आंशिक → §5 |
| 4 मालिका: correction थकतोय | `structure.py` cw_parts (slower, smaller bodies, more overlap, counter wicks, failed extension) | `test_correction_weakening_score…` | आंशिक: legs लहान होणं, spreads, absorption (effort / result) नाहीत; trend थकणं नाही |
| 4 zone वरच्या 3–6 candles ची गोष्ट | — | — | ❌ → §5 |
| 4 sweep / spring | `evidence.py:liquidity` (pool पलीकडे 0.1–1 MR + reclaim close) | `test_lq_*` | आंशिक: **gap bar / gap ने ओलांडलेली level sweep म्हणून मोजली जाते** (7 Oct 09:30, A-end) → §8.2 |
| 4 futures volume | `chart_reader/volume.py` | `test_chart_reader_volume::*` | ✅ (data असेल तेव्हा) |
| 4 RSI divergence | `evidence.py:divergence` (regular / hidden) | `test_dv_*` | ✅ |
| 4 patterns | `evidence.py:patterns` (flag, wedge, double, H&S) | `test_pt_*` | ✅ |
| 5 gap: वर्ग, location, acceptance / rejection, fill % | `vision/gap_context.py:build` (प्रत्येक evaluate वर पुन्हा) | gap tests, `test_cas::test_gap_context_uses_official_pdc` | ✅ (गणना) |
| 5 gap setups A / B / C, पहिल्या pullback ची वाट, gap-fill → zone → reversal | फक्त GP ±10 आणि G3 / G5 व्हेटो | — | ❌ → §4 |
| 5 gap गोष्ट (कालची शेवटची चाल + आजचा gap) | — | — | ❌ → §4 |
| 5 वेळ / expiry / VIX / event | `evidence.py:time_of_day/vix`, `grade.py` EV | `test_tm_*`, `test_vx_*` | ✅ |
| 6 reversal composite (बंद candle, zone वर) | `chart_reader/reversal.py`, `elliott/reversal.py` | `test_chart_reader_reversal::*` | ✅ |
| 6 correction च्या channel / trendline चा break | — | — | ❌ |
| 7 invalidation (zone पलीकडे / correction टोक) + दोन्ही नोंद | `risk.py:compute` (एकच); vision: `vision_led/validate.py:sl_definitions` (दोन) | `test_risk_*`, `test_two_sl_definitions_7oct_like` | आंशिक (chart_reader मध्ये दोन्ही नोंद नाही) |
| 7 target | `areas.py:trade_targets`, `evaluate.py:trend_extreme` | `test_targets_are_impulse_end…` | ✅ |
| 7 strike σ | `vision_led/validate.py:strike_info` | `test_vision_led::*` | आंशिक (chart_reader मध्ये नाही) |
| 8 गोष्ट + grade + "कुठे चुकीचा" | `narrative.py:build` | `test_evaluate_reports_all_evidence_tools_and_tagged_story` | आंशिक ("कोणत्या zone वर entry" ओळ नाही) |

## भाग D: पुराव्याची यादी (16) आणि grade

| # | Code | Test | स्थिती |
|---|---|---|---|
| T | `grade.py:_trend` | `test_trend_weakening_range_edge…` | ✅ |
| PB | `evidence.py:pullback` | `test_pb_*` | ✅ |
| CW | `structure.py` cw_parts | `test_correction_weakening_score…` | आंशिक (§5 मालिका) |
| AQ / CF | `areas.py:active`, `grade.py` | `test_ruler_counts…` | ✅ |
| LQ | `evidence.py:liquidity` | `test_lq_*` | आंशिक (gap bar sweep) |
| RV | `grade.py:rv_points` | `test_reversal_points_mapping` | ✅ |
| VL | `chart_reader/volume.py:evidence` | `test_vl_dryup…` | ✅ |
| DV | `evidence.py:divergence` | `test_dv_*` | ✅ |
| PT | `evidence.py:patterns` | `test_pt_*` | ✅ |
| GP | `evaluate.py:_gap_evidence` | gap tests | आंशिक: trend सोबतचा gap ⇒ +10 कायम, pullback झाला की नाही न पाहता |
| EW | `elliott_ctx.py`, `grade.py` | `test_elliott_*` | ✅ |
| RM | `grade.py` | `test_trend_weakening_range_edge_gap_event_rr` | ✅ |
| TM / VX / EV | `evidence.py`, `grade.py` | `test_tm_*`, `test_vx_*` | ✅ |
| Grade A ≥ 60, B 45–59 | `grade.py:grade_of` | `test_all_evidence_max_is_a_and_thresholds` | ✅ |
| अंतिम grade = min(code, vision) | — | — | ❌ (Stage 1) |

## भाग E: नेहमीच्या चुका

| # | Code / बचाव | Test | स्थिती |
|---|---|---|---|
| 1 trendline विसरली | `areas.py:sloping` | golden 7 Oct | ✅ (गणना) / आंशिक (chart crop) |
| 2 Fibonacci एकटा | `areas.py:active` | `test_fibonacci_alone_scores_zero` | ✅ |
| 3 A-end = C-end | market_state labels | golden T6 | ✅ |
| 4 expanded flat B = breakout | `trend_extreme`, `_abc_type` | `test_target_extreme_covers_expanded_flat_b…` | आंशिक |
| 5 पहिला CHoCH = reversal | F2 | `test_break_without_confirmation_is_testing…` | ✅ |
| 6 wick = sweep | `liquidity` (reclaim close हवा) | `test_lq_no_reclaim…` | आंशिक: gap open / gap bar ला sweep म्हणतो |
| 7 acceptance नंतर fade | `breaks.py`, vetoes | `test_veto_origin_acceptance…` | ✅ |
| 8 minor line break = reversal | F2 | `test_trend_down_protected_holds…` | ✅ |
| 9 चालू candle | `bar_end ≤ asof` सगळीकडे | `test_v5_*` | ✅ |
| 10 09:15 candles | TM −5 | `test_tm_*` | आंशिक (LQ / structure मध्ये 09:15 bar सामान्य bar सारखा) |
| 11 divergence वरून counter trade | DV फक्त पुरावा | `test_dv_*` | ✅ |
| 12 pattern नाव | composite reversal | `test_chart_reader_reversal::*` | ✅ |
| 13 strike level जवळ | vision_led σ | — | आंशिक |
| 14 HTF न पाहता trend | market_state | golden | ✅ |
| 15 image वरून किंमत | `vision_led/validate.py:check_refs` | `test_vision_led::*` | ✅ |
| 16 X wave = correction संपला | — | — | ❌ |
| 17 gap open पाठलाग | `gap_chase` नेहमी False; व्हेटो फक्त G3 / G5 | `test_veto_gap_b…` | **❌** (v1 मध्ये ✅ लिहिलं होतं — चूक; 7 Oct 09:30) |

## भाग G: विरोधाभासांचे निर्णय

| विषय | Code | स्थिती |
|---|---|---|
| Real break एकच (`elliott/breaks.py`) | market_state, `_origin_break`; `areas.py:_line_state` स्वतःची व्याख्या | आंशिक |
| Displacement व्याख्या | breaks / zones / market_state वेगवेगळे आकडे | आंशिक |
| MR = 20 बंद bars | `breaks.py:median_range` | ✅ |
| Swing engine एकच | `elliott/swings.py` | ✅ |
| HTF trend = context, gate नाही | `grade.py` T; F4 फक्त इशारा | आंशिक (Abhi निर्णय: F4 gate?) |
| खोली 38.2–80% | `structure.py`, `evidence.py:pullback` | ✅ |
| CAS | `opportunity_engine/cas.py` + resamplers | ✅ `test_cas::*` |

## भाग H: Golden setups G1–G7

| Setup | Code | Test | स्थिती |
|---|---|---|---|
| G1–G6 detector, candidates वर setup label, vision `setup_type`, playbook मजकूर | मसुदा तयार (`backtest_review/gallery.py`, playbook v3) — repo मध्ये नाही | मसुद्यात 7 tests (real data G3 / G5 सकट) | ❌ (repo) — K-10 नंतर |
| **G7 exhaustion gap reversal** (KB भाग H, K13 setup D → G7; `gap_setup_g7` ON PAPER, स्वतंत्र scorecard): stretched trend + G5/E gap थेट न तुटलेल्या major HTF (D2/D3) zone मध्ये + पहिल्या 2–6 bars मध्ये rejection ⇒ पहिल्या pullback वर reversal; SL gap दिवसाचं टोक + buffer; target PDC / gap fill | — (gap_context मध्ये G5 / E वर्ग आहेत; major HTF zones `levels_v2` मध्ये; stretch / rejection / G7 setup नाही) | — | ❌ → §4A |
| Checklist #22 "setup प्रकार" (G1–G7) | त्याच detector वरून | — | ❌ |

## K1–K14

| Chapter | मुख्य नियम | Code | Test | स्थिती |
|---|---|---|---|---|
| K1 | HH/HL, protected, CHoCH, reversal | `market_state:trend` | `test_market_state::*` | ✅ |
| K1 | multi-TF secondary reaction | F2 + F4 | golden | ✅ |
| K1 | trend थकणं (marginal HH, मोठा pullback) | — | — | ❌ |
| K2 | impulse वि. correction | `leg_metrics`, `structure.py` | `test_f3_leg…` | आंशिक (ER 0.45 — Abhi मंजुरी) |
| K3 | R1–R11, प्रकार, बंदी | `elliott/*`, `elliott_ctx`, `_abc_type` | elliott tests | आंशिक (ED / combination नाही) |
| K4 | base / flip / range edge / supply–demand | `areas.py:base_zones`, `levels_v2` | `test_base_before_displacement_is_tool_c` | आंशिक: base सापडतो पण "selling / buying" भूमिका किंमतीवरून; freshness / reaction नाही |
| K5 | pools, sweep, real break, magnet | `evidence.py:liquidity/pools`, `breaks.py`, `levels_v2` | `test_lq_*`, `test_chop_is_magnet` | आंशिक (gap sweep) |
| K6.1 | trendline ≥ 3 touches | `areas.py:sloping` | golden | ✅ (गणना); आंशिक: दर bar ला नवी "सर्वोत्तम" रेषा |
| K6.2–6.3 | channels | `areas.py:_channels` | `test_all_twelve_tools…` | आंशिक |
| K6.4 | horizontal की तिरका — price action वरून | `areas.py:active` | golden | ✅ |
| K7 | Fibonacci confluence | `areas.py:_fib` | `test_fibonacci_alone_scores_zero` | ✅ |
| K8 | round / PDH / PDL / PDC / week H/L | `areas.py:_rounds/_pd_levels` | `test_cas::test_chart_reader_prior_levels…` | ✅ (गणना) / ❌ (chart वर नाहीत) |
| K9 | candle psychology, logical reversal | `candles.py`, `reversal.py` | `test_chart_reader_reversal::*` | आंशिक (फक्त शेवटचा candle) |
| K10.1 | price-only ताकद (legs, overlap, spreads, wicks, failed ext.) | `structure.py` cw_parts | ✅ tests | आंशिक (legs लहान / spreads / absorption नाहीत) |
| K10.2 | RSI divergence | `evidence.py:divergence` | `test_dv_*` | ✅ |
| K10.3 | futures volume | `chart_reader/volume.py` | `test_chart_reader_volume::*` | ✅ |
| K11 | patterns | `evidence.py:patterns` | `test_pt_*` | ✅ |
| K12 | Wyckoff / absorption (effort वि. result) | — | — | ❌ |
| K13 | gaps: वर्ग + behaviour | `vision/gap_context.py` | gap tests | ✅ |
| K13 | gap setups, first pullback, chase बंदी, gap गोष्ट | — | — | ❌ → §4 |
| K13 | setup D → G7 exhaustion gap (आधी OFF, आता PAPER ON) | — | — | ❌ → §4A |
| K14 | session, expiry, VIX, σ strike | `evidence.py`, `vision_led/validate.py` | `test_tm_*`, `test_vx_*` | आंशिक |

## नवीन मागण्या (§2–§5A): आत्ताची स्थिती

| § | मागणी | आत्ता | काय करायचं |
|---|---|---|---|
| 2 | Selling / buying zones (7 प्रकार + उलट), गुणधर्म (id, प्रकार, MR पट्टा, degree / TF, freshness, state, touches, reaction) | 12 साधनं; भूमिका किंमतीवरून; state बहुतेक "ACTIVE" | `chart_reader/zones.py` (नवीन): जन्मावरून supply / demand, पाच states (`breaks.py` real break), freshness (touches नंतर), reaction (touch नंतरची चाल MR मध्ये), मोठा lookback, truncation-invariant |
| 2 | Chart वर लाल / हिरवी छटा, label "S1 · flip · 15M · ACTIVE · 2 touches", 1H + 15M | फक्त active area | `backtest_review/charts.py` zones layer; मोठ्या lookback वर गणना, मग crop |
| 3 | Zone शिवाय entry नाही: reversal zone मध्ये / ≤ `zone_entry_tol_mr` 0.3; entry ≤ `max_entry_dist_mr` 1.0 | नाही | `rules.check` मध्ये नवीन नियम + `NO_ZONE` / `FAR_FROM_ZONE` codes; SL दोन व्याख्या (zone दूरची कड / correction टोक) दोन्ही नोंद |
| 4 | Gap: 09:15 वर्ग + location + trend संबंध; प्रत्येक bar ला acceptance / fill; setups A/B/C; `GAP_NO_PULLBACK`; गोष्ट; chart वर gap पट्टा | वर्ग + behaviour ✅; बाकी ❌ | `chart_reader/gap.py` (नवीन, gap_context वर): first-pullback state machine, gap-fill → zone → reversal = setup, GP नव्याने |
| 4A | G7 exhaustion gap: stretch (leg / ATR, legs लहान, DV, Elliott 5 / C-end), G5/E gap major HTF zone मध्ये, 2–6 bars rejection (failed extension, wick, open / edge reclaim, volume climax), पहिला pullback + reversal; opening window / पहिली recovery candle वर नाही; SL gap टोक, target PDC; स्वतंत्र scorecard; 4 tests (a–d); Gallery मध्ये G7 (8) | काही नाही (G5 / E वर्ग आणि HTF levels फक्त) | `chart_reader/gap.py` मध्ये G7 state (gap setups सोबत), setting `gap_setup_g7` (default ON, PAPER), checklist #15 / #22 |
| 5 | प्रत्येक बंद 15M candle (CL, body, wicks, range/MR, control, ओळ); leg मालिका; zone वरच्या 3–6 candles ची गोष्ट; chart वर फक्त entry area candles वर खुणा | फक्त शेवटचा candle + 5 cw खुणा | `chart_reader/candles.py`: `series()` + `leg_read()` + `zone_story()`; absorption; CW त्यावरून |
| 5A | 23 बाबींचा checklist, क्रमाने; रिकामी ⇒ `CHECKLIST_INCOMPLETE`; trade card / page वर तक्ता; Telegram सारांश; vision JSON मध्येही | नाही | `chart_reader/checklist.py`: 23 बाबी (खाली), evaluate चा भाग; test: एक बाब काढली ⇒ fail |

### §5A checklist: 23 बाबी आत्ता कुठून मिळतात

| # | बाब | आत्ताचा स्रोत | स्थिती |
|---|---|---|---|
| 1 | HTF trend, protected | `market_state.trend` | ✅ |
| 2 | Elliott position | `elliott_ctx.read` (`run_elliott=False` ⇒ gray) | ✅ ("लागू नाही" कारणासह) |
| 3 | impulse | `market_state.impulse` | ✅ |
| 4 | correction / reversal / unclear | `structure.read` pullback | ✅ |
| 5 | correction प्रकार, टप्पा | `_abc_type`, labels | आंशिक (combo / ED नाही) |
| 6 | retrace % | `structure.retrace` | ✅ |
| 7 | zones (a–l) selling / buying | `areas.tools` | आंशिक (§2) |
| 8 | active zone | `areas.active` | ✅ |
| 9 | confluence | `active.confluence` | ✅ |
| 10 | liquidity / sweep | `evidence.liquidity` | आंशिक (§8.2) |
| 11 | candle मालिका | cw_parts | आंशिक (§5) |
| 12 | futures volume | `volume.evidence` | ✅ ("उपलब्ध नाही" कारणासह) |
| 13 | RSI divergence | `evidence.divergence` | ✅ |
| 14 | chart pattern | `evidence.patterns` | ✅ |
| 15 | gap गोष्ट | `gap_context` | आंशिक (§4) |
| 16 | वेळ / expiry / event / VIX | `time_of_day`, `vix`, EV | ✅ |
| 17 | reversal composite | `reversal.evaluate` | ✅ |
| 18 | zone जवळ entry | — | ❌ (§3) |
| 19 | invalidation + target | `risk.compute` | ✅ (दोन SL नोंद आंशिक) |
| 20 | R:R | `risk.rr` | ✅ |
| 21 | पक्के नियम + A3 व्हेटो | `rules.check`, `vetoes` | आंशिक (gap chase, zone) |
| 22 | setup G1–G6 | gallery मसुदा | ❌ (repo) |
| 23 | evidence + grade | `grade.score` | ✅ |

## §8: 7 Oct च्या दुरुस्त्या → code मधलं मूळ कारण → सर्वसाधारण नियम

| # | दिसलेली चूक | मूळ कारण (code) | सर्वसाधारण नियम / दुरुस्ती | आधी लिहायचा failing test |
|---|---|---|---|---|
| 8.1 | 09:30 B = gap chase | `gap_chase=False`; व्हेटो फक्त G3 / G5; GP +10; entry ↔ area अंतर नाही | trend सोबतचा कुठलाही gap (G2 / G3 / G5) ⇒ पहिला pullback (gap fill / PDC / gap edge / active zone कडे) + तिथे reversal येईपर्यंत `GAP_NO_PULLBACK`; `FAR_FROM_AREA` (> 1.0 MR) | synthetic gap-down + सरळ घसरण ⇒ entry नाही; gap-fill rally zone ला लागून reversal ⇒ entry; golden 7 Oct: 09:30 नाही, 12:15 A |
| 8.2 | gap bars वर "sweep" | `liquidity`: pool ची पातळी आधी किंमत कुठे होती ते पाहत नाही; 09:15 bar सामान्य | sweep = pool कडे त्याच बाजूने आलेली किंमत, wick ने पार, आत close; gap open / gap ने ओलांडलेली level = sweep नाही | synthetic gap through pool ⇒ LQ 0; खरा sweep ⇒ LQ > 0 |
| 8.3 | 7 ✅ (एकाच correction वर) | evaluate stateless; backtest मध्ये फक्त एक position | एकाच correction (C/E-end + active zone) वर पहिली valid entry ⇒ बाकी `DUP_SETUP`, invalidation / नवा correction होईपर्यंत; हा नियम gap नियमानंतर | 7 Oct ⇒ फक्त 12:15 |
| 8.4 | anchor 30 Sep 09:15 | chart crop (day chart आदले 1–2 sessions); anchor x window च्या पहिल्या bar वर दाबला | anchors फक्त confirmed pivots, मोठ्या lookback वर; chart बाहेर ⇒ edge label; रेषा दर bar ला बदलू नये (स्थिर ओळख: anchors जोडी कायम, नवीन touch ⇒ तीच रेषा) | anchor timestamps window वर अवलंबून नाहीत; 7 Oct रेषा 28 Sep / 30 Sep / 7 Oct |
| 8.5 | day chart वर areas / labels नाहीत; lookback कमी | day chart = आदले 1–2 sessions, फक्त active area; 15M entry chart ≥ 5 sessions hard-coded | **adaptive window:** 15M = impulse सुरुवातीच्या थोडं आधीपासून (impulse + correction + active zone anchors), 2–15 sessions; 1H 20–40 sessions; line chart सर्वात लांब; मोठी चाल ⇒ window / y-axis आपोआप. गणना (zones, swings, trendlines, Elliott: D1 ~2 आठवडे, D2 ~6 आठवडे, D3 ~6 महिने+) window पासून वेगळी. नवीन किंमत क्षेत्र ⇒ जुने न तुटलेले मोठ्या degree levels + round numbers + नवे swings; सगळे वापरलेले zones (साधन + id), प्रत्येक ✅ वर "12:15 A 67.5 · area …" label; A/B/C pivot वर, बाहेर गेले ⇒ edge label | chart test: 5 Oct 22,217 window मध्ये; labels उपस्थित |

### वेग (§8.5, नवीन)

| मागणी | आत्ता | काय करायचं |
|---|---|---|
| रोज संध्याकाळी history precompute; प्रत्येक बंद 15M bar वर फक्त incremental | evaluate प्रत्येक वेळी पूर्ण गणना (90 दिवस lookback; market_state + 12 साधनं + Elliott) | `chart_reader/precompute.py`: HTF zones / degree swings / trendline anchors cache (truncation-invariant), bar वर फक्त नवे bars |
| code facts ≤ 20 s, chart ≤ 5 s, vision ≤ 40 s (≈ 1 मिनिट) — मोजून अहवालात | मोजलेलं नाही | K-10 run मध्ये प्रत्येक टप्प्याची वेळ नोंद (p50 / max) अहवालात |

## प्रस्तावित क्रम (एक PR, प्रत्येक दुरुस्तीसाठी failing test आधी)

1. **§8.1 gap नियम** (`GAP_NO_PULLBACK`, `FAR_FROM_AREA`) + §4 gap state machine (setups A/B/C, gap गोष्ट) + **§4A G7**.
2. **§8.2 sweep व्याख्या.**
3. **§8.3 `DUP_SETUP`** (gap नियमानंतर).
4. **§2 zones** (selling / buying, गुणधर्म) ⇒ **§3 zone entry नियम** (`NO_ZONE` / `FAR_FROM_ZONE`, दोन SL).
5. **§5 candle-by-candle** (series, leg read, zone story, absorption ⇒ CW).
6. **§5A checklist** (23 बाबी, `CHECKLIST_INCOMPLETE`).
7. **§8.4–8.5 charts** (zones layer, gap पट्टा, entry-area candle खुणा, adaptive window, edge labels, स्थिर trendline) + precompute / वेळ मोजणी.
8. Settings (सगळे नवीन tolerances MR मध्ये, dashboard वर) → full suite → PR → स्वतंत्र review → merge → **K-10** (10 random दिवस, seed नोंद).

**Abhi साठी प्रश्न (तक्त्यावरून):**

- **(a)** G2 gap (trend सोबत, PDH/PDL च्या आत) सुद्धा "पहिला pullback हवा" मध्ये धरू का? मी धरतोय: KB K13 "trend सोबतचा gap".
- **(b)** trendline दर bar ला पुन्हा निवडायची नाही, एकदा सापडलेली रेषा touches वाढवत ठेवायची. ठीक?
- **(c)** F4 gate आणि ER 0.45: आधीचे प्रश्न अजून उघडे.

## v1 (C-V1) मधून कायम नोंदी


- दुरुस्त: F2 reversal नंतरचं trend टोक (BOS कायमचा बंद होत होता — 20 Aug ला trend चुकीचा "up/trend"); OE चा PDC (CAS-आधीचा close ⇒
  official close); trendline वर active-area तुलना त्या bar वरच्या रेषेच्या मूल्याशी; instant (5M) profile साठी impulse टोकांचा खरा bar;
  HTF range + लहान frames वर crash; Elliott vote अपयशाचं कारण नोंद; impulse विस्तार origin real break नंतर नाही; रिकामा 1d frame;
  15M / 1H तक्त्यातील एकाच वेळेचे ohlc_ref; vision तक्त्यात CAS सूचना; G-E1a research scripts सुद्धा market_state वरून.
- **Contaminated काळावरून ठरलेले आकडे (Abhi मंजुरी हवी; tuning नाही असा नियम):** `impulse_er_min` 0.45 (7 Oct overlap 0.62),
  `tl_search_pivots` 16 / `tl_search_bars` 200 (28 Sep anchor दिसावा म्हणून), `active_extreme_bars` 12 (12:00 rejection). IS / VAL वर
  backtest visual review मध्ये तपासायचे.
- K6 सावधानता: प्रत्येक bar ला ~120 जोड्यांतून सर्वोत्तम रेषा ⇒ "दर bar रेषा पुन्हा काढणं" (curve-fit) धोका — review मध्ये पाहायचं.
- F4 + HTF range (dir 0): side impulse वरून (विरोध नाही म्हणून) — Abhi ने स्पष्ट करायचं.
- अजून market_state न वापरणारे: OE / PCS live trend; `structure.read` चा जुना finder फक्त `ms` नसताना (tests).

