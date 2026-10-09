# थर 3: Correction चे patterns आणि "momentum कमकुवत होतोय का" (v2.1, 2026-10-09)

> Master लागू. **थर 2 ला ✔ झाल्यावरच.**
>
> ## का
> Abhi: "pattern कोणता ⇒ momentum कमकुवत होतोय का." Picture-perfect नाही (wedge अपूर्ण + trendline breakout + commitment candle).
> Audit: tie अक्षरानुसार; पालक-lag "count नाही"; flat B ≤ 2A ⇒ "B"; labels bar-गणिक.
>
> **संशोधनाचे धडे (`price_action/03_correction_patterns.md`, `02_…momentum.md`, `correction_patterns_reference.md`, `elliott_wave.md`):**
> 1. **तीन शब्दसंग्रह, एक वस्तू:** Brooks H2/L2 ≈ zigzag/flat ≈ flag; three pushes/H3 ≈ diagonal/triangle ≈ wedge/pennant; trading range ≈ flat/combination ≈ rectangle.
> 2. **Bulkowski:** breakout direction सगळ्यात कमी उपयोगी; throwback ~58%; **busted breakout नंतरची चाल मोठी** ⇒ far-line reversal entry ही breakout entry पेक्षा चांगली जागा.
> 3. **खोल retrace (≥ 70%) नंतर दुसरा leg जास्त वेळा पूर्ण** ⇒ खोली एकटी grade नाही.
> 4. Sub-wave रचना नाजूक ⇒ पुरावा.
> 5. Momentum कमकुवत होण्याची लक्षणं (12) — "SOT = deceleration, not reversal" ⇒ trigger थर 7.
> 6. Brooks: trend मध्ये reversal patterns fail; wedge = three pushes (converge गरजेचं नाही); final flag ~40%; आकडे heuristic.

---

## 0. मूलतत्त्वं
1. फक्त थर 2 च्या K चा pattern; पूर्ण count नाही.
2. **`invalid` फक्त I_origin real break (थर 2 "I रद्द").** बाकी नियम = प्रकार ठरवणारे / मजबूत पुरावा (m = 0.2).
3. Pattern = पुरावा; मुख्य output = momentum + अवस्था. निर्णय थर 7.
4. Tie अक्षरानुसार / position-नुसार कधीच नाही. Alternate नेहमी.
5. थर 2 "impulse चालू" ⇒ pattern नाही; "K सुरू झाला असावा" ⇒ फक्त `forming_A`.

## 1. Input / State
थर 1 pivots; थर 2 I (आवृत्त्या), K अवस्था, legs + labels + features, flags (`cisd`, `last_leg_start_broken`), RVOL. State = साठवलेल्या प्रवाहावर शुद्ध fold.

## 2. Hypotheses
### 2.1 क्रम आणि wave
P = [I_end] + K चे D0 confirmed pivots + tentative; wave = दोन pivots मधला भाग, दिशा एकाआड एक, **सुरुवात / शेवट हीच टोकं**, sub-legs विषम. Pattern confirmed pivot वर संपू शकतो + **एकच** उलट leg (I-दिशेने, शेवटच्या wave च्या सुरुवातीपलीकडे नाही). P > 30 ⇒ त्या K साठी एकदाच D1 (`coarse`). Node budget: drop by (ओळख-गुण, template-क्रम, सुरुवातीचा pivot).
### 2.2 Templates (Elliott ↔ classical ↔ Brooks)
Zigzag (flag; H2/L2) A-B-C · Flat (rectangle/range) A-B-C (उप-प्रकार C नंतर; identity नाही) · Triangle A-E (contracting/expanding; barrier label; apex वेळ) · Wedge (संपूर्ण K; diagonal / three pushes; converge नसले तरी; अपूर्ण wedge सुद्धा) 1-5 · Double zigzag W-X-Y · Combination W-X-Y · Impulse-K 1-5 (correction नाही). Triple ⇒ "ओळखता येत नाही". अपूर्ण = कुटुंब (prefix); न आलेल्या waves तटस्थ. Brooks leg count (H1/H2/H3) नोंद.
### 2.3 आतली रचना (पुरावा)
माप 1 = D0 sub-legs; माप 2 = wave bars वर DC θ = 0.236 × |wave| (अंदाज 0.18/0.236/0.3); **चालू wave साठी θ शेवटच्या confirmed extreme वरून गोठलेला** आणि फक्त confirmed sub-pivots. वर्ग: 1 अज्ञात / 3 / 5 (impulse नियम) / diagonal (wedge नियम) / बाकी अज्ञात. एकत्र तक्ता (अज्ञात×x ⇒ x; 3×5 ⇒ "3 किंवा 5"; 3×diag ⇒ "3 किंवा diagonal"; 5×diag ⇒ "5 किंवा diagonal"); "X किंवा Y" मध्ये एक पर्याय जुळतो ⇒ m 0.85.

