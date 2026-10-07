# Claude Code: Trade repo, "Elliott Pullback Credit Spread" bot (संपूर्ण, स्वयंपूर्ण prompt)

> **वापर:** `abhishekwasu-hue/Trade` च्या Claude Code session मध्ये हा prompt paste करा, आणि सोबत **`Elliott Wave trading setups सुधारित.md`** ही file attach करा.
> या विषयावर Trade repo ला आधी काहीही दिलेलं नाही. तुम्हाला लागणारी सगळी माहिती या prompt मध्ये आणि attach केलेल्या spec मध्ये आहे.

---

## 0. संदर्भ
- **Trader:** Abhi. NIFTY (आणि पर्यायी SENSEX) **weekly expiry वर directional credit spreads** (bull put / bear call). 15m वरचे लहान swings. एक trade सरासरी ~2 दिवस चालतो.
- **Repo मध्ये आधी झालेलं (WORK_LOG पाहा):**
  - T1–T5 (#243–#248) झाले. Validation नुसार सध्याच्या level engines ना random levels पेक्षा edge नाही.
  - Strike किती तुटेल हे मुख्यतः **अंतरावर** ठरतं.
  - Leg classifier चे STRONG/WEAK labels REJECT झाले.
  - G3 नुसार order safety (market_protection, exit alerts) जोडलं आहे. Partial-exit fix सुद्धा.
- **नवीन strategy चा आधार:** Elliott Wave. **भविष्य सांगण्यासाठी नाही,** तर दोन प्रश्नांसाठी:
  1. Pullback (correction) पूर्ण झाला का? ⇒ entry.
  2. Count मेला का? ⇒ exit.
- **Spec (attach केलेली file) हाच strategy logic चा एकमेव प्रमाण आहे.** त्यातला विभाग 14 अंतिम आहे. हा prompt प्रक्रिया, dashboard आणि थांबा-बिंदूंसाठी आहे.

## 1. Trader चे अटळ नियम (प्रत्येक PR मध्ये पाळायचे)
1. **Entry फक्त corrective wave च्या शेवटी,** कोणत्याही degree वर, **पुढच्या motive wave च्या दिशेने.** उदा. 2→3, (ii)→(iii), 4→5, B→C, C-(ii)→(iii), पूर्ण ABC→trend, triangle E→thrust.
2. **Breakout entry कधीच नाही.** Level, trendline, आधीच्या candle चा high किंवा sub-wave break, यापैकी कशावरही entry नाही. Gap वर entry नाही.
3. **A चा शेवट entry नाही.** Trend विरुद्धची पहिली leg म्हणजे correction संपली नाही. B च्या आत, triangle च्या आत, आणि "gray" count मध्ये entry नाही.
4. **Logical reversal ने entry:** composite 1–3 candles. Touch → reclaim → strength (1.2–2.5 × median range) → rejection score ≥ min. अनिर्णय असेल तर follow-through ची वाट. Candle TF = setup च्या degree चा TF (auto). Fill पुढच्या candle च्या open वर. पहिली 15 मिनिटं entry नाही.
5. **Expiry:** चालू weekly. आज expiry असेल तरच पुढची weekly. 1 DTE चालतो. Expiry तारीख contract master वरून घ्यायची, weekday hard-code नाही. NIFTY मंगळवार, SENSEX गुरुवार. **BANKNIFTY weekly नाही** (Nov 2024 पासून monthly फक्त).
6. **Short strike** = max(त्या degree चं invalidation + buffer, k × spot × IV × √(DTE/252)). Credit/width guard fail झाला तर **skip**. Strike जवळ आणायचा नाही.
7. **Exit:**
   - Spot ने short strike intrabar ओलांडला तर लगेच.
   - Invalidation चा **खरा break:** buffer = 0.25 × median range पलीकडे close, **आणि** यापैकी एक: displacement candle, पुढची candle reclaim न करणं, किंवा failed retest.
   - Premium 2 × credit, candle close वर.
   - C-wave trades: zone/level वर **उलट logical reversal.**
   - Profit % of credit, आणि expiry दिवशी time exit.
   - **False break (wick, किंवा कमकुवत close नंतर reclaim) वर exit नाही.**
8. **HTF trend = context, gate नाही.** Tier A (मोठ्या trend सोबत) पूर्ण size, Tier B (counter, C-waves) ½, Tier C (शेवटचा टप्पा) ¼ किंवा skip.
9. **सगळ्या settings dashboard वर.** एकही hard-code नाही. **Logic-based:** fixed points ऐवजी median range आणि candle ची ताकद.
10. **PAPER default.** LIVE फक्त Abhi च्या स्पष्ट मंजुरीने. Exits कधीच block होत नाहीत. AI कधीच order देत नाही.
11. **Naked option buy नाही.** एका signal वर एकच position.

## 2. आधी reuse, नवीन code नंतर
| Module | कशासाठी |
|---|---|
| `opportunity_engine` structure state machine, BOS/CHoCH | Swings आणि structure |
| `price_action/legs.py` | Leg features (speed, overlap, displacement) |
| `price_action/candles.py` (#241) | **Composite rejection score.** MCX-specific असेल तर generic करा; MCX वर्तन tests ने अबाधित ठेवा |
| `price_action/level_strength.py` + T2.6 events | Sweep, real break, failed breakout |
| `order_safety.py`, `order_execution.py` | market_protection, partial-exit safety |
| Settings (Supabase pattern), Signal Log, Telegram alerts | सध्याची रचना |
| `opportunity_engine/visual_audit/` | **आत्ता नाही.** नंतरच्या vision prompt मध्ये |

## 3. Phases (एक phase = एक किंवा अधिक PR, `claude/elliott-<slug>`)
| Phase | काम | Spec विभाग |
|---|---|---|
| **E0** | Plan: PR यादी, data उपलब्धता तपासणी (§5), आणि WORK_LOG | — |
| **E1** | **Count engine:** causal multi-degree swings (D0–D3), confirmed/tentative pivots, count tree, alternate counts + score + vote, नियम R1–R11, Neely time नियम (score/delay). **No-repaint CI tests.** | 2, 4, 12 |
| **E2** | **Setups S1–S14** + entry trigger (composite, T1–T7 + no-breakout guard) + invalidation hierarchy (hard/soft, degree प्रसार) | 5, 6, 7 |
| **E3** | Strike, expiry, contract master (expiry, lot, strike_step, freeze), cost model (**STT 0.15% option sale, 1 Apr 2026 पासून; तारखेनुसार दर**), exits आणि management | 8, 9 |
| **E4** | **Backtest + golden-file regression (§4) + अहवाल** `docs/reports/elliott_pullback_backtest.md` ⇒ **G2** | 13 |
| **E5** | **Dashboard पान** (§6) ⇒ **G1 screenshots** | 11 |
| **E6** | (G2 मंजुरीनंतरच) PAPER wiring, default **off**. 1-Min Instant Trader ला हात नाही; तो PAPER baseline म्हणून तसाच | — |

## 4. Golden-file regression (खऱ्या Upstox OHLC वरून)
NIFTY 15m (आणि गरजेनुसार 5m), 25 Sep – 6 Oct 2026. Screenshot वरच्या किंमती ±15 points मानून assertions करायचे.

**अपेक्षित trades:**
| # | केव्हा | Setup | Spread | Invalidation | Expiry |
|---|---|---|---|---|---|
| T1 | 28 Sep, flag चं टोक (~22,870) | (iv) of 3 → (v) | Bear call | 23,027 + flag चं टोक | 29 Sep. **मध्यम खात्री:** reversal candle पडताळा |
| T2 | 29 Sep दुपार, b चा शेवट (~22,625) | b → c of wave 4 | Bull put (Tier B) | 22,570 | 6 Oct. Exit 30 Sep ला 22,805 वर उलट reversal |
| T3 | 30 Sep, 22,801–22,805 वर reversal | Wave 4 चा शेवट → 5 | Bear call (Tier A) | 23,030 | 6 Oct |
| T4 | 1 Oct सकाळ, 22,591–22,608 खाली नकार | (ii) of 5 → (iii) | Bear call | 22,805 | 6 Oct |
| T7 | 5 Oct ~12:15–12:30, B चा शेवट (~22,396–22,400) | B → C | Bull put (Tier B) | 22,217 | 6 Oct |
| T8 | 5 Oct ~13:30, C-(ii) चा शेवट | (ii) → (iii) of C | Bull put (Tier B) | 22,396 | 6 Oct |

**अपेक्षित नकार:**
- 5 Oct 09:50 आणि 10:15 चा bear call (A चा शेवट). लक्षात ठेवा: जुन्या Instant Trader ने इथेच bear calls घेतले होते.
- 1 Oct चा (iv) → (v) of 5 (Tier C).
- 6 Oct 09:15–09:45 (Tier C, entry_start).
- 28 Sep आणि 6 Oct च्या gaps वर entry नाही.
- 6 Oct 09:40 ला 22,614 वर bear call नाही. Level भावाच्या खाली होता, म्हणजे support. Instant Trader ने इथे −51k घेतले होते.

Bot चा निकाल आणि ही यादी जुळली नाही, तर फरक कारणासह report करायचा: bot ची चूक, की वाचनाची चूक (screenshot ±15). फक्त test pass करण्यासाठी logic बदलायचं नाही.

## 5. Data
- **Structure:** NIFTY spot/index 5m/15m (offline + Upstox). Futures नाही.
- **Options P&L:** NIFTY weekly options फेब्रुवारी 2019 पासून आहेत (पडताळा). त्यामुळे 2015–2018 चा भाग फक्त spot-structure चाचण्यांसाठी.
  - Premium साठी उपलब्ध स्रोत: option-chain snapshot recorder, किंवा Upstox historical/expired instruments, हे तपासा.
  - नसेल तर तसं स्पष्ट लिहा, आणि BS model फक्त शेवटचा पर्याय म्हणून, अहवालात ठळकपणे नमूद करून.
  - Historical options data विकत घ्यायचा असेल (TrueData/GDFL), तर पर्याय आणि खर्च द्या, आणि थांबा (**G-PAID**).
- **Splits:**
  - IS 2015–2021 (options P&L 2019–2021).
  - VAL 2022–2024-03.
  - **Sealed holdout 2024-04 नंतरचा, उघडायचा नाही.**
- प्रत्येक काळासाठी त्या वेळचं expiry calendar, lot आणि STT.

## 6. Dashboard (नवीन Streamlit पान "Elliott Pullback Credit Spread")
- **Settings:** spec विभाग 11 + 14 चे सगळे settings, विभागांनुसार (expanders). प्रत्येक setting ला मराठी label, ⓘ मदत ("हे काय करतं, वाढवल्यास काय होतं"), validation आणि default.
- **Presets:** Conservative / Balanced / Aggressive. "Reset to defaults" बटण.
- **Live preview** (फक्त वाचन, order नाही):
  - सध्याचा preferred count आणि alternate (degree-निहाय).
  - चालू correction कुठे आहे (A/B/C).
  - Invalidation आणि entry zone.
  - "आत्ता signal आला तर" expiry, strikes, credit guard, lots, आणि अटींची ✅/❌ यादी.
- **Chart:** wave labels, levels, zone, invalidation आणि signals.
- **Settings बदलांचा इतिहास,** आणि प्रत्येक trade सोबत settings चा snapshot.
- **Signal Log:** प्रत्येक नकाराचं कारण (A-end, gray, Tier C, credit guard वगैरे).
- Mobile वर एका column चा layout.

## 7. कामाची पद्धत
- प्रत्येक PR मध्ये:
  - Tests.
  - Full suite आणि CI हिरवे.
  - **स्वतंत्र self-review subagent:** lookahead, breakout entry, exit-blocking, hard-code, units तपासेल.
  - `docs/WORK_LOG.md` नोंद.
  - मग merge.
- थांबा-बिंदू नसताना प्रश्न विचारू नका. वाजवी निर्णय घ्या, आणि कारण WORK_LOG मध्ये लिहा.
- **थांबा-बिंदू:**
  - **G1:** dashboard screenshots.
  - **G2:** backtest अहवाल, setup-निहाय, tier-निहाय, DTE-निहाय; random baselines आणि PBO सह.
  - **G3:** PAPER/LIVE wiring.
  - **G-PAID / G-COST:** data विकत घेणं, किंवा AI/API खर्च $5 पेक्षा जास्त.
- **चालू काम** (partial-exit fix, BANKNIFTY daily test वगैरे) अपूर्ण असेल, तर आधी ते संपवा, मग E0.
