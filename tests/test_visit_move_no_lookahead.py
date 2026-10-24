"""B flag 1 (E53): the move start of a visit is a swing CONFIRMED by the decision bar — a swing whose confirmation bar is after t is
never used (no look-ahead). E53: D0 L 55,587.10 at 10-15 15:00 confirms at the 15:15 bar ⇒ move start 15:00 only from t = 15:15."""
from types import SimpleNamespace as NS

from decision3 import engine as E3


def _stub():
    piv = [NS(kind="L", bar=10, confirm_bar=12, price=95.0), NS(kind="L", bar=20, confirm_bar=21, price=96.0),
           NS(kind="H", bar=15, confirm_bar=16, price=104.0)]
    return NS(levels=NS(_known0=piv), visit_end_new=False, visit_swings=lambda: piv)


def test_away_swing_used_only_from_its_confirmation_bar():
    V = _stub()
    aw = lambda t: E3.V22._away_swings(V, t, 100.0, 102.0, -1)          # noqa: E731 — supply ⇒ swing lows below the area
    assert aw(11) == [] and aw(12) == [10]
    assert aw(20) == [10] and aw(21) == [10, 20]                      # the bar-20 low (E53's 15:00) only once confirmed (bar 21 = 15:15)


def test_move_from_never_reads_an_unconfirmed_swing():
    if not hasattr(E3.V22, "move_from"):                              # the B2 move start lives on branch visitmove
        return
    V = _stub()
    V._away_swings = lambda t, lo, hi, d, born=0: E3.V22._away_swings(V, t, lo, hi, d, born)
    assert E3.V22.move_from(V, 20, 100.0, 102.0, -1) == 10
    assert E3.V22.move_from(V, 21, 100.0, 102.0, -1) == 20
