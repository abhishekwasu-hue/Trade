#!/usr/bin/env bash
# scripts/deploy_pa_standard_vps.sh — PA standard (Abhi 21 Oct): entry models E1–E4 live in PAPER, Vision human_confirm, NIFTY + BANKNIFTY.
# Abhi runs it on the VPS (a session never does). PAPER only — every settings write is refused for a combo that is not PAPER; LIVE is
# never touched (a needed LIVE change ⇒ STOP with the reason). Nothing secret is printed (.env loaded silently; token check = ok/rejected).
#   bash scripts/deploy_pa_standard_vps.sh          ⇒ 1 save the settings it changes ⇒ /root/pa_standard_prev_settings.json
#                                                     2 bash scripts/deploy_one_bot.sh (code = DEPLOY_REF, default origin/main; own rollback file)
#                                                     3 Vision vision_mode human_confirm · engine3_entry_gate = models · models E1–E4 ON
#                                                     4 engine symbols NIFTY + BANKNIFTY (signal_symbols; PAPER only)
#                                                     5 status block (scripts/pa_standard_status.py, read-only)
#   bash scripts/deploy_pa_standard_vps.sh --revert ⇒ the saved settings back, then bash scripts/deploy_one_bot.sh --revert
#                                                     (NOTE: deploy_one_bot --revert also runs the one-bot settings / engine schedule revert)
# Env: REPO_DIR (default /root/Trade), PREV_FILE (default /root/pa_standard_prev_settings.json),
#      ROLLBACK_FILE (default /root/pa_standard_rollback.txt — the commit before THIS deploy, written once by deploy_one_bot.sh).
set -euo pipefail
REPO_DIR="${REPO_DIR:-/root/Trade}"
PREV="${PREV_FILE:-/root/pa_standard_prev_settings.json}"
export ROLLBACK_FILE="${ROLLBACK_FILE:-/root/pa_standard_rollback.txt}"
cd "$REPO_DIR"
[ -f ./.env ] || { echo "❌ $REPO_DIR/.env नाही — deploy थांबवला"; exit 1; }
set +u; set -a; . ./.env; set +a; set -u

if [ "${1:-}" = "--revert" ]; then
  echo "== 1/3 PA standard settings revert ($PREV)"
  set +e; python3 scripts/pa_standard_settings.py revert --file "$PREV"; RC=$?; set -e
  [ "$RC" = 0 ] || echo "⚠️ settings revert exit $RC — वरची ओळ पाहा (LIVE combo कधीच बदलत नाही)"
  echo "== 2/3 code + one-bot revert (deploy_one_bot.sh --revert, rollback file $ROLLBACK_FILE)"
  bash scripts/deploy_one_bot.sh --revert
  [ -f "$ROLLBACK_FILE" ] && mv -f "$ROLLBACK_FILE" "$ROLLBACK_FILE.reverted" || true
  echo "== 3/3 status"; python3 scripts/pa_standard_status.py --no-token-check || true
  exit 0
fi

echo "== 1/5 save current settings ⇒ $PREV (before anything changes)"
# The code on the VPS is still the old one here: the helper is taken from the deploy ref into a temp dir and run with the CURRENT repo's
# modules and data paths (cwd = repo, PYTHONPATH = repo) — read only (save writes only $PREV; plan writes nothing).
REF="${DEPLOY_REF:-origin/main}"
git fetch -q origin
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/scripts" && git show "$REF:scripts/pa_standard_settings.py" > "$T/scripts/pa_standard_settings.py"
PYTHONPATH="$REPO_DIR" python3 "$T/scripts/pa_standard_settings.py" save --file "$PREV"
set +e; PYTHONPATH="$REPO_DIR" python3 "$T/scripts/pa_standard_settings.py" plan --file "$PREV"; RC=$?; set -e
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
