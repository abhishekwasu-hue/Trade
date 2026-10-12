# Level bots — touch vs confirmation replay (L6)

Generated 2026-10-11 17:33 by `python3 scripts/level_bots_replay.py`.

Data: NIFTY 1m bars, replay 2015-01-09 → 2024-03-27 (2282 days); BANKNIFTY 15m bars, replay 2026-07-13 → 2026-10-09 (63 days); GOLD 30m bars, replay 2026-06-19 → 2026-10-07 (78 days); SILVER 30m bars, replay 2026-06-19 → 2026-10-07 (78 days); COPPER 30m bars, replay 2026-06-19 → 2026-10-07 (78 days)

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

- Classic · NIFTY · IS · all · confirmation: net expectancy -0.05 (n 143) vs touch -5.60 (n 2661) ⇒ +5.55 pts/trade; max DD 458.6 vs 15,644.2; PF 1.00 vs 0.74.
- Classic · NIFTY · IS · all · confirmation + structural exit (not live): net expectancy 1.52 (n 148) vs touch -5.60 (n 2661) ⇒ +7.12 pts/trade; max DD 306.9 vs 15,644.2; PF 1.12 vs 0.74.
- Classic · NIFTY · IS · bull · confirmation: net expectancy -0.01 (n 78) vs touch -6.19 (n 1546) ⇒ +6.19 pts/trade; max DD 331.9 vs 10,281.2; PF 1.00 vs 0.74.
- Classic · NIFTY · IS · bull · confirmation + structural exit (not live): net expectancy 2.85 (n 81) vs touch -6.19 (n 1546) ⇒ +9.04 pts/trade; max DD 223.1 vs 10,281.2; PF 1.23 vs 0.74.
- Classic · NIFTY · IS · bear · confirmation: net expectancy -0.10 (n 65) vs touch -4.73 (n 1065) ⇒ +4.64 pts/trade; max DD 393.3 vs 5,307.5; PF 0.99 vs 0.75.
- Classic · NIFTY · IS · bear · confirmation + structural exit (not live): net expectancy -0.09 (n 67) vs touch -4.73 (n 1065) ⇒ +4.64 pts/trade; max DD 397.5 vs 5,307.5; PF 0.99 vs 0.75.
- 5M Instant · NIFTY · IS · all · confirmation: net expectancy -2.95 (n 115) vs touch -2.91 (n 4859) ⇒ -0.04 pts/trade; max DD 370.1 vs 14,165.3; PF 0.52 vs 0.53.
- 5M Instant · NIFTY · IS · all · confirmation + structural exit (not live): net expectancy -1.49 (n 109) vs touch -2.91 (n 4859) ⇒ +1.42 pts/trade; max DD 439.2 vs 14,165.3; PF 0.90 vs 0.53.
- 5M Instant · NIFTY · IS · bull · confirmation: net expectancy -1.90 (n 63) vs touch -3.04 (n 2996) ⇒ +1.15 pts/trade; max DD 152.2 vs 9,140.0; PF 0.70 vs 0.54.
- 5M Instant · NIFTY · IS · bull · confirmation + structural exit (not live): net expectancy 5.85 (n 59) vs touch -3.04 (n 2996) ⇒ +8.89 pts/trade; max DD 167.0 vs 9,140.0; PF 1.45 vs 0.54.
- 5M Instant · NIFTY · IS · bear · confirmation: net expectancy -4.23 (n 52) vs touch -2.72 (n 1768) ⇒ -1.51 pts/trade; max DD 235.1 vs 4,827.6; PF 0.30 vs 0.50.
- 5M Instant · NIFTY · IS · bear · confirmation + structural exit (not live): net expectancy -10.15 (n 50) vs touch -2.72 (n 1768) ⇒ -7.43 pts/trade; max DD 591.8 vs 4,827.6; PF 0.39 vs 0.50.
- 15M SRv2 · NIFTY · IS · all · confirmation: net expectancy -3.18 (n 46) vs touch -2.84 (n 1340) ⇒ -0.34 pts/trade; max DD 186.5 vs 3,894.3; PF 0.51 vs 0.56.
- 15M SRv2 · NIFTY · IS · all · confirmation + structural exit (not live): net expectancy 9.43 (n 43) vs touch -2.84 (n 1340) ⇒ +12.27 pts/trade; max DD 270.6 vs 3,894.3; PF 1.58 vs 0.56.
- Classic · NIFTY · VAL · all · confirmation: net expectancy -8.09 (n 36) vs touch -1.67 (n 769) ⇒ -6.42 pts/trade; max DD 390.4 vs 2,601.6; PF 0.70 vs 0.95.
- Classic · NIFTY · VAL · all · confirmation + structural exit (not live): net expectancy -6.26 (n 36) vs touch -1.67 (n 769) ⇒ -4.59 pts/trade; max DD 324.2 vs 2,601.6; PF 0.71 vs 0.95.
- Classic · NIFTY · VAL · bull · confirmation: net expectancy -8.09 (n 36) vs touch -1.67 (n 769) ⇒ -6.42 pts/trade; max DD 390.4 vs 2,601.6; PF 0.70 vs 0.95.
- Classic · NIFTY · VAL · bull · confirmation + structural exit (not live): net expectancy -6.26 (n 36) vs touch -1.67 (n 769) ⇒ -4.59 pts/trade; max DD 324.2 vs 2,601.6; PF 0.71 vs 0.95.

