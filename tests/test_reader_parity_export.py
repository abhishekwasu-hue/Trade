"""scripts/reader_parity_export.py — the mirror is exact; the export refuses anything but a clean tagged commit, an output inside this
public repo, a sealed (holdout) intraday bar, or an engine error, and never leaves a partial folder (STABLE.md). No real data here."""
import os

import pandas as pd
import pytest

from scripts import reader_parity_export as P


def fake_git(status="", tags="", worktrees=()):
    """`git` as the exporter calls it: status, rev-parse HEAD / --show-toplevel, tag --points-at, worktree list."""
    def git(*a):
        if a[0] == "status":
            return status
        if a[0] == "rev-parse":
            return P.HERE if "--show-toplevel" in a else "abc1234"
        if a[0] == "tag":
            return tags
        if a[0] == "worktree":
            return "\n".join(f"worktree {w}\nHEAD abc1234\n" for w in (*worktrees, P.HERE))
        raise AssertionError(a)
    return git


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
    monkeypatch.setattr(P, "git", fake_git(tags="reader-layer2-stable-v1"))
    with pytest.raises(SystemExit, match="does not point at HEAD"):
        P.export({3: "reader-layer3-stable-v1"}, str(tmp_path))
    (tmp_path / "parity" / "layer2" / "reader-layer2-stable-v1").mkdir(parents=True)
    (tmp_path / "parity" / "layer2" / "reader-layer2-stable-v1" / "x").write_text("x")
    with pytest.raises(SystemExit, match="never overwritten"):
        P.export({2: "reader-layer2-stable-v1"}, str(tmp_path))
    monkeypatch.setattr(P, "git", fake_git(status=" M x.py"))
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
    monkeypatch.setattr(P, "git", fake_git(tags="\n".join(tags.values())))
    monkeypatch.setattr(P, "nifty_inputs", lambda td: {"m15": _frame(), "m1": None, "ltf": _frame(), "fut": _frame(), "daily": _frame(2)})
    monkeypatch.setattr(P, "banknifty_inputs", lambda td: {"m15": _frame(base=500.0), "m1": None, "ltf": None, "fut": None,
                                                           "daily": _frame(2, 500.0)})
    monkeypatch.setattr(P, "check_holdout", lambda symbol, inp: 7 if symbol == "NIFTY" else 0)
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
        assert man["holdout_daily_bars"] == {"NIFTY_real": 7, "NIFTY_mirror": 7, "BANKNIFTY_real": 0, "BANKNIFTY_mirror": 0}
        assert "NIFTY_mirror 7 bars" in man["holdout"]
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
    assert sorted(os.listdir(tmp_path / "parity" / "layer1")) == [tags[1]]           # no temp folder left behind


def _setup_synthetic(monkeypatch, tags):
    monkeypatch.setattr(P, "git", fake_git(tags="\n".join(tags.values())))
    monkeypatch.setattr(P, "nifty_inputs", lambda td: {"m15": _frame(), "m1": None, "ltf": None, "fut": None, "daily": None})
    monkeypatch.setattr(P, "banknifty_inputs", lambda td: {"m15": _frame(), "m1": None, "ltf": None, "fut": None, "daily": None})
    monkeypatch.setattr(P, "pack_version", lambda: "0123456789ab")


def test_an_engine_error_fails_the_export_and_leaves_no_partial_folder(monkeypatch, tmp_path):
    """No silent "error" fixtures: an engine exception on any bar stops the export, names the bar, and removes the temp folder, so
    a re-run is not blocked."""
    tags = {3: "reader-layer3-stable-v1", 4: "reader-layer4-stable-v1"}
    _setup_synthetic(monkeypatch, tags)

    class V:
        m15 = _frame()

        def decide(self, t):
            if t == 2:
                raise ValueError("boom")
            return {"decision": "wait"}
    monkeypatch.setattr(P, "build", lambda symbol, inp: V())
    with pytest.raises(P.EngineError, match=r"layer 3: the engine raised on bar 2 .*ValueError: boom"):
        P.export(tags, str(tmp_path), log=lambda m: None)
    for n, tag in tags.items():
        d = tmp_path / "parity" / f"layer{n}"
        assert not d.exists() or os.listdir(d) == []
    monkeypatch.setattr(V, "decide", lambda self, t: {"decision": "wait"})
    monkeypatch.setattr(P, "OUTPUTS", {**P.OUTPUTS, 4: lambda V: iter([{"ok": 1}])})
    monkeypatch.setattr(P, "golden", lambda V: {})
    assert sorted(P.export(tags, str(tmp_path), log=lambda m: None)) == [3, 4]  # the re-run is not blocked


