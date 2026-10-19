"""Q16 (Abhi) — ⑥ commitment = level वरची reversal candle. प्रत्येक form: level वर ③ + ⑥ ✔, level पासून दूर ③ ✘; pullback-दिशेची candle /
doji / inside bar ⇒ वाट; grade (extreme पलीकडे / engulf ⇒ A, wick-only + close पलीकडे ⇒ B); commit_beyond default close; extreme = what-if."""
import numpy as np
import pytest

from decision3 import method as M
from decision3 import settings as S3

S = S3.load()
LVL = {"lo": 100.0, "hi": 102.0}
FAR = {"lo": 90.0, "hi": 92.0}


def A_of(rows):
    a = np.array(rows, float)
    return {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}


# Grade: merged (2-candle) forms ⇒ "मागची candle" = pattern आधीची (t − 2; Q30) — doji / inside / star / tweezer B जोवर close t − 2 च्या
# extreme पलीकडे नाही.
FORMS = {
    "engulf": ([(106, 106.5, 103.5, 104), (104, 104.3, 101.2, 101.6), (101.4, 104.8, 101, 104.6)], "A"),
    "pin": ([(106, 106.4, 104, 104.2), (104, 104.3, 101.5, 102.2), (102.1, 102.9, 100.2, 102.7)], "B"),
    "doji_confirm": ([(102.5, 103, 101.8, 102.0), (101.5, 102.0, 100.4, 101.55), (101.6, 103.2, 101.4, 103.0)], "B"),
    "inside_break": ([(104, 104.5, 100.5, 101.0), (101.1, 102.0, 100.8, 101.6), (101.6, 103.0, 101.5, 102.8)], "B"),
    "star": ([(104, 104.4, 101, 101.2), (101.0, 101.5, 100.5, 101.2), (101.3, 103.4, 101.2, 103.2)], "B"),
    "tweezer": ([(103.5, 104, 102.6, 103), (102.5, 102.8, 100.3, 100.8), (100.9, 103.5, 100.32, 103.3)], "B"),
    "strong_close": ([(103, 103.5, 101.5, 101.7), (101.6, 102.4, 101.4, 102.0), (102.0, 103.5, 101.9, 103.4)], "A"),
}


@pytest.mark.parametrize("form", sorted(FORMS))
def test_each_reversal_form_passes_at_level_and_fails_away(form):
    rows, grade = FORMS[form]
    A = A_of([(107, 107.5, 105, 106)] + rows)                                       # आधीचा bar level वर ⇒ "उलट बाजूने आलेली"
    t = len(rows)
    ok3, _ = M.at_level(A, t, M.UP, LVL, int(S["touch_window_bars"]))
    ok6, why6, cm = M.commitment(A, t, M.UP, LVL, {**S, "candle_rule": "ratio"})   # the legacy ratio forms (what-if); method forms below
    assert ok3 and ok6, (form, why6)
    assert cm["form"] == form and cm["grade"] == grade, cm
    assert not M.at_level_or_confirm(A, t, M.UP, FAR, S)[0]                          # engine चा ③ gate: level पासून दूर ⇒ ✘
    far_ok, far_why, _ = M.commitment(A, t, M.DOWN, FAR, S)                          # तीच candle विरुद्ध दिशेने ⇒ ⑥ ✘
    assert not far_ok


@pytest.mark.parametrize("form", sorted(FORMS))
def test_each_form_fails_in_level_eval_pipeline_away_from_level(form):
    """_level_eval मध्ये ③ ✘ ⇒ ⑥ चालतच नाही (pipeline): level दूर असताना कुठलाही form setup देत नाही."""
    from decision3 import engine as E3
    rows, _ = FORMS[form]
    A = A_of([(107, 107.5, 105, 106)] + rows)
    t = len(rows)
    V = E3.V22.__new__(E3.V22)
    V.s, V._ts = S, None
    V.levels = type("Lv", (), {"A": A, "ts": [None] * (t + 1)})()
    V.pb = type("Pb", (), {"at": lambda self, t, d: {"open": True, "why_open": "fixture", "legs": 1}})()
    dec, chk, _ = V._level_eval(t, "UP", {**FAR, "role": "support"}, None, [])
    assert chk["③"][0] is False and "⑥" not in chk and dec != "setup", chk


def test_down_mirror_engulf():
    rows = [(94, 96.5, 93.5, 96), (96, 98.8, 95.7, 98.4), (98.6, 99.0, 95.2, 95.4)]   # bear call: resistance 98–100 वर engulf
    A = A_of([(93, 95, 92.5, 94)] + rows)
    lvl = {"lo": 98.0, "hi": 100.0}
    assert M.at_level(A, 3, M.DOWN, lvl, 3)[0]
    ok, why, cm = M.commitment(A, 3, M.DOWN, lvl, S)
    assert ok and cm["form"] == "engulf" and cm["grade"] == "A"


