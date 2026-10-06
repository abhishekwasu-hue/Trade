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
