# थर 4: Buyer / seller areas, liquidity, sweep (v2.1, 2026-10-09)

> Master लागू. **थर 3 ला ✔ झाल्यावरच.**
>
> ## का
> Abhi: uptrend मध्ये buyer area, downtrend मध्ये seller area; range मध्ये कडा; Fib फक्त area / liquidity सोबत. Audit: Elliott zone फक्त Fib; seller zone input नाही; engines विसंगत. **आपला पुरावा:** level engine एकट्याला random पेक्षा bounce-edge नाही ⇒ area "कुठे", "का" नाही.
>
> **संशोधनाचे धडे (`price_action/04_zones_liquidity.md`, `sr_level_validity.md`):** (a) orders होते आणि भाव वेगाने निघाला (base ⇒ departure); (b) टोकापलीकडे stops (liquidity) — फक्त (b) ला hard पुरावा (Osler). OB/breaker/FVG/Seiden/spring/naked POC: peer-reviewed काही नाही; zone-touch एकटा 38–48%, sweep/displacement confirmation ⇒ 53–59%. Fresh vs tested ⇒ reaction-weighted touch_score. PDH/PDL break = continuation (56–67%). Zone ≤ 1.5 σ. NIFTY volatility 09:15–10:00 सर्वाधिक; expiry days volatile, max-pain नाही.

---

## 0. मूलतत्त्वं
1. Zone चा उगम = **D1+ swing टोक**; base / liquidity / range-कड = flags. PDH/PDL/PDC, PWH/PWL = स्वतंत्र स्रोत. **K च्या आत जन्मलेले zones (origin pivot I_end नंतर) = `self`** ⇒ "K area मध्ये" साठी कधीच नाही (area आधीपासून असायला हवा).
2. Round, gap, Fib (50/61.8/78.6), C=A, pattern रेघा, profile = **confluence**. Open-type / IB extensions या थरात नाहीत (थर 7 नोंद).
3. Zone = पट्टा; भूमिका फक्त उगम + real-break state machine; जागा वेगळी.
4. गुण = पुरावा; trigger थर 7.

## 1. Input
थर 1 (pivots प्रत्येक degree चा `known_at`, EQ, trend + `range_known_at`, σ), थर 2 (legs, labels, I incl. I_end, K, RVOL), थर 3 (रेघा-टोकं, C=A, momentum + item-9 NA), spot OHLC, futures volume, `areas.py::prior_levels` (शुद्ध + holdout guard).

## 2. जन्म
### 2.1 Pivot zone (a)
D1+ pivot = उमेदवार; जन्म = D1 `known_at`; degree वाढ त्या `known_at` पासून. पट्टा H ⇒ [max(O,C), high], L ⇒ [low, min(O,C)]; रुंदी < 0.2 σ ⇒ टोकापासून body कडे वाढव; > 1 σ ⇒ टोकापासून body कडे कापा (जन्माचा σ). भूमिका H seller / L buyer. D0 ⇒ zones नाहीत.
### 2.2 Flags
| Flag | व्याख्या | `known_at` |
|---|---|---|
| **c origin/base** | pivot पासूनचा थर-2 leg आवेग(कमकुवत सह) + departure (पुढच्या 3 candles मध्ये ≥ 2 displacement किंवा net ≥ 2 σ) + जवळचा आधीचा swing plain-close BOS. Band convention = setting (`base` ≤ 2 candles range ≤ 1 σ **किंवा** `ob` शेवटची opposite-colour candle; default base). `fvg` आत असेल तर खूण | max(label known_at, 3री departure candle, BOS candle) |
| **d range कड** | थर 1 RANGE पट्ट्याचा H/L | `range_known_at` |
| **e liquidity** | EQ जोडी, **किंवा** त्या degree चं शेवटचं टोक. Sweep ⇒ e राहतं + `swept_at`; नवं टोक त्या degree वर / accept / real break ⇒ e काढायचं (त्या `known_at` ला) | EQ दुसरा pivot / जन्म |
### 2.3 k: PDH/PDL/PDC, PWH/PWL (पूर्ण sessions), ±0.1 σ. Break + accept ⇒ continuation नोंद.
### 2.4 Confluence-only: round (100/500/1000), gap कड (भरला ⇒ मेला, अपरिवर्तनीय), ruler (Fib, C=A, थर 3 रेघा; थर 5 trade-योग्य रेघ नंतर area), profile (§5).

