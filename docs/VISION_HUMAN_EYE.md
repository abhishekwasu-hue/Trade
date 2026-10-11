# Vision + Human-Eye — PAPER signals ची chart तपासणी

> स्रोत: TRADE_VISION_HUMAN_CONFIRM_PROMPT.md (§10 तुमचे निर्णय आणि §11 PNG जतन — विरोध असेल तर हे जिंकतात) + 2026-10-07 चे निर्णय. टप्पे V0 → V1 → V2 → V3. **हे पान V1 + prompt v2.1 (`signal_check_v2_1`) पर्यंत अद्ययावत.**

## अटळ नियम
1. Vision / AI कधीच order देत नाही, size वाढवत नाही (reduce-only). **V0 modes (shadow / notify) मध्ये trading वर शून्य परिणाम.** V1 modes मध्ये
   फक्त entry थांबवणे / अर्धा size — bot मध्ये gate चे lots फक्त `min(मूळ, gate)` मधूनच वापरले जातात (AST test).
2. Exits पूर्ण automatic — `trade_monitor.py` / `trading_engine.py` / `engine_service.py` मध्ये vision नाही (test).
3. किंमती image वरून नाहीत — level / spot bot च्या OHLC मधून; vision फक्त enum मत देतो.
4. फक्त PAPER. LIVE bot ⇒ `effective_mode = off` (कुठलाही mode लागू नाही).
5. No-lookahead: chart फक्त signal च्या क्षणापर्यंत **पूर्ण** झालेल्या 1m bars वरून (चालू minute चा bar नाही), मोठे TF त्याच कापलेल्या data वरून (test: भविष्यातला spike chart मध्ये नाही).
6. Secrets फक्त VPS `.env`: `ANTHROPIC_API_KEY`, Telegram token. Log / repo मध्ये नाहीत.

## V0 — shadow / notify (हा PR)

```
Bot (cron, दर मिनिट) — सगळे gates पास, entry च्या आधी
   └─ vision.hook.submit_signal(...)  → data/vision.db: vision_signals (QUEUED)      ← फक्त नोंद, ~ms, कधीच raise नाही
Bot नेहमीप्रमाणे trade करतो (निर्णय / size / exits बदलत नाहीत)

vision worker (cron, दर मिनिट, 55 s loop, दर 5 s तपासणी, ProcessLock)
   1. 15 मिनिटांपेक्षा जुने QUEUED ⇒ EXPIRED
   2. Upstox 1m (14 दिवस) → signal पर्यंत कापून 2-panel chart (setup TF + मोठा TF), ~1000×700 PNG
      → data/visual_audit/YYYY-MM-DD/<bot>_<symbol>_<signal_id>_<HHMM>_sent.png (overwrite नाही) + sha256; vision आणि Telegram ला हीच फाईल
   3. तोच symbol / दिशा / TF / level (±0.05%) 15 मिनिटांत आधी तपासलेला ⇒ तेच मत (API call नाही)
   4. Budget (आज ≤ $2.00, आधी $0.30; महिना ≤ $60, आधी $5 — Abhi. **Dashboard / DB मध्ये `_global` save केलं असेल तर तीच value लागू — code default नाही**; म्हणून dashboard वरही 2.0 / 60 ठेवा) / model / key नाही ⇒ verdict unavailable, fail action = ignore (algorithm चा निर्णय) + दिवसातून एकदा Telegram इशारा
   5. Audit: 1 call; confidence < 0.6 ⇒ दुसरा (budget असेल तर)
   6. नोंद: verdict, JSON, latency, tokens, $
   7. mode = notify ⇒ Telegram: chart + मत + कारण (बटणं नाहीत). shadow ⇒ फक्त नोंद.
```

| Bot | key | V0 default | कारण |
|---|---|---|---|
| NIFTY 5-Min Instant | `dynamic_sr_instant` | **notify** | G-V0 ला पहिल्या दिवसाचा Telegram हवा |
| NIFTY 15M Dynamic SR | `srv2_momentum_reversal` | **notify** | तसंच |
| Pullback Credit Spread | `pullback_credit_spread` | off | §10.1: "PAPER चालू असेल तर" — तो सध्या फक्त preview पान आहे, PAPER bot म्हणून चालत नाही (hook ला जागा नाही). PAPER runner आला की याच hook ने notify |
| MCX Futures | `mcx_futures` | off | तुमचा निर्णय: MCX off |
| Elliott | `elliott` | off | E6 PAPER wiring नंतर |

