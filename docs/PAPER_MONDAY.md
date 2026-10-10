# Monday PAPER — मार्ग, settings, deploy (Abhi P0)

**मुख्य मार्ग:** existing bots (5-Min Instant, 15M Dynamic SR, SR V3) → (signal_source) → Vision → Abhi ✅ → PAPER entry → updates → exit → journal.
LIVE मार्गाला हात नाही. Vision कधीच order देत नाही; किंमती फक्त API (option chain / LTP / order_log) मधून.

| # | काय | कुठे |
|---|---|---|
| 1 | `signal_source` own / engine / both (dashboard: Bot Dynamic SR Algo → 🧭 Signal source; SR V3 साठी वेगळा) | `engine_signal.py`, `paper/bot_hooks.py`, `paper/engine_entry.py`, `scripts/engine_signal_run.py` |
| 1 | engine चं shadow मत Vision caption मध्ये ("engine: setup/wait …") | `vision/worker.py: engine_line` |
| 2 | Approval शिवाय PAPER entry नाही: PAPER मध्ये auto_veto / V0 mode ⇒ `human_confirm`; entry फक्त Telegram ✅ (`decided_by telegram:`) नंतर; timeout / ❌ / drift / ✅ नसणं ⇒ **कुठलीही PAPER position नाही** (shadow सुद्धा नाही) — फक्त `paper_would_have` नोंद (lots 0); gate चूक / gate नाही ⇒ entry नाही; यादीबाहेरचा symbol ⇒ नाही | `vision/config.py: approval_required`, `vision/gate.py: _shadow`, `paper/journal.py: would_have`, तिन्ही bots |
| 2 | SR V3 आता Vision gate + forced levels मार्गावर | `srv3_instant_shadow.py` |
| 3 | Lot size Upstox instrument master (front FUT) मधून; config.yaml फक्त fallback; mismatch ⇒ Telegram | `paper/lots.py`, `config.yaml: paper.instruments` |
| 4–6 | Journal (bot, signal_source, Vision मत + कारण, approver, engine मत, R:R, entry / exit charges, net P&L) + Telegram updates (entry fill, दर N मिनिटं P&L, SL / target जवळ, exit). Watcher फक्त cron monitor loop मधून, exit lock सुटल्यानंतर, स्वतःच्या lock + `watch_min_interval_sec` throttle ने — stream monitor (position_stream_monitor) च्या hot loop मधून कधीच नाही | `paper/journal.py`, `paper/watch.py: run_locked`, `trade_monitor.py: run_monitor_cycle` |
| 7 | `/status` `/positions` `/pause` `/resume` (फक्त approver). `/pause` `/resume` = **PAPER-scope** flag (`paper/pause.py`) — LIVE / dashboard pause ला Telegram वरून हात नाही; pause फक्त नवे PAPER entries (bots, engine, ✋ /paper), exits नेहमी | `paper/commands.py`, `paper/pause.py`, `paper/bot_hooks.py: own_signal_ok` |
| 9 | NIFTY enabled; BANKNIFTY / SENSEX `enabled: false` | `config.yaml: paper.instruments` |
| — | Token नाही ⇒ स्पष्ट error + Telegram (दिवसातून एकदा) | `paper/bot_hooks.py: token_error`, bots चा `__main__` |
| ✋ | Manual trigger `/paper` (P1 मधून P0): validation ⇒ Vision (bot key `manual`; NA तरी बटणं) ⇒ ✅ ⇒ PAPER entry ⇒ updates ⇒ तुमचा spot SL / T exit ⇒ journal | `paper/manual.py`, `vision/telegram_bot.py`, `paper/watch.py`, `vision/worker.py: v1_caption` |

## Settings (code मध्ये आकडे नाहीत)
- `config.yaml → paper`: `instruments.<SYM>.enabled / lot_size_fallback`, `update_every_min` (30), `near_alert_pct` (80), `entry_cutoff` ("14:45" — ✋ /paper आणि engine मार्ग), `watch_min_interval_sec` (15).
- Vision (dashboard / `/vision`): `approval_required` (default true), `approve_window_min` (10), `exec_window_min` (5).
- Bot settings: `signal_source` (own), SR V3: `srv3_signal_source` (own).

## ✋ Manual trigger (Telegram, फक्त TELEGRAM_APPROVER_IDS)
```
/paper NIFTY bullput SL 24750 T 25300              # strikes / width / lots: manual_profile bot च्या settings (default SR V3)
/paper NIFTY bearcall 25100/25200 SL 25250 T 24800 # तुमचे strikes (short/hedge)
/help
```
- तपासणी: instrument enabled, बाजार वेळ, token, pause, kill-switch, उघडी manual position (एका वेळी एक), आधीचा pending manual, option chain
  (आज expiry ⇒ पुढची weekly), बाजू (bull put: short > hedge, SL spot खाली, T वर; bear call उलट), strikes chain मध्ये, net credit > 0.
- R:R = |T − spot| / |spot − SL| caption मध्ये; < 3 ⇒ ⚠️ (तरी ✅ ने घेता येतो).
- ✅ ⇒ लगेच (Telegram service) drift guard + entry (`open_multi_leg_trade` — kill-switch / pause / VIX पुन्हा). ❌ / 10 मिनिटं उत्तर नाही ⇒ entry नाही.
- Exit: तुमचा spot SL / T (paper watcher, trade_monitor च्या प्रत्येक cycle ला) + backstop generic नियम (credit च्या 100% तोटा, 3:10 नियम).
- `manual_profile`: dashboard → Vision Human Eye → "✋ manual_profile".

