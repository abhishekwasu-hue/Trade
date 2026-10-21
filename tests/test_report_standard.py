"""docs/reader/REPORT_STANDARD.md is enforced: a chart missing a layer, a day-based outcome horizon or a missing section fails."""
import pytest

from reader_report import standard as RS


def chart(key="E1@a", drop=None, story="line one\nline two"):
    layers = {k: {"evaluated": True, "count": 0} for k in RS.REQUIRED_LAYERS}
    layers["story"]["note"] = story
    if drop:
        layers.pop(drop)
    return {"entry_key": key, "layers": layers,
            "lines_view": {"max_lines": 6, "shown": ["ev", "ch"], "evidence": ["ev"], "legend": ["ev", "ch"], "hidden": 3}}


def card(key="E1@a", **kw):
    c = {"entry_key": key, "model": "E1", "area": "1H 290", "state": "tested", "side": "bear_call", "evidence": [["handover", "✓"]],
         "invalidation": 55135.5, "story": "a\nb", "outcome": "next_area_first", "mfe": 700.0, "mae": 30.0}
    c.update(kw)
    return c


def report(**kw):
    r = {"first_line": RS.RULES_LINE, "summary_mr": "सारांश", "outcome_rule": {"horizon": "structure", "target": "next opposite area",
         "stop": "15M close beyond the invalidation"}, "entries": [card()], "charts": {"E1@a": chart()},
         "per_model": [{"model": "E1"}], "running_total": [{"model": "E1"}], "missed_big_moves": [{"chart": "m.png"}],
         "worst_losses": [], "gaps": []}
    r.update(kw)
    return r


@pytest.mark.parametrize("layer", RS.REQUIRED_LAYERS)
def test_every_layer_is_required(layer):
    with pytest.raises(RS.ReportStandardError, match=layer):
        RS.validate_chart(chart(drop=layer))


def test_story_is_two_lines():
    with pytest.raises(RS.ReportStandardError, match="two lines"):
        RS.validate_chart(chart(story="only one"))
    assert RS.validate_chart(chart())


@pytest.mark.parametrize("rule", [{"horizon": "trigger_day"}, {"horizon": "session_end"}, {"horizon": "eod"},
                                  {"horizon": "structure", "cutoff": "end of the trigger day"},
                                  {"horizon": "structure", "max_hold": "2 sessions"}, {"horizon": "structure", "max_hold": "48 hours"},
                                  {"horizon": "structure", "cutoff": "till market close"}, {"horizon": "structure", "cut": "3 weeks"}])
def test_day_based_horizon_fails(rule):
    with pytest.raises(RS.ReportStandardError):
        RS.validate_outcome_rule(rule)


def test_structural_rule_passes_and_full_report_passes():
    assert RS.validate_outcome_rule({"horizon": "structure", "target": "next opposite area", "stop": "close beyond invalidation"})
    assert RS.validate_report(report())


def test_every_entry_needs_a_chart_not_samples():
    with pytest.raises(RS.ReportStandardError, match="no chart"):
        RS.validate_report(report(entries=[card(), card("E3@b")]))


@pytest.mark.parametrize("key,val,msg", [("first_line", "Hello", "first line"), ("summary_mr", "", "Marathi"),
                                         ("running_total", [], "running_total"), ("missed_big_moves", None, "missed_big_moves"),
                                         ("worst_losses", [{"chart": ""}], "worst_losses"), ("gaps", None, "gaps")])
def test_sections_required(key, val, msg):
    with pytest.raises(RS.ReportStandardError, match=msg):
        RS.validate_report(report(**{key: val}))


def test_card_fields_and_outcome_words():
    with pytest.raises(RS.ReportStandardError, match="invalidation"):
        RS.validate_card(card(invalidation=None))
    with pytest.raises(RS.ReportStandardError, match="outcome"):
        RS.validate_card(card(outcome="target_by_eod"))


def test_claude_md_and_standard_exist_with_key_rules():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    md = (root / "CLAUDE.md").read_text(encoding="utf-8")
    for need in ("PAPER only", "Exits are never blocked", "human_confirm", "Never run anything on the VPS", "holdout",
                 "CLOSED", "E1–E4", "No fixed numbers", "REPORT_STANDARD.md", "Rules re-read: CLAUDE.md, REPORT_STANDARD.md"):
        assert need in md, need
    std = (root / "docs" / "reader" / "REPORT_STANDARD.md").read_text(encoding="utf-8")
    for k in RS.REQUIRED_LAYERS:
        assert f"`{k}`" in std, k


# ------------------------------------------------------------------------------------------------ P8 clean charts (legend cap, evidence)
def test_legend_cap_follows_the_display_setting():
    from decision3 import settings as S3
    m = chart()
    m["lines_view"].update(shown=[f"l{i}" for i in range(7)], legend=[f"l{i}" for i in range(7)], evidence=["l0"], max_lines=7)
    with pytest.raises(RS.ReportStandardError, match="max_lines 7 > chart_max_lines 6"):
        RS.validate_chart(m)
    assert RS.validate_chart(m, chart_max_lines=7)                       # Abhi set the dashboard value higher
    assert S3.OUTPUT["chart_max_lines"][0] == RS.chart_max_lines_default() == 6
    m["lines_view"]["max_lines"] = 6
    with pytest.raises(RS.ReportStandardError, match="legend lists 7 lines > chart_max_lines 6"):
        RS.validate_chart(m)


def test_evidence_lines_must_be_shown_and_legend_only_shown_lines():
    m = chart()
    m["lines_view"]["evidence"] = ["ev", "gone"]
    with pytest.raises(RS.ReportStandardError, match="evidence line"):
        RS.validate_chart(m)
    m = chart()
    m["lines_view"]["legend"] = ["ev", "ch", "a hidden line"]
    with pytest.raises(RS.ReportStandardError, match="only the shown lines"):
        RS.validate_chart(m)
    m = chart()
    m.pop("lines_view")
    with pytest.raises(RS.ReportStandardError, match="lines_view"):
        RS.validate_chart(m)


# ------------------------------------------------------------------------------------------------ RC5: the pre-replay data check
def test_group_is_testable_only_with_fut_volume_on_every_spot_session():
    spot = ["2026-10-07", "2026-10-08", "2026-10-09"]
    ok = RS.group_data_status(spot, spot + ["2026-10-10"])
    assert ok["status"] == "testable" and ok["missing"] == []
    bad = RS.group_data_status(spot, ["2026-10-07", "2026-10-09"])
    assert bad["status"] == RS.NOT_TESTABLE == "not testable — FUT volume missing" and bad["missing"] == ["2026-10-08"]
    assert bad["line"].startswith("not testable — FUT volume missing") and "2026-10-08" in bad["line"]
    assert RS.group_data_status([], [])["status"] == RS.NOT_TESTABLE
    with pytest.raises(RS.ReportStandardError, match="not testable"):   # a not-testable group never ships a report
        RS.validate_report(report(data_status=bad))
    assert RS.validate_report(report(data_status=ok))


@pytest.mark.parametrize("text", ["close beyond invalidation; update on new swing", "next opposite area; candidate area",
                                  "validated by volume", "the area's far edge on the same timeframe"])
def test_structural_words_are_not_day_words(text):
    assert RS.validate_outcome_rule({"horizon": " Structure ", "stop": text})


def test_malformed_inputs_raise_the_standard_error():
    with pytest.raises(RS.ReportStandardError):
        RS.validate_chart(None)
    c = card(); c.pop("entry_key")
    with pytest.raises(RS.ReportStandardError, match="entry_key"):
        RS.validate_card(c)
