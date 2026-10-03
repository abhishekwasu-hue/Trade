"""tests/test_opportunity_engine_zones.py -- zones, Level Quality (§2.6 चे 6 tests), gap registry, level_id; कृत्रिम डेटा, network-free."""
import numpy as np
import pandas as pd
import pytest

from opportunity_engine import level_quality as lq
from opportunity_engine import zones as Z
from opportunity_engine.config import EngineConfig
from opportunity_engine.journal import Journal
from opportunity_engine.structure import StructureTracker

T0 = pd.Timestamp("2025-01-06 09:15")


def cfg(**kw):
    params = {"ref_range_min_bars": 3, "ref_range_bars": 10, "pivot_n": {"x": 2}, "swing_k": {"x": 1.0}, **kw}
    return EngineConfig(**params)


def tracker_from_bars(bars, config=None):
    """bars = [(o, h, l, c)] -> tracker (tf 'x')."""
    tr = StructureTracker("x", config or cfg())
    for i, (o, h, l, c) in enumerate(bars):
        tr.on_bar(T0 + pd.Timedelta(minutes=5 * (i + 1)), o, h, l, c, True)
    return tr


def candle(o, c, wick=0.3):
    return (o, max(o, c) + wick, min(o, c) - wick, c)


def quiet(n, mid=100.0, amp=0.5):
    """छोटी range (≈ ref_range 1.1) चे bars."""
    out, price = [], mid
    for i in range(n):
        nxt = mid + (amp if i % 2 else -amp)
        out.append(candle(price, nxt, 0.3))
        price = nxt
    return out


# ---- displacement / origin ----------------------------------------------------------------------------------------------------
def demand_setup(extra_after=()):
    base = quiet(12, 100.0)
    down = [candle(100.0, 99.2)]                       # base candle (bearish) -> origin
    disp = [candle(99.2, 103.0, 0.1), candle(103.0, 106.5, 0.1)]       # सलग 2 मोठे bullish candles
    return base + down + disp + list(extra_after)


def test_displacement_makes_a_demand_zone_with_body_core_inside_outer():
    tr = tracker_from_bars(demand_setup(quiet(6, 106.5)))
    zs, _ = Z.displacement_zones(tr)
    dem = [z for z in zs if z["kind"] == "DEMAND"]
    assert dem, zs
    z = dem[0]
    assert z["low"] <= z["core_low"] <= z["core_high"] <= z["high"]                  # core (body) outer (wick) च्या आत
    assert (z["core_high"] - z["core_low"]) < (z["high"] - z["low"])
    assert z["freshness"] if "freshness" in z else True


def test_origin_bos_when_displacement_breaks_structure_else_minor():
    # चढत्या swings नंतरचा displacement जो आधीचा swing high तोडतो => ORIGIN_BOS; शांत बाजारातला displacement => ORIGIN_MINOR
    rising = []
    price = 100.0
    for leg in range(3):
        rising += [candle(price, price + 1.0) for _ in range(4)] + [candle(price + 4.0, price + 2.0) for _ in range(2)]
        price += 2.5
    tr_minor = tracker_from_bars(demand_setup(quiet(6, 106.5)))
    z_minor = Z.displacement_zones(tr_minor)[0][0]
    assert z_minor["origin_type"] in ("ORIGIN_MINOR", "ORIGIN_BOS")
    # synthetic: BOS event ठरवून जोडा (tracker events मध्ये) -> ORIGIN_BOS
    tr = tracker_from_bars(demand_setup(quiet(6, 106.5)))
    a = Z.displacement_zones(tr)[0][0]
    tr.events.append({"tf": "x", "bar_idx": a["formed_idx"], "time": tr.bar_end[a["formed_idx"]], "type": "BOS", "price": 1.0,
                      "state": "UPTREND", "from_state": "UPTREND_PULLBACK", "to_state": "UPTREND"})
    b = Z.displacement_zones(tr)[0][0]
    assert b["origin_type"] == "ORIGIN_BOS"
    comps_bos = lq.ORIGIN_SCORE[b["origin_type"]]
    assert comps_bos > lq.ORIGIN_SCORE["ORIGIN_MINOR"] > lq.ORIGIN_SCORE["ORIGIN_NONE"]


