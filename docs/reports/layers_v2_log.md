# थर v2 (price-action पाया): कामाची नोंद आणि Abhi साठी प्रश्न

> हा log प्रत्येक थरासोबत अद्ययावत होतो. MASTER (`docs/prompts_v2/00_MASTER`) चे कायम नियम लागू:
> - backtest / IS / VAL नाही; PAPER फक्त; LIVE ला हात नाही; order नाही;
> - नव्या code मध्ये तारीख नाही; holdout कुठेच नाही;
> - Telegram पाठवणं, VPS बदल आणि merge फक्त Abhi च्या मंजुरीने.
>
> **महत्त्वाचं:** MASTER नुसार आधीच्या थराला Abhi चा ✔ मिळाल्याशिवाय पुढचा थर नाही. तुम्ही सांगितलं "सगळं काम पूर्ण करा, उद्या उत्तरं
> देतो" म्हणून थर 2–7 चं code + tests + स्वतंत्र review + suite केलं आहे. **Telegram ला काहीही पाठवलं नाही.** तुमचा ✔ / ✘ आल्यावर
> क्रमाने (थर 1 ⇒ 2 ⇒ …) charts पाठवायचे आणि दुरुस्त्या करायच्या.

## स्थिती (थोडक्यात)
| थर | module | स्थिती | Abhi ✔ |
|---|---|---|---|
| 1 v2.1 | `swings2/` | commit `6529f1f`; SWING CHECK v2 run1 trade-data मध्ये (50 albums; VPS block दिला होता) | बाकी |
| 2 v2.1 | `legs2/` (features, measure2, ik2) | code + 27 tests | बाकी |
| 3 v2.1 | `patterns2/` (rules2, enum2, score2, fold2, momentum) | code + 21 tests | बाकी |
| 4 | `zones2/` | code + 14 tests | बाकी |
| 5 | `trendlines2/` | code + 11 tests | बाकी |
| 6 | `rsi2/` | code + 10 tests | बाकी |
| 7 | `decision2/` + `vision2/` | code + 19 tests; vision = फक्त veto नियम (API call नाही) | बाकी |

**वेग:** खऱ्या data वर (जुलै–ऑक्टोबर, 1727 bars) सगळे 7 थर ~15 सेकंदात चालतात.

---

## थर 1 v2.1 (`swings2/`)
**काय केलं**
- D0 = DC (same-bar ⇒ 1m किंवा सावध नियम). D(n+1): extreme फक्त confirmed D(n) pivots, θ-crossing raw bars वर.
  `known_at` = max(crossing close, D(n) known_at). Nesting उल्लंघन 0.
- `1m_status` प्रवाह (`stream.json`); replay `--m1-status` ने त्यावरच.
- Market structure (D1, D2): trend, Rhea range, EQ, BOS / CHoCH / sweep, reversal 3-पायरी, always-in, failed_gap_break, "pullback सुरू".
- k: D1 = 4, D2 = 6 (तुमची निवड).

**मोजमाप (शेवटचे 22 दिवस):** pivots D0 108, D1 29, D2 13, D3 2; scaling slope −1.92; D1–D2 एकमत 36.7%; D1 RANGE 40.7%.

**प्रश्न**
1. **D1 RANGE 41% वेळ** (नियम: 8 candles, 3σ पट्टा, प्रत्येक कडेला ≥ 2 स्पर्श). पट्टा 2σ करायचा की min 10 candles?
2. SWING CHECK v2 albums (50) ✔ / ✘?
3. Weekly (D4) अजून warm-up मध्ये (data जुलैपासून). चालेल ना?

---

## थर 2 v2.1 (legs, I / K)
**काय केलं**
- थर 1 v2 च्या pivots वर legs. Candle features: CLV_d, wick_opp_d, overlap3, climax, FVG, displacement; leg features: ER (clamp, 0 ⇒ NA),
  trend%, max_run, n_FVG, n_disp, wave_vol, wave_RVOL, effort_result.
- C baseline: स्वतः वगळून, warm-up / 1–2-bar / gap_leg_theta legs वगळून; 10–39 ⇒ warmup; < 10 ⇒ NA. V: कोणत्याही leg ला < 3 reliable
  bars ⇒ तटस्थ.
