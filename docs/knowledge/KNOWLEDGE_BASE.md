# Trading Knowledge Base आणि Chart Reading Protocol
**Pullback credit spread (NIFTY 15M) साठी: bot, vision आणि Abhi साठी एकच संदर्भ**

> **आवृत्ती:** 2026-10-08 · **स्रोत:**
> - Project चे 6 अहवाल: candlestick, Elliott सिद्धांत, Elliott setups/spec, correction waves, gap, leg/level;
> - repo चे निकाल (T3, G2, C2, candle merge, strike model);
> - नवीन अभ्यास (या आवृत्तीत): areas, liquidity, Fibonacci, channels, Dow, Wyckoff, chart patterns, RSI divergence, session, expiry, MTF, theta, VIX.
>
> **वापर:**
> - Code चे facts (`chart_reader/facts.py`) आणि vision चं playbook (system prompt) **याच document वरून** बनतात.
> - नवीन ज्ञान जोडायचं असेल तर इथे जोडायचं, मग code आणि playbook मध्ये.
> - Repo मध्ये जागा: `docs/knowledge/KNOWLEDGE_BASE.md`.

---

## लेबलांचा अर्थ
| लेबल | अर्थ |
|---|---|
| **[नियम]** | व्याख्येने खरं (उदा. Elliott rule). मोडलं तर count/कल्पना चुकीची. |
| **[पुरावा +]** | Peer-reviewed किंवा पद्धतशीर चाचणीत आधार मिळालेला. |
| **[पुरावा −]** | चाचणीत आधार **मिळाला नाही**. |
| **[अनुभव]** | Practitioners मध्ये प्रचलित, पण कठोर चाचणी नाही. |
| **[अनुमान]** | आपला तर्क, वरच्या गोष्टींवरून. |
| **[NIFTY]** | आपल्या repo मध्ये NIFTY data वर तपासलेला निकाल. |

**मोजपट्टी:**
- **MR** = शेवटच्या 20 बंद candles च्या (High − Low) चा median, चालू candle वगळून.
- सगळी अंतरं "× MR" मध्ये, कारण instrument किंवा TF बदलला तरी नियम तसेच राहतात.
- σ-अंतर (strike साठी) = spot × IV × √(दिवस/365).

**सूचना:** नवीन अभ्यासातले काही आकडे (equal highs ≤ 0.15 MR, sweep 0.1–1.0 MR, Fibonacci band ±0.25 MR) 50-bar true range वर लिहिलेले आहेत. Repo च्या 20-bar MR वर ते IS मध्ये पुन्हा calibrate करायचे.

**No-lookahead:** फक्त बंद candles. Swing pivot फक्त k (2–3) candles नंतर confirmed. त्याआधी तो वापरायचा नाही.

---

## अनुक्रमणिका
- **भाग A:** मूलतत्त्वं (Abhi ची शैली आणि विचारपद्धती)
- **भाग B:** Chart Reading Protocol (8 टप्पे)
- **भाग C:** Knowledge chapters K1–K14 (K10.3 volume सह)
- **भाग D:** पुराव्याची यादी आणि grade
- **भाग E:** नेहमीच्या चुका (checklist)
- **भाग F:** प्रामाणिक मर्यादा: काय सिद्ध आहे, काय नाही
- **भाग G:** विरोधाभासांचे निर्णय (एकच व्याख्या)
- **स्रोत**

---

# भाग A: मूलतत्त्वं

## A1. Abhi ची trading शैली
1. **Impulse** दिशा ठरवतो. त्यानंतर येणारी corrective चाल म्हणजे **pullback**. ती नेहमी corrective असते: zigzag (ABC), flat (ABC), triangle (ABCDE), आणि कधी combination (W-X-Y).
2. आधी खात्री करायची की हा **pullback आहे, reversal नाही.**
3. Pullback संपल्याची **पुष्टी** झाली की impulse च्या दिशेने credit spread विकायचा: uptrend मध्ये bull put, downtrend मध्ये bear call.
4. बाजार थोडा बाजूने गेला की profit, आणि 2–3 दिवसांत expiry जवळ आल्याने premium झिजतो. **लक्ष्य: 60–80% premium.**
5. **Risk मर्यादित, R:R ≥ 1:3** (spot वर: entry → invalidation वि. entry → target).
6. **Breakout entry कधीच नाही.** False break वर exit नाही.

## A2. विचारपद्धती: probability, नियमांची साखळी नाही
- Trading probability वर चालतं. पूर्ण गणिती नियमांची साखळी लावली तर trade मिळणारच नाही.
- **कोणतंही एक साधन निर्णय घेत नाही.** पुराव्यांची बेरीज (confluence), मग पुष्टी (reversal candle), मग R:R.
- **Chart वरचे buyer/seller areas आणि liquidity या ठोस (objective) गोष्टी आहेत.** Fibonacci, channel किंवा C = A ही **मोजपट्टी** आहे. ती तेव्हाच valid जेव्हा तिथे खरा area किंवा liquidity असेल (Abhi चा नियम, K7).
- Resistance horizontal असेल की तिरका, हे **आधी ठरवता येत नाही.** ताज्या price action वरून कळतं की बाजार कोणत्या area ला मान देतोय (K6).
- **प्रत्येक वेळी सगळी साधनं वापरून पाहायची** (Protocol टप्पा 3). 7 Oct 2026 ला फक्त horizontal पाहिल्याने उतरती trendline सुटली होती. ती चूक पुन्हा होऊ नये.

## A3. पक्के नियम (फक्त हे पाच; बाकी सगळं पुरावा)
1. Breakout / chase entry नाही. Support वर bear call किंवा resistance वर bull put नाही. Gap-and-go किंवा ORB नाही.
2. फक्त **बंद candle** वर entry.
3. स्पष्ट **invalidation**.
4. **R:R ≥ 1:3** spot वर.
5. Risk मर्यादा (dashboard).

**व्याख्यात्मक व्हेटो (score च्या बाहेर).** हे "पुरावे" नाहीत. हे असतील तर ती चाल pullback च नाही, म्हणून entry नाही:
- Count स्पष्ट असताना A-end किंवा B / triangle / X च्या **आत** entry. Count gray असेल तर हा व्हेटो लागत नाही; त्याऐवजी EW गुण.
- Impulse origin पलीकडे (> 100%) **acceptance** (real break).
- MAGNET level.
- Gap setup B मध्ये pullback आलाच नाही.

**Grade:** A किंवा B ⇒ entry (full size × tier setting). C ⇒ नाही (shadow मध्ये नोंद).

---

# भाग B: Chart Reading Protocol (bot आणि vision दोघांसाठी, दर वेळी याच क्रमाने)

> प्रत्येक टप्पा **निरीक्षण** देतो, gate नाही. शेवटी त्यांची गोष्ट आणि grade बनते.

## टप्पा 1: मोठं चित्र (Daily → 1H किंवा 75m)
- **Trend:** HH/HL की LH/LL, की range (K1). Trend मजबूत आहे की थकतोय (K10)?
- **Elliott:** मोठ्या degree मध्ये आपण कुठे आहोत (impulse चा मधला भाग, wave 5, correction)? (K3)
- **मोठे areas:** major swing highs/lows, role flips, range edges, मोठ्या trendlines, उघडे gaps.
- **TF शिडी:** Daily (context) → 1H किंवा 75m (swing ची दिशा) → 15M (pullback आणि entry). 4H मुळे NIFTY चं 6h15m session असमान तुटतं; 75m (= 5 × 15m) जास्त स्वच्छ. [अनुभव/अनुमान]

## टप्पा 2: Trade TF: ही चाल impulse आहे की correction?
- आधीचा **impulse** ओळखा: लांब (≥ 4 MR), मोठ्या bodies, कमी overlap, structure तोडणारा (BOS).
- आत्ताची चाल corrective आहे का: overlap, mixed candles, 3-wave रचना?
- **Correction प्रकार:** zigzag / flat (regular, expanded, running) / triangle / combination (K3).
- **Correction कुठपर्यंत आला:** A, B, की C चालू? A संपला असेल तर entry नाही (A-end ban). C-end किंवा E-end जवळ असेल तर setup.
- **Reversal ची चिन्हं** (K2): counter-move impulsive (displacement, 5 waves), impulse origin वर real break, 100% पलीकडे acceptance.

## टप्पा 3: Areas: **सगळी साधनं, प्रत्येक वेळी**
ही यादी पूर्ण तपासायची, एकही वगळायचा नाही:

| # | साधन | प्रकार | Chapter |
|---|---|---|---|
| a | Horizontal swing high/low cluster | ठोस | K4 |
| b | Role flip (तुटलेला support = resistance) | ठोस | K4 |
| c | Supply/demand origin (displacement च्या आधीचा base) | ठोस | K4 |
| d | Range edge | ठोस | K4 |
| e | Liquidity: equal highs/lows, आधीचे swing extremes, PDH/PDL (stop pools) | ठोस | K5 |
| f | **Sloping trendline** (ताज्या 2–3 swings मधून; ≥ 3 touches असल्यास जास्त वजन) | ठोस / ताज्या price action वरून | K6 |
| g | **Channel** (impulse चं, आणि correction चं स्वतःचं) | मोजपट्टी | K6 |
| h | Fibonacci retracement 38.2/50/61.8/78.6 (band ± 0.25 MR) | मोजपट्टी, confluence फक्त | K7 |
| i | C = A (0.618 / 1.0 / 1.618 × A) | मोजपट्टी, confluence फक्त | K3, K7 |
| j | Round numbers (100 / 500 / 1000) | ठोस (कमकुवत) | K8 |
| k | PDH / PDL / PDC, आधीच्या आठवड्याचा H/L | ठोस | K8 |
| l | Gap edge / PDC (gap दिवस, किंवा जुना न भरलेला gap) | ठोस (कमकुवत) | K13 |

**मग निवड:**
- **Active area** = ताज्या bars मध्ये बाजार ज्या area ला प्रत्यक्ष react करतोय तो (K6.4).
- **Confluence** = एकाच ठिकाणी (≤ 0.5 MR) किती वेगवेगळ्या **प्रकारची** साधनं जुळतात. ठोस + मोजपट्टी = चांगलं. नुसती मोजपट्टी = 0.
- प्रत्येक area ची स्थिती: ACTIVE / TESTED / BROKEN / FLIPPED / MAGNET (K5).

## टप्पा 4: Area वरचं वर्तन (price action)
- **Candles ची मालिका:** कोणाचं नियंत्रण? Bodies आणि wicks कोणत्या बाजूला? (K9)
- **Correction कमकुवत होतोय का:** legs लहान, overlap वाढतोय, spreads आकुंचन, closes पुन्हा वर सरकत आहेत (rising CLV) (K10, K12).
- **Sweep / spring / upthrust:** A चा low किंवा equal lows थोडे तोडून परत आत close? (K5)
- **Volume (NIFTY futures, वेळेनुसार normalise):** pullback मध्ये volume सुकतोय का? C-end ला absorption spike? Reversal candle ला volume? (K10.3)
- **RSI divergence** (फक्त पुरावा): C-end ला regular, किंवा pullback मध्ये hidden (K10).
- **Chart pattern वाचन:** flag (pullback) की double top / H&S (reversal warning)? (K11)

