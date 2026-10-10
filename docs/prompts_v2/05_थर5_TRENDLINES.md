# थर 5: Trendlines (v2.1, 2026-10-09; चार reviews नंतर दुरुस्त)

> Master लागू. **थर 4 ला ✔ झाल्यावरच.** **v2.1 व्याप्ती:** primary + latest + fan + K आधार/टोक रेघा + break/flip + trade-योग्य वर्ग + quality descriptors. **v2.2 (Abhi च्या ✔ नंतर; या spec मध्ये फक्त stub):** channel / speed रेघा, internal twins, Brooks trend-channel line.
>
> ## का
> Abhi: (1) trend ची रेघ (lower highs / higher lows) = तिरका seller / buyer area ("trend line perfect resistance", "trendline + seller zone"); (2) correction ची स्वतःची रेघ: "wedge पूर्ण न होता trendline breakout + commitment candle ⇒ entry"; फक्त रेघ तुटणं = noise.
> Audit: touch फक्त pivot वर (±0.2 MR), wick नाही (Abhi ची रेघ 8 pts वर "दिसली नाही"); 200 bars; प्रत्येक बाजूला एक रेघ; 1H नाही; vision charts वर रेघ नाही.
>
> **संशोधनाचे धडे (`research_notes/trendline_rules_reference.md`; Sperandeo, DeMark, Murphy, Bulkowski 6,400 trendlines, Brooks, LuxAlgo):**
> 1. **कोणते points:** correction ची टोकं (reaction highs / lows), impulse-आतले नाहीत. दोन deterministic रेघा: **Primary (Sperandeo)** = trend extreme → latest extreme च्या आधीचं correction-टोक, किंमत न कापता; **Latest (DeMark)** = दोन सगळ्यात अलीकडची same-level correction-टोकं. बाकी fan.
> 2. **गुणवत्ता (Bulkowski):** सपाट > तीव्र; touches मध्ये जास्त अंतर; लांब; inbound trend सपाट. **फक्त 3ऱ्या touch वर trade = win/loss 37%** ⇒ रेघ पुरावा, gate नाही.
> 3. **Break = पहिला close पलीकडे; throwback 59%** ⇒ पहिला break = नोंद. DeMark qualifiers + Sperandeo 1-2-3 = commitment चे ingredients (थर 7).
> 4. Touch wick ने, **भेटीनुसार** (prototype: 6 Oct ला भाव अनेक candles रेघेला चिकटून = एक touch; 7 Oct 12:00 तिसरा touch 2 pts आत, close 41 pts खाली).

---

## 0. आधार
### 0.1 स्रोत
`research_notes/trendline_rules_reference.md` (Sperandeo, DeMark, Murphy, Bulkowski, Brooks, LuxAlgo); `advanced_analysis_tools.md` §4. Abhi: रेघ wicks ला; correction रेघेचा break + commitment candle ⇒ entry; फक्त break = noise.

### 0.2 मूलतत्त्वं
1. **एकच pivot पाया** (थर 1). रेघेचे anchors फक्त confirmed pivots, त्यांच्या `known_at` पासून.
2. **Touch = wick ने रेघेला स्पर्श, close पलीकडे नाही.** फक्त pivot वरचा touch नाही. एक भेट = एक touch.
3. **Real break ची व्याख्या एकच:** `elliott/breaks.py::first_real_break` detrended frame वर (§3). K-रेघेची "break घटना" = Master पातळी-1 (पहिला plain close), वेगळी.
4. **रेघ = पुरावा / area, gate नाही.** Correction रेघेचा break हा फक्त **घटना**; त्याचा अर्थ (entry की noise) थर 7 commitment candle वरून ठरवतो.
5. **एका केससाठी नियम नाही.**

## 1. Input (प्रत्येक बंद candle ला, फक्त decision bar पर्यंत)
- **थर 1:** D0–D2 pivots (`known_at` सह), प्रत्येक degree चा trend, σ (session साठी गोठलेला).
- **थर 2:** I, K, legs.
- **थर 3:** preferred / alternate pattern (labels, pivots).
- **थर 4:** zones (पट्टे, भूमिका, अवस्था).
- **15M spot OHLC.** 1H साठी 15M पासून aggregate.

