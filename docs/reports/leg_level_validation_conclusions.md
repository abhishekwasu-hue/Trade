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
