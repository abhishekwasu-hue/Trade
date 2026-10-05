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

**Tests:** 2413 → 2441 (legs 18, level_strength 10). Full suite हिरवा.

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