- I: दिशा = पालक trend (D1 साठी D2); label आवेग **किंवा** त्या leg मध्ये BOS. पालक RANGE ⇒ `range_alt`; unknown ⇒ I नाही.
  origin वरचा high नसेल ⇒ पालक strong low + `origin_bounded`. I_end फक्त close पलीकडे सरकतो (wick ⇒ `sweep_of_I_end`).
  रद्द: I_origin real break किंवा थर 1 reversal.
- K: अवस्था, I_strict_HL, खोली मुख्य / दुय्यम, quiet / heavy, CHoCH strict, `cisd`, `last_leg_start_broken`.

**खऱ्या data वर (22 दिवस, D1):** K सुरू झाला असावा 145, K चालू 142, impulse चालू 131, I नाही 110 bars. I_end सरकला 8 वेळा, reversal ने रद्द 1.

**मी घेतलेले अर्थ (तुमचा ✔ हवा)**
- "label आवेग **किंवा** BOS": मी दिशा = पालक trend ही अट **दोन्हींना** लावली (धडा 6: I ची दिशा D2 शी सुसंगत).
- I रद्द झाल्यावर नवा I फक्त रद्द झालेल्या I_end **नंतर** संपणाऱ्या legs मधून (तोच I परत येऊ नये म्हणून).
- I_end D1 ने confirm, पण अजून एकही confirmed K leg नाही ⇒ "K सुरू झाला असावा" (prompt: "K चालू = ≥ 1 confirmed D1 leg").
- D2 चा I: पालक D3 (थर 1 मध्ये D3 structure नाही) ⇒ D3 pivots चा trend_of. D3 बहुतेक warm-up ⇒ unknown ⇒ D2 ला I नाही.
- `cisd`: K मधल्या शेवटच्या counter-close run च्या पहिल्या candle चा open; नंतर I-दिशेची candle त्यापलीकडे close.
- `last_leg_start_broken`: K चा शेवटचा counter D0 leg ज्या pivot पासून सुरू झाला, त्यापलीकडे close.

**प्रश्न**
4. D2 RANGE झाला तरी I sticky ("trend" mode) राहतो; फक्त real break / reversal ने रद्द होतो. त्यामुळे थर 7 चा range mode (I range_alt
   हवा) लागू होत नाही — 7 Oct 12:00 ला हेच झालं. D2 RANGE झाल्यावर I ला `range_alt` मध्ये बदलायचं का?
5. D2 चा I फक्त D3 trend वर. D3 warm-up असताना D2 I नाही. चालेल की D2 स्वतःचा trend वापरायचा?

---

## थर 3 v2.1 (patterns + momentum)
**काय केलं**
- `invalid` फक्त I_origin real break; बाकी नियम = प्रकार ठरवणारे (zigzag B/A < 0.90; flat ≥ 0.618; 0.90–1.0 फक्त flat) किंवा मजबूत
  पुरावा m 0.2 (flat B > 2A; wedge 2 पलीकडे 1-start, 4 पलीकडे 2-end; W-X-Y: X पलीकडे W-start, W चा C, A-end पर्यंत नाही).
- Wedge = संपूर्ण K (ending). "3 > 1-end" नसेल ⇒ 0.6 (three push). अपूर्ण wedge valid (`final_leg_short`).
- Triangle apex > 85% ⇒ 0.6. Volume / वेळ फक्त पूर्णता-पुरावा. K > 2 × I-leg ⇒ `range_like`.
- complete_resuming = शेवटचा wave confirmed + एक उलट leg + `cisd` **किंवा** `last_leg_start_broken`. Resuming failed नोंद.
- position_ban (D2 preferred: A बनतोय / B / X / triangle), final_flag_risk, partial_rise, C = A, pattern रेघा JSON मध्ये.
- **Momentum 12 लक्षणं** ✓ / ✗ / NA; निकाल ≥ 0.65 कमकुवत होतोय, ≤ 0.35 नाही; non-NA < 6 ⇒ early; danger ⇒ नाही; hysteresis 2 candles.

**खऱ्या data वर:** momentum verdict असलेले bars: अस्पष्ट 79, नाही 56, कमकुवत होतोय 7.

