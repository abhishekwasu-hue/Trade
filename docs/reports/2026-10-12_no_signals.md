# 12 Oct 2026 — Telegram ला एकही setup message नाही (निदान, skeleton)

स्थिती: **code वरून ठरवता येणारं भरलं; VPS वरच्या गोष्टी `TODO (diag)`** — `scripts/diag_today.py --out …` चा output
(trade-data `live_export/2026-10-12/`) आल्यावर भरायच्या. हा अहवाल order / settings काहीही बदलत नाही.

## 1. आज कोणता code चालत होता?

| प्रश्न | code वरून | TODO (diag) |
|---|---|---|
| VPS commit / branch | deploy = `deploy-main` (docs/PAPER_MONDAY.md चा deploy one-liner), rollback file `/root/paper_rollback.txt` | diag §1: `HEAD`, branch, reflog वेळा |
| Level-gate MVP deploy 09:15 आधी? | deploy command फक्त संध्याकाळी दिला ⇒ बहुधा **नाही** (म्हणजे सकाळी जुना code, touch / confirmation-पूर्व वर्तन) | diag §1 reflog: `checkout: moving … deploy-main` ची वेळ < 09:15 IST? |
| Engine service | `scripts/engine_signal_run.py` (cron `1,16,31,46 3-10`) = **decision2, फक्त NIFTY** (`--symbols` default NIFTY). decision3 (V22 method engine) **live कुठेच चालत नव्हता** — फक्त review scripts (`scripts/v22_check.py`) | diag §3 crontab; §4a engine_signals rows (`payload` मध्ये engine नाही ⇒ decision2) |

## 2. Bot × symbol settings (आजचे) आणि त्यांचा परिणाम

Code defaults (Supabase मध्ये बदल नसेल तर हेच; प्रत्यक्ष values: diag §2):

| Bot (settings key) | enabled field (default) | trading_mode | entry_mode (PAPER default) | signal_source (default) | परिणाम |
|---|---|---|---|---|---|
| 15M SRv2 (`15m_dynamic_sr`) | `symbol_enabled`: NIFTY ✔, BANKNIFTY / SENSEX ✘ | PAPER | confirmation (Daily trend gate + बंद candle वर commitment) | own | own ⇒ engine चं मत फक्त caption; entry = SRv2 चा स्वतःचा level gate |
| 5M Instant (`1m_instant`) | NIFTY ✔ | PAPER | confirmation | own | — |
| SR V3 PAPER shadow | `1m_instant.srv3_shadow_enabled` ✘ | PAPER | — | own | — |
| Classic SR (`classic_sr_reversal`) | सगळे ✘ | PAPER | confirmation | — | — |
| MCX futures | सगळे ✘ (opt-in) | PAPER | confirmation (LIVE ⇒ touch) | — | — |
| oi_signal / credit_spread / oi_greeks auto traders | settings flag नाही — फक्त cron | `--mode` | — | — | diag §3 crontab |

इतर gates जे message अडवू शकतात (code):
- `config.yaml paper.instruments`: **BANKNIFTY / SENSEX `enabled: false`** ⇒ त्या symbols वर PAPER entry / approval मार्गच नाही (`paper/bot_hooks.pre_cycle`).
- Vision settings `symbols` default **फक्त NIFTY** ⇒ इतर symbols `SKIPPED_NOT_ENABLED` (approval message नाही).
- `approval_required` = True ⇒ ✅ message फक्त Vision row झाल्यावर; vision_worker / vision_telegram services बंद ⇒ message नाही (diag §3).
- confirmation mode: Daily trend `origin_risk` / `origin_broken` / parent correction ⇒ "no entry: trend unclear" (दिवसभर); level DB मधला (15M/30M/60M ACTIVE zone) नसेल तर area नाही.
- Kill switch / trading pause / PAPER pause (diag §2).

TODO (diag): प्रत्येक combo ची प्रत्यक्ष value + चुकीची setting (value → योग्य value) यादी.

## 3. Per-15M-bar निर्णय (आज)

TODO (diag §4a/§4b/§4c): engine store rows (decision2, NIFTY) + signal_log (SRv2: SKIPPED_* कारणे) + level-gate trend cache. प्रत्येक bar:
no touch / against trend / gate / approval not sent / error.

## 4. Abhi चा trade (NIFTY bear call, 12 Oct पहिला तास) — message का नाही?

Code वरून (तपशील: `docs/reports/2026-10-12_engine_blockers.md`) — सकाळी **दोन स्तरांवर** अडलं असतं:

1. **Engine path चालूच नव्हता:** live engine = decision2, फक्त NIFTY; decision3 (V22, trend → area → pullback → commitment → R:R)
   कुठेच live नव्हता ⇒ `signal_source = engine` असतं तरी decision3 setup येऊ शकत नव्हता (§1).
