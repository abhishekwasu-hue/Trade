# G2 नंतरच्या चाचण्या — positional strikes, pullbacks, retested zones (NIFTY, report-only)

डेटा: NIFTY offline 1M (2015 → 2024-03). IS 2015–2021, VAL 2022 → 2024-03. Sealed holdout बंद. कोणताही gate चालू नाही.

## (a) Positional short strike — 5 सत्र hold (Daily/Weekly levels वि. यादृच्छिक दिवस, तेच अंतर)

Strike = किंमतीपासून 0.5–4.0% मधल्या सर्वात जवळच्या level ची दूरची कड (put: support चा low, call: resistance चा high). touch = 5 सत्रांत कधीही पलीकडे; close = 5व्या सत्राचा close पलीकडे. RANDOM = त्याच period चे 5 यादृच्छिक दिवस, तेच % अंतर, तीच बाजू. z = cluster-bootstrap (कॅलेंडर महिना, 1000 पुनरावृत्ती) — लगतच्या दिवसांचे hold-windows एकमेकांवर येतात म्हणून साधा two-proportion z फुगतो. Hold-window IS/VAL सीमा ओलांडत नाही. OE 1d मध्ये BROKEN zones वगळले. levels काढता न आलेले दिवस: नाहीत.

| engine | period | अंतर | n_level | touch_level% | touch_random% | z_touch | close_level% | close_random% | z_close |
|---|---|---|---|---|---|---|---|---|---|
| DYN_D | IS | 0.5–1.0% | 269 | 61.3 | 64.3 | -0.83 | 31.6 | 35.9 | -1.31 |
| DYN_D | IS | 1.0–2.0% | 569 | 40.9 | 38.7 | 0.76 | 21.3 | 20.8 | 0.2 |
| DYN_D | IS | 2.0–4.0% | 886 | 15.5 | 15.5 | 0.0 | 9.0 | 7.7 | 1.04 |
| DYN_D | VAL | 0.5–1.0% | 93 | 48.4 | 59.4 | -1.68 | 30.1 | 34.8 | -1.13 |
| DYN_D | VAL | 1.0–2.0% | 230 | 40.0 | 35.4 | 0.84 | 25.2 | 18.9 | 1.87 |
| DYN_D | VAL | 2.0–4.0% | 351 | 12.0 | 11.7 | 0.13 | 6.6 | 5.2 | 0.81 |
| OE_1D | IS | 0.5–1.0% | 2288 | 66.9 | 66.5 | 0.41 | 36.5 | 35.0 | 1.61 |
| OE_1D | IS | 1.0–2.0% | 633 | 43.6 | 45.5 | -0.83 | 22.9 | 27.0 | -2.29 |
| OE_1D | IS | 2.0–4.0% | 79 | 13.9 | 15.7 | -0.43 | 7.6 | 8.4 | -0.23 |
| OE_1D | VAL | 0.5–1.0% | 922 | 64.9 | 63.9 | 0.83 | 35.0 | 34.8 | 0.19 |
| OE_1D | VAL | 1.0–2.0% | 89 | 49.4 | 47.4 | 0.32 | 31.5 | 28.5 | 0.51 |
| OE_1D | VAL | 2.0–4.0% | 20 | 20.0 | 18.0 | 0.13 | 5.0 | 10.0 | -0.64 |
| SRV3_DW | IS | 0.5–1.0% | 1178 | 62.0 | 62.4 | -0.42 | 34.8 | 34.7 | 0.11 |
| SRV3_DW | IS | 1.0–2.0% | 1521 | 44.2 | 41.9 | 1.79 | 24.0 | 23.0 | 0.96 |
| SRV3_DW | IS | 2.0–4.0% | 312 | 23.4 | 20.7 | 1.02 | 13.8 | 11.5 | 1.35 |
| SRV3_DW | VAL | 0.5–1.0% | 374 | 62.0 | 62.0 | 0.02 | 33.4 | 34.7 | -0.68 |
| SRV3_DW | VAL | 1.0–2.0% | 543 | 39.6 | 39.4 | 0.08 | 24.5 | 22.5 | 1.26 |
| SRV3_DW | VAL | 2.0–4.0% | 116 | 20.7 | 19.5 | 0.33 | 8.6 | 10.7 | -0.62 |