## टप्पा 5: Context
- **Gap ची गोष्ट:** आदल्या दिवशीची शेवटची चाल + आजचा gap ⇒ पुष्टी की विरोध (K13).
- **वेळ:** 09:15–09:45 मधला signal कमी विश्वासार्ह. 11:00–13:30 मध्ये प्रत्येक bar कमी माहिती देतो. दुपारी entry आणि रात्र hold हे evidence शी जुळतं (K14).
- **Expiry:** expiry पर्यंत किती दिवस. Expiry दिवशी नवीन entry पुढच्या weekly मध्ये.
- **Event आणि VIX:** event दिवस, VIX ची पातळी आणि बदल (K14).

## टप्पा 6: पुष्टी
- **Logical reversal candle** (composite 1–3 candles: touch → reclaim → strength → close location) बंद झालेली. CL 0.40–0.60 ⇒ follow-through ची वाट (K9).
- **अतिरिक्त पुरावा:** correction च्या स्वतःच्या छोट्या channel/trendline चा impulse दिशेने break, किंवा lower TF वर structure shift.

## टप्पा 7: Risk
- **Invalidation:** active area च्या पलीकडे + buffer, किंवा reversal candle च्या टोकापलीकडे. Elliott hard inv (उदा. wave 1 origin) माहिती म्हणून.
- **Target:** पुढचा opposite area, किंवा impulse चं टोक.
- **R:R ≥ 3** spot वर.
- **Strike:** invalidation च्या पलीकडे, **आणि** σ-अंतर पुरेसं (K14). Strike साठी अंतरच निर्णायक, level नाही [NIFTY].

## टप्पा 8: गोष्ट आणि grade
- 8–12 ओळींची गोष्ट: trend → impulse → correction प्रकार → area (confluence) → area वरचं वर्तन → context → पुष्टी → risk.
- **Evidence for / against** यादी, आणि grade (भाग D).
- **"मी कुठे चुकीचा ठरेन"** हे एका ओळीत.

---

# भाग C: Knowledge chapters

> प्रत्येक chapter चा साचा:
> - **काय** (व्याख्या);
> - **मानसशास्त्र**;
> - **ओळख**, code साठी, MR च्या पटीत;
> - **Pullback वाचनात उपयोग**;
> - **विश्वासार्हता**;
> - **चुका**.

## K1. Market structure आणि Dow theory
**काय.**
- Uptrend = higher highs (HH) + higher lows (HL). Downtrend = LH + LL.
- Dow चे तीन स्तर:
  - primary (trend);
  - secondary reaction (= आपला pullback);
  - minor (noise).
- आपल्यासाठी: 1H/75m swing = primary, 15M ABC = secondary, sub-waves = minor. [अनुमान]

**मानसशास्त्र.** Pullback म्हणजे profit-taking आणि उशिरा आलेले counter-trend traders. Trend दिशेचे buyers आधीच्या swing low च्या वर बचाव करतात, म्हणून HL तयार होतो.

**ओळख (repo `opportunity_engine/structure.py` च्या व्याख्या):**
- सगळे breaks फक्त **close** ने. Wick पलीकडे आणि close आत = **SWEEP**; trend state बदलत नाही.
- **BOS** = शेवटच्या swing high च्या वर close. ही event आहे; state बदलत नाही.
- **CHoCH** = protected HL च्या खाली close ⇒ UPTREND_WEAK. हा **इशारा** आहे, reversal नाही.
- **Reversal confirmed:** CHoCH नंतर LH तयार होतो, आणि मग CHoCH नंतरच्या low च्या खाली close. (Dow: पहिला break = इशारा; failed rally (LH) नंतरच reversal.)
- Range: 4 नवे swings आणि कोणताही निर्णय नाही ⇒ RANGE.
- Swing ग्राह्य धरण्यासाठी किमान आकार ≥ 1.5–2 MR, म्हणजे noise swings मोजले जात नाहीत.

**Pullback वाचनात उपयोग.**
- Pullback चा low आधीच्या HL च्या वर टिकला ⇒ trend जिवंत.
- Dow नुसार secondary reaction साधारण 1/3–2/3 retrace करते [अनुभव]. Abhi च्या अनुभवानुसार reversal 50%, 61.8% आणि कधी 78.6–80% पर्यंत खोल जाऊन येतो. ~0.80 पेक्षा खोल ⇒ reversal धोका वाढतो. 1.0 पलीकडे ⇒ HL तुटला, आता pullback नाही.
- **Trend थकण्याची खूण:** नवा HH आधीच्या high पेक्षा < 0.5 MR पुढे (marginal HH), आणि त्यानंतरचा pullback आधीच्या pullback पेक्षा मोठा.
- **Multi-TF:** 15M चा "uptrend" हा 1H downtrend मधला secondary reaction असू शकतो. नेहमी वरचा TF पाहायचा.

**विश्वासार्हता.**
- 1/3–2/3 नियम: [अनुभव], चाचणी नाही.
- "Trend टिकतो" (momentum): [पुरावा +]. Time-series momentum 58 futures markets मध्ये (Moskowitz, Ooi & Pedersen 2012). Intraday momentum: पहिल्या अर्ध्या तासाचा return शेवटच्या अर्ध्या तासाचा अंदाज देतो, पण R² ~2% (Gao et al. 2018, US).
- Swing-pivot नियम स्वतः तपासलेले नाहीत.

**चुका.**
- प्रत्येक लहान वळणाला swing मानणं.
- पहिल्या CHoCH लाच reversal म्हणणं.
- वरचा TF न पाहणं.

---

## K2. Impulse वि. correction (pullback की reversal?)
**काय.**
- **Impulse:** वेगवान, कमी overlap, मोठ्या bodies, closes टोकाजवळ, आधीचे extremes तोडतो.
- **Correction:** संथ किंवा chop, overlap, mixed candles, विरुद्ध दिशेचे wicks.

**मानसशास्त्र.**
- Impulse मध्ये एक बाजू घाईत असते: market orders आणि stop-outs.
- Correction मध्ये विरुद्ध बाजू संधी शोधते, पण trend दिशेच्या resting orders ना भिडते. म्हणून चाल तुटक होते.
- Trend दिशेची बाजू थकली की तिचे legs लहान होतात आणि counter legs मोठे.

**ओळख (प्रत्येक leg वर, confirmed pivots).**

| मोजमाप | Impulse | Healthy pullback | धोक्याचा (reversal कडे) |
|---|---|---|---|
| Retrace (impulse च्या प्रमाणात) | — | 0.382–0.80 (Abhi; repo च्या HEALTHY label चा `r_ok` 0.5 फक्त research label) | > 0.80 (repo `r_warn` 0.75 engine मध्ये 0.80 करायचा); > 1.0 = reversal |
| Speed (MR / bar) | जास्त | < impulse × 0.8 | ≥ impulse |
| Overlap ratio | < 0.4 | > 0.6 | — |
| Displacement / मोठी counter candle | हो | नाही | counter दिशेने हो |
| Candles चा spread | रुंद | impulse पेक्षा अरुंद | रुंद |
| Protected swing | — | अबाधित | CHoCH + displacement |

**Repo चे labels (`price_action/legs.py`):**
- STRONG_IMPULSE / WEAK_IMPULSE / HEALTHY_PULLBACK / DANGEROUS_PULLBACK / MIXED_PULLBACK / REVERSAL / RANGE.
- Depth > 1 एखाद्या impulse नंतर ⇒ REVERSAL.

**⚠️ NIFTY 15M वरची वस्तुस्थिती [NIFTY]:**
- NIFTY चे pullbacks अनेकदा **impulse इतकेच किंवा जास्त वेगवान** असतात (57%), त्यांत displacement असतं (62%), आणि ते 0.75 पेक्षा खोल असतात (31%).
- त्यामुळे फक्त ~1% pullbacks "HEALTHY" ठरतात. HEALTHY नंतर trend पुन्हा सुरू होण्याचं प्रमाण 90.9% (n = 22), तर DANGEROUS नंतर 65.8% (n = 1,501). फरक दिसतो, पण n फार लहान ⇒ REVIEW.
- Repo C2: NIFTY वर corrective legs सरासरी **कमी** bars चे निघाले (impulsive median 7 वि. corrective 4 bars, D0).
- **म्हणून "pullback impulse पेक्षा संथ असतो" हा पुरावा NIFTY वर कमकुवत आहे.** तो जास्त वजनाने वापरायचा नाही.
- सगळ्यात स्वच्छ भेद **overlap** आणि **रचना (3 waves वि. 5 waves)** यातून मिळतो, आणि **impulse origin टिकला की नाही** यातून.

**Pullback वाचनात उपयोग.**
- Correction 3 waves, overlapping, impulse origin च्या आत ⇒ pullback.
- Counter-move मध्ये 5 waves, displacement, origin वर real break ⇒ **reversal, entry नाही.**
- एकच निरीक्षण निर्णायक नाही; सगळे एकत्र पाहायचे.

**विश्वासार्हता.** भूमितीय वर्णन विश्वासार्ह. "Strong impulse पुढे चालू राहतो" हा दावा NIFTY वर REJECT (PBO 0.35). HEALTHY चं वजन REVIEW मध्ये.

**चुका.**
- एका candle वरून ताकद ठरवणं.
- Opening candles (नैसर्गिकरीत्या रुंद) वरून निष्कर्ष काढणं.
- Triangle चा वेगवान E wave म्हणजे counter-impulse समजणं.
- Running flat (मजबूत trend चं लक्षण) ला कमजोरी समजणं.

---

## K3. Elliott: corrections, entry points, invalidation
**मूलभूत [नियम] (Frost & Prechter; spec R1–R11):**
- **R1:** wave 2 कधीच wave 1 च्या सुरुवातीपलीकडे जात नाही.
- **R2:** wave 3 सगळ्यात लहान नसतो.
- **R3:** wave 4 wave 1 च्या भागात शिरत नाही (NIFTY **spot** वर; diagonal अपवाद).
- **R4:** correction कधीच 5 waves नसतो. **Trend विरुद्ध पहिली 5-wave चाल ही correction चा शेवट नसते ⇒ A-end ban.**
- **R5:** Triangle एकटा wave 2 नसतो; तो फक्त शेवटच्या actionary wave आधी येतो (4, B, X).
- **R6:** Zigzag मध्ये B कधीच A च्या सुरुवातीपलीकडे जात नाही.
- **R7:** Flat मध्ये B ≥ 90% × A.
- **R9:** Ending diagonal फक्त wave 5 किंवा C मध्ये, रचना 3-3-3-3-3.
- **R11:** पूर्ण झालेला pattern जेवढं परवानगी देतो त्याच्या पलीकडे बाजार गेला ⇒ count चुकीचा.

**Correction चे प्रकार:**

