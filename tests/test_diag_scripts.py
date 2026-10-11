"""Degree निदान + zone संरचनात्मक मृत्यू scripts (फक्त मोजमाप) — helpers, तारीख-मुक्त code."""
import os
from types import SimpleNamespace

import numpy as np

from scripts import degree_diag as DD
from scripts import zone_structural_death as ZD
from tests.test_legs2 import DATE_RX_I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def P(kind, price, bar, cb=None):
    return SimpleNamespace(kind=kind, price=price, bar=bar, confirm_bar=bar + 2 if cb is None else cb)


def test_unknown_reason_names_missing_condition():
    assert DD.unknown_reason([P("H", 10, 1), P("L", 5, 2)]) == "H 1 आणि L 1 (< 2)"
    assert DD.unknown_reason([P("H", 10, 1), P("H", 11, 3), P("L", 5, 2)]) == "L 1 (< 2)"
    assert DD.unknown_reason([P("H", 10, 1), P("H", 11, 3), P("L", 5, 2), P("L", 6, 4)]) is None


def test_first_swing_nearest_beyond_and_known_only():
    ps = [P("H", 110, 3), P("H", 105, 6), P("H", 104, 20), P("L", 90, 8)]
    s = ZD.first_swing(ps, "seller", 100.0, 102.0, tref=10)
    assert s.price == 105                                                        # 104 चा H tref ला confirm नाही (lookahead नाही)
    assert ZD.first_swing(ps, "buyer", 95.0, 97.0, tref=12).price == 90
    assert ZD.first_swing(ps, "buyer", 85.0, 87.0, tref=12) is None
    close = np.full(30, 100.0)
    close[8] = 106.0                                                              # 105 चा H tref आधीच तुटला ⇒ पुढचा 110
    assert ZD.first_swing(ps, "seller", 100.0, 102.0, tref=10, close=close).price == 110


def test_broken_and_touches_with_reversal():
    n = 40
    c = np.full(n, 99.0)
    h, l = c + 0.5, c - 0.5
    h[10], l[10] = 101.0, 99.0                                                    # स्पर्श 1 (seller zone 100–102), मग खाली 3
    l[12] = 96.0
    h[20], l[20] = 100.5, 99.5                                                    # स्पर्श 2, उलट नाही
    c[30] = 106.0                                                                 # swing 105 तुटला
    sig = np.full(n, 2.0)
    b = ZD.broken_at(c, 105.0, "seller", 5)
    assert b == 30
    ep, rev = ZD.touches(h, l, sig, 100.0, 102.0, "seller", 5, b)
    assert ep == [10, 20] and rev == [True, False]


def test_scripts_date_free():
    for f in ("degree_diag.py", "zone_structural_death.py"):
        src = open(os.path.join(ROOT, "scripts", f), encoding="utf-8").read()
        assert not [ln for ln in src.splitlines() if any(rx.search(ln) for rx in DATE_RX_I)], f
