# BagMitra — Delivery Plan

Source of truth for requirements: [`SPEC_v1.md`](SPEC_v1.md). This plan maps every spec
section to concrete files and milestones. Each milestone has a Definition of Done (DoD)
that must be met before the next one starts. Progress is tracked in
[`PROGRESS.md`](PROGRESS.md); unresolved points live in
[`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) with a provisional default.

The product name is configurable in one place: [`../product.env`](../product.env)
(`PRODUCT_NAME`, `PRODUCT_SLUG`). The API reads it through settings; the app receives it
via `--dart-define-from-file=product.env`.

## Repository layout

```
bagmitra/
  product.env              # product name / slug (single place)
  api/                     # FastAPI backend (Python 3.12)
    src/bagmitra_api/
      core/                # settings, logging, request ids, errors
      auth/                # Supabase JWT verification, current-user dependency
      db/                  # SQLAlchemy base, session, models
      routers/             # health, me, sync, (later: plots, bahars, ...)
      sync/                # outbox ingestion: idempotency, LWW + audit
      ai/                  # (M3) Claude service behind an interface
      weather/, market/, messaging/, risk/   # (M4–M5) provider adapters
    alembic/               # migrations (reversible, RLS policies included)
    tests/
  app/                     # Flutter app (Android first, iOS + PWA) + admin web entrypoint
    lib/
      theme/               # ALL design tokens (colours, spacing, radii, type, elevation)
      l10n/                # ARB files (en source; mr, hi launch; te, kn, ta, ml wave 2)
      core/                # config, connectivity, result types
      data/local/          # Drift database, tables, DAOs
      sync/                # outbox engine, backoff, transport interface
      features/<feature>/  # presentation + domain per feature
      design_system/       # reusable widgets (cards, chips, banners, timeline, ...)
      admin/               # admin web shell (main_admin.dart)
    test/                  # unit, widget, golden tests
    integration_test/      # offline -> online sync, perf budget
  infra/                   # docker-compose, Supabase SQL helpers, deployment notes
  docs/                    # PLAN, PROGRESS, OPEN_QUESTIONS, adr/, agronomy/, api/, runbooks/, design/
```

CI lives at the repository root: `.github/workflows/bagmitra-api.yml` and
`.github/workflows/bagmitra-app.yml` (path-filtered to `bagmitra/**`).

## Spec → files map

| Spec § | Topic | Where |
|---|---|---|
| 0.1 | Test-first, coverage gates | `api/pyproject.toml` (`--cov-fail-under=85`), `app/tool/coverage_gate.dart` (≥80% on `lib/core`, `lib/data`, `lib/sync`, `features/*/domain`) |
| 0.2 | Strict typing & linting | `api/pyproject.toml` (mypy strict, ruff, bandit), `app/analysis_options.yaml` |
| 0.3 | Contract-first API | `api/src/bagmitra_api/export_openapi.py` → `docs/api/openapi.json`; `app/openapi/` + `swagger_dart_code_generator` → `app/lib/api/generated/`; CI fails on drift |
| 0.4 | Small PRs + self-review | `.github/pull_request_template.md` |
| 0.5 | No hardcoded business values | DB config tables (`crop_stage_templates`, `risk_rules`, `app_config`, ...) + admin UI; lint test `app/test/architecture/` |
| 0.6 | Offline-first | `app/lib/data/local`, `app/lib/sync`, `api/src/bagmitra_api/sync`; `app/test/sync/offline_online_test.dart` |
| 0.7 | DoD per milestone | this file; `PROGRESS.md` |
| 0.8 | Continuous work | `OPEN_QUESTIONS.md` |
| 0.9 | Security | Alembic RLS policies, `.env.example`, Pydantic validation, rate limits (M3), signed URLs (M3) |
| 0.10 | Observability | `api/src/bagmitra_api/core/logging.py`, request-id middleware, `/health/*`, Sentry hook behind `SENTRY_DSN`; app sync status banner |
| 2 | Stack | ADRs 0001–0006 |
| 2 i18n | Languages | `app/l10n.yaml`, `app/lib/l10n/*.arb`, `docs/adr/0004-i18n.md` |
| 3 | Domain model | `api/src/bagmitra_api/db/models/`, migrations per milestone |
| 4 | Features | milestones below |
| 4A | Visual design | `app/lib/theme/`, `app/lib/design_system/`, `docs/design/DESIGN_SYSTEM.md`, golden tests |
| 5 | Agronomy content | `docs/agronomy/` (citations), seed data in migrations with `source` column |
| 6 | Documentation | `docs/*`, `README.md` |

## Milestones

### M0 — Foundation

Scope:
1. Repo layout, `product.env`, README with one-command local setup (`make dev`).
2. API skeleton: settings, JSON logs with request ids, error envelope, `/health/live`,
   `/health/ready`, Supabase JWT verification, `GET/PUT /v1/me` (farmer profile),
   `POST /v1/sync/push` + `GET /v1/sync/pull` (generic outbox ingestion with idempotency,
   last-writer-wins + audit), OpenAPI export.
3. DB: SQLAlchemy models `farmers`, `sync_mutations`; Alembic migration 0001 with RLS
   (owner-only) on every table; CI migration job against Postgres (upgrade → downgrade → upgrade).
4. App skeleton: Riverpod, go_router, theme tokens from the reference mockup (light + dark),
   bundled Baloo 2 + Mukta, i18n plumbing (`en` source, `mr`, `hi`), Drift DB + outbox +
   sync engine with exponential backoff, offline/sync banner, phone-OTP login flow behind an
   `AuthRepository` interface, Home screen ("today's orchard") built from design-system widgets
   with demo fixture data, component gallery behind `DEV_GALLERY`, admin web shell.
5. CI: lint, format, type, test, coverage gates, OpenAPI drift + Dart client generation,
   golden tests, APK build artifact.
6. Docs: ADRs, DESIGN_SYSTEM.md (initial), runbook for local dev.

DoD:
- [ ] `ruff`, `ruff format --check`, `mypy --strict`, `bandit`, `pytest` (≥85%) green.
- [ ] `dart format`, `dart analyze` (zero issues), `flutter test` green, logic coverage ≥80%.
- [ ] Golden tests for Home (mr, light + dark) committed and passing.
- [ ] Migration reversible against Postgres in CI; RLS enabled on every table.
- [ ] OpenAPI exported and Dart client generated with no drift.
- [ ] APK artifact built in CI.
- [ ] Demo checklist executed and recorded in `PROGRESS.md` (emulator, or documented substitute).
- [ ] ADRs written for every architectural choice.

### M1 — Orchard & bahar core

Files: `api/.../models/{plots,trees,bahar_cycles,crop_stage_templates,tasks}.py`, routers,
seed migration from `docs/agronomy/santra_*.md`; app `features/onboarding`, `features/plots`
(GPS walk/draw, area entry), `features/bahar` (cycle creation, stage calendar, bahar
selection assistant — rule config), `features/tasks` (+ reminders via push; WhatsApp/SMS adapters
stubbed behind interface). Wave-2 locales (`te`, `kn`, `ta`, `ml`) added as ARB + font-on-demand.
DoD: all writes offline + synced (integration test), goldens for each screen, design system doc
with gallery screenshots completed before UI work, agronomy citations reviewed.

### M2 — Records & accounts

Spray/input/irrigation/labour/expense/income/harvest records, voice-note quick entry, PHI/MRL
check, cost & profit per bahar, YoY, buyer dues, PDF/Excel export (Marathi fonts embedded).
DoD: calculations unit-tested with fixtures, exports golden-tested, offline entry tested.

### M3 — Photos & AI

Camera + compression (≤1000 px, q≈75), offline photo queue (metadata first, then bytes),
gallery; `api/.../ai/` two-stage Haiku → Sonnet diagnosis, prompt templates in DB (versioned),
prompt caching, Batch API for nightly jobs, per-user cost caps and `ai_usage`; voice assistant
via STT/TTS adapter, grounded answers with citations of records; admin usage dashboard;
rate limits on AI endpoints; signed photo URLs.
DoD: AI service tested with recorded fixtures (no live calls in CI), cost caps enforced.

### M4 — Weather & risk alerts

Open-Meteo adapter, per-plot pulls (ARQ jobs), history; configurable risk engine; alert
delivery (WhatsApp/SMS/push) with templates per language; morning brief; irrigation advisory.
DoD: rule engine property-tested; no rule constants in code.

### M5 — Market, schemes, community

Agmarknet adapter + community prices with moderation, trend chart, harvest-sell planner,
buyers & credit ledger, schemes directory with eligibility checklist, groups.

### M6 — Consultant/FPO mode & billing

Grants, consultant dashboard, broadcasts, comments, plans & Razorpay subscriptions/webhooks,
traceability QR report.

### M7 — IoT ingestion

MQTT → ingestion API → time-series table → risk engine; device registry/provisioning,
health alerts, sensor charts, sensor-based irrigation advisory.

### M8 — Hardening & launch

Low-end device profiling, size/battery/data audits, accessibility pass, store assets,
privacy policy, DPDP export/delete, load tests, backups, runbooks.
