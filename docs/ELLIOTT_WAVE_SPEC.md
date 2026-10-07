# प्रत्येक degree वर pullback विका, breakout कधीच नाही

**मुख्य निष्कर्ष:** Elliott Wave चा सर्वात बचाव करता येणारा trading उपयोग भाकितासाठी नाही. तो आहे **"कोणत्या corrective wave चा शेवट आपण विकतोय, आणि कोणत्या किमतीला हा count मरतो"** हे यांत्रिकपणे ठरवण्यासाठी. Practitioners चं साहित्य हे स्पष्ट सांगतं: Kennedy (EWI) च्या शब्दांत "waves (2), (4), (5) and (B) are actually setups for high-probability trades in waves (3), (5), (A) and (C)" ([Kennedy, EWI](https://elliottwaveplus.com/how-the-wave-principle-can-improve-your-trading/)). बहुतेक setups चा hard stop एका Elliott **नियमाला** बांधलेला असतो (अपवाद: S6b expanded flat आणि S8 X-wave, जिथे inv हा **[अनुमान]** स्तर आहे). म्हणूनच तो bull put किंवा bear call च्या short strike मध्ये थेट भाषांतरित होतो. हा अहवाल आधीच्या दोन Elliott अहवालांची जागा घेतो. त्यातले चार दोष इथे दुरुस्त केले आहेत. पहिला दोष: HTF trend ला hard gate मानलं होतं. आता HTF हा **context** आहे, म्हणजे size आणि target ठरवणारा, gate नाही. दुसरा: min_dte = 2 चुकीचं होतं. आता **फक्त आजची expiry टाळायची, 1 DTE चालतो**. तिसरा: "correction ला impulse पेक्षा जास्त वेळ" हा नियम पडताळलेला नव्हता. Neely चे पडताळलेले नियम आहेत t(w2)>t(w1) **किंवा** t(w4)>t(w3), आणि zigzag/flat मध्ये t(c) ≤ t(a)+t(b). चौथा: Kennedy चे break-triggers हे breakout entries आहेत, म्हणून त्यांना pullback-पर्याय दिले आहेत. पुढे अहवालात हे सगळं येतं: 14 setups चा catalogue, degree-निहाय invalidation hierarchy, strike सूत्र `max(invalidation+buffer, k·S·IV·√(DTE/252))`, management, Oct 2026 चे India contract facts, सर्व dashboard settings (defaults सह), code साठी data structures आणि algorithm, P1–P16 backtest protocol, आणि 5–6 Oct 2026 च्या NIFTY वर worked example. त्या उदाहरणात spec ने B-end आणि C-(ii) वरचे दोन bull puts स्वीकारले, दोन्ही OTM राहिले, आणि 09:50/10:15 चे A-end bear calls नाकारले. **प्रामाणिक मर्यादा:** Fibonacci आणि time ratios चा पुरावा नकारात्मक आहे. कोणत्याही Elliott setup चा प्रकाशित, स्वतंत्र win-rate अस्तित्वात नाही. म्हणून हा spec edge असल्याचा दावा नाही. तो edge **तपासण्याचं** साधन आहे.

**लेबलांचा अर्थ:**

| लेबल | अर्थ |
|---|---|
| **[नियम]** | मूळ लेखकाने (Elliott, Frost & Prechter, Neely) अटळ म्हटलेला. मोडला तर count मेला. |
| **[मार्गदर्शक]** | मूळ लेखकाने "सहसा / प्रवृत्ती" म्हटलेलं. Score म्हणून वापरायचं, gate म्हणून नाही. |
| **[दावा]** | Practitioner, vendor किंवा लेखकाचं विधान किंवा आकडा, स्वतंत्रपणे न तपासलेला. |
| **[पुरावा]** | पद्धत स्पष्ट असलेला शैक्षणिक किंवा अधिकृत अभ्यास. दिशा (+/−) सोबत. |
| **[अनुमान]** | या अहवालाचं स्वतःचं design किंवा संश्लेषण. स्रोतात थेट नाही. Code मध्ये parameter म्हणून ठेवा. |

---

## 1. दुरुस्त्या: चार चुका आणि त्यांच्या जागी काय

हा विभाग सगळ्यात आधी आहे, कारण पुढचा प्रत्येक भाग या दुरुस्त्यांवर उभा आहे. आधीचे दोन अहवाल ("Elliott Wave सिद्धांत संपूर्ण अभ्यास" आणि "Elliott Correction Waves Study") आता **रद्द आणि superseded** समजावेत. त्यांतला जो भाग अजून वैध आहे तो या अहवालात पुन्हा लिहिला आहे.

### दुरुस्ती 1: HTF trend हा gate नाही, context आहे

**आधी काय होतं.** आधीच्या अहवालाच्या P2 नियमात "HTF (1H/daily) swing structure च्या दिशेनेच spread" अशी अट होती. त्यामुळे trend विरुद्धच्या प्रत्येक motive wave वरचा trade blocked झाला. उदाहरणार्थ, मोठ्या downtrend मधल्या correction चा C wave (वर) bull put ने trade करता आला नसता. 5 Oct चा B→C bull put हाच प्रकार होता.

**का चुकीचं.** स्रोत असा gate कुठेच देत नाहीत. Kennedy च्या setup यादीत (B) → (C) आहे ([Kennedy, EWI](https://elliottwaveplus.com/how-the-wave-principle-can-improve-your-trading/)) **[दावा]**. ELWAVE म्हणतो "only waves 1,3,5, A and C can be impulsive waves", आणि "wave C in a correction" ला wave 3 सारखीच "strong probability" देतो ([ELWAVE FAQ](https://elwave.com/elwave/faq/principle/trading_ew.html)) **[दावा]**. Kennedy "trade with the one larger trend" असं म्हणतो खरं ([Kennedy Visual Guide sample](https://download.e-bookshelf.de/download/0000/8049/21/L-G-0000804921-0007908122.pdf)) **[मार्गदर्शक]**. पण तो conflict **position sizing** ने सोडवतो: divergence दिसली तर partial entries आणि tight stops ([Traders.com reprint](https://traders.com/reprints/pdf_reprints/Expired/EW_KENNEDY.pdf)). Counter-trend trade वर बंदी हा कुठल्याही free primary स्रोतातला नियम नाही. Research notes मध्येच हे gap म्हणून नोंदवलं आहे.

**आता काय.** **[अनुमान]** **Degree-aware trading.** Bot ज्या degree D वर corrective wave संपलेली ओळखतो, त्याच degree च्या पुढच्या motive wave चा trade घेतो. D+1 आणि D+2 (मोठ्या degrees) तीन गोष्टी ठरवतात:

1. **Size multiplier** (Tier A/B/C).
2. **Target zone** आणि exit: C wave असेल तर target bounded, wave 3 असेल तर open.
3. **Strike conservatism.**

Gate फक्त dashboard वर `htf_gate_enabled = true` केलं तरच लागतो. Default `false` आहे.

### दुरुस्ती 2: min_dte = 2 चुकीचं. फक्त आजची expiry टाळायची

**आधी काय होतं.** min_dte = 2 सुचवलं होतं.

**तुमचा खरा नियम.** आज expiry दिवस नसेल तर **current weekly**. आज expiry दिवस असेल तर **next weekly**. म्हणजे सोमवारी Tuesday expiry साठी **1 DTE trade चालतो**. NIFTY weekly Tuesday ला expire होते ([NSE NIFTY 50 F&O](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50)) **[पुरावा]**.

**आता काय.** Setting `expiry_rule = "current_unless_today_expiry"` (default). `min_dte` ही setting **पूर्णपणे काढून टाकली** आहे. तिच्या जागी फक्त एक पर्यायी, default-बंद `min_dte_override` ठेवला आहे. 1 DTE वर gamma जास्त असतो, आणि त्याची काळजी strike सूत्र, credit guard आणि exits घेतात. Expiry टाळणं हे काम त्यांचं नाही (विभाग 8).

### दुरुस्ती 3: "Correction ने impulse पेक्षा जास्त वेळ घ्यायलाच हवा" हा पडताळलेला नियम नाही

आधीच्या corrective अभ्यासात हे NEoWave **नियम** म्हणून दिलं होतं (R6). Neely च्या पानांवर ते त्या स्वरूपात सापडत नाही. **पडताळलेले Neely time-नियम** असे आहेत:

1. Standard impulse मध्ये "wave-2 normally takes more time than wave-1, **OR** wave-4 takes more time than wave-3". Terminals ला यातून सूट आहे ([NEoWave QOW 3782](https://www.neowave.com/qow/qow-archive-3782.asp)) **[नियम, Neely]**. ही OR-अट आहे. एकट्या wave 2 ला wave 1 पेक्षा जास्त वेळ लागायलाच हवा असं नाही.
2. Flat आणि zigzag मध्ये "wave-c should never consume more time than the total of waves-a + b combined" ([NEoWave QOW 3518](https://www.neowave.com/qow/qow-archive-3518.asp)) **[नियम, Neely]**. त्याच पानावर अपवाद आहे: "the last leg of a Triangle or Terminal will 'Push' beyond the ideal time targets". म्हणून C हा ending diagonal (Terminal) असेल, तर हा time-नियम लागू नाही.

दोन्ही नियम Neely ने स्वतः ठामपणे मांडलेले आहेत. त्यांची प्रकाशित सांख्यिकीय पडताळणी शून्य आहे, आणि QOW 3782 मधला शब्द "normally" आहे. म्हणून default वापर score/delay आहे, hard invalidation नाही.

**आता काय.** `pullback_time_ratio` = bars(correction) / bars(impulse) हा फक्त **feature** आहे, gate नाही. Code मध्ये दोन flags असतील:

- `impulse_time_ok = t(w2) > t(w1) OR t(w4) > t(w3)`. हा फक्त पूर्ण 5-wave impulse validate करताना वापरायचा, terminal/diagonal नसेल तेव्हा.
- `c_time_violation = t(c) > t(a) + t(b)`, जिथे t(·) = त्या leg चे bars (structure TF वर, पहिल्या pivot च्या bar पासून शेवटच्या pivot च्या bar पर्यंत), आणि t(c) = C च्या origin पासून चालू bar पर्यंत. हा flag लागला तर तो साधा zigzag/flat नाही. Correction complex होतेय (double, combination). म्हणून C-end वरची entry पुढे ढकलायची. **अपवाद:** C ending diagonal म्हणून label असेल तर flag लावू नका (QOW 3518 चा Terminal अपवाद).

### दुरुस्ती 4: Kennedy चे break-triggers म्हणजे breakout entries. ते निषिद्ध, त्यांचे pullback-पर्याय खाली

Kennedy तीन ठिकाणी break वर entry घेतो:

- Impulse नंतर "a break below wave (iv) of 5".
- Ending diagonal नंतर "a break of the extreme of wave 4" ([Kennedy Visual Guide sample](https://download.e-bookshelf.de/download/0000/8049/21/L-G-0000804921-0007908122.pdf)) **[दावा]**.
- Triangle च्या B–D line चा break. हा सर्वसाधारण practitioner trigger आहे.

हे तिन्ही **breakout entries** आहेत, आणि तुमच्या पद्धतीत चालत नाहीत. MTPredictor ची "reversal bar चा high exceed झाला की entry" ([MTPredictor Intro PDF](https://mtpredictor.com/wp-content/uploads/2021/03/IntrotoMTPredictor21-1.pdf)) ही सुद्धा micro stop-entry आहे. LiteFinance च्या NEoWave सारांशातलं "wave 3 ने wave 1 चं टोक तोडलं की add करा" ([LiteFinance](https://www.litefinance.org/blog/for-professionals/neowave-part-27-trading-strategy-based-on-the-neowave-theory-part-1/)) हे breakout add आहे. **[अनुमान]** यांचे pullback-पर्याय:

| निषिद्ध break-trigger | Pullback-सुसंगत पर्याय | Hard invalidation |
|---|---|---|
| 5 पूर्ण झाल्यावर wave (iv) of 5 चा break (S12) | पहिला 5-wave A (उलट दिशेने) पूर्ण होऊ द्या. मग **B bounce च्या शेवटी** reversal candle वर C साठी entry (S12 → S3a). | 5 चं टोक (B ने ते ओलांडू नये, zigzag नियम) |
| Ending diagonal नंतर wave 4 extreme चा break (S11) | Diagonal संपल्यावर उलट दिशेने पहिली हालचाल होऊ द्या. मग तिच्या **पहिल्या lower-degree retrace ((ii) किंवा b) च्या शेवटी** entry. | Diagonal चं टोक (wave 5 extreme) |
| Triangle B–D line break (S9) | **E च्या शेवटी** reversal candle वर entry. | Contracting triangle मध्ये E हा C चं टोक ओलांडत नाही ⇒ C चं टोक |
| Reversal bar high exceed (MTP) | Reversal candle **close** वर signal, पुढच्या bar च्या open ला fill (किंवा limit). | Setup च्या degree चा hard inv |
| Wave 3 ने wave 1 तोडल्यावर add | **(ii) of 3 किंवा (iv) of 3 च्या शेवटी** नवीन spread (S2, S4) | (i) of 3 चा origin / (i) of 3 चं टोक |
| NEoWave Stage 1 (2-4 line break) हा entry म्हणून | Stage 1 फक्त **confirm-to-hold** आणि score म्हणून. Entry आधीच reversal candle वर झालेली असते. | — |

### इतर लहान दुरुस्त्या

- **BANKNIFTY weekly.** आधी "BANKNIFTY weekly उपलब्ध आहे का तपासा" असं म्हटलं होतं. आता हे निश्चित झालं आहे: **Nov 2024 पासून BANKNIFTY weekly बंद आहे, फक्त monthly** ([Business Standard](https://www.business-standard.com/amp/markets/news/nse-bids-adieu-to-thursday-expiry-as-dates-swap-come-into-effect-explained-125082800635_1.html)) **[पुरावा]**. म्हणून profile मधलं "NIFTY, BANKNIFTY, SENSEX weekly" हे BANKNIFTY साठी आता monthly-only आहे.
- **c_min = 0.2.** आधीचा credit/width guard 0.2 होता. 1 DTE वर तो बहुतेक trades skip करेल. Notes नुसार 1 DTE वर 1–2% OTM spread ला width च्या फक्त काही टक्के credit मिळतं. हा आकडा fetched data ने सिद्ध झालेला नाही **[अनुमान]**. म्हणून आता guard **DTE-निहाय** आहे (विभाग 8).
- **Neely time बद्दल.** "पूर्ण A-B-C हळू असायला हवी" हे विधान आता नियम नाही, फक्त feature आहे (दुरुस्ती 3).

---

## 2. सिद्धांताचा पाया: अटळ नियम (R1–R11), बाकी सगळं score

### नियम विरुद्ध मार्गदर्शक

Frost & Prechter यांची व्याख्या नेमकी आहे: "A *rule* is so called because it governs all waves to which it applies. Typical, yet not inevitable, characteristics of waves are called *guidelines*" ([EWI: Impulse](https://www.elliottwave.com/waveopedia/impulse)). Algorithm साठी याचा अर्थ असा. **नियम = pass/fail filter आणि hard invalidation. मार्गदर्शक = soft score.** EWI चा ranking नियम सुद्धा हेच सांगतो: "preferred" count तो "that satisfies the largest number of guidelines" ([EWI Introduction](https://www.elliottwave.com/free/introduction-to-the-wave-principle/)) **[मार्गदर्शक]**.

| # | विधान | लेबल | Code मध्ये वापर **[अनुमान]** | स्रोत |
|---|---|---|---|---|
| R1 | Wave 2 कधीच wave 1 च्या सुरुवातीपलीकडे retrace करत नाही | **[नियम]** | wave-2/(ii) entries चा hard inv = wave 1 origin | [Kennedy, EWI](https://elliottwaveplus.com/how-the-wave-principle-can-improve-your-trading/); [MTPredictor](https://mtpredictor.com/elliott-wave-2-rules/) |
| R2 | Wave 3 हा 1, 3, 5 पैकी कधीच सर्वात लहान नसतो | **[नियम]** | wave-5 लांबीची वरची मर्यादा (w3 < w1 असेल तर w5 ≤ w3) | [Kennedy, EWI](https://elliottwaveplus.com/how-the-wave-principle-can-improve-your-trading/) |
| R3 | Impulse मध्ये wave 4 हा wave 1 च्या price territory मध्ये शिरत नाही | **[नियम]** (cash markets) | wave-4 entries चा hard inv = wave 1 चं टोक | [EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf) |
| R4 | Correction कधीच 5 नसते. "An initial 5-wave move against the larger trend is never the end of the correction" | **[नियम]** | **A-end entry ban**. (नियम काटेकोरपणे 5-wave पहिल्या हालचालीला लागू. 3-wave पहिला leg "A" म्हणून label झाला तर ban हा label चा परिणाम आहे, कारण A नंतर B येतोच; पण तोच 3-wave leg lower degree वर पूर्ण correction असू शकतो, हे vote ठरवतो **[अनुमान]**) | [EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf) |
| R5 | Triangle कधीच एकटा wave 2 म्हणून येत नाही. तो "always occurs in a position prior to the final actionary wave" (4, B, X, combination चा शेवट) | **[नियम]** | Triangle ⇒ पुढे thrust (S9) | [EWI: Triangles](https://www.elliottwave.com/waveopedia/triangles/) |
| R6 | Zigzag (5-3-5): B हा A च्या सुरुवातीपलीकडे जात नाही **[नियम]**. C हा A च्या टोकापलीकडे जातो हे **[मार्गदर्शक, मजबूत]**: Outline चे शब्द "C moves well beyond A's extreme" वर्णनात्मक आहेत, आणि truncated C शक्य आहे | B भाग **[नियम]**; C भाग **[मार्गदर्शक]** | B→C entry चा hard inv = A origin. "C > A end" फक्त score/target, कधीच gate किंवा inv नाही | [EWGold](https://elliottwavegold.com/2020/06/comprehensive-list-of-elliott-wave-rules-and-guidelines/); [EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf) |
| R7 | Flat (3-3-5): "wave B must retrace at least 90 percent of wave A. This is a rule." Expanded flat मध्ये B > 105% A, आणि C हा A च्या टोकापलीकडे | **[नियम]** | कुटुंब classifier; flat मध्ये A origin हा B चा inv **नाही** | [EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf) |
| R8 | Contracting triangle: C हा A च्या टोकाआत, D हा B च्या टोकाआत, E हा C च्या टोकाआत | **[नियम]** (EWGold यादी, practitioner) | E-end entry चा hard inv = C चं टोक. **Barrier triangle** मध्ये D ≈ B (EWGold: "the only Elliott wave rule that's not absolute") ⇒ D-containment tolerance setting. **Expanding triangle** मध्ये E हा C च्या पलीकडे जातो (Outline), म्हणून हा inv लागू नाही ⇒ expanding triangle वर entry नाही (P8) | [EWGold](https://elliottwavegold.com/2020/06/comprehensive-list-of-elliott-wave-rules-and-guidelines/) |
| R9 | Ending diagonal फक्त wave 5 किंवा C म्हणून येतो (EWI: "primarily in the fifth wave position"; Outline: C म्हणून "rarely"), 3-3-3-3-3 असतो. Diagonal मध्ये wave 3 कधीच सर्वात लहान नाही, आणि "no reactionary subwave fully retraces the preceding actionary subwave" ⇒ wave 4 हा wave 2 च्या टोकापलीकडे जात नाही. Wave 4 चा wave 1 शी overlap: EWP नुसार "almost always", EWGold नुसार अनिवार्य. Leading diagonal फक्त wave 1 किंवा A म्हणून येतो; त्याचं subdivision 5-3-5-3-5 की 3-3-3-3-3 हे EWP नुसार अनिर्णित, आणि Neely leading diagonals नाकारतो ([QOW 1645](https://www.neowave.com/qow/qow-archive-1645.asp)) | स्थान, 3-3-3-3-3, w3 not shortest, w4 ≤ w2 end: **[नियम]**. W4 overlap: **[मार्गदर्शक]** (EWP), [नियम] फक्त EWGold मध्ये | Diagonal setups S10/S11/S14. Overlap नसलेला 5-leg pattern diagonal म्हणून reject करू नका; तो impulse म्हणून तपासा | [EWI Diagonals](https://www.elliottwave.com/waveopedia/elliott-wave-pattern-diagonals/); [EWGold](https://elliottwavegold.com/2020/06/comprehensive-list-of-elliott-wave-rules-and-guidelines/) |
| R10 | Combination: एकापेक्षा जास्त zigzag नाही, आणि triangle फक्त शेवटी | **[नियम]** (EWGold यादी) | WXY classifier | [EWGold](https://elliottwavegold.com/2020/06/comprehensive-list-of-elliott-wave-rules-and-guidelines/) |
| R11 | "If the market moves beyond what the apparently completed pattern allows, the conclusion is wrong" | **[नियम]** (तत्त्व) | प्रत्येक count node ला `hard_inv` | [EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf) |

**पडताळणीतली उणीव.** "C wave चा sub-wave (ii) हा C च्या सुरुवातीपलीकडे (B end) जात नाही" हा नियम R1 चाच परिणाम आहे. C हा 5-wave motive आहे, म्हणून त्याचा (ii) त्याच्या (i) origin पलीकडे जाऊ शकत नाही. पण notes मध्ये तो वेगळ्या शब्दांत primary स्रोताने पडताळलेला नाही **[नियम, R1 वरून व्युत्पन्न]**. EWP मधला "zigzag B < A origin" हा नियम EWGold आणि EWP Outline वरून आहे, थेट EWI Waveopedia पानावरून नाही.

**Cash data.** Neely च्या मते overlap नियम "must be strictly applied", नाहीतर "nearly any scenario desired can be concocted". तो cash data वापरायला सांगतो, कारण futures मध्ये expiry आणि premium "havoc" करतात ([NEoWave Q&A #48](https://www.neowave.com/qow/qow-archive-48.asp)) **[मार्गदर्शक]**. **[अनुमान]** म्हणून structure **NIFTY spot** वर मोजा, आणि P&L options वर.

### Degrees: तुमचा swing threshold हीच तुमची degree

EWP नऊ degrees देतं: Grand Supercycle ते Subminuette ([Wikipedia: Elliott wave principle](https://en.wikipedia.org/wiki/Elliott_wave_principle)). Fractal नियम असा: "Movements with the larger trend subdivide into 5. Movements against the larger trend subdivide into 3" **[नियम]** ([EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf)). Weekly NIFTY trader मुख्यतः Minute (दिवस) आणि Minuette/Subminuette (तास/मिनिटं) degrees वर काम करतो. Prechter इशारा देतो की price-filter turning points "often miss critical waves entirely", आणि "waves are a function of form, not price alone" ([Prechter — Semantic Scholar](https://www.semanticscholar.org/paper/Elliott-Waves,-Fibonacci-and-Statistics-Prechter/806b3836aa6a723230ba10e1d34e0bd36716a797)) **[दावा]**. **[अनुमान]** Bot मध्ये "degree" म्हणजे **swing threshold चा स्तर** (D0, D1, D2, D3). दोन शेजारी legs एकाच degree चे आहेत का, हे NEoWave चा Similarity & Balance नियम ठरवतो: लहान wave मोठ्याच्या किमान 1/3 price **किंवा** 1/3 time असावी ([NEoWave QOW 78](https://www.neowave.com/qow/qow-archive-78.asp)) **[नियम, Neely]**.

### Personality, alternation, channeling, equality, depth

हे सगळे **[मार्गदर्शक]** आहेत, आणि tie-breaker म्हणून वापरायचे. EWP personality चा उपयोग स्पष्ट सांगतं: "several different wave counts are admissible under all known Elliott rules" अशा वेळी पर्याय निवडण्यासाठी ([EWI: Wave Personality](https://www.elliottwave.com/waveopedia/wave-personality/)).

| Wave | EWP वर्णन | Trading अर्थ **[अनुमान]** |
|---|---|---|
| 2 | "Retrace so much of wave one that most of the profits… are erased" | सर्वात भीतीदायक pullback, पण inv स्पष्ट (wave 1 origin) |
| 3 | "Wonders to behold… strong and broad" | आतले pullbacks उथळ. (ii)/(iv) of 3 हे Tier A |
| 4 | "Predictable in both depth and form", बहुधा sideways | Theta साठी चांगला, पण reward लहान आणि truncation धोका |
| 5 | Wave 3 पेक्षा कमी dynamic | Wave 5 नंतरचा pullback हा मोठ्या correction चा A असू शकतो |
| A | "Just a pullback" असं गर्दीला वाटतं | **A-end entry नाही** (R4) |
| B | "Phonies… sucker plays, bull traps", "virtually always doomed to complete retracement by wave C" | B च्या **आत** entry नाही. B च्या **शेवटी** C साठी entry |
| C | Declining C "usually devastating", wave 3 सारखा | C च्या शेवटी पुढच्या motive साठी entry |

Alternation बद्दल EWP म्हणतं: "If wave two of an impulse is a sharp retracement, expect wave four to be a sideways correction, and vice versa" ([EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf)) **[मार्गदर्शक]**. Swannell च्या आकडेवारीनुसार ते फक्त **61.8%** वेळा घडतं, आणि wave 2 sideways असेल तर 78% वेळा wave 4 सुद्धा sideways असतो ([EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf)) **[दावा]**.

Channeling: "The upper parallel most accurately forecasts the end of wave 5 when drawn touching the peak of wave three" ([EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf)) **[मार्गदर्शक]**. पण "the wave count takes precedence over channel lines and projected Fibonacci targets" ([EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf)) **[मार्गदर्शक]**.

Depth: corrections, विशेषतः fourth waves, "tend to register their maximum retracement within the span of travel of the previous fourth wave of one lesser degree" ([EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf)) **[मार्गदर्शक]**. Wave 2 च्या खोलीवर परंपरा स्वतःशीच भांडते. Kennedy नुसार typical wave 2 ".618 retracement" आहे ([Kennedy, EWI](https://elliottwaveplus.com/how-the-wave-principle-can-improve-your-trading/)). Swannell नुसार stock-market wave 2 बहुधा 38.2%, "twice as likely" 61.8% पेक्षा ([EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf)) **[दावा]**. **[अनुमान]** म्हणून depth हा score आहे, entry level नाही. यांपैकी एकाचाही peer-reviewed frequency अभ्यास सापडलेला नाही.

---

## 3. पुरावा: Fibonacci आणि time योगायोगाइतकेच, NEoWave codable पण न तपासलेला

### Fibonacci: 144 पैकी 15 चाचण्या

EWP ची ratio यादी सगळी **[मार्गदर्शक]** आहे:

- Wave 2 ≈ 0.5/0.618 × w1.
- Wave 3 ≈ 1.618/2.618 × w1.
- Wave 4 ≈ 0.382 × w3 (मग 0.236).
- Wave 3 extended असेल तर wave 5 ≈ wave 1.
- Zigzag मध्ये C = A, "in that order" मग 1.618A, मग 0.618A.
- Expanded flat मध्ये B ≈ 1.236–1.382A आणि C ≈ 1.618A.
- Contracting triangle मध्ये प्रत्येक leg ≈ 0.618 × आधीचा.

([EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf))

यांच्या विरुद्धचा पुरावा कठोर आहे **[पुरावा −]**. Batchelor & Ramyar यांनी 1915–2003 चा DJIA daily data (22,194 दिवस, 430 turning points) घेतला. त्यावर 16 ratio प्रकार (price, log, %, आणि **time**) stationary block bootstrap (2,000 reps) विरुद्ध तपासले. **144 पैकी 15 चाचण्या 90% पातळीवर significant आल्या, आणि योगायोगाने 14.4 अपेक्षित होत्या** ([City Univ. open access](https://openaccess.city.ac.uk/id/eprint/16276/1/magic%20numbers%20in%20the%20dow.pdf)). Tsinaslanidis, Guijarro & Voukelatos (2022) यांनी 30 Dow, 100 NASDAQ आणि 30 DAX stocks वर 1968–2019 तपासलं. त्यांच्या मते Fibonacci zone वर bounce होण्याची शक्यता इतर zones पेक्षा "statistically indistinguishable" आहे. Fibonacci strategies random आणि buy-and-hold दोघांपेक्षा मागे पडल्या ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0957417421012495)) **[पुरावा −]**.

Prechter चा प्रतिवाद **[दावा]** असा आहे. Batchelor & Ramyar नी percentage-filter swings तपासले, तर EW चा Fibonacci दावा फक्त योग्य label केलेल्या पर्यायी waves (1 वि. 5, A वि. C) साठी आहे ([Prechter — Semantic Scholar](https://www.semanticscholar.org/paper/Elliott-Waves,-Fibonacci-and-Statistics-Prechter/806b3836aa6a723230ba10e1d34e0bd36716a797)). हा प्रतिवाद अर्धा बरोबर आहे, पण तो कोणतीही प्रति-चाचणी देत नाही. **[अनुमान]** म्हणून spec मध्ये Fibonacci फक्त **target zone** आणि **score** म्हणून येतो, कधीच gate म्हणून नाही. आणि P15 तो ratio-blind labeller ने random-ratio sets विरुद्ध तपासतो.

S/R ची सर्वात भक्कम यंत्रणा round numbers आहे. Osler (NY Fed) ला FX order-book मध्ये orders round numbers वर clustering करताना आढळल्या ([NY Fed SR125](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.pdf)) **[पुरावा +, FX]**. NSE वर हे तपासलेलं नाही.

### Time: Elliott स्वतः "baffling" म्हणाला

Elliott चं 1941 चं वाक्य: "The time element as an independent device… continues to be baffling" ([Prechter — Semantic Scholar](https://www.semanticscholar.org/paper/Elliott-Waves,-Fibonacci-and-Statistics-Prechter/806b3836aa6a723230ba10e1d34e0bd36716a797)) **[दावा]**. Batchelor & Ramyar चे time-ratios सुद्धा योगायोगाइतकेच आले **[पुरावा −]**. NEoWave चे time नियम कठोर शब्दांत आहेत, पण त्यांची सांख्यिकीय पडताळणी शून्य आहे:

| NEoWave time विधान | लेबल | Spec मधला वापर **[अनुमान]** | स्रोत |
|---|---|---|---|
| t(w2) > t(w1) **OR** t(w4) > t(w3). Terminals ला सूट. | **[नियम, Neely]** | `impulse_time_ok`. Impulse validate करताना score/filter | [QOW 3782](https://www.neowave.com/qow/qow-archive-3782.asp) |
| Flat/zigzag मध्ये t(c) ≤ t(a) + t(b). Terminal C ला सूट | **[नियम, Neely]** (author-asserted, न तपासलेला) | `c_time_violation` ⇒ correction complex होतेय ⇒ entry पुढे ढकला | [QOW 3518](https://www.neowave.com/qow/qow-archive-3518.asp) |
| Triangle मध्ये t(e) ≤ t(b)+t(c)+t(d) | **[मार्गदर्शक / विरोधाभास]**: Neely "should never" म्हणतो, पण त्याच पानावर "the last leg of a Triangle … will 'Push' beyond the ideal time targets" असा अपवाद देतो | फक्त score. E लांबला म्हणून triangle count reject करू नका | [QOW 3518](https://www.neowave.com/qow/qow-archive-3518.asp) |
| t(B) < t(A) ⇒ triangle/diametric. t(B) ≥ t(A) ⇒ flat/zigzag | **[मार्गदर्शक]** | कुटुंब classifier score | [QOW 509](https://www.neowave.com/qow/qow-archive-509.asp) |
| Stage 1: 2-4 line "broken in less time than wave-5 took to form". Stage 2: wave-5 पूर्ण retrace "in less time than it took to form" | Stage 1 **[नियम, Neely]** (QOW 22: "mandatory"; फक्त पूर्ण 5-wave impulse नंतर), Stage 2 confirmatory | Reversal candle ची time-अट (analog, **[अनुमान]**) आणि confirm-to-hold. Entry trigger नाही | [QOW 22](https://www.neowave.com/qow/qow-archive-22.asp); [QOW 1109](https://www.neowave.com/qow/qow-archive-1109.asp?searchterms=leas); [QOW 18](https://www.neowave.com/qow/qow-archive-18.asp) |

Hurst चे nominal cycles (5-day ≈ 4.3 दिवस, 10-day ≈ 8.5 …) ([MarketCycles docs](https://docs.marketcycles.blog/books/cycles---decoding-the-hidden-rhythm/page/hurst-nominal-cycle-model)) आणि Gann च्या दिवस-संख्या ([Cycles Research Institute](https://cyclesresearchinstitute.org/cycles-research/economy/markets/w-d-gann/)) हे **[दावा]** आहेत, आणि त्यांची peer-reviewed चाचणी नाही. भारतासाठी जे खरं आहे ते **intraday U-shaped volatility** आहे ([MPRA 89689](https://mpra.ub.uni-muenchen.de/89689/)) **[पुरावा +, working paper]**. **[अनुमान]** Options seller साठी उपयोगी "time" म्हणजे time-of-day आणि DTE. Fibonacci किंवा Gann time नाही.

### NEoWave आणि automation

NEoWave हा सर्वात codable प्रकार आहे. Monowaves, Retracement Rules 1–7, Similarity & Balance आणि Stage 1/2 हे त्याचे भाग. पण Rules 1–7 च्या पूर्ण condition tables फक्त *Mastering Elliott Wave* (1990) मध्ये आहेत. ते पुस्तक copyrighted आणि paid आहे ([masteringelliottwave.com](https://masteringelliottwave.com/)). Neely ची trading-style ची भूमिका तुमच्याशी जुळते. तो "bargain hunting — buy pullbacks in uptrends, sell rallies in downtrends" ही तीन शैलींपैकी एक मानतो ([NEoWave Q&A #688](https://www.neowave.com/qow/qow-archive-688.asp)) **[दावा]**. Neely चा Type 2 confirmation "the largest, counter-trend move inside the unfinished trend" वापरतो, आणि expanding patterns मध्ये खोटे signals देतो ([QOW 1109](https://www.neowave.com/qow/qow-archive-1109.asp?searchterms=leas)) **[मार्गदर्शक]**.

Automated EW चे प्रकाशित आकडे साधारण **64–88% direction accuracy** च्या पट्ट्यात आहेत. Vantuch et al.: Gold 68.1%, Silver 71.1%, EURUSD 70.1% ([EUDL](https://eudl.eu/pdf/10.4108/eai.27-2-2017.152341)). Kotyrba & Volná: 67.8%, >90% similarity matches वर ([ECMS 2013](https://scs-europe.net/dlib/2013/ecms13papers/is_ECMS2013_0050.pdf)). ElliottAgents: पूर्ण impulses वर 73–88%, अपूर्ण वर 67–73%, simulated ([arXiv](https://arxiv.org/html/2507.03435v1)). पण हे आकडे **पूर्ण** patterns चे आहेत, P&L नसलेले आहेत, आणि walk-forward शिवायचे आहेत **[पुरावा, कमकुवत]**. LuxAlgo सारखे tools invalidated counts सुद्धा दाखवतात ("A struck pattern is information, not noise") ([LuxAlgo](https://www.luxalgo.com/library/indicator/elliott-wave/)) **[दावा]**. WaveBasis चं धोरण असं: higher degrees "evolve forward", आणि पुन्हा count फक्त "when price action invalidates the wave count at higher degrees" ([WaveBasis FAQ](https://wavebasis.com/docs/frequently-asked-questions/automatic-wave-counts/how-often-should-i-re-run-a-wave-count/)) **[दावा]**. हे धोरण विभाग 12 मधल्या stability policy चा आधार आहे.

### Track record

Prechter चा 1984 चा 444% contest return खरा आहे ([Wikipedia: Robert Prechter](https://en.wikipedia.org/wiki/Robert_Prechter)). पण Hulbert च्या secondary आकड्यांनुसार 1985–2009 मध्ये त्याचा trading सल्ला **−15.4%/वर्ष** राहिला, आणि market +9.7%/वर्ष ([wavesnaps citing Hulbert](https://wavesnaps.blogspot.com/2011/02/lousy-track-record-for-robert-prechter.html)) **[दावा, पडताळणी आवश्यक]**. CXO Advisory ने त्याच्या forecasts ना 21% अचूकता दिली ([CXO Advisory](https://www.cxoadvisory.com/individual-gurus/robert-prechter/)) **[पुरावा −, लहान sample]**. भारतीय EW अभ्यास circular आहेत. उदाहरणार्थ, Sharma & Modak (2024) यांना NIFTY वर नियम "held" आढळले, पण count नंतर काढला तर नियम व्याख्येनेच पाळले जातात ([IIP Series](https://www.iipseries.org/assets/docupload/rsl2024A68ECAEFD7778F2.pdf)) **[पुरावा, शून्य मूल्य]**. MTPredictor चा developer स्वतःच्या अनुभवावरून सांगतो: ~1/3 तोटे, ~1/3 breakeven, ~1/3 नफे, आणि मोठे winners फक्त ~1/6 trades मध्ये ([MTPredictor Intro PDF](https://mtpredictor.com/wp-content/uploads/2021/03/IntrotoMTPredictor21-1.pdf)) **[दावा, backtest नाही]**.

---

## 4. Degree-aware architecture: पुढची motive wave trade करा, मोठी degree फक्त size आणि target ठरवते

### मूळ तत्त्व

Practitioners चं साहित्य एका गोष्टीवर एकमत आहे. Trade **corrective wave च्या शेवटी** घ्यायचा, **पुढच्या motive wave** च्या दिशेने. Kennedy: "If it is going up, I like to buy pullbacks. If it is going down, I like to sell bounces" ([Traders.com reprint](https://traders.com/reprints/pdf_reprints/Expired/EW_KENNEDY.pdf)) **[दावा]**. Kennedy waves 3, 5, A आणि C ला "the most advantageous to trade" म्हणतो ([Kennedy Visual Guide sample](https://download.e-bookshelf.de/download/0000/8049/21/L-G-0000804921-0007908122.pdf)) **[मार्गदर्शक]**. MTPredictor चा developer wave-2 नंतरच्या wave-3 setup ला "My personal favourite" म्हणतो. त्यासाठी तो Gann चं वाक्य देतो: "Best place to buy is on the initial correction after the start of the new trend" ([MTPredictor Intro PDF](https://mtpredictor.com/wp-content/uploads/2021/03/IntrotoMTPredictor21-1.pdf)) **[दावा]**.

**[अनुमान]** यावरून spec ची व्याख्या अशी:

> **Trade degree D** = ज्या corrective wave चा शेवट ओळखला तिची degree. Trade दिशा = त्याच sequence मधल्या पुढच्या motive wave ची दिशा. ती wave 3, 5, C, Y किंवा post-correction resumption असू शकते.
> **Parent D+1** = ज्या मोठ्या wave ची ही sequence subdivision आहे.
> **Grandparent D+2** = आणखी मोठा context (HTF).

Lower-degree count तेव्हाच admissible असतो, जेव्हा तो किमान एका valid D+1 count च्या चालू wave चा legal subdivision असतो. ELWAVE हेच सुचवतो: "Do the same for shorter and longer time frames (or lower and higher wave degrees) and try to narrow down alternatives" ([ELWAVE FAQ](https://elwave.com/elwave/faq/principle/trading_ew.html)) **[दावा]**.

### Alignment tiers (size multiplier)

| Tier | व्याख्या **[अनुमान]** | उदाहरणं | Default size | Target धोरण |
|---|---|---|---|---|
| **A** | Trade दिशा = D+1 motive sequence ची दिशा, **आणि** D+1 त्याच्या sequence च्या सुरुवातीला/मध्यात | 2→3; (ii)→(iii) of 3; (iv)→(v) of 3; 4→5 जेव्हा D+1 हा wave 3 आहे | 1.0× | Open-ended. % credit किंवा time exit; T1/T2 = 1.0/1.618 × (i) |
| **B** | Trade दिशा = D+1 च्या **corrective** wave ची दिशा, म्हणजे C किंवा Y trade (bounded), **किंवा** D+2 विरुद्ध | Zigzag/flat B→C; WXY मधला X→Y; C-(ii)→(iii) जेव्हा C स्वतः HTF विरुद्ध | 0.5× | **Bounded:** C zone (0.618/1.0/1.618 × A) मध्ये उलट logical reversal आला की पूर्ण exit (विभाग 14 Q4) |
| **C** | Late-stage किंवा truncation-prone | 4→5 जेव्हा D+1 स्वतः wave 5 मध्ये; (iv)→(v) of 5; diagonal-संशयित legs | 0.25× किंवा skip | लहान target; लवकर exit |
| **Blocked** | Correction पूर्ण नाही (A-end, B च्या आत, triangle च्या आत), किंवा counts "gray" आहेत (vote < किमान) | — | 0 | — |

हा tier-विचार notes मधल्या प्रस्तावावर आधारित आहे. तो Kennedy च्या "partial entries" आणि "trade with the one larger trend" या दोन्हींशी सुसंगत आहे. पण **कोणत्याही free primary स्रोतात counter-trend trades साठी आकडेवारीने ठरवलेली size-कपात नाही** **[अनुमान]**. 0.5 आणि 0.25 हे दोन्ही dashboard parameters आहेत.

### HTF gate पर्यायी

`htf_gate_enabled` (default `false`). तो `true` केला तर Tier B trades block होतात, म्हणजे जुनं वर्तन. Backtest P2 मध्ये दोन्हीची तुलना अनिवार्य आहे. Gate-off ने एकूण expectancy वाढली की नाही आणि Tier B ची स्वतःची expectancy सकारात्मक आहे का, हेच दुरुस्ती 1 बरोबर होती का याचा पुरावा असेल.

### Directional vote: "never trade gray"

EWI नुसार "At any time, two or more valid wave interpretations usually exist" ([EWI Introduction](https://www.elliottwave.com/free/introduction-to-the-wave-principle/)) **[मार्गदर्शक/तत्त्व]** (हे निरीक्षण आहे, pass/fail नियम नाही). ELWAVE: "If you find several alternative counts pointing in the same direction, you have found an excellent trading opportunity" ([ELWAVE FAQ](https://elwave.com/elwave/faq/principle/trading_ew.html)) **[दावा]**. Kennedy: "You never trade gray" ([Traders.com reprint](https://traders.com/reprints/pdf_reprints/Expired/EW_KENNEDY.pdf)) **[दावा]**.

**[अनुमान]** Spec:

```
vote_up = Σ score(c) [c expects up next at degree D] / Σ score(c)   (सर्व valid counts)
अट: vote_dir ≥ vote_min (default 0.60)
Strike: score ≥ alt_weight_min (default 0.25) असलेल्या सगळ्या same-direction counts च्या hard_inv पलीकडे.
जर opposite-direction count चं score ≥ alt_block_weight (default 0.35) ⇒ skip.
```

---

## 5. Setup catalogue: कोणत्या corrective शेवटी entry, कुठे count मरतो, कुठे बाहेर पडायचं

Catalogue चे सर्वसाधारण नियम (सगळ्या setups ना लागू):

- Entry नेहमी corrective wave च्या **शेवटी**, reversal candle **close** वर, पुढच्या bar च्या open ला fill. Reversal candle चा timeframe = त्या setup च्या degree/level चा timeframe (`trigger_tf_mode = level_tf`, विभाग 6).
- "Hard inv" हा **त्याच degree चा** नियम-स्तर. अपवाद S6b आणि S8, जिथे तो **[अनुमान]** स्तर आहे.
- Hard inv किंवा soft stop चा "break" म्हणजे नेहमी विभाग 7/14 मधला **real break**: buffer (0.25 × median range) पलीकडे close **आणि** displacement candle, **किंवा** पुढची candle reclaim न करणं (acceptance), **किंवा** failed retest. Wick किंवा कमकुवत close होऊन परत आला तर false break, exit नाही.
- "Soft stop" हा reversal candle चा extreme.
- Bull put = पुढची motive wave **वर** जाणार. Bear call = पुढची motive wave **खाली** जाणार.
- Target zones सगळे **[मार्गदर्शक]**, म्हणजे Fibonacci किंवा channel.
- Mapping स्तंभ **[अनुमान]**.

| # | Context | Entry कोणत्या corrective शेवटी | Hard invalidation (त्या degree चा) | Target zone | Exit | Tier | Spread mapping |
|---|---|---|---|---|---|---|---|
| **S1** | नवीन trend: D वर impulsive 5-wave 1 पूर्ण, मग 3-wave correction | **Wave 2 चा शेवट** (zigzag सर्वात सामान्य; flat/combination शक्य; triangle कधीच नाही, R5) | **Wave 1 origin** (R1) **[नियम]**; Kennedy: "one tick below the origin of wave (1)" ([EWI](https://elliottwaveplus.com/how-the-wave-principle-can-improve-your-trading/)) | W3 = 1.618/2.618 × W1 ([Kennedy](https://elliottwaveplus.com/how-the-wave-principle-can-improve-your-trading/)); T1 = W1 चं टोक | % credit, किंवा T1 नंतर time exit | A | Up ⇒ bull put; down ⇒ bear call. Short strike W1 origin पलीकडे |
| **S2** | Wave 3 चालू. (i) of 3 impulsive, मग (ii) | **(ii) of 3 चा शेवट** (MTP चा "minor ABC in wave 2" TS1) ([MTPredictor](https://mtpredictor.com/wp-content/uploads/2021/03/IntrotoMTPredictor21-1.pdf)) | **(i) of 3 चा origin** (= wave 2 end) **[नियम R1, lower degree]** | (iii) = 1.618 × (i); "third of a third" acceleration ([EWI](https://www.elliottwave.com/articles/catching-the-third-of-a-third-in-ai-before-the-rest-of-the-world/)) | % credit | A | सर्वात tight inv. 1 DTE साठी सर्वोत्तम उमेदवार **[अनुमान]** |
| **S3** | Wave 3 पूर्ण, wave 4 sideways (बहुधा flat, triangle किंवा combination) | **Wave 4 चा शेवट** | **Wave 1 चं टोक** (R3) **[नियम]**; Kennedy: "one tick below the extreme of wave (1)" | W5 = W1 (W3 extended असेल तर) ([EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf)); 2-4 channel वरची रेषा W3 टोकातून | W5 target जवळ, किंवा % credit | A (D+1 = 3) / C (D+1 = 5) | Truncation धोका ⇒ जवळचा spread किंवा लहान size **[अनुमान]** |
| **S4** | Wave 3 च्या आत (iii) पूर्ण, मग (iv) | **(iv) of 3 चा शेवट** | **(i) of 3 चं टोक** (R3, lower degree) | (v) of 3 = (i) | % credit | A | — |
| **S5** | Wave 5 च्या आत (iii) पूर्ण, मग (iv) | **(iv) of 5 चा शेवट** | (i) of 5 चं टोक (impulse). Wave 5 ending diagonal म्हणून label असेल तर (ii) of 5 चं टोक (R9) | लहान: (v) = (i) | लवकर exit (≤ 40% credit) | C | Truncation आणि ending diagonal धोका |
| **S6a** | Zigzag चालू: A = 5 waves, मग B (3 waves, A च्या 38–79%) | **B चा शेवट** | **A origin** (R6) **[नियम]** | C = A (प्रथम), मग 1.618A, मग 0.618A ([EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf)). B end पासून मोजा | C zone (0.618/1.0/1.618 × A) किंवा विरुद्ध major level वर **उलट logical reversal** आला की पूर्ण exit (`tierB_exit_mode = opposite_reversal`, विभाग 14 Q4). C ने zone acceptance ने ओलांडला ⇒ hold + progressive_inv | B (D+1 correction) | **C वर ⇒ bull put, C खाली ⇒ bear call.** उदाहरण: 5 Oct |
| **S6b** | Flat चालू: A = 3 waves, B ≥ 90% A | **B चा शेवट**. Regular: B ≈ 90–105% A. **Expanded: B > 105% A** | Flat मध्ये A origin हा inv **नाही** (expanded flat मध्ये B तो ओलांडतो). B ची वरची मर्यादा सांगणारा नियम नाही. म्हणून trade-level inv = **B चं टोक + buffer**: ते ओलांडलं तर "B संपला" हा count मेला **[अनुमान]**. B > 2 × A ⇒ flat count सोडा **[अनुमान]** | C ≈ 1.0–1.65 × A; expanded flat मध्ये C ≈ 1.618A ([EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf)) | C zone | B | **Expanded flat चा B हा "breakout" सापळा आहे.** Entry फक्त B च्या शेवटी reversal वर |
| **S6c** | Triangle हा B म्हणून (R5) | **Triangle च्या E चा शेवट** (फक्त contracting/barrier; expanding ⇒ skip) | **C (triangle आतला) चं टोक** (R8) | C (मोठा) ≈ triangle ची सर्वात रुंद बाजू ([EWI: Triangles](https://www.elliottwave.com/waveopedia/triangles/)) | Target वर exit | B | B–D break वर entry नाही (दुरुस्ती 4) |
| **S7** | Trend resumption: पूर्ण correction (ABC zigzag, flat, किंवा combination WXY/WXYXZ) नंतर मोठ्या trend ची पुन्हा सुरुवात | **C, Y किंवा Z चा शेवट**. Correction कुटुंब पूर्ण असल्याचा नियम-check पास (R6–R10) | Correction wave 2 असेल तर wave 1 origin. Wave 4 असेल तर wave 1 चं टोक. Soft = C/Y extreme | मोठ्या degree चा पुढचा motive (3 किंवा 5 चे targets) | % credit | A (2 किंवा 4 of 3) / C (4 of 5) | Kennedy चं मुख्य तंत्र ([Traders.com](https://traders.com/reprints/pdf_reprints/Expired/EW_KENNEDY.pdf)). **"C संपला" असं वाटलं पण preferred count तो W मानतो आणि X सुरू होतोय ⇒ correction अजून चालू ⇒ S7 entry नाही** (X-end वरचा trade फक्त S8, default बंद) |
| **S8** | Combination मधला X | **X चा शेवट ⇒ Y साठी** | W origin **[अनुमान]**: notes मध्ये "X हा W origin पलीकडे जात नाही" असा नियम सापडलेला नाही. Parent चा rule-inv (उदा. wave 2 combination असेल तर wave 1 origin) हा नियम-स्तर | Y ≈ W (zigzag) **[मार्गदर्शक, कमकुवत]** | Y zone | B / C | Sideways combination मध्ये reward लहान ⇒ default **बंद** |
| **S9** | Triangle हा wave 4 (किंवा combination चा शेवट) | **E चा शेवट** (E A–C line च्या थोडा पलीकडे किंवा आत: "more often than not") ([EWI: Triangles](https://www.elliottwave.com/waveopedia/triangles/)) | **C चं टोक** (R8); मोठ्या degree साठी wave 1 चं टोक (R3) | Thrust ≈ "the distance of the widest part of the triangle" **[मार्गदर्शक]**; apex time हा turning point **[मार्गदर्शक]** | Thrust target वर | A / C | B–D break वर entry नाही. EWI इशारा: "Many analysts are fooled into labeling a completed triangle way too early" |
| **S10** | Leading diagonal हा wave 1 | **Wave 2 चा शेवट** ("typically followed by a deep retracement") ([EWI Diagonals](https://www.elliottwave.com/waveopedia/elliott-wave-pattern-diagonals/)) | **Diagonal origin** (R1) | S1 सारखेच | S1 सारखेच | A (size 0.75×: Neely leading diagonals नाकारतो, [QOW 1645](https://www.neowave.com/qow/qow-archive-1645.asp)) | — |
| **S11** | Ending diagonal (wave 5 किंवा C) पूर्ण | Diagonal संपल्यावर उलटा पहिला leg होऊ द्या. मग **त्याच्या पहिल्या lower-degree retrace चा शेवट** | **Diagonal चं टोक** (wave 5 extreme) | "retracing at least back to the level where it began" ([EWI Diagonals](https://www.elliottwave.com/waveopedia/elliott-wave-pattern-diagonals/)) | Diagonal start वर | B (मोठ्या trend विरुद्ध) | Kennedy चा wave-4 break नाही (दुरुस्ती 4) |
| **S12** | 5-wave impulse पूर्ण (post-5 reversal) | A (5 waves, उलट दिशेने) होऊ द्या. **B bounce च्या शेवटी ⇒ C साठी** | **5 चं टोक** (zigzag मध्ये B < A origin, R6) | C = A. पहिला target = "previous fourth wave of one lesser degree" ([EWI Basics](https://marscapitalpartners.com/wp-content/uploads/2014/01/EW-Basics.pdf)) | C zone | B | Wave 5 fade करणं निषिद्ध. Wave (iv) of 5 break सुद्धा निषिद्ध |
| **S13** | C wave चालू. (i) of C impulsive, मग (ii) of C | **(ii) of C चा शेवट** | **C origin = B end** (R1, lower degree) | C zone (0.618/1.0/1.618 × A) | S6a प्रमाणेच: C zone/level वर उलट logical reversal ⇒ पूर्ण exit (विभाग 14 Q4) | B | **उदाहरण: 5 Oct 13:30** |
| **S14** | C च्या आत (iv) of C | **(iv) of C चा शेवट** | (i) of C चं टोक (impulse C). Ending diagonal C असेल तर wave 2 चं टोक (R9) | C = A जवळ | लवकर exit | C | Diagonal-संशय असल्यास skip |

**निषिद्ध entries (सगळ्या degrees वर)** **[नियम R4 + अनुमान]**:

1. **A-end** (trend विरुद्धचा पहिला leg संपल्यावर). कारण "initial 5-wave move … never the end of the correction". शिवाय A नंतर B हा corrective wave येतो, motive नाही.
2. **B च्या आत, triangle च्या आत, आणि X च्या आत.** Kennedy "you never trade gray" ([Traders.com](https://traders.com/reprints/pdf_reprints/Expired/EW_KENNEDY.pdf)).
3. **Wave 5 संपल्यावर लगेच उलटा trade** (S12 वापरा).
4. **कोणतंही level, trendline किंवा bar-high break.**
5. **Ending diagonal च्या दिशेने pullback.** पुढची अपेक्षित हालचाल diagonal च्या सुरुवातीकडे तीव्र उलटी असते.

**Failure modes ज्यांची किंमत backtest ने मोजायची** **[मार्गदर्शक/अनुमान]**:

- Wave 2 complex होतो (double zigzag).
- "Wave 1" खरं तर A होता, म्हणजे "wave 3" खरं तर C.
- Expanded flat मधला B, A origin पलीकडे जातो.
- Running flat मध्ये C हा A चं टोक गाठत नाही, त्यामुळे C=A target चुकतो.
- Triangle लवकर label होतो.
- Truncated wave 5.

---

## 6. Entry trigger: touch, reclaim, strength, rejection score, एका deterministic क्रमात

Kennedy च्या confirmation मध्ये तीन गोष्टी आहेत: momentum divergence (RSI/MACD), correct internal subdivision, आणि candlestick reversal ("bullish engulfing pattern or maybe a morning star") ([Traders.com reprint](https://traders.com/reprints/pdf_reprints/Expired/EW_KENNEDY.pdf)) **[दावा]**. "Let the market commit to you before you commit to the market" ([Kennedy Visual Guide sample](https://download.e-bookshelf.de/download/0000/8049/21/L-G-0000804921-0007908122.pdf)) **[मार्गदर्शक]**. Candlesticks एकट्याने कमकुवत आहेत. DJIA stocks (1992–2002) मध्ये "no evidence that any candlestick signals predict" ([Marshall, Young & Rose 2006](https://ideas.repec.org:443/a/eee/jbfina/v30y2006i8p2303-2323.html)) **[पुरावा −]**. Taiwan मध्ये काही two-day bullish reversals costs नंतर नफ्यात होते ([Lu, Shiu & Liu 2012](https://www.sciencedirect.com/science/article/abs/pii/S1058330012000092)) **[पुरावा, मिश्र]**. **म्हणून candle फक्त Elliott context च्या आत trigger आहे, एकटा signal नाही.**

**[अनुमान]** Bull put साठी trigger. Bear call साठी सगळं mirror करायचं. सर्व thresholds dashboard वर.

```
पूर्व-अट (context):
  C0. Preferred count (degree D) म्हणतो: "corrective wave X संपण्याच्या zone मध्ये".
      Corrective structure नियम-check पास: किमान 3 legs (A-B-C), किंवा पूर्ण triangle E, किंवा पूर्ण WXY.
  C1. Entry zone = [zone_low, zone_high]. हा correction च्या पहिल्या Fib/structure targets चा union.
      उदा. zigzag C = 0.618/1.0/1.618 × A; zigzag B-end = 0.382/0.5/0.618/0.786 × A (A टोकापासून retrace);
      wave 2 = 0.382–0.786 × W1; wave 4 = आधीच्या lesser-degree 4 चा span.
      zone_low/zone_high = त्या levels चा min/max, ± zone_tol_atr × ATR(TTF).
      प्रत्येक level ± zone_tol_atr × ATR.
  C2. hard_inv अजून real-break (विभाग 7) ने तुटलेला नाही.
  C3. c_time_rule ≠ "delay" किंवा c_time_violation = false (zigzag/flat C-end setups साठीच; Terminal C ला सूट).
  C4. Causality: correction चे पूर्ण झालेले legs (उदा. B-end setup साठी A, आणि B चे आतले a, b) यांचे
      pivots `confirmed` असायला हवेत. फक्त चालू शेवटचा leg (B चा c) tentative असू शकतो.

Trigger timeframe (TTF):
  trigger_tf_mode = "level_tf" (default): TTF = setup च्या degree D चा timeframe.
      degree_tf_mode = "auto_by_bars" (default, विभाग 14 Q3): ज्या corrective wave च्या शेवटी entry आहे ती
      tf_bars_min (8)–tf_bars_max (40) बंद candles मध्ये दिसेल असा {5m,15m,30m,1H,1D} पैकी सर्वात लहान TF.
      पर्याय: "fixed" ⇒ degree_tf[D] किंवा trigger_tf_fixed.
  खालचे सर्व bars, ATR आणि median TTF वरचे **बंद** bars आहेत.

Trigger (bull put; bear call साठी सगळं mirror):
  touched_level = zone मधला सर्वात वरचा level L (C1 चे Fib/structure levels) ज्यासाठी bar.low ≤ L + zone_tol.
  T1 touch:    touch bar: bar.low ≤ zone_high  AND  bar.low > hard_inv   (wick zone मध्ये, inv च्या आत)
  T2 reclaim:  composite rejection candle (Trade repo #241 चं मंजूर logic, विभाग 14 Q2):
               शेवटच्या N = 1…touch_reclaim_window (3) बंद candles चा composite =
               (पहिल्या candle चा open, max high, min low, शेवटच्या candle चा close).
               प्रत्येक N साठी T1–T4 तपासा, सर्वोत्तम score वापरा; window नेहमी सर्वात नवीन बंद candle वर संपते.
               अटी: composite.close > touched_level; N ≥ 2 असेल तर शेवटची candle trade दिशेने close;
               मधल्या कुठल्याही candle चा close hard_inv पलीकडे नाही.
               Composite close-location 0.40–0.60 (अनिर्णय) ⇒ पुढच्या follow-through candle ची वाट (N+1, कमाल 4).
               T3 strength आणि T4 score composite च्या range वर. T7 no-breakout guard composite वरही लागू.
               reclaim_ref पर्याय: "touched_level" (default) | "zone_high".
               (prev_bar_high, sub-wave (iv)/2-4 line break हे **entry reference म्हणून निषिद्ध**:
                ते breakout/stop-entry आहेत, दुरुस्ती 4. ते फक्त confirm-to-hold score म्हणून.)
  T3 strength: reclaim bar वर range_ratio = (high−low) / median(high−low of मागचे N बंद bars, चालू bar वगळून), N = median_range_n (20)
               strength_min (1.2) ≤ range_ratio ≤ strength_max (2.5)
               > 2.5 ⇒ reject (news spike/exhaustion; soft stop खूप दूर)
  T4 rejection score (0–1), reclaim bar वर:
      lower_wick = min(open, close) − low;  range = high − low (range = 0 ⇒ reject)
      s = w_wick·(lower_wick/range) + w_cl·((close−low)/range) + w_body·(|close−open|/range)·[close>open]
          + w_time·[bars_to_reclaim ≤ bars_last_subleg]      ← NEoWave Stage-1 analog [अनुमान]
          + w_div·[div_ok]                                     ← Kennedy (optional, default weight 0)
      bars_to_reclaim = reclaim bar index − correction extreme (low) च्या bar चा index
      bars_last_subleg = correction च्या शेवटच्या D−1 leg चे bars (शेवटचा D−1 pivot high ते low)
      div_ok = correction low < आधीचा D−1 swing low AND RSI(rsi_len) at low > RSI at आधीचा low
      defaults: w_wick 0.30, w_cl 0.30, w_body 0.20, w_time 0.20, w_div 0.00 (बेरीज 1.0)
      अट: s ≥ rejection_min (0.60)
  T5 time-of-day: entry_start (09:30) ≤ bar.close_time ≤ entry_end (14:45)
  T6 vote: vote_dir ≥ vote_min, आणि opposite count score < alt_block_weight
  T7 no-breakout guard [अनुमान]: reclaim bar चा close < H, H = correction च्या शेवटच्या D−1 sub-leg चा origin
               (low आधीचा शेवटचा D−1 pivot high). Close H च्या वर ⇒ ती sub-leg-break entry ठरेल ⇒ reject.

Signal = C0∧…∧C4∧T1∧…∧T7, reclaim bar close वर (knowable_at = त्या bar चा close).
Fill = पुढच्या TTF bar च्या open वर (backtest, + slippage_ticks), live मध्ये limit order (mid ± slippage_ticks).
Expiry आणि DTE fill च्या तारखेवरून काढा (विभाग 8).
soft_stop = trigger (reclaim) bar चा low (bear call साठी high) − soft_buffer_pts.
```

**का हे breakout नाही.** Entry corrective wave च्या *आत* होते: touch आणि reclaim, आणि तेही correction च्या शेवटच्या zone मध्ये. ती कोणत्याही structural level च्या पलीकडे जात नाही. "Reclaim" म्हणजे फक्त pierced level वर पुन्हा close. आधीच्या मसुद्यात `prev_bar_high` आणि `last_subwave_iv_extreme` हे reclaim पर्याय होते. ते काढले आहेत, कारण close > आधीच्या bar चा high हा MTP-प्रकारचा stop-entry आहे, आणि sub-wave (iv)/2-4 line ओलांडणं हा NEoWave Stage-1 break आहे. दुरुस्ती 4 नुसार हे दोन्ही entry म्हणून निषिद्ध आहेत. ते फक्त **entry नंतर** confirm-to-hold score म्हणून वापरता येतात. P6 मध्ये candle-only वि. +time-score ची तुलना करायची.

---

## 7. Invalidation hierarchy: count मेला तर बाहेर, फक्त timing चुकलं तर पुन्हा संधी

### दोन स्तर

CWCOUNT हे स्पष्ट मांडतो: "Invalidation occurs when price action violates a structural rule". प्रत्येक scenario ला "its own invalidation level" असतो, आणि invalid झालेला scenario "discarded—not revised or adjusted" ([CWCOUNT](https://cwcount.com/blog/elliott-wave-invalidation-example/)) **[दावा]**. ELWAVE: "exit a trade when a price movement makes your preferred wave count invalid" ([ELWAVE FAQ](https://elwave.com/elwave/faq/principle/trading_ew.html)) **[दावा]**.

| स्तर | व्याख्या | Trigger | कृती | Re-entry |
|---|---|---|---|---|
| **Hard invalidation** | Trade degree D चा नियम-स्तर. उदा. wave 1 origin (S1), wave 1 चं टोक (S3), A origin (S6a), B end (S13) | **Real break** (खाली व्याख्या), confirmation TF वर | Spread **लगेच exit**. तो count node invalidated | **नाही**. त्या count/setup साठी re-entry बंद. नवीन count तयार झाल्यावरच नवीन setup |
| **Soft timing stop** | Reversal candle चा extreme ± soft_buffer | Real break (तीच व्याख्या), पण hard_inv अबाधित | `soft_stop_action` (default **exit**) | **हो**. Hard_inv टिकला असेल तर नवीन reversal candle वर, `max_reentries` (default 1) पर्यंत |
| **False break** | Wick level पलीकडे पण close आत; **किंवा** एकच close पलीकडे आणि पुढच्या `break_no_reclaim_bars` मध्ये close परत आत | Real break ची अट पूर्ण नाही | **Exit नाही** (`false_break_no_exit = true`). Premium stop (क्रम 2) फक्त `hard_stop_eval` नुसार (default bar close) | — |

**Real break ची नेमकी व्याख्या [अनुमान, तुमच्या नियम 6 ची अंमलबजावणी]** (bull put; bear call mirror):

```
(विभाग 14 मधल्या Abhi च्या logic नुसार अंतिम व्याख्या: आकडे नाहीत, बाजाराचा स्वतःचा noise आणि ताकद)
L      = level (hard_inv किंवा soft_stop). Level zone असेल तर L = zone ची far edge (bull put साठी zone_low).
MR     = median(high−low) of मागचे median_range_n (20) बंद CTF bars (चालू bar वगळून)
buf    = break_buffer_mr (0.25) × MR        ← fixed points नाहीत; बाजाराच्या noise च्या प्रमाणात
CTF    = confirmation TF = break_confirm_tf (default "level_tf" = trade degree चा TTF)
Break candidate: CTF bar t चा close < L − buf
Real break confirmed (यांपैकी जे आधी घडेल):
  (a) Displacement break: bar t स्वतःच ताकदीचा — range(t) ≥ strength_min (1.2) × MR AND
      close bar च्या break-दिशेच्या टोकाच्या break_close_loc (0.30) भागात ⇒ bar t च्या close वर confirm.
  (b) Acceptance: bar t कमकुवत असेल तर पुढचा bar t+1 सुद्धा L च्या पलीकडेच close (reclaim नाही)
      ⇒ bar t+1 च्या close वर confirm (break_no_reclaim_bars = 1).
  (c) Failed retest: break नंतर भाव परत L कडे आला आणि उलट बाजूने logical reversal (विभाग 6 चे T1–T4,
      mirror) ने नाकारला गेला ⇒ त्या bar च्या close वर confirm.
अन्यथा (कमकुवत close पलीकडे आणि पुढच्या bar ला close ≥ L) ⇒ false break, candidate रद्द, exit नाही.
```

म्हणून default वर एकच close पलीकडे जाऊन पुढच्या bar ला reclaim झाला तर exit **नाही**. आधीचा `inv_confirm_bars = 1` (एका close वर exit) हा तुमच्या false-break नियमाशी विसंगत होता, म्हणून काढला. Strike साठी `inv_buffer` ≥ `buf` ठेवा, म्हणजे short strike हा real-break स्तराच्या (L − buf) पलीकडे राहतो, आणि count मरण्याआधी spot short strike ला पोहोचत नाही.

**Count engine आणि trade exit एकाच basis वर.** काटेकोर EWP नुसार wick सुद्धा "price territory" मोडतो. पण count एका basis ने मेला आणि trade दुसऱ्या basis ने चालू राहिला, तर विसंगती येते. म्हणून `count_inv_basis = "real_break"` (default) | `"wick"` (strict EWP). Default हा EWP पासून जाणूनबुजून घेतलेला फरक आहे **[अनुमान]**. P4 मध्ये दोन्ही तपासा.

**[अनुमान]** हा दोन-स्तरीय फरक notes मधल्या प्रस्तावावर आधारित आहे: `hard_inv` (count dead) वि. `soft_stop` (timing wrong). Kennedy आणि MTP दोघांचे stops "one tick" beyond असतात. ते intraday ticks वर आधारित आहेत, close-basis वर नाहीत. Real-break निवड (close + buffer + n bars no reclaim) ही तुमच्या "false-break no-exit" नियमाची अंमलबजावणी आहे. याची किंमत P4 मध्ये मोजायची: real-break exit वि. एक-close exit वि. tick-basis exit.

### Degrees मधला प्रसार

**[अनुमान]** (WaveBasis चं "evolve, don't recount" धोरण, [WaveBasis FAQ](https://wavebasis.com/docs/frequently-asked-questions/automatic-wave-counts/how-often-should-i-re-run-a-wave-count/)):

1. Degree d चा `hard_inv` तुटला ⇒ तो node आणि त्याचे सगळे descendants invalidated. ते log मध्ये ठेवायचे, delete करायचे नाहीत.
2. त्याच D+1 parent खाली वेगळ्या labels ने price path पुन्हा बसतो का, ते तपासा. उदा. "(ii) संपला" ⇒ "(ii) अजून चालू: expanded flat किंवा double zigzag".
3. Legal relabel नसेल तरच failure D+1 कडे पाठवा, आणि `inv_{D+1}` तपासा.
4. **Trade चा exit फक्त त्याच्या स्वतःच्या degree D च्या inv वर.** D+1 टिकला तरी trade बंद, कारण trade हा D च्या count वरचा bet होता. D+1 चा inv तुटला तर त्या D+1 खालचे सगळे open trades exit (cascade).
5. Lower degree (D−1) चा inv तुटणं हे D-trade साठी फक्त **warning** आहे: `lower_inv_action` = alert (default) | reduce | exit.

**उदाहरण (5 Oct).** C-(ii) trade (S13) चा hard inv 22,396 आहे. B-end trade (S6a) चा 22,217. भाव 22,396 − buf च्या खाली real break झाला असता (close, आणि पुढच्या bar ला reclaim नाही), तर S13 trade exit झाला असता. "(ii) of C" count मेला असता, पण zigzag (A-B-C) टिकला असता: B अजून चालू, expanded/complex. त्यामुळे S6a trade चालू राहिला असता. 22,217 खाली real break ⇒ zigzag मेला ⇒ S6a exit.

---

## 8. Strike, expiry आणि India contract facts (Oct 2026)

### Strike सूत्र

Varsity पद्धत: period SD = daily SD × √days, 1 SD ≈ 68% ([Zerodha Varsity](https://zerodha.com/varsity/chapter/volatility-applications/)) **[पुरावा, शिक्षण]**. **[अनुमान]** Spec:

```
spot      = fill bar चा open (backtest) / order वेळेचा spot (live)
dist_inv  = |spot − hard_inv(D)| + inv_buffer
            inv_buffer = inv_buffer_mr (0.5) × MR(TTF)  (median range; fixed points नाहीत);  अट: inv_buffer ≥ break buf (0.25 × MR)
dist_vol  = k_sd (1.0) × spot × IV_atm × √(dte_frac / 252)
            dte_days = आजनंतर expiry पर्यंतची trading sessions, expiry दिवस धरून (Monday → Tuesday expiry = 1)
            dte_frac (dte_mode = "session_fraction", default) = (आजच्या session ची उरलेली मिनिटं
                       + dte_days × 375) / 375   [NSE session 09:15–15:30 = 375 मिनिटं; holidays contract calendar मधून]
            dte_mode = "whole_days" ⇒ dte_frac = dte_days
dist      = max(dist_inv, dist_vol, min_dist_pts)
grid      = strike_step, contract master मधून (NIFTY weekly सध्या 50; hardcode नाही)
short_K   = bull put:  floor_to_grid(spot − dist, grid)
            bear call: ceil_to_grid(spot + dist, grid)
long_K    = short_K ∓ width (default 100; पर्याय 50/150/200)
guard:    credit/width ≥ c_min(dte_days)   — c_min table: 1 DTE 0.06, 2 DTE 0.08, 3 DTE 0.10, 4–5 DTE 0.12
          आणि credit ≥ min_credit_pts (3.0)
          आणि short-leg |delta| ≤ max_short_delta (0.30)
guard fail ⇒ credit_fail_action: "skip" (default) | "widen_width" | "try_next_weekly"
```

**Examples.** NIFTY 22,400, IV 13% असताना 1-SD move: dte_frac = 1.0 ⇒ ≈ 183 pts, dte_frac = 5.0 ⇒ ≈ 410 pts (हा अहवालाचा स्वतःचा हिशोब) **[अनुमान]**. Default `session_fraction` मध्ये Monday 12:30 ला Tuesday expiry साठी dte_frac ≈ (180 + 375)/375 ≈ 1.48, म्हणजे ≈ 223 pts. c_min चे default आकडे **कोणत्याही fetched data वर आधारित नाहीत** **[अनुमान]**. Notes स्पष्ट सांगतात की NIFTY credit-to-width by DTE चा public dataset सापडला नाही. म्हणून पहिलं काम: Upstox option-chain history मधून DTE-निहाय distribution मोजा, आणि IS मध्येच c_min calibrate करा.

**Delta.** Directional spreads साठी short delta 0.15–0.30 हा practitioner convention आहे, पण भारतीय स्रोताने पडताळलेला नाही **[दावा, unsourced]**.

**Primary/alternate.** Same-direction counts चे inv वेगळे असतील, तर `dist_inv` सगळ्यात दूरच्या inv वरून घ्या.

### Expiry निवड

```
expiry_rule = "current_unless_today_expiry":
  today = fill ची तारीख (signal ची नाही)
  E = exchange contract master मधून underlying (NIFTY; पर्यायी SENSEX/BSE) ची today किंवा नंतरची पहिली weekly expiry (holiday shift सह)
  जर today == E ⇒ E = त्यानंतरची weekly
  (min_dte_override = off by default. BANKNIFTY ला weekly नाही, म्हणून तो underlying म्हणून या mode मध्ये निवडता येत नाही)
```

NSE नुसार Tuesday holiday असेल तर expiry "previous trading day" ला सरकते ([NSE](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50)) **[पुरावा]**. म्हणून expiry date **कधीच** "पुढचा Tuesday" अशी काढायची नाही. ती नेहमी contract master मधून घ्या.

**[अनुमान]** `try_next_weekly` पर्याय तुमच्या नियमापेक्षा वेगळा आहे, म्हणून तो default बंद आहे. तो फक्त guard fail झाल्यावर वापरायचा, आणि backtest मध्ये वेगळा नोंदवायचा.

### India contract facts (6 Oct 2026 पर्यंत)

| बाब | तथ्य | लेबल | स्रोत |
|---|---|---|---|
| Weekly options | Exchange प्रति एकच benchmark index weekly (20 Nov 2024 पासून) | [पुरावा] | [SEBI circular (CSE copy)](https://www.cse-india.com/upload/upload/Oct_011024.pdf) |
| NIFTY expiry | Weekly आणि monthly **Tuesday** (Sep 2025 पासून). Monthly = शेवटचा Tuesday. Holiday ⇒ आधीचा trading day | [पुरावा] | [NSE](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50); [Business Standard](https://www.business-standard.com/amp/markets/news/nse-bids-adieu-to-thursday-expiry-as-dates-swap-come-into-effect-explained-125082800635_1.html) |
| SENSEX expiry | Weekly आणि monthly **Thursday** (Sep 2025 पासून) | [पुरावा] | [Business Standard](https://www.business-standard.com/amp/markets/news/nse-bids-adieu-to-thursday-expiry-as-dates-swap-come-into-effect-explained-125082800635_1.html) |
| BANKNIFTY | **Weekly बंद (Nov 2024). फक्त monthly.** Monthly शेवटच्या Tuesday ला असावी, पण BANKNIFTY पानावर हे स्वतंत्रपणे पडताळलेलं नाही | [पुरावा]/[अनुमान] | [Business Standard](https://www.business-standard.com/amp/markets/news/nse-bids-adieu-to-thursday-expiry-as-dates-swap-come-into-effect-explained-125082800635_1.html) |
| Lot sizes | NIFTY **65**, BANKNIFTY 30 (Jan 2026 series पासून; 6 Jan 2026 weekly पासून). SENSEX 20 (बदलाची तारीख पडताळलेली नाही) | [पुरावा, secondary] | [HDFC Sky](https://hdfcsky.com/news/nse-revises-market-lot-sizes-for-major-index-derivatives-effective-january-2026); [Sahi](https://www.sahi.com/blogs/nifty-lot-size-2026-bank-nifty-sensex) |
| NIFTY strikes | Weekly/monthly साठी 50-point interval, tick ₹0.05 | [पुरावा] | [NSE](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50) |
| Freeze qty | NIFTY 1,800 units प्रति order (1 Sep 2026 पासून, ≈ 27 lots). एकच secondary स्रोत आहे, म्हणून contract file मधून घ्या | [दावा] | [5paisa](https://www.5paisa.com/blog/nse-quantity-freeze-limits-index-derivatives) |
| STT | Option sale premium वर **0.15%** (1 Apr 2026 पासून; आधी 0.10%). Exercised options वर settlement value च्या 0.15% | [पुरावा] | [ICICI Direct](https://www.icicidirect.com/futures-and-options/articles/stt-changes-in-budget-2026-what-f-o-traders-need-to-know); [Upstox News](https://upstox.com/news/personal-finance/tax/explained-how-the-stt-hike-on-equity-futures-and-options-affects-traders-and-investors/article-189260/) |
| Expiry-day margin | Expiring short options वर **+2% ELM** (20 Nov 2024 पासून). Expiry दिवशी **calendar-spread offset नाही** (1 Feb 2025 पासून) | [पुरावा] | [SEBI circular](https://www.cse-india.com/upload/upload/Oct_011024.pdf); [ICICI Direct](https://www.icicidirect.com/futures-and-options/articles/calendar-spreads-in-f-o-after-sebi-s-new-rules-what-you-need-to-know) |
| SEBI retail algo framework | 1 Apr 2026 पासून: API users साठी **static IP** अनिवार्य. 10 orders/sec वर exchange registration. Market orders ला **market protection** | [पुरावा, broker explainer] | [Zerodha Substack](https://inthemoneybyzerodha.substack.com/p/sebi-algo-trading-changes-april-2026); [Tradejini](https://www.tradejini.com/blogs/what-sebis-new-algo-trading-rules-mean-for-you) |
| Retail outcomes | FY26 मध्ये 87.7% individual F&O traders तोट्यात. Index-options turnover चा 59% expiry दिवशी, ~75% expiry च्या एका दिवसात | [पुरावा, press] | [Open Magazine](https://openthemagazine.com/business/sebi-fo-loss-study-explained-why-9-in-10-retail-traders-lost-91685-crore-in-fy26); [Moneylife](https://www.moneylife.in/article/92-percentage-of-aggregate-losses-incurred-by-individuals-are-from-options-trading-sebi-study/81429.html) |

**[अनुमान] अंमलबजावणीचे परिणाम:**

- Hedge (long) leg आधी, मग short leg. दोन्ही limit orders, किंवा market-protection % सह.
- GitHub Actions runner ला static IP नसतो. म्हणून order placement static-IP VPS किंवा Upstox कडे registered proxy वरूनच करा. Signal generation Actions वर चालू ठेवता येईल.
- STT 0.15% फक्त sold leg च्या premium वर. ₹40 × 65 वर ते ≈ ₹3.9/lot. 1 DTE च्या लहान credits वर हा खर्च लक्षणीय ठरतो.
- ITM leg exercise होऊ देऊ नका. Settlement value वर STT लागतो, म्हणून expiry आधी बंद करा.
- तुमचा "expiry दिवशी next weekly" नियम तीन गोष्टी टाळतो: सर्वात गर्दीचं 0-DTE session, +2% ELM, आणि गमावलेला calendar offset. पण expiring spread आणि नवीन weekly spread एकाच दिवशी असतील, तर expiry दिवशी margin block जास्त लागेल.

---

## 9. Trade management: target zone, 2× credit, close-break, false-break आणि time

MTP: weak trend मध्ये WPT targets वर profit घ्या, strong trend मध्ये ATR trailing ([MTPredictor Intro PDF](https://mtpredictor.com/wp-content/uploads/2021/03/IntrotoMTPredictor21-1.pdf)) **[दावा]**. Kennedy: 1–3% risk, ≥ 3:1 ([Traders.com](https://traders.com/reprints/pdf_reprints/Expired/EW_KENNEDY.pdf)) **[दावा]**. Elliott Wave Forecast: ≥ 2:1 ([EWF](https://elliottwave-forecast.com/elliottwave/where-to-place-stop-losses-using-the-elliott-wave-principle/)) **[दावा]**. Breakeven-move, time-stop आणि scaling चे स्पष्ट नियम free primary स्रोतांत **सापडले नाहीत**. खालचे सगळे **[अनुमान]** आहेत, आणि parameters म्हणून ठेवायचे.

**Exit priority क्रम.** क्रम 0 (spot ने short strike ओलांडणं) दर tick/poll वर तपासायचा. बाकी सगळे प्रत्येक bar close वर, वरून खाली (premium stop फक्त `hard_stop_eval = "intrabar"` असेल तेव्हाच दर tick वर). पहिला लागू झालेला exit जिंकतो.

**Exits कधीच block होत नाहीत.** `entry_start`/`entry_end`, vote, `max_daily_loss_pct`, `max_open_spreads`, `htf_gate_enabled`, `trading_mode`/`live_approved` या सगळ्या settings फक्त **नवीन entries** थांबवतात. Exit order (आणि manual "close all") कोणत्याही mode मध्ये, कोणत्याही वेळी पाठवता येते. Live exit साठी नवीन approval लागत नाही.

| क्रम | Exit | अट (default) | Re-entry |
|---|---|---|---|
| 1 | **Hard invalidation real break** | Trade-degree hard_inv वर real break (विभाग 7/14: buffer पलीकडे close + displacement, किंवा पुढची candle reclaim नाही, किंवा failed retest; level च्या TF वर) | नाही |
| 0 | **Emergency (intrabar)** | Spot ने **short strike** स्वतः intrabar ओलांडला (`emergency_spot_cross_short = true`). Strike invalidation च्या पलीकडे ठेवलेला असल्याने इथे structure आधीच तुटलेलं असतं; 1 DTE gamma मध्ये candle close ची वाट नाही. (विभाग 14 Q5) | नाही |
| 2 | **Hard premium stop** | Spread MTM debit ≥ `hard_stop_mult` (2.0) × entry credit, **candle close वर** (`hard_stop_eval = bar_close`). Option premium चे intrabar wicks (gamma, bid-ask रुंदावणं) false signal देतात; खरा धोका underlying च्या structure वरून (क्रम 1) आणि strike cross वरून (क्रम 0) पकडला जातो | Hard_inv अबाधित असेल तर नवीन setup ची परवानगी (`reentry_after_premium_stop` = false default) |
| 3 | **Soft timing stop** | Reversal candle extreme ± soft_buffer वर real break | हो, `max_reentries` = 1 |
| 4 | **Target zone** | Tier B (C waves), `tierB_exit_mode = opposite_reversal` (default, विभाग 14 Q4): C चा zone (B end + 0.618/1.0/1.618 × A) फक्त **कुठे लक्ष ठेवायचं** हे सांगतो. **पूर्ण exit तेव्हाच** जेव्हा C त्या zone मध्ये किंवा विरुद्ध major level वर पोचून **विरुद्ध दिशेचा logical reversal** (विभाग 6, mirror) देतो, म्हणजे उलट setup चा trigger. C ने zone/level acceptance ने (real break) ओलांडला तर hold, आणि `progressive_inv` (C च्या आतल्या शेवटच्या confirmed sub-wave चा तळ) ने संरक्षण. पर्याय `fixed_mult`: spot ≥ B end + `tierB_target_mult` × A ⇒ exit (फक्त P-तुलनेसाठी). Tier A: T1 = (ii) end + `tierA_target_fibs[0]` (1.0) × (i) गाठलं की `tierA_target_action` = "exit_50pct_trail_rest": निम्मे lots बंद, उरलेले lots `progressive_inv`, क्रम 5–8 ने बंद | — |
| 5 | **Profit % credit** | Captured ≥ `tp_pct_credit` (Tier A 65%, Tier B 50%, Tier C 40%) | — |
| 6 | **Time exit (progress)** | Entry नंतर `progress_bars` (= `progress_bars_mult` 1.0 × bars_last_subleg, विभाग 6) TTF bars मध्ये spot (close) ने correction च्या शेवटच्या D−1 sub-leg चा origin (bull put: शेवटचा D−1 pivot high; bear call: pivot low) ओलांडला नाही ⇒ exit | — |
| 7 | **Expiry-day time exit** | Expiry दिवशी `expiry_exit_time` (14:45) ला spot short strike पासून < `expiry_hold_min_dist_sd` (0.5 SD remaining) ⇒ exit. नाहीतर expire होऊ द्या, पण ITM leg कधीच नाही | — |
| 8 | **Thesis-complete exit** | Bull put चा next motive पूर्ण झाला असं count सांगतो, किंवा opposite-direction setup trigger झाला | — |

**False-break नियम.** Wick inv पलीकडे जाऊन close परत आत आला, किंवा एकच close पलीकडे जाऊन पुढच्या `break_no_reclaim_bars` मध्ये reclaim झाला, तर exits 1 आणि 3 लागत नाहीत. यामागचा तर्क असा: 1 DTE वर गर्दीचे wicks वारंवार येतात, आणि real-break नियम खोटे exits कमी करतो. **धोका:** एका bar मध्ये तीव्र हालचाल झाली तर exit उशिरा होतो. Spread defined-risk असल्याने कमाल तोटा width − credit इतकाच मर्यादित आहे. Intrabar premium stop (`hard_stop_eval = "intrabar"`) हा पर्याय आहे, पण तो wick वर exit करू शकतो, म्हणजे false-break नियमाच्या विरुद्ध. म्हणून default bar close आहे. ही तडजोड backtest मध्ये P4 ने मोजायची.

**Sizing.** Max loss = (width − credit) × lot_size × lots. lot_size contract master मधून (NIFTY सध्या 65; hardcode नाही). `risk_per_trade_pct` (1.0% capital) × tier multiplier मधून lots काढा. Lots freeze qty पेक्षा जास्त झाले तर order slicing करा. Kennedy च्या 1–3% शी सुसंगत **[दावा]**.

**Breakeven/trail.** Credit spread मध्ये stop हलवणं म्हणजे exit-level बदलणं. Spot ने (i) चं टोक ओलांडलं (S1/S2), तर `hard_inv` वर हलवून correction end (wave 2 end) करा. कारण त्यानंतर तो level तुटला तर (i)-(ii) count मेला. हे फक्त नियम क्रमाने लावणं आहे, नवीन धारणा नाही **[अनुमान]**. `progressive_inv = true` (default).

---

## 10. Worked regression example: NIFTY, 5–6 Oct 2026

**इशारा:** खालच्या किमती screenshots वरून घेतलेल्या अंदाजे आहेत (±10–15 pts). IV, intraday spot आणि option premiums प्रत्यक्ष data वरून तपासलेले नाहीत. हे उदाहरण **spec कसा वागतो** हे दाखवण्यासाठी आहे. ते edge चा पुरावा नाही.

**Context (D+2).** 23,190 → 22,217 ही घसरण आहे, म्हणजे मोठा downtrend. ती एकतर 5-wave impulse आहे, किंवा A-B-C. त्यानंतरची चढण **correction** आहे (D+1). Trade degree D हे त्या correction चे legs.

| वेळ / घटना | किंमत (अंदाजे) | Spec ची तपासणी | निर्णय |
|---|---|---|---|
| A: 22,217 → 22,621 | +404 | Impulsive (5 सलग मजबूत candles आणि gap). Trend (D+2) विरुद्धचा पहिला leg. **[अनुमान]** A चं 5-wave subdivision screenshot वरून गृहीत; candles ची संख्या म्हणजे waves नव्हेत, engine ने D−1 pivots वर ते तपासायला हवं | — |
| **5 Oct 09:50 आणि 10:15**: A-end bear calls | ~22,600 | R4 नुसार trend विरुद्धची पहिली 5-wave हालचाल correction चा शेवट नाही. A नंतर येणारा B corrective आहे, motive नाही. **Rejection चं कारण फक्त R4 (नियम) आहे.** "C हा A चं टोक ओलांडतो" हे मार्गदर्शक आहे (R6 चा C भाग), नियम नाही | **Rejected (A-end ban).** नंतर C ने 22,731 गाठलं (22,621 च्या वर), पण हे निकालाचं निरीक्षण आहे, rejection चं कारण नाही |
| B: 22,621 → ~22,396 | −225 = **A च्या 55.7%** | Zigzag B band 38–79% **[मार्गदर्शक]** ([EWP Outline](https://elliottwaveplus.com/wp-content/uploads/2016/11/Guide-2-Wave-Notes-An-Outline-of-the-Wave-Principle.pdf)). आतून a-b-c (22,467 / 22,522 / 22,396). B < 90% A ⇒ R7 नुसार flat नाही ⇒ zigzag. A origin (22,217) अबाधित | Setup **S6a** सक्रिय |
| **5 Oct ~12:15–12:30**: B-end reversal candle | spot ~22,400–22,420 | Touch (zone: 0.5–0.618 × A, A टोकापासून = 22,419–22,371; B-end zone_fibs चा उपसंच), reclaim (close > touched level), strength, score. B चा c leg tentative, A आणि B चे a, b pivots confirmed (C4). DTE: आज Monday, 6 Oct Tuesday expiry ⇒ **current weekly (6 Oct), dte_days = 1** (dte_frac ≈ 1.48) (दुरुस्ती 2). Tier B (D+1 correction ची दिशा; D+2 विरुद्ध) ⇒ 0.5× | **Bull put स्वीकारला** |
| Strike (S6a) | — | hard_inv = 22,217 (A origin). dist_inv ≈ 22,410 − 22,217 + 25 ≈ 218. dist_vol (IV 13% गृहीत, dte_frac ≈ 1.48) ≈ 223 (dte_frac = 1.0 घेतल्यास ≈ 183). dist = 223 ⇒ 22,187 ⇒ short **22,150 PE** (50-grid floor), long 22,050 PE (width 100). दोन्ही dte_mode मध्ये strike तोच. Credit guard (1 DTE c_min 0.06): प्रत्यक्ष premium तपासलेलं नाही | **[अनुमान]** Guard पास झाला असता का हे data वरून तपासा |
| (i) of C, मग (ii) of C | (ii) end ~22,45x–22,5xx | C चा (ii) B end (22,396) च्या वर (R1, lower degree) | Setup **S13** सक्रिय |
| **5 Oct ~13:30**: C-(ii) reversal | spot ~22,480–22,520 (अंदाजे) | hard_inv = **22,396**. Tier B. Expiry अजूनही 6 Oct (1 DTE) | **दुसरा bull put स्वीकारला** |
| Strike (S13) | — | dist_inv ≈ 22,500 − 22,396 + 25 ≈ 129. dist_vol (dte_frac ≈ (115 + 375)/375 ≈ 1.31) ≈ 211. dist = 211 (vol जिंकतो) ⇒ 22,289 ⇒ short **22,250 PE**, long 22,150 PE. (`dte_mode = whole_days` घेतल्यास dist_vol ≈ 184 ⇒ short 22,300 PE.) **गृहीत:** 13:30 ला "C-(ii) अजून संपला नाही / B अजून चालू" हा same-direction alternate count `alt_weight_min` (0.25) पेक्षा कमी score चा होता. तसा नसेल तर dist_inv सगळ्यात दूरच्या inv (22,217) वरून ⇒ ≈ 308 ⇒ short 22,150 PE | **[अनुमान]** |
| C चालू | → 22,731 | C ने A चं टोक ओलांडलं (R6 चा C भाग, मार्गदर्शक ✔). 0.618A (B end पासून) = 22,646 पार. C = 1.0A = 22,396 + 404 = **22,800** अजून नाही. C हळू आणि overlapping आहे ⇒ ending diagonal ची शक्यता (alternate; C म्हणून ending diagonal "rarely", Outline) | Tier B target = C = 1.0A (`tierB_target_mult`) ⇒ C zone 22,780–22,805 अजून गाठला नाही, म्हणून क्रम-4 exit नाही |
| **6 Oct (expiry)**: low ~22,560, close ~22,717 | — | 22,560 > 22,396 > 22,250 > 22,150. एकही hard_inv वर real break नाही, आणि short strikes पासून spot दूर | **दोन्ही bull puts OTM राहिले.** पण spec च्या क्रम 5 (Tier B `tp_pct_credit` = 50%) नुसार दोन्ही spreads बहुधा expiry आधीच, 5 Oct दुपारी किंवा 6 Oct सकाळी, 50% credit capture वर बंद झाले असते. नेमकी वेळ premium data शिवाय सांगता येत नाही **[अनुमान]**. जे spread तोपर्यंत उघडे राहिले, त्यांच्यासाठी 14:45 ला spot short strike पासून ≥ 0.5 SD remaining ⇒ hold/expire |
| 6 Oct चा 22,560 dip | — | तीन counts शक्य: (a) C चा (iv), जर (i) of C चं टोक < 22,560 असेल (R3, impulse नियम). (b) Ending diagonal चा wave 4 (overlap सहसा, R9; wave 2 end पलीकडे नाही, नियम). (c) C 22,731 ला संपला. Counts gray आहेत, आणि 6 Oct expiry दिवस असल्याने नवीन trade 13 Oct weekly वर गेला असता | S14 (Tier C) फक्त (a) प्रबळ असेल तरच. Diagonal-संशय असेल तर default skip **[अनुमान]** |

**पुढचा संभाव्य bear call: फक्त C च्या शेवटी.** याला setup S7 म्हणता येईल: D+1 correction संपून D+2 downtrend पुन्हा सुरू होणं. **[अनुमान]**

1. **Zone 1: 22,780–22,805.** C = 1.0 × A (≈ 22,800) आणि 22,801 चा आधीचा lower high. इथे reversal candle (touch, reclaim खाली, strength, score) ⇒ bear call. Expiry: 6 Oct नंतर current weekly = **13 Oct** (Tuesday). Hard inv: D+2 घसरण 5-wave impulse (wave 1) असेल तर ही correction wave 2 ⇒ inv **23,190** (R1). D+2 घसरण A-B-C (पूर्ण correction) म्हणून preferred असेल, तर 22,217 पासूनची चढण नवीन motive असू शकते, bear call साठी नियम-आधारित inv उरत नाही ⇒ setup नाही (vote/`alt_block_weight` ने skip). Soft stop = reversal candle high. Strike (spot ≈ 22,790): dist_inv ≈ 23,190 − 22,790 + 25 ≈ 425 वि. dist_vol (IV 13%; 7 Oct entry ⇒ dte_frac ≈ 4.5 ⇒ ≈ 396; 6 Oct expiry-दिवशी entry ⇒ 13 Oct, dte_frac ≈ 5.5 ⇒ ≈ 438) ⇒ entry दिवसानुसार inv- किंवा vol-आधारित. Tier A फक्त तेव्हाच, जेव्हा D+2 चा preferred count "wave 1 पूर्ण, हा wave 2" असेल (2→3). Bullish alternate count (22,217 पासून नवीन 1-2-3) चं vote तपासा.
2. **Zone 2: 23,027–23,050.** 22,805 वर acceptance झाला तर: 1.618 × A ≈ 22,396 + 654 ≈ 23,050, आणि crash चा उगम 23,027. इथे पुन्हा reversal ची वाट पाहायची. **22,805 च्या break वर काहीच नाही** (breakout ban).
3. **23,190 च्या वर close** ⇒ wave-2 count मेला. HTF downtrend count रद्द. तेव्हा नवीन A-B-C pullback पूर्ण झाल्यावरच bull put.

**या उदाहरणातून दिसलेल्या दुरुस्त्या.** जुन्या spec ने P2 (HTF gate) मुळे दोन्ही bull puts block केले असते (दुरुस्ती 1). min_dte = 2 मुळे ते 13 Oct expiry वर ढकलले असते, म्हणजे जास्त premium, पण जास्त exposure आणि वेगळी risk (दुरुस्ती 2). A-end bear calls दोन्ही specs ने नाकारले असते. पण कारण आता नियम R4 आणि "पुढची wave corrective आहे" हे आहे, HTF नाही. हे फक्त एका दिवसाचं उदाहरण आहे, म्हणजे n = 2 trades. त्यातून सांख्यिकीय निष्कर्ष काढता येत नाही.

---

## 11. Dashboard settings: सगळे parameters आणि defaults

सगळ्या settings **[अनुमान]** आहेत, म्हणजे free parameters. त्यांचे defaults IS मध्ये पुन्हा calibrate करायचे.

**Default ची स्थिती.** खालचे defaults स्रोत/नियमावर आधारित आहेत, म्हणून calibrate करायचे नाहीत: `similarity_balance_min` 1/3 (Neely), flat B ≥ 0.9A (R7), `strength_min`/`strength_max` 1.2/2.5 आणि `expiry_rule` (तुमचे नियम), `underlying`/expiry/lot/strike_step/freeze qty (contract master), STT 0.15% (Budget 2026), `htf_gate_enabled = false` (दुरुस्ती 1), `trading_mode = paper`. **बाकी प्रत्येक आकडा data-backed नाही ⇒ "calibration आवश्यक"** (IS walk-forward मध्ये, pre-registered grid सह). Code मध्ये एकही आकडा hardcode करायचा नाही. Supabase मध्ये `settings` table ठेवा, आणि Streamlit form मधून ती बदला. प्रत्येक trade सोबत त्या वेळच्या settings चा snapshot (hash) log करा.

| गट | Setting | Default | पर्याय / नोंद |
|---|---|---|---|
| **Mode / safety** | `trading_mode` | **paper** | paper / live. Live फक्त `live_approved = true` असताना |
| | `live_approved` | false | फक्त trader स्वतः dashboard वर बदलतो (timestamp + user log). Code कधीच true करत नाही. Exits वर परिणाम नाही |
| **Instrument** | `underlying` | NIFTY | SENSEX (BSE weekly, पर्यायी). BANKNIFTY weekly नाही (Nov 2024 पासून), म्हणून या weekly mode मध्ये निषिद्ध |
| | `contract_master_source` | Upstox instruments file | expiry, lot_size, strike_step, freeze_qty इथूनच. Hardcode नाही |
| **Data** | `structure_symbol` | underlying चा spot/index | Futures नाही (Neely cash data) |
| | `structure_tf` | 5m | 3m / 5m / 15m. Pivots/counts याच TF वर |
| | `degree_tf_mode` | **auto_by_bars** | auto_by_bars / fixed. Auto: setup च्या corrective wave साठी {5m, 15m, 30m, 1H, 1D} पैकी सर्वात लहान TF जिथे त्या wave चे बंद bars `tf_bars_min`–`tf_bars_max` मध्ये येतात (विभाग 14 Q3) |
| | `tf_bars_min` / `tf_bars_max` | 8 / 40 | **Calibration आवश्यक**. कमी bars ⇒ sub-waves दिसत नाहीत; जास्त ⇒ noise (Neely: खूप swings ⇒ मोठा chart) |
| | `degree_tf` | (fixed mode मध्येच) | प्रति degree TF, उदा. D0 = 5m, D1 = 15m, D2 = 1H, D3 = 1D |
| | `trigger_tf_mode` | level_tf | level_tf / fixed (तुमचा नियम: candle TF = level TF) |
| | `trigger_tf_fixed` | 5m | फक्त mode = fixed |
| | `atr_len` | 14 | |
| **Degrees / swings** | `degree_levels` | 4 (D0–D3) | 2–5 |
| | `swing_mode` | atr | atr / pct / fractal |
| | `swing_atr_mult` | [1.5, 3.0, 6.0, 12.0] | प्रत्येक degree साठी, ×ATR(degree_tf). Pivot confirm: बंद bars च्या high/low वरून opposite move ≥ θ_d; confirmed_at = तो bar |
| | `swing_pct` | [0.15, 0.30, 0.60, 1.20] % | pct mode साठी |
| | `similarity_balance_min` | 0.333 | Neely 1/3 (price OR time) |
| | `trade_degrees_enabled` | D0, D1, D2 | कोणत्या degrees वर trades |
| **Count engine** | `beam_k` | 5 | प्रति degree जास्तीत जास्त valid counts |
| | `guideline_weights` | equal (1.0) | EWI: unweighted guideline count. Weights फक्त IS मध्ये |
| | `hysteresis_margin` | 0.15 | Preferred बदलण्यासाठी score फरक |
| | `vote_min` | 0.60 | |
| | `alt_weight_min` | 0.25 | Strike साठी विचारात घ्यायचे counts |
| | `alt_block_weight` | 0.35 | Opposite count एवढा मजबूत ⇒ skip |
| | `impulse_time_rule` | score | off / score / filter (Neely OR-नियम) |
| | `c_time_rule` | delay | off / score / delay (t(c) ≤ t(a)+t(b); Terminal C ला सूट) |
| | `wave4_overlap_strict` | true | Intraday overlap सुद्धा मोजायचा |
| | `count_inv_basis` | real_break | real_break / wick (strict EWP). विभाग 7 |
| | `zigzag_b_band` | [0.38, 0.79] | फक्त score (मार्गदर्शक) |
| | `flat_b_max_ratio` | 2.0 | B > 2×A ⇒ flat count सोडा [अनुमान] |
| | `barrier_d_tol_atr` | 0.25 | Barrier triangle मध्ये D चा B पलीकडचा tolerance |
| **Setups** | `setups_enabled` | S1, S2, S3, S4, S6a, S6b, S6c, S7, S9, S10, S12, S13 | S5, S8, S11, S14 default **off** |
| | `htf_gate_enabled` | **false** | true ⇒ Tier B block (दुरुस्ती 1) |
| | `min_corrective_legs` | 3 | A-end ban (R4) |
| | `zone_fibs` (प्रति setup) | उदा. zigzag C: [0.618, 1.0, 1.618] × A; B-end: [0.382, 0.5, 0.618, 0.786] × A; W2: [0.382, 0.5, 0.618, 0.786] | |
| | `zone_tol_atr` | 0.5 | |
| **Entry trigger** | `reclaim_ref` | touched_level | zone_high. (prev_bar_high / sub-wave (iv) break **निषिद्ध**: breakout) |
| | `touch_reclaim_window` | **3** | Composite rejection candle (1–3 candles merge; अनिर्णय असेल तर follow-through ने कमाल 4). विभाग 14 Q2 |
| | `rsi_len` | 14 | फक्त w_div > 0 असेल तर |
| | `strength_min` / `strength_max` | 1.2 / 2.5 | × median range |
| | `median_range_n` | 20 | |
| | `rejection_weights` | wick 0.30, close-loc 0.30, body 0.20, time 0.20, div 0.00 | |
| | `rejection_min` | 0.60 | |
| | `entry_start` / `entry_end` | 09:30 / 14:45 | U-shape: पहिली 15 मिनिटं टाळा |
| | `fill_mode` | next_open | next_open / limit_mid |
| **Context / sizing** | `tier_mult` | A 1.0, B 0.5, C 0.25 | C = 0 ⇒ skip |
| | `leading_diag_mult` | 0.75 | |
| | `risk_per_trade_pct` | 1.0 | % capital, max loss आधारित |
| | `max_open_spreads` | 2 | |
| | `max_daily_loss_pct` | 2.0 | फक्त नवीन entries थांबवतो, exits नाही |
| **Strike / expiry** | `expiry_rule` | current_unless_today_expiry | (दुरुस्ती 2) |
| | `min_dte_override` | off | |
| | `inv_buffer_mr` | 0.5 | × median range. Break buffer (0.25 × MR) पेक्षा मोठा, म्हणजे count मरण्याआधी spot short strike ला पोचत नाही |
| | `k_sd` | 1.0 | 0.8–1.2 |
| | `iv_source` | ATM IV (chosen expiry) | India VIX fallback |
| | `dte_mode` | session_fraction | whole_days (विभाग 8 व्याख्या) |
| | `strike_step` | contract master | NIFTY weekly सध्या 50 |
| | `min_dist_pts` | 100 | |
| | `width_pts` | 100 | 50 / 100 / 150 / 200 |
| | `c_min_by_dte` | {1: 0.06, 2: 0.08, 3: 0.10, 4: 0.12, 5: 0.12} | **Data वरून calibrate** |
| | `min_credit_pts` | 3.0 | |
| | `max_short_delta` | 0.30 | |
| | `credit_fail_action` | skip | widen_width / try_next_weekly |
| **Management** | `break_buffer_mr` | 0.25 | Real break buffer = हे × median range (fixed points नाहीत). विभाग 7, 14 Q1 |
| | `break_displacement_confirm` | true | Breaking candle स्वतः ताकदीचा (range ≥ strength_min × MR, close टोकाच्या `break_close_loc` 0.30 भागात) ⇒ त्याच close वर real break |
| | `break_no_reclaim_bars` | 1 | कमकुवत breaking close नंतर इतके bars reclaim नाही ⇒ real break. 0 ⇒ एक-close exit (तुमच्या नियमाविरुद्ध, फक्त P4 साठी) |
| | `break_retest_confirm` | true | Break नंतर L चा retest उलट logical reversal ने नाकारला ⇒ real break |
| | `emergency_spot_cross_short` | true | Spot short strike intrabar ओलांडतो ⇒ लगेच exit (क्रम 0) |
| | `tierB_exit_mode` | opposite_reversal | opposite_reversal / fixed_mult. विभाग 14 Q4 |
| | `break_confirm_tf` | level_tf | level_tf / 5m / 15m |
| | `false_break_no_exit` | true | |
| | `hard_stop_mult` | 2.0 | × credit |
| | `hard_stop_eval` | bar_close | bar_close / intrabar |
| | `soft_stop_action` | exit | exit / reduce / alert |
| | `soft_buffer_pts` | 5 | |
| | `max_reentries` | 1 | फक्त soft stop नंतर |
| | `reentry_after_premium_stop` | false | |
| | `tp_pct_credit` | A 65, B 50, C 40 | |
| | `tierA_target_action` | exit_50pct_trail_rest | exit_all (विभाग 9 क्रम 4 व्याख्या) |
| | `tierA_target_fibs` | [1.0, 1.618] × (i), (ii) end पासून | |
| | `tierB_target_mult` | 1.0 | फक्त `tierB_exit_mode = fixed_mult` मध्ये. Default mode मध्ये C zone चा मध्य म्हणून alert |
| | `target_tol_atr` | 0.25 | |
| | `progress_bars_mult` | 1.0 | × bars(last corrective leg) |
| | `expiry_exit_time` | 14:45 | |
| | `expiry_hold_min_dist_sd` | 0.5 | |
| | `progressive_inv` | true | (i) टोक ओलांडल्यावर inv = wave-2 end |
| | `lower_inv_action` | alert | reduce / exit |
| **Execution / compliance** | `order_type` | limit | market_with_protection |
| | `market_protection_pct` | 1.0 | |
| | `leg_order` | hedge_first | |
| | `slice_to_freeze_qty` | true | qty contract master मधून |
| | `static_ip_host` | (VPS) | SEBI framework |
| **Backtest** | `cost_model` | STT 0.15% sell premium (1 Apr 2026 पासून; आधीच्या काळात त्या वेळचा दर), brokerage, exchange, GST, stamp, slippage | काळानुसार दर table |
| | `slippage_ticks` | 2 प्रति leg | |
| | `wf_train_years` / `wf_test_months` | 2 / 6 | Walk-forward |
| | `split_embargo_expiries` | 1 | Split सीमांवर |
| | `pbo_max` | 0.05 | PBO > ⇒ reject |
| | `min_cell_n` | 30 | यापेक्षा कमी n ⇒ निष्कर्ष नाही |

---

## 12. Code साठी data structures, algorithm आणि no-repaint चाचण्या

### Data structures **[अनुमान]**

MQL5 चा wave-tree (`TNode`, `TWave`) आणि WaveBasis/LuxAlgo चे धोरणं ([MQL5](https://www.mql5.com/en/articles/260); [LuxAlgo](https://www.luxalgo.com/library/indicator/elliott-wave/)) यांच्यावरून:

```python
@dataclass(frozen=True)
class Pivot:
    degree: int            # 0..3
    kind: str              # "H" | "L"
    price: float
    bar_idx: int           # extreme चा bar
    confirmed_at: int      # opposite move ≥ θ_d झाल्याचा bar (knowable_at)
    status: str            # "tentative" | "confirmed"

@dataclass
class Leg:
    degree: int; start: Pivot; end: Pivot
    length: float; bars: int; speed: float
    overlap_flag: bool     # lower-degree subdivision overlapping?
    sub_count: int         # lower degree swings (3/5/other)

@dataclass
class CountNode:
    id: str; degree: int
    pattern: str           # impulse | lead_diag | end_diag | zigzag | flat_reg | flat_exp | flat_run | tri_contr | tri_barrier | tri_exp | wxy | wxyxz
    labels: list[str]      # ["1","2","3"] किंवा ["A","B"] (unfinished सह)
    pivots: list[Pivot]
    parent_id: str | None; children: list[str]
    current_wave: str      # सध्या चालू wave label
    next_expected: str     # "up" | "down"
    hard_inv: float        # नियम-स्तर
    inv_rule: str          # "R1" "R3" "R6" ...
    confirm_level: float | None
    targets: list[tuple[float, float]]   # zones
    time_flags: dict       # impulse_time_ok, c_time_violation
    guideline_hits: dict   # {fib_c_eq_a: 1, alternation: 0, channel: 1, ...}
    score: float
    status: str            # active | invalidated
    created_at: int; invalidated_at: int | None

@dataclass
class Setup:
    id: str; setup_code: str           # "S6a"
    count_id: str; degree: int; tier: str
    direction: str                     # "bull_put" | "bear_call"
    zone: tuple[float, float]
    hard_inv: float; soft_stop: float | None
    vote: float; trigger_bar: int | None
    settings_hash: str

@dataclass
class Trade:
    setup_id: str; expiry: date; short_k: int; long_k: int
    lots: int; credit: float; entry_bar: int
    exits: list[dict]; reentries_used: int
```

### प्रति-bar update loop **[अनुमान]**

```
on_bar_close(t):
 1. Pivots: प्रत्येक degree d साठी degree_tf[d] चा bar बंद झाल्यावर tentative pivot update.
    बंद bars च्या high/low वरून opposite move ≥ θ_d ⇒ confirm (confirmed_at = t). Confirmed pivot कधीच हलत नाही.
    Similarity & Balance (≥1/3 price OR time) ने degree assignment तपासा.
 2. Invalidation: प्रत्येक active CountNode साठी, hard_inv वर count_inv_basis नुसार break (default real break, विभाग 7)
    ⇒ invalidate (log ठेवा). मग त्याच parent खाली relabel प्रयत्न. नसेल तर parent तपासा (cascade).
 3. Extend: नवीन confirmed pivot ⇒ प्रत्येक active node चे legal continuations generate करा
    (rules R1–R10 ने prune). फक्त confirmed pivots completed waves साठी. Tentative फक्त current wave साठी.
 4. Cross-degree: degree d चा node admissible फक्त तेव्हाच जेव्हा तो कोणत्यातरी active d+1 node च्या
    current_wave चा legal subdivision आहे. Joint score = parent × child.
 5. Score: guideline_hits (Fib, alternation, channel, equality, depth, time flags, personality proxies)
    ⇒ score. Beam: top beam_k per degree. Preferred बदल फक्त hysteresis_margin ओलांडल्यावर.
    Higher degrees कधीच scratch ने recount करायचे नाहीत (evolve forward). फक्त त्यांचा hard_inv तुटल्यावर.
 6. Setups: preferred node म्हणतो "corrective wave संपण्याच्या zone मध्ये" ⇒ Setup तयार करा
    (setup_code, tier from parent/grandparent, zone, hard_inv). Vote काढा.
 7. Trigger: विभाग 6 चे C0–C4, T1–T6, setup च्या TTF वर. पास ⇒ signal (knowable_at = t). Fill t+1 open.
    trading_mode = live असेल आणि live_approved = false ⇒ order नाही, फक्त paper log.
 8. Strike/expiry: विभाग 8 (expiry/DTE fill तारखेवरून). Guard fail ⇒ credit_fail_action.
 9. Manage open trades: विभाग 9 चा priority क्रम. हा step entry-filters च्या आधी/स्वतंत्र चालतो; कोणतीही entry setting तो block करत नाही.
10. Log: pivots, counts (active आणि invalidated), setups, signals, trades. प्रत्येकाला knowable_at आणि settings_hash.
```

### No-repaint आणि causality चाचण्या (CI मध्ये, प्रत्येक commit वर) **[अनुमान]**

1. **Truncation invariance.** Data bar t वर कापून engine पुन्हा चालवा. ज्यांचा `knowable_at ≤ t` आहे असे सगळे pivots, counts, setups आणि signals full-run मधल्यांशी **हुबेहूब** जुळायला हवेत.
2. **Signal immutability.** एकदा emit झालेला signal कोणत्याही नंतरच्या bar वर बदलत किंवा गायब होत नाही. Invalidated counts log मध्ये राहतात.
3. **HTF join.** मोठ्या timeframe चे bars फक्त ते **बंद** झाल्यावरच वापरा (merge_asof on close time).
4. **Fill lag.** Close-based signal चा fill t+1 open वर. Same-bar fill ⇒ test fail.
5. **Expiry calendar.** त्या दिवसाचं प्रत्यक्ष expiry, lot size आणि STT दर, historical contract master मधून.
6. **Tentative-pivot ban.** एकाही completed-wave rule check मध्ये tentative pivot वापरला गेला तर test fail.
7. **False-break test.** Synthetic paths: (a) wick hard_inv पलीकडे, close आत ⇒ exit नाही; (b) एक close L − buf पलीकडे, पुढचा close ≥ L ⇒ exit नाही; (c) close पलीकडे आणि पुढचे `break_no_reclaim_bars` closes पलीकडेच ⇒ exit bar t+n वर. एकही चुकला ⇒ fail.
8. **Breakout-ban test.** प्रत्येक emitted bull-put signal साठी assert: (a) reclaim bar चा close < H, जिथे H = correction च्या शेवटच्या D−1 sub-leg चा origin (low आधीचा शेवटचा D−1 pivot high); म्हणजे entry correction च्या आत आहे, sub-leg origin/2-4 line च्या break नंतर नाही. (b) reclaim_ref ∈ {touched_level, zone_high}. Bear call साठी mirror. यांपैकी एक चुकला ⇒ fail.
9. **Exit-never-blocked test.** entry window बाहेर, max_daily_loss गाठल्यावर, vote < min असताना, live_approved = false असताना exit signals तरीही order तयार करतात हे assert करा.
10. **Golden-file test.** 5–6 Oct 2026 चे 5m bars fixture म्हणून ठेवा. 09:50 आणि 10:15 ला A-end setup **नाही**, आणि B-end (S6a) व C-(ii) (S13) setups हे **किमान अपेक्षा** म्हणून assert करा. पण ते फक्त प्रत्यक्ष data वर label मॅच झाल्यावरच.

---

## 13. Backtest protocol: P1–P16, splits, baselines आणि overfitting नियंत्रण

### P1–P16 (सुधारित)

| P# | नियम | बदल (आधीच्या तुलनेत) | काय तपासायचं |
|---|---|---|---|
| P1 | Causal multi-degree swings + `confirmed_at` | 4 degrees | No-repaint suite. Degree-निहाय label stability |
| **P2** | **HTF context ⇒ tier multiplier आणि target. Gate पर्यायी** | **Gate ⇒ context (दुरुस्ती 1)** | Gate-on वि. gate-off. Tier B ची स्वतंत्र expectancy |
| P3 | A-end ban (min 3 corrective legs) | — | A-end entries (counterfactual) वि. पूर्ण correction entries |
| P4 | Hard inv real-break exit (close + buf + n bars no reclaim) + false-break no-exit | एक-close exit काढला | Real-break वि. एक-close वि. tick-basis वि. hold; count_inv_basis real_break वि. wick; hard_stop_eval close वि. intrabar |
| P5 | Strike = max(inv+buffer, k·σ√T), DTE-निहाय credit guard | c_min DTE-निहाय | EW-strike वि. same-delta strike: breach rate |
| P6 | Reversal trigger (touch, reclaim, strength, score, Stage-1 time) | reclaim_ref पर्याय | Candle-only वि. +time वि. random-time entry |
| P7 | Overlap/5-vs-3 classifier | — | Impulsive-like वि. corrective-like counter-legs |
| P8 | Pattern blocks (ending diagonal, expanding) | — | Block केलेल्या trades चा counterfactual P&L |
| P9 | Depth feature (buckets), Neely 61.8% trending | — | Bucket-निहाय breach rate वि. bootstrap |
| **P10** | **Time features: Neely OR-नियम, t(c) ≤ t(a)+t(b)** | **"Correction > impulse" काढलं (दुरुस्ती 3)** | Delay वि. no-delay |
| P11 | Similarity & Balance | — | Gate सह वि. शिवाय |
| P12 | Alternate-count vote / gray skip | Vote आधारित | Conflict trades वि. clean trades |
| **P13** | **Time-of-day + expiry rule (current unless today expiry)** | **min_dte काढलं (दुरुस्ती 2)** | DTE bucket (1–5) निहाय expectancy; 1 DTE ची tail |
| P14 | Round-number feature | — | Round-number पलीकडचे strikes |
| P15 | Fibonacci zones फक्त hypothesis | — | Random-ratio आणि shifted-Fib baselines |
| P16 | Hurst (प्रायोगिक), Gann नाही | — | Randomized dates |

### Splits आणि regime

| भाग | काळ | उपयोग |
|---|---|---|
| IS | 2015-01 → 2021-12 | सगळं calibration. Walk-forward: 2 वर्षं train / 6 महिने test |
| VAL | 2022-01 → 2024-03 | IS मध्ये निवडलेल्या ≤ 3 configurations. Tuning नाही |
| Holdout (sealed) | 2024-04 → आज | **एकदाच**, अंतिम एकाच configuration साठी |

**Regime इशारा [पुरावा + अनुमान].** Holdout काळात बरेच नियामक बदल येतात:

- 20 Nov 2024: weekly rationalisation आणि +2% ELM.
- 1 Feb 2025: expiry-day calendar offset बंद.
- Sep 2025: NIFTY expiry Thursday → Tuesday.
- Jan 2026: lot 65.
- 1 Apr 2026: STT 0.15% आणि algo framework.

([SEBI circular](https://www.cse-india.com/upload/upload/Oct_011024.pdf); [Business Standard](https://www.business-standard.com/amp/markets/news/nse-bids-adieu-to-thursday-expiry-as-dates-swap-come-into-effect-explained-125082800635_1.html); [ICICI Direct](https://www.icicidirect.com/futures-and-options/articles/stt-changes-in-budget-2026-what-f-o-traders-need-to-know))

त्यामुळे holdout हा फक्त "नवीन data" नाही, तो **नवीन regime** आहे. IS आणि VAL मध्ये NIFTY weekly expiry Thursday होती. Backtest ने प्रत्येक दिवसाचं त्या वेळचं expiry calendar वापरायलाच हवं.

**[अनुमान, पडताळा]** NIFTY weekly options 2019 च्या सुमारास सुरू झाले असं माझं समजणं आहे. तसं असेल तर IS चा 2015–2018 चा भाग weekly-options backtest साठी उपलब्ध नसेल. NSE contract history वरून हे तपासा. मग त्या काळासाठी फक्त spot-structure चाचण्या (P3, P7, P9) घ्या, options P&L नाही.

Split सीमांवर किमान एका weekly expiry चं embargo ठेवा.

### Baselines (प्रत्येक EW नियम यांच्याशी तुलना) **[अनुमान]**

1. **Random entry:** random वेळ, तीच दिशा, तोच delta, width आणि DTE.
2. **"कोणताही pullback":** साधा trend filter + 1-leg pullback + तीच candle.
3. **Same-delta strike:** EW inv दुर्लक्षित.
4. **Random-ratio sets:** U[0.2, 0.9] मधून, 10,000 वेळा.
5. **Shifted-Fib:** F + ε.
6. **Stationary block bootstrap price paths:** 2,000 reps, block 10–40, Batchelor & Ramyar शैलीत ([City Univ.](https://openaccess.city.ac.uk/id/eprint/16276/1/magic%20numbers%20in%20the%20dow.pdf)).
7. **Randomized dates:** time features साठी.

### Overfitting नियंत्रण

Sullivan, Timmermann & White यांनी 7,846 rule variants तपासले. In-sample सर्वोत्तम rule p < 0.002 होता, पण out-of-sample मध्ये White's Reality Check p **0.341** आला ([STW](https://www.kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf)) **[पुरावा]**. म्हणून चार गोष्टी अनिवार्य:

1. सर्व trials (अपयशी सुद्धा) pre-registered grid मध्ये नोंदवा.
2. White's Reality Check किंवा Hansen SPA चालवा.
3. Deflated Sharpe ([Bailey & López de Prado](https://www.researchgate.net/publication/324663771_The_Deflated_Sharpe_Ratio_Correcting_for_Selection_Bias_Backtest_Overfitting_and_Non-Normality)).
4. **PBO via CSCV, S = 16** ([Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)). आपला कडक निकष: **PBO > 0.05 ⇒ reject**.

त्याशिवाय parameter plateau तपासा, आणि buckets साठी Benjamini–Hochberg FDR वापरा.

### Reporting: setup-wise आणि degree-wise अनिवार्य

प्रत्येक निकाल **setup (S1–S14) × degree (D0–D3) × tier (A/B/C) × DTE (1–5)** grid मध्ये नोंदवा. प्रत्येक cell साठी हे metrics:

- n
- Costs नंतरची expectancy (₹ आणि max-loss च्या %)
- Short-strike breach rate
- Max-loss trades चा दर
- CVaR 5%
- Hard-inv exits चा दर
- Soft-stop re-entry चा परिणाम

n < 30 असलेल्या cells वर निष्कर्ष नाही. Edge एका degree वर दिसला आणि शेजारच्या threshold वर उलटला, तर तो edge नाही. Win rate > 60% **आणि** Sharpe > 2 आला, तर आधी bug शोधा. NIFTY आणि SENSEX वेगळे नोंदवा. SENSEX हा out-of-sample replication आहे.

**Live forward-test.** Holdout पास झाल्यावर किमान 3–6 महिने paper किंवा अगदी लहान size वर चालवा. प्रत्येक entry चा count, inv आणि settings_hash timestamp करा, आणि ते नंतर कधीच edit करू नका.

---

## Conclusion: पुराव्याबद्दल प्रामाणिक तात्पर्य

या दुरुस्त्यांमुळे spec **जास्त trades** घेतो: counter-trend C waves, 1 DTE, आणि प्रत्येक degree वरचे nested entries. पण त्याच वेळी तो **जास्त कठोरपणे मरतो**. प्रत्येक trade त्याच्या स्वतःच्या degree च्या नियम-स्तराला बांधलेला असतो, close-basis वर बाहेर पडतो, आणि hard invalidation नंतर परत येत नाही. हा खरा बदल आहे. आधीचा HTF gate जोखीम कमी करत नव्हता. तो एका प्रकारच्या जोखमीला (counter-trend) दुसऱ्या प्रकारच्या जोखमीने (संधी गमावणं आणि नमुना लहान होणं) बदलत होता. आता ती जोखीम size आणि bounded targets ने मोजली जाते. ती मोजता येते, म्हणून तपासताही येते. 5–6 Oct चं उदाहरण spec सुसंगत असल्याचं दाखवतं. पण n = 2 हा पुरावा नाही.

पुराव्याचं चित्र बदललेलं नाही. Fibonacci price आणि time ratios योगायोगाइतकेच आहेत, candlesticks एकट्याने कमकुवत आहेत, आणि कोणत्याही Elliott setup चा (wave 3, C, किंवा triangle thrust) स्वतंत्र, out-of-sample, costs नंतरचा win-rate प्रकाशित झालेला नाही. Vendors सुद्धा तो देत नाहीत. Elliott मधले objective भाग, म्हणजे नियम-आधारित invalidation आणि "पहिला leg हा correction चा शेवट नाही", हेच सर्वात tradable आहेत. आणि नेमकं त्यांचंच मूल्य जगात कोणीही मोजलेलं नाही. त्यामुळे तुमचा backtest हा कुणाच्यातरी दाव्याची पुनरावृत्ती नाही, ती पहिली चाचणी आहे. P3, P4, P5 आणि P6 हे चार नियम baselines (1)–(3) विरुद्ध, PBO ≤ 0.05 सह, setup-wise आणि degree-wise पास झाले नाहीत, तर Fibonacci, alternation किंवा Hurst जोडून ते पास करवणं म्हणजे Aronson ने वर्णन केलेली "story" ठरेल ([Wikipedia: Elliott wave principle](https://en.wikipedia.org/wiki/Elliott_wave_principle)). ते पास झाले, तर तुमच्याकडे असं काहीतरी असेल जे Prechter पासून आजच्या AI papers पर्यंत कोणीही दाखवलेलं नाही.

---

## स्वतंत्र तपासणी: दुरुस्त्यांची नोंद

ही तपासणी मूळ लेखकाने केलेली नाही. प्रत्येक दुरुस्ती research notes विरुद्ध (`Elliott Wave trading setups सुधारित/`, `Elliott Wave सिद्धांत संपूर्ण अभ्यास/`, `Leg and level strength research/elliott_wave.md`) आणि trader च्या सहा न बदलणाऱ्या नियमांविरुद्ध तपासली आहे. वैध मजकूर काढलेला नाही. फक्त चुकीचे लेबल, नियमविरोधी defaults आणि अस्पष्ट पायऱ्या बदलल्या आहेत.

### A. Elliott नियमांची अचूकता

| # | कुठे | काय बदललं | का |
|---|---|---|---|
| A1 | विभाग 2, R6 | "C हा A च्या टोकापलीकडे जातो" हा भाग [नियम] वरून **[मार्गदर्शक, मजबूत]** केला. "B < A origin" [नियम] राहिला | Notes मध्ये फक्त Outline चे वर्णनात्मक शब्द "C moves well beyond A's extreme" आहेत. Truncated C शक्य आहे. Hard inv फक्त B भागावर टिकतो |
| A2 | विभाग 2, R9 | Diagonal wave 4 overlap: EWP नुसार "almost always" ⇒ [मार्गदर्शक]. "W4 ≤ W2 end" ला EWI चा नियम ("no reactionary subwave fully retraces…") जोडला. Ending diagonal C म्हणून "rarely". Leading diagonal subdivision अनिर्णित; Neely नाकारतो | `core_theory…md` §1: EWI Diagonals "almost always overlaps"; EWGold च तो नियम मानतो |
| A3 | विभाग 2, R8 | Barrier triangle tolerance आणि expanding triangle (E > C) अपवाद जोडले | EWGold: barrier हा "the only Elliott wave rule that's not absolute"; Outline: expanding मध्ये E हा C पलीकडे |
| A4 | विभाग 2, R4 | नियम 5-wave पहिल्या हालचालीपुरता; 3-wave A ban हा label-परिणाम, असं स्पष्ट केलं | Outline चे शब्द "initial **5-wave** move" |
| A5 | विभाग 3, time table | Triangle t(e) ≤ t(b)+t(c)+t(d) [नियम] वरून **[मार्गदर्शक/विरोधाभास]** केला | QOW 3518 त्याच पानावर "last leg of a Triangle or Terminal will 'Push' beyond the ideal time targets" असा अपवाद देतो (`time_cycles…md` ओळ 19) |
| A6 | दुरुस्ती 3, `c_time_violation`, time table | t(c) ≤ t(a)+t(b) ला Terminal (ending diagonal C) सूट जोडली. t(·) ची bar-व्याख्या दिली. Neely चे time नियम author-asserted, "normally", न तपासलेले असं नोंदवलं | तोच QOW 3518 अपवाद; QOW 3782 चा शब्द "normally" |
| A7 | विभाग 3, Stage 1 | स्रोत QOW 22 जोडला ("mandatory"); Stage 1 फक्त पूर्ण 5-wave impulse नंतर, entry trigger नाही | `neowave…md` Q2 |
| A8 | विभाग 4, vote | "two or more valid interpretations usually exist" [नियम/तत्त्व] ⇒ **[मार्गदर्शक/तत्त्व]** | हे निरीक्षण आहे, pass/fail नियम नाही |
| A9 | शीर्ष सारांश, S8 | "प्रत्येक setup चा stop नियमाला बांधलेला" ⇒ "बहुतेक"; S8 चा "W origin" inv [अनुमान] केला | X बद्दल असा नियम notes मध्ये नाही. S6b चा inv आधीच [अनुमान] होता |
| A10 | शीर्षक, विभाग 2 | "पाच अटळ नियम" ⇒ "अटळ नियम (R1–R11)" | Table मध्ये 11 नोंदी आहेत. EWP चे impulse नियम 3 आहेत |

तपासून बरोबर आढळलेले (बदल नाही): R1, R2, R3 (cash), R5, R7 (flat B ≥ 90% "This is a rule"), R10, R11, fractal 5/3, Similarity & Balance 1/3 price OR time, t(w2)>t(w1) OR t(w4)>t(w3).

### B. Trader च्या नियमांचं पालन

| # | कुठे | काय बदललं | का (कोणता नियम) |
|---|---|---|---|
| B1 | विभाग 6 T2, settings | `reclaim_ref` पर्याय `prev_bar_high` आणि `last_subwave_iv_extreme` काढले (आता touched_level / zone_high) | नियम 2: close > आधीचा bar high हा stop-entry; sub-wave (iv)/2-4 break हा Stage-1 break. दस्तऐवजाच्या स्वतःच्या दुरुस्ती 4 शी सुद्धा विसंगत होते |
| B2 | विभाग 6 T7, विभाग 12 test 8 | No-breakout guard (close < शेवटच्या sub-leg चा origin) आणि breakout-ban CI test जोडली | नियम 2 चं यांत्रिक assert |
| B3 | विभाग 6, 5, settings | Trigger candle TF "signal TF 5m" ऐवजी `trigger_tf_mode = level_tf` (degree_tf) | नियम 3: candle timeframe = level/chart timeframe by default |
| B4 | विभाग 7, 9, 12, settings | `inv_confirm_bars = 1` (एका close वर exit) काढला. **Real break** = close L − buf पलीकडे + `break_no_reclaim_bars` (1) bars reclaim नाही, `break_confirm_tf`. False-break मध्ये "एकच close मग reclaim" जोडलं | नियम 6: "wick or single close beyond, then reclaim" exit trigger करू नये. जुना default नेमका एका close वर exit करत होता |
| B5 | विभाग 9 क्रम 2, settings | Premium stop default intrabar ⇒ `hard_stop_eval = bar_close` (intrabar पर्याय) | Intrabar 2× stop wick वर exit करू शकतो, म्हणजे false-break वर exit (नियम 6). Spread defined-risk आहे |
| B6 | विभाग 7 | `count_inv_basis` setting; count engine आणि trade exit एकाच basis वर | Count wick ने मेला पण trade चालू, ही विसंगती टाळणे |
| B7 | विभाग 9, 12, settings | "Exits कधीच block होत नाहीत" स्पष्ट नियम + CI test; `trading_mode = paper` default, `live_approved` (फक्त trader बदलतो) | नियम 5: LIVE फक्त explicit approval; exits never blocked. आधी mode setting च नव्हती |
| B8 | विभाग 8, settings | `underlying` setting: NIFTY default, SENSEX पर्यायी, BANKNIFTY weekly mode मध्ये निषिद्ध | नियम 1 |
| B9 | विभाग 8 | Expiry fill तारखेवरून काढायची | Signal आणि fill वेगवेगळ्या दिवशी पडले तर expiry नियम चुकू नये (नियम 4) |

तपासून बरोबर आढळलेले: HTF gate default false (नियम B), min_dte काढलेला आणि `min_dte_override` default off, 1 DTE allowed, `try_next_weekly` default off, सगळे Kennedy/MTP break-triggers निषिद्ध, S11/S12 pullback-पर्याय.

### C. अंतर्गत सुसंगती आणि गणित

| # | कुठे | काय बदललं | का |
|---|---|---|---|
| C1 | विभाग 8, 10 | DTE ची नेमकी व्याख्या: `dte_days` (Mon→Tue = 1; c_min table साठी) आणि `dte_frac` (session_fraction, 375 मिनिटं). जुनं नाव "calendar_fraction" पण वर्णन "trading days", हा विरोध काढला | Example मध्ये intraday fraction default असूनही DTE = 1.0 वापरलं होतं |
| C2 | विभाग 10, S13 strike | dte_frac ≈ 1.31 ⇒ dist_vol ≈ 211 ⇒ short **22,250 PE** / long 22,150 PE (आधी 22,300/22,200). DTE = 1.0 घेतल्यास 22,300 हे नोंदवलं. 6 Oct ओळ "22,560 > 22,396 > 22,250 > 22,150" | Default dte_mode नुसार हिशोब. S6a चा strike (22,150) दोन्ही प्रकारे तोच (dist_vol ≈ 223 वि. dist_inv 218) |
| C3 | विभाग 10, S13 | Alternate same-direction count (B अजून चालू) alt_weight_min पेक्षा कमी असल्याचं गृहीत स्पष्ट केलं; नसेल तर inv 22,217 ⇒ short 22,150 | विभाग 4/8 चा "सगळ्यात दूरचा inv" नियम example मध्ये लावला नव्हता |
| C4 | विभाग 5 S6a/S13, विभाग 9 क्रम 4, settings | "C zone चा पहिला स्तर" अस्पष्ट होता (0.618A = 22,646 की 1.0A = 22,800?). आता `tierB_target_mult` = 1.0 (B end पासून) | Example मध्ये C ने 22,646 ओलांडलं तरी "target गाठला नाही" म्हटलं होतं; 0.618A हा पहिला स्तर मानला असता तर spec ने तेव्हाच exit केला असता |
| C5 | विभाग 10, 6 Oct ओळ | "दोन्ही OTM expire" ⇒ OTM राहिले, पण Tier B `tp_pct_credit` 50% ने बहुधा expiry आधीच बंद | Spec च्या स्वतःच्या exit क्रम 5 शी विसंगत होते |
| C6 | विभाग 10, A-end ओळ | Rejection चं कारण फक्त R4; "C > A end" हे मार्गदर्शक आणि निकाल-निरीक्षण | A1 चा परिणाम |
| C7 | विभाग 10, Zone 1 | dist_inv ≈ 425 (आधी "~400"); dist_vol entry दिवसानुसार ≈ 396 (dte_frac 4.5) ते ≈ 438 (5.5) (आधी "5 DTE ~415"); D+2 ABC असेल तर setup नाही असं नेमकं केलं; Tier A ची अट | गणित आणि "inv अधिक कमकुवत" ही अस्पष्टता |
| C8 | विभाग 10 | B = 225/404 = 55.7% (56% बरोबर); A चं 5-wave status screenshot-गृहीत [अनुमान] | Candles ≠ waves |

तपासलेले आणि बरोबर: A = 404; 0.5–0.618 × A zone = 22,419–22,371; S6a dist_inv 218; 1-SD 183/410; C = 1.0A = 22,800; 0.618A = 22,646; 1.618A ≈ 23,050; 6 Oct expiry = Tuesday, current weekly; 13 Oct पुढची weekly; दोन्ही trades Tier B 0.5×, max_open_spreads 2 मध्ये बसतात; S6a inv 22,217 (D) वि. S13 inv 22,396 (D−1) degree-सुसंगत.

### D. Settings

नवीन settings: `trading_mode`, `live_approved`, `underlying`, `contract_master_source`, `structure_tf` (आधी `signal_tf`), `degree_tf`, `trigger_tf_mode`, `trigger_tf_fixed`, `count_inv_basis`, `zigzag_b_band`, `flat_b_max_ratio`, `barrier_d_tol_atr`, `touch_reclaim_window`, `rsi_len`, `strike_step`, `break_buffer_pts`/`_atr`, `break_no_reclaim_bars`, `break_confirm_tf`, `hard_stop_eval`, `tierA_target_fibs`, `tierB_target_mult`, `target_tol_atr`, `wf_train_years`/`wf_test_months`, `split_embargo_expiries`, `pbo_max`, `min_cell_n`. काढलेले: `inv_confirm_bars`, C3 मधला `override_c_time` (table मध्ये नव्हता; आता `c_time_rule`). `dte_mode` चे पर्याय `session_fraction`/`whole_days`. Strike grid (50) आणि lot (65) code मधून काढून contract master वर. विभाग 11 च्या सुरुवातीला कोणते defaults स्रोत-आधारित आहेत ते नोंदवलं; बाकी सगळे "calibration आवश्यक".

### E. पुरावा-दावे

| # | कुठे | बदल | का |
|---|---|---|---|
| E1 | विभाग 3, automation | "65–83%" ⇒ "≈64–88%" आणि प्रत्येक अभ्यासाचे आकडे | Notes: Vantuch 68.1/71.1/70.1%, Kotyrba 67.8%, ElliottAgents 73–88% (पूर्ण) / 67–73% (अपूर्ण) |
| E2 | विभाग 3, Batchelor & Ramyar | "430 phases" ⇒ "430 turning points" | Notes चा शब्द |

तपासलेले आणि बरोबर: 144 पैकी 15 वि. 14.4; Tsinaslanidis (Leg notes मध्ये पडताळलेले; "सिद्धांत" notes मध्ये page blocked होतं); Osler; Marshall–Young–Rose; Lu–Shiu–Liu; STW p 0.341; PBO 0.05; Hulbert [दावा, पडताळणी आवश्यक]; CXO 21%; Swannell [दावा]; India facts (Tuesday/Thursday, BANKNIFTY monthly, lot 65, STT 0.15%, +2% ELM, algo framework). Pirated links नाहीत: EW-Basics (marscapitalpartners) ही EWI ची free ebook copy, आणि Kennedy चा Wiley publisher sample आहे.

### F. अंमलबजावणीयोग्यता

- विभाग 6: `touched_level`, lower_wick, median (चालू bar वगळून), `bars_to_reclaim`, `bars_last_subleg`, `div_ok` यांच्या नेमक्या व्याख्या; touch/reclaim एकाच candle वर की window मध्ये; C4 causality (पूर्ण legs चे pivots confirmed, फक्त शेवटचा leg tentative).
- विभाग 9: Tier A "exit_50pct_trail_rest" आणि time-exit (progress) चा संदर्भ-स्तर नेमका केला.
- विभाग 12: pivot confirmation बंद bars वरून; live gate; exit step स्वतंत्र; false-break, breakout-ban, exit-never-blocked CI tests.

### Trader साठी उघडे प्रश्न (प्रश्न 1–6 ची उत्तरं: विभाग 14; खालची यादी फक्त इतिहासासाठी)

1. **Premium stop:** `hard_stop_eval` default bar close ठेवला आहे (false-break नियमाशी सुसंगत). 1 DTE वर intrabar 2× stop हवा का? तो wick वर exit करू शकतो.
2. **Real break चे आकडे:** `break_no_reclaim_bars` = 1 आणि buffer max(10 pts, 0.10 × ATR) हे [अनुमान] आहेत. तुमचा प्रत्यक्ष n आणि buffer काय?
3. **Touch–reclaim:** एकाच candle वर (default) की 2–3 candles च्या window मध्ये?
4. **Degree ↔ timeframe map:** D0–D3 साठी कोणते chart TF (उदा. D2 = 15m)? याच TF वर reversal candle घ्यायचा.
5. **Tier B target:** C = 1.0 × A वर पूर्ण exit (default) बरोबर, की 0.618 × A वर?
6. **T1:** Wick hard_inv च्या पलीकडे गेला पण close आत आला, तर entry ला परवानगी द्यायची का? सध्या नाही (conservative).
7. **Worked example data:** Screenshot-आधारित किमती (±10–15) आणि "crash चा उगम 23,027" वि. घसरणीची सुरुवात 23,190, यांची प्रत्यक्ष 5m data वरून खात्री करा. Golden-file test त्यावर अवलंबून आहे.
8. **SENSEX:** strike interval, freeze qty आणि lot-बदलाची तारीख primary स्रोताने पडताळलेली नाहीत; contract master वरूनच घ्या.

---

## 14. अंतिम निर्णय: Abhi च्या "logical trading" नुसार उघड्या प्रश्नांची उत्तरं

> **हा विभाग वरच्या सगळ्या defaults वर प्राधान्य घेतो.**
> **मूळ तत्त्व:** कुठलाही निर्णय ठराविक points, ठराविक candles किंवा ठराविक Fibonacci ratio वर नाही. तो बाजाराच्या स्वतःच्या noise (median range), ताकद (displacement) आणि buyers/sellers च्या वर्तनावर (reclaim, acceptance, rejection) ठरतो. Entry साठी वापरलेलं logic exit साठीही तसंच, फक्त उलट दिशेने, वापरायचं.

### Q1. खरा break: किती candles, किती buffer?
**उत्तर:** आकडा नाही, logic.
- **Buffer = 0.25 × median range** (त्या TF वरचा). बाजार शांत असेल तर buffer लहान, आणि वेगवान असेल तर मोठा.
- **तीन पैकी कुठलाही एक पुरावा मिळाला की break खरा मानायचा:**
  - **(a) Displacement:** breaking candle स्वतःच ताकदीची असेल (range ≥ 1.2 × median आणि close टोकाला), तर तिथेच खरा break. ताकदवान candle म्हणजे विरुद्ध बाजू खरंच आली आहे.
  - **(b) Acceptance:** कमकुवत candle पलीकडे गेली, तर पुढची candle सुद्धा पलीकडेच close व्हायला हवी (reclaim नाही). म्हणजे भाव तिथे "स्वीकारला" गेला.
  - **(c) Failed retest:** break नंतर भाव level कडे परत आला आणि उलट बाजूने logical reversal मिळाला. म्हणजे level ची भूमिका बदलली (role reversal).
- **बाकी सगळं false break:** wick, किंवा कमकुवत close होऊन लगेच reclaim. त्यावर exit नाही.
- **Timeframe = level चा TF** (तुमचा नियम: candle TF = chart TF).

### Q2. Touch आणि reclaim एकाच candle वर की 2–3 candles मध्ये?
**उत्तर:** 1 ते 3 candles चा **composite rejection candle.** हेच logic MCX bot मध्ये (#241) आधीच मंजूर झालं आहे.
- खरा rejection कधी एका candle मध्ये होतो (hammer), कधी दोन (engulfing), तर कधी तीन (morning star) candles मध्ये. Logic सगळ्यांचं एकच: खाली ढकललं गेलं, आणि buyers ने परत ताबा घेतला.
- शेवटच्या 1–3 बंद candles एकत्र करायच्या: पहिल्याचा open, सगळ्यांचा max high, min low, आणि शेवटच्याचा close.
- Touch, reclaim, strength आणि score composite वर मोजायचे. N ≥ 2 असेल तर शेवटची candle trade दिशेने close व्हायला हवी.
- Close range च्या मध्यावर (0.40–0.60) असेल तर तो अनिर्णय आहे. पुढच्या follow-through candle ची वाट पाहायची (कमाल 4).
- Composite सुद्धा correction च्या शेवटच्या sub-leg च्या सुरुवातीच्या पलीकडे close होता कामा नये (T7). म्हणजे composite मुळे breakout entry होत नाही.

### Q3. कुठल्या degree साठी कुठला timeframe?
**उत्तर:** Degree घड्याळावरून ठरत नाही, रचनेवरून ठरते. म्हणून TF आपोआप निवडायचा.
- ज्या corrective wave (pullback) च्या शेवटी entry घ्यायची आहे, ती wave **8 ते 40 बंद candles** मध्ये दिसेल असा सर्वात लहान TF निवडायचा: 5m, 15m, 30m, 1H किंवा 1D.
- 8 पेक्षा कमी candles असतील तर wave ची आतली रचना दिसत नाही. 40 पेक्षा जास्त असतील तर noise वाढतो. Neely सुद्धा सांगतो की खूप swings दिसत असतील तर मोठा chart घ्या.
- 8 आणि 40 हे सुरुवातीचे आकडे आहेत; backtest मध्ये calibrate करायचे.
- **Reversal candle, real break आणि exit, सगळं याच TF वर.**
- **5 Oct उदाहरण:** B leg ~10 candles 15m वर, म्हणजे B-end entry 15m वर. C च्या आतला (ii) लहान होता, म्हणजे तो 5m वर.

### Q4. C-wave trade चा exit: C = 1.0 × A की 0.618 × A?
**उत्तर:** कुठलाच ठराविक ratio नाही. Fibonacci ratios ची भाकीत-शक्ती पुराव्यात सिद्ध झालेली नाही.
- C चा zone (0.618 / 1.0 / 1.618 × A) फक्त **कुठे लक्ष ठेवायचं** हे सांगतो.
- **Exit तेव्हाच** जेव्हा C त्या zone मध्ये, किंवा विरुद्ध major level वर, पोचून **उलट दिशेचा logical reversal** देतो. म्हणजे C संपल्याचा पुरावा: तोच signal ज्यावर पुढचा उलट trade (उदा. bear call) सुरू होतो.
- C ने zone किंवा level ताकदीने ओलांडून टिकवला (real break), तर तो फक्त C नसेल; मोठा trend आपल्या बाजूने बदलत असेल. मग hold करायचं, आणि संरक्षणासाठी C च्या आतल्या शेवटच्या confirmed sub-wave चा तळ वापरायचा.
- Profit % (credit चा 50–65%) आणि expiry हे बाकी exits तसेच राहतात.
- **5 Oct उदाहरण:** C 22,731 पर्यंत गेला, पण zone (22,780–22,805) मध्ये reversal आला नाही. त्यामुळे C-आधारित exit नाही, आणि spread 6 Oct च्या expiry ला OTM राहून पूर्ण credit मिळालं असतं. Profit-% नियम आधी लागला असता तर तो आधीच फायद्यात बंद झाला असता.

### Q5. 1 DTE वर 2 × credit stop: candle च्या आत की close वर?
**उत्तर:** दोन थर.
- **Option premium वरचा 2 × credit stop: candle close वर.** 1 DTE ला premium मध्ये gamma आणि bid-ask रुंदावण्यामुळे खोटे wicks येतात. त्यावर exit म्हणजे false break वर exit, आणि ते तुमच्या नियमाविरुद्ध आहे.
- **खरा धोका underlying वरून पकडायचा:**
  - Invalidation चा real break (Q1). Displacement candle असेल तर तो त्याच candle च्या close वर पकडला जातो.
  - **Emergency:** spot ने **short strike स्वतः** candle च्या आत ओलांडला, तर लगेच exit. Close ची वाट नाही. Short strike आधीच invalidation च्या पलीकडे ठेवलेला असतो, म्हणजे strike पर्यंत भाव आला तेव्हा structure आधीच तुटलेलं असतं. हा wick नाही, हा खरा धोका आहे.

### Q6. Wick invalidation च्या पलीकडे गेली पण close आत आला: entry चालेल का?
**उत्तर:** पूर्वीच्या count वर entry नाही. पण count बदलून entry शक्य आहे.
- Zigzag मध्ये B ने A ची सुरुवात (wick ने) ओलांडली, तर zigzag चा नियम मोडला. पण flat मध्ये B ला A च्या सुरुवातीपलीकडे जायची परवानगी आहे (expanded flat).
- त्यामुळे count engine ने **expanded flat** चा count तपासायचा:
  - तो valid असेल आणि reversal candle मिळाली, तर entry.
  - **नवीन invalidation = त्या wick चं टोक − buffer.** Strike त्याच्या पलीकडे.
  - Expanded flat मध्ये C मोठा (~1.618 × A) असतो, म्हणजे trade च्या बाजूने.
- दुसरा कुठलाच valid count नसेल, तर entry नाही.
- Settings: `wick_beyond_inv_action = recount` (default) / `skip`.

### नवीन/बदललेल्या settings चा सारांश
`break_buffer_mr` 0.25 · `break_displacement_confirm` true · `break_close_loc` 0.30 · `break_no_reclaim_bars` 1 · `break_retest_confirm` true · `touch_reclaim_window` 3 (composite) · `degree_tf_mode` auto_by_bars · `tf_bars_min`/`tf_bars_max` 8/40 · `tierB_exit_mode` opposite_reversal · `hard_stop_eval` bar_close · `emergency_spot_cross_short` true · `wick_beyond_inv_action` recount. **काढले:** `break_buffer_pts`/`break_buffer_atr` (fixed points).

**Tests (CI मध्ये जोडायचे):**
- Displacement break त्याच candle वर exit देतो.
- कमकुवत close + reclaim ⇒ exit नाही.
- Failed retest ⇒ exit.
- Composite entry कधीच T7 च्या पलीकडे नाही.
- Auto-TF निवड फक्त बंद candles वरून, no-repaint.
- Short strike intrabar cross ⇒ लगेच exit.
- Wick-beyond-inv ⇒ expanded flat recount; नवीन invalidation = wick टोक.