`algo_decision = ENTER` म्हणजे bot चे सगळे gates पास झाले. पण option chain / strike-निवड नंतर अपयशी झाली तर प्रत्यक्ष trade होत नाही
⇒ outcome साठी नेहमी `live_trades` शी (bot source, symbol, वेळ) जोडून पाहायचं (V3).
Chart वरचा शेवटचा bar: bot ने signal च्या क्षणी पाहिलेली चालू 1m candle (`last_bar`) — ती bot कडची त्या क्षणीची माहिती आहे, भविष्य नाही; signal नंतरची candle नाकारली जाते (test).

Setup TF → chart: 1M/5M level ⇒ 5m + 15m; 15M ⇒ 15m + 1H; 30M ⇒ 30m + 1H; 60M ⇒ 1H + Daily.

### Vision प्रश्न (`signal_check_v1`, structured JSON)
`level_real` yes/no/unclear · `trend_context` with/against/range/unclear · `reversal_valid` yes/no/unclear · `is_breakout_entry` yes/no ·
`false_break_risk` low/medium/high · `elliott_note` · `verdict` agree/gray/disagree · `reason` (मराठी, ≤ 160) · `confidence` 0–1.
System prompt मध्ये तुमचे नियम: pullback-only (breakout कधीच नाही), reversal = touch → reclaim → strength → close location, level खरा हवा, A-end entry नाही.

**Verdict code मध्ये:** breakout = yes किंवा reversal = no ⇒ disagree; कुठलंही unclear ⇒ gray; 2 audits असहमत ⇒ gray; enum अवैध / API अपयश / refusal ⇒ unavailable.

### खर्च (G-COST)
- Model नाव फक्त env मध्ये: `VISION_SIGNAL_MODEL` (signals — मध्यम model), `VISION_LEVEL_MODEL` (V2 सकाळचा audit — सर्वात स्वस्त). ऐच्छिक `VISION_SIGNAL_EFFORT`, `VISION_SIGNAL_THINKING`, `VISION_SIGNAL_MAX_TOKENS` (v2 पासून 1200; thinking off ठेवा).
- एका audit चा अंदाज (मध्यम model, $2 / $10 प्रति 1M): input ≈ 900 (image) + ≈ 570 (system) + ≈ 70 = ~1.6k ⇒ $0.003; output JSON ~150–500 ⇒ $0.002–0.005.
  **≈ $0.005–0.01 प्रति audit.** 10 signals/दिवस × 1.3 audits × 22 दिवस ⇒ **≈ $1.4–2.9 / महिना** (< $5). दैनिक मर्यादा (आता $2.00) आणि मासिक ($60) हे कठोर ब्रेक; v2.2 chart audits signals साठी राखीव (`signals_daily_reserve_usd`) सोडून.
- System prompt `cache_control` सह. तो ~570 tokens (अंदाज) — नव्या models चं किमान 512 च्या अगदी जवळ, त्यामुळे cache होईलच असं नाही; सर्वात स्वस्त model वर किमान 4096 असल्याने होत नाही. शिवाय signals मध्ये 5 मिनिटांपेक्षा जास्त अंतर असेल तर cache संपतो. एकूण परिणाम लहान (system चा खर्च प्रति audit ~$0.001) — म्हणून खर्च नेहमी API च्या `usage` वरून मोजला जातो, अंदाजावरून नाही.
- Budget तपासणी सावध: प्रत्येक call आधी अंदाज = input ~2k + output = `VISION_SIGNAL_MAX_TOKENS` (thinking सुद्धा output मध्ये मोजलं जातं). API timeout / network अपयश
  (usage मिळाला नाही) ⇒ हाच अंदाज खर्च म्हणून नोंद (billed झाला असू शकतो).
- `VISION_SIGNAL_EFFORT=low` शिफारस (कमी thinking ⇒ कमी खर्च, 20 s timeout मध्ये उत्तर). `VISION_SIGNAL_THINKING` फक्त तो model स्वीकारत असलेला प्रकार असेल तरच
  (उदा. काही models वर `disabled` 400 देतो) — शंका असेल तर रिकामा ठेवा. चुकीचं मूल्य ⇒ प्रत्येक audit unavailable (खर्च 0) — `--usage` / log मध्ये दिसेल.
- **पहिल्या दिवसाचं खरं मोजमाप:** `python3 -m vision.worker --usage` (calls, input / cache-read / cache-write / output tokens, $).

