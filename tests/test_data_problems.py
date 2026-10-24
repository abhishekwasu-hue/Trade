"""DECISIONS 74 (Abhi): bad data is marked in the data layer with its evidence — never patched or hidden silently."""
import pandas as pd

from decision3 import history as HI


def test_banknifty_31_aug_1515_is_marked_with_evidence():
    (p,) = [r for r in HI.data_problems("BANKNIFTY") if r["id"] == "DP-1"]
    assert p["bars"]["15M"] == "2026-08-31 15:15" and p["status"] == "marked, not patched"
    assert len(p["evidence"]) >= 3 and any("1m" in e for e in p["evidence"]) and any("FUT" in e for e in p["evidence"])


def test_mark_adds_a_column_and_never_changes_or_drops_a_bar():
    ts = pd.date_range("2026-08-31 14:45", periods=3, freq="15min")
    df = pd.DataFrame({"timestamp": ts, "open": [57423.25, 57437.65, 57397.35], "high": [57546.4, 57443.05, 58024.95],
                       "low": [57409.7, 57374.2, 57397.35], "close": [57437.65, 57402.45, 58024.95]})
    out = HI.mark_data_problems(df, "BANKNIFTY", "15M")
    assert out["data_problem"].tolist() == ["", "", "DP-1"]
    pd.testing.assert_frame_equal(out.drop(columns="data_problem"), df)
    assert HI.mark_data_problems(df, "NIFTY", "15M")["data_problem"].eq("").all()


# ---------------------------------------------------------------------------------------------------------------- DECISIONS 84 (R5-3)
import numpy as np                                                                 # noqa: E402
import pytest                                                                      # noqa: E402

from decision3 import levels as LV                                                 # noqa: E402
from decision3 import settings as S3                                               # noqa: E402
from swings2 import engine as SE                                                   # noqa: E402

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["print_up", "print_down"])


def _session_1m(day, n_traded, flat_n, jump, after=0, start=50000.0, gap_print=False):
    """A synthetic 1m session: `n_traded` traded bars, `flat_n` identical flat bars, one print (`jump` from the flat price), `after` flat
    bars at the printed price."""
    ts = pd.date_range(f"{day} 09:15", periods=n_traded + flat_n + 1 + after, freq="1min")
    rows, p = [], start
    for i in range(n_traded):
        o, c = p, p + (3.0 if i % 2 else -2.0)
        rows.append((o, max(o, c) + 1.5, min(o, c) - 1.5, c))
        p = c
    flat = p - 0.5
    rows += [(flat, flat, flat, flat)] * flat_n
    q = flat + jump
    rows.append((q, q, q, q) if gap_print else (flat, max(flat, q), min(flat, q), q))
    rows += [(q, q, q, q)] * after
    return pd.DataFrame([(t, *r) for t, r in zip(ts, rows)], columns=["timestamp", "open", "high", "low", "close"])


def _m(x, mirror):
    return -x if mirror else x


@MIRRORS
def test_detector_finds_the_flat_run_and_the_single_last_print_with_evidence(mirror):
    d = pd.concat([_session_1m("2030-01-07", 20, 0, _m(3.0, mirror)),                      # an ordinary session: no flat run
                   _session_1m("2030-01-08", 20, 14, _m(600.0, mirror)),                    # flat run + the last print
                   _session_1m("2030-01-09", 20, 13, _m(400.0, mirror), after=1),           # the print one bar early, flat after
                   _session_1m("2030-01-10", 20, 14, _m(30.0, mirror), gap_print=True)],    # the print is itself one flat bar
                  ignore_index=True)
    r = HI.close_print_runs(d)
    assert [str(x.date()) for x in r["session"]] == ["2030-01-08", "2030-01-09", "2030-01-10"]
    assert r["n_flat"].tolist() == [14, 13, 14] and r["jump"].tolist() == pytest.approx([_m(600.0, mirror), _m(400.0, mirror),
                                                                                         _m(30.0, mirror)])
    assert r["n_after"].tolist() == [0, 1, 0] and all(len(b) == n + 1 + a for b, n, a in zip(r["bars"], r["n_flat"], r["n_after"]))
    m = HI.close_print_mask(d)
    assert m.sum() == 15 + 15 + 15 and not m[:21].any()


