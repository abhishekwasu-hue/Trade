Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders

# आजपर्यंतच्या कामाचा रिपोर्ट (Abhi साठी)

Abhi च्या आदेशानुसार नवीन job सुरू केला नाही. चालू असलेली सगळी background कामं थांबवली: local full test suite, gallery build,
स्वतंत्र review agent आणि बंद झाल्यानंतरची आठवण. जे झालं आहे ते commit करून PR #367 मध्ये merge साठी ठेवलं आहे.

## 1. Merge झालेले PR (main वर)

| PR | काय | स्थिती |
|---|---|---|
| #359 | Token rejected alert | merged |
| #362 | PA standard live: entry models E1–E4 PAPER मध्ये, Vision human_confirm | merged |
| #363 | CLAUDE.md, REPORT_STANDARD, reader_report validator, threshold guard | merged |
| #364 | RC1–RC6 root-cause fixes, concept-C base fixes, clean charts, max_hits 4 | merged, VPS वर deploy झाला |
| #365 | Trigger: traded_inside (close trade बाजूला बाहेर चालतो) | merged, VPS वर deploy झाला (status ✅ clean) |
| #366 | Memory protocol: CLAUDE.md + docs/owner-orders (README / INBOX / DECISIONS) | merged (CI green) |

## 2. PR #367: merge होणार (CI green झाल्यावर)

### a. Trigger candle स्वतः 15M refined base मध्ये यायला हवी (E1 / E2 / E3 / E4a)
- `Reader.off_base`: candle फक्त मोठ्या area ला लागली तर entry नाही.
- 07 Oct 09:15 ची E2 (MAE 539) आता येत नाही.
- Sweep / fakeout नियम a–e साठी 18 tests आहेत.
- एका close ने refined base पलीकडे गेली तर फक्त E1 संपतो. E2 / E3 / E4 चालू राहतात.

### b. Flip झालेला area पुन्हा तुटला ⇒ DEAD (DECISIONS 27)
- एक area एकदाच flip होतो. Flip नंतर तो पुन्हा तुटला (close + swing पलीकडे), तर तो लगेच DEAD होतो.
- DEAD area कधी armed होत नाही, आणि त्यावर E4b retest येत नाही.
- Setting: `flip_dead_rule = broken_again`. जुनं वाचन (`far_swing`) फक्त what-if म्हणून ठेवलं आहे.
- **Worst loss चं कारण:** 13 Oct 11:45, area 287 ची E4b.
  - 287 resistance होता. 9 Oct 14:15 ला तो वर तुटून support झाला (flip).
  - 13 Oct 09:15 ला तो पुन्हा खाली तुटला (close + swing low 54,708.80).
  - जुन्या code ने तो BROKEN ठेवला आणि त्यावर E4b दिली. परिणाम: MAE 312.

### c. एका जागी एकच E4b (DECISIONS 28)
- एकमेकांवर येणारे broken areas, आणि त्यांच्यावर पडणारी broken line, यांची एक जागा मानली जाते. एका visit मध्ये एकच E4b.
- Edges आणि invalidation प्रत्येक signal चे स्वतःचे राहतात; union band नाही.

### d. 07–21 Oct मध्ये ज्या entries अशा (flip नंतर पुन्हा तुटलेल्या) area वर होत्या

| Entry | Area | Flip | पुन्हा तुटला | परिणाम |
|---|---|---|---|---|
| 07 Oct 13:45 E4b | 282 | 06 Oct 12:30 | 07 Oct 10:00 | next area first, MAE 431 |
| 07 Oct 13:45 E4b | 283 (282 चा duplicate) | 06 Oct 12:30 | 07 Oct 10:00 | next area first, MAE 431 |
| 08 Oct 09:30 E4b | 282 | 06 Oct 12:30 | 07 Oct 10:00 | next area first, MAE 176 |
| 13 Oct 11:45 E4b | 287 | 09 Oct 14:15 | 13 Oct 09:15 | invalidation first, MAE 312 |

E1 / E2 / E3 पैकी कुठलीही entry अशा area वर नव्हती.

### e. आधी / नंतर, 07–21 Oct

Max hits 4, outcome structure ने. कंसात: (पुढचा area आधी / invalidation आधी).

