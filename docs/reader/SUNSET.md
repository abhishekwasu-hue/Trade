# Trade sunset checklist — prepare now, execute only on Abhi's word

Owner decision (Abhi): everything that matters moves to ATP. ATP runs in shadow beside Trade; when Abhi switches, Trade becomes a
read-only archive and the VPS is shut down. **Nothing in this file is run by a session.** Every step on the VPS, every LIVE line, and every
secret is Abhi's.

**Source of this list.** It was built from the repo: `deploy/*.service|*.timer`, the cron lines in `deploy/README.md`, the installer
`scripts/install_engine_schedule.sh` (one-bot mode), and the setting names that the code reads. The VPS itself was not read. Before
executing, Abhi confirms against the VPS:
- `crontab -l`
- `systemctl list-units --type=service,timer --all | grep -E "vision|position|streamlit|upstox|cloudflared|engine"`
- `cut -d= -f1 /root/Trade/.env` (names only)

Lines tagged `#one-bot-off#` are already commented out.

The "ATP replacement" column is a **proposal**; Abhi decides each one.

Switch-off convention: a cron line is commented out with the prefix `#sunset-off# ` (reversible, never deleted); a unit is stopped with
`systemctl disable --now <unit>`.

## 1. Crons (`crontab -l` on the VPS)

