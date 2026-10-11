"""scripts/send_review_to_telegram.py — review charts (K-10 / Golden Gallery / backtest visual review) Telegram वर, फक्त VPS वरून.

    python3 scripts/send_review_to_telegram.py --run review/k10/run1 [--data-dir /root/trade-data] [--no-pull] [--dry-run] [--vision-audit auto|off]

v2.2 items (kind "v22…"): chart → Vision audit (decision3/vision_audit.py, daily budget hard stop) → Telegram (caption मध्ये audit ओळ,
"Vision report" reply); audit JSON PNG शेजारी; दैनिक सारांश docs/reports/v22/VISION_AUDIT.md.

trade-data pull ⇒ <data-dir>/<run>/manifest.json ⇒ न पाठवलेले items (sent log, data/review_tg_sent.json) ⇒ media group + caption.
Approve बटण नाही; replies (✔ / ✘ / सुटलेला trade) vision/telegram_bot listener backtest_review मध्ये नोंदवतो. Token कधीच print नाही.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main(argv=None):
    from backtest_review import telegram as RT
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="trade-data मधला run folder, उदा. review/k10/run1")
    ap.add_argument("--data-dir", default=os.environ.get("TRADE_DATA_DIR", "/root/trade-data"))
    ap.add_argument("--no-pull", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pause", type=float, default=3.0, help="संदेशांमध्ये विराम (sec)")
    ap.add_argument("--vision-audit", choices=("auto", "off"), default="auto",
                    help="v2.2 charts (kind v22…): Telegram आधी Vision audit (Abhi). off ⇒ फक्त तपासणीसाठी; caption मध्ये 'skipped'")
    ap.add_argument("--audit-summary", default=None,
                    help="दैनिक Vision audit सारांश (append); default <data-dir>/review/v22/VISION_AUDIT.md — repo checkout बाहेर "
                         "(tracked file बदलला तर VPS deploy clean-tree check थांबतो)")
    a = ap.parse_args(argv)
    a.audit_summary = a.audit_summary or os.path.join(a.data_dir, "review", "v22", "VISION_AUDIT.md")
    if not a.no_pull:
        r = subprocess.run(["git", "-C", a.data_dir, "pull", "-q", "--ff-only"], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"❌ trade-data pull अयशस्वी: {re.sub(r'://[^@/]+@', '://***@', r.stderr.strip())[:300]}")
            return 2
    run_dir = os.path.join(a.data_dir, a.run)
    from process_lock import ProcessLock, ProcessLockHeld
    try:
        with ProcessLock("review_tg_send"):                                # एका वेळी एकच sender (sent log)
            auditor = None
            if a.vision_audit == "auto" and not a.dry_run:
                from decision3 import vision_audit as VA
                from vision import store as VS
                model = os.environ.get("VISION_SIGNAL_MODEL", "")
                auditor = VA.make_auditor(model=model, on_usage=lambda u, c: VS.add_usage(VA.TASK, model, u, c))   # per-call cost log
            out = RT.send_run(run_dir, pause_s=a.pause, dry_run=a.dry_run, run_key=a.run.strip("/"), auditor=auditor)
            if out.get("audits"):
                from decision3 import vision_audit as VA
                VA.append_summary(a.audit_summary,
                                  __import__("vision.store", fromlist=["now_ist"]).now_ist().strftime("%Y-%m-%d"), out["audits"])
                print("Vision audit: " + " · ".join(f"{x.get('chart')}: {x['status']} {x.get('verdict') or x.get('why')}"
                                                    for x in out["audits"]))
    except ProcessLockHeld:
        print("⏭️ दुसरा sender चालू आहे")
        return 5
    except RT.NoCredentials as exc:
        print(f"❌ {exc}")
        return 3
    except (OSError, ValueError) as exc:
        print(f"❌ manifest: {exc}")
        return 4
    print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    for d, why in out["failed"]:
        print(f"   ✖ {d}: {why}")
    return 0 if not out["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
