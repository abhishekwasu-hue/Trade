"""scripts/reader_parity_export.py — the mirror is exact and the export refuses anything but a clean tagged commit (STABLE.md)."""
import pandas as pd
import pytest

from scripts import reader_parity_export as P


def test_mirror_swaps_high_low_and_keeps_volume():
    df = pd.DataFrame({"timestamp": [1, 2], "open": [100.0, 102.0], "high": [103.0, 104.0], "low": [99.0, 101.0], "close": [102.0, 101.5],
                       "volume": [10, 20]})
    m = P.mirror(df, 100.0)
    assert m["high"].tolist() == [101.0, 99.0] and m["low"].tolist() == [97.0, 96.0]
    assert m["open"].tolist() == [100.0, 98.0] and m["close"].tolist() == [98.0, 98.5] and m["volume"].tolist() == [10, 20]
    assert (m["high"] >= m[["open", "close"]].max(axis=1)).all() and (m["low"] <= m[["open", "close"]].min(axis=1)).all()
    pd.testing.assert_frame_equal(P.mirror(m, 100.0), df.astype({"open": float}))


def test_export_refuses_unknown_layers_untagged_heads_and_existing_fixtures(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="only"):
        P.export({5: "reader-layer5-stable-v1"}, str(tmp_path))
    monkeypatch.setattr(P, "git", lambda *a: {"status": "", "rev-parse": "abc1234", "tag": "reader-layer2-stable-v1"}[a[0]])
    with pytest.raises(SystemExit, match="does not point at HEAD"):
        P.export({3: "reader-layer3-stable-v1"}, str(tmp_path))
    (tmp_path / "parity" / "layer2" / "reader-layer2-stable-v1").mkdir(parents=True)
    (tmp_path / "parity" / "layer2" / "reader-layer2-stable-v1" / "x").write_text("x")
    with pytest.raises(SystemExit, match="never overwritten"):
        P.export({2: "reader-layer2-stable-v1"}, str(tmp_path))
    monkeypatch.setattr(P, "git", lambda *a: {"status": " M x.py", "rev-parse": "abc1234", "tag": ""}[a[0]])
    with pytest.raises(SystemExit, match="changes"):
        P.export({2: "reader-layer2-stable-v1"}, str(tmp_path))


