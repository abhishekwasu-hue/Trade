# G-MAP1: टप्पा A अहवाल (Abhi साठी थांबा-बिंदू)

**तारीख:** 2026-10-08/09 (रात्र). **स्थिती:** टप्पा A पूर्ण. टप्पा B, merge आणि VPS वर काहीही बदल नाही; LIVE ला हात लावलेला नाही.

**या अहवालाबद्दल:**
- प्रत्येक विभागाचा तपशील त्याच्या स्वतःच्या अहवालात आहे (folder `docs/reports/situation_map/`). प्रत्येक row चा JSON data private
  trade-data repo मध्ये आहे (`research/situation_map/`).
- IS = 2015–2021. VAL आणि holdout अजून वापरलेले नाहीत.
- Jul–Oct 2026 चा data contaminated आहे, त्यामुळे तो फक्त उदाहरण म्हणून वापरला आहे.
- कोणताही threshold किंवा मूल्य निवडलेलं नाही. फक्त Abhi ने रात्री 23:48 ला सांगितलेले settings लागू केले (खाली §0).

---

## 0. Abhi च्या Sep–Oct review नंतर काय केलं

| # | Abhi ने काय सांगितलं | काय झालं |
|---|---|---|
| 1 | Target degree चुकतो; impulse_end बरोबर तुलना करा | `A6_sepoct_targets.md`: 11 signals वर next_opposite_area −0.29R, impulse_end +2.24R (R:R फिल्टर बंद ठेवून). **सावधानता:** impulse_end सुद्धा 25 आणि 28 Sep ला लहान degree चा impulse निवडतो (R:R 0.48 आणि 0.13). Degree-सुसंगत व्याख्या टप्पा B मध्ये. |
| 2 | g9_tier रिकामा ठेवा; full / half असता तर काय | Shadow निकाल `A6` मध्ये. 7 Oct ला code चा label G9 होता, तर Abhi चा golden G5 / S1 (C-end) आहे. हा फरक नोंदवला. |
| 3 | 1H / Daily count gray का येतो | `A4b_gray.md` (खाली §4) |
| 4 | 30 Sep 10:30 = Gray-2 test case | टप्पा B च्या test यादीत टाकलं |
| 5 | Chart labels एकमेकांवर येतात | उजवीकडचे labels आता वर-खाली सरकवले जातात (stagger), हललेल्या label पासून खऱ्या भावापर्यंत बारीक रेषा असते. फक्त entry-area आणि ENTRY ठळक दिसतात. Tests लिहिले. |
| 6 | 22,217 चा low 1 Oct चा आहे | बरोबर: low 1 Oct 14:05 चा आहे; D3 वर तो 5 Oct 13:40 ला confirm झाला, म्हणून गोंधळ झाला. नकाशा KB मध्ये जाताना (टप्पा B) तारीख दुरुस्त करेन. |
| 23:48 | PAPER profile: g9_tier = full, target_mode = impulse_end | `paper_core` profile store मध्ये नसेल तर हीच मूल्यं आपोआप घेतली जातात. g9_tier ला full आणि half पर्याय जोडले. LIVE किंवा इतर कोणत्याही profile ला default नाही. Instrument, strike आणि lots dashboard वरच निवडायचे. VPS वर हे merge आणि VPS block नंतरच लागू होईल. |
| 23:48 | 1 Sep – 8 Oct पुन्हा चालवा, जुन्याशी तुलना | `SepOct_run2_vs_run1.md`: run1 मध्ये 0 trades; run2 मध्ये 2 trades: 21 Sep SL −1R, 7 Oct target +4.33R, एकूण +3.33R. trade झालेल्यांचा सरासरी R:R 5.19. Signals दोन्हीकडे 11, तेच. |

---

## 1. A1: Constants register आणि "अंदाज" आकड्यांची sensitivity

**Register** (`A1_constants_register.md`) मध्ये आकडे वर्गानुसार:

| वर्ग | संख्या |
|---|---|
| अंदाज | 122 |
| shadow | 97 |
| config | 16 |
| research | 14 |
| Abhi | 11 |
| व्याख्या | 5 |
| रद्द | 3 |

याशिवाय code मध्ये थेट लिहिलेले (inline) आकडे 113 आहेत. Real break ची व्याख्या एकच आहे: `elliott/breaks.py`, आणि 3-close चा नियम Abhi चा.

⚠ **टप्पा B साठी नोंद:** `levels_v2` मधला `accept_closes` आणि Simple Core मधले area acceptance bars `breaks.time_accepted` मध्ये एकत्र करायचे.

**Sensitivity** (`A1_sensitivity.md`; IS मधले random 40 दिवस; hindsight फक्त गटांसाठी, target 3R):
- आत्ताच्या मूल्यांनी 17 signals आले: 3 target, 12 SL, 2 TIME. सरासरी −0.24R.
- **फार संवेदनशील आकडे** (मूल्य बदललं की signals चा संच खूप बदलतो):
  - `commitment_vs_pause` 2.0 केला तर signals 9 होतात, जुन्या संचाशी साम्य (Jaccard) 0.37.
  - `commit_strength_min_mr` 1.5 केला तर signals 12 होतात, साम्य 0.45.
- **स्थिर आकडे** (साम्य 0.78–0.94): `area_tol_mr`, `pause_body_max`, `commit_close_max`. `pause_range_max_mr` मध्यम (साम्य 0.67–0.68).
- n खूप लहान आहे, त्यामुळे निकालातले फरक noise च्या आतच आहेत.

**Abhi चा निर्णय हवा:**
1. संवेदनशील आकडे "Abhi" वर्गात न्यायचे की impulse आकाराशी सापेक्ष करायचे?
2. `commitment_vs_pause` (22 Sep ला याच नियमाने signal अडवला; §3 पाहा) पुढे कसा ठेवायचा?

## 2. A2: Counter-moves मध्ये continuation आणि reversal वेगळे करणारे पुरावे

IS मधले counter-moves (`A2_counter_moves.md`): trend चालू राहिला 316, reversal झालं 75, अनिर्णित 25.

AUC म्हणजे एखादा पुरावा दोन गट किती चांगला वेगळे करतो: 0.5 म्हणजे काहीच भेद नाही, 0.5 पासून जितका दूर तितका भेद मजबूत.

| पुरावा | AUC (reversal > continuation) | माझं वाचन |
|---|---|---|
| खोली (depth) | **0.71** | सगळ्यात मजबूत. पण अंशतः साहजिक आहे: खोल counter-move origin च्या जवळ असतो. |
| displacement | **0.59** | मध्यम |
| legs (3 वि. 5) | 0.55 | कमकुवत |
| er, overlap, overlap percentile, वेग / impulse | 0.45–0.53 | भेद जवळजवळ नाही |
| impulse ची 1H रचना तुटली | प्रमाण 0.25 वि. 0.12 | n फार कमी (24 / 4) |

IS मध्ये futures volume data नाही, म्हणून तो पुरावा मोजता आला नाही.

**Abhi चा निर्णय हवा:** कोणते पुरावे "मजबूत" आणि कोणते "कमकुवत" याची अंतिम यादी गोठवा. त्यानंतर VAL वर एकदाच तीच तुलना होईल.

## 3. A3: चार केसेसचे MAP CHECK charts (Abhi ✔ / ✘ बाकी)

Charts trade-data `review/map/a3` मध्ये आहेत. VPS वर `send_review_to_telegram.py --run review/map/a3` ने Telegram वर येतील.

