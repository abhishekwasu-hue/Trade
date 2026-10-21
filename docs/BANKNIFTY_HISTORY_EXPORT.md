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
1. The market-hours check runs first (`--guard-only`). Between 08:30 and 15:35 IST on a trading day it stops before touching anything.
2. It checks `/root/trade-data`: it must be on `main`, and `git pull --ff-only` must work. This is the VPS clone that already pushes
   every night as `vps-data-export`, through the `github-trade-data` deploy key. If either check fails, the clone is not touched and
   the run goes to the tarball (step 6).
3. `scripts/export_banknifty_history.py` **reads** the bot's local files and writes ONE new folder,
   `trade-data/banknifty/vps_history/<IST date_time>/`. The folder holds the CSV.gz files, `manifest.json` and `README.md`. The files
   are written first under the clone's `.git/` folder, which git never tracks (outside a git clone: a hidden sibling folder). They are
   then renamed into place, so a half-written folder never sits at the final path. A crash leftover can never be pushed.
4. `git add --ignore-removal` + commit of **that folder only**, then `git push origin HEAD:main`. If the push is rejected, it runs
   `pull --rebase --autostash` (as `vision_archive.py` does) and pushes once more. Sometimes the clone's own uncommitted changes cannot
   be put back after the rebase (a conflict). Git then keeps them in the clone's stash. The script says so, and puts the tracked files
   back to HEAD so that no conflict markers break the nightly push. `git stash pop` restores the changes, so nothing is lost.
5. It fetches again and compares every file's blob on the remote with the local file, then prints
   `✅ trade-data push पक्की … commit <sha>`.
6. Tarball: if there is no clone, the clone is not on `main`, or the first pull fails, the folder is written outside the clone and
   packed as `/root/banknifty_history_<IST date_time>.tgz`, with its sha256 printed. If `tar` fails, the run exits 1. Copy that file to the laptop
   (`scp root@<VPS>:/root/banknifty_history_….tgz .`) and give it to Claude. Nothing is lost.
7. Committed but not pushed: if the rebase or the second push fails, the commit stays in the clone. The script then exits with
   **exit code 4** and makes **no** tarball, because a tarball as well would land the folder twice. The nightly `vision_archive.py` push
   (23:50 IST) sends it. If that push also fails, vision_archive sends a Telegram ⚠️; then tell Claude. **Do not re-run** in that
   case.

**Safety:**
* The export is **read-only** on the bot's files. SQLite is opened with `mode=ro`, and parquet / cache files are only read.
* There is no Upstox, Supabase or paid call, and no network at all, apart from git to trade-data.
* It is **BANKNIFTY only**. NIFTY / SENSEX rows are never read into an output, and a FUT contract that is not BANKNIFTY makes the run
  refuse.
* It never overwrites anything: the folder must be new, and files are opened with "x". A failed write removes its own hidden folder.
* It does not touch settings, cron, services or `.env`. It runs under `nice` / `ionice`. Git push hints are silenced.
* Exit codes: 0 = pushed and verified, or tarball written · 1 = error · 2 = refused · 3 = no BANKNIFTY data · 4 = committed in the
  clone, push pending. On an export error nothing is committed.

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
cd /root/Trade && python3 scripts/export_banknifty_history.py --guard-only     # market-hours check only
```

Tests (synthetic sqlite / parquet / cache, no real data): `python3 -m pytest -q tests/test_export_banknifty_history.py`.