## 3. एकत्र करणं
फक्त a + k. Linkage overlap किंवा मध्यबिंदू ≤ 0.5 σ (सध्याचा σ; क्रम-स्वतंत्र). Union > 1.5 σ ⇒ सगळ्यात मोठ्या अंतरावर तोडणी, **प्रत्येक भाग ≤ 1.5 σ होईपर्यंत पुन्हा**; एकटा zone > 1.5 σ ⇒ bodies; तरी > ⇒ नाकार. Id = पहिल्या निर्मितीचा सगळ्यात जुना **pivot** (k id ठरवत नाही; k-फक्त गटाला k-id); merge ⇒ जुना; split ⇒ मूळ pivot चा भाग; नोंद. Pruning: D1 20 sessions; D2/D3 फक्त मेलेले / 15 σ दूर; id बदलत नाही. एकच संच; 1H/Daily = filter. अवस्था = सदस्य + bars चं शुद्ध फंक्शन, प्रत्येक candle.

## 4. अवस्था
- **भेट** (एक स्पर्श); **जन्माची चाल भेट नाही.** **Reaction** = break न होता पट्ट्यापासून ≥ 1 σ (अंदाज; θ_D0 नाही) **पुढच्या भेटीपर्यंत किंवा N = 12 bars मध्ये**; चालू भेट मोजायची नाही. **touch_score** = Σ(+1 reaction / −1 नाही), fresh +1.
- **zone_sweep:** wick पलीकडे 0.1–1 σ (अंदाज), close आत (त्याच / 2 candles); > 1 σ पलीकडे + close आत = `deep_sweep` नोंद (थर 1 sweep बदलत नाही). **Reclaim:** 3 candles मध्ये close sweep candle च्या mid पलीकडे. **Accept:** Master. **Spring test:** sweep नंतरचा low ≥ sweep low, volume < sweep.
- **Pending** ⇒ **Real break** (confirm index) ⇒ **flip (b)** (retest खूण; shallow retest मजबूत) ⇒ दुसरा ⇒ **मेला.** **breaker:** flip ज्याच्या आधी (break च्या आधीच्या 20 bars मध्ये) sweep + displacement.
- वय = शेवटच्या reaction पासून sessions (नसेल तर जन्म).

## 5. Profile
Spot candle range वर त्याच वेळेचं futures volume; bins 0.1 σ निश्चित grid; (अ) मागचे 5 पूर्ण sessions (प्रत्येकाचा POC; naked = न स्पर्शलेला, पहिल्या स्पर्शाला retire; composite VA 70%); (ब) I-leg. Rollover वगळ; NA.

## 6. गुण (क्रम / ★)
| ओळ | 0–1 | वजन |
|---|---|---|
| Liquidity (e) + **सगळ्यात अलीकडच्या भेटीत** sweep+reclaim | 1 / फक्त e 0.5 / नाही 0 | 3 |
| Origin (c) | displacement+BOS+fvg 1 / fvg नाही 0.7 / कमकुवत 0.5 | 2 |
| Degree | D1 0.33 / D2 0.67 / D3 1 | 2 |
| Reactions | min(held,3)/3; touch_score < 0 ⇒ 0 | 1 |
| Flip quality | b 0.7 / breaker 1 (sweep इथे पुन्हा नाही) | 1 |
| k / profile (POC-VA) | 1 / 0.6 | 1 |
| वय | ≤ 5 sessions 1 ⇒ 20 sessions 0.5 (D1 pruning शी जुळतं) | 1 |
| `htf_against` | D2 trend विरुद्ध दिशेचा zone ⇒ खूण (थर 7 gate) | — |
भारित सरासरी (NA normalise); ★ निश्चित (< 0.4 / 0.4–0.7 / ≥ 0.7). Raw touches / round / ruler गुणात नाहीत.

