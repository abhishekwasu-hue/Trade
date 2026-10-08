"""Chart Reader — KB भाग D चे नवीन पुरावे (PB, LQ, DV, PT, TM, VX) आणि A3 चे व्याख्यात्मक व्हेटो (Abhi 2026-10-08, Knowledge Base)."""
import numpy as np
import pandas as pd

from chart_reader import evidence as E
from chart_reader import settings as CS
from chart_reader import structure as ST

S = dict(CS.DEFAULTS)


def bars_from_closes(c, wick=0.2, start="2021-03-01 09:15", tf="15min"):
    c = [float(x) for x in c]
    o = [c[0]] + c[:-1]
    return pd.DataFrame({"timestamp": pd.date_range(start, periods=len(c), freq=tf), "open": o,
                         "high": [max(a, b) + wick for a, b in zip(o, c)], "low": [min(a, b) - wick for a, b in zip(o, c)], "close": c})


def ohlc(rows, start="2021-03-01 09:15", tf="15min"):
    return pd.DataFrame({"timestamp": pd.date_range(start, periods=len(rows), freq=tf), "open": [r[0] for r in rows],
                         "high": [r[1] for r in rows], "low": [r[2] for r in rows], "close": [r[3] for r in rows]})


def st_dict(**kw):
    base = {"impulse": {"dir": 1, "origin": 100.0, "end": 160.0, "start_bar": 0, "end_bar": 10, "bars": 10, "size_mr": 20.0},
            "side": 1, "correction_type": "zigzag", "entry_point": "C-end", "correction": [160.0, 140.0, 150.0, 132.0],
            "correction_bars": [10, 14, 17, 21], "retrace": 0.47, "overlap": 0.7, "origin_probe": False, "reversal_reasons": [],
            "pullback": "pullback"}
    base.update(kw)
    return base


# ------------------------------------------------------------------------------------------------ PB [K2]
def test_pb_healthy_pullback_plus_10():
    r = E.pullback(st_dict(), S)
    assert r["pts"] == 10 and "[K2]" in r["line"]


def test_pb_missing_overlap_or_depth_is_zero():
    assert E.pullback(st_dict(overlap=0.2), S)["pts"] == 0
    assert E.pullback(st_dict(retrace=0.30), S)["pts"] == 0                               # उथळ (< 38.2%)
    assert E.pullback(st_dict(correction_type="triangle", retrace=0.30), S)["pts"] == 10  # triangle ला खोली अट नाही


def test_pb_danger_signs_minus_10():
    assert E.pullback(st_dict(reversal_reasons=["counter_move_impulsive"]), S)["pts"] == -10
    assert E.pullback(st_dict(retrace=0.85), S)["pts"] == -10                             # > 80% आणि area / sweep नाही
    assert E.pullback(st_dict(retrace=0.85), S, deep_support=True)["pts"] == 0            # तिथे ठोस area / sweep ⇒ दंड नाही


def test_pb_near_origin_or_probe_minus_15_and_acceptance_is_veto():
    assert E.pullback(st_dict(retrace=0.93), S)["pts"] == -15
    assert E.pullback(st_dict(origin_probe=True, retrace=1.02), S)["pts"] == -15
    r = E.pullback(st_dict(reversal_reasons=["impulse_origin_acceptance"]), S)
    assert r["pts"] == 0 and r.get("veto")


def path(points, step=2.0, wick=0.4, start="2021-03-01 09:15"):
    closes = [float(points[0])]
    for a, b in zip(points[:-1], points[1:]):
        n = max(int(round(abs(b - a) / step)), 1)
        closes += list(np.linspace(a, b, n + 1)[1:])
    return bars_from_closes(closes, wick=wick, start=start)


def test_structure_origin_acceptance_uses_real_break_and_probe_is_not_acceptance():
    p0 = [100, 104, 100, 104, 100]
    acc = ST.read(path(p0 + [100, 160, 130, 142, 94]), S)                                 # buffer पलीकडे closes, reclaim नाही
    assert "impulse_origin_acceptance" in acc["reversal_reasons"] and acc["pullback"] == "reversal"
    probe = path(p0 + [100, 160, 130, 142, 102])
    i = len(probe) - 1
    probe.loc[i, "low"] = 98.8                                                             # wick origin पलीकडे, close आत
    r = ST.read(probe, S)
    assert "impulse_origin_acceptance" not in r["reversal_reasons"] and r["origin_probe"] is True
    assert r["overlap"] is not None and 0.0 <= r["overlap"] <= 1.0