### Settings
`python3 -m vision.config show` · `python3 -m vision.config set dynamic_sr_instant vision_mode shadow --by abhishek` (बदल-इतिहास `vision_settings_history` मध्ये, `python3 -m vision.config history`).
Keys: `vision_mode`, `symbols`, `vision_gray_action`, `vision_disagree_action`, `vision_fail_action`, `timeout_action`, `approve_window_min`, `max_drift_mr`,
`exit_advice`, `vision_timeout_sec` (20), `second_audit_below_conf` (0.6), `reuse_window_min` (15), `level_gate`; `_global`: `vision_daily_budget_usd` (2.00; आधी 0.30; DB value code default वर मात करते),
`vision_monthly_budget_usd` (60), `morning_audit_time` (08:00), `exec_window_min` (5, V1), `shadow_cooldown_min` (30, V1).
V1 modes (`auto_veto` / `human_confirm` / `veto_then_confirm`) फक्त PAPER bot वर — bot चा `trading_mode` LIVE किंवा अज्ञात ⇒ save नाकारलं (CLI, dashboard, Telegram तिन्ही).

### Telegram user ID (V1 approver साठी — आत्ताच काढून ठेवा)
1. Telegram मध्ये **@userinfobot** ला कुठलाही संदेश पाठवा → तो `Id: 123456789` असं उत्तर देतो. हाच तुमचा user ID.
2. (पर्याय) तुमच्या trading bot ला संदेश पाठवा, मग `https://api.telegram.org/bot<TOKEN>/getUpdates` उघडा → `"from":{"id": …}`. खाजगी chat मध्ये `chat.id` = तोच आकडा.
3. V1 मध्ये VPS `.env`: `TELEGRAM_APPROVER_IDS=123456789` (फक्त तुमचा). Token कुठेही paste करू नका.

## V1 — veto_then_confirm / auto_veto / human_confirm

**Defaults अजून `notify` च.** G-V1 (dry-run screenshot) नंतर तुम्ही ठरवाल त्या bot वर `veto_then_confirm` चालू करायचा
(`/vision vtc dynamic_sr_instant` Telegram वर, किंवा dashboard → 👁 पान → ⚙️ Settings, किंवा `python3 -m vision.config set …`).

| mode | vision मत | काय होतं |
|---|---|---|
| `veto_then_confirm` | disagree | आपोआप skip (Telegram वर फक्त माहिती, बटण नाही) ⇒ shadow trade |
| | agree / gray | ✅ / ❌ बटणं. Approve ⇒ agree पूर्ण, gray **अर्धा** size. Reject ⇒ skip (shadow) |
| | unavailable | ✅ / ❌ बटणं (Approve ⇒ पूर्ण) |
| | (मुदतीत उत्तर नाही) | `timeout_action = auto_veto` ⇒ auto_veto चे नियम: agree पूर्ण, gray ⇒ `vision_gray_action`, unavailable ⇒ `vision_fail_action` (`skip` ⇒ सगळे skip) |
| | (approver / बटणं नाहीत) | 10 मिनिटं न थांबता **लगेच** वरचा timeout नियम (Telegram वर फक्त माहिती: ENTRY मंजूर / नाकारली) |
| `auto_veto` | agree / gray / disagree / unavailable | बटण नाही: 1 / `vision_gray_action` / `vision_disagree_action` / `vision_fail_action` |
| `human_confirm` | कोणतंही | नेहमी बटणं (gray ⇒ अर्धा). Reject / timeout ⇒ skip |

```
Bot cycle 1: सगळे gates पास ⇒ vision.gate.entry_gate ⇒ QUEUED + HOLD   (signal_log SKIPPED_VISION_PENDING — hit / cooldown मध्ये मोजत नाही)
Worker:      chart ⇒ vision ⇒ decide ⇒ APPROVED / REJECTED / PENDING_HUMAN (बटणांसह chart; मुदत approve_window_min = 10)
Telegram service (long-polling): ✅ ⇒ APPROVED · ❌ ⇒ REJECTED  (WHERE status = 'PENDING_HUMAN' — एकदाच)
Worker:      मुदत संपली ⇒ timeout नियम (caption बदल, बटणं गायब)
Bot cycle N: forced level (touch नसला तरी तो level पुन्हा तपासतो) ⇒ bot चे सगळे gates पुन्हा ⇒ gate:
             APPROVED ⇒ drift guard ⇒ ठीक: EXECUTED, lots = floor(lots × factor) · अपयश: DRIFT_REJECTED + shadow
             REJECTED ⇒ SHADOWED + shadow trade.  अर्ध्या size चे lots 0 ⇒ shadow
Worker:      APPROVED / REJECTED ला exec_window_min (5) मध्ये bot पोहोचला नाही (gates बदलले) ⇒ EXPIRED (Telegram माहिती)
```

