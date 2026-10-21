#!/usr/bin/env bash
# scripts/export_banknifty_history_vps.sh — Abhi (VPS, after the market close): BANKNIFTY history already on the VPS disk ⇒ private trade-data.
#   bash scripts/export_banknifty_history_vps.sh
# What it does:
#   0. market-hours check first (scripts/export_banknifty_history.py --guard-only; 08:30–15:35 IST on trading days ⇒ stop, nothing touched).
#   1. trade-data clone must be on `main` and `pull --ff-only` must work — else the clone is not touched and a tarball is made instead.
#   2. scripts/export_banknifty_history.py (READ-ONLY on the bot's files; no Upstox / paid call; BANKNIFTY only) writes ONE new folder:
#      $DATA/banknifty/vps_history/<IST date_time>/ (CSV.gz + manifest.json + README.md; written aside and renamed into place).
#   3. `git add --ignore-removal` + commit of THAT folder only; push origin HEAD:main (rejected ⇒ pull --rebase --autostash, as
#      vision_archive.py does, then push once more); then the remote's blob of every file is compared with the local file.
#      Committed but not pushable ⇒ NO tarball (the commit is in the clone; the nightly vision_archive push sends it — a tarball too
#      would land the folder twice); says so honestly.
# Never touches: the bot's data / DB / settings / .env / cron / services. Prints no secret (git's own credentials, never echoed).
# Env: TRADE (default /root/Trade), DATA (default $TRADE_DATA_DIR or /root/trade-data), TARDIR (tarball folder, default /root).
# Exit: 0 pushed + verified (or tarball written) · 1 error · 2 refused (market hours / folder exists) · 3 no BANKNIFTY data ·
#       4 committed in the clone, push pending (nightly push sends it — do NOT re-run).
set -uo pipefail
TRADE=${TRADE:-/root/Trade}
DATA=${DATA:-${TRADE_DATA_DIR:-/root/trade-data}}
TARDIR=${TARDIR:-/root}
STAMP=$(TZ=Asia/Kolkata date +%Y-%m-%d_%H%M)
REL="banknifty/vps_history/$STAMP"
G=(git -C "$DATA" -c user.name=vps-data-export -c user.email=vps-data-export@users.noreply.github.com
   -c advice.pushUpdateRejected=false -c advice.pushNonFFCurrent=false -c advice.skippedCherryPicks=false)

cd "$TRADE" || { echo "❌ $TRADE नाही"; exit 1; }
[ -f scripts/export_banknifty_history.py ] || { echo "❌ scripts/export_banknifty_history.py नाही — आधी नेहमीचा deploy (deploy_one_bot.sh) करा"; exit 1; }
echo "code: $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
python3 scripts/export_banknifty_history.py --guard-only || exit $?

PUSH=1
if [ ! -d "$DATA/.git" ]; then
  echo "⚠️ $DATA trade-data clone नाही ⇒ tarball"; PUSH=0
elif [ "$(git -C "$DATA" symbolic-ref --short -q HEAD)" != "main" ]; then
  echo "⚠️ trade-data clone 'main' branch वर नाही ($(git -C "$DATA" symbolic-ref --short -q HEAD || echo detached)) ⇒ clone ला हात नाही, tarball"; PUSH=0
elif ! "${G[@]}" pull -q --ff-only origin main; then
  echo "⚠️ trade-data pull --ff-only जमला नाही (local commits?) ⇒ clone ला हात नाही, tarball"; PUSH=0
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
pending() {   # committed locally, not on the remote: no tarball (it would land twice)
  echo "⏳ commit $("${G[@]}" rev-parse --short HEAD) ($REL) trade-data clone मध्ये आहे, पण push झाला नाही: $1"
  echo "   रात्रीचा vision_archive push (23:50 IST, fetch + rebase --autostash + push) तो पाठवेल; त्याचा rebase पण अडकला तर तो Telegram वर ⚠️ पाठवतो"
  echo "   — मग Claude ला सांगा. हा command पुन्हा चालवू नका (folder दोनदा येईल)."
  echo "   उद्या तपासा: git -C $DATA fetch -q origin main && git -C $DATA ls-tree --name-only FETCH_HEAD -- $REL"
  exit 4
}

if [ "$PUSH" = 0 ]; then tarball; exit 0; fi

move_out() {  # not committed ⇒ take the folder OUT of the clone (a later `git add -A` there must not push it too), then tarball
  "${G[@]}" reset -q -- "$REL" >/dev/null 2>&1
  mkdir -p "$TARDIR/banknifty_history_export" && mv "$OUT" "$TARDIR/banknifty_history_export/$STAMP" && OUT="$TARDIR/banknifty_history_export/$STAMP"
  echo "   folder clone बाहेर हलवला: $OUT"; tarball
}
"${G[@]}" add --ignore-removal -- "$REL" || { echo "❌ git add अयशस्वी — commit नाही"; move_out; exit 1; }
"${G[@]}" commit -q -m "banknifty/vps_history/$STAMP: BANKNIFTY history from the VPS (read-only export)" -- "$REL" \
  || { echo "❌ commit अयशस्वी — commit नाही"; move_out; exit 1; }
if ! "${G[@]}" push -q origin HEAD:main; then
  echo "↻ push नाकारला — pull --rebase --autostash करून एकदा पुन्हा"
  if ! "${G[@]}" pull -q --rebase --autostash origin main; then
    "${G[@]}" rebase --abort >/dev/null 2>&1
    pending "rebase जमला नाही"
  fi
  "${G[@]}" push -q origin HEAD:main || pending "दुसरा push पण नाकारला"
fi

if ! "${G[@]}" fetch -q origin main; then
  echo "⚠️ push झाला, पण पडताळणीचा fetch अयशस्वी — remote तपासता आला नाही (tarball नाही: data push झाला आहे)."
  echo "   नंतर तपासा: git -C $DATA fetch -q origin main && git -C $DATA ls-tree --name-only FETCH_HEAD -- $REL"
  exit 1
fi
N=0; BAD=()
while IFS= read -r -d '' f; do
  rel=${f#"$DATA/"}; N=$((N + 1))
  loc=$("${G[@]}" hash-object -- "$rel")
  rem=$("${G[@]}" rev-parse -q --verify "FETCH_HEAD:$rel" 2>/dev/null || true)
  [ -n "$loc" ] && [ "$loc" = "$rem" ] || BAD+=("$rel")
done < <(find "$OUT" -type f -print0)
if [ "$N" -gt 0 ] && [ "${#BAD[@]}" = 0 ]; then
  echo "✅ trade-data push पक्की: $REL ($N files, प्रत्येक file चा remote blob = local) · commit $("${G[@]}" rev-parse --short FETCH_HEAD)"
else
  echo "❌ remote मध्ये नाहीत / वेगळ्या: ${#BAD[@]} / $N (${BAD[*]:0:5})"; exit 1
fi