def _frame(n=3, base=100.0):
    ts = pd.date_range("2030-01-01 09:15", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": base, "high": base + 1, "low": base - 1, "close": base + 0.5})


def test_export_writes_inputs_outputs_kb_and_a_checked_manifest(monkeypatch, tmp_path):
    """Synthetic end-to-end (no real data): every case's inputs (real + mirror), each layer's JSONL output, golden.json, kb/ and a
    MANIFEST whose sha256s match the files; the NIFTY holdout Daily count is stated; a second run refuses to overwrite."""
    import gzip
    import json
    import numpy as np
    tags = {n: f"reader-layer{n}-stable-v1" for n in (1, 2, 3, 4)}
    monkeypatch.setattr(P, "git", lambda *a: {"status": "", "rev-parse": "abc1234", "tag": "\n".join(tags.values())}[a[0]])
    monkeypatch.setattr(P, "nifty_inputs", lambda td: {"m15": _frame(), "m1": None, "ltf": _frame(), "fut": _frame(), "daily": _frame(2)})
    monkeypatch.setattr(P, "banknifty_inputs", lambda td: {"m15": _frame(base=500.0), "m1": None, "ltf": None, "fut": None,
                                                           "daily": _frame(2, 500.0)})
    monkeypatch.setattr(P, "holdout_daily_bars", lambda daily: 7)
    monkeypatch.setattr(P, "build", lambda symbol, inp: {"symbol": symbol, "high0": float(inp["m15"]["high"].iloc[0])})
    monkeypatch.setattr(P, "OUTPUTS", {n: (lambda V, n=n: iter([{"layer": n, "v": V, "x": np.float64("nan"), "i": np.int64(3)}]))
                                       for n in (1, 2, 3, 4)})
    monkeypatch.setattr(P, "golden", lambda V: {"2030-01-01": {"bars": [], "symbol": V["symbol"]}})
    monkeypatch.setattr(P, "pack_version", lambda: "0123456789ab")
    roots = P.export(tags, str(tmp_path), log=lambda m: None)
    assert sorted(roots) == [1, 2, 3, 4]
    for n, root in roots.items():
        man = json.loads((tmp_path / "parity" / f"layer{n}" / tags[n] / "MANIFEST.json").read_text(encoding="utf-8"))
        assert (man["layer"], man["tag"], man["commit"], man["method_pack_version"]) == (n, tags[n], "abc1234", "0123456789ab")
        assert man["cases"] == ["NIFTY_real", "NIFTY_mirror", "BANKNIFTY_real", "BANKNIFTY_mirror"]
        assert man["holdout"].endswith(": 7 bars")
        for f, sha in man["files"].items():
            assert P._sha(f"{root}/{f}") == sha
        files = set(man["files"])
        assert {"golden.json", "kb/KNOWLEDGE_BASE.md", "kb/method_pack.md", "kb/CHART_READER_METHOD.md",
                "inputs/NIFTY_mirror/fut.csv.gz", "inputs/BANKNIFTY_real/daily.csv.gz"} <= files
        assert "inputs/BANKNIFTY_real/fut.csv.gz" not in files and "inputs/NIFTY_real/m1.csv.gz" not in files
        with gzip.open(f"{root}/outputs/NIFTY_mirror.jsonl.gz", "rt", encoding="utf-8") as fh:
            rec = json.loads(fh.readline())
        assert rec == {"i": 3, "layer": n, "v": {"high0": 102.0, "symbol": "NIFTY"}, "x": None}   # pivot 100.5: high = 2·100.5 − 99
    m = pd.read_csv(f"{roots[2]}/inputs/NIFTY_mirror/m15.csv.gz")
    assert m["high"].tolist() == [102.0] * 3 and m["low"].tolist() == [100.0] * 3
    with pytest.raises(SystemExit, match="never overwritten"):
        P.export(tags, str(tmp_path), log=lambda m: None)


def test_pack_version_reads_the_check_output(monkeypatch):
    monkeypatch.setattr(P.subprocess, "check_output", lambda *a, **k: "Method Pack version 4e65a0880257 · 38,865 chars\n✅ ok\n")
    assert P.pack_version() == "4e65a0880257"


def test_stable_register_rows_match_their_tags_and_fixture_paths():
    """docs/reader/STABLE.md: every register row names its tag `reader-layer<N>-stable-v<k>` and the fixtures at
    `parity/layer<N>/<tag>/`; a layer is called stable in the status table only with a register row (no ✅ + tag ⇒ not stable)."""
    import pathlib
    import re
    txt = (pathlib.Path(P.HERE) / "docs" / "reader" / "STABLE.md").read_text(encoding="utf-8")
    reg = txt.split("## Register", 1)[1].split("\n## ", 1)[0]
    rows = [r for r in reg.splitlines() if re.match(r"\| \d+ \|", r)]
    stable = set()
    for r in rows:
        cells = [c.strip() for c in r.strip("|").split("|")]
        n, tag = int(cells[0]), cells[1].strip("`")
        assert re.fullmatch(rf"reader-layer{n}-stable-v\d+", tag), r
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", cells[2]) and re.search(r"Method Pack `[0-9a-f]{12}`", cells[5]), r
        assert f"parity/layer{n}/{tag}/" in cells[6], r
        stable.add(n)
    state = txt.split("## Where each layer stands", 1)[1]
    called = {int(m) for m in re.findall(r"^\| (\d+) \|[^|]*\| \*\*Stable", state, flags=re.M)}
    assert called == stable and set(P.LAYERS) >= stable
