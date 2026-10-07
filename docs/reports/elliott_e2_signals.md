# Elliott E2 — entry signals (NIFTY spot, IS 2015-01-01 – 2021-12-31, default settings)

Structure bars: 128,602; trading days: 1,727; signals: **510** (0.30 प्रति दिवस); scan वेळ 14.8 मिनिटं (6.9 ms/bar).
फक्त वर्णन — P&L, win-rate किंवा edge चा दावा नाही (तो E4 backtest मध्ये, costs सह). Settings hash: `84183f9999a9`.

## Setup × tier × दिशा

| Setup | Tier | दिशा | Signals |
|---|---|---|---|
| S3 | C | bull_put | 64 |
| S2 | A | bull_put | 52 |
| S7 | A | bull_put | 49 |
| S2 | A | bear_call | 48 |
| S3 | C | bear_call | 46 |
| S7 | B | bull_put | 43 |
| S7 | B | bear_call | 41 |
| S7 | A | bear_call | 25 |
| S6a | B | bull_put | 14 |
| S6b | B | bear_call | 13 |
| S3 | A | bull_put | 11 |
| S12 | B | bear_call | 11 |
| S13 | B | bear_call | 11 |
| S3 | B | bear_call | 10 |
| S6b | B | bull_put | 8 |
| S3 | B | bull_put | 8 |
| S6c | B | bear_call | 8 |
| S13 | B | bull_put | 7 |
| S2 | C | bear_call | 7 |
| S12 | B | bull_put | 7 |
| S2 | C | bull_put | 6 |
| S4 | A | bull_put | 5 |
| S7 | C | bull_put | 4 |
| S3 | A | bear_call | 3 |
| S4 | A | bear_call | 2 |
| S9 | A | bear_call | 2 |
| S1 | A | bear_call | 1 |
| S6c | B | bull_put | 1 |
| S9 | B | bear_call | 1 |
| S9 | B | bull_put | 1 |
| S1 | A | bull_put | 1 |

## Degree × trigger TF

| Degree | TTF | Signals |
|---|---|---|
| D0 | 5m | 110 |
| D1 | 15m | 35 |
| D1 | 5m | 223 |
| D2 | 15m | 62 |
| D2 | 30m | 1 |
| D2 | 5m | 79 |

## वर्षनिहाय

| वर्ष | bull_put | bear_call |
|---|---|---|
| 2015 | 40 | 31 |
| 2016 | 37 | 39 |
| 2017 | 56 | 40 |
| 2018 | 29 | 35 |
| 2019 | 35 | 31 |
| 2020 | 42 | 41 |
| 2021 | 42 | 12 |

## Composite candles (N) आणि score

| N | Signals |
|---|---|
| 1 | 149 |
| 2 | 193 |
| 3 | 156 |
| 4 | 12 |

Rejection score: median 0.69, 10–90% 0.62–0.76. Recount (§14 Q6) signals: 8.

## Entry का नाही — degree-निहाय कारणे (प्रत्येक बंद 5m bar वर एक)

कारणांचा अर्थ: `no_count` = त्या degree वर valid count नाही; `gray` = vote < vote_min; `next_not_motive` = पुढची wave corrective (A-end R4 / triangle आत); `inside_B_X_triangle` = parent च्या B/X/triangle आत; `not_ttf_close` = trigger TF चा bar अजून बंद नाही; `tf_bars_min` = wave अजून 8 candles पेक्षा लहान; `R4_legs` = correction मध्ये < 3 sub-legs; `T7_breakout` = close शेवटच्या sub-leg च्या origin पलीकडे; `T_*` = composite candle अटी (touch/reclaim/strength/score).

| Degree | कारण | bars | वाटा |
|---|---|---|---|
| D0 | no_count | 91,346 | 71.1% |
| D0 | gray | 25,896 | 20.2% |
| D0 | tf_bars_min | 3,526 | 2.7% |
| D0 | inside_B_X_triangle | 2,675 | 2.1% |
| D0 | next_not_motive | 1,805 | 1.4% |
| D0 | inside_end_diag | 859 | 0.7% |
| D0 | T_no_touch | 437 | 0.3% |
| D0 | R4_legs | 293 | 0.2% |
| D0 | T_weak | 257 | 0.2% |
| D0 | C3_c_time | 231 | 0.2% |
| D0 | wick_beyond_inv | 225 | 0.2% |
| D0 | disabled_S11 | 215 | 0.2% |
| D0 | T_no_reclaim | 198 | 0.2% |
| D0 | T_low_score | 164 | 0.1% |
| D1 | no_count | 71,613 | 55.8% |
| D1 | gray | 41,419 | 32.3% |
| D1 | inside_B_X_triangle | 3,333 | 2.6% |
| D1 | inside_end_diag | 2,621 | 2.0% |
| D1 | T_no_touch | 1,880 | 1.5% |
| D1 | not_ttf_close | 1,094 | 0.9% |
| D1 | R4_legs | 887 | 0.7% |
| D1 | T_no_reclaim | 866 | 0.7% |
| D1 | tf_bars_min | 824 | 0.6% |
| D1 | next_not_motive | 726 | 0.6% |
| D1 | T5_time | 641 | 0.5% |
| D1 | T_weak | 485 | 0.4% |
| D1 | T_low_score | 382 | 0.3% |
| D1 | disabled_S11 | 270 | 0.2% |
| D2 | gray | 76,421 | 59.5% |
| D2 | no_count | 36,235 | 28.2% |
| D2 | not_ttf_close | 4,321 | 3.4% |
| D2 | inside_B_X_triangle | 2,504 | 1.9% |
| D2 | T_no_touch | 2,151 | 1.7% |
| D2 | next_not_motive | 1,434 | 1.1% |
| D2 | disabled_S11 | 789 | 0.6% |
| D2 | T7_breakout | 700 | 0.5% |
| D2 | T5_time | 671 | 0.5% |
| D2 | T_no_reclaim | 589 | 0.5% |
| D2 | R4_legs | 514 | 0.4% |
| D2 | disabled_S14 | 357 | 0.3% |
| D2 | C3_c_time | 308 | 0.2% |
| D2 | T_weak | 301 | 0.2% |
