# Progress

## M0 — Foundation · 2026-10-12

### Delivered
- **API** (`api/`): settings from env + `product.env`, JSON logs with request ids, uniform error
  envelope, `/health/live`, `/health/ready`, Supabase JWT verification, `GET /v1/me`,
  `POST /v1/sync/push` / `GET /v1/sync/pull` (idempotent, last-writer-wins, full audit log),
  OpenAPI export, Sentry hook behind `SENTRY_DSN`, Dockerfile.
- **DB:** `farmers`, `sync_mutations`; Alembic 0001 with owner-only RLS (ENABLE + FORCE).
- **App** (`app/`): Riverpod + go_router; theme tokens from the reference mockup (light + dark);
  Baloo 2 + Mukta bundled; i18n `en` / `mr` / `hi`; Drift DB + outbox + sync engine (batching,
  backoff with jitter, offline/signed-out states, pull cursor); generated API client; HTTP sync
  transport; phone-OTP login (Supabase adapter + demo mode); Home "today's orchard" built from
  design-system components; painted glyph illustration set; component gallery behind
  `DEV_GALLERY`; admin web shell (`lib/main_admin.dart`).
- **CI:** `.github/workflows/bagmitra-api.yml` (ruff, format, mypy strict, bandit, pytest ≥ 85%,
  OpenAPI drift, Postgres migration + RLS job), `.github/workflows/bagmitra-app.yml` (codegen drift,
  format, analyze `--fatal-infos`, tests incl. goldens, logic coverage ≥ 80%, release APK artifact).
- **Docs:** PLAN, ADRs 0001–0007, DESIGN_SYSTEM (with screenshots), OPEN_QUESTIONS, runbook.

### DoD checklist (verified in the build session)
| Item | Result |
|---|---|
| ruff / ruff format / mypy --strict / bandit | clean |
| pytest | 30 passed, 1 Postgres-only; coverage **95.9%** (gate 85%) |
| Postgres: upgrade → downgrade → upgrade, RLS on every table, cross-user read/insert blocked | passed (postgis/postgis:16-3.4) |
| API smoke on Postgres: migrate, push profile, `GET /v1/me` (Marathi), JSON access logs | passed |
| dart format / flutter analyze | zero issues |
| flutter test | 55 passed (unit, widget, offline→online sync, l10n completeness, no-inline-colours, goldens) |
| App logic coverage | **91.2%** (gate 80%) |
| Goldens | Home mr light/dark, hi, en, offline banner; login; gallery |
| `flutter build web` (app + admin) | passed |
| OpenAPI exported, Dart client generated | yes; CI checks drift |
| APK build | CI job (no Android SDK in the build container) |
| Emulator demo checklist | **not run** — no KVM/Android SDK in the cloud container (OPEN_QUESTIONS Q4) |
| `make dev` (Docker compose) | **not verified** — Docker Hub returned 429 for `python:3.12-slim`; the same steps passed without Docker (above) |

### Demo checklist (run on an emulator when one is available)
1. Fresh install → login screen in device language (Marathi device → Marathi).
2. Invalid number shows error; valid number → OTP screen; wrong OTP error; correct OTP → Home.
3. Home: weather header, stage card with day count in Devanagari digits, alert, tasks, price.
4. Tick a task → animated check; dark mode via system setting.
5. Airplane mode → offline banner; edits queue; network back → banner clears.

### Known gaps carried into M1
Home slightly exceeds one 5.5" screen (Q7); mic not wired until STT (Q5); performance budget
measurement on a 2 GB device profile not yet automated.
