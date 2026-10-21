"""CLAUDE.md: no fixed numbers in reading rules. A NEW numeric literal in a comparison in the reading modules (decision3, minus
settings / display) fails. Numbers belong in decision3/settings.py (REGISTER, classified by test_method_no_numbers.py). The baseline
lists the reviewed existing literals (METHOD_MAP); it may only shrink — refresh it (python3 -m tests.reader_numeric_scan --write) only
in a reviewed PR that removes literals."""
import json

from tests import reader_numeric_scan as RS


def test_no_new_numeric_thresholds_in_reading_modules():
    base = json.loads(RS.BASELINE.read_text(encoding="utf-8"))
    new = []
    for f, counts in RS.scan().items():
        for v, n in counts.items():
            if n > base.get(f, {}).get(v, 0):
                new.append(f"{f}: {v} ×{n - base.get(f, {}).get(v, 0)}")
    assert not new, "new hard-coded thresholds in reading code (move them to decision3/settings.py): " + "; ".join(new)


def test_scan_detects_a_threshold(tmp_path, monkeypatch):
    p = tmp_path / "x.py"
    p.write_text("def f(a):\n    return a > 0.6 or a >= 2 or a < -1\n", encoding="utf-8")
    monkeypatch.setattr(RS, "READING", tmp_path)
    assert RS.scan() == {"x.py": {"0.6": 1}}                            # 2 and -1 are sign / index arithmetic


def test_no_dates_in_reading_modules():
    # intended: every decision3 file, display modules included (CLAUDE.md: no date framing anywhere in the reader package)
    import re
    for f in RS.READING.glob("*.py"):
        assert not re.search(r"20\d\d-\d\d-\d\d", f.read_text(encoding="utf-8")), f.name
