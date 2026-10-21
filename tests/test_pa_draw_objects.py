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


# ------------------------------------------------------------------------------------------------------------------------- renderer
def _starts_1h(days=("2026-10-20", "2026-10-21")):
    import pandas as pd
    return [pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(hours=h) for d in days for h in range(7)]


def test_xmap_maps_time_into_the_charts_own_bars():
    from decision3 import draw_render as DR
    xm = DR.XMap(_starts_1h(), j0=7, n=7)                                # the window = the second day
    assert xm.x("2026-10-21 09:15") == 0.0 and xm.x("2026-10-21 10:45", frac=False) == 1.0
    assert xm.x("2026-10-21 10:45") == pytest.approx(1.5)               # a 15M time inside a 1H bar: the bar + its fraction
    assert xm.x("2026-10-20 09:15") == -7.0                              # before the window: negative x (clipped by geometry)
    assert xm.x("2026-10-22 09:15") is None                              # after the chart's last bar: never drawn


def test_geometry_line_clipped_at_the_window_keeps_its_slope():
    from decision3 import draw_render as DR
    xm = DR.XMap(_starts_1h(), j0=7, n=7)
    ln = DO.validate(_o(t0="2026-10-20 09:15", p0=25140, t1="2026-10-21 15:15", p1=25010))   # x -7 … 6: 10 points per bar
    seg = [p for p in DR.geometry([ln], xm) if p["type"] == "seg"][0]
    assert seg["x0"] == -0.5 and seg["y0"] == pytest.approx(25140 - 10 * 6.5) and seg["x1"] == 6 and seg["y1"] == 25010


def test_geometry_area_level_edge_note_and_swing_degree_filter():
    from decision3 import draw_render as DR
    xm = DR.XMap(_starts_1h(), j0=7, n=7)
    objs = [DO.obj("area", "1H", "2026-10-21 10:15", 25050, t1="2026-10-21 15:15", p1=25080, label="1H supply", state="active",
                   style_key="area.supply.armed"),
            DO.obj("level", "D", "2026-10-01", 26000, t1="2026-10-21 15:15", label="Daily protected LH 26,000", state="protected",
                   style_key="level.protected"),
            DO.obj("swing", "15M", "2026-10-21 11:30", 25070, label="LH", state="confirmed", style_key="swing.D1", degree=1, src="H"),
            DO.obj("swing", "15M", "2026-10-21 12:15", 25075, label="LH", state="confirmed", style_key="swing.D2", degree=2, src="H")]
    pr = DR.geometry(objs, xm, ylim=(24900, 25200), min_degree=2)
    band = [p for p in pr if p["type"] == "band"][0]
    assert (band["x0"], band["x1"], band["y0"], band["y1"], band["alpha"]) == (1.0, 6.5, 25050, 25080, 0.30)
    assert [p["text"] for p in pr if p["type"] == "note"] == ["▲ Daily protected LH 26,000"]   # far level: an edge note, no squash
    sw = [p for p in pr if p["type"] == "text" and p["text"] == "LH"]
    assert len(sw) == 1 and sw[0]["x"] == 3.0 and sw[0]["va"] == "bottom"   # only D2 on a 1H chart; a high labelled above


