"""(4) 9 Oct 2026 blind spot (docs/reports/v22_missed_levels_touch.md): a broken support that flipped to supply (spec ② (c)) was killed
by the sharp fall that followed the break, because death is judged on the ORIGINAL role's side (Q2 default "role0"). With
`level_death_side` = "role" (Q2 alternative, OPEN_QUESTIONS Q2 / TL1) death is judged on the current role's side and the flipped
supply stays alive for the retest. Default "role" (TL1, Abhi मंजूर); "role0" kept as an explicit setting. Mirrored (broken resistance ⇒ demand)."""
import pytest

from decision3 import levels as LV
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

CLOSES = [110, 104, 96, 92, 90.5, 95, 99, 103, 108, 112, 109, 104, 101, 99, 97, 101, 105, 110, 108, 104, 100,
          94, 93, 92, 91.5, 89,                                           # support (≈96.5) तुटला ⇒ 3 closes ⇒ flip; मग swing 90 close ने तुटला
          92, 95, 96.8, 94]                                               # परत खालून supply मध्ये (retest), नकार
PIV = [("H", 113, 0, 1), ("L", 90.0, 4, 6), ("H", 113, 9, 11), ("L", 96.5, 14, 16)]
T_BREAK = 25                                                              # swing 90 (mirror 110) close ने तुटला


def _flip_case(mirror, side=None):
    f = (lambda x: 200.0 - x) if mirror else (lambda x: float(x))
    closes = [f(c) for c in CLOSES]
    m = m15_from(closes, **({"highs": {4: f(90.0)}} if mirror else {"lows": {4: 90.0}}))
    piv = [P(("L" if k == "H" else "H") if mirror else k, f(p), b, cb) for k, p, b, cb in PIV]
    lv = LV.Levels(res_of(m, piv), s=None if side is None else {"level_death_side": side})
    L = [x for x in lv.L if abs(x.anchor - f(96.5)) < 1e-6][0]
    return m, lv, L


@pytest.mark.parametrize("mirror", [False, True])
def test_broken_support_flipped_to_supply_survives_the_fall_when_death_side_is_role(mirror):
    m, lv, L = _flip_case(mirror, "role")
    n = len(m)
    t_flip = next(b for b, k, _ in L.events if k == "flip")
    assert t_flip < T_BREAK and L.role_at(T_BREAK) == (LV.SUP if mirror else LV.RES)
    assert L.alive(n - 1) and L.dead_bar is None                            # flip नंतर जुन्या बाजूचा swing तुटला ⇒ मृत्यू नाही
    t_retest = n - 2
    lo, hi = L.band_at(t_retest)
    assert m["low"].iloc[t_retest] <= hi and m["high"].iloc[t_retest] >= lo  # retest पट्ट्यात
    assert any(x["id"] == L.id for x in lv.active(t_retest, "UP" if mirror else "DOWN"))   # trade-बाजूचा level: engine ला दिसतो


@pytest.mark.parametrize("mirror", [False, True])
def test_default_is_role_and_explicit_role0_keeps_old_q2_behaviour(mirror):
    assert S3.DEFAULTS["level_death_side"] == "role"                        # TL1 (Abhi मंजूर)
    _, _, L = _flip_case(mirror)                                            # default ⇒ flipped supply जिवंत
    assert L.dead_bar is None
    _, _, L0 = _flip_case(mirror, "role0")                                  # जुना Q2 (मूळ भूमिका) ⇒ मेला
    assert L0.dead_bar == T_BREAK


def test_level_death_side_rejects_unknown_value():
    m = m15_from(CLOSES, lows={4: 90.0})
    with pytest.raises(ValueError):
        LV.Levels(res_of(m, [P(*x) for x in PIV]), s={"level_death_side": "both"})
