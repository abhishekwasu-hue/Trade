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
| 2 v2.1 | `legs2/` (features, measure2, ik2) | code + 30 tests (उत्तरं 4, 5 लागू) | बाकी |
| 3 v2.1 | `patterns2/` (rules2, enum2, score2, fold2, momentum) | code + 23 tests (उत्तरं 6, 7) | बाकी |
| 4 | `zones2/` | code + 17 tests (उत्तर 8, id वंश, 5-session profile) | बाकी |
| 5 | `trendlines2/` | code + 14 tests (उत्तरं 10-ब, 11) | बाकी |
| 6 | `rsi2/` | code + 12 tests (उत्तर 12, cascade degree-निहाय) | बाकी |
| 7 | `decision2/` + `vision2/` | code + 26 tests (उत्तरं 13–16, tier, N = 6); vision = फक्त veto नियम (API call नाही) | बाकी |

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

## Abhi ची उत्तरं (batch 1) — काय बदललं
प्रश्न 1–16 ची उत्तरं आली (2, 10-अ, 15 मधला खर्च Abhi ⚠️ — तुम्ही भरायचे). Threshold कुठेही सैल केला नाही.

| # | उत्तर | code मध्ये |
|---|---|---|
| 1 | 8 candles / 3σ / 2 स्पर्श तसेच | बदल नाही; मोजमाप तक्त्यात RANGE% **D1 आणि D2 वेगळे** (`swings2/report.py`). शेवटचे 22 दिवस: **D1 40.7%, D2 32.4%** |
| 3 | D4 = display / filter, gate नाही; htf_unknown फक्त D3 | D4 ला कुठेही gate नव्हतं; SWING CHECK box मध्ये "display only" खूण |
| 4 | I_mode = प्रत्येक candle ला पालक trend चं function | `legs2/ik2.py`: पालक RANGE ⇒ trend I जातो, `range_alt` I; RANGE तुटून trend ⇒ §5.1 ने trend I पुन्हा; sticky फक्त trend I च्या identity ला |
| 5 | D3 unknown ⇒ D2 स्वतःचा Dow trend + htf_unknown; D3 RANGE ⇒ range_alt | `ctx()`: पालक unknown ⇒ स्वतःचा trend (RANGE ⇒ range_alt) + `htf_unknown`; पालक माहीत झाला ⇒ I पुन्हा शोध |
| 6 | Thresholds तसेच; ratio फक्त non-NA वर; < 6 non-NA ⇒ NA | ratio आधीपासून non-NA वर होता; आता < 6 non-NA ⇒ verdict **"NA (non-NA < 6)"** (आधी "अस्पष्ट (early)") |
| 7 | final_flag_risk = (a) + (b) + (c) | (c) measured-move जोडलं: पहिला I_end − I_origin, पहिल्या K च्या टोकापासून projection; चालू K पट्टा ± 1σ ⇒ ✓; नोंद + grade |
| 8 | 0.25σ, register 0.15/0.25/0.4 | register बदलला |
| 9 | futures data स्रोत | खाली "प्रश्न 9: तपासणी" |
| 10-ब | provisional K-टोक रेघ trade-योग्य: ≥ 2 held + 3रा touch (close आत) + K आधार-रेघ break ≤ 6 candles | `trendlines2/engine.py` `prov_ok()`; `prov_break_n` = 6 (थर 7 `tl_break_n` शी समान, test) |
| 11 | तीव्र = gate नाही; grade −0.5; तीव्र + 2 ⇒ नाही, ≥ 3 held ⇒ trade-योग्य | `line_class()`; थर 7 `w_steep` = −0.5 |
| 12 | line_skip = 2; register 0/1/2; `line_clear_strict` | प्रत्येक divergence मध्ये `line_clear_strict` (skip 0) खूण |
| 13 | प्रश्न 4 नंतर 22 दिवस पुन्हा, gate-निहाय | खाली "22 दिवस rerun" |
| 14 | VIX (Upstox 15M, known_at = close), event yaml (added_on), macro (fetch time); फक्त size / नोंद | `decision2/context.py`, `decision2/events.yaml` (रिकामी — तुम्ही भरायची); G-I चे दोन्ही **block काढले**: VIX > 22 ⇒ size floor, event ⇒ ×0.5, macro विरुद्ध ⇒ ×0.75; macro grade मधून काढला |
| 15 | default veto-only Sonnet; budget सध्याच्या caps मधूनच | `vision2/veto.py`: `run_budget()` = `visual_audit_daily_cap` (दैनिक budget च्या आत), महिना $5 तसाच; model नाव फक्त VPS `.env` मध्ये (`VISION_VETO_MODEL`) — repo मध्ये नाही |
| 16 | Gray-1 block तसाच | बदल नाही |
| बाकी | tier 1 default; tier 2 setting | `commit_tier()`: tier 2 = t−1 commitment + t चा close त्याच्या टोकापलीकडे |
| बाकी | trendline-break N = 6 | flavour फक्त break आधी ≤ 6 candles मध्ये area स्पर्श असेल तर |
| बाकी | zone id वंश (04 §3) | `assign_ids()`: id बदलत नाही; merge ⇒ जुना id; split ⇒ मूळ pivot चा भाग; मूळ pivot pruning ⇒ तोच id; `lineage` नोंद |
| बाकी | base default | तसंच |
| बाकी | 5 पूर्ण sessions profile; कमी ⇒ NA | `sessions_profile()` (आजच्या आधीची 5 पूर्ण sessions, प्रत्येकात volume हवा) |
| बाकी | cascade degree-निहाय | `cascade()` degree tag नुसार; त्याच degree चे pivots |

