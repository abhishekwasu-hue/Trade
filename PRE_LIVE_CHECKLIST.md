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
- **Which script actually runs exit-monitoring on your VPS is unconfirmed.**
  `engine_service.py` has a committed systemd timer
  (`deploy/engine_service.service`) and `deploy/README.md` documents that
  setup. But `trade_monitor.py`'s own docstring says it's meant to run via
  **crontab** (not systemd) and describes itself as "the one, sole
  authoritative place" for exit logic — implying a past migration the deploy
  docs were never updated for. Both are now protected against running
  concurrently (`ProcessLock`), so nothing breaks either way — but if the
  wrong one is actually live, or both are, that needs to be known, not
  assumed. **Resolve on the VPS before going live:**
  ```
  systemctl status engine_service.timer
  crontab -l | grep trade_monitor
  ```
  Whichever one is confirmed live, consider removing the other's deployment
  path entirely rather than leaving two dormant copies of exit logic in the
  repo.

## 3. Recommended rollout, in order

1. Confirm the deployment question in §2 on the actual VPS.
2. Run PAPER mode through at least a few full trading sessions after this
   merge. Watch the Signal Log and Order Log daily — not just for errors, but
   for entries/exits that look right by eye.
3. Go LIVE only on Upstox, only with the smallest position size the platform
   allows (1 lot), regardless of account size.
4. Compare each LIVE fill's actual price/P&L against what PAPER mode would
   have shown for the same signal, for at least a week, before increasing size.
5. Re-visit Shoonya/Stocko only after their own option-chain/strike-resolution
   path is built and has been through the same PAPER-first process.

## 4. Known, deliberately out-of-scope items (not bugs, just incomplete)

- Full per-broker option-chain fetching for Shoonya/Stocko (§2).
- Shoonya/Stocko partial-fill auto-reversal (§2).
- `fetch_ltp_map`/option chain/candles for Stocko are stubbed (return
  empty/`None`) — no public endpoint found in the Stocko API PDF provided.
  PAPER mode is explicitly unavailable on Stocko for this reason.