## 5M Instant — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 4859 | 18% | -2.91 | -14,135.9 | 14,165.3 | 0.53 |  |
| IS | all | confirmation | 115 | 17% | -2.95 | -339.3 | 370.1 | 0.52 |  |
| IS | all | confirmation + structural exit (not live) | 109 | 28% | -1.49 | -162.3 | 439.2 | 0.90 |  |
| IS | bull | touch | 2996 | 18% | -3.04 | -9,120.1 | 9,140.0 | 0.54 |  |
| IS | bull | confirmation | 63 | 21% | -1.90 | -119.4 | 152.2 | 0.70 |  |
| IS | bull | confirmation + structural exit (not live) | 59 | 39% | 5.85 | 345.2 | 167.0 | 1.45 |  |
| IS | bear | touch | 1768 | 19% | -2.72 | -4,805.6 | 4,827.6 | 0.50 |  |
| IS | bear | confirmation | 52 | 12% | -4.23 | -219.9 | 235.1 | 0.30 |  |
| IS | bear | confirmation + structural exit (not live) | 50 | 14% | -10.15 | -507.5 | 591.8 | 0.39 |  |
| IS | no trend | touch | 95 | 21% | -2.21 | -210.2 | 258.4 | 0.57 |  |
| IS | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | no trend | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 1539 | 19% | -2.71 | -4,177.9 | 4,328.7 | 0.69 |  |
| VAL | all | confirmation | 16 | 12% | -4.89 | -78.3 | 110.4 | 0.47 | n < 30 — no conclusion |
| VAL | all | confirmation + structural exit (not live) | 16 | 25% | -11.20 | -179.3 | 272.0 | 0.45 | n < 30 — no conclusion |
| VAL | bull | touch | 1539 | 19% | -2.71 | -4,177.9 | 4,328.7 | 0.69 |  |
| VAL | bull | confirmation | 16 | 12% | -4.89 | -78.3 | 110.4 | 0.47 | n < 30 — no conclusion |
| VAL | bull | confirmation + structural exit (not live) | 16 | 25% | -11.20 | -179.3 | 272.0 | 0.45 | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 6398 · kept by the gate: 77 (taken by the confirmation arm: 77) · rejected: 6321.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | against the Daily trend | 2048 | 388 | -5,805.7 | -2.83 | 5,805.7 |  |
| IS | area broken (real break) | 1026 | 31 | -7,474.7 | -7.29 | 7,474.7 |  |
| IS | Daily trend unclear / entries blocked | 701 | 143 | -1,823.4 | -2.60 | 1,823.4 |  |
| IS | R:R below minimum | 370 | 140 | 1,145.6 | 3.10 | -1,145.6 |  |
| IS | timeout — no commitment within max_armed_bars | 267 | 68 | -166.1 | -0.62 | 166.1 |  |
| IS | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 104 | 22 | -249.0 | -2.39 | 249.0 |  |
| IS | no opposite area for a target | 102 | 41 | 324.4 | 3.18 | -324.4 |  |
| IS | impulsive approach | 86 | 15 | -244.1 | -2.84 | 244.1 |  |
| IS | timeout — counter side absorbing inside the area | 73 | 20 | -2.1 | -0.03 | 2.1 |  |
| IS | kept — the gate confirmed the same visit and side | 68 | 27 | 193.1 | 2.84 | — |  |
| IS | confirmed only in hindsight (not on the live cycle) | 10 | 1 | -50.2 | -5.02 | 50.2 | n < 30 |
| IS | gate confirmed, but after the no-new-entry cutoff | 4 | 2 | 16.2 | 4.06 | -16.2 | n < 30 |
| VAL | against the Daily trend | 603 | 131 | -1,086.4 | -1.80 | 1,086.4 |  |
| VAL | Daily trend unclear / entries blocked | 350 | 67 | -1,058.6 | -3.02 | 1,058.6 |  |
| VAL | area broken (real break) | 284 | 7 | -2,969.9 | -10.46 | 2,969.9 |  |
| VAL | R:R below minimum | 113 | 44 | 789.6 | 6.99 | -789.6 |  |
| VAL | timeout — no commitment within max_armed_bars | 61 | 19 | 238.4 | 3.91 | -238.4 |  |
| VAL | impulsive approach | 39 | 5 | -262.3 | -6.72 | 262.3 |  |
| VAL | no opposite area for a target | 34 | 12 | 211.5 | 6.22 | -211.5 |  |
| VAL | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 28 | 5 | -48.2 | -1.72 | 48.2 | n < 30 |
| VAL | timeout — counter side absorbing inside the area | 17 | 6 | 0.5 | 0.03 | -0.5 | n < 30 |
| VAL | kept — the gate confirmed the same visit and side | 9 | 2 | -5.0 | -0.56 | — | n < 30 |
| VAL | gate confirmed, but after the no-new-entry cutoff | 1 | 1 | 12.5 | 12.52 | -12.5 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay/trades.csv`)

**Daily trend unclear / entries blocked** (1051)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-01-12 | 13:14 | 8,274.35 | short | no trend | TSL_SL | -3.2 | Daily UNKNOWN |
| 2015-01-12 | 14:23 | 8,294.38 | short | no trend | SL | -7.3 | Daily UNKNOWN |
| 2015-01-13 | 13:18 | 8,349.65 | short | no trend | SL | -7.4 | Daily UNKNOWN |
| 2015-01-13 | 13:48 | 8,349.65 | short | no trend | TARGET | 13.5 | Daily UNKNOWN |
| 2015-01-13 | 14:30 | 8,322.30 | long | no trend | SL | -7.3 | Daily UNKNOWN |
| 2015-01-13 | 14:42 | 8,294.38 | long | no trend | SL | -7.3 | Daily UNKNOWN |
| 2015-01-13 | 14:44 | 8,274.35 | long | no trend | SL | -7.3 | Daily UNKNOWN |
| 2015-01-14 | 09:22 | 8,294.38 | long | no trend | TARGET | 13.4 | Daily UNKNOWN |
| 2015-01-14 | 09:42 | 8,322.30 | short | no trend | TARGET | 13.5 | Daily UNKNOWN |
| 2015-01-14 | 10:18 | 8,294.38 | long | no trend | TARGET | 13.4 | Daily UNKNOWN |
| 2015-01-14 | 12:05 | 8,272.12 | long | no trend | TSL_SL | -3.2 | Daily UNKNOWN |
| 2015-01-14 | 12:27 | 8,249.05 | long | no trend | SL | -7.5 | Daily UNKNOWN |
| 2015-01-14 | 13:33 | 8,249.05 | long | no trend | TARGET | 13.3 | Daily UNKNOWN |
| 2015-01-14 | 14:10 | 8,272.12 | short | no trend | SL | -7.3 | Daily UNKNOWN |
| 2015-01-14 | 14:17 | 8,294.38 | short | no trend | SL | -7.3 | Daily UNKNOWN |

**area broken (real break)** (1310)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-02 | 10:52 | 8,930.17 | long | bull | SL | -7.6 | broken |
| 2015-03-03 | 13:48 | 8,970.62 | long | bull | SL | -7.7 | broken |
| 2015-03-04 | 14:42 | 8,954.35 | long | bull | TSL_SL | -3.9 | broken |
| 2015-03-05 | 11:52 | 8,902.60 | long | bull | SL | -7.6 | broken |
| 2015-03-05 | 12:48 | 8,890.08 | long | bull | SL | -7.6 | broken |
| 2015-03-09 | 13:14 | 8,802.83 | long | bull | SL | -7.6 | broken |
| 2015-03-10 | 13:14 | 8,739.75 | long | bull | SL | -7.6 | broken |
| 2015-03-13 | 10:08 | 8,757.70 | long | bull | SL | -7.6 | broken |
| 2015-03-13 | 14:01 | 8,680.03 | long | bull | SL | -7.5 | broken |
| 2015-04-29 | 12:56 | 8,274.33 | short | bear | SL | -7.3 | broken |
| 2015-04-30 | 14:18 | 8,190.65 | short | bear | SL | -7.3 | broken |
| 2015-05-04 | 10:49 | 8,268.80 | short | bear | SL | -7.3 | broken |
| 2015-05-05 | 13:33 | 8,307.30 | short | bear | TSL_SL | -3.2 | broken |
| 2015-05-08 | 09:21 | 8,153.88 | short | bear | SL | -7.3 | broken |
| 2015-05-11 | 11:08 | 8,287.40 | short | bear | SL | -7.3 | broken |

**against the Daily trend** (2651)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-02 | 12:34 | 8,930.17 | short | bull | TARGET | 14.7 | Daily UP |
| 2015-03-02 | 14:26 | 8,930.17 | short | bull | SL | -7.6 | Daily UP |
| 2015-03-03 | 12:50 | 8,970.62 | short | bull | SL | -8.4 | Daily UP |
| 2015-03-05 | 13:56 | 8,890.08 | short | bull | SL | -12.4 | Daily UP |
| 2015-04-28 | 13:15 | 8,207.92 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-04-28 | 14:07 | 8,207.92 | long | bear | TARGET | 13.2 | Daily DOWN |
| 2015-04-29 | 14:03 | 8,274.33 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-04-29 | 14:34 | 8,274.33 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-04-30 | 09:17 | 8,190.28 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-05-04 | 14:25 | 8,270.05 | long | bear | TARGET | 13.3 | Daily DOWN |
| 2015-05-05 | 09:35 | 8,300.12 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-05-05 | 13:14 | 8,300.12 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-05-05 | 14:31 | 8,307.30 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-05-06 | 09:17 | 8,300.12 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-05-06 | 09:38 | 8,285.25 | long | bear | SL | -7.3 | Daily DOWN |

**no opposite area for a target** (136)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-03 | 09:17 | 8,930.17 | long | bull | TSL_SL | -3.2 | no target area |
| 2015-04-30 | 11:50 | 8,190.28 | short | bear | SL | -7.3 | no target area |
| 2015-05-06 | 13:41 | 8,144.30 | short | bear | TARGET | 13.1 | no target area |
| 2015-05-06 | 14:13 | 8,144.30 | short | bear | SL | -7.3 | no target area |
| 2015-06-09 | 09:44 | 8,056.28 | short | bear | TARGET | 12.9 | no target area |
| 2015-10-13 | 14:34 | 8,109.62 | short | bear | EOD | -1.1 | no target area |
| 2015-11-13 | 12:22 | 7,760.80 | short | bear | TSL_SL | -3.2 | no target area |
| 2015-11-13 | 13:03 | 7,760.80 | short | bear | SL | -8.5 | no target area |
| 2016-01-19 | 09:17 | 7,386.65 | short | bear | SL | -6.9 | no target area |
| 2016-02-03 | 14:32 | 7,416.48 | short | bear | TARGET | 11.6 | no target area |
| 2016-03-16 | 14:06 | 7,454.22 | short | bear | TSL_SL | -3.2 | no target area |
| 2016-03-29 | 09:49 | 7,643.62 | short | bear | TARGET | 12.1 | no target area |
| 2016-05-04 | 13:16 | 7,742.05 | short | bear | SL | -7.1 | no target area |
| 2016-05-06 | 10:33 | 7,707.80 | short | bear | TSL_SL | -3.2 | no target area |
| 2016-05-06 | 11:51 | 7,707.80 | short | bear | SL | -7.0 | no target area |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (132)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-04 | 14:15 | 9,027.62 | long | bull | SL | -8.3 |  |
| 2015-10-07 | 11:06 | 8,175.80 | short | bear | SL | -7.3 |  |
| 2015-11-27 | 09:46 | 7,901.35 | short | bear | SL | -7.1 |  |
| 2015-12-01 | 12:04 | 7,965.30 | short | bear | SL | -7.2 |  |
| 2016-01-07 | 14:18 | 7,596.72 | short | bear | TARGET | 12.0 |  |
| 2016-01-08 | 12:28 | 7,593.52 | short | bear | SL | -7.0 |  |
| 2016-03-30 | 11:51 | 7,671.05 | short | bear | TSL_SL | -3.2 |  |
| 2016-05-05 | 13:57 | 7,743.35 | short | bear | SL | -7.1 |  |
| 2016-05-23 | 13:41 | 7,774.75 | short | bear | SL | -7.1 |  |
| 2016-06-10 | 14:28 | 8,182.65 | short | bear | SL | -7.3 |  |
| 2016-07-08 | 13:18 | 8,320.48 | short | bear | SL | -7.3 |  |
| 2016-10-20 | 13:09 | 8,693.92 | short | bear | SL | -7.5 |  |
| 2017-01-10 | 13:21 | 8,282.08 | short | bear | SL | -7.3 |  |
| 2017-01-10 | 14:36 | 8,282.08 | short | bear | EOD | 0.7 |  |
| 2017-01-17 | 14:13 | 8,393.15 | short | bear | TSL_SL | -3.2 |  |

**R:R below minimum** (483)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-05 | 09:59 | 8,902.60 | long | bull | SL | -7.6 | R:R < min (1.12 < 3) |
| 2015-05-04 | 14:07 | 8,300.12 | short | bear | TARGET | 13.4 | R:R < min (1.06 < 3) |
| 2015-05-13 | 14:01 | 8,239.72 | short | bear | SL | -7.3 | R:R < min (1.96 < 3) |
| 2015-05-14 | 13:24 | 8,200.78 | short | bear | SL | -7.3 | R:R < min (0.76 < 3) |
| 2015-05-20 | 11:16 | 8,433.88 | short | bear | TARGET | 13.7 | R:R < min (2.60 < 3) |
| 2015-05-21 | 09:20 | 8,433.88 | short | bear | SL | -7.4 | R:R < min (0.50 < 3) |
| 2015-05-22 | 09:17 | 8,434.88 | short | bear | TSL_SL | -3.2 | R:R < min (1.97 < 3) |
| 2015-06-09 | 13:55 | 8,049.15 | short | bear | SL | -7.2 | R:R < min (0.64 < 3) |
| 2015-06-25 | 10:17 | 8,371.20 | short | bear | TSL_SL | -3.2 | R:R < min (1.54 < 3) |
| 2015-06-25 | 13:59 | 8,404.52 | short | bear | TSL_SL | -3.2 | R:R < min (2.35 < 3) |
| 2015-06-26 | 14:16 | 8,394.22 | short | bear | SL | -7.4 | R:R < min (1.22 < 3) |
| 2015-09-10 | 13:29 | 7,769.35 | short | bear | TARGET | 12.4 | R:R < min (0.74 < 3) |
| 2015-09-15 | 13:16 | 7,856.95 | short | bear | TARGET | 12.5 | R:R < min (1.20 < 3) |
| 2015-09-30 | 12:52 | 7,919.20 | short | bear | SL | -7.1 | R:R < min (1.39 < 3) |
| 2015-09-30 | 14:17 | 7,919.20 | short | bear | TSL_SL | -3.2 | R:R < min (1.56 < 3) |

**timeout — no commitment within max_armed_bars** (328)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-13 | 11:18 | 8,730.10 | long | bull | TSL_SL | -3.2 | timeout |
| 2015-03-13 | 13:17 | 8,680.03 | long | bull | TARGET | 14.2 | timeout |
| 2015-05-28 | 09:17 | 8,362.42 | short | bear | SL | -7.4 | timeout |
| 2015-05-29 | 10:17 | 8,362.42 | short | bear | SL | -7.4 | timeout |
| 2015-06-10 | 09:44 | 8,102.50 | short | bear | TARGET | 13.0 | timeout |
| 2015-06-10 | 10:18 | 8,102.50 | short | bear | SL | -7.2 | timeout |
| 2015-06-10 | 12:04 | 8,105.88 | short | bear | SL | -7.2 | timeout |
| 2015-06-24 | 11:19 | 8,405.42 | short | bear | TSL_SL | -3.2 | timeout |
| 2015-06-24 | 12:28 | 8,405.42 | short | bear | SL | -7.4 | timeout |
| 2015-06-30 | 09:16 | 8,347.42 | short | bear | SL | -7.4 | timeout |
| 2015-08-27 | 09:16 | 7,914.42 | short | bear | SL | -7.1 | timeout |
| 2015-10-07 | 10:15 | 8,175.80 | short | bear | SL | -7.3 | timeout |
| 2015-10-13 | 12:29 | 8,138.02 | short | bear | SL | -7.2 | timeout |
| 2015-10-16 | 10:11 | 8,173.22 | short | bear | SL | -7.3 | timeout |
| 2015-10-20 | 11:45 | 8,284.78 | short | bear | SL | -7.3 | timeout |

**impulsive approach** (125)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-13 | 11:38 | 8,684.35 | long | bull | SL | -7.5 | impulsive approach |
| 2015-05-29 | 14:38 | 8,419.98 | short | bear | TSL_SL | -3.2 | impulsive approach |
| 2015-09-28 | 13:15 | 7,869.80 | short | bear | TSL_SL | -3.2 | impulsive approach |
| 2016-03-21 | 13:47 | 7,652.67 | short | bear | SL | -7.0 | impulsive approach |
| 2016-04-26 | 12:41 | 7,917.55 | short | bear | SL | -7.1 | impulsive approach |
| 2016-04-27 | 09:24 | 7,972.95 | short | bear | TARGET | 12.8 | impulsive approach |
| 2016-05-23 | 13:46 | 7,785.65 | short | bear | SL | -7.1 | impulsive approach |
| 2016-05-24 | 12:54 | 7,740.28 | short | bear | SL | -7.1 | impulsive approach |
| 2016-07-22 | 14:16 | 8,541.75 | short | bear | EOD | -1.3 | impulsive approach |
| 2016-07-25 | 11:19 | 8,570.33 | short | bear | SL | -7.5 | impulsive approach |
| 2017-02-01 | 13:06 | 8,643.25 | short | bear | SL | -7.5 | impulsive approach |
| 2017-04-18 | 14:42 | 9,125.92 | long | bull | SL | -7.7 | impulsive approach |
| 2017-05-02 | 10:49 | 9,293.70 | long | bull | SL | -7.8 | impulsive approach |
| 2017-05-05 | 09:23 | 9,321.22 | long | bull | TSL_SL | -3.2 | impulsive approach |
| 2017-05-05 | 12:01 | 9,287.02 | long | bull | SL | -7.8 | impulsive approach |

**timeout — counter side absorbing inside the area** (90)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-04-29 | 09:35 | 8,274.33 | short | bear | SL | -7.3 | timeout |
| 2015-05-12 | 13:31 | 8,154.80 | short | bear | SL | -7.3 | timeout |
| 2015-05-25 | 10:21 | 8,434.88 | short | bear | TARGET | 13.7 | timeout |
| 2015-05-27 | 10:31 | 8,328.83 | short | bear | SL | -7.3 | timeout |
| 2015-11-19 | 09:20 | 7,778.02 | short | bear | SL | -7.1 | timeout |
| 2015-11-19 | 09:51 | 7,778.02 | short | bear | TSL_SL | -3.2 | timeout |
| 2015-12-23 | 09:28 | 7,849.38 | short | bear | TSL_SL | -3.2 | timeout |
| 2015-12-23 | 10:03 | 7,849.38 | short | bear | SL | -7.1 | timeout |
| 2015-12-31 | 09:55 | 7,900.30 | short | bear | SL | -7.1 | timeout |
| 2016-01-27 | 09:16 | 7,457.62 | short | bear | TARGET | 11.7 | timeout |
| 2016-02-03 | 13:21 | 7,416.48 | short | bear | TSL_SL | -3.2 | timeout |
| 2016-02-15 | 12:32 | 7,160.30 | short | bear | SL | -6.8 | timeout |
| 2016-06-09 | 10:37 | 8,232.72 | short | bear | SL | -7.3 | timeout |
| 2016-11-16 | 09:20 | 8,183.50 | short | bear | SL | -7.3 | timeout |
| 2016-11-22 | 10:32 | 7,977.85 | short | bear | SL | -7.2 | timeout |

**confirmed only in hindsight (not on the live cycle)** (10)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2016-03-09 | 10:11 | 7,457.38 | short | bear | SL | -6.9 |  |
| 2017-02-06 | 14:14 | 8,802.17 | short | bear | SL | -7.6 |  |
| 2017-08-04 | 10:42 | 9,994.83 | long | bull | SL | -8.2 |  |
| 2020-01-03 | 10:55 | 12,235.22 | long | bull | SL | -9.3 |  |
| 2020-02-04 | 14:11 | 11,962.75 | long | bull | TSL_SL | -3.2 |  |
| 2020-06-02 | 11:06 | 9,904.80 | short | bear | TARGET | 16.6 |  |
| 2020-09-04 | 11:13 | 11,410.90 | short | bear | SL | -8.9 |  |
| 2020-10-01 | 14:16 | 11,408.15 | short | bear | SL | -8.9 |  |
| 2021-02-19 | 13:01 | 15,066.30 | long | bull | SL | -10.7 |  |
| 2021-03-24 | 13:03 | 14,616.40 | long | bull | TSL_SL | -3.2 |  |

**gate confirmed, but after the no-new-entry cutoff** (5)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2018-09-14 | 14:28 | 11,481.50 | long | bull | EOD | 4.1 | confirmed after the no-new-entry cutoff |
| 2019-05-22 | 14:37 | 11,726.42 | long | bull | SL | -9.0 | confirmed after the no-new-entry cutoff |
| 2019-09-25 | 14:37 | 11,422.55 | long | bull | TSL_SL | -3.2 | confirmed after the no-new-entry cutoff |
| 2021-01-28 | 14:31 | 13,764.70 | long | bull | TARGET | 24.3 | confirmed after the no-new-entry cutoff |
| 2022-05-19 | 14:44 | 15,789.62 | long | bull | EOD | 12.5 | confirmed after the no-new-entry cutoff |

## 15M SRv2 — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 1340 | 11% | -2.84 | -3,809.2 | 3,894.3 | 0.56 |  |
| IS | all | confirmation | 46 | 9% | -3.18 | -146.3 | 186.5 | 0.51 |  |
| IS | all | confirmation + structural exit (not live) | 43 | 33% | 9.43 | 405.6 | 270.6 | 1.58 |  |
| IS | bull | touch | 826 | 12% | -2.53 | -2,091.1 | 2,157.6 | 0.63 |  |
| IS | bull | confirmation | 21 | 10% | -2.75 | -57.8 | 72.6 | 0.62 | n < 30 — no conclusion |
| IS | bull | confirmation + structural exit (not live) | 20 | 30% | 13.72 | 274.4 | 141.5 | 1.69 | n < 30 — no conclusion |
| IS | bear | touch | 491 | 10% | -3.42 | -1,679.2 | 1,679.2 | 0.42 |  |
| IS | bear | confirmation | 25 | 8% | -3.54 | -88.5 | 118.6 | 0.41 | n < 30 — no conclusion |
| IS | bear | confirmation + structural exit (not live) | 23 | 35% | 5.70 | 131.2 | 151.1 | 1.44 | n < 30 — no conclusion |
| IS | no trend | touch | 23 | 13% | -1.69 | -38.9 | 82.3 | 0.71 | n < 30 — no conclusion |
| IS | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | no trend | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 407 | 10% | -4.12 | -1,675.7 | 1,704.6 | 0.56 |  |
| VAL | all | confirmation | 7 | 0% | -9.92 | -69.4 | 69.4 | 0.00 | n < 30 — no conclusion |
| VAL | all | confirmation + structural exit (not live) | 7 | 57% | 10.01 | 70.1 | 110.6 | 1.61 | n < 30 — no conclusion |
| VAL | bull | touch | 407 | 10% | -4.12 | -1,675.7 | 1,704.6 | 0.56 |  |
| VAL | bull | confirmation | 7 | 0% | -9.92 | -69.4 | 69.4 | 0.00 | n < 30 — no conclusion |
| VAL | bull | confirmation + structural exit (not live) | 7 | 57% | 10.01 | 70.1 | 110.6 | 1.61 | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 1747 · kept by the gate: 27 (taken by the confirmation arm: 27) · rejected: 1720.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | against the Daily trend | 519 | 64 | -1,316.3 | -2.54 | 1,316.3 |  |
| IS | area broken (real break) | 228 | 5 | -1,541.9 | -6.76 | 1,541.9 |  |
| IS | Daily trend unclear / entries blocked | 192 | 15 | -748.9 | -3.90 | 748.9 |  |
| IS | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 131 | 9 | -521.4 | -3.98 | 521.4 |  |
| IS | R:R below minimum | 117 | 37 | 576.9 | 4.93 | -576.9 |  |
| IS | timeout — no commitment within max_armed_bars | 59 | 4 | -207.3 | -3.51 | 207.3 |  |
| IS | impulsive approach | 29 | 4 | 18.6 | 0.64 | -18.6 | n < 30 |
| IS | kept — the gate confirmed the same visit and side | 25 | 2 | -105.7 | -4.23 | — | n < 30 |
| IS | timeout — counter side absorbing inside the area | 16 | 2 | 22.0 | 1.38 | -22.0 | n < 30 |
| IS | no commitment (still armed when the window / session ended) | 12 | 3 | 1.1 | 0.09 | -1.1 | n < 30 |
| IS | no opposite area for a target | 6 | 2 | 33.6 | 5.59 | -33.6 | n < 30 |
| IS | confirmed only in hindsight (not on the live cycle) | 3 | 0 | -17.7 | -5.92 | 17.7 | n < 30 |
| IS | gate confirmed, but after the no-new-entry cutoff | 3 | 1 | -2.2 | -0.72 | 2.2 | n < 30 |
| VAL | against the Daily trend | 154 | 16 | -773.4 | -5.02 | 773.4 |  |
| VAL | Daily trend unclear / entries blocked | 73 | 3 | -533.4 | -7.31 | 533.4 |  |
| VAL | area broken (real break) | 66 | 1 | -617.9 | -9.36 | 617.9 |  |
| VAL | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 40 | 4 | -161.6 | -4.04 | 161.6 |  |
| VAL | R:R below minimum | 39 | 9 | 407.2 | 10.44 | -407.2 |  |
| VAL | timeout — no commitment within max_armed_bars | 15 | 3 | -28.7 | -1.91 | 28.7 | n < 30 |
| VAL | impulsive approach | 5 | 0 | -42.9 | -8.58 | 42.9 | n < 30 |
| VAL | timeout — counter side absorbing inside the area | 5 | 1 | 18.3 | 3.66 | -18.3 | n < 30 |
| VAL | no commitment (still armed when the window / session ended) | 5 | 3 | 21.0 | 4.20 | -21.0 | n < 30 |
| VAL | no opposite area for a target | 3 | 1 | 42.0 | 14.01 | -42.0 | n < 30 |
| VAL | kept — the gate confirmed the same visit and side | 2 | 0 | -6.4 | -3.18 | — | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay/trades.csv`)