## 3. नियम
**नकार:** फक्त I_origin real break.
**प्रकार:** zigzag/flat: B > A-start ⇒ flat; B/A < 0.618 ⇒ zigzag; 0.618–0.90 दोन्ही (flat m कमी); **0.90–1.0 ⇒ फक्त flat**. Flat उप-प्रकार (expanded B > 1.05A आणि C > A-end; running B > A आणि C < A-end; regular). Triangle contracting / expanding / barrier. Wedge contracting (3<1, 4<2) / expanding. Double zigzag vs combination. Impulse-K (2 ≯ 1-start, 3 > 1-end, 3 सगळ्यात लहान नाही, 4 ∉ 1, 5 > 3-end).
**मजबूत पुरावा (m = 0.2; प्रत्येक एकदाच):** flat B ≤ 2A; wedge 2 ≯ 1-start, 4 ≯ 2-end; W-X-Y: X ≯ W-start, W चा C ≥ W चा A-end, ≤ 1 zigzag, triangle फक्त Y; triangle मध्ये leg रचना "5" (impulse नियम). Wedge "3 > 1-end" = guideline 0.6 जेव्हा Brooks three-push (Brooks: third push need not exceed).

## 4. गुण
- **ओळख-गुण** (पूर्ण waves; क्रम) आणि **पूर्णता-पुरावा** (शेवटचा wave; अवस्था / अहवाल) वेगळे. गुण = m चा भौमितिक सरासरी × साधेपणा (1.0/0.9/0.8). प्रत्येक पुरावा एकदाच.
- Guidelines: zigzag B/A 0.382–0.618, B वेळ ≥ A, A रचना (5/diag 1; अज्ञात 0.7; 3 ⇒ 0.2); [पूर्णता] C/A {0.618,1,1.618}±tol, C वेळ > A, C रचना, channel स्पर्श. Flat B/A 0.90–1.382 (0.618–0.90 चढता; > 2 ⇒ 0.2), A रचना 3, B वेळ ≥ A; [पूर्णता] C/A, A–B पट्टा. Triangle legs लहान, expanding 0.5, wave-2 संदर्भ 0.2 (D2 trend I-विरुद्ध + I मध्ये एकच D1 आवेग), apex 0.6 (> 85%); [पूर्णता] A–C / B–D रेघा. Wedge 1>3>5 सुसंगती, 4 ∈ 1 (EWI); [पूर्णता] 5 ने 3 गाठलं (अपूर्ण 0.6), रेघा, throw-over. Double zigzag X/W ≤ 0.618, Y≈W. Combination X/W ≥ 0.5, X वेळ. Impulse-K Tier B.
- **थर 2 स्वभाव-ओळ** (wave ची टोकं D1 leg शी जुळतात, `known_at` ≤ decision): zigzag A चं **स्वभाव-मत** आवेगी ⇒ 1 (label विरोध-2 असेल; तेच); flat A सुधारात्मक ⇒ 1; उलट 0.5; expanded-flat B: label आवेग ⇒ 0.3, आवेग(कमकुवत) ⇒ 0.6. रचना माहीत (अज्ञात नाही) ⇒ स्वभाव-ओळ नाही.
- **Volume / वेळ = पूर्णता-पुरावा / अहवाल (ओळख-गुणात नाही):** K वर RVOL slope (<0 ⇒ 1; ≥0 ⇒ 0.6; NA वगळ; desc-triangle अपवाद नोंद); K वेळ ≥ I-leg/3 आणि शेवटचा leg वेळ ≥ पहिला, उल्लंघन 0.5; K > 2× I-leg वेळ ⇒ `range_like`.

## 5. Preferred / alternate / स्थिरता
क्रम: ओळख-गुण ⇒ निश्चित template-क्रम. Identity (कुटुंब, K key, confirmed wave-टोकं; prefix; coarse मधून टिकते). Hysteresis 1.2× / तोच challenger 2 candles; invalid ⇒ लगेच. K key = I_origin + I_end आवृत्त्या; जुन्या I_end पासूनचे hypotheses (expanded flat) एकत्र क्रमवारीत. Alternate = वेगळ्या अर्थाचा.

