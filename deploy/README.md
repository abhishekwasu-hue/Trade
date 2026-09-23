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

🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("SL slippage कमी करा") — Performance Report मध्ये
सापडलं की SL threshold च्या बऱ्याच पुढे जाऊन लागत होता, कारण cron दर 60 सेकंदांनीच नव्याने ही
script सुरू करत होता. **crontab अजूनही दर 1 मिनिटालाच invoke करतो (खाली तेच, बदललेलं नाही)** —
पण आता `trade_monitor.py` स्वतःच आतून, प्रत्येक invocation मध्ये, दर ~20 सेकंदांनी (डीफॉल्ट
`--interval-seconds 20`) 60-सेकंद cron window च्या आत (`--loop-seconds 50`) पुन्हा-पुन्हा तपासत
राहते — म्हणजे प्रत्यक्ष SL/Target तपासणी आता दर ~20 सेकंदांनी होते, दर 60 सेकंदांनी नाही. यामुळे
प्रति-symbol API कॉल्स ~3x वाढतात (rate-limit वर लक्ष ठेवा — जास्त वाटल्यास
`--interval-seconds 30` किंवा `40` देऊन कमी करता येतं).

**सद्य crontab (VPS वर `crontab -l` ने पडताळलेलं, वेळा UTC मध्ये — VPS ची timezone
`timedatectl`/`date` ने आधी खात्री करूनच बदल करा):**
```
45-59 3 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> /root/Trade/monitor.log 2>&1
```
म्हणजे cron दर मिनिटाला invoke करतो (सकाळी ९:१५ ते संध्याकाळी ~४:२९ IST, सोमवार-शुक्रवार — UTC
3:45 ते 10:59 शी समतुल्य — भारतीय बाजाराच्या पूर्ण सत्रभर), आणि प्रत्येक invocation च्या आत
script स्वतःच ~3 वेळा (दर ~20 सेकंदांनी) पुन्हा तपासते.

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

🎓 वापरकर्त्याने आधी दर 30 मिनिटांनी करायला सांगितलं होतं, पण नंतर स्वतःच लक्षात आणून दिलं — 5M हेच
सध्या Instant Trader strategy चं डीफॉल्ट live-trading timeframe आहे, आणि 30-मिनिटांच्या cadence
मध्ये एखादा level किंमत त्याच्यापासून बरीच पुढे गेली तरी पुढच्या merge पर्यंत ACTIVE/tradeable राहू
शकला असता (जास्त lag, जुना level trade होण्याचा धोका). त्यामुळे परत **दर 5 मिनिटांनीच** (1M
प्रमाणेच) — शेवटचा निर्णय, बदल मागे घेतला.
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

# MCX Futures Trader — Deployment (crontab) — ⚠️ वेगळा, स्वतंत्र cron — अजून सक्रिय करू नका

🎓 वापरकर्त्याने मागितलेली सुधारणा ("यासाठी cron पण वेगळा तयार करा") — वरच्या NIFTY/BANKNIFTY/SENSEX
entry bots चा crontab अजिबात बदलायचा नाही (वापरकर्त्याने स्पष्टपणे सांगितलेलं) — MCX Futures Trader
साठी **पूर्णपणे वेगळी** crontab entries इथे नोंदवल्या आहेत, वरच्या bots च्या ओळींमध्ये मिसळलेल्या नाहीत.

✅ **Update** — `mcx_futures_trader.py` (entry+exit) आणि `refresh_market_zones_mcx.py` (Dynamic S/R,
30M/60M) दोन्ही स्क्रिप्ट्स आता बांधलेल्या आहेत (आधी फक्त Dashboard चं पान/settings होतं).

