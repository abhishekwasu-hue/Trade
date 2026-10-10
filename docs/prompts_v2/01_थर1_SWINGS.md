# थर 1: एकच Swing engine + market structure (v2.1, 2026-10-09)

> Master चे कायम नियम आणि सामायिक व्याख्या लागू.
>
> ## का
> Audit: सहा pivot संच, Elliott degrees 5M वर, 1H trend आणि 15M legs एकाच आकाराचे, ATR मध्ये gap, 18% pivots 09:15 वर. हा थर **एकच** पाया.
>
> **संशोधनाचे धडे (`research_notes/price_action/01_market_structure_swings.md`):**
> 1. दोनच मूळ गोष्टी: **swing point** आणि **structural break** (close पलीकडे). Trend = एका दिशेने breaks.
> 2. Degree = आपण निवडलेला parameter; 2–3 degrees पुरेशा (trade + एक वर).
> 3. Degrees सुसंगत = **nesting** (मोठ्या degree चा pivot लहानचाही). स्वतंत्र zigzags छेद देतात.
> 4. **Reversal = दोन घटना:** Dow failure swing; SMC CHoCH ⇒ LH ⇒ BOS; Brooks: trend-line break ⇒ test of extreme. एक HL तुटणं = pullback (~80% reversal attempts fail).
> 5. Lookahead-safe फक्त confirmation bar वर stamp केल्यास; zigzag चा शेवटचा leg repaint होतो ⇒ signal मध्ये कधीच नाही.
> 6. DC scaling (Glattfelder): swings ∝ δ^−2; overshoot ≈ δ ⇒ उंबरठा ठरवायला, target म्हणून नाही.
> 7. Gap ≥ θ ⇒ लगेच DC पण "gap leg"; gap ने level ओलांडला तर BOS फक्त पहिल्या 15M candle च्या close वर; 2 candles मध्ये परत आत = failed breakout (नोंद).

---

## 1. Engine: DC, nested
### 1.1 D0: 15M bars वर DC, θ₀ = k₀ × σ
```
mode ∈ {UNDECIDED, UP, DOWN}; ext (भाव, bar)
UP: if high >= ext: ext ← (high, bar)                 # बरोबरीत नंतरची candle
    if ext − low >= θ: (same-bar ⇒ §1.3) else confirm H(ext); mode ← DOWN; ext ← (low, bar)
DOWN: आरसा ('<=').  UNDECIDED: max/min दोन्ही; पहिला θ उलटा बदल mode ठरवतो.
```
- Wicks. Confirm candle = θ पूर्ण झाली ती; `known_at` = तिची बंद वेळ. Confirmed pivot कधीच बदलत नाही; चालू टोक = tentative (signal मध्ये नाही).

### 1.2 D1…D4: zigzag चा zigzag (nesting बांधलेलं)
- D(n+1) = DC ज्यात **extreme फक्त confirmed D(n) pivots** मधून, पण θ_(n+1) ओलांडणं **raw bar high/low** वर तपासायचं (θ_(n+1) > θ_n म्हणून तो extreme आधीच confirmed D(n) असतो). D(n) चा tentative extreme कधीच नाही.
- `known_at(D(n+1) pivot) = max(raw crossing candle चा close, त्या D(n) extreme pivot चा known_at)`.
- D4 याच साखळीतून. **Invariant (test):** D(n+1) ⊆ D(n), सावध same-bar नियमासह.
- k पर्याय ("अंदाज"): D0 1.5/2/2.5; D1 3/4/5; D2 6/8/10; D3 12/16/20; D4 24/32/40; पहिल्या run मध्ये D1/D2 चे 3 k शेजारी (3 दिवस) ⇒ Abhi निवडतो. (Prototype: k = 2/4/8 Abhi च्या वाचनाशी जुळले.)

### 1.3 एकाच candle मध्ये दोन्ही घटना
- 1m (फक्त `known_at` ला उपलब्ध) ⇒ high/low क्रम. एकाच मिनिटात दोन्ही / 1m अपूर्ण / 1m 15M शी जुळत नाही ⇒ **सावध नियम:** candle फक्त extend; उलट θ पुढच्या candle च्या स्वतःच्या high/low ने.
- एका candle मधून दोन pivots कधीच नाहीत; नियम (`normal`/`1m`/`conservative`) नोंद; backfill नंतर पुन्हा मोजायचं नाही.
- **Replay = live:** live run प्रत्येक candle ला `1m_status` (complete / partial / absent) प्रवाहात साठवतो; replay त्यावरच fold (test: मुद्दाम missing 1m).

### 1.4 Warm-up, holdout
UNDECIDED पासून; warm-up sessions (D0/D1 3, D2 10, D3 30, D4 60) ⇒ `warmup=true` (निर्णयात नाहीत). Warm-up holdout मध्ये ⇒ data नाही, "अपूर्ण". `display_only` data DC / σ / JSON मध्ये पोहोचत नाही (test).

### 1.5 Gap (09:15)
`gap_bar_2s`: |open − आदला close| ≥ 2 σ. Gap ≥ θ ⇒ लगेच DC, leg ला `gap_leg_theta` (थर 2 ची मापं नेहमीच gap वगळून; flags माहितीसाठी). Gap ने D2 level ओलांडला ⇒ BOS फक्त close वर; 2 candles मध्ये परत आत ⇒ `failed_gap_break` नोंद. अहवाल: 09:15 वरचे pivots %.

