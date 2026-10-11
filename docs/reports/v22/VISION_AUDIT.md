# v2.2 Vision audit — daily summary

Vision judges placement only; disagreements are evidence for Abhi's review, never auto-changes. Engine numbers from data — no order.
Each Telegram send of v2.2 charts (scripts/send_review_to_telegram.py, VPS) appends one block per day — charts audited, agree / partly / disagree,
top recurring issues, spend — to **trade-data** `review/v22/VISION_AUDIT.md` (default `--audit-summary`), not to this file: a tracked file changed
on the VPS checkout would stop the deploy clean-tree check. Per-chart audit JSON: `<png>.vision.json` beside each chart in trade-data.
Budget: chart audits keep the signals reserve (`signals_daily_reserve_usd` per day, and × remaining weekdays of the month) — same rule as
run_visual_audit.
