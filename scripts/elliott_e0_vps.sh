#!/usr/bin/env bash
# scripts/elliott_e0_vps.sh — Elliott E0: VPS वरचा data export (फक्त वाचन; order/DB write नाही).
# 🎓 Destination फक्त private `trade-data` repo (deploy key: ssh alias "github-trade-data", IdentityFile ~/.ssh/trade_data_key).
#    Public Trade repo मध्ये डेटा कधीच नाही. 15:30 IST नंतर चालवायचा (weekday ला आधी चालवला तर थांबतो; FORCE=1 ने override).
# पायऱ्या: trade-data clone/pull → Upstox expired-API probe → golden NIFTY 1m → major-levels candles → BANKNIFTY daily CSV copy →
#          push → data check + BANKNIFTY अहवाल (paste करायला) → NSE bhavcopy background मध्ये (~1 तास; संपल्यावर push + सारांश).
#          शेवटी या run मध्ये काय push झालं त्याचा सारांश.
set -u
TRADE=${TRADE:-/root/Trade}
DATA=${DATA:-/root/trade-data}
KEY=${KEY:-$HOME/.ssh/trade_data_key}
HOST=github-trade-data
REMOTE=${REMOTE:-"git@${HOST}:abhishekwasu-hue/trade-data.git"}
export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new"

HM=$(TZ=Asia/Kolkata date +%H%M); DOW=$(TZ=Asia/Kolkata date +%u)
if [ "${FORCE:-0}" != "1" ] && [ "$DOW" -le 5 ] && [ "$HM" -ge 900 ] && [ "$HM" -lt 1530 ]; then
  echo "⏳ बाजार चालू आहे — 15:30 IST नंतर चालवा (FORCE=1 ने override)"; exit 1
fi

# ---------------------------------------------------------------- deploy key / ssh alias
if ! grep -q "^Host $HOST\$" "$HOME/.ssh/config" 2>/dev/null; then
  if [ -f "$KEY" ]; then
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    printf 'Host %s\n  HostName github.com\n  User git\n  IdentityFile %s\n  IdentitiesOnly yes\n' "$HOST" "$KEY" >> "$HOME/.ssh/config"
    chmod 600 "$HOME/.ssh/config"
  else
    echo "❌ ssh alias '$HOST' आणि key $KEY दोन्ही नाहीत. एकदा:"
    echo "   ssh-keygen -t ed25519 -N '' -f $KEY && cat $KEY.pub"
    echo "   → https://github.com/abhishekwasu-hue/trade-data/settings/keys/new (✔ Allow write access), मग हाच command पुन्हा."
    exit 3
  fi
fi
if ! git ls-remote "$REMOTE" >/dev/null 2>&1; then
  echo "❌ $REMOTE पोहोचत नाही — deploy key trade-data मध्ये (write access सह) जोडली आहे का तपासा: ssh -T $HOST"
  exit 3
fi

# ---------------------------------------------------------------- trade-data checkout
if [ ! -d "$DATA/.git" ]; then
  git clone -q "$REMOTE" "$DATA" || { echo "❌ clone अयशस्वी"; exit 4; }
fi
git -C "$DATA" remote set-url origin "$REMOTE"
git -C "$DATA" config user.name "vps-data-export"
git -C "$DATA" config user.email "vps-data-export@users.noreply.github.com"
git -C "$DATA" pull -q --ff-only origin main 2>/dev/null || true
BEFORE=$(git -C "$DATA" rev-parse -q --verify HEAD 2>/dev/null || echo "")

push_data() {
  git -C "$DATA" add -A
  if ! git -C "$DATA" diff --cached --quiet; then
    git -C "$DATA" commit -qm "$1" && git -C "$DATA" push -q origin HEAD:main && echo "⬆️  push: $1"
  fi
}

summary() {   # $1 = पासून (commit किंवा रिकामं)
  echo "── push सारांश (trade-data):"
  local range=${1:+$1..}HEAD
  [ -n "$(git -C "$DATA" rev-parse -q --verify HEAD 2>/dev/null)" ] || { echo "   (काहीच नाही)"; return; }
  if [ -n "${1:-}" ] && [ "$1" = "$(git -C "$DATA" rev-parse HEAD)" ]; then echo "   (या run मध्ये नवीन काही नाही)"; return; fi
  git -C "$DATA" log --format='   %h %s' $range
  git -C "$DATA" diff --stat=100 ${1:-$(git -C "$DATA" hash-object -t tree /dev/null)} HEAD | tail -1 | sed 's/^/   /'
  for d in probes upstox major_levels_candles banknifty nse_fo_bhavcopy/NIFTY nse_fo_bhavcopy/NIFTY_golden; do
    [ -e "$DATA/$d" ] && printf '   %-28s %s\n' "$d" "$(du -sh "$DATA/$d" | cut -f1)"
  done
}

# ---------------------------------------------------------------- export (read-only)
cd "$TRADE" || exit 5
echo "── Elliott E0 ($(date '+%F %T'))"
python3 research/elliott_vps_data.py --repo "$DATA" probe-expired
python3 research/elliott_vps_data.py --repo "$DATA" golden
python3 research/elliott_vps_data.py --repo "$DATA" major-levels
BN=data/research/BANKNIFTY_daily_2015_2024-03.csv
if [ -f "$BN" ]; then
  mkdir -p "$DATA/banknifty" && cp -p "$BN" "$DATA/banknifty/"
  echo "✅ BANKNIFTY daily CSV → trade-data/banknifty/"
fi
push_data "E0: Upstox probe + golden NIFTY 1m + major-levels candles + BANKNIFTY daily"
python3 research/elliott_data_check.py --data "$DATA"
if [ -f "$BN" ]; then
  echo "── BANKNIFTY स्वतंत्र चाचणी"
  python3 research/banknifty_independent_test.py --csv "$BN"
fi
summary "$BEFORE"

LOG=/root/elliott_bhavcopy.log
nohup bash -c "cd '$TRADE' && python3 research/elliott_vps_data.py --repo '$DATA' bhavcopy; \
  B=\$(git -C '$DATA' rev-parse HEAD); git -C '$DATA' add -A; git -C '$DATA' diff --cached --quiet || \
  (git -C '$DATA' commit -qm 'E0: NSE F&O bhavcopy (NIFTY)' && git -C '$DATA' push -q origin HEAD:main && echo '⬆️ pushed'); \
  git -C '$DATA' diff --stat \$B HEAD | tail -1; du -sh '$DATA/nse_fo_bhavcopy' 2>/dev/null; echo DONE" > "$LOG" 2>&1 &
echo "── NSE bhavcopy background मध्ये (~1 तास). प्रगती/सारांश: tail -5 $LOG   (DONE दिसलं की पूर्ण)"
