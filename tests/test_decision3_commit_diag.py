"""⑥ diag (अहवाल, Q16): engine च्याच commitment वरून — निकाल नेहमी engine शी जुळतो; JSON साठी साधे bool; form / grade / वाट."""
import json

import numpy as np

from decision3 import method as M
from decision3 import settings as S3
from scripts import v22_commit_diag as CD
from tests.test_decision3_commitment_q16 import FORMS, LVL, A_of

S = S3.load()


def test_explain_matches_engine_on_random_bars():
    rng = np.random.default_rng(3)
    oks = 0
    for _ in range(300):
        c = 101 + np.cumsum(rng.normal(0, 1, 4))
        o = np.r_[101, c[:-1]]
        h = np.maximum(o, c) + np.abs(rng.normal(0, 0.6, 4))
        lo = np.minimum(o, c) - np.abs(rng.normal(0, 0.6, 4))
        A = {"open": o, "high": h, "low": lo, "close": c}
        for d in (M.UP, M.DOWN):
            x = CD.explain(A, 3, d, LVL, S)
            assert x["ok"] == M.commitment(A, 3, d, LVL, S)[0]
            oks += x["ok"]
    assert oks > 0


def test_explain_reports_form_grade_and_plain_bools():
    rows, grade = FORMS["pin"]
    A = A_of([(107, 107.5, 105, 106)] + rows)
    x = CD.explain(A, 3, M.UP, LVL, S)
    assert x["ok"] and x["form"] == "pin" and x["grade"] == grade and x["beyond_close"] and not x["beyond_extreme"]
    assert json.loads(json.dumps(x)) == x
