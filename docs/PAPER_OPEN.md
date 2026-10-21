# PAPER trading at the open — NIFTY and BANKNIFTY (Abhi)

**What runs:** the 15M SRv2 bot, mode **PAPER**, signal source **engine** (decision3), for NIFTY and BANKNIFTY. The bot starts on its
own each weekday from cron (the engine warm-up at 08:50 IST, the bot and trade_monitor from 09:15). Each engine setup ⇒ Vision card
with ✅ / ❌ ⇒ **on ✅ the PAPER order is placed at once** (the Telegram service runs the bot's engine cycle; the bot's next minute is
the fallback; one lock ⇒ never two entries). Lots, strikes, hedge, SL / TSL and the spread target ("Target — % of net premium") come
from the dashboard. The position and its exits are tracked live (trade_monitor); Telegram gets the fill (🟢 PAPER entry), the
updates, and the exit as **🛑 PAPER SL hit** / **🎯 PAPER target hit** / 🔴 PAPER exit (any other reason). **LIVE stays OFF** — nothing
here changes a LIVE setting or places a real-money order. Exits are never blocked (pause / kill switch only stop new entries).

## 1. ONE VPS block (Abhi runs it tonight — market closed)

Deploys main with the existing one-bot deploy, prints the status, then sends ONE "🧪 TEST — not a trade" card through the real path.
Stops at the first problem and says why. `.env` is only read; no secret is printed.

```
bash -c 'set -euo pipefail; cd /root/Trade
bash scripts/deploy_one_bot.sh
set +u; set -a; . ./.env; set +a; set -u
echo "== status (one-bot)"; python3 scripts/set_one_bot_mode.py --status
echo "== status (PAPER trading)"; python3 scripts/paper_status.py --symbols NIFTY,BANKNIFTY || { echo "❌ PAPER TRADING NOT ACTIVE — reasons above; fix them first (nothing else was sent)"; exit 1; }
echo "== TEST card (Telegram: chart + Vision + ✅ / ✏️ / ❌ — press any; NO position is ever created)"
python3 scripts/paper_test_card.py --symbol NIFTY --wait-min 10'
```

- `deploy_one_bot.sh`: pull main (stops on tracked changes / failed imports; rollback file `/root/one_bot_rollback.txt`) → engine
  schedule (decision3, refuses without the trade_monitor exits line) → one-bot settings (only 15M SRv2 ON for NIFTY + BANKNIFTY,
  PAPER, signal_source engine, Vision approval required, SENSEX and every other bot off, LIVE combos untouched) → restart the services
  → pre-open dry-run → engine dry-run → status.
- `paper_status.py` must print `PAPER TRADING: ACTIVE — NIFTY` and `… — BANKNIFTY`; otherwise the block stops with the reasons.
- The TEST card: the 15M SRv2 bot's real Vision gate ⇒ vision_worker sends the chart + Vision verdict + ✅ Approve / ✏️ change the
  entry only / ❌ Reject (+ reason) ⇒ press any button ⇒ the script reports your button and checks the real trades DB / journal are
  unchanged (`no position created`). Its level is the last closed day's high (replay only).
- **Rollback (one line):** `cd /root/Trade && bash scripts/deploy_one_bot.sh --revert`
- Status alone, any time: `cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_status.py`

## 2. Tomorrow

The pre-open message as usual (09:00). A real card comes only if the reader finds a setup (NIFTY / BANKNIFTY 15M). On ✅ the PAPER order
is placed at once with the dashboard's lots / strikes / SL / target; Telegram: 🟢 entry · updates · 🛑 SL hit / 🎯 target hit / 🔴 exit.
Stop new PAPER entries any time: Telegram `/pause` (exits continue); `/resume`.