## 6. अवस्था (पहिली जुळणारी)
`invalid` ⇒ `impulse_K` ⇒ `forming_A/B`, `in_X`, `in_triangle` ⇒ `final_leg_in_progress` (template-नुसार; `C_short_possible` जर उलट leg सुरू) ⇒ `final_leg_present` ⇒ **`complete_resuming`** (शेवटचा wave confirmed pivot वर संपला + एक उलट leg + थर 2 `cisd` **किंवा** `last_leg_start_broken`; शेवटचा wave लक्ष्यापर्यंत नसेल (अपूर्ण wedge / C_short) तरी चालतो, **`final_leg_short`** खूण + पूर्णता 0.6). Resuming नंतर भाव शेवटच्या wave च्या टोकापलीकडे ⇒ परत `final_leg_in_progress` (resuming failed).
- **Position (नोंद + थर 7 gate):** D1 चा K हा D2 च्या preferred मधली जागा ⇒ `position_ban` जेव्हा: D1 K = D2 pattern चा **A चा शेवट** (A-end ⇒ पुढे B/C बाकी), **B च्या आत**, **X च्या आत**, किंवा **triangle च्या आत (B–D)** (नकाशा / Abhi चे मंजूर नियम; KB A3).
- `final_flag_risk` (अंदाज: K slope < 0.02 σ/bar; I मध्ये ≥ 3 pushes किंवा SOT_trend; measured-move target = I-leg size K-end पासून ±1 σ जवळ; channel magnet NA, v2.2). `partial_rise` (rectangle/flat: swing ≥ 70% पण < 100% range ⇒ उलट कडेचा break 75–79%).
- Output JSON मध्ये: labels + pivots, रेघांची टोकं, C = A projected किंमत (B-end पासून), अवस्था, गुण, momentum.

## 7. Momentum कमकुवत होतोय का (मुख्य output; प्रत्येक बंद candle)
Pushes = preferred hypothesis चे counter-दिशेचे waves (fallback: K चे D0 pivots जेव्हा "ओळखता येत नाही"). **✓ = सगळ्या उप-अटी खऱ्या; ✗ = कोणतीही खोटी; NA = कोणताही input NA.** Units slot-normalised (rng_ratio).
| # | लक्षण | उप-अटी | NA कधी |
|---|---|---|---|
| 1 | SOT | 3 pushes चे gains घटत, gain₃ ≤ 0.5 gain₁ | < 3 pushes |
| 2 | Three-push geometry + convergence | s1 ≥ s2 ≥ s3; push-3 body% < push-1; टोकावर wick_opp ≥ 0.5; K च्या रेघा converge (थर 3 रेघा) | < 3 pushes |
| 3 | Counter candles लहान | शेवटच्या 3 counter candles चा median rng_ratio < 0.7 × K च्या पहिल्या 3 चा; K median rng_ratio < I-leg median | K < 6 candles |
| 4 | Closes टोकापासून दूर + शेवटचा push स्वभाव | शेवटच्या 3 चा avg CLV_counter ≤ 0.5; शेवटच्या 5 मध्ये trend_candle(counter)% ≤ 0.4; शेवटच्या push चं C×V मत सुधारात्मक / तटस्थ | push C = NA |
| 5 | Counter displacement नाही | शेवटच्या 5 candles मध्ये n_disp(counter) = 0; counter FVG नसेल किंवा भरला (नसेल ⇒ खरं) | — |
| 6 | संथ | speed(K) ≤ 0.6 speed(I-leg); bars(K) ≥ 0.8 bars(I-leg) | — |
| 7 | नाममात्र नवं टोक | शेवटचा push नवं extreme < 0.5 σ ने **किंवा नवं extreme नाहीच**, आणि candle उलट अर्ध्यात बंद | < 2 pushes |
| 8 | Volume fading | 3 pushes: RVOL₃ < RVOL₂ < RVOL₁ (2 pushes: RVOL₂ < RVOL₁); `pullback_quiet` | vol_unreliable |
| 9 | Absorption | effort_result(K) ≥ 1.5 × I-leg (अंदाज) आणि K टोक थर 4 **zone** मध्ये (फक्त zone; रेघ नाही) | थर 4 आधी NA |
| 10 | खोली / origin | retrace (मुख्य) 0.33–1.00; `I_strict_HL` अखंड (CHoCH strict नाही) | — |
| 11 | 3 legs, impulsive 5 नव्हे | counter रचना impulsive "5" नाही (impulse-K preferred नाही; sub-structure "5" impulse नियम पास नाही). **Wedge / triangle / diagonal (3-3-3-3-3) = 5 legs तरी ✓** | — |
| 12 | CISD | थर 2 `cisd` ✓ (सुरू झालं) | — |
**निकाल:** non-NA ≥ 6 हवेत (नाहीतर "अस्पष्ट (early)"; < 2 pushes ⇒ early); ratio = ✓ / non-NA; ≥ 0.65 ⇒ **कमकुवत होतोय**; ≤ 0.35 ⇒ **नाही**; मध्ये **अस्पष्ट** (अंदाज 0.6/0.65/0.7, 0.3/0.35/0.4). **Danger (⇒ नाही):** K leg label आवेग + `pullback_heavy`; CHoCH strict + choch_disp; impulsive 5-leg counter; `climax` I टोकावर आणि K चा पहिलाच leg; impulse-K preferred. **Retrace ≥ 0.80 (Master register) = फक्त नोंद** (sweep-flavour; danger नाही). Verdict hysteresis = preferred सारखंच (2 candles). थर 4 नंतर item 9 भरून **तेच function** पुन्हा ⇒ एकच verdict.

