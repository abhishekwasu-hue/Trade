# आधीच नोंदवलेली (pre-registered) गृहीतके

**नियम:**
- प्रत्येक गृहीतकाची व्याख्या, metric आणि pass नियम **डेटा पाहण्याआधी** इथे लिहिले आहेत.
- चाचणी फक्त नमूद केलेल्या स्वतंत्र डेटावर, **एकदाच** होईल.
- निकालानंतर व्याख्या, thresholds किंवा TF बदलणार नाही. बदल हवा असेल तर नवीन क्रमांकाचं नवीन गृहीतक लिहायचं, आणि त्याला पुन्हा नवीन स्वतंत्र डेटा लागेल.
- Sealed holdout (2024-04 पासूनचा) या चाचण्यांत वापरला जाणार नाही.
- नोंदणीची तारीख: **2026-10-06**. वापरकर्त्याचा निर्णय: G2 नंतर (3).

---

## H-PB1 · "DANGEROUS नसलेले" pullbacks वि. DANGEROUS pullbacks — trend resume

**उगम (शोध — पुरावा नाही):**
- G2 (b) मधलं post-hoc निरीक्षण, NIFTY 15M IS 2015–2021 (`docs/reports/g2_followups.md`).
- NOT DANGEROUS (HEALTHY + MIXED): 65 legs, resume ~87%. DANGEROUS: resume ~66%.
- हा आकडा व्याख्या पाहिल्यानंतर निवडला ⇒ NIFTY वर पुन्हा तपासणं निरर्थक. म्हणून चाचणी फक्त स्वतंत्र डेटावर.

**डेटा:**
- BANKNIFTY index, **15-minute** candles, 2015-01-01 → 2024-03-31 (2024-03-31 नंतरचा भाग load करतानाच कापायचा).
- स्रोत अधिकृत/विश्वासार्ह हवा (वापरकर्त्याचा निर्णय: Kaggle/GitHub नको).
- ⚠️ niftyindices.com चा **daily** CSV या गृहीतकासाठी पुरेसा नाही: शोध 15M वर होता, आणि daily legs वेगळ्या TF चे आहेत. अधिकृत BANKNIFTY intraday (15M किंवा 1M) डेटा मिळेपर्यंत ही चाचणी **प्रलंबित**. Daily वर चालवायची असेल तर ते वेगळं, नवीन गृहीतक (H-PB1-D) म्हणून आधी नोंदवावं लागेल.

**व्याख्या (गोठवलेली):**
- Legs: `price_action.legs.build_legs(df, LegConfig(e_hi=0.35, o_lo=0.65, d_k=1.5, d_body=0.5))`. बाकी सर्व `LegConfig` डीफॉल्ट, 2026-10-06 च्या code प्रमाणे. हा T2.3 चा NIFTY IS calibration आहे; BANKNIFTY वर पुन्हा calibration नाही.
- Pullback = `role == PULLBACK`.
- गट:
  - **ND** = label ∈ {HEALTHY_PULLBACK, MIXED_PULLBACK};
  - **D** = label == DANGEROUS_PULLBACK.
- resume = `price_action.leg_eval.outcomes` चा `resume`: pullback नंतरचा पुढचा leg impulse चं टोक ओलांडतो (1/0). NaN (पुढचा leg नाही) वगळा.
- सर्व pullbacks, दोन्ही दिशा, एकत्र.

**Metric:** Δ = resume%(ND) − resume%(D).

**Pass नियम — चारही अटी हव्यात:**
1. n(ND) ≥ 30 आणि n(D) ≥ 100. नसल्यास निकाल "अपुरा नमुना", pass नाही.
2. Δ ≥ +10 percentage points.
3. Label-shuffle permutation (ND/D labels; 10 000 shuffles; seed 11; एकतर्फी, Δ > 0): p < 0.01.
4. कालक्रमानुसार दोन अर्धे (2015-01 → 2019-08 आणि 2019-09 → 2024-03): दोन्हींत Δ > 0.

**Fail:** H-PB1 नाकारलं. NOT-DANGEROUS वर आधारित कुठलाही gate/filter प्रस्तावित होणार नाही.

**Pass:** फक्त "पुढे तपासण्यासारखं" एवढाच अर्थ. Gate/engine चालू करण्याचा निर्णय वापरकर्त्याचा, आणि sealed holdout G4 वरच.

