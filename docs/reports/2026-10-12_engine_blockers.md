# 12 Oct (NIFTY bear call) — decision3 V22 blockers

Branch `claude/oct12-blockers` (from `main` + merged `claude/v22-confirmation` @31e907b, so a2, c0 and c1 are active).
This covers the reference case in TRADE_SESSION_ONE_BOT_TOMORROW §7: Daily DOWN → supply ≈22,600 plus the descending trendline from the
30-Sep high → a corrective channel on falling FUT volume → a 09:15 sweep with a long upper wick on high volume → a channel break
(LTF CHoCH) → a dominant red candle.

**Data status.** The 12-Oct collector export (`trade-data/live_export/2026-10-12/`) had not arrived when this was written, so the
12-Oct replay ran on the **synthetic fixture** (`tests/oct12_fixture.py`, which reproduces the sequence above with no real prices).
Real 1m data up to 9 Oct was used to check the state before 12 Oct. Once the export lands, run:

```
python3 scripts/replay_day.py --symbol NIFTY --day 2026-10-12 --daily <nifty_daily_is> <nifty_daily_ext> <nifty_daily_post> \
        --dry-run-telegram --out-dir <dir>
```

## Findings per blocker

| # | Blocker | Finding (real data to 9 Oct) | Fix on this branch |
|---|---|---|---|
| a | Code running on 12 Oct | Covered by the separate `2026-10-12_no_signals.md` diagnosis, which needs VPS `diag.txt` (inside the same pending export). The live `engine_signal` service still runs **decision2**, not V22. | — (deploy / wiring task) |
| b | Maturity cap | **Blocking.** At every bar on 8–9 Oct the state was `Daily DOWN · impulse · mature (Q44 target 22,183) ⇒ cap weak`. "Weak" means WAIT, so no V22 setup was possible on any bar while the trend was mature. Protected 24,774 was intact and there was no counter impulse. | Maturity is now evidence only. If structure is intact (`mature_intact`: phase ≠ origin_broken and counter ≠ correction), conviction drops one step (A ⇒ B; B stays B) and the bar still becomes a setup. If structure is broken, the old weak cap still applies. Row field `mature_step_down`. |
| c | 09:15 candle | `entry_start` = 09:30 also excluded 09:15 from `_same_window`. The opening candle therefore could not be the first half of a 2-candle form (engulf / star / tweezer …) or the reference candle. Touch, sweep ★, the liquidity sweep and the a2 / c0 / c1 window **already** included 09:15. | New `evidence_start` = 09:15 (session open, "व्याख्या"). The opening candle now counts as evidence; the entry window (`entry_start` … `entry_end`) is unchanged. |
| d | Sloping resistance | V22 had no sloping area (`trendline.py` only had the K inner line, ⑤). On real data the D2 swing highs 22,809 (30 Sep) → 22,732 (6 Oct) form a descending line at **≈22,654 at 12-Oct 09:15**, which matches Abhi's line (FUT ≈22,667). **There was no live horizontal level there** (see e), so no confluence. | `trendline.swing_line` and `confluence_areas`: a line through confirmed trend-degree (D2) swings (lower highs / higher lows), using only swings known at t. Line + trade-side horizontal level ⇒ an extra area = the overlap band (births + `tl`, counts as level ★). A trendline on its own is **not** an area (spec ② births a–d): OPEN_QUESTIONS D12-2. |
| e | Missing 1H level 22,600–22,670 | **Blocking, same blind spot as 9 Oct.** Band 22,476–22,809 (flipped to resistance on 1 Oct) died on 8 Oct 11:15 under the old-role death rule ("swing 22,397 broken by close"). On 9 Oct the only resistances were 22,715–22,724 and 22,767–22,776, and a spike to ≈22,600 touches neither. | Not duplicated. TL1 `level_death_side="role"` is on `claude/v22-touch-levels`; `replay_day.py` passes it explicitly (it has no effect until that branch merges). |
| f | FUT volume | V22 on `main` had **no volume at all** (`Levels.A` was OHLC only), so a2 and c0 were NA. With the merged confirmation branch, V22 takes `futures=` → `legs2.volume.bar_volume`: near-month contract, each 15M bar = sum of the three 09:15-anchored 5M bins, matched to the spot `bar_start` exactly. The level-gate live path (`level_gate_bot.attach_futures_volume`) also matches by exact bar start (Upstox index and FUT candles are both bar-start stamped). **No misalignment found.** The stored FUT 5M data ends on 8 Oct, so 9 Oct has FUT volume on 0/24 bars in replay. | Test `test_futures_volume_15m_is_sum_of_0915_anchored_5m_bins` |

Still open, expected on real data (not verifiable without the export):
- **⑦ R:R ≥ 3.** SL sits above the sweep high and the target is the nearer of I_end and the nearest live support. If the 09:15 wick is long and the 9-Oct channel left supports (e.g. the ≈22,450 dashed level), R:R falls below 3. In the fixture an earlier geometry gave R:R 0.32 because of exactly this. OPEN_QUESTIONS D12-5.
- **c1 on a clean V-reversal.** PR #308 fixes this case: with no LTF lower high and no sweep, the result is "LTF still trending against". In the fixture the sweep branch passes.

## Replay of 12 Oct (synthetic fixture, a2 + c0 + c1 active)

`python3 scripts/replay_day.py --symbol NIFTY --day 2026-10-12 --synthetic --dry-run-telegram --out-dir <dir>`

| bar | decision | reason |
|---|---|---|
| 09:15 | wait | ③ ✔ (spike into supply, sweep ★) · ⑥ outside the entry window (evidence only) |
| 09:30 | wait | ⑥ commitment on low volume (0.6× window) |
| **09:45** | **setup ✅ A — bear call** | ③ ✔ · ④ 2/4 · ⑥ strong_close, body 2.7×, volume 1.1×, 5M CHoCH (sweep of the high closed back inside, close below the 5M swing low at 09:40) · ⑦ R:R 3.13 |

Entry 22,708.92 · SL 22,985.75 · target 21,842.79 (I_end) · R:R 3.13. The trendline-confluence area (`10+TL`) gives the same setup.
The dry run writes the approval PNG plus `_message.txt`, which holds the exact `vision.worker.v1_caption` text with
"Vision: NA (Vision skipped: dry run)" and the engine line. The mirrored case (bull put) gives the same decisions.
Synthetic prices only demonstrate the gate path. They are not a claim about 12-Oct prices.

**a2 / c0 / c1:** all three are active in this replay (c1 required). a2 found no handover because the study window starts at arrival
(09:15) and has fewer than 4 bars; the channel's falling volume lies before arrival. a2 is therefore NA, not a blocker.

## Golden / chart diffs
- `test_mature_cap_in_pipeline` and `test_step1_…_mature…` were rewritten for the owner rule. The old Q15 (5) expectation, "mature ⇒ weak ⇒ no
  setup", no longer holds. No other decision3 test or golden changed (decision3 + level suites: 499 passed, 1 xfailed).
- V22 review charts were not regenerated. On NIFTY, mature periods (e.g. 8–9 Oct) can now show 🟡 setups where they used to show ⏳.

## Tests
`tests/test_decision3_oct12.py` (11, mirrored): first-hour setup with a2/c0/c1 and no lookahead, the maturity step, the opening candle as evidence,
the TL confluence area being known at t, a trendline alone not being an area, and the FUT 15M = 5M-bin sums.
