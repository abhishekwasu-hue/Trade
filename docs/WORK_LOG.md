# WORK_LOG — TRADE_FULL_EXECUTION_PROMPT अंमलबजावणी

प्रत्येक टप्प्याची नोंद: तारीख · टप्पा · काय केलं · tests (आधी → नंतर) · निर्णय (कारणासह) · उघडे प्रश्न.
नियम (§0.2): एक टप्पा = एक PR; डीफॉल्ट वर्तन बदलत नाही; नवीन gate/engine डीफॉल्ट OFF; no-lookahead; IS = 2015–2021, VAL = 2022 → 2024-03,
sealed holdout = Upstox 2024-04 → (फक्त G4 ला, एकदाच).

## सामायिक निर्णय (सर्व टप्प्यांना लागू)

- **Branch नाव:** PDF `claude/<phase>-<slug>` सांगतो, पण या session ला push फक्त `claude/project-review-n8v42i` वर करण्याची परवानगी आहे.
  म्हणून प्रत्येक टप्पा त्याच branch वर क्रमाने (प्रत्येक merge नंतर branch `origin/main` वर reset) — "एक टप्पा = एक PR" नियम पाळला जातो.
- **`docs/ROADMAP.md` अस्तित्वात नाही** — PDF च हाच roadmap मानला.
- **Validation कालावधी:** offline डेटा (`data/nifty50_1min.parquet`) 2024-03-27 ला संपतो ⇒ VAL = 2022-01-01 → 2024-03-27 (OE चा जुना OOS विभाग तोच).
- **Sealed holdout:** sandbox मधून Upstox पोहोचत नाही ⇒ `cache_holdout_upstox.py` VPS वर चालवायचा; तो फक्त bars/दिवस संख्या आणि sha256 छापतो.

## 2026-10-05 · T1 — निदान गृहीतकं H1–H5 (PR #243)

**काय केलं:**
- OE मध्ये डीफॉल्ट-OFF knobs: `d2_allowed_biases` (H1), `d1_exit_rule` = none / bars / or_reentry (H4). H3 साठी सध्याचाच `adr_min_frac` (SL_TOO_TIGHT नकार) वापरला.
- `research_stats.py`: PBO (CSCV), Deflated Sharpe, permutation.
- `oe_t1_hypotheses.py` (8 trials, V1). `cache_holdout_upstox.py`.
- अहवाल: `docs/reports/t1_hypotheses.md` (+ trial log CSV, stats JSON).

**Tests:** 2379 → 2413+ (नवे: research_stats, T1 runner, holdout cache, D2 bias filter, D1 exit नियम, अज्ञात d1_exit_rule नकार, VAL ⊄ holdout).

**निर्णय (कारणासह):**
- H3 चा अर्थ = "SL अंतर < k × ADR असेल तर trade नाकारणे" (`adr_min_frac`), SL रुंद करणे नव्हे. कारण: हाच सध्याचा OE नियम; नवा SL-बदल mechanism आणणं T1 च्या "फक्त निदान" व्याप्तीबाहेर.
- H5 निवड नियम आधीच ठरवला: IS दैनिक-R Sharpe; BASE पेक्षा चांगला नसेल तर तो भाग BASE.
- PBO साठी सर्व 8 trials चे IS दैनिक R (ट्रेड नसलेल्या दिवशी 0), S = 16.
- Independent review (subagent): blocker नाही. SHOULD-FIX: VAL ला 2024-03-31 ची वरची मर्यादा → केलं. Nits: अज्ञात `d1_exit_rule` → ValueError; holdout dir repo ला anchored; अपूर्ण दिवस वगळला → केलं.

**निकाल (थोडक्यात):**
- सर्व trials IS मध्ये ऋण.
- H3 (0.25 × ADR) तोटा सर्वात जास्त कमी करतो, पण निरपेक्ष edge नाही (DSR 0.003). PBO 0.0002 (सापेक्ष क्रम स्थिर).
- D1/D2 नमुने फार लहान.

**उघडे प्रश्न (G2 ला):**
- H3 ला bot मध्ये default-off setting म्हणून आणायचं का?
- D2 gap-fade चं counter-bias counterfactual वेगळं गृहीतक म्हणून तपासायचं का?
- Holdout cache VPS वर चालवणे बाकी.

## 2026-10-06 · T2 — Leg & Level Strength Classifier (T2.1–T2.6)

**काय केलं:**
- `price_action/legs.py` (T2.1–T2.3):
  - median_range(N);
  - fractal + range-normalised ZigZag swings (internal 1.5×, swing 3×), दोन्हींना pivot_bar/confirm_bar;
  - legs आणि चालू (provisional) leg;
  - features: efficiency, overlap, dir dominance, body%, CLV, FVG / body gaps, displacement, speed, spread, depth, EW Tier-A;
  - लेबल्स + score + मराठी कारणं.
- `price_action/leg_eval.py`: outcomes + IS-calibration (दोन आधीच ठरलेले 81-grids). `leg_classifier_report.py` → `docs/reports/leg_classifier_g1.md` + 10 नमुना दिवस (screenshots).
- Dashboard चार्ट: "Legs" checkbox (डीफॉल्ट बंद) — impulse गडद, pullback फिकट, range राखाडी; hover वर features + कारण. फक्त पूर्ण candles.
- `price_action/level_strength.py` (T2.4–T2.6):
  - ताकद features (departure, base, touches, recency, round-number, TPO, role reversal, origin leg);
  - `strength_score` (touches वजन 0 — चिन्ह T3 मध्ये data वरून);
  - approach नियम (REACTION / BREAK candidate);
  - घटना SWEEP / BREAK / BREAK_CASCADE / FAILED_BREAKOUT (`known_at` = break + n_reclaim).

**Tests:** full suite 2427 हिरवा (legs 18, level_strength 10 नवे).

**निर्णय (कारणासह):**
- **G1 वर थांबलो नाही** (वापरकर्त्याची रात्रीची सूचना): 10 नमुना दिवसांचे चार्ट report मध्ये तयार ठेवले.
- Efficiency च्या denominator मध्ये H−L ऐवजी true range (आदल्या close सह). कारण: overnight gap मुळे efficiency > 1 होत होती.
- "spread < 1" चा अर्थ = pullback candles ची सरासरी range ÷ impulse ची सरासरी range < 1. कारण: median_range शी तुलना केल्यावर (mean > median) अट जवळजवळ कधीच पूर्ण होत नव्हती.
- `MIXED_PULLBACK` लेबल जोडलं: ना healthy ना dangerous. कारण: spec चे 6 लेबल्स मधल्या pullbacks ना जागा देत नाहीत.
- FVG मोजायला किमान आकार `fvg_min` (× median_range) — pullback grid मध्ये calibrate.
- k_swing = 3, k_internal = 1.5, N = 20 आधीच ठरवले (grid मध्ये नाहीत). Calibration TF = NIFTY 15M (bots चा मुख्य TF). H = 8 bars.
- दोन grids (impulse 81 + pullback 81); प्रत्येकी ≤ 81 नियम पाळला. Impulse निवड pullback grid आधी निश्चित.
- Pullback grid मध्ये एकही trial अट (HEALTHY आणि DANGEROUS दोन्ही ≥ 10%) पूर्ण करत नाही ⇒ डीफॉल्ट ठेवले; नियम post-hoc सैल केले नाहीत.
- Level touches: zone सोडेपर्यंतचे उगमानंतरचे bars departure मानले, touch नाही.

- Independent review (subagent): blocker नाही. केलेल्या दुरुस्त्या:
  - depth आता खरा किंमत-retrace — आधी legs च्या वेगवेगळ्या mr मुळे mixed units होते;
  - KEY/ROUND zone चा role reversal उगमावेळच्या बाजूवरून;
  - Daily चार्टवर आजचा अपूर्ण candle 15:30 पूर्वी वगळला;
  - `</script>` escape; NaN median fallback; outcomes मध्ये n_median param.
  - Nit जसा ठेवला: `fvg_min` pullback grid मध्ये impulse FVG मोजणीवरही परिणाम करतो — फक्त IS मध्ये, grid आधीच ठरलेला असल्याने बदलला नाही.
  - Nit जसा ठेवला: FAILED_BREAKOUT नंतर reclaim खिडकीतले sweeps नोंदवत नाही.

**निकाल (दुरुस्तीनंतर):**
- STRONG वि. WEAK impulse: IS t = 1.62, VAL ≈ 0 ⇒ पुरावा नाही.
- ~96% pullbacks DANGEROUS (spec चे OR-नियम).
- HEALTHY दुर्मिळ (IS n = 22, resume 90.9% वि. 65.8%).

**उघडे प्रश्न (सकाळी):**
- G1 — लेबल्स चार्टवर पटतात का?
- "धोकादायक = ≥ 2 अटी" हे नवं गृहीतक तपासायचं का?

## 2026-10-06 · T3 — Leg आणि Level validation (Osler पद्धत) → **G2 वर थांबलो**

**काय केलं:**
- `price_action/level_validation.py`: bounce outcome, random zones, option breach, numpy logistic.
- `leg_level_validation.py` → `docs/reports/leg_level_validation.md` (+ CSV/JSON).
- Level engines: sr_dynamic (15M, ±0.10% band), SR V3 (15M+1H+D), OE zones (OE timeline as-of), OE + T2.4 ताकद ≥ IS median.
  प्रत्येक दिवशी open पासून ±1.5% मधले zones. प्रत्येक खऱ्या zone मागे 3 random zones (एकूण ~4.5 लाख).
- Leg tests (label-shuffle permutation, 2000), PBO (leg grid 81 आणि engines 4), DSR, option-seller (5 सत्र).

**Tests:** 2427 → 2435 (level_validation 8: bounce नियम, random zones, option breach, logistic, verdict, holdout guard, accuracy स्तंभ).

**निर्णय (कारणासह):**
- फक्त NIFTY: BANKNIFTY/MCX चा offline डेटा repo मध्ये नाही.
  Upstox वरचा 2024-04 नंतरचा डेटा sealed holdout आहे, आणि त्याआधीचा sandbox मधून मिळत नाही. Runner मध्ये 2024-03-31 नंतरचा डेटा hard-cut.
- Bounce व्याख्या आधीच ठरवली: पहिल्या स्पर्शानंतर 8 bars मध्ये close-अंतर ≥ 1 × median range, दूरच्या कडेपलीकडे close होण्याआधी. स्पर्श-bar स्वतः मोजत नाही.
- Random अंतर-वितरण त्या engine च्या **IS** खऱ्या अंतरांवरून (VAL चा वापर नाही).
- Option-seller: प्रत्येक (engine, दिवस, बाजू) साठी किंमतीच्या सर्वात जवळचा मजबूत zone. कारण: एकाच दिवशी अनेक सारख्या strikes ने आकडे फुगू नयेत; हा बदल वेगासाठीही आवश्यक होता.
- Verdict नियम: PBO > 0.05 ⇒ REJECT; कोणत्याही गटाचा n < 30 ⇒ REVIEW; IS edge > 0 आणि z ≥ 2 आणि VAL edge > 0 ⇒ KEEP.
- Engines मधल्या निवडीचा PBO वेगळ्या ओळीत दिला, प्रत्येक engine वर लावला नाही (review नुसार). Engine वि. random ⇒ REVIEW.
- हाताने लिहिलेले निष्कर्ष `leg_level_validation_conclusions.md` मध्ये. कारण: runner पुन्हा चालवल्यावर ते पुसले जाऊ नयेत.
- Independent review: blocker नाही. केलेल्या दुरुस्त्या: random break दर + zone-रुंदी स्तंभ, touches-buckets engine-निहाय, leg rows ची एकके. z च्या स्वतंत्रता-गृहीतकाची मर्यादा अहवालात नोंदवली.

**निकाल:**
- एकाही level engine ला random पेक्षा edge नाही (|z| < 1.8 ⇒ REVIEW). Engine निवड overfit (PBO 0.18).
- T2.4 ताकद मदत करत नाही. Option strikes zone मुळे सुरक्षित नाहीत.
- STRONG/WEAK leg REJECT. HEALTHY pullback REVIEW (नमुना लहान).
- OE मध्ये न-retest zones कमी टिकतात (27% वि. 40–47%).

**CI नोंद:** PR #243 चा एक CI run IST मध्यरात्री (23:59→00:05) fail झाला; त्याच code वरचा re-run हिरवा.
Log blob मिळत नाही ⇒ कोणती test ते कळलं नाही. Date-rollover वर अवलंबून असलेली एखादी जुनी test असावी — **उघडा प्रश्न**.

**G2 — तुमचा निर्णय हवा:**
- (1) T4 (one level truth / approach gate / credit-spread filter) थांबवायचा का? माझी शिफारस: होय — पुरावा नाही.
- (2) HEALTHY-pullback आणि "retested zone" ही दोन गृहीतकं मोठ्या डेटावर तपासायची का?
- (3) T5 (order-type तपासणी, फक्त अहवाल + default-off marketable-LIMIT) G2 पासून स्वतंत्र आहे — सुरू करायचा का?

## 2026-10-06 · T5 — Order type तपासणी (फक्त अहवाल + default-off code) → **G3 वर थांबलो**

**संदर्भ:** वापरकर्त्याने "Continue" सांगितलं, पण G1/G2 चे निर्णय दिले नाहीत. T4 ला G2 मंजुरी लागते आणि माझी शिफारस T4 थांबवण्याची आहे ⇒ T4 सुरू केला नाही.
त्याऐवजी G2 वर अवलंबून नसलेला T5 केला: अहवाल + default-off module, कोणत्याही LIVE मार्गाला जोडलेला नाही.

**काय केलं:**
- `docs/reports/t5_order_types.md`: MARKET/SL-M वापराच्या 8 जागा आणि धोका, नियमांचा सारांश (स्रोतांसह), VPS वर read-only पडताळणी.
- `order_execution.py`: `apply_order_style` (MARKET डीफॉल्ट / MARKET_PROTECTION / MARKETABLE_LIMIT), `run_marketable_limit` (partial fill, cancel, retry, वाढता buffer), tick-गोलाई.
- `tests/test_order_execution.py` (11).

**निर्णय (कारणासह):**
- Module कुठेही जोडला नाही. कारण: G3 — LIVE/order-type बदल वापरकर्त्याच्या मंजुरीनंतरच.
- Upstox docs sandbox मधून उघडत नाहीत (egress block) ⇒ search सारांशांवर आधारित. अहवालात "VPS/ docs वर पडताळा" असं स्पष्ट लिहिलं.
- Exit साठी marketable-LIMIT ची शिफारस नाही (exit उशिरा होण्याचा धोका). त्याऐवजी `market_protection` स्पष्ट भरण्याची शिफारस.

- Independent review: blocker नाही. Wiring-आधीच्या दुरुस्त्या केल्या:
  - cancel अयशस्वी / अनिश्चित ⇒ retry थांबवतो, `unresolved_order_id` देतो (नाहीतर दुहेरी position चा धोका);
  - over-fill वेगळा नोंदवतो;
  - BUY/SELL validation; सरासरी किंमत फक्त किंमत-माहीत fills वर;
  - poll किमान 0.2s; बारीक tick गोलाई; VPS SQL read-only (`mode=ro`).
- **Midnight CI flake शोध:** libfaketime ने IST 00:00:30 पासून suite चालवला. पहिल्या ~65% tests मध्ये (fake वेळ 00:00–00:25 IST) एकही failure नाही.
  उरलेला भाग faketime खाली खूप हळू (≈ तासभर) ⇒ थांबवला. **उघडाच** — पुढचा CI flake आल्यास त्या run चा test-नाव पाहणं हा मार्ग.

**उघडे प्रश्न (G3):** VPS order_log मोजणी; `market_protection` स्पष्ट भरायचा का; Stocko चा 0; MCX API orders ची सद्यस्थिती.

## 2026-10-06 · G3 अंमलबजावणी — order सुरक्षा (वापरकर्त्याचे निर्णय)

**वापरकर्त्याचे निर्णय (सकाळ):**
- G1: STRONG/WEAK labels तपासायची गरज नाही (REJECT). HEALTHY/DANGEROUS REVIEW मध्ये.
- G2: T4 थांबवला. पुढे फक्त report-only: (a) positional strike breach, (b) HEALTHY/DANGEROUS मोठा नमुना, (c) retested वि. fresh.
- G3: VPS पुरावा — 2026-09-10 ची NIFTY LIVE spread entry (MARKET, market_protection शिवाय) COMPLETE ⇒ तातडी नाही.

**काय केलं (हा PR):**
- `order_safety.py` + `trading_engine.py` wiring:
  - (a) `order_market_protection_pct`: डीफॉल्ट None ⇒ field पाठवत नाही (**जुनं वर्तन**). 1–25 ⇒ entry, SL/Target/TSL exit, manual close, auto-reverse मधल्या सर्व MARKET/SL-M orders मध्ये.
  - (b) Exit अपयश इशारा **डीफॉल्ट ON** (फक्त सूचना): leg-निहाय भरले/न भरले, "POSITION अजून उघडी आहे", partial-exit धोका, पहिल्या आणि दर 5व्या सलग अपयशाला, आणि अखेर बंद झाल्यावर ✅.
    आधी दर cycle ला साधा संदेश जायचा.
  - (b) त्याच cycle मध्ये retry: फक्त **पूर्ण** अपयशावर, setting `exit_retry_on_fail` **डीफॉल्ट OFF**. Partial exit वर कधीच retry नाही.
- `order_execution.py`: MARKETABLE_LIMIT फक्त `purpose="entry"` (exit ⇒ ValueError). अजूनही कुठेही जोडलेला नाही.
- Dashboard sidebar "🧾 Order सुरक्षा" expander. कारण: sidebar दर rerun ला `engine_settings.json` पूर्ण पुन्हा लिहितो, त्यामुळे हाताने टाकलेला setting पुसला गेला असता. डीफॉल्ट मूल्ये वरीलप्रमाणे.
- Stocko ला हात लावलेला नाही. MCX API orders चा प्रश्न MCX LIVE आधी पुन्हा.

**Tests:** 2446 → 2466 (order_safety 20: डीफॉल्ट वर्तन (तीच list), throttle, process-पार मोजणी, HTML escape, partial इशारा, निश्चित-अपयशावरच retry, entry/exit market_protection, खरा settings loader; order_execution +1).

**Independent review (subagent):**
- BLOCKER (opt-in retry): open/unknown legs किंवा timeout लाही "पूर्ण अपयश" मानलं जात होतं ⇒ दुहेरी exit चा धोका.
  - दुरुस्ती: retry फक्त सर्व legs rejected/cancelled असताना, किंवा order_ids शिवाय स्पष्ट 4xx असताना.
  - Retry आधी trade अजून OPEN आहे का तपासतो, आणि नवीन correlation ids वापरतो.
- SHOULD-FIX, सर्व केले:
  - अपयश-मोजणी `data/exit_fail_counts.json` मध्ये (process-पार; gitignored);
  - Telegram HTML escape;
  - इशारा तयार/पाठवणं try मध्ये (exit loop थांबू नये).
- Nits: sidebar मध्ये अवैध मूल्य clamp, widget keys prefix, खऱ्या settings-loader ची test, डीफॉल्ट exit तीच list ची test.
- उघडं: Fyers/Shoonya/Stocko adapters `market_protection` key दुर्लक्षित करतात का हे तपासलेलं नाही. Setting डीफॉल्ट बंद; Upstox व्यतिरिक्त broker वर चालू करू नये.
- Re-review (दुसरा subagent): मूळ BLOCKER दुरुस्त. आणखी एक SHOULD-FIX केला: `cancelled` पण अंशतः भरलेला leg (filled_quantity > 0) ⇒ आता "पूर्ण अपयश" नाही ⇒ retry नाही.
  Nits केले: `partial_order_ids` असल्यास retry नाही; counts temp-file process-id सह; retry तपासणी try मध्ये; trade आधीच बंद असेल तर "उघडी" इशारा पाठवत नाही.

**महत्त्वाचा निष्कर्ष (तुमचा निर्णय हवा):** partial exit (काही legs भरले, काही नाकारले) झाल्यास trade OPEN राहतो.
पुढच्या monitor cycle ला **सर्व** legs चा close order पुन्हा जातो ⇒ आधीच बंद झालेल्या leg वर उलटी नवी position उघडू शकते.
हे जुनं वर्तन आहे. ते बदलणं म्हणजे LIVE exit logic बदल ⇒ केलं नाही; आता इशाऱ्यात हा धोका स्पष्ट लिहिला जातो.
प्रस्ताव: partial exit नंतर फक्त न भरलेले legs पुन्हा पाठवणे (भरलेल्या legs ची नोंद DB मध्ये). Default-off setting सह, PAPER/fake-broker tests सह.

## 2026-10-06 · G2 नंतरच्या report-only चाचण्या (वापरकर्त्याचा निर्णय (a)(b)(c))

**काय केलं:** `g2_followups.py` → `docs/reports/g2_followups.md` (+ CSV). NIFTY 2015 → 2024-03; holdout hard-cut.
- (a) Positional short strike: SR V3 (day+week), sr_dynamic (daily), OE 1d.
  - दर दिवशी प्रत्येक बाजूचा 0.5–4% मधला सर्वात जवळचा level; strike = दूरची कड; 5 सत्र hold.
  - Random-दिवस baseline (तेच % अंतर, तीच बाजू, तोच period). अंतर-buckets वेगळे.
- (b) HEALTHY वि. DANGEROUS, 15M आणि 1H, T2.3 चा calibrated LegConfig (नवीन tuning नाही), permutation.
- (c) Retested वि. fresh (OE): random zones चे touches त्याच उगम-खिडकीत मोजून touches-bucket-निहाय तुलना.

**Tests:** +3 (`tests/test_g2_followups.py`).

**निर्णय (कारणासह):**
- (a) मधले engines आणि अंतर-buckets आधीच ठरवले. दर दिवशी प्रत्येक बाजूला एकच strike (सर्वात जवळचा level), कारण एका दिवशी अनेक सारख्या strikes ने नमुना फुगू नये.
- (b) मध्ये नवीन व्याख्या (उदा. "≥ 2 धोके") वापरली नाही — वापरकर्त्याची मंजुरी नाही; post-hoc निरीक्षण फक्त गृहीतक म्हणून नोंदवलं.
- BANKNIFTY: सार्वजनिक third-party डेटा उपलब्ध (Kaggle/GitHub); download केला नाही (गुणवत्ता अनिश्चित; holdout भाग) — निर्णय वापरकर्त्याचा.

**निकाल:**
- (a) level-आधारित strikes random इतक्याच तुटतात; breach अंतरावर अवलंबून.
- (b) HEALTHY नमुना वाढला नाही (15M IS 22, 1H IS 4).
- (c) random baseline सह retested-zone फायदा नाहीसा. Fresh OE zones random पेक्षा कमकुवत दिसतात (IS cluster z −4.65; VAL −1.12 ⇒ फक्त निरीक्षण).
- Review दुरुस्त्या:
  - SR V3 PDH/PDL एक दिवस जुने होते → सत्र-अखेर stamp.
  - साधा two-proportion z → महिना-cluster bootstrap (rows स्वतंत्र नाहीत).
  - Hold-window IS/VAL सीमा ओलांडत नाही.
  - OE 1d मधले BROKEN zones वगळले.
  - Random zones साठी "उगमानंतरचा पहिला overlap वगळणे" नियम तसाच ठेवला (दोन्ही बाजूंना सारखा, परिणाम नगण्य).
- एकूण: कोणताही gate/engine चालू करण्याची शिफारस नाही.

**उघडे प्रश्न:**
- "NOT DANGEROUS वि. DANGEROUS" हे नवं, आधीच ठरवलेलं गृहीतक तपासायचं का?
- BANKNIFTY डेटा वापरायचा का?
- Partial-exit नंतर फक्त न भरलेले legs पाठवण्याचा प्रस्ताव (G3 नोंद)?

## 2026-10-06 · Partial-exit safety fix (वापरकर्त्याचा निर्णय: flag शिवाय)

**काय केलं:**
- `order_safety.py`:
  - exit-state (`data/exit_state.json`, gitignored): मागच्या अयशस्वी प्रयत्नात काय पाठवलं, तो निश्चित no-fill होता का, कोणते orders pending होते.
  - `plan_exit_resend`, `blocked_message`.
- `trading_engine._send_exit_orders`: `manage_open_trades` (same-cycle retry सकट) आणि `close_trade_manually` दोन्ही याच मार्गाने.
- पहिला प्रयत्न आणि PAPER: जुनंच वर्तन (सर्व legs, तीच list).

**नियम (पुढचा प्रयत्न, LIVE):**
1. मागचे pending order ids → Upstox order details. Terminal नसतील / मिळाले नाहीत ⇒ थांबा.
2. Broker positions (ताजे fetch) → प्रत्येक leg ची net qty (instrument + product):
   - 0 ⇒ leg वगळा;
   - पूर्ण ⇒ पूर्ण qty;
   - कमी ⇒ फक्त उरलेली qty;
   - गहाळ / उलटी बाजू / जास्त qty / MCX अंशतः ⇒ थांबा.
3. Positions मिळाल्या नाहीत (Upstox अपयश, किंवा Fyers/Shoonya/Stocko adapters ज्यांना positions API नाही) ⇒ मागचा प्रयत्न निश्चित no-fill असेल तरच **तेच** orders पुन्हा, नाहीतर थांबा.
4. सर्व legs flat ⇒ काही पाठवत नाही (reconciliation पुढच्या cycle ला DB बंद करते).

**निर्णय (कारणासह):**
- "थांबा" इशारा `exit_fail_alert` setting बंद असतानाही जातो — सुरक्षा-इशारा; वापरकर्त्याने "Telegram alert द्या" सांगितलं.
- त्याची मोजणी वेगळी (`<trade>#blocked`): पहिल्या प्रसंगाला लगेच, मग दर 5व्या cycle ला.
- गहाळ leg = बंद नाही (reconciliation चाच नियम).
- जास्त qty ⇒ दुसरा trade त्याच instrument वर असू शकतो ⇒ आंधळेपणाने बंद करणं धोकादायक ⇒ थांबा.
- MCX: positions मधली qty units की lots ते अस्पष्ट ⇒ पूर्ण leg (units किंवा lots जुळले) चालेल, अंशतः ⇒ थांबा.
- Adapters (Fyers/Shoonya/Stocko): partial नंतर आता थांबून इशारा देतात (आधी सर्व legs पुन्हा जायचे).
- उरलेला धोका: पहिल्या प्रयत्नाचा प्रतिसाद order_ids शिवाय हरवला (network) आणि order नंतर भरला, तर positions मध्ये तो दिसेपर्यंत दुहेरी exit शक्य. MARKET orders ~सेकंदात भरतात आणि पुढचा cycle 60s नंतर ⇒ शक्यता कमी. order-book तपासणी पुढे जोडता येईल.

**Tests:** `tests/test_partial_exit_safety.py` (+21):
- partial-fill: पुढच्या cycle ला फक्त hedge; leg मधली अंशतः qty;
- double-retry: रोज फक्त उरलेला leg;
- broker-mismatch: उलटी बाजू / जास्त qty / गहाळ;
- pending → थांबा → terminal झाल्यावर पुढे;
- positions नाहीत; throttle; PAPER अबाधित; manual close.

**VPS:** वापरकर्ता 15:30 नंतर pull करणार.

**स्वतंत्र review नंतरच्या दुरुस्त्या (त्याच PR मध्ये):**
- **In-flight नोंद:** पाठवण्याआधीच नोंद होते. Process मध्येच थांबली, प्रतिसाद हरवला किंवा state save अयशस्वी झाला तरी पुढचा प्रयत्न "पहिला" समजला जात नाही.
- **Order book तपासणी:** मागच्या प्रयत्नाचा निकाल अज्ञात असेल (timeout, order_ids नाहीत, in-flight), तर Upstox order book (`fetch_order_book`, GET /v2/order/retrieve-all) मध्ये तेच instrument + बाजू + tag चे orders (प्रयत्नाच्या वेळेपासून) शोधले जातात.
  - Non-terminal order सापडला, किंवा order book मिळाला नाही ⇒ थांबा.
  - ⚠️ हा endpoint sandbox मधून तपासता आला नाही (Upstox docs प्रमाणे).
- **Shared instrument:** दुसरा OPEN LIVE trade त्याच instrument वर असेल तर broker net qty कोणाची ते कळत नाही ⇒ थांबा. फक्त पुढच्या (resend) प्रयत्नात लागू; पहिला प्रयत्न जुनाच.
- **Locks:**
  - `exit_state.json` fcntl lock खाली.
  - प्रत्येक trade साठी non-blocking exit-lock: monitor आणि manual close एकाच वेळी पाठवत नाहीत. दुसरी process पाठवत असेल ⇒ "busy", काही पाठवत नाही.
  - Lock मिळाल्यावर trade OPEN आहे का पुन्हा तपासलं जातं.