# ------------------------------------------------------------------------------------------------ LQ [K5]
def _lq_df(last):
    rows = [(150, 150.5, 149.5, 150)] * 10 + [(141, 141.5, 140.0, 140.5), (142, 146, 141.5, 145), (145, 150, 144.5, 149),
                                              (149, 149.5, 143, 143.5), (143.5, 144, 141.5, 142), last]
    return ohlc(rows)


def test_lq_sweep_of_a_end_and_reclaim():
    st = st_dict(correction=[160.0, 140.0, 150.0, 139.5], correction_bars=[5, 10, 12, 15])
    df = _lq_df((142, 142.5, 139.5, 142.3))                                               # A low 140 च्या 0.5 पलीकडे, close परत वर
    r = E.liquidity(df, st, [], 1, S, mr=1.0)
    assert r["pts"] == 8 and r["pool"] == "A-end" and "[K5]" in r["line"]                 # lower wick ≥ 50% ⇒ +3
    df2 = _lq_df((141.5, 142.5, 139.5, 140.6))                                            # wick लहान
    assert E.liquidity(df2, st, [], 1, S, mr=1.0)["pts"] == 5


def test_lq_no_reclaim_or_too_deep_is_zero():
    st = st_dict(correction=[160.0, 140.0, 150.0, 139.0], correction_bars=[5, 10, 12, 15])
    assert E.liquidity(_lq_df((142, 142.5, 139.0, 139.4)), st, [], 1, S, mr=1.0)["pts"] == 0     # close आत नाही
    assert E.liquidity(_lq_df((142, 142.5, 138.5, 141.0)), st, [], 1, S, mr=1.0)["pts"] == 0     # 1.5 MR — sweep नाही, break
    assert E.liquidity(_lq_df((142, 142.5, 139.5, 142.3)), st_dict(correction=[160.0, 140.0], correction_bars=[5, 10]), [], 1, S,
                       mr=1.0)["pts"] == 0                                                # A-end अजून pool नाही (B नाही)


def test_lq_pdl_pool_from_candidates():
    st = st_dict(correction=[160.0, 150.0], correction_bars=[5, 10])
    cands = [{"id": "PDL", "tool": "k", "low": 139.75, "high": 140.25, "role": "SUPPORT"}]
    assert E.liquidity(_lq_df((142, 142.5, 139.5, 142.3)), st, cands, 1, S, mr=1.0)["pool"] == "PDL"


def test_lq_gap_open_through_pool_is_not_a_sweep():
    """§8.2 (7 Oct 09:30 सारखं, सर्वसाधारण): bear बाजूचा pool (A-end high 150) — gap down open pool च्या वर (152), bar खाली पार करून
    close खाली. किंमत pool कडे खालून आली नाही ⇒ sweep नाही. तसंच pool आधीच पार झाला असेल तर नंतरचा poke sweep नाही."""
    st = st_dict(side=-1, impulse={"dir": -1, "origin": 200.0, "end": 140.0, "start_bar": 0, "end_bar": 10, "bars": 10, "size_mr": 20.0},
                 correction=[140.0, 150.0, 144.0, 151.0], correction_bars=[10, 12, 14, 16])
    rows = [(160, 160.5, 159.5, 160)] * 10 + [(141, 141.5, 140, 140.5), (141, 149.5, 140.8, 149), (149, 150, 145, 145.5),
                                              (145.5, 146, 143.5, 144), (144, 148, 143.8, 147.5), (147.5, 148.5, 147, 148)]
    gap_bar = (152.0, 152.4, 148.0, 148.6)                                                 # open pool च्या वर, खाली पार, close खाली
    df = ohlc(rows + [gap_bar])
    assert E.liquidity(df, st, [], -1, S, mr=1.0)["pts"] == 0
    real = (148.0, 150.5, 147.8, 148.3)                                                    # खालून आलं, wick ने 0.5 पार, परत खाली close
    assert E.liquidity(ohlc(rows + [real]), st, [], -1, S, mr=1.0)["pts"] > 0
    used = rows[:-1] + [(147.5, 151.5, 147, 148)]                                          # pool आधीच पार झाला
    assert E.liquidity(ohlc(used + [real]), st, [], -1, S, mr=1.0)["pts"] == 0