⚠️ **तरीही या ओळी अजून VPS crontab मध्ये जोडू नका** — जोडण्याआधी:
1. `python3 resolve_mcx_futures_instruments.py` VPS वर चालवून, खरा instrument_key/lot_size/tick_size
   Upstox कडून प्रत्यक्ष पडताळा (अजून हे केलेलं नाही — PR #73 मध्ये फक्त read-only resolver जोडलेला).
2. `python3 refresh_market_zones_mcx.py` एकदा हाताने चालवून, कुठल्याही commodity साठी Dynamic S/R
   zones प्रत्यक्ष तयार होतात/वाजवी दिसतात याची खात्री करा (नाहीतर mcx_futures_trader.py ला
   कुठलेही ACTIVE levels सापडणार नाहीत — निरुपद्रवी, पण उपयोगहीन).
3. `python3 mcx_futures_trader.py` एकदा हाताने (PAPER mode — page_mcx_futures.py चा डीफॉल्ट)
   चालवून बघा, कुठलाही अनपेक्षित error येत नाही ना, आणि Signal Log (Dashboard) मध्ये अपेक्षित
   नोंदी दिसतात ना.
4. वरच्या तिन्ही पायऱ्या समाधानकारक झाल्यावरच खालच्या crontab ओळी प्रत्यक्ष जोडा — आधी जोडलं तर
   नेमकी तीच bug परत घडेल जी वर "`refresh_dynamic_sr_15m.py` हा file कधीच अस्तित्वातच नव्हता" या
   इशाऱ्यात नोंदवलेली आहे — दर काही मिनिटांनी निरुपयोगी प्रयत्न, काहीही अर्थपूर्ण न करता.

## MCX चे trading hours NSE पेक्षा खूप वेगळे — वेगळी crontab window का लागते

NSE च्या 9:15 AM–3:30 PM च्या विपरीत, MCX चा session **9:00 AM ते 11:30 PM (हिवाळा) किंवा 11:55 PM
(अमेरिकेच्या Daylight Saving काळात, कारण Crude Oil/Gold आंतरराष्ट्रीय किमतींशी जोडलेले आहेत) पर्यंत**
चालतो — जवळपास संपूर्ण दिवस. त्यामुळे वरच्या entry bots ची crontab window (UTC 3:45-10:xx, म्हणजे
IST 9:15-4:29) इथे वापरता येत नाही — वेगळी, जास्त रुंद window लागते.

**तयार ठेवलेल्या crontab entries (जोडण्यासाठी तयार, वेळा UTC मध्ये — वरच्या 4 पायऱ्या पूर्ण/
पडताळणी झाल्यावरच जोडा):**
```
45-59 3 * * 1-5 cd /root/Trade && sleep 60 && python3 mcx_futures_trader.py >> /root/Trade/mcx_futures.log 2>&1
* 4-18 * * 1-5 cd /root/Trade && sleep 60 && python3 mcx_futures_trader.py >> /root/Trade/mcx_futures.log 2>&1
35 5,8,11,14,18 * * 1-5 cd /root/Trade && set -a && . /root/Trade/.env && set +a && python3 refresh_market_zones_mcx.py >> /root/Trade/market_zones_mcx_refresh.log 2>&1
```
🎓 वापरकर्त्याने सापडवलेली bug (22-Sep) — तिसरी ओळ आधी दिवसातून **एकदाच** (फक्त `35 18 * * 1-5`, म्हणजे
MCX बंद झाल्यावर) चालायची — त्यामुळे Market Zones (bot प्रत्यक्ष trading साठी वापरत असलेले साठवलेले
zones) दिवसभर stale राहायचे, चार्टच्या नेहमी-ताज्या live गणनेशी न जुळणारे. आता त्याच स्क्रिप्टला MCX
च्या लांब session (9 AM–11:30/11:55 PM) मध्ये पसरून **दिवसातून 5 वेळा** (11:05, 14:05, 17:05, 20:05
IST + मूळचा शेवटचा close-नंतरचा 00:05 IST) चालवलं जातं — एकाच line मध्ये स्वल्पविरामाने वेगळे तास
(`5,8,11,14,18` UTC) देऊन, नवीन line न जोडता.
शेवटचा run (18:35 UTC = 00:05 IST पुढच्या दिवशी, 11:55 PM च्या उन्हाळी-वेळेतल्या MCX close नंतरही
सुरक्षित) आधीसारखाच ठेवलेला आहे — पूर्ण दिवसाच्या candles वरून अंतिम, सर्वात विश्वासार्ह EOD zone set
यासाठी. मधले 4 runs फक्त त्या-त्या क्षणापर्यंतच्या आंशिक (partial) दिवसावरून ताजे recompute करतात —
`cloud_db.save_market_zones()` प्रत्येक वेळी त्या symbol चे **सर्व जुने zones आधी DELETE करून** नवीन
संच पूर्णपणे बदलतो (replace-on-refresh, वाढत जाणारा इतिहास नाही), त्यामुळे दिवसातून 5 वेळा चालवूनही
डुप्लिकेट/कचरा साठण्याची शक्यता नाही — प्रत्येक वेळी फक्त सद्य (त्या क्षणापर्यंतच्या) संगणनेइतकाच संच
राहतो.
`refresh_market_zones.py` च्याच (NSE साठीच्या) crontab ओळीशी सुसंगत पॅटर्न, पण पूर्णपणे वेगळी वेळ (MCX
च्या उशिरापर्यंतच्या session मुळे) आणि वेगळी log file.
UTC 3:45 ते 18:59 = IST 9:15 AM ते पुढच्या दिवशी 12:29 AM — म्हणजे 11:55 PM (उन्हाळी वेळेतला MCX
close) सुद्धा आत बसतो; `sleep 60` (वरच्या entry bots च्या 15/30/45s पेक्षा जास्त — वेगळ्या तासाला
चालत असल्याने टक्कर होण्याची शक्यता नसली, तरी VPS वरच्या इतर दर-मिनिटाच्या cron jobs (trade_monitor.py
वगैरे, त्याच मिनिटाला) सोबत सुरुवातीचीच गर्दी टाळण्यासाठी). **महत्त्वाचं** — script स्वतःच आतून, actual
MCX holiday calendar/नेमकी बंद होण्याची वेळ (हिवाळा/उन्हाळा) तपासून सुरक्षितपणे थांबायला हवं — ही cron
window मुद्दामच किंचित रुंद (12:29 AM पर्यंत) ठेवलेली आहे, script ने स्वतःच बरोबर वेळी थांबावं.

⚠️ **NSE bots च्या (`trade_monitor.py`/`srv2_momentum_reversal_strategy.py` इ.) कुठल्याही crontab
entry ला हात लावलेला नाही** — वरचं जोडणं म्हणजे फक्त नवीन ओळी, existing ओळींमध्ये कुठलाही बदल नाही.

**तपासणी (जोडल्यानंतर):**
```bash
tail -f /root/Trade/mcx_futures.log
crontab -l | grep mcx_futures
```

---

# Market Zones Refresh (15M/30M/60M — SRv2 चा एकमेव zone-स्रोत) — आता VPS crontab वर

🎓 वापरकर्त्याने सापडवलेली bug — SRv2 Momentum-Reversal चा Signal Log रिकामा दिसत होता ("Srv2 log
disat nnahi", दिवसभर एकही entry नाही, तेच `1M/5M Instant Trader` चा log मात्र नेहमीसारखाच भरलेला).
Root cause: SRv2 फक्त `status == "ACTIVE"` असलेले 15M/30M/60M zones शोधतो
(`srv2_momentum_reversal_strategy._collect_touch_candidates()`), आणि हे zones फक्त
`refresh_market_zones.py` कडूनच येतात — जो अजूनही **फक्त GitHub Actions cron** वर होता (VPS crontab
वर कधीच हलवलेला नव्हता, 1M/5M प्रमाणे). प्रत्यक्ष run history तपासली असता तो शेवटचा यशस्वी (schedule
ने) १८ सप्टेंबरलाच चालला होता — `trigger_upstox_token_request.yml` साठी सापडलेली, तीच "scheduled
workflows are best-effort, silently skip होऊ शकतात" समस्या. Zones शिळे राहिले (सर्व आधीचे ACTIVE
zones दरम्यान hit/invalidate झाले), नवीन कधीच generate झाले नाहीत — SRv2 ला रोज "कुठलेही ACTIVE
Dynamic S/R levels (15M/30M/60M) सापडले नाहीत" असं दिसत राहिलं, आणि तो कधीच कुठलाही candidate
साठवायचाच नाही (लगेच early-return, `save_signal_log()` पर्यंत पोचतच नाही).

**जोडायचं crontab entry (`crontab -e`, वेळ UTC मध्ये — बाजार बंद झाल्यावर, १०:०५ UTC = १५:३५ IST,
सोम-शुक्र — मूळ GitHub Actions cron पेक्षा 5 मिनिटं उशीरा, जेणेकरून बाजार खरंच बंद झाल्याची खात्री
असेल):**
```
5 10 * * 1-5 cd /root/Trade && set -a && . /root/Trade/.env && set +a && python3 refresh_market_zones.py >> /root/Trade/market_zones_refresh.log 2>&1
```
`--token` दिलेला नाही — स्क्रिप्ट आपोआप Supabase मधून सद्य token घेते (इतर crontab entries सारखंच).

**तपासणी:**
```bash
tail -f /root/Trade/market_zones_refresh.log
crontab -l | grep refresh_market_zones
```
यशस्वी run नंतर log मध्ये प्रत्येक symbol साठी "✅ NIFTY: N zones साठवले (M अजून ACTIVE)" असं दिसायला
हवं — `M` (ACTIVE count) 0 असेल, तर तेव्हा SRv2 चा Signal Log त्या दिवशी रिकामाच राहील (हे स्क्रिप्ट
बरोबर चालूनही घडू शकतं — फक्त त्या दिवशी कुठलेही नवीन 15M/30M/60M zone तयार झालेले नाहीत असा अर्थ).

⚠️ GitHub Actions मधला `schedule` काढून टाकलेला आहे (`workflow_dispatch` फक्त मॅन्युअल/backup साठी
उरलाय) — वरची crontab entry हाच आता खरा, रोजचा ट्रिगर आहे.

---

# NIFTY/BANKNIFTY/SENSEX — 15M/30M/60M Zones Intraday Refresh (5x/दिवस — नवीन, वेगळा cron)

🎓 वापरकर्त्याने सापडवलेली bug — वरचा `refresh_market_zones.py` cron दिवसातून **फक्त एकदाच** (बाजार
बंद झाल्यावर, 15:35 IST) चालतो, त्यामुळे SRv2/Classic S/R Reversal bots चे 15M/30M/60M zones दिवसभर
stale राहतात (MCX Market Zones प्रमाणेच सापडलेली, त्याच वर्गातली समस्या — बघा वरचा MCX भाग).
वापरकर्त्याने किमान 5 वेळा/दिवस अपडेट मागितलं.

⚠️ **वरचा `refresh_market_zones.py` cron मात्र दिवसातून एकदाच बाजार बंद झाल्यावरच चालवायचा, बदलायचा
नाही** — तो त्याच वेळी DYNAMIC_SR_*_1M/*_5M zones सुद्धा नव्याने काढतो, आणि **`save_market_zones()`
चं डीफॉल्ट DELETE symbol-व्यापी आहे (सगळेच zone_types पुसतं)** — तेच 1M/5M zones
`dynamic_sr_instant_trader.py` बाजार चालू असताना दर मिनिटाला, जुने कधीच न काढता फक्त STALE करणाऱ्या
पद्धतीने live जपत असतो, त्यावरच प्रत्यक्ष trade चालू असू शकतो. तो cron intraday चालवला असता, तर प्रत्येक
वेळी live-maintained 1M/5M zones सरसकट उडून नव्याने लिहिले गेले असते — real money trading मध्ये अचानक
व्यत्यय येण्याचा धोका.

त्यामुळे **नवीन, पूर्णपणे स्वतंत्र** `refresh_market_zones_intraday.py` script जोडलेला आहे —
`market_zones.compute_intraday_sr_zones()` (फक्त 15M/30M/60M, compute_all_zones() ला अजिबात स्पर्श
न करता) व `cloud_db.save_market_zones(..., scoped=True)` (फक्त तेच सहा zone_types replace — 1M/5M,
SUPPORT/RESISTANCE, Order Blocks इ. पूर्णपणे अबाधित) वापरतो.

**जोडायचं crontab entry (`crontab -e`, वेळ UTC मध्ये — वरच्या once-daily entry सोबतच, ती न बदलता
नवीन ओळ म्हणून; बाजार सत्रादरम्यान 4 वेळा + वरचा मूळचा close-नंतरचा run = एकूण 5 वेळा/दिवस):**
```
5 5,6,8,9 * * 1-5 cd /root/Trade && set -a && . /root/Trade/.env && set +a && python3 refresh_market_zones_intraday.py >> /root/Trade/market_zones_intraday_refresh.log 2>&1
```
म्हणजे 10:35, 11:35, 13:35, 14:35 IST (नवीन 4, बाजार सत्रात 9:15 AM–3:30 PM च्या आतच) + वरचा मूळचा
15:35 IST (close+5, अजूनही तोच, न बदललेला `refresh_market_zones.py` run) — एकूण 5 वेळा/दिवस.

**तपासणी:**
```bash
tail -f /root/Trade/market_zones_intraday_refresh.log
crontab -l | grep refresh_market_zones_intraday
```
यशस्वी run नंतर log मध्ये प्रत्येक symbol साठी "✅ NIFTY: N zones साठवले (15M+30M+60M, इतर zone_types
अबाधित)" असं दिसायला हवं.

---

# Upstox Token Webhook — Deployment (1-Tap Mobile Approval)

`trigger_upstox_token_request.py` Upstox ला "आजचा token हवा" अशी विनंती पाठवतो — तुमच्या मोबाईलवर
Upstox app मध्ये notification येते, एका टॅपने Approve केलं की Upstox तो token एका webhook URL ला
POST करतो. `upstox_token_webhook.py` (VPS वर, Flask) तो POST स्वीकारून Supabase मध्ये साठवतो —
कुठेही manual copy-paste लागत नाही.

## ⚠️ रोजचा ट्रिगर आता VPS crontab वर (GitHub Actions cron अविश्वसनीय ठरलं)

🎓 वापरकर्त्याने प्रत्यक्ष सापडवलेला बग — "notification आलंच नाही, ७:३० वाजले, yml मध्ये ७:०० सेट आहे"
अशी तक्रार आल्यावर, `trigger_upstox_token_request.yml` चा GitHub Actions `schedule` cron तपासला असता
तो १६/१७ सप्टेंबरनंतर **एकदाही आपोआप चाललाच नव्हता** — cron वेळ (`"30 1 * * 1-5"` = ०७:०० IST) बरोबर
असूनही. GitHub स्वतः सांगतं की scheduled workflows "best-effort" असतात, जास्त load मध्ये सरळ skip
होऊ शकतात — या repo मध्ये आधीच अनेक scheduled workflows असल्याने हेच घडत होतं (मधल्या काळात रोज
मॅन्युअल "Run workflow" क्लिकनेच चालवावं लागत होतं).

`trade_monitor.py`/entry bots साठी आधीच याच कारणासाठी VPS crontab वापरलं जातंय (वर बघा) — तोच पॅटर्न
इथेही: workflow मधला `schedule` काढून टाकला (फक्त मॅन्युअल/backup `workflow_dispatch` उरलाय), आणि हा
daily trigger आता खालच्या crontab entry ने चालतो — VPS cron कधीच silently skip होत नाही.

**जोडायचं crontab entry (`crontab -e`, वेळ UTC मध्ये — ०१:३० UTC = ०७:०० IST, सोम-शुक्र):**
```
30 1 * * 1-5 cd /root/Trade && set -a && . /root/Trade/.env && set +a && python3 trigger_upstox_token_request.py >> /root/Trade/token_request.log 2>&1
```
`set -a && . .env && set +a` हे `.env` मधले सर्व (`UPSTOX_CLIENT_ID`/`UPSTOX_CLIENT_SECRET` सकट)
environment variables म्हणून export करतं — cron स्वतः `.env` वाचत नाही, त्यामुळे हे लागतंच.

⚠️ **आधी खात्री करा** `/root/Trade/.env` मध्ये `UPSTOX_CLIENT_ID` आणि `UPSTOX_CLIENT_SECRET` (Upstox
Developer Console मधलं App बनवताना मिळालेलं API Key/Secret — access_token नाही) आहेत — आधी हे फक्त
GitHub Actions Secrets मध्ये होते, `.env` मध्ये नसतील तर आधी तिथे जोडा.

**तपासणी:**
```bash
tail -f /root/Trade/token_request.log
crontab -l | grep trigger_upstox_token_request
```

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
