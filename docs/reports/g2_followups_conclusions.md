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
