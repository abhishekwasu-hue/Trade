"""Track t1 scope addition (Abhi 21 Oct): `daily_leg_read` = compare | elliott — a Daily leg's nature by comparison with its
neighbouring legs (decision3/legs_compare) instead of Elliott counts + legs2 percentiles; default stays "elliott" (today) until Abhi's ✅.
Plus: the Elliott display pieces are admin diagnostics (off by default)."""
import ast
import inspect

import numpy as np
import pytest

from decision3 import daily as DD
from decision3 import daily_legs as DL
from decision3 import mtf_state as MS
from decision3 import settings as S3
from tests.test_decision3 import daily_from_path

S = {"daily_min_sessions": 3, "daily_sigma_sessions": 3}
PATH = [100, 120, 110, 130, 118, 140, 125, 150, 120, 135, 110, 128, 100]


def test_setting_registered_default_elliott_and_validated():
    assert S3.DEFAULTS["daily_leg_read"] == "elliott"
    reg = S3.REGISTER["daily_leg_read"]
    assert reg[2] == "Abhi नियम" and "Abhi 21 Oct" in reg[3]
    with pytest.raises(ValueError):
        DD.fold(daily_from_path(PATH, legs=5), {**S, "daily_leg_read": "count"})


def test_default_fold_is_todays_elliott_reading():
    d = daily_from_path(PATH, legs=5)
    a = DD.fold(d, S)
    b = DD.fold(d, {**S, "daily_leg_read": "elliott"})
    assert [(x.trend, x.phase, x.why) for x in a] == [(x.trend, x.phase, x.why) for x in b]


def _bars(rows):
    o, h, l, c = (np.array([r[k] for r in rows], float) for k in range(4))
    return {"o": o, "h": h, "l": l, "c": c}


def test_compare_classify_by_neighbours():
    P = DD.DPivot
    ts = __import__("pandas").Timestamp("2030-01-01")
    rows = [(100, 100, 100, 100)]
    x = 100.0
    for _ in range(6):                                             # slow overlapping fall 100 ⇒ ~94
        rows.append((x, x + 3, x - 4, x - 1)); x -= 1
    for _ in range(4):                                             # fast clean rise
        rows.append((x, x + 10, x, x + 10)); x += 10
    for _ in range(6):                                             # slow overlapping fall
        rows.append((x, x + 3, x - 4, x - 1)); x -= 1
    A = _bars(rows)
    seq = [P("H", 103.0, 0, ts, 1, ts), P("L", 90.0, 6, ts, 7, ts), P("H", 134.0, 10, ts, 11, ts), P("L", 120.0, 16, ts, 16, ts)]
    up = DL.compare_classify(A, seq, 6, 94.0, 10, 134.0, 16)
    assert up["kind"] == "impulse" and up["form"] == "compare" and up["C"] is None and "larger bodies" in up["why"]
    dn = DL.compare_classify(A, seq, 10, 134.0, 16, 128.0, 16)
    assert dn["kind"] == "corrective"
    assert DL.tag(up).startswith("impulse (vs neighbours")
    lone = DL.compare_classify(A, [], 6, 94.0, 10, 134.0, 10)
    assert lone["kind"] == "unclear" and lone["c_cls"] == "NA"


def test_compare_fold_runs_and_has_no_look_ahead():
    d = daily_from_path(PATH, legs=5)
    sc = {**S, "daily_leg_read": "compare"}
    full = DD.fold(d, sc)
    assert {x.trend for x in full} <= {"UP", "DOWN", "RANGE", "NEUTRAL", "UNKNOWN"}
    for k in (25, 40, len(d) - 3):
        cut = DD.fold(d.iloc[:k].reset_index(drop=True), sc)
        assert [(x.trend, x.phase, None if x.protected is None else x.protected.price) for x in cut] == \
            [(x.trend, x.phase, None if x.protected is None else x.protected.price) for x in full[:k]]


def test_compare_path_uses_no_elliott_or_percentiles():
    """Under compare, read_counter / unfolded_123 / complete_impulse_start / c_class are never called."""
    d = daily_from_path(PATH, legs=5)
    called = []
    saved = {n: getattr(DL, n) for n in ("read_counter", "unfolded_123", "c_class", "classify")}
    try:
        for n in saved:
            setattr(DL, n, (lambda name: (lambda *a, **k: called.append(name) or saved[name](*a, **k)))(n))
        DD.fold(d, {**S, "daily_leg_read": "compare"})
        assert called == []
        DD.fold(d, {**S, "daily_leg_read": "elliott"})              # the same fixture does reach those readers under elliott
        assert called
    finally:
        for n, f in saved.items():
            setattr(DL, n, f)


def test_mtf_state_does_not_use_rhea_range():
    tree = ast.parse(inspect.getsource(MS))
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not {"rhea", "fold", "all_structure", "rng_ratio"} & names
    assert "swings2.structure" not in {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}


def test_labels_and_trend_use_c13_equal():
    p = [MS.SP("L", 100, 0, None, 1), MS.SP("H", 120, 5, None, 6), MS.SP("L", 110, 10, None, 11), MS.SP("H", 119.5, 15, None, 16)]
    eq = lambda later, earlier: later.kind == "H" and abs(later.price - earlier.price) <= 1   # noqa: E731 — stand-in for C-13
    assert MS.labels(p, eq)[-1] == "EQH" and MS.labels(p)[-1] == "LH"
    assert MS.trend_of(p, eq) == MS.RANGE


def test_daily_swings_build_elliott_is_debug_only():
    from decision3 import daily_swings as DS
    sig = inspect.signature(DS.build)
    assert sig.parameters["with_elliott"].default is False and sig.parameters["elliott_debug"].default is False
    d = daily_from_path(PATH * 3, legs=5)
    v = DS.build(d, s=S, window=len(d))
    assert v["elliott"] == {"error": "disabled"}
    objs = v["q15"]["objects"]
    assert all(c["shape"] is None and c["marks"] == [] for c in objs["corrections"])
    assert all(lg["family"] is None and not lg["verified"] for lg in objs["impulses"])


def test_compare_mixed_or_unclear_is_not_corrective_for_the_nature_gate(monkeypatch):
    """Mirror of the elliott semantics (nature_ok: "C नाही; रचना corrective नाही ⇒ pass"): under compare only a CORRECTION verdict is
    corrective — a mixed / nothing-to-compare leg never blocks the Q28 / Q36 gate. With every leg read "unclear", the gate on = gate off."""
    unclear = {"kind": "unclear", "structure": "unclear", "form": "compare", "n": 1, "C": None, "c_cls": "mixed", "why": "mixed"}
    monkeypatch.setattr(DL, "compare_classify", lambda *a, **k: dict(unclear))
    d = daily_from_path(PATH * 2, legs=5)
    on = DD.fold(d, {**S, "daily_leg_read": "compare", "daily_start_nature_gate": True})
    off = DD.fold(d, {**S, "daily_leg_read": "compare", "daily_start_nature_gate": False})
    assert [(x.trend, x.phase) for x in on] == [(x.trend, x.phase) for x in off]
    assert any(x.trend in ("UP", "DOWN") for x in on)
    corr = {**unclear, "kind": "corrective", "structure": "corrective", "c_cls": "correction"}
    monkeypatch.setattr(DL, "compare_classify", lambda *a, **k: dict(corr))
    blocked = DD.fold(d, {**S, "daily_leg_read": "compare", "daily_start_nature_gate": True})
    assert not any(x.trend in ("UP", "DOWN") for x in blocked)          # a correction verdict on both legs ⇒ no trend start
