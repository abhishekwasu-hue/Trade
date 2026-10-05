# T3 — Leg आणि Level validation (Osler पद्धत, NIFTY)

डेटा: NIFTY offline 1M → 15M (56816 bars), IS 2015→2021, VAL 2022→2024-03. Sealed holdout वापरलेला नाही. BANKNIFTY/MCX offline डेटा उपलब्ध नाही ⇒ फक्त NIFTY.
Bounce = पहिल्या स्पर्शानंतर 8 bars (15M) मध्ये close दूरच्या कडेपलीकडे जाण्याआधी zone पासून ≥ 1.0 × median_range close-अंतर. zones दिवसाच्या open पासून ±1.5%.
Random: प्रत्येक खऱ्या zone मागे 3 यादृच्छिक zones (तीच रुंदी, अंतर त्या engine च्या IS अंतर-वितरणातून, बाजू यादृच्छिक). OE_T24 = OE zones ज्यांची T2.4 ताकद ≥ IS median (56.7).

## निर्णय सारांश (KEEP / REVIEW / REJECT)

| घटक | IS edge (pp) | IS z | VAL edge (pp) | निर्णय |
|---|---|---|---|---|
| Level engine DYN | 0.8 | 0.49 | 1.0 | REJECT (PBO > 0.05) |
| Level engine OE | -0.5 | -1.35 | 0.5 | REJECT (PBO > 0.05) |
| Level engine OE_T24 | -0.3 | -0.59 | 1.2 | REJECT (PBO > 0.05) |
| Level engine SRV3 | -0.1 | -0.16 | 2.7 | REJECT (PBO > 0.05) |
| Leg: STRONG वि. WEAK impulse | 0.342 | p=0.055 | -0.01 | REJECT (PBO > 0.05) |
| Leg: HEALTHY वि. DANGEROUS pullback | 0.251 | p=0.007 |  | REVIEW (डेटा अपुरा) |


## 1. Level अचूकता — खरे वि. यादृच्छिक

| engine | period | real_zones | real_touched | real_bounce_pct | random_touched | random_bounce_pct | edge_pp | z | real_break_pct | real_react_mr | random_react_mr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DYN | IS | 3462 | 1307 | 41.4 | 3924 | 40.6 | 0.8 | 0.49 | 43.8 | -0.522 | -0.502 |
| DYN | VAL | 1117 | 420 | 44.8 | 1168 | 43.8 | 1.0 | 0.36 | 43.1 | -0.376 | -0.179 |
| OE | IS | 68705 | 26578 | 37.9 | 68137 | 38.3 | -0.5 | -1.35 | 44.3 | -0.416 | -0.409 |
| OE | VAL | 24996 | 9178 | 40.5 | 23175 | 40.0 | 0.5 | 0.82 | 42.8 | -0.197 | -0.19 |
| OE_T24 | IS | 34565 | 13821 | 40.2 | 35288 | 40.5 | -0.3 | -0.59 | 39.4 | -0.455 | -0.429 |
| OE_T24 | VAL | 12483 | 4834 | 43.5 | 12127 | 42.3 | 1.2 | 1.4 | 36.0 | -0.253 | -0.231 |
| SRV3 | IS | 8819 | 3508 | 29.5 | 9856 | 29.6 | -0.1 | -0.16 | 66.4 | -0.478 | -0.371 |
| SRV3 | VAL | 2987 | 1152 | 31.9 | 3172 | 29.3 | 2.7 | 1.71 | 65.4 | -0.148 | -0.127 |


### touches चं चिन्ह (IS logistic, standardised) आणि touches-bucket नुसार bounce

| feature | coef_IS(standardised) |
|---|---|
| f_touches | -0.016 |
| f_departure_mr | 0.015 |
| f_base_bars | -0.006 |
| f_recency | -0.048 |
| f_round_dist_mr | 0.032 |
| f_role_reversal | 0.118 |
| f_width_mr | 0.207 |



| period | touch_bucket | n | bounce_pct |
|---|---|---|---|
| IS | 0 | 6226.0 | 27.1 |
| IS | 1 | 1673.0 | 37.4 |
| IS | 2 | 1484.0 | 40.6 |
| IS | 3–4 | 2688.0 | 37.6 |
| IS | 5+ | 19322.0 | 39.9 |
| VAL | 0 | 2280.0 | 27.2 |
| VAL | 1 | 496.0 | 39.3 |
| VAL | 2 | 436.0 | 42.9 |
| VAL | 3–4 | 831.0 | 43.4 |
| VAL | 5+ | 6707.0 | 43.4 |


## 2. Leg classifier चाचण्या

| period | n_strong | fwd_strong | n_weak | fwd_weak | fwd_random_momentum | strong_minus_weak | p_perm | n_healthy | resume_healthy | n_danger | resume_danger | healthy_minus_danger | p_perm_pullback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IS | 519 | 0.194 | 529 | -0.148 | 0.18 | 0.342 | 0.055 | 22 | 0.909 | 1501 | 0.658 | 0.251 | 0.007 |
| VAL | 180 | -0.1 | 166 | -0.09 | 0.088 | -0.01 | 0.5297 | 5 | 1.0 | 496 | 0.651 |  |  |


## 3. PBO / Deflated Sharpe

