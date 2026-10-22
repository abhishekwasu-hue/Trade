"""Reading checks from the BANKNIFTY 6-month galleries (OPEN_QUESTIONS "E4b on channel parallels"), both mirrors, synthetic (CI-safe):

1. K6.5 mirror / C lifecycle for a BROKEN LINE (E4 (b) object): E4 (b) reads a broken line as a flipped object (Abhi 22 Oct: close
   beyond + swing beyond = broken (flip); the return from the other side = its retest). A broken line that price closes back through
   on its ORIGINAL side AND builds a swing (of the line's degree) beyond it there is broken again ⇒ dead as a flipped area broken
   again is (owner-orders DECISIONS 27) — never an E4 (b) retest object. A close back WITHOUT a swing formed there is a sweep: the line
   stays broken and its retest still fires. (Replayed: 13 Jul E4b on a 1H channel parallel broken back the day after its break, MAE
   919; 02 Sep E4b on a falling line of lows broken back the same day, MAE 669 — price came onto the line from the original side.)
2. K4 reclaim on the break's own confirming bar (levels): a BROKEN area is reclaimed by a close back on its role side AND a swing
   formed there; when the bar that makes the break KNOWN (its swing beyond confirmed) itself closes back on the role side, that close
   starts the reclaim attempt, so a swing formed at that bar completes it (was: the attempt began one bar later and the swing was lost
   — replayed 14 May: a support "broken" at a gap-up bar that closed far above it, then an E4 (b) bear call from above, MAE 684).
"""
from types import SimpleNamespace as NS

import pytest

from decision3 import entry_models as EM
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import trendline as TL
from tests.test_decision3_entry_models import MID, _bare, _mirror_rows
from tests.test_decision3_zone_answers import _break_case, _zone

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
UP, DOWN = 1, -1
REJECT = 9
# A rising line of lows (95 + 0.5·bar) broken DOWN (closes below from bar 2, the swing low 93.0 at bar 3 known at bar 4). Price then
# closes back ABOVE the line (bars 5 … 7) and a swing high 100.2 forms there (bar 6, confirmed at bar 8); it comes back to the line
# (bars 8 / 9 touch it) and bar 9 is a rejection closing below it.
ROWS = [(96.0, 96.4, 95.2, 96.2, 1.0), (96.2, 96.4, 95.6, 96.1, 1.0), (96.1, 96.2, 94.0, 94.2, 1.0), (94.2, 94.3, 93.0, 93.2, 1.0),
        (93.2, 94.6, 93.1, 94.5, 1.0), (94.5, 97.8, 94.4, 97.7, 1.0), (97.7, 100.2, 97.6, 99.9, 1.0), (99.9, 100.0, 98.9, 99.0, 1.0),
        (99.0, 99.1, 98.0, 98.2, 1.0), (98.2, 99.6, 98.1, 98.3, 1.0)]


def _line_case(mirror, monkeypatch, swing_back=True):
    import decision3.method as M
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None: ("engulf", 1) if t == REJECT else None)
    rows = ROWS
    ln = {"family": "rising line of lows", "kind": "L", "slope_dir": "rising", "degree": 2, "p1": [0, 95.0], "p2": [1, 95.5],
          "slope": 0.5, "touches": 2, "touch_groups": [[0], [1]], "value_t": 0.0, "broken": True, "break_bar": 2,
          "break_side": "down", "state": "BROKEN", "id": "L+:0-1"}
    piv = [NS(kind="H", price=100.2, bar=6, confirm_bar=8)] if swing_back else []
    if mirror:
        rows = _mirror_rows(rows)
        ln = {**ln, "family": "falling line of highs", "kind": "H", "slope_dir": "falling", "p1": [0, 2 * MID - 95.0],
              "p2": [1, 2 * MID - 95.5], "slope": -0.5, "break_side": "up", "id": "H-:0-1"}
        piv = [NS(kind="L", price=2 * MID - p.price, bar=p.bar, confirm_bar=p.confirm_bar) for p in piv]
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [ln])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 4)
    V, _lvl, _d = _bare(rows, [], mirror=False, trend_at=lambda u: "UP" if mirror else "DOWN")
    V.levels.known_pivots = lambda t: [p for p in piv if p.confirm_bar <= t]   # the line's own degree (D2 = level_degree)
    return V, ln, (UP if mirror else DOWN)


