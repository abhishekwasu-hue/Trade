# Correction Reader (नकाशा भाग II): §13 पायरी 1 चा अहवाल

**हा फक्त अहवाल आहे. यात code चा कोणताही बदल नाही.** हा अहवाल टप्पा B च्या code (`map-a`, deecba6) वरून लिहिला आहे. Correction वाचणाऱ्या भागांत main पेक्षा फरक फक्त एक: टप्पा B चा count-tie नियम. तो `elliott/` मध्ये नाही; `simple_core/count_source.py` मध्ये आहे.

## 1. सध्याची तीन correction वाचनं

| | `elliott/patterns.py` (+ `counts.py`) | `market_state/core.py::correction()` | `chart_reader/structure.py` (`_classify`, `_abc_type`) |
|---|---|---|---|
| Pivots | Degree D0–D3 चे 5m pivots (`swings.multi_degree`), confirmed + tentative | Trade-degree (15M) market_state pivots | market_state चे A/B/C. Weakening / overlap साठी आतले pivots |
| Patterns | zigzag, flat (regular / expanded), triangle (contracting / barrier / expanding), wxy, lead / end diagonal | फक्त labels A, B, C = impulse नंतरचे पहिले तीन legs. Pattern प्रकार नाही | zigzag / flat (3 legs), triangle (5 legs), "impulsive", "complex" |
| Zigzag / flat सीमा | flat: B ≥ **0.90** A (R7, gate). zigzag B band 0.38–0.79 फक्त score | — | flat: B ≥ **0.90** A. zigzag: B ≤ **0.79** A **आणि** C ने A चं टोक ओलांडलं. 0.79–0.90 = "unclear" |
| C ची अट | Gate नाही. `start-of-C` invalidation. `g_c_time` = t(C) ≤ t(A)+t(B) (score) | C = B नंतरचं टोक (confirmed नसेल तर tentative) | zigzag ला "C ने A ओलांडलं" आवश्यक. flat C-end ला C ≥ 0.9 A (`flat_c_min`) |
| Triangle | R8: D, B च्या आत (barrier सहनशीलतेसह). E, C च्या आत (invalidation). "C, A च्या आत" अशी अट **नाही** | — | 5 legs: legs 3 < 1, 4 < 2, 5 < 3 **आणि** सगळे legs A च्या पट्ट्यात (स्वतःची व्याख्या) |
| Overlap | — | `overlap_ratio` (bar ची स्वतःची range, 50%). correction ≥ **0.60**; impulse < **0.40** | `_overlap_ratio` (तीच K10.1 व्याख्या). Leg गुणांसाठी वेगळी "सरासरी overlap" (`_leg`) |
| स्थिती | count beam (पसंतीचा + पर्यायी), चालू wave, पुढची दिशा (`NEXT_MOTIVE`) | `status`: none / not_started / shallow / correction / unclear / origin_broken | `entry_point`: zigzag C-end / flat C-end / triangle E-end |
| Origin break | R1 / R6 (भावावरून) | `breaks.py` real break ⇒ `origin_broken` | market_state कडून |

**मुख्य फरक:**
1. **तीन वाचनं जोडलेली नाहीत.** Elliott count एका degree वर 5m pivots ने वाचतो, तर market_state आणि chart_reader 15M trade-degree pivots ने. त्यामुळे एकाच दिवशी तिन्ही वेगवेगळं सांगू शकतात. उदा. 7 Oct ला market_state चं ABC = C-end, तर count engine चं D3 = "flat/B", tie मध्ये.
2. **Zigzag / flat सीमा दोन ठिकाणी वेगळी:**
   - elliott: flat ≥ 0.90 (gate), zigzag चा पट्टा फक्त score;
   - chart_reader: 0.79–0.90 = "unclear".
   - Spec चा NEoWave पर्याय (0.618) कुठेच नाही.
