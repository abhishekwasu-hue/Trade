# थर 7: Context, commitment candle, निर्णय; मग vision (v2.1, 2026-10-09; चार reviews नंतर दुरुस्त)

> Master लागू. **थर 6 ला ✔ झाल्यावरच.** PAPER / shadow. AI / vision कधीच order देत नाही; exits कधीच block होत नाहीत (budget, listener, vision, approval, वेळ-gate, holdout guard यांपासून स्वतंत्र; test).
>
> **संशोधनाचे धडे (`price_action/05_entry_triggers_risk.md`, `06_…` भाग 2):**
> 1. एकच trigger: भाव reference पलीकडे ⇒ टिकत नाही ⇒ **close** परत. Wick = attempt.
> 2. **Context > candle** (engulfing 63% पण rank 84/103). Brooks: pullback entry 40–60%; breakouts ~80% fail ⇒ failed break वर entry; one-tick stops channels मध्ये hit ⇒ close-based / second entry.
> 3. Confirmation vs anticipation: seller ला confirmation (theta); tier = setting.
> 4. Stops = chart invalidation, P&L stop नाही; 60–80% premium; **P(touch) ≈ 2 × P(ITM)** ⇒ strike invalidation पलीकडे.
> 5. Top-down: HTF veto, MTF must-hold, LTF trigger; markets ~70–80% range ⇒ आधी range की trend.
> 6. Sentiment short-horizon predictive ≈ 0 ⇒ size / width, direction नाही.
> 7. NSE: close = 15:00–15:30 VWAP; expiry 13:00–15:00 decay; 09:15–09:45 noise.

---

## 0. मूलतत्त्वं
निर्णय = **थोडे gates (Abhi चे) + grade (पुरावे)**. Pattern / खोली / divergence / रेघ-break = पुरावा. Correction रेघ / minor swing तुटणं = noise (commitment candle सोबतच). एका केससाठी नियम नाही.

## 1. Input (प्रत्येक बंद 15M candle; `known_at` ≤ decision)
थर 1–6 ची fields (नावं तशीच): थर 1 trend (D1–D4; `unknown` सह), RANGE, protected / strict_HL(D), घटना; थर 2 I (दिशा, origin, end), K अवस्था, flags (`cisd`, `last_leg_start_broken`, `pullback_quiet/heavy`, `SOT_trend`, `climax`, `sweep_of_I_end`), candle features (CLV_d, wick_opp_d, overlap3, rng_ratio, climax_candle); merged candle हा थर बनवतो (Master व्याख्या); थर 3 preferred / अवस्था / `C_short_possible` / `last_leg_short` / `position_ban` / `final_flag_risk` / **momentum** (थर 4 ने re-emit केलेला) / danger; थर 4 "K area मध्ये" (हो / हो-sweep / हो-pending / नाही), zone ★, `self`, accept, confluence, `htf_against`, `open_noise`, `expiry`, range_mode zones; थर 5 trade-योग्य रेघ, ∩, K आधार-रेघ break घटना + Q1–Q3, throw-over touch; थर 6 `rsi_range`, labels (on_K, regular_in_K, at_impulse_end, cascade), `rsi_disagree`. **बाह्य (data rows, `known_at` सह):** India VIX (15M + daily history, holdout guard), event calendar file, expiry field, **macro view row** (`TRADE_MACRO_SENTIMENT_PROMPT.md` चा output, साठवलेला), `gray_policy` + Abhi ची दिशा (review loop `abhi_review` data row; default `block`), `signal_approval_required` (review loop चं `plan_approval_required` वेगळं).

