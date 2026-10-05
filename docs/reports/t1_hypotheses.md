# T1 — निदान गृहीतकं H1–H5 (Opportunity Engine, V1)

तयार: 2026-10-05 · डेटा: `data/nifty50_1min.parquet` (2015-01-15 → 2024-03-27) · दिवस: IS 1716, VAL 553.
R = साइज-विना (प्रति ट्रेड risk एककात), slippage सह. **फक्त अहवाल — कुठलाही डीफॉल्ट बदललेला नाही.** Sealed holdout वापरलेला नाही.

## 1. सर्व trials — IS वि. Validation (V1, सर्व setups)

| trial | period | trades | win_pct | expectancy_r | profit_factor | total_r | max_dd_r |
|---|---|---|---|---|---|---|---|
| BASE | IS 2015→2021 | 390 | 44.1 | -0.182 | 0.66 | -71.11 | 72.91 |
| BASE | VAL 2022→2024-03 | 148 | 53.4 | 0.033 | 1.08 | 4.94 | 6.68 |
| H1 | IS 2015→2021 | 383 | 44.1 | -0.181 | 0.66 | -69.38 | 71.18 |
| H1 | VAL 2022→2024-03 | 146 | 53.4 | 0.029 | 1.07 | 4.28 | 7.63 |
| H3_020 | IS 2015→2021 | 230 | 47.4 | -0.071 | 0.84 | -16.4 | 23.17 |
| H3_020 | VAL 2022→2024-03 | 86 | 52.3 | 0.003 | 1.01 | 0.29 | 7.82 |
| H3_025 | IS 2015→2021 | 166 | 50.0 | -0.037 | 0.91 | -6.13 | 18.57 |
| H3_025 | VAL 2022→2024-03 | 59 | 54.2 | 0.053 | 1.14 | 3.14 | 5.57 |
| H4a_none | IS 2015→2021 | 386 | 44.0 | -0.183 | 0.66 | -70.71 | 73.03 |
| H4a_none | VAL 2022→2024-03 | 147 | 54.4 | 0.038 | 1.09 | 5.61 | 7.24 |
| H4b_12bars | IS 2015→2021 | 388 | 43.6 | -0.186 | 0.66 | -72.01 | 74.34 |
| H4b_12bars | VAL 2022→2024-03 | 147 | 55.1 | 0.042 | 1.1 | 6.19 | 6.51 |
| H4c_or_reentry | IS 2015→2021 | 388 | 43.8 | -0.181 | 0.66 | -70.22 | 72.54 |
| H4c_or_reentry | VAL 2022→2024-03 | 147 | 54.4 | 0.056 | 1.13 | 8.18 | 6.08 |
| H5 | IS 2015→2021 | 162 | 48.8 | -0.036 | 0.92 | -5.86 | 18.71 |
| H5 | VAL 2022→2024-03 | 58 | 56.9 | 0.078 | 1.2 | 4.51 | 5.57 |


## 2. D1 / D2 वेगळे