## 2. रेघा शोधणं
### 2.1 एकक आणि वेळ-अक्ष
- **सगळी गणना 15M bars वर**, थर 1 च्या masked series वर (`cas_mask` candle वगळलेली). Bar index = त्या series मधला क्रमांक (trading bars; session gaps मोजत नाही).
- **1H दृश्य** म्हणजे फक्त कोणत्या degrees (D2 / D3) च्या रेघा आणि कसं काढायचं. 1H bars वर गणना नाही, म्हणून अपूर्ण 1H candle कधीच वापरली जात नाही.
- **Linear किंमत.**
- **रेघेचा σ = तिच्या जन्माचा σ** (जन्म = max(A2 `known_at`, A1/A2 `top_known_at`) चा session σ), गोठलेला. τ, slope, वैधता आणि held (θ_D0 = k₀ × हा σ) या σ ने.

### 2.2 कोणते swings जोडायचे (सगळ्यात महत्त्वाचं; Abhi च्या तपासणीनंतर)
| दृश्य | origin degree | correction-टोक degree |
|---|---|---|
| 15M | D2 (reversal ज्या D2 pivot पासून) | D1 |
| 1H | D3 | D2 |

**सगळ्या जोड्या जोडायच्या नाहीत.** Trend रेघ फक्त **correction ची टोकं** जोडते (Murphy: "uptrend line along successive reaction lows"; LuxAlgo: "lower swing highs for a down trendline … prominent pivots beat minor wiggles").

**Downtrend (seller बाजू; uptrend साठी आरसा-रूप):**
- **Trend origin:** ज्या D2 (1H दृश्यासाठी D3) H pivot पासून थर 1 ची दोन-पायरी reversal DOWN सुरू झाली तो; `origin_known_at` = reversal पूर्ण झाल्याचा `known_at`. (Frame लांबीवर अवलंबून नाही; id त्यावर.) D1 दृश्यासाठी तेच D1 वर.
- **Correction-टोक (structural top):** त्या degree चा H pivot P, ज्यानंतर भाव P वर जाण्याआधी P च्या आधीच्या same-degree low खाली **close** झाला (थर 1 plain-close BOS_down; wick = sweep, top नाही). `top_known_at` = त्या close candle चा बंद. Degree-निहाय (1H रेघांसाठी D2 tops).
- **Provisional टोक:** शेवटचा D1 H pivot जो अजून ओलांडला नाही. **फक्त रेघ काढण्यासाठी** (DeMark latest चं चित्र); §2.7 / §5 (trade-योग्य / K area) साठी **कधीच नाही** (K च्या A-high वर anchor = स्वतःला पुरावा).
- **जोडणी:** A1 = origin किंवा correction-टोक; A2 = नंतरचं, A1 पेक्षा खालचं correction-टोक किंवा provisional टोक.
- **दोन नावाच्या रेघा नेहमी काढायच्या आणि तशा लेबल करायच्या** (संशोधन §1):
  - **Primary (Sperandeo):** A1 = trend origin; A2 = trend च्या सध्याच्या सगळ्यात खालच्या low च्या आधीचं शेवटचं correction-टोक. रेघ A1–A2 किंमत कापत असेल (§2.3.1) तर A2 = **त्याच्या आधीचं (A1 कडचं)** correction-टोक जे रेघ कापत नाही (सगळ्यात सपाट स्वच्छ रेघ), जोपर्यंत स्वच्छ होत नाही. नवा low ⇒ primary पुन्हा (नवी id).
    - Origin पासून कोणतीच रेघ स्वच्छ नसेल (origin नंतर लगेच उंच correction, जी रेघ कापते) ⇒ A1 = पुढचं correction-टोक, `origin_shifted` खूण. Prototype: महिन्याच्या data वर सगळ्यात उंच टोकावरून एकही रेघ स्वच्छ नव्हती; पुढच्या correction-टोकावरून primary स्वच्छ आली आणि ती सध्याच्या भावाला test करतेय.
  - **Latest (DeMark):** A1, A2 = **दोन सगळ्यात अलीकडची** correction-टोकं (provisional सह). नवं correction-टोक आलं की latest बदलते.
  - बाकी जोड्या = **fan** रेघा (त्याच origin वरून कितवी, ते नोंदवायचं).
- **Internal आवृत्ती:** v2.2 stub (या थरात code नाही).
- **Impulse च्या आतले highs** (उदा. घसरणीदरम्यानचे लहान highs, किंवा correction च्या आतले highs, जसे K चा A) **anchor होत नाहीत.**
- **Id = (A1 bar, A1 प्रकार, A2 bar);** degree = दोन्ही anchors ची समान सगळ्यात मोठी degree.
- **Incremental:** नवं correction-टोक किंवा provisional टोक माहीत झाल्यावरच नव्या जोड्या.
- **रेघ कधीपासून अस्तित्वात (जन्म):** max(A2 `known_at`, A1/A2 `top_known_at`, A1 = origin असेल तर `origin_known_at`). σ याच क्षणाचा.
- **किंमत:** v(t) = A1 + slope × (t − A1 bar).

