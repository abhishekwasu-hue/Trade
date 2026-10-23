# थर v2.2 — OPEN_QUESTIONS (default घेऊन काम चालू; Abhi उत्तर देतील तेव्हा बदल batch PR ने)

## Still open (as of 2026-10-21)

Only what is really open today. Every older section below stays as history; each one now carries a one-line **closed / status**
pointer under its heading (answered by …, superseded by …, or "listed in Still open"). Abhi's method
(`docs/knowledge/CHART_READER_METHOD.md`) replaced the piece-by-piece answers — see the section "Abhi's method … all earlier questions
resolved" near the end.

**For Abhi (an answer or a ✅ is needed):**

| id | Question (one line) | Current default | Where |
|---|---|---|---|
| R-BN-1 … R-BN-5 | BANKNIFTY replay: does Abhi agree with "no handover" (E29 / E31), see a handover on any G3 visit (E14, E17, E20, E21, E24, E29), and is E26 / M06 only a note? R-BN-5 = data note (re-run when more history lands) | no change to the reader | trade-data `review/replay_banknifty_6m/04a8b40/ABHI_QUESTIONS_MR.md` (simple Marathi, charts side by side); last section of this file |
| L5 / L6a ✅ | Layer 5 (RSI divergence inside the move into the zone, L5-a) and layer 6a (verdict: required set ⇒ enter; A = + ≥ 1 confirming, B = required only) — ✅ / ✏️ | as merged; not stable until ✅ | trade-data `review/layer5_6a_report/2b43f17/README.md`; `docs/reader/STABLE.md` |
| R0-3 | Golden Vision V4 expectations (12 Oct, 29 Sep): ✅ the drafts | drafts; every V4 result PROVISIONAL; live V4 off (R0-8) | trade-data `golden_v4/cases.json`; section "Chart Reader R0" |
| R1a-13 | Bands on the Vision approval chart (`vision_chart_bands`) — turn on, and change the Vision legend with it? | OFF (image unchanged) | section "R1 (a)" |
| BW-1 / C-18 | Keep the 150-pt "merged band — check" alert now that bands are never merged (Z-1u)? | 150, display only | decided with layer 6 (output) |

**Open work — no answer needed now (done in the named layer):**

| id | What | Current default | Where |
|---|---|---|---|
| L3-c3 · L3-n · Z-1b · R1b-1, R1b-2, R1b-4 … R1b-7 | Facts dossier: its own visit finder (`touch_window_bars`, PENDING in the guard), its commitment read, the shared band check's "flipped", owner disagreements | as coded | layer 6 (output) |
| CD1 … CD14-E · VP1 … VP6 · R1a-1 … R1a-12 · Q48 | Chart / pane display defaults (Daily structure chart, volume panes, chart line / band checks, 1H / 15M review charts) | as coded | layer 6 (output) |
| C-22 | Retire the old numeric rsi2 `RSI` class (only the facts dossier still uses it) | kept | layer 5 / 6 clean-up |
| RSI-4 | The review listener does not record ✏️ (a ✘ + reason is recorded) | as is | tooling |

**Standing operational defaults** (no answer recorded; they stay unless Abhi objects): TG1–TG7 (Telegram), DP1–DP4 (data /
pre-open), OB2 (an engine setup stays pending for 30 min), OB3 (auto-trader PAPER crons commented in one-bot mode), Z-1l (SENSEX FUT
missing ⇒ no Telegram line; SENSEX is not live), B3 note (`last_sl_hit_time` is never written, so the optional post-SL cooldown never
bites).

**Answered today:** L1-c — Abhi: keep N = 2 as the provisional value; he may change it later from the dashboard (setting added by the
live-switches track).

**Dormant** (not on the live path; reopen only if that part comes back): level bots (LB*, RF-1, RR6, TF6 — rebuilt in ATP on the
ported reader, off in one-bot mode), reader2 / Chart Reader v2 (CR-Q*, research only), simple_core (Q41, RR5, research / backtest
only), MCX confirmation (LB12–LB17).

---

> **closed (2026-10-21):** Q15–Q17, Q22–Q40, Q44, Q49, Q55 answered (sections below; Q7 changed by Q33). The rest are superseded by
> Abhi's method (last sections): Q1 / Q5 / Q8 / Q9 / Q42 / Q43 / Q45 / Q47 / Q50–Q54 → layer 1 ✅ (L1-a, L1-b; C-2 / C-13); Q2 → TL1;
> Q3 → C-4 / L2-a; Q4 / Q19 → Z-1u (each zone from its own base, never merged); Q6 → C-21; Q10 / Q11 → L6-a (no scores); Q12 → C-15;
> Q13 / Q18 → C-5 (the visit); Q14 / Q21 → EC1 (no engine R:R / entry / SL / target); Q20 → L4-a … L4-g; Q46 → B1 (wave counts are
> context only); Q41 → dormant (simple_core G8, research only; the golden xfail stays); Q48 → layer 6 (Still open). Later method
> rows also replace some batch answers (e.g. Q24 / Q30 forms → L3-f / L3-m; Q40 distance filter → C-14).

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| Q1 | ① HH / HL: "जवळपास समान" (RANGE tol) च्या आत असलेला H2 > H1 HH मानायचा का? | नाही — HH / HL साठी tol पलीकडे हवं (`range_eq_sigma_d` × σ_D); tol च्या आत ⇒ RANGE उमेदवार | साधं `>` |
| Q2 | ② मृत्यू: "level पलीकडचा structural swing" — कोणती बाजू? | ~~मूळ भूमिकेची~~ **TL1 (Abhi 2026-10-12) ने बदललं: चालू भूमिकेची बाजू** (`level_death_side` = "role"); जुना: **मूळ भूमिकेची** (support ⇒ खालचा जवळचा D2 L; resistance ⇒ वरचा D2 H), flip झाल्यानंतरही | चालू भूमिकेची बाजू (flipped resistance ⇒ वरचा swing) |
| Q3 | ② flip ("real break") किती closes? | **spec §5.4 / §7.7 ने ठरलं:** पलीकडे सलग 3 closes (acceptance, `accept_closes`); 1–2 closes किंवा wick आणि परत ⇒ sweep ★ | — |
| Q4 | ② (b) BOS base चा पट्टा | ↑ [low, open] / ↓ [open, high] (base चा उगम-भाग) + किमान रुंदी | पूर्ण candle [low, high] |
| Q5 | ① नवा trend: नवा HL आणि HH दोन्ही शेवटच्या break नंतरचे हवेत का? | हो (दोन्ही pivots break bar नंतरचे) | फक्त दुसरा (नंतरचा) pivot नवा |
| Q6 | ② (a) "1H trend-degree swing" | थर 1 swings2 D2 (15M bars वर, θ₂ = 6σ — v2.1 मधली 1H degree) | खऱ्या 1H candles वर स्वतंत्र pivots |
| Q7 | BANKNIFTY Daily (fetched D 10y) | ~~engine मध्ये फक्त sealed holdout नंतरचे rows~~ **Q33 (Abhi) ने बदललं:** engine पूर्ण history वर (warm-up); NIFTY holdout तारखांचा output नाही | — |
| Q8 | ① intraday: आजचा trend कधी बदलतो? | आजच्या Daily close नंतरच (शेवटच्या 15M bar ला); दिवसभर कालच्या close ची state | — |
| Q9 | ② RANGE trade-बाजू | खालचा जवळचा support + वरचा जवळचा resistance (प्रत्येकी 1) | range पट्ट्याच्या कडांवरचेच levels |
| Q10 | §2 "✅ फक्त ①②③④⑥ पूर्ण" वि. §6.2 "कठोर नियम फक्त H1–H3" | H1–H3 + ⑥ (entry trigger) कठोर; ④ आणि बाकी पुरावे ⇒ conviction; ✅ = conviction A, 🟡 = B; §5.3 range अवस्था = gate | ④ सुद्धा कठोर |
| Q11 | §6 पुराव्यांचं वजन / conviction सीमा | `evidence_weights` (trap / power shift 1.5; star / दुसरा प्रयत्न / commit 1; बाकी 0.5; विरुद्ध bodies −1, चौथा प्रयत्न −1.5); A ≥ 0.6, B ≥ 0.4, weak ≥ 0.2 — Abhi E1–E4 वरून ठरवायचं | — |
| Q12 | §5.1 "पाय" मोजणी | K मधले confirmed D1 counter swings + चालू पाय (1 = H1 / L1 ⇒ कमाल B, ≥ 2 ⇒ A शक्य, > 3 ⇒ trade नाही) | D0 swings |
| Q13 | ③ "उलट बाजूने आली" | आधीचा 15M close level च्या trade-बाजूला (bear call: पट्ट्याखाली/आत, वरून नाही); open / close पलीकडे ⇒ breakout ✘ | पहिल्या स्पर्शाची दिशा |
| Q14 | ⑦ target | I_end आणि विरुद्ध बाजूचा जवळचा जिवंत level — जो जवळ | फक्त I_end |
| Q15 | ~~Daily lag~~ **निकाली (Abhi FINAL)** | degree-aware Dow: trend = शेवटचा impulse leg, protected = त्याचा origin; correction (zigzag / flat / …) त्याच degree ची, minor LH तुटला तरी trend नाही; origin close-break + उलट impulse ⇒ flip; नवा LL (close) ⇒ protected = correction टोक; Weekly पालक; maturity पुरावा; elliott count सल्ला caption मध्ये. `daily_trend_mode` = impulse (minor = what-if) | — |
| Q16 | ~~commitment~~ **निकाली (Abhi)** | reversal candle at level: engulf / star / inside_break / doji_confirm / tweezer / pin / strong_close (≤ 2 merged); किमान: close मागच्या close पलीकडे (`commit_beyond` = close); grade A = extreme पलीकडे किंवा engulf, B = wick नकार; pullback-दिशेची / doji / inside ⇒ एक candle वाट; `commitment_form` output | — |
| Q17 | v2.2 charts साठी `matplotlib` — `requirements.txt` मध्ये नाही (sandbox मध्ये वेगळं install) | engine (decision3 core) ला matplotlib लागत नाही; फक्त `decision3/charts.py` / `scripts/v22_check.py` ला. **बदल:** पायरी D चे tests charts बनवतात ⇒ CI ला लागतं ⇒ `matplotlib~=3.11` requirements मध्ये जोडलं (5a499f1, draft PR); VPS वर फक्त Abhi च्या deploy ने | **निकाली (Abhi): requirements मध्ये ठेवा** |
| Q18 | ③ "level मध्ये / लगत" (⑥, §6.2 H2 "वर / जवळ"): स्पर्श फक्त entry bar वर का? | शेवटच्या `touch_window_bars` = 3 bars (commitment ≤ 2 merged + आधीचा) पैकी एकाने पट्ट्याला स्पर्श; breakout / gap तपासणी bar t वर; "उलट बाजूने" = पहिल्या स्पर्शाआधीचा close (independent review नंतर बदल — run1 मध्ये entry bar वरच स्पर्श लागत होता) | फक्त entry bar (1) |
| Q19 | ② merge: नवा support जिवंत resistance ला overlap झाला तर? | जुन्या level मध्ये merge, जुनी भूमिका (role) कायम; जन्म-कारण जोडलं जातं | फक्त समान भूमिकेचे merge; उलट भूमिका ⇒ वेगळा level |
| Q20 | ⑤ "K ची आतली तिरकी रेघ" — कोणते बिंदू? | I_end + K मधले confirmed D1 counter pivots (DOWN ⇒ lows); शेवटची K-दिशेने सरकलेली जोडी; स्पर्श σ_1H × 0.15; break = रेघ confirm झाल्यानंतरचा trend-दिशेचा close. पुरावा `tl_break` (वजन 1.0) फक्त तुटली तर True; रेघ अखंड / नाही ⇒ NA (spec "(असल्यास) … तुटली ⇒ grade +" ⇒ grade वजा नाही); दोन anchors = 2 स्पर्श | D0 pivots; किंवा फक्त K मधले pivots (I_end शिवाय) |
| Q21 | "B1/B2 तसेच" (spec §2 / C) — B1 / B2 म्हणजे काय? repo / आधीच्या spec मध्ये व्याख्या सापडली नाही | §5.2 चे दोन entry trigger: **B1** = commitment close वर (default), **B2** = signal-bar extreme च्या 1 tick (`entry_tick` 0.05) पलीकडे break; SL / target तेच, B2 चा R:R वेगळा (< 3 ⇒ B2 नाही). Caption + debug मध्ये दोन्ही | Abhi ची स्वतःची व्याख्या |

| Q22 | Q15 "त्याच degree ची correction" — impulse आतल्या minor bounces पासून वेगळी कशी? | correction = impulse टोकानंतरचा confirmed उलट swing ज्याचा आकार ≥ `corr_degree_frac` (0.5) × मागच्या same-degree correction चा आकार (सुरुवातीला (2) चा आकार) | 0.382 / 0.618; किंवा वेळ (दिवस) प्रमाण |
| Q23 | origin close ने तुटला पण उलट impulse नाही — conviction? | cap नाही; फक्त नोंद ("correction चालू") — spec: state = DOWN, correction in progress (आधी weak cap होता ⇒ E-days दडपले जात होते, काढला) | कमाल B |
| Q24 | §5.3 range gate वि. Q16 doji / inside forms (form स्वतःच overlap + doji दाखवतो) | commitment candle मागच्या `range_state_n` candles च्या पट्ट्याबाहेर trade-दिशेने close ⇒ range संपली (gate लागू नाही); पट्ट्याआतच close ⇒ gate | form असल्यास §5.3 नेहमी माफ |
| Q25 | Q16 "doji / inside ⇒ एक candle वाट" — पुष्टीची candle ③ च्या 3-bar स्पर्श खिडकीबाहेर पडते | t − 1 ला ③ ✔ + ⑥ वाट (doji / inside) ⇒ t ला ③ वारसा (breakout तपासणी t वर) | खिडकी 4 bars |
| Q26 | Q16 grade B (wick-only नकार) चा conviction वर परिणाम? | grade B ⇒ conviction कमाल B (🟡). `commit_strong` पुरावा grade पासून वेगळा — signal-bar आकार (big body + big range, आधीसारखा; review 🟡3) | grade A ⇒ commit_strong |
| Q27 | Q15 नंतर RANGE कधी? (impulse mode मध्ये trend एकदा लागला की RANGE ला पोचत नाही — फक्त NEUTRAL पासून) | RANGE फक्त data सुरुवातीला / NEUTRAL मधून; trend असताना बाजूची हालचाल = correction (flat / triangle) — Q15 "correction in progress" | origin_broken + दोन समान H / L ⇒ RANGE |
| Q28 | data (A) च्या सुरुवातीपासून असेल तर (B) zigzag (HL + HH) = UP impulse म्हणून वाचला जातो ⇒ (C) चा (3) सुरू झाल्यावरही (B) चा HL close ने तुटेपर्यंत UP correction (Q15 नियम: origin close-break शिवाय trend संपत नाही). NIFTY window (holdout नंतर) (B) च्या टोकाजवळ सुरू होतो ⇒ E-days वर परिणाम नाही | नियम जसाच (structure ने impulse; leg-nature वर्गीकरण नाही) | legs2 / patterns2 ने establishing leg 3-wave (corrective) असेल तर trend लावू नये ⇒ (3) पासूनच DOWN |
| Q29 | origin तुटल्यावर उलट रचना जुन्या impulse टोकापासूनच आधी झाली असेल (LH + मधल्या L खाली close) — कधी flip? (review 🔴1: degree data-सुरुवातीवर अवलंबून होती) | त्याच दिवशी flip; origin = impulse टोकानंतरचा सर्वात उंच LH (UP ⇒ सर्वात खालचा HL); नसेल तर break नंतरचा HL / LH + टोकापलीकडे close | फक्त break नंतरची रचना |
| Q30 | Q16 "close मागच्या candle च्या close / extreme पलीकडे" — 2-candle (merged) forms (doji_confirm, inside_break, star, tweezer, strong_close_2) मध्ये "मागची" कोणती? (review: t − 1 pattern चाच भाग ⇒ grade A आपोआप) | merged = एक candle ⇒ "मागची" = pattern आधीची candle t − 2 (त्याच दिवसाची असेल तर; नसेल ⇒ t − 1). Engulf / pin / strong_close (1 candle) ⇒ t − 1. Q16 आधीचा code पण असाच (i0 − 1) | नेहमी t − 1 (doji / inside नंतरची पुष्टी जवळपास नेहमी A) |
| Q31 | Daily swing view: NIFTY चा "शेवटची 2 वर्षं" chart ⇒ 2024-04 … 2026-06 sealed holdout rows लागतात | NIFTY साठी holdout rows कधीच नाहीत (script drop करतो; sandbox मध्ये तो data नाहीच) ⇒ NIFTY chart फक्त holdout नंतरच्या Daily वर (Jul 2026 पासून). आधी फक्त BANKNIFTY (Abhi: "Initially only banknifty chart") | Abhi स्पष्टपणे holdout display-only उघडेल (VPS वर, tuning नाही) |
| Q32 | Daily legs impulse / corrective — "legs2 / patterns2 classification" | legs2 / patterns2 intraday swings2 (15M degrees) वर चालतात, Daily pivots वर नाहीत ⇒ Daily legs चं वर्गीकरण Q15 fold वरून (leg संपताना trend दिशेचा ⇒ impulse, उलट ⇒ corrective) | legs2 ला Daily frame साठी adapter (वेगळं काम) |
| Q33 | Daily swing view मध्ये engine पूर्ण history वर (Abhi) वि. v22_check मध्ये BANKNIFTY Daily फक्त Jul 2026 पासून (Q7) — degree वेगळी येते (BANKNIFTY आज: full history ⇒ Q15 UP correction (6); Jul-पासून ⇒ DOWN impulse (5)) | View: full history (Abhi चा नियम); engine run (v22_check) Q7 तसाच — फरक caption / report मध्ये नोंद | engine run पण full history वर (BANKNIFTY ला holdout नाही) |
| Q34 | Q15 wave क्रमांक (5) नंतरही वाढत राहतो ((6) … (36)) — mechanical count, Elliott degree नाही | तसाच (फक्त दाखवतो); maturity (5)+ ला लागते | (5) नंतर मोठ्या degree ला नवा count / वर्तुळ ((1)…(5)) |
| Q35 | Q22: "आतले pullbacks" कोणते, आणि impulse leg अजून सरळ (आतला pullback नाही) व मागच्या impulse leg मध्येही नाही ⇒ पहिला उलट swing कोणत्या degree चा? | आतले = एक degree खालचे Daily pivots (N − 1 = 1); संदर्भ = चालू leg चा किंवा मागच्या impulse leg चा सर्वात मोठा (जो मोठा); संदर्भ 0 ⇒ आतलाच (संदर्भ 0 ⇒ correction नाही); तो पुढच्या swings चा संदर्भ बनतो. शब्दशः नियमाने प्रत्येक पहिला bounce correction ठरत होता ⇒ wave count फुगत होता (FLAT fixture (3) मध्ये L10) | पहिला swing नेहमी same-degree |
| Q36 | Q28 gate (impulse-स्वभावाचा पाय) फक्त NEUTRAL / RANGE मधून trend सुरुवातीला की origin_broken नंतरच्या flip ला पण? | फक्त सुरुवातीला (Abhi: "first leg after the data start"); flip (उलट impulse) ला नाही — origin_broken मध्ये Q23 कमाल B आधीच | flip ला पण gate |
| Q37 | Q28: C माहीत नसेल (baseline < 10 आधीचे Daily legs — warm-up; किंवा ≤ 2-bar पाय) तर? | फक्त रचना (आतली रचना एक degree खालच्या pivots वरून): (1) किंवा (3) corrective (3-wave) ⇒ trend नाही; नाहीतर परवानगी. C असेल तर (1) किंवा (3) impulse हवा (5-wave impulse किंवा C = IMP) | warm-up मध्ये trend नाहीच |
| Q38 | Q27 RANGE: कोणते H / L, आणि ② ला कडा कशा? | impulse टोकानंतरचे शेवटचे दोन H आणि दोन L (tol = `range_eq_sigma_d` × σ_D); ② मध्ये support पट्ट्याच्या खालच्या अर्ध्यात, resistance वरच्या अर्ध्यात (मध्य = पट्ट्याचा मध्य) | कडेपासून σ अंतर |
| Q39 | Q33: NIFTY चा protected / origin pivot holdout काळातला असेल तर output मध्ये? | किंमत दाखवतो (engine state), तारीख "before window"; caption मध्ये "since before the shown window" | किंमतही लपवा |
| Q40 | Q33: पूर्ण Daily history ⇒ जुने (वर्षांपूर्वीचे / NIFTY holdout) Daily pivots 1H levels म्हणून जन्मावेत का? | नाही — 15M window आधी बनलेले Daily pivots level म्हणून जन्मत नाहीत (त्यांचे आधीचे breaks / flips माहीत नाहीत; holdout काळ output मध्ये नाही). Daily trend / protected पूर्ण history वरूनच | जुने Daily pivots सुद्धा levels |
| Q41 | #284 (28 Sep 14:15 bear): 11-candle G8 flag आता चालतो (`g8_max_bars` 11), पण अजून Gray-2 IMPULSE_NA — flag चा low (impulse टोक) trade-degree confirmed pivot नाही. "Flag ने impulse टोक confirm केलं" असा नियम लावला तर 28 Sep जुळतं, पण 16 Feb 2018 13:30 (Abhi: none) ला G8 signal येतो. दोन्हींत फरक कसा करायचा? | बदल नाही — golden 28 Sep xfail तसाच; 16 Feb 2018 "none" जपला | (अ) flag ने टोक confirm + अजून एक अट (उदा. flag ची खोली / impulse आकार — Abhi सांगतील ती); (आ) 16 Feb 2018 13:30 चं उत्तर बदलणं (Abhi चं) |
| Q42 | Daily review A1: "मोठ्या degree चा origin" engine मध्ये कसा? | **hybrid (default):** impulse origin close ने तुटला ⇒ (अ) याच trend मधली counter-move इतकी किंवा मोठी शेवटची correction — तिचं टोक ("the top of the previous same-degree correction"); (आ) अशी नसेल ⇒ trend ज्या origin पासून सुरू झाला तो. Close parent पलीकडे ⇒ तेव्हाच origin_broken / flip. Impulse mature (A3) झाला असेल ⇒ gate नाही (मोठा reversal शक्य) — **नोंद:** ही सूट maturity वर (अंदाज `maturity_sigma_d` आणि Q44 target) अवलंबून ⇒ maturity आता "फक्त पुरावा" राहत नाही, रचनेवर परिणाम करते (**जुनी नोंद:** ABC_FIX / PR A नंतर `daily.py` मध्ये mature रचनेत वापरला जात नाही — फक्त V22 cap "weak" + caption). Correction चालू (counter = correction) ⇒ कमाल B (आधीच्या origin_broken सारखा; loosen नाही). Weekly parent नाही: NIFTY Weekly अजून "UP, origin broken" — DOWN दिसत नाही. फक्त trend-start ⇒ पूर्ण history वर NIFTY 2009 पासून UP; फक्त (अ) ⇒ C चा DOWN कधीच लागत नाही | फक्त trend-start; Weekly |
| Q43 | A2: same-degree correction चा संदर्भ — "the largest internal pullback of the impulse **so far**" (A2 शब्द) की Q35 default (चालू leg **किंवा मागच्या impulse leg** चा, जो मोठा)? NIFTY: शेवटचा bounce +559; चालू (5) चा सर्वात मोठा आतला pullback 474; मागच्या leg चा 657 | Q35 default तसाच ⇒ +559 < 657 ⇒ "pullback" (candidate नाही). फक्त "so far" केलं तर +559 candidate होतो, पण 23,593 चा bounce (+474 > 353) सुद्धा same-degree होऊन origin पुढे सरकतो — तुमच्या "तीन bounces lower degree" शी विसंगत | फक्त चालू impulse |
| Q44 | ~~A3: (A) low target~~ **निकाली — खालचा "PR A अंमल" विभाग पाहा** (target = parent नंतरच्या पहिल्या impulse leg चं टोक; numeric fallback काढला). जुना प्रश्न: (A) low target — (1) सर्वकालीन उच्चांकावरून सुरू झाला (NIFTY 26,373 > आधीचा 26,277) ⇒ "त्याहून उंच आधीचा H" नाही ⇒ जुना fallback = history मधला सर्वात खालचा pivot (6,826 — अर्थहीन) | बदल नाही (आधीपासूनचं वर्तन); maturity flag तरीही (5) = (4) − (1) equality target मुळे ON | (अ) अशा वेळी (A) target नाही; (आ) "जवळपास तितकाच उंच" आधीचा H — पण tolerance नवी संख्या (0.5σ ने 26,277 पकडला जात नाही: 96 > 67) |
| Q45 | A1/A2: (4) संपून (5) कधी? Engine: correction (4) चालू ⇒ (5) फक्त confirmed झाल्यावर — close counter-move च्या शेवटच्या HL खाली (nature gate नाही कारण trend-दिशेचं पुढे जाणं). "टोकानंतर LH + मधल्या L खाली" हा पर्याय तपासला: NIFTY च्या complex (4) मधल्या minor रचनेवर तो लवकर (b-102) फुटतो आणि पुढची रचना बिघडते ⇒ default मध्ये नाही. NIFTY: (4) टोक b-46, (5) confirmed b-19 (जुना engine याच दिवशी DOWN flip करत होता). Chart वर correction box टोकापर्यंतच (hindsight object), state पट्टा confirm पासून | तसाच (real-time मध्ये टोक आधी कळत नाही) | टोकानंतर पहिल्या LH वर |
| Q46 | A4: caption मध्ये wave क्रमांक ("impulse 5 of C")? Q34: mechanical count ला (n) नाही | क्रमांक नाही: "Trend DOWN (impulse) · pullback in progress (lower degree) · protected 24,774"; mechanical L-index फक्त JSON debug | mechanical क्रमांक दाखवा |
| Q47 | B1 "origin at risk": engine नियम = correction किंमत protected च्या `maturity_sigma_d` × σ_D आत (जुनी संख्या). BANKNIFTY (87% retrace, सर्वात जवळ 759 points > 0.5σ) ला तो लागत नाही — तुमच्या उदाहरणात लागायला हवा होता | नियम तसाच (निकाल पाहून बदल नाही); caption मध्ये depth % दाखवतो | retrace ≥ ठराविक अपूर्णांक (तुमची संख्या) |
| Q48 | C1 1H / 15M review charts: "trend-degree legs, corrections as boxes" — 1H / 15M ला स्वतःची trend-degree रचना engine मध्ये नाही (Daily legs आठवडे लांब; 1H window 8 sessions) | default: ≤ 6 level पट्टे + trigger candle + (15M) entry/SL/target; Daily अवस्था title मध्ये; बाकी debug | 1H वर Daily चा चालू leg / correction box प्रक्षेपित करा |
| Q49 | ABC_FIX / FIXTURES: counter-move स्वतःच 5-wave impulse ⇒ flip — पण zigzag चा a (आणि double zigzag चा W) सुद्धा 5-wave impulse असतो; Elliott त्या क्षणी wave A आणि नव्या trend चा wave 1 वेगळे करू शकत नाही. Engine degree संदर्भ: counter impulse चा आतला pullback (wave 2 / 4) ≥ Q22 degree_ref (चालू / मागच्या impulse leg चा सर्वात मोठा आतला pullback) ⇒ same degree ⇒ flip शक्य | default: Q22 leg-degree संदर्भ — library 100 / 112 pass; `very_deep_holds_origin` व `double_zigzag` (12 cases) strict xfail; real NIFTY / BANKNIFTY तुमच्या counts प्रमाणे | संपूर्ण correct होणाऱ्या impulse चा संदर्भ (trend-degree impulse सुरुवातीपासून): library 112 / 112 pass, पण real BANKNIFTY Feb–Mar घसरण "UP correction" (parent 32,155) — तुमच्या count विरुद्ध |
| Q50 | A1 parent: #289 hybrid ("मागच्या same-degree correction चं टोक", नसेल तर trend सुरुवातीचा LH) की ABC_FIX ("prior impulse's origin = the Feb top") | default: ABC_FIX — trend-degree impulse ची सुरुवात (टोक, उदा. NIFTY fixture मध्ये (B) top 1352, आधी LH 1302); A1 correction पूर्ण ⇒ correction चा शेवट. #289 चा hybrid test strict xfail. Hybrid + provisional restore ⇒ real NIFTY post-holdout "UP correction" (जुन्या parent वर restore). A3 "mature impulse ⇒ सामान्य origin_broken" सूट सुद्धा rule 1 ने बदलली: mature नंतरची 3-wave counter-move सुद्धा correction (counter impulse असेल तरच break) | hybrid / A3 सूट परत (Q42 सारखे) |
| Q51 | ABC_FIX rule 3 "conviction up": engine मध्ये फक्त caps (कमाल B / weak) आहेत, grade वाढवण्याची यंत्रणा नाही | default: पुरावा `DState.evidence` + `engine.step1` ctx["evidence"] / note मध्ये नोंद (cap बदलत नाही; फक्त नवा impulse चालू असताना). दोन मर्यादा: (अ) sharp zone मध्ये संपलेली A1 correction zone च्या कडेपलीकडे close वर completion धरते (Q45 च्या HL break आधी); (आ) पुरावा फक्त A1 (origin तुटलेल्या) correction साठी — origin न तोडणारी correction zone मध्ये संपली तर नोंद नाही | पुराव्यावर grade +1 (नवीन नियम — तुमची संख्या / अट) |
| Q52 | Fixture library: sideways triple three (zigzag + X + flat + X + triangle Z) — engine दोन box करतो (W-X-Y एक correction, Z नंतर वेगळी); trend / origin बरोबर, फक्त family box चुकतो | default: strict xfail (family only); 5-segment combination वाचन `daily_legs.read_counter` मध्ये जोडलं, पण completion W-X-Y नंतरच होते | Z triangle ला correction चा भाग मानणं (completion नियम बदल — तुमचा निर्णय) |
| Q53 | ABC_FIX rule 1 नंतर जुन्या Q15 / Q23 / Q27 / Q36 fixtures मधली 3-wave counter-move (trend सुरुवात टिकलेली) आता correction ⇒ default मध्ये origin_broken / RANGE / Q36 नकार दिसत नाहीत | default: ती यंत्रणा counter impulse किंवा trend सुरुवात तुटल्यावरच चालते; जुने tests `daily_parent_gate` off ने तीच यंत्रणा तपासतात + नवा test (default ⇒ correction). Q28 / Q36 nature gate चं वाचन जुनंच (Elliott subdivision वाचन फक्त ABC_FIX साठी) | जुने fixtures नव्या मार्गाने (counter impulse) पुन्हा बांधा |
| Q54 | तात्पुरत्या completion चा stack (`prov`) फक्त confirm (corr_end) किंवा अपयशी restore वर रिकामा होतो; confirm कधीच न झाल्यास जुन्या अवस्था राहतात (restore फक्त snapshot चा origin / parent आज close ने टिकला तरच) | default: तसेच — expiry चा प्रयत्न correction box ची सुरुवात (leg_from) बिघडवत होता | expiry नियम (उदा. confirm-equivalent bookkeeping सह) |
| Q55 | **निकाली — खालचा "PR A अंमल" विभाग (B: पहिला तोडलेला swing low).** जुना प्रश्न: ABC_FIX rule 2 "sharp-fall point": engine = impulse मधला wide-range धाव सुरू होण्याआधीचा शेवटचा उलट swing (DOWN ⇒ swing **high**). Real BANKNIFTY: Feb–Mar घसरणीसाठी हा 12 Feb चा high (60,598–60,864) येतो; तुम्ही chart वर late-January चा swing **low** (तुटलेला support ⇒ supply) दाखवला, जिथे c (58,706) संपला. त्यामुळे real chart वर rule 3 पुरावा / rule 5 caption येत नाही (trend, protected 58,706, next demand बरोबर) | default: तसेच (निकाल पाहून व्याख्या बदलली नाही) | sharp-fall point = wide-range धावेने तोडलेला शेवटचा swing low (DOWN; UP आरसा) |

## PA standard — decisions (Abhi) and provisional choices

**Abhi decided:**
1. E1–E4 go live in PAPER (entry gate = the four entry models); the old ③ (BOS impulse + K pullback) stays a logged diagnostic only.
2. No 6a required set for model entries — the models are independent; per-model PAPER stats decide later. The 13 Oct golden is
   principle-level: E2 / E3 never fire while the zone study reads absorption without a handover (E1 / E4 not forced to "no entry").
3. Vision mode = human_confirm (Vision audits and shows its verdict, never skips a card, never enters without ✅; no reply ⇒ the card
   expires, no entry).
5. The range comes from structure (not the C-13 equal-highs / equal-lows reading).
6. `daily_leg_read` = compare (Elliott ratios leave the reading; `elliott` stays as the what-if).

**Provisional (lead, from the method + research defaults; Abhi may override):**
- Overlapping areas of the same role visited together = one location: at most one signal per model per overlapping cluster per visit
  (`entry_cluster_rule = cluster`; the card lists every member area; ~~E1 invalidation = beyond the cluster's far edge~~ —
  **SUPERSEDED by RC1 (Abhi 21 Oct, Z-1u): the cluster only counts; edges, trigger and invalidation come from the visited area**).
- Engine entries respect the existing dashboard setting `max_hits_per_zone`, as every other entry path does (~~per area / cluster~~
  **SUPERSEDED by RC1: per visited area**, per role, per day).
