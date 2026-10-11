# ABC_FIX rule 7 — 3-wave counter-moves that used to flip the Daily trend

Old = main engine before this PR (#289); new = this PR. Full Daily history (warm-up included). NIFTY holdout (2024-04 … 2026-06) dates are not listed — only counted. Engine reason text (`why`) as logged.


## BANKNIFTY

- flips: old **19**, new **8**
- today: old UP correction (protected 53,027) → new DOWN impulse (protected 58,706)

### Old flips the new engine does not make (counter-move now read as a correction)

| day | to | old engine reason |
|---|---|---|
| 2017-01-11 | UP | origin तुटला + उलट रचना ⇒ UP (origin 17,830.95) |
| 2018-02-20 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 25,810.25) |
| 2018-05-07 | UP | origin तुटला + उलट रचना ⇒ UP (origin 24,466.10) |
| 2019-05-08 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 30,121.75) |
| 2019-09-23 | UP | origin तुटला + उलट रचना ⇒ UP (origin 26,643.00) |
| 2021-01-13 | UP | origin तुटला + उलट रचना ⇒ UP (origin 28,976.75) |
| 2024-01-17 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 48,381.95) |
| 2024-03-04 | UP | origin तुटला + उलट रचना ⇒ UP (origin 45,661.75) |
| 2024-11-13 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 52,577.50) |
| 2024-12-05 | UP | origin तुटला + उलट रचना ⇒ UP (origin 51,693.95) |
| 2024-12-19 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 53,738.90) |
| 2025-04-15 | UP | origin तुटला + उलट रचना ⇒ UP (origin 49,156.95) |
| 2025-08-26 | DOWN | नवा impulse (L5) ⇒ protected पुढे = correction टोक 57,316.60 |
| 2025-10-07 | UP | origin तुटला + उलट रचना ⇒ UP (origin 54,226.60) |
| 2026-01-23 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 60,235.15) |
| 2026-02-10 | UP | origin तुटल्यानंतर उलट impulse ⇒ UP (origin 59,644.55) |
| 2026-03-23 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 55,554.15) |
| 2026-06-17 | UP | origin तुटला + उलट रचना ⇒ UP (origin 53,027.15) |

### New flips (not in old)

| day | to | new engine reason |
|---|---|---|
| 2017-01-25 | UP | origin तुटला + उलट रचना ⇒ UP (origin 18,722.85) |
| 2018-03-06 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 25,810.25) |
| 2018-07-26 | UP | origin तुटला + उलट रचना ⇒ UP (origin 24,466.10) |
| 2021-02-15 | UP | origin तुटला + उलट रचना ⇒ UP (origin 35,428.15) |
| 2021-03-16 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 37,232.20) |
| 2021-09-17 | UP | origin तुटला + उलट रचना ⇒ UP (origin 34,817.50) |
| 2026-03-12 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 61,678.80) |

## NIFTY

- flips: old **28**, new **7**
- today: old DOWN impulse (protected 24,774) → new DOWN impulse (protected 24,774)
- holdout (masked): 3 old-only flips, 2 new-only flips

### Old flips the new engine does not make (counter-move now read as a correction)

| day | to | old engine reason |
|---|---|---|
| 2015-03-19 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 8,844.05) |
| 2015-07-06 | UP | origin तुटला + उलट रचना ⇒ UP (origin 8,196.10) |
| 2015-08-24 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 8,621.40) |
| 2015-10-05 | UP | origin तुटला + उलट रचना ⇒ UP (origin 7,691.30) |
| 2015-12-08 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 8,115.70) |
| 2016-03-21 | UP | origin तुटला + उलट रचना ⇒ UP (origin 7,405.25) |
| 2018-03-23 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 10,637.65) |
| 2018-04-27 | UP | origin तुटला + उलट रचना ⇒ UP (origin 10,536.75) |
| 2018-09-11 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 11,602.75) |
| 2018-11-29 | UP | origin तुटला + उलट रचना ⇒ UP (origin 10,490.45) |
| 2019-07-08 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 12,000.30) |
| 2019-09-23 | UP | origin तुटला + उलट रचना ⇒ UP (origin 10,670.50) |
| 2020-03-09 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 12,272.05) |
| 2020-11-06 | UP | origin तुटला + उलट रचना ⇒ UP (origin 8,056.20) |
| 2021-11-22 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 18,209.60) |
| 2022-03-30 | UP | origin तुटला + उलट रचना ⇒ UP (origin 17,004.10) |
| 2022-05-04 | DOWN | नवा impulse (L5) ⇒ protected पुढे = correction टोक 17,377.30 |
| 2022-07-28 | UP | origin तुटला + उलट रचना ⇒ UP (origin 15,511.85) |
| 2022-09-26 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 17,918.45) |
| 2022-10-31 | UP | origin तुटला + उलट रचना ⇒ UP (origin 16,950.65) |
| 2023-03-24 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 18,200.75) |
| 2023-05-02 | UP | origin तुटला + उलट रचना ⇒ UP (origin 17,554.10) |
| 2023-10-25 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 19,849.75) |
| 2023-11-28 | UP | origin तुटला + उलट रचना ⇒ UP (origin 19,329.45) |

### New flips (not in old)

| day | to | new engine reason |
|---|---|---|
| 2015-04-27 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 8,844.75) |
| 2017-03-16 | UP | origin तुटला + उलट रचना ⇒ UP (origin 8,328.05) |
| 2020-03-12 | DOWN | origin तुटला + उलट रचना ⇒ DOWN (origin 12,272.05) |
| 2020-11-09 | UP | origin तुटला + उलट रचना ⇒ UP (origin 8,056.20) |


## Note

The new engine flips far less often: a counter-move must itself be a same-degree 5-wave impulse (Q22 leg-degree reference, OPEN_QUESTIONS Q49), or close beyond the parent. Some removed flips may have been real trend changes at Abhi's degree. Please eyeball the BANKNIFTY list above; the degree reference is open in Q49. No threshold was tuned on these results.
