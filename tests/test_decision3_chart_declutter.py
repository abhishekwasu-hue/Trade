"""PR B (Abhi: TRADE_SESSION_Q44_Q49_Q55_CHART_FIX §5) — Daily structure chart declutter, legend, 2-line caption, Vision consistency.

Synthetic fixtures only (no real dates / prices in code). Mirror (UP / DOWN) pairs wherever direction matters.
"""
import itertools

import numpy as np
import pytest

from decision3 import charts as CH
from decision3 import daily_legs as DL
from decision3 import daily_swings as DS
from decision3 import settings as S3
from decision3 import vision_audit as VA
from tests import elliott_fixtures as F
from tests.test_decision3_daily_review import HEAD, WAVE4, WAVE5, path


def long_points():
    """~2.5 years of Daily bars: an UP staircase of 5-wave impulses and zigzag corrections, then a pullback in progress."""
    waves, px = [], 1000.0
    for _ in range(7):
        waves += [(px + 300, "m5")] + F.zz(px + 300 - 110, px + 300 - 60, px + 300 - 165)
        px += 135
    waves += [(px + 280, "m5"), (px + 280 - 120, "c3")]
    return [(1000.0, 0)] + F.build(1000.0, waves)


TWO_YEARS = 500                                                            # ≈ 2 years of sessions


def _long(mirror):
    d = F.ohlc(long_points(), mirror)
    return DS.build(d, window=TWO_YEARS, with_elliott=False)


def _mirror_path(points):
    return path([(F.MIRROR - p, n) for p, n in points])


def _fixture(mirror):
    pts = HEAD + WAVE4 + WAVE5
    return DS.build(_mirror_path(pts) if mirror else path(pts), window=60, with_elliott=False)


def _texts(fig_info):
    fig, info = fig_info
    fig.canvas.draw()
    return fig, info, fig.canvas.get_renderer()


MIRRORS = [pytest.param(False, id="down-or-up"), pytest.param(True, id="mirror")]


@pytest.fixture(autouse=True)
def _close_figs():
    yield
    import matplotlib.pyplot as plt
    plt.close("all")


# ------------------------------------------------------------------------------------------------ §5.1 / §5.2 boxes
@pytest.mark.parametrize("mirror", MIRRORS)
def test_two_year_window_labels_only_current_and_previous_correction(mirror):
    v = _long(mirror)
    sp = DS.view_spec(v)
    shown = [b for b in sp["boxes"] if b["label"]]
    assert 1 <= len(shown) <= 2 and len(sp["tags"]) <= 2
    assert v["n"] - v["i0"] > S3.DEFAULTS["chart_old_box_sessions"]       # long window ⇒ older boxes omitted (no faint clutter)
    assert all(b["label"] for b in sp["boxes"])
    cur = [b for b in sp["boxes"] if b["state"] == "in progress"]
    assert cur and cur[0]["label"].startswith("pullback")                 # in-progress candidate: "pullback" written once
    assert not any("candidate" in t for t in sp["tags"]) and sum(t.count("pullback") for t in sp["tags"]) == 1
    done = [c for c in v["q15"]["objects"]["corrections"] if c["state"] == "done"]
    assert [b["end_bar"] for b in sp["boxes"] if b["state"] == "done"] == [done[-1]["end_bar"]]


def test_short_window_keeps_older_boxes_faint_without_text():
    v = _fixture(False)
    sp = DS.view_spec(v)
    corr = [c for c in v["q15"]["objects"]["corrections"] if c["end_bar"] >= v["i0"]]
    assert len(sp["boxes"]) == len(corr)
    assert all((b["label"] is None) == b["faint"] for b in sp["boxes"])
    assert sum(1 for b in sp["boxes"] if b["label"]) <= 2


@pytest.mark.parametrize("mirror", MIRRORS)
def test_box_depth_is_start_to_end_extreme_only(mirror):
    v = _long(mirror)
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    boxes = [p for p in info["ax"].patches if (p.get_gid() or "").startswith(("correction", "counter-move", "older"))]
    sp = DS.view_spec(v)
    assert len(boxes) == len(sp["boxes"])
    for p, c in zip(boxes, sp["boxes"]):
        lo, hi = sorted((c["start_price"], c["end_price"]))
        assert p.get_y() == pytest.approx(lo) and p.get_y() + p.get_height() == pytest.approx(hi)
        end = c["end_bar"] if c["state"] == "done" else v["n"] - 1
        assert p.get_x() + p.get_width() == pytest.approx(end - v["i0"] + 0.5)


def test_full_view_still_shows_everything():
    v = _long(False)
    full = DS.view_spec(v, full=True)
    corr = [c for c in v["q15"]["objects"]["corrections"] if c["end_bar"] >= v["i0"]]
    assert len(full["boxes"]) == len(corr) and all(b["label"] for b in full["boxes"])
    assert len(full["bands"]) >= len(DS.view_spec(v)["bands"])
    assert CH.daily_swings_png(v, "TEST", full=True)[:4] == b"\x89PNG"


# ------------------------------------------------------------------------------------------------ §5.4 bands
NAME_RE = ("demand ", "supply ", "sharp-fall supply ", "sharp-rise demand ", "protected ", "parent protected ", "target ")


@pytest.mark.parametrize("mirror", MIRRORS)
def test_bands_trader_names_at_most_one_broken(mirror):
    v = _fixture(mirror)
    bands = v["q15"]["levels"]
    assert 0 < len(bands) <= 6
    assert all(b["name"].startswith(NAME_RE) for b in bands), [b["name"] for b in bands]
    close = float(v["frame"]["close"].iloc[-1])
    for b in bands:
        if b["role"] in ("demand", "supply") and b["state"] != "broken":
            assert b["role"] == ("demand" if b["price"] < close else "supply")
        if b["state"] != "target":
            assert f"({b['state']})" in b["name"]
    assert sum(1 for b in bands if b["state"] == "broken") <= 1
    every = DS.level_bands(v, limit=None, max_broken=None)
    br = [b for b in every if b["state"] == "broken"]
    if len(br) > 1:                                                        # the kept one is the most recently broken
        kept = [b for b in bands if b["state"] == "broken"]
        assert kept and kept[0]["broken_bar"] == max(b["broken_bar"] for b in br)