| प्रकार | रचना | ओळख | सामान्य जागा | Entry | Invalidation (trade) |
|---|---|---|---|---|---|
| **Zigzag** | 5-3-5 | धारदार. B = A च्या 38–79%. C बहुधा A च्या टोकापलीकडे [guideline, strong]. C = A, नंतर 1.618A, नंतर 0.618A | wave 2, A, Y | **C-end** reversal | C चं टोक; count: impulse origin |
| **Regular flat** | 3-3-5 | B = A च्या 90–105%, C ≈ A चं टोक | wave 4, B | C-end | C चं टोक |
| **Expanded flat** | 3-3-5 | B > 105% A (सहसा 1.236–1.382A). C ≈ 1.618A, A च्या टोकापलीकडे. **B चा नवा extreme हा सगळ्यात मोठा "breakout" सापळा.** | wave 4, B | C-end (A च्या low/high चा sweep सामान्य) | C चं टोक |
| **Running flat** | 3-3-5 | B खूप पलीकडे, C A च्या टोकापर्यंत पोहोचत नाही ⇒ **मजबूत trend** | — | C-end (उथळ) | — |
| **Triangle** | 3-3-3-3-3 | आकुंचन पावणारा, वेळखाऊ, E चा throw-over शक्य | wave 4, B, X (wave 2 कधीच नाही) | **E-end** reversal. B–D line break वर नाही. | C चं टोक |
| **Combination** | W-X-Y | बाजूला, वेळखाऊ. **X आला म्हणजे correction अजून संपलेला नाही.** | wave 4, B | Y-end | — |
| **Ending diagonal** | 3-3-3-3-3 wedge | फक्त 5 किंवा C मध्ये. Legs लहान होत जातात (1 > 3 > 5), overlap. नंतर diagonal च्या सुरुवातीकडे वेगवान reversal [अनुभव] | 5, C | **C मधला diagonal:** तो संपल्यावर reversal candle वर, मोठ्या trend दिशेने (= C-end entry; 7 Oct). **Wave 5 मधला diagonal:** लगेच fade नाही; फक्त S11 (पहिल्या counter leg नंतरचा पहिला retrace). Diagonal च्या दिशेने pullback कधीच विकायचा नाही. | Diagonal चं टोक |

**Family classifier:** B < ~80% A ⇒ zigzag; 90–105% ⇒ regular flat; > 105% ⇒ expanded flat.

**खोली (wave 2 / ABC साठी, फक्त वर्गीकरण):**
- < 38.2% ⇒ मजबूत trend;
- 38.2–61.8 ⇒ सामान्य;
- 61.8–80 ⇒ खोल पण valid (Abhi; तिथे area / sweep हवा);
- 80–100 ⇒ कमकुवत;
- > 100 ⇒ reversal (किंवा आधीची चाल corrective होती).

**Wave personality (tie-breaker):**
- **2:** wave 1 चा बहुतेक भाग पुसतो, invalidation स्पष्ट.
- **3:** मजबूत. आतले pullbacks उथळ ((ii)/(iv) of 3 = Tier A).
- **4:** बाजूला, theta साठी चांगला, पण truncation धोका.
- **5:** कमी जोर, divergence.
- **A:** "फक्त pullback" वाटतो ⇒ entry नाही.
- **B:** "phonies, bull traps". B च्या **आत** entry नाही.
- **C:** wave 3 सारखा जोरदार. **सगळ्यात चांगली entry C च्या शेवटी, जेव्हा गर्दीला वाटतं correction हाच नवा trend आहे.**

**Entry setups (spec):**
- S1 wave-2 end, S3 wave-4 end, **S7 C/Y-end (मुख्य)**, S9 triangle E-end.
- S2 / S4: (ii)/(iv) of 3.
- S6a/S13 (B-end → C, counter-HTF): **default OFF** (Abhi, 2026-10-08).

**बंदी:**
- A-end entry;
- B, triangle किंवा X च्या आत entry;
- wave 5 चा लगेच fade;
- कोणत्याही level/trendline/bar-high च्या break वर entry;
- ending diagonal च्या दिशेने pullback विकणं.

**Invalidation hierarchy:**
1. **Hard inv:** trade degree चा नियम-स्तर. Real break ⇒ तात्काळ exit, त्या count वर re-entry नाही.
2. **Soft stop:** reversal candle चं टोक. Real break ⇒ exit; hard inv अबाधित असेल तर एकदा re-entry चालते.
3. **False break** (wick, किंवा एक कमकुवत close जो पुढच्या bar ने परत घेतला) ⇒ exit नाही.

**वेळ (Neely, तपासलेलं; फक्त score / delay म्हणून, hard invalidation नाही):**
- impulse मध्ये t(w2) > t(w1) **किंवा** t(w4) > t(w3);
- zigzag/flat मध्ये t(c) ≤ t(a) + t(b) (terminal/triangle अपवाद).
- "संपूर्ण correction impulse पेक्षा जास्त वेळ घेतो" हा **नियम नाही** (भाग G).

**विश्वासार्हता.**
- Rules व्याख्येने खरे, पण भाकितासाठीचा पुरावा नाही.
- Fibonacci आणि time ratios: [पुरावा −]. 144 पैकी 15 चाचण्या significant, तर योगायोगाने 14.4 अपेक्षित (Batchelor & Ramyar).
- Automated EW चे "65–83%" आकडे फक्त पूर्ण झालेल्या patterns वर.
- [NIFTY]: Elliott entries त्याच zones मधल्या random entries पेक्षा वेगळ्या निघाल्या नाहीत. Golden चाचणीत आपल्या 5 trades पैकी 0 पकडले.
- **म्हणून Elliott = पुरावा:** बरोबर end ⇒ +10, gray ⇒ 0, A-end / B च्या आत **शक्यता** ⇒ −15. Count स्पष्ट असेल तर A3 चा व्हेटो.
- **सगळ्यात बचाव करता येणारा उपयोग:**
  1. हा पूर्ण correction आहे की फक्त A?
  2. Invalidation (strike/exit संदर्भ).
  3. Reversal candle = NEoWave Stage-1 पुष्टी.

**चुका.**
- Gray count वर trade.
- A-end ला C-end समजणं.
- Expanded flat च्या B ला breakout समजणं.
- X आल्यावर correction संपला असं मानणं.

---

## K4. Areas: buyer/seller (supply/demand), role flip, range edges
**काय.**
- **Demand (supply) zone** = displacement (जोरदार impulse) च्या आधीचा **base**: 1–4 लहान, overlapping candles. तिथे न भरलेल्या orders शिल्लक असतात असं मानलं जातं.
- **Role flip (polarity):** तुटलेला support resistance बनतो, आणि उलट.

**मानसशास्त्र.**
- चाल सुटलेले traders परत किंमत आली की entry घेऊ इच्छितात.
- अडकलेले traders "निदान खरेदी किमतीवर बाहेर" पडू इच्छितात. दोघांच्या orders एकाच किमतीवर येतात.
- Flip मध्ये, जुन्या support वर खरेदी केलेले break नंतर तोट्यात असतात, आणि retest वर विकतात.

**ओळख.**
- **Base:** 1–4 candles, प्रत्येकाचा range ≤ 0.8 MR, bodies ≥ 50% overlap.
  - Zone = [lowest low, highest body-top] (demand; supply उलट).
  - उंची ≤ 1.5 MR.
- **Displacement** (repo `zones.py`): ≥ 2 सलग candles, प्रत्येकाचा body ≥ 0.6 × range आणि range ≥ 1.5 MR; किंवा एकच candle ≥ 2.5 MR. सोबत **आधीचा swing तुटला पाहिजे (BOS).** BOS नाही तर तो noise.
- **Flip level:** आधीचा swing ≥ 0.5 MR close ने तुटला, आणि नंतर दुसऱ्या बाजूने retest आणि rejection (repo `breaks.py` चा failed retest).
- **Freshness:** touches मोजा. पण नुसती संख्या नको; **प्रत्येक test वरची reaction किती जोरदार** होती ते मोजा (खाली विश्वासार्हता पाहा).
- **Range edge:** range चा वरचा आणि खालचा कडा. Range च्या आतले minor swings नाहीत.
- **Zone, line नाही.**

**Pullback वाचनात उपयोग.**
- Impulse ज्या base वरून सुरू झाला तिथेच, किंवा तुटलेल्या swing च्या flip वर, pullback संपणं = textbook continuation.
- Impulse origin zone च्या पलीकडे **close आणि acceptance** = reversal.
- *उदाहरण (bear call):*
  1. Downtrend मधली ABC तेजी तुटलेल्या जुन्या swing low वर (आता resistance) अडते.
  2. तिथे supply base आहे.
  3. Bearish rejection candle येते ⇒ bear call, short call supply zone च्या वर.

**विश्वासार्हता.**
- **[पुरावा +]** Osler (NY Fed, 2000): प्रकाशित FX S/R levels वर bounce 60.8%, random levels वर 56.2%. Edge खरा पण लहान, आणि firms नी दिलेलं "strength" rating निरुपयोगी.
- **[पुरावा +]** Kavajecz & Odders-White (2004): S/R levels order-book मधल्या orders च्या शिखरांशी जुळतात. म्हणजे "areas of resting orders" हा अर्थ बरोबर.
- **[पुरावा +]** Garzarelli et al. (2014), Chung & Bellotti (2021): आधीचे bounces जितके जास्त, तितकी पुढच्या bounce ची शक्यता जास्त (अत्यंत लहान timescale वर), आणि वेळेनुसार level कमकुवत होतो. "Fresh zone सगळ्यात चांगला" हा दावा [अनुभव] असून त्याची चाचणी नाही.
- **[NIFTY] ⚠️ महत्त्वाचं:**
  - आपले कोणतेही level engines random zones पेक्षा चांगले निघाले नाहीत (सगळे |z| < 1.8).
  - Strong zone च्या पलीकडचा strike त्याच अंतरावरच्या random strike इतकाच breach झाला.
  - **अर्थ:** area म्हणजे **कुठे पाहायचं**, संरक्षण नाही. माहिती **area वरच्या reaction** मध्ये असते (टप्पा 4, 6). Strike चं अंतर σ वरून ठरवायचं (K14).

**चुका.**
- Displacement किंवा BOS नसलेल्या प्रत्येक थांब्याला zone म्हणणं.
- Zone फार रुंद (> 1.5 MR) ⇒ R:R बिघडतो.
- Reversal candle शिवाय zone टिकेल असं गृहीत धरणं.
- वरच्या TF ने आधीच पार केलेला zone "fresh" मानणं.

---

## K5. Liquidity, sweep, spring/upthrust, real break वि. false break
**काय.**
- Stop-loss आणि breakout orders स्पष्ट swing highs/lows, equal highs/lows, PDH/PDL आणि round numbers च्या **थोडं पलीकडे** जमा होतात. हा stop pool (liquidity).
- **Sweep** (stop run, false break, Wyckoff spring/upthrust) = तो pool थोडक्यात तोडून **परत आत close.**

**मानसशास्त्र.**
- Stops लागले की ते market orders बनतात. मोठ्या खेळाडूंना fills मिळतात.
- Pool संपला की break दिशेने ढकलणारं कोणी उरत नाही ⇒ किंमत परत फिरते.

**ओळख.**
- **Pool:** confirmed swing high/low, आणि विशेषतः equal highs/lows (≥ 2 pivots, ≤ 0.15 MR अंतरात, ≥ 5 bars अंतराने). PDH/PDL आणि round numbers.
- **Sweep:** bar pool च्या 0.1–1.0 MR पलीकडे जातो पण **आत close** करतो, किंवा पुढचे 1–2 bars आत close करतात. Wick ≥ 50% range असेल तर अधिक मजबूत.
- **Real break (repo `elliott/breaks.py`, एकच अधिकृत व्याख्या):** buffer = **0.25 × MR** पलीकडे close, आणि पुढीलपैकी पहिलं जे होईल ते:
  - (a) **displacement:** break bar range ≥ 1.2 MR, close break दिशेच्या बाहेरच्या 30% मध्ये;
  - (b) **acceptance:** पुढचा bar सुद्धा पलीकडे close (reclaim नाही);
  - (c) **failed retest:** reclaim नंतर तुटलेल्या बाजूने retest, आणि तिथे logical reversal ने rejection ⇒ role flip confirmed.

  नाहीतर **false break: exit नाही, invalidation नाही.**
