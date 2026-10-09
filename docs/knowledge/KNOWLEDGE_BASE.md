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
- **भाग H:** Golden setups G1–G9
- **भाग I:** बाजारातल्या परिस्थितींचा नकाशा (S1–S12, P1–P9, Gray-1 / Gray-2) — Simple Core चं reading layer
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
- **D → G7: Exhaustion gap reversal (Abhi, 2026-10-08; PAPER मध्ये ON, स्वतंत्र scorecard):** trend दिशेने stretched चालीनंतर अचानक मोठा gap थेट **major (HTF) supply/demand zone** मध्ये उघडतो, zone hit होतो, आणि त्याच दिवशी short covering / recovery येते. अटी खाली भाग H (G7) मध्ये. Open वर entry कधीच नाही; rejection ची पुष्टी आणि पहिला pullback आल्यावरच.
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
| HTF trend | **पालक दिशा trade ची दिशा ठरवते; आजोबा degree फक्त पुरावा** (Abhi, 2026-10-08; नकाशा भाग I P1). अपवाद: S4 flip retest, G7, G10 (स्वतंत्र scorecard). Opportunity engine चा daily veto नवीन engine मध्ये नाही. |
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

# भाग H: Golden setups G1–G9 (Abhi ने मंजूर केलेले, 2026-10-08)

> सगळ्यांमध्ये समान 5 गोष्टी:
> 1. स्पष्ट impulse (BOS);
> 2. corrective pullback (3 waves, overlap, origin अबाधित);
> 3. खऱ्या area मध्ये शेवट (demand, flip, trendline, liquidity; Fibonacci फक्त सोबतीला);
> 4. reversal candle बंद (sweep आणि reclaim असेल तर अधिक चांगलं);
> 5. invalidation जवळ आणि स्पष्ट ⇒ R:R ≥ 3. Breakout चा पाठलाग नाही.

| # | Setup | ओळख | Entry | Invalidation | Chapter |
|---|---|---|---|---|---|
| **G1** | Zigzag wave 2 / ABC चा शेवट | धारदार impulse → A-B-C. C ≈ A. 50–61.8% (80% पर्यंत) retrace, **आणि तिथे आधीचा demand / base** | C-end ला reversal candle बंद झाल्यावर | Impulse origin (wave 1 सुरुवात) | K3, K4, K7 |
| **G2** | Expanded flat: C, A चा low/high तोडून परत (spring / upthrust) | B > 105% A (सापळा). C, A च्या टोकापलीकडे sweep करून परत आत close | Sweep नंतरची पहिली मजबूत candle | C चं टोक | K3, K5, K12 |
| **G3** | Triangle (wave 4 / B): E चा शेवट | आकुंचन पावणारे 5 legs (3-3-3-3-3). E undershoot किंवा throw-over | E-end ला reversal. Triangle breakout वर नाही. | C चं टोक | K3 |
| **G4** | Role flip retest | तुटलेला support (आता resistance) किंवा उलट. त्यावर pullback, **कमी volume**, rejection wick / engulfing | Rejection candle बंद झाल्यावर | Flip zone पलीकडे real break | K4, K5, K10.3 |
| **G5** | Ending diagonal C + trendline / resistance | C wedge सारखा: लहान होत जाणारे, overlapping legs. Trendline / area वर संपतो. Gap ची पुष्टी असेल तर अधिक मजबूत (7 Oct 2026). | Area वर reversal candle | Diagonal चं टोक | K3, K6, K13 |
| **G6** | Trend मधला साधा pullback demand वर | HH/HL स्पष्ट. Pullback संथ, overlapping, कमी volume. Displacement च्या आधीच्या base वर. | Hammer / engulfing बंद झाल्यावर | Base पलीकडे | K1, K2, K4, K9 |

| **G7** | Exhaustion gap reversal (major zone मध्ये gap) | (1) Trend stretched: शेवटचा leg ATR च्या पटीत लांब, legs लहान होत जाणं / divergence / Elliott 5 किंवा C च्या शेवटाची शक्यता; (2) trend दिशेने मोठा gap (G5 / E) थेट **major HTF zone** मध्ये (D2/D3 demand / supply, न तुटलेला); (3) पहिल्या 2–6 bars मध्ये **rejection**: gap extension अपयशी, zone मध्ये लांब wick, close परत open च्या पलीकडे / gap edge reclaim, futures volume climax पण प्रगती नाही (absorption) | Rejection नंतरचा **पहिला pullback** (higher low / lower high) zone वर टिकल्यावर reversal candle. Opening window मध्ये आणि पहिल्या रिकव्हरी candle वर entry नाही. | Gap दिवसाचं टोक (zone च्या पलीकडे) + buffer. Target: PDC / gap fill (Bulkowski: exhaustion gaps 60–66% आठवड्यात भरतात). | K13, K4, K5, K10, K12, K3 |
| **G8** | Motive wave मधला उथळ pullback: wave 3 मध्ये (ii) / (iv) of 3 | Wave 2 संपून wave 3 सुरू, मजबूत displacement. आतले pullbacks **उथळ** (23.6–38.2%), जलद (2–6 candles, flag / छोटा ABC), wave 1 च्या टोकावरचा flip किंवा wave 3 मधला base area. Momentum मजबूत. | उथळ pullback च्या शेवटी commitment candle (impulse दिशेने) | Sub-wave (i) ची सुरुवात / pullback चं टोक (R1, lower degree) | K3 (S2, S4), K4, K11 (flag) |
| **G9** | Wave 4 चा शेवट ⇒ wave 5 | Wave 3 नंतर बाजूला किंवा उथळ correction (flat / triangle / zigzag), wave 1 च्या भागात शिरत नाही (R3). Alternation: wave 2 धारदार असेल तर 4 बाजूला. | Wave 4 end वर commitment candle | Wave 1 चं टोक (overlap = count चुकला) | K3 (S3, S9) |


> **Motive wave चे trades (G1, G8, G9 आणि बाकी):** सगळे setups correction च्या शेवटी entry घेऊन **पुढची motive wave** पकडतात:
> - wave 2 end (G1) ⇒ wave 3, सगळ्यात मोठी चाल;
> - (ii) / (iv) of 3 (G8) ⇒ wave 3 चालू असताना पुन्हा entry;
> - wave 4 end (G9, G3) ⇒ wave 5;
> - ABC / C-end (G1, G2, G5) ⇒ मोठ्या trend ची पुढची impulse.
>
> **Motive wave च्या आत, उथळ pullback शिवाय, entry नाही** (breakout / chase).
>

> **Motive wave reference levels (engine फक्त माहिती देतो; target / SL dashboard setting ठरवते):**
> - Wave 3 projection = wave 2 end + 1.618 × wave 1 (पर्याय 1.0 / 2.618). SL संदर्भ: wave 1 origin (G1), sub-wave (i) origin (G8).
> - Wave 5 projection = wave 4 end + 1.0 × wave 1, किंवा wave 4 end + 0.618 × (wave 1 start → wave 3 end). SL संदर्भ: wave 1 चं टोक (G9).
> - या projections [अनुभव / guideline] आहेत (Fibonacci ratios ना सांख्यिकीय आधार नाही, K7). म्हणून फक्त `ref_levels` मध्ये, आणि dashboard च्या `target_mode` चे पर्याय म्हणून.

> **G9 सावधानता:** wave 5 लहान असू शकतो (truncation), आणि शेवटी divergence येते. Target कमी; spec Tier C (size setting).

> **G7 टीप:** अनेकदा हा gap मोठ्या degree च्या correction चा C-end असतो, म्हणजे मोठ्या trend मधला pullback संपतोय. मग हा सुद्धा "pullback end" च. पण मोठ्या trend विरुद्ध असेल तर तो counter-trend trade; evidence T लागू, आणि scorecard वेगळा. Event दिवशी जास्त काटेकोर.

**वापर:**
- Vision playbook मध्ये ही 9 नावं आणि ओळख (मजकूर म्हणून).
- Vision JSON मध्ये `setup_type` (G1–G9 किंवा none).
- Code candidates वर setup label.
- Golden Gallery मधले Abhi ने निवडलेले खरे NIFTY charts या प्रत्येकाची उदाहरणं.

---

# भाग I: बाजारातल्या परिस्थितींचा नकाशा (Market Situation Map)

