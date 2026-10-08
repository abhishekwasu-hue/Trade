# Chart Reader — funnel (C-V1 आधीचा, legacy ad-hoc impulse finder; तुलनेसाठी)

> IS 2015–2021, 15m, SRv2 profile, 364.0 आठवडे. Settings/thresholds बदलले नाहीत: {'impulse_min_mr': 6.0, 'swing_atr_mult': 3.0, 'internal_atr_mult': 1.5, 'impulse_lookback_legs': 8, 'zigzag_b_max': 0.79, 'flat_b_min': 0.9, 'flat_c_min': 0.9, 'retrace_max': 0.8, 'disp_bars_reversal': 2}.

## 1. Funnel (प्रति आठवडा सरासरी)

| पायरी | bars | / आठवडा | मागच्या पायरीतून टिकले |
|---|---|---|---|
| a 15M bars | 42,669 | 117.22 | — |
| b impulse + corrective pullback | 834 | 2.29 | 2.0% |
| c pullback-end candidates | 675 | 1.85 | 80.9% |
| d ठोस area touch | 376 | 1.03 | 55.7% |
| e reversal ok | 177 | 0.49 | 47.1% |
| f व्हेटो पास | 173 | 0.48 | 97.7% |
| g R:R ≥ 3 | 81 | 0.22 | 46.8% |
| h grade A/B | 22 | 0.06 | 27.2% |
| entry (बाकी पक्के नियम सुद्धा) | 21 | 0.06 | 95.5% |

Unique setups (एकाच correction चे सलग bars एक): candidates 175, A/B (a–h) 16, entries 15.

## 2. (b) का गळतं — structure

- Impulse सापडला: 86.2% bars
- Correction प्रकार (impulse असलेल्या bars): {'complex': 83.2, 'ABCD': 4.9, 'AB': 4.0, 'A': 2.8, 'unclear': 1.4, 'zigzag': 1.4, 'flat': 1.3, 'impulsive': 0.7, 'triangle': 0.3}
- Pullback label: {'reversal': 58.7, 'pullback': 38.4, 'unclear': 2.9} · reversal कारणं: {'counter_move_impulsive': 58.0, 'impulse_origin_acceptance': 6.6}
- Correction legs (p10/p25/p50/p75/p90): [3.0, 6.0, 11.0, 17.0, 22.0] · > 5 legs ("complex"): 79.2%

Sensitivity (फक्त माहिती, settings बदलले नाहीत):

| बदल | corrective / आठवडा | candidates bars / आठवडा | unique / आठवडा |
|---|---|---|---|
| impulse_min_mr 4 | 2.29 | 1.85 | 0.48 |
| swing_atr_mult 2 | 4.59 | 3.68 | 1.0 |
| internal_atr_mult 1.0 | 1.37 | 1.12 | 0.45 |
| impulse_lookback_legs 4 | 4.68 | 4.14 | 1.07 |

## 3. ठोस area touch

- Touch नाही: 44.3% candidates
- सरासरी candidates / bar (साधन a–l): {'a': 2.57, 'b': 0.45, 'c': 0.37, 'd': 2.57, 'e': 3.31, 'f': 2.0, 'g': 2.0, 'h': 4.0, 'i': 3.0, 'j': 2.81, 'k': 5.0, 'l': 2.21}
- Active area कोणत्या साधनाचा: {'k': 30.3, 'e': 28.5, 'l': 13.6, 'j': 11.7, 'c': 8.5, 'b': 5.9, 'a': 0.8, 'd': 0.8}
- Active zone रुंदी (MR, p10…p90): [0.2, 0.28, 0.5, 0.55, 1.71]
- Touch नसताना जवळच्या trade-बाजूच्या ठोस area पर्यंत अंतर (MR, p10…p90): [0.18, 0.45, 1.02, 1.77, 2.86] · {'≤0.25 MR': np.float64(14.0), '≤0.5 MR': np.float64(28.1), '≤1.0 MR': np.float64(49.5), '≤2.0 MR': np.float64(79.9)}
- Touch व्याख्या: शेवटच्या 3 बंद bars पैकी एकाची high–low पट्टी zone ला छेदते (अतिरिक्त tolerance नाही); zone रुंदी साधनानुसार: trendline ± 0.2 MR, round / PDH-PDL ± 0.25 MR, swing / equal pools ± 0.1 MR, HTF levels (levels_v2) ± 0.25 HTF-MR (किमान 0.5 HTF-MR).