- **Magnet:** दिवसात ≥ 4 वेळा close ने आरपार झालेला level ⇒ no-trade level.
- Sweep हे फक्त reclaim close झाल्यावरच कळतं (no-lookahead).

**Pullback वाचनात उपयोग.**
- सगळ्यात चांगले pullback endings बहुधा **A चा low (किंवा आतला एखादा low) sweep करून reclaim** करतात. Expanded flat मध्ये C, A च्या पलीकडे जातोच. हा correction मधला spring.
- *उदाहरण (bull put):*
  1. Uptrend; A low 25,010.
  2. C, 24,992 पर्यंत खाली जातो (0.4 MR पलीकडे; 25,000 round number सुद्धा तिथेच).
  3. Bar 25,018 वर लांब lower wick सह close होतो.
  4. पुढचा bar bullish ⇒ bull put.
- **Reversal इशारा:** sweep impulse origin (100%) च्या पलीकडे होऊन तिथे **acceptance** झाली ⇒ trend बदलला. हा pullback नाही.

**विश्वासार्हता.**
- **[पुरावा +]** Osler (2003, 2005): stop-loss orders round numbers च्या थोडं पलीकडे, take-profit orders round numbers **वर** जमा होतात. Stop cluster गाठला की किंमत वेगाने पुढे जाते (cascade); take-profit cluster वर उलटते. परिणाम **तासांचा**, दिवसांचा नाही.
- म्हणून sweep-and-reclaim महत्त्वाचा आहे, **कारण cascade अपयशी ठरला.** प्रत्येक poke परत फिरेल असं नाही.
- Spring/upthrust, "liquidity grab": [अनुभव], hit-rate अभ्यास नाही.
- **[पुरावा, practitioner dataset: Bulkowski]** Breakout नंतर ~66–69% patterns परत breakout level पर्यंत येतात ⇒ breakout bar वर entry नको, हा नियम योग्य.

**चुका.**
- प्रत्येक wick ला sweep म्हणणं (reclaim close शिवाय).
- Sweep bar बंद होण्याआधी entry.
- 2+ closes पलीकडे म्हणजे acceptance: आता stops हे इंधन आहे, सापळा नाही.
- स्वतःचा short strike नेमका स्पष्ट pool वर ठेवणं.

---

## K6. Trendlines आणि channels: horizontal की तिरका?
**काय.**
- **Trendline:** ≥ 2 pivots जोडणारी रेषा (uptrend मध्ये lows, downtrend मध्ये highs). **Channel:** विरुद्ध टोकातून समांतर रेषा.
- **Elliott channeling:**
  - wave 4 अनेकदा wave 2 मधून काढलेल्या समांतर रेषेजवळ संपतो;
  - **zigzag चा C**, A च्या सुरुवात आणि B च्या टोकाला जोडणाऱ्या रेषेला A च्या टोकातून काढलेल्या समांतर रेषेजवळ संपतो;
  - शेवटच्या wave मध्ये **throw-over:** channel पलीकडे थोडं जाऊन परत आत close.

**मानसशास्त्र.**
- Uptrend मध्ये dip buyers वाढत्या दराने खरेदी करतात. Slope दाखवतो की वरचढ बाजू किती घाईत आहे.
- Slope तुटणं म्हणजे घाई संपली, reversal झालंच असं नाही.

**ओळख.**
- **6.1 बांधणी:**
  - Confirmed pivots (k = 2–3).
  - **Valid line ≥ 3 touches:** 2 anchors, आणि 3रा touch पुष्टी देतो. Touch = pivot चं टोक रेषेपासून ±0.2 MR मध्ये.
  - Anchors च्या मधे कोणताही **close** रेषेपलीकडे > 0.3 MR नाही.
  - **Anchor wicks वर, break चा निर्णय closes वर.**
  - Touches एकमेकांपासून ≥ 6–8 bars दूर. Slope मध्यम: प्रति bar > 0.5 MR इतकी तीव्र रेषा reject.
- **6.2 Channel:** anchors च्या मधल्या सगळ्यात टोकाच्या opposite pivot मधून समांतर रेषा. 15M वर रुंदी साधारण 2–6 MR.
- **6.3 Correction चा स्वतःचा channel:** A ची सुरुवात आणि B चं टोक जोडा; A च्या टोकातून समांतर रेषा. C चं लक्ष्य = C जिथे ही रेषा गाठतो. C = A सोबत confluence.
- **6.4 Horizontal की तिरका: ताज्या price action वरून निवड.** प्रत्येक candidate ला गुण:
  - (a) शेवटच्या ~2 sessions मधले touches;
  - (b) शेवटची reaction किती ताजी;
  - (c) reaction ची ताकद (3 bars मध्ये किती MR दूर गेली).

  निर्णय:
  - ताजे pivots slope वर ओळीत येत असतील आणि horizontal levels कापले जात असतील ⇒ बाजार **slope** ला मान देतोय.
  - एकाच किमतीवर वारंवार reactions ⇒ **horizontal.**
  - **दोन्ही ≤ 0.5 MR मध्ये भेटत असतील ⇒ तो छेदबिंदू सगळ्यात उच्च दर्जाचा area** (7 Oct चं उदाहरण).
- **6.5 Break वि. false break:**
  - Real = K5 ची एकच व्याख्या (`elliott/breaks.py`: 0.25 MR buffer + displacement / acceptance / failed retest), किंवा structure बदल (LH/HL).
  - False = 1–2 bars मध्ये परत आत close (throw-over / sweep).
  - **Pullback दरम्यान minor impulse line तुटणं अपेक्षितच आहे.** त्याला reversal मानायचं नाही.
  - **Correction च्या channel चा impulse दिशेने break**, reversal candle नंतर = pullback संपल्याची अतिरिक्त पुष्टी.

**Pullback वाचनात उपयोग (7 Oct 2026, NIFTY 15M, golden उदाहरण).**
1. उतरती trendline: 28 Sep ~22,850 → 30 Sep ~22,801 → 7 Oct ~22,715 (3रा touch).
2. सोबत 6 Oct चा horizontal top 22,700–22,730.
3. ABC तेजीचा C-end, ending diagonal सारखा.
4. Gap fill PDC पर्यंत.
5. ⇒ छेदबिंदू area, 15M bearish reversal ⇒ bear call. 8 Oct ला 22,217. (Illustration only; ही तारीख contaminated.)

**विश्वासार्हता.**
- **[पुरावा, practitioner dataset: Bulkowski]** 3,172 uptrend lines: 3rd touch वर bounce trade ⇒ फक्त 37% win. **4+ touches, लांब कालावधी, सौम्य slope आणि दूरदूरचे touches** असलेल्या रेषा चांगल्या.
  - ⇒ **एकटी trendline entry नाही.** Area confluence आणि reversal candle हवी.
- Lo, Mamaysky & Wang (2000): patterns code करता येतात आणि त्यांत थोडी माहिती असते, पण trendlines/channels स्वतः तपासले नाहीत.
- Elliott channel targets आणि throw-over: [अनुभव].
- Repo SILVER audit: OOS मध्ये trendline control पेक्षा कमकुवत [NIFTY नाही, SILVER].

**चुका.**
- एका ठिकाणी bodies आणि दुसरीकडे wicks वरून रेषा.
- प्रत्येक bar नंतर रेषा पुन्हा काढणं (curve-fitting).
- फक्त 2 touches.
- खूप तीव्र रेषा.
- Pullback मध्ये impulse line तुटली म्हणजे reversal समजणं.
- **फक्त horizontal पाहून trendline विसरणं (7 Oct ची चूक).**

---

## K7. Fibonacci: मोजपट्टी आणि confluence फक्त (Abhi चा नियम)
**Abhi चं तत्त्व (2026-10-08):**
- Reversal बहुधा 50%, अनेकदा 61.8% (golden ratio), तर कधी 78.6–80% पर्यंत खोल जाऊन येतो.
- **त्यामागचं मानसशास्त्र:** त्या level वर **आधीचा demand (किंवा supply) area** असतो, म्हणून तिथून reversal येतो.
- म्हणून Fibonacci level तेव्हाच valid जेव्हा तिथे खरा buyer/seller area किंवा liquidity असेल, आणि हे **cross-verify** करायचं.
- Fibonacci हे साधन आणि मोजपट्टी आहे, subjective. Buyer area, seller area आणि liquidity ठोस आहेत. Fibonacci त्यांच्यासोबत **पूरक (confluence)** म्हणून.

**ओळख.**
- Anchor फक्त **confirmed pivots** वर, आणि अशा impulse वर जो ≥ 4 MR लांब असून structure तोडलेला आहे. नवा extreme आला की पुन्हा मोजा. Noise वर Fibonacci नाही.
- प्रत्येक level म्हणजे **band ± 0.25 MR**, line नाही.
- **Validity gate:** Fibonacci band ला गुण **फक्त तेव्हा** जेव्हा तो K4 (zone/flip/base), K5 (liquidity), K6 (trendline/channel) किंवा K8 (round number/PDH-PDL) शी overlap करतो. **एकटा Fibonacci = 0 गुण.**
- **Measured move:**
  - C ≈ A (±15%), structure zone मध्ये ⇒ completion confluence.
  - C ≥ 1.618A ⇒ correction मोठा/गुंतागुंतीचा होतोय, किंवा reversal चा संशय.
- **खोली = regime माहिती:**
  - ≤ 38.2% ⇒ मजबूत trend;
  - 50–61.8% ⇒ सामान्य;
  - 61.8–80% ⇒ खोल पण valid (Abhi), तिथे ठोस area / sweep हवा;
  - 80–100% ⇒ कमकुवत trend;
  - > 100% ⇒ pullback नाही.

**उदाहरण (bear call).**
1. NIFTY 25,300 → 25,000 घसरण (~7 MR).
2. ABC तेजी: A = 25,000 → 25,130, B = 25,070. C = A ⇒ 25,200. 61.8% = 25,185.
3. दोन्ही 25,180–25,210 supply base आणि 25,200 round number शी जुळतात.
4. Bearish engulfing 25,180 खाली close ⇒ bear call 25,250 च्या वर.
5. पर्यायी परिस्थिती:
   - तेजी area नसताना 78.6% (~25,236) पार करून बंद झाली ⇒ grade कमी.
   - 25,300 (100%) पार ⇒ reversal, trade नाही.

**विश्वासार्हता (पुरावा Abhi च्या तत्त्वाशी सुसंगत आहे).**
- **[पुरावा −]** Tsinaslanidis et al. (2022): Fibonacci zones मध्ये bounce होतो, पण इतर zones पेक्षा **सांख्यिकीदृष्ट्या वेगळा नाही.**
- **[पुरावा −, practitioner]** ~40,000 FX corrections: correction खोलीचं वितरण गुळगुळीत, Fibonacci ratios वर शिखरं नाहीत (practitioner अभ्यास).
- **[पुरावा −, practitioner]** Bulkowski (2020): "lab मध्ये उत्तर नाही."
- **[पुरावा −]** Batchelor & Ramyar (DJIA): योगायोगाइतकेच.
- 50% हा Fibonacci ratio सुद्धा नाही.
- ⇒ Ratio मध्ये विशेष काही नाही. भाकीत-शक्ती त्याच ठिकाणच्या structure आणि liquidity मधून येते, हा [अनुमान] (Abhi चं तत्त्व).

