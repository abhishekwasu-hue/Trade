#!/usr/bin/env bash
# scripts/install_engine_schedule.sh — Abhi (one bot): decision3 engine चा live schedule (प्रत्येक बंद 15M candle नंतर, NIFTY / BANKNIFTY /
# SENSEX) VPS crontab मध्ये. Idempotent (दोनदा चालवलं तरी एकच ओळ). Abhi VPS वर चालवतो — session नाही. LIVE ओळींना कधीच हात नाही.
#   • crontab वाचता आला नाही / trade_monitor (exits) ओळ नाही ⇒ ❌ थांबतो, काहीच लिहीत नाही (exits कधीच थांबू नयेत).
#   • जुन्या `scripts/engine_signal_run.py` ओळी (decision2, NIFTY) ⇒ comment (`#one-bot-off# `), delete नाही.
#   • नवी ओळ (tag `# one-bot-engine`): 1,16,31,46 4-9 UTC = 09:31 … 15:16 IST (09:30 … 15:00 चे bars; 15:15 bar script स्वतः वगळतो).
#   • 08:50 IST warm-up ओळ (tag `# one-bot-engine-warm`): Daily fold cache — dry-run, store / Telegram नाही.
#   • oi_signal_auto_trader / credit_spread_auto_trader / oi_greeks_vix_strategy च्या PAPER ओळी ⇒ comment — पण त्या bot ची OPEN position
#     असेल (किंवा तपासता आलं नाही) तर ओळ चालू (exits / position management साठी) + ⚠️; नवे PAPER entries settings `symbol_enabled` = false
#     ने बंद (scripts/set_one_bot_mode.py). `--mode LIVE` / `--mode=LIVE` / quoted ओळींना हात नाही (इशारा).
#   • 15M SRv2 bot ची cron ओळ नसेल तर deploy/README ची शिफारस केलेली ओळ (tag `# one-bot-srv2`) — engine setups वापरणारा तोच.
#   --revert ⇒ आमच्या (tagged) ओळी काढतो आणि `#one-bot-off# ` comments परत चालू करतो (बाकी ओळी / रिकाम्या ओळी तशाच).
#   --dry-run ⇒ नवा crontab फक्त दाखवतो.
# Env: CRONTAB_FILE (tests: crontab ऐवजी ही file), REPO_DIR (default /root/Trade), ONE_BOT_OPEN_SOURCES (tests: open positions असलेले
# auto traders, comma; नाहीतर python ने live_trades DB मधून).
set -euo pipefail
REPO_DIR="${REPO_DIR:-/root/Trade}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="install"; DRY=0
for a in "$@"; do
  case "$a" in
    --revert) MODE="revert" ;;
    --dry-run) DRY=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

OFF='#one-bot-off# '
LIVE_RE="--mode[=[:space:]]+[\"']?LIVE([^A-Za-z0-9_]|\$)"
AUTO_RE='(oi_signal_auto_trader|credit_spread_auto_trader|oi_greeks_vix_strategy)\.py'

if [ -n "${CRONTAB_FILE:-}" ]; then
  [ -f "$CRONTAB_FILE" ] || { echo "❌ crontab file नाही ($CRONTAB_FILE) — काहीच बदललं नाही"; exit 1; }
  CUR="$(cat "$CRONTAB_FILE")"
else
  CUR="$(crontab -l 2>/dev/null)" || { echo "❌ crontab -l अयशस्वी — काहीच बदललं नाही (exits चा cron तपासता येत नाही)"; exit 1; }
fi
has_monitor() { printf '%s\n' "$1" | grep -v '^[[:space:]]*#' | grep -q 'trade_monitor.py'; }
if [ "$MODE" = "install" ] && ! has_monitor "$CUR"; then
  echo "❌ trade_monitor.py (exits) cron ओळ दिसली नाही — schedule लावला नाही, काहीच लिहिलं नाही. आधी deploy/README प्रमाणे exits चा cron तपासा."
  exit 1
fi
write_cron() { if [ -n "${CRONTAB_FILE:-}" ]; then cat > "$CRONTAB_FILE"; else crontab -; fi; }

