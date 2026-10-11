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
    evidence, protected, phase, Q44 targets / mature / target_passed)."""
    key = lambda x: (x.trend, x.phase, getattr(x.protected, "price", None), x.sharp, x.corr_zone, x.leg_from, x.evidence,  # noqa: E731
                     x.counter, x.targets, x.mature, x.target_passed)
    seen = 0
    for d in (F.acceptance_banknifty()[0], F.acceptance_banknifty(True)[0], _walk(3, 300)[0]):
        full = DD.fold(d)
        seen += sum(bool(x.targets) for x in full)
        for k in range(60, len(d), 7):
            part = DD.fold(d.iloc[:k].reset_index(drop=True))
            assert [key(x) for x in part] == [key(x) for x in full[:k]], k
    assert seen > 0                                                        # targets सुद्धा तपासले गेले


def _walk(seed, n=500):
    """random walk Daily frame (Q44 property / lookahead tests) ⇒ (d, low, high)."""
    import pandas as pd
    rng = np.random.default_rng(seed)
    c = 1000.0 + np.cumsum(rng.normal(0, 8, n))
    o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) + rng.uniform(0.5, 4, len(c))
    lo = np.minimum(o, c) - rng.uniform(0.5, 4, len(c))
    days = pd.bdate_range("2030-01-01", periods=len(c))
    d = pd.DataFrame({"timestamp": days, "open": o, "high": hi, "low": lo, "close": c,
                      "bar_end": days + pd.Timedelta(hours=15, minutes=30)})
    return d, lo, hi


def test_q55_sharp_zone_is_the_first_swing_low_the_run_breaks():
    """Q55 (B): the run breaks two swing lows (sharp_point, then the lead-in's second_low) — the zone is the first one broken."""
    for mirror in (False, True):
        d, info = F.acceptance_banknifty_two_lows(mirror)
        st = DD.fold(d)
        z = next(x.corr_zone for x in st if x.corr_zone is not None)
        sp, sl = (info["sharp_point"], info["second_low"])
        if mirror:
            sp, sl = F.MIRROR - sp, F.MIRROR - sl
        ext = sp + F.WICK if mirror else sp - F.WICK                       # swing candle wick extreme
        assert z[0] <= ext <= z[1] and not (z[0] <= sl <= z[1])
        assert z[0] <= (F.MIRROR - info["c"] - F.WICK if mirror else info["c"] + F.WICK) <= z[1]   # c ends inside the zone


def test_q44_target_is_first_impulse_leg_extreme_and_inside_window():
    """Q44: target = extreme of the first impulse leg after the parent origin; never outside the window's price range; none ⇒
    "target: none (structure incomplete)"."""
    for mirror in (False, True):
        d, _ = F.acceptance_banknifty(mirror)
        st = DD.fold(d)
        want = (F.MIRROR - 1080.0 + F.WICK) if mirror else (1080.0 - F.WICK)
        assert st[-1].targets == (want,)
    fx = [F.correction_fixture(k, m)[0] for k in F.CORRECTIONS for m in (False, True)]
    fx += [F.impulse_control(k, m)[0] for k in F.IMPULSES for m in (False, True)]
    fx += [F.acceptance_nifty()[0]]
    for d in fx:
        lo, hi = float(d["low"].min()), float(d["high"].max())
        for x in DD.fold(d):
            assert all(lo <= t <= hi for t in (x.targets or ()))
    q = DS.build(F.correction_fixture("zigzag_c_eq_a")[0], window=200, with_elliott=False)["q15"]
    line = DS.trend_line({**q, "targets": (), "phase": "impulse"})
    assert "target: none (structure incomplete)" in line


def test_q44_caption_target_passed_vs_none():
    """Q44 nit (review): a structural target that protected has already moved beyond ⇒ "target passed" (not "none (structure
    incomplete)"); no structure ⇒ "target: none (structure incomplete)"; a live target ⇒ "target <price>"."""
    q = DS.build(F.correction_fixture("zigzag_c_eq_a")[0], window=200, with_elliott=False)["q15"]
    base = {**q, "phase": "impulse", "counter": None, "rule5": False}
    passed = DS.trend_line({**base, "targets": (), "target_passed": True})
    assert "target passed" in passed and "structure incomplete" not in passed
    assert "target: none (structure incomplete)" in DS.trend_line({**base, "targets": (), "target_passed": False})
    assert "target 1,234" in DS.trend_line({**base, "targets": (1234.0,), "target_passed": False})
    for mirror in (False, True):                                           # engine: passed ⇒ target / mature नाहीत
        d, _, _ = _walk(1)
        if mirror:
            d = d.assign(open=3000.0 - d["open"], close=3000.0 - d["close"], high=3000.0 - d["low"], low=3000.0 - d["high"])
        st = DD.fold(d)
        assert any(x.target_passed for x in st)
        assert not any(x.target_passed and (x.targets or x.mature) for x in st)


def test_family_combination_needs_two_complete_patterns():
    """Item 4: W-X-Y needs W and Y to be complete corrective patterns (zigzag / flat / triangle / combination). A move whose W
    reads only "3-wave" is no longer a combination (before PR A: "combination"; now: "flat"). Mirror reads the same."""
    from decision3 import daily_legs as DL
    wxy = [100.0, 160.0, 130.0, 180.0, 150.0, 200.0, 175.0, 230.0]                 # W zigzag, X, Y zigzag
    w3 = [100.0, 136.0, 131.0, 141.0, 132.0, 159.0, 112.0, 140.0, 122.0, 158.0]    # W = 3-wave (अपूर्ण) ⇒ combination नाही
    for m in (False, True):
        f = (lambda p: [1000.0 - x for x in p]) if m else (lambda p: p)
        assert DL.read_counter(f(wxy))["family"] == "combination"
        assert DL.read_counter(f(w3))["family"] == "flat"


def test_correction_box_family_read_at_trend_degree():
    """Item 4: the correction box is read on the engine's trend-degree pivots — the same box reads "zigzag" there (a-b-c) but
    "flat" on lower-degree pivots (only used when trend-degree swings are fewer than a-b-c). Mirror pair."""
    import pandas as pd
    from decision3 import daily_legs as DL
    low_px = [100.0, 136.0, 131.0, 141.0, 132.0, 159.0, 112.0, 140.0, 122.0, 158.0]   # leg टोक 100 ⇒ box शेवट 158
    t0 = pd.Timestamp("2030-01-01")
    for m in (False, True):
        f = (lambda p: 1000.0 - p) if m else (lambda p: p)
        kind = (lambda k: {"H": "L", "L": "H"}[k]) if m else (lambda k: k)
        P = lambda k, px, b: DD.DPivot(kind(k), f(px), b, t0, b, t0)        # noqa: E731
        low = [P("H" if j % 2 else "L", px, 3 * j) for j, px in enumerate(low_px) if 0 < j < len(low_px) - 1]
        trend_pv = [P("H", 159.0, 15), P("L", 112.0, 18)]                   # trend degree: a = 159, b = 112
        leg = {"to": 0, "p1": f(100.0), "p0": f(200.0), "dir": 1 if m else -1, "par": None}
        end = 3 * (len(low_px) - 1)
        at_trend = DS._corr(leg, end, f(158.0), "done", low, DL, trend_pv=trend_pv)
        at_low = DS._corr(leg, end, f(158.0), "done", low, DL, trend_pv=())
        assert at_trend["shape"] == "zigzag" and at_low["shape"] == "flat", (m, at_trend["shape"], at_low["shape"])
        assert at_trend["b_price"] == f(112.0)


def test_q44_target_property_on_random_walks():
    """Q44 (review): on random walks (both signs), a target exists only in an A1 correction (counter = "correction") or after it.
    The target is a real extreme (DOWN ⇒ a low, UP ⇒ a high) beyond protected, printed after the A1 parent bar; while the A1
    correction runs it is after the parent, and afterwards it is the same target the A1 correction showed, printed before the
    current protected origin (the new impulse started after it)."""
    seen = after = 0
    for seed in range(12):
        d, lo, hi = _walk(seed)
        a1 = None                                                          # शेवटच्या A1 correction चा (parent bar, targets)
        prev_trend = None
        for i, x in enumerate(DD.fold(d)):
            if x.trend != prev_trend:
                a1, prev_trend = None, x.trend
            if not x.targets:
                continue
            assert x.trend in ("UP", "DOWN"), (seed, i)
            col = lo if x.trend == "DOWN" else hi
            sgn = -1 if x.trend == "DOWN" else 1
            if x.counter == "correction":
                a1 = (x.parent.bar, x.targets)
                lo_bar, hi_bar = x.parent.bar, i + 1                       # parent नंतर, आजपर्यंत
            else:
                assert a1 is not None, (seed, i)                           # A1 शिवाय target नाही
                assert x.targets == a1[1], (seed, i, x.targets, a1)        # A1 मधलाच target (नवा parent नाही ⇒ reset नाही)
                lo_bar, hi_bar = a1[0], x.protected.bar                    # A1 parent नंतर, नव्या protected origin आधी
                after += 1
            for t in x.targets:
                hits = [k for k in range(len(col)) if abs(col[k] - t) <= 0.005 + 1e-9]   # targets 2 दशांश ⇒ त्या किंमतीचा bar
                assert hits and all(lo_bar < k < hi_bar for k in hits), (seed, i, t, hits, lo_bar, hi_bar)
                assert (t - x.protected.price) * sgn > 0, (seed, i, t)
            seen += 1
    assert seen > 0 and after > 0
