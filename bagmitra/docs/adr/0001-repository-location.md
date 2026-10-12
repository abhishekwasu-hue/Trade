# ADR 0001 — Repository location

Status: Accepted (provisional) · 2026-10-12

## Context
The spec asks for a new `bagmitra` repository. The working session only had access to the
existing `trade` repository; creating a new GitHub repository is an outward-facing action the
owner should take.

## Decision
Build BagMitra as a fully self-contained subdirectory `bagmitra/` of the current repository.
Nothing in it imports from or depends on the trading code. CI workflows are path-filtered to
`bagmitra/**`, and the only files outside it are those two workflows and a PR template.

## Consequences
Moving out is mechanical and keeps history:
`git subtree split --prefix=bagmitra -b bagmitra-main` → push to the new repo → move
`.github/workflows/bagmitra-*.yml` (drop the `bagmitra/` prefix in paths and `working-directory`).
Tracked in OPEN_QUESTIONS Q1.
