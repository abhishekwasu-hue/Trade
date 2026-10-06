# G2 नंतरच्या चाचण्या — positional strikes, pullbacks, retested zones (NIFTY, report-only)

डेटा: NIFTY offline 1M (2015 → 2024-03). IS 2015–2021, VAL 2022 → 2024-03. Sealed holdout बंद. कोणताही gate चालू नाही.

## (a) Positional short strike — 5 सत्र hold (Daily/Weekly levels वि. यादृच्छिक दिवस, तेच अंतर)

Strike = किंमतीपासून 0.5–4.0% मधल्या सर्वात जवळच्या level ची दूरची कड (put: support चा low, call: resistance चा high). touch = 5 सत्रांत कधीही पलीकडे; close = 5व्या सत्राचा close पलीकडे. RANDOM = त्याच period चे 5 यादृच्छिक दिवस, तेच % अंतर, तीच बाजू.

| engine | period | अंतर | n_level | touch_level% | touch_random% | z_touch | close_level% | close_random% | z_close |
|---|---|---|---|---|---|---|---|---|---|
| DYN_D | IS | 0.5–1.0% | 269 | 61.3 | 63.0 | -0.53 | 31.6 | 34.7 | -0.99 |
| DYN_D | IS | 1.0–2.0% | 569 | 40.9 | 39.1 | 0.83 | 21.3 | 21.9 | -0.35 |
| DYN_D | IS | 2.0–4.0% | 890 | 15.7 | 15.9 | -0.12 | 9.3 | 7.9 | 1.39 |
| DYN_D | VAL | 0.5–1.0% | 93 | 48.4 | 59.6 | -1.99 | 30.1 | 34.4 | -0.8 |
| DYN_D | VAL | 1.0–2.0% | 230 | 40.0 | 38.0 | 0.57 | 25.2 | 21.8 | 1.13 |
| DYN_D | VAL | 2.0–4.0% | 349 | 12.0 | 12.6 | -0.3 | 6.6 | 6.2 | 0.24 |
| OE_1D | IS | 0.5–1.0% | 2586 | 67.1 | 66.7 | 0.39 | 36.9 | 35.4 | 1.48 |
| OE_1D | IS | 1.0–2.0% | 415 | 42.7 | 48.9 | -2.31 | 21.7 | 29.6 | -3.26 |
| OE_1D | IS | 2.0–4.0% | 39 | 15.4 | 21.5 | -0.87 | 10.3 | 14.4 | -0.68 |
| OE_1D | VAL | 0.5–1.0% | 958 | 66.8 | 65.8 | 0.59 | 36.4 | 35.6 | 0.52 |
| OE_1D | VAL | 1.0–2.0% | 65 | 49.2 | 40.9 | 1.24 | 29.2 | 25.5 | 0.62 |
| OE_1D | VAL | 2.0–4.0% | 10 | 20.0 | 26.0 | -0.4 | 10.0 | 16.0 | -0.49 |
| SRV3_DW | IS | 0.5–1.0% | 1175 | 63.0 | 63.0 | -0.03 | 35.7 | 33.3 | 1.62 |
| SRV3_DW | IS | 1.0–2.0% | 1497 | 43.4 | 42.5 | 0.58 | 24.0 | 24.1 | -0.08 |
| SRV3_DW | IS | 2.0–4.0% | 324 | 22.8 | 19.1 | 1.56 | 12.7 | 9.8 | 1.57 |
| SRV3_DW | VAL | 0.5–1.0% | 357 | 61.3 | 60.2 | 0.4 | 33.3 | 33.1 | 0.1 |
| SRV3_DW | VAL | 1.0–2.0% | 552 | 38.8 | 38.9 | -0.06 | 21.6 | 21.2 | 0.19 |
| SRV3_DW | VAL | 2.0–4.0% | 115 | 22.6 | 20.5 | 0.5 | 12.2 | 10.6 | 0.49 |


## (b) HEALTHY वि. DANGEROUS pullback — trend resume (15M आणि 1H)

LegConfig = T2.3 चं IS calibration (बदल नाही). resume = पुढचा leg impulse चं टोक ओलांडतो. p = label-shuffle permutation (एकतर्फी).

| TF | period | pullbacks | n_healthy | resume_healthy% | n_dangerous | resume_dangerous% | n_mixed | resume_mixed% | resume_सर्व% | p_perm |
|---|---|---|---|---|---|---|---|---|---|---|
| 15M | IS | 1576 | 22 | 90.9 | 1501 | 65.8 | 43 | 86.0 | 66.6 | 0.0075 |
| 15M | VAL | 520 | 5 | 100.0 | 496 | 65.1 | 13 | 92.3 | 66.5 |  |
| 1H | IS | 479 | 4 | 100.0 | 456 | 66.4 | 17 | 82.4 | 67.4 |  |
| 1H | VAL | 156 | 1 | 0.0 | 148 | 70.9 | 6 | 66.7 | 70.3 |  |


## (c) Retested वि. fresh zones (OE, 15M) — touches-bucket निहाय, random baseline सह

Random zones चे touches त्याच उगम-खिडकीत (खऱ्या zone च्या formed_at पासून दिवसाच्या आधीपर्यंत) मोजले. Bounce व्याख्या T3 सारखीच.

