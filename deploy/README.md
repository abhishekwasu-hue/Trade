# ⚠️ प्रत्यक्षात काय चालू आहे (VPS वर पडताळलेलं, महत्त्वाचं)

Position-exit monitoring साठी codebase मध्ये **दोन** स्वतंत्र script आहेत — `engine_service.py`
(हा systemd timer) आणि `trade_monitor.py` (crontab). दोघेही एकाच वेळी चालू असतील तर एकच trade
दोनदा बंद होण्याचा धोका होता (आता `ProcessLock` मुळे तसं होणार नाही, पण दोन्ही चालू ठेवणं
गोंधळाचं आणि निरर्थक आहे — फक्त एकच खरा असायला हवा).

**पडताळणी (२०२६-०९-१९, प्रत्यक्ष VPS वर):**
```
$ systemctl status engine_service.timer
     Loaded: loaded (...; disabled; preset: enabled)
     Active: inactive (dead)
# ०७ सप्टेंबरपासून बंद, पुन्हा सुरूच केलेलं नाही.

$ crontab -l | grep trade_monitor
45-59 3 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
# दर मिनिटाला, ९:१५ सकाळी ते ~४:२९ संध्याकाळ IST, सोम-शुक्र — चालूच आहे.
```

**निष्कर्ष — `trade_monitor.py` (crontab) हाच खरा, सक्रिय exit-monitoring मार्ग आहे.
`engine_service.timer` निष्क्रिय आहे — खालच्या "Engine Service" सूचना फक्त ऐतिहासिक/संदर्भासाठी
ठेवलेल्या आहेत. `engine_service.timer` परत कधीच `systemctl enable --now` करू नका — ते
`trade_monitor.py` शीच डुप्लिकेट होईल.** Crontab च्या सेटअपसाठी खाली "Trade Monitor — प्रत्यक्ष
Deployment (crontab)" बघा.

---

# Engine Service — Deployment (Phase 1: Position Monitoring) — ⚠️ सध्या निष्क्रिय, फक्त संदर्भासाठी

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

# Trade Monitor — प्रत्यक्ष Deployment (crontab) — ⚠️ हाच खरा, सक्रिय मार्ग

`trade_monitor.py` (crontab, VPS वर दर मिनिटाला) — SL/Target/EOD/TSL/Carry-Forward/Next-Level-Exit/
PCR Gate सकट संपूर्ण आधुनिक exit-logic (`trading_engine.manage_open_trades()`) प्रत्यक्षात इथूनच
चालते. `engine_service.py` मधलेच काही shared helpers (`load_settings`/`compute_atr_points`/
`MONITORED_SYMBOLS`) import करते, पण स्वतःचा systemd timer वापरत नाही — cron नियंत्रित करतो.

**सद्य crontab (VPS वर `crontab -l` ने पडताळलेलं, वेळा UTC मध्ये — VPS ची timezone
`timedatectl`/`date` ने आधी खात्री करूनच बदल करा):**
```
45-59 3 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
```
म्हणजे दर मिनिटाला, सकाळी ९:१५ ते संध्याकाळी ~४:२९ IST, सोमवार-शुक्रवार (UTC 3:45 ते 10:59 शी
समतुल्य) — भारतीय बाजाराच्या पूर्ण सत्रभर.

**तपासणी:**
```bash
tail -f /root/Trade/monitor.log
crontab -l | grep trade_monitor
```

**⚠️ `engine_service.timer` परत सुरू करण्याआधी** — आधी हा crontab entry काढून टाका (किंवा
उलट) — दोन्ही एकाच वेळी चालू ठेवू नका.

---

# Entry-Signal Bots + Dynamic S/R Refresh — Deployment (crontab)

`refresh_dynamic_sr_1m.py`/`_5m.py` (Dynamic S/R levels, candle-आधारित), `oi_snapshot_collector.py`,
आणि तीन entry bots — `srv2_momentum_reversal_strategy.py`, `dynamic_sr_instant_trader.py`, व
`classic_sr_reversal_trader.py` — हे सर्व VPS वरच्या crontab मधूनच चालतात (कुठलाही systemd
timer/service नाही).

⚠️ **`refresh_dynamic_sr_15m.py` हा file या repo मध्ये कधीच अस्तित्वातच नव्हता** — तो VPS crontab
मध्ये चुकून जोडलेला होता, आणि दर 5 मिनिटांनी फक्त "No such file or directory" error देत होता,
काहीही न करता (`refresh_15m.log` बघा). **15M/30M/60M Dynamic S/R फक्त रोज रात्री एकदाच
`refresh_market_zones.py` द्वारे अपडेट होतात** (हीच रचना मुद्दाम आहे — खाली बघा) — त्यामुळे ती चुकीची
crontab line VPS वरून **काढून टाका**, नवीन काही जोडायची गरज नाही.