## 2. Regime (D) — 1H वर; एकक **σ_1H**; window = शेवटचे 20 **बंद** 1H candles; net progress decision-bar close ने
- `trend_up`: थर 1 D2 UP **आणि** H = RH − RL ≥ 6 σ_1H **आणि** net/H ≥ 0.5; `trend_down` आरसा.
- `range`: थर 1 D2 RANGE **आणि** |net|/H < 0.3 (एकच व्याख्या; Brooks "flag ही range नाही").
- `barbwire`: range आणि median 1H range < 0.5 σ_1H ⇒ no trade.
- `transition`: range_break पासून, > 5 1H bars बाहेर + पहिला pullback जुन्या कडेबाहेर held होईपर्यंत; **दिशा = break ची; फक्त त्या बाजूचा trade, held pullback नंतर**; size × 0.5.
- बाकी (D2 UP पण H / net अटी नाहीत) ⇒ `drift` ⇒ wait.
- `htf_unknown` (D3 warm-up / unknown) ⇒ setting `htf_unknown_action` ∈ {grade −1, block}, default grade −1.

## 3. Gates (सगळे; ✘ ⇒ wait / no_trade कारणासह)
| # | Gate | व्याख्या | ✘ ⇒ |
|---|---|---|---|
| G-A | **Trend बाजू** | `trend_up` ⇒ bull put; `trend_down` ⇒ bear call; **I ची दिशा ≠ regime दिशा ⇒ `against_parent`**; `range` ⇒ **range mode** (§3a); `transition` ⇒ break-दिशा; `drift` / `barbwire` ⇒ नाही; D3 trend trade-विरुद्ध ⇒ HTF veto (unknown ⇒ §2); Gray-1 (थर 1 "pullback, CHoCH इशारा" D2 वर) ⇒ `gray_policy` (block ⇒ no_trade; reduce + Abhi दिशा ⇒ ती दिशा, size × 0.5) | no_trade |
| G-B | **Must-hold** | D2 strong low/high (थर 1) real break नाही (**हा थर मोजतो:** `breaks.py`, settings `must_hold_break`, register); I रद्द नाही | no_trade |
| G-C | **Area** | थर 4 "K area मध्ये" = हो / हो-sweep / हो-pending (self नाही, accept नाही) **किंवा** थर 5 trade-योग्य रेघ (थर 5 §2.7 / §5, candidate सह; accept ⇒ नाही; ∩ = grade); `htf_against` ⇒ नाही | wait |
| G-D | **Momentum** | थर 3/4 verdict "कमकुवत होतोय", **किंवा** "अस्पष्ट" + थर 6 on_K "K संपतोय"; "नाही" / danger ⇒ ✘. (Master retrace खूण ≥ 0.80: danger नाही; फक्त flavour बंधन §4) | wait |
| G-E | **Commitment candle** | §4 (tier प्रमाणे) | wait |
| G-F | **Invalidation + R:R** | §5; (target − entry)/(entry − invalidation) ≥ 3 underlying वर | no_trade (या candle ला) |
| G-G | **Pattern / position** | preferred ∈ {`final_leg_present`, `complete_resuming`} ⇒ पास; `final_leg_in_progress` + (K आधार-रेघ break घटना **किंवा** `C_short_possible` + candle zone वर) ⇒ **`final_leg_short`** मार्ग (§3b); `forming_*` / `impulse_K` / "ओळखता येत नाही" ⇒ wait; **`position_ban`** (थर 3 §6 व्याख्या) ⇒ no_trade | wait / no_trade |
| G-H | **वेळ / expiry** | सगळ्या (merged) candles 09:30 नंतर; 15:15 नंतर नवी entry नाही; expiry day त्या expiry चा नाही; `min_sessions_to_expiry` (default 2) पेक्षा कमी ⇒ पुढचा weekly | no_trade (candle) |
| G-I | **Risk regime** | VIX > `vix_block` (22) ⇒ नवी entry नाही; event hold-window मध्ये आणि `event_action = defer` ⇒ नाही | no_trade |
### 3a. Range mode (regime = range)
थर 2 चा `range_alt` I/K (I_mode खूण) वापरायचा; G-C = थर 4 range-कड zone (d); G-D = थर 6 "range-fade पुरावा" **किंवा** momentum verdict; G-G = कडेकडची चाल 3-wave किंवा impulse-K नाही; entry फक्त खालच्या / वरच्या तृतीयांशात (मध्य ±1 σ_1H नाही).
### 3b. final_leg_short / S5
C ने A-end गाठलं नाही (थर 3 `C_short_possible` / `final_leg_short`) पण zone वर commitment candle: **S5 निकष** (नकाशा L79 / Correction Reader §4, inline): I च्या शेवटच्या दोन with-trend D1 legs ची किंमत-लांबी कमी होत नाही (थर 2 `SOT_trend` नाही) **आणि** I च्या शेवटच्या दोन टोकांमध्ये regular divergence नाही (थर 6 `at_impulse_end` नाही) ⇒ पुढे, grade −1; नाहीतर Gray-2 ⇒ `gray_policy`.

