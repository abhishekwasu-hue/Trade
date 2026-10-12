# ADR 0006 — Admin UI

Status: Accepted · 2026-10-12

The admin is a second Flutter entrypoint (`lib/main_admin.dart`) built for web from the same
codebase: shared theme tokens, l10n and generated API client, one toolchain, one CI. A separate
React app would duplicate all three. Admin screens are table/form-heavy and desktop-only, which
Flutter web handles adequately; if it becomes a bottleneck, the API contract makes swapping it
cheap. Admin endpoints will require an `admin` role claim (M1).
