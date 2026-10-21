"""PA standard §2L (track T7) — range edges as AREAS (decision3/range_edges.py), synthetic.

  • when the Daily state is RANGE (decision3.daily, unchanged) the two edges are areas built from the equal swing candles (wick to body,
    the extreme swing's own candle — never the numeric band), upper = resistance / bear call, lower = support / bull put;
  • a later equal swing (third touch) joins the edge's members; the area is not widened;
  • lifecycle = the levels' own K4 machine: fresh → tested → broken (close beyond + swing beyond) → flipped (far swing reached);
  • a breakout of the range is context only (no trade location, no armable edge);
  • entries carry every `Levels.snapshot` key; no look-ahead (truncation invariant); 1H / 15M rectangle hook.
"""
import os
import re
from types import SimpleNamespace as NS

import pandas as pd

from decision3 import daily as DD
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import range_edges as RE
from tests.test_decision3 import P, daily_from_path, res_of

S = {"daily_min_sessions": 3, "daily_sigma_sessions": 3}
RANGE_PATH = [100, 120, 110, 119.8, 110.3, 119.9, 110.2, 115]               # flat from the start ⇒ Daily RANGE (C-13 equal H / L)
BREAK_UP = RANGE_PATH + [130, 124, 135]
PER_DAY = 4


def expand(d):
    """Daily candles ⇒ PER_DAY 15M bars each (o → low → high → close for an up day, mirror for a down day) whose Daily aggregate is the
    same candle; Daily bar_end = its last 15M bar_end."""
    rows = []
    for _, r in d.iterrows():
        o, h, l, c = r.open, r.high, r.low, r.close
        seq = [o, l, h, c, c] if c >= o else [o, h, l, c, c]
        t0 = pd.Timestamp(r.timestamp) + pd.Timedelta(hours=9, minutes=15)
        for k in range(PER_DAY):
            a, b = seq[k], seq[k + 1]
            ts = t0 + pd.Timedelta(minutes=15 * k)
            rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": a, "close": b, "high": max(a, b),
                         "low": min(a, b)})
    m = pd.DataFrame(rows)
    d = d.copy()
    d["bar_end"] = m.groupby(m["timestamp"].dt.normalize())["bar_end"].max().values
    return m, d


def build(path, piv2=(), piv1=(), days=None, s=None, wicks=()):
    d = daily_from_path(path)
    m, d = expand(d)
    for j, kind in wicks:                                                  # give 15M bar j a wick at its swing extreme (high / low unchanged)
        ext = m.at[j, "high"] if kind == "H" else m.at[j, "low"]
        col = "close" if m.at[j, "close"] == ext else "open"
        m.at[j, col] = ext - 0.4 if kind == "H" else ext + 0.4
    if days is not None:
        d, m = d.iloc[:days].reset_index(drop=True), m.iloc[:days * PER_DAY].reset_index(drop=True)
    s = {**S, **(s or {})}
    st = DD.fold(d, s)
    lv = LV.Levels(res_of(m, list(piv2), list(piv1)), st, d, s)
    return NS(levels=lv, daily=st, daily_df=d, weekly=None, weekly_df=None, m15=m), m, d


def first_range(V):
    return next(x for x in V.daily if x.trend == "RANGE")


def edges_by(r):
    return {e["range_edge"]: e for e in r["edges"]}


# ------------------------------------------------------------------------------------------------ edges = areas
def test_range_edges_are_swing_candle_areas_not_the_band():
    V, m, d = build(RANGE_PATH)
    t = len(m) - 1
    st = DD.state_at(V.daily, V.levels.bar_end.iloc[t])
    assert st.trend == "RANGE"
    r = RE.read_range_edges(V, t)
    e = edges_by(r)
    assert set(e) == {"lower", "upper"}
    up, lo = e["upper"], e["lower"]
    assert up["role"] == LV.RES and up["trade_side"] == "bear_call"
    assert lo["role"] == LV.SUP and lo["trade_side"] == "bull_put"
    # the upper area = the extreme swing high candle's own area [body top, high]; the lower = [low, body bottom]
    ah = next(x for x in up["members"] if x["relation"] == "anchor")
    row = d.iloc[ah["bar"]]
    assert (up["lo"], up["hi"]) == (round(max(row.open, row.close), 2), round(row.high, 2))
    al = next(x for x in lo["members"] if x["relation"] == "anchor")
    row = d.iloc[al["bar"]]
    assert (lo["lo"], lo["hi"]) == (round(row.low, 2), round(min(row.open, row.close), 2))
    # the band's extremes are the anchors, but the areas are not the band (never one numeric span)
    assert up["hi"] == st.band[1] and lo["lo"] == st.band[0]
    assert up["lo"] > lo["hi"]
    assert (lo["lo"], up["hi"]) != (lo["lo"], lo["hi"]) and up["width"] < st.band[1] - st.band[0]