| केस | नकाशाचं उत्तर (decision bar पर्यंतच्या data वरून) |
|---|---|
| 22 Sep 15:00 | Wave (4) चे A-B-C decision bar ला पूर्ण दिसत होते, त्यामुळे Gray-2 नाही आणि G9 bear शक्य होता. Signal **निर्णय थरात** अडला: 10:15 ची commitment candle (34.6) pause सरासरीच्या (30.6) 1.5 पटीपेक्षा लहान होती. |
| 28 Sep 14:15 | Flag 11 candles चा, त्यामुळे G8 नाही (2–6 candles ची व्याख्या तशीच ठेवली). With-trend legs लहान होत नव्हते, त्यामुळे S8 नाही. S1 म्हणून तपासलं (तुटलेला swing 23,021 / displacement base): **12:45 ला S1 bear signal**, entry 22,830. |
| 16 Feb 2018 09:30 | Origin 15 Feb ला real-broken झाला होता, पण 09:30 पर्यंत break अपयशी ठरला. त्यामुळे S1 (जुना downtrend): area आणि commitment असेल तर bear setup शक्य. |
| 15 Nov 2021 13:00 | Retest ची रचना corrective नव्हती, पण rejection होतं. त्यामुळे G4 नाही. |

## 4. A4: PARENT_CONFLICT, आणि A4b: counts gray का येतात

**A4** (`A4_parent_conflict.md`; दिवसाच्या close ला; पालक degree D2 चा vote):

| | IS | Jul–Oct 2026 (फक्त उदाहरण) |
|---|---|---|
| counts चं मत नाही (gray) | 87% दिवस | 78% दिवस |
| दोन्हींचं मत असलेल्या दिवसांत conflict | 22 / 44 (50%) | 8 / 13 (62%) |

**A4b** (`A4b_gray.md`; 1H bar close ला; IS मधले 606 नमुने):
- **महत्त्वाचं:** सध्याच्या `auto_by_bars` mode मध्ये D0 ते D3 हे चारही degrees **5m pivots वरूनच** बनतात. Degree फक्त swing च्या आकाराने वेगळी होते, त्यामुळे वेगळा "1H" किंवा "Daily" count अस्तित्वातच नाही.
- प्रत्येक degree चा एक leg साधारण इतक्या वेळाचा असतो, आणि इतक्या वेळा gray:

  | degree | leg (तास) | gray |
  |---|---|---|
  | D0 | 0.3 | 91% |
  | D1 | 1.2 | 87% |
  | D2 | 4.1 | 86% |
  | D3 | 12.8 | 63% |

- Gray ची कारणं:
  - Data / history ची कमतरता नाही: 130 आणि 400 दिवसांच्या history ने आकडे अगदी तेच आले.
  - नियमांमुळे सगळे counts बाद होणं नाही: 0%.
  - **"पुढची wave corrective" (vote = 0):** D3 च्या gray पैकी 86%, D2 च्या 62%. Count असतो, पण vote फक्त पुढच्या motive wave ची दिशा मोजतो, त्यामुळे correction च्या मध्यात तो gray येतो.
  - **मोठ्या degree शी जुळत नाही** (strict cross-degree नियम): D0 च्या gray पैकी 75%, D1 च्या 62%.
- तुलना म्हणून खरे 1h / 1d frames (fixed mode) वापरले: IS मध्ये चारही degrees **100% gray**.

**प्रस्ताव (Abhi चा निर्णय हवा):**
1. नकाशा P1 मध्ये पालक दिशा म्हणजे "primary count मधल्या motive sequence ची दिशा". त्यासाठी vote ऐवजी preferred count ची चालू दिशा वापरायची का?
2. PARENT_CONFLICT वर gate लावायचा, की फक्त नोंद / size कमी करायची?

## 5. A5: Range च्या कडांचे tests (G10)

IS मध्ये 496 tests मिळाले (`A5_range_edges.md`). "कड तुटली" म्हणजे `breaks.py` नुसार real break.

| प्रकार | n | आधी विरुद्ध कडेपर्यंत गेला | आधी कड तुटली | R:R ≥ 3 शक्य |
|---|---|---|---|---|
| sweep + reclaim | 162 | 49 (30%) | 113 | 99 |
| sweep शिवाय rejection | 258 | 74 (29%) | 183 | 204 |
| real break | 76 | — | — | — |