## (b) HEALTHY वि. DANGEROUS pullback — trend resume (15M आणि 1H)

LegConfig = T2.3 चं IS calibration (बदल नाही). resume = पुढचा leg impulse चं टोक ओलांडतो. p = label-shuffle permutation (एकतर्फी).

| TF | period | pullbacks | n_healthy | resume_healthy% | n_dangerous | resume_dangerous% | n_mixed | resume_mixed% | resume_सर्व% | p_perm |
|---|---|---|---|---|---|---|---|---|---|---|
| 15M | IS | 1576 | 22 | 90.9 | 1501 | 65.8 | 43 | 86.0 | 66.6 | 0.0075 |
| 15M | VAL | 520 | 5 | 100.0 | 496 | 65.1 | 13 | 92.3 | 66.5 |  |
| 1H | IS | 479 | 4 | 100.0 | 456 | 66.4 | 17 | 82.4 | 67.4 |  |
| 1H | VAL | 156 | 1 | 0.0 | 148 | 70.9 | 6 | 66.7 | 70.3 |  |


## (c) Retested वि. fresh zones (OE, 15M) — touches-bucket निहाय, random baseline सह

Random zones चे touches त्याच उगम-खिडकीत (खऱ्या zone च्या formed_at पासून दिवसाच्या आधीपर्यंत) मोजले. Bounce व्याख्या T3 सारखीच. z_cluster = महिना-cluster bootstrap (एकच zone अनेक दिवस येतो ⇒ rows स्वतंत्र नाहीत).

| period | touches | n_real | bounce_real% | n_random | bounce_random% | edge_pp | z_cluster |
|---|---|---|---|---|---|---|---|
| IS | 0 | 5956 | 27.2 | 15696 | 30.8 | -3.6 | -4.65 |
| IS | 1 | 1164 | 40.4 | 3013 | 41.9 | -1.5 | -0.83 |
| IS | 2 | 1130 | 42.8 | 2855 | 41.1 | 1.7 | 0.94 |
| IS | 3–4 | 2057 | 39.9 | 5302 | 39.8 | 0.1 | 0.06 |
| IS | 5+ | 16271 | 41.0 | 41313 | 40.6 | 0.3 | 0.63 |
| VAL | 0 | 2188 | 27.2 | 5591 | 29.0 | -1.8 | -1.12 |
| VAL | 1 | 328 | 41.8 | 926 | 43.2 | -1.4 | -0.47 |
| VAL | 2 | 319 | 47.3 | 821 | 43.2 | 4.1 | 0.99 |
| VAL | 3–4 | 597 | 45.1 | 1486 | 43.1 | 1.9 | 0.85 |
| VAL | 5+ | 5746 | 44.6 | 14532 | 44.0 | 0.6 | 0.66 |


## निष्कर्ष
(हाताने लिहिलेला. 18 + 10 + 4 सेल्स तपासले ⇒ 5% स्तरावर काही "महत्त्वाचे" सेल्स योगायोगानेही येतात; म्हणून IS आणि VAL दोन्हींत एकाच दिशेने टिकतं तेच निष्कर्ष मानले.)

