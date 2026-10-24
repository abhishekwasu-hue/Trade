# OPEN_QUESTIONS — open items only (≤ 30 KB, DECISIONS 70)

Closed / answered items and every full text: docs/archive/OPEN_QUESTIONS_CLOSED.md (grep by id; "archive L<n>" = its line).
When an item is answered, move its line to the archive (append) — never delete.

## Waiting for Abhi now (24 Oct)
| id | Question (one line) | Current default | Where |
|---|---|---|---|
| A-L1 | BREAK-1 hold swing degree: D1 (2.17 never broken; 2 goldens fail) or D0 (matches 2.17 / X01 / 2.3; 9 goldens fail)? And what to do with the failing goldens / 28 pinned tests | D1, not merged | branch lifecycle, docs/reports/gallery_review_fixes.md §A |
| F2-CONF | Daily protected origin only after the top is a confirmed swing (29 Jun 58,706 confirmed 30 Jun); fix fails NIFTY 29 Sep golden — apply or hold? | held | branch dailyF, docs/reports/gallery_review_fixes_F.md |
| B-2 | Visit ends when its object becomes BROKEN; open visit away from the area reads nothing (D11, N07) — confirm after charts | provisional default | branch visitmove |
| B-1 / B-3 / B-4 | Visit uses D0 ∪ D1 swings; line move start follows DECISIONS 64; D04/D05 area born on its touching bar | as built | branch visitmove |
| L58-c | Daily traded area: does an overlapping other Daily area count as confluence? | no (line / pool only) | branch label54 |
| L55-c | Liquidity pool for confluence = equal highs / lows only (a plain swing in the band is the area's own reaction) | as built | branch label54 |
| D5M-1 | 15M what-if dossier keeps the old liquidity (no Daily frame) | kept | facts/dossier.py |
| L5 gallery | Layer 5 rebuilt gallery ✅ (after the C PR: pushes C1–C8) | not approved | trade-data review/layer5_gallery |
| Fix proof | Fix proof gallery ✅ (rebuild after A + B / C / D + E) | not approved | trade-data review/fix_proof_gallery |
| 5M Q1–Q18 | 5M trigger provisional defaults (store window, catch-up, cron, card) | as built | archive: "Entry trigger on 5M" |

## Still open (carried from 21 Oct; one line each — full text in the archive)
| id | Question | Current default | Full text |
|---|---|---|---|
| R-BN-1 … R-BN-5 | BANKNIFTY replay: does Abhi agree with "no handover" (E29 / E31), see a handover on any G3 visit (E14, E17, E20, E21, E24, E29), and is E26 / M06 only… | no change to the reader | archive L18 |
| L5 / L6a ✅ | Layer 5 (RSI divergence inside the move into the zone, L5-a) and layer 6a (verdict: required set ⇒ enter; A = + ≥ 1 confirming, B = required only) — ✅… | as merged; not stable until ✅ | archive L19 |
| C-L5-1 | Layer 5 gallery (23 Oct): ✅ the C-L5-1 fix (E4 (b) broken area on the 5M path: RSI move start) after checking its charts (L5-b / L5-c answered: DECISI… | fix on branch `l5`, awaiting ✅ | archive L20 |
| R0-3 | Golden Vision V4 expectations (12 Oct, 29 Sep): ✅ the drafts | drafts; every V4 result PROVISIONAL; live V4 off (… | archive L21 |
| R1a-13 | Bands on the Vision approval chart (`vision_chart_bands`) — turn on, and change the Vision legend with it? | OFF (image unchanged) | archive L22 |
| BW-1 / C-18 | Keep the 150-pt "merged band — check" alert now that bands are never merged (Z-1u)? | 150, display only | archive L23 |
| L3-c3 · L3-n · Z-1b · R1b-1, R1b-2, R1b- | Facts dossier: its own visit finder (`touch_window_bars`, PENDING in the guard), its commitment read, the shared band check's "flipped", owner disagre… | as coded | archive L29 |
| CD1 … CD14-E · VP1 … VP6 · R1a-1 … R1a-1 | Chart / pane display defaults (Daily structure chart, volume panes, chart line / band checks, 1H / 15M review charts) | as coded | archive L30 |
| C-22 | Retire the old numeric rsi2 `RSI` class (only the facts dossier still uses it) | kept | archive L31 |
| RSI-4 | The review listener does not record ✏️ (a ✘ + reason is recorded) | as is | archive L32 |
| # | प्रश्न | घेतलेला default | archive L55 |
| Q1 | ① HH / HL: "जवळपास समान" (RANGE tol) च्या आत असलेला H2 > H1 HH मानायचा का? | नाही — HH / HL साठी tol पलीकडे हवं (`range_eq_sigm… | archive L57 |
| Q2 | ② मृत्यू: "level पलीकडचा structural swing" — कोणती बाजू? | ~~मूळ भूमिकेची~~ **TL1 (Abhi 2026-10-12) ने बदललं:… | archive L58 |
| Q3 | ② flip ("real break") किती closes? | **spec §5.4 / §7.7 ने ठरलं:** पलीकडे सलग 3 closes … | archive L59 |
| Q4 | ② (b) BOS base चा पट्टा | ↑ [low, open] / ↓ [open, high] (base चा उगम-भाग) +… | archive L60 |
| Q5 | ① नवा trend: नवा HL आणि HH दोन्ही शेवटच्या break नंतरचे हवेत का? | हो (दोन्ही pivots break bar नंतरचे) | archive L61 |
| Q6 | ② (a) "1H trend-degree swing" | थर 1 swings2 D2 (15M bars वर, θ₂ = 6σ — v2.1 मधली … | archive L62 |
| Q7 | BANKNIFTY Daily (fetched D 10y) | ~~engine मध्ये फक्त sealed holdout नंतरचे rows~~ *… | archive L63 |
| Q8 | ① intraday: आजचा trend कधी बदलतो? | आजच्या Daily close नंतरच (शेवटच्या 15M bar ला); दि… | archive L64 |
| Q9 | ② RANGE trade-बाजू | खालचा जवळचा support + वरचा जवळचा resistance (प्रत्… | archive L65 |
| Q10 | §2 "✅ फक्त ①②③④⑥ पूर्ण" वि. §6.2 "कठोर नियम फक्त H1–H3" | H1–H3 + ⑥ (entry trigger) कठोर; ④ आणि बाकी पुरावे … | archive L66 |
| Q11 | §6 पुराव्यांचं वजन / conviction सीमा | `evidence_weights` (trap / power shift 1.5; star /… | archive L67 |
| Q12 | §5.1 "पाय" मोजणी | K मधले confirmed D1 counter swings + चालू पाय (1 =… | archive L68 |
| Q13 | ③ "उलट बाजूने आली" | आधीचा 15M close level च्या trade-बाजूला (bear call… | archive L69 |
| Q14 | ⑦ target | I_end आणि विरुद्ध बाजूचा जवळचा जिवंत level — जो जव… | archive L70 |
| Q15 | ~~Daily lag~~ **निकाली (Abhi FINAL)** | degree-aware Dow: trend = शेवटचा impulse leg, prot… | archive L71 |
| Q16 | ~~commitment~~ **निकाली (Abhi)** | reversal candle at level: engulf / star / inside_b… | archive L72 |
| Q17 | v2.2 charts साठी `matplotlib` — `requirements.txt` मध्ये नाही (sandbox मध्ये वेगळं install) | engine (decision3 core) ला matplotlib लागत नाही; फ… | archive L73 |
| Q18 | ③ "level मध्ये / लगत" (⑥, §6.2 H2 "वर / जवळ"): स्पर्श फक्त entry bar वर का? | शेवटच्या `touch_window_bars` = 3 bars (commitment … | archive L74 |
| Q19 | ② merge: नवा support जिवंत resistance ला overlap झाला तर? | जुन्या level मध्ये merge, जुनी भूमिका (role) कायम;… | archive L75 |
| Q20 | ⑤ "K ची आतली तिरकी रेघ" — कोणते बिंदू? | I_end + K मधले confirmed D1 counter pivots (DOWN ⇒… | archive L76 |
| Q21 | "B1/B2 तसेच" (spec §2 / C) — B1 / B2 म्हणजे काय? repo / आधीच्या spec मध्ये व्याख्या सापडली नाही | §5.2 चे दोन entry trigger: **B1** = commitment clo… | archive L77 |
| Q22 | Q15 "त्याच degree ची correction" — impulse आतल्या minor bounces पासून वेगळी कशी? | correction = impulse टोकानंतरचा confirmed उलट swin… | archive L79 |
| Q23 | origin close ने तुटला पण उलट impulse नाही — conviction? | cap नाही; फक्त नोंद ("correction चालू") — spec: st… | archive L80 |
| Q24 | §5.3 range gate वि. Q16 doji / inside forms (form स्वतःच overlap + doji दाखवतो) | commitment candle मागच्या `range_state_n` candles … | archive L81 |
| Q25 | Q16 "doji / inside ⇒ एक candle वाट" — पुष्टीची candle ③ च्या 3-bar स्पर्श खिडकीबाहेर पडते | t − 1 ला ③ ✔ + ⑥ वाट (doji / inside) ⇒ t ला ③ वारस… | archive L82 |
| Q26 | Q16 grade B (wick-only नकार) चा conviction वर परिणाम? | grade B ⇒ conviction कमाल B (🟡). `commit_strong` प… | archive L83 |
| Q27 | Q15 नंतर RANGE कधी? (impulse mode मध्ये trend एकदा लागला की RANGE ला पोचत नाही — फक्त NEUTRAL पासून) | RANGE फक्त data सुरुवातीला / NEUTRAL मधून; trend अ… | archive L84 |
| Q28 | data (A) च्या सुरुवातीपासून असेल तर (B) zigzag (HL + HH) = UP impulse म्हणून वाचला जातो ⇒ (C) चा (3) सुरू झाल्यावरही (B) चा HL close ने तुटेपर्यंत UP … | नियम जसाच (structure ने impulse; leg-nature वर्गीक… | archive L85 |
| Q29 | origin तुटल्यावर उलट रचना जुन्या impulse टोकापासूनच आधी झाली असेल (LH + मधल्या L खाली close) — कधी flip? (review 🔴1: degree data-सुरुवातीवर अवलंबून हो… | त्याच दिवशी flip; origin = impulse टोकानंतरचा सर्व… | archive L86 |
| Q30 | Q16 "close मागच्या candle च्या close / extreme पलीकडे" — 2-candle (merged) forms (doji_confirm, inside_break, star, tweezer, strong_close_2) मध्ये "मा… | merged = एक candle ⇒ "मागची" = pattern आधीची candl… | archive L87 |
| Q31 | Daily swing view: NIFTY चा "शेवटची 2 वर्षं" chart ⇒ 2024-04 … 2026-06 sealed holdout rows लागतात | NIFTY साठी holdout rows कधीच नाहीत (script drop कर… | archive L88 |
| Q32 | Daily legs impulse / corrective — "legs2 / patterns2 classification" | legs2 / patterns2 intraday swings2 (15M degrees) व… | archive L89 |
| Q33 | Daily swing view मध्ये engine पूर्ण history वर (Abhi) वि. v22_check मध्ये BANKNIFTY Daily फक्त Jul 2026 पासून (Q7) — degree वेगळी येते (BANKNIFTY आज: … | View: full history (Abhi चा नियम); engine run (v22… | archive L90 |
| Q34 | Q15 wave क्रमांक (5) नंतरही वाढत राहतो ((6) … (36)) — mechanical count, Elliott degree नाही | तसाच (फक्त दाखवतो); maturity (5)+ ला लागते | archive L91 |
| Q35 | Q22: "आतले pullbacks" कोणते, आणि impulse leg अजून सरळ (आतला pullback नाही) व मागच्या impulse leg मध्येही नाही ⇒ पहिला उलट swing कोणत्या degree चा? | आतले = एक degree खालचे Daily pivots (N − 1 = 1); स… | archive L92 |
| Q36 | Q28 gate (impulse-स्वभावाचा पाय) फक्त NEUTRAL / RANGE मधून trend सुरुवातीला की origin_broken नंतरच्या flip ला पण? | फक्त सुरुवातीला (Abhi: "first leg after the data s… | archive L93 |
| Q37 | Q28: C माहीत नसेल (baseline < 10 आधीचे Daily legs — warm-up; किंवा ≤ 2-bar पाय) तर? | फक्त रचना (आतली रचना एक degree खालच्या pivots वरून… | archive L94 |
| Q38 | Q27 RANGE: कोणते H / L, आणि ② ला कडा कशा? | impulse टोकानंतरचे शेवटचे दोन H आणि दोन L (tol = `… | archive L95 |
| Q39 | Q33: NIFTY चा protected / origin pivot holdout काळातला असेल तर output मध्ये? | किंमत दाखवतो (engine state), तारीख "before window"… | archive L96 |
| Q40 | Q33: पूर्ण Daily history ⇒ जुने (वर्षांपूर्वीचे / NIFTY holdout) Daily pivots 1H levels म्हणून जन्मावेत का? | नाही — 15M window आधी बनलेले Daily pivots level म्… | archive L97 |
| Q41 | #284 (28 Sep 14:15 bear): 11-candle G8 flag आता चालतो (`g8_max_bars` 11), पण अजून Gray-2 IMPULSE_NA — flag चा low (impulse टोक) trade-degree confirmed… | बदल नाही — golden 28 Sep xfail तसाच; 16 Feb 2018 "… | archive L98 |
| Q42 | Daily review A1: "मोठ्या degree चा origin" engine मध्ये कसा? | **hybrid (default):** impulse origin close ने तुटल… | archive L99 |
| Q43 | A2: same-degree correction चा संदर्भ — "the largest internal pullback of the impulse **so far**" (A2 शब्द) की Q35 default (चालू leg **किंवा मागच्या im… | Q35 default तसाच ⇒ +559 < 657 ⇒ "pullback" (candid… | archive L100 |
| Q44 | ~~A3: (A) low target~~ **निकाली — खालचा "PR A अंमल" विभाग पाहा** (target = parent नंतरच्या पहिल्या impulse leg चं टोक; numeric fallback काढला). जुना प… | बदल नाही (आधीपासूनचं वर्तन); maturity flag तरीही (… | archive L101 |
| Q45 | A1/A2: (4) संपून (5) कधी? Engine: correction (4) चालू ⇒ (5) फक्त confirmed झाल्यावर — close counter-move च्या शेवटच्या HL खाली (nature gate नाही कारण … | तसाच (real-time मध्ये टोक आधी कळत नाही) | archive L102 |
| Q46 | A4: caption मध्ये wave क्रमांक ("impulse 5 of C")? Q34: mechanical count ला (n) नाही | क्रमांक नाही: "Trend DOWN (impulse) · pullback in … | archive L103 |
| Q47 | B1 "origin at risk": engine नियम = correction किंमत protected च्या `maturity_sigma_d` × σ_D आत (जुनी संख्या). BANKNIFTY (87% retrace, सर्वात जवळ 759 p… | नियम तसाच (निकाल पाहून बदल नाही); caption मध्ये de… | archive L104 |
| Q48 | C1 1H / 15M review charts: "trend-degree legs, corrections as boxes" — 1H / 15M ला स्वतःची trend-degree रचना engine मध्ये नाही (Daily legs आठवडे लांब;… | default: ≤ 6 level पट्टे + trigger candle + (15M) … | archive L105 |
| Q49 | ABC_FIX / FIXTURES: counter-move स्वतःच 5-wave impulse ⇒ flip — पण zigzag चा a (आणि double zigzag चा W) सुद्धा 5-wave impulse असतो; Elliott त्या क्षणी… | default: Q22 leg-degree संदर्भ — library 100 / 112… | archive L106 |
| Q50 | A1 parent: #289 hybrid ("मागच्या same-degree correction चं टोक", नसेल तर trend सुरुवातीचा LH) की ABC_FIX ("prior impulse's origin = the Feb top") | default: ABC_FIX — trend-degree impulse ची सुरुवात… | archive L107 |
| Q51 | ABC_FIX rule 3 "conviction up": engine मध्ये फक्त caps (कमाल B / weak) आहेत, grade वाढवण्याची यंत्रणा नाही | default: पुरावा `DState.evidence` + `engine.step1`… | archive L108 |
| Q52 | Fixture library: sideways triple three (zigzag + X + flat + X + triangle Z) — engine दोन box करतो (W-X-Y एक correction, Z नंतर वेगळी); trend / origin … | default: strict xfail (family only); 5-segment com… | archive L109 |
| Q53 | ABC_FIX rule 1 नंतर जुन्या Q15 / Q23 / Q27 / Q36 fixtures मधली 3-wave counter-move (trend सुरुवात टिकलेली) आता correction ⇒ default मध्ये origin_broke… | default: ती यंत्रणा counter impulse किंवा trend सु… | archive L110 |
| Q54 | तात्पुरत्या completion चा stack (`prov`) फक्त confirm (corr_end) किंवा अपयशी restore वर रिकामा होतो; confirm कधीच न झाल्यास जुन्या अवस्था राहतात (rest… | default: तसेच — expiry चा प्रयत्न correction box च… | archive L111 |
| Q55 | **निकाली — खालचा "PR A अंमल" विभाग (B: पहिला तोडलेला swing low).** जुना प्रश्न: ABC_FIX rule 2 "sharp-fall point": engine = impulse मधला wide-range धा… | default: तसेच (निकाल पाहून व्याख्या बदलली नाही) | archive L112 |