**माझा एक अर्थ — तुमचा ✔ हवा (range_alt "जवळची कड"):** "I = जवळच्या कडेपासून दूर जाणारा शेवटचा D1 leg; K = कडेकडे येणारी चाल" —
जवळची कड **t च्या close** पासून मोजली (leg च्या सुरुवातीपासून नाही). कारण: leg-सुरुवात अर्थाने 7 Oct 12:00 ला I = खालच्या कडेपासूनचा
UP leg येत होता (long, आणि भाव वरच्या तृतीयांशात ⇒ G-A थांबा). Close-अर्थाने भाव वरच्या कडेजवळ ⇒ I = वरच्या कडेपासून खाली गेलेला leg,
K = वर येणारी चाल ⇒ trade-बाजू seller (तुमच्या trade सारखी). जवळची कड बदलली ⇒ range_alt I पुन्हा शोधतो.

### प्रश्न 9: futures data तपासणी
1. VPS collector (`collect_index_futures_volume.py`) चा data trade-data (private) मध्ये आहे, पण फक्त **30 Sep – 6 Oct** (5M, 308 rows,
   एक आठवडा). VPS च्या `data/` मध्ये जास्त असेल तर ते trade-data ला push करावं लागेल (VPS block, तुमच्या मंजुरीने).
2. Upstox historical (चालू / पुढचा contract) — token फक्त VPS वर; sandbox मधून call नाही. Expired contracts चा endpoint उपलब्ध आहे का ते
   VPS वरच्या probe ने पाहावं लागेल.
3. तोपर्यंत रोज साठवणं चालू; profile / item 8 NA. Data बनवला नाही; Trade repo मध्ये data नाही.

### 22 दिवस rerun (उत्तर 13; प्रश्न 4 नंतर + review दुरुस्त्यांनंतर; threshold सैल नाही)
528 bars (22 sessions): **setup 0, wait 528**. Gate-निहाय (पहिला थांबवणारा gate):

| Gate | कारण | bars |
|---|---|---|
| G-A | I नाही | 234 |
| G-C | area नाही (zone / रेघ स्पर्श नाही) | 152 |
| G-A | drift regime | 79 |
| G-D | momentum मोजलं नाही (K अवस्था अजून नाही) | 20 |
| G-C | range mode: range-कड (d) zone नाही | 16 |
| G-A | range मध्ये (कडेच्या तृतीयांशात नाही) | 15 |
| G-D | momentum "नाही" | 12 |

D1 I_mode: trend 235, range_alt 59, I नाही 234 bars (आधी 107). **"I नाही" वाढलं:** D2 RANGE असताना (32% वेळ) range_alt I हवा, आणि
जवळच्या कडेपासून दूर जाणारा पात्र confirmed leg नसेल (किंवा त्याचा origin तुटला असेल) तर I नाही. हा उत्तर 4 + "जवळची कड" अर्थाचा परिणाम.

**ठरलेले क्षण:**
- **7 Oct 11:00 – 12:30:** D2 RANGE (pivot पट्टा 22,217 – 22,809) ⇒ range mode. I = range_alt **DOWN** (22,731.8 ⇒ 22,578.2), बाजू seller
  (तुमच्या trade सारखी). K अवस्था "K सुरू झाला असावा" (confirmed K leg नाही ⇒ momentum मोजलं नाही). थांबवणारा gate **G-C "range-कड
  zone नाही"**: 12:00 ला seller zone p1650H (22,715 – 22,735) ला स्पर्श ("K area: हो"), पण तो range च्या वरच्या कडेपासून (22,809) 74 pts खाली ⇒
  0.25σ आत नाही ⇒ d (range कड) खूण नाही. 12:30 ला त्याला d खूण येते, पण त्या candle चा high (22,675) zone पर्यंत पोचत नाही.
  30 Sep → 6 Oct रेघ ("latest", provisional, 3 held) 12:15 ला दिसते, पण "लागू नाही": K आधार-रेघ break नाही (उत्तर 10-ब ची अट); आणि
  §3a नुसार range mode मध्ये फक्त range-कड zone area आहे, रेघ नाही. **तुमचा निर्णय हवा:** range mode मध्ये trade-योग्य रेघ / सामान्य
  zone सुद्धा area मानायचा का, की फक्त range-कड zone?
- **30 Sep 14:00:** D2 DOWN, trend I (23,592.8 ⇒ 22,569.7). **G-C "area नाही"**: trade-बाजूच्या zone / trade-योग्य रेघेला स्पर्श नाही
  (primary "लागू नाही", fans तुटलेल्या, latest तीव्र 0 touches).

**Momentum (उत्तर 6 ची तपासणी):**
- 30 Sep 10:45 – 11:00: **कमकुवत होतोय** (ratio 0.75 / 0.625, non-NA 8). 11:15 नंतर अस्पष्ट, 12:45 – 13:15 नाही, 14:00 अस्पष्ट (0.5;
  SOT, three-push, counter candles लहान, closes, नाममात्र टोक ✗).