# ------------------------------------------------------------------------------------------------ DV [K10.2]
def _div_series():
    c = [100 + (i % 2) * 0.5 for i in range(20)]
    x = 100
    while x < 160:
        x += 3
        c.append(x)
        if x < 160:
            x -= 1
            c.append(x)
    i0, iE = 19, len(c) - 1
    c += list(np.linspace(c[-1], c[-1] - 40, 21)[1:])
    iA = len(c) - 1
    c += list(np.linspace(c[-1], c[-1] + 10, 6)[1:])
    iB = len(c) - 1
    x, tgt = c[-1], c[iA] - 4
    while x > tgt:
        x -= 2.5
        c.append(x)
        if x > tgt:
            x += 1.0
            c.append(x)
    iC = len(c) - 1
    c += [c[-1] + 1.5, c[-1] + 3]
    return c, (i0, iE, iA, iB, iC)


def test_rsi_wilder_basic():
    r = E.rsi(list(range(1, 40)))
    assert np.isnan(r[:14]).all() and r[-1] == 100.0
    r = E.rsi([10, 11] * 20)
    assert 40 < r[-1] < 60


def test_dv_regular_bullish_at_c_end():
    c, (i0, iE, iA, iB, iC) = _div_series()
    df = bars_from_closes(c)
    st = st_dict(impulse={"dir": 1, "origin": c[i0], "end": c[iE], "start_bar": i0, "end_bar": iE, "bars": iE - i0, "size_mr": 20.0},
                 correction=[c[iE], c[iA], c[iB], c[iC]], correction_bars=[iE, iA, iB, iC])
    r = E.divergence(df, st, 1, S, mr=1.0)
    assert r["pts"] >= 5 and "regular" in r["line"] and "[K10.2]" in r["line"]


def test_dv_needs_confirmed_pivot_no_lookahead():
    c, (i0, iE, iA, iB, iC) = _div_series()
    df = bars_from_closes(c[: iC + 1])                                                    # C नंतर bars नाहीत ⇒ pivot confirmed नाही
    st = st_dict(impulse={"dir": 1, "origin": c[i0], "end": c[iE], "start_bar": i0, "end_bar": iE, "bars": iE - i0, "size_mr": 20.0},
                 correction=[c[iE], c[iA], c[iB], c[iC]], correction_bars=[iE, iA, iB, iC])
    assert "regular" not in E.divergence(df, st, 1, S, mr=1.0)["line"]


# ------------------------------------------------------------------------------------------------ PT [K11]
def test_pt_flag_plus_5():
    c = [100.0] * 20 + list(np.linspace(100, 160, 11)[1:]) + list(np.linspace(160, 150, 9)[1:])
    df = bars_from_closes(c)
    st = st_dict(impulse={"dir": 1, "origin": 100.0, "end": 160.0, "start_bar": 20, "end_bar": 29, "bars": 9, "size_mr": 30.0},
                 retrace=0.17)
    r = E.patterns(df, st, 1, S, mr=2.0)
    assert r["pts"] == 5 and "flag" in r["line"]


def test_pt_double_top_with_neckline_break_minus_10():
    c = [130.0] * 15 + list(np.linspace(130, 160, 11)[1:]) + list(np.linspace(160, 148, 7)[1:]) + list(np.linspace(148, 160.3, 7)[1:])
    c += list(np.linspace(160.3, 146, 8)[1:])                                            # trough 148 च्या खाली close
    df = bars_from_closes(c)
    e = int(np.argmax(c))
    st = st_dict(impulse={"dir": 1, "origin": 148.0, "end": float(max(c)), "start_bar": e - 6, "end_bar": e, "bars": 6, "size_mr": 6.0},
                 retrace=1.1)
    r = E.patterns(df, st, 1, S, mr=1.0)
    assert r["pts"] == -10 and "double top" in r["line"]


def test_pt_nothing_is_zero():
    df = path([100, 104, 100, 104, 100, 100, 160, 140, 150, 132])
    st = ST.read(df, S)
    assert E.patterns(df, st, 1, S, mr=2.8)["pts"] in (0, 3, 5)


# ------------------------------------------------------------------------------------------------ TM / VX [K14]
def test_tm_opening_and_expiry_morning():
    assert E.time_of_day("2021-03-01 09:45", S)["pts"] == -5                              # सोमवार 09:45
    assert E.time_of_day("2021-03-01 14:00", S)["pts"] == 0
    assert E.time_of_day("2021-03-02 10:30", S)["pts"] == -3                              # मंगळवार (expiry) सकाळ
    assert E.time_of_day("2021-03-02 09:45", S)["pts"] == -5                              # कमाल −5
    assert E.time_of_day("2021-03-02 13:00", S)["pts"] == 0
    assert E.time_of_day("2021-03-03 10:30", S, expiry_day=True)["pts"] == -3             # holiday shift ⇒ caller flag


