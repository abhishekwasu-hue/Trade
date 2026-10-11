# थर v2.2 — runs (tuning नाही; thresholds register प्रमाणे)

Charts / summary / bars: private trade-data `review/v22/<run>/`.

## NIFTY run3 — Q15 / Q16 + review दुरुस्त्यांनंतर (18 Aug – 09 Oct 2026, 864 bars; tuning नाही)
Daily (Q15 impulse-degree; window आधीचा Daily 1 Jul पासून — holdout नंतरचा):
- 18 Aug – 08 Sep: **DOWN, (4) correction चालू, phase origin_broken** (protected origin 24,367 — 3 Aug ला close ने तुटला; उलट impulse नाही ⇒ trend DOWN, Q23 cap नाही). Correction पाय c → d → e.
- 09 Sep पासून: **DOWN impulse (5)**, protected = (4) टोक 24,704 (Q15 (3): (3) low खाली close नंतरच पुढे). Mature ⚠ लगेच (target 23,978 — equality; window लहान ⇒ (1) minor, data-मर्यादा. (1)-आधीचा swing data-सुरुवातीवर अवलंबून नसल्याने नाही).
- Weekly: 11 Sep पर्यंत UNKNOWN (आठवडे < 10), नंतर NEUTRAL ⇒ cap नाही. Weekly fallback वापरला नाही.

| पायरी | ✔ | ✘ |
|---|---|---|
| ① Daily | 864 | 0 |
| ③ K + level | 142 | 722 |
| ④ power shift (पुरावा) | 87 | 55 |
| ⑥ commitment (best level) | 1 | 140 |
| ⑦ R:R ≥ 3 | 1 | 0 |

Setups 1: 26 Aug 10:00 🟡 B bear call, resistance 24,266–24,367, inside_break (grade B — Q30: pattern आधीच्या candle च्या extreme पलीकडे नाही), R:R 4.03. (Q30 आधी ✅ A.)

**Abhi च्या खुणा — दिवसनिहाय** (प्रत्येक दिवसाचा सर्वात पुढे गेलेला level; ⑦ ढिला केला नाही):

| दिवस | ① resolution | Daily wave | पोचली पायरी | ⑥ form (grade) | conviction | Entry | SL | Target | R:R | कुठे अडलं |
|---|---|---|---|---|---|---|---|---|---|---|
| 01 Sep (E1) | daily impulse | DOWN (4) d, origin_broken | ② | — | — | — | — | — | — | ③ K उघडी नाही / levels 24,266–24,379 ला स्पर्श नाही |
| 03 Sep (E2) | daily impulse | DOWN (4) d, origin_broken | ⑥ ✔ | inside_break (A) 11:00 | A | 23,926.90 | 24,031.01 | 23,895.70 | 0.30 | ⑦ |
| 04 Sep (E3) | daily impulse | DOWN (4) d, origin_broken | ⑥ ✔ | doji_confirm (B) 11:45; strong_close (A) 12:00 | B; A | 23,978.65; 23,952.85 | 24,030.99 | 23,895.70 | 1.58; 0.73 | ⑦ |
| 07 Sep (E4) | daily impulse | DOWN (4) e, origin_broken | ⑥ ✔ | strong_close_2 12:30; engulf 14:30 | weak; B | 23,758.40; 23,758.70 | 23,901.17 | 23,666.35; 23,738.70 | 0.64; 0.14 | ⑦ (12:15 engulf: §5.3 range, close पट्ट्याआत) |

Level: E2 / E3 resistance 23,994–24,025 (a:D2+c ★★★★); E4 resistance 23,787–23,896 (a:D+a:D2+c ★★★). SL = level + K टोक पलीकडे
+ buffer; target = जवळचा (I_end / विरुद्ध जिवंत level). ⇒ **4 पैकी 3 दिवस ⑥ पार**, तिन्ही ⑦ (R:R < 3) वर अडतात: target (जवळचा support
23,896 / 23,666 / 23,739) entry पासून खूप जवळ. E1 ③ पर्यंत पोचत नाही.

## BANKNIFTY run2 — Q15 / Q16 + review दुरुस्त्यांनंतर (13 Jul – 09 Oct 2026, 1575 bars)
Daily: 17 Jul UP impulse (3) (data 13 Jul पासून ⇒ minor degree), 22 Jul origin 57,287 close ने तुटला ⇒ **UP origin_broken (4) 15 Sep
पर्यंत** (उलट रचना नव्हती); 15 Sep DOWN impulse (3) (origin = सर्वात उंच LH 58,248, Q29); 17 Sep correction (4); 24 Sep impulse (5),
protected 56,996, mature ⚠. Weekly 25 Sep पासून DOWN.

