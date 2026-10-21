"""PA standard §2J (J.2) — decision3.rsi_hidden: hidden RSI divergence as continuation evidence, read in the regular divergence's frame
(Abhi L5-a: consecutive pushes inside the move, highest degree with two pushes). Synthetic (always run) + a real-data smoke read (private
trade-data; skipped cleanly when absent — values are REPORTED, never asserted)."""
import glob
import json
import os
import re
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import rsi_hidden as RH
from rsi2 import engine as RE
from rsi2 import settings as RS
from tests.test_rsi_divergence import build, frame, piv, res_of, rsi_with
from tests.test_pivots_dc import m15_from, walk

TD = os.environ.get("TRADE_DATA", "/home/user/trade-data")


def V_of(D, df, pb=None):
    return NS(_rsi_hidden=D, _ts=pd.to_datetime(df["timestamp"]).to_numpy(), pb=pb)


def bull_hidden(l2=97.0, r1=35.0, r2=30.0, n=40, after=None):
    """Uptrend pullback (move from the swing high at 5): L 95 @ 10 · H 105 @ 15 · L l2 @ 25; RSI r1 @ 10, r2 @ 25."""
    lows = {10: 95.0, 25: l2, **(after or {})}
    df = frame(n, highs={5: 110.0, 15: 105.0}, lows=lows)
    ps = [piv(df, "H", 5), piv(df, "L", 10), piv(df, "H", 15), piv(df, "L", 25)]
    return df, ps, rsi_with(n, {10: r1, 25: r2})


def bear_hidden(h2=106.0, r1=65.0, r2=70.0, n=40):
    """Mirror — downtrend pullback (move from the swing low at 5): H 110 @ 10 · L 95 @ 15 · H h2 @ 25; RSI r1 @ 10, r2 @ 25."""
    df = frame(n, highs={10: 110.0, 25: h2}, lows={5: 90.0, 15: 95.0})
    ps = [piv(df, "L", 5), piv(df, "H", 10), piv(df, "L", 15), piv(df, "H", 25)]
    return df, ps, rsi_with(n, {10: r1, 25: r2})


def hid(df, ps, r, **s):
    return build(df, ps, r, div_hidden=True, **s)


# ------------------------------------------------------------------------------------------------ the definition (mirror)
def test_uptrend_pullback_higher_low_with_rsi_lower_low_is_hidden_bull():
    df, ps, r = bull_hidden()
    got = RH.read_hidden_divergence(V_of(hid(df, ps, r), df), 30, +1, move_from=5)
    assert got["found"] is True and got["side"] == "bull" and got["degree"] == 0 and got["pushes"][0] == 2
    (x,) = got["divergences"]
    assert (x["L1"]["price"], x["L2"]["price"], x["price_rel"]) == (95.0, 97.0, "higher low")
    assert (x["L1"]["rsi"], x["L2"]["rsi"], x["rsi_diff"]) == (35.0, 30.0, -5.0) and x["status"] == "confirmed"
    assert got["frame"]["kind"] == "zone_move" and got["frame"]["move_from"] == 5
    assert "continuation" in got["statements"][0] and "never a gate" in got["role"]


def test_downtrend_pullback_lower_high_with_rsi_higher_high_is_hidden_bear():
    df, ps, r = bear_hidden()
    got = RH.read_hidden_divergence(V_of(hid(df, ps, r), df), 30, -1, move_from=5)
    assert got["found"] is True and got["side"] == "bear"
    (x,) = got["divergences"]
    assert x["price_rel"] == "lower high" and (x["L1"]["rsi"], x["L2"]["rsi"]) == (65.0, 70.0)


def test_regular_shape_and_rsi_with_price_are_not_hidden():
    df, ps, r = bull_hidden(l2=93.0, r1=30.0, r2=35.0)                  # lower low + higher RSI = regular, not hidden
    assert RH.read_hidden_divergence(V_of(hid(df, ps, r), df), 30, +1, move_from=5)["found"] is False
    df, ps, r = bull_hidden(r1=30.0, r2=35.0)                            # higher low with a higher RSI low = no divergence
    assert RH.read_hidden_divergence(V_of(hid(df, ps, r), df), 30, +1, move_from=5)["found"] is False


def test_equal_low_is_a_double_bottom_not_hidden():
    df, ps, r = bull_hidden(l2=95.0)
    D = hid(df, ps, r)
    assert any(x["type"] == "hidden" and x["price_rel"] == "equal low" for x in D.history(30))   # rsi2 marks it hidden …
    assert RH.read_hidden_divergence(V_of(D, df), 30, +1, move_from=5)["found"] is False       # … the method words say "higher low"


# ------------------------------------------------------------------------------------------------ the frame (Abhi L5-a)
def test_a_swing_from_before_the_move_is_never_compared():
    df, ps, r = bull_hidden()
    got = RH.read_hidden_divergence(V_of(hid(df, ps, r), df), 30, +1, move_from=12)   # the move starts after the low at 10
    assert got["found"] is False and got["degree"] is None and got["pushes"][0] == 1
    assert "fewer than two pushes" in got["statements"][0]