**Daily trend unclear / entries blocked** (265)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-01-27 | 14:32 | 8,870.42 | short | no trend | SL | -7.6 | Daily UNKNOWN |
| 2015-02-03 | 12:04 | 8,749.80 | long | no trend | SL | -7.6 | Daily NEUTRAL |
| 2015-02-03 | 12:43 | 8,749.80 | long | no trend | SL | -7.6 | Daily NEUTRAL |
| 2015-02-05 | 09:26 | 8,734.10 | long | no trend | SL | -7.5 | Daily NEUTRAL |
| 2015-02-11 | 13:22 | 8,647.00 | short | no trend | TARGET | 31.4 | Daily NEUTRAL |
| 2015-02-12 | 09:34 | 8,647.00 | short | no trend | SL | -7.5 | Daily NEUTRAL |
| 2015-02-12 | 10:00 | 8,647.00 | short | no trend | TARGET | 31.4 | Daily NEUTRAL |
| 2015-02-13 | 09:55 | 8,765.88 | short | no trend | TSL_SL | -3.2 | Daily NEUTRAL |
| 2015-02-13 | 12:13 | 8,765.88 | short | no trend | SL | -7.6 | Daily NEUTRAL |
| 2015-02-16 | 09:42 | 8,854.83 | short | no trend | TSL_SL | -3.2 | Daily NEUTRAL |
| 2015-02-16 | 10:54 | 8,854.83 | short | no trend | TARGET | 32.2 | Daily NEUTRAL |
| 2015-02-18 | 10:30 | 8,854.83 | short | no trend | SL | -7.6 | Daily NEUTRAL |
| 2015-02-18 | 11:15 | 8,854.83 | short | no trend | SL | -7.6 | Daily NEUTRAL |
| 2015-02-20 | 09:17 | 8,882.20 | short | no trend | SL | -7.6 | Daily NEUTRAL |
| 2015-02-23 | 14:09 | 8,814.30 | long | no trend | SL | -7.6 | Daily NEUTRAL |