**चुका.**
- अपुष्ट pivots वर anchor.
- जुळेल असा anchor शोधत बसणं.
- 61.8 ला रेषा मानणं.
- फक्त Fibonacci लागला म्हणून entry.
- 100% invalidation विसरणं.
- Corrective (overlapping) leg वर Fibonacci काढणं.

---

## K8. Round numbers, PDH/PDL/PDC, आठवड्याचे H/L
**काय.**
- NIFTY चे 100 (वजन 1), 500 (वजन 2), 1000 (वजन 3) levels.
- आधीच्या दिवसाचा high / low / close, आधीच्या आठवड्याचा high/low, दिवसाचा open.

**मानसशास्त्र.**
- Limit आणि take-profit orders, आणि option strikes, गोल आकड्यांवर जमतात (anchoring).
- Stops थोडे पलीकडे ठेवले जातात.

**ओळख.**
- प्रत्येक level band ±0.2–0.3 MR. फक्त पूर्ण झालेल्या sessions वरून (no-lookahead).
- Osler नुसार: **गोल आकड्यावर किंवा थोडं आधी reversal candle = take-profit absorption.** ≥ 0.5 MR पलीकडे close = cascade धोका.
- PDH/PDL हे liquidity pools (K5) आणि flip levels (K4) सुद्धा.

**उपयोग.** Round number + zone + sweep एकत्र (उदा. C, 24,990 पर्यंत जाऊन 25,000 आणि PDL sweep करतो, आणि reclaim) = उच्च confluence. Short strike गोल आकड्यापलीकडे + ≥ 1 MR buffer, गोल strike वर नाही.

**विश्वासार्हता.**
- FX आणि US stocks मध्ये [पुरावा +] (Osler; Bhattacharya, Holden & Jacobsen 2012).
- Stock indices मध्ये **मिश्र.**
- NIFTY-विशिष्ट अभ्यास नाही ⇒ [अनुभव]. PDH/PDL: [अनुभव].
- Repo T3: OE zones (ज्यांच्या स्रोतांत KEY levels सुद्धा आहेत) random पेक्षा वेगळे नाहीत [NIFTY].
- ⇒ **कमी वजन, फक्त confluence म्हणून.**

**चुका.**
- प्रत्येक 50-pt level ला major मानणं.
- Acceptance (2+ closes) नंतरही गोल आकडा fade करणं.
- Strike नेमका गोल strike वर.

---

## K9. Candle psychology आणि logical reversal
**चार किमती, चार प्रश्न.**
- **Open:** लढाई कुठून सुरू झाली. 15M intraday वर तो बहुधा आधीचा close असतो, म्हणून कमी माहिती देतो. 09:15 चा gap मात्र खरी माहिती.
- **High / Low:** buyers आणि sellers चा कमाल धक्का.
- **Close:** **निकाल**, सगळ्यात महत्त्वाची किंमत.
- **Body** |C − O| = निव्वळ प्रगती. मोठी body = एका बाजूचं नियंत्रण.
- **Upper wick** = वरच्या किमती नाकारल्या. **Lower wick** = खालच्या किमती नाकारल्या (absorption शक्य).
- **Range** = तीव्रता, फक्त MR च्या तुलनेत अर्थपूर्ण.
- **Close location CL = (C − L) / (H − L):** 0 = sellers चा पूर्ण विजय, 1 = buyers चा, 0.5 = बरोबरी.
- **मूळ सूत्र:** "टोकांवर कोणाचं नियंत्रण होतं, आणि close वर कोणाचं?"

**Reversal ची सार्वत्रिक 3-पायरी कथा:**
1. Trend candle उशिरा येणाऱ्यांना आकर्षित करते.
2. Extension नाकारलं जातं (probe → rejection).
3. विरुद्ध बाजू trend candle च्या body मध्ये खोल, किंवा पलीकडे, close करते ⇒ उशिरा आलेले अडकतात.

पायरी 3 नसलेले patterns (harami, matching low, homing pigeon) data मध्ये कमकुवत आहेत.

**Composite logical reversal (repo `elliott/reversal.py`, अधिकृत व्याख्या):**
- **Composite:** 1–3 candles एकत्र: पहिला open, max high, min low, शेवटचा close. Hammer (1), engulfing (2) आणि star (3) यांना एकच logic: "ढकललं, मग दुसऱ्या बाजूने ताबा घेतला".
- **Touch:** area ला touch (MR tolerance; repo सध्या 0.5 × ATR14). Invalidation पलीकडे close नाही.
- **Reclaim:** composite चा close सगळ्यात खोल touched level च्या पलीकडे, परत आत.
- **Last:** N ≥ 2 असेल तर शेवटची candle trade दिशेने बंद.
- **Strength:** range / MR. 1.2–2.5 सामान्य.
  - < 1.2 ⇒ कमकुवत (गुण कमी).
  - > 2.5 आणि CL < 0.6 ⇒ climax / extension (वजा).
  - > 2.5 आणि reclaim + CL ≥ 0.6 ⇒ absorption, दंड नाही (G-E0).
- **Indecision:** CL 0.40–0.60 ⇒ पुढच्या bar ची वाट (follow-through: पुढचा close trade दिशेने).
- **Score s (0–1):** wick 0.3, CL 0.3, body 0.2, time 0.2. ⇒ grade मधले गुण **RV = 50 × (s − 0.30)**, मर्यादा −10…+25.
- **T7 no-breakout:** composite close हा correction च्या शेवटच्या sub-leg origin च्या पलीकडे नसावा.
- Pattern नावं फक्त log आणि narrative मध्ये.

**Patterns (Bulkowski, US daily, फक्त संदर्भ):**
- **Single candles ≈ नाणेफेक:** hammer 60%, doji 50–52%.
- **उलट अर्थाचे:**
  - hanging man = 59% bullish **continuation**;
  - inverted hammer = 65% bearish **continuation**;
  - marubozu = continuation.
- **Multi-candle (मजबूत):** bearish engulfing 79%, morning star 78%, evening star 72%, three outside up 75%, piercing 64%, bullish engulfing 63%.
- **Harami कुटुंब:** 53–57%, बहुतेक continuation ⇒ reversal म्हणून नाही.
- **Three white soldiers / black crows:** momentum (breakout धोका), entry trigger नाही.

**विश्वासार्हता.**
- [पुरावा −] बहुतेक peer-reviewed अभ्यास: एकट्या candle patterns ला भाकित-शक्ती नाही (Marshall et al. 2006; Duvinage 2013: costs नंतर 83 पैकी फक्त 3–5 significant, कोणताही buy-and-hold पेक्षा चांगला नाही).
- [पुरावा +, मर्यादित] Caginalp & Laurent (1998): योग्य trend मध्ये, ~2 दिवस hold केल्यावर, net 0.56–0.76%.
- **Context महत्त्वाचा:** मुख्य trend मधल्या pullback च्या शेवटी, level वर, पुष्टीसह, आणि 2–3 दिवसांच्या hold सह, patterns चांगले काम करतात. Oscillator filters ने फायदा नाही.
- [NIFTY] Candle merge: 11 candle variants पैकी कोणताही generic पेक्षा वेगळा निघाला नाही (PBO 0.62). निर्णय "अजून मोजता येत नाही", "edge नाही" नाही.

**उपयोग.**
- **फक्त आधी ओळखलेल्या area वर** शेवटच्या 1–3 बंद candles एकत्र वाचायच्या: कोण अडकलं? नावं विसरा.
- **Exit बाजू:** एकटी विरुद्ध candle कधीच exit नाही. Exit फक्त real break वर (K5).

---

## K10. Momentum आणि ताकद: price, RSI divergence आणि futures volume
### K10.1 Price-only ताकद
**प्रत्येक leg वर मोजायचं:**
- **Speed** = leg (MR) / bars.
- **Overlap ratio:** मागच्या bar शी > 50% overlap असलेल्या bars चं प्रमाण. Impulse < 0.4, correction > 0.6.
- **Directional closes:** leg दिशेने CL ≥ 0.6 असलेल्या candles चं प्रमाण. Impulse ≥ 0.6, healthy pullback ≤ 0.5.

**Trend थकण्याची चिन्हं (trend आणि correction दोघांसाठी):**
- **Shrinking legs:** प्रत्येक trend दिशेचा leg आधीच्या पेक्षा लहान (ratio < 0.8, सलग दोनदा).
- **Expanding pullbacks:** pullback n > pullback n−1 × 1.3.
- **Failed extension:** आधीच्या टोकापलीकडे < 0.5 MR जाऊन 2 bars मध्ये परत आत close.
- **Wedge / ending diagonal रचना** (K3, K11).
- **Wick rejection:** pullback च्या टोकावर विरुद्ध wick ≥ 0.5 range आणि ≥ 0.6 MR.

**Correction संपतोय याची चिन्हं:**
- C च्या आतले legs लहान;
- spreads आकुंचन;
- closes टोकापासून दूर (rising CL);
- A च्या टोकाचा sweep आणि reclaim;
- विरुद्ध दिशेची पहिली मजबूत candle.

**विश्वासार्हता.**
- "Pullback संथ असतो": [अनुभव]. **NIFTY वर कमकुवत** (K2 ⚠️).
- Momentum persistence: [पुरावा +] (सामान्य).
- ⇒ हे गुण scoring features आहेत, नियम नाहीत. NIFTY data वर तपासायचे.

### K10.2 RSI(14) divergence: मंजूर असलेलं **एकमेव indicator**, फक्त पुरावा म्हणून
**काय.**
- **Regular bullish:** price lower low, RSI higher low ⇒ ताकद कमी होतेय (थकवा). Bearish उलट.
- **Hidden bullish:** price **higher** low, RSI lower low ⇒ trend continuation. Pullback ने oscillator ला जास्त ढकललं, पण price structure तुटलं नाही. [अनुभव: Cardwell / Brown]
- **Range shift:** uptrend मध्ये RSI साधारण 40–80, downtrend मध्ये 20–60 [अनुभव].

**ओळख (no-lookahead).**
1. Price चे confirmed pivots. RSI ची किंमत **त्याच price pivot bar वर** घ्यायची (वेगळे RSI pivots नाहीत).
2. आधीच्या त्याच प्रकारच्या pivot शी तुलना, 8–60 bars मागे.
3. Price फरक ≥ 0.25 MR; RSI फरक ≥ 3 points; मधल्या bars ने रेषा तोडलेली नसावी.
4. Location:
   - regular bullish फक्त पहिल्या low चा RSI ≤ 30 असेल तर (bearish साठी ≥ 70);
   - hidden bullish फक्त trend up असेल आणि pullback चा RSI ≥ 35–40 असेल तर.
5. Pivot + k bar नंतरच वापरायचं.