def test_highest_degree_with_two_pushes_is_read():
    """D1 shows two lows inside the move (10, 25) with no RSI divergence between them; D0 adds 18 ⇒ D1 is the highest with two and is
    the one read (a D0 hidden pair 18 → 25 is not this frame's evidence)."""
    n = 40
    df = frame(n, highs={5: 110.0, 15: 105.0, 21: 104.0}, lows={10: 95.0, 18: 98.0, 25: 97.0})
    r = rsi_with(n, {10: 30.0, 18: 40.0, 25: 32.0})                     # D1 95 → 97 RSI 30 → 32 (none); D0 98 → 97 is a lower low
    ps = [piv(df, "H", 5, degree=1), piv(df, "L", 10, degree=1), piv(df, "H", 15, degree=1), piv(df, "L", 25, degree=1),
          piv(df, "H", 5), piv(df, "L", 10), piv(df, "H", 15), piv(df, "L", 18), piv(df, "H", 21), piv(df, "L", 25)]
    got = RH.read_hidden_divergence(V_of(hid(df, ps, r, div_degrees=(0, 1, 2)), df), 30, +1, move_from=5)
    assert got["degree"] == 1 and got["pushes"] == {0: 3, 1: 2, 2: 0} and got["found"] is False
    r2 = rsi_with(n, {10: 35.0, 18: 40.0, 25: 30.0})                    # D1 95 → 97 with RSI 35 → 30 ⇒ hidden at D1
    got = RH.read_hidden_divergence(V_of(hid(df, ps, r2, div_degrees=(0, 1, 2)), df), 30, +1, move_from=5)
    assert got["found"] is True and [x["degree"] for x in got["divergences"]] == [1]


def test_overtaken_when_price_goes_beyond_the_held_low():
    df, ps, r = bull_hidden(n=45, after={35: 96.0})
    D = hid(df, ps, r)
    assert RH.read_hidden_divergence(V_of(D, df), 34, +1, move_from=5)["found"] is True
    got = RH.read_hidden_divergence(V_of(D, df), 36, +1, move_from=5)       # 96 < 97: the higher low is gone
    assert got["found"] is False and len(got["overtaken"]) == 1 and "went beyond" in got["statements"][0]


def test_arm_keeps_only_pairs_whose_second_push_is_inside_the_visit():
    df, ps, r = bull_hidden()
    D = hid(df, ps, r)
    assert RH.read_hidden_divergence(V_of(D, df), 30, +1, move_from=5, arm=20)["found"] is True
    assert RH.read_hidden_divergence(V_of(D, df), 30, +1, move_from=5, arm=26)["found"] is False


def test_decision_row_frame_and_na_when_the_move_is_not_known():
    df, ps, r = bull_hidden()
    V = V_of(hid(df, ps, r), df)
    row = {"trend_used": "UP", "level": {"role": "SUP"}, "commit": {"move_from_bar": 5, "arm_bar": 20}}
    got = RH.read_hidden_divergence(V, 30, row=row)
    assert got["found"] is True and got["d"] == 1 and got["frame"]["arm"] == 20
    na = RH.read_hidden_divergence(V, 30, +1, row={"commit": {}})
    assert na["found"] is None and "not known" in na["na"]


def test_level_frame_uses_the_areas_visit_like_the_confirmation():
    """A row with a level but no commit facts (③ not reached) ⇒ the area's own visit (V.visit): move_from = approach_from − 1."""
    df, ps, r = bull_hidden()
    calls = []

    def visit(t, lvl, d, k0=0):
        calls.append((t, d, k0))
        return {"start": 20, "approach_from": 6} if lvl["id"] == "a" else {"start": None, "approach_from": None, "why": "no visit in progress"}
    V = V_of(hid(df, ps, r), df, pb=NS(at=lambda t, d: {"k_open_bar": 12}))
    V.visit = visit
    got = RH.read_hidden_divergence(V, 30, row={"trend_used": "UP", "level": {"id": "a", "role": "SUP"}, "commit": {}})
    assert got["found"] is True and (got["frame"]["move_from"], got["frame"]["arm"]) == (5, 20) and calls == [(30, 1, 12)]
    na = RH.read_hidden_divergence(V, 30, +1, lvl={"id": "b"})
    assert na["found"] is None and "no visit in progress" in na["na"]


def test_pullback_K_frame_and_both_sides_when_d_is_none():
    df, ps, r = bull_hidden()
    pb = NS(at=lambda t, d: {"i_end_bar": 5, "open": True} if d == 1 else None)
    got = RH.read_hidden_divergence(V_of(hid(df, ps, r), df, pb=pb), 30)
    assert got["bull"]["found"] is True and got["bull"]["frame"]["kind"] == "pullback_K"
    assert got["bear"]["found"] is None and "no trend-side impulse" in got["bear"]["na"]


