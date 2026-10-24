"""DECISIONS 56 (Abhi, owner rule) — layer 5 RSI divergence:
  L5-b: the push still FORMING at the decision bar counts as a push (marked "forming"; read only from bars <= t; "confirmed" once its swing
        confirms) — engine.rsi_divergence, the one read behind both trigger modes (15M read / 5M read5) and the legacy decide;
  L5-c: RSI divergence is read at the retest of a broken LINE like at any area — the move into the retest begins at the last swing built
        away from the line on the side price comes from, after its break, before the revisit (entry_models.Reader.line_move_from), wired
        in the 15M reader (read) and the 5M reader (read5).
Synthetic, both mirrors, no look-ahead (data cut at t = full data at t). Evidence only: never a gate."""
from types import SimpleNamespace as NS

import numpy as np
import pytest

from decision3 import engine as E3
from decision3 import entry_models as EM
from decision3 import entry_models5 as EM5
from decision3 import trendline as TL
from tests.test_decision3_entry_models import MID, _bare, _ltf_from, _mirror_rows
from tests.test_rsi_divergence import build, frame, piv, rsi_with

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
N = 40


def _case(mirror):
    """The move begins at its own swing (bar 15); one confirmed push inside it (18), then the next push runs to bar 25 (a new extreme,
    RSI weaker) — its swing confirms only at bar 28."""
    if not mirror:
        df = frame(N, highs={10: 110.0, 18: 104.0, 25: 106.0}, lows={15: 95.0, 21: 100.0})
        kinds, rsi = ("H", "L"), rsi_with(N, {10: 70.0, 18: 68.0, 25: 65.0})
    else:
        df = frame(N, highs={15: 105.0, 21: 100.0}, lows={10: 90.0, 18: 96.0, 25: 94.0})
        kinds, rsi = ("L", "H"), rsi_with(N, {10: 30.0, 18: 32.0, 25: 35.0})
    a, b = kinds
    ps = [piv(df, a, 10), piv(df, b, 15), piv(df, a, 18), piv(df, b, 21), piv(df, a, 25, confirm=28)]
    return df, ps, rsi, (-1 if not mirror else 1)


def _read(df, ps, rsi, t, d, mf=15, arm=20):
    D = build(df, ps, rsi, div_degrees=(0, 1, 2))
    return E3.V22.rsi_divergence(NS(_rsi=D, s={"level_degree": 2}, _ts=df["timestamp"].to_numpy()), t, d, arm, "1H", mf)


@MIRRORS
def test_the_push_still_forming_counts_as_the_second_push_marked_forming(mirror):
    df, ps, rsi, d = _case(mirror)
    got = _read(df, ps, rsi, 26, d)
    assert got["pushes"][0] == 1 and got["forming_push"][0]["push"] == "forming"   # one confirmed + the one forming
    assert got["found"] is True and got["degree"] == 0
    x = got["divergences"][0]
    assert (x["L1"]["price"], x["L2"]["price"]) == ((104.0, 106.0) if not mirror else (96.0, 94.0))
    assert x["status"] == "forming" and x["L2"]["push"] == "forming"
    later = _read(df, ps, rsi, 29, d)                                    # its swing confirmed ⇒ "confirmed", no forming push any more
    assert later["pushes"][0] == 2 and "forming_push" not in later and later["found"] is True
    assert later["divergences"][0]["L2"]["push"] == "confirmed"


@MIRRORS
def test_the_forming_push_is_read_from_bars_up_to_t_only_cut_equals_full(mirror):
    df, ps, rsi, d = _case(mirror)
    for t in range(20, N - 1):
        full = _read(df, ps, rsi, t, d)
        cut = _read(df.iloc[:t + 1].reset_index(drop=True), [p for p in ps if p.confirm_bar <= t], rsi[:t + 1], t, d)
        assert full == cut, t


@MIRRORS
def test_a_forming_push_alone_is_one_push_and_a_swing_before_the_move_is_never_compared(mirror):
    df, ps, rsi, d = _case(mirror)
    got = _read(df, ps, rsi, 26, d, mf=19)                               # the move begins after the 18 push: only the forming one inside
    assert got["found"] is False and got["degree"] is None and got["forming_push"][0]["push"] == "forming"
    assert "fewer than two pushes" in got["statements"][0]
    assert _read(df, ps, rsi, 26, d, mf=None)["found"] is None          # no move known ⇒ NA (unchanged)