3. **C ची अट तिन्हीकडे वेगळी:**
   - elliott मध्ये C ने A गाठणं gate नाही;
   - chart_reader मध्ये zigzag ला gate आहे;
   - market_state मध्ये अट नाहीच;
   - टप्पा B च्या `reading.correction_legs` मध्ये नकाशा P2 प्रमाणे gate आहे (Gray-2).
4. **Triangle च्या दोन व्याख्या:**
   - elliott R8: D / B आणि E / C;
   - chart_reader: legs लहान होत जाणं + सगळे legs A च्या पट्ट्यात.
5. **Overlap च्या तीन व्याख्या आणि तीन thresholds:**
   - market_state 0.40 / 0.60;
   - `price_action/legs.py` 0.35 / 0.55 (`o_lo`, `o_range`);
   - chart_reader (K10.1 + leg-सरासरी).

## 2. Spec चे जे भाग आधीच code मध्ये आहेत

| Spec | Code मध्ये | फरक / नोंद |
|---|---|---|
| §3.1 R6: B, A च्या सुरुवातीपलीकडे नाही | `patterns.py` R6 (gate) + invalidation | ✔ तसंच |
| §3.4 R7: flat B ≥ 0.90 A | `flat_b_min_ratio` 0.90, `calibrate=False` | ✔ gate (spec §3.7 नुसार तसाच) |
| §3.6 R8: triangle D / E आत | `patterns.py` R8 (+ `barrier_d_tol_atr`) | "C, A च्या आत" नाही |
| §3.6 / R5: triangle wave 2 म्हणून एकटा नाही | `CHILD_FAMILY[("impulse","2")]` मध्ये triangle नाही | ✔ |
| §5.1 B वेळ ≥ A | `g_time_ab` (score) | ✔ score |
| §5.1 C वेळ > A | `g_c_time` = **t(C) ≤ t(A)+t(B)** (Neely ची वरची मर्यादा) | ⚠ उलट बाजू: spec ला खालची मर्यादा (C > A) हवी. आज ती नाही |
| §3.1 B पट्टा | `g_b_band` 0.38–0.79 (score) | ✔ score |
| §1.2 Same degree | `swings.similar_degree`, `similarity_balance_min`, `g_sim_12` | ✔ |
| §3.5 diagonal R9 + overlap | R9: w4 ≯ w2 end (gate). `g_diag_overlap` आणि `g_diag_converge` = **score** | ✔ overlap gate नाही. Contracting व्याख्या (3 < 1, 5 < 3, 4 < 2) gate नाही, फक्त `g_diag_converge` score + R2 invalidation |
| §3.5 end_diag C position | `CHILD_FAMILY` (zigzag / flat चा C = impulse / end_diag). `counts.py:193` पूर्ण end_diag ला दिशा 0 (S11) | ✔. Shadow reader ने `counts.py` बदलायचा नाही (spec प्रमाणे) |
| §3.6 expanding triangle | `tri_exp` ⇒ `nm = 0` (entry नाही) | spec: फक्त नकारात्मक पुरावा (Abhi चा निर्णय बाकी) |
| §2.3.1 origin real break | market_state `origin_broken` (`breaks.py`); टप्पा B `reading.origin_state` S4 / S7 | ✔ |
| §4 `final_leg_short` / Gray-2 | टप्पा B `reading.correction_legs` (C ने A गाठलं का; truncated ⇒ Gray-2) | अंशतः: S5 निकष आणि lower degree तपासणी नाहीत |
| §2.1 वेग / overlap / ER / counter wicks | `legs.py speed_ratio`, `overlap_ratio`, `efficiency`, `structure cw_parts` | ✔ (मापक आहेत; reader मध्ये एकत्र नाहीत) |
| §2.1 RSI divergence, futures volume | `evidence.divergence()`, `chart_reader/volume.py` | ✔ (IS मध्ये volume नाही) |
| §6 12 साधनं, trendline `tl_*` | `chart_reader/areas.py`, `sloping()` | ✔ |
| §7 composite rejection | `elliott/reversal.py` | ✔. Sweep + reclaim आणि throw-over वेगळे triggers म्हणून नाहीत |
| Double zigzag वि. combination | `wxy` एकच pattern | ✘ फरक नाही |
| Running flat | नाही | ✘ |