## Engine service (signal_source engine / both साठी; own असताना फक्त caption मत; cron वेळ UTC)
```
1,16,31,46 3-10 * * 1-5  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/engine_signal_run.py >> engine_signal.log 2>&1
```

## Sunday dry-run
```
cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_dry_run.py --wait-min 12
```
प्रत्येक bot चा (आणि एक ✋ manual `/paper`) "🧪 [DRY-RUN]" Vision संदेश येतो ⇒ ✅ दाबा ⇒ PAPER entry ⇒ updates ⇒ exit ⇒ journal. Log: `data/paper_dry_run_<date>.log`.

## VPS deploy (Sunday, Abhi) — एकच ओळ
Tracked बदल असतील तर थांबते; आधीची branch / commit `/root/paper_rollback.txt` मध्ये; नवा code आधी तात्पुरत्या worktree मध्ये import-तपासणी
(अयशस्वी ⇒ काहीही बदलत नाही); requirements बदलले तरच pip; engine cron (UTC) एकच ओळ; services: VPS वरचे चालू `vision* position* streamlit*`
(systemctl स्वतः शोधतो) + `vision_worker`, `vision_telegram` (installed असतील तर) restart; `.env` फक्त वाचते, approver साठी फक्त 160201826 छापते.
```
bash -c 'set -euo pipefail; cd /root/Trade; [ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "❌ tracked बदल आहेत — deploy थांबवला:"; git status --short --untracked-files=no; exit 1; }; OLD=$(git rev-parse HEAD); [ "$(git rev-parse --abbrev-ref HEAD)" = paper-monday ] || echo "$(git rev-parse --abbrev-ref HEAD) $OLD" > /root/paper_rollback.txt; echo "rollback माहिती: $(cat /root/paper_rollback.txt)"; git fetch -q origin claude/paper-monday; W=$(mktemp -d); trap "git worktree remove --force $W >/dev/null 2>&1 || true; rm -rf $W" EXIT; git worktree add -q --detach "$W" origin/claude/paper-monday; git diff --quiet "$OLD" origin/claude/paper-monday -- requirements.txt || python3 -m pip install -q -r "$W/requirements.txt"; ( cd "$W" && python3 -c "import paper.manual, paper.watch, paper.commands, paper.pause, engine_signal, vision.telegram_bot, vision.worker, srv3_instant_shadow, dynamic_sr_instant_trader, srv2_momentum_reversal_strategy, trade_monitor" >/dev/null ) && echo "✅ imports OK (checkout आधी)" || { echo "❌ imports अयशस्वी — काहीही बदललं नाही (branch / cron / services जसेच्या तसे)"; exit 1; }; git checkout -q -B paper-monday origin/claude/paper-monday; C=$(crontab -l 2>/dev/null | grep -v "scripts/engine_signal_run.py" || true); { [ -z "$C" ] || printf "%s\n" "$C"; echo "1,16,31,46 3-10 * * 1-5 cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/engine_signal_run.py >> engine_signal.log 2>&1"; } | crontab -; SVCS=$(systemctl list-units --type=service --state=active --no-legend --plain "vision*" "position*" "streamlit*" | cut -d" " -f1); for u in vision_worker.service vision_telegram.service; do systemctl cat "$u" >/dev/null 2>&1 && SVCS="$SVCS $u"; done; SVCS=$(echo $SVCS | tr " " "\n" | sort -u | tr "\n" " "); echo "restart: ${SVCS:-—}"; if [ -n "${SVCS// /}" ]; then systemctl restart $SVCS; fi; for s in $SVCS; do echo "$s: $(systemctl is-active "$s" || true)"; done; ( set +u -a; . ./.env; set +a; echo ",${TELEGRAM_APPROVER_IDS:-}," | tr -d " \"" | grep -q ",160201826," && echo "approver: 160201826 ✅" || echo "approver: 160201826 नाही ❌" ); echo "engine cron: $(crontab -l | grep -c scripts/engine_signal_run.py) ओळ"; git log -1 --oneline'
```

## Rollback — वेगळी ओळ
```
bash -c 'set -euo pipefail; cd /root/Trade; [ -f /root/paper_rollback.txt ] || { echo "❌ /root/paper_rollback.txt नाही"; exit 1; }; read -r B H < /root/paper_rollback.txt; if [ "$B" = HEAD ]; then git checkout -q --detach "$H"; else git checkout -q "$B"; fi; echo "आता: $(git rev-parse --abbrev-ref HEAD) $(git rev-parse --short HEAD) (अपेक्षित ${H:0:7})"; git diff --quiet paper-monday HEAD -- requirements.txt 2>/dev/null || python3 -m pip install -q -r requirements.txt; C=$(crontab -l 2>/dev/null | grep -v "scripts/engine_signal_run.py" || true); printf "%s\n" "$C" | crontab -; SVCS=$(systemctl list-units --type=service --state=active --no-legend --plain "vision*" "position*" "streamlit*" | cut -d" " -f1); for u in vision_worker.service vision_telegram.service; do systemctl cat "$u" >/dev/null 2>&1 && SVCS="$SVCS $u"; done; SVCS=$(echo $SVCS | tr " " "\n" | sort -u | tr "\n" " "); echo "restart: ${SVCS:-—}"; if [ -n "${SVCS// /}" ]; then systemctl restart $SVCS; fi; for s in $SVCS; do echo "$s: $(systemctl is-active "$s" || true)"; done'
```
