"""tests/test_research_stats.py — PBO (CSCV), Deflated Sharpe, permutation test; कृत्रिम डेटा, network-free."""
import numpy as np
import pytest

import research_stats as RS


def test_sharpe_and_moments_edge_cases():
    assert RS.sharpe([]) == 0.0 and RS.sharpe([1.0]) == 0.0 and RS.sharpe([2.0, 2.0, 2.0]) == 0.0
    assert RS.sharpe([1.0, 3.0]) == pytest.approx(2.0 / np.std([1.0, 3.0], ddof=1))
    assert RS.moments([1.0, 2.0]) == (0.0, 3.0)
    sk, ku = RS.moments(np.random.default_rng(1).normal(size=20000))
    assert abs(sk) < 0.1 and abs(ku - 3) < 0.15


def test_expected_max_sharpe_grows_with_trials():
    assert RS.expected_max_sharpe(1, 0.01) == 0.0
    a, b = RS.expected_max_sharpe(10, 0.01), RS.expected_max_sharpe(100, 0.01)
    assert 0 < a < b


def test_pbo_low_for_a_real_edge_and_high_for_pure_noise():
    rng = np.random.default_rng(7)
    T, N = 800, 8
    noise = rng.normal(0, 1, size=(T, N))
    assert RS.pbo_cscv(noise, S=16)["pbo"] > 0.2                                  # शुद्ध noise ⇒ IS-सर्वोत्तम OOS मध्ये randomly
    edge = noise.copy()
    edge[:, 3] += 0.4                                                               # एक trial खरोखर चांगला
    r = RS.pbo_cscv(edge, S=16)
    assert r["pbo"] < 0.05 and r["n_splits"] == 12870 and r["N"] == N


def test_pbo_degenerate_inputs():
    assert RS.pbo_cscv(np.zeros((10, 1)), S=4)["pbo"] is None
    assert RS.pbo_cscv(np.zeros((3, 4)), S=4)["pbo"] is None
    with pytest.raises(ValueError):
        RS.pbo_cscv(np.zeros(5))


def test_deflated_sharpe_penalises_many_trials():
    rng = np.random.default_rng(3)
    r = rng.normal(0.1, 1.0, 500)
    few = RS.deflated_sharpe(r, [0.0, 0.05, RS.sharpe(r)])
    many = RS.deflated_sharpe(r, list(rng.normal(0, 0.05, 200)) + [RS.sharpe(r)])
    assert 0 <= many["dsr"] <= few["dsr"] <= 1 and many["sr0"] > few["sr0"]
    assert RS.deflated_sharpe([1.0, 2.0], [0.1])["dsr"] is None


def test_shuffle_pvalue_detects_dependence_and_is_reproducible():
    rng = np.random.default_rng(0)
    x = rng.normal(size=300)
    y = x + rng.normal(scale=0.5, size=300)
    corr = lambda a, b: float(np.corrcoef(a, b)[0, 1])                               # noqa: E731
    stat, p = RS.shuffle_pvalue(corr, x, y, n_perm=200, seed=1)
    assert stat > 0.5 and p < 0.01
    _, p_null = RS.shuffle_pvalue(corr, x, rng.normal(size=300), n_perm=200, seed=1)
    assert p_null > 0.01
    assert RS.shuffle_pvalue(corr, x, y, n_perm=50, seed=2) == RS.shuffle_pvalue(corr, x, y, n_perm=50, seed=2)
