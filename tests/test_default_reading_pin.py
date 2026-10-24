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


# pins the default reading as of PR #385; change only with a before/after chart
PIN_DEFAULT = {("abc", "15M"): "bee6106f8ae0cff75c0b22e822cecdee9369a03e47395aa1089cccd9f5b2474d",
               ("abc", "5M"): "bee6106f8ae0cff75c0b22e822cecdee9369a03e47395aa1089cccd9f5b2474d",
               ("oct12_bear", "15M"): "842dfe9ac4af0da85c32667b0bcfdc2903be98c4b93e8f00f667f16472834920",
               ("oct12_bear", "5M"): "a1d15a44183d1d9291b3d2b5fba9cf89dd5ef780d9e69a68ed42dc527f5d90e0",
               ("oct12_bull", "15M"): "c25437a23efdf6afdd5eb77bac22c5c0e74b528ab3ef59ad10d54aab4664667e",
               ("oct12_bull", "5M"): "d035c754c8760736c3d246797684ce07185543ee4d51da445d5e2e46a177dc12"}


def test_the_pinned_settings_are_the_defaults():
    assert {k: S3.DEFAULTS[k] for k in DEFAULT} == DEFAULT


@pytest.mark.parametrize("name,trigger_tf", sorted(PIN_DEFAULT))
def test_default_reading_full_rows_are_pinned(name, trigger_tf):
    rows = _rows(name, trigger_tf)
    assert rows and _digest(rows) == PIN_DEFAULT[(name, trigger_tf)]