- **Forced level (touch नसताना):** फक्त V1 mode, फक्त आजचे, फक्त exec_window आतले निर्णय. ENTER फक्त ताज्या APPROVED वरून — mode बदलला / चूक / row नाही ⇒
  `SKIPPED_VISION_FORCED_STALE` (touch शिवाय algorithm चा entry कधीच नाही). signal_log मध्ये `hit_type = VISION_FORCED`.
- **Worker बंद असला तरी अडकत नाही:** bot चा gate स्वतः timeout लावतो — PENDING_HUMAN मुदत ⇒ timeout नियम; QUEUED / RUNNING `approve_window_min` पेक्षा जुने ⇒
  "vision unavailable + उत्तर नाही" (veto_then_confirm ⇒ algorithm, human_confirm ⇒ skip, auto_veto ⇒ `vision_fail_action`).
- **दिशा / breakout प्रकार बदलला** ⇒ जुना निर्णय रद्द (EXPIRED, shadow नाही), हा touch नवा signal.
- **½ size:** चालू leg चे lots 0 झाले (उदा. 1 lot × ½) ⇒ entry नाही, shadow (0-lot / multi-account किमान-1-lot order टाळायला).
- **नाकारलेला level:** `shadow_cooldown_min` (30) मध्ये पुन्हा विचारणा / shadow नाही (`SKIPPED_VISION_COOLDOWN`); आधीचा shadow उघडा ⇒ नवा shadow नाही.

- **Shadow trade:** नाकारलेला signal मूळ lots ने PAPER मध्ये, वेगळ्या source ने (`dynamic_sr_instant_vision_shadow`, `srv2_momentum_reversal_vision_shadow`).
  Exit नियम मूळ bot चेच (`SHADOW_EXIT_PARENT_SOURCE`). खरा entry नाही ⇒ hit / cooldown / max-open मध्ये मोजत नाही. Outcome chart तोच trade जोडतो.
- **Drift guard (entry च्या क्षणी):** 1. spot signal-spot पासून `max_drift_mr` (0.5) × median range (setup TF चे शेवटचे 20 bars, worker chart वरून;
  chart नसेल तर spot च्या 0.10%) पेक्षा दूर · 2. invalidation (setup मध्ये असेल तर) ओलांडली / level ची बाजू बदलली · 3. pullback origin ओलांडला — bot ने origin
  दिला तरच (5-Min / 15M bots सध्या origin मोजत नाहीत ⇒ त्यांना लागू नाही) · 4. bot चे daily-loss / kill switch / max-open — bot चे gates पुन्हा चालतात म्हणून रचनेनेच.
- **Security:** callback = `v1|signal_id|A/R|HMAC16(VISION_CALLBACK_SECRET)`; `from.id` **आणि** `chat.id` दोन्ही `TELEGRAM_APPROVER_IDS` मध्ये; दुसऱ्यांदा / replay ⇒ "आधीच ठरलं";
  मुदतीनंतर ⇒ "मुदत संपली". Secret / approvers नसतील, किंवा बटणं जिथे जातात तो chat (`TELEGRAM_CHAT_ID`) approvers मध्ये नसेल (group chat ⇒ त्याचा id पण जोडा)
  ⇒ बटणं पाठवत नाही (caption मध्ये कारण; service सुरू होताना इशारा) ⇒ timeout नियम. Service restart ⇒ उघडे PENDING_HUMAN ⇒ EXPIRED.
- **Commands** (फक्त approver): `/pending` · `/today` (signals + खर्च) · `/vision <off|shadow|notify|veto|confirm|vtc> <bot>` (LIVE guard सह).
- **Vision worker अपयश (V1 row)** ⇒ "unavailable" सारखं (veto_then_confirm ⇒ बटणं / algorithm), signal अडकत नाही.
- **Exits:** `trade_monitor.py` / `trading_engine.py` / `engine_service.py` मध्ये vision import नाही (AST test); trading_engine मध्ये फक्त shadow source ची नावं.

### Dry-run (G-V1) — order नाही
`python3 scripts/vision_dryrun.py [--no-vision] [--window 3] [--drift] [--mode auto_veto]` — शेवटच्या 1m candle वर TEST signal (bot `vision_dryrun`) ⇒ chart + बटणं ⇒
तुम्ही ✅ / ❌ / काहीच नाही ⇒ drift guard ⇒ Telegram वर "🧪 DRY-RUN निकाल — कोणताही order नाही". Script मध्ये `trading_engine` चा import नाही (test).
Telegram service चालू नसेल तर script स्वतः getUpdates वाचतो.