def test_detector_ignores_a_short_flat_run_and_a_flat_run_inside_the_session():
    d = _session_1m("2030-01-08", 20, 1, 50.0)                                      # one flat bar < dp_flat_run_min_bars
    assert S3.DEFAULTS["dp_flat_run_min_bars"] == 2 and HI.close_print_runs(d).empty
    mid = pd.concat([_session_1m("2030-01-08", 10, 5, 0.5), _session_1m("2030-01-08", 10, 0, 1.0, start=50010.0).assign(
        timestamp=lambda x: x["timestamp"] + pd.Timedelta(minutes=16))], ignore_index=True)
    assert HI.close_print_runs(mid).empty                                           # traded bars after the run ⇒ not the session end
    assert HI.close_print_runs(_session_1m("2030-01-08", 20, 1, 50.0), min_run=1)["n_flat"].tolist() == [1]


def test_frozen_tail_without_a_print_is_marked():
    d = _session_1m("2030-01-08", 20, 13, 0.0)                                      # the "print" equals the flat price ⇒ all flat
    r = HI.close_print_runs(d)
    assert r["n_flat"].tolist() == [14] and r["print_ts"].isna().all() and r["jump"].tolist() == [0.0]


@MIRRORS
def test_the_15m_bar_holding_the_run_is_marked_from_the_finer_bars(mirror):
    m1 = pd.concat([_session_1m("2030-01-07", 20, 0, 3.0), _session_1m("2030-01-08", 45, 14, _m(600.0, mirror))], ignore_index=True)
    g = m1.assign(_k=m1["timestamp"].dt.floor("15min")).groupby("_k")
    m15 = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index().rename(
        columns={"_k": "timestamp"})
    assert HI.close_print_mask(m15, "15M").sum() == 0                                # the 15M alone cannot show it
    out = HI.mark_data_problems(m15, "TESTSYM", "15M", finer=m1)
    flagged = out.loc[out["data_problem"] != "", "timestamp"].dt.strftime("%Y-%m-%d %H:%M").tolist()
    assert flagged == ["2030-01-08 10:00"] and set(out["data_problem"]) == {"", HI.CLOSE_PRINT}
    pd.testing.assert_frame_equal(out.drop(columns="data_problem"), m15)            # marked, never patched


def test_the_close_print_rule_is_listed_with_its_evidence_and_a_listed_bar_wins():
    (p,) = [r for r in HI.data_problems("NIFTY") if r["id"] == HI.CLOSE_PRINT]
    assert p["symbol"] == "ALL" and p["status"] == "marked, not patched" and "dp_flat_run_min_bars" in p["detector"]
    assert any("2026-08-03" in e for e in p["evidence"]) and any("FUT" in e for e in p["evidence"])
    m5 = pd.DataFrame({"timestamp": pd.to_datetime(["2026-08-31 15:10", "2026-08-31 15:15", "2026-08-31 15:20", "2026-08-31 15:25"]),
                       "open": [57409.25, 57397.35, 57397.35, 57397.35], "high": [57429.7, 57397.35, 57397.35, 58024.95],
                       "low": [57381.35, 57397.35, 57397.35, 57397.35], "close": [57402.45, 57397.35, 57397.35, 58024.95]})
    assert HI.mark_data_problems(m5, "BANKNIFTY", "5M")["data_problem"].tolist() == ["", "DP-2", "DP-2", "DP-1"]


# -- the guard: a data-problem bar never defines a swing extreme, a base or a refined origin
def _m15_spike(mirror, flag):
    from tests.test_pivots_dc import m15_from, walk
    m15 = m15_from(walk(25 * 30, 3, 5.0))
    last = 25 * 25 - 1                                                              # a session's last bar (after the σ warm-up)
    o = float(m15.loc[last, "open"])
    if mirror:
        m15.loc[last, ["high", "low", "close"]] = [o, o - 400.0, o - 400.0]
    else:
        m15.loc[last, ["high", "low", "close"]] = [o + 400.0, o, o + 400.0]
    if flag is not None:
        m15["data_problem"] = ""
        if flag:
            m15.loc[last, "data_problem"] = HI.CLOSE_PRINT
    return m15, last


