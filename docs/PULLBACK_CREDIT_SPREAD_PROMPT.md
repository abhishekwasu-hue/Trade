# Claude Code: "Pullback Credit Spread" strategy (Trade repo)

> **वापर:** `abhishekwasu-hue/Trade` च्या Claude Code session मध्ये paste करा.
> **ध्येय:** Abhi च्या trade logic चा **directional credit spread** bot बनवायचा. Entry **फक्त pullback वर**, breakout वर कधीच नाही.
> **मुख्य अट:** एकही setting hard-coded नाही. सगळ्या settings dashboard वर, user-friendly. Default mode **OFF**, चालू केल्यास PAPER.

---

## 0. नियम
1. आधी plan (PR यादी) WORK_LOG मध्ये लिहा, मग थेट काम सुरू करा. फक्त §9 च्या थांबा-बिंदूंवर थांबा.
2. **आधी reuse, नवीन code नंतर.** हे modules आधीच आहेत:

   | Module | कशासाठी |
   |---|---|
   | `opportunity_engine` structure state machine | trend, BOS/CHoCH |
   | `price_action/legs.py` | leg classifier: HEALTHY/DANGEROUS pullback |
   | `price_action/candles.py` | logical rejection score (#241) |
   | `price_action/level_strength.py`, T2.6 events | sweep / real break / failed breakout |
   | `order_safety.py` | market_protection, partial-exit fix |
   | Major Level engine | काम चालू आहे; तयार झाल्यावर जोडायचा |

   यापैकी काही MCX-specific असेल, तर ते साधारण (generic) करा, पण MCX चं वर्तन बदलू नका. याची खात्री tests ने करा.
3. No-lookahead सर्वत्र: confirmed pivots, पूर्ण झालेल्या candles, आणि HTF bar फक्त त्याच्या `bar_end` नंतर.
4. LIVE ला हात नाही. Exits कधीच अडवायचे नाहीत.

## 1. Strategy logic (क्रमाने; प्रत्येक पायरीचं skip कारण Signal Log मध्ये)
1. **Event blackout:** blackout window मध्ये नवीन entry नाही (उदा. RBI, Budget, expiry सकाळ). Exits चालू राहतात.
2. **Trend (HTF):** structure state UPTREND/DOWNTREND. RANGE किंवा WEAK असेल तर skip, setting नुसार. Bias LONG ⇒ फक्त bull put, SHORT ⇒ फक्त bear call.
3. **Level:** निवडलेल्या level engine मधून trend च्या दिशेचा खरा level. Uptrend मध्ये support/role-reversal, downtrend मध्ये resistance.
4. **Pullback quality:** level कडे येणारा leg HEALTHY असायला हवा, DANGEROUS असेल तर skip. Speed ratio, overlap, उलट displacement नाही, आणि depth ≤ setting.
5. **Logical reversal (entry trigger):** touch → reclaim → strength (k × median range) → rejection score ≥ min. Candle TF = level चा TF (default). Reversal नसेल ⇒ entry नाही.
6. **Breakout guard:** level पलीकडे acceptance झाला (real break) तर ती idea रद्द. Breakout वर entry **कधीच नाही.** नवीन दिशेचा role-reversal pullback आल्यावरच नवीन setup.
7. **Strike आणि expiry निवड** (§3) → **order** (hedge-first, market_protection setting) → position.
8. **Exit व्यवस्थापन** (§5).

## 2. Expiry
- **Weekly expiry.** Expiry तारीख instrument master वरून घ्यायची. **Weekday hard-code करायचा नाही** (NSE ने expiry दिवस बदलले आहेत).
- **आज expiry असेल ⇒ पुढची weekly expiry.**
- Setting: `min_dte` (default 1). यापेक्षा कमी DTE असेल तर पुढची expiry.
- Setting: `expiry_type` = weekly (default) / monthly. भविष्यासाठी.

## 3. Short strike निवड (mode dashboard वरून)
| Mode | Setting | उदाहरण default |
|---|---|---|
| `beyond_level` | level पलीकडे buffer (points किंवा %) | 0.3% |
| `distance_pct` | spot पासून % | 1.5% |
| `delta` | target |Δ| | 0.15 |
| `premium` | target premium (₹) | — |
| `strikes_otm` | ATM पासून N strikes | 6 |

- Default mode: `beyond_level`.
- **Guards** (सगळे settings):
  - `min_distance_pct`: कुठल्याही mode मध्ये strike किमान इतका दूर असला पाहिजे.
  - `max_distance_pct`.
  - `min_credit`.
  - `min_credit_to_width_ratio`.
- Strike step instrument master वरून (NIFTY 50, BANKNIFTY/SENSEX 100), hard-code नाही. Rounding नेहमी सुरक्षित बाजूला, म्हणजे दूरच्या strike कडे.
- **Long (hedge) strike:** `width_mode` = points किंवा strikes, default 200 points.

## 4. Risk आणि size
- `risk_per_trade_pct` (capital च्या %). Lots = floor(risk ÷ max loss per lot).
- `max_lots` cap.
- `max_open_spreads` (एकूण आणि प्रति symbol).
- `daily_loss_cap`.
- `event_day_size_multiplier` (default 0.5).
- Margin check: broker margin API.

## 5. Exit आणि adjustment
| Setting | Default | अर्थ |
|---|---|---|
| `profit_target_pct_of_credit` | 60% | Credit चा इतका % मिळाला की बंद. |
| `hard_stop_credit_multiple` | 2.0× | Spread किंमत credit च्या इतक्या पट झाली की बंद. **Logic कुठलंही असो.** |
| `spot_stop_distance_pct` | 0.5% | Spot short strike पासून इतक्या % च्या आत आला की बंद. |
| `real_break_exit` | on | Level चा खरा break: far edge + `break_buffer_pct` (0.1%), `no_reclaim_bars` (3), displacement किंवा retest hold. `confirm_tf` (default 1H). False break वर exit नाही. |
| `adjustment_mode` | close | close / roll (पुढचा strike किंवा पुढची expiry) / add_hedge. |
| `time_exit` | expiry दिवस 14:30 | |

## 6. Timeframes (सगळे settings)
- `trend_tf` (default 1H; HTF veto Daily).
- `level_tf` (default 1H).
- `entry_candle_tf` = `level_tf` (default), override करता येतो.
- `scan_tf` (15m).

## 7. Dashboard: user-friendly (नवीन Streamlit पान "Pullback Credit Spread")
- **विभाग (expanders):**
  1. Mode आणि symbols
  2. Trend
  3. Levels
  4. Pullback
  5. Entry reversal
  6. Expiry
  7. Strike
  8. Risk
  9. Exit / adjustment
  10. Events
  11. Orders
- **प्रत्येक setting साठी:** मराठी label, ⓘ मदत मजकूर ("हे काय करतं, वाढवल्यास काय होतं"), min/max validation, default दाखवा.
- **Presets:** Conservative / Balanced / Aggressive. एका click ने सगळ्या settings भरतात, नंतर हाताने बदलता येतात.
- **Live preview:** "आत्ता signal आला तर" निवडलेला expiry, short/long strike, credit, max loss, lots, आणि कुठली अट पूर्ण किंवा अपूर्ण (✅/❌ checklist). फक्त वाचन, order नाही.
- **Per-symbol settings:** NIFTY, BANKNIFTY आणि SENSEX वेगवेगळे, "सगळ्यांना लागू करा" पर्यायासह.
- **Save आणि इतिहास:** Supabase मध्ये (सध्याच्या settings pattern ने). प्रत्येक बदलाची नोंद (कोणी, केव्हा, जुनं → नवं). "Reset to defaults" बटण.
- **प्रत्येक trade सोबत त्या वेळच्या settings चा snapshot** साठवायचा, नंतरच्या विश्लेषणासाठी.
- Mobile वर वापरता यावं: एका column चा layout.

## 8. Backtest / replay (तेच settings, तेच code)
- Dashboard वरच्या settings ने historical replay. NIFTY offline data, IS 2015–2021, VAL 2022–2024-03. Sealed holdout बंद.
- Option premium साठी उपलब्ध पद्धत वापरा (snapshot किंवा model). मर्यादा अहवालात स्पष्ट लिहा.
- **Random-entry baseline:** त्याच दिवशी, त्याच दिशेने, त्याच अंतराचा spread. तुलना: win rate, expectancy, max DD.
- Setting-निहाय sensitivity तक्ता. PBO नोंदवा.
- अहवाल: `docs/reports/pullback_credit_spread_backtest.md`.

## 9. थांबा-बिंदू
- **G1:** dashboard पान + live preview तयार झाल्यावर, mobile आणि desktop चे screenshots. मी UI तपासेन.
- **G2:** backtest अहवाल. PAPER चालू करायचं का, हा निर्णय माझा.
- **G3:** LIVE. फक्त माझ्या स्पष्ट मंजुरीने.

## 10. Tests
- Expiry निवड: आज expiry असेल तर पुढची; min_dte; सुट्टीमुळे expiry हलली तर.
- Strike modes आणि guards, rounding.
- Breakout वर entry कधीच नाही.
- Reversal नसेल तर entry नाही.
- False break वर exit नाही; real break वर exit.
- Hard stop logic ला bypass करतो.
- Settings validation, presets, snapshot.
- MCX वर्तन बदललं नाही.
