# Gate error 23 Oct — "error 14" (SRv2) and BANKNIFTY "no entry because a gate error"

Owner order: INBOX 23 Oct item 1, DECISIONS 47. Branch `gate-err` (from `claude/hopeful-gates-hf186c`), local commits only.
Checked against DECISIONS 47 (fail-closed, one alert per cause per day), CLAUDE.md Safety (PAPER only, exits never blocked, nothing run on
the VPS) and the one-bot mode (only 15M SRv2, `signal_source = engine`).

## 1. What Abhi saw and where it comes from

| Telegram text | Produced by | Data it reads |
|---|---|---|
| "15M SRv2: … ignored N: error 14" | `bots_common/level_visibility.py` `summary_text` → `_group_lines` → `summarize` (category `error` = `SKIPPED_GATE_ERROR`, label `⚠️ gate error`) | Supabase `signal_log` rows written by `srv2_momentum_reversal_strategy.py` (plain `SUPPORT` / `RESISTANCE` level_type = 15M SRv2) |
| "BANKNIFTY: … Price reached a supply area N times; no entry because a gate error (no entry, safe side)" | `scripts/paper_daily_summary.py` `symbol_line` (`WHY_PLAIN["error"]`) from the same `LV.summarize` counts | same `signal_log` rows |

Both are the **old level-bot confirmation gate** inside the SRv2 bot (`LGB.cycle_gate` → `LR.evaluate`), not the engine.

## 2. Every code path that can produce "gate error"

| # | Path | Where (file:line, branch `gate-err`) | What is recorded | Can it block an ENGINE entry? |
|---|---|---|---|---|
| A | old level-bot gate — **no closed 15M candle yet today** (09:15–09:29) | `bots_common/level_gate_bot.py:229` (was `err="आजचा पहिला बंद candle अजून नाही"`) | before the fix: `state ERROR` for **every** candidate area ⇒ `SKIPPED_GATE_ERROR`, reason `[GATE] <band> · आजचा पहिला बंद candle अजून नाही` | No |
| B | old level-bot gate — 15M candles fetch returned nothing | `bots_common/level_gate_bot.py:224` | `gate error (fail-closed): 15m candles मिळाले नाहीत` on every area | No |
| C | old level-bot gate — any exception in trend / bars / FUT volume / session index | `bots_common/level_gate_bot.py:238` | `gate error (fail-closed): <Type>: <msg[:80]>` on every area | No |
| D | old level-bot gate — Daily trend fetch failed / timed out (25 s, `call_with_timeout`) | `bots_common/level_reaction.py:250-252` | ctx reason `gate error (fail-closed): trend — <Type>: …` ⇒ at every arrival at an area `DISARMED` with that reason ⇒ `SKIPPED_GATE_ERROR` (only when price ARRIVES at an area — matches "while price was in its supply area") | No |
| E | old level-bot gate — exception inside the per-area replay | `bots_common/level_reaction.py:586-592` (`safe_evaluate`) | `gate error (fail-closed): <Type>: …` for that area | No |
| F | SRv2 — `cycle_gate` itself raised (e.g. a bad dashboard `gate_*` value; `gate_settings` / `confirm_tf` run before the try) | `srv2_momentum_reversal_strategy.py:315-321` | printed to `srv2.log` "confirmation gate त्रुटी ⇒ नवीन entry नाही — …" + `SKIPPED_GATE_ERROR` | No |
| G | engine step in the bot cycle raised | `paper/bot_hooks.py:88-91` | `srv2.log` "engine त्रुटी ⇒ entry नाही (<Type>: …)" | **Yes** (that engine cycle; next minute retries) |
| H | engine entry: chain / tags / Vision call raised | `paper/engine_entry.py:234-237` (legacy path), `:537-540` (models) | message line in `srv2.log` "gate त्रुटी ⇒ entry नाही (…)" | **Yes** (that cycle; the entry stays pending) |
| I | engine entry: one entry raised / PAPER open failed | `paper/engine_entry.py:487-490`, `:559-562` (`OPEN_FAILED: …` in `engine_entry_consumed`) | `srv2.log` + engine store status | **Yes** (OPEN_FAILED is claimed: no retry for that visit) |
| J | engine store read failed | `engine_signal.py:602-606` (`pending_entries` ⇒ `[]`) | `srv2.log` "⚠️ engine_signal.pending_entries: …" | **Yes** (that cycle) |
| K | Vision / approval gate raised | `vision/gate.py:59-72` | `SKIPPED_VISION_ERROR` (PAPER + approval ⇒ HOLD) / printed | **Yes** (that cycle) |
| L | engine run (decision3, every minute, 5M trigger) | `scripts/engine_signal_run.py:184-205` | `engine_signals` row `decision='error'` + existing ❌ Telegram line (`ES.alert_error`, repeats after 60 min) | **Yes** (fail-closed: no entry from that bar) |

