# थर v2.2 — what-if (फक्त अहवाल; defaults बदलले नाहीत)

Abhi च्या Q15 (Daily lag) आणि Q16 (commitment व्याख्या) निर्णयासाठी. तेच NIFTY data (18 Aug – 09 Oct 2026, 864 bars, थर 1 एकदाच),
register मधले पर्याय एकेक बदलून. Script: `scripts/v22_whatif.py`; JSON: trade-data `review/v22/whatif_nifty.json`.
"अडलं" = त्या दिवसाच्या सर्वात पुढे गेलेल्या bar चा पहिला ✘ **gate** (①②③⑥⑦; ④ = पुरावा, gate नाही).

## run3 — Q15 / Q16 + review दुरुस्त्यांनंतर (default = impulse-degree Dow + reversal-form commitment, `commit_beyond` close)
JSON: trade-data `review/v22/whatif_nifty_q1516.json`. "अडलं" = best-level चा पहिला ✘ gate (दिवसाचा सर्वात पुढचा bar).

| variant | प्रश्न | ① ✔ | ③ ✔ | ④ ✔ | ⑥ ✔ | ⑦ ✔ | setups | 01 Sep | 03 Sep | 04 Sep | 07 Sep |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **default** | — | 864 | 142 | 87 | 1 | 1 | 1 | ③ K उघडी नाही | ⑥ inside — वाट | ⑥ doji — वाट | ⑥ pullback-दिशेची — वाट |
| daily_minor (जुना) | Q15 आधी | 552 | 59 | 38 | 0 | 0 | 0 | ① NEUTRAL | ① NEUTRAL | ③ स्पर्श नाही | ⑥ pullback-दिशेची |
| daily_pivot_n = 1 | Q15 (ii) नाकारला | 505 | 89 | 55 | 0 | 0 | 0 | ① NEUTRAL | ① NEUTRAL | ① NEUTRAL | ⑥ pullback-दिशेची |
| daily DC | Q15 (iii) नाकारला | 841 | 141 | 86 | 1 | 1 | 1 | ⑥ pullback-दिशेची | ⑥ inside — वाट | ⑥ doji — वाट | ⑥ pullback-दिशेची |
| commit_beyond = extreme | Q16 आधी | 864 | 156 | 96 | 0 | 0 | 0 | ③ K उघडी नाही | ⑥ inside — वाट | ⑥ candle नाही | ⑥ pullback-दिशेची |

default / DC मधला setup: 26 Aug 10:00 🟡 B bear call (inside_break, Q30 grade B), R:R 4.03; `commit_beyond = extreme` मध्ये तो ⑥ ✘ (close pattern आधीच्या candle च्या extreme पलीकडे नाही). हा तक्ता best-level / best-bar दाखवतो; त्याच दिवसाचे ⑥ ✔ पण ⑦ ✘
level-bars (E2 0.30, E3 1.58 / 0.73, E4 0.64 / 0.14) `RUNS.md` मध्ये.

वाचन: Q15 ने E1–E4 चा ① अडथळा गेला (minor / N = 1 मध्ये NEUTRAL). Q16 नंतर E2 / E3 / E4 ⑥ पार करतात (inside_break, doji_confirm,
strong_close, engulf) आणि ⑦ (R:R < 3) वर थांबतात — ⑦ ढिला केला नाही.

## ⑥ diag run3 — Q16 commitment निकाल (③ ✔ bars, engine चंच `commitment`)
| निकाल | NIFTY (142) | BANKNIFTY (154) |
|---|---|---|
| वाट: candle अजून pullback-दिशेची | 68 | 68 |
| वाट: doji level वर | 25 | 23 |
| वाट: inside bar | 23 | 26 |
| ✔ form (grade) | inside_break A 1 + B 1, strong_close A 1, engulf A 1, pin B 1 | engulf A 2, doji_confirm A 1, strong_close A 1, star B 1 |
| reversal form नाही | 11 (+1 close pattern-आधीच्या close खाली) | 14 (+1) |
| entry वेळ-खिडकीबाहेर | 9 | 17 |

(Diag प्रत्येक ③ ✔ bar चा best level घेतो; level-निहाय ⑥ ✔ जास्त — RUNS.md.)

## (जुना) run2 — Q15 / Q16 आधी