## 4. Commitment candle (trade दिशा d; बंद candle किंवा Master merged ≤ 3)
| # | Feature | Test |
|---|---|---|
| G1 | Location | candle चं उलट टोक zone / चालणाऱ्या रेघेच्या पट्ट्यात / पलीकडे |
| G2 | Excursion | wick ने स्पर्श / पलीकडे (sweep flavour) |
| G3 | **Reclaim on close** | close area च्या trade-बाजूला **आणि** (CLV_d ≥ 0.67 **किंवा** close आधीच्या candle च्या extreme पलीकडे) |
| G4 | Rejection shape | wick_opp_d ≥ 0.5 (pin) **किंवा** body% ≥ 0.6 दिशा d (strong close; engulfing = feature); दोन्ही ⇒ grade ↑ |
| G5 | Size | rng_ratio ≥ 1.0; counter-दिशेने climax_candle नाही |
| G6 | Not range-bar | overlap3 < 0.6 किंवा close आधीच्या extreme पलीकडे |
| G7 | Second attempt (grade) | याच area वर या K मध्ये आधीचा failed reclaim ⇒ +1 |
| G8 | Not acceptance | थर 4 `accept` नाही (रेघ-आधारित G-C ला थर 5 चा detrended accept) |
- **Tier (setting, default 1):** 0 = फक्त setting मूल्य, code path नाही (शिफारस नाही); **1 = G1–G6 + G8 hard, G7 grade**; 2 = + पुढची candle commitment candle च्या extreme पलीकडे / वरच्या अर्ध्यात close.
- **Flavours (नोंद + grade):** rejection; engulf; **sweep-reclaim** (थर 4 zone_sweep + reclaim + spring test; सगळ्यात मजबूत); **throw-over** (थर 5 K टोक-रेघ throw-over नंतर रेघेच्या आत close; sweep-प्रकार); **trendline-break** (थर 5 K आधार-रेघ break घटना; तीच candle G3–G5; `break_entry_mode` ∈ {break_candle (Abhi), retest}; **G-C तरीही लागतो**: area K च्या शेवटच्या leg ने ≤ N = 6 candles आधी गाठलेला, G1/G2 त्या area वर; invalidation = K tentative टोक; Q1–Q3 ≥ 1 ⇒ grade). **Master retrace खूण (≥ 0.80) ⇒ फक्त sweep-reclaim / throw-over flavours.**
- जुने आकाराचे gates: **फक्त जुन्या engine चा आधीच असलेला output log** (recompute नाही).

## 5. Risk
- **`invalidation_mode` ∈ {candle, structural, farther}** (default structural जेव्हा candle लहान / overlap3 ≥ 0.6, नाहीतर candle): candle = commitment candle चं उलट टोक + `sl_buffer`; structural = K चं टोक (throw-over सह) / rejected zone-रेघेपलीकडे. **Hard exits (नेहमी, hold मध्येही):** I_origin **real break**; D2 must-hold real break. Generic ATR / % P&L stop नाही.
- **Target:** `target_mode` (I_end / range उलट कड; measured move = I-leg size K टोकापासून; थर 4 उलट zone). R:R ≥ 3.
- **Short strike** invalidation पलीकडे; room = **σ(2d)** = setting ∈ {VIX/16 × √2 % (default), 20-session realised 2-day move}.
- **Premium 60–80%**, time-exit = min(दुसऱ्या session चा close, expiry-day `expiry_exit_time` default 13:00). Trade-management state machine (stop to mid, MFE breakeven) = नंतरचा टप्पा; MAE calibration = अहवाल + Abhi-मंजूर batch PR, automatic नाही.

