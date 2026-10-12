# BagMitra — Orchard Management Platform for Indian Fruit Growers (Spec v1)

You are starting a brand-new repository: `bagmitra` (name may be changed later by the owner; keep it configurable in one place). This is a greenfield project. Read this entire spec first, then write `docs/PLAN.md` mapping every section to concrete files and milestones, then begin Milestone 0 without waiting.

All code, comments, docs, commit messages, API names and English UI source strings in English only. User-facing strings are translated via i18n files — Marathi, Hindi and English at launch, and the platform must support all major Indian languages (see §2 i18n) so a grower anywhere in India can use it in their own language.

---

## 0. Engineering rules — non-negotiable

The owner has had poor experiences with careless, untested code in other projects. These rules exist to prevent a repeat. CI enforces them; a PR that violates any of them is not merged.

1. **Test-first.** Every feature starts with failing tests (unit + where relevant integration), then implementation. Backend coverage gate ≥ 85%, app domain/logic coverage ≥ 80%. No coverage drop allowed in a PR.
2. **Strict typing & linting.** Python: `mypy --strict`, `ruff` (lint + format), `bandit` for security. Dart: `analysis_options.yaml` with strict mode (`strict-casts`, `strict-inference`, `strict-raw-types`), `dart analyze` zero warnings, `dart format` check. All run in CI; any failure blocks merge.
3. **Contract-first API.** The OpenAPI schema is the source of truth. FastAPI generates it; the Dart API client is auto-generated from it in CI (`openapi-generator` or `swagger_dart_code_generator`). Hand-written request/response models in the app are forbidden.
4. **Small PRs.** One feature per PR, ≤ 400 changed lines of production code (tests excluded). Each PR description includes a filled self-review checklist: correctness, offline behaviour, error handling, Marathi strings present, tests added, migration reversible, no hardcoded business values.
5. **No hardcoded business values.** Crop stages, bahar calendars, disease-risk rules, thresholds, prices, plan limits, prompt templates, notification texts all live in DB/config and are editable from an admin UI. Code contains mechanisms, not agronomy numbers.
6. **Offline-first is a requirement, not a feature.** Every user-facing write must work with no network and sync later. Every PR touching the app must state how it behaves offline. Integration tests cover offline → online sync.
7. **Definition of Done per milestone** (written in PLAN.md before starting the milestone): tests green, CI green, demo checklist executed by the session on an emulator and recorded in `docs/PROGRESS.md`, docs updated, ADR written for any architectural choice.
8. **Work continuously.** Never stop to wait for the owner. Unclear points → log in `docs/OPEN_QUESTIONS.md` with a provisional default and proceed. Self-review every diff before pushing. Merge your own PRs when CI is green and the self-review checklist is complete. Never deploy to production — the owner does that.
9. **Security basics.** Supabase RLS on every table (owner-only rows, consultant access via explicit grants). No secrets in repo; `.env.example` only. Input validation at API boundary with Pydantic. Rate limits on AI endpoints. Signed URLs for photos.
10. **Observability.** Structured JSON logs, request ids, Sentry (or OpenTelemetry) hooks behind config, health endpoints, sync-failure metrics visible to the user.

---

## 1. Product summary

BagMitra is a bahar-based (flowering-cycle-based) orchard management app for Indian fruit growers — first crop **Nagpur mandarin (santra) and mosambi**, architecture generic so pomegranate, grape, mango, banana can be added as configuration. It is the grower's side: record keeping, bahar planning, task and spray scheduling, costs and profit per bahar, market prices, weather-based disease-risk alerts, AI photo diagnosis and Marathi voice assistant, government scheme guidance, and (later) IoT sensor nodes in the orchard. It does **not** sell inputs — independence from input sellers is the trust proposition.

Primary users: growers in Vidarbha (Nagpur, Amravati, Warud, Katol, Morshi, Kalmeshwar belt), mostly Android phones ₹8–15k, intermittent 2G/3G/4G, Marathi speakers, varying literacy — **voice and icons matter**. Secondary (paying B2B) users: agri consultants, Krishi Seva Kendra owners, FPOs managing 50–500 growers.

---

## 2. Tech stack (decided — do not change without an ADR and a logged question)

