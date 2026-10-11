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
    ok6, why6, cm = M.commitment(A, t, M.UP, LVL, S)
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
    assert M.commitment(A, 2, M.UP, LVL, S, tss("15:00"))[0]
    assert not M.commitment(A, 2, M.UP, LVL, S, tss("15:15"))[0]
    assert not M.commitment(A, 2, M.UP, LVL, S, tss("09:15"))[0]


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
