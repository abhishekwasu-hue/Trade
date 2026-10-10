"""थर v2.2 ⑤ — K ची आतली रेघ: फक्त confirmed बिंदू (known_at), ≥ 2 स्पर्श, trend-दिशेचा close-break ⇒ grade (gate नाही), आरसा, NA."""
from types import SimpleNamespace as NS

import numpy as np

from decision3 import settings as S3
from decision3 import trendline as TL

S = S3.load()


def _V(closes, pivots):
    c = np.array(closes, float)
    A = {"open": c, "high": c + 0.2, "low": c - 0.2, "close": c}
    return NS(s=S, levels=NS(A=A, sig1h=np.full(len(c), 10.0)), res={"pivots": {1: pivots}})


def _K(i_end, i_end_bar):
    return {"open": True, "i_end": i_end, "i_end_bar": i_end_bar}


# DOWN trend (bear call): K वर चढते; रेघ = I_end low 100 (bar 2) + L 103 (bar 6, confirm 8) ⇒ slope 0.75 / bar
CL = [110, 104, 100, 102, 104, 105, 103, 104.5, 106, 107, 108, 109, 107.0, 106]
PIV = [NS(kind="L", price=103.0, bar=6, confirm_bar=8), NS(kind="H", price=105.0, bar=5, confirm_bar=7)]


def test_line_only_after_second_point_confirmed():
    V = _V(CL, PIV)
    assert TL.k_line(V, 7, TL.DOWN, _K(100.0, 2)) is None                         # bar 7: L 103 अजून confirm नाही ⇒ रेघ नाही
    tl = TL.k_line(V, 8, TL.DOWN, _K(100.0, 2))
    assert tl and tl["touches"] >= 2 and tl["slope"] > 0 and not tl["broken"]


def test_break_by_close_in_trend_direction():
    V = _V(CL, PIV)
    tl11 = TL.k_line(V, 11, TL.DOWN, _K(100.0, 2))
    assert not tl11["broken"]                                                     # bar 11: close 109 > रेघ 106.75
    tl12 = TL.k_line(V, 12, TL.DOWN, _K(100.0, 2))
    assert tl12["broken"] and tl12["break_bar"] == 12                            # bar 12: close 107 < रेघ 107.5


def test_mirror_up_trend():
    cl = [200 - (x - 100) for x in CL]
    piv = [NS(kind="H", price=197.0, bar=6, confirm_bar=8)]
    V = _V(cl, piv)
    assert not TL.k_line(V, 11, TL.UP, _K(200.0, 2))["broken"]
    tl = TL.k_line(V, 12, TL.UP, _K(200.0, 2))
    assert tl["broken"] and tl["slope"] < 0


def test_no_line_when_points_do_not_follow_k_or_k_closed():
    V = _V(CL, [NS(kind="L", price=99.0, bar=6, confirm_bar=8)])                # दुसरा low खाली ⇒ K ची रेघ नाही
    assert TL.k_line(V, 12, TL.DOWN, _K(100.0, 2)) is None
    assert TL.k_line(_V(CL, PIV), 12, TL.DOWN, {"open": False, "i_end": 100.0, "i_end_bar": 2}) is None


def test_tl_break_is_evidence_not_gate():
    w = S["evidence_weights"]
    assert w["tl_break"] > 0
    from decision3 import method as M
    ev = {k: False for k in w}
    ev.update(power_shift=True, trap_sweep=True, commit_strong=True, second_attempt=True, level_star=True)
    a = M.conviction({**ev, "tl_break": None}, S)
    b = M.conviction({**ev, "tl_break": False}, S)
    assert a[1] >= b[1]                                                          # NA बेरजेत नाही; अखंड रेघ फक्त grade कमी, नकार नाही
    assert M.conviction({**ev, "tl_break": True}, S)[1] >= a[1]