**Fan principle (Murphy / LuxAlgo):** एकाच origin / टोकावरून निघणाऱ्या रेघा. Steep रेघ तुटली की पुढची सपाट रेघ (पुढच्या correction-टोकावरून) येते.
- प्रत्येक रेघेचा fan क्रमांक नोंदवायचा (त्याच A1 वरून कितवी).
- Fan च्या 3ऱ्या रेघेचा break = trend बदलाचा मजबूत पुरावा (Murphy; थर 7 साठी नोंद).

**पहिला break म्हणजे reversal नाही** (Brooks; LuxAlgo: "a break signals a change in pace, not necessarily a reversal"). Break नंतर बहुतेक वेळा trend च्या टोकाची चाचणी होते. म्हणून break = नोंद, निर्णय नाही.

### 2.3 वैधता (माणूस काढतो तशी रेघ)
1. **A1 ते A2 मध्ये कोणताही close रेघेच्या पलीकडे 0.3 σ पेक्षा जास्त नाही** (H-रेघेसाठी वर, L साठी खाली). Wick पलीकडे चालतो.
2. **|slope| ≤ 0.5 σ प्रति bar** ("अंदाज"; live `tl_max_slope_mr` = 0.5 MR चीच प्रत). ही मर्यादा सैल आहे; ती फक्त उभ्या रेघा काढून टाकते.
3. **A1 आणि A2 मध्ये ≥ 6 bars** (live `tl_min_spacing`).
4. **|slope| < 0.02 σ प्रति bar ⇒ "सपाट".** सपाट रेघ थर 4 च्या आडव्या zone ची प्रत आहे. ती chart वर दाखवायची, पण "K area मध्ये" आणि क्रमात मोजायची नाही (दुहेरी मोजणी नाही).

### 2.4 Touches (भेटीनुसार)
- **Tolerance τ = 0.2 σ** ("अंदाज"; 0.1 / 0.2 / 0.3).
- **भेट:** रेघेच्या ± τ मध्ये टोक आल्यापासून **held (≥ θ_D0 दूर) किंवा break होईपर्यंत** सगळ्या candles = एक भेट (मध्ये थोडं दूर जाऊन परत आलं तरी तीच भेट; दुहेरी मोजणी नाही). एक भेट = एक touch.
- **Close पलीकडे पण buffer आत**, किंवा buffer पलीकडे पण `breaks.py` ने नाकारलेला (reclaim) ⇒ तीच भेट, `false_break` खूण (reclaim candle ला). σ (touch) आणि MR (break) ही दोन वेगळी एककं मुद्दाम ठेवली आहेत: break ची व्याख्या एकाच ठिकाणी राहावी म्हणून.
- **Held:** भेटीनंतर, break न होता, भावाचं टोक आणि रेघेची त्याच candle वरची किंमत यांच्यातलं अंतर ≥ θ_D0 झालं.
  - Decision bar पर्यंत असं झालं नसेल ⇒ "चालू भेट" (मोजायची नाही).
- **Anchors** व्याख्येनेच held touches. A1 / A2 ज्या भेटीत आहेत ती भेट त्याच anchor मध्ये मोजायची, दुसऱ्यांदा नाही.
- **Valid** = ≥ 3 held touches (anchors सह) आणि §2.3. 2 = "उमेदवार" (ruler सारखी; area नाही).

### 2.5 प्रकार
- **Trend रेघ:** §2.2 चे anchors (correction-टोकं / origin).
- **Channel / speed रेघ:** v2.2 stub.
- **सपाट:** §2.3.4.
- **Correction रेघ:** §4.

### 2.6 क्रम, डुप्लिकेट, निवड
- **Key** = (held touches, degree, लांबी (bars), शेवटच्या held touch चा ताजेपणा, −|slope|, A2 bar, A1 bar). निश्चित; अक्षरानुसार नाही.
- **डुप्लिकेट:** key क्रमाने, लोभी पद्धतीने (greedy). आधी निवडलेल्या रेघेशी ≥ 2 held touches समान **आणि** decision bar वरची किंमत ± τ मध्ये ⇒ काढायची. हे top-2 च्या कपातीच्या आधी.
- **निवड:** primary आणि latest नेहमी (cap बाहेर); fan रेघा प्रत्येक बाजूला कमाल 2 valid + 1 उमेदवार.