**Mobile/web app:** Flutter (Dart, stable channel), Android first, iOS and PWA from the same code.
- State: Riverpod. Routing: go_router. Local DB: Drift (SQLite) with a sync layer (outbox pattern: every local write queued; background sync with exponential backoff; conflict rule = server wins for reference data, last-writer-wins with audit for user data; photos uploaded after metadata).
- Images: in-app camera via `camera` package; compress to max 1000 px long edge, JPEG quality ~75 (target 120–200 KB) before upload; original stays on device only if user enables it. Photos carry plot id, tree id (optional), GPS, timestamp, growth stage.
- Low-data mode: text-first screens, thumbnails only, no autoplay media, delta sync, gzip. App size target < 25 MB download.
- i18n: `flutter_localizations` + ARB files; source `en`. **Target: all major Indian languages** — launch set `mr`, `hi`, `en`; **second wave (soon after launch, plan for it in M1 already): South Indian languages `te` (Telugu), `kn` (Kannada), `ta` (Tamil), `ml` (Malayalam)** — major citrus/mango/banana/pomegranate growing states; then `gu`, `bn`, `pa`, `or`, `as` (and more as config). Every UI string, notification template, agronomy content item and AI output must be language-keyed from day one; no language may require a code change to add. Fonts for Devanagari, Gujarati, Telugu, Kannada, Tamil, Malayalam, Bengali, Gurmukhi, Odia bundled or downloaded on demand (to keep APK small). Translation workflow: English source → machine draft (Claude) → human review flag per string; untranslated strings fall back to English, never blank. Numbers/dates in Indian format per locale. STT/TTS provider adapter must support the same language list (Bhashini covers 22 scheduled languages).
- Accessibility: large tap targets, voice readout of alerts (TTS), icon + text labels everywhere.

**Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + Alembic migrations, Postgres on Supabase with PostGIS for plot polygons. Supabase Auth (phone OTP primary, Google optional). Supabase Storage for photos (private buckets, signed URLs). Background jobs: ARQ or Celery on Redis (weather pulls, risk evaluation, notifications, AI batch). Docker Compose for local dev; GitHub Actions CI; deploy to the owner's VPS via Docker.

**AI:** Claude API through one `ai/` service module behind an interface.
- Photo diagnosis: two-stage — Haiku first (image quality check, healthy/unclear/obvious cases); escalate to Sonnet only when Haiku flags a possible problem or low confidence. Structured JSON output: {quality_ok, crop_part, observations[], suspected_issues[{name, confidence}], severity, recommended_actions[] (non-commercial: cultural, biological, generic active-ingredient level only), when_to_consult_expert, follow_up_photo_request}. Prompt templates in DB, versioned. Prompt caching for the system/knowledge prefix. Batch API for non-urgent nightly jobs.
- Voice assistant: Marathi/Hindi speech-to-text and text-to-speech via a provider adapter (Bhashini / Sarvam / Google — pick one, keep adapter swappable); Claude answers using the grower's own orchard context (plots, stage, recent weather, recent photos) — always grounded, cites which record it used.
- Per-user daily AI cost caps (configurable), cost logged per call.

**Messaging:** WhatsApp Business API (primary), SMS fallback (DLT-registered templates), FCM push. All templates in DB per language.

**Weather:** provider adapter (Open-Meteo first; IMD/Tomorrow.io optional) — hourly forecast and observed data per plot centroid; stored history for risk models.

**Market prices:** Agmarknet scraper/API adapter for Kalamna, Warud, Katol, Morshi, Amravati APMCs + community-reported prices with moderation.

**IoT (Milestone 7, design now):** MQTT broker (EMQX/Mosquitto) ingestion → time-series table (TimescaleDB extension if available, else partitioned Postgres) → same risk engine. Device registry, provisioning tokens, heartbeat, battery/solar telemetry. Firmware is a separate repo later.

---

## 3. Domain model (minimum)

- `farmers` (profile, language, village, taluka, district, phone, consent flags)
- `orchards` / `plots` (polygon or point + area, crop, variety, planting year, tree count, spacing, irrigation type, water source, soil type)
- `trees` (optional per-tree records for sampled/flagged trees; QR tag id)
- `bahar_cycles` (plot, bahar type ambiya/mrig/hasta, season year, planned dates: stress start, irrigation restart, flowering, fruit set, harvest; actual dates; status)
- `crop_stage_templates` (per crop/variety/bahar: ordered stages with expected day offsets, GDD-based adjustment hooks, tasks per stage) — config, admin-editable
- `tasks` (plot, bahar, stage, type, due date, done date, notes, reminders)
- `spray_records` (date, product name, active ingredient, dose, water volume, area, cost, operator, PHI days, target pest/disease; MRL/PHI warnings computed)
- `input_records` (fertiliser/manure/micronutrients), `irrigation_records`
- `labour_register` (worker, date, task, wage, advance, settlement), `expenses`, `incomes` (buyer, grade, quantity, rate, deductions, payment status/date)
- `harvests` (date, grade-wise quantity, size distribution)
- `photos` (storage key, plot/tree, stage, gps, taken_at, ai_review id)
- `ai_reviews`, `ai_usage`
- `weather_observations`, `weather_forecasts` (per plot centroid)
- `risk_rules` (config: disease/pest, crop, conditions over weather/stage windows, output level, advice template) and `risk_events`
- `alerts` / `notifications` (channel, template, status, delivered_at)
- `market_prices` (market, commodity, grade/size, min/modal/max, date, source)
- `buyers` and `credit_ledger` (dues from traders)
- `schemes` (config: name, eligibility rules, documents, deadlines, links) and `farmer_scheme_status`
- `consultants`, `consultant_grants` (farmer → consultant access), `groups` (village/taluka communities)
- `devices`, `device_readings`, `device_health`
- `plans`, `subscriptions`, `payments` (Razorpay)