- 7 Oct 11:00 – 12:15: K अवस्था नाही ⇒ momentum मोजलं नाही. (Leg-सुरुवात अर्थाने range_alt UP असताना पहिल्या run मध्ये अस्पष्ट 0.43,
  non-NA 7.) **"कमकुवत" नाही ⇒ बिघाड म्हणून नोंद**; threshold फिरवला नाही. Volume (item 8) futures data नसल्याने NA.

### Review (या batch चा, स्वतंत्र) — दुरुस्त / बाकी
**दुरुस्त:** range_alt "जवळची कड" बदलल्यावर I पुन्हा शोध (high; आधी I अडकून राहत होता); VIX / macro timestamps tz-aware ⇒ IST;
जुनी VIX (दुसऱ्या session ची) / macro (> 24 तास) ⇒ NA; trendline-break खिडकी break **आधीच्या** N candles, रेघ area ला थर 5 चा touch bar;
तीव्र + provisional ला सुद्धा ≥ 3 held; provisional खिडकी नेमकी N; zone "वारसा" नोंद एकदाच; tier 2 session ओलांडून नाही आणि flavour
commitment candle वर; charts मधून G-I काढला; profile cache key मध्ये σ.
**मुद्दाम लागू नाही (तुमचा निर्णय):** पालक trend थेट उलटला (UP ⇒ DOWN, मध्ये RANGE / reversal नाही) तर trend I रद्द करायचा का? 02 §5.2
नुसार sticky I फक्त origin real break / reversal ने रद्द होतो — म्हणून तसंच ठेवलं.
**बाकी (नोंद):** `run_budget` / `MODEL_TASK` अजून कोणत्याही replay vision call ला जोडलेले नाहीत (paid call नाही म्हणून); 07 §5 room
(σ 2-day, VIX 18–22 ⇒ +0.5σ strike), `room_mode` / `premium` / `break_entry_mode = retest` register मध्ये पण वापर नाही; 04 §5 per-session
POC / naked POC आणि rollover वगळ नाही; prompt files (07 §3 / §6, 05 §2.7) मधला मजकूर उत्तरांशी जुळवायचा — prompt तुमचे असल्याने मी बदलले
नाहीत.

## Audit थर 1 (`swings2/`) — #1–#10 (branch `claude/v21-audit-l1`)
| # | spec म्हणतो | code करत होता | दुरुस्ती | test |
|---|---|---|---|---|
| 1 | reversal पायरी 2 = CHoCH नंतरचा **confirmed** LH | `p.bar > choch_bar` (आधीच्या bar चा, नंतर confirm झालेला LH सुटायचा) | `p.confirm_bar > choch_bar`; पायरी-3 पातळी [min, max] | `test_audit1_reversal_step2_uses_confirmed_lh` |
| 2 | strong low = BOS ची चाल ज्या **confirmed** low पासून | raw (tentative) low | `strong_price()`: ext नंतरचा confirmed L; तोवर strict | `test_audit2_3_…`, `test_audit2_protected_waits_…` |
| 3 | weak high = न ओलांडलेला high | `weak` = lastH (UP मध्ये HH) | `weak_level()` | `test_audit2_3_…` |
| 4 | D2 साखळी 15M वर | D2 Rhea 1H bars + σ_1H | 15M + σ, पट्टा / min bars × k2/k1 (Abhi: k-प्रमाण) ⇒ 4.5σ / 12 bars | `test_audit4_…`, `test_audit10_rhea_…` |
| 5 | (prompt मध्ये नाही) | pivot-RANGE range_break पट्टा | register `range_band_source = pivots` + 01 §2.1 | `test_audit10_pivot_range_break_…` |
| 6 | replay = live | stream मध्ये फक्त status; replay ला 1m rows पुन्हा वाचायचे | stream मध्ये 1m **निर्णय** (`order`); replay त्यावर (`pivots/dc.py` मध्ये फक्त `order_fn` hook) | `test_audit6_stream_stores_1m_decision_…` |
| 7 | k D2 = 6 (Abhi) | docs मध्ये 8; `K_OPTIONS[2]` 6/8/10 | MASTER §3 + 01 §3; `K_OPTIONS[2]` = 4/6/8 | `test_audit7_8_…` |
| 8 | k-तुलना 3 दिवस | फक्त शेवटचा दिवस | `k_compare_days` = 3 | `test_audit7_8_…` |
| 9 | first_rev same-bar | split खूण फक्त p.bar == b | `rule == "1m"` आणि p.bar ≠ b ⇒ split | `test_audit9_first_rev_…` |
| 10 | tests | — | Rhea end-to-end, pivot-RANGE break, reversal negative (LH आधी step 3 नाही, नवा HH ⇒ रद्द), always-in clause 3, 1m partial, σ_1H | `test_audit10_*` |

**22 दिवस आधी ⇒ नंतर:** D1 बदल नाही (RANGE 40.7%, घटना तशाच). D2 RANGE 32.4% ⇒ **36.9%**, range_start 1 ⇒ 9, range_break 2 ⇒ 10,
protected बदल 9 ⇒ 19 (Rhea आता 15M वर); weak high 313 / 357 bars ⇒ 0 (UP मध्ये शेवटचा H नेहमी HH ⇒ नव्या व्याख्येने weak नाही);
split candles 23 ⇒ 25; pivots तेच (D0 108, D1 29, D2 13).

