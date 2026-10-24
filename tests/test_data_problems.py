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