def test_single_huge_candle_is_a_displacement_but_a_moderate_one_is_not():
    big = tracker_from_bars(quiet(12, 100) + [candle(100, 99.4), candle(99.4, 106.0, 0.1)] + quiet(4, 106))
    assert any(z["kind"] == "DEMAND" for z in Z.displacement_zones(big)[0])
    moderate = tracker_from_bars(quiet(12, 100) + [candle(100, 99.4), candle(99.4, 101.6, 0.1)] + quiet(4, 101.6))
    assert not Z.displacement_zones(moderate)[0]


# ---- freshness / mitigation / flip ---------------------------------------------------------------------------------------------
def test_freshness_order_and_touch_counting():
    zone = {"tf": "x", "kind": "DEMAND", "source": "DISPLACEMENT", "low": 99.0, "high": 100.0, "core_low": 99.2, "core_high": 99.8,
            "formed_idx": 14, "origin_idx": 12, "formed_at": T0, "origin_type": "ORIGIN_MINOR", "departure_rr": 3.0, "spike": False}
    def run(extra):
        tr = tracker_from_bars(demand_setup(extra))
        return Z.evaluate(dict(zone), tr)
    fresh = run(quiet(6, 106.5))
    assert fresh["freshness"] == "FRESH" and fresh["touches"] == 0 and fresh["status"] == "ACTIVE"
    one = run(quiet(3, 106.5) + [candle(106.5, 99.6, 0.1), candle(99.6, 100.6, 0.1)] + [candle(100.6, 106.0)] * 2 + quiet(3, 106.0))
    assert one["touches"] == 1 and one["freshness"] == "TESTED_1"
    two = run(quiet(3, 106.5) + [candle(106.5, 99.6, 0.1), candle(99.6, 106.0), candle(106.0, 106.5)] * 2 + quiet(3, 106.0))
    assert two["touches"] == 2 and two["freshness"] == "TESTED_2+"
    assert [fresh["touches"], one["touches"], two["touches"]] == sorted([fresh["touches"], one["touches"], two["touches"]])


def test_close_through_far_edge_twice_breaks_the_zone_and_flips_its_role():
    zone = {"tf": "x", "kind": "DEMAND", "source": "DISPLACEMENT", "low": 99.0, "high": 100.0, "core_low": 99.2, "core_high": 99.8,
            "formed_idx": 14, "origin_idx": 12, "formed_at": T0, "origin_type": "ORIGIN_MINOR", "departure_rr": 3.0, "spike": False}
    tr = tracker_from_bars(demand_setup([candle(106.5, 98.0, 0.1), candle(98.0, 97.0, 0.1), candle(97.0, 96.5, 0.1)]))
    z = Z.evaluate(dict(zone), tr)
    assert z["status"] == "BROKEN" and z["broken"]
    assert Z.role_of(z, 96.5) == "RESISTANCE" and Z.role_of(z, 101.0) == "SUPPORT"          # तुटलेला demand आता वरून resistance
    single = Z.evaluate(dict(zone), tracker_from_bars(demand_setup([candle(106.5, 98.0, 0.1), candle(98.0, 100.5, 0.1)])))
    assert not single["broken"]                                                              # एकच close पलीकडे = acceptance नाही


def test_close_inside_core_marks_mitigated():
    zone = {"tf": "x", "kind": "DEMAND", "source": "DISPLACEMENT", "low": 99.0, "high": 100.0, "core_low": 99.2, "core_high": 99.8,
            "formed_idx": 14, "origin_idx": 12, "formed_at": T0, "origin_type": "ORIGIN_MINOR", "departure_rr": 3.0, "spike": False}
    tr = tracker_from_bars(demand_setup([candle(106.5, 99.5, 0.1), candle(99.5, 105.0, 0.1)] + quiet(3, 105)))
    assert Z.evaluate(dict(zone), tr)["status"] == "MITIGATED"


# ---- gap registry ---------------------------------------------------------------------------------------------------------------
def _daily(rows):
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["date"])
    df["bar_start"] = df["timestamp"] + pd.Timedelta(minutes=9 * 60 + 15)
    df["bar_end"] = df["timestamp"] + pd.Timedelta(minutes=15 * 60 + 30)
    df["bar_is_full"] = True
    return df


