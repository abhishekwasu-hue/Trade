# T3 — Leg आणि Level validation (Osler पद्धत, NIFTY)

डेटा: NIFTY offline 1M → 15M (56816 bars), IS 2015→2021, VAL 2022→2024-03. Sealed holdout वापरलेला नाही. BANKNIFTY/MCX offline डेटा उपलब्ध नाही ⇒ फक्त NIFTY.
Bounce = पहिल्या स्पर्शानंतर 8 bars (15M) मध्ये close दूरच्या कडेपलीकडे जाण्याआधी zone पासून ≥ 1.0 × median_range close-अंतर. zones दिवसाच्या open पासून ±1.5%.
Random: प्रत्येक खऱ्या zone मागे 3 यादृच्छिक zones (तीच रुंदी, अंतर त्या engine च्या IS अंतर-वितरणातून, बाजू यादृच्छिक). OE_T24 = OE zones ज्यांची T2.4 ताकद ≥ IS median (56.7).

## निर्णय सारांश (KEEP / REVIEW / REJECT)

| घटक | IS edge | IS z / p | VAL edge | निर्णय |
|---|---|---|---|---|
| Level engine DYN (वि. random) | 0.8 pp | 0.49 | 1.0 pp | REVIEW |
| Level engine OE (वि. random) | -0.5 pp | -1.35 | 0.5 pp | REVIEW |
| Level engine OE_T24 (वि. random) | -0.3 pp | -0.59 | 1.2 pp | REVIEW |
| Level engine SRV3 (वि. random) | -0.1 pp | -0.16 | 2.7 pp | REVIEW |
| Engines मधून IS-सर्वोत्तम निवड | सर्वोत्तम DYN | PBO=0.1816 |  | REJECT (PBO > 0.05) |
| Leg: STRONG वि. WEAK impulse (fwd, × range) | 0.342 | p=0.055 | -0.01 | REJECT (PBO > 0.05) |
| Leg: HEALTHY वि. DANGEROUS pullback (resume दर) | 0.251 | p=0.007 |  | REVIEW (डेटा अपुरा) |


## 1. Level अचूकता — खरे वि. यादृच्छिक

| engine | period | real_zones | real_touched | real_bounce_pct | random_touched | random_bounce_pct | edge_pp | z | real_break_pct | random_break_pct | real_width_pct_med | random_width_pct_med | real_react_mr | random_react_mr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DYN | IS | 3462 | 1307 | 41.4 | 3924 | 40.6 | 0.8 | 0.49 | 43.8 | 45.0 | 0.2 | 0.2 | -0.522 | -0.502 |
| DYN | VAL | 1117 | 420 | 44.8 | 1168 | 43.8 | 1.0 | 0.36 | 43.1 | 43.2 | 0.2 | 0.2 | -0.376 | -0.179 |
| OE | IS | 68705 | 26578 | 37.9 | 68137 | 38.3 | -0.5 | -1.35 | 44.3 | 43.6 | 0.204 | 0.212 | -0.416 | -0.409 |
| OE | VAL | 24996 | 9178 | 40.5 | 23175 | 40.0 | 0.5 | 0.82 | 42.8 | 43.4 | 0.205 | 0.21 | -0.197 | -0.19 |
| OE_T24 | IS | 34565 | 13821 | 40.2 | 35288 | 40.5 | -0.3 | -0.59 | 39.4 | 39.0 | 0.236 | 0.237 | -0.455 | -0.429 |
| OE_T24 | VAL | 12483 | 4834 | 43.5 | 12127 | 42.3 | 1.2 | 1.4 | 36.0 | 37.8 | 0.267 | 0.259 | -0.253 | -0.231 |
| SRV3 | IS | 8819 | 3508 | 29.5 | 9856 | 29.6 | -0.1 | -0.16 | 66.4 | 66.5 | 0.023 | 0.003 | -0.478 | -0.371 |
| SRV3 | VAL | 2987 | 1152 | 31.9 | 3172 | 29.3 | 2.7 | 1.71 | 65.4 | 67.7 | 0.032 | 0.001 | -0.148 | -0.127 |


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



| engine | period | touch_bucket | n | bounce_pct |
|---|---|---|---|---|
| DYN | IS | 0 | 2 | 0.0 |
| DYN | IS | 1 | 16 | 43.8 |
| DYN | IS | 2 | 45 | 28.9 |
| DYN | IS | 3–4 | 152 | 37.5 |
| DYN | IS | 5+ | 1092 | 42.5 |
| DYN | VAL | 0 | 1 | 100.0 |
| DYN | VAL | 1 | 4 | 50.0 |
| DYN | VAL | 2 | 18 | 38.9 |
| DYN | VAL | 3–4 | 51 | 47.1 |
| DYN | VAL | 5+ | 346 | 44.5 |
| OE | IS | 0 | 5956 | 27.2 |
| OE | IS | 1 | 1164 | 40.4 |
| OE | IS | 2 | 1130 | 42.8 |
| OE | IS | 3–4 | 2057 | 39.9 |
| OE | IS | 5+ | 16271 | 41.0 |
| OE | VAL | 0 | 2188 | 27.2 |
| OE | VAL | 1 | 328 | 41.8 |
| OE | VAL | 2 | 319 | 47.3 |
| OE | VAL | 3–4 | 597 | 45.1 |
| OE | VAL | 5+ | 5746 | 44.6 |
| SRV3 | IS | 0 | 268 | 25.0 |
| SRV3 | IS | 1 | 493 | 30.2 |
| SRV3 | IS | 2 | 309 | 34.3 |
| SRV3 | IS | 3–4 | 479 | 27.6 |
| SRV3 | IS | 5+ | 1959 | 29.7 |
| SRV3 | VAL | 0 | 91 | 26.4 |
| SRV3 | VAL | 1 | 164 | 34.1 |
| SRV3 | VAL | 2 | 99 | 29.3 |
| SRV3 | VAL | 3–4 | 183 | 37.2 |
| SRV3 | VAL | 5+ | 615 | 31.1 |


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


