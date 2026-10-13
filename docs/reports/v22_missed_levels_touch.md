# V22: the missed 9 Oct supply and the 29 Sep "no touch" (TELEGRAM_CLEANUP §4–§5, ONE_BOT §7(e))

Data: NIFTY 1m 2026-07-01 → 2026-10-09 (the 9 Oct file is the VPS export). The Daily warm-up is used only to build Daily state and is
never shown. Engine: `decision3` V22 at main `1e6c9ac` plus this branch. Charts are in private trade-data
(`review/v22/recent_2026_09_10/NIFTY/daymap_20260929.png`, `daymap_20261009.png`).

## 1. 9 Oct: why 22,570–22,640 was not a decision3 1H level

On 9 Oct, price traded at 22,295–22,580. The level list showed only 22,715–22,724 (BOS base) and 22,767–22,776 (Daily H, 6 Oct).

The level lifecycle (`levels.py`) shows the area **was** known. The method read it correctly as a broken support that became supply.
**Death** then removed it, and **merging** had already distorted it:

| Level | Band | What happened |
|---|---|---|
| L1 | 22,476–22,809 (`a:D-prior + a:W-prior + a:D2 + b`, flip `c`) | Support. 1 Oct 12:45: 3 closes below ⇒ **flip to resistance** (broken support = supply). On 8 Oct at 11:15 the close (22,338) went below the D2 L 22,397 under the band ⇒ **dead**, because death is checked on the *original* role's side (Q2 default). |
| L18 | 22,518–22,527 (`a:W-prior`, weekly swing) | 8 Oct 09:45: flip to resistance. Died at 11:15 by the same rule. |
| L27 | 22,715–22,724 (`b`) | BOS 8 Oct 11:15. Its origin is the last confirmed D2 H, 22,732 (6 Oct), so the base is the first bearish 1H candle after it. |

Root causes, in order:

1. **Expired (Q2 death side).** A flipped support dies when the next swing *below* it breaks. In a downtrend, the move away from a
   broken support almost always breaks that swing. So "broken support = supply" (spec ② (c)) can never be retested. This is a rule
   choice (Q2 was an open default), not a coding slip.
2. **Merged (Q19).** The 22,570–22,640 area sits inside L1, which is 333 pts wide. L1 was built at bar 0 from Q40 prior Daily and
   Weekly bands, then grew with a D2 H (22,809), a BOS base and the D2 H 22,732, even though their roles differ. Even when L1 is
   alive, the stop goes above 22,809, so R:R < 1.
3. **Degree.** The actual lows of the broken support (7 Oct 22,546 / 22,578) and the start of the sharp fall (22,649 on 7 Oct 14:15;
   22,599 at the 8 Oct open) are D0/D1 swings. By design, they do not become levels.

**Fix.** A new setting, `level_death_side` (**TL1 approved by Abhi 2026-10-12: default = "role"**):
- `"role0"`: the old Q2 rule, kept only as an explicit setting (revert / what-if).
- `"role"` (default): a flipped level dies only when a swing beyond its *current* role breaks.

The merge width (**TL2**, Abhi: "not now") and a 1H
sharp-fall base (**TL3**) are also listed as options.

NIFTY Sep–Oct 2026, old vs new default:

| | setups | no_trade | wait |
|---|---|---|---|
| role0 (old default) | 1 (30 Sep 13:15 B) | 118 | 529 |
| role (new default) | 1 (same) | 142 | 505 |

On 9 Oct with `"role"` (now the default):
- Both supplies, L1 and L18, are active. Price touches them from 09:45, so the bars no longer read "no touch".
- **11:30**: bear call at L18 22,518–22,527. Commitment `inside_break`, entry 22,487, SL 22,542, target 22,180, **R:R 5.55**.
  The only block is conviction *weak*, from the maturity cap. That cap belongs to branch `claude/oct12-blockers` (maturity = evidence
  only).
