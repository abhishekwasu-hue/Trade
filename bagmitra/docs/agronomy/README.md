# Agronomy content

Rules (spec §5): every crop, stage, disease or bahar fact used by the app is sourced (ICAR-CCRI
Nagpur, MSKVV/PDKV Akola, state agriculture department, peer-reviewed work) and cited here, one
file per topic (e.g. `santra_mrig_bahar.md`), before it is seeded into config tables. Where
sources differ, both values are stored and the admin chooses; the conflict is logged in
`../OPEN_QUESTIONS.md`. Recommendations stay at practice / generic active-ingredient level and
chemical actions carry a "verify with local expert" line.

M0 contains no agronomy data. The Home screen's sample content (`app/assets/demo/home_demo.json`)
is illustrative only, labelled "Sample data" in the UI, and not used by any logic. Seeding the
santra/mosambi stage templates with citations is the first M1 task.
