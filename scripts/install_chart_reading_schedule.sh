#!/usr/bin/env bash
# scripts/install_chart_reading_schedule.sh — the daily Chart Reading Report (owner-orders DECISIONS 35) in the VPS crontab.
# Abhi runs it on the VPS (a session never does). Idempotent (run twice ⇒ still one line each). Touches ONLY its own tagged lines.
#   • close   (tag `# chart-reading-close`):   20 10 * * 1-5 UTC = 15:50 IST, after the market close — charts + reading.
#   • preopen (tag `# chart-reading-preopen`): 35 3 * * 1-5 UTC  = 09:05 IST, before the open — the short refresh.
#   Operational times only (the reading itself has no clock logic). The script exits at once while the dashboard setting
#   `chart_reading_report` is off (the default until Abhi approves the sample) — the lines are harmless until then.
#   --revert ⇒ removes the two tagged lines (nothing else changes) · --dry-run ⇒ prints the new crontab only.
# Env: CRONTAB_FILE (tests: a file instead of the crontab), REPO_DIR (default /root/Trade).
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
if [ -n "${CRONTAB_FILE:-}" ]; then
  [ -f "$CRONTAB_FILE" ] || { echo "❌ crontab file नाही ($CRONTAB_FILE) — काहीच बदललं नाही"; exit 1; }
  CUR="$(cat "$CRONTAB_FILE")"
else
  CUR="$(crontab -l 2>/dev/null)" || { echo "❌ crontab -l अयशस्वी — काहीच बदललं नाही"; exit 1; }
fi
write_cron() { if [ -n "${CRONTAB_FILE:-}" ]; then cat > "$CRONTAB_FILE"; else crontab -; fi; }

CLOSE_LINE="20 10 * * 1-5 cd $REPO_DIR && set -a && . ./.env && set +a && flock -n /tmp/chart_reading.lock timeout 900 python3 scripts/chart_reading_report.py --mode close >> $REPO_DIR/chart_reading.log 2>&1 # chart-reading-close"
PRE_LINE="35 3 * * 1-5 cd $REPO_DIR && set -a && . ./.env && set +a && flock -n /tmp/chart_reading.lock timeout 600 python3 scripts/chart_reading_report.py --mode preopen >> $REPO_DIR/chart_reading.log 2>&1 # chart-reading-preopen"
BASE="$( { printf '%s\n' "$CUR" | grep -v -e '# chart-reading-close$' -e '# chart-reading-preopen$' || true; } )"
if [ "$MODE" = "revert" ]; then
  NEW="$BASE"
else
  NEW="$BASE
$CLOSE_LINE
$PRE_LINE"
fi
if [ "$DRY" = 1 ]; then
  echo "---- new crontab (dry-run, not written) ----"; printf '%s\n' "$NEW"; exit 0
fi
printf '%s\n' "$NEW" | write_cron
echo "✅ crontab ($MODE): chart-reading close $(printf '%s\n' "$NEW" | grep -c '# chart-reading-close$' || true) · preopen $(printf '%s\n' "$NEW" | grep -c '# chart-reading-preopen$' || true)"
