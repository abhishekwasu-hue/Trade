#!/usr/bin/env bash
# scripts/export_banknifty_history_vps.sh — Abhi (VPS, after the market close): BANKNIFTY history already on the VPS disk ⇒ private trade-data.
#   bash scripts/export_banknifty_history_vps.sh
# What it does:
#   1. scripts/export_banknifty_history.py (READ-ONLY on the bot's files; no Upstox / paid call; BANKNIFTY only; refuses 08:30–15:35 IST
#      on trading days) writes ONE new folder: $DATA/banknifty/vps_history/<IST date_time>/ (CSV.gz + manifest.json + README.md).
#   2. trade-data: pull --ff-only first; then `git add --ignore-removal` + commit of THAT folder only; push origin HEAD:main; checks the
#      remote has every file. Push not possible (no clone / pull or push fails) ⇒ a tarball path to copy instead (nothing is lost).
# Never touches: the bot's data / DB / settings / .env / cron / services. Prints no secret (git's own credentials, never echoed).
# Env: TRADE (default /root/Trade), DATA (default $TRADE_DATA_DIR or /root/trade-data), TARDIR (tarball folder, default /root).
set -uo pipefail
TRADE=${TRADE:-/root/Trade}
DATA=${DATA:-${TRADE_DATA_DIR:-/root/trade-data}}
TARDIR=${TARDIR:-/root}
STAMP=$(TZ=Asia/Kolkata date +%Y-%m-%d_%H%M)
REL="banknifty/vps_history/$STAMP"
G=(git -C "$DATA" -c user.name=vps-data-export -c user.email=vps-data-export@users.noreply.github.com)

cd "$TRADE" || { echo "❌ $TRADE नाही"; exit 1; }
[ -f scripts/export_banknifty_history.py ] || { echo "❌ scripts/export_banknifty_history.py नाही — आधी नेहमीचा deploy (deploy_one_bot.sh) करा"; exit 1; }
echo "code: $(git rev-parse --short HEAD 2>/dev/null || echo '?')"

PUSH=1
if [ ! -d "$DATA/.git" ]; then
  echo "⚠️ $DATA trade-data clone नाही ⇒ tarball"; PUSH=0
elif ! "${G[@]}" pull -q --ff-only origin main; then
  echo "⚠️ trade-data pull --ff-only जमला नाही (local बदल / commits?) ⇒ clone ला हात नाही, tarball"; PUSH=0
fi
if [ "$PUSH" = 1 ]; then OUT="$DATA/$REL"; else OUT="$TARDIR/banknifty_history_export/$STAMP"; fi

NICE=(nice -n 19); command -v ionice >/dev/null 2>&1 && NICE+=(ionice -c3)
"${NICE[@]}" python3 scripts/export_banknifty_history.py --out-dir "$OUT"
RC=$?
if [ "$RC" != 0 ]; then echo "❌ export थांबला (exit $RC) — trade-data ला काहीच commit / push नाही"; exit "$RC"; fi

tarball() {
  local T="$TARDIR/banknifty_history_$STAMP.tgz"
  tar czf "$T" -C "$(dirname "$OUT")" "$(basename "$OUT")" && echo "📦 tarball: $T  sha256 $(sha256sum "$T" | cut -d' ' -f1)" \
    && echo "   हा file laptop वर copy करा (उदा. scp root@<VPS>:$T .) आणि Claude ला द्या — तो trade-data मध्ये टाकेल."
}

if [ "$PUSH" = 1 ]; then
  N=$(find "$OUT" -type f | wc -l)
  "${G[@]}" add --ignore-removal -- "$REL" && "${G[@]}" commit -q -m "banknifty/vps_history/$STAMP: BANKNIFTY history from the VPS (read-only export)" -- "$REL" \
    || { echo "❌ commit अयशस्वी"; tarball; exit 1; }
  if ! "${G[@]}" push -q origin HEAD:main; then
    echo "↻ push नाकारला — pull --rebase करून एकदा पुन्हा"
    if ! "${G[@]}" pull -q --rebase origin main; then "${G[@]}" rebase --abort >/dev/null 2>&1; echo "❌ rebase जमला नाही"; tarball; exit 1; fi
    "${G[@]}" push -q origin HEAD:main || { echo "❌ push अयशस्वी"; tarball; exit 1; }
  fi
  "${G[@]}" fetch -q origin main
  R=$("${G[@]}" ls-tree -r --name-only FETCH_HEAD -- "$REL" | wc -l)
  if [ "$R" = "$N" ]; then
    echo "✅ trade-data push पक्की: $REL ($R files) · commit $("${G[@]}" rev-parse --short FETCH_HEAD)"
  else
    echo "❌ remote मध्ये $R / $N files"; tarball; exit 1
  fi
else
  tarball
fi
