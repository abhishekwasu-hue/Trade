# थर v2.2 — OPEN_QUESTIONS (default घेऊन काम चालू; Abhi उत्तर देतील तेव्हा बदल batch PR ने)

| # | प्रश्न | घेतलेला default | पर्याय |
|---|---|---|---|
| Q1 | ① HH / HL: "जवळपास समान" (RANGE tol) च्या आत असलेला H2 > H1 HH मानायचा का? | नाही — HH / HL साठी tol पलीकडे हवं (`range_eq_sigma_d` × σ_D); tol च्या आत ⇒ RANGE उमेदवार | साधं `>` |
| Q2 | ② मृत्यू: "level पलीकडचा structural swing" — कोणती बाजू? | **मूळ भूमिकेची** (support ⇒ खालचा जवळचा D2 L; resistance ⇒ वरचा D2 H), flip झाल्यानंतरही | चालू भूमिकेची बाजू (flipped resistance ⇒ वरचा swing) |
| Q3 | ② flip ("real break") किती closes? | **spec §5.4 / §7.7 ने ठरलं:** पलीकडे सलग 3 closes (acceptance, `accept_closes`); 1–2 closes किंवा wick आणि परत ⇒ sweep ★ | — |
| Q4 | ② (b) BOS base चा पट्टा | ↑ [low, open] / ↓ [open, high] (base चा उगम-भाग) + किमान रुंदी | पूर्ण candle [low, high] |
| Q5 | ① नवा trend: नवा HL आणि HH दोन्ही शेवटच्या break नंतरचे हवेत का? | हो (दोन्ही pivots break bar नंतरचे) | फक्त दुसरा (नंतरचा) pivot नवा |
| Q6 | ② (a) "1H trend-degree swing" | थर 1 swings2 D2 (15M bars वर, θ₂ = 6σ — v2.1 मधली 1H degree) | खऱ्या 1H candles वर स्वतंत्र pivots |
| Q7 | BANKNIFTY Daily (fetched D 10y) | engine मध्ये फक्त sealed holdout नंतरचे rows (data-policy); जुने W/D फक्त chart (display) | — |
| Q8 | ① intraday: आजचा trend कधी बदलतो? | आजच्या Daily close नंतरच (शेवटच्या 15M bar ला); दिवसभर कालच्या close ची state | — |
| Q9 | ② RANGE trade-बाजू | खालचा जवळचा support + वरचा जवळचा resistance (प्रत्येकी 1) | range पट्ट्याच्या कडांवरचेच levels |
| Q10 | §2 "✅ फक्त ①②③④⑥ पूर्ण" वि. §6.2 "कठोर नियम फक्त H1–H3" | H1–H3 + ⑥ (entry trigger) कठोर; ④ आणि बाकी पुरावे ⇒ conviction; ✅ = conviction A, 🟡 = B; §5.3 range अवस्था = gate | ④ सुद्धा कठोर |
| Q11 | §6 पुराव्यांचं वजन / conviction सीमा | `evidence_weights` (trap / power shift 1.5; star / दुसरा प्रयत्न / commit 1; बाकी 0.5; विरुद्ध bodies −1, चौथा प्रयत्न −1.5); A ≥ 0.6, B ≥ 0.4, weak ≥ 0.2 — Abhi E1–E4 वरून ठरवायचं | — |
| Q12 | §5.1 "पाय" मोजणी | K मधले confirmed D1 counter swings + चालू पाय (1 = H1 / L1 ⇒ कमाल B, ≥ 2 ⇒ A शक्य, > 3 ⇒ trade नाही) | D0 swings |
| Q13 | ③ "उलट बाजूने आली" | आधीचा 15M close level च्या trade-बाजूला (bear call: पट्ट्याखाली/आत, वरून नाही); open / close पलीकडे ⇒ breakout ✘ | पहिल्या स्पर्शाची दिशा |
| Q14 | ⑦ target | I_end आणि विरुद्ध बाजूचा जवळचा जिवंत level — जो जवळ | फक्त I_end |
| Q15 | NIFTY run1: Daily DOWN फक्त 4 Sep पासून (18 Aug ला HL close-break ⇒ NEUTRAL; नवा LH + LL pivot N = 2 ने confirm व्हायला 4 Sep) ⇒ E1 (1 Sep), E2 (3 Sep) ① ✘ | default तसाच (tuning नाही) | (i) नवा LL = आधीचा swing low **close** ने तुटला (pivot confirm ची वाट नाही); (ii) N = 1; (iii) DC पद्धत |
| Q16 | NIFTY run1: ③ ✔ 46 bars, ⑥ ✔ 0 (28 "commitment candle नाही", 13 §5.3 range अवस्था, 4 वेळ-खिडकी, 1 कमकुवत). Review दुरुस्त्यांनंतर run2: ③ ✔ 65, ④ ✔ 41, ⑥ ✔ 0 (40 commitment candle नाही, 17 §5.3, 4 वेळ, 4 कमकुवत) | default तसाच | commitment मध्ये close "मागच्या candle च्या extreme पलीकडे" ऐवजी "मागच्या close पलीकडे" (Brooks second-entry) — Abhi चा निर्णय |
| Q17 | v2.2 charts साठी `matplotlib` — `requirements.txt` मध्ये नाही (sandbox मध्ये वेगळं install) | engine (decision3 core) ला matplotlib लागत नाही; फक्त `decision3/charts.py` / `scripts/v22_check.py` ला. requirements बदल पायरी D (Telegram) सोबत, Abhi च्या मंजुरीने | आत्ताच requirements मध्ये जोडा |
| Q18 | ③ "level मध्ये / लगत" (⑥, §6.2 H2 "वर / जवळ"): स्पर्श फक्त entry bar वर का? | शेवटच्या `touch_window_bars` = 3 bars (commitment ≤ 2 merged + आधीचा) पैकी एकाने पट्ट्याला स्पर्श; breakout / gap तपासणी bar t वर; "उलट बाजूने" = पहिल्या स्पर्शाआधीचा close (independent review नंतर बदल — run1 मध्ये entry bar वरच स्पर्श लागत होता) | फक्त entry bar (1) |
| Q19 | ② merge: नवा support जिवंत resistance ला overlap झाला तर? | जुन्या level मध्ये merge, जुनी भूमिका (role) कायम; जन्म-कारण जोडलं जातं | फक्त समान भूमिकेचे merge; उलट भूमिका ⇒ वेगळा level |
| Q20 | ⑤ "K ची आतली तिरकी रेघ" — कोणते बिंदू? | I_end + K मधले confirmed D1 counter pivots (DOWN ⇒ lows); शेवटची K-दिशेने सरकलेली जोडी; स्पर्श σ_1H × 0.15; break = रेघ confirm झाल्यानंतरचा trend-दिशेचा close. पुरावा `tl_break` (वजन 1.0) फक्त तुटली तर True; रेघ अखंड / नाही ⇒ NA (spec "(असल्यास) … तुटली ⇒ grade +" ⇒ grade वजा नाही); दोन anchors = 2 स्पर्श | D0 pivots; किंवा फक्त K मधले pivots (I_end शिवाय) |
| Q21 | "B1/B2 तसेच" (spec §2 / C) — B1 / B2 म्हणजे काय? repo / आधीच्या spec मध्ये व्याख्या सापडली नाही | §5.2 चे दोन entry trigger: **B1** = commitment close वर (default), **B2** = signal-bar extreme च्या 1 tick (`entry_tick` 0.05) पलीकडे break; SL / target तेच, B2 चा R:R वेगळा (< 3 ⇒ B2 नाही). Caption + debug मध्ये दोन्ही | Abhi ची स्वतःची व्याख्या |