## 3. §3.7: आज code मध्ये gate, पण स्रोत research / practitioner (Abhi च्या निर्णयासाठी; बदल नाही)

| आकडा / नियम | Code | आजचा वर्ग (A1 register) | स्रोत | Spec ची नोंद |
|---|---|---|---|---|
| `flat_b_min_ratio` = 0.90 (R7) | `elliott/settings.py:91`, `patterns.py:242` (gate) | "नियम" असं लिहिलं आहे, `calibrate=False` | Practitioner (Wavetraders "≥ 90%"); EWI पानावर सापडलं नाही. NEoWave 0.618, Wagner 0.78 | IS sensitivity 0.618 / 0.786 / 0.90 |
| Triangle R8 (D आत B, E आत C) | `patterns.py:270–298` | नियम | Practitioner (EWI पानावर पडताळणी नाही) | + "C, A च्या आत" जोडायचं का? (आज नाही) |
| `flat_b_max_ratio` = 2.0 | `settings.py:92` (flat gate; triangle B सुद्धा) | अंदाज | Practitioner ≤ 1.382 (Wavetraders, Wagner) | Sensitivity 1.382 / 2.0 / 3.0 |
| wxy: X ≯ W origin | `patterns.py:303` (gate) | अंदाज | Inference (spec §D) | — |
| Diagonal overlap | `g_diag_overlap` = score (gate नाही) ✔ | — | EWI "almost always" | ✔ spec प्रमाणे |
| chart_reader `zigzag_b_max` = 0.79, `flat_c_min` = 0.90 | `chart_reader/settings.py:122–124` (entry_point gate, shadow engine) | अंदाज | KB K3 family / R7 | Shadow engine मध्येच; Simple Core live gate नाही |

**थर 3 (patterns2) मधून नवे मुद्दे (थर 3 prompt §10.4; Abhi च्या निर्णयासाठी, आज default):**

| मुद्दा | थर 3 मध्ये आज | पर्याय |
|---|---|---|
| Sub-wave ची आतली रचना (A = 5, B = 3, C = 5) | **पुरावा** (गुण), gate नाही. कारण: रचना swing उंबरठ्यावर अवलंबून (EW संशोधन Q5; थर 2 मध्ये रचना फक्त नोंद) | spec §3 प्रमाणे RULE (gate) |
| Wedge चा truncation gate (5 हा 3 च्या टोकापलीकडे) | gate (EWGold) | EWP: पाचव्या wave चं truncation शक्य (recalled, verify) ⇒ gate काढणं |
| संपूर्ण-K wedge "ending" म्हणून entry | नाही: पहिला पाच-legs भाग = leading (A) ⇒ "थांबा" (`wedge_as_ending` = False) | ending diagonal म्हणून शेवटचा leg / entry (Correction Reader §3.5) |
| Triangle: "C, A च्या आत" | अट नाही (contracting मध्ये C, A पलीकडे चालतो) | अट जोडणं |
| Expanding triangle | valid, गुण 0.5 ("expanding उप-प्रकार"); code मध्ये `nm = 0` | पूर्ण बंदी / फक्त नकारात्मक पुरावा |
| Flat B/A > 2.0 | gate नाही, m 0.2 (आजच्या code मध्ये gate) | gate ठेवणं |
| गुण बरोबरीत शेवटचा tie-break | गुण ⇒ नवा I ⇒ pattern-क्रम ⇒ (फक्त निश्चिततेसाठी) wave-सीमा, म्हणजे position | दुसरा नियम (उदा. alternate दोन्ही दाखवणं) |
| शेवटच्या wave चं confirmed टोक पुढे सरकलं (उदा. C लांबला) | तोच hypothesis ("extension"), बदल मोजत नाही | spec §5.3 शब्दशः: identity जुळत नाही ⇒ बदल |

## 4. 22 Sep: area ला पहिला स्पर्श कोणत्या bar ला?