**area broken (real break)** (294)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-04 | 14:43 | 8,956.25 | long | bull | SL | -7.7 | broken |
| 2015-03-09 | 09:31 | 8,825.22 | long | bull | TSL_SL | -4.0 | broken |
| 2015-03-09 | 10:02 | 8,825.22 | long | bull | SL | -7.6 | broken |
| 2015-03-10 | 13:28 | 8,738.50 | long | bull | SL | -7.6 | broken |
| 2015-05-18 | 13:48 | 8,320.12 | short | bear | SL | -7.3 | broken |
| 2015-05-29 | 09:30 | 8,349.75 | short | bear | SL | -7.4 | broken |
| 2015-05-29 | 09:52 | 8,349.75 | short | bear | SL | -7.4 | broken |
| 2015-06-17 | 13:44 | 8,095.08 | short | bear | SL | -7.2 | broken |
| 2015-06-25 | 14:39 | 8,409.75 | short | bear | SL | -7.4 | broken |
| 2015-07-01 | 09:56 | 8,410.70 | short | bear | SL | -7.4 | broken |
| 2015-08-27 | 13:11 | 7,925.95 | short | bear | SL | -7.1 | broken |
| 2015-09-29 | 13:44 | 7,879.60 | short | bear | SL | -7.1 | broken |
| 2015-10-12 | 09:46 | 8,206.12 | short | bear | SL | -7.3 | broken |
| 2015-10-16 | 14:15 | 8,188.60 | short | bear | SL | -7.3 | broken |
| 2015-11-27 | 09:58 | 7,916.78 | short | bear | SL | -7.1 | broken |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (171)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-05 | 13:55 | 8,882.20 | long | bull | TARGET | 32.4 |  |
| 2015-05-05 | 09:16 | 8,318.98 | short | bear | SL | -7.3 |  |
| 2015-05-05 | 09:57 | 8,318.98 | short | bear | SL | -7.3 |  |
| 2015-05-14 | 09:17 | 8,172.25 | short | bear | SL | -7.3 |  |
| 2015-06-01 | 09:17 | 8,428.62 | short | bear | SL | -7.4 |  |
| 2015-06-01 | 09:45 | 8,428.62 | short | bear | SL | -7.4 |  |
| 2015-06-11 | 10:11 | 8,126.00 | short | bear | SL | -7.2 |  |
| 2015-06-17 | 13:06 | 8,074.50 | short | bear | SL | -7.2 |  |
| 2015-09-16 | 10:22 | 7,862.62 | short | bear | SL | -7.1 |  |
| 2015-10-09 | 11:55 | 8,188.60 | short | bear | SL | -7.3 |  |
| 2015-11-27 | 11:55 | 7,916.78 | short | bear | TSL_SL | -3.2 |  |
| 2015-11-30 | 09:16 | 7,938.20 | short | bear | SL | -7.1 |  |
| 2016-01-21 | 09:43 | 7,359.95 | short | bear | TSL_SL | -3.2 |  |
| 2016-03-02 | 13:47 | 7,347.68 | short | bear | SL | -6.9 |  |
| 2016-03-10 | 09:37 | 7,514.78 | short | bear | SL | -6.9 |  |

**timeout — counter side absorbing inside the area** (21)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-10 | 09:16 | 8,739.42 | long | bull | TSL_SL | -4.4 | timeout |
| 2015-03-10 | 09:57 | 8,739.42 | long | bull | TSL_SL | -3.2 | timeout |
| 2016-02-26 | 13:45 | 7,041.83 | short | bear | SL | -6.7 | timeout |
| 2016-02-26 | 14:05 | 7,041.83 | short | bear | TSL_SL | -3.2 | timeout |
| 2017-02-10 | 09:27 | 8,802.00 | short | bear | SL | -7.6 | timeout |
| 2017-02-10 | 10:11 | 8,802.00 | short | bear | TSL_SL | -3.2 | timeout |
| 2017-09-08 | 13:15 | 9,915.65 | long | bull | TSL_SL | -3.2 | timeout |
| 2018-03-05 | 10:44 | 10,344.90 | long | bull | TSL_SL | -3.2 | timeout |
| 2018-03-05 | 12:00 | 10,344.90 | long | bull | SL | -8.4 | timeout |
| 2019-11-22 | 11:35 | 11,897.45 | long | bull | SL | -9.1 | timeout |
| 2019-11-22 | 12:37 | 11,897.45 | long | bull | SL | -9.1 | timeout |
| 2020-01-15 | 09:48 | 12,297.30 | long | bull | TSL_SL | -3.2 | timeout |
| 2020-01-15 | 10:28 | 12,297.30 | long | bull | SL | -9.3 | timeout |
| 2021-01-29 | 13:49 | 13,754.70 | long | bull | SL | -10.1 | timeout |
| 2021-01-29 | 14:11 | 13,754.70 | long | bull | TARGET | 51.9 | timeout |

**timeout — no commitment within max_armed_bars** (74)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-13 | 11:59 | 8,678.98 | long | bull | SL | -7.5 | timeout |
| 2015-03-13 | 13:17 | 8,678.98 | long | bull | TSL_SL | -3.2 | timeout |
| 2015-05-08 | 09:38 | 8,167.52 | short | bear | SL | -7.3 | timeout |
| 2015-05-08 | 10:19 | 8,167.52 | short | bear | SL | -7.3 | timeout |
| 2015-05-15 | 09:32 | 8,254.25 | short | bear | TARGET | 29.8 | timeout |
| 2015-05-15 | 09:54 | 8,254.25 | short | bear | SL | -7.3 | timeout |
| 2015-12-28 | 09:42 | 7,898.15 | short | bear | SL | -7.1 | timeout |
| 2015-12-28 | 10:18 | 7,898.15 | short | bear | SL | -7.1 | timeout |
| 2016-02-05 | 10:31 | 7,472.00 | short | bear | SL | -6.9 | timeout |
| 2016-02-05 | 10:47 | 7,472.00 | short | bear | SL | -6.9 | timeout |
| 2016-08-24 | 09:16 | 8,656.98 | short | bear | TSL_SL | -3.2 | timeout |
| 2016-10-19 | 09:17 | 8,677.30 | short | bear | SL | -7.5 | timeout |
| 2016-10-19 | 09:38 | 8,677.30 | short | bear | SL | -7.5 | timeout |
| 2017-01-03 | 11:16 | 8,206.12 | short | bear | SL | -7.3 | timeout |
| 2017-01-03 | 11:45 | 8,206.12 | short | bear | TSL_SL | -3.2 | timeout |

**R:R below minimum** (156)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-04-29 | 13:00 | 8,291.80 | short | bear | SL | -7.3 | R:R < min (0.36 < 3) |
| 2015-04-29 | 13:57 | 8,291.80 | short | bear | TSL_SL | -3.2 | R:R < min (0.36 < 3) |
| 2015-05-15 | 12:28 | 8,261.80 | short | bear | SL | -7.3 | R:R < min (2.98 < 3) |
| 2015-06-30 | 09:28 | 8,335.20 | short | bear | TSL_SL | -3.2 | R:R < min (2.71 < 3) |
| 2015-06-30 | 09:53 | 8,335.20 | short | bear | TSL_SL | -3.2 | R:R < min (2.71 < 3) |
| 2015-09-09 | 09:19 | 7,811.42 | short | bear | TSL_SL | -3.2 | R:R < min (1.25 < 3) |
| 2015-09-09 | 09:47 | 7,811.42 | short | bear | TARGET | 28.0 | R:R < min (1.25 < 3) |
| 2015-12-02 | 09:45 | 7,967.92 | short | bear | TARGET | 28.7 | R:R < min (0.03 < 3) |
| 2015-12-17 | 09:34 | 7,780.50 | short | bear | TARGET | 27.9 | R:R < min (1.41 < 3) |
| 2015-12-22 | 13:17 | 7,838.92 | short | bear | SL | -7.1 | R:R < min (0.56 < 3) |
| 2016-01-25 | 09:33 | 7,482.70 | short | bear | SL | -6.9 | R:R < min (1.73 < 3) |
| 2016-04-12 | 12:57 | 7,716.08 | short | bear | TARGET | 27.7 | R:R < min (2.18 < 3) |
| 2016-04-26 | 13:28 | 7,962.20 | short | bear | SL | -7.2 | R:R < min (2.99 < 3) |
| 2016-04-26 | 13:44 | 7,962.20 | short | bear | TSL_SL | -3.2 | R:R < min (2.99 < 3) |
| 2016-05-11 | 12:08 | 7,881.52 | short | bear | TARGET | 28.3 | R:R < min (2.53 < 3) |

**against the Daily trend** (673)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-05-06 | 09:48 | 8,167.52 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-05-06 | 10:15 | 8,167.52 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-05-12 | 10:24 | 8,167.52 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-05-12 | 10:41 | 8,167.52 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-05-13 | 09:17 | 8,167.52 | long | bear | TARGET | 29.5 | Daily DOWN |
| 2015-05-25 | 13:23 | 8,377.95 | long | bear | SL | -7.4 | Daily DOWN |
| 2015-05-25 | 13:45 | 8,377.95 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-05-26 | 09:33 | 8,338.95 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-05-26 | 13:52 | 8,329.92 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-05-27 | 09:55 | 8,329.92 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-06-02 | 09:30 | 8,374.28 | long | bear | SL | -7.4 | Daily DOWN |
| 2015-06-02 | 10:44 | 8,374.28 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-06-02 | 11:34 | 8,321.15 | long | bear | SL | -7.3 | Daily DOWN |
| 2015-06-02 | 11:54 | 8,321.15 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-06-08 | 09:30 | 8,075.88 | long | bear | SL | -7.2 | Daily DOWN |

**gate confirmed, but after the no-new-entry cutoff** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-05-15 | 14:00 | 8,261.80 | short | bear | SL | -7.3 | confirmed after the no-new-entry cutoff |
| 2016-10-24 | 13:37 | 8,734.20 | short | bear | EOD | 13.6 | confirmed after the no-new-entry cutoff |
| 2018-06-05 | 14:01 | 10,569.22 | long | bull | SL | -8.5 | confirmed after the no-new-entry cutoff |

**no opposite area for a target** (9)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-06-15 | 09:45 | 8,031.40 | short | bear | TARGET | 28.9 | no target area |
| 2015-11-03 | 09:31 | 8,096.08 | short | bear | TARGET | 29.2 | no target area |
| 2015-11-04 | 09:34 | 8,098.20 | short | bear | SL | -7.2 | no target area |
| 2019-07-05 | 11:50 | 11,894.28 | long | bull | TSL_SL | -3.2 | no target area |
| 2021-04-09 | 13:50 | 14,795.10 | long | bull | TSL_SL | -3.2 | no target area |
| 2021-06-09 | 13:16 | 15,646.05 | long | bull | SL | -11.0 | no target area |
| 2023-04-13 | 12:32 | 17,736.35 | long | bull | TARGET | 67.8 | no target area |
| 2023-07-07 | 12:08 | 19,374.80 | long | bull | SL | -12.9 | no target area |
| 2023-07-07 | 13:29 | 19,374.80 | long | bull | SL | -12.9 | no target area |