| trial | period | setup | trades | win_pct | expectancy_r | total_r |
|---|---|---|---|---|---|---|
| BASE | IS 2015→2021 | D1 | 15 | 66.7 | 0.291 | 4.37 |
| BASE | IS 2015→2021 | D2 | 11 | 36.4 | -0.46 | -5.06 |
| BASE | VAL 2022→2024-03 | D1 | 7 | 14.3 | -0.399 | -2.8 |
| BASE | VAL 2022→2024-03 | D2 | 4 | 50.0 | 0.019 | 0.08 |
| H1 | IS 2015→2021 | D1 | 15 | 66.7 | 0.291 | 4.37 |
| H1 | IS 2015→2021 | D2 | 1 | 0.0 | -1.085 | -1.09 |
| H1 | VAL 2022→2024-03 | D1 | 7 | 14.3 | -0.399 | -2.8 |
| H1 | VAL 2022→2024-03 | D2 | 0 |  |  | 0.0 |
| H3_020 | IS 2015→2021 | D1 | 12 | 66.7 | 0.316 | 3.79 |
| H3_020 | IS 2015→2021 | D2 | 5 | 40.0 | -0.564 | -2.82 |
| H3_020 | VAL 2022→2024-03 | D1 | 7 | 14.3 | -0.399 | -2.8 |
| H3_020 | VAL 2022→2024-03 | D2 | 1 | 0.0 | -0.033 | -0.03 |
| H3_025 | IS 2015→2021 | D1 | 11 | 72.7 | 0.38 | 4.18 |
| H3_025 | IS 2015→2021 | D2 | 3 | 66.7 | -0.208 | -0.62 |
| H3_025 | VAL 2022→2024-03 | D1 | 3 | 33.3 | -0.009 | -0.03 |
| H3_025 | VAL 2022→2024-03 | D2 | 1 | 0.0 | -0.033 | -0.03 |
| H4a_none | IS 2015→2021 | D1 | 12 | 66.7 | 0.368 | 4.42 |
| H4a_none | IS 2015→2021 | D2 | 11 | 36.4 | -0.46 | -5.06 |
| H4a_none | VAL 2022→2024-03 | D1 | 6 | 33.3 | -0.359 | -2.15 |
| H4a_none | VAL 2022→2024-03 | D2 | 4 | 50.0 | 0.019 | 0.08 |
| H4b_12bars | IS 2015→2021 | D1 | 12 | 58.3 | 0.382 | 4.58 |
| H4b_12bars | IS 2015→2021 | D2 | 11 | 36.4 | -0.46 | -5.06 |
| H4b_12bars | VAL 2022→2024-03 | D1 | 6 | 50.0 | -0.258 | -1.55 |
| H4b_12bars | VAL 2022→2024-03 | D2 | 4 | 50.0 | 0.019 | 0.08 |
| H4c_or_reentry | IS 2015→2021 | D1 | 13 | 53.8 | 0.299 | 3.89 |
| H4c_or_reentry | IS 2015→2021 | D2 | 11 | 36.4 | -0.46 | -5.06 |
| H4c_or_reentry | VAL 2022→2024-03 | D1 | 7 | 28.6 | -0.086 | -0.6 |
| H4c_or_reentry | VAL 2022→2024-03 | D2 | 4 | 50.0 | 0.019 | 0.08 |
| H5 | IS 2015→2021 | D1 | 9 | 55.6 | 0.314 | 2.83 |
| H5 | IS 2015→2021 | D2 | 0 |  |  | 0.0 |
| H5 | VAL 2022→2024-03 | D1 | 3 | 66.7 | 0.438 | 1.31 |
| H5 | VAL 2022→2024-03 | D2 | 0 |  |  | 0.0 |


## 3. H5 निवड (फक्त IS वरून, नियम आधीच ठरलेला: IS दैनिक-R Sharpe; BASE पेक्षा चांगला नसेल तर तो भाग BASE)

- H3 निवड: **H3_025** · H4 निवड: **H4c_or_reentry** · H5 knobs: `{"d2_allowed_biases": ["LONG_ONLY", "SHORT_ONLY"], "adr_min_frac": 0.25, "d1_exit_rule": "or_reentry"}`


## 4. Overfitting तपासणी (IS दैनिक R, सर्व trials)

- PBO (CSCV, S=16, 12870 splits, N=8 trials, T=1716 दिवस): **0.0002** (> 0.05 ⇒ निवड overfit मानावी)
- IS-सर्वोत्तम trial: **H5** · Deflated Sharpe: SR=-0.0121 (दैनिक), अपेक्षित कमाल SR0=0.0539, **DSR=0.0032** (≥ 0.95 हवा)


## 5. H2 — D2 score bucket / bias नुसार (BASE)

