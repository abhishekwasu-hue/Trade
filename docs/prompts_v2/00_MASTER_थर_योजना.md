# Trade session: Price-action पाया, थर-योजना (MASTER, v2.1, 2026-10-09; चार स्वतंत्र reviews नंतर दुरुस्त)

> **Abhi ची पद्धत (सगळ्या थरांचं ध्येय):**
> 1. **Trend ओळखणं** (weekly ⇒ daily ⇒ 1H ⇒ 15M).
> 2. Uptrend मध्ये **buyer area** वर, downtrend मध्ये **seller area** वर entry; range मध्ये खालच्या कडेला bull put, वरच्या कडेला bear call.
> 3. **Correction चा pattern** ⇒ momentum कमकुवत होतोय का.
> 4. **Commitment candle** (बंद reversal candle / price failure) ⇒ entry. फक्त रेघ / minor swing तुटणं = noise.
> 5. Picture-perfect काही नसतं; view आणि sentiment महत्त्वाचे; R:R ≥ 1:3; ~2 दिवसांचा trade, premium 60–80%.
>
> **का नव्याने (v2):** जुना code सहा pivot संचांवर, 5M Elliott degrees वर, अक्षरानुसार tie-break वर, bar-गणिक बदलणाऱ्या labels वर उभा होता (`reports/Code_logic_audit_and_tools.md`). v2 = एकच पाया; प्रत्येक थर web-संशोधनावर (`research_notes/price_action/01…06`, `trendline_rules_reference.md`); प्रत्येक थर Abhi च्या chart-तपासणीनंतरच पुढचा.

---

## 1. थरांचा क्रम (एक prompt file = एक थर; आधीच्याला Abhi चा ✔ मिळाल्याशिवाय पुढचा नाही)
| # | File | काम | Abhi काय तपासतो |
|---|---|---|---|
| 1 | `01_थर1_SWINGS.md` | एकच swing engine (DC, nested), trend state, BOS / CHoCH / sweep, protected swings, range | swings, trend |
| 2 | `02_थर2_LEGS_IK.md` | leg भूमिका + स्वभाव; impulse I, correction K (sticky) | I / K |
| 3 | `03_थर3_PATTERNS_MOMENTUM.md` | K चा pattern, अवस्था, **momentum कमकुवत होतोय का** | pattern, momentum |
| 4 | `04_थर4_ZONES.md` | buyer / seller areas, liquidity, sweep / accept, ★ | areas |
| 5 | `05_थर5_TRENDLINES.md` | trend रेघा (primary / latest / fan), K ची रेघ | रेघा |
| 6 | `06_थर6_RSI_DIVERGENCE.md` | pivot-based divergence, Cardwell range | divergence |
| 7 | `07_थर7_DECISION_VISION.md` | gates, regime, commitment candle, risk, decision; vision | निर्णय, vision |

## 2. कायम नियम (प्रत्येक थरात हेच)
- **Backtest / IS मोजमाप / VAL / tuning नाही.** सराव = शेवटचे N = 22 trading days (रोज पुढे). मोजमाप = फक्त वर्णन.
- **नव्या code मध्ये तारीख नाही** (logic, settings, tests, fixtures). Expiry contract-field वरून; event calendar = data file.
- **Shadow:** live engines, `elliott/`, `market_state`, `chart_reader`, `levels_v2` बदलायचे नाहीत. Migration वेगळा टप्पा.
- **PAPER; LIVE ला हात नाही; order / broker call नाही; AI / vision कधीच order देत नाही; exits कधीच block होत नाहीत** (budget, listener, vision, approval, वेळ-gate यांपासून exits स्वतंत्र; test).
- **किंमती फक्त OHLC**; **futures फक्त volume.**
- **Holdout कोणत्याही input मध्ये नाही** (pivots, σ, baselines, volume, RSI warm-up, आधीच्या दिवसाच्या पातळ्या, VIX history). Daily/Weekly chart background `display_only` (Abhi ची परवानगी; test: तो data गणनेत पोहोचत नाही).
- **No-lookahead:** प्रत्येक गोष्टीला `known_at`; truncation test प्रत्येक थरात. **Replay = live:** साठवलेल्या प्रवाहावर शुद्ध fold (live run मध्ये उपलब्ध नसलेली माहिती, उदा. 1m status, प्रवाहात नोंदवायची).
- Secrets फक्त VPS `.env`. Charts / JSON फक्त private trade-data (`review/<layer>/<run_id>/`). Merge Abhi च्या मंजुरीने. VPS बदल 15:30 नंतर, एक block.
- **"अंदाज" register:** प्रत्येक थराच्या prompt मध्ये एक तक्ता (आकडा, default, 3 पर्याय, वर्ग: व्याख्या / Abhi / research / NIFTY-मोजलेला / अंदाज, स्रोत). Test: register मध्ये नसलेला अंदाज-आकडा code मध्ये नाही. **एका केससाठी नियम नाही.**