Why the old level-bot gate (A–F) never blocks an engine entry: in `signal_source = engine` the engine entry step runs inside
`paper/bot_hooks.pre_cycle` (`srv2_momentum_reversal_strategy.py:242`) **before** the level gate is built (`:317`); its result does not
read the level gate. The bot's own (level-gate) entries are always refused in engine mode by `own_signal_ok` (`:476`, `engine ⇒ False`).
Test `test_engine_step_runs_before_and_independent_of_level_gate_error` pins this order.

## 3. Root cause of "error 14" (reproduced)

Cause A. The SRv2 cron runs every minute from 09:15 IST (`scripts/install_engine_schedule.sh:58`, `45-59 3 * * 1-5` UTC). Upstox already
returns today's forming 15M candle, so `_collect_touch_candidates` finds candidates, but `LR.closed_bars` drops the forming candle ⇒
`session_start_index` = len(bars) ⇒ `cycle_gate` returned `err="आजचा पहिला बंद candle अजून नाही"`. `CycleGate.result` turned every
area into `state ERROR` and `status_of` mapped it to `SKIPPED_GATE_ERROR`. One row per ACTIVE area per symbol each morning (the
signal_log dedupe keeps the first). In `level_visibility._visits` each such row is a visit that ends with "error" when the next row is
"price not at area" ⇒ one "error" per area per day. With ~14 ACTIVE SRv2 areas across NIFTY / BANKNIFTY / SENSEX that is exactly the
"error 14" of the 15:45 block, and the per-symbol line picks "error" as the most frequent reason ⇒ "BANKNIFTY … no entry because a gate
error". It is not an error: nothing can be read before the first 15M candle closes. This is a daily pattern, not new with the 5M trigger
(#378 did not touch `bots_common/`).

Reproduction: `tests/test_gate_error_23oct.py::test_before_first_closed_15m_bar_is_a_wait_not_an_error` (09:16 / 09:20 / 09:29) and
`::test_morning_rows_no_longer_count_as_error_14` (14 areas ⇒ old code `error 14`, new code 0). Both fail on the old code.

Still to confirm from the VPS dump (section 6): whether any of today's rows carry a real cause (B / C / D / E — e.g.
`TimeoutError` from the Daily trend fetch or "15m candles मिळाले नाहीत" when Upstox is busy with the engine's every-minute 5M fetches).
Those stay errors (fail-closed) and now each sends one ⚠️ alert.

Second finding (wording): in engine mode the per-symbol line of the 15:45 summary wrote the OLD level-bot check's reasons as "no entry
because …", which reads as if the engine entry was blocked. In engine mode that line now says it is the old level-bot check
(comparison only — engine entries come from the engine models). `scripts/paper_daily_summary.py` `symbol_line(engine=…)`.

## 4. The fix (commit on `gate-err`)

1. `bots_common/level_gate_bot.py`: no closed confirmation-TF candle yet today AND the raw fetch already holds today's forming bar
   (`_forming_today`) ⇒ `CycleGate(wait=…)`; no bar from today at all (data missing, any time) ⇒ still `SKIPPED_GATE_ERROR` + ⚠️ (review 1); `result()` returns `IDLE`, `entry
   False`, reason "waiting for today's first closed candle (15m) — nothing to read yet", status `SKIPPED_GATE_FIRST_BAR_PENDING`.
   Fail-closed unchanged (no entry). Real errors (B–E) unchanged: still `SKIPPED_GATE_ERROR`.
2. `bots_common/level_visibility.py`: the new status = category `first_bar`, a visit boundary like "price not at area"; never counted as
   ignored / error; dashboard label "⚪ waiting for today's first closed candle". `level_bots_replay.py` label added.
3. `scripts/paper_daily_summary.py`: per-symbol line — rows of each index level bot whose OWN `signal_source` is engine are summarized
   separately and named "the old level-bot check (comparison only)", never "no entry because …" (review 5; display only).
4. Alert (DECISIONS 47): new small module `bots_common/gate_alert.py` — `alert(path, symbol, detail, …)` sends ONE plain-words ⚠️
   Telegram message per cause per day (cause = path + exception name, or the reason's words without numbers); state in the engine alert
   file (`data/engine_signal_alerts.json`, key `_gate_error`, today's keys only), recorded only after a successful send; never raises,
   never blocks or changes an entry / exit. A failed send is not retried in the same run (review 3); the write re-reads the shared file
   and replaces it atomically (review 4). `text()` is one function so the Telegram message standard (⚠️ type) can re-skin it. Hooked
   at A–K paths: SRv2 per-area gate error (`srv2_momentum_reversal_strategy.py:344-345`), engine step (`paper/bot_hooks.py:90-91`),
   engine entry (`paper/engine_entry.py:236, 489, 539, 561`), engine store (`engine_signal.py:603-604`), Vision gate
   (`vision/gate.py:59-64`). Example:

   ```
   ⚠️ Alert — error in the old level-bot check in the 15M SRv2 bot (BANKNIFTY, first at 11:05). No action — information.
   • What failed: ConnectionError: Upstox 429
   • Safe side: no entry was taken from it; exits are not affected.
   • Engine entries are decided by the engine models, not by this check.
   • One alert per cause per day; the cause is being fixed.
   ```
5. Tests: `tests/test_gate_error_23oct.py` (17) + `tests/conftest.py` autouse stub (no real Telegram / no repo state from tests).

Provisional (listed for Abhi): path L (engine run errors) keeps its existing ❌ line (first failure, again after 60 min, ✅ recovered)
— changing it to once-per-day is left to the Telegram message standard work (DECISIONS 48), so the two do not fight. Classic / 5M
Instant / MCX bots are OFF in the one-bot mode and are not hooked yet (same helper, one line each, when they are switched on).

## 5. Tests run

`tests/test_srv2*.py tests/test_level*.py tests/test_engine*.py tests/test_one_bot.py tests/test_trigger_5m*.py
tests/test_gate_error_23oct.py tests/test_method_no_numbers.py tests/test_paper*.py tests/test_vision*.py tests/test_telegram_cleanup.py
tests/test_preopen*.py tests/test_approval_band_width.py tests/test_layer6b_output.py tests/test_entry_models*.py` — 1215 passed, 2 skipped, 7 failed (after the review fixes);
the 7 (tests/test_vision_blind_test.py ×2, tests/test_vision_v2.py ×4, tests/test_vision_v21.py ×1) fail identically on the base
branch without this change (pre-existing, chart / Vision rendering — not touched here). New: tests/test_gate_error_23oct.py 20 passed
(4 of them fail on the old code).

## 6. Read-only VPS command (lists every gate / engine error today)

Read-only: SELECT on Supabase `signal_log` (dashboard getter), sqlite `mode=ro` for `engine_signals.db` / `vision.db`, log files read;
secrets redacted (see `vps_cmd_v2.txt`). Output also saved to `/root/gate_err_23oct.txt`.
Sections: 1 engine `error` rows; 1b every engine entry today and the bot's decision (`engine_entry_consumed`); 2 every level-gate error
row (time, symbol, level, exact reason, path, and whether an engine entry was pending in the 30 min before it and what the bot did);
2b the "error N" count exactly as the 15:45 block computes it; 3 trend cache; 4 Vision rows (errors flagged); 5 distinct error lines in
`srv2.log` / `engine_signal.log` (with counts); 6 the alert state file.

Note: importing `cloud_db` (for the signal_log SELECT) opens the app's log file for appending (its logger setup) — the only file the
command touches besides its own `tee` output; nothing is written to any DB.

Paste as ONE block (after market close where possible) — `vps_cmd_v2.txt` (redaction reviewed):

```bash
cd /root/Trade && set -a && . ./.env && set +a && DAY=2026-10-23 python3 - <<'PY' 2>&1 | tee /root/gate_err_23oct.txt
# READ-ONLY: SELECT on Supabase signal_log, sqlite mode=ro, log files read. Nothing is written except the tee'd report. Secrets redacted.
import collections, glob, json, os, re, sqlite3, sys
sys.path.insert(0, ".")
DAY = os.environ.get("DAY")
SECRET = re.compile(r"(?i)(token|secret|password|passwd|pwd|api[_-]?key|bearer|authorization|cookie|jwt)([\"'=:\s]*)(\S+)")
URLPW = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^@\s/]+@")
LONG = re.compile(r"[A-Za-z0-9_\-\.+/=]{32,}")
def red(s):
    s = URLPW.sub(lambda m: f"{m.group(1)}<redacted>@", str(s))
    s = re.sub(r"(?i)(bearer\s+)\S+", r"\1<redacted>", s)
    s = re.sub(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.?[A-Za-z0-9_\-]*", "<redacted>", s)
    s = SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", s)
    return LONG.sub("<redacted>", s)
def P(*a): print(red(" ".join(str(x) for x in a)))
def H(t): P("\n" + "=" * 110 + "\n" + t + "\n" + "=" * 110)
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5); c.row_factory = sqlite3.Row; return c
import pandas as pd
P(f"gate / engine errors · day {DAY} · git HEAD:", os.popen("git log -1 --format='%h %ci %s'").read().strip())

# ---------------------------------------------------------------- 1. engine store: errors + pending entries per time
import engine_signal as ES
edb = ES.db_path(); erows, cons = [], []
try:
    with ro(edb) as c:
        erows = [dict(r) for r in c.execute("SELECT symbol, bar_ts, computed_at, decision, gate, reason, payload FROM engine_signals "
                                            "WHERE bar_ts LIKE ? ORDER BY bar_ts", (DAY + "%",))]
        cons = [dict(r) for r in c.execute("SELECT * FROM engine_entry_consumed WHERE bar_ts LIKE ? OR at LIKE ?", (DAY + "%", DAY + "%"))]
except Exception as e:
    P("engine store read error:", type(e).__name__, e)
H(f"1. ENGINE errors today (engine_signals decision='error', path = engine run) — db {edb}, rows today {len(erows)}")
for r in erows:
    if r["decision"] == ES.ERROR:
        P(f"  {r['bar_ts'][11:16]} {r['symbol']:<10} computed {str(r['computed_at'])[11:19]} · {str(r['reason'])[:220]}")
def entries_of(r):
    try: return json.loads(r["payload"] or "{}").get("entries") or []
    except Exception: return []
def pending_at(sym, t, age=30):
    """engine entries (rows with entries) in [t-age, t] for sym + what the bot did with each (engine_entry_consumed)."""
    out = []
    for r in erows:
        if r["symbol"] != sym or r["decision"] == ES.ERROR: continue
        b = pd.Timestamp(r["bar_ts"])
        if not (t - pd.Timedelta(minutes=age) <= b <= t): continue
        for e in entries_of(r):
            st = [x.get("status") for x in cons if x.get("symbol") == sym and str(x.get("visit_id")) == str(e.get("visit_id"))
                  and str(x.get("model")).upper() == str(e.get("model")).upper()]
            out.append(f"{r['bar_ts'][11:16]} {e.get('model')} dir {e.get('direction')} area {e.get('lo')}–{e.get('hi')} ⇒ bot: {st[0] if st else 'NOT CONSUMED'}")
    return out
H("1b. ENGINE entries today and the bot's decision (engine_entry_consumed)")
for r in erows:
    for e in entries_of(r):
        st = [x for x in cons if x.get("symbol") == r["symbol"] and str(x.get("visit_id")) == str(e.get("visit_id"))
              and str(x.get("model")).upper() == str(e.get("model")).upper()]
        P(f"  {r['bar_ts'][11:16]} {r['symbol']:<10} {e.get('model')} dir {e.get('direction')} area {e.get('lo')}–{e.get('hi')} "
          f"visit {e.get('visit_id')} ⇒ {(st[0].get('status'), str(st[0].get('at'))[11:19]) if st else 'NOT CONSUMED'}")

# ---------------------------------------------------------------- 2. old level-bot gate (SRv2) errors in signal_log (Supabase SELECT)
H("2. OLD LEVEL-BOT GATE errors (signal_log SKIPPED_GATE_ERROR / *_ERROR; plain SUPPORT/RESISTANCE = 15M SRv2) — first row per level "
  "(save_signal_log keeps one row per level while the status repeats)")
import cloud_db
from bots_common import level_visibility as LV
tot = collections.Counter(); causes = collections.Counter()
for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
    try:
        df = cloud_db.get_signal_log(sym, DAY)
    except Exception as e:
        P(f"  {sym}: signal_log read error {type(e).__name__}"); continue
    if df is None: P(f"  {sym}: signal_log NA (DB)"); continue
    df = df.sort_values("signal_time")
    err = df[df["trade_status"].astype(str).str.contains("ERROR")]
    P(f"  {sym}: rows {len(df)} · error rows {len(err)} · status counts:",
      dict(collections.Counter(df["trade_status"].astype(str)).most_common(12)))
    for _, r in err.iterrows():
        t = pd.Timestamp(r["signal_time"]); t = t.tz_convert("Asia/Kolkata").tz_localize(None) if t.tzinfo else t
        bot = "15M SRv2 (old level-bot gate)" if LV.level_tf(r["level_type"]) == LV.PLAIN else f"level bot {r['level_type']}"
        why = str(r["reason"]); m = re.search(r"gate error \(fail-closed\):\s*(.*)$", why)
        cause = (m.group(1) if m else why.split("·")[-1]).strip()
        tot[sym] += 1; causes[re.sub(r"[\d.,]+", "#", cause)[:90]] += 1
        pend = pending_at(sym, t)
        P(f"  {t:%H:%M:%S} {sym:<10} {r['level_type']:<12} {r['level_price']} {r['trade_status']:<26} path: {bot}")
        P(f"           exact: {why[:260]}")
        P(f"           engine entry pending then: {'; '.join(pend) if pend else 'none'}")
P("  totals by symbol:", dict(tot)); P("  causes (numbers masked):")
for k, v in causes.most_common(): P(f"    {v:>4} × {k}")
H("2b. 'error' count as the 15:45 Telegram block computes it (LV.summarize, SRv2 group)")
try:
    rows, e = LV.fetch_rows(DAY)
    if e: P("  NA:", e)
    else:
        for label, tfs, mk in LV.GROUPS:
            s = LV.summarize(LV.group_rows(rows, tfs, mk)); P(f"  {label}: armed {s['armed']} confirmed {s['confirmed']} ignored {dict(s['ignored'])}")
except Exception as e:
    P("  summarize error:", type(e).__name__, e)

# ---------------------------------------------------------------- 3. trend cache (a trend fetch error ⇒ every arrival = gate error)
H("3. LEVEL-GATE trend cache today (data/level_gate)")
for f in sorted(glob.glob(f"data/level_gate/trend_*{DAY}*.json")):
    try: P(" ", os.path.basename(f), open(f, encoding="utf-8").read()[:400])
    except Exception as e: P(" ", f, e)

# ---------------------------------------------------------------- 4. Vision gate errors
H("4. VISION / approval gate today (errors + engine cards)")
try:
    from vision import store as VS
    with ro(VS.db_path()) as c:
        for r in c.execute("SELECT * FROM vision_signals WHERE created_at LIKE ? ORDER BY created_at", (DAY + "%",)):
            r = dict(r); bad = "ERROR" in str(r.get("status")) or r.get("error")
            P(("  ⚠️ " if bad else "     ") + " · ".join(f"{k}={str(r.get(k))[:120]}" for k in
              ("created_at", "bot", "symbol", "direction", "level", "setup_tf", "status", "verdict", "error", "exec_note") if k in r))
except Exception as e:
    P("  vision store read error:", type(e).__name__, e)

# ---------------------------------------------------------------- 5. logs: exact exceptions printed by the bot / engine cycles
H("5. LOG lines (srv2.log / engine_signal.log / dsr.log / classic_sr.log): gate / engine errors (unique, with count, last 40000 lines)")
PAT = re.compile(r"gate त्रुटी|engine त्रुटी|gate error|अनपेक्षित त्रुटी|Traceback|Error|Exception|❌|⚠️ Engine|BarLate|entry नाही \(")
for f in ("srv2.log", "engine_signal.log", "dsr.log", "classic_sr.log"):
    if not os.path.exists(f): P(f"  {f}: absent"); continue
    ls = open(f, encoding="utf-8", errors="replace").read().splitlines()[-40000:]
    cnt = collections.Counter(); first = {}
    for i, ln in enumerate(ls):
        if PAT.search(ln):
            k = re.sub(r"\d{1,2}:\d{2}(:\d{2})?", "HH:MM", ln.strip())[:240]; cnt[k] += 1; first.setdefault(k, i)
    P(f"  --- {f}: {len(cnt)} distinct error lines (mtime {pd.Timestamp(os.path.getmtime(f), unit='s') + pd.Timedelta(hours=5, minutes=30):%d/%m %H:%M} IST)")
    for k, v in sorted(cnt.items(), key=lambda x: first[x[0]])[-80:]: P(f"    {v:>5} × {k}")

# ---------------------------------------------------------------- 6. alert state (what Telegram already got)
H("6. engine alert state (data/engine_signal_alerts.json)")
try: P(" ", open(ES._alert_path(None), encoding="utf-8").read()[:1500])
except Exception as e: P("  ", type(e).__name__, e)
P("\nDONE — read-only. Report saved to /root/gate_err_23oct.txt")
PY
```