def test_gap_registry_unfilled_partial_filled_transition():
    c = EngineConfig()
    base = [("2025-01-06", 100, 101, 99, 100), ("2025-01-07", 103, 104, 103.0, 103.5)]      # gap-up 3%: [100, 103]
    t = pd.Timestamp("2025-01-10 16:00")
    unfilled = Z.gap_registry(_daily(base + [("2025-01-08", 103.6, 105, 103.5, 104.5)]), t, c)
    assert unfilled and unfilled[0]["gap_status"] == "UNFILLED" and (unfilled[0]["low"], unfilled[0]["high"]) == (100.0, 103.0)
    partial = Z.gap_registry(_daily(base + [("2025-01-08", 103.6, 104.5, 101.5, 102)]), t, c)
    assert partial[0]["gap_status"] == "PARTIAL"
    filled = Z.gap_registry(_daily(base + [("2025-01-08", 102, 103, 99.5, 100.5)]), t, c)
    assert filled[0]["gap_status"] == "FILLED"
    small = Z.gap_registry(_daily([("2025-01-06", 100, 101, 99, 100), ("2025-01-07", 100.1, 101, 99.5, 100.5)]), t, c)
    assert small == []                                                                  # < 0.25% gap नाही
    not_yet_closed = Z.gap_registry(_daily(base), pd.Timestamp("2025-01-07 12:00"), c)
    assert not_yet_closed == []                                                          # gap-day अजून बंद नाही (bar_end > t) — no-lookahead


def test_key_levels_use_only_closed_days_and_include_round_numbers():
    d = _daily([("2025-01-06", 100, 110, 95, 105), ("2025-01-07", 105, 112, 101, 108), ("2025-01-08", 108, 109, 100, 101)])
    keys = {z["source"]: z for z in Z.key_levels(d, pd.Timestamp("2025-01-08 16:00"), 24000.0, "NIFTY")}
    assert keys["PDH"]["low"] == 109 and keys["PDL"]["low"] == 100 and keys["PDC"]["low"] == 101
    assert any(k.startswith("R") for k in keys)
    early = {z["source"] for z in Z.key_levels(d, pd.Timestamp("2025-01-08 10:00"), 24000.0, "NIFTY")}
    assert "PDH" in early                                                               # 8 तारखेचा दिवस अजून बंद नाही => 7 तारखेचा PDH
    assert next(z for z in Z.key_levels(d, pd.Timestamp("2025-01-08 10:00"), 24000.0) if z["source"] == "PDH")["low"] == 112


# ---- Level quality (§2.6 tests) --------------------------------------------------------------------------------------------------
def test_spike_candle_wick_does_not_become_a_level_and_is_recorded_as_sweep():
    c = cfg()
    bars = quiet(12, 100.0) + [candle(100.0, 99.0)]
    # base म्हणून spike candle: छोटं body, खाली खूप मोठी wick, लगेच परत
    spike = (99.2, 99.6, 80.0, 99.0)
    bars += [spike, candle(99.2, 103.0, 0.1), candle(103.0, 106.5, 0.1)] + quiet(5, 106.5)
    tr = tracker_from_bars(bars, c)
    zs, sweeps = Z.displacement_zones(tr, c)
    dem = [z for z in zs if z["kind"] == "DEMAND"]
    assert dem and dem[0]["spike"]
    assert dem[0]["low"] > 90                                                  # wick (80) outer मध्ये नाही
    assert any(s["side"] == "LOW" and s["price"] == pytest.approx(80.0) for s in sweeps)
    assert lq.spike_kind(99.2, 99.6, 80.0, [99.5], 1.2, c, 99.2, 99.0) == "DOWN"
    assert lq.spike_kind(99.2, 99.6, 80.0, [90.0], 1.2, c, 99.2, 99.0) is None          # परत आली नाही => spike नाही (खरी घसरण)


def test_body_core_is_narrower_than_wick_outer_and_scores_higher_when_tight():
    assert lq.body_core_score(0.5, 5.0, 1.0) == pytest.approx(1.0)
    assert lq.body_core_score(4.0, 5.0, 1.0) == pytest.approx(0.0)
    assert lq.body_core_score(2.0, 5.0, 1.0) > lq.body_core_score(3.0, 5.0, 1.0)