@pytest.mark.parametrize("mirror", MIRRORS)
def test_structure_extreme_ranks_above_window_extremes(mirror):
    """The major low / high the structure stands on (start of the last same-degree correction) outranks the window low / high."""
    d, _ = F.acceptance_banknifty_two_lows(mirror)
    v = DS.build(d, window=len(d), with_elliott=False)
    every = DS.level_bands(v, limit=None, max_broken=None)
    lab = [b["label"] for b in every]
    base = next(i for i, x in enumerate(lab) if x.startswith("structure "))
    win = [i for i, x in enumerate(lab) if x.startswith("window ")]
    assert all(base < i for i in win)
    want = "structure high" if mirror else "structure low"
    assert lab[base] == want


@pytest.mark.parametrize("mirror", MIRRORS)
def test_broken_band_drawn_dashed_and_labelled(mirror):
    v = _fixture(mirror)
    br = [b for b in v["q15"]["levels"] if b["state"] == "broken"]
    assert br, "fixture has a broken band (Q55 sharp-fall swing low)"
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    lines = [ln for ln in info["ax"].lines if ln.get_gid() == "broken"]
    assert lines and all(ln.get_linestyle() == "--" for ln in lines)
    assert any(t.get_gid() == "broken" and "(broken)" in t.get_text() for t in info["ax"].texts)


# ------------------------------------------------------------------------------------------------ §5.5 / §5.6 layout
def _all_text_boxes(fig, info, r):
    out = []
    for a in (info["ax"], info["bx"]):
        out += [(t.get_text(), t.get_window_extent(r)) for t in a.texts if t.get_visible() and t.get_text().strip()]
    if info["ax"].get_legend() is not None:
        out.append(("<legend>", info["ax"].get_legend().get_window_extent(r)))
    out.append(("<title>", info["ax"].title.get_window_extent(r)))
    return out


def _candle_hits(info, bb):
    ax, fr = info["ax"], info["frame"]
    (x0, y0), (x1, y1) = ax.transData.inverted().transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
    lo, hi = fr["low"].to_numpy(float), fr["high"].to_numpy(float)
    idx = [i for i in range(len(fr)) if i + 0.3 >= x0 and i - 0.3 <= x1]
    return [i for i in idx if lo[i] <= y1 and hi[i] >= y0]


CASES = [pytest.param(lambda: _long(False), id="long"), pytest.param(lambda: _long(True), id="long-mirror"),
         pytest.param(lambda: _fixture(False), id="c-wave"), pytest.param(lambda: _fixture(True), id="c-wave-mirror"),
         pytest.param(lambda: DS.build(F.acceptance_banknifty()[0], window=200, with_elliott=False), id="bn-shape")]


@pytest.mark.parametrize("mk", CASES)
def test_no_text_overlaps_text_or_candles(mk):
    v = mk()
    fig, info, r = _texts(CH.daily_swings_fig(v, "TEST"))
    boxes = _all_text_boxes(fig, info, r)
    for (ta, a), (tb, b) in itertools.combinations(boxes, 2):
        assert not a.overlaps(b), f"{ta!r} overlaps {tb!r}"
    for t in info["ax"].texts:
        assert not _candle_hits(info, t.get_window_extent(r)), t.get_text()
    assert not _candle_hits(info, info["ax"].get_legend().get_window_extent(r)), "legend over candles"


@pytest.mark.parametrize("mirror", MIRRORS)
def test_label_count_on_two_year_window(mirror):
    """≤ 2 correction labels + their wave letters + 6 band labels + 1 in-progress leg label + legend."""
    v = _long(mirror)
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    kinds = [x["kind"] for x in info["labels"]]
    letters = sum(len(b.get("marks") or ()) for b in DS.view_spec(v)["boxes"] if b["label"])
    assert kinds.count("correction") <= 2 and kinds.count("band") <= 6 and kinds.count("leg") <= 1
    assert 0 < kinds.count("wave") <= letters <= 2 * 5
    assert set(kinds) <= {"correction", "wave", "wave_a", "band", "leg"}
    assert len(info["ax"].texts) == len(kinds) <= 2 + letters + 6 + 1
    assert info["ax"].get_legend() is not None


@pytest.mark.parametrize("mk", CASES)
def test_legend_lists_exactly_the_styles_drawn(mk):
    v = mk()
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    ax = info["ax"]
    drawn = {a.get_gid() for a in list(ax.lines) + list(ax.patches) + list(ax.texts) + list(ax.collections) if a.get_gid()}
    legend = {t.get_text() for t in ax.get_legend().get_texts()}
    assert legend == {CH.LEGEND_TEXT[g] for g in drawn}
    assert all(g in CH.LEGEND_TEXT for g in drawn)


# ------------------------------------------------------------------------------------------------ §5.7 caption
@pytest.mark.parametrize("mirror", MIRRORS)
def test_caption_line1_state_protected_risk_line2_nearest_band_atr(mirror):
    v = _fixture(mirror)
    q = v["q15"]
    t = q["trend"]
    cap = DS.caption(v, "TEST", audit_line="Vision audit: pass").splitlines()
    assert len(cap) <= 7 and cap[-1] == "Visual review only — no trade, no order"
    atr = DS.atr(v["frame"], S3.DEFAULTS["chart_atr_n"])
    close = float(v["frame"]["close"].iloc[-1])
    p = q["protected_now"]["price"]
    assert cap[0].startswith(f"TEST Daily: {t}") and f"protected {p:,.0f}" in cap[0]
    assert f"risk {DS.protected_risk(v):.1f} ATR" in cap[0]
    assert cap[1].startswith("Nearest ") and "ATR" in cap[1]
    sup, dem = DS.nearest_bands(v)
    for b, side in ((sup, "supply"), (dem, "demand")):
        if b is not None:
            assert f"earest {side}: {b['name']}, {b['dist_atr']:.1f} ATR" in cap[1]
            assert b["hi"] > close if side == "supply" else b["lo"] < close
    assert cap[2].startswith("Trend " + t)


def _tiny_frame():
    """3 Daily bars, hand values: TR = 2 (H−L), 3 (H − prev close 12 − 9), 4 (prev close − L 11 − 7)."""
    import pandas as pd
    return pd.DataFrame({"timestamp": pd.bdate_range("2030-01-01", periods=3), "open": [9.0, 9.0, 11.0], "high": [10.0, 12.0, 11.0],
                         "low": [8.0, 9.0, 7.0], "close": [9.0, 11.0, 8.0]})


def test_atr_hand_values():
    d = _tiny_frame()
    assert DS.atr(d, 2) == pytest.approx(3.5) and DS.atr(d, 3) == pytest.approx(3.0) and DS.atr(d, 14) == pytest.approx(3.0)


