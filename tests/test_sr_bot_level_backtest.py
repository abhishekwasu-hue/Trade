"""tests/test_sr_bot_level_backtest.py -- जुने Dynamic वि. SR V3 levels: 5-Min Instant आणि 15M Reversal bots चे नियम (कृत्रिम, network-free)."""
import numpy as np
import pandas as pd
import pytest

import run_sr_bot_level_backtest as RUN
import sr_bot_level_backtest as SB


def minutes(days=30, seed=5, start="2024-01-01"):
    rng = np.random.default_rng(seed)
    out, price = [], 22000.0
    for d in pd.bdate_range(start, periods=days):
        for m in range(375):
            t = d + pd.Timedelta(hours=9, minutes=15 + m)
            step = rng.normal(0, 4)
            o, c = price, price + step
            out.append({"timestamp": t, "open": o, "high": max(o, c) + abs(rng.normal(0, 2)), "low": min(o, c) - abs(rng.normal(0, 2)), "close": c})
            price = c
    return pd.DataFrame(out)


def test_prepare_frames_and_no_lookahead_closed_bars():
    p = SB.prepare(minutes(days=5))
    assert set(p.frames) == {"5min", "15min", "30min", "60min"} and len(p.days) == 5 and len(p.rsi1) == len(p.df1)
    t = p.days[2] + pd.Timedelta(hours=10, minutes=17)
    c15 = SB._closed(p, "15min", t, 10)
    assert (c15["end"] <= t).all() and c15["end"].iloc[-1] == p.days[2] + pd.Timedelta(hours=10, minutes=15)
    assert p.frames["15min"]["timestamp"].iloc[0] == p.days[0] + pd.Timedelta(hours=9, minutes=15)


def test_levels_both_sources_and_grade_filter():
    p = SB.prepare(minutes(days=30))
    t = p.days[-1] + pd.Timedelta(hours=11, minutes=15)
    spec = SB.BOTS["5m_instant"]
    dyn = SB.levels_at(p, spec, "DYNAMIC", t)
    v3 = SB.levels_at(p, spec, "SR_V3", t)
    assert all(isinstance(x, float) for x in dyn + v3)
    loose = SB.levels_at(p, SB.BotSpec(**{**spec.__dict__, "v3_grades": ("A", "B", "C")}), "SR_V3", t)
    assert set(v3) <= set(loose)


def test_simulate_rules_on_handmade_day(monkeypatch):
    """एकच level 22000: bar 1 ला खालून स्पर्श, किंमत level च्या वर (BULLISH), RSI < 40 ⇒ long; target 0.2% ⇒ TARGET."""
    day = pd.Timestamp("2024-03-01")
    rows = []
    for m in range(375):
        t = day + pd.Timedelta(hours=9, minutes=15 + m)
        px = 22010.0 if m == 0 else 22000.5 if m == 1 else 22000.5 + 2.0 * (m - 1)
        rows.append({"timestamp": t, "open": px, "high": px + 1, "low": px - 1 if m != 1 else 21999.0, "close": px})
    p = SB.prepare(pd.DataFrame(rows))
    p.rsi1[:] = 30.0
    monkeypatch.setattr(SB, "levels_at", lambda prep, spec, source, t: [22000.0])
    tr = SB.simulate(p, SB.BOTS["5m_instant"], "DYNAMIC", start="2024-03-01")
    assert len(tr) == 1
    r = tr.iloc[0]
    assert r["direction"] == "BULLISH" and r["reason"] == "TARGET" and r["level"] == 22000.0
    assert r["pts"] == pytest.approx(r["entry"] * 0.002) and r["r"] == pytest.approx(4.0)
    p.rsi1[:] = 55.0                                                          # RSI gate अपयशी
    assert SB.simulate(p, SB.BOTS["5m_instant"], "DYNAMIC", start="2024-03-01").empty


def test_simulate_sl_cooldown_and_max_hits(monkeypatch):
    """level 22000 वर वारंवार स्पर्श, प्रत्येक वेळी SL: कमाल 2 trades/level/day, SL नंतर 15 मिनिटं cooldown."""
    day = pd.Timestamp("2024-03-01")
    rows = []
    for m in range(375):
        t = day + pd.Timedelta(hours=9, minutes=15 + m)
        cyc = m % 6
        px = {0: 22020.0, 1: 22001.0, 2: 21960.0, 3: 21990.0, 4: 22030.0, 5: 22040.0}[cyc]
        rows.append({"timestamp": t, "open": px, "high": px + 2, "low": px - 2, "close": px})
    p = SB.prepare(pd.DataFrame(rows))
    p.rsi1[:] = 30.0
    monkeypatch.setattr(SB, "levels_at", lambda prep, spec, source, t: [22000.0])
    tr = SB.simulate(p, SB.BOTS["5m_instant"], "DYNAMIC", start="2024-03-01")
    assert len(tr) == 2 and (tr["reason"] == "SL").all()
    gap = (tr["entry_time"].iloc[1] - tr["exit_time"].iloc[0]).total_seconds() / 60
    assert gap >= 15


def test_comparison_split_and_cli(tmp_path):
    fake = pd.DataFrame([{"bot": "5m_instant", "source": "DYNAMIC", "date": pd.Timestamp("2020-01-02"), "pts": 10.0, "r": 1.0, "reason": "TARGET"},
                         {"bot": "5m_instant", "source": "DYNAMIC", "date": pd.Timestamp("2023-01-02"), "pts": -5.0, "r": -1.0, "reason": "SL"}])
    c = SB.comparison(fake)
    assert list(c["period"]) == ["IS 2015→2021", "OOS 2022→"] and list(c["trades"]) == [1, 1] and SB.summarize(fake.iloc[0:0])["trades"] == 0
    assert RUN.main(["--out", str(tmp_path), "--workers", "1", "--bots", "5m_instant"], df1=minutes(days=25)) == 0
    assert (tmp_path / "sr_bot_comparison.csv").exists()