### 2.7 Trade-योग्य रेघ (decision bar ला; हे chart वर स्पष्ट दाखवायचं)
एक रेघ **"trade-योग्य"** तेव्हाच, जेव्हा सगळं खरं आहे:
1. ती trend रेघ आहे (§2.2 चे anchors), trade बाजूची (I खाली ⇒ correction-टोकांची उतरती रेघ, भावाच्या वर).
2. तुटलेली नाही (या भूमिकेत).
3. दोन anchors (दोन्ही K च्या शेवटच्या leg आधी जन्मलेले, कोणताही K च्या टोकावर नाही) + ही भेट = **किमान 3रा स्पर्श** (Abhi चा trade 3ऱ्या स्पर्शावर); ≥ 3 held आधीच असणं = quality descriptor, अट नाही.
4. K चं चालू टोक रेघेपासून ≤ 1 σ आत आहे, किंवा रेघेला स्पर्श करतं ("K रेघेकडे आलं").
5. Slope trend च्या slope (origin → latest extreme, σ/bar) पेक्षा जास्त तीव्र नाही (Murphy) ⇒ नाहीतर "तीव्र" खूण, trade-योग्य नाही. (I-ratio फक्त descriptor.)

**Chart वर प्रत्येक रेघेचा वर्ग दिसायला हवा:**
- **trade-योग्य** (ठळक लाल / हिरवी);
- **trend रेघ पण आत्ता लागू नाही** (भाव दूर; फिकी);
- **तुटलेली fan रेघ** (राखाडी, ×);
- **K ची स्वतःची रेघ** (§4; निळी तुटक);
- **channel / speed रेघा** (correction-टोकं नसलेल्या: उदा. downtrend मधल्या lows च्या रेघा). या target / संदर्भ आहेत, seller entry साठी नाहीत.
- **नाकारलेल्या** (anchors मध्ये close पलीकडे, तीव्र, impulse-आतले swings): chart वर नाहीत; अहवालात कारणासह गणना.

**गुणवत्तेचे descriptors (Bulkowski; फक्त दाखवण्यासाठी आणि क्रमासाठी, gate नाही):** प्रत्येक trade-योग्य रेघेसोबत:
- slope वर्ग: सपाट / मध्यम / तीव्र (I च्या सरासरी slope च्या तुलनेत: < 0.5× / 0.5–1× / > 1×);
- touches मधलं सरासरी अंतर (bars) आणि रेघेचं आयुष्य (bars);
- inbound trend: A1 च्या आधीच्या 20 bars चा slope (सपाट असेल तर चांगलं);
- held touches ची संख्या, sweep / खोटा-break touches वेगळे.
Chart च्या लेबलमध्ये एक ओळ: उदा. "3 touches · सपाट · अंतर 28 bars · आयुष्य 180 bars".

**एकत्र येणाऱ्या रेघा:** दोन-तीन trade-योग्य रेघा decision bar ला ± τ मध्ये येत असतील ⇒ एक "रेघा-पट्टा" (confluence), आणि थर 4 चा zone तिथे असेल तर ∩ खूण.

**Prototype ची नोंद (code मध्ये नाही):** हाच नियम महिन्याच्या data वर, फक्त त्या वेळेपर्यंतचा data वापरून चालवला.
- Abhi च्या 7 Oct च्या trade च्या candle ला code ने दोन trade-योग्य रेघा दिल्या: origin-टोक ते चालू टोक, आणि दोन correction-टोकं. दोन्ही त्या candle वर एकत्र आल्या होत्या, आणि seller zone सुद्धा तिथेच होता.
- पहिली fan रेघ त्याआधीच तुटलेली दिसली.
- सगळ्यात जुन्या उंच टोकावरून काढलेल्या रेघा "anchors मध्ये close पलीकडे" म्हणून आपोआप नाकारल्या गेल्या.