## 6. Grade आणि size
- **Grade = भारित बेरीज (वजनं अंदाज, register):** zone ★ (0–2); ∩ (+1); थर 6 on_K (+1) / regular_in_K (+0.5) / at_impulse_end trap (−1) / cascade (−1); थर 3 ओळख-गुण (0–1) + momentum ratio (0–1); sweep-reclaim / throw-over flavour (+1); G7 (+1); Q1–Q3 (+0.5); G4 दोन्ही (+0.5); `pullback_quiet` (+0.5) / `heavy` (−1); `final_flag_risk` (−1); S5 मार्ग (−1); rsi_disagree (−1); D2–D3 एकमत (+0.5); `open_noise` / 09:30–09:45 (−0.5, नकाशा S12); macro view row (±1). **A ≥ 6, B 4–6, C < 4** (अंदाज). Test: तेच inputs ⇒ तीच grade; macro row grade / size बदलते, `decision` नाही.
- **size_weight** = max(गुणाकार, `size_floor` 0.5): VIX 11–18 ×1; 18–22 ×0.75 (+0.5σ strike); VIX दिवसात +10% ×0.75; event window ×0.5 (defer नसेल तर); transition / gray-reduce ×0.5. PCR / FII / breadth फक्त macro row मधली नोंद.

## 6a. अंदाज register (थर 7)
| आकडा | default | पर्याय |
|---|---|---|
| trend H / net | 6 σ_1H / 0.5 | 4–8 / 0.4–0.6 |
| range net / barbwire | 0.3 / 0.5 σ_1H | ±0.1 |
| transition bars | 5 | 3/5/8 |
| G3 CLV_d / G4 wick / body / G5 rng / G6 overlap3 | 0.67 / 0.5 / 0.6 / 1.0 / 0.6 | ±0.1 |
| trendline-break N | 6 candles | 4/6/8 |
| vix_block / bands | 22; 11/18 | ±2 |
| min_sessions_to_expiry / expiry_exit_time | 2 / 13:00 | 1–3 / 12:30–14:00 |
| grade A/B | 6 / 4 | ±1 |
| size_floor | 0.5 | 0.4/0.5/0.6 |
| sl_buffer | setting (dashboard) | — |
(वर्ग: research / Abhi / अंदाज)

## 7. Output `decision` (12 मुद्दे, परिशिष्ट A क्रम)
1 htf_state (D3/D4, regime, htf_unknown); 2 parent (D2 trend, must-hold, I); 3 impulse_ok (थर 2 गुणवत्ता); 4 character (K labels, volume, CHoCH strict); 5 pattern; 6 complete (अवस्था, position_ban); 7 area (zone ★ / रेघ / ∩ / confluence); 8 depth; 9 price_failure (candle, flavour, G1–G8, tier); 10 risk (invalidation_mode, target, R:R, strike); 11 context (gap, वेळ, expiry, event, VIX); 12 hard_rules. `decision` ∈ {setup, wait(कोणता gate), no_trade(कोणता gate)}, `grade`, `size_weight`, `where_wrong`.
- `setup` ⇒ PAPER signal; Telegram "📌 SETUP" + Approve / Reject (सध्याचा listener; `signal_approval_required`). Live engine ला हात नाही.