All tables tenant-scoped by farmer (and by consultant grants) with RLS.

---

## 4. Features by milestone

**M0 — Foundation (DoD: CI green on empty app + API, emulator smoke test, docs).**
Repo layout (`app/`, `api/`, `infra/`, `docs/`), CI pipelines (lint, type, test, coverage gates, OpenAPI → Dart client generation, APK build artifact), Supabase project schema + RLS skeleton, auth (phone OTP), i18n plumbing with `mr/hi/en`, Drift + outbox sync skeleton with tests, design system (large type, icons, offline banner), admin UI skeleton (web, same Flutter codebase or simple React — choose and record ADR).

**M1 — Orchard & bahar core.**
Farmer onboarding (voice-guided), plots (draw/walk boundary with GPS or enter area), bahar cycle creation with stage calendar from templates (santra: ambiya, mrig, hasta), bahar selection assistant (compare bahars by water availability, last bahar, market timing — rule-based, config), task list and reminders (push/WhatsApp/SMS), offline everything. Seed santra/mosambi stage templates from published MSKVV/ICAR-CCRI recommendations with source citations in `docs/agronomy/`.

**M2 — Records & accounts.**
Spray, input, irrigation, labour, expense, income, harvest records with fast entry (voice note → transcribed fields, confirm). PHI/MRL warning: block-list check before harvest date. Cost per acre / per tree / per tonne, profit per bahar, year-over-year comparison, dues from buyers, exports (PDF/Excel in Marathi).

**M3 — Photos & AI.**
In-app camera, compression, offline queue, gallery by plot/stage. Two-stage Claude photo diagnosis with structured output, confidence display, "consult expert" path, follow-up photo prompts. Voice assistant (Marathi/Hindi) grounded in the grower's records. Cost caps and usage dashboard in admin.

**M4 — Weather & risk alerts.**
Per-plot weather pulls, history storage. Rule-based risk engine (configurable rules) for heat-wave fruit drop risk, prolonged leaf wetness/humidity → canker/fungal risk, psylla favourable windows, hail/heavy rain warnings, irrigation advisory ("water today?" from soil type + ET0 + rainfall + stage). Alerts via WhatsApp/SMS/push with action advice in the grower's language, plus a daily morning brief. AI used only to phrase and personalise the alert, never to decide the trigger.

**M5 — Market, schemes, community.**
APMC daily prices with size/grade, trend chart, harvest-sell planner ("if harvested this week, estimated ₹"), buyer records and credit ledger. Schemes directory with eligibility checklist and deadline reminders (fruit orchard plantation scheme, drip subsidy, farm pond, crop insurance, AgriStack Farmer ID). Village/taluka groups: price reports, trader experiences, labour/machinery sharing (moderated).

**M6 — Consultant/FPO mode & billing.**
Consultant dashboard: roster of growers, each plot's stage, risk alerts, photos needing review, broadcast advisories; comment on records. Grower grants/revokes access. Plans: Free (records + accounts, limited photos), Grower Pro (calendar, alerts, AI, voice), Consultant (per 100 growers). Razorpay subscriptions + webhooks; prices configurable. Traceability report: spray history → QR for exporters/processors.

**M7 — IoT ingestion.**
MQTT ingestion API, device registry/provisioning, readings pipeline into the same risk engine (soil moisture at two depths, air temp/RH, leaf wetness, rainfall, battery/solar), device health alerts, per-plot sensor charts, irrigation advisory upgraded to sensor-based. Camera add-on (gateway camera, smart sticky-trap counts) designed as optional ingestion types. Firmware/hardware BOM delivered as a separate spec later.

**M8 — Hardening & launch.**
Performance on low-end devices (profile on 2 GB RAM emulator), app size, battery, data usage audit, accessibility pass, Play Store listing assets, privacy policy, data export/delete (DPDP compliance), load tests, backup/restore, runbooks.

---

## 4A. UI / visual design — must be attractive, catchy and distinctive (owner's explicit requirement)