@pytest.mark.parametrize("last, reason", [((102.5, 102.8, 100.5, 100.9), "pullback"),          # अजून खाली
                                          ((101.0, 101.8, 100.3, 101.05), "doji"),             # level वर doji
                                          ((101.2, 101.9, 101.0, 101.5), "inside")])           # inside bar
def test_waits_one_candle(last, reason):
    rows = [(102.5, 102.6, 100.8, 101.0) if reason == "inside" else (104, 104.3, 101.2, 101.6), last]
    A = A_of([(107, 107.5, 105, 106)] + rows)
    ok, why, cm = M.commitment(A, 2, M.UP, LVL, S)
    assert not ok and cm.get("wait") == reason, why


def test_doji_then_confirming_candle_passes():
    rows = [(102.5, 103, 101.8, 102.0), (101.5, 102.0, 100.4, 101.55)]
    A = A_of([(107, 107.5, 105, 106)] + rows)
    assert M.commitment(A, 2, M.UP, LVL, S)[2].get("wait") == "doji"                 # doji ⇒ वाट
    A2 = A_of([(107, 107.5, 105, 106)] + rows + [(101.6, 103.2, 101.4, 103.0)])
    assert M.commitment(A2, 3, M.UP, LVL, S)[2]["form"] == "doji_confirm"             # पुढची candle पुष्टी ⇒ ✔


def test_close_beyond_prev_close_is_minimum_and_extreme_mode_is_stricter():
    rows, _ = FORMS["pin"]                                                           # close > मागचा close, पण < मागचा high
    A = A_of([(107, 107.5, 105, 106)] + rows)
    assert M.commitment(A, 3, M.UP, LVL, S)[0]
    assert not M.commitment(A, 3, M.UP, LVL, {**S, "commit_beyond": "extreme"})[0]
    bad = A_of([(107, 107.5, 105, 106), (104, 104.3, 101.5, 102.2), (101.0, 102.1, 100.2, 101.9)])   # close मागच्या close खाली
    assert not M.commitment(bad, 2, M.UP, LVL, S)[0]


def test_default_commit_beyond_close_and_validation():
    assert S["commit_beyond"] == "close"
    with pytest.raises(ValueError):
        M.commitment(A_of(FORMS["pin"][0]), 2, M.UP, LVL, {**S, "commit_beyond": "Close"})


def test_entry_window_end_exclusive():
    import pandas as pd
    rows, _ = FORMS["engulf"]
    A = A_of(rows)
    day = pd.Timestamp("2030-01-07")
    tss = lambda hm: [day + pd.Timedelta(hours=9, minutes=45), day + pd.Timedelta(hours=10), pd.Timestamp(f"2030-01-07 {hm}")]  # noqa: E731
    L = {**S, "session_windows": True}                                     # legacy: the window inside the reading (what-if)
    assert M.commitment(A, 2, M.UP, LVL, L, tss("15:00"))[0]
    assert not M.commitment(A, 2, M.UP, LVL, L, tss("15:15"))[0]
    assert not M.commitment(A, 2, M.UP, LVL, {**L, "entry_first_bar": False}, tss("09:15"))[0]   # जुना नियम (pin, Abhi 13 Oct)
    assert M.commitment(A, 2, M.UP, LVL, S, tss("15:15"))[0]               # method P2: the reading never looks at the clock …
    from types import SimpleNamespace as NS
    from decision3 import engine as E3
    V = NS(s=S, _ts=np.array([pd.Timestamp(f"2030-01-07 {hm}") for hm in ("09:15", "09:30", "15:00", "15:15")], dtype="datetime64[ns]"))
    win = [E3.V22.entry_window(V, i) for i in range(4)]                   # … the entry hours are the operational schedule after it
    assert win == [True, True, True, False] and E3.V22.entry_window(NS(s={**S, "entry_first_bar": False}, _ts=V._ts), 0) is False