def test_members_are_the_equal_swings_and_a_third_touch_joins_without_widening():
    V, m, d = build(RANGE_PATH)
    t = len(m) - 1
    up = edges_by(RE.read_range_edges(V, t))["upper"]
    assert len(up["members"]) >= 2
    a = next(x for x in up["members"] if x["relation"] == "anchor")
    for x in up["members"]:
        assert x["price"] <= a["price"]                                    # C-13 equal: never beyond the anchor
        assert x["relation"] in ("anchor", "inside", "overlaps")
    # the area stays the anchor candle's area whatever the members
    assert (up["lo"], up["hi"]) == a["area"]
    # at the bar the range is first known, the third swing (confirmed later) is not a member yet (no look-ahead)
    t0 = up["range"]["known_bar"]
    early = edges_by(RE.read_range_edges(V, t0))["upper"]
    assert len(early["members"]) <= len(up["members"])


def test_snapshot_key_compatibility_and_d_filter():
    V, m, d = build(RANGE_PATH)
    t = len(m) - 1
    snap = V.levels.snapshot(t)
    assert snap, "the Daily swings are levels too"
    r = RE.read_range_edges(V, t)
    for e in r["edges"]:
        assert set(snap[0]) <= set(e), set(snap[0]) - set(e)
        assert e["tf"] == "D" and RE.BIRTH in e["births"]
    assert [e["range_edge"] for e in RE.read_range_edges(V, t, d=1)["edges"]] == ["lower"]
    assert [e["range_edge"] for e in RE.read_range_edges(V, t, d=-1)["edges"]] == ["upper"]
    # the matching Daily level (same swing candle band) is named — lineage, not a second zone
    up = edges_by(r)["upper"]
    assert up["same_level"] is not None


def test_no_range_no_edges():
    V, m, d = build([100, 120, 110, 130, 118, 140])                       # UP trend
    r = RE.read_range_edges(V, len(m) - 1)
    assert r["edges"] == [] and r["by_tf"]["D"]["state"] == "no_range" and RE.armable(V, len(m) - 1) == []
    assert RE.draw_objects(V, len(m) - 1) == []


def test_before_the_range_is_known_nothing():
    V, m, d = build(RANGE_PATH)
    known = RE._first_bar(V.levels, first_range(V).known_at)
    assert RE.read_range_edges(V, known - 1)["edges"] == []
    assert len(RE.read_range_edges(V, known)["edges"]) == 2


# ------------------------------------------------------------------------------------------------ lifecycle
def test_fresh_then_tested():
    V, m, d = build(RANGE_PATH)
    known = RE._first_bar(V.levels, first_range(V).known_at)
    e0 = edges_by(RE.read_range_edges(V, known))
    assert all(x["lifecycle"] == "fresh" and x["fresh"] for x in e0.values())
    e1 = edges_by(RE.read_range_edges(V, len(m) - 1))
    assert any(x["lifecycle"] == "tested" and x["tests"] >= 1 for x in e1.values())
    assert all(x["trade_location"] for x in e1.values()) or any(x["inside_1h"] for x in e1.values())


def _scenario_break(piv_kind):
    """The range, then a rally through the upper edge. piv_kind: "broken" ⇒ only a finer (D1) swing high forms beyond the edge (no
    far-side D2 swing yet ⇒ BROKEN); "flipped" ⇒ a D2 swing high forms beyond it and is confirmed (first swing after the break, Z-1s)."""
    V0, m, d = build(BREAK_UP)
    known = RE._first_bar(V0.levels, first_range(V0).known_at)
    hi = edges_by(RE.read_range_edges(V0, known))["upper"]["hi"]
    C, H = m["close"].to_numpy(), m["high"].to_numpy()
    b0 = next(i for i in range(known + 1, len(m)) if C[i] > hi)          # first close beyond the upper edge
    top = max(range(b0, len(m)), key=lambda i: (H[i], -i))
    peak = max(range(b0, top), key=lambda i: H[i]) if top > b0 + 2 else top
    sw = P("H", float(H[peak]), peak, peak + 2)
    piv1 = [sw]
    piv2 = [sw] if piv_kind == "flipped" else []
    V, m, d = build(BREAK_UP, piv2=piv2, piv1=piv1)
    return V, m, b0, peak + 2


