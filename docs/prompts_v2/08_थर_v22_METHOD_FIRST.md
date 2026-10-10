Abhi कडून — Trade repo: थर v2.2 "method-first" spec (v2.1 engine चा पूर्ण review नंतर). हा दस्तऐवज 07_थर7 आणि decision2/legs2/zones2 च्या gate-logic ची जागा घेतो; थर 1 (swings2, k D1=4, D2=6) ✔ तसाच.
नियम: तारखा/किंमती hardcode नाहीत; सगळे thresholds "price-behaviour" नियम; अंदाज-आकडे कमीत कमी आणि register मध्ये; known_at + truncation tests; NIFTY holdout sealed; shadow/PAPER; merge फक्त Abhi; LIVE/VPS नाही. काम न थांबता (OPEN_QUESTIONS + default), WORK_LOG दर 2 तासांनी.

══════════════════════════════════
0. Review चा निष्कर्ष (का बदलतोय)
══════════════════════════════════
NIFTY 18 Aug–09 Oct (37 sessions, 222 बंद 1H, स्पष्ट downtrend, Abhi ने ≥4 trades खुणावले): engine 222/222 wait.
Funnel: G-A 185 (83%) — "I नाही" 91 (41%), drift 52, transition 41; G-C "area नाही" 33; G-D 4; G-E (commitment) पर्यंत 0 bars.
विरोधाभास: D1 "K चालू" (pullback चालू — Abhi trade घेतो तीच वेळ) 38 bars, त्यातले 28 G-A ने block (transition 21, drift 7) — कारण regime = 20-bar 1H window चं net/H ≥ 0.5, जे pullback मध्ये नेहमी घसरतं. D2 DOWN असताना 98 पैकी 49 bars net/H अट अपयशी.
D3 trend 222/222 unknown (σ 20 sessions + warm-up 30 sessions + k=16σ ⇒ 3 महिन्यांत D3 कधीच नाही); D2 unknown 41 bars.
Impulse "पात्र leg नाही" 91 bars: I ला leg चं C/V "nature" label (c_hi 0.6 / v_hi 1.2 सारखे fixed आकडे) किंवा BOS + origin unbroken + range_alt mid-σ अट.
Zones 121: prune/merge 76, दुसऱ्या break ने 27 मेले, `self` वगळ 91 bars; flip नंतर 24 तासांत 21 मेले.
Commitment ला 7 एकाचवेळी अटी (close zone पलीकडे + range ≥ median + overlap < 0.6 + counter-climax नाही + CLV/beyond-prev + merged ≤ 3 + वेळ-खिडकी), momentum ला 12-item checklist ratio ≥ 0.65 (≥ 6 non-NA, ≥ 2 pushes), pattern ला completed template; वर Gray-1/HTF veto/htf_unknown/position_ban/final_leg/retrace ≥ 0.80.
निर्णय: logic चुकीचं (regime, impulse व्याख्या, trend degree, zone lifecycle) + over-analysis (gates ची साखळी). म्हणून gates ची साखळी Abhi च्या 6 पायऱ्यांनी बदलायची; बाकी सगळं (pattern family, RSI, volume, VIX, vision, nature) = grade/annotation, gate नाही.

══════════════════════════════════
1. Pipeline = Abhi च्या 6 पायऱ्या (हेच gates; दुसरं gate नाही)
══════════════════════════════════
प्रत्येक पायरीचं output chart वर + json मध्ये; प्रत्येक बंद 15M bar ला checklist ①–⑥ ✔/✘ + कारण.

