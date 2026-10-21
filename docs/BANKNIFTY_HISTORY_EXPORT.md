# BANKNIFTY history export (VPS → private trade-data)

**Why:** the BANKNIFTY Chart Reader replay (trade-data `review/replay_banknifty_6m/04a8b40/`) could only use 13 Jul – 13 Oct, and had
full inputs for only 9 sessions: in trade-data, near-month FUT 5M volume starts 30 Sep and spot 5M / 1m start 15 Sep (1m ends 12 Oct).
This copies the **older BANKNIFTY candles the VPS already has on disk** into trade-data, so the replay can use more history.

## Abhi: the ONE command (VPS, after the market close)

The script arrives with the normal deploy (`bash scripts/deploy_one_bot.sh`). No separate `git pull` is needed. Run it on any day
**after 16:30 IST**, when the 16:10 FUT collector has finished, and before the 23:50 vision archive. Weekends and holidays are fine too.

```bash
cd /root/Trade && bash scripts/export_banknifty_history_vps.sh 2>&1 | tee /root/banknifty_history_export.log
```

Then paste the output (or `/root/banknifty_history_export.log`) to Claude. It contains no secret: only counts, dates and checksums.

**What it does:**
1. `git pull --ff-only` in `/root/trade-data`. This is the VPS clone that already pushes every night as `vps-data-export`, through
   the `github-trade-data` deploy key.
2. `scripts/export_banknifty_history.py` **reads** the bot's local files and writes ONE new folder,
   `trade-data/banknifty/vps_history/<IST date_time>/`. The folder holds the CSV.gz files, `manifest.json` and `README.md`.
3. `git add --ignore-removal` + commit of **that folder only**, then `git push origin HEAD:main`. It then checks that the remote has
   every file and prints `✅ trade-data push पक्की … commit <sha>`.
4. If there is no clone, or the pull or push does not work, it writes a tarball instead,
   `/root/banknifty_history_<IST date_time>.tgz`, and prints its sha256. Copy that file to the laptop
   (`scp root@<VPS>:/root/banknifty_history_….tgz .`) and give it to Claude. Nothing is lost.

**Safety:**
* The export is **read-only** on the bot's files. SQLite is opened with `mode=ro`, and parquet / cache files are only read.
* There is no Upstox, Supabase or paid call, and no network at all, apart from git to trade-data.
* It is **BANKNIFTY only**. NIFTY / SENSEX rows are never read into an output, and a FUT contract that is not BANKNIFTY makes the run
  refuse.
* It never overwrites anything: the folder must be new, and files are opened with "x".
* It refuses 08:30–15:35 IST on trading days (`config.is_market_open` with a margin).
* It does not touch settings, cron, services or `.env`. It runs under `nice` / `ionice`.
* The exit code is not 0 on any error. When that happens, nothing is committed.

## What the VPS is expected to have (honest)

| Data | VPS source the script reads | Expected range | Gain over trade-data |
|---|---|---|---|
| Spot **1m** | `data/engine3_cache/hist_NSE_INDEX_Nifty_Bank_1minute_*.pkl`, the engine's daily 1m history cache. It exists only if `engine3_use_1m` is on (the default). It holds `engine3_m15_days` of 1m (default 90 days), and only the newest file is kept. | about the last 90 calendar days, up to the last session before the run (≈ late Jul → now) | **yes**: about 2 months older than 15 Sep, plus 13 Oct → now. 5M can be built from it (the replay found that 15M built from 1m matched the 15M bars exactly). |
| Spot **5M** | `data/oe_index_5min_BANKNIFTY.parquet` (FUT collector) | 30 Sep → now (the store started 30 Sep: 525 rows on 9 Oct, VPS log) | forward only (14 Oct → now) |
| Near-month **FUT 5M volume** | `data/oe_futures_5min_BANKNIFTY.parquet` (+ `_all`: front + next) | 30 Sep → now | **forward only**. The older near-month contracts are expired. Their 5M volume was never stored on the VPS, and Upstox gives expired FUT candles only with Upstox Plus (HTTP 401, paid). **Before 30 Sep the reader will still say FUT volume missing.** |
| 15M / 1H / Daily | `historical_candles` in `data/historical_data.db`, if it has BANKNIFTY rows. No current code writes that table, so it is probably empty. | unknown | probably none. trade-data already has 15M from 13 Jul and Daily from 2015, and 1m-built 15M is possible. |

Not read on purpose: `data/holdout/` (the sealed holdout cache), Supabase tables, the NIFTY files and the NIFTY cache entries.

**So:** with this export, the replay can have spot 1m + 5M from about late July. FUT volume will still only exist from 30 Sep. The
live reader treats missing FUT volume as a data error (`FutVolumeMissing`, Abhi Z-1c), so before 30 Sep a replay can show the reader's
levels / ③ but not a formed setup. Getting the older FUT volume would need a paid source (Upstox Plus expired-instrument candles).
That is Abhi's call, and nothing here does it.

## Output layout (trade-data)

`banknifty/vps_history/<IST date_time>/`

* `BANKNIFTY_1M.csv.gz`, `_5M`, `_15M`, `_1H`, `_D`: only the datasets that have rows.
  Columns: `timestamp` (bar start, IST, naive), `open, high, low, close, volume, oi, source`.
* `BANKNIFTY_FUT_5M.csv.gz` (near-month) and `BANKNIFTY_FUT_5M_all.csv.gz` (front + next contract). These add a `contract` column,
  e.g. `BANKNIFTY FUT 27 OCT 26`, which `legs2.volume.expiry_of` reads.
* `manifest.json`: per file, rows, first / last bar, days, expected sessions, missing sessions, incomplete sessions (fewer bars than a
  full session: 1m 375, 5M 75, 15M 25, 1H 7), the FUT contracts and sessions with volume, the missing near-month FUT-volume days
  against the spot range, conflicts between sources, and sha256.
* `README.md`: a short table.

The replay reads these the same way it reads `banknifty/*.csv.gz` (`pd.read_csv`, `timestamp` column).
A later run makes a new folder and never changes an older one.

## Run by hand (optional)

```bash
cd /root/Trade && python3 scripts/export_banknifty_history.py --check          # coverage only, writes nothing
```

Tests (synthetic sqlite / parquet / cache, no real data): `python3 -m pytest -q tests/test_export_banknifty_history.py`.