---

## H-POS1 · BANKNIFTY positional short strike — levels वि. random (G2 (a) ची प्रतिकृती)

**उगम:** G2 (a), NIFTY. Level च्या पलीकडची strike random-दिवस strike इतकीच तुटते; ठरवणारं अंतर आहे.

**अपेक्षा (null):** BANKNIFTY वरही level-आधारित strike चा फायदा नाही.

**डेटा:**
- ~~niftyindices.com वरचा अधिकृत NIFTY BANK daily CSV.~~ **दुरुस्ती 2026-10-06, चाचणी चालवण्याआधी:** वापरकर्त्याने VPS वर Upstox V3 historical API मधून काढलेला BANKNIFTY daily CSV:
  - `data/research/BANKNIFTY_daily_2015_2024-03.csv`, 2290 दिवस, 2015-01-01 → 2024-03-28;
  - स्तंभ: date, open, high, low, close;
  - फक्त डेटा-स्रोत बदलला; पद्धत आणि नियम तसेच.
- 2024-03-31 नंतरचा भाग load करतानाच कापायचा.
- IS = 2015–2021, VAL = 2022-01 → 2024-03.

**व्याख्या (गोठवलेली — `g2_followups.py` (a) सारखीच, फक्त daily engines):**
- Engines:
  - SR V3 (day + week; सत्र-अखेर stamp);
  - sr_dynamic daily (prd = 5, ±0.1% band).
  - OE 1d वगळला, कारण त्याला intraday लागतं.
- दर दिवशी प्रत्येक बाजूचा 0.5–4% मधला सर्वात जवळचा level. Strike = दूरची कड.
- Hold 5 सत्र. Hold-window IS/VAL सीमा ओलांडत नाही.
- Baseline: त्याच period चे 5 यादृच्छिक दिवस, तेच % अंतर, तीच बाजू (seed 11).
- अंतर-buckets: 0.5–1, 1–2, 2–4 %.
- z = महिना-cluster bootstrap (1000).

**"Level edge" मानण्याचा नियम — सर्व अटी:**
- एकाच engine × bucket मध्ये touch-breach **कमी**;
- IS आणि VAL दोन्हींत cluster z ≤ −2;
- फरक ≥ 3 pp.

असा सेल नसेल तर null टिकला (अपेक्षित).

---

## H-BR1 · NIFTY वर fit केलेलं strike-breach model BANKNIFTY वर calibrated आहे का

**उगम:** `strike_breach_model.py` — NIFTY IS 2015–2021 वर fit, NIFTY VAL वर calibrated (`docs/reports/strike_breach_model.md`).

**डेटा:** H-POS1 सारखाच BANKNIFTY daily (2024-03-31 नंतर कापलेला). IS 2015–2021 आणि VAL 2022 → 2024-03 **वेगवेगळे** तपासायचे. दोन्ही BANKNIFTY साठी out-of-sample आहेत, कारण model NIFTY वर fit केलं आहे.

**व्याख्या (गोठवलेली):**
- Rows: `strike_breach_model.build_rows` (तीच रचना).
  - Weekly expiry गुरुवार धरला. BANKNIFTY ची प्रत्यक्ष expiry 2023-09 पासून बुधवार होती; हा फरक नोंदवला, पण पद्धत NIFTY सारखीच ठेवली.
- Predictions: `docs/reports/strike_breach_model_coef.json` मधले **गोठवलेले** M_RV coefs (expiry close आणि touch). पुन्हा fit नाही.
- Benchmark: Φ(−z_rv).

**Pass नियम (expiry close; IS आणि VAL दोन्हींत):**
1. log-loss(M_RV) ≤ log-loss(Φ(−z)).
2. Predicted bins (0–5, 5–10, 10–20, 20–30, 30–50 %) पैकी n ≥ 300 असलेल्या प्रत्येक bin मध्ये |actual − mean predicted| ≤ 5 pp.

Touch breach फक्त माहितीसाठी आहे; pass नियम नाही.

**Fail:** NIFTY वरचा अंतर-तक्ता BANKNIFTY ला थेट लागू करता येत नाही. वेगळं calibration लागेल, पण ते sealed holdout शिवाय फक्त IS वर.