def _band(role, price, lo, hi, state="tested", rank=2, label=None):
    b = {"rank": rank, "label": label or role, "price": price, "lo": lo, "hi": hi, "state": state, "bar": 0, "off_window": None,
         "broken_bar": None, "also": [], "role": role}
    b["name"] = DS.band_name(b)
    return b


def _tiny_v(levels, protected=None):
    return {"frame": _tiny_frame(), "s": {"chart_atr_n": 3},                # close 8, ATR 3.0
            "q15": {"levels": levels, "protected_now": protected}}


def test_nearest_band_by_edge_not_centre_and_exclusions():
    wide = _band("supply", 14.0, 9.5, 18.5)                                # centre 6 away, edge 1.5 away
    thin = _band("supply", 12.0, 11.8, 12.2)                               # centre 4 away, edge 3.8 away
    low = _band("demand", 5.0, 4.0, 6.0)                                   # edge 2 below
    brk = _band("demand", 7.5, 7.2, 7.8, state="broken")                   # closer but broken ⇒ excluded
    tgt = _band("target", 8.6, 8.5, 8.7, state="target")                   # closer but target ⇒ excluded
    sup, dem = DS.nearest_bands(_tiny_v([thin, wide, low, brk, tgt]))
    assert sup["price"] == 14.0 and sup["dist_atr"] == 0.5                 # 1.5 / 3.0
    assert dem["price"] == 5.0 and dem["dist_atr"] == pytest.approx(0.7)   # 2.0 / 3.0 = 0.67 ⇒ 0.7
    inside = _band("demand", 7.9, 7.0, 9.0)                                # close 8 inside ⇒ 0
    sup, dem = DS.nearest_bands(_tiny_v([inside, thin]))
    assert dem["price"] == 7.9 and dem["dist_atr"] == 0.0 and sup["price"] == 12.0 and sup["dist_atr"] == pytest.approx(1.3)


@pytest.mark.parametrize("mirror", MIRRORS)
def test_caption_risk_to_protected_price_line2_to_band_edge(mirror):
    """Line 1 risk = close → protected PRICE (never the merged sharp-zone edge, which would understate it); line 2 = band edge."""
    if not mirror:                                                         # protected 11 above close 8, merged zone 9.0–12.0
        prot = _band("protected", 11.0, 9.0, 12.0, rank=1, label="protected origin · sharp-fall supply")
        pk = "H"
    else:                                                                  # protected 5 below close 8, merged zone 4.0–7.0
        prot = _band("protected", 5.0, 4.0, 7.0, rank=1, label="protected origin · sharp-rise demand")
        pk = "L"
    prot["sharp"] = "sharp-rise demand" if mirror else "sharp-fall supply"
    prot["name"] = DS.band_name(prot)
    v = _tiny_v([prot], protected={"kind": pk, "price": prot["price"], "bar": 1})
    sup, dem = DS.nearest_bands(v)
    near = dem if mirror else sup
    assert DS.protected_risk(v) == pytest.approx(1.0)                      # |8 − 11| / 3 (or |8 − 5| / 3) — the price itself
    assert near["dist_atr"] == pytest.approx(0.3)                          # 1.0 / 3 to the zone edge


@pytest.mark.parametrize("cap_sessions, kept", [(200, True), (199, False)])
def test_old_box_window_boundary(cap_sessions, kept):
    v = DS.build(F.ohlc(long_points()), window=200, with_elliott=False)
    assert v["n"] - v["i0"] == 200
    v["s"] = {"chart_old_box_sessions": cap_sessions}
    sp = DS.view_spec(v)
    corr = [c for c in v["q15"]["objects"]["corrections"] if c["end_bar"] >= v["i0"]]
    assert len(corr) > sum(1 for b in sp["boxes"] if b["label"])           # window has older (unlabelled) boxes
    assert any(b["faint"] for b in sp["boxes"]) is kept and (len(sp["boxes"]) == len(corr)) is kept


# ------------------------------------------------------------------------------------------------ review: bands
def test_drop_path_keeps_protected_and_target_and_records_drops():
    v = _fixture(False)
    p = v["q15"]["protected_now"]["price"]
    packed = [_band("protected", p, p - 1, p + 1, rank=1, label="protected origin"),
              _band("target", p - 2, p - 2, p - 2, state="target", rank=4, label="target")]
    packed += [_band("supply", p + 2 + k, p + 1.5 + k, p + 2.5 + k, rank=5, label="correction end") for k in range(8)]
    v["q15"]["levels"] = packed
    png, meta = CH.daily_swings_render(v, "TEST")
    assert packed[0]["name"] in meta["bands_drawn"] and packed[1]["name"] in meta["bands_drawn"]
    assert meta["dropped"] and not set(meta["dropped"]) & set(meta["bands_drawn"])
    assert len(meta["bands_drawn"]) + len(meta["dropped"]) == len(packed)
    js = DS.to_json(v, "TEST")
    js["chart"].update(meta)
    f = VA.facts_text("v22_daily_swings", js)
    assert "Not drawn (no room for the label): " + meta["dropped"][0] in f and meta["dropped"][0] not in f.split("Bands: ")[1].split("\n")[0]


def test_protected_line_needs_the_protected_label_not_only_the_parent():
    v = _fixture(False)
    p = v["q15"]["protected_now"]["price"]
    v["q15"]["levels"] = [_band("parent protected", p + 40, p + 39, p + 41, rank=0, label="larger-degree origin")]
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    lines = [ln for ln in info["ax"].lines if ln.get_gid() == "protected origin"]
    assert not any(abs(ln.get_ydata()[0] - p) < 1e-9 for ln in lines)       # no unlabelled protected line


def _synthetic_levels_v():
    """Controlled candidates: parent 150 (broken long ago), next level 80 (broken recently), a valid correction end 151 that the
    parent band used to swallow, window high / low."""
    import pandas as pd
    c = np.r_[np.full(10, 100.0), np.linspace(100, 200, 10), np.linspace(200, 50, 10), np.linspace(50, 120, 10), np.full(5, 120.0)]
    d = pd.DataFrame({"timestamp": pd.bdate_range("2030-01-01", periods=len(c)), "open": c, "high": c + 1, "low": c - 1, "close": c})
    d = DS.prepare(d)
    corr = [{"state": "done", "start_bar": 38, "start_price": 125.0, "end_bar": 40, "end_price": 151.0}]
    q = {"trend": "NEUTRAL", "parent": {"kind": "H", "price": 150.0, "bar": 5}, "protected_now": None, "sharp_end": None,
         "next_level": {"price": 80.0, "bar": 8}, "targets": [], "objects": {"corrections": corr}}
    return {"frame": d, "n": len(d), "i0": 0, "q15": q}


