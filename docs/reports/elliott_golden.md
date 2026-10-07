# Golden-file regression — NIFTY 25 Sep – 6 Oct 2026

> Data: `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-06.csv.gz` (contaminated काळ, फक्त golden; 1 Jul – 24 Sep warm-up). अपेक्षा: `docs/reports/elliott_golden_expectations.json` (Master §4). Signal + plan स्तर; premiums नाहीत. T5 sizing स्तरावर (default tier_of_A, प्रति-lot तोटा = width × lot).

## 1. सारांश — प्रत्येक variant

| अपेक्षा | level | E4_default | b_profile | c1_time_slot | c2_cap_logic | c3_reclaim_depth | c4_overlap | c5_path_n3 | c6_body_fix | c7_followthrough | c7b_followthrough_gate | c8_c_leg_exhaustion | c_all | d_profile_c_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | verify | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ |
| T2 | must | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| T3 | must | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| T4 | must | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| T5 | must_not | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| T6 | must_not | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| T7 | must | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| T8 | must | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| T9 | report | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ | ℹ️ |
| R-gap-0928 | must_not | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| R-gap-1006 | must_not | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| R-1006-0940 | must_not | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

✅ PASS · ❌ FAIL · ℹ️ REPORT (verify/report स्तर). FAIL संख्या: E4_default 5, b_profile 5, c1_time_slot 5, c2_cap_logic 5, c3_reclaim_depth 5, c4_overlap 5, c5_path_n3 5, c6_body_fix 5, c7_followthrough 5, c7b_followthrough_gate 5, c8_c_leg_exhaustion 5, c_all 5, d_profile_c_all 5

## 2. E4 default — तपशील

| अपेक्षा | level | निकाल | तपशील |
|---|---|---|---|
| T1 | verify | REPORT | जुळणारा signal नाही |
| T2 | must | FAIL | जुळणारा signal नाही · त्या वेळची कारणं: D2:next_not_motive ×42, D0:gray ×19, D1:gray ×17, D0:no_count ×10, D0:inside_B_X_triangle ×9 |
| T3 | must | FAIL | जुळणारा signal नाही · त्या वेळची कारणं: D0:no_count ×60, D1:no_count ×60, D2:next_not_motive ×50, D1:gray ×15, D2:inside_B_X_triangle ×15 |
| T4 | must | FAIL | जुळणारा signal नाही · त्या वेळची कारणं: D2:gray ×32, D1:gray ×21, D0:gray ×17, D0:no_count ×12, D1:inside_B_X_triangle ×12 |
| T5 | must_not | PASS | जुळणारा signal नाही |
| T6 | must_not | PASS | जुळणारा signal नाही |
| T7 | must | FAIL | जुळणारा signal नाही · त्या वेळची कारणं: D1:gray ×16, D2:gray ×16, D0:no_count ×12, D0:gray ×4 |
| T8 | must | FAIL | जुळणारा signal नाही · त्या वेळची कारणं: D0:gray ×10, D1:gray ×7, D2:gray ×6, D1:inside_B_X_triangle ×6, D2:not_ttf_close ×4 |
| T9 | report | REPORT | जुळणारा signal नाही |
| R-gap-0928 | must_not | PASS | — |
| R-gap-1006 | must_not | PASS | — |
| R-1006-0940 | must_not | PASS | — |

### Golden काळातले सगळे signals (E4 default, 1)

| वेळ | D | setup | tier | दिशा | TTF | extreme | hard inv | score | label | sized |
|---|---|---|---|---|---|---|---|---|---|---|
| 09-29 14:35 | 1 | S9 | A | bear_call | 5m | 22696.0 | 22705.0 | 0.717 | shooting-star-like | हो |

### 5 Oct 09:45–10:20 (A-end, T6) — scanner ची कारणं (E4 default)

- D0 —: gray × 3
- D0 S6b: tf_bars_min × 5
- D1 —: gray × 8
- D2 —: gray × 8

## 3. निदान — must वेळांना degrees काय पाहत होते (E4 default)

