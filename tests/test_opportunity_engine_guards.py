"""tests/test_opportunity_engine_guards.py -- AST guards: indicator-मुक्त, ref_range फक्त मोजपट्टी म्हणून, कुठलाही DB/network/bot import नाही (PR-1a)."""
import ast
import glob
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "opportunity_engine", "**", "*.py"), recursive=True))

FORBIDDEN_NAMES = {"calculate_ema", "calculate_rsi", "calculate_adx", "calculate_supertrend", "calculate_bollinger", "calculate_vwap",
                   "calculate_atr", "compute_atr", "prepare_futures_ohlcv", "compute_trend_direction_1h", "supertrend", "calculate_macd",
                   "compute_dynamic_sr", "compute_sr_v3"}
FORBIDDEN_MODULES = {"cloud_db", "upstox_api", "requests", "psycopg2", "psycopg", "supabase", "streamlit", "trading_engine", "broker_factory",
                     "dynamic_sr_instant_trader", "mcx_futures_trader", "market_zones", "sr_dynamic", "sr_levels_v3", "database"}
BANNED_PANDAS_AGG = {"rolling", "ewm", "expanding", "cumsum", "diff", "shift", "mean", "cumprod", "pct_change"}
MEASURE_CALLS = {"ref_range", "adr", "ref_range_from_ranges"}


def _tree(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def _parents(tree):
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    return parent


def test_package_files_exist():
    names = {os.path.basename(f) for f in FILES}
    assert {"config.py", "measures.py", "sessions.py", "adapters.py", "structure.py", "zones.py", "level_quality.py", "journal.py"} <= names


def test_no_indicator_function_is_imported_or_called():
    bad = []
    for path in FILES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                bad += [(path, n) for n in names if n.split(".")[-1] in FORBIDDEN_NAMES]
            elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                bad.append((path, node.id))
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
                bad.append((path, node.attr))
    assert not bad, bad


def test_pr1a_has_no_db_network_ui_or_bot_imports():
    bad = []
    for path in FILES:
        for node in ast.walk(_tree(path)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            bad += [(path, m) for m in mods if m.split(".")[0] in FORBIDDEN_MODULES]
    assert not bad, bad


def test_measures_uses_only_median_aggregation():
    bad = [n.attr for n in ast.walk(_tree(os.path.join(ROOT, "opportunity_engine", "measures.py"))) if isinstance(n, ast.Attribute) and n.attr in BANNED_PANDAS_AGG]
    assert not bad, bad


def test_measure_call_sites_are_never_compared_with_prices_or_added():
    """ref_range()/adr() चा call comparison मध्ये, किंवा +/− अंकगणितात थेट नाही (फक्त `k × ref_range`, scalar assignment, float()/np.isfinite)."""
    violations = []
    for path in FILES:
        tree = _tree(path)
        parent = _parents(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in MEASURE_CALLS):
                continue
            up = parent.get(node)
            if isinstance(up, ast.Compare) or (isinstance(up, ast.BinOp) and isinstance(up.op, (ast.Add, ast.Sub))):
                violations.append((path, node.lineno))
    assert not violations, violations


def test_rr_attribute_is_never_compared_with_a_price_or_added():
    """tracker.rr / rr_hist चा वापर: Compare मध्ये फक्त स्थिरांकाशी (0) किंवा isfinite; +/− मध्ये नाही (गुणाकार/भागाकार फक्त)."""
    violations = []
    for path in FILES:
        tree = _tree(path)
        parent = _parents(tree)
        for node in ast.walk(tree):
            is_rr = (isinstance(node, ast.Attribute) and node.attr in ("rr", "rr_hist")) or (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "rr_hist")
            if not is_rr:
                continue
            up = parent.get(node)
            if isinstance(up, ast.Subscript) and up.value is node:        # rr_hist[...] चा आतला Attribute — बाहेरचा Subscript तपासेल
                continue
            if isinstance(up, ast.Compare):
                others = [x for x in [up.left] + up.comparators if x is not node]
                if not all(isinstance(x, ast.Constant) for x in others):
                    violations.append((path, node.lineno, "compare"))
            elif isinstance(up, ast.BinOp) and isinstance(up.op, (ast.Add, ast.Sub)):
                violations.append((path, node.lineno, "add/sub"))
    assert not violations, violations


def test_ref_range_requires_enough_full_bars_and_is_a_float():
    from opportunity_engine import measures
    df = pd.DataFrame({"high": [2.0] * 9, "low": [1.0] * 9, "bar_is_full": [True] * 9})
    assert measures.ref_range(df, 20, 10) != measures.ref_range(df, 20, 10)       # 10 पेक्षा कमी => NaN
    df10 = pd.DataFrame({"high": [2.0] * 10, "low": [1.0] * 10})
    assert type(measures.ref_range(df10, 20, 10)) is float
    assert not isinstance(measures.ref_range(df10), pd.Series)


def test_old_modules_are_untouched_by_the_package_import():
    import importlib
    import sr_dynamic
    import sr_levels_v3
    before = (sr_dynamic.compute_dynamic_sr, sr_levels_v3.compute_sr_v3)
    for name in ("config", "measures", "sessions", "adapters", "structure", "zones", "level_quality", "journal"):
        importlib.import_module(f"opportunity_engine.{name}")
    assert before == (sr_dynamic.compute_dynamic_sr, sr_levels_v3.compute_sr_v3)