@MIRRORS
def test_a_flagged_bar_is_never_a_swing_extreme_at_any_degree(mirror):
    m15, last = _m15_spike(mirror, None)
    raw = SE.build(m15)
    assert any(p.bar == last for p in raw["pivots"][0])                             # unflagged: the print is the swing extreme
    res = SE.build(_m15_spike(mirror, True)[0])
    assert not any(p.bar == last for d in res["pivots"] for p in res["pivots"][d])


@pytest.mark.parametrize("seed", [1, 7])
def test_unflagged_data_reads_byte_identical(seed):
    from tests.test_pivots_dc import m15_from, walk
    m15 = m15_from(walk(25 * 30, seed, 5.0))
    a, b = SE.build(m15), SE.build(m15.assign(data_problem=""))
    assert all(a["pivots"][d] == b["pivots"][d] for d in a["pivots"]) and a["stream"] == b["stream"]


@MIRRORS
def test_a_flagged_1h_candle_is_never_the_bos_base(mirror):
    Lv = LV.Levels.__new__(LV.Levels)
    rows = [(100, 101, 99, 100.5), (100.5, 101, 100, 100.8), (100.8, 104, 100.8, 104), (104, 104.5, 103, 104.2)]
    if mirror:
        rows = [tuple(200 - x for x in (o, l, h, c)) for o, h, l, c in rows]
    Lv.n = 4
    Lv.A = {k: np.array([r[i] for r in rows], float) for i, k in enumerate(("open", "high", "low", "close"))}
    Lv.h1_of = np.array([0, 1, 2, 3])
    d = -1 if mirror else 1
    origin = type("P", (), {"bar": 0})()
    Lv.dp = np.zeros(4, dtype=bool)
    assert Lv._base(d, origin, 3)[0] == 1                                            # the first trend-direction candle
    Lv.dp[1] = True
    assert Lv._base(d, origin, 3)[0] == 2                                            # flagged ⇒ never the base; the next one


@MIRRORS
def test_a_flagged_15m_bar_is_never_the_refined_origin(mirror):
    from decision3 import entry_models as EM
    from tests.test_refined_origin_base import _org
    V, lvl, d = _org(mirror)
    assert EM.Reader(V).refined(5, lvl, d)["bar"] == 1
    V, lvl, d = _org(mirror)
    V.levels.dp = np.array([i == 1 for i in range(len(V._ts))])
    rb = EM.Reader(V).refined(5, lvl, d)
    assert rb["bar"] != 1 and 1 not in rb["bars"]


def test_live_inputs_mark_the_15m_bar_from_the_5m_feed_going_forward():
    """engine3_live (the feed fix): Upstox's 15M / 5M index candles reach the reader marked — the 5M by its own flat run + print, the
    15M bar that holds them from the 5M; prices untouched."""
    import engine3_live as EL
    f = 55481.85                                                                    # BANKNIFTY 2026-10-19 (Upstox 5M / 15M)
    ltf = pd.DataFrame({"timestamp": pd.date_range("2026-10-19 15:00", periods=6, freq="5min"),
                        "open": [55518.30, 55488.10, 55431.95, f, f, f], "high": [55532.45, 55501.85, f, f, f, 55488.10],
                        "low": [55471.45, 55418.30, 55412.35, f, f, f], "close": [55486.90, 55429.20, f, f, f, 55488.10]})
    m15 = pd.DataFrame({"timestamp": pd.to_datetime(["2026-10-19 15:00", "2026-10-19 15:15"]), "open": [55518.30, f],
                        "high": [55532.45, 55488.10], "low": [55412.35, f], "close": [f, 55488.10]})
    m, l5 = EL.mark_close_prints("BANKNIFTY", m15, ltf)
    assert m["data_problem"].tolist() == ["", "DP-2"] and l5["data_problem"].tolist() == ["", "", "", "DP-2", "DP-2", "DP-2"]
    pd.testing.assert_frame_equal(m.drop(columns="data_problem"), m15)
