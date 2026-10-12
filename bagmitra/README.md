# BagMitra

Bahar-based orchard management for Indian fruit growers — Nagpur santra and mosambi first.
Offline-first Flutter app (Marathi · Hindi · English), FastAPI backend on Supabase Postgres.
The product name is configured in one place: [`product.env`](product.env).

```bash
make dev        # API + Postgres (Docker) on http://localhost:8000/docs
make api-check  # lint, types, security, tests (≥85%)
make app-check  # format, analyze, tests + goldens, logic coverage (≥80%)
make app        # run the app (demo mode unless SUPABASE_URL/ANON_KEY are passed)
```

| | |
|---|---|
| Spec | [docs/SPEC_v1.md](docs/SPEC_v1.md) |
| Plan & milestones | [docs/PLAN.md](docs/PLAN.md) |
| Progress | [docs/PROGRESS.md](docs/PROGRESS.md) |
| Open questions | [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) |
| Decisions | [docs/adr/](docs/adr/) |
| Design system | [docs/design/DESIGN_SYSTEM.md](docs/design/DESIGN_SYSTEM.md) |
| API contract | [docs/api/openapi.json](docs/api/openapi.json) |
| Local setup | [docs/runbooks/local-dev.md](docs/runbooks/local-dev.md) |

Layout: `api/` backend · `app/` Flutter app + admin web · `infra/` docker compose · `docs/`.