## 8. Vision (code नंतर; **फक्त veto, कधीच promote नाही**)
- **कधी:** `setup` किंवा grade ≥ B चा `wait`; Abhi चा manual "मला trade दिसतोय". Budget: `run_vision_budget` (replay साठी वेगळं; live `vision_*` reserve ला हात नाही).
- **काय:** थर 1–6 charts (Weekly, Daily, 1H, 15M सगळ्या layers सह) + `decision` JSON + macro row. किंमती image वरून नाहीत.
- **Vision चं काम:** 12 मुद्दे ✔ / ✘ / ✏️ (labels फक्त; ✏️ मधली कोणतीही किंमत dropped) + agree / disagree / unclear + कारण + `v2_disagree_rules` / `v2_gray_rules` id.
- **नियम:** gate items (4, 5, 6, 9, 10, 12) वर vision ✘ ⇒ setup → `no_trade(vision:<item>)`; vision ✔ / ✏️ कधीच wait / no_trade ⇒ setup करत नाही; evidence items (1, 7, 8, 11) ⇒ फक्त grade. Vision fail ⇒ `vision_fail_action`. Vision कधीच order / exit block / किंमत नाही.
- रोजचा तुलना अहवाल (code vs vision प्रति मुद्दा) review loop मध्ये. FinChart-Bench: vision रचना तपासतं, मोजत नाही.

## 9. Charts / Telegram
15M decision chart (सगळे थर; ⭐ commitment candle; invalidation / target; gates ✓✗; grade; size; momentum; divergence). "🧭 DECISION CHECK n/N" ⇒ Abhi ✔ / ✘ ("मी घेतला असता / नसता, का"). महत्त्वाचे क्षण: setup, gate बदल, Abhi चा live trade note.

## 10. मोजमाप (वर्णन)
Decisions वाटप (gate-निहाय); grade; tiers (वर्णन); **Abhi च्या live trades शी जुळणी** (setup आला का, candle, flavour); vision vs code प्रति मुद्दा; size वाटप; sensitivity.

## 11. Tests
Regime σ_1H / बंद 1H / drift / transition दिशा / barbwire; प्रत्येक gate ✘ ⇒ योग्य wait vs no_trade; against_parent; HTF veto + htf_unknown setting; gray_policy block / reduce; range mode end-to-end synthetic; retrace 0.85 + sweep-reclaim ⇒ setup, + plain rejection ⇒ wait; merged candle (09:30 सगळ्या, invalidation merged extreme); G1–G8 प्रत्येकी; tiers; flavours (trendline-break with/without area ⇒ G-C ठरवतो; throw-over); final_leg_short दोन्ही branches; position_ban; invalidation_mode + R:R त्यावर; hard exits real break; strike पलीकडे; time-exit / min_sessions_to_expiry; G-I; grade determinism + macro row ≠ decision; size floor; output क्रम; vision veto-only / किंमत drop / order नाही / exit block नाही / budget वेगळा; exits स्वतंत्र (budget, listener, vision, approval, G-H, holdout); PAPER; truncation; replay; shadow; caption; तारीख (calendar = data).

## 12. क्रम
`decision2/` + `vision2/` ⇒ suite ⇒ review ⇒ run 22 दिवस (vision setup / B+ दिवस, `run_vision_budget`; model Abhi ठरवतो) ⇒ push ⇒ PDF ⇒ Telegram ⇒ Abhi ✔ ⇒ migration prompt.

## परिशिष्ट A: Vision 12-मुद्दे checklist
1 Weekly + Daily स्थिती, मोठे areas · 2 1H trend, protected swing, impulse · 3 Impulse खरा · 4 Pullback = correction, reversal नाही · 5 Pattern (labels) · 6 Pattern पूर्ण / position · 7 Area (zone / रेघ / confluence; Fib फक्त area सोबत) · 8 खोली · 9 Price failure बंद candle वर · 10 Risk (invalidation, target, R:R ≥ 3) · 11 संदर्भ (gap, वेळ, expiry, event, VIX) · 12 पक्के नियम. **Gates: 4, 5, 6, 9, 10, 12; पुरावे: 1, 7, 8, 11** (2, 3 = संदर्भ).