**उपयोग.**
- **C-end मध्ये regular divergence** (C, A पेक्षा lower low, RSI higher low) ⇒ correction थकतोय. **आदर्श पुरावा.**
- **Pullback मध्ये hidden divergence** ⇒ continuation पुरावा.
- **Impulse च्या शेवटच्या high वर regular bearish divergence** ⇒ पुढचा pullback reversal असू शकतो ⇒ जास्त पुष्टी हवी.
- **गुण:** लहान (+3…+5). कधीच एकट्याने निर्णय नाही.

**विश्वासार्हता.**
- **[पुरावा −/कमकुवत]** Bulkowski (994 stocks, 19,294 नमुने): फक्त bull market मधला bullish divergence index पेक्षा चांगला (win 50–55%; 1995 पासून मोजल्यास 45–48%). "Fails more often than it works." 30–70 च्या आत सुरू होणारे divergences दुर्लक्षित करा.
- Hidden divergence चा कठोर अभ्यास नाही.
- **Divergence 2–3 वेळा सलग येऊ शकतो** (मजबूत trend मध्ये). Trend विरुद्ध trade फक्त divergence वरून कधीच नाही.

### K10.3 Volume: NIFTY futures वरून (Abhi, 2026-10-08)
**Abhi चं निरीक्षण:** pullback मध्ये volume कमी असतो. NIFTY index ला volume नसतो, पण **NIFTY futures चा volume** घेता येतो.

**मानसशास्त्र.**
- Impulse मध्ये मोठे खेळाडू आणि घाईचे orders असतात, म्हणून volume जास्त.
- Pullback मध्ये फक्त profit-taking आणि थोडे counter-trend traders असतात, म्हणून volume कमी. Supply/demand "सुकतो" (Wyckoff: LPS ची खूण).
- Pullback मध्ये volume **वाढत** असेल तर विरुद्ध बाजू खरंच ताकदीने येतेय, म्हणजे reversal धोका.
- C-end ला एक **volume spike, पण किंमत पुढे जात नाही** (effort खूप, result कमी) = absorption. Correction संपण्याची खूण.

**ओळख (code साठी).**
- **स्रोत:** near-month NIFTY futures चे 5M candles (repo `collect_index_futures_volume.py`, रोज VPS वर). 15M साठी 3 candles ची बेरीज.
- **Roll:** expiry जवळ volume पुढच्या महिन्याकडे सरकतो. ज्या दिवशी पुढच्या contract चा volume जास्त होतो त्या दिवसापासून त्याचा वापर (continuous series). Roll च्या दिवसांची तुलना टाळायची.
- **वेळेनुसार normalise (आवश्यक):** NSE वर volume U-आकाराचा आहे (K14). म्हणून volume ची तुलना **त्याच वेळेच्या slot च्या median** शी (उदा. 10:15 चा bar मागच्या 20 दिवसांच्या 10:15 bars शी). याला `rel_vol` म्हणू.
- **मोजमापं:**
  - **Pullback dry-up:** pullback च्या bars चा सरासरी `rel_vol` ÷ impulse च्या bars चा सरासरी `rel_vol`. < 0.8 ⇒ healthy; > 1.0 ⇒ धोक्याचा.
  - **C मध्ये घटता volume:** C चा `rel_vol` A पेक्षा कमी ⇒ थकवा.
  - **Absorption spike:** area वर `rel_vol` ≥ 1.5, पण निव्वळ प्रगती ≤ 0.3 MR आणि close परत आत ⇒ correction संपण्याचा पुरावा.
  - **Reversal candle चा volume:** reversal candle (impulse दिशेने) चा `rel_vol` ≥ 1.2 ⇒ पुष्टी अधिक मजबूत.
- **Data नसेल तर** (gap, contract बदल, collector चुकला) ⇒ volume पुरावा 0. Trade अडवायचा नाही.

**उपयोग.**
- Healthy pullback = कमी volume + overlap + 3 waves. Dangerous = वाढता volume + displacement.
- 7 Oct सारखा setup: gap fill ची तेजी कमी volume ने, आणि trendline वर bearish candle जास्त volume ने ⇒ मजबूत.

**विश्वासार्हता.**
- "Pullback मध्ये volume कमी, impulse मध्ये जास्त": Wyckoff, Dow आणि practitioners मध्ये सर्वमान्य [अनुभव]. कठोर अभ्यास मर्यादित.
- Volume U-shape (NSE): [पुरावा +]. म्हणून slot-normalisation अनिवार्य.
- **[NIFTY] मर्यादा:** expired futures चा जुना volume Upstox Plus शिवाय मिळत नाही (HTTP 401). Collector काही आठवड्यांपासूनच data गोळा करतोय, आणि तो सगळा holdout / contaminated काळातला आहे. **म्हणून IS/VAL backtest मध्ये volume तपासता येणार नाही.** त्याचं मूल्य फक्त live PAPER scorecard मधून कळेल. सुरुवातीला गुण लहान.

---

## K11. Chart patterns: **वाचनासाठी**, breakout entry साठी कधीच नाही
| Pattern | अर्थ | Pullback वि. reversal वाचन |
|---|---|---|
| **Flag / pennant** | Pole नंतर लहान counter consolidation | **Pullback.** Bull flag = impulse चा ABC/triangle correction. Entry flag च्या खालच्या कडेवर reversal ने, flag breakout वर नाही. |
| **Triangle** | आकुंचन पावणारे swings | Trend च्या मधे continuation (wave 4/B). लांब चालीनंतर शेवटचा consolidation असू शकतो. |
| **Rising wedge (uptrend मध्ये) / falling wedge (downtrend मध्ये)** | Trend दिशेची overlapping, आकुंचन पावणारी चाल | **Trend थकतोय** (ending diagonal वर्तन). उलट दिशेचा wedge (uptrend मधला falling wedge) = pullback. |
| **Double top / bottom** | आधीचं टोक ओलांडता आलं नाही | **Reversal इशारा**, पण neckline (मधला low) तुटल्यावरच. |
| **Head & shoulders** | Marginal HH (head), मग LH (right shoulder) | Dow reversal क्रम. Right shoulder = पहिला LH. |

**ओळख (confirmed pivots).**
- **Flag:** pole ≥ 6 MR, ≤ 12 bars. Consolidation ≤ 0.5 pole, 4–20 bars, pole विरुद्ध उतार.
- **Double top:** दोन highs ≤ 0.5 MR अंतरात, ≥ 8 bars दूर, मधला trough ≥ 2 MR खाली. Trough खाली close झाल्यावरच confirmed.
- **H&S:** मधला high खांद्यांपेक्षा ≥ 0.5 MR वर, खांदे ≤ 1.5 MR अंतरात, neckline close ने तुटल्यावरच.
- **Wedge:** प्रत्येक रेषेवर ≥ 3 pivots, एकाच दिशेने उतार, एकमेकांकडे येणाऱ्या रेषा. प्रत्येक trend leg आधीच्या पेक्षा लहान.

**उपयोग.**
- "Pullback low" हा double top चा दुसरा trough असेल (impulse ला 0.5 MR पेक्षा जास्त HH करता आला नाही) ⇒ reversal धोका, grade कमी.
- Impulse स्वतःच rising wedge असेल ⇒ पुढचा pullback reversal असू शकतो.

**विश्वासार्हता.**
- **[पुरावा, Bulkowski]**
  - H&S top: 19% failure; 68% वेळा breakout level पर्यंत परत.
  - Pennants: 54% failure; target फक्त ~30% वेळा.
  - Rising wedge: 60% खाली तुटतो; downward break failure 51%, bust rate 63%.
  - Busted patterns: 24–40%.
- **[पुरावा +/मिश्र]** Lo-Mamaysky-Wang (2000): माहिती आहे, पण नफा सिद्ध नाही. Savin et al. (2007): H&S नंतर underperformance, पण एकट्याने short फायदेशीर नाही.
- ⇒ **Context filter म्हणून चांगले, trigger म्हणून नाहीत.**

**चुका.**
- Neckline तुटण्याआधी pattern नाव देणं.
- 0.3 MR उंचीचा "double top" (हा noise).
- गोष्टीला जुळेल अशा रेषा काढणं.

---

## K12. Wyckoff (volume शिवाय, NIFTY index साठी)
**काय.**
- Accumulation / distribution चे टप्पे:
  - A: trend थांबणं;
  - B: range;
  - C: **spring** (खाली) किंवा **upthrust (UTAD)** (वर);
  - D: SOS / SOW, आणि मग **LPS / LPSY** (last point of support / supply);
  - E: markup / markdown.
- **Spring** = range support च्या खाली थोडक्यात जाऊन लगेच परत. **Test** = spring area ला पुन्हा भेट, पण कमी spread आणि low टिकतो.
- **Effort वि. result:** खूप प्रयत्न (spread) आणि कमी निकाल (प्रगती) = **absorption.**
- **LPS = आपला pullback end** [अनुमान].

**Volume नसताना (index):**
- Effort = **spread** (range / MR); result = **निव्वळ प्रगती** |C − O| / range; **CL**.
- **Absorption:** level मध्ये ढकलणाऱ्या ≥ 2 रुंद (≥ 1.5 MR) candles, पण close परत आत (CL ढकलण्याच्या विरुद्ध), आणि level पलीकडे ≤ 0.3 MR प्रगती.
- **प्राधान्य:** NIFTY futures चा खरा volume (K10.3). तो नसेल तेव्हाच वरचे price-only proxies.

**उपयोग.**
- C-wave चा शेवट LPS / test सारखा दिसायला हवा: spreads आकुंचन, closes टोकापासून दूर (CL वाढतोय), A च्या low चा लहान sweep आणि लगेच reclaim (mini-spring).
- **उलट:** C रुंद spreads सह, closes तळाशी, reclaim नाही ⇒ हा absorption नाही, supply आहे ⇒ संभाव्य SOW (reversal).

**विश्वासार्हता.**
- Wyckoff schematics ची peer-reviewed चाचणी नाही [अनुभव].
- "Stop run, मग reclaim" ला Osler च्या stop-cluster पुराव्याचा अप्रत्यक्ष आधार.

**चुका.**
- प्रत्येक range ला नंतर accumulation म्हणणं (आधी SOS हवा).
- टिकलेल्या breakdown ला spring म्हणणं.
- 15M वर पूर्ण schematic जबरदस्तीने बसवणं.

---

## K13. Gaps
**वर्गीकरण (09:15–09:30), आकार ATR14 (daily) च्या पटीत, % मध्ये नाही:**
- **G0** noise;
- **G1** trend विरुद्ध, range च्या आत;
- **G2** trend सोबत, range च्या आत;
- **G3** trend सोबत, PDH/PDL च्या पलीकडे;
- **G4** trend विरुद्ध, पलीकडे;
- **G5** stretched;
- **GX** trend अस्पष्ट, inside किंवा beyond;
- **E** event.

**खरा निर्णय** पहिल्या 2–6 bars (15M) मधल्या **acceptance वि. rejection** मधून, आणि तो प्रत्येक bar वर पुन्हा ठरवायचा (open-test-drive = acceptance).

**तथ्यं.**
- मोठा gap ⇒ fill ची शक्यता कमी.
- NIFTY वर ≥ 0.30% gaps त्याच दिवशी PDC ला touch: 47% (IS) / 43% (VAL) [NIFTY].
- **Options pre-open auction मध्ये नसतात** ⇒ gap पासून संरक्षण फक्त strike अंतर, width आणि size ने.
- NIFTY ची बहुतेक वाढ overnight झाली आहे (descriptive).