## Audit 🔴 (#11, 21, 30, 31, 41, 62, 63) — वेगळा commit
| # | थर | spec म्हणतो | code करत होता | दुरुस्ती | test (जुन्या code वर fail) |
|---|---|---|---|---|---|
| 11 | 2 | `eb` नंतर confirmed D1 K leg / उलट pivot ⇒ K | `sweep_of_I_end` नंतर `eb ≠ e.bar` ⇒ state कायम "K सुरू झाला असावा" | `ik2.py`: `eb` नंतर सुरू झालेला K leg किंवा `eb` नंतरचा confirmed उलट pivot ⇒ `ST_K`; `k_from_bar` output | `test_audit11_k_state_not_stuck_after_sweep_of_I_end` |
| 21 | 3 | impulse-K preferred ⇒ momentum danger | सगळ्या hyps forming ⇒ `agg = none` ⇒ `pref_family = None` ⇒ danger कधीच नाही | `fold2.py`: `pref_family` थेट `rec["pref"]` वरून; `FORMING` मधून `impulse_K` काढला | `test_audit21_impulse_k_danger_not_suppressed_by_agg_none` |
| 30 | 4 | अवस्था = सदस्य + bars चं शुद्ध फंक्शन | dead / flipped atoms clustering मध्ये ⇒ नवा zone जन्मताच dead | `zones2/engine.py`: `owner_status()`; dead owner चे atoms `active()` बाहेर; flipped ≠ owner ⇒ link नाही | `test_audit30_dead_and_flipped_groups_do_not_swallow_new_atoms` |
| 31 | 4 | > 1σ sweep = फक्त नोंद | deep sweep `z["sweeps"]` मध्ये ⇒ k_area "हो (sweep)" आणि score | वेगळी `z["deep"]` list; snapshot `deep_sweeps` | `test_audit31_deep_sweep_is_note_only_not_zone_sweep` |
| 41 | 5 | DeMark Q = confirm झालेल्या break ची candle | `L.cand` = buffer पलीकडचा पहिला close (reclaim झालेला false break सुद्धा) | `trendlines2/engine.py`: `break_candle()` — `cb` पासून मागे सलग पलीकडच्या closes चा run, त्याची पहिली candle | `test_audit41_demark_on_confirmed_break_not_earlier_false_break` |
| 62 | 7 | `target_mode` (I_end / उलट कड / measured move / उलट zone) | target = I_end hardcoded | `decision2/engine.py`: `target_price()` dispatch; target मिळत नाही ⇒ G-F no_trade; `10_risk.target_mode` | `test_audit62_target_mode_dispatch` |
| 63 | 7 | §3a फक्त G-C/G-D/G-G/entry बदलतो, बाकी सगळे gates | range mode मध्ये HTF veto, htf_unknown, Gray-1, G-B, position_ban, expiry, संदर्भ, hard_exits, 12 पैकी 7 मुद्दे नाहीत | `decide()`: veto / Gray-1 / G-B / position_ban range branch आधी; `trend_mode()` / `range_mode()` plan देतात; common `_tail()` (G-F, G-H, संदर्भ, hard_exits, grade, size) | `test_audit63_range_mode_gates_do_not_leak` |

Range mode चा target = range ची उलट कड (§3a) — `target_mode` फक्त trend path वर (नोंद `10_risk.target_mode`).

## Abhi चे निर्णय (batch 2, 5 मुद्दे) — काय बदललं
| # | निर्णय | code |
|---|---|---|
| 1 | range_alt "जवळची कड" = close; (a) close मध्य ±1 σ_1H ⇒ कड नाही ⇒ I नाही; (b) `range_alt_edge_from = close` register | `ik2.near_edge()`; `range_alt_mid_sigma` = 1 (legs2 register); prompt 02 §5.1 अद्ययावत |
| 2 | range mode area = (a) कडेचा zone (d) +1 grade; (b) ★ ≥ 2 zone बाहेरच्या तृतीयांशात; (c) trade-योग्य रेघ त्याच तृतीयांशात | `decision2.range_area()`; `w_range_edge` = +1, `range_zone_min_stars` = 2 |
| 3 | `parent_flip`: D2 थेट I-विरुद्ध trend ⇒ trend I रद्द, नव्या दिशेने शोध | `ik2` तिसरं रद्द-कारण; prompt 02 §5.2 + register |
| 4 | macro = NA, `macro_source = none`, परिणाम नाही; `macro_daily` interface | `decision2.context.MacroDailyProvider` (रिकामा); `macro_source` setting; flag "macro_source = none" |
| 5 | `events.yaml` भरा; window = event दिवस + आधीचा 1 session ⇒ ×0.5 | 36 entries: सुट्ट्या 4 (config मधून, `verify`), NIFTY / SENSEX weekly + NIFTY monthly expiry (नियम + 31 Dec 2026 पर्यंत generate), FOMC 28 Oct / 9 Dec (IST परिणाम दुसऱ्या दिवशी, `verify`), RBI MPC 4 Dec / 5 Feb 2027 (`verify`), Budget 1 Feb 2027. `event_size_kinds` = rbi / fomc / budget; expiry / holiday = calendar (size window नाही — माझा अर्थ, तुमचा ✔ हवा) |

