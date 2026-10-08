"""Chart Reader — pullback वि. reversal, correction प्रकार (Abhi 2026-10-08, दुसरी दुरुस्ती).

मुख्य setup = PULLBACK END: impulse नंतरचा corrective pullback (zigzag / flat / triangle) पूर्ण होताना, impulse दिशेने entry.
Reversal चे पुरावे (counter-move impulsive, impulse origin वर real break, major level वर acceptance) ⇒ pullback नाही.
"""
import numpy as np
import pandas as pd

from chart_reader import settings as CS
from chart_reader import structure as ST

S = dict(CS.DEFAULTS)


def path(points, step=2.0, wick=0.4, start="2021-03-01 09:15", tf="15min"):
    """Pivot किंमतींमधून सरळ रेषेतले bars (प्रत्येक bar ≈ step points), लहान wicks — synthetic, गोंगाट नाही."""
    closes = [float(points[0])]
    for a, b in zip(points[:-1], points[1:]):
        n = max(int(round(abs(b - a) / step)), 1)
        closes += list(np.linspace(a, b, n + 1)[1:])
    o = [closes[0]] + closes[:-1]
    c = closes
    h = [max(x, y) + wick for x, y in zip(o, c)]
    lo = [min(x, y) - wick for x, y in zip(o, c)]
    ts = pd.date_range(start, periods=len(c), freq=tf)
    return pd.DataFrame({"timestamp": ts, "open": o, "high": h, "low": lo, "close": c})


def warm(points):
    p0 = float(points[0])
    return [p0, p0 + 4, p0, p0 + 4, p0] + list(points)              # median range साठी थोडा आधीचा इतिहास (त्याच किंमतीवर)


def test_zigzag_c_end_is_entry_point_with_impulse_direction():
    df = path(warm([100, 160, 140, 150, 132]))
    r = ST.read(df, S)
    assert r["impulse"]["dir"] == 1 and r["side"] == 1                                    # bull put — impulse दिशेने
    assert r["correction_type"] == "zigzag" and r["entry_point"] == "C-end"
    assert r["pullback"] == "pullback" and not r["reversal_reasons"]
    assert 0.38 <= r["retrace"] <= 0.786


def test_flat_c_end_is_entry_point():
    df = path(warm([100, 160, 140, 159, 136]))
    r = ST.read(df, S)
    assert r["correction_type"] == "flat" and r["entry_point"] == "C-end" and r["pullback"] == "pullback"


def test_triangle_e_end_is_entry_point():
    df = path(warm([100, 160, 140, 155, 144, 152, 146]))
    r = ST.read(df, S)
    assert r["correction_type"] == "triangle" and r["entry_point"] == "E-end" and r["pullback"] == "pullback"


def test_bear_side_mirror_zigzag():
    df = path(warm([200, 140, 160, 150, 168]))
    r = ST.read(df, S)
    assert r["impulse"]["dir"] == -1 and r["side"] == -1 and r["correction_type"] == "zigzag" and r["entry_point"] == "C-end"


def test_impulsive_counter_move_is_reversal_no_entry():
    df = path(warm([100, 160, 145, 152, 125, 131, 112]))                                 # 5 legs, LL/LH ⇒ impulsive
    r = ST.read(df, S)
    assert r["pullback"] == "reversal" and "counter_move_impulsive" in r["reversal_reasons"] and r["entry_point"] is None


def test_impulse_origin_real_break_is_reversal():
    df = path(warm([100, 160, 130, 142, 94]))
    r = ST.read(df, S)
    assert r["pullback"] == "reversal" and "impulse_origin_acceptance" in r["reversal_reasons"]      # elliott/breaks.py real break


def test_acceptance_beyond_major_level_is_reversal():
    df = path(warm([100, 160, 140, 150, 120, 121, 119, 120]), step=1.0)
    r = ST.read(df, S, major_zones=[(128.0, 132.0)])                                     # zone खाली दोन+ closes
    assert "acceptance_major_level" in r["reversal_reasons"] and r["pullback"] == "reversal"


def test_correction_weakening_score_in_unit_interval_and_lines():
    df = path(warm([100, 160, 140, 150, 132]))
    r = ST.read(df, S)
    assert 0.0 <= r["correction_weakening"] <= 1.0 and r["facts"]


def test_truncation_invariance():
    df = path(warm([100, 160, 140, 150, 132, 145, 150]))
    cut = 60
    a = ST.read(df.iloc[:cut].reset_index(drop=True), S)
    b = ST.read(df.iloc[:cut].copy().reset_index(drop=True), S)
    assert a == b                                                                         # तेच इनपुट ⇒ तेच (state नाही)
    full_then_cut = ST.read(df, S, upto=cut - 1)
    assert full_then_cut["correction_type"] == a["correction_type"] and full_then_cut["impulse"] == a["impulse"]


def test_flat_c_short_of_a_end_is_not_yet_entry():
    df = path(warm([100, 160, 140, 159, 150]))                                           # C = 9 < 0.9 × A (20) ⇒ C चालू
    r = ST.read(df, S)
    assert r["correction_type"] == "flat" and r["entry_point"] is None and r["c_progress"] < 0.9


def test_correction_extreme_reported():
    df = path(warm([100, 160, 140, 150, 132]))
    r = ST.read(df, S)
    assert r["correction_extreme"] <= 132.0