| प्रकार | period | score | bias | trades | win_pct | expectancy_r | avg_win_r | avg_loss_r | profit_factor | total_r | max_dd_r |
|---|---|---|---|---|---|---|---|---|---|---|---|
| घेतलेले | IS 2015→2021 | 60–70 | सर्व | 11 | 36.4 | -0.46 | 0.428 | -0.967 | 0.25 | -5.06 | 4.57 |
| घेतलेले | IS 2015→2021 | सर्व | LONG_ONLY | 1 | 0.0 | -1.085 |  | -1.085 | 0.0 | -1.09 | 0.0 |
| घेतलेले | IS 2015→2021 | सर्व | LONG_ONLY_WAIT_PULLBACK_END | 6 | 33.3 | -0.588 | 0.472 | -1.117 | 0.21 | -3.53 | 3.32 |
| घेतलेले | IS 2015→2021 | सर्व | SHORT_ONLY_WAIT_PULLBACK_END | 4 | 50.0 | -0.112 | 0.385 | -0.609 | 0.63 | -0.45 | 0.1 |
| घेतलेले | VAL 2022→2024-03 | 60–70 | सर्व | 4 | 50.0 | 0.019 | 0.586 | -0.549 | 1.07 | 0.08 | 1.06 |
| घेतलेले | VAL 2022→2024-03 | सर्व | SHORT_ONLY_WAIT_PULLBACK_END | 4 | 50.0 | 0.019 | 0.586 | -0.549 | 1.07 | 0.08 | 1.06 |
| gate-rejected (counterfactual) | IS 2015→2021 | सर्व | LONG_ONLY | 43 | 62.8 | 0.318 | 1.2 | -1.17 | 1.73 | 13.69 | 9.16 |
| gate-rejected (counterfactual) | IS 2015→2021 | सर्व | LONG_ONLY_WAIT_PULLBACK_END | 119 | 55.5 | 0.044 | 0.99 | -1.134 | 1.09 | 5.26 | 6.7 |
| gate-rejected (counterfactual) | IS 2015→2021 | सर्व | NO_TRADE | 206 | 50.0 | -0.063 | 0.949 | -1.075 | 0.88 | -12.97 | 36.44 |
| gate-rejected (counterfactual) | IS 2015→2021 | सर्व | RANGE_EDGES_ONLY | 67 | 35.8 | -0.323 | 1.098 | -1.116 | 0.55 | -21.61 | 22.8 |
| gate-rejected (counterfactual) | IS 2015→2021 | सर्व | SHORT_ONLY | 9 | 55.6 | 0.275 | 1.366 | -1.087 | 1.57 | 2.48 | 2.24 |
| gate-rejected (counterfactual) | IS 2015→2021 | सर्व | SHORT_ONLY_WAIT_PULLBACK_END | 36 | 38.9 | -0.356 | 0.803 | -1.093 | 0.47 | -12.81 | 12.04 |
| gate-rejected (counterfactual) | VAL 2022→2024-03 | सर्व | LONG_ONLY | 7 | 85.7 | 0.335 | 0.575 | -1.103 | 3.13 | 2.35 | 1.1 |
| gate-rejected (counterfactual) | VAL 2022→2024-03 | सर्व | LONG_ONLY_WAIT_PULLBACK_END | 31 | 38.7 | -0.226 | 1.125 | -1.08 | 0.66 | -7.01 | 7.57 |
| gate-rejected (counterfactual) | VAL 2022→2024-03 | सर्व | NO_TRADE | 54 | 48.1 | -0.191 | 0.751 | -1.066 | 0.65 | -10.32 | 13.61 |
| gate-rejected (counterfactual) | VAL 2022→2024-03 | सर्व | RANGE_EDGES_ONLY | 21 | 57.1 | -0.151 | 0.544 | -1.077 | 0.67 | -3.16 | 4.84 |
| gate-rejected (counterfactual) | VAL 2022→2024-03 | सर्व | SHORT_ONLY | 2 | 50.0 | -0.317 | 0.412 | -1.045 | 0.39 | -0.63 | 1.04 |
| gate-rejected (counterfactual) | VAL 2022→2024-03 | सर्व | SHORT_ONLY_WAIT_PULLBACK_END | 14 | 35.7 | -0.315 | 0.879 | -0.978 | 0.5 | -4.41 | 4.42 |


### LONG_ONLY bias मधले D2 candidates — status आणि मुख्य कारणं (BASE)