- **आधीच्या दिवसाचा प्रयत्न:** DAY orders संपलेले असतात ⇒ pending/book तपासणी नाही, थेट positions.
- **खराब state नोंद** ⇒ थांबा.
- **अनपेक्षित चूक** ⇒ 'blocked' + इशारा. Monitor loop आणि इतर trades चालू राहतात.
- **Realized P&L:** आधीच्या अयशस्वी प्रयत्नांतले प्रत्यक्ष fills साठवले जातात आणि शेवटी realized P&L त्यावरून मोजला जातो.
- **Reconciliation:** त्याने trade बंद केला तर exit-state साफ होते.
- **Operator escape:** `clear_exit_state.py --trade-id … [--clear | --mark-closed]`. Blocked इशाऱ्यात ही ओळ दिसते. Adapter trades आणि कायमचे अडकलेले trades यासाठी.
- **दुसऱ्या review नंतर:**
  - (BLOCKER) exit-state आता DB मध्ये CLOSED + commit झाल्यानंतरच साफ होते. मधल्या वेळेत manual close आलं, तर ते in-flight नोंद पाहतं, order book / positions तपासतं आणि flat पाहून काही पाठवत नाही.
  - Order book मध्ये tag ने गाळणं काढलं: Upstox tag कापू शकतो, आणि जास्त जुळणं ही सुरक्षित बाजू.
  - State फाईल वाचता/लिहिता आली नाही ⇒ fail-closed. पहिला प्रयत्नही थांबतो + इशारा; खराब फाईल ओव्हरराइट होत नाही.
  - Book-window साठी पाठवण्याची (in-flight) वेळ ठेवली जाते.
  - `at` नसेल तर आजचाच प्रयत्न मानला जातो.
  - Lock फाईल handle leak बंद केला.
  - Tests +6: manual close race, tag mismatch, जुने orders, खराब फाईल, खरी flock contention, in-flight वेळ.
- **वापरकर्त्याचा निर्णय (merge आधी):**
  - exit_state.json वाचता न आल्याने exits blocked असतील तर "EXITS BLOCKED" इशारा प्रत्येक cycle ला येतो. Throttle 5 मिनिटं (सर्व trades मिळून एक), आणि इशाऱ्यात नेमकी `clear_exit_state.py --reset-file` command असते.
  - `--reset-file` खराब फाईल `.corrupt-<वेळ>` नावाने बाजूला ठेवतो.
  - Runbook: `PRE_LIVE_CHECKLIST.md` §7 (3 ओळी).
- **उरलेलं (बदललं नाही):** monitor वि. manual close मध्ये DB-स्तरावर atomic "CLOSING" claim नाही. Exit-lock + lock नंतरची OPEN तपासणी हा धोका बंद करतात; DB claim हा मोठा बदल ⇒ पुढे गरज वाटल्यास.

**Tests:** +11 (एकूण 32):
- crash before save → order book;
- timeout/no ids;
- shared instrument;
- आधीच्या दिवसाचा pending;
- corrupt state;
- lock busy;
- internal error;
- fills मधून P&L;
- reconciliation clear;
- adapter path;
- CLI.

## 2026-10-06 · Strike breach probability model (NIFTY) + BANKNIFTY स्वतंत्र चाचण्या + pre-registration

**काय केलं:**
- **`strike_breach_model.py` (report-only, level filter नाही):**
  - Strike अंतर z = |ln(K/open)| ÷ (σ20·√h) मध्ये मोजलं. ATR14 version वेगळं.
  - घटक: ADX regime × बाजू, OE StructureTracker("1d"), ln h + 0DTE, entry weekday, बाजू.
  - Numpy IRLS logistic (ridge 1, निश्चित). NIFTY IS वर fit, VAL वर calibration.
  - Coefs वर महिना-cluster bootstrap CI.
  - Calibrated "X% धोका ⇒ किती दूर" तक्ता: DTE 0–4 × put/call, close आणि touch.
  - गोठवलेले coefs: `docs/reports/strike_breach_model_coef.json`.
  - अहवाल: `docs/reports/strike_breach_model.md`.
- **`docs/reports/preregistered_hypotheses.md`:** BANKNIFTY चालवण्याआधी लिहिलेलं.
  - H-PB1: NOT-DANGEROUS वि. DANGEROUS, 15M.
  - H-POS1: BANKNIFTY positional, levels वि. random.
  - H-BR1: NIFTY-fit model BANKNIFTY वर calibrated आहे का.
- **`banknifty_positional.py`:** loader + H-POS1 runner.
- **`research/banknifty_independent_test.py`:** VPS वर चालवायची script.
  - फक्त CSV वाचते. Network, orders आणि DB write नाही.
  - stdout वर ≤ 40 ओळी; CSVs `data/research/banknifty_results/` मध्ये. `data/research/` gitignored.

**निर्णय (कारणासह):**
- **H-PB1 daily वर चालवलं नाही:** ते 15M साठी नोंदवलं आहे. Daily legs वेगळ्या TF चे; तिथे चालवणं म्हणजे नवीन, न नोंदवलेलं गृहीतक. Script हे स्पष्ट छापते.
- **BANKNIFTY साठी model पुन्हा fit केलं नाही:** NIFTY चे गोठवलेले coefs वापरले. त्यामुळे BANKNIFTY चे IS आणि VAL दोन्ही खरे out-of-sample आहेत.
- **Weekly expiry:** NIFTY सारखाच गुरुवार नियम ठेवला, पद्धत एकच राहावी म्हणून. BANKNIFTY ची प्रत्यक्ष expiry 2023-09 पासून बुधवार होती; हा फरक नोंदवला.
- **H-POS1 डेटा-स्रोत:** niftyindices वरून वापरकर्त्याच्या Upstox V3 CSV वर बदलला. चाचणीआधी नोंदवलं; पद्धत तशीच.
- **Synthetic run मधली चूक (दुरुस्त):** loader ISO तारखा day-first वाचत होता (2021-09-01 → 9 Jan). आता आधी ISO, नाहीतर day-first. Tests सह.

**NIFTY निकाल (`strike_breach_model_conclusions.md`):**
- अंतर z हीच मुख्य माहिती. Regime/वार/structure जोडून log-loss फक्त 0.3298 → 0.3289.
- ATR-आधारित model थोडं चांगलं: 0.3243.
- VAL calibration चांगलं.
- 10% expiry-close धोका ⇒ z ≈ 1.05 (DTE 0) ते 1.3 (DTE 4).

**Tests:**
- `test_strike_breach_model.py` (+7)
- `test_banknifty_positional.py` (+7)
- `test_banknifty_independent_test.py` (+4)

## 2026-10-06 · Major Level (Trader's Eye) engine v1 — टप्पा (a) ची तयारी (report-only, gate नाही)

**काय केलं:**
- `docs/reports/ground_truth_levels.csv`: वापरकर्त्याचे हाताने काढलेले levels. NIFTY 15m, GOLD/COPPER 30m, SILVER 30m (+ उतरती trendline; anchor तारखा अंदाजे).
- `price_action/major_levels.py`:
  - HTF (240 मिनिट, सत्राच्या सुरुवातीपासून; NSE 09:15, MCX 09:00), फक्त पूर्ण bars.
  - Fractal pivots (r = 2), confirmed झाल्यावरच.
  - Prominence: दोन्ही बाजूंना ≥ s × median HTF range. यामुळे range च्या आतले minor swings वगळले जातात.
  - Clusters: gap ≤ tol, span ≤ 2·tol; tol = k × median range.
  - Score = reactions + 2 × role-reversal + 1 × range-edge.
  - Level = wick extremes चा median, किंवा extreme (grid).
  - 2–4 levels, एकमेकांपासून > 2·tol.
  - Trendline: ≥ 3 pivots ± tol, पहिल्या anchor नंतर एकही HTF close पलीकडे नाही.
  - `match_levels`: precision/recall ±0.15%.
- `research/major_levels_eval.py`:
  - `--export` (VPS; फक्त candles वाचतो) → `data/research/major_levels_candles/` (gitignored).
  - `--eval`:
    - grid 3 lookback × 3 k × 2 min_react × 2 prominence × 2 price-mode = **72 संयोजनं** (≤ 81);
    - निवड: चार charts वर सरासरी F1. बरोबरी ⇒ लहान lookback, लहान k;
    - leave-one-chart-out F1 (प्रामाणिक अंदाज);
    - overlay PNGs आणि CSVs → `docs/reports/major_levels/`.

**निर्णय (कारणासह):**
- Sandbox मधून Upstox ला पोहोचता येत नाही (403), आणि repo मध्ये 2024-03 नंतरचा NIFTY/MCX डेटा नाही. म्हणून candles VPS वर काढले जातात आणि **वेगळ्या branch** वर (git worktree मधून) push होतात. चालू checkout आणि bots ला धक्का लागत नाही. Overlays इथे बनवले जातात.
- Weights (role reversal 2, edge 1) आधीच ठरवले, grid मध्ये नाहीत. 4 charts / 10 levels वर जास्त parameters ⇒ overfit. म्हणून LOCO नोंदवला.
- MCX साठी front-month contract (`resolve_symbol` डीफॉल्ट). वापरकर्त्याचा chart वेगळ्या contract चा असेल, तर levels जुळणार नाहीत; export contract चं नाव छापतं.
- SILVER trendline जुळणी = त्याच प्रकारची algo रेषा, जिचे anchors ≥ 2 GT तारखांपासून ±1.5 दिवसांत.
- टप्पा (b) (NIFTY IS/VAL edge test) वापरकर्त्याने overlays पाहिल्यानंतरच.

**स्वतंत्र review नंतर:**
- **Holdout धोरण:** 2026 चे NIFTY/MCX candles holdout काळातले आहेत. ते **वेगळ्या data branch** वर राहतील आणि main मध्ये कधीच merge होणार नाहीत. ते फक्त टप्पा (a) मध्ये, वापरकर्त्याच्या स्पष्ट विनंतीने, डोळा-जुळणीसाठी वापरले जातात. पुढच्या G4 holdout चाचणीतून NIFTY 2026-07 → 2026-10-06 हा भाग वगळावा, कारण engine चे params त्यावर निवडले गेले.
- `asof`: फक्त संपलेले bars (timestamp + TF ≤ asof). आधी एका bar चा lookahead होता.
- MCX सत्र-अखेर तारखेनुसार: नोव्हेंबर–मार्च 23:55.
- Lookback दिवसाच्या सुरुवातीपासून घेतला जातो.
- Edge ओळख index ने होते.
- Role-reversal levels क्रमवारीत आधी (नियम 4).
- 2 पेक्षा कमी levels असतील तर range edges "weak" म्हणून भरले जातात (`below_min`).
- Trendline गणित chart-TF bar-index वर, anchor = प्रत्यक्ष wick चा bar. Overlay engine ने fit केलेली रेषाच काढतो.
- MCX contract: bot चा आणि सर्वात जवळचा, दोन्ही export होतात. Eval मध्ये ज्याच्या किंमत-पट्ट्यात GT levels बसतात तो निवडला जातो (डेटा-निवड, params fitting नाही).
- Candles (symbol, tf) ने keyed.

**Tests:** `tests/test_major_levels.py` (+18). यात non-circular planted-level चाचणी, asof सीमा, MCX सत्र, min_levels, role-reversal क्रम, prominence, extreme mode, trendline violation आणि LOCO.

## 2026-10-06 · Pullback Credit Spread — योजना (नियम 1; spec: `docs/PULLBACK_CREDIT_SPREAD_PROMPT.md`)

**PR यादी (एक PR = एक टप्पा; थांबा फक्त G1/G2/G3):**
- **PCS-1 core (हा PR)** — `pullback_credit_spread/settings.py` + `core.py`:
  - सर्व settings एका schema मध्ये: 11 विभाग, मराठी label + ⓘ मदत, min/max/पर्याय, डीफॉल्ट. Mode डीफॉल्ट **OFF**; पर्याय फक्त OFF/PAPER.
  - Presets: Conservative/Balanced/Aggressive. Validation, diff (इतिहासासाठी), snapshot (trade सोबत).
  - Expiry: instrument master च्या तारखांवरून (वार hard-code नाही). आज expiry ⇒ पुढची; min_dte; monthly.
  - Strike step chain वरून. Short strike चे 5 modes + min/max distance guards; rounding नेहमी दूर बाजूला. Long strike (points/strikes).
  - Credit guards, lots (risk%, max_lots, event गुणक), capacity, blackout.
  - Exits: hard stop **सर्वात आधी**, मग target → spot stop → खरा break (false break वर नाही) → time exit.
- **PCS-2 signal pipeline** — `pullback_credit_spread/signal.py`, क्रमाने, प्रत्येक पायरीचं skip कारण:
  - blackout → trend (StructureTracker, trend_tf + HTF veto);
  - level (srv3 / major_levels / oe_zones, trend-दिशेचा);
  - pullback quality (`price_action/legs`);
  - logical reversal (`price_action/candles.evaluate_rejection`);
  - breakout guard (real break ⇒ idea रद्द);
  - expiry → strike → credit → lots.
  - No-lookahead (फक्त पूर्ण bars, HTF bar_end नंतर). MCX वर्तन अबाधित (MCX modules ला हात नाही; test).
- **PCS-3 dashboard** — नवीन पान "Pullback Credit Spread":
  - 11 expanders, एका column चा layout (mobile).
  - Presets; per-symbol settings (NIFTY/BANKNIFTY/SENSEX) + "सगळ्यांना लागू करा"; Reset.
  - Supabase `strategy_settings` (strategy "pullback_credit_spread") + नवीन change-history table.
  - Live preview (फक्त वाचन): expiry, strikes, credit, max loss, lots, ✅/❌ checklist.
  - → **G1:** mobile + desktop screenshots.
- **PCS-4 PAPER runner** (डीफॉल्ट OFF):
  - Orders: hedge-first + `order_safety` (market_protection, partial-exit fix).
  - Settings snapshot प्रत्येक trade सोबत.
  - Exits कधीच अडवत नाही.
- **PCS-5 backtest/replay** (तेच code):
  - NIFTY IS/VAL; premium model (मर्यादा अहवालात).
  - Random-entry baseline, sensitivity, PBO.
  - → **G2.**

**निर्णय (कारणासह):**
- **Level engine डीफॉल्ट `srv3`:** Major Level engine अजून ground truth शी पडताळलेलं नाही (टप्पा (a) चालू). प्रमाणित झाल्यावर डीफॉल्ट बदलण्याचा निर्णय वापरकर्त्याचा.
- **`adjustment_mode`:** setting आहे, पण v1 मध्ये फक्त `close` अंमलात. Roll/add_hedge नंतर, कारण त्यात नवीन order मार्ग आहेत.
- **DTE:** कॅलेंडर-दिवस (expiry − आज). आज expiry ⇒ min_dte काहीही असो, पुढची.

## 2026-10-06 · Pullback Credit Spread PCS-3 — dashboard पान + live preview → G1

**काय केलं:**
- `page_pullback_credit_spread.py` — BOTS विभागात नवीन पान "Pullback Credit Spread":
  - 11 expanders; प्रत्येक setting साठी मराठी label, ⓘ मदत, डीफॉल्ट दाखवलेला, min/max;
  - Presets;
  - per-symbol settings (NIFTY/BANKNIFTY/SENSEX) + "सगळ्यांना लागू करा";
  - Save, Reset (खात्री checkbox सह), बदलांचा इतिहास;
  - एका column चा layout.
- `pullback_credit_spread/store.py`:
  - Supabase `strategy_settings` ("pullback_credit_spread", symbol); पूर्ण dict बदलतो (merge नाही), म्हणजे Reset खरा.
  - नवीन `pcs_settings_history` table (CREATE IF NOT EXISTS).
  - Supabase नसेल तर स्थानिक फाईल (gitignored).
- `pullback_credit_spread/levels_source.py`: srv3 / major_levels → एकसारखं level स्वरूप. oe_zones v1 मध्ये उपलब्ध नाही (कारण दाखवतो).
- `pullback_credit_spread/preview.py` — "आत्ता signal आला तर", फक्त वाचन:
  - offline NIFTY डेटा (holdout-cut) निवडलेल्या वेळी, तोच `evaluate_entry`;
  - premium = Black-Scholes **अंदाज** (IV ≈ σ20; स्पष्ट लेबल);
  - trend नसेल तर दोन्ही बाजूंचा hypothetical plan.

**निर्णय (कारणासह):**
- Live (Upstox) preview PAPER runner (PCS-4) सोबत, कारण तिथेच chain/expiry/positions fetching लागतं. Sandbox मधून Upstox पोहोचत नाही, म्हणून G1 screenshots offline preview चे.
- Offline expiries = त्या आठवड्याचे गुरुवार (अंदाज). Live मध्ये instrument master.

**Tests:** `tests/test_pcs_dashboard.py` (+17: store local fallback/इतिहास/reset/LIVE नाकार, BS model, offline preview read-only + holdout, AppTest render + mode OFF, navigation, review नंतरचे 7). `test_app_navigation` अपडेट.

**स्वतंत्र review नंतर दुरुस्त्या (कारणासह):**
- दुसऱ्या पानावर जाऊन परत आल्यावर Streamlit widget मूल्यं पुसतो, त्यामुळे Save जुनी/चुकीची मूल्यं साठवू शकत होता. म्हणून मूल्यांची widget-बाहेरची प्रत (`pcs_values`) ठेवली आणि हरवलेली मूल्यं परत भरली. Test आधी फेल होतो, दुरुस्तीनंतर पास होतो.
- Supabase मिळालं पण save फेल झालं, तर source "error" + rollback होतो. आधी अशा वेळी गुपचूप स्थानिक फाईलमध्ये साठवलं जायचं; पण load नंतर जुनी Supabase नोंद वाचतो, म्हणून ते चुकीचं होतं. स्थानिक fallback आता फक्त connection नसतानाच वापरला जातो.
- Validation चुका असताना Save बंद; इतिहासासाठी नावाचं input.
- "सगळ्यांना लागू करा" आता `mode` / `symbol_enabled` कॉपी करत नाही, म्हणजे चुकून BANKNIFTY/SENSEX PAPER होणार नाहीत.
- इतिहास `st.cache_data` (30s) मध्ये; save/reset नंतर cache साफ. History table DDL प्रत्येक process मध्ये एकदाच. Local file लिहिताना `mkstemp` + lock.
- Preview मध्ये:
  - intraday resample 09:15 ला anchored;
  - BS वेळ trading-year (/252) मध्ये;
  - त्या तारखेचा NIFTY lot (2021-07→2024-04 = 50), जो बदलता येतो;
  - exception आल्यास पान क्रॅश होत नाही.
- दुसऱ्या review नंतर (2 Medium + Low):
  - Save नंतर widgets store मधून पुन्हा भरत नाही. आधी अयशस्वी save नंतरच्या retry मध्ये बदल पुसले जायचे आणि खोटं "0 बदल साठवले" यश दिसायचं; यशस्वी save नंतरचा पहिला बदल पण हरवायचा.
  - पान बदलल्यावर निवडलेला symbol टिकतो.
  - Supabase वाचन फेल ⇒ source "error", Save/Reset बंद, "पुन्हा वाचा" बटण. जुन्या/डीफॉल्ट मूल्यांनी खरी नोंद overwrite होत नाही.
  - DDL flag फक्त commit यशस्वी झाल्यावर लागतो. Reset अयशस्वी झाल्यास error दिसतो.
  - इतिहासातील old/new str मध्ये (Arrow चूक टाळतो).
  - Offline expiries 10 आठवडे (monthly + मोठा min_dte).
  - 2015-11 पूर्वी lot 25.
  - डेटा load अपयश cache होत नाही.


## 2026-10-06 · Elliott Pullback Credit Spread — E0: plan, data धोरण, VPS data scripts

**Spec:**
- `docs/ELLIOTT_WAVE_SPEC.md` हाच strategy logic चा एकमेव प्रमाण. त्यातला विभाग 14 अंतिम.
- प्रक्रिया: `docs/ELLIOTT_MASTER_PROMPT.md`.
- दोन्ही Abhi ने दिले (2026-10-06).

**Abhi चे निर्णय (2026-10-06, एकदाच विचारलेले प्रश्न):**
1. **PCS थांबवला.** PCS ला G1 वर गोठवलं; PCS-4 (PAPER runner) आणि PCS-5 (backtest) रद्द.
   - त्याचे भाग (settings store/इतिहास, expiry/strike guards, preview, dashboard रचना) Elliott मध्ये reuse करायचे.
   - PCS पान OFF स्थितीत तसंच राहील.
2. **Golden-file काळ 2026-07-01 → 2026-10-06 "contaminated".**
   - Logic याच काळावरून ठरलं. फक्त regression साठी वापरायचा, tuning किंवा आकडेवारीसाठी नाही.
   - **अंतिम holdout चाचणीतूनही वगळायचा** (`elliott/data_policy.py: final_holdout_mask`).
   - बाकी 2024-04 नंतरचा holdout बंदच.
3. **Upstox candles public Trade repo मध्ये नाहीत.**
   - Private `trade-data` repo मध्ये जातात (Abhi तयार करेल आणि session access देईल).
   - VPS script फक्त read-only आहे, आणि destination remote "trade-data" नसेल तर थांबतो.
   - तपासलं: public repo मध्ये आधी कुठलाही candles branch push झालेला नाही.
   - Major-levels export सुद्धा आता इथूनच जातो.
4. **Options premium चा क्रम:**
   - (a) Upstox expired-options API probe.
   - (a2) NSE F&O bhavcopy (2019 पासून, VPS वरून, private repo मध्ये). त्या दिवसाच्या bhavcopy वरून IV काढून intraday entry/exit साठी BS.
   - (b) शुद्ध BS फक्त शेवटचा पर्याय; अहवालात ठळक "model premium".
   - (c) TrueData/GDFL चे पर्याय समांतर शोधायचे; विकत घेणं Abhi च्या निर्णयानंतरच (G-PAID).
   - तपशील: `docs/reports/options_data_sources.md`. दोघांचेही दर sandbox मधून सापडले नाहीत, quote मागवावा लागेल.
5. **v1 फक्त NIFTY.** SENSEX फक्त settings मधला पर्याय; replication डेटा मिळाल्यावर.
6. **Branch:** याच branch वर, एक phase = एक PR, PR title `[Elliott E#]`.
7. **Phase क्रम:** E0 → E1 → E2 → E3 → E4 (G2) → E5 (G1) → E6 (G3).
8. **Golden expectations** (`docs/reports/elliott_golden_expectations.json`):

   | Trade | पातळी | अर्थ |
   |---|---|---|
   | T2, T3, T4, T7, T8 | must | घेतला नाही तर test FAIL |
   | T1 | verify | मध्यम खात्री; आधी reversal candle पडताळा |
   | T6 (5 Oct A-end bear calls) | must_not | नियम R4; bot ने घेतला तर test FAIL |
   | T5, T9 | report | Tier C, 0.25×; घेतला किंवा नाही दोन्ही चालतं |

   - इतर must_not: 28 Sep आणि 6 Oct च्या gaps वर entry नाही; 6 Oct 09:40 ला 22,614 वर bear call नाही.
9. **Backtest capital:** ₹10 लाख default, dashboard setting म्हणून. निकाल ₹ सोबत R-multiples आणि % मध्येही.

**माझे निर्णय (कारणासह):**
- **T1 "verify" पातळीवर.** Master prompt मध्ये तो "मध्यम खात्री, reversal candle पडताळा" असा आहे. म्हणून तो जुळला नाही तर FAIL नाही; कारणासह report.
- **T9 report-only, पण 09:40 / 22,614 bear call must_not.** Master prompt मध्ये 6 Oct 09:15–09:45 नकार आहे, तर Abhi चं उत्तर T9 ला report-only म्हणतं. दोन्ही पाळण्यासाठी: त्या window मधला Tier C trade चालतो, पण तो विशिष्ट bear call नाही.
- **Bhavcopy सगळ्या calendar दिवसांसाठी मागवतो.** म्हणजे Budget/Muhurat सारखे weekend special sessions चुकत नाहीत.
  - फक्त सगळीकडे 404 आलं तरच तो दिवस "नाही" (सुट्टी) मानतो.
  - 403 किंवा timeout आला तर "चूक", आणि पुढच्या run ला पुन्हा प्रयत्न.
- **Bhavcopy ची श्रेणी:** 2018-12 → 2024-03 (weekly options कधी सुरू झाले याचा data-पुरावा मिळावा म्हणून थोडा आधीचा भाग) + golden काळ. Sealed holdout चा एकही दिवस नाही.
- **Upstox probe चा candle sample** ≤ 2024-03 च्या expiry चा. नसेल तर golden काळातला. Holdout चा कधीच नाही.
- **ऐतिहासिक expiry calendar** bhavcopy वरूनच (अधिकृत). Weekday hard-code नाही. Live साठी फक्त Upstox contract master.
- **Lot size bhavcopy मधून फक्त UDiFF काळात** (8 Jul 2024 नंतर = आपल्यासाठी फक्त golden काळ). जुन्या format मध्ये lot column नाही, म्हणून IS/VAL चा lot इतिहास E3 मध्ये स्रोतासह वेगळ्या तक्त्यातून.
- **Major-levels साठी MCX candles** (GOLD/COPPER/SILVER, 110 दिवस) sealed-holdout नियमाखाली नाहीत, कारण तो नियम NIFTY साठी आहे. NSE index candles मात्र आपोआप filter होतात (फक्त IS/VAL + golden काळ).

**E0 मध्ये काय आहे:**
- `elliott/data_policy.py`: IS / VAL / CONTAMINATED / HOLDOUT, `check_range`, `filter_allowed`, `final_holdout_mask`.
- `elliott/bhavcopy.py`: NSE F&O bhavcopy parser (जुना format आणि UDiFF), NIFTY options + futures, expiry calendar, पहिली weekly listing.
- `research/elliott_vps_data.py` (VPS, read-only): `probe-expired`, `golden`, `major-levels`, `bhavcopy`, `all`. Resume होतो, token छापत नाही, public repo नाकारतो.
- `scripts/elliott_e0_vps.sh`: VPS वरचा एकच idempotent command. पहिल्यांदा deploy key तयार करून थांबतो; key जोडल्यावर clone → probe → golden → major-levels → push → data check + BANKNIFTY अहवाल → bhavcopy background मध्ये (संपल्यावर push).
- `research/elliott_data_check.py`: data उपलब्धतेचा ≤ 40 ओळींचा अहवाल. Offline निकाल: NIFTY 1m 2015-01-09 → 2024-03-27, IS 1727 दिवस, VAL 555 दिवस.
- `docs/reports/options_data_sources.md`, `docs/reports/elliott_golden_expectations.json`.
- `tests/test_elliott_e0.py` (+20).

**स्वतंत्र review नंतर दुरुस्त्या (High नाही; 4 Medium + Low):**
- **Bhavcopy "सुट्टी" आता कायमची लपवली जात नाही.**
  - आजचा/कालचा दिवस ⇒ `pending`.
  - Weekday 404 ⇒ offline NIFTY डेटा/2026 सुट्टी-यादीनुसार ठरतं: सुट्टी, "फाईल हवीच" (चूक), किंवा माहीत नाही (`missing_weekday`). शेवटच्या दोन्ही बाबतीत पुढच्या run ला पुन्हा प्रयत्न.
  - जुन्या फाइल्ससाठी तिसरा URL (nsearchives historical path) जोडला.
  - Parse न होणारी (HTML) फाईल आली तर पुढचा URL प्रयत्न; 0 NIFTY ओळींची फाईल = चूक.
- **Major-levels:** NSE index candles मधून sealed holdout काढला. आजपासून चालवलं तरी 2026-10-07 नंतरचे candles लिहिले जात नाहीत.
- **Golden 1m पूर्णता तपासणी:** अपेक्षित trading दिवस (weekday − NSE 2026 सुट्ट्या) गहाळ किंवा अपूर्ण असतील तर ✅ नाही, exit ≠ 0. 6 Oct चा बाजार बंद होण्याआधी चालवलं तर नकार.
- **Bhavcopy parser:**
  - प्रत्यक्ष expiry (`FininstrmActlXpryDt`) वापरतो.
  - Volume चं एकक `volume_unit` मध्ये नोंदवलं.
  - सगळे संख्या-columns float64, म्हणजे प्रत्येक महिन्याचा parquet schema एकच.