def test_broken_needs_a_close_beyond_and_a_swing_beyond():
    V, m, b0, conf = _scenario_break("broken")
    up = [e for e in RE.read_range_edges(V, conf)["by_tf"]["D"]["edges"] or
          RE.read_range_edges(V, conf)["by_tf"]["D"]["last_range"]["edges"] if e["range_edge"] == "upper"][0]
    assert up["state"] == FL.BROKEN and up["lifecycle"] == "broken" and up["trade_location"] is False
    before = RE.read_range_edges(V, b0 - 1)["by_tf"]["D"]
    upb = [e for e in (before["edges"] or before["last_range"]["edges"]) if e["range_edge"] == "upper"][0]
    assert upb["state"] in (FL.ACTIVE, FL.TESTED)


def test_flipped_when_the_far_side_swing_is_reached():
    V, m, b0, conf = _scenario_break("flipped")
    x = RE.read_range_edges(V, conf)["by_tf"]["D"]
    up = [e for e in (x["edges"] or x["last_range"]["edges"]) if e["range_edge"] == "upper"][0]
    assert up["state"] == FL.FLIPPED and up["lifecycle"] == "flipped"
    assert up["role"] == LV.SUP and up["trade_side"] is None and up["trade_location"] is False
    assert "c" in up["births"]


def test_breakout_is_context_only():
    V, m, d = build(BREAK_UP)
    t = len(m) - 1
    x = RE.read_range_edges(V, t)["by_tf"]["D"]
    assert x["state"] == "no_range" and x["edges"] == []
    b = x["breakout"]
    assert b["dir"] == "up" and b["context_only"] is True and "breakouts" in b["note"]
    assert all(e["trade_location"] is False for e in x["last_range"]["edges"])
    assert RE.armable(V, t) == []
    kinds = [o["kind"] for o in RE.draw_objects(V, t)]
    assert kinds.count("pattern") == 1 and kinds.count("area") == 2


# ------------------------------------------------------------------------------------------------ Z-1u, truncation, hooks
def test_overlapping_1h_zone_is_the_location():
    V0, m, d = build(RANGE_PATH)
    t = len(m) - 1
    up = edges_by(RE.read_range_edges(V0, t))["upper"]
    # a 15M D2 swing high inside the upper edge area ⇒ a 1H zone overlapping it
    H = m["high"].to_numpy()
    k = next(i for i in range(len(m) - 8) if up["lo"] <= H[i] <= up["hi"] and i > 2)
    V, m, d = build(RANGE_PATH, piv2=[P("H", float(H[k]), k, k + 2)])
    e = edges_by(RE.read_range_edges(V, t))["upper"]
    assert e["inside_1h"] and e["trade_location"] is False and "1H" in e["not_location_why"]
    assert e not in RE.armable(V, t)


def test_truncation_invariant():
    V, m, d = build(RANGE_PATH)
    full_days = len(d)
    for days in range(full_days - 4, full_days + 1):
        Vk, mk, dk = build(RANGE_PATH, days=days)
        t = len(mk) - 1
        a = RE.read_range_edges(Vk, t)
        b = RE.read_range_edges(V, t)
        key = lambda r: [(e["range_edge"], e["lo"], e["hi"], e["state"], e["tests"], len(e["members"])) for e in r["edges"]]  # noqa: E731
        assert key(a) == key(b)


def test_rectangle_hook_15m():
    V, m, d = build(RANGE_PATH)
    A = V.levels.A
    # two equal 15M highs / lows taken from the bars themselves (the later reaches the earlier candle's area, not beyond)
    H, L = A["high"], A["low"]
    hs = sorted(range(len(m)), key=lambda i: -H[i])[:1]
    i1 = hs[0]
    i2 = next(i for i in range(i1 + 3, len(m)) if max(A["open"][i1], A["close"][i1]) <= H[i] <= H[i1])
    j1 = int(min(range(len(m)), key=lambda i: L[i]))
    j2 = next(i for i in range(j1 + 3, len(m)) if L[j1] <= L[i] <= min(A["open"][j1], A["close"][j1]))
    rect = {"tf": "15M", "highs": [P("H", H[i1], i1, i1 + 2), P("H", H[i2], i2, i2 + 2)],
            "lows": [P("L", L[j1], j1, j1 + 2), P("L", L[j2], j2, j2 + 2)]}
    t = len(m) - 1
    out = RE.edges_from_rectangle(V, t, rect)
    assert out is not None and {e["range_edge"] for e in out} == {"lower", "upper"}
    assert all(e["tf"] == "15M" for e in out)
    bad = {**rect, "highs": [P("H", H[i1] - 50, i1, i1 + 2), P("H", H[i2], i2, i2 + 2)]}   # later beyond the earlier ⇒ not equal
    assert RE.edges_from_rectangle(V, t, bad) is None


def test_draw_objects_shape():
    V, m, d = build(RANGE_PATH)
    obs = RE.draw_objects(V, len(m) - 1)
    assert len(obs) == 2
    for o in obs:
        assert set(o) == {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "style_key", "evidence"}
        assert o["p0"] < o["p1"] and o["kind"] == "area" and o["style_key"] == "area.range_edge"
        assert o["state"] in ("active", "tested", "broken", "flipped", "dead")