| period | touches | n_real | bounce_real% | n_random | bounce_random% | edge_pp | z |
|---|---|---|---|---|---|---|---|
| IS | 0 | 5956 | 27.2 | 15696 | 30.8 | -3.6 | -5.13 |
| IS | 1 | 1164 | 40.4 | 3013 | 41.9 | -1.5 | -0.89 |
| IS | 2 | 1130 | 42.8 | 2855 | 41.1 | 1.7 | 1.01 |
| IS | 3–4 | 2057 | 39.9 | 5302 | 39.8 | 0.1 | 0.06 |
| IS | 5+ | 16271 | 41.0 | 41313 | 40.6 | 0.3 | 0.73 |
| VAL | 0 | 2188 | 27.2 | 5591 | 29.0 | -1.8 | -1.54 |
| VAL | 1 | 328 | 41.8 | 926 | 43.2 | -1.4 | -0.45 |
| VAL | 2 | 319 | 47.3 | 821 | 43.2 | 4.1 | 1.25 |
| VAL | 3–4 | 597 | 45.1 | 1486 | 43.1 | 1.9 | 0.8 |
| VAL | 5+ | 5746 | 44.6 | 14532 | 44.0 | 0.6 | 0.77 |


## निष्कर्ष

(हाताने लिहिलेला. 18 + 10 + 4 सेल्स तपासले ⇒ 5% स्तरावर काही "महत्त्वाचे" सेल्स योगायोगानेही येतात; म्हणून IS आणि VAL दोन्हींत एकाच दिशेने टिकतं तेच निष्कर्ष मानले.)

1. **(a) Positional short strike — Daily/Weekly levels मुळे सुरक्षा मिळत नाही.**
   - तिन्ही engines (SR V3 day+week, sr_dynamic daily, OE 1d) मध्ये level च्या पलीकडची strike त्याच % अंतरावरच्या random-दिवस strike इतकीच तुटते.
   - बहुतेक सेल्समध्ये |z| < 1.6.
   - IS मध्ये एकच ठळक सेल आहे: OE 1d, 1–2%, level strikes कमी तुटल्या (touch 42.7% वि. 48.9%). पण VAL मध्ये तो उलट दिशेने गेला (49.2% वि. 40.9%) ⇒ टिकत नाही.
   - **ठरवणारं आहे अंतर**, level नाही. 5 सत्रांत breach दर (सर्व engines, IS, RANDOM सरासरी):

     | अंतर | touch | close |
     |---|---|---|
     | 0.5–1% | ~63–67% | ~33–35% |
     | 1–2% | ~40–49% | ~22–30% |
     | 2–4% | ~15–21% | ~8–14% |

   - **Credit spread साठी:** strike निवडताना "level च्या मागे" हा नियम random पेक्षा चांगला नाही; अंतर (आणि त्यानुसार premium) हाच मुख्य घटक.
2. **(b) HEALTHY वि. DANGEROUS — मोठा नमुना मिळाला नाही.**
   - 15M IS: HEALTHY फक्त 22 (resume 90.9% वि. 65.8%, p = 0.0075). 1H IS: फक्त 4. VAL: 5 आणि 1.
   - Spec च्या व्याख्येने HEALTHY फारच दुर्मिळ आहे (~1–1.5%), त्यामुळे 1H जोडून नमुना वाढत नाही.
   - निरीक्षण (post-hoc, निष्कर्ष नाही): "धोकादायक नसलेले" (HEALTHY + MIXED) 15M IS 65 legs, resume ~87% वि. 66%; VAL 18 legs, ~94%.
     हे पुढचं आधीच ठरवायचं गृहीतक होऊ शकतं ("NOT DANGEROUS वि. DANGEROUS"). याला वापरकर्त्याची मंजुरी हवी.
   - REVIEW कायम.
3. **(c) Retested वि. fresh — random baseline सह फरक नाहीसा होतो.**
   - 1+ touches असलेल्या खऱ्या zones चा bounce त्याच touches असलेल्या random zones इतकाच आहे (edge −1.5 ते +4.1pp, |z| ≤ 1.25).
   - T3 मधलं "retested zones जास्त टिकतात" हे level-गुणधर्म नाही — random zones मध्येही तोच pattern आहे.
   - उलट, **fresh (0-touch) OE zones random fresh zones पेक्षा वाईट**: IS 27.2% वि. 30.8% (z −5.1); VAL 27.2% वि. 29.0% (त्याच दिशेने, z −1.5).
     म्हणजे "ताजा OE zone" हा सरळ random पेक्षाही कमकुवत bounce देतो.
4. **BANKNIFTY offline डेटा:** repo मध्ये नाही. सार्वजनिक स्रोत (2015 पासूनचा 1-minute):
   - Kaggle: [NIFTY BANK 1 minute data](https://www.kaggle.com/datasets/sumansarkar24/nifty-bank-1-minute-data-from-10-years), [BankNifty data 1-minute](https://www.kaggle.com/datasets/sandeepkapri/banknifty-data-upto-2024);
   - GitHub: [sandeepkapri/BankNifty-Minute-Data](https://github.com/sandeepkapri/BankNifty-Minute-Data).

   हे third-party, अनधिकृत डेटा आहेत आणि त्यात 2024-04 नंतरचा (holdout) भागही आहे ⇒ download केलं नाही. वापरायचा निर्णय वापरकर्त्याचा; वापरल्यास 2024-03-31 नंतरचा भाग load करतानाच कापायचा.
5. **G2 सारांश:**
   - या तिन्ही चाचण्यांमुळे "levels / leg labels मुळे edge" हा दावा बळकट होत नाही.
   - कोणताही gate/engine चालू करण्याची शिफारस नाही. T4 थांबलेलाच ठेवावा.