> **स्थिती:** मंजूर (Abhi, G-MAP1 2026-10-09) — मसुदा 4 + G-MAP1 चे निर्णय (P1, P4, S3, S9, I9). KB चा भाग I (हाच मजकूर; वेगळी file नाही).
> **कोणत्या engine साठी:** Simple Core (trend → area → pause → commitment). हा नकाशा Simple Core ला सांगतो की **आपण कोणत्या परिस्थितीत आहोत, trend दिशा कोणती, आणि area कुठे शोधायचा.** नवीन gates चा ढीग नाही.
> **लेबलं:**
> - [नियम] Elliott चा पक्का नियम;
> - [स्रोत: नाव] practitioner किंवा प्रकाशित research;
> - [research-अनुमान] research notes मधला संशोधकाचा तर्क (स्रोताचं थेट विधान नाही);
> - [NIFTY] आपल्या data वर मोजलेलं;
> - [Abhi] Abhi चा निर्णय;
> - [अनुमान] या नकाशातला तर्क, तपासायचा;
> - **[प्रस्ताव]** KB भाग A3 / G मध्ये बदल, Abhi च्या मंजुरीशिवाय लागू नाही.

---

## I0. हा भाग का लिहिला

आतापर्यंत उदाहरणागणिक नियम बदलत गेले:
- 7 Oct वरून "protected level तुटेपर्यंत correction";
- 14 Aug वरून माझा "> 80% आणि impulsive ⇒ POSSIBLE_REVERSAL";
- मग Abhi ने सांगितलं की 58% सुद्धा नवी impulse असू शकते [Abhi], आणि तो नियम पुन्हा बदलावा लागला.

शेवटी 16 Feb 2018 चा 09:30 चा signal (target गाठलेला; Abhi चा निर्णय बाकी) अडला. 144% चाल (impulse origin पार केलेली) "counter-move" म्हणून मोजली गेली, आणि flag कधीच संपला नाही.

**मूळ कारण: research न वापरणं.**
- **NIFTY 15M वरचे आकडे (KB K2) [NIFTY]:** 57% pullbacks impulse इतके किंवा जास्त वेगवान, 62% मध्ये displacement, आणि 31% pullbacks 0.75 पेक्षा खोल. म्हणून "वेगवान / displacement असलेली counter-move ⇒ reversal" हा नियम अनेक सामान्य pullbacks अडवणार होता.
- **Research मधल्या तीन मुख्य गोष्टी prompts मध्ये नव्हत्या:**
  1. नेहमी primary आणि alternate count, आणि प्रत्येकाचा invalidation [स्रोत: EWI, CWCOUNT];
  2. Trade degree आणि त्याच्या वरची degree [स्रोत: Kennedy, MTPredictor];
  3. चालीचा अर्थ अनेकदा तिच्या नंतरच्या चालीवरून कळतो [स्रोत: EWP outline (elliottwaveplus, secondary): "trend change ची पुष्टी एका लहान degree च्या उलट 5-wave चालीने"; NEoWave: pattern ची पुष्टी "shortly after the fact"].

हा भाग नियमांची यादी नाही. Pullback trader समोर येणाऱ्या प्रत्येक परिस्थितीसाठी तो सांगतो:
- ती कशी दिसते;
- तिच्यासारखी दिसणारी दुसरी कोणती;
- फरक कसा ओळखायचा, आणि **कोणत्या bar ला तो सर्वात लवकर कळतो** (no lookahead);
- ओळखता येत नसेल तेव्हा काय करायचं.

---

## I1. नऊ मूलतत्त्वं

### P1. आधी degree, मग setup
- **Degree म्हणजे count मधली जागा**, वेळ किंवा आकार नाही [स्रोत: EWP].
  - सोयीसाठी default: trade degree = 15M वरचा correction, पालक = 1H swing, आजोबा = Daily / Weekly. पण degree count वरून ठरते, TF वरून नाही (खाली पालकाची व्याख्या).
- **पालकाची दिशा:** आपण ज्या correction च्या शेवटी trade घेतो, तो correction ज्या motive sequence मध्ये बसतो, तिची दिशा (primary count नुसार).
  - **Code मध्ये [Abhi, 2026-10-09]:** preferred count ची चालू sequence दिशा. "पुढची motive wave" चा vote नाही; correction च्या मध्यात तो शून्य येतो (A4b: 63–91% gray).
  - **Abhi ची पालक-दिशा दुरुस्ती** (review loop): त्या session साठी `parent_source_effective = abhi_review`. ती त्याच्या count च्या invalidation शी बांधलेली; तो तुटला ⇒ खालच्या setting वर परत.
  - Setting `parent_source` = `market_state` (सध्या) / `preferred_count`. आधी दोन्हींची तुलना आणि conflict चं प्रमाण; मग Abhi बदल करेल. `PARENT_CONFLICT` अजून gate नाही. `preferred_count` mode मध्ये count / sequence नसेल ⇒ `PARENT_UNKNOWN` ⇒ trade नाही. हा Gray-1 नाही (रचनेची घटना नाही), म्हणून gray `reduce` ने सुद्धा trade होत नाही.
  - उदा. 22 Sep: wave (4) हा (1)–(5) खालच्या sequence मध्ये ⇒ पालक दिशा खाली.
  - 26 Aug: P3 ने ठरल्यावर wave (2) हा नव्या (1)–(5) खालच्या sequence मध्ये ⇒ खाली.
  - त्या sequence च्या वरची degree (उदा. Daily) ही आजोबा. ती अजून विरुद्ध दिशेला असू शकते. तसं असेल तर तो फक्त नकारात्मक पुरावा (कमी विश्वास), बंदी नाही.
- Counts ची क्रमवारी फक्त Elliott नियम, guidelines आणि रचनेच्या घटनांवरून (P2, P3). त्यामुळे P1 आणि P2 एकमेकांवर अवलंबून नाहीत.
- **Trade पालक degree च्या दिशेने** [स्रोत: Kennedy: "Waves 3, 5, A, and C are the most advantageous to trade, because they are oriented in the direction of the one larger trend"; MTPredictor: "Trade in direction of larger-degree trend"].
  - Simple Core trend दिशा HTF market state (protected level सह) वरून घेतो [अनुमान: Trade session च्या Simple Core अहवालानुसार; code मध्ये पडताळायचं].
  - **[Abhi, 2026-10-08 मंजूर]** KB भाग G ची ओळ "HTF trend = Context / पुरावा, gate नाही (spec, `htf_gate_enabled=false`)" बदलून: **"पालक दिशा trade ची दिशा ठरवते; आजोबा degree फक्त पुरावा."**
- **स्पष्ट अपवाद** (स्वतंत्र scorecard सह):
  - S4 मध्ये flip retest, break दिशेने [Abhi, K-10];
  - G7 exhaustion gap reversal (PAPER मध्ये ON) [Abhi, KB H];
  - G10 range / sideways कड: पालक trend नसताना, दिशा कडेवरून (S9) [Abhi];
  - K13 setup A: trend विरुद्ध gap अपयशी ⇒ trend दिशेने (हा अपवाद नाही, पालकाच्याच दिशेने आहे).
- **B-end → C trade, जेव्हा तो संपूर्ण ABC ज्या trend ला correct करतो त्याच्या विरुद्ध असतो:** default OFF [Abhi]. (ABC च्या आत C ची दिशाच "पालक" वाटेल, म्हणून इथे पालक = ABC ज्या trend ला correct करतो तो trend.)
- **आजोबा degree वर** wave 5 / ending diagonal / मोठ्या correction चा शेवट जवळ ⇒ फक्त नोंद / पुरावा, बंदी नाही [research-अनुमान]. Size वर परिणाम P9 च्या मोजमापानंतरच.

### P2. दोन counts: primary आणि alternate
- "At any time, two or more valid wave interpretations usually exist." Preferred = सगळ्यात जास्त guidelines पाळणारा, alternate = त्यानंतरचा [स्रोत: EWI].
  - Backtest (2015–2021) मध्ये vision / Evening Plan नसतो, त्यामुळे क्रमवारी फक्त code च्या नियम + guidelines वरून.
  - Live मध्ये vision आणि Abhi चं मत (Evening Plan ✔) जोडलं जातं.
- **प्रत्येक count सोबत:**
  - invalidation: इथे गेला तर count मेला;
  - confirmation: इथे गेला तर count बळकट [स्रोत: CWCOUNT; research-अनुमान].
