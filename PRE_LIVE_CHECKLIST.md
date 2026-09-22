# Pre-Live Trading Checklist

Status as of commit `a816e2b` (main). This is a working risk sign-off document,
not a one-time report — update it as items move between sections. Do not enable
LIVE trading on any symbol/broker whose gating item below is unresolved.

## 1. Fixed and verified (unit-tested, merged to `main`)

| # | Fix | PR |
|---|---|---|
| 1 | Signal Log duplicate entries (dedup compared volatile `reason` text, missed real dupes) | #45, #46 |
| 2 | SL/Target level computed without scaling by `lots × lot_size` | #46 |
| 3 | Naked-option trades crashed `open_multi_leg_trade` (`max_profit=None` used in arithmetic) | #46 |
| 4 | Naked-option SL level had the wrong sign | #46 |
| 5 | Broker reconciliation closed positions on any *absent* leg instead of a *confirmed-flat* leg — could blind-close a position still open at the broker | #46 |
| 6 | Kill switch read `trade_date` instead of `exit_time` for today's realized P&L — missed carried-forward trades closed today | #46 |
| 7 | Kill switch didn't block new trades when a broker-reconciled close still had unverified/`NULL` P&L | #46 |
| 8 | `engine_service.py` and `trade_monitor.py` could both run `manage_open_trades()` concurrently with no lock — now share one `ProcessLock` | #46 |
| 9 | Shoonya/Stocko LIVE orders could carry Upstox-shaped instrument identifiers straight to the broker (wrong exchange code, meaningless token) — now hard-blocked | #47 |
| 10 | SRv2 ignored the Dashboard's "Target — % of Net Premium" setting, always used a hardcoded 80% | #47 |
| 11 | Entry basis (`net_credit`, `sl_pnl_level`, logged fill price) used the pre-order chain snapshot instead of the actual fill price — ignored MARKET-order slippage for the position's entire lifetime | #47 |
| 12 | `fetch_ltp_map_detailed()` coerced a missing `last_price` to `0.0`, defeating the missing-data guard and risking a false early TARGET exit | #47 |
| 13 | ATM strike always rounded to a 50-point grid — silently failed strike selection on BANKNIFTY/SENSEX (100-point grid) roughly half the time | #47 |
| 14 | Stocko: same-second multi-leg orders could get an identical `user_order_id` and get rejected as duplicates | #47 |
| 15 | Stocko: missing `STOCKO_BASE_URL` crashed order placement with an unhandled `AttributeError` instead of a clean error | #47 |
| 16 | `numpy.float64` values (from pandas-derived `level_price`/`zone_low`) silently corrupted every `cloud_db.py` write via `psycopg2` under NumPy 2.x's changed `repr()` — every `save_signal_log()` call for MCX (and almost certainly NIFTY/BANKNIFTY/SENSEX too, same code path) was failing silently, logged only to `data/app.log`, never surfaced on the Dashboard | #85 |

Every row above has a unit test asserting the specific failure mode is closed.
None of them have been confirmed against a live market session.

## 2. NOT safe for LIVE capital — explicit no-go gates

- **Shoonya and Stocko cannot place a real order at all right now.** All 3 entry
  bots (`dynamic_sr_instant_trader.py`, `classic_sr_reversal_trader.py`,
  `srv2_momentum_reversal_strategy.py`) select strikes from **Upstox's** option
  chain only, regardless of which broker account is configured. Item #9 above
  makes this fail loudly instead of silently placing a wrong-contract order —
  but until each broker has its own strike-resolution path, **do not select
  Shoonya or Stocko as the trading account for any strategy.** Pure Upstox
  (no `broker_account_ids` selected) is the only path that has ever placed a
  real order.
- **Partial-fill auto square-off is Upstox-only.** `trading_engine.py`'s
  `_auto_reverse_filled_legs()` (closes an accidentally-unhedged leg if a
  multi-leg order partially fails) is keyed to Upstox's own fill-verification
  response shape. It does not — and currently cannot — trigger for
  Shoonya/Stocko. Another reason those brokers are gated above, not a
  separate risk once they're wired up.
- ~~Which script actually runs exit-monitoring on your VPS is unconfirmed.~~
  **RESOLVED 2026-09-19, verified directly on the VPS:**
  ```
  $ systemctl status engine_service.timer
       Loaded: loaded (...; disabled; preset: enabled)
       Active: inactive (dead)
  # Stopped 2026-09-07, never restarted since.

  $ crontab -l | grep trade_monitor
  45-59 3 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
  * 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
  # Every minute, 9:15 AM - ~4:29 PM IST, Mon-Fri — running.
  ```
  `trade_monitor.py` (crontab) is the real, active exit-monitoring path.
  `engine_service.timer` is confirmed dead. `deploy/README.md` has been
  updated to document the crontab setup and flag `engine_service.timer`'s
  section as historical-only — **do not re-enable it** without first
  removing the `trade_monitor.py` crontab entries (or vice versa); running
  both is the duplicate-exit scenario `ProcessLock` guards against but
  neither script needs to court.