def test_the_output_never_goes_inside_this_public_repo(monkeypatch, tmp_path):
    """Parity fixtures are private: an output root inside this checkout, its top level or any worktree of the repo is refused — also
    through a symlink — before anything is written."""
    tags = {1: "reader-layer1-stable-v1"}
    other = tmp_path / "Trade-main"
    (other / "trade-data").mkdir(parents=True)
    _setup_synthetic(monkeypatch, tags)
    monkeypatch.setattr(P, "git", fake_git(tags=tags[1], worktrees=(str(other),)))
    for out in (os.path.join(P.HERE, "parity"), os.path.join(P.HERE, "..", os.path.basename(P.HERE), "x"), str(other / "trade-data")):
        with pytest.raises(SystemExit, match="inside this public repo"):
            P.export(tags, str(tmp_path), out)
    (tmp_path / "link").symlink_to(P.HERE)
    with pytest.raises(SystemExit, match="inside this public repo"):
        P.export(tags, str(tmp_path / "link" / "trade-data"))
    assert not os.path.exists(os.path.join(P.HERE, "parity"))
    assert P.guard_out_root(str(tmp_path / "td" / "parity")) == os.path.realpath(tmp_path / "td" / "parity")


def test_holdout_check_refuses_sealed_intraday_bars_and_late_sealed_daily(monkeypatch):
    """NIFTY: no 15M / LTF / FUT / 1m bar on a sealed date; sealed Daily bars only before the 15M window (Abhi Z-1t), counted.
    BANKNIFTY has no sealed dates."""
    from elliott import data_policy as DP
    sealed = DP.HOLDOUT_START + pd.Timedelta(days=30, hours=9, minutes=15)
    after = DP.ILLUSTRATION_START + pd.Timedelta(days=3, hours=9, minutes=15)

    def fr(ts):
        return pd.DataFrame({"timestamp": pd.to_datetime(ts), "close": 1.0})
    ok = {"m15": fr([after]), "ltf": fr([after]), "fut": None, "m1": None, "daily": fr([sealed.normalize(), sealed.normalize()
                                                                                        + pd.Timedelta(days=1), after.normalize()])}
    assert P.check_holdout("NIFTY", ok) == 2 and P.check_holdout("BANKNIFTY", {**ok, "m15": fr([sealed])}) == 0
    for k in P.INTRADAY:
        with pytest.raises(SystemExit, match=f"{k}: 1 rows on sealed"):
            P.check_holdout("NIFTY", {**ok, k: fr([sealed])} if k != "m15" else {**ok, "m15": fr([sealed, after])})
    with pytest.raises(SystemExit, match="at / after the 15M window start"):
        P.check_holdout("NIFTY", {**ok, "m15": fr([DP.HOLDOUT_START - pd.Timedelta(days=5)]), "ltf": None,   # a VAL window
                                   "daily": fr([sealed.normalize()])})


def test_real_nifty_inputs_have_no_sealed_intraday_bars():
    """The real golden inputs (private trade-data; skipped without it): no sealed intraday bar; sealed Daily only before the window."""
    from tests import test_decision3_flip as T
    if not all(os.path.exists(p) for p in T.files(T.TD).values()):
        pytest.skip("private trade-data not present")
    inp = P.nifty_inputs(T.TD)
    assert P.check_holdout("NIFTY", inp) > 0 and P.check_holdout("NIFTY", P.mirrored(inp)) == P.check_holdout("NIFTY", inp)


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