- E4a kept as is, observed in the PAPER stats.
- Hidden divergence = the classic reading (the pullback low vs the trend's previous higher low across the impulse; mirror for highs);
  the inside-the-move read is kept as a second, labelled read.

## Abhi उत्तरं Q22–Q34 (batch) — अंमल

> **closed (2026-10-21):** answered (implementation record). Later method rows replace some of them (Q22 / Q27 / Q28 → layer 1 ✅ L1-b; Q24 / Q30 → L3-f / L3-m; Q26 → L6-a).

| # | निर्णय | अंमल |
|---|---|---|
| Q22 | option — रचनात्मक: correction त्याच degree ची ⇔ impulse च्या सर्वात मोठ्या आतल्या pullback पलीकडे; वेळ फक्त पुरावा; 0.5 / 0.382 / 0.618 नाही | `corr_degree_rule` = internal_pullback (default); जुना ratio फक्त what-if; Q35 default |
| Q23 | option — origin close-through, उलट impulse नाही ⇒ कमाल B (नोंद तशीच) | `engine.step1` cap B + नोंद |
| Q24 | default | बदल नाही |
| Q25 | default | बदल नाही |
| Q26 | default | बदल नाही |
| Q27 | option — origin तुटला + दोन समान H / L ⇒ RANGE; पट्टा ② / ③ ला | `range_after_trend`; `levels.active(…, band)`; Q38 |
| Q28 | option — 3-wave (corrective) रचना trend लावत नाही; impulse-स्वभावाचा पाय येईपर्यंत trend नाही | `daily_start_nature_gate` (Q32 adapter); Q36 / Q37 |
| Q29 | default | बदल नाही |
| Q30 | default — 26 Aug A ⇒ B चालेल, re-tune नाही | बदल नाही |
| Q31 | default — holdout sealed; BANKNIFTY 2-year chart पूर्ण history वर; NIFTY chart फक्त holdout नंतर | view: window शेवटच्या sealed row नंतर |
| Q32 | option — Daily adapter legs2 / patterns2 (आधी) | `decision3/daily_legs.py` (legs2 C + patterns2 5 / 3-wave नियम) |
| Q33 | option — engine दोन्हींसाठी पूर्ण history (warm-up); NIFTY साठी holdout तारखांचा कोणताही output नाही (test) | `decision3/history.py`; `v22_check` / view / telegram_view / engine rows; Q7 बदलला; Q39 |
| Q34 | option — mechanical count ला (n) नाही; "L7" फक्त debug; Elliott लेबल फक्त advisory | `DState.wave` = "L5"…; describe / caption / chart वर क्रमांक नाही |
| #284 | golden अपेक्षा कधीच बदलायची नाही; xfail + issue तसेच; 4 marked दिवसांसारखं पायरीवार निदान; rule / degree चूक असेल तरच वेगळ्या PR ने दुरुस्ती | निदान अहवाल (पुढे) |


## Abhi उत्तरं Q35–Q40 — अंमल

> **closed (2026-10-21):** answered (implementation record). Q40's ATR-distance filter is replaced by C-14 (method table below).

| # | निर्णय | अंमल |
|---|---|---|
| Q35 | default OK | तसाच |
| Q36 | option — flip ला सुद्धा Q28: नव्या दिशेचा impulse-स्वभावाचा पाय हवा; फक्त corrective पायांची उलट रचना ⇒ origin_broken (Q23 कमाल B); Q29: त्याच दिवशी flip फक्त impulse पाय असेल तर | `flip()` दोन्ही मार्ग (अ / आ) `nature_ok` ने; नकार ⇒ why मध्ये "(Q36; कमाल B)"; `daily_start_nature_gate` सुरुवात + flip दोन्हीला |
| Q37 | default OK | तसाच |
| Q38 | default OK | तसाच |
| Q39 | default OK | तसाच |
| Q40 | option (refined) — window आधीचे महत्त्वाचे Daily levels हवेत: फक्त trend-degree swings (impulse origin / टोक, correction टोकं) + Weekly swings, किंमतीपासून ATR-scaled अंतरात; NIFTY holdout swings ⇒ फक्त किंमत (तारीख masked) | `levels._prior_levels`: degree-aware Dow चे protected (origin / correction टोक) + `imp_end` + Weekly pivots, `prior_level_atr_mult` (8) × ATR_D (`prior_level_atr_n` 14) आत; bar 0 ला जन्म, भूमिका तेव्हाच्या किंमतीनुसार; birth "a:D-prior" / "a:W-prior" |

## Level bots — confirmation (TRADE_SESSION_LEVEL_BOTS_CONFIRMATION) — MVP मध्ये घेतलेले default निर्णय (Abhi ने बदलावे)

> **closed (2026-10-21):** superseded — the level bots are not rebuilt here: they stay off in one-bot mode and are rebuilt in ATP on the ported reader (`docs/reader/STABLE.md`, `METHOD_MAP.md` "Level bots"). The decision3 parts (LB11, LB25–LB30) are replaced by layer 3 (L3-a … L3-n).

| # | प्रश्न | MVP default | पर्याय |
|---|---|---|---|
| LB1 | A1: impulse origin तुटला, parent टिकला (same-degree correction चालू) — नवे entries? | नाहीत (`allow_parent_correction` = false, fail-safe; spec "origin being invalidated ⇒ no entries") ⇒ BANKNIFTY सारखा c-top short सुद्धा नाही | trend बाजूचे entries चालू (setting) |
| LB2 | Confirmation mode मध्ये exit: "structural (area पलीकडे खरा break) + emergency stop" | bots चे सध्याचे exits तसेच (कधीच अडवत नाहीत); structural exit नियम L5/L6 नंतर | structural exit जोडणे |
| LB3 | Grade B ⇒ lots | ×1.0 (`gate_grade_b_lot_mult`) — बदल नाही | उदा. ×0.5 |
| LB4 | एकाच किंमतीचा level (zone_low = zone_high) | शून्य-रुंदीचा area (स्पर्श / आतली कड = तीच किंमत) | median range च्या भागाने पट्टा |
| LB5 | आकडे (निकाल न पाहता ठरवले, dashboard वर): impulsive approach ≥ 1.5 × median range, close टोकाच्या 25% मध्ये, सलग 2; `max_armed_bars` 8; SL buffer 0.25 × MR; median range 20 bars | तसेच | L6 replay नंतर Abhi |
| LB6 | RSI divergence पुरावा | MVP मध्ये NA (grade मध्ये मोजत नाही) | rsi2 मधून जोडणे |
| LB7 | Daily `mature` (impulse target जवळ) | gate नाही (फक्त नोंद) | mature ⇒ नवे entries नाहीत |
| LB8 | c0 "dominant" commitment: body किती पट window सरासरी? | 1.5× (`commit_dom_mult`, register "अंदाज") — निकाल पाहून नाही | 1.25 / 2.0 |
| LB9 | a2 handover वाचन: पहिल्या / दुसऱ्या अर्ध्याची तुलना; body आवश्यक + इतर उप-तपासण्यांपैकी किमान अर्ध्या | तसेच (`study_min_bars` 4) | प्रत्येक उप-तपासणी आवश्यक |
| LB10 | SENSEX volume | SENSEX FUT (BSE) resolver नाही ⇒ NA ⇒ grade कमाल B | BSE FO resolver जोडणे |
| LB11 | Engine (decision3) diffs: ④ (a) आता relative contraction (`power_a_rule`); ④ (e) handover-volume (volume असेल तर, engine च्या 15M data मध्ये volume नाही ⇒ NA); commitment ला dominance + volume फक्त `win` दिल्यावर (gate) — ~~engine call अजून win देत नाही~~ **2026-10-12: V22 ⑥ आता `method.confirm` (a2 + c0 + c1, LB25–LB30)** | decision3 tests / goldens मध्ये बदल नाही (फक्त जुन्या strict-3 test ला `power_a_rule="strict3"`); v22 review charts पुन्हा बनवले नाहीत | engine मध्ये commitment ला K window देणे (Abhi सांगतील तेव्हा) |
| LB18 | L6 replay cost: option premium इतिहास नाही ⇒ P&L index points; cost = 1 lot naked ITM buy (NIFTY premium ₹150, lot 75, delta 0.6, slippage ₹0.5 / बाजू ⇒ ≈ 3.2 pts; BANKNIFTY ₹350 / 35 / 0.6 / ₹1 ⇒ ≈ 6.7 pts) | `COST_DEFAULTS` (निकाल न पाहता) | Abhi चे आकडे / credit spread चा cost |
| LB19 | L6 exits: touch आणि confirmation दोघांना bot चेच exits — naked spot % SL / target entry पासून + TSL-to-breakeven (5M / SRv2 0.10 %, Classic 0.6 %, sticky; live चं "premium ≤ 0" ⇒ spot ≤ entry); premium-points SL / TSL / target, premium trailing, spread exits, next-level exit replay नाहीत (premium इतिहास नाही) | तसेच; structural SL / target फक्त तिसरा तुलना-arm (not live) | premium model / LB2 structural exit live करणे |
| LB20 | L6 levels: सत्र सुरुवात + दर 60 मिनिटं (live: 1M / 5M दर 5 मिनिटं, 15M+ दर 15 मिनिटं); level memory replay नाही | `level_refresh_min` 60 | 5 / 15 मिनिटं (run वेळ ×4–12) |
| LB21 | BANKNIFTY intraday इतिहास फक्त 15M ≈ 3 महिने (2026-07 → 10, calendar NIFTY design window शी जुळतो) ⇒ फक्त SRv2, illustration | तसेच | VPS वरून BANKNIFTY 1m / 5m IS / VAL इतिहास |
| LB22 | MCX: फक्त 30m ≈ 4 महिने, volume नाही; confirmation 30m (live 15m); Daily trend ≤ 4 महिन्यांवरून (live ~10 वर्षं); cascade / supertrend / structure SL replay नाहीत | illustration | MCX 15m + Daily लांब इतिहास (L4 सोबत) |
| LB23 | IS / VAL मध्ये index futures volume नाही ⇒ gate ची volume तपासणी (c0) replay मध्ये कधीच लागत नाही (grade ≤ B) | तसेच | NSE F&O bhavcopy (Daily) पुरेसा नाही — intraday futures volume हवा |
| LB24 | Trend split: Daily trend UP / DOWN पण gate ने entries अडवले (origin broken / धोक्यात, A1 parent correction) ⇒ bull / bear मध्येच, verdict "trend unclear" | तसेच | वेगळा "blocked" गट |
| LB25 | c1 "LTF stops making lower lows": higher low म्हणजे काय? | **review 🔴1 नंतर:** study window मधल्या सर्वात खालच्या low (LL) नंतर किमान एक बंद LTF candle (LL हाच शेवटचा बंद bar ⇒ "LTF still trending against"); higher low = LL नंतर CHoCH candle पर्यंतचा सर्वात खालचा low (समान ⇒ double bottom); किंवा LL candle ने आधीचा LTF swing low / area ची far edge sweep करून close परत आत (मग तीच candle CHoCH असू शकते). V-reversal / stair-step / gap-down पहिलाच bar low ⇒ चालतं | 1-bar pivot HL आवश्यक (कडक — V-reversal कधीच नाही) |
| LB26 | c1 "last LTF lower high": कोणता swing? | lower low आधीचा शेवटचा LTF 1-bar swing high (संदर्भ = सत्र सुरुवात (bots) / K चं impulse टोक (V22)); pivot नसेल (सरळ घसरण) ⇒ lower low आधीच्या candle चा high | संपूर्ण pullback चा सर्वात जवळचा मोठा swing |
| LB27 | a2 "handover study passed" = ? | absorption **नाही** (gate); handover (दोन्ही बाजू) = grade A पुरावा — level bots आधीसारखंच (a2 / c0 वर्तन बदल नाही) | handover = True आवश्यक (कडक; अनेक entries जातील) |
| LB28 | V22 study window ("arrival" कधी)? | K मध्ये level ला स्पर्श करणाऱ्या 15M bars चा शेवटचा सलग गट (स्पर्शांत ≤ `touch_window_bars` अंतर); arrival bar स्वतः commitment असेल ⇒ window = तीच candle ⇒ dominant नाही (level bots सारखं) | "near" साठी अंतर (σ / ATR) setting — #24 मधले 25-Mar लाल candles window मध्ये येतील |
| LB29 | LTF data कुठून (bots)? | त्याच fetch मार्गाने: 5M Instant = bot चे स्वतःचे 1-मिनिट candles (पुन्हा fetch नाही); Classic 1M, 15M SRv2 5M (Upstox index), MCX 5M (contract) — cycle मध्ये पहिल्या area result ला एकदाच; नाही ⇒ "LTF data missing" (entry नाही). Replay: BANKNIFTY (15M-only) आणि MCX (30m-only) ला LTF नाही ⇒ confirmation entries नाहीत | `gate_ltf_minutes` dashboard override |
| LB30 | V22 volume (c0 / ④ e) | `futures=` (collector 5M FUT ⇒ legs2.volume.bar_volume) किंवा m15 चा volume column; IS / VAL मध्ये intraday FUT नाही ⇒ NA ⇒ grade कमाल B (सगळे इतिहासातले setups B) | Upstox FUT इतिहास |


## Chart Reader v2 (TRADE_SESSION_CHART_READER_V2) — CR0–CR3 मध्ये घेतलेले default निर्णय (Abhi ने बदलावे; research-only, कोणताही bot / decision3 वापरत नाही)

> **closed (2026-10-21):** dormant — reader2 is research only (never on the reading path, `tests/test_reader2_boundary.py`); Abhi's method is the reader spec. Defaults stay as recorded; reopen only if reader2 work resumes.

| # | प्रश्न | default | पर्याय |
|---|---|---|---|
| CR-Q1 | §2d "candles फक्त lowest degree साठी" — अर्थ? | **सोडवला (review नंतर):** candles फक्त lowest degree ला (leg च्या आत खालचे pivots नाहीत ⇒ तो leg स्वतः lowest swing); वरच्या degree चा anatomy = sub-legs (एक degree खाली, recursive) चा roll-up: motive sub-legs (आकाराने वजनी) + counter sub-legs + थांबे (वेळ / खोली). लांब leg च्या सगळ्या candles ची सरासरी नाही. Daily + `low=` 1H ⇒ lowest-degree candles मध्ये वजनी सरासरी | — |
| CR-Q2 | Correction fixture library वर reader2 (library candles एकसारख्या) | `tests/test_reader2_library.py` (round 2 नंतर): उलट flip नाही 32/32; correction ⇒ trend-capable impulse नाही 32/32; impulse दिशा 0/32 — library चा degree-2 leg lead-in top ⇒ lower high ⇒ impulse असा एकच (9-wave, unparsed), re-read ला बहुमत नाही ⇒ trend नाही. Corrections "correction low" / uncertain (एकसारख्या candles मध्ये प्रत्येक push आवेगी दिसतो). आकडे tune केले नाहीत | dev gallery वर `dc_k` calibration |
| CR-Q3 | three-push आकार आणि climax candle anatomy vote मध्ये नाहीत | three-push ⇒ roll-up `pause_depth` (counter ÷ motive चाल) + structure; climax फक्त `leg_features` मध्ये मोजलं (vote नाही) | स्वतंत्र three-push / climax features |
| CR-Q4 | impulsive candles + impulse रचना असलेली counter-move जी prior swing तोडत नाही (wave 1 की wave A — Q49) | invariant 2 / 5 ⇒ "uncertain" (trend तसाच, entry नाही) ⇒ uncertain rate वाढू शकतो | label impulse ठेवा पण flip नाही |
| CR-Q5 | Protected origin पलीकडे close ⇒ trend "uncertain"; पुन्हा trend कसा? | **बदल (review):** uncertain कायमचं नाही — पुढचा trend-capable impulse (दोन्ही votes सहमत), कोणत्याही दिशेचा, trend पुन्हा ठरवतो (origin आधीच तुटला ⇒ prior swing break ची गरज नाही). BANKNIFTY: uncertain 66 % ⇒ 44 % (उरलेले = bull phases ज्यांचे up-legs zigzag / mixed वाचले जातात — gallery) | — |
| CR-Q6 | Anatomy / degree आकडे (`FEATURES`, `a_hi`/`a_lo` ±0.25, `dc_k` 2/4/8, `mr_bars` 20, re-read गुणक 1/0.875/0.75/0.625 — फक्त एक degree खाली; roll-up ROLLUP / वजनं) | register मध्ये "अंदाज"; dev gallery (Abhi labels) वरच calibrate — trade निकालांवर कधीच नाही | — |
| CR-Q7 | Index volume | caller `volume` column देतो: `reader2.frame.with_futures_volume` (near-month, expiry/contract वरून); नाही / 0 ⇒ volume features NA (vote बाकी features वर). SENSEX FUT resolver नाही ⇒ NA (LB10 सारखं) | — |
| CR-Q8 | Roll-up चे नियम (review नंतर, "अंदाज"): pause पुरावा फक्त ≥ 2 counter sub-legs असताना (एक थांबा = zigzag चा b सुद्धा); motive आवेगी नसेल तर leg आवेगी नाही; motive चालीचा ≥ 25 % वाटा असलेला सुधारात्मक motive sub-leg ⇒ veto (big-c zigzag चा a) | तसेच; dev gallery वर तपासा | veto share 0.2 / 0.33; pause ला एकच counter पुरे |
| CR-Q9 | एकच vote: structure impulse + candles गप्प (re-read नंतरही) ⇒ "uncertain"; structure correction + गप्प ⇒ correction "low"; फक्त candles ⇒ "low". "low" impulse trend ठरवत / उलटवत / protected हलवत नाही (Abhi ची तक्रार: रचनेवरूनच impulse नाही) | तसेच | structure-only impulse ⇒ impulse "low" (uncertain ऐवजी) |
| CR-Q10 | (round 2) sub-legs ची संख्या / two-push cap anatomy मधून काढले — wave count फक्त structure vote मध्ये. a-b-c विरुद्ध 1-2-3-4-5 candles च्या पुराव्याने: c_like_a (c चे candles / वेग / आकार a सारखे), b_brief (b लांब vs wave 2/4 थोडके), middle_push (सर्वात आवेगी push मधला = wave 3). परिणाम: sharp a-b-c ⇒ correction "low" (anatomy neutral); लहान wave 2 / 4 असलेला impulse ⇒ uncertain (कधीच correction high नाही) | तसेच; थ्रेशोल्ड "अंदाज" — gallery वर | — |
| CR-Q11 | Re-read: तीन पर्याय (0.9 / 0.75 / 0.6 × dc_k[D−1]), कधीच dc_k[0] खाली नाही (नाहीतर abstain) — **म्हणून degree-1 legs चं re-read कधीच होत नाही** (dc_k[0] × 0.9 < floor): त्यांचा label फक्त पहिल्या वाचनावर (सहमत ⇒ high; विरोध ⇒ uncertain; एक vote ⇒ low / uncertain), कधीच medium नाही; बहुमत 2 / 3, दोन्ही दिशांना एकच; नाव असलेली correction re-read ने impulse होत नाही. परिणाम: mis-placed-pivot test आणि sharp_a चे 3 self-check tests strict xfail (3/3 पर्याय 5 waves वाचतात तरी zigzag ⇒ uncertain) | तसेच — Abhi निर्णय | नाव असलेली correction सर्व (3/3) पर्याय impulse सांगतात तेव्हा re-read होऊ द्या |
| CR-Q12 | BANKNIFTY Daily trend (round 2 नंतर): UP 23.6 % / DOWN 5.5 % / uncertain 55.2 % / warm-up 15.7 %. 37 पैकी फक्त 3 degree-2 legs trend-capable impulse. सगळे uncertain bars 2 origin-close घटनांतून (2018-07 → 2021-05, 2021-09 → 2024-06); origin-close ने trend तसाच ठेवला असता तर 2019–2024 rally मध्ये "DOWN" ⇒ origin-close नियम कारण नाही, ओळखले न जाणारे up-impulses कारण | gallery labels वर तपासा (degree / anatomy calibration) | — |
| CR-Q13 | (CR3) Gallery marking कुठे साठवायची? | Supabase table `reader2_gallery` (backtest_review / golden_gallery सारखी, VPS `.env`) — redeploy नंतरही टिकते; `scripts/reader2_gallery_export.py` (VPS) ⇒ **private trade-data** `reader2_gallery/labels/dev|test/<id>.json`. Repo public ⇒ labels repo मध्ये कधीच नाहीत (Abhi नियम: charts / marking फक्त private storage). ⇒ CR4 scoring: trade-data असलेल्या ठिकाणी (VPS / हे sandbox), public CI मध्ये नाही — Abhi निर्णय | labels public repo मध्ये (CI secrets शिवाय) — फक्त Abhi परवानगी दिल्यास |
| CR-Q14 | BANKNIFTY / SENSEX साठी NIFTY holdout च्या तारखा (2024-04 … 2026-06) | auto candidates त्या तारखा टाळतात (correlated बाजार); अपवाद फक्त तुमचा आधीचा BANKNIFTY case (Dec 2025 → Oct 2026, Feb → Mar 2026 DOWN impulse) — `holdout_dates_exception`. NIFTY ला कधीच अपवाद नाही | BANKNIFTY ला NIFTY holdout लागू नाही (सगळ्या तारखा) / case सुद्धा वगळा |
| CR-Q15 | SENSEX चा data repo / trade-data मध्ये नाही (Daily / 1H / 15M कुठलाच) | **✅ Abhi 2026-10-12: SENSEX हवा, split symbol-निहाय stratified — additive `--add-symbol SENSEX` (NIFTY / BANKNIFTY तसेच), CR-Q22–CR-Q26.** आधी: 0 SENSEX charts; त्याचा वाटा (13) NIFTY / BANKNIFTY ला (manifest `missing` मध्ये नोंद). **Marking सुरू करण्याआधी** VPS वरून SENSEX candles आणल्यास manifest पुन्हा बनवा (split बदलतो) | marking नंतर SENSEX charts वेगळ्या "append" यादीत (split न बदलता) |
| CR-Q16 | Test / dev एकाच तारखांवर पण वेगळ्या TF वर (उदा. BANKNIFTY 15M test Jul 2026 वि. BANKNIFTY Daily case dev) | चालतं — एकाच symbol + TF वर कधीच overlap नाही (grid); cross-TF जोड्या (12) manifest `cross_tf_overlap` मध्ये | symbol + तारखा overlap ⇒ एकाच split मध्ये (कडक; BANKNIFTY intraday सगळे dev होतील) |
| CR-Q17 | Data मर्यादा: NIFTY auto charts फक्त IS 2015–2021 (VAL जपला, research/golden_gallery सारखं; holdout नाही); BANKNIFTY 1H / 15M फक्त 2026-07-13 → 10-09 (≈ 3 महिने ⇒ 1H चे फक्त 3 windows) | तसेच — NIFTY 23 (D 8, 1H 7, 15M 8), BANKNIFTY 17 (D 7, 1H 3, 15M 7) | NIFTY VAL सुद्धा; BANKNIFTY intraday इतिहास VPS वरून |
| CR-Q18 | तुमचे आधीचे 2 cases (BANKNIFTY sharp fall → a-b-c → DOWN; NIFTY flat C wave) | नेहमी dev, `calibration: false` — logic त्यांच्यावरच ठरलं / NIFTY case CONTAMINATED ⇒ फक्त regression, thresholds त्यांच्यावर calibrate नाहीत | calibration मध्येही घ्या |
| CR-Q19 | Marking UX | Chart वर क्लिक (प्रत्येक high / low वर ठिपका; Streamlit 1.63 plotly selection — headless browser मध्ये तपासलं) + fallback bar क्रमांक + H / L; legs = लागोपाठच्या बिंदूंची साखळी (एक chart = एक degree); labels तक्त्यात | दोन degrees (मोठा leg + sub-legs) एकाच chart वर; zones सुद्धा क्लिकने |
| CR-Q20 | Gallery आकडे | window Daily 160 / 1H 140 (≈ 20 सत्र) / 15M 150 (≈ 6 सत्र) bars; किंमत tolerance 0.25 × median range; trend states up / down / range / uncertain; shape tags (दिशा 0.4, deep 0.618 / shallow 0.382, flat b ≥ 0.9 a + c ≥ 1.2 a, impulse 0.7 / 0.5) फक्त विविधतेसाठी, निकाल पाहून नाहीत; seed 7 | लहान / मोठे windows; tolerance 0.5 MR |
| CR-Q21 | CR4 CI ला candles लागतात: NIFTY IS (22 charts) repo च्या parquet मध्ये; BANKNIFTY (17) आणि NIFTY golden case (1) private trade-data मध्ये | CR4 मध्ये ठरवायचं — default: data नसलेले charts CI मध्ये skip (golden_chart_cases सारखे), पूर्ण gallery score VPS वर | CI ला trade-data read-only deploy key (secret) / gallery windows चे candles public repo मध्ये (README नियमाविरुद्ध) |
| CR-Q22 | (Abhi 2026-10-12 ✅ SENSEX, stratified split) SENSEX volume | BSE F&O SENSEX near-month futures सापडले तर त्याचा 15M volume फक्त चालू contract च्या काळापुरता (expired futures ⇒ Upstox Plus हवा, probe 401) ⇒ बहुतेक जुने bars volume NA ⇒ grade cap B; near-month सुरुवात = front expiry − (next − front) | Upstox Plus (expired futures) / BSE bhavcopy वरून दैनिक futures volume |
| CR-Q23 | SENSEX manifest repo मध्ये कसा येतो (token VPS वरच) | VPS: fetch + `--add-symbol SENSEX --out <trade-data>/reader2_gallery/manifest_sensex_add.json` ⇒ trade-data push ⇒ Claude review (NIFTY / BANKNIFTY entries byte-identical, test pin) ⇒ repo मध्ये commit | VPS वरून थेट repo PR (VPS ला repo push key लागेल) |
| CR-Q24 | CD14 leg चा शेवट | 2026-04-02 low 49,954.85 (bar 73) — तुमच्या नोंदलेल्या count चा (abhi_cases) आणि fall चा खरा तळ; मार्चचा तळ 2026-03-30 50,105.25 (bar 71) फक्त 2 bars आधी, थोडा उंच. Seed मध्ये trend "down" Feb top पासून (validator ला किमान एक trend state हवा) — बाकी chart तुम्ही mark करा. **Anatomy vote तुमच्याशी असहमत ⇒ तो reader चा calibration case; label तुमचाच राहतो.** Chart `calibration: false` (abhi_cases नियम) तसाच | मार्च तळावर (bar 71) leg संपवा; हा chart calibration मध्ये घ्या |
| CR-Q25 | SENSEX 1H कसा | 15M चा 09:15-anchored resample (BANKNIFTY 1H v3 `hours/1` चेच bins 09:15 … 15:15, 15M शी तंतोतंत सुसंगत, कमी calls) | v3 `hours/1` थेट |
| CR-Q26 | SENSEX intraday इतिहास | Upstox minutes data 2022 पासूनच (default `--intraday-years 4.5`); NIFTY holdout तारखा (2024-04 … 2026-06) gallery मध्ये टाळल्या (CR-Q14) ⇒ SENSEX intraday windows 2022 → 2024-03 आणि 2026-07 → | — |

## Abhi उत्तरं Q44 / Q55 + family (TRADE_SESSION_Q44_Q49_Q55_CHART_FIX) — PR A अंमल

> **closed (2026-10-21):** answered. The "उघडा" note (COMPLETE ⇒ some 9-wave readings) is covered by layer 1 ✅ (L1-a / L1-b: Daily structure by structure logic; B1: wave labels are context only).

| # | निर्णय | अंमल |
|---|---|---|
| Q55 | (B) sharp-fall point = wide-range धावेने तोडलेला **पहिला** swing low (UP आरसा: swing high); band = swing candle wick टोक + base candles | `daily.sharp_zone`: एक degree खालचे swings — impulse origin च्या **आधीचेही** चालतात (BANKNIFTY: Feb top आधीचा late-Jan low), धावेच्या आतले lows सुद्धा; अट: swing चा पहिला close-break origin नंतर, धावेतल्या candle ने (range > आधीच्या bars चा सरासरी range, दिशेचा body, सलग दोन); त्यांपैकी (range > आधीच्या bars चा सरासरी range, दिशेचा body, सलग दोन) close ने तोडलेला सर्वात आधीचा swing; zone = त्या candle चा wick टोक ⇒ base (±1 candle) body टोक, + EQ. Fixture: धाव दोन lows तोडते — पहिला निवडला जातो (test) |
| Q44 | target = parent origin नंतरच्या पहिल्या impulse leg चं टोक; numeric fallback नाही | `t_first` (A1 सुरू होताना पहिल्या leg चं टोक); `pre_swing` / जुना fallback काढला; target नसेल ⇒ caption "target: none (structure incomplete)"; test: कुठलाही target window च्या किंमत-मर्यादेबाहेर नाही. Real BANKNIFTY: 49,955 (2 Apr wick — March अखेरची घसरण तिथे संपली; 30 Mar low 50,105) |
| family | correction स्वतःच्या (trend) degree वर; combination = दोन **पूर्ण** corrective patterns X ने जोडलेले | box family आता engine च्या trend-degree pivots वर (ते a-b-c इतकेही नसतील तरच एक degree खाली); `read_counter` combination ला W / Y (/ Z) zigzag / flat / triangle / combination हवेत — न ओळखलेला "3-wave" नाही. Real BANKNIFTY Apr → Jun box: "zigzag" (आधी "combination") |
| May low | wick टोकच | खरा May low = **52,783** (18 May wick). 53,027 = 3 Jun चा wick low (उंच low) — जुन्या engine चा UP origin, b low नव्हे. नव्या engine चं b (a-b-c reduction) आणि next demand 52,783 वापरतात; close वापरणारा मार्ग सापडला नाही |

**PR A — independent review नंतर (वर्तन बदल, जाहीर):**
- Fixture: मूळ `acceptance_banknifty` जसा होता तसा परत; "धाव दोन lows तोडते" हा case नवा `acceptance_banknifty_two_lows` (second low 1520).
- Q44 target A1 correction सुरू होताना ठरतो आणि **नवा parent (दुसरी A1 correction) आला की नव्याने** ठरतो (जुना टोक राहत नाही). A1 correction चालू असतानाही caption मध्ये target दिसतो; `mature` फक्त नवा leg चालू असताना. नवा impulse protected आधीच target च्या पलीकडे नेतो ⇒ तो target जुना, दाखवत नाही (random-walk property test ने सापडलं).
- म्हणजे targets / mature आता **फक्त A1 correction नंतर** — आधीचे equality / मोठ्या swing चे numeric targets गेले.
- `read_counter`: combination ला दोन पूर्ण patterns (COMPLETE) ⇒ काही counter-moves चं वर्गीकरण बदलतं.
- Before / after (Daily, NIFTY 2015-01 … 2024-03 फक्त — holdout नाही; BANKNIFTY पूर्ण): **trend एकाही दिवशी बदलला नाही** (NIFTY 0 / 2282, BANKNIFTY 0 / 2479). Phase / counter बदल: NIFTY 55 दिवस (correction ⇄ impulse-pullback), BANKNIFTY 14. Target असलेले दिवस: NIFTY 1785 ⇒ 1220, BANKNIFTY 1756 ⇒ 1095. BANKNIFTY शेवटचा दिवस: [56,586, 16,116] ⇒ [49,955].

**PR A — दुसऱ्या review नंतर (जाहीर):**
- **Mature दिवस** (V22 मध्ये mature ⇒ कमाल "weak" ⇒ setup नाही): NIFTY 1755 ⇒ 809 / 2282 (शेवटचे 250 दिवस: 250 ⇒ 127; शेवटचा दिवस 2024-03-27 mature ⇒ नाही), BANKNIFTY 1685 ⇒ 443 / 2479 (शेवटचे 250: 168 ⇒ 19; शेवटचा दिवस mature ⇒ नाही).
- **V22 setups:** BANKNIFTY 15M (उपलब्ध 1575 bars, 2026-07-13 पासून; Daily पूर्ण history): setup 0 ⇒ 0 (wait 1574, no_trade 1 — दोन्हीकडे सारखे); mature bars 1575 ⇒ 0. NIFTY V22 (2015 … 2024-03 चे 15M, holdout आधी) जड ⇒ चालवला नाही (lead साठी command WORK_LOG मध्ये).
- **Level bots** (`bots_common.level_reaction.context_from_state`, `counter == "correction"` ⇒ entry नाही): BANKNIFTY शेवटचे 250 सत्र (2025-10-07 … 2026-10-09) — `ok` / sides 5 दिवस बदलले (2026-06-29 … 07-03: जुनं "correction" ⇒ नवं impulse / pullback ⇒ entry **चालतो**; उलट दिशेचा बदल नाही); शेवटचा दिवस context तसाच (DOWN, ok, BEARISH; फक्त ctx["mature"] True ⇒ False — gate नाही). पूर्ण history: BANKNIFTY 11 दिवस (सगळे blocked ⇒ allowed), NIFTY (2015 … 2024-03) 51 दिवस (40 allowed, 11 blocked). NIFTY चे अलीकडचे सत्र holdout मध्ये / नंतर ⇒ offline तपासता येत नाहीत (local NIFTY data 2024-03 ला संपतो); 2024-03 आधीच्या शेवटच्या 250 सत्रांत बदल 0.
- Caption: रचनेतला target होता पण protected आधीच पलीकडे ⇒ "target passed" (नवा `DState.target_passed`); रचनाच नाही ⇒ "target: none (structure incomplete)".
- `t_first` / `t_first_par` snapshot (`PROV_KEYS`) मध्ये — सुरक्षा (A1 फक्त रिकाम्या stack वर सुरू होतो ⇒ output बदल 0, वरचे आकडे तसेच).
- **उघडा:** COMPLETE मुळे काही चाली "combination" ऐवजी 9-wave extended **impulse** वाचतात (synthetic शोधात ~4,600 combination पैकी 11) ⇒ अशी counter-move खरा break ठरू शकते (flip शक्य). Real NIFTY / BANKNIFTY वर trend बदल 0, पण नियम म्हणून Abhi ✔ हवा.

## Abhi उत्तर Q49 (TRADE_SESSION_Q44_Q49_Q55_CHART_FIX §2) — PR C अंमल

> **closed (2026-10-21):** answered. The open column (Q49-b, Q49-Q22, Q49-dz, Q49-CH) is covered by layer 1 ✅ (L1-a / L1-b) and B1 (wave labels are context only); the strict xfails stay as recorded.

| # | निर्णय | अंमल | उघडा प्रश्न |
|---|---|---|---|
| Q49 | 5-wave पहिला पाय default **wave A** (trend तसाच); wave 1 फक्त (a) counter-move तो correct करत असलेल्या **impulse च्या origin** पलीकडे close करतो (Abhi: engine चा impulse-leg origin, A1 parent / trend सुरुवात नाही — ABC_FIX rule 1 सुसंगत) किंवा (b) counter-move स्वतःची same-degree 5-wave रचना पूर्ण करते. Ratios / खोली नाहीत | `daily.counter_kind`: same-degree 5-wave ⇒ "wave_1a"; (a) origin = `imp_origin(i)`; त्यापलीकडे close ⇒ wave 1 (flip शक्य; origin = तोच तुटलेला origin); नाहीतर parent टिकला ⇒ A1 correction, `DState.wave_a` (chart "A") + `alt = "1"` (फक्त debug). (b) = `daily_legs.unfolded_123` ("1" 5, "2" 3, "3" "1" पलीकडे 5 — दिसणारे पाय). Telegram / trend line / ① मध्ये wave क्रमांक नाही (Q46) | **✅ (a) चा विस्तार — Abhi मंजूर (2026-10-12)** (setting `q49_impulse_origin`, default `complete_impulse`): चालू impulse leg हा एखाद्या **पूर्ण** 5-wave impulse चा wave 5 असेल (`daily.complete_impulse_start`: P ⇒ impulse टोक read_counter impulse, wave 5 bar ने चालू leg आधीच्या correction मध्ये — Rule 4 origin सुद्धा) तर origin = त्या impulse ची सुरुवात. **तिन्ही नवे fixture tests या विस्तारावर अवलंबून**: साध्या वाचनाने (`q49_impulse_origin: leg`, origin = impulse-leg origin) deep zigzag (`very_deep_holds_origin`), `q49_complete_five` आणि `q49_beyond_impulse_origin` तिन्ही fail (A wave (4) high ओलांडतो ⇒ लगेच flip; पडताळलं) |
| Q49-b | (b) शब्दशः A(5)–B(3)–C(5) = zigzag 5-3-5 | engine: संपूर्ण counter-move 5-wave ज्याचे "1-2-3" स्वतः 5-3-5 ⇒ flip "3" नंतर नाही, counter-move चा "5" चालू असताना (test) | "3" पूर्ण झाल्यावरच flip हवा का? |
| Q49-Q22 | खालच्या degree चा (Q22) 5-wave पहिला पाय | नेहमी wave A — (a) impulse origin तुटला तरी flip नाही; **wave 1 फक्त parent (trend सुरुवात) close ने तुटल्यावर** (आधीसारखंच). why मजकूर तसं सांगतो ("खालच्या degree चा (Q22) … wave 1 फक्त parent … पलीकडे close ने") | बरोबर? |
| Q49-dz | double zigzag (W-X-Y) | W चा a-b-c + X + Y चा a = 5-3-5-3-5 ⇒ (b) ⇒ flip — fixture strict xfail | double zigzag ला अपवाद हवा का? |
| Q49-BN | ✅ Abhi: BANKNIFTY Feb top ⇒ Mar low = **DOWN impulse** (ABC_FIX count) | before / after BANKNIFTY (2016-10 → 2026-10, 2479 दिवस): default `complete_impulse` (base = main): trend / phase 2 दिवस, counter 3, protected 4 बदल — सगळे 2018-07-26 → 27 (base UP · Q49 DOWN, extension मुळे); wave A 36 दिवस (`leg` ⇒ 34); 2026 बदल नाही; शेवटचा दिवस DOWN · protected 58,706 | — |
| Q49-CH | Chart: चालू box चं तात्पुरतं family वाचन (triangle / zigzag) wave A शी विसंगत असू शकतं (A = "c"); wave A चं टोक reading corrective झाल्यावर स्थिर राहतं | box चं "a" = wave A ⇒ मोठी अक्षरं A B C; नाहीतर box अक्षरं नाहीत, फक्त "A"; A टोक स्थिर | box family वाचन wave A पासून सुरू करा (A नंतरचे पाय B / C) — engine बदल |

## Chart declutter (TRADE_SESSION_Q44_Q49_Q55_CHART_FIX §5) — PR B मध्ये घेतलेले default निर्णय (Abhi ने बदलावे)

> **status (2026-10-21):** CD14-A answered; CD1 … CD14-E and the VP1–VP6 table below are display defaults → listed in Still open (layer 6, output). The LB12–LB17 table below → dormant (MCX / level bots, ATP). OB1 → superseded by Z-1c (FUT missing = data problem, no entry); OB2 / OB3 → standing defaults (Still open).

| # | प्रश्न | आत्ता (default) | पर्याय |
|---|---|---|---|
| CD1 | "चालू correction" कोणती? | in-progress box असेल तर तो; box नसताना lower-degree pullback चालू ⇒ एकच "pullback" खूण = चालू, शेवटचा पूर्ण box = आधीची; नाहीतर शेवटचे दोन पूर्ण boxes | फक्त same-direction (त्याच trend मधल्या) corrections मोजणे |
| CD2 | in-progress **candidate** box चं नाव | "pullback (in progress) · NN% of impulse · shape" ("candidate" शब्द नाही); same-degree correction चालू ⇒ "correction (in progress)" | candidate ला वेगळं नाव |
| CD3 | "~6 महिने" | `chart_old_box_sessions` = 126 sessions (setting, फक्त chart); त्यापेक्षा लांब window ⇒ जुने boxes नाहीत, लहान ⇒ फिके, text नाही | 100 / 150 |
| CD4 | "रचना ज्या major low / high वर उभी" (उदा. March low) | शेवटच्या पूर्ण same-degree correction ची सुरुवात (आधीच्या impulse चं टोक: DOWN ⇒ low, UP ⇒ high), rank 2 (window high / low = 3 च्या वर); तो close ने तुटला ⇒ उमेदवार नाही. BANKNIFTY: demand 49,955 (= Q44 target, एकाच पट्ट्यात "· target") | parent origin नंतरचा सर्वात मोठा swing |
| CD5 | demand / supply नाव | आजच्या close च्या खाली ⇒ demand, वर ⇒ supply; तुटलेला ⇒ तुटण्याआधीची भूमिका (उलट बाजू). Protected origin = "protected" (पट्टा + origin रेषा, label एकच — margin मध्ये) | protected ला सुद्धा demand / supply शब्द |
| CD6 | कमाल 1 तुटलेला पट्टा | सर्वात अलीकडे तुटलेला (शेवटचा उलट-बाजूचा close); target आधीच तुटलेल्या पट्ट्यात जोडत नाही (वेगळी dotted रेषा) | तुटलेले कधीच नाहीत |
| CD7 | Caption ओळ 1 "risk" | आजच्या close पासून protected origin पर्यंत ATR_D (`chart_atr_n` = 14, साधा सरासरी true range) + origin_risk असेल तर "(origin at risk)" | % अंतर / points |
| CD8 | Caption ओळ 2 | chart वरच्या (तुटलेले / target सोडून) पट्ट्यांपैकी वरची जवळची supply आणि खालची जवळची demand — जवळच्या कडेपर्यंत ATR_D; पट्ट्यात ⇒ "price inside" | फक्त trend-बाजूची एक |
| CD9 | Label जागा नाही | label सोडतो **आणि** तो पट्टाही (unlabeled पट्टा नको); box label सोडतो, box राहतो. BANKNIFTY 2y: काहीच सोडावं लागलं नाही | — |
| CD10 | Vision consistency | फक्त Daily structure chart: नवं `consistency` field (consistent / inconsistent / na) — inconsistent ⇒ caption ओळीत "structure inconsistent", report मध्ये ❌; audit-only, निर्णयात नाही (PROMPT_VERSION v3) | 1H / 15M charts ला सुद्धा |
| CD11 | Engine ची phase "impulse" म्हणजे काय? | Engine (fold) मध्ये "impulse" = **Dow trend leg** (origin पासून नवं टोक) — 5-wave सिद्ध झालेलं नाही. Chart / caption / title आता प्रत्येक trend leg त्याच्या स्वतःच्या (एक degree खालच्या) pivots वर `daily_legs.read_counter` ने तपासतात (pivots confirm ≤ chart चा bar): impulse / diagonal ⇒ घन नारंगी "impulse (5 waves)"; पूर्ण पण 3-wave ⇒ राखाडी; चालू आणि अजून 5 waves नाहीत (किंवा आतले pivots नाहीत) ⇒ dashed नारंगी "decline / advance in progress — impulse not confirmed", caption "new decline in progress (impulse not yet confirmed)". Engine trend / protected बदलत नाहीत. Strip वर "DOWN · impulse" ⇒ "DOWN · trend leg". पुढे Chart Reader v2 (anatomy vote) candle anatomy जोडेल | — |
| CD12 | Correction box अक्षरं | फक्त labelled (चालू + आधीची) boxes: family ज्या pivots वरून वाचलं तिथेच (`daily_legs.wave_ends`, read_counter चाच शाखा-क्रम) — zigzag / flat / 3-wave ⇒ a b c, triangle ⇒ a–e, combination ⇒ W X Y (X Z); चालू correction ⇒ पूर्ण waves नाच अक्षर; impulse / diagonal ⇒ अक्षरं नाहीत | diagonal ला 1–5 |
| CD13 | Review नंतर (PR B) | जवळचा पट्टा जवळच्या कडेवरून निवडतो आणि मोजतो (ओळ 1 risk तोच नियम); protected / sharp / parent / target / next demand-supply / caption चे जवळचे पट्टे कधीच टाकत नाही (label सरकवतो + leader रेषा), बाकी टाकले ⇒ JSON `chart.dropped` + Vision facts; protected sharp zone च्या पूर्ण आत ⇒ एकच पट्टा "sharp-fall supply · protected …"; तुटलेल्यांची मर्यादा merge आधी; target कोणत्याही न तुटलेल्या पट्ट्यात जोडतो; Vision cache key मध्ये prompt version | — |
| CD14 | Trend leg तपासणी (structure-only) | Chart trend degree वर: engine चे सलग एकाच दिशेचे sub-legs (A1 / दिशा बदलापर्यंत) = एक leg (`trend_impulses`), संपूर्ण leg एकदा read_counter. read_counter impulse / diagonal ⇒ घन नारंगी "impulse (5 waves)"; बाकी सगळं ⇒ dashed "trend leg — impulse not verified (structure-only check)" — trend leg ला कधीच राखाडी / corrective म्हणत नाही; राखाडी legend मधून काढलं. रेषा leg च्या स्वतःच्या trend-degree pivots मधून, window मधला भाग कमाल `chart_leg_path_points` (15) बिंदू. Caption / title: "impulse not verified". BANKNIFTY Feb top 61,765 (3 Feb) → 49,955 (2 Apr): read_counter = **zigzag, n = 9** — Abhi चं "DOWN impulse" वाचन structure-only तपासणीशी जुळत नाही; खरा verifier = reader2 (candle anatomy roll-up), तोपर्यंत "not verified". (आधीचा UP: combination, n = 207) | ✅ Abhi 2026-10-12: खाली CD14-A |
| CD14-A | ✅ Abhi (2026-10-12): default + Telegram chart वर Abhi चं स्वीकारलेलं वाचन — घन impulse, "not verified" मजकूर नाही; तो तपशील फक्त debug | नोंदी `decision3/data/accepted_legs.json` (symbol, timeframe 1D, from / to तारखा, reading impulse, direction, source; env `DECISION3_ACCEPTED_LEGS` ⇒ दुसरी file). जुळवणं: काढलेल्या trend leg ची स्वतःची pivot टोकं (from / to bar) ± `daily_pivot_n` (2) sessions + दिशा तीच — pivot च्या n-bar खिडकीत त्याच प्रकारचा दुसरा pivot नसतो ⇒ जुळणं एकाच pivot शी; किंमत कधीच नाही. जुळला ⇒ घन, legend **"impulse"** (verified 5 waves आणि स्वीकारलेलं एकाच दिसण्याचे ⇒ एकच legend ओळ; मूळ JSON / debug मध्ये). BANKNIFTY 3 Feb → 2 Apr: structure vote zigzag n 9 तसाच (JSON `check`), chart वर घन impulse. Default मध्ये "not verified" कुठेच नाही (title, caption, legend, chart मजकूर); debug PNG / JSON `trend_line_debug` / `objects.impulses[].check` = "impulse not verified (structure vote: …; anatomy vote: …) · accepted by Abhi as impulse (source: …)"; Vision facts = chart जसा दिसतो (prompt v4) | legend "impulse (accepted reading)" वेगळी ओळ |
| CD14-B | Verified नाही आणि स्वीकारलेलाही नाही असा trend leg default chart वर कसा? | पातळ dashed नारंगी, legend "trend leg" (तटस्थ; "not verified" शब्द नाही); title / caption "new decline in progress" — impulse दावा नाही (BANKNIFTY चालू Jun → Sep leg: flat, n 13) | सगळे trend legs घन (Abhi ला dashed नको असेल तर) |
| CD14-C | Debug मधला "anatomy vote" | आत्ता "anatomy vote: not run" — हा chart reader2 चालवत नाही; leg वर `anatomy` ({lean, score}) असेल तर तो दाखवतो | reader2 `anatomy.leg_vote` Daily chart builder मध्ये जोडणं (वेगळा PR) |
| CD14-D | स्वीकारलेल्या नोंदी कुठे? | Repo (public) मध्ये — या नोंदीच्या तारखा आधीच docs मध्ये (Q49-BN / CD14); पुढच्या नोंदी private हव्या असतील तर `DECISION3_ACCEPTED_LEGS` ⇒ trade-data file | सगळ्या नोंदी trade-data मध्ये |
| CD14-E | Reader v2 gallery मध्ये हा leg Abhi-labelled impulse (dev) | या PR मध्ये नाही — trade-data `cb91e66` मध्ये CD14 seed label आधीच आहे; anatomy vote असहमत ⇒ calibration case (label Abhi चं) | — |

| LB12 | MCX (L4) trend इतिहास | सध्याच्या front-month contract चे Daily candles (Upstox कडे expired contracts नाहीत) ⇒ roll नंतर < 30 bars ⇒ "trend unclear", entry नाही | continuous MCX series (उदा. spot / स्वतःचा roll-stitched इतिहास) हवा का? |
| LB13 | MCX SL cap | structural SL > settings `sl_points` (default 20) ⇒ `SKIPPED_GATE_SL_TOO_WIDE` — GOLD / SILVER वर बहुतेक structural SL यापेक्षा रुंद ⇒ बहुतेक skip | MCX साठी cap वाढवायचा की structural SL ⇒ lots कमी? |
| LB14 | MCX Supertrend filter | confirmation mode मध्येही Supertrend / cascade / cooldown / max hits चालू (फक्त breakout, candle-confirm, min-hold बंद; RSI default बंद) | Supertrend confirmation मध्ये बंद करायचा? |
| LB15 | MCX approval | CONFIRMED ⇒ जुना PAPER order मार्ग (Vision / §9 Telegram ✅ नाही — आधीसुद्धा MCX PAPER approval शिवाय होता) | MCX ला §9 approval हवं का? |
| LB16 | L5 signal_log मध्ये bot column नाही | 5M Instant आणि Classic दोघे 5M levels च्या सारख्याच rows लिहितात ⇒ dashboard मध्ये 5M rows दोन्ही bots खाली (caption), summary मध्ये "5M levels (Instant + Classic)" एक ओळ; touch-legacy संख्या bot-wise अचूक | signal_log ला bot column (hit मोजणी / page filters ला हात) — हवं का? |
| LB17 | L5 MCX दृश्य | MCX signal_log level_type फक्त SUPPORT / RESISTANCE (30M / 60M TF नाही) ⇒ सारांश / dashboard मध्ये area = (symbol, किंमत); MCX symbols = सक्रिय (symbol_enabled) commodities; वापरलेली confirmation फक्त MCX साठी file मध्ये (index bots ला Vision ✅ आहे) | MCX signal_log मध्ये TF हवा का? index bots ना पण तसाच confirm-used guard हवा का? |

| VP1 | Volume pane: "window avg" कोणत्या bars ची? | commitment **आधीचे** study-window bars [arrival, commitment) — decision3 c0 (`commitment(win=)`) चीच व्याख्या; trend-side / counter-side × सुद्धा त्याच सरासरीशी | commitment सकट पूर्ण window |
| VP2 | V22 rows मध्ये study window (arrival bar) नाही | chart helper evaluate चाच arrival नियम (area overlap + आधीचा close approach बाजूला) 15M bars वर लावतो, कमाल 48 bars मागे; JSON `volume.computed` मध्ये नोंद. a2 / c0 / c1 decision3 मध्ये आल्यावर engine चं window | K open bar पासून |
| VP3 | जुने (2015–2024-03) setups: intraday futures volume नाही (expired contracts Upstox कडे नाहीत) | 15M / 5M pane "volume: NA (grade cap B)"; Daily pane = NSE bhavcopy near-month FUT (contracts, 2018-12 पासून); setup दिवसाचा अर्धवट bar NA (पूर्ण-दिवस bhavcopy = भविष्य; दुसरं एकक मिसळत नाही) | जुना futures 1m डेटा विकत / दुसरा स्रोत |
| VP4 | 5M (lower TF) pane वर कोणता bar खूण? | c1 output मध्ये CHoCH bar असेल तर तो ("CHoCH bar vol ×"), नाहीतर setup bar चा शेवटचा 5M bar; window = 15M arrival पासूनचे 5M bars | setup bar चे तीन 5M bars एकत्र |
| VP5 | 1H level chart (`h1_png`) ला volume pane? | नाही — spec फक्त 15M, lower TF आणि Daily सांगतं | 1H ला सुद्धा |
| VP6 | Daily volume एकक: Upstox futures = quantity, bhavcopy = contracts | bhavcopy मध्ये lot_size (udiff, 2024 नंतर) ⇒ quantity (contracts × lot) आणि setup दिवस futures मधून; lot_size नाही ⇒ contracts, setup दिवस NA | नेहमी contracts (quantity ÷ lot) |

| OB1 | One bot: FUT volume नसेल तर | front-month FUT 5M volume (SENSEX = BSE) नाही ⇒ volume NA (c0 चालतं, grade कमाल B) — fail-closed नाही; फक्त 5M spot (LTF, c1) नसेल ⇒ fail-closed | ठीक? (review नंतर बदल: आधी FUT नसेल तर symbol दिवसभर बंद होता) |
| OB2 | One bot: engine setup ची मुदत | `pending_entry` = `engine_max_age_min` (30) मधला सर्वात नवा न-वापरलेला setup — पुढचा 15M bar "wait" असला तरी ✅ ची वाट चालू; नवी "error" row ⇒ नाही | 30 मिनिटं ठीक? |
| OB3 | One bot: auto traders | oi_signal / credit_spread / oi_greeks ना settings flag नाही ⇒ installer त्यांच्या PAPER cron ओळी comment करतो (`#one-bot-off# `), LIVE ओळ नाही | या bots ना dashboard वर `symbol_enabled` हवा का? |


## Telegram cleanup (TRADE_SESSION_TELEGRAM_CLEANUP 1–3, ONE_BOT §4) — घेतलेले default निर्णय (Abhi ने बदलावे)

> **status (2026-10-21):** standing operational defaults (no answer recorded) → listed in Still open.

| # | प्रश्न | आत्ता (default) | पर्याय |
|---|---|---|---|
| TG1 | अनोळखी review kind | allowed यादीबाहेरचा kind ⇒ नकार (fail-closed), `--force` ने जातो | फक्त debug kinds नकार, बाकी जाऊ द्या |
| TG2 | Setup audits (`v22_setup`) | run ला "debug" tag नसेल तरच जातात — "audit झाल्यावर, फक्त निर्णय लागणारे" हे manifest बनवणाऱ्याने निवडायचं | manifest मध्ये "audited" tag बंधनकारक |
| TG3 | Review charts ची निर्णय ओळ | "Decision needed: reply ✔ (engine right) or ✘ + reason" | "approve / reject" शब्द |
| TG4 | साध्या ओळींची भाषा | English (Abhi चं उदाहरण); details मधला जुना मराठी / codes मजकूर तसाच | मराठी साधी ओळ |
| TG5 | 15:45 "जवळचा area" | ACTIVE zones (1M–60M bot TFs), 15:45 ला; आज तुटलेला area दिसत नाही; high / low = Upstox 15M (VPS token) | फक्त 15M+ TFs / आज तुटलेले सुद्धा |
| TG6 | Pre-open engine ❌ | signal source engine / both असलेल्या symbols साठी engine store चा शेवटचा computed_at नाही किंवा 96 तासांपेक्षा जुना ⇒ ❌ | 09:00 ला कालच्या 15:00 bar ची सक्ती (सुट्टी कॅलेंडर लागेल) |
| TG7 | Pre-open "चालू bots" यादी | 15M SRv2, 5M Instant, SR V3 shadow, Classic SR (symbol_enabled — bots चेच defaults) + MCX सक्रिय commodities. Vision shadow / oi_signal / credit_spread traders या ओळीत नाहीत | त्यांचेही flags वाचणे |


## Trend first — setups audit (TRADE_SESSION_DECISIONS_SENSEX_SETUPS_CD14 §2) — default निर्णय (Abhi ने बदलावे; अहवाल `docs/reports/setups_prA_v1_audit.md`)

> **closed (2026-10-21):** TF2 is Abhi's own rule ("structure UP ⇒ never a bear call"); TF1 / TF3–TF5 / TF7 (audit of the PR A setups) → layer 1 ✅ (L1-a / L1-b); TF6 → dormant (level bots, ATP). D12 table below: D12-1 → B1; D12-2 → L4-g (a line alone is not an entry); D12-3 → TA3 / L4-a; D12-4 → EC2; D12-5 → EC1; D12-6 → L6-a (confluence is a confirming piece).

| # | प्रश्न | आत्ता (default) | पर्याय |
|---|---|---|---|
| TF1 | Trend-first gate ची "Daily रचना" कोणत्या swings वर? | Daily swings (seq, N = 2 — spec ①, flip (अ) सारखेच) — counter-move same-degree correction (phase correction / origin_broken) असताना: impulse टोकानंतर HL (UP ⇒ LH) + मधल्या swing पलीकडे close + impulse-स्वभावाचा पाय (Q29 / Q36) ⇒ `DState.rev` ⇒ trend-बाजूचा trade नाही (trend / protected बदल नाही) | Q22 ने गाळलेले trend-degree swings — NIFTY 2020 rally तिथे एकच पाय ⇒ defect राहतो (पडताळलं: rev दिवस 62, 2020 नाही) |
| TF2 | zigzag चा c, a च्या टोकापलीकडे close (b = HL) ⇒ Dow रचना UP ⇒ c-top bear call अडतो (HL wick ने तुटेपर्यंत / नवा LL होईपर्यंत; close परत a टोकाखाली आला तरी — PR #305 review) | अडतो (Abhi: "structure UP असताना bear call कधीच नाही"). NIFTY 633 / 2,282, BANKNIFTY 716 / 2,479 दिवस trend-बाजू बंद (सगळे correction phase); 30 पैकी फक्त 2020-11-04 ×2 वर परिणाम | counter-move impulse वाचला तरच अडवा — पण read_counter ने 2020 zigzag वाचलं ⇒ defect राहतो |
| TF3 | Audit rule (126 sessions, N = 5 swings, शेवटचे दोन H / L) हाच Abhi चा "6-month structure"? | अहवालात rule चं वाचन (निकाल पाहण्याआधी जाहीर) | दुसरा rule |
| TF4 | 2019-09-03, 2022-03-28 ×4: engine UP (Q45: A1 correction counter-move च्या शेवटच्या N = 2 LH पलीकडे close ने संपली) वि. rule DOWN (N = 5 LH टिकलेला) | बदल नाही (T1 — engine degree) | T2: gate audit rule सुद्धा वाचतो ⇒ 9 FAIL rows जातात, 19 उरतात — पण नवी swing degree (N = 5) |
| TF5 | rule-ambiguous rows (equal lows / आधीच तुटलेलं DOWN वाचन): 2015-08-10, 2022-01-20, 2022-03-14, 2022-11-15 | FAIL* (Abhi confirm) | प्रत्येक row Abhi |
| TF6 | Level bots ला तोच gate (`structure_against` ⇒ नवे entries नाहीत) | हो (shared ① gate, fail-safe) | फक्त V22 |
| TF7 | §2 a–f audit columns (diagnostic, `scripts/setups_audit_columns.py`): (a) 15M N 3 / 5 sessions, 1H N 2 / 20, Daily N 2 / 126 + तुटलेले Daily lows; (b) edge touch = ≤ 2 candles + near half; (d) provisional = engine `prov` stack (why-trail वरून, अंदाजे); 2015–2024 ला futures volume नाही ⇒ NA | तसेच (फक्त अहवाल; engine बदल इतर branches वर) | Abhi च्या व्याख्या |

| D12-1 | Maturity (Abhi 12 Oct: पुरावा फक्त, "कमाल एक पायरी खाली") — B setup चं काय? | रचना अखंड ⇒ A ⇒ B, B तसाच (B ⇒ weak केलं तर maturity ने entry अडते — owner नियमाविरुद्ध); रचना अखंड नाही ⇒ जुना cap weak | B ⇒ weak (म्हणजे mature + B ⇒ वाट) |
| D12-2 | फक्त तिरक्या trendline वरून reversal (horizontal level नाही) — area? | नाही: spec ② level जन्म (a)–(d) च; रेघ फक्त horizontal level शी confluence असेल तर area (overlap पट्टा, births + `tl`) | रेघ एकटी area, grade कमाल B |
| D12-3 | तिरकी रेघ किती स्पर्श? | 2 (anchors; `tl_min_touches`) — spec "पक्की ≥ 3" = माहिती (`tl.touches`) | ≥ 3 आवश्यक |
| D12-4 | पुरावा-खिडकी (`evidence_start`) | 09:15 (सत्राची सुरुवात) — opening candle 2-candle form / संदर्भ म्हणून; entry खिडकी 09:30 … 15:15 तशीच | entry_start (जुनं) |
| D12-5 | ⑦ target 12-Oct सारख्या case मध्ये: sweep वर SL + जवळचा support target ⇒ R:R < 3 शक्य | Q14 तसाच (I_end / जवळचा जिवंत level — जो जवळ); बदल नाही | पहिला target जवळचा level, R:R I_end वर (areas-quality branch) |
| D12-6 | Trendline confluence ने grade वाढावा का? (spec ② "trendline रेघ तिथे (+)") | नाही: confluence area चा ★ / conviction parent level इतकाच; `tl_confluence` फक्त पुरावा-नोंद (वजन नाही). Area फक्त ② च्या active (जवळचे `active_levels_max`) levels वरून, किंमतीच्या योग्य बाजूला; p2 नंतर close रेघेपलीकडे ⇒ रेघ नाही | `tl_confluence` ला evidence वजन (उदा. `level_star` सारखं) |

## Touch / levels audit (TRADE_SESSION_TELEGRAM_CLEANUP §4–§5, one-bot §7(e)) — `docs/reports/v22_missed_levels_touch.md`

> **closed (2026-10-21):** TL1 answered; TL2 / TL3 → Z-1u (each zone from its own base / reaction candles, never merged or widened); TL4 → Z-1p.

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| TL1 | **✅ Abhi मंजूर (2026-10-12): default `level_death_side` = "role"** (Q2 बदलला; "role0" फक्त revert / what-if). **Q2 पुन्हा (9 Oct blind spot):** flip झालेला level कधी मरतो? 9 Oct: तुटलेला support (22,476–22,809 आणि weekly 22,518–22,527) 1 Oct / 8 Oct ला resistance झाला (3 closes, बरोबर), पण 8 Oct 11:15 ला **खालचा** D2 L 22,397 close ने तुटला ⇒ मूळ भूमिकेच्या (support) नियमाने मेला ⇒ 9 Oct (आणि 12 Oct ≈22,600) ला supply engine ला दिसली नाही. Downtrend मध्ये break ची पुढची धाव नेहमी खालचा swing तोडते ⇒ "तुटलेला support = supply" (spec ② (c)) व्यवहारात कधीच trade होत नाही | `level_death_side` = "role0" (जुना Q2 default, बदल नाही) | **"role" (शिफारस)** = चालू भूमिकेची बाजू: flipped supply फक्त वरचा D2 H close ने तुटला तरच मरते. Setting तयार + fixture (आरसा सह). What-if (NIFTY Sep–Oct 2026): setup 1 → 1, no_trade 118 → 142; 9 Oct ला दोन्ही supply दिसतात, 11:30 bar ला weekly 22,518–22,527 वर R:R 5.55 — फक्त maturity cap (weak) ने अडलं. बदल = एक settings ओळ |
| TL2 | (Abhi 2026-10-12: "आत्ता नाही" — merge नियम तसाच, प्रश्न उघडा) Merge (Q19) ने पट्टा फुगतो: 22,570–22,640 चं क्षेत्र 22,476–22,809 (333 pts) level मध्ये गेलं (bar 0 ला Q40 prior Daily / Weekly पट्टे + नंतर D2 H 22,809 / BOS base / D2 H 22,732 — भूमिका वेगळी असूनही). इतक्या रुंद पट्ट्यावर SL वरच्या कडेपलीकडे ⇒ R:R < 1 (9 Oct 11:00 / 11:45: 0.99 / 0.74) | तसेच (Q19) | (a) फक्त समान भूमिकेचे merge (Q19 पर्याय); (b) merge फक्त पट्टा ≤ k × σ_1H राहत असेल तर (k Abhi ने ठरवायचा); (c) Q40 prior पट्टे आपापसात merge न करता वेगळे |
| TL3 | (b) BOS base: 8 Oct BOS चा origin = शेवटचा confirmed D2 H 22,732 (6 Oct) ⇒ base 22,715–22,724. धाव प्रत्यक्ष 7 Oct 14:15 (22,649, D0) / 8 Oct open 22,599 पासून सुरू झाली — तो D2 swing नाही (degree filter: "लहान pivot पासून level नाही") | तसेच (Q4 / spec ② (b)) | 1H साठी Q55 सारखा "sharp-fall base" (धाव सुरू करणारी candle) — Daily `sharp_zone` चा 1H आरसा |
| TL4 | a2 handover (`zone_study`) — trend-बाजूचा पहिला अर्धा रिकामा (29 Sep: 11:00–12:00 सगळ्या greens, 12:15 पहिली red) ⇒ `trend_growing` NA ⇒ `handover` False, जरी buying candles दमल्या (counter_weakening ✔) आणि 12:15 dominant engulf | तसेच (बदल नाही — `claude/v22-confirmation` चा भाग) | रिकामा पहिला अर्धा + दुसऱ्यात trend candle ⇒ "growing" ✔ |

## Abhi निर्णय 2026-10-13 — entry candle + R:R (one bot; branch `claude/entry-candle-sl`)

> **closed (2026-10-21):** EC1 / EC2 / EC6 answered. EC3 → layer 3 (the commitment is the dominant candle after the handover; its volume vs the approach leg across the gap — L3-c, L3-c2, L3-e; golden 12 Oct 09:30); EC4 → L3-h (two-candle forms span sessions; a gap is the next candle); EC5 → no option left (c1 unchanged).

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| EC1 | **✅ Abhi मंजूर (2026-10-13): "R:R removed from the engine; R:R is Abhi's own judgement at approval; SL/target from dashboard (Abhi 2026-10-13)".** (त्याच दिवशीचे आधीचे टप्पे — entry-candle spot SL + PAPER exit, मग R:R फक्त माहिती — Abhi नेच रद्द केले; exits ला हात नाही) | `rr_step` = False: checklist मध्ये ⑦ नाही; engine SL / target / R:R setup output, store row (entry / invalidation / target = NULL), approval ticket, 15M chart, replay मध्ये नाहीत; setup निर्णय ⑥ (commitment + c1) वर संपतो. `rr_step` = True = जुना ⑦ फक्त जुने reports / golden tests reproduce (dashboard वर नाही). `sl_mode` बनवलं नाही — फक्त R:R साठी होतं | — |
| EC2 | **✅ Abhi मंजूर (2026-10-13, 12 Oct chart):** 09:15 candle स्वतः entry (commitment) candle असू शकते — setup तिच्या close ला (bar_end 09:30), entry 09:30 | `entry_first_bar` = True (commitment खिडकी `evidence_start` 09:15 पासून); False = जुनं (09:15 फक्त पुरावा). Live: store row bar_ts = bar_end 09:30 ⇒ `engine_signal.in_window` (09:30–15:00) मध्ये; cron 09:31 IST पहिला run | — |
| EC3 | (उघडा) 09:15 candle हीच area मधली पहिली (arrival) candle असेल तर c0 चा study window = ती candle स्वतः ⇒ body 1.0× (< `commit_dom_mult` 1.5) आणि volume 1.0× (≤ 1) ⇒ "dominant नाही" ⇒ वाट. म्हणजे 12 Oct सारखा gap-up spike (आदल्या दिवशी area ला स्पर्श नाही) 09:15 ला setup होत नाही; आदल्या दिवसाच्या शेवटच्या ≤ `touch_window_bars` bars नी area ला स्पर्श केला असेल तरच. हाच नियम दिवसभर: arrival candle = commitment candle ⇒ c0 कधीच नाही | तसेच (c0 बदललेला नाही — निर्णय हवा) | (a) window फक्त commitment candle ⇒ तुलना मागच्या `candle_avg_n` (5) candles शी (आदल्या दिवसाच्या सुद्धा); (b) 09:15 volume ⇒ आदल्या दिवसाच्या सरासरीशी; (c) तसेच |
| EC4 | (उघडा) 09:15 commitment ची "मागची candle" = आदल्या दिवसाची 15:15 candle ⇒ close तिच्या close पलीकडे हवा; 2-candle forms (engulf / tweezer / star …) आदल्या दिवसाशी जोडत नाहीत (Q30 / `evidence_start`) ⇒ 09:15 ला फक्त pin / strong_close. Gap-up spike जो परत आला पण आदल्या close च्या वरच बंद झाला (synthetic 12 Oct fixture: close +20) ⇒ commitment नाही | तसेच | (a) gap दिवशी "मागची" = 09:15 चा open / आदला close + gap; (b) तसेच |
| EC5 | (उघडा) c1 (5M CHoCH by close) 09:15 candle मध्येच पूर्ण होऊ शकतो — फक्त 09:30 पर्यंत बंद 5M bars (09:15 / 09:20 / 09:25) + आदल्या दिवसाची 5M रचना (शेवटचा swing) वापरून: synthetic आरसा test मध्ये spike नंतर 09:25 चा 5M close आदल्या दिवसाच्या HL / LH पलीकडे ⇒ CHoCH ✔; close परत पुरेसा खाली नाही ⇒ "no close below HL yet" ⇒ वाट. c1 सैल केला नाही | तसेच | — |
| EC6 | **✅ Abhi (2026-10-13, branch `claude/rr-correction`): "Remove every R:R rule that came from Claude's orders. R:R, SL, target, lots and exits are his dashboard settings only."** (आधी: level bots स्वतःच्या ⑦ `min_rr` 3 ने ignore करायचे) | Level gate: ⑦ (R:R < min_rr आणि "no target area") फक्त dashboard `gate_rr_gate_enabled` (default **बंद**) चालू असेल तर; बंद ⇒ skip / disarm / R:R ओळ / इशारा नाही. ✏️ Modify आणि ✋ /paper: R:R इशारा काढला (R:R आकडा फक्त माहिती). Setups audit (a): R:R verdict काढला, फक्त तथ्य | dashboard वर `gate_rr_gate_enabled` चालू ⇒ जुना नियम |

## R:R correction (branch `claude/rr-correction`) — उरलेले प्रश्न (Abhi ने ठरवावे)

> **closed (2026-10-21):** RR1–RR3 answered; RR4 → EC1 (no engine target by default; facts only); RR5 → dormant (simple_core, no execution); RR6 → dormant (the R:R gate lives in the level gate, `bots_common/level_reaction.py` — level bots, ATP).

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| RR1 | **✅ Abhi निर्णय (PR #316): MCX चे SL / target पूर्णपणे dashboard settings चे; confirmation gate फक्त entry हो / नाही ठरवतो.** (आधी: gate चा structural SL, settings SL कमाल; target = पुढचा उलट area) | `mcx_futures_trader`: gate SL / target कधीच set / cap करत नाही — `SKIPPED_GATE_SL_TOO_WIDE` / `_TARGET_PASSED` / `_INVALIDATED` (gate किंमतींवरून) नाहीत; SL / target = `_sl_target_points` (+ dashboard चे candle-confirm SL / next-level target पर्याय). R:R gate (default बंद) चालू ⇒ dashboard SL / target वर (`_gate_rr_skip`); gate (level_reaction) ला MCX साठी R:R कधीच नाही | — |
| RR2 | **✅ Abhi निर्णय (PR #316): ticket = dashboard SL / target; engine SL / target दाखवले तर "engine reference (info)" असं स्पष्ट लेबल, नाहीतर काढा — लहान बदल निवडा.** | निवड: **लेबल** (काढणं मोठं — ✏️ Modify ला entry तपासणीसाठी तोच SL लागतो, chart रेषा, tests). Caption: "Entry … · engine reference (info): SL … · target …" + "Trade SL / target: dashboard settings"; dashboard / log ओळ (`describe`), Vision chart ("ENGINE REF SL / TARGET"), Vision audit prompt, ✏️ Modify ticket (src engine) — सगळीकडे तेच लेबल | — |
| RR3 | **✅ Abhi निर्णय (PR #316): "no target area" = स्वतंत्र dashboard setting, default बंद.** | `gate_no_target_disarm_enabled` (level_reaction `no_target_disarm_enabled`, default False), `gate_rr_gate_enabled` पासून स्वतंत्र; दोन्ही पानांवर (Bot Dynamic SR Algo, MCX) R:R checkbox शेजारी. R:R gate चालू पण target area नाही ⇒ R:R मोजता येत नाही ⇒ R:R skip नाही (target नसण्याचा निर्णय फक्त या setting चा) | — |
| RR4 | Setups audit (a) मधला target = V22 run चा (फक्त legacy `rr_step` = True मध्ये असतो; default run ⇒ "no risk") — dashboard target वापरायचा? | तसेच (verdict नाही, फक्त तथ्य) | audit script ला dashboard target (points / %) input |
| RR5 | `simple_core` PAPER_SEED मध्ये `rr_filter` = True, `min_rr` 3 (research / backtest review पान; live execution नाही — `bots_common/one_bot`: "simple_core (execution नाही)") | तसेच (live नाही ⇒ हात नाही) | seed मध्ये `rr_filter` False |
| RR6 | NSE options bots (5M Instant / Classic / 15M SRv2): dashboard R:R gate **चालू** केल्यास तो engine चा reference SL (area च्या पलीकडे + buffer) आणि पुढच्या area चा target (spot) वापरतो — कारण त्या bots चे dashboard SL / target option premium / P&L वर आहेत (spot अंतर नाही). हे चालेल का? (gate default बंद ⇒ आज परिणाम नाही; trade चे SL / target नेहमी dashboard चेच) | तसेच (पानावर caption) | R:R gate options bots साठी लपवायचा; किंवा spot मध्ये वेगळे dashboard SL / target अंतर देऊन त्यावर R:R |

## Data / pre-open fixes (13 Oct VPS findings) — घेतलेले default निर्णय (Abhi ने बदलावे)

> **status (2026-10-21):** standing operational defaults (no answer recorded) → listed in Still open.

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| DP1 | Futures collector ला SENSEX (BSE FUT) default मध्ये? | हो — `--symbols NIFTY,BANKNIFTY,SENSEX`; BSE front-month FUT सापडला नाही ⇒ ℹ️ log + skip (exit 0, बाकी symbols चालू) | SENSEX फक्त `--symbols` ने स्पष्ट दिल्यावर |
| DP2 | Replay (`--source upstox`) चा FUT volume स्रोत | collector file मध्ये दिवस D असेल तर ती; नाहीतर `feed.futures` (front-month as of D+1 — expiry दिवशी पुढचा contract असू शकतो, contract छापला जातो) | नेहमी feed (live engine सारखं) / नेहमी file |
| DP3 | Pre-open: आज engine row नाही + cron आहे — ℹ️ कधी? | (review #313) 09:45 IST पर्यंत, **आणि** मागच्या trading session (weekday − config सुट्ट्या) चा किमान एक row असेल तरच ℹ️; नाहीतर ❌ "engine did not run in the last session — check engine_signal.log". 09:45 नंतर row नाही ⇒ ❌ | ℹ️ फक्त 09:31 पर्यंत / stale row ला पण ℹ️ |
| DP4 | 09:45 नंतर "आज row नाही" पण कालचा row आहे ⇒ ❌? | नाही (बदल नाही — सुट्टीच्या दिवशी manual run ला खोटा ❌ टाळला); फक्त store पूर्ण रिकामा ⇒ ❌ | trading day + 09:45 नंतर आजचा row नाही ⇒ ❌ |

## Trendline / area audit 2026-10-13 (`docs/reports/2026-10-13_trendline_area_audit.md`) — Abhi निर्णय हवे (code बदल नाही)

> **closed (2026-10-21):** TA1–TA4 answered (below). TA5 → layer 4 (a line is gone only by a close beyond AND a swing beyond — L4-d; time never removes it — P2).

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| TA1 | Chart वर फक्त K6-valid रेघा? (≥ 3 wick touches, spacing, मधे close-through नाही, slope ≤ 0.5 MR/bar, real break नाही, शेवटच्या 2 sessions मध्ये touch) — आज 153 पैकी 8 valid | तसेच (audit फक्त; सगळे drawers जसेच्या तसे) | (a) सगळ्या charts वर फक्त valid, TF मागे कमाल 2, label "N touches"; (b) invalid फिकट + कारण; (c) तसेच |
| TA2 | K6 spacing: 6 की 8 bars? (KB "6–8"; या sample मध्ये verdict सारखाच — दोन्हीने 8 valid; < 8 फक्त BANKNIFTY 1H trendlines2 च्या 13 रेघांत, त्या आधीच stale) | audit दोन्ही दाखवतो; trendlines2 `min_spacing` 6 | 6 / 8 |
| TA3 | V22 `tl_min_touches` 2 ⇒ 3? (K line / swing line सगळ्या 2 स्पर्शांच्या; K6 ≥ 3). निर्णयावर परिणाम (⑤ पुरावा, "+TL" area) वेगळा मोजावा लागेल | 2 (Abhi नियम "K ≥ 2 स्पर्श") | 3 फक्त chart साठी / 3 engine मध्येही |
| TA4 | SR V3 आणि Vision majors एकच किंमत (line) काढतात — K4 "zone, line नाही". Band कसा? | तसेच | (a) wick–body पट्टा (V22 `_band_swing` सारखा); (b) ± अपूर्णांक × MR; (c) तसेच |

**TA1–TA4 ✅ Abhi निर्णय (2026-10-13):** TA3 (दुरुस्त) — valid रेघ = 2 स्पर्श (3रा projected स्पर्श = trade जागा; ≥ 3 = "established");
TA3b — horizontal: एकाच किंमत-पट्ट्यावर 2 reaction स्पर्श (मधे किंमत पट्टा सोडून गेली, ≥ 6 bars) = valid S/R पट्टा, break नंतर role flip;
TA4 — area म्हणजे पट्टा (low–high), एकच किंमत नाही; तुटलेले areas invalid, फक्त सर्वात नवा तुटलेला सोडून; TA2 — spacing फक्त 6 bars.
Re-run: अहवाल §8 (रेघा 153 पैकी 24 valid, 8 established; areas 1,485 पैकी 310 valid). Code (drawers) मध्ये अजून बदल नाही.

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| TA5 | "Recent price ने मान" (शेवटच्या 2 sessions मध्ये touch) 2-touch नियमाशी टक्कर देतो: projected 3ऱ्या touch ची वाट पाहणारी रेघ बहुतेक 2 sessions touch शिवाय असते. Re-run मध्ये 44 रेघा फक्त याच नियमावर गळल्या (31 "touch नाही", 13 broken); 30 Sep → 6 Oct golden रेघ 9 Oct close ला फक्त यामुळे लपली असती (12 Oct 09:15 ला तिचा touch 22,654 वर) | audit मध्ये तसाच ठेवला (Abhi: "keep as defined") | (a) फक्त real break (K5) ठेवा, "2 sessions touch" काढा; (b) touch-window = रेघेच्या स्वतःच्या touch-spacing च्या × k; (c) तसेच |

## R1 (a) — shared line / band checks (branch `claude/r1a-lines-bands`; `facts/validity.py`) — घेतलेले default निर्णय (Abhi ने बदलावे)

> **status (2026-10-21):** chart / band display checks → listed in Still open (layer 6, output); R1a-13 (`vision_chart_bands`) is Abhi's switch → Still open.

TA5 अजून उघडा ⇒ shared line check मध्ये "शेवटच्या 2 sessions मध्ये touch" नियम **लावलेला नाही**. Decision3 चा निर्णय / कोणताही bot gate बदललेला नाही (फक्त charts).

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| R1a-1 | TF वर 2 पेक्षा जास्त valid रेघा ⇒ कोणत्या 2 दाखवायच्या? (audit मध्ये cap फक्त एकदा लागला: BANKNIFTY 15M, 3 रेघा) | जास्त spaced touches आधी; बरोबरी ⇒ शेवटचा touch जास्त ताजा; मग लांब रेघ (`rank_line`); बाजू (वर / खाली) वेगळी नाही | (a) ताजा touch आधी; (b) एक resistance + एक support; (c) projected touch किंमतीच्या सगळ्यात जवळ |
| R1a-2 | K6 व्याख्या "uptrend मध्ये lows, downtrend मध्ये highs": highs मधून चढती / lows मधून उतरती रेघ = channel कड, trendline नाही — validity नियम? | हो, `trend_direction_only` (reason `against_trend_direction`); audit re-run मध्ये एकाही engine रेघेला लागला नाही (finder मधल्या दूरच्या रेघा गळतात) | बंद (setting) |
| R1a-3 | Anchor कोणता? 6 bars पेक्षा जवळचे pivots = एकच touch | त्या reaction चं टोक (highest high / lowest low) — रेघ wicks वरून, आरपार नाही (golden: 6 Oct 14:00, 12:45 नाही) | पहिला pivot |
| R1a-4 | Band ची कडा (low–high) reaction candles वरून कशी? | swing highs ⇒ [उंच body-top (खालच्या high पर्यंत मर्यादित), उंच high]; lows ⇒ आरसा. रुंदी > 1.5 MR ⇒ invalid (कापत नाही) | (a) पूर्ण candle; (b) टोक ± अपूर्णांक × MR |
| R1a-5 | "Broken" band ची व्याख्या | शेवटची घटना K5 real break आणि नव्या बाजूने < 2 touches ⇒ broken (invalid; chart वर फक्त सगळ्यात ताजा dashed); नव्या बाजूने 2 touches ⇒ पुन्हा valid ("flipped") | audit §8 सारखा: पहिल्या touch नंतर कधीही acceptance ⇒ broken |
| R1a-6 | K5 magnet (दिवसात ≥ 4 close-crossings) band invalid करतो का? (TA1–TA4 मध्ये नव्हता) | हो (`magnet_invalidates`, KB K5 "no-trade level"; audit 2-touch run सारखा) | फक्त खूण, invalid नाही |
| R1a-7 | Projected touch zone रुंदी: ± 0.2 MR (K6 touch). 12 Oct 09:15 FUT high रेघेच्या 0.27 MR वर (zone बाहेर, close परत खाली = K5 sweep); spot high zone मध्ये | ± 0.2 MR; बदल नाही (golden test FUT साठी "touch किंवा K5 sweep" तपासतो) | (a) ± 0.25 MR; (b) zone = touch + sweep पट्टा (0.1–1.0 MR पलीकडे, close आत) |
| R1a-8 | FUT "≈ 22,667 supply" कोणता band? Data: 22,620–22,665 (9 Oct 11:15 / 14:15 reactions, flipped) — रेघेला 12 Oct 13:45 ला भेटतो (0.49 MR), 09:15 ला नाही (1.14 MR दूर). 09:15 ला confluence 22,729–22,761 (7 Oct 11:00 / 14:15) शी | Rule जसा तसा; दोन्ही अहवालात (audit §9); golden test: ≈ 22,667 band + रेघ confluence 12 Oct वर, आणि 09:15 ला कोणत्यातरी supply band शी | Abhi ने band चे reaction bars सांगावे |
| R1a-9 | Decision3 1H chart: engine चा active level band check fail करतो तेव्हा? | तरीही दाखवतो (निर्णय त्यावरच), label "fails band check: …" | लपवा (फक्त debug) |
| R1a-10 | Confluence: रेघेचा anchor हाच band चा touch असेल तर? | confluence नाही (स्वतंत्र साधनं नाहीत; KB टप्पा 3) | मोजा |
| R1a-11 | Setup chart वरची V22 K रेघ तुटलेली असते (break = trigger, K6.5) — TA1 "फक्त valid" मध्ये? | K6 गुणवत्तेचे नियम (wick, spacing, close-through, slope, दिशा) pass ⇒ दाखवते, label "broken HH:MM"; बाकी फक्त debug | तुटलेली रेघ लपवा |
| R1a-13 | Vision approval chart वर bands (TA4) चालू करायचे? Setting `vision_chart_bands` (per bot): ON ⇒ M1 / M2 एकच-किंमत रेषा नाहीत, shared band check चे पट्टे (supply नारिंगी, demand फिकट निळा — L च्या हिरव्या / लाल पासून वेगळे; ताजा broken तपकिरी-राखाडी dashed) आणि signal text मध्ये "Chart note" legend + पट्ट्यांच्या अचूक किंमती. Vision SYSTEM_PROMPT (legend "thin blue lines M1/M2") बदललेला नाही | **OFF** (image main सारखीच, byte-for-byte तपासलं) — Vision चं वर्तन Abhi च्या मंजुरीशिवाय बदलत नाही | ON (bot-वार); ON करताना SYSTEM_PROMPT चा legend सुद्धा बदलायचा का? |
| R1a-12 | Dashboard "Trendline Gate" (`signals.detect_trendline`, polyfit) — gate आहे, बदलला नाही. Shared check: 86 पैकी 4 valid (79 anchors wick वर नाहीत) | बदल नाही (या PR चा scope फक्त drawing) | (a) wick-anchored `trendlines2.two_touch` ने बदला; (b) gate मधून काढा |

## R1 (b) — facts dossier (branch `claude/r1b-facts-dossier`; `facts/dossier.py`, `facts/README.md`) — owners मधले मतभेद / नसलेले owners (Abhi ने ठरवावे)

> **status (2026-10-21):** dossier owner questions → listed in Still open (layer 6, output; L3-n); R1b-3 answered below.

Dossier कुठलाही मतभेद स्वतः सोडवत नाही: §3 चा owner जसा देतो तसा; इतर हिशोब फक्त "evidence" म्हणून नोंदवले.

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| R1b-1 | Trend चे अनेक हिशोब: swings2 D1 / D2 fold (owner) वि. reader2 चा leg-trend (`legs.reader2_trend`) वि. vision.gap_context चा SMA-10 trend (`gaps.trend`); decision3 चा Daily Dow dossier मध्ये नाही. R1a real data, 9 Oct close: swings2 D1 DOWN, D2 RANGE, D3 DOWN; reader2 15M "uncertain" | owner = swings2; बाकी फक्त evidence म्हणून दिसतात | (a) reader2 / gap trend dossier मधून काढा; (b) decision3 Daily Dow swings2 मध्ये merge होईपर्यंत तोही evidence म्हणून द्या |
| R1b-2 | PDH / PDL / PWH / PWL दोनदा: `context` (vision.context, 1m, ISO आठवडा) आणि `liquidity.pools` (decision3.liquidity, 15M, W-FRI आठवडा) | दोन्ही ठेवले (synthetic वर जुळले); §3 प्रमाणे context = owner | liquidity pools ने context च्या किंमती वापराव्या (merge टप्प्यात) |
| R1b-3 | FUT contract roll: volume owner (`opportunity_engine.volume.attach_futures_volume`) एका timestamp चे सगळे FUT rows बेरीज करतो; `legs2.volume.bar_volume` फक्त near-month ठेवतो | owner जसा (R1a FUT file मध्ये प्रत्येक timestamp ला एकच contract ⇒ फरक नाही) | volume owner मध्ये near-month filter (K10.3) — merge टप्प्यात |
| R1b-4 | Owner नाही: VIX, FII / DII, global cues (context `missing`); K11 चे box / flag / double top area मध्ये फक्त `decision3.method.zone_pattern` (candles.area_studies) मधून | NA म्हणून नोंद | vision_led मधून context owner मध्ये हलवा (§3); K11 patterns2 शी align (R1 नंतर) |
| R1b-5 | swings2 warm-up: σ ला 20 पूर्ण sessions + D2 ला 10 warm-up sessions ⇒ लहान इतिहासावर structure NA / D2 "unknown", तेव्हा decision3 Daily Dow (daily bars) कडे trend असतो | NA / unknown तसेच (silent pass नाही) | dossier ला Daily / Weekly इतिहास द्या आणि swings2 D3 / D4 त्यावर (merge टप्पा) |
| R1b-6 | Legs owner: design §3 म्हणतो reader2, पण reader2 research-only (gallery gate + Abhi ✅ होईपर्यंत production import मनाई — `tests/test_reader2_boundary.py`) | facts reader2 import करत नाही; `legs` default NA (कारणासह); research / test caller `cfg["legs_reader"] = reader2.reader.read` देतो | (a) R1 साठी facts/ ला boundary अपवाद (Abhi ✅); (b) gallery gate नंतरच legs; (c) तोपर्यंत legs2 / decision3.daily_legs |
| R1b-7 | Owners swings2 (`sigma_1h`, `structure._h1`) आणि rsi2 `pivots.charts` import करतात ⇒ `backtest_review.charts` ⇒ `vision_led.charts` (frozen package, फक्त plotting helpers). facts चा स्वतःचा code chart module import करत नाही (1H = `opportunity_engine.sessions.resample_nse`) | test: vision_led मधून फक्त `vision_led.charts`; बाकी frozen modules कधीच load नाहीत | owner merge मध्ये `agg_1h` / `daily_from_15m` non-chart module मध्ये हलवा |

## KB K11 chart patterns (branch `claude/kb-k11-patterns`, PR #317) — **निकाली: Abhi चे निर्णय 2026-10-13** (KB K11.0, K11.1, K11.7, K11.19; code बदल change control प्रमाणे)

| # | प्रश्न | Abhi चा निर्णय | पर्याय |
|---|---|---|---|
| KP1 | ~~G8 flag: `simple_core/flags.py:62` `breakout_ok` gate वि. "flag breakout वर entry नाही"~~ **निकाली (Abhi)** | Correction ची स्वतःची रेषा (flag / wedge / channel कड) **area वरच्या dominant commitment candle ने close-through** = valid trigger form. Entry कधीच नाही: area पासून दूर breakout, चाल निघून गेल्यावर पाठलाग, commitment candle शिवाय रेषा break. Minor swing / लहान trendline चा break एकटा = noise. G8 gate सुसंगत (code बदल नाही). T7 (`elliott/trigger.py`) code टप्प्यात एकत्र तपासायचा (KB K11.19 #10) | — |
| KP2 | ~~Flag लांबी: PT 4–20 वि. G8 2–11~~ **निकाली (Abhi)** | Flag लांबी = G8 चे 2–11 bars (setting); research चा 4–20 फक्त नोंद ⇒ `chart_reader/settings.py:62–63` change control ने | — |
| KP3 | ~~संपूर्ण counter-move wedge: ending वि. leading A~~ **निकाली (Abhi)** | Default वाचन **ENDING**; leading A फक्त alternate count (narrative) ⇒ patterns2 v1 `wedge_as_ending` बदल / निवृत्ती change control ने | — |
| KP4 | ~~Expanding wedge + `forming_wedge` position_ban~~ **निकाली (Abhi)** | Diverging wedge = broadening = **फक्त विरोधी पुरावा** (patterns2 दंड: change control). अपूर्ण / बनत असलेला wedge entry **अडवत नाही**; KP1 नियमाने तपासायचा (`forming_wedge` BAN_STATES बाहेरच — सुसंगत) | — |
| KP5 | ~~नवीन K11 patterns ना PT गुण~~ **निकाली (Abhi: "KB प्रमाणे")** | गुण नाहीत — फक्त नोंद / narrative; भाग D ची PT ओळ तशीच | — |

## Chart Reader R0 — Method Pack + Vision V4 checklist (branch `claude/r0-method-pack`) — Abhi निर्णय हवे

> **closed (2026-10-21):** answered (R0 ✅ below); R0-3 (Abhi's ✅ of the golden V4 drafts) → Still open.

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| R0-1 | Checklist items 1–7 म्हणजे नक्की काय? (design §12.2 मध्ये यादी नाही) | Method Pack sections 1–7: ① top-down trend · ② area · ③ trendline / channel · ④ correction · ⑤ zone study (handover) · ⑥ trigger (5M CHoCH by close + FUT volume वरची dominant commitment) · ⑦ never-list (`vision/checklist.py` ITEMS) | decision3 चे ①–⑥ (⑦ R:R बंद असल्याने 6 items) |
| R0-2 | Pack मधले 4 नियम KB च्या जुन्या मजकुरात नव्हते, आता KB मध्ये English pack blocks म्हणून आले: zone "dead only beyond the far swing" (Q2 / TL1), sharp-fall / sharp-rise point (Q55), handover candle वाचन (a2), trigger c0 + c1 (LEVEL_BOTS_CONFIRMATION). शब्द बरोबर आहेत का? | §12.1 मंजुरीनुसार तसेच (KB blocks 2, 5c, 6 — source सह) | शब्द बदला ⇒ KB block बदल + `scripts/build_method_pack.py` (pack version बदलतो) |
| R0-3 | Golden दिवसांचे अपेक्षित checklist वाचन (प्रत्येक item pass / fail / NA + verdict): 12 Oct NIFTY, 29 Sep NIFTY, BANKNIFTY a-b-c | सगळे TODO (`tests/fixtures/golden_vision_v4_cases.json`); run "TODO" दाखवतो, pass / fail ठरवत नाही | — (फक्त Abhi भरतो; अपेक्षा कधीच run नंतर बदलायची नाही) |
| R0-4 | BANKNIFTY a-b-c दिवस: नक्की decision bar, दिशा, data file? तुमचा case (Feb → Mar 2026 घसरण, a-b-c Jun 2026) NIFTY holdout तारखांत (2024-04 … 2026-06) येतो — runner चा guard सगळ्या symbols ना लागतो ⇒ तो दिवस नाकारतो | guard तसाच (holdout कधीच load नाही); 2026-07 नंतरचा BANKNIFTY a-b-c दिवस निवडा (BANKNIFTY intraday फक्त 15M ≈ Jul → Oct 2026) | BANKNIFTY ला CR-Q14 प्रमाणे अपवाद (code बदल + स्पष्ट मंजुरी) |
| R0-5 | 12 Oct आणि 29 Sep चा proposal area (spot band lo–hi) Vision ला द्यायचा का? | नाही (`area` TODO ⇒ "not given — judge the area"); 29 Sep 12:15 आणि 12 Oct 09:30 decision bars WORK_LOG / design §11 वरून | band द्या (anonymise होऊनच जातो) |
| R0-6 | भरलेल्या अपेक्षा कुठे? Repo public आहे (Abhi चे labels फक्त trade-data मध्ये) | repo मध्ये फक्त TODO template; भरलेली copy `/root/trade-data/golden_v4/cases.json` ⇒ `--cases` | repo fixture मध्येच भरा |
| R0-7 | Golden runner मध्ये futures volume नाही ⇒ items 5 / 6 चा volume भाग NA | NA (facts मध्ये तसं लिहिलं) | FUT 1m / 5M file option जोडा (anonymise सह) |
| R0-8 | Live V4 (`vision_v4_audit` = "v4"): V2 audit नंतर प्रत्येक signal ला एक जास्त call (≈ $0.03–0.05, pack cached / uncached) + एक Telegram संदेश (shadow mode ⇒ फक्त नोंद); cache TTL 5 मिनिटं | **off** (live मध्ये बदल नाही); golden runs नंतर Abhi ठरवतो — dashboard "vision_v4_audit" किंवा `python3 -m vision.config set _global vision_v4_audit v4 --by abhi` | on; TTL 1h (§8) |
| R0-9 | V4 ची दैनिक उप-मर्यादा `vision_v4_daily_cap` (review #318): किती? (V4 कधीच signals राखीव `signals_daily_reserve_usd` वापरत नाही; मासिक राखीव नियम visual audit सारखाच) | **$0.30 / दिवस** (≈ 6–8 V4 calls, pack cached / uncached) | dashboard वरून बदला (0–2) |

**R0 ✅ Abhi निर्णय (2026-10-13) — लागू (branch `claude/r0-method-pack`):**

| # | निर्णय | स्थिती |
|---|---|---|
| R0-1 | Checklist items = Method Pack चे 7 sections; decision3 शी ठरीव जोड: 1→① · 2→② · 3→⑤ · 4→③ · 5→④ + ⑥a2 · 6→⑥ c0 + c1 · 7→H1–H3 (design §12.2 तक्ता; `vision/checklist.py` `DECISION3_MAP`, प्रत्येक V4 निकाल / log row / golden निकालात) | ✅ निकाली |
| R0-2 | Handover + trigger शब्द ✅; sharp-fall / sharp-rise point ✅. 2-touch नियम (TA3 / TA3b) pack मध्ये स्पष्ट: रेषा / horizontal band 2 touches वरून, 3रा touch = trade location, ≥ 3 = established (minimum नाही). **"Zone dead only beyond the far swing" मंजूर नाही** ⇒ KB block मध्ये `pending Abhi`, generated pack मधून वगळला (pack version 4855ff77991f) | ✅ बाकी निकाली · **"zone dead" उघडा** |
| R0-3 | Golden अपेक्षा private trade-data `golden_v4/cases.json` मध्ये, status "draft — pending Abhi ✅"; Abhi ✅ होईपर्यंत प्रत्येक निकाल "PROVISIONAL" | ✅ निकाली (drafts लिहिले; Abhi ✅ बाकी) |
| R0-4 | BANKNIFTY दिवस: 3 उमेदवार (`trade-data/review/banknifty_abc_candidates/`) — Abhi एक निवडेपर्यंत golden फक्त 12 Oct + 29 Sep | ✅ निकाली (निवड बाकी) |
| R0-5 | Golden runner नेहमी FUT volume (`--futures`, default collector parquet); नाही ⇒ स्पष्ट "volume NA". W / D फक्त holdout-नंतरचा data (1 Jul 2026 पासून) + "item 1 limited history" नोंद | ✅ निकाली |
| R0-6 | भरलेल्या अपेक्षा private trade-data मध्ये (repo मध्ये फक्त template) | ✅ निकाली (R0-3 सोबत) |
| R0-7 | Golden मध्ये FUT volume | ✅ निकाली (R0-5) |
| R0-8 | Live V4 default off; Abhi golden निकालांनंतर ठरवतो | ✅ निकाली (off) |
| R0-9 | `vision_v4_daily_cap` = $0.30 / दिवस | ✅ निकाली |

## K-RSI — RSI divergence facts (branch `claude/rsi-divergence`; `rsi2.engine.Divergence`, KB K10.4 pending) — Abhi निर्णय हवे

> **closed (2026-10-21):** RSI-1 → L5-a (the pushes inside the move into the zone); RSI-2 answered (3 bars, below); RSI-3 → the EOD export has the full 13 Oct (`tests/test_decision3_flip.py::test_real_13_oct_no_bear_call`); RSI-5 → L6-a (the commitment's grade never caps; its form is a fact); RSI-6 → Z-1e (spot zone); RSI-7 → P2 (a gap is just the next candle); RSI-4 → Still open (tooling).

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| RSI-1 | "त्याच swing degree चे push" — कोणती swings2 degree? 12 Oct: फक्त D0 मध्ये 9-Oct push high (22,580.75) हा आधीचा H आहे; D1 / D2 मध्ये आधीचा H 7 Oct 22,717.65 / 6 Oct 22,731.85 (12-Oct 22,651.10 = lower high ⇒ divergence नाही) | D0, D1, D2 तिन्ही (`div_degrees`), प्रत्येक divergence ला degree; chart वर same pair एकच रेघ (D0/D1) | एकच degree (उदा. D0 = 15M push, D1 = 1H) |
| RSI-2 | 12-Oct spike high वि. 9-Oct push high (D0): price HH 22,580.75 → 22,651.10, RSI 67.09 → 66.41 (−0.68), पण **4 bars** (9 Oct 14:15 → 12 Oct 09:15; मध्ये 14:30, 14:45, 15:00 आणि रात्रीचा gap) ⇒ 15M window 5–50 च्या min मुळे नाकारली (grey "cap 4 bars"). Min 5 bars रात्रीच्या gap वरही लागू करायचा? | spec प्रमाणे 5–50 (tuning नाही); cap log मध्ये नोंद | min कमी / session-gap वेगळा मोजा — Abhi ✏️ नंतरच |
| RSI-3 | 13 Oct golden: export मध्ये 13 Oct फक्त 10:15 पर्यंत (oe_index 5M) ⇒ test skip; partial chart पाठवला (10:00 ला RSI 67.9, price 22,581 < 22,651 ⇒ lower high, divergence नाही) | skip + partial chart | पूर्ण दिवसाचा export (VPS) नंतर rerun |
| RSI-4 | Telegram reply ✏️: review listener फक्त ✔ / ✅ (OK) आणि ✘ (WRONG) ओळखतो; ✏️ नोंदला जात नाही | headline मध्ये ✅ / ✏️ (spec); ✏️ ऐवजी "✘ + काय चुकलं" लिहिलं तर नोंद होते | listener मध्ये ✏️ = WRONG (वेगळा PR) |
| RSI-5 | "Dominant commitment candle" = `decision3.method.commitment` (कोणताही ओळखलेला reversal form, close मागच्या close पलीकडे; grade A / B दोन्ही) | A आणि B दोन्ही confirm करतात (`status_by` + form / grade नोंद) | फक्त grade A |
| RSI-6 | Area fact spot 15M वर `decision3.levels.find_bands` (confirmation bar ला) — 22,667 zone FUT band आहे; spot band वेगळा येतो | spot (spec: structure / levels spot वर) | FUT band सुद्धा तपासा |
| RSI-7 | RSI window ± 2 bars रात्रीच्या gap पलीकडे जाते (उदा. 12-Oct 09:15 चा D1 / D2 RSI 9-Oct 14:45 च्या bar वरून 67.09) — फक्त pivot च्या स्वतःच्या swing आत | ± N bars, swing च्या आत, confirm bar पर्यंत | फक्त त्याच session मधले bars |

### Abhi निर्णय — FUT roll, BANKNIFTY दिवस, zone flip

> **closed (2026-10-21):** answered (Z-1 / Z-2 rows replaced by the final answers below).

| # | निर्णय | परिणाम |
|---|---|---|
| R1b-3 | Roll च्या दिवशी सुद्धा FUT volume = **फक्त near-month** contract (दोन contracts ची बेरीज कधीच नाही) | `opportunity_engine.volume.near_month_rows` + `attach_futures_volume(near_month=True)` (default False ⇒ जुने callers तसेच); facts dossier near-month वापरतो; KB K10.3 + pack 5b. ✅ निकाली |
| R0-4 | BANKNIFTY a-b-c golden दिवस: **सोडून द्या** | Golden फक्त 12 Oct + 29 Sep NIFTY; 3 उमेदवार charts trade-data मध्ये तसेच (हटवले नाहीत). ✅ निकाली |
| ~~R0-2 (zone)~~ (खालच्या अंतिम उत्तरांनी बदलले) | "Zone dead only beyond the far swing" **नाही**: तुटलेला zone **flip** होतो — मजबूत move (dominant commitment / displacement) ने तोडून **पुढच्या swing पर्यंत** पोचल्यावर; तसा नसेल तर sweep, zone जुनी भूमिका ठेवतो | KB K4 block (pending काढला) ⇒ Method Pack मध्ये (नवीन version). ✅ नियम निकाली |
| ~~Z-1~~ (खालच्या अंतिम उत्तरांनी बदलले) | Code: `decision3/levels.py` चा BROKEN / FLIPPED lifecycle या नियमाशी जुळवायचा (flip = strong move + next swing गाठला; नाहीतर sweep, भूमिका तशीच) | Abhi ने KB शब्द ✅ केल्यावर वेगळा PR (KB change control) — आत्ता code बदल नाही |
| ~~Z-2~~ (खालच्या अंतिम उत्तरांनी बदलले) | KB S4 / G4 आणि pack मध्ये "flip retest" हे नाव कोणत्याही real break नंतरच्या retest ला वापरलं आहे — Abhi च्या flip नियमापेक्षा सैल. नाव बदलायचं ("break retest") की G4 ला flip नियम लावायचा? | तसेच (pack मध्ये व्याख्या नाही, फक्त नाव) | Abhi ठरवतो |

### Abhi अंतिम उत्तरं (#322 नंतर) — flip नियम

> **closed (2026-10-21):** answered; Z-1 coded (next section).

| # | निर्णय | परिणाम |
|---|---|---|
| "strong move" | "strong" आणि dominant candle / displacement अर्थ **काढला**. Zone flip = price zone पलीकडे **आणि** पलीकडच्या बाजूचा swing पार; swing पार होणं हाच पुरावा, candle ची वेगळी अट नाही. तोपर्यंत sweep | KB K4 + pack. ✅ निकाली |
| Z-2 | (b) सगळीकडे एकच flip नियम (G4 सकट). BROKEN (swing पार नाही) ⇒ retest trade location नाही, थांबा. FLIPPED ⇒ swing वरून परत येणं = pullback, flipped area = trade location; entry आधी (a) pullback corrective (zigzag / flat / triangle), (b) एकूण कमी FUT volume (flip करणाऱ्या impulse पेक्षा; सुरुवात वाढत्या volume ने चालते), (c) area वर handover (a2) + dominant commitment जास्त FUT volume (c0) + LTF CHoCH (c1) + RSI divergence पुरावा. Impulsive / जास्त volume ने परत ⇒ trade नाही. G4 चं नाव "flip retest" = नेमकं हेच | KB K4 + G4 + pack. ✅ निकाली |
| Z-1 | decision3 BROKEN / FLIPPED code | वेगळा PR (fixtures: 12 Oct sweep, 13 Oct flip, 3 synthetic) |

### Z-1 code (decision3 BROKEN / FLIPPED, branch `claude/decision3-flip-state`) — निकाल + पुढचे प्रश्न

> **closed (2026-10-21):** Z-1, Z-1a, Z-1c–Z-1f, Z-1k, Z-1o (a) answered; Z-1g → L2-b; Z-1h / Z-1j / Z-1m superseded (rows say so); Z-1i → Z-1u (no merge across timeframes); Z-1n = a note; Z-1b → Still open (layer 6); Z-1l → standing default (Still open).

| # | प्रश्न / नोंद | सध्या code (default) | कोण |
|---|---|---|---|
| Z-1 | decision3 BROKEN / FLIPPED code | ✅ केलं (rework, Abhi अंतिम उत्तरं): BROKEN = trade location नाही; far swing पार ⇒ FLIPPED; FLIPPED पुन्हा far swing पार ⇒ DEAD; G4 (a) / (b) फक्त context; in-zone study (⑥ a2 + c0 + c1, RSI पुरावा) निर्णय; volume = slot-normalised per bar; FUT नाही ⇒ data problem. Live PAPER: 15M SRv2 engine मार्ग (engine3_live ⇒ V22) | ✅ निकाली (review बाकी) |
| Z-1a | पलीकडे swing नसेल ⇒ break नंतरचा पहिला confirmed swing | ✅ Abhi ठरवलं — code केलं (`flip.far_swing`, source "first_confirmed_after_break") | ✅ निकाली |
| Z-1b | Shared band check (`facts.validity.check_band`) चा "flipped" = real break + नव्या बाजूला ≥ 2 touches — Abhi च्या नियमापेक्षा वेगळा. `find_bands` ला `flip_state` / `far_swing` / `flipped_at` facts (additive); `valid` / `flipped` तसेच | facts जोडल्या, validity बदल नाही | Abhi / वेगळा PR |
| Z-1c | NIFTY / BANKNIFTY FUT नाही = data error | ✅ Abhi ठरवलं — `engine3_live.FutVolumeMissing` ⇒ error row, entry नाही, Telegram "data problem: FUT volume missing" (symbol प्रमाणे दिवसातून एकदा); V22 c0 volume NA ⇒ "data problem" वाट (`c0_volume_required`); cap_b पर्याय काढला | ✅ निकाली |
| Z-1d | Pullback आकार फक्त context; zone वाचन अस्पष्ट ⇒ थांबा | ✅ Abhi ठरवलं — checklist "G4" = [None, context], कधीच no_trade / wait नाही | ✅ निकाली |
| Z-1e | 22,544–22,622 spot zone = FLIPPED seller area; 12 Oct bear call golden | ✅ Abhi ठरवलं — code: zone FLIPPED (8 Oct 11:15, 5 Oct low 22,397.1 पार), 12 Oct 09:15 sweep. पण golden bear call **code देत नाही** — Z-1j पाहा | ✅ नियम; निकाल Z-1j |
| Z-1f | FLIPPED zone पुन्हा far swing पार ⇒ DEAD (दुसरा flip नाही) | ✅ Abhi ठरवलं — code केलं ("dead" event, log) | ✅ निकाली |
| RSI-2 | किमान pivot अंतर 3 bars सगळ्या TF | ✅ `rsi2/settings.py` `div_bars` 3–50 / 3–35 / 3–60; dashboard "RSI div min bars" (chart overlay) | ✅ निकाली |
| Z-1h | ~~Slot baseline: 20 sessions (`vol_slot_sessions`, Abhi); 20 पेक्षा कमी history ⇒ उपलब्ध sessions, किमान `vol_slot_min_sessions` 10 (legs2 rvol सारखं); त्याहून कमी ⇒ NA ⇒ data problem. Live: `engine3_fut_days` 45 calendar दिवस; Upstox फक्त चालू front-month contract देतो ⇒ rollover नंतर आधीचे दिवस next-month च्या (कमी) volume चे — baseline विकृत~~ **superseded ⇒ Z-1h row in "Abhi Z-1j / Z-1h / Z-1m — code" (short history ⇒ labelled raw per-bar fallback, not a data problem)** | 10 / NA | Abhi |
| Z-1i | `_born` merge: नवा swing BROKEN level मध्ये merge होतो (DEAD मध्ये कधीच नाही). न-merge केल्यास Abhi चा 22,544–22,622 zone दोन levels मध्ये फुटतो आणि 12 Oct spike ने अरुंद demand band DEAD होतो (Z-1e विरुद्ध) ⇒ merge ठेवलं. Level list: DEAD snapshot बाहेर; न-flipped BROKEN levels राहतात (births इतकेच, bounded) | merge ठेवलं | Abhi |
| Z-1j | ~~12 Oct golden bear call code देत नाही: (1) default — trade-data मध्ये FUT फक्त 30 Sep पासून ⇒ 12 Oct ला slot history 7 sessions < 10 ⇒ "data problem" वाट (09:30 strong_close body 6.0×; 10:15 inside_break body 2.54×). (2) what-if (min 5, फक्त अहवाल): 09:30 §5.3 range अवस्थेने अडला; 10:15 inside_break (A, vol 1.41×) + 5M CHoCH 09:40 + RSI bear div ⇒ **setup (bear call, grade B — Daily protected origin तुटला ⇒ कमाल B)**. RSI (1m order सह, phase 1 सारखं): D0 9 Oct 14:15 22,580.75 RSI 67.09 → 12 Oct 09:15 22,651.10 RSI 66.41, 4 bars, 09:15 forming / 09:30 + 09:45 confirmed~~ **superseded ⇒ Z-1p**: Z-1h (कमी history ⇒ raw per-bar fallback, data problem नाही) आणि Z-1j (§5.3 gate काढला) नंतर 12 Oct चं खरं कारण = no handover (09:30 buying candles दमल्या नाहीत; 10:15 दुसऱ्या अर्ध्यात counter candle नाही) | wait (data) | Abhi |
| Z-1o | Live engine3 V22 ला 1m order data नाही (`V22(m15, None, …)`) ⇒ swings2 D0 pivots 1m-आधारित runs पेक्षा वेगळे. 12 Oct: 1m शिवाय 09:15 high D0 pivot होत नाही ⇒ वरचा RSI divergence live मध्ये सापडला नसता (तपासलेलं: 1m शिवाय D0 जोडी 9 Oct 11:15 → 14:15, "RSI made a new high"). Live ला 1m आणायचा का? (levels सुद्धा बदलतील) | ✅ Abhi (a) — खालची ओळ | ✅ निकाली |
| Z-1o (a) | Z-1o: Abhi (a) — live engine gets 1m. `engine3_live` spot 1m (90 दिवस = `engine3_m15_days`; history दिवसातून एकदा cache, आजचा intraday प्रत्येक cycle) ⇒ V22 `df1m` (swings2 ⇒ levels + rsi2). Setting `engine3_use_1m` (dashboard 15M SRv2 पान, default ON; OFF = जुनं). 1m नाही ⇒ 1m शिवाय + कारण (payload `m1`), block नाही. Upstox calls: +1 / symbol / cycle, दिवसाचा पहिला cycle +5. तुलना (trade-data `review/engine3_1m/run1`): NIFTY 12 / 13 Oct — निर्णय सगळे wait दोन्हीकडे (setup बदल नाही); zone 22,543.75–22,621.80 चा hi 1m सह 22,651.10 (12 Oct 10:15 पासून); RSI bear div 9 Oct 14:15 → 12 Oct 09:15 फक्त 1m सह; grade (wait bars वर) 4 + 6 bars एक पायरी वर. BANKNIFTY: निर्णय / grade बदल नाही. बाकी प्रश्न: replay `--source upstox` अजून 1m शिवाय | ON (1m) | Abhi पुष्टी |
| Z-1k | 13 Oct: Abhi "spot 22,731.8 पार ⇒ flip" पण Z-1f नुसार हा zone 8 Oct ला आधीच flip झाला ⇒ पार ⇒ DEAD (दुसरा flip नाही). 13 Oct spot high 22,721.95 < 22,731.8 ⇒ code: BROKEN (15:00), resistance; bear call नाही ✅ (absorption 13:30–14:15; 14:00–14:15 D0 bear div forming, नंतर RSI नवा high ने रद्द) | BROKEN | Abhi |
| Z-1l | SENSEX FUT नाही ⇒ V22 data problem (entry नाही) पण Telegram नाही (FUT_REQUIRED = NIFTY / BANKNIFTY). Level bots (OFF) मध्ये volume NA ⇒ grade B अजून तसंच | असंच | Abhi |
| Z-1m | ~~In-zone gate = विद्यमान ⑥ (a2 = absorption ⇒ वाट, c0, c1); handover आवश्यक केलेला नाही (पुरावा). RSI divergence पुरावा: सापडला ⇒ +, नसेल ⇒ NA (वजा नाही — gate होऊ नये)~~ **superseded ⇒ Z-1m row in "Abhi Z-1j / Z-1h / Z-1m — code" (handover mandatory, order a2 → c1 → c0)** | असंच | Abhi पुष्टी |
| Z-1n | Flip वेग: real NIFTY वर जवळचा far swing बहुधा band पलीकडे फक्त 33–55 points ⇒ break च्याच bar ला flip शक्य. नियम बदलला नाही | — | Abhi |
| Z-1g | व्याख्या: reclaim = BROKEN नंतर `accept_closes` closes परत भूमिकेच्या बाजूला ⇒ जुनी भूमिका (sweep ★ नोंद); approach context: flip impulse = excursion आधीच्या शेवटच्या उलट D2 swing नंतरचं टोक ⇒ flip टोक; approach volume = flip टोक नंतर … decision bar आधी, per-bar normalised सरासरी | असंच | Abhi पुष्टी |

### Abhi अंतिम उत्तरं — Z-1 / RSI-2 (in-zone study)

> **closed (2026-10-21):** answered. The slot-normalised volume here is replaced by C-3 (raw volume bars, no time-slot baseline).

| # | निर्णय |
|---|---|
| मुख्य | Zone कडे येण्याची पद्धत (जलद / हळू, कोणताही volume) trade ठरवत नाही. Pullback corrective का आणि volume कमी का = फक्त **context**. निर्णय **zone मध्ये आल्यानंतरच्या वाचनावर** (बाजूनुसार candles, प्रत्येक candle चा normalised FUT volume, zone मधले patterns, कोणती बाजू वाढते / कमी होते, selling / buying volume, RSI divergence) ⇒ dominant commitment (जास्त volume) + LTF CHoCH = entry. ✅ |
| Volume | सरासरी per bar (बेरीज नाही), प्रत्येक bar त्याच्या वेळेच्या slot च्या मागच्या 20 sessions च्या median ने normalise. ✅ |
| Z-1a | पलीकडे swing नसेल (नवे high / low) ⇒ break नंतरचा पहिला **confirmed** swing. ✅ |
| Z-1c | NIFTY / BANKNIFTY FUT volume नाही = data error ⇒ entry नाही + Telegram "data problem: FUT volume missing". Volume शिवाय grade-B trade नाही. ✅ |
| Z-1d | Pullback आकार फक्त context; zone वाचन अस्पष्ट ⇒ थांबा. ✅ |
| Z-1e | (ii) 22,544–22,622 spot zone = FLIPPED seller area; zone मधलं वाचन ठरवतं. 12 Oct bear call = golden ✅. |
| Z-1f | Flip झाल्यावर जुनी भूमिका संपते; FLIPPED zone पुन्हा पलीकडच्या swing पार तुटला ⇒ dead (दुसरा flip नाही), log. ✅ |
| RSI-2 | किमान pivot अंतर 3 bars, सगळ्या timeframes (dashboard setting). ✅ |
| Trend बाजू (13 Oct) | Daily trend बदलला नाही तोपर्यंत reversal पासूनची चाल correction (a-b-c); flip झालेल्या zone वर bull trade = S4 अपवाद **नाही**. पुढचा seller zone ≈ 5–6 Oct highs; correction च्या शेवटी zone वाचन ⇒ bear. ✅ Abhi |
| B (Abhi, ZONE_STUDY_FINAL) | Trader's patience: wave count / maturity / c = a फक्त context — correction संपणं predict नाही, त्यावर block नाही. Watch-list: trend दिशेचे पुढचे सगळे counter-side zones armed (जवळचा आधी); zone तुटला ⇒ पुढचा आधीच armed. Loss सामान्य; rule / threshold जिंकवण्यासाठी बदलायचे नाहीत; loss नंतर lock-out नाही (setting, default OFF). ✅ KB + pack |
| Z-1k | एकदा flip झालेला zone पुन्हा पलीकडच्या swing पार तुटला ⇒ **DEAD** (दुसरा flip नाही; Z-1f प्रमाणे). 13 Oct चा zone spot 22,731.8 पार झाला तर DEAD, मग वरचे armed zones. ✅ Abhi (a) |
| Z-1j | §5.3 range state (overlap / doji) entry gate **काढला** — zone मधल्या overlap / sideways candles = handover study; range कडेवर trade (bull put तळाला, bear call वरच्या कडेला). §5.1 first-leg cap सुद्धा काढला (wave gate). ✅ Abhi |
| Z-1h | Volume normalise: 20 sessions (किमान 10); 10 पेक्षा कमी ⇒ "volume normalisation: insufficient history" + raw per-bar सरासरी (label सह). VPS वरून जुना FUT export. ✅ Abhi |
| Z-1m | Handover (a2) **बंधनकारक**: zone मध्ये दिसणारा handover + LTF CHoCH (close) शिवाय entry नाही; commitment candle त्यानंतर. ✅ Abhi |

### Abhi B (trader's patience) + Z-1k — code (branch `claude/decision3-flip-state`)

> **closed (2026-10-21):** B1 → C-15 / method §6 (no wave-count gates); B1-a → L6-a (the old caps are context notes, never the label); B2 / B3 / D-29 / Z-1k done (B3 note → Still open, standing).

| # | नोंद | code (default) | कोण |
|---|---|---|---|
| Z-1k | Flip झालेला zone पुन्हा far swing पार ⇒ DEAD (Abhi: (a)) | ✅ Z-1f तसंच; 13 Oct high 22,721.95 < 22,731.8 ⇒ BROKEN (close), पुढचे zones armed | ✅ निकाली |
| B1 | Wave / maturity / projections फक्त context — काढलेले gates (`wave_gates` = False; True = जुने tests): `decision3/engine.py` step1 — mature ⇒ cap weak, mature + अखंड ⇒ grade step-down, origin_risk ⇒ cap weak; `_level_eval` — §5.1 पहिला पाय cap (★ ≥ 2 + मजबूत signal-bar नाही ⇒ weak), §5.1 चौथा+ प्रयत्न ⇒ no_trade, पुरावा second_attempt / fourth_attempt (leg count) ⇒ NA; `bots_common/level_reaction.mature_cap` ⇒ नेहमी None; pre-open / 15:45 ओळ "daily move: mature (context only)". §5.1 (spec 08_थर_v22 §5.1) पाय-मोजणी = wave count ⇒ gate मानलं — Abhi ला चुकीचं वाटल्यास `wave_gates` | ✅ केलं | Abhi पुष्टी (§5.1) |
| B1-a | ठेवलेले (wave prediction नाहीत, Dow रचना): Q23 origin close ने तुटला ⇒ कमाल B, A1 same-degree correction ⇒ कमाल B, weekly विरुद्ध ⇒ कमाल B, trend first (`st.rev`) ⇒ trade नाही; §5.3 range अवस्था (Z-1j, Abhi कडे). ~~Level bots (OFF): origin_risk ⇒ NO_TREND तसंच~~ **superseded ⇒ RF-1** (level gate: origin_risk = context only) | तसंच | Abhi |
| B2 | Watch-list: trend दिशेचे पुढचे सगळे valid counter-side zones (BROKEN / DEAD नाहीत), जवळचे पहिले, `watch_levels_max` 3 (KB K4 display ≤ 3); प्रत्येकावर in-zone study; zone तुटला ⇒ पुढचा आधीच यादीत; row / payload `watch_list` | ✅ केलं | — |
| B3 | Loss नंतर lock-out: engine मार्गात (engine_entry) कोणताही loss lock-out नाही. SRv2 bot च्या स्वतःच्या (non-engine) मार्गात: ~~`COOLDOWN_MINUTES` 30 (SL नंतर, hard-coded)~~ ⇒ **Abhi 7a ⇒ (a) setting केलं** (branch `claude/srv2-cooldown-symbols-apply`): `15m_dynamic_sr.post_sl_cooldown_enabled` default **OFF** (cooldown नाही) + `post_sl_cooldown_minutes` 30 (फक्त ON असताना; ON ⇒ जुनं वर्तन तंतोतंत), 15M SRv2 dashboard panel "⏸️ Post-SL Cooldown". फक्त 15M SRv2 (हा code path दुसरा bot वापरत नाही; 5M Instant / Classic चा (level, role) 30-मिनिट re-entry gap आणि MCX `sl_cooldown_minutes` वेगळे, बदल नाही). टीप: `srv2_strategy_state.last_sl_hit_time` नवीन मूल्याने कधीच लिहिला जात नाही ⇒ ON केलं तरी live मध्ये हा cooldown व्यवहारात लागत नाही (आधीही नव्हता; replay मध्ये SRv2 symbol cooldown 0). `sl_tsl_cooldown_minutes` 15 (dashboard, त्याच level वर SL/TSL नंतर) तसाच. वेगळे risk settings (बदल नाही): Kill switch enabled, max_daily_loss_pct 2.0, max_daily_profit_pct 3.0, max_trades_per_day 15, count_paper_pnl True (PAPER लाही लागू), MCX kill switch 1.0 %, vision shadow_cooldown_min | ✅ ठरलं (a): setting, default OFF | ✅ निकाली (ON खरंच लागावा असं हवं असल्यास: SL exit वर `last_sl_hit_time` लिहिणं — Abhi) |
| D-29 | 29 Sep: trade-data मध्ये FUT 30 Sep पासून ⇒ 29 Sep ला FUT नाही (NIFTY live ⇒ data error); शिवाय decision3 1H levels मध्ये किंमतीजवळ zone नाही (जवळचा resistance 23,231–23,270, 12:15 close 22,677 पासून ~554 pts) ⇒ ③ ✘ दिवसभर ⇒ wait | ⇒ Z-1s / Z-1t (Daily warm-up ने zone जन्मला; 11:30 FLIPPED) | ✅ निकाली |

### Abhi Z-1j / Z-1h / Z-1m — code

> **closed (2026-10-21):** done. Z-1h's slot baseline → C-3 (raw volume); Z-1m's order → Z-1r (no order).

| # | नोंद | code (default) | कोण |
|---|---|---|---|
| Z-1j | §5.3 range अवस्था entry gate नाही — context fact (`range_state` row / payload); `range_state_gate` True फक्त जुने tests | ✅ केलं | ✅ निकाली |
| Z-1h | Slot normalisation 20 sessions (किमान 10); कमी history ⇒ "volume normalisation: insufficient history — raw per-bar average" (त्याच window मधली per-bar सरासरी; data error नाही); row / payload `volume_measure`, pre-open ℹ️ ओळ. FUT पूर्ण नसेल (NIFTY / BANKNIFTY) ⇒ data error तसाच. `live_export/2026-10-13-fut45/` अजून नाही ⇒ 12 Oct raw fallback वर | ✅ केलं | ✅ निकाली |
| Z-1m | a2 handover अनिवार्य (`a2_handover_required`), क्रम a2 → c1 → c0. Handover present ⇔ `method.zone_study(arm … t − 1)["handover"]`: zone मधल्या window च्या पहिल्या / दुसऱ्या अर्ध्यात trade-side candles वाढतात (body ↑ आवश्यक + range ↑ / close trade-टोकाजवळ ↑ / volume ↑ पैकी उपलब्धांपैकी किमान अर्धे) **आणि** counter-side candles दमतात (body ↓ आवश्यक + उलट wick ↑ / close दूर ↑ / volume ↓ पैकी किमान अर्धे); window ≥ 4 bars. Level bots (OFF) जुनं वर्तन | ✅ केलं | ✅ निकाली |
| Z-1p | Handover व्याख्येतली कडा: दुसऱ्या अर्ध्यात counter-side candle **नाहीच** ⇒ counter weakening NA ⇒ handover नाही (12 Oct 10:15). Counter बाजू पूर्ण गायब = दमली मानायचं का? 12 Oct 09:30: selling candles + selling volume वाढले, पण buying candles "दमल्या" नाहीत (body / wick majority) ⇒ handover नाही ⇒ golden bear call अजून नाही | ✅ Abhi (a): counter बाजू गायब = दमली ⇒ फक्त trade बाजू वाढतेय का (`method.zone_study` `counter_gone`) | ✅ निकाली |

### Review follow-ups — घेतलेले default निर्णय (Abhi ने बदलावे)

> **closed (2026-10-21):** RF-2 / Z-1q / Z-1r answered; RF-1 → dormant (level gate, ATP); RF-3 → C-3 (no slot baseline, so no rollover exclusion).

| # | नोंद | code (default) | कोण |
|---|---|---|---|
| RF-1 | Level gate (SRv2 / classic / MCX confirmation mode — PAPER default; LIVE touch mode ला लागत नाही): origin_risk आता entry अडवत नाही, फक्त context (B1-a मधली "Level bots: origin_risk ⇒ NO_TREND तसंच" ओळ यामुळे बदलली). Level bots OFF | context | Abhi |
| RF-2 | FUT gaps in-zone window मध्ये: NA bars वगळून per-bar सरासरी + label मध्ये gap count / कारण. Decision bar (c0) चाच volume NA ⇒ data problem (entry नाही). Gaps जास्त असतील तर (उदा. अर्ध्याहून जास्त bars) entry थांबवायची का? | ✅ Abhi (b): सरासरी volume असलेल्या bars ची + "gaps n/m"; gaps > `vol_gap_max_frac` (50%) ⇒ data problem, entry नाही + Telegram (`V22.vol_gaps`) | ✅ निकाली |
| RF-3 | FUT rollover दिवस (expiry + आधीचे 2 sessions) slot baseline मधून वगळले (legs2 प्रमाणे); त्या दिवसाचा स्वतःचा bar normalise होतो, label "FUT rollover day" | वगळले | Abhi |
| Z-1q | Handover एकदा दिसला की commitment पर्यंत वैध राहतो का, की commitment bar च्या window मध्ये (arm … t − 1) तो पुन्हा दिसायला हवा? Code आज commitment bar ला पुन्हा तपासतो. 12 Oct: 09:45 / 10:00 ला handover होता (doji / inside bar ⇒ commitment नाही), 10:15 ला window बदलल्यावर नाही (Z-1p) | ✅ Abhi (a): sticky — absorption / zone तुटणे (K4 BROKEN) पर्यंत टिकतो (`method.handover_episode`) | ✅ निकाली |
| Z-1r | क्रम (handover → LTF CHoCH → commitment) फक्त commitment bar ला तपासला जातो ⇒ handover दिसण्याआधी छापलेला 5M CHoCH सुद्धा चालतो (12 Oct: CHoCH 09:40, handover 09:45). CHoCH handover नंतरच हवा का? | ✅ Abhi (a+): क्रम नाही, तिन्ही commitment bar ला; CHoCH zone मध्ये आल्यानंतरचा (`ltf_choch` `arrival_at`) | ✅ निकाली |

### Deploy fixes (branch `claude/preopen-fixes`)

> **closed (2026-10-21):** done / answered.

| # | प्रश्न | आत्ता काय (default) | पर्याय |
|---|---|---|---|
| PF-1 | ~~15:45 सारांश एकच-किंमत areas~~ — केलं (review #326): engine source ⇒ `watched_levels` पट्टे (BROKEN / DEAD नाहीत); own / both ⇒ bot चा gate पट्टा; symbols = `signal_symbols` (SENSEX ओळ नाही) | केलं | — |
| PF-2 | decision3 levels: σ_1H नसताना (window चे पहिले 20 sessions) तात्पुरती किमान रुंदी = bars ≤ t चे 1H ranges चा median × 0.15; σ आल्यावर spec प्रमाणे | ✅ Abhi (a): तसंच, label "provisional width" (level facts, chart labels, log) | ✅ निकाली |
| PF-3 | ~~`signal_symbols` बदलल्यावर one-bot mode आपोआप लागत नाही~~ — केलं (Abhi 9a, branch `claude/srv2-cooldown-symbols-apply`): dashboard 🎯 panel वर सेव्ह ⇒ `bots_common/one_bot.apply_signal_symbols` = script चाच plan / apply, फक्त signal-symbols भाग (15M SRv2 per symbol on/off + engine + PAPER, Vision srv2 symbols / approval, PAPER instruments); सेव्ह केलेली यादीच वापरतो (पुन्हा वाचलेली जुळली नाही ⇒ काहीच नाही); signal symbols साठी `signal_source` = engine (own / both बदलतं); LIVE combo नाकार तसाच (effective + raw row); बाकी bots (5M / Classic / MCX / auto) ला हात नाही; log (`data/app.log`: before / after, by dashboard, वेळ); अयशस्वी ⇒ symbols सेव्ह राहतात, कोणते भाग लागले ते + script चालवायची सूचना | केलं | — |

### Abhi अंतिम उत्तरं — zone study (Z-1p … Z-1t, RF-2, PF-2) — code (branch `claude/zone-study-answers`)

> **closed (2026-10-21):** answered (implementation record).

| # | निर्णय (Abhi) | code | स्थिती |
|---|---|---|---|
| Z-1p (a) | Counter बाजू zone मधून गायब (दुसऱ्या अर्ध्यात counter candle नाही, पहिल्यात होती) = दमली ⇒ फक्त trade बाजू वाढतेय का | `method.zone_study` (`counter_gone`) | ✅ निकाली |
| Z-1q (a) | Handover एकदा दिसला की commitment पर्यंत टिकतो; रद्द फक्त नंतरच्या absorption ने किंवा zone तुटल्याने; प्रत्येक zone भेटीसाठी, look-ahead नाही | `method.handover_episode`, `V22.handover_episode` (zone तुटणे = K4 BROKEN / DEAD) | ✅ निकाली |
| Z-1r (a+) | क्रम महत्त्वाचा नाही — handover, LTF CHoCH, commitment तिन्ही commitment bar ला; CHoCH zone मध्ये आल्यानंतरचा (arm bar नंतर) | `method.ltf_choch` (`arrival_at`, `after_arrival`), `confirm(handover=…)`; row `commit.choch_vs_arm` | ✅ निकाली |
| RF-2 (b) | FUT gaps: volume असलेल्या bars ची सरासरी + "gaps n/m"; window च्या `vol_gap_max_frac` (default 50%) पेक्षा जास्त bars ला FUT नाही ⇒ entry नाही + Telegram "data problem: FUT volume gaps" (NIFTY / BANKNIFTY, दिवसातून एकदा); commitment candle चाच volume नाही ⇒ entry नाही | `V22.vol_gaps`, `V22._confirm`, setting `vol_gap_max_frac` (register) | ✅ निकाली |
| Z-1s (b) | Z-1a ची दुरुस्त शब्दरचना (नवा नियम नाही): पलीकडे आधीचा swing नसेल ⇒ break नंतरचा पहिला swing **confirm** होताच FLIPPED (तोडायची गरज नाही); आधीचा swing असेल ⇒ तो पार हवा; DEAD साठी तसंच | `flip.reached`, `Levels._step_far_swing`, `levels.band_flip_facts` (chart labels = engine) | ✅ निकाली |
| Z-1t (a) | Replays / tests: NIFTY holdout Daily bars फक्त Daily levels चा इतिहास (Q40), फक्त holdout नंतरच्या (≥ 2026-07) window साठी; holdout तारखेचा निर्णय / गुण / report कधीच नाही; प्रत्येक वापराची नोंद; "0 Daily bars before window ⇒ Q40 prior levels skipped" नोंद | `history.level_history_daily`, `read_level_history`, `repo_level_history`, `daily_warmup`; `engine.guard_sealed_bars` (+ `decide` पहारा); `Levels._prior_levels` log; harness: `tests/test_decision3_flip.real_inputs`, `scripts/replay_day.py` | ✅ निकाली |
| PF-2 (a) | तात्पुरती रुंदी (σ_1H नसताना median 1H range) तशीच; logs, chart labels, level facts मध्ये "provisional width" | `Level.prov` / `provisional`, snapshot `provisional_width` / `width_note`, `levels.width_tag` (1H chart, setup chart) | ✅ निकाली |

Re-run (default settings, 1m सह, Daily warm-up; FUT 30 Sep पासून ⇒ raw per-bar fallback; `live_export/2026-10-13-fut45/` अजून नाही):
~~12 Oct — bear call ✅ 09:30 candle (close 09:45): sticky handover (9 Oct 11:30 पासून), 5M CHoCH 09:40 (arrival 9 Oct 09:55 नंतर),
strong_close body 4.5×, volume 1.4× (raw) ⇒ grade B (golden xfail काढला); 11:00 ला दुसरा setup.~~ **चुकीच्या कारणाने** (merge झालेला 22,476–22,809 पट्टा + 9 Oct चा handover) — review #329; खाली नवा re-run. 13 Oct — bear call नाही ✅. 29 Sep —
22,725–22,810 BROKEN 09:45, FLIPPED 11:30 (22,569.65 confirm), 12:00 / 12:15 = pullback (③ ✔), पण त्या दिवशी FUT नाही ⇒ data problem
(entry नाही). तपशील: scratchpad अहवाल / WORK_LOG.

### Zone study answers नंतर — Abhi ने ठरवायचे (नवे)

> **closed (2026-10-21):** answered (Review #329, next section).

| # | प्रश्न | आत्ता काय (default) | पर्याय |
|---|---|---|---|
| Z-1u | ~~Daily warm-up (Z-1t, live सारखं) मुळे Q40 prior Daily / **Weekly** पट्टे (weekly candle चा wick-to-body, ~200–330 pts) window सुरुवातीला जन्मतात आणि overlap ⇒ merge होतात. 12 Oct चा 22,544–22,622 zone 22,476–22,809 या मोठ्या पट्ट्यात merge झाला (1 Oct ला तुटून flip; Abhi चा 8 Oct flip नाही); त्याखाली 21,965–22,622 support पट्टा सुद्धा overlap. Live engine3 (Upstox Daily) मध्येही हेच होत असणार~~ | ✅ निकाली (Abhi, खाली "Review #329") | — |
| Z-1v | ~~अर्थ लावलेले भाग: (1) Z-1q "zone तुटणे" = K4 BROKEN (accept_closes closes पलीकडे; एका close चा sweep रद्द करत नाही); तुटल्यानंतर handover फक्त break नंतरच्या bars वरून. (2) Z-1r "zone मध्ये आल्यानंतर" = arm bar नंतरची zone ला स्पर्श करणारी पहिली LTF candle. (3) RF-2 window = arm … commitment bar (commitment सकट); gaps जास्त असताना commitment नसली तरी data problem (Telegram दिवसातून एकदा). (4) FUT पूर्ण दिवस नसेल ⇒ "data problem: FUT volume missing on all n zone-window bars"~~ | ✅ निकाली (Abhi, खाली "Review #329") | — |


### Review #329 नंतर — Abhi ची उत्तरं (Z-1u, Z-1w, Z-1v) — code (branch `claude/zone-study-answers`)

> **closed (2026-10-21):** answered (implementation record).

| # | निर्णय (Abhi) | code | स्थिती |
|---|---|---|---|
| Z-1u (a) + confluence | वेगवेगळ्या timeframes चे levels कधीच एका पट्ट्यात merge नाहीत; प्रत्येक zone स्वतःच्या TF च्या base / reaction candles वरून (TA4); पट्टे फक्त बांधायचे, merge ने रुंद नाहीत. Daily / Weekly zone 1H zone वर ⇒ दोन्ही वेगळे, 1H वर label "confluence: Daily <low–high>" (पुरावा); trade location = अरुंद 1H पट्टा. Weekly (पूर्ण weekly candle) पट्टे फक्त context. Same-TF: पूर्ण आत ⇒ तोच zone (lineage), अंशतः overlap ⇒ स्वतःचा पट्टा + lineage | `levels.TF_OF`, `Levels._born` (merge नाही), `snapshot` (`tf`, `confluence`, `confluence_label`, `trade_location`, `width`, `width_sigma`, `lineage`), `active`; live: `engine3_live.tradeable_levels`, `level_gate_preopen.engine_zone_rows` (`ENGINE_LEVEL_1H\|confluence: …`), `plain_text.zone_note`; ⑥ पुरावा `level_star` ⇐ confluence. जुनं merge फक्त `level_merge` (legacy tests) | ✅ निकाली |
| Z-1w | "8 Oct" कधीच Abhi ची अपेक्षा नव्हती — fixture / tests मधून काढलं. Golden फक्त: 12 Oct ला हा zone seller area आणि bear call valid; तारखा K4 (Z-1s) ने | KB fixture ओळ, `tests/test_decision3_flip.py` (8-Oct test काढला; lifecycle test नवा) | ✅ निकाली |
| Z-1v (हो) | Handover फक्त त्याच **visit** मध्ये; किंमत पट्ट्याबाहेर, त्याच्यापासून दूर (आली त्या बाजूला) close, commitment शिवाय ⇒ visit संपली; नव्या visit ला नवा handover. `touch_window_bars` आता visit ठरवत नाही — फक्त ③ (commitment candle शेवटच्या स्पर्शापासून किती दूर चालते), त्याच visit मध्ये. Row / facts: `visit_start`, `visit_prev_end`, `visit_end`. Absorption gate सुद्धा episode च्या window वर (zone तुटल्यावर नव्याने). Daily warm-up (Z-1t) ① Daily / Weekly trend warm-up सुद्धा चालवतो (V22 `daily_df` ⇒ `DD.fold`) | `V22.visit`, `_confirm`; `method.handover_episode` (`window_start`), `confirm`; जुनं `zone_visit_rule` = "touch_window" फक्त legacy tests | ✅ निकाली |
| Review notes | `after_arrival` नेहमी True होतं (रचनेनेच) ⇒ काढलं; tests आता वेळा तुलना करतात (CHoCH > arrival > arm). `daily_from_1m` session शेवट `pivots.engine.session_complete` वरून (CAS सकट), literal नाही. "No prior swing ⇒ post-break swing confirm होण्याआधी reclaim ⇒ sweep" coverage परत (engine + band facts). `vol_gap_max_frac` dashboard वर नाही ⇒ KB मध्ये "register setting" | — | ✅ |

Re-run (default, 1m सह, Daily warm-up; `live_export/2026-10-13-fut45/` अजून नाही ⇒ raw per-bar volume, label सह) — 22,543.75–22,621.80 पट्ट्यावर:
12 Oct — bear call **नाही** ⇒ golden strict xfail (कारण तपासून): visit 12 Oct 09:15 पासून (9 Oct चा visit 9 Oct 15:00 च्या close ने संपला); 09:30
dominant red candle (body 6.3×, volume 0.6× raw, 5M CHoCH 09:40) आधी visit मध्ये फक्त 1 bar < study_min_bars 4 ⇒ handover वाचता येत नाही; 09:30 चा
close पट्ट्याखाली ⇒ visit संपली; दिवसात पुढे visit नाही. 13 Oct — bear call नाही ✅. 29 Sep — Daily 22,725–22,810 BROKEN 09:45, FLIPPED 11:30
(22,569.65 confirm); 12:15 engulf (5.8×), CHoCH 12:30, handover नाही, FUT नाही ⇒ entry नाही.

### Review #329 नंतर — Abhi ने ठरवायचे (नवे)

> **closed (2026-10-21):** answered (Z-1z volume → L3-c2).

| # | प्रश्न | आत्ता काय (default) | पर्याय |
|---|---|---|---|
| Z-1x | ✅ **ठरलं (Abhi, final):** zone एकाच base / reaction मधून; रुंदीला आकड्याची मर्यादा नाही, किमान रुंदी नाही. रुंद दिसला ⇒ दोन bases जोडले ⇒ बांधणी दुरुस्त (Z-1u). `trade_band_max_sigma` None (what-if), `level_min_width_sigma` 0; dashboard setting नाही | मर्यादा नाही | — |
| Z-1y | ✅ **ठरलं (Abhi, a):** far swing = पट्ट्यापलीकडचा, break आधीचा त्याच structural degree चा swing (इथे lower high 22,731.8). पट्ट्याच्या अगदी पलीकडची sweep wick (candle पट्ट्यात परत close — 12 Oct 22,651.10) structural swing नाही (`flip.structural`). 13 Oct: पट्टा BROKEN, resistance (flip नाही) | structural swing | — |
| Z-1z | **(Volume rule superseded by L3-c2: above the AVERAGE of the approach leg + the opposite side.)** ✅ **ठरलं (Abhi, final):** पूर्ण visit चं वाचन; push नाकारला + dominant उलट candle ने लगेच गिळला = handover; हळू visit = एक बाजू वाढते, दुसरी दमते; किमान candle संख्या नाही; volume = commitment ची तुलना (visit मधल्या उलट बाजूच्या candles पेक्षा मोठा) | तुलना | — |
| Z-1v-a | ✅ **ठरलं (Abhi, a):** अपयशी dominant candle पट्ट्याबाहेर close ⇒ visit संपली; पुढचा प्रवेश = नवी visit, नवा handover (code आधीपासून असंच) | असंच | — |

### Abhi च्या Z-1x / Z-1y / Z-1z / Z-1v-a उत्तरांनंतर — Abhi ने ठरवायचे (नवे)

> **closed (2026-10-21):** Z-1z-b / Z-1x-a closed; Z-1z-a, Z-1z-c, Z-1v-b → the method table below.

| # | प्रश्न | आत्ता काय (default) | पर्याय |
|---|---|---|---|
| Z-1z-a | 12 Oct 09:15 → 09:30: 09:30 ची candle 09:15 ची body engulf करत नाही (09:30 open 22,584.25 < 09:15 open 22,593.20) आणि close 22,512.15 हा 09:15 च्या low 22,512.00 च्या 0.15 pt वर. "Engulf" = body ने body झाकणं, आणि "closes back beyond it" = candle 1 च्या low (supply) पलीकडे — असं वाचलं | body-engulf + candle 1 च्या low पलीकडे close | (a) असंच; (b) engulf = candle 1 चा close / body खालचा भाग पार; (c) "beyond" = candle 1 च्या body पलीकडे |
| Z-1z-b | ✅ बंद: आकडा काढला — नकार = push-बाजूची wick body पेक्षा लांब (तुलना) | — | — |
| Z-1z-c | Volume normalisation (त्याच 15M slot च्या आधीच्या sessions चा median; 20 / किमान 10 sessions) हा आकडा उरतो — NUMBERS_INVENTORY C-3. 12–13 Oct ला normalised NA (7–8 sessions) ⇒ raw bars ची visit मधली तुलना वापरली | slot baseline (NA ⇒ raw, labelled) | (a) visit मधले raw volume bars (trader view); (b) slot baseline ठेवायचा (data plumbing) |
| Z-1x-a | ✅ बंद (Z-1x final: मर्यादा नाही) — 29 Sep Daily पट्टा पुन्हा location | — | — |
| Z-1v-b | "Visit … until price leaves it by structure": आत्ताचा नियम = पट्ट्याबाहेर (आली त्या बाजूला) एक close ⇒ visit संपली. 13 Oct ला पट्ट्याच्या खालच्या कडेवर लहान candles मुळे visit वारंवार संपते (10:15, 10:30, 10:45, 12:30, 12:45, 13:15…) | एक close बाहेर ⇒ संपली | (a) असंच; (b) "structure ने बाहेर" = पट्ट्याबाहेर close + पुढे swing (उदा. LTF lower high) / ठराविक अंतर |

### Approval पट्ट्याची रुंदी (branch `claude/approval-band-width`)

> **status (2026-10-21):** BW-1 → Still open (decided with layer 6, output; C-18).

| # | प्रश्न | आत्ता काय (default) | पर्याय |
|---|---|---|---|
| BW-1 | approval_band_warn_pts default 150 (Abhi) | 15M SRv2 (`15m_dynamic_sr`) setting `approval_band_warn_pts` = **150**: पट्टा (hi − lo) 150 pts पेक्षा रुंद ⇒ approval caption, pre-open आणि 15:45 सारांशात "⚠️ merged band — check" ओळ. फक्त दाखवणं (निर्णय / gate / order बदलत नाही). Dashboard: 15M SRv2 → 🧭 Signal source. Own-path (non-engine) signals ⇒ नेहमी default 150 (setting फक्त engine मार्ग, pre-open आणि सारांश वाचतात). PR #329 (root cause) नंतर हा इशारा ठेवायचा का? | 150 ठीक / दुसरा आकडा (उदा. 100 / 200) / #329 नंतर इशारा काढा |

### Abhi चं तत्त्व (final): वाचन = तर्क, गणित नाही — उरलेले आकडे

> **closed (2026-10-21):** the C items are resolved in the method table below; the two stray rows here (Z-1z-d, Z-1v-c) → the method table too.

सगळी यादी: `docs/reports/v22/NUMBERS_INVENTORY.md` (A = आता बदलले, B = चालणारे operational / display / data, C = Abhi ने ठरवायचे).
C मधले मुख्य: C-1 swings2 degree (k × σ) = "खरा swing" ची व्याख्या; C-3 volume slot baseline; C-4 `accept_closes` 3 (break वि. sweep);
C-5 ③ `touch_window_bars` 3 (प्रस्ताव: ③ = visit चालू); C-6 commitment candle-shape आकडे; C-12 trendline / chart-band (K5 / K6) MR आकडे;
C-17 conviction weights; C-18 approval 150-pt इशारा.
| Z-1z-d | **(Volume rule superseded by L3-c2: above the AVERAGE of the approach leg + the opposite side.)** Commitment volume = "visit मधल्या उलट बाजूच्या candles पेक्षा स्पष्ट मोठा". Visit मध्ये उलट बाजूची (रंगाने) candle नसेल तर? 12 Oct: opening push candle **लाल** close (upper wick), मग 09:30 लाल dominant — उलट बाजूची candle नाही ⇒ आत्ता "मात करायला काही नाही" (fail नाही). Raw पाहिलं तर 09:30 चा volume opening candle पेक्षा कमी | नोंद + fail-safe grade कमाल B (review) | (a) असंच; (b) push candle (wick ने नाकारलेली) = उलट बाजूची candle मानायची ⇒ तिच्यापेक्षा मोठा हवा |
| Z-1v-c | 29 Sep: जुना test "buyers exhausting" zone study 11:00 पासून (touch-window) वाचतो; visit (Z-1v) 11:45 पासून वाचली तर buyers मजबूत (absorption). Visit मधलं वाचन हेच engine वापरतं | visit पासून (engine) | (a) visit पासून (Abhi Z-1v / Z-1z — test बदलायचा); (b) दुसरं |

### Abhi's method (`docs/knowledge/CHART_READER_METHOD.md`) — all earlier questions resolved

> **status (2026-10-21):** the resolutions stand; L1-c answered today (row below); layer 5 / 6a await Abhi's ✅ (Still open).

The method replaces every piece-by-piece answer. Each item below is **assumed — no answer needed unless Abhi objects**, resolved by the
method's own text (resolution order: the method → Abhi's KB words → principles → an experienced trader's reading → the simpler reading).
Implementation per layer: `docs/reports/v22/METHOD_MAP.md`.

| # | Resolved as (method section) | Layer |
|---|---|---|
| Z-1z-a | Fast form = push rejected, then a dominant opposite candle that **closes beyond the push candle's body** (§3 Handover) | 3 |
| Z-1z-d | **(Volume rule superseded by L3-c2: above the AVERAGE of the approach leg + the opposite side.)** Commitment volume larger than the **approach leg's** candles and the visit's opposite-side candles; the rejected push and the commitment excluded (§3 Commitment). The grade-cap-B fail-safe goes | 3 |
| Z-1z-c / C-3 | Raw volume bars; no time-slot baselines (§3 Volume) | 3 |
| Z-1v-b / Z-1v-c / C-5 | A visit ends only by structure: a swing built away from the area, a break / flip, or a failed commitment closing outside; candles closing just outside and coming back are the same visit; time never ends a visit (§3 Visit) | 3 |
| C-4 | Broken = a close beyond **and** a swing formed beyond; sweep = back inside before any swing forms beyond (§3 Area lifecycle) | 2 |
| C-1 / C-21 / C-2 / C-13 | Swings, degrees, impulse / correction, equal, trend — by structure (§3 Structure) | 1 |
| C-6 / C-7 / C-9 / C-10 / C-20 | Candle forms, big / dominant, equal, range — by comparison (§3) | 1, 3 |
| C-12 | Lines from two separate reactions on the structure's own swings (§3 Lines) | 4 |
| C-17 | No scores: A = the required set + ≥ 1 confirming piece; B = the required set only (§5) | 6 |
| C-18 | Approval width alert = operational display; decided with the output (layer 6) | 6 |
| C-24 | Definitions coded earlier without Abhi's wording are replaced by the method's wording in their layers | 1–6 |
| C-8 | Power shift is not in the method's confirming-evidence list (§4) ⇒ reported as context only, never scored or required; its sub-checks by comparison (§3 Structure) | 3 |
| C-11 | K extreme reset when price makes a new extreme beyond the old one (§3 Structure) | 1 |
| C-14 | Prior Daily / Weekly swings are areas like any other (§3 Areas: built from their own base, armed ahead of price in the trend direction, §4 Watch) — no ATR-distance filter | 2 |
| C-15 | Fourth-attempt / wave-count gates removed (§6 Never: wave-count gates) | 6 |
| C-16 | G4 approach volume = comparison only; context, never a gate (§3 Volume: "the approach does not decide") | 3 |
| C-19 | RSI compares consecutive real swings of the same degree (§3 RSI) | 5 |
| C-22 | The old rsi2 `RSI` class is not on the reading path; retired in a clean-up (§7 one owner) | 5 |
| C-23 | Slow handover = trend-side candles grow, opposite-side shrink, volume tilts to the trend side — no "at least half" count (§3 Handover) | 3 |
| BW-1 | Approval width alert = operational display, decided with the output (layer 6) | 6 |
| L2-a | "A swing formed beyond" = a swing of the finest STRUCTURE degree (D1 — Abhi's approved structure degrees are D1 / D2; D0 turns are the "small wiggles inside a leg" of §3, not swings), beyond the area, after the first close beyond (§3 Area lifecycle; any real swing, not only the trend degree) | 2 |
| L2-b | Reclaim of a broken area mirrors the break: a close back on the role side (outside the band) **and** a swing formed there; a close back inside before that swing is confirmed ends the attempt, as a poke back inside ends the break (§3 Area lifecycle, mirror) | 2 |
| L2-c | Equal highs / lows (liquidity area) = the later extreme stays within the earlier swing's own area and does not go beyond it (§3 Equal) | 2 |
| L3-a | Slow form "volume tilts to the trend side" = in the later part of the visit the trend-side candles' volume is above the opposite side's (opposite side gone ⇒ tilted; volume NA ⇒ the candles are read alone and the commitment's volume check reports the gap) (§3 Handover) | 3 |
| L3-b | A failed commitment that ends the visit = a dominant trade-side candle closing outside on the side price came from WITH the visit's handover present ("the commitment is the dominant candle after the handover"); without a handover it is only a candle that closed outside — the same visit. The visit-ending swing = a swing of the finest structure degree, beyond the area on that side (§3 Visit) | 3 |
| L3-c | **Abhi (answered):** a gap is just the next candle (P2), never a boundary — the leg that brought price into the area began before the gap, so the commitment's volume is compared with that leg's candles (and the visit's opposite-side candles), exactly as §3 says. "Nothing to compare" never occurs for a gap entry; no automatic pass. The earlier vacuous-pass resolution (and the grade A it gave 12 Oct) is withdrawn | 3 |
| L3-c2 | **Abhi (answered, his own rule):** the commitment's volume is higher than the AVERAGE of its comparison set (the leg into the area + the visit's opposite-side candles; the rejected push and the commitment excluded) — not higher than every one of them; a pullback may start on heavy volume, so the largest candle never decides. The spec wording "larger than the candles" was wrong. "Dominant body" stays "larger than the other candles of the visit". | 3 |
| L3-c3 | The facts dossier (vision facts) calls the same commitment read without the rejected push excluded (the engine excludes it), so the two can disagree on a heavy opposite-coloured push. Deferred with the dossier visit finder to layer 6 (L3-n). | 6 |
| L3-d | Absorption = opposite-side candles in the later part of the visit, each smaller than the largest trend-side candle of the visit, the trend side NOT growing, and no later close beyond the earlier part's closes on the trade side (a sideways base) — so absorption and the slow handover exclude each other (§3 Absorption) | 3 |
| L3-e | Approach leg = the candles after the last swing built away from the area (the finest structure degree), across any gap, session change or earlier visit (Abhi, P2); no such swing known ⇒ the approach is unknown and only the visit's opposite side is compared (none ⇒ no commitment) (§3 Commitment) | 3 |
| L3-n | Deferred to layer 6 (output): the vision facts dossier finds its zone visits with the chart band finder — a session look-back for candidate bands and a `touch_window_bars` count — not the engine's structural visit; its commitment read now uses the same approach leg (the last structure swing built away, across gaps) | 6 |
| L3-f | Commitment forms by comparison (§3 "comparing body and wicks"): pin = the rejection wick longer than the body and the other wick together; strong close = the body larger than both wicks together; star = a strong opposite candle (body larger than its wicks), a middle candle smaller than both neighbours, then a close back into the first candle's body; tweezer = the extreme reaches the previous candle's wick and does not go beyond (the §3 "equal"); doji = the body smaller than each wick | 3 |
| L3-g | "Big" (§3) = body / range above the average of the visit's other candles; with no visit context there is no "big" reading (never a fixed look-back) | 3 |
| L3-h | P2 in the commitment: two-candle forms span sessions (a gap is the next candle); the entry hours stay an operational dashboard schedule, applied by V22 after the read, never inside it | 3 |
| L3-i | Liquidity pools (§3 equal / sweep / broken applied to pools): the structure's swings + equal pairs (one pool); sweep = beyond and back inside before any swing formed beyond; a close beyond and back = trapped (failed breakout); window = the current pullback; no day / week pools (P2) | 3 |
| L3-k | Zone patterns (double / triple top or bottom inside the visit) by the §3 "equal" in time order: each later extreme reaches the reference swing candle's own band and does not go beyond it; one that goes beyond becomes the new reference | 3 |
| L3-l | G4 approach context (b): the approach's per-bar volume "lower than" the flip impulse's — a plain comparison, never a ratio limit (context only, never a gate) | 3 |
| L3-m | When a 2-candle form's read fails (measured against the candle before the pair) but the last candle is itself a pin / strong close, it is read as that 1-candle form (a commitment is never lost to a looser 2-candle name) | 3 |
| L4-a | A line touch = the swing candle's wick reaches the line while its body stays on the line's side (the §3 "equal" read for a line); the two anchors are the line — no touch count (§3 Lines) | 4 |
| L4-b | Between the two reactions no candle closes through the line; a wick past it is a touch / sweep, not a disqualifier (§3 Lines, Sweep) | 4 |
| L4-c | Confluence = the line passes through the area's band at the read bar ⇒ that area is labelled (same band); never a new, narrowed band (§3 Lines, §6 "bands merged or widened by numbers") | 4 |
| L4-c2 | **Abhi (answered, B):** a reaction that rises out of (falls out of) an area and turns at the line is a touch — the closest approach since the previous touch, no close beyond the line, then away from it. The area and the line meet there ⇒ "confluence: line". The golden third-touch case reads this way (12 Oct 09:15 turn ⇒ the 1H supply labelled). | 4 |
| L4-f | "The previous touch" for that comparison = the last time a candle reached the line (its second anchor or a later wick touch). If a reaction-touch itself counted, every lower turn would be a touch and "closest" would never exclude anything. The turn = a swing of the structure (finest degree, layer 2's "a swing"); its confirmation is the "goes away" evidence. (Superseded by L4-g for which turn is read: the reaction's own closest turn; one reaction = between two opposite swings of the line's structure.) | 4 |
| L4-g | **Abhi (answered):** (1) count touches by REACTIONS, not contacts — contacts with no real opposite swing of the line's structure between them are one touch; from the third touch on every touch is a trade location while the line is unbroken; the touch number is information. (2) The touch point is the reaction's own turn (the swing it forms at the line); a later turn that stays away from the line does not remove the confluence label for that visit. Code: `trendline.touch_groups`, `reaction_touch` (`touch_no`, `trade_location`), label "confluence: line (touch N)". Golden 12 Oct: the 7 Oct 12:00 wick contact merges with the 6 Oct anchor (no swing low between) ⇒ the 12 Oct 09:15 turn is touch 3. One reaction = the move between two real opposite swings of the line's structure (its degree): the label holds for that reaction (the visit) and moves to the next reaction's turn once a new opposite structure swing forms; it also ends at a close beyond the line, a later turn that reaches the line, or the line's redraw. Earlier reactions that turned at the line out of an area alive then are counted as touches too. Assumed: a line alone with no area is still not an entry (spec ②) — the touch is a trade location where an area stands at it. | 4 |
| L5-a | **Abhi (answered, final — default; he can change it):** read the divergence between the consecutive pushes INSIDE the move into the zone; use the highest degree at which that move shows at least two pushes; a swing from before the move began (e.g. the D1 high before the move's own low) is never compared; also report a zone-degree divergence. Code: `engine.rsi_divergence` (`move_from` = the approach leg's own swing; `degree`, `pushes`, `zone_degree`; `div_degree_rule = all` = the old D0–D2 what-if). Golden 12 Oct: D1 shows one push inside the move, D0 two ⇒ D0 is read: 9 Oct 14:15 → 12 Oct 09:15 (RSI 67.09 → 66.41) = the bear divergence; 09:30 label A (RSI divergence + confluence). Assumed: the zone degree of a Daily zone = D3 (not computed by rsi2 ⇒ reported "not computed"); a zone-degree divergence is information, not the confirming piece on its own. | 5 |
| L6-a | Method §5 label rule (A = required + ≥ 1 confirming, B = required only) replaces the older label caps ("Weekly against ⇒ max B", origin broken, counter-correction, Weekly fallback; maturity was already context; Q16 "wick-only commitment (grade B) ⇒ max B"; the first-leg / commit-strength cap, legacy wave gates only): they are reported as context notes (the commitment's form stays in its facts), never the label; `trend_cap` is None under the method rule. A label belongs to an entry: a wait or a legacy R:R no-trade has none. The evidence list shows the reading's required set apart from the operational entry hours. "Confluence" as confirming evidence = a line meets the area OR a Daily / Weekly area overlaps it (Abhi Z-1u). | 6 |
| L4-d | The correction's own line triggers when the commitment candle (bar t) closes through it at the area (§3 trigger form). Before t a line (K line or trade-side line) is gone only by a close beyond AND a swing formed beyond it (K6.5, "as an area"); a close that comes back first is a throw-over and the line stands | 4 |
| L4-e | "Separate reactions" = a swing of the opposite kind lies between the two anchors (price left the line); without one the pair is one reaction, not a line (§3 Lines) | 4 |
| L3-j | "At the area" also means the commitment trades in the area: its candle, or the candle just before it (a merged pair, or a commitment right next to the area), touches the band — a candle far below / above it inside a still-open visit is a chase, never an entry (§1 P4, §4 "a breakout away from an area") | 3 |
| L1-a | **Abhi (answered, layer 1 ✅):** keep A — the approved swings2 D1 / D2 ARE the swing definition. A swing's significance is always judged against the market's own normal movement; swings2 does that at the scale Abhi chose from his own charts (his visual calibration, not a fixed point value). The pure comparative rule is not used (it matched A in 4 / 12 because it counts one-candle turns as swings; trade-data `review/method_layer1_rule/RULE_CASES.md`). The scale is recorded as Abhi's calibration setting (advanced dashboard; KB K1); C-1 resolved. | 1 |
| L1-b | **Abhi (answered):** the Daily-structure numbers follow C-13 logic; the only calibration that stays is the swings2 scale (D1 / D2). Code: equal = the later extreme reaches the earlier swing candle's area (wick to body) and does not go beyond it (RANGE edges, Q27 RANGE after a broken origin); a lower high / higher low = stays short of the earlier swing's area (trend start); maturity is context only and "near" = the leg's extreme reached the projection's area (the target swing candle, wick to body); origin risk = price reached the protected origin's area; the sharp-fall / sharp-rise zone is the area itself (no σ band); the K pullback resets when price goes beyond the old extreme (no σ). `maturity_sigma_d` and `k_reset_sigma` removed; `range_eq_sigma_d` remains only for the legacy minor fold and the Daily chart's display bands. | 1 |
| L1-c | **Abhi (answered 2026-10-21):** keep N = 2 as the provisional value; he may change it later from the dashboard (setting added by the live-switches track). Earlier text: **For Abhi (default until he answers):** the Daily pivot size `daily_pivot_n` (a Daily swing = more extreme than N Daily bars each side, N = 2) has no decided logic (C-13 covers "equal" and maturity only). Default: unchanged (N = 2), listed PENDING for layer 1 in the guard. Options: keep it as a Daily definition; or Daily swings from the same rule as the approved swings2 at the Daily degree. | 1 |

### BANKNIFTY reader replay at 04a8b40 — observations for Abhi (test report only; no rule, no setting changed)

> **status (2026-10-21):** open → Still open. One simple-Marathi page with the charts side by side: trade-data `review/replay_banknifty_6m/04a8b40/ABHI_QUESTIONS_MR.md`.

Walk-forward replay of the reader as merged (layers 1–4, 5, 6a; default settings) at each closed 15M bar, BANKNIFTY only (NIFTY holdout untouched), 13 Jul–13 Oct (the BANKNIFTY history available locally; not 6 months). Report, charts and CSVs are in the private trade-data repo only: `review/replay_banknifty_6m/04a8b40/`.

| # | Observation for Abhi | Where (trade-data) |
|---|---|---|
| R-BN-1 | 0 setups formed and 32 forming zone visits, all bear call (Daily DOWN throughout). In the 9 sessions with complete inputs, 7 of 8 visited areas were later closed through, and at each the reader had read "no handover". Does Abhi agree with "no handover" there? | `groups.md`, `charts/E29_*`, `charts/E31_*` |
| R-BN-2 | "Commitment + 5M CHoCH but no handover" happened 6 times (E14, E17, E20, E21, E24, E29): 3 reached the next area first, 3 broke the zone first. Does Abhi read a handover on any of them by eye? | `groups.md` G3, `charts/E14_*`, `charts/E21_*`, `charts/E24_*` |
| R-BN-3 | E26: fast handover + engulf A + confluence, still waiting for the 5M CHoCH. The next area came about 2 h later, but the adverse move first was larger than the code-default spot SL. Recorded only; no rule. | `charts/E26_*`, `observations.md` |
| R-BN-4 | 10 large moves had no setup before them. 4 were against the Daily trend (by design). The largest drop started from a sideways top that was not an area. | `missed_moves.md`, `charts/missed/M06_*` |
| R-BN-5 | Data: BANKNIFTY FUT 5M volume exists only from 30 Sep, and 5M / 1m only from 15 Sep, so 24 of 32 visits could not be read as live (flagged, not filled). Re-run when more history is exported, and when layers 5 / 6b change. | `data_check.md`, `README.md` |

## BANKNIFTY replay reading checks (deployed code da7cbbc; report in private trade-data `review/replay_banknifty_6m/da7cbbc/checks/`)
Misreads are bugs against a named concept of the Price Action Standard (never one-chart rules). Not fixed yet — fix in a separate PR.
- **FIXED (branch `claude/models-inside-area-clean-charts`, `levels._base`, tests/test_levels_bos_base.py) — BUG — concept C (area base), BOS-origin area (birth "b").** Now: the first trend-direction 1H candle after the origin that is complete before the BOS bar's hour; none ⇒ the origin's own candle (the base the impulse left); never the breakout candle. A 1H support area was built from the BOS breakout candle itself
  (the base 1H candle cut at the BOS bar = the breakout 15M candle), not from the candles where buyers acted. Method §3 Areas: "An
  area is built from ONE base or reaction: the candles where buyers or sellers acted (wick to body)". Owner: `decision3/levels.py`
  (BOS base selection).
- **FIXED (same branch, `levels.bos_band` = `_band_swing`'s rule) — BUG — concept C (area band), Z-1x.** When the base candle has no wick on the area side, the code takes the whole candle
  (`decision3/levels.py` ~503–505) instead of the body (Z-1x: wick-to-body; no wick ⇒ body).
- **Checked, matches the method — concept C:** a swing-born 1H area (birth "a") ~300 points wide is one 1H candle's wick-to-body
  after a sharp first-hour push; no merge of bases or timeframes (Z-1u holds).
- **Checked, matches the definition — §3 E2 commitment:** the commitment candle is the dominant candle IN the visit (body larger than
  every other visit candle, volume above). It closed outside the area, so the invalidation (visit extreme) was ~460 points away.
  **Question for Abhi (provisional default: no change):** should a commitment that closes far beyond the area be skipped (P4 "no
  chase")? No such rule exists in the method today.
- **Info — same-bar entries (two models on one bar):** 5 bars / 10 entries over 30 Sep → 19 Oct. `max_hits_per_zone` = 2 does not
  choose between them; the one-position-at-a-time rule moves the second to the next cycle. Abhi decides (provisional: no change).

## Abhi's root-cause order RC1–RC6 (BANKNIFTY 07–21 Oct review; branch `claude/models-inside-area-clean-charts`)
Implemented (rules recorded in CLAUDE.md, CHART_READER_METHOD.md §1 P8 / §8, REPORT_STANDARD.md §0 / §3a; tests named per item):
- **RC1 (Z-1u, §3 models):** `entry_models.clusters()` only counts one signal per model per place; trigger, edges and invalidation come
  from the visited area. The cluster carries no band (payload / card); `max_hits_per_zone` counts the visited area
  (tests/test_entry_models_inside_area.py::test_no_union_field_reaches_an_entry_the_payload_or_the_card).
- **RC3 (§3 models / C lifecycle):** `entry_trigger_rule = inside` (#364; `legacy` = da7cbbc, what-if). **Superseded by Abhi 22 Oct
  (RC3 wording fix, branch `claude/trigger-traded-inside`): default `entry_trigger_rule = traded_inside`** — the trigger candle traded
  inside the visited area (refined base reached in the visit) and price is not beyond the INVALIDATION side; a close outside on the
  TRADE side is the confirmation and fires. `inside` / `legacy` stay as what-ifs. The earlier question above ("should a commitment that
  closes far beyond the area be skipped?") is answered by Abhi: a commitment that traded in and closes away on the trade side is an
  entry (invalidation = the visit's extreme); one that closes beyond the far edge / never traded inside is not.
- **RC2 (research default, review after the replay):** `entry_area_refine = setup_tf` (default; `area` = the context area itself).
- **RC4 (§3 E4 b):** a broken line is "at" price only while a bar's range holds the line; the revisit ends at a swing that does not
  reach it (either side). Before: the touch was one-sided (any bar above a broken support line "touched" it), so a line far away stayed
  "revisit in progress" (04 Aug).
- **RC5:** `reader_report.standard.group_data_status` — a group without near-month FUT volume on every spot session is "not testable".
- **RC6 / P8:** `decision3/chart_lines.py` + display setting `chart_max_lines` (6).

Provisional choices (assumed — no answer needed unless Abhi objects). Each was checked against CLAUDE.md and CHART_READER_METHOD.md:
- **Refined base = the NEWEST 15M swing (finest structure) of the area's side whose extreme is inside the context band, from the area's
  birth turn on; band = that candle's wick to body (levels._band_swing), clipped to the context band.** Method §3 Areas "built from ONE
  base … the candles where buyers or sellers acted (wick to body)" + "the trade area is the lower-timeframe one"; P1 no numbers (none).
- ~~**Proximity = price reached the refined base in this visit; the close must be inside the CONTEXT area** (not inside the narrow
  refined band — a commitment closes away from the base by its nature). RC3 "inside its (refined) area" read as: at the refined base,
  closing inside the area; method §3 Commitment (the dominant candle after the handover) would otherwise never fire.~~ **Superseded
  by Abhi 22 Oct (`traded_inside`, then the refined-base trigger decision): the trigger candle itself trades into the refined base; its close may be
  outside the area on the trade side (never beyond the invalidation side).**
- **E1 with a refined base = the visit's first candle that reaches the refined base** (was: the visit's first candle). Invalidation
  beyond the base's far side. **E2 / E3 invalidation = the farther of the base's far side and the visit's extreme** (an invalidation is
  never inside a price already traded in the visit).
- **E4 (b) "at the object" = a candle of the rejection form touches it** (one-candle forms: the trigger candle; two-candle forms: the
  trigger or the one before). Method §3 Lines: "the third touch is the trade location".
- **E4 (a) sweep keeps the context area's far edge** (the sweep is of the area; the refined base gives the trigger location: the trigger candle trades into it).
- ~~**`traded_inside` (Abhi 22 Oct) — "traded inside the (refined) area" = the trigger candle's range reaches the VISITED area's own band
  (the band #364 checked the close against) and the refined base was reached earlier in this visit** — not that the trigger candle
  itself reaches the narrow refined band.~~ **DECIDED by Abhi (22 Oct; branch
  `claude/trigger-touches-refined-base`): the trigger candle ITSELF must trade into the 15M refined base (its range overlaps the base
  band) for E1 / E2 / E3 / E4 a — the refined base exists so entry and invalidation come from the narrow base; a candle that never
  touches it brings back the wide invalidation.** Kept: a close outside the area on the trade side is allowed; never a close beyond the
  invalidation side; E1 base_broken; `entry_area_refine = area` ⇒ the visited area is the base; E4 b keeps "at the retested object";
  `inside` / `legacy` what-ifs unchanged (`Reader.off_base`; tests/test_entry_models_inside_area.py `*_only_into_the_context_area_*`,
  tests/test_entry_models_real_bn_oct07.py::test_oct07_0915_e2_commitment_not_trading_into_the_refined_base_no_longer_fires). Before
  this, in the 07–21 Oct replay 3 of the 19 triggers (07 Oct 09:15 E2, 07 Oct 12:15 E3, 08 Oct 09:15 E3) did not touch the refined
  base themselves.
- **Sweep / fakeout behaviour (Abhi 22 Oct, confirmed — method §8):** a close beyond without a swing beyond, then back inside = sweep
  (area alive, visit continues); E4 a on the failed next push (invalidation beyond the sweep extreme); E2 / E3 later in the visit
  (candle in the refined base; invalidation includes the sweep extreme); E1 never comes back; close beyond + swing beyond = broken
  (flip) ⇒ the area's models disarm, a return from the other side ⇒ E4 b; a close beyond the refined base ends only E1. The code already
  read it so — no code change; pinned by tests/test_entry_models_sweep_fakeout.py (both mirrors; two tests feed the real K4 reader,
  decision3/levels.py, into the models).
- **The invalidation side = a close beyond the area's far edge (H2, unchanged) or beyond the model's invalidation; E1 keeps the RC3
  base-closed-through lifecycle check; E2 / E3 do not add it** (their invalidation is already the farther of the base's far edge and
  the visit's extreme — no new rule). A wick beyond the far edge with a close back on the trade side is a sweep (method §3), not the
  invalidation side.
- **E4 (b) is unchanged by `traded_inside`:** the rejection form (one-candle: the trigger; two-candle: the trigger or the one before)
  trades at the retested object and closes on its trade side — #364 already read it so.

Effects to review (07–21 Oct, trade-data `review/replay_banknifty_6m/<sha>/groups/2026-10-07_2026-10-21/`):
- **E2 5 → 0 in this group under the inside rule:** every E2 commitment here closed outside its area. RC3 as ordered; flagged.
  **Abhi 22 Oct: a wording bug — fixed by `traded_inside`.** Replay 8423bd5 (trade-data
  `review/replay_banknifty_6m/8423bd5/groups/2026-10-07_2026-10-21/`, before = #364 7b29a70 `inside`, both max_hits_per_zone 4):
  entries 16 → 19 (next area first 10 → 12, invalidation first 6 → 7); E1 4 → 4, E2 0 → 3, E3 5 → 5 (three move to an earlier
  bar of the same visit / cluster — the CHoCH bar's trade-side close), E4a 0 → 0, E4b 7 → 7. E2: 07 Oct 09:15 (286, closed 149 below the area,
  invalidation 55,201 = the visit's extreme; invalidation first, MAE 539), 16 Oct 09:15 (270; next area first), 19 Oct 09:15 (268;
  next area first).
- **RESOLVED (Abhi 22 Oct) — the 12 Oct fixture conflict:** the synthetic 12 Oct bear-call fixture's trigger candle trades up through
  the area and closes below it (the trade side): under `traded_inside` it is an entry again (E1 / E3 on it;
  tests/test_entry_models_inside_area.py::test_oct12_fixture_spike_trading_through_and_closing_away_fires_under_traded_inside), so
  the row-shape / live-contract tests read that fixture on the default again. Its next, dominant candle never traded inside the area
  ⇒ no E2 there (the facts-dossier parity test keeps `legacy` for that bar only). The real 12 Oct golden test stays pinned to
  `legacy_k` (unchanged). Nothing left to ask.
- Wide single areas (~300 pts, 3.5–4× the median): not a cluster effect. The BOS-origin one (Abhi's 300, births b + c) came from the
  two concept-C bugs above — fixed here (C-1 / C-2); the swing-born ones (a:D2, one sharp 1H candle wick to body) match the method and
  stay; the refined 15M base now bounds the trade location inside them.

## BANKNIFTY 6-month reading galleries (code bf98040; trade-data `review/replay_banknifty_6m/reading/bf98040/`) — possible misreads
Logged as bugs against named concepts (never one-chart rules). Not fixed yet.
- ~~**Z-1u / RC1 counter not applied to E4b broken areas**~~ — FIXED (owner-orders DECISIONS 28): `entry_models.read` runs the
  place count over E4 (b)'s broken areas and broken lines (`clusters(obj=("broken_area", "broken_line"))`). Was: two E4b entries at one place — 25 Sep 14:00 (1H 276 + D 277, identical band
  55,699–55,970), 01 Jul 12:15 (D 295 + 1H 296), 20 Jul 14:15 (area 295 + a broken line at the same bar). The one-signal-per-model-
  per-place counter must include E4b's broken objects.
- **RC2 refined base (§2C):** the 26 May 09:30 down move (2,415 pts) had no entry — D area 97 waited "no refined base yet: no 15M
  turn inside its band". Check whether a refined base should come from the turn that starts the departure (short 15M history may
  contribute).
  **Checked — not a bug against TA4 / RC2 (DECISIONS 10); no code change.** (a) The departure turn (15M swing high 26 May 09:30,
  55,536.80, inside the D band 55,326.05–55,554.15) is a finest-structure (D1) swing only when confirmed: at 13:00, when price was
  already ~250 pts below the band (close 55,076). From 13:00 the reader does use it as the refined base (55,459.00–55,536.80, wick to
  body) — E1 correctly reads it as "a newer turn formed inside this visit" (E1 = the first arrival at a base known before) and no later
  candle traded back into it (high after 13:00: 55,204.95), so E2 / E3 / E4 (a) had no trigger candle at the base (DECISIONS 22). Using
  the turn before its confirmation would be look-ahead; using its D0 confirmation (09:45) would read a wiggle as a swing (§3 "small
  wiggles inside a leg are not swings"). (b) The short 15M history is the real cause in the gallery: the replay's 15M data starts
  13 Apr, and swings2 reads no swing until its σ has `sigma_sessions` sessions (data quality, not a reading rule) ⇒ no 15M swing of
  any degree before 13 May (first pivots 13 May 09:15). This D area (born before the 15M window, `a:D-prior`) was tested 13 Apr, swept
  28 Apr–4 May and touched 8 May — all before 13 May — so none of its earlier 15M turns could become the refined base (with a turn
  known before 25 May, E1 would have been read at the first touch of this visit). The same warm-up explains the two empty gallery
  groups (13 Apr–9 May: 0 entries). Live reads a 90-day 15M window (`engine3_m15_days`), so its first ~`sigma_sessions` sessions carry
  no 15M turn either — for Abhi's eye only (a D / W area whose only 15M turns lie in that first part waits until a new turn forms
  inside it, or a newer one is confirmed); no change without his word (RC2 is a research default, review after the replay).
- ~~**§3 E4a (K4 sweep):** E4a never fired in six months. Check the sweep read on charts.~~ — CHECKED, not a bug (see "Reading
  checks — E4a and E4b" below).
- ~~**E4b on channel parallels (`|par`):** the worst losses (13 Jul MAE 919; 02 Sep MAE 669; 14 May broken area 271 MAE 684). Check
  whether a parallel's retest is a trade location per §2E.~~ — two lifecycle bugs FIXED (see "Reading checks — E4a and E4b" below).
- **§1 MTF agreement / E3 CHoCH:** 09–11 Jun visits of areas 280 / 288 gave 6 stops out of 6 while the 15M read "trending up".
  **Checked — the model gating follows the method; one evidence-wording fix (§1 MTF state).** (a) Which timeframes must agree: only
  the Daily side (§2 b, P4: "trade in the direction of the higher-timeframe trend"; a correction does not change the Daily trend).
  Daily was DOWN (correction in progress, protected LH 61,764.85), so these are pullback entries at 1H supply inside the Daily
  correction — the side question is the already-logged "Daily DOWN for six months" item for Abhi's eye (§1 / §2B), not this one.
  The 15M is the pullback timeframe (§2 d): a pullback into a bear-call area is by definition going up on 15M; the MTF state /
  agreement is evidence only (T1 "never enters, blocks or grades"; CLAUDE.md "evidence is listed and never blocks"; DECISIONS 6).
  (b) When the pullback shows weakness: §3 / §4 "LTF still trending against ⇒ no entry" is the 5M CHoCH after entry into the area,
  which E3 requires — all three E3 entries had it (09 Jun 10:40 close below HL 54,639.45 after arrival 09:25; 10 Jun 12:35 below
  55,419.20 after a sweep of 55,534.65; 11 Jun 13:10 below 55,470.15 after a sweep of 55,600.15). E1 (Aggressive) is the first touch
  of the refined base without LTF confirmation by Abhi's own model definition (21 Oct, DECISIONS 6) — its 5M read "trending up" on
  10 Jun 10:45 is listed, never a gate. (c) The 6 / 6: the 1H impulse up kept running (1H HL 53,843.30 → the Daily correction
  extended to 55,600+); P5 / P7 — a valid read can lose; no rule from one cluster. (d) **Evidence misread fixed (§1 MTF state;
  DECISIONS 16 range = price fails to make a new extreme on BOTH sides; T4 a break is real only by a close + a swing beyond):** on
  09–10 Jun the 15M read "range 53,843.30–54,865.50" (D1: LH 54,455.20 + HL 53,949.90) while price closed above 54,865.50 on 09 Jun
  and traded 600 pts above it with no D1 swing formed beyond. The state stays "range" (no confirmed break), but the detail now says
  "closed above its high 54,865.50 since the last swing — no swing formed beyond it yet (not a confirmed break)"
  (`mtf_state._range_left`, wording only; entries unchanged; tests/test_pa_mtf_state.py). Note (review of #373): the wording
  applies to the range detail of EVERY timeframe (it runs inside `swing_state`), not only the 15M — the commit message of 0720c16
  says "15M range detail"; that is the case it was found on, the change is per timeframe.
- **For Abhi's eye (§1 / §2B, not logged as a bug):** all 69 entries are bear calls — Daily DOWN for six months (protected LH 58,706
  never taken); the 52,877 → 58,673 up leg read as "correction in progress"; the largest move with no entry is up 3,961 pts.

## Reading checks — E4a and E4b (BANKNIFTY galleries; checked against CLAUDE.md, DECISIONS 3, 9, 12, 23, 27, 28, method §3 / §8, KB K6.5)
Replay: the walk-forward runner on the branch head (b74e832 → this fix), 13 groups 13 Apr – 21 Oct; 12 groups reading-only (no
near-month FUT volume, REPORT_STANDARD 0a: E2 / volume not evaluated) + 07–21 Oct testable (FUT on every session, live rule). Outcomes
by structure across sessions (next opposite area first vs a close beyond the invalidation first). The two warm-up groups (13 Apr –
9 May: the 15M history starts 13 Apr, so the swing engine has no finest swings yet) give no entries either side.
- **§3 E4 (a) — not a bug; the method had no qualifying case.** Funnel over the 101 armed trade-side area visits (after warm-up): 55 had
  a push beyond the far edge / a K4 sweep event (34 with a close beyond, then back inside — the CLAUDE.md "Sweep / fakeout" read is
  correct in levels: `sweep` events, area alive, visit continues). In none did the E4 (a) read complete: 46 visits ended (or the area
  broke) before the NEXT PUSH formed as a confirmed swing of the finest structure (D1) after the sweep; 3 sweeps failed (price went
  beyond the sweep extreme later — then the K4 break / flip, not E4 (a)); 6 visits ended at the poke itself (no later bar). So the
  trigger-stage checks (traded inside the area, into the refined base, not beyond the sweep extreme) were never reached. Example 22 May
  1H 53,963.10–54,109.15: five closes above (high 54,213.05), back inside at 14:00 = K4 sweep; the later push (15:15, high 54,193.00)
  stayed under the sweep extreme but is no D1 swing (and closed above the far edge), and the 25 May gap broke the area. Code =
  method: E4 (a) at `entry_models.Reader.sweep` reads "the next push" as a swing of the finest structure (method §3: a swing is a
  turning point the structure respects; small wiggles are not swings; Abhi's D1 / D2 calibration). Assumed — no answer needed unless
  Abhi objects. For Abhi's eye (not a rule): a D1 swing is usually larger than a narrow 1H band, so a failed push inside a sweep of
  such a band rarely completes before the visit ends — E4 (a) will stay rare on BANKNIFTY by this reading. Never tuned.
- **§2E lines / channels: a parallel's retest IS a trade location (not a bug in itself).** Abhi's own order (INBOX C-11, C-b / C-f: "B's
  line of highs (or its channel parallel) BROKEN by K6.5, then the retest of that broken line … = E4 (b)") makes a broken channel
  parallel an E4 (b) object; its break is K6.5 (`channels` → `_broken_at`: a close beyond + a swing of its kind beyond).
- **FIXED — C lifecycle / K6.5 mirror for a BROKEN LINE (E4 b object; DECISIONS 23 + 27).** Was: a broken line (main line or channel
  parallel) stayed an E4 (b) retest object whatever price did after its break — the lines had no lifecycle (areas have reclaim /
  dead). E4 (b) reads a broken line as a flipped object ("close beyond + swing beyond = broken (flip)"), so a broken line that price
  closes back through on its ORIGINAL side AND builds a swing (of the line's degree) beyond it there has its break undone — the
  mirror of a BROKEN area's reclaim (levels: a close back on the role side + a swing formed there), read the same way as Levels: the
  closes back must hold until that swing is CONFIRMED (the confirming bar may itself close back); a close not back before the
  confirmation ends the attempt (a sweep of the retest — the line stays broken). Once undone, never an E4 (b) object again
  (`trendline.broken_back_at`, read in `Reader.broken_objects` for every E4 (b) line object — model C's C-b / C-d / C-f lines too,
  model C stays OFF). No new setting, no number. (Review of #373: the first version counted a run of closes back that only reached
  the swing's bar, not its confirmation — fixed, with the sweep-retest case as a test in both mirrors.) The two
  replayed worst losses were this: 13 Jul 09:15 (1H parallel D2:H+:1025-1123|par, broken down 23 Jun 14:45, closed back above from
  24 Jun 09:15 with the swing high 58,706.10 (25 Jun) — broken back the next day; the "retest" 3 weeks later was the rising line
  catching up with price, entry 57,596.30 after a gap, 449 pts from the line, MAE 919) and 02 Sep 11:15 (falling line of lows
  D2:L-:1177-1279, broken down 19 Aug 09:30, closed back above 19 Aug 13:30 + the swing high 57,873.80 (24 Aug): price came onto the
  line from ABOVE, MAE 669). The other removed E4 (b) were all broken back before (or at) their trigger: 20 May 13:15, 30 Jun 14:00,
  08 Jul 09:15, 13 Jul 10:30, 20 Jul 09:15 and 14:15, 07 Sep 09:15, 24 Sep 13:45. Tests: `tests/test_entry_models_broken_back.py`
  (both mirrors). ~~Display only, not changed: `channels()` still labels such a line "retest of the broken … line"~~ — FIXED
  (display): `trendline.channels_on` reads the same K6.5 mirror (`broken_back_on`, the core of `broken_back_at`, any timeframe's closes
  and swings) and labels such a line "<lower|upper> line broken, then broken back (closed back + a swing on its original side)", never
  a retest; `broken_side` / `broken_lines` unchanged. `broken_back_at` = the same reading (refactor only; replay parity below). Test:
  `test_channel_label_follows_broken_back_at` (both mirrors, incl. the sweep-retest case).
- **FIXED — K4 reclaim on the break's own confirming bar (levels, layer 2 lifecycle).** Was: when the bar that makes a break KNOWN (its
  swing beyond confirmed) itself closed back on the role side, the reclaim attempt ("a close back on the role side AND a swing formed
  there", the break's mirror) began only at the next bar, so a swing formed AT that bar was lost and the area stayed BROKEN. Now that
  close starts the attempt (`Levels._step_far_swing`). Replayed: 14 May 1H support 53,492.10–53,510.45 "broken" at 09:15 (the swing low
  53,385.45 of 13 May 15:15 confirmed by the gap-up bar that closed at 53,924.40, swing high 53,968.65 there) — now reclaimed at 09:45,
  so no E4 (b) bear call from above at 10:30 (was MAE 684). Only this entry changed across all groups (E1 / E2 / E3 identical);
  the chart band labels (`levels.band_flip_facts`, facts.validity breaks) are a separate reader — ~~not checked for the same
  case~~ CHECKED, does not depart (display): its breaks are the band check's own (known at their own bar — no later confirming bar),
  and a break back the other way is a reclaim from the very next bar on (the far swing checked first on that bar, as the engine).
  Nothing to mirror; pinned by `test_band_flip_facts_reclaim_on_the_bar_right_after_the_break_is_kept`.
- **Process — STABLE layer 2 (docs/reader/STABLE.md).** The K4 reclaim fix is in the layer-2 lifecycle (`reader-layer2-stable-v1`).
  The trade-data parity snapshot (`parity/layer2/reader-layer2-stable-v1/`) was NOT re-exported (a fix = a new tag, `-v2`, only after
  Abhi's ✅). Read-only check (outputs kept in scratch, nothing written to trade-data): the layer-2 output on the four parity cases
  (NIFTY / BANKNIFTY, real + mirror; 1,776 / 1,575 bars) is IDENTICAL before (0720c16) and after this fix — 0 records differ; the
  fix can still change other charts (it did on 14 May BANKNIFTY). Found while checking: the stored stable-v1 outputs already differ
  from the pre-fix code on every record (band lo / hi / width / anchor / lineage — later band changes merged after the tag), so the
  layer-2 parity fixtures are stale independent of this fix; a `-v2` export needs Abhi's ✅.
- **Before / after (same data, same outcome rule).** Per model, all 13 groups — entries (next first / invalidation first):

  | model | before | after |
  |---|---|---|
  | E1 | 25 (8 / 17) | 25 (8 / 17) |
  | E2 | 2 (2 / 0) | 2 (2 / 0) |
  | E3 | 19 (12 / 7) | 19 (12 / 7) |
  | E4 a | 0 | 0 |
  | E4 b | 28 (14 / 14), worst MAE 918.8 | 17 (10 / 7), worst MAE 590.8 |
  | all | 74 (36 / 38) | 63 (32 / 31) |

  Changed groups (E4 b): 10–24 May 3 → 1 (14 May, 20 May out), 24 Jun – 8 Jul 3 → 1 (30 Jun, 8 Jul out), 9–23 Jul 6 → 2 (13 Jul ×2,
  20 Jul ×2 out), 23 Aug – 6 Sep 2 → 1 (2 Sep out), 7–21 Sep 3 → 2 (7 Sep out), 22 Sep – 6 Oct 6 → 5 (24 Sep out). Removed: 7 that
  hit the invalidation first, 4 that reached the next area first (P7: a valid read can lose; these were not valid reads). 07–21 Oct
  (testable, live rule): 14 (9 / 5) before and after — unchanged.

## C lifecycle — a flipped area broken again (owner-orders DECISIONS 27; code `flip_dead_rule = broken_again`)
- Was: a FLIPPED area broken again stayed BROKEN until that break's far-side swing was reached, and E4 (b) used it as a retest
  object (07–21 Oct: E4b on 282 / 283 / 282 / 287 — all four flipped once and broken back by close + swing beyond before the retest).
  Now DEAD at the second break. The earlier reading stays as the what-if `flip_dead_rule = far_swing`.
- ~~Open (display only): `levels.band_flip_facts` still marked DEAD only past the far-side swing~~ — FIXED: it mirrors
  `flip_dead_rule` (default `broken_again`: DEAD at the first confirmed swing beyond the band after the second break; `far_swing` what-if
  kept and pinned in the older band tests). Note (review, low): the chart callers pass facts settings, so a dashboard
  `flip_dead_rule = far_swing` override reaches the engine but not the band labels (they stay on the default); carry it over if ever used.

## Handover pack (new account) — questions with provisional defaults (checked against DECISIONS / CLAUDE.md)
- **Where OPEN_QUESTIONS lives.** The pack names `docs/OPEN_QUESTIONS.md`; the repo's file is this one. Provisional: keep this file
  (no second list). Assumed — no answer needed unless Abhi objects.
- **PR order vs one working branch.** The session pushes only to `claude/hopeful-gates-hf186c`, which already carries #367 (T-2 + the
  trigger follow-up, T-4) + its CI fix + the naked-card part of T-6. Abhi wrote "Merge". Provisional: the STEP 0 docs ride in that
  same PR (order 1 + 3 together), merged on green CI + independent review (DECISIONS 24); T-1 / T-5 / T-6 follow as the next PR
  from the same branch restarted on main. Nothing is lost; the order only joins two PRs.
- **VPS commit.** Last status Abhi pasted (per the earlier handoff): `bf98040` (#365), ✅ clean. #367 has never been deployed.
  Provisional: treat bf98040 as live until Abhi pastes `./deploy status`.
- **T-1 / T-5 reports need the VPS database** (vision_signals / vision_events, Telegram message ids, the chart image Vision got). The
  session cannot read the VPS (CLAUDE.md). Provisional: one read-only export block for Abhi (after close); the fixes are built and
  tested meanwhile; the reports are written when the export arrives.
- **T-4 INTRADAY vs two-day holding.** Abhi's decision; the current dashboard setting stays. Replay numbers for both are not
  available yet (the replay measures outcomes by structure, not by holding style).
- **T-4 Fyers `fno_historical_data` probe.** Needs Abhi's own Fyers account / token; not run. Forward FUT collection continues.

## T-5 — Vision audit of engine signals (owner-orders DECISIONS 31, PROVISIONAL; checked against CLAUDE.md / DECISIONS 4, 8, 22, 23 / method §1 P1–P2, §6)
- **Root cause (confirmed in code).** `signal_source = engine` entries (paper/engine_entry.py, tags `engine: True`) went through the
  level-bot audit: vision/chart.render drew the old card (thick L line "L RESISTANCE · held R / reclaimed", PDH / PDL / PDC, PWH / PWL,
  OPEN + the opening-range band, gap bands, session separators) and vision/signal_audit.audit (`signal_check_v2_2`) sent the level-bot
  playbook + signal text (L line approach / today's role, "Time: N minutes since the open", gap class G0–G5, fill %, event day).
  `code_verdict` takes the stricter of Vision's verdict and a code floor from DISAGREE_RULES / GRAY_RULES; the code-fact rules
  (`opening`, `gap_chase`, `gap_b_pdc_accept`, `wrong_approach`, `role_conflict`; gray `event_day`, `gap_undecided_early`) fire from
  the context alone, so a session / gap / clock fact could floor an engine signal to "disagree" whatever its engine reading.
- **Provisional default (built).** Vision setting `vision_engine_audit = engine` (`legacy` = the old audit, what-if): engine signals get
  the engine card (vision/engine_card.py: area faint / broken object dashed, refined base strong, trigger "T", INV, NEXT, HTF strip;
  no L line / reference levels / opening / gap / separators), the engine facts text and the method's concept checklist (trend side,
  area lifecycle, visit, trigger in the refined base, invalidation side, model rule, evidence — evidence never decides); the floor is
  only Vision's own checklist; the old rules are stored and shown as "Context only (old level-bot rules, not in the verdict)".
  Level-bot signals are byte-identical (pinned test). Vision stays advisory (human_confirm, reduce-only). Assumed — no answer needed
  unless Abhi objects; reviewed with the "Vision agreed / disagreed / gray × result" table (Vision page).
- **Next area.** The engine row carries only trade-side areas (watch list), so the engine's opposite "next area" is often absent.
  Provisional: next area = the nearest alive opposite-role engine area beyond the entry; none ⇒ the chart band finder
  (decision3.levels.display_bands at signal time, labelled "chart band finder"); none ⇒ "none known" and the outcome follows the
  invalidation only. Open (display / measurement only): the engine payload could carry its own next opposite area.
- **Report of the L22,747 card** still needs the VPS export (vision_signals / vision_events); written when it arrives.
- **T-1 finding: no shadow trade opens in approval mode.** With `approval_required` = True (the PAPER default), a rejected / no-reply
  V1 signal becomes only a would-have note (`paper_would_have`, lots 0) — `vision/gate._shadow` returns HOLD; the one-bot engine path
  never opens a shadow position either. That is why no `srv2_momentum_reversal_vision_shadow` trade exists. Provisional: behaviour
  unchanged (opening shadow trades would be a new execution behaviour Abhi did not state); the cards now say it in plain words
  ("No shadow trade: approval mode keeps only a would-have note …"). Abhi decides whether approval mode should open comparison-only
  shadow trades.
- **T-1 review notes, logged (low, not fixed here):** (a) a card still pending from a previous day expires with
  `transition_notified=1` and gets no outcome line / reply (its buttons stay; a press answers "आधीच ठरलं") — same as before T-1;
  (b) `vision/notify.post` reads and rewrites `tg_outcome` without a lock, so two processes posting different outcomes for one signal
  at the same instant can drop one line from the card history (each reply message is still sent).

## T-3 model C (counter-trend C leg) — coverage questions (2026-10-22)
- Q1–Q11 with their provisional defaults are in `docs/reports/model_c/COVERAGE.md` §4 (assumed — no answer needed unless Abhi objects).
  The ones Abhi may want to see: Q1 (model C needs DState.trend DOWN; `rev` / Weekly fallback ⇒ none), Q2 (method P4 / Vision
  `trend_side` vs DECISIONS 32 — model C only), Q6 (a flipped area inside A is not C-a; the C-f switch only labels), Q7
  (`c_projections` default (1.0,), display only), Q8 (15M-only channels are not E4 (b) objects).

## T-3 model C — step 2 (built behind the switch, default OFF) (2026-10-22)
- **Conflict for Abhi: method P4 vs DECISIONS 32.** P4 says "never a counter-trend entry"; DECISIONS 32 (Abhi's later order, T-3) adds
  model C, a counter-trend C-leg entry. **Provisional: DECISIONS 32 wins for model C only** — P4 stands unchanged for E1–E4 on the
  Daily side. Written into CHART_READER_METHOD §8 ("Model C" bullet) and into the Vision engine audit: the prompt names the one
  exception (PROMPT_VERSION `engine_check_v2`) and a model C card's facts carry its own trend-side rule (Daily side the other way, a
  1H CHoCH began A, B corrective and in progress, not dead), so `trend_side` is not failed for being counter-trend. Vision stays
  advisory (human_confirm). Assumed — no answer needed unless Abhi objects.
- **C-e window.** Appendix A: "With C-e ON, c_window = b_and_ha_retest". Built so: with the C-e switch on, the first return to HA is
  open for the C-e objects only (HA's own area BROKEN ⇒ E4 (b); FLIPPED ⇒ E1–E4 at it), whatever `c_window` says; the other sub-ways
  keep the B window. The first return = the first touch of HA's band after the C push away (a finest-structure swing beyond the band,
  confirmed) and it ends at a new swing that does not reach the band (the RC4 revisit rule). The break candle of HA is never an entry.
- **c_pullbacks (what-if only).** Read as the B window PLUS C's own pullbacks after the close beyond HA, at 1H areas whose base lies
  from B's end on, until a 1H CHoCH back to the Daily side (C's end by structure). Provisional; never a default.
- **Engine vs dashboard defaults.** Engine `model_c_subs` default = all six (the replay reads every sub-way when `model_c = on`); live,
  every dashboard switch (`engine3_model_c_on`, `engine3_model_c_<a…f>_on`) is OFF by default and passes its own subset.
- **C-f** labels a Daily-side entry (`model_c_context.sub_model = C-f`) when its area overlaps the end zone's first Daily / Weekly area
  (or it is an E4 (b) on a line anchored inside C) after C left HA; the entry, its tag and its statistics slot stay the Daily side's.
- **Row decision.** A bar whose only fired entries are model C keeps the Daily-side decision text; the C entries are in `entries`
  (the live path reads them there) and the cycle in `model_c`.
- **B read early.** B's nature is read on the closed 1H candles after HA's; until one exists B reads NA ⇒ the models wait. If B reads
  mixed / NA on a visit's first bars, E1 cannot fire in that visit (the window starts later) — E2 / E3 / E4 can (Q9).
- **Hidden divergence pair (coverage C-8).** The context line reads `rsi_hidden.read_hidden_divergence(V, t, d)` as it is; the explicit
  (O, B-low) pair frame was not added (it needs a real-data case to compare; step 3 replay).
- **Review fixes (PR #370).** The Vision engine audit keeps `SYSTEM_PROMPT` and `engine_check_v1` byte-identical for every non-C card;
  only a model C card gets a second system block (`MODEL_C_SYSTEM`) and the version `engine_check_v1+c` (audit, validate and the
  worker's reuse lookup). HA's area is read as known at t (born by t, alive at t); when HA's own birth fell inside an alive band
  (lineage only, `Level.inside_bases`), that band is the area at HA; no such level ⇒ no C-e object (C-e waits; logged here as the
  provisional reading). `c_window = b_and_ha_retest` opens the HA first return for the C-e sub-way only (without C-e it reads as
  b_only). c_pullbacks opens from the bar after the HA break. An unreadable `engine3_c_projections` falls back to the default with a
  warning (display only — never stops the engine).

## T-3 step 3 — model C replay, BANKNIFTY 07–21 Oct (code 0d7813e; trade-data review/replay_banknifty_6m/model_c/0d7813e/)
Testable (near-month FUT on all 9 sessions). Model C OFF = 14 Daily-side entries (9 / 5), equal to the #367 "after" column; ON (both
windows) = the same 14 + C-f labels, **0 model C entries**. Golden check (the 1,357-pt up move 12–15 Oct): no C-a / C-b / C-e entry.
Logged as reading differences against named concepts — never tuned:
- **C-3 / method §3 CHoCH (`mtf_state.dow_events`):** after the 08 Oct CHoCH down the next 1H high (55,419.30) was a higher high, so
  the 1H never read DOWN; the 13 Oct close above 55,419.30 reads as a 1H BOS up, not a CHoCH up ⇒ no wave A by C-3.
- **§1 degree of A / HA / B:** Abhi's A → HA → B (54,708.8 → 55,644.7 → 55,168.2) are 15M swings; there is no 1H swing between
  54,708.80 and 56,065.50, so at 1H degree HA would be C's own end and the B window could not open before C. Question for Abhi: is
  model C's A / B read at 15M degree (the setup degree) rather than 1H? Provisional: unchanged (1H, as Appendix A C-3 says).
- **C-5 area set / lifecycle:** B ended inside 1H area 54,886–55,193, which the engine reads FLIPPED (a supply broken up on 09 Oct, then
  tested as support; base 05 Oct, before A); Abhi reads a TESTED 1H demand. Provisional: a flipped area is not a C area (Q6).
- Holds: B on lower FUT volume than A (12,863 vs 25,882 per bar); C ended just under the top of the Weekly area 54,891–56,099; the
  earlier up move (07 Oct) has no model C entry (inside the older cycle, window closed — not by the C-4 death).

## Chart Reading Report (owner-orders DECISIONS 35; branch `chart-reading-report`) — provisional choices, checked against DECISIONS / CLAUDE.md
Checked against: DECISIONS 1, 2 (no reading number — every value in the message is a reader fact; the only constants are the Telegram
platform limit and display windows), 4 / 8 (Vision information only, never a gate), 9 (Z-1u: overlapping areas counted once, never
merged — said as a reading check), 13 / 26 (FUT volume missing is said, never spot volume), 14 (P8 clean charts, `chart_max_lines`),
27 (dead areas never drawn), 32 / 34 (model C stays OFF; the other side says "only via model C (OFF)"), 35 (the order), CLAUDE.md
(no day / date / session framing in the reading; no paid call without approval; PAPER untouched; private charts never in this repo).
- ~~**CRR-1 report default OFF.**~~ — RESOLVED by Abhi (DECISIONS 36): `chart_reading_report` and `chart_reading_vision` default **on**; Vision budget
  $5 / day (provisional with it: monthly 100, visual-audit sub-cap 2.0 — the settings' maxima). Both can be switched off on the dashboard.
- **CRR-2 detail.** `short` (default) = each section's main lines (≈ the order's layout); `full` = every line, still one Telegram
  message (extra lines dropped bottom-up when too long, then whole sections; the plan and the link always stay). Length counted in
  Telegram's UTF-16 units. The full detail (every armed area, every overlap group, every pattern, every concept's facts) is the page.
- **CRR-3 Vision default OFF.** `chart_reading_vision = off`: no new Vision spend without Abhi's word (CLAUDE.md). When on: the existing
  Dual-Eye auditor (prompts / schemas unchanged), timeframes Daily + 1H (run_visual_audit's default), the same budget gate
  (`make_allow`) and cost record (`record_usage`, task visual_audit) — the caps are unchanged.
- **CRR-4 duplicates.** The auditor's JSON schema has no duplicate field (kept unchanged for the old audit), so the duplicate check is
  the reader's own comparison (alive areas of one timeframe and role whose bands overlap = one place), reported in Vision's section
  and in the Areas section as a concept C / Z-1u reading check.
- **CRR-5 selection words.** The message names: the nearest and the next trade-side area (the engine's watch list), the next opposite
  area, the nearest Daily / Weekly area above and below (and any one price is inside), the overlap groups at those places, the
  channel price is in, the next line above / below, the latest pattern (full: + the patterns whose boundary is next in the path),
  the latest RSI pair per side. "Nearest / next / latest" are comparisons; everything else is on the page.
- **CRR-6 Daily candle after the close.** At the close run the day's completed Daily candle is included (the next session's engine
  reads it); the pre-open refresh reads the same bars (nothing new overnight) and lists what changed against the stored close facts.
- **CRR-7 schedule (operational).** 15:50 IST close run, 09:05 IST pre-open refresh (`scripts/install_chart_reading_schedule.sh`). The
  old `run_visual_audit.py` cron (16:20 IST) is unchanged: it still audits the old Opportunity Engine levels (its message is now off
  by default, the data is on the page). Whether to stop that old audit (cost) is Abhi's decision.
- **CRR-8 charts.** Weekly + Daily in one PNG (two columns); the RSI panes use the reader's RSI period (display); divergence pairs come
  only from the reader (rsi2 15M D1 / D2 pairs, drawn on the 15M and, by time, on the 1H chart) — no Daily / Weekly divergence reader
  exists, the pane says so. P8 on these charts: the channel price is in (the one through the latest swing), the next line above /
  below, the latest pattern's boundaries, capped at `chart_max_lines` (no entry ⇒ no evidence line).
Reading checks seen in the sample (19 Oct close; never tuned — misread candidates against named concepts):
- ~~**§1 MTF vs L range.**~~ — FIXED (bug against §1 market state / concept L, DECISIONS 16; evidence words only). BANKNIFTY 1H at the 19 Oct
  close: `mtf_state` read "correction in progress (UP)" while `range_edges.range_state` read a 1H range 53,786–56,624 on the same D2
  swings (15M the same: "correction (DOWN)" vs range 55,168–56,066). Not two questions: both answer "what state is the 1H in", and
  `mtf_state` read "range" on 1H / 15M only from the last two highs / lows (HH + LL, LH + HL or C-13 equal) — the C-13 reading
  DECISIONS 16 retired ("range = from structure … not C-13 equal"); it never saw the OUTER pair (swing high 56,623.80 / swing low
  53,785.70) whose later swings all failed on both sides. The swings inside it (HL 54,709 → HH 56,066, then the counter-move) are the
  range's inner swings, not the 1H trend. Fix (`mtf_state._structural_range`): on 1H / 15M the word "range" comes from the one
  structural reader (`range_edges` pairs, `daily.range_at`, known ≤ t) with its edges; the inner swings stay in the detail ("inside it
  the swings read correction in progress — …"); a swing disagreement (HH + LL / C-13 equal) with no structural range in force is no
  range ⇒ "unclear" (no trend structure). D / W already used the DState structural RANGE; 5M has no structural range reader
  (unchanged). Evidence only (mtf_state never enters / blocks; pa_evidence + legs_compare + the report read it) — entries unchanged
  (replay parity below). Report now: "1H: range · 15M: range". Tests: `tests/test_pa_mtf_state.py`
  (`test_swing_tf_range_word_comes_from_the_structural_range_reader`, `test_mtf_range_word_agrees_with_range_state_on_every_bar`).
- **C / Z-1u overlaps — not a bug (separate births).** NIFTY supply #271 / #273 / #274 (23,116–23,178): #271 = the D2 swing low
  23,118.60 (its own 1H candle), #273 = the next D2 swing low 23,116.10 (a different 1H candle, a D2 swing high 23,281.15 between
  them = two separate reactions, a double bottom), #274 = the BOS-origin base (birth b) the impulse left from that low (the next up 1H
  candle's wick to body, DECISIONS 15 / C-1). Each band is its own candles; none lies wholly inside another (⇒ own level + lineage
  "overlaps", Z-1u, `Levels._born`); their lifecycles differ (#274 broken / flipped on its own bar, #271 / #273 later). BANKNIFTY
  #341 / #342 / #345 the same pattern (D2 swing high 55,340.70, its BOS-origin base on the next 1H candle, a later D2 swing high
  55,419.30). No duplicate birth; counted once per model per place (DECISIONS 9), never merged. Assumed — no answer needed unless Abhi
  objects.
- **C width (Z-1x) — not a bug.** NIFTY Weekly demand #247 21,281.45–23,290.15 (birth a:W-prior, not a BOS origin) = the swing week's
  own candle, wick to body: open 23,337.90, high 23,338.70, low 21,281.45, close 23,290.15 — a lower wick from the low to the body's
  bottom (the close) of about 2,000 points. The band rule (TA4 / Z-1x: wick to body, never a numeric width) gives exactly that; a
  width limit would be a number in a reading rule (DECISIONS 2). Weekly = context only (Z-1u). The week is inside the sealed holdout
  period — read only as level history (Z-1t), its date not shown.
- **Replay parity (the two fixes above + the channel label).** BANKNIFTY walk-forward, 13 groups 13 Apr – 21 Oct, base 806b74a vs this
  branch, same outcome rule: every entry identical (56 = 56, same trigger / model / entry / invalidation / outcome / area). Per model
  (entries, next first / invalidation first): E1 25 (8 / 17) · E2 2 (2 / 0) · E3 19 (12 / 7) · E4 a 0 · E4 b 10 (5 / 5), worst MAE
  590.8 · all 56 (27 / 29) — before and after. The 15M decide rows of the `abc` fixture differ only in `channels[].state` and
  `pa_evidence` text (key-by-key diff; `tests/test_trigger_5m.py` pins re-hashed with that note). STABLE layer 4 (lines):
  `broken_back_at` behaviour unchanged (refactor into `broken_back_on`); only the channel display words changed.

## PA T3 (channels per timeframe) + T9 (evidence wiring) — provisional choices (2026-10-22; docs/knowledge/pa_standard/t3_t9_coverage.md)
Checked against CLAUDE.md ("evidence is listed and never blocks", no number / rule / setting added, P8 display only), DECISIONS 3, 5, 6,
7, 9, 14, 28, 35 and the method doc §8. Assumed — no answer needed unless Abhi objects:
- **T3-1 5M has no lines / channels.** The 5M swing in the reader is the LTF-CHoCH trigger definition (a high above its left neighbour),
  not a structure swing; lines on it would read wiggles (method §3). Lines / channels are read on W, D (their own candles and the fold's
  swings, the ones `mtf_state` reads) and 1H / 15M (the existing two degrees of the 15M chart, unchanged).
- **T3-2 Daily / Weekly channels are evidence only.** Their broken lines are NOT E4 (b) retest objects (that would add trade locations
  ⇒ new entries; Abhi's word + a replay first). The row carries them as `channels_htf`.
- **T9-1 hooks not wired.** `patterns_pa.retest_levels` (`PATTERN_HOOK`, E4 b) and `range_edges.armable` (range edges as armed areas)
  change entries — a reading change, not evidence. Left off; listed for Abhi.
- **T9-2 Vision input unchanged.** The PA list goes to the entry (`pa_evidence`), the payload (first fact per track) and the approval
  card (one line, the first detail dropped when the caption is full) — not into Vision's prompt (its input and paid size as before).
- **T9-3 selection = identity only.** The area's own base / confluence / inducement by its id; liquidity = the reader's own "nearest"
  extremes; channels = the one price is in, a retest of a broken line, a counter channel broken in the trade direction; range edges =
  overlap with the entry band. No ranking, no score.
- **T8 objects into the gate tags** (`chart_objects`, default off): still open (display, a separate item).

## Live reading check — BANKNIFTY E4 (b) bear call at a broken line (owner-orders DECISIONS 38–41; report docs/reports/live_e4b_check.md)
Checked against CLAUDE.md, DECISIONS 6, 23, 27, 28, 38–41, method P4 / §8 (T7, E4 (b)), H2.
- **FIXED — E4 (b) approach side (DECISIONS 38).** Was: no read of where price came from; a candle opening on the object's original side
  and closing through it (a breakdown, H2) passed as the rejection. Now `Reader.approach_side` (`e4b_approach_rule = break_side`; `any`
  = what-if): the close before the revisit's first bar and the open of the rejection form's first candle are not beyond the original
  side. Replay: E4 (b) 17 → 10 (7 removed: 5 next first, 2 invalidation first); E1–E3 identical.
- **Covered — lines dead after a second break (DECISIONS 39 / T-2).** `trendline.broken_back_at` (#373). The live VPS (last confirmed
  deploy c3e9f0a) most likely ran without it — the VPS command in the report prints the commit. For Abhi's eye (no change): the swing
  that undoes a line's break is read on the line's own degree (1H); 15M swings alone keep the line broken.
- **FIXED — range edges as areas (DECISIONS 40).** Was: range read as evidence only, edges never armed (`armable` hook unwired). Now
  `range_edges.trade_edges` ⇒ `Reader.range_edge_areas` (`range_edge_areas = on`): current Daily / 1H range edges, trade side only.
  Replay: no new entry (the outer ranges were never visited). Provisional, assumed unless Abhi objects:
  (a) **15M range edges are not armed** (15M = the setup TF of the refined base / trigger; areas are 1H / Daily context);
  (b) **the counter-trend edge is not armed** when the Daily is UP / DOWN (P4; with a Daily RANGE both edges are);
  (c) **the outer range only** (T7, 21 Oct: "the range in force = the oldest such pair not broken"): an inner range inside it (e.g. the
  broken line ↔ an upper edge rejected several times) is not read as a range — question for Abhi: should the newest (inner) range of a
  timeframe give the edges too?
- **Not a bug — evidence ✗ / label None on an E4 (b).** Evidence never blocks (DECISIONS 6); the missing part of the E4 (b) form was the
  approach side (fixed above).
- **FIXED — card / Vision text for a line (DECISIONS 41).** `entry_line` tag (tf, degree, family, break side, value) ⇒ "broken 1H line at X
  (…, broken down), retest from below"; header symbol first; engine name "Price-action engine (PAPER)" (addition D); Vision prompt
  `engine_check_v2`. E4 (b) lines are always the 1H degree (D2).
- **Live list (item 7):** needs the read-only VPS export (command in the report); the replay list is in the report.
- **Approach side after an overshoot (review M1), PROVISIONAL.** `e4b_approach_rule = break_side` also blocks a rejection candle that
  OPENS on the object's original side right after a single overshoot close from the break side (no swing formed beyond). By the sweep
  reading (DECISIONS 23) that overshoot is a sweep, not acceptance, so such a retest may be a valid E4 (b) from below. Provisional
  default: a rejection candle opening on the original side counts as "from above" even after one overshoot close (no number added to
  separate it from the live case, where price closed above four times without a swing of the line's degree). Affects 2 of the 7
  removed replay entries (03 Sep, 09 Oct: "trigger opened above"). Abhi decides; `any` restores the earlier reading.

## Entry trigger on 5M (owner-orders DECISIONS 37; report docs/reports/trigger_5m_report.md; built 23 Oct)
Checked against CLAUDE.md (trigger reading, sweep / fakeout, refined base, clusters, E4 (b), live safety), DECISIONS 6, 9–11, 21–23, 27,
28, 32, 37–41, method §2 d / e and §3 (models, trigger at the refined base). Provisional defaults (report §11, Q1–Q18), assumed unless
Abhi objects — each is in the code as written here:
- Q1 / Q2 a visit may start on a 5M candle inside the 15M bar in progress; the visit's 5M start = its first 5M candle trading into the
  area; visit id = area @ the 15M bin that contains it (the same id the 15M bar gets once closed); it ends only by 15M structure.
- Q3 E1 = the visit's first 5M candle trading into the refined base known at k(u); that candle closing beyond the base's far edge ⇒ no
  E1 this visit (the base was closed through).
- Q4 / Q5 E2 on the 5M candles: dominant over every other 5M candle of the visit; FUT 5M volume above the average of the approach leg's
  and the visit's opposite-side 5M candles; handover / sharp reversal / absorption on the visit's 5M candles (gating E2 / E3); the slot
  baseline stays a what-if. Method §2 d carries the line citing DECISIONS 37.
- Q6 E3: the trigger is the 5M candle whose close makes the CHoCH, and it must trade into the refined base — not relaxed (a CHoCH candle
  outside the base gives no E3 for that CHoCH; a later new CHoCH in the same visit may).
- Q7 E4 (a): the push = the LTF swing definition of `method.ltf_choch` on 5M (a swing high above the previous candle's high and not below
  the next one's, confirmed at the next candle); a K4 sweep event of the area counts at its 15M close.
- Q8 E4 (b): objects as known at k(u) (`break_known_at`, `broken_back_at`, DEAD); a line's value at a 5M candle at its float position on
  the 15M axis (the child's place inside its bin); the revisit ends by a 15M away swing (mapped to the 5M candle closing that 15M bar);
  approach side (DECISIONS 38) on the 5M candles.
- Q9 the required set (handover + commitment + volume + LTF CHoCH) is read on 5M at the trigger; the confirming pieces / zone read / RSI /
  lines at the last closed 15M bar k; evidence never blocks.
- Q10 model C follows `trigger_tf` (its reads go through the 5M reader); it stays OFF.
- Q11 every-minute cron `* 3-10 * * 1-5` with `--guard` + flock (exits unless the bar closed a minute ago is due and unstored); the
  entry-hours / store-window settings unchanged; in 5M mode the window is judged on the end of the 15M bin holding the 5M candle
  (review #378), so the 09:20 / 09:25 closes are stored with the 09:30 opening bin and 15:05 / 15:10 stay out, as for 15M bars.
- Q12 catch-up: a due run decides every unstored closed 5M bar of the session in order (since = the last stored non-error row); the
  freshness stays `engine_max_age_min`. A 5M bar (spot / FUT) not yet at Upstox fails the cycle closed (error row, retried next
  minute); only that one close missing ⇒ silent retry (no Telegram, review #378), more than one ⇒ the usual error line.
- Q13 / Q14 replay outcomes on 5M closes for both variants; entry time difference counted in 5M candles.
- Q15 groups without FUT: one line each + the reading-only E1 / E3 / E4 comparison "without volume evidence".
- Q16 the 5M history window stays `engine3_ltf_days` = 10; a visit whose first 15M bar has no 5M candles ⇒ its 5M models wait with a
  data reason.
- Q17 built on the DECISIONS 38–41 fix (8ff504e + c1cf6ed). Q18 the card keeps the 15M and 1H panels and adds the 5M trigger panel
  (inset), display only; Vision's bar wait / signal bar / apply_facts read the trigger candle's TF; a 5M card adds a prompt block
  (`engine_check_v2+5m`), SYSTEM_PROMPT unchanged for 15M cards.
- Deploy rollback: `install_engine_schedule.sh --revert` now restores the 15M engine line in place with `ENGINE3_TRIGGER_TF=15m` (the run
  reads the 15M trigger whatever the dashboard says; pre-37 code ignores it); re-running it changes nothing; no engine line ⇒ nothing
  written. The full one-bot revert is only `--revert-all` (deploy_one_bot.sh uses it).
- Logged, out of scope (report §9.12): `zone_entries_today` counts `max_hits_per_zone` by day; CLAUDE.md says per visited area.
- Noted while building (not changed here): on 8ff504e `tests/test_model_c.py::test_switch_off…[oct12_bear]` failed (the DECISIONS 38–41
  rows vs the old pin) — fixed on the branch by c1cf6ed (merged into this build).


## Reading check — Daily trend side over six months (BANKNIFTY regression sample, origin/main 5243383; trade-data `review/fix_proof_gallery/sec6.html`)

Checked against CLAUDE.md (Trading / reading), DECISIONS 1–3, 17, 46, method §1 P2 / P4, §2 b), §3 Structure / Area lifecycle, §8 T1,
STABLE layer 1 (L1-a / L1-b / L1-c). Verdicts only — nothing in the engine changed; no rule, number or golden expectation touched.

- **D-SIDE-1 (concept: Daily trend — Q15 impulse-degree Dow, A1 parent gate, Q49 (a), ABC_FIX 3, trend first). Verdict: correct
  reading by the method, not a bug.** The engine's Daily fold (impulse mode, `daily_leg_read = compare`, `daily_pivot_n = 2`) reads:
  DOWN from 23 Mar 2026 (origin 53,562 closed below + opposite structure, leg (3) 55,554 → 51,324 impulse-natured by comparison);
  8 Apr close 55,704 above the impulse origin 54,146 ⇒ counter-move 49,955 → 55,778 corrective vs the leg it corrects (54,146 → 49,955:
  smaller bodies, more overlap; Daily has no volume, T1) ⇒ same-degree correction (A1), parent 61,765 held ⇒ side stays DOWN (cap B);
  17 Jun HL 52,783 + close above 57,456 ⇒ Daily structure UP ⇒ trend first: NEUTRAL (sessions 18 – 29 Jun, no bear call); a flip
  needed a close above the parent 61,765 — never came; 29 Jun the C top 58,706 lay inside the sharp-fall supply 58,394–59,840 (ABC_FIX
  2) and the close 57,727 was below it (ABC_FIX 3) ⇒ correction ended, new DOWN impulse, protected 58,706; Jul – Oct lower highs (58,597,
  58,248, 58,025, 56,996, 56,066) and lower lows (57,457 … 53,786), no close above 58,706. Bug hypotheses checked, all clean: look-ahead
  (52 prefix folds = the full fold), warm-up (the live 3,650-day cut gives identical 2026 states), stale state (all 3,075 replay rows'
  `trend_used` = the fold's side of the previous Daily close), truncated Daily bars (Upstox D to 9 Oct + complete 15M sessions; no gap),
  the compare reader stuck (re-read at every new counter-move extreme; corrective each time). What-if (display only): judging the
  counter-move against the whole fall 61,765 → 49,955 changes nothing (impulse-natured, but its own inner pullback is smaller than the
  trend's ⇒ lower degree, Q22 ⇒ still a correction).
- **D-SIDE-2 (concept: Swing degree, L1-c `daily_pivot_n`) — information for Abhi, assumed: no change.** The six-month side depends
  strongly on Abhi's provisional N = 2: N = 3 reads the Feb – Apr fall as a same-degree correction of the 2025 uptrend (parent 47,703
  held) ⇒ UP (bull put) all six months; N = 1 reads trend first NEUTRAL (LH 61,679 + close below 59,645) all six months. N stays 2 until
  Abhi changes it on the dashboard (DECISIONS 2; L1-c).
- **D-SIDE-3 (display wording, layer 1 `daily.fold_impulse` why text) — assumed: logged only.** On 29 Jun the why reads "close beyond
  the counter-move's last HL 58,393.55"; 58,393.55 is the sharp-fall zone's edge (ABC_FIX 3 branch), not an HL swing. Wording only;
  the reading is unchanged. A fix (say "the sharp-fall zone edge") belongs to the next layer-1 bug-fix batch with Abhi's ✅.
- **K4-W1 (concept: Area lifecycle — Broken vs Sweep; R5-N01) — verdict: replay warm-up, not a K4 misread.** Area 77 (D resistance
  56,105–56,161) logged "119 closes beyond, back inside" as a sweep on 24 Apr because the replay's 15M history starts 13 Apr and the
  swing engine (swings2, σ over 20 sessions) had NO swing at any degree until 13 May — so "a swing formed beyond" could never be read.
  Sessions before ~13 May (groups 13 Apr – 9 May and part of 10 – 24 May) are structure warm-up and should not count as K4 / E3 / E4
  evidence. Noted (operational, not a reading rule): the replay / live data floor (`len(m15) < 200` ⇒ EngineDataError) is shorter than
  the swing warm-up; live has 90 days of 15M so it is unaffected. Provisional: mark those sessions "warm-up — structure not readable" in
  replay reports.
- **K6.5-R1 (concept: line broken / broken back, DECISIONS 39; R5-N05) — verdict: correct.** The 1H line D2:H+:1148-1262|par broke
  down 30 Jun 14:45 (swing 57,457 beyond); price closed back above from 30 Jun 15:15, but no 1H-degree (D2) swing low formed above the
  line by 2 Jul 14:15 (price rose to 58,242, then drifted down without a confirmed D2 low) ⇒ the break is not undone, the line stays
  BROKEN; E4 (b) correctly waits because the revisit came from above (DECISIONS 38).
- **E4b-G1 (concept: E4 (b) after a gap break; R5-E08) — verdict: correct.** D support 274 (56,024–56,169): the 11 Sep 09:15 bar
  opened below it (a gap = the next candle, P2), the D1 swing low 55,699 was confirmed at 10:00 ⇒ BROKEN (close beyond + swing beyond =
  broken (flip), CLAUDE.md / DECISIONS 23); price came back up to it from below and the 5M rejection closed below ⇒ E4 (b) bear call
  10:25. "No far-side swing known" = no D2 swing beyond from before the break; the D2 flip event follows at 11:00 when 55,699 is
  confirmed at that degree. The elapsed time between break and retest never matters (P2).
- **TA4-B1 (concept: Swing placement → refined base wick to body; R5-N08) — verdict: TA4 applied as written; the thin band comes from
  layer 1, logged for Abhi.** The refined base 56,551.65–56,552.85 is NOT a near-doji: it is the upper wick (1.2 pts) of a strong
  bearish 15M candle (10 Sep 09:30, O 56,551.65 H 56,552.85 L 56,452.95 C 56,464). The swing high was placed on that candle because the
  previous 15M bar (09:15) holds both the swing low 56,252 and (later, by the 1m order) the true high 56,575.15; swings2 keeps one pivot
  per bar, so the H moves to 09:30 with its own high. Assumed (no change; STABLE layer 1): a question for the next layer-1 review —
  should a turn whose extreme sits in the bar of the opposite swing keep that bar's extreme (56,575.15)?


## Layer 6 gallery — output reading checks (BANKNIFTY, 13 groups 13 Apr – 21 Oct; origin/main 855fa7b; trade-data `review/layer6_gallery/`)

Checked against CLAUDE.md (Entry framework, Trigger reading, Clusters / Z-1u), DECISIONS 37, 40, 41, 46, 49, method §5 (the verdict, the
evidence list, the A / B label; "every price in the output must exist in the data"), L6-a, L3-c3, L3-n, BW-1 / C-18, VP3. 53 entries
(E1 22, E4 (a) 11, E4 (b) 10, E3 9, E2 1; label A 1, no label 52 — the required set reads absent; 12 groups reading-only, FUT volume
missing; 07–21 Oct FUT-testable). Per entry the engine's entry (E) was compared field by field with the stored payload (P), the Vision
row tags (T), the real card text (classic = dashboard default, and summary), the real engine card image + Vision facts text (F), the
facts dossier at the same bar (D) and the gallery chart (G). Fix: worktree branch `l6` (8ec561e + 50f3a9d) — **awaiting Abhi ✅**, not merged; the
engine's entries are identical before / after (53 / 53). Display only: no reading rule, no decision, no number.

- **L6-O1 (concept: C areas — the target is the next opposite area; engine card + Vision facts). Bug (output), fixed.** 53 / 53: the
  card's "NEXT" / the facts' "Next area in the trade direction" came from the chart band finder (facts.validity) or said "none known",
  never the engine's own next opposite area (the tags carried only the trade-side areas: payload level + watch list). Fix: the live
  decision attaches to each entry its next area as the engine reads it (`engine3_live.next_area_of`: the nearest alive trade-location
  area of the opposite role beyond the entry reference, at the decision's 15M bar) ⇒ payload entry `next_area` ⇒ tags `gate.next_area`
  ⇒ engine_audit.reading; none ahead ⇒ "none known"; the chart band finder stays only for an older row without it.
- **L6-O2 (L6-a label rule — Vision facts). Bug (output), fixed.** 53 / 53: facts_text printed "| label E1 — Aggressive" (the model's
  name in the label field); the A / B label (rd.grade) was never printed (L6-53, E2 label A). Now "| label A (the required set + at
  least one confirming piece)" / "| label B (the required set only)" / "| no A / B label (the required set reads absent)".
- **L6-O3 (L6-a — the classic card, dashboard default). Gap, fixed.** The classic card had no A / B label line at all (summary only).
  The evidence line now reads "📋 E2 — Confirmation evidence (label A): …" on every layout.
- **L6-O4 (DECISIONS 37 — the card's 5M trigger text line). Gap, logged (no change).** 53 / 53 classic and summary: "Trigger 5M: …
  traded into the refined base ✓ …" is always cut by the 1024 caption limit. Moving it ahead made the cut drop the 📋 evidence line (the
  verdict) instead, so the order stays as on main. The trigger itself is on the card image (the 5M panel, DECISIONS 37) and in the Vision
  facts; the 🎯 card field order of DECISIONS 48 (parked) decides the text layout.
- **L6-O5 (L6-a / §1 MTF — card detail lines). Gap, fixed.** On engine entry models the old level-bot line "🎯 Confirmation: supply … ·
  grade None · trend" (52; cut by 1024 here, shown when there is room) and the details "Area … (Resistance, 15M)" printing the setup TF
  instead of the area's own 1H / Daily TF (43). The level-bot line is left out for engine entry models; the Area line prints the area's
  TF. Every other signal: today's card byte for byte (pinned by tests/test_approval_card_summary.py).
- **L6-O6 (K6.5 lines / DECISIONS 41 — the retested line's state). Bug (output), fixed.** 7 E4 (b) on broken lines: card / Vision facts
  "state n/a" (the row's level for a line carries no state); now BROKEN as the engine read it.
- **L6-O7 (L3-n visit by structure — dossier vs the 5M trigger, DECISIONS 37). Output disagreement, not fixed.** 10 E1 entries: the 5M
  visit began inside the 15M bar in progress; the dossier reads the last CLOSED 15M bar and finds no visit in progress for the entry's
  area (no zone study / commitment / CHoCH section for it). Where both see the visit (33) the visit start is the same (33 / 33).
  Provisional default: the dossier stays 15M (it is not wired into the live Vision card); a 5M-trigger view for the dossier is its own PR
  after Abhi's ✅ on this gallery.
- **L6-O8 (L3-c3 / DECISIONS 37 — the required set in the dossier). Output disagreement, not fixed.** 1 (L6-53, E2, label A): the engine
  reads the required set on 5M (present); the dossier reads it on 15M at the last closed bar (handover ✗, commitment ✗ "candle still in
  the pullback direction", LTF CHoCH ✓). The other 32 visible visits agree. No disagreement from the rejected-push exclusion itself
  (L3-c3 as written) was seen. Same provisional default as L6-O7.
- **L6-O9 (L3-n — dossier scope). Gap, logged.** E4 (b) (10): the dossier reads visits of alive areas only; a broken area / line being
  retested has no section.
- **L6-O10 (BW-1 / C-18 — "⚠️ merged band — check"). Open for Abhi.** The line shows on 23 / 53 engine areas (one base each by
  construction, Z-1u; no width limit, Z-1x) because they are wider than 150 pts. The existing display setting `approval_band_warn_rule =
  method` already drops it for engine areas. Provisional: unchanged (Abhi's BW-1 answer).
- **L6-O11 (VP3 / L6-a — volume pane wording). Logged.** With FUT volume missing (41 reading-only entries) the engine card's volume pane
  says "volume: NA (grade cap B)" — "grade cap" contradicts L6-a (no label caps). Provisional: the wording change goes with VP3 (layer 6
  display defaults) on Abhi's ✅; FUT-missing sessions never enter live anyway (Z-1c).
- **L6-O12 (dossier liquidity). Logged.** The dossier's liquidity section builds `Levels` without the Daily frame ("0 Daily bars before
  window ⇒ Q40 prior levels skipped"), so its pools / sweeps may differ from the engine's; not compared per entry here.
- **L6-O13 (DECISIONS 37 — the engine card's 5M trigger panel). Display, logged.** The 5M trigger inset is drawn over the upper-left of
  the 15M setup panel and hides its candles / the area's upper part on most cards (e.g. L6-53). Provisional: unchanged (display; the
  card layout follows DECISIONS 48, parked).
- **Held on every entry (no mismatch):** model, side, object (line words DECISIONS 41: 7 / 7), area band (E = P = T = F = G), area TF,
  Z-1u no union band (53 / 53, clusters included), refined base (E = P = T = F = G), the trigger candle traded into the refined base (card
  ✓ = engine, 43 / 43 with a base), trigger time, entry reference, invalidation price and rule, label in payload / tags / summary card,
  required set in payload / tags / summary 📋 Reader line, the evidence list (card line + facts), trend side, dossier areas = engine areas
  (all alive areas with state, 53 / 53), dossier trend side (43 / 43). Structural risk logged (no case seen): the summary card's 📋 Reader
  pieces "handover (fast)", the LTF label and ① / ③ come from the ROW's best area (payload.reader), not from the entry's own read.
### Abhi's answers on the layer 6 gallery (23 Oct) — DECISIONS 50–54
- L6-O1 / O2 / O3 / O5 / O6: ✅ (merged with branch l6).
- L6-O7 / O8 / O9 / O12: answered — the dossier follows the 5M trigger (its own PR).
- L6-O4: answered — short caption, full details as a reply under the card. L6-O13: answered — 5M trigger panel beside the 15M panel.
- L6-O10 (BW-1 / C-18): answered — no merged-band warning for engine areas (`approval_band_warn_rule = method`).
- L6-O11 (VP3): answered — "FUT volume missing — E2 cannot be read", no grade cap.
- L6-a label: answered — required set = the fired model's own conditions; A = + ≥ 1 confirming piece; B = the model's conditions only; never blocks.
- Done (branch `card6`, engine-entry Vision cards only; display only; level-bot cards byte-identical; older engine-setup rows without an entry model also take the engine volume wording and, under `method`, lose the merged-band line — DECISIONS 53 applies to all engine areas): L6-O4 — the caption is
  short bullets (trend, area + refined base, 5M trigger, invalidation, next area, evidence ✓, Vision, FUT-missing note, decision lines;
  ≤ 1024, no key field cut) and the full details (5M trigger with OHLC / FUT volume / model facts, invalidation rule, evidence list, PA
  evidence, Vision's reading) go as reply(ies) threaded under the card's message id (`vision/worker.engine_caption / engine_details /
  send_details`; buttons stay on the card; works with Vision NA). L6-O13 — the engine card is setup 15M | trigger 5M | higher (own panel,
  no inset). L6-O10 — `approval_band_warn_rule` = method (default) / width (what-if, the 150-pt line), on the 15M SRv2 dashboard;
  "points" (old name) reads as width. L6-O11 — the engine card's volume words: "volume: FUT volume missing — E2 cannot be read" (no grade
  cap); other charts unchanged. Not changed: the V0 `notify` caption of an engine entry (PAPER approval always runs V1 human_confirm).

## Dossier follows the 5M trigger (DECISIONS 51; L6-O7 / O8 / O9 / O12) — branch `dossier5m` (local)

Built: `facts/dossier.build_dossier` reads, with decision3 `trigger_tf = 5M` (the default), exactly what the engine read at the 5M
decision — `V22.decide5(j)` on the same V22 (j = the last 5M candle closed at as_of) and the engine's own 5M functions whose memo that
decision filled (`entry_models5.Reader5.visit5 / confirm5 / c0 / absorbing / broken_objects / broken5`), never a 15M re-read. New
sections `trigger` (the engine's row: 5M candle, context 15M bar, every armed object with each model's state, the fired entries =
the payload's source) and `e4b_objects` (broken areas / lines with lifecycle, revisit, E4 state, required set); `candles.area_studies`
/ `ltf_choch` / `divergence.at_visits` per visit at the 5M decision (visit id, first 5M candle, 15M bin in progress, required set on
5M, models, entries); `liquidity` on the engine's own levels (with the Daily frame) + the evidence window per visit. `trigger_tf =
15M` = the earlier dossier byte for byte (pinned, `tests/fixtures/dossier_15m_pin.json.gz`). No reading rule, no number, no engine
change (entries identical: the engine is not touched).

Replay check (53 BANKNIFTY entries of the layer 6 gallery; tool `trade-data review/layer6_gallery/dossier5m/tools/dcheck.py`):
| check (entries with the mismatch) | before | after |
|---|---|---|
| O-7 the entry's visit in progress, visit id / 15M bin / first 5M candle = the engine's | 10 (E1, visit began inside the 15M bar in progress) | 0 |
| O-8 the required set at that visit = the engine's | 1 (L6-53, E2) + the 10 O-7 entries (no visit seen) | 0 |
| O-9 the E4 (b) object (id, band / line value, broken at, revisit, E4 fired, the entry) in the dossier | 10 | 0 |
| O-12 liquidity = the engine's levels (pools at k, Daily frame) + the visit's evidence window | 43 (pools equal 53 / 53; no Daily frame, no visit window) | 0 |
| every payload field of the entry = the dossier's trigger entry | 53 (no 5M section) | 0 |
| no look-ahead (dossier on bars cut at the 5M close = on the whole session) | 0 | 0 |

Before / after charts of the 21 changed reading cases: trade-data `review/layer6_gallery/dossier5m/index.html`.

Provisional (checked against DECISIONS 37, 46, 49, 51, 54, CLAUDE.md "Trigger reading" / "E4 (b)" / Safety, method §3 visit):
- **D5M-1** The 15M what-if keeps its old liquidity (Levels without the Daily frame) — the order pins 15M byte-identical (DECISIONS 37
  "15M = the earlier behaviour, byte-identical"); the Daily frame applies under the default 5M. (Pools were equal on all 53 entries;
  the Daily frame did not change a pool here.)
- **D5M-2** Visits listed = every alive trade-location area (both roles) + the range edges the engine arms (DECISIONS 40), read with
  the engine's 5M visit; `armed` says which ones the engine arms (trade side). Non-armed areas are facts, as before.
- **D5M-3** `required_set.read` = the shared confirmation as `Reader5.confirm5` reads it on the visit's 5M candles; `by_model` = each
  fired entry's required set exactly as the engine wrote it (so DECISIONS 54 — the model's own conditions — flows through unchanged
  when that build lands; the dossier never computes a label).
- **D5M-4** `zone_study` in a 5M study = the confirmation's a2 window on 5M (the read that decides absorption); the 15M zone read of
  the evidence list stays in the entry's own evidence list.
- **D5M-5** No 5M spot bars (and no 1m to build them) ⇒ `trigger` / `e4b_objects` NA and `area_studies` None with the reason — never
  a silent 15M fallback (fail-closed, DECISIONS 47 spirit). Trend side RANGE ⇒ `e4b_objects` empty with the reason (the engine reads
  E4 (b) only with a trend side).
- The dossier is still not wired into the live Vision card (no live change); before / after charts: trade-data
  `review/layer6_gallery/dossier5m/` — awaiting Abhi ✅ (DECISIONS 46).
