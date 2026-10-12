"""scripts/reader2_gallery_candidates.py — Chart Reader v2 gallery चे 40 candidate charts (CR3, spec §5) ⇒ `gallery2/data/manifest.json`.

🎓 फक्त किंमतीवरून वर्णनात्मक tags (gallery2/candidates.py चा "निवड नियम") — reader2 / decision3 चं उत्तर किंवा trade निकाल वापरत नाही.
Split 28 dev / 12 test seeded (seed manifest मध्ये). NIFTY holdout चा bar कधीच वाचत नाही (gallery2/data.py). Manifest मध्ये फक्त
तारखा / tags / आकडे — candles नाहीत (public repo). Data नसलेले symbol / TF (उदा. SENSEX) manifest च्या `missing` मध्ये.

    python3 scripts/reader2_gallery_candidates.py [--seed 7] [--out gallery2/data/manifest.json] [--force]

असलेला manifest --force शिवाय कधीच बदलत नाही (marking सुरू झाल्यावर split / ids स्थिर हवेत).
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gallery2 import candidates as GC      # noqa: E402
from gallery2 import store as GS           # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=GC.SEED)
    ap.add_argument("--out", default=GS.MANIFEST)
    ap.add_argument("--force", action="store_true", help="असलेला manifest बदला (split बदलू शकतो — marking सुरू झाल्यावर नको)")
    a = ap.parse_args(argv)
    if os.path.exists(a.out) and not a.force:
        print(f"⛔ {a.out} आधीच आहे — overwrite नाही (split / ids बदलले तर Abhi ची marking चुकीच्या split मध्ये जाईल). "
              "मुद्दाम बदलायचा असेल तर --force.")
        return 2
    slots, cases, missing = GC.real_inputs()
    m = GC.build(slots, cases, seed=a.seed, missing=missing)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps({"n_total": m["n_total"], "dev": m["n_dev"], "test": m["n_test"], "counts": m["counts"],
                      "missing": [f"{x['symbol']}/{x['timeframe']}" for x in m["missing"]]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
