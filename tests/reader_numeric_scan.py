"""Scan the reading modules for numeric literals used in comparisons (the threshold shape `x > 0.6`, `n >= 3`). Shared by
tests/test_reader_no_new_thresholds.py and its baseline refresh (python3 -m tests.reader_numeric_scan --write, reviewed in a PR)."""
import ast
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
READING = ROOT / "decision3"
# not reading logic: settings (the allow-list), chart / display / audit / data-loading modules
EXCLUDE = {"__init__.py", "settings.py", "charts.py", "setup_chart.py", "preopen_chart.py", "telegram_view.py", "volume_pane.py",
           "draw_render.py", "draw_objects.py", "vision_audit.py", "history.py", "advisory.py"}
ALLOWED = {0, 1, -1, 2, -2}                                              # sign / index / pair arithmetic, not thresholds
BASELINE = ROOT / "tests" / "data" / "reader_numeric_literals_baseline.json"


def _num(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) \
            and isinstance(node.operand.value, (int, float)) and not isinstance(node.operand.value, bool):
        return -node.operand.value
    return None


def scan():
    out = {}
    for f in sorted(READING.glob("*.py")):
        if f.name in EXCLUDE:
            continue
        c = collections.Counter()
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Compare):
                for side in [node.left, *node.comparators]:
                    v = _num(side)
                    if v is not None and v not in ALLOWED:
                        c[repr(float(v))] += 1
        out[f.name] = dict(sorted(c.items()))
    return out


if __name__ == "__main__" and "--write" in sys.argv:
    BASELINE.write_text(json.dumps(scan(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {BASELINE}")
