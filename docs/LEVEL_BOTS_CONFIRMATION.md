# Level bots — trend first, entry only after confirmation (L0 design note)

Abhi: TRADE_SESSION_LEVEL_BOTS_CONFIRMATION (§0–§10). Applies to 5M Instant, Classic, 15M SRv2, their shadows (SR V3, Vision) and MCX.
A stored level is only a candidate **area** (zone_low–zone_high), not a signal.

## One shared gate (no new method)
`bots_common/level_reaction.py` calls decision3 / elliott as they are today (no copies):

| Step | Function | Gate / evidence |
|---|---|---|
| ① Trend | `decision3.daily.fold` (degree-aware Dow, ABC_FIX), state known at yesterday's close; Upstox `day` candles ~10 years (same state as full history on NIFTY / BANKNIFTY), cached per day | gate |
| Area side | UP ⇒ bullish at demand below price; DOWN ⇒ bearish at supply above; RANGE ⇒ lower half bullish, upper half bearish (Q27/Q38) | gate |
| No entries | NEUTRAL / UNKNOWN, origin closed beyond (`origin_broken`), origin at risk (Q47), A1 parent correction (setting `allow_parent_correction`, default off) | gate |
| Approach (a) | consecutive wide-range candles (≥ 1.5 × median range) closing near the approach extreme ⇒ impulsive ⇒ no entry | gate |
| Zone study (a2) | `method.zone_study` on the window ARMED → commitment: trend-side candles growing (body ↑ required; range, close-to-extreme, volume) and counter-side weakening (body ↓ required; opposite wick, close away, volume) = handover ⇒ grade A. Counter-side strengthening (body + range ↑, volume ↑ when known) = absorption ⇒ no entry while it lasts. Patterns from in-zone swings (`zone_pattern`: wedge, channel / flag, double / triple top-bottom) named on the ticket, never required. One function, direction d; every test mirrored | gate (absorption) / grade |
| Contraction (④ a) | `method.contraction`: average range of the pullback candles inside the area < pullback's earlier candles AND impulse candles (no "exactly 3") — `power_a_rule` = relative (old strict3 = what-if) | evidence |
| Handover (b) | sweep (beyond far edge, close back), corrective approach (`power_shift` with the area), pattern, RSI divergence (NA in MVP) | grade A/B |
| Commitment (c, c0) | `method.commitment(..., win=ARMED)`: Q16 form + close beyond the area's inner edge + dominant (body ≥ `commit_dom_mult` × window average) + volume > window average when volume exists (lower ⇒ "commitment on low volume", keep waiting); volume NA ⇒ allowed, grade ≤ B, "volume: NA" | gate |
| Volume | index ⇒ its front futures (NIFTY FUT, BANKNIFTY FUT; SENSEX FUT not resolvable ⇒ NA); price from spot; MCX ⇒ contract volume | — |
| Real break | `elliott.breaks.break_from` on the far edge (displacement or no reclaim) ⇒ area broken; no breakout / reverse trade | disarm |
| ⑦ Risk | SL = beyond far edge and the armed-period extreme + 0.25 × median range; target = next opposite area; R:R ≥ `min_rr` (3) | gate |

State machine per (symbol, area): IDLE → ARMED → CONFIRMED | DISARMED (broken / timeout `max_armed_bars` / impulsive / R:R / no target / against trend).
It is replayed every cycle from today's **closed** confirmation-TF candles (restart-safe, causal; `entry` is True only on the commitment
candle itself). Fail-closed: any data / trend / code error ⇒ no new entry, reason logged. Exits are never touched.

Confirmation TF: 5M Instant 5m (1m only detects arrival), Classic 5m, 15M SRv2 15m, MCX 15m (dashboard `confirm_tf_minutes`).

## Bots (`bots_common/level_gate_bot.py`)
- `entry_mode`: `confirmation` (PAPER default) | `touch` (legacy; a LIVE bot keeps touch until Abhi changes it). Dashboard warns on touch.
- Confirmation mode: breakout entries off; RSI threshold / PCR gates off by default (`conf_rsi_gate_enabled`, `conf_pcr_gate_enabled`);
  max hits, cooldowns, one position at a time unchanged.
- CONFIRMED ⇒ the existing approval path (`vision.gate.entry_gate`, approval_required): chart with area / entry / SL / target + Vision audit
  + Telegram ✅ / ❌ ⇒ PAPER only on ✅ (drift check). Vision is audit-only.
- Legacy touch ⇒ only a `paper_would_have` record (bot `<bot>_touch_legacy`, lots 0), no Telegram.
- Signal log: `SKIPPED_GATE_*` + "[GATE] Watching demand 22,570–22,640 · price arrived · waiting for a bullish commitment · 3/8 bars".
- Ticket (Vision caption / approval): "inside supply: rising wedge · selling candles growing, buying candles weakening · volume rising on selling
  candles" and "commitment: bearish engulfing · body 1.8× window avg · volume 1.6× window avg".
- MCX: PAPER new entries paused until L4 (MCX gate); LIVE unchanged.

## Not in the MVP (follow-ups)
L4 MCX gate · full L5 dashboard (armed areas table, daily summary per bot) ·
structural exit (real break beyond the area) as an extra exit rule — today the bots' existing exits stay (never blocked) · RSI divergence evidence.

## L6 replay (touch vs confirmation)
`level_bots_replay.py` (pure) + `scripts/level_bots_replay.py` (CLI, local data only) ⇒ `docs/reports/level_bots_confirmation.md` and CSVs in
`data/research/level_bots_replay/`. Same days, same levels (bots' Dynamic S/R, hourly from closed bars), same costs (`charges.py`, points);
legacy arm = the bots' own touch / direction functions + default settings; confirmation arm = `level_reaction.evaluate` on closed confirmation-TF
candles with one `decision3.daily.fold` per symbol. NIFTY IS / VAL only (HOLDOUT guard); BANKNIFTY 15M (≈ 3 months) and MCX 30m (≈ 4 months) are
illustrations. Full run: `python3 scripts/level_bots_replay.py` (≈ 35 min, sequential).