| variant | प्रश्न | ① ✔ | ③ ✔ | ④ ✔ | ⑥ ✔ | ⑦ ✔ | setups | 01 Sep | 03 Sep | 04 Sep | 07 Sep |
|---|---|---|---|---|---|---|---|---|---|---|---|
| default | — | 552 | 65 | 41 | 0 | 0 | 0 | ① NEUTRAL | ① NEUTRAL | ③ स्पर्श नाही | ⑥ candle नाही |
| daily_pivot_n = 1 | Q15 (ii) | 577 | 112 | 72 | 0 | 0 | 0 | ① NEUTRAL | ① NEUTRAL | ③ स्पर्श नाही | ⑥ candle नाही |
| daily DC (k_D × σ_D) | Q15 (iii) | 864 | 156 | 96 | 1 | 1 | 1 | ⑥ candle नाही | ⑥ वेळ-खिडकी | ⑥ candle नाही | ⑥ candle नाही |
| commit_beyond = close | Q16 | 552 | 59 | 38 | 0 | 0 | 0 | ① NEUTRAL | ① NEUTRAL | ③ स्पर्श नाही | ⑥ candle नाही |
| pivot_n = 1 + close | Q15 (ii) + Q16 | 577 | 103 | 67 | 0 | 0 | 0 | ① NEUTRAL | ① NEUTRAL | ③ स्पर्श नाही | ⑥ candle नाही |

DC चा एकमेव setup: 26 Aug 10:00 bear call ✅ A, R:R 4.03.

निरीक्षणं (निर्णय Abhi चा):
- E1 / E2 चा ① अडथळा फक्त DC पद्धतीने जातो (संपूर्ण window DOWN). Pivot N = 1 ने नाही (18 Aug च्या HL close-break नंतर नवा LH + LL लवकर confirm होत नाही).
- ① पार झाल्यावरही चारही E-days ⑥ (commitment candle) वर अडतात — Q16 चा "close पलीकडे" पर्याय एकटा पुरेसा नाही (⑥ ✔ 0 च).
- ⇒ मुख्य अडथळा ⑥ ची रचना (body ≥ 50 %, close तृतीयांश, उलट wick, merged ≤ 2) — Abhi च्या E-days च्या 15M candles सोबत पुन्हा पाहायला हवं.
- Funnel मधले ③ / ④ आकडे variant नुसार थोडे बदलतात कारण प्रत्येक bar ला "सर्वात चांगल्या" level चा checklist दाखवतो.

## ⑥ diag — ③ ✔ bars वर commitment च्या कोणत्या अटी अडवतात (`scripts/v22_commit_diag.py`, फक्त अहवाल)
प्रत्येक ③ ✔ bar साठी सर्वात जवळचा k (1 / 2 merged) घेऊन ✘ अटींचा संच (वेळ-खिडकी वेगळी):

| ✘ अटी | NIFTY (65 bars) | BANKNIFTY (98 bars) |
|---|---|---|
| दिशा + body + extreme पलीकडे + close तृतीयांश (candle अजून उलट दिशेची — pullback चालू) | 29 | 40 |
| दिशा + body + extreme पलीकडे | 7 | 4 |
| **फक्त** extreme पलीकडे close | 6 | 12 |
| body + extreme + तृतीयांश + उलट wick | 5 | 11 |
| **फक्त** close तृतीयांश | 4 | 5 |
| **फक्त** body ≥ 50 % | 1 | 5 |
| सगळ्या अटी ✔ (पण वेळ-खिडकीबाहेर / range अवस्था) | 2 | 3 |

वाचन: ③ ✔ पैकी जवळपास निम्म्या bars ला candle अजून pullback च्याच दिशेने आहे (⑥ ची वाट योग्य). एकच अट अडवणारे bars थोडे
(NIFTY 11, BANKNIFTY 22) — त्यात "मागच्या extreme पलीकडे close" सर्वात जास्त. Q16 चा निर्णय या आकड्यांवरून Abhi घेतील; defaults तसेच.
(Commitment दुरुस्ती — k = 1 कमकुवत ⇒ k = 2 merged पाहणे — नंतरचे आकडे; NIFTY / BANKNIFTY runs पुन्हा चालवले: ⑥ आकडे बदलले नाहीत. Diag engine सारखाच: 09:15 merged नाही, `commit_beyond` नुसार.)