| पायरी | ✔ | ✘ |
|---|---|---|
| ① Daily | 1451 | 124 (UNKNOWN 74, NEUTRAL 50) |
| ③ K + level | 154 | 1252 |
| ④ power shift | 92 | 62 |
| ⑥ commitment (best level) | 1 | 152 |
| ⑦ R:R ≥ 3 | 1 | 0 |

Setups 0. ⑥ ✔ level-bars (सर्व levels): Aug–2 Sep bull put support 57,002 (UP origin_broken) — R:R 0.12–2.63 ⇒ ⑦; 16–23 Sep bear call
56,474 — चौथा+ प्रयत्न (§5.1) ⇒ trade नाही; 25 Sep – 06 Oct bear call — R:R 0.03–1.76; **09 Oct 12:30** engulf, R:R 3.02 (entry 55,099.70,
SL 55,270.68, target 54,583.05) पण conviction weak (पहिला पाय, ★ < 2, mature cap) ⇒ वाट. Telegram views: `review/v22/banknifty_tg1`
(02 Sep, 15 Sep, 25 Sep, 09 Oct).

निरीक्षण (Abhi साठी): BANKNIFTY चा UP origin_broken ~8 आठवडे टिकला (data सुरुवातीचा minor UP; Q28 सारखा data-सुरुवात परिणाम) — त्या
काळात bull put levels तपासले गेले. Q23 नुसार cap नाही.

## Q18–Q21 (Abhi: defaults तसेच; एक ओळ प्रत्येकी)
- **Q18** ③ स्पर्श-खिडकी — default 3 bars (commitment ≤ 2 merged + आधीचा); फक्त entry bar (1) घेतलं तर स्पर्श entry bar वरच हवा ⇒ ③ ✔ bars कमी (pullback टोक मागच्या bar वर असलेले commitment bars सुटतात; Q25 वारसा फक्त doji / inside नंतर).
- **Q19** merge भूमिका — default जुन्या level मध्ये merge, जुनी role कायम; उलट role वेगळा ठेवला तर flip झालेल्या पट्ट्यांवर दोन levels (support + resistance) दिसले असते, ② ची निवड बदलली असती.
- **Q20** ⑤ K रेघ — default I_end + K मधले D1 counter pivots, तुटली तरच grade +; D0 pivots घेतले तर रेघा जास्त / लवकर तुटतात ⇒ `tl_break` जास्त वेळा (grade +), gate नाही ⇒ निर्णय क्वचित बदलतो.
- **Q21** B1 / B2 — default B1 = commitment close वर entry, B2 = signal-bar extreme पलीकडे 1 tick break; फक्त B2 घेतल्यास entry दूर ⇒ R:R आणखी कमी (E-days वर ⑦ अधिक कठीण).


## (जुना) NIFTY run2 — 18 Aug – 09 Oct 2026 (864 bars, Q15 / Q16 आधी)
| पायरी | ✔ | ✘ |
|---|---|---|
| ① Daily | 552 | 312 (NEUTRAL) |
| ③ K + level | 65 | 487 |
| ④ power shift | 41 | 24 |
| ⑥ commitment | 0 | 65 — 40 candle नाही, 17 §5.3 range, 4 वेळ, 4 कमकुवत |

Setups 0. E1 / E2 (1, 3 Sep) Daily NEUTRAL (Q15); E3 (4 Sep) ③ स्पर्श नाही; E4 (7 Sep) ③ ✔, ④ 0/4, ⑥ candle नाही (Q16).

## (जुना) BANKNIFTY run1 — 13 Jul – 09 Oct 2026 (1575 bars; Daily फक्त sealed holdout नंतरचे rows)
Trend: NEUTRAL 825, DOWN 651, UNKNOWN 74, UP 25.

| पायरी | ✔ | ✘ |
|---|---|---|
| ① Daily | 676 | 899 |
| ③ K + level | 98 | 578 |
| ④ power shift | 55 | 43 |
| ⑥ commitment | 2 | 96 — 60 candle नाही, 25 §5.3 range, 7 वेळ, 4 कमकुवत |
| ⑦ R:R ≥ 3 | 1 | 1 |

Setups 0. ⑥ ✔ चे दोन bars:
- 15 Sep 09:45 bear call — R:R 0.28 ⇒ trade नाही (H3).
- 09 Oct 12:30 bear call — R:R 3.02, conviction weak (0.5): पहिला पाय, ★ < 2 + signal-bar मजबूत नाही ⇒ §5.1 नुसार दुसऱ्या पायाची वाट.

✅ मध्ये breakout: 0 (✅ च नाहीत). Daily UNKNOWN 74 bars = पहिले ≤ 10 Daily candles (warm-up फक्त holdout नंतरच्या data मुळे).