def test_broken_limit_applies_before_merging():
    v = _synthetic_levels_v()
    every = DS.level_bands(v, limit=None, max_broken=None)
    br = [b for b in every if b["state"] == "broken"]
    assert {b["price"] for b in br} >= {150.0, 80.0}
    old = min(br, key=lambda b: b["broken_bar"])
    assert old["price"] == 150.0                                           # parent broke first, next level later
    out = DS.level_bands(v)
    assert [b["price"] for b in out if b["state"] == "broken"] == [80.0]   # the most recent broken survives
    assert any(b["price"] == 151.0 and b["state"] != "broken" for b in out)   # the level the dropped band absorbed reappears


@pytest.mark.parametrize("mirror", MIRRORS)
def test_protected_inside_sharp_zone_is_one_band_one_label(mirror):
    from tests.test_decision3_abc_fix import _bn_points
    d = F.ohlc(_bn_points()[:-3], mirror)
    v = DS.build(d, window=len(d), with_elliott=False)
    lv = v["q15"]["levels"]
    side = "sharp-rise demand" if mirror else "sharp-fall supply"
    merged = [b for b in lv if b.get("sharp")]
    assert len(merged) == 1 and merged[0]["name"].startswith(f"{side} · protected ")
    assert not any(b["role"] == side for b in lv)                          # no second overlapping sharp band


def test_target_merges_into_any_live_hit():
    """Target between a broken band (first hit) and a live one ⇒ joins the live one, not a separate target band."""
    v = _synthetic_levels_v()
    base = DS.level_bands(v)
    b80 = next(b for b in base if b["price"] == 80.0)
    h = (b80["hi"] - b80["lo"]) / 2
    v["q15"]["objects"]["corrections"].append({"state": "done", "start_bar": 39, "start_price": 125.0, "end_bar": 41,
                                               "end_price": 80.0 + 3 * h})
    v["q15"]["targets"] = [80.0 + 1.5 * h]
    out = DS.level_bands(v, limit=None)
    live = next(b for b in out if abs(b["price"] - round(80.0 + 3 * h, 2)) < 1e-6)
    assert live["state"] != "broken" and "target" in live["also"] and not any(b["role"] == "target" for b in out)
    assert not next(b for b in out if b["price"] == 80.0)["also"]


# ------------------------------------------------------------------------------------------------ Abhi review: wave letters
@pytest.mark.parametrize("mirror", MIRRORS)
def test_wave_letters_sit_at_the_pivots_of_the_family_read(mirror):
    v = _long(mirror)
    d, i0 = v["frame"], v["i0"]
    H, L = d["high"].to_numpy(float), d["low"].to_numpy(float)
    sp = DS.view_spec(v)
    shown = [b for b in sp["boxes"] if b["label"]]
    done = [b for b in shown if b["state"] == "done"]
    prog = [b for b in shown if b["state"] != "done"]
    assert done and prog
    assert [m["letter"] for m in done[-1]["marks"]] == ["a", "b", "c"]     # zigzag
    assert [m["letter"] for m in prog[-1]["marks"]] == ["a", "b"]          # running c ⇒ no letter
    for b in shown:
        fam, ends = DL.wave_ends(b["wave_prices"])
        assert fam == {"5-wave": "impulse"}.get(b["shape"], b["shape"])   # the letters come from the same read as the shape
        pts = list(zip(b["wave_bars"], b["wave_prices"]))
        for m in b["marks"]:
            assert (m["bar"], m["price"]) in pts
            assert m["price"] == (H[m["bar"]] if m["kind"] == "H" else L[m["bar"]])   # at the pivot's wick extreme
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    drawn = [x for x in info["labels"] if x["kind"] == "wave"]
    assert drawn and len(drawn) <= sum(len(b["marks"]) for b in shown)
    for x in drawn:
        assert tuple(x["artist"].xy) == (x["bar"] - i0, x["price"])
        assert x["text"] in "abcdeWXYZ"


def test_wave_ends_letters_per_family():
    zz = [100.0] + F.m5(100.0, 140.0) + F.c3(140.0, 125.0) + F.m5(125.0, 170.0)
    fam, ends = DL.wave_ends(zz)
    assert fam == "zigzag" and [w for _, w in ends] == ["a", "b", "c"] and ends[-1][0] == len(zz) - 1
    assert [zz[k] for k, _ in ends] == [140.0, 125.0, 170.0]
    fam, ends = DL.wave_ends([100.0, 130.0, 115.0, 170.0, 150.0, 200.0])
    assert fam == "impulse" and ends == []                                 # motive ⇒ no correction letters


# ------------------------------------------------------------------------------------------------ Abhi review: verified legs
class _P:
    def __init__(self, kind, price, bar, confirm_bar=None):
        self.kind, self.price, self.bar, self.confirm_bar = kind, price, bar, bar + 2 if confirm_bar is None else confirm_bar


def _leg(prices, mirror, gap=5):
    """prices = origin, inner turns, end (UP); mirror ⇒ DOWN. Returns (leg dict, pivots)."""
    px = [F.MIRROR - p for p in prices] if mirror else list(prices)
    up = not mirror
    lg = {"dir": 1 if up else -1, "from": 0, "to": gap * (len(px) - 1), "p0": px[0], "p1": px[-1]}
    piv = [_P(("H" if k % 2 else "L") if up else ("L" if k % 2 else "H"), px[k], gap * k) for k in range(1, len(px) - 1)]
    return lg, piv


FIVE = [100.0, 130.0, 115.0, 170.0, 150.0, 200.0]
THREE = [100.0, 140.0, 120.0, 170.0]


@pytest.mark.parametrize("mirror", MIRRORS)
def test_leg_check_five_waves_is_impulse_three_is_not(mirror):
    lg, piv = _leg(FIVE, mirror)
    c = DS.leg_check(lg, piv, [], 100)
    assert c["verified"] and c["style"] == "impulse" and c["family"] == "impulse"
    assert c["path"] == [[b, p] for b, p in zip(range(0, 30, 5), [lg["p0"]] + [q.price for q in piv] + [lg["p1"]])]
    lg, piv = _leg(THREE, mirror)
    c = DS.leg_check(lg, piv, [], 100)
    assert not c["verified"] and c["style"] == "unconfirmed" and c["family"] != "impulse" and c["n"] == 3   # never "corrective"
    c = DS.leg_check(lg, piv, [], 100, in_progress=True)
    assert not c["verified"] and c["style"] == "unconfirmed" and c["state"] == "in progress"
    lg, piv = _leg(FIVE, mirror)
    assert DS.leg_check(lg, piv, [], 100, in_progress=True)["style"] == "impulse"   # running leg already reads 5 waves