## 8. अंदाज register
m floor 0.2; साधेपणा 1/0.9/0.8; hysteresis 1.2×/2; माप-2 r 0.236; coarse 30; 12-लक्षणांचे आकडे (0.5, 0.7, 0.5/0.4, 0.6/0.8, 0.5 σ, 1.5×, 0.33–1.00); निकाल 0.65/0.35, min 6; final_flag slope 0.02; partial 70% — प्रत्येकी 3 पर्याय, वर्ग research / अंदाज.

## 9. Charts / Telegram
15M: labels (preferred ठळक / alternate फिके), आतले 1-5, pattern रेघा, D0 ठिपके, final_flag / partial / position_ban खुणा, **box: momentum निकाल + 12 ✓✗NA ओळ + अवस्था + गुण.** 1H D2. महत्त्वाचे क्षण: final_leg_present, complete_resuming, preferred बदल, momentum ⇒ कमकुवत. Telegram "🧭 PATTERN CHECK" (pattern · अवस्था · momentum · कारण).

## 10. मोजमाप (वर्णन)
Patterns / अवस्था; ओळखता येत नाही %; preferred बदल; momentum verdict वाटप + flip count; 12 लक्षणांची ✓/NA frequency; danger; sensitivity.

## 11. Tests
Templates (ओळख; प्रकार ⇒ दुसरा; मजबूत ⇒ 0.2 valid; invalid फक्त real break); wave नियम; coarse drop rule; K-state inputs (impulse चालू ⇒ नाही; सुरू झाला असावा ⇒ forming_A); flat उप-प्रकार ≠ preferred बदल; 0.90–1.0 flat; triangle apex / wave-2; wedge अपूर्ण valid; three-push 3≯1 ⇒ 0.6; W-X-Y; impulse-K; रचना तक्ता + 0.85 + चालू wave θ गोठलेला + "फक्त 3 D0 sub-legs ⇒ माप 2 diagonal" + "विरोधात तरी valid"; गुण (geo mean, पूर्णता वेगळी, एक पुरावा एकदा; volume / वेळ ओळख-गुणात नाहीत); स्वभाव-ओळ `known_at`; क्रम नावं उलटी; hysteresis; identity; expanded-flat कुटुंब; अवस्था सगळ्या incl. complete_resuming with cisd / last_leg_short / resuming failed; position_ban; final_flag; partial_rise; JSON मध्ये C=A आणि रेघा; **momentum: प्रत्येक लक्षण ✓/✗/NA, wedge preferred ⇒ 11 ✓, ratio / min non-NA / early, danger, retrace 0.85 ⇒ danger नाही, hysteresis, re-emit same function**; prototype-सदृश synthetic (दोन्ही वाचनं दिसतात); "निर्णय नाही"; D2; truncation; replay; shadow; caption; तारीख.

## 12. क्रम
`elliott/` किंमत-नियम import (तुलना-test) ⇒ `patterns2/` ⇒ suite ⇒ review ⇒ run ⇒ push ⇒ PDF ⇒ Telegram ⇒ Abhi ✔ ⇒ थर 4.
