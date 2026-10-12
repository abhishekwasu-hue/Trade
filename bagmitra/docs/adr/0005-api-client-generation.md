# ADR 0005 — Contract-first Dart client

Status: Accepted · 2026-10-12

FastAPI generates the OpenAPI schema; `python -m bagmitra_api.export_openapi` writes
`docs/api/openapi.json` (stable `operation_id`s). The app keeps a copy in `app/openapi/` and
generates its client with `swagger_dart_code_generator` + `chopper` via `build_runner` (pure
Dart; no Java toolchain needed in CI, unlike `openapi-generator`).

CI enforces: API test compares committed spec with the code; app CI diffs the copy against
`docs/api/openapi.json` and regenerates the client, failing on any diff. Hand-written
request/response models are not used; app code maps generated models into domain types at the
transport edge (`sync/http_transport.dart`).