हे decision-bar data वर तपासलं (प्रत्येक bar ला फक्त त्या वेळी माहीत असलेले zones; touch tolerance 0.3 MR, सध्याचं):

| 15M bar | O / H / L / C | त्या वेळचे seller zones ज्यांना स्पर्श | Simple Core |
|---|---|---|---|
| **09:15** | 23,454.0 / **23,489.0** / 23,425.7 / 23,446.0 | **PDH 23,462–23,471** आणि SWH 23,465–23,469 | opening window |
| 09:30 | 23,448.0 / 23,459.5 / 23,433.2 / 23,456.0 | PDH | area वर commitment नाही |
| 09:45 | 23,456.2 / 23,464.5 / 23,449.5 / 23,457.2 | PDH | — |
| 10:00 | 23,457.2 / 23,470.6 / 23,453.0 / 23,465.2 | PDH | — |
| **10:15** | 23,465.1 / 23,466.0 / 23,431.3 / 23,437.3 | PDH, SWH 23,469–23,472 | **commitment (34.6) < 1.5 × pause सरासरी (30.6) ⇒ नाकारली** |
| 10:30 | 23,437.3 / 23,439.8 / 23,368.2 / 23,382.7 | (खाली गेलं) | — |

**उत्तर:**
- Area ला पहिला स्पर्श **09:15 च्या bar ला** झाला: high 23,489, PDH / swing-high पट्ट्यात, close परत खाली (rejection).
- Spec प्रमाणे तो bar trigger चा भाग नाही (`entry_start` 09:30).
- 09:30–10:00 हे तीन bars त्याच पट्ट्याला लागून आहेत (pause).
- **10:15 = bearish engulfing:** 10:00 ची bull body 23,457.2–23,465.2 ही 10:15 च्या bear body (23,465.1 → 23,437.3) ने पूर्ण झाकली. Abhi चा 10:15 entry हाच.
- Code ने तो size gate (`commitment_vs_pause`) मुळे नाकारला. `commit_vs_impulse` = 1.04 (टप्पा B I6 अहवाल).

**Spec च्या areas शी तुलना:**
- (अ) Code चा पट्टा = **PDH 23,462–23,471 + swing high**. Spec म्हणतो "flip 23,445–23,473". त्या नावाचा flip zone code च्या यादीत नाही, पण पट्टा तोच आहे (PDH + liquidity).
- (ब) "16 Sep पासूनच्या highs ची चढती रेघ" = code ची `TL-R2609160915` (16 Sep 09:15 पासून). 09:15 ला ती 23,497–23,504, 10:15 ला 23,506–23,514 वर होती. Bars तिच्यापर्यंत पोहोचले नाहीत (09:15 high 23,489: रेघेच्या 8 pts खाली; 0.3 MR सहनशीलता ≈ 5 pts). म्हणजे सध्याच्या `tl_touch_mr` ने रेघेला **स्पर्श नाही**.
- **Abhi च्या निर्णयासाठी:** हा फरक आहे, पण golden pass करण्यासाठी कोणताही आकडा बदललेला नाही.

## 5. पुढे (spec §13)
- **पायरी 2:** टप्पा B merge झाल्यावर `correction/` module (shadow), charts आणि tests. Live engine, commitment gate आणि market_state thresholds बदलायचे नाहीत.
- **पायरी 3:** golden केसेस + आजच्या vision test (12 मुद्दे) शी तुलना, charts सह.
- **पायरी 4:** §11.3 IS मोजमाप. **पायरी 5:** draft PR (merge Abhi च्या मंजुरीनेच).
- Abhi चे निर्णय येईपर्यंत spec मधले defaults वापरायचे.

