# Monday PAPER — मार्ग, settings, deploy (Abhi P0)

**मुख्य मार्ग:** existing bots (5-Min Instant, 15M Dynamic SR, SR V3) → (signal_source) → Vision → Abhi ✅ → PAPER entry → updates → exit → journal.
LIVE मार्गाला हात नाही. Vision कधीच order देत नाही; किंमती फक्त API (option chain / LTP / order_log) मधून.

| # | काय | कुठे |
|---|---|---|
| 1 | `signal_source` own / engine / both (dashboard: Bot Dynamic SR Algo → 🧭 Signal source; SR V3 साठी वेगळा) | `engine_signal.py`, `paper/bot_hooks.py`, `paper/engine_entry.py`, `scripts/engine_signal_run.py` |
| 1 | engine चं shadow मत Vision caption मध्ये ("engine: setup/wait …") | `vision/worker.py: engine_line` |
| 2 | Approval शिवाय PAPER entry नाही: PAPER मध्ये V1 नसलेला mode ⇒ `human_confirm`; gate चूक / gate नाही ⇒ entry नाही; यादीबाहेरचा symbol ⇒ नाही | `vision/config.py: approval_required`, `vision/gate.py`, तिन्ही bots |
| 2 | SR V3 आता Vision gate + forced levels मार्गावर | `srv3_instant_shadow.py` |
| 3 | Lot size Upstox instrument master (front FUT) मधून; config.yaml फक्त fallback; mismatch ⇒ Telegram | `paper/lots.py`, `config.yaml: paper.instruments` |
| 4–6 | Journal (bot, signal_source, Vision मत + कारण, approver, engine मत, R:R, entry / exit charges, net P&L) + Telegram updates (entry fill, दर N मिनिटं P&L, SL / target जवळ, exit) | `paper/journal.py`, `paper/watch.py` (trade_monitor / engine_service मध्ये exits नंतर) |
| 7 | `/status` `/positions` `/pause` `/resume` (फक्त approver; pause फक्त नवे entries) | `paper/commands.py`, `vision/telegram_bot.py` |
| 9 | NIFTY enabled; BANKNIFTY / SENSEX `enabled: false` | `config.yaml: paper.instruments` |
| — | Token नाही ⇒ स्पष्ट error + Telegram (दिवसातून एकदा) | `paper/bot_hooks.py: token_error`, bots चा `__main__` |
| ✋ | Manual trigger `/paper` (P1 मधून P0): validation ⇒ Vision (bot key `manual`; NA तरी बटणं) ⇒ ✅ ⇒ PAPER entry ⇒ updates ⇒ तुमचा spot SL / T exit ⇒ journal | `paper/manual.py`, `vision/telegram_bot.py`, `paper/watch.py`, `vision/worker.py: v1_caption` |

## Settings (code मध्ये आकडे नाहीत)
- `config.yaml → paper`: `instruments.<SYM>.enabled / lot_size_fallback`, `update_every_min` (30), `near_alert_pct` (80).
- Vision (dashboard / `/vision`): `approval_required` (default true), `approve_window_min` (10), `exec_window_min` (5).
- Bot settings: `signal_source` (own), SR V3: `srv3_signal_source` (own).

## ✋ Manual trigger (Telegram, फक्त TELEGRAM_APPROVER_IDS)
```
/paper NIFTY bullput SL 24750 T 25300              # strikes / width / lots: manual_profile bot च्या settings (default SR V3)
/paper NIFTY bearcall 25100/25200 SL 25250 T 24800 # तुमचे strikes (short/hedge)
/help
```
- तपासणी: instrument enabled, बाजार वेळ, token, pause, kill-switch, उघडी manual position (एका वेळी एक), आधीचा pending manual, option chain
  (आज expiry ⇒ पुढची weekly), बाजू (bull put: short > hedge, SL spot खाली, T वर; bear call उलट), strikes chain मध्ये, net credit > 0.
- R:R = |T − spot| / |spot − SL| caption मध्ये; < 3 ⇒ ⚠️ (तरी ✅ ने घेता येतो).
- ✅ ⇒ लगेच (Telegram service) drift guard + entry (`open_multi_leg_trade` — kill-switch / pause / VIX पुन्हा). ❌ / 10 मिनिटं उत्तर नाही ⇒ entry नाही.
- Exit: तुमचा spot SL / T (paper watcher, trade_monitor च्या प्रत्येक cycle ला) + backstop generic नियम (credit च्या 100% तोटा, 3:10 नियम).
- `manual_profile`: dashboard → Vision Human Eye → "✋ manual_profile".

## Engine service (signal_source engine / both साठी; own असताना फक्त caption मत; cron वेळ UTC)
```
1,16,31,46 3-10 * * 1-5  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/engine_signal_run.py >> engine_signal.log 2>&1
```

## Sunday dry-run
```
cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_dry_run.py --wait-min 12
```
प्रत्येक bot चा (आणि एक ✋ manual `/paper`) "🧪 [DRY-RUN]" Vision संदेश येतो ⇒ ✅ दाबा ⇒ PAPER entry ⇒ updates ⇒ exit ⇒ journal. Log: `data/paper_dry_run_<date>.log`.