- पालक trend च्या दिशेची कड आणि विरुद्ध कड यांच्यात फार फरक नाही: विरुद्ध कडेपर्यंत अनुक्रमे 27% आणि 31% वेळा गेला.
- शुद्ध S9 (पालक trend नाही) गटात फक्त 6 tests आले.

**Abhi चा निर्णय हवा:** G10 चं PAPER मधलं वर्तन. पर्याय: फक्त नोंद / लहान size / बंद.

## 6. Abhi चे बाकी निर्णय (prompt §G-MAP1)

1. **`gray_size`:** default नाही. Abhi सांगेपर्यंत `reduce` = `block`.
2. **`eod_signal_carry`:** नकाशातला प्रस्ताव असा: 15:15 चा signal दुसऱ्या दिवशी नव्याने वाचायचा.
3. **7 Oct चा count:**
   - Code ने 12:15 पर्यंतच्या bars वरून G9 म्हटलं: wave 3 चं टोक 22,217 (1 Oct), नंतरची तेजी wave 4, retrace 41%.
   - Abhi चा golden: G5 / S1 (C-end).
   - तुम्हाला कोणता count योग्य वाटतो ते सांगा. ते टप्पा B मध्ये golden test होईल.
   - **Code च्या आतच दोन वाचनं:** 15M chart वरचं market_state चं ABC असं वाचतं: impulse 22,809 वरून 22,217, मग A 22,620, B 22,400,
     C सुमारे 22,730 (6 Oct). म्हणजे C-end, आणि हे Abhi च्या golden शी जुळतं. पण `simple_core/waves.py` तोच भाग "wave 4 end ⇒ G9"
     म्हणतो. टप्पा B मध्ये ही दोन वाचनं एकाच count मधून यायला हवीत.
4. **नकाशात एखादी परिस्थिती सुटली आहे का (I9.8):** Sep–Oct review मधून दोन गोष्टी दिसल्या:
   - target degree (§0.1);
   - G9 विरुद्ध C-end मधला गोंधळ (§6.3).
5. **Evening Plan च्या watch_areas बाहेर दिवसा तयार होणारे areas (§B5):** कसं वागवायचं ते ठरवा.

## 7. टप्पा B ची यादी (G-MAP1 नंतरच)

- Situation map (S1–S12, P1–P8, Gray-1 / Gray-2) code मध्ये; POSSIBLE_REVERSAL काढून टाकणं.
- `accept_bars` आणि levels_v2 चा "N closes" नियम `breaks.py` मध्ये एकत्र करणं (3 closes).
- **next_opposite_area ची degree दुरुस्ती:** चालू correction च्या आतले areas target नाहीत; target impulse end वर किंवा त्यापलीकडे (नकाशा P1). हा पर्याय राहतो, पण default नाही.
- Gray-2 test cases: 30 Sep 10:30 (grade A, पण rally चालू आणि ABC अपूर्ण), 22 Sep.
- Golden cases: 28 Sep (provisional; S1 म्हणून), 7 Oct (Abhi चा count).
- नकाशातली तारीख दुरुस्ती: 22,217 चा low 1 Oct चा.
- `A4b` च्या निर्णयानुसार पालक दिशा.
- ⚠ **3-close नियम आणि elliott count engine:** WIP मध्ये `elliott/settings.break_accept_closes = 3` default आहे. त्यामुळे count invalidation थोडं
  बदलतं. `tests/test_elliott_c1.py::test_defaults_off_byte_identical_to_e2_snapshot` fail होतो: 2019 H1 मध्ये signals तंतोतंत तेच,
  पण gray / no_count मोजणी 1 ने वेगळी. Main वर हा test pass होतो.
  **Abhi चा निर्णय हवा:** 3-close नियम elliott counts ला पण लागू करायचा (मग snapshot नव्याने घ्यायचा), की फक्त levels_v2 आणि
  Simple Core च्या acceptance ला?
- VAL तुलना (A2 आणि A5): एकदाच.