1. **(a) Positional short strike — Daily/Weekly levels मुळे सुरक्षा मिळत नाही.**
   - तिन्ही engines (SR V3 day+week, sr_dynamic daily, OE 1d) मध्ये level च्या पलीकडची strike त्याच % अंतरावरच्या random-दिवस strike इतकीच तुटते.
   - z = महिना-cluster bootstrap (review नंतर; साधा z फुगलेला होता). 36 पैकी फक्त एका सेलमध्ये |z| > 2.
   - ठळक सेल्स, आणि ते का टिकत नाहीत:
     - OE 1d, IS, 1–2%: close-breach कमी (22.9% वि. 27.0%, z −2.29). पण VAL मध्ये उलट दिशा (31.5% वि. 28.5%, z +0.51).
     - SR V3, IS, 1–2% आणि 2–4%: level strikes उलट **जास्त** तुटल्या (touch z +1.79 / +1.02). VAL मध्ये ≈ 0.
     - sr_dynamic, VAL, 0.5–1%: touch 48.4% वि. 59.4% (z −1.68). IS मध्ये फक्त −0.83. याच engine च्या VAL 1–2% मध्ये close उलट (z +1.87).
   - **ठरवणारं आहे अंतर**, level नाही. 5 सत्रांत breach दर (IS, RANDOM, तिन्ही engines ची श्रेणी):

     | अंतर | touch | close |
     |---|---|---|
     | 0.5–1% | ~62–67% | ~35–36% |
     | 1–2% | ~39–46% | ~21–27% |
     | 2–4% | ~16–21% | ~8–12% |

   - **Credit spread साठी:** strike निवडताना "level च्या मागे" हा नियम random पेक्षा चांगला नाही. अंतर (आणि त्यानुसार premium) हाच मुख्य घटक.
   - Review दुरुस्त्या: SR V3 चे PDH/PDL आधी एक दिवस जुने होते (आता दिवस i−1); hold-window IS/VAL सीमा ओलांडत नाही; OE 1d मधले BROKEN zones वगळले. निष्कर्ष बदलला नाही.
2. **(b) HEALTHY वि. DANGEROUS — मोठा नमुना मिळाला नाही.**
   - 15M IS: HEALTHY फक्त 22 (resume 90.9% वि. 65.8%, p = 0.0075). 1H IS: फक्त 4. VAL: 5 आणि 1.
   - Spec च्या व्याख्येने HEALTHY फारच दुर्मिळ आहे (~1–1.5%), त्यामुळे 1H जोडून नमुना वाढत नाही.
   - निरीक्षण (post-hoc, निष्कर्ष नाही): "धोकादायक नसलेले" (HEALTHY + MIXED) 15M IS 65 legs, resume ~87% वि. 66%; VAL 18 legs, ~94%.
     हे पुढचं आधीच ठरवायचं गृहीतक होऊ शकतं ("NOT DANGEROUS वि. DANGEROUS"). याला वापरकर्त्याची मंजुरी हवी.
   - REVIEW कायम.
3. **(c) Retested वि. fresh — random baseline सह फरक नाहीसा होतो.**
   - 1+ touches असलेल्या खऱ्या zones चा bounce त्याच touches असलेल्या random zones इतकाच आहे (edge −1.5 ते +4.1pp, cluster |z| ≤ 0.99).
   - T3 मधलं "retested zones जास्त टिकतात" हे level-गुणधर्म नाही — random zones मध्येही तोच pattern आहे.
   - **निरीक्षण (निष्कर्ष नाही):** fresh (0-touch) OE zones random fresh zones पेक्षा कमकुवत दिसतात: IS 27.2% वि. 30.8% (cluster z −4.65); VAL 27.2% वि. 29.0% (त्याच दिशेने, पण z −1.12, सांख्यिकीदृष्ट्या पुष्टी नाही).
     एकच zone अनेक महिने टिकतो, त्यामुळे महिना-cluster सुद्धा पूर्ण स्वतंत्र नाही ⇒ IS चा z अजूनही थोडा फुगलेला असू शकतो.
4. **BANKNIFTY offline डेटा:** repo मध्ये नाही. सार्वजनिक स्रोत (2015 पासूनचा 1-minute):
   - Kaggle: [NIFTY BANK 1 minute data](https://www.kaggle.com/datasets/sumansarkar24/nifty-bank-1-minute-data-from-10-years), [BankNifty data 1-minute](https://www.kaggle.com/datasets/sandeepkapri/banknifty-data-upto-2024);
   - GitHub: [sandeepkapri/BankNifty-Minute-Data](https://github.com/sandeepkapri/BankNifty-Minute-Data).

   हे third-party, अनधिकृत डेटा आहेत आणि त्यात 2024-04 नंतरचा (holdout) भागही आहे ⇒ download केलं नाही. वापरायचा निर्णय वापरकर्त्याचा; वापरल्यास 2024-03-31 नंतरचा भाग load करतानाच कापायचा.
5. **G2 सारांश:**
   - या तिन्ही चाचण्यांमुळे "levels / leg labels मुळे edge" हा दावा बळकट होत नाही.
   - कोणताही gate/engine चालू करण्याची शिफारस नाही. T4 थांबलेलाच ठेवावा.
