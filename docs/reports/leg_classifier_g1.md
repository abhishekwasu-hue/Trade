# T2.1–T2.3 — Leg classifier: IS calibration आणि G1 नमुने (NIFTY 15M)

डेटा: `data/nifty50_1min.parquet` → 15M (56816 bars). IS = 2015→2021 (calibration फक्त इथे), VAL = 2022→2024-03 (फक्त दाखवणे). Sealed holdout वापरलेला नाही.
परिणाम-क्षितिज H = 8 bars (15M ⇒ 2 तास). fwd_mr = leg माहीत झाल्यापासून (confirm bar) H bars नंतरचा close-बदल, leg दिशेने, ÷ median_range.

## 1. आधीच ठरलेले grids (प्रत्येकी 81) आणि निवड

- Impulse grid {'e_hi': (0.35, 0.45, 0.55), 'o_lo': (0.45, 0.55, 0.65), 'd_k': (1.0, 1.5, 2.0), 'd_body': (0.5, 0.6, 0.7)} — उद्दिष्ट: STRONG वि. WEAK fwd_mr फरकाचा Welch t (STRONG वाटा 10%–60%).
  - निवड: **{'e_hi': 0.35, 'o_lo': 0.65, 'd_k': 1.5, 'd_body': 0.5}** · पात्र trials: 54/81 · t ची रेंज -1.13 → 1.21
- Pullback grid {'r_ok': (0.4, 0.5, 0.6), 'r_warn': (0.7, 0.85, 1.0), 's_ratio': (0.6, 0.8, 1.0), 'fvg_min': (0.1, 0.25, 0.5)} — उद्दिष्ट: HEALTHY वि. DANGEROUS resume दराचा z (दोन्ही वाटे ≥ 10%).
  - निवड: **एकही trial अट पूर्ण करत नाही ⇒ डीफॉल्ट ठेवले** · HEALTHY वाटा रेंज 0.008 → 0.060, DANGEROUS 0.836 → 0.963
- अंतिम LegConfig: `{'n_median': 20, 'fractal_r': 2, 'k_internal': 1.5, 'k_swing': 3.0, 'e_hi': 0.35, 'o_lo': 0.65, 'd_k': 1.5, 'd_body': 0.5, 'fvg_min': 0.1, 'r_ok': 0.5, 'r_warn': 0.75, 's_ratio': 0.8, 'healthy_max_dir': 0.8, 'e_range': 0.15, 'o_range': 0.55, 'alt_range': 0.5}`

## 2. IS वि. VAL (निवडलेल्या cfg ने, एकाच सलग चालवणीत)

| मापक | IS | VAL |
|---|---|---|
| period | IS 2015→2021 | VAL 2022→2024-03 |
| legs | 3109 | 1006 |
| n_impulse | 1054 | 343 |
| strong_share | 0.479 | 0.507 |
| fwd_strong | 0.206 | -0.156 |
| fwd_weak | -0.053 | -0.045 |
| t | 1.214 | -0.333 |
| n_pullback | 1558 | 520 |
| healthy_share | 0.012 | 0.012 |
| danger_share | 0.958 | 0.963 |
| resume_healthy | 0.895 | 1.000 |
| resume_danger | 0.663 | 0.644 |
| z | 2.127 | 1.815 |
| share_DANGEROUS_PULLBACK | 0.480 | 0.498 |
| share_WEAK_IMPULSE | 0.177 | 0.168 |
| share_STRONG_IMPULSE | 0.162 | 0.173 |
| share_REVERSAL | 0.156 | 0.137 |
| share_MIXED_PULLBACK | 0.015 | 0.013 |
| share_HEALTHY_PULLBACK | 0.006 | 0.006 |
| share_RANGE | 0.004 | 0.005 |


## 3. लेबलनिहाय पुढचे परिणाम

| period | label | n | fwd_mr_mean | fwd_pos_pct | resume_pct |
|---|---|---|---|---|---|
| IS | DANGEROUS_PULLBACK | 1493 | -0.230 | 47.000 | 66.300 |
| IS | HEALTHY_PULLBACK | 19 | -1.476 | 26.300 | 89.500 |
| IS | MIXED_PULLBACK | 46 | 0.391 | 45.700 | 84.800 |
| IS | RANGE | 12 | 1.055 | 66.700 | 50.000 |
| IS | REVERSAL | 485 | -0.001 | 50.900 |  |
| IS | STRONG_IMPULSE | 505 | 0.206 | 53.900 |  |
| IS | WEAK_IMPULSE | 549 | -0.053 | 48.300 |  |
| VAL | DANGEROUS_PULLBACK | 501 | -0.245 | 47.500 | 64.400 |
| VAL | HEALTHY_PULLBACK | 6 | -0.121 | 50.000 | 100.000 |
| VAL | MIXED_PULLBACK | 13 | -1.535 | 23.100 | 92.300 |
| VAL | RANGE | 5 | -1.424 | 20.000 | 100.000 |
| VAL | REVERSAL | 138 | 0.512 | 55.100 |  |
| VAL | STRONG_IMPULSE | 174 | -0.156 | 50.000 |  |
| VAL | WEAK_IMPULSE | 169 | -0.045 | 47.900 |  |