**Web:** rbi.org.in आणि federalreserve.gov sandbox मधून उघडले नाहीत (DNS). RBI च्या तारखा RBI press release (prid 62422) चा web-search
सारांश; FOMC च्या तारखा दोन स्वतंत्र calendars. दोन्ही `verify: true` — तुम्ही अधिकृत page वर तपासा.

**22 दिवस पुन्हा (batch 2 नंतर):** setup 0. 7 Oct 12:00 – 12:30 आता **G-C पास** (वरच्या तृतीयांशातला ★ ≥ 2 zone 22,715 – 22,735)
⇒ थांबवणारा gate **G-D**: K अवस्था "K सुरू झाला असावा" मध्ये अडकते ⇒ momentum मोजलं जात नाही. हा audit मुद्दा **#11 (🔴, K अवस्था
अडकते)** — थर 2 च्या audit दुरुस्तीत येतो. Gate-निहाय: I नाही 255, area नाही 152, drift 70, momentum मोजलं नाही 20 + 4, momentum नाही 12,
range area नाही 12, range मध्य 3.

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

**बाकी:** सगळ्यांवर तुमचा निर्णय आला; वरच्या "Abhi ची उत्तरं" तक्त्यात लागू.

## abhi_marked_entries_08sep
**फक्त निदान — code / threshold बदल नाही.** NIFTY replay (`known_at` नुसार, `scripts/decision_check.build_ctx` + `decision2.engine.decide`),
code = #280 worktree (🔴 audit दुरुस्त्यांसह, commit आधीची स्थिती). Panels (15M + 1H, प्रत्येक bar) आणि पूर्ण `diag.json`:
trade-data `review/abhi_marked_08sep/`. 15M bar ची वेळ = candle सुरुवात (chart title वर bar_end, उदा. 14:15 ⇒ 14:30).

### 1. चार bars — थर-निहाय (15M = D1 tracker / f1; 1H = D2 tracker / f2)
| थर | E1 · 01 Sep 11:15 (c 24,126 · h 24,130) | E2 · 03 Sep 10:15 (c 23,985 · h 24,005) | E3 · 04 Sep 11:15 (c 23,982 · h 23,990) | E4 · 07 Sep 14:15 (c 23,784 · h 23,787) |
|---|---|---|---|---|
| 1 regime (थर 7 §2) | **drift** — D2 RANGE (pivot-RANGE: HH 24,379 + LL 23,994), H 6.48 σ_1H, \|net\|/H 0.50 (≥ 0.30 ⇒ range नाही) | **transition ↑** — D2 Rhea पट्टा 23,801–23,896 (2 Sep 14:00) चा 3 Sep 09:15 gap-up break; held pullback नाही | **transition ↑** (तोच break) | **drift** — D2 DOWN, H 6.48 σ, net/H 0.19 (< 0.5) |
| 1 D1 / D2 / D3 | RANGE / RANGE (CHoCH ↓ 28 Aug 24,115 ⇒ reversal पायरी 1) / unknown | RANGE / **DOWN** (protected 24,143) / unknown | UP / **DOWN** (protected 24,143) / unknown | RANGE / **DOWN** (protected 24,025) / unknown |
| 2 D1 (15M) | I **↑ range_alt** 23,994 ⇒ 24,114; **impulse चालू** (24,130 > I_end, D0 उलट pivot नाही) | I ↓ 24,143 ⇒ 23,787; **K चालू** (टोक 24,025, खोली 0.67, 2 legs) | I ↓ 24,143 ⇒ 23,787; **K चालू** (0.67, 4 legs) | I ↓ 24,704 ⇒ 23,787; **impulse चालू** (नवा low 23,738.7) |
| 2 D2 (1H) | I नाही (पात्र leg नाही) | I ↓ 24,143 ⇒ 23,787; K सुरू झाला असावा | I ↓; K चालू | I नाही |
| 3 D1 / D2 | impulse / none | **flat · final_leg_in_progress** (0.97); momentum **अस्पष्ट** (0.5, 8 items) / forming_A | **wedge · final_leg_in_progress** (0.90); momentum **अस्पष्ट** (0.3, 10) / तेच | impulse / none |
| 4 बाजू · K area | buyer (I ↑) · **NA** (K नाही) | seller · **हो (sweep + reclaim)** p1081L 24,010–24,018 (★1, flip seller 1 Sep 13:45) | seller · **नाही** (स्पर्श नाही) | seller · **NA** (K नाही) |
| 4 पातळी A ≈ 24,130 जवळ | kPDH1079 24,126–24,131 seller ★1 (31 Aug PDH) · p1077H 24,092–24,114 seller ★1 (11:30 ला flip buyer, 13:00 मेला) | kPDH1079 24,128–24,143 seller ★2 | kPDH1079 ★1 | kPDH1079 24,141–24,145 ★1 |
| 4 पातळी B ≈ 24,025 जवळ | p1081L 24,010–24,018 buyer ★1 · p1062L 23,991–24,002 buyer ★2 | p1081L seller (flipped) ★1 | p1127H 24,003–24,028 seller ★2 (**self**: 3 Sep 09:15 चं K टोक) · p1081L seller ★1 (11:30 h 24,005.75 — 3.75 pt कमी) | p1127H ★2 · p1160H 23,984–24,006 ★1 · p1081L ★1 |
| 4 23,800 | — | p1103L 23,785–23,815 buyer ★2 | p1103L buyer ★2 | p1103L **seller (flip 7 Sep 11:00) ★1** |
| 5 रेघा | नाहीत | primary trade-योग्य (held 2) · K area रेघ नाही | latest तुटलेली (held 4) · primary लागू नाही | नाहीत |
| 6 RSI | 63.9, label — | 62.5; on_K hidden_bear (24,143 RSI 61.8 vs 24,025 RSI 66.6, strength 0.92), label — | 63.2; तोच hidden_bear, label — | 40.5, label — |
| 7 पहिला अडलेला gate | **G-A drift** | **G-A transition** | **G-A transition** | **G-A drift** |