- Leg impulse grid (81 trials, IS दैनिक signal-R): PBO = **0.3514**, IS-सर्वोत्तम {"e_hi": 0.35, "o_lo": 0.65, "d_k": 1.5, "d_body": 0.5}, DSR = 0.4648
- Level engines (trials = ['DYN', 'OE', 'OE_T24', 'SRV3'], IS दैनिक react-R): PBO = **0.1816**, सर्वोत्तम DYN, Sharpe {'DYN': -0.1248, 'OE': -0.158, 'OE_T24': -0.1477, 'SRV3': -0.1654}, DSR = 0.0

## 4. Option-seller चाचणी (5 सत्र hold; ZONE = मजबूत zone ची दूरची कड, RANDOM = त्याच % अंतरावर यादृच्छिक दिवस)

| engine | period | kind | n | touch_breach_pct | close_breach_pct | avg_dist_pct |
|---|---|---|---|---|---|---|
| OE | IS | RANDOM | 15325 | 80.4 | 41.5 | 0.38 |
| OE | IS | ZONE | 3065 | 79.7 | 41.9 | 0.38 |
| OE | VAL | RANDOM | 5210 | 80.4 | 40.0 | 0.38 |
| OE | VAL | ZONE | 1042 | 83.5 | 42.1 | 0.38 |
| SRV3 | IS | RANDOM | 11835 | 74.9 | 39.1 | 0.53 |
| SRV3 | IS | ZONE | 2367 | 74.5 | 38.4 | 0.53 |
| SRV3 | VAL | RANDOM | 4055 | 72.7 | 37.7 | 0.54 |
| SRV3 | VAL | ZONE | 811 | 74.8 | 40.0 | 0.54 |


## 5. निष्कर्ष (हाताने लिहिलेला)

1. **एकाही level engine ला यादृच्छिक (random) zones पेक्षा अर्थपूर्ण bounce-edge नाही.**
   - IS edge: DYN +0.8pp, OE −0.5pp, OE+T2.4 −0.3pp, SRV3 −0.1pp. सर्व |z| < 1.4.
   - VAL edge: +0.5 ते +2.7pp; सर्व |z| < 1.8.
   - संशोधनात अपेक्षित ~4–5pp edge आपल्या NIFTY 15M intraday व्याख्येवर दिसत नाही.
   - Engines मधून IS वर "सर्वोत्तम" निवडणं overfit आहे: PBO 0.18 > 0.05, DSR 0.0. चारही engines चा IS दैनिक react-R Sharpe ऋण.
2. **SR V3 चा break दर 66% (इतरांचा ~43%)** कारण SR V3 zones फार अरुंद आहेत (median रुंदी ≈ 0.025% ≈ 5 pts; DYN/OE ~0.2%).
   तीच रुंदी असलेल्या random zones चा break दरही ~67% ⇒ फरक zone-रुंदीमुळे आहे, level च्या "खरेपणामुळे" नाही.
3. **T2.4 ताकद गुणांनी OE zones सुधारत नाहीत** (OE_T24: IS −0.3pp, VAL +1.2pp, z 1.4).
   - Logistic (IS): touches चं वजन ≈ 0 (−0.016).
   - Role reversal (+0.12) आणि zone रुंदी (+0.21) सकारात्मक.
   - Bucket निरीक्षण: 0 touches (कधीच retest न झालेले) zones चा bounce 27%, तर 1+ touches चा 37–43% — IS आणि VAL दोन्हींत. म्हणजे "ताजा zone जास्त मजबूत" हे गृहीतक इथे **उलट** दिसतं.
     ही random baseline शिवायची तुलना आहे — पुढच्या चाचणीचं गृहीतक, निष्कर्ष नाही.
4. **Option seller:** मजबूत zone च्या पलीकडची strike त्याच अंतरावरच्या यादृच्छिक-दिवस strike इतकीच तुटते.
   - OE IS: touch 79.7% वि. 80.4%, close 41.9% वि. 41.5%.
   - SRV3 IS: 74.5% वि. 74.9%. VAL मध्ये zone strikes किंचित *जास्त* तुटल्या.
   - ⇒ zone मुळे सुरक्षा मिळत नाही. Credit-spread strike filter (T4) ला आधार नाही.
5. **Leg classifier:**
   - STRONG वि. WEAK: IS +0.34 × range (p = 0.055), VAL −0.01, impulse-grid PBO 0.35 ⇒ REJECT.
   - HEALTHY वि. DANGEROUS (trend resume): IS 90.9% वि. 65.8% (p = 0.007, n = 22); VAL 5/5 वि. 65.1% ⇒ REVIEW. दिशा टिकते, पण नमुना फार लहान.
6. **मर्यादा:**
   - फक्त NIFTY; BANKNIFTY/MCX offline डेटा नाही.
   - Bounce व्याख्या एकच, आधीच ठरलेली (8 bars, 1 × median range, ±1.5%); इतर व्याख्यांवर निकाल बदलू शकतात.
   - OE zones दर दिवशी अनेक ⇒ नमुना मोठा पण परस्परावलंबी.
   - Engine-PBO सर्व engines ना एकत्र लागू केला (spec-literal); तो "engines मधली निवड" overfit आहे हे सांगतो.
7. **G2 शिफारस:** कोणताही नवा gate/engine चालू करू नये. T4 ("one level truth", approach gate, credit-spread filter) ला सध्याच्या पुराव्याने आधार नाही.
   पुढे फक्त दोन गृहीतकं — HEALTHY-pullback आणि "retested zone > fresh zone" — आधीच ठरवलेल्या चाचणीने मोठ्या नमुन्यावर (5M, BANKNIFTY — VPS वर, 2024-03 पूर्वीचा डेटा) तपासावीत.