## 3. रेघेची अवस्था (फक्त decision bar पर्यंत)
- **Break: `breaks.py` चीच व्याख्या, पातळी candle-नुसार.**
  - run-window च्या masked frame वर (holdout नाही; A1 च्या आधीचे window मधले bars सह) OHLC मधून v(t) वजा करायचा ⇒ "रेघ = 0" frame. एका candle मध्ये v स्थिर असल्याने range, MR, displacement आणि close-location बदलत नाहीत.
  - `mr = median_range(मूळ frame, median_range_n)` स्पष्टपणे द्यायचा.
  - `first_real_break(frame', start, 0, side, s, mr=mr, end=decision_bar, retest_fn=None)` थेट call (`s` = `elliott.settings` DEFAULTS ची गोठवलेली प्रत, register मध्ये); truncation test: decision नंतरचे bars काढले तरी confirm index तोच:
    - H-रेघ ⇒ side "above"; L ⇒ "below";
    - start = A2 bar + 1.
  - **`retest_fn` बंद (None):** retest-फंक्शन ज्या frame वर बनलं त्याच्याच किमती वाचतं. परिणाम: रेघेचा (c) failed-retest confirm मार्ग नाही ⇒ रेघ zone पेक्षा उशिरा confirm होऊ शकते (नोंद). `_beyond` import नाही; wrapper मध्ये पुन्हा लिहून `breaks._beyond` शी equality test.
  - **`BreakCache` वापरायचा नाही:** त्याची key पातळीवर आहे, आणि इथे प्रत्येक रेघेची पातळी 0 आहे.
  - **Pending:** नव्या module मधला छोटा wrapper, त्याच `_beyond` आणि buffer ने, (candidate bar, confirm bar) परत देतो. `breaks.py` बदलायचं नाही.
  - Break चा दिवस-वेळ = confirm bar.
  - A2 bar आणि A2 च्या `known_at` मध्ये break झाला असेल ⇒ रेघ जन्मतःच "तुटलेली / flip".
- **Sweep:** wick पलीकडे, close अलीकडे ⇒ touch (§2.4) + "sweep" खूण.
- **Break सोबत confirmation-नोंद (थर 7 साठी; इथे निर्णय नाही):**
  - DeMark Q1: break candle च्या आधीची candle break च्या **उलट** दिशेने बंद;
  - Q2: break candle चा **open** रेघेपलीकडे;
  - Q3: projected value = आधीच्या candle चा close + (close − low) (up-break) / close − (high − close) (down-break) रेघेपलीकडे.
  - Sperandeo 1-2-3 ची अवस्था: (1) break झाला; (2) trend च्या टोकाची चाचणी अयशस्वी (भाव टोक ओलांडत नाही आणि D0 pivot बनतो); (3) point-2 (break नंतरचा पहिला उलट swing) तुटला. प्रत्येक पायरीची वेळ.
- **Throwback / retest:** break नंतर रेघेकडे परतणं (Bulkowski: ~59% वेळा). Retest ची candle आणि ती held झाली का (flip भूमिकेत) ⇒ "retest" खूण.
- **Flip:** break नंतर रेघ उलट भूमिकेत. Confirm + 1 पासून उलट side ने पुन्हा scan. Flip नंतरचा पहिला held touch = "retest" खूण (Bulkowski).
- **मेली:** फक्त flip नंतर पुन्हा real break. शेवटच्या held touch नंतर median touch-spacing च्या N = 3 पट bars (अंदाज 2/3/4) काहीच नाही ⇒ `stale` descriptor (मेली नाही; "लागू नाही" वर्ग).
- **भूमिका:** H-रेघ ⇒ resistance, L ⇒ support; flip नंतर उलट. भाव वर / खाली ही वेगळी "जागा".

## 4. Correction (K) ची स्वतःची रेघ
**K = थर 2 चा K** (सध्याच्या I_end पासून). Anchors फक्त confirmed pivots; K चं tentative टोक कधीच anchor नाही.

**I खाली (K वर जातो):**
- **आधार रेघ** = K च्या lows ची रेघ. ही "trendline breakout" ची रेघ.
- **टोक रेघ** = K च्या highs ची (wedge चं 1–3; 5 = touch / throw-over).
- **Break घटना** = close आधार रेघेच्या **खाली**.

**I वर (K खाली येतो):**
- आधार रेघ = K च्या highs ची.
- टोक रेघ = lows ची.
- Break घटना = close आधार रेघेच्या **वर**.

**Anchors कसे निवडायचे:**
1. थर 3 च्या preferred pattern ची रेघ असेल तर तीच:
   - wedge: आधार 2–4, टोक 1–3–5;
   - zigzag: आधार I_end (K ची सुरुवात) ते B;
   - triangle: B–D आणि A–C.
2. नाहीतर K मधले, **I_end सह**, शेवटचे दोन same-type confirmed pivots, जे §2.3.1 पाळतात; K-रेघ spacing = वेगळं setting (default 2 bars; §2.3.3 चे 6 नाही).
3. Pattern बदलला तर रेघ बदलते. नवी id, बदल-नोंदीत.