### 2. विशेष प्रश्न
**a) तुटलेला support ⇒ seller zone?** हो — थर 4 role-flip करतो. 04 §4: "**Pending ⇒ Real break (confirm index) ⇒ flip (b) (retest खूण;
shallow retest मजबूत) ⇒ दुसरा ⇒ मेला.**" आणि §7: "**I खाली ⇒ seller (flip सह) वर**". पण तुमच्या दोन्ही पातळ्यांचे मूळ zones flip नंतर लगेच
**मेले**: पातळी A = 25 Aug HL zone p963L (24,115–24,126, buyer ★2–3) — 28 Aug 11:45 flip ⇒ seller, 28 Aug 15:00 **मेला** (close परत वर =
"दुसरा" real break). पातळी B = 19/20 Aug L zone p883L (24,023–24,039, buyer ★2) — 31 Aug 10:00 flip ⇒ seller, 31 Aug 12:00 **accept ⇒ मेला**
(23,994 नंतर भाव परत वर). म्हणून 01 / 03 / 04 Sep ला 24,130 / 24,025 वर "तुमचा" zone नव्हता; जवळचे नवे zones होते (वरचा तक्ता): A ला 31 Aug
PDH (kPDH1079), B ला 1 Sep 09:45 चा L (p1081L, 1 Sep 13:45 flip ⇒ seller) — E2 ला तोच K area (sweep) म्हणून सापडला.

**b) "impulse चालू 20 Aug – 08 Sep"?** नाही — box फक्त त्या bar ची अवस्था दाखवतो. D1 tracker चा timeline (बदलांचे क्षण):
20 Aug 09:15 I ↓ 24,360 ⇒ 24,026 "K सुरू"; 24 Aug 11:00 **K चालू**; D2 RANGE / unknown मुळे 20, 24, 25 Aug ला I अनेकदा गेला ("mode बदल: पालक
RANGE"); 25 Aug 14:45 range_alt I; 26 Aug 09:15 I रद्द (I_origin 24,313 real break); 26 Aug 11:45 **I ↑ 24,026 ⇒ 24,379** (D2 27 Aug ला UP: HH +
HL) — म्हणजे **25–27 Aug ची चाल system ने नवा ↑ I मानली, ↓ I ची K नाही**; 28 Aug 13:15 – 31 Aug: D2 RANGE ⇒ I नाही / I ↑ पुन्हा; 31 Aug 10:00
I रद्द (24,026 तुटला); 1 Sep 11:15 range_alt **↑** I (23,994 ⇒ 24,114) — **29 Aug – 1 Sep ची चाल ↓ I ची K नव्हती, कारण तेव्हा ↓ I च नव्हता**
(D2 UP / RANGE); 1 Sep 13:45 I ↓ 24,704 ⇒ 23,994 (impulse); 2 Sep 10:15 K सुरू, 12:00 **K चालू**; 2 Sep 14:00 D2 RANGE ⇒ I नाही; 3 Sep 09:15
I ↓ 24,143 ⇒ 23,787 **K चालू** (4 Sep पर्यंत) — **02–03 Sep ला K उघडलेली होती.** 7 Sep 10:45 पासून impulse (नवा low).
K उघडण्याची अट depth / bars / σ ची **नाही** (02 §5.3, `ik2.state`): भाव I_end पलीकडे गेला तर "impulse चालू", जोवर त्या नव्या टोकानंतरचा
**खालच्या degree (D0) चा उलट pivot confirm** होत नाही. 7 Sep: low 23,738.7 (12:45) ⇒ D0 H 23,786.8 (14:30) confirm 15:00 — पण 15:00 च्या
candle ने **23,737.9 (0.8 pt खाली)** नवा low केला ⇒ टोक सरकलं ⇒ तो H आता "टोकाआधीचा" ⇒ K नाही. मुख्य अडथळा: तुमचा I (24,704 ⇒ 23,787) हा
D3-पातळीचा; system D1 I चा पालक D2 घेतो, D3 संपूर्ण काळ **unknown** आणि D2 मध्ये UP / RANGE / DOWN बदलत गेला ⇒ I तुटक.

**c) Regime कोणत्या degree चा?** थर 7 §2 regime = **थर 1 D2** trend + 20 बंद 1H candles (H ≥ 6 σ_1H, net/H ≥ 0.5). D1 regime ठरवत नाही (box मधला
"D1 range" फक्त माहिती). I / K = D1 tracker (पालक D2; D2 RANGE ⇒ range_alt). E1 / E4 मध्ये trend mode बंद **D2 / net मुळे** (D1 मुळे नाही):
E1 D2 RANGE + |net|/H 0.50 ⇒ drift; E4 D2 DOWN पण net/H 0.19 ⇒ drift; E2 / E3 D2 DOWN पण D2 transition ↑ ⇒ G-A.