① Trend (Daily, Dow):
 - Input: Daily candles (1m वरून बांधलेले, bar-END label; BANKNIFTY ला fetched D). Daily swings: थर 1 DC पद्धत Daily वर (σ_D = Daily range median, k_D config; warm-up फक्त σ साठी किमान sessions — 20 नव्हे, config, default 10) किंवा साधा pivot (N bars दोन्ही बाजूला, N config default 2) — दोन्ही implement, setting `daily_swing_method`, default pivot (कमी warm-up).
 - Uptrend = शेवटचे HH+HL; downtrend = LH+LL. Trend संपतो (neutral) जेव्हा शेवटचा HL (↑) / LH (↓) Daily close ने तुटतो. नवा trend = नवा HL+HH / LH+LL. Range = neutral + दोन H जवळपास समान आणि दोन L जवळपास समान (σ_D च्या अपूर्णांकात; config).
 - Protected swing = तो HL/LH; chart वर रेघ.
 - Output: daily_trend ∈ {UP, DOWN, RANGE, NEUTRAL}, protected, range band (असल्यास).
 - Trade दिशा: UP ⇒ bull put; DOWN ⇒ bear call; RANGE ⇒ खालच्या कडेला bull put, वरच्या कडेला bear call; NEUTRAL ⇒ trade नाही.
 - Weekly: फक्त संदर्भ (chart + grade); gate नाही. 1H/15M degrees trend ठरवत नाहीत.
 - v2.1 चं regime (h1_window/trend_h/trend_net/range_net/barbwire/transition), D3/htf veto, htf_unknown, Gray-1 — सगळं काढा.

② Level (1H, trade-बाजूचा significant area):
 - जन्म (कोणतीही एक): (a) 1H trend-degree swing (D2 वर 1H ची HH/HL/LH/LL) किंवा Daily swing; (b) BOS केलेल्या impulse चा origin/base (पहिली trend-दिशेची candle ज्यापासून मागचा swing तुटला, तिचा पट्टा); (c) S/R flip: structural swing/base real break ने तुटला ⇒ उलट भूमिका; (d) liquidity: equal highs/lows (σ_1H च्या अपूर्णांकात). लहान pivot (D0/D1 15M) पासून level नाही.
 - पट्टा: swing candle चा wick-to-body (config: wick/body), किमान रुंदी σ_1H × अपूर्णांक.
 - गुण: वरच्या TF चं confluence (+), impulse 50/61.8/~80% retracement तिथेच (+, फक्त level असेल तरच), trend-दिशेची trendline/channel रेघ तिथे (+), fresh (+), अनेक चाचण्या (−). Merge: overlap ⇒ एक.
 - जीवनक्रम: संदर्भ → चाचणी (किंमत आत/पलीकडे) → प्रतिक्रिया → पुष्टी → (मृत्यू फक्त: level पलीकडचा structural swing close ने तुटला). Close पलीकडे ⇒ मृत्यू नाही. Sweep (पलीकडे जाऊन परत) ⇒ ★ +1. Prune: जिवंत level snapshot मधून कधीही नाही (फक्त दूरची levels chart वर लपवा).
 - `self` नियम काढा: K च्या पहिल्या टोकाचा level दुसऱ्या चाचणीला वैध.
 - Trade-बाजू: DOWN ⇒ किंमतीच्या वरचे seller levels; UP ⇒ खालचे buyer levels. Active level = pullback ज्याकडे जातोय/ज्यात आहे ती (जवळची 2).
 - Trendline/channel: तीच साखळी; पक्की = ≥ 3 स्पर्श confirmed swings वर; मृत्यू पलीकडच्या swing ने.

③ Pullback (K):
 - Impulse = Daily-trend दिशेची 1H चाल जिने मागचा 1H swing तोडला (BOS). nature/C/V/spike/climax = annotation, पात्रता नाही. Origin = (b) चा base. I_end = त्या चालीचं टोक.
 - K उघडते: I_end नंतर पहिली उलट-दिशेची 15M swing confirm (D1) किंवा किंमत trade-बाजूच्या level मध्ये शिरली — जे आधी.
 - K reset नाही जर नवं टोक < 0.25 σ_1H ने सरकलं (तेच टोक). K रद्द फक्त: I चा origin close ने तुटला (मग trend पुन्हा ① ने) — "parent_flip/reversal flag" ने नाही.
 - K चा प्रकार (zigzag/flat/triangle/complex) = annotation + grade; state "forming/complete" gate नाही. "final_leg_in_progress", "position_ban", "Gray-2" काढा.
 - ③ ✔ = K उघडी आहे आणि किंमत active level च्या पट्ट्यात/स्पर्शात (wick), आणि level मध्ये ती उलट बाजूने आली (bull put: वरून खाली; bear call: खालून वर). Level मधून gap/breakout ने पार ⇒ ✘ (breakout नाही).