10 उदाहरणं (charts trade-data मध्ये, `chart_reader/no_touch/`):

- 2015-10-06 13:00:00 · बाजू +1 · जवळचा area 6.21 MR · `no_touch_20151006_1300.png`
- 2017-12-12 12:45:00 · बाजू +1 · जवळचा area 5.81 MR · `no_touch_20171212_1245.png`
- 2019-08-23 14:15:00 · बाजू -1 · जवळचा area 0.14 MR · `no_touch_20190823_1415.png`
- 2015-03-27 14:15:00 · बाजू -1 · जवळचा area 1.21 MR · `no_touch_20150327_1415.png`
- 2016-04-06 13:30:00 · बाजू -1 · जवळचा area 0.15 MR · `no_touch_20160406_1330.png`
- 2018-06-29 12:45:00 · बाजू -1 · जवळचा area 0.48 MR · `no_touch_20180629_1245.png`
- 2016-02-15 10:15:00 · बाजू -1 · जवळचा area 1.9 MR · `no_touch_20160215_1015.png`
- 2017-03-01 10:45:00 · बाजू -1 · जवळचा area 4.05 MR · `no_touch_20170301_1045.png`
- 2015-03-27 15:00:00 · बाजू -1 · जवळचा area 0.57 MR · `no_touch_20150327_1500.png`
- 2018-07-31 11:00:00 · बाजू +1 · जवळचा area 0.21 MR · `no_touch_20180731_1100.png`

## 4. R:R — चार संयोजनं (risk, reward MR मध्ये; p10/p25/p50/p75/p90)

| invalidation × target | n | risk MR | reward MR | R:R | R:R ≥ 3 % | setups / आठवडा (बाकी पायऱ्या पास) |
|---|---|---|---|---|---|---|
| area×nearest_area | 376 | [0.49, 0.64, 0.94, 1.43, 2.48] | [0.09, 0.31, 0.76, 1.34, 1.9] | [0.07, 0.24, 0.69, 1.53, 2.73] | 8.0 | 0.01 |
| area×impulse_end | 376 | [0.49, 0.64, 0.94, 1.43, 2.48] | [2.55, 3.13, 4.27, 6.17, 8.44] | [1.49, 2.67, 4.71, 7.36, 11.23] | 69.1 | 0.07 |
| candle×nearest_area | 376 | [0.35, 0.57, 0.91, 1.28, 1.65] | [0.08, 0.3, 0.74, 1.31, 1.88] | [0.09, 0.33, 0.83, 1.58, 2.93] | 9.8 | 0.0 |
| candle×impulse_end | 376 | [0.35, 0.57, 0.91, 1.28, 1.65] | [2.56, 3.17, 4.39, 6.3, 8.53] | [1.88, 2.89, 5.05, 9.52, 15.65] | 73.7 | 0.06 |
| सध्याचा | 376 | [0.71, 0.94, 1.38, 2.33, 3.77] | [2.56, 3.17, 4.39, 6.3, 8.53] | [0.71, 1.67, 3.4, 5.88, 8.75] | 57.4 | 0.04 |

- area = active area ची दूरची कड + 0.25 MR · candle = reversal composite चं टोक + 0.25 MR · nearest_area = पुढचा ठोस opposite area (सगळी साधनं) · impulse_end = impulse सुरू झाल्यापासूनचं trade-दिशेचं टोक. सध्याचा = तिन्हीपैकी दूरची invalidation (area / candle / correction टोक) × impulse टोक + पलीकडचे HTF areas.