@MIRRORS
def test_a_broken_line_broken_back_with_a_swing_is_no_e4b_object(mirror, monkeypatch):
    V, ln, d = _line_case(mirror, monkeypatch)
    assert TL.broken_back_at(V, ln, 7) is None                             # the swing back (bar 6) is not confirmed before bar 8
    assert TL.broken_back_at(V, ln, 8) == 5 and TL.broken_back_at(V, ln, REJECT) == 5   # the run of closes back starts at bar 5
    R = EM.Reader(V)
    assert [t for t in range(4, 8) for _f in R.broken(t, d)[1]] == []
    for t in range(8, len(ROWS)):                                          # known broken back ⇒ never armed, never fired again
        armed, fired = R.broken(t, d)
        assert armed == [] and fired == []


@MIRRORS
def test_a_broken_line_swept_back_without_a_swing_still_fires_its_e4b(mirror, monkeypatch):
    """The same closes back through the line, but no swing forms beyond it there ⇒ a sweep of the retest: still a broken line, the
    rejection at bar 9 is the E4 (b) (as before)."""
    V, ln, d = _line_case(mirror, monkeypatch, swing_back=False)
    assert all(TL.broken_back_at(V, ln, t) is None for t in range(len(ROWS)))
    fired = [(t, f) for t in range(4, len(ROWS)) for f in EM.Reader(V).broken(t, d)[1]]
    assert [t for t, _ in fired] == [REJECT]
    f = fired[0][1]
    assert f["obj"]["area_id"] == "line:" + ln["id"] and f["invalidation"] == pytest.approx(2 * MID - 100.2 if mirror else 100.2)


def test_broken_back_needs_a_broken_line():
    V, _l, _d = _bare(ROWS, [])
    assert TL.broken_back_at(V, {"kind": "L", "broken": False, "break_bar": None, "p1": [0, 95.0], "slope": 0.5}, 9) is None


@pytest.mark.parametrize("mirror", [False, True], ids=["resistance", "support"])
def test_reclaim_counts_the_close_back_on_the_breaks_own_confirming_bar(mirror):
    """resistance 116.3–118 broken up (closes above, the swing 120.5 at bar 20 confirmed at bar 22). Bar 22 — the bar that makes the
    break known — itself closes back BELOW the band, and a swing low forms at bar 22 (confirmed at 24) while the closes stay below ⇒
    the break failed: reclaim at 24, role kept, not BROKEN (so no E4 (b) object). Mirror: a support broken down."""
    m, lv, f = _break_case(True, mirror, tail=[115.0, 115.5, 115.8, 115.6, 115.2], last=("L", 114.7, 22, 24))
    Z = _zone(lv, f)
    ev = [(b, k) for b, k, _ in Z.events if k in ("broken", "reclaim", "flip", "dead")]
    assert ev == [(22, "broken"), (24, "reclaim")], ev
    assert Z.state_at(len(m) - 1) != FL.BROKEN and Z.role_at(len(m) - 1) == (LV.SUP if mirror else LV.RES)
    assert all(x.get("state") != FL.BROKEN for x in lv.snapshot(len(m) - 1) if x["id"] == Z.id)
    # the swing back formed only BEFORE the confirming bar (bar 21, still beyond the band) does not count ⇒ still BROKEN
    m, lv, f = _break_case(True, mirror, tail=[115.0, 115.5, 115.8, 115.6, 115.2], last=("L", 114.7, 21, 24))
    Z = _zone(lv, f)
    assert [(b, k) for b, k, _ in Z.events if k in ("broken", "reclaim", "flip", "dead")] == [(22, "broken")]
    assert Z.state_at(len(m) - 1) == FL.BROKEN
