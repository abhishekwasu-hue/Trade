"""PR #385 review: a full-row digest pin of the DEFAULT reading (the earlier pins — tests/test_trigger_5m.py PIN15 / PIN15_C,
tests/test_entry_models_broken_back.py, the dossier pin — now hold what-ifs and stay as they are). Default = DECISIONS 76 lifecycle
(`break_hold_rule = follow_through`), DECISIONS 79 origin base (`entry_area_refine_base = origin`), DECISIONS 64 visit rule
(`visit_end_rule = away_not_reached`), DECISIONS 58 label rule (`label_rule = evidence_count`); both trigger modes (15M decide rows,
5M decide5 rows) on the abc fixture and the 12 Oct synthetic fixture (both mirrors). Synthetic only (CI-safe)."""
import hashlib
import json

import pytest

from decision3 import engine as E3
from decision3 import settings as S3

DEFAULT = {"break_hold_rule": "follow_through", "entry_area_refine_base": "origin", "visit_end_rule": "away_not_reached",
           "label_rule": "evidence_count"}


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _engine(name, trigger_tf):
    if name == "abc":
        from tests.test_decision3_method import _abc_m15
        return E3.V22(_abc_m15(), s={"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_volume_required": False,
                                      "trigger_tf": trigger_tf})
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=name == "oct12_bull")
    return E3.V22(m15, s={"level_death_side": "role", "trigger_tf": trigger_tf}, ltf=ltf, futures=fut)


def _rows(name, trigger_tf):
    V = _engine(name, trigger_tf)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    if name == "abc":                                    # no 5M frame on abc: every decide row, read under each trigger mode
        return V.run()
    if trigger_tf == "15M":
        return [V.decide(t) for t in range(len(ts)) if ts.dt.normalize().iloc[t] == last]
    F = V.trigger_frame()                                # the 5M candles of the last session (decide5 rows)
    return [V.decide5(j) for j in range(F.n) if str(F.end[j])[:10] == str(last)[:10]]


# pins the default reading as of PR #385 + DECISIONS 94 (S1 precise: no entry change; synthetic Daily supports break one step later —
# chart review/gallery_fixes/S1_precise/P3); change only with a before/after chart
PIN_DEFAULT = {("abc", "15M"): "abc5f8d8d4013d8b7ce336319a8d875166bbae2106c793df6b49c2dd44f52100",
               ("abc", "5M"): "abc5f8d8d4013d8b7ce336319a8d875166bbae2106c793df6b49c2dd44f52100",
               ("oct12_bear", "15M"): "48ad8d98db68bbcd72a8dc8acc1a2abafa9225041f96d5b5a1123a61ae6305b9",
               ("oct12_bear", "5M"): "3aabc0f50fd042185bfa18bb280e847867e2ca3730ae6ecac85d91854f27ea32",
               ("oct12_bull", "15M"): "365b7662864f7e3d3b714bc79ba07cb51187b3369c4d97338ba81cba4ebfb3c8",
               ("oct12_bull", "5M"): "4c364ae267474fbc76f3f69db3d97857a244962e0704596aed5376f4a505dae3"}


def test_the_pinned_settings_are_the_defaults():
    assert {k: S3.DEFAULTS[k] for k in DEFAULT} == DEFAULT


@pytest.mark.parametrize("name,trigger_tf", sorted(PIN_DEFAULT))
def test_default_reading_full_rows_are_pinned(name, trigger_tf):
    rows = _rows(name, trigger_tf)
    assert rows and _digest(rows) == PIN_DEFAULT[(name, trigger_tf)]