④ Correction संपतेय (power shift, 15M, फक्त level मध्ये): खालच्यापैकी किमान 2 (config, default 2):
 (a) counter-trend candles च्या ranges शेवटच्या 3 मध्ये लहान होत जातात; (b) शेवटच्या 3 bodies एकमेकांवर overlap (≥ 50%); (c) शेवटचा counter push नवं टोक करत नाही किंवा sweep करून परत बंद होतो (false break); (d) trend-दिशेचे wicks/rejection; (e) RSI divergence (थर 6, तसाच) — e फक्त पूरक, एकटी पुरेशी नाही.
 - 12-item momentum checklist आणि ratio ≥ 0.65 काढा; items annotation म्हणून ठेवू शकता.

⑤ Trendline/channel break (असल्यास): K ची आतली तिरकी रेघ (K चे ≥ 2 स्पर्श) trend-दिशेने close ने तुटली ⇒ grade + (gate नाही).

⑥ Commitment candle (15M, level मध्ये/लगत): एक candle (किंवा ≤ 2 merged, config) जी trend-दिशेची, body ≥ 50% range (config), मागच्या candle च्या extreme पलीकडे close, आणि close level च्या trade-बाजूला किंवा level मध्ये (पूर्ण पलीकडे close ही अट नाही — reclaim चालेल). Engulf = +grade. वेळ-खिडकी फक्त settings (entry_start/end) — default 09:30–15:15 तसाच.
 - G1–G8, overlap3, rng_ratio ≥ median, counter-climax, tier — काढा (annotation म्हणून ठेवू शकता).

⑦ Risk (gate नाही, फक्त हिशेब + R:R अट): SL = level पलीकडे आणि K चं टोक पलीकडे + buffer (σ_15M × अपूर्णांक, config); target = मागचा impulse end (I_end) किंवा विरुद्ध बाजूचा जवळचा जिवंत level (जवळचा); R:R < 3 ⇒ "trade नाही (R:R)" (हे एकमेव numeric gate, Abhi चा नियम). Premium 60–80%, expiry नियम, exits (hard_exits) तसेच.

⑧ Grade/size/annotation (निर्णयात नाही): pattern family, nature/volume (futures), RSI, VIX/event size, vision veto (फक्त veto, order नाही), Weekly संदर्भ, confluence ★.

══════════════════════════════════
2. Output आणि chart
══════════════════════════════════
- प्रत्येक बंद 15M bar: {daily_trend, protected, active_levels[≤2], K{open, origin, end, extreme, type}, checklist ①–⑥ ✔/✘ + कारण, decision setup/wait/no_trade, SL/target/R:R, grade}.
- Chart (trader view): W+D संदर्भ (Dow swings, trend, protected, मुख्य level) · 1H (swings, impulse, K, active levels ★ कारणासह, target level) · 15M (level, power-shift खुणा, commitment candle, ✅/🟡 बाण + label, B2 योजना). Debug view वेगळा. Caption 5–7 ओळी (आधीचा spec).
- B1/B2 तसेच; ✅ फक्त ①②③④⑥ पूर्ण.

══════════════════════════════════
3. Tests (crafted data; प्रत्येक नियमाला)
══════════════════════════════════
- Dow: HH+HL ⇒ UP; HL close ने तुटला ⇒ NEUTRAL; नवा LH+LL ⇒ DOWN. Daily unknown फक्त data अपुरा असेल तरच (≤ 10 sessions).
- Pullback मध्ये trend बदलत नाही (regime-सारखं net/H नाही) — test: deep pullback 60% retrace, trend UP कायम.
- Level: लहान pivot पासून level नाही; BOS origin level बनतो; flip भूमिका बरोबर; close पलीकडे ⇒ जिवंत; structural swing तुटला ⇒ मेला; sweep ⇒ ★+1; `self` टोक दुसऱ्या चाचणीला वैध.
- K: < 0.25σ नवं टोक ⇒ reset नाही; origin break ⇒ रद्द.
- Breakout नाही: level मधून gap/पार ⇒ ③ ✘.
- Power shift: 2 of (a–d) ⇒ ④ ✔; फक्त RSI ⇒ ✘.
- Commitment: body ≥ 50%, beyond prev extreme ⇒ ✔; reclaim (level मध्ये close) चालतं.
- Truncation (शेवटचे bars कापले तरी आधीच्या निर्णयात बदल नाही), तारीख-मुक्त, holdout guard.
- Acceptance (मोजमाप, tuning नाही): NIFTY 18 Aug–09 Oct वर Abhi च्या E1–E4 (01, 03, 04, 07 Sep bear calls) ✅ किंवा 🟡 यावेत; BANKNIFTY 3 महिन्यांवर ✅ ची यादी + प्रत्येकाला ①–⑥ कारणं; ✅ मध्ये breakout शून्य (test).