| What runs (script) | Purpose | ATP replacement (proposal) | Switch-off step |
|---|---|---|---|
| `trade_monitor.py` (every minute, market hours) | PAPER exits: SL / target / EOD for open positions | ATP paper exit monitor | **Last of the trading lines**: only after every open position is closed or handed over |
| `scripts/engine_signal_run.py --engine decision3` (`# one-bot-engine`, 15M closes) + warm-up (`# one-bot-engine-warm`) | The chart reader's live setups (the one bot) | ATP reader + signal, in shadow first | `#sunset-off#` once ATP is live |
| `srv2_momentum_reversal_strategy.py` (`# one-bot-srv2`) | PAPER bot that trades the reader's setups | ATP paper bot | Stop new entries first; exits stay until flat |
| `scripts/level_gate_preopen.py` (`# one-bot-preopen`) | Level bots' pre-open gate | Retire (level bots are rebuilt in ATP) | `#sunset-off#` |
| `classic_sr_reversal_trader.py`, `dynamic_sr_instant_trader.py`, `mcx_futures_trader.py` (entry / exit), `oi_signal_auto_trader.py`, `credit_spread_auto_trader.py`, `oi_greeks_vix_strategy.py` | Frozen engines (PAPER; any LIVE line is Abhi's) | Retire | Exits stay until each bot is flat; LIVE lines only by Abhi |
| `refresh_market_structure.py` (+ `--brief`, `_intraday`), `refresh_market_zones.py` (+ `_intraday`, `_mcx`), `refresh_dynamic_sr_1m.py`, `refresh_dynamic_sr_5m.py` | Feeds for the frozen engines and the dashboard | Retire | `#sunset-off#` after the engines stop |
| `collect_index_futures_volume.py` | FUT volume (the reader's volume source) | ATP data collector | Only after ATP collects the same series |
| `iv_snapshot_collector.py`, `oi_snapshot_collector.py` | IV / OI snapshots | Retire (or ATP data, Abhi) | `#sunset-off#` |
| `check_vix_spike_halt.py` | VIX-spike halt flag | ATP risk guard (or retire, Abhi) | With the trading lines |
| `mcx_market_readiness_check.py` | MCX readiness | Retire | `#sunset-off#` |
| `eod_trade_summary.py --market nse / mcx`, `scripts/paper_daily_summary.py` | End-of-day reports | ATP reports | After the last trading day on Trade |
| `-m vision.worker --loop-seconds 55`, `-m vision.outcome` | Vision on PAPER signals; outcome tracking | ATP Vision (Abhi) | With the reader |
| `run_visual_audit.py` | Daily visual audit (Vision, paid) | Retire (or ATP, Abhi) | `#sunset-off#` |
| `scripts/vision_archive.py` (daily) | Vision log archive | Retire after the final export | After the final export (§5) |
| `trigger_upstox_token_request.py` | Daily Upstox token request | ATP broker / data auth | Only after ATP has its own token flow |

## 2. systemd units

| Unit | Purpose | ATP replacement (proposal) | Switch-off step |
|---|---|---|---|
| `vision_worker.service` | Vision worker (PAPER signals) | ATP Vision (Abhi) | `systemctl disable --now vision_worker.service` |
| `vision_telegram.service` | Telegram approve / reject buttons (long-polling) | ATP approvals | `systemctl disable --now vision_telegram.service` |
| `streamlit_dashboard.service` | The dashboard (port 8501) | ATP UI | Last, after the final exports (read-only use until then) |
| `position_stream_monitor.service`, `position_stream_monitor_mcx.service` | Real-time SL / target stream for positions | ATP exit monitor / retire | With `trade_monitor.py`, after flat |
| `upstox_token_webhook.service` + `cloudflared_upstox_webhook.service` | Token webhook + its HTTPS tunnel | ATP broker auth | After ATP's token flow works |
| `engine_service.timer` / `.service` | Old exit monitor — already inactive (deploy/README) | Retire | Confirm `disabled`; remove the unit file |

## 3. Telegram

| Bot / chat | Used by | Step |
|---|---|---|
| One bot (`TELEGRAM_BOT_TOKEN`) posting to one chat (`TELEGRAM_CHAT_ID`) | Signals, EOD summaries, health, Vision photos and buttons | Post a final "Trade switched off — ATP from <date>" note, then stop the senders above. Abhi decides whether ATP reuses the bot or revokes the token (@BotFather) |
| Approvers (`TELEGRAM_APPROVER_IDS`) | Vision buttons | Move to ATP with the approvals |

## 4. Scheduled exports (VPS → private trade-data)

| Export | Writes | Step |
|---|---|---|
| `scripts/elliott_e0_vps.sh` (rerunnable) | `banknifty/`, `nse_fo_bhavcopy/`, `upstox/`, `major_levels_candles/`, `probes/` | Final run, then off |
| Live candle / FUT exports (the writer is not in this repo's code — Abhi confirms which VPS job writes it) | `live_export/<date>/` | Final run on the last day, then off |
| `run_visual_audit.py` | `visual_audit/` | Off with the audit |
| Push access: SSH deploy key (alias `github-trade-data`) | — | Abhi removes the deploy key from trade-data after the last push |

## 5. Setting names in use (`.env` — names only, never values)

Read by the code that runs on the VPS:
- **Database:** `SUPABASE_DB_URL`
- **Broker / market data:**
  - Upstox: `UPSTOX_ACCESS_TOKEN`, `UPSTOX_CLIENT_ID`, `UPSTOX_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEY`
  - Shoonya: `SHOONYA_PASSWORD`, `SHOONYA_API_SECRET`, `SHOONYA_TOTP_SECRET`
  - Stocko: `STOCKO_BASE_URL`
- **Telegram:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_APPROVER_IDS`
- **Vision:**
  - `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`
  - `VISION_CALLBACK_SECRET`, `VISION_DB_PATH`, `VISION_IMAGE_DIR`
  - `VISION_SIGNAL_MODEL`, `VISION_SIGNAL_EFFORT`, `VISION_SIGNAL_THINKING`, `VISION_SIGNAL_MAX_TOKENS`, `VISION_V4_MAX_TOKENS`
  - `VISUAL_AUDIT_*`
- **Paper / engine stores:** `PAPER_JOURNAL_DB`, `PAPER_DATA_DIR`, `PAPER_CONFIG`, `PAPER_LOCAL_CONFIG`, `ENGINE_SIGNAL_DB`, `ENGINE_SIGNAL_ENGINE`, `ENGINE3_CACHE_DIR`
- **Ops:** `HEALTHCHECK_PING_URL` (+ `HEALTHCHECK_PING_URL_<SCRIPT>`), `APP_PASSWORD`, `TRADE_DATA_DIR`

Step at the end: Abhi revokes or rotates every credential above that ATP does not reuse, then deletes `/root/Trade/.env` with the VPS.

## 6. Order on the day (Abhi)

1. ATP has run in shadow beside Trade, and Abhi switches.
2. Stop new entries: the `#sunset-off#` prefix on the entry lines (§1), then `vision_*`.
3. Wait until every PAPER position is flat (exits keep running). LIVE: Abhi only.
4. Stop the exits, the stream monitors and the collectors.
5. Final exports to trade-data (§4, and the VPS-only items in EXPORT_MANIFEST.md: paper journal, Vision logs, engine signal store). Re-run
   `scripts/reader_export_manifest.py` and check the checksums on the ATP side.
6. Stop the remaining units (§2), the dashboard last.
7. Telegram final note; credentials revoked (§3, §5); trade-data deploy key removed.
8. **Archive:** replace the top of `README.md` with the text below, merge it, set the GitHub repo to archived (read-only).
9. Shut down the VPS.

Archive README text (§8):

> **Archived.** This repository is read-only. The Chart Reader and everything in use moved to **ATP**; see ATP for the current code, the
> ported reader layers (`docs/reader/STABLE.md` lists the tags they were ported from) and the data (`docs/reader/EXPORT_MANIFEST.md`).