COMPARE_FORMS = {                                                          # method §3: body and wicks compared — demand (UP) at 100–101
    "engulf": [(103, 103.2, 102.6, 102.8), (102.6, 102.7, 101.0, 101.2), (101.1, 103.0, 100.9, 102.9)],
    "star": [(104.0, 104.1, 101.4, 101.5), (101.4, 101.6, 100.4, 101.45), (101.3, 102.9, 101.2, 102.8)],
    "doji_confirm": [(103, 103.2, 102.6, 102.7), (101.6, 102.2, 100.6, 101.6), (101.7, 102.5, 101.5, 102.4)],
    "tweezer": [(103.5, 103.6, 102.4, 102.6), (102.6, 102.7, 100.3, 100.9), (100.9, 101.8, 100.5, 101.7)],
    "pin": [(103, 103.2, 102.6, 102.8), (102.8, 103.0, 101.9, 102.2), (102.3, 102.5, 100.1, 102.4)],
    "strong_close": [(103, 103.2, 102.6, 102.8), (102.0, 102.3, 101.9, 102.2), (101.0, 102.9, 100.9, 102.8)],
    "inside_break": [(101.0, 102.5, 100.4, 102.2), (101.6, 102.0, 101.3, 101.8), (101.8, 102.8, 101.7, 102.7)],
    "strong_close_2": [(102.0, 102.2, 101.8, 101.9), (101.0, 101.6, 100.8, 101.4), (101.4, 102.2, 101.0, 101.9)],
}


@pytest.mark.parametrize("form", sorted(COMPARE_FORMS))
@pytest.mark.parametrize("mirror", [False, True], ids=["demand", "supply"])
def test_commitment_forms_by_comparing_body_and_wicks(form, mirror):
    """Method §3 Commitment: "any recognised reversal form … described by comparing body and wicks, never by ratios". Mirror: supply."""
    rows = COMPARE_FORMS[form]
    if mirror:
        rows = [(2 * 101.5 - o, 2 * 101.5 - lo, 2 * 101.5 - h, 2 * 101.5 - c) for o, h, lo, c in rows]
    A = A_of(rows)
    d = M.DOWN if mirror else M.UP
    assert M.reversal_form(A, 2, d, S) [0] == form
    for k in ("commit_body", "commit_close_frac", "pin_wick_min", "star_body_max", "tweezer_tol", "doji_body_max", "candle_avg_n"):
        assert k in S3.DEFAULTS                                            # legacy what-if values stay registered, never read here
    assert M.is_doji(101.6, 102.2, 100.6, 101.6, S) and not M.is_doji(101.0, 102.9, 100.9, 102.8, S)


def test_range_state_released_when_commitment_closes_beyond_cluster():
    rows = [(101.6, 102.0, 101.0, 101.5), (101.5, 101.9, 101.1, 101.52), (101.55, 101.95, 101.05, 101.5)]   # overlap + doji
    A = A_of(rows + [(101.5, 103.4, 101.4, 103.3)])                                   # cluster वर close
    assert M.range_state(A_of(rows), 2, S)
    assert M.range_broken_by(A, 3, M.UP, S) and not M.range_broken_by(A, 3, M.DOWN, S)
    A2 = A_of(rows + [(101.5, 101.98, 101.3, 101.9)])                                 # cluster आतच ⇒ range चालू
    assert not M.range_broken_by(A2, 3, M.UP, S)


def test_confirming_candle_after_doji_inherits_step3():
    # touch 2 bars before the doji; confirmation candle is outside the 3-bar touch window but must still count (Q16 "wait one candle")
    rows = [(107, 107.5, 105, 106), (105.8, 106, 101.5, 102.5), (102.6, 103.4, 102.4, 103.0), (103.1, 103.6, 102.6, 103.12),
            (103.2, 105.0, 103.1, 104.8)]
    A = A_of(rows)
    assert not M.at_level(A, 4, M.UP, LVL, int(S["touch_window_bars"]))[0]
    assert M.commitment(A, 3, M.UP, LVL, S)[2].get("wait") == "doji"
    ok, why = M.at_level_or_confirm(A, 4, M.UP, LVL, S)
    assert ok and "पुष्टी" in why
    ok6, _, cm = M.commitment(A, 4, M.UP, LVL, S)
    assert ok6 and cm["form"] == "doji_confirm"
    A2 = A_of(rows[:3] + [(103.1, 103.9, 102.6, 103.7), rows[4]])                   # t − 1 doji नाही ⇒ वारसा नाही
    assert not M.at_level_or_confirm(A2, 4, M.UP, LVL, S)[0]


def test_merged_form_graded_against_candle_before_pattern():
    """Q30: doji_confirm — pattern आतल्या doji (t − 1) च्या high पलीकडे close पुरेसा नाही; pattern आधीच्या candle (t − 2) च्या high
    पलीकडे close ⇒ A, नाहीतर B. किमान अट पण t − 2 च्या close वर."""
    pre = [(107, 107.5, 105, 106), (102.5, 103, 101.8, 102.0), (101.5, 102.0, 100.4, 101.55)]
    a = M.commitment(A_of(pre + [(101.6, 103.6, 101.4, 103.4)]), 3, M.UP, LVL, S)[2]
    b = M.commitment(A_of(pre + [(101.6, 102.9, 101.4, 102.8)]), 3, M.UP, LVL, S)[2]
    assert a["form"] == b["form"] == "doji_confirm" and a["grade"] == "A" and b["grade"] == "B"
    c = M.commitment(A_of(pre + [(101.6, 102.2, 101.4, 101.9)]), 3, M.UP, LVL, S)                 # पुष्टी नाही (doji high खाली) ⇒ ✘
    assert not c[0]


