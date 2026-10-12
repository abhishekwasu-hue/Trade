<!-- BagMitra PRs: open with ?template=bagmitra.md. One feature per PR, ≤ 400 production lines. -->

## What & why

## Offline behaviour
<!-- How does this behave with no network? What is queued, what syncs later? -->

## Screenshots (UI PRs: light + dark, Marathi)

## Self-review checklist
- [ ] Correctness: tests written first and cover the change
- [ ] Offline behaviour described above and tested
- [ ] Error handling: failures are visible to the user, never silent
- [ ] Marathi (and Hindi) strings present; no overflow
- [ ] Tests added; coverage did not drop
- [ ] Migration reversible (upgrade → downgrade → upgrade)
- [ ] No hardcoded business values (stages, thresholds, prices, templates live in config)
- [ ] Design tokens only; works in dark mode; would a grower show this to a neighbour?
