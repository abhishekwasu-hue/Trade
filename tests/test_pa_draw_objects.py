"""PA standard §4 OUTPUT (track T8): the one drawn-object list — schema, validation, extras from other tracks, renderers (same geometry on
the matplotlib and plotly charts), the chart_objects setting (default off = today's charts), the per-timeframe story. Synthetic only."""
import pytest

from decision3 import draw_objects as DO


def _o(**kw):
    base = {"kind": "line", "tf": "1H", "t0": "2026-10-20 10:15", "p0": 25100, "t1": "2026-10-21 11:15", "p1": 25000,
            "label": "falling line", "state": "respected", "style_key": "line.falling", "evidence": ["two reactions"]}
    base.update(kw)
    return base


def test_schema_fields_and_kinds():
    assert DO.FIELDS == ("kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "style_key", "evidence")
    assert set(DO.KINDS) == {"swing", "area", "line", "channel", "level", "fvg", "fib", "pattern", "liquidity", "sweep", "divergence",
                             "entry"}
    o = DO.validate(_o())
    assert list(o)[:10] == list(DO.FIELDS)
    assert o["t0"] == "2026-10-20 10:15:00" and o["p1"] == 25000.0 and o["evidence"] == ["two reactions"]


def test_point_objects_fill_t1_p1():
    o = DO.obj("swing", "15M", "2026-10-21 09:45", 25050.555, label="LH", state="confirmed", style_key="swing.D2", degree=2)
    assert o["t1"] == o["t0"] and o["p1"] == o["p0"] == 25050.56 and o["degree"] == 2


@pytest.mark.parametrize("bad, why", [
    (_o(kind="trendline"), "unknown kind"),
    (_o(tf="2H"), "unknown tf"),
    (_o(t1="2026-10-19 10:00"), "before t0"),
    (_o(p0=float("nan")), "not finite"),
    (_o(state="maybe"), "state"),
    (_o(style_key="area.supply"), "style_key"),
    (_o(kind="area", p0=25100, p1=25000, state="active", style_key="area"), "band"),
    (_o(kind="fib", state="confluent", style_key="fib", evidence=[]), "only when"),
    (_o(kind="area", p0=25000, p1=25100, state="active", style_key="area", base_type="XYZ"), "base_type"),
])
def test_bad_objects_raise_with_reason(bad, why):
    with pytest.raises(ValueError, match=why):
        DO.validate(bad)


def test_unknown_optional_field_rejected():
    with pytest.raises(ValueError, match="unknown field"):
        DO.obj("level", "D", "2026-10-01", 25500, colour="red")


def test_clean_never_raises_and_says_why():
    good, why = DO.clean([_o(), _o(kind="nope"), "not a dict", None])
    assert len(good) == 1 and len(why) == 3 and "unknown kind" in why[0]


def test_channel_and_pattern_lines_points():
    ch = DO.obj("channel", "1H", "2026-10-15 09:15", 24800, t1="2026-10-21 10:15", p1=25150, label="rising channel", state="broken",
                style_key="channel.rising", evidence=["lower line closed through"],
                lines=[{"role": "parallel", "t0": "2026-10-15 13:15", "p0": 25050, "t1": "2026-10-21 10:15", "p1": 25400}])
    assert ch["lines"][0]["role"] == "parallel" and ch["lines"][0]["t1"] == "2026-10-21 10:15:00"
    pt = DO.obj("pattern", "15M", "2026-10-20 10:00", 25200, t1="2026-10-21 11:00", p1=25200, label="double top", state="forming",
                style_key="pattern", points=[["2026-10-20 10:00", 25300], ["2026-10-21 10:30", 25295]])
    assert pt["points"][1] == ["2026-10-21 10:30:00", 25295.0]


def test_window_filter():
    objs = [DO.validate(_o()), DO.validate(_o(t0="2026-10-01 09:15", t1="2026-10-02 09:15"))]
    assert len(DO.in_window(objs, "2026-10-21 09:15", "2026-10-21 15:15")) == 1
