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

**महत्त्वाचा निष्कर्ष (तुमचा निर्णय हवा):** partial exit (काही legs भरले, काही नाकारले) झाल्यास trade OPEN राहतो.
पुढच्या monitor cycle ला **सर्व** legs चा close order पुन्हा जातो ⇒ आधीच बंद झालेल्या leg वर उलटी नवी position उघडू शकते.
हे जुनं वर्तन आहे. ते बदलणं म्हणजे LIVE exit logic बदल ⇒ केलं नाही; आता इशाऱ्यात हा धोका स्पष्ट लिहिला जातो.
प्रस्ताव: partial exit नंतर फक्त न भरलेले legs पुन्हा पाठवणे (भरलेल्या legs ची नोंद DB मध्ये). Default-off setting सह, PAPER/fake-broker tests सह.
