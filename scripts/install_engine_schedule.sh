#!/usr/bin/env bash
# scripts/install_engine_schedule.sh — Abhi (one bot): decision3 engine चा live schedule (प्रत्येक बंद 15M candle नंतर, NIFTY / BANKNIFTY /
# SENSEX) VPS crontab मध्ये. Idempotent (दोनदा चालवलं तरी एकच ओळ). Abhi VPS वर चालवतो — session नाही.
#   • जुन्या `scripts/engine_signal_run.py` ओळी (decision2, NIFTY) ⇒ comment (`#one-bot-off# `), delete नाही.
#   • नवी ओळ (tag `# one-bot-engine`): 1,16,31,46 4-9 UTC = 09:31 … 15:16 IST (09:30 … 15:00 चे bars; 15:15 bar script स्वतः वगळतो).
#   • 08:50 IST warm-up ओळ (tag `# one-bot-engine-warm`): Daily fold cache (पहिला 09:31 run ~1 मिनिटात) — dry-run, store / Telegram नाही.
#   • oi_signal_auto_trader / credit_spread_auto_trader / oi_greeks_vix_strategy च्या PAPER ओळी ⇒ comment. `--mode LIVE` ओळींना हात नाही (इशारा).
#   • 15M SRv2 bot ची cron ओळ नसेल तर deploy/README ची शिफारस केलेली ओळ (tag `# one-bot-srv2`) — engine setups वापरणारा तोच.
#   • trade_monitor (exits) ला हात नाही; नसेल तर फक्त इशारा.
#   --revert ⇒ आमच्या (tagged) ओळी काढतो आणि `#one-bot-off# ` comments परत चालू करतो.  --dry-run ⇒ नवा crontab फक्त दाखवतो.
# Env: CRONTAB_FILE (tests: crontab ऐवजी ही file), REPO_DIR (default /root/Trade).
set -euo pipefail
REPO_DIR="${REPO_DIR:-/root/Trade}"
MODE="install"; DRY=0
for a in "$@"; do
  case "$a" in
    --revert) MODE="revert" ;;
    --dry-run) DRY=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

read_cron() { if [ -n "${CRONTAB_FILE:-}" ]; then cat "$CRONTAB_FILE" 2>/dev/null || true; else crontab -l 2>/dev/null || true; fi; }
write_cron() { if [ -n "${CRONTAB_FILE:-}" ]; then cat > "$CRONTAB_FILE"; else crontab -; fi; }

OFF='#one-bot-off# '
ENGINE_LINE="1,16,31,46 4-9 * * 1-5 cd $REPO_DIR && set -a && . ./.env && set +a && flock -n /tmp/engine_signal_run.lock python3 scripts/engine_signal_run.py --engine decision3 --symbols NIFTY,BANKNIFTY,SENSEX >> $REPO_DIR/engine_signal.log 2>&1 # one-bot-engine"
WARM_LINE="20 3 * * 1-5 cd $REPO_DIR && set -a && . ./.env && set +a && flock -n /tmp/engine_signal_run.lock python3 scripts/engine_signal_run.py --engine decision3 --symbols NIFTY,BANKNIFTY,SENSEX --dry-run --force >> $REPO_DIR/engine_signal.log 2>&1 # one-bot-engine-warm"
SRV2_LINES="45-59 3 * * 1-5 cd $REPO_DIR && sleep 30 && python3 srv2_momentum_reversal_strategy.py --symbols NIFTY,BANKNIFTY,SENSEX >> $REPO_DIR/srv2.log 2>&1 # one-bot-srv2
* 4-10 * * 1-5 cd $REPO_DIR && sleep 30 && python3 srv2_momentum_reversal_strategy.py --symbols NIFTY,BANKNIFTY,SENSEX >> $REPO_DIR/srv2.log 2>&1 # one-bot-srv2"

CUR="$(read_cron)"
if [ "$MODE" = "revert" ]; then
  NEW="$( { printf '%s\n' "$CUR" | grep -v -e '# one-bot-engine$' -e '# one-bot-engine-warm$' -e '# one-bot-srv2$' || true; } | sed "s|^$OFF||")"
else
  # 1) आधीच्या आमच्या ओळी काढा (idempotent), 2) जुनी engine ओळ + PAPER auto-trader ओळी comment, 3) नवी ओळ जोडा
  BASE="$(printf '%s\n' "$CUR" | grep -v -e '# one-bot-engine$' -e '# one-bot-engine-warm$' -e '# one-bot-srv2$' || true)"
  NEW="$(printf '%s\n' "$BASE" | awk -v off="$OFF" '
    /^[[:space:]]*#/ { print; next }
    /scripts\/engine_signal_run\.py/ { print off $0; next }
    /(oi_signal_auto_trader|credit_spread_auto_trader|oi_greeks_vix_strategy)\.py/ {
      if ($0 ~ /--mode[[:space:]]+LIVE/) { print; next }
      print off $0; next }
    { print }')"
  NEW="$(printf '%s\n' "$NEW" | sed '/^$/d')"
  if ! printf '%s\n' "$NEW" | grep -v '^[[:space:]]*#' | grep -q 'srv2_momentum_reversal_strategy.py'; then
    NEW="$NEW
$SRV2_LINES"
    echo "ℹ️ 15M SRv2 bot cron ओळ नव्हती ⇒ जोडली (# one-bot-srv2)"
  fi
  NEW="$NEW
$WARM_LINE
$ENGINE_LINE"
fi
NEW="$(printf '%s\n' "$NEW" | sed '/^$/d')"

printf '%s\n' "$NEW" | grep -v '^[[:space:]]*#' | grep -E '(oi_signal_auto_trader|credit_spread_auto_trader|oi_greeks_vix_strategy)\.py' | grep -E -- '--mode[[:space:]]+LIVE' \
  | sed 's/^/⚠️ LIVE auto-trader ओळ — हात लावला नाही: /' || true
printf '%s\n' "$NEW" | grep -v '^[[:space:]]*#' | grep -q 'trade_monitor.py' || echo "⚠️ trade_monitor.py (exits) cron ओळ दिसली नाही — deploy/README तपासा"

if [ "$DRY" = 1 ]; then
  echo "---- नवा crontab (dry-run, लिहिला नाही) ----"; printf '%s\n' "$NEW"; exit 0
fi
printf '%s\n' "$NEW" | write_cron
echo "✅ crontab ($MODE): engine ओळी $(printf '%s\n' "$NEW" | grep -c '# one-bot-engine$' || true) · warm $(printf '%s\n' "$NEW" | grep -c '# one-bot-engine-warm$' || true) · comment केलेल्या $(printf '%s\n' "$NEW" | grep -c "^$OFF" || true)"
