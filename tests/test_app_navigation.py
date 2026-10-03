"""tests/test_app_navigation.py -- sidebar मांडणी (4 विभाग, 11 पानं) आणि Orders -> Settings साधनांची हालचाल जशीच्या तशी टिकावी म्हणून.
app.py streamlit चालवल्याशिवाय import होत नाही, म्हणून स्रोत-मजकूर तपासतो."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_SRC = (ROOT / "app.py").read_text(encoding="utf-8")

EXPECTED_SECTIONS = {
    "TRADE": ["page_dashboard", "page_positions", "page_orders"],
    "BOTS": ["page_bot_dynamic_sr_algo", "page_mcx_futures"],
    "ANALYZE": ["page_performance", "page_multi_strategy", "page_mtf_pullback", "page_sr_levels_v3", "page_opportunity_engine"],
    "SYSTEM": ["page_broker_accounts"],
}


def _navigation_block():
    start = APP_SRC.index("    pages = {")
    end = APP_SRC.index("    pg = st.navigation(pages)")
    return APP_SRC[start:end]


def test_sections_and_pages_are_exactly_as_agreed():
    block = _navigation_block()
    parsed = {}
    current = None
    for line in block.splitlines():
        header = re.match(r'\s+"([A-Z]+)": \[', line)
        if header:
            current = header.group(1)
            parsed[current] = []
            continue
        page = re.search(r"st\.Page\((page_[a-z0-9_]+)\.render", line)
        if page and current:
            parsed[current].append(page.group(1))
    assert parsed == EXPECTED_SECTIONS


def test_every_page_has_a_unique_url_path_and_exactly_one_default():
    block = _navigation_block()
    urls = re.findall(r'url_path="([a-z0-9-]+)"', block)
    assert len(urls) == 11 and len(set(urls)) == 11
    assert block.count("default=True") == 1


def test_every_page_module_is_registered():
    registered = {p for pages in EXPECTED_SECTIONS.values() for p in pages}
    on_disk = {p.stem for p in ROOT.glob("page_*.py") if p.stem not in ("page_system_tools",)}
    assert registered == on_disk


def test_system_tools_live_in_settings_not_orders():
    orders = (ROOT / "page_orders.py").read_text(encoding="utf-8")
    for needle in ("run_system_diagnostics", "reconcile_positions", "restore_db_from_bytes", "upload_to_google_drive"):
        assert needle not in orders
    settings = (ROOT / "page_broker_accounts.py").read_text(encoding="utf-8")
    for fn in ("render_system_diagnostics", "render_data_safety", "render_history_backup"):
        assert fn in settings
    tools = ast.parse((ROOT / "page_system_tools.py").read_text(encoding="utf-8"))
    assert {n.name for n in tools.body if isinstance(n, ast.FunctionDef)} == {
        "render_system_diagnostics", "render_data_safety", "render_history_backup",
    }


def test_dead_srv2_lots_control_is_gone_from_settings():
    """Settings वरचा 'SRv2 Settings (Lots/Hedge Width)' जुन्या srv2_settings table मध्ये लिहायचा, जी आता कुठलाही bot वाचत नाही."""
    settings = (ROOT / "page_broker_accounts.py").read_text(encoding="utf-8")
    assert "save_srv2_settings" not in settings and "get_srv2_settings" not in settings