def test_rsi2_failure_is_na_with_the_reason():
    df, _, _ = bull_hidden()
    got = RH.read_hidden_divergence(NS(_rsi_hidden="ValueError: x", _ts=None), 30, +1, move_from=5)
    assert got["found"] is None and "rsi2 Divergence (hidden on) failed" in got["na"]


# ------------------------------------------------------------------------------------------------ the live reader is untouched
def test_rsi2_defaults_and_regular_records_untouched():
    assert RS.load()["div_hidden"] is False                             # the live reader's default stays off
    df, ps, r = bull_hidden(l2=93.0, r1=30.0, r2=35.0)                  # a regular pair
    off, on = build(df, ps, r), hid(df, ps, r)
    reg = lambda D: [(x["L1"]["bar"], x["L2"]["bar"], x["count"]) for x in D.history(30) if x["type"] == "regular"]   # noqa: E731
    assert reg(off) == reg(on) and reg(on)


def test_hidden_reader_builds_its_own_instance_with_hidden_on():
    df, ps, _ = bull_hidden()
    V = NS(m15=df, res=res_of(df, ps), _rsi="regular reader")
    D = RH.hidden_reader(V)
    assert isinstance(D, RE.Divergence) and D.s["div_hidden"] is True and V._rsi == "regular reader"
    assert RH.hidden_reader(V) is D                                     # cached


def test_engine_and_settings_not_edited_by_this_module():
    src = open(RH.__file__, encoding="utf-8").read()
    assert not re.search(r"\b20\d\d-\d\d", src)                          # no dates in code
    assert "div_hidden\": True" in src and "RS.DEFAULTS" not in src and "_rsi =" not in src


# ------------------------------------------------------------------------------------------------ no look-ahead / output shape
def test_no_lookahead_cut_never_changes_earlier_reads():
    m15 = m15_from(walk(25 * 30, 3, step=3.0))
    full = RE.Divergence(m15, "15M", s={"div_hidden": True}, areas=False)
    n = len(m15)
    seen = 0
    for c in (n - 1 - 9 * k for k in range(0, 30, 5)):
        cut = RE.Divergence(m15.iloc[:c + 1], "15M", s={"div_hidden": True}, areas=False)
        for t in range(c - 20, c + 1):
            for d in (1, -1):
                a = RH.read_hidden_divergence(V_of(full, m15), t, d, move_from=max(0, t - 120))
                b = RH.read_hidden_divergence(V_of(cut, m15.iloc[:c + 1]), t, d, move_from=max(0, t - 120))
                assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str), (c, t, d)
                seen += bool(a["found"])
    assert seen                                                          # the walk does show hidden pairs


def test_draw_objects_shape():
    df, ps, r = bull_hidden()
    objs = RH.draw_objects(V_of(hid(df, ps, r), df), 30, +1, move_from=5)
    assert [o["kind"] for o in objs] == ["rsi_hidden_div", "rsi_hidden_div_rsi"]
    for o in objs:
        assert set(o) == {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"} and o["state"] == "confirmed"
    assert (objs[0]["p0"], objs[0]["p1"], objs[1]["p0"], objs[1]["p1"]) == (95.0, 97.0, 35.0, 30.0)
    json.dumps(objs)


# ------------------------------------------------------------------------------------------------ real data (reported, not asserted)
NIFTY_IN = os.path.join(TD, "review/diagnosis_today/2026-10-21/vps_run3/inputs")


@pytest.mark.skipif(not os.path.exists(os.path.join(NIFTY_IN, "engine_NIFTY_m15.csv.gz")), reason="private trade-data not present")
def test_real_nifty_21_oct_reads_run_and_are_json_safe():
    from decision3 import engine as E3
    from elliott import data_policy as DP
    m15 = pd.read_csv(os.path.join(NIFTY_IN, "engine_NIFTY_m15.csv.gz"), parse_dates=["timestamp", "bar_end"])
    daily = pd.read_csv(os.path.join(NIFTY_IN, "engine_NIFTY_daily.csv.gz"), parse_dates=["timestamp"])
    day = pd.Timestamp(m15["timestamp"].iloc[-1]).normalize()
    assert DP.period(day) != "HOLDOUT"
    from decision3 import history as HI
    V = E3.V22(m15, None, daily, sealed=HI.sealed_fn("NIFTY"))
    bars = [i for i in range(len(m15)) if pd.Timestamp(m15["timestamp"].iloc[i]).normalize() == day]
    for t in bars:
        row = V.decide(t)
        got = RH.read_hidden_divergence(V, t, row=row) if row.get("level") else RH.read_hidden_divergence(V, t)
        json.dumps(got, default=str)
    print("\n" + json.dumps(RH.read_hidden_divergence(V, bars[-1]), default=str)[:600])
    assert V._rsi_hidden is not getattr(V, "_rsi", None)