| period | bias | status | candidates | दिवस | दिशा | मुख्य कारणं |
|---|---|---|---|---|---|---|
| IS 2015→2021 | LONG_ONLY | REJECTED_GATE | 139 | 67 | SHORT | दिशा HTF bias शी जुळत नाही (139) |
| IS 2015→2021 | LONG_ONLY | REJECTED_RISK | 2 | 2 | LONG | Risk: SL_TOO_TIGHT (2) |
| IS 2015→2021 | LONG_ONLY | REJECTED_SCORE | 3 | 3 | LONG | Score 57 < 60 — trade नाही (log मध्ये नोंद) (3) |
| IS 2015→2021 | LONG_ONLY | REJECTED_VALIDATION | 2 | 2 | LONG | wick_rejection नाही (1) ; body_confirm नाही (1) |
| IS 2015→2021 | LONG_ONLY | TAKEN | 1 | 1 | LONG |  (1) |
| IS 2015→2021 | LONG_ONLY_WAIT_PULLBACK_END | DROPPED | 3 | 3 | LONG | Selector: POSITION_OPEN (2) ; Selector: SL_COOLDOWN (1) |
| IS 2015→2021 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_GATE | 377 | 159 | LONG,SHORT | दिशा HTF bias शी जुळत नाही (330) ; SL primary-HTF protected level पलीकडे (HTF structure धोक्यात) (24) ; Daily FRESH supply/A-B resistance जवळ (veto c) (16) |
| IS 2015→2021 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_RISK | 15 | 14 | LONG | Risk: SL_TOO_TIGHT (11) ; Risk: SL_TOO_WIDE (4) |
| IS 2015→2021 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_SCORE | 91 | 48 | LONG | Score 51 < 60 — trade नाही (log मध्ये नोंद) (14) ; Score 52 < 60 — trade नाही (log मध्ये नोंद) (11) ; Score 53 < 60 — trade नाही (log मध्ये नोंद) (10) |
| IS 2015→2021 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_VALIDATION | 43 | 34 | LONG | body_confirm नाही (25) ; wick_rejection नाही (18) |
| IS 2015→2021 | LONG_ONLY_WAIT_PULLBACK_END | TAKEN | 6 | 6 | LONG |  (6) |
| VAL 2022→2024-03 | LONG_ONLY | REJECTED_GATE | 31 | 16 | SHORT | दिशा HTF bias शी जुळत नाही (31) |
| VAL 2022→2024-03 | LONG_ONLY | REJECTED_SCORE | 3 | 2 | LONG | Score 57 < 60 — trade नाही (log मध्ये नोंद) (3) |
| VAL 2022→2024-03 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_GATE | 97 | 43 | LONG,SHORT | दिशा HTF bias शी जुळत नाही (72) ; SL primary-HTF protected level पलीकडे (HTF structure धोक्यात) (14) ; Daily RANGE: range edge खूप जवळ (10) |
| VAL 2022→2024-03 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_RISK | 4 | 3 | LONG | Risk: SL_TOO_TIGHT (2) ; Risk: SL_TOO_WIDE (2) |
| VAL 2022→2024-03 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_SCORE | 31 | 17 | LONG | Score 52 < 60 — trade नाही (log मध्ये नोंद) (6) ; Score 56 < 60 — trade नाही (log मध्ये नोंद) (5) ; Score 57 < 60 — trade नाही (log मध्ये नोंद) (4) |
| VAL 2022→2024-03 | LONG_ONLY_WAIT_PULLBACK_END | REJECTED_VALIDATION | 19 | 13 | LONG | body_confirm नाही (11) ; wick_rejection नाही (8) |


## 6. निष्कर्ष

(हाताने लिहिलेला; आकडे वरील तक्त्यांतून. पूर्ण trial log: `docs/reports/t1_trials.csv`, आकडेवारी: `docs/reports/t1_stats.json`.)

1. **एकाही trial ला IS मध्ये सकारात्मक edge नाही.** BASE (V1, D1–D10) IS expectancy −0.182R (390 trades); VAL +0.033R (148). सर्वोत्तम IS trial (H5) सुद्धा IS −0.036R.
   Deflated Sharpe 0.003 (≥ 0.95 हवा) ⇒ "H5 चांगला" हा दावा अनेक trials मधून निवडीच्या नशिबापलीकडे टिकत नाही.
2. **PBO 0.0002 कमी आहे** — म्हणजे trials चा क्रम (H3 कुटुंब इतरांपेक्षा कमी वाईट) IS च्या उप-भागांत स्थिर आहे. पण हा फक्त *सापेक्ष* क्रम; *निरपेक्ष* Sharpe ऋणच.
3. **H3 (SL किमान 0.25 × ADR — त्यापेक्षा जवळचा SL असलेले trades नाकारणे):** तोटा सर्वात जास्त कमी करतो (IS −71R → −6R) कारण trades 390 → 166.
   VAL मध्ये +0.053R (59 trades). हा "कमी पण कमी-वाईट trades" परिणाम आहे, नफ्याचा पुरावा नाही. → **REVIEW** (G2 ला बघण्यासारखा; डीफॉल्ट बदलला नाही).
4. **H1 (D2 फक्त LONG_ONLY/SHORT_ONLY):** D2 चे trades जवळजवळ शून्य (IS 11 → 1). D2 चा नमुना इतका लहान आहे की निष्कर्ष नाही. → **REVIEW**.
5. **H4 (D1 exit):** D1 चे IS trades फक्त 12–15; फरक आवाजाच्या आत. OR-reentry ने VAL मधला D1 तोटा कमी केला (−2.8R → −0.6R, 7 trades) — नमुना लहान. → **REVIEW**.
6. **H2:** घेतलेले सर्व D2 score 60–70 bucket मध्ये. LONG_ONLY bias मध्ये D2 candidates मुख्यतः "दिशा HTF bias शी जुळत नाही" (gap-up fade = SHORT) म्हणून नाकारले.
   त्यांचा counterfactual (gate ने नाकारलेले, तरी घेतले असते तर): IS +0.318R (43), VAL +0.335R (7) — **हे tuning नव्हे, फक्त नोंद**; G2 ला वेगळं गृहीतक म्हणून मांडायचं.
7. Sealed holdout वापरलेला नाही. Holdout cache script VPS वर चालवायची बाकी (फक्त संख्या).