## 2. Market structure (D1, D2; माहिती)
### 2.1 Trend state
- शेवटचे दोन confirmed (non-warmup) H, L: HH+HL ⇒ UP; LH+LL ⇒ DOWN; बाकी ⇒ RANGE. < 2 उपलब्ध ⇒ `unknown`.
- **Rhea line / Brooks TR:** ≥ 8 bars highs-lows ≤ 3 σ पट्ट्यात, प्रत्येक कडेला ≥ 2 स्पर्श (wick कडेपासून ≤ 0.25 σ) ⇒ RANGE, पट्ट्यासह, `range_known_at`.
- **EQH / EQL:** एकाच degree चे **लागोपाठचे** दोन same-type confirmed pivots ≤ 0.1 σ (σ नंतरच्या pivot च्या `known_at` चा) ⇒ HH/LH नाहीत ⇒ RANGE कडे; e खूण (थर 4).
- RANGE मध्ये BOS / CHoCH / protected swing नाहीत; फक्त `range_break` (close पट्ट्याबाहेर) घटना.

### 2.2 Protected swings, strict_HL
- **Strong low** = ज्या low पासूनच्या चालीने शेवटचा BOS_up केला; **weak high** = आधीच्या high ला न ओलांडलेला. आरसा DOWN. प्रत्येक घटनेनंतर पुन्हा.
- **strict_HL(D)** = त्या degree च्या सध्याच्या extreme (`last_H1` = शेवटचा HH) आधीचा HL (तो HH देणारा); Master पहा (थर 2 चं `I_strict_HL` वेगळं).

### 2.3 घटना (plain close; नोंद)
- **BOS:** close शेवटच्या with-trend D(n) टोकापलीकडे. **CHoCH:** close strict_HL / strict_LH पलीकडे; सोबत `displacement` खूण (Master व्याख्या) असेल तर `choch_disp`.
- **Sweep:** wick पलीकडे, close अलीकडे (वेगळी नोंद).
- **Reversal (दोन-पायरी, UP ⇒ DOWN):** (1) CHoCH; (2) नंतरचा confirmed D(n) high < `last_H1` (trend चं extreme, शेवटचा HH) ⇒ LH; (3) LH confirm झाल्यावर close CHoCH-ते-LH मधल्या सगळ्यात खालच्या low खाली (नव्या दिशेने BOS). तोपर्यंत "pullback, CHoCH इशारा".
- **Always-in flip (एक logged flag):** reversal पूर्ण; किंवा ≥ 3 लागोपाठ उलट trend candles ज्यांचा net |close_last − open_first| ≥ 3 σ; किंवा range_break + एक follow-through candle.
- D0/D1 CHoCH जी D2 trend विरुद्ध = "pullback सुरू" (थर 2).

## 3. अंदाज register (थर 1)
| आकडा | default | पर्याय | वर्ग |
|---|---|---|---|
| k (D0…D4) | 2/4/8/16/32 | वर | Abhi (charts) |
| EQ tolerance | 0.1 σ | 0.05/0.1/0.15 | अंदाज |
| gap_bar | 2 σ | 1.5/2/3 | अंदाज |
| Rhea पट्टा / bars / touch tol | 3 σ / 8 / 0.25 σ | 2–4 / 6–10 / 0.15–0.35 | अंदाज (Dow line 5%, दिवस) |
| displacement (Master) | 1.5 rng_ratio, 0.6, 0.2 | ±0.25 | research-practitioner |
| always-in | 3 candles, 3 σ | 3–5, 2–4 | Brooks |
| warm-up sessions | 3/3/10/30/60 | ±50% | अंदाज |

## 4. मोजमाप (वर्णन)
प्रति degree: pivots, leg लांबी (bars, σ), confirmation lag, 09:15 %, same-bar नियम %, nesting उल्लंघन (0), gap legs, घटना संख्या, D1–D2 trend एकमत, scaling check (k vs count ∝ k^−2).

## 5. Charts
15M: D1 pivots (HH/HL/LH/LL/EQ), D0 लहान, tentative पोकळ, protected swing रेघ, strict_HL खूण, BOS ▲▼, CHoCH ⚑, sweep ~, RANGE पट्टा, gap_bar खूण. 1H D2; Daily D3; Weekly D4 (holdout राखाडी). Box: प्रति degree trend, 2 pivots, protected, शेवटची घटना. महत्त्वाचे क्षण: BOS / CHoCH / reversal पूर्ण / range_break. Telegram "🧭 SWING CHECK". पहिला run: k-तुलना charts.

## 6. Tests
DC नियम / `known_at` / immutability; truncation; nesting (random + adversarial + सावध नियम); `known_at` monotone across degrees; same-bar सगळे प्रकार + backfill; `1m_status` replay-vs-live; σ (वगळ, गोठ, gap, θ-only confirm नाही); warm-up determinism; holdout + display_only guard; EQ (लागोपाठ, σ at known_at); trend state incl. unknown / RANGE (no BOS/CHoCH); Rhea touch tol; strict_HL; BOS / CHoCH / choch_disp / sweep / reversal 3-पायरी (step 3 फक्त LH नंतर); always-in तिन्ही clauses; gap: confirm+extend candle, gap BOS close वर, failed_gap_break; incomplete day; register completeness; caption / output / order नाही / shadow / तारीख-grep.

## 7. क्रम
`swings2/` ⇒ suite ⇒ review ⇒ run ⇒ push ⇒ PDF ⇒ Telegram ⇒ Abhi ✔ + k ⇒ थर 2.