@pytest.mark.parametrize("mirror", [False, True], ids=["demand", "supply"])
def test_a_merged_form_that_fails_falls_back_to_the_one_candle_form(mirror):
    """Review: a strong close whose low sits in the previous candle's lower wick also reads as a tweezer (2 candles) — measured against
    t − 2 the merged read fails, so the candle is read as the 1-candle strong close it is (never lost)."""
    rows = [(104, 104.2, 102.8, 103.0), (102.6, 102.7, 101.0, 101.5), (101.6, 103.0, 101.2, 102.9)]
    lvl = {"lo": 100.5, "hi": 101.6}
    d = M.UP
    if mirror:
        rows = [(2 * 101.5 - o, 2 * 101.5 - lo, 2 * 101.5 - h, 2 * 101.5 - c) for o, h, lo, c in rows]
        lvl, d = {"lo": 2 * 101.5 - 101.6, "hi": 2 * 101.5 - 100.5}, M.DOWN
    A = A_of(rows)
    assert M.reversal_form(A, 2, d, S) == ("tweezer", 2)
    ok, why, cm = M.commitment(A, 2, d, lvl, S)
    assert ok and cm["form"] == "strong_close" and cm["merged"] == 1, why


def test_doji_waits_and_big_is_judged_against_the_visit():
    """Method §3: a doji (body smaller than each wick) on the area ⇒ wait for the next candle; "big" = larger than the other candles of
    the same visit (no visit context ⇒ no reading)."""
    A = A_of([(103, 103.2, 102.6, 102.8), (101.2, 101.9, 100.5, 101.25)])
    assert M.commitment(A, 1, M.UP, LVL, S)[2].get("wait") == "doji"
    B = A_of([(101.0, 101.3, 100.8, 101.1), (101.1, 101.4, 100.9, 101.0), (101.0, 102.6, 100.9, 102.5)])
    assert M.candle_read(B, 2, S, 0)["big_body"] is True and M.candle_read(B, 1, S, 0)["big_body"] is False
    assert M.candle_read(B, 2, S)["big_body"] is None                     # no visit context ⇒ no "big" reading


@pytest.mark.parametrize("mirror", [False, True], ids=["bottom", "top"])
def test_zone_pattern_double_by_comparison_in_time_order(mirror):
    """Method §3 equal: the later low reaches the earlier swing candle's own band (wick to body) and does not go beyond it ⇒ double
    bottom; a later low beyond the earlier one is a new low, not a double bottom. Mirror: tops."""
    def A_lows(l2):
        rows = [(103, 103.2, 102.4, 102.5), (102.5, 102.6, 101.5, 101.6), (101.6, 101.7, 100.0, 100.4), (100.4, 101.8, 100.3, 101.7),
                (101.7, 102.4, 101.6, 102.3), (102.3, 102.4, 101.0, 101.1), (101.1, 101.2, l2, 100.6), (100.6, 102.0, 100.5, 101.9),
                (101.9, 102.1, 101.5, 101.8)]
        if mirror:
            rows = [(2 * 101.5 - o, 2 * 101.5 - lo, 2 * 101.5 - h, 2 * 101.5 - c) for o, h, lo, c in rows]
        return A_of(rows)
    d = M.DOWN if mirror else M.UP
    word = "double top" if mirror else "double bottom"
    assert M.zone_pattern(A_lows(100.2), 0, 8, d, S) == word               # 100.2 inside 100.0–100.4 (the first low's wick to body)
    assert M.zone_pattern(A_lows(99.5), 0, 8, d, S) != word                # beyond the first low ⇒ not equal


def test_entry_window_is_applied_after_the_read_in_v22(monkeypatch):
    """P2: the reading never looks at the clock; V22 applies the operational entry hours after it (⑥ names both)."""
    from tests.test_decision3_flip import _HANDOVER, _default_case
    from decision3 import engine as E3
    V = _default_case(_HANDOVER)
    assert V.decide(741)["decision"] == "setup"
    monkeypatch.setattr(E3.V22, "entry_window", lambda self, t: False)
    r = V.decide(741)
    assert r["decision"] == "wait" and r["checklist"]["⑥"][1].startswith("entry वेळ-खिडकीबाहेर (operational schedule) · reading: commitment")

