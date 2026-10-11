#!/usr/bin/env python3
"""🗓 PAPER दिवस-सारांश (Abhi §10e, 15:45 IST): approvals, ✏️ modifications, ❌ rejections (कारणानुसार), 📝 corrections, approved trades
चा net P&L वि. would-have नोंदी ⇒ Telegram. फक्त वाचन (vision.db + paper journal) — order / settings ला हात नाही. Dry-run नोंदी वगळून.

VPS cron (VPS ची वेळ UTC ⇒ 15:45 IST = 10:15 UTC; crontab या script मधून बदलत नाही — Abhi स्वतः जोडतो):
  15 10 * * 1-5  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_daily_summary.py >> paper_daily_summary.log 2>&1
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main(argv=None, send=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None, help="YYYY-MM-DD (default: आज, IST)")
    ap.add_argument("--print", dest="print_only", action="store_true", help="Telegram नाही, फक्त छाप")
    a = ap.parse_args(argv)
    from vision import approval as AP
    text = AP.daily_summary_text(a.day)
    print(text)
    if a.print_only:
        return 0
    if send is None:
        from notifications import send_telegram_message as send
    try:
        send(text)
    except Exception as exc:
        print(f"⚠️ सारांश Telegram वर गेला नाही: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