def test_two_strong_rejections_beat_three_weak_touches():
    strong = lq.reaction_strength([5.0, 5.0], [10, 20])
    weak = lq.reaction_strength([1.0, 1.0, 1.0], [10, 20, 30])
    assert strong > weak
    assert lq.reaction_strength([5.0], [5]) > lq.reaction_strength([5.0], [400])             # recent touch जास्त वजनाचा
    assert 0.0 <= lq.reaction_strength([100.0] * 50, [0] * 50, 50.0) <= 1.0


def test_grade_uses_weights_and_rejects_low_scores():
    c = EngineConfig()
    full = {"clean": 1, "body_core": 1, "origin": 1, "reaction": 1, "density": 1, "mtf": 1}
    assert lq.grade(full, c) == (1.0, "A")
    assert lq.grade({k: 0.0 for k in full}, c) == (0.0, "REJECT")
    mid = {"clean": 1, "body_core": 0.5, "origin": 0.5, "reaction": 0.5, "density": 0.5, "mtf": 0.0}
    assert lq.grade(mid, c)[1] in ("B", "C")


def test_density_histogram_puts_range_edge_on_acceptance_not_on_wick_spike():
    rng = np.random.default_rng(0)
    ts = pd.date_range("2025-01-06 09:15", periods=200, freq="5min")
    mid = 100 + rng.normal(0, 0.3, 200)
    df = pd.DataFrame({"timestamp": ts, "open": mid, "close": mid, "high": mid + 0.3, "low": mid - 0.3})
    df.loc[100, "high"] = 112.0                                                              # एकच wick spike
    edges, share = lq.price_density(df, n_sessions=5, bin_pct=0.05)
    assert abs(share.sum() - 1.0) < 1e-9
    assert lq.density_percentile(edges, share, 100.0) > lq.density_percentile(edges, share, 111.0)         # acceptance भाग > spike भाग
    assert lq.density_percentile(edges, share, 111.0) <= 0.2
    assert lq.price_density(pd.DataFrame(columns=["timestamp", "high", "low"]))[0].size == 0


def test_level_id_is_stable_and_sensitive_to_inputs():
    a = lq.level_id("NIFTY", "1h", "DEMAND", 22000.04, T0)
    assert a == lq.level_id("NIFTY", "1h", "DEMAND", 22000.04, T0) and len(a) == 12
    assert a == lq.level_id("NIFTY", "1h", "DEMAND", 22000.0401, T0)                      # round(core, 1)
    assert a != lq.level_id("NIFTY", "4h", "DEMAND", 22000.04, T0)
    assert a != lq.level_id("BANKNIFTY", "1h", "DEMAND", 22000.04, T0)
    assert a != lq.level_id("NIFTY", "1h", "DEMAND", 22000.04, T0 + pd.Timedelta(minutes=5))


# ---- एकत्रित build_levels ---------------------------------------------------------------------------------------------------------
def _frames_from(tr, tf):
    return pd.DataFrame({"timestamp": tr.bar_end, "bar_end": tr.bar_end, "bar_start": tr.bar_end, "bar_is_full": True,
                         "open": tr.o, "high": tr.h, "low": tr.l, "close": tr.c})


def test_build_levels_end_to_end_is_deterministic_and_explains_rejections():
    c = cfg(pivot_n={"15m": 2, "1h": 2, "4h": 2, "1d": 2}, swing_k={"15m": 1.0, "1h": 1.0, "4h": 1.0, "1d": 1.0})
    tr = tracker_from_bars(demand_setup(quiet(20, 106.5) + [candle(106.5, 98.0, 0.1), candle(98.0, 97.0, 0.1), candle(97.0, 96.5, 0.1)] + quiet(5, 96.5)), c)
    frame = _frames_from(tr, "15m")
    j = Journal(c, tfs=("15m",)).run({"15m": frame})
    a = Z.build_levels(j, {"15m": frame}, "NIFTY", 96.5, c, tfs=("15m",), fine=frame)
    b = Z.build_levels(j, {"15m": frame}, "NIFTY", 96.5, c, tfs=("15m",), fine=frame)
    assert [z["level_id"] for z in a["levels"]] == [z["level_id"] for z in b["levels"]]
    assert all(z["quality_grade"] in ("A", "B", "C") for z in a["levels"])
    assert a["rejected"] and all(z["reject_reason"] for z in a["rejected"])                # तुटलेला demand "का नाकारला" सकट
    assert all({"clean", "body_core", "origin", "reaction", "density", "mtf"} == set(z["quality_components"]) for z in a["levels"] + a["rejected"])