- **Golden bhavcopy वेगळ्या folder मध्ये** (`NIFTY_golden/`). त्यामुळे research loader चुकून contaminated डेटा उचलत नाही.
- **`data_policy` च्या सीमा exclusive**, म्हणजे sub-second फरकाने उत्तर बदलत नाही.
- **Probe:** candle window सुद्धा `check_range` ने तपासतो, आणि `instrument_key` नसेल तर पुढचा contract घेतो.
- **`check_repo`** fetch आणि सगळे push URLs तपासतो.
- **`main()`** कुठलीही पायरी फेल किंवा अपूर्ण असेल तर exit ≠ 0 आणि ⚠️. जे मिळालं ते (manifest सह) push होतं, आणि पुढच्या run ला resume.

**`trade-data` access:** Abhi ने repo तयार केला (2026-10-07). पण session ला जोडताना GitHub ने "no access" दिलं, म्हणजे Claude GitHub App त्या repo वर अजून install नाही. VPS push deploy key ने होतो, त्यामुळे इथे काही अडत नाही. फक्त मला तो डेटा वाचण्यासाठी access लागेल.

**पुढचे PRs (प्रत्येकात tests, full suite, CI, स्वतंत्र review, WORK_LOG):**

| PR | काम | थांबा-बिंदू |
|---|---|---|
| E1a | Causal multi-degree pivots D0–D3 (confirmed/tentative, `confirmed_at`), Similarity & Balance, auto-TF (8–40 बंद candles). No-repaint tests: truncation invariance, tentative-ban | — |
| E1b | Count tree: patterns, नियम R1–R11, guideline score, beam, hysteresis, vote; Neely time flags; invalidation चा degree-प्रसार (relabel → parent cascade); `count_inv_basis` | — |
| E2 | Setups S1–S14 (S5/S8/S11/S14 default off); composite trigger T1–T7 (`price_action/candles.py` generic, MCX वर्तन tests ने अबाधित); real break / false break; `wick_beyond_inv_action = recount` | — |
| E3 | Contract layer (live: Upstox master; इतिहास: bhavcopy), काळानुसार STT/lot, strike सूत्र, DTE-निहाय credit guard, exits क्रम 0–8, sizing (₹10 लाख default). Exit कधीच अडत नाही याची test | — |
| E4 | Backtest (golden-file regression, baselines 1–7, WRC/SPA, Deflated Sharpe, PBO CSCV S=16). अहवाल setup × degree × tier × DTE, ₹ + R + % मध्ये → `docs/reports/elliott_pullback_backtest.md` | **G2** |
| E5 | Dashboard "Elliott Pullback Credit Spread": settings (विभाग 11 + 14), presets, live preview, wave-label chart, इतिहास + snapshot, Signal Log | **G1** |
| E6 | PAPER wiring, default OFF. 1-Min Instant Trader ला हात नाही | **G3** |

## 2026-10-07 · Elliott E0.1 — VPS export: Abhi चा deploy key alias, 15:30 पहारा, push सारांश

**Abhi (2026-10-07):**
- `trade-data` private repo तयार आहे आणि Claude GitHub App ला त्याचा access दिला. मी तो session मध्ये जोडला.
- VPS push deploy key ने: ssh alias `github-trade-data`, IdentityFile `~/.ssh/trade_data_key`, remote `git@github-trade-data:abhishekwasu-hue/trade-data.git`.
- `trade-data` मध्ये काय ठेवायचं: golden candles, major-levels candles, BANKNIFTY daily, Upstox probe निकाल, NSE bhavcopy.
- Export block read-only, 15:30 नंतर, एकाच copy-paste मध्ये, आणि शेवटी काय push झालं याचा सारांश.

**बदल (`scripts/elliott_e0_vps.sh`):**
- Abhi चा आधीपासूनचा alias आणि key वापरतो; script स्वतः key तयार करत नाही.
  - Alias नसेल पण key असेल ⇒ alias जोडतो.
  - दोन्ही नसतील ⇒ नेमक्या पायऱ्या सांगून थांबतो.
- Weekday ला 09:00–15:30 IST मध्ये चालवला तर थांबतो (`FORCE=1` ने override).
- BANKNIFTY daily CSV `trade-data/banknifty/` मध्ये copy करतो.
- शेवटी push सारांश छापतो: या run चे commits, फाइल्सची संख्या, आणि folder-निहाय आकार. Background मधला bhavcopy सुद्धा संपल्यावर स्वतःचा सारांश log मध्ये लिहितो.
- `REMOTE`, `DATA`, `TRADE`, `KEY` env ने बदलता येतात (चाचणीसाठी).
- Sandbox मध्ये local bare repo आणि डमी scripts वापरून पूर्ण वाट चालवून पाहिली: push, सारांश, background push. दुसऱ्यांदा चालवल्यावर "नवीन काही नाही".

**`trade-data` README** (push केला): folders ची रचना आणि data-use नियम (IS / VAL / CONTAMINATED / sealed HOLDOUT).

## 2026-10-07 · Elliott E1a — causal multi-degree swings (D0–D3)

**काय केलं:**
- **`elliott/settings.py`:** Elliott चा एकच settings schema (dashboard E5 हाच वापरेल). Code मध्ये आकडा hard-code नाही.
  - प्रकार: int, float, choice, list_float, list_int, list_tf.
  - Validation:
    - यादीची लांबी = degrees ची संख्या.
    - Degree वाढताना threshold वाढायला हवा.
    - `tf_bars_min < tf_bars_max`.
    - अस्तित्वात नसलेल्या trade degrees वगळतो.
  - प्रत्येक trade सोबत settings चा snapshot hash.
  - E1a चा विभाग "Degrees / swings" (spec §11) आहे; पुढचे phases पुढचे विभाग जोडतील.
- **`elliott/swings.py`:**
  - **Frames:** NIFTY spot 1m → NSE 09:15-anchored TF bars. फक्त **बंद** bars (`opportunity_engine.sessions.resample_nse` reuse).
  - **Threshold (प्रति degree):** atr (पट × ATR), pct (% × भाव), किंवा fractal (r, आलटून-पालटून, causal).
  - **ZigZag core:** `price_action/legs.zigzag_pivots` reuse केलं.
  - **Confirmed pivot:** `confirmed_at` = confirm bar चा `bar_end` (knowable_at). एकदा confirm झालेला pivot कधीच बदलत नाही.
  - **Tentative pivot:** फक्त चालू wave साठी.
  - **Degree → TF:** `degree_tf_mode = auto_by_bars` (default) मध्ये pivots structure TF (5m) वर; `fixed` मध्ये degree-निहाय TF.
  - **Auto-TF (§14 Q3):** corrective wave जितक्या **बंद** candles मध्ये दिसते, त्यावरून `tf_bars_min`–`tf_bars_max` मध्ये बसणारा सर्वात लहान TF.
  - **Similarity & Balance (Neely 1/3, price किंवा time):** degree assignment च्या गुणवत्तेसाठी.
- **`research/elliott_swings_report.py` → `docs/reports/elliott_e1a_swings.md`:** फक्त IS, फक्त वर्णन.

**IS निकाल (default settings, NIFTY 5m, 2015–2021):**

| Degree | pivots/दिवस | leg median (points) | leg median (bars) | Similarity & Balance |
|---|---|---|---|---|
| D0 | 14.2 | 25 | 5 | 0.94 |
| D1 | 4.2 | 53 | 15 | 0.91 |
| D2 | 1.2 | 114 | 50 | 0.90 |
| D3 | 0.4 | 206 | 155 | 0.90 |

Degrees स्पष्टपणे वेगळ्या आकाराच्या आहेत. Leg चे bars दोन्ही टोकं धरून मोजले आहेत (auto-TF च्या मोजणीसारखे). D0 चे legs ~5 bars चे आहेत, त्यामुळे 5m वरही त्यांची आतली रचना दिसत नाही; म्हणून auto-TF मध्ये D0 वर entry फक्त पुरेशी लांब correction असतानाच.

**निर्णय (कारणासह):**
- **Auto mode मध्ये सगळ्या degrees चे pivots एकाच structure TF (5m) वर**, फक्त threshold वेगळा. Spec नुसार pivots/counts structure TF वर आणि TF निवड फक्त trigger साठी (§6), आणि एकाच TF मुळे cross-degree nesting सोपं आणि causal राहतं. Fixed mode पर्याय म्हणून ठेवला.
- **ATR मध्ये रात्रीचा gap (आधीचा close) TR मध्ये धरला** (standard TR). सकाळी थोडा वेळ threshold मोठा राहतो, म्हणजे gap वर खोटे swings कमी. Gap वर entry नसल्याचा नियम (E2) वेगळा.
- **Fractal mode causal ठेवला:** सलग समान प्रकाराचा अधिक टोकाचा pivot आला, तर आधीचा pivot न बदलता मधला उलट extreme नवीन confirmed pivot म्हणून घालतो.
- **Auto-TF चा fallback:** कुठलाच TF 8–40 मध्ये नसेल, तर ≥ 8 candles असलेल्यांपैकी सर्वात मोठा (रचना दिसते आणि noise कमी); कुठलाच ≥ 8 नसेल तर सर्वात लहान.

**स्वतंत्र review नंतर दुरुस्त्या (High नाही; 2 Medium + Low):**
- **Settings:** आधी "degree वाढताना वाढायला हवं" हा नियम तपासतो आणि मगच यादीची लांबी. आधी या क्रमामुळे reset झालेल्या 4-मूल्यांच्या यादीसोबत `degree_levels = 5` राहून engine `IndexError` देत होतं.
  - फक्त चालू पद्धतीत वापरली जाणारी यादी तपासली जाते.
  - Fixed mode मध्ये degree_tf degree सोबत लहान होऊ नये.
  - Trade degrees मधले duplicates काढले.
  - `list_int` मध्ये पूर्णांकच चालतो.
  - TF यादीत फक्त 3m–1d.
- **Fractal mode:** उलट प्रकारचा pivot त्याच्या दिशेने खरंच पुढे असेल तरच घेतो. आधी 2018 च्या डेटावर काही "वर" legs प्रत्यक्षात खाली जात होते. हे फक्त fractal mode मध्ये होतं, default नाही.
- **Tentative pivot:**
  - समान भाव आल्यास शेवटचा bar घेतो (confirm करताना zigzag तोच निवडतो).
  - `upto` पर्यंत माहीत असलेल्या pivots वरूनच तयार होतो.
- **`auto_tf`:**
  - आता `in_range` flag सुद्धा देतो. E2 मध्ये < 8 candles ⇒ रचना दिसत नाही ⇒ entry नाही.
  - `auto_tfs` मधला TF frames मध्ये नसेल तर गुपचूप वगळत नाही, ValueError देतो.
- **Bars मोजण्याची एकच पद्धत:** दोन्ही टोकं धरून.
- **1m frame** ला regular-hours filter लावला.
- **नोंद:** NSE outage च्या दिवशी (2021-02-24) सत्र लवकर संपल्याने त्या दिवसाचे काही bars "बंद" मानले जात नाहीत, म्हणजे वगळले जातात. हे causal आहे आणि repaint होत नाही. IS मध्ये असे 13 5m bars आहेत.

**Tests:** `tests/test_elliott_swings.py` (+14):
- Truncation invariance: atr / pct / fractal आणि fixed mode (15m/1h/1d). Cuts सत्रातल्या, 5m grid बाहेरच्या random मिनिटांवर. `now=` path आणि tentative pivot सुद्धा हुबेहूब जुळतात.
  - Mutation check: `bar_closed` filter काढल्यावर 4 tests fail होतात.
- Fractal mode मध्ये प्रत्येक leg योग्य दिशेने जातो.
- समान भावाचा tentative pivot.
- Pivots कधीच बदलत नाहीत (immutability).
- Pivot semantics आणि tentative pivot (फक्त upto पर्यंतचे bars).
- अपूर्ण bar वगळतो; ATR causal.
- Fixed TF mode.
- Similarity & Balance.
- Auto-TF (फक्त बंद candles).
- Settings validation.

## 2026-10-07 · Elliott E1b — count tree: नियम R1–R11, patterns, real break, cross-degree, vote

**काय केलं:**
- **`elliott/breaks.py` — "खरा break" (spec §7, §14 Q1):** count invalidation आणि (E3) exits दोन्ही याच व्याख्येवर.
  - buffer = 0.25 × median range. Median range = मागच्या बंद bars चा, चालू bar वगळून.
  - Break खरा तेव्हाच, जेव्हा यापैकी जे आधी घडेल:
    - displacement candle (त्याच bar वर);
    - acceptance (पुढचे bars reclaim नाहीत; window मधली displacement सुद्धा चालते).
  - नाहीतर false break.
  - Failed retest (c) साठी logical reversal लागतो, म्हणून त्याचा hook E2 मध्ये.
  - `BreakCache` फक्त चालू वेळेपर्यंत scan करतो (causal). पूर्वी तो पूर्ण उपलब्ध frame scan करायचा, ज्यामुळे पूर्ण IS वर तो खूप हळू होता.