2. **decision3 चालला असता तरी (9 Oct पर्यंतच्या खऱ्या data वर तपासलं):**
   - (b) **maturity cap** — 8–9 Oct प्रत्येक bar वर "impulse mature ⇒ entries weak" ⇒ setup नाही. **Bug** (owner नियम: maturity फक्त
     evidence) ⇒ दुरुस्त: maturity फक्त grade A → B, कधीच अडवत नाही.
   - (e) **22,476–22,809 resistance 8 Oct ला "मेला"** (death rule role0) ⇒ 12 Oct ला ≈22,600–22,670 area च नव्हता. **Bug** ⇒ TL1
     (`level_death_side = "role"`, Abhi मंजूर) — 9 Oct ला level आता जिवंत.
   - (c) 09:15 candle two-candle pattern मध्ये धरली जात नव्हती ⇒ दुरुस्त: 09:15 चा sweep / wick evidence, entry 09:30 पासूनच.
   - (d) 30-Sep high पासूनची उतरती trendline (09:15 ला ≈22,654) — horizontal level सोबत confluence असेल तर area (एकटी line नाही);
     तुटलेली line / price च्या चुकीच्या बाजूचं area वगळलं; grade parent level पेक्षा वर नाही.
   - (f) FUT volume 5M → 15M (09:15 anchor) बरोबर; पण stored FUT data 8 Oct ला संपतो ⇒ VPS collector वरून.
3. **Replay:** synthetic fixture वर 09:45 bear call A (entry 22,708.92 · SL 22,985.75 · target 21,842.79 · R:R 3.13, a2/c0/c1 चालू) +
   dry-run approval message. **खरा 12 Oct data अजून चालवलेला नाही** — VPS वर
   `python3 scripts/replay_day.py --symbol NIFTY --day 2026-10-12 --source upstox --dry-run-telegram` (read-only). खऱ्या data वर
   R:R < 3 आला तर setup नाही ("valid read, skipped on R:R") — तो निकाल बदलण्यासाठी threshold फिरवणार नाही.

TODO (Abhi चे charts + diag): त्याचे bar-by-bar कारण खऱ्या data वरून.

## 5. आजपासूनचा बदल (one bot) — `claude/one-bot-tomorrow` (main वर merged, PR #310)

- फक्त 15M SRv2 ON (NIFTY / BANKNIFTY / SENSEX, PAPER), `signal_source = engine`; engine = decision3 (V22) live, प्रत्येक बंद 15M bar
  09:30–15:00 (`engine3_live.py`, `scripts/install_engine_schedule.sh`). बाकी bots OFF (`scripts/set_one_bot_mode.py`, `--revert`).
- PAPER instruments BANKNIFTY / SENSEX + Vision symbols — त्याच script ने (वरचे दोन blockers).
- Fail-closed: data / 5M नाही ⇒ entry नाही + Telegram ओळ (पहिलं अपयश, 60 मिनिटांनी अजून अपयश असेल तर, मग "recovered"). FUT volume नाही ⇒
  volume NA, grade कमाल B (entry अडत नाही).
- सकाळी चालू: a2 (absorption ⇒ वाट), c0 (dominant candle + volume > window सरासरी; NA ⇒ कमाल B), c1 (5M CHoCH by close) — तिन्ही.

## 6. Engine dry run on real recent data — BANKNIFTY, merged main (13 Oct पहाट; `scripts/v22_setup_charts.py run --m15 … --ltf … --futures …`)

Live path सारखेच inputs जिथे उपलब्ध (trade-data): 15M 2026-07-13 … 10-09 (1,575 bars), Daily पूर्ण (2016 →), 5M spot + front-month FUT 5M
volume **फक्त 2026-09-30 … 10-06** (collector; त्याआधी c1 ⇒ "LTF data missing" ⇒ wait, volume NA). Setting / threshold बदल 0. निकाल
trade-data `review/v22/banknifty_merged_1013/` (`bars.json` = प्रत्येक bar चा पहिला ✘ gate; tag debug).

- **Setup 0** (wait 1,519 · no_trade 56); Daily सगळीकडे DOWN (impulse; Weekly UP ⇒ cap B). ③ (level ला स्पर्श नाही / K नाही) 1,347 bars.
- **30 Sep – 6 Oct (100 bars, पूर्ण inputs):** ③ 38 · ⑤ 25 · ④ 20 · ⑥ 15 · ⑦ 2. ⑥ मध्ये खरे volume / 5M निर्णय दिसतात: 13:30 "commitment on
  low volume (0.5×)", 14:30 "not dominant (1.4×)", 10:45–11:45 absorption, 5M CHoCH 13:40 ला नोंदला (sweep of high 55,135.5, close below
  HL 55,049). म्हणजे a2 / c0 (volume सह) / c1 live data वर end-to-end चालतात.
- **30 Sep 14:00 आणि 14:15 — bear call ⑦ वर अडला: R:R 0.06 / 0.21.** a2 ✔, c0 ✔ (inside_break 1.5× body, volume 1.42×; 14:15 strong_close
  2.4×, 1.84×), c1 ✔. कारण: resistance area = **54,891–56,200 (1,309 points, जन्म a:D-prior + a:W-prior + a:D + a:D2 + b + c)** ⇒ SL 56,220
  (entry 54,930 पासून 1,290 वर); target 54,854 (जवळचा जिवंत level, I_end 53,788 नाही). Charts `BANKNIFTY/bar_20260930_1400.png` / `_1415.png`
  (volume pane सह). हे TL2 (merge रुंदी) + D12-5 (target = जवळचा level) चं live उदाहरण — NIFTY 9 Oct (333 pts पट्टा) सारखंच, मोठं.
  (Chart शीर्षकात "conviction A": no_trade row ला cap ⑦ नंतर लागतो, म्हणून इथे cap-पूर्व grade; निर्णयावर परिणाम नाही.)
- 14:30 ला `vol_mult` None (FUT 5M rows त्या 15 मिनिटांत नाहीत — collector gap) ⇒ "not dominant" फक्त body वरून; fail-closed नाही (OB1 प्रमाणे).
