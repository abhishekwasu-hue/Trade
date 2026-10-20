# Trade sunset checklist — documents only; executed only when Abhi says so

## Owner rule (Abhi) — read first

- **Never shut down, archived or disabled automatically:** the Trade session, the Trade repo and the Trade VPS. No automation does it:
  no condition, no "shadow run passed", no schedule, no session.
- **Switch-over and sunset happen only when Abhi says so explicitly**, in his own words, at a time he chooses. Until then Trade keeps
  running exactly as now: the PAPER bot, the crons and Telegram.
- **This file and the one command block in §7 are preparation only.** No session runs them, and nobody schedules them.
- **Nothing in Trade is removed or weakened because a feature now exists in ATP.** Both run side by side for as long as Abhi wants.

Plan context: everything that matters is ported to ATP, and ATP runs beside Trade. Only on Abhi's explicit word does Trade become a
read-only archive and the VPS shut down. Every step on the VPS, every LIVE line, and every secret is Abhi's.

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
| `srv2_momentum_reversal_strategy.py` (`# one-bot-srv2`) | PAPER bot that trades the reader's setups (also manages its own positions) | ATP paper bot | New entries off by the dashboard setting (`symbol_enabled` / `signal_symbols`); the cron line stays until flat |
| `scripts/level_gate_preopen.py` (`# one-bot-preopen`) | The one bot's daily pre-open status message (bot state, engine store freshness) | ATP health message | `#sunset-off#` with the reader |
| `classic_sr_reversal_trader.py`, `dynamic_sr_instant_trader.py`, `mcx_futures_trader.py` (entry / exit), `oi_signal_auto_trader.py`, `credit_spread_auto_trader.py`, `oi_greeks_vix_strategy.py` | Frozen engines (PAPER; any LIVE line is Abhi's) | Retire | Exits stay until each bot is flat; LIVE lines only by Abhi |
| `refresh_market_structure.py` (+ `--brief`, `_intraday`), `refresh_market_zones.py` (+ `_intraday`, `_mcx`), `refresh_dynamic_sr_1m.py`, `refresh_dynamic_sr_5m.py` | Feeds for the frozen engines and the dashboard | Retire | `#sunset-off#` after the engines stop |
| `collect_index_futures_volume.py` | FUT volume (the reader's volume source) | ATP data collector | Only after ATP collects the same series |
| `iv_snapshot_collector.py`, `oi_snapshot_collector.py` | IV / OI snapshots | Retire (or ATP data, Abhi) | `#sunset-off#` |
| `check_vix_spike_halt.py` | VIX-spike halt flag | ATP risk guard (or retire, Abhi) | With the trading lines |
| `mcx_market_readiness_check.py` | MCX readiness | Retire | `#sunset-off#` |
| `eod_trade_summary.py --market nse / mcx`; `scripts/paper_daily_summary.py` (its cron line is not in the repo docs — confirm on the VPS) | End-of-day reports | ATP reports | After the last trading day on Trade |
| `-m vision.worker --loop-seconds 55`, `-m vision.outcome` | Vision on PAPER signals; outcome tracking | ATP Vision (Abhi) | With the reader |
| `run_visual_audit.py` | Daily visual audit (Vision, paid) | Retire (or ATP, Abhi) | `#sunset-off#` |
| `scripts/vision_archive.py` (daily) | Vision log archive — pushes to trade-data `visual_audit/YYYY-MM/` | Retire after the final export | After the final export (§6 step 5) |
| `trigger_upstox_token_request.py` | Daily Upstox token request | ATP broker / data auth | Only after ATP has its own token flow |

## 1b. GitHub Actions (this repo, `.github/workflows/`)

| Workflow | Schedule | Purpose | ATP replacement (proposal) | Switch-off step |
|---|---|---|---|---|
| `nifty_1min_daily_update.yml` | weekdays 15:45 IST | NIFTY spot 1m → Supabase `nifty_1min_ohlc` (the live spot history) | **ATP spot-history feed — must run in ATP before this stops** | Disable the workflow (GitHub → Actions) |
| `eod_market_report.yml` | weekdays 16:00 IST | EOD report to Telegram; commits PDFs to `data/reports/` in this public repo (a scheduled export) | ATP reports | Disable |
| `check_token_freshness.yml` | weekdays 08:45 IST | Token freshness alert to Telegram | ATP broker auth health | Disable |
| `run_algo.yml` | weekdays 09:05 IST | Runs `app.py` (Stoxkart credentials) | Retire (Abhi) | Disable |
| `ci.yml` | on push / PR | Tests | — | Stays until the archive |
| `dynamic_sr_instant_trader`, `srv2_momentum_reversal_strategy`, `market_structure_refresh`, `market_zones_refresh`, `oi_snapshot_collector`, `migrate_nifty_1min_to_supabase`, `test_supabase_connection`, `trigger_upstox_token_request`, `visual_audit` | manual only | — | — | Disable |

Repo Actions secrets (names only) to delete after the workflows are disabled:
- `SUPABASE_DB_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `UPSTOX_CLIENT_ID`, `UPSTOX_CLIENT_SECRET`
- `STOXKART_API_KEY`, `STOXKART_CLIENT_ID`, `STOXKART_PASSWORD`, `STOXKART_SECRET_KEY`
- `ANTHROPIC_API_KEY`, `VISUAL_AUDIT_MODEL`

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
| One bot (`TELEGRAM_BOT_TOKEN`) posting to one chat (`TELEGRAM_CHAT_ID`) | VPS: signals, EOD summaries, health, Vision photos and buttons, review packs (`scripts/send_review_to_telegram.py`). GitHub Actions: `eod_market_report`, `check_token_freshness`, `run_algo` (repo secrets) | Post a final "Trade switched off — ATP from <date>" note, then stop the senders above. Abhi decides whether ATP reuses the bot or revokes the token (@BotFather) |
| Approvers (`TELEGRAM_APPROVER_IDS`) | Vision buttons | Move to ATP with the approvals |

## 4. Exports to trade-data and to this repo

| Export | Writes | Kind | Step |
|---|---|---|---|
| `scripts/vision_archive.py` (daily cron) | trade-data `visual_audit/YYYY-MM/` | scheduled | Final run, then off |
| `eod_market_report.yml` (GitHub Actions) | this repo `data/reports/` (PDFs) | scheduled | Disable (§1b) |
| Live candle / FUT exports (the writer is not in this repo's code — Abhi confirms which VPS job writes it) | trade-data `live_export/<date>/` | VPS | Final run on the last day, then off |
| `scripts/elliott_e0_vps.sh` | `banknifty/`, `nse_fo_bhavcopy/`, `upstox/`, `major_levels_candles/`, `probes/` | one-off, run by hand | Nothing to stop |
| `research/backtest_review_run.py`, `research/golden_gallery.py`, `scripts/reader2_gallery_export.py`, `scripts/send_review_to_telegram.py` | the VPS clone of trade-data: `backtest_review/`, `golden_gallery/`, `reader2_gallery/labels/` (+ Telegram) | on demand | Push the VPS clone once (EXPORT_MANIFEST external section) |
| Push access: SSH deploy key (alias `github-trade-data`) | — | — | Abhi removes the deploy key from trade-data after the last push |

## 5. Setting names in use (names only, never values)

**`/root/Trade/.env`**, as read by the code that runs on the VPS:
- **Database:** `SUPABASE_DB_URL`
- **Broker / market data:**
  - Upstox: `UPSTOX_ACCESS_TOKEN`, `UPSTOX_CLIENT_ID`, `UPSTOX_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEY`
  - Shoonya: `SHOONYA_PASSWORD`, `SHOONYA_API_SECRET`
  - Stocko: `STOCKO_BASE_URL`
- **Telegram:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_APPROVER_IDS`, `REVIEW_TG_SENT_PATH`
- **Vision:**
  - `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`, `VISION_CALLBACK_SECRET`, `VISION_DB_PATH`, `VISION_IMAGE_DIR`, `VISION_TEST_DIR`
  - `VISION_SIGNAL_MODEL` / `_EFFORT` / `_THINKING` / `_MAX_TOKENS`, `VISION_LEVEL_MODEL` / `_EFFORT` / `_THINKING`, `VISION_V4_MAX_TOKENS`
  - `VISION_PRICE_IN`, `VISION_PRICE_OUT`, `VISION_PRICE_CACHE_READ`, `VISUAL_AUDIT_*`
- **Paper / engine stores:** `PAPER_JOURNAL_DB`, `PAPER_DATA_DIR`, `PAPER_CONFIG`, `PAPER_LOCAL_CONFIG`, `ENGINE_SIGNAL_DB`, `ENGINE_SIGNAL_ENGINE`, `ENGINE3_CACHE_DIR`, `SIMPLE_CORE_EXEC_PATH`, `TRADE_INSTRUMENT`
- **Data / review paths:** `TRADE_DATA`, `TRADE_DATA_DIR`, `BACKTEST_REVIEW_DIR`, `GOLDEN_GALLERY_DIR`, `READER2_GALLERY_STORE`, `READER2_GALLERY_LABELS`, `READER2_GALLERY_MANIFEST`, `READER2_GALLERY_SEEDS`, `CM_CACHE`
- **Ops:** `HEALTHCHECK_PING_URL` (+ `HEALTHCHECK_PING_URL_<SCRIPT>`), `APP_PASSWORD`

**Credential stores outside `.env`** (revoke or rotate each one):
- `.streamlit/secrets.toml`: `[gdrive] service_account_json` (a Google service account), `[proxy] url`, `app_password`, `[upstox] access_token`
- `data/notification_config.json`: database URL, Telegram, and a `TOKEN_ENCRYPTION_KEY` fallback
- the cloudflared tunnel's config, and the Upstox app's webhook URL that points at the tunnel
- GitHub Actions secrets (§1b) and the trade-data deploy key (§4)

**Supabase (the hosted database):** a final dump of the tables named in EXPORT_MANIFEST (external section), then pause or delete the
project — Abhi.

**VPS state files to export first:** `data/one_bot_before.json` (needed to revert one-bot mode) and `data/review_tg_sent.json`.

Step at the end: Abhi revokes or rotates every credential above that ATP does not reuse, then deletes `/root/Trade/.env` with the VPS.

## 6. Order on the day — only after Abhi says so explicitly, in his own words

1. Abhi's explicit word that today Trade switches off. A shadow result, a date or a condition is never that word.
2. Stop new entries: in the dashboard, switch every bot's entries off (`symbol_enabled` off, `signal_symbols` empty); turn off the reader / pre-open / Vision cron lines and the Vision units. The bots' own cron lines stay, so they keep managing their positions.
3. Wait until every PAPER position is flat (exits keep running). LIVE: Abhi only.
4. Stop the bots' cron lines, the exits, the stream monitors and the collectors. Disable the GitHub Actions workflows (§1b) — the spot-history feed only once ATP runs its own.
5. Final exports to trade-data (§4, and the VPS-only items in EXPORT_MANIFEST.md: paper journal, Vision logs, engine signal store). Re-run
   `scripts/reader_export_manifest.py` and check the checksums on the ATP side.
6. Stop the remaining units (§2), the dashboard last.
7. Telegram final note; credentials revoked (§3, §5); trade-data deploy key removed.
8. **Archive:** replace the top of `README.md` with the text below, merge it, set the GitHub repo to archived (read-only).
9. Shut down the VPS.

Archive README text (§8):

> **Archived.** This repository is read-only. The Chart Reader and everything in use moved to **ATP**; see ATP for the current code, the
> ported reader layers (`docs/reader/STABLE.md` lists the tags they were ported from) and the data (`docs/reader/EXPORT_MANIFEST.md`).

## 7. The one command block (prepared — never run by a session, never scheduled)

For Abhi to paste on the VPS himself, only after his explicit word (§6 step 1). It asks him to type the confirmations; it never touches
a LIVE line; every cron line it turns off is commented with `#sunset-off# ` (reversible: `crontab -l | sed 's|^#sunset-off# ||' |
crontab -`). The dashboard entries switch, the GitHub Actions workflows and steps 5 and 7–9 (final exports, credentials, archive, VPS off) stay manual.

```bash
# Trade sunset — Abhi only, by hand, after his explicit decision. Never scheduled, never run by a session.
set -euo pipefail
cd /root/Trade
read -r -p "Type exactly: ABHI SWITCHES TRADE OFF > " ok; [ "$ok" = "ABHI SWITCHES TRADE OFF" ] || { echo "stopped — nothing changed"; exit 1; }
crontab -l > "/root/crontab_before_sunset_$(date +%F_%H%M).txt"
LIVE="--mode[=[:space:]]+[\"']?LIVE([^A-Za-z0-9_]|$)"
off() {  # comment out the active, non-LIVE cron lines that match $1
  crontab -l | awk -v pat="$1" -v live="$LIVE" '/^[[:space:]]*#/ {print; next} ($0 ~ pat && $0 !~ live) {print "#sunset-off# " $0; next} {print}' | crontab -
}
# §6 step 2: new entries off (exits stay)
read -r -p "Dashboard: every bot's entries switched off (symbol_enabled off, signal_symbols empty)? Type ENTRIES-OFF > " e; [ "$e" = "ENTRIES-OFF" ] || { echo "stopped — nothing changed"; exit 1; }
off 'engine_signal_run\.py|level_gate_preopen\.py|vision\.worker|vision\.outcome|run_visual_audit\.py'
systemctl disable --now vision_worker.service vision_telegram.service || true
# §6 step 3: wait until every PAPER position is flat
read -r -p "All PAPER positions flat? Type FLAT > " flat; [ "$flat" = "FLAT" ] || { echo "stopped after entries-off; exits still running"; exit 1; }
# §6 step 4: exits, monitors, collectors off (LIVE lines untouched)
off 'srv2_momentum_reversal_strategy\.py|classic_sr_reversal_trader\.py|dynamic_sr_instant_trader\.py|oi_signal_auto_trader\.py|credit_spread_auto_trader\.py|oi_greeks_vix_strategy\.py|trade_monitor\.py|mcx_futures_trader\.py|refresh_|_collector\.py|collect_index_futures_volume\.py|check_vix_spike_halt\.py|mcx_market_readiness_check\.py|eod_trade_summary\.py|paper_daily_summary\.py|vision_archive\.py|trigger_upstox_token_request\.py'
systemctl disable --now position_stream_monitor.service position_stream_monitor_mcx.service || true
echo "Now by hand: disable the GitHub Actions workflows (§1b); final exports (§6 step 5) incl. data/one_bot_before.json. Then press Enter."; read -r _
# §6 step 6: remaining units, the dashboard last
systemctl disable --now upstox_token_webhook.service cloudflared_upstox_webhook.service engine_service.timer || true
systemctl disable --now streamlit_dashboard.service || true
crontab -l | grep -v '^[[:space:]]*#' || echo "no active cron lines left (LIVE lines, if any, were never touched — Abhi decides them)"
```