**मी घेतलेले अर्थ**
- Pushes चे "gains" = push ची लांबी (start → end).
- Item 4 चा "push C×V": push = एक D0 leg असेल तेव्हाच मोजता येतो; नाहीतर NA.
- position_ban: D2 ची अवस्था forming_A / forming_B / in_X / in_triangle असताना.
- final_flag_risk: "measured-move ±1σ जवळ" याचा अर्थ स्पष्ट नव्हता ⇒ measured-move target फक्त नोंदवला, अट म्हणून नाही.

**प्रश्न**
6. Momentum मध्ये "कमकुवत होतोय" फार कमी (22 दिवसांत 7 bars). Items 1, 2 (≥ 3 pushes) आणि 8 (volume) बहुतेक NA. Thresholds तसेच ठेवायचे?
7. final_flag_risk ची measured-move अट नक्की काय?

---

## थर 4 (zones)
**काय केलं**
- D1+ pivot zones (पट्टा 0.2–1 σ), k (PDH / PDL / PDC, PWH / PWL), flags c / d / e.
- Single-linkage merge (0.5 σ), > 1.5 σ ⇒ सगळ्यात मोठ्या अंतरावर तोड. Id = सगळ्यात जुना pivot.
- अवस्था: भेट (जन्माची चाल नाही), reaction, touch_score, zone_sweep / deep_sweep, reclaim, accept, spring test, pending ⇒ real break ⇒
  flip ⇒ मेला, breaker.
- गुण (NA normalise) ⇒ ★; trade बाजू; "K area मध्ये"; confluence; I-profile; momentum item 9 भरून **एकच** verdict.

**खऱ्या data वर (lookahead दुरुस्तीनंतर):** K area: हो (sweep) 92, हो 53, हो (pending) 8, नाही 203 bars.

**प्रश्न**
8. d flag (range कड) साठी zone पट्टा range कडेच्या 0.25 σ आत असावा असं मी ठरवलं (prompt मध्ये आकडा नाही). चालेल?
9. Profile futures volume वर; आपल्याकडे futures data फक्त काही दिवसांचा (6750 5M rows). जास्त data कुठून?

---

## थर 5 (trendlines)
**काय केलं**
- Origin = D2 reversal चं H (downtrend) / L (uptrend). Structural top फक्त close ने (wick ⇒ नाही). Primary (Sperandeo), latest (DeMark),
  fan. वैधता: close 0.3 σ, slope 0.5 σ/bar, spacing 6, सपाट 0.02.
- Touch भेटीनुसार (wick ± 0.2 σ; held = θ_D0 दूर). Break = detrended frame वर `breaks.first_real_break`; pending; flip; मेली; DeMark Q1–Q3.
- Trade-योग्य वर्ग (5 अटी), K आधार / टोक रेघा, आधार-break घटना (एकदाच), K sloping area, ∩ zone.

**खऱ्या data वर:** trade-योग्य 6 bar-रेघा (flip झालेल्या उलट रेघांसह). बाकी: तुटलेली 1171, लागू नाही 346, तीव्र 65.

**7 Oct 12:00 (तुमचा trade):**
- Chart वर "latest" रेघ 30 Sep 11:45 च्या high (~22800) पासून 6 Oct च्या high (~22730) पर्यंत आहे. तिला 3 touches आहेत, ती सपाट आहे,
  आणि 12:15 ला भाव तिला स्पर्श करतो (~22715). ही तुमची रेघ असावी.
- पण 6 Oct चं टोक अजून ओलांडलेलं नाही. आणि त्यानंतर आधीच्या D1 low खाली close झालेला नाही. म्हणून ते **provisional टोक** आहे,
  structural top नाही.
- Prompt §2.2 / §2.7 नुसार provisional टोकावरची रेघ trade-योग्य नसते. ते टोक K चंच high आहे, म्हणून हा नियम "स्वतःला पुरावा" टाळतो.
  म्हणून code ने ही रेघ "लागू नाही" ठरवली.
- Primary रेघ (origin वरून) तिथे 23046 आहे: भावापासून दूर, अवस्था "pending".

