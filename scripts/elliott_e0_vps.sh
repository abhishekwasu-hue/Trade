#!/usr/bin/env bash
# scripts/elliott_e0_vps.sh — Elliott E0: VPS वरचा data export (फक्त वाचन; order/DB write नाही).
# 🎓 Destination फक्त private `trade-data` repo (deploy key ने push). Public Trade repo मध्ये डेटा कधीच नाही.
# पुन्हा-पुन्हा चालवता येतो (idempotent):
#   1) पहिल्यांदा deploy key तयार करून public key दाखवतो आणि थांबतो (exit 3). Key GitHub वर जोडल्यावर हाच command पुन्हा.
#   2) नंतर: trade-data clone → Upstox expired-API probe → golden NIFTY 1m → major-levels candles → push →
#      data check + BANKNIFTY अहवाल (stdout, paste करायला) → NSE bhavcopy background मध्ये (~1 तास), संपल्यावर push.
set -u
TRADE=${TRADE:-/root/Trade}
DATA=${DATA:-/root/trade-data}
KEY=$HOME/.ssh/trade_data_deploy
HOST=github-trade-data
REMOTE="git@${HOST}:abhishekwasu-hue/trade-data.git"
export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new"

command -v ssh-keygen >/dev/null || { echo "❌ ssh-keygen नाही — sudo apt install -y openssh-client"; exit 6; }
mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
[ -f "$KEY" ] || ssh-keygen -q -t ed25519 -N "" -C "vps-trade-data-deploy" -f "$KEY"
if ! grep -q "^Host $HOST\$" "$HOME/.ssh/config" 2>/dev/null; then
  printf 'Host %s\n  HostName github.com\n  User git\n  IdentityFile %s\n  IdentitiesOnly yes\n' "$HOST" "$KEY" >> "$HOME/.ssh/config"
fi
chmod 600 "$HOME/.ssh/config"

if ! git ls-remote "$REMOTE" >/dev/null 2>&1; then
  echo "🔑 पहिली पायरी: ही public key trade-data repo मध्ये Deploy key म्हणून जोडा (✔ Allow write access):"
  echo "   https://github.com/abhishekwasu-hue/trade-data/settings/keys/new"
  echo
  cat "$KEY.pub"
  echo
  echo "जोडल्यावर हाच command पुन्हा चालवा."
  exit 3
fi

if [ ! -d "$DATA/.git" ]; then
  git clone -q "$REMOTE" "$DATA" || { echo "❌ clone अयशस्वी"; exit 4; }
fi
git -C "$DATA" config user.name "vps-data-export"
git -C "$DATA" config user.email "vps-data-export@users.noreply.github.com"
git -C "$DATA" pull -q --ff-only origin main 2>/dev/null || true

push_data() {
  git -C "$DATA" add -A
  if ! git -C "$DATA" diff --cached --quiet; then
    git -C "$DATA" commit -qm "$1" && git -C "$DATA" push -q origin HEAD:main && echo "⬆️  trade-data push: $1"
  fi
}

cd "$TRADE" || exit 5
echo "── Elliott E0 ($(date '+%F %T'))"
python3 research/elliott_vps_data.py --repo "$DATA" probe-expired
python3 research/elliott_vps_data.py --repo "$DATA" golden
python3 research/elliott_vps_data.py --repo "$DATA" major-levels
push_data "E0: Upstox probe + golden NIFTY 1m + major-levels candles"
python3 research/elliott_data_check.py --data "$DATA"

BN=data/research/BANKNIFTY_daily_2015_2024-03.csv
if [ -f "$BN" ]; then
  echo "── BANKNIFTY स्वतंत्र चाचणी"
  python3 research/banknifty_independent_test.py --csv "$BN"
fi

LOG=/root/elliott_bhavcopy.log
nohup bash -c "cd '$TRADE' && python3 research/elliott_vps_data.py --repo '$DATA' bhavcopy; \
  git -C '$DATA' add -A; git -C '$DATA' diff --cached --quiet || \
  (git -C '$DATA' commit -qm 'E0: NSE F&O bhavcopy (NIFTY)' && git -C '$DATA' push -q origin HEAD:main && echo '⬆️ pushed'); \
  echo DONE" > "$LOG" 2>&1 &
echo "── NSE bhavcopy background मध्ये चालू (~1 तास). प्रगती: tail -3 $LOG   (DONE दिसलं की पूर्ण)"
