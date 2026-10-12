"""scripts/reader2_gallery_candidates.py — Chart Reader v2 gallery चे candidate charts (CR3, spec §5) ⇒ `gallery2/data/manifest.json`.

🎓 फक्त किंमतीवरून वर्णनात्मक tags (gallery2/candidates.py चा "निवड नियम") — reader2 / decision3 चं उत्तर किंवा trade निकाल वापरत नाही.
NIFTY holdout चा bar कधीच वाचत नाही (gallery2/data.py). Manifest मध्ये फक्त तारखा / tags / आकडे — candles नाहीत (public repo).

**नेहमीचा (documented) मार्ग = additive:** नवा symbol (उदा. SENSEX) त्याच्याच 70 / 30 stratum मध्ये, आधीचे NIFTY / BANKNIFTY
entries byte-for-byte तसेच (Abhi ची marking सुरक्षित):

    python3 scripts/reader2_gallery_candidates.py --add-symbol SENSEX [--base gallery2/data/manifest.json] [--out PATH]

`--out` नाही ⇒ base manifest मध्येच. Symbol चे OHLC files नाहीत ⇒ काहीही लिहीत नाही, कारण सांगतो (exit 3).

पूर्ण rebuild (split बदलू शकतो — marking सुरू झाल्यावर नको): `--force` शिवाय असलेला manifest कधीच बदलत नाही.

    python3 scripts/reader2_gallery_candidates.py [--seed 7] [--out gallery2/data/manifest.json] [--force]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gallery2 import candidates as GC      # noqa: E402
from gallery2 import data as GD            # noqa: E402
from gallery2 import store as GS           # noqa: E402


def _write(path, m):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def _summary(m):
    by = {s: {"dev": sum(c["split"] == "dev" for c in m["charts"] if c["symbol"] == s),
              "test": sum(c["split"] == "test" for c in m["charts"] if c["symbol"] == s)} for s in GD.SYMBOLS}
    return {"n_total": m["n_total"], "dev": m["n_dev"], "test": m["n_test"], "by_symbol": by, "counts": m["counts"],
            "missing": [f"{x['symbol']}/{x['timeframe']}" for x in m.get("missing", [])]}


def add_symbol(symbol, base_path, out_path, inputs=None):
    """Additive mode. inputs (tests) = (slots, cases, missing); नाहीतर या machine वरचा data. रिटर्न exit code."""
    symbol = symbol.upper()
    if symbol not in GD.SYMBOLS:
        print(f"⛔ {symbol}: माहीत नसलेला symbol ({', '.join(GD.SYMBOLS)})")
        return 2
    base = GS.load_manifest(base_path)
    slots, cases, missing = inputs if inputs is not None else GC.real_inputs(symbols=[symbol])
    try:
        m = GC.add_symbol(base, symbol, slots, cases, missing)
    except GD.DataMissing as exc:
        why = "; ".join(f"{x['timeframe']}: {x['why']}" for x in missing if x["symbol"] == symbol)
        print(f"⏸ {exc}. Manifest तसाच ({base_path}); काहीही लिहिलं नाही." + (f" [{why}]" if why else ""))
        return 3
    except ValueError as exc:
        print(f"⛔ {exc}. Manifest तसाच; काहीही लिहिलं नाही.")
        return 2
    _write(out_path, m)
    new = [c for c in m["charts"] if c["symbol"] == symbol]
    print(json.dumps({"added": symbol, "new_charts": len(new), "dev": sum(c["split"] == "dev" for c in new),
                      "test": sum(c["split"] == "test" for c in new), "seed": m["strata"][symbol]["seed"],
                      "by_tf": {t: sum(c["timeframe"] == t for c in new) for t in GD.TIMEFRAMES},
                      "unchanged_entries": len(base["charts"]), "out": out_path, "manifest": _summary(m)}, ensure_ascii=False))
    return 0


def main(argv=None, inputs=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=GC.SEED)
    ap.add_argument("--out", default=None, help="लिहायचा manifest (default: repo manifest / additive मध्ये --base)")
    ap.add_argument("--force", action="store_true", help="पूर्ण rebuild ने असलेला manifest बदला (split बदलू शकतो — marking सुरू झाल्यावर नको)")
    ap.add_argument("--add-symbol", default=None, help="Additive: हा symbol त्याच्याच 70/30 stratum मध्ये जोडा; आधीचे entries तसेच")
    ap.add_argument("--base", default=None, help="Additive mode चा आधीचा manifest (default: repo manifest)")
    a = ap.parse_args(argv)
    if a.add_symbol:
        base = a.base or GS.manifest_path()
        return add_symbol(a.add_symbol, base, a.out or base, inputs)
    out = a.out or GS.MANIFEST
    if os.path.exists(out) and not a.force:
        print(f"⛔ {out} आधीच आहे — overwrite नाही (split / ids बदलले तर Abhi ची marking चुकीच्या split मध्ये जाईल). "
              "नवा symbol ⇒ --add-symbol <SYMBOL>; पूर्ण rebuild मुद्दाम हवा असेल तर --force.")
        return 2
    slots, cases, missing = inputs if inputs is not None else GC.real_inputs()
    m = GC.build(slots, cases, seed=a.seed, missing=missing)
    _write(out, m)
    print(json.dumps(_summary(m), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