**मी घेतलेले अर्थ**
- Reversal शिवाय सुरू झालेला trend (data सुरुवात) ⇒ origin = segment मधलं सगळ्यात टोकाचं pivot (`origin_fallback`).
- 1H दृश्य: D3 structure नाही ⇒ origin D2 reversal वरूनच, tops D2.

**प्रश्न**
10. 7 Oct ची तुमची रेघ 30 Sep high → 6 Oct high हीच होती का?
    - असेल तर: provisional / K-टोकावरच्या रेघेला trade-योग्य होऊ द्यायचं का?
    - (उदा. 3 held touches असतील तर, किंवा K चं टोक झाल्यानंतर θ_D0 दूर गेल्यावर.)
11. "तीव्र" (रेघ trend slope पेक्षा तीव्र) बरेचदा येतं. ही अट ठेवायची?

---

## थर 6 (RSI divergence)
**काय केलं**
- RSI = `chart_reader.evidence.rsi` (Wilder 14; import, बदल नाही), segment-निहाय. 1H RSI फक्त बंद candles वर.
- D0 pivots वर लागोपाठच्या same-type जोड्या; degree tag; gap मर्यादा; Δp ≥ 0.25 σ, Δrsi ≥ 3; line_clear, price_clear.
- on_K (I_origin / I_strict_HL → K चा शेवटचा low), regular_in_K, at_impulse_end, cascade; Cardwell rsi_range; shift; rsi_disagree; labels.

**खऱ्या data वर:** divergences 6 (regular_bull 4, hidden_bull 1, regular_bear 1). Labels: continuation trap 120, K संपतोय 18,
K thinning 4, trend मजबूत 2 bars.

**मी घेतलेले अर्थ**
- line_clear मध्ये L1 / L2 शेजारचे 2 bars वगळले (`line_skip`). नाहीतर pivot च्या आधीची candle नेहमी रेघ ओलांडते आणि एकही divergence
  उरत नाही.
- on_K ला line_clear / price_clear लावले नाहीत (फक्त नोंद).

**प्रश्न**
12. `line_skip = 2` चालेल?

---

## थर 7 (decision + vision)
**काय केलं**
- Regime (1H, σ_1H, बंद 20 candles): trend_up / trend_down / range / barbwire / transition / drift.
- Gates G-A … G-I (wait vs no_trade prompt प्रमाणे).
- Commitment candle G1–G8 (merged ≤ 3, 09:30 नंतर), tier 1.
- Flavours: rejection / engulf / sweep-reclaim / throw-over / trendline-break. Retrace ≥ 0.80 ⇒ फक्त sweep-reclaim / throw-over.
- Risk: invalidation_mode auto / candle / structural; target I_end; R:R ≥ 3.
- Grade (वजनं register), size_weight (floor 0.5).
- `hard_exits` वेगळं शुद्ध फंक्शन (कोणत्याही gate / vision / approval / budget शिवाय).
- Vision: फक्त veto नियम — gate items ✘ ⇒ no_trade; ✔ कधीच promote नाही; evidence ✘ ⇒ grade −0.5; किंमती काढल्या.
  **API call नाही.**

**खऱ्या data वर (22 दिवस, review दुरुस्त्यांनंतर):** setup 0. Regime: drift 268, trend_down 188, range 60, transition 12.
थांबण्याची कारणं: drift 220, area नाही 141, range mode (I range_alt नाही) 60, I नाही 52, momentum 43, transition 12.

**दुरुस्ती (मी केलेली):** transition regime कधीच संपत नव्हता. आता संपतो जेव्हा failed breakout (close परत आत) होतो, किंवा held pullback
आणि > 5 1H bars पूर्ण होतात.

**मी घेतलेले अर्थ**
- G4 "wick_opp_d ≥ 0.5 (pin)": pin = trade-दिशेच्या **उलट** बाजूची लांब wick (buy ⇒ खालची wick).
- VIX / event calendar / macro row / gray दिशा अजून data म्हणून नाहीत ⇒ "VIX data नाही" नोंद, gate पास. Expiry फक्त futures
  contract-expiry वरून (monthly).
- vision_fail_action default = code चा निर्णय तसाच (`keep_code`).

**प्रश्न**
13. 22 दिवसांत एकही setup नाही. तुमच्या 7 Oct च्या trade ला थर 7 "थांबा (range mode: I range_alt नाही)" म्हणतो. प्रश्न 4 चं उत्तर इथे
    निर्णायक आहे.
