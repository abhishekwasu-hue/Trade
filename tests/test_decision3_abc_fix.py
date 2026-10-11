"""ABC_FIX (Abhi: TRADE_SESSION_BANKNIFTY_ABC_FIX) — rule 3 / 4 / 5 output, provisional completion restore, no lookahead."""
import numpy as np

from tests import elliott_fixtures as F
from decision3 import daily as DD
from decision3 import daily_swings as DS
from tests.test_decision3_daily_q15 import _V_with


def test_rule5_caption_bands_and_next_demand_on_banknifty_shape():
    """Abhi's caption while the new decline is above the b low; once price closes below b, "next demand" is no longer shown."""
    for mirror in (False, True):
        d = F.ohlc(_bn_points()[:-3], mirror)                              # new decline in progress, still above the b low
        v = DS.build(d, window=len(d), with_elliott=False)
        q = v["q15"]
        t = "UP" if mirror else "DOWN"
        side = "fall supply" if t == "DOWN" else "rise demand"
        line = DS.trend_line(q)
        assert line.startswith(f"Trend {t} · a-b-c correction completed at sharp-{side} · new impulse {t.lower()} in progress"), line
        assert f"protected {q['protected_now']['price']:,.0f}" in line
        b_px = (F.MIRROR - 1220.0 + F.WICK) if mirror else (1220.0 - F.WICK)
        assert abs(q["next_level"]["price"] - b_px) < 1e-9                  # rule 4: next demand = b low (a-b-c reduction)
        assert f"next {'demand' if t == 'DOWN' else 'supply'} {b_px:,.0f}" in line
        labels = [b["label"] for b in q["levels"]]
        assert any("sharp-" in x for x in labels) and any(x.startswith("next ") for x in labels)
        full, _ = F.acceptance_banknifty(mirror)                           # later bars close beyond the b low
        vf = DS.build(full, window=len(full), with_elliott=False)
        assert vf["q15"]["next_level"] is None and "next demand" not in DS.trend_line(vf["q15"])


def test_rule5_caption_not_shown_while_a_new_correction_runs():
    d2 = F.ohlc(_bn_points() + [(1330.0, 6), (1300.0, 3), (1360.0, 5)])  # same shape + a later bounce (new counter-move)
    st = DD.fold(d2)
    v = DS.build(d2, window=len(d2), with_elliott=False)
    if st[-1].phase != "impulse" or st[-1].counter not in (None, "pullback"):
        assert "completed at sharp" not in DS.trend_line(v["q15"])
        V = _V_with(st, [DD.DState(0, st[0].day, st[0].known_at, "UNKNOWN")])
        _, _, _, ctx = V.step1(0)
        assert "evidence" not in ctx
    else:
        raise AssertionError("fixture: the bounce should start a new counter-move")


def _bn_points():
    """acceptance_banknifty waypoints (DOWN) — rebuilt here so the test can extend the series."""
    top, a, b, c = 1600.0, 1380.0, 1220.0, 1567.0
    slow = [(1580.0, 3), (1590.0, 2), (1560.0, 3), (1570.0, 2), (1545.0, 3)]
    fall = [(1300.0, 5), (1360.0, 4), (1150.0, 5), (1220.0, 4), (1080.0, 5)]
    corr = F.build(1080.0, F.zz(a, b, c))
    after = [(1420.0, 6), (1460.0, 3), (1250.0, 7), (1290.0, 3), (1150.0, 6), (1170.0, 3)]
    lead = [(1350.0, 0), (top, 30), (1520.0, 8), (1585.0, 5)]
    return lead + slow + fall + corr + after


def test_bn_points_helper_matches_fixture():
    d, _ = F.acceptance_banknifty()
    d2 = F.ohlc(_bn_points())
    assert np.allclose(d["close"].to_numpy(), d2["close"].to_numpy())


def test_engine_step1_records_continuation_evidence_after_sharp_zone_completion():
    d, _ = F.acceptance_banknifty()
    st = DD.fold(d)
    assert st[-1].corr_zone is not None and st[-1].evidence
    V = _V_with(st, [DD.DState(0, st[0].day, st[0].known_at, "UNKNOWN")])
    ok, why, s1, ctx = V.step1(0)
    assert ok and ctx["trend"] == "DOWN" and ctx["evidence"] and any("continuation evidence" in x for x in ctx["notes"])


def test_expanded_flat_provisional_completion_is_restored():
    """b makes a new low beyond the impulse end (provisional completion), c then breaks that provisional origin ⇒ the earlier
    correction state comes back (trend stays DOWN) — the restore path."""
    d, _ = F.correction_fixture("flat_expanded")
    st = DD.fold(d)
    assert any("वर परत" in (x.why or "") for x in st)
    eb = int(np.argmin(np.abs(d["low"].to_numpy() - (F.E - F.WICK))))
    assert all(x.trend == "DOWN" for x in st[eb:])


def test_new_state_fields_have_no_lookahead():
    """truncation invariance: state at bar k is the same whether later bars exist or not (sharp zone, corr_zone, leg_from,
    evidence, protected, phase)."""
    d, _ = F.acceptance_banknifty()
    full = DD.fold(d)
    key = lambda x: (x.trend, x.phase, getattr(x.protected, "price", None), x.sharp, x.corr_zone, x.leg_from, x.evidence,  # noqa: E731
                     x.counter)
    for k in range(60, len(d), 7):
        part = DD.fold(d.iloc[:k].reset_index(drop=True))
        assert [key(x) for x in part] == [key(x) for x in full[:k]], k
