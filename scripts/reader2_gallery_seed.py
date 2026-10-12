"""scripts/reader2_gallery_seed.py — Abhi-provided seed labels (private trade-data `reader2_gallery/seeds/<split>/<id>.json`) ⇒ gallery
store (VPS वर Supabase `reader2_gallery`; `READER2_GALLERY_STORE=<folder>` ⇒ JSON folder).

🎓 उदा. CD14: Abhi च्या निर्णयातला BANKNIFTY Daily Feb 2026 top ⇒ sharp fall low leg = impulse (dev chart BANKNIFTY_D_20251215).
Label repo मध्ये कधीच नाही (public repo) — seed फक्त trade-data मध्ये; हे script फक्त तो वाचून store मध्ये टाकतं. ज्या chart ला आधीच
नोंद आहे तिथे काहीही करत नाही (Abhi ची marking जिंकते). प्रत्येक seed तपासला जातो (manifest id / split / window, bars ⇒ किंमती).
फक्त ids / आकडे छापतो (किंमती, DB key नाहीत).

    python3 scripts/reader2_gallery_seed.py [--seeds <trade-data>/reader2_gallery/seeds] [--dry-run]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gallery2 import data as GD            # noqa: E402
from gallery2 import store as GS           # noqa: E402


def main(argv=None, store=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=None, help="default: READER2_GALLERY_SEEDS किंवा <trade-data>/reader2_gallery/seeds")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--dry-run", action="store_true", help="तपासा, पण store मध्ये लिहू नका")
    a = ap.parse_args(argv)
    m = GS.load_manifest(a.manifest)
    store = store or GS.default_store()
    seeds = a.seeds or GS.seeds_dir()
    if not os.path.isdir(seeds):
        print(f"⏸ seeds folder नाही: {seeds} — काहीही केलं नाही")
        return 3
    res = GS.import_seeds(store, m, seeds, bars_for=GD.load_window, dry_run=a.dry_run)
    print(json.dumps({"store": store.describe(), "seeds": seeds, "dry_run": a.dry_run, **res}, ensure_ascii=False, indent=1))
    return 1 if res["invalid"] or res["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