ENGINE_LINE="1,16,31,46 4-9 * * 1-5 cd $REPO_DIR && set -a && . ./.env && set +a && flock -n /tmp/engine_signal_run.lock python3 scripts/engine_signal_run.py --engine decision3 --symbols NIFTY,BANKNIFTY,SENSEX >> $REPO_DIR/engine_signal.log 2>&1 # one-bot-engine"
WARM_LINE="20 3 * * 1-5 cd $REPO_DIR && set -a && . ./.env && set +a && flock -n /tmp/engine_signal_run.lock python3 scripts/engine_signal_run.py --engine decision3 --symbols NIFTY,BANKNIFTY,SENSEX --dry-run --force >> $REPO_DIR/engine_signal.log 2>&1 # one-bot-engine-warm"
SRV2_LINES="45-59 3 * * 1-5 cd $REPO_DIR && sleep 30 && python3 srv2_momentum_reversal_strategy.py --symbols NIFTY,BANKNIFTY,SENSEX >> $REPO_DIR/srv2.log 2>&1 # one-bot-srv2
* 4-10 * * 1-5 cd $REPO_DIR && sleep 30 && python3 srv2_momentum_reversal_strategy.py --symbols NIFTY,BANKNIFTY,SENSEX >> $REPO_DIR/srv2.log 2>&1 # one-bot-srv2"
TAGS=(-e '# one-bot-engine$' -e '# one-bot-engine-warm$' -e '# one-bot-srv2$')

if [ "$MODE" = "revert" ]; then
  NEW="$( { printf '%s\n' "$CUR" | grep -v "${TAGS[@]}" || true; } | sed "s|^$OFF||")"
else
  if [ -n "${ONE_BOT_OPEN_SOURCES+x}" ]; then
    OPEN_SRC="$ONE_BOT_OPEN_SOURCES"
  else
    OPEN_SRC="$(cd "$HERE" && python3 -c 'from bots_common.one_bot import open_auto_sources as f; print(",".join(f()))' 2>/dev/null)" || OPEN_SRC="UNKNOWN"
  fi
  BASE="$( { printf '%s\n' "$CUR" | grep -v "${TAGS[@]}" || true; } )"
  NEW="$(printf '%s\n' "$BASE" | awk -v off="$OFF" -v live="$LIVE_RE" -v auto="$AUTO_RE" -v open_src=",$OPEN_SRC," '
    /^[[:space:]]*#/ { print; next }
    /scripts\/engine_signal_run\.py/ { print off $0; next }
    $0 ~ auto {
      if ($0 ~ live) { print; next }
      match($0, auto); src = substr($0, RSTART, RLENGTH - 3)
      if (open_src == ",UNKNOWN," || index(open_src, "," src ",") > 0) {
        print "⚠️ " src ": open position (or not checkable) ⇒ cron line kept for exits; new PAPER entries blocked by symbol_enabled=false" > "/dev/stderr"
        print; next }
      print off $0; next }
    { print }')"
  if ! printf '%s\n' "$NEW" | grep -v '^[[:space:]]*#' | grep -q 'srv2_momentum_reversal_strategy.py'; then
    NEW="$NEW
$SRV2_LINES"
    echo "ℹ️ 15M SRv2 bot cron ओळ नव्हती ⇒ जोडली (# one-bot-srv2)"
  fi
  NEW="$NEW
$WARM_LINE
$ENGINE_LINE"
fi

printf '%s\n' "$NEW" | grep -v '^[[:space:]]*#' | grep -E "$AUTO_RE" | grep -E -- "$LIVE_RE" \
  | sed 's/^/⚠️ LIVE auto-trader ओळ — हात लावला नाही: /' || true
has_monitor "$NEW" || echo "⚠️ trade_monitor.py (exits) cron ओळ दिसली नाही — deploy/README तपासा"

if [ "$DRY" = 1 ]; then
  echo "---- नवा crontab (dry-run, लिहिला नाही) ----"; printf '%s\n' "$NEW"; exit 0
fi
printf '%s\n' "$NEW" | write_cron
echo "✅ crontab ($MODE): engine ओळी $(printf '%s\n' "$NEW" | grep -c '# one-bot-engine$' || true) · warm $(printf '%s\n' "$NEW" | grep -c '# one-bot-engine-warm$' || true) · comment केलेल्या $(printf '%s\n' "$NEW" | grep -c "^$OFF" || true)"
