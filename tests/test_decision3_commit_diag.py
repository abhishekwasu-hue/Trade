"""⑥ diag (अहवाल): अटींचं विघटन engine च्या commitment शी जुळतं — सगळ्या अटी पास (k पैकी एक) ⇔ commitment ✔ (वेळ-खिडकी वेगळी)."""
import numpy as np

from decision3 import method as M
from decision3 import settings as S3
from scripts import v22_commit_diag as CD

S = S3.load()
LVL = {"lo": 100.0, "hi": 102.0}


def test_conditions_match_engine_commitment_on_random_bars():
    rng = np.random.default_rng(3)
    agree = hits = 0
    for _ in range(400):
        c = 101 + np.cumsum(rng.normal(0, 1, 4))
        o = np.r_[101, c[:-1]]
        h = np.maximum(o, c) + np.abs(rng.normal(0, 0.6, 4))
        lo = np.minimum(o, c) - np.abs(rng.normal(0, 0.6, 4))
        A = {"open": o, "high": h, "low": lo, "close": c}
        for d in (M.UP, M.DOWN):
            eng = M.commitment(A, 3, d, LVL, S)[0]
            mine = False
            for k in range(1, int(S["commit_merge_max"]) + 1):
                x = CD.conditions(A, 3, d, LVL, S, k)
                if x and all(v for key, v in x.items() if key not in CD.INFO):
                    mine = True
                    break
            agree += eng == mine
            hits += eng
    assert agree == 800 and hits > 0                                              # non-vacuous: काही ✔ आले


def test_conditions_are_plain_bools_for_json():
    import json
    A = {"open": np.array([101.0, 101.0]), "high": np.array([101.5, 103.0]), "low": np.array([100.5, 100.9]),
         "close": np.array([101.0, 102.8])}
    x = CD.conditions(A, 1, M.UP, LVL, S, 1)
    assert all(type(v) is bool for v in x.values()) and json.loads(json.dumps(x)) == x


def test_diag_respects_merge_window_and_commit_beyond_setting():
    import pandas as pd
    A = {"open": np.array([103, 101.0, 101.1]), "high": np.array([103.4, 101.3, 103.6]), "low": np.array([101, 100.5, 101.0]),
         "close": np.array([101.5, 101.1, 102.6])}
    early = [pd.Timestamp("2030-01-06 15:15"), pd.Timestamp("2030-01-07 09:15"), pd.Timestamp("2030-01-07 09:30")]
    assert CD.conditions(A, 2, M.UP, LVL, S, 2, early) is None                     # engine सारखं: 09:15 merged नाही
    assert CD.conditions(A, 2, M.UP, LVL, S, 2) is not None
    x = CD.conditions(A, 2, M.UP, LVL, {**S, "commit_beyond": "close"}, 1)
    assert x["beyond"] == x["beyond_close"]


def test_commit_beyond_unknown_value_raises():
    import pytest
    A = {"open": np.array([101.0, 101.0]), "high": np.array([101.5, 103.0]), "low": np.array([100.5, 100.9]),
         "close": np.array([101.0, 102.8])}
    with pytest.raises(ValueError):
        M.commitment(A, 1, M.UP, LVL, {**S, "commit_beyond": "Close"})
