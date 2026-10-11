# Level bots — touch vs confirmation replay (L6)

> **SAMPLE — full run pending.** Small slice only, to review the template. Every cell here is n < 30 ⇒ no conclusion.

Generated 2026-10-11 16:47 by `python3 scripts/level_bots_replay.py --start 2021-12-17,BANKNIFTY=2026-09-10,GOLD=2026-09-10,SILVER=2026-09-10,COPPER=2026-09-10 --max-days 20 --out data/research/level_bots_replay_sample --sample`.

Data: NIFTY 1m bars, replay 2021-12-17 → 2022-01-13 (20 days); BANKNIFTY 15m bars, replay 2026-09-10 → 2026-10-09 (20 days); GOLD 30m bars, replay 2026-09-10 → 2026-10-07 (19 days); SILVER 30m bars, replay 2026-09-10 → 2026-10-07 (19 days); COPPER 30m bars, replay 2026-09-10 → 2026-10-07 (19 days)

## How this replay works

- Same days, same levels, same cost model for both modes. Levels = the bots' Dynamic S/R (`sr_dynamic.compute_dynamic_sr`, refresh parameters and lookbacks), recomputed at the session open and every 60 min from closed bars only (no lookahead). Level memory is not replayed.
- **Touch (legacy)** = the bots' own functions imported from the bot files (`check_level_crossed`, `determine_direction_with_hysteresis`), default settings (RSI thresholds, max hits per level and role, cooldowns, one position at a time, no new entry from 14:45, EOD). PCR gate skipped (no PCR history). Exits = the bots' naked spot-% SL / target (MCX: settings points).
- **Confirmation** = `level_reaction.evaluate` on closed confirmation-TF candles, exactly as the live cycle: an entry only on the commitment candle itself. Trend = one `decision3.daily.fold` per symbol + `state_at` per day (yesterday's close). Gate defaults: min R:R 3, max armed bars 8, area = level ± 0.05% / 2. RSI / PCR gates off, no breakout. Exits = the gate's structural SL (beyond the area's far edge + buffer) / target (next opposite area).
- Exit simulation on the next base bars: SL before target when both are inside one bar (pessimistic); a gap beyond SL fills at the open; EOD closes at the bar close. Index futures volume is not available for IS / VAL ⇒ volume NA ⇒ grade ≤ B (as live with volume NA).
- P&L is in **index / futures points** — intraday option premium history is not available. Cost per round trip (points) from `charges.py` (Upstox rates): 1 lot naked ITM option buy (premium / lot / delta / slippage in `COST_DEFAULTS`) ⇒ {'NIFTY': 3.18, 'BANKNIFTY': 6.66, 'GOLD': 28.26, 'SILVER': 43.11, 'COPPER': 0.36}.
- NIFTY: IS / VAL per `elliott.data_policy`; the HOLDOUT is never loaded (guard raises). BANKNIFTY: only 15M candles exist (≈ 3 months, not sealed, but the calendar overlaps the gate's NIFTY design window ⇒ illustration, not validation); touch and exits on 15M bars; only 15M SRv2. MCX: 30m candles only (≈ 4 months, no volume); confirmation on 30m (live: 15m); Daily trend from ≤ 4 months of Daily bars (live: ~10 years) ⇒ trend often UNKNOWN; MCX extra filters (cascade, supertrend, structure SL, min-hold) not replayed.
- Trend split = the gate's Daily trend that day (UP ⇒ bull, DOWN ⇒ bear, RANGE ⇒ range, NEUTRAL / UNKNOWN ⇒ no trend). A day whose trend is UP / DOWN but where the gate blocks new entries (origin broken / at risk, parent correction A1) stays in bull / bear; its legacy trades show the verdict "Daily trend unclear / entries blocked".
- Rejected legacy trades: for each legacy trade, the gate's verdict on the same area in the window max armed bars before → after the touch (the same visit); the Daily trend check comes first, as in the gate. "Kept" = the gate confirmed the same area and side in that window (whether or not the confirmation arm could take it).

Cells with n < 30 carry **no conclusion** (numbers shown for reference only).

## Conclusions (cells with n ≥ 30 in both modes)

- None — no cell reaches n ≥ 30 in both modes.

## 5M Instant — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 24 | 17% | -5.36 | -128.7 | 141.5 | 0.45 | n < 30 — no conclusion |
| IS | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | touch | 24 | 17% | -5.36 | -128.7 | 141.5 | 0.45 | n < 30 — no conclusion |
| IS | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 17 | 24% | -3.53 | -60.0 | 84.8 | 0.62 | n < 30 — no conclusion |
| VAL | all | confirmation | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | bull | touch | 17 | 24% | -3.53 | -60.0 | 84.8 | 0.62 | n < 30 — no conclusion |
| VAL | bull | confirmation | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 41 · kept by the gate: 1 (taken by the confirmation arm: 1) · rejected: 40.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | Daily trend unclear / entries blocked | 24 | 4 | -128.7 | -5.36 | 128.7 | n < 30 |
| VAL | against the Daily trend | 9 | 2 | -51.6 | -5.73 | 51.6 | n < 30 |
| VAL | area broken (real break) | 4 | 1 | -3.4 | -0.86 | 3.4 | n < 30 |
| VAL | kept — the gate confirmed the same area and side | 1 | 1 | 32.1 | 32.14 | — | n < 30 |
| VAL | impulsive approach | 1 | 0 | -12.0 | -12.04 | 12.0 | n < 30 |
| VAL | no opposite area for a target | 1 | 0 | -12.3 | -12.27 | 12.3 | n < 30 |
| VAL | Daily trend unclear / entries blocked | 1 | 0 | -12.8 | -12.78 | 12.8 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**Daily trend unclear / entries blocked** (25)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2021-12-17 | 09:18 | 17,217.88 | long | bull | SL | -11.8 | Daily UP: parent correction (A1) |
| 2021-12-17 | 14:43 | 17,000.53 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-23 | 09:43 | 17,086.43 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 09:36 | 17,036.97 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 09:40 | 17,017.07 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 10:11 | 16,926.85 | long | bull | SL | -11.6 | Daily UP: parent correction (A1) |
| 2021-12-24 | 10:36 | 16,926.85 | long | bull | SL | -11.6 | Daily UP: parent correction (A1) |
| 2021-12-24 | 13:56 | 17,009.70 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 14:15 | 17,040.80 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 09:22 | 16,835.15 | long | bull | TARGET | 30.5 | Daily UP: parent correction (A1) |
| 2021-12-27 | 09:51 | 16,964.32 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 10:34 | 16,996.97 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 12:17 | 17,029.12 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-28 | 14:40 | 17,210.32 | long | bull | SL | -11.8 | Daily UP: parent correction (A1) |
| 2021-12-29 | 09:20 | 17,234.68 | short | bull | TARGET | 31.3 | Daily UP: parent correction (A1) |

**area broken (real break)** (4)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-06 | 09:16 | 17,761.15 | long | bull | SL | -12.1 | broken |
| 2022-01-07 | 12:17 | 17,770.42 | long | bull | SL | -12.1 | broken |
| 2022-01-11 | 13:56 | 18,040.93 | long | bull | TARGET | 32.9 | broken |
| 2022-01-11 | 14:34 | 18,040.93 | long | bull | SL | -12.2 | broken |

**against the Daily trend** (9)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-06 | 14:26 | 17,761.15 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-07 | 09:21 | 17,853.45 | short | bull | SL | -12.4 | Daily UP |
| 2022-01-07 | 10:54 | 17,853.45 | long | bull | SL | -12.1 | ignored: against trend |
| 2022-01-07 | 13:04 | 17,770.42 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-07 | 13:56 | 17,770.42 | long | bull | SL | -12.1 | ignored: against trend |
| 2022-01-07 | 14:42 | 17,790.00 | short | bull | EOD | 16.7 | Daily UP |
| 2022-01-12 | 14:44 | 18,201.35 | short | bull | SL | -12.3 | Daily UP |
| 2022-01-13 | 11:55 | 18,246.28 | short | bull | SL | -12.3 | Daily UP |
| 2022-01-13 | 14:05 | 18,246.28 | short | bull | EOD | 17.0 | Daily UP |

**impulsive approach** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-07 | 12:46 | 17,725.05 | long | bull | SL | -12.0 | impulsive approach |

**no opposite area for a target** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-13 | 10:39 | 18,178.92 | long | bull | SL | -12.3 | no target area |

## 15M SRv2 — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 6 | 17% | 1.12 | 6.7 | 35.1 | 1.11 | n < 30 — no conclusion |
| IS | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | touch | 6 | 17% | 1.12 | 6.7 | 35.1 | 1.11 | n < 30 — no conclusion |
| IS | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 3 | 33% | -1.08 | -3.2 | 24.3 | 0.87 | n < 30 — no conclusion |
| VAL | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | bull | touch | 3 | 33% | -1.08 | -3.2 | 24.3 | 0.87 | n < 30 — no conclusion |
| VAL | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 9 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 9.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | Daily trend unclear / entries blocked | 6 | 1 | 6.7 | 1.12 | -6.7 | n < 30 |
| VAL | against the Daily trend | 3 | 1 | -3.2 | -1.08 | 3.2 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**Daily trend unclear / entries blocked** (6)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2021-12-17 | 10:40 | 17,042.10 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-17 | 11:17 | 17,042.10 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 09:50 | 16,951.25 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-30 | 09:16 | 17,153.88 | long | bull | TARGET | 65.5 | Daily UP: parent correction (A1) |
| 2021-12-31 | 09:34 | 17,330.18 | short | bull | SL | -11.8 | Daily UP: parent correction (A1) |
| 2021-12-31 | 11:01 | 17,330.18 | short | bull | SL | -11.8 | Daily UP: parent correction (A1) |

**against the Daily trend** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-10 | 09:30 | 17,924.43 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-10 | 11:46 | 17,924.43 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-13 | 12:22 | 18,246.28 | short | bull | EOD | 21.0 | Daily UP |

## Classic — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 13 | 62% | 36.57 | 475.4 | 72.5 | 2.92 | n < 30 — no conclusion |
| IS | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | touch | 13 | 62% | 36.57 | 475.4 | 72.5 | 2.92 | n < 30 — no conclusion |
| IS | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 8 | 50% | 1.60 | 12.8 | 140.4 | 1.05 | n < 30 — no conclusion |
| VAL | all | confirmation | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | bull | touch | 8 | 50% | 1.60 | 12.8 | 140.4 | 1.05 | n < 30 — no conclusion |
| VAL | bull | confirmation | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 21 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 21.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | Daily trend unclear / entries blocked | 13 | 8 | 475.4 | 36.57 | -475.4 | n < 30 |
| VAL | against the Daily trend | 3 | 1 | -24.3 | -8.11 | 24.3 | n < 30 |
| VAL | no opposite area for a target | 2 | 2 | 90.5 | 45.24 | -90.5 | n < 30 |
| VAL | area broken (real break) | 1 | 0 | -74.4 | -74.43 | 74.4 | n < 30 |
| VAL | Daily trend unclear / entries blocked | 1 | 0 | -66.0 | -65.98 | 66.0 | n < 30 |
| VAL | R:R below minimum | 1 | 1 | 87.1 | 87.07 | -87.1 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**Daily trend unclear / entries blocked** (14)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2021-12-17 | 09:16 | 17,279.82 | short | bull | TARGET | 134.7 | Daily UP: parent correction (A1) |
| 2021-12-17 | 10:22 | 17,042.10 | long | bull | SL | -71.4 | Daily UP: parent correction (A1) |
| 2021-12-21 | 12:44 | 16,942.95 | short | bull | TARGET | 132.3 | Daily UP: parent correction (A1) |
| 2021-12-23 | 09:42 | 17,086.43 | short | bull | EOD | 17.3 | Daily UP: parent correction (A1) |
| 2021-12-24 | 09:35 | 17,036.97 | long | bull | SL | -71.4 | Daily UP: parent correction (A1) |
| 2021-12-24 | 10:10 | 16,926.85 | long | bull | TARGET | 132.3 | Daily UP: parent correction (A1) |
| 2021-12-27 | 09:21 | 16,835.15 | long | bull | TARGET | 131.5 | Daily UP: parent correction (A1) |
| 2021-12-27 | 10:06 | 16,951.25 | long | bull | TARGET | 132.6 | Daily UP: parent correction (A1) |
| 2021-12-28 | 14:40 | 17,210.32 | long | bull | EOD | -14.1 | Daily UP: parent correction (A1) |
| 2021-12-29 | 09:26 | 17,234.68 | short | bull | EOD | -17.7 | Daily UP: parent correction (A1) |
| 2021-12-30 | 09:16 | 17,153.88 | long | bull | EOD | 35.6 | Daily UP: parent correction (A1) |
| 2021-12-31 | 09:31 | 17,330.18 | short | bull | SL | -72.5 | Daily UP: parent correction (A1) |
| 2021-12-31 | 14:15 | 17,342.18 | long | bull | EOD | 6.1 | Daily UP: parent correction (A1) |
| 2022-01-04 | 14:15 | 17,738.28 | short | bull | EOD | -66.0 | Daily UP: parent correction (A1) |

**area broken (real break)** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-06 | 09:16 | 17,761.15 | long | bull | SL | -74.4 | broken |

**R:R below minimum** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-06 | 10:46 | 17,658.03 | long | bull | EOD | 87.1 | R:R < min (1.51 < 3) |

**against the Daily trend** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-07 | 09:21 | 17,853.45 | short | bull | EOD | 75.7 | Daily UP |
| 2022-01-10 | 09:16 | 17,924.43 | short | bull | SL | -74.9 | Daily UP |
| 2022-01-12 | 13:15 | 18,201.35 | short | bull | EOD | -25.2 | Daily UP |

**no opposite area for a target** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-11 | 10:17 | 17,960.82 | long | bull | EOD | 66.1 | no target area |
| 2022-01-13 | 10:14 | 18,178.92 | long | bull | EOD | 24.4 | no target area |

## 15M SRv2 — BANKNIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| ALL | all | touch | 6 | 17% | -13.34 | -80.0 | 103.5 | 0.54 | n < 30 — no conclusion |
| ALL | all | confirmation | 2 | 50% | -56.27 | -112.5 | 178.3 | 0.37 | n < 30 — no conclusion |
| ALL | bear | touch | 6 | 17% | -13.34 | -80.0 | 103.5 | 0.54 | n < 30 — no conclusion |
| ALL | bear | confirmation | 2 | 50% | -56.27 | -112.5 | 178.3 | 0.37 | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 6 · kept by the gate: 2 (taken by the confirmation arm: 2) · rejected: 4.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| ALL | kept — the gate confirmed the same area and side | 2 | 0 | -68.5 | -34.24 | — | n < 30 |
| ALL | R:R below minimum | 2 | 1 | 58.2 | 29.10 | -58.2 | n < 30 |
| ALL | gate confirmed the other side / an earlier visit | 1 | 0 | -34.9 | -34.87 | 34.9 | n < 30 |
| ALL | area broken (real break) | 1 | 0 | -34.9 | -34.90 | 34.9 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**area broken (real break)** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-11 | 14:00 | 56,470.52 | short | bear | SL | -34.9 | broken |

**gate confirmed the other side / an earlier visit** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-18 | 14:15 | 56,426.55 | short | bear | SL | -34.9 |  |

**R:R below minimum** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-21 | 14:00 | 56,656.75 | short | bear | EOD | 93.2 | R:R < min (0.75 < 3) |
| 2026-09-22 | 09:45 | 56,656.75 | short | bear | SL | -35.0 | R:R < min (0.43 < 3) |

## MCX — GOLD

### Results by Daily trend context (net of costs, points)

| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| ALL | all | touch | 11 | 9% | -55.41 | -609.5 | 620.7 | 0.02 | n < 30 — no conclusion |
| ALL | all | confirmation | 2 | 0% | -165.68 | -331.4 | 331.4 | 0.00 | n < 30 — no conclusion |
| ALL | bull | touch | 11 | 9% | -55.41 | -609.5 | 620.7 | 0.02 | n < 30 — no conclusion |
| ALL | bull | confirmation | 2 | 0% | -165.68 | -331.4 | 331.4 | 0.00 | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 11 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 11.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| ALL | against the Daily trend | 5 | 0 | -313.3 | -62.65 | 313.3 | n < 30 |
| ALL | area broken (real break) | 3 | 0 | -210.2 | -70.07 | 210.2 | n < 30 |
| ALL | R:R below minimum | 2 | 0 | -97.2 | -48.60 | 97.2 | n < 30 |
| ALL | timeout — no commitment within max_armed_bars | 1 | 1 | 11.1 | 11.15 | -11.1 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**timeout — no commitment within max_armed_bars** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-10 | 18:30 | 153,494.50 | long | bull | TARGET | 11.1 | timeout |

**area broken (real break)** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-11 | 10:30 | 153,216.00 | long | bull | SL | -79.8 | broken |
| 2026-09-17 | 10:00 | 152,128.00 | long | bull | SL | -81.6 | broken |
| 2026-09-24 | 12:30 | 152,941.00 | long | bull | SL | -48.8 | broken |

**against the Daily trend** (5)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-16 | 11:00 | 153,216.00 | short | bull | SL | -88.8 | Daily UP |
| 2026-09-17 | 18:30 | 154,485.00 | short | bull | SL | -49.0 | Daily UP |
| 2026-09-17 | 20:00 | 154,485.00 | short | bull | SL | -49.0 | Daily UP |
| 2026-09-18 | 12:00 | 155,565.00 | short | bull | SL | -50.2 | Daily UP |
| 2026-09-18 | 15:30 | 155,565.00 | short | bull | SL | -76.2 | Daily UP |

**R:R below minimum** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-10-05 | 10:30 | 148,966.50 | long | bull | SL | -48.1 | R:R < min (1.08 < 3) |
| 2026-10-06 | 10:30 | 148,966.50 | long | bull | SL | -49.1 | R:R < min (2.18 < 3) |

## MCX — SILVER

### Results by Daily trend context (net of costs, points)

| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| ALL | all | touch | 10 | 0% | -51.35 | -513.5 | 513.5 | 0.00 | n < 30 — no conclusion |
| ALL | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| ALL | bear | touch | 1 | 0% | -116.33 | -116.3 | 116.3 | 0.00 | n < 30 — no conclusion |
| ALL | bear | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| ALL | no trend | touch | 9 | 0% | -44.13 | -397.2 | 397.2 | 0.00 | n < 30 — no conclusion |
| ALL | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 10 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 10.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| ALL | Daily trend unclear / entries blocked | 9 | 0 | -397.2 | -44.13 | 397.2 | n < 30 |
| ALL | against the Daily trend | 1 | 0 | -116.3 | -116.33 | 116.3 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**Daily trend unclear / entries blocked** (9)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-10 | 18:00 | 236,853.00 | long | no trend | SL | -64.3 | Daily NEUTRAL |
| 2026-09-14 | 21:00 | 231,040.50 | long | no trend | SL | -63.3 | Daily NEUTRAL |
| 2026-09-15 | 14:30 | 230,010.50 | long | no trend | TARGET | -3.1 | Daily NEUTRAL |
| 2026-09-15 | 15:00 | 230,010.50 | long | no trend | TARGET | -3.2 | Daily NEUTRAL |
| 2026-09-18 | 13:00 | 242,149.50 | short | no trend | SL | -65.2 | Daily NEUTRAL |
| 2026-09-18 | 15:00 | 242,149.50 | short | no trend | SL | -65.2 | Daily NEUTRAL |
| 2026-09-22 | 13:30 | 236,790.00 | long | no trend | SL | -64.3 | Daily NEUTRAL |
| 2026-09-25 | 16:00 | 236,667.00 | short | no trend | SL | -64.3 | Daily NEUTRAL |
| 2026-09-25 | 18:00 | 236,667.00 | short | no trend | TARGET | -4.3 | Daily NEUTRAL |

**against the Daily trend** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-30 | 17:00 | 225,300.50 | long | bear | SL | -116.3 | Daily DOWN |

## MCX — COPPER

### Results by Daily trend context (net of costs, points)

| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| ALL | all | touch | 11 | 18% | -5.02 | -55.3 | 55.3 | 0.03 | n < 30 — no conclusion |
| ALL | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| ALL | bull | touch | 11 | 18% | -5.02 | -55.3 | 55.3 | 0.03 | n < 30 — no conclusion |
| ALL | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 11 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 11.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| ALL | Daily trend unclear / entries blocked | 9 | 2 | -22.8 | -2.54 | 22.8 | n < 30 |
| ALL | area broken (real break) | 2 | 0 | -32.4 | -16.21 | 32.4 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**area broken (real break)** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-10 | 16:00 | 1,406.18 | long | bull | SL | -20.4 | broken |
| 2026-09-10 | 18:30 | 1,393.58 | long | bull | EOD | -12.1 | broken |

**Daily trend unclear / entries blocked** (9)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-16 | 09:30 | 1,382.42 | short | bull | EOD | -1.7 | Daily UP: parent correction (A1) |
| 2026-09-17 | 15:00 | 1,394.68 | short | bull | EOD | -9.9 | Daily UP: parent correction (A1) |
| 2026-09-18 | 12:30 | 1,406.68 | short | bull | EOD | -4.9 | Daily UP: parent correction (A1) |
| 2026-09-21 | 14:00 | 1,422.12 | short | bull | EOD | 1.3 | Daily UP: parent correction (A1) |
| 2026-09-23 | 19:30 | 1,415.38 | long | bull | EOD | 0.2 | Daily UP: parent correction (A1) |
| 2026-09-28 | 11:30 | 1,405.00 | long | bull | EOD | -0.5 | Daily UP: parent correction (A1) |
| 2026-10-05 | 18:30 | 1,409.28 | short | bull | EOD | -4.0 | Daily UP: parent correction (A1) |
| 2026-10-06 | 09:30 | 1,415.70 | short | bull | EOD | -0.3 | Daily UP: parent correction (A1) |
| 2026-10-07 | 13:00 | 1,416.32 | short | bull | EOD | -3.1 | Daily UP: parent correction (A1) |