**Break घटना:**
- **फक्त पहिल्यांदा:** मागचा close अलीकडे आणि या candle चा close पलीकडे. प्रत्येक आधार-रेघ id साठी एकदाच.
- नोंद:
  - candle;
  - close किती σ पलीकडे;
  - candle ची ताकद (थर 2 च्या मापांवर: body %, range / σ, दिशा);
  - `breaks.py` चा pending / confirm, माहितीसाठी;
  - **DeMark Q1–Q3 (§3) याच break साठी** (1-2-3 K-रेघेला लागू नाही).
- **ही फक्त घटना आहे.** थर 7 हिला commitment candle सोबत वाचेल (Abhi: break + commitment candle ⇒ entry; फक्त break ⇒ noise).

**Trend channel line (Brooks):** v2.2 stub.

**K टोक-रेघेला स्पर्श** (wedge च्या 1–3 रेघेला 5 चा स्पर्श, throw-over सह): खूण, थर 3 च्या पूर्णतेसाठी पुरावा.

**K च्या स्वतःच्या रेघा "K area मध्ये" साठी कधीच मोजायच्या नाहीत** (स्वतःलाच पुरावा देणं होईल; §5).

## 5. Trade बाजूची sloping area आणि K
- **Trade बाजू** थर 4 प्रमाणे (I ची दिशा; range ⇒ दोन्ही).
- **Trade-बाजूच्या रेघा:**
  - I खाली ⇒ resistance-भूमिकेच्या **trade-योग्य (§2.7, candidate सह)** रेघा (उतरती trend रेघ, flip केलेली support रेघ), भावाच्या वर.
  - I वर ⇒ आरसा-रूप.
  - सपाट रेघा आणि K च्या स्वतःच्या रेघा वगळायच्या.
- **चालणारी रेघ:** दोन्ही anchors K च्या शेवटच्या leg सुरू होण्याआधी जन्मलेले (structural tops / origin; provisional नाही; K च्या टोकावर नाही); K ची भेट = ≥ 3रा स्पर्श. ≥ 3 held आधीच = quality (grade), अट नाही.
- **K sloping area मध्ये आहे का:** K च्या शेवटच्या leg ची candle अशा रेघेच्या ± τ मध्ये ⇒ हो; wick पलीकडे + close आत ⇒ हो (sweep); close पलीकडे पण accept नाही (detrended) आणि real break नाही ⇒ हो (pending); **accept ⇒ नाही.**
- **Intersection (सगळ्यात मजबूत; आडवा ∩ तिरका):** त्याच candle वर ती रेघ थर 4 च्या trade-बाजूच्या zone च्या पट्ट्यात आहे. तो zone त्या candle च्या आधी जन्मलेला असावा ⇒ "आडवा ∩ तिरका" खूण.
- **थर 4 ला परत:** "K area मध्ये" = zone **किंवा** अशी valid trade-बाजूची रेघ. Output मध्ये कोणतं ते स्पष्ट.

## 5a. अंदाज register
close-पलीकडे 0.3 σ; spacing 6 / K-रेघ 2; slope 0.5 σ/bar; सपाट 0.02; τ 0.2 σ; K-जवळ 1 σ; मेली 3× spacing; internal 0.3 σ; slope वर्ग 0.5×/1×; — प्रत्येकी 3 पर्याय, वर्ग live-code / Bulkowski / अंदाज.

## 6. Charts आणि तपासणी (Abhi साठी)
- **15M:**
  - valid trend रेघा जाड, उमेदवार बारीक तुटक; channel कडा मध्यम;
  - anchors आणि held touches वर ठिपके; sweep वर वेगळी खूण;
  - रेघा decision bar पुढे थोड्या (projection) तुटक;
  - K च्या आधार / टोक रेघा वेगळ्या रंगात; आधार-रेघेचा break असेल तर ती candle खुणेने;
  - थर 4 चे trade-बाजूचे zones फिके; intersection वर ★;
  - flip / pending / मेली अवस्था लेबलमध्ये.
- **1H:** D2–D3 trend रेघा.
- **कोपऱ्यातला box:**
  - trade बाजू;
  - K sloping area मध्ये: हो / नाही, रेघ, touches, intersection;
  - K आधार-रेघ: break झाला का, candle, किती σ;
  - पुढची trade-बाजूची रेघ, आणि तिची आत्ताची किंमत;
  - final momentum verdict (थर 4 re-emit), K area (थर 4), संदर्भासाठी.
