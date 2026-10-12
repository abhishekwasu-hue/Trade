# ADR 0002 — Backend auth and row-level security

Status: Accepted · 2026-10-12

## Decision
- The app signs in with Supabase Auth (phone OTP). The API verifies the Supabase access token
  (HS256, audience `authenticated`, `exp`/`sub` required) with `SUPABASE_JWT_SECRET`.
  Verification lives in `api/src/bagmitra_api/auth/jwt.py`; switching to asymmetric JWKS keys
  is a local change there.
- The API connects to Postgres with a privileged role and enforces ownership in code
  (every handler scopes by `user.id`).
- RLS is defence in depth: every table gets `ENABLE` + `FORCE ROW LEVEL SECURITY` and an
  owner-only policy (`owner_column = auth.uid()`), created in the same Alembic migration as the
  table. Every model declares `owner_column`; a test fails if one is missing, and the Postgres CI
  job fails if any table lacks RLS and proves a second user cannot read or insert another
  farmer's row. Consultant access (M6) will add grant-based policies.
- Plain Postgres (CI, local docker) has no `auth` schema, so the migration creates a compatible
  `auth.uid()` *only if none exists* — Supabase's own function is never replaced.

## Consequences
Two walls: a bug in API scoping is still blocked for direct client access, and RLS gaps are CI
failures, not review comments.
