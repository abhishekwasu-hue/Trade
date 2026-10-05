# रात्रीचा एकत्रित अहवाल — T1 → T2 → T3 (G2 वर थांबलो)

**थोडक्यात:** तीन टप्पे पूर्ण, प्रत्येकाचा PR — tests, CI, independent review, मग merge.
- कोणताही bot gate चालू केलेला नाही.
- LIVE / order type बदललेला नाही.
- Sealed holdout उघडलेला नाही.
- डीफॉल्ट वर्तन बदललेलं नाही.

| टप्पा | PR | स्थिती |
|---|---|---|
| T1 — निदान गृहीतकं H1–H5 | #243 | merged |
| T2 — Leg & level strength classifier (+ G1 नमुने) | #244 | merged |
| T3 — Leg/Level validation (Osler) | हा PR | G2 — तुमचा निर्णय हवा |

## 1. T1 — काय सापडलं (`docs/reports/t1_hypotheses.md`)
- Opportunity Engine V1 चे **सर्व 8 trials IS मध्ये तोट्यात.** BASE: −0.18R/trade, 390 trades.
- H3 (SL < 0.25 × ADR असलेले trades नाकारणे) तोटा सर्वात कमी करतो: IS −71R → −6R. पण हे "कमी trades" मुळे; निरपेक्ष edge नाही (DSR 0.003).
- D1/D2 चे नमुने फार लहान (IS 11–15 trades) ⇒ H1/H4 वर निष्कर्ष नाही.
- H2: LONG_ONLY bias मधले D2 (gap-up fade) gate ने नाकारले जातात. त्यांचा counterfactual IS +0.32R (43 trades) — **फक्त नोंद**, नवीन गृहीतक म्हणून G2 ला.

## 2. T2 — Legs (`docs/reports/leg_classifier_g1.md`)
- चार्टवर swings/legs योग्य दिसतात — **10 नमुना दिवसांचे screenshots report मध्ये**.
- Dashboard → चार्ट खाली **"Legs" checkbox** (डीफॉल्ट बंद).
- STRONG वि. WEAK impulse: पुढच्या 2 तासांत फरकाचा पुरावा नाही.
- Spec च्या नियमांनुसार ~96% pullbacks "धोकादायक" ठरतात. "निरोगी" फक्त ~1%; ते दिसले की trend 91% वेळा पुढे जातो (n = 22) — आशादायक पण लहान नमुना.

## 3. T3 — Levels खरंच काम करतात का? (`docs/reports/leg_level_validation.md`)
- **sr_dynamic, SR V3, OE zones, OE + ताकद — एकाही engine चे levels random levels पेक्षा जास्त bounce देत नाहीत** (फरक ±3pp, संख्याशास्त्रीय महत्त्व नाही).
- SR V3 levels जास्त तुटतात (66%) कारण ते फार अरुंद आहेत. त्याच रुंदीचे random levels सुद्धा तितकेच तुटतात.
- Option seller साठी: "मजबूत zone च्या पलीकडे strike" ही strike random strike इतकीच तुटते ⇒ सुरक्षा नाही.
- एक मनोरंजक निरीक्षण: **कधीच retest न झालेले zones कमी टिकतात (27%) — एकदा तरी retest झालेले जास्त (37–43%)**, IS आणि VAL दोन्हींत. पुढचं गृहीतक म्हणून.

## 4. तुमचे निर्णय हवेत (G1 + G2)
1. **G1:** report मधले 10 चार्ट पाहून leg लेबल्स पटतात का?
2. **G2:** T4 (one-level-truth / approach gate / credit-spread filter) थांबवायचा का? **माझी शिफारस: थांबवा — पुरावा नाही.**
3. पुढे दोन गृहीतकं तपासायची का? "निरोगी pullback" आणि "retested zone". BANKNIFTY/5M सह, VPS वर, 2024-03 पूर्वीचा डेटा.
4. T5 (order type — फक्त अहवाल + default-off marketable LIMIT) सुरू करायचा का? हा G2 शी संबंधित नाही. LIVE बदल G3 ला.

## 5. VPS वर तुम्ही चालवायचं (एकत्रित block)
```bash
cd /root/Trade && git pull -q origin main && set -a && . /root/Trade/.env && set +a && python3 cache_holdout_upstox.py 2>&1 | grep -v "WARNING\|No runtime"
```
(फक्त bars/दिवस संख्या छापतो; डेटा `data/holdout/` मध्ये, G4 पर्यंत बंद.)

## 6. आधीच्या संदेशांवर (VPS outputs)
- **COPPER:** Dynamic 30M ने तुमचे 3/3 levels पकडले, SRV3 ने 0/3 ⇒ COPPER साठी `level_engine = DYNAMIC` ची शिफारस कायम (setting तुम्ही बदलायची).
- **GOLD/SILVER/NIFTY:** कुठलाही engine तुमचे levels सातत्याने पकडत नाही, आणि मधले जास्तीचे levels बरेच. हे T3 च्या निकालाशी सुसंगत आहे.
- **SILVER trendline audit:** IS मध्ये चढती support real 53.7% वि. control 38.1% hold. पण OOS मध्ये real control पेक्षा *कमी* (42.9 वि. 50.0), आणि उतरती resistance दोन्हीकडे control पेक्षा कमी ⇒ trendlines फक्त चार्टवर, gate म्हणून नको.