@pytest.mark.parametrize("mirror", MIRRORS)
def test_impulse_of_several_engine_sub_legs_is_verified_as_one_leg(mirror):
    """Waves 2 / 4 large enough for the engine to cut sub-legs (origin advances, no A1) ⇒ one trend-degree leg, read whole."""
    w = [(1300.0, "m5"), (1180.0, "c3"), (1600.0, "m5"), (1450.0, "c3"), (1750.0, "m5"), (1600.0, "c3")]
    d = F.ohlc([(1000.0, 0)] + F.build(1000.0, w), mirror)
    v = DS.build(d, window=len(d), with_elliott=False)
    ob = v["q15"]["objects"]
    assert len(ob["legs"]) >= 2 and not any(c.get("broke_origin") for c in ob["corrections"] if c["state"] == "done")
    imp = ob["impulses"]
    assert len(imp) == 1 and imp[0]["sub_legs"] == len(ob["legs"])
    assert imp[0]["family"] == "impulse" and imp[0]["verified"] and imp[0]["style"] == "impulse"
    assert imp[0]["from"] == ob["legs"][0]["from"] and imp[0]["to"] == ob["legs"][-1]["to"]
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    lines = [ln for ln in info["ax"].lines if ln.get_gid() in ("impulse leg", "trend leg")]
    assert len(lines) == 1 and lines[0].get_gid() == "impulse leg"         # sub-legs are not drawn as separate legs


def test_a1_correction_splits_trend_degree_impulses():
    legs = [{"dir": -1, "from": 0, "to": 10, "p0": 200.0, "p1": 150.0}, {"dir": -1, "from": 14, "to": 20, "p0": 170.0, "p1": 120.0},
            {"dir": -1, "from": 30, "to": 40, "p0": 190.0, "p1": 100.0}]
    corrs = [{"state": "done", "start_bar": 10, "end_bar": 14, "broke_origin": False},
             {"state": "done", "start_bar": 20, "end_bar": 30, "broke_origin": True}]
    imp = DS.trend_impulses(legs, corrs, [], [], 100)
    assert [(x["from"], x["to"], x["sub_legs"]) for x in imp] == [(0, 20, 2), (30, 40, 1)]


def test_coarse_path_never_raises_when_reduction_stops_early():
    p = [100.0]
    p += [100.0 + 3 * k if k % 2 else 100.0 - 3 * k for k in range(1, 41)]   # expanding swings: no inner pair can be removed
    p.append(p[-2] + 500.0)
    pts = list(enumerate(p))
    for mp in (15, 6, 2):
        out = DS.coarse_path(pts, mp)
        assert out[0] == pts[0] and out[-1] == pts[-1] and all(q in pts for q in out)
    ok = [(i, x) for i, x in enumerate([100.0, 130.0, 115.0, 170.0, 150.0, 200.0, 180.0, 230.0, 210.0, 260.0])]
    assert len(DS.coarse_path(ok, 2)) <= DS.MIN_PATH_POINTS                 # max_points below the floor ⇒ floor (6)


@pytest.mark.parametrize("mirror", MIRRORS)
def test_pullback_label_anchored_to_current_bounce_with_leader(mirror):
    v = _fixture(mirror)
    q = v["q15"]
    assert q["counter"] == "pullback"
    cur = q["objects"]["legs"][-1]
    d = v["frame"]
    seg = d["high"].to_numpy(float)[cur["to"] + 1:] if cur["dir"] < 0 else d["low"].to_numpy(float)[cur["to"] + 1:]
    want = float(seg.max() if cur["dir"] < 0 else seg.min())
    pb = DS.view_spec(v)["pullbacks"]
    assert len(pb) == 1 and pb[0]["bar"] > cur["to"] and pb[0]["price"] == want and pb[0]["text"] == "pullback"
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    lab = next(x for x in info["labels"] if x["text"] == "pullback")
    x0, y0 = pb[0]["bar"] - v["i0"], pb[0]["price"]
    assert any(list(ln.get_xdata())[0] == x0 and list(ln.get_ydata())[0] == y0 and ln.get_gid() is None for ln in info["ax"].lines)
    assert lab["bar"] == pb[0]["bar"]


NINE = [100.0, 130.0, 110.0, 150.0, 120.0, 160.0, 135.0, 175.0, 140.0, 190.0]   # 9 waves read_counter cannot parse