**d) 07 Sep ★★ zone, "area नाही" का?** स्पर्शाच्या व्याख्येपर्यंत पोचलंच नाही: (1) G-A drift आधी; (2) थर 2 "impulse चालू" ⇒ K नाही ⇒ `k_area`
= **NA** ("I / K नाही"). K उघडली असती तर व्याख्या (04 §7, `zones2.k_area`): K च्या शेवटच्या leg ची कोणतीही candle — **wick** (high ≥ zone
bottom आणि low ≤ top), close नाही; पट्टा `band_convention = base`. 14:15 high 23,786.65 ≥ p1103L bottom 23,784.6 ⇒ "हो" झालं असतं. तेव्हा
p1103L flip नंतर ★1 होता (8 Sep panel वर ★★).

**e) 1H vs 15M panel?** दोन्ही एकाच `charts7.figure()` मधून, **तोच** थर 4 record (`L4[t]`: next पैकी 3 + opp पैकी 2 zones) आणि तोच box. फरक फक्त
x-खिडकी (15M = 3 sessions, 1H = 15) आणि y-range (दिसणाऱ्या candles + zones). run2 चा 08 Sep 15:15 15M panel (trade-data
`review/all7/run2/2026-09-08/1500_15M.png`) मध्ये तीन seller zones (23,800 ★★, 23,760 ★, 23,740 ★) दिसतात. "trade-बाजूचे zones 4" = next ची
संख्या; chart वर पहिले 3 काढतो (4था नाही — हा chart मधला फरक, निर्णयावर परिणाम नाही).

### 3. निष्कर्ष (प्रत्येक entry)
| Entry | अडवणारा थर + कारण | spec नुसार बरोबर / bug / spec त्रुटी |
|---|---|---|
| E1 01 Sep (पातळी A, LH 24,143) | थर 1/7: D2 pivot-RANGE + \|net\|/H 0.50 ⇒ **drift (G-A)**; थर 2: I **↑ range_alt** (buy बाजू); थर 1: 28 Aug D2 CHoCH ⇒ Gray-1 (default block); थर 4: पातळी A चा flip zone 28 Aug ला मेला | Code spec नुसार (01 §2.1, 07 §2, 07 §3 Gray-1, 04 §4). **Spec त्रुटी:** CHoCH नंतर तुटलेल्या पातळीचा retest (LH बनताना) हा setup spec मध्ये नाही; flip नंतर एका दिवसात "दुसरा" break ⇒ पातळी कायमची जाते |
| E2 03 Sep (पातळी B, LH 24,025) | थर 7 **G-A transition ↑** (2 Sep च्या छोट्या D2 Rhea पट्ट्याचा gap-up break); त्यामागे G-C ✓ (sweep p1081L), **G-D** (momentum अस्पष्ट 0.5), **G-G** (flat final_leg_in_progress) | G-A: code = 07 §2 ("दिशा = break ची"). **Spec त्रुटी:** D2 DOWN + protected 24,143 अखंड असताना उलट break ला transition. G-D / G-G spec नुसार |
| E3 04 Sep (पातळी B, LH 24,006) | **G-A transition ↑** (तोच); त्यामागे G-C: p1127H = K च्या स्वतःच्या टोकाचा `self` zone (04 §1 ⇒ कधीच नाही), p1081L ला 3.75 pt ने स्पर्श नाही; G-D अस्पष्ट (0.3); G-G wedge final_leg_in_progress | Spec नुसार. **Spec त्रुटी:** K च्या पहिल्या टोकाचा zone दुसऱ्या test (LH) ला कधीच area नाही; स्पर्शाला सहनशीलता नाही |
| E4 07 Sep (23,800 ★★) | **G-A drift** (net/H 0.19); थर 2 **impulse चालू** (15:00 चा 0.8 pt नवा low ⇒ K reset) ⇒ K area NA | Spec नुसार (07 §2, 02 §5.3). **Spec त्रुटी:** खोल pullback मध्ये 20-candle net/H trend काढून घेतो; एक-tick नवा low K reset करतो |

**Code bug:** या चार bars मध्ये spec-विरुद्ध code सापडला नाही. नोंद (तपासायचं): D2 trend 18–26 Aug "unknown" आणि D3 संपूर्ण काळ unknown (htf_unknown).

**सुचवलेले उपाय (लागू नाहीत, तुमचा निर्णय):** (1) D2 trend उलट range_break + protected अखंड ⇒ transition नाही, regime = D2 trend;
(2) CHoCH retest setup (तुटलेल्या पातळीवर rejection, LH आधी) — size, target (measured move?) ठरवायचे; (3) K च्या आधीच्या टोकाचा self zone
दुसऱ्या test ला area + स्पर्श ± 0.25 σ; (4) sweep / दुसरा test असेल तर G-D "अस्पष्ट" चालेल; (5) नवा टोक K reset करायला ≥ x σ पलीकडे
हवा (E4); (6) regime net/H ऐवजी I-खिडकी किंवा D2 protected अखंड ⇒ trend (E4). Chat मध्ये तुम्ही (1)–(4) वर उत्तरं दिली होती (CHoCH retest पूर्ण
size + measured move; G-G तसाच); त्यांचा **draft patch** trade-data `review/abhi_marked_08sep/proposed_rules.patch` मध्ये ठेवला — **लागू नाही**.
त्या draft चा आंशिक run (measured move आणि दुसरा-test G-D आधी): E1 G-F (R:R 1.94, I_end target), E2 G-G, E3 G-D (11:30–12:00) / G-E (12:15+).