══════════════════════════════════
4. क्रम
══════════════════════════════════
A. design PR: docs/prompts_v2/08_थर_v22_METHOD_FIRST.md (हा spec) + decision2 चा नवा module (decision3/ किंवा decision2 v22 flag) — जुना code तसाच (shadow तुलना), setting `engine_version`.
B. ① Daily Dow + ② levels (lifecycle) + tests → charts (W/D/1H) → Abhi ✔.
C. ③ K + ④ power shift + ⑥ commitment + ⑦ risk + B1/B2 → NIFTY window + BANKNIFTY → charts + acceptance आकडे → Abhi ✔.
D. Telegram trader view (आधीचा spec) या engine वर; v2.1 charts बंद.
E. Monday PAPER bots ला `signal_source=engine` हा engine (v2.2) — Abhi ✔ नंतरच; तोपर्यंत own.
प्रत्येक PR: स्थिती-तक्ता, hashes, मुद्दा-निहाय "fixed/कारण/needs Abhi", OPEN_QUESTIONS. Thresholds निकाल पाहून फिरवायचे नाहीत; प्रत्येक आकडा register मध्ये "Abhi नियम / व्याख्या / अंदाज" वर्गासह.

══════════════════════════════════
5. जोड (research नंतर): reversal / correction-end ची यांत्रिक व्याख्या — पायरी ④ आणि ⑥ ला पूरक
══════════════════════════════════
Practitioner साहित्य (Brooks signal/entry bars, Wyckoff spring/upthrust, role-reversal playbooks, zigzag/pivot mechanics) कुठेही universal आकडे देत नाही; ते "बार-वर्तन" नियम देतात. म्हणून इथे फक्त वर्तन-नियम; आकडे फक्त "किमान" म्हणून, register मध्ये.
5.1 Pullback चा शेवट = "दुसरा प्रयत्न" (Brooks H2/L2): pullback मध्ये counter-move चे दोन पाय (ABC = दोन पाय) झाल्यावर trend-दिशेचा दुसरा close-beyond-prior-close प्रयत्न हा सर्वात विश्वासार्ह entry. नियम: ⑥ चा commitment candle K च्या **दुसऱ्या** (किंवा नंतरच्या) counter-leg नंतर आला तर grade A; पहिल्याच counter-leg नंतर (H1/L1) फक्त level ★ ≥ 2 आणि signal-bar मजबूत असेल तरच (grade B). चौथ्या प्रयत्नानंतर (H4/L4) ⇒ reversal शक्यता, trade नाही.
5.2 Signal-bar गुणवत्ता (⑥ साठी मोजमाप): close range च्या trend-बाजूच्या वरच्या/खालच्या तृतीयांशात; body मागच्या 5 candles च्या सरासरी body पेक्षा मोठी; उलट बाजूचा wick body पेक्षा लहान; range मागच्या सरासरीपेक्षा मोठा (हे "मोठा/लहान" तुलना, fixed आकडा नाही). Doji / दोन्ही बाजूंनी मोठे wicks / मध्य close = कमकुवत ⇒ ⑥ ✘. Entry trigger पर्याय (setting): commitment close वर (default) किंवा signal-bar extreme च्या 1 tick पलीकडे break वर (Brooks).
5.3 Overlap नियम (gate, पण σ नाही): 3+ लागोपाठ candles बहुतांश overlap आणि त्यात doji ⇒ "range अवस्था" ⇒ entry नाही (v2.1 चा barbwire σ-नियम याने बदला). Follow-through: entry नंतरची candle signal-bar शी ≤ 50% overlap ⇒ पुष्टी, अन्यथा "failed entry" ⇒ exit/breakeven नियम (⑦).
5.4 Flip (S/R role reversal) ची पुष्टी: break = decisive close (body पलीकडे, displacement) — wick नाही; flip "पक्का" = परत येऊन trade-दिशेने तत्काळ rejection आणि closes बरोबर बाजूला टिकणे (acceptance). Closes पुन्हा जुन्या बाजूला टिकले ⇒ flip अयशस्वी ⇒ level आपल्या जुन्या भूमिकेत परत (मृत्यू नाही) आणि उलट बाजूला trap-setup नोंद. Level ★: touches, provenance (period extreme, range edge, base), freshness (पहिली चाचणी सर्वात मजबूत; प्रत्येक चाचणी ★ −), width (zone, रेघ नाही).
5.5 Spring/Upthrust (false break) = पायरी ④ (c) चा मजबूत प्रकार: level पलीकडे probe, त्याच/पुढच्या candle मध्ये close परत आत, नंतरचा rally/dip त्या extreme च्या आत थांबतो ⇒ ④ ✔ + grade; acceptance पलीकडे ⇒ रद्द.
5.6 Daily swings: pivot bar-count (N दोन्ही बाजूला) किंवा ATR/σ-multiple reversal threshold — दोन्ही setting; confirmation lag स्वीकारायचा, pivot चा known_at = confirm bar (lookahead नाही). Universal आकडा नाही ⇒ N आणि k register मध्ये "Abhi charts वरून", निकाल पाहून नाही.
5.7 काय research देत नाही: levels/pullback entries चा "सिद्ध" edge नाही; म्हणून स्वीकार-निकष = Abhi च्या chart-खुणा (E1–E4, BANKNIFTY खुणा) आणि "✅ मध्ये breakout शून्य", आणि trial ledger/holdout शिस्त — निकाल पाहून thresholds नाही.

