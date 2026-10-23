#!/usr/bin/env bash
# scripts/install_reading_gallery_schedule.sh — today's reading gallery (owner-orders DECISIONS 49, the daily loop) in the VPS crontab.
# Abhi runs it on the VPS (a session never does). Idempotent (run twice ⇒ still one line). Touches ONLY its own tagged line.
#   • tag `# reading-gallery-close`: 40 10 * * 1-5 UTC = 16:10 IST — after the close AND after the chart reading run
#     (scripts/install_chart_reading_schedule.sh: 15:50 IST, timeout 15 min ⇒ done by 16:05 IST).
#   Operational time only (the reading has no clock logic). The script itself exits at once on a market holiday / weekend
#   (config.is_trading_day) or while the dashboard setting `reading_gallery` is off; it pushes to the private trade-data clone
#   ($TRADE_DATA_DIR or /root/trade-data; push impossible ⇒ a tarball under /root/reading_gallery + sha256 in the log).
#   --revert ⇒ removes the tagged line (nothing else changes) · --dry-run ⇒ prints the new crontab only.
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

LINE="40 10 * * 1-5 cd $REPO_DIR && set -a && . ./.env && set +a && flock -n /tmp/reading_gallery.lock timeout 1800 nice -n 19 python3 scripts/reading_gallery_today.py >> $REPO_DIR/reading_gallery.log 2>&1 # reading-gallery-close"
BASE="$( { printf '%s\n' "$CUR" | grep -v -e '# reading-gallery-close$' || true; } )"
if [ "$MODE" = "revert" ]; then
  NEW="$BASE"
else
  NEW="$BASE
$LINE"
fi
if [ "$DRY" = 1 ]; then
  echo "---- new crontab (dry-run, not written) ----"; printf '%s\n' "$NEW"; exit 0
fi
printf '%s\n' "$NEW" | write_cron
echo "✅ crontab ($MODE): reading-gallery $(printf '%s\n' "$NEW" | grep -c '# reading-gallery-close$' || true)"
