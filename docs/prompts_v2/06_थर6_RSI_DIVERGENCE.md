# थर 6: RSI divergence (v2.1, 2026-10-09)

> Master लागू. **थर 5 ला ✔ झाल्यावरच.** Abhi चा एकमेव indicator = RSI divergence.
>
> **संशोधनाचे धडे (`price_action/06_rsi_divergence_context.md` भाग 1):**
> 1. **Divergence = condition, signal नाही.** Cardwell: trend मध्ये regular divergence = continuation feature; **positive / negative reversal (hidden divergence) = trend resumption** ⇒ pullback संपतोय चा पुरावा (Abhi च्या उपयोगाला जुळतं).
> 2. **RSI range (Cardwell / Brown):** bull 40–80(90), bear 20(10)–60, 40–60 neutral; range shift = RSI बाहेर टिकतो **आणि** structure तुटतं.
> 3. **Objective detection:** price pivots वर; RSI त्याच candle ला; जोडी 5–60 bars; line-of-sight; lag = confirmation.
> 4. **पुरावा:** Bulkowski 19k ~45–55%; फक्त bull-market bullish divergence; पहिला RSI 30–70 ⇒ कमी; Backtrex DAX 4h 38.7% WR; NIFTY intraday काही नाही. "Divergence cascades" strong trend मध्ये.

---

## 0. मूलतत्त्वं
1. Divergence = पुरावा; trigger थर 7.
2. **RSI-range आधी** (`rsi_range` field; थर 7 च्या price "regime" पासून वेगळं नाव), divergence नंतर. Hidden on_K = "K संपतोय"; regular at_impulse_end = risk flag; neutral + RANGE ⇒ range-fade पुरावा.
3. Pivots थर 1 चे (`known_at`); RSI त्याच candle; repaint नाही.

## 1. Input
थर 1 pivots (D0 ⊇ D1 ⊇ D2; degree tag nesting वरून), trend, `gap_bar_2s`; थर 2 I (I_origin, `I_strict_HL`, I_end), K; थर 3 preferred (K चा पहिला / शेवटचा low), अवस्था; थर 4 "K area मध्ये", range-कड (d); थर 5 trade-योग्य रेघ (§2.7). **RSI:** masked 15M closes (cas वगळलेली), Wilder smoothing (RMA), period 14 default (9 पर्याय); `chart_reader.evidence.rsi` शुद्ध असेल तर import + equality test; `rsi_warmup` खूण पहिल्या N bars (setting; holdout मधून warm-up नाही). **1H RSI:** Master च्या aligned 1H candles वर, फक्त बंद candles.

## 2. Detector (A)
```
D0 pivots वर चालवायचा; degree tag = nesting (D1 / D2 असेल तर तसं); same (L1, L2) जोडी दोन degrees मध्ये ⇒ एकदाच (सगळ्यात मोठी degree)
minGap / maxGap per degree (D0 5/60, D1 5/120, D2 3/60 1H-bars; अंदाज); minPriceDiff 0.25 σ; minRsiDiff 3 (अंदाज)
rsi(Li) = RSI त्या pivot candle च्या close वर
regular_bull : price L2 < L1 − Δp AND rsi L2 > rsi L1 + Δr
hidden_bull  : price L2 > L1 + Δp AND rsi L2 < rsi L1 − Δr      (Cardwell positive reversal)   (highs आरसा)
line_clear   : L1→L2 मधली RSI जोडरेघ ओलांडत नाही;  price_clear : मधली candle price जोडरेघेखाली close नाही
emit at known_at(L2) (D2 / 1H: max(pivot known_at, L2 असलेल्या 1H candle चा close))
fields: type, degree, L1, L2, gap, rsi1, rsi2, strength = |Δrsi| / (|Δprice|/σ), gap_between (L1–L2 मध्ये gap_bar_2s), in_K_area (थर 4/5)
```
- **Grade:** regular ला rsi1 ≤ 30 (bear ≥ 70) ⇒ मजबूत; 30–70 ⇒ कमकुवत. Hidden ला rsi_range लागते.
- **on_K (Cardwell positive reversal, सगळ्या templates):** hidden_bull ज्यात **L1 ∈ {I_origin, I_strict_HL}** आणि L2 = K चा शेवटचा low (थर 3 preferred चा C/E/Y-low; नसेल तर K चा सध्याचा confirmed low). `on_K_known_at = max(known_at(L2), label known_at)`. (K च्या A-low vs C-low ही जोडी hidden नसते; ती **`regular_in_K`** = regular_bull A-low→C-low = momentum thinning पुरावा, वेगळी खूण; सध्याचं `evidence.divergence()` हेच मोजतं.)
- **at_impulse_end:** regular_* ज्याचं H2 = I_end.
- **cascade:** एकाच दिशेची लागोपाठ ≥ 2 regular divergences ज्या price ने नाकारल्या (नंतरचा same-type confirmed pivot L2/H2 पलीकडे trend-दिशेने) ⇒ खूण, `known_at` = त्या pivot चा.

