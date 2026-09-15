# Engine Service — Deployment (Phase 1: Position Monitoring)

`engine_service.py` established SL/Target/EOD मॉनिटरिंग आता Dashboard (Streamlit) पासून पूर्ण
स्वतंत्र, systemd timer वर दर १ मिनिटाला चालतं — ब्राउझर बंद असला तरी चालू राहतं.

## एकदाच सेटअप (droplet वर, root किंवा sudo सह):

```bash
# 1. paths जुळवा — तुमचा प्रोजेक्ट फोल्डर वेगळा असेल तर engine_service.service मधले दोन्ही path बदला
cp deploy/engine_service.service /etc/systemd/system/
cp deploy/engine_service.timer /etc/systemd/system/

# 2. Secrets साठी .env फाईल (आता .gitignore मध्ये आधीच वगळलेली — चुकूनही कमिट होणार नाही)
cat > /root/amw_a1_trading_system/.env << 'EOF'
SUPABASE_DB_URL=postgresql://postgres:xxxx@db.xxxx.supabase.co:5432/postgres
TELEGRAM_BOT_TOKEN=xxxxx
TELEGRAM_CHAT_ID=xxxxx
# ऐच्छिक — बाह्य uptime-monitor (healthchecks.io / UptimeRobot चा "push monitor" — मोफत) ping URL.
# सेट केलं तर, VPS स्वतःच बंद पडला (वीज/नेट/क्रॅश) तरीही तुम्हाला कळेल — local heartbeat फाईल
# तेव्हा कुणालाच दिसत नाही, पण बाह्य सेवेला ping न आल्याने तीच अलर्ट पाठवेल.
# सर्व scripts साठी समान एक:
HEALTHCHECK_PING_URL=https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# — किंवा प्रत्येक script साठी वेगळा (script-specific तो आधी वापरला जातो):
# HEALTHCHECK_PING_URL_ENGINE_SERVICE=https://hc-ping.com/...
EOF
chmod 600 /root/amw_a1_trading_system/.env

# 3. आवश्यक Python packages (dashboard साठी आधीच असतील — तरी खात्री करा)
pip install -r /root/amw_a1_trading_system/requirements.txt

# 4. systemd ला नवीन units दिसण्यासाठी
systemctl daemon-reload

# 5. timer सुरू करा (आणि reboot नंतरही आपोआप सुरू व्हावा म्हणून enable)
systemctl enable --now engine_service.timer

# 6. तपासणी
systemctl status engine_service.timer
systemctl list-timers | grep engine_service
```

## मॅन्युअली एकदा चालवून बघायचं असेल (टेस्टसाठी):
```bash
systemctl start engine_service.service
journalctl -u engine_service.service -n 50 --no-pager
```

## Heartbeat तपासणी (script खरंच धावतेय की अडकलीये):
दोन स्वतंत्र मार्ग, दोन्ही एकत्र वापरणं उत्तम:
1. **Local फाईल** — `data/heartbeats/engine_service.txt`, प्रत्येक यशस्वी run नंतर अपडेट होते.
   Dashboard याच VPS वर चालत असेल तरच Reports टॅबवरच्या "Auto-Trader Health Check" मध्ये दिसेल —
   Dashboard वेगळ्या होस्टवर (उदा. Streamlit Cloud) असेल तर हे तिथे कधीच दिसणार नाही.
2. **बाह्य ping** (वर `.env` मध्ये `HEALTHCHECK_PING_URL` सेट केलं असेल तर) — प्रत्येक यशस्वी run
   नंतर आपोआप healthchecks.io/UptimeRobot ला ping जातो; ती सेवा ठराविक वेळेत ping न आल्यास स्वतः
   Telegram/Email/SMS अलर्ट पाठवते — VPS स्वतःच बंद पडला तरी हे काम करतं, म्हणून production साठी
   हाच जास्त विश्वासार्ह मार्ग.

## ⚠️ 1GB RAM droplet — महत्त्वाची सूचना
हा script "single-shot" आहे (प्रत्येक वेळी नवीन प्रोसेस, systemd timer ट्रिगर करतं) — म्हणजे मेमरी
साचत नाही. तरीही स्वतंत्र सुरक्षा-जाळी म्हणून swap file नसेल तर आधी सेटअप करा:

```bash
fallocate -l 1G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```