@pytest.mark.parametrize("mirror", MIRRORS)
def test_long_leg_path_is_coarse_and_on_its_pivots(mirror):
    px = [100.0]
    for k in range(20):                                                    # 40 waves: big dips early, small dips late
        up = px[-1] + 30.0 + (k % 3) * 5
        px += [up, up - (25.0 if k < 10 else 6.0)]
    px.append(px[-1] + 40.0)
    lg, piv = _leg(px, mirror, gap=3)
    c = DS.leg_check(lg, piv, [], 10 ** 6, max_points=15)
    full = [[lg["from"], lg["p0"]]] + [[q.bar, q.price] for q in piv] + [[lg["to"], lg["p1"]]]
    assert c["n"] == len(full) - 1 and 3 <= len(c["path"]) <= 15
    assert c["path"][0] == full[0] and c["path"][-1] == full[-1] and all(p in full for p in c["path"])
    i0 = full[len(full) // 2][0]                                           # window starts mid-leg ⇒ in-window part coarsened on its own
    wp = CH.leg_window_path({**lg, **c}, i0, 15)
    assert len(wp) <= 15 and wp[-1] == full[-1] and all(p in full for p in wp) and wp[1][0] >= i0 > wp[0][0]
    assert sum(1 for b, _ in wp if b >= i0) > sum(1 for b, _ in c["path"] if b >= i0)   # more detail where it is drawn


@pytest.mark.parametrize("mirror", MIRRORS)
def test_trend_legs_never_drawn_grey(mirror):
    pts = HEAD + WAVE4 + WAVE5
    d = _mirror_path(pts) if mirror else path(pts)
    v = DS.build(d, window=len(d), with_elliott=False)
    imp = v["q15"]["objects"]["impulses"]
    assert {x["style"] for x in imp} <= {"impulse", "unconfirmed"} and any(not x["verified"] for x in imp)
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    legend = {t.get_text() for t in info["ax"].get_legend().get_texts()}
    assert "trend leg" in legend and not any("3-wave" in t or "not verified" in t for t in legend)   # CD14: neutral name


@pytest.mark.parametrize("mirror", MIRRORS)
def test_unparsed_leg_is_unclear_not_three_wave(mirror):
    """read_counter "3-wave" is its fallback when it cannot parse the pivots: unparsed ≠ corrective ⇒ dashed, not grey."""
    lg, piv = _leg(NINE, mirror)
    assert DL.read_counter([lg["p0"]] + [q.price for q in piv] + [lg["p1"]]) == {"family": "3-wave", "n": 9}
    c = DS.leg_check(lg, piv, [], 100)
    assert c["family"] == "3-wave" and c["n"] == 9 and not c["verified"] and c["style"] == "unconfirmed" and c["state"] == "done"
    lg, piv = _leg(THREE, mirror)
    assert DS.leg_check(lg, piv, [], 100)["style"] == "unconfirmed"         # structure-only ⇒ never drawn as corrective
    one = {"dir": 1 if not mirror else -1, "from": 0, "to": 5, "p0": 100.0, "p1": 120.0}
    assert DS.leg_check(one, [], [], 100)["style"] == "unconfirmed"        # single (no inner pivots) ⇒ unclear


@pytest.mark.parametrize("mirror", MIRRORS)
def test_leg_check_no_look_ahead(mirror):
    lg, piv = _leg(FIVE, mirror)
    late = DS.leg_check(lg, piv, [], upto=piv[2].confirm_bar - 1)          # 3rd inner pivot not yet confirmed at the drawn bar
    assert not late["verified"] and len(late["path"]) < len(FIVE)
    assert all(b != piv[2].bar for b, _ in late["path"])


@pytest.mark.parametrize("mirror", MIRRORS)
def test_chart_legs_follow_pivots_and_styles(mirror):
    pts = HEAD + WAVE4 + WAVE5
    d = _mirror_path(pts) if mirror else path(pts)
    v = DS.build(d, window=len(d), with_elliott=False)
    legs = DS.view_spec(v)["impulses"]
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    ax, i0 = info["ax"], v["i0"]
    gid = {"impulse": "impulse leg", "unconfirmed": "trend leg"}            # CD14: no accepted reading in synthetic fixtures
    lines = [ln for ln in ax.lines if ln.get_gid() in gid.values()]
    assert len(lines) == len(legs)
    for ln, lg in zip(lines, legs):
        assert ln.get_gid() == gid[lg["style"]]
        wp = CH.leg_window_path(lg, i0, S3.DEFAULTS["chart_leg_path_points"])
        xs, ys = CH._clip_path(wp, i0)
        assert list(ln.get_xdata()) == xs and list(ln.get_ydata()) == ys   # zig-zag through the leg's own pivots
        assert all(p in lg["pivots"] for p in wp) and len(wp) <= S3.DEFAULTS["chart_leg_path_points"]
        assert len(lg["path"]) >= 2 and (lg["style"] != "impulse" or lg["verified"])
        if lg["style"] == "unconfirmed":
            assert ln.get_linestyle() == "--"
    assert not any(ln.get_gid() == "impulse leg" for ln, lg in zip(lines, legs) if not lg["verified"])


@pytest.mark.parametrize("mirror", MIRRORS)
def test_unverified_new_leg_is_dashed_and_caption_never_claims_impulse(mirror):
    """CD14: an unverified, non-accepted running leg — default chart / caption say "new decline in progress" (no impulse claim, no
    "not verified" clutter); the debug wording keeps the structure / anatomy votes."""
    from tests.test_decision3_abc_fix import _bn_points
    d = F.ohlc(_bn_points()[:-3], mirror)
    v = DS.build(d, window=len(d), with_elliott=False)
    q = v["q15"]
    move = "advance" if mirror else "decline"
    ln = q["leg_now"]
    assert q["trend"] == ("UP" if mirror else "DOWN") and ln["state"] == "in progress" and not ln["verified"] and not ln["accepted"]
    line = DS.trend_line(q)
    assert f"new {move} in progress" in line and "new impulse" not in line and "not verified" not in line
    dbg = DS.trend_line(q, debug=True)
    assert f"new {move} in progress (impulse not verified (structure vote: {ln['family']}, n {ln['n']}; anatomy vote: not run))" in dbg
    cap = DS.caption(v, "TEST").splitlines()
    assert f"new {move} in progress" in cap[0] and "new impulse" not in "\n".join(cap) and "not verified" not in "\n".join(cap)
    fig, info, _ = _texts(CH.daily_swings_fig(v, "TEST"))
    assert "new impulse" not in info["ax"].get_title() and "not verified" not in info["ax"].get_title()
    cur = [ln for ln in info["ax"].lines if ln.get_gid() == "trend leg"]
    assert cur and cur[-1].get_linestyle() == "--"
    assert any(x["kind"] == "leg" and x["text"] == f"{move} in progress" for x in info["labels"])


# ------------------------------------------------------------------------------------------------ §5.8 Vision consistency
GOOD = {"verdict": "partly_agree", "issues": ["3-wave rally called a trend flip"], "missing_or_clutter": "",
        "sections": {"zones": {"status": "ok", "reason": "bands at reactions"}, "structure": {"status": "warn", "reason": "x"},
                     "pullback_trigger": {"status": "na", "reason": ""}, "entry_sl_target": {"status": "na", "reason": ""}},
        "consistency": {"status": "inconsistent", "reason": "3-wave counter-move labelled as a trend flip"}}


def test_daily_prompt_asks_structure_consistency():
    p = VA.DAILY_SYSTEM_PROMPT
    assert "consistency" in p and "3-wave" in p and "inconsistent" in p
    assert "consistency" in VA.DAILY_SCHEMA["required"] and "consistency" not in VA.SCHEMA["required"]
    req = VA.build_request(b"png", "facts", "m", system=p, schema=VA.DAILY_SCHEMA)
    assert req["output_config"]["format"]["schema"] is VA.DAILY_SCHEMA


def test_validate_and_report_consistency():
    data, err = VA.validate(GOOD)
    assert err is None and data["consistency"]["status"] == "inconsistent"
    assert VA.validate({**GOOD, "consistency": {"status": "maybe", "reason": ""}})[1] == "invalid consistency status"
    a = {"status": "done", **data, "cost_usd": 0.0}
    assert "structure inconsistent" in VA.caption_line(a)
    assert "Consistency: ❌" in VA.report_text(a, "T")
    ok = {**a, "verdict": "agree", "consistency": {"status": "consistent", "reason": "caption matches"},
          "sections": {**a["sections"], "structure": {"status": "ok", "reason": "x"}}}
    assert VA.caption_line(ok) == "Vision audit: pass" and "Consistency: ✅" in VA.report_text(ok, "T")
    no = {k: v for k, v in GOOD.items() if k != "consistency"}
    assert "consistency" not in VA.validate(no)[0]                          # 1H / 15M charts: unchanged


def test_daily_facts_carry_caption_trend_and_drawn_structure():
    v = _fixture(False)
    js = DS.to_json(v, "TEST")
    js["caption"] = DS.caption(v, "TEST")
    f = VA.facts_text("v22_daily_swings", js)
    assert "Caption (trend claim): TEST Daily:" in f and "Latest correction drawn:" in f
    assert f"corrections bracketed: {js['chart']['boxes_drawn']}" in f and js["chart"]["labels"] == DS.view_spec(v)["tags"]
    assert "never report them as missing" in VA.DAILY_SYSTEM_PROMPT       # older boxes omitted by design


def test_two_year_facts_say_older_boxes_omitted():
    v = _long(False)
    js = DS.to_json(v, "TEST")
    f = VA.facts_text("v22_daily_swings", js)
    assert js["chart"]["boxes_drawn"] < len(js["objects"]["corrections"]) and "omitted / faint by design" in f


# ------------------------------------------------------------------------------------------------ CD14: Abhi-accepted readings
def _day(v, bar):
    return str(v["frame"]["timestamp"].iloc[int(bar)].date())


def _acc(v, lg, shift_from=0, shift_to=0, direction=None, symbol="TEST"):
    """Accepted record built from the drawn leg's own pivot dates (± sessions shift)."""
    return {"symbol": symbol, "timeframe": "1D", "from": _day(v, lg["from"] + shift_from), "to": _day(v, lg["to"] + shift_to),
            "reading": "impulse", "direction": direction or ("up" if lg["dir"] > 0 else "down"), "source": "test"}


def _done_unverified(v):
    return next(x for x in v["q15"]["objects"]["impulses"] if not x["verified"] and x["state"] == "done" and x["n"] > 1)


def _default_texts(v, fig_info):
    """Every word the default chart and the Telegram caption carry: title, axes texts, legend, labels, caption."""
    fig, info, _ = _texts(fig_info)
    ax = info["ax"]
    out = [ax.get_title()] + [t.get_text() for t in ax.texts] + [t.get_text() for t in ax.get_legend().get_texts()]
    out += [x["text"] for x in info["labels"]] + DS.caption(v, "TEST").splitlines()
    return out


def _head(mirror, accepted=None):
    pts = HEAD + WAVE4 + WAVE5
    d = _mirror_path(pts) if mirror else path(pts)
    return DS.build(d, window=len(d), with_elliott=False, accepted=accepted)


def _line_of(ax, lg, i0):
    xs, ys = CH._clip_path(CH.leg_window_path(lg, i0, S3.DEFAULTS["chart_leg_path_points"]), i0)
    return next(ln for ln in ax.lines if ln.get_gid() in ("impulse leg", "trend leg") and list(ln.get_xdata()) == xs
                and list(ln.get_ydata()) == ys)


@pytest.mark.parametrize("mirror", MIRRORS)
def test_accepted_leg_is_solid_impulse_and_default_has_no_not_verified_text(mirror):
    v0 = _head(mirror)
    lg0 = _done_unverified(v0)
    assert DS.drawn_as(lg0) == "trend leg" and lg0["accepted"] is None
    v = _head(mirror, accepted=[_acc(v0, lg0)])
    imp = v["q15"]["objects"]["impulses"]
    lg = next(x for x in imp if (x["from"], x["to"]) == (lg0["from"], lg0["to"]))
    assert lg["accepted"]["source"] == "test" and lg["drawn_as"] == "impulse" and not lg["verified"]   # structure vote unchanged
    assert sum(1 for x in imp if x["accepted"]) == 1
    fig, info = CH.daily_swings_fig(v, "TEST")
    line = _line_of(info["ax"], lg, v["i0"])
    assert line.get_gid() == "impulse leg" and line.get_linestyle() == "-"
    texts = _default_texts(v, (fig, info))
    assert not any("not verified" in t for t in texts), [t for t in texts if "not verified" in t]
    assert "impulse" in {t.get_text() for t in info["ax"].get_legend().get_texts()}
    js = DS.to_json(v, "TEST")                                              # JSON keeps the full detail
    jl = next(x for x in js["objects"]["impulses"] if x["accepted"])
    assert jl["check"].startswith(f"impulse not verified (structure vote: {lg['family']}, n {lg['n']}; anatomy vote: not run)")
    assert "accepted by Abhi as impulse" in jl["check"] and jl["drawn_as"] == "impulse"
    js["caption"] = DS.caption(v, "TEST")
    f = VA.facts_text("v22_daily_swings", js)                               # Vision facts describe what the default chart shows
    assert "not verified" not in f and f"{jl['from_day']}..{jl['to_day']} impulse (owner-accepted reading)" in f
    assert "dashed = trend leg" in f and "not verified" not in VA.DAILY_SYSTEM_PROMPT


@pytest.mark.parametrize("mirror", MIRRORS)
def test_unaccepted_unverified_leg_is_dashed_trend_leg_with_neutral_legend(mirror):
    v = _head(mirror)
    lg = _done_unverified(v)
    fig, info = CH.daily_swings_fig(v, "TEST")
    ax = info["ax"]
    line = _line_of(ax, lg, v["i0"])
    imp = next(ln for ln in ax.lines if ln.get_gid() == "impulse leg")      # the verified running leg
    assert line.get_gid() == "trend leg" and line.get_linestyle() == "--" and line.get_linewidth() < imp.get_linewidth()
    legend = {t.get_text() for t in ax.get_legend().get_texts()}
    assert {"trend leg", "impulse"} <= legend and not any("not verified" in t for t in _default_texts(v, (fig, info)))
    assert not any(x["accepted"] for x in v["q15"]["objects"]["impulses"])


@pytest.mark.parametrize("mirror", MIRRORS)
def test_accepted_match_by_pivot_dates_within_pivot_slack_only(mirror):
    v0 = _head(mirror)
    lg0 = _done_unverified(v0)
    n = int(S3.DEFAULTS["daily_pivot_n"])

    def hit(rec):
        return any(x["accepted"] for x in _head(mirror, accepted=[rec])["q15"]["objects"]["impulses"])
    assert hit(_acc(v0, lg0, shift_from=n, shift_to=-n))                    # same pivot ± confirmation window
    assert not hit(_acc(v0, lg0, shift_from=n + 1))                         # a different bar ⇒ no match
    assert not hit(_acc(v0, lg0, shift_to=n + 1))
    assert not hit(_acc(v0, lg0, direction="up" if lg0["dir"] < 0 else "down"))   # direction must agree
    d = _mirror_path(HEAD + WAVE4 + WAVE5) if mirror else path(HEAD + WAVE4 + WAVE5)
    v = DS.build(d, window=len(d), with_elliott=False, symbol="TEST", accepted=[_acc(v0, lg0, symbol="OTHER")])
    assert not any(x["accepted"] for x in v["q15"]["objects"]["impulses"])  # another symbol's record never matches
    v = DS.build(d, window=len(d), with_elliott=False)                      # no symbol, no records ⇒ nothing accepted
    assert not any(x["accepted"] for x in v["q15"]["objects"]["impulses"])


@pytest.mark.parametrize("mirror", MIRRORS)
def test_accepted_running_leg_reads_impulse_in_title_caption_and_label(mirror):
    from tests.test_decision3_abc_fix import _bn_points
    d = F.ohlc(_bn_points()[:-3], mirror)
    v0 = DS.build(d, window=len(d), with_elliott=False)
    cur = v0["q15"]["objects"]["impulses"][-1]
    assert cur["state"] == "in progress" and not cur["verified"]
    v = DS.build(d, window=len(d), with_elliott=False, accepted=[_acc(v0, cur)])
    q = v["q15"]
    assert q["leg_now"]["accepted"] and not DS.unverified(q)
    assert f"new impulse {('UP' if mirror else 'DOWN').lower()} in progress" in DS.trend_line(q)
    fig, info = CH.daily_swings_fig(v, "TEST")
    assert any(x["kind"] == "leg" and x["text"] == "impulse" for x in info["labels"])
    assert not any("not verified" in x for x in _default_texts(v, (fig, info)))
    dbg = DS.trend_line(q, debug=True)                                      # debug keeps the votes + "accepted by Abhi"
    assert "impulse not verified (structure vote:" in dbg and "accepted by Abhi as impulse" in dbg


@pytest.mark.parametrize("mirror", MIRRORS)
def test_debug_view_keeps_full_verification_detail(mirror, monkeypatch):
    v0 = _head(mirror)
    lg0 = _done_unverified(v0)
    v = _head(mirror, accepted=[_acc(v0, lg0)])
    figs = []
    monkeypatch.setattr(CH, "_png", lambda fig: figs.append(fig) or b"png")
    assert CH.daily_swings_debug_png(v, "TEST") == b"png"
    txt = [t.get_text() for t in figs[0].axes[0].texts]
    acc = [x for x in txt if "accepted by Abhi" in x]
    assert len(acc) == 1 and acc[0].startswith(f"impulse not verified (structure vote: {lg0['family']}, n {lg0['n']}; anatomy vote:")
    assert any(x.startswith("impulse (5 waves; structure vote: impulse") for x in txt)
    from tests.test_decision3_abc_fix import _bn_points                    # running unverified leg: debug title carries the votes
    d = F.ohlc(_bn_points()[:-3], mirror)
    vb = DS.build(d, window=len(d), with_elliott=False)
    CH.daily_swings_debug_png(vb, "TEST")
    assert "impulse not verified (structure vote:" in figs[-1].axes[0].get_title()
    _, info = CH.daily_swings_fig(vb, "TEST", full=True)                    # full (debug) variant of the default chart
    assert "impulse not verified" in info["ax"].get_title()


def test_accepted_legs_loader_validates(tmp_path, monkeypatch):
    import json
    from decision3 import accepted_legs as AL
    good = {"symbol": "bn", "timeframe": "1D", "from": "2020-01-02", "to": "2020-02-03", "reading": "impulse", "direction": "down",
            "source": "test"}
    assert AL.validate(good)["symbol"] == "BN" and AL.validate(good)["dir"] == -1
    for bad in ({**good, "direction": "sideways"}, {**good, "reading": "zigzag"}, {**good, "timeframe": "1H"},
                {**good, "to": good["from"]}, {**good, "source": " "}, {k: x for k, x in good.items() if k != "source"},
                {**good, "from": "not a date"}):
        with pytest.raises(ValueError):
            AL.validate(bad)
    p = tmp_path / "acc.json"
    p.write_text(json.dumps({"legs": [good, {**good, "from": "2020-01-20", "to": "2020-03-01"}]}))
    with pytest.raises(ValueError, match="overlapping"):
        AL.load(str(p))
    p.write_text(json.dumps({"legs": [good]}))
    monkeypatch.setenv(AL.ENV, str(p))
    assert [x["symbol"] for x in AL.load(symbol="BN")] == ["BN"] and AL.load(symbol="OTHER") == []
    assert AL.load(str(tmp_path / "missing.json")) == []
    monkeypatch.delenv(AL.ENV)
    shipped = AL.load()                                                     # the repo file itself is valid
    assert shipped and all(x["reading"] == "impulse" for x in shipped)


BN_DAILY = "/home/user/trade-data/banknifty/BANKNIFTY_D.csv.gz"


def test_banknifty_accepted_leg_real_data():
    """CD14 on real data (skipped without the private trade-data file): the owner-accepted BANKNIFTY leg is matched on its own pivot
    dates and drawn solid; the default chart and caption carry no "not verified" text; the debug detail keeps the structure vote."""
    import os
    if not os.path.exists(BN_DAILY):
        pytest.skip("private BANKNIFTY daily data not available")
    from decision3 import accepted_legs as AL
    from decision3 import history as HI
    recs = AL.load(symbol="BANKNIFTY")
    if not recs:
        pytest.skip("no accepted BANKNIFTY record")
    d = HI.load_daily([BN_DAILY], prepare=DS.prepare)
    v = DS.build(d, window=500, with_elliott=False, symbol="BANKNIFTY")
    acc = [x for x in v["q15"]["objects"]["impulses"] if x["accepted"]]
    assert len(acc) == len([r for r in recs if r["to"] <= d["timestamp"].iloc[-1]]) >= 1
    for lg in acc:
        assert lg["drawn_as"] == "impulse" and "accepted by Abhi" in lg["check"]
        assert lg["dir"] == AL.DIRECTIONS[lg["accepted"]["direction"]]
    fig, info = CH.daily_swings_fig(v, "BANKNIFTY")
    assert not any("not verified" in t for t in _default_texts(v, (fig, info)))
    for lg in acc:
        if lg["to"] >= v["i0"]:
            assert _line_of(info["ax"], lg, v["i0"]).get_gid() == "impulse leg"
