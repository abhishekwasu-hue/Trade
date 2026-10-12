# V22 after the shared confirmation (a2 + c0 + c1): NIFTY before / after

**Change:** V22 step ⑥ now calls `decision3.method.confirm`. This adds three conditions to the Q16 commitment:
- **a2:** no absorption in the study window.
- **c0:** the commitment candle is dominant (body ≥ 1.5× the window average, `commit_dom_mult`) and its volume is above the window average.
- **c1:** the 5M chart shows a CHoCH by close, using only 5M bars that closed by the 15M setup bar's close.

Any missing piece means wait (OPEN_QUESTIONS LB25–LB30).

**Run:** NIFTY 15M, 2015-01-09 → 2024-03-27 (IS / VAL only; the holdout was not loaded). Same inputs as `setups_prA_v1`, plus 5M bars resampled from the same 1-minute data (`market_state.core.frame`).
- **Volume:** the spot parquet has volume 0 and there is no intraday futures history for IS / VAL, so volume is NA. c0 therefore checks dominance only, and every setup is capped at grade B.
- **Before:** origin/main (1e6c9ac), the 30 setups of `setups_prA_v1`.
- **After:** branch `claude/v22-confirmation` (1c7e1b8).

| | before | after |
|---|---|---|
| bars | 56,765 | 56,765 |
| setup | 30 | 8 (all grade B, volume NA) |
| wait | 55,813 | 55,873 |
| no_trade | 922 | 884 |

### Step ⑥ wait reasons (bars where ③ passed but ⑥ did not)

| reason | bars |
|---|---|
| pullback-direction candle | 1,573 |
| no commitment form | 714 |
| commitment not dominant (c0) | 638 |
| absorption (a2) | 576 |
| inside bar | 439 |
| doji | 406 |
| waiting for 5M CHoCH (c1) | 159 |
| other | 8 |

## The 30 setups, before → after

| setup (15M bar) | before | after |
|---|---|---|
| 2015-03-10 10:30 | B | no setup |
| 2015-08-10 10:45 | A | no setup |
| 2017-03-27 12:45 | B | no setup |
| 2017-11-08 10:15 | A | no setup |
| 2017-11-08 13:30 | A | **setup B** · engulf, body 2.4× · 5M CHoCH: sweep of low 10,326.55 closed back inside, higher low 10,330.55, close above LH 10,341.3 at 13:40 |
| 2018-03-05 12:00 / 13:15 / 13:30 | B | no setup |
| 2018-03-05 13:45 | B | **setup B** · strong close, body 1.6× · 5M CHoCH at 13:35 |
| 2018-05-16 10:15 | B | **setup B** · inside-bar break, body 5.5× · 5M CHoCH at 10:20 |
| 2018-05-16 15:00 | B | no setup |
| 2018-06-19 11:45 | B | no setup |
| 2018-06-19 13:15 | B | **setup B** · strong close, body 1.9× · 5M CHoCH at 13:25 |
| 2019-09-03 10:45 | B | no setup |
| 2019-09-25 10:45 | A | no setup |
| 2020-11-04 10:00 / 15:00 (the bear-call defect) | B | no setup |
| 2020-11-20 11:15 / 11:30 | B | no setup |
| 2021-11-11 11:30 | B | no setup |
| 2022-01-20 14:45 | A | **setup B** · engulf, body 2.6× · 5M CHoCH at 15:00 |
| 2022-02-07 12:30 | B | no setup |
| **2022-03-14 13:30 (#23)** | B | **setup B** · inside-bar break, body 1.7× · 5M CHoCH: higher low 16,759.1, close above LH 16,781.8 at 13:40 |
| **2022-03-28 09:45 (#24)** | B | **no setup:** the 09:45 pin is not dominant (body 1.0× the window, which includes the 09:15 red candle), and 5M is still making lower lows (17,037.2 at 09:50) |
| 2022-03-28 10:45 | A | no setup: not dominant (1.2×); 5M swept 17,004.1 but has only a wick above LH 17,045.6 |
| 2022-03-28 12:00 | A | **setup B** · bullish engulf, body 1.7× · 5M CHoCH: sweep of low 17,004.1 closed back inside, higher low 17,010.85, close above LH 17,045.6 at 11:25 |
| 2022-03-28 12:15 | A | **setup B** · strong close (2 candles), body 3.6× · same CHoCH |
| 2022-04-25 10:00 | B | no setup |
| 2022-09-16 14:30 | B | no setup |
| 2022-11-15 11:15 | B | no setup |

No setup appears that was not already in the 30.

## #23 and #24

- **#24 (2022-03-28):** this matches Abhi's expectation. There is no setup at 09:45. The setup comes later, at 12:00, on a dominant bullish engulf after the 5M CHoCH (11:25).
  - The window's a2 absorption read does not cover the 25-Mar afternoon red candles. The V22 study window starts at the first 28-Mar touch of the level (LB28).
  - Volume is NA, so c0 cannot check the 09:15 red candle's volume.
- **#23 (2022-03-14 13:30):** a2, c0 and c1 all pass, so it stays a setup (grade B).
  - Abhi's expected "no setup" comes from item 2 (a): the daily supply between entry and target makes R:R < 3.
  - It also comes from item 2 (b): this is a breakout-retest, not a pullback.
  - Both rules belong to the `claude/v22-areas-quality` branch, not to this change.

Charts are not regenerated here. That happens after the chart-volume branch lands.