**impulsive approach** (34)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-06-18 | 10:25 | 8,151.60 | short | bear | SL | -7.3 | impulsive approach |
| 2015-06-18 | 11:33 | 8,151.60 | short | bear | SL | -7.3 | impulsive approach |
| 2015-12-17 | 13:57 | 7,787.85 | short | bear | SL | -7.1 | impulsive approach |
| 2016-02-29 | 13:49 | 7,041.83 | short | bear | TSL_SL | -3.2 | impulsive approach |
| 2017-05-19 | 11:56 | 9,439.25 | long | bull | SL | -7.9 | impulsive approach |
| 2017-09-21 | 10:00 | 10,117.65 | long | bull | SL | -8.2 | impulsive approach |
| 2017-10-11 | 13:32 | 10,018.12 | long | bull | TSL_SL | -3.2 | impulsive approach |
| 2017-10-11 | 13:55 | 10,018.12 | long | bull | SL | -8.2 | impulsive approach |
| 2018-02-01 | 12:48 | 10,907.42 | long | bull | TARGET | 40.5 | impulsive approach |
| 2018-07-19 | 09:49 | 10,945.42 | long | bull | TARGET | 40.6 | impulsive approach |
| 2018-09-04 | 09:41 | 11,539.62 | long | bull | TARGET | 43.0 | impulsive approach |
| 2018-10-31 | 10:00 | 10,134.55 | long | bull | SL | -8.3 | impulsive approach |
| 2018-10-31 | 10:27 | 10,134.55 | long | bull | SL | -8.2 | impulsive approach |
| 2019-01-25 | 14:22 | 10,804.47 | long | bull | SL | -8.6 | impulsive approach |
| 2019-01-25 | 14:39 | 10,804.47 | long | bull | TSL_SL | -3.2 | impulsive approach |

**no commitment (still armed when the window / session ended)** (17)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2016-03-30 | 14:34 | 7,728.05 | short | bear | SL | -7.0 | no commitment |
| 2016-04-12 | 14:37 | 7,716.08 | short | bear | EOD | 1.0 | no commitment |
| 2016-10-28 | 14:37 | 8,645.52 | short | bear | SL | -7.5 | no commitment |
| 2017-09-22 | 14:43 | 9,963.78 | long | bull | EOD | 13.0 | no commitment |
| 2017-10-11 | 14:24 | 9,958.30 | long | bull | SL | -8.2 | no commitment |
| 2019-06-06 | 14:18 | 11,848.68 | long | bull | SL | -9.1 | no commitment |
| 2019-06-06 | 14:42 | 11,848.68 | long | bull | EOD | -1.0 | no commitment |
| 2020-09-02 | 14:36 | 11,534.10 | short | bear | TSL_SL | -3.2 | no commitment |
| 2020-10-09 | 14:33 | 11,920.38 | short | bear | TSL_SL | -3.2 | no commitment |
| 2020-12-21 | 14:36 | 13,184.10 | long | bull | TARGET | 50.1 | no commitment |
| 2021-02-17 | 13:46 | 15,203.55 | long | bull | SL | -10.8 | no commitment |
| 2021-10-22 | 14:30 | 18,044.97 | long | bull | SL | -12.9 | no commitment |
| 2022-02-07 | 14:01 | 17,139.15 | long | bull | TSL_SL | -3.2 | no commitment |
| 2023-02-20 | 14:23 | 17,827.53 | long | bull | EOD | 22.7 | no commitment |
| 2023-06-09 | 14:24 | 18,559.80 | long | bull | EOD | 9.2 | no commitment |

**confirmed only in hindsight (not on the live cycle)** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2016-06-01 | 09:57 | 8,205.12 | short | bear | SL | -7.3 |  |
| 2016-06-01 | 10:21 | 8,205.12 | short | bear | SL | -7.3 |  |
| 2016-11-23 | 11:31 | 8,025.70 | short | bear | TSL_SL | -3.2 |  |