- **कधी:** दिवस-अखेरीस, आणि दिवसात कमाल 3 "महत्त्वाचे क्षण": K ने trade-बाजूच्या रेघेला स्पर्श केला; K आधार-रेघेचा break; रेघ flip.
- **Run:** शेवटचे N = 22 trading days (code मध्ये तारीख नाही). Output trade-data `review/trendlines/<run_id>/`, PDF, Telegram.
- **Telegram "🧭 TRENDLINE CHECK n/N · दिवस · वेळ"**, album (15M, 1H). Caption ≤ 8 ओळी, ≤ 1024 अक्षरं UTF-16, code keys नाहीत:
  ```
  🧭 TRENDLINE CHECK n/N · दिवस · वेळ
  बाजू: seller / buyer / range
  K रेघेवर: हो / नाही · touches · ∩ zone
  K आधार-रेघ: break / नाही · candle
  पुढची रेघ: किंमत
  Reply: ✔ बरोबर · ✘ कोणती रेघ चुकली / सुटली (दोन टोकं: वेळ, किंमत)
  ```
- Replies `backtest_review` मध्ये (प्रकार `trendline_check`). Abhi ने दिलेली रेघ फक्त अहवालात (code ची कोणती रेघ जवळची, किती touches); त्यावरून नियम नाही.

## 7. मोजमाप (वर्णन, backtest नाही; PDF चं पहिलं पान)
- प्रत्येक दिवशी valid रेघा (प्रकार / बाजू), उमेदवार किती.
- Touches चं वितरण; sweep touches किती.
- Flip / pending / मेल्या किती.
- K sloping area मध्ये आलेले क्षण; त्यापैकी intersection किती.
- K आधार-रेघेचे breaks किती, त्या वेळी momentum (थर 3) आणि K area (थर 4) काय होते.
- Abhi च्या replies मधल्या रेघांशी जुळणी (अहवाल).
- Primary / latest / fan / internal रेघांचं वाटप; किती वेळा primary आणि latest एकच रेघ होती.
- Break नंतर throwback किती वेळा (Bulkowski च्या 59% शी तुलना, फक्त वर्णन); DeMark qualifiers किती breaks ला लागू होते; 1-2-3 पूर्ण झालेले किती.
- Trade-योग्य touches चे quality descriptors (slope वर्ग, अंतर, आयुष्य, inbound) आणि त्या वेळचा थर 3 momentum.
- "अंदाज" आकड्यांची sensitivity (τ, slope, close-पलीकडे मर्यादा). **फक्त वर्णन;** यावरून Abhi शिवाय कोणताही default बदलायचा नाही.

## 8. Tests (तारखा नाहीत; synthetic data)
0. **v2.1 भर:** `end=decision_bar`; origin frame-लांबी-स्वतंत्र (reversal वरून); structural top फक्त close वर (sweep ⇒ नाही); provisional-top रेघ §5 ला कधीच नाही; भेट continuity (दूर जाऊन परत = एक); buffer-पलीकडे-नाकारलेला = false_break touch; candidate रेघ + K 3रा touch = चालते; primary A2 A1 कडे सरकते; named lines cap बाहेर; σ जन्माला (max rule); DeMark Q2 open / Q3 formula; मेली spacing-आधारित; K-रेघ break ला Q1–Q3; id मध्ये internal; register.
1. **रेघ:**
   - फक्त correction-टोकं / origin / provisional टोक anchor होतात; impulse-आतला high anchor होत नाही;
   - correction-टोक फक्त नवा lower low झाल्यावर (`top_known_at`), truncation test;
   - fan क्रमांक; 3ऱ्या fan चा break नोंद;
   - trade-योग्य: सगळ्या 5 अटी, आणि प्रत्येक अट मोडल्यावर वर्ग बदलतो;
   - रेघ, max(`known_at`, `top_known_at`) पासूनच;
   - primary (Sperandeo): A2 = latest low च्या आधीचं correction-टोक; किंमत कापत असेल तर पुढचं; नवा low ⇒ नवी primary;
   - latest (DeMark): दोन सगळ्यात अलीकडची correction-टोकं; नवं टोक ⇒ बदल;
   - internal आवृत्ती फक्त wick-विकृती असताना, खुणेसह;
   - quality descriptors बरोबर (slope वर्ग, अंतर, आयुष्य, inbound);
   - anchors मध्ये close पलीकडे ⇒ अवैध; wick पलीकडे ⇒ वैध;
   - slope आणि spacing मर्यादा;
   - सपाट रेघ "K area" मध्ये मोजली जात नाही;
   - `cas_mask` नंतरचा bar index बरोबर;
   - D1 / D2 मधून तीच रेघ ⇒ एकच id.
