"""tests/test_dashboard_default_dyn_levels.py -- NIFTY Dashboard chart चा "—" view: chart च्या TF चे (15M) bot चे Supabase Dynamic S/R levels,
लाल/हिरव्या ठिपक्यांच्या रेषा; DB मध्ये नसतील तर chart वरून मोजलेले (जुने) levels."""
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

import cloud_db

from tests.test_dashboard_sr_v3_view import ROOT, SCRIPT, _trade_lines

ZONES = pd.DataFrame([
    {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": 24150.0, "zone_high": 24150.0, "strength": 4, "status": "ACTIVE"},
    {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": 24050.0, "zone_high": 24050.0, "strength": 3, "status": "ACTIVE"},
    {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 24090.0, "zone_high": 24090.0, "strength": 2, "status": "ACTIVE"}])


def _run(script):
    at = AppTest.from_string(script.replace("__ROOT__", repr(ROOT)), default_timeout=120)
    at.run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    return at


def test_default_view_shows_bots_db_levels_for_chart_tf():
    with patch.object(cloud_db, "get_market_zones", return_value=ZONES), \
         patch.object(cloud_db, "get_zone_hits_today_bulk", return_value={}), \
         patch.object(cloud_db, "get_strategy_settings", return_value={"max_hits_per_zone": 2}):
        at = _run(SCRIPT)
    lines = _trade_lines(at.session_state["html"])
    assert sorted(l["price"] for l in lines) == [24050.0, 24150.0]                 # फक्त 15M (chart TF), 5M चा नाही
    by = {l["price"]: l for l in lines}
    assert by[24150.0]["color"].startswith("rgba(255,23,68") and by[24050.0]["color"].startswith("rgba(0,200,83") and by[24150.0]["dotted"]
    assert "Support / Resistance Levels" not in at.session_state["html"]          # chart वरून मोजलेले levels काढले
    assert "15M" in at.session_state["note"]


def test_default_view_falls_back_to_computed_levels_without_db():
    at = _run(SCRIPT)
    html = at.session_state["html"]
    assert _trade_lines(html) == [] and "Support / Resistance Levels" in html and "LineStyle.Dotted, title: l.title" in html
