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

---

# Upstox Token Webhook — Deployment (1-Tap Mobile Approval)

`trigger_upstox_token_request.py` (GitHub Actions, रोज सकाळी ०८:०० IST) Upstox ला "आजचा token हवा"
अशी विनंती पाठवतो — तुमच्या मोबाईलवर Upstox app मध्ये notification येते, एका टॅपने Approve केलं की
Upstox तो token एका webhook URL ला POST करतो. `upstox_token_webhook.py` (VPS वर, Flask) तो POST
स्वीकारून Supabase मध्ये साठवतो — कुठेही manual copy-paste लागत नाही.

⚠️ **महत्त्वाचं** — `upstox_token_webhook.py` चा स्वतःचा server (`app.run()`) plain HTTP आहे, TLS/SSL
नाही. `https://VPS-IP:8080` असं थेट URL Upstox ला दिलं तर तो **खरं HTTPS होत नाही** (TLS handshake
वरच अयशस्वी होतो) — Upstox चा webhook-delivery बहुतेक अयशस्वी होईल. यासाठी **cloudflared** (Cloudflare
Tunnel) वापरून, त्याच्याकडूनच खरं, विश्वासार्ह (publicly trusted) HTTPS मिळवतो — Flask ला कुठलाही
SSL बदल करावा लागत नाही.

## एकदाच सेटअप (droplet वर, root किंवा sudo सह):

```bash
# 1. cloudflared इंस्टॉल करणे
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb

# 2. दोन्ही systemd unit files copy करणे — paths जुळवा (तुमचा प्रोजेक्ट फोल्डर वेगळा असेल तर बदला)
cp deploy/upstox_token_webhook.service /etc/systemd/system/
cp deploy/cloudflared_upstox_webhook.service /etc/systemd/system/

# 3. systemd ला नवीन units दिसण्यासाठी
systemctl daemon-reload

# 4. दोन्ही सुरू करा (आणि reboot नंतरही आपोआप सुरू व्हावेत म्हणून enable)
systemctl enable --now upstox_token_webhook.service
systemctl enable --now cloudflared_upstox_webhook.service

# 5. तपासणी — दोन्ही "active (running)" दिसायला हवेत
systemctl status upstox_token_webhook.service
systemctl status cloudflared_upstox_webhook.service
```

## तुमची नवीन, खरी HTTPS URL शोधणे:
```bash
journalctl -u cloudflared_upstox_webhook -n 20 --no-pager | grep trycloudflare
```
यात `https://xxxx-xxx-xxx.trycloudflare.com` असं काहीतरी दिसेल — **हीच** URL (शेवटी `/upstox-webhook`
जोडून, उदा. `https://xxxx-xxx-xxx.trycloudflare.com/upstox-webhook`) पुढच्या पायरीत Upstox कडे
नोंदवायची आहे.

## Upstox Developer Console मध्ये Notifier URL नोंदवणे (एकदाच, मॅन्युअली):
1. https://account.upstox.com/developer/apps वर जा, तुमचं App उघडा.
2. "Notifier URL" (किंवा "Redirect/Webhook URL") field मध्ये वरची URL पेस्ट करा, Save करा.

## ⚠️ URL बदलते (Quick Tunnel ची मर्यादा):
ही "Quick Tunnel" पद्धत मोफत आहे, कुठलंही Cloudflare account/domain लागत नाही — पण
`cloudflared_upstox_webhook.service` कधीही (re)start झाला (उदा. VPS reboot, क्रॅश) की **नवीन** URL
मिळते. तेव्हा वरची "URL शोधणे" पायरी पुन्हा करून, Upstox Console मध्येही अपडेट करावी लागेल.

कायमस्वरूपी, कधीच न बदलणारी URL हवी असल्यास — तुमच्याकडे स्वतःचं domain असेल तर **Cloudflare Named
Tunnel** वापरा (Cloudflare Dashboard → Zero Trust → Networks → Tunnels मधून एकदा तयार करून, एक
कायमचा subdomain — उदा. `upstox-webhook.तुमचंdomain.com` — त्याला जोडता येतो; त्यानंतर हीच URL कधीच
बदलत नाही, reboot झाला तरी).

## मॅन्युअली टेस्ट करायचं असेल:
```bash
systemctl restart upstox_token_webhook.service cloudflared_upstox_webhook.service
journalctl -u cloudflared_upstox_webhook -n 20 --no-pager
journalctl -u upstox_token_webhook -n 20 --no-pager
curl http://localhost:8080/health   # स्थानिक (VPS वरूनच) तपासणी — {"status":"ok"} यायला हवं
```