- **तपासण्याचा क्रम (प्रत्येक बंद bar वर):**
  1. **Gray-1: पालकाची दिशा रचनेने ठरलेली आहे का?** खालीलपैकी काहीही चालू असेल तर ⇒ gray ⇒ trade नाही:
     - S3 चा reaction अजून उघडा (P3 चा निकाल नाही; 12 Aug, 25 Aug 10:45);
     - S4 चं testing अजून न सुटलेलं (अपवाद: S4 चा flip retest);
     - (Range च्या **मध्यात** असणं हा gray नाही. तिथे area नाही, म्हणजे व्याख्येनेच setup नाही, कोणत्याही gray धोरणात. कडा G10 नियमाने tradable; S9 पाहा.)

     Gray-1 फक्त या **रचनेच्या घटनांवरून** ठरतो. Counts च्या "गुणांच्या फरकावरून" नाही, म्हणजे लपलेला आकडा नाही.
  2. **Gray-2: trade degree वर correction संपल्याचं commitment bar ला ठरवता येतं का?** ठरवता येतं म्हणजे:
     - **zigzag / flat:** A, B, C तिन्ही legs दिसतात, आणि C, A च्या टोकापर्यंत किंवा पलीकडे गेला. C, A च्या टोकापर्यंत पोहोचला नाही (truncated) ⇒ Gray-2. अपवाद: S5 चे निकष (with-trend legs लहान होत नाहीत, divergence नाही) पूर्ण असतील तेव्हाच, आणि तो कमी पुरावा.
     - **triangle:** पाच legs.
     - **flag (S5):** G8 ची रचना.
     - आणि commitment candle बंद.
     - **G10 (range कड):** ABC नसतो ⇒ Gray-2 म्हणजे फक्त "commitment candle बंद झाली का". Grade वाढ लागू नाही.

     Counter-move स्वतः 5 waves (म्हणजे A) असेल, किंवा legs पुरेसे दिसत नसतील ⇒ gray [नियम R4; KB A-end ban; KB E3].
  3. **Trade:** पालक दिशेने, त्या परिस्थितीच्या area वर (I3), Simple Core ची commitment.
  4. **Grade वाढ (बंधन नाही):** alternate count नुसार सुद्धा entry पासून target पर्यंतचा मार्ग trade invalidation आधी पूर्ण होतो (R:R ≥ 3 सह) ⇒ "उत्तम संधी" [स्रोत: ELWAVE: "If you find several alternative counts pointing in the same direction, you have found an excellent trading opportunity"]. Target दोघांपैकी जवळचा.
- **Alternate असणं म्हणजे gray नाही; alternate नेहमीच असतो.** Gray म्हणजे रचनेने अजून न सुटलेला प्रश्न: "काय चाललंय ते माहीत नाही" [स्रोत: Kennedy: "You never trade gray. You have to know what is going on"].
- **Gray चं धोरण: Abhi दर दिवशी ठरवतो [Abhi, 2026-10-08].** Code मध्ये पक्का नियम नाही.
  - **Evening Plan:** उद्याच्या plan मध्ये gray ची स्थिती दाखवायची (कोणता gray, का, कोणते दोन counts). Abhi च्या reply मध्ये त्या दिवसाचं धोरण:
    - `gray = block` ⇒ gray मध्ये trade नाही;
    - `gray = reduce` ⇒ trade चालेल, पण grade कमी आणि size dashboard च्या `gray_size` setting प्रमाणे (Abhi, 2026-10-09: अर्धे lots; अर्धे 1 lot पेक्षा कमी ⇒ trade नाही).
    - **Gray-1 मध्ये पालक दिशाच ठरलेली नसते.** म्हणून `reduce` फक्त तेव्हाच, जेव्हा Abhi reply मध्ये दिशा सुद्धा सांगतो (उदा. "gray reduce bear"). दिशा नसेल ⇒ Gray-1 साठी `block`. Gray-2 मध्ये दिशा पालकाची.
  - **Abhi ने धोरण सांगितलं नाही** ⇒ `block`.
  - **Plan ला ✔ नसेल तर (Abhi, 2026-10-09):** entries चालू, पण signal संदेशात "⚠ plan Abhi ने तपासलेला नाही". Gray धोरण नसल्यास gray `block` कायम. स्पष्ट plan ✘ ⇒ त्या दिवशी trade नाही.
  - **दिवसा नव्याने gray आला** (उदा. S3 reaction सुरू झाला): त्या दिवसाचं धोरण लागू. `reduce` असेल तर signal Telegram वर "GRAY" खुणेसह, Approve बटणासह (सध्याची व्यवस्था).
  - **नोंद:** प्रत्येक दिवसाचं धोरण आणि gray signals चा निकाल scorecard मध्ये वेगळा. कालांतराने कोणतं धोरण चांगलं ते data दाखवेल.
- **स्थिरता:** count दर bar ला नव्याने मोजायचा नाही; पुढे वाढवायचा. वरच्या degree चा invalidation तुटला तरच नवी मोजणी [स्रोत: WaveBasis]. अपवाद: Abhi ने मागितलेला "पुन्हा count" (त्याच्या मान्य दुरुस्त्या anchors म्हणून), नोंदवून. Primary बदलताना hysteresis [research-अनुमान].

### P3. चालीचा अर्थ तिच्या नंतरच्या चालीवरून (reaction test)
- जोरदार counter-move दिसल्या क्षणी "pullback की reversal" ठरवणं बहुतेक वेळा शक्य नसतं. दोन valid counts असतात [स्रोत: EWI], आणि pattern संपल्याची खात्री थोड्या उशिरा मिळते [स्रोत: NEoWave].
- **Reaction corrective असेल** (3 waves, overlap), counter-move ने तोडलेला area / flip ओलांडला नाही, आणि मग counter-move दिशेने commitment आली ⇒ counter-move = नवी impulse.
  - Reaction चा शेवट = नव्या trend चा पहिला correction [स्रोत: MTPredictor W3: "Best place to buy is on the initial correction after the start of the new trend" (Gann)].
- **Reaction impulsive असेल**, आणि counter-move ची सुरुवात real break ने (breaks.py) परत घेतली ⇒ counter-move हाच pullback होता ⇒ जुना trend.
- **Reaction चालू असताना** ⇒ Gray-1.
- **सगळ्यात लवकर कधी कळतं:** reaction च्या शेवटच्या commitment candle च्या close वर, किंवा real break च्या confirm bar वर. त्याआधी नाही.

### P4. मोजमाप सापेक्ष; आकडे फक्त व्याख्येचे
- **प्रत्येक चाल दोन गोष्टींशी तुलना करून मोजायची:**
  1. ती ज्या impulse ला correct करते तिच्याशी;
  2. बाजाराच्या अलीकडच्या, त्याच degree च्या चालींशी (किती मागे पाहायचं ते setting) [अनुमान].
- **व्याख्येच्या रेषा:**
  - **Impulse origin:** त्याचा real break (breaks.py, KB भाग G ची एकच व्याख्या) ⇒ pullback नाही (A3 व्हेटो). Wick पलीकडे जाऊन परत आत ⇒ sweep (S7; KB D मध्ये −15 पुरावा).
  - Elliott नियम R1–R11 [नियम].
  - बंद candle.
- **कोणते पुरावे भेद करतात:**
  - **NIFTY वर मोजलेलं:** वेग आणि displacement सामान्य pullbacks मध्ये सुद्धा भरपूर ⇒ एकटे reversal चा पुरावा नाहीत [NIFTY, KB K2].
  - **IS वर मोजलेलं (G-MAP1, A2) [NIFTY]:** "trend चालू" वि. "reversal" यांत फरक दिसला तो फक्त **खोलीत** (AUC 0.71) आणि **displacement** मध्ये (0.59, कमकुवत). Overlap आणि legs (3 वि. 5) यांनी फरक केला नाही. खोलीचा AUC काहीसा फुगलेला आहे, कारण खोल चाल origin जवळ असते, आणि ती तुटण्याची शक्यता आपोआप जास्त.
  - **गोठवलेली यादी [Abhi, 2026-10-09]:**
    - खोली = पुरावा;
    - displacement = कमकुवत पुरावा;
    - overlap / legs = फक्त नोंदीसाठी.
  - **निष्कर्ष:** counter-move स्वतःकडे पाहून pullback की reversal हे त्या क्षणी ठरत नाही. म्हणूनच P3 (reaction test) हाच मुख्य मार्ग.
- **खोली (पुरावा, gate नाही):**
  - < 38.2%: फक्त मजबूत trend मध्ये (S5, G8: 23.6–38.2% [KB H, Abhi]);
  - 38.2–80%: valid [Abhi];
  - 80–100%: कमकुवत; area + sweep हवा [KB D];
  - origin चा real break ⇒ pullback नाही.

### P5. Area प्रत्येक परिस्थितीत वेगळ्या साधनाने
- प्रत्येक परिस्थितीचा area वेगळा (I3). उदा. मजबूत trend मधल्या flag साठी flag ची स्वतःची कड आणि तुटलेला लहान swing हेच areas. जुना horizontal zone असेलच असं नाही [अनुमान; structure notes: "Enter on the reversal candle at the flag's lower boundary"].
- **Area निर्णयाच्या क्षणी अस्तित्वात असला पाहिजे** (no lookahead):
  - zone displacement + BOS confirm झाल्यावरच [स्रोत: areas notes];
  - pivot त्याच्या confirm bar नंतरच [स्रोत: algo biases notes].

