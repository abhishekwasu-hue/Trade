"""Trade sunset §4: the export manifest classifies every trade-data folder, fails on an unclassified or a missing moving item, and its
checksum verifies a copied item (same files ⇒ same sum; a changed byte ⇒ a different one)."""
import os

import pytest

from scripts import reader_export_manifest as RM


def _tree(root, items):
    for rel in items:
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(rel)


def test_checksum_verifies_a_copy_and_changes_with_content(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for r in (a, b):
        _tree(str(r), ["x/1.csv", "x/sub/2.csv"])
    assert RM.measure(str(a), "x") == RM.measure(str(b), "x")
    (b / "x" / "1.csv").write_text("changed")
    assert RM.measure(str(a), "x")[2] != RM.measure(str(b), "x")[2]
    assert RM.measure(str(a), "missing") is None


def test_unclassified_folder_fails_the_run(tmp_path, monkeypatch):
    _tree(str(tmp_path), ["upstox/1.csv", "review/swings2/s.json", "review/new_run/c.png", "brand_new/z.csv"])
    monkeypatch.setattr(RM, "ITEMS", [("data", "upstox", "Candle history", True, ""), ("data", "review/swings2", "Abhi", True, "")])
    assert RM.unclassified(str(tmp_path)) == ["brand_new", "review/new_run"]
    with pytest.raises(SystemExit):
        RM.build(str(tmp_path))


def test_missing_moving_item_fails_and_output_has_no_data(tmp_path, monkeypatch):
    _tree(str(tmp_path), ["upstox/1.csv"])
    monkeypatch.setattr(RM, "ITEMS", [("data", "upstox", "Candle history", True, "spot")])
    text = RM.build(str(tmp_path))
    assert "| `upstox` | trade-data | 1 |" in text and "upstox/1.csv" not in text
    monkeypatch.setattr(RM, "ITEMS", [("data", "upstox", "C", True, ""), ("data", "gone", "C", True, "")])
    with pytest.raises(SystemExit):
        RM.build(str(tmp_path))
