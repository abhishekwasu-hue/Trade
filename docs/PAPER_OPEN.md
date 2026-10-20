# PAPER trading at the open — NIFTY and BANKNIFTY (Abhi)

**What runs:** the 15M SRv2 bot, mode **PAPER**, signal source **engine** (decision3), for NIFTY and BANKNIFTY. The bot starts on its
own each weekday from cron (the engine warm-up at 08:50 IST, the bot and trade_monitor from 09:15). Each engine setup ⇒ Vision card
with ✅ / ❌ ⇒ **on ✅ the PAPER order is placed at once** (the Telegram service runs the bot's engine cycle; the bot's next minute is
the fallback; one lock ⇒ never two entries). Lots, strikes, hedge, SL / TSL and the spread target ("Target — % of net premium") come
from the dashboard. The position and its exits are tracked live (trade_monitor); Telegram gets the fill (🟢 PAPER entry), the
updates, and the exit as **🛑 PAPER SL hit** / **🎯 PAPER target hit** / 🔴 PAPER exit (any other reason). **LIVE stays OFF** — nothing
here changes a LIVE setting or places a real-money order. Exits are never blocked (pause / kill switch only stop new entries).

## 1. VPS block (Abhi runs it, after the PR is merged into main)

Stops at the first problem and says why; the last step must print `PAPER TRADING: ACTIVE` for both symbols — otherwise it stops with
`NOT ACTIVE — <symbol>: <reasons>` (never a false OK). `.env` is only read; no secret is printed.

```
bash -c 'set -euo pipefail; cd /root/Trade
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "❌ tracked changes on the VPS — stopped:"; git status --short --untracked-files=no; exit 1; }
OLD=$(git rev-parse HEAD); CUR=$(git rev-parse --abbrev-ref HEAD); echo "$CUR $OLD" > /root/paper_open_rollback.txt; echo "rollback: $(cat /root/paper_open_rollback.txt)"
git fetch -q origin +main:refs/remotes/origin/main
W=$(mktemp -d); trap "git worktree remove --force $W >/dev/null 2>&1 || true; rm -rf $W" EXIT; git worktree add -q --detach "$W" origin/main
git diff --quiet "$OLD" origin/main -- requirements.txt || python3 -m pip install -q -r "$W/requirements.txt"
( cd "$W" && python3 -c "import paper.engine_entry, paper.watch, vision.telegram_bot, vision.worker, srv2_momentum_reversal_strategy, trade_monitor, scripts.paper_status, scripts.paper_test_order" >/dev/null ) || { echo "❌ imports failed — nothing changed"; exit 1; }
git checkout -q -B deploy-main origin/main; echo "code: $(git log -1 --oneline)"
set -a; . ./.env; set +a
python3 -c "import cloud_db; s=[x.upper() for x in cloud_db.get_signal_symbols()]; need=[\"NIFTY\",\"BANKNIFTY\"]; s2=sorted(set(s)|set(need), key=lambda x: (x not in need, x)); (s2==s) or cloud_db.save_signal_symbols(s2); print(\"signal_symbols:\", cloud_db.get_signal_symbols())"
python3 scripts/set_one_bot_mode.py
bash scripts/install_engine_schedule.sh
SVCS=""; for u in vision_worker.service vision_telegram.service; do systemctl cat "$u" >/dev/null 2>&1 && SVCS="$SVCS $u"; done
[ -n "${SVCS// /}" ] || { echo "❌ vision_worker / vision_telegram services are not installed"; exit 1; }
systemctl restart $SVCS; sleep 3
python3 scripts/paper_status.py --symbols NIFTY,BANKNIFTY || { echo "❌ PAPER TRADING is NOT active — see the reasons above; nothing else to do until they are fixed"; exit 1; }
echo "✅ PAPER trading ready for the open (LIVE untouched)"'
```

- Step by step: deploy main (stops on tracked changes / failed imports) · signal_symbols include NIFTY and BANKNIFTY · one-bot mode
  (`set_one_bot_mode.py`: 15M SRv2 ON for both, PAPER, engine; Vision approvals for both; PAPER instruments enabled; other bots off;
  LIVE combos untouched) · cron (`install_engine_schedule.sh`: engine + 15M SRv2; refuses to run without the trade_monitor exits line)
  · restart the Vision services · **status check**.
- Status alone (any time): `cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_status.py`
- Code rollback: `bash -c 'set -e; cd /root/Trade; read -r B H < /root/paper_open_rollback.txt; if [ "$B" = HEAD ]; then git checkout -q --detach "$H"; else git checkout -q -B "$B" "$H"; fi; systemctl restart vision_worker vision_telegram; git log -1 --oneline'`
  (settings stay; to stop new PAPER entries at any time: Telegram `/pause`, `/resume` — exits continue).

## 2. Tonight's TEST (market closed; one signal, NIFTY)

```
cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_test_order.py --symbol NIFTY --wait-min 10
```

A card labelled **🧪 [TEST · DRY-RUN]** comes on Telegram ⇒ press ✅ ⇒ a PAPER TEST order is created and closed at once ⇒ Telegram
lines start **🧪 [TEST]**. It is kept out of the real journal and P&L: the order is written to `data/historical_data_TEST.db` and its
journal to `data/paper_journal_TEST.db`; the script compares the real trades DB and journal before / after and says
`real journal / P&L untouched: yes` (anything else ⇒ exit 1 and a ❌ line). It refuses while the market is open. Log:
`data/paper_test_order.log`.
