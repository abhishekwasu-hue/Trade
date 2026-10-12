# One-command local setup: `make dev` (API + Postgres in Docker), then `make app`.
.PHONY: dev down api-check app app-check openapi

dev:
	docker compose -f infra/docker-compose.yml up --build -d
	@echo "API: http://localhost:8000/docs"

down:
	docker compose -f infra/docker-compose.yml down

api-check:
	cd api && ruff check . && ruff format --check . && mypy src tests alembic && bandit -q -c pyproject.toml -r src && pytest

openapi:
	cd api && python -m bagmitra_api.export_openapi && cp ../docs/api/openapi.json ../app/openapi/bagmitra.openapi.json
	cd app && dart run build_runner build --delete-conflicting-outputs && dart format lib > /dev/null

app:
	cd app && flutter run --dart-define-from-file=../product.env --dart-define=API_BASE_URL=http://10.0.2.2:8000

app-check:
	cd app && dart format --output=none --set-exit-if-changed lib test tool && flutter analyze --fatal-infos && flutter test --coverage && dart run tool/coverage_gate.dart 80
