# ADR 0003 — Offline-first sync protocol

Status: Accepted · 2026-10-12

## Decision
**Client (Drift):** every user write happens in one transaction with an `outbox_entries` row
(id = UUID v4 = idempotency key, entity, entity_id, op, JSON payload, `client_updated_at`).
`SyncEngine` pushes due entries in batches (default 50), oldest first, then pulls.
- Network failure / timeout / 5xx → entries stay, `attempts++`, `next_attempt_at` set by
  exponential backoff with full jitter (base 5 s, cap 30 min). Status → offline banner.
- 401/403 → stop, status `signedOut`.
- Result `applied` / `duplicate` → entry deleted. `stale` → deleted; the server's newer row
  arrives on the next pull. `rejected` → kept with its error and shown to the user (never silent).
- Pull uses a server cursor; a pulled change is skipped while the same entity has a pending
  local entry (that write is pushed first and the server decides).

**Server:** `POST /v1/sync/push` evaluates each mutation independently: idempotent on
`(owner_id, client_mutation_id)`, validates the payload against the entity's Pydantic schema,
last-writer-wins on `client_updated_at`. Every mutation — applied, stale or rejected — is stored in
`sync_mutations` (audit log). Its autoincrement `seq` is the global pull cursor; synced tables
store `last_seq`. `GET /v1/sync/pull?since=` returns rows with `last_seq > since`.
Entities register a handler in `sync/registry.py`; reference data (server-wins) will be pull-only
entities.

## Consequences
Adding a synced entity = one handler + one Drift table + one applier. Photos (M3) upload after
their metadata mutation is applied.