## Prompt v2 — "knowledgeable" vision (`signal_check_v2`, TRADE_VISION_PROMPT_V2)
- **Chart v2** (`vision/chart.py` + `vision/context.py`, सगळं signal पर्यंतच): traded level L (जाड), major levels प्रत्येक बाजूला 2 (`M1↑ / M1↓`,
  role reversal ⇒ `F`; `price_action/major_levels.py`, asof = signal, 15m bars, ~3 आठवडे), PDH / PDL / PDC आणि PWH / PWL (आधीचा **पूर्ण** दिवस /
  आठवडा, dotted), आजचा OPEN + opening range (पहिली 15 मिनिटं, फिकट पट्टा), confirmed swing H / L, session separators. 0.1 × median range
  पेक्षा जवळचे overlays ⇒ एक label (`PDH+M1↑`); y-range बाहेरचे ⇒ कडेला ▲ / ▼. Labels इंग्रजीत, जवळचे labels एकमेकांवर येत नाहीत.
  Composite reversal box: bot N सांगत नाही ⇒ नाही.
- **Signal text v2:** levels चा तक्ता (नाव, अचूक किंमत, median range च्या पटीत अंतर, role), room (पुढचा विरोधी level), invalidation अंतर, open पासून मिनिटं
  (पहिली 15 मिनिटं / शेवटचा तास flag), gap % + भरला का, weekly expiry किती दिवसांवर (contract master), bot tags.
- **System prompt v2:** trader's playbook (entry philosophy, levels, real vs false break, trend, Elliott, reversal candle, time) — इंग्रजीत,
  ~1.6k tokens, `cache_control`. फक्त `reason` मराठीत. `max_tokens` default 1200 (`VISION_SIGNAL_MAX_TOKENS`), `VISION_SIGNAL_EFFORT=low`.
- **JSON v2** (schema-enforced): htf_trend, setup_structure, trend_context, level_real, level_kind, confluence, wave_position,
  correction_complete, false_break_reclaim, reversal_touch / reclaim / strength / close_location, reversal_valid, is_breakout_entry,
  room_to_next_level, time_risk, false_break_risk, elliott_note (≤ 100), verdict, reason (≤ 160), confidence. अवैध enum / field गायब ⇒ unavailable.
- **Verdict नियम (code मध्ये, vision चं मत यांपेक्षा positive कधीच नाही)** — settings `v2_disagree_rules` / `v2_gray_rules`, dashboard वर on/off:

| नियम | प्रकार | अट |
|---|---|---|
| `breakout` | disagree | is_breakout_entry = yes |
| `reversal_invalid` | disagree | reversal_valid = no |
| `weak_level` | disagree | level_kind ∈ {mid_range, magnet} |
| `bad_wave` | disagree | wave_position ∈ {a_end, inside_b_or_triangle} |
| `bad_close` | disagree | reversal_close_location = bad |
| `opening` | disagree | time_risk = opening |
| `unclear` | gray | कोणतंही unclear (htf_trend वगळून) |
| `correction_incomplete` | gray | correction_complete = no |
| `tight_room` | gray | room_to_next_level = tight |
| `middle_close` | gray | reversal_close_location = middle |
| `impulse_running` | gray | wave_position = impulse_running |
| — | gray | दोन audits असहमत |

- **auto_veto (तुमचा नियम):** agree ⇒ entry; gray / disagree / unavailable ⇒ skip (`vision_gray_action = skip`, `vision_fail_action = skip`).
- **Caption:** ✅ ENTRY मंजूर / ❌ ENTRY नाकारली (कारण) + trend (HTF / setup), level प्रकार, wave position, reversal 4 टप्पे ✓ / ✗, room,
  false-break risk, लागलेले नियम.
- **Dashboard:** v2 fields चे columns, `prompt_version` filter + गट (v1 / v2 वेगळे), कुठल्याही v2 field वर filter, नियम on/off.
- **जुने records** `signal_check_v1` म्हणूनच; 15-मिनिट reuse फक्त त्याच prompt version चं मत.
- **नमुने:** `python3 scripts/vision_v2_samples.py` — शेवटचे 3 signals पुन्हा v2 ने (JSON + code verdict छापतो, Telegram वर "trade नाही"),
  vision_signals ला हात नाही. `--no-vision` ⇒ फक्त chart + text (खर्च 0).