| Model | आधी (35b2b17) | फक्त E4b एका जागी एक | नंतर (#367) |
|---|---|---|---|
| E1 | 4 (1 / 3) | 4 (1 / 3) | 4 (1 / 3) |
| E2 | 2 (2 / 0) | 2 (2 / 0) | 2 (2 / 0) |
| E3 | 5 (4 / 1) | 5 (4 / 1) | 5 (4 / 1) |
| E4a | 0 | 0 | 0 |
| E4b | 7 (5 / 2) | 5 (3 / 2) | 3 (2 / 1) |
| एकूण | 18 (12 / 6) | 16 (10 / 6) | 14 (9 / 5) |
| Σ MFE | 2,946 | 2,410 | 2,037 |
| Σ MAE | 3,438 | 2,830 | 2,087 |
| सर्वात मोठा MAE | 431 | 431 | 329 |

काढलेल्या 4 E4b पैकी 3 "next area first" होत्या, पण त्यांचे MAE मोठे होते. त्यामुळे MFE सुद्धा कमी झाला.

### f. Tests
- **नवे tests:** `tests/test_entry_models_flip_dead.py` मध्ये 11 tests, दोन्ही mirror, खऱ्या K4 reader वर. यातले 10 जुन्या code वर fail होतात (area + line चा test जुन्या code वर तपासलेला नाही).
- **जुने DEAD tests** what-if (`far_swing`) ला pin केले.
- **स्थानिक runs (पास):**
  - flip, death, zone, range-edge, flip_dead: 173 passed;
  - entry-model files: 149 passed.
  - नवे tests सुरू होण्याआधीचा पूर्ण suite: 6008 passed.
- **Local full suite (नव्या code वर)** Abhi च्या आदेशाने मध्येच थांबवला. GitHub CI पूर्ण suite चालवतो, आणि merge फक्त CI green झाल्यावरच.
- **स्वतंत्र review:** refined-base भागाचा review APPROVE झाला. Flip-dead / E4b भागाचा review Abhi च्या आदेशाने थांबवला, म्हणजे तो भाग फक्त self-review वर merge होतो.

## 3. VPS: एकच block (Abhi चालवतील; `--revert` सह)

आत्ता VPS वर `bf98040` (#365) आहे. #367 merge झाल्यावर origin/main वर हा block चालवा:

```
cd /root/Trade && git fetch origin && export PREV_FILE=/root/pa_rb_prev_settings.json ROLLBACK_FILE=/root/pa_rb_rollback.txt && git show origin/main:scripts/deploy_pa_standard_vps.sh > /root/deploy_pa_rb.sh && bash /root/deploy_pa_rb.sh 2>&1 | tee /root/pa_rb_deploy.log
```

परत आधीसारखं करायचं (फक्त हा deploy उलटा होतो):

```
export PREV_FILE=/root/pa_rb_prev_settings.json ROLLBACK_FILE=/root/pa_rb_rollback.txt && bash /root/deploy_pa_rb.sh --revert
```

- Block शेवटी status छापतो. ✅ clean दिसायला हवं.
- Market चालू असताना चालवला तर vision / position / streamlit services एक-दोन मिनिटं restart होतील.
- फक्त PAPER. LIVE ला हात नाही.

## 4. Data आणि galleries (private trade-data)
- **07–21 Oct, #367 आधीचे:** gallery `review/replay_banknifty_6m/35b2b17/groups/2026-10-07_2026-10-21/`.
- **#367 नंतरची gallery:** बनवली नाही, Abhi च्या आदेशाने थांबवली. आकडे वरच्या टेबलमध्ये आहेत.
- **6 महिन्यांच्या reading galleries:** 12 batches (`review/replay_banknifty_6m/reading/bf98040/`). यात "FUT volume missing" असं चिन्हांकित आहे.
- **30 Sep आधीचा BANKNIFTY FUT volume:** उपलब्ध नाही. Upstox expired-instruments साठी Plus plan लागतो (पैसे लागतात). Abhi ची परवानगी हवी.

## 5. उघडी कामं (OPEN_QUESTIONS; आत्ता काम नाही)
- Vision approval chart चे band labels (`band_flip_facts`) अजून जुन्या DEAD नियमाने येतात. याचा फक्त display वर परिणाम आहे, निर्णयावर नाही.
- RC2: refined base नसताना मोठी move सुटली (26 May).
- E4a 6 महिन्यांत एकदाही fire झाला नाही.
- Channel parallel वरच्या E4b ने सर्वात मोठे loss दिले.
- 9–11 Jun: वर जाणाऱ्या 15M विरुद्ध 6 stops.
- Reading-only validator branch: `claude/reading-only-reports`, PR बाकी.
- जुने PR: #358, #311, #299. यांचा निर्णय बाकी.
