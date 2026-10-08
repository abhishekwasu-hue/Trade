# Data स्रोत (Trade repo — public)

> Options / bhavcopy / golden 1m data **या public repo मध्ये नाही** — फक्त खाजगी `trade-data` repo मध्ये (VPS export).

| File | काळ | स्रोत | वापर | Licence / अटी |
|---|---|---|---|---|
| `data/nifty50_1min.parquet` | 2015-01-09 → 2024-03-27 (852,087 1m bars) | वापरकर्त्याचा स्वतःचा CSV (Upstox नाही) | Elliott research: IS (2019-02-11 → 2021-12-31) व VAL; त्याआधी warm-up. `elliott/data_policy.py` नुसारच | **वापरकर्त्याकडून नोंद बाकी** (स्रोत/परवाना माहिती मिळाल्यावर इथे भरायची — अंदाज लिहिलेला नाही) |
| `data/nifty50_daily_extension.parquet` | 2024-03-28 → 2026-08-20 (daily) | PR #225 | **Sealed holdout काळ** — elliott/research मध्ये वाचायचा नाही. `data_policy.load_parquet` हा file वाचायला `HoldoutError` देतो (test: `tests/test_elliott_fixes.py`) | — |
| `trade-data` (खाजगी repo) | 2018-12 → 2024-03 (research), 2026-09-25 → 10-06 (golden); NIFTY 1m 2026-07-01 → 10-08 (golden + Chart Reader golden story) | NSE bhavcopy, Upstox expired instruments (VPS export, `research/elliott_vps_data.py`) | E4/C3 खरे premiums व IV (F8), golden regression; `futures_volume/` = NIFTY/BANKNIFTY futures 5M volume (collector, front + पुढचा contract — Chart Reader K10.3, फक्त PAPER तपासणी) | NSE / Upstox अटींनुसार; public repo मध्ये commit नाही |

Holdout नियम: 2024-04 पासूनचा काळ बंद (contaminated 2026-07-01 → 10-08 — golden regression आणि Chart Reader illustration साठीच, `purpose="golden"`).
