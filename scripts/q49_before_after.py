"""scripts/q49_before_after.py — Q49 (Abhi: 5-wave पहिला पाय default wave A) before / after: Daily fold base (git rev) वि. working
tree, त्याच Daily data वर. trend / phase / counter बदललेले दिवस, trend बदलाचे पट्टे, wave A दिवस, शेवटचा दिवस.

  python3 scripts/q49_before_after.py --csv /home/user/trade-data/banknifty/BANKNIFTY_D.csv.gz --symbol BANKNIFTY [--base HEAD]

NIFTY: sealed holdout (elliott.data_policy) — HOLDOUT_START पासूनचे bars fold मध्ये कधीच जात नाहीत (आधीच कापले). Order / broker /
network call नाही; फक्त अहवाल (stdout).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CHILD = r"""
import json, sys
import pandas as pd
sys.path.insert(0, sys.argv[1]); sys.path.insert(1, sys.argv[2])
from decision3 import daily as DD
d = pd.read_pickle(sys.argv[3])
rows = []
for x in DD.fold(d):
    w = getattr(x, "wave_a", None)
    rows.append([str(x.day.date()), x.trend, x.phase, x.counter, None if x.protected is None else round(x.protected.price, 2),
                 None if w is None else round(w.price, 2), getattr(x, "alt", None)])
json.dump(rows, open(sys.argv[4], "w"))
"""


def load(csv, symbol):
    import pandas as pd
    sys.path.insert(0, ROOT)
    from decision3 import daily_swings as DS
    d = DS.prepare(pd.read_csv(csv))
    if symbol.upper() == "NIFTY":                                           # sealed holdout: त्या तारखेपासून काहीच नाही
        from elliott import data_policy as DP
        d = d[d["timestamp"] < DP.HOLDOUT_START].reset_index(drop=True)
    return d


def fold_rows(pkg_root, frame_pkl, out_json):
    subprocess.run([sys.executable, "-c", _CHILD, pkg_root, ROOT, frame_pkl, out_json], check=True, cwd=pkg_root)
    return json.load(open(out_json))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--base", default="HEAD", help="git rev of the base decision3 (default HEAD = before uncommitted Q49)")
    a = ap.parse_args(argv)
    d = load(a.csv, a.symbol)
    with tempfile.TemporaryDirectory() as tmp:
        base_root = os.path.join(tmp, "base")
        os.makedirs(base_root)
        arch = subprocess.run(["git", "-C", ROOT, "archive", a.base, "decision3"], check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", base_root], input=arch, check=True)
        pkl = os.path.join(tmp, "d.pkl")
        d.to_pickle(pkl)
        old = fold_rows(base_root, pkl, os.path.join(tmp, "old.json"))
        new = fold_rows(ROOT, pkl, os.path.join(tmp, "new.json"))
    assert len(old) == len(new) == len(d)
    n = len(d)
    diff = {k: sum(1 for o, w in zip(old, new) if o[j] != w[j]) for j, k in ((1, "trend"), (2, "phase"), (3, "counter"),
                                                                            (4, "protected"))}
    print(f"{a.symbol}: {n} Daily bars {old[0][0]} → {old[-1][0]} · base {a.base} vs working tree")
    for k, v in diff.items():
        print(f"  {k:9s} differs on {v} / {n} days")
    print(f"  wave A (alt 1) shown on {sum(1 for w in new if w[5] is not None)} days")
    runs, cur = [], None
    for o, w in zip(old, new):
        key = (o[1], w[1]) if o[1] != w[1] else None
        if key != (cur[2] if cur else None):
            if cur:
                runs.append(cur)
            cur = [w[0], w[0], key] if key else None
        elif cur:
            cur[1] = w[0]
    if cur:
        runs.append(cur)
    print(f"  trend-difference runs: {len(runs)}")
    for s_, e_, (bo, bn) in runs:
        print(f"    {s_} → {e_}: base {bo} · Q49 {bn}")
    for tag, r in (("base", old[-1]), ("Q49 ", new[-1])):
        print(f"  last day {tag}: trend {r[1]} · phase {r[2]} · counter {r[3]} · protected {r[4]} · wave A {r[5]} · alt {r[6]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
