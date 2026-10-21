"""docs/reader/REPORT_STANDARD.md is enforced: a chart missing a layer, a day-based outcome horizon or a missing section fails."""
import pytest

from reader_report import standard as RS


def chart(key="E1@a", drop=None, story="line one\nline two"):
    layers = {k: {"evaluated": True, "count": 0} for k in RS.REQUIRED_LAYERS}
    layers["story"]["note"] = story
    if drop:
        layers.pop(drop)
    return {"entry_key": key, "layers": layers}


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
                                  {"horizon": "structure", "max_hold": "2 sessions"}])
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