**शिफारस केलेला crontab (9:16 ऐवजी 9:15 पासून सुरू होणारा, खालच्या "टायमिंग-चूक" भागात सांगितलेला
fix आधीच लागू केलेला — वेळा UTC मध्ये, `crontab -e` मध्ये पेस्ट करा):**
```
*/5 3-10 * * 1-5 cd /root/Trade && python3 refresh_dynamic_sr_5m.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/refresh_5m.log 2>&1
*/5 3-10 * * 1-5 cd /root/Trade && python3 refresh_dynamic_sr_1m.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/refresh_1m.log 2>&1
*/5 3-10 * * 1-5 cd /root/Trade && python3 oi_snapshot_collector.py >> /root/Trade/oi_snapshot.log 2>&1
45-59 3 * * 1-5 cd /root/Trade && sleep 30 && python3 srv2_momentum_reversal_strategy.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/srv2.log 2>&1
* 4-10 * * 1-5 cd /root/Trade && sleep 30 && python3 srv2_momentum_reversal_strategy.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/srv2.log 2>&1
45-59 3 * * 1-5 cd /root/Trade && sleep 15 && python3 dynamic_sr_instant_trader.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/dsr.log 2>&1
* 4-10 * * 1-5 cd /root/Trade && sleep 15 && python3 dynamic_sr_instant_trader.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/dsr.log 2>&1
45-59 3 * * 1-5 cd /root/Trade && sleep 45 && python3 classic_sr_reversal_trader.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/classic_sr.log 2>&1
* 4-10 * * 1-5 cd /root/Trade && sleep 45 && python3 classic_sr_reversal_trader.py --symbols NIFTY,BANKNIFTY,SENSEX >> /root/Trade/classic_sr.log 2>&1
```
`sleep 0/15/30/45` — `trade_monitor.py` (लगेच), `dynamic_sr_instant_trader.py` (15s), `srv2_momentum_reversal_strategy.py`
(30s), `classic_sr_reversal_trader.py` (45s) — असे टप्प्याटप्प्याने, Upstox API वर एकाच क्षणी गर्दी
होऊ नये म्हणून.

⚠️ **`classic_sr_reversal_trader.py` चा `symbol_enabled` डीफॉल्ट सर्व symbols साठी बंद आहे**
(backtest-टप्प्यातली strategy असल्याने, `cloud_db.py` मधला मुद्दाम ठेवलेला safety default) — वरचं
crontab जोडलं तरी, Dashboard च्या Bot Dynamic SR Algo पानावरून "🎯 Classical S/R Reversal" strategy
साठी हवा तो symbol स्पष्टपणे सक्रिय (checkbox) केल्याशिवाय कुठलाही trade (PAPER सुद्धा) घेतला जाणार
नाही — script चालतच राहील, पण दरवेळी "symbol बंद आहे" म्हणून थांबेल.

## 🎓 वापरकर्त्याने सापडवलेली टायमिंग-चूक (इतिहास) — entry bots आधी 9:15 ऐवजी 9:16 ला सुरू व्हायचे

मूळ crontab मध्ये `srv2_momentum_reversal_strategy.py`/`dynamic_sr_instant_trader.py` चा पहिला run
`46-59 3 * * 1-5` (UTC 3:46 = IST **9:16**) होता — `refresh_dynamic_sr_*.py`/`oi_snapshot_collector.py`
सारखाच, जे candle-आधारित असल्याने 9:16 (पहिला पूर्ण 1-मिनिट candle तेव्हाच बंद होतो) पर्यंत थांबावंच
लागतं. पण हे दोन्ही entry bots candle ची वाट न बघता **थेट live LTP** level ला touch झाला का हे
तपासतात — त्यामुळे बाजार उघडल्यावरचा पहिला, अनेकदा सर्वात मोठ्या हालचालीचा मिनिट (9:15-9:16) आधी
पूर्णपणे चुकायचा. वरच्या "शिफारस केलेला crontab" मध्ये हा fix (`46-59` → `45-59`, `trade_monitor.py`
सारखंच) आधीच लागू केलेला आहे — `classic_sr_reversal_trader.py` नव्यानेच जोडताना सुरुवातीपासूनच
बरोबर वेळेत (9:15) जोडलेली आहे, त्याला हा जुना बगच कधी लागला नव्हता.

⚠️ Note: **F&O (options) ला pre-open session नाही** (फक्त equity/cash मार्केटला 9:00-9:15 pre-open
असतो) — त्यामुळे "9:10 च्या pre-open किमतीनुसार S/R अपडेट करा" हा दृष्टिकोन इथे लागू होत नाही (त्या
वेळी बाजारात कुठलाच नवीन, वापरण्यायोग्य डेटा नसतो). प्रत्यक्ष फायदा फक्त bots बरोबर 9:15 (आधीचा 9:16
नाही) पासून सुरू होण्यातूनच मिळतो.

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