### 4. Abhi चा निर्णय (10 Oct) आणि उरलेलं निदान
**निदान मान्य:** code spec-प्रमाणे; spec मध्ये तीन मुळं — (अ) trend चा degree (D2 ऐवजी D3 / सर्वोच्च confirm degree), (ब) zone-lifecycle (दुसऱ्या
स्पर्शाला मरणं + K-टोकाचा `self` वगळणं), (क) K चा tick-reset आणि pullback मधलं drift / transition. तिन्ही एकाच spec-सुधारणेत (v2.2); ती येईपर्यंत
नियम बदल नाही. `proposed_rules_NOT_APPLIED.patch` trade-data मध्ये तसाच, लागू नाही.

**D2 trend 18–26 Aug "unknown" — कारण:** `swings2.structure.trend_of` = शेवटचे दोन confirmed **non-warmup** H आणि L; कमी ⇒ unknown.
Data 1 Jul पासून; σ ला 20 पूर्ण sessions ⇒ DC (segment "started") ~29 Jul पासून; D2 warm-up 10 sessions ⇒ ~11 Aug पर्यंतचे D2 pivots
`warmup` (4 Aug चा H 24,703.9 सकट). पहिले non-warmup D2 pivots: L 24,025.7 (19 Aug, confirm 20 Aug 09:15), H 24,313.0 (24 Aug), L 24,115.5
(25 Aug), H 24,378.6 (confirm 27 Aug 09:15) ⇒ 2 H + 2 L **27 Aug 09:15** ला ⇒ UP. कमी पडलेली अट = **दोन non-warmup H** (H 24,313 फक्त 24 Aug ला;
दुसरा 27 Aug ला). मधल्या काळात Rhea पट्टा असताना RANGE, बाकी unknown. 4 Aug चा 24,704 H warm-up मुळे trend मध्ये कधीच नाही ⇒ तुमच्या I ↓
24,704 ला D2 पातळीवर आधार नव्हता. D3 (warm-up 30 sessions, k 16 σ) संपूर्ण काळ unknown. Code spec नुसार (01 §1.4 warm-up) — data सुरुवात
(1 Jul) + σ (20) + warm-up (10) मिळून पहिले ~8 आठवडे D2 कमकुवत; हे v2.2 च्या मूळ (अ) शी जोडलेलं.

**v2.2 साठी data (18 Aug – 09 Oct, start_date explicit; E1–E4 आत):** trade-data `review/structure_timeline_22d/` (folder नाव जुनं) —
`a0_D2_pivots_from_1jul.csv`, `a_1h_timeline.csv` (प्रत्येक बंद 1H: D1/D2/D3, protected, थर 2 role / I_origin / I_end / K घटना, G-A regime + कारण),
`b_zones_lifecycle.csv` (जन्म, flip, स्पर्श, मृत्यू + कारण, मृत्यूच्या bar चा close पलीकडे? पुढच्या 1H ने परत घेतला?, `self` प्रसंग),
`c_k_events.csv` (K reset: जुनं-नवं टोक, फरक pts / σ_1H, K अवस्था, किती bars, K टोक, retrace %, I_origin, I_end), `summary.json`, `README.md`.
मुख्य आकडे (222 बंद 1H): regime drift 113 (D2 trend असूनही 60), transition 58, trend_down 36, range 15; सगळे wait (G-A 185, G-C 33, G-D 4);
D3 unknown 222 / 222. K resets 12 (< 0.25 σ_1H 7, 0.25–0.5 1, > 0.5 4). Zones 121 — prune / merge 76, flip नंतर दुसरा break 27 (24 तासांत 21),
accept 5, जिवंत 13; सगळ्या 32 मृत्यूंत close पलीकडे, पुढच्या 1H ने परत घेतला: दुसरा break 6 / 27, accept 1 / 5; `self` वगळले 13 zones / 91 bars.
D2 transitions 14, त्यापैकी protected अखंड 8 (D2 trend च्या उलट 6).

**Chart (दृश्य दुरुस्ती):** box मध्ये "zones 4" पण chart वर 3 — आता box मधले सगळे trade-बाजूचे (next) आणि उलट (opp) zones काढतो.

## पुढे (तुमच्या उत्तरांनंतर)
1. थर 1 ✔ ⇒ थर 2 चा LEG CHECK v2 run (22 दिवस) ⇒ trade-data push ⇒ VPS block (15:30 नंतर, एकच block) ⇒ तुमचा ✔.
2. मग क्रमाने थर 3 … 7 (प्रत्येक थराचं script तयार आहे: `scripts/leg_check2.py`, `pattern_check2.py`, `zone_check.py`,
   `trendline_check.py`, `rsi_check.py`, `decision_check.py`).
3. सात ✔ ⇒ migration prompt (वेगळा टप्पा).