- **खर्च:** एका audit ला ≈ 900 (image) + ~1.6k (system, cache read नंतर स्वस्त) + ~450 (text) input, ~400 output ⇒ cache नसताना ≈ $0.01, cache read सह
  कमी (≤ $0.015 / signal). दैनिक $0.30 तसाच. आठवड्यात सरासरी > 20 signals / दिवस दिसले तर कळवणे.
- **Evaluation:** 30 signals नंतर `docs/reports/vision_human_eye.md` — field × outcome (उदा. level_kind = flip वि. बाकी, room = tight), नाकारलेल्यांचा
  shadow P&L, random-veto baseline. Few-shot (v3) फक्त तुम्ही label केल्यानंतर.

## v2.1 — gap संदर्भ + line chart + तुमच्या दुरुस्त्या (`signal_check_v2_1`)
- **Image ~1000×900:** A setup candles · B higher candles · **C line chart** (15m closes, `line_lookback_sessions` = 5; L / M / PDC / PDH / PDL,
  swing ठिपके, session separators, signal क्षणी उभी रेषा — त्यानंतर काहीच नाही). Image tokens ≈ w × h / 750 ≈ 1.2k.
- **Panel A:** [PDC, Open] gap पट्टा (भरलेला भाग गडद), opening window (09:15–09:30) छटा, जुने unfilled gaps (`UG`), composite reversal candles
  (1–3) भोवती dotted box, swing `sH` / `sL` ("L" फक्त traded level), **INV** रेषा नेहमी (bot ने न दिल्यास L ∓ `inv_buffer_mr` × median range).
  Level labels वर आजचं वागणं: `held S` / `held R` / `broken↓` / `broken↑` / `reclaimed`.
- **`vision/gap_context.py`** (causal): gap_atr = (Open − PDC) / ATR14, वर्ग G0–G5 + E, fill %, PDC touch / पलीकडे acceptance, पहिल्या 2–6 पूर्ण
  15m bars चं वर्तन (acceptance / rejection / undecided, code ने), जुने unfilled gaps, event दिवस (`_global.event_days`, dashboard).
  G0 सीमा `gap_g0_atr` = 0.25 (IS 2015–2021 |gap_atr| p50 = 0.247), मोठा gap `gap_large_atr` = 0.63 (p90), G5 leg `gap_stretch_atr` = 3.
  Muhurat / special (< 200 bars) sessions PDC / ATR मधून वगळले. पुढच्या gap-module PR मध्ये `price_action/gap_context.py` मध्ये हलवायचा.
- **Signal text:** levels तक्ता = नाव (एकाच किमतीचे एकत्र, उदा. `M1↑+PWH`) | किंमत | position (spot च्या वर / खाली, median range पट) |
  **today_role** (held_as_support / held_as_resistance / broken_down / broken_up + वेळ / untested; reclaim असेल तर तसं). **L ची ओळ:** किंमत L वर कुठून
  आली, आज कुठल्या बाजूला उघडला, आधी (शेवटच्या 3 bars आधी) L कसा वागला, real break झाला का / reclaim. **Room:** फक्त न तुटलेले विरोधी levels; < 1 × median range
  ⇒ "ROOM TIGHT (नाव)". Gap विभाग (वरचे सगळे आकडे) आणि event.
- **today_role व्याख्या:** बाजू = आजच्या पहिल्या open ची बाजू. Real break = बाजू बदलणारा close, buffer (0.25 × median range) सह, पुढच्या bar ने reclaim नाही
  (शेवटचा bar ⇒ अजून reclaim नाही). Break चिकटतो (retest सुद्धा "broken"). उघडण्याच्या बाजूकडे परतणारा break = **reclaim** (false break / spring).
- **Code तथ्यं (`apply_facts`, फक्त कडक दिशेने):** पहिली 15 मिनिटं ⇒ time_risk = opening; room < 1× ⇒ tight; संदर्भ नाही ⇒ room unclear;
  **L तुटला (reclaim नाही) आणि त्याच दिशेने spread** (broken_down + bear call / broken_up + bull put) ⇒ is_breakout_entry = yes (तुमचा नियम 4);
  **bear call पण किंमत L वर वरून आली** (किंवा bull put खालून) आणि L held / untested / त्याच दिशेने broken ⇒ pullback नाही ⇒ breakout. नमुना 3 सारखा
  reclaim (spring) breakout नाही.