14. VIX, event calendar, macro row यांचा data source (आणि `known_at`) कोणता वापरायचा?
15. Vision: कोणतं model आणि `run_vision_budget` किती? (महिना $5 मर्यादा लक्षात ठेवून.)
16. Gray-1 साठी review loop मधली "Abhi दिशा" row अजून नाही. Default `block` तसाच ठेवायचा?

---

## स्वतंत्र review (थर 2–7) — काय दुरुस्त केलं, काय बाकी
**दुरुस्त केलं:**
- **Zones lookahead (गंभीर):** "K area मध्ये" शेवटच्या data चं zone state वाचत होतं (pending / sweep / spring). आता प्रत्येक candle ची गोठलेली प्रत वापरतो.
- **Transition regime:** 1H आणि 15M एकक मिसळले होते. "> 5 1H bars" अट आता बरोबर लागते.
- **Must-hold:** trade-दिशा पाहिली जात होती, D2 trend नाही. आता D2 UP ⇒ strong low (long साठीच); उलट असेल तर लागू नाही.
- **Hard exits** आता फक्त दोन: trade च्या I चा I_origin real break, आणि D2 must-hold real break.
- **Expiry:** भविष्यातल्या data दिवसांऐवजी trading calendar वापरतो (replay = live). आज expiry असेल ⇒ पुढचा expiry, block नाही.
- **Range mode (§3a):** range-कड zone, range-fade पुरावा, मध्य ±1 σ_1H वगळ, target = उलट कड. पट्टा नसेल ⇒ pivot पट्टा.
- **G3:** close area च्या trade-बाजूलाच हवा (आत close चालत नाही).
- **G7** (दुसरा प्रयत्न +1). **Gray-2** ला सुद्धा Abhi दिशा लागते. htf_against ⇒ G-C नाही.
- **थर 2:** पालक trend बदलल्यावर I पुन्हा शोधतो. त्यामुळे "I नाही" 110 वरून 52 bars वर आलं.
  - Snapshot मध्ये भविष्यातला break index दिसत नाही. origin break आता I_end पासून मोजतो.
  - खोली आणि वेळ आता tentative टोकावरून सुसंगत मोजतो.
- **थर 3:** momentum hysteresis नव्या I / K ला पुन्हा सुरू होते. चालू B/A ≥ 0.90 ⇒ zigzag नाही. Item 3 / 4 चे NA prompt प्रमाणे.
- **थर 5:**
  - pending आता "आत्ता पलीकडे, reclaim नाही" या अर्थाने.
  - flip झालेली उलट रेघ trade-बाजूची उमेदवार.
  - steepness आता trendline origin वरून मोजतो.
  - K-रेघेचा जन्म anchors च्या known_at वरून. origin_shifted खूण.
- **थर 6:** 1H shift मधले एकक दुरुस्त केले.
  - on_K / regular_in_K ला line / price clear लावले; regular_in_K preferred चा A-end वापरतो.
  - range-fade मध्ये divergence range-कड zone मध्ये हवी (bull ⇒ खालची कड).
  - trap ची दिशा range शी जुळायला हवी.
- सगळ्या scripts ना `--m1-status` (replay = live).

**बाकी (नोंद; तुमच्या निर्णयानंतर):**
- tier 2 commitment;
- trendline-break flavour ची "≤ 6 candles आधी area" अट;
- zone id pruning नंतर वंशानुसार टिकवणं;
- base / ob पट्टा;
- 5-session profiles;
- cascade degree-निहाय.

## पुढे (तुमच्या उत्तरांनंतर)
1. थर 1 ✔ ⇒ थर 2 चा LEG CHECK v2 run (22 दिवस) ⇒ trade-data push ⇒ VPS block (15:30 नंतर, एकच block) ⇒ तुमचा ✔.
2. मग क्रमाने थर 3 … 7 (प्रत्येक थराचं script तयार आहे: `scripts/leg_check2.py`, `pattern_check2.py`, `zone_check.py`,
   `trendline_check.py`, `rsi_check.py`, `decision_check.py`).
3. सात ✔ ⇒ migration prompt (वेगळा टप्पा).