प्रत्येक must च्या वेळ-खिडकीच्या शेवटी (किंवा आधीचा शेवटचा scan): degree → gray?, vote वर/खाली, preferred count (pattern, चालू wave, pattern दिशा). Setup ला त्या degree चा non-gray count, parent शी जुळणारी दिशा आणि पुढची motive trade दिशेने हवी.

| must | scan | D0 | D1 | D2 | D3 |
|---|---|---|---|---|---|
| T2 | 09-29 15:30 | gray ↑None ↓None | gray ↑None ↓None | ok ↑0.0 ↓0.65 triangle/D/-1 | gray ↑0.2 ↓0.0 impulse/3/-1 |
| T3 | 09-30 15:30 | gray ↑0.0 ↓0.0 impulse/5/-1 | gray ↑0.0 ↓0.0 flat/A/-1 | ok ↑0.76 ↓0.0 flat/B/+1 | ok ↑0.0 ↓0.65 flat/B/-1 |
| T4 | 10-01 12:00 | gray ↑None ↓None | gray ↑0.0 ↓0.0 impulse/3/-1 | gray ↑0.0 ↓0.0 flat/A/-1 | gray ↑0.43 ↓0.0 wxy/Y/-1 |
| T7 | 10-05 13:10 | gray ↑None ↓None | gray ↑0.0 ↓0.0 flat/A/-1 | gray ↑0.0 ↓0.0 triangle/C/-1 | gray ↑0.25 ↓0.0 wxy/Y/-1 |
| T8 | 10-05 14:10 | ok ↑1.0 ↓0.0 flat/B/+1 | gray ↑0.0 ↓0.0 end_diag/1/+1 | ok ↑0.0 ↓0.79 zigzag/C/+1 | ok ↑0.0 ↓0.8 flat/B/-1 |

**D1–D3 pivots व confirm वेळ** (pivot चा bar → confirmed_at):

| D | प्रकार | किंमत | pivot | confirmed |
|---|---|---|---|---|
| D1 | L | 22808 | 09-28 11:15 | 09-28 12:30 |
| D1 | H | 22855 | 09-28 12:25 | 09-28 13:10 |
| D1 | L | 22570 | 09-29 09:35 | 09-29 11:00 |
| D1 | H | 22753 | 09-29 12:05 | 09-29 12:30 |
| D1 | L | 22628 | 09-29 12:30 | 09-29 13:00 |
| D1 | H | 22705 | 09-29 12:55 | 09-29 13:40 |
| D1 | L | 22629 | 09-29 13:35 | 09-29 14:35 |
| D1 | H | 22772 | 09-30 10:20 | 09-30 10:45 |
| D1 | L | 22666 | 09-30 11:15 | 09-30 12:00 |
| D1 | H | 22809 | 09-30 12:45 | 09-30 13:40 |
| D1 | L | 22508 | 10-01 09:25 | 10-01 10:10 |
| D1 | H | 22611 | 10-01 10:05 | 10-01 11:10 |
| D1 | L | 22217 | 10-01 14:05 | 10-01 14:35 |
| D1 | H | 22622 | 10-05 09:50 | 10-05 10:30 |
| D1 | L | 22397 | 10-05 12:05 | 10-05 13:15 |
| D1 | H | 22732 | 10-06 14:05 | 10-06 14:30 |
| D1 | L | 22685 | 10-06 14:25 | 10-06 15:30 |
| D2 | L | 22570 | 09-29 09:35 | 09-29 12:05 |
| D2 | H | 22809 | 09-30 12:45 | 09-30 14:20 |
| D2 | L | 22217 | 10-01 14:05 | 10-01 15:10 |
| D2 | H | 22622 | 10-05 09:50 | 10-05 11:50 |
| D2 | L | 22397 | 10-05 12:05 | 10-05 13:45 |
| D3 | L | 22570 | 09-29 09:35 | 09-30 13:30 |
| D3 | H | 22809 | 09-30 12:45 | 10-01 11:15 |
| D3 | L | 22217 | 10-01 14:05 | 10-05 13:40 |
