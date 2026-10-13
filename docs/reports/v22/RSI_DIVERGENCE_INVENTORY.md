# RSI / divergence — inventory (K-RSI spec item 0)

Design `docs/design/CHART_READER_AGENT.md` §3: **RSI divergence owner = `rsi2`**. Everything else below is frozen (§4): no edits, no new
work, no second implementation. Line numbers are on branch `claude/rsi-divergence` (base `origin/main` 1eeb5e4).

## Owner (facts layer)

| Where | What | Status |
|---|---|---|
| `rsi2/engine.py:27` `rsi_segmented` | Wilder RSI per data segment (holdout gap ⇒ new segment), via `chart_reader.evidence.rsi` | **owner** — reused by K-RSI |
| `rsi2/engine.py:37` `RSI` (`_detect` :150, `known`, `classify` :193), `special` :241, `cascade` :290, `mapping` | थर 6: pivot-based divergence on swings2 pivots with min price / RSI differences, line / price clear, grade; Cardwell rsi_range | **owner, unchanged** (API kept: `facts/dossier.py:677` calls `RSI(lg, struct).known(t)`) |
| `rsi2/engine.py:383` `Divergence` (+ `div_frame`, `div_label`) | **K-RSI (new, KB K10.4 pending Abhi):** consecutive same-degree swings2 pivots, wick prices, RSI extreme ± N bars, equal counts, no minimum RSI difference, bar window + cap log, forming / confirmed, area facts, explicit absence | **owner, new** |
| `rsi2/charts.py` `div_figure`, `div_chart`, `div_rows`, `merge_degrees` | K-RSI verification plot (price pane + RSI pane 70 / 30 + table) | owner (display) |
| `rsi2/settings.py` `div_*` | K-RSI settings (defaults per spec) | owner settings store |
| `bot_view.py` `rsi_div_overlay` · `tradingview_chart.py` `rsi_divs` · `page_dashboard.py` "Show RSI divergences" | dashboard display of the owner's output only (5M / 15M / 1H) | display only, never a gate |

## Other implementations — frozen (no edits, no second implementation)

| Where | What | Used by | Status |
|---|---|---|---|
| `chart_reader/evidence.py:133` `rsi` | Wilder RSI (the function rsi2 imports) | rsi2, chart_reader | shared helper (kept; rsi2 calls it) |
| `chart_reader/evidence.py:167` `divergence` | DV [K10.2]: regular at C-end / hidden in pullback / against at impulse end, min RSI 3 pts, scored (+5 / +3 / −3) | `chart_reader/evaluate.py:274` (old grading) | frozen (design §3: retire) |
| `elliott/trigger.py:84` `_rsi`, `:168` `_div_ok` | EWM RSI + divergence flag for the Elliott reversal score | `elliott/reversal.py:161` ("div" component) | frozen |
| `correction/reader.py:194` `_rsi`, `:248` | EWM RSI + "RSI divergence (C-end वर regular)" row | correction annotation reader | frozen (§4 proposed) |
| `signals.py:8` `calculate_rsi` | Wilder-style RSI series used by bots / dashboard RSI pane | bots, backtests, dashboard | shared (not a divergence owner) |
| `signals.py:497` `check_rsi_signal` | OB / OS or "simple divergence" (two halves of a 20-bar window) | `signals.py:608` `check_price_action_strategy`, `backtest.py` | frozen |
| `signals.py:940` `rsi_momentum_and_divergence` | close-trend vs RSI-trend over 20 bars | `entry_engine.py:154`, `page_dashboard.py:2058` (direction engine), `gap_fill_reversal_strategy.py:28` (import) | frozen |
| `signals.py:1069` `check_pattern_rsi_gate` | RSI range gate with a candle pattern | `backtest.py:194` | frozen (gate, not divergence) |
| `nifty_futures_swing_rsi_st.py:32`, `:40` | bullish / bearish divergence over a 4-bar lookback, RSI(5) | that strategy | frozen |
| `backtest.py:140`, `:309`, `:586` | RSI series for the backtests (via `signals`) | backtests | frozen |
| `entry_engine.py:104`, `:154` | RSI + `rsi_momentum_and_divergence` | entry engine | frozen |
| `gap_fill_reversal_strategy.py:120`, `:191` | RSI 5M / 15M confirmation | gap-fill strategy | frozen |
| `shared_context.py:209` | text only ("RSI Oversold / Overbought / Divergence") | — | no logic |
| `page_dashboard.py:1239`, `:1457`, `:2058` | dashboard RSI pane (`calculate_rsi`), direction-engine divergence display | dashboard | unchanged (the new toggle swaps the main chart's RSI pane to the owner's RSI only while it is ON) |
| `mtf/adapter.py:102`, `mtf/charts.py:640` | consumes `rsi2.RSI` / layer output (not an implementation) | mtf | consumer |
| `dynamic_sr_instant_trader.py:166`, `classic_sr_reversal_trader.py:74`, `srv2_momentum_reversal_strategy.py`, `mcx_futures_trader.py`, `sr_bot_level_backtest.py:140` | RSI threshold gates of the live bots (not divergence) | bots | untouched (PAPER bots; no change) |
