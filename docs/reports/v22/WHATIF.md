# थर v2.2 — what-if (फक्त अहवाल; defaults बदलले नाहीत)

Abhi च्या Q15 (Daily lag) आणि Q16 (commitment व्याख्या) निर्णयासाठी. तेच NIFTY data (18 Aug – 09 Oct 2026, 864 bars, थर 1 एकदाच),
register मधले पर्याय एकेक बदलून. Script: `scripts/v22_whatif.py`; JSON: trade-data `review/v22/whatif_nifty.json`.
"अडलं" = त्या दिवसाच्या सर्वात पुढे गेलेल्या bar चा पहिला ✘ **gate** (①②③⑥⑦; ④ = पुरावा, gate नाही).

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