## 5. निष्कर्ष

(हाताने लिहिलेला; independent review नंतर दुरुस्त.)

1. **एकाही level engine ला यादृच्छिक (random) zones पेक्षा अर्थपूर्ण bounce-edge नाही.**
   - IS edge: DYN +0.8pp, OE −0.5pp, OE+T2.4 −0.3pp, SRV3 −0.1pp. सर्व |z| < 1.4.
   - VAL edge: +0.5 ते +2.7pp; |z| < 1.8.
   - प्रत्येक engine ला निर्णय **REVIEW** (edge महत्त्वाचा नाही, पण नाकारण्याइतका ऋणही नाही).
   - Engines मधून IS वर "सर्वोत्तम" निवडणं overfit आहे: PBO 0.18 > 0.05 ⇒ ती *निवड* REJECT. चारही engines चा IS दैनिक react-R Sharpe ऋण.
   - संशोधनात अपेक्षित ~4–5pp edge आपल्या NIFTY 15M intraday व्याख्येवर दिसत नाही.
   - z rows स्वतंत्र मानतो (एकाच दिवसाचे zones एकत्र येतात) ⇒ खरा z आणखी लहान.
2. **SR V3 चा break दर ~66%** (DYN/OE ~43%). SR V3 zones फार अरुंद आहेत (स्पर्श झालेल्यांची median रुंदी 0.02–0.03%; DYN/OE ~0.2%).
   त्याच engine च्या random zones चा break दरही 66.5% (IS) / 67.7% (VAL) ⇒ "जास्त तुटणं" हे अरुंद zones चं लक्षण आहे, level च्या खरेपणाचं नाही.
3. **T2.4 ताकद गुणांनी OE zones सुधारत नाहीत.** OE_T24: IS −0.3pp, VAL +1.2pp (z 1.4).
   Logistic (IS, सर्व engines एकत्र): touches चं वजन ≈ 0 (−0.016); role reversal +0.12; रुंदी +0.21 (engines च्या मिश्रणामुळे गोंधळलेलं असू शकतं).
4. **"Retested zone" निरीक्षण (engine-निहाय, random baseline शिवाय):**
   - OE मध्ये 0 touches (उगमानंतर कधीच retest न झालेले) zones चा bounce 27.2% (IS आणि VAL दोन्ही), तर 1+ touches चा 40–47%.
   - SRV3 मध्ये फरक लहान (25–26% वि. 28–37%). DYN मध्ये 0-touch नमुना जवळजवळ नाही (उगम-वेळ माहीत नसल्याने 400-bar खिडकी).
   - ⇒ "ताजा zone जास्त मजबूत" हे गृहीतक OE मध्ये **उलट** दिसतं. Random zones शी touches-निहाय तुलना पुढच्या चाचणीत; हा निष्कर्ष नाही.
5. **Option seller:** मजबूत zone च्या पलीकडची strike त्याच अंतरावरच्या यादृच्छिक-दिवस strike इतकीच तुटते.
   - OE IS: touch 79.7% वि. 80.4%, close 41.9% वि. 41.5%.
   - SRV3 IS: 74.5% वि. 74.9%.
   - ⇒ zone मुळे सुरक्षा मिळत नाही. Credit-spread strike filter (T4) ला आधार नाही.
6. **Leg classifier:**
   - STRONG वि. WEAK: IS +0.34 × range (p = 0.055), VAL −0.01, impulse-grid PBO 0.35 ⇒ REJECT.
   - HEALTHY वि. DANGEROUS (trend resume): IS 90.9% वि. 65.8% (p = 0.007, n = 22); VAL 5/5 वि. 65.1% ⇒ REVIEW. नमुना लहान; VAL permutation शक्य नाही.
7. **मर्यादा:**
   - फक्त NIFTY.
   - एकच आधीच ठरलेली bounce व्याख्या.
   - OE zones परस्परावलंबी. OE_T24 हा OE चा उपसंच (PBO trials सहसंबंधित).
   - DYN ला उगम-वेळ नाही ⇒ departure/base = 0 मानले.
   - शेवटच्या IS दिवसांचे outcome-window काही bars VAL मध्ये जातात (नगण्य).
8. **G2 शिफारस:** कोणताही नवा gate/engine चालू करू नये. T4 ("one level truth", approach gate, credit-spread filter) ला सध्याच्या पुराव्याने आधार नाही.
   पुढे दोन गृहीतकं — HEALTHY-pullback आणि "retested zone > fresh zone" (random baseline सह) — आधीच ठरवलेल्या चाचणीने मोठ्या नमुन्यावर तपासावीत.