2. **Touch:**
   - wick चा स्पर्श (pivot नसलेल्या candle वरही) ⇒ touch;
   - रेघेला चिकटलेल्या अनेक candles ⇒ एक touch;
   - held फक्त ≥ θ_D0 नंतर; चालू भेट मोजली जात नाही;
   - anchors दुहेरी मोजले जात नाहीत;
   - close पलीकडे पण buffer आत ⇒ "खोटा break" touch;
   - 3 held ⇒ valid, 2 ⇒ उमेदवार;
   - session बदलल्यावर σ बदलला तरी जुने touches तेच (जन्माचा σ).
3. **Break:**
   - detrended frame वर `first_real_break` = रेघेचा break;
   - A1 आधीच्या MR मुळे सुरुवातीचा break सुटत नाही;
   - `retest_fn` None; `BreakCache` नाही (दोन रेघांचे निकाल मिसळत नाहीत);
   - pending wrapper;
   - A2 bar आणि `known_at` मध्ये break ⇒ जन्मतः flip;
   - flip नंतर side उलटते; retest; दुसरा break ⇒ मेली;
   - DeMark qualifiers 1–3 प्रत्येकी खरे / खोटे synthetic वर; 1-2-3 च्या तिन्ही पायऱ्या क्रमाने आणि truncation-safe; throwback खूण;
   - channel line समांतर, उलट टोकातून; overshoot खूण.
4. **K रेघा:**
   - wedge ⇒ आधार 2–4, टोक 1–3–5; zigzag ⇒ I_end–B;
   - I खाली ⇒ break खाली; I वर ⇒ break वर (आरसा-रूप);
   - tentative टोक anchor होत नाही;
   - break घटना फक्त पहिल्या पलीकडच्या close वर, एकदाच;
   - candle-ताकद नोंद.
5. **Trade बाजू आणि intersection:**
   - I खाली ⇒ resistance रेघा;
   - K च्या शेवटच्या leg आधी valid नसलेली रेघ ⇒ चालत नाही;
   - K च्या स्वतःच्या रेघा आणि K-टोकावर anchor असलेल्या रेघा ⇒ "K area" नाही;
   - intersection फक्त त्या candle आधी जन्मलेल्या zone सोबत;
   - थर 4 चा "K area" रेघेमुळे हो, आणि स्रोत स्पष्ट.
6. **क्रम आणि डुप्लिकेट:** key पूर्ण क्रम; जवळजवळ-सपाट रेघांची डुप्लिकेट ओळख; id स्थिर.
7. **No-lookahead truncation:** decision bar नंतरचा data काढला तरी रेघा, touches, अवस्था, intersection आणि घटना तेच.
8. **Holdout:** anchors / touches holdout मधून नाहीत.
9. **Replay = live:** incremental गणना आणि पूर्ण पुनर्गणना यांचा निकाल तोच.
10. **Shadow:** `areas.py::sloping`, `breaks.py`, live engines आणि live signals byte-for-byte तसेच.
11. **Caption:** ≤ 1024, code keys नाहीत. **Output:** फक्त trade-data path; order call नाही; पुन्हा run ⇒ तोच JSON.
12. **Code मध्ये तारीख नाही:** नव्या module वर grep test.

## 9. क्रम
1. थर 4 ला Abhi चा ✔ ⇒ मगच सुरुवात.
2. नवं module (उदा. `trendlines2/`), थर 1 च्या pivots वर. `elliott/breaks.py::first_real_break` आणि `median_range` import (detrended frame; `retest_fn=None`; cache नाही). Shadow.
3. थर 4 मध्ये "K area मध्ये" = zone किंवा valid रेघ, ही छोटी भर (थर 4 चा test अद्ययावत).
4. Full suite ⇒ स्वतंत्र review ⇒ run (शेवटचे 22 दिवस) ⇒ trade-data push ⇒ PDF Abhi ला ⇒ VPS वरून Telegram ची एक ओळ (15:30 नंतर).
5. Abhi ✔ / ✘. चुका ⇒ सामान्य नियमात दुरुस्ती, पूर्ण महिना पुन्हा run, आधी बरोबर आलेले दिवस मोडले नाहीत ना ते दाखवायचं.
6. Abhi च्या ✔ नंतरच थर 6 (RSI divergence).