## Classic — NIFTY

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| IS | all | touch | 2661 | 40% | -5.60 | -14,897.0 | 15,644.2 | 0.74 |  |
| IS | all | confirmation | 143 | 45% | -0.05 | -6.9 | 458.6 | 1.00 |  |
| IS | all | confirmation + structural exit (not live) | 148 | 34% | 1.52 | 224.5 | 306.9 | 1.12 |  |
| IS | bull | touch | 1546 | 41% | -6.19 | -9,575.3 | 10,281.2 | 0.74 |  |
| IS | bull | confirmation | 78 | 49% | -0.01 | -0.5 | 331.9 | 1.00 |  |
| IS | bull | confirmation + structural exit (not live) | 81 | 38% | 2.85 | 230.8 | 223.1 | 1.23 |  |
| IS | bear | touch | 1065 | 39% | -4.73 | -5,042.0 | 5,307.5 | 0.75 |  |
| IS | bear | confirmation | 65 | 42% | -0.10 | -6.4 | 393.3 | 0.99 |  |
| IS | bear | confirmation + structural exit (not live) | 67 | 28% | -0.09 | -6.3 | 397.5 | 0.99 |  |
| IS | no trend | touch | 50 | 38% | -5.59 | -279.7 | 446.7 | 0.69 |  |
| IS | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| IS | no trend | confirmation + structural exit (not live) | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| VAL | all | touch | 769 | 43% | -1.67 | -1,281.5 | 2,601.6 | 0.95 |  |
| VAL | all | confirmation | 36 | 47% | -8.09 | -291.1 | 390.4 | 0.70 |  |
| VAL | all | confirmation + structural exit (not live) | 36 | 36% | -6.26 | -225.2 | 324.2 | 0.71 |  |
| VAL | bull | touch | 769 | 43% | -1.67 | -1,281.5 | 2,601.6 | 0.95 |  |
| VAL | bull | confirmation | 36 | 47% | -8.09 | -291.1 | 390.4 | 0.70 |  |
| VAL | bull | confirmation + structural exit (not live) | 36 | 36% | -6.26 | -225.2 | 324.2 | 0.71 |  |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 3430 · kept by the gate: 36 (taken by the confirmation arm: 35) · rejected: 3394.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| IS | against the Daily trend | 1091 | 443 | -3,567.5 | -3.27 | 3,567.5 |  |
| IS | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 388 | 159 | -2,398.8 | -6.18 | 2,398.8 |  |
| IS | area broken (real break) | 385 | 87 | -8,540.3 | -22.18 | 8,540.3 |  |
| IS | Daily trend unclear / entries blocked | 381 | 154 | -2,192.8 | -5.76 | 2,192.8 |  |
| IS | R:R below minimum | 191 | 105 | 852.3 | 4.46 | -852.3 |  |
| IS | timeout — no commitment within max_armed_bars | 101 | 51 | 357.3 | 3.54 | -357.3 |  |
| IS | impulsive approach | 36 | 17 | 90.4 | 2.51 | -90.4 |  |
| IS | no opposite area for a target | 36 | 22 | 617.1 | 17.14 | -617.1 |  |
| IS | kept — the gate confirmed the same visit and side | 32 | 17 | 125.5 | 3.92 | — |  |
| IS | timeout — counter side absorbing inside the area | 15 | 6 | -172.9 | -11.53 | 172.9 | n < 30 |
| IS | confirmed only in hindsight (not on the live cycle) | 3 | 1 | -58.0 | -19.32 | 58.0 | n < 30 |
| IS | gate confirmed, but after the no-new-entry cutoff | 2 | 0 | -9.3 | -4.66 | 9.3 | n < 30 |
| VAL | against the Daily trend | 298 | 137 | 1,383.1 | 4.64 | -1,383.1 |  |
| VAL | Daily trend unclear / entries blocked | 190 | 76 | -470.8 | -2.48 | 470.8 |  |
| VAL | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 97 | 40 | -721.8 | -7.44 | 721.8 |  |
| VAL | area broken (real break) | 87 | 22 | -3,221.2 | -37.02 | 3,221.2 |  |
| VAL | R:R below minimum | 39 | 28 | 1,473.3 | 37.78 | -1,473.3 |  |
| VAL | timeout — no commitment within max_armed_bars | 19 | 8 | 297.0 | 15.63 | -297.0 | n < 30 |
| VAL | impulsive approach | 17 | 7 | -138.9 | -8.17 | 138.9 | n < 30 |
| VAL | no opposite area for a target | 12 | 5 | -128.0 | -10.66 | 128.0 | n < 30 |
| VAL | timeout — counter side absorbing inside the area | 5 | 2 | 28.9 | 5.79 | -28.9 | n < 30 |
| VAL | kept — the gate confirmed the same visit and side | 4 | 3 | 209.1 | 52.29 | — | n < 30 |
| VAL | gate confirmed, but after the no-new-entry cutoff | 1 | 1 | 7.6 | 7.62 | -7.6 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay/trades.csv`)

**Daily trend unclear / entries blocked** (571)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-01-12 | 12:15 | 8,274.35 | long | no trend | EOD | 34.1 | Daily UNKNOWN |
| 2015-01-13 | 13:16 | 8,349.65 | short | no trend | TARGET | 63.6 | Daily UNKNOWN |
| 2015-01-13 | 14:44 | 8,274.35 | long | no trend | EOD | 2.1 | Daily UNKNOWN |
| 2015-01-14 | 09:16 | 8,294.38 | long | no trend | SL | -36.4 | Daily UNKNOWN |
| 2015-01-14 | 12:26 | 8,272.12 | long | no trend | EOD | -7.1 | Daily UNKNOWN |
| 2015-01-21 | 13:39 | 8,734.98 | short | no trend | EOD | 3.9 | Daily UNKNOWN |
| 2015-01-22 | 12:20 | 8,756.98 | long | no trend | EOD | -21.0 | Daily UNKNOWN |
| 2015-01-27 | 09:20 | 8,851.58 | short | no trend | SL | -38.6 | Daily UNKNOWN |
| 2015-01-27 | 14:36 | 8,870.42 | short | no trend | EOD | -20.0 | Daily UNKNOWN |
| 2015-01-28 | 14:23 | 8,877.75 | long | no trend | EOD | 12.5 | Daily NEUTRAL |
| 2015-01-29 | 09:17 | 8,877.75 | long | no trend | EOD | 8.8 | Daily NEUTRAL |
| 2015-01-30 | 09:51 | 8,914.95 | long | no trend | SL | -38.9 | Daily NEUTRAL |
| 2015-01-30 | 11:10 | 8,884.55 | long | no trend | SL | -38.7 | Daily NEUTRAL |
| 2015-01-30 | 11:42 | 8,828.98 | long | no trend | SL | -38.5 | Daily NEUTRAL |
| 2015-02-02 | 11:44 | 8,774.03 | long | no trend | TSL_SL | -3.2 | Daily NEUTRAL |

**area broken (real break)** (472)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-02 | 10:55 | 8,930.17 | long | bull | SL | -38.9 | broken |
| 2015-03-04 | 14:42 | 8,954.35 | long | bull | SL | -39.0 | broken |
| 2015-03-09 | 09:21 | 8,825.22 | long | bull | SL | -38.5 | broken |
| 2015-05-04 | 09:31 | 8,268.80 | short | bear | SL | -36.2 | broken |
| 2015-05-08 | 09:21 | 8,153.88 | short | bear | SL | -35.8 | broken |
| 2015-05-11 | 11:07 | 8,287.40 | short | bear | SL | -36.3 | broken |
| 2015-05-29 | 09:16 | 8,330.35 | short | bear | SL | -36.5 | broken |
| 2015-05-29 | 09:26 | 8,349.75 | short | bear | SL | -36.6 | broken |
| 2015-05-29 | 10:19 | 8,382.28 | short | bear | SL | -36.7 | broken |
| 2015-06-04 | 14:28 | 8,099.90 | short | bear | SL | -35.6 | broken |
| 2015-06-05 | 12:31 | 8,151.68 | short | bear | SL | -35.7 | broken |
| 2015-06-15 | 09:35 | 7,998.58 | short | bear | SL | -35.1 | broken |
| 2015-07-01 | 09:51 | 8,410.70 | short | bear | SL | -36.8 | broken |
| 2015-08-27 | 13:11 | 7,925.95 | short | bear | SL | -34.9 | broken |
| 2015-09-03 | 13:44 | 7,826.48 | short | bear | EOD | 1.6 | broken |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (485)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-02 | 12:26 | 8,901.78 | long | bull | EOD | 12.8 |  |
| 2015-03-04 | 14:15 | 9,027.62 | long | bull | SL | -39.3 |  |
| 2015-03-05 | 13:57 | 8,890.08 | long | bull | EOD | 12.1 |  |
| 2015-05-04 | 12:30 | 8,300.12 | short | bear | EOD | -13.8 |  |
| 2015-05-05 | 09:16 | 8,318.98 | short | bear | SL | -36.5 |  |
| 2015-05-06 | 09:16 | 8,300.12 | short | bear | TARGET | 63.2 |  |
| 2015-05-12 | 09:18 | 8,287.40 | short | bear | TARGET | 62.9 |  |
| 2015-05-13 | 10:54 | 8,214.90 | short | bear | TARGET | 62.4 |  |
| 2015-05-14 | 09:17 | 8,168.78 | short | bear | SL | -35.9 |  |
| 2015-05-15 | 09:33 | 8,254.25 | short | bear | SL | -36.1 |  |
| 2015-05-15 | 10:16 | 8,254.25 | short | bear | EOD | -14.7 |  |
| 2015-06-01 | 09:17 | 8,428.62 | short | bear | SL | -36.9 |  |
| 2015-06-15 | 09:16 | 7,949.72 | short | bear | SL | -35.0 |  |
| 2015-06-18 | 10:15 | 8,151.60 | short | bear | SL | -35.7 |  |
| 2015-06-25 | 11:00 | 8,371.20 | short | bear | SL | -36.7 |  |

**no opposite area for a target** (48)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-03 | 09:30 | 8,930.17 | long | bull | EOD | 54.5 | no target area |
| 2015-04-30 | 11:50 | 8,190.28 | short | bear | EOD | -21.7 | no target area |
| 2015-05-06 | 13:41 | 8,144.30 | short | bear | EOD | 34.9 | no target area |
| 2015-06-09 | 09:45 | 8,056.28 | short | bear | EOD | 31.3 | no target area |
| 2016-08-29 | 09:16 | 8,579.52 | short | bear | SL | -37.4 | no target area |
| 2016-11-11 | 13:15 | 8,384.52 | short | bear | TARGET | 63.9 | no target area |
| 2016-11-17 | 14:20 | 8,108.90 | short | bear | EOD | 17.4 | no target area |
| 2016-11-21 | 14:30 | 7,957.32 | short | bear | EOD | 28.7 | no target area |
| 2017-06-05 | 09:16 | 9,648.17 | long | bull | EOD | 14.9 | no target area |
| 2017-07-10 | 09:35 | 9,666.45 | long | bull | TARGET | 74.2 | no target area |
| 2017-09-01 | 14:15 | 9,964.12 | long | bull | EOD | 5.5 | no target area |
| 2017-11-02 | 09:25 | 10,431.08 | long | bull | EOD | -8.9 | no target area |
| 2018-01-22 | 10:25 | 10,886.30 | long | bull | EOD | 65.0 | no target area |
| 2018-06-13 | 10:00 | 10,845.08 | long | bull | EOD | 9.8 | no target area |
| 2018-08-24 | 09:20 | 11,573.30 | long | bull | EOD | -22.9 | no target area |

**R:R below minimum** (230)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-05 | 09:57 | 8,902.60 | long | bull | SL | -38.8 | R:R < min (1.12 < 3) |
| 2015-04-29 | 10:05 | 8,274.33 | short | bear | SL | -36.2 | R:R < min (0.39 < 3) |
| 2015-05-13 | 14:00 | 8,239.72 | short | bear | EOD | 9.3 | R:R < min (1.82 < 3) |
| 2015-05-20 | 11:15 | 8,433.88 | short | bear | EOD | 4.9 | R:R < min (2.60 < 3) |
| 2015-05-21 | 09:20 | 8,433.88 | short | bear | EOD | 16.0 | R:R < min (0.50 < 3) |
| 2015-05-22 | 09:17 | 8,434.88 | short | bear | SL | -36.9 | R:R < min (1.97 < 3) |
| 2015-06-25 | 13:59 | 8,404.52 | short | bear | EOD | -7.1 | R:R < min (2.35 < 3) |
| 2015-09-09 | 09:19 | 7,811.42 | short | bear | SL | -34.4 | R:R < min (2.23 < 3) |
| 2015-09-10 | 13:28 | 7,769.35 | short | bear | EOD | 9.5 | R:R < min (0.74 < 3) |
| 2015-09-21 | 14:21 | 7,972.75 | short | bear | EOD | -15.6 | R:R < min (2.26 < 3) |
| 2015-10-19 | 14:15 | 8,271.60 | short | bear | EOD | 7.2 | R:R < min (2.85 < 3) |
| 2015-11-20 | 14:15 | 7,905.92 | short | bear | EOD | 26.4 | R:R < min (2.82 < 3) |
| 2015-11-27 | 09:16 | 7,901.35 | short | bear | SL | -34.8 | R:R < min (0.05 < 3) |
| 2015-12-02 | 09:16 | 7,967.92 | short | bear | EOD | 24.3 | R:R < min (1.13 < 3) |
| 2015-12-17 | 09:50 | 7,770.28 | short | bear | SL | -34.2 | R:R < min (1.05 < 3) |

**timeout — no commitment within max_armed_bars** (120)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-10 | 09:16 | 8,739.42 | long | bull | SL | -38.1 | timeout |
| 2015-04-29 | 13:04 | 8,291.80 | short | bear | TARGET | 63.2 | timeout |
| 2015-05-28 | 09:16 | 8,362.42 | short | bear | TARGET | 63.7 | timeout |
| 2015-06-10 | 09:44 | 8,102.50 | short | bear | SL | -35.6 | timeout |
| 2015-06-15 | 09:44 | 8,031.40 | short | bear | EOD | 3.6 | timeout |
| 2015-06-30 | 09:16 | 8,347.42 | short | bear | EOD | -22.8 | timeout |
| 2015-08-27 | 09:20 | 7,914.42 | short | bear | SL | -34.8 | timeout |
| 2015-10-07 | 10:15 | 8,175.80 | short | bear | EOD | 13.5 | timeout |
| 2015-11-05 | 12:00 | 8,025.68 | short | bear | EOD | 44.0 | timeout |
| 2015-11-06 | 09:26 | 7,988.80 | short | bear | EOD | 36.5 | timeout |
| 2015-12-11 | 10:15 | 7,673.50 | short | bear | TARGET | 58.2 | timeout |
| 2015-12-14 | 12:49 | 7,651.80 | short | bear | EOD | 13.2 | timeout |
| 2016-01-13 | 10:15 | 7,583.40 | short | bear | TARGET | 57.4 | timeout |
| 2016-02-25 | 13:35 | 6,988.62 | short | bear | EOD | 9.7 | timeout |
| 2016-02-29 | 09:16 | 7,040.20 | short | bear | SL | -31.2 | timeout |

**against the Daily trend** (1389)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-13 | 09:18 | 8,817.17 | short | bull | TARGET | 67.4 | Daily UP |
| 2015-03-13 | 10:08 | 8,782.88 | short | bull | TARGET | 66.8 | Daily UP |
| 2015-04-28 | 13:15 | 8,207.92 | long | bear | TARGET | 62.4 | Daily DOWN |
| 2015-04-30 | 09:17 | 8,190.28 | long | bear | SL | -35.9 | Daily DOWN |
| 2015-05-05 | 13:14 | 8,300.12 | long | bear | EOD | 18.1 | Daily DOWN |
| 2015-05-06 | 09:46 | 8,203.22 | long | bear | SL | -36.0 | Daily DOWN |
| 2015-05-06 | 09:47 | 8,157.32 | long | bear | TSL_SL | -3.2 | Daily DOWN |
| 2015-05-06 | 10:31 | 8,157.32 | long | bear | SL | -35.8 | Daily DOWN |
| 2015-05-07 | 14:15 | 8,031.70 | long | bear | SL | -35.3 | Daily DOWN |
| 2015-05-08 | 13:51 | 8,167.52 | long | bear | EOD | 31.7 | Daily DOWN |
| 2015-05-11 | 14:31 | 8,287.40 | long | bear | EOD | 20.6 | Daily DOWN |
| 2015-05-12 | 10:13 | 8,167.52 | long | bear | SL | -35.9 | Daily DOWN |
| 2015-05-13 | 09:17 | 8,166.40 | long | bear | TARGET | 62.2 | Daily DOWN |
| 2015-05-13 | 11:01 | 8,126.80 | long | bear | TARGET | 61.8 | Daily DOWN |
| 2015-05-14 | 10:46 | 8,168.78 | long | bear | EOD | 38.7 | Daily DOWN |

**impulsive approach** (53)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-03-13 | 11:41 | 8,684.35 | long | bull | SL | -37.9 | impulsive approach |
| 2015-05-27 | 09:55 | 8,329.92 | short | bear | EOD | 6.8 | impulsive approach |
| 2016-05-23 | 13:52 | 7,785.65 | short | bear | EOD | 43.7 | impulsive approach |
| 2016-08-30 | 09:16 | 8,654.58 | short | bear | SL | -37.8 | impulsive approach |
| 2017-04-18 | 14:42 | 9,125.92 | long | bull | EOD | -20.1 | impulsive approach |
| 2017-06-23 | 09:21 | 9,615.05 | long | bull | SL | -41.7 | impulsive approach |
| 2017-10-03 | 09:19 | 9,846.30 | long | bull | EOD | 0.9 | impulsive approach |
| 2017-10-11 | 14:23 | 9,958.30 | long | bull | EOD | 22.1 | impulsive approach |
| 2018-01-12 | 12:13 | 10,659.62 | long | bull | SL | -45.9 | impulsive approach |
| 2018-07-02 | 09:25 | 10,673.68 | long | bull | SL | -45.9 | impulsive approach |
| 2018-08-21 | 09:35 | 11,555.12 | long | bull | EOD | 19.3 | impulsive approach |
| 2018-09-04 | 09:33 | 11,539.62 | long | bull | SL | -49.4 | impulsive approach |
| 2019-02-27 | 12:13 | 10,764.70 | long | bull | EOD | 32.0 | impulsive approach |
| 2019-05-31 | 12:02 | 11,897.40 | long | bull | EOD | -22.2 | impulsive approach |
| 2019-06-12 | 13:25 | 11,866.00 | long | bull | EOD | 18.1 | impulsive approach |

**timeout — counter side absorbing inside the area** (20)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2015-04-29 | 09:16 | 8,274.33 | short | bear | SL | -36.2 | timeout |
| 2016-05-09 | 09:36 | 7,825.85 | short | bear | SL | -34.5 | timeout |
| 2016-11-16 | 09:20 | 8,183.50 | short | bear | TSL_SL | -3.2 | timeout |
| 2017-09-25 | 13:15 | 9,844.98 | long | bull | EOD | 0.5 | timeout |
| 2018-11-20 | 13:13 | 10,700.65 | long | bull | SL | -46.0 | timeout |
| 2018-12-20 | 09:16 | 10,888.90 | long | bull | EOD | 29.1 | timeout |
| 2019-01-11 | 14:01 | 10,752.92 | long | bull | EOD | 38.8 | timeout |
| 2019-02-01 | 14:33 | 10,830.92 | long | bull | EOD | 46.3 | timeout |
| 2020-01-01 | 12:31 | 12,176.18 | long | bull | EOD | -0.2 | timeout |
| 2020-05-27 | 09:18 | 9,058.17 | short | bear | SL | -39.4 | timeout |
| 2020-07-07 | 12:31 | 10,770.85 | short | bear | EOD | -18.7 | timeout |
| 2020-07-21 | 11:15 | 11,138.52 | short | bear | SL | -47.7 | timeout |
| 2020-09-28 | 13:00 | 11,222.02 | short | bear | EOD | 4.3 | timeout |
| 2021-03-17 | 14:09 | 14,776.30 | long | bull | EOD | 8.9 | timeout |
| 2021-10-12 | 09:16 | 17,924.90 | long | bull | SL | -75.0 | timeout |

**confirmed only in hindsight (not on the live cycle)** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2016-07-12 | 12:15 | 8,493.85 | short | bear | EOD | -17.7 |  |
| 2018-10-17 | 11:45 | 10,564.48 | long | bull | SL | -45.5 |  |
| 2020-10-01 | 14:15 | 11,408.15 | short | bear | EOD | 5.2 |  |

**gate confirmed, but after the no-new-entry cutoff** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2016-08-23 | 14:35 | 8,611.78 | short | bear | EOD | -8.2 | confirmed after the no-new-entry cutoff |
| 2019-09-25 | 14:35 | 11,422.55 | long | bull | EOD | -1.1 | confirmed after the no-new-entry cutoff |
| 2022-05-19 | 14:43 | 15,789.62 | long | bull | EOD | 7.6 | confirmed after the no-new-entry cutoff |

## 15M SRv2 — BANKNIFTY

> ⚠️ **ILLUSTRATION — dates fall in CONTAMINATED / ILLUSTRATION (elliott.data_policy): not IS / VAL validation.**

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| CONTAMINATED | all | touch | 29 | 7% | -20.66 | -599.0 | 657.2 | 0.14 | n < 30 — no conclusion |
| CONTAMINATED | all | confirmation | 3 | 33% | -21.12 | -63.4 | 63.4 | 0.09 | n < 30 — no conclusion |
| CONTAMINATED | all | confirmation + structural exit (not live) | 3 | 67% | -8.37 | -25.1 | 97.3 | 0.74 | n < 30 — no conclusion |
| CONTAMINATED | bear | touch | 29 | 7% | -20.66 | -599.0 | 657.2 | 0.14 | n < 30 — no conclusion |
| CONTAMINATED | bear | confirmation | 3 | 33% | -21.12 | -63.4 | 63.4 | 0.09 | n < 30 — no conclusion |
| CONTAMINATED | bear | confirmation + structural exit (not live) | 3 | 67% | -8.37 | -25.1 | 97.3 | 0.74 | n < 30 — no conclusion |
| ILLUSTRATION | all | touch | 2 | 0% | -20.46 | -40.9 | 40.9 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | all | confirmation | 1 | 0% | -6.66 | -6.7 | 6.7 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | all | confirmation + structural exit (not live) | 1 | 0% | -178.28 | -178.3 | 178.3 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | bear | touch | 2 | 0% | -20.46 | -40.9 | 40.9 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | bear | confirmation | 1 | 0% | -6.66 | -6.7 | 6.7 | 0.00 | n < 30 — no conclusion |
| ILLUSTRATION | bear | confirmation + structural exit (not live) | 1 | 0% | -178.28 | -178.3 | 178.3 | 0.00 | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 31 · kept by the gate: 2 (taken by the confirmation arm: 2) · rejected: 29.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | against the Daily trend | 10 | 0 | -296.1 | -29.61 | 296.1 | n < 30 |
| CONTAMINATED | timeout — no commitment within max_armed_bars | 6 | 0 | -97.8 | -16.30 | 97.8 | n < 30 |
| CONTAMINATED | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 3 | 0 | -48.5 | -16.17 | 48.5 | n < 30 |
| CONTAMINATED | R:R below minimum | 3 | 1 | 22.7 | 7.57 | -22.7 | n < 30 |
| CONTAMINATED | kept — the gate confirmed the same visit and side | 2 | 0 | -71.2 | -35.60 | — | n < 30 |
| CONTAMINATED | gate confirmed, but after the no-new-entry cutoff | 2 | 1 | -31.1 | -15.54 | 31.1 | n < 30 |
| CONTAMINATED | area broken (real break) | 2 | 0 | -70.4 | -35.18 | 70.4 | n < 30 |
| CONTAMINATED | impulsive approach | 1 | 0 | -6.7 | -6.66 | 6.7 | n < 30 |
| ILLUSTRATION | impulsive approach | 2 | 0 | -40.9 | -20.46 | 40.9 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay/trades.csv`)