══════════════════════════════════
6. जोड: "Chart पुस्तकासारखं वाचणं" — checklist नव्हे, पुराव्याचं वजन + psychology (§1 च्या ①–⑥ ला हे लागू)
══════════════════════════════════
6.1 तत्त्व: picture-perfect setup दुर्मिळ. Engine प्रत्येक tool चं output "पुरावा" म्हणून घेतो, त्याचा psychology-अर्थ लावतो (भीती/लोभ; कोण नियंत्रणात, कोण थकतोय, कोण अडकला), आणि एकत्रित conviction ठरवतो. AND-साखळी नाही.
6.2 कठोर नियम फक्त तीन (invalidation): (H1) दिशा = Daily Dow trend (range ⇒ कडा; neutral ⇒ नाही); (H2) entry pullback नंतर significant level वर/जवळ, किंमत level मध्ये उलट बाजूने आलेली — breakout/gap-through ⇒ नाही; (H3) SL (level + K टोक पलीकडे) आणि target ठरतं, R:R ≥ 3. बाकी कोणतीही अट एकटी trade नाकारत नाही.
6.3 पुरावे आणि त्यांचा psychology-अर्थ (प्रत्येक पुरावा: उपस्थित/अनुपस्थित/विरुद्ध + वजन; वजन register मध्ये, Abhi वर्ग):
 - Level ची गुणवत्ता (★): structural swing / BOS origin / flip / liquidity, confluence, freshness — "इथे आधी कोणी जिंकलं, आता कोण थांबलेला आहे".
 - Counter-move थकवा: candles लहान होणं (विरुद्ध बाजूचा जोर संपतोय), bodies overlap (दोन्ही बाजू सम), trend-दिशेचे wicks/rejection (विरुद्ध बाजू नाकारली जातेय), शेवटचा push नवं टोक करत नाही (तो गट हरतोय).
 - Trap: sweep/spring/upthrust — level पलीकडे जाऊन परत (breakout घेणारे अडकले ⇒ त्यांचं exit = आपल्या दिशेला इंधन). सर्वात मजबूत पुरावा.
 - दुसरा प्रयत्न (H2/L2): counter-move चे दोन पाय झालेत (पहिला पाय कमजोर हात काढतो, दुसरा संधी).
 - Commitment candle: trend-दिशेची मोठी body, close तृतीयांशात, उलट wick लहान — "नियंत्रण परत गेलं" हा क्षण. Engulf = विरुद्ध बाजूचा पूर्ण नकार.
 - RSI divergence: विरुद्ध चालीची गती कमी.
 - Volume (futures): pullback मध्ये कमी = विरुद्ध बाजूला खरी बांधिलकी नाही.
 - Pattern family (zigzag/flat/triangle): correction किती परिपक्व (triangle/flat चा शेवट = निर्णयाचा क्षण).
 - वरचा TF संदर्भ (Weekly), VIX/event: आकार आणि सावधगिरी.
 - विरुद्ध पुरावे (वजन −): trend-विरुद्ध मोठ्या bodies level मध्ये (विरुद्ध बाजू आक्रमक), level पलीकडे acceptance (closes टिकले), 3+ overlapping candles + doji (कोणीच नियंत्रणात नाही ⇒ वाट), चौथा+ प्रयत्न (reversal चा धोका), CHoCH Daily वर.