**Setups (pullback-only):**
- **A:** trend विरुद्ध gap अपयशी ⇒ trend दिशेने reversal.
- **B:** trend सोबत मोठा gap ⇒ पहिल्या pullback ची वाट (gap edge / PDC). Pullback नाही तर trade नाही.
- **C:** जुन्या न भरलेल्या gap ची कड (कमकुवत, confluence फक्त).
- **D:** exhaustion fade, **OFF.**
- **नाकारलेले:** gap-and-go, ORB, पहिल्या candle चा break, FVG entries.

**गोष्ट म्हणून वाचन (Abhi, 7 Oct):** आदल्या दिवशीची **कमकुवत तेजी + आज gap down = कमजोरीची पुष्टी.** मग gap भरण्यासाठीची तेजी ही sellers ची दुसरी संधी.

**उघड्या spread विरुद्ध gap:**
- opening print वर exit नाही;
- acceptance ⇒ exit;
- open वरच short strike पलीकडे ⇒ emergency exit.

**विश्वासार्हता.** बहुतेक US/practitioner आकडे. NIFTY पुरावा कमकुवत; framework अजून तपासलेला नाही.

---

## K14. Session, expiry, VIX, theta आणि strike अंतर
**Session (U-shape: [पुरावा +]; bot साठीचे निष्कर्ष: [अनुमान]).**
- NSE वर volatility आणि volume U-आकारात: सकाळी आणि शेवटी जास्त, मध्ये कमी (Sampath & Gopalaswamy 2020).
- NIFTY futures वर **11:00–12:00 सर्वात शांत** (Singh & Gangwar 2018).
- ⇒ 09:15–09:45 मधला signal कमी विश्वासार्ह; पुढच्या candle ची पुष्टी हवी. Opening candles नैसर्गिकरीत्या रुंद असतात, म्हणून शक्य असल्यास MR वेळेनुसार (time-of-day) काढायचा.
- दुपारची (11:00–13:30) "पूर्ण झालेली" pullback, आकुंचन पावणाऱ्या candles सह, हा कमकुवत पुरावा.

**Overnight [पुरावा +].**
- Bhat, Pandey & Rao (2024): NIFTY options च्या **short positions चा फायदा मुख्यतः overnight** मिळतो; intraday नकारात्मक किंवा शून्य.
- ⇒ **दुपारी entry आणि रात्र hold** हे ~2 दिवसांच्या शैलीशी जुळतं. Overnight gap हीच त्या premium ची किंमत; width आणि size gap गृहीत धरून.

**Expiry [पुरावा + / नियम].**
- Expiry दिवशी volume आणि volatility जास्त. "Max pain" चा भारतीय पुरावा नाही.
- SEBI interim order (Jane Street, 2025, **आरोप**, BANKNIFTY घटक, 18 दिवस): expiry दिवशी सकाळची चाल दुपारनंतर उलटण्याचा pattern [अनुमान: त्यामुळे] ⇒ **मंगळवार सकाळचा "trend" पुरावा कमी वजनाचा.**
- **SEBI नियम:**
  - प्रति exchange एकच weekly index (NIFTY मंगळवार, SENSEX गुरुवार);
  - NIFTY lot 65;
  - expiry दिवशी short options वर +2% ELM;
  - expiry दिवशी calendar spread margin लाभ नाही.
- ⇒ 60–80% मिळाल्यावर सोमवार close किंवा मंगळवार सकाळपर्यंत exit (exit settings Abhi चे).

**Theta आणि room [पुरावा / सिद्धांत].**
- ATM premium √T ने झिजतो. **OTM premium expiry जवळ टक्केवारीत जास्त वेगाने झिजतो** ⇒ 2 दिवसांत 60–80% हे वास्तववादी.
- **Expected move (1σ)** = spot × IV × √(दिवस/365). उदा. NIFTY 25,000, VIX 13 ⇒ 1 दिवस ~±170, 2 दिवस ~±240.
- Short strike 1σ ⇒ ITM ची शक्यता ~16%; 1.5σ ⇒ ~7%. **Touch ची शक्यता ≈ 2×.**
- **[NIFTY] Strike breach model:** breach धोका जवळजवळ पूर्णपणे **σ-अंतरावर** अवलंबून. Level मुळे फरक पडत नाही.
- ⇒ Strike = invalidation च्या पलीकडे **आणि** पुरेसं σ-अंतर (spec चं सूत्र: max(|spot − inv| + 0.5 MR, k × spot × IV × √(dte_frac/252)). Breach model चा realised σ20 × √(DTE+1) तपासणीसाठी).
- Put बाजूला +0.1–0.2 z cushion (VAL निरीक्षण).

**VIX ("आकार, दिशा नाही" आणि range आकडे: [पुरावा +]; pullback संबंधी निष्कर्ष: [अनुमान/अनुभव]).**
- India VIX आकार सांगतो, दिशा नाही. Weekly close VIX range मध्ये ~77% वेळा, पण high/low फक्त ~57%.
- ⇒ pullback खोली आणि stops VIX/MR च्या प्रमाणात. 100 pts चा ABC VIX 11 ला "खोल", VIX 20 ला सामान्य.
- **Pullback दरम्यान VIX वाढतोय** ⇒ "फक्त pullback" यावरचा विश्वास कमी. **VIX घटतोय** ⇒ thesis ला आधार (आणि vega फायदा).

**Option selling ची वस्तुस्थिती [पुरावा +].**
- भारतात variance risk premium आहे (Sankar et al. 2020), पण tail मोठी (US PUT index skew ≈ −2.1).
- SEBI: **91–93% individual F&O traders तोट्यात** (FY22–FY25).
- ⇒ Costs, sizing आणि tail events निकाल ठरवतात. "OTM ची जास्त शक्यता" म्हणजे edge नाही.

---

# भाग D: पुराव्याची यादी आणि grade

> **आधार:** G-E0 (Abhi ने मंजूर केलेला, 2026-10-08) तक्ता. या knowledge base मुळे काही नवीन पुरावे जोडले आहेत (✚).
> - सगळे weights आधी ठरवलेले आहेत; grid मध्ये tune करायचे नाहीत.
> - बदल फक्त PAPER scorecard पाहून, Abhi च्या मंजुरीने.

| # | पुरावा | गुण | Chapter |
|---|---|---|---|
| T | Trend: HTF सोबत आणि मजबूत +15 · थकतोय +8 · range edge +5 · विरुद्ध −20 | −20…+15 | K1 |
| ✚ PB | Pullback चं स्वरूप: 3 waves, overlap, origin अबाधित, खोली 38.2–80% ⇒ +10 · धोक्याची चिन्हं (counter displacement, 5-wave counter-move, खोली > 0.80 आणि तिथे area/sweep नाही) ⇒ −10 · impulse origin जवळ / 100% च्या पलीकडे wick पण acceptance नाही ⇒ −15 (acceptance = A3 व्हेटो) | −15…+10 | K2 |
| CW | Correction कमकुवत होतोय (लहान legs/bodies, overlap, विरुद्ध wicks, wedge/diagonal, failed extension) | 0…+15 | K10 |
| AQ | Area गुणवत्ता (ठोस साधनं: flip, base/zone, range edge, ≥ 3-touch trendline, PDH/PDL; ACTIVE) | 0…+20 | K4, K6, K8 |
| CF | Confluence: प्रत्येक अतिरिक्त **प्रकाराला** +5. Fibonacci / C = A / channel यांना गुण फक्त ठोस area सोबत (K7). | 0…+10 | K7 |
| ✚ LQ | Liquidity: A low / equal lows / PDL चा sweep आणि reclaim | 0…+8 | K5 |
| RV | Reversal: 50 × (s − 0.30) | −10…+25 | K9 |
| ✚ VL | Volume (futures, `rel_vol`): pullback dry-up < 0.8 ⇒ +3 · C-end absorption spike किंवा reversal candle ला volume ⇒ +2 · pullback मध्ये वाढता volume (> 1.0) ⇒ −5 · data नाही ⇒ 0 | −5…+5 | K10.3 |
| ✚ DV | RSI divergence: C-end ला regular किंवा pullback मध्ये hidden ⇒ +3…+5. Impulse च्या टोकावर विरुद्ध regular divergence ⇒ −3. | −3…+5 | K10 |
| ✚ PT | Pattern वाचन: flag / opposite wedge ⇒ +3…+5 · double top/bottom किंवा H&S neckline break, impulse वरचा wedge ⇒ −10 | −10…+5 | K11 |
| GP | Gap: पुष्टी +10 · विरोध −10 | −10…+10 | K13 |
| EW | Elliott: 2/4/C/E-end +10 · gray 0 · A-end किंवा B च्या आत **शक्यता** −15 (count स्पष्ट असेल तर A3 व्हेटो) | −15…+10 | K3 |
| RM | R:R ≥ 5 | 0…+5 | A3 |
| ✚ TM | वेळ: 09:15–09:45 −5 · expiry दिवस सकाळ −3 | −5…0 | K14 |
| ✚ VX | Pullback दरम्यान VIX उडी −5 · VIX घटतोय +2 | −5…+2 | K14 |
| EV | Event दिवस | −5…0 | K13 |

**Grade:** A ≥ 60 · B 45–59 · C < 45. A/B ⇒ entry; C ⇒ नाही (shadow).

**अंतिम grade:** min(code, vision).

**⚠️ नवीन ✚ घटकांमुळे कमाल बेरीज वाढते.** म्हणून:
- G-E1a मध्ये IS वरचं गुणांचं वितरण (किती % setups A/B होतात) दाखवायचं.
- Thresholds (60/45) बदलायचे का, हा निर्णय Abhi चा.
- 7 Oct (अपेक्षित A) आणि एक स्पष्ट reversal दिवस (अपेक्षित C) यावर तपासणी.

---

# भाग E: नेहमीच्या चुका (bot आणि vision दोघांसाठी checklist)
1. **फक्त horizontal पाहिलं, trendline किंवा channel विसरलो** (7 Oct). ⇒ टप्पा 3 ची पूर्ण यादी, दर वेळी.
2. Fibonacci एकट्यावर area मानला. ⇒ ठोस area सोबतच.
3. A-end ला C-end समजलो. ⇒ आधी A, B, C मोजा. A नंतर B येईपर्यंत थांबा.
4. Expanded flat च्या B चा नवा extreme हा breakout समजलो. ⇒ B ≥ 90% A ⇒ flat; B > 105% A ⇒ expanded flat, आणि C अजून बाकी.
5. पहिल्या CHoCH लाच reversal म्हटलं. ⇒ LH (किंवा HL) तयार झाल्यावरच.
6. प्रत्येक wick ला sweep म्हटलं. ⇒ reclaim close हवा.
7. 2+ closes पलीकडे (acceptance) असूनही fade केलं. ⇒ हा real break.
8. Pullback दरम्यान minor impulse line तुटली म्हणून reversal म्हटलं. ⇒ हे अपेक्षितच.
9. चालू (न बंद झालेल्या) candle वर निर्णय. ⇒ फक्त बंद candles.
10. 09:15 च्या candles ना स्वच्छ structure समजलो.
11. Divergence वरून trend विरुद्ध trade. ⇒ divergence फक्त पुरावा.
12. Pattern नाव (hammer, engulfing) वरून निर्णय. ⇒ composite आणि context.
13. Level ला संरक्षण समजलो (strike level च्या थोडं पलीकडे). ⇒ strike अंतर σ वरून.
14. वरचा TF न पाहता 15M वर trend ठरवला.
15. Image वरून किंमत वाचली (vision). ⇒ किंमती फक्त code कडून.
16. X wave आल्यावर correction संपला असं मानलं.
17. Gap open वर पाठलाग. ⇒ पहिल्या pullback ची वाट.

