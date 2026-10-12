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

## 4. Abhi चे trades (NIFTY bear call, 12 Oct) — message का नाही?

TODO (Abhi चे charts + diag): प्रत्येक setup साठी वरच्या कोणत्या कारणाने अडलं. Engine-बाजूचे (§7 a–f: maturity cap, 09:15 candle,
sloping resistance, 1H level blind spot, FUT volume alignment) — `claude/oct12-blockers` branch चा अहवाल.

## 5. आजपासूनचा बदल (one bot) — `claude/one-bot-tomorrow`

- फक्त 15M SRv2 ON (NIFTY / BANKNIFTY / SENSEX, PAPER), `signal_source = engine`; engine = decision3 (V22) live, प्रत्येक बंद 15M bar
  09:30–15:00 (`engine3_live.py`, `scripts/install_engine_schedule.sh`). बाकी bots OFF (`scripts/set_one_bot_mode.py`, `--revert`).
- PAPER instruments BANKNIFTY / SENSEX + Vision symbols — त्याच script ने (वरचे दोन blockers).
- Fail-closed: data / FUT volume / 5M नाही ⇒ entry नाही + Telegram एक ओळ (symbol मागे दिवसातून एकदा).