### P6. पुष्टी: बाजाराला आधी commit करू द्या
- "Let the market commit to you before you commit to the market" [स्रोत: Kennedy].
- Commitment candle बंद झाल्यावर entry (Simple Core).
- Candle एकटी कमकुवत पुरावा [स्रोत: Marshall, Young & Rose 2006; Tharavanij 2017] ⇒ ती फक्त योग्य परिस्थिती + area मध्ये अर्थपूर्ण.

### P7. "नाही" ची नोंद
- प्रत्येक "नाही" सोबत: परिस्थिती (S#), दोन counts, पालक दिशा, gray प्रकार.
- Scorecard मध्ये gray मुळे सोडलेल्या संधी वेगळ्या (I4.5) ⇒ gray फार कडक आहे का ते कळेल.

### P8. आकडा फक्त कारणासह
- **Code मधल्या प्रत्येक आकड्याचा स्रोत यापैकी एक:** व्याख्या / Abhi / research / NIFTY वर मोजलेला.
- **अंदाजाने ठेवलेला आकडा** = setting + sensitivity (I5).
- या नकाशातले आकडे (उदा. Brooks चे "1–3 bars", K11 चे "4–20 bars") स्रोताचे आहेत, आपले नियम नाहीत.

### P9. बाजार खरा पैसा आणि sentiment ने हलतो [Abhi, 2026-10-09]
- Elliott, patterns, channels आणि S/R फक्त **कुठे** वळू शकतो ते सांगतात. बाजार **खरंच** वळेल की नाही हे पैसा ठरवतो: FII / DII flows, जागतिक परिस्थिती (US बाजार, bond yields, dollar index, crude), भारतीय valuation आणि VIX.
- **Weekly वरून बाजाराची एकूण स्थिती** ठरते [Abhi].
- म्हणून Evening Plan मध्ये रोज **"Macro आणि sentiment"** हा भाग, VIX च्या chart सह. हे **पुरावा आणि संदर्भ** आहे, ठरीव नियम नाही.
- कोणत्या macro परिस्थितीत कोणते trades चालतात, हे **IS data वर मोजून** ठरवायचं. गृहीत धरायचं नाही.
- उदा. "wave 5 मध्ये trades कमी फायदेशीर" (S8) हे **गृहीतक** आहे, मोजलेलं नाही. ते macro / sentiment सोबत तपासायचं.

---

## I2. परिस्थितींचा तक्ता

| # | परिस्थिती | ओळख (real time) | सारखी दिसणारी | Setup | काय |
|---|---|---|---|---|---|
| **S1** | सामान्य pullback | पालक दिशा स्पष्ट; 3-wave, overlapping; origin अबाधित | S3; W-X-Y combination | G1, G6, G5 | C-end वर area + commitment |
| **S2** | खोल pullback | 61.8–80% (valid) किंवा 80–100% (कमकुवत); रचना corrective | S3, S4 | G1, G2 | Area + sweep / spring |
| **S3** | जोरदार counter-move | Impulse चा शेवटचा confirmed 1H HL / LH breaks.py real break ने तुटला; origin real-broken नाही | S2 | नव्या trend चा पहिला correction | Gray-1; reaction ची वाट |
| **S4** | Testing | Correct होणाऱ्या impulse च्या origin चा **real break** (breaks.py). हा origin बहुधा पालकाचा protected level असतो. | S7 | G4 | Flip retest, break दिशेने [Abhi] |
| **S5** | मजबूत trend मधला उथळ flag | Trade degree वर wave 3 / C; उथळ, अरुंद; G8 ची रचना (2–6 candles, flag / छोटा ABC) | S8 | G8 | Flag कड / तुटलेला swing |
| **S6** | बाजूचा correction | स्पष्ट impulse नंतर, वेळखाऊ, overlapping | S9 | G3, G9 | E-end / C-end फक्त |
| **S7** | Expanded flat / spring | B नवा extreme; C, A चं टोक sweep करून परत | S4 | G2 | Sweep + reclaim नंतर |
| **S8** | Trend थकतोय | Trade degree वर with-trend legs लहान, pullbacks मोठे, divergence | S5 | G9 (सावध) | कमी विश्वास; fade नाही |
| **S9** | Range / sideways | market_state RANGE; overlap, दोन्ही कडांवर sweeps, मध्ये MAGNET | S6; range ची खरी break | G10 | कडेवर commitment ⇒ कडेच्या दिशेने (खाली ⇒ bull put, वर ⇒ bear call); मध्यात नाही [Abhi] |
| **S10** | Gap दिवस | Open आदल्या range बाहेर | — | K13 A / B, G7 | Gap स्वीकारला की नाकारला |
| **S11** | B wave सापळा | पालक degree वर correction मध्यात (A झाला, C बाकी) | S1 चा impulse | — | B च्या आत नाही |
| **S12** | विशेष वेळा | पहिली 30 मिनिटं, event, expiry, VIX उडी, "आजपर्यंत pullback नाही", 15:15 चा signal | — | — | पुरावा / execution नियम |

**दोन परिस्थिती एकत्र लागू झाल्या तर:**

| जोडी | कोणती जिंकते |
|---|---|
| S3 + S11 (26 Aug सारखं) | S3 चे नियम (reaction test). S11 फक्त सांगतो की reaction च्या आत trade नाही. |
| S5 + मोठ्या degree चा wave 5 (P1 आजोबा) | Entry साठी S5 (trade degree). मोठ्या degree चा wave 5 फक्त नोंद / पुरावा (size वर परिणाम P9 च्या मोजमापानंतरच). |
| S5 + S8 (दोन्ही trade degree वर) | S8. With-trend legs लहान होत असतील तर तो मजबूत trend नाही. |
| S6 + S9 | Range हा मोठ्या trend मधला correction असेल तर फक्त trend दिशेची कड. पालक degree वर trend नसेल तर दोन्ही कडा (S9 पाहा) [प्रस्ताव, default]. |
| S2 + S3 | Counter-move corrective (3 waves, overlap) ⇒ S2. नाहीतर S3 (gray). |
| S4 + S10 / S12 | S4 चे नियम; S10 / S12 वेळ आणि पुराव्यासाठी. |
| इतर कुठलीही | जास्त कडक परिस्थिती लागू. |

---

## I3. प्रत्येक परिस्थिती तपशीलवार

> **साचा:** गोष्ट · सारखी दिसणारी · फरक · सगळ्यात लवकर कधी कळतं · area · invalidation · स्रोत.

### S1. सामान्य pullback
- **गोष्ट:** Impulse नंतर trend दिशेचे traders नफा घेतात, आणि उशिरा आलेले counter-traders धाडस करतात. Trend दिशेच्या resting orders मुळे चाल तुटक आणि overlapping होते [स्रोत: KB K2; Wyckoff: reactions "show smaller spreads and diminished volume"].
- **सारखी दिसणारी:**
  - S3 (नव्या trend ची पहिली चाल);
  - W-X-Y combination: पहिला ABC संपला वाटतो, पण X नंतर आणखी एक correction येतो [KB E16].
- **फरक:**
  - 3 waves, overlap;
  - origin अबाधित;
  - candles impulse पेक्षा अरुंद;
  - futures volume कमी [Abhi; KB K10.3].
  - Combination चा धोका: correction impulse पेक्षा खूप जास्त वेळ बाजूला गेला, किंवा पहिला "C" लहान / truncated दिसला ⇒ alternate "हा W आहे" बळकट [अनुमान].
- **C चे प्रकार:**
  - C कधी ending diagonal च्या रूपात येतो (7 Oct) ⇒ S1 च (G5).
  - C कधी A च्या टोकापर्यंत पोहोचत नाही (truncated C, running flat) ⇒ मजबूत trend चं लक्षण [KB K3].
- **सगळ्यात लवकर:** commitment candle च्या close वर.
- **Area:** impulse चा origin base / demand, flip, trendline, liquidity (KB टप्पा 3 ची पूर्ण यादी).
- **Invalidation:**
  - trade: C चं टोक;
  - count: wave 2 entry ⇒ wave 1 ची सुरुवात; wave 4 entry ⇒ wave 1 चं टोक [स्रोत: Kennedy].
- **Counter-move स्वतः 5 waves असेल** ⇒ ते A आहे, C नाही ⇒ entry नाही [नियम R4; KB A-end ban] ⇒ बहुधा S3.

### S2. खोल pullback
- **गोष्ट:** "Second waves often retrace so much of wave one that most of the profits gained up to that time are erased" [स्रोत: EWP wave personality]. गर्दीला वाटतं trend संपला. Invalidation (origin) जवळ असल्याने R:R चांगला मिळू शकतो.
- **सारखी दिसणारी:** S3, S4.
- **फरक:** रचना S1 सारखीच; शेवटी sweep / spring किंवा spreads आकुंचन [स्रोत: Wyckoff test; areas notes].
- **खोली:** 61.8–80% valid [Abhi]; 80–100% कमकुवत ⇒ area + sweep आवश्यक [KB D].
  - Wave 2 च्या सामान्य खोलीबाबत स्रोतांत मतभेद: Kennedy ".618"; Swannell (शेअर) "38.2% दुप्पट वेळा".
- **Area:** origin जवळचा demand / flip / liquidity. Fibonacci फक्त सोबत [Abhi, KB K7].
- **Invalidation:** C चं टोक (trade); origin (count).

### S3. जोरदार counter-move: नवी impulse असू शकते (11–12 Aug)
- **गोष्ट:** Trend विरुद्ध एक बाजू अचानक घाईत येते, आणि जी impulse ती correct करते तिची अंतर्गत रचना (शेवटचा confirmed 1H HL / LH) real break ने तुटते. Impulse origin चा real break नाही (झाला तर S4). चाल अनेकदा 5-wave सारखी, कमी overlap अशी दिसते, पण हे फक्त वर्णन आहे, ओळखीची अट नाही (P4).
  - ही नव्या trend ची wave 1 / A असू शकते, किंवा जुन्या trend चा खोल, वेगवान pullback (NIFTY वर वेगवान pullbacks सामान्य [NIFTY, KB K2]).
  - KB K1 नुसार इथे झालेला CHoCH हा **इशारा** आहे, reversal नाही.
- **सारखी दिसणारी:** S2.
- **फरक त्या क्षणी करता येत नाही; तो reaction मधून कळतो (P3):**

  | Reaction | अर्थ | Trade |
  |---|---|---|
  | Corrective; तोडलेला area / flip ओलांडला नाही; मग counter-move दिशेने commitment | नवी impulse; reaction = wave 2 (किंवा मोठ्या correction चा B) | Reaction च्या शेवटी counter-move दिशेने (26 Aug) |
  | Impulsive; counter-move ची सुरुवात real break ने परत घेतली | Counter-move = pullback | जुन्या trend दिशेने, पुढच्या pullback वर |
  | अजून ठरलेलं नाही | पालक दिशा अस्पष्ट | Gray-1, trade नाही (12 Aug; 25 Aug 10:45) |

- **पहिल्या ओळीत trade का चालतो:**
  - Primary count ("wave 2 संपला") नुसार पालक दिशा आता बदलली आहे ⇒ P1 प्रमाणे trade.
  - Alternate ("मोठ्या correction चा B संपला") नुसार सुद्धा पुढची चाल (C) त्याच दिशेला ⇒ P2 ची grade वाढ.
  - Alternate खरा असेल तर C ची चाल मर्यादित (C ≈ A [स्रोत: EWP guideline]) ⇒ target दोघांपैकी जवळचा.
- **Gray-1 कधी संपतो:** फक्त रचनेने (वरच्या दोन ओळी), किंवा counter-move च्या सुरुवातीच्या real break ने.
  - ठरीव % वरून नाही, कारण wave 2 ची सामान्य खोली स्वतःच 0.618 सांगितली आहे [स्रोत: Kennedy].
  - वेळ-मर्यादा हवी असेल तर ती setting, आणि Abhi चा निर्णय (I9).
- **S3 ची ओळख [Abhi, 2026-10-09, A2 नंतर]:** एका **रचनेच्या घटनेवरून**: counter-move ने correct होणाऱ्या impulse ची 1H अंतर्गत रचना (शेवटचा confirmed 1H HL / LH) breaks.py च्या real break ने तोडली, आणि origin real-broken नाही. Impulse मध्ये confirmed 1H pivot नसेल ⇒ S3 नाही (`S3_NO_1H_PIVOT`; पुढचा निर्णय Abhi चा).
  - "5-wave / impulsive" ही अट नाही. ते NIFTY वर भेद करत नाहीत (P4), आणि आपोआप ओळखणं कठीण [स्रोत: neowave / automation notes].
  - निर्णय reaction ने (P3).
  - Live मध्ये vision + Evening Plan (Abhi ✔) ची भर; backtest मध्ये फक्त code.
- **सगळ्यात लवकर:**
  - S3 = त्या 1H HL / LH च्या real break चं confirm bar (breaks.py);
  - reaction चा निकाल = P3.
- **Invalidation (पहिल्या ओळीचा trade):**
  - trade: reaction चं टोक;
  - count: counter-move ची सुरुवात [स्रोत: Kennedy stop rule].
- **स्रोत:**
  - EWP outline: "Confirmation that trend change of certain degree comes with 5-wave move of one lesser degree in opposite direction";
  - MTPredictor W3;
  - research-अनुमान (Brooks तर्क): "strong counter spike → at least a second leg".

### S4. Testing: impulse origin चा real break (15 Nov 2021, 16 Feb 2018)
- **गोष्ट:** Correct होणाऱ्या impulse चा origin real-broken (breaks.py). हा origin बहुधा पालकाचा protected level असतो. Origin च्या आतली कोणतीही break S3 आहे, S4 नाही. जुन्या trend चे लोक अडकले; नवी दिशा अजून सिद्ध नाही. पहिला break = इशारा [KB K1; research-अनुमान: Dow / Rhea "failed retest"].
- **सारखी दिसणारी:** S7 (sweep, म्हणजे परत आत).
- **फरक:** breaks.py ची real break (buffer + displacement / acceptance / failed retest) वि. reclaim. एकच व्याख्या [KB भाग G].
- **Trade:**
  - फक्त break दिशेने, तुटलेल्या level च्या flip retest वर: retest corrective, आणि rejection (G4) [Abhi].
  - Retest ची वारंवारता: Bulkowski च्या daily chart patterns मध्ये ~2/3 [स्रोत: Bulkowski; NIFTY intraday वर तपासलेलं नाही].
- **MAGNET:** तुटलेल्या level भोवती closes वर-खाली (16 Feb 13:30) ⇒ बाजार अनिर्णित ⇒ setup नाही.
- **S4 कसा संपतो:**
  - **नवा trend confirm:** break नंतर LH (किंवा HL) तयार होतो, आणि मग break बाजूचं नवं टोक तुटतं [KB K1 "Reversal confirmed"] ⇒ नव्या दिशेने S1 / S5.
  - **Break अपयशी:** जुनं टोक पुन्हा घेतलं, किंवा reclaim + परत real break उलट दिशेने ⇒ जुना trend ⇒ S1.
  - तोपर्यंत जुन्या trend दिशेने trade नाही.
- **सगळ्यात लवकर:** real break चं confirm bar (breaks.py जे सांगते ते).

### S5. मजबूत trend मधला उथळ flag (28 Sep)
- **गोष्ट:** Trade degree वर wave 3 / C चालू; एक बाजू पूर्ण नियंत्रणात; counter-traders ला वेळ मिळत नाही.
  - Brooks: tight channel मध्ये pullbacks "last for only one to three bars";
  - micro channel जितका मजबूत, "the more likely that the first pullback will fail to reverse the trend".
- **सारखी दिसणारी:** S8: तिथे with-trend legs लहान होत जातात आणि pullbacks मोठे [स्रोत: structure notes].
- **फरक:**
  - flag मधल्या candles impulse पेक्षा अरुंद, futures volume कमी;
  - आधीचे with-trend legs लहान होत नाहीत;
  - divergence नाही.
- **फक्त दिसणारी flag रचना चालते:**
  - रचना Abhi ने मंजूर केलेल्या G8 प्रमाणे: "जलद (2–6 candles, flag / छोटा ABC)" [KB H, Abhi].
  - त्यापेक्षा लहान pause (1 candle) म्हणजे setup नाही (S12 "आजपर्यंत pullback नाही").
  - Structure notes चा "4–20 bars" हा संशोधकाचा code-साठीचा प्रस्ताव आहे [research-अनुमान]. तो G8 शी जुळत नाही, म्हणून वापरायचा नाही.
- **Area:**
  - flag च्या आत / लगेच आधीचा तुटलेला swing (polarity);
  - शेवटच्या displacement चा base;
  - flag ची कड, **फक्त** flag पुरेसा लांब असेल तर (त्याचे pivots decision bar आधी confirm झालेले असावेत). ही K6 ची long trendline नाही; वेगळं साधन. 2–3 candles च्या flag मध्ये confirmed pivots नसतात ⇒ फक्त पहिले दोन.

  जुना मोठा zone असेलच असं नाही. 28 Sep ला code फक्त zones पाहत होता [अनुमान; KB E1 ची चूक].
- **खोली:** < 38.2% इथेच valid (G8: 23.6–38.2% [KB H, Abhi]).
- **Trade:** flag च्या शेवटी trend दिशेने commitment (G8). Flag breakout वर नाही [Abhi].
- **Invalidation:**
  - trade: flag चं टोक;
  - count: (ii) ⇒ (i) ची सुरुवात; (iv) ⇒ (i) चं टोक [नियम R1, R3].
- **सावधानता:** pennant नंतरची चाल आधीच्या चालीइतकी फक्त ~30% वेळा जाते [स्रोत: Bulkowski] ⇒ target dashboard वर.

### S6. बाजूचा correction (triangle / flat; wave 4 / B)
- **गोष्ट:** दोन्ही बाजू थकलेल्या; वेळ जातो, range आकुंचन पावते. "Triangles take time and go sideways" [स्रोत: EWI].
- **सारखी दिसणारी:** S9.
- **S6 वि. S9 (real time):** फक्त "आधी स्पष्ट impulse आला होता का" [अनुमान].
- **Correction संपला का (Gray-2):** commitment bar ला legs ची संख्या पूर्ण असेल तर ठरवता येतो (flat: A-B-C; triangle: पाच legs). पण combination (W-X-Y) चा alternate राहतोच ⇒ trade invalidation (C / E चं टोक) हेच संरक्षण.
- **Trade:** E-end / C-end (G3, G9). आत (B, D, X) नाही [KB K3 बंदी].
- **धोके:**
  - triangle लवकर "पूर्ण" म्हणणं: "Many analysts are fooled into labeling a completed triangle way too early" [स्रोत: EWI].
  - Expanding triangle / diametric मध्ये Type-2 confirmation "can provide false signals" [स्रोत: NEoWave QOW 1109] ⇒ **पुरावा (−)**; बंदी हवी का हा Abhi चा निर्णय [अनुमान].
- **Invalidation:** C चं टोक; wave 4 असेल तर wave 1 चं टोक (R3).

### S7. Expanded flat / spring
- **गोष्ट:** B नवा extreme करतो ⇒ breakout traders आत येतात ⇒ C त्यांचे stops घेत A च्या टोकापलीकडे जातो ⇒ परत आत [स्रोत: KB K3; Wyckoff spring; Osler stop clusters].
- **सारखी दिसणारी:** S4.
- **फरक:** reclaim वि. real break (breaks.py).
- **Trade:** sweep + reclaim नंतरची commitment (G2).
- **Invalidation:** C चं टोक.
- **सगळ्यात लवकर:** reclaim close वर. Sweep bar वर नाही [स्रोत: areas notes].

### S8. Trend थकतोय (trade degree वर)
- **गोष्ट:** Trend दिशेचे शेवटचे लोक येतात: with-trend legs लहान, pullbacks मोठे, overlap वाढतो, divergence [स्रोत: EWP: fifth waves "less dynamic than third waves"; structure notes; Bulkowski rising wedge].
- **सारखी दिसणारी:** S5.
- **Trade:**
  - नवे with-trend trades कमी विश्वासाचे (पुरावा, size setting) [research-अनुमान; **NIFTY वर मोजलेलं नाही** ⇒ P9 प्रमाणे macro / sentiment सोबत IS वर तपासायचं; तोपर्यंत size वर परिणाम नाही, फक्त नोंद].
  - Wave 4 end ⇒ wave 5 (G9) चालतो; truncation धोका [KB H].
  - Wave 5 चा लगेच fade नाही [KB K3]. Reversal ची पहिली impulse आली की ती S3 ⇒ reaction ची वाट.
  - G7 हा वेगळा approved अपवाद (P1).
- **फरक लक्षात ठेवा:** trend दिशेचा ending diagonal (S8) आणि correction च्या C मधला ending diagonal (S1, 7 Oct) वेगळे.
- **सगळ्यात लवकर:** "legs लहान होत आहेत" हे प्रत्येक नवा leg confirm झाल्यावर. Ending diagonal पूर्ण झाल्याचं शेवटीच कळतं.

### S9. Range / sideways (G10: range कड) [Abhi, 2026-10-08: sideways trades सुद्धा घ्यायचे]
- **गोष्ट:**
  - कोणत्याही बाजूचं नियंत्रण नाही. Buyers खालच्या कडेवर, sellers वरच्या कडेवर बचाव करतात; मधल्या भागात बाजार भटकतो.
  - खालच्या कडेखाली stop-losses जमा होतात. Sweep होऊन परत आत आला की ते stops संपतात, आणि पलीकडे ढकलायला कोणी उरत नाही [स्रोत: Osler stop clusters; Wyckoff spring / upthrust; areas notes].
  - Range मध्ये premium selling ला वेळ (theta) फायदेशीर [research-अनुमान: sideways waves suit selling premium].
- **ओळख (real time):**
  - **Trade degree** (15M) चा market_state = RANGE (repo व्याख्या: नवे swings, पण कोणताही निर्णय नाही; KB K1). Range edges चे pivots decision bar आधी confirm झालेले.
  - कडा = range चे confirmed high / low. Repo च्या equal highs / liquidity व्याख्येनुसार त्यांच्याशी जुळणारे levels, आणि PDH / PDL फक्त ते कडेवर असतील तर. Range रुंद करण्यासाठी नाही.
  - **पालक degree** (HTF market_state) वर trend असेल ⇒ S6 + S9. पालक सुद्धा RANGE / trend नाही ⇒ शुद्ध S9.
  - **Range ची उंची risk च्या तुलनेत पुरेशी असली पाहिजे.** हे R:R ≥ 3 (A3) मधूनच आपोआप ठरतं; वेगळा आकडा नाही.
- **सारखी दिसणारी:**
  1. **S6** (trend मधला बाजूचा correction: triangle / flat). फरक: आधी पालक degree वर स्पष्ट impulse आहे का.
  2. **Range ची खरी break** (breakout). फरक: breaks.py ची real break / acceptance वि. reclaim.
- **Trade (G10):**
  - **खालची कड ⇒ bull put; वरची कड ⇒ bear call.** इथे दिशा पालक trend वरून नाही, तर कडेवरून ठरते. P1 चा स्पष्ट अपवाद, स्वतंत्र scorecard सह.
  - Simple Core प्रमाणेच: कडेवर pause + commitment candle (बंद).
  - Sweep + reclaim (कडेपलीकडे wick / थोडा close, मग परत आत close) असेल तर पुरावा मजबूत (KB D: LQ).
  - Sweep नसताना कडेवर साधी rejection सुद्धा चालते, पण पुरावा कमी.
  - Range च्या मध्यात entry नाही. Area नाही; MAGNET.
- **S6 + S9 एकत्र** (range हा मोठ्या trend मधला correction असू शकतो) [प्रस्ताव, default]:
  - फक्त trend दिशेची कड tradable;
  - विरुद्ध कड ⇒ B च्या आतला trade (S11) ⇒ नाही.
  - पालक degree वर trend नसेल तेव्हाच दोन्ही कडा.
- **Invalidation:**
  - trade: sweep चं टोक (sweep नसेल तर कड) + buffer (बाकी trades सारखंच dashboard SL buffer setting; नवा आकडा नाही);
  - range संपली: कडेची real break (breaks.py) ⇒ S4 (flip retest, break दिशेने). Break अपयशी (परत आत real break) ⇒ पुन्हा S9.
- **Target:** range ची विरुद्ध कड (किंवा dashboard चा target_mode).
- **सगळ्यात लवकर कधी कळतं:**
  - RANGE हे market_state ने confirm केल्यावर;
  - sweep हे reclaim close वर (sweep bar वर नाही).
- **प्रामाणिक मर्यादा:**
  - Range-कड trading चा प्रकाशित पुरावा कमकुवत आहे. Brooks चं "most breakout attempts from trading ranges fail" हे practitioner मत आहे.
  - Raschke / Connors च्या "Turtle Soup" (false breakout) चा vendor backtest costs नंतर कमकुवत ("D" rating) [स्रोत: Oxford Capital].
  - Trading-range-break नियम 1986 नंतर out-of-sample टिकले नाहीत [स्रोत: Sullivan, Timmermann & White].
  - ⇒ PAPER मध्ये स्वतंत्र scorecard, आणि IS वर आधी मोजमाप (कड टिकली / तुटली, sweep सह / शिवाय).
  - **IS चा पहिला निकाल (A5) [NIFTY]:** कडेवरून उलट trade केला तर फक्त ~30% वेळा भाव विरुद्ध कडेपर्यंत गेला.
  - **[Abhi, 2026-10-09]:** G10 सध्या **shadow मध्ये**: signal आणि नोंद होईल, PAPER trade नाही. Sweep + reclaim आणि sweep शिवाय यांचे वेगळे निकाल (SL आधी target गाठला का) आल्यावर Abhi PAPER ON करेल.

### S10. Gap दिवस
- **मुख्य तत्त्व:**
  - Gap चा प्रकार 09:15 ला ठरत नाही. "By the time you properly identify them, the move is nearly over" [स्रोत: Bulkowski]; LuxAlgo: label "largely retrospective".
  - 09:15 ला फक्त context माहीत असतो: कुठे (range आत / बाहेर; trend मध्ये कुठे), आकार (daily ATR14 च्या पटीत, KB G), आणि news.
  - निर्णय पहिल्या 2–6 bars (15M) मध्ये, gap **स्वीकारला की नाकारला** यावरून, दर bar पुन्हा तपासून [KB K13].
- **उप-परिस्थिती (KB K13):**
  - **B: trend दिशेचा gap** ⇒ पहिल्या pullback ची वाट; pullback नाही तर trade नाही.
    - 7 Oct: gap down trend दिशेने; 09:30 entry = chase ⇒ नाही.
    - 12:15: gap fill rally (C-diagonal) trendline + seller zone वर अडली, आणि commitment ⇒ bear call ✔.
  - **A: trend विरुद्ध gap अपयशी (नाकारला)** ⇒ trend दिशेने, पहिल्या pullback नंतर.
  - **Trend विरुद्ध gap स्वीकारला** ⇒ ही counter-move ⇒ S3 / S4.
  - **G7: trend दिशेचा मोठा gap major HTF zone मध्ये, नाकारला** ⇒ पहिल्या pullback नंतर (approved अपवाद, P1).
  - **Range आतला लहान gap** ⇒ सामान्य दिवस.

### S11. B wave सापळा
- **गोष्ट:** मोठ्या correction मधली जोरदार उलट चाल; गर्दीला वाटतं trend परत आला. "B waves are phonies. They are sucker plays, bull traps" [स्रोत: EWP].
- **Trade:**
  - B च्या आत नाही [KB K3].
  - B-end → C, जेव्हा तो ABC ज्या trend ला correct करतो त्याच्या विरुद्ध असतो ⇒ OFF [Abhi] (P1).
  - S3 पहिल्या ओळीत primary नुसार trend च बदलला आहे (counter-move = नवी impulse). त्यामुळे तिथला trade "ज्या trend ला correct करतो" त्याच्याच दिशेने आहे; B → C नाही.
- **मर्यादा:** "आपण B मध्ये आहोत" हे बहुतेक वेळा नंतरच कळतं ⇒ live मध्ये Gray-1 हेच संरक्षण.

### S12. विशेष वेळा आणि execution
- **पहिली 30 मिनिटं:** bars रुंद ⇒ पुरावा कमी (KB D: TM −5) [स्रोत: session notes; KB K14].
- **Event दिवस:** VIX आधीच भरलेला, नंतर IV crush ⇒ KB D: EV [स्रोत: session notes].
- **Pullback दरम्यान VIX उडी** ⇒ "फक्त pullback" वरचा विश्वास कमी (KB D: VX) [research-अनुमान, practitioner-level].
- **"आजपर्यंत pullback नाही" (trend day):** setup नाही; chase बंदी [Abhi; A3]. हा नवीन gate नाही, A1 ची व्याख्या आहे.
- **15:15 च्या bar वर signal [Abhi, 2026-10-09: `eod_signal_carry = recheck`]:** दुसऱ्या दिवशी 09:15 ला आपोआप entry नाही.
  - रात्रीचा gap आणि उघडण्याच्या 30 मिनिटांचा कमी विश्वास (KB D: TM −5) यामुळे तो signal दुसऱ्या दिवशी S10 नुसार नव्याने वाचायचा.
  - Area अजून वैध असेल तर तिथे नवी commitment हवी.
  - Invalidation पार झाला ⇒ रद्द.
- **MR आणि सामान्य खोली VIX नुसार बदलते** [research-अनुमान] ⇒ म्हणूनच P4.

---

## I4. दोन counts कसे वापरायचे (code आणि vision)

1. **Evening Plan (Weekly → Daily → 1H):** प्रत्येक degree साठी primary आणि alternate. प्रत्येकासाठी:
   - पुढचं अपेक्षित पाऊल;
   - invalidation;
   - confirmation;
   - आघाडी (स्पष्ट / बरोबरी).
2. **Intraday, प्रत्येक बंद 15M bar वर:**
   - परिस्थिती (S1–S12; जोडी असेल तर I2 चा precedence);
   - P2 चा क्रम (Gray-1 → Gray-2 → trade → grade वाढ);
   - trade असेल तर त्या परिस्थितीचा area (I3) आणि Simple Core ची commitment.
3. **Invalidation झाला ⇒** तो count काढा; alternate primary; नवा alternate. वरची degree शाबूत असेल तर तीच ठेवा [स्रोत: WaveBasis].
4. **Vision:**
   - code च्या counts शी सहमत / असहमत, आणि तिला दिसणारा वेगळा count.
   - Chart decision bar वर कापलेला (पुढचं काही नाही).
   - किंमती code च्या.
5. **Gray चं मोजमाप:**
   - gray मुळे सोडलेल्या संधींपैकी किती वेळा एक दिशा 1:3 ने यशस्वी झाली असती;
   - जास्त असेल तर अपुरी परिस्थिती शोधायची (I6). नियम सैल करायचा नाही.
6. **Labels फक्त त्या bar ला माहीत असलेले:**
   - "हा B होता", "(2) संपला" असे hindsight labels tests मध्ये नाहीत.
   - Tests मध्ये फक्त decision bar पर्यंत दिसणारी माहिती.

---

## I5. आकड्यांचं धोरण

| वर्ग | उदाहरण | काय करायचं |
|---|---|---|
| **व्याख्या** | Impulse origin real break, Elliott R1–R11, बंद candle | Code मध्ये ठेवा |
| **Abhi** | R:R ≥ 3; valid खोली 38.2–80%; G8 23.6–38.2%; pullback volume कमी | Dashboard setting, default = Abhi चा |
| **Research / practitioner** | sweep 0.1–1.0 MR (areas notes) | Setting, स्रोतासह; NIFTY वर तपासायचा. **Research notes मधले "codable rules" चे आकडे** (उदा. flag 4–20 bars, ≤ 0.5 pole) संशोधकाचे प्रस्ताव आहेत ⇒ "अंदाज" वर्गात |
| **NIFTY वर मोजलेला** | उदा. counter-move overlap चं वितरण | IS वर मोजा, VAL वर तपासा |
| **अंदाज** | commitment_vs_pause 1.5, touch 0.3 MR, "≥ 3 खुणा", flag ≤ 50%, lookback लांबी | **सापेक्ष तुलनेत बदला**, नाहीतर setting + sensitivity (किमान 3 मूल्ये) + Abhi चा निर्णय |

Real break साठी एकच व्याख्या: breaks.py (KB G). इतर कुठलीही "N closes" व्याख्या वापरायची नाही.

**Constants register:** Trade session ने entry engine मधल्या **प्रत्येक** आकड्याची यादी बनवायची. प्रत्येकासाठी:
- नाव;
- मूल्य;
- file:line;
- वर्ग;
- कारण.

"अंदाज" वर्गाची sensitivity, आणि कोणते सापेक्ष तुलनेत बदलता येतील याचा प्रस्ताव.

---

## I6. नवीन उदाहरण आलं की प्रक्रिया (overfitting थांबवण्यासाठी)

1. **परिस्थिती ओळखा (S#).** कुठलीच बसत नसेल ⇒ नकाशात भर (Abhi सोबत); code मध्ये थेट नियम नाही.
2. **चूक कुठल्या थराची:**
   - **वाचन:** swing / area / degree / count; area त्या वेळी अस्तित्वात नव्हता;
   - **निर्णय:** परिस्थितीचा नियम चुकीचा लागला;
   - **अंमलबजावणी:** bug.

   दुरुस्ती त्याच थरात.
3. **संच:** त्या परिस्थितीची आणि तिच्यासारख्या दिसणाऱ्या परिस्थितीची अनेक उदाहरणं IS मधून (Golden Gallery पद्धत). Labels decision bar पर्यंतच्या माहितीवर.
4. **बदल संचावर तपासा.** काय मोडलं ते अहवालात.
5. **नवीन आकडा फक्त I5 प्रमाणे.**
6. **Batch मध्ये एकच एकत्रित बदल.**
7. **Abhi चा निर्णय बाकी असलेल्या उदाहरणांवर** नकाशाचं उत्तर **आधी** लिहायचं, मग Abhi चा निर्णय. उलट क्रमाने नाही.

---

## I7. Abhi च्या उदाहरणांवर नकाशाची तपासणी (decision bar ला जे माहीत होतं त्यावर)

| दिवस | परिस्थिती | P2 चा क्रम | नकाशाचं उत्तर | Abhi |
|---|---|---|---|---|
| 12 Aug 2026 | S3: 24,677 → ~24,000 (58%), impulsive; reaction अजून सुरू नाही | Gray-1 (S3 reaction उघडा). शिवाय: uptrend count मध्ये 5-wave घसरण = फक्त A ⇒ Gray-2 (R4); नव्या downtrend count मध्ये bull put पालकविरुद्ध (P1). तिन्ही मार्गांनी नाही. | Bull put नाही | ✔ नाही |
| 25 Aug 10:45 | S3, reaction चालू (त्या वेळी "B" हे माहीत नव्हतं) | Gray-1 (reaction उघडा) | Buy नाही | ✔ नाही |
| 26 Aug | S3, reaction corrective; 24,380–24,420 flip ओलांडली नाही; खाली commitment | Gray-1 संपला (P3 पहिली ओळ) ⇒ (2) नव्या खालच्या sequence मध्ये ⇒ पालक खाली. Gray-2: तीन legs, C (24,380–24,420) A (24,330) च्या पलीकडे ⇒ ठरवता येतं. Alternate (B-end) सुद्धा खाली ⇒ grade वाढ. | Bear call; target दोघांपैकी जवळचा; R:R ≥ 3 dashboard वर | ✔ bear |
| 22 Sep | S6: wave (4) end ~23,500 | पालक: (4) खालच्या (1)–(5) मध्ये ⇒ खाली. Gray-2: (4) ची legs पूर्ण (flat / zigzag) आणि commitment ⇒ ठरवता येतं (Trade session ने bars वर तपासायचं) | G9 bear call; wave 5 truncation सावधानता | ✔ bear |
| 28 Sep | Flag 11 candles ⇒ G8 नाही ⇒ **S1** (Abhi, 2026-10-08: G8 ची व्याख्या बदलायची नाही). मोठ्या degree चा wave (5) = P1 आजोबा पुरावा | पालक खाली | S1 bear: area = तुटलेला swing 23,021 / displacement base 22,856–22,912, + commitment; आजोबा wave 5 फक्त नोंद | ✔ bear |
| 31 Aug | Wave (3) चालू (26 Aug नंतर) ⇒ S1 / S5 | — | Commitment कमकुवत आणि R:R 1:1.1 < 3 ⇒ A3 ⇒ नाही | ✔ नाही |
| 7 Oct 09:30 | S10-B: trend दिशेचा gap, pullback नाही | — | नाही (chase) | ✔ नाही |
| 7 Oct 12:15 | S10-B → S1: gap fill rally, C-diagonal trendline + seller zone वर | पालक (1H) खाली: protected H 22,809 (code चं वाचन 7 Oct review मध्ये ✔) | G5 bear call | ✔ bear — पक्का (Abhi 2026-10-09, run2 review: 12:15 = C-end). Code चं "B च्या आत (S11)" = वाचनाचा दोष (count score tie) ⇒ I6 |
| 16 Feb 2018 13:30 | S4, MAGNET | — | Setup नाही | बरोबर (session) |
| 16 Feb 2018 09:30 | आधीची चाल 144% ⇒ origin real-broken ⇒ S4 (S3 नाही) | — | **नकाशाची अट:** 09:30 पर्यंत break अपयशी ठरला असेल (उलट real break, किंवा जुनं टोक) ⇒ जुना downtrend ⇒ S1 ⇒ area + commitment असेल तर setup शक्य. नाहीतर S4 ⇒ फक्त वरच्या दिशेने flip retest ⇒ bear नाही. | **Trade session ने decision bar पर्यंतच्या data वर ही अट तपासून नकाशाचं उत्तर लिहायचं; मग Abhi ✔/✘** |
| 15 Nov 2021 13:00 | S4 (session: जुनं टोक 18,604; 18,210 फक्त local high; testing) | — | **नकाशाची अट:** break real (breaks.py) असेल आणि 13:00 चा retest corrective + rejection असेल ⇒ G4 bear. नाहीतर नाही. | **तसंच: आधी अट तपासून उत्तर, मग Abhi** |

**निष्कर्ष:**
- 12, 25 आणि 26 Aug ला तीन वेगळे नियम लागत नाहीत. P2 चा क्रम (Gray-1) आणि P3 (reaction) तिन्ही दिवसांचं उत्तर देतात.
- 28 Sep चा प्रश्न "touch" नव्हता, तर "या परिस्थितीचा area कोणता" हा होता (P5).
- **मर्यादा:** 28 Sep नंतरचा Abhi चा count माहीत नाही. 7 Oct ची पालक दिशा code च्या मान्य 1H वाचनावरून घेतली आहे (protected H 22,809; 1 Oct चा low 22,217 पासून ABC तेजी; 2–4 Oct बाजार बंद [Sep–Oct review charts]).
- **मर्यादा:** हे 11 दिवस फक्त **तपासणी** आहेत. खरी चाचणी I6 च्या IS संचांवर.

---

## I8. Code आणि vision मध्ये काय बदलेल (उच्च पातळी; तपशील मंजुरीनंतरच्या एकत्रित prompt मध्ये)

1. **Simple Core तसाच** (area → pause → commitment). त्याच्या आधी दोन गोष्टी: परिस्थिती (S#) आणि पालक दिशा, P2 च्या क्रमाने.
2. **`POSSIBLE_REVERSAL` flag जातो.** त्याची जागा S3 + Gray-1 + reaction test (P3) घेतात.
3. **S3 / S4 सीमा:** correct होणाऱ्या impulse च्या origin चा real break (breaks.py) ⇒ S4. Origin च्या आतली कोणतीही break ⇒ S3.
4. **Area sources परिस्थितीनुसार:**
   - S5: flag कड + तुटलेला swing;
   - S4: flip;
   - बाकी: KB टप्पा 3.
5. **प्रत्येक signal आणि "नाही" ची नोंद:** S#, दोन counts, पालक दिशा, gray प्रकार, invalidation.
6. **पुराव्यांचं NIFTY मोजमाप (P4)**, आणि **constants register (I5).**
7. **Evening Plan:** प्रत्येक degree चे दोन counts, आघाडी, आणि उद्याच्या अपेक्षित परिस्थिती.
8. **Vision playbook:** हा नकाशा मजकूर म्हणून.
9. **Tests:** I7 चा तक्ता (decision-bar labels), आणि I6 चे संच.

---

## I9. Abhi कडून हवे निर्णय

1. ~~Gray-1 आणि Gray-2~~ ⇒ **ठरलं:** Abhi दर दिवशी Evening Plan मधून ठरवतो (P2).
2. ~~पालक दिशा (P1)~~ ⇒ **ठरलं:** KB भाग G ची ओळ बदलायची (Abhi ✔).
3. **S3 मधला gray:** default = फक्त रचनेने संपतो, वेळ-मर्यादा नाही (Abhi बदलेपर्यंत).
4. ~~S9 range कड~~ ⇒ **ठरलं:** sideways trades सुद्धा (G10, स्वतंत्र scorecard). S6 + S9 मध्ये फक्त trend दिशेची कड, हा default; बदलायचा असेल तर Abhi सांगेल.
5. **S6 expanding triangle:** default = फक्त नकारात्मक पुरावा, बंदी नाही.
6. **7 Oct चा count:** 7 Oct 12:15 पर्यंतचे bars पाहून तुमचा count (त्यानंतरचे bars न पाहता)?
7. **16 Feb 2018 09:30 आणि 15 Nov 2021 13:00:** वर नकाशाचं उत्तर आधीच लिहिलं आहे. आता charts पाहून ✔ / ✘.
8. **नकाशा पुरेसा आहे का?** एखादी परिस्थिती सुटली आहे का?

**G-MAP1 चे निर्णय (Abhi, 2026-10-09 08:36):**
- Commitment candle ची ताकद impulse च्या candles च्या तुलनेत (`commit_vs_impulse`). Gate ला threshold लागतो, आणि Abhi ने 17 signals वरून मूल्य न निवडण्याचं ठरवलं. म्हणून टप्पा B मध्ये हा **फक्त report** (Claude ची अंमलबजावणी-निवड, Abhi चा थेट आदेश नाही). Gate सध्याचाच राहील. सापेक्ष gate कोणत्या मूल्याने, आणि तोपर्यंत जुना MR gate ठेवायचा का, हा निर्णय Abhi PR वर घेईल.
- 3-close फक्त रचनेच्या breaks ना; Elliott R1–R11 भावावरून.
- पुराव्यांची यादी गोठवली (P4).
- S3 ची ओळख रचनेच्या घटनेवरून (S3).
- पालक दिशा: `parent_source`, आणि आधी तुलना (P1).
- G10 सध्या shadow (S9).
- `gray_size` = अर्धे lots; `eod_signal_carry` = दुसऱ्या दिवशी नव्याने वाचन.
- Target साठी तोच impulse, ज्याचा correction आपण trade करतो (degree-सुसंगत).
- 28 Sep = S1; `g9_tier = full`; `target_mode = impulse_end` (2026-10-08 रात्री).

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
