"""reader2 is research-only (spec §1): no production module (decision3, bots, vision, engine, dashboard …) imports it."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"tests", "reader2", ".git", "venv", ".venv", "node_modules", "__pycache__"}


def _imports(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
    return out


def test_no_production_module_imports_reader2():
    bad = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in SKIP or any(part in SKIP for part in rel.parts):
            continue
        if "reader2" in _imports(p):
            bad.append(str(rel))
    assert not bad, f"research-only reader2 imported by: {bad}"


def test_reader2_does_not_import_bots_or_vision():
    banned = {"bots_common", "vision", "vision2", "vision_led", "decision2", "order_execution", "broker_factory"}
    for p in (ROOT / "reader2").glob("*.py"):
        assert not (_imports(p) & banned), p.name