6.4 Conviction = पुराव्यांची बेरीज (वजन × उपस्थिती) ÷ कमाल; चार स्तर: strong (A) / moderate (B) / weak (वाट) / against (नाही). Trade: A ⇒ पूर्ण size; B ⇒ कमी size किंवा Vision/Abhi पुष्टीने; weak ⇒ "वाट पाहा: कशाची" (कोणता पुरावा गहाळ). स्तरांच्या सीमा register मध्ये; निकाल पाहून नाही, Abhi च्या chart-खुणांशी जुळवून (E1–E4 ⇒ A/B यायला हवेत).
6.5 "वाचन" output (प्रत्येक बंद 15M candle, caption आणि json): 3–5 ओळींची कथा — "Daily ↓: विक्रेते नियंत्रणात. 1H: खरेदीदारांचा pullback तुटलेल्या support (आता seller area ★★★) कडे. 15M: pullback चे दोन पाय, candles लहान, sweep होऊन परत ⇒ खरेदीदार अडकले. Commitment: मोठी लाल candle, close खालच्या तृतीयांशात ⇒ विक्रेते परत. Conviction A. Entry/SL/target/R:R." हीच कथा Vision ला (veto साठी) आणि Telegram ला.
6.6 Candle psychology सारणी (code मध्ये `candle_read`): प्रत्येक candle ला "कोण जिंकला" (buyers/sellers/कोणी नाही) + ताकद (body/range, close स्थान, wicks); patterns (engulfing, pin/hammer/shooting star, inside, doji, two-bar reversal, three-bar) = फक्त याच वाचनाचा संक्षेप; अर्थ **स्थानावर** अवलंबून (level वर trend-दिशेने = अर्थपूर्ण; मध्यभागी = नगण्य). Pattern-नाव gate नाही.
6.7 Vision (LLM) ची भूमिका: tools चे आकडे + कथा वाचून "ही कथा chart शी जुळते का" एवढंच ठरवतो (veto/पुष्टी/कारण); स्वतः level/किंमत काढत नाही; order कधीच नाही.
6.8 Tests: H1–H3 कधीही मोडत नाहीत (breakout ✘, विरुद्ध दिशा ✘, R:R < 3 ✘); पुरावा गहाळ असून conviction A येऊ शकते (उदा. RSI नाही, volume NA — तरी trade); trap + commitment ⇒ A; फक्त pattern-नाव ⇒ trade नाही; truncation; तारीख-मुक्त.

══════════════════════════════════
7. जोड: Liquidity आणि "pullback म्हणजे काय" — psychology-आधारित व्याख्या (②③④ चा गाभा)
══════════════════════════════════
7.1 Liquidity कुठे असते (engine ने प्रत्येक TF वर नकाशा ठेवायचा, `liquidity_map`):
 - Swing highs / equal highs च्या **वर**: short-सेलर्सचे stops + breakout-buyers चे buy orders ⇒ "buy-side liquidity". Swing lows / equal lows च्या **खाली**: longs चे stops + breakout-sellers ⇒ "sell-side liquidity". Equal highs/lows (σ च्या अपूर्णांकात समान) = सर्वात स्पष्ट pool. मागच्या day/week high-low, range च्या कडा, जुना protected swing = मोठे pools.
 - Trend-साइडचा अर्थ: downtrend मध्ये किंमत वरच्या pool कडे (LH च्या वर) गेली तर ती "liquidity घेण्याची" चाल असू शकते, trend बदल नव्हे — sweep होऊन परत आली तर विक्रेत्यांनी buyers ना अडकवलं ⇒ bear call चा सर्वोत्तम क्षण.