- **`elliott/patterns.py`:** impulse, leading/ending diagonal, zigzag, flat (regular/expanded), triangle (contracting/barrier/expanding), WXY.
  - नियम म्हणजे pass/fail: R1, R2 (wave 5 ची मर्यादा, diagonals सुद्धा), R3 (strict), R6, R7, R8, R9.
  - Guidelines फक्त score म्हणून (Fibonacci, depth, alternation, sub-counts, Neely time).
  - प्रत्येक count साठी चालू wave नुसार hard invalidation (level + बाजू + नियम).
  - "पुढची wave motive असेल तर तिची दिशा":
    - A नंतर B येतो ⇒ 0 (R4: A-end ban).
    - Ending diagonal आणि expanding triangle ⇒ 0 (spec §5 निषिद्ध #5, P8).
  - पूर्ण झालेल्या waves चे नियम फक्त confirmed pivots वर (tentative ban).
  - Tolerances संबंधित pivot च्या confirm bar वर गोठवलेले, म्हणजे मेलेला count परत येत नाही (R11).
- **`elliott/counts.py`:** प्रत्येक degree वर दिलेल्या वेळेपर्यंत माहीत डेटावरून counts.
  - Cross-degree (वरून खाली): लहान degree चा count मोठ्या degree च्या count च्या **चालू wave** चा कायदेशीर भाग असेल तरच. Origin, दिशा आणि pattern-कुटुंब जुळायला हवं (R5: triangle wave 2 नाही).
  - Pattern ची शेवटची wave (5/C/E/Y) चालू असेल तर पुढची दिशा parent ठरवतो (S7).
  - Beam, vote, hysteresis ("वंश" जुळल्यास) आणि invalidation log (break confirm झाल्याच्या वेळेसह).
- **Settings:** "Count engine" आणि "Real break" विभाग (spec §11, §14).
  - काही नवीन [अनुमान] parameters, सगळे dashboard वर: `fib_tol`, `guideline_prior`, `cross_degree_*`, `orphan_position_penalty`.
- **`research/elliott_counts_report.py` → `docs/reports/elliott_e1b_counts.md`:** फक्त IS, फक्त वर्णन.

**IS निकाल (2015–2021, दर 30 मिनिटांनी snapshot, 5.7 ms/snapshot):**

| Degree | count नाही | vote स्पष्ट | पुढे motive वर | पुढे motive खाली |
|---|---|---|---|---|
| D3 | 0% | 40.2% | 16.5% | 23.7% |
| D2 | 28.2% | 12.4% | 6.0% | 6.4% |
| D1 | 55.8% | 12.1% | 6.1% | 6.0% |
| D0 | 71.1% | 8.9% | 4.3% | 4.6% |

- D3 चे preferred counts: flat/C 27%, impulse/3 24%, flat/B 18%, wxy/Y 13%.
- लहान degrees वर अनेकदा count नसतो. हे spec च्या strict nesting मुळे आहे (लहान degree चा count फक्त मोठ्या degree च्या चालू wave चा भाग म्हणूनच). याचा trade-संख्येवरचा परिणाम E4 मध्ये मोजेन; penalty mode हा पर्याय आहे.

**निर्णय (कारणासह):**
- **Count दर snapshot ला pivots वरून पुन्हा मांडला जातो** (stateless; causal आणि सोपा). "Evolve forward" चा हेतू preferred वर hysteresis लावून पाळला. Hysteresis count च्या वंशावर (degree + pattern + दिशा + origin) लागतो, म्हणजे नवीन pivot confirm झाल्यावर बदलणाऱ्या key ला अडथळा येत नाही.
- **Vote beam वर:** §11 नुसार `beam_k` हीच "valid counts" ची संख्या. सगळ्या कच्च्या उमेदवारांवर vote घेतल्यास D3 वर स्पष्ट vote 40% वरून 1.4% वर येतो.
- **Sub-count = 1** (leg च्या आत lower pivot नाही) म्हणजे पुरावा नाही. आधी तो 3/5 दोन्हीत "चूक" धरला जायचा; IS मध्ये असे 42% legs आहेत.
- **स्थान-बंधित patterns** (diagonals, triangle) ना parent नसताना score × 0.5 (`orphan_position_penalty`). R5/R9 नुसार ते फक्त ठराविक wave म्हणून येतात, आणि सर्वात वरच्या degree वर स्थान तपासता येत नाही. याआधी D3 वर ending diagonal सुमारे 48% वेळा preferred होता.
- **Triangle B:** flat सारखी मर्यादा, म्हणजे B ≤ 2 × A. पूर्ण B आणि चालू B चा invalidation दोन्हींना हीच, त्यामुळे दोन्ही सुसंगत आणि expanding triangle शक्य. चालू C ला "C ची सुरुवात" हाच invalidation, कारण contracting की expanding हे C संपल्यावरच ठरतं.
- **`count_lookback_pivots` ची कमाल 5:** कुठल्याही pattern मध्ये 5 पेक्षा जास्त legs नाहीत. Parent च्या चालू wave ची सुरुवात lookback बाहेर असली तरी origin म्हणून घेतली जाते.
- **Strict मोड:** मोठ्या degree कडे डेटा आहे पण एकही count नाही ⇒ लहान degree ला पण count नाही (gray). मोठ्या degree कडे डेटाच नसेल तेव्हाच लहान degree मुक्त (`parent_missing`; E2 ते block करेल).
- **अजून नाही (नोंद):**
  - Neely "Terminal C" सूट (C ending diagonal असल्याचं child वरून समजेल; E2).
  - R10 (combination मध्ये एकच zigzag; sub-pattern माहिती लागते).
  - Failed-retest break (E2).

**स्वतंत्र review (High नाही; 6 Medium + Low) — सगळे दुरुस्त:**
- k ≥ 2 मध्ये window मधली displacement.
- शेवटच्या wave चा vote parent वरून.
- Ending diagonal 2/4 ⇒ 0.
- Diagonal R2 मर्यादा.
- Running आणि completed नियम सुसंगत (triangle B/C, गोठवलेले ATR/MR).
- Parent रिकामा ⇒ child रिकामा.
- Low मुद्दे: wave 3 wave 1 च्या आत ⇒ नकार (strict), expanding triangle E ⇒ entry नाही, flat B मध्ये triangle चालतो, vote 50/50 ⇒ gray, log मध्ये break ची वेळ, fixed-TF origins.

**दुसरा review (blocking नाही; 1 Medium regression + Low) — दुरुस्त:**
- **Regression:** expanding triangle चा E चालू असताना child parent ची दिशा घेत होता. आता ending diagonal आणि expanding triangle कधीच parent ची दिशा घेत नाहीत ⇒ 0.
- **Spec मधला अंतर्गत विरोध — निर्णय S11:** ending diagonal संपल्यावर लगेच C-end entry (S7) नाही. आधी उलटा leg, मग त्याचा retrace (S11).
- **Non-strict R3:** चालू wave 4 च्या level ला सुद्धा तितकीच सवलत (wave 3 च्या confirm वर गोठलेली MR), म्हणजे completed check आणि running level एकच.
- **`frozen()`:** NaN ⇒ 0 (units मिसळत नाहीत, आणि मूल्य bar-दर-bar बदलत नाही).
- **Origin scan:** लवकर थांबतो (वेगासाठी).
- **Vote संच = beam:** spec §4 पासूनचा हा जाणूनबुजून घेतलेला फरक आहे. E2 मधल्या `alt_block_weight` आणि strike च्या `alt_weight_min` तपासण्या याच beam संचावर करायच्या.

**Tests:** `tests/test_elliott_counts.py` (+19):
- प्रत्येक pattern चे नियम आणि invalidation ची बाजू.
- R2/R3/R9, triangle (B मर्यादा, गोठवलेला tolerance, expanding).
- Neely flags.
- Real break: false break, acceptance, displacement (दोन्ही बाजू), k = 2.
- Cache causal.
- Truncation invariance (real_break आणि wick; nodes, preferred, vote, gray).
- Cross-degree (parent कुटुंब, शेवटच्या wave ची दिशा, रिकामा parent).
- Hysteresis (margin 1 आणि 0) आणि log.
- Mutation checks: tentative ला भविष्य दिलं, break ला भविष्य दिलं, किंवा parent-vote काढला, तर tests fail होतात.

## 2026-10-07 · Elliott E2 — setups S1–S14, composite entry trigger T1–T7, failed-retest break, invalidation hierarchy

**काय केलं:**
- **`elliott/reversal.py` — composite "logical reversal" (spec §6 T1–T4, §14 Q2):** शेवटच्या 1–3 बंद candles चा composite. Touch, reclaim, शेवटची candle trade दिशेने, strength (1.2–2.5 × median range), अनिर्णय ⇒ follow-through (N = 4), score (wick / close-location / body / time / divergence). Bear call = किंमत उलटी करून तेच नियम (mirror test).
- **`elliott/breaks.py` — (c) failed retest:** break नंतर reclaim झाला, पण लगेच (trigger window मध्ये) level ला उलट बाजूने logical reversal मिळाला ⇒ खरा break. (a)/(b)/(c) पैकी जे आधी. `break_retest_confirm` (default true).
- **`elliott/setups.py` — count → setup:** trade degree वर preferred count "चालू wave corrective, पुढची motive" म्हणतो तेव्हाच. Pattern / चालू wave आणि parent ची चालू wave यावरून S1–S14, tier (A/B/C), zone (Fib levels), hard invalidation.
  - Block: count नाही, `parent_missing`, gray, पुढची wave corrective (A-end R4, triangle/X आत), parent च्या B/X/triangle आत, उलट count ≥ `alt_block_weight`, setup बंद, HTF gate.
  - §14 Q6: preferred चा inv wick ने ओलांडला (real break नाही) ⇒ `recount`: त्याच दिशेचा दुसरा valid count (उदा. expanded flat, inv = wick टोक); `skip`: entry नाही.
- **`elliott/trigger.py` — Scanner:** दर बंद 5m bar ला snapshot → setup → trigger TF चा bar नेमका तेव्हा बंद झाला तरच तपासणी.
  - Trigger TF = corrective wave 8–40 बंद candles मध्ये दिसेल असा सर्वात लहान TF (§14 Q3).
  - C2 (hard inv TTF वर तुटलेला नाही), R4 (correction मध्ये ≥ 3 sub-legs), T7 (close शेवटच्या sub-leg च्या origin च्या आतच — breakout ban), T1–T4, T5 (09:30–14:45; composite चे सगळे candles त्याच session चे आणि 09:30 नंतर सुरू झालेले ⇒ opening gap candle composite मध्ये नाही), T6 (vote).
  - Signal = TTF bar close (knowable_at); fill पुढच्या bar च्या open वर (E3/E4). एकाच setup वर नवीन signal फक्त नवीन composite वर.
- **`elliott/invalidation.py`:** signal नंतर hard / parent (cascade) / soft levels चा real break (TTF वर) — E3 चे exits याच्यावर.
- **Settings:** "Setups" आणि "Entry trigger" विभाग (spec §11, §14) — सगळे dashboard साठी. नवीन प्रकार: `time`, `list_str`.
- **`research/elliott_signals_report.py` → `docs/reports/elliott_e2_signals.md`** (फक्त IS, फक्त वर्णन). `docs/reports/elliott_e1b_counts.md` retest बदलानंतर पुन्हा तयार केला (फरक: 2 invalidation आकडे).

**IS निकाल (2015–2021, default, review दुरुस्त्यांनंतर, P&L नाही):** 510 signals (0.30 प्रति दिवस); bull put 281 / bear call 229.
- Setup: S7 (correction संपली) 162, S3 (wave 4) 142 (त्यापैकी 110 Tier C — leading diagonal wave 4), S2 ((ii) of 3/5) 113, S6b 21, S12 18, S13 18, S6a 14, S6c 9, S4 7, S9 4, S1 2.
- Degree: D1 258, D2 142, D0 110. Trigger TF: 5m 412, 15m 97, 30m 1.
- Entry न होण्याची मुख्य कारणं: count नाही / gray (D0 91%, D1 88%, D2 88% bars).
- **नोंद:** review च्या दुरुस्तीआधी 566 signals होते; S1 25 → 2 आणि S10 10 → 0 झाले — ते बहुतेक "preferred block झाल्यावर दुसऱ्या count वरून" आलेले चुकीचे signals होते. S1/S10 इतके कमी का (wave 1 नंतरचा wave 2 बहुतेक वेळा parent च्या wave 3/5 म्हणून S2 मध्ये जातो, की cross-degree मुळे count च नसतो) हे E4 मध्ये trade-स्तरावर तपासेन. Tuning नाही.

**निर्णय (कारणासह):**
- **"Touched level" = शिवलेल्या levels पैकी सर्वात खोल.** §6 मध्ये "सर्वात वरचा" लिहिलं आहे, पण §10 चं उदाहरण (B low 22,396, reversal close ~22,410, zone 22,419–22,371) फक्त सर्वात खोल level नेच जुळतं. सर्वात उथळ level (22,467) वर close मागितला तर T7 (sub-leg origin च्या आत close) शी विसंगत.
- **MCX चं `price_action/candles.py` बदललं नाही.** त्याचे weights/score (0–100, sweep, speed) वेगळे आहेत; फक्त composite चं logic तेच ठेवून `elliott/reversal.py` नवीन. त्यामुळे MCX वर्तनाला धोका शून्य.
- **D0 च्या sub-legs (R4, T7 चा H):** D0 खाली degree नाही ⇒ trigger TF चे 1-bar fractals (सर्वात लहान दिसणारी रचना). D ≥ 1 ला D−1 चे confirmed pivots; ते अपुरे असतील तर हेच fallback. [अनुमान]
- **Wave 4 zone:** spec मध्ये "आधीच्या lesser-degree 4 चा span" (मोजायला sub-pattern माहिती लागते) ⇒ wave 3 चा 0.236/0.382/0.5 retrace [मार्गदर्शक]; flat B zone 0.9/1.0/1.236/1.382 × A; triangle E 0.5/0.618/0.786 × D. सगळे dashboard वर.
- **(ii) of 5 = S2, Tier C** (late stage, §4). S3 चा parent wave 5 असेल तर तो S5 (default बंद).
- **S7 चा parent B/X मध्ये** ⇒ तो parent चा C/Y trade ⇒ Tier B; parent flat B ⇒ inv = B टोक ∓ buffer (S6b नियम), flat_b_max नाही (पहिल्या smoke run मध्ये हे दूरचं level येत होतं — दुरुस्त).
- **S11 ओळख:** wave 2/B चा origin = degree D किंवा D+1 वरच्या contracting ending diagonal चं टोक (overlap + converging legs). S11 default बंद ⇒ diagonal नंतरचा pullback trade नाही.
- **Tier:** parent wave 5 ⇒ C; parent C/Y (corrective) ⇒ B; D+2 च्या चालू दिशेविरुद्ध ⇒ B; lead_diag wave 4 ⇒ C.
- **Gap नियम:** composite मध्ये 09:30 आधीचा candle नाही (1h TTF ला पहिला 09:15–10:15 bar composite मध्ये येत नाही).
- **C3 (`c_time_rule = delay`):** zigzag/flat C-end (S7) वर t(c) > t(a)+t(b) ⇒ entry नाही; C स्वतः ending diagonal (D−1 चा preferred count) असेल तर सूट (Neely Terminal C).
- **अजून नाही (E3):** fill, strike, expiry, cost, exits.

**स्वतंत्र review (2 High + 6 Medium + Low) — सगळे दुरुस्त:**
- **High — preferred count block झाला तरी दुसऱ्या count वरून setup:** आता setup फक्त preferred count वरून (C0). दुसरा count फक्त §14 Q6 मध्ये (preferred चा inv wick ने ओलांडला) आणि तोही **त्याच चालू wave** चा (उदा. expanded flat). (2019 मध्ये 86 पैकी 12 signals चुकीने "recount" होते.)
- **High — X-end trade S7 म्हणून निसटत होता:** parent wxy च्या X चा शेवट ⇒ S8 (default बंद), §5 S7 नोंदीप्रमाणे.
- **Failed retest कडक:** composite तुटलेल्या बाजूने सुरू (पहिला open L पलीकडे) आणि नकाराचा close buffer पलीकडे; प्रत्येक window स्वतंत्र तपासली. आधी वरून आलेला आणि buffer आत close होणारा bar सुद्धा "break" ठरत होता — false-break नियमाविरुद्ध.
- **Ending diagonal च्या आत pullback** (parent end_diag) ⇒ block (§5 निषिद्ध #5).
- **S7 चा parent सुद्धा संपतोय (wxy Y)** ⇒ grandparent चा नियम-स्तर inv (आधी कधीच fire होत नव्हता).
- **Dedup TF-निरपेक्ष** (composite च्या वेळेवरून; auto-TF 5m → 15m बदलल्यावर नवीन नकार चुकीने अडत होता).
- **Scan वेळा** = सगळ्या TFs च्या bar_end चा union (`Scanner.times()`; structure TF मोठा असला तरी प्रत्येक trigger-TF close तपासला जातो).
- **Hard inv तुटल्यावर त्या setup ला re-entry नाही** (S6b चा inv B सोबत हलतो, म्हणून आधीच्या signal चा inv लक्षात ठेवतो).
- Low: Terminal C सूट फक्त **याच** C च्या origin वरून सुरू होणाऱ्या D−1 ending diagonal ला; S11 चा inv = diagonal टोक; S7 चा TF/sub-legs पूर्ण correction वरून (§14 Q3); wick = inv अचूक बरोबर ⇒ पलीकडे नाही; settings: `entry_start` ≥ 09:30, wick/close/body weights पैकी एक > 0, `datetime.time` चालतो.
- नोंद (बदल नाही): 1d trigger TF चा bar 15:30 ला बंद ⇒ T5 कधीच पास नाही, म्हणजे फक्त daily वर दिसणाऱ्या wave वर intraday entry नाही — spec शी सुसंगत. रिकामा `setups_enabled` चालतो (सगळे setups बंद).

**Tests:** `tests/test_elliott_e2.py` (+49):
- Reversal: hammer score, bull/bear mirror, touch/reclaim/weak/exhaustion, inv पलीकडे (low आणि मधला close), सर्वात खोल touched level + `zone_high`, शेवटची candle उलट, N = 4 follow-through (फक्त N=4 पास होणारा case), min_start.
- Failed retest: confirm, setting बंद, causal (truncation); वरून आलेला/buffer आत close ⇒ नाही; false-break मार्ग (wick, reclaim, acceptance) तसेच; नंतरचा retest वि. आधीचा displacement ⇒ आधीचा.
- Setup table (19 प्रकार), tier (D+2 विरुद्ध, 4 of 5), zones, hard inv (S6a, S6b, S7, S7-in-flat-B, S7-under-Y).
- Blocks: no count, gray, parent_missing, A-end, alt block, B आत (fall-through नाही), ending diagonal आत, S8 leak, wick recount/skip, C3 (+ Terminal C फक्त याच C ला), setup बंद, HTF gate.
- Real data (2019 Q1): प्रत्येक signal वर breakout ban — H **स्वतंत्रपणे** D−1 pivots वरून, inv आत, reclaim, soft stop, TTF close, gap candle नाही, वेळ, vote; truncation invariance.
- Synthetic T7 bull आणि bear (mirror); hard break ⇒ level_events (causal) आणि re-entry बंदी.
- Mutation checks: T7 काढला, gap नियम काढला, touched = सर्वात उथळ — तिन्ही tests fail होतात.

## 2026-10-07 · Elliott E3 — expiry, strike, credit guard, sizing, खर्च, exits (§8, §9)

**स्थिती:** trade-data मध्ये options data अजून नाही (VPS block चालायचा आहे). म्हणून E3 = data-निरपेक्ष, तपासलेले भाग (pure functions); bhavcopy/Upstox premium जोडणी आणि golden-file regression E4 मध्ये.

**काय केलं:**
- **`elliott/contracts.py`:**
  - Expiry स्रोत: bhavcopy calendar (फक्त fill दिवसापर्यंत listed contracts — causal; सुट्टीमुळे सरकलेली प्रत्यक्ष expiry). तो नसेल तर नियम-calendar: Thursday (1 Sep 2025 पासून Tuesday), monthly = महिन्याचा शेवटचा, holiday ⇒ आधीचा trading day, weekly फक्त 11 Feb 2019 पासून.
  - Expiry निवड (दुरुस्ती 2): fill दिवसानंतरची पहिली; आज expiry असेल तर पुढची. `min_dte_override` (default बंद).
  - DTE: Monday → Tuesday = 1; `session_fraction` = (आजची उरलेली मिनिटं + पूर्ण sessions × 375) / 375.
  - Lot: bhavcopy (UDiFF) असेल तर तो; नाहीतर तारीखनिहाय table.
- **`elliott/pricing.py`:** Black-Scholes price / delta / implied vol (T = dte_frac / 252, spec चा convention).
- **`elliott/costs.py`:** तारीखनिहाय दर — STT (sell premium) 0.017% → 0.05% (1 Jun 2016) → 0.0625% (1 Apr 2023) → 0.1% (1 Oct 2024) → 0.15% (1 Apr 2026); exchange, SEBI, stamp, GST/service tax, brokerage प्रति order; slippage ticks fill किंमतीत.
- **`elliott/strikes.py`:** spec §8 सूत्र — सर्वात दूरचा same-direction inv + 0.5 × MR, volatility अंतर, किमान 100 pts; 50-grid; credit/width, किमान credit, delta guard; fail ⇒ skip / widen_width / try_next_weekly; lots = capital × risk% × tier गुणक (S10 × 0.75) ÷ (width − credit) × lot.
- **`elliott/exits.py`:** §9 क्रम 0–8 (emergency strike cross → hard / parent cascade → premium stop (bar close) → soft → target → profit % → progress → expiry-day → thesis), Tier A T1 वर निम्मे lots + progressive inv, Tier B C zone मध्ये उलट logical reversal (§14 Q4) / fixed_mult, lower-degree warning. Entry settings चा कुठेही संदर्भ नाही (exits कधीच block नाहीत — test).
- **E2 `Signal`:** count आणि parent चे points (targets साठी).
- **Settings:** "Strike / expiry / sizing", "Trade management", "खर्च" विभाग (spec §11; ₹10 लाख capital — उत्तर 9).

**Spec §10 worked example (test):** S6a spot 22,410, inv 22,217, IV 13%, Monday 12:30 ⇒ dist_inv 218, dist_vol ≈ 223 ⇒ short **22,150 PE**, long 22,050, expiry 6 Oct (1 DTE). S13 spot 22,500 ⇒ short **22,250 PE**; alternate inv 22,217 मोजल्यास ⇒ 22,150 PE. तिन्ही spec शी जुळतात.

**महत्त्वाचा शोध (default बदलला नाही — E4 report मध्ये ठळक):** ₹10 लाख × 1% risk × Tier B 0.5 = ₹5,000, पण 100-width spread चा एका lot चा कमाल तोटा ≈ (100 − credit) × 65 ≈ ₹6,000 ⇒ **default वर Tier B (आणि C) trades 0 lot ⇒ skip**. Tier A ला ₹10,000 ⇒ 1 lot. E4 मध्ये निकाल R-multiples (प्रति lot) मध्येही देणार, त्यामुळे setup ची गुणवत्ता sizing शिवाय दिसेल; risk% / width बदलायचा निर्णय तुमचा.

**निर्णय (कारणासह):**
- **2019 आधी (weekly नव्हते)** "current weekly" ⇒ सर्वात जवळची listed expiry (monthly). IS चा मोठा भाग (2015–2018) यात येतो; E4 मध्ये weekly-काळ (2019+) वेगळा report करेन.
- **Lot / exchange / stamp दर** [अनुमान, secondary स्रोत]: फक्त ₹ निकालांवर परिणाम; bhavcopy UDiFF lot असेल तेव्हा तो वापरतो. E4 मध्ये bhavcopy वरून पडताळणी.
- **widen_width:** 50 च्या पावलांनी 200 पर्यंत; **try_next_weekly:** एकदाच पुढची weekly (तुमच्या नियमापेक्षा वेगळं — default बंद).
- **Tier A target चा (i):** wave-2/4 setups ना count चा पहिला leg; S7 ला parent motive चा पहिला leg. **Tier B C zone:** S6a/S6b/S12/S11 = B end + × count चा A; S6c/S7(B)/S8 = extreme + × parent चा पहिला leg; S13/S14 = parent B end + × parent A.
- **Expiry दिवस:** 14:45 नंतर short ITM किंवा < 0.5 SD (उरलेल्या मिनिटांवरून) ⇒ exit; ITM leg कधीच expire होऊ देत नाही.

**स्वतंत्र review (1 High + 7 Medium + Low) — दुरुस्त्या:**
- **High — मुहूर्त / weekend special sessions पूर्ण trading day धरले जात होते** (spot data मध्ये 1-तासाचे sessions) ⇒ नियम-calendar ने 4 Nov 2021 (दिवाळी) ही expiry मानली आणि DTE चुकले. आता `TradingCalendar.from_spot`: फक्त weekday + ≥ 300 bars चे दिवस; data नंतरचे दिवस config च्या सुट्ट्या वगळून. Test: 3 Nov 2021 expiry, 4 Nov नाही.
- **Lot:** 26 Apr 2024 → 25 जोडलं; lot आता **expiry** वरून (बदल contract series नुसार लागतात; 6 Jan 2026 पासूनच्या expiries ⇒ 65).
- **Delta guard** `delta_fn` नसताना BS delta ने (risk_free_rate, त्या expiry चा IV) — आधी गुपचूप बंद होता. IV आता प्रत्येक expiry साठी (callable) — IV नाही ⇒ "no_iv".
- **Reduce एकदाच** (soft / lower), **tick वर फक्त `emergency_check`** (pure — evaluate फक्त TTF bar close वर), **strike "ओलांडला" = पलीकडे** (स्पर्श नव्हे).
- **Tier B:** C zone acceptance ने ओलांडला ⇒ target नाही, hold + trailing (शेवटचा confirmed sub-wave, फक्त trade च्या बाजूने); C zone नसलेले Tier B (D+2 विरुद्ध झालेले S1–S4/S9/S10) ⇒ T1 वर पूर्ण exit (bounded). S8 ⇒ Y ≈ स्वतःचा W.
- **Expiry दिवशी IV / उरलेली मिनिटं नसतील** ⇒ सुरक्षित बाजू: exit (आधी फक्त ITM वर).
- **try_next_weekly:** पुढची listed नसेल तर खरं guard कारण; no_price वरही पुढची weekly तपासते. **widen_width** फक्त min_credit साठी उपयोगी (credit/width घटतो) — नोंद.
- **खर्च:** exchange txn टप्पे (0.05% → 0.053% Apr 2023 → 0.0495% Jan 2024 → 0.03503% Oct 2024), service tax इतिहास (12.36% → 14% → 14.5% → 15% → GST 18%), exercise STT **long** (exercise करणाऱ्या) leg वर, 2016 आधी notional वर [अनुमान].
- **Rule-mode listing:** 11 Feb 2019 आधीचा fill weekly निवडत नाही.
- **Settings:** `strike_step`, `iv_source`, `min_one_lot` (default **बंद**; चालू केल्यास budget < 1 lot तरी 1 lot, plan मध्ये `over_budget`); रिकामी Tier A targets ⇒ error message.
- **Golden test साठी निर्णय (M7):** T2/T7/T8 (must) Tier B आहेत आणि default sizing वर 0 lot. E4 मध्ये golden test signal + strike plan स्तरावर ("bot ने trade निवडला") तपासेल; sizing (₹) स्वतंत्रपणे report — default risk% बदलणार नाही (तुमचा निर्णय). `min_one_lot` ने ₹ परिणामही दाखवेन.
- नोंद (बदल नाही): `max_reentries`, `reentry_after_premium_stop`, `max_open_spreads`, `max_daily_loss_pct`, `expiry_exit_time` हे E4 backtest loop मध्ये वापरले जातील; premium stop अशक्य (hard_stop_mult × credit ≥ width) असेल तर plan मध्ये `premium_stop_reachable = false`.

**Tests:** `tests/test_elliott_e3.py` (+28): expiry calendar (Tuesday/Thursday काळ, holiday shift, 2019 आधी monthly, मुहूर्त/weekend sessions, listing), golden दिवसांच्या expiries (T1/T2/T7/T9), DTE, lot सीमा, BS parity / IV, STT तारखा व बाजू, spec §10 strikes (22,150 / 22,250 / alternate ⇒ 22,150), bear call, sizing (Tier B default 0 lot), guard fail actions, BS delta guard, exit क्रम, premium stop bar close वि. intrabar, soft/lower reduce एकदाच, Tier A partial + progressive inv, Tier B C zone / fixed / acceptance trailing, bear call exits, expiry IV नसताना, exits entry settings ने block नाहीत.

## 2026-10-07 · Elliott E4 — backtest, baseline, golden checker, report → **G2 वर थांबलो**

**स्थिती:** trade-data मध्ये options data (bhavcopy / Upstox expired / golden 1m) **अजून नाही** ⇒ सगळे premiums **model premium** (Black-Scholes, IV = आधीच्या 20 पूर्ण sessions चा realized vol; उत्तर 4 (b)). Golden regression चालवता आला नाही (checker + test तयार, data आल्यावर आपोआप).

**काय केलं:**
- **`elliott/backtest.py`:** E2 signals → E3 plan → E3 exits. Entry fill = पुढच्या trigger-TF bar चा open; exit निर्णय bar close वर, fill पुढच्या bar च्या open वर (15:30 नंतर ⇒ पुढच्या session चा open, gap सह); emergency (strike cross) intrabar, gap असेल तर open वर; expiry-day तपासणी 5m घड्याळावर; उलट signal ची नोंद पुढच्या TTF close पर्यंत; premium मिळाला नाही ⇒ exit पुढे ढकल (खोटा नफा नाही); expiry close ला intrinsic settle (+ exercise STT); data संपताना उघडे trades "end_of_data". Entry filters (फक्त नवीन entries): max_open_spreads, daily loss (sized trades), एक trade प्रति setup-instance, soft/premium stop नंतर re-entry (max_reentries). Default sizing वर 0 lot ⇒ **shadow** 1-lot (₹ portfolio बाहेर, R तक्त्यांत). Guard आणि sizing slippage नंतरच्या credit वर. Signals एकदाच, variants replay.
- **`elliott/golden.py`:** expectations JSON नुसार must / must_not / verify / report आणि gap rejections; वेळ-खिडकी + दिशा + correction extreme ±15 + setup code / tier (JSON मध्ये असतील तर); must_not फक्त वेळ + दिशा.
- **`research/elliott_backtest_report.py` → `docs/reports/elliott_pullback_backtest.md`:** IS weekly काळ (11 Feb 2019 → 31 Dec 2021; 2015–2018 मध्ये weekly options नव्हते ⇒ फक्त spot-structure, E2 report). शेवटचे 7 दिवस entry embargo. VAL / holdout उघडले नाहीत.

**IS निकाल (model premium — अंदाज):** 199 signals.

| Variant | trades (sized) | win% | R सरासरी | CVaR5% R | ₹ (sized) |
|---|---|---|---|---|---|
| A default | 53 (16) | 22.6 | −0.019 | −0.09 | −1,526 |
| B guard बंद (निदान) | 145 (58) | 13.1 | −0.019 | −0.09 | −7,006 |
| C guard + progress बंद (निदान) | 151 (61) | 35.1 | −0.016 | −0.11 | −6,165 |

- **Default मध्ये 199 पैकी 127 signals credit guard ने अडले** (model premium वर credit/width बहुतेक 0.05–0.10 < c_min 0.06–0.12). c_min खऱ्या premiums वरूनच calibrate करता येईल (spec §8).
- **Progress-time exit** (mult 1.0 × शेवटच्या sub-leg चे bars) बहुतेक trades काही bars मध्येच लहान तोट्यात बंद करतो (A: 53 पैकी 37).
- **Entry तुलना (त्याच structure-free exits, filters बंद):** Elliott 197 trades R −0.022, win 62% वि. random 952 trades R −0.011, win 67%. **Model premium वर Elliott entry ला random entry पेक्षा फायदा दिसत नाही.**
- n < 30 मुळे setup/degree/DTE cells वर निष्कर्ष नाही.

**निर्णय (कारणासह):**
- **VAL चालवला नाही:** spec §13 — VAL फक्त IS मध्ये निवडलेल्या ≤ 3 configurations साठी; निवड G2 ला तुमची.
- **Variants B/C** pre-registered निदान — tuning/निवड नाही.
- **Golden = signal + strike-plan स्तर** (Tier B sizing 0 lot — E3 शोध — golden चा भाग नाही).
- **Random baseline:** inv-अंतर जुळवलं (spec चं "same delta/DTE" नाही) — नोंद.
- **अजून नाही (नोंद):** lower-degree inv warning आणि "पुढची motive पूर्ण" (thesis) ctx backtest मध्ये पुरवलेले नाहीत; D0 trades चा trailing D0 pivots वर (खाली degree नाही); calendar चा "पूर्ण session" निकष दिवसाच्या एकूण bars वरून (outage दिवसांवर 1-दिवस lookahead — नगण्य).

**स्वतंत्र review (1 High + 6 Medium + Low) — दुरुस्त्या:** gap मधलं emergency pricing; premium नसताना खोटा नफा (आता defer; लहान sessions ला आधीचा IV); exits पुढच्या open वर; expiry check 5m वर; उलट signal sticky; baseline दोन्ही बाजूंना सारखे filters; golden खोटे PASS (setup/tier, ±15, must_not किंमत-निरपेक्ष, gap 09:45); re-entry मर्यादा premium stop लाही; partial न झाल्यास परत; intrabar premium stop stop-level वर; end-of-data trades; slippage-नंतरचा guard/sizing; report मध्ये n<30, R mean/sd, §13 grid, start ≥ 11 Feb 2019, data policy filter.

**Tests:** `tests/test_elliott_e4.py` (+12; 1 golden-data test data नसल्याने skip): fill/exit वेळा (exit पुढच्या bar च्या open वर, 15:30 नाही), P&L/R मर्यादा, shadow ₹ बाहेर, truncation invariance, IV causal + बदलतो + लहान session, emergency gap pricing, daily loss ⇒ entries थांबतात पण exits चालू, re-entry नियम, random baseline, golden matcher (levels + कडकपणा).

## 2026-10-07 · Elliott C1 — candle merge: WaveContext → CandleProfile, composite सुधारणा, ARMED state machine (addendum §1–§3, §5, §6)

**कुठे बसतं:** addendum नुसार C1 = E2 सोबत (trigger), C2 = E1 सोबत (report-only leg features), C3 = E4 सोबत (variants + सांख्यिकी → `docs/reports/elliott_candle_merge.md`, **G2**), C4 = E5 dashboard मधला "Candle Trigger" विभाग (G1 नंतर). E0–E4 merged असल्याने C1 हा वेगळा PR; C2/C3 report पुढच्या PR मध्ये, मग G2 वर थांबणे.

**काय केलं (सगळं default OFF — defaults वर 2019 H1 चे signals व reasons E2 snapshot शी byte-for-byte सारखे):**
- **Settings (`candle` विभाग, 20 keys, सगळ्या `calibrate = False`):** `candle_profile_mode` off/shadow/on; profile संदर्भ (w4 / flat C / triangle E = own_correction, बाकी last_20); `profile_counter_extra` 0.05; `strength_ref` last_20/time_slot; `slot_median_sessions`; `strength_cap_mode` fixed/logic + `strength_risk_guard_mult`; `w_reclaim_depth`, `w_overlap`; `path_checks`, `n3_penalty`; `body_term_mode`, `min_body_or_reclaim`; `followthrough_mode` legacy/addendum + `followthrough_max_bars`; `c_leg_exhaustion_required`; `opposite_candle_action` watch/tighten.
- **`reversal.py`:** blended label (hammer / shooting-star / marubozu / engulfing / piercing / dark-cloud / star-like — फक्त log); score parts log; path check (शेवटच्या candle ने स्वतः merged range चा > ½ परत दिला); cap logic (रुंद candle: pullback दिशेने close ⇒ reject, level आत close ⇒ pass; पर्यायी risk guard); reclaim depth (stab + आत close, × median); overlap (आधीचे 3 bars); n3 penalty; body_or_reclaim (piercing ≥ 50%) व dragonfly/gravestone किमान; addendum follow-through.
- **`trigger.py`:** `Signal.wave_ctx` (setup, degree, tier, vote, zone, hard_inv, pattern/wave, `zone_known_at`) आणि `candle_ctx` (N, composite, touched, strength, CL, parts, label, follow-through, profile); profile (A-end कधीच नाही — setups मध्येच block); ARMED state machine log (`IDLE → ARMED → (WAIT_FOLLOWTHROUGH) → TRIGGERED`, `→ EXPIRED`, EXPIRED नंतर re-ARM); `profile_log` (shadow मध्ये नकारही).
- **`backtest.py`:** उलट reversal candle (pullback origin H वर) ⇒ `notes` मध्ये एकदा नोंद; tighten ⇒ profit target निम्मा. **कधीच exit नाही.**
- **`settings.core_candle`:** real-break (failed retest) आणि Tier B C-zone reversal exit ला C1 settings defaults वर — candle प्रयोग counts / setups / exits बदलत नाहीत (ablation स्वच्छ).

**निर्णय (कारणासह):**
- **Profile admitted अपवाद फक्त wave 4 / triangle E (`w4`, `tri_e`) + own_correction** (addendum §2 शब्दशः). Expanded flat C ला own_correction संदर्भ असला तरी तो फक्त कमी करतो. **S6c** (B wave मधला triangle E) triangle E family मध्ये ठेवला (§2 तक्ता "Triangle E (S6)") — counter_extra लागत नाही; G2 ला तुम्हाला बदलायचं असेल तर एक ओळ.
- **Reduce-only पळवाट बंद:** profile on मध्ये generic निर्णयाचं dedup / hard-break bookkeeping वेगळं ठेवलं; generic ने dedup केलेला signal profile मधून येत नाही.
- **Profile मधला `last_20` = generic `strength_ref`** (time_slot on असेल तर profile लाही तोच).
- **time_slot:** 15m slot; प्रत्येक session चा त्या slot मधला median range → मागच्या 20 sessions चा median (चालू session वगळून); window-start bar ला `max(slot, median20)`. Causality test (पुढचे bars बदलले तरी मूल्य तेच).
- **Follow-through (addendum):** अनिर्णयी composite (CL 0.40–0.60; touch/reclaim/strength पास) नंतर ≤ `followthrough_max_bars` मध्ये close त्या composite च्या close पलीकडे ⇒ trigger; मधे hard_inv पलीकडे close किंवा मधेच trigger ⇒ नाही; score अनिर्णयी composite चा; T7 trigger मध्ये तसाच; stop-entry नाही. Score किमान लावला नाही — CL ≈ 0.5 composite चा score रचनेनेच कमी असतो, लावला तर follow-through जवळजवळ अशक्य (addendum ची व्याख्या थेट trigger).
- **Path check चा अर्थ:** "शेवटच्या candle ने merged range चा > ½ परत दिला" हे गणिताने CL < 0.5 असतानाच शक्य; त्यामुळे हा नियम फक्त 0.40–0.50 indecision band मधल्या, शेवटच्या candle ने परत दिलेल्या composites ना reject करतो (आधीच्या candle मुळे CL कमी असेल तर indecision / follow-through चालू).
- **C-leg displacement:** फक्त extreme नंतरचे पहिले bars (j − ext ≤ 1) थांबवतो — कायमचा block नाही.
- **ARMED log-only:** candle evaluation ARMED आधीही होतो (zone touch नसेल तर `no_touch`) — byte-identity साठी; FILLED backtest trade log मध्ये. "Zone सोडला" expiry नाही (count बदल / inv / gray ⇒ EXPIRED).
- **Settings hash** नवीन keys मुळे बदलतो (वर्तन तेच) — नोंद.

**स्वतंत्र review (5 Medium + Low) — दुरुस्त्या:** path check खरा "शेवटच्या candle चा give-back"; follow-through addendum प्रमाणे (re-gate नाही, gap-up चालतो, max_bars setting); reduce-only dedup पळवाट; admitted अपवाद family वर; C-leg कायमचा block; time_slot window-start + 15m + session-median; reclaim depth मध्ये stab; cap logic risk guard; EXPIRED → re-ARM, TRIGGERED नंतर WAIT नाही, WAIT → ARMED; break/exit मध्ये C1 settings गळती (`core_candle`); shadow profile log; opposite candle नोंद वेगळी व एकदाच; `calibrate = False`; body दिशा. कमकुवत tests मजबूत केले.

**Tests:** `tests/test_elliott_c1.py` (13): defaults byte-identity (E2 snapshot), contexts + state transitions (परवानगी असलेले संच), profile shadow/on (extras फक्त w4/tri_e admitted), path/n3/cap logic/guard, body/reclaim/dragonfly, weights, follow-through (gap-up, max_bars, legacy वेगळं), labels, C-leg, opposite candle (exits byte-same, एकदाच नोंद, tighten), time_slot/own_correction causality, profile families, `core_candle`. MCX (#241) candle code ला हात लावला नाही.

## 2026-10-07 · Elliott C2/C3 — candle merge variants, random-in-ARMED baseline, सांख्यिकी → **G2 वर थांबलो**

**काय केलं:** `research/elliott_candle_merge_report.py` → `docs/reports/elliott_candle_merge.md`. फक्त IS weekly काळ (11 Feb 2019 → 31 Dec 2021; script मध्ये IS assert), **model premium** (options data नाही), VAL / holdout उघडले नाहीत. Trading settings सगळ्या variants ना सारखे (credit guard बंद = E4 variant B, पूर्ण exits) — फरक फक्त candle settings चा.
- Variants: (a) generic, (b) profile on, c1 time_slot, c2 cap logic, c3 reclaim depth 0.10, c4 overlap 0.10, c5 path + n3 0.05, c6 body fix, c7 follow-through addendum, c8 C-leg wait, c_all (c1–c7), (d) b + c_all. Variant निकाल cache मध्ये (key = settings + trading settings + काळ + code hash) — container restart नंतर पुढे चालू.
- (r) random baseline: (a) चे सगळे ARMED episodes (re-arm सह; ARMED → पुढचा TRIGGERED/EXPIRED, कमाल 3 दिवस) — त्या setup च्या trigger TF वर 09:30–14:45 चे bars (episode ला कमाल 12), प्रत्येक bar ला **त्या वेळचा** setup (extreme / inv / alt invs) ⇒ strike, structure-free exits. तुलना **फक्त Elliott ने trigger केलेल्या episodes** वर; Elliott व random दोन्ही resample करून फरकाचा bootstrap CI.
- सांख्यिकी numpy मध्ये (scipy नाही): day-block bootstrap CI, PBO (CSCV, S = 16), White Reality Check (प्रति-trade R), Mann-Whitney (ties correction), score quintiles, blended label, bull/bear, tier, setup.
- C2: preferred counts चे completed legs (leg चं शेवटचं label) — impulsive वि. corrective; `disp_per_bar` (लांबी-निरपेक्ष) सह.

**IS निकाल (model premium — अंदाज):**
- (a) 199 signals, 145 trades, R −0.019 (95% CI −0.025 … −0.014). सगळे variants −0.018 … −0.020 — (a) शी फरक ±0.0013 R च्या आत.
- **PBO 0.62** (> 0.05), **Reality Check p 0.35** ⇒ कुठलाही variant योगायोगापेक्षा चांगला नाही.
- **Random तुलना (trigger झालेले 143 episodes):** Elliott (a) R −0.022 वि. random −0.010 ⇒ फरक −0.0125 (95% CI −0.033 … +0.008) ⇒ **Elliott entry random पेक्षा चांगली नाही** (वाईट असल्याचंही सिद्ध नाही). सगळ्या variants चं तेच.
- Score quintiles monotonic नाहीत (Q4 −0.013, Q5 −0.022). Profile on: 7 admitted signals, परिणाम नगण्य.
- **C2:** preferred counts मध्ये पूर्ण झालेली wave 5 / C जवळजवळ नाही ⇒ impulsive ≈ 1, 3, A; corrective ≈ 2, 4, B. Impulsive legs लांब (bars rank-biserial 0.36–0.63). Displacement **प्रति bar** फक्त D0 वर वेगळा (0.33), D1 कमकुवत (0.15), D2/D3 फरक नाही ⇒ "impulsive legs मध्ये displacement जास्त" हा मुख्यतः लांबीचा परिणाम. D0 overlap कमी. फक्त report.

**निर्णय (कारणासह):**
- **KEEP नाही:** KEEP = (a) पेक्षा (फरक > 0, PBO ≤ 0.05, RC p < 0.05) **आणि** random पेक्षा (फरकाचा CI > 0) चांगला **आणि** VAL मध्ये टिकला. एकही variant पहिल्या दोन अटी पूर्ण करत नाही ⇒ सगळे candle settings **off**. VAL चालवला नाही (§13: फक्त G2 ला तुम्ही निवडलेल्या ≤ 3 configurations).
- Random तुलना structure-free exits वर (दोन्ही बाजूंना सारखे); variant तुलना पूर्ण exits वर.
- Golden regression चालवता आला नाही (trade-data मध्ये golden 1m data नाही) — checker तयार.

**स्वतंत्र review (1 High + 5 Medium + Low) — दुरुस्त्या:** random baseline मध्ये trigger न झालेले episodes मिसळले होते आणि 95th percentile Elliott चा sampling noise धरत नव्हता (आता trigger झालेले episodes + दोन्ही बाजू resample); C2 displacement लांबीचा परिणाम (`disp_per_bar`, bars दाखवले) आणि 5/C legs नसल्याचं चुकीचं वर्णन; KEEP मध्ये PBO/RC; cache key मध्ये trading settings / code hash; random signals ला त्या वेळचा setup व trigger TF; re-arm episodes; MW ties; IS assert; report मजकूर (episodes, win%, रिकामे tiers). पहिल्या आवृत्तीत Reality Check रिकाम्या दिवसांना 0 भरल्याने p = 0.000 येत होता — प्रति-trade R वर दुरुस्त.

**Tests:** `tests/test_elliott_c3.py` (+7): Mann-Whitney (ties सह), day-block CI, PBO (खरा विजेता / noise), Reality Check (कमी trades ने फसत नाही), random तुलना (दोन्ही noise), LEG_KIND.

## 2026-10-07 · G2 निर्णय (तुमचे) — नोंद + S6c

1. **Candle settings:** एकही on नाही, सगळे off/shadow. कारण (तुमचं): progress-time exit (20–30 मि.) आणि model premium (IV = RV) मुळे ही चाचणी entry quality मधला फरक पकडूच शकत नाही. ⇒ E4 व C3 अहवालांचा निष्कर्ष **"Elliott/candle मध्ये edge नाही" असा नाही, "अजून मोजता आलं नाही"** असा. दोन्ही अहवालांच्या सुरुवातीला (आणि scripts मध्ये, पुन्हा चालवल्यावरही) ही टीप.
2. **VAL:** आत्ता नाही — खरे premiums आणि E4 review fixes नंतर.
3. **S6c** (B wave मधला triangle E) ⇒ B-end / counter profile गट (`counter_extra` लागू). C1 मधला माझा "triangle E" निर्णय बदलला; test सह.
4. **पुढचा क्रम:** (a) TRADE_E4_REVIEW_FIXES.md मधले F1–F7, F9–F11 (data नको) — defaults: `sizing_mode = tier_of_A` (Tier B किमान 1 lot), `progress_mode = off`, `break_confirm_tf = degree TF`, H fallback ⇒ skip; (b) VPS export नंतर F8: bhavcopy premiums/IV वर E4 + C3 + golden पुन्हा, bull put / bear call स्वतंत्र, random baseline ≥ 1,000 त्याच ARMED zones मध्ये; (c) मग G2 पुन्हा; E5 dashboard त्यानंतर. LIVE ला हात नाही, PAPER default, VAL/holdout बंद.
- **थांबा:** TRADE_E4_REVIEW_FIXES.md हा file या session मध्ये पोचला नाही (uploads मध्ये नाही) ⇒ F1–F11 चे नेमके तपशील मिळेपर्यंत (a) सुरू केलं नाही.

## 2026-10-07 · E4 review fixes — PR 1: F1 sizing, F3 H fallback, F4 confirmation TF (correctness)

**F1 — Sizing (Critical):** नवीन `sizing_mode` = **`tier_of_A`** (default, तुमचा निर्णय): Tier A lots = risk budget ÷ प्रति-lot तोटा (**किमान 1**), मग Tier B/C = round(A × tier गुणक) पण किमान `tierB_min_lots` (1) / `tierC_min_lots` (0); गुणक 0 ⇒ skip. `risk_budget` = जुनं वर्तन (पर्याय). ₹10 लाख, 1%, lot 65, credit 8 ⇒ A 1 / B 1 / C 0 (आधी B, C दोन्ही 0 ⇒ golden T2/T7/T8 सारखे Tier B कधीच घेतले जात नव्हते). Tier A किंवा B किमान 1 lot मुळे budget ओलांडला तर plan मध्ये `over_budget = true` (report मध्ये वेगळं).
- **Tier A partial:** "half exit, trail rest" ला ≥ 2 lots लागतात. `lots_open ≤ 1` असताना T1 target वर **पूर्ण exit** (`tierA_target`) — partial कधीच लागत नाही. Dashboard (E5) वर "partial needs ≥ 2 lots" दाखवेन.

**F3 — H fallback (High):** D−1 pivot नसताना TTF वरचा "मागे चालत जाऊन high" fallback काढला. H = शेवटच्या sub-leg चा **confirmed origin** (D−1 confirmed pivot, नाहीतर TTF चा confirmed fractal pivot); सापडला नाही ⇒ signal skip, `reason = no_subleg_origin`. (2019 H1 मध्ये असा skip आला नाही; T7_breakout नकार 32 → 16, कारण H आता खरा origin.)

**F4 — Count आणि trade exit एकाच TF वर (High):** नवीन `elliott/confirm.py::ConfirmTF` + setting `break_confirm_tf` (default **`level_tf`**; पर्याय 5m / 15m). `level_tf` = fixed degree mode मध्ये `degree_tf[d]`; auto mode मध्ये wave start → आत्ता चा auto TF (trigger TF चाच 8–40 bars नियम; wave लांब होते तसा TF मोठा, कधीच लहान नाही). Count engine (`_valid`, invalidation log), trigger चा C2 (hard inv आधीच तुटला?) आणि backtest चा hard-inv exit — तिन्ही तोच `ConfirmTF` वापरतात ⇒ 5m वरच्या दोन कमकुवत closes ने 15m trade उघडा असताना count मरत नाही. Soft stop आणि parent invs trade TF वरच (timing; parent wave चा start signal मध्ये नाही — नोंद). `CountEngine` ला `confirm` न दिल्यास (research count report, E1 tests) जुनं degree-frame वर्तन.
- 2019 H1 snapshot (`tests/data/elliott_e2_signals_2019h1.json`) **पुन्हा तयार केला**: 30 → 33 signals (2 गेले, 5 नवे); count पातळीवर gray 8,852 → 9,105, no_count 15,075 → 14,790, next_not_motive 213 → 257. C1 चा "candle settings off ⇒ byte-identical" test आता या नव्या baseline वर.

**स्वतंत्र review (1 High + 4 Medium + Low) — दुरुस्त्या:**
- **H1 sticky:** auto mode मध्ये TF वेळेनुसार 5m → 15m बदलला की आधी मेलेला count "जिवंत" होत होता (किंवा उलट — मागचा break अचानक). आता प्रत्येक TF फक्त त्याच्या **सक्रिय काळात** (wave start व bar grids वरून ठरलेले spans) break confirm करतो; सर्वात आधीचा confirm ⇒ निर्णय sticky, deterministic, causal. Spans wave start नुसार memo (tf_for ~15 µs).
- **M1 inv मालक:** S7 चा hard inv parent/grandparent count चा ⇒ Setup/Signal मध्ये `inv_degree` + `inv_start_ts` (मालक count ची degree व चालू wave ची सुरुवात); C2, re-entry बंदी आणि backtest hard-inv exit तिथेच तपासतात. S6b / flat-B चा `B_extreme` count चा inv नाही (trade-only level) — तरी त्याच मालक wave च्या TF वर. Count इतर invs (R2, flat_b_max…) ने मेला तरी trade फक्त स्वतःच्या hard inv वर exit (count बदल ⇒ recount/सूचना) — नोंद.
- **M2 parent cascade:** parent (D+1) invs आता parent count च्या (`parent_start_ts`, D+1) confirmation TF वर.
- **M3 shadow:** `tier_of_A` मध्येही `min_one_lot` (backtest shadow) ⇒ Tier C 1-lot shadow trades परत मोजले जातात.
- **M4 performance:** spans memo; `confirm` मध्ये रूपांतर एकदाच.
- **Low:** `size_floor` कारण (`a_min_one` / `tier_floor` / `min_one_lot`) plan मध्ये — over_budget चं कारण वेगळं; Tier B/C किमान A पेक्षा जास्त नाही; half-up rounding (epsilon); `trigger_tf_mode = fixed` ⇒ confirmation TF = trigger TF; ConfirmTF ला caches constructor ने. **नोंद (बदल नाही):** r=1 fractal मुळे 1-bar sub-leg (bls 1) अजून शक्य — F2 (progress_mode off) नंतर परिणाम नगण्य, पुढे `swing_fractal_r` विचार; `invalidation.level_events` (फक्त tests) अजून trade TF वर; research count report (`CountEngine` without confirm) जुन्या degree-frame वर.
- Snapshot पुन्हा: 33 signals (sticky + मालक बदलानंतर संख्या तीच), gray 9,032, no_count 14,863, hard_broken_no_reentry 5.

**Tests:** `tests/test_elliott_fixes.py` (+8: F3 no-origin skip / fractal origin; F4 displacement 5m वि. false break 15m; acceptance (दोन कमकुवत closes); level_tf TF बदलूनही sticky; खऱ्या ConfirmTF वर count `_valid` आणि backtest `_hard_broken` प्रत्येक bar ला सारखे; fixed trigger mode; count/trade दोघे inv मालकाची degree/start वापरतात), `tests/test_elliott_e3.py` (sizing: tier_of_A A 1 / B 1 / C 0, risk_budget जुनं, era-wise lot 25/50/75/65 गुणोत्तर, floor कारणे, shadow min_one_lot).

## 2026-10-07 · E4 review fixes — PR 2: F2, F5, F6, F7, F9, F10, F11

**F2 — Progress / time exit (High):** नवीन `progress_mode` = **`off`** (default, तुमचा निर्णय — IS calibration पर्यंत) / `correction_time` / `legacy`. `correction_time`: घड्याळ correction च्या **टोकापासून** (Signal मध्ये `bars_from_extreme`), मुदत = `progress_ref` (correction = wave start → टोक TTF bars `corr_bars`; wave1 = correction आधीचा leg `prev_leg_bars`) × `progress_bars_mult`; exit **फक्त** spread तोट्यात असेल (mark > entry credit) **किंवा** entry नंतर नवीन टोक झालं असेल तर. `legacy` = जुनं (bars_last_subleg × mult; 5m वर 20–30 मि.). Soft stop real-break वरच लागतो (`cache.confirm_index` — एका close वर नाही) हे तपासलं; soft-stop exits चं hold-time वितरण व "नंतर नफ्यात गेले असते का" — F8 report मध्ये (खरे premiums सोबत).

**F5 — पूर्ण waves वर wick-basis (Medium):** R1 / R6 / R9 पूर्ण waves ना सुद्धा `count_inv_basis` (default real_break): wick पलीकडे पण खरा break नाही ⇒ count जिवंत; `wick` पर्याय काटेकोर. Equality ⇒ violation नाही (double bottom चालतो; आधी `<= 0`). पूर्ण-wave नियमाने count गायब झाला तर invalidation log मध्ये `R1_completed` / `R6_completed` / `R9_completed` (break_at नाही). Beam/hysteresis मुळे बाहेर गेलेले counts invalidation नाहीत ⇒ log नाही (नोंद). Break तपासणी F4 च्या ConfirmTF वर.

**F6 — Hard-coded आकडे settings मध्ये (defaults तेच ⇒ वर्तन तेच):** `w3_fib_targets`, `w3_not_short_ratio`, `w2_depth_band`, `w4_depth_max`, `alternation_min`, `flat_expanded_min`, `flat_b_classic_max`, `indecision_band`, `min_body_frac`, `widen_widths`, `full_session_min_bars`; **`similarity_balance_min` आता खरंच वापरला जातो** (आधी 1/3 hard-coded — default तोच). Dashboard (E5) वर हे settings दिसतील.

**F7 — Contract master (Medium):** `elliott/contract_master.py`: Upstox option contracts (`/v2/option/contract`) ⇒ expiries, lot (contract-wise — एका expiry मध्ये दोन lots ⇒ error), strike step. `expiry_book_for(mode)`: **paper / live ⇒ contract master अनिवार्य** (`ContractMasterMissing`), weekday नियम + holiday table फक्त backtest. Network fetch फक्त live/PAPER loop मधून (E6). **SENSEX** (BSE, Thursday) v1 मध्ये नाही — E5 dashboard वर स्पष्ट; नंतरचं काम.

**F9 — Golden (Medium):** T5 (1 Oct (iv)→(v) of 5, Tier C) `report` ⇒ **`must_not`** (Master §4 अपेक्षित नकार). त्याच दिवशी T4 (must) bear call असल्याने T5 ला `match_on: ["tier"]` — फक्त Tier C bear call FAIL. Golden regression data आल्यावर पहिलं काम (T1–T8, 5 Oct 09:50/10:15 A-end).

**F10 — C1 (Low):** S6c ⇒ counter (G2 PR मध्ये). Follow-through score अट पर्याय `followthrough_score_gate` (default बंद) + `followthrough_score_relax` (0.05): merged (N+k) window चा score ≥ rejection_min − relax. C3 मध्ये `c7b_followthrough_gate` variant (F8 run मध्ये दोन्ही मोजणार). ARMED फक्त log — E5 dashboard वर तसं लिहू.

**F11 — इतर (Low):** `tests/conftest.py` चे MCX / order_safety autouse fixtures app deps नसतील तर काही करत नाहीत ⇒ elliott tests स्वतंत्र. `data_policy.load_parquet` + `HOLDOUT_FILES`: `nifty50_daily_extension.parquet` वाचायला `HoldoutError`; test: elliott/research loaders हा file वाचत नाहीत. `docs/DATA_SOURCES.md` (1m CSV चा licence वापरकर्त्याकडून नोंद बाकी — अंदाज लिहिला नाही). Live loop मधले `same_setup_open` / `no_reentry` guards E6 (PAPER) मध्ये backtest चेच वापरणार — नोंद.

**F1 पूरक:** Dashboard (E5) वर "Tier A partial needs ≥ 2 lots".

**स्वतंत्र review (1 High + 4 Medium + Low) — दुरुस्त्या:**
- **H1 (F5):** पूर्ण-wave तपासणी pivot `lv_i` (origin) पासूनच्या TF spans वर होत होती, तर चालू wave असताना `_valid` violating wave च्या सुरुवातीपासून — auto-TF मध्ये वेगळे TF ⇒ 5m वर मेलेला count pivot confirm झाल्यावर 15m वर "जिवंत" (2019 H1: ~5.5k calls). आता दोन्ही **violating wave च्या सुरुवातीपासून** (pts[b−1]) — एकच निर्णय; test.
- **M1:** wick-only R1/R6/R9 (count जिवंत) नंतर तो level पुढच्या waves साठी सुद्धा inv (R1 origin, zigzag C मध्ये R6 origin, diag R9, wxy X_W_origin) ⇒ नंतर खरा break ⇒ count मेला. wxy "X ≯ W origin" सुद्धा `count_inv_basis` वर.
- **M2:** S7 ला (wave start = points[0]) `progress_ref = wave1` मध्ये आधीचा leg नाही ⇒ correction कालावधी (आधी 0 ⇒ exit कधीच नाही). "wave1" = correction आधीचा leg (S3/S6 मध्ये wave 3 / A) — नाव तसंच, अर्थ नोंदवला.
- **M3 (F9):** Master §4 चा Tier C नकार **sizing स्तरावर** (Tier C 0 lot) ⇒ T5 ला `check: "sized"`: golden evaluate ला `sized(sig)` दिलं तरच must_not; नाहीतर REPORT (signal स्तरावर खोटा FAIL नाही). F8 मध्ये plan सह golden चालवताना sized देणार.
- **M4 (F7):** mode case-insensitive + अज्ञात mode ⇒ error; book `source = contract_master`; `lot_for(master, expiry)` (table fallback नाही). Live/PAPER loop (E6) मध्ये `expiry_book_for` / `lot_for` / `strike_step` वापरणार — आत्ता backtest मध्ये नियम-book (नोंद). Upstox `weekly` flag असेल तर तोच.
- **Low:** F10 merged window आधीच नापास ⇒ gate नापास; settings validate: पट्टे उलटे नकोत, w3 Fib रिकामे नको, widen widths strike step च्या पटीत; conftest `ModuleNotFoundError` फक्त; research loaders `DP.load_parquet` मधून; `_why` मर्यादित. **नोंद (बदल नाही):** `new_extreme` sticky (तुमच्या "तोट्यात **किंवा** नवीन टोक" शब्दांनुसार); random baselines structure-free exits ⇒ progress exit नाहीच; `indecision_band` trigger विभागात (real-break retest मध्येही वापरतो — calibrate करताना लक्षात ठेवा); beam बाहेरचे counts log होत नाहीत; spec §9/§11 मधला progress मजकूर जुना (spec doc तुमचा — बदल केला नाही).

**Snapshot:** 2019 H1 पुन्हा (F5 + review): 33 → 36 signals; gray 9,032 → 9,057. `*_completed` invalidations 2019 H1 मध्ये नाहीत (चालू-wave तपासणी आधीच पकडते — आता सुसंगत).

## 2026-10-07 · Golden-file regression (खरा data) — T1–T8 + rejections, सगळे variants

**Data:** `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-06.csv.gz` (17:52 IST push; contaminated काळ — फक्त golden). `research/elliott_golden_report.py` → `docs/reports/elliott_golden.md`: E4 default + C3 चे सगळे 12 candle variants.

**निकाल (सगळ्या 13 variants मध्ये सारखाच):**
- **must T2, T3, T4, T7, T8 — FAIL** (जुळणारा signal नाही).
- must_not **T5 PASS, T6 (5 Oct 09:50/10:15 A-end) PASS**, R-gap-0928 / R-gap-1006 / R-1006-0940 PASS. T1 (verify), T9 (report) — signal नाही.
- Golden काळात (25 Sep – 6 Oct) E4 default ने एकच signal दिला: 29 Sep 14:35 D1 S9 Tier A bear call (golden यादीत नाही).
- T6 PASS चं कारण "A-end नियम" नाही तर त्या वेळी सगळ्या degrees gray (D0/D1/D2) / D0 S6b tf_bars_min — म्हणजे नकार योग्य, पण **कारण वेगळं**.

**निदान (bot ची बाजू — screenshot वाचनाची चूक नाही):**
- **कारणं must नुसार वेगळी:**
  - T2 आणि T3 ला मुख्यतः `D2:next_not_motive` आणि `D0/D1:no_count` — count आहे पण पुढची motive trade दिशेने नाही, किंवा count च नाही.
  - T4, T7 आणि T8 ला मुख्यतः gray (vote < 0.5).
- **D3 चा preferred count सगळ्या must वेळांना खाली-दिशेचा** (pattern दिशा −1):
  - T2: impulse / wave 3;
  - T3 आणि T8: flat / B;
  - T4 आणि T7: wxy / Y.
  - त्यामुळे तुमचं "5 संपली, A-B-C वर" वाचन engine कडे त्या वेळी parent म्हणून उपलब्धच नाही.
- **संभाव्य मूळ कारण: वरच्या degrees चा pivot confirm lag आणि strict cross-degree.**
  - 1 Oct 14:05 चा 22,217 low D1 ला 14:35 ला, D2 ला 15:10 ला, पण D3 ला 5 Oct 13:40 ला confirm झाला (T7 12:15 नंतर).
  - 30 Sep चा 22,809 high D3 ला 1 Oct 11:15 ला confirm झाला.
- **Review नोंदी (non-blocking, पुढच्या golden run मध्ये सुधारायच्या):**
  - (a) T5 चा `sized` तपास credit 0 धरतो. Tier C ला हा सर्वात कमी lots चा (PASS कडे झुकणारा) अंदाज आहे; खऱ्या credit ≥ ~23 points ला Tier C = 1 lot होऊ शकतो.
    या run मध्ये 1 Oct ला signal च नाही, म्हणून निकाल बदलत नाही.
  - (b) §2 मधली "5 Oct 09:45–10:20" कारणांची खिडकी T6 च्या grading खिडकीपेक्षा (09:30–10:55) लहान आहे.
  - (c) T5 चा तपशील sizing filter नंतर लिहिला जातो, त्यामुळे sizing ने वगळलेला signal "जुळणारा signal नाही" असा दिसेल.
(तपशीलवार degree views आणि pivot confirm वेळा अहवालाच्या §3 मध्ये.)

**निर्णय:** फक्त golden pass करण्यासाठी logic / swing settings (swing_atr_mult [1.5, 3, 6, 12], fractal r, cross_degree_mode, vote_min) बदलले **नाहीत** (master नियम). हा **G-निर्णय** तुमचा: degree scaling / confirm lag / cross-degree mode बदलायचा का, आणि कसा (IS वर calibrate, golden फक्त तपासणीसाठी). `tests/test_elliott_e4.py::test_golden_regression_on_real_data` आता trade-data असताना **FAIL** होतो (CI मध्ये data नाही ⇒ skip) — test skip/disable केला नाही.

## 2026-10-07 · Vision + Human-Eye — V0 (shadow / notify) → **G-V0 वर थांबणार** (पहिल्या दिवसाचा Telegram screenshot)

**काय केलं:**
- नवीन `vision/` package:
  - `store` (SQLite `data/vision.db`: signals, usage, settings + इतिहास, kv);
  - `config` (bot-निहाय settings, validation, `effective_mode`: LIVE ⇒ off);
  - `chart` (2-panel ~1000×700, signal पर्यंतच);
  - `signal_audit` (`signal_check_v1` structured JSON, cached system prompt, verdict नियम code मध्ये, 2रा audit फक्त confidence < 0.6, खर्च);
  - `hook` (bots साठी — फक्त QUEUED row, नेहमी None);
  - `worker` (cron, 55 s loop: expire → render → 15-मिनिट reuse → budget → audit → नोंद → notify).
- `notifications.send_telegram_photo` (outbound, कधीच raise नाही).
- Hook: `dynamic_sr_instant_trader.py`, `srv2_momentum_reversal_strategy.py` — सगळे gates पास झाल्यावर, entry च्या आधी, स्वतंत्र try/except मध्ये.
- `scripts/vision_v0_smoke.py` (खोटा TEST signal, order नाही), `docs/VISION_HUMAN_EYE.md`, deploy/README (cron ओळी).
- **§11 (PNG जतन, तुमचा 2रा prompt — सर्वोच्च प्राधान्य):**
  - `vision/images.py`: `_sent.png` आणि `_outcome.png` नावं, overwrite नाही (O_EXCL), sha256.
  - Worker आधी फाईल लिहितो, मग तीच परत वाचून vision आणि Telegram ला पाठवतो.
  - `vision/outcome.py`: POST-HOC chart, vision कडे नाही.
  - `scripts/vision_archive.py`: trade-data push, पडताळणी, marker, 90-दिवस cleanup, disk इशारा.
  - Dashboard पान `page_vision_human_eye.py` (ANALYZE).

**Tests:** `tests/test_vision_v0.py` (29) + `tests/test_vision_images.py` (12). Full suite: खाली commit मध्ये.
- reduce-only: hook नेहमी None; bots hook चा परिणाम वापरत नाहीत (AST).
- `vision/` कधीच order / exit modules import करत नाही, आणि exit modules मध्ये vision नाही.
- no-lookahead: भविष्यातला spike chart मध्ये नाही; चालू minute चा bar नाही.
- LIVE ⇒ off; V1 modes V0 मध्ये नाकारले.
- verdict नियम; API fail / refusal / अवैध enum ⇒ unavailable.
- budget संपलं ⇒ API call नाही, आणि Telegram इशारा फक्त एकदा. Key / model नाही ⇒ call नाही.
- 15-मिनिट reuse; stale ⇒ EXPIRED; smoke script end-to-end.

**निर्णय (कारणासह):**
- **Async worker, inline call नाही:** bot cron दर मिनिटाला ProcessLock सह चालतो. 20 s चा vision call inline केला तर entry उशिरा होते आणि पुढचा cycle अडतो.
  V0 मध्ये मताचा trade वर परिणाम नसल्याने तो वेगळ्या worker मध्ये. V1 मध्ये PENDING state याच queue वर बसेल.
- **Data स्थानिक SQLite (Supabase नाही):** bots, worker आणि dashboard एकाच VPS वर. V1 चा conditional `WHERE status='PENDING'` इथे सोपा आणि atomic.
  Trade repo public असल्याने DB आणि images `data/` मध्ये (gitignored).
- **V0 defaults:** NIFTY 5-Min Instant आणि 15M = notify, कारण G-V0 साठी पहिल्या दिवसाचा Telegram हवा. Pullback Credit Spread = off, कारण तो अजून फक्त preview पान आहे
  (PAPER bot म्हणून चालत नाही ⇒ hook ला जागा नाही). MCX आणि Elliott = off (तुमचा निर्णय).
- **Chart साठी Upstox 1m (14 दिवस) worker मध्ये fetch करून स्वतः resample:** bot कडचे candles पाठवले तर queue मोठी होते आणि 15M bot कडे 1H नसतो.
  1m वरून कापल्याने no-lookahead सिद्ध करता येतो (test).
- **Breakout tag:** 5-Min bot चे Breakout Entry trades सुद्धा vision कडे जातात (tag `breakout_entry`). तुमच्या नियमानुसार vision तिथे बहुधा disagree देईल —
  V0 मध्ये फक्त माहिती.
- **Outcome साठी trade जोडणी:** live_trades (local SQLite) मध्ये source = bot, symbol, entry_time signal च्या −1…+10 मिनिटांत, mode PAPER.
  Spot मध्ये SL / target साठवलेले नाहीत (ते P&L ₹ स्तरावर) ⇒ chart वर ₹ मजकूर म्हणून, रेषा म्हणून नाही.
- **Archive marker:** push नंतर `git fetch` करून remote मध्ये फाईल असल्याची खात्री झाल्यावरच. Cleanup marker मधल्या यादीशी जुळवतो — marker नंतर आलेली
  फाईल (उदा. उशिरा तयार झालेला outcome chart) असेल तर delete नाही.
- **Image मधला मजकूर इंग्रजीत:** vision ला जाणारा chart इंग्रजीत (font वर अवलंबून नको). Telegram caption मराठीत. (पुढच्या नोंदीत दुरुस्ती: Devanagari font असेल तर outcome chart मराठीत.)
- **System prompt cache:** ~570 tokens, किमान 512 च्या जवळ ⇒ cache होईलच असं नाही. खर्च नेहमी `usage` वरून मोजला जातो. `python3 -m vision.worker --usage` ⇒ पहिल्या दिवसाचं खरं मोजमाप (G-COST).

**Independent review (subagent):** blocking नाही. Should-fix सगळे केले:
- tests आता खरी `data/vision.db` भरत नाहीत (conftest autouse tmp DB);
- smoke फक्त स्वतःची row claim करतो;
- reuse साठी bot, role आणि breakout / directional प्रकार सारखा हवा;
- budget अंदाज `max_tokens` वरून, आणि API अपयशालाही सावध खर्च नोंद;
- `*.db-wal` आणि `*.db-shm` gitignore मध्ये; images आता `data/visual_audit/` (आधीपासून gitignored);
- bot ने पाहिलेली चालू 1m candle (`last_bar`) chart वर, त्यामुळे trigger touch दिसतो.
Nits:
- caption मध्ये setup प्रकार;
- hook चा DB timeout 2 s;
- Telegram HTML 400 ⇒ साधा caption;
- THINKING / EFFORT मूल्यांची नोंद;
- worker tests Chrome शिवाय.

**§11 independent review (2रा subagent):** blocking नाही. Should-fix सगळे केले:
- archive रोज सगळे अपूर्ण दिवस + मागचे 3 दिवस;
- outcome साठी DB चूक ⇒ error (no_trade नाही), read-only DB;
- trade जुळणी: entry ≥ signal, एक trade एकाच signal ला, मध्ये दुसरा signal असेल तर नाही;
- trade-data repo ची खात्री (`check_repo`);
- push आधी rebase;
- marker मध्ये sha256, blob-id पडताळणी, temp → link लेखन.
Nits:
- folder नसलेले दिवस वगळले; commit फक्त आपल्या फाईल्स; `ls-tree -z`;
- FAILED row मध्येही image path;
- reuse मध्ये मूळ image sha;
- पानावर IST तारीख आणि n/a निकाल;
- `mode='PAPER'`.
- **Model नावं repo मध्ये नाहीत:** किंमत तक्ता model family (haiku / sonnet / opus) नुसार; अचूक नावं फक्त VPS `.env` मध्ये.

**खर्च अंदाज (G-COST):** मध्यम model ⇒ ≈ $0.005–0.01 प्रति audit, ≈ $1.4–2.9 / महिना (10 signals/दिवस धरून). मर्यादा: $0.30 / दिवस, $5 / महिना.

**उघडे / पुढे:**
- G-V0: पहिल्या दिवसाचा Telegram screenshot आणि `--usage` आकडे.
- मग V1 (veto_then_confirm, inbound service, HMAC, drift guard, dry-run → G-V1), V2 (08:00 level audit), V3 (पान + अहवाल).
- F8 (bhavcopy pricer, stash `f8-wip`) V1 नंतर.

## 2026-10-07 · Elliott — कुठे थांबलो (तुमच्या सूचनेनुसार थांबवलं: golden regression, F8, golden निदान, count बदल)

- **Golden regression:** PR #265 (report-only: research script, अहवाल, WORK_LOG) तुमचा "थांबा" संदेश येण्याआधीच merge झाला होता. त्यात logic बदल नाही.
  त्यावर review च्या 3 non-blocking नोंदी आहेत: T5 sizing credit 0 धरतो, T6 कारणांची खिडकी अरुंद आहे, T5 तपशील sizing नंतर लिहिला जातो — वरच्या golden नोंदीत आहेत.
  5 must FAIL (T2, T3, T4, T7, T8) वरचा degree scaling / confirm lag / cross-degree चा G-निर्णय उघडा आहे.
- **F8 (bhavcopy premiums):** `elliott/bhav_pricer.py` (previous-day smile IV + BS) आणि `elliott/backtest.py` (emergency 1m cross minute) अर्धवट आहेत.
  **Trade main वर नाहीत.** ते private trade-data मध्ये `wip/elliott_f8_2026-10-07/` (README सह) जतन केले आहेत.
  बाकी: F8 report (bull put / bear call वेगळे, P&L ÷ credit, ₹ प्रति lot, random ≥ 1000), C3 real premiums वर, golden sized plan.
- **Count बदल / golden निदानावर पुढचं काम:** सुरू केलेलं नाही.
- **पुन्हा सुरू:** Vision V0 → V1 नंतर. क्रम: F8 (wip मधून) → G2 → E5.

## 2026-10-07 · Vision §11 — पूर्तता तपासणी + outcome chart मध्ये भर

**तुमचा §11 संदेश पुन्हा आला; बहुतेक भाग PR #266 मध्ये आधीच आहे:**
- `_sent.png` (O_EXCL, overwrite नाही) + sha256; vision आणि Telegram ला तेच bytes.
- Audit record सगळे fields सह. Human निर्णय, वेळ आणि drift guard चे कॉलम आहेत; ते V1 मध्ये भरतील.
- `_outcome.png` POST-HOC आहे आणि vision कडे जात नाही.
- Dashboard पान, filters आणि CSV.
- trade-data archive रोज रात्री, remote पडताळणी, 90 दिवसांनी cleanup फक्त पडताळलेल्या marker नंतर.
- Disk इशारा > 80%.
- Tests: unique नावं, sha, outcome ≠ vision, push आधी delete नाही.

**या PR मध्ये भर:**
- **Outcome chart वर मराठी "POST-HOC: vision ला पाठवलेली नाही":** फक्त machine वर Devanagari font (`fc-list :lang=mr`) असेल तर; नाहीतर इंग्रजी.
  आधीची नोंद "kaleido मध्ये Devanagari font नसतो" **चुकीची** होती — font machine वर अवलंबून असतो (sandbox मध्ये FreeSans ने नीट दिसलं).
- **SL / target खुणा:** SL / target P&L (₹) स्तरावर आहेत, spot मध्ये नाहीत ⇒ अंदाजाने spot रेषा काढल्या नाहीत (खोटी अचूकता टाळली).
  त्याऐवजी legs चे strikes (`legs_json`: SELL / BUY) रेषा म्हणून — credit spread चा नफा / तोटा याच सीमांवर ठरतो. ₹ SL / target मजकुरात.
- **Review (subagent):** blocking नाही. केलेले बदल:
  - strike 0 / NaN (MCX futures) वगळला;
  - y-range candles + जवळचे strikes पुरता; लांबचे strikes कडेला ↑ / ↓ खुणेने;
  - एकाच strike चे legs एका label मध्ये;
  - तारीख दुरुस्त केली.

**अजून बाकी (V2):** `morning_<symbol>_<tf>.png` — path helper (`vision/images.morning_path`) तयार आहे; सकाळचा audit V2 मध्ये.
**PNG आकार:** आपले charts ~90 KB (< 150 KB). Archive मूळ PNG जशीच्या तशी ठेवतो, compression नाही.

## 2026-10-08 · Elliott review fixes (PRs #254–#265 चा review) — PAPER/LIVE wiring आधी

**काय केलं:**
1. **Forced exits ला premium नसेल तर intrinsic नाही** (`elliott/backtest.py`):
   - Emergency आणि end_of_data साठी नवीन `_forced_debit` वापरला. क्रम: pricer → model price → पूर्ण width.
   - आधी intrinsic वापरायचो. Strike जवळ ते ≈ 0.05 येतं ⇒ जवळजवळ पूर्ण credit, म्हणजे सर्वात वाईट exit वर आशावादी निकाल.
   - Primary pricer `ModelPricer` नसेल (उदा. bhavcopy) तरच model fallback.
   - Full width ला closing खर्च short leg = width धरून.
   - `exit_price_src` trade row मध्ये नोंदवतो.
2. **Emergency exit bar च्या सुरुवातीच्या वेळी priced:**
   - Strike cross bar मध्ये कधीही होऊ शकतो. आधी bar_end ला price ⇒ bar भराचा time decay मिळायचा ⇒ 1-DTE वर तोटा कमी दिसायचा.
   - आता price bar start ला (conservative मर्यादा). Fill / P&L ची नोंद bar_end ला.
3. **Tier A "किमान 1 lot" आता setting:** `tierA_min_one_lot` = backtest_only (default) / always / never.
   - `plan_spread` / `size_lots_detail` ला `context` दिला. Default "paper"; Backtest आणि golden report "backtest" पाठवतात.
   - PAPER / LIVE मध्ये 1 lot चा कमाल तोटा capital × risk% पेक्षा जास्त असेल तर 0 lots (size_zero). त्यामुळे Tier B/C चा floor पण 0.
4. **Settings `trading_mode` आणि `live_approved`** (नवीन section "mode", spec B7):
   - Defaults: PAPER आणि false.
   - LIVE पण मंजुरी नाही ⇒ validate PAPER करतो (error सह).
   - `effective_trading_mode()` हा अनवैध dict साठीही सुरक्षित: फक्त `live_approved is True`.
5. **Backtest report variant C:** F2 नंतर `progress_mode` default off असल्याने जुना C (`progress_bars_mult = 0`) B सारखाच झाला होता.
   - C आता `C_guard_off_progress_on` (`progress_mode = correction_time`) ⇒ progress exit चा परिणाम दिसतो.
   - G2 note अद्ययावत केली (जुना "20–30 मिनिटांत बंद" दावा त्या वेळचा असल्याचं स्पष्ट).
   - **Report पुन्हा तयार केला — फक्त IS** (2019-02-11 → 2021-12-31). VAL / holdout उघडले नाहीत.

**नवीन IS निकाल (model premium, अंदाज):**

| Variant | n | Sized | R सरासरी | ₹ (sized) |
|---|---|---|---|---|
| A | 55 | 41 | −0.012 | −2,499 |
| B | 157 | 117 | −0.018 | −14,496 |
| C (progress on) | 156 | 117 | −0.018 | −13,847 |

- Signals 212 (जुन्या report मध्ये 199 — मधल्या F-fixes मुळे).
- Variants A / B / C मध्ये emergency / end_of_data exits **0** ⇒ तिथे fixes 1–2 चा परिणाम नाही. पण section 2 च्या structure-free तुलनेत breach झालेले trades emergency ने बंद होतात (EW ~4 / 208, random ~15 / 1014) ⇒ तिथे fix 2 (bar-start pricing) लागू. Section 2 आणि variants साठी exit कारणं + forced-exit premium स्रोत आता report मध्ये छापले जातात. Model primary असल्याने full_width कधीच लागला नाही (max-loss% 0).
- EW वि. random (structure-free exits): R −0.022 वि. −0.024 ⇒ फरक नाही.
- Golden: 5 must FAIL, आधीसारखेच.

**Tests:**
- e3: Tier A context (paper / live / backtest / always / never), plan_spread, mode settings.
- e4: pricer None ⇒ model fallback / full width, emergency bar-start pricing (exit निर्णय monkeypatch — 2019 नमुन्यात emergency exit नाही).
- एक जुना assert अपडेट केला: `size_lots_detail("A", …, 1e3, …)` आता backtest context मध्ये (1, "a_min_one"); default context मध्ये (0, "").

**Independent review (subagent):** blocking नाही. केलेले बदल:
- `min_one_lot` (shadow) सुद्धा आता फक्त backtest context मध्ये — PAPER / LIVE मध्ये risk cap मोडत नाही (test).
- Intrabar premium-stop चा gap price bar start ला (emergency सारखाच).
- `trading_mode` lowercase (spec मधलं `paper` / `live`) स्वीकारतो.
- WORK_LOG मधला "exits 0" दावा दुरुस्त केला (वर).
नोंद: `docs/reports/elliott_candle_merge.md` जुन्या pricing वर आहे (structure-free emergency exits) — पुढच्या C3 run मध्ये ताजा होईल.
Model fallback वापरला तर (bhavcopy primary) entry bhavcopy वर आणि exit model वर ⇒ reports मध्ये `exit_price_src` नुसार वेगळं दाखवायचं.

**नोंद:** trade-data मधला F8 WIP (`wip/elliott_f8_2026-10-07/backtest.diff`) emergency branch बदलतो ⇒ पुन्हा सुरू करताना या बदलांवर rebase करायचा.

## 2026-10-08 · Vision V1 — veto_then_confirm / auto_veto / human_confirm → **G-V1 वर थांबणार** (dry-run screenshot)

**काय केलं:**
- `vision/decide.py` (नवीन, pure): mode × verdict ⇒ APPROVED / REJECTED / PENDING_HUMAN + factor (≤ 1), timeout नियम, `scaled_lots` (floor, reduce-only),
  drift guard (4 नियम), callback HMAC (`v1|sid|A/R|hmac16`, `compare_digest`), approver ids.
- `vision/gate.py` (नवीन): bots साठी `entry_gate` ⇒ ENTER / HOLD / SHADOW. कधीच raise नाही (चूक ⇒ algorithm, पूर्ण size). V0 modes ⇒ आधीसारखं फक्त नोंद.
- `vision/store.py`: `vision_events` table (प्रत्येक transition ची नोंद), V1 columns (idempotent ALTER), conditional `transition()` (`WHERE status IN …`).
- `vision/worker.py`: V1 rows ⇒ `decide` ⇒ Telegram (बटणांसह chart); housekeeping: PENDING_HUMAN मुदत ⇒ timeout नियम, APPROVED / REJECTED ला bot `exec_window_min` मध्ये
  न पोहोचल्यास EXPIRED; DRIFT_REJECTED / EXPIRED ची Telegram माहिती. `chart.py` meta मध्ये `median_range` (drift guard साठी).
- `vision/tg.py` + `vision/telegram_bot.py` (नवीन): long-polling service, from.id + chat.id whitelist, HMAC, single-use, deadline, restart ⇒ EXPIRED,
  `/pending` `/today` `/vision`. `deploy/vision_telegram.service`.
- Bots (5-Min Instant, 15M): V0 hook च्या जागी gate. HOLD ⇒ `SKIPPED_VISION_PENDING` (hit / cooldown मध्ये नाही). Approve नंतर forced level ⇒ bot चे सगळे gates पुन्हा ⇒
  `lots = min(lots, gate.lots)`. Reject / drift ⇒ मूळ lots ने PAPER shadow trade (`<bot>_vision_shadow`, exits मूळ bot चे — `SHADOW_EXIT_PARENT_SOURCE`).
- `vision/config.py`: V1 modes आता चालतात, पण फक्त PAPER — bot `trading_mode` LIVE / अज्ञात ⇒ save नाकार (CLI, dashboard, Telegram). Runtime ला LIVE ⇒ off (आधीसारखं).
- Dashboard 👁 पान: ⚙️ Settings (LIVE / अज्ञात bot ला V1 modes दिसतच नाहीत) + बदल-इतिहास. `outcome.py`: shadow trades जोडतो.
- `scripts/vision_dryrun.py` (नवीन): TEST signal ⇒ बटणं ⇒ approve / reject / timeout / `--drift` ⇒ निकाल Telegram वर. **Order नाही** (trading_engine import नाही — test).

**Tests:** vision 67 → 91 (`test_vision_v1.py` 37: निर्णय तक्ता, reduce-only, HMAC / whitelist / replay / deadline / race, restart expiry, timeout, exec-window expiry,
drift guard, LIVE guard, dashboard, dry-run चे 4 मार्ग; `test_vision_v1_bot.py` 7: खऱ्या 5-Min bot सोबत HOLD ⇒ approve ½ ⇒ 1 lot, reject ⇒ shadow 2 lots,
LIVE अप्रभावित, notify लगेच, नाकारल्यानंतर notify ⇒ forced entry नाही, ½ × 1 lot ⇒ shadow, control). `test_vision_v0.py`: exit modules मध्ये vision नाही (AST), bots मध्ये gate lots फक्त `min()` मध्ये.

**निर्णय (कारणासह):**
- **Defaults अजून `notify`** — §10 नुसार NIFTY default veto_then_confirm, पण G-V1 (dry-run screenshot) आधी trading बदलायचं नाही. G-V1 नंतर तुम्ही `/vision vtc <bot>`.
- **Bot 10 मिनिटं थांबू शकत नाही** (cron, दर मिनिट नवीन process) ⇒ HOLD + DB state + पुढच्या cycle ला forced level. त्यामुळे entry च्या क्षणी bot चे सगळे gates
  (daily loss, kill switch, max-open, cooldown) ताज्या data वर पुन्हा चालतात — drift guard चा नियम 4 रचनेनेच.
- **`exec_window_min` = 5** (नवीन setting): approve नंतर bot च्या gates पैकी कुठलं तरी बदललं तर signal कायम उघडा राहू नये.
- **Shadow trade वेगळ्या source ने**: खऱ्या P&L / hit / max-open मोजणीत मिसळत नाही, पण नाकारलेल्यांचा निकाल (V3 random-veto तुलना) मोजता येतो.
- **Worker अपयश (V1 row) ⇒ unavailable सारखं**: signal अडकू नये; veto_then_confirm मध्ये तुम्हाला विचारतो, उत्तर नाही ⇒ algorithm.
- **Secret / approvers नसतील तर बटणं नाहीत** (caption मध्ये इशारा) ⇒ timeout नियम लागू — खोटी बटणं दाबता येऊ नयेत.
- `find_open_decision` role / दिशा न पाहता (bot, symbol, TF, level, दिवस) ने शोधतो; दिशा / breakout प्रकार बदलला ⇒ जुनी row EXPIRED, नवा signal.

**Independent review (subagent):** 2 BLOCKER + 7 SHOULD-FIX — सगळे दुरुस्त (प्रत्येकाला test):
- **B1 forced level ⇒ touch शिवाय पूर्ण-size entry शक्य होता** (नाकारल्यानंतर mode notify केला / gate ची DB चूक / जुने rows). आता `forced_levels` फक्त V1 mode +
  आजचे + exec_window आतले; forced call (`forced=True`) ला ENTER फक्त ताज्या APPROVED वरून, बाकी सगळं (mode बदल, चूक, row नाही) ⇒ HOLD
  `SKIPPED_VISION_FORCED_STALE`; bot मध्ये gate import / call अपयशी + forced ⇒ entry नाही. signal_log मध्ये `hit_type = VISION_FORCED` (touch म्हणून नाही).
- **B2 0-lot leg:** ½ × 1 lot ⇒ `ENTER(0, …)` होऊ शकत होतं (0-lot PAPER row; multi-account `max(1, …)` ⇒ 1 lot!). आता bots फक्त चालू legs चे lots पाठवतात
  (बंद leg = 0) आणि चालू leg 0 झाला ⇒ SHADOW.
- **S1** नाकारलेल्या bearish level वर खरा bullish touch ⇒ आधी bullish signal चुकीच्या row ला जोडून shadow व्हायचा. आता दिशा / breakout प्रकार वेगळा ⇒ जुनी row
  EXPIRED (shadow नाही), नवा signal.
- **S2** एकाच level वर दर touch ला नवा shadow + पुन्हा Telegram. आता `shadow_cooldown_min` (30, नवीन setting) मध्ये पुन्हा नाही (`SKIPPED_VISION_COOLDOWN`),
  आणि `<bot>_vision_shadow` उघडा असेल तर नवा shadow नाही (algorithm सारखंच: एका वेळी एक). जुना "shadow एकदाच" test दुसऱ्या level वर होता — दुरुस्त.
- **S3** worker बंद ⇒ bot कायम HOLD. आता `gate.resolve_due` (bot आणि worker दोघे): PENDING_HUMAN मुदत ⇒ timeout नियम; QUEUED / RUNNING `approve_window_min`
  पेक्षा जुने ⇒ "vision unavailable + उत्तर नाही" (veto_then_confirm ⇒ algorithm; human_confirm ⇒ skip). V0 चा 15-मिनिट expiry V1 rows ला लागत नाही.
  Housekeeping ची चूक नवे signals थांबवत नाही (try).
- **S4** worker चा `finish` आता conditional (`status = RUNNING` असेल तरच) — bot / service ने आधी ठरवलेलं overwrite नाही, दुसऱ्यांदा बटणं नाहीत;
  Telegram चूक निर्णय बिघडवत नाही.
- **S5** drift guard चे दोन नियम प्रत्यक्षात कधीच लागत नव्हते: invalidation `setup_json` मधून वाचतो; median range नसेल (chart अपयश) ⇒ spot च्या 0.10%
  (तपासणी वगळत नाही). Pullback origin: सध्याचे bots तो मोजत नाहीत ⇒ नियम 3 त्यांना लागू नाही (docs मध्ये स्पष्ट).
- **S6** पहिल्या V1 start ला अनेक processes एकाच वेळी `ALTER TABLE` ⇒ "duplicate column" चूक गिळली.
- **S7** बटणं जिथे जातात तो chat (notifications चा `TELEGRAM_CHAT_ID`) approvers मध्ये नसेल तर प्रत्येक दाब नाकारला जाऊन signal शांतपणे timeout ने जायचा.
  आता `tg.can_ask()` ⇒ बटणं नाहीत + caption मध्ये कारण; service सुरू होताना Telegram इशारा.
- Nits: forced तपासणी कधीच raise नाही; caption edit text संदेशावरही; dry-run चा signal चालू worker ने उचलला तरी चालतो; dry-run test चा नेहमी-खरा assert दुरुस्त.
- **Re-review:** blocker नाही. केलेले: shadow cooldown फक्त त्याच दिशा / breakout प्रकाराला (उलट दिशेचा खरा touch अडत नाही);
  मागच्या दिवसाचे न ठरलेले V1 rows शांतपणे EXPIRED (worker बंद होता ⇒ सकाळी संदेशांचा पूर नाही). Gate ने timeout / रद्द केलेल्या row चं Telegram बटण
  तसंच राहतं (दाबल्यास "आधीच ठरलं") — bot मार्गात network call नको म्हणून बदल नाही.
- **माहीत असलेल्या मर्यादा (बदल नाही):** APPROVED → EXECUTED हे option chain / strike-निवडीच्या आधी — ती अपयशी झाली तर निर्णय वापरला जातो पण trade नाही
  (`exec_note` / outcome `no_trade` मध्ये दिसतं). Supabase बंद असताना `bot_trading_mode` default PAPER वाचतो ⇒ LIVE bot साठी V1 mode save होऊ शकतो,
  पण runtime ला LIVE ⇒ vision off (trade वर परिणाम नाही). Outcome जुळणी EXECUTED साठी `executed_at` नंतरच्या trade वर (trade_id नोंद नाही).

**तुमचा निर्णय (2026-10-08, market चालू असताना):** LIVE trading बंद (फक्त PAPER) ⇒ **auto_veto आजच** NIFTY PAPER bots वर (5-Min Instant, 15M).
- नियम: agree ⇒ entry; gray / disagree / unavailable ⇒ skip (shadow) — म्हणजे `vision_gray_action = skip`, `vision_disagree_action = skip`,
  `vision_fail_action = skip`. Code चे defaults बदलले नाहीत (अजून notify / half / ignore) — हे VPS वर `vision.config set` ने, आधी actions आणि मग mode
  (मधल्या क्षणी gray ⇒ half होऊ नये म्हणून).
- Deploy नियमाला (23:30 नंतर / 08:00–09:00) तुमच्या सांगण्यावरून अपवाद. Bots / vision worker cron वर ⇒ `git pull` पुरे, restart नाही. VPS block आधी
  Supabase मधले सगळे strategy × symbol `trading_mode` आणि उघडे trades तपासतो: PAPER शिवाय काहीही (LIVE / LIVE_PAPER) ⇒ काहीच न बदलता थांबतो.
  `position_stream_monitor` (long-running, जुना code memory त) फक्त उघडा trade नसेल तरच restart; नाहीतर 15:30 नंतर. तोपर्यंत नव्या vision shadow trades चे
  exits cron `trade_monitor` (नवा code) करतो — खऱ्या trades चे exit नियम बदललेले नाहीत.
- Telegram: worker चा संदेश "✅ ENTRY मंजूर / ❌ ENTRY नाकारली — कारण", entry झाल्यावर bot चा नेहमीचा trade संदेश, drift ⇒ "❌ ENTRY नाकारली (drift guard)".
  auto_veto ला बटणं / `vision_telegram` service लागत नाही.

**उघडे प्रश्न (G-V1 ला):** dry-run screenshot (approve / reject / timeout); मग कोणत्या bots वर `veto_then_confirm`. त्यानंतर V2 (08:00 level audit).

## 2026-10-08 · Vision prompt v2 + v2.1 (`signal_check_v2_1`) — chart overlays + gap संदर्भ + line panel + playbook prompt + JSON + code verdict नियम

**काय केलं (TRADE_VISION_PROMPT_V2):**
- `vision/context.py` (नवीन, causal): major levels (`price_action/major_levels.py`, asof = signal), PDH / PDL / PDC, PWH / PWL (आधीचा पूर्ण दिवस / आठवडा),
  open + opening range, confirmed swings, room, वेळ flag, gap, expiry, जवळचे overlays एका label मध्ये.
- `vision/chart.py`: v2 overlays (labels इंग्रजीत, collision टाळून, बाहेरचे ▲ / ▼), meta मध्ये `ctx`.
- `vision/signal_audit.py`: `signal_check_v2` playbook system prompt (cached), JSON v2 schema, signal text v2 (अचूक किंमती), नियम-आधारित verdict
  (`DISAGREE_RULES` / `GRAY_RULES`, settings ने on/off), `max_tokens` 1200.
- `vision/config.py`: `v2_disagree_rules`, `v2_gray_rules` (validated). `vision/worker.py`: 21 दिवस 1m (major levels साठी), expiry list, v2 caption,
  `vision_json` मध्ये `context` + `rule_hits`; reuse फक्त त्याच prompt version चं. Dashboard: v2 fields, version filter / गट, नियम on/off.
- `scripts/vision_v2_samples.py` (नवीन): शेवटचे 3 signals v2 ने पुन्हा (JSON + code verdict), vision_signals ला हात नाही.

**Tests:** `tests/test_vision_v2.py` 40 — context no-lookahead (भविष्यातला spike ⇒ संदर्भ तसाच), PDH / PWH आधीच्या पूर्ण दिवस / आठवड्याचे (आजचा spike
नाही), OR पूर्ण / अपूर्ण, swings confirmation, वेळ flags, प्रत्येक disagree (8) आणि gray (8) नियम (vision agree असला तरी; नियम बंद ⇒ लागू नाही),
अवैध enum ⇒ unavailable ⇒ auto_veto skip, request v2 + cached + text मध्ये अचूक किंमती, v1 records reuse नाहीत, labels merge, caption, dashboard,
samples script. जुने v0 / images tests v2 JSON वर अद्ययावत.

**निर्णय (कारणासह):**
- **v2 थेट auto_veto वर** (तुमचा निर्णय: पहिला दिवस, v1 data नाही; v1 + v2 shadow म्हणजे दुप्पट खर्च).
- Major levels 15m bars वरून (worker कडे 1m आहे; 15m हा bot चा swing TF) आणि 21 दिवस (spec 2–8 आठवडे; Upstox 1m fetch हलका ठेवायला).
  नसतील तर "bot चे इतर levels" — worker कडे ते नाहीत ⇒ तेवढे overlays कमी (text मध्ये दिसतं).
- Composite reversal box नाही: bots trigger चा N सांगत नाहीत (spec: "N कळत असेल तर").
- `level_real = no` हा नियम-यादीत नाही (spec प्रमाणे) — vision चा स्वतःचा verdict तो पकडतो.
- **नमुना JSON sandbox मधून नाही:** इथे API key / network नाही. 3 charts + signal text (2021 IS data) दाखवले; खरे v2 JSON VPS वर
  `vision_v2_samples.py` ने (≈ $0.03), auto_veto चालू करण्याआधी त्याच block मध्ये.
- **Samples script exit 2** (model असूनही एकही वैध JSON नाही) ⇒ deploy block auto_veto चालू करत नाही — नाहीतर key / model / max_tokens चूक असताना
  fail_action = skip मुळे सगळे PAPER signals skip झाले असते.

**Independent review (subagent):** 1 BLOCKER + 7 SHOULD-FIX — दुरुस्त (प्रत्येकाला test):
- **B1 gap दिवशी agree ⇒ unavailable ⇒ skip:** `gap.filled` numpy bool ⇒ `vision_json` JSON चूक ⇒ worker चा except. आता `bool()` + `store.finish` ला
  numpy-safe `default`; gap-down / gap-up (भरलेला / न भरलेला) सह worker-level test (agree ⇒ APPROVED, ctx request मध्ये).
- **S1** ≥ 10 जवळचे labels ⇒ `StopIteration` ⇒ chart नाही ⇒ skip. आता शेवटचा slot. **S3** tz-aware signal_ts ⇒ naive IST.
- **S2** संदर्भ (ctx) अपयशी ⇒ text "Room: no opposing level" म्हणायचा (agree कडे झुकवणारं). आता "Context unavailable" आणि room = unclear ⇒ gray.
- **S4** नियम model ने तथ्य पुन्हा लिहिण्यावर अवलंबून होते. आता code ची तथ्यं लादली जातात (`apply_facts`, फक्त कडक दिशेने): पहिली 15 मिनिटं ⇒
  time_risk = opening (disagree); पुढचा विरोधी level < 1 × median range ⇒ room = tight (gray). `code_overrides` नोंद.
- **S5** कमी-confidence agree + दुसरा audit अयशस्वी ⇒ आधी agree (entry). आता gray.
- **S6** caption 1024 वर कापताना ENTRY ओळ / HTML तुटू शकत होती ⇒ निर्णयाची ओळ दुसऱ्या ओळीत, कापणी पूर्ण ओळींनी.
- **S7** `max_tokens` 1200 + thinking ⇒ max_tokens संपले ⇒ unavailable: deploy block thinking env दाखवतो आणि samples step (exit 2) हे पकडतो; docs 2000 → 1200.
- Nits: `L+PDL+PWL` label ("PDPWL" bug), बिघडलेली settings row ⇒ defaults (कुठलीही चूक), reuse मध्ये context या signal चा, samples मध्ये फक्त खरे bots.
- तसेच राहिलं (कारण): swing शेवटच्या अपूर्ण setup bar ने "confirmed" होऊ शकतो — causal (भविष्य नाही), बदल नाही; "दोन audits असहमत ⇒ gray"
  settings मध्ये बंद करता येत नाही (सुरक्षित बाजू); system prompt ~1.6k tokens — काही models चं किमान cache prefix यापेक्षा मोठं असू शकतं ⇒ cache नाही,
  budget cache न धरता मोजतं (सुरक्षित).

**v2.1 + तुमच्या दुरुस्त्या (3 नमुने पाहून) — याच PR मध्ये (v2 अजून merge झाला नव्हता):**
- TRADE_VISION_V2_1_GAP_LINE: `vision/gap_context.py`, line panel (C), gap पट्टा / opening window / UG, playbook §9–10, JSON v2.1, gap नियम, event दिवस.
  `signal_check_v2_1`. G0 सीमा IS वरून मोजली (|gap_atr| p50 = 0.247 ⇒ 0.25; p90 = 0.628 ⇒ मोठा gap 0.63) — फक्त IS 2015–2021 वाचलं.
- तुमच्या दुरुस्त्या: today_role (levels तक्ता + chart labels), L ची ओळ, एकाच किमतीचे levels एका ओळीत, room फक्त न तुटलेले + tight नाव, INV नेहमी,
  composite box, sH / sL, gap पट्टा + line panel, नियम 4.
- **नियम 4 बद्दल निर्णय (कारणासह):** "broken_down + bear call ⇒ breakout" शब्दशः लावला तर (अ) नमुना 2 पकडला जात नाही — signal च्या क्षणी PDH खाली real
  break (buffer सह close) झालेलाच नव्हता (शेवटचा close 15,729.3 वि. 15,730.55); आणि (ब) नमुना 3 (PDL खाली गेला, मग 10:00 ला परत वर = spring) "broken_up +
  bull put ⇒ breakout ⇒ disagree" होतो — तुमच्या वाचनाविरुद्ध. म्हणून: (1) उघडण्याच्या बाजूकडे परतणारा break = reclaim, breakout नाही; (2) bear call पण किंमत L वर
  **वरून** आली (bull put खालून) = pullback नाही ⇒ breakout. परिणाम (vision काहीही म्हणो): नमुना 2 ⇒ code disagree ✓; नमुने 1 आणि 3 vision च्या मतावर
  (code त्यांना जबरदस्ती disagree करत नाही — तुमचं वाचन disagree / gray हे vision ने पकडायचं; JSON VPS वर `--historical`).
- **Bug (स्वतः सापडलेला):** `validate` सगळे enums lowercase करत होता ⇒ gap_setup "A/B/C" उत्तर ⇒ unavailable ⇒ auto_veto skip. Case-insensitive केलं (test).
- **Gap-module prompt (TRADE_GAP_CONTEXT_MODULE_PROMPT) अजून नाही:** त्याचा क्रम "vision v2 / v2.1 deploy नंतर" — पुढचा टप्पा (G-GAP1 पासून).
- **नमुन्यांचं vision JSON sandbox मध्ये नाही** (API key / network नाही) — VPS block `--historical` ने 3 JSON छापतो आणि auto_veto आधी तुमचं "yes" मागतो.

**v2.1 independent review (subagent):** lookahead नाही; 1 BLOCKER + 7 SHOULD-FIX — दुरुस्त:
- **B1 daily trend बहुतेक "unclear"** (1m फक्त 21 दिवस ⇒ < 15 पूर्ण sessions ~61% दिवस) ⇒ G2 / G3 / G5 आणि gap_chase / gap_b_pdc_accept कधीच नाहीत. आता worker
  daily candles (120 दिवस, एक call) नेहमी आणतो; ATR14 / trend / leg त्यावरून (आजचा अपूर्ण daily candle वगळून). `trend_source` नोंद.
- **S1 setup A ला नियम 4 disagree देत होता** (gap-down, PDL वर परत, मग PDL ला वरून pullback). नियम 4 परिष्कृत: break **आणि** किंमत break च्या मूळ बाजूने
  L वर येत आहे (chase) ⇒ breakout; break नंतर उलट बाजूने retest = pullback. ⚠️ हा तुमच्या शब्दशः नियम 4 पेक्षा वेगळा — तुमचा निर्णय हवा.
- **S2 break अपूर्ण शेवटच्या bar वर ठरत होता** (उदा. नमुना 1: PWL फक्त 10:30 च्या 1-मिनिटाने "broken" ⇒ room मधून गायब ⇒ tight room चुकला).
  आता break / PDC acceptance फक्त पूर्ण bars वर; अपूर्ण bar फक्त reclaim नाही हे पुष्टी करतो. परिणाम: नमुना 1 ⇒ PWL held, room 0.30× ⇒ code gray;
  नमुना 3 (10:01) ⇒ 10:00 चा reclaim bar अपूर्ण ⇒ L "broken_down at 09:45", पण text मध्ये "price is now above L".
- **S3 room मधून flip झालेले levels गायब:** तुमच्या सूचनेप्रमाणे room फक्त न तुटलेले, पण आता text मध्ये वेगळी ओळ "Broken (flipped) level in the trade direction".
- **S4** today_role आता आजच्या सगळ्या bars वरून (09:15 पासून), chart च्या शेवटच्या 60 bars वरून नाही.
- **S5** "कोणतंही unclear ⇒ gray" मधून line_structure / gap_class_agrees / line_vs_candles वगळले (skip दर विनाकारण वाढू नये).
- **S6** 15-मिनिट reuse मध्ये code तथ्यं (L break, PDC acceptance) नव्या संदर्भावर पुन्हा — जुनं agree आता कडक होऊ शकतं.
- **S7** samples script model नसतानाही exit 2 (deploy block auto_veto चालू करत नाही).
- Nits: prompt "three panels", विभाग क्रमांक, ATR नसल्यास "ATR unavailable" (G0 नाही), gap_undecided_early model च्या उत्तरानेही, line panel labels
  slots, OPEN = level असताना बाजू पहिल्या close वरून, dashboard वर gap सीमा, muhurat / opening-bar tests खरे केले.

**तुमच्या 4 दुरुस्त्या (v2.1 नमुने पाहून) — याच PR मध्ये:**
1. Room: तुटलेले (flip) आणि untested levels सुद्धा, फक्त magnet (आज ≥ 4 crossings) वगळून ⇒ नमुना 1 PWL 0.30× (tight), नमुना 3 PDC 1.89× ✓.
2. Deterministic नियम: `wrong_approach` (2a), 2b (signal bar / मागचे 3 bars नी trade दिशेने real break ⇒ breakout; signal bar अपूर्ण असला तरी — veto साठी
   आक्रमक, reduce-only), `role_conflict` (2c). आधीचा माझा "नियम 4 परिष्कृत / approach" logic काढला — तुमचे नियम त्याची जागा घेतात.
   **निर्णय:** 2b मध्ये उघडण्याच्या बाजूकडे परत येणारे breaks (reclaim) मोजत नाही — नाहीतर नमुना 3 मधला ORL चा 09:50 चा reclaim (spring चा भाग)
   breakout ठरून नमुना 3 disagree झाला असता (तुमचं वाचन gray). 2c फक्त held_* विरोध (तुमचा शब्द "held_as_support") — broken_* नाही, कारण नमुना 3 मध्ये
   PDL पूर्ण bars वर broken_down आहे (10:00 चा reclaim bar 10:01 ला अपूर्ण).
3. Gap वर्ग GX-inside / GX-beyond; text WITH / AGAINST / no clear trend; opening behaviour प्रत्येक बंद bar वर, इतिहासासह ⇒ नमुना 2: acceptance ✓.
4. `vision_v0_smoke.py --sample` (⇒ `vision_v2_samples.py --historical`): JSON + code verdict + खर्च + सारांश (तुमच्या अपेक्षेसह).

**Code-floor (vision "सगळं ठीक / agree" म्हणाला असता तरी):** नमुना 1 ⇒ gray (tight room), नमुना 2 ⇒ disagree (breakout ORL 13:10, wrong_approach,
role_conflict), नमुना 3 ⇒ agree. म्हणजे तुमचं अपेक्षित 1 disagree / 3 gray हे vision च्या मतावर — खरं JSON VPS वर पाहायचं.

**शेवटच्या 3 दुरुस्त्या (round 3) — याच PR मध्ये:**
1. Signal bar बंद नसणे: text मध्ये bar स्थिती; तक्त्यात "held until <शेवटचा पूर्ण bar>; current open bar is breaking it"; code: bar बंद नाही ⇒ reversal unclear ⇒
   gray; `vision_wait_for_bar_close` (default on) — worker bar बंद होईपर्यंत row QUEUED (क्लेम पुन्हा 5 s loop मध्ये), मग asof = bar close.
   Scripts (smoke / dry-run / samples) थांबत नाहीत (`wait_for_bar=False`) — नमुने मुद्दाम signal क्षणीच (तुमच्या अपेक्षेप्रमाणे "bar बंद नाही").
2. today_role "reclaimed" (break नंतर पूर्ण bar चा close परत opening side ला); role_conflict reclaimed ला लागू नाही. नमुना 3: L+PDL reclaimed at 09:55.
3. Code-only pre-verdict (`pre_verdict`): नमुना 1 = gray (unclear: bar बंद नाही, tight_room PWL 0.30×); नमुना 2 = disagree (breakout ORL 13:10,
   wrong_approach, role_conflict); नमुना 3 = gray (फक्त bar बंद नाही — live मध्ये wait_for_bar_close मुळे bar बंद झाल्यावर vision ठरवेल).
   `vision_v0_smoke.py --sample` output: code pre-verdict + vision JSON + अंतिम verdict + खर्च + सारांश.

**"Live प्रमाणे" नमुने (bar close नंतर):** `vision_v0_smoke.py --sample --bar-close [--no-telegram]` — मूल्यमापन signal bar बंद झाल्यावर (10:35 / 13:15 /
10:05), chart व संदर्भ तिथपर्यंत, आणि entry च्या क्षणीचा drift guard (signal spot वि. bar close spot). Code pre-verdict: नमुना 1 = gray (room tight
0.18× — bar close spot वरून, drift ✅), नमुना 2 = disagree (L+PDH आणि ORL 13:10 ला पूर्ण bar वर तुटले ⇒ breakout; wrong_approach; drift ❌ 15,702 वि. 15,729), नमुना 3 =
agree (L reclaimed 09:55, bar बंद, drift ✅ ⇒ vision ठरवेल). VPS वर हे फक्त वेगळ्या `git worktree` मधून, तात्पुरत्या DB / image dir सह चालवायचं
(live checkout / bots / worker ला हात नाही, Telegram नाही) — फक्त 3 vision calls.

**Independent review (round-3 code) च्या दुरुस्त्या — याच PR मध्ये:**
- **B1 (blocking):** bar-close wait चालू असताना V1 चा QUEUED/RUNNING timeout `created_at` पासून मोजला जात होता ⇒ 15M/30M/60M signal bar बंद होण्याआधीच
  "vision unavailable" ठरून (veto_then_confirm मध्ये) vision शिवाय entry. आता `gate.stale_base` = max(created_at, signal bar बंद) — `resolve_due` आणि
  `forced_levels` दोन्हीत. V0 चा `expire_stale` सुद्धा bar-aware.
- Signal bar 15:30 ला clamp (60M 15:15 bar ⇒ 15:30, 16:15 नाही); bot ने दिलेल्या चालू candle (`last_bar`) वरून bar ठरवणं (signal_ts 10:35:05 ⇒ 10:35 bar).
- Bar बंद झाल्यावर शेवटची 1m candle data मध्ये नसेल तर कमाल +2 मिनिटं पुन्हा थांबणं (मग जे आहे त्यावर).
- Bar-close मूल्यमापनात spot = bar close (levels / room त्यावरून; text मध्ये signal spot वि. evaluation spot दोन्ही). ⇒ नमुना 1 room 0.18×.
- Reclaimed level "recent breakout" यादीत नाही (signal text आणि breakout नियम सुसंगत).
- Deferral ⇒ `store.requeue` (RUNNING→QUEUED, event / Telegram नाही — आधी प्रत्येक 5 s ला event row); claim_queued limit 20.
- Tests: 15M stale timeout bar-aware, 60M expire_stale, 15:30 clamp, last_bar, data-completeness re-defer, quiet requeue, reclaimed ≠ breakout.
- दुसरा review (या दुरुस्त्यांवर): tz-aware `signal_ts` ⇒ worker मध्ये naive वि. aware तुलना crash (⇒ unavailable ⇒ vision शिवाय entry) — दुरुस्त + test;
  bar-close spot फक्त data bar close पर्यंत असेल तर (नाहीतर signal spot); `claim_queued` आधी bar बंद झालेल्या rows (थांबलेल्या ≥ 20 rows नवीन rows
  उपाशी ठेवत नाहीत) + test; `expire_stale` मध्ये खराब created_at ⇒ crash नाही.
  **निर्णय (बदल नाही):** drift guard signal spot वरूनच मोजतो (तुमचं "signal spot वि. bar close spot" — नमुना 2 ❌); 60M वर bar बंद होईपर्यंतची हालचाल
  मोठी असेल तर entry drift मुळे नाकारली जाईल — हे reduce-only दिशेने, म्हणून ठेवलं. Bot च्या चालू candle (last_bar) वरून signal bar ठरतो (touch चालू
  candle वर होतो). `approve_window_min` ≥ 4 ठेवावा (bar close नंतर data साठी कमाल 2 मिनिटं + vision call).

## 2026-10-08 — Vision live deploy (veto_then_confirm, NIFTY PAPER) — PR
VPS वर 3 नमुने (bar close नंतर, खरा vision call): 1 disagree, 2 disagree, 3 gray (code agree; vision ने HTF downtrend पकडला) — Abhi च्या वाचनाशी जुळलं.
खर्च $0.040 / 3 calls, caching चालू, latency 4–6 s.

Deploy आधी 2 code दुरुस्त्या (Abhi चा नियम: agree ⇒ entry; gray / disagree / unavailable ⇒ skip; approver नसेल तर फक्त माहिती + auto_veto):
- `veto_then_confirm` timeout (`timeout_action = auto_veto`) आता auto_veto चेच नियम वापरतो: gray ⇒ `vision_gray_action`, unavailable ⇒
  `vision_fail_action` (आधी gray नेहमी अर्धा आणि unavailable नेहमी पूर्ण). Defaults (half / ignore) सोबत वर्तन तसंच; `timeout_action = skip` ⇒
  unavailable सुद्धा skip (reduce-only).
- Approver / बटणं नसतील (`TELEGRAM_APPROVER_IDS` / `VISION_CALLBACK_SECRET` नाही, किंवा chat approver यादीत नाही) तर worker 10 मिनिटं PENDING_HUMAN मध्ये न
  ठेवता **लगेच** timeout नियम लावतो — नाहीतर entry 10+ मिनिटं उशिरा आणि drift guard मुळे बहुतेक नाकारली गेली असती.
- `python3 -m vision.worker --shadow [YYYY-MM-DD]`: दिवसाचे V1 निर्णय + entry घेतलेले वि. नाकारलेले-shadow trades चा P&L (read-only).
- Worker latency: systemd service (`--poll 2`, तासाला restart ⇒ नवा code), cron fallback (process lock ⇒ एकच worker).
- Independent review नंतर: gate ची स्वतःची चूक (exception) + V1 + `vision_fail_action = skip` ⇒ HOLD (`SKIPPED_VISION_ERROR`, entry नाही) — आधी
  नेहमी algorithm चा पूर्ण-size entry ("unavailable ⇒ skip" नियम मोडत होता). `fail_action = ignore` ⇒ आधीसारखं. Deploy block mode बदलण्याआधी जुन्या
  उघड्या V1 rows (PENDING_HUMAN — आधीच्या नियमांचा timeout साठवलेला) EXPIRED करतो. Tests: unavailable / agree लगेच, can_ask चूक, stale + fail skip.

## 2026-10-08 — data_policy: CONTAMINATED 2026-10-08 पर्यंत (G-E1 पूर्वतयारी)
- Abhi चा निर्णय: Chart Reader ची 7 Oct 2026 "golden story" (आणि 8 Oct चा निकाल) Abhi ने आधीच पाहिली आहे ⇒ HOLDOUT ऐवजी CONTAMINATED
  (फक्त purpose="golden", illustration; tuning नाही; अंतिम holdout चाचणीतून वगळले). `CONTAMINATED_END` 2026-10-06 → 2026-10-08.
- VPS export (`research/elliott_vps_data.py golden`) आता 2026-07-01 → 2026-10-08 ची नवी file लिहितो (`NIFTY_1m_2026-07-01_2026-10-08.csv.gz`);
  जुनी 10-06 file (golden regression) तशीच.

## 2026-10-08 · G-E1a — Chart Reader (report-only) + Knowledge Base
**काय केलं** (`chart_reader/`, `docs/CHART_READER.md`, KB `docs/knowledge/KNOWLEDGE_BASE.md`):
- Evaluate = KB भाग B चे 8 टप्पे; गोष्ट [K#] tags सह. सगळी 12 साधनं (a–l) प्रत्येक वेळी उमेदवार (≥ 3 pivots ⇒ trendline उमेदवार नेहमी);
  active area K6.4; Fibonacci / C = A / channel ला गुण फक्त ठोस area सोबत.
- KB भाग D: नवीन पुरावे PB, LQ, VL, DV (RSI14, confirmed pivots), PT, TM, VX (`evidence.py`, `volume.py`) + A3 व्याख्यात्मक व्हेटो.
  Thresholds 60/45 आणि weights बदलले नाहीत.
- एकच व्याख्या (भाग G): impulse origin वरचा break = `elliott/breaks.py` real break; MR = 20 बंद bars (`levels_v2` सुद्धा 50 → 20);
  swings = `elliott/swings.py`; `legs.py` r_warn 0.75 → 0.80. Reversal = `elliott/reversal.py` soft (पुरावा).
- Futures volume (K10.3): collector आता front + पुढचा contract `_all` store मध्ये; causal continuous roll; slot-normalised `rel_vol` (20 दिवस).
  IS / VAL मध्ये volume नाही ⇒ VL फक्त PAPER scorecard मधून.
- Tests आधी (failing): evidence, grade, volume, evaluate (causal), areas targets; collector next contract.

**निर्णय (कारणासह, Abhi च्या मंजुरीसाठी):**
- Counter-move impulsive ⇒ PB −10 (पुरावा, grade C जबरदस्तीने नाही); structure अशा वेळी entry point देत नाही ⇒ entry नाही.
  Origin acceptance (real break) ⇒ व्हेटो. Major level acceptance ⇒ PB −10.
- **Target (टप्पा 7):** पहिल्या IS run मध्ये 44 A/B setups पैकी सगळे R:R < 3 (1:0.0–0.5) ने अडले — target म्हणून correction च्या आतले लहान pools
  (swing / equal, round, gap edge, PDC) निवडले जात होते. KB "पुढचा opposite area किंवा impulse चं टोक" ⇒ आता target = impulse सुरू झाल्यापासूनचं
  trade-दिशेचं टोक (सहसा impulse end; expanded flat ⇒ B), मग पलीकडचे ठोस HTF areas (a/b/c/d/k). मधले areas = obstacles (गोष्टीत नोंद).
- IS grade वितरण (400 pullback-end उमेदवार, Elliott सह): A 3.2% · B 8.2% · C 88.5% · entries 12; व्हेटो 17 (count स्पष्ट A-end/B 10, S6a बंद 7).
  Thresholds बदलायचे का — Abhi चा निर्णय (KB भाग D ⚠️).
- Reversal दिवस 2018-02-02 (LTCG budget): bull put बाजूचे 19 bars सगळे C, entry 0 ✓.
- Calibration (MR20; बदल नाही): MR20 ≈ median-50 (p50 0.998), ≈ 0.90 × ATR14. Equal-pool tolerance 0.10–0.50 MR मध्ये retest-reject दर सपाट
  (64.5–65.6%, baseline 68%) ⇒ 0.15 ठीक, edge नाही. Sweep: reclaim % खोलीसोबत घटतो (0–0.1: 96%, 0.5–1.0: 58%, > 1.5: 20%); reclaim
  झाल्यावर यश खोलीसोबत वाढतं ⇒ 0.1–1.0 band ठीक. Fibonacci ± 0.25 MR: pullback टोकं 30.5% वि. uniform null 31.1% ⇒ Fibonacci ला स्वतःचा edge
  नाही (KB भाग F शी सुसंगत; मोजपट्टीच).
- 7 Oct golden: trade-data export (VPS block) अजून नाही ⇒ अहवाल प्रलंबित.

- Independent review (high नाही) नंतर दुरुस्त्या: futures volume `load` दोन्ही files एकत्र (जुना इतिहास); flat चा B (impulse टोकाजवळ) "double top" म्हणून
  PT −10 नाही; VIX फक्त बंद bars; major HTF levels (degree ≥ 2, impulse पट्ट्यात) structure ला ⇒ "major level acceptance" आता चालतो; collector च्या
  नवीन पायरीचं अपयश front/index collection थांबवत नाही; MR = 0 guard; tz-aware timestamps.
  जाणीवपूर्वक ठेवलं: `legs.py` r_warn 0.80 (KB) ⇒ `level_strength` / `bot_view` / `leg_level_validation` च्या default LegConfig मध्ये 75–80% pullback आता
  MIXED (आधी DANGEROUS); PCS signal r_warn स्वतः देतो ⇒ बदल नाही. Roll नंतर 20-दिवस baseline जुन्या contract चा (खरा volume सलग ⇒ परिणाम लहान).
**उघडे प्रश्न:** thresholds (60/45) वितरणानुसार; IS उदाहरणांमध्ये (flat/triangle) entry नसलेले A (R:R < 3) — target नियम योग्य वाटतो का.

## 2026-10-08 · V-L0 — Vision-led नमुना चाचणी (टप्पा 0, TRADE_VISION_LED_PROMPT)
**दिशा (Abhi):** "Vision-led" entry — vision trade निवडतो; code आकडे आणि सुरक्षा पाहतो. कारण: G-E1a code grade आठवड्याला ~0.03–0.05 setups.
**काय केलं (`vision_led/`, `research/vision_led_sample.py`, live code नाही):**
- Candidates (सैल, high recall): impulse ≥ 3 MR + BOS, pullback ≥ 38.2% (origin अबाधित), 12 साधनांपैकी कोणत्याही area पासून ≤ 0.5 MR,
  बंद candle वर rejection (wick ≥ 0.4 किंवा CL ≥ 0.6), 09:30 नंतर; एकाच correction चे सलग bars ⇒ एक; cooldown 4 bars.
  24 Sep → 8 Oct (contaminated) dry-run: 11 candidates, त्यात 7 Oct 14:00 (golden window).
- `vision_led_v1`: chart (15M + code areas + trendlines तिरक्या, futures volume — rel_vol नसेल तर raw, 1H, line panel) + OHLC तक्ते (15M 60,
  1H 20) + code areas (id, साधन, पट्टा, touches) + तटस्थ facts (confirmed swings, PDH/PDL/PDC, gap, volume आकडे) + playbook (KB चा English
  सारांश, < 4k tokens, cache_control); temperature 0. **Anchoring नाही (Abhi):** code ची बाजू / grade / narrative vision ला दिली जात नाही
  (test: code side बदलला तरी मजकूर तंतोतंत तोच). **No-lookahead:** input chart / तक्ते decision bar च्या close पर्यंतच (runtime assert + test).
  JSON schema (trade, side, grade, area_id, story, entry/invalidation/target {price, ohlc_ref}, evidence, wrong_if).
- Code validation: प्रत्येक ohlc_ref OHLC मध्ये (± 0.1 MR), entry = decision bar चा close, invalidation = ref + 0.25 MR buffer, बाजू सुसंगत,
  R:R ≥ 3, पाच पक्के नियम, A3 व्हेटो, strike σ (माहिती). Annotated chart (entry bar पर्यंतच) + hindsight chart (पुढचे 2 दिवस, वेगळा);
  REJECTED ⇒ रेषा नाहीत. Telegram "🧪 SAMPLE — trade नाही": एका संदेशात दोन images (entry-वेळचा annotated + hindsight), caption मध्ये code side
  आणि vision side (≤ 20 संदेश; जास्त ⇒ A/B आधी + सारांश). अहवाल तक्ता: candidate | code side | vision side/grade | validation | R:R |
  hindsight, आणि 7 Oct golden ची स्वतंत्र नोंद (golden "पकडला" = vision ची bear call, code ची बाजू नाही). खर्च ≤ $1.50 (पुढचा call ओलांडेल तर थांबतो).
- PNG / JSON फक्त trade-data (`vision_led/<date>/`); public repo मध्ये फक्त अहवाल (मजकूर). Run VPS वर (API key, Telegram).
**थांबा-बिंदू V-L0:** अहवाल + Telegram नमुने पाहून Abhi ची मंजुरी; तोपर्यंत टप्पा 1 नाही.

## 2026-10-08 · C-V1 — CAS noise, एकच market state (F1–F4), cross-verification (TRADE_CODE_FIX_CROSSVERIFY_PROMPT)
**का (Abhi):** 7 Oct 14:00 candidate ला code ने bull_put दिली — 6 Oct ची तेजी (22,220 → 22,720, ~86% overlapping ABC) impulse धरली.
बरोबर वाचन: impulse 22,801 → 22,220, 22,801 protected LH अबाधित ⇒ trend down ⇒ bear_call.
**CAS (`opportunity_engine/cas.py`, setting `config.yaml` → `market_data.cas_window`):**
- NSE/CMTR/75479 (30 Jul 2026): CAS 3 Aug 2026 पासून (15:15–15:20 reference, 15:20–15:30 order entry, 15:30–15:35 matching). Data मध्ये
  रोज 15:15–15:28 index गोठलेला आणि 15:28/15:29 ला auction close ची उडी (6 Oct: 22,717.70 → 22,776.10). 3 Aug आधी (IS 2015–2024 सकट)
  असं काही नाही ⇒ `effective_from` 2026-08-03; window 15:15 ≤ bar start < 15:30. Hard-code नाही (DEFAULT फक्त circular चा fallback).
- `sessions.resample_nse / resample_nse_daily(cas=…)`: CAS bars चे OHLC वगळून high/low/close; पूर्ण CAS bins structure मधून काढले
  ("flat" पर्याय chart साठी); `official_close` (auction close) + `cas` flag. `daily_levels`: PDH/PDL CAS वगळून, **PDC = official close**
  (chart_reader areas, vision gap_context, vision_led facts). elliott/swings 1m frame, chart_reader daily frame सुद्धा. Futures volume
  bins (`opportunity_engine/volume.py`) CAS ने बदलत नाहीत (cas=False).
- Data tests: 6 Oct high 22,731.85 (TradingView ~22,731) · PDC 22,776.10 · session बाहेर bars नाहीत · outlier flag (range > 5 × मागचा
  non-flat median) 6 Oct 15:29 पकडतो, CAS वगळल्यावर शेवटच्या 15 मिनिटांत outlier नाही.
- F2 तपासणी: CAS उडी सकट chart_reader चा impulse 23,163 → 22,570 (चुकीचा) होता; CAS वगळल्यावर 22,809 → 22,217 (बरोबर). म्हणजे खोट्या
  high ने impulse / degree निवड बिघडवली होती. (6 Oct ची तेजी "impulse" ठरण्याचं मुख्य कारण मात्र counter_move_impulsive ⇒ reversal नियम — F2.)
**Market state (`market_state/`, F1):** candidates (vision_led), chart_reader आणि vision facts हेच वापरतात.
- F2 trend: 1H (setting 75m) swings (elliott/swings ATR × 1.5); protected = शेवटचा LL/HH बनवणाऱ्या leg ची सुरुवात; counter चाल protected चा
  real break (elliott/breaks.py) **आणि** नंतर HL/LH confirmed होईपर्यंत correction; break पण पुष्टी नाही ⇒ "testing" (side unclear).
- F3 impulse: displacement (body ≥ 1.5 MR, ≥ 60%) **आणि** कमी overlap (efficiency ratio ≥ 0.45 किंवा K10.1 overlap < 0.4 — KB चा 0.4
  NIFTY 15M वर लागू होत नाही: 7 Oct impulse 0.62 ⇒ **Abhi मंजुरी हवी**) **आणि** BOS, ≥ 4 MR; trend दिशेचा सगळ्यात ताजा. Correction:
  A / B / C (trade-degree swings; tentative B/C), retrace, origin real break ⇒ `origin_broken`.
- F4 side: HTF trend, HTF StructureTracker state (*_WEAK = त्याच दिशेचा इशारा) आणि Elliott vote — विरोध ⇒ "unclear" + कारण.
- chart_reader: `structure.read(ms=…)` (impulse + A/B/C market_state मधून; F2 नुसार फक्त origin real break = reversal, counter-impulsive /
  major acceptance = PB −10 धोका), `trend.read(ms=…)`, side unclear ⇒ entry नाही. `evaluate.frame` = `market_state.frame`.
- Areas: `sloping` आता शेवटच्या 16 आतल्या swings मधल्या जोड्यांतून सर्वोत्तम रेषा (touches, मग trade-degree touches, मग ताजेपणा) —
  7 Oct उतरती रेषा 28 Sep 22,855 / 30 Sep 22,809 / 6 Oct 22,732 / 7 Oct 22,718 (4 touches) सापडते. `active`: ताजे 3 bars + शेवटच्या 12
  bars मधलं trade-विरुद्ध टोक (12:00 चा rejection) ⇒ 14:00–14:45 active area = ती trendline.
- vision_led: candidates `market_state` मधून (ad-hoc `impulse_at` काढला), code side = F4 (vision ला दिली जात नाही), तटस्थ facts =
  market_state swings (15M + 1H). Prompt `vision_led_v2`: invalidation = idea जिथे चुकीची ठरते (active area / trendline पलीकडे);
  tight SL ला `invalidation_reason`; 1H तक्ता 70 bars (~10 sessions). Validation: दोन SL व्याख्या (reversal-candle / structural) + R:R,
  tight SL + कारण नाही ⇒ warning. Charts: annotated ≥ 10 sessions / anchors, vision area ठळक (trendline तिरकी + anchors), impulse origin
  रेषा, दोन SL रेषा, "SIM" watermark (grade chart वर नाही), CAS राखाडी + "CAS".
**Cross-verification:** V1 `docs/reports/kb_traceability.md` (KB → code → test → स्थिती + सुटलेल्यांची यादी) · V2 `tests/golden_chart_cases/`
(7 Oct 14:00–15:00 आणि 5–6 Oct; JSON फक्त, data trade-data मध्ये; दोन्ही pass) · V5 `tests/test_market_state.py` (truncation / future bars /
precomputed frames) · funnel C-V1 mode (`research/chart_reader_funnel.py`, `--legacy` तुलना; जुना अहवाल
`chart_reader_funnel_legacy.md`) + 7 Oct SL उदाहरण. V4 (40 LABEL CHECK) ची जागा **Backtest visual review** (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT,
Abhi 18:20) ने घेतली — हा PR merge झाल्यावर वेगळा PR.
**थांबा-बिंदू C-V1:** backtest visual review चं Abhi चं उत्तर — त्यानंतरच V-L0 run.

## 2026-10-08 · Visual audit: अपयशाचं कारण, vision budget, फक्त NIFTY
- **2026-10-08 चं अपयश (VPS log):** NIFTY 1H — overlay OK, पण त्याच frame चा levels-शिवाय (plain) chart render झाला नाही ⇒ स्वतंत्र वाचन FAILED
  "chart image नाही" (calls 1 ⇒ एकूण 7). Code path तोच ⇒ kaleido / Chrome चं तात्पुरतं अपयश (1 GB VPS). दुरुस्ती: render एकदा पुन्हा (2 s नंतर) +
  प्रत्येक प्रयत्नाचं कारण log मध्ये. बाकी 3 charts चा अहवाल गेला (वर्तन तसंच).
- आधीचा "काही charts चा audit अयशस्वी — log बघा" संदेश कोणता chart / का हे सांगत नव्हता. आता प्रत्येक अपयश (symbol, TF, overlay /
  स्वतंत्र / Supabase save, status, कारण) log, Telegram सारांश आणि error संदेशात. Render अपयश आधी शांत `None` ("chart image नाही") होतं — आता कारण log मध्ये.
  एका chart चं अपयश ⇒ बाकींचा अहवाल जातो (वर्तन तसंच). Chart न बनलेले TFs सुद्धा नोंदवले.
- खर्च: visual audit आधी vision budget मध्ये मोजला जात नव्हता. आता प्रत्येक chart चा खर्च `vision_usage` (task `visual_audit`) मध्ये.
  **Signals ला प्राधान्य (Abhi):** प्रत्येक chart आधी तपासणी — audit आज + अंदाज ≤ min(`visual_audit_daily_cap` $0.10, दैनिक budget −
  `signals_daily_reserve_usd` $0.20), आणि एकूण दैनिक ($0.30) / मासिक ($5). ओलांडत असेल तर chart वगळला (अपयश नाही). अंदाज = मागच्या खऱ्या chart
  खर्चाची सरासरी. Dashboard वर signals / visual audit वेगवेगळे + एकत्र, cap आणि राखीव dashboard वरून.
- Render (kaleido v1): आधी प्रत्येक `to_image` नवा Chrome सुरू करून बंद करायचा (8 charts ⇒ 8 launches). आता `KaleidoSession` — एकच Chrome server सगळ्या
  charts साठी, शेवटी (चुकीतही) cleanup; render अपयश ⇒ server restart + एकदा पुन्हा. Model claude-opus-5-5 तसाच (Abhi).
- Abhi चा निर्णय: visual audit मध्ये BANKNIFTY बंद — setting `visual_audit_symbols` (vision `_global`, default ["NIFTY"], dashboard वरून).
- 2026-10-08 चा run: 7 calls, 19,403 / 4,982 tokens ⇒ model claude-opus-5-5 (repo दर 4 / 20 $ per 1M) ≈ **$0.177** — आजच्या $0.30 पैकी 59%.
  NIFTY-only ⇒ साधारण निम्मा.

## 2026-10-08 · Backtest visual review + Golden Gallery G1–G6 (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT, TRADE_GOLDEN_GALLERY_PROMPT)
**का (Abhi):** backtest ची फक्त आकडेवारी ⇒ code ने chart चुकीचा वाचला का ते दिसत नाही. प्रत्येक निर्णय chart वर खुणांसह, घेतलेले **आणि
सुटलेले** trades; ✘ ⇒ golden test case. V4 (40 LABEL CHECK) ची जागा हा review घेतो. KB भाग H: 6 golden setups — खऱ्या NIFTY data मधून
उदाहरणं, Abhi निवडतो.
**Backtest review (`backtest_review/`, `research/backtest_review_run.py`, पान "Backtest Review"):**
- काळ: 1 Jul → 8 Oct 2026 (contaminated) आणि 1 Jan → 31 Mar 2024 (VAL शेवट); `elliott/data_policy` ने (holdout ⇒ HoldoutError; warm-up
  सुद्धा holdout मधून नाही). Logic पडताळणी फक्त; settings hash नोंद.
- प्रत्येक बंद 15M bar: market_state (impulse + correction ≥ 38.2%) ⇒ candidate ⇒ chart_reader.evaluate ⇒ ✅ ENTRY / 🟡 C / ✖ + reason
  codes (`RR<3`, `NO_AREA`, `SIDE_UNCLEAR`, `VETO_A_END`, `NO_REVERSAL`, `OPENING_WINDOW` …; रिकामा कधीच नाही). Trades: एका वेळी एकच
  position (आधीचा बंद होईपर्यंत नवीन entry नाही). Hindsight: target / SL / time (2–3 sessions), MFE / MAE.
- Charts: trade ⇒ 1H context (≥ 15 sessions; trend + protected, मोठे areas, trendline anchors, impulse / ABC, Elliott), 15M entry (entry
  bar पर्यंतच; impulse रंगीत, ABC + प्रकार, areas साधन नावासह, reversal candles ठळक, sweep, ENTRY / SL (कुठून) / TARGET / R:R / strike σ,
  grade + मुख्य पुरावे, CAS राखाडी), hindsight. दिवस ⇒ 1H + 15M (सगळे candidates + "code ची गोष्ट").
- पान: run / filter (फक्त trades / ✘ / न तपासलेले) / प्रगती; प्रत्येक दिवस / trade ✔ / ✘ / ? + कारण, दिवसासाठी "सुटलेला trade" (वेळ + side)
  ⇒ Supabase `backtest_review` (upsert; पुन्हा उघडल्यावर दिसतं). Telegram (--send): फक्त trades, "🔎 REVIEW", Approve नाही, दिवसाला ≤ 10.
- 7 Oct smoke run: 24 candidates; 09:30 bear_call (B) entry, 12:15 A (त्याच position मुळे trade नाही); उतरती trendline / ABC दिसतात.
**Golden Gallery (`backtest_review/gallery.py`, `research/golden_gallery.py`, पानावर "⭐ Golden Gallery" tab):**
- काळ: IS 2015–2021 + Jul–Oct 2026 (VAL नाही — नियम gallery मधून ठरणार; holdout नाही).
- G1–G6 detectors (market_state वर, सैल, फक्त बंद bars) ⇒ shortlist ⇒ evaluate ⇒ rank = code total + 5 × confluence (**hindsight नाही**) ⇒
  प्रति G ≤ 8 (वर्षं / दोन्ही बाजू / एका आठवड्यात एकच). Charts 1H + 15M entry + hindsight. Abhi: ⭐ / ✔ / ✘ + "वेगळा G" ⇒ `golden_gallery`.
  Telegram: प्रति G एक ("⭐ GALLERY", एकूण 6).
- Jul–Oct 2026 smoke: G1 2, G2 0, G3 4, G4 6, G5 2, G6 5 सापडले.
- Vision: playbook मध्ये G1–G7 मजकूर (`vision_led_v3`; G7 = KB नवीन आवृत्ती), JSON `setup_type` (G1–G7 / none); code candidates वर `setups` label. Images system
  prompt मध्ये नाहीत. "कसं दिसतं" ओळी Abhi च्या ⭐ नंतर.
- अहवाल: `research/review_report.py` ⇒ `docs/reports/backtest_visual_review.md` (✔ / ✘ / ? %, ✘ प्रकार ⇒ file:function, सुटलेले trades)
  आणि `docs/reports/golden_gallery.md` (प्रति G ⭐ / ✔ / ✘, hindsight फक्त माहिती).
**थांबा-बिंदू:** C-V1 (backtest review अहवाल) आणि G-GAL (Abhi ची निवड) — मग V-L0.
**क्रम बदल (Abhi 19:30, TRADE_KB_FULL_IMPLEMENTATION_PROMPT):** हा PR फक्त साधनं (code + page + tests). पूर्ण review (125 दिवस) आणि
Gallery runs **K-10** (10 random दिवस, KB दुरुस्त्यांनंतर) चांगले दिसल्यावरच. G7 detector KB दुरुस्ती PR मध्ये (gap नियमासोबत).

## 2026-10-08 · Review charts ⇒ Telegram (VPS वरून) + ✔ / ✘ replies ⇒ backtest_review
**का (Abhi):** K-10 / Golden Gallery / backtest review चे charts phone वर पाहायचे; Approve बटण नाही, reply मध्ये ✔ / ✘ कारण / सुटलेला trade.
- Charts + manifest फक्त private trade-data: `review/<kind>/<run_id>/manifest.json` ({run_id, title, items[n, date, item, reading, files]}).
  K-10 run1 (10 दिवस: 1H + 15M, signal दिवसांचा trade chart) तिथे push केला.
- `backtest_review/telegram.py` + `scripts/send_review_to_telegram.py`: trade-data pull ⇒ manifest ⇒ प्रत्येक item एक media group, caption
  "🔎 K-10 दिवस n/N · तारीख" + एका ओळीत वाचन. Sent log (VPS local `data/review_tg_sent.json`) ⇒ duplicate नाही; संदेशांमध्ये 3 s विराम;
  Telegram ने नाकारलं ⇒ लहान (JPEG 60%) करून एकदा. Token / chat id नाहीत ⇒ स्पष्ट error (token कधीच print नाही).
- Replies: सध्याचा listener (`vision/telegram_bot`, getUpdates) — sent log मधल्या संदेशाला approver चा reply ⇒ `parse_reply` (✔ OK / ✘ WRONG /
  ? UNCLEAR / "सुटलेला trade HH:MM bear|bull" ⇒ missed; वेळ / बाजू अस्पष्ट ⇒ ❓, नोंद नाही) ⇒ `backtest_review` (item_id = manifest item:
  K-10 ⇒ "k10/run1|day:…", backtest review ⇒ "day:…" / "trade:…" page शी जुळणारे; settings_hash = run) ⇒ "नोंद ✓". इतरांचे replies दुर्लक्षित.
- Telegram चुका: 429 ⇒ retry_after थांबून तेच; 400 / 413 ⇒ लहान करून एकदा; network ⇒ पुन्हा नाही (duplicate album टाळा). Sent log खराब ⇒
  sender थांबतो; ProcessLock ⇒ एका वेळी एक sender. Independent review: 9 findings (ids, 429, files 1–10, parser edge cases, sent log,
  caption UTF-16, README restart wording, stderr redaction) — सगळे दुरुस्त + tests; manifest writer K-10 runner मध्ये Simple Core PR सोबत. Listener restart ⇒ फक्त उघडे vision PENDING_HUMAN रद्द (आधीसारखं); PAPER exits ला हात नाही.
- याच PR मध्ये Backtest Review page + Golden Gallery साधनं (आधीचा local commit).

## 2026-10-08 · Simple Core + execution settings; KB दुरुस्त्या (context म्हणून)
**का (Abhi):** "आपण analysis paralysis मध्ये अडकलो आहोत." Engine चं काम फक्त (1) entry चा area शोधणं, (2) confirmation (commitment
candle) झाल्यावर ENTRY SIGNAL. SL / target / R:R / instrument / strike / lots / expiry = dashboard settings, engine मध्ये काहीही hardcoded
नाही. Story P1–P5 module **नाही** (बनवलेला काढला). बाकी analysis (gap, Elliott, volume, divergence, patterns, VIX, 23 बाबी, गुण) =
context / shadow.
**Simple Core (`simple_core/`):**
- `engine.detect`: trend (market_state; HTF range ⇒ impulse बाजू; F4 विरोध / testing ⇒ signal नाही) · area = trade बाजूचे zones
  (`chart_reader.zones`; ≤ 0.5 MR अंतरातले एकत्र, उदा. trendline + swing high) · pause = commitment आधी area ला लागलेले indecision bars
  (body ≤ 50% / range ≤ 1 MR / दोन्ही wicks), किमान 1 · commitment = एकटा bar (टोक area ला) किंवा शेवटचा pause bar (touch) + हा bar:
  range 1.2–2.5 MR, body ≥ 50%, close टोकाजवळ · area पलीकडे सलग 2 closes ⇒ acceptance ⇒ रद्द · `Tracker`: त्याच area (पट्टा overlap) वर
  एकच signal (`DUP_SETUP`) · opening window नाही. Signal = {side, trigger_time, trigger_price, area, pause_bars, pause_from, commitment,
  ref_levels {structural_invalidation, commitment_extreme, next_opposite_area, impulse_end}, context_story}. `signal_at` = real data
  wrapper (trendline memory सह). वेळ ~1 s / bar.
- `execution.plan / simulate`: sl_mode, target_mode, rr_filter (+ min_rr), instrument, strike_mode / value, width, lots, expiry_rule —
  निवडलेलं नसेल ⇒ trade नाही ("SL mode निवडलेला नाही" …); settings hash प्रत्येक plan मध्ये. `settings.py`: profiles store
  (`data/simple_core_exec.json`, default नाही). Dashboard: Backtest Review पान ⇒ "⚙ Simple Core execution settings" tab.
- Tests (`tests/test_simple_core.py`): (a)–(g) + settings नसल्यावर trade नाही + DUP_SETUP + store; engine.py मध्ये SL / target /
  instrument शब्द नाहीत (grep test).
**KB दुरुस्त्या (आधीचं काम, फेकलेलं नाही):** `zones.py` (core वापरतो), `setups.SetupTracker` / `LineMemory` (trendline स्थिर ओळख: बदल
फक्त real break — आता `elliott/breaks.first_real_break`, detrend — किंवा ≥ +2 touches आणि ताजा touch; कारण log), `gap.py`
(`GAP_NO_PULLBACK`, setups A/B/C, गोष्ट, G7 scorecard), sweep व्याख्या (gap open = sweep नाही), candle series / zone story,
23 बाबींचा checklist, दोन SL व्याख्या — हे सगळं जड chart_reader (shadow) मध्ये context म्हणून; F4 gate (shadow मध्ये `SIDE_UNCLEAR`).
**7 Oct golden (Simple Core, tuning नाही):** 09:30 signal नाही (area वर नाही) · 11:00–12:00 seller area (trendline 28 Sep + swing high,
22,682–22,740) वर pause · **12:15 ENTRY SIGNAL** (bear, 22,648.9) · 12:45 `DUP_SETUP`. 09:30 आणि 12:15 ला तीच trendline (28 Sep 22,855 /
30 Sep 22,809 / 6 Oct 22,732).
**K-10:** `research/k10_days.py` (seed 20261008; IS 5 + Jul–Oct 2026 5; gap-up / gap-down / trend ×2 / range) — प्रत्येक दिवस 15M (trend,
areas, pause फिकट, commitment ठळक, 🚩, ref_levels, shadow ओळ) + 1H; `--exec-profile` ⇒ plan + simulate. **थांबा-बिंदू K-10.**
नंतर: OE / PCS live trend market_state वर.

## 2026-10-08 (रात्र) · Simple Core v2: G1 / G8 / G9 wave context, K-10 निर्णय A–D, commitment ≥ pause, POSSIBLE_REVERSAL, Gallery G7–G9
**KB:** नवीन आवृत्ती (भाग H G1–G9; motive wave reference levels फक्त माहिती).
**Motive wave (`simple_core/waves.py`):** trade-degree swings (market_state, 15M ATR × 3) + चालू pullback ⇒ origin / W1 / W2 / wave 3 टोक.
चालू pullback = wave 2 ⇒ G1; wave 3 मधला उथळ (≤ 38.2% + 5%) जलद (≤ 6 bars) ⇒ G8; wave 3 ≥ wave 1 आणि W1 overlap नाही ⇒ G9; W1 भागात
(R3) / wave 5 नंतर / origin खाली ⇒ count gray. Simple Core चे 4 टप्पे तसेच — wave फक्त setup label आणि ref_levels: wave3_projection
(W2 end + 1.618 × wave 1; 1.0 / 2.618 पर्याय), wave5_projection (W4 end + 1.0 × wave 1; पर्याय + 0.618 × (W1 start → W3 end)),
wave1_origin, wave1_extreme, subwave_origin. Gray / लागू नाही ⇒ None + `ref_notes` कारण. Wave 3 ने पार केलेलं W1 टोक ⇒ flip area.
**Execution:** target_mode wave3_projection / wave5_projection; sl_mode wave1_origin / subwave_origin / wave1_extreme; G9 ⇒ `g9_tier`
(C ⇒ `g9_lots`, skip ⇒ trade नाही) — निवडलेलं नसेल ⇒ trade नाही. Default कुठेच नाही. `plan(spot_only=True)` (K-10 / review अहवाल).
**K-10 निर्णय (Abhi):**
- A1 testing मध्ये जुन्या trend टोकापलीकडे close ⇒ BREAK_FAILED, trend लगेच परत (protected = break नंतरचं टोक) — 15 Nov 2021.
- A2 testing ⇒ फक्त (a) तुटलेल्या protected / flip PDL-PDH चा retest break दिशेने (G4) किंवा (b) range edges; बाकी TESTING_ONLY_FLIP_OR_EDGE.
- B1 touch 0.3 MR तसाच; pause + commitment मालिकेतला कोणताही candle area ला लागला तरी valid (28 Sep). Flip zone: pause / acceptance
  role_since (break bar) नंतरचेच.
- B2 time acceptance: level पलीकडे सलग 3 closes (buffer आत) ⇒ खरा break / BROKEN — `elliott/breaks.time_accepted`, Elliott settings
  `break_accept_closes` 3 आणि levels_v2 `accept_closes` 3 — एकच व्याख्या (16 Feb 2018 PDL).
- C K-10 runner: `--exec-json` / `--exec-profile` ⇒ प्रत्येक signal वर spot plan + simulate; एका ओळीत वाचन; review manifest (Telegram).
- D 15M chart window कमाल 7 sessions (`backtest_review/charts.CHART`), मोठा context 1H वर.
**Evening plan §8.1 पूर्वतयारी:** commitment range ≥ `commitment_vs_pause` (1.5, dashboard) × pause सरासरी; K-10 runner `--engine-alt`
⇒ 1.3 / 1.5 / 2.0 signals शेजारी (निर्णय Abhi चा).
**POSSIBLE_REVERSAL v2 (Abhi, K-10 खऱ्या data नंतर):** counter-move impulse च्या ≥ 38.2% **आणि** impulsive — 5 निकषांपैकी ≥ 3
(5 legs / कमी overlap; displacement; गती impulse पेक्षा जास्त; impulse ची सुरुवात close ने तुटली; वाटेत उथळ pauses). दोन legs: पूर्ण
counter-move आणि ताजा leg (impulse दिशेच्या शेवटच्या swing पासून). शेवट फक्त रचनेने: (a) सुरुवात close ने पुन्हा; (b) शेवटचा आतला swing
impulsive leg ने तुटला ⇒ जुना trend; (c) नव्या दिशेत HL / LH confirm ⇒ new_trend. 61.8% नियम नाही (wave (2)). HTF protected तोडणारी
counter-move ⇒ market_state trend / testing (इथे नाही). Flag असताना जुन्या दिशेने signal नाही, नव्या दिशेने (wave (2) end) चालतो.
**G8 flag channel (`simple_core/flags.py`):** area = flag channel (समांतर रेषा, प्रत्येक बाजूस ≥ 2 touches), impulse नंतर उथळ (≤ 50%),
overlapping (≥ 0.6), slope trend विरुद्ध / सपाट; commitment flag रेषेबाहेर close ⇒ setup G8. Breakout bar नेच नवं टोक केलं तरी flag
आधीच्या टोकावरून. Futures volume (कमी) अजून engine मध्ये नाही.
**खऱ्या data वर (regression, tuning नाही):** 7 Oct 12:15 bear कायम · 28 Sep 14:15 G8 bear 22,794 · 26 Aug 10:00 bear (flip, G4) ·
16 Feb 2018: 09:30 नाही (counter-move 144% + HL ⇒ new_trend), 13:30 G8 flag breakout bear · 11 Aug: flag (3/5) पण (b) ने रद्द; ताजा leg
1/5 ⇒ Abhi ला degree विचारला. `research/reversal_check.py`: IS मधून 5 reversal + 5 continuation (hindsight फक्त निवडीसाठी) + charts.
**Independent review (12 findings) — दुरुस्त + tests:** (1) सगळे pause bars असलेला flag "late zone" ने गळत होता ⇒ flag zone जन्म = impulse
टोक; (2) B2 zones path (`chart_reader/zones` ⇒ lifecycle) मध्ये accept_closes नव्हतं ⇒ जोडलं, engine area acceptance आणि BROKEN ⇒ DEAD
सुद्धा `time_accepted`; (3) K-10 spot_only G9 वर g9_lots KeyError; (4) ताज्या counter leg चा swing प्रकार उलटा ⇒ दुरुस्त, आणि ताजा leg फक्त
पूर्ण counter-move रद्द झाल्यावर (ABC चा C leg ≠ reversal); (5) G8 label असताना wave G9 ⇒ g9_tier gate; (6) protected exclusion wick ऐवजी
close; (7) दोन vacuous tests खरे केले; (8) K-10 वाचन SL / target None; (9) PROT-BRK zone role_since; (10) "उथळ pauses" pause नसेल तर
खरा नाही, (b) displacement दिशेसह, "कमी overlap" = F3 व्याख्या (ER किंवा K10.1); (11) rr_filter "false" string, अज्ञात sl / target mode,
--engine-alt keys तपासणी. Golden: 7 Oct 12:15 bear आणि 28 Sep 14:15 G8 bear (नवीन case) पास.
**Golden Gallery:** G7 (exhaustion gap reversal, सैल), G8 / G9 (waves.py) detectors; manifest ⇒ Telegram; corrected_setup G1–G9.

---
## थर v2.2 "method-first" — पायरी A + B (decision3)
**Spec:** `docs/prompts_v2/08_थर_v22_METHOD_FIRST.md` (Abhi, §0–§7; §5–§7 जोड research / पुराव्याचं वजन / liquidity नंतर).
**A:** नवा package `decision3/` (जुना `decision2` तसाच — shadow तुलना, setting `engine_version` v21 / v22). Register: प्रत्येक आकडा
"Abhi नियम / व्याख्या / अंदाज / setting" वर्गासह (`decision3/settings.py`).
**B — ① Daily Dow (`decision3/daily.py`):** Daily swings pivot (N = 2, default) किंवा DC (k_D × σ_D); confirm-क्रमाने आलटून पालटून.
UP = नवा HL + HH (break नंतरचे), DOWN आरसा; protected = तो HL / LH; trend फक्त protected च्या Daily **close** ने संपतो (wick नाही) ⇒
pullback मध्ये trend बदलत नाही (v2.1 चं net/H regime, D3 / htf_unknown / Gray-1 नाहीत). RANGE = NEUTRAL + दोन H व दोन L σ_D-अपूर्णांकात समान.
UNKNOWN फक्त ≤ 10 Daily candles. Intraday: Daily state known_at ≤ bar_end.
**B — ② 1H levels (`decision3/levels.py`):** जन्म (a) D2 / Daily swing (wick-to-body + किमान रुंदी), (b) BOS origin base, (c) flip
(acceptance: पलीकडे सलग 3 closes), (d) equal highs / lows. Merge overlap ⇒ एक (पट्टा-इतिहास ⇒ truncation-safe). 1–2 closes पलीकडे / wick
आणि परत ⇒ sweep ★. Flip अयशस्वी (closes जुन्या बाजूला टिकले) ⇒ जुनी भूमिका. मृत्यू फक्त मूळ बाजूचा पलीकडचा D2 swing close ने तुटला (Q2).
Prune नाही; `self` नियम नाही. Active = trade-बाजूची जवळची 2.
**OPEN_QUESTIONS:** `docs/reports/v22/OPEN_QUESTIONS.md` (Q1–Q9, प्रत्येकाला default).
**C — ③④⑥⑦ + §5–§7 (`decision3/method.py`, `liquidity.py`, `engine.py`):** K (BOS impulse ⇒ उलट D1 swing / level ⇒ उघडी;
origin close ने तुटला ⇒ रद्द), ③ breakout / gap ✘, ④ power shift (a–d पैकी 2; RSI NA), ⑥ commitment (body, मागच्या extreme पलीकडे close,
reclaim चालतो, कमकुवत signal-bar ✘, वेळ-खिडकी end exclusive), ⑦ SL / target / R:R ≥ 3, §5.1 पाय-मोजणी (पहिला पाय ⇒ फक्त ★ ≥ 2 +
मजबूत signal-bar ⇒ कमाल B), §5.3 range अवस्था gate, §6 conviction (NA बेरजेत नाही), §7 liquidity pools / sweeps / traps. Charts English
(Abhi), Telegram caption `story` मराठी.
**Self-review + independent review दुरुस्त्या:** 1H पट्टा / BOS base अपूर्ण तासाचे पुढचे bars वापरत होते (lookahead) ⇒ `_h1_upto`;
retest + reclaim ला नवा BOS ⇒ K रीसेट (एक pivot = एकच BOS); §5.1 पहिल्या पायाचा नियम उलटा होता; Daily protected टाकलेल्या pivot वर
जात होता; 15:15 bar entry ला चालत होता; ③ स्पर्श फक्त entry bar (spec "लगत" ⇒ `touch_window_bars`, Q18); level score नंतरचे births पाहत
होता (फक्त माहिती); magic numbers register मध्ये; engine invariant test खरा (ABC synthetic ⇒ setup) + truncation key मध्ये K / risk /
checklist. OPEN_QUESTIONS Q10–Q19.
**⑤ trendline (`decision3/trendline.py`):** K ची आतली रेघ (I_end + confirmed D1 counter pivots, ≥ 2 स्पर्श), trend-दिशेचा close-break ⇒
पुरावा `tl_break` (grade +, gate नाही; रेघ नाही ⇒ NA). Checklist ⑤, 15M chart वर रेघ (English), caption मध्ये ओळ. Q20.
**D — Telegram trader view (`decision3/telegram_view.py`):** setups + Abhi च्या खुणांसाठी 3 charts (Daily known-at पर्यंत, 1H, 15M — English,
emoji ऐवजी "SETUP A / B" + बाण), मराठी caption 5–8 ओळी (कथा + B1 / B2), debug.json वेगळा. Manifest = backtest_review format ⇒ पाठवणं फक्त VPS
(`scripts/send_review_to_telegram.py --run review/v22/<run>`). `scripts/v22_check.py --tg-run`. Q21 (B1 / B2 व्याख्या).
**What-if (Q15 / Q16, फक्त अहवाल):** `scripts/v22_whatif.py` + `docs/reports/v22/WHATIF.md`; setting `commit_beyond` (default extreme,
spec ⑥). NIFTY: फक्त Daily DC ने E1 / E2 ① पार; सगळ्या variants मध्ये E-days ⑥ (commitment candle) वर अडतात. Defaults तसेच.
**⑥ दुरुस्ती + diag:** commitment मध्ये k = 1 core ✔ पण कमकुवत असेल तर k = 2 merged पाहत नव्हता (spec "≤ 2 merged") ⇒ दुरुस्त (diag च्या
agreement test ने पकडलं). `scripts/v22_commit_diag.py` (फक्त अहवाल): ③ ✔ bars वर ⑥ च्या प्रत्येक अटीचा निकाल, कोणती अट किती अडवते.