The app must look and feel premium and joyful — growers should *want* to open it every morning — while staying fast on a ₹8k Android phone. Design is a deliverable, not polish at the end.

**Design direction**
- A real brand, not Material defaults: custom colour system rooted in the orchard — deep leaf green, santra orange as the accent, warm earth/soil browns, sky blue for weather, cream background (not pure white). Dark mode supported. Define all tokens in one `theme/` module (colours, spacing, radii, type scale, elevation); no inline colours anywhere (lint rule).
- Typography: a distinctive Devanagari + Latin pairing with excellent legibility at large sizes (e.g. Mukta / Baloo 2 for Devanagari with a matching Latin face; evaluate and record in an ADR); minimum body 16 sp, big numerals for money and dates.
- Illustration system: a consistent set of flat, friendly illustrations and icons for crops, bahar stages, weather, pests, tasks (SVG, tinted from the theme). Empty states, onboarding and success screens use them. Growth stages shown as an illustrated timeline of the tree (bud → flower → fruit set → harvest), not a text list.
- Home screen = "today's orchard": weather strip, bahar stage card with illustration and day count, today's tasks, risk alert (if any), market price ticker, one big camera button. Everything important visible without scrolling on a 5.5" screen.
- Micro-interactions: light, purposeful motion only (task tick, sync success, alert pulse) using Flutter implicit animations; respect reduced-motion; no heavy Lottie/video on low-end devices (gate by device class).
- Data display: money, yield and cost charts in the brand palette with clear labels; "profit per bahar" as a hero number.
- Voice-first affordances: a prominent microphone button on every entry screen; big camera button; icon + text on every action.
- Accessibility and low-literacy: 48 dp tap targets, high contrast, numbers read aloud on demand, pictograms for tasks.
- Performance budget per screen: first frame < 1 s on a 2 GB RAM device, 60 fps scrolling; measured in CI with Flutter integration tests and recorded in PROGRESS.md.

**Bar for "attractive"** — the owner's words: *dashing and attractive*. Concretely: a grower showing the app to a neighbour should get "कुठून घेतलं?" ("where did you get this?"). Reference quality: top-tier Indian consumer fintech/health apps (CRED, Groww, Cult.fit level polish) adapted to a rural, warm, orchard aesthetic — generous whitespace, strong hierarchy, one hero number or image per card, gradient accents used sparingly, rounded 16–20 dp cards with soft shadows, bold section headers, illustrated empty/success states, delightful but light motion. Not: default Material widgets, grey tables, dense forms, stock icons.

**Process**
- A reference mockup of the Home screen is provided by the owner: `docs/design/reference/home_mockup.html` + `home_mockup.png` (copy both files from the owner into the repo at the start of M0). Tokens used there: leaf #1F4D2B / #2E6B3C, leaf-light #9BC79A, santra #F28C28 / #FFB15C, sun #FFC857, soil #6B4A2B, sky #CFE8F3, background #F3F7EE, ink #1B2A1E; fonts Baloo 2 (display) + Mukta (body). Treat these as the starting design tokens; match its direction, extend it to all screens, and never ship a screen that is visibly less polished than the reference.
- Every UI PR must attach emulator screenshots (light + dark, Marathi) in the PR description; the self-review must answer "would a grower show this to a neighbour?" honestly.
- Before M1 UI work, produce a design system document (`docs/design/DESIGN_SYSTEM.md`) with tokens, components (buttons, cards, chips, inputs, alert banners, stage timeline, photo tiles, price ticker) and screenshots of a component gallery screen built in the app; keep that gallery screen in the app behind a dev flag.
- Each milestone's screens get a golden-test (widget screenshot) suite so visual regressions fail CI.
- Design review checklist in every UI PR: tokens only, Marathi strings fit without overflow, works offline, works in dark mode, 2 GB device profile passes.

## 5. Agronomy content rules
- All crop/disease/bahar content must be sourced (ICAR-CCRI Nagpur, MSKVV/PDKV Akola, state agriculture department, peer-reviewed) and cited in `docs/agronomy/`. No invented thresholds. Where sources differ, store both and let admin choose; log a question.
- Recommendations at the level of practice and generic active ingredient; never brand names, never "buy from".
- Every recommendation shown to a grower carries a "verify with local expert" line for chemical actions.

## 6. Documentation to maintain
`docs/PLAN.md`, `docs/PROGRESS.md`, `docs/OPEN_QUESTIONS.md`, `docs/adr/`, `docs/agronomy/`, `docs/api/` (generated), `docs/runbooks/`, `README.md` with one-command local setup.

Begin now: create the repo structure, write `docs/PLAN.md`, then Milestone 0. Do not wait for approval between steps.