## ⚠️ प्रत्यक्ष घडलेला गंभीर बग — "429: error code 1015" (Cloudflare rate-limit) मध्ये अडकणे
🎓 वापरकर्त्याला प्रत्यक्ष live trading आधी आलेला अनुभव — `cloudflared_upstox_webhook.service` कधी
अयशस्वी झालं (network blip/VPS reboot), की जुन्या `RestartSec=5` मुळे दर ५ सेकंदाला Cloudflare च्या
मोफत quick-tunnel endpoint ला पुन्हा विनंती जायची — याच वारंवार-विनंतीमुळे Cloudflare स्वतःच
rate-limit (`429: error code 1015`) लावतं, आणि मग service कायमचं (अनंत लूपमध्ये) अडकून राहतं — कधीच
एकही URL न मिळवता. रोजचा token-refresh त्यामुळे शांतपणे अयशस्वी व्हायचा, कुठलाही स्पष्ट error न
दाखवता (`check_token_freshness.py --verify-live` शिवाय हे सापडणंही अवघड).

**लक्षण ओळखणे:**
```bash
journalctl -u cloudflared_upstox_webhook -n 40 --no-pager | grep "429\|1015"
```
हे दिसलं (आणि `systemctl status` मध्ये restart counter झपाट्याने वाढताना दिसलं), तर हेच घडलंय.

**बरं करणे (rate-limit निघून जाईपर्यंत थांबावं लागतं):**
```bash
systemctl stop cloudflared_upstox_webhook.service
sleep 60   # किंवा जास्त — 429 लगेच निघून जात नसेल तर काही मिनिटं थांबा
systemctl start cloudflared_upstox_webhook.service
journalctl -u cloudflared_upstox_webhook -n 20 --no-pager | grep trycloudflare
```

आता `RestartSec=30` + `StartLimitIntervalSec=600`/`StartLimitBurst=5` (५ प्रयत्नांनंतर systemd
स्वतःहून थांबतं, अनंत लूप नाही) — त्यामुळे हे स्वतःहून पुन्हा घडण्याची शक्यता कमी आहे, पण VPS reboot
सारख्या मोठ्या गोष्टीनंतर पुन्हा घडलं, तर वरचीच पावलं वापरा.

# Dashboard Password Gate (APP_PASSWORD) — ⚠️ Live Trading आधी अनिवार्य

🎓 वापरकर्त्याने प्रत्यक्ष सापडवलेली गंभीर सुरक्षा त्रुटी — Streamlit Dashboard (`app.py`) आधी
कुठल्याही password/login शिवाय, VPS च्या public IP:port वरून (server `0.0.0.0` वर बांधलेला)
**कुणालाही** उघडं होतं — LIVE Trading चालू करणं, Lot Size/SL/Target बदलणं, Broker
credentials/access tokens बघणं-बदलणं, सर्व काही. आता `app.py` च्या अगदी सुरुवातीला एक password
gate आहे — बरोबर पासवर्ड दिल्याशिवाय काहीच (chart, settings, काहीही) दिसणार नाही.

**Fail-closed** — `APP_PASSWORD` सेट केलेला नसेल, तरीही Dashboard उघडं सोडत नाही; त्याऐवजी सेटअप
सूचना दाखवून थांबतं. त्यामुळे live trading सुरू करण्याआधी हे सेट करणं **अनिवार्य** आहे.

## एकदाच सेटअप:

```bash
# 1. Dashboard साठी systemd unit copy करणे (आधीपासून bare `streamlit run` command ने चालत असेल,
#    तर तो आधी थांबवा — जेणेकरून दोन प्रोसेस एकाच पोर्टवर भांडणार नाहीत)
cp deploy/streamlit_dashboard.service /etc/systemd/system/

# 2. established upstox_token_webhook.service सारखाच, तोच /root/Trade/.env वापरतो -- त्यात
#    (आधीच SUPABASE_DB_URL वगैरे असेल तिथेच) एक नवीन ओळ जोडा:
echo 'APP_PASSWORD=तुमचा-मजबूत-पासवर्ड-इथे-टाका' >> /root/Trade/.env

# 3. systemd ला नवीन unit दिसण्यासाठी, आणि सुरू करणे
systemctl daemon-reload
systemctl enable --now streamlit_dashboard.service

# 4. तपासणी — "active (running)" दिसायला हवं
systemctl status streamlit_dashboard.service
```

Browser मध्ये Dashboard उघडल्यावर आता सर्वात आधी पासवर्ड विचारला जाईल — बरोबर टाकल्यावरच पुढे
जाता येईल (एका browser session/tab पुरतं लक्षात राहतं, पुन्हा-पुन्हा विचारत नाही).

⚠️ पासवर्ड कधीही `git commit` करू नका — फक्त `.env` फाईलमध्येच (जी `.gitignore` मध्ये आधीच आहे).
