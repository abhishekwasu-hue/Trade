#!/usr/bin/env bash
# scripts/deploy_pa_standard_vps.sh — PA standard (Abhi 21 Oct): entry models E1–E4 live in PAPER, Vision human_confirm, NIFTY + BANKNIFTY.
# Abhi runs it on the VPS (a session never does). PAPER only — every settings write is refused for a combo that is not PAPER; LIVE is
# never touched (a needed LIVE change ⇒ STOP with the reason). Nothing secret is printed (.env loaded silently; token check = ok/rejected).
#   bash scripts/deploy_pa_standard_vps.sh          ⇒ 1 save the settings it changes ⇒ /root/pa_standard_prev_settings.json
#                                                     2 bash scripts/deploy_one_bot.sh (code = DEPLOY_REF, default origin/main; own rollback file)
#                                                     3 Vision vision_mode human_confirm · engine3_entry_gate = models · models E1–E4 ON
#                                                     4 engine symbols NIFTY + BANKNIFTY (signal_symbols; PAPER only)
#                                                     5 status block (scripts/pa_standard_status.py, read-only)
#   bash scripts/deploy_pa_standard_vps.sh --revert ⇒ the saved settings back, then the code from this deploy's rollback file + restart
#                                                     (one-bot mode, its settings and the engine cron are not touched)
# Start (no pull first): cd /root/Trade && git fetch origin && git show origin/main:scripts/deploy_pa_standard_vps.sh > /root/deploy_pa.sh && bash /root/deploy_pa.sh
# Env: REPO_DIR (default /root/Trade), PREV_FILE (default /root/pa_standard_prev_settings.json),
#      ROLLBACK_FILE (default /root/pa_standard_rollback.txt — the commit before THIS deploy, written once by deploy_one_bot.sh).
set -euo pipefail
REPO_DIR="${REPO_DIR:-/root/Trade}"
PREV="${PREV_FILE:-/root/pa_standard_prev_settings.json}"
export ROLLBACK_FILE="${ROLLBACK_FILE:-/root/pa_standard_rollback.txt}"
cd "$REPO_DIR"
[ -f ./.env ] || { echo "❌ $REPO_DIR/.env नाही — deploy थांबवला"; exit 1; }
set +u; set -a; . ./.env; set +a; set -u

REF="${DEPLOY_REF:-origin/main}"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/scripts"
helper() {  # the settings helper from the deploy ref (the old checkout has none), run against the repo's current modules / data paths
  [ -s "$T/scripts/pa_standard_settings.py" ] || { git fetch -q origin; git show "$REF:scripts/pa_standard_settings.py" > "$T/scripts/pa_standard_settings.py"; }
  PYTHONPATH="$REPO_DIR" python3 "$T/scripts/pa_standard_settings.py" "$@"
}
restart_units() {  # same units as deploy_one_bot.sh (vision* / position* / streamlit* + vision_worker / vision_telegram); missing ⇒ skip
  local u S
  S=$(systemctl list-units --type=service --state=active --no-legend --plain "vision*" "position*" "streamlit*" 2>/dev/null | cut -d" " -f1)
  for u in vision_worker.service vision_telegram.service; do systemctl cat "$u" >/dev/null 2>&1 && S="$S $u"; done
  S=$(echo $S | tr " " "\n" | sort -u | tr "\n" " ")
  [ -n "${S// /}" ] || { echo "· restart: unit नाही"; return 0; }
  for u in $S; do systemctl restart "$u" && echo "↻ $u: $(systemctl is-active "$u" || true)" || echo "⚠️ $u restart अयशस्वी"; done
}

