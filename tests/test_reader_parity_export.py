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
