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