def test_vx_jump_falling_and_no_data():
    v = pd.DataFrame({"bar_end": pd.to_datetime(["2021-03-01 10:00", "2021-03-01 12:00", "2021-03-01 14:00"]), "close": [13.0, 14.0, 12.7]})
    assert E.vix(v, "2021-03-01 10:00", "2021-03-01 12:00", S)["pts"] == -5               # +7.7%
    assert E.vix(v, "2021-03-01 10:00", "2021-03-01 14:00", S)["pts"] == 2                # −2.3%
    assert E.vix(None, "2021-03-01 10:00", "2021-03-01 14:00", S)["pts"] == 0
    assert E.vix(v, "2021-03-01 10:00", "2021-03-01 11:00", S)["pts"] == 0                # भविष्यातला VIX वाचत नाही
    m = pd.DataFrame({"timestamp": pd.to_datetime(["2021-03-01 09:59", "2021-03-01 10:00"]), "close": [13.0, 20.0]})
    # 10:00 चा 1m bar 10:01 ला बंद ⇒ 10:00 च्या signal ला वापरत नाही (timestamp = bar start)
    assert "20.00" not in E.vix(m, "2021-03-01 09:59", "2021-03-01 10:00", S)["line"]


# ------------------------------------------------------------------------------------------------ A3 vetoes
def test_veto_elliott_clear_count_only():
    assert E.vetoes(st_dict(), {"state": "a_end_or_in_b", "clear": True}, {}, [], {}, 1, None, S, 1.0)
    assert not E.vetoes(st_dict(), {"state": "a_end_or_in_b", "clear": False}, {}, [], {}, 1, None, S, 1.0)


def test_veto_origin_acceptance_and_magnet():
    assert E.vetoes(st_dict(reversal_reasons=["impulse_origin_acceptance"]), {}, {}, [], {}, 1, None, S, 1.0)
    trig = ohlc([(140, 141, 139, 140.5)] * 3)
    mag = [{"id": "M1", "low": 140.0, "high": 141.0, "state": "MAGNET"}]
    assert any("MAGNET" in v for v in E.vetoes(st_dict(), {}, {}, mag, {}, 1, trig, S, 1.0))
    far = [{"id": "M2", "low": 150.0, "high": 151.0, "state": "MAGNET"}]
    assert not E.vetoes(st_dict(), {}, {"area": {"low": 139.0, "high": 140.0}}, far, {}, 1, trig, S, 1.0)


def test_gap_veto_moved_to_gap_rule():
    """gap setup B चा व्हेटो आता chart_reader/gap.py (GAP_NO_PULLBACK, सगळे वर्ग) — vetoes मध्ये दुहेरी ओळ नाही."""
    gap = {"has_gap": True, "direction": "up", "class": "G3"}
    up = ohlc([(100 + i, 101.1 + i, 100.5 + i, 101 + i) for i in range(5)], start="2021-03-01 09:15")
    assert not any("[K13]" in v for v in E.vetoes(st_dict(), {}, {}, [], gap, 1, up, S, 1.0))


def test_flat_b_near_impulse_end_is_not_a_double_top():
    """Review: flat मध्ये B ≈ impulse टोक आणि C, A च्या पलीकडे (K3: सामान्य) ⇒ PT −10 नाही."""
    c = [130.0] * 15 + list(np.linspace(130, 160, 11)[1:]) + list(np.linspace(160, 148, 7)[1:]) + list(np.linspace(148, 160.3, 7)[1:])
    c += list(np.linspace(160.3, 146, 8)[1:])
    df = bars_from_closes(c)
    e = 25
    b = int(np.argmax(c[e + 3:])) + e + 3
    st = st_dict(impulse={"dir": 1, "origin": 130.0, "end": 160.0, "start_bar": 15, "end_bar": e, "bars": 10, "size_mr": 30.0},
                 correction_type="flat", correction=[160.0, 148.0, 160.3, 146.0], correction_bars=[e, e + 6, b, len(c) - 1], retrace=0.47)
    assert E.patterns(df, st, 1, S, mr=1.0)["pts"] != -10
