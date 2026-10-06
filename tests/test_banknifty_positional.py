"""tests/test_banknifty_positional.py — H-POS1 BANKNIFTY daily loader (holdout cut) आणि pre-registered नियम. Network नाही."""
import numpy as np
import pandas as pd

import banknifty_positional as B


def _csv(tmp_path, rows, header="Index Name,Date,Open,High,Low,Close"):
    p = tmp_path / "bn.csv"
    p.write_text(header + "\n" + "\n".join(rows) + "\n")
    return str(p)


def test_loader_parses_niftyindices_format_and_cuts_holdout(tmp_path):
    rows = ["NIFTY BANK,02 Jan 2015,\"18,700.10\",18800,18650,18790",
            "NIFTY BANK,01 Jan 2015,18600,18720,18550,18700",
            "NIFTY BANK,28 Mar 2024,47000,47300,46900,47124",
            "NIFTY BANK,01 Apr 2024,47200,47600,47100,47500",           # holdout ⇒ कापला
            "NIFTY BANK,02 Jan 2015,18700.10,18800,18650,18790"]       # duplicate
    df = B.load_banknifty_daily(_csv(tmp_path, rows))
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close"]
    assert df["timestamp"].is_monotonic_increasing and df["timestamp"].max() <= pd.Timestamp("2024-03-31 23:59")
    assert len(df) == 3 and df.loc[1, "open"] == 18700.10


def test_loader_alt_headers_and_bad_rows(tmp_path):
    rows = ["01-01-2015,100,110,95,105", "02-01-2015,105,104,100,103", "03-01-2015,abc,1,1,1"]   # high<open ⇒ वगळा; abc ⇒ वगळा
    df = B.load_banknifty_daily(_csv(tmp_path, rows, header=" Date ,Open ,High ,Low ,Close "))
    assert len(df) == 1 and df.loc[0, "timestamp"] == pd.Timestamp("2015-01-01")


def test_loader_missing_columns_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        B.load_banknifty_daily(_csv(tmp_path, ["01 Jan 2015,1,2"], header="Date,Open,High"))


def test_level_edge_rule_needs_both_periods():
    def row(eng, per, bk, tl, tr, z):
        return {"engine": eng, "period": per, "अंतर": bk, "touch_level%": tl, "touch_random%": tr, "z_touch": z}
    tab = pd.DataFrame([row("DYN_D", "IS", "1.0–2.0%", 30, 40, -2.5), row("DYN_D", "VAL", "1.0–2.0%", 31, 40, -2.1),
                        row("SRV3_DW", "IS", "1.0–2.0%", 30, 40, -3.0), row("SRV3_DW", "VAL", "1.0–2.0%", 38, 40, -2.2),   # VAL फरक < 3pp
                        row("SRV3_DW", "IS", "0.5–1.0%", 50, 60, -2.5)])                                                    # VAL नाही
    assert B.level_edge_cells(tab) == [("DYN_D", "1.0–2.0%")]
    assert B.level_edge_cells(pd.DataFrame()) == []


def test_run_on_synthetic_series_smoke():
    rng = np.random.default_rng(0)
    n = 160
    ts = pd.bdate_range("2021-03-01", periods=n)
    c = 30000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]]
    dd = pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) * 1.004, "low": np.minimum(o, c) * 0.996, "close": c})
    tab, rows = B.run(dd)
    assert set(tab["engine"]) <= set(B.ENGINES) if len(tab) else True
    if len(rows):
        assert set(rows["period"]) <= {"IS", "VAL"} and "OE_1D" not in set(rows["engine"])


def test_iso_dates_are_not_read_day_first(tmp_path):
    rows = ["2021-09-01,100,110,95,105", "2021-09-02,105,112,101,110", "2024-03-28,1,2,0.5,1.5", "2024-04-01,1,2,0.5,1.5"]
    df = B.load_banknifty_daily(_csv(tmp_path, rows, header="date,open,high,low,close"))
    assert list(df["timestamp"].dt.strftime("%Y-%m-%d")) == ["2021-09-01", "2021-09-02", "2024-03-28"]


def test_upstox_v3_timestamp_with_offset(tmp_path):
    rows = ["2015-01-01T00:00:00+05:30,100,110,95,105", "2015-01-02T00:00:00+05:30,105,112,101,110"]
    df = B.load_banknifty_daily(_csv(tmp_path, rows, header="date,open,high,low,close"))
    assert list(df["timestamp"].dt.strftime("%Y-%m-%d")) == ["2015-01-01", "2015-01-02"]
