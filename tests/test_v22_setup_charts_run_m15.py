"""scripts/v22_setup_charts.py `run` on 15M-only symbols (BANKNIFTY: --m15 + --daily [+ --ltf + --futures]) — synthetic data,
network नाही. V22 ची गणना इथे तपासत नाही; फक्त driver: inputs वाचतो, holdout guard, --from truncation (no lookahead), pickle रचना."""
import collections
import pickle

import numpy as np
import pandas as pd
import pytest

from scripts import v22_setup_charts as VSC


def _session_bars(days, start, minutes, seed):
    """सलग trading दिवस × session bars (09:15 … 15:30 − minutes), random walk; timestamp = bar सुरुवात (naive IST)."""
    rng = np.random.default_rng(seed)
    per = (6 * 60 + 15) // minutes
    rows, px = [], 1000.0
    for d in range(days):
        day = pd.Timestamp(start) + pd.Timedelta(days=d)
        if day.weekday() >= 5:
            continue
        for k in range(per):
            o = px
            c = o + rng.normal(0, 2.0)
            h = max(o, c) + abs(rng.normal(0, 1.0))
            lo = min(o, c) - abs(rng.normal(0, 1.0))
            rows.append((day + pd.Timedelta(minutes=9 * 60 + 15 + k * minutes), o, h, lo, c, float(rng.integers(100, 1000))))
            px = c
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


@pytest.fixture
def files(tmp_path):
    m15 = _session_bars(40, "2021-01-04", 15, 1)
    d = m15.set_index("timestamp").resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    # Daily history 15M पेक्षा लांब (warm-up) — 200 सत्रं आधीची
    hist = _session_bars(300, "2020-02-03", 375, 2)
    hist["timestamp"] = hist["timestamp"].dt.normalize()
    daily = pd.concat([hist[["timestamp", "open", "high", "low", "close"]], d], ignore_index=True)
    daily = daily[daily["timestamp"] < d["timestamp"].min()].pipe(lambda x: pd.concat([x, d], ignore_index=True))
    ltf = _session_bars(40, "2021-01-04", 5, 3)
    fut = ltf[["timestamp", "volume"]].assign(contract="BANKNIFTY FUT 25 FEB 21")
    p = {}
    for name, df in (("m15", m15[["timestamp", "open", "high", "low", "close"]]), ("daily", daily), ("ltf", ltf), ("fut", fut)):
        p[name] = str(tmp_path / f"{name}.csv")
        df.to_csv(p[name], index=False)
    p["out"] = str(tmp_path / "rows.pkl")
    return p


def _run(p, *extra):
    VSC.main(["run", "--symbol", "BANKNIFTY", "--m15", p["m15"], "--daily", p["daily"], "--out", p["out"], *extra])
    return pickle.load(open(p["out"], "rb"))


def test_run_m15_with_ltf_and_futures(files):
    o = _run(files, "--ltf", files["ltf"], "--futures", files["fut"])
    m15 = pd.read_csv(files["m15"])
    assert o["symbol"] == "BANKNIFTY" and o["n"] == len(m15)
    assert set(o) >= {"setups", "m15", "daily_df", "daily_states", "decisions"}
    assert sum(o["decisions"].values()) == o["n"] == len(o["bars"])
    assert all(set(b) == {"ts", "decision", "gate", "why", "trend"} for b in o["bars"])
    assert collections.Counter(b["decision"] for b in o["bars"]) == o["decisions"]
    assert all(r["decision"] == "setup" for r in o["setups"])
    # Daily मध्ये 15M च्या शेवटच्या दिवसानंतरचा bar नाही; warm-up history आहे
    assert pd.to_datetime(o["daily_df"]["timestamp"]).max() <= pd.to_datetime(m15["timestamp"]).max().normalize()
    assert len(o["daily_df"]) > len(set(pd.to_datetime(m15["timestamp"]).dt.normalize()))


def test_run_m15_without_ltf_is_fail_closed_wait(files):
    """ltf नाही ⇒ V22 fail-closed: ⑥ "LTF data missing" ⇒ एकही setup नाही (decisions मध्ये setup 0)."""
    with pytest.warns(RuntimeWarning, match="LTF data missing"):
        o = _run(files)
    assert o["decisions"].get("setup", 0) == 0


def test_run_from_truncation_no_lookahead(files):
    """--from ⇒ फक्त त्या तारखेपासूनचे bars evaluate; आधीचे bars warm-up. पूर्ण run मधले त्याच bars चे निर्णय तेच (no lookahead —
    नंतरचे bars निकाल बदलत नाहीत, आधीचे bars दोन्हीकडे समान)."""
    full = _run(files, "--ltf", files["ltf"], "--futures", files["fut"])
    m15 = pd.read_csv(files["m15"])
    cut = str(pd.to_datetime(m15["timestamp"]).iloc[len(m15) // 2].normalize().date())
    part = _run(files, "--ltf", files["ltf"], "--futures", files["fut"], "--from", cut)
    assert part["n"] == int((pd.to_datetime(m15["timestamp"]) >= pd.Timestamp(cut)).sum()) < full["n"]
    fs = {r["ts"]: r["decision"] for r in full["setups"] if pd.Timestamp(r["ts"]) >= pd.Timestamp(cut)}
    ps = {r["ts"]: r["decision"] for r in part["setups"]}
    assert fs == ps


def test_run_requires_daily_with_m15(files):
    with pytest.raises(SystemExit):
        VSC.main(["run", "--symbol", "BANKNIFTY", "--m15", files["m15"], "--out", files["out"]])
    with pytest.raises(SystemExit):
        VSC.main(["run", "--symbol", "BANKNIFTY", "--out", files["out"]])