def test_same_primitives_on_both_backends():
    """One geometry: matplotlib draws one artist per primitive and plotly one shape / trace / annotation per primitive."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from decision3 import draw_render as DR
    xm = DR.XMap(_starts_1h(), j0=7, n=7)
    objs = [DO.validate(_o(t0="2026-10-21 09:15", p0=25140, t1="2026-10-21 15:15", p1=25010, points=[["2026-10-21 09:15", 25140]])),
            DO.obj("sweep", "15M", "2026-10-21 11:00", 25000, t1="2026-10-21 11:15", p1=24980, label="sweep swing low", state="swept",
                   style_key="sweep.sell"),
            DO.obj("divergence", "15M", "2026-10-21 10:00", 25100, t1="2026-10-21 13:00", p1=25120, label="bear regular div (D1)",
                   state="confirmed", style_key="divergence.regular.bear"),
            DO.obj("entry", "15M", "2026-10-21 14:15", 25060, p1=25110, label="E2", state=None, style_key="entry.E2")]
    pr = DR.geometry(objs, xm, ylim=(24900, 25200))
    kinds = [p["type"] for p in pr]
    fig, ax = plt.subplots()
    n0 = len(ax.lines) + len(ax.texts) + len(ax.patches)
    DR.draw_mpl(ax, pr)
    assert len(ax.lines) + len(ax.texts) + len(ax.patches) - n0 == len(pr)
    plt.close(fig)
    from plotly.subplots import make_subplots
    pf = make_subplots(rows=1, cols=1)
    DR.draw_plotly(pf, pr, row=1, col=1)
    assert len(pf.layout.shapes) == kinds.count("seg") + kinds.count("band")
    assert len(pf.data) == kinds.count("marker") and len(pf.layout.annotations) == kinds.count("text") + kinds.count("note")


# ------------------------------------------------------------------------------------------------------------------------- setting
def test_chart_objects_setting_registered_default_off():
    from decision3 import settings as S3
    from vision import config as VCF
    assert S3.OUTPUT["chart_objects"][:2] == ("off", ("off", "on")) and S3.REGISTER["chart_objects"][0] == "off"
    assert VCF.BOT_DEFAULTS["chart_objects"] == "off" and "chart_objects" in VCF.CTX_KEYS
    assert "chart_objects" not in S3.DEFAULTS                            # display only, never a reading setting
    with pytest.raises(ValueError):
        VCF.validate("srv2_momentum_reversal", {"chart_objects": "yes"})


def test_vision_chart_byte_identical_when_off_and_objects_drawn_when_on():
    from tests import test_vision_v2 as TV
    from vision import chart as VCH
    from vision import config as VCF
    df = TV.bars()
    cs = {**{k: VCF.BOT_DEFAULTS[k] for k in VCF.CTX_KEYS}, "events": {}}
    cs_old = {k: v for k, v in cs.items() if k != "chart_objects"}         # today's ctx_settings (no key at all)
    objs = [DO.obj("line", "15M", "2026-10-06 09:15", 25050, t1="2026-10-06 11:00", p1=24990, label="falling line", state="respected",
                   style_key="line"),
            DO.obj("swing", "15M", "2026-10-06 10:00", 25030, label="LH", state="confirmed", style_key="swing.D2", degree=2, src="H")]
    base, m0 = VCH.render(df, TV.sig(ctx_settings=cs_old))
    if m0["error"] and "aleido" in m0["error"]:
        pytest.skip("kaleido / Chrome missing (BROWSER_PATH)")
    off, m1 = VCH.render(df, TV.sig(ctx_settings=cs, objects=objs))
    assert off == base and "objects" not in m1                           # default off: the image is today's, byte for byte
    on, m2 = VCH.render(df, TV.sig(ctx_settings={**cs, "chart_objects": "on"}, objects=objs + [{"kind": "bogus"}]))
    assert m2["error"] is None and m2["objects"] == 2 and m2["objects_dropped"] and on != base
    on2, m3 = VCH.render(df, TV.sig(ctx_settings={**cs, "chart_objects": "on"}, tags={"gate": {"objects": objs}}))
    assert m3["error"] is None and m3["objects"] == 2                   # the engine gate tags may carry the list instead (T9 wiring)


# ------------------------------------------------------------------------------------------------------------------------- engine
@pytest.fixture(scope="module")
def synth():
    from decision3 import engine as E3
    from tests.test_decision3_method import _synthetic_m15
    V = E3.V22(_synthetic_m15())
    t = len(V.m15) - 1
    return V, t, V.decide(t)


def test_collect_reads_only_what_is_known_at_t(synth):
    V, t, r = synth
    why = []
    objs = DO.collect(V, t, r=r, why=why)
    assert not why and objs and all(DO.validate(o) == o for o in objs)
    now = DO.ts_str(V.m15["timestamp"].iloc[t])
    assert all(o["t0"] <= now for o in objs)
    sw = DO.of_kind(objs, "swing")
    assert sw and {o["degree"] for o in sw} <= {1, 2} and all(o["label"] in ("HH", "HL", "LH", "LL", "EQH", "EQL", "H", "L") for o in sw)
    k = t - 40                                                           # no look-ahead: an earlier bar never sees a later swing
    early = DO.collect(V, k, since=0)
    tk = DO.ts_str(V.m15["timestamp"].iloc[k])
    assert all(o["t0"] <= tk for o in early)
    later = {(o["t0"], o["label"]) for o in DO.of_kind(DO.collect(V, t, since=0), "swing")}
    assert {(o["t0"], o["label"]) for o in DO.of_kind(early, "swing")} <= later   # confirmed swings never change label later


def test_collect_takes_other_tracks_lists_and_drops_bad_or_future_ones(synth):
    V, t, r = synth
    now = V.m15["timestamp"].iloc[t]
    ok = {"kind": "channel", "tf": "1H", "t0": V.m15["timestamp"].iloc[t - 30], "p0": 20000, "t1": now, "p1": 19600,
          "label": "falling channel", "state": "inside", "style_key": "channel", "evidence": ["two lines"],
          "lines": [{"role": "parallel", "t0": V.m15["timestamp"].iloc[t - 25], "p0": 20300, "t1": now, "p1": 19900}]}
    future = {**ok, "t0": now + __import__("pandas").Timedelta(days=1), "t1": now + __import__("pandas").Timedelta(days=2)}
    why = []
    objs = DO.collect(V, t, extras=[ok, future, {"kind": "fib", "tf": "1H", "t0": now, "p0": 1, "state": "confluent"}], r=r, why=why)
    assert len(DO.of_kind(objs, "channel")) == 1
    assert any("after the bar" in w for w in why) and any("fib" in w for w in why)


def test_decision3_charts_off_is_today_and_on_draws(synth):
    from decision3 import charts as CH
    V, t, r = synth
    tr = r["trend_used"]
    assert CH.h1_png(V.levels, t, tr, "X") == CH.h1_png(V.levels, t, tr, "X", chart_objects="off")
    assert CH.m15_png(V, t, "X", r=r) == CH.m15_png(V, t, "X", r=r, chart_objects="off")
    objs = DO.collect(V, t, r=r)
    on = CH.h1_png(V.levels, t, tr, "X", chart_objects="on", objects=objs, story=DO.story_text(DO.tf_story(V, t, objs, r=r)))
    assert on[:8] == b"\x89PNG\r\n\x1a\n" and on != CH.h1_png(V.levels, t, tr, "X")
    assert CH.m15_png(V, t, "X", r=r, chart_objects="on")[:4] == b"\x89PNG"
    with pytest.raises(ValueError):
        CH.h1_png(V.levels, t, tr, "X", chart_objects="yes")


def test_tf_story_one_line_per_timeframe(synth):
    V, t, r = synth
    objs = DO.collect(V, t, r=r)
    st = DO.tf_story(V, t, objs, r=r)
    assert list(st) == ["W", "D", "1H", "15M", "5M"] and all(st[k].startswith(k + ": ") for k in st)
    assert st["D"].startswith("D: down")                                 # the fixture is a Daily downtrend
    assert DO.tf_story(V, t, objs, r=r, states={"1H": "correction in progress"})["1H"].startswith("1H: correction in progress")
    assert DO.story_text(st).count("\n") == 4