**timeout — no commitment within max_armed_bars** (6)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-17 | 10:45 | 58,184.35 | short | bear | SL | -35.7 | timeout |
| 2026-07-31 | 09:45 | 57,299.05 | short | bear | TSL_SL | -6.7 | timeout |
| 2026-08-21 | 10:00 | 57,732.58 | short | bear | TSL_SL | -6.7 | timeout |
| 2026-08-21 | 11:00 | 57,732.58 | short | bear | TSL_SL | -6.7 | timeout |
| 2026-09-04 | 11:30 | 57,615.05 | short | bear | SL | -35.5 | timeout |
| 2026-09-04 | 12:00 | 57,615.05 | short | bear | TSL_SL | -6.7 | timeout |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-27 | 10:30 | 57,074.75 | short | bear | TSL_SL | -6.7 |  |
| 2026-07-27 | 11:15 | 57,074.75 | short | bear | SL | -35.2 |  |
| 2026-09-03 | 10:45 | 57,615.05 | short | bear | TSL_SL | -6.7 |  |

**gate confirmed, but after the no-new-entry cutoff** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-29 | 14:30 | 57,299.05 | short | bear | EOD | 3.8 | confirmed after the no-new-entry cutoff |
| 2026-09-18 | 14:15 | 56,426.55 | short | bear | SL | -34.9 | confirmed after the no-new-entry cutoff |

**against the Daily trend** (10)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-08-11 | 11:00 | 57,265.30 | long | bear | SL | -35.3 | Daily DOWN |
| 2026-08-11 | 11:30 | 57,265.30 | long | bear | TSL_SL | -6.7 | Daily DOWN |
| 2026-08-14 | 12:00 | 57,392.98 | long | bear | SL | -35.4 | Daily DOWN |
| 2026-08-17 | 09:30 | 57,206.05 | long | bear | SL | -35.3 | Daily DOWN |
| 2026-08-27 | 12:15 | 57,655.88 | long | bear | SL | -35.5 | Daily DOWN |
| 2026-08-28 | 09:30 | 57,406.12 | long | bear | SL | -35.4 | Daily DOWN |
| 2026-08-28 | 10:00 | 57,406.12 | long | bear | TSL_SL | -6.7 | Daily DOWN |
| 2026-08-31 | 10:30 | 57,240.80 | long | bear | SL | -35.3 | Daily DOWN |
| 2026-09-01 | 14:00 | 57,225.68 | long | bear | SL | -35.3 | Daily DOWN |
| 2026-09-01 | 14:30 | 57,225.68 | long | bear | SL | -35.3 | Daily DOWN |

**impulsive approach** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-08-17 | 13:15 | 57,647.88 | short | bear | TSL_SL | -6.7 | impulsive approach |
| 2026-10-09 | 10:00 | 55,207.82 | short | bear | SL | -34.2 | impulsive approach |
| 2026-10-09 | 10:30 | 55,207.82 | short | bear | TSL_SL | -6.7 | impulsive approach |

**area broken (real break)** (2)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-03 | 09:30 | 57,615.05 | short | bear | SL | -35.5 | broken |
| 2026-09-11 | 14:00 | 56,470.52 | short | bear | SL | -34.9 | broken |

**R:R below minimum** (3)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-03 | 10:00 | 57,749.95 | short | bear | SL | -35.5 | R:R < min (0.35 < 3) |
| 2026-09-21 | 14:00 | 56,656.75 | short | bear | EOD | 93.2 | R:R < min (0.75 < 3) |
| 2026-09-22 | 09:45 | 56,656.75 | short | bear | SL | -35.0 | R:R < min (0.43 < 3) |

## MCX — GOLD

> ⚠️ **ILLUSTRATION — MCX settings defaults are one SL / target in futures points for every commodity (20 / 40; no per-commodity defaults exist) ⇒ unrealistic for GOLD / SILVER / COPPER; ≈ 4 months of 30m data, no volume, Daily trend from ≤ 4 months.**

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| CONTAMINATED | all | touch | 31 | 23% | -51.18 | -1,586.6 | 1,598.8 | 0.05 |  |
| CONTAMINATED | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | bull | touch | 15 | 7% | -54.55 | -818.2 | 818.2 | 0.01 | n < 30 — no conclusion |
| CONTAMINATED | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | no trend | touch | 16 | 38% | -48.03 | -768.4 | 780.6 | 0.09 | n < 30 — no conclusion |
| CONTAMINATED | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