## 7. Trade बाजू आणि K
- I खाली ⇒ seller (flip सह) वर; I वर ⇒ buyer खाली; D1/D2 RANGE ⇒ दोन्ही कडा (d) = `range_mode` zones; I नाही ⇒ NA (range mode मध्ये तरी range zones द्यायचे).
- पुढचे ≤ 4; उलट ≤ 2.
- **K area मध्ये:** `self` नसलेल्या trade-बाजूच्या zone ला K च्या शेवटच्या leg ची candle स्पर्श ⇒ **हो**; zone_sweep (+reclaim) ⇒ **हो (sweep)**; pending (close पलीकडे, accept नाही, real break नाही) ⇒ **हो (pending)**; **accept ⇒ नाही**; फक्त ruler / round ⇒ नाही. सोबत zone, ★, कारण, spring-test, `open_noise` (09:15–09:45), `expiry`.
- Confluence (± 0.25 σ): round, gap, Fib, C=A, pattern रेघ, दुसरा zone, POC/VA.
- **Momentum re-emit:** थर 3 चं function item 9 (absorption, फक्त zone) भरून ⇒ **एकच final verdict** पुढे (थर 5/6/7 हाच वापरतात).

## 8. अंदाज register
रुंदी 0.2–1 σ; linkage 0.5 σ; split 1.5 σ; reaction 1 σ / 12 bars; sweep band 0.1–1 σ; reclaim 3; accept 0.5 σ / 2; breaker 20 bars; pruning 20 / 15 σ; वजनं; ★ 0.4/0.7; bins 0.1 σ; VA 70%; confluence 0.25 σ; departure 3 candles / 2 σ — प्रत्येकी 3 पर्याय.

## 9. Charts / Telegram
15M: पट्टे (seller लाल / buyer हिरवा / flip पट्टेदार / pending तुटक / breaker ◆ / self फिके-राखाडी), लेबल (degree, flags, ★, touch_score), trade-बाजू ठळक, Fib/C=A तुटक, I-profile (POC, VA, naked), sweep ~ / accept ≫. 1H D2+; Daily D3+ + आठवडी. Box: बाजू, K area (zone ★ sweep/pending), confluence, पुढचे / उलट, momentum (re-emitted). महत्त्वाचे क्षण: पहिला स्पर्श, flip, मेला, accept. Telegram "🧭 ZONE CHECK" (सुटलेला zone ⇒ किंमत reply, अहवालात).

## 10. मोजमाप (वर्णन)
Zones/दिवस, ★/flags; flip/pending/मेले/breaker; "K area हो" दर (नेहमी हो ⇒ इशारा); sweep vs accept; touch_score; self zones किती; Abhi levels शी जुळणी; sensitivity.

## 11. Tests
जन्म (D1+, degree known_at, पट्टा दिशा, σ गोठ); flags (c known_at max-rule truncation, convention setting, fvg; d range_known_at; e EQ / last-extreme + removal); k; linkage क्रम-स्वतंत्र, split पुन्हा, guard, id (k नाही), merge/split, pruning, regroup; अवस्था (भेट, जन्म-चाल नाही, reaction 1 σ window, open visit, touch_score, zone_sweep band + deep_sweep, reclaim, accept, spring test, pending ⇒ confirm index, flip, breaker pre-sweep, मेला; real break शिवाय भूमिका नाही); गुण (NA, ★, sweep एकदाच, raw touches नाही); profile (spot range, grid, पूर्ण sessions, rollover, naked retire, NA); trade बाजू (range_mode zones, flip सह, ≤4+2, NA); **K area (self वगळ; accept ⇒ नाही; pending/sweep ⇒ हो flagged; ruler नाही)**; momentum re-emit; truncation; holdout सगळे मार्ग; replay; shadow; caption; तारीख.

## 12. क्रम
`zones2/` ⇒ suite ⇒ review ⇒ run ⇒ push ⇒ PDF ⇒ Telegram ⇒ Abhi ✔ ⇒ थर 5.