- **नवीन नियम (settings मध्ये on/off):** disagree — `gap_disallowed` (model: gap_setup = disallowed), `gap_chase` (code: G3 / G5, gap दिशेने, fill < 25%,
  L PDC / gap edge जवळ नाही), `gap_b_pdc_accept` (code: G3 / G5, PDC पलीकडे acceptance, gap दिशेने). gray — `gap_undecided_early` (code: undecided आणि
  < 6 पूर्ण 15m bars), `line_conflict` (model), `event_day` (code), `gap_c_alone` (model: setup C, confluence नाही).
- **JSON v2.1:** v2 + gap_class_agrees, gap_behaviour, gap_setup (A / B / C / none / disallowed), line_structure, line_vs_candles.
- **नमुने:** `python3 scripts/vision_v2_samples.py --historical` — तुम्हाला दाखवलेले तेच 3 (2021 IS, repo मधला parquet) + त्यांचं JSON.

### v2.1 — तुमच्या 4 दुरुस्त्या (नमुने पाहून, अंतिम)
- **Room:** trade दिशेने पुढचा कोणताही level — आज तुटलेला (flip: broken support ⇒ आता resistance, text मध्ये "flip") आणि untested सुद्धा; फक्त
  magnet वगळा (आज closes ने ≥ 4 वेळा ओलांडलेला). < 1 × median range ⇒ "ROOM TIGHT (नाव)" ⇒ gray. (नमुना 1: PWL 0.30×; नमुना 3: PDC 1.89×.)
- **Deterministic code नियम (disagree, settings मध्ये on/off):** `wrong_approach` — bear call ⇒ किंमत L कडे खालून, bull put ⇒ वरून; उलट ⇒ disagree.
  2b — signal bar (अपूर्ण असला तरी) किंवा मागच्या 3 bars नी trade दिशेने कोणताही level real-break ने तोडला (उघडण्याच्या बाजूपासून दूर; परत येणारा
  reclaim मोजत नाही) ⇒ is_breakout_entry = yes ⇒ `breakout`. `role_conflict` — bot-role RESISTANCE पण L held_as_support (किंवा SUPPORT पण
  held_as_resistance) ⇒ disagree. (आधीचा "नियम 4" / approach-logic यांनी बदलला.)
- **Gap वर्ग:** daily trend range / unclear ⇒ `GX-inside` / `GX-beyond` (G1 / G3 / G4 नाही); text: WITH / AGAINST / "no clear daily trend".
- **Opening behaviour** (प्रत्येक बंद 15m bar वर पुन्हा, lock नाही, इतिहासासह — उदा. "09:15 test, 09:30 acceptance (open-test-drive)"):
  rejection = gap दिशेने नवीन extreme न होता open ओलांडून PDC कडे buffer पेक्षा जास्त; acceptance = open-test-drive (नवीन extreme + PDH / PDL पलीकडे
  टिकाव; inside gap ⇒ open पलीकडे buffer सह); acceptance नंतर परत open खाली ⇒ undecided ("failed drive").
- **नमुने VPS वर:** `python3 scripts/vision_v0_smoke.py --sample` — 3 नमुने खऱ्या vision call सह, JSON + code verdict + खर्च + सारांश.

### v2.1 — शेवटच्या 3 दुरुस्त्या
- **Signal bar बंद नसणे:** Instant bot चा signal 5m bar च्या मधे येतो. Text: "Signal bar 10:30-10:35: NOT CLOSED yet (1/5 min)". Levels तक्ता:
  "held_as_support until 13:05; the current OPEN (unfinished) bar is breaking it down" (breakout ओळीशी विरोध नाही). Code: bar बंद नाही ⇒
  reversal_valid = unclear ⇒ gray. **`vision_wait_for_bar_close` (default on):** worker signal चा setup bar बंद होईपर्यंत row QUEUED ठेवतो
  (fetch / खर्च नाही), मग chart आणि संदर्भ bar च्या close पर्यंत (title: "evaluated at bar close HH:MM"), मग निर्णय; entry च्या क्षणी drift guard.
- **today_role "reclaimed":** आधी real break, नंतर पूर्ण bar चा close परत आजच्या उघडण्याच्या बाजूला. Reclaimed ⇒ role_conflict नियम लागू नाही.
  Chart label "PDL · reclaimed".
- **Code-only pre-verdict:** vision शिवाय, फक्त OHLC तथ्यं + नियम (`signal_audit.pre_verdict`) — samples output मध्ये प्रत्येक नमुन्यासाठी.

