"""tests/test_opportunity_engine_pr3.py -- PR-3: patterns (box/triangle/OR), D7 Range-Box breakout, D8 Triangle breakout, D10 box trap, T1 hint,
visual audit key-नसल्यास skip. कृत्रिम, network-free."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import run_visual_audit as RVA
from opportunity_engine import backtest as BT
from opportunity_engine import diagnostics as DG
from opportunity_engine import sessions
from opportunity_engine.detectors import box_triangle as BX
from opportunity_engine.detectors import patterns as P
from opportunity_engine.detectors import range_box as RB
from opportunity_engine.detectors.base import Candidate
from opportunity_engine.risk import plan_trade
from tests.test_opportunity_engine_backtest import CFG, bars, ctx_of, info_of, walk_1m, zone
from tests.test_opportunity_engine_pr2 import run

# 14 bars box 24000–24040: सम bars वरच्या कडेला (high 24040), विषम खालच्या (low 24000) ⇒ प्रत्येकी 7 touches
BOX_ROWS = [(24012, 24040, 24010, 24030) if i % 2 == 0 else (24022, 24025, 24000, 24010) for i in range(14)]
UP_BREAK = (24030, 24055, 24028, 24050)
DOWN_BREAK = (24010, 24012, 23990, 23992)
PAT = [0, 0.5, 1, 0.5, 0, -0.5, -1, -0.5]


def tri_rows(n=30):
    out = []
    for i in range(n):
        c = 24000 + (60 - 1.2 * i) * PAT[i % 8]
        out.append((c, c + 3, c - 3, c))
    return out


# ---- patterns ------------------------------------------------------------------------------------------------------------------------------
def test_find_box_longest_window_touches_and_height_limit():
    df = bars(BOX_ROWS)
    b = P.find_box(df["high"].to_numpy(float), df["low"].to_numpy(float), 200.0)
    assert b is not None and (b.top, b.bottom, b.start, b.end, b.bars) == (24040.0, 24000.0, 0, 13, 14)
    assert b.touches_top == 7 and b.touches_bottom == 7 and b.mid == 24020.0 and b.height == 40.0
    assert P.find_box(df["high"].to_numpy(float), df["low"].to_numpy(float), 100.0) is None            # 40 > 0.35 × 100
    assert P.find_box(df["high"].to_numpy(float)[:8], df["low"].to_numpy(float)[:8], 200.0) is None     # 12 bars पेक्षा कमी
    flat_top = [(24012, 24040, 24010, 24030)] + [(24022, 24025, 24000, 24010)] * 13                      # वरच्या कडेला एकच touch
    d2 = bars(flat_top)
    assert P.find_box(d2["high"].to_numpy(float), d2["low"].to_numpy(float), 200.0) is None
    assert P._visits([True, True, False, True, False, False, True]) == 3 and P._visits([]) == 0


def test_find_triangle_symmetrical_and_rejects():
    t = P.find_triangle(bars(tri_rows()), 10.0)
    assert t is not None and t.kind == "SYMMETRICAL" and t.m_hi < 0 < t.m_lo and t.n_hi >= 2 and t.n_lo >= 2
    assert t.upper(30) == pytest.approx(24027.0, abs=0.5) and t.lower(30) == pytest.approx(23973.0, abs=0.5) and t.width0 > 100
    flat = [(24000 + 30 * PAT[i % 8], 24003 + 30 * PAT[i % 8], 23997 + 30 * PAT[i % 8], 24000 + 30 * PAT[i % 8]) for i in range(30)]
    assert P.find_triangle(bars(flat), 10.0) is None                                                    # रुंदी कमी होत नाही ⇒ triangle नाही
    asc = []
    for i in range(30):                                                                                   # highs सपाट 24060, lows वाढते
        lo = 23940 + 2.5 * i
        c = lo + (24060 - lo) * (PAT[i % 8] + 1) / 2
        asc.append((c, min(c + 3, 24060.0), max(c - 3, lo), c))
    ta = P.find_triangle(bars(asc), 10.0)
    assert ta is not None and ta.kind == "ASCENDING"
    assert P.find_triangle(bars(tri_rows()), float("nan")) is None


def test_or_box():
    df = bars([(24000, 24040, 23990, 24030), (24030, 24035, 24005, 24010), (24010, 24025, 24000, 24020), (24020, 24030, 24010, 24025)])
    b = P.or_box(df, 3, 200.0)
    assert b.kind == "OR" and (b.top, b.bottom, b.end) == (24040.0, 23990.0, 2)
    assert P.or_box(df, 3, 100.0) is None and P.or_box(df.iloc[:2], 3, 200.0) is None


# ---- D7 ------------------------------------------------------------------------------------------------------------------------------------
def test_d7_long_breakout_sl_mid_t1_hint_and_single_use():
    det, state = BX.RangeBoxBreakout(CFG), {}
    df5 = bars(BOX_ROWS + [UP_BREAK], start="10:00")
    c = run(det, df5, ctx_of(price=24050.0), state=state)
    assert len(c) == 1
    c = c[0]
    assert c.setup_id == "D7" and c.direction == "LONG" and c.kind == "BREAKOUT" and c.entry == 24050.0 and c.sl_ref == 24020.0
    assert c.meta["t1_hint"] == 24090.0 and c.targets_hint == [24130.0] and c.trigger["level"] == 24040.0 and c.meta["box_kind"] == "BOX"
    assert c.zone["kind"] == "BOX" and not c.meta["on_htf_zone"] and 50.0 < c.setup_quality <= 100.0
    assert run(det, df5, ctx_of(price=24050.0), state=state) == []                                   # तोच box पुन्हा नाही


def test_d7_short_edge_sl_htf_zone_bonus_and_no_breakout_and_window():
    det = BX.RangeBoxBreakout(replace(CFG, d7_sl_mode="edge"))
    c = run(det, bars(BOX_ROWS + [DOWN_BREAK], start="10:00"), ctx_of(price=23992.0))
    assert [x.direction for x in c] == ["SHORT"] and c[0].sl_ref == 24040.0 and c[0].meta["t1_hint"] == 23952.0
    plain = run(BX.RangeBoxBreakout(CFG), bars(BOX_ROWS + [UP_BREAK], start="10:00"), ctx_of(price=24050.0))[0]
    dz = zone("DEMAND", 23990.0, 24005.0, tf="1h", grade="B")
    on = run(BX.RangeBoxBreakout(CFG), bars(BOX_ROWS + [UP_BREAK], start="10:00"), ctx_of(levels=[dz], price=24050.0))[0]
    assert on.meta["on_htf_zone"] and on.zone["kind"] == "DEMAND" and on.setup_quality == pytest.approx(plain.setup_quality + 10.0)
    weak = (24030, 24046, 24028, 24043)                                                                # close 24043 < 24040 + 0.1 × 40
    assert run(BX.RangeBoxBreakout(CFG), bars(BOX_ROWS + [weak], start="10:00"), ctx_of()) == []
    assert run(BX.RangeBoxBreakout(CFG), bars(BOX_ROWS + [UP_BREAK], start="13:45"), ctx_of()) == []   # 14:45 नंतर
    assert run(BX.RangeBoxBreakout(CFG), bars(BOX_ROWS + [UP_BREAK], start="10:00"), ctx_of(adr=float("nan"))) == []


def test_d7_opening_range_when_no_box():
    rows = [(24000, 24040, 23990, 24030), (24030, 24035, 24005, 24010), (24010, 24025, 24000, 24020), (24020, 24030, 24010, 24025),
            (24025, 24060, 24024, 24055)]
    c = run(BX.RangeBoxBreakout(CFG), bars(rows), ctx_of(price=24055.0))
    assert len(c) == 1 and c[0].meta["box_kind"] == "OR" and c[0].direction == "LONG" and c[0].trigger["level"] == 24040.0


def test_d7_retest_mode_waits_for_edge_touch():
    det, state = BX.RangeBoxBreakout(replace(CFG, d7_entry_mode="retest")), {}
    rows = BOX_ROWS + [UP_BREAK]
    assert run(det, bars(rows, start="10:00"), ctx_of(), state=state) == []
    assert len(state["d7_pending"]) == 1
    rows2 = rows + [(24050, 24052, 24038, 24048)]                                                       # कडेला (24040) स्पर्श, close पुन्हा वर
    c = run(det, bars(rows2, start="10:00"), ctx_of(), state=state)
    assert len(c) == 1 and c[0].meta["retest"] and c[0].entry == 24048.0 and state["d7_pending"] == []
    st2 = {}
    run(det, bars(rows, start="10:00"), ctx_of(), state=st2)
    failed = rows + [(24050, 24052, 24010, 24015)]                                                      # box मध्याखाली परत ⇒ रद्द
    assert run(det, bars(failed, start="10:00"), ctx_of(), state=st2) == [] and st2["d7_pending"] == []


def test_pattern_frames_15m_only_on_fresh_close():
    df5 = bars(BOX_ROWS + [UP_BREAK], start="10:00")
    now = df5["bar_end"].iloc[-1]
    fresh = bars(BOX_ROWS + [UP_BREAK], start="06:15", freq=15)                                           # शेवटचा bar_end = 10:00 + 75 मि.
    fresh["bar_end"] = fresh["bar_end"] + (now - fresh["bar_end"].iloc[-1])
    b = {"5m": df5, "15m": fresh, "rr5": 10.0, "rr15": 20.0}
    assert [f[0] for f in BX.pattern_frames(b, now, ("5m", "15m"))] == ["5m", "15m"]
    stale = fresh.assign(bar_end=fresh["bar_end"] - pd.Timedelta(minutes=5))
    assert [f[0] for f in BX.pattern_frames({**b, "15m": stale}, now, ("5m", "15m"))] == ["5m"]
    assert BX.pattern_frames({**b, "15m": fresh}, now, ("5m", "15m"))[1][2] == 20.0


# ---- D8 ------------------------------------------------------------------------------------------------------------------------------------
def test_d8_symmetrical_long_breakout_targets_and_single_use():
    det, state = BX.TriangleBreakout(CFG), {}
    df5 = bars(tri_rows() + [(24020, 24046, 24018, 24045)], start="10:00")
    c = run(det, df5, ctx_of(price=24045.0), state=state)
    assert len(c) == 1
    c = c[0]
    assert c.setup_id == "D8" and c.direction == "LONG" and c.meta["triangle"] == "SYMMETRICAL" and c.meta["aligned"]
    assert c.trigger["level"] == pytest.approx(24027.0, abs=0.5) and c.targets_hint[0] == pytest.approx(c.trigger["level"] + c.meta["width0"])
    assert c.sl_ref < c.entry and c.zone["kind"] == "TRIANGLE"
    assert run(det, df5, ctx_of(price=24045.0), state=state) == []
    inside = bars(tri_rows() + [(24000, 24015, 23995, 24010)], start="10:00")
    assert run(BX.TriangleBreakout(CFG), inside, ctx_of()) == []
    down = run(BX.TriangleBreakout(CFG), bars(tri_rows() + [(23990, 23992, 23950, 23955)], start="10:00"), ctx_of(price=23955.0))
    assert [x.direction for x in down] == ["SHORT"] and not down[0].meta["aligned"]                  # symmetrical, trend UP ⇒ जुळत नाही


# ---- D10 box trap --------------------------------------------------------------------------------------------------------------------------
def test_d10_box_trap_ranks_first_with_opposite_edge_target():
    sweep = (24010, 24015, 23990, 24008)                                                                # box तळ 24000 खाली wick, परत आत close
    c = run(RB.FailedBreakoutTrap(CFG), bars(BOX_ROWS + [sweep], start="10:00"), ctx_of(price=24008.0), info=info_of(pdl=23000.0))
    assert len(c) == 1 and c[0].meta["level_type"] == "BOX" and c[0].meta["swept_level"] == 24000.0
    assert 24040.0 in c[0].targets_hint and c[0].sl_ref == 23990.0 and c[0].zone["kind"] == "BOX"
    lv = [x for x in RB.trap_levels(ctx_of(), None, bars(BOX_ROWS), 1, CFG) if x["type"] == "BOX"]
    assert lv and lv[0]["price"] == 24000.0 and lv[0]["target"] == 24040.0


# ---- risk T1 hint ----------------------------------------------------------------------------------------------------------------------------
def test_plan_trade_uses_t1_hint_only_when_ahead():
    base = dict(setup_id="D7", direction="LONG", time=None, entry=24050.0, sl_ref=24020.0, trigger={}, targets_hint=[24130.0])
    p = plan_trade(Candidate(**base, meta={"t1_hint": 24090.0}), ctx_of(), CFG, 10.0, adr=200.0)
    assert p.ok and p.t1 == 24090.0 and p.t2 == 24130.0
    p2 = plan_trade(Candidate(**base, meta={"t1_hint": 24040.0}), ctx_of(), CFG, 10.0, adr=200.0)        # entry मागे ⇒ दुर्लक्ष (1R)
    assert p2.t1 == pytest.approx(24050.0 + p2.risk)
    p3 = plan_trade(Candidate(**base), ctx_of(), CFG, 10.0, adr=200.0)
    assert p3.t1 == pytest.approx(24050.0 + p3.risk)


# ---- registry / diagnostics / replay ---------------------------------------------------------------------------------------------------------
def test_registry_defaults_and_diag_windows():
    assert BT.BacktestConfig().detectors == ("D1", "D2", "D3", "D6", "D7", "D8", "D10")
    assert [d.setup_id for d in BT.make_detectors(("D7", "D8"), CFG)] == ["D7", "D8"]
    t = pd.Timestamp("2025-01-08 15:00")
    assert not DG._in_window("D7", t, CFG) and not DG._in_window("D8", t, CFG) and DG._in_window("D7", pd.Timestamp("2025-01-08 11:00"), CFG)


def test_full_replay_with_all_detectors_runs():
    frames = sessions.build_frames(walk_1m(days=45, seed=11))
    res = BT.run_backtest(frames, BT.BacktestConfig(variants=("V1",)))
    dec = res.results["V1"]["decisions"]
    assert isinstance(dec, pd.DataFrame)
    if len(dec):
        assert set(dec["setup"]) <= set(BT.DETECTORS)


# ---- visual audit: key नसल्यास skip ---------------------------------------------------------------------------------------------------------
def test_visual_audit_skips_quietly_without_api_key(monkeypatch, capsys):
    monkeypatch.setenv("VISUAL_AUDIT_ENABLED", "1")
    monkeypatch.setenv("VISUAL_AUDIT_MODEL", "some-model")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(RVA.cloud_db, "get_effective_upstox_token", lambda t=None: "tok")

    def boom():
        raise AssertionError("client बनवू नये")
    assert RVA.main([], client_factory=boom) == 0
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out