# ------------------------------------------------------------------------------------------------ L5-c: the broken line's retest
ROWS = [(96.0, 96.4, 95.2, 96.2, 1.0), (96.2, 96.4, 95.6, 96.1, 1.0), (96.1, 96.2, 94.0, 94.2, 1.0),
        (94.2, 94.3, 93.0, 93.2, 1.0), (93.2, 94.6, 93.1, 94.5, 1.0), (94.5, 96.1, 94.4, 96.0, 1.0),
        (96.0, 97.3, 95.9, 97.2, 1.0), (97.2, 98.6, 97.1, 98.4, 1.0), (98.4, 98.5, 96.6, 96.7, 1.0)]


def _line_case(mirror, monkeypatch):
    """test_decision3_entry_models.test_e4b_broken_line_revisited_and_rejected's line (95 + 0.5·bar, broken down at bar 2) with the
    swing low beyond it at bar 3 (confirmed at 4): the move back up to the line begins there. Mirror: a falling line of highs."""
    rows = ROWS
    ln = {"family": "rising line of lows", "kind": "L", "slope_dir": "rising", "p1": [0, 95.0], "p2": [1, 95.5], "slope": 0.5,
          "touches": 2, "touch_groups": [[0], [1]], "value_t": 0.0, "broken": True, "break_bar": 2, "break_side": "down",
          "state": "BROKEN", "id": "L+:0-1"}
    sw = [("L", 93.0, 3, 4)]
    if mirror:
        rows = _mirror_rows(rows)
        ln = {**ln, "family": "falling line of highs", "kind": "H", "slope_dir": "falling", "p1": [0, 2 * MID - 95.0],
              "p2": [1, 2 * MID - 95.5], "slope": -0.5, "break_side": "up", "id": "H-:0-1"}
        sw = [("H", 2 * MID - 93.0, 3, 4)]
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [ln])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 4)
    V, _lvl, _d = _bare(rows, [], mirror=False, trend_at=lambda u: "UP" if mirror else "DOWN", ltf=_ltf_from(rows))
    V.levels._known0 = [NS(kind=k, price=float(p), bar=b, confirm_bar=c) for k, p, b, c in sw]
    V.step2 = None
    V.range_structure = lambda t: None
    return V, ln, (1 if mirror else -1)


@MIRRORS
def test_line_move_from_is_the_last_swing_built_away_from_the_line_after_its_break(mirror, monkeypatch):
    V, ln, d = _line_case(mirror, monkeypatch)
    R = EM.Reader(V)
    assert R.line_move_from(8, ln, d, 7) == 3
    assert R.line_move_from(3, ln, d, 7) is None                         # not confirmed yet at bar 3 (bars <= t only)
    assert R.line_move_from(8, {**ln, "break_bar": 4}, d, 7) is None     # a swing before the break is not the retest's move
    assert R.line_move_from(8, ln, d, 3) == 3                            # DECISIONS 64 (B2): the LAST away swing known at t — also one
    V.s = {**V.s, "visit_end_rule": "single_swing"}                       # formed inside the revisit (the start moves forward)
    assert R.line_move_from(8, ln, d, 3) is None                         # the earlier reading (what-if): only before the revisit


@MIRRORS
def test_both_readers_pass_the_line_retest_move_to_the_rsi_read(mirror, monkeypatch):
    V, ln, d = _line_case(mirror, monkeypatch)
    seen = []

    def ev(self, t, dd, lvl, arm, appr=None, move_from=None, cm=None, read_ok=None):
        seen.append((str(lvl.get("id")), move_from))
        return {"label": None, "evidence": [], "evidence_list": {"required": "absent"}, "confirming": {}, "channel_evidence": {},
                "rsi": {}}
    monkeypatch.setattr(EM.Reader, "evidence", ev)
    monkeypatch.setattr(EM.PE, "for_entry", lambda *a, **k: {})
    out = EM.read(V, 8, "UP" if mirror else "DOWN", [])
    assert [e["object"] for e in out["entries"]] == ["broken_line"]
    assert seen == [("line:" + ln["id"], 3)]                             # the 15M reader
    seen.clear()
    V._em5_memo = {}
    F = EM5.TF.of(V)
    lines5 = [e for j in range(13, F.n) for e in EM5.read5(V, j, "UP" if mirror else "DOWN", [])["entries"]
              if e["object"] == "broken_line"]
    assert lines5 and all(mf == 3 for _id, mf in seen)                    # the 5M reader: the same move start