- At L1, 11:00 / 11:45 / 15:00 log `no_trade R:R` (0.99 / 0.74 / 0.03) because of the merged band (TL2).

12 Oct (one-bot §7(e), supply ≈22,600 spot) is the same blind spot: L1 and L18 died on 8 Oct, so nothing above 22,476 and below
22,715 existed. `live_export/2026-10-12` was not available here, so the 12 Oct replay is still pending. Fixture
`tests/test_decision3_level_death_side.py` (mirrored): under `"role"` the flipped supply survives the swing break and is active on
the retest. Under `"role0"` it dies, as before.

## 2. 29 Sep 12:15: the "no touch" bug

The 12:15 bar (O 22,742, H 22,744, L 22,673, C 22,677) touched the 1H supply 22,725–22,810 (lo 22,725 ≤ H 22,744).
`at_level` / `touch_window` were correct: for that level ③ ✔, ⑥ engulf grade A, ⑦ R:R 0.77 ⇒ `no_trade`.

The bug was in `engine.decide()`, which picks one level to report per bar. It ranked setup < **wait** < no_trade. The second active
level (22,930–23,002, never reached) returns *wait / no touch*, so it outranked the touched level's real verdict.

Fix: a level with ③ ✔ (price is at it) carries the bar's verdict. When no level has ③ ✔, the old order applies. Setups are
unaffected.

| Sep–Oct 2026 | before | after |
|---|---|---|
| setups | 1 | 1 |
| no_trade | 5 | 118 |
| wait | 642 | 529 |

The 113 changed bars are 63 × "R:R < 3" and 50 × "4th+ attempt". Bars that logged "no touch" while another level was touched: 113 → 0.

### The full gate on 29 Sep 12:15

| Check | Result |
|---|---|
| Touch | ✔ (12:15 high inside the band; first touch 11:30) |
| a2 handover (`zone_study`, from K open 11:00 or first touch 11:30) | Buying candles weakening ✔, no absorption. The trend side is NA: no red candle before 12:15, so the first half is empty ⇒ `handover` = False on main (TL4, `claude/v22-confirmation`). |
| c0 dominance | Engulf, body **2.6×** the window mean (4.2× from 11:30) ≥ 1.5 ✔ |
| c0 volume | NIFTY FUT 5-min data starts 30 Sep 2026 (`trade-data/futures*/oe_futures_5min_NIFTY*.parquet`) ⇒ NA ⇒ grade max B (Daily cap is B anyway) |
| c1 5M CHoCH (diagnostic) | The 5M rally makes HL 22,707 (11:45) and HH 22,753 (12:05). The 12:25 5M bar closes at 22,677 < 22,707 ⇒ **bearish CHoCH ✔** by 12:30. Gate wiring lands with `claude/v22-confirmation`. |
| R:R | Entry 22,677, SL 22,816 (band top + buffer). |

R:R against the nearest demand:
- 15M (day low 22,570): 0.77
- 1H (support 22,550): 0.92
- Daily (prior band top 22,550): 0.92

A 3R trade needs a target ≤ 22,260.

**Verdict (corrected, Abhi rr-correction): valid bear-call read** (touch + buyers exhausting + dominant bearish engulf + 5M CHoCH).
There is no "skipped on R:R" outcome: Abhi never asked for an R:R filter — R:R, SL, target, lots and exits are his dashboard
settings. The R:R numbers above are history / information only. (The earlier verdict "no setup, skipped on R:R (0.77 < 3)" came from
the legacy ⑦, which now runs only with `rr_step` = True.) Fixture: `tests/test_decision3_touch_levels.py`.
- Synthetic, mirrored: the read, plus the decide-level selection with the near and far levels in either order (default ⇒ bear-call
  setup at the touched supply; legacy `rr_step` = True ⇒ the old `no_trade · R:R < 3`, still at the touched level, not "no touch").
- Real-data check (skipped if private data is missing): touch + dominant engulf + counter weakening.