## 6. बदल (Abhi, नंतरचे निर्णय)
- **Backtest बंद:** पुढची सूचना येईपर्यंत कोणतंही backtest, IS मोजमाप किंवा VAL नाही. यात टप्पा B §4, macro §4 आणि या spec चा §11.3 येतात. चालू असलेलं टप्पा B §4 मोजमाप थांबवलं.
- **Code / tests मध्ये तारीख नाही.** §11.1 च्या golden केसेस आणि §12 मधले तारखांचे tests code मध्ये जाणार नाहीत. ती उदाहरणं फक्त अहवालात, तुलनेसाठी.
- **नवं काम:** annotation (ANNOTATION CHECK, `correction/` shadow module). शेवटचा सुमारे एक महिना annotate करायचा, Abhi ✔ / ✘ देईल. Vision चा टप्पा त्यानंतर.
- **पायरी 2 मध्ये तीन भर** (annotation module मध्ये लागू होतील):
  1. `g_c_time` (t(C) ≤ t(A) + t(B)) तसाच, आणि spec §5 ची खालची सीमा "t(C) > t(A)" वेगळा पुरावा (score; gate नाही).
  2. पायरी 3 च्या अहवालात 22 Sep 10:15: `elliott/reversal.py` composite (touch / reclaim / strength / close location) पास होतो का; नसेल तर कोणती अट अडवते (उदा. strength 1.2 MR); engulfing feature काय म्हणतो. आकडा बदल नाही.
  3. Trendline: code ची TL-R2609160915 आणि Abhi ची रेघ (15 Sep नंतरच्या low पासून, 17 Sep च्या high मधून, 22 Sep पर्यंत) दोन्ही काढायच्या. `tl_touch_mr` तसाच; फक्त फरक अहवालात.

### तुलनेसाठी उदाहरणं (फक्त अहवाल; tests मध्ये नाहीत)
| केस | Abhi चा निर्णय | आधार |
|---|---|---|
| 22 Sep 10:15 | bear setup | Abhi चा live trade |
| 30 Sep ~13:00 | bear setup (wedge C, flip 22,808) | Abhi चा live trade |
| 30 Sep 10:30 | entry नाही (wedge अपूर्ण) | रात्रीचा log |
| 7 Oct 12:15 | bear (C ending diagonal + trendline + seller zone) | नकाशा I7 ✔ |
| 26 Aug | bear | I7 ✔ |
| 12 Aug | bull put नाही (Gray-1 / S3) | I7 ✔ |
| 31 Aug | trade नाही (R:R 1:1.1) | I7 ✔ |
| **9 Oct 14:21** | **trade नाही.** NIFTY 15M Dynamic SR bearish signal, 22,565 resistance (touch). Vision V1 ने veto केला आणि Abhi ने trade घेतला नाही. कारणं: price failure नाही, close bar च्या मध्यात, 22,180 पासून जोरदार rally, correction अपूर्ण, शेवटचा तास. | Abhi (live) |

### नवे सामान्य नियम (Abhi, नंतर)
1. **Futures फक्त volume साठी.** रचना, levels, zones आणि RSI सगळं spot वर. Futures चं volume spot च्या bar ला **वेळेने** जोडलं जातं (`chart_reader/volume.py`: continuous contract, 15M bins); futures चे भाव कुठेच वापरले जात नाहीत.
2. **Monthly expiry चा rollover:** continuous contract बदलल्याचा दिवस (`roll_day`) वेगळ्या खुणेने (chart वर नारिंगी bars) दाखवला जातो आणि impulse वि. correction तुलनेत धरला जात नाही.
3. **Correction मधल्या छोट्या swing चा किंवा correction च्या स्वतःच्या रेघेचा break = noise.** फक्त नोंद (box मध्ये "नोंद (noise)"). पुष्टी नाही, grade नाही, entry नाही. निर्णय फक्त area वरच्या price failure ने.
4. **Annotation:** 15M खाली futures volume panel; box मध्ये impulse वि. correction चं सरासरी volume (rollover वगळून) आणि area candle चं volume.
5. **Data policy:** 8 Oct 2026 नंतरचे नवे दिवस "ILLUSTRATION" वर्गात: फक्त `annotation` purpose (annotation / vision तपासणी). Golden backtest, IS, VAL आणि research साठी नाहीत. 2024-04 ते 2026-06 चा holdout तसाच, कधीच नाही.