## 3. Recommended rollout, in order

1. ~~Confirm the deployment question in §2 on the actual VPS.~~ Done.
2. Run PAPER mode through at least a few full trading sessions after this
   merge. Watch the Signal Log and Order Log daily — not just for errors, but
   for entries/exits that look right by eye.
3. Go LIVE only on Upstox, only with the smallest position size the platform
   allows (1 lot), regardless of account size.
4. Compare each LIVE fill's actual price/P&L against what PAPER mode would
   have shown for the same signal, for at least a week, before increasing size.
5. Re-visit Shoonya/Stocko only after their own option-chain/strike-resolution
   path is built and has been through the same PAPER-first process.

## 3b. Broker-side SL (Phase 2, Upstox-only, Naked + Credit Spread) — wired in, PAPER-tested, LIVE untested

🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा — Performance Report (2026-09-22) मध्ये सापडलेल्या SL
slippage चं Phase 1 (`trade_monitor.py`, ~20-सेकंद polling — PR #80) आधीच मर्ज झालेलं आहे. Phase 2
(resting SL-M order थेट Upstox कडेच — पूर्ण polling-मुक्त) आता entry/exit flow मध्ये पूर्णपणे wired
आहे — settings मध्ये (`Bot Dynamic SR Algo` पान → Exit Gate टॅब → "⚡ Broker-Side SL — Phase 2"
expander) **डीफॉल्ट बंद** असलेला per-strategy-per-symbol टॉगल (`broker_side_sl_enabled`).

**काय होतं (चालू केल्यावर):**
- `open_multi_leg_trade()` — entry confirm झाल्या-झाल्याच `_maybe_place_broker_side_sl()` कॉल होतो.
  Naked — trigger price गणिताने अचूक (entry_price ± sl_premium_points). Credit Spread — फक्त SHORT
  (SELL) leg वर, hedge leg entry किमतीलाच स्थिर आहे असं **worst-case/conservative** गृहीत धरून
  (वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — प्रत्यक्षात SL आवश्यकतेपेक्षा किंचित आधीच लागू शकतो,
  कधीच उशिरा नाही).
- `trading_mode != "LIVE"` (PAPER/LIVE_PAPER चा PAPER भाग) — **खरा order कधीच जात नाही**, फक्त
  trigger price ची गणना होऊन `monitor.log` मध्ये लॉग होते (`legs_json.sl_order_id="DRYRUN"`) —
  वापरकर्त्याने स्पष्टपणे मागितलेली "आधी PAPER मध्ये test करूया" ही सुरक्षा-पायरी.
- `manage_open_trades()` (SL/TSL/Target/Next-Level/EOD/OI-Reversal/Carry-Forward/broker-reconciliation
  — सर्व exit-paths) आणि `close_trade_manually()` — trade कुठल्याही कारणाने बंद होताना
  `_maybe_cancel_broker_side_sl()` आपोआप कॉल होऊन pending SL-M order रद्द करतो (हे चुकलं तर जुना
  order नंतर चुकून trigger होऊन unwanted position उघडू शकतो — या फीचरमधला सर्वात मोठा धोका).
- फक्त 3 sources साठी लागू (Spot%+Premium-Points settings-चालित SL वापरणारे — बाकीच्यांना (MANUAL/
  credit_spread_auto_trader/इ.) हे feature अजिबात लागू नाही, जुनंच वर्तन): `dynamic_sr_instant`
  ("1m_instant" settings), `classic_sr_reversal`, `srv2_momentum_reversal` ("15m_dynamic_sr" settings).
- Scope फक्त Upstox (`adapter is None` किंवा `isinstance(adapter, UpstoxBrokerAdapter)`) —
  Shoonya/Stocko/Fyers `supports_broker_side_stop_loss()` कडून आपोआप `False` मिळत असल्याने
  पूर्णपणे अस्पर्शित राहतात.

**अजून व्हायचं आहे (LIVE करण्याआधी अनिवार्य):**
- ⚠️ **कधीही खरा LIVE order अजून टाकलेला नाही** — फक्त `pytest tests/` (unit + integration, mocked
  Upstox API) आणि PAPER dry-run लॉग वाचून पडताळणी. प्रत्यक्ष VPS वर PAPER mode मध्ये काही दिवस चालवून
  `monitor.log` मधले dry-run trigger prices वापरकर्त्याने डोळ्यांनी पडताळल्याशिवाय **कुठल्याही
  symbol/strategy साठी हा टॉगल LIVE मोड मध्ये चालू करू नये.**
- टॉगल चालू करण्याआधी prod Supabase मध्ये `broker_side_sl_enabled` column/field नव्याने ADD होत नाही
  (JSONB मध्ये आपोआप मर्ज होतं) — वेगळं migration लागत नाही, पण जुनं cached settings-दाखवणं (Dashboard
  उघडाच ठेवलेलं असेल तर) refresh करूनच नवीन टॉगल दिसेल.

## 4. Known, deliberately out-of-scope items (not bugs, just incomplete)

- Full per-broker option-chain fetching for Shoonya/Stocko (§2).
- Shoonya/Stocko partial-fill auto-reversal (§2).
- `fetch_ltp_map`/option chain/candles for Stocko are stubbed (return
  empty/`None`) — no public endpoint found in the Stocko API PDF provided.
  PAPER mode is explicitly unavailable on Stocko for this reason.

## 5. MCX Futures Trader (CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER) — crontab already active (PAPER), rollout order verification incomplete

A separate strategy from everything above — direct futures (no options), its
own page (`page_mcx_futures.py`), its own execution bot (`mcx_futures_trader.py`,
PR #76), its own zones refresh (`refresh_market_zones_mcx.py`, PR #76). Reuses
`trading_engine.open_multi_leg_trade()`/`manage_open_trades()` unmodified (a
single futures leg passed through the same "legs" path options use), so the
engine-level risk gates in §1/§2 above (kill switch, margin check, partial-fill
reversal — Upstox-only per §2) already apply to it. Automated PAPER *is* now
running (crontab confirmed live, see the 2026-09-22 note below) — what's
still unverified before trusting its output or considering LIVE:

- **Real instrument data never independently confirmed.**
  `resolve_mcx_futures_instruments.py` (PR #73) exists and is read-only-safe,
  but nobody has separately confirmed sane `instrument_key`/`lot_size`/
  `tick_size` output for all 5 commodities by eye — `mcx_futures_trader.py`
  calls it every cycle regardless, so it's implicitly exercised, but a
  standalone sanity check hasn't been done.
- **Dynamic S/R data status unconfirmed for symbols other than CRUDEOIL.**
  `refresh_market_zones_mcx.py`'s output hasn't been spot-checked against a
  real chart for any commodity — if `cloud_db.market_zones` has zero rows for
  a symbol, `mcx_futures_trader.py` just finds no ACTIVE levels and does
  nothing (safe, but useless) rather than erroring.
- **Shoonya/Stocko not evaluated for MCX at all.** `broker_account_ids`
  routing works mechanically (same `execute_trade_on_all_accounts()` path),
  but nobody has checked whether Shoonya/Stocko can even place an MCX order —
  treat this exactly like §2's NIFTY gate: Upstox-only until proven otherwise.

🎓 **2026-09-22 update — found live on the VPS, out of the documented order below.**
`crontab -l` on the VPS shows all 3 MCX lines from `deploy/README.md` already
active (entry bot every minute during MCX hours, nightly
`refresh_market_zones_mcx.py`) — added before steps 1-3 below were confirmed
done in order. Verified in this session: CRUDEOIL's `symbol_enabled` was off
until now (so `mcx_futures_trader.py` was returning early every cron tick,
writing nothing to `signal_log` — this, not a bug, is why the Dashboard's
Level Hit Log looked empty even though cron was clearly running), and
CRUDEOIL's Trading Mode is confirmed **PAPER** (user-checked, not LIVE — no
real capital at risk right now). Steps 1-2 below (resolver/zones sanity
checks) were **not independently confirmed** before the crontab went in —
worth spot-checking now that the loop is actually live, per step 3.

**Rollout order (MCX-specific, mirrors §3 above but starts further back):**
1. Run `resolve_mcx_futures_instruments.py` on the VPS with a real token —
   confirm sane `instrument_key`/`lot_size`/`tick_size`/`expiry` for all 5
   commodities. **Not independently confirmed — worth spot-checking now.**
2. Run `refresh_market_zones_mcx.py` once by hand — spot-check the saved
   30M/60M levels against a real chart (e.g. TradingView) for 1-2 commodities.
   **Not independently confirmed — worth spot-checking now.**
3. ✅ Crontab is running `mcx_futures_trader.py` automatically now (PAPER) —
   watch the Dashboard's Level Hit Log/Order Log for a few cron cycles and
   confirm entries look sane (no repeated errors in `mcx_futures.log`).
4. Crontab entries from `deploy/README.md` are live (see above) — for any
   *other* MCX symbol before enabling `symbol_enabled`, still do steps 1-2
   by hand first (this update only covers CRUDEOIL's current state).
5. Run PAPER mode through several full MCX sessions before considering LIVE —
   note MCX's session runs to ~11:30/11:55 PM IST, much longer than NSE's, so
   "a few sessions" takes real calendar time to accumulate.
6. Go LIVE only on Upstox, only 1 lot, same discipline as §3 above — this is
   a brand-new, unverified strategy, not a variant of an already-proven one.