## 3. rsi_range classifier (B)
```
RSI pivots: RSI series वर k (setting, default 3) left/right; `known_at` = pivot + k candles चा close (1H: बंद 1H); classifier / shift खुणा त्या `known_at` पासून (truncation test)
window 40 bars (15M) / 20 (1H)
bull_range : min ≥ 38 AND max ≥ 65 AND प्रत्येक RSI trough ≥ 40 (एक trough 38–40 मध्ये चालतो)
bear_range : max ≤ 62 AND min ≤ 35 AND प्रत्येक peak ≤ 60 (एक 60–62 चालतो)
neutral    : बाकी
range_shift_warn (bull→bear): trough < 40 AND पुढचा peak < 60;  (bear→bull): peak > 60 AND पुढचा trough > 40
range_shift_confirmed: warn AND थर 1 CHoCH (त्या दिशेने)
rsi_disagree: थर 1 D2 UP पण bull_range नाही; RANGE पण neutral नाही (1H classifier D2 trend शी)
```
## 3a. अंदाज register
| आकडा | default | पर्याय |
|---|---|---|
| RSI period | 14 | 9/14/21 |
| minGap/maxGap (D0/D1/D2) | 5/60, 5/120, 3/60 | ±50% |
| minPriceDiff | 0.25 σ | 0.15/0.25/0.4 |
| minRsiDiff | 3 | 2/3/5 |
| rsi_range सीमा | 38/65, 62/35, 40/60 | ±2 |
| window | 40 / 20 | 30/40/60, 15/20/30 |
| RSI pivot k | 3 | 2/3/5 |
| grade 30/70 | — | 25/30/35 |
(वर्ग: Cardwell/Brown/Bulkowski research, बाकी अंदाज)

## 4. Mapping (C) (label; निर्णय थर 7)
bull_range + hidden on_K (RSI trough 40–55) ⇒ **"K संपतोय"** (projection = L2 + (मधला swing high − L1 price) नोंद) · bull_range + regular at_impulse_end ⇒ **"continuation trap / risk"** · bear आरसा · neutral + थर 1 RANGE + regular_* थर 4 च्या range-कड zone (d) वर ⇒ **"range-fade पुरावा"** · cascade ⇒ "trend मजबूत" · regular_in_K ⇒ "K thinning" (पुरावा). दोन्ही (regular + reversal) ⇒ reversal प्राधान्य. 1H label > 15M.

## 5. Charts / Telegram
15M + RSI panel: pivots वर RSI ठिपके; रेघा (regular / hidden); labels (type, grade, on_K / regular_in_K / at_impulse_end / cascade, gap_between); 30/40/60/70 रेघा; rsi_range पट्टी; range_shift खूण. 1H तसंच. Box: rsi_range (15M, 1H), शेवटची divergence + label, K जोडणी, final momentum verdict (थर 4 re-emit). Telegram "🧭 RSI CHECK". महत्त्वाचे क्षण: on_K emit, at_impulse_end, range_shift_confirmed.

## 6. मोजमाप (वर्णन)
Divergences (type / degree / grade); on_K %, regular_in_K %; cascade; rsi_range वाटप + थर 1 एकमत; shifts; RSI 9 vs 14 labels फरक; sensitivity.

## 7. Tests
RSI Wilder (equality with evidence.rsi), masked closes, warmup, holdout; detector D0 + degree tag + dedupe; gaps per degree; Δp / Δr; line_clear / price_clear; emit `known_at` (truncation) incl. 1H max rule आणि partial 1H वगळ; 4 types; grade; **on_K = I_origin / I_strict_HL → K last low (A→C नाही); regular_in_K वेगळं; on_K_known_at max rule; सगळ्या templates**; at_impulse_end; cascade व्याख्या; gap_between; in_K_area; classifier (RSI pivots k, band allowance, दोन्ही shifts, CHoCH लागतो, rsi_disagree); mapping सगळ्या ओळी; reversal प्राधान्य; 1H > 15M; replay; shadow (`evidence.divergence()` तसाच); caption; तारीख.

## 8. क्रम
`rsi2/` ⇒ suite ⇒ review ⇒ run ⇒ push ⇒ PDF ⇒ Telegram ⇒ Abhi ✔ ⇒ थर 7.