def test_no_dates_or_tuned_numbers_in_module():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "decision3", "range_edges.py"),
               encoding="utf-8").read()
    assert not re.search(r"20\d\d-\d\d-\d\d", src)
    code = "\n".join(line.split("#")[0] for line in src.splitlines() if not line.strip().startswith(("\"", "'")))
    assert not re.search(r"(?<![\w.])\d+\.\d+(?![\w])", code.replace("0.0", "")), "no tuned numbers (width 0.0 only)"


# ------------------------------------------------------------------------------------------------ range state from structure (Abhi 21 Oct)
def _intraday_case(after_break=False):
    """15M D1 swings at the Daily range's own swing days: the 15M bar that made each Daily swing extreme (given a wick there) ⇒ two equal
    highs and two equal lows on 15M candles. after_break ⇒ the same swings on the breakout path, read after the rally."""
    path = BREAK_UP if after_break else RANGE_PATH
    V0, m, d = build(path)
    st = first_range(V0)
    hs = [p for p in st.pivots if p.kind == "H"][-2:]
    ls = [p for p in st.pivots if p.kind == "L"][-2:]
    H, L = m["high"].to_numpy(), m["low"].to_numpy()

    def bar_of(p):
        js = range(p.bar * PER_DAY, (p.bar + 1) * PER_DAY)
        return next(j for j in js if (H[j] if p.kind == "H" else L[j]) == p.price)
    bars = {(p.kind, p.bar): bar_of(p) for p in hs + ls}
    piv1 = sorted([P(k, H[j] if k == "H" else L[j], j, j + 2) for (k, _), j in bars.items()], key=lambda q: q.bar)
    V, m, d = build(path, piv1=piv1, wicks=[(j, k) for (k, _), j in bars.items()])
    return V, m, max(q.confirm_bar for q in piv1)


def test_intraday_range_from_equal_swings_and_breakout_is_context():
    V, m, born = _intraday_case()
    r = RE.read_intraday(V, born, "15M")
    assert r["state"] == "range" and {e["range_edge"] for e in r["edges"]} == {"lower", "upper"}
    assert RE.read_intraday(V, born - 1, "15M")["state"] == "no_range"          # the fourth swing not confirmed yet
    s = RE.range_state(V, born)
    assert s["by_tf"]["15M"]["state"] == "range" and s["in_range"] and s["rule"] == "structure"
    assert s["tf"] == "15M"                                                     # the Daily RANGE is not known yet at that bar
    s2 = RE.range_state(V, len(m) - 1)
    assert s2["tf"] == "D" and s2["tfs_in_range"] == ["D", "15M"]                 # later: the higher timeframe first
    Vb, mb, born_b = _intraday_case(after_break=True)
    last = len(mb) - 1
    rb = RE.read_intraday(Vb, last, "15M")
    assert rb["state"] == "no_range" and rb["breakout"]["dir"] == "up" and rb["breakout"]["context_only"]
    assert all(e["trade_location"] is False for e in rb["last_range"]["edges"])


def test_range_state_has_no_overlap_ratio_or_candle_count():
    import inspect
    src = inspect.getsource(RE.range_state) + inspect.getsource(RE.read_intraday)
    for key in ("range_overlap_min", "range_state_n", "doji", "rhea", "sigma"):
        assert key not in src


def test_engine_range_state_rule_default_is_today_and_structure_wires_the_row():
    import warnings
    from decision3 import engine as E3
    from decision3 import settings as S3
    assert S3.DEFAULTS["range_state_rule"] == "overlap" and "range_state_rule" in S3.REGISTER
    assert S3.REGISTER["range_state_rule"][2] == "Abhi नियम"
    d = daily_from_path(RANGE_PATH)
    m, d = expand(d)
    t = len(m) - 1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        V0 = E3.V22(m, daily_df=d, s=S)
        V1 = E3.V22(m, daily_df=d, s={**S, "range_state_rule": "structure"})
    r0, r1 = V0.decide(t), V1.decide(t)
    assert r0["range_state"] is None                                           # today (verdict_rule = method): not read
    rs = r1["range_state"]
    assert rs["rule"] == "structure" and rs["tf"] == "D" and {e["range_edge"] for e in rs["edges"]} == {"lower", "upper"}
    assert {k: r0[k] for k in ("decision", "checklist")} == {k: r1[k] for k in ("decision", "checklist")}   # evidence only
    try:
        E3.V22(m, daily_df=d, s={**S, "range_state_rule": "x"}).decide(t)
        raise AssertionError("unknown rule accepted")
    except ValueError:
        pass