if [ "${1:-}" = "--revert" ]; then
  # Undoes ONLY this deploy: the saved PA settings, then the code from this deploy's own rollback file. The one-bot mode, its settings
  # and the engine cron (deploy_one_bot.sh) are NOT touched.
  echo "== 1/3 PA standard settings revert ($PREV)"
  set +e; helper revert --file "$PREV"; RC=$?; set -e
  if [ "$RC" != 0 ] && [ "$RC" != 4 ]; then
    echo "❌ settings revert exit $RC — code NOT rolled back (the helper must still be able to finish). Fix the line above, then run --revert again."
    exit "$RC"
  fi
  echo "== 2/3 code rollback (this deploy only: $ROLLBACK_FILE)"
  if [ -f "$ROLLBACK_FILE" ]; then
    read -r B H < "$ROLLBACK_FILE"
    if [ "$B" = HEAD ]; then git checkout -q --detach "$H"; else git checkout -q -B "$B" "$H"; fi
    mv -f "$ROLLBACK_FILE" "$ROLLBACK_FILE.reverted"
    echo "code: $(git rev-parse --abbrev-ref HEAD) $(git rev-parse --short HEAD)"
    restart_units
  else
    echo "⚠️ $ROLLBACK_FILE नाही — code तसाच ($(git rev-parse --short HEAD))"
  fi
  echo "== 3/3 status"; python3 scripts/set_one_bot_mode.py --status || true
  exit 0
fi

# Start this script from the deploy ref WITHOUT pulling first (a pull would make the rollback point the new code):
#   cd /root/Trade && git fetch origin && git show origin/main:scripts/deploy_pa_standard_vps.sh > /root/deploy_pa.sh && bash /root/deploy_pa.sh
git fetch -q origin
if [ ! -f "$ROLLBACK_FILE" ] && [ "$(git rev-parse HEAD)" = "$(git rev-parse "$REF")" ]; then
  echo "❌ the checkout is already at $REF (git pull ran?) — the rollback point would be the new code. Nothing changed. Check out the previous commit, then run again."
  exit 1
fi

echo "== 1/5 save current settings ⇒ $PREV (before anything changes)"
# The code on the VPS is still the old one here: the helper is taken from the deploy ref into a temp dir and run with the CURRENT repo's
# modules and data paths (cwd = repo, PYTHONPATH = repo) — read only (save writes only $PREV; plan writes nothing).
helper save --file "$PREV"
set +e; helper plan --file "$PREV"; RC=$?; set -e
if [ "$RC" != 0 ]; then echo "❌ STOP before deploy (exit $RC): an engine bot combo is not PAPER / settings unreadable (above) — nothing changed"; exit 3; fi

echo "== 2/5 deploy_one_bot.sh (code, schedule, one-bot settings, restart, dry-runs)"
bash scripts/deploy_one_bot.sh

echo "== 3/5 Vision human_confirm + entry models ON (PAPER only)"
python3 -m vision.config set srv2_momentum_reversal vision_mode human_confirm --by abhi >/dev/null \
  && echo "✅ Vision srv2_momentum_reversal vision_mode = human_confirm" \
  || { echo "❌ vision_mode human_confirm refused (it is PAPER-only — a LIVE symbol?) — revert: bash scripts/deploy_pa_standard_vps.sh --revert"; exit 3; }

echo "== 4/5 engine settings + symbols NIFTY / BANKNIFTY"
set +e; python3 scripts/pa_standard_settings.py apply --file "$PREV"; RC=$?; set -e
if [ "$RC" != 0 ]; then
  echo "❌ engine settings not applied (exit $RC; LIVE untouched) — revert: bash scripts/deploy_pa_standard_vps.sh --revert"; exit "$RC"
fi
flock -n /tmp/engine_signal_run.lock python3 scripts/engine_signal_run.py --dry-run --force || echo "⚠️ engine dry-run: वरची ❌ ओळ पाहा"

echo "== 5/5 status"
set +e; python3 scripts/pa_standard_status.py; RC=$?; set -e
[ "$RC" = 0 ] && echo "✅ PA standard deploy done · revert: bash scripts/deploy_pa_standard_vps.sh --revert" \
  || echo "⚠️ status not clean (above) · revert: bash scripts/deploy_pa_standard_vps.sh --revert"