## Chart images कायमस्वरूपी (§11)
- **`_sent.png`**: vision ला गेलेली आणि Telegram वरची हीच फाईल. आधी disk वर `O_EXCL` ने लिहिली जाते (नाव असेल तर `_2`; overwrite कधीच नाही),
  temp फाईल → `os.link` (अर्धवट फाईल अंतिम नावाने कधीच नाही), मग परत वाचून sha256 तपासला जातो. Record मध्ये path + sha256, prompt_version, model, vision JSON (tokens), cost, algo निर्णय, अंतिम निर्णय
  (V0 = algo), (V1) माझा निर्णय + वेळ आणि drift guard.
- **`_outcome.png`** (`python3 -m vision.outcome`, दर 15 मिनिटं 09:30–16:15 IST): trade बंद झाल्यावर.
  - जुळणी: live_trades (read-only) मध्ये त्याच bot चा source, PAPER, entry signal नंतर 0–10 मिनिटांत.
  - आधीच दुसऱ्या signal ला जोडलेला trade पुन्हा नाही. Signal आणि entry च्या मध्ये त्याच bot चा दुसरा signal असेल तर तो trade नंतरच्या signal चा.
  - DB चूक ⇒ error, पुढच्या run ला पुन्हा (चुकून no_trade नाही).
  - Signal पासून exit पर्यंत 5m candles; signal / ENTRY / EXIT खुणा, level रेषा, P&L, SL / target (₹).
  - ठळक शीर्षक "POST-HOC: vision ला पाठवलेली नाही · NOT SENT TO VISION". VPS वर Devanagari font (`fc-list :lang=mr`) नसेल तर फक्त इंग्रजी,
    कारण font शिवाय मराठी अक्षरं डबे दिसतात. Font: `apt-get install -y fonts-noto-core`.
  - Legs चे strikes (`legs_json`) डॅश रेषा म्हणून: SELL लाल, BUY हिरवट-निळी. लांबचे strikes (candles च्या range पेक्षा / ~0.6% पेक्षा दूर) कडेला ↑ / ↓ खुणेने — candles लहान होऊ नयेत म्हणून. Credit spread मध्ये नफा / तोटा याच सीमांवर ठरतो.
    SL / target P&L (₹) स्तरावर असतात (spot मध्ये नाहीत), म्हणून ते मजकुरात.
  - हा chart vision कडे कधीच जात नाही — `outcome.py` मध्ये vision / API चा import नाही (test).
  - Trade सापडला नाही आणि 1 दिवस झाला ⇒ `no_trade`.
- **Dashboard → ANALYZE → 👁 Vision & Human Eye:**
  - दोन्ही images शेजारी, मत, निर्णय, निकाल;
  - filters: तारीख, bot, verdict, win / loss / open / no_trade;
  - CSV export, disk वापर.
- **Archive** (`scripts/vision_archive.py`, रोज 23:50 IST):
  - `data/visual_audit/<day>/` → private `trade-data/visual_audit/YYYY-MM/<day>/`, सोबत `vision_records_<day>.jsonl`;
  - आधी destination खरंच trade-data checkout आहे याची खात्री (public repo कधीच नाही).
  - रोज: marker नसलेले / marker शी न जुळणारे सगळे दिवस (आधीचा अयशस्वी push, उशिरा आलेला outcome) + मागचे 3 दिवस (records ताजे).
  - copy नंतर sha256 तपासणी. Push आधी `fetch` + `rebase`.
  - push नंतर remote blob id = local `hash-object` ⇒ तरच `.archived` marker ({नाव: sha256}).
  - 90 दिवसांनंतरचे local folders फक्त marker असेल आणि प्रत्येक local फाईलचा sha256 marker शी जुळत असेल तरच delete.
  - Push अयशस्वी ⇒ Telegram इशारा, delete नाही, पुढच्या रात्री पुन्हा.
  - Disk > 80% ⇒ Telegram इशारा. PNG > 150 KB ⇒ यादी. आपले charts ~90 KB.
  - `data/visual_audit/` gitignored — public repo मध्ये images कधीच नाहीत.

## पुढचे टप्पे
- **V1** ✅ (वर). G-V1: dry-run screenshot (approve / reject / timeout) ⇒ मग कोणत्या bots वर `veto_then_confirm` ते तुम्ही ठरवा.
- **V2** 08:00 level audit (NIFTY, 1 image, सर्वात स्वस्त model), `level_gate` off.
- **V3** "Vision & Human Eye" पान + साप्ताहिक `docs/reports/vision_human_eye.md` (random-veto baseline ≥ 1000).
