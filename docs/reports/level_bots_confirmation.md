# Level bots — touch vs confirmation replay (L6)

> **SAMPLE — full run pending.** Small slice only, to review the template. Every cell here is n < 30 ⇒ no conclusion.

Generated 2026-10-11 17:08 by `python3 scripts/level_bots_replay.py --start 2021-12-17,BANKNIFTY=2026-09-10,GOLD=2026-09-10,SILVER=2026-09-10,COPPER=2026-09-10 --max-days 20 --out data/research/level_bots_replay_sample --sample`.

Data: NIFTY 1m bars, replay 2021-12-17 → 2022-01-13 (20 days); BANKNIFTY 15m bars, replay 2026-09-10 → 2026-10-09 (20 days); GOLD 30m bars, replay 2026-09-10 → 2026-10-07 (19 days); SILVER 30m bars, replay 2026-09-10 → 2026-10-07 (19 days); COPPER 30m bars, replay 2026-09-10 → 2026-10-07 (19 days)

## How this replay works

- Same days, same levels, same position rules and cost model for every arm. Levels = the bots' Dynamic S/R (`sr_dynamic.compute_dynamic_sr`, refresh parameters and lookbacks), recomputed at the session open and every 60 min from closed bars only (no lookahead). Level memory is not replayed.
- **Touch (legacy)** entries = the bots' own functions imported from the bot files (`check_level_crossed`, `determine_direction_with_hysteresis`) with default settings (RSI thresholds). PCR gate skipped (no PCR history).
- Position rules (all arms, as live): one position at a time; max hits per (level, role) per day; 5M Instant and Classic: 30 min since the last trade on the same level and role; 5M Instant / SRv2 / Classic: 15 min after an SL / TSL exit on the same level; MCX: 60 min after a losing SL / TSL (symbol-wide) and no re-entry on a level + direction that hit a losing SL today; no new entry from the bot's cutoff (14:45; MCX 22:45); EOD square-off.
- **Confirmation** (live PAPER behaviour) entries = `level_reaction.evaluate` on closed confirmation-TF candles, exactly as the live cycle: an entry only on the commitment candle itself, at its close. Trend = one `decision3.daily.fold` per symbol + `state_at` per day (yesterday's close). Gate defaults: min R:R 3, max armed bars 8, area = level ± 0.05% / 2. RSI / PCR gates off, no breakout. **Exits = the bot's own exits, the same as touch** (live confirmation mode never touches exits) ⇒ for 5M Instant / SRv2 / Classic only the entry differs. MCX (L4): structural SL capped by the settings SL (wider ⇒ skipped `SKIPPED_GATE_SL_TOO_WIDE`), target = next opposite area, R:R re-checked at the entry price, one entry per confirmation.
- **confirmation + structural exit (not live)** = the same gate entries with the gate's structural SL (beyond the area's far edge + buffer) and next-area target, no TSL — a comparison arm for the NSE bots only; it is **not** what the bots do live.
- Bot exits replayed from `trading_engine.evaluate_point_spot_exit`, spot part only: naked spot-% SL / target from entry (MCX: settings points), TSL-to-breakeven once spot moves the naked TSL % (5M Instant 0.1%, 15M SRv2 0.1%, Classic 0.6%; sticky; live 'premium ≤ 0' read as spot ≤ entry). The premium-point SL / TSL / target legs and premium trailing cannot be replayed (no premium history) — live exits may fire earlier.
- Exit simulation on the next base bars: SL (or breakeven) before target when both are inside one bar (pessimistic); TSL activates from the bar after the trigger bar; a gap beyond SL fills at the open; EOD closes at the bar close. An entry on the session's last bar has no bar to exit on ⇒ not taken, listed as `dropped`. Index futures volume is not available for IS / VAL ⇒ volume NA ⇒ grade ≤ B (as live with volume NA).
- P&L is in **index / futures points** — intraday option premium history is not available. Cost per round trip (points) from `charges.py` (Upstox rates): 1 lot naked ITM option buy (premium / lot / delta / slippage in `COST_DEFAULTS`) ⇒ {'NIFTY': 3.18, 'BANKNIFTY': 6.66, 'GOLD': 28.26, 'SILVER': 43.11, 'COPPER': 0.36}.
- Period = `elliott.data_policy.period(day)` for every symbol. NIFTY: IS / VAL only; the HOLDOUT is never loaded (guard raises). BANKNIFTY: only 15M candles exist (≈ 3 months, not sealed, but the dates are CONTAMINATED / ILLUSTRATION — the gate's NIFTY design window ⇒ illustration, not validation); touch and exits on 15M bars; only 15M SRv2. MCX: 30m candles only (≈ 4 months, no volume) ⇒ confirmation on **30m** (live L4: 15m — no 15m data here); Daily trend from ≤ 4 months of Daily bars (live: front-month contract) ⇒ trend often UNKNOWN; MCX cascade / supertrend filters not replayed.
- Trend split = the gate's Daily trend that day (UP ⇒ bull, DOWN ⇒ bear, RANGE ⇒ range, NEUTRAL / UNKNOWN ⇒ no trend). A day whose trend is UP / DOWN but where the gate blocks new entries (origin broken / at risk, parent correction A1) stays in bull / bear; its legacy trades show the verdict "Daily trend unclear / entries blocked".
- Rejected legacy trades: the Daily trend check first (as in the gate); then the gate visit of the **same side** that contains the touch (arrival → the area is left after its first CONFIRMED / DISARMED): a live confirmation in that visit ⇒ kept; confirmed only after the cutoff ⇒ 'after cutoff'; the visit's DISARMED reason; still armed ⇒ 'no commitment'; no such visit ⇒ 'no arrival'.

Arms: **touch** (legacy = what LIVE bots do today) · **confirmation** (live PAPER behaviour: gate entry, the bot's own exits; MCX: L4 structural exits) · **confirmation + structural exit (not live)** (comparison only, NSE bots).

Cells with n < 30 carry **no conclusion** (numbers shown for reference only).

## Conclusions (cells with n ≥ 30 in both arms compared)

- None — no cell reaches n ≥ 30 in both arms compared.

## 5M Instant — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 24 | 21% | -3.24 | -77.9 | 90.7 | 0.64 | n < 30 — no conclusion |
| IS | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | all | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | touch | 24 | 21% | -3.24 | -77.9 | 90.7 | 0.64 | n < 30 — no conclusion |
| IS | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 18 | 22% | -3.01 | -54.3 | 79.1 | 0.65 | n < 30 — no conclusion |
| VAL | all | confirmation | 1 | 100% | 32.17 | 32.2 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | all | confirmation + structural exit (not live) | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | bull | touch | 18 | 22% | -3.01 | -54.3 | 79.1 | 0.65 | n < 30 — no conclusion |
| VAL | bull | confirmation | 1 | 100% | 32.17 | 32.2 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | bull | confirmation + structural exit (not live) | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 42 · kept by the gate: 1 (taken by the confirmation arm: 1) · rejected: 41.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | Daily trend unclear / entries blocked | 24 | 5 | -77.9 | -3.24 | 77.9 | n < 30 |
| VAL | against the Daily trend | 8 | 2 | -30.6 | -3.82 | 30.6 | n < 30 |
| VAL | area broken (real break) | 5 | 0 | -51.6 | -10.33 | 51.6 | n < 30 |
| VAL | kept — the gate confirmed the same visit and side | 1 | 1 | 32.1 | 32.14 | — | n < 30 |
| VAL | impulsive approach | 1 | 0 | -12.0 | -12.04 | 12.0 | n < 30 |
| VAL | no opposite area for a target | 1 | 0 | -12.3 | -12.27 | 12.3 | n < 30 |
| VAL | Daily trend unclear / entries blocked | 1 | 0 | -12.8 | -12.78 | 12.8 | n < 30 |
| VAL | timeout — no commitment within max_armed_bars | 1 | 1 | 32.9 | 32.90 | -32.9 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**Daily trend unclear / entries blocked** (25)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2021-12-17 | 09:18 | 17,217.88 | long | bull | SL | -11.8 | Daily UP: parent correction (A1) |
| 2021-12-17 | 14:43 | 17,000.53 | long | bull | TSL_SL | -3.2 | Daily UP: parent correction (A1) |
| 2021-12-23 | 09:43 | 17,086.43 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 09:36 | 17,036.97 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 09:40 | 17,017.07 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 10:11 | 16,926.85 | long | bull | SL | -11.6 | Daily UP: parent correction (A1) |
| 2021-12-24 | 10:41 | 16,926.85 | long | bull | TARGET | 30.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 13:56 | 17,009.70 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-24 | 14:15 | 17,040.80 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 09:22 | 16,835.15 | long | bull | TARGET | 30.5 | Daily UP: parent correction (A1) |
| 2021-12-27 | 09:51 | 16,964.32 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 10:34 | 16,996.97 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 12:17 | 17,029.12 | short | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-28 | 14:40 | 17,210.32 | long | bull | SL | -11.8 | Daily UP: parent correction (A1) |
| 2021-12-29 | 09:20 | 17,234.68 | short | bull | TARGET | 31.3 | Daily UP: parent correction (A1) |

**area broken (real break)** (5)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-06 | 09:16 | 17,761.15 | long | bull | SL | -12.1 | broken |
| 2022-01-07 | 10:54 | 17,853.45 | long | bull | SL | -12.1 | broken |
| 2022-01-07 | 12:17 | 17,770.42 | long | bull | TSL_SL | -3.2 | broken |
| 2022-01-07 | 14:09 | 17,770.42 | long | bull | SL | -12.1 | broken |
| 2022-01-11 | 14:34 | 18,040.93 | long | bull | SL | -12.2 | broken |

**against the Daily trend** (8)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-06 | 14:26 | 17,761.15 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-07 | 09:21 | 17,853.45 | short | bull | SL | -12.4 | Daily UP |
| 2022-01-07 | 13:04 | 17,770.42 | short | bull | TSL_SL | -3.2 | Daily UP |
| 2022-01-07 | 13:34 | 17,770.42 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-07 | 14:42 | 17,790.00 | short | bull | EOD | 16.7 | Daily UP |
| 2022-01-12 | 14:44 | 18,201.35 | short | bull | SL | -12.3 | Daily UP |
| 2022-01-13 | 11:55 | 18,246.28 | short | bull | SL | -12.3 | Daily UP |
| 2022-01-13 | 14:05 | 18,246.28 | short | bull | EOD | 17.0 | Daily UP |

**impulsive approach** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-07 | 12:46 | 17,725.05 | long | bull | SL | -12.0 | impulsive approach |

**timeout — no commitment within max_armed_bars** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-11 | 13:56 | 18,040.93 | long | bull | TARGET | 32.9 | timeout |

**no opposite area for a target** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-13 | 10:39 | 18,178.92 | long | bull | SL | -12.3 | no target area |

## 15M SRv2 — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 6 | 17% | 1.12 | 6.7 | 35.1 | 1.11 | n < 30 — no conclusion |
| IS | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | all | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | touch | 6 | 17% | 1.12 | 6.7 | 35.1 | 1.11 | n < 30 — no conclusion |
| IS | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 3 | 0% | -9.15 | -27.4 | 27.4 | 0.00 | n < 30 — no conclusion |
| VAL | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | bull | touch | 3 | 0% | -9.15 | -27.4 | 27.4 | 0.00 | n < 30 — no conclusion |
| VAL | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | bull | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 9 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 9.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | Daily trend unclear / entries blocked | 6 | 1 | 6.7 | 1.12 | -6.7 | n < 30 |
| VAL | against the Daily trend | 3 | 0 | -27.4 | -9.15 | 27.4 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**Daily trend unclear / entries blocked** (6)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2021-12-17 | 10:40 | 17,042.10 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-17 | 11:08 | 17,042.10 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-27 | 09:50 | 16,951.25 | long | bull | SL | -11.7 | Daily UP: parent correction (A1) |
| 2021-12-30 | 09:16 | 17,153.88 | long | bull | TARGET | 65.5 | Daily UP: parent correction (A1) |
| 2021-12-31 | 09:34 | 17,330.18 | short | bull | SL | -11.8 | Daily UP: parent correction (A1) |
| 2021-12-31 | 09:52 | 17,330.18 | short | bull | SL | -11.8 | Daily UP: parent correction (A1) |

**against the Daily trend** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-10 | 09:30 | 17,924.43 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-10 | 09:47 | 17,924.43 | short | bull | SL | -12.1 | Daily UP |
| 2022-01-13 | 12:22 | 18,246.28 | short | bull | TSL_SL | -3.2 | Daily UP |

## Classic — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 13 | 62% | 36.57 | 475.4 | 72.5 | 2.92 | n < 30 — no conclusion |
| IS | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | all | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | touch | 13 | 62% | 36.57 | 475.4 | 72.5 | 2.92 | n < 30 — no conclusion |
| IS | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | bull | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 8 | 50% | 1.60 | 12.8 | 140.4 | 1.05 | n < 30 — no conclusion |
| VAL | all | confirmation | 1 | 100% | 79.22 | 79.2 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | all | confirmation + structural exit (not live) | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | bull | touch | 8 | 50% | 1.60 | 12.8 | 140.4 | 1.05 | n < 30 — no conclusion |
| VAL | bull | confirmation | 1 | 100% | 79.22 | 79.2 | 0.0 | ∞ | n < 30 — no conclusion |
| VAL | bull | confirmation + structural exit (not live) | 1 | 100% | 78.28 | 78.3 | 0.0 | ∞ | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 21 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 21.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | Daily trend unclear / entries blocked | 13 | 8 | 475.4 | 36.57 | -475.4 | n < 30 |
| VAL | against the Daily trend | 3 | 1 | -24.3 | -8.11 | 24.3 | n < 30 |
| VAL | area broken (real break) | 1 | 0 | -74.4 | -74.43 | 74.4 | n < 30 |
| VAL | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 1 | 1 | 24.4 | 24.42 | -24.4 | n < 30 |
| VAL | no opposite area for a target | 1 | 1 | 66.1 | 66.07 | -66.1 | n < 30 |
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

**no opposite area for a target** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-11 | 10:17 | 17,960.82 | long | bull | EOD | 66.1 | no target area |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2022-01-13 | 10:14 | 18,178.92 | long | bull | EOD | 24.4 |  |

## 15M SRv2 — BANKNIFTY

> ⚠️ **ILLUSTRATION — dates fall in CONTAMINATED / ILLUSTRATION (elliott.data_policy): not IS / VAL validation.**

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| CONTAMINATED | all | touch | 4 | 25% | -2.89 | -11.6 | 69.8 | 0.89 | n < 30 — no conclusion |
| CONTAMINATED | all | confirmation | 1 | 0% | -34.21 | -34.2 | 34.2 | 0.00 | n < 30 — no conclusion |
| CONTAMINATED | all | confirmation + structural exit (not live) | 1 | 100% | 65.74 | 65.7 | 0.0 | ∞ | n < 30 — no conclusion |
| CONTAMINATED | bear | touch | 4 | 25% | -2.89 | -11.6 | 69.8 | 0.89 | n < 30 — no conclusion |
| CONTAMINATED | bear | confirmation | 1 | 0% | -34.21 | -34.2 | 34.2 | 0.00 | n < 30 — no conclusion |
| CONTAMINATED | bear | confirmation + structural exit (not live) | 1 | 100% | 65.74 | 65.7 | 0.0 | ∞ | n < 30 — no conclusion |
| ILLUSTRATION | all | touch | 2 | 0% | -20.46 | -40.9 | 40.9 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | all | confirmation | 1 | 0% | -6.66 | -6.7 | 6.7 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | all | confirmation + structural exit (not live) | 1 | 0% | -178.28 | -178.3 | 178.3 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | bear | touch | 2 | 0% | -20.46 | -40.9 | 40.9 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | bear | confirmation | 1 | 0% | -6.66 | -6.7 | 6.7 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | bear | confirmation + structural exit (not live) | 1 | 0% | -178.28 | -178.3 | 178.3 | 0.00 | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 6 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 6.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | R:R below minimum | 2 | 1 | 58.2 | 29.10 | -58.2 | n < 30 |
| CONTAMINATED | gate confirmed, but after the no-new-entry cutoff | 1 | 0 | -34.9 | -34.87 | 34.9 | n < 30 |
| CONTAMINATED | area broken (real break) | 1 | 0 | -34.9 | -34.90 | 34.9 | n < 30 |
| ILLUSTRATION | impulsive approach | 2 | 0 | -40.9 | -20.46 | 40.9 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**area broken (real break)** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-11 | 14:00 | 56,470.52 | short | bear | SL | -34.9 | broken |

**gate confirmed, but after the no-new-entry cutoff** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-18 | 14:15 | 56,426.55 | short | bear | SL | -34.9 | confirmed after the no-new-entry cutoff |

**R:R below minimum** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-21 | 14:00 | 56,656.75 | short | bear | EOD | 93.2 | R:R < min (0.75 < 3) |
| 2026-09-22 | 09:45 | 56,656.75 | short | bear | SL | -35.0 | R:R < min (0.43 < 3) |

**impulsive approach** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-10-09 | 10:00 | 55,207.82 | short | bear | SL | -34.2 | impulsive approach |
| 2026-10-09 | 10:30 | 55,207.82 | short | bear | TSL_SL | -6.7 | impulsive approach |

## MCX — GOLD

> ⚠️ **ILLUSTRATION — MCX settings defaults are one SL / target in futures points for every commodity (20 / 40; no per-commodity defaults exist) ⇒ unrealistic for GOLD / SILVER / COPPER; ≈ 4 months of 30m data, no volume, Daily trend from ≤ 4 months.**

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| CONTAMINATED | all | touch | 9 | 11% | -53.81 | -484.3 | 495.5 | 0.02 | n < 30 — no conclusion |
| CONTAMINATED | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | bull | touch | 9 | 11% | -53.81 | -484.3 | 495.5 | 0.02 | n < 30 — no conclusion |
| CONTAMINATED | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

- skipped (confirmation): SKIPPED_GATE_SL_TOO_WIDE × 2

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 9 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 9.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | against the Daily trend | 3 | 0 | -188.0 | -62.68 | 188.0 | n < 30 |
| CONTAMINATED | area broken (real break) | 2 | 0 | -130.4 | -65.20 | 130.4 | n < 30 |
| CONTAMINATED | R:R below minimum | 2 | 0 | -97.2 | -48.60 | 97.2 | n < 30 |
| CONTAMINATED | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 1 | 0 | -79.8 | -79.82 | 79.8 | n < 30 |
| CONTAMINATED | timeout — no commitment within max_armed_bars | 1 | 1 | 11.1 | 11.15 | -11.1 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**timeout — no commitment within max_armed_bars** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-10 | 18:30 | 153,494.50 | long | bull | TARGET | 11.1 | timeout |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-11 | 10:30 | 153,216.00 | long | bull | SL | -79.8 |  |

**against the Daily trend** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-16 | 11:00 | 153,216.00 | short | bull | SL | -88.8 | Daily UP |
| 2026-09-17 | 18:30 | 154,485.00 | short | bull | SL | -49.0 | Daily UP |
| 2026-09-18 | 12:00 | 155,565.00 | short | bull | SL | -50.2 | Daily UP |

**area broken (real break)** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-17 | 10:00 | 152,128.00 | long | bull | SL | -81.6 | broken |
| 2026-09-24 | 12:30 | 152,941.00 | long | bull | SL | -48.8 | broken |

**R:R below minimum** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-10-05 | 10:30 | 148,966.50 | long | bull | SL | -48.1 | R:R < min (1.08 < 3) |
| 2026-10-06 | 10:30 | 148,966.50 | long | bull | SL | -49.1 | R:R < min (2.18 < 3) |

## MCX — SILVER

> ⚠️ **ILLUSTRATION — MCX settings defaults are one SL / target in futures points for every commodity (20 / 40; no per-commodity defaults exist) ⇒ unrealistic for GOLD / SILVER / COPPER; ≈ 4 months of 30m data, no volume, Daily trend from ≤ 4 months.**

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| CONTAMINATED | all | touch | 8 | 0% | -55.50 | -444.0 | 444.0 | 0.00 | n < 30 — no conclusion |
| CONTAMINATED | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | bear | touch | 1 | 0% | -116.33 | -116.3 | 116.3 | 0.00 | n < 30 — no conclusion |
| CONTAMINATED | bear | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | no trend | touch | 7 | 0% | -46.81 | -327.7 | 327.7 | 0.00 | n < 30 — no conclusion |
| CONTAMINATED | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 8 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 8.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | Daily trend unclear / entries blocked | 7 | 0 | -327.7 | -46.81 | 327.7 | n < 30 |
| CONTAMINATED | against the Daily trend | 1 | 0 | -116.3 | -116.33 | 116.3 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay_sample/trades.csv`)

**Daily trend unclear / entries blocked** (7)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-10 | 18:00 | 236,853.00 | long | no trend | SL | -64.3 | Daily NEUTRAL |
| 2026-09-14 | 21:00 | 231,040.50 | long | no trend | SL | -63.3 | Daily NEUTRAL |
| 2026-09-15 | 14:30 | 230,010.50 | long | no trend | TARGET | -3.1 | Daily NEUTRAL |
| 2026-09-15 | 15:00 | 230,010.50 | long | no trend | TARGET | -3.2 | Daily NEUTRAL |
| 2026-09-18 | 13:00 | 242,149.50 | short | no trend | SL | -65.2 | Daily NEUTRAL |
| 2026-09-22 | 13:30 | 236,790.00 | long | no trend | SL | -64.3 | Daily NEUTRAL |
| 2026-09-25 | 16:00 | 236,667.00 | short | no trend | SL | -64.3 | Daily NEUTRAL |

**against the Daily trend** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-30 | 17:00 | 225,300.50 | long | bear | SL | -116.3 | Daily DOWN |

## MCX — COPPER

> ⚠️ **ILLUSTRATION — MCX settings defaults are one SL / target in futures points for every commodity (20 / 40; no per-commodity defaults exist) ⇒ unrealistic for GOLD / SILVER / COPPER; ≈ 4 months of 30m data, no volume, Daily trend from ≤ 4 months.**

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| CONTAMINATED | all | touch | 11 | 18% | -5.02 | -55.3 | 55.3 | 0.03 | n < 30 — no conclusion |
| CONTAMINATED | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | bull | touch | 11 | 18% | -5.02 | -55.3 | 55.3 | 0.03 | n < 30 — no conclusion |
| CONTAMINATED | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 11 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 11.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | Daily trend unclear / entries blocked | 9 | 2 | -22.8 | -2.54 | 22.8 | n < 30 |
| CONTAMINATED | area broken (real break) | 2 | 0 | -32.4 | -16.21 | 32.4 | n < 30 |

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