7.2 Liquidity sweep (grab) ची व्याख्या: किंमत pool पलीकडे गेली (wick किंवा 1–2 candles close) आणि **लवकर** परत pool च्या आत बंद झाली (त्याच session मध्ये / पुढच्या काही candles मध्ये — "लवकर" = acceptance नाही: closes पलीकडे टिकले नाहीत). परत आल्यानंतर पलीकडे गेलेली किंमत = अडकलेल्या traders ची जागा; त्यांचं stop/exit = आपल्या दिशेला इंधन. Sweep नंतरचा पहिला trend-दिशेचा commitment candle = conviction A चा प्रमुख घटक. Sweep झालेला level मरत नाही, ★ वाढतो (§2).
7.3 अडकलेले traders कुठे (`trapped_zone`): (a) failed breakout: level पलीकडे close, मग परत आत acceptance ⇒ breakout traders अडकले, त्यांचा exit level पलीकडे; (b) counter-trend चा शेवटचा push जो नवं टोक करून परत आला ⇒ late counter-trend traders अडकले; (c) pullback मध्ये trend-विरुद्ध मोठी candle नंतर लगेच उलट engulf ⇒ ते अडकले. Trapped zone = त्यांचा entry पट्टा; तो आपला target-मार्ग आणि SL-पलीकडची जागा ठरवायला वापरायचा (SL trapped zone च्या पलीकडे, कारण तिथे ते exit करतात आणि आपल्या दिशेने किंमत येते).
7.4 Pullback म्हणजे काय (psychology): impulse नंतर trend-साइड profit घेतो आणि counter-साइड लवकर entry घेतो ⇒ किंमत impulse च्या विरुद्ध सरकते. ही **correction** आहे (reversal नाही) जोवर: (i) protected swing (Daily/1H trend-degree HL/LH) close ने अखंड; (ii) counter-move चं character impulse पेक्षा कमजोर — लहान bodies/ranges, overlap, दोन-तीन पाय (ABC), trend-विरुद्ध BOS नाही; (iii) counter-move एखाद्या trend-side level कडे येतो (जिथे trend-साइड पुन्हा येईल); (iv) volume कमी (असल्यास). Reversal ची खूण: trend-विरुद्ध displacement (मोठ्या bodies, gap), protected swing close ने तुटणं (CHoCH), level पलीकडे acceptance. 
7.5 Engine pullback कसा ठरवतो (③ ची नेमकी व्याख्या): शेवटच्या impulse (BOS केलेली trend-दिशेची चाल) च्या टोकापासून किंमत उलट सरकली आणि (i) protected swing अखंड, (ii) counter-move चा "character score" impulse पेक्षा कमी (ranges/bodies सरासरी, overlap, BOS नाही — तुलनात्मक, fixed आकडे नाहीत), ⇒ K = pullback. Depth (retrace %) = फक्त माहिती; 50/61.8/80% level सोबत असेल तरच पुरावा. K चे पाय मोजा (zigzag/flat/triangle = annotation); "दुसरा पाय" झाला का हे §5.1 ला. Protected swing तुटला ⇒ K नाही, trend ① ने पुन्हा.
7.6 Chart/caption: liquidity pools (equal H/L, swing H/L, PDH/PDL/PWH/PWL) लहान खुणांनी; sweep ⚡ आणि trapped zone पट्टा; कथेत एक ओळ "liquidity: … वर buyers अडकले / … खाली sellers अडकले".
7.7 Tests: equal highs ⇒ pool; wick पलीकडे + close आत ⇒ sweep, level ★+1; close पलीकडे 3+ candles टिकले ⇒ acceptance (sweep नाही); failed breakout ⇒ trapped zone; counter-move मोठ्या bodies + protected तुटला ⇒ reversal, K नाही; लहान bodies + protected अखंड ⇒ pullback.
