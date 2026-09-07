# Engine Service — Deployment (Phase 1: Position Monitoring)

`engine_service.py` established SL/Target/EOD मॉनिटरिंग आता Dashboard (Streamlit) पासून पूर्ण
स्वतंत्र, systemd timer वर दर १ मिनिटाला चालतं — ब्राउझर बंद असला तरी चालू राहतं.

## एकदाच सेटअप (droplet वर, root किंवा sudo सह):

```bash
# 1. paths जुळवा — तुमचा प्रोजेक्ट फोल्डर वेगळा असेल तर engine_service.service मधले दोन्ही path बदला
cp deploy/engine_service.service /etc/systemd/system/
cp deploy/engine_service.timer /etc/systemd/system/

# 2. Secrets साठी .env फाईल (git मध्ये commit करू नका — .gitignore मध्ये जोडा)
cat > /root/amw_a1_trading_system/.env << 'EOF'
SUPABASE_DB_URL=postgresql://postgres:xxxx@db.xxxx.supabase.co:5432/postgres
TELEGRAM_BOT_TOKEN=xxxxx
TELEGRAM_CHAT_ID=xxxxx
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
`data/heartbeats/engine_service.txt` — प्रत्येक यशस्वी run नंतर अपडेट होते. यावर आधीपासूनच
`notifications.check_heartbeat_stale("engine_service", max_age_minutes=30)` वापरून वेगळा alert
जोडता येईल (हवं असल्यास पुढच्या टप्प्यात).

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
