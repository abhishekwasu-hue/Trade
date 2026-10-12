#!/usr/bin/env bash
# scripts/deploy_one_bot.sh — Abhi (one bot, VPS वर एकच command). LIVE ला हात नाही (set_one_bot_mode LIVE combos नाकारतो; installer LIVE cron
# ओळी तशाच ठेवतो; इथे कुठलाही order / LIVE setting नाही).
#   bash scripts/deploy_one_bot.sh            ⇒ pull (deploy-main = origin/main, rollback file) → engine schedule → one-bot settings
#                                               (before / after table) → services restart (असतील तेच) → pre-open dry-run → engine dry-run → status
#   bash scripts/deploy_one_bot.sh --revert   ⇒ settings revert → schedule revert → code rollback (rollback file) → restart → status
# Env: REPO_DIR (default /root/Trade), DEPLOY_REF (default origin/main), ROLLBACK_FILE (default /root/one_bot_rollback.txt).
set -euo pipefail
REPO_DIR="${REPO_DIR:-/root/Trade}"
REF="${DEPLOY_REF:-origin/main}"
RB="${ROLLBACK_FILE:-/root/one_bot_rollback.txt}"
UNITS=(vision_worker vision_telegram streamlit_dashboard)
cd "$REPO_DIR"

restart_units() {
  local u
  for u in "${UNITS[@]}"; do
    if systemctl list-unit-files --no-legend "$u.service" 2>/dev/null | grep -q "^$u.service"; then
      systemctl restart "$u.service" && echo "↻ $u: $(systemctl is-active "$u.service" || true)" || echo "⚠️ $u restart अयशस्वी"
    else
      echo "· $u: unit नाही (optional) — skip"
    fi
  done
}

if [ "${1:-}" = "--revert" ]; then
  echo "== 1/4 settings revert"; python3 scripts/set_one_bot_mode.py --revert || echo "⚠️ settings revert: वरचा संदेश पाहा"
  echo "== 2/4 schedule revert"; bash scripts/install_engine_schedule.sh --revert
  echo "== 3/4 code rollback"
  if [ -f "$RB" ]; then
    read -r B H < "$RB"
    if [ "$B" = HEAD ]; then git checkout -q --detach "$H"; else git checkout -q -B "$B" "$H"; fi
    echo "code: $(git rev-parse --abbrev-ref HEAD) $(git rev-parse --short HEAD)"
  else
    echo "⚠️ $RB नाही — code तसाच ($(git rev-parse --short HEAD))"
  fi
  echo "== 4/4 restart"; restart_units
  python3 scripts/set_one_bot_mode.py --status || true
  exit 0
fi

echo "== 1/7 pull ($REF)"
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "❌ tracked बदल आहेत — deploy थांबवला:"; git status --short --untracked-files=no; exit 1; }
OLD=$(git rev-parse HEAD); CUR=$(git rev-parse --abbrev-ref HEAD)
[ -f "$RB" ] || echo "$CUR $OLD" > "$RB"
echo "rollback: $(cat "$RB")"
git fetch -q origin
W=$(mktemp -d); trap 'git worktree remove --force "$W" >/dev/null 2>&1 || true; rm -rf "$W"' EXIT
git worktree add -q --detach "$W" "$REF"
git diff --quiet "$OLD" "$REF" -- requirements.txt || python3 -m pip install -q -r "$W/requirements.txt"
( cd "$W" && python3 -c "import engine_signal, engine3_live, bots_common.one_bot, paper.engine_entry, vision.worker, srv2_momentum_reversal_strategy, trade_monitor, scripts.level_gate_preopen" >/dev/null ) \
  || { echo "❌ नव्या code चे imports अयशस्वी — काहीच बदललं नाही"; exit 1; }
git checkout -q -B deploy-main "$REF"
echo "code: $(git log -1 --oneline)"

echo "== 2/7 engine schedule"
bash scripts/install_engine_schedule.sh

echo "== 3/7 one-bot settings (before / after)"
set +e; python3 scripts/set_one_bot_mode.py; RC=$?; set -e
if [ "$RC" = 3 ]; then
  echo "❌ one-bot mode clean नाही (वरची ❌ ओळ = कारण) — deploy इथे थांबवला. Revert: bash scripts/deploy_one_bot.sh --revert"; exit 3
elif [ "$RC" != 0 ]; then
  echo "❌ set_one_bot_mode exit $RC — deploy थांबवला"; exit "$RC"
fi

echo "== 4/7 restart (असलेले units)"; restart_units
echo "== 5/7 pre-open (dry-run, Telegram नाही)"; python3 scripts/level_gate_preopen.py --dry-run || echo "⚠️ pre-open dry-run अयशस्वी"
echo "== 6/7 engine (dry-run, store / Telegram नाही)"; flock -n /tmp/engine_signal_run.lock python3 scripts/engine_signal_run.py --dry-run --force || echo "⚠️ engine dry-run: वरची ❌ ओळ पाहा"
echo "== 7/7 status"; python3 scripts/set_one_bot_mode.py --status || true
echo "engine cron: $(crontab -l | grep -c '# one-bot-engine$') ओळ · revert: bash scripts/deploy_one_bot.sh --revert"