- skipped (confirmation): SKIPPED_GATE_SL_TOO_WIDE × 2

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 31 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 31.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | Daily trend unclear / entries blocked | 16 | 6 | -768.4 | -48.03 | 768.4 | n < 30 |
| CONTAMINATED | against the Daily trend | 6 | 0 | -335.9 | -55.98 | 335.9 | n < 30 |
| CONTAMINATED | area broken (real break) | 5 | 0 | -316.4 | -63.29 | 316.4 | n < 30 |
| CONTAMINATED | R:R below minimum | 2 | 0 | -97.2 | -48.60 | 97.2 | n < 30 |
| CONTAMINATED | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 1 | 0 | -79.8 | -79.82 | 79.8 | n < 30 |
| CONTAMINATED | timeout — no commitment within max_armed_bars | 1 | 1 | 11.1 | 11.15 | -11.1 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay/trades.csv`)

**Daily trend unclear / entries blocked** (16)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-01 | 13:00 | 147,578.00 | long | no trend | TARGET | 12.1 | Daily UNKNOWN |
| 2026-07-16 | 18:00 | 143,964.50 | long | no trend | SL | -165.2 | Daily NEUTRAL |
| 2026-07-21 | 09:30 | 144,437.50 | short | no trend | TARGET | 12.7 | Daily NEUTRAL |
| 2026-07-21 | 10:30 | 144,437.50 | short | no trend | SL | -47.3 | Daily NEUTRAL |
| 2026-07-21 | 20:30 | 144,960.00 | short | no trend | SL | -47.4 | Daily NEUTRAL |
| 2026-07-22 | 10:00 | 147,026.50 | short | no trend | TARGET | 12.3 | Daily NEUTRAL |
| 2026-07-24 | 12:00 | 144,611.00 | long | no trend | SL | -298.3 | Daily NEUTRAL |
| 2026-07-28 | 09:30 | 144,123.50 | long | no trend | SL | -47.3 | Daily NEUTRAL |
| 2026-07-29 | 10:00 | 143,656.00 | long | no trend | TARGET | 12.8 | Daily NEUTRAL |
| 2026-07-29 | 19:30 | 143,205.50 | long | no trend | SL | -47.1 | Daily NEUTRAL |
| 2026-07-30 | 09:30 | 144,706.00 | short | no trend | TARGET | 12.7 | Daily NEUTRAL |
| 2026-07-30 | 21:30 | 145,971.00 | short | no trend | SL | -47.5 | Daily NEUTRAL |
| 2026-07-31 | 19:00 | 144,251.50 | long | no trend | SL | -47.3 | Daily NEUTRAL |
| 2026-08-05 | 09:30 | 146,185.00 | short | no trend | SL | -47.6 | Daily NEUTRAL |
| 2026-08-05 | 18:00 | 148,560.00 | short | no trend | TARGET | 12.0 | Daily NEUTRAL |

**against the Daily trend** (6)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-08-17 | 10:00 | 156,924.50 | short | bull | SL | -49.4 | Daily UP |
| 2026-09-03 | 10:00 | 155,853.50 | short | bull | SL | -49.3 | Daily UP |
| 2026-09-09 | 19:00 | 155,346.50 | short | bull | SL | -49.2 | Daily UP |
| 2026-09-16 | 11:00 | 153,216.00 | short | bull | SL | -88.8 | Daily UP |
| 2026-09-17 | 18:30 | 154,485.00 | short | bull | SL | -49.0 | Daily UP |
| 2026-09-18 | 12:00 | 155,565.00 | short | bull | SL | -50.2 | Daily UP |

**area broken (real break)** (5)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-08-19 | 09:30 | 155,667.00 | long | bull | SL | -49.2 | broken |
| 2026-08-26 | 21:00 | 163,047.00 | long | bull | SL | -50.5 | broken |
| 2026-08-31 | 09:30 | 155,694.00 | long | bull | SL | -86.3 | broken |
| 2026-09-17 | 10:00 | 152,128.00 | long | bull | SL | -81.6 | broken |
| 2026-09-24 | 12:30 | 152,941.00 | long | bull | SL | -48.8 | broken |

**timeout — no commitment within max_armed_bars** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-10 | 18:30 | 153,494.50 | long | bull | TARGET | 11.1 | timeout |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-11 | 10:30 | 153,216.00 | long | bull | SL | -79.8 |  |

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
| CONTAMINATED | all | touch | 37 | 0% | -67.02 | -2,479.7 | 2,479.7 | 0.00 |  |
| CONTAMINATED | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | bear | touch | 1 | 0% | -116.33 | -116.3 | 116.3 | 0.00 | n < 30 — no conclusion |
| CONTAMINATED | bear | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | no trend | touch | 36 | 0% | -65.65 | -2,363.3 | 2,363.3 | 0.00 |  |
| CONTAMINATED | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 37 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 37.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | Daily trend unclear / entries blocked | 36 | 0 | -2,363.3 | -65.65 | 2,363.3 |  |
| CONTAMINATED | against the Daily trend | 1 | 0 | -116.3 | -116.33 | 116.3 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay/trades.csv`)

**Daily trend unclear / entries blocked** (36)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-03 | 16:00 | 243,509.00 | short | no trend | TARGET | -5.4 | Daily UNKNOWN |
| 2026-07-07 | 17:00 | 236,645.00 | long | no trend | SL | -279.3 | Daily NEUTRAL |
| 2026-07-08 | 20:30 | 227,054.00 | long | no trend | SL | -62.6 | Daily NEUTRAL |
| 2026-07-09 | 13:30 | 232,850.00 | short | no trend | SL | -63.6 | Daily NEUTRAL |
| 2026-07-10 | 17:30 | 228,931.50 | long | no trend | TARGET | -2.9 | Daily NEUTRAL |
| 2026-07-10 | 19:00 | 228,931.50 | long | no trend | TARGET | -3.0 | Daily NEUTRAL |
| 2026-07-13 | 13:00 | 225,929.00 | long | no trend | TARGET | -2.4 | Daily NEUTRAL |
| 2026-07-13 | 19:30 | 225,929.00 | long | no trend | SL | -62.4 | Daily NEUTRAL |
| 2026-07-13 | 22:00 | 224,846.00 | long | no trend | SL | -62.2 | Daily NEUTRAL |
| 2026-07-15 | 22:00 | 224,846.00 | long | no trend | SL | -62.2 | Daily NEUTRAL |
| 2026-07-16 | 11:00 | 224,846.00 | long | no trend | SL | -92.3 | Daily NEUTRAL |
| 2026-07-21 | 09:30 | 224,687.50 | short | no trend | SL | -62.2 | Daily NEUTRAL |
| 2026-07-21 | 22:00 | 228,478.00 | short | no trend | TARGET | -2.8 | Daily NEUTRAL |
| 2026-07-23 | 17:00 | 226,002.50 | long | no trend | SL | -62.4 | Daily NEUTRAL |
| 2026-07-23 | 18:30 | 223,842.50 | long | no trend | SL | -62.1 | Daily NEUTRAL |

**against the Daily trend** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-09-30 | 17:00 | 225,300.50 | long | bear | SL | -116.3 | Daily DOWN |

## MCX — COPPER

> ⚠️ **ILLUSTRATION — MCX settings defaults are one SL / target in futures points for every commodity (20 / 40; no per-commodity defaults exist) ⇒ unrealistic for GOLD / SILVER / COPPER; ≈ 4 months of 30m data, no volume, Daily trend from ≤ 4 months.**

### Results by Daily trend context (net of costs, points)

| period | trend | arm | n | win rate | net expectancy | net total | max DD | profit factor | note |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| CONTAMINATED | all | touch | 32 | 34% | -3.23 | -103.5 | 115.4 | 0.28 |  |
| CONTAMINATED | all | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | bull | touch | 28 | 29% | -4.12 | -115.4 | 115.4 | 0.13 | n < 30 — no conclusion |
| CONTAMINATED | bull | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |
| CONTAMINATED | no trend | touch | 4 | 75% | 2.98 | 11.9 | 10.4 | 2.14 | n < 30 — no conclusion |
| CONTAMINATED | no trend | confirmation | 0 | — | — | 0.0 | 0.0 | — | n < 30 — no conclusion |

### Legacy (touch) trades the gate rejects — grouped by reason

Legacy trades: 32 · kept by the gate: 0 (taken by the confirmation arm: 0) · rejected: 32.

`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.

| period | gate verdict | n | wins | net total | net expectancy | saved | note |
|---|---|---:|---:|---:|---:|---:|---|
| CONTAMINATED | Daily trend unclear / entries blocked | 13 | 5 | -10.9 | -0.84 | 10.9 | n < 30 |
| CONTAMINATED | against the Daily trend | 9 | 2 | -47.9 | -5.32 | 47.9 | n < 30 |
| CONTAMINATED | area broken (real break) | 4 | 1 | -31.9 | -7.98 | 31.9 | n < 30 |
| CONTAMINATED | no gate arrival of the same side (price already inside the area / not at the area on closed candles) | 4 | 1 | -15.4 | -3.84 | 15.4 | n < 30 |
| CONTAMINATED | R:R below minimum | 1 | 1 | 0.9 | 0.89 | -0.9 | n < 30 |
| CONTAMINATED | timeout — no commitment within max_armed_bars | 1 | 1 | 1.7 | 1.74 | -1.7 | n < 30 |

### Rejected legacy trades (first 15 per reason; full list in `data/research/level_bots_replay/trades.csv`)

**Daily trend unclear / entries blocked** (13)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-08 | 21:00 | 1,306.80 | long | no trend | EOD | 5.9 | Daily NEUTRAL |
| 2026-07-09 | 17:30 | 1,329.25 | short | no trend | EOD | -10.4 | Daily NEUTRAL |
| 2026-07-13 | 19:30 | 1,348.30 | short | no trend | EOD | 7.7 | Daily NEUTRAL |
| 2026-07-16 | 10:30 | 1,359.95 | short | no trend | EOD | 8.7 | Daily NEUTRAL |
| 2026-09-16 | 09:30 | 1,382.42 | short | bull | EOD | -1.7 | Daily UP: parent correction (A1) |
| 2026-09-17 | 15:00 | 1,394.68 | short | bull | EOD | -9.9 | Daily UP: parent correction (A1) |
| 2026-09-18 | 12:30 | 1,406.68 | short | bull | EOD | -4.9 | Daily UP: parent correction (A1) |
| 2026-09-21 | 14:00 | 1,422.12 | short | bull | EOD | 1.3 | Daily UP: parent correction (A1) |
| 2026-09-23 | 19:30 | 1,415.38 | long | bull | EOD | 0.2 | Daily UP: parent correction (A1) |
| 2026-09-28 | 11:30 | 1,405.00 | long | bull | EOD | -0.5 | Daily UP: parent correction (A1) |
| 2026-10-05 | 18:30 | 1,409.28 | short | bull | EOD | -4.0 | Daily UP: parent correction (A1) |
| 2026-10-06 | 09:30 | 1,415.70 | short | bull | EOD | -0.3 | Daily UP: parent correction (A1) |
| 2026-10-07 | 13:00 | 1,416.32 | short | bull | EOD | -3.1 | Daily UP: parent correction (A1) |

**against the Daily trend** (9)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-20 | 09:30 | 1,349.45 | short | bull | EOD | -6.5 | Daily UP |
| 2026-07-30 | 10:30 | 1,348.95 | short | bull | EOD | -12.1 | Daily UP |
| 2026-07-31 | 09:30 | 1,361.48 | short | bull | EOD | 2.6 | Daily UP |
| 2026-08-05 | 10:00 | 1,386.00 | short | bull | EOD | -6.9 | Daily UP |
| 2026-08-20 | 09:30 | 1,390.95 | short | bull | EOD | 4.0 | Daily UP |
| 2026-08-21 | 09:30 | 1,392.57 | short | bull | EOD | -5.2 | Daily UP |
| 2026-09-03 | 19:00 | 1,386.35 | short | bull | EOD | -5.8 | Daily UP |
| 2026-09-07 | 13:30 | 1,393.98 | short | bull | EOD | -1.4 | Daily UP |
| 2026-09-08 | 09:30 | 1,404.12 | short | bull | EOD | -16.8 | Daily UP |

**no gate arrival of the same side (price already inside the area / not at the area on closed candles)** (4)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-07-23 | 16:00 | 1,369.45 | long | bull | EOD | -14.8 |  |
| 2026-07-24 | 11:00 | 1,351.98 | long | bull | EOD | -0.8 |  |
| 2026-07-28 | 09:30 | 1,349.70 | long | bull | EOD | -4.9 |  |
| 2026-08-19 | 09:30 | 1,380.92 | long | bull | EOD | 5.0 |  |

**area broken (real break)** (4)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-08-07 | 22:30 | 1,383.50 | long | bull | EOD | -0.7 | broken |
| 2026-08-26 | 20:30 | 1,397.25 | long | bull | EOD | 1.1 | broken |
| 2026-09-10 | 16:00 | 1,406.18 | long | bull | SL | -20.4 | broken |
| 2026-09-10 | 18:30 | 1,393.58 | long | bull | EOD | -12.1 | broken |

**timeout — no commitment within max_armed_bars** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-08-17 | 19:00 | 1,390.95 | long | bull | EOD | 1.7 | timeout |

**R:R below minimum** (1)

| day | time | level | side | trend | exit | net pts | detail |
|---|---|---:|---|---|---|---:|---|
| 2026-08-31 | 09:30 | 1,394.25 | long | bull | EOD | 0.9 | R:R < min (1.16 < 3) |