## 4. G1 — 10 नमुना दिवस (IS, स्थिर seed; प्रत्येक लेबल किमान एकदा)

| दिवस | legs (3 दिवसांत) | लेबल्स |
|---|---|---|
| 2015-03-26 (Thu) | 4 | DANGEROUS_PULLBACK 2, STRONG_IMPULSE 1, REVERSAL 1 |
| 2015-11-16 (Mon) | 4 | DANGEROUS_PULLBACK 2, STRONG_IMPULSE 1, WEAK_IMPULSE 1 |
| 2015-12-28 (Mon) | 2 | DANGEROUS_PULLBACK 1, STRONG_IMPULSE 1 |
| 2016-01-13 (Wed) | 6 | DANGEROUS_PULLBACK 3, STRONG_IMPULSE 2, WEAK_IMPULSE 1 |
| 2018-05-15 (Tue) | 6 | DANGEROUS_PULLBACK 2, STRONG_IMPULSE 2, MIXED_PULLBACK 1, WEAK_IMPULSE 1 |
| 2018-06-04 (Mon) | 8 | MIXED_PULLBACK 2, DANGEROUS_PULLBACK 2, REVERSAL 2, STRONG_IMPULSE 1, WEAK_IMPULSE 1 |
| 2018-06-27 (Wed) | 5 | DANGEROUS_PULLBACK 3, STRONG_IMPULSE 1, REVERSAL 1 |
| 2019-01-04 (Fri) | 8 | DANGEROUS_PULLBACK 4, STRONG_IMPULSE 2, WEAK_IMPULSE 1, REVERSAL 1 |
| 2020-03-23 (Mon) | 7 | DANGEROUS_PULLBACK 4, STRONG_IMPULSE 2, HEALTHY_PULLBACK 1 |
| 2020-06-11 (Thu) | 2 | STRONG_IMPULSE 1, RANGE 1 |


चार्ट: `--out` folder मधील `legs_YYYY-MM-DD.html` (interactive; गडद = impulse, फिकट = pullback, राखाडी = range, जांभळा = उलटफेर; hover वर features + कारण).
प्रत्येक दिवसाचा (मागच्या 2 दिवसांच्या संदर्भासह) screenshot खाली — वरच्या कोपऱ्यातली पेटी = crosshair खालच्या leg ची माहिती.
Dashboard वर: चार्ट खाली **"Legs (impulse / pullback लेबल)"** checkbox (डीफॉल्ट बंद).

![2015-03-26](g1_samples/legs_2015-03-26.png)
![2015-11-16](g1_samples/legs_2015-11-16.png)
![2015-12-28](g1_samples/legs_2015-12-28.png)
![2016-01-13](g1_samples/legs_2016-01-13.png)
![2018-05-15](g1_samples/legs_2018-05-15.png)
![2018-06-04](g1_samples/legs_2018-06-04.png)
![2018-06-27](g1_samples/legs_2018-06-27.png)
![2019-01-04](g1_samples/legs_2019-01-04.png)
![2020-03-23](g1_samples/legs_2020-03-23.png)
![2020-06-11](g1_samples/legs_2020-06-11.png)

## 5. निष्कर्ष (हाताने लिहिलेला)

1. **Swings → legs रचना चार्टवर तर्कसंगत दिसते** (वरचे 10 नमुने): ZigZag (3 × median_range) मुख्य swings पकडतो. legs फक्त confirm झाल्यावर (`known_at`) लेबल होतात.
2. **STRONG वि. WEAK impulse:** IS वर सर्वोत्तम grid trial चा फरक t = 1.21 (महत्त्वाचा नाही). VAL मध्ये उलट (STRONG −0.156 वि. WEAK −0.045 × range).
   ⇒ 15M / 2-तास क्षितिजावर "जोरदार impulse नंतर तीच दिशा चालू राहते" याचा पुरावा **नाही**.
3. **Pullback लेबल्स:** spec चे "धोकादायक" नियम OR ने जोडलेले आहेत (खोल > r_warn, किंवा pullback-दिशेचा displacement/FVG, किंवा speed ≥ impulse speed, किंवा CHoCH + displacement).
   NIFTY 15M वर: speed ≥ impulse 57%, displacement/FVG 62%, depth > 0.75 31% pullbacks मध्ये. म्हणून ~96% pullbacks DANGEROUS आणि HEALTHY फक्त ~1%.
   ठरवलेल्या pullback grid मधला एकही trial "दोन्ही ≥ 10%" अट पूर्ण करत नाही ⇒ डीफॉल्ट ठेवले (post-hoc सैल केलं नाही).
4. HEALTHY दिसतो तेव्हा trend resume 89.5% (IS, n = 19) वि. DANGEROUS 66.3% (n = 1493). दिशा आशादायक, पण नमुना फार लहान.
5. **G1 साठी प्रस्ताव (तुमचा निर्णय):**
   - (a) व्याख्या जशा आहेत तशा ठेवा. Approach-rule मध्ये फक्त STRONG_IMPULSE ⇒ BREAK candidate वापरा.
   - (b) नवीन, आधीच ठरवलेलं गृहीतक: "धोकादायक = 4 पैकी ≥ 2 अटी". IS वर नवा grid, VAL वेगळा.
   - हे bot मध्ये नाही; overlay डीफॉल्ट बंद.