## 3. सामायिक व्याख्या (सगळे थर हेच वापरतात; इथे बदलल्याशिवाय कुठे वेगळी नाही)
- **Series:** 15M spot, `cas_mask` लागू (15:15 नंतरची CAS candle वगळलेली). Bar index = या series मधला क्रमांक. 1H / Daily / Weekly candles **या series पासून aggregate** (1H: 09:15–10:15 … 14:15–15:15; शेवटची 15:15–15:30 लहान); **अपूर्ण aggregate candle कधीच वापरायची नाही.**
- **σ:** मागच्या 20 पूर्ण sessions च्या 15M (high − low) चा median, 09:15 आणि cas candles वगळून; session आधी एकदा, गोठलेला. ATR / Yang-Zhang ने "सुधारणा" नाही. **σ_1H:** तसंच बंद 1H candles वर (पहिली आणि शेवटची लहान 15:15–15:30 candle वगळून). संशोधनातलं "R / MR" ≈ σ.
- **θ_D = k_D × σ;** defaults k = 2 / 4 / 8 / 16 / 32 (D0…D4), Abhi charts पाहून ठरवतो. **Degrees:** D0 आतली रचना; D1 trade (15M वर काढलेली); D2 पालक (8σ साखळी 15M वरच; 1H chart वर दाखवलेली); D3 Daily; D4 Weekly.
- **Pivot:** (degree, H/L, भाव, टोकाच्या candle ची वेळ, `known_at` = confirm candle ची बंद वेळ, नियम-खूण).
- **Break च्या तीन पातळ्या (क्रम ठरलेला):**
  1. **Plain-close घटना** (BOS / CHoCH; थर 1): close पातळीपलीकडे; लवकर; `known_at` = त्या candle चा close.
  2. **Real break** (confirmation; `elliott/breaks.py::first_real_break`, `end = decision_bar`, `retest_fn=None`, cache नाही; त्याचं MR = त्याच्याच settings चा rolling median, **σ नाही**; settings dict नाव + register): I_origin रद्द, zone / रेघ "तुटली", must-hold exits यासाठी.
  3. **Accept:** ≥ 2 लागोपाठ closes ≥ 0.5 σ पलीकडे (sweep नाही); zones (थर 4) आणि रेघा (थर 5, detrended) दोघांना.
  - **कोण मोजतं:** प्लेन-close घटना थर 1; I_origin real break थर 2; zone real break थर 4; रेघ real break थर 5; **D2 must-hold real break थर 7** (तेच `breaks.py`, settings नाव register मध्ये).
  **Sweep:** wick पलीकडे, close अलीकडे (थर 1 घटना; थर 4 चा `zone_sweep` band सह वेगळा).
- **Displacement candle (एकच व्याख्या):** rng_ratio ≥ 1.5 (slot-normalised), body% ≥ 0.6, wick_opp ≤ 0.2 (ICT heuristic; नोंद / कमकुवत पुरावा). **Trend candle(d):** body% ≥ 0.5 आणि CLV_d ≥ 0.6. **Climax candle(d):** rng_ratio ≥ 2 आणि d-दिशेने बंद.
- **rng_ratio:** (H−L) / त्याच 15M slot चा मागच्या 20 पात्र sessions चा median (holdout नाही; session-गोठलेला).
- **RVOL(slot):** futures volume / त्याच slot चा 20-session median (monthly expiry + 2 sessions आधी वगळून; `vol_unreliable`).
- **Merged candle (≤ 3):** O = पहिल्याचा open, C = शेवटच्याचा close, H/L = extremes, `known_at` = शेवटच्याचा close; प्रत्येक candle 09:30 नंतर सुरू.
- **strict_HL(D) / strict_LH(D):** थर 1, degree-निहाय: त्या degree चं सध्याचं structural extreme (शेवटचा HH / LL) ज्या HL / LH पासून निघालं तो. **I_strict_HL:** थर 2, I_end च्या आधीचा D1 HL (I_end देणारा). थर 6 / 7 `I_strict_HL` वापरतात (I sticky असल्याने दोन्ही वेगळे असू शकतात).
- **Retrace खूण (एकच आकडा):** K retrace ≥ 0.80 (register; 0.786/0.80/0.85) ⇒ नोंद + थर 7 flavour बंधन; danger नाही.
- **Trade बाजू:** थर 2 च्या I ची दिशा, पण regime (थर 7) शी विसंगत असेल तर `against_parent` ⇒ no_trade; range मध्ये दोन्ही कडा (थर 7 "range mode").

## 4. प्रत्येक थराचं output
- JSON (`known_at` सह) trade-data; PDF (पहिलं पान = मोजमापाचं वर्णन + अंदाज register); Telegram album "🧭 <LAYER> CHECK n/N · दिवस · वेळ", caption ≤ 8 ओळी / ≤ 1024 UTF-16, code keys नाहीत; replies `backtest_review`.
- Charts: 15M (मुख्य), 1H, Daily (थर 1 मध्ये Weekly). दिवस-अखेर + दिवसात कमाल 3 "महत्त्वाचे क्षण" (प्रत्येक थर स्वतःचे qualifiers लिहितो). Chart मजकूर इंग्रजी चालेल; caption मराठी.
- Abhi ✔ / ✘ ⇒ सामान्य नियमात दुरुस्ती ⇒ पूर्ण महिना पुन्हा ⇒ regression दाखवायचं.

## 5. Trade session साठी
1. आता थर 1. ANNOTATION CHECK / vision run-2 थांबलेले.
2. प्रत्येक थर: module ⇒ suite ⇒ स्वतंत्र review ⇒ run 22 दिवस ⇒ push ⇒ PDF ⇒ VPS Telegram ओळ (15:30 नंतर) ⇒ Abhi ✔.
3. सात ✔ ⇒ migration prompt (वेगळा).