---

# भाग F: प्रामाणिक मर्यादा: काय सिद्ध आहे, काय नाही
| गोष्ट | स्थिती |
|---|---|
| Strike breach = σ-अंतर | **[NIFTY] सगळ्यात चांगलं validated** (IS fit, VAL calibrated) |
| Real break वि. false break | यंत्रणा (stop clusters, cascade) पुराव्याने आधारित (Osler); 0.25 MR हा विशिष्ट नियम तपासलेला नाही |
| Trend persistence (momentum) | [पुरावा +] सामान्यतः; swing नियम स्वतः तपासलेले नाहीत |
| S/R levels चा edge | जगात लहान (+4–5pp, Osler). **[NIFTY] आपल्या engines मध्ये random पेक्षा वेगळा नाही.** |
| Candle patterns एकटे | [पुरावा −] ≈ random; context मध्ये चांगले. [NIFTY] अजून मोजता आलेलं नाही. |
| Fibonacci ratios | [पुरावा −]. फक्त मोजपट्टी. |
| Elliott भाकीत | पुरावा नाही. [NIFTY] random पेक्षा वेगळं नाही; golden 0/5. |
| Trendline एकटी | [पुरावा −] (3rd touch 37%). Confluence सोबत. |
| RSI divergence | कमकुवत |
| Chart patterns | Context filter, trigger नाही |
| Wyckoff, liquidity grab | [अनुभव] |
| Pullback मध्ये कमी volume | [अनुभव]; NIFTY futures चा जुना volume नाही ⇒ फक्त live PAPER मध्ये तपासता येईल |
| Session U-shape, overnight premium | [पुरावा +] |

**निष्कर्ष:**
- Edge कोणत्याही एका साधनात नाही. ते **confluence + पुष्टी + R:R ≥ 3 + σ-आधारित strike + शिस्त** यांच्या एकत्रित परिणामात असण्याची शक्यता आहे.
- ते खरं आहे का, हे **फक्त PAPER scorecard** (grade नुसार win %, प्रत्यक्ष R:R, expectancy) आणि random baseline शी तुलना सांगेल.
- म्हणून प्रत्येक signal ची पूर्ण गोष्ट आणि पुरावे नोंदवायचे.

---

# भाग G: विरोधाभासांचे निर्णय (code मध्ये एकच व्याख्या)
| विषय | निर्णय |
|---|---|
| Correction वेळ | Neely चे तपासलेले नियम (OR-rule, t(c) ≤ t(a)+t(b)) score म्हणून. "संपूर्ण correction impulse पेक्षा जास्त वेळ" हा नियम नाही. NIFTY वर corrective legs कमी bars चे निघाले. |
| Zigzag C, A च्या टोकापलीकडे | Strong guideline (truncated C शक्य) |
| Ending diagonal w4–w1 overlap | Guideline ("almost always") |
| HTF trend | Context / पुरावा (T), gate नाही (spec, `htf_gate_enabled=false`). Opportunity engine चा daily veto नवीन engine मध्ये नाही. |
| Pullback / wave 2 ची खोली | निश्चित आकडा नाही; valid zone 38.2–80% (Abhi), 80% पलीकडे कमकुवत, 100% पलीकडे acceptance = व्हेटो. Repo चा `r_warn` 0.75 → 0.80. |
| Real break | **एकच: `elliott/breaks.py`** (0.25 MR buffer + displacement / acceptance / failed retest). इतर व्याख्या (level_strength, zones, structure) engine मध्ये वापरायच्या नाहीत. |
| Displacement | **एकच:** range ≥ 1.2 MR (break साठी). Zone origin साठी `zones.py` ची (≥ 2 candles body ≥ 0.6 आणि ≥ 1.5 MR, किंवा एक ≥ 2.5 MR). दोन्ही settings मध्ये, नावं वेगळी. |
| MR window | चालू bar **वगळून**, 20 बंद bars (सगळीकडे) |
| Swing engine | Engine साठी एकच: `elliott/swings.py` (degree सह). Structure (HH/HL) त्याच pivots वरून. |
| Strength cap 2.5 MR | Climax logic (G-E0 modifiers): reclaim सह ⇒ दंड नाही; extension ⇒ वजा |
| FVG | Unproven ⇒ गुण नाहीत |
| Strike model expiry | NIFTY मंगळवार (table DTE-आधारित) |
| Gap थ्रेशोल्ड | ATR14 (daily) च्या पटीत, fixed % नाही |
| Levels चा edge | Area = कुठे पाहायचं; strike = σ-अंतर |

---

# स्रोत
**Project चे अहवाल आणि repo:**
- *Candlestick patterns आणि मानसशास्त्र*;
- *Elliott Wave सिद्धांत संपूर्ण अभ्यास*;
- *Elliott Wave trading setups सुधारित* (= `docs/ELLIOTT_WAVE_SPEC.md`);
- *Elliott Correction Waves Study*;
- *Gap trading अभ्यास*;
- *Leg and level strength research*;
- repo: `docs/reports/` (leg_classifier_g1, leg_level_validation_conclusions, g2_followups_conclusions, elliott_candle_merge, strike_breach_model_conclusions), `price_action/*`, `elliott/*`, `opportunity_engine/structure.py`, `zones.py`.

**नवीन अभ्यास:**
- [Osler (2000), Support for Resistance, FRBNY EPR](https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.html)
- [Osler (2003), Currency Orders and Exchange-Rate Dynamics, J. Finance (SR125)](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.html)
- [Osler, Stop-Loss Orders and Price Cascades (SR150)](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.html)
- [Garzarelli et al. (2014), Memory effects in stock price dynamics, Sci. Rep.](https://ar5iv.arxiv.org/html/1110.5197)
- [Chung & Bellotti (2021), Evidence and Behaviour of S/R Levels](https://ideas.repec.org/p/arx/papers/2101.07410.html)
- [Kavajecz & Odders-White (2004), Technical Analysis and Liquidity Provision, RFS](https://ideas.repec.org/a/oup/rfinst/v17y2004i4p1043-1071.html)
- [Lo, Mamaysky & Wang (2000), Foundations of Technical Analysis](https://web.mit.edu/~alo/www/Papers/techanal.html)
- [Tsinaslanidis, Guijarro & Voukelatos (2022), Fibonacci retracements, ESWA](https://www.datalearner.com/academic/journal-papers/0957-4174/volumes-and-issues/391/paper-detail/17703)
- [Kerobyan, Fibonacci Retracement: Myth or Reality? (forexop)](https://forexop.com/strategy/fibonacci-fact-or-fiction/)
- [Bulkowski (2020), Do Fibonacci Retraces Work? TASC](https://store.traders.com/stcov384dofi.html)
- [Bulkowski, Uptrendlines](https://thepatternsite.com/uptrendlines.html)
- [Bulkowski, Throwbacks and Pullbacks](https://thepatternsite.com/ThrowPull.html)
- [Bulkowski, Head-and-Shoulders Tops](https://thepatternsite.com/hst.html)
- [Bulkowski, Pennants](https://thepatternsite.com/pennants.html)
- [Bulkowski, Rising Wedges](https://thepatternsite.com/risewedge.html)
- [Bulkowski, Busted Pattern Performance](https://thepatternsite.com/BustPerformance.html)
- [Bulkowski, RSI Divergence Test](https://www.thepatternsite.com/DivergenceTest.html)
- [Bhattacharya, Holden & Jacobsen (2012), Round Numbers, Management Science](https://ideas.repec.org/a/inm/ormnsc/v58y2012i2p413-431.html)
- [Savin, Weller & Zvingelis (2007), H&S predictive power](https://www.cxoadvisory.com/technical-trading/testing-the-head-and-shoulders-pattern/)
- [Chang & Osler (1999), Methodical Madness, Economic Journal](https://ideas.repec.org/a/ecj/econjl/v109y1999i458p636-61.html)
- [Chong, Ng & Liew (2014), MACD and RSI oscillators](https://www.mdpi.com/1911-8074/7/1/1)
- [Moskowitz, Ooi & Pedersen (2012), Time Series Momentum](https://papers.ssrn.com/abstract=2089463)
- [Gao, Han, Li & Zhou (2018), Market Intraday Momentum](https://profiles.wustl.edu/en/publications/market-intraday-momentum/)
- [StockCharts: Dow and Fibonacci (Rhea secondary reactions)](https://articles.stockcharts.com/article/articles-chartwatchers-2017-06-charles-dow-and-leonardo-fibonacci-walk-into-a-bar/)
- [StockCharts: Wyckoff entry points](https://articles.stockcharts.com/article/articles-wyckoff-2016-04-how-to-determine-the-best-trade-entry-points/)
- [Sampath & Gopalaswamy (2020), Intraday variability, NSE](https://ideas.repec.org/a/sae/emffin/v19y2020i3p271-295.html)
- [Singh & Gangwar (2018), Intraday volatility of Nifty futures](https://mpra.ub.uni-muenchen.de/89689/1/MPRA_paper_89689.pdf)
- [Bhat, Pandey & Rao (2024), Day and night option returns, JFM](https://law-journals-books.vlex.com/vid/the-asymmetry-in-day-1115554990)
- [Sankar et al. (2020), Variance risk premium India](https://ideas.repec.org/a/eee/reveco/v70y2020icp321-334.html)
- [Ni, Pearson & Poteshman (2005), Clustering at strikes](https://ideas.repec.org/a/eee/jfinec/v78y2005i1p49-87.html)
- [Singh & Sen (IIMB), Expiration day effect](https://repository.iimb.ac.in/handle/2074/21032?mode=full)
- [ECGI: Jane Street expiry episode](https://www.ecgi.global/publications/blog/expiry-day-and-the-governance-of-algorithmic-trading-the-jane-street-episode)
- [SEBI: 93% individual F&O traders lost (FY22–24)](https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2024/updated-sebi-study-reveals-93-of-individual-traders-incurred-losses-in-equity-fando-between-fy22-and-fy24-aggregate-losses-exceed-1-8-lakh-crores-over-three-years_86906.html)
- [Business Standard: FY25 F&O losses](https://www.business-standard.com/amp/markets/news/net-losses-of-traders-in-fo-widens-in-fy25-sebi-study-125070701221_1.html)
- [Zerodha: SEBI index derivative rules](https://zerodha.com/z-connect/business-updates/sebis-new-rules-for-index-derivatives-heres-whats-changing)
- [FundsIndia: VIX as a predictor](https://www.fundsindia.com/blog/equities/vix-as-a-predictor/19270)
- [Bondarenko PUT/WPUT (S&P DJI Indexology)](https://www.indexologyblog.com/2016/02/18/paper-by-professor-bondarenko-has-intriguing-new-analysis-of-put-and-wput-indexes/)
- Frost & Prechter, *Elliott Wave Principle* (पुस्तक); Elder, *Trading for a Living* (पुस्तक)
